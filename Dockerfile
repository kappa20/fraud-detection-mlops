# Service de scoring de fraude — image légère, sans dlt/dbt/dagster/mlflow
# (inutiles à l'inférence). Le modèle est chargé depuis un .pkl exporté par
# ml/register_model.py, pas depuis un serveur MLflow vivant.
FROM python:3.11-slim

WORKDIR /app

COPY requirements-api.txt .
RUN pip install --no-cache-dir -r requirements-api.txt

COPY api/ api/
COPY ml/artifacts/model.pkl ml/artifacts/model.pkl
COPY ml/artifacts/model_version.txt ml/artifacts/model_version.txt

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
