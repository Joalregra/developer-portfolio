# Frontend

Bilingual (ES/EN) single-page portfolio with an AI assistant panel. React 19, TypeScript, Vite and Tailwind CSS v4. The build prerenders `/es/` and `/en/` to static HTML, which React then hydrates. The output deploys to Cloudflare Pages.

The page is built for recruiters and technical leads, who are often on a phone. It covers who Johan is, his projects, experience, skills, education and how to contact him. The assistant answers questions about him.

## Status

| Part                                                                    | State                                                                                          |
| ----------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| Sections: hero, projects, experience, about, skills, education, contact | Done                                                                                           |
| Spanish and English, light and dark theme                               | Done                                                                                           |
| Assistant UI (panel, quick questions, every error state)                | Done, waiting for the backend                                                                  |
| `POST /chat` endpoint                                                   | Not built yet. Until it exists, the panel shows "assistant unavailable" with the contact email |
| Domain                                                                  | Not bought yet. Set `VITE_SITE_URL` once it exists                                             |

## Requirements

Node 20 or newer.

## Commands

```bash
npm install
cp .env.example .env
npm run dev            # http://localhost:5173/es/ and /en/
npm run build          # type check, client build, server build and prerender of /es/ and /en/
npm run preview        # serve dist/
npm run lint
npm run format:check   # npm run format to fix
npm test               # Vitest + React Testing Library
npx vitest run src/sections/Hero.test.tsx -t "photo"   # one file or one test
```

## Environment variables

Every `VITE_` variable ends up in the public JavaScript bundle, so never put secrets in them. LLM keys live only in the backend.

| Variable        | Use                                                                                                                                                                                                     |
| --------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `VITE_API_URL`  | Backend URL. If it is empty, the assistant shows the "unavailable" state without making a request.                                                                                                      |
| `VITE_SITE_URL` | Public origin, for example `https://example.com`, with no trailing slash. At build time it adds canonical and hreflang tags, absolute Open Graph URLs and `sitemap.xml`. Leave it empty in development. |

## Project structure

```
frontend/
├── index.html, es/index.html, en/index.html   Entry pages. The root picks a language; /es/ and /en/ are prerendered
├── vite-plugin-locale-head.ts                 Per-language head: title, description, Open Graph, hreflang, JSON-LD, robots, sitemap
├── scripts/prerender.mjs                      Writes the rendered app into dist/es and dist/en
├── public/
│   ├── cv/        CV in PDF, one per language
│   ├── fonts/     Archivo, a single WOFF2 file (latin subset, weight 400-800, width 72-100) and its license
│   ├── img/       Portrait in WebP (144 and 240 px wide)
│   ├── og/        Open Graph images, 1200x630, one per language
│   └── favicon.svg, apple-touch-icon.png, 404.html
└── src/
    ├── app/App.tsx            Providers and section order, no logic
    ├── entry-server.tsx       renderToString entry, used only by the prerender step
    ├── sections/              Hero, Projects (+ ProjectRecord, diagrams/), Experience, About, Skills, Education, Contact
    ├── components/layout/     Header (navigation, language switch, theme toggle), Footer
    ├── components/ui/         Button, Badge, Section, ExternalLink, CopyEmailButton, icons, RichText, LinkedText
    ├── features/chat/         ChatProvider, ChatLauncher, ChatPanel (lazy chunk), useChat, Composer, MessageList, QuickQuestions
    ├── data/                  Content: profile.ts, projects.ts, profileSections.ts (experience, skills, education, certifications), nav.ts
    ├── i18n/                  es.ts, en.ts (UI text), meta.ts (title and description), LocaleProvider, locale.ts
    ├── hooks/                 useLocale, useTheme, useActiveSection, useFocusTrap, useMediaQuery
    ├── lib/                   format.ts (dates with Intl), storage.ts (guarded storage access), cx.ts
    ├── services/api.ts        The only layer that calls the backend: request<T>, ApiError, postChat
    └── styles/index.css       Tailwind v4 design tokens, fonts, theme colors, print and reduced-motion rules
```

## How it works

### Content

All facts about Johan live in `src/data/`, with one text per language (`Record<'es' | 'en', string>`). Interface labels live in `src/i18n/es.ts` and `en.ts`. `en.ts` is typed from `es.ts`, so a missing key fails the build.

The assistant's knowledge files (`backend/knowledge/ChatbotKnowledge.*.md`) must say the same things as `src/data/`. Update both together.

In project texts, wrapping a number in `**double asterisks**` renders it in bold.

### Languages

- Each language has its own URL: `/es/` and `/en/`. The root `/` chooses one in this order: the language saved in `localStorage`, then the browser languages (any `es*` means Spanish), then English. It then switches the URL.
- Switching language updates `<html lang>`, the title, the meta description and the URL. It keeps the `#hash` and the scroll position of the current section.
- Dates are formatted with `Intl.DateTimeFormat`, for example "abr 2026 – oct 2026" or "Apr 2026 – Oct 2026".

### Prerendering

`npm run build` runs `vite build`, then `vite build --ssr src/entry-server.tsx` (output in `node_modules/.cache/ssr`), then `scripts/prerender.mjs`. The content ends up in the HTML of `/es/` and `/en/`, so it is visible to crawlers and link previews and shows on first paint. `main.tsx` hydrates when the root already has content and renders from scratch otherwise.

Code that runs during render must work without `window`. Browser-only work belongs in effects or behind guards.

### Assistant

- The panel code is a separate chunk. It loads when the visitor opens it, hovers or focuses the launcher, or focuses the hero question field.
- On desktop it is a non-modal panel of 400 px. Below 640 px it is a full-screen modal dialog with trapped focus. Escape closes it, and focus returns to the control that opened it.
- Enter sends and Shift+Enter adds a new line. The 1000-character limit shows a counter from 800 characters.
- Error states: 429 shows the rate limit message, no connection shows the offline message, and anything else shows "unavailable" with a Retry button.
- The conversation is kept in `sessionStorage` until the visitor starts a new one.
- The request and response contract for the backend is in [`docs/architecture.md`](../docs/architecture.md). If an answer includes `sources`, the panel links each one ("Ver en: Proyectos").

### Visual system

- The concept is a records file: each project is a "record" with a metadata column (period, team, role, status) and the case study next to it.
- A single typeface, Archivo by Omnibus-Type: condensed width for headings, normal width for body text. Its Arial fallback is adjusted to the same metrics, so the font swap does not shift the layout.
- Colors are semantic tokens in `styles/index.css`. Light and dark themes are designed separately and checked against WCAG AA. The theme follows the system until the visitor picks one with the toggle, and that choice is saved.
- No animation library. Motion uses CSS only and is turned off under `prefers-reduced-motion`.
- Icons are inline SVG: strokes from Lucide (ISC license), plus the LinkedIn and GitHub logos from Simple Icons (CC0).

## Quality and performance

- TypeScript strict mode with `verbatimModuleSyntax` and `erasableSyntaxOnly`. Prettier: no semicolons, single quotes, 100 columns.
- The tests cover language selection, date formatting, header and mobile menu, hero, projects (order, NDA texts, no empty demo buttons), copying the email, theme, and every assistant state.
- CI (`.github/workflows/ci.yml`) runs format check, lint, tests and build on every push to `main` and on every pull request.
- Latest measurement (Lighthouse, mobile, compressed build): Performance 98-100, and Accessibility, Best Practices and SEO 100. LCP about 1.7 s, CLS 0. Initial JavaScript is about 89 KB gzip, and the chat chunk is about 2.6 KB gzip.

## Pending

- Implement `POST /chat` in the backend.
- Buy the domain and set `VITE_SITE_URL`.
- Replace the temporary portrait in `public/img/` with a recent professional photo (keep the two sizes and the 3:4 ratio).
- Add verification links to the Globant certificates if they become available (`verifyUrl` in `src/data/profileSections.ts`). Only the Anthropic one has one today.
