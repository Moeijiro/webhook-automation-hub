# Webhook Automation Hub

A small automation tool with one job: take an incoming webhook, transform the payload, and
do something with it somewhere else — post to Discord, message a Telegram chat, or call
another HTTP API — then keep a log of every run.

```
POST /hooks/{token}  →  validate  →  render template  →  action adapter  →  execution log
```

It is deliberately not a Zapier clone. There is one trigger type, three actions, and an
adapter interface that makes the fourth one a single file.

---

## Why this project exists

Most "automation platform" demos stop at the happy path. The parts that decide whether a
tool like this is usable are the unglamorous ones, and they are what this repository is
built around:

- what happens when the destination returns a 502 (retry) versus a 400 (do not)
- where third-party credentials live, and who can read them back
- what stops a workflow from being pointed at `169.254.169.254` or `localhost:5432`
- what the caller sees while the action is still running
- what the operator sees afterwards, when someone asks "did that order notification fire?"

---

## Contents

- [Screenshots](#screenshots)
- [Architecture](#architecture)
- [Features](#features)
- [Tech stack](#tech-stack)
- [Installation](#installation)
- [Environment variables](#environment-variables)
- [Creating a workflow](#creating-a-workflow)
- [Webhook example](#webhook-example)
- [API keys](#api-keys)
- [API overview](#api-overview)
- [Security](#security)
- [Tests](#tests)
- [Project structure](#project-structure)
- [Future extensions](#future-extensions)

---

## Screenshots

| | |
|---|---|
| ![Dashboard](docs/screenshots/dashboard.png) | ![Workflow detail](docs/screenshots/workflow.png) |
| *Counts computed from your own rows* | *Webhook URL and a ready-to-run curl command* |
| ![Execution logs](docs/screenshots/logs.png) | ![API keys](docs/screenshots/api-keys.png) |
| *Every run, with payload and result* | *Keys shown once, stored as a digest* |

> Captured from the running stack. The executions in them are real runs against a local
> endpoint and against Discord (with an invalid webhook, which is why one row failed).

---

## Architecture

```mermaid
flowchart TD
    EXT["External service<br/>(shop, CI, monitoring)"] -->|"POST /hooks/{token}"| EP["Webhook endpoint"]

    subgraph API["FastAPI application"]
        EP --> V["Validate<br/>size · JSON · token · HMAC"]
        V --> ENG["Workflow engine<br/>background task · up to 3 attempts"]
        ENG --> AD["Action adapter"]
        MGMT["Management API<br/>session cookie or X-API-Key"]
    end

    AD -->|"webhook"| DISCORD["Discord"]
    AD -->|"Bot API"| TELEGRAM["Telegram"]
    AD -->|"any method"| HTTP["HTTP API"]

    ENG --> DB[("Database<br/>users · keys · workflows · executions")]
    MGMT --> DB
    DASH["Dashboard<br/>React + TypeScript"] --> MGMT
```

**Request lifecycle**

1. `POST /hooks/{token}` — the token is the credential; 32 bytes of entropy, unique per workflow.
2. Reject oversized bodies (`413`), non-JSON bodies (`422`), unknown tokens (`404`), disabled workflows (`409`).
3. If the workflow requires signing, verify `X-Hub-Signature-256` over the exact bytes received.
4. Write the `Execution` row with status `processing` and answer `202` with its id.
5. In the background: render the template, call the adapter, retry retryable failures with exponential backoff.
6. Store status, attempts, duration, the destination's answer, and the error if there was one.

---

## Features

**Authentication** — email and password, hashed with scrypt (parameters stored alongside the
digest). The session is a signed JWT in an HttpOnly cookie; the browser never holds a token
it could leak.

**API keys** — `whk_…` keys for scripts and CI, sent as `X-API-Key`. Only a SHA-256 digest is
stored; the raw key appears exactly once, in the response that created it. Keys can be
revoked and record their own `last_used_at`.

**Workflows** — name, trigger (`incoming_webhook`), action, configuration, enabled flag.
Each one owns a webhook URL and, optionally, a signing secret.

**Actions** — three adapters, each with its own validated configuration:

| Action | Configuration | Notes |
|---|---|---|
| `discord_webhook` | webhook URL, message template, optional username | URL must be a real Discord webhook |
| `telegram_message` | bot token, chat ID, message template, parse mode | token never leaves the server |
| `http_request` | method, URL, headers, body template | GET/POST/PUT/PATCH/DELETE only |

**Templating** — `{{order_id}}`, `{{customer.name}}`, `{{items.0.sku}}`. Dotted paths and
nothing else: no expressions to evaluate on untrusted input. Missing paths render empty and
are listed in the execution result, so a typo is visible instead of silent.

**Execution log** — status, attempts, duration, trigger payload and action result for every
run, filterable by workflow and status, with the payload expandable inline.

**Retries** — up to three attempts with exponential backoff, and only for failures where a
retry could help: timeouts, connection errors, `429` and `5xx`. A `400` is recorded once and
left alone.

---

## Tech stack

| Layer | Choice | Why |
|---|---|---|
| API | FastAPI + Pydantic v2 | typed models, OpenAPI for free, `BackgroundTasks` instead of a queue |
| ORM | SQLAlchemy 2.0 (typed) | SQLite by default, PostgreSQL by changing one URL |
| HTTP | httpx | one async client for every adapter, swappable transport in tests |
| Crypto | `cryptography` (Fernet + HKDF), PyJWT, `hashlib.scrypt` | encrypted credentials, signed sessions, hashed passwords |
| Dashboard | React 19 + TypeScript + Vite + Tailwind v4 | six small pages, no component library |
| Tests | pytest | 51 tests, none of which touch the network |

Nine runtime dependencies in total. There is no queue, no worker process and no container
orchestration, because at this size they would be decoration.

---

## Installation

Requirements: Python 3.11+, Node 18+.

```bash
git clone https://github.com/Moeijiro/webhook-automation-hub.git
cd webhook-automation-hub
cp .env.example backend/.env       # works as-is for local development
make install                       # venv + pip install + npm install
```

Run the two processes (each in its own terminal):

```bash
make api    # http://localhost:8000  (OpenAPI docs at /docs)
make web    # http://localhost:5173
```

Open <http://localhost:5173>, register an account, and create your first workflow.

**PostgreSQL** instead of SQLite — no code changes:

```env
DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/webhook_hub
```

---

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `ENVIRONMENT` | `development` | `production` enables the startup safety checks |
| `PUBLIC_BASE_URL` | `http://localhost:8000` | used to build the webhook URL shown in the UI |
| `FRONTEND_URL` | `http://localhost:5173` | CORS origin |
| `DATABASE_URL` | `sqlite:///./webhook_hub.db` | any SQLAlchemy URL |
| `SECRET_KEY` | dev placeholder | signs sessions, derives the credential-encryption key |
| `ACCESS_TOKEN_TTL_MINUTES` | `720` | session lifetime |
| `COOKIE_SECURE` / `COOKIE_SAMESITE` | `false` / `lax` | set `true` / `none` when the dashboard is on another domain over HTTPS |
| `ALLOW_REGISTRATION` | `true` | turn off once your own account exists |
| `MAX_PAYLOAD_BYTES` | `65536` | largest accepted webhook body |
| `ACTION_TIMEOUT_SECONDS` | `10` | timeout for one outbound call |
| `MAX_ATTEMPTS` | `3` | attempts per execution, including the first |
| `ALLOW_PRIVATE_NETWORK_TARGETS` | `false` | the SSRF guard; refused in production |

`.env` is git-ignored, `.env.example` is the template, and no secret is committed.

---

## Creating a workflow

In the dashboard: **Workflows → New workflow**, then pick an action and fill its fields.
Saving returns the webhook URL and a curl command you can paste straight into a terminal.

Or over the API:

```bash
curl -X POST http://localhost:8000/api/workflows \
  -H "X-API-Key: $WAH_KEY" -H "Content-Type: application/json" \
  -d '{
    "name": "Order created → Discord",
    "action_type": "discord_webhook",
    "config": {
      "webhook_url": "https://discord.com/api/webhooks/…",
      "message_template": "New order #{{order_id}}\nCustomer: {{customer}}\nAmount: ${{amount}}"
    },
    "enabled": true
  }'
```

---

## Webhook example

Given this payload:

```bash
curl -X POST http://localhost:8000/hooks/abc123… \
  -H 'Content-Type: application/json' \
  -d '{"order_id": 1024, "customer": "Alex", "amount": 49.99}'
```

the endpoint answers immediately:

```json
{"accepted": true, "execution_id": 7, "workflow": "Order created → Discord", "status": "processing"}
```

and the Discord channel receives:

```
New order #1024
Customer: Alex
Amount: $49.99
```

**Signed workflows.** If the workflow requires a signature, send an HMAC-SHA256 of the exact
body:

```bash
BODY='{"order_id":1024}'
SIG="sha256=$(printf '%s' "$BODY" | openssl dgst -sha256 -hmac "$SIGNING_SECRET" -r | cut -d' ' -f1)"
curl -X POST http://localhost:8000/hooks/abc123… \
  -H 'Content-Type: application/json' -H "X-Hub-Signature-256: $SIG" -d "$BODY"
```

---

## API keys

Create one under **API keys** in the dashboard, or with `POST /api/api-keys`. The raw value
is shown once:

```bash
curl http://localhost:8000/api/workflows -H "X-API-Key: whk_…"
```

Keys authenticate the management API only. The webhook endpoint uses its own per-workflow
token, so an integration that can trigger a workflow cannot list or edit your workflows.

---

## API overview

Interactive documentation: <http://localhost:8000/docs>.

| Method | Route | Auth | Notes |
|---|---|---|---|
| `POST` | `/api/auth/register` | — | disabled when `ALLOW_REGISTRATION=false` |
| `POST` | `/api/auth/login` | — | sets the session cookie |
| `POST` | `/api/auth/logout` | session | clears it |
| `GET` | `/api/auth/me` | session or key | current user |
| `GET` | `/api/actions` | session or key | action catalogue, generated from the adapters |
| `GET` | `/api/workflows` | session or key | your workflows |
| `POST` | `/api/workflows` | session or key | validates config, returns URL + curl |
| `GET` | `/api/workflows/{id}` | owner | detail, secrets redacted |
| `PATCH` | `/api/workflows/{id}` | owner | partial update |
| `DELETE` | `/api/workflows/{id}` | owner | removes the workflow and its executions |
| `GET` | `/api/workflows/{id}/logs` | owner | paged execution history |
| `GET` | `/api/executions` | session or key | across all workflows, filterable |
| `GET` | `/api/stats` | session or key | dashboard counts |
| `GET`/`POST` | `/api/api-keys` | session or key | list / create |
| `DELETE` | `/api/api-keys/{id}` | owner | revoke |
| `POST` | `/hooks/{token}` | workflow token (+ optional HMAC) | trigger |

Status codes are used as intended: `401` unauthenticated, `404` for objects the caller does
not own (never `403`, which would confirm they exist), `409` for a disabled workflow,
`413` for an oversized payload, `422` for validation failures, `429` when rate limited.

---

## Security

- **Passwords** are hashed with scrypt (N=2¹⁴, r=8, p=1) and a per-user salt; the parameters
  travel with the digest so they can be raised later without invalidating old hashes.
- **Sessions** are signed JWTs in HttpOnly cookies. The signing key and the credential
  encryption key are derived from `SECRET_KEY` through HKDF with different info labels, so
  they never share material.
- **API keys** are 256-bit random values stored as a SHA-256 digest. A slow KDF would buy
  nothing against that much entropy and would tax every request; the reasoning is in the
  code next to the decision.
- **Action credentials** (Discord webhook URLs, Telegram bot tokens, HTTP headers) are
  encrypted with Fernet before they are stored, and the API returns a redaction marker
  instead — there is no endpoint that can read them back.
- **SSRF guard**: every outbound URL is resolved and refused if it points at a private,
  loopback, link-local or reserved address; redirects are not followed, so a public URL
  cannot bounce a request into the private network.
- **Webhook signatures** are verified over the exact bytes received, before parsing, with a
  constant-time comparison.
- **Payload size** is capped before the body is parsed.
- **Credentials are never logged**: the Telegram token is part of the request URL, so the
  adapter reports the chat, never the URL.
- **Production refuses unsafe configuration**: a weak `SECRET_KEY` or a disabled SSRF guard
  stops the app from booting.
- Rate limits cover authentication (10/min per IP) and the webhook endpoint (120/min per
  token, so one noisy integration cannot throttle the others).

---

## Tests

```bash
make test        # or: cd backend && .venv/bin/python -m pytest
```

51 tests, with outbound HTTP replaced by a mock transport so nothing reaches the network:

- authentication: protected routes, password hashing, identical errors for wrong password
  and unknown account, tampered cookies
- webhook execution: template rendering, the execution row, disabled workflows, unknown
  tokens, non-JSON bodies, oversized payloads, HMAC signatures
- retries: a `502` is attempted three times, a `400` once, and a retry that succeeds is
  reported as a success
- API keys: shown once, stored hashed, usable instead of a session, revocable
- configuration: invalid Discord URLs, forbidden headers, bad JSON body templates, ownership
- templating and the SSRF guard as unit tests

---

## Project structure

```
backend/
  app/
    actions/           base.py · discord.py · telegram.py · http.py · registry.py
    api/
      deps.py          session cookie or API key → user → ownership
      routes/          auth · workflows · api_keys · hooks · dashboard · system
    core/              config · security · net (SSRF guard) · rate limiting
    db/                engine, session, declarative base
    models/            User · APIKey · Workflow · Execution
    schemas/           Pydantic request/response models
    services/          engine (retries) · templating · stats · http client
    main.py            middleware, error handlers, routers
  tests/               pytest suite
frontend/
  src/
    components/        AppShell · WorkflowForm · ExecutionTable · CodeBlock + ui/ primitives
    pages/             Login · Dashboard · Workflows · WorkflowDetail · Logs · ApiKeys
    lib/               API client, types, formatting
docs/screenshots/      README images
.env.example           every variable, documented
Makefile               install / api / web / test
```

Adding a fourth action means adding one file in `actions/` and one line in `registry.py`;
the config form, the catalogue endpoint and the secret handling follow from the adapter.

---

## Future extensions

Deliberately out of scope here, but the shape of the code leaves room for:

- **more adapters** — Slack, email, S3 upload; one module each
- **a durable queue** — swap `BackgroundTasks` for Redis/RQ when executions must survive a
  restart
- **scheduled triggers** — a second trigger type alongside `incoming_webhook`
- **filters and conditions** — run the action only when the payload matches a rule
- **replay** — re-run a stored execution's payload after fixing a configuration

---

## Licence

MIT — see [LICENSE](LICENSE).
