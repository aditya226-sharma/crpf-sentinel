# CyberRakshak

A Security Information and Event Management (SIEM) platform for Central
Reserve Police Force (CRPF) units — submitted for **Smart India Hackathon
(SIH)**. The system ingests Windows Event Logs from endpoint agents, normalizes
them, runs correlation + MITRE ATT&CK–mapped detection rules, and surfaces
alerts in a live React dashboard with role-based access control.

> **Live deployment.** The platform is deployed for live monitoring; data comes
> only from registered agents shipping real Windows Event Logs. No synthetic
> data is generated at runtime.

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
└────────────┘                          │  Recharts · live event feed  │
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
5. **Parse & Normalize** — `backend/app/parsers/` → `backend/app/normalization/`
   extract host, user, source IP, process, command line, etc.
6. **Detect** — `backend/app/detection/` runs enabled rules (event filters,
   conditions, correlation windows) and IOC matches
   (`detection/ioc.py`) against the IOC library, raising alerts with risk
   scores and MITRE mapping.
7. **Notify** — alerts and events stream over Server-Sent Events to the
   frontend (`/api/stream/live`) and become dashboard notifications.
8. **Investigate** — open alerts can be grouped into incidents
   (`/incidents`) with a triage → investigate → escalate → resolve → close
   workflow, linked alert/event timelines and investigation notes.

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

# 2) Frontend
cd frontend
npm install
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

1. `make seed`, then open `http://localhost:3000/dashboard`.
2. Register a real agent (**Agents** → **Register**) — the UI returns an API
   token — and run the Windows collector on a monitored endpoint:
   `make agent AGENT_API_TOKEN=<token>`.
3. Watch the **Live Events** feed populate as the agent ships real Windows
   Event Logs (Security/System/Application channels).
4. Triage alerts in **Alerts**, correlate with **Logs**, and export **Reports**.
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
| `SEED_DEMO_DATA`          | `false`                  | seed synthetic units/agents/logs |
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

---

## Scaling notes

- **Stateless backend** — multiple uvicorn workers behind a load balancer;
  detection correlation uses the DB with bounded time windows.
- **Agent spooling** — the on-disk JSONL spool absorbs disconnects; ingests
  are batched (≤2000 events) and rate-limited (`RATE_LIMIT_INGEST_PER_MINUTE`).
- **Live feed** — SSE fan-out in `backend/app/websocket/` for real-time alerts;
  swap to Redis pub/sub for multi-worker deploys.
- **Postgres** — `docker compose up -d` runs Postgres + backend + frontend;
  swap `DATABASE_URL` for a managed instance.

## Project layout

```
agent/            # endpoint collector (Windows Event Log → HTTPS ingest)
  collector/      #   win32evtlog reader + simulator
  parser/         #   normalization to IngestItem
  spool/          #   persistent offline JSONL buffer
  transport/      #   batched ingest + heartbeat (retry/backoff)
  config/         #   settings + agent.yaml
backend/          # FastAPI SIEM engine
  app/models/     #   units, agents, logs, events, rules, alerts,
                  #   incidents, iocs, audit, notifications
  app/detection/  #   rule engine, correlation, IOC matching, MITRE map
  app/api/routes/ #   auth, logs, alerts, incidents, ioc, mitre,
                  #   analytics, assets, search, agents, units, users,
                  #   rules, reports, audit, stats, stream
  app/seed/       #   roles, units, rules, SOC seed (+ demo mode)
frontend/         # Next.js 15 dashboard
  app/(dashboard) #   dashboard, live-events, logs, alerts, incidents,
                  #   rules, threat-intel, ioc-library, mitre, correlations,
                  #   search, threat-analytics, assets, units, agents,
                  #   users, reports, audit-logs, settings
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
