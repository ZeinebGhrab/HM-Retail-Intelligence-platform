from pyspark.sql import functions as F
from pyspark.sql.types import StructType, StructField, StringType, DoubleType, LongType, IntegerType

# Schéma du message JSON reçu depuis Kafka (topic transactions.raw)
kafka_message_schema = StructType([
    StructField("t_dat", StringType(), True),
    StructField("customer_id", StringType(), True),
    StructField("article_id", LongType(), True),
    StructField("price", DoubleType(), True),
    StructField("sales_channel_id", IntegerType(), True),
])

def parse_kafka_messages(raw_stream_df):
    """Kafka livre value en binaire JSON : on le parse selon le schéma attendu."""
    return (
        raw_stream_df
        .selectExpr("CAST(value AS STRING) as json_value", "timestamp as kafka_timestamp")
        .withColumn("data", F.from_json(F.col("json_value"), kafka_message_schema))
        .select("data.*", "kafka_timestamp")
    )

def split_valid_invalid(parsed_df):
    """
    Sépare les messages valides des messages rejetés (dead-letter),
    plutôt que de les faire disparaître silencieusement.
    """
    is_valid = (
        F.col("customer_id").isNotNull()
        & F.col("article_id").isNotNull()
        & F.col("price").isNotNull()
        & (F.col("price") > 0)
        & F.col("t_dat").isNotNull()
    )
    valid_df = parsed_df.filter(is_valid).withColumn("t_dat", F.to_date("t_dat", "yyyy-MM-dd"))
    rejected_df = parsed_df.filter(~is_valid).withColumn("rejection_reason", F.lit("schema_or_value_invalid"))
    return valid_df, rejected_df