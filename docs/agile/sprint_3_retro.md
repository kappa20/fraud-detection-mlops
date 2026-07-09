# Sprint 3 — Retrospective

## Ce qui a bien fonctionné

- Simuler la CI dans un clone isolé plutôt que de pousser directement et espérer que ça marche a permis de détecter le bug de cache `dlt` (chemin DuckDB résolu par rapport au CWD du premier run) **avant** qu'il ne cause un échec silencieux en production ou en CI réelle. C'est probablement la découverte la plus utile du projet pour la fiabilité à long terme du pipeline.
- Découpler l'API du serveur MLflow (chargement d'un `.pkl` local plutôt qu'un appel réseau) a simplifié la conteneurisation et rendu les tests plus rapides et plus déterministes.
- Concevoir `tests/test_api.py` avec un modèle factice (indépendant du pipeline ML complet) a permis des tests unitaires rapides (<1s) sans sacrifier la couverture du contrat de l'API.

## Ce qui a été difficile

- Le conflit `protobuf` entre `dbt-core` et `mlflow`, déjà repéré en Sprint 2, a persisté sans jamais devenir bloquant — mais reste une dette technique non résolue si le projet devait grandir au-delà du cadre du module.
- Le rapport de dérive (PSI) est peu informatif sur ce dataset précis : 2 jours de données ne permettent pas de démontrer une vraie dérive temporelle. La technique est correcte, mais la donnée disponible limite ce qu'on peut réellement en conclure.

## Actions pour la suite du projet (au-delà du scope du module)

- Isoler l'environnement ML (mlflow, scikit-learn) de l'environnement DataOps (dlt, dbt, dagster) dans deux environnements conda distincts pour éliminer durablement le conflit `protobuf`.
- Ajouter une stratégie de rollback explicite dans le Model Registry (revenir à une version antérieure si le modèle en `Production` dérive).
- Explorer `SMOTE` (déjà dans `requirements.txt`, non utilisé) pour tenter d'améliorer le recall sans dégrader la precision.
