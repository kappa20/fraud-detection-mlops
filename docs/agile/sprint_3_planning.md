# Sprint 3 — Planning

**Durée :** 2 semaines
**Objectif de sprint (Sprint Goal) :** *"Le modèle est exposé via une API conteneurisée, testée en continu par la CI/CD, et supervisée en production (monitoring, dérive)."*

## Contexte

Ce sprint correspond aux Phases E et F : c'est le sprint qui rend le projet réellement "industrialisable" au sens du cahier des charges — jusqu'ici, le modèle n'existait que sous forme de fichier local. Il applique le principe cité en cours (Chapitre 2) : *"Chaque push déclenche automatiquement la validation complète du pipeline. Un pipeline qui ne passe pas les tests ne peut pas être mergé."*

## User Stories sélectionnées (voir `product_backlog.md`)

| ID | User Story (résumé) | Points | Assigné |
|---|---|---|---|
| US-14 | `POST /predict` | 5 | Youssef Sarraf |
| US-15 | `GET /health` | 1 | Youssef Sarraf |
| US-16 | Conteneurisation Docker | 3 | Youssef Sarraf |
| US-17 | CI/CD GitHub Actions | 5 | Anass Dabibe |
| US-18 | Monitoring (disponibilité, latence, métriques ML) | 3 | Aymane El Badri |
| US-19 | Rapport de dérive simple | 3 | EL HABTI Oumaima (Data Analyst) |
| US-20 | README + guides d'installation/utilisation | 3 | Hassan El Hadi (PO) |

**Capacité du sprint :** 23 points.

## Risques identifiés en planning

- **La CI ne doit jamais dépendre du vrai dataset Kaggle** (non redistribuable) — mitigation : générer une fixture synthétique versionnée avant même d'écrire le workflow CI.
- **Risque de "ça marche en local, pas en CI"** (cf. Chapitre 2) — mitigation : valider systématiquement chaque étape dans un environnement isolé avant de la considérer terminée.

## Definition of Ready

- Modèle enregistré dans le Model Registry MLflow (`fraud-detection-classifier`, stage `Production`) et exportable en `.pkl`.
