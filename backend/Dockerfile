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
# Written under /tmp: the Helm Blueprint's default pod securityContext sets
# readOnlyRootFilesystem, so /data (baked into the image's read-only layer)
# is not actually writable at runtime. /tmp is backed by a writable emptyDir
# even under that policy. This means the DB does not persist across pod
# restarts, which is acceptable for this demo app (see app/seed.py).
ENV FLOWMATCH_DB_PATH=/tmp/flowmatch.db

# HOME=/tmp so gunicorn's control server (~/.gunicorn) also lands on the
# writable /tmp instead of the non-root user's read-only home directory.
ENV HOME=/tmp

# Runs as a non-root user, per standard container hardening practice.
RUN useradd --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8100

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8100/api/health').read()" || exit 1

CMD ["gunicorn", "--bind", "0.0.0.0:8100", "--workers", "2", "--threads", "4", "app.main:create_app()"]
