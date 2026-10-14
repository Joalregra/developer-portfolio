# Technical decisions

Short records of the main choices and why they were made.

## 1. Monorepo for frontend and backend
One repository, one README and one CI pipeline make the whole project reviewable in a single place.

## 2. Knowledge in the system prompt, no RAG
The knowledge file is a few thousand words, so it fits comfortably in the model context. A vector database would add cost and moving parts without improving answers. RAG would be reconsidered if the content grew beyond the context window.

## 3. Groq as primary LLM, Gemini as fallback
Both offer free tiers. The backend routes requests to Groq and fails over to Gemini when Groq is rate-limited or unavailable, so the assistant degrades gracefully instead of failing.

## 4. API keys only in the backend
Every `VITE_` variable is bundled into public JavaScript, so the frontend never holds secrets. The chat endpoint is rate-limited per IP to protect the free-tier quota.

## 5. Static frontend on Cloudflare Pages, backend in Docker on a VM
The portfolio is static and benefits from a CDN at no cost. The backend runs in a container behind Caddy, which provides automatic HTTPS.

## 6. PostgreSQL on Neon
The only stored data is an anonymous log of assistant questions. Neon's free tier is enough, and plain PostgreSQL keeps the project portable.
