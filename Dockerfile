FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml .
COPY ingestion ingestion
COPY storage storage
COPY utils utils
COPY api api
COPY config.py main.py ./
COPY data data
COPY tests tests
RUN pip install --no-cache-dir '.[api,postgres,test]'
EXPOSE 8000
CMD ["uvicorn", "api.routes:app", "--host", "0.0.0.0", "--port", "8000"]
