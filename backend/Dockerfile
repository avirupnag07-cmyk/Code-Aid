FROM python:3.9.21-slim-bookworm
ARG BUILDTYPE=production
ENV DOCKER_HOST=

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 CODE_AID_DATABASE=backend/data/code_aid.sqlite3 CODE_AID_STORAGE=backend/data/investigations CODE_AID_SAMPLES=samples


WORKDIR /app
RUN if [ "$BUILDTYPE" = "dev" ]; then \
        apt-get update && \
        apt-get install --no-install-recommends -y git ca-certificates docker.io && \
        rm -rf /var/lib/apt/lists/*; \
    else \
        apt-get update && \
        apt-get install --no-install-recommends -y git ca-certificates && \
        rm -rf /var/lib/apt/lists/*; \
    fi
COPY backend/requirements.lock /app/backend/requirements.lock
RUN python -m pip install --no-cache-dir -r /app/backend/requirements.lock
COPY backend /app/backend
COPY samples /app/samples

RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin codeaid \
    && mkdir -p /app/backend/data/investigations \
    && chown -R codeaid:codeaid /app
WORKDIR /app/backend
USER root
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "from urllib.request import urlopen; urlopen('http://127.0.0.1:8000/api/health', timeout=3)"
CMD ["sh", "-c", "exec python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]

