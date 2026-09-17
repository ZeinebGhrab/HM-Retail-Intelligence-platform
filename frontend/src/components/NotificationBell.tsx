import { useEffect, useRef, useState } from "react";
import {
  fetchNotifications,
  markAllNotificationsRead,
  markNotificationRead,
  subscribeToNotifications,
  type NotificationItem,
} from "../services/notificationsApi";
import "./NotificationBell.css";

function formatDate(iso?: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("fr-FR", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function NotificationBell() {
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [open, setOpen] = useState(false);
  const wrapperRef = useRef<HTMLDivElement>(null);

  // Chargement initial + abonnement au flux temps réel
  useEffect(() => {
    fetchNotifications()
      .then(setNotifications)
      .catch(() => {
        /* silencieux : la cloche reste vide si le backend est injoignable */
      });

    const unsubscribe = subscribeToNotifications((n) => {
      setNotifications((prev) => [n, ...prev].slice(0, 50));
    });
    return unsubscribe;
  }, []);

  // Fermeture du dropdown au clic extérieur
  useEffect(() => {
    const onClickOutside = (e: MouseEvent) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, []);

  const unreadCount = notifications.filter((n) => !n.read).length;

  const handleItemClick = (n: NotificationItem) => {
    if (n.read) return;
    setNotifications((prev) => prev.map((x) => (x.id === n.id ? { ...x, read: true } : x)));
    markNotificationRead(n.id).catch(() => {});
  };

  const handleMarkAllRead = () => {
    setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
    markAllNotificationsRead().catch(() => {});
  };

  return (
    <div className="notif-bell-wrapper" ref={wrapperRef}>
      <button
        className="notif-bell-btn"
        onClick={() => setOpen((v) => !v)}
        aria-label="Notifications"
        title="Notifications"
      >
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
          <path
            d="M12 3a5 5 0 0 0-5 5v3.09c0 .5-.19.98-.53 1.35L5 14.5c-.83.9-.2 2.5 1.1 2.5h11.8c1.3 0 1.93-1.6 1.1-2.5l-1.47-2.06a2.1 2.1 0 0 1-.53-1.35V8a5 5 0 0 0-5-5Z"
            stroke="currentColor"
            strokeWidth="1.7"
            strokeLinejoin="round"
          />
          <path d="M9.5 19a2.5 2.5 0 0 0 5 0" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
        </svg>
        {unreadCount > 0 && <span className="notif-badge">{unreadCount > 9 ? "9+" : unreadCount}</span>}
      </button>

      {open && (
        <div className="notif-dropdown">
          <div className="notif-dropdown-header">
            <div className="notif-dropdown-title">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
                <path
                  d="M12 3a5 5 0 0 0-5 5v3.09c0 .5-.19.98-.53 1.35L5 14.5c-.83.9-.2 2.5 1.1 2.5h11.8c1.3 0 1.93-1.6 1.1-2.5l-1.47-2.06a2.1 2.1 0 0 1-.53-1.35V8a5 5 0 0 0-5-5Z"
                  stroke="currentColor"
                  strokeWidth="1.7"
                  strokeLinejoin="round"
                />
              </svg>
              <span>Notifications</span>
              {notifications.length > 0 && <span className="notif-count-pill">{notifications.length}</span>}
            </div>

            {unreadCount > 0 && (
              <button className="notif-mark-all" onClick={handleMarkAllRead}>
                Tout marquer comme lu
              </button>
            )}

            <button className="notif-close-btn" onClick={() => setOpen(false)} aria-label="Fermer">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
                <path d="M6 6l12 12M18 6L6 18" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
              </svg>
            </button>
          </div>

          <div className="notif-list">
            {notifications.length === 0 && (
              <div className="notif-empty">Aucune notification pour le moment.</div>
            )}
            {notifications.map((n) => (
              <div
                key={n.id}
                className={`notif-item ${n.read ? "read" : "unread"}`}
                onClick={() => handleItemClick(n)}
              >
                <p className="notif-message">{n.message}</p>
                <div className="notif-meta">
                  <span className="notif-date">{formatDate(n.created_at)}</span>
                  {n.prediction?.dominant_segment && (
                    <span className="notif-tag">{n.prediction.dominant_segment}</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
