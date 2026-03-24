FROM python:3.13-slim
WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy only the gateway's own pyproject + the root lockfile.
# The root uv.lock covers all workspace members, so uv can resolve
# the gateway package's deps from it without the other members present.
COPY pyproject.toml uv.lock ./
COPY gateway/pyproject.toml ./gateway/pyproject.toml

# Install only the gateway package and its dependencies.
# --no-install-workspace prevents uv from trying to install the other
# workspace members (cyclones, earthquakes, etc.) which aren't copied in.
RUN uv sync --frozen --no-dev --no-install-workspace --package gateway

COPY gateway/main.py ./gateway/main.py

CMD ["uv", "run", "--package", "gateway", "uvicorn", "gateway.main:app", "--host", "0.0.0.0", "--port", "8000"]