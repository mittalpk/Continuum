FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock README.md ./
COPY src ./src

RUN uv sync --frozen --no-dev

ENV PORT=8080
EXPOSE 8080

CMD ["sh", "-c", "uv run uvicorn continuum.server:app --host 0.0.0.0 --port ${PORT}"]
