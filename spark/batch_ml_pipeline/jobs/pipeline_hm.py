
import sys
sys.path.append("/opt/spark/work-dir/batch_ml_pipeline/utils")
sys.path.append("/opt/spark/work-dir/common")
import argparse
from pyspark.sql import functions as F

from config import get_spark_session, get_jdbc_config
from schemas import transactions_schema, customers_schema, articles_schema
from cleaning import clean_transactions, clean_customers, clean_articles
from features import (
    compute_customer_features,
    compute_products_performance,
    compute_daily_sales,
    compute_segment_summary,
)

spark = get_spark_session("hm_pipeline")
parser = argparse.ArgumentParser()
parser.add_argument("--source", choices=["csv", "warehouse"], default="csv")
args = parser.parse_args()
jdbc_url, jdbc_props = get_jdbc_config()
if args.source == "csv":
# ========== ETAPE 1 : INGESTION ==========
  customers_df = spark.read.csv("/opt/spark/work-dir/data/raw/customers.csv", header=True, schema=customers_schema)
  articles_df = spark.read.csv("/opt/spark/work-dir/data/raw/articles.csv", header=True, schema=articles_schema)
  transactions_df = spark.read.csv("/opt/spark/work-dir/data/raw/transactions_train.csv", header=True, schema=transactions_schema)

# ========== ETAPE 2 : DATA CLEANING ==========
  transactions_clean = clean_transactions(transactions_df)
  customers_clean = clean_customers(customers_df)
  articles_clean = clean_articles(articles_df)

# ========== ETAPE 3 : JOINTURES ==========
  master_dataset = (
    transactions_clean
    .join(F.broadcast(customers_clean), "customer_id", "left")
    .join(F.broadcast(articles_clean), "article_id", "left")
  )
else:  # warehouse : recalcul périodique incluant les données streaming fusionnées
    master_dataset = (
        spark.read.jdbc(jdbc_url, "fact_transaction", properties=jdbc_props)
        .join(spark.read.jdbc(jdbc_url, "dim_customer", properties=jdbc_props), "customer_key")
        .join(spark.read.jdbc(jdbc_url, "dim_article", properties=jdbc_props), "article_key")
    )
    customers_clean = spark.read.jdbc(jdbc_url, "dim_customer", properties=jdbc_props)

# ========== ETAPE 4 : FEATURE ENGINEERING ==========
customers_features_train = compute_customer_features(master_dataset, customers_clean)
products_performance = compute_products_performance(master_dataset, articles_clean)
daily_sales = compute_daily_sales(master_dataset)
customer_segments_summary = compute_segment_summary(customers_features_train)

# ========== ETAPE 5 : STOCKAGE (Data Warehouse uniquement) ==========

# --- Dimensions ---
dim_customer = (
    customers_clean.select(
        "customer_id", "age", "age_group", "club_member_status",
        "fashion_news_frequency", "postal_code"
    )
    .withColumn("customer_key", F.abs(F.crc32(F.col("customer_id").cast("binary"))))
)

dim_article = (
    articles_clean.select(
        "article_id", "product_group_name", "product_type_name",
        "department_name", "colour_group_name", "index_name", "section_name"
    )
    .withColumn("article_key", F.col("article_id"))
)

dim_date = (
    master_dataset.select("t_dat").distinct()
    .withColumn("date_key", F.date_format("t_dat", "yyyyMMdd").cast("int"))
    .withColumn("month", F.month("t_dat"))
    .withColumn("year", F.year("t_dat"))
    .withColumnRenamed("t_dat", "date")
)

# --- Fact ---
fact_transaction = (
    master_dataset
    .withColumn("customer_key", F.abs(F.crc32(F.col("customer_id").cast("binary"))))
    .withColumn("article_key", F.col("article_id"))
    .withColumn("date_key", F.date_format("t_dat", "yyyyMMdd").cast("int"))
    .select("customer_key", "article_key", "date_key", "price", "sales_channel_id")
)

# --- Marts dérivés ---
customers_features_train_wh = (
    customers_features_train
    .withColumn("customer_key", F.abs(F.crc32(F.col("customer_id").cast("binary"))))
    .drop("customer_id")
)

products_performance_wh = products_performance.withColumnRenamed("article_id", "article_key")

daily_sales_wh = (
    daily_sales
    .withColumn("date_key", F.date_format("t_dat", "yyyyMMdd").cast("int"))
    .drop("t_dat")
)

tables = {
    "dim_customer": dim_customer,
    "dim_article": dim_article,
    "dim_date": dim_date,
    "fact_transaction": fact_transaction,
    "customers_features_train": customers_features_train_wh,
    "products_performance": products_performance_wh,
    "daily_sales": daily_sales_wh,
    "customer_segments_summary": customer_segments_summary,
}
for name, df in tables.items():
    df.write.mode("overwrite").jdbc(url=jdbc_url, table=name, properties=jdbc_props)

print("Pipeline terminé : Data Warehouse mis à jour (star schema + marts dérivés).")
spark.stop()