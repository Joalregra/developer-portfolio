FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY knowledge ./knowledge

# /data holds the chat state file (STATE_FILE): the answer cache and the token budget. The owner
# is set here because a named volume copies it from the image the first time it is mounted.
RUN useradd --create-home --uid 10001 appuser \
    && mkdir /data \
    && chown appuser /data
USER appuser

EXPOSE 8000
# --no-server-header hides the uvicorn version. --timeout-graceful-shutdown lets a chat that is
# already running (up to 25 s) finish before a deploy stops the process. --proxy-headers makes
# uvicorn read X-Forwarded-For, but only from the addresses in FORWARDED_ALLOW_IPS: behind the
# shared Caddy, deploy/api/docker-compose.yml sets it to that container's fixed address, so the
# real client IP is used (SEC-03). One process only: the rate limits live in memory and the
# state file has a single writer (see docs/deploy.md).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--no-server-header", "--timeout-graceful-shutdown", "30"]
