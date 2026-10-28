import { useEffect, useState } from "react";
import { api } from "../api.js";
import MatchMeter from "./MatchMeter.jsx";
import CoverLetterSection from "./CoverLetter.jsx";
import KeywordCheck from "./KeywordCheck.jsx";

// "$120k", "$120k–$150k", or null when unknown.
function fmtSalary(job) {
  const lo = job.salary_min;
  const hi = job.salary_max;
  if (!lo && !hi) return null;
  const k = (n) => "$" + Math.round(n / 1000) + "k";
  if (lo && hi && lo !== hi) return k(lo) + "–" + k(hi);
  return k(hi || lo);
}

// Prefer the native in-app browser (Electron). In the dev web build, fall back
// to a new tab.
function openToApply(url, cvPath) {
  if (window.copilot?.openApply) window.copilot.openApply(url, cvPath);
  else window.open(url, "_blank", "noreferrer");
}

// The system default browser (Electron's shell.openExternal), so a paywalled or
// login-gated listing opens in a session you are already signed into. The web
// dev build has no shell, so it opens a tab.
function openInBrowser(url) {
  if (window.copilot?.openExternal) window.copilot.openExternal(url);
  else window.open(url, "_blank", "noreferrer");
}

export default function JobDetail({ jobId, onClose, onChanged }) {
  const [job, setJob] = useState(null);
  const [error, setError] = useState(null);
  const [latestCvPath, setLatestCvPath] = useState(null);

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

  async function remove() {
    const label = [job.title, job.company].filter(Boolean).join(" at ");
    if (!window.confirm(`Remove "${label}"? It won't come back in future scans.`))
      return;
    try {
      await api.post(`/api/jobs/${jobId}/dismiss`, {});
      onChanged?.();
      onClose();
    } catch (err) {
      window.alert(`Could not remove that job: ${err.message}`);
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
                    {fmtSalary(job) && (
                      <span className="pay-pill mono" title={job.salary_text}>
                        {fmtSalary(job)}
                      </span>
                    )}
                  </div>
                </div>
              </div>
              <button className="icon-btn" onClick={onClose} aria-label="Close">
                ✕
              </button>
            </header>

            <div className="stage-picker">
              <button
                className={`stage-choice ${job.stage === "Sourced" ? "active" : ""}`}
                onClick={() => setStage("Sourced")}
              >
                Not applied
              </button>
              <button
                className={`stage-choice ${job.stage !== "Sourced" ? "active" : ""}`}
                onClick={() => setStage("Applied")}
              >
                Applied
              </button>
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

            <WhyThisMatch job={job} />

            <ScoreBreakdown reason={job.score_reason} />

            <CVSection job={job} onLatestCv={setLatestCvPath} />

            <CoverLetterSection job={job} />

            <KeywordCheck jobId={job.id} />

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

            <ApplicationLinks job={job} onSaved={setJob} />

            <div className="modal-actions">
              <button className="btn-apply" onClick={() => openToApply(job.url, latestCvPath)}>
                Open listing to apply
              </button>
              <button className="btn-danger" onClick={remove}>
                Remove job
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

// One URL row: the link as selectable text, plus copy / open-in-browser.
function LinkRow({ label, url, onCopy, copied }) {
  return (
    <div className="link-row">
      <span className="link-row-label">{label}</span>
      <span className="link-row-url mono" title={url}>
        {url}
      </span>
      <button className="btn-secondary btn-sm" onClick={() => onCopy(url)}>
        {copied ? "Copied" : "Copy"}
      </button>
      <button className="btn-secondary btn-sm" onClick={() => openInBrowser(url)}>
        Open in browser
      </button>
    </div>
  );
}

// Boards paywall or expire their listings, so the company's own careers page is
// often the only way to actually apply. It is resolved best-effort, and always
// editable — a wrong guess should cost one paste to fix.
function ApplicationLinks({ job, onSaved }) {
  const [copied, setCopied] = useState(null); // which url was just copied
  const [finding, setFinding] = useState(false);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(job.company_url || "");
  const [note, setNote] = useState(null);

  async function copy(url) {
    try {
      await navigator.clipboard.writeText(url);
      setCopied(url);
      setTimeout(() => setCopied((c) => (c === url ? null : c)), 1500);
    } catch {
      setNote("Could not copy — select the link and copy it manually.");
    }
  }

  async function findSite() {
    setFinding(true);
    setNote(null);
    try {
      const res = await api.post(`/api/jobs/${job.id}/find-company-site`, {});
      if (res.company_url) {
        onSaved({ ...job, company_url: res.company_url });
      } else {
        setNote("Couldn't find it — paste the company's careers link yourself.");
        setEditing(true);
      }
    } catch (err) {
      setNote(`Lookup failed: ${err.message}`);
    } finally {
      setFinding(false);
    }
  }

  async function saveDraft() {
    try {
      const updated = await api.patch(`/api/jobs/${job.id}`, {
        company_url: draft.trim(),
      });
      onSaved(updated);
      setEditing(false);
      setNote(null);
    } catch (err) {
      setNote(`Could not save: ${err.message}`);
    }
  }

  return (
    <section className="detail-section">
      <h3>Application links</h3>
      <div className="link-rows">
        <LinkRow
          label="Listing"
          url={job.url}
          onCopy={copy}
          copied={copied === job.url}
        />

        {job.company_url && !editing && (
          <LinkRow
            label="Company site"
            url={job.company_url}
            onCopy={copy}
            copied={copied === job.company_url}
          />
        )}

        {editing ? (
          <div className="link-row">
            <span className="link-row-label">Company site</span>
            <input
              className="link-row-input"
              placeholder="https://company.com/careers"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && saveDraft()}
              autoFocus
            />
            <button className="btn-secondary btn-sm" onClick={saveDraft}>
              Save
            </button>
            <button
              className="btn-secondary btn-sm"
              onClick={() => {
                setDraft(job.company_url || "");
                setEditing(false);
              }}
            >
              Cancel
            </button>
          </div>
        ) : (
          <div className="link-row link-row-actions">
            {!job.company_url && (
              <button
                className="btn-secondary btn-sm"
                onClick={findSite}
                disabled={finding}
              >
                {finding ? "Looking…" : "Find company site"}
              </button>
            )}
            <button
              className="link-btn"
              onClick={() => {
                setDraft(job.company_url || "");
                setEditing(true);
              }}
            >
              {job.company_url ? "Edit company link" : "Paste it yourself"}
            </button>
          </div>
        )}
      </div>
      {note && <p className="empty-hint">{note}</p>}
    </section>
  );
}

function CVSection({ job, onLatestCv }) {
  const [packs, setPacks] = useState(null);
  const [targetTitle, setTargetTitle] = useState(job.title || "");
  const [emphasis, setEmphasis] = useState("");
  const [length, setLength] = useState("concise");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  async function load() {
    try {
      const p = await api.get(`/api/jobs/${job.id}/cv`);
      setPacks(p);
      onLatestCv?.(p && p.length ? p[0] : null);
    } catch {
      setPacks([]);
      onLatestCv?.(null);
    }
  }

  function revealCv(path) {
    if (!path) return;
    if (window.copilot?.showItem) window.copilot.showItem(path);
    else window.alert("Saved here:\n" + path);
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
        Builds an ATS-friendly PDF CV from your profile facts only, ordered for this
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

      {packs && packs.length > 0 && packs[0].file_path && (
        <p className="empty-hint" style={{ marginTop: 8 }}>
          Saved to: <span className="mono">{packs[0].file_path}</span>
        </p>
      )}

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
              <button
                className="btn-secondary btn-sm"
                onClick={() => revealCv(p.file_path)}
                title={p.file_path}
              >
                Reveal in folder
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

// The explanation people actually read. Research on explainable job matching
// is consistent that a sentence naming the evidence ("matches 6 of your
// skills, including Kafka") is trusted far more than a number, and that
// explanations should support a decision rather than argue for one. The bars
// below are for anyone who wants to audit the arithmetic.
function WhyThisMatch({ job }) {
  const lines = job.explanations || [];
  const stale = isStale(job);
  if (lines.length === 0 && !stale) return null;
  return (
    <section className="detail-section why-match">
      <h3>Why this match</h3>
      <ul className="why-list">
        {lines.map((line, i) => (
          <li key={i}>{line}</li>
        ))}
        {stale && (
          <li className="why-stale">
            Posted {stale} days ago
            {job.sightings > 2 ? ` and seen in ${job.sightings} scans` : ""} —
            postings this old are often no longer being filled.
          </li>
        )}
      </ul>
      {job.closed_reason && (
        <p className="why-closed">
          Moved to Closed: {job.closed_reason}. Drag it back if it is still live.
        </p>
      )}
    </section>
  );
}

// Days since the board said it was posted, or null when unknown or recent.
function isStale(job) {
  if (!job.posted_at) return null;
  const days = Math.floor((Date.now() - new Date(job.posted_at)) / 86400000);
  return days >= 30 ? days : null;
}

function ScoreBreakdown({ reason }) {
  if (!reason || !reason.skills) return null;
  // Older rows were scored under earlier rubrics: "arrangement" replaced
  // "remote", "role" replaced "title", and "eligibility" replaced "visa".
  // Support both so a job scanned months ago still renders.
  const arrangement = reason.arrangement || reason.remote;
  const role = reason.role || reason.title;
  const eligibility = reason.eligibility || reason.visa;
  const rows = [
    { key: "skills", label: "Skill overlap", cell: reason.skills, matched: reason.skills.matched },
    { key: "role", label: "Role fit", cell: role, note: role?.label },
    { key: "text", label: "Résumé similarity", cell: reason.text },
    { key: "arrangement", label: "Work arrangement", cell: arrangement, note: arrangement?.label },
    { key: "eligibility", label: "Eligibility", cell: eligibility, note: eligibility?.label },
    { key: "domain", label: "Domain overlap", cell: reason.domain, matched: reason.domain?.matched },
  ];
  return (
    <section className="detail-section">
      <h3>Score breakdown</h3>
      {reason.provisional && (
        <p className="score-provisional">
          Provisional — upload your résumé to score against your real skills.
        </p>
      )}
      <div className="score-rows">
        {rows.map((r) => {
          const c = r.cell;
          if (!c || typeof c.score !== "number") return null;
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
