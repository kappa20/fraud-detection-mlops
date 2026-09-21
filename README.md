# Détection de fraude bancaire — Projet MLOps & DataOps

Projet de groupe du module **MLOps & DataOps** (Pr. Mohammed AIT DAOUD, FSBM, Université Hassan II de Casablanca, 2025/2026).

**Sujet :** Détection de fraude bancaire — Classification des transactions frauduleuses (Finance).
**Réalisé par :** équipe de 9 personnes — voir [`info.txt`](info.txt) pour la répartition des rôles Agile.
**Encadré par :** Pr. Mohammed AIT DAOUD.
**Cahier des charges :** cahier des charges du module (fourni séparément).
**Rapport final (Livrable 7) :** conservé hors dépôt (document de soutenance).

> **Statut : les 10 livrables du cahier des charges sont complets.** Voir le mapping détaillé dans le rapport final (conservé hors dépôt).

## Architecture cible

```
Sources de données → dlt (ingestion automatisée) → DuckDB (stockage local) → dbt (transformations)
   → Tests Qualité (Data Contract) → Dagster (orchestration)
   → Machine Learning (Scikit-Learn) → Tracking & Registry (MLflow) → Service ML (FastAPI)
   → Conteneurisation (Docker) → CI/CD (GitHub Actions) → Monitoring & Observabilité
```

Détail complet de l'architecture : [`docs/02_architecture.md`](docs/02_architecture.md).

## Documentation

| Document | Contenu | Livrable |
|---|---|---|
| [`docs/01_vision.md`](docs/01_vision.md) | Problématique, objectifs, utilisateurs cibles, valeur métier, Data Strategy | 1 |
| [`docs/agile/`](docs/agile/) | Product Backlog, User Stories, Sprint Planning/Review/Retrospective (3 sprints) | 2 |
| [`docs/data/data_contract.yaml`](docs/data/data_contract.yaml) | Contrat de données (schéma, règles de qualité, consommateurs) | 4 |
| [`docs/data/data_lineage.md`](docs/data/data_lineage.md) | Lignage des données, de la source au service exposé | 4 |
| [`docs/data/data_quality_report.md`](docs/data/data_quality_report.md) | Rapport de qualité (11 dimensions du cours) sur le dataset réel | 4 |
| [`docs/ml/experiments_summary.md`](docs/ml/experiments_summary.md) | Synthèse des expériences MLflow | 6 |
| [`docs/02_architecture.md`](docs/02_architecture.md) | Architecture complète, décisions techniques, limites assumées | 10 |
| [`docs/03_installation.md`](docs/03_installation.md) | Guide d'installation | 10 |
| [`docs/04_guide_utilisation.md`](docs/04_guide_utilisation.md) | Guide d'utilisation | 10 |
| [`docs/06_stack_komodo.md`](docs/06_stack_komodo.md) | Stack Komodo : ports, Dagster (UI, schedule, sensor), alertes de dérive, MLflow serveur, déploiement continu gardé par la CI | — |

## Structure du dépôt

```
projet/
├── docs/                    # Vision, Agile, Qualité des données, ML, documentation
├── data/raw/                # Dataset source (non versionné, voir data/README.md)
├── ingestion_dlt/           # Pipeline d'ingestion dlt → DuckDB
├── dbt_fraud/                # Projet dbt (staging + marts + tests + macros)
├── quality/                  # Validation shift-left du schéma
├── orchestration_dagster/    # Orchestration Dagster du pipeline
├── ml/                       # Préparation des données, entraînement, évaluation, MLflow
├── api/                      # Service FastAPI (/predict, /health, /metrics)
├── monitoring/               # Détection de dérive (PSI) + logs de prédiction
├── tests/                    # Tests automatisés + fixtures pour la CI
├── scripts/                  # Génération de la fixture synthétique CI
├── Dockerfile                # Conteneurisation du service
├── docker-compose.yml
└── .github/workflows/        # CI/CD GitHub Actions
```

## Prérequis — dataset

Le pipeline s'appuie sur le dataset public **"Credit Card Fraud Detection" (ULB)**, à télécharger manuellement depuis Kaggle. Voir [`data/README.md`](data/README.md) pour les instructions exactes.

## Installation

Détaillé dans [`docs/03_installation.md`](docs/03_installation.md). En résumé, environnement conda (recommandé, testé) :
```bash
conda create -n mlops_fraud python=3.11
conda activate mlops_fraud
pip install -r requirements.txt
```
Alternative avec `venv` :
```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Exécuter le pipeline DataOps

```bash
# 1. Placer data/raw/creditcard.csv (voir data/README.md)
# 2. Lancer le pipeline complet via Dagster :
dagster job execute -f orchestration_dagster/fraud_dagster/job.py -a fraud_pipeline_job
# ou avec l'UI web (http://localhost:3000, + démon : schedule nocturne et sensor) :
dagster dev -f orchestration_dagster/fraud_dagster/job.py
```
Sur Komodo, l'UI Dagster est le service `dagster` (port 4608).
Étapes exécutées : ingestion `dlt` (CSV → DuckDB) → validation shift-left → `dbt run` (staging + marts) → `dbt test` (27 tests qualité).

## Entraîner le modèle et le publier dans MLflow

```bash
python ml/train.py            # entraîne LogisticRegression + RandomForest, logue tout dans MLflow
mlflow ui --backend-store-uri sqlite:///mlflow.db   # explorer les runs (http://localhost:5000)
python ml/register_model.py   # enregistre le meilleur run (PR-AUC) -> Model Registry (Production) + ml/artifacts/model.pkl
```
Détails et résultats : [`docs/ml/experiments_summary.md`](docs/ml/experiments_summary.md).

## Lancer le service de scoring

```bash
# En local (sans Docker) :
uvicorn api.main:app --reload
# puis : curl http://localhost:8000/health

# Avec Docker :
docker build -t fraud-api .
docker run -p 8000:8000 fraud-api
# ou : docker compose up --build
```
Endpoints : `GET /health`, `POST /predict`, `GET /metrics` (Prometheus).

## Monitoring et dérive

```bash
python monitoring/drift_check.py   # rapport PSI -> monitoring/drift_report.md
```
Chaque appel à `/predict` est journalisé dans `monitoring/predictions_log.jsonl`. Détails : [`docs/04_guide_utilisation.md`](docs/04_guide_utilisation.md#6-surveiller-le-service).

## Tests et CI/CD

```bash
pytest tests/ -v      # tests unitaires (API, validation, métriques ML) — indépendants du dataset réel
ruff check .           # lint
```
La CI GitHub Actions (`.github/workflows/ci.yml`) exécute, à chaque push/PR, le pipeline complet (lint → tests → génération d'une fixture synthétique → ingestion dlt → validation → `dbt build` → entraînement → enregistrement du modèle → `docker build`) sans jamais dépendre du vrai fichier Kaggle. Principe cité en cours : *"Un pipeline qui ne passe pas les tests ne peut pas être mergé."*

## Équipe et rôles Agile

| Rôle | Membre(s) |
|---|---|
| Product Owner | Product Owner |
| Scrum Master | Scrum Master |
| Data Engineer | Data Engineer (lead), Data Engineer 2, Data Engineer 3 |
| ML Engineer | ML Engineer 1, ML Engineer 2 |
| Data Analyst | Data Analyst 1, Data Analyst 2 |
