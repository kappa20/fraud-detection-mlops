# Données du projet

## Dataset requis : Credit Card Fraud Detection (ULB)

Le pipeline DataOps de ce projet (Phase B) a besoin du fichier `creditcard.csv`, **non fourni dans ce dépôt** (144 Mo, licence Kaggle ODbL qui restreint la redistribution automatisée).

### Étapes pour l'obtenir

1. Créer un compte sur [kaggle.com](https://www.kaggle.com) si nécessaire.
2. Télécharger le dataset **"Credit Card Fraud Detection"** du Machine Learning Group de l'ULB (Université Libre de Bruxelles).
3. Décompresser l'archive et placer le fichier exactement à ce chemin :
   ```
   projet/data/raw/creditcard.csv
   ```

### Description du dataset

- 284 807 transactions par carte bancaire, réalisées par des porteurs européens en septembre 2013.
- 492 transactions frauduleuses (`Class = 1`), soit **0,172 %** du total — jeu fortement déséquilibré.
- Colonnes :
  - `Time` : secondes écoulées depuis la première transaction du jeu de données.
  - `V1` à `V28` : composantes issues d'une transformation PCA (anonymisation), sans signification métier directe.
  - `Amount` : montant de la transaction.
  - `Class` : 0 = transaction légitime, 1 = fraude.

### Important

- Ce fichier est exclu du suivi Git (`.gitignore`) — ne jamais forcer son ajout (`git add -f`).
- La CI/CD ne dépend jamais de ce fichier réel : elle utilise une fixture synthétique versionnée (`../tests/fixtures/sample_transactions.csv`), générée par `../scripts/make_sample_fixture.py`.
