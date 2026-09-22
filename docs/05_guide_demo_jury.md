# Live demo guide: showing the platform to the jury

Demo target: **http://exp.s3.fsbm.ma:4607/#/versions** (the operations dashboard, `platform_api` + React UI on Komodo).
Target length: **7 to 9 minutes**, with a fallback plan if anything fails.

> Status of this guide (updated 2026-09-22). **Checked on the live server:** the 9-service stack is up; the Écosystème page
> (including the Dagster card); the Dagster UI (jobs, schedule, sensor, daemons); Prometheus targets and its 7 alert rules; the Grafana
> "Dérive & pipeline" dashboard; a retraining launched from the dashboard and followed in Dagster. **Not rehearsed live:** the
> Transactions edit / rollback flow, `simulate`, the drift alert going *firing*, and the approve / reject buttons. Do one full dry run
> 24 h before, and time the retraining step (see §4).

---

## 0. Story to tell

One sentence to keep in your head:

> "New data arrives → we **version** it (DVC + git) → we **detect drift** (PSI, exported to Prometheus and alerted) → we **retrain**
> through the Dagster pipeline → a **quality gate** compares the candidate with Production → a human **approves or rejects** → the
> scoring API is redeployed. And every code change is **tested by CI before it is deployed**."

Every screen of the demo is one link in this chain. Say which link you are on before you click.

---

## 1. Pre-flight checklist (30 min before)

| Check | How | Expected |
|---|---|---|
| Dashboard is up | open `http://exp.s3.fsbm.ma:4607/` | login page |
| You can log in | type the dashboard credentials **yourself** (don't paste them on a shared screen) | Transactions page |
| Whole ecosystem is green | sidebar → **Écosystème** → "Vérifier maintenant" | MLflow, Grafana, Prometheus, scoring API, **Dagster**, MinIO all "disponible" |
| Dataset is untouched | Transactions or Pipeline page | **284 807** transactions |
| Production model | `http://exp.s3.fsbm.ma:4602/#/models` | `fraud-detection-classifier` with one version in **Production**: **write down its version number and PR-AUC** (you will compare candidates to it, §2 step 5). **As of 2026-09-22 v1 is still in Staging (PR-AUC 0.8444) and Production is empty: approve it once in the dashboard before the demo** (§6) |
| Scoring API serves that model | `http://exp.s3.fsbm.ma:4601/health` | `model_version` matches the Production version. If not, restart the `api` service in Komodo (§6) |
| Dagster is healthy | `http://exp.s3.fsbm.ma:4608` → **Deployment → Daemons** | Sensors, Scheduler, Run queue "Running" |
| No alert firing | `http://exp.s3.fsbm.ma:4604/alerts` | 7 rules, all **inactive** |
| Latest dataset version | **Versions du dataset** page | **write down the top commit SHA**, you will roll back to it (§7) |
| Other tabs open and logged in | Grafana `:4603` (dashboard **Dérive & pipeline**), MLflow `:4602`, Dagster `:4608`, Swagger `:4601/docs` | ready to switch |
| Fallback ready | `../fraud-detection-mlops_private/screenshots/platform_ui/` and a screen recording | see §8 |

Also: full-screen the browser (F11), zoom 110-125 % so the back row can read, close notifications, disable the screensaver.

**Useful facts if the jury asks:**

- Only `/health`, `/metrics`, `/auth/login` and static files are public; every other API route returns **401** without a token.
  (`/metrics` is public on purpose: Prometheus scrapes it. It exposes counters, not data.)
- The default demo account is `admin:changeme` unless `PLATFORM_USERS` is overridden in Komodo. Make sure it has been.
  Grafana (`admin`/`admin`) and MinIO (`admin`/`admin12345`) also still use their default credentials.
- The dashboard was captured read-only in the past, and one write demo (`simulate`) was already cleaned up (backup branch
  `backup/komodo-pre-cleanup-20260919` on the server).

---

## 2. Demo flow (recommended order)

### Step 1: Écosystème (≈ 45 s), "what is deployed"

Sidebar → **Écosystème**.

- Point at the cards: scoring API, MLflow Registry, Grafana, Prometheus, **Dagster (orchestration)**, MinIO, the platform's own Swagger.
- Say: "9 containers on one Docker network on Komodo (8 long-running services and one setup task that creates the storage buckets).
  Komodo may label the stack 'unhealthy' because that setup task has finished: that is expected. **A push to GitHub does not deploy
  by itself: CI runs the tests first, and only if they pass does a job redeploy the stack through the Komodo API.** The health checks
  on this page run from the server, inside the Docker network, and refresh every 30 s."

### Step 2: Transactions (≈ 1 min 30), "the data is a governed asset"

Sidebar → **Transactions**.

1. Show the KPI: 284 807 transactions "dans le dataset versionné".
2. Filter by fraud only and sort by amount. Say: "server-side pagination, DuckDB built from the DVC-tracked CSV".
3. Open a row (**Voir**) to show the drawer, then **Modifier** on one row and change something small (e.g. the amount).
4. The staging bar appears at the bottom. Click **Enregistrer et versionner** (blue button).
5. **Stop on the modal, don't rush.** Read it out: *"Ce lot sera appliqué au dataset, puis versionné avec dvc add et un commit git."*
   It shows Créations / Modifications / Suppressions counts.
6. Click **Enregistrer et versionner**. Wait for the toast with the **commit hash**.

Say: "A data change is never silent: atomic CSV rewrite, `dvc add`, `dvc push` to MinIO, git commit by a bot. If versioning fails,
the change is rolled back."

> If you'd rather not touch the live dataset, do this step on the **staging bar only**: stage a change, open the modal, read it,
> click **Retour**. You lose the commit hash but risk nothing.

### Step 3: Versions du dataset (≈ 1 min 30), "time travel" (your URL)

Go to `http://exp.s3.fsbm.ma:4607/#/versions`.

1. Show the history: commit SHA, author (bot), date, what changed.
2. Find the version you just created (or any older one) and click **Revenir à cette version** on the row just below the top one (the top row is tagged "Version courante"), then confirm in the modal.
3. Say: "**A rollback is a new commit, never a history rewrite or a force-push.** Nothing is ever lost, and the audit trail stays intact."
4. Refresh the list: the rollback commit is now at the top.

This is the strongest "DataOps" moment: dataset versioning with git semantics.

### Step 4: Pipeline & automatisation → Dérive (≈ 2 min), "the loop"

Sidebar → **Pipeline & automatisation**.

1. **État du déclencheur**: point at the progress bar ("N / seuil en attente"), the row count, and the retraining threshold.
2. **Simuler l'arrivée de données**: set **3000** transactions, drift **Forte**, click **Générer**.
   Small batches (a few rows) will *not* move the PSI on a 284k-row dataset; use thousands, with strong drift.
3. Sidebar → **Dérive des données**. A red banner appears: *"Dérive significative détectée (PSI max ≥ seuil)"*.
   - PSI cards per variable (click one to see reference vs. recent distribution and the history chart).
   - Explain PSI: < 0.1 stable, 0.1-0.25 watch, ≥ 0.25 significant drift. (Check the thresholds shown on your screen.)
4. Click **Recalculer et consigner** to add a point to the history.
5. Say: "This same PSI is exported to Prometheus, so it is also monitored and alerted outside the dashboard. You will see it in Grafana
   in a minute." (Prometheus scrapes every 30 s and the alert needs the condition to hold for 1 min, so expect **1 to 2 minutes** before
   it fires: this is why you start it now and come back to it at step 7.)

> The simulated rows are appended to the dataset and **versioned like any other change**. You'll undo them in §7.

### Step 5: Retraining and the promotion gate (≈ 2 min), "human in the loop"

From the red banner click **Ré-entraîner maintenant** (or, on the Pipeline page, **Ré-entraîner le modèle maintenant**).

1. The page shows **Dernier job** with **step-by-step progress**: ingestion (dlt) → validation → dbt run → dbt test → training → drift → register.
2. **Switch to Dagster** (`:4608`, or the link **Ouvrir l'UI Dagster** on the Pipeline page) → **Runs**: the same run is there with its graph
   and step logs. Say: "The dashboard launches the Dagster job; Dagster is the orchestrator and keeps the run history. The same job also runs
   on its own: **every night at 02:00** (schedule) and **when the dataset version changes outside the platform** (sensor). See them under **Automation**."
3. While it runs, explain the automation switches: auto-retrain on PSI, auto-promote *off* (so a human decides).
4. When it finishes, look at the **candidate vs. Production** comparison (PR-AUC, etc.).
5. Explain the gate: "the candidate is registered in **Staging**; it only replaces Production if the metric is better *and* someone approves".
6. **Click Rejeter** unless the candidate clearly beats the current Production model (the PR-AUC you wrote down in the pre-flight).
   Say: "Rejected candidates stay archived in the registry. On approval, the platform promotes it in MLflow and asks Komodo to restart
   the scoring API."

> **Risk:** approving a weaker candidate would replace the good Production model on the shared server. Rejecting is always the safe
> action for a demo.

> **Timing risk:** the full retraining pipeline (dbt on ~285k rows + training) may take minutes. Time it during your dry run. If it
> is longer than ~3 min, do **not** launch it live: open **Historique des runs** and the matching run in Dagster, and walk through a past
> run instead (Step 6).

### Step 6: Historique des runs (≈ 45 s), "traceability"

Sidebar → **Historique des runs**.

- Each run: trigger (manual / drift / API), user, timestamp, status, per-step results.
- Click a row to expand it.
- **Do not click "Relancer"** unless you want to start a real job.

### Step 7: The other tools (≈ 1 min 30), "it's a real stack"

Use the links in **Écosystème** or your pre-opened tabs.

| Tab | URL | What to show |
|---|---|---|
| Grafana → **Dérive & pipeline** | `:4603/d/fraud-drift-pipeline` | after step 4: tile **ALERTE**, max PSI above the threshold, PSI per feature, and the table of alerts in progress. Before any run, the "Dernier run" tile reads **AUCUN RUN** (blue): that is normal |
| Prometheus → Alerts | `:4604/alerts` | `FraudDataDriftHigh` **pending, then firing** after the simulation; the other 6 rules inactive |
| MLflow | `:4602/#/models` | registered model, versions, stages; runs and artifacts (stored in MinIO, metadata in PostgreSQL) |
| Swagger (scoring API) | `:4601/docs` | `POST /predict` → **Try it out** → execute → `fraud_probability`, `is_fraud`, `model_version` |
| Grafana → Fraud Detection API | `:4603` | request rate, p95 latency, 5xx rate |

(Port map: API 4601, MLflow 4602, Grafana 4603, Prometheus 4604, MinIO API/console 4605/4606, platform 4607, Dagster 4608.)

Say about alerts: "Rules for drift, a failed or stale pipeline run, and service availability. They are visible in Prometheus and Grafana;
sending them by email or chat would need Alertmanager, which we left out of scope."

---

## 3. Suggested timing and who says what

| Min | Screen | Key message |
|---|---|---|
| 0:00 | Écosystème | 9 containers, deployed by Komodo **after CI passes** |
| 0:45 | Transactions | governed, versioned data |
| 2:15 | Versions | rollback = new commit |
| 3:45 | Pipeline → Dérive | drift detected (PSI), simulation started |
| 5:45 | Retrain + Dagster + gate | orchestrated run, candidate vs. Production, human approval |
| 7:45 | Grafana / Prometheus alert / MLflow | drift monitored and alerted, traceability |

---

## 4. If the jury interrupts

| Question | Short answer |
|---|---|
| "Why PSI?" | Standard, cheap, works per variable, and gives an interpretable threshold. It reuses `monitoring/drift_check.py`. |
| "Why not auto-promote?" | It's a settings toggle; we default to manual approval because a wrong model in production costs money. |
| "Where does the data live?" | `data/raw/creditcard.csv` tracked by DVC; remote = MinIO bucket `dvc-store`; the git commit stores only the `.dvc` pointer. |
| "What if two people edit at once?" | Optimistic lock (`base_version` / `dataset_epoch`): a batch prepared on a stale version is refused with HTTP 409. |
| "How many tests?" | `pytest`: 71 (run on every push). `dbt test`: 23 tests (27 = `dbt build`: 4 models + 23 tests). CI also validates the Dagster definitions, the Prometheus alert rules (with unit tests) and the MLflow image build. |
| "Is it secured?" | Login with signed tokens; every route except `/health`, `/metrics`, `/auth/login` and static files needs a token. |
| "How does a change reach production?" | Push → GitHub Actions runs lint, tests, dbt, training on a fixture and the Docker builds. Only if all pass, a second job calls the Komodo API to redeploy the stack and waits for the result. A failing build never deploys. It retries on temporary registry/network errors and fails on real ones. |
| "Why Dagster?" | It gives the pipeline a graph, run history and logs, plus scheduling (nightly) and a sensor on the dataset version, on top of the same commands we run by hand. |
| "Where is the MLflow data?" | Metadata in PostgreSQL, model artifacts in the MinIO bucket `mlflow`, served through MLflow's artifact proxy. It replaced a read-only SQLite snapshot committed to git. |
| "What's not finished?" | (1) Alerts have no notification channel (no Alertmanager): they are visible in Prometheus/Grafana only. (2) The automatic Komodo restart after approval (`/models/redeploy`) depends on `KOMODO_URL/API_KEY/API_SECRET/STACK`; the promotion in MLflow always works. (3) The registry restarted empty when we moved MLflow to PostgreSQL (the earlier v1/v2 history was not migrated; the new v1 has the same PR-AUC, 0.8444). Say this honestly if asked. |

---

## 5. Things NOT to do live

- Don't click **Approuver** on a weak candidate.
- Don't press **Relancer** in Runs or **Lancer le pipeline complet** "just to see": only one job runs at a time, and it modifies shared state.
- Don't launch a job from Dagster's Launchpad while another run is going: the pipeline steps queue behind each other (file lock), so it will look stuck.
- Don't toggle the schedule or the sensor in Dagster's **Automation** page: they are meant to stay on.
- Don't paste dashboard credentials on screen. (Grafana and MinIO still have default logins, so don't show their login pages either.)
- Don't delete rows in bulk. (It is reversible through Versions, but it's an unnecessary risk.)
- Don't run `simulate` more than once: each run appends up to 5 000 rows to the dataset.
- Don't push to `main` right before or during the demo: it redeploys the stack and the containers restart for a minute or two.

---

## 6. Known caveats

**Registry and served model.** The MLflow registry now lives in PostgreSQL, so it **survives redeploys and container recreation** (the old
`mlflow.db` inside the platform container no longer matters). It started empty on 2026-09-22 when MLflow moved to PostgreSQL. The first
retraining from the dashboard then registered **v1 in Staging** (RandomForest, PR-AUC **0.8444**, 23/23 dbt tests passed): the platform
runs with auto-promote *off*, so a human has to approve it. **Nothing is in Production yet.**

- **Before demoing, approve v1 once**: dashboard → Pipeline (candidate vs. Production panel) → **Approuver**. This is the one case where
  approving is right: v1 has the same PR-AUC as the model the scoring API already serves (fixed seed, same data), and Production is
  empty. It promotes v1 in MLflow, exports `model.pkl` and commits it with the bot identity. Then confirm on `:4602/#/models` that v1 is
  **Production**, and write down its PR-AUC (0.8444) for step 5.
- **The scoring API loads `model.pkl` at startup.** After a promotion it keeps serving the previous model until it restarts. The approval
  flow asks Komodo to restart it (only if `KOMODO_URL/API_KEY/API_SECRET/STACK` are set on `platform-api`; otherwise the panel says
  "skipped"). If it was skipped, restart the `api` service in Komodo (Stack → Services → `api` → Restart) and check that `:4601/health`
  reports the same model version as MLflow.
- **During the demo, a new candidate will have about the same PR-AUC**, because training is deterministic. The gate only promotes a
  *strictly better* model, and promotion needs an approval anyway: reject it.

**Deploys can fail on network errors.** The Komodo server is shared, and its access to image registries sometimes times out. Komodo
stops before replacing any container, so the running stack is unaffected; the CI deploy job retries a few times. If it still fails, use
**Re-run failed jobs** in GitHub Actions. Do this well before the demo, not during it.

**"Unhealthy" in Komodo.** The stack shows UNHEALTHY because the one-shot setup container (`minio-init`) has exited. It is expected; all
8 long-running services should be RUNNING.

---

## 7. Cleanup after the demo (2 min)

1. **Versions du dataset** → restore the SHA you wrote down in the pre-flight checklist (rollback creates a new commit; nothing is lost).
2. Confirm the dataset is back to **284 807** rows (Pipeline or Transactions KPI).
3. `:4602/#/models`: the Production version you noted must still be **Production**. Candidate rejected (or archived).
4. `:4604/alerts`: after the rollback the drift alert should return to **inactive** within a couple of minutes.
5. Optional: `curl http://exp.s3.fsbm.ma:4601/health` → `model_version` should match the Production version.

---

## 8. Fallback plan (if the network or Komodo fails)

1. **Screenshots** in `../fraud-detection-mlops_private/screenshots/platform_ui/` (`report_figs/` = cropped versions). Walk the same
   story in the same order. Have them in a folder that opens in one click. *(These predate Dagster's UI, the drift dashboard and the alerts:
   take fresh screenshots of `:4608`, Grafana "Dérive & pipeline" and `:4604/alerts` and add them.)*
2. **Screen recording**: record a full clean run the day before with OBS or `Ctrl+Alt+Shift+R` (GNOME), with narration.
3. **Local instance** (only if you have time to prepare):
   ```bash
   cd platform_ui && npm install && npm run build
   cd .. && PLATFORM_USERS="demo:demo" PLATFORM_SECRET=x uvicorn platform_api.main:app --port 8000
   # http://localhost:8000
   # optional, the pipeline UI + schedule/sensor: dagster dev -f orchestration_dagster/fraud_dagster/job.py  (http://localhost:3000)
   ```
   It needs `data/raw/creditcard.csv` (`dvc pull`) and a working DVC remote, otherwise saving a version will fail. Without
   `MLFLOW_TRACKING_URI` the local instance uses its own SQLite registry, not the server's. The local `fraud-platform-api` Docker image
   on your laptop is **stale** (image of 09-18): rebuild it or don't use it.
4. Say it out loud: "the server is unreachable from here, here is the same flow recorded yesterday". Jurors accept that; they don't
   accept silence.

---

## 9. One-page cheat sheet (print this)

```
Login → Écosystème (all green? 9 containers) → Transactions (284 807)
      → edit 1 row → Enregistrer et versionner → hash
      → Versions → rollback (new commit)
      → Pipeline: simulate 3000 / Forte → Dérive: red banner   (alert starts: wait 1-2 min)
      → Ré-entraîner → steps → DAGSTER :4608 Runs → candidate vs Prod → REJETER
      → Grafana "Dérive & pipeline" (ALERTE) → Prometheus :4604/alerts (firing) → MLflow / Swagger /predict
Cleanup: Versions → restore noted SHA → 284 807 rows, noted Production version, alert back to inactive
Never: Approuver a weak model · Relancer · 2nd simulate · push to main during the demo
```
