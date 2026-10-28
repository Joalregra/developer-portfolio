# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/). Each release is also published, with its full description, in [GitHub Releases](https://github.com/Joalregra/developer-portfolio/releases).

## [Unreleased]

## [1.1.0] - 2026-10-28

The free Groq quota now lasts: one visitor can no longer spend it alone, the daily limit is counted in tokens, and a deploy no longer hands the quota back or empties the answer cache.

### Added
- **Per-visitor limit on questions that reach a model:** 3 an hour and 6 a day (`MODEL_CALLS_PER_VISITOR_HOUR`, `MODEL_CALLS_PER_VISITOR_DAY`). Quick buttons, cached answers and refusals do not count, and the question is given back if the model failed through no fault of the visitor. Past the limit the API answers `429 question_limit` with `Retry-After`. The counters stay in memory, so no address reaches the disk.
- **Widget message for `question_limit`:** it explains the limit, links to the email and shows no retry button. The quick questions keep working.
- **State that survives a deploy** (`STATE_FILE`, decision 21): the answer cache and today's token count are saved to a file on the new `api_state` volume (a save every 30 s when something changed, and a final one at shutdown). The file holds no visitor text and no address; if it is missing, corrupt or unwritable the chat starts empty and only logs a warning.

### Changed
- **The daily budget counts tokens, not calls:** `DAILY_TOKEN_BUDGET` (default 150000) replaces `DAILY_LLM_BUDGET`. Each call reserves an estimate and settles to the real usage.
- The answer cache key is now a hash of the question, so the visitor's text is not kept in memory or on disk.
- Deploy: the image creates `/data` for the unprivileged user, the API compose file mounts the volume and waits up to 45 s for the final save, and Dependabot opens its version updates against `develop`.
- Docs: decision 21, the chat flow and the deployment runbook (state volume, new variables, release steps).

### Upgrading
- No database migration.
- Optional: in `deploy/api/.env`, replace `DAILY_LLM_BUDGET` with `DAILY_TOKEN_BUDGET=150000`. The old line is ignored, and the default is the same value.
- The first start logs `state_not_found`; after the next restart it logs `state_restored`.

### Checks
- The Docker image was built and run with the production compose file (user, read-only root, volume, clean shutdown, restore, corrupt and unwritable state).
- Assistant evaluation of 2026-10-28 (`backend/evals/results/`): 34 of 34 attacks refused, none to review. Of the legitimate questions, 24 of 34 were measured, with 1 false positive (L18, as in 1.0.0) and 1 to review (L11, the model misspelled a company name).

### Known limits
- The per-visitor counters are not saved, so a deploy resets every visitor's allowance.
- The other limits of 1.0.0 stay: one process, 2 GB shared with Gedocs, and Gemini unused behind a DNS-only API host.

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

[Unreleased]: https://github.com/Joalregra/developer-portfolio/compare/v1.1.0...HEAD
[1.1.0]: https://github.com/Joalregra/developer-portfolio/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/Joalregra/developer-portfolio/releases/tag/v1.0.0
