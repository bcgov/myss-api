# Stage 1: builder
FROM python:3.12-slim AS builder

WORKDIR /build

RUN pip install --upgrade pip

COPY pyproject.toml .
RUN pip install --no-cache-dir ".[dev]" --prefix=/install

COPY app/ app/
COPY alembic/ alembic/
COPY alembic.ini .

# Stage 2: runtime
FROM python:3.12-slim AS runtime

WORKDIR /app

# Create non-root user
RUN groupadd --system appgroup && \
    useradd --system --gid appgroup --no-create-home appuser

# Copy installed packages from builder
COPY --from=builder /install /usr/local
COPY --from=builder /build/app ./app
COPY --from=builder /build/alembic ./alembic
COPY --from=builder /build/alembic.ini .

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import httpx; r = httpx.get('http://localhost:8000/health'); r.raise_for_status()"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
