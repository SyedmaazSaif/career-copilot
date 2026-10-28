import { useEffect, useState } from "react";
import { api } from "../api.js";

const preStyle = {
  whiteSpace: "pre-wrap",
  fontFamily: "inherit",
  fontSize: "13px",
  lineHeight: 1.5,
  background: "#f4f6f9",
  border: "1px solid rgba(102,114,132,0.3)",
  borderRadius: 8,
  padding: 10,
  margin: "8px 0 0",
};

export default function FollowUps() {
  const [items, setItems] = useState(null);
  const [copied, setCopied] = useState(null);

  useEffect(() => {
    api
      .get("/api/jobs/follow-ups")
      .then(setItems)
      .catch(() => setItems([]));
  }, []);

  async function copy(txt, id) {
    try {
      await navigator.clipboard.writeText(txt);
      setCopied(id);
      setTimeout(() => setCopied(null), 1500);
    } catch {
      /* clipboard unavailable — text is still selectable */
    }
  }

  if (!items || items.length === 0) return null;

  return (
    <div className="panel">
      <h2>Follow-ups due</h2>
      <p className="empty-hint" style={{ marginTop: 0 }}>
        These applications have had no reply yet. A short nudge often helps.
      </p>
      {items.map((it) => (
        <div key={it.job_id} style={{ marginBottom: 14 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
            <strong>{it.title}</strong>
            <span className="muted">
              at {it.company} · {it.days_since} day{it.days_since === 1 ? "" : "s"} ago
            </span>
            <button
              className="btn-secondary btn-sm"
              onClick={() => copy(it.message, it.job_id)}
            >
              {copied === it.job_id ? "Copied" : "Copy message"}
            </button>
          </div>
          <pre style={preStyle}>{it.message}</pre>
        </div>
      ))}
    </div>
  );
}
