FROM python:3.11-slim

# Variables d'environnement
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Dossier de travail
WORKDIR /app

# Installer le client Docker
RUN apt-get update && \
    apt-get install -y --no-install-recommends docker.io && \
    rm -rf /var/lib/apt/lists/*

# Installer les dépendances Python
RUN pip install --no-cache-dir \
    fastapi \
    uvicorn

# Copier uniquement l'API
COPY job_trigger_api.py .

# Port exposé
EXPOSE 8091

# Lancer l'API
CMD ["uvicorn", "job_trigger_api:app", "--host", "0.0.0.0", "--port", "8091"]