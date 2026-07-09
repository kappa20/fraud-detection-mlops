# Sprint 2 — Retrospective

## Ce qui a bien fonctionné

- Calculer les métriques du rapport de qualité **directement sur DuckDB** (plutôt que de les estimer) a permis de détecter immédiatement que le dataset réel est effectivement propre (0 valeur nulle, 0 doublon) — une vraie vérification, pas une hypothèse.
- Avoir fixé le choix du PR-AUC dès la Vision (Sprint 1) a évité tout débat a posteriori sur l'interprétation des résultats du RandomForest vs la baseline.

## Ce qui a été difficile

- Construire un Data Contract sans gabarit fourni par le cours a demandé de combiner plusieurs notions vues séparément (schéma, métadonnées 3 couches, dimensions de qualité) — plus de travail de synthèse que prévu en planning.
- L'installation de `mlflow` a fait apparaître un conflit de version `protobuf` avec `dbt-core` déjà installé (environnement conda partagé). Vérifié que `dbt build` continue de fonctionner malgré l'avertissement, mais c'est un signal d'alerte pour la suite du projet.

## Actions pour le sprint suivant

- Surveiller le conflit `protobuf` lors de l'ajout de nouvelles dépendances en Sprint 3 (FastAPI, Docker) ; documenter la limite dans `docs/02_architecture.md` plutôt que de la laisser implicite.
- Réutiliser le Data Contract comme référence unique du schéma de features pour l'API du Sprint 3, plutôt que de le redéfinir.
