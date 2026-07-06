import { useEffect, useRef, useState } from "react";
import { api } from "../api.js";

// Shows whether the optional local AI (Ollama) is available, and a one-click
// button that installs it, downloads the model, and turns it on. Everything in
// the app works without it; it just makes resume parsing and CV writing smarter.
export default function AiStatus() {
  const [s, setS] = useState(null);
  const [setup, setSetup] = useState(null); // {state, message, steps}
  const poll = useRef(null);

  function refresh() {
    api.get("/api/ai/status").then(setS).catch(() => setS(null));
  }
  useEffect(() => {
    refresh();
    return () => poll.current && clearInterval(poll.current);
  }, []);

  async function startSetup() {
    try {
      const st = await api.post("/api/ai/ollama/setup", {});
      setSetup(st);
      if (!poll.current) {
        poll.current = setInterval(async () => {
          const cur = await api.get("/api/ai/ollama/setup/status");
          setSetup(cur);
          if (!cur.running && cur.state !== "running") {
            clearInterval(poll.current);
            poll.current = null;
            refresh(); // update the on/off badge
          }
        }, 1500);
      }
    } catch (e) {
      setSetup({ state: "error", message: e.message, steps: [] });
    }
  }

  if (!s) return null;

  const on = s.enabled && s.reachable && s.model_ready;
  const busy = setup && (setup.running || setup.state === "running");

  return (
    <div className={`ai-status ${on ? "on" : ""}`}>
      <span className={`status-dot ${on ? "ok" : busy ? "pending" : ""}`} />
      <div style={{ flex: 1 }}>
        <div className="ai-status-title">
          Local AI (Ollama): <span className="mono">{on ? "ready" : busy ? "setting up…" : "off"}</span>
        </div>
        <div className="ai-status-sub">
          {on
            ? "Resume parsing and CV writing use it. Free and fully on your device."
            : "Optional. It makes resume reading and CV wording smarter, and stays free and private on your computer."}
        </div>

        {!on && !busy && (
          <button className="btn-secondary ai-setup-btn" onClick={startSetup}>
            Set up local AI (one click)
          </button>
        )}
        {!on && !busy && (
          <div className="ai-setup-note">
            Installs Ollama and downloads the AI model (about 4 GB), then turns it on.
            You only do this once.
          </div>
        )}

        {setup && setup.steps && setup.steps.length > 0 && (
          <ul className="setup-steps">
            {setup.steps.map((st) => (
              <li key={st.key} className={`setup-step ${st.status}`}>
                <span className="setup-icon">
                  {st.status === "done"
                    ? "✓"
                    : st.status === "running"
                    ? "…"
                    : st.status === "error"
                    ? "✕"
                    : st.status === "manual"
                    ? "!"
                    : "○"}
                </span>
                <span className="setup-label">{st.label}</span>
                {st.detail && <span className="setup-detail mono">{st.detail}</span>}
              </li>
            ))}
          </ul>
        )}
        {setup && setup.message && (
          <div className={`setup-message ${setup.state}`}>{setup.message}</div>
        )}
      </div>
    </div>
  );
}
