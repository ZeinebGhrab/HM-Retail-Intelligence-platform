from pyspark.sql import functions as F

def clean_customers(customers_df):
    """
    - FN / Active : supprimées après ingestion car forte proportion de valeurs manquantes
    - age : imputation par la MÉDIANE (skew=0.61, non-normale — test D'Agostino-Pearson, cellule 25)
    - club_member_status : imputation par le MODE
    - fashion_news_frequency : imputation par le MODE

    """
    customers_df = customers_df.drop(
    "FN",
    "Active"
     )
    age_count = (
        customers_df
        .filter(F.col("age").isNotNull())
        .count()
    )


    if age_count > 0:

        age_median = (
            customers_df
            .approxQuantile(
                "age",
                [0.5],
                0.001
            )[0]
        )

    else:

        raise Exception(
            "No valid age values found"
        )

    club_mode = (
        customers_df.filter(F.col("club_member_status").isNotNull())
        .groupBy("club_member_status").count()
        .orderBy(F.desc("count")).first()["club_member_status"]
    )
    news_mode = (
        customers_df.filter(F.col("fashion_news_frequency").isNotNull())
        .groupBy("fashion_news_frequency").count()
        .orderBy(F.desc("count")).first()["fashion_news_frequency"]
    )

    customers_clean = (
        customers_df
        .withColumn("age", F.coalesce(F.col("age"), F.lit(age_median)))
        .withColumn("club_member_status", F.coalesce(F.col("club_member_status"), F.lit(club_mode)))
        .withColumn("fashion_news_frequency", F.coalesce(F.col("fashion_news_frequency"), F.lit(news_mode)))
        .withColumn(
            "age_group",
            F.when(F.col("age") < 20, "16-19")
             .when(F.col("age") < 25, "20-24")
             .when(F.col("age") < 30, "25-29")
             .when(F.col("age") < 35, "30-34")
             .when(F.col("age") < 40, "35-39")
             .when(F.col("age") < 50, "40-49")
             .when(F.col("age") < 60, "50-59")
             .when(F.col("age") < 70, "60-69")
             .otherwise("70+")
        )
    )
    return customers_clean


def clean_articles(articles_df):
    return articles_df


def clean_transactions(transactions_df):
    return transactions_df.withColumn("t_dat", F.to_date("t_dat", "yyyy-MM-dd"))