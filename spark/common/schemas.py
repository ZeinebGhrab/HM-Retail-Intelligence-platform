from pyspark.sql.types import StructType, StructField, StringType, DoubleType, LongType, IntegerType

# article_id est un entier dans l'EDA (dtype "int64"), pas une chaîne
transactions_schema = StructType([
    StructField("t_dat", StringType(), True),
    StructField("customer_id", StringType(), True),
    StructField("article_id", LongType(), True),
    StructField("price", DoubleType(), True),
    StructField("sales_channel_id", IntegerType(), True),
])

customers_schema = StructType([
    StructField("customer_id", StringType(), True),
    StructField("FN", StringType(), True),
    StructField("Active", StringType(), True),
    StructField("club_member_status", StringType(), True),
    StructField("fashion_news_frequency", StringType(), True),
    StructField("age", DoubleType(), True),
    StructField("postal_code", StringType(), True),
])

articles_schema = StructType([
    StructField("article_id", LongType(), True),
    StructField("product_code", StringType(), True),
    StructField("prod_name", StringType(), True),
    StructField("product_type_no", IntegerType(), True),
    StructField("product_type_name", StringType(), True),
    StructField("product_group_name", StringType(), True),
    StructField("graphical_appearance_no", IntegerType(), True),
    StructField("graphical_appearance_name", StringType(), True),
    StructField("colour_group_code", IntegerType(), True),
    StructField("colour_group_name", StringType(), True),
    StructField("perceived_colour_value_id", IntegerType(), True),
    StructField("perceived_colour_value_name", StringType(), True),
    StructField("perceived_colour_master_id", IntegerType(), True),
    StructField("perceived_colour_master_name", StringType(), True),
    StructField("department_no", IntegerType(), True),
    StructField("department_name", StringType(), True),
    StructField("index_code", StringType(), True),
    StructField("index_name", StringType(), True),
    StructField("index_group_no", IntegerType(), True),
    StructField("index_group_name", StringType(), True),
    StructField("section_no", IntegerType(), True),
    StructField("section_name", StringType(), True),
    StructField("garment_group_no", IntegerType(), True),
    StructField("garment_group_name", StringType(), True),
    StructField("detail_desc", StringType(), True),
])