# FlowMatch backend - Flask API (stdlib sqlite3, no ORM).
# Runs under gunicorn in production; `python -m app.main` still works for
# local dev (see README.md).
FROM python:3.11-slim

# Keeps python from writing .pyc files / buffering stdout, useful in containers.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# The seeded demo database is regenerated on first run (see app/seed.py).
# Point FLOWMATCH_DB_PATH at a mounted volume to persist it across restarts.
ENV FLOWMATCH_DB_PATH=/data/flowmatch.db
RUN mkdir -p /data

# Runs as a non-root user, per standard container hardening practice.
RUN useradd --uid 10001 --create-home appuser \
    && chown -R appuser:appuser /app /data
USER appuser

EXPOSE 8100

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8100/api/health').read()" || exit 1

CMD ["gunicorn", "--bind", "0.0.0.0:8100", "--workers", "2", "--threads", "4", "app.main:create_app()"]
