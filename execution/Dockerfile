FROM python:3.9.21-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY backend/requirements.lock /tmp/requirements.lock
RUN python -m pip install --no-cache-dir --requirement /tmp/requirements.lock \
    && rm /tmp/requirements.lock \
    && useradd --create-home --uid 65532 --shell /usr/sbin/nologin runner

USER runner
WORKDIR /workspace

# The backend supplies the complete command: python -m pytest ... .
# A CMD permits that override without prepending a second Python executable.
CMD ["python", "-m", "pytest", "--version"]
