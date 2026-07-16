# Stage 1: Build dependencies
FROM python:3.11-slim-bookworm AS builder

ARG PIP_INDEX_URL=https://pypi.org/simple

ENV PIP_INDEX_URL=${PIP_INDEX_URL} \
    PIP_DEFAULT_TIMEOUT=120 \
    PIP_RETRIES=6 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build
COPY requirements.txt .
RUN set -eu; \
    if ! python -m pip install --no-cache-dir --prefix=/install -r requirements.txt; then \
        if [ "$PIP_INDEX_URL" = "https://pypi.org/simple" ]; then exit 1; fi; \
        echo "Primary Python package index unavailable; retrying with official PyPI"; \
        PIP_INDEX_URL=https://pypi.org/simple \
            python -m pip install --no-cache-dir --prefix=/install -r requirements.txt; \
    fi

# Stage 2: Production image
FROM python:3.11-slim-bookworm

# Ensure UTF-8 encoding for Chinese character support
ENV LANG=C.UTF-8 LC_ALL=C.UTF-8 PYTHONIOENCODING=utf-8

# Install ffmpeg for audio transcoding (webm -> mp3 before STT)
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Security: Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY . .

# Security: Change ownership and switch to non-root user
RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Health check for container orchestrators
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${PORT:-8000}/health')" || exit 1

CMD sh -c "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"
