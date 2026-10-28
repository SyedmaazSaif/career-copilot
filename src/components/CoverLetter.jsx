import { useState } from "react";
import { api } from "../api.js";

const preStyle = {
  whiteSpace: "pre-wrap",
  fontFamily: "inherit",
  fontSize: "13px",
  lineHeight: 1.5,
  background: "#f4f6f9",
  border: "1px solid rgba(102,114,132,0.3)",
  borderRadius: 8,
  padding: 12,
  margin: 0,
};

const qStyle = { fontWeight: 600, fontSize: 13, marginBottom: 2 };
const aStyle = { color: "#3d4856", fontSize: 13, marginBottom: 10 };

export default function CoverLetterSection({ job }) {
  const [letter, setLetter] = useState(null);
  const [screener, setScreener] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [copied, setCopied] = useState(null);

  async function generateLetter() {
    setBusy(true);
    setError(null);
    try {
      setLetter(await api.post(`/api/jobs/${job.id}/cover-letter`, {}));
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function loadScreener() {
    setBusy(true);
    setError(null);
    try {
      setScreener(await api.get(`/api/jobs/${job.id}/screener`));
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function copy(txt, key) {
    try {
      await navigator.clipboard.writeText(txt);
      setCopied(key);
      setTimeout(() => setCopied(null), 1500);
    } catch {
      /* clipboard unavailable — the text is still visible to select */
    }
  }

  function reveal(p) {
    if (window.copilot?.showItem) window.copilot.showItem(p);
    else window.alert("Saved here:\n" + p);
  }

  return (
    <section className="detail-section">
      <h3>Cover letter</h3>
      <p className="empty-hint" style={{ marginTop: 0 }}>
        Written from your profile facts only, tailored to this job. Nothing is invented.
      </p>
      <div className="form-actions">
        <button onClick={generateLetter} disabled={busy}>
          {busy ? "Working…" : "Generate cover letter"}
        </button>
      </div>
      {letter && (
        <div style={{ marginTop: 12 }}>
          <pre style={preStyle}>{letter.text}</pre>
          <div className="form-actions" style={{ marginTop: 8 }}>
            <button
              className="btn-secondary btn-sm"
              onClick={() => copy(letter.text, "letter")}
            >
              {copied === "letter" ? "Copied" : "Copy text"}
            </button>
            {letter.file_path && (
              <button
                className="btn-secondary btn-sm"
                onClick={() => reveal(letter.file_path)}
                title={letter.file_path}
              >
                Reveal in folder
              </button>
            )}
          </div>
        </div>
      )}

      <h3 style={{ marginTop: 20 }}>Screener answers</h3>
      <p className="empty-hint" style={{ marginTop: 0 }}>
        Ready-made answers for common application questions, from your profile.
      </p>
      <div className="form-actions">
        <button onClick={loadScreener} disabled={busy}>
          {busy ? "Working…" : "Show screener answers"}
        </button>
      </div>
      {error && <div className="banner error" style={{ marginTop: 10 }}>{error}</div>}
      {screener && screener.length > 0 && (
        <div style={{ marginTop: 12 }}>
          {screener.map((s, i) => (
            <div key={i}>
              <div style={qStyle}>{s.question}</div>
              <div style={aStyle}>
                {s.answer}{" "}
                <button
                  className="btn-secondary btn-sm"
                  onClick={() => copy(s.answer, "s" + i)}
                >
                  {copied === "s" + i ? "Copied" : "Copy"}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
