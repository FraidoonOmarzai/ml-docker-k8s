# ──────────────────────────────────────────────────────────────────────────────
# Stage 1: Builder — install dependencies into a clean venv
# ──────────────────────────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build tools (needed for some scikit-learn native extensions)
# RUN apt-get update && apt-get install -y --no-install-recommends \
#     build-essential \
#     gcc \
#     gfortran \
#     libatlas-base-dev \
#     && rm -rf /var/lib/apt/lists/*

# Create a virtual environment to isolate dependencies
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy and install requirements first (layer caching — only rebuilds on changes)
COPY requirements-serve.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements-serve.txt


# ──────────────────────────────────────────────────────────────────────────────
# Stage 2: Runtime — lean final image, no build tools
# ──────────────────────────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

# Security: run as non-root user
RUN groupadd --gid 1001 mluser && \
    useradd --uid 1001 --gid mluser --no-create-home mluser

WORKDIR /app

# Copy the venv from builder (no pip/compilers in final image)
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code
COPY app/         ./app/
COPY model/       ./model/

# Set artifact path env var (can be overridden at runtime via k8s ConfigMap)
ENV ARTIFACTS_DIR=/app/model/artifacts
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Switch to non-root user
USER mluser

# Expose port
EXPOSE 8080

# Health check (Docker-level, before Kubernetes probes take over)
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" || exit 1

# Start server with Uvicorn — 2 workers, production settings
CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8080", \
     "--workers", "2", \
     "--log-level", "info", \
     "--access-log"]