# Sprint 2 — Review

**Sprint Goal rappelé :** *"Formaliser la qualité et la confiance dans les données (Data Contract, lineage, tests étendus) et livrer un modèle de détection de fraude entraîné, évalué et tracé dans MLflow."*

## Démonstration réalisée

- `docs/data/data_contract.yaml`, `docs/data/data_lineage.md` (diagramme mermaid), `docs/data/data_quality_report.md` présentés, avec des chiffres calculés sur les données réellement ingérées (0 valeur nulle, 0 doublon, 0 montant négatif, 284 807 transactions distinctes).
- `dbt build` : **27/27 tests** passants (schéma, contenu, métier — Chapitre 3), incluant un test générique `accepted_range` écrit à la main.
- `python ml/train.py` exécuté en direct :
  - `logreg_baseline` : PR-AUC 0,7200
  - `rf_balanced_v1` : **PR-AUC 0,8444** (retenu)
  - Observation partagée avec l'équipe : le seuil optimal (F1) de la régression logistique est quasi égal à 1 (0,999999...), signe de fragilité — argument supplémentaire en faveur du RandomForest.
- `python ml/register_model.py` : modèle `fraud-detection-classifier` v1 enregistré, transition Staging → Production démontrée dans MLflow UI.

## User Stories livrées

US-08, US-09, US-10, US-11, US-12, US-13.

## Feedback (simulé)

- Positif : documenter honnêtement les limites (dimensions Fraîcheur/Intégrité non applicables, colonnes PCA non enrichies artificiellement) renforce la crédibilité scientifique du rapport plutôt que de la fragiliser.
- Point d'attention : le split stratifié aléatoire n'est pas la façon la plus réaliste de simuler un déploiement en production (un split temporel serait plus proche de la réalité) — noté comme piste d'amélioration, pas bloquant pour ce module.

## Incrément livré

Qualité des données formalisée et modèle de fraude entraîné, tracé et enregistré, versionnés sur Git (commits `bc71fee`, `05c08bb`).
