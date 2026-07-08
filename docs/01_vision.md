# Livrable 1 — Vision du projet

**Projet :** Détection de fraude bancaire — Classification des transactions frauduleuses
**Module :** MLOps & DataOps — Pr. Mohammed AIT DAOUD, FSBM, Université Hassan II de Casablanca, 2025/2026
**Équipe :** voir `../info.txt`

---

## 1. Problématique

La fraude sur les transactions par carte bancaire représente une perte financière directe pour les banques et les commerçants, et une perte de confiance pour les clients. Le volume de transactions légitimes rend une détection manuelle impossible : la fraude ne représente statistiquement qu'une fraction infime des transactions (dans notre jeu de données de référence, 492 transactions frauduleuses sur 284 807, soit **0,17 %**), ce qui rend le problème doublement difficile — il faut détecter un événement rare, en temps quasi réel, sans pénaliser l'expérience des clients légitimes par des faux positifs excessifs.

Au-delà du seul modèle de classification, la problématique posée par le module est plus large : *"comment livrer et maintenir un système data/ML robuste et utile dans la durée ?"* (reformulation du problème central du Chapitre 1 du cours). Un modèle de détection de fraude entraîné une fois sur un notebook n'a aucune valeur opérationnelle s'il n'est pas :
- reproductible (mêmes données + même code + mêmes paramètres → même résultat),
- traçable (on doit pouvoir répondre aux **5 questions** du cours : quelle donnée, quelle version, quel modèle, quel responsable, quelle validation),
- surveillé en production (les comportements de fraude évoluent : *concept drift* et *data drift*),
- gouverné (qui a accès aux données sensibles, qui valide un nouveau modèle avant mise en production).

C'est précisément l'écart, décrit dans le Chapitre 1 du cours, entre un **bon prototype** (qui fonctionne dans un notebook, sur un jeu de données figé) et un **bon système** (qui fonctionne en continu, sur des données qui évoluent, avec plusieurs contributeurs) que ce projet doit combler.

## 2. Objectifs

### Objectif métier
Fournir à une institution financière un service capable d'évaluer, pour chaque transaction, une probabilité de fraude exploitable pour déclencher une action (blocage, vérification manuelle, alerte client).

### Objectifs pédagogiques (démonstration de l'industrialisation du cycle de vie)
En reprenant le cycle de vie en 8 étapes présenté au Chapitre 1 (slide 34) comme fil conducteur du projet :

| # | Étape du cycle de vie (cours) | Application dans notre projet |
|---|---|---|
| 1 | Cadrage du besoin | Cette section (Vision) : problème métier, indicateurs de succès (PR-AUC, recall), contraintes (déséquilibre des classes), acteurs (voir §3) |
| 2 | Acquisition et préparation des données | Ingestion `dlt` du dataset Kaggle Credit Card Fraud (ULB) vers DuckDB |
| 3 | Construction des pipelines | `dbt` (transformations versionnées et testées) + `Dagster` (orchestration) |
| 4 | Expérimentation et entraînement | `scikit-learn` + tracking `MLflow` (Experiment Tracking) |
| 5 | Validation | Tests de qualité des données (dbt tests, Data Contract) + évaluation du modèle (PR-AUC, recall, precision, F1) |
| 6 | Déploiement | Service `FastAPI` conteneurisé avec `Docker` |
| 7 | Monitoring et observabilité | Disponibilité, temps de réponse, métriques ML, dérive simple |
| 8 | Maintenance et amélioration continue | Sprints itératifs, rétrospectives, Model Registry MLflow (Staging → Production) |

### Objectifs mesurables (indicateurs de succès)
- Pipeline DataOps (`dlt → DuckDB → dbt → Dagster`) exécutable de bout en bout sans intervention manuelle.
- Au moins 3 familles de tests de qualité couvertes (schéma, contenu, métier — Chapitre 3).
- Modèle avec **PR-AUC ≥ 0,80** sur le jeu de test (métrique primaire, l'accuracy étant trompeuse sur un jeu à 0,17 % de positifs).
- API exposant `POST /predict` et `GET /health`, conteneurisée, avec CI/CD qui bloque tout merge si les tests échouent.
- Historique Git complet avec commits structurés et Pull Requests entre les membres de l'équipe.

## 3. Utilisateurs cibles (Data Consumers)

Le cours (Chapitre 1, notion de *"Data/ML as a Product"*) insiste sur le fait qu'un produit data/ML doit avoir des **utilisateurs identifiés**. Pour ce projet :

| Utilisateur (Data Consumer) | Besoin | Interface |
|---|---|---|
| Système de paiement / back-office bancaire | Score de fraude en temps quasi réel pour chaque transaction | `POST /predict` (API FastAPI) |
| Analyste fraude (Data Analyst) | Comprendre les transactions signalées, consulter les tendances | Rapports dbt (`agg_fraud_hourly_summary`), dashboards |
| Data Scientist / ML Engineer | Comparer les expériences, ré-entraîner, versionner les modèles | MLflow (Experiment Tracking + Registry) |
| Data Engineer | Garantir la fiabilité et la fraîcheur du pipeline | Dagster (UI d'orchestration), tests dbt, Data Contract |
| Équipe Ops / SRE | Surveiller la disponibilité et la dérive du service | `GET /metrics`, rapports de dérive (`monitoring/drift_check.py`) |
| Auditeur / Conformité | Vérifier la traçabilité des décisions (gouvernance) | Historique Git, MLflow Registry, Data Lineage |

## 4. Valeur métier

- **Réduction des pertes financières** liées à la fraude non détectée (faux négatifs).
- **Réduction de la friction client** en limitant les faux positifs (transactions légitimes bloquées à tort) — d'où le choix de métriques d'évaluation adaptées (PR-AUC/F1 plutôt qu'accuracy) et d'un seuil de décision documenté et ajustable.
- **Confiance et auditabilité** : chaque décision de score peut être reliée à une version de modèle, une version de données et un run d'entraînement (traçabilité — cf. triade ci-dessous), ce qui est indispensable dans un contexte réglementé (secteur financier).
- **Réduction du time-to-value** : grâce à l'automatisation du pipeline (DataOps) et à l'orchestration (Dagster), une mise à jour du modèle ou des règles de qualité peut être livrée rapidement et en confiance (principe *"Delivering value fast"* du DataOps Manifesto).

## 5. Positionnement DataOps / MLOps du projet

### Pourquoi DevOps seul ne suffit pas (Chapitre 1)
Le code de classification est trivial à versionner avec Git ; ce qui pose problème, ce sont les **données qui changent**, le **modèle qui dérive**, et la nécessité de **résultats auditables** — les trois raisons pour lesquelles le cours explique que DevOps doit être étendu par DataOps (fiabiliser la donnée) et MLOps (industrialiser le cycle de vie du modèle).

| Dimension | DevOps | DataOps (notre pipeline) | MLOps (notre modèle) |
|---|---|---|---|
| Objet principal | Code applicatif (API FastAPI) | Pipeline `dlt → DuckDB → dbt` | Modèle scikit-learn |
| Finalité | Livrer le service | Fiabiliser les transactions ingérées | Industrialiser la détection de fraude |
| Artefacts | Image Docker, releases | Tables DuckDB, tests dbt | Runs MLflow, modèle enregistré |
| Risques clés | Régression logicielle | Dérive de schéma, données corrompues | Dérive du modèle (nouveaux patterns de fraude) |
| Pratiques phares | CI/CD, tests unitaires | Data Contract, Data Lineage, tests qualité | Experiment Tracking, Registry, monitoring |

*(Tableau adapté du comparatif DevOps/DataOps/MLOps présenté au Chapitre 1.)*

### Où se situe le projet dans la pyramide de maturité MLOps (Atwal, 2020)
Le cours présente une hiérarchie des besoins en 6 niveaux. Notre projet vise à couvrir les 5 premiers niveaux dans le cadre du module (le niveau "Gouvernance" étant traité de façon introductive, faute de temps/échelle) :

1. **Fondation (Base DevOps)** — Git, CI/CD, tests ✅ couvert (Livrable 3, 8)
2. **Ingénierie des données** — pipelines, qualité, lineage ✅ couvert (Livrable 3, 4)
3. **Plateforme ML** — Model Registry (MLflow) ✅ couvert (Livrable 6)
4. **Automatisation** — orchestration Dagster du pipeline complet ✅ couvert (Livrable 3)
5. **Monitoring** — dérive simple, disponibilité, métriques ML ✅ couvert (Livrable 9)
6. **Gouvernance** — explicabilité, conformité, audit ⚠️ traité de façon introductive (traçabilité MLflow, Data Contract, historique Git) — hors échelle complète d'un projet étudiant

### Triade Reproductibilité / Traçabilité / Gouvernance (Chapitre 1)
- **Reproductibilité** : `requirements.txt` figé, code versionné (Git), données versionnées via le pipeline dlt (chargement idempotent dans DuckDB), paramètres et environnement du modèle journalisés dans MLflow → formule du cours : *Même code + Mêmes données + Mêmes dépendances + Mêmes paramètres = Résultat cohérent*.
- **Traçabilité** : chaque run MLflow répond aux **5 Q** du cours :
  - *Quelle donnée ?* → nombre de lignes ingérées + date d'ingestion dlt (tag `data_version`)
  - *Quelle version ?* → hash du commit Git (tag `code_version`)
  - *Quel modèle ?* → nom + version dans le Model Registry
  - *Quel responsable ?* → tag `trained_by`
  - *Quelle validation ?* → statut des tests dbt au moment de l'entraînement (tag `dbt_test_status`)
- **Gouvernance** : Data Contract (Livrable 4) formalisant qui peut consommer quelles données, sous quelles règles de qualité ; Pull Requests obligatoires sur GitHub avant fusion sur la branche principale.

## 6. Data Strategy

### Source et nature des données
Le projet utilise le jeu de données public **"Credit Card Fraud Detection" (ULB / Machine Learning Group, via Kaggle)** : 284 807 transactions par carte bancaire européennes réalisées en septembre 2013, dont 492 frauduleuses. Les variables `V1` à `V28` sont le résultat d'une transformation PCA (Analyse en Composantes Principales) appliquée par les auteurs du dataset pour des raisons de confidentialité — elles sont donc **anonymisées et sans signification métier directement interprétable**. Seules les colonnes `Time` (secondes écoulées depuis la première transaction), `Amount` (montant) et `Class` (0 = légitime, 1 = fraude) sont interprétables en l'état.

> **Choix assumé de rigueur scientifique** : plutôt que d'inventer artificiellement des colonnes métier (ex. un faux `merchant_category`) pour "enrichir" la démonstration de qualité des données, nous documentons honnêtement cette limite. Les dimensions de qualité (Chapitre 3) sont appliquées sur les colonnes réellement interprétables (`Time`, `Amount`, `Class`) et sur des contrôles génériques de schéma pour l'ensemble des colonnes (types, nullité, domaine). Cela reflète une situation réaliste : en pratique, les data scientists travaillent très souvent sur des données déjà anonymisées ou pré-transformées par des équipes en amont, et la qualité des données doit être évaluée avec les moyens du bord.

### Gouvernance et accès
- Le fichier source (`creditcard.csv`) n'est jamais commité dans le dépôt Git (licence Kaggle restrictive sur la redistribution, volumétrie ~144 Mo) — voir `data/README.md`.
- La CI/CD s'appuie sur une fixture synthétique versionnée (`tests/fixtures/sample_transactions.csv`) pour ne jamais dépendre du fichier réel.
- Le Data Contract (`docs/data/data_contract.yaml`) formalise le schéma attendu, les règles de qualité et les consommateurs autorisés du produit de données.

### Cycle de vie de la donnée dans le pipeline
```
Kaggle CSV (source statique)
   → dlt (ingestion automatisée, chunkée) → DuckDB (raw.transactions_raw)
   → dbt staging (typage, renommage)      → DuckDB (stg_transactions)
   → dbt marts (nettoyage, features)      → DuckDB (fct_transactions_clean, fct_transactions_features)
   → dbt marts (agrégats)                 → DuckDB (agg_fraud_hourly_summary)
   → ml/train.py                          → MLflow (Experiment Tracking + Registry)
   → api/main.py (FastAPI)                → Service exposé (POST /predict)
   → monitoring/                          → Logs de prédiction, rapport de dérive
```
Ce flux est détaillé et illustré (diagramme) dans `docs/data/data_lineage.md` (Livrable 4).

### Qualité et confiance (rappel du Chapitre 3)
> *"Disponibilité ≠ fiabilité."* — une donnée peut être chargée sans erreur technique et rester non fiable si elle contient des doublons, des valeurs hors domaine, ou n'est pas documentée.

La stratégie de qualité suit le principe **Shift Left** du cours : contrôler dès l'ingestion (`quality/validate_schema.py`) plutôt que de découvrir un problème en aval, dans le modèle ou en production.

## 7. Références citées (issues du cours, à conserver pour le rapport final)

- Jabbari, R., & al. (2016) — *What is DevOps?*
- Bergh, C. (2017) — *DataOps Manifesto* (18 principes)
- Atwal, H. (2019) — *Practical DataOps*
- Atwal, H. (2020) — hiérarchie des besoins en MLOps (pyramide de maturité)
- Gift, N. & Deza, A. (2021) — *Practical MLOps*
- Wang, R. Y. & Strong, D. M. (1996) — *What Data Quality Means to Data Consumers* ("fitness for use")
- DAMA International (2017) — *DAMA-DMBOK2 Data Management Framework*
