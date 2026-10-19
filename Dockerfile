# Code-Aid backend image.
# Build from the repository root:
#   docker build --tag code-aid-api:0.1.0 .
# Run the API locally:
#   docker run --rm --publish 127.0.0.1:8000:8000 --volume code_aid_data:/app/backend/data code-aid-api:0.1.0
#
# Compose builds and serves the frontend locally with an /api reverse proxy.

FROM python:3.9.21-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    CODE_AID_DATABASE=/app/backend/data/code_aid.sqlite3 \
    CODE_AID_STORAGE=/app/backend/data/investigations \
    CODE_AID_SAMPLES=/app/samples \
    CODE_AID_ALLOWED_ORIGINS=http://localhost:5173

WORKDIR /app

# Keep OS package installation explicit and reproducible. The API image does
# not include the Docker socket or daemon; generated test execution stays
# unavailable unless a separately reviewed executor is configured.
RUN apt-get update \
    && apt-get install --no-install-recommends --yes ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.lock /app/backend/requirements.lock
RUN python -m pip install --no-cache-dir --requirement /app/backend/requirements.lock

COPY backend /app/backend
COPY samples /app/samples

RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin codeaid \
    && mkdir -p /app/backend/data/investigations \
    && chown --recursive codeaid:codeaid /app

WORKDIR /app/backend
USER codeaid
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "from urllib.request import urlopen; urlopen('http://127.0.0.1:8000/api/health', timeout=3)"

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
