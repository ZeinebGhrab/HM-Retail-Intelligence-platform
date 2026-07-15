FROM python:3.11-slim

WORKDIR /opt/ml

# Dépendances (couche mise en cache tant que requirements.txt ne change pas)
COPY requirements.txt /opt/ml/requirements.txt
RUN pip install --no-cache-dir -r /opt/ml/requirements.txt

# Code de la partie ML (training/common utilisés par l'API pour la config et le repli local)
COPY common.py config.yaml /opt/ml/
COPY serving/ /opt/ml/serving/

# Modèles locaux (repli hors MLflow Model Registry) — voir MLOPS_GUIDE.md
COPY models/ /opt/ml/models/

ENV PYTHONUNBUFFERED=1
EXPOSE 8500

CMD ["uvicorn", "serving.app:app", "--host", "0.0.0.0", "--port", "8500"]