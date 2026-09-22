# Stack Komodo — services, déploiement continu, MLflow serveur

Ce document décrit ce que `docker-compose.yml` déploie sur Komodo (`exp.s3.fsbm.ma`) et les
opérations manuelles à faire *une fois* côté Komodo / GitHub.

## Services et ports

| Port | Service | Rôle |
|---|---|---|
| 4601 | `api` | Scoring temps réel (FastAPI), `/metrics` Prometheus |
| 4602 | `mlflow` | Serveur MLflow **vivant** : PostgreSQL (`mlflow-db`) + artefacts MinIO (bucket `mlflow`) |
| 4603 | `grafana` | Dashboards « Fraud Detection API » et « Dérive & pipeline » |
| 4604 | `prometheus` | Scrape de `api` et `platform-api`, règles d'alerte (`/alerts`) |
| 4605 / 4606 | `minio` | Stockage objet (remote DVC + artefacts MLflow) : API / console |
| 4607 | `platform-api` | Tableau de bord d'opérations (API + UI React), `/metrics` |
| 4608 | `dagster` | UI Dagster + démon (schedule nocturne, sensor sur le dataset) |
| — | `mlflow-db`, `minio-init` | PostgreSQL de MLflow ; tâche unique qui crée les buckets MinIO |

`minio-init` apparaît « Exited (0) » dans Komodo : c'est normal (tâche unique).

## Orchestration Dagster

- `dagster` et `platform-api` partagent le volume `dagster_home` (`DAGSTER_HOME=/dagster_home`,
  config dans `orchestration_dagster/dagster.yaml`) : les runs lancés depuis le tableau de bord
  apparaissent dans l'UI Dagster.
- **Schedule** `nightly_pipeline_schedule` : `fraud_pipeline_job` chaque nuit à 02:00 (Africa/Casablanca).
- **Sensor** `dataset_version_sensor` : relance `fraud_pipeline_job` quand `data/raw/creditcard.csv.dvc`
  change *hors plateforme* (ex. nouvelle version tirée par `dvc pull`). Une version déjà traitée par un
  run de la plateforme (`dvc_md5` dans `runs.jsonl`) est ignorée, pour ne pas doubler le run.
- Un seul run à la fois : file `max_concurrent_runs: 1` côté démon + verrou de fichier
  (`data/state/pipeline.lock`) entre les étapes, car `platform-api` lance `dagster job execute` en
  dehors de cette file et tous écrivent le même DuckDB.

## Supervision : dérive et alertes

`platform-api` expose `GET /metrics` (public, comme `/health`) : `fraud_drift_psi{feature}`,
`fraud_drift_max_psi`, `fraud_drift_threshold`, `fraud_drift_alert`, `fraud_dataset_rows`,
`fraud_pipeline_last_run_success`, … (voir `platform_api/metrics.py`). Les règles
(`monitoring/prometheus/alerts.yml`, testées par `alerts_test.yml` en CI) :

| Alerte | Condition |
|---|---|
| `FraudDataDriftHigh` (critical) | PSI max ≥ seuil configuré, 1 min |
| `FraudDataDriftModerate` (warning) | 0,10 ≤ PSI max < seuil, 5 min |
| `FraudPipelineLastRunFailed` (critical) | dernier run terminé en échec |
| `FraudPipelineStale` (warning) | aucun run depuis 3 jours |
| `FraudApiDown` / `FraudPlatformDown` / `FraudDriftUnavailable` | disponibilité |

Il n'y a pas d'Alertmanager : les alertes se consultent dans Prometheus (`:4604/alerts`) et dans le
panneau « Alertes en cours » du dashboard Grafana « Dérive & pipeline ».

## MLflow : du snapshot SQLite au serveur vivant

Avant : `mlflow` servait en lecture seule un `mlflow_snapshot/mlflow.db` commité dans git (SQLite,
version du serveur ≠ version du client → dérives de schéma). Maintenant : serveur MLflow
`2.22.5` (même version que `requirements.txt`), backend PostgreSQL, artefacts dans MinIO via le proxy
d'artefacts (`--serve-artifacts`). `train.py`, `register_model.py` et `platform-api` y accèdent avec
`MLFLOW_TRACKING_URI=http://mlflow:5000` ; sans cette variable, le mode local SQLite est inchangé
(tests, développement). Avec un serveur vivant, `publish_mlflow_snapshot()` est ignoré.

**Le registry est neuf.** Les versions v1/v2 de l'ancien snapshot ne sont pas migrées. Lancé depuis le tableau de
bord, le premier ré-entraînement enregistre une v1 **en Staging** : la plateforme tourne avec la promotion automatique
désactivée (`auto_promote: false`), un humain doit approuver (Pipeline → « Approuver »). Seul un lancement direct de
`ml/register_model.py` sans `--no-promote` promeut automatiquement le premier candidat quand il n'y a pas de
Production. À l'approbation, `model.pkl` est réécrit, puis `fraud-api` est redémarré via Komodo (si `KOMODO_*` est défini
sur `platform-api`) — sinon redémarrer le service `api` à la main.

## Déploiement continu gardé par la CI

Le webhook GitHub → Komodo déploie à chaque push, même quand la CI est rouge. Le job `deploy` de
`.github/workflows/ci.yml` (`needs: test`, push sur `main` uniquement) appelle
`scripts/komodo_deploy.py` : `DeployStack` via l'API Komodo, attente du statut de l'update, puis test
de santé optionnel.

À faire une fois :

1. **GitHub → Settings → Secrets and variables → Actions** — secrets `KOMODO_URL`
   (`https://komodo.s3.fsbm.ma`), `KOMODO_API_KEY`, `KOMODO_API_SECRET`, `KOMODO_STACK` (nom de la stack) ;
   variable optionnelle `DEPLOY_HEALTH_URL` (ex. `http://exp.s3.fsbm.ma:4607/health`).
2. **Supprimer le webhook** GitHub existant (Settings → Webhooks, URL `…/listener/github/stack/<id>/deploy`)
   ou désactiver « Webhook enabled » dans la config de la stack Komodo. Sans cela, le déploiement non gardé
   continue de partir en parallèle.
3. **Environment de la stack Komodo** : `MLFLOW_DB_PASSWORD` (défaut `mlflow`, à surcharger) ; les
   identifiants MinIO/Grafana par défaut restent à changer.

Si les secrets sont absents (fork, premier push), le job affiche un avertissement et se termine sans échec.

### Panne connue : `.git/rebase-merge` bloqué sur le serveur

Si le job `deploy` échoue avec `fatal: It seems that there is already a rebase-merge directory` (le
`git pull` que Komodo lance côté serveur avant le build), **rejouer ne sert à rien** : ce n'est pas un
incident réseau transitoire, c'est un rebase resté ouvert dans le checkout de la stack sur `vh3` — il ne
se résorbe pas tout seul, `scripts/komodo_deploy.py` échoue donc immédiatement sur cette erreur au lieu
de gaspiller 3 tentatives (voir `GitLockError`/`GIT_REBASE_LOCK_MARKER`).

Cause la plus probable : le webhook GitHub (étape 2 ci-dessus) est toujours actif en plus du job CI —
deux `DeployStack` concurrents tirent sur le même checkout et interrompent le `git pull` de l'un des deux
en plein rebase. Vérifier d'abord que le webhook a bien été supprimé/désactivé.

Correctif : se connecter au serveur Komodo (ou au conteneur qui a accès au checkout de la stack) et
lancer `git rebase --abort` — ou, à défaut, supprimer le répertoire `.git/rebase-merge` — dans le
répertoire de la stack, puis relancer le déploiement.
