import sys
sys.path.append("/opt/spark/work-dir/common")
sys.path.append("/opt/spark/work-dir/streaming_pipeline/utils")

from pyspark.sql import functions as F
from config import get_spark_session, get_jdbc_config, get_kafka_config
from schemas import customers_schema, articles_schema
from validation import parse_kafka_messages, split_valid_invalid
# from cleaning import enrich_with_dimensions

spark = get_spark_session("hm_streaming_pipeline",executor_cores="2",executor_memory="512m")
spark.sparkContext.setLogLevel("WARN")

jdbc_url, jdbc_props = get_jdbc_config()
kafka_conf = get_kafka_config()

# --- Dimensions statiques, chargées une fois au démarrage (pas en flux) ---
# customers_static = spark.read.csv("/opt/spark/work-dir/data/raw/customers.csv", header=True, schema=customers_schema)
# articles_static = spark.read.csv("/opt/spark/work-dir/data/raw/articles.csv", header=True, schema=articles_schema)

# --- Lecture du flux Kafka ---
raw_stream = (
    spark.readStream
    .format("kafka")
    .option("kafka.bootstrap.servers", kafka_conf["bootstrap.servers"])
    .option("subscribe", kafka_conf["topic"])
    .option("startingOffsets", "latest")   # ne rejoue pas tout l'historique du topic à chaque redémarrage
    .option("failOnDataLoss", "false")
    .load()
)

parsed = parse_kafka_messages(raw_stream)
parsed.writeStream \
    .format("console") \
    .option("truncate", False) \
    .start()
valid_df, rejected_df = split_valid_invalid(parsed)
valid_df.writeStream \
    .format("console") \
    .option("truncate", False) \
    .start()
# enriched_df = enrich_with_dimensions(valid_df, customers_static, articles_static)

# Cette fonction est appelée automatiquement par Spark à chaque micro-batch.
# Elle prend les transactions valides traitées pendant une période donnée
# et les insère dans PostgreSQL en mode append.
# Le paramètre batch_id permet d'identifier chaque micro-batch exécuté.

def write_batch_to_postgres(batch_df, batch_id):

    print(f"========== Batch {batch_id} ==========")

    if len(batch_df.take(1)) == 0:
        print("Batch vide")
        return

    (
        batch_df.select(
            "customer_id",
            "article_id",
            "t_dat",
            "price",
            "sales_channel_id",
            "kafka_timestamp"
    )
        .write
        .mode("append")
        .jdbc(
            url=jdbc_url,
            table="stream_transactions_ingested",
            properties=jdbc_props
        )
    )

    print("Batch terminé")


# Cette fonction gère les messages qui ne respectent pas les règles
# de validation.
# Au lieu de supprimer ces données, elles sont stockées dans une table
# dédiée afin de pouvoir analyser les erreurs plus tard.
def write_rejected_to_postgres(batch_df, batch_id):
    print(f"========== Batch {batch_id} ==========")

    if len(batch_df.take(1)) == 0:
        print("Batch vide")
        return
    (
            batch_df.write.mode("append")
            .jdbc(url=jdbc_url, table="stream_transactions_rejected", properties=jdbc_props)
    )
    print(f"[batch {batch_id}] messages rejetés.")

# Création du flux d'écriture des transactions valides.
# Toutes les 30 secondes, Spark récupère les nouvelles données Kafka,
# crée un micro-batch et appelle la fonction write_batch_to_postgres()
# pour enregistrer ces données dans PostgreSQL.
query_valid = (
    valid_df.writeStream
    .foreachBatch(write_batch_to_postgres)
    .option("checkpointLocation", "/opt/spark/work-dir/checkpoint/valid")
    .trigger(processingTime="30 seconds")
    .start()
)

query_rejected = (
    rejected_df.writeStream
    .foreachBatch(write_rejected_to_postgres)
    .option("checkpointLocation", "/opt/spark/work-dir/checkpoint/rejected")
    .trigger(processingTime="30 seconds")
    .start()
)

spark.streams.awaitAnyTermination()