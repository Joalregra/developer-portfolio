FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY knowledge ./knowledge

RUN useradd --create-home appuser
USER appuser

EXPOSE 8000
# --no-server-header hides the uvicorn version. --timeout-graceful-shutdown lets a chat that is
# already running (up to 25 s) finish before a deploy stops the process. Behind Caddy, set
# FORWARDED_ALLOW_IPS to the proxy address in the production compose file, so the real client
# IP is used (SEC-03).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-server-header", "--timeout-graceful-shutdown", "30"]
