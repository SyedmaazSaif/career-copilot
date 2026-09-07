import { useRef, useState } from "react";
import { api } from "../api.js";

// Upload a resume (PDF/DOCX), preview what was read, then apply it to the profile.
export default function ResumeUpload({ onApplied }) {
  const fileRef = useRef(null);
  const [state, setState] = useState("idle"); // idle | parsing | preview | applying
  const [parsed, setParsed] = useState(null);
  const [usedAi, setUsedAi] = useState(false);
  const [aiNote, setAiNote] = useState(null); // why the AI pass fell short
  const [error, setError] = useState(null);

  function pick() {
    setError(null);
    fileRef.current?.click();
  }

  async function onFile(e) {
    const file = e.target.files?.[0];
    e.target.value = ""; // allow re-picking the same file
    if (!file) return;
    setState("parsing");
    setError(null);
    try {
      const res = await api.upload("/api/ai/resume/parse", file);
      setParsed(res.data);
      setUsedAi(res.used_ai);
      setAiNote(res.error || null);
      setState("preview");
    } catch (err) {
      setError(err.message);
      setState("idle");
    }
  }

  async function apply() {
    setState("applying");
    try {
      await api.post("/api/ai/resume/apply", { data: parsed, replace: true });
      setState("idle");
      setParsed(null);
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

  return (
    <>
      <input
        ref={fileRef}
        type="file"
        accept=".pdf,.docx,.txt"
        style={{ display: "none" }}
        onChange={onFile}
      />
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
                  ? "Read with local AI — experience and skills included below."
                  : "Read without AI, so only your contact details and summary were filled. Add the rest by hand, or fix the problem below and upload again."}
                {aiNote && (
                  <div className="ai-status-err">
                    Local model: {aiNote}
                  </div>
                )}
              </div>
            </div>

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
