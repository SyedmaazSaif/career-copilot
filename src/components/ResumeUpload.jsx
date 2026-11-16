import { useEffect, useRef, useState } from "react";
import { api } from "../api.js";

const PROVIDER_LABEL = {
  ollama: "local AI (Ollama)",
  deepseek: "DeepSeek",
  custom: "your API",
};

// A short, helpful nudge when the chosen model couldn't read the resume.
function hintFor(error, provider) {
  if (!error) return "";
  const e = error.toLowerCase();
  if (provider === "ollama") {
    if (e.includes("switched off"))
      return "Your local AI is switched off. Turn it on in Settings → AI model, or pick a paid model above.";
    if (e.includes("not reachable"))
      return "Ollama isn't running. Start it in Settings → AI model, or pick a paid model above.";
    if (e.includes("not installed"))
      return "The local model isn't downloaded yet. Set it up in Settings → AI model, or pick a paid model above.";
  } else {
    if (e.includes("no api key"))
      return "No API key is set. Add it in Settings → AI model, or pick the local model above.";
  }
  return "It couldn't read with that model. Pick another model above, or check Settings → AI model.";
}

// Upload a resume (PDF/DOCX), preview what was read, then apply it to the profile.
// The user picks which AI model reads it; if that model isn't ready, the app says
// so clearly instead of silently falling back.
export default function ResumeUpload({ onApplied }) {
  const fileRef = useRef(null);
  const [state, setState] = useState("idle"); // idle | parsing | preview | applying
  const [file, setFile] = useState(null);
  const [provider, setProvider] = useState("ollama");
  const [parsed, setParsed] = useState(null);
  const [usedAi, setUsedAi] = useState(false);
  const [aiNote, setAiNote] = useState(null); // why the AI pass fell short
  const [error, setError] = useState(null);

  // Default to whatever model is set in Settings, so nothing changes unless the
  // user chooses something different here.
  useEffect(() => {
    api.get("/api/ai/config")
      .then((c) => { if (c && c.provider) setProvider(c.provider); })
      .catch(() => {});
  }, []);

  function pick() {
    setError(null);
    fileRef.current?.click();
  }

  async function parse(theFile, prov) {
    setState("parsing");
    setError(null);
    try {
      const res = await api.upload("/api/ai/resume/parse", theFile, { provider: prov });
      setParsed(res.data);
      setUsedAi(res.used_ai);
      setAiNote(res.error || null);
      setState("preview");
    } catch (err) {
      setError(err.message);
      setState("idle");
    }
  }

  async function onFile(e) {
    const f = e.target.files?.[0];
    e.target.value = ""; // allow re-picking the same file
    if (!f) return;
    setFile(f);
    await parse(f, provider);
  }

  async function reparse() {
    if (file) await parse(file, provider);
  }

  async function apply() {
    setState("applying");
    try {
      await api.post("/api/ai/resume/apply", { data: parsed, replace: true });
      setState("idle");
      setParsed(null);
      setFile(null);
      onApplied?.();
    } catch (err) {
      setError(err.message);
      setState("preview");
    }
  }

  const p = parsed?.profile || {};
  const counts = parsed
    ? {
        experiences: (parsed.experiences || []).length,
        skills: (parsed.skills || []).length,
        education: (parsed.education || []).length,
      }
    : null;

  const providerPicker = (
    <label className="field" style={{ maxWidth: 420 }}>
      <span className="field-label">Read with</span>
      <select value={provider} onChange={(e) => setProvider(e.target.value)}>
        <option value="ollama">Ollama — local, free</option>
        <option value="deepseek">DeepSeek — paid (your key)</option>
        <option value="custom">Custom API — paid (your key)</option>
      </select>
    </label>
  );

  return (
    <>
      <input
        ref={fileRef}
        type="file"
        accept=".pdf,.docx,.txt"
        style={{ display: "none" }}
        onChange={onFile}
      />

      <div className="cv-form" style={{ marginBottom: 10 }}>
        {providerPicker}
      </div>

      <button className="btn-secondary" onClick={pick} disabled={state === "parsing"}>
        {state === "parsing" ? "Reading…" : "Upload resume"}
      </button>

      {error && (
        <div className="modal-overlay" onClick={() => setError(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 460 }}>
            <div className="banner error">{error}</div>
            <div className="form-actions">
              <button className="btn-secondary" onClick={() => setError(null)}>Close</button>
            </div>
          </div>
        </div>
      )}

      {state !== "idle" && state !== "parsing" && parsed && (
        <div className="modal-overlay" onClick={() => setState("idle")}>
          <div className="modal" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 560 }}>
            <header className="modal-head">
              <h2>Review what we read</h2>
              <button className="icon-btn" onClick={() => setState("idle")}>✕</button>
            </header>

            <div className={`ai-status ${usedAi ? "on" : ""}`} style={{ marginBottom: 14 }}>
              <span className={`status-dot ${usedAi ? "ok" : "pending"}`} />
              <div className="ai-status-sub">
                {usedAi
                  ? `Read with ${PROVIDER_LABEL[provider] || provider} — experience and skills included below.`
                  : `Couldn't read with ${PROVIDER_LABEL[provider] || provider}, so only your contact details and summary were filled.`}
                {aiNote && (
                  <div className="ai-status-err">{aiNote}</div>
                )}
                {!usedAi && (
                  <div className="ai-status-err">{hintFor(aiNote, provider)}</div>
                )}
              </div>
            </div>

            {!usedAi && (
              <div className="cv-form" style={{ marginBottom: 10 }}>
                {providerPicker}
                <div className="form-actions" style={{ marginTop: 6 }}>
                  <button className="btn-secondary btn-sm" onClick={reparse} disabled={state === "parsing"}>
                    {state === "parsing" ? "Reading…" : "Read again"}
                  </button>
                </div>
              </div>
            )}

            <dl className="kv">
              <dt>Name</dt><dd>{p.name || "—"}</dd>
              <dt>Email</dt><dd>{p.email || "—"}</dd>
              <dt>Phone</dt><dd>{p.phone || "—"}</dd>
              <dt>LinkedIn</dt><dd>{p.linkedin || "—"}</dd>
            </dl>
            <div className="cv-counts">
              <span>{counts.experiences} experiences</span>
              <span>{counts.skills} skills</span>
              <span>{counts.education} education</span>
            </div>

            <p className="empty-hint">
              Applying replaces your current profile records with what was read. You can
              edit anything afterwards.
            </p>

            <div className="modal-actions">
              <button onClick={apply} disabled={state === "applying"}>
                {state === "applying" ? "Applying…" : "Apply to profile"}
              </button>
              <button className="btn-secondary" onClick={() => setState("idle")}>Cancel</button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
