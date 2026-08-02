# 📊 Grafana Dashboards - HM Retail Intelligence Platform

Ce document présente les dashboards Grafana **réellement implémentés** pour le projet
**HM Retail Intelligence Platform**. Chaque panel a été vérifié contre les fichiers JSON exportés
de Grafana et contre le schéma en étoile réellement produit par le pipeline Spark
(`spark/batch_ml_pipeline/jobs/pipeline_hm.py`).

**État actuel : 5 dashboards, 25 panels, tous fonctionnels.**
Aucun dashboard "temps réel" ou "monitoring ML" n'existe à ce jour (voir §6 "Ce qui n'est pas
implémenté").

---

# Dashboard 1 : Sales Overview

## 1. Evolution du chiffre d'affaires

**Type** 📈 Time Series (Line Chart)

**Description** Permet de suivre l'évolution du chiffre d'affaires dans le temps.

```sql
SELECT
    TO_DATE(date_key::text,'YYYYMMDD') AS time,
    chiffre_affaires AS revenue
FROM daily_sales
ORDER BY date_key;
```

## 2. Nombre de transactions par jour

**Type** 📊 Bar Chart

**Description** Suivre le volume de transactions jour par jour.

```sql
SELECT
    TO_DATE(date_key::text,'YYYYMMDD') AS time,
    nb_transactions
FROM daily_sales
ORDER BY date_key;
```

---

## 3. Nombre de transactions par mois

**Type** 📊 Bar Chart

**Description** Identifier les mois les plus actifs.

```sql
SELECT
    TO_CHAR(TO_DATE(date_key::text,'YYYYMMDD'),'YYYY-MM') AS month,
    SUM(nb_transactions) AS nb_transactions
FROM daily_sales
GROUP BY month
ORDER BY month;
```

## 4. Chiffre d'affaires mensuel

**Type** 📊 Bar Chart

**Description** Comparer les revenus entre les mois.

```sql
SELECT
    TO_CHAR(TO_DATE(date_key::text,'YYYYMMDD'),'YYYY-MM') AS month,
    SUM(chiffre_affaires) AS revenue
FROM daily_sales
GROUP BY month
ORDER BY month;
```

---

## 5. Ticket moyen

**Type** 📌 Stat Panel

**Description** Montant moyen d'une transaction.

```sql
SELECT
    ROUND((SUM(chiffre_affaires) / NULLIF(SUM(nb_transactions),0))::numeric,2) AS average_ticket
FROM daily_sales;
```

---

## 6. Nombre total de ventes

**Type** 📌 Stat Panel

**Description** Indicateur global du nombre de ventes.

```sql
SELECT
    SUM(nb_transactions) AS total_sales
FROM daily_sales;
```

---

## 7. Chiffre d'affaires moyen par jour

**Type** 📌 Stat Panel

**Description** Indicateur global : CA moyen généré par jour sur toute la période couverte.

```sql
SELECT
    ROUND(AVG(chiffre_affaires)::numeric,2) AS ca_moyen_journalier
FROM daily_sales;
```

---

# Dashboard 2 : Product Analytics

## 8. Top 10 produits les plus vendus

**Type** 📊 Horizontal Bar Chart

**Description** Identifier les produits les plus populaires.

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

## 9. Top 10 produits générant le plus de revenus

**Type** 📊 Horizontal Bar Chart

**Description** Identifier les produits les plus rentables.

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

## 10. Chiffre d'affaires par département

**Type** 🥧 Pie Chart

**Description** Visualiser la contribution de chaque département au chiffre d'affaires total.

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

## 11. Nombre de ventes par catégorie (top 10)

**Type** 📊 Horizontal Bar Chart

**Description** Comparer les catégories de produits les plus vendues.

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

## 12. Répartition des ventes par couleur

**Type** 🥧 Pie Chart

**Description** Visualiser les préférences des clients selon les couleurs des produits.

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

## 13. Répartition des clients par âge

**Type** 📊 Bar Chart

**Description** Comprendre la répartition des clients selon leur tranche d'âge.

```sql
SELECT
    age_group,
    COUNT(*) AS clients
FROM dim_customer
GROUP BY age_group
ORDER BY age_group;
```

---

## 14. Clients Club vs Non Club

**Type** 🥧 Pie Chart

**Description** Mesurer le taux d'adhésion au programme Club.

```sql
SELECT
    club_member_status,
    COUNT(*) AS clients
FROM dim_customer
GROUP BY club_member_status;
```

---

## 15. Répartition par fréquence Fashion News

**Type** 🥧 Pie Chart

**Description** Analyser la fréquence de réception des newsletters.

```sql
SELECT
    fashion_news_frequency,
    COUNT(*) AS clients
FROM dim_customer
GROUP BY fashion_news_frequency;
```

---

## 16. Top 20 meilleurs clients

**Type** 📋 Table

**Description** Identifier les clients ayant généré le plus de chiffre d'affaires.

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

## 17. Dépense moyenne par tranche d'âge

**Type** 📊 Bar Chart

**Description** Comparer les habitudes d'achat selon les tranches d'âge.

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

## 18. Nombre de clients

**Type** 📌 Stat Panel

**Description** Indicateur global du nombre de clients dans la base.

```sql
SELECT COUNT(*) FROM dim_customer;
```

---

# Dashboard 4 : Customer Segmentation

## 19. Répartition des segments

**Type** 🍩 Pie Chart

**Description** Visualiser la répartition des clients par segment (quartiles de dépense totale).

```sql
SELECT
    segment_valeur,
    nb_clients
FROM customer_segments_summary;
```

---

## 20. CA généré par segment

**Type** 📊 Bar Chart

**Description** Identifier les segments les plus rentables.

```sql
SELECT
    segment_valeur,
    ca_segment
FROM customer_segments_summary
ORDER BY ca_segment DESC;
```

---

## 21. Dépense moyenne par segment

**Type** 📊 Bar Chart

**Description** Comparer le pouvoir d'achat des différents segments.

```sql
SELECT
    segment_valeur,
    montant_moyen
FROM customer_segments_summary
ORDER BY montant_moyen DESC;
```

---

## 22. Nombre moyen d'achats par segment

**Type** 📊 Bar Chart

**Description** Comparer la fidélité des différents segments de clientèle.

```sql
SELECT
    segment_valeur,
    achats_moyen
FROM customer_segments_summary
ORDER BY achats_moyen DESC;
```

---

# Dashboard 5 : Produits & Ventes journalières

Basé sur les tables agrégées `products_performance` et `daily_sales`, déjà écrites par le pipeline
Spark (`compute_products_performance`, `compute_daily_sales` dans `spark/batch_ml_pipeline/utils/features.py`)
mais non exploitées jusqu'ici.

## 23. Top 10 produits par volume de ventes

**Type** 📊 Horizontal Bar Chart

**Description** Classement des produits les plus vendus, calculé depuis la table déjà agrégée
`products_performance` (plus rapide qu'une agrégation à la volée sur `fact_transaction`).

```sql
SELECT
    prod_name,
    n_sales
FROM products_performance
ORDER BY n_sales DESC
LIMIT 10;
```

---

## 24. Répartition des ventes par rayon (index)

**Type** 🥧 Pie Chart

**Description** Visualiser la contribution de chaque rayon (`index_name` : Ladieswear, Menswear,
Baby/Children, etc.) au volume total de ventes — une dimension non couverte par les autres dashboards.

```sql
SELECT
    index_name,
    SUM(n_sales) AS ventes
FROM products_performance
GROUP BY index_name
ORDER BY ventes DESC;
```

# 25. Ce qui n'est pas implémenté (à ne pas présenter comme fonctionnel)

| Dashboard envisagé                       | Pourquoi ce n'est pas fait aujourd'hui                                                                                                                                                                                                  |
| ---------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Monitoring ML (MLflow + drift Evidently) | MLflow expose ses métriques via API REST, pas en SQL direct ; Evidently génère un rapport HTML statique. Il faut une datasource JSON API dans Grafana ou un export périodique vers PostgreSQL avant de pouvoir construire ce dashboard. |
| Temps réel                               | Le service Kafka démarre dans Docker mais `kafka/producers/` et `kafka/consumers/` sont vides — rien ne publie ni ne consomme de flux. Le pipeline actuel lit des CSV statiques, pas un flux continu.                                   |
