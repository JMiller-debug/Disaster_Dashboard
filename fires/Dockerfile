FROM python:3.13-slim
WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
COPY ../shared /shared
COPY pyproject.toml ./
RUN uv sync --frozen --no-dev --no-install-project
COPY app/ ./app/
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8004"]