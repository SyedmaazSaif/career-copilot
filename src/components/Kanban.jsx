import { useEffect, useRef, useState } from "react";
import { api } from "../api.js";
import MatchMeter from "./MatchMeter.jsx";

// The board tracks only whether you've applied -- the app has no way to know
// about a screen, an interview, or an offer, so pretending to track those
// stages was fiction. Any stage besides "Sourced" (there used to be several)
// buckets into "Applied" here; the backend still records whatever exact stage
// a job carries from before this simplification.
const COLUMNS = ["Sourced", "Applied"];
const COLUMN_LABEL = { Sourced: "Jobs", Applied: "Applied" };
const STAGE_HINT = {
  Sourced: "Found by a scan, not yet applied",
  Applied: "You have applied",
};
const DRAG_THRESHOLD = 5; // px before a press becomes a drag rather than a click

// `scanAt` is when the most recent completed scan started. A Sourced job last
// seen before it dropped off the boards is likely no longer accepting
// applications ("possibly closed").
// "New" comes from the backend (job.is_new, same rule against the latest
// completed run); scanAt is the fallback when the board is rendered from a
// payload that predates that field.
function isNew(job, scanAt) {
  if (job.is_new !== undefined) return job.is_new;
  if (!scanAt || !job.first_scanned_at) return false;
  return new Date(job.first_scanned_at).getTime() >= new Date(scanAt).getTime();
}
function isStale(job, scanAt) {
  if (!scanAt || !job.last_seen_at || job.stage !== "Sourced") return false;
  return new Date(job.last_seen_at).getTime() < new Date(scanAt).getTime();
}

// "$120k", "$120k–$150k", or null when unknown.
function fmtSalary(job) {
  const lo = job.salary_min;
  const hi = job.salary_max;
  if (!lo && !hi) return null;
  const k = (n) => "$" + Math.round(n / 1000) + "k";
  if (lo && hi && lo !== hi) return k(lo) + "–" + k(hi);
  return k(hi || lo);
}

export default function Kanban({ onOpen, onChanged, scanAt }) {
  const [jobs, setJobs] = useState(null);
  const [error, setError] = useState(null);
  const [overStage, setOverStage] = useState(null);
  const [clearing, setClearing] = useState(false);
  const drag = useRef(null); // { id, fromStage, startX, startY, moved }

  async function load() {
    try {
      setJobs(await api.get("/api/jobs?limit=1000"));
      setError(null);
    } catch (err) {
      setError(err.message);
    }
  }
  useEffect(() => {
    load();
  }, []);

  // Not dependent on any closed-over `jobs`: the optimistic update uses the
  // functional setState form, so it always sees the latest board.
  async function moveTo(jobId, stage) {
    setJobs((prev) =>
      prev ? prev.map((j) => (j.id === jobId ? { ...j, stage } : j)) : prev
    );
    try {
      await api.patch(`/api/jobs/${jobId}`, { stage });
      onChanged?.();
    } catch (err) {
      setError(err.message);
      load();
    }
  }

  async function remove(e, job) {
    e.stopPropagation();
    const label = [job.title, job.company].filter(Boolean).join(" at ");
    if (!window.confirm(`Remove "${label}"? It won't come back in future scans.`))
      return;
    setJobs((prev) => (prev ? prev.filter((j) => j.id !== job.id) : prev));
    try {
      await api.post(`/api/jobs/${job.id}/dismiss`, {});
      onChanged?.();
    } catch (err) {
      setError(err.message);
      load();
    }
  }

  async function clearStale() {
    setClearing(true);
    try {
      await api.post("/api/jobs/close-stale", {});
      await load();
      onChanged?.();
    } catch (err) {
      setError(err.message);
    } finally {
      setClearing(false);
    }
  }

  function stageFromPoint(x, y) {
    let el = document.elementFromPoint(x, y);
    while (el && !el.dataset?.stage) el = el.parentElement;
    return el?.dataset?.stage ?? null;
  }

  function onPointerDown(e, job) {
    if (e.button !== 0) return;
    drag.current = {
      id: job.id,
      fromStage: job.stage,
      startX: e.clientX,
      startY: e.clientY,
      moved: false,
    };
    window.addEventListener("pointermove", onPointerMove);
    window.addEventListener("pointerup", onPointerUp);
  }
  function onPointerMove(e) {
    const d = drag.current;
    if (!d) return;
    if (!d.moved) {
      if (Math.hypot(e.clientX - d.startX, e.clientY - d.startY) < DRAG_THRESHOLD) return;
      d.moved = true;
      document.body.classList.add("dragging-cursor");
    }
    setOverStage(stageFromPoint(e.clientX, e.clientY));
  }
  function onPointerUp(e) {
    const d = drag.current;
    window.removeEventListener("pointermove", onPointerMove);
    window.removeEventListener("pointerup", onPointerUp);
    document.body.classList.remove("dragging-cursor");
    setOverStage(null);
    drag.current = null;
    if (!d) return;
    if (!d.moved) {
      onOpen(d.id); // it was a click, not a drag
      return;
    }
    const stage = stageFromPoint(e.clientX, e.clientY);
    if (stage && stage !== d.fromStage) moveTo(d.id, stage);
  }

  if (jobs === null && !error) return <div className="muted">Loading pipeline…</div>;
  if (error) return <div className="banner error">{error}</div>;

  if (jobs && jobs.length === 0) {
    return (
      <div className="empty-panel">
        <p>No jobs yet. Hit "Scan now" above to pull today's roles from your boards.</p>
      </div>
    );
  }

  // Any stage other than "Sourced" (leftover Screening/Interview/Offer from
  // before the pipeline was simplified, plus "Applied" itself) buckets into
  // the Applied column -- the app never sees those stages happen, so drawing
  // them as separate columns was always fiction. Closed jobs never reach this
  // component: the backend excludes them by default.
  const byStage = { Sourced: [], Applied: [] };
  for (const j of jobs) (j.stage === "Sourced" ? byStage.Sourced : byStage.Applied).push(j);
  // Sourced is scan output — surface the freshest roles first so re-scans feel
  // like they update the board. Applied stays ranked by fit + order.
  const ts = (j) => (j.first_scanned_at ? new Date(j.first_scanned_at).getTime() : 0);
  byStage.Sourced.sort((a, b) => ts(b) - ts(a) || b.score - a.score);
  byStage.Applied.sort((a, b) => b.score - a.score || a.sort_order - b.sort_order);

  const staleCount = byStage.Sourced.filter((j) => isStale(j, scanAt)).length;

  return (
    <>
      <div className="kan-toolbar">
        {staleCount > 0 && (
          <button className="btn-ghost btn-ghost-warn" onClick={clearStale} disabled={clearing}>
            {clearing
              ? "Clearing…"
              : `Clear ${staleCount} possibly-closed`}
          </button>
        )}
      </div>
      <div className="kanban">
        {COLUMNS.map((stage) => (
          <div
            key={stage}
            data-stage={stage}
            className={`kan-col ${overStage === stage ? "drop-target" : ""}`}
          >
            <div className="kan-head" title={STAGE_HINT[stage]}>
              <span className="kan-title">{COLUMN_LABEL[stage]}</span>
              <span className="kan-count mono">{byStage[stage].length}</span>
            </div>
            <div className="kan-cards">
              {byStage[stage].map((job) => {
                const stale = isStale(job, scanAt);
                return (
                  <article
                    key={job.id}
                    className={`job-card ${stale ? "stale" : ""} ${
                      drag.current?.id === job.id && drag.current?.moved ? "dragging" : ""
                    }`}
                    onPointerDown={(e) => onPointerDown(e, job)}
                  >
                    {/* stopPropagation on pointerdown too: the card treats a
                        press as the start of a drag (and a click as "open"). */}
                    <button
                      className="card-remove"
                      title="Remove this job — it won't come back in future scans"
                      aria-label={`Remove ${job.title}`}
                      onPointerDown={(e) => e.stopPropagation()}
                      onClick={(e) => remove(e, job)}
                    >
                      ✕
                    </button>
                    <div className="job-card-main">
                      <div className="job-card-text">
                        <span className="job-card-title">
                          {stage === "Sourced" && !stale && isNew(job, scanAt) && (
                            <span className="new-pill">New</span>
                          )}
                          {job.title}
                        </span>
                        <span className="job-card-company">
                          {job.company || job.source}
                        </span>
                      </div>
                      <MatchMeter score={job.score} size={46} stroke={5} />
                    </div>
                    <div className="job-card-foot">
                      {stale ? (
                        <span
                          className="stale-pill"
                          title="Not seen in the latest scan — likely no longer accepting applications"
                        >
                          Possibly closed
                        </span>
                      ) : (
                        <span className="mono job-card-src">{job.source}</span>
                      )}
                      <span className="job-card-foot-right">
                        {fmtSalary(job) && (
                          <span className="pay-pill mono" title={job.salary_text}>
                            {fmtSalary(job)}
                          </span>
                        )}
                        {job.red_flags.length > 0 && (
                          <span className="flag-pill" title={job.red_flags.join(" · ")}>
                            {job.red_flags.length} flag{job.red_flags.length > 1 ? "s" : ""}
                          </span>
                        )}
                      </span>
                    </div>
                    <button
                      className="card-mark-applied"
                      onPointerDown={(e) => e.stopPropagation()}
                      onClick={(e) => {
                        e.stopPropagation();
                        moveTo(job.id, stage === "Sourced" ? "Applied" : "Sourced");
                      }}
                    >
                      {stage === "Sourced" ? "Mark as applied" : "Move back to Jobs"}
                    </button>
                  </article>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </>
  );
}
