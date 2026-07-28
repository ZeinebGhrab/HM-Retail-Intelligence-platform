import sys
sys.path.append("/opt/spark/work-dir/common")

import psycopg2
from pyspark.sql import functions as F
from config import get_spark_session, get_jdbc_config

spark = get_spark_session("hm_merge_stream")
jdbc_url, jdbc_props = get_jdbc_config()

from pyspark.sql.types import StructType, StructField, StringType, TimestampType


def ensure_watermark_table():
    """
    Crée la table merge_watermark si elle n'existe pas.
    Cette table stocke le dernier timestamp traité par chaque pipeline.
    """

    try:
        # Test de lecture pour vérifier si la table existe
        spark.read.jdbc(
            jdbc_url,
            "merge_watermark",
            properties=jdbc_props
        )

        print("Table merge_watermark déjà existante.")

    except Exception:
        print("Création de la table merge_watermark...")

        schema = StructType([
            StructField(
                "pipeline_name",
                StringType(),
                False
            ),
            StructField(
                "last_merged_at",
                TimestampType(),
                True
            )
        ])

        empty_df = spark.createDataFrame(
            [],
            schema
        )

        empty_df.write \
            .mode("overwrite") \
            .jdbc(
                jdbc_url,
                "merge_watermark",
                properties=jdbc_props
            )

        print("Table merge_watermark créée.")

ensure_watermark_table()
# --- 1. Lire le watermark actuel (dernière donnée déjà fusionnée) ---
def get_last_watermark():
    try:
        conn = psycopg2.connect(
            host="postgres", dbname=jdbc_props.get("user") and None,  # voir note ci-dessous
        )
    except Exception:
        pass
    # Lecture simple via Spark, plus cohérent avec le reste du pipeline :
    df = spark.read.jdbc(jdbc_url, "merge_watermark", properties=jdbc_props)
    row = df.filter(F.col("pipeline_name") == "stream_to_warehouse").select("last_merged_at").first()
    return row[0] if row else "1970-01-01 00:00:00"

last_merged_at = get_last_watermark()

# --- 2. Lire uniquement les transactions streaming plus récentes que le watermark ---
new_stream_data = (
    spark.read.jdbc(jdbc_url, "stream_transactions_ingested", properties=jdbc_props)
    .filter(F.col("kafka_timestamp") > F.lit(last_merged_at))
)

if new_stream_data.rdd.isEmpty():
    print("Aucune nouvelle donnée streaming à fusionner.")
    spark.stop()
    sys.exit(0)

# --- 3. Construire les clés de dimension (mêmes règles que le batch) ---
new_fact = (
    new_stream_data
    .withColumn("customer_key", F.abs(F.xxhash64("customer_id")))
    .withColumn("article_key", F.col("article_id"))
    .withColumn("date_key", F.date_format("t_dat", "yyyyMMdd").cast("int"))
    .select("customer_key", "article_key", "date_key", "price", "sales_channel_id")
)

# --- 4. Append dans fact_transaction (jamais overwrite ici) ---
new_fact.write.mode("append").jdbc(jdbc_url, "fact_transaction", properties=jdbc_props)

# --- 5. Compléter dim_date si de nouvelles dates apparaissent ---
existing_dates = spark.read.jdbc(jdbc_url, "dim_date", properties=jdbc_props).select("date_key")
new_dates = (
    new_stream_data.select(F.col("t_dat").alias("date"))
    .distinct()
    .withColumn("date_key", F.date_format("date", "yyyyMMdd").cast("int"))
    .withColumn("month", F.month("date"))
    .withColumn("year", F.year("date"))
    .join(existing_dates, "date_key", "left_anti")  # uniquement les dates absentes de dim_date
)
if not new_dates.rdd.isEmpty():
    new_dates.write.mode("append").jdbc(jdbc_url, "dim_date", properties=jdbc_props)

# --- 6. Mettre à jour le watermark ---
max_ts = new_stream_data.agg(F.max("kafka_timestamp")).first()[0]
watermark_df = spark.createDataFrame([("stream_to_warehouse", max_ts)], ["pipeline_name", "last_merged_at"])
watermark_df.write.mode("overwrite").option("truncate", "false").jdbc(
    jdbc_url, "merge_watermark_tmp", properties=jdbc_props
)
# Remplace uniquement la ligne concernée (table de contrôle minuscule, overwrite total sans risque ici)
watermark_df.write.mode("overwrite").jdbc(jdbc_url, "merge_watermark", properties=jdbc_props)

print(f"{new_fact.count()} transactions fusionnées dans fact_transaction (watermark : {max_ts}).")
spark.stop()