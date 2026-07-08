# Livrable 4 — Rapport de qualité des données

**Portée :** tables `stg_transactions`, `fct_transactions_clean`, `fct_transactions_features`, `agg_fraud_hourly_summary` (DuckDB, base `fraud_detection.duckdb`).
**Date du run de référence :** ingestion dlt du 08/07/2026 (`load_id` unique, 1 run à ce stade du projet).
**Méthode :** application des **11 dimensions de qualité** présentées au Chapitre 3 du cours (Atwal 2019 ; Wang & Strong 1996) au dataset réellement ingéré — chiffres calculés directement sur `fraud_detection.duckdb`, pas des estimations.

> Rappel du cours : *"Disponibilité ≠ fiabilité."* Ce rapport vérifie que les données sont non seulement chargées, mais fiables au sens du Chapitre 3 (complètes, valides, exactes, opportunes, cohérentes).

## Résultats par dimension

| # | Dimension | Vérification appliquée | Résultat mesuré | Statut |
|---|---|---|---|---|
| 1 | **Complétude** | Nullité sur `amount`, `is_fraud`, `time_seconds` | 0 valeur nulle sur 284 807 lignes | ✅ |
| 2 | **Validité** | `is_fraud ∈ {0,1}` ; `amount ≥ 0` ; `hour_of_day ∈ [0,23]` ; `amount_bucket` dans les valeurs autorisées | 100 % conforme (0 violation détectée sur les 4 règles) | ✅ |
| 3 | **Cohérence** | Pas de contradiction logique attendue entre colonnes dérivées (`log_amount` cohérent avec `amount`) | `log_amount = ln(amount+1)` recalculable et vérifié `≥ 0` par test dbt | ✅ |
| 4 | **Cohérence métier** | `amount` ne doit jamais être négatif (règle métier : un montant de transaction ne peut pas être négatif) | 0 ligne avec `amount < 0` (test singulier dbt `assert_amount_non_negative`) | ✅ |
| 5 | **Unicité** | `transaction_id` ne doit contenir aucun doublon | 284 807 lignes, 284 807 `transaction_id` distincts | ✅ |
| 6 | **Exactitude** | Distance à la réalité observée | Non vérifiable indépendamment : `amount`/`is_fraud` sont fournis tels quels par la source (ULB), sans second système de référence pour recouper — limite assumée, cf. section "Limites" | ⚠️ |
| 7 | **Fraîcheur** | Délai entre disponibilité de la donnée et son usage | Non applicable au sens SLA temps réel : dataset historique statique (transactions de septembre 2013), pas de flux continu — voir `docs/data/data_contract.yaml`, section `sla` | N/A (documenté) |
| 8 | **Intégrité** | Relations référentielles entre tables | Non applicable : schéma en étoile à une seule table de faits (pas de table dimension externe type `clients`/`commandes` à relier) — honnêtement documenté plutôt que simulé artificiellement | N/A (documenté) |
| 9 | **Traçabilité** | Capacité à relier chaque ligne à son run d'ingestion | Colonne `load_id` (`_dlt_load_id` dlt) présente et propagée jusqu'aux marts sur 100 % des lignes | ✅ |
| 10 | **Uniformité** | Représentation homogène (formats de date, unités) dans tout le système | `time_seconds` en secondes (int) partout, `amount` en unité monétaire unique (pas de devise multiple dans ce dataset) | ✅ |
| 11 | **Documentation / Métadonnées** | Chaque colonne exposée est décrite | 100 % des colonnes des modèles dbt documentées dans `schema.yml` (voir `dbt_fraud/models/**/*.yml`) et dans `docs/data/data_contract.yaml` | ✅ |

**Score global : 8/11 dimensions pleinement vérifiées automatiquement, 1 documentée comme non vérifiable (exactitude), 2 documentées comme non applicables à ce dataset (fraîcheur, intégrité).**

## Statistiques descriptives (calculées sur le run de référence)

| Métrique | Valeur |
|---|---|
| Nombre total de transactions | 284 807 |
| Transactions frauduleuses (`is_fraud = 1`) | 492 (**0,1727 %**) |
| Montant minimum / maximum | 0,00 / 25 691,16 |
| Période couverte (`time_seconds`) | 0 à 172 792 s (~2 jours) |
| Répartition `amount_bucket` | medium: 130 108 · low: 95 489 · high: 54 316 · very_high: 3 069 · zero: 1 825 |
| Runs d'ingestion (`load_id` distincts) | 1 |

## Tests automatisés associés (Chapitre 3 : Schéma / Contenu / Métier)

| Famille (cours) | Tests dbt implémentés | Nombre |
|---|---|---|
| Tests de Schéma | Colonnes requises vérifiées à l'ingestion (`quality/validate_schema.py`) | 1 script |
| Tests de Contenu | `not_null`, `unique`, `accepted_values`, `accepted_range` (macro custom) | 26 tests dbt |
| Tests Métier | `assert_amount_non_negative` (test singulier) | 1 test dbt |

**Total : 27 tests dbt, tous PASS** (voir `dbt build --profiles-dir .` dans `dbt_fraud/`).

> Règle d'or citée en cours : *"Les tests de données doivent être versionnés et exécutés exactement comme les tests unitaires en génie logiciel."* — tous les tests ci-dessus sont versionnés dans Git et ré-exécutés à chaque run du job Dagster (`orchestration_dagster/fraud_dagster/job.py`, étape `test_data`) et dans la CI/CD (Phase E).

## Limites assumées

- **Exactitude non vérifiable indépendamment** : le dataset ULB ne fournit pas de source de vérité tierce pour recouper `amount`/`is_fraud`. On fait confiance à la réputation académique de la source (référencée dans de nombreuses publications).
- **Colonnes `v1`-`v28` non testables sur des règles métier** : étant des composantes PCA anonymisées, seules des vérifications génériques (type, nullité) leur sont applicables — aucune règle de domaine métier n'a de sens sur ces colonnes, ce qui est documenté plutôt que masqué.
- **Un seul run d'ingestion à ce stade** : les dimensions Fraîcheur/dérive ne peuvent être pleinement démontrées qu'avec plusieurs runs dans le temps — traité en Phase F (monitoring, dérive simple).
