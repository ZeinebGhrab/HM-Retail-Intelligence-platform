import { API_BASE_URL } from "../config";

export interface ChatHistoryItem {
  role: "user" | "assistant";
  content: string;
}

export interface ChatResponse {
  answer: string;
  model?: string;
  tool_used?: string;
  error?: string;
}

// Même contrat que old-frontend/src/services/api.ts + chatBridge.ts,
// étendu d'un champ customer_id (voir backend/app/schemas.py).
export async function askChatbot(
  question: string,
  customerId: string | null,
  history: ChatHistoryItem[],
): Promise<ChatResponse> {
  const res = await fetch(`${API_BASE_URL}/chat/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, customer_id: customerId, history }),
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error((body as { error?: string }).error ?? `Erreur ${res.status}`);
  }

  return res.json() as Promise<ChatResponse>;
}
