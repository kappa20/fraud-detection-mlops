#!/bin/sh
# Point d'entrée du conteneur `dagster` (même image que platform-api, voir
# Dockerfile.platform) : UI Dagster + démon (schedule nocturne, sensor sur le
# dataset) sur le dépôt bind-monté dans /app.
#
# Lancé via `sh /app/docker/dagster-entrypoint.sh` (docker-compose.yml) : le
# script vit dans le dépôt monté, pas dans l'image, donc une modification
# n'exige pas de reconstruire l'image.
set -e

# git opère sur /app (bind mount, uid différent) : ml/register_model.py committe
# model.pkl/model_version.txt quand un modèle est promu.
git config --global --add safe.directory /app

# Instance Dagster partagée avec platform-api (volume `dagster_home`).
mkdir -p "$DAGSTER_HOME"
cp /app/orchestration_dagster/dagster.yaml "$DAGSTER_HOME/dagster.yaml"

exec dagster dev -h 0.0.0.0 -p 3000 -f orchestration_dagster/fraud_dagster/job.py
