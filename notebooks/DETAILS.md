# 🛍️ H&M Customer Analytics — EDA, Feature Engineering & Machine Learning

<p align="center">
  <a href="./DETAILS.md"><strong>🇬🇧 English</strong></a> ·
  <a href="./DETAILS.fr.md">🇫🇷 Français</a>
</p>

Full exploratory analysis, data cleaning, feature engineering, and Machine Learning modeling on
the **H&M Personalized Fashion Recommendations** dataset (Kaggle), based on the `customers.csv`,
`articles.csv`, and `transactions_train.csv` files.

Notebook designed for **Google Colab + Google Drive**, with a fallback mode for local execution.

---

## 📑 Table of contents

1. [Project overview](#-project-overview)
2. [Datasets](#-datasets)
3. [Environment & dependencies](#-environment--dependencies)
4. [Notebook structure](#-notebook-structure)
5. [Data cleaning](#-data-cleaning)
6. [Exploratory analysis (EDA)](#-exploratory-analysis-eda)
7. [External enrichment (weather & public holidays)](#-external-enrichment-weather--public-holidays)
8. [Feature Engineering (enriched RFM)](#-feature-engineering-enriched-rfm)
9. [Export for RAG chatbot](#-export-for-rag-chatbot)
10. [Machine Learning modeling](#-machine-learning-modeling)
    - [Dimensionality reduction (PCA, t-SNE, UMAP)](#a-dimensionality-reduction)
    - [Classification — club status](#b-supervised-classification--club-status-club_member_status)
    - [Regression — amount spent](#c-supervised-regression--total_spend)
    - [Clustering — customer segmentation](#d-unsupervised-clustering--customer-segmentation)
11. [Results summary](#-results-summary)
12. [Limitations & improvement ideas](#-limitations--improvement-ideas)
13. [How to run the notebook](#-how-to-run-the-notebook)

---

## 🎯 Project overview

The project has three complementary goals:

| Goal | Description |
|---|---|
| **Understand** | Explore and clean H&M customer, product, and transaction data to surface business insights (age, club status, purchase behavior, seasonality, weather...). |
| **Predict** | Build supervised models to predict **club membership status** (classification) and the **total amount spent** per customer (regression). |
| **Segment** | Identify homogeneous customer groups (unsupervised clustering) and make them interpretable for non-technical business teams. |

---

## 📂 Datasets

| File | Rows x columns | Description |
|---|---|---|
| `customers.csv` | 1,371,980 x 7 | Customer demographic and membership data |
| `articles.csv` | 105,542 x 25 | Product catalog (group, type, colour, target segment...) |
| `transactions_train.csv` | ~31M rows | Transaction history (price, sales channel, date) |
| `customers_cleaned.csv` | 1,371,980 x 5 | Export of the customer dataset after cleaning |
| Weather/holiday calendar | 734 x 7 | Data enriched via external APIs |
| Customer feature table | 1,371,980 x 16 | Enriched RFM table after feature engineering |

> The raw data isn't included in this repo (too large) — it needs to be placed on Google Drive or
> locally, see [How to run the notebook](#-how-to-run-the-notebook).

---

## ⚙️ Environment & dependencies

**Language**: Python 3.12

### Main libraries

| Category | Libraries |
|---|---|
| Data manipulation | `pandas`, `numpy` |
| Visualization | `matplotlib`, `seaborn` |
| Statistics | `scipy.stats` (skew, kurtosis, normaltest, QQ-plot), `statsmodels` (OLS / Backward Elimination) |
| Preprocessing | `sklearn.preprocessing` (`StandardScaler`, `LabelEncoder`) |
| Dimensionality reduction | `sklearn.decomposition.PCA`, `sklearn.manifold.TSNE`, `umap-learn` |
| Clustering | `sklearn.cluster` (`KMeans`, `AgglomerativeClustering`), `sklearn.mixture.GaussianMixture`, `scipy.cluster.hierarchy` (dendrogram), `kneed` (KneeLocator — elbow method) |
| Classification | `sklearn.linear_model.LogisticRegression`, `sklearn.tree.DecisionTreeClassifier`, `sklearn.ensemble.RandomForestClassifier`, `sklearn.neighbors.KNeighborsClassifier`, `sklearn.svm.SVC`, `lightgbm`, `xgboost`, `catboost` |
| Regression | `sklearn.linear_model` (`LinearRegression`, `Lasso`, `Ridge`, `ElasticNet`), `xgboost.XGBRegressor` |
| Class rebalancing | `imblearn.over_sampling.SMOTE`, `sklearn.utils.class_weight.compute_sample_weight` |
| Feature selection | `sklearn.feature_selection.SelectKBest`, `f_regression`, Backward Elimination (OLS p-values via `statsmodels`) |
| Hyperparameter optimization | `sklearn.model_selection.GridSearchCV`, `cross_validate` |
| Metrics | `accuracy_score`, `f1_score`, `classification_report`, `confusion_matrix`, `mean_squared_error`, `mean_absolute_error`, `r2_score`, `silhouette_score` |
| External data | `requests` (Open-Meteo API, Nager.Date API) |
| Other | `gc` (memory management), `google.colab.drive` |

### Installation

```bash
pip install pandas numpy matplotlib seaborn scipy statsmodels scikit-learn \
    umap-learn kneed lightgbm xgboost catboost imbalanced-learn requests
```

---

## 🗂️ Notebook structure

The notebook is organized into **17 main sections** (307 cells):

| # | Section |
|---|---|
| 0 | Environment setup (Colab + Drive) |
| 1–3 | General overview, missing values, `age` analysis (QQ-plot, skewness/kurtosis) |
| 4–5 | Data cleaning (imputation) and summary |
| 6–7 | In-depth exploration of the cleaned customer dataset |
| 8 | Exploration of the `articles.csv` product dataset |
| 9 | Join of `customers` x `articles` x `transactions` |
| 10 | Combined summary of the 3 datasets |
| 11 | RFM analysis (Frequency x Amount), quartile segmentation |
| 12 | Weather (Open-Meteo) and public holiday (Nager.Date) enrichment |
| 13 | Updated overall summary |
| 14 | Feature Engineering — customer feature table (enriched RFM) |
| 15 | Data export for a RAG chatbot |
| 16 | Sales periods and impact on revenue |
| 17 | **ML modeling**: PCA, t-SNE/UMAP, K-Means, Classification, Regression, in-depth clustering |

---

## 🧹 Data cleaning

| Column | Issue detected | Treatment applied |
|---|---|---|
| `FN`, `Active` | NaN = genuine absence of subscription/activity (not missing data) | Columns removed |
| `age` | Skewed distribution (**skewness ≈ 0.61**), non-normal (D'Agostino-Pearson test, **p ≈ 0**) | Imputed with the **median** |
| `club_member_status` | Highly imbalanced categorical variable | Imputed with the **mode** (`ACTIVE`) |
| `fashion_news_frequency` | Highly imbalanced categorical variable | Imputed with the **mode** (`NONE`) |
| `customer_id`, `postal_code` | No missing values | No treatment |

➡️ Final dataset with no missing values, exported to `customers_cleaned.csv`.

### Statistical basis for the imputation decision

**Skewness** — measures the degree of asymmetry of the distribution around the mean:

$$
\text{Skewness} = \frac{\frac{1}{n}\sum_{i=1}^{n}(x_i - \bar{x})^3}{\left(\frac{1}{n}\sum_{i=1}^{n}(x_i - \bar{x})^2\right)^{3/2}}
$$

Interpretation rule used:

| \|skew\| | Interpretation |
|---|---|
| < 0.5 | Fairly symmetric distribution |
| 0.5 – 1 | Moderate asymmetry |
| > 1 | Strong asymmetry |

**Kurtosis** — measures tail thickness relative to a normal distribution (excess kurtosis, normal
= 0):

$$
\text{Kurtosis} = \frac{\frac{1}{n}\sum_{i=1}^{n}(x_i - \bar{x})^4}{\left(\frac{1}{n}\sum_{i=1}^{n}(x_i - \bar{x})^2\right)^{2}} - 3
$$

**D'Agostino-Pearson test** (`scipy.stats.normaltest`) — combines skewness and kurtosis into a
$K^2$ statistic that approximately follows a χ² distribution with 2 degrees of freedom under H₀
(normality):

$$
K^2 = Z_{skew}^2 + Z_{kurtosis}^2 \;\sim\; \chi^2_{(2)}
$$

Decision rule (threshold α = 0.05): **p > 0.05** → do not reject normality; **p < 0.05** → reject
it.

**Comparison of available normality tests:**

| Test | Use case | Advantages | Limitations |
|---|---|---|---|
| Shapiro-Wilk | Small/medium samples (≲ 5,000 obs.) | Very powerful | Poorly suited to very large samples |
| **D'Agostino-Pearson** (chosen) | Large samples (n ≥ 20, ideally > 100) | Combines skewness + kurtosis, suited to large volumes | Needs a large enough sample |
| Anderson-Darling | All sizes | Sensitive in the distribution tails | No direct p-value in SciPy |
| Kolmogorov-Smirnov | Known reference distribution | Simple | Poorly suited when parameters are estimated from the data |
| Lilliefors | KS variant, estimated parameters | Corrects the classic KS limitation | Not natively available in SciPy |

➡️ **D'Agostino-Pearson** is chosen because `customers` contains ~1.37M rows — a "large sample"
context for which this test is the most suitable and directly available (`scipy.stats.normaltest`).

### Results obtained on `age`

| Statistic | Value | Interpretation |
|---|---:|---|
| Skewness | ≈ 0.61 | **Moderate right skew** (tail stretched toward older ages), above the 0.5 threshold |
| Kurtosis | ≈ −0.71 | **Platykurtic** distribution (flatter than a normal distribution) |
| p-value (D'Agostino-Pearson) | ≈ 0 | **Rejection** of the normality hypothesis |

**Imputation decision rule applied:**

| Situation | Recommended imputation |
|---|---|
| Normal distribution | Mean |
| Skewed distribution / outliers | **Median** |
| Categorical variable | Mode |

➡️ Since `age` is skewed and non-normal, **median** imputation is used: more robust to extreme
values than the mean.

> **Methodological note**: on very large samples, normality tests reject H₀ almost systematically
> even for minor deviations from normality (statistical overpowering). The result should therefore
> always be interpreted together with visualizations (histogram, QQ-plot) and descriptive measures
> (skewness, kurtosis), not as an isolated verdict.

---

## 🔍 Exploratory analysis (EDA)

### Customers (`customers.csv`)
- Breakdown by age group
- Median age by club status
- Club status breakdown by age group (%)
- Fashion news subscription frequency by club status
- Geographic concentration (`postal_code`)
- Customer segmentation table

### Products (`articles.csv`)
- Missing values
- Breakdown by product group
- Target customer segment (`index_name`)
- Most represented product types
- Most frequent colours
- Product group x customer segment crosstab

### Transactions (join of the 3 files)
- Volume and time coverage
- Average price spent by age group
- Most purchased categories by age group
- Purchase behavior by club status
- Sales channel (in-store vs online)
- Top 10 best-selling articles

### RFM analysis (section 11)
- Customer purchase profile (Frequency x Amount)
- Value segmentation (`total_spend` quartiles)
- Demographic profile of VIP vs other customers
- Revenue by product category

### Seasonality (section 16)
- Impact of sales periods on revenue

---

## 🌦️ External enrichment (weather & public holidays)

| Source | API used | Content |
|---|---|---|
| Weather | [Open-Meteo](https://open-meteo.com/) | Daily temperatures |
| Public holidays | [Nager.Date](https://date.nager.at/) | Public holiday calendar |

**Analyses performed:**
- Merging sales x weather x public holidays calendar
- Temperature vs revenue / number of transactions
- Impact of public holidays on revenue
- Monthly trend: revenue vs average temperature
- **Statistical significance test** for weather/public holiday influence on sales

> ⚠️ **Decision made**: weather and public holidays are **not included** as features in the ML
> models in section 17, since their statistical influence wasn't judged determinant enough.

---

## 🏗️ Feature Engineering (enriched RFM)

Feature table built **per customer**, from the aggregates already computed during the chunked
join (section 9), without re-reading the large transactions file.

| Feature | Definition | Business interpretation |
|---|---|---|
| `total_spend` | Sum of prices paid | Monetary value (the **M** in RFM) |
| `n_transactions` | Total number of purchases | Purchase frequency (the **F** in RFM) |
| `recency_days` | Days since the last purchase | The **R** in RFM — recent engagement |
| `tenure_days` | Time between first and last purchase | Real activity tenure |
| `avg_basket_value` | `total_spend / n_transactions` | Average basket — purchasing power |
| `purchase_frequency_per_month` | Purchases normalized by months of tenure | Purchase regularity, comparable across customers |
| `n_distinct_categories` | Number of distinct `product_group_name` purchased | Purchase diversity / catalog exploration |
| `segment_valeur` | `total_spend` quartile | Actionable marketing segment (VIP, mid, low) |

**Mathematical formalization of the RFM features (for a customer $u$, with $t_{max}$ = the
dataset's end date):**

$$
\text{total\_spend}_u = \sum_{i=1}^{n_u} price_i
\qquad
\text{n\_transactions}_u = n_u
$$

$$
\text{recency\_days}_u = t_{max} - \max_i(date_i)
\qquad
\text{tenure\_days}_u = \max_i(date_i) - \min_i(date_i)
$$

$$
\text{avg\_basket\_value}_u = \frac{\text{total\_spend}_u}{\text{n\_transactions}_u}
\qquad
\text{purchase\_frequency\_per\_month}_u = \frac{\text{n\_transactions}_u}{\text{tenure\_days}_u / 30}
$$

**`segment_valeur`** — segmentation by `total_spend` quartiles (classic RFM method): customers are
ranked then split into 4 equal-sized groups (25% each) by total amount spent, from the lowest
quartile (low-value customers) to the highest (VIP customers).

---

## 🤖 Export for RAG chatbot

A dedicated section (15) generates:
- A structured, ready-to-use dataset
- A **narrative summary per customer**, meant to be vectorized (embeddings) to feed a
  **RAG (Retrieval-Augmented Generation)** chatbot

---

## 🧠 Machine Learning modeling

> **Data scale — `FULL_SCALE = True`.** The notebook has a scale switch (dedicated cell, section
> 17.1): `FULL_SCALE = False` trains the models on a stratified sample of 50,000 customers
> (suited to a constrained environment); **`FULL_SCALE = True` — the currently active
> configuration** — trains the models that scale (Logistic Regression, Decision Tree, Random
> Forest, linear/regularized regressions, XGBoost, LightGBM, CatBoost, K-Means, GMM) on the full
> **~1.36M purchasing customers**.
>
> **Some methods stay deliberately capped regardless of available RAM**, because their algorithmic
> complexity — not just memory — becomes prohibitive beyond a few tens of thousands of points
> (hours of compute rather than minutes, even on an oversized machine):
>
> | Method | Cap applied even with `FULL_SCALE=True` |
> |---|---|
> | **t-SNE** | 5,000-customer subsample (`viz_sample`) |
> | **Agglomerative hierarchical clustering** | 2,000-customer subsample (`hier_sample_idx`) |
> | **SVM and KNN** | Capped at 50,000 training rows (`Xtr_slow`) |
> | **GridSearchCV** | Hyperparameter search on this same capped subsample, then the selected model is retrained on the full set |
> | **SMOTE** | Majority class capped at 100,000 rows before oversampling, to avoid generating several million synthetic rows |

### A. Dimensionality reduction

| Technique | Use |
|---|---|
| **PCA** (Principal Component Analysis) | Linear dimensionality reduction, explained-variance analysis |
| **t-SNE** | Non-linear 2D visualization of local similarities between customers |
| **UMAP** | Alternative non-linear visualization, better preserving global structure |

#### Mathematical basis

**PCA** — looks for the orthogonal directions (principal components) that maximize the variance of
the projected data. Formally, the covariance matrix $\Sigma$ of the standardized features is
diagonalized:

$$
\Sigma = \frac{1}{n-1} X^T X, \qquad \Sigma v_k = \lambda_k v_k
$$

where $v_k$ is the $k$-th eigenvector (principal component) and $\lambda_k$ its associated
eigenvalue (variance explained by that component). The **cumulative explained variance** guides
how many components to keep:

$$
\text{Cumulative explained variance}(k) = \frac{\sum_{i=1}^{k}\lambda_i}{\sum_{i=1}^{p}\lambda_i}
$$

**t-SNE** — converts Euclidean distances into similarity probabilities (Gaussian distribution in
the original space, heavy-tailed Student t distribution in the reduced space), then minimizes the
Kullback-Leibler divergence between the two distributions:

$$
p_{j|i} = \frac{\exp(-\|x_i-x_j\|^2 / 2\sigma_i^2)}{\sum_{k \neq i}\exp(-\|x_i-x_k\|^2 / 2\sigma_i^2)}, \qquad
KL(P\|Q) = \sum_{i \neq j} p_{ij}\log\frac{p_{ij}}{q_{ij}}
$$

Very effective at revealing local structures (small homogeneous groups), but expensive in
memory/CPU (quadratic algorithm in the number of observations) and poorly suited to very large
volumes.

**UMAP** — relies on a topological approach (simplicial set theory): builds a weighted
neighborhood graph in the original space, then optimizes a layout in the reduced space that
minimizes the fuzzy cross-entropy between the two graphs. Faster than t-SNE and generally better
at preserving both the local **and** global structure of the data.

> These three techniques are used here for **exploratory and visualization** purposes (visually
> checking the separability of future clusters/classes), not as a preprocessing step for the final
> supervised models.

---

### B. Supervised classification — club status (`club_member_status`)

**Goal**: predict whether a customer is `ACTIVE`, `PRE-CREATE`, or `LEFT CLUB`.

> ⚠️ Highly imbalanced classes: `ACTIVE` ≈ 93%, `LEFT CLUB` < 0.1%. A model that always predicts
> `ACTIVE` would already achieve ~93% accuracy without learning anything — hence the systematic
> use of **F1-macro** alongside accuracy.

#### Models tested (default) — how they work

| Model | How it works | Advantages | Limitations |
|---|---|---|---|
| **Decision Tree** | Builds a tree structure where each node applies a decision rule on a variable to separate classes; splits maximize class separation (Gini, Entropy). | Easy to interpret · handles non-linear relationships · little data prep needed | Risk of overfitting · sensitive to small data variations |
| **KNN (K-Nearest Neighbors)** | Classifies a new example by the majority class among its **K nearest neighbors** in feature space. | Simple · no complex training phase · effective if data is well separated | Expensive on large volumes · sensitive to the choice of K and feature scale |
| **Random Forest** | Ensemble of several decision trees (*ensemble learning*), each trained on a different subsample of data and features (bagging). Final decision = majority vote. | Reduces overfitting vs a single tree · good general performance · handles complex relationships | Less interpretable than a single tree · more computationally expensive |
| **SVM (RBF kernel)** | Looks for the hyperplane separating classes with maximum margin; the RBF (*Radial Basis Function*) kernel implicitly transforms the space to create non-linear boundaries. | Very effective on complex, small datasets · good generalization | Sensitive to hyperparameters (`C`, `gamma`) · not efficient on large volumes · needs normalization |
| **Logistic Regression** | Statistical model estimating class membership probability via a linear combination of variables passed through a sigmoid function. | Fast, simple, interpretable · good baseline | Assumes a linear relationship between variables and target · limited on complex relationships |

**RBF-kernel SVM formula:**

$$
K(x_i, x_j) = \exp\left(-\gamma \|x_i - x_j\|^2\right), \qquad \gamma > 0
$$

**Logistic regression formula (probability of belonging to the positive class):**

$$
P(y=1\mid x) = \sigma(\beta_0 + \beta^T x) = \frac{1}{1+e^{-(\beta_0+\beta^T x)}}
$$

#### Results (default models, no tuning)

| Model | Accuracy | F1-macro | Weighted F1 | Interpretation |
|---|---:|---:|---:|---|
| **Random Forest** | **0.9294** | 0.3391 | **0.9012** | Best accuracy and best weighted F1; low F1-macro → performs worse on minority classes |
| **KNN** | 0.9246 | 0.3434 | 0.8998 | Very close to Random Forest, slightly better balance between classes |
| **Decision Tree** | 0.8862 | **0.3627** | 0.8851 | Lower accuracy but best F1-macro among default models |
| **SVM (RBF)** | 0.6278 | 0.3297 | 0.7214 | Weak performance, difficulty separating classes (imbalance / hyperparameters) |
| **Logistic Regression** | 0.5494 | 0.3076 | 0.6687 | Weakest model — likely non-linear relationship between variables and target |

➡️ Even at this stage (before tuning), **F1-macro** reveals a different reality from raw accuracy:
the Decision Tree, weaker on accuracy, handles minority classes better than Random Forest or KNN.

#### Hyperparameter optimization — GridSearchCV

**Principle**: GridSearchCV exhaustively tests every combination of a hyperparameter grid
(`param_grid`), evaluates each combination via cross-validation, then selects the one that
maximizes the chosen metric.

```
Define hyperparameters
        ↓
Test every possible combination
        ↓
Cross-validation for each combination
        ↓
Compute the average score
        ↓
Select the best model
        ↓
Final training with the best parameters
```

**Hyperparameters searched per model:**

| Model | Hyperparameters explored |
|---|---|
| **Random Forest** | `n_estimators` (number of trees), `max_depth` (max depth), `min_samples_split` |
| **KNN** | `n_neighbors` (K), `weights` (neighbor weighting) |
| **SVM** | `C` (error/margin penalty), `gamma` (RBF kernel influence) |

**Cross-validation (k-fold)** — training data is split into $k$ subsets (*folds*); the model is
trained on $k-1$ folds and evaluated on the remaining fold, repeated $k$ times. The final score is
the average of the $k$ scores:

$$
\text{Score}_{CV} = \frac{1}{k}\sum_{i=1}^{k}\text{Score}(\text{fold}_i)
$$

**Choice of `cv` (number of folds):**

| Dataset size | Recommended `cv` | Rationale |
|---|---:|---|
| Small (< 1,000 obs.) | 10 (or LOOCV) | More stable estimate, uses the data better |
| Medium (1,000 – 100,000 obs.) | **5** (chosen) | Good reliability/compute-time trade-off |
| Very large (> 100,000 obs.) | 3 | Reduces compute time |

**Chosen optimization metric — F1-macro**: in a context of imbalanced classes, accuracy
artificially favors the majority class. F1-macro computes each class's F1-score independently
then takes the **unweighted average**, giving each class equal weight:

$$
F1_{macro} = \frac{1}{C}\sum_{c=1}^{C} F1_c, \qquad
F1_c = 2 \cdot \frac{\text{Precision}_c \cdot \text{Recall}_c}{\text{Precision}_c + \text{Recall}_c}
$$

This forces GridSearchCV to select a model that recognizes minority classes (`LEFT CLUB`) as well
as the majority class (`ACTIVE`).

**Results after optimization:**

| Model | Accuracy | F1-macro | Weighted F1 |
|---|---:|---:|---:|
| Decision Tree (optimized) | 0.8862 | 0.3627 | 0.8851 |
| **Random Forest (optimized)** | 0.8750 | **0.3955** | **0.8855** |

*Best Random Forest hyperparameters: `max_depth=20`, `min_samples_leaf=5`, `n_estimators=100`.*

#### Class rebalancing & boosting

With F1-macro still modest (~0.40) after Random Forest optimization, two families of solutions
are tested together:

**1) Data rebalancing techniques**

| Technique | Principle | How it works | Advantages | Limitations |
|---|---|---|---|---|
| **`class_weight="balanced"`** | Class weighting during training | Higher weight to minority classes, lower to majority classes; errors on rare classes penalize training more | Simple, doesn't modify the data, fast | Doesn't create new observations · insufficient if the imbalance is very strong |
| **SMOTE** | Synthetic oversampling | Generates new points by interpolating between a minority example and its nearest neighbors (see formula in the Classification section above) | Increases representation of rare classes · avoids simple duplication | Can create unrealistic examples in mixed zones · sensitive to outliers · adds training cost |
| Classic oversampling (Random OverSampling) | Duplication of minority observations | Copies rare examples multiple times | Simple | High risk of overfitting on the same repeated examples |

> At full scale, fully balancing the classes (~1.27M `ACTIVE`) would generate a disproportionate
> synthetic dataset (~3.8M rows). The majority class fed to SMOTE is therefore capped via prior
> subsampling, for a reasonable memory/time cost.

**2) Boosting models compared**

| Model | Principle | Handling imbalance | Advantages | Limitations |
|---|---|---|---|---|
| **XGBoost** | Ensemble of trees built successively, each new tree corrects the errors of the previous ones (*gradient boosting*) | `scale_pos_weight` to weight minority classes | Very effective on tabular data · handles non-linearity · built-in regularization | Complex parameterization · slower training |
| **LightGBM** | Gradient boosting with optimized trees (*leaf-wise* growth) for speed on large volumes | Supports `class_weight` and dedicated imbalance parameters | Very fast, low memory footprint, very good performance | Can overfit on small datasets · sensitive to tuning |
| **CatBoost** | Gradient boosting with native, optimized handling of categorical variables | Supports class weights | Very effective on mixed data · little preprocessing needed · robust | More computationally expensive than LightGBM |

**General gradient boosting formula** — additive construction of weak models $f_k$ (trees), each
fitted on the residual gradient of the current model's loss function $L$:

$$
F_m(x) = F_{m-1}(x) + \eta \cdot f_m(x), \qquad f_m \approx \underset{f}{\arg\min}\sum_{i=1}^n L\big(y_i, F_{m-1}(x_i) + f(x_i)\big)
$$

where $\eta$ is the learning rate, which controls each new tree's contribution.

**Results — rebalancing x boosting comparison:**

| Approach | Accuracy | F1-macro | Comment |
|---|---:|---:|---|
| **LightGBM + SMOTE** | — | **0.4013** | Best F1-macro across all approaches |
| CatBoost + SMOTE | **0.9147** | slightly < 0.4013 | Best accuracy, but driven by the majority class |
| XGBoost + SMOTE | — | close to LightGBM | Good performance, slightly behind |
| Boosting + `class_weight="balanced"` (no SMOTE) | — | lower F1-macro | Reweights the loss but doesn't add new information about rare classes |

**Comparison with the best classic ensembling model:**

| Model | F1-macro |
|---|---:|
| Optimized Random Forest (GridSearchCV) | 0.3955 |
| **LightGBM + SMOTE** | **0.4013** |

✅ **Model selected: LightGBM + SMOTE** — best F1-macro trade-off for a strongly imbalanced
problem (very minority `LEFT CLUB` class).

#### Mathematical basis of the classification metrics

From the **confusion matrix** (True Positives *TP*, False Positives *FP*, True Negatives *TN*,
False Negatives *FN*):

$$
\text{Accuracy} = \frac{TP+TN}{TP+TN+FP+FN}
\qquad
\text{Precision} = \frac{TP}{TP+FP}
\qquad
\text{Recall} = \frac{TP}{TP+FN}
$$

$$
F1 = 2 \cdot \frac{\text{Precision}\cdot\text{Recall}}{\text{Precision}+\text{Recall}}
$$

- **Accuracy**: overall share of correct predictions — misleading in the presence of class
  imbalance.
- **Precision**: among positive predictions, the share that's actually correct (cost of false
  positives).
- **Recall**: among actually positive cases, the share detected (cost of false negatives).
- **F1-score**: harmonic mean of precision and recall — heavily penalizes an imbalance between
  the two.
- **F1-macro**: unweighted average of per-class F1 (see formula above) — every class counts the
  same regardless of size.
- **Weighted F1**: average of per-class F1, weighted by each class's sample count — closer to
  overall accuracy.

#### SMOTE (Synthetic Minority Over-sampling Technique)

SMOTE generates **synthetic** examples of the minority class (rather than duplicating existing
ones), by interpolating between a minority-class point $x_i$ and one of its $k$ nearest neighbors
$x_{zi}$ (also minority class):

$$
x_{new} = x_i + \lambda \cdot (x_{zi} - x_i), \qquad \lambda \sim \mathcal{U}(0,1)
$$

This lets the model better learn the minority class's decision boundary, unlike plain
`class_weight="balanced"`, which only reweights the loss function without adding new information.

#### Interpretation & detailed analysis

- The progression from Decision Tree (F1-macro = 0.363) → optimized Random Forest (0.395) →
  LightGBM+SMOTE (0.401) shows a **progressive but limited gain**: each technical improvement
  (ensembling, tuning, rebalancing) brings a diminishing marginal gain.
- **CatBoost + SMOTE** reaches the best accuracy (91.47%) but a lower F1-macro than
  LightGBM+SMOTE: a sign that its performance is driven by the majority class `ACTIVE`, without a
  real gain on minority classes — a concrete illustration of why accuracy alone is a misleading
  indicator here.
- The observed ceiling (F1-macro ≈ 0.40) reflects a **structural limitation of the problem**
  rather than a model limitation: the `LEFT CLUB` class represents a tiny fraction of customers,
  and no rebalancing (SMOTE, weighting) can compensate for the near-absence of real signal for
  that class.

**Metrics used**: `accuracy_score`, `f1_score` (macro and weighted), `classification_report`,
`confusion_matrix`.

---

### C. Supervised regression — `total_spend`

**Goal**: predict the total amount spent by a customer from their demographic and behavioral
characteristics.

#### Preventing data leakage
`avg_basket_value` is **deliberately excluded** since it's directly derived from the target:
`avg_basket_value = total_spend / number_of_orders`.

#### Target transformation
Strongly skewed distribution → logarithmic transformation:

```
y = log(1 + total_spend)
```

Conversion back to the original scale: `total_spend = e^y - 1`.

#### Feature selection

| Method | Principle | Result |
|---|---|---|
| **SelectKBest** (`f_regression`) | Evaluates each feature individually against the target | Top **12 features** selected, mostly behavioral |
| **Backward Elimination** (OLS p-values, `statsmodels`) | Iterative removal of non-significant variables in a global model | Cross-validates the variables selected by SelectKBest |

➡️ **SelectKBest chosen** for modeling (simpler to integrate into a scikit-learn pipeline);
Backward Elimination kept as a complementary statistical check.

**SelectKBest (`f_regression`)** — computes, for each feature $x_j$, an F statistic from a
univariate linear regression against the target $y$, then keeps the $k$ variables with the
highest F-statistic (equivalent to the squared correlation, tested for significance):

$$
F_j = \frac{r_j^2 \cdot (n-2)}{1 - r_j^2}, \qquad r_j = \text{corr}(x_j, y)
$$

**Backward Elimination (stepwise downward elimination, OLS p-values)** — starts with the full set
of variables in a multiple linear regression model (`statsmodels.OLS`), then iteratively removes
the variable whose coefficient $\beta_j$ has the highest p-value (the least significant), as long
as it's above a threshold (typically α = 0.05):

$$
H_0: \beta_j = 0 \quad \text{(variable } x_j \text{ has no significant effect on } y \text{)}
$$

Unlike SelectKBest (variable-by-variable evaluation, independent of the others), Backward
Elimination evaluates each variable **in the context of the other variables in the model**, which
lets it detect and remove redundancy between correlated variables (multicollinearity).

#### Models compared (5-fold cross-validation)

| Model | Principle | Formula |
|---|---|---|
| **Linear Regression** | Linear relationship, minimizes squared error | ŷ = β₀ + β₁x₁ + ... + βₚxₚ |
| **Lasso (L1)** | L1 penalty, automatic feature selection | min Σ(yᵢ−ŷᵢ)² + λΣ\|βⱼ\| |
| **Ridge (L2)** | L2 penalty, coefficient shrinkage | min Σ(yᵢ−ŷᵢ)² + λΣβⱼ² |
| **ElasticNet (L1+L2)** | Combines Lasso + Ridge | min Σ(yᵢ−ŷᵢ)² + λ₁Σ\|βⱼ\| + λ₂Σβⱼ² |
| **XGBoost Regressor** | Boosting of successive decision trees | ŷᵢ = Σ fₖ(xᵢ) |

#### Results (test set)

| Model | R² (test) | RMSE | MAE |
|---|---:|---:|---:|
| **XGBoost Regressor** | **0.9433** | **0.3691** | **0.1497** |
| Ridge (L2) | 0.8962 | — | — |
| Linear Regression | 0.8962 | — | — |
| ElasticNet (L1+L2) | 0.8947 | — | — |
| Lasso (L1) | 0.8934 | — | — |

✅ **Model selected: XGBoost Regressor** — a gain of **+4.7 R² points** over the regularized
linear models (0.9433 vs 0.8962), thanks to its ability to capture non-linear relationships and
interactions between behavioral variables.

**Comparative analysis:**
- The four linear models (Linear, Ridge, Lasso, ElasticNet) all converge around **R² ≈ 0.89–0.90**,
  indicating that most of the signal linking behavioral variables to `total_spend` is **linear**
  in nature — consistent with `total_spend` largely being a direct function of `n_transactions` and
  purchase frequency.
- The near-absence of a gap between Linear Regression (0.8962) and Ridge/Lasso/ElasticNet
  (0.8934–0.8962) suggests **little problematic collinearity** among the 12 selected features —
  regularization therefore adds little value here.
- XGBoost's edge over the linear models (+4.7 R² pts) captures **residual non-linear
  interactions** (e.g. the combined effect of tenure and category diversity on spend), invisible
  to a linear model.
- The **MAE of 0.1497** (on the log-transformed scale) and **RMSE of 0.3691** confirm that errors
  remain generally contained and without systematic drift.

**Regression metrics used:**
- **RMSE** (Root Mean Squared Error) — heavily penalizes large errors
- **MAE** (Mean Absolute Error) — average absolute error, more robust to outliers
- **R²** (coefficient of determination) — proportion of variance explained

#### Residual analysis (best model)
- Residuals vs predictions
- Residual distribution
- Residual QQ-plot

➡️ Confirms no major systematic bias.

---

### D. Unsupervised clustering — customer segmentation

#### Choosing the optimal number of clusters (section 17.8.1)

| Criterion | Suggested optimal k |
|---|---:|
| Elbow method (via `KneeLocator`) | **6** |
| Silhouette score | 2 |
| BIC (Bayesian Information Criterion, GMM) | 10 |
| AIC (Akaike Information Criterion, GMM) | 10 |

➡️ **k = 6 chosen**, a trade-off between statistical separation quality and business
interpretability.

#### Mathematical basis for the k-selection criteria

**Elbow method** — plots within-cluster inertia (WCSS, *Within-Cluster Sum of Squares*) as a
function of $k$, and looks for the inflection point ("elbow") beyond which adding a cluster no
longer brings a significant gain. Automated detection via `KneeLocator` (the `kneed` library):

$$
\text{WCSS}(k) = \sum_{c=1}^{k}\sum_{x_i \in C_c} \|x_i - \mu_c\|^2
$$

**Silhouette score** — measures, for each point $i$, how well it's assigned to its cluster
relative to neighboring clusters:

$$
s(i) = \frac{b(i) - a(i)}{\max(a(i), b(i))}
$$

where $a(i)$ is the average distance from $i$ to the other points in its own cluster (cohesion),
and $b(i)$ the average distance from $i$ to the points of the nearest neighboring cluster
(separation). $s(i) \in [-1, 1]$: close to 1 = well grouped, close to 0 = at the boundary,
negative = poorly classified. The overall score is the average across all points.

**BIC / AIC (for the Gaussian Mixture Model)** — information criteria penalizing model complexity
(number of parameters) to avoid overfitting:

$$
\text{AIC} = 2p - 2\ln(\hat{L}), \qquad \text{BIC} = p\ln(n) - 2\ln(\hat{L})
$$

where $\hat{L}$ is the model's maximized likelihood, $p$ the number of parameters, and $n$ the
number of observations. The **lower** the value, the better the fit/complexity trade-off. BIC
penalizes complexity more heavily than AIC on large samples (factor $\ln(n)$ vs $2$).

**Why the 4 criteria diverge (6, 2, 10, 10)**: each optimizes a different objective — the elbow
looks for a simplicity/inertia trade-off, silhouette looks for the maximum geometric separation
(often minimal in k, hence k=2), while BIC/AIC on a GMM look for the best probabilistic fit, which
tends to favor more Gaussian components. The choice of **k=6** is therefore a business trade-off,
not a purely statistical one: it keeps a segmentation granularity that's usable in marketing
(neither too coarse like k=2, nor too fine and hard to interpret like k=10).

#### Comparing 3 clustering algorithms (k=6)

| Algorithm | Principle |
|---|---|
| **K-Means** | Partitioning by minimizing within-cluster inertia (distance to centroids) |
| **Hierarchical Clustering (Agglomerative)** | Iterative merging of the closest clusters (dendrogram) |
| **Gaussian Mixture Model (GMM)** | Probabilistic modeling, mixture of Gaussian distributions |

**Result: K-Means chosen — silhouette score = 0.250** (best trade-off among the three algorithms
tested).

**Mathematical basis:**

- **K-Means** minimizes within-cluster inertia by alternating assignment (each point to the
  nearest centroid) and centroid update (mean of assigned points), until convergence:
$$
\underset{C}{\arg\min}\sum_{c=1}^{k}\sum_{x_i \in C_c}\|x_i - \mu_c\|^2
$$
- **Agglomerative hierarchical clustering** builds a dendrogram by merging, at each step, the two
  closest clusters, according to a linkage criterion (e.g. Ward — minimizes the increase in
  within-cluster variance at each merge).
- **GMM** models the data as a mixture of $k$ multivariate Gaussian distributions, and estimates
  the parameters (means $\mu_c$, covariances $\Sigma_c$, weights $\pi_c$) via the **EM
  (Expectation-Maximization)** algorithm, maximizing the likelihood:
$$
p(x) = \sum_{c=1}^{k}\pi_c \, \mathcal{N}(x \mid \mu_c, \Sigma_c)
$$

**Why K-Means wins here**: unlike hierarchical clustering (memory-expensive — $O(n^2)$) and GMM
(assumes elliptical Gaussian clusters, more sensitive to initialization), K-Means offers the best
performance/scalability/separation-quality trade-off on this RFM feature set, whose clusters are
relatively compact and spherical after standardization (`StandardScaler`).

#### The 6 customer types identified (k=6)

Analyzing the centroids (average value of each feature per cluster) gives a distinct behavioral
profile for each of the **6 customer segments**:

| # | Customer type | Average age | Behavioral profile |
|---|---|---:|---|
| **0** | 🔵 **Regular mid-tier customers** | ~35 y/o | Moderate number of transactions, high tenure, decent purchase diversity. Active but average-value customers. |
| **1** | ⚪ **Inactive older customers** | ~54 y/o | Low number of transactions, low tenure, high recency (last activity long ago). Profile close to a dormant customer. |
| **2** | 🟡 **Young occasional customers** | ~26 y/o | Few transactions, low tenure, limited activity. Occasional-buyer profile. |
| **3** | 🟠 **New, low-engagement customers** | — | Very low tenure, low purchase history, high frequency likely tied to a recent sign-up. To be watched to confirm real engagement. |
| **4** | 🟢 **Loyal, high-value customers** | — | ~139 transactions on average, high tenure, wide category diversity. The **best customers** in the portfolio. |
| **5** | 🟣 **High-basket, low-activity customers** | — | Few transactions but a high average basket (`avg_basket_value > 0.05`). Loyalty-building potential. |

**Grouping into broader profile families:**

| Family | Clusters involved | Common trait |
|---|---|---|
| **High-value customers** | Cluster 4 | High loyalty, high purchase frequency, wide diversity — CRM core target |
| **Occasional / dormant customers** | Clusters 1, 2, 3 | Few purchases, high recency — reactivation campaign targets |
| **High-potential customers** | Cluster 5 | High average basket but low frequency — loyalty-building targets to increase frequency |
| **Mid-tier customers** | Cluster 0 | Stable activity but average value — portfolio core, upsell targets |

➡️ This "family" reading turns the 6 statistical clusters into **4 broad marketing levers**: VIP
loyalty (4), reactivation (1, 2, 3), frequency development (5), and upselling (0).


#### Cluster interpretation — rule extraction via decision tree

A `DecisionTreeClassifier` is trained to **predict K-Means cluster membership**, in order to
translate an unsupervised segmentation into rules readable by non-technical teams.

**Tree fidelity to the K-Means clusters: Accuracy = 90.7%**

**Principle**: a `DecisionTreeClassifier` recursively builds `feature > threshold`-type rules,
choosing at each node the split that maximizes the reduction in impurity (Gini index):

$$
Gini(t) = 1 - \sum_{c=1}^{k} p_c(t)^2, \qquad \Delta Gini = Gini(\text{parent}) - \sum_{\text{children}} \frac{n_{\text{child}}}{n_{\text{parent}}} \, Gini(\text{child})
$$

where $p_c(t)$ is the proportion of observations of class (cluster) $c$ at node $t$. The 90.7%
fidelity means that the tree, trained solely to predict the K-Means cluster *labels* (not the raw
data), correctly reproduces the cluster assignment in 90.7% of cases from simple thresholds on RFM
features — this is **indirect proof that the K-Means clusters are well separated and
explainable** by a small number of thresholds on interpretable variables, rather than by a complex
boundary requiring the standardized N-dimensional space.

**Main rules extracted:**

| Rule | Cluster | Interpretation |
|---|---|---|
| `tenure_days > 307.5` and `n_transactions > 89.5` | Cluster 4 | Very loyal customers, high purchase activity |
| `tenure_days > 307.5` and `n_transactions <= 79.5` | Cluster 0 / 1 | Long-standing customers, moderate activity |
| `tenure_days <= 307.5` and `age <= 39.5` | Cluster 2 / 3 / 5 | Recent customers, differentiated by frequency/basket |
| `avg_basket_value > 0.05` | Cluster 5 | High average basket, limited frequency |
| `age > 39.5` with low activity | Cluster 1 | Older customers, low activity (close to the dormant profile) |
| `n_distinct_categories > 6.5` + high activity | Cluster 4 | Wide purchase diversity, high commercial value |

**Most discriminant variables (in order of importance):**
1. `tenure_days` — tenure
2. `n_transactions` — purchase volume
3. `n_distinct_categories` — purchase diversity
4. `age` and `avg_basket_value` — secondary profiles

**Customer profiles identified:**
- 🏆 Loyal, high-value customers (tenure + many transactions)
- 🛒 Occasional customers (low tenure + low activity)
- 💰 High-potential customers (high average basket, low frequency)
- 😴 Dormant customers (low activity, last interaction long ago)

> This 6-cluster behavioral segmentation is finer-grained than the value-quartile segmentation
> (section 11, 4 segments) — the two approaches are complementary: quartiles for simple reporting,
> clusters for precise marketing targeting.

---

## 📊 Results summary

| Task | Best model | Key metric | Score |
|---|---|---|---:|
| **Classification** (`club_member_status`) | LightGBM + SMOTE | F1-macro | **0.4013** |
| **Regression** (`total_spend`) | XGBoost Regressor | R² (test) | **0.9433** |
| **Clustering** (customer segmentation) | K-Means (k=6) | Silhouette score | **0.250** |
| **Clustering interpretability** | Decision tree | Fidelity (accuracy) | **90.7%** |
| **Customer segmentation** | K-Means | Number of customer types identified | **6 profiles** (0. Regular mid-tier · 1. Inactive older · 2. Young occasional · 3. New low-engagement · 4. Loyal high-value · 5. High-basket/low-activity) |

---

## 🔬 Cross-cutting analysis & perspective

- **Asymmetry between the three ML tasks**: regression (`total_spend`, R² = 0.943) achieves a
  much higher score than classification (F1-macro = 0.401). This isn't a methodological weakness
  but a direct consequence of the **nature of the targets**: `total_spend` is an almost direct
  combination of features already present in the dataset (number of transactions, average
  basket), whereas `club_member_status` depends on behavioral/psychological factors poorly
  captured by purely transactional variables (reasons for unsubscribing, emotional brand
  engagement, etc.).
- **Consistency between clustering and quartile RFM**: the 6-cluster behavioral segmentation
  (section 17.8) and the value-quartile segmentation (section 11) both rely on the same underlying
  variables (amount, frequency, tenure) but at different granularities — their mutual consistency
  (VIP customers in the top quartile ↔ high-value customers in cluster 4) provides a **qualitative
  cross-validation** of the segmentation's robustness.
- **Central role of `tenure_days` and `n_transactions`**: these two variables stand out as the
  most discriminant both in the cluster-interpretation tree and in the regression's feature
  selection (SelectKBest) — a sign that they concentrate most of the usable behavioral signal in
  this dataset.
- **F1-macro capped at ~0.40 is not a pipeline failure** but an honest reflection of an extreme,
  structural class imbalance (`LEFT CLUB` close to 0.1% of customers): no rebalancing technique
  can create predictive signal that doesn't exist in the available data for that class.

## ⚠️ Limitations & improvement ideas

| Limitation | Impact | Improvement idea |
|---|---|---|
| ~~50,000-customer sample out of 1.36M~~ → **resolved**: `FULL_SCALE = True` is now active | The results above reflect training on the full ~1.36M purchasing customers for models that scale | t-SNE, hierarchical clustering, SVM/KNN, and GridSearchCV remain deliberately capped on a subsample (structural algorithmic limit, not a one-off resource constraint — see box in section 17) |
| Limited resources (1 CPU core) | Restricted hyperparameter search | Broader optimization via **Optuna** or **RandomizedSearchCV** |
| Strong class imbalance (`club_member_status`) | Limited F1-macro despite SMOTE and boosting | Advanced rebalancing techniques (ADASYN, asymmetric costs), collecting more `LEFT CLUB` examples |

---

## ▶️ How to run the notebook

### On Google Colab (recommended)
1. Upload the `customers.csv`, `articles.csv`, `transactions_train.csv` files to Google Drive.
2. Adjust the `BASE_PATH` variable in section 0 to the folder's actual path on Drive.
3. Run the cells in order — the notebook will mount the Drive automatically.

### Locally
1. Place the 3 CSV files in the same folder as the notebook (`BASE_PATH = "./"` is used
   automatically if `google.colab` isn't detected).
2. Install the dependencies (see [Environment & dependencies](#-environment--dependencies)).
3. Launch Jupyter: `jupyter notebook Eda_hm_customers.ipynb`.

---

## 📁 Generated files

| File | Description |
|---|---|
| `customers_cleaned.csv` | Cleaned customer dataset (no missing values) |
| Customer feature table | Enriched RFM table (16 columns) ready for modeling |
| Narrative summaries | Per-customer text ready for embedding in a RAG pipeline |

---

*Notebook produced as part of an EDA + Machine Learning analysis on the public H&M Personalized
Fashion Recommendations dataset (Kaggle).*