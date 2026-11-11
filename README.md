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

The admin dashboard shows stats, escalated questions (with full chat, resolve and "Create FAQ"), leads, and FAQ add/edit. New FAQs are written to `knowledge_base/phase_2/` and take effect immediately.
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

Start with free-tier services:
- Backend: Free cloud hosting (Render, Railway, Vercel)
- Database: PostgreSQL free tier
- Email: SMTP/free service

Scale to managed services as traffic grows.
