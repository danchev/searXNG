# Stage 1: Builder
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

# Install dependencies first (optimizes Docker layer caching)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Copy project files and install the project itself
COPY searxng/ ./searxng/
COPY README.md LICENSE ./
RUN uv sync --frozen --no-dev

# Stage 2: Production Runtime
FROM python:3.12-slim-bookworm

# Standard OCI Image Labels (Specifically useful for GitHub Container Registry)
LABEL org.opencontainers.image.title="SearXNG MCP Server"
LABEL org.opencontainers.image.description="MCP server that provides network search capabilities for models using SearXNG."
LABEL org.opencontainers.image.source="https://github.com/danchev/searXNG"
LABEL org.opencontainers.image.licenses="AGPL-3.0"

# Prevent Python from buffering stdout/stderr and writing pyc files
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Create a non-root user for security
RUN groupadd -r mcpuser && useradd -r -g mcpuser mcpuser && chown -R mcpuser:mcpuser /app

# Switch to the non-root user
USER mcpuser

# Copy the compiled virtual environment from the builder
COPY --from=builder --chown=mcpuser:mcpuser /app/.venv /app/.venv

# Put the virtual environment on the path
ENV PATH="/app/.venv/bin:$PATH"

# Expose the default Streamable HTTP port
EXPOSE 8000

# Set the entrypoint
ENTRYPOINT ["searxng"]
