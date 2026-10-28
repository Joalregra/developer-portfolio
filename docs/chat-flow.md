# How the chat works

`POST /api/chat` answers recruiters' questions about Johan, and nothing else. This page explains the path of one question, what happens when something fails, and what to watch when it runs. The rules behind it come from a private backend design document: its `ERR-`, `DATA-` and `PI-` ids appear in code comments.

## Path of one question

```mermaid
flowchart TD
  Q[Question] --> S{Chat switched on?}
  S -- no --> P[503 assistant_paused]
  S -- yes --> R{Rate limit per visitor}
  R -- over --> L[429 rate_limited + Retry-After]
  R -- ok --> C[Clean the text<br/>mask emails and phone numbers<br/>drop the browser's assistant turns]
  C -- nothing left --> E[422 invalid_request]
  C --> K{Quick-question button?}
  K -- yes --> QA[Fixed answer from the knowledge file<br/>no model, no budget]
  K -- no --> H{Known attack phrase?}
  H -- yes --> X[200 refused + strike for the visitor]
  H -- no --> AC{Same question already answered?<br/>no history, same language}
  AC -- yes --> CA[200 stored answer<br/>no model, no budget]
  AC -- no --> G{Prompt Guard 2 score}
  G -- attack --> X2[200 refused]
  G -- ok or unavailable --> Q{Visitor has questions<br/>left for the model?<br/>3 an hour, 6 a day}
  Q -- no --> QL[429 question_limit + Retry-After]
  Q -- yes --> B{Token budget left today?}
  B -- no --> P
  B -- yes --> M[Groq gpt-oss-120b<br/>falls back to Gemini]
  M --> V{Output validator}
  V -- off topic or leak --> X3[200 refused, fixed text]
  V -- ok --> A[200 answer + section]
  QA --> LOG[(Log row, written after the answer)]
  CA --> LOG
  X --> LOG
  X2 --> LOG
  X3 --> LOG
  A --> LOG
```

A refusal is still HTTP 200 with `refused: true`. The text of a refusal is written by the code, never by the model, and the visitor is never told which rule fired.

## What each layer is for

| Layer | Stops | Where |
|---|---|---|
| Rate limit and strikes | Abuse of the endpoint. A visitor is an IPv4 address or an IPv6 /56 block: 10 requests a minute and 30 a day, counting every kind of request | `services/rate_limit.py` (`RateLimiter`) |
| Model quota per visitor | One person burning the free quota. Only a question that would reach a model counts: 3 an hour and 6 a day (`MODEL_CALLS_PER_VISITOR_HOUR`, `MODEL_CALLS_PER_VISITOR_DAY`). It runs after the cache and Prompt Guard, so quick buttons, repeated questions and refusals never spend it. The question is given back if the model failed through no fault of the visitor (no provider, request error, timeout, budget spent); an invalid answer is not given back, because it spent tokens. In memory only: no address reaches the disk | `services/rate_limit.py` (`ModelQuota`) |
| Daily token budget | The whole site burning the free quota. 150,000 tokens a day (`DAILY_TOKEN_BUDGET`), about 27 uncached questions, which leaves room for the evals and manual tests on the same key. Each call reserves an estimate and settles to the real usage (prompt minus cached tokens, plus the answer) | `services/budget.py`, `services/llm/router.py` |
| Cleaning | Invisible and blank filler characters, look-alike letters, personal data going to a provider | `services/guard.py` |
| Phrase list | Known injection phrases in Spanish and English, encoded blocks, scrambled words, Cyrillic or Greek look-alikes, phrases hidden by spaces or fillers | `services/guard_patterns.py` |
| Answer cache | Calling a model twice for the same question. It keeps only answers the output validator accepted, for questions asked without history, for a day (`ANSWER_CACHE_TTL_SECONDS`) and up to 500 entries. It is checked after the phrase list, so an attack is still refused, and before Prompt Guard, because a stored question already passed it. It survives a restart through the state file (see below), and the key is a hash of the question, so the visitor's text is never stored | `services/answer_cache.py` |
| Prompt Guard 2 | Attacks the list does not know. Long messages go in overlapping pieces of 450 characters, and one bad piece blocks | `services/llm/groq_provider.py` |
| Prompt structure | The visitor's text never enters the system message and cannot close a tag. Only the visitor's earlier questions are sent: the browser also sends the assistant's earlier answers, but it could have invented them, so they never reach the model | `services/prompt.py` |
| Output validator | A leaked prompt or key (checked before and after removing markup, ignoring case and spacing for the canary), links to other sites, HTML, off-topic answers | `services/output_validator.py` |

No single layer is enough. The real protection is that the assistant has no tools, no secrets in its prompt and nothing to act on: the worst a successful attack can do is make it say something off topic, and the validator checks for that.

## When something fails

| Failure | What the visitor gets | What is logged |
|---|---|---|
| Invalid request, or a question with no text left after cleaning | 422 `invalid_request` | |
| Too many requests | 429 `rate_limited` + `Retry-After` | |
| The visitor used up their questions for the model | 429 `question_limit` + `Retry-After`. Quick buttons and repeated questions still work | `visitor_model_quota_reached` with `window` (`hour` or `day`), without the address |
| Switch off, or token budget spent | 503 `assistant_paused` | `budget_used` at 50, 80 and 100 % of the tokens |
| Attack phrase detected (phrase list) | 200 `refused: true` and a strike for the visitor | `injection_attempt`, then `ip_blocked` after 3 in 10 min |
| Attack detected by Prompt Guard | 200 `refused: true`, with no strike (the classifier has more false positives than the list) | `chat_completed` with `guard_result: classifier` |
| Prompt Guard down or slow | The question goes on | `guard_unavailable` |
| Groq 429 | The wait is remembered for everyone, so later visitors do not call Groq during it. Waits for it (up to 5 s with a fallback, 20 s without, as many times as the deadline allows), or goes to Gemini | `provider_failed` with `retry_after`, `provider_queue_wait` |
| Groq daily quota spent | Gemini, and Groq is paused until its reset. A 429 is also read as daily when it asks for more than 2 minutes | `provider_failed`, `provider_paused` |
| Groq 5xx, timeout, request too large | Gemini | `provider_failed` |
| Groq 400, 401, 403 or 404 (our bug, key or model name) | 503, no fallback | ERROR `provider_request_failed` |
| No provider can answer | 503 `assistant_unavailable` + `Retry-After` if known | `fallback_ineligible` when only the country blocked Gemini |
| A rating cannot be stored | 503 `feedback_unavailable`. The chat is not affected | `feedback_failed` |
| 25 s total exceeded | 503 `assistant_unavailable` | ERROR `deadline_exceeded` |
| Invalid or cut-off model output | 502 `invalid_model_output` (one retry first, none if cut off) | `provider_failed` |
| Answer leaks the prompt or a key | 200 refusal | ERROR `prompt_leak_blocked` |
| Database down | Nothing, the answer is already sent | `chat_log_failed`, `chat_log_dropped` |

The visitor's question never appears in a log line, only its length.

Only one call to Groq runs at a time, and the lock is never held while waiting. A refused call (429) does no work, so its reservation is returned to the token budget. Any other failure keeps it, because the call may have reached the model.

## State that survives a deploy

The answer cache and today's token count are copied to `STATE_FILE` (`/data/state.json`, on the `api_state` volume in production) every 30 seconds when something changed, and once more when the process stops (the deploy sends SIGTERM and waits up to 45 s). At most 30 s are lost if the process dies. The chat never depends on the file: if it is missing, corrupt, from another version or unwritable, the chat starts empty and logs `state_load_failed` or `state_save_failed` once.

- The file holds validated answers keyed by a hash of the question, and the day's token count. It holds no question text, no address and no per-visitor counter: those reset on every restart on purpose.
- The cache is tied to a fingerprint (sha256) of the system prompt, which covers the knowledge, the rules and the canary. If it changed, the saved answers are dropped (`state_cache_discarded`); the token count is kept, because the quota does not depend on the knowledge.
- A saved count is restored only if it is from the current UTC day.
- Without `STATE_FILE` (development, tests, the evals) everything stays in memory.

## The free Groq tier is the bottleneck

Measured on 2026-10-15 with the real prompt (about 5,100 tokens):

- The limit is 8,000 tokens per minute, so **one uncached question fits per minute**. A second one gets a 429 with `retry-after` of 13 to 16 s.
- Groq's prompt cache is best effort and works only some of the time. Cached tokens do not count toward the limit. Measured on 2026-10-20 and 21 with the same prompt: 2 of 14 real calls reported cached tokens, both 2,304 of about 5,200 (the rules and the first sections, in blocks of 256), and the rest reported none, even for identical questions a minute apart. Groq answered from two regions (`dls` and `yul`) in the same hour, which fits a cache kept per node. We cannot steer it: the system message is already byte for byte the same on every call, with the fixed text first. Do not plan the quota around it.
- The daily limit is 200,000 tokens, which is about 39 uncached questions a day at this size. Groq confirmed it on 2026-10-21: `tokens per day (TPD): Limit 200000, Used 195561, Requested 5543. Please try again in 7m56s`. The wait was minutes, not hours, so it looks like a rolling window rather than a reset at midnight. Cached tokens do not count, which is why a long run can fit more questions than that (48 questions on 2026-10-20 fitted), but it cannot be counted on. When it is spent the router moves to Gemini for visitors who may use it, and the evaluation set (`--country CO`) then mixes in Gemini answers: for a run that must measure Groq, use `--country none`.
- A repeated question does not reach Groq at all: the answer cache (`services/answer_cache.py`) serves it from memory, in a few milliseconds, with no tokens, no budget and no visitor quota. It only helps with exact repeats of questions asked without history, such as the ones suggested in the chat. Free text rarely repeats, so it is a small saving, not a fix for the quota. Since it now survives deploys, the suggested questions stay answered after each release.
- Quick-question buttons cost nothing: they never reach a model.
- Tokens are counted against `DAILY_TOKEN_BUDGET` (150,000), a margin below Groq's 200,000, and one visitor can spend at most 6 uncached questions a day, about a fifth of that budget. Groq's own limit can still trip first if the evals or manual tests spend the margin.

What the code does about it: a visitor who can use Gemini goes to Gemini at once. A visitor who cannot (EU, EEA, UK, Switzerland, or an unknown country) waits for the `retry-after`, up to 20 s. Beyond that they get a 503 with the contact email.

If this turns out to be too tight, the options are (any can be combined): shorten the knowledge so two questions fit in a minute, proxy the API host through Cloudflare (it is DNS only today, decision 20) so the country is known and Gemini can serve everyone outside the excluded regions, move Groq to a paid tier, or pay for Gemini and drop the regional rule. Each one is a decision for Johan; see `docs/decisions.md`.

## Where to look when it misbehaves

All of these are fields in the JSON logs on stdout.

| Symptom | Search for |
|---|---|
| "Always unavailable" | `provider_failed` and `fallback_ineligible` |
| Slow answers | `chat_completed` with a high `latency_ms`, and `cache_cold: true` |
| Is the answer cache working? | `chat_completed` with `status: answered_cached` (no `prompt_tokens`, `latency_ms` near 0) |
| Refusing normal questions | `chat_completed` with `status` `refused_off_topic` or `refused_injection` |
| Paused for the day | `budget_used` |
| A visitor says they cannot ask more | `visitor_model_quota_reached` (hour or day). The window slides: it frees up an hour after the oldest counted question |
| The state file | `state_not_found` (first start), `state_restored`, `state_cache_discarded`, `state_load_failed`, `state_save_failed` |
| One office blocked | `ip_blocked` (restart the process to clear it) |
| Nothing in the database | `chat_log_failed`, `chat_log_dropped` (logged once a minute) |
| A provider cut off for everyone | `provider_paused` (with the reason and the seconds) |
| Visitors queueing for Groq | `provider_queue_wait` |
| Ratings are lost | `feedback_failed` (database), `feedback_recorded` with `duplicate` (a repeated rating) |
| Old rows are not deleted | `chat_log_purged` (once a day) and `chat_log_purge_failed`; see the retention job in the README |

On Windows, start uvicorn with `--reload` while developing, or the log writes fail with `psycopg_needs_selector_event_loop`. Linux is not affected.
