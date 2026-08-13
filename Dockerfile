FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

WORKDIR /app

RUN addgroup --system app && adduser --system --ingroup app app

COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir .

FROM base AS test

RUN pip install --no-cache-dir ".[dev]"
COPY tests ./tests
COPY data ./data

USER app

CMD ["python", "-m", "pytest", "-p", "no:cacheprovider"]

FROM base AS runtime

USER app

CMD ["uvicorn", "nhl_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
