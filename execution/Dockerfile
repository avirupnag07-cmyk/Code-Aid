FROM python:3.9.21-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN python -m pip install --no-cache-dir pytest==8.3.4 \
    && useradd --create-home --uid 65532 --shell /usr/sbin/nologin runner

USER runner
WORKDIR /workspace

ENTRYPOINT ["python"]
