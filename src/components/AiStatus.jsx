import { useEffect, useRef, useState } from "react";
import { api } from "../api.js";

// Shows whether the optional local AI (Ollama) is available, and a one-click
// button that installs it, downloads the model, and turns it on. Everything in
// the app works without it; it just makes resume parsing and CV writing smarter.
export default function AiStatus() {
  const [s, setS] = useState(null);
  const [setup, setSetup] = useState(null); // {state, message, steps}
  const [hw, setHw] = useState(null); // {specs, recommended, options, reason, warning}
  const [hwErr, setHwErr] = useState(null);
  const [picked, setPicked] = useState(null); // model name the user chose
  const poll = useRef(null);

  function refresh() {
    api.get("/api/ai/status").then(setS).catch(() => setS(null));
  }
  useEffect(() => {
    refresh();
    return () => poll.current && clearInterval(poll.current);
  }, []);

  // Read the machine's specs before offering to install anything, so the user
  // sees which model fits and why before committing to the download.
  async function checkHardware() {
    setHwErr(null);
    try {
      const r = await api.get("/api/ai/hardware");
      setHw(r);
      setPicked(r.recommended.name);
    } catch (e) {
      setHwErr(e.message);
    }
  }

  async function startSetup() {
    try {
      const st = await api.post("/api/ai/ollama/setup", { model: picked });
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

        {!on && !busy && !hw && (
          <>
            <button className="btn-secondary ai-setup-btn" onClick={checkHardware}>
              Set up local AI
            </button>
            <div className="ai-setup-note">
              We'll check your computer first and tell you which model it can run,
              before downloading anything. You only do this once.
            </div>
            {hwErr && <div className="ai-status-err">Could not read your specs: {hwErr}</div>}
          </>
        )}

        {!on && !busy && hw && (
          <div className="hw-check">
            <div className="hw-title">What your computer can run</div>
            <ul className="hw-specs">
              <li><span>Memory</span><span className="mono">
                {hw.specs.ram_total_gb ? `${hw.specs.ram_total_gb} GB` : "unknown"}
                {hw.specs.ram_free_gb != null && ` (${hw.specs.ram_free_gb} GB free)`}
              </span></li>
              {hw.specs.cpu_cores && (
                <li><span>CPU</span><span className="mono">{hw.specs.cpu_cores} cores</span></li>
              )}
              {hw.specs.gpu && (
                <li><span>Graphics</span><span className="mono">
                  {hw.specs.gpu}{hw.specs.vram_gb ? ` · ${hw.specs.vram_gb} GB` : ""}
                  {hw.specs.gpu_accelerated ? "" : " · not usable by Ollama"}
                </span></li>
              )}
            </ul>

            <div className="hw-reason">{hw.reason}</div>

            <div className="hw-options">
              {hw.options.map((m) => (
                <label
                  key={m.name}
                  className={`hw-option ${picked === m.name ? "picked" : ""} ${m.fits ? "" : "unfit"}`}
                >
                  <input
                    type="radio"
                    name="ollama-model"
                    value={m.name}
                    checked={picked === m.name}
                    onChange={() => setPicked(m.name)}
                  />
                  <span className="hw-option-body">
                    <span className="hw-option-head">
                      {m.label}
                      <span className="mono hw-option-size">{m.size_gb} GB download</span>
                      {m.name === hw.recommended.name && (
                        <span className="hw-badge">recommended</span>
                      )}
                      {!m.fits && <span className="hw-badge warn">too big for this PC</span>}
                    </span>
                    <span className="hw-option-note">{m.note}</span>
                  </span>
                </label>
              ))}
            </div>

            {hw.warning && <div className="hw-warning">{hw.warning}</div>}

            {picked && !hw.options.find((m) => m.name === picked)?.fits && (
              <div className="hw-warning strong">
                You've picked a model this computer can't run well. It will install,
                but expect requests to time out and the app to fall back to its
                basic reader.
              </div>
            )}

            <div className="hw-actions">
              <button onClick={startSetup}>
                Install {hw.options.find((m) => m.name === picked)?.label || "model"}
              </button>
              <button className="btn-secondary" onClick={() => setHw(null)}>
                Cancel
              </button>
            </div>
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
