import { useCallback, useRef, useState } from "react";
import DashboardView from "./components/DashboardView";
import ChatPanel from "./components/ChatPanel";
import "./App.css";

const DEFAULT_CHAT_WIDTH = 440;
const MIN_CHAT_WIDTH = 320;

export default function App() {
  const [chatOpen, setChatOpen] = useState(false);
  const [customerId, setCustomerId] = useState("");
  const [chatWidth, setChatWidth] = useState(DEFAULT_CHAT_WIDTH);
  const dragRef = useRef<{ startX: number; startWidth: number } | null>(null);

  const onDragStart = useCallback(
    (e: React.MouseEvent) => {
      dragRef.current = { startX: e.clientX, startWidth: chatWidth };

      const onMove = (moveEvent: MouseEvent) => {
        if (!dragRef.current) return;
        // Le panneau est à droite : glisser vers la gauche l'agrandit.
        const delta = dragRef.current.startX - moveEvent.clientX;
        const maxWidth = window.innerWidth * 0.85;
        const next = Math.min(maxWidth, Math.max(MIN_CHAT_WIDTH, dragRef.current.startWidth + delta));
        setChatWidth(next);
      };

      const onUp = () => {
        dragRef.current = null;
        window.removeEventListener("mousemove", onMove);
        window.removeEventListener("mouseup", onUp);
      };

      window.addEventListener("mousemove", onMove);
      window.addEventListener("mouseup", onUp);
    },
    [chatWidth],
  );

  return (
    <div className="app-shell">
      <header className="app-header">
        <span className="app-title">H&amp;M Retail Intelligence</span>
        <button
          className={`chat-toggle-btn ${chatOpen ? "active" : ""}`}
          onClick={() => setChatOpen((v) => !v)}
          aria-label="Ouvrir l'assistant IA"
          title="Assistant IA"
        >
          <svg width="26" height="26" viewBox="0 0 24 24" fill="none">
            <path
              d="M4 5h16v11H8l-4 4V5z"
              stroke="currentColor"
              strokeWidth="1.8"
              strokeLinejoin="round"
            />
          </svg>
        </button>
      </header>

      <div className="app-body">
        <main className="app-main">
          <DashboardView />
        </main>

        {chatOpen && (
          <div className="app-chat-panel" style={{ width: chatWidth }}>
            <div
              className="app-chat-resize-handle"
              onMouseDown={onDragStart}
              role="separator"
              aria-orientation="vertical"
              aria-label="Redimensionner le panneau de discussion"
              title="Glisser pour redimensionner"
            />
            <ChatPanel customerId={customerId} onCustomerIdChange={setCustomerId} />
          </div>
        )}
      </div>
    </div>
  );
}
