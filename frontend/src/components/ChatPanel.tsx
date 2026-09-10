import { useEffect, useRef, useState } from "react";
import { askChatbot, type ChatHistoryItem } from "../services/chatApi";
import "./ChatPanel.css";

interface Message {
  id: number;
  text: string;
  sender: "bot" | "user";
  time: string;
  loading?: boolean;
  model?: string;
  toolUsed?: string;
}

interface ChatPanelProps {
  customerId: string;
  onCustomerIdChange: (id: string) => void;
}

const now = () => {
  const d = new Date();
  return `${d.getHours()}h${String(d.getMinutes()).padStart(2, "0")}`;
};

const WELCOME: Message = {
  id: 0,
  sender: "bot",
  time: "",
  text:
    "Bonjour ! Je suis l'assistant analytique H&M Retail Intelligence.\n\n" +
    "Renseignez un identifiant client ci-dessus pour des questions précises " +
    "(profil, prédiction de dépense, comparaison à son segment...), ou posez " +
    "une question générale sans identifiant.",
};

export default function ChatPanel({ customerId, onCustomerIdChange }: ChatPanelProps) {
  const [messages, setMessages] = useState<Message[]>([WELCOME]);
  const [inputText, setInputText] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const bodyRef = useRef<HTMLDivElement>(null);
  const msgsRef = useRef<Message[]>([WELCOME]);

  useEffect(() => {
    msgsRef.current = messages;
  }, [messages]);

  useEffect(() => {
    bodyRef.current?.scrollTo({ top: bodyRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  const send = async (text: string) => {
    const question = text.trim();
    if (!question || isLoading) return;

    const uid = Date.now();
    setMessages((prev) => [
      ...prev,
      { id: uid, text: question, sender: "user", time: now() },
      { id: uid + 1, text: "…", sender: "bot", time: now(), loading: true },
    ]);
    setInputText("");
    setIsLoading(true);

    const history: ChatHistoryItem[] = msgsRef.current
      .filter((m) => m.id !== 0 && !m.loading)
      .slice(-6)
      .map((m) => ({ role: m.sender === "user" ? "user" : "assistant", content: m.text }));

    try {
      const { answer, model, tool_used, error } = await askChatbot(
        question,
        customerId.trim() || null,
        history,
      );
      setMessages((prev) =>
        prev.map((m) =>
          m.loading
            ? { ...m, text: error ? `⚠️ ${error}` : answer, loading: false, time: now(), model, toolUsed: tool_used }
            : m,
        ),
      );
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Erreur inconnue";
      setMessages((prev) => prev.map((m) => (m.loading ? { ...m, text: `⚠️ ${msg}`, loading: false } : m)));
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <aside className="chat-panel">
      <div className="chat-panel-header">
        <div className="chat-panel-title">Assistant IA</div>
        <input
          className="chat-customer-input"
          placeholder="customer_id (optionnel)"
          value={customerId}
          onChange={(e) => onCustomerIdChange(e.target.value)}
          spellCheck={false}
        />
      </div>

      <div className="chat-panel-body" ref={bodyRef}>
        {messages.map((m) => (
          <div key={m.id} className={`chat-msg-row ${m.sender}`}>
            <div className={`chat-bubble ${m.sender} ${m.loading ? "loading" : ""}`}>
              <p>{m.text}</p>
              {!m.loading && m.time && (
                <div className="chat-bubble-footer">
                  <span>{m.time}</span>
                  {m.model && <span className="chat-bubble-model">{m.model.split(":")[0]}</span>}
                  {m.toolUsed && <span className="chat-bubble-tool">{m.toolUsed}</span>}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      <div className="chat-panel-footer">
        <input
          className="chat-input"
          placeholder="Posez votre question…"
          value={inputText}
          onChange={(e) => setInputText(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send(inputText)}
          disabled={isLoading}
        />
        <button className="chat-send-btn" onClick={() => send(inputText)} disabled={isLoading}>
          Envoyer
        </button>
      </div>
    </aside>
  );
}
