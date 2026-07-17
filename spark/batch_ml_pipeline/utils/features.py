from pyspark.sql import functions as F
from pyspark.sql.window import Window

DATASET_END = "2020-09-22"  # dernière date du dataset historique, pas current_date()
def compute_customer_features(master_dataset, customers_clean,source="history"):
    if source == "warehouse":
        # convertir date_key (20200922) en vraie date Spark
        master_dataset = master_dataset.withColumn(
            "purchase_date",
            F.to_date(
                F.col("date_key").cast("string"),
                "yyyyMMdd"
            )
        )

        date_column = "purchase_date"
        date_ref = F.current_date()

    else:
        date_column = "t_dat"
        date_ref = F.lit(DATASET_END).cast("date")
    
    # --- RFM de base : total_spend, n_transactions, first/last purchase
    customer_stats = (
        master_dataset.groupBy("customer_id")
        .agg(
            F.sum("price").alias("total_spend"),
            F.count("*").alias("n_transactions"),
            F.min(date_column).alias("first_purchase"),
            F.max(date_column).alias("last_purchase"),
            F.countDistinct("product_group_name").alias("n_distinct_categories"),
        )
    )

    customer_features = (
        customer_stats
        .withColumn("recency_days", F.datediff(date_ref, F.col("last_purchase")))
        .withColumn("tenure_days", F.datediff(F.col("last_purchase"), F.col("first_purchase")))
        .withColumn("avg_basket_value", F.round(F.col("total_spend") / F.col("n_transactions"), 4))
        .withColumn(
            "purchase_frequency_per_month",
            F.round(F.col("n_transactions") / ((F.col("tenure_days") + 1) / F.lit(30)), 3)
        )
    )

    # --- segment_valeur : quartiles de total_spend via approxQuantile ---
    q1, q2, q3 = customer_features.approxQuantile("total_spend", [0.25, 0.5, 0.75], 0.01)

    customer_features = customer_features.withColumn(
        "segment_valeur",
        F.when(F.col("total_spend") <= q1, "Bas (Q1)")
         .when(F.col("total_spend") <= q2, "Moyen-bas (Q2)")
         .when(F.col("total_spend") <= q3, "Moyen-haut (Q3)")
         .otherwise("Haut (Q4 - VIP)")
    )

    # --- Fusion avec les attributs démographiques nettoyés ---
    customers_features_train = customer_features.join(
        customers_clean.select(
            "customer_id", "age", "age_group", "club_member_status",
            "fashion_news_frequency", "postal_code"
        ),
        "customer_id", "left"
    )
    return customers_features_train
#  tables d'agrégation pour le RAG/dashboard
def compute_products_performance(master_dataset, articles_clean):
    return (
        master_dataset.groupBy("article_id")
        .agg(F.count("*").alias("n_sales"))
        .join(
            articles_clean.select(
                "article_id", "prod_name", "product_group_name", "department_name", "index_name"
            ),
            "article_id", "left"
        )
        .orderBy(F.desc("n_sales"))
    )


def compute_daily_sales(master_dataset):
    if "t_dat" in master_dataset.columns:
        date_column = "t_dat"

    else:
        master_dataset = master_dataset.withColumn(
            "sales_date",
            F.to_date(
                F.col("date_key").cast("string"),
                "yyyyMMdd"
            )
        )
        date_column = "sales_date"
    return (
        master_dataset.groupBy(date_column)
        .agg(
            F.sum("price").alias("chiffre_affaires"),
            F.count("*").alias("nb_transactions"),
        )
        .orderBy(date_column)
    )


def compute_segment_summary(customers_features_train):
    return (
        customers_features_train.groupBy("segment_valeur")
        .agg(
            F.count("*").alias("nb_clients"),
            F.avg("total_spend").alias("montant_moyen"),
            F.avg("n_transactions").alias("achats_moyen"),
            F.sum("total_spend").alias("ca_segment"),
        )
    )