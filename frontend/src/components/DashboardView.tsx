import { useState } from "react";
import { DASHBOARDS, GRAFANA_BASE_URL } from "../config";
import "./DashboardView.css";

export default function DashboardView() {
  const [selectedUid, setSelectedUid] = useState<string>(DASHBOARDS[0].uid);
  const selected = DASHBOARDS.find((d) => d.uid === selectedUid) ?? DASHBOARDS[0];

  // &kiosk (sans valeur) masque TOUT le chrome Grafana (barre du haut,
  // recherche, "Sign in", barre latérale) — &kiosk=tv (utilisé avant)
  // masque moins et laissait la nav Grafana cliquable dans l'iframe,
  // constaté en test réel le 2026-08-29 (navigation vers Alerting depuis
  // l'iframe). theme=light pour matcher le reste de l'app. Voir
  // docker-compose.yml (GF_SECURITY_ALLOW_EMBEDDING, GF_AUTH_ANONYMOUS_ENABLED)
  // pour que l'iframe se charge sans login.
  const src = `${GRAFANA_BASE_URL}/d/${selected.uid}?orgId=1&kiosk&theme=light`;

  return (
    <div className="dashboard-view">
      <div className="dashboard-toolbar">
        {DASHBOARDS.map((d) => (
          <button
            key={d.uid}
            className={`dashboard-tab ${d.uid === selectedUid ? "active" : ""}`}
            onClick={() => setSelectedUid(d.uid)}
          >
            {d.title}
          </button>
        ))}
      </div>
      <iframe
        key={selectedUid}
        className="dashboard-iframe"
        src={src}
        title={selected.title}
      />
    </div>
  );
}
