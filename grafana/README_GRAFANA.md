# 📊 Grafana Dashboards - HM Retail Intelligence Platform

<p align="center">
  <a href="./README_GRAFANA.md"><strong>🇬🇧 English</strong></a> ·
  <a href="./README_GRAFANA.fr.md">🇫🇷 Français</a>
</p>

This document presents the Grafana dashboards **actually implemented** for the
**HM Retail Intelligence Platform** project. Every panel has been checked against the JSON files
exported from Grafana and against the star schema actually produced by the Spark pipeline
(`spark/batch_ml_pipeline/jobs/pipeline_hm.py`).

**Current state: 5 dashboards, 25 panels, all functional.**
No "real-time" or "ML monitoring" dashboard exists yet (see §6 "What is not implemented").

*Note: the underlying SQL column aliases (e.g. `chiffre_affaires`, `ventes`) come straight from the
Spark-produced tables and are kept as-is below so the queries can be copy-pasted directly into
Grafana.*

---

# Dashboard 1: Sales Overview

## 1. Revenue over time

**Type** 📈 Time Series (Line Chart)

**Description** Tracks how revenue evolves over time.

```sql
SELECT
    TO_DATE(date_key::text,'YYYYMMDD') AS time,
    chiffre_affaires AS revenue
FROM daily_sales
ORDER BY date_key;
```

## 2. Number of transactions per day

**Type** 📊 Bar Chart

**Description** Tracks daily transaction volume.

```sql
SELECT
    TO_DATE(date_key::text,'YYYYMMDD') AS time,
    nb_transactions
FROM daily_sales
ORDER BY date_key;
```

---

## 3. Number of transactions per month

**Type** 📊 Bar Chart

**Description** Identifies the most active months.

```sql
SELECT
    TO_CHAR(TO_DATE(date_key::text,'YYYYMMDD'),'YYYY-MM') AS month,
    SUM(nb_transactions) AS nb_transactions
FROM daily_sales
GROUP BY month
ORDER BY month;
```

## 4. Monthly revenue

**Type** 📊 Bar Chart

**Description** Compares revenue across months.

```sql
SELECT
    TO_CHAR(TO_DATE(date_key::text,'YYYYMMDD'),'YYYY-MM') AS month,
    SUM(chiffre_affaires) AS revenue
FROM daily_sales
GROUP BY month
ORDER BY month;
```

---

## 5. Average basket

**Type** 📌 Stat Panel

**Description** Average amount of a transaction.

```sql
SELECT
    ROUND((SUM(chiffre_affaires) / NULLIF(SUM(nb_transactions),0))::numeric,2) AS average_ticket
FROM daily_sales;
```

---

## 6. Total number of sales

**Type** 📌 Stat Panel

**Description** Global indicator of the total number of sales.

```sql
SELECT
    SUM(nb_transactions) AS total_sales
FROM daily_sales;
```

---

## 7. Average daily revenue

**Type** 📌 Stat Panel

**Description** Global indicator: average revenue generated per day over the whole covered period.

```sql
SELECT
    ROUND(AVG(chiffre_affaires)::numeric,2) AS ca_moyen_journalier
FROM daily_sales;
```

---

# Dashboard 2: Product Analytics

## 8. Top 10 best-selling products

**Type** 📊 Horizontal Bar Chart

**Description** Identifies the most popular products.

```sql
SELECT
    a.prod_name,
    COUNT(*) AS sales
FROM fact_transaction f
JOIN dim_article a
ON f.article_key = a.article_key
GROUP BY a.prod_name
ORDER BY sales DESC
LIMIT 10;
```

---

## 9. Top 10 highest-revenue products

**Type** 📊 Horizontal Bar Chart

**Description** Identifies the most profitable products.

```sql
SELECT
    a.prod_name,
    SUM(f.price) AS revenue
FROM fact_transaction f
JOIN dim_article a
ON f.article_key = a.article_key
GROUP BY a.prod_name
ORDER BY revenue DESC
LIMIT 10;
```

---

## 10. Revenue by department

**Type** 🥧 Pie Chart

**Description** Visualizes each department's contribution to total revenue.

```sql
SELECT
    a.department_name,
    SUM(f.price) AS revenue
FROM fact_transaction f
JOIN dim_article a
ON f.article_key = a.article_key
GROUP BY a.department_name
ORDER BY revenue DESC;
```

---

## 11. Number of sales by category (top 10)

**Type** 📊 Horizontal Bar Chart

**Description** Compares the best-selling product categories.

```sql
SELECT
    product_group_name,
    SUM(n_sales) AS ventes
FROM products_performance
GROUP BY product_group_name
ORDER BY ventes DESC
LIMIT 10;
```

---

## 12. Sales breakdown by colour

**Type** 🥧 Pie Chart

**Description** Visualizes customer preferences based on product colour.

```sql
SELECT
    a.colour_group_name,
    COUNT(*) AS ventes
FROM fact_transaction f
JOIN dim_article a
ON f.article_key = a.article_key
GROUP BY a.colour_group_name
ORDER BY ventes DESC;
```

---

# Dashboard 3: Customer Analytics

## 13. Customer breakdown by age

**Type** 📊 Bar Chart

**Description** Understands how customers are distributed across age groups.

```sql
SELECT
    age_group,
    COUNT(*) AS clients
FROM dim_customer
GROUP BY age_group
ORDER BY age_group;
```

---

## 14. Club vs non-Club customers

**Type** 🥧 Pie Chart

**Description** Measures the Club program membership rate.

```sql
SELECT
    club_member_status,
    COUNT(*) AS clients
FROM dim_customer
GROUP BY club_member_status;
```

---

## 15. Breakdown by Fashion News frequency

**Type** 🥧 Pie Chart

**Description** Analyzes how often newsletters are received.

```sql
SELECT
    fashion_news_frequency,
    COUNT(*) AS clients
FROM dim_customer
GROUP BY fashion_news_frequency;
```

---

## 16. Top 20 best customers

**Type** 📋 Table

**Description** Identifies the customers who generated the most revenue.

```sql
SELECT
    c.customer_id,
    cf.total_spend
FROM customers_features_train cf
JOIN dim_customer c
ON cf.customer_key = c.customer_key
ORDER BY cf.total_spend DESC
LIMIT 20;
```

---

## 17. Average spend by age group

**Type** 📊 Bar Chart

**Description** Compares purchasing habits across age groups.

```sql
SELECT
    c.age_group,
    ROUND(AVG(cf.total_spend)::numeric,2) AS avg_spend
FROM customers_features_train cf
JOIN dim_customer c
ON cf.customer_key = c.customer_key
GROUP BY c.age_group
ORDER BY avg_spend DESC;
```

---

## 18. Number of customers

**Type** 📌 Stat Panel

**Description** Global indicator of the number of customers in the database.

```sql
SELECT COUNT(*) FROM dim_customer;
```

---

# Dashboard 4: Customer Segmentation

## 19. Segment breakdown

**Type** 🍩 Pie Chart

**Description** Visualizes how customers are distributed across segments (total-spend quartiles).

```sql
SELECT
    segment_valeur,
    nb_clients
FROM customer_segments_summary;
```

---

## 20. Revenue generated by segment

**Type** 📊 Bar Chart

**Description** Identifies the most profitable segments.

```sql
SELECT
    segment_valeur,
    ca_segment
FROM customer_segments_summary
ORDER BY ca_segment DESC;
```

---

## 21. Average spend by segment

**Type** 📊 Bar Chart

**Description** Compares the purchasing power of the different segments.

```sql
SELECT
    segment_valeur,
    montant_moyen
FROM customer_segments_summary
ORDER BY montant_moyen DESC;
```

---

## 22. Average number of purchases by segment

**Type** 📊 Bar Chart

**Description** Compares customer loyalty across the different segments.

```sql
SELECT
    segment_valeur,
    achats_moyen
FROM customer_segments_summary
ORDER BY achats_moyen DESC;
```

---

# Dashboard 5: Products & Daily Sales

Based on the aggregated tables `products_performance` and `daily_sales`, already written by the
Spark pipeline (`compute_products_performance`, `compute_daily_sales` in
`spark/batch_ml_pipeline/utils/features.py`) but not used until now.

## 23. Top 10 products by sales volume

**Type** 📊 Horizontal Bar Chart

**Description** Ranking of the best-selling products, computed from the already-aggregated
`products_performance` table (faster than aggregating on the fly over `fact_transaction`).

```sql
SELECT
    prod_name,
    n_sales
FROM products_performance
ORDER BY n_sales DESC
LIMIT 10;
```

---

## 24. Sales breakdown by index (department group)

**Type** 🥧 Pie Chart

**Description** Visualizes each index (`index_name`: Ladieswear, Menswear, Baby/Children, etc.)
contribution to total sales volume — a dimension not covered by the other dashboards.

```sql
SELECT
    index_name,
    SUM(n_sales) AS ventes
FROM products_performance
GROUP BY index_name
ORDER BY ventes DESC;
```

# 25. What is not implemented (should not be presented as functional)

| Planned dashboard | Why it isn't done today |
| --- | --- |
| ML monitoring (MLflow + Evidently drift) | MLflow exposes its metrics via a REST API, not directly in SQL; Evidently generates a static HTML report. A JSON API datasource in Grafana or a periodic export to PostgreSQL would be needed before this dashboard can be built. |
| Real time | The Kafka service starts in Docker, but `kafka/producers/` and `kafka/consumers/` are empty — nothing publishes or consumes a stream. The current pipeline reads static CSVs, not a continuous stream. |                        |
