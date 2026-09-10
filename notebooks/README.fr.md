# H&M Retail Intelligence — Série de notebooks

<p align="center">
  <a href="./README.md">🇬🇧 English</a> ·
  <a href="./README.fr.md"><strong>🇫🇷 Français</strong></a>
</p>

Ce projet analyse le dataset Kaggle **H&M Personalized Fashion Recommendations**
(`customers.csv`, `articles.csv`, `transactions_train.csv` — 33,7M lignes) à travers un pipeline
complet : nettoyage, EDA, enrichissement externe, feature engineering RFM, export RAG, et
modélisation ML (classification, régression, réduction de dimension, clustering).

> ⚠️ **Sorties d'exécution (`.pkl`, `.csv`, `.md`)** : les fichiers intermédiaires
> (`intermediate/*.pkl`, `customers_features.csv`, `insights_summary.md`, etc. — voir §2.1 et §4)
> sont **générés localement à l'exécution des notebooks**, dans le dossier `intermediate/` à côté
> des données (`BASE_PATH`). Ils **ne sont pas versionnés dans ce dépôt** car ils dépendent des
> données brutes Kaggle (`customers.csv`, `articles.csv`, `transactions_train.csv`, non incluses —
> voir `data/raw/`) : il faut exécuter la série 01→07 sur ces données pour les obtenir. Les
> notebooks `.ipynb` de ce dossier contiennent en revanche déjà les sorties affichées (graphiques,
> tableaux) de leur dernière exécution.

---

## 1. Structure de la série

| # | Notebook | Contenu | Sections d'origine |
|---|---|---|---|
| 01 | `01_EDA_Nettoyage_Clients.ipynb` | Config, nettoyage de `customers.csv` (imputation justifiée statistiquement), EDA clients | 0–7 |
| 02 | `02_EDA_Produits_Transactions.ipynb` | EDA `articles.csv`, passage par blocs sur `transactions_train.csv` (33,7M lignes) | 8–10 |
| 03 | `03_RFM_Enrichissement_Externe.ipynb` | Analyse RFM, enrichissement météo (Open-Meteo) et jours fériés (Nager.Date) | 11–13 |
| 04 | `04_FeatureEngineering_Soldes_RAG.ipynb` | Table de features clients, impact des soldes, export base de connaissances RAG | 14–16 |
| 05 | `05_ML_ReductionDim_Clustering_Rapide.ipynb` | Préparation ML, PCA, t-SNE/UMAP, K-Means exploratoire | 17.1–17.4 |
| 06 | `06_ML_Classification_Regression.ipynb` | Classification (`club_member_status`) et régression (`total_spend`), SMOTE, GridSearchCV, boosting | 17.5–17.6 |
| 07 | `07_ML_Clustering_Approfondi_Synthese.ipynb` | Clustering approfondi (K-Means/GMM/hiérarchique, k=6), interprétation par arbre de décision, synthèse ML | 17.7–17.8 |

---

## 2. Exécuter la série

### 2.1 Ordre d'exécution

**Les notebooks doivent être exécutés dans l'ordre, une fois chacun, sur le même `BASE_PATH`.**
Chaque notebook exporte à sa dernière cellule les objets nécessaires au suivant dans un dossier
`intermediate/` ; chaque notebook (à partir du 02) recharge ces objets dans sa première cellule
de code plutôt que de tout recalculer.

```
01 ──▶ nb01_customers.pkl ──────────────────────────────┐
                                                          ├──▶ 02
02 ──▶ nb02_transactions_accumulators.pkl ───────┬───────┼──▶ 03
                                                  │       └──▶ 04
03 ──▶ nb03_segment_summary.pkl                  │
       nb03_calendar_df.pkl (optionnel)  ────────┴───────────▶ 04
04 ──▶ customers_features.csv ───────────────────────────────▶ 05
05 ──▶ nb05_ml_prep.pkl (ml_sample, X_behavior_scaled, scaler) ─┬──▶ 06
                                                                  └──▶ 07
```

Si un notebook est ouvert seul sans que les précédents aient été exécutés, sa première cellule
de code lève une `FileNotFoundError` explicite indiquant quel notebook exécuter avant.

### 2.2 Pourquoi cette architecture (et pas des notebooks 100% indépendants)

Le passage sur `transactions_train.csv` (33,7M lignes) est fait **une seule fois**, par blocs, dans
le notebook 02 — le relire à chaque notebook serait très coûteux en temps et en mémoire. Les
notebooks 03 et 04 réutilisent donc les agrégats déjà calculés (dépenses par client, dates de 1er/
dernier achat, CA quotidien, etc.) via un export/import `pickle`, plutôt que de recalculer.

### 2.3 Sur Google Colab

1. Placer `customers.csv`, `articles.csv`, `transactions_train.csv` dans un dossier Google Drive,
   par ex. `MyDrive/HM_dataset/`.
2. Adapter si besoin `BASE_PATH` dans la première cellule de config de chaque notebook.
3. Exécuter les notebooks 01 → 07 dans l'ordre. Le dossier `MyDrive/HM_dataset/intermediate/`
   se remplit automatiquement au fil de l'exécution.

### 2.4 Bascule `FULL_SCALE` (notebook 05)

- `FULL_SCALE = False` : échantillon stratifié de 50 000 clients (recommandé en environnement
  contraint en RAM/CPU).
- `FULL_SCALE = True` : ~1,36M clients acheteurs (recommandé sur Colab avec ≥12–25 Go de RAM).
  Certains algorithmes restent cependant plafonnés quel que soit ce réglage, car leur coût
  algorithmique (pas seulement mémoire) explose au-delà de quelques dizaines de milliers de
  points : t-SNE (échantillon de 5 000), clustering hiérarchique (2 000), SVM/KNN (50 000),
  et le rééquilibrage SMOTE (classe majoritaire plafonnée à 100 000).

---

## 3. Points méthodologiques à connaître

- **Codes postaux hashés en SHA-256** : aucune inférence géographique possible. L'enrichissement
  météo/jours fériés utilise Stockholm/Suède comme proxy géographique global, pas une donnée réelle
  du dataset (qui est mondial, sans attribution géographique par client).
- **Météo exclue des modèles ML** : le test de significativité formel donne un R² < 5 % entre
  température et ventes — statistiquement significatif mais négligeable en pratique.
- **Section 17.4 vs 17.7 (clustering)** : la section 17.4 (notebook 05) retient volontairement
  k=4 pour comparer au clustering aux quartiles RFM (section 11), même si l'analyse coude/silhouette
  y recommande statistiquement k=6. Ce k=6 est repris et validé rigoureusement en section 17.7
  (notebook 07) avec K-Means, clustering hiérarchique, GMM et critères BIC/AIC. Les deux sections
  ont été relues pour que le texte reflète honnêtement cet écart méthodologique assumé, plutôt que
  de prétendre à une fausse convergence.
- **État production** : les modèles ne sont pas prêts pour la production — entraînés sur un
  échantillon, pas de split temporel, pas de versioning des modèles, plafond F1-macro ~0,40 sur la
  classification `club_member_status` dû au déséquilibre structurel des classes (`LEFT CLUB` < 0,1 %).

---

## 4. Autres documents du projet

- `ARCHITECTURE.md` (racine du projet) — architecture technique complète (7 cas d'usage, pile MLOps : Git, DVC,
  DagsHub, MLflow, Docker, GitHub Actions, Evidently AI, intégration n8n).
- Section RAG (notebook 04) — export de la base de connaissances pour le chatbot (`insights_summary.md`
  + tables CSV agrégées, dans `intermediate/` — généré à l'exécution, non versionné, voir l'encart
  en haut de ce document).