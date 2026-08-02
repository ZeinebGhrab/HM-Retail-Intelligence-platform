FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Installer Docker CLI
RUN apt-get update && \
    apt-get install -y --no-install-recommends docker-cli && \
    docker --version && \
    rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    fastapi \
    uvicorn

COPY job_trigger_api.py .

EXPOSE 8091

CMD ["uvicorn", "job_trigger_api:app", "--host", "0.0.0.0", "--port", "8091"]