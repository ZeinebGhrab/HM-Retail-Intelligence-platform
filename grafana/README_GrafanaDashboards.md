# 📊 Grafana Dashboards - HM Retail Intelligence Platform

Ce document présente les dashboards Grafana développés pour le projet **HM Retail Intelligence Platform**. Chaque dashboard contient des indicateurs décisionnels permettant d'analyser les ventes, les produits, les clients et leur segmentation.

---

# Dashboard 1 : Sales Overview

## 1. Evolution du chiffre d'affaires

**Type**

📈 Time Series (Line Chart)

**Description**

Permet de suivre l'évolution du chiffre d'affaires dans le temps.

```sql
SELECT
    d.date AS time,
    SUM(f.price) AS revenue
FROM fact_transaction f
JOIN dim_date d
ON f.date_key = d.date_key
GROUP BY d.date
ORDER BY d.date;
```

---

## 2. Nombre de transactions par mois

**Type**

📊 Bar Chart

**Description**

Identifier les mois les plus actifs.

```sql
SELECT
    CONCAT(d.year,'-',LPAD(d.month::text,2,'0')) AS month,
    COUNT(*) AS nb_transactions
FROM fact_transaction f
JOIN dim_date d
ON f.date_key = d.date_key
GROUP BY d.year,d.month
ORDER BY d.year,d.month;
```

---

## 3. Chiffre d'affaires mensuel

**Type**

📊 Bar Chart

**Description**

Comparer les revenus entre les mois.

```sql
SELECT
    CONCAT(d.year,'-',LPAD(d.month::text,2,'0')) AS month,
    SUM(f.price) AS revenue
FROM fact_transaction f
JOIN dim_date d
ON f.date_key = d.date_key
GROUP BY d.year,d.month
ORDER BY d.year,d.month;
```

---

## 4. Ticket moyen

**Type**

📌 Stat Panel

**Description**

Montant moyen d'une transaction.

```sql
SELECT
ROUND(AVG(price)::numeric,2) AS average_ticket
FROM fact_transaction;
```

---

## 5. Nombre total de ventes

**Type**

📌 Stat Panel

**Description**

Indicateur global du nombre de ventes.

```sql
SELECT
COUNT(*) AS total_sales
FROM fact_transaction;
```

---

# Dashboard 2 : Product Analytics

## 6. Top 10 produits les plus vendus

**Type**

📊 Horizontal Bar Chart

**Description**

Identifier les produits les plus populaires.

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

## 7. Top 10 produits générant le plus de revenus

**Type**

📊 Horizontal Bar Chart

**Description**

Identifier les produits les plus rentables.

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

## 8. Chiffre d'affaires par département

**Type**

🥧 Pie Chart

**Description**

Visualiser la contribution de chaque département au chiffre d'affaires total.

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

## 9. Top 10 catégories les plus vendues

**Type**

📊 Horizontal Bar Chart

**Description**

Comparer les catégories de produits les plus vendues.

```sql
SELECT
    a.product_group_name,
    COUNT(*) AS ventes
FROM fact_transaction f
JOIN dim_article a
ON f.article_key = a.article_key
GROUP BY a.product_group_name
ORDER BY ventes DESC
LIMIT 10;
```

---

## 10. Répartition des ventes par couleur

**Type**

🥧 Pie Chart

**Description**

Visualiser les préférences des clients selon les couleurs des produits.

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

# Dashboard 3 : Customer Analytics

## 11. Répartition des clients par âge

**Type**

📊 Bar Chart

**Description**

Comprendre la répartition des clients selon leur tranche d'âge.

```sql
SELECT
    age_group,
    COUNT(*) AS clients
FROM dim_customer
GROUP BY age_group
ORDER BY age_group;
```

---

## 12. Clients Club vs Non Club

**Type**

🍩 Donut Chart

**Description**

Mesurer le taux d'adhésion au programme Club.

```sql
SELECT
    club_member_status,
    COUNT(*) AS clients
FROM dim_customer
GROUP BY club_member_status;
```

---

## 13. Répartition par fréquence Fashion News

**Type**

🥧 Pie Chart

**Description**

Analyser la fréquence de réception des newsletters.

```sql
SELECT
    fashion_news_frequency,
    COUNT(*) AS clients
FROM dim_customer
GROUP BY fashion_news_frequency;
```

---

## 14. Top 20 meilleurs clients

**Type**

📋 Table

**Description**

Identifier les clients ayant généré le plus de chiffre d'affaires.

```sql
SELECT
    c.customer_id,
    SUM(f.price) AS total_spend
FROM fact_transaction f
JOIN dim_customer c
ON f.customer_key = c.customer_key
GROUP BY c.customer_id
ORDER BY total_spend DESC
LIMIT 20;
```

---

## 15. Dépense moyenne par tranche d'âge

**Type**

📊 Bar Chart

**Description**

Comparer les habitudes d'achat selon les tranches d'âge.

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

# Dashboard 4 : Customer Segmentation

## 16. Répartition des segments

**Type**

🍩 Donut Chart

**Description**

Visualiser la répartition des clients par segment.

```sql
SELECT
    segment_valeur,
    nb_clients
FROM customer_segments_summary;
```

---

## 17. Chiffre d'affaires généré par segment

**Type**

📊 Bar Chart

**Description**

Identifier les segments les plus rentables.

```sql
SELECT
    segment_valeur,
    ca_segment
FROM customer_segments_summary
ORDER BY ca_segment DESC;
```

---

## 18. Dépense moyenne par segment

**Type**

📊 Bar Chart

**Description**

Comparer le pouvoir d'achat des différents segments.

```sql
SELECT
    segment_valeur,
    montant_moyen
FROM customer_segments_summary
ORDER BY montant_moyen DESC;
```

---

## 19. Nombre moyen d'achats par segment

**Type**

📊 Bar Chart

**Description**

Comparer la fidélité des différents segments de clientèle.

```sql
SELECT
    segment_valeur,
    achats_moyen
FROM customer_segments_summary
ORDER BY achats_moyen DESC;
```

---
