# Chatbox Support Automation

![Docker](https://img.shields.io/badge/Docker-2496ED?logo=docker&logoColor=white)
![Python](https://img.shields.io/badge/Python-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-61DAFB?logo=react&logoColor=black)
![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?logo=typescript&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-DC382D?logo=redis&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-003B57?logo=sqlite&logoColor=white)
![Multi--Tenant](https://img.shields.io/badge/Multi--Tenant-Supported-blueviolet)
![LLM Layer](https://img.shields.io/badge/LLM-Mock%20%2F%20OpenAI-green)

A Dockerized full-stack demo for deterministic, multi-tenant IT support automation.

Chatbox combines a FastAPI backend, React/Vite frontend, Redis session/state storage, and SQLite persistence for usage and tenant data. It demonstrates deterministic support workflows, email ingest automation, tenant-aware Jira-style payload previews, and an optional mock/OpenAI LLM classification layer.

The system is deterministic-first: core VPN troubleshooting, tenant routing, usage logging, and Jira preview generation work without AI. The default LLM provider is `mock`, so real OpenAI calls are not required.

## Key Features

- One-command Docker Compose startup for Redis, FastAPI, and React/Vite
- Deterministic VPN support workflow with structured escalation/handoff behavior
- Email ingest automation with idempotency, tenant routing, and activity logging
- Email demo scenarios for `VPN_ISSUE`, `PASSWORD_RESET`, and `EMAIL_ISSUE`
- Multi-tenant support with seeded demo tenants and frontend tenant creation
- Tenant-specific Jira label mapping UI backed by persistent tenant config
- Jira-style payload previews without creating real Jira tickets
- Redis-backed chat sessions, pending handoffs, and email processing state
- SQLite-backed usage tracking and tenant persistence
- Usage dashboard for tenant activity summaries, event-type breakdown, and intent breakdown
- Optional mock/OpenAI LLM-assisted classification with deterministic fallback
- No LLM billing, token accounting, or provider cost tracking is implemented

## Tech Stack

- Backend: Python, FastAPI, Pydantic, Uvicorn
- Frontend: React, TypeScript, Vite
- Runtime services: Docker Compose, Redis
- Persistence: SQLite for usage events and tenant registry
- Optional AI layer: mock provider by default, OpenAI provider optional

## Project Structure

```text
chatbox/
  docker-compose.yml

  backend/
    Dockerfile
    app/
      api/          FastAPI route handlers and chat orchestration
      email/        Email ingest, pending resolution, and processing logic
      flows/vpn/    Deterministic VPN workflow and NLP helpers
      jira/         Jira-style payload and label mapping helpers
      llm/          Mock/OpenAI classification layer
      storage/      Redis memory store and SQLite usage logging
      tenants/      Seeded demo tenants and SQLite tenant registry
    requirements.txt
    readme.md       Backend-focused README

  frontend/
    Dockerfile
    src/
      App.tsx       Demo UI for chat, email ingest, tenants, labels, and usage
      styles.css
    package.json
```

## Run with Docker Compose

From the repository root:

```powershell
docker compose up --build
```

Docker Compose starts:

- Redis
- FastAPI backend
- React/Vite frontend

Frontend:

```text
http://127.0.0.1:5173
```

Backend:

```text
http://127.0.0.1:8000
```

Swagger/docs:

```text
http://127.0.0.1:8000/docs
```

SQLite files are stored in the backend data volume. They are local runtime data and should not be committed.

## Demo Tenants

Fresh local/Docker runs seed useful demo tenants automatically:

```text
bank_demo
auto_demo
health_demo
fox_clothes_demo
candyshop_demo
hatifim_demo
```

Demo tenants include realistic Jira project keys, ownership components, default `it-support` labels, and tenant-specific label mappings. Additional tenants can be created from the frontend and are persisted in SQLite.

## Demo Workflow

1. Select a seeded or frontend-created tenant.
2. Run a chat VPN workflow or submit a sample email.
3. Review the detected intent, confidence, internal tags, handoff summary, and Jira-style payload preview.
4. Open Usage to inspect activity totals, breakdown by event type, and email intent breakdown.
5. Add a tenant or update tenant-specific Jira label mappings to see routing behavior change.

## Manual Local Development

### Backend

From the repository root:

```powershell
cd backend
.\env\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
redis-server
uvicorn app.main:app --reload
```

Backend URL:

```text
http://127.0.0.1:8000
```

API docs:

```text
http://127.0.0.1:8000/docs
```

### Frontend

In a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

Frontend URL:

```text
http://127.0.0.1:5173
```

The frontend uses `VITE_API_BASE_URL` when provided and defaults to:

```text
http://127.0.0.1:8000
```

## Minimal API Surface

The frontend exercises the main demo flows:

- `GET /health`
- `POST /api/chat`
- `POST /api/email/ingest`
- `GET /api/tenants`
- `POST /api/tenants`
- `GET/PATCH /api/tenants/{tenant_id}/labels`
- `GET /api/usage/summary`

See [backend/readme.md](backend/readme.md) or Swagger for deeper backend/API details.

## Current Status

This project is a deterministic-first portfolio/demo system focused on multi-tenant support automation architecture, configurable Jira-style routing, and optional LLM-assisted workflows.

The current full-stack implementation demonstrates chat support flows, email ingest automation, seeded and dynamic tenants, tenant-specific Jira label mappings, activity analytics, handoff summaries, and Jira-style payload previews.

The system does not create real Jira tickets. Instead, it generates structured payload previews designed to demonstrate integration architecture, tenant-aware routing, and deterministic workflow behavior.
