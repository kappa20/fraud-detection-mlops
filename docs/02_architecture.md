# Livrable 10 — Architecture

## Vue d'ensemble

```
Sources de données → dlt (ingestion automatisée) → DuckDB (stockage local) → dbt (transformations)
   → Tests Qualité (Data Contract) → Dagster (orchestration)
   → Machine Learning (Scikit-Learn) → Tracking & Registry (MLflow) → Service ML (FastAPI)
   → Conteneurisation (Docker) → CI/CD (GitHub Actions) → Monitoring & Observabilité
```

Cette architecture est celle imposée par le cahier des charges du module ; l'implémentation détaillée de chaque brique est documentée ci-dessous et dans `docs/data/data_lineage.md` (lignage détaillé) et `docs/ml/experiments_summary.md` (détail ML/MLflow).

## Composants et responsabilités

| Composant | Rôle | Répertoire | Déclenchement |
|---|---|---|---|
| **dlt** | Ingestion automatisée du CSV source vers DuckDB, par chunks | `ingestion_dlt/` | `python ingestion_dlt/run_pipeline.py` (op Dagster `ingest`) |
| **DuckDB** | Stockage analytique local, un seul fichier (`fraud_detection.duckdb`) | racine du projet | — |
| **Validation shift-left** | Contrôle schéma/nullité/domaine juste après l'ingestion | `quality/` | `python quality/validate_schema.py` (op Dagster `validate`) |
| **dbt** | Transformations SQL versionnées et testées (staging → marts) | `dbt_fraud/` | `dbt build --profiles-dir .` (ops Dagster `transform` + `test_data`) |
| **Data Contract / Lineage** | Documentation des engagements de qualité et du flux de données | `docs/data/` | — (documentation) |
| **Dagster** | Orchestration du pipeline DataOps (ingest → validate → transform → test) | `orchestration_dagster/` | `dagster job execute -f orchestration_dagster/fraud_dagster/job.py -a fraud_pipeline_job` |
| **Scikit-Learn** | Entraînement et évaluation du modèle de classification | `ml/` | `python ml/train.py` |
| **MLflow** | Experiment Tracking + Model Registry | `mlflow.db` (SQLite) + `mlruns/` | `python ml/train.py`, `python ml/register_model.py` |
| **FastAPI** | Service d'inférence temps réel | `api/` | `uvicorn api.main:app` ou conteneur Docker |
| **Docker** | Conteneurisation du service d'inférence | `Dockerfile`, `docker-compose.yml` | `docker build` / `docker compose up` |
| **GitHub Actions** | CI/CD : lint, tests, pipeline complet sur fixture, build Docker | `.github/workflows/ci.yml` | à chaque push / pull request |
| **Monitoring** | Disponibilité, latence, métriques ML, dérive simple (PSI) | `monitoring/` | `GET /metrics` (continu), `python monitoring/drift_check.py` (à la demande) |

## Flux de données (résumé — détail complet dans `docs/data/data_lineage.md`)

```
creditcard.csv (Kaggle, local)
    │  dlt
    ▼
raw.transactions_raw (DuckDB)
    │  quality/validate_schema.py
    ▼
[validation shift-left]
    │  dbt staging
    ▼
stg_transactions
    │  dbt marts
    ▼
fct_transactions_clean → fct_transactions_features → agg_fraud_hourly_summary
    │  ml/train.py
    ▼
MLflow (Experiment Tracking) → Model Registry (Staging → Production)
    │  ml/register_model.py
    ▼
ml/artifacts/model.pkl
    │  api/model_loader.py
    ▼
Service FastAPI (POST /predict, GET /health, GET /metrics)
    │
    ▼
monitoring/predictions_log.jsonl → monitoring/drift_check.py → monitoring/drift_report.md
```

## Décisions d'architecture et alternatives écartées

| Décision | Alternative envisagée | Raison du choix |
|---|---|---|
| Orchestration Dagster en `@op`/`@job` classiques | Software-Defined Assets | Pattern déjà validé par le professeur dans le TP Chapitre 2 ; moins de risque, suffisant pour le scope du module |
| Modèle chargé depuis un `.pkl` local dans l'API | Appel à un serveur MLflow vivant depuis le conteneur | Simplifie la conteneurisation, évite un point de défaillance réseau supplémentaire en démo |
| PSI calculé à la main pour la dérive | Bibliothèque Evidently | Évite une dépendance lourde supplémentaire (risque de conflits, comme rencontré avec `protobuf` entre `dbt-core` et `mlflow`) ; le PSI est une technique standard suffisante pour une "dérive simple" |
| Un seul environnement conda partagé (dlt/dbt/dagster/ML) | Environnements séparés par étape | Plus simple pour un projet étudiant ; le conflit `protobuf` rencontré (voir ci-dessous) montre la limite de cette approche à plus grande échelle |
| Fixture synthétique versionnée pour la CI | Stocker un extrait du vrai dataset | Le dataset réel n'est pas redistribuable (licence Kaggle) ; la fixture garantit une CI reproductible sans dépendance externe |

## Limite technique rencontrée et documentée

Lors de l'installation de `mlflow` dans l'environnement partagé, pip a signalé un conflit de version sur `protobuf` avec `dbt-core` (qui exige `protobuf>=6`, alors que `mlflow` a fait downgrader vers `protobuf 5.29.6`). Vérifié empiriquement : `dbt build` continue de fonctionner correctement malgré l'avertissement. Documenté ici par souci de transparence plutôt que masqué — c'est un exemple concret des risques d'un environnement Python partagé entre plusieurs outils (cf. Chapitre 2, niveaux de maîtrise d'environnement).

## Environnement d'exécution

- **Python** : 3.11
- **Gestion des dépendances** : `requirements.txt` (pipeline complet) et `requirements-api.txt` (sous-ensemble léger pour l'image Docker du service)
- **Environnement testé** : conda (`conda create -n mlops_fraud python=3.11`), voir `docs/03_installation.md`
