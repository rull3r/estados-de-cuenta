# syntax=docker/dockerfile:1

# ---------- etapa 1: construir el frontend ----------
FROM node:20-alpine AS frontend
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-fund --no-audit
COPY frontend/ ./
RUN npm run build

# ---------- etapa 2: backend + SPA ----------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    EDC_DATA_DIR=/data \
    EDC_FRONTEND_DIST=/srv/frontend/dist

WORKDIR /srv

RUN useradd --create-home --uid 10001 edc

COPY backend/ ./backend/
COPY README.md LICENSE ./
RUN pip install ./backend

COPY --from=frontend /build/frontend/dist ./frontend/dist

RUN mkdir -p /data && chown -R edc:edc /data /srv
USER edc

VOLUME ["/data"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/api/health')" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
