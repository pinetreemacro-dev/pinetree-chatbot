# PineTree Chatbot — Phase 1

A FAQ-based chatbot assistant for PineTree with human escalation for out-of-scope questions.

## Project Structure

```
chatbot/
├── backend/              # Python FastAPI backend
│   ├── api/             # API routes
│   ├── chatbot/         # Core chatbot logic
│   ├── knowledge/       # Knowledge base retrieval
│   ├── database/        # Database models & migrations
│   ├── services/        # Email, notifications, retention
│   └── tests/           # Unit tests
├── frontend/            # React/Next.js UI
├── knowledge_base/      # FAQ database (JSON)
│   └── phase_1/         # Initial 50 FAQs
├── admin/               # Admin dashboard (future)
├── docker/              # Docker configuration
└── docs/                # Documentation
```

## Requirements

See [CLAUDE.md](CLAUDE.md) for project context and guidelines.

## Getting Started

### Backend Setup

Requires Python 3.10+ (developed on 3.14). From the `chatbot/` folder:

```bash
py -3.14 -m venv .venv
.venv\Scripts\pip install -r backend\requirements-dev.txt
copy .env.example .env
.venv\Scripts\python -m uvicorn backend.main:app --reload
.venv\Scripts\python -m pytest backend/tests
```

- Chat: http://localhost:8000/
- Admin dashboard: http://localhost:8000/admin (browser login prompt; set `ADMIN_USERNAME` / `ADMIN_PASSWORD` in `.env`. Admin stays disabled while `ADMIN_PASSWORD` is empty.)
- API docs: http://localhost:8000/docs

The first start downloads a small embedding model (BAAI/bge-small-en-v1.5, cached in `.cache/`), so it needs internet once. Answer / clarify / hand-off thresholds are `CONFIDENCE_HIGH`, `CONFIDENCE_LOW` and `CLARIFY_MARGIN` (similarity scores, not probabilities); `backend/tests/test_matching_quality.py` must still pass after any dataset or threshold change.

The admin dashboard shows stats, escalated questions (with full chat, resolve and "Create FAQ"), leads, and FAQ add/edit. FAQs added or edited there are saved in the database (table `faqs`) and override the `knowledge_base/` file with the same id; they take effect immediately on every server instance. To change the bundled set permanently, edit the JSON files and commit them.
 Without `SMTP_HOST` set, escalation emails are logged instead of sent.

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

## Key Features (Phase 1)

- ✓ FAQ-based Q&A from knowledge base
- ✓ Contact collection (name, email, phone) — no authentication
- ✓ Out-of-scope detection and human escalation
- ✓ Email forwarding to info@pinetree.com
- ✓ Session management (ephemeral for users, 30-day retention internally)
- ✓ Auto-purge of data after 30 days
- ✓ Free/open-source infrastructure

## Deployment

Vercel (app) + Supabase (Postgres). `pyproject.toml` names `index:app` as the entry point and lists the packages Vercel installs (a test keeps it identical to `backend/requirements.txt`, so change both together); `vercel.json` schedules the nightly purge.

Environment variables to set on Vercel (never commit them):

| Variable | Value |
| --- | --- |
| `DATABASE_URL` | Supabase "Transaction pooler" connection string (port 6543) |
| `ADMIN_PASSWORD` | long random password for `/admin` |
| `CRON_SECRET` | long random string; Vercel Cron sends it when it calls `/api/internal/purge` |
| `ESCALATION_EMAIL`, `CONTACT_EMAIL` | where team emails go / the address visitors see |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD` | outgoing email (Gmail app password or similar) |

On a serverless host the app skips the in-process scheduler, stores the embedding model in `/tmp` (downloaded on a cold start), and trusts the `X-Forwarded-For` header for the per-visitor rate limits (`RATE_SESSION_PER_HOUR`, `RATE_CONTACT_PER_HOUR`, `RATE_CHAT_PER_MINUTE`; `0` turns one off).
