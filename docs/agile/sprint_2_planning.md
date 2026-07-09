# Sprint 2 — Planning

**Durée :** 2 semaines
**Objectif de sprint (Sprint Goal) :** *"Formaliser la qualité et la confiance dans les données (Data Contract, lineage, tests étendus) et livrer un modèle de détection de fraude entraîné, évalué et tracé dans MLflow."*

## Contexte

Ce sprint correspond aux Phases C et D du plan d'implémentation. Il applique directement les enseignements du Chapitre 3 (qualité des données, "la fiabilité se construit à chaque étape, se mesure en continu et se prouve par des tests") et du Chapitre 1 (traçabilité par les "5 Q") au pipeline construit au Sprint 1.

## User Stories sélectionnées (voir `product_backlog.md`)

| ID | User Story (résumé) | Points | Assigné |
|---|---|---|---|
| US-08 | Data Contract | 3 | Seif |
| US-09 | Data Lineage | 3 | Étudiante 1 (Data Analyst) |
| US-10 | Tests dbt étendus (schéma/contenu/métier) | 3 | Anass Dabibe |
| US-11 | Préparation des données (split stratifié) | 3 | Aymane El Badri |
| US-12 | Entraînement + comparaison de modèles (MLflow) | 8 | Aymane El Badri |
| US-13 | Model Registry (Staging → Production) | 3 | Youssef Sarraf |

**Capacité du sprint :** 23 points.

## Risques identifiés en planning

- **Absence de gabarit de Data Contract dans le cours** : l'équipe devra concevoir sa propre structure en s'appuyant sur les dimensions de qualité et les métadonnées du Chapitre 3 — mitigation : s'appuyer sur le schéma dbt déjà existant plutôt que de repartir de zéro.
- **Déséquilibre extrême des classes** (0,17 % de fraude) : risque de métriques trompeuses si l'équipe se fie à l'accuracy — mitigation : figer le choix du PR-AUC comme métrique de décision dès `docs/01_vision.md` (déjà fait au Sprint 1).

## Definition of Ready

- Pipeline DataOps du Sprint 1 exécutable sans erreur.
- Tables `fct_transactions_clean` et `fct_transactions_features` disponibles dans DuckDB.
