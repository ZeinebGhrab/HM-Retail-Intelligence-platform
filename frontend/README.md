# `frontend/` — Interface web (dashboard + assistant IA)

Application React + Vite. Remplace un ancien frontend mobile Ionic/Capacitor (supprimé du dépôt
depuis) — repartie de zéro en web simple plutôt qu'en repackagant l'app mobile, cet ancien frontend
n'ayant servi que de référence pour le contrat de l'API chat (voir `src/services/chatApi.ts`).

---

## Ce que fait cette app

- **`DashboardView`** — les 5 dashboards Grafana existants (`grafana/dashboard-*.json`, désormais
  provisionnés via `grafana/provisioning/dashboards/`), affichés en iframe avec un sélecteur
  d'onglets. Dashboards agrégés (segments, ventes, produits) — aucun n'a de variable de filtrage par
  client (voir `grafana/provisioning/dashboards/json/*.json`, `spec.variables` vide).
- **`ChatPanel`** — panneau latéral (pas une page à part), ouvert/fermé via l'icône en haut à droite
  du header. Contient son propre champ `customer_id` : le panneau ne déduit pas automatiquement le
  client depuis le dashboard affiché (les dashboards Grafana embarqués n'exposent pas cette
  information au parent) — c'est un champ texte simple pour l'instant, à améliorer plus tard
  (recherche, sélection depuis une liste clients...).

Parle à [`backend/app/`](../backend/app/README.md) (`POST /chat/`).

## Lancement

```bash
npm install
cp .env.example .env.local   # ajuster VITE_API_URL / VITE_GRAFANA_URL si besoin
npm run dev
```

Nécessite `backend/app/` (le chatbot) et `grafana` (voir `docker-compose.yml`) démarrés pour être
pleinement fonctionnel — l'UI se charge sans eux, mais les requêtes chat et les iframes échoueront.

Les UID des dashboards dans `src/config.ts` (exports JSON format Grafana v2) ont été vérifiés en test
réel le 2026-08-29 — les 5 dashboards se chargent correctement. L'iframe utilise `?kiosk` (sans
valeur) pour masquer le chrome de navigation Grafana ; `&kiosk=tv`, utilisé initialement, ne le
masquait pas complètement et laissait la barre latérale Grafana cliquable dans l'iframe.
