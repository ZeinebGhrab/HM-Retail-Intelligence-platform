export interface NotificationPrediction {
    n_customers_scored?: number;
    dominant_club_status?: string;
    dominant_segment?: string;
    predicted_spend_total?: number;
    predicted_spend_mean?: number;
}

export interface NotificationItem {
    id: string;
    type: string;
    message: string;
    date?: string | null;
    generated_at?: string | null;
    created_at: string;
    read: boolean;
    prediction?: NotificationPrediction | null;
}

// Ajustez si votre backend est exposé sur une autre URL/port.
// Si vous avez déjà une variable pour l'URL du backend ailleurs dans le
// projet (ex. dans services/chatApi.ts ou config.ts), réutilisez-la plutôt
// que de dupliquer cette constante.
const API_BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export async function fetchNotifications(): Promise<NotificationItem[]> {
    const res = await fetch(`${API_BASE}/api/notifications`);
    if (!res.ok) throw new Error("Impossible de charger les notifications");
    return res.json();
}

export async function markNotificationRead(id: string): Promise<void> {
    await fetch(`${API_BASE}/api/notifications/${id}/read`, { method: "PATCH" });
}

export async function markAllNotificationsRead(): Promise<void> {
    await fetch(`${API_BASE}/api/notifications/read-all`, { method: "PATCH" });
}

/**
 * Ouvre une connexion SSE persistante vers le backend et appelle `onMessage`
 * pour chaque nouvelle notification poussée par le job n8n nocturne.
 * Retourne une fonction de nettoyage à appeler dans le useEffect cleanup.
 */
export function subscribeToNotifications(
    onMessage: (n: NotificationItem) => void,
    onError?: (e: Event) => void,
): () => void {
    const es = new EventSource(`${API_BASE}/api/notifications/stream`);

    es.addEventListener("notification", (event) => {
        try {
            const data = JSON.parse((event as MessageEvent).data) as NotificationItem;
            onMessage(data);
        } catch {
            // payload malformé : on ignore plutôt que de casser le flux
        }
    });

    if (onError) es.onerror = onError;

    return () => es.close();
}
