# Chatbox Support API

A deterministic-first FastAPI backend for multi-tenant IT support automation.

This project demonstrates how an internal support system can route chat and email requests, run structured troubleshooting workflows, generate Jira-style payload previews, track activity events, and optionally enrich classification with an LLM provider.

The backend is designed to work without AI. LLM support is optional, confidence-gated, and failure-safe. The default/demo LLM provider is `mock`, so real OpenAI calls are not required.

The system is intentionally designed so that core support workflows remain deterministic, auditable, and operational even when the LLM layer is disabled or unavailable.

---

## What This Project Demonstrates

- FastAPI backend architecture with clear router/service/storage boundaries
- Deterministic VPN troubleshooting automation
- Email ingest pipeline with idempotency and pending tenant resolution
- Redis-backed session, pending, and receipt storage
- SQLite-backed activity/audit tracking
- Multi-tenant routing and tenant-specific Jira label mapping
- Internal normalized tags separated from tenant-facing labels
- Optional mock/OpenAI LLM provider layer
- Safe fallback behavior when LLMs, Redis, or tenant data are unavailable
- Practical manual testing via Swagger UI, Thunder Client, or curl

---

## Architecture Overview

The application starts from `app/main.py`, where the FastAPI app is created, routers are registered, and startup tasks initialize SQLite usage tracking and the tenant registry.

```text
app/
  main.py                    FastAPI app, lifespan startup, router registration

  api/                       HTTP route layer
    chat_routes.py           Chat/session endpoints
    email_routes.py          Email ingest, resolve, reprocess, pending endpoints
    tenant_routes.py         Tenant list/upsert endpoints
    usage_routes.py          Usage/audit endpoints
    chat_controller.py       Chat orchestration
    intent_router.py         Intent routing
    vpn_handler.py           VPN flow integration and handoff handling

  flows/
    vpn/                     Deterministic VPN troubleshooting state machine

  email/                     Email ingest pipeline and pending resolution

  jira/                      Jira-style payload preview builders and label mapping

  llm/                       Mock/OpenAI provider abstraction

  storage/                   Redis/in-memory session store and SQLite usage log

  tenants/                   Built-in tenant config and SQLite tenant registry

  tagging/                   Internal normalized tag generation

  schemas/                   Pydantic request/response models
```

The backend is layered around a simple principle:

```text
API routes -> orchestration services -> deterministic domain logic -> storage/adapters
```

---

## Core Flows

### Chat Flow

`POST /api/chat`

1. The client sends a message, optionally with `session_id` and `company_id`.
2. The backend creates or loads a session.
3. The user message is appended to session history.
4. Tenant is resolved from:
   - `X-Company-Id` header
   - request body `company_id`
   - stored session tenant
5. Intent routing classifies the message.
6. VPN issues enter the deterministic VPN workflow.
7. If escalation is needed, the system generates a Jira-style payload preview.
8. The assistant reply, intent, confidence, handoff summary, and optional preview are returned.

### Email Ingest Flow

`POST /api/email/ingest`

1. Email is submitted with a stable `message_id`.
2. The system checks idempotency.
3. Tenant is resolved from:
   - `X-Company-Id` header
   - request body `company_id`
   - plus-address inference from `to_email`
4. Email content is classified deterministically or optionally by the LLM layer.
5. A handoff summary is built.
6. Internal tags are attached.
7. Tenant-specific Jira labels are generated.
8. A Jira-style payload preview is returned.
9. Activity events are logged when processing succeeds.

If tenant resolution fails, the email is stored as `pending_tenant` and can be resolved later.

---

## Deterministic Support Automation

The project is deterministic-first. The VPN support flow is implemented as a state machine, not as free-form generation.

VPN states include:

```text
VPN_START
VPN_ASK_OS
VPN_ASK_CLIENT
VPN_ASK_SYMPTOM
VPN_ASK_ERROR_CODE
VPN_GIVE_STEPS
VPN_CHECK_RESULT
VPN_HANDOFF
```

The flow collects:

- Operating system
- VPN client
- Symptom category
- Error code or error signal
- Troubleshooting attempts
- Steps already provided

After repeated failure, the flow escalates and produces a structured handoff summary. Once a session reaches VPN_HANDOFF, further troubleshooting is restricted to avoid inconsistent post-escalation state.

---

## Email Ingest Pipeline

The email pipeline is built for deterministic automation and safe retries.

Main behaviors:

- `message_id` is used as the idempotency key.
- Processed email receipts are stored so duplicate requests return deterministic results.
- Missing tenant information creates a pending record instead of dropping the email.
- Pending emails can be resolved manually with a tenant ID.
- Pending emails can also be reprocessed if a candidate tenant becomes available.
- Successful direct email processing creates activity events for email ingest and Jira preview generation.
- Email classification supports `VPN_ISSUE`, `PASSWORD_RESET`, and `EMAIL_ISSUE`.

Email statuses:

```text
processed
duplicate_skipped
pending_tenant
```

Tenant inference supports plus-addressing:

```text
support+bank_demo@example.com -> bank_demo
support+auto_demo@example.com -> auto_demo
support+bank@example.com      -> bank_demo
support+auto@example.com      -> auto_demo
```

---

## Storage Model

### Redis Session and Pending Storage

By default, the app uses Redis.

Redis stores:

- Chat message history
- Last detected intent
- VPN context
- Session tenant/company ID
- Pending chat handoff summary
- Processed email markers
- Email receipts
- Pending email payloads

Session and email keys are stored with TTL expiration using `SESSION_TTL_SECONDS`.

Set `USE_REDIS=0` to use the in-memory store for local development without Redis.

### SQLite Usage Tracking

SQLite is used for append-only activity/audit events.

Default path:

```text
data/usage_events.db
```

Tracked event data includes:

- Timestamp
- Tenant ID
- Event type
- Message ID
- Source
- Intent
- Confidence
- Metadata

Tracked activity event types include:

```text
email_ingested
jira_preview_generated
tenant_created
label_mapping_updated
```

Usage endpoints expose raw events and summaries. Summaries include:

- `by_event_type`: counts all tracked backend activities by event type.
- `by_intent`: counts processed direct email classifications by intent using `email_ingested` events, avoiding double-counting `jira_preview_generated`.

### SQLite Tenant Registry

Built-in demo tenants are defined in code, and additional tenants can be added dynamically through the tenant API.

Dynamic tenants are persisted in SQLite.

Default path:

```text
data/tenants.db
```

On application startup, persisted tenants are loaded into the runtime tenant registry.

---

## Multi-Tenant Routing

The seeded demo tenants are:

```text
bank_demo
auto_demo
health_demo
fox_clothes_demo
candyshop_demo
hatifim_demo
```

Additional tenants can be added dynamically through:

```text
POST /api/tenants
```

Tenant resolution depends on the flow:

Chat tenant resolution:

1. `X-Company-Id` header
2. request body `company_id`
3. existing session tenant

Email tenant resolution:

1. `X-Company-Id` header
2. request body `company_id`
3. plus-address inference from `to_email`

Each tenant controls:

- Jira project key
- Jira issue type
- Default labels
- Optional component
- Internal-tag-to-Jira-label mapping

---

## Internal Tags and Tenant-Specific Jira Labels

The project separates internal meaning from tenant-specific ticket labels.

Internal tags are stable across tenants:

```text
vpn
connectivity
access
stability
certificate
auth_failed
timeout
error_619
error_809
error_812
password
email
general
unknown
escalated
```

Tenant label mapping translates those internal tags into tenant-specific Jira labels.

Example:

```text
Internal tag: connectivity
```

For `bank_demo`:

```text
bank-network
```

For `auto_demo`:

```text
auto-network
```

This keeps business logic consistent while allowing each tenant to use its own Jira taxonomy.

The system does not create real Jira tickets. It generates Jira-style payload previews that show what would be sent to a ticketing system.

---

## LLM Provider Layer

The LLM layer is optional.

Supported providers:

```text
mock
openai
```

The default development provider is `mock`, which simulates structured LLM classification without requiring external API calls.

The LLM layer can enrich email classification with:

- Intent
- Confidence
- Reason
- Extracted VPN fields
- Internal tags

The app only accepts LLM output when it meets the configured confidence threshold. Otherwise, it falls back to deterministic classification.

Important safety behaviors:

- If `USE_LLM=0`, deterministic classification is used.
- If the provider is unsupported, deterministic classification is used.
- If OpenAI credentials are missing, deterministic classification is used.
- If the LLM returns invalid or low-confidence output, deterministic classification is used.
- If the LLM call fails, deterministic classification is used.

This makes AI an enhancement, not a dependency.

---

## Safe Fallback Behavior

The backend is designed to continue operating when optional systems fail.

Examples:

- LLM unavailable -> deterministic classifier
- Missing OpenAI API key -> deterministic classifier
- Low-confidence LLM result -> deterministic classifier
- Missing tenant during email ingest -> pending tenant state
- Missing tenant during chat escalation -> ask for company ID before final handoff
- Redis disabled -> in-memory store
- Usage DB initialization failure -> API startup continues
- Duplicate email ingest -> stored receipt is returned when available

---

## Observability

The backend emits structured operational logs for:
- LLM acceptance/rejection
- tenant resolution
- pending email handling
- usage tracking
- duplicate detection
- escalation behavior

Usage events are also persisted in SQLite for activity/audit reporting.

## API Reference

### Core

```text
GET /
GET /health
GET /docs
```

### Chat

```text
POST /api/chat
GET /api/sessions/{session_id}
DELETE /api/sessions/{session_id}
```

### Email Automation

```text
POST /api/email/ingest
POST /api/email/resolve
POST /api/email/reprocess
GET /api/email/pending
GET /api/email/pending/{message_id}
```

### Tenants

```text
GET /api/tenants
GET /api/tenants/{tenant_id}
GET /api/tenants/{tenant_id}/labels
PATCH /api/tenants/{tenant_id}/labels
POST /api/tenants
```

### Usage Tracking

```text
GET /api/usage/events
GET /api/usage/summary
```

---

## Environment Variables

`.env` is private and should not be committed.

`.env.example` is the public template that documents the expected configuration.

Example:

```env
USE_LLM=1
LLM_PROVIDER=mock
LLM_MIN_CONFIDENCE=0.75

OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4o-mini
OPENAI_TIMEOUT_SECONDS=20

USE_REDIS=1
REDIS_URL=redis://localhost:6379/0
SESSION_TTL_SECONDS=7200

USAGE_DB_PATH=data/usage_events.db
TENANT_DB_PATH=data/tenants.db
```

For local development without Redis:

```env
USE_REDIS=0
```

For deterministic-only behavior without LLM enrichment:

```env
USE_LLM=0
```

---

## How to Run on Windows

For full-stack Docker Compose usage, see the root [readme.md](../readme.md). The commands below are for running the backend manually.

From the backend directory:

```powershell
cd "C:\Users\My-PC\Desktop\programing\new programing\chatbox\backend"
```

Activate the virtual environment:

```powershell
.\env\Scripts\activate
```

Install dependencies if needed:

```powershell
pip install -r requirements.txt
```

Create a private `.env` from the public template:

```powershell
copy .env.example .env
```

Start Redis if `USE_REDIS=1`:

```powershell
redis-server
```

In another terminal, start the FastAPI backend:

```powershell
uvicorn app.main:app --reload
```

Open the API docs:

```text
http://127.0.0.1:8000/docs
```

Health check:

```text
http://127.0.0.1:8000/health
```

---

## Manual Testing with Thunder Client

Use this base URL:

```text
http://127.0.0.1:8000
```

### Health Check

```http
GET /health
```

Expected response:

```json
{
  "status": "ok"
}
```

---

## Chat API Examples

### Start VPN Troubleshooting

```http
POST /api/chat
Content-Type: application/json
X-Company-Id: bank_demo
```

Body:

```json
{
  "message": "VPN is not working"
}
```

The response includes a generated `session_id`. Use it in the next requests.

### Continue VPN Flow

```http
POST /api/chat
Content-Type: application/json
X-Company-Id: bank_demo
```

Body:

```json
{
  "session_id": "PASTE_SESSION_ID_HERE",
  "message": "Windows"
}
```

### Provide More Details

```http
POST /api/chat
Content-Type: application/json
X-Company-Id: bank_demo
```

Body:

```json
{
  "session_id": "PASTE_SESSION_ID_HERE",
  "message": "AnyConnect, cannot connect, error 619"
}
```

### Report Failure After Steps

```http
POST /api/chat
Content-Type: application/json
X-Company-Id: bank_demo
```

Body:

```json
{
  "session_id": "PASTE_SESSION_ID_HERE",
  "message": "still failing with the same error"
}
```

After enough failed attempts, the response can include:

- `handoff: true`
- `handoff_summary`
- `jira_payload_preview`

### Get Session History

```http
GET /api/sessions/PASTE_SESSION_ID_HERE
```

### Delete Session

```http
DELETE /api/sessions/PASTE_SESSION_ID_HERE
```

---

## Email API Examples

### Email Ingest With Explicit Tenant

```http
POST /api/email/ingest
Content-Type: application/json
X-Company-Id: bank_demo
```

Body:

```json
{
  "message_id": "email-vpn-001",
  "from_email": "employee@example.com",
  "to_email": "support@example.com",
  "subject": "VPN issue",
  "body": "I cannot connect to VPN from Windows using AnyConnect. Error 619."
}
```

Expected behavior:

- Status is `processed`
- Tenant is `bank_demo`
- Internal tags are generated
- Jira-style payload preview is returned
- Activity events are logged

### Password Reset / Account Access Email

```http
POST /api/email/ingest
Content-Type: application/json
X-Company-Id: bank_demo
```

Body:

```json
{
  "message_id": "email-password-001",
  "from_email": "employee@example.com",
  "to_email": "support@example.com",
  "subject": "Account access issue",
  "body": "I cannot log in to my work account. It says my password expired and my account is locked."
}
```

Expected behavior:

- Intent is `PASSWORD_RESET`
- Generic Jira-style payload preview is returned
- Internal tags include `password` and `escalated`

### Outlook / Email / Calendar Sync Email

```http
POST /api/email/ingest
Content-Type: application/json
X-Company-Id: bank_demo
```

Body:

```json
{
  "message_id": "email-outlook-001",
  "from_email": "employee@example.com",
  "to_email": "support@example.com",
  "subject": "Outlook calendar sync issue",
  "body": "My Outlook calendar is not syncing with Exchange. Meeting invite updates are delayed and the shared mailbox is out of sync."
}
```

Expected behavior:

- Intent is `EMAIL_ISSUE`
- Generic Jira-style payload preview is returned
- Internal tags include `email` and `escalated`

### Email Ingest With Plus-Address Tenant Inference

```http
POST /api/email/ingest
Content-Type: application/json
```

Body:

```json
{
  "message_id": "email-vpn-002",
  "from_email": "employee@example.com",
  "to_email": "support+auto_demo@example.com",
  "subject": "VPN keeps disconnecting",
  "body": "GlobalProtect connects but keeps disconnecting."
}
```

Expected behavior:

- Tenant is inferred as `auto_demo`
- Tenant-specific labels use the `auto_demo` mapping

### Duplicate Email Ingest

Send the same request again with the same `message_id`:

```json
{
  "message_id": "email-vpn-002",
  "from_email": "employee@example.com",
  "to_email": "support+auto_demo@example.com",
  "subject": "VPN keeps disconnecting",
  "body": "GlobalProtect connects but keeps disconnecting."
}
```

Expected behavior:

```text
duplicate_skipped
```

The system avoids processing the same email twice.

### Email Ingest With Missing Tenant

```http
POST /api/email/ingest
Content-Type: application/json
```

Body:

```json
{
  "message_id": "email-pending-001",
  "from_email": "employee@example.com",
  "to_email": "support@example.com",
  "subject": "VPN issue",
  "body": "I cannot connect to VPN. Error 809."
}
```

Expected behavior:

```text
pending_tenant
```

No Jira-style payload preview is returned yet because the tenant is unknown.

### List Pending Emails

```http
GET /api/email/pending
```

### Get Pending Email Details

```http
GET /api/email/pending/email-pending-001
```

### Resolve Pending Email

```http
POST /api/email/resolve
Content-Type: application/json
X-Company-Id: bank_demo
```

Body:

```json
{
  "message_id": "email-pending-001"
}
```

Alternative body-based tenant resolution:

```json
{
  "message_id": "email-pending-001",
  "company_id": "bank_demo"
}
```

Expected behavior:

- Pending email becomes `processed`
- Tenant-specific Jira-style payload preview is generated
- Usage event is logged

### Reprocess Pending Email

```http
POST /api/email/reprocess
Content-Type: application/json
```

Body:

```json
{
  "message_id": "email-pending-001"
}
```

This attempts to reprocess a pending email using any candidate tenant data already stored in the pending payload.

---

## Tenant API Examples

### List Tenants

```http
GET /api/tenants
```

Seeded demo tenants include:

```text
bank_demo
auto_demo
health_demo
fox_clothes_demo
candyshop_demo
hatifim_demo
```

### Get One Tenant

```http
GET /api/tenants/bank_demo
```

### Add or Update a Tenant

```http
POST /api/tenants
Content-Type: application/json
```

Body:

```json
{
  "tenant_id": "acme_corp",
  "display_name": "Acme Corp",
  "jira_project_key": "ACME",
  "jira_issue_type": "Incident",
  "default_labels": ["it-support"],
  "component": "Service Desk",
  "label_map": {
    "vpn": ["vpn"],
    "connectivity": ["network-connectivity"],
    "access": ["internal-access"],
    "stability": ["unstable-connection"],
    "escalated": ["escalated"],
    "password": ["password-reset"],
    "email": ["email-issue"],
    "unknown": ["needs-triage"]
  }
}
```

The tenant is persisted in SQLite and loaded again on application startup.

### Get Tenant Label Mapping

```http
GET /api/tenants/bank_demo/labels
```

### Update Tenant Label Mapping

```http
PATCH /api/tenants/bank_demo/labels
Content-Type: application/json
```

Body:

```json
{
  "label_map": {
    "vpn": ["vpn"],
    "connectivity": ["bank-network"],
    "error_619": ["error-619"],
    "escalated": ["escalated"]
  }
}
```

---

## Usage API Examples

### List Usage Events

```http
GET /api/usage/events
```

With tenant filter:

```http
GET /api/usage/events?tenant_id=bank_demo
```

### Usage Summary

```http
GET /api/usage/summary
```

With tenant filter:

```http
GET /api/usage/summary?tenant_id=bank_demo
```

With event type filter:

```http
GET /api/usage/summary?tenant_id=bank_demo&event_type=jira_preview_generated
```

The summary response includes:

- `total`: total tracked activities matching the filters
- `by_event_type`: all activities grouped by event type
- `by_intent`: direct processed email classifications grouped by intent

`by_intent` is based on `email_ingested` events so one processed email counts once even when it also generates a Jira preview activity.

---

## Testing Notes

This repository currently does not include a first-party automated test suite.

Recommended future automated test coverage:

- Intent routing and vague follow-up behavior
- VPN state machine transitions
- VPN terminal handoff lock
- Tenant resolution priority
- Email idempotency and duplicate receipts
- Pending tenant lifecycle
- Internal tag generation
- Tenant-specific Jira label mapping
- LLM fallback behavior
- Usage event logging

For now, the project can be tested manually through:

- Swagger UI at `/docs`
- Thunder Client
- curl or PowerShell HTTP requests

---

## Operational Notes

- The system generates Jira-style payload previews only.
- It does not create real Jira tickets.
- The default LLM provider is `mock`.
- Real OpenAI calls are optional and require `LLM_PROVIDER=openai` plus `OPENAI_API_KEY`.
- LLM token accounting, provider cost tracking, and billing logic are not implemented.
- `.env` is private local configuration.
- `.env.example` is the public configuration template.
- Redis keys expire according to `SESSION_TTL_SECONDS`.
- SQLite files are created under `data/` by default.
- Usage database startup errors are logged but do not block API startup.

---

## Design Principles

- Deterministic first
- AI-assisted, not AI-dependent
- Safe fallback over hard failure
- Tenant-aware routing
- Stable internal taxonomy
- Tenant-specific external labels
- Idempotent email processing
- Practical observability
- Clear service boundaries

---

## Future Improvements

Potential next steps:

- Automated pytest suite
- Real Jira integration behind the existing payload preview layer
- Email provider/webhook integration
- Background queue for async ingest processing
- Authentication and role-based tenant access
- Admin dashboard for pending emails, tenants, and usage
- Additional deterministic support flows beyond VPN

