# Sprint 1 — Review

**Sprint Goal rappelé :** *"Disposer d'une vision partagée du projet, d'un backlog priorisé, et d'un pipeline DataOps minimal (dlt → DuckDB → dbt → Dagster) exécutable de bout en bout sur le dataset de transactions."*

## Démonstration réalisée

- `docs/01_vision.md` et `docs/agile/product_backlog.md` présentés et validés.
- Pipeline exécuté en direct via `dagster job execute -f orchestration_dagster/fraud_dagster/job.py -a fraud_pipeline_job` :
  - Ingestion `dlt` : **284 807 lignes** chargées dans `raw.transactions_raw` (492 fraudes, 0,17 %).
  - Validation shift-left : schéma et qualité minimale OK.
  - `dbt run` : 4 modèles construits (`stg_transactions`, `fct_transactions_clean`, `fct_transactions_features`, `agg_fraud_hourly_summary`).
  - `dbt test` : tests initiaux passants.
  - Run Dagster : `RUN_SUCCESS`.

## User Stories livrées

US-01, US-02, US-03, US-04, US-05, US-06, US-07 (toutes les stories planifiées pour ce sprint — voir `product_backlog.md`).

## Feedback (simulé — professeur / relecture croisée de l'équipe)

- Positif : la reprise du pattern déjà validé dans le TP Chapitre 2 (ingest → validate → transform → test) a permis d'aller vite sans réinventer l'architecture.
- Point d'attention soulevé : s'assurer que `dlt` normalise les noms de colonnes (`Time` → `time`) est bien documenté, sous peine de confusion pour la suite du pipeline (ML, API).

## Incrément livré

Un pipeline DataOps fonctionnel de bout en bout sur les données réelles, versionné sur Git (commits `2bc264b`, `902a3ab`).
