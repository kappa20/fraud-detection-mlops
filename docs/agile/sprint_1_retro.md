# Sprint 1 — Retrospective

## Ce qui a bien fonctionné

- Reprendre le pattern déjà validé par le professeur (TP Chapitre 2) plutôt que de partir d'une feuille blanche a évité plusieurs erreurs de conception (structure des ops Dagster, séparation ingestion/validation/transformation).
- Écrire `docs/01_vision.md` **avant** de coder a clarifié dès le départ les métriques cibles (PR-AUC plutôt qu'accuracy), ce qui a évité un aller-retour en Sprint 2.

## Ce qui a été difficile

- **dlt normalise les noms de colonnes** (`Time` → `time`, `Amount` → `amount`) à l'ingestion : la première version de `quality/validate_schema.py` cherchait les colonnes en casse d'origine (`Time`, `Amount`, `Class`) et échouait. Corrigé en alignant les noms attendus sur la normalisation snake_case de dlt.
- Le cours (Chapitre 2) ne détaille pas la syntaxe `dlt`/`DuckDB` avec du code — il a fallu s'appuyer sur la documentation officielle des outils en complément du TP.

## Actions pour le sprint suivant

- Documenter explicitement la normalisation de noms dlt dans le Data Contract (Sprint 2) pour éviter que d'autres membres de l'équipe reproduisent la même erreur.
- Prévoir du temps dédié à la lecture de la doc officielle dbt/dagster en début de Sprint 2, plutôt qu'en réaction à un blocage.
