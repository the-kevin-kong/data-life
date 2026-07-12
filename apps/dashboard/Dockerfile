# Streamlit dashboard image for the NAS. Build context is the repo root:
#   docker build -f apps/dashboard/Dockerfile -t data-life-dashboard .
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

COPY . /app
RUN uv sync --package dashboard --no-dev --frozen

EXPOSE 8501
CMD ["uv", "run", "--no-sync", "--package", "dashboard", \
     "streamlit", "run", "apps/dashboard/src/dl_dashboard/streamlit_app.py", \
     "--server.port=8501", "--server.address=0.0.0.0", \
     "--server.headless=true", "--browser.gatherUsageStats=false"]
