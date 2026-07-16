import os
from dotenv import load_dotenv
from pyspark.sql import SparkSession

load_dotenv("/opt/spark/work-dir/.env")

def get_spark_session(app_name="hm_pipeline"):
    return (
        SparkSession.builder
        .appName(app_name)
        .master("spark://spark-master:7077")
        .config(
            "spark.sql.adaptive.enabled",
            "false"
        )
        .config(
            "spark.serializer",
            "org.apache.spark.serializer.KryoSerializer"
        )
        .config(
            "spark.sql.streaming.forceDeleteTempCheckpointLocation",
            "true"
        )
        .config("spark.jars", "/opt/spark/jars/postgresql-42.7.3.jar")
        .getOrCreate()
    )

def get_jdbc_config():
    host = "postgres"  # nom du service dans le réseau docker
    port = os.environ.get("POSTGRES_PORT", "5432")
    db = os.environ.get("POSTGRES_DB")
    url = f"jdbc:postgresql://{host}:{port}/{db}"
    props = {
        "user": os.environ.get("POSTGRES_USER"),
        "password": os.environ.get("POSTGRES_PASSWORD"),
        "driver": "org.postgresql.Driver",
    }
    return url, props

def get_kafka_config():
    return {
        "bootstrap.servers": "kafka:29092",  # listener interne Docker, pas localhost:9092
        "topic": os.environ.get("KAFKA_TOPIC", "transactions.raw"),
    }