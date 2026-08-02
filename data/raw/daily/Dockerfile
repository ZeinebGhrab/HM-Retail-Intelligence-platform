FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY generate_daily_transactions.py generator_api.py ./

# Fichiers de référence H&M (articles.csv, customers.csv) et dossier de sortie
# journalière : à monter en volume au lancement du conteneur, ex.
#   -v /host/ref:/data/ref -v /host/daily:/data/daily
ENV ARTICLES_CSV=/data/raw/articles.csv
ENV CUSTOMERS_CSV=/data/raw/customers.csv
ENV OUTPUT_DIR=/data/raw/daily

EXPOSE 8089
CMD ["uvicorn", "generator_api:app", "--host", "0.0.0.0", "--port", "8089"]
