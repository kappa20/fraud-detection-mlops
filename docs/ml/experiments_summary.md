# Livrable 6 — Synthèse des expériences MLflow

**Experiment MLflow :** `fraud_detection` (`sqlite:///mlflow.db`)
**Jeu de données :** `fct_transactions_features` (dbt), split stratifié 80/20 sur `is_fraud` (`ml/prepare_data.py`)
**Train / Test :** 227 845 / 56 962 lignes (ratio de fraude préservé : 0,1727 %)

## Modèles comparés

| Run | Modèle | PR-AUC | ROC-AUC | Precision | Recall | F1 | Seuil retenu |
|---|---|---|---|---|---|---|---|
| `logreg_baseline` | `LogisticRegression(class_weight="balanced")` | 0,7200 | 0,9717 | 0,8247 | 0,8163 | 0,8205 | 0,99999… |
| `rf_balanced_v1` | `RandomForestClassifier(class_weight="balanced_subsample", n_estimators=200, max_depth=12)` | **0,8444** | 0,9761 | 0,8421 | 0,8163 | 0,8290 | 0,4998 |

**Modèle retenu : `rf_balanced_v1`** (meilleur PR-AUC, métrique primaire pour ce jeu déséquilibré). Enregistré dans le MLflow Model Registry sous `fraud-detection-classifier` v1, stage **Production** (`ml/register_model.py`).

## Pourquoi le PR-AUC plutôt que l'accuracy

Avec 0,17 % de fraude, un modèle qui prédirait systématiquement "légitime" obtiendrait déjà **99,83 % d'accuracy** sans détecter aucune fraude — l'accuracy est donc inutilisable comme métrique de décision ici. Le **PR-AUC** (aire sous la courbe précision-rappel) résume la capacité du modèle à bien classer la classe minoritaire sur tous les seuils possibles, ce qui en fait une métrique bien plus honnête sur ce type de problème (cf. `docs/01_vision.md`, objectifs mesurables).

## Détail au seuil retenu (maximisation du F1 sur le jeu de test)

| Run | TP | FP | TN | FN |
|---|---|---|---|---|
| `logreg_baseline` | 80 | 17 | 56 847 | 18 |
| `rf_balanced_v1` | 80 | 15 | 56 849 | 18 |

Les deux modèles détectent 80/98 fraudes du jeu de test (recall identique 0,8163) mais le RandomForest génère 2 faux positifs de moins.

**Observation sur le choix de seuil** : la recherche du seuil qui maximise le F1 (`ml/evaluate.py::best_threshold_by_f1`) sélectionne un seuil quasi égal à 1 pour la régression logistique (0,999999...), signe que ce modèle sature ses probabilités près de 0 ou 1 sur ce jeu de données linéairement bien séparé par les composantes PCA. En pratique, un seuil aussi extrême serait fragile en production (peu de marge). C'est un argument supplémentaire, au-delà du PR-AUC, en faveur du RandomForest dont le seuil optimal (≈0,50) est plus robuste.

## Traçabilité (tags MLflow — mapping sur les "5 Q" du Chapitre 1)

Chaque run porte les tags suivants, vérifiables dans `mlflow ui` :

| Tag | Valeur | Question tracée |
|---|---|---|
| `data_version` | `284807_rows` | Quelle donnée ? |
| `code_version` | hash du commit Git au moment de l'entraînement | Quelle version ? |
| `trained_by` | `ML Engineer 1` | Quel responsable ? |
| `dbt_test_status` | statut des tests dbt (ex. `23/23 PASS`) au moment du run | Quelle validation ? |

*(Le nom du modèle et sa version — "Quel modèle ?" — sont directement portés par le Model Registry MLflow.)*

## Artefacts loggés par run

- `confusion_matrix_<run>.png`
- `pr_curve_<run>.png`
- Modèle scikit-learn complet (`Pipeline` StandardScaler + classifieur), avec exemple d'entrée (`input_example`) pour l'inférence de signature.

## Limites et pistes d'amélioration (non implémentées à ce stade, pour rester dans le scope du module)

- **SMOTE / rééchantillonnage** (`imbalanced-learn`, déjà dans `requirements.txt`) : à tester en complément du `class_weight="balanced_subsample"` pour voir si le recall peut être amélioré sans trop dégrader la precision.
- **Split temporel** plutôt que stratifié aléatoire : plus réaliste pour un cas d'usage de production (entraîner sur le passé, tester sur le futur), mais non retenu ici pour rester au plus proche du protocole standard de comparaison de modèles sur ce dataset académique.
- **Recherche d'hyperparamètres** (`GridSearchCV`/`RandomizedSearchCV`) : les hyperparamètres du RandomForest (`n_estimators=200`, `max_depth=12`) sont raisonnables mais non optimisés finement.

## Comment reproduire

```bash
python ml/train.py            # entraîne et logue les 2 runs dans MLflow
mlflow ui --backend-store-uri sqlite:///mlflow.db   # explorer les runs dans le navigateur
python ml/register_model.py   # enregistre le meilleur run dans le Model Registry + exporte ml/artifacts/model.pkl
```
