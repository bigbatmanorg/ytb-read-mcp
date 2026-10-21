FROM ghcr.io/astral-sh/uv:0.10.9 AS uv
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_NO_PROGRESS=1 PATH="/app/.venv/bin:$PATH" YTB_DATA_DIR=/data
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg ca-certificates \
    && rm -rf /var/lib/apt/lists/*
# Official Deno is installed with the Python package dependencies via its wheel.
WORKDIR /app
COPY --from=uv /uv /uvx /bin/
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN uv sync --no-dev
RUN mkdir -p /data
EXPOSE 8001
CMD ["ytb-read-mcp", "serve", "--transport", "http", "--host", "0.0.0.0"]
