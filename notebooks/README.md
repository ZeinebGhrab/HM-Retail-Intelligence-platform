# H&M Retail Intelligence — Notebook Series

<p align="center">
  <a href="./README.md"><strong>🇬🇧 English</strong></a> ·
  <a href="./README.fr.md">🇫🇷 Français</a>
</p>

This project analyzes the Kaggle **H&M Personalized Fashion Recommendations** dataset
(`customers.csv`, `articles.csv`, `transactions_train.csv` — 33.7M rows) through a full pipeline:
cleaning, EDA, external enrichment, RFM feature engineering, RAG export, and ML modeling
(classification, regression, dimensionality reduction, clustering).

> ⚠️ **Execution outputs (`.pkl`, `.csv`, `.md`)**: the intermediate files
> (`intermediate/*.pkl`, `customers_features.csv`, `insights_summary.md`, etc. — see §2.1 and §4)
> are **generated locally when the notebooks run**, in the `intermediate/` folder next to the data
> (`BASE_PATH`). They are **not versioned in this repo** since they depend on the raw Kaggle data
> (`customers.csv`, `articles.csv`, `transactions_train.csv`, not included — see `data/raw/`): the
> 01→07 series needs to be run on that data to obtain them. The `.ipynb` notebooks in this folder,
> on the other hand, already contain the displayed outputs (charts, tables) from their last run.

---

## 1. Series structure

| # | Notebook | Content | Original sections |
|---|---|---|---|
| 01 | `01_EDA_Nettoyage_Clients.ipynb` | Config, cleaning of `customers.csv` (statistically justified imputation), customer EDA | 0–7 |
| 02 | `02_EDA_Produits_Transactions.ipynb` | `articles.csv` EDA, chunked pass over `transactions_train.csv` (33.7M rows) | 8–10 |
| 03 | `03_RFM_Enrichissement_Externe.ipynb` | RFM analysis, weather enrichment (Open-Meteo) and public holidays (Nager.Date) | 11–13 |
| 04 | `04_FeatureEngineering_Soldes_RAG.ipynb` | Customer feature table, sales-period impact, RAG knowledge base export | 14–16 |
| 05 | `05_ML_ReductionDim_Clustering_Rapide.ipynb` | ML preparation, PCA, t-SNE/UMAP, exploratory K-Means | 17.1–17.4 |
| 06 | `06_ML_Classification_Regression.ipynb` | Classification (`club_member_status`) and regression (`total_spend`), SMOTE, GridSearchCV, boosting | 17.5–17.6 |
| 07 | `07_ML_Clustering_Approfondi_Synthese.ipynb` | In-depth clustering (K-Means/GMM/hierarchical, k=6), decision-tree interpretation, ML summary | 17.7–17.8 |

---

## 2. Running the series

### 2.1 Execution order

**The notebooks must be run in order, once each, against the same `BASE_PATH`.**
Each notebook exports, in its last cell, the objects needed by the next one into an
`intermediate/` folder; each notebook (from 02 onward) reloads these objects in its first code
cell instead of recomputing everything.

```
01 ──▶ nb01_customers.pkl ──────────────────────────────┐
                                                          ├──▶ 02
02 ──▶ nb02_transactions_accumulators.pkl ───────┬───────┼──▶ 03
                                                  │       └──▶ 04
03 ──▶ nb03_segment_summary.pkl                  │
       nb03_calendar_df.pkl (optional)  ─────────┴───────────▶ 04
04 ──▶ customers_features.csv ───────────────────────────────▶ 05
05 ──▶ nb05_ml_prep.pkl (ml_sample, X_behavior_scaled, scaler) ─┬──▶ 06
                                                                  └──▶ 07
```

If a notebook is opened on its own without the previous ones having run, its first code cell
raises an explicit `FileNotFoundError` indicating which notebook to run beforehand.

### 2.2 Why this architecture (and not fully independent notebooks)

The pass over `transactions_train.csv` (33.7M rows) is done **only once**, in chunks, in notebook
02 — re-reading it in every notebook would be very costly in time and memory. Notebooks 03 and 04
therefore reuse the aggregates already computed (spend per customer, first/last purchase dates,
daily revenue, etc.) via a `pickle` export/import, instead of recomputing them.

### 2.3 On Google Colab

1. Place `customers.csv`, `articles.csv`, `transactions_train.csv` in a Google Drive folder, e.g.
   `MyDrive/HM_dataset/`.
2. Adjust `BASE_PATH` in each notebook's first config cell if needed.
3. Run notebooks 01 → 07 in order. The `MyDrive/HM_dataset/intermediate/` folder fills in
   automatically as they run.

### 2.4 `FULL_SCALE` switch (notebook 05)

- `FULL_SCALE = False`: stratified sample of 50,000 customers (recommended in a
  RAM/CPU-constrained environment).
- `FULL_SCALE = True`: ~1.36M purchasing customers (recommended on Colab with ≥12–25 GB of RAM).
  Some algorithms remain capped regardless of this setting, though, because their algorithmic
  cost (not just memory) explodes beyond a few tens of thousands of points: t-SNE (5,000-point
  sample), hierarchical clustering (2,000), SVM/KNN (50,000), and SMOTE rebalancing (majority
  class capped at 100,000).

---

## 3. Methodological points to know

- **Postal codes hashed with SHA-256**: no geographic inference is possible. Weather/holiday
  enrichment uses Stockholm/Sweden as a global geographic proxy, not real data from the dataset
  (which is worldwide, with no per-customer geographic attribution).
- **Weather excluded from the ML models**: the formal significance test gives R² < 5% between
  temperature and sales — statistically significant but negligible in practice.
- **Section 17.4 vs 17.7 (clustering)**: section 17.4 (notebook 05) deliberately keeps k=4 to
  compare against the RFM-quartile clustering (section 11), even though the elbow/silhouette
  analysis there statistically recommends k=6. This k=6 is picked back up and rigorously validated
  in section 17.7 (notebook 07) with K-Means, hierarchical clustering, GMM, and BIC/AIC criteria.
  Both sections were reviewed so the text honestly reflects this deliberate methodological gap,
  rather than claiming a false convergence.
- **Production readiness**: the models are not production-ready — trained on a sample, no
  temporal split, no model versioning, F1-macro capped around ~0.40 on the `club_member_status`
  classification due to structural class imbalance (`LEFT CLUB` < 0.1%).

---

## 4. Other project documents

- `ARCHITECTURE.md` (project root) — full technical architecture (7 use cases, MLOps stack: Git,
  DVC, DagsHub, MLflow, Docker, GitHub Actions, Evidently AI, n8n integration).
- RAG section (notebook 04) — export of the knowledge base for the chatbot (`insights_summary.md`
  + aggregated CSV tables, in `intermediate/` — generated at run time, not versioned, see the
  note at the top of this document).