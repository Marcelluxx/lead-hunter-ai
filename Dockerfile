FROM ghcr.io/astral-sh/uv:0.11.15@sha256:e590846f4776907b254ac0f44b5b380347af5d90d668138ca7938d1b0c2f98d3 AS uv

FROM python:3.11.15-slim-bookworm@sha256:b18992999dbe963a45a8a4da40ac2b1975be1a776d939d098c647482bcad5cba AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

RUN useradd --create-home --uid 10001 leadhunter \
    && install -d -o leadhunter -g leadhunter /app
WORKDIR /app

COPY --from=uv /uv /uvx /bin/
COPY --chown=leadhunter:leadhunter pyproject.toml uv.lock ./
USER leadhunter
RUN uv sync --frozen --no-default-groups --no-install-project

COPY --chown=leadhunter:leadhunter . .

EXPOSE 8000
CMD ["uvicorn", "src.server:create_server_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
