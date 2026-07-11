# Cloud Run Job image. Build context is the repo root:
#   docker build -f services/ingest-monarch/Dockerfile -t ingest-monarch .
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

COPY . /app
RUN uv sync --package ingest-monarch --no-dev --frozen

# Runs to completion, then exits. Cloud Run Job semantics.
CMD ["uv", "run", "--no-sync", "--package", "ingest-monarch", "ingest-monarch"]
