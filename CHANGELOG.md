# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/). Each release is also published, with its full description, in [GitHub Releases](https://github.com/Joalregra/developer-portfolio/releases).

## [Unreleased]

## [1.0.0] - 2026-10-27

First stable release. The portfolio is live at [johanrendon.com](https://johanrendon.com).

### Frontend
- Bilingual portfolio (Spanish and English), one prerendered URL per language (`/es/`, `/en/`) with per-language title, Open Graph, hreflang, JSON-LD, robots and sitemap.
- Sections: hero, about, experience, projects, skills, education and contact; light and dark theme; downloadable CV and certificates.
- Gedocs demo with screenshots visitors can enlarge. The Globant recommendation letter is shown as a quote; the signed PDF is not published yet.
- Chat widget with quick questions, answer ratings, history in `sessionStorage` and states for rate limit, offline and unavailable.
- Accessibility and performance: self-hosted font, no animation or icon library, `prefers-reduced-motion` respected, Lighthouse CI budgets and Playwright layout checks.
- A Content-Security-Policy generated at build time from the hashes of the built HTML.

### AI assistant
- The whole knowledge file goes into the system prompt (no RAG); quick-question buttons are answered without a model.
- Layered defences: on/off switch, per-visitor rate limit, text cleaning that masks emails and phone numbers, known attack phrases, in-memory answer cache, Prompt Guard 2 classifier, daily budget of model calls and an output validator.
- Groq `gpt-oss-120b` first, Gemini `gemini-3.5-flash-lite` as the fallback, never for the EU, EEA, UK, Switzerland or an unknown country.
- Evaluation set in `backend/evals/` (34 attacks, 34 recruiter questions). Run of 2026-10-20: 33 of 34 attacks blocked, 1 to review, 0 failed; 1 false positive in 34 legitimate questions.

### Backend
- `POST /api/chat`, `POST /api/chat/feedback` (idempotent, first rating wins) and `GET /health`.
- Uniform error body with a stable `code`, JSON logs that never contain the visitor's question, body size limit, request deadline and API docs closed in production.
- Strict mypy and Ruff; Alembic migrations `0001` (chat tables) and `0002` (`answered_cached` status).

### Data and privacy
- PostgreSQL on Neon with three roles: the app can only `INSERT` and `SELECT`, Alembic uses the owner and the retention job can only `SELECT` and `DELETE`.
- The anonymous log stores no IP, user agent or other identifier, and a daily job deletes rows older than 90 days. The chat never depends on the database.

### Infrastructure and CI/CD
- Frontend on Cloudflare Workers (static assets only), built by Workers Builds on every push to `main`.
- API in Docker on an AWS Lightsail instance shared with the Gedocs demo, behind one shared Caddy; GitHub Actions tests, builds the image to GHCR and deploys over SSH with a forced command.
- CI on every pull request: frontend checks, layout checks and Lighthouse, deploy-file validation and backend checks. Runbook in [docs/deploy.md](docs/deploy.md).

### Known limits
- One uvicorn process and 2 GB shared with Gedocs.
- Without Cloudflare in front of the API, Gemini is not used and the assistant depends on Groq's free quota.
- The answer cache and the daily call budget live in memory, so a deploy empties them.
- Not done yet: uptime monitors, and publishing the signed recommendation letter.

[Unreleased]: https://github.com/Joalregra/developer-portfolio/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/Joalregra/developer-portfolio/releases/tag/v1.0.0
