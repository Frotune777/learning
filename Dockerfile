# ==============================================================================
# NSE Pipeline — Multi-stage Dockerfile
# ==============================================================================
# Stage 1: Builder — installs system deps + Python packages
# Stage 2: Runtime — lean image with only what's needed to run

# ---- Builder stage ----
FROM python:3.13-slim AS builder

# Install TA-Lib C library and build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    wget \
    libta-lib-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy dependency manifests only (for layer caching)
COPY pyproject.toml uv.lock ./

# Install into a virtual environment under /app/.venv
RUN uv sync --frozen --no-dev

# ---- Runtime stage ----
FROM python:3.13-slim AS runtime

# Install only the TA-Lib runtime (not build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libta-lib0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy source code
COPY src/ ./src/
COPY main.py ./

# Make sure the venv is on PATH
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app"

# Data directories (mount via docker volume in production)
RUN mkdir -p data/raw data/processed data/historical/1d

# Default: launch the interactive menu
ENTRYPOINT ["python", "main.py"]
CMD ["menu"]
