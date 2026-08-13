FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml .
COPY nhl_pipeline nhl_pipeline
COPY data data
RUN pip install --no-cache-dir .[api]
EXPOSE 8000
CMD ["uvicorn", "nhl_pipeline.api:app", "--host", "0.0.0.0", "--port", "8000"]
