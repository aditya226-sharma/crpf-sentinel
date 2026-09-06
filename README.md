# CyberRakshak

A Security Information and Event Management (SIEM) platform for Central
Reserve Police Force (CRPF) units — submitted for **Smart India Hackathon
(SIH)**. A universal log pre-processing framework (single dispatch point:
`ParserRegistry`/`BaseParser`) powers two independent workspaces:

- **Log Intelligence** — Windows Event Logs, Syslog/CEF, NetFlow and IPsec
  VPN events are parsed, normalized, correlated, and MITRE ATT&CK–mapped into
  alerts, incidents and risk scores with a live React dashboard and
  role-based access control.
- **Criminal Intelligence** — an entity/relationship graph over case records
  (persons, phones, vehicles, accounts, locations, cases) with network map,
  community detection, hub analysis and shortest-path search.

> **Live deployment.** The platform is deployed for live monitoring; log data
> comes only from registered agents shipping real Windows Event Logs. The
> Criminal Intelligence workspace is populated with **synthetic case records**
> (fabricated names, numbers, vehicle and bank identifiers) that are generated
> only when `SEED_DEMO_DATA=true` and are clearly labelled as demo data in the
> UI. No synthetic security-event data is generated at runtime unless an agent
> is run in `--simulate` mode.

---

## Architecture

```
┌────────────┐  HTTPS (x-agent-token)   ┌────────────────────────────┐
│  agent/    │ ──── POST /api/logs/     │          backend/          │
│  Windows   │      /ingest + heartbeat │  FastAPI · SQLAlchemy       │
│  collector │ ◄──── 200 {accepted,     │                            │
│  (pywin32  │        parsed, alerts…}  │  parse → normalize → detect │
│  /sim)     │                          │  (correlation, MITRE)      │
└────────────┘                          │  SSE /api/stream/live       │
        ▲ local JSONL spool              └─────────────┬──────────────┘
        │ (survives outages)                          │
┌────────────┐                          ┌─────────────▼──────────────┐
│  agent     │                          │          frontend/          │
│  spool     │                          │  Next.js 15 · TanStack Query│
└────────────┘                          │  Log dashboard (/dashboard) │
                                        │  Criminal graph (/criminal) │
                                        └────────────────────────────┘
```

### Flow

1. **Collect** — `agent/collector/windows.py` reads Security/System/Application
   channels via the native Event Log API (`win32evtlog`). On non-Windows dev
   boxes a simulated reader emits realistic synthetic events.
2. **Normalize** — `agent/parser/windows.py` maps raw records (XML/dict) into a
   compact `IngestItem` (event_id, provider, host, user, data, raw_xml).
3. **Buffer** — `agent/spool/spool.py` persists normalized events as JSONL so
   nothing is lost while the server is unreachable.
4. **Ship** — `agent/transport/api.py` drains the spool in `max_batch` chunks
   to `POST /api/logs/ingest` (auth: `x-agent-token`), retrying with
   exponential backoff; periodic heartbeats keep the agent `online`.
5. **Parse & Normalize** — every format resolves through
   `ParserRegistry`/`BaseParser` (`backend/app/parsers/`) into one common
   event schema via the per-format YAML catalogs
   (`backend/app/config/formats/*.yaml`). Formats: `windows`, `syslog`,
   `netflow`, `ipsec` and `case_record`. Adding a source = one parser + one
   YAML file; the engine never changes.
6. **Detect** — `backend/app/detection/` runs enabled rules (event filters,
   conditions, correlation windows) and IOC matches
   (`detection/ioc.py`) against the IOC library, raising alerts with risk
   scores and MITRE mapping. Dedicated analyzers raise `RULE-NET-001`
   (NetFlow traffic anomalies) and `RULE-VPN-001` (weak IPsec VPN configs)
   into the same shared Alert model.
7. **Graph** — `case_record` events flow through `backend/app/graph/`
   (extraction → indexer → store) into a per—entity graph. The default store is
   relational (`GraphNode`/`GraphEdge`); an optional Neo4j store activates with
   `GRAPH_BACKEND=neo4j` (see `docker-compose.yml`).
8. **Query** — `POST /api/query` is a template-first, explainable query bar
   (open alerts, failed logons, network bursts, graph paths) with confidence +
   provenance; no generative inference.
9. **Notify & Investigate** — alerts and events stream over Server-Sent Events
   to the frontend (`/api/stream/live`) and become dashboard notifications.
   Open alerts can be grouped into incidents (`/incidents`) with a
   triage → investigate → escalate → resolve → close workflow, linked
   alert/event timelines and investigation notes.

---

## Quick start (local)

Requires Python 3.10+ and Node 18+.

```bash
# 1) Backend (SQLite by default)
cd backend
cp .env.example .env
pip install -r requirements.txt
python -m app.seed.seed_all        # tables + roles + admin + rules + units
uvicorn app.main:app --reload --port 8000

# optional — run the pipeline smoke suite (isolated SQLite DB)
pip install -r requirements-dev.txt
python -m pytest tests

# 2) Frontend
cd frontend
npm ci
npm run dev                        # http://localhost:3000

# 3) Agent (simulated events; works on any OS)
cd agent
pip install -r requirements.txt
# register an agent in the web UI (Agents → Register) and copy its token:
CYBERRAKSHAK_API_TOKEN=<token> python -m main --simulate
```

Or with the Makefile:

```bash
make backend      # uvicorn on :8000
make frontend     # Next.js on :3000
make seed         # seed roles + admin + rules + units
make agent        # simulated agent (needs AGENT_API_TOKEN=...)
```

### Bootstrapped credentials

| Role         | Username | Password        |
|--------------|----------|-----------------|
| Super admin  | `admin`  | `Sentinel@123`  |

> In production, set `SEED_ADMIN_PASSWORD` to a strong value — do not keep the
> default.

### Live runbook

1. `make seed`, then open `http://localhost:3000/` and pick a dashboard (login
   also lands you on `Role.default_dashboard`).
2. Register a real agent (**Agents** → **Register**) — the UI returns an API
   token — and run the Windows collector on a monitored endpoint:
   `make agent AGENT_API_TOKEN=<token>`.
3. Watch the **Live Events** feed populate as the agent ships real Windows
   Event Logs (Security/System/Application channels).
4. Triage alerts in **Alerts**, correlate with **Logs**, and export **Reports**.
5. To see the Criminal Intelligence workspace locally, seed the synthetic
   case corpus: `SEED_DEMO_DATA=true python -m app.seed.seed_all`, then open
   **/criminal**. Try the **Ask the Corpus** bar, e.g.
   *"network scan in last hour"* or *"open high alerts"*.
5. Open **Incidents** (`/incidents`) to group related alerts and drive the
   triage → investigate → escalate → resolve → close workflow.
6. Open **IOC Library** (`/ioc-library`) to add indicators matched against
   inbound events during detection; **MITRE ATT&CK** (`/mitre`) shows
   technique coverage.
7. Use **Search** (`/search`) for a global lookup across events, alerts,
   incidents, rules, IOCs, agents and units.

---

## Environment variables

Backend (`.env`, see `backend/.env.example`):

| Variable                  | Default                  | Notes                          |
|---------------------------|--------------------------|--------------------------------|
| `DATABASE_URL`            | Postgres (docker)        | use `sqlite:///./sentinel.db`  |
| `JWT_SECRET`              | change-me…               | long random secret             |
| `SEED_DEMO_DATA`          | `false`                  | seed synthetic units/agents/logs + ~180 case records for /criminal |
| `SEED_ADMIN_USERNAME`     | `admin`                  | seeded super-admin             |
| `SEED_ADMIN_PASSWORD`     | `Sentinel@123`           | seeded password                |

Agent (`CYBERRAKSHAK_*` env vars override `agent/config/agent.yaml`):

| Variable                    | Default                | Notes                          |
|-----------------------------|------------------------|--------------------------------|
| `CYBERRAKSHAK_SERVER_URL`   | `http://localhost:8000`| backend base URL               |
| `CYBERRAKSHAK_API_TOKEN`    | _(empty)_              | from agent registration (x-agent-token) |
| `CYBERRAKSHAK_AGENT_ID`     | `WIN-AGT-0001`         | must match the registered agent|
| `CYBERRAKSHAK_SIMULATE`     | `true`                 | fake events for dev/demo       |
| `CYBERRAKSHAK_CHANNELS`     | Security,System,App    | Windows channels to read       |
| `CYBERRAKSHAK_POLL_INTERVAL_SECONDS` | `5`             | collect/flush cadence          |
| `CYBERRAKSHAK_MAX_BATCH`    | `200`                  | events per ingest request (≤2000) |
| `CYBERRAKSHAK_SPOOL_DIR`    | `spool`                | offline JSONL buffer           |

---

## RBAC

Permissions are enforced server-side in `backend/app/core/deps.py`.

| Role             | Can do                                                     |
|------------------|------------------------------------------------------------|
| `super_admin`    | everything incl. users, units, settings, audit, IOCs       |
| `security_expert`| logs, alerts (manage), rules (manage), incidents, IOC view, agents view, reports |
| `unit_admin`     | dashboard, logs, alerts, agents/units view, reports (unit-scoped) |
| `crime_analyst`  | criminal graph (`/criminal`), case-record feed, queries   |

Every role carries a `default_dashboard` (`log` or `criminal`); the login page
lands the user on their workspace, and `/` lets them switch at any time.

---

## Scaling notes

- **Stateless backend** — multiple uvicorn workers behind a load balancer;
  detection correlation uses the DB with bounded time windows.
- **Agent spooling** — the on-disk JSONL spool absorbs disconnects; ingests
  are batched (≤2000 events) and rate-limited (`RATE_LIMIT_INGEST_PER_MINUTE`).
- **Live feed** — SSE fan-out in `backend/app/websocket/` for real-time alerts;
  swap to Redis pub/sub for multi-worker deploys.
- **Postgres** — `docker compose up -d` runs Postgres + optional Neo4j;
  swap `DATABASE_URL` for a managed instance.
- **Graph backend** — `GRAPH_BACKEND=relational` (default, zero deps) uses
  `GraphNode`/`GraphEdge` tables; set `GRAPH_BACKEND=neo4j` + `NEO4J_URI/USER/PASSWORD`
  to use the optional Neo4j store via the same `GraphStore` interface.
- **Schema migrations** — no Alembic; `init_database()` runs `ensure_columns()`
  at startup and idempotently ALTERs any post-launch columns (e.g.
  `roles.default_dashboard`).

## Project layout

```
agent/            # endpoint collector (Windows Event Log → HTTPS ingest)
  collector/      #   win32evtlog reader + simulator
  parser/         #   normalization to IngestItem
  spool/          #   persistent offline JSONL buffer
  transport/      #   batched ingest + heartbeat (retry/backoff)
  config/         #   settings + agent.yaml
backend/          # FastAPI SIEM engine
  app/parsers/    #   universal parser registry (windows, syslog, netflow,
                  #   ipsec, case_record) — one dispatch point
  app/config/formats/  # per-format YAML catalogs
  app/normalization/   # common event schema (extractors + classifiers)
  app/models/     #   units, agents, logs, events, rules, alerts,
                  #   incidents, iocs, audit, notifications, graph nodes
  app/detection/  #   rule engine, correlation, IOC matching, MITRE map,
                  #   NetFlow/VPN analyzers
  app/graph/      #   case-record extraction, indexer, store (relational/Neo4j)
  app/api/routes/ #   auth, logs, alerts, incidents, ioc, mitre,
                  #   analytics, assets, search, agents, units, users,
                  #   rules, reports, audit, stats, stream, graph, query
  app/seed/       #   roles, units, rules, SOC seed + case records (demo mode)
  app/database/   #   init_db (roles, ensure_columns post-launch migrations)
frontend/         # Next.js 15 dashboard
  app/(dashboard) #   picker (/), log dashboard, criminal graph (/criminal),
                  #   live-events, logs, alerts, incidents, rules,
                  #   threat-intel, ioc-library, mitre, correlations,
                  #   search, threat-analytics, assets, units, agents,
                  #   users, reports, audit-logs, settings
  components/layout  # sidebar/topbar retitle sections for the two workspaces
docker-compose.yml   # optional Postgres + Neo4j
```

## Deployment (Vercel)

The dashboard (`frontend/`) deploys as a static export from the `master`
branch. Vercel project settings used for the CI job:

| Setting | Value |
|---|---|
| Root Directory | `frontend` |
| Framework | Next.js |
| Output Directory | `out` |
| Production Branch | `master` |
| Env var `NEXT_PUBLIC_API_URL` | `https://cyberrakshak-api.onrender.com` |

`vercel.json` maps unknown paths (e.g. the removed `/demo` page) to a real
HTTP 404.

Push to `master` auto-deploys (Vercel GitHub app). One gotcha: the project's
**Root Directory** must be set to `frontend` in Vercel project settings —
without it the build runs from the repo root and fails with
`Couldn't find any pages or app directory`.

## CI/CD pipeline

| Stage | Where | Trigger | Gate |
|---|---|---|---|
| Continuous integration | GitHub Actions (`.github/workflows/ci.yml`) | push / PR | Backend: `compileall` + pipeline smoke tests (`pytest tests`) on an isolated SQLite DB. Frontend: `tsc --noEmit` + production `next build` (bakes `NEXT_PUBLIC_API_URL`) |
| Backend deploy | Render web service `cyberrakshak-api` | push to `master` (auto-deploy, `Auto Deploy: yes`) | `render.yaml` / service config; env vars incl. `DATABASE_URL`, `JWT_SECRET`, `SEED_ADMIN_PASSWORD` |
| Frontend deploy | Vercel project `cyberrakshak-frontend` | push to `master` | Root Directory `frontend`, static export to `out` |

Notes:

- The backend smoke suite is the source of truth for the data pipeline
  (seed → auth → agent registration → agent-token heartbeat → ingestion →
  persistence → scoped stats → dashboard aggregation). It never touches the
  production database — `tests/conftest.py` forces a throwaway SQLite URL
  before the app is imported.
- Dependency locks keep builds reproducible: `frontend/package-lock.json`
  (`npm ci`) and `backend/requirements*.txt` (pinned ranges).
- If a secret is ever needed in CI build stops, pass it via GitHub repository
  variables/secrets — never commit it. `NEXT_PUBLIC_API_URL` defaults to the
  live backend via the `vars.NEXT_PUBLIC_API_URL` repository variable.
- Runtime artifacts (`.env`, `*.db`, logs, event spools, agent live configs
  with tokens) are gitignored and never in the repository.
