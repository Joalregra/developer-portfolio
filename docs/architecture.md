# Architecture

```mermaid
flowchart LR
  V[Visitor / recruiter] --> F[Frontend<br/>React + TypeScript<br/>Cloudflare Workers, static assets]
  F -->|REST| P[Shared Caddy<br/>HTTPS, security headers]
  P --> B[Backend<br/>FastAPI in Docker<br/>AWS Lightsail]
  B --> K[(Knowledge file<br/>ChatbotKnowledge.en.md)]
  B --> L1[Groq<br/>primary LLM]
  B -.fallback.-> L2[Gemini<br/>secondary LLM]
  B --> D[(PostgreSQL<br/>Neon, us-east-1)]
  J[Daily retention job<br/>cron on the Lightsail instance] --> D
```

The backend shares one Lightsail instance with the Gedocs demo, behind a single Caddy. Where each piece runs, how a deploy works and how to set the server up are in [`deploy.md`](deploy.md).

| Part | Responsibility |
|---|---|
| Frontend | Static single-page portfolio (ES/EN), CV download and the chat widget. Talks to the backend only through `src/services/api.ts`. |
| Backend | Validates chat requests, builds the system prompt from the knowledge file, calls the LLM provider with failover, enforces rate limits and stores anonymous chat logs. |
| Knowledge file | Single source of truth about Johan for the assistant. Versioned with the code. |
| PostgreSQL | Anonymous log of questions asked to the assistant (no personal data) and the visitors' ratings of the answers, used to improve the knowledge file. Rows are deleted after 90 days. |

## Chat contract

`POST /api/chat`, implemented in `backend/app/api/routes/chat.py` and consumed by `frontend/src/services/api.ts`. How a question travels, and every failure mode, is in [`chat-flow.md`](chat-flow.md).

```jsonc
// POST /api/chat
{ "message": "string, 1 to 1000 characters",
  "locale": "es" | "en",                       // language of the site UI; the answer follows the question
  "history": [{ "role": "user" | "assistant", "content": "string, 1 to 1000 characters" }],   // at most 6 earlier messages
  "quick_question_id": "projects" | "stack" | "production" | "availability" | "challenge" | "ai" }  // optional

// 200 (also for refusals)
{ "answer": "plain text",
  "refused": false,                            // true: off topic or an attack, `answer` is a fixed text
  "section": "projects" | "experience" | "about" | "skills" | "education" | "contact" | null,
  "message_id": "uuid",
  "request_id": "string" }

// Every error has the same body; clients branch on `code`, never on `message`
{ "error": { "code": "rate_limited", "message": "text in the visitor's language",
             "request_id": "string", "details": null } }
```

| Status | `code` | Meaning |
|---|---|---|
| 413 | `payload_too_large` | The request body is bigger than `MAX_BODY_BYTES` (16 KB by default; the proxy cuts at 64 KB before that) |
| 422 | `invalid_request` | Body not valid (empty, over 1000 characters, unknown field, more than 6 history messages) |
| 429 | `rate_limited` | Too many requests; `Retry-After` says when to try again |
| 500 | `internal_error` | An unexpected error. The body carries the `request_id` to look it up in the logs, and nothing else |
| 502 | `invalid_model_output` | The model answered twice without a usable answer |
| 503 | `assistant_paused` | Switched off, or today's model budget is spent |
| 503 | `assistant_unavailable` | No model could answer in time |

When `section` is present, the UI links to that part of the page under the answer ("Ver en: Proyectos"). A quick-question id is answered from the knowledge file without calling a model.

### Rating an answer

`POST /api/chat/feedback`, in the same router. One rating per answer; sending it again, with the same value or the other one, is accepted and ignored, so the first rating wins.

```jsonc
// POST /api/chat/feedback
{ "message_id": "uuid from the chat response",
  "helpful": true,
  "locale": "es" | "en" }                      // language of the error messages

// 204, no body (also when the answer had already been rated)
```

| Status | `code` | Meaning |
|---|---|---|
| 404 | `not_found` | No such message in the log. The log is best effort, so an answer whose row could not be written cannot be rated |
| 422 | `invalid_request` | Body not valid (not a UUID, `helpful` not a boolean, unknown field) |
| 429 | `rate_limited` | More than 20 ratings a minute or 200 a day from one visitor; `Retry-After` says when to try again |
| 503 | `feedback_unavailable` | No database, or it failed. The chat is not affected |

### Retention

`python -m app.jobs.purge_chat_log` deletes the messages older than `CHAT_LOG_RETENTION_DAYS` (90) and, by cascade, their ratings. It connects with `RETENTION_DATABASE_URL`, the user `portfolio_retention` (`SELECT` and `DELETE` only, created by `backend/sql/retention_role.sql`). The running app never has that URL.

## Frontend build

`npm run build` type-checks, builds the client, builds a server bundle of the app and prerenders `/es/` and `/en/` into static HTML, so the content is in the HTML itself (SEO, link previews, first paint) and React hydrates it. Set `VITE_SITE_URL` to enable canonical/hreflang tags, absolute Open Graph URLs and `sitemap.xml`. The last build step, `scripts/security-headers.mjs`, writes `dist/_headers` with the security headers Cloudflare adds to every response; its Content-Security-Policy is computed from the built pages (the hashes of their inline script and style) and from `VITE_API_URL`, so `VITE_API_URL` must be set in the Cloudflare build variables.

## Repository layout

```
developer-portfolio/
├── frontend/              React + Vite + TypeScript + Tailwind
│   ├── public/cv/         CV in PDF
│   └── src/
│       ├── app/           App shell and layout composition
│       ├── sections/      Page sections: Hero, Projects, Experience, About, Skills, Education, Contact
│       ├── components/    Reusable UI (ui/) and layout pieces (layout/)
│       ├── features/chat/ Chat widget: components, context and hooks (the HTTP calls are in services/)
│       ├── hooks/         Shared hooks
│       ├── i18n/          Spanish and English UI strings
│       ├── data/          Portfolio content (profile, projects, skills)
│       ├── services/      HTTP client for the backend
│       ├── styles/        Tailwind entry point and theme
│       └── test/          Test setup
├── backend/               FastAPI
│   ├── app/
│   │   ├── main.py        App factory: middleware, error handlers, lifespan and routers
│   │   ├── core/          Settings, JSON logs, errors, deadline and other cross-cutting helpers
│   │   ├── api/           deps.py (what routes receive) and routes/ (thin HTTP routers)
│   │   ├── schemas/       Pydantic request/response models
│   │   ├── services/      Business logic (chat, guard, feedback, retention, knowledge loading)
│   │   │   └── llm/       Groq and Gemini clients behind one interface, and the router
│   │   ├── jobs/          Commands run by cron, such as the retention job
│   │   ├── db/            Engine, sessions and repositories
│   │   └── models/        ORM models
│   ├── alembic/           Migrations
│   ├── sql/               schema.sql, roles.sql and retention_role.sql, run by hand once
│   ├── knowledge/         Assistant knowledge files
│   ├── evals/             Attack and recruiter-question set, run by hand against the real models
│   └── tests/             pytest
├── deploy/                Production files for the Lightsail instance
│   ├── proxy/             Shared Caddy (compose and Caddyfile)
│   ├── api/               API compose, env examples and the retention job
│   └── scripts/           deploy.sh, run on the server by CI
├── docs/                  Architecture, decisions, chat flow, deployment runbook and screenshots
└── .github/               CI and Dependabot
```
