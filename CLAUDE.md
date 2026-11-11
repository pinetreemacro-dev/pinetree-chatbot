# PineTree Chatbot Development Guide

## Project Overview

**Phase 1 MVP**: A FAQ-based chatbot for PineTree that:
- Answers questions from a curated knowledge base (~50 FAQs initially)
- Collects user contact info (name, email, phone) for lead follow-up
- Escalates out-of-scope questions to the human team
- Retains conversation data for 30 days, then auto-purges
- Runs on free/open-source infrastructure initially

**Success Criteria**: User can ask a question → get an answer from the FAQ, or be escalated to a human if out-of-scope.

---

## Architecture Decisions

### Knowledge Base First, LLM Second

- **Don't**: Send user question directly to LLM and hope it gives the right answer
- **Do**: Retrieve relevant FAQ from knowledge base first, then use LLM to formulate natural response

Example flow:
```
User: "What services does PineTree offer?"
  ↓
Search knowledge base for semantically similar FAQ
  ↓
Find FAQ_042 with 0.89 confidence
  ↓
Pass FAQ content + user question to LLM
  ↓
LLM generates natural answer
  ↓
User sees answer
```

If confidence < threshold (e.g., 0.70):
```
No reliable FAQ found
  ↓
Escalate to human team
  ↓
Send email to info@pinetree.com
  ↓
User notified: "Our team will contact you shortly"
```

### Session vs. History

- **User-facing**: No chat history shown. Each visit is a fresh conversation.
- **Backend**: Store all messages internally for 30 days for review/training/context
- **Auto-cleanup**: 30-day-old records auto-deleted from database

### No Authentication

- No login, no accounts, no passwords
- Collect: name, email, phone (one-time at start of session)
- Store contact info with session for human team follow-up

---

## Tech Stack

| Component          | Technology           | Rationale                              |
| ------------------ | -------------------- | -------------------------------------- |
| Backend API        | Python FastAPI       | Simple, fast, async-ready              |
| Frontend           | React/Next.js        | Modern, responsive UI                  |
| Database           | PostgreSQL           | Scalable, free tier available          |
| Vector Search      | FAISS or ChromaDB    | Semantic search for FAQ retrieval      |
| Embeddings         | Sentence Transformers| Open-source, lightweight               |
| LLM                | Open-source (Ollama) | Or Hugging Face via API                |
| Email              | SMTP (Resend/SendGrid free tier) | Reliable escalation emails             |
| Containerization   | Docker               | Easy local dev + cloud deployment      |

---

## Code Organization

### Backend (`backend/`)

```
api/                   → FastAPI routes (chat, contact, session, escalation)
core/                  → Config, security, logging
chatbot/               → Core chatbot logic (intent, retrieval, confidence)
knowledge/             → FAQ loader, embeddings, vector search
database/              → Models, migrations, queries
services/              → Email, data retention, notifications
tests/                 → Unit tests
main.py                → FastAPI app entry point
requirements.txt       → Python dependencies
```

### Frontend (`frontend/`)

```
components/            → ChatWindow, Message, InputBox, ContactForm
pages/                 → Index page, about (minimal)
services/              → API client
styles/                → CSS/Tailwind
```

### Knowledge Base (`knowledge_base/`)

```
phase_1/
  ├── faq_001.json
  ├── faq_002.json
  └── ...faq_050.json

future/                → Placeholder for Phase 2 FAQs
```

Each FAQ file:
```json
{
  "id": "FAQ_001",
  "question": "What is PineTree?",
  "answer": "PineTree is...",
  "category": "Company",
  "keywords": ["PineTree", "company"],
  "active": true,
  "phase": 1
}
```

---

## Development Workflow

1. **Backend first**: Implement API, database, chatbot logic
2. **Knowledge base**: Create/curate initial 50 FAQs
3. **Frontend**: Build chat UI
4. **Integration**: Connect frontend → backend
5. **Testing**: Test Q&A, escalation, email, data retention
6. **Deployment**: Docker → free cloud hosting

---

## Key APIs

### `POST /api/contact`
Collect user info (name, email, phone). Returns session_id.

### `POST /api/chat`
Submit question. Returns answer or escalation response.

### `POST /api/escalation`
Create escalation, send email to info@pinetree.com.

### `GET /api/session/{id}`
Retrieve current session (optional — may not expose to frontend).

---

## Important Constraints

- **No login required**: Stateless API (use session cookies if needed)
- **Confidence threshold**: Only answer FAQs with high confidence (>0.70 initially)
- **Rate limiting**: Prevent spam/abuse
- **Input validation**: Sanitize all user input
- **Data retention**: Auto-delete after 30 days
- **Email escalation**: Every out-of-scope question → email to info@pinetree.com

---

## For Future Expansion

- Phase 2: Admin dashboard for escalation review, FAQ management
- Phase 3: Production cloud infrastructure (managed database, autoscaling)
- Phase 4: Advanced features (multilingual, voice, CRM integration, live chat handoff)

---

## Questions to Answer Before Coding

1. What are the initial 50 FAQs?
2. What's the confidence threshold for "out of scope"?
3. Should we collect user data before or after the first question?
4. Who monitors info@pinetree.com for escalations?
5. Should escalations trigger automatic CRM updates, or just email?
