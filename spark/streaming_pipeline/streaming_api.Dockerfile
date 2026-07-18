FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y docker.io && \
    pip install --no-cache-dir \
    fastapi \
    uvicorn && \
    rm -rf /var/lib/apt/lists/*

COPY streaming_pipeline/streaming_api.py .

EXPOSE 8000

CMD ["uvicorn", "streaming_api:app", "--host", "0.0.0.0", "--port", "8000"]