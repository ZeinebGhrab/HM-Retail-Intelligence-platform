FROM apache/spark:3.5.1
USER root

RUN apt-get update && \
    apt-get install -y python3-pip curl && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/requirements.txt
RUN pip3 install --no-cache-dir -r /tmp/requirements.txt

# --- Driver JDBC PostgreSQL, nécessaire pour écrire dans le Data Warehouse ---
RUN curl -L -o /opt/spark/jars/postgresql-42.7.3.jar \
    https://jdbc.postgresql.org/download/postgresql-42.7.3.jar

WORKDIR /opt/spark/work-dir

COPY jobs ./jobs
COPY utils ./utils

ENV PYTHONUNBUFFERED=1

CMD ["bash"]