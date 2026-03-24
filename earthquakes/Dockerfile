FROM python:3.13-slim
WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy shared package first so it can be installed as a local dep
COPY shared/ ./shared/

# Install dependencies in isolation — no workspace, no dev deps
COPY pyproject.toml uv.lock ./
COPY earthquakes/ ./earthquakes/
RUN uv sync --frozen --no-dev --package earthquakes-service

COPY earthquakes/app/ ./app/
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]