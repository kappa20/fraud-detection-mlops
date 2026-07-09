# Sprint 3 — Review

**Sprint Goal rappelé :** *"Le modèle est exposé via une API conteneurisée, testée en continu par la CI/CD, et supervisée en production (monitoring, dérive)."*

## Démonstration réalisée

- Service FastAPI lancé (`uvicorn api.main:app`) : `GET /health` → `{"status":"ok","model_loaded":true,...}`, `POST /predict` → probabilité de fraude cohérente (ex. 0,62 % sur une transaction légitime réelle du dataset), `GET /metrics` expose les métriques Prometheus.
- Image Docker construite et testée : `docker build` + `docker run` → mêmes réponses `/health` et `/predict` qu'en local.
- **CI validée dans un clone Git isolé** (pas sur le dépôt de travail, pour ne pas écraser les résultats MLflow/DuckDB déjà obtenus) : lint → tests unitaires (12/12) → génération de la fixture synthétique → ingestion `dlt` → validation → `dbt build` (27/27) → entraînement → enregistrement du modèle → `docker build`, **tout est passé**.
- **Bug de reproductibilité découvert et corrigé pendant cette validation** : `dlt` mémorise localement (`~/.dlt/pipelines/<nom>/`) le répertoire de travail du premier run et l'utilise pour résoudre les chemins relatifs des runs suivants — un comportement qui aurait pu faire échouer silencieusement la CI (ou pire, écrire dans le mauvais fichier sans erreur visible). Corrigé en résolvant systématiquement le chemin DuckDB en absolu (commit `795c5c4`), puis re-vérifié avec succès.
- `python monitoring/drift_check.py` exécuté sur les données réelles : PSI < 0,01 sur `amount`, `log_amount`, `hour_of_day` entre les deux moitiés temporelles du dataset — cohérent avec un dataset ne couvrant que ~2 jours (peu de dérive attendue à cette échelle de temps).

## User Stories livrées

US-14, US-15, US-16, US-17, US-18, US-19, US-20.

## Feedback (simulé)

- Positif : tester la CI dans un clone isolé avant de compter sur GitHub Actions a permis de trouver un vrai bug avant qu'il ne bloque une Pull Request — exactement l'esprit du principe "shift left" du Chapitre 3, appliqué ici à l'infrastructure plutôt qu'aux données.
- Point d'attention : le PSI quasi nul s'explique par la faible couverture temporelle du dataset (2 jours) — à mentionner explicitement dans le rapport final pour ne pas laisser croire que le modèle est à l'abri de toute dérive en production réelle.

## Incrément livré

Service de scoring conteneurisé, testé automatiquement à chaque push, et supervisé (disponibilité, latence, dérive), versionné sur Git (commits `cfa6eda`, `795c5c4`).
