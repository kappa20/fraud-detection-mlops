# Rapport final — Détection de fraude bancaire

**Module :** MLOps & DataOps — Pr. Mohammed AIT DAOUD, FSBM, Université Hassan II de Casablanca, 2025/2026
**Projet n°3 du catalogue :** Détection de fraude bancaire — Classification des transactions frauduleuses (Finance)
**Équipe :** voir [`info.txt`](info.txt)

Ce document synthétise le projet pour la présentation finale (Livrable 7 : rapport + oral 15 min, dont 10 min de démonstration et 5 min de questions). Chaque section renvoie vers le document détaillé correspondant plutôt que de le dupliquer.

## 1. Problématique et objectifs

Voir [`docs/01_vision.md`](docs/01_vision.md) pour le détail complet (problématique, utilisateurs cibles, valeur métier, Data Strategy).

**En résumé :** détecter des transactions frauduleuses parmi un flux massif de transactions légitimes (0,17 % de fraude dans le dataset de référence), en construisant non pas seulement un modèle, mais un **système** data/ML complet, reproductible, traçable, testé et déployé — conformément au cadre DataOps/MLOps du cours (Atwal 2019, DataOps Manifesto, cycle de vie en 8 étapes du Chapitre 1).

## 2. Organisation Agile

- **Rôles** : Product Owner (Hassan El Hadi), Scrum Master (Yassin Farih), Data Engineers (Anass Dabibe — lead, Adnane Dahbi, Seif), ML Engineers (Aymane El Badri, Youssef Sarraf), Data Analysts (ASSOFI Nada, EL HABTI Oumaima).
- **3 sprints** réalisés (minimum imposé par le cahier des charges), chacun avec Planning / Review / Retrospective : voir [`docs/agile/`](docs/agile/).
  - Sprint 1 : fondations + pipeline DataOps (dlt/DuckDB/dbt/Dagster).
  - Sprint 2 : qualité des données (Data Contract, lineage) + Machine Learning/MLflow.
  - Sprint 3 : déploiement (FastAPI/Docker), CI/CD, monitoring.
- **Product Backlog** : 20 user stories couvrant les 10 livrables — voir [`docs/agile/product_backlog.md`](docs/agile/product_backlog.md).

## 3. Architecture livrée

```
Sources de données → dlt (ingestion automatisée) → DuckDB (stockage local) → dbt (transformations)
   → Tests Qualité (Data Contract) → Dagster (orchestration)
   → Machine Learning (Scikit-Learn) → Tracking & Registry (MLflow) → Service ML (FastAPI)
   → Conteneurisation (Docker) → CI/CD (GitHub Actions) → Monitoring & Observabilité
```

Détail complet : [`docs/02_architecture.md`](docs/02_architecture.md). Lignage bout en bout : [`docs/data/data_lineage.md`](docs/data/data_lineage.md).

## 4. Résultats clés (vérifiés, pas estimés)

| Indicateur                                              | Valeur                                                                                                                          |
| ------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| Transactions ingérées (`dlt` → DuckDB)             | 284 807                                                                                                                         |
| Fraudes                                                 | 492 (0,1727 %)                                                                                                                  |
| Tests qualité dbt                                      | **27/27 PASS** (schéma, contenu, métier)                                                                                |
| Modèle retenu                                          | RandomForest (`class_weight="balanced_subsample"`)                                                                            |
| PR-AUC (modèle retenu / baseline)                      | **0,8444** / 0,7200                                                                                                       |
| Recall / Precision (seuil optimal)                      | 0,8163 / 0,8421                                                                                                                 |
| Fraudes détectées sur le jeu de test                  | 80 / 98                                                                                                                         |
| Tests unitaires (API, validation, métriques)           | **12/12 PASS**                                                                                                            |
| Endpoints API                                           | `GET /health`, `POST /predict`, `GET /metrics` — tous testés en local et en conteneur Docker                            |
| CI/CD                                                   | Pipeline complet (lint → tests → ingestion → qualité → dbt → ML → registry → build Docker) validé dans un clone isolé |
| Dérive (PSI,`amount`/`log_amount`/`hour_of_day`) | < 0,01 — pas de dérive significative sur la période couverte (~2 jours)                                                      |

Détails : [`docs/data/data_quality_report.md`](docs/data/data_quality_report.md), [`docs/ml/experiments_summary.md`](docs/ml/experiments_summary.md).

## 5. Mapping des 10 livrables du cahier des charges

| #  | Livrable                                       | Statut | Où                                                                                                       |
| -- | ---------------------------------------------- | ------ | --------------------------------------------------------------------------------------------------------- |
| 1  | Vision du projet                               | ✅     | `docs/01_vision.md`                                                                                     |
| 2  | Gestion Agile (3 sprints)                      | ✅     | `docs/agile/`                                                                                           |
| 3  | Pipeline DataOps (dlt/DuckDB/dbt/Dagster)      | ✅     | `ingestion_dlt/`, `dbt_fraud/`, `orchestration_dagster/`                                            |
| 4  | Qualité des données (Data Contract, Lineage) | ✅     | `docs/data/`                                                                                            |
| 5  | Machine Learning                               | ✅     | `ml/prepare_data.py`, `ml/train.py`, `ml/evaluate.py`                                               |
| 6  | MLflow (Tracking + Registry)                   | ✅     | `ml/register_model.py`, `docs/ml/experiments_summary.md`                                              |
| 7  | Déploiement (FastAPI + Docker)                | ✅     | `api/`, `Dockerfile`                                                                                  |
| 8  | CI/CD                                          | ✅     | `.github/workflows/ci.yml`                                                                              |
| 9  | Monitoring                                     | ✅     | `monitoring/`, `GET /metrics`                                                                         |
| 10 | Documentation                                  | ✅     | `README.md`, `docs/02_architecture.md`, `docs/03_installation.md`, `docs/04_guide_utilisation.md` |

## 6. Un exemple concret d'ingénierie MLOps rencontré pendant le projet

En validant la CI/CD dans un clone Git isolé (plutôt que de compter sur GitHub Actions pour découvrir les problèmes), l'équipe a détecté un vrai bug de reproductibilité : `dlt` mémorise localement (`~/.dlt/pipelines/<nom>/`) le répertoire de travail du **premier** run et résout les chemins relatifs des runs suivants par rapport à celui-ci — même depuis un autre répertoire ou une autre machine. Une ingestion relancée en CI aurait donc pu écrire silencieusement dans le mauvais fichier. Corrigé en résolvant systématiquement le chemin de destination en chemin absolu (commit `795c5c4`), puis revérifié avec succès. C'est une illustration directe du principe du Chapitre 2 : *"Ça marche sur mon laptop, ça marche pas sur mon serveur — l'absence d'environnement maîtrisé est la première cause d'irreproductibilité dans les projets data/ML."*

## 7. Limites assumées et perspectives

- **Colonnes anonymisées (V1-V28)** : aucune règle métier n'a pu leur être appliquée (composantes PCA opaques) — documenté honnêtement plutôt que masqué (`docs/data/data_quality_report.md`).
- **Dimensions Fraîcheur et Intégrité non applicables** : dataset historique statique, schéma à une seule table de faits.
- **PSI peu discriminant** sur seulement ~2 jours de données couvertes par le dataset — la technique est correcte mais la donnée disponible limite ce qu'on peut en conclure en conditions réelles.
- **Conflit de versions `protobuf`** entre `dbt-core` et `mlflow` dans l'environnement partagé — sans impact observé, mais dette technique documentée (`docs/02_architecture.md`).
- **Pistes non implémentées** (hors scope du module, documentées comme perspectives) : SMOTE pour le rééquilibrage, split temporel pour l'entraînement, séparation des environnements DataOps/ML, gestion des secrets, environnements dev/staging/prod distincts.

## 8. Plan de démonstration orale (10 minutes)

1. **Vision et architecture** (1 min) — `docs/01_vision.md`, diagramme d'architecture.
2. **Pipeline DataOps en direct** (2 min) — `dagster job execute -f orchestration_dagster/fraud_dagster/job.py -a fraud_pipeline_job` (ou UI `dagster dev`).
3. **Qualité des données** (1 min) — `dbt test` (27 tests), aperçu de `data_contract.yaml`.
4. **MLflow** (2 min) — `mlflow ui`, comparaison des runs, Model Registry (Staging → Production).
5. **API en conteneur** (2 min) — `docker run`, `curl /health`, `curl /predict` avec une vraie transaction du dataset.
6. **Monitoring** (1 min) — `GET /metrics`, `python monitoring/drift_check.py`.
7. **CI/CD** (1 min) — montrer le run GitHub Actions vert sur le dépôt distant.
