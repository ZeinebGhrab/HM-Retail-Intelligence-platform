# Intégration de Grafana dans le projet

<p align="center">
  <a href="./README.md">🇬🇧 English</a> ·
  <a href="./README.fr.md"><strong>🇫🇷 Français</strong></a>
</p>

Ce document explique **ce qu'est Grafana**, **pourquoi il a été ajouté au projet**, **comment il est configuré**, et **quels changements ont été apportés** au projet (`docker-compose.yml` + fichiers de provisioning) pour l'intégrer.

---

## 1. À quoi sert Grafana ici ?

Grafana est l'outil de **visualisation et de dashboarding**. Il se connecte à la base **PostgreSQL** (`shop-postgres`) du projet pour afficher, sous forme de graphiques et de tableaux (courbes, stats, tables...), les données déjà transformées et stockées par la chaîne Kafka → Spark → PostgreSQL.

En résumé, dans le pipeline du projet :

```
Kafka (données brutes) → Spark (traitement) → PostgreSQL (stockage) → Grafana (visualisation)
```

Grafana ne fait **aucun calcul** : il exécute des requêtes SQL sur PostgreSQL et affiche le résultat sous forme de panels (graphiques, valeurs stat, tables, etc.).

---

## 2. Changements apportés au projet

### 2.1 Ajout du service `grafana` dans `docker-compose.yml`

```yaml
grafana:
  image: grafana/grafana:latest
  container_name: shop-grafana
  restart: unless-stopped
  ports:
    - "3001:3000"
  environment:
    - GF_SECURITY_ADMIN_USER=admin
    - GF_SECURITY_ADMIN_PASSWORD=hm_admin
  volumes:
    - grafana_data:/var/lib/grafana
    - ./grafana/provisioning:/etc/grafana/provisioning
  networks:
    - shop_data_net
```

**Explication ligne par ligne :**

| Élément | Rôle |
|---|---|
| `image: grafana/grafana:latest` | Image officielle Grafana |
| `ports: "3001:3000"` | Grafana écoute sur le port `3000` en interne, exposé sur `3001` en local (`http://localhost:3001`) |
| `GF_SECURITY_ADMIN_USER` / `GF_SECURITY_ADMIN_PASSWORD` | Identifiants admin créés automatiquement au premier démarrage (`admin` / `hm_admin`) |
| `grafana_data:/var/lib/grafana` | Volume persistant : conserve les dashboards, utilisateurs, préférences même après `docker compose down` |
| `./grafana/provisioning:/etc/grafana/provisioning` | Dossier local monté dans le conteneur : permet de **pré-configurer** les datasources et dashboards automatiquement au démarrage (sans passer par l'UI) |
| `networks: shop_data_net` | Grafana est sur le même réseau Docker que `postgres`, donc peut le joindre via `postgres:5432` |

### 2.2 Ajout du volume `grafana_data`

```yaml
volumes:
  grafana_data:
```

Nécessaire pour que le volume nommé référencé plus haut soit déclaré au niveau racine du fichier.

### 2.3 Ajout du dossier de provisioning

Un nouveau dossier local a été créé :

```
grafana/
└── provisioning/
    └── datasources/
        └── postgres.yml
```

Ce dossier est monté dans le conteneur Grafana. Tout ce qu'il contient est lu **automatiquement au démarrage** : plus besoin de configurer la datasource à la main dans l'interface web.

Contenu de `postgres.yml` :

```yaml
apiVersion: 1
datasources:
  - name: PostgreSQL-HM
    type: postgres
    access: proxy
    url: postgres:5432
    database: hm_retail
    isDefault: true
    user: hm_admin
    secureJsonData:
      password: postgres
    jsonData:
      database: hm_retail
      sslmode: disable
      postgresVersion: 1500
```

**Explication :**

| Champ | Rôle |
|---|---|
| `name` | Nom affiché dans Grafana (`PostgreSQL-HM`) |
| `type: postgres` | Type de datasource |
| `url: postgres:5432` | Adresse du conteneur PostgreSQL sur le réseau Docker interne (nom du service, pas `localhost`) |
| `database` (racine) **et** `jsonData.database` | Nom de la base à laquelle se connecter (`hm_retail`). **Important** : depuis Grafana 12.2.0, seul `jsonData.database` est réellement pris en compte pour la connexion — le champ racine seul ne suffit plus (bug connu de cette version) |
| `user` / `secureJsonData.password` | Identifiants de connexion PostgreSQL |
| `sslmode: disable` | Pas de SSL requis (connexion interne au réseau Docker) |
| `isDefault: true` | Cette datasource est sélectionnée par défaut dans les panels |

---

## 3. Accéder à Grafana

1. Démarrer les services :
   ```bash
   docker compose up -d grafana
   ```
2. Ouvrir : [http://localhost:3001](http://localhost:3001)
3. Se connecter avec :
   - **Utilisateur** : `admin`
   - **Mot de passe** : `hm_admin`
4. La datasource `PostgreSQL-HM` est déjà configurée (visible dans *Connections → Data sources*).

---

## 4. Créer un dashboard rapide

1. **Dashboards → New → New dashboard → Add visualization**
2. Choisir la datasource `PostgreSQL-HM`
3. Écrire une requête SQL, par exemple :
   ```sql
   SELECT date, chiffre_affaires
   FROM daily_sales
   WHERE $__timeFilter(date)
   ORDER BY date
   ```
4. Choisir le type de panel (Time series, Stat, Table...)
5. **Save** le panel puis le dashboard.

---

## 5. Dépannage rapide

| Symptôme | Cause probable | Solution |
|---|---|---|
| "No data" + erreur "default database not configured" | `jsonData.database` manquant (bug Grafana ≥ 12.2.0) | Ajouter `database` dans `jsonData` (voir §2.3) |
| Impossible de joindre `postgres:5432` | Grafana pas sur le même réseau Docker | Vérifier `networks: shop_data_net` sur les deux services |
| Les identifiants provisionnés ne s'appliquent pas | Ancien `grafana_data` en cache | `docker compose down` puis `docker volume rm <projet>_grafana_data` puis `docker compose up -d` |
| Modification du fichier `postgres.yml` sans effet | La datasource provisionnée ne peut pas être éditée depuis l'UI | Modifier le fichier YAML directement, puis redémarrer le conteneur `grafana` |

---

## 6. Résumé des fichiers modifiés/ajoutés

- `docker-compose.yml` → ajout du service `grafana` + volume `grafana_data`
- `grafana/provisioning/datasources/postgres.yml` → **nouveau fichier**, connexion automatique à PostgreSQL