# 🛍️ H&M Customer Analytics — EDA, Feature Engineering & Machine Learning

Analyse exploratoire complète, nettoyage de données, feature engineering et modélisation Machine Learning sur le dataset **H&M Personalized Fashion Recommendations** (Kaggle), à partir des fichiers `customers.csv`, `articles.csv` et `transactions_train.csv`.

Notebook conçu pour **Google Colab + Google Drive**, avec un mode de repli pour une exécution locale.

---

## 📑 Table des matières

1. [Aperçu du projet](#-aperçu-du-projet)
2. [Jeux de données](#-jeux-de-données)
3. [Environnement & dépendances](#-environnement--dépendances)
4. [Structure du notebook](#-structure-du-notebook)
5. [Nettoyage des données](#-nettoyage-des-données)
6. [Analyse exploratoire (EDA)](#-analyse-exploratoire-eda)
7. [Enrichissement externe (météo & jours fériés)](#-enrichissement-externe-météo--jours-fériés)
8. [Feature Engineering (RFM enrichi)](#-feature-engineering-rfm-enrichi)
9. [Export pour chatbot RAG](#-export-pour-chatbot-rag)
10. [Modélisation Machine Learning](#-modélisation-machine-learning)
    - [Réduction de dimension (PCA, t-SNE, UMAP)](#a-réduction-de-dimension)
    - [Classification — statut club](#b-classification-supervisée--statut-club-club_member_status)
    - [Régression — montant dépensé](#c-régression-supervisée--total_spend)
    - [Clustering — segmentation client](#d-clustering-non-supervisé--segmentation-client)
11. [Synthèse des résultats](#-synthèse-des-résultats)
12. [Limites & pistes d'amélioration](#-limites--pistes-damélioration)
13. [Comment exécuter le notebook](#-comment-exécuter-le-notebook)

---

## 🎯 Aperçu du projet

Le projet a trois objectifs complémentaires :

| Objectif | Description |
|---|---|
| **Comprendre** | Explorer et nettoyer les données clients, produits et transactions H&M pour en dégager des insights business (âge, statut club, comportement d'achat, saisonnalité, météo...). |
| **Prédire** | Construire des modèles supervisés pour prédire le **statut d'abonnement club** (classification) et le **montant total dépensé** par client (régression). |
| **Segmenter** | Identifier des groupes de clients homogènes (clustering non supervisé) et les rendre interprétables pour des équipes métier non-techniques. |

---

## 📂 Jeux de données

| Fichier | Lignes x colonnes | Description |
|---|---|---|
| `customers.csv` | 1 371 980 x 7 | Données démographiques et d'abonnement des clients |
| `articles.csv` | 105 542 x 25 | Catalogue produits (groupe, type, couleur, segment visé...) |
| `transactions_train.csv` | ~31M lignes | Historique des transactions (prix, canal de vente, date) |
| `customers_cleaned.csv` | 1 371 980 x 5 | Export du dataset clients après nettoyage |
| Calendrier météo/jours fériés | 734 x 7 | Données enrichies via API externes |
| Table de features clients | 1 371 980 x 16 | Table RFM enrichie post feature engineering |

> Les données brutes ne sont pas incluses dans ce dépôt (poids trop important) — elles doivent être placées sur Google Drive ou en local, voir [Comment exécuter le notebook](#-comment-exécuter-le-notebook).

---

## ⚙️ Environnement & dépendances

**Langage** : Python 3.12

### Bibliothèques principales

| Catégorie | Bibliothèques |
|---|---|
| Manipulation de données | `pandas`, `numpy` |
| Visualisation | `matplotlib`, `seaborn` |
| Statistiques | `scipy.stats` (skew, kurtosis, normaltest, QQ-plot), `statsmodels` (OLS / Backward Elimination) |
| Prétraitement | `sklearn.preprocessing` (`StandardScaler`, `LabelEncoder`) |
| Réduction de dimension | `sklearn.decomposition.PCA`, `sklearn.manifold.TSNE`, `umap-learn` |
| Clustering | `sklearn.cluster` (`KMeans`, `AgglomerativeClustering`), `sklearn.mixture.GaussianMixture`, `scipy.cluster.hierarchy` (dendrogramme), `kneed` (KneeLocator — méthode du coude) |
| Classification | `sklearn.linear_model.LogisticRegression`, `sklearn.tree.DecisionTreeClassifier`, `sklearn.ensemble.RandomForestClassifier`, `sklearn.neighbors.KNeighborsClassifier`, `sklearn.svm.SVC`, `lightgbm`, `xgboost`, `catboost` |
| Régression | `sklearn.linear_model` (`LinearRegression`, `Lasso`, `Ridge`, `ElasticNet`), `xgboost.XGBRegressor` |
| Rééquilibrage des classes | `imblearn.over_sampling.SMOTE`, `sklearn.utils.class_weight.compute_sample_weight` |
| Sélection de variables | `sklearn.feature_selection.SelectKBest`, `f_regression`, Backward Elimination (p-values OLS via `statsmodels`) |
| Optimisation d'hyperparamètres | `sklearn.model_selection.GridSearchCV`, `cross_validate` |
| Métriques | `accuracy_score`, `f1_score`, `classification_report`, `confusion_matrix`, `mean_squared_error`, `mean_absolute_error`, `r2_score`, `silhouette_score` |
| Données externes | `requests` (API Open-Meteo, API Nager.Date) |
| Autres | `gc` (gestion mémoire), `google.colab.drive` |

### Installation

```bash
pip install pandas numpy matplotlib seaborn scipy statsmodels scikit-learn \
    umap-learn kneed lightgbm xgboost catboost imbalanced-learn requests
```

---

## 🗂️ Structure du notebook

Le notebook est organisé en **17 sections principales** (307 cellules) :

| # | Section |
|---|---|
| 0 | Configuration de l'environnement (Colab + Drive) |
| 1–3 | Aperçu général, valeurs manquantes, analyse de `age` (QQ-plot, skewness/kurtosis) |
| 4–5 | Nettoyage des données (imputation) et synthèse |
| 6–7 | Exploration approfondie du dataset clients nettoyé |
| 8 | Exploration du dataset produits `articles.csv` |
| 9 | Jointure `customers` x `articles` x `transactions` |
| 10 | Synthèse combinée des 3 jeux de données |
| 11 | Analyse RFM (Fréquence x Montant), segmentation par quartiles |
| 12 | Enrichissement météo (Open-Meteo) et jours fériés (Nager.Date) |
| 13 | Synthèse globale mise à jour |
| 14 | Feature Engineering — table de features clients (RFM enrichi) |
| 15 | Export des données pour un chatbot RAG |
| 16 | Périodes de soldes et impact sur le chiffre d'affaires |
| 17 | **Modélisation ML** : PCA, t-SNE/UMAP, K-Means, Classification, Régression, Clustering approfondi |

---

## 🧹 Nettoyage des données

| Colonne | Problème détecté | Traitement retenu |
|---|---|---|
| `FN`, `Active` | NaN = absence réelle d'abonnement/activité (pas une donnée manquante) | Colonnes retirées |
| `age` | Distribution asymétrique (**skewness ≈ 0.61**), non normale (test D'Agostino-Pearson, **p ≈ 0**) | Imputation par la **médiane** |
| `club_member_status` | Variable catégorielle très déséquilibrée | Imputation par le **mode** (`ACTIVE`) |
| `fashion_news_frequency` | Variable catégorielle très déséquilibrée | Imputation par le **mode** (`NONE`) |
| `customer_id`, `postal_code` | Aucune valeur manquante | Aucun traitement |

➡️ Dataset final sans valeur manquante, exporté vers `customers_cleaned.csv`.

### Fondements statistiques de la décision d'imputation

**Skewness (asymétrie)** — mesure le degré d'asymétrie de la distribution autour de la moyenne :

$$
\text{Skewness} = \frac{\frac{1}{n}\sum_{i=1}^{n}(x_i - \bar{x})^3}{\left(\frac{1}{n}\sum_{i=1}^{n}(x_i - \bar{x})^2\right)^{3/2}}
$$

Règle de lecture retenue :

| \|skew\| | Interprétation |
|---|---|
| < 0.5 | Distribution assez symétrique |
| 0.5 – 1 | Asymétrie modérée |
| > 1 | Forte asymétrie |

**Kurtosis (aplatissement)** — mesure l'épaisseur des queues par rapport à une loi normale (kurtosis en excès, normale = 0) :

$$
\text{Kurtosis} = \frac{\frac{1}{n}\sum_{i=1}^{n}(x_i - \bar{x})^4}{\left(\frac{1}{n}\sum_{i=1}^{n}(x_i - \bar{x})^2\right)^{2}} - 3
$$

**Test D'Agostino-Pearson** (`scipy.stats.normaltest`) — combine skewness et kurtosis en une statistique $K^2$ suivant approximativement une loi du χ² à 2 degrés de liberté sous H₀ (normalité) :

$$
K^2 = Z_{skew}^2 + Z_{kurtosis}^2 \;\sim\; \chi^2_{(2)}
$$

Règle de décision (seuil α = 0.05) : **p > 0.05** → on ne rejette pas la normalité ; **p < 0.05** → on la rejette.

**Comparatif des tests de normalité disponibles :**

| Test | Contexte d'usage | Avantages | Limites |
|---|---|---|---|
| Shapiro-Wilk | Petits/moyens échantillons (≲ 5 000 obs.) | Très puissant | Peu adapté aux très grands échantillons |
| **D'Agostino-Pearson** (retenu) | Grands échantillons (n ≥ 20, idéalement > 100) | Combine skewness + kurtosis, adapté aux gros volumes | Nécessite un échantillon suffisamment grand |
| Anderson-Darling | Toutes tailles | Sensible dans les queues de distribution | Pas de p-value directe dans SciPy |
| Kolmogorov-Smirnov | Distribution de référence connue | Simple | Peu adapté si paramètres estimés sur les données |
| Lilliefors | Variante de KS, paramètres estimés | Corrige la limite du KS classique | Non disponible nativement dans SciPy |

➡️ Le **D'Agostino-Pearson** est retenu car `customers` contient ~1,37M de lignes — contexte de "grand échantillon" pour lequel ce test est le plus adapté et directement disponible (`scipy.stats.normaltest`).

### Résultats obtenus sur `age`

| Statistique | Valeur | Interprétation |
|---|---:|---|
| Skewness | ≈ 0.61 | Asymétrie **modérée à droite** (queue étalée vers les âges élevés), au-dessus du seuil de 0.5 |
| Kurtosis | ≈ −0.71 | Distribution **platykurtique** (plus "aplatie" qu'une loi normale) |
| p-value (D'Agostino-Pearson) | ≈ 0 | **Rejet** de l'hypothèse de normalité |

**Règle de décision d'imputation appliquée :**

| Situation | Imputation recommandée |
|---|---|
| Distribution normale | Moyenne |
| Distribution asymétrique / valeurs aberrantes | **Médiane** |
| Variable catégorielle | Mode |

➡️ `age` étant asymétrique et non-normale, l'imputation par la **médiane** est retenue : plus robuste que la moyenne face aux valeurs extrêmes.

> **Note méthodologique** : sur de très grands échantillons, les tests de normalité rejettent presque systématiquement H₀ même pour des écarts mineurs à la normalité (sur-puissance statistique). Le résultat doit donc toujours être interprété conjointement avec les visualisations (histogramme, QQ-plot) et les mesures descriptives (skewness, kurtosis), et pas comme un verdict isolé.

---

## 🔍 Analyse exploratoire (EDA)

### Clients (`customers.csv`)
- Répartition par tranche d'âge
- Âge médian par statut club
- Répartition du statut club par tranche d'âge (%)
- Fréquence d'abonnement aux news mode par statut club
- Concentration géographique (`postal_code`)
- Tableau de segmentation clients

### Produits (`articles.csv`)
- Valeurs manquantes
- Répartition par groupe de produit
- Segment client visé (`index_name`)
- Types de produits les plus représentés
- Couleurs les plus fréquentes
- Croisement groupe de produit x segment client

### Transactions (jointure des 3 fichiers)
- Volume et couverture temporelle
- Prix moyen dépensé par tranche d'âge
- Catégories les plus achetées par tranche d'âge
- Comportement d'achat par statut club
- Canal de vente (magasin vs en ligne)
- Top 10 des articles les plus vendus

### Analyse RFM (section 11)
- Profil d'achat des clients (Fréquence x Montant)
- Segmentation par valeur (quartiles de `total_spend`)
- Profil démographique des clients VIP vs autres
- Chiffre d'affaires par catégorie de produit

### Saisonnalité (section 16)
- Impact des périodes de soldes sur le chiffre d'affaires

---

## 🌦️ Enrichissement externe (météo & jours fériés)

| Source | API utilisée | Contenu |
|---|---|---|
| Météo | [Open-Meteo](https://open-meteo.com/) | Températures journalières |
| Jours fériés | [Nager.Date](https://date.nager.at/) | Calendrier des jours fériés |

**Analyses réalisées :**
- Fusion calendrier ventes x météo x jours fériés
- Température vs chiffre d'affaires / nombre de transactions
- Impact des jours fériés sur le CA
- Évolution mensuelle : CA vs température moyenne
- **Test de significativité statistique** de l'influence météo/jours fériés sur les ventes

> ⚠️ **Décision retenue** : la météo et les jours fériés ne sont **pas inclus** comme features dans les modèles ML de la section 17, leur influence statistique n'étant pas jugée suffisamment déterminante.

---

## 🏗️ Feature Engineering (RFM enrichi)

Table de features construite **par client**, à partir des agrégats déjà calculés lors de la jointure par blocs (section 9), sans relecture du fichier volumineux de transactions.

| Feature | Définition | Interprétation métier |
|---|---|---|
| `total_spend` | Somme des prix payés | Valeur monétaire (le **M** de RFM) |
| `n_transactions` | Nombre total d'achats | Fréquence d'achat (le **F** de RFM) |
| `recency_days` | Jours écoulés depuis le dernier achat | Le **R** de RFM — engagement récent |
| `tenure_days` | Durée entre 1er et dernier achat | Ancienneté réelle d'activité |
| `avg_basket_value` | `total_spend / n_transactions` | Panier moyen — pouvoir d'achat |
| `purchase_frequency_per_month` | Achats normalisés par mois d'ancienneté | Régularité d'achat, comparable entre clients |
| `n_distinct_categories` | Nombre de `product_group_name` distincts achetés | Diversité d'achat / exploration catalogue |
| `segment_valeur` | Quartile de `total_spend` | Segment marketing actionnable (VIP, moyen, bas) |

**Formalisation mathématique des features RFM (pour un client $u$, avec $t_{max}$ = date de fin du dataset) :**

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

**`segment_valeur`** — segmentation par quartiles de `total_spend` (méthode RFM classique) : les clients sont classés puis répartis en 4 groupes de taille égale (25% chacun) selon leur montant total dépensé, du quartile le plus bas (clients à faible valeur) au plus haut (clients VIP).

---

## 🤖 Export pour chatbot RAG

Une section dédiée (15) génère :
- Un jeu de données structuré prêt à l'emploi
- Un **résumé narratif par client**, destiné à être vectorisé (embeddings) pour alimenter un chatbot de type **RAG (Retrieval-Augmented Generation)**

---

## 🧠 Modélisation Machine Learning

> **Échelle des données — `FULL_SCALE = True`.** Le notebook dispose d'une bascule d'échelle (cellule dédiée, section 17.1) : `FULL_SCALE = False` entraîne les modèles sur un échantillon stratifié de 50 000 clients (adapté à un environnement contraint) ; **`FULL_SCALE = True` — configuration actuellement active** — entraîne sur l'intégralité des **~1,36M clients acheteurs** les modèles qui passent à l'échelle (Régression Logistique, Arbre de décision, Random Forest, régressions linéaires/régularisées, XGBoost, LightGBM, CatBoost, K-Means, GMM).
>
> **Certaines méthodes restent volontairement bornées quelle que soit la RAM disponible**, car leur complexité algorithmique — pas seulement mémoire — devient prohibitive au-delà de quelques dizaines de milliers de points (heures de calcul plutôt que minutes, même sur une machine surdimensionnée) :
>
> | Méthode | Plafond appliqué même en `FULL_SCALE=True` |
> |---|---|
> | **t-SNE** | Sous-échantillon de 5 000 clients (`viz_sample`) |
> | **Clustering hiérarchique agglomératif** | Sous-échantillon de 2 000 clients (`hier_sample_idx`) |
> | **SVM et KNN** | Plafonnés à 50 000 lignes d'entraînement (`Xtr_slow`) |
> | **GridSearchCV** | Recherche d'hyperparamètres sur ce même sous-échantillon borné, puis ré-entraînement du modèle retenu sur l'ensemble complet |
> | **SMOTE** | Classe majoritaire plafonnée à 100 000 lignes avant sur-échantillonnage, pour éviter de générer plusieurs millions de lignes synthétiques |

### A. Réduction de dimension

| Technique | Usage |
|---|---|
| **PCA** (Analyse en Composantes Principales) | Réduction linéaire de dimension, analyse de la variance expliquée |
| **t-SNE** | Visualisation non linéaire 2D des similarités locales entre clients |
| **UMAP** | Visualisation non linéaire alternative, préservant mieux la structure globale |

#### Fondements mathématiques

**PCA** — recherche les directions orthogonales (composantes principales) qui maximisent la variance des données projetées. Formellement, on diagonalise la matrice de covariance $\Sigma$ des features standardisées :

$$
\Sigma = \frac{1}{n-1} X^T X, \qquad \Sigma v_k = \lambda_k v_k
$$

où $v_k$ est le $k$-ème vecteur propre (composante principale) et $\lambda_k$ sa valeur propre associée (variance expliquée par cette composante). La **variance expliquée cumulée** guide le choix du nombre de composantes à conserver :

$$
\text{Variance expliquée cumulée}(k) = \frac{\sum_{i=1}^{k}\lambda_i}{\sum_{i=1}^{p}\lambda_i}
$$

**t-SNE** — convertit les distances euclidiennes en probabilités de similarité (distribution gaussienne dans l'espace d'origine, distribution de Student t à queue lourde dans l'espace réduit), puis minimise la divergence de Kullback-Leibler entre les deux distributions :

$$
p_{j|i} = \frac{\exp(-\|x_i-x_j\|^2 / 2\sigma_i^2)}{\sum_{k \neq i}\exp(-\|x_i-x_k\|^2 / 2\sigma_i^2)}, \qquad
KL(P\|Q) = \sum_{i \neq j} p_{ij}\log\frac{p_{ij}}{q_{ij}}
$$

Très efficace pour révéler des structures locales (petits groupes homogènes), mais coûteux en mémoire/CPU (algorithme quadratique en nombre d'observations) et peu adapté à de très grands volumes.

**UMAP** — repose sur une approche topologique (théorie des simplicial sets) : construction d'un graphe pondéré de voisinages dans l'espace d'origine, puis optimisation d'une disposition dans l'espace réduit qui minimise l'entropie croisée floue entre les deux graphes. Plus rapide que t-SNE et généralement meilleur pour préserver à la fois la structure locale **et** la structure globale des données.

> Ces trois techniques sont utilisées ici à des fins **exploratoires et de visualisation** (vérifier visuellement la séparabilité des futurs clusters/classes), et non comme étape de prétraitement des modèles supervisés finaux.

---

### B. Classification supervisée — statut club (`club_member_status`)

**Objectif** : prédire si un client est `ACTIVE`, `PRE-CREATE` ou `LEFT CLUB`.

> ⚠️ Classes très déséquilibrées : `ACTIVE` ≈ 93%, `LEFT CLUB` < 0,1%. Un modèle prédisant toujours `ACTIVE` obtiendrait déjà ~93% d'accuracy sans rien apprendre — d'où l'usage systématique du **F1-macro** en complément.

#### Modèles testés (par défaut) — principe de fonctionnement

| Modèle | Principe de fonctionnement | Avantages | Limites |
|---|---|---|---|
| **Arbre de décision (Decision Tree)** | Construit une structure arborescente où chaque nœud applique une règle de décision sur une variable pour séparer les classes ; les divisions maximisent la séparation (Gini, Entropie). | Facile à interpréter · gère les relations non linéaires · peu de préparation des données | Risque de surapprentissage · sensible aux petites variations des données |
| **KNN (K-Nearest Neighbors)** | Classe un nouvel exemple selon la classe majoritaire parmi ses **K plus proches voisins** dans l'espace des features. | Simple · pas de phase d'entraînement complexe · efficace si les données sont bien séparées | Coûteux sur de grands volumes · sensible au choix de K et à l'échelle des variables |
| **Random Forest** | Ensemble de plusieurs arbres de décision (*ensemble learning*), chacun entraîné sur un sous-échantillon différent des données et des variables (bagging). Décision finale = vote majoritaire. | Réduit le surapprentissage vs un arbre seul · bonne performance générale · gère les relations complexes | Moins interprétable qu'un arbre seul · plus coûteux en calcul |
| **SVM (noyau RBF)** | Cherche l'hyperplan séparant les classes avec la marge maximale ; le noyau RBF (*Radial Basis Function*) transforme implicitement l'espace pour créer des frontières non linéaires. | Très performant sur données complexes peu nombreuses · bonne généralisation | Sensible aux hyperparamètres (`C`, `gamma`) · peu efficace sur beaucoup de données · nécessite normalisation |
| **Régression Logistique** | Modèle statistique estimant la probabilité d'appartenance à une classe via une combinaison linéaire des variables passée dans une fonction sigmoïde. | Rapide, simple, interprétable · bonne baseline | Suppose une relation linéaire variables/cible · limité sur relations complexes |

**Formule du SVM à noyau RBF :**

$$
K(x_i, x_j) = \exp\left(-\gamma \|x_i - x_j\|^2\right), \qquad \gamma > 0
$$

**Formule de la régression logistique (probabilité d'appartenance à la classe positive) :**

$$
P(y=1\mid x) = \sigma(\beta_0 + \beta^T x) = \frac{1}{1+e^{-(\beta_0+\beta^T x)}}
$$

#### Résultats (modèles par défaut, sans tuning)

| Modèle | Accuracy | F1-macro | F1-pondéré | Interprétation |
|---|---:|---:|---:|---|
| **Random Forest** | **0.9294** | 0.3391 | **0.9012** | Meilleure accuracy et meilleur F1-pondéré ; F1-macro faible → performe moins bien sur les classes minoritaires |
| **KNN** | 0.9246 | 0.3434 | 0.8998 | Très proche de Random Forest, équilibre un peu meilleur entre classes |
| **Arbre de décision** | 0.8862 | **0.3627** | 0.8851 | Accuracy plus faible mais meilleur F1-macro parmi les modèles par défaut |
| **SVM (RBF)** | 0.6278 | 0.3297 | 0.7214 | Performance faible, difficulté à séparer les classes (déséquilibre / hyperparamètres) |
| **Régression Logistique** | 0.5494 | 0.3076 | 0.6687 | Modèle le plus faible — relation vraisemblablement non linéaire entre variables et cible |

➡️ Même à ce stade (avant tuning), le **F1-macro** révèle une réalité différente de l'accuracy brute : l'Arbre de décision, moins bon en accuracy, gère mieux les classes minoritaires que Random Forest ou KNN.

#### Optimisation des hyperparamètres — GridSearchCV

**Principe** : GridSearchCV teste exhaustivement toutes les combinaisons d'une grille d'hyperparamètres (`param_grid`), évalue chaque combinaison par validation croisée, puis sélectionne celle qui maximise la métrique choisie.

```
Définition des hyperparamètres
        ↓
Test de toutes les combinaisons possibles
        ↓
Validation croisée pour chaque combinaison
        ↓
Calcul du score moyen
        ↓
Sélection du meilleur modèle
        ↓
Entraînement final avec les meilleurs paramètres
```

**Hyperparamètres recherchés par modèle :**

| Modèle | Hyperparamètres explorés |
|---|---|
| **Random Forest** | `n_estimators` (nb d'arbres), `max_depth` (profondeur max), `min_samples_split` |
| **KNN** | `n_neighbors` (K), `weights` (pondération des voisins) |
| **SVM** | `C` (pénalisation des erreurs / marge), `gamma` (influence du noyau RBF) |

**Validation croisée (Cross-Validation, k-fold)** — les données d'entraînement sont divisées en $k$ sous-ensembles (*folds*) ; le modèle est entraîné sur $k-1$ folds et évalué sur le fold restant, répété $k$ fois. Le score final est la moyenne des $k$ scores :

$$
\text{Score}_{CV} = \frac{1}{k}\sum_{i=1}^{k}\text{Score}(\text{fold}_i)
$$

**Choix de `cv` (nombre de folds) :**

| Taille du dataset | `cv` recommandé | Justification |
|---|---:|---|
| Petit (< 1 000 obs.) | 10 (ou LOOCV) | Estimation plus stable, utilise mieux les données |
| Moyen (1 000 – 100 000 obs.) | **5** (retenu) | Bon compromis fiabilité / temps de calcul |
| Très grand (> 100 000 obs.) | 3 | Réduit le temps de calcul |

**Métrique d'optimisation retenue — F1-macro** : dans un contexte de classes déséquilibrées, l'accuracy favorise artificiellement la classe majoritaire. Le F1-macro calcule le F1-score de chaque classe indépendamment puis en fait la **moyenne non pondérée**, donnant le même poids à chaque classe :

$$
F1_{macro} = \frac{1}{C}\sum_{c=1}^{C} F1_c, \qquad
F1_c = 2 \cdot \frac{\text{Precision}_c \cdot \text{Recall}_c}{\text{Precision}_c + \text{Recall}_c}
$$

Cela force GridSearchCV à sélectionner un modèle qui reconnaît aussi bien les classes minoritaires (`LEFT CLUB`) que la classe majoritaire (`ACTIVE`).

**Résultats après optimisation :**

| Modèle | Accuracy | F1-macro | F1-pondéré |
|---|---:|---:|---:|
| Arbre de décision (optimisé) | 0.8862 | 0.3627 | 0.8851 |
| **Random Forest (optimisé)** | 0.8750 | **0.3955** | **0.8855** |

*Meilleurs hyperparamètres Random Forest : `max_depth=20`, `min_samples_leaf=5`, `n_estimators=100`.*

#### Rééquilibrage des classes & boosting

Le F1-macro restant modeste (~0,40) après optimisation de Random Forest, deux familles de solutions sont testées conjointement :

**1) Techniques de rééquilibrage des données**

| Technique | Principe | Fonctionnement | Avantages | Limites |
|---|---|---|---|---|
| **`class_weight="balanced"`** | Pondération des classes pendant l'apprentissage | Poids plus élevé aux classes minoritaires, plus faible aux classes majoritaires ; les erreurs sur les classes rares pénalisent davantage l'entraînement | Simple, ne modifie pas les données, rapide | Ne crée pas de nouvelles observations · insuffisant si déséquilibre très fort |
| **SMOTE** | Sur-échantillonnage synthétique | Génère de nouveaux points par interpolation entre un exemple minoritaire et ses voisins proches (voir formule dans la section Classification ci-dessus) | Augmente la représentation des classes rares · évite la simple duplication | Peut créer des exemples peu réalistes en zones mélangées · sensible aux outliers · alourdit l'entraînement |
| Sur-échantillonnage classique (Random OverSampling) | Duplication des observations minoritaires | Copie des exemples rares plusieurs fois | Simple | Risque élevé de surapprentissage sur les mêmes exemples répétés |

> À pleine échelle, équilibrer totalement les classes (~1,27M `ACTIVE`) générerait un jeu synthétique disproportionné (~3,8M lignes). La classe majoritaire fournie à SMOTE est donc plafonnée via sous-échantillonnage préalable, pour un coût mémoire/temps raisonnable.

**2) Modèles de boosting comparés**

| Modèle | Principe | Gestion du déséquilibre | Avantages | Limites |
|---|---|---|---|---|
| **XGBoost** | Ensemble d'arbres construits successivement, chaque nouvel arbre corrige les erreurs des précédents (*gradient boosting*) | `scale_pos_weight` pour pondérer les classes minoritaires | Très performant sur tabulaire · gère le non linéaire · régularisation intégrée | Paramétrage complexe · entraînement plus lent |
| **LightGBM** | Gradient boosting à arbres optimisés (croissance *leaf-wise*) pour la rapidité sur gros volumes | Supporte `class_weight` et paramètres dédiés au déséquilibre | Très rapide, faible empreinte mémoire, très bonnes performances | Peut sur-apprendre sur petits datasets · sensible au réglage |
| **CatBoost** | Gradient boosting avec traitement natif optimisé des variables catégorielles | Supporte les poids de classes | Très performant sur données mixtes · peu de prétraitement nécessaire · robuste | Plus coûteux en calcul que LightGBM |

**Formule générale du gradient boosting** — construction additive de modèles faibles $f_k$ (arbres), chacun ajusté sur le gradient résiduel de la fonction de perte $L$ du modèle courant :

$$
F_m(x) = F_{m-1}(x) + \eta \cdot f_m(x), \qquad f_m \approx \underset{f}{\arg\min}\sum_{i=1}^n L\big(y_i, F_{m-1}(x_i) + f(x_i)\big)
$$

où $\eta$ est le taux d'apprentissage (*learning rate*), qui contrôle la contribution de chaque nouvel arbre.

**Résultats — comparaison rééquilibrage x boosting :**

| Approche | Accuracy | F1-macro | Commentaire |
|---|---:|---:|---|
| **LightGBM + SMOTE** | — | **0.4013** | Meilleur F1-macro toutes approches confondues |
| CatBoost + SMOTE | **0.9147** | légèrement < 0.4013 | Meilleure accuracy, mais tirée par la classe majoritaire |
| XGBoost + SMOTE | — | proche de LightGBM | Bonnes performances, un peu en retrait |
| Boosting + `class_weight="balanced"` (sans SMOTE) | — | F1-macro plus faible | Repondère la perte mais n'ajoute pas d'information nouvelle sur les classes rares |

**Comparaison avec le meilleur modèle par ensembling classique :**

| Modèle | F1-macro |
|---|---:|
| Random Forest optimisé (GridSearchCV) | 0.3955 |
| **LightGBM + SMOTE** | **0.4013** |

✅ **Modèle retenu : LightGBM + SMOTE** — meilleur compromis F1-macro pour un problème fortement déséquilibré (classe `LEFT CLUB` très minoritaire).

#### Fondements mathématiques des métriques de classification

À partir de la **matrice de confusion** (Vrais Positifs *TP*, Faux Positifs *FP*, Vrais Négatifs *TN*, Faux Négatifs *FN*) :

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

- **Accuracy** : proportion globale de prédictions correctes — trompeuse en cas de déséquilibre des classes.
- **Precision** : parmi les prédictions positives, proportion réellement correcte (coût des faux positifs).
- **Recall** : parmi les cas réellement positifs, proportion détectée (coût des faux négatifs).
- **F1-score** : moyenne harmonique de precision et recall — pénalise fortement un déséquilibre entre les deux.
- **F1-macro** : moyenne non pondérée des F1 par classe (voir formule ci-dessus) — chaque classe compte autant, quelle que soit sa taille.
- **F1-pondéré** : moyenne des F1 par classe, pondérée par le nombre d'échantillons de chaque classe — plus proche de l'accuracy globale.

#### SMOTE (Synthetic Minority Over-sampling Technique)

SMOTE génère des exemples **synthétiques** de la classe minoritaire (plutôt que de dupliquer les exemples existants), en interpolant entre un point $x_i$ de la classe minoritaire et l'un de ses $k$ plus proches voisins $x_{zi}$ (également minoritaire) :

$$
x_{new} = x_i + \lambda \cdot (x_{zi} - x_i), \qquad \lambda \sim \mathcal{U}(0,1)
$$

Cela permet au modèle de mieux apprendre la frontière de décision de la classe minoritaire, contrairement au simple `class_weight="balanced"` qui ne fait que repondérer la fonction de coût sans ajouter d'information nouvelle.

#### Interprétation & analyse détaillée

- Le passage de l'Arbre de décision (F1-macro = 0.363) → Random Forest optimisé (0.395) → LightGBM+SMOTE (0.401) montre un **gain progressif mais limité** : chaque amélioration technique (ensembling, tuning, rééquilibrage) apporte un gain marginal décroissant.
- **CatBoost + SMOTE** atteint la meilleure accuracy (91.47%) mais un F1-macro inférieur à LightGBM+SMOTE : signe que sa performance est tirée par la classe majoritaire `ACTIVE`, sans réel gain sur les classes minoritaires — illustration concrète de pourquoi l'accuracy seule est un indicateur trompeur ici.
- Le plafond observé (F1-macro ≈ 0.40) reflète une **limite structurelle du problème** plutôt qu'une limite des modèles : la classe `LEFT CLUB` représente une fraction infime des clients, et aucun rééquilibrage (SMOTE, pondération) ne peut compenser une quasi-absence de signal réel pour cette classe.

**Métriques utilisées** : `accuracy_score`, `f1_score` (macro et pondéré), `classification_report`, `confusion_matrix`.

---

### C. Régression supervisée — `total_spend`

**Objectif** : prédire le montant total dépensé par un client à partir de ses caractéristiques démographiques et comportementales.

#### Prévention de la fuite de données (data leakage)
`avg_basket_value` est **volontairement exclue** car directement dérivée de la cible : `avg_basket_value = total_spend / nombre_de_commandes`.

#### Transformation de la cible
Distribution fortement asymétrique → transformation logarithmique :

```
y = log(1 + total_spend)
```

Reconversion à l'échelle originale : `total_spend = e^y - 1`.

#### Sélection de variables (Feature Selection)

| Méthode | Principe | Résultat |
|---|---|---|
| **SelectKBest** (`f_regression`) | Évalue chaque feature individuellement par rapport à la cible | Top **12 features** retenues, principalement comportementales |
| **Backward Elimination** (p-values OLS, `statsmodels`) | Élimination itérative des variables non significatives dans un modèle global | Validation croisée des variables retenues par SelectKBest |

➡️ **SelectKBest retenue** pour la modélisation (plus simple à intégrer dans un pipeline scikit-learn) ; Backward Elimination conservée comme validation statistique complémentaire.

**SelectKBest (`f_regression`)** — calcule pour chaque feature $x_j$ une statistique F issue d'une régression linéaire univariée avec la cible $y$, puis conserve les $k$ variables avec la F-statistique la plus élevée (équivalent à la corrélation au carré, testée pour sa significativité) :

$$
F_j = \frac{r_j^2 \cdot (n-2)}{1 - r_j^2}, \qquad r_j = \text{corr}(x_j, y)
$$

**Backward Elimination (élimination pas à pas descendante, p-values OLS)** — démarre avec l'ensemble complet des variables dans un modèle de régression linéaire multiple (`statsmodels.OLS`), puis retire itérativement la variable dont la p-value associée à son coefficient $\beta_j$ est la plus élevée (la moins significative), tant qu'elle dépasse un seuil (typiquement α = 0.05) :

$$
H_0: \beta_j = 0 \quad \text{(la variable } x_j \text{ n'a pas d'effet significatif sur } y \text{)}
$$

Contrairement à SelectKBest (évaluation variable par variable, indépendante des autres), Backward Elimination évalue chaque variable **dans le contexte des autres variables du modèle**, ce qui permet de détecter et d'éliminer la redondance entre variables corrélées (multicolinéarité).

#### Modèles comparés (validation croisée à 5 plis)

| Modèle | Principe | Formule |
|---|---|---|
| **Régression Linéaire** | Relation linéaire, minimisation de l'erreur quadratique | ŷ = β₀ + β₁x₁ + ... + βₚxₚ |
| **Lasso (L1)** | Pénalité L1, sélection automatique de variables | min Σ(yᵢ−ŷᵢ)² + λΣ\|βⱼ\| |
| **Ridge (L2)** | Pénalité L2, réduction des coefficients | min Σ(yᵢ−ŷᵢ)² + λΣβⱼ² |
| **ElasticNet (L1+L2)** | Combinaison Lasso + Ridge | min Σ(yᵢ−ŷᵢ)² + λ₁Σ\|βⱼ\| + λ₂Σβⱼ² |
| **XGBoost Regressor** | Boosting d'arbres de décision successifs | ŷᵢ = Σ fₖ(xᵢ) |

#### Résultats (test set)

| Modèle | R² (test) | RMSE | MAE |
|---|---:|---:|---:|
| **XGBoost Regressor** | **0.9433** | **0.3691** | **0.1497** |
| Ridge (L2) | 0.8962 | — | — |
| Régression Linéaire | 0.8962 | — | — |
| ElasticNet (L1+L2) | 0.8947 | — | — |
| Lasso (L1) | 0.8934 | — | — |

✅ **Modèle retenu : XGBoost Regressor** — gain de **+4.7 points de R²** par rapport aux modèles linéaires régularisés (0.9433 vs 0.8962), grâce à sa capacité à capturer les relations non linéaires et les interactions entre variables comportementales.

**Analyse comparative :**
- Les quatre modèles linéaires (Linéaire, Ridge, Lasso, ElasticNet) convergent tous autour de **R² ≈ 0.89–0.90**, ce qui indique que l'essentiel du signal reliant les variables comportementales à `total_spend` est de nature **linéaire** — cohérent avec le fait que `total_spend` est en grande partie une fonction directe de `n_transactions` et de la fréquence d'achat.
- La quasi-absence d'écart entre Régression Linéaire (0.8962) et Ridge/Lasso/ElasticNet (0.8934–0.8962) suggère une **faible colinéarité problématique** entre les 12 features retenues — la régularisation n'apporte donc que peu de valeur ajoutée ici.
- L'écart de XGBoost par rapport aux modèles linéaires (+4.7 pts de R²) capture les **interactions non linéaires résiduelles** (p. ex. effet combiné de l'ancienneté et de la diversité de catégories sur la dépense), invisibles à un modèle linéaire.
- Le **MAE de 0.1497** (sur l'échelle log-transformée) et le **RMSE de 0.3691** confirment que les erreurs restent globalement contenues et sans dérive systématique.

**Métriques de régression utilisées :**
- **RMSE** (Root Mean Squared Error) — pénalise fortement les grandes erreurs
- **MAE** (Mean Absolute Error) — erreur moyenne absolue, plus robuste aux outliers
- **R²** (coefficient de détermination) — proportion de variance expliquée

#### Analyse résiduelle (meilleur modèle)
- Résidus vs prédictions
- Distribution des résidus
- QQ-plot des résidus

➡️ Absence de biais systématique majeur confirmée.

---

### D. Clustering non supervisé — segmentation client

#### Choix du nombre de clusters optimal (section 17.8.1)

| Critère | k optimal suggéré |
|---|---:|
| Méthode du coude (Elbow, via `KneeLocator`) | **6** |
| Score de silhouette | 2 |
| BIC (Bayesian Information Criterion, GMM) | 10 |
| AIC (Akaike Information Criterion, GMM) | 10 |

➡️ **k = 6 retenu**, compromis entre qualité de séparation statistique et interprétabilité métier.

#### Fondements mathématiques des critères de choix de k

**Méthode du coude (Elbow)** — trace l'inertie intra-cluster (WCSS, *Within-Cluster Sum of Squares*) en fonction de $k$, et recherche le point d'inflexion ("coude") au-delà duquel ajouter un cluster n'apporte plus de gain significatif. Détection automatisée via `KneeLocator` (librairie `kneed`) :

$$
\text{WCSS}(k) = \sum_{c=1}^{k}\sum_{x_i \in C_c} \|x_i - \mu_c\|^2
$$

**Score de silhouette** — mesure, pour chaque point $i$, à quel point il est bien assigné à son cluster par rapport aux clusters voisins :

$$
s(i) = \frac{b(i) - a(i)}{\max(a(i), b(i))}
$$

où $a(i)$ est la distance moyenne de $i$ aux autres points de son propre cluster (cohésion), et $b(i)$ la distance moyenne de $i$ aux points du cluster voisin le plus proche (séparation). $s(i) \in [-1, 1]$ : proche de 1 = bien groupé, proche de 0 = à la frontière, négatif = mal classé. Le score global est la moyenne sur tous les points.

**BIC / AIC (pour le Gaussian Mixture Model)** — critères d'information pénalisant la complexité du modèle (nombre de paramètres) pour éviter le surapprentissage :

$$
\text{AIC} = 2p - 2\ln(\hat{L}), \qquad \text{BIC} = p\ln(n) - 2\ln(\hat{L})
$$

où $\hat{L}$ est la vraisemblance maximisée du modèle, $p$ le nombre de paramètres, et $n$ le nombre d'observations. Plus la valeur est **faible**, meilleur est le compromis ajustement/complexité. Le BIC pénalise davantage la complexité que l'AIC sur de grands échantillons (facteur $\ln(n)$ vs $2$).

**Pourquoi les 4 critères divergent (6, 2, 10, 10)** : chacun optimise un objectif différent — l'elbow cherche un compromis simplicité/inertie, la silhouette cherche la séparation géométrique maximale (souvent minimale en k, d'où k=2), tandis que BIC/AIC sur un GMM cherchent le meilleur ajustement probabiliste, qui tend à favoriser davantage de composantes gaussiennes. Le choix de **k=6** est donc un arbitrage métier, pas uniquement statistique : il conserve une granularité de segmentation exploitable en marketing (ni trop grossière comme k=2, ni trop fine et difficile à interpréter comme k=10).

#### Comparaison de 3 algorithmes de clustering (k=6)

| Algorithme | Principe |
|---|---|
| **K-Means** | Partitionnement en minimisant l'inertie intra-cluster (distance aux centroïdes) |
| **Clustering Hiérarchique (Agglomératif)** | Fusion itérative des clusters les plus proches (dendrogramme) |
| **Gaussian Mixture Model (GMM)** | Modélisation probabiliste, mélange de distributions gaussiennes |

**Résultat : K-Means retenu — score de silhouette = 0.250** (meilleur compromis parmi les trois algorithmes testés).

**Fondements mathématiques :**

- **K-Means** minimise l'inertie intra-cluster en alternant assignation (chaque point au centroïde le plus proche) et mise à jour des centroïdes (moyenne des points assignés), jusqu'à convergence :
$$
\underset{C}{\arg\min}\sum_{c=1}^{k}\sum_{x_i \in C_c}\|x_i - \mu_c\|^2
$$
- **Clustering hiérarchique agglomératif** construit un dendrogramme en fusionnant à chaque étape les deux clusters les plus proches, selon un critère de liaison (*linkage*, p.ex. Ward — minimise l'augmentation de variance intra-cluster à chaque fusion).
- **GMM** modélise les données comme un mélange de $k$ distributions gaussiennes multivariées, et estime les paramètres (moyennes $\mu_c$, covariances $\Sigma_c$, poids $\pi_c$) par l'algorithme **EM (Expectation-Maximization)**, en maximisant la vraisemblance :
$$
p(x) = \sum_{c=1}^{k}\pi_c \, \mathcal{N}(x \mid \mu_c, \Sigma_c)
$$

**Pourquoi K-Means l'emporte ici** : contrairement au clustering hiérarchique (coûteux en mémoire — $O(n^2)$) et à GMM (suppose des clusters gaussiens elliptiques, plus sensible à l'initialisation), K-Means offre le meilleur compromis performance/scalabilité/qualité de séparation sur ce jeu de features RFM, dont les clusters sont relativement compacts et sphériques après standardisation (`StandardScaler`).

#### Les 6 types de clients identifiés (k=6)

L'analyse des centroïdes (valeurs moyennes de chaque feature par cluster) permet de dresser un profil comportemental distinct pour chacun des **6 segments clients** :

| # | Type de client | Âge moyen | Profil comportemental |
|---|---|---:|---|
| **0** | 🔵 **Clients réguliers intermédiaires** | ~35 ans | Nombre de transactions modéré, ancienneté élevée, diversité d'achat correcte. Clients actifs mais à valeur moyenne. |
| **1** | ⚪ **Clients âgés inactifs** | ~54 ans | Faible nombre de transactions, faible ancienneté, forte récence (dernière activité ancienne). Profil proche de client dormant. |
| **2** | 🟡 **Jeunes clients occasionnels** | ~26 ans | Peu de transactions, faible ancienneté, activité limitée. Profil d'acheteur occasionnel. |
| **3** | 🟠 **Nouveaux clients à faible engagement** | — | Très faible ancienneté, faible historique d'achat, fréquence élevée probablement liée à une inscription récente. À surveiller pour confirmer l'engagement réel. |
| **4** | 🟢 **Clients fidèles à forte valeur** | — | ~139 transactions en moyenne, forte ancienneté, grande diversité de catégories achetées. Les **meilleurs clients** du portefeuille. |
| **5** | 🟣 **Clients à panier élevé mais faible activité** | — | Peu de transactions mais panier moyen élevé (`avg_basket_value > 0.05`). Potentiel de fidélisation. |

**Regroupement par grande famille de profils :**

| Famille | Clusters concernés | Caractéristique commune |
|---|---|---|
| **Clients à forte valeur** | Cluster 4 | Forte fidélité, forte fréquence d'achat, grande diversité — cœur de cible du CRM |
| **Clients occasionnels / dormants** | Clusters 1, 2, 3 | Peu d'achats, récence élevée — cibles de campagnes de réactivation |
| **Clients à potentiel** | Cluster 5 | Panier moyen élevé mais fréquence faible — cibles d'actions de fidélisation pour augmenter la fréquence |
| **Clients intermédiaires** | Cluster 0 | Activité stable mais valeur moyenne — cœur de portefeuille, cible de montée en gamme (*upsell*) |

➡️ Cette lecture par "familles" transforme les 6 clusters statistiques en **4 grands leviers d'action marketing** : fidélisation VIP (4), réactivation (1, 2, 3), développement de fréquence (5), et montée en gamme (0).


#### Interprétation des clusters — extraction de règles via arbre de décision

Un `DecisionTreeClassifier` est entraîné pour **prédire l'appartenance aux clusters K-Means**, dans le but de traduire une segmentation non supervisée en règles lisibles par des équipes non-techniques.

**Fidélité de l'arbre aux clusters K-Means : Accuracy = 90.7%**

**Principe** : un `DecisionTreeClassifier` construit récursivement des règles de type `feature > seuil` en choisissant à chaque nœud la division qui maximise la réduction d'impureté (indice de Gini) :

$$
Gini(t) = 1 - \sum_{c=1}^{k} p_c(t)^2, \qquad \Delta Gini = Gini(\text{parent}) - \sum_{\text{enfants}} \frac{n_{\text{enfant}}}{n_{\text{parent}}} \, Gini(\text{enfant})
$$

où $p_c(t)$ est la proportion d'observations de la classe (cluster) $c$ au nœud $t$. La fidélité de 90.7% signifie que l'arbre, entraîné à prédire uniquement les *labels* de cluster K-Means (et non les données brutes), reproduit correctement l'assignation de cluster dans 90.7% des cas à partir de règles simples sur les features RFM — c'est une **preuve indirecte que les clusters K-Means sont bien séparés et explicables** par un petit nombre de seuils sur des variables interprétables, plutôt que par une frontière complexe nécessitant l'espace standardisé à N dimensions.

**Principales règles extraites :**

| Règle | Cluster | Interprétation |
|---|---|---|
| `tenure_days > 307.5` et `n_transactions > 89.5` | Cluster 4 | Clients très fidèles, forte activité d'achat |
| `tenure_days > 307.5` et `n_transactions <= 79.5` | Cluster 0 / 1 | Clients anciens, activité modérée |
| `tenure_days <= 307.5` et `age <= 39.5` | Cluster 2 / 3 / 5 | Clients récents, différenciés par fréquence/panier |
| `avg_basket_value > 0.05` | Cluster 5 | Panier moyen élevé, fréquence limitée |
| `age > 39.5` avec faible activité | Cluster 1 | Clients âgés, peu actifs (proches du profil dormant) |
| `n_distinct_categories > 6.5` + forte activité | Cluster 4 | Grande diversité d'achat, forte valeur commerciale |

**Variables les plus discriminantes (par ordre d'importance) :**
1. `tenure_days` — ancienneté
2. `n_transactions` — volume d'achat
3. `n_distinct_categories` — diversité d'achat
4. `age` et `avg_basket_value` — profils secondaires

**Profils de clients dégagés :**
- 🏆 Clients fidèles à forte valeur (ancienneté + nombreuses transactions)
- 🛒 Clients occasionnels (faible ancienneté + faible activité)
- 💰 Clients à potentiel (panier moyen élevé, fréquence faible)
- 😴 Clients dormants (faible activité, dernière interaction ancienne)

> Cette segmentation comportementale à 6 clusters est plus fine que la segmentation par quartiles de valeur (section 11, 4 segments) — les deux approches sont complémentaires : quartiles pour le reporting simple, clusters pour un ciblage marketing précis.

---

## 📊 Synthèse des résultats

| Tâche | Meilleur modèle | Métrique clé | Score |
|---|---|---|---:|
| **Classification** (`club_member_status`) | LightGBM + SMOTE | F1-macro | **0.4013** |
| **Régression** (`total_spend`) | XGBoost Regressor | R² (test) | **0.9433** |
| **Clustering** (segmentation client) | K-Means (k=6) | Score de silhouette | **0.250** |
| **Interprétabilité du clustering** | Arbre de décision | Fidélité (accuracy) | **90.7%** |
| **Segmentation client** | K-Means | Nombre de types de clients identifiés | **6 profils** (0. Réguliers intermédiaires · 1. Âgés inactifs · 2. Jeunes occasionnels · 3. Nouveaux à faible engagement · 4. Fidèles à forte valeur · 5. Panier élevé/faible activité) |

---

## 🔬 Analyse transversale & mise en perspective

- **Asymétrie des trois tâches ML** : la régression (`total_spend`, R² = 0.943) obtient un score bien supérieur à la classification (F1-macro = 0.401). Ceci n'est pas une faiblesse de méthode mais une conséquence directe de la **nature des cibles** : `total_spend` est une combinaison quasi-directe de features déjà présentes dans le jeu de données (nombre de transactions, panier moyen), alors que `club_member_status` dépend de facteurs comportementaux/psychologiques peu capturés par des variables purement transactionnelles (raisons d'un désabonnement, engagement affectif à la marque, etc.).
- **Cohérence entre clustering et RFM par quartiles** : la segmentation comportementale à 6 clusters (section 17.8) et la segmentation par quartiles de valeur (section 11) s'appuient toutes deux sur les mêmes variables sous-jacentes (montant, fréquence, ancienneté) mais à des granularités différentes — leur cohérence mutuelle (clients VIP en quartile ↔ clients à forte valeur en cluster 4) constitue une **validation croisée qualitative** de la robustesse de la segmentation.
- **Rôle central de `tenure_days` et `n_transactions`** : ces deux variables ressortent comme les plus discriminantes à la fois dans l'arbre d'interprétation des clusters et dans la sélection de features de la régression (SelectKBest) — signe qu'elles concentrent l'essentiel du signal comportemental exploitable dans ce dataset.
- **Le F1-macro plafonné à ~0.40 n'est pas un échec du pipeline** mais le reflet honnête d'un déséquilibre de classes extrême et structurel (`LEFT CLUB` proche de 0.1% des clients) : aucune technique de rééquilibrage ne peut créer du signal prédictif qui n'existe pas dans les données disponibles pour cette classe.

## ⚠️ Limites & pistes d'amélioration

| Limite | Impact | Piste d'amélioration |
|---|---|---|
| ~~Échantillon de 50 000 clients sur 1,36M~~ → **résolu** : `FULL_SCALE = True` désormais actif | Les résultats ci-dessus reflètent l'entraînement sur l'intégralité des ~1,36M clients acheteurs pour les modèles qui passent à l'échelle | t-SNE, clustering hiérarchique, SVM/KNN et GridSearchCV restent volontairement bornés sur sous-échantillon (limite algorithmique structurelle, pas une contrainte de ressources ponctuelle — voir encadré section 17) |
| Ressources limitées (1 cœur CPU) | Recherche d'hyperparamètres restreinte | Optimisation élargie via **Optuna** ou **RandomizedSearchCV** |
| Fort déséquilibre des classes (`club_member_status`) | F1-macro limité malgré SMOTE et boosting | Techniques avancées de rééquilibrage (ADASYN, coûts asymétriques), collecte de plus d'exemples `LEFT CLUB` |

---

## ▶️ Comment exécuter le notebook

### Sur Google Colab (recommandé)
1. Charger les fichiers `customers.csv`, `articles.csv`, `transactions_train.csv` sur Google Drive.
2. Adapter la variable `BASE_PATH` dans la section 0 au chemin réel du dossier sur le Drive.
3. Exécuter les cellules dans l'ordre — le notebook montera automatiquement le Drive.

### En local
1. Placer les 3 fichiers CSV dans le même dossier que le notebook (`BASE_PATH = "./"` est utilisé automatiquement si `google.colab` n'est pas détecté).
2. Installer les dépendances (voir [Environnement & dépendances](#-environnement--dépendances)).
3. Lancer Jupyter : `jupyter notebook Eda_hm_customers.ipynb`.

---

## 📁 Fichiers générés

| Fichier | Description |
|---|---|
| `customers_cleaned.csv` | Dataset clients nettoyé (sans valeurs manquantes) |
| Table de features clients | Table RFM enrichie (16 colonnes) prête pour la modélisation |
| Résumés narratifs | Textes par client prêts pour l'embedding dans un pipeline RAG |

---

*Notebook réalisé dans le cadre d'une analyse EDA + Machine Learning sur le dataset public H&M Personalized Fashion Recommendations (Kaggle).*
