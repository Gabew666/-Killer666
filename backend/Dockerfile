FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ATLAS_SCHEMA_MODE=migrations \
    ATLAS_CONTENT_MODE=real \
    PORT=8000

WORKDIR /opt/atlas/backend
COPY backend/requirements.txt ./requirements.txt
RUN --mount=type=secret,id=build_ca \
    if [ -f /run/secrets/build_ca ]; then export PIP_CERT=/run/secrets/build_ca; fi; \
    pip install --no-cache-dir -r requirements.txt \
    && useradd --create-home --uid 10001 atlas
COPY backend/app ./app
COPY backend/content ./content
COPY backend/alembic.ini ./alembic.ini
COPY backend/migrations ./migrations
COPY curricula /opt/atlas/curricula
RUN chmod -R a+rX /opt/atlas

USER atlas
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s \
    CMD python -c 'import os, urllib.request; urllib.request.urlopen("http://127.0.0.1:" + os.environ.get("PORT", "8000") + "/health", timeout=3)'
CMD ["sh", "-c", ": \"${ATLAS_DATABASE_URL:?Configure ATLAS_DATABASE_URL}\"; : \"${ATLAS_CORS_ORIGINS:?Configure ATLAS_CORS_ORIGINS}\"; alembic upgrade head; exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
