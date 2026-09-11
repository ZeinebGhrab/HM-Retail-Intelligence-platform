// URL de base de l'API du chatbot (backend/app/, voir backend/app/main.py).
export const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8601";

// URL de base de Grafana (voir docker-compose.yml, service "grafana").
export const GRAFANA_BASE_URL = import.meta.env.VITE_GRAFANA_URL || "http://localhost:3001";

// UID de chaque dashboard (metadata.name dans les JSON exportés — voir
// grafana/provisioning/dashboards/json/*.json). Provisionnés au démarrage
// de Grafana via grafana/provisioning/dashboards/dashboards.yml.
//
// ⚠️ À vérifier une fois Grafana lancé : ces UID viennent des exports JSON
// (format v2, apiVersion dashboard.grafana.app/v2) et n'ont pas encore été
// validés contre une instance Grafana réellement démarrée avec ce
// provisioning. Si un dashboard ne s'affiche pas, ouvrir Grafana
// (http://localhost:3001) et corriger l'UID correspondant ici.
export const DASHBOARDS = [
  { uid: "advzvfm", title: "Customer Analytics" },
  { uid: "ad6pnn6", title: "Customer Segmentation" },
  { uid: "ad7wvpg", title: "Product Analytics" },
  { uid: "677407e", title: "Produits & Ventes journalières" },
  { uid: "adf4rtw", title: "Sales Overview" },
] as const;
