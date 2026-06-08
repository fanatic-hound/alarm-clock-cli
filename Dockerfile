# ─── Stage 1: Builder ─────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /app

# Install SDL2 build-time libs (required for pygame if enabled)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Install into an isolated prefix so we can copy cleanly
RUN pip install --prefix=/install --no-cache-dir \
    typer rich pydantic python-dateutil apscheduler \
    && pip install --prefix=/install --no-cache-dir \
    "pydantic==1.10.21"

# ─── Stage 2: Runtime ─────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

WORKDIR /app

# Copy installed Python packages from builder stage
COPY --from=builder /install /usr/local

# Copy application source and package metadata
COPY alarm_cli/ ./alarm_cli/
COPY pyproject.toml ./

# Install the package (editable so entry_point 'alarm' is registered)
RUN pip install --no-cache-dir -e . \
    && pip install --no-cache-dir pydantic==1.10.21

# Create default data directory
RUN mkdir -p /root/.misty_nova

# ─── Default: run daemon in foreground (no detach needed inside Docker) ────────
# For CLI commands, override with:
#   docker run ... alarm list
#   docker run ... alarm add "Meeting" 9am
CMD ["python", "-m", "alarm_cli.daemon.runner", "--foreground"]

# ─── Labels ───────────────────────────────────────────────────────────────────
LABEL org.opencontainers.image.title="Misty Nova Alarm CLI"
LABEL org.opencontainers.image.description="Production-quality CLI alarm clock with background daemon"
LABEL org.opencontainers.image.version="1.0.0"
