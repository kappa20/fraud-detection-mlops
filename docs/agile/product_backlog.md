# Product Backlog — Détection de fraude bancaire

**Product Owner :** Hassan El Hadi
**Scrum Master :** Yassin Farih
**Format des User Stories :** *En tant que \<rôle\>, je veux \<besoin\>, afin de \<valeur\>.*
**Estimation :** points en échelle de Fibonacci (1, 2, 3, 5, 8, 13)
**Priorité :** Must (M) / Should (S) / Could (C) — inspiré MoSCoW

Ce backlog découpe les 10 livrables du cahier des charges (`../../PROJETS.pdf`) en user stories exploitables sur 3 sprints. Chaque story référence le livrable auquel elle contribue.

| ID | User Story | Livrable | Priorité | Points | Sprint |
|---|---|---|---|---|---|
| US-01 | En tant que **Product Owner**, je veux formaliser la problématique, les objectifs et la valeur métier du projet, afin que l'équipe partage une vision commune avant de coder. | 1 — Vision | M | 3 | 1 |
| US-02 | En tant que **Scrum Master**, je veux un Product Backlog priorisé et un planning de 3 sprints, afin d'organiser le travail de l'équipe de façon itérative. | 2 — Agile | M | 2 | 1 |
| US-03 | En tant que **Data Engineer**, je veux initialiser le dépôt Git avec une structure de dossiers claire, afin que chaque membre de l'équipe puisse contribuer sans conflit. | 3 — GitHub | M | 2 | 1 |
| US-04 | En tant que **Data Engineer**, je veux ingérer automatiquement le dataset de transactions via `dlt` vers `DuckDB`, afin de disposer d'une table brute reproductible sans script ad hoc. | 3 — Pipeline DataOps | M | 5 | 1 |
| US-05 | En tant que **Data Engineer**, je veux valider le schéma et la nullité des données dès l'ingestion (*shift left*), afin de détecter les anomalies avant qu'elles ne se propagent dans les transformations. | 4 — Qualité | M | 3 | 1 |
| US-06 | En tant que **Data Engineer**, je veux transformer les données brutes avec `dbt` (staging puis marts), afin d'obtenir des tables nettoyées et documentées prêtes pour le Machine Learning. | 3 — Pipeline DataOps | M | 5 | 1 |
| US-07 | En tant que **Data Engineer**, je veux orchestrer l'ingestion, la validation et la transformation avec `Dagster`, afin que le pipeline s'exécute de bout en bout de façon fiable et visible. | 3 — Pipeline DataOps | M | 5 | 1 |
| US-08 | En tant que **Data Analyst**, je veux documenter le Data Contract (schéma, règles de qualité, consommateurs) du produit de données, afin de formaliser les engagements de qualité envers les équipes en aval. | 4 — Qualité | M | 3 | 2 |
| US-09 | En tant que **Data Analyst**, je veux documenter le lignage des données (data lineage) de la source Kaggle jusqu'au service exposé, afin de pouvoir diagnostiquer rapidement l'origine d'une anomalie. | 4 — Qualité | S | 3 | 2 |
| US-10 | En tant que **Data Engineer**, je veux des tests dbt couvrant schéma, contenu et règles métier, afin de garantir qu'un pipeline cassé ne soit jamais utilisé pour entraîner un modèle. | 4 — Qualité | M | 3 | 2 |
| US-11 | En tant que **ML Engineer**, je veux préparer un jeu d'entraînement/test stratifié à partir des tables dbt, afin de traiter correctement le fort déséquilibre des classes (0,17 % de fraude). | 5 — Machine Learning | M | 3 | 2 |
| US-12 | En tant que **ML Engineer**, je veux entraîner et comparer plusieurs modèles scikit-learn (régression logistique, random forest) avec un tracking `MLflow`, afin de choisir objectivement le meilleur modèle selon des métriques adaptées (PR-AUC, recall). | 5 — Machine Learning / 6 — MLflow | M | 8 | 2 |
| US-13 | En tant que **ML Engineer**, je veux enregistrer le modèle retenu dans le MLflow Model Registry avec ses métadonnées de traçabilité, afin de pouvoir en suivre les versions et le promouvoir en production. | 6 — MLflow | M | 3 | 2 |
| US-14 | En tant qu'**utilisateur du système de paiement (Data Consumer)**, je veux appeler un endpoint `POST /predict`, afin d'obtenir un score de fraude pour une transaction donnée. | 7 — Déploiement | M | 5 | 3 |
| US-15 | En tant qu'**équipe Ops**, je veux un endpoint `GET /health`, afin de vérifier que le service est disponible avant de le mettre en trafic. | 7 — Déploiement | M | 1 | 3 |
| US-16 | En tant que **ML Engineer**, je veux conteneuriser le service avec `Docker`, afin de garantir un déploiement reproductible indépendant de la machine hôte. | 7 — Déploiement | M | 3 | 3 |
| US-17 | En tant que **Data Engineer**, je veux un pipeline CI/CD GitHub Actions qui lance les tests et construit l'image Docker à chaque push, afin qu'un code cassé ne puisse jamais être fusionné sur la branche principale. | 8 — CI/CD | M | 5 | 3 |
| US-18 | En tant qu'**équipe Ops**, je veux surveiller la disponibilité, le temps de réponse et des métriques ML du service, afin de détecter rapidement un incident en production. | 9 — Monitoring | S | 3 | 3 |
| US-19 | En tant que **Data Analyst**, je veux un rapport simple de dérive des données comparant la distribution récente à celle d'entraînement, afin d'anticiper le besoin de ré-entraînement du modèle. | 9 — Monitoring | S | 3 | 3 |
| US-20 | En tant que **nouveau contributeur**, je veux un README avec architecture, guide d'installation et guide d'utilisation, afin de pouvoir installer et faire fonctionner le projet sans aide externe. | 10 — Documentation | M | 3 | 3 |

**Total estimé : 71 points sur 3 sprints** (~24 points/sprint en moyenne — cohérent avec une équipe de 9 personnes sur des sprints courts).

## Definition of Done (DoD) — commune à toutes les user stories
- Code versionné sur Git, revu via Pull Request par au moins un autre membre de l'équipe.
- Tests associés (dbt test, pytest) exécutés et passants.
- Documentation associée mise à jour (README, docstring, ou fichier `docs/`).
- Démontrable lors de la Sprint Review.
