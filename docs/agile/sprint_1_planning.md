# Sprint 1 — Planning

**Durée :** 2 semaines
**Objectif de sprint (Sprint Goal) :** *"Disposer d'une vision partagée du projet, d'un backlog priorisé, et d'un pipeline DataOps minimal (dlt → DuckDB → dbt → Dagster) exécutable de bout en bout sur le dataset de transactions."*

## Contexte
Ce sprint correspond aux Phases A et B du plan d'implémentation technique : fondations du dépôt, vision, backlog, puis construction du pipeline d'ingestion et de transformation des données. Conformément au principe Lean rappelé en cours — *"On n'automatise pas le chaos. Il faut d'abord comprendre, simplifier et standardiser, puis automatiser"* — on livre volontairement un pipeline minimal mais fiable avant d'ajouter la complexité du Machine Learning (Sprint 2) et du déploiement (Sprint 3).

## User Stories sélectionnées (voir `product_backlog.md`)

| ID | User Story (résumé) | Points | Assigné |
|---|---|---|---|
| US-01 | Vision du projet | 3 | Product Owner |
| US-02 | Product Backlog + planning des sprints | 2 | Scrum Master |
| US-03 | Initialisation du dépôt Git | 2 | Data Engineer (lead) |
| US-04 | Ingestion `dlt` → `DuckDB` | 5 | Data Engineer (lead) |
| US-05 | Validation shift-left du schéma | 3 | Data Engineer 3 |
| US-06 | Transformations `dbt` (staging + marts) | 5 | Data Engineer 2 |
| US-07 | Orchestration `Dagster` | 5 | Data Engineer 2 |

**Capacité du sprint :** 25 points (7 membres actifs sur ce sprint, 2 Data Analysts en observation/préparation Sprint 2).

## Risques identifiés en planning
- **Dépendance bloquante** : le dataset réel (`creditcard.csv`, Kaggle) doit être téléchargé manuellement par un membre de l'équipe avant de pouvoir exécuter le pipeline dlt en conditions réelles — mitigation : développer et tester d'abord sur un petit échantillon synthétique, puis valider sur le fichier réel dès qu'il est disponible.
- **Prise en main de dlt/dbt-duckdb/Dagster** : aucun membre n'a une expérience approfondie de ces outils au-delà du TP du Chapitre 2 — mitigation : s'appuyer sur le pattern déjà validé par le professeur dans ce TP (`td/tp_chapitre_2/`).

## Definition of Ready (avant d'entrer dans le sprint)
- Cahier des charges du module lu par toute l'équipe.
- Rôles Agile attribués (voir `../../info.txt`).
- Environnement Python installable via `requirements.txt`.
