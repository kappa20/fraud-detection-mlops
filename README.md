# Détection de fraude bancaire — Projet MLOps & DataOps

Projet de groupe du module **MLOps & DataOps** (Pr. Mohammed AIT DAOUD, FSBM, Université Hassan II de Casablanca, 2025/2026).

**Sujet :** Détection de fraude bancaire — Classification des transactions frauduleuses (Finance).
**Équipe :** voir [`info.txt`](../info.txt).
**Cahier des charges :** [`PROJETS.pdf`](../PROJETS.pdf).
**Rapport final (Livrable 7) :** [`RAPPORT_FINAL.md`](RAPPORT_FINAL.md).

> **Statut : les 10 livrables du cahier des charges sont complets.** Voir le mapping détaillé dans [`RAPPORT_FINAL.md`](RAPPORT_FINAL.md#5-mapping-des-10-livrables-du-cahier-des-charges).

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
| [`RAPPORT_FINAL.md`](RAPPORT_FINAL.md) | Synthèse finale, résultats clés, plan de démo orale | 7 |
| [`docs/01_vision.md`](docs/01_vision.md) | Problématique, objectifs, utilisateurs cibles, valeur métier, Data Strategy | 1 |
| [`docs/agile/`](docs/agile/) | Product Backlog, User Stories, Sprint Planning/Review/Retrospective (3 sprints) | 2 |
| [`docs/data/data_contract.yaml`](docs/data/data_contract.yaml) | Contrat de données (schéma, règles de qualité, consommateurs) | 4 |
| [`docs/data/data_lineage.md`](docs/data/data_lineage.md) | Lignage des données, de la source au service exposé | 4 |
| [`docs/data/data_quality_report.md`](docs/data/data_quality_report.md) | Rapport de qualité (11 dimensions du cours) sur le dataset réel | 4 |
| [`docs/ml/experiments_summary.md`](docs/ml/experiments_summary.md) | Synthèse des expériences MLflow | 6 |
| [`docs/02_architecture.md`](docs/02_architecture.md) | Architecture complète, décisions techniques, limites assumées | 10 |
| [`docs/03_installation.md`](docs/03_installation.md) | Guide d'installation | 10 |
| [`docs/04_guide_utilisation.md`](docs/04_guide_utilisation.md) | Guide d'utilisation | 10 |

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
# ou avec l'UI web :
dagster dev -f orchestration_dagster/fraud_dagster/job.py
```
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
| Product Owner | Hassan El Hadi |
| Scrum Master | Yassin Farih |
| Data Engineer | Anass Dabibe (lead), Adnane Dahbi, Seif |
| ML Engineer | Aymane El Badri, Youssef Sarraf |
| Data Analyst | ASSOFI Nada, EL HABTI Oumaima |
