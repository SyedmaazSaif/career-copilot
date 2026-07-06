import { useEffect, useState } from "react";
import { api } from "../api.js";
import MatchMeter from "./MatchMeter.jsx";

const STAGES = ["Sourced", "Applied", "Screening", "Interview", "Offer", "Closed"];

// Prefer the native in-app browser (Electron). In the dev web build, fall back
// to a new tab.
function openToApply(url) {
  if (window.copilot?.openApply) window.copilot.openApply(url);
  else window.open(url, "_blank", "noreferrer");
}

export default function JobDetail({ jobId, onClose, onChanged }) {
  const [job, setJob] = useState(null);
  const [error, setError] = useState(null);

  async function load() {
    try {
      setJob(await api.get(`/api/jobs/${jobId}`));
    } catch (err) {
      setError(err.message);
    }
  }
  useEffect(() => {
    load();
  }, [jobId]);

  // close on Escape
  useEffect(() => {
    const onKey = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  async function setStage(stage) {
    try {
      const updated = await api.patch(`/api/jobs/${jobId}`, { stage });
      setJob(updated);
      onChanged?.();
    } catch (err) {
      window.alert(err.message);
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        {error && <div className="banner error">{error}</div>}
        {!job && !error && <div className="muted">Loading…</div>}
        {job && (
          <>
            <header className="modal-head">
              <div className="modal-title-wrap">
                <MatchMeter score={job.score} size={72} stroke={7} />
                <div>
                  <h2>{job.title}</h2>
                  <div className="modal-sub">
                    <span>{job.company || "Unknown company"}</span>
                    <span className="dim"> · {job.location}</span>
                    {job.posted && <span className="mono dim"> · {job.posted}</span>}
                  </div>
                  <div className="modal-badges">
                    <span className="mono modal-src">{job.source}</span>
                    {job.work_type && job.work_type !== "unknown" && (
                      <span className={`work-pill work-${job.work_type}`}>{job.work_type}</span>
                    )}
                    {job.employment_type && job.employment_type !== "unknown" && (
                      <span className="work-pill work-emp">{job.employment_type}</span>
                    )}
                  </div>
                </div>
              </div>
              <button className="icon-btn" onClick={onClose} aria-label="Close">
                ✕
              </button>
            </header>

            <div className="stage-picker">
              {STAGES.map((s) => (
                <button
                  key={s}
                  className={`stage-choice ${job.stage === s ? "active" : ""}`}
                  onClick={() => setStage(s)}
                >
                  {s}
                </button>
              ))}
            </div>

            {job.red_flags.length > 0 && (
              <div className="flags-box">
                <span className="flags-title">Red flags</span>
                <ul>
                  {job.red_flags.map((f) => (
                    <li key={f}>{f}</li>
                  ))}
                </ul>
              </div>
            )}

            <ScoreBreakdown reason={job.score_reason} />

            <CVSection job={job} />

            {job.requirements.length > 0 && (
              <section className="detail-section">
                <h3>Requirements</h3>
                <ul className="req-list">
                  {job.requirements.map((r, i) => (
                    <li key={i}>{r}</li>
                  ))}
                </ul>
              </section>
            )}

            <section className="detail-section">
              <h3>Full description</h3>
              <div className="job-desc">{job.description || "No description captured."}</div>
            </section>

            <div className="modal-actions">
              <button className="btn-apply" onClick={() => openToApply(job.url)}>
                Open listing to apply
              </button>
              <span className="apply-note">
                Opens in the app's browser. You apply manually — the app never submits
                for you.
              </span>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function CVSection({ job }) {
  const [packs, setPacks] = useState(null);
  const [targetTitle, setTargetTitle] = useState(job.title || "");
  const [emphasis, setEmphasis] = useState("");
  const [length, setLength] = useState("concise");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  async function load() {
    try {
      setPacks(await api.get(`/api/jobs/${job.id}/cv`));
    } catch {
      setPacks([]);
    }
  }
  useEffect(() => {
    load();
  }, [job.id]);

  async function generate() {
    setBusy(true);
    setError(null);
    try {
      await api.post(`/api/jobs/${job.id}/cv`, {
        answers: { target_title: targetTitle, emphasis, length },
      });
      await load();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="detail-section">
      <h3>Tailored CV</h3>
      <p className="empty-hint" style={{ marginTop: 0 }}>
        Builds an ATS-friendly Word CV from your profile facts only, ordered for this
        job. Nothing is invented.
      </p>
      <div className="cv-form">
        <label className="field">
          <span className="field-label">Target title</span>
          <input value={targetTitle} onChange={(e) => setTargetTitle(e.target.value)} />
        </label>
        <label className="field">
          <span className="field-label">What to emphasize (optional)</span>
          <input
            value={emphasis}
            onChange={(e) => setEmphasis(e.target.value)}
            placeholder="e.g. monetization, partnerships"
          />
        </label>
        <label className="field">
          <span className="field-label">Length</span>
          <select value={length} onChange={(e) => setLength(e.target.value)}>
            <option value="concise">Concise (top 3 bullets/role)</option>
            <option value="detailed">Detailed (up to 5)</option>
          </select>
        </label>
      </div>
      <div className="form-actions">
        <button onClick={generate} disabled={busy}>
          {busy ? "Generating…" : "Generate CV pack"}
        </button>
      </div>
      {error && <div className="banner error" style={{ marginTop: 10 }}>{error}</div>}

      {packs && packs.length > 0 && (
        <ul className="cv-list">
          {packs.map((p) => (
            <li key={p.id} className="cv-item">
              <div className="cv-item-main">
                <span className="cv-name mono">{p.filename}</span>
                <span className={`cv-badge ${p.used_ai ? "ai" : ""}`}>
                  {p.used_ai ? "AI-worded" : "standard"}
                </span>
                {p.flags.length > 0 ? (
                  <span className="flag-pill" title={p.flags.join(" | ")}>
                    {p.flags.length} claim{p.flags.length > 1 ? "s" : ""} to check
                  </span>
                ) : (
                  <span className="cv-verified">✓ all traceable</span>
                )}
              </div>
              <a className="link-btn" href={api.fileUrl(`/api/cv/${p.id}/download`)}>
                Download
              </a>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function ScoreBreakdown({ reason }) {
  if (!reason || !reason.skills) return null;
  // "arrangement" replaced the old "remote" key; support both for older jobs.
  const arrangement = reason.arrangement || reason.remote;
  const rows = [
    { key: "skills", label: "Skill overlap", matched: reason.skills.matched },
    { key: "title", label: "Role fit", note: reason.title.label },
    { key: "arrangement", label: "Work arrangement", note: arrangement?.label, cell: arrangement },
    { key: "visa", label: "Visa friendliness", note: reason.visa.label },
    { key: "domain", label: "Domain overlap", matched: reason.domain.matched },
  ];
  return (
    <section className="detail-section">
      <h3>Why this score</h3>
      <div className="score-rows">
        {rows.map((r) => {
          const c = r.cell || reason[r.key];
          if (!c) return null;
          return (
            <div className="score-row" key={r.key}>
              <span className="score-row-label">{r.label}</span>
              <div className="score-row-track">
                <div
                  className="score-row-fill"
                  style={{ width: `${(c.score / c.of) * 100}%` }}
                />
              </div>
              <span className="score-row-num mono">
                {c.score}/{c.of}
              </span>
              <span className="score-row-note">
                {r.note || (r.matched && r.matched.length > 0
                  ? r.matched.slice(0, 4).join(", ")
                  : "")}
              </span>
            </div>
          );
        })}
      </div>
    </section>
  );
}
