FROM python:3.12-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy lockfile + project metadata first for layer caching
COPY pyproject.toml uv.lock ./

# Install deps into the system Python (no virtualenv needed in Docker)
RUN uv sync --frozen --no-dev --no-install-project

# Copy source
COPY app/ ./app/

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]