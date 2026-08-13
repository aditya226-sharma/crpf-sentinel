# CyberRakshak — How the Web Application Works

A deep-dive technical reference for **CyberRakshak**, a Security Information
and Event Management (SIEM) platform for Central Reserve Police Force (CRPF)
units. This document explains how the web application is built and how it works
end to end.

> **Live deployment.** Data comes only from registered agents shipping real
> Windows Event Logs; no synthetic data is generated at runtime.

---

## 1. High-level architecture

```
┌─────────────────┐  HTTPS (x-agent-token)   ┌───────────────────────────────┐
│   agent/        │ ──── POST /api/logs/     │           backend/            │
│  Windows Event  │       /ingest            │  FastAPI · SQLAlchemy (ORM)   │
│  collector      │ ◄──── 200 {accepted,     │                               │
│  (pywin32 /     │        parsed, alerts}   │  parse → normalize → detect   │
│   simulator)    │       + heartbeats       │  (rules, correlation, IOC)    │
└─────────────────┘                          │  SSE  /api/stream/live        │
                                            └──────────────┬────────────────┘
                                                          │ REST + SSE
                                            ┌──────────────▼────────────────┐
                                            │          frontend/            │
                                            │  Next.js 15 · React 19        │
                                            │  TanStack Query · Recharts    │
                                            │  live event feed (SSE)        │
                                            └───────────────────────────────┘
```

Three components:

| Component | Role | Stack |
|-----------|------|-------|
| `agent/` | Endpoint collector on a Windows host | Python, pywin32, requests, spool (JSONL) |
| `backend/` | SIEM engine (parse, normalize, detect, alert) | FastAPI, SQLAlchemy, SQLite/Postgres, PyJWT, SSE |
| `frontend/` | Analyst dashboard | Next.js 15 (App Router), React 19, TanStack Query, Tailwind |

---

## 2. End-to-end data flow

One event from an endpoint agent to a live dashboard alert:

1. **Collect** — `agent/collector/windows.py` reads Security/System/Application
   channels via the Windows Event Log API (`win32evtlog`). On non-Windows
   machines a `SimulatedEventReader` emits realistic synthetic events.
2. **Normalize (agent)** — `agent/parser/windows.py` maps raw records into a
   compact `IngestItem` shape (`event_id`, `provider`, `computer`,
   `time_created`, `user`, `data`, optional `raw_xml`).
3. **Buffer** — `agent/spool/spool.py` appends events to a local JSONL queue so
   nothing is lost while the server is unreachable.
4. **Ship** — `agent/transport/api.py` drains the spool in batches (≤ 2000) to
   `POST /api/logs/ingest` with `x-agent-token` auth, retrying with exponential
   backoff; periodic heartbeats keep the agent marked `online`.
5. **Parse (backend)** — `backend/app/parsers/windows.py` parses raw XML, JSON
   text, or a dict (both the nested Windows layout and the flat collector
   layout) into a `ParsedEvent`.
6. **Normalize (backend)** — `backend/app/normalization/engine.py` converts the
   parsed event into a common schema: category/action/severity (e.g.
   `4624 → authentication / login_success / low`), cleans IPs and usernames,
   parses timestamps.
7. **Detect** — `backend/app/detection/` evaluates every **enabled rule** stored
   in the database against the event:
   - *Stateless signature* matches (`detection/matcher.py`)
   - *Count correlation* — N matching events within a time window, grouped by a
     correlation key (`detection/correlation.py`)
   - *Sequence correlation* — e.g. ≥5 failed logons (4625) followed by a
     success (4624) within the window
   - *IOC matching* — IP/domain/hash/URL/command indicators
     (`detection/ioc.py`)
8. **Store** — a `Log` (raw payload) and a `NormalizedEvent` are written to the
   database. Matches create/update `Alert` rows with a transparent **risk score**
   and MITRE ATT&CK mapping; open alerts are deduplicated by
   `rule_id + correlation_key`.
9. **Notify** — alerts publish to **Server-Sent Events** at
   `/api/stream/live` (unit-scoped fan-out) and in-app `Notification` rows are
   created for users who can see the alert's unit.
10. **Investigate** — analysts group alerts into **incidents** with a
    triage → investigate → escalate → resolve → close workflow, linked event
    timelines, and notes.

---

## 3. Backend internals

### 3.1 Application startup (`app/main.py`)

- Creates the FastAPI app; `/docs`, `/redoc`, `/openapi.json` are only exposed
  when `APP_ENV != "production"`.
- CORS from `BACKEND_CORS_ORIGINS` (default `http://localhost:3000`).
- Security headers middleware (`X-Frame-Options: DENY`, `nosniff`, etc.; HSTS
  only in production).
- Central error envelope handler: `{"success": false, "error": {"code", "message"}}`.
- On startup it creates tables and seeds **roles + admin + rules + units**
  (`seed_all`). No events, alerts or incidents are fabricated; data accumulates
  only from registered agents ingesting real Windows Event Logs. With
  `SEED_DEMO_DATA=true` the startup additionally seeds synthetic units, agents,
  users, ~10k events, IOCs and incidents for evaluation.

### 3.2 Configuration (`app/core/config.py`)

Environment-driven (`backend/.env`). Key settings: `DATABASE_URL` (SQLite or
Postgres), `JWT_SECRET`, `APP_ENV`, `BACKEND_CORS_ORIGINS`, `TRUST_PROXY`,
rate limits (login/ingest/general), `SEED_*` admin credentials. A placeholder
`JWT_SECRET` is auto-replaced with a random secret in development and rejected
in production.

### 3.3 Auth & RBAC (`app/core/deps.py`, `app/core/security.py`)

- **Users:** JWT (HS256) via `Authorization: Bearer`; passwords hashed with
  bcrypt. Login is rate-limited per IP + username.
- **Agents:** each agent stores a **sha256 hash** of its secret token; the
  plaintext token is shown only once at registration. Requests authenticate via
  the `x-agent-token` header; revoked/disabled agents are rejected.
- **Roles & permissions:** three roles (super_admin, security_expert,
  unit_admin) mapped to a flat permission list (e.g. `alerts.manage`,
  `rules.view`). Enforced per-endpoint via `require_permission(...)`.
- **Unit scoping:** `unit_admin` sees only rows whose `unit_id` matches their
  own unit; global roles see everything. Applied everywhere (list queries, SSE
  stream, notifications).

### 3.4 Database schema

SQLAlchemy ORM over SQLite (dev) or PostgreSQL (deploy). Tables:

| Table | Purpose |
|-------|---------|
| `units` | CRPF geographic units (Delhi, Gujarat, …) |
| `users`, `roles` | Operators + RBAC permissions (JSON) |
| `agents` | Endpoint collectors; `auth_token_hash`, `is_enabled`, telemetry |
| `logs` | Raw received payloads |
| `normalized_events` | Normalized detection subjects (the core table) |
| `detection_rules` | Editable rules: event IDs, conditions, correlation, MITRE |
| `alerts`, `alert_events` | Alerts + join to triggering events |
| `incidents`, `incident_alerts`, `incident_notes` | Case management |
| `ioc_entries` | Threat-intel indicators |
| `audit_logs` | Admin/security actions |
| `notifications` | In-app alerts per user |

### 3.5 API routes (mounted under `/api`)

| Prefix | Purpose |
|--------|---------|
| `/auth` | login, me, logout, password change |
| `/health`, `/stats` | liveness + platform counters |
| `/dashboard/*` | KPI summary, timeline, severity, live events, active threats, unit overview |
| `/logs` | event list/detail/related + `POST /logs/ingest` (agent-token auth) |
| `/alerts` | list, detail, status transitions, linked events |
| `/incidents` | create/update, link alerts, notes, event timeline |
| `/rules` | CRUD + dry-run test + stats/matches + `/signatures` (MITRE grouped) |
| `/ioc` | indicator library CRUD |
| `/mitre` | ATT&CK technique coverage |
| `/analytics` | top IPs/users/hosts/rules, threat activity |
| `/assets` | host inventory with computed risk |
| `/search` | global search across all entities (unit-scoped) |
| `/agents` | register (returns token once), list, update, revoke, heartbeat |
| `/units`, `/users` | management (guards protect last super_admin) |
| `/audit-logs`, `/notifications` | audit trail + in-app notifications |
| `/reports` | daily/weekly/unit/alerts/rules as CSV or JSON |
| `/stream/live` | **SSE live feed** (events + alerts) |

### 3.6 Detection engine

Rules are stored in the DB (seeded from `detection/rules.py` built-ins) and
re-read on every event, so no logic is hardcoded in the hot path. On a match
the engine computes a risk score (base severity + repeated-auth bonus +
privileged account + public IP + correlated success), creates or updates an
alert, notifies visible users, links the triggering event, and publishes an
SSE `alert` frame.

### 3.7 SSE live feed (`app/websocket/stream.py`)

Despite the package name this is Server-Sent Events, not WebSockets. A
module-level subscriber list holds `(asyncio.Queue, allowed_unit_ids)` pairs.
`publish(kind, payload)` fans out to every subscriber whose unit scope matches
the payload's `unit_id` (None = global). `GET /api/stream/live` authenticates
the JWT (header or `?token=`), computes the user's unit scope, and returns a
`text/event-stream` streaming response.

---

## 4. Frontend internals

### 4.1 Stack & model

Next.js 15 App Router + React 19 + TypeScript. The app is effectively a
**fully client-side SPA** — every page is a `"use client"` component; all data
is fetched on the client via TanStack Query against `NEXT_PUBLIC_API_URL`
(default `http://localhost:8000`). The only server-rendered pieces are the
root layout and the `/` → `/dashboard` redirect.

### 4.2 Route tree

- `/(auth)/login` — sign-in page.
- `/(dashboard)` — protected group with an `AppShell` (sidebar + topbar):
  `/dashboard`, `/live-events`, `/logs`, `/alerts`, `/incidents`, `/search`,
  `/units`, `/agents`, `/assets`, `/rules`, `/threat-intel`,
  `/ioc-library`, `/mitre`, `/threat-analytics`, `/risk-overview`,
  `/correlations`, `/reports`, `/users`, `/audit-logs`, `/settings`.

### 4.3 API client (`lib/api.ts`)

A typed fetch wrapper: attaches `Authorization: Bearer <token>`, parses the
backend error envelope into `ApiError`, and handles 204/JSON/text responses.
Tokens are stored in `localStorage` (remember me) or `sessionStorage`.

### 4.4 Authentication flow

Login → `POST /api/auth/login` → stores token + user → `AuthProvider` hydrates
the profile via `/api/auth/me` on load. Route protection is client-side in the
`(dashboard)/layout.tsx` guard (redirects to `/login`). Nav items and actions
are filtered by `hasPermission()/can()` against `user.role.permissions`.

### 4.5 Live feed (`hooks/use-live-stream.tsx`)

A custom **fetch-based SSE reader** (not `EventSource`): opens
`GET /api/stream/live` with an `AbortController`, reads the body via a
`ReadableStream`, splits frames on `\n\n`, parses `data:` lines as JSON
`{kind: "event"|"alert", data}`, and keeps a capped 200-event ring buffer.
It auto-reconnects with exponential backoff and drives the connection badge
(LIVE / CONNECTING / RECONNECTING / OFFLINE) in the top bar.

---

## 5. Security model summary

| Concern | Mechanism |
|---------|-----------|
| User auth | JWT (HS256), bcrypt password hashes, rate-limited login |
| Agent auth | `x-agent-token` header vs stored sha256 hash; token shown once |
| Authorization | RBAC permissions enforced server-side per endpoint |
| Row-level access | Unit scoping: unit_admin limited to their unit |
| Live stream | SSE filtered by the caller's unit scope |
| Hardening | Security headers, HSTS in production, docs disabled in production, `TRUST_PROXY` gating `X-Forwarded-For` |
| Secrets | `.env` files git-ignored; placeholder `JWT_SECRET` rejected in production |

---

## 6. Deployment notes

- **Local:** `make backend` + `make frontend` (SQLite) — or
  `make up` (Docker Compose: Postgres + backend + seed + frontend).
- **Compose** starts Postgres, backend, a one-shot `seed` service
  (`python -m app.seed.seed_all`), and the frontend (built with
  `NEXT_PUBLIC_API_URL` baked in).
- **Production:** set `APP_ENV=production`, `TRUST_PROXY=true`, a strong
  `JWT_SECRET`, and CORS to your real origin; put Caddy/Nginx in front for
  HTTPS. The backend runs one uvicorn worker — the SSE fan-out and rate
  limiter are in-memory per process, so multi-worker would require Redis
  pub/sub (see `README.md` "Scaling notes").

---

## 7. Bootstrapped credentials

| Role | Username | Password |
|------|----------|----------|
| Super admin | `admin` | `Sentinel@123` |

> In production, override `SEED_ADMIN_PASSWORD` — do not keep the default.

Runbook: open `/dashboard` → register real agents (**Agents** → **Register**,
each returns a one-time API token) → install/run the Windows collector on
endpoints (`agent/`) → watch Live Events as real Windows Event Logs stream in →
triage alerts → group into incidents → export reports.

> Live platform — data is produced only by registered agents shipping real
> Windows Event Logs.
