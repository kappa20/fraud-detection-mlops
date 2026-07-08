# Détection de fraude bancaire — Projet MLOps & DataOps

Projet de groupe du module **MLOps & DataOps** (Pr. Mohammed AIT DAOUD, FSBM, Université Hassan II de Casablanca, 2025/2026).

**Sujet :** Détection de fraude bancaire — Classification des transactions frauduleuses (Finance).
**Équipe :** voir [`info.txt`](../info.txt).
**Cahier des charges :** [`PROJETS.pdf`](../PROJETS.pdf).

> Statut actuel du projet : **Phase A (fondations) terminée.** Les sections marquées 🚧 ci-dessous seront complétées au fil des phases suivantes (voir [`docs/agile/product_backlog.md`](docs/agile/product_backlog.md)).

## Architecture cible

```
Sources de données → dlt (ingestion automatisée) → DuckDB (stockage local) → dbt (transformations)
   → Tests Qualité (Data Contract) → Dagster (orchestration)
   → Machine Learning (Scikit-Learn) → Tracking & Registry (MLflow) → Service ML (FastAPI)
   → Conteneurisation (Docker) → CI/CD (GitHub Actions) → Monitoring & Observabilité
```

Détail complet de l'architecture : [`docs/02_architecture.md`](docs/02_architecture.md) 🚧.

## Documentation

| Document | Contenu | Livrable |
|---|---|---|
| [`docs/01_vision.md`](docs/01_vision.md) | Problématique, objectifs, utilisateurs cibles, valeur métier, Data Strategy | 1 |
| [`docs/agile/`](docs/agile/) | Product Backlog, User Stories, Sprint Planning/Review/Retrospective | 2 |
| [`docs/data/data_contract.yaml`](docs/data/data_contract.yaml) 🚧 | Contrat de données (schéma, règles de qualité, consommateurs) | 4 |
| [`docs/data/data_lineage.md`](docs/data/data_lineage.md) 🚧 | Lignage des données, de la source au service exposé | 4 |
| [`docs/ml/experiments_summary.md`](docs/ml/experiments_summary.md) 🚧 | Synthèse des expériences MLflow | 6 |
| [`docs/03_installation.md`](docs/03_installation.md) 🚧 | Guide d'installation | 10 |
| [`docs/04_guide_utilisation.md`](docs/04_guide_utilisation.md) 🚧 | Guide d'utilisation | 10 |

## Structure du dépôt

```
projet/
├── docs/                    # Vision, Agile, Qualité des données, ML, documentation
├── data/raw/                # Dataset source (non versionné, voir data/README.md)
├── ingestion_dlt/           # 🚧 Pipeline d'ingestion dlt → DuckDB
├── dbt_fraud/               # 🚧 Projet dbt (staging + marts + tests)
├── quality/                 # 🚧 Validation shift-left du schéma
├── orchestration_dagster/   # 🚧 Orchestration Dagster du pipeline
├── ml/                      # 🚧 Préparation des données, entraînement, évaluation, MLflow
├── api/                     # 🚧 Service FastAPI (/predict, /health, /metrics)
├── monitoring/              # 🚧 Surveillance et détection de dérive
├── tests/                   # 🚧 Tests automatisés + fixtures pour la CI
├── scripts/                 # 🚧 Scripts utilitaires (génération de fixtures, etc.)
├── Dockerfile               # 🚧 Conteneurisation du service
└── .github/workflows/       # 🚧 CI/CD GitHub Actions
```

## Prérequis — dataset

Le pipeline s'appuie sur le dataset public **"Credit Card Fraud Detection" (ULB)**, à télécharger manuellement depuis Kaggle. Voir [`data/README.md`](data/README.md) pour les instructions exactes.

## Installation

Détaillé dans [`docs/03_installation.md`](docs/03_installation.md) 🚧 (Phase F). En résumé, environnement conda (recommandé, testé) :
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

## Exécuter le pipeline DataOps (Phase B)

```bash
# 1. Placer data/raw/creditcard.csv (voir data/README.md)
# 2. Lancer le pipeline complet via Dagster :
dagster job execute -f orchestration_dagster/fraud_dagster/job.py -a fraud_pipeline_job
# ou avec l'UI web :
dagster dev -f orchestration_dagster/fraud_dagster/job.py
```
Étapes exécutées : ingestion `dlt` (CSV → DuckDB) → validation shift-left → `dbt run` (staging + marts) → `dbt test` (20 tests qualité).

## Équipe et rôles Agile

| Rôle | Membre(s) |
|---|---|
| Product Owner | Hassan El Hadi |
| Scrum Master | Yassin Farih |
| Data Engineer | Anass Dabibe (lead), Adnane Dahbi, Seif |
| ML Engineer | Aymane El Badri, Youssef Sarraf |
| Data Analyst | Étudiante 1, Étudiante 2 *(noms à compléter)* |
