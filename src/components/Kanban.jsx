import { useEffect, useRef, useState } from "react";
import { api } from "../api.js";
import MatchMeter from "./MatchMeter.jsx";

const STAGES = ["Sourced", "Applied", "Screening", "Interview", "Offer", "Closed"];
// The two stages that matter for daily triage. The rest live behind "Show all".
const FOCUS_STAGES = ["Sourced", "Applied"];
const STAGE_HINT = {
  Sourced: "Found by a scan, not yet acted on",
  Applied: "You have applied",
  Screening: "Recruiter screen in progress",
  Interview: "Interviewing",
  Offer: "Offer on the table",
  Closed: "Rejected, withdrawn, or declined",
};
const DRAG_THRESHOLD = 5; // px before a press becomes a drag rather than a click

// A job counts as "new" if it was first scanned during the most recent scan.
function isNew(job, newSince) {
  if (!newSince || !job.first_scanned_at) return false;
  return new Date(job.first_scanned_at).getTime() >= new Date(newSince).getTime();
}

export default function Kanban({ onOpen, onChanged, newSince }) {
  const [jobs, setJobs] = useState(null);
  const [error, setError] = useState(null);
  const [overStage, setOverStage] = useState(null);
  const [showAll, setShowAll] = useState(false);
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

  const byStage = Object.fromEntries(STAGES.map((s) => [s, []]));
  for (const j of jobs) (byStage[j.stage] ?? byStage.Sourced).push(j);
  // Sourced is scan output — surface the freshest roles first so re-scans feel
  // like they update the board. User-curated stages stay ranked by fit + order.
  const ts = (j) => (j.first_scanned_at ? new Date(j.first_scanned_at).getTime() : 0);
  byStage.Sourced.sort((a, b) => ts(b) - ts(a) || b.score - a.score);
  for (const s of STAGES) {
    if (s === "Sourced") continue;
    byStage[s].sort((a, b) => b.score - a.score || a.sort_order - b.sort_order);
  }

  const visibleStages = showAll ? STAGES : FOCUS_STAGES;
  const hiddenCount = showAll
    ? 0
    : STAGES.filter((s) => !FOCUS_STAGES.includes(s)).reduce(
        (n, s) => n + byStage[s].length,
        0
      );

  return (
    <>
      <div className="kan-toolbar">
        <button className="btn-ghost" onClick={() => setShowAll((v) => !v)}>
          {showAll ? "Focus: Sourced + Applied" : "Show all stages"}
        </button>
        {!showAll && hiddenCount > 0 && (
          <span className="kan-toolbar-note">
            {hiddenCount} job{hiddenCount > 1 ? "s" : ""} in later stages hidden
          </span>
        )}
      </div>
      <div className={`kanban ${showAll ? "" : "kanban-focus"}`}>
        {visibleStages.map((stage) => (
          <div
            key={stage}
            data-stage={stage}
            className={`kan-col ${overStage === stage ? "drop-target" : ""}`}
          >
            <div className="kan-head" title={STAGE_HINT[stage]}>
              <span className="kan-title">{stage}</span>
              <span className="kan-count mono">{byStage[stage].length}</span>
            </div>
            <div className="kan-cards">
              {byStage[stage].map((job) => (
                <article
                  key={job.id}
                  className={`job-card ${
                    drag.current?.id === job.id && drag.current?.moved ? "dragging" : ""
                  }`}
                  onPointerDown={(e) => onPointerDown(e, job)}
                >
                  <div className="job-card-main">
                    <div className="job-card-text">
                      <span className="job-card-title">
                        {stage === "Sourced" && isNew(job, newSince) && (
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
                    <span className="mono job-card-src">{job.source}</span>
                    {job.red_flags.length > 0 && (
                      <span className="flag-pill" title={job.red_flags.join(" · ")}>
                        {job.red_flags.length} flag{job.red_flags.length > 1 ? "s" : ""}
                      </span>
                    )}
                  </div>
                </article>
              ))}
            </div>
          </div>
        ))}
      </div>
    </>
  );
}
