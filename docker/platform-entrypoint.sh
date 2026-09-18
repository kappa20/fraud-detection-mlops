#!/bin/sh
# Point d'entrée du conteneur platform-api (voir Dockerfile.platform) :
# 1. Autorise git à opérer sur /app, un dépôt bind-monté depuis l'hôte
#    ("dubious ownership" sinon, uid différent entre hôte et conteneur).
# 2. Écrit .dvc/config.local avec les identifiants MinIO et l'endpoint
#    *interne* au réseau docker (http://minio:9000, pas le port public
#    4605) — ATTENTION (documenté dans data/README.md) : comme /app est
#    un bind mount du dépôt hôte, ceci écrase le .dvc/config.local
#    personnel d'un développeur qui lancerait ce service en local ; à
#    régénérer depuis .dvc/config.local.example après coup si besoin.
set -e

git config --global --add safe.directory /app

mkdir -p .dvc
cat > .dvc/config.local <<EOF
['remote "minio_shared"']
    endpointurl = http://minio:9000
    access_key_id = ${MINIO_ROOT_USER:-admin}
    secret_access_key = ${MINIO_ROOT_PASSWORD:-admin12345}
EOF

exec uvicorn platform_api.main:app --host 0.0.0.0 --port 8000
