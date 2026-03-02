#
--- L9_META ---
l9_schema: 1
origin: l9-template
engine: graph
layer: [docker]
tags: [L9_TEMPLATE, docker, dev]
owner: platform
status: active
--- /L9_META ---
─────────────────────────────────────────────────────────────
L9 Graph Cognitive Engine — Multi-stage Dockerfile
Stage 1: deps    — install Python packages
Stage 2: runtime — slim image with only what we need
─────────────────────────────────────────────────────────────

── Stage 1: Dependencies ──────────────────────────────────
FROM python:3.12-slim AS deps

WORKDIR /build
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

── Stage 2: Runtime ───────────────────────────────────────
FROM python:3.12-slim AS runtime

WORKDIR /app

Copy installed packages from deps stage
COPY --from=deps /install /usr/local

Copy application code
COPY engine/ /app/engine/
COPY domains/ /app/domains/

Copy entrypoint
COPY scripts/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

Non-root user
RUN groupadd -r l9 && useradd -r -g l9 -d /app -s /sbin/nologin l9
RUN chown -R l9:l9 /app
USER l9

EXPOSE 8000

Health check
HEALTHCHECK --interval=15s --timeout=5s --retries=3 \
    CMD python -c "import httpx; r=httpx.get('http://localhost:8000/v1/health'); exit(0 if r.status_code==200 else 1)"

ENTRYPOINT ["/app/entrypoint.sh"]
