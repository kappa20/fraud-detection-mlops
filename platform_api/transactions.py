"""Lecture paginée (côté serveur) et corrections manuelles du dataset brut.

Source de vérité : data/raw/creditcard.csv, le fichier versionné par DVC
(voir versioning.py). Le DuckDB du projet (fraud_detection.duckdb) est
reconstruit depuis ce CSV à chaque run dlt (write_disposition="replace") :
y écrire ferait perdre les corrections au prochain pipeline.

Lecture : le CSV est chargé dans une table DuckDB *en mémoire*, reconstruite
seulement quand le fichier change (empreinte mtime+taille), puis interrogée
en SQL avec WHERE / ORDER BY / LIMIT / OFFSET. Le navigateur ne reçoit
jamais qu'une page.

Identifiant : le CSV n'a pas de clé ; `id` = position de la ligne (base 0).
Elle se décale après une suppression — d'où le verrou optimiste
(`base_version`, voir `current_epoch`) exigé à l'écriture et le rechargement de l'interface après
chaque sauvegarde.
"""

import csv
import io
import os
import threading
from collections.abc import Iterator
from pathlib import Path

import duckdb
import pandas as pd

from platform_api import dataset, state

DUCKDB_PATH = dataset.PROJECT_ROOT / "fraud_detection.duckdb"

V_COLUMNS = [f"v{i}" for i in range(1, 29)]
DATA_COLUMNS = ["time", *V_COLUMNS, "amount", "is_fraud"]
SORTABLE_COLUMNS = {"id", *DATA_COLUMNS}
MAX_PAGE_SIZE = 200
MAX_EXPORT_ROWS = 50_000

_cache_lock = threading.Lock()
_cache: dict = {"fingerprint": None, "con": None}


class StaleDatasetError(RuntimeError):
    """Le dataset a changé depuis la lecture faite par l'interface (409)."""


class UnknownRowError(ValueError):
    """Identifiant de ligne hors du dataset (404/422)."""


def current_epoch() -> str:
    """Version "structurelle" du dataset : change quand des positions de lignes
    ont pu se décaler (correction manuelle, rollback), pas lors d'un ajout."""
    return str(state.load_state()["dataset_epoch"])


def _connection() -> duckdb.DuckDBPyConnection:
    """Connexion DuckDB en mémoire, table `tx` reconstruite si le CSV a changé."""
    fingerprint = dataset.fingerprint()
    with _cache_lock:
        if _cache["fingerprint"] != fingerprint or _cache["con"] is None:
            if not dataset.RAW_CSV_PATH.exists():
                raise FileNotFoundError(
                    f"{dataset.RAW_CSV_PATH} introuvable — voir data/README.md ('dvc pull' requis)."
                )
            # Lecture via pandas plutôt que read_csv de DuckDB : le CSV peut mélanger
            # des fins de ligne LF (fichier Kaggle) et CRLF (lignes ajoutées par
            # d'anciennes versions de dataset.append_rows), que le sniffer de
            # DuckDB refuse.
            frame = pd.read_csv(dataset.RAW_CSV_PATH).rename(columns=str.lower).rename(columns={"class": "is_fraud"})
            frame = frame.astype({"time": "float64", "amount": "float64", "is_fraud": "int64"})
            frame.insert(0, "id", range(len(frame)))
            con = duckdb.connect(":memory:")
            con.register("frame", frame)
            con.execute("CREATE TABLE tx AS SELECT * FROM frame")
            con.unregister("frame")
            if _cache["con"] is not None:
                _cache["con"].close()
            _cache["con"], _cache["fingerprint"] = con, fingerprint
        return _cache["con"].cursor()


def _last_dlt_load() -> tuple[str | None, int]:
    """(load_id, nb de lignes) du dernier chargement dlt, pour la colonne
    `load_id` : approximatif (les lignes corrigées depuis ce chargement n'y
    figurent pas encore), mais indique à quel run d'ingestion une ligne se
    rattache. Silencieux si le DuckDB est absent ou verrouillé par un run."""
    if not DUCKDB_PATH.exists():
        return None, 0
    try:
        con = duckdb.connect(str(DUCKDB_PATH), read_only=True)
        try:
            load_id = con.execute(
                "SELECT load_id FROM raw._dlt_loads WHERE status = 0 ORDER BY inserted_at DESC LIMIT 1"
            ).fetchone()
            count = con.execute("SELECT count(*) FROM raw.transactions_raw").fetchone()[0]
        finally:
            con.close()
        return (load_id[0] if load_id else None), int(count)
    except duckdb.Error:
        return None, 0


def _where(
    amount_min: float | None,
    amount_max: float | None,
    is_fraud: int | None,
    time_min: float | None,
    time_max: float | None,
) -> tuple[str, list]:
    clauses, params = [], []
    for column, op, value in (
        ("amount", ">=", amount_min),
        ("amount", "<=", amount_max),
        ("is_fraud", "=", is_fraud),
        ("time", ">=", time_min),
        ("time", "<=", time_max),
    ):
        if value is not None:
            clauses.append(f"{column} {op} ?")
            params.append(value)
    return ("WHERE " + " AND ".join(clauses)) if clauses else "", params


def query_transactions(
    page: int = 1,
    page_size: int = 50,
    sort: str = "id",
    order: str = "asc",
    amount_min: float | None = None,
    amount_max: float | None = None,
    is_fraud: int | None = None,
    time_min: float | None = None,
    time_max: float | None = None,
) -> dict:
    if sort not in SORTABLE_COLUMNS:
        raise ValueError(f"Colonne de tri inconnue : {sort!r}")
    direction = "DESC" if order.lower() == "desc" else "ASC"
    page_size = max(1, min(page_size, MAX_PAGE_SIZE))
    page = max(1, page)

    where, params = _where(amount_min, amount_max, is_fraud, time_min, time_max)
    con = _connection()
    total = con.execute(f"SELECT count(*) FROM tx {where}", params).fetchone()[0]
    # `sort` provient de la liste blanche SORTABLE_COLUMNS ci-dessus : jamais
    # d'entrée utilisateur brute dans le SQL. `id` en second critère = tri stable.
    cursor = con.execute(
        f"SELECT * FROM tx {where} ORDER BY {sort} {direction}, id ASC LIMIT ? OFFSET ?",
        [*params, page_size, (page - 1) * page_size],
    )
    columns = [c[0] for c in cursor.description]
    items = [dict(zip(columns, row)) for row in cursor.fetchall()]

    load_id, loaded_rows = _last_dlt_load()
    for item in items:
        item["load_id"] = load_id if item["id"] < loaded_rows else None
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "base_version": current_epoch(),
    }


def get_transaction(row_id: int) -> dict | None:
    con = _connection()
    cursor = con.execute("SELECT * FROM tx WHERE id = ?", [row_id])
    row = cursor.fetchone()
    if row is None:
        return None
    return dict(zip([c[0] for c in cursor.description], row))


def export_csv(ids: list[int]) -> Iterator[str]:
    """Génère le CSV des lignes sélectionnées (en-tête + lignes), borné pour
    ne pas transformer l'export en téléchargement du dataset entier."""
    if len(ids) > MAX_EXPORT_ROWS:
        raise ValueError(f"Export limité à {MAX_EXPORT_ROWS} lignes.")
    con = _connection()
    placeholders = ",".join("?" for _ in ids) or "NULL"
    cursor = con.execute(f"SELECT * FROM tx WHERE id IN ({placeholders}) ORDER BY id", ids)
    columns = [c[0] for c in cursor.description]

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["transaction_id" if c == "id" else c for c in columns])
    yield buffer.getvalue()
    for row in cursor.fetchall():
        buffer.seek(0)
        buffer.truncate()
        writer.writerow(row)
        yield buffer.getvalue()


def _format(value: float | int) -> str:
    return repr(float(value)) if not isinstance(value, int) else str(value)


def apply_changes(
    base_version: str,
    creates: list[dict],
    updates: list[tuple[int, dict]],
    deletes: list[int],
) -> dict:
    """Applique un lot de corrections au CSV, de façon atomique (fichier
    temporaire puis os.replace) et en ne réécrivant que les lignes touchées :
    les autres restent identiques à l'octet près, ce qui garde un diff DVC
    minimal. Lève StaleDatasetError si des corrections/un rollback ont eu lieu
    depuis la lecture de l'interface, UnknownRowError si un identifiant n'existe pas."""
    path: Path = dataset.RAW_CSV_PATH
    with dataset.WRITE_LOCK:
        if current_epoch() != base_version:
            raise StaleDatasetError("Le dataset a été modifié depuis son affichage — rechargez la page.")

        with path.open("r", newline="") as f:
            lines = f.readlines()
        header, rows = lines[0], lines[1:]

        for row_id in [*deletes, *(row_id for row_id, _ in updates)]:
            if not 0 <= row_id < len(rows):
                raise UnknownRowError(f"Ligne inexistante : {row_id}")

        deleted = set(deletes)
        updated_rows = 0
        for row_id, fields in updates:
            if row_id in deleted:
                continue  # mise à jour d'une ligne supprimée dans le même lot : sans objet
            values = next(csv.reader([rows[row_id]]))
            for name, value in fields.items():
                if value is None:
                    continue
                values[DATA_COLUMNS.index(name)] = _format(value)
            out = io.StringIO()
            csv.writer(out, lineterminator="\n").writerow(values)
            rows[row_id] = out.getvalue()
            updated_rows += 1

        kept = [line for index, line in enumerate(rows) if index not in deleted]
        for create in creates:
            out = io.StringIO()
            csv.writer(out, lineterminator="\n").writerow(dataset.row_to_csv_values(create))
            kept.append(out.getvalue())

        # Dernière ligne éventuellement sans saut de ligne final : normalisé
        # ici pour que les lignes ajoutées ne soient pas collées à la précédente.
        kept = [line if line.endswith("\n") else line + "\n" for line in kept]

        tmp_path = path.with_suffix(".csv.tmp")
        with tmp_path.open("w", newline="") as f:
            f.write(header)
            f.writelines(kept)
        os.replace(tmp_path, path)

    return {"rows_created": len(creates), "rows_updated": updated_rows, "rows_deleted": len(deleted)}
