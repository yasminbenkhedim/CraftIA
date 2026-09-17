# ============================================================================
# INTERNAL DEPLOYMENT INFRASTRUCTURE — NEVER SHARE WITH CLIENTS
#
# CreateFlow AI is delivered as a HOSTED SaaS ONLY. This file exists to run the
# product on OUR OWN infrastructure. It is not a customer deliverable.
#
# Do NOT send this file, the image it builds, or any artifact derived from it to a
# customer, partner, or third party -- including for on-prem installs, self-hosted or
# air-gapped deployments, white-label/OEM builds, evaluation copies, or escrow.
#
# This is a LEGAL constraint, not a preference. The product depends on GPL-3.0
# components (phonemizer / espeak-ng, via the Kokoro TTS engine). GPL obligations are
# triggered by DISTRIBUTION, not by hosting. Handing any build to a third party would
# convey the work and activate those obligations, making the product non-compliant.
#
# See LICENSES.md (deployment banner and item R6') before any such deal is agreed.
# ============================================================================
# Multi-stage build for CraftAI API Server
FROM python:3.11-slim AS base

# Install system dependencies including FFmpeg
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsm6 \
    libxext6 \
    libgl1-mesa-glx \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install Python deps
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir celery[redis] redis prometheus_client opentelemetry-sdk opentelemetry-exporter-otlp edge-tts

# Copy application code
COPY backend/ ./backend/
COPY agents/ ./agents/

# Set environment
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health/live || exit 1

# Expose port
EXPOSE 8000

# Run API server
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
