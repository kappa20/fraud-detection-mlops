# Livrable 10 — Guide d'installation

## Prérequis

- Python 3.11
- conda (recommandé, testé) ou `venv`
- Docker (pour la conteneurisation, Livrable 7)
- Un compte Kaggle (pour télécharger le dataset)

## 1. Cloner le dépôt

```bash
git clone <url-du-depot>
cd projet
```

## 2. Créer l'environnement Python

Avec conda (recommandé — c'est l'environnement effectivement testé pour ce projet) :
```bash
conda create -n mlops_fraud python=3.11
conda activate mlops_fraud
pip install -r requirements.txt
```

Avec `venv` :
```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 3. Télécharger le dataset

Le pipeline a besoin du fichier `creditcard.csv` (dataset Kaggle "Credit Card Fraud Detection", ULB), **non fourni dans ce dépôt** (licence non redistribuable). Voir [`../data/README.md`](../data/README.md) pour les instructions complètes. En résumé :

1. Télécharger le dataset depuis Kaggle.
2. Placer le fichier à : `data/raw/creditcard.csv`.

## 4. Vérifier l'installation

```bash
python -c "import dlt, duckdb, dagster, mlflow, sklearn, fastapi; print('OK')"
ruff check .
pytest tests/ -v   # ne nécessite pas le dataset réel (fixture synthétique + modèle factice)
```

## 5. Exécuter le pipeline complet (ordre recommandé)

```bash
# a. Pipeline DataOps (ingestion -> validation -> transformation -> tests)
dagster job execute -f orchestration_dagster/fraud_dagster/job.py -a fraud_pipeline_job

# b. Entraînement et enregistrement du modèle
python ml/train.py
python ml/register_model.py

# c. Lancer le service d'inférence
uvicorn api.main:app --reload
# ou en conteneur :
docker build -t fraud-api .
docker run -p 8000:8000 fraud-api

# d. Vérifier la dérive (à exécuter périodiquement en production)
python monitoring/drift_check.py
```

Détails de chaque étape : [`04_guide_utilisation.md`](04_guide_utilisation.md).

## Dépannage

| Problème | Cause probable | Solution |
|---|---|---|
| `FileNotFoundError` sur `creditcard.csv` | Dataset non téléchargé/mal placé | Voir étape 3 ci-dessus |
| L'ingestion `dlt` écrit dans le mauvais fichier DuckDB | Ancien bug connu et corrigé (commit `795c5c4`) : `dlt` mémorise le CWD du premier run dans `~/.dlt/pipelines/` | Mettre à jour vers la dernière version de `ingestion_dlt/run_pipeline.py` (résout toujours le chemin en absolu) |
| `dbt build` échoue avec "table not found" | Le pipeline dlt n'a pas encore été exécuté | Lancer l'étape (a) ci-dessus avant `dbt build` |
| `GET /health` renvoie `model_loaded: false` | Le modèle n'a pas encore été entraîné/enregistré | Lancer l'étape (b) ci-dessus |
| Avertissement pip sur `protobuf` (conflit `dbt-core`/`mlflow`) | Environnement partagé, voir `docs/02_architecture.md` | Sans impact observé sur le fonctionnement (vérifié) ; ignorer ou isoler dans deux environnements si le conflit devient bloquant |
