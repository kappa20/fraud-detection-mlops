# platform_api — plateforme d'opérations (tableau de bord + API)

Service FastAPI (port 4607 sur Komodo) + interface React (`platform_ui/`, servie par FastAPI).
Tout est en français côté interface ; le code et les noms de variables sont en anglais.

## Lancer en local

```bash
cd platform_ui && npm install && npm run build      # une fois (ou `npm run dev` : :5173 avec proxy)
cd .. && uvicorn platform_api.main:app --port 8000   # http://localhost:8000
```

Connexion : variable `PLATFORM_USERS` (`"utilisateur:mot_de_passe,autre:mot_de_passe"`, défaut de démo `admin:changeme`)
et `PLATFORM_SECRET` (signature des jetons). **À surcharger dans l'Environment de la stack Komodo** : le service est joignable
depuis Internet et expose des actions destructives. L'authentification est vérifiée côté API sur toutes les routes sauf
`/health`, `/auth/login` et les fichiers statiques.

## Qui fait quoi (réel vs. à brancher)

| Fonction | Endpoints | État |
|---|---|---|
| Login employé | `POST /auth/login` | **Réel** (simple : comptes en variable d'environnement) |
| Table des transactions paginée côté serveur (tri, filtres) | `GET /transactions`, `/transactions/{id}` | **Réel** (DuckDB en mémoire construit depuis le CSV, reconstruit quand le fichier change) |
| Export CSV de la sélection | `GET /transactions/export` | **Réel** |
| Création / modification / suppression par lot + versionnement | `POST /transactions/changes` | **Réel** : réécriture atomique du CSV, `dvc add` + `dvc push` + commit git (bot), annulation si le versioning échoue |
| Historique des versions + rollback | `GET /versions`, `POST /versions/{sha}/rollback` | **Réel** : rollback = nouveau commit, jamais de réécriture ni de push |
| Seuil, simulation, auto-ré-entraînement, promotion auto | `GET/PUT /config`, `/config/threshold`, `POST /data/simulate`, `/data/ingest` | **Réel** |
| Pipeline complet / ré-entraînement, suivi par étape | `POST /pipeline/run`, `/pipeline/retrain`, `GET /jobs/{id}`, `POST /runs/{id}/rerun`, `GET /runs` | **Réel** : sous-processus Dagster lu ligne à ligne (`STEP_START/SUCCESS/FAILURE`) ; un seul job à la fois |
| Dérive (PSI par variable, historique, distributions) | `GET /drift/current`, `/drift/history`, `/drift/distribution`, `POST /drift/check` | **Réel** : réutilise `monitoring/drift_check.py` |
| Candidat vs. Production, approbation / rejet | `GET /models/comparison`, `POST /models/approve`, `/models/reject` | **Réel** (MLflow Registry) |
| Redémarrage de `fraud-api` après approbation | `POST /models/redeploy` (+ appel automatique à l'approbation) | **À valider sur Komodo** : appel `RestartStack` de l'API Komodo si `KOMODO_URL/API_KEY/API_SECRET/STACK` sont définis, sinon « non effectué » (la promotion MLflow a bien lieu). Le format exact de la requête n'a pas pu être testé hors Komodo |
| État des services de l'écosystème | `GET /services/health` | **Réel** (pings depuis le serveur, réseau docker interne) |

## Points à connaître

- **Source de vérité = `data/raw/creditcard.csv`** (fichier suivi par DVC). Le DuckDB du projet est reconstruit depuis ce CSV
  à chaque run dlt : y écrire perdrait les corrections.
- **Identifiant de transaction = position de la ligne** (le CSV n'a pas de clé) ; elle se décale après une suppression. Un verrou
  optimiste (`base_version`, compteur `dataset_epoch` incrémenté à chaque correction/rollback, pas à un simple ajout) refuse un lot
  préparé sur une version périmée (HTTP 409).
- **Dérive** : « référence » = tout le dataset d'origine, « récent » = les lignes arrivées après (`time > 172 792`). Tant qu'il y a
  moins de 100 nouvelles lignes, on retombe sur la comparaison des deux moitiés temporelles (comme `drift_report.md`).
- **Promotion** : par défaut (`auto_promote = false`) le job enregistre le candidat en Staging (`FRAUD_REGISTER_NO_PROMOTE=1` →
  `ml/register_model.py --no-promote`) et attend l'approbation dans le tableau de bord.
- Le suivi d'étapes dépend du format de log de `dagster job execute` ; s'il change, le job s'exécute normalement mais l'interface
  n'affiche qu'une étape « Pipeline ».
