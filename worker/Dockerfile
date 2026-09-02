# Multi-stage Dockerfile for Celery Audio Analysis & Mastering Worker
FROM python:3.11-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY worker/requirements.txt .
COPY api/requirements.txt ./api-reqs.txt
RUN pip install --no-cache-dir --user -r requirements.txt -r api-reqs.txt

# Final runtime stage
FROM python:3.11-slim AS runner

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -u 10001 -m -s /bin/bash appuser

COPY --from=builder /root/.local /home/appuser/.local
COPY worker/ /app/worker/
COPY api/ /app/api/
COPY tests/ /app/tests/

ENV PATH=/home/appuser/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    STORAGE_DIR=/storage

RUN mkdir -p /storage && chown -R appuser:appuser /app /storage

USER appuser

CMD ["celery", "-A", "worker.celery_app", "worker", "--loglevel=info", "--concurrency=2", "-Q", "analysis-cpu,dsp-heavy,metadata-network,exports"]
