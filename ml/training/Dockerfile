FROM python:3.11-slim

WORKDIR /opt/ml

# Dépendances (couche mise en cache tant que requirements.txt ne change pas)
COPY requirements.txt /opt/ml/requirements.txt
RUN pip install --no-cache-dir -r /opt/ml/requirements.txt

# Code nécessaire à l'entraînement : common.py (accès Postgres/MLflow),
# config.yaml, et les scripts train_*.py + l'API qui les orchestre.
COPY common.py config.yaml /opt/ml/
COPY training/ /opt/ml/training/

# Repli local pour les artefacts entraînés (partagé avec ml-serving via le
# volume ./ml/models monté par docker-compose.yml sur les deux services).
RUN mkdir -p /opt/ml/models

ENV PYTHONUNBUFFERED=1
EXPOSE 8600

CMD ["uvicorn", "training.training_api:app", "--host", "0.0.0.0", "--port", "8600"]