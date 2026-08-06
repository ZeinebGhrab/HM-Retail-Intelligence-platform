# Grafana integration in the project

<p align="center">
  <a href="./README.md"><strong>🇬🇧 English</strong></a> ·
  <a href="./README.fr.md">🇫🇷 Français</a>
</p>

This document explains **what Grafana is**, **why it was added to the project**, **how it's
configured**, and **what changes were made** to the project (`docker-compose.yml` + provisioning
files) to integrate it.

---

## 1. What is Grafana used for here?

Grafana is the **visualization and dashboarding** tool. It connects to the project's
**PostgreSQL** database (`shop-postgres`) to display, as charts and tables (time series, stats,
tables...), the data already transformed and stored by the Kafka → Spark → PostgreSQL chain.

In short, in the project's pipeline:

```
Kafka (raw data) → Spark (processing) → PostgreSQL (storage) → Grafana (visualization)
```

Grafana performs **no computation**: it runs SQL queries against PostgreSQL and displays the
result as panels (charts, stat values, tables, etc.).

---

## 2. Changes made to the project

### 2.1 Adding the `grafana` service to `docker-compose.yml`

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

**Line-by-line explanation:**

| Element | Role |
|---|---|
| `image: grafana/grafana:latest` | Official Grafana image |
| `ports: "3001:3000"` | Grafana listens on port `3000` internally, exposed on `3001` locally (`http://localhost:3001`) |
| `GF_SECURITY_ADMIN_USER` / `GF_SECURITY_ADMIN_PASSWORD` | Admin credentials created automatically on first startup (`admin` / `hm_admin`) |
| `grafana_data:/var/lib/grafana` | Persistent volume: keeps dashboards, users, and preferences even after `docker compose down` |
| `./grafana/provisioning:/etc/grafana/provisioning` | Local folder mounted in the container: lets datasources and dashboards be **pre-configured** automatically on startup (without going through the UI) |
| `networks: shop_data_net` | Grafana is on the same Docker network as `postgres`, so it can reach it via `postgres:5432` |

### 2.2 Adding the `grafana_data` volume

```yaml
volumes:
  grafana_data:
```

Needed so the named volume referenced above is declared at the file's root level.

### 2.3 Adding the provisioning folder

A new local folder was created:

```
grafana/
└── provisioning/
    └── datasources/
        └── postgres.yml
```

This folder is mounted into the Grafana container. Everything it contains is read **automatically
on startup**: no need to configure the datasource by hand in the web UI anymore.

Contents of `postgres.yml`:

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

**Explanation:**

| Field | Role |
|---|---|
| `name` | Name shown in Grafana (`PostgreSQL-HM`) |
| `type: postgres` | Datasource type |
| `url: postgres:5432` | Address of the PostgreSQL container on the internal Docker network (service name, not `localhost`) |
| `database` (root) **and** `jsonData.database` | Name of the database to connect to (`hm_retail`). **Important**: since Grafana 12.2.0, only `jsonData.database` is actually used for the connection — the root field alone is no longer enough (known bug in this version) |
| `user` / `secureJsonData.password` | PostgreSQL connection credentials |
| `sslmode: disable` | No SSL required (connection stays inside the Docker network) |
| `isDefault: true` | This datasource is selected by default in panels |

---

## 3. Accessing Grafana

1. Start the services:
   ```bash
   docker compose up -d grafana
   ```
2. Open: [http://localhost:3001](http://localhost:3001)
3. Log in with:
   - **Username**: `admin`
   - **Password**: `hm_admin`
4. The `PostgreSQL-HM` datasource is already configured (visible under *Connections → Data
   sources*).

---

## 4. Creating a quick dashboard

1. **Dashboards → New → New dashboard → Add visualization**
2. Choose the `PostgreSQL-HM` datasource
3. Write a SQL query, for example:
   ```sql
   SELECT date, revenue
   FROM daily_sales
   WHERE $__timeFilter(date)
   ORDER BY date
   ```
4. Choose the panel type (Time series, Stat, Table...)
5. **Save** the panel, then the dashboard.

---

## 5. Quick troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| "No data" + "default database not configured" error | Missing `jsonData.database` (Grafana ≥ 12.2.0 bug) | Add `database` under `jsonData` (see §2.3) |
| Can't reach `postgres:5432` | Grafana not on the same Docker network | Check `networks: shop_data_net` on both services |
| Provisioned credentials don't apply | Stale cached `grafana_data` | `docker compose down`, then `docker volume rm <project>_grafana_data`, then `docker compose up -d` |
| Editing `postgres.yml` has no effect | A provisioned datasource can't be edited from the UI | Edit the YAML file directly, then restart the `grafana` container |

---

## 6. Summary of modified/added files

- `docker-compose.yml` → added the `grafana` service + `grafana_data` volume
- `grafana/provisioning/datasources/postgres.yml` → **new file**, automatic PostgreSQL connection