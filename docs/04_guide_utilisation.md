# Livrable 10 — Guide d'utilisation

Suppose l'installation terminée (voir [`03_installation.md`](03_installation.md)).

## 1. Lancer le pipeline DataOps

```bash
dagster job execute -f orchestration_dagster/fraud_dagster/job.py -a fraud_pipeline_job
```
Enchaîne automatiquement : ingestion `dlt` → validation shift-left → `dbt run` → `dbt test`.

Pour explorer visuellement le pipeline (UI web) :
```bash
dagster dev -f orchestration_dagster/fraud_dagster/job.py
# puis ouvrir http://localhost:3000
```

Pour ré-exécuter seulement une étape (debug) :
```bash
python ingestion_dlt/run_pipeline.py
python quality/validate_schema.py
cd dbt_fraud && dbt run --profiles-dir . && dbt test --profiles-dir .
```

## 2. Explorer les données transformées

```bash
python -c "
import duckdb
con = duckdb.connect('fraud_detection.duckdb', read_only=True)
print(con.execute('SELECT * FROM main.agg_fraud_hourly_summary ORDER BY hour_of_day').fetchdf())
"
```

## 3. Entraîner et comparer les modèles

```bash
python ml/train.py
```
Logue deux runs dans MLflow (`logreg_baseline`, `rf_balanced_v1`). Pour explorer les résultats :
```bash
mlflow ui --backend-store-uri sqlite:///mlflow.db
# puis ouvrir http://localhost:5000
```
Détails et résultats de référence : [`ml/experiments_summary.md`](ml/experiments_summary.md).

## 4. Enregistrer le meilleur modèle

```bash
python ml/register_model.py
```
Sélectionne automatiquement le run avec le meilleur PR-AUC, l'enregistre dans le Model Registry (`fraud-detection-classifier`, stage `Production`), et exporte `ml/artifacts/model.pkl` pour le service.

## 5. Lancer le service de scoring

En local :
```bash
uvicorn api.main:app --reload
```

En conteneur :
```bash
docker build -t fraud-api .
docker run -p 8000:8000 fraud-api
# ou :
docker compose up --build
```

### Appeler l'API

```bash
curl http://localhost:8000/health

curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{
    "time": 0, "amount": 149.62,
    "v1": -1.36, "v2": -0.07, "v3": 2.54, "v4": 1.38, "v5": -0.34,
    "v6": 0.46, "v7": 0.24, "v8": 0.10, "v9": 0.36, "v10": 0.09,
    "v11": -0.55, "v12": -0.62, "v13": -0.99, "v14": -0.31, "v15": 1.47,
    "v16": -0.47, "v17": 0.21, "v18": 0.03, "v19": 0.40, "v20": 0.25,
    "v21": -0.02, "v22": 0.28, "v23": -0.11, "v24": 0.07, "v25": 0.13,
    "v26": -0.19, "v27": 0.13, "v28": -0.02
  }'
```
Réponse attendue (valeurs vérifiées avec le modèle `rf_balanced_v1` enregistré) :
```json
{"fraud_probability": 0.006241, "is_fraud": false, "threshold": 0.4998, "model_version": "fraud-detection-classifier v1 (...)"}
```

Documentation interactive (Swagger) : `http://localhost:8000/docs`.

## 6. Surveiller le service

```bash
curl http://localhost:8000/metrics   # métriques Prometheus (disponibilité, latence, compteurs de requêtes)
python monitoring/drift_check.py     # rapport de dérive (PSI) -> monitoring/drift_report.md
```
Chaque appel à `/predict` est journalisé dans `monitoring/predictions_log.jsonl`, réutilisé par `drift_check.py` dès qu'assez de trafic a été observé.

## 7. Lancer les tests et le lint

```bash
ruff check .
pytest tests/ -v
```
Ces tests n'ont besoin ni du dataset réel ni d'un modèle entraîné (fixture synthétique + modèle scikit-learn factice) — voir `tests/`.

## 8. Reproduire la CI localement

```bash
python scripts/make_sample_fixture.py
python ingestion_dlt/run_pipeline.py --csv tests/fixtures/sample_transactions.csv --duckdb /tmp/ci_test.duckdb
python quality/validate_schema.py --duckdb /tmp/ci_test.duckdb
```
*(Utiliser un chemin DuckDB différent de celui du dataset réel pour ne pas écraser vos résultats — voir `.github/workflows/ci.yml` pour le déroulé complet exécuté à chaque push.)*
