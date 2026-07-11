# Cloud Run Job image. Build context is the repo root:
#   docker build -f services/split-transactions/Dockerfile -t split-transactions .
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

COPY . /app
RUN uv sync --package split-transactions --no-dev --frozen

CMD ["uv", "run", "--no-sync", "--package", "split-transactions", "split-transactions"]
