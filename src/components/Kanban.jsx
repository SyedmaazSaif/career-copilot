import { useEffect, useRef, useState } from "react";
import { api } from "../api.js";
import MatchMeter from "./MatchMeter.jsx";

const STAGES = ["Sourced", "Applied", "Screening", "Interview", "Offer", "Closed"];
const STAGE_HINT = {
  Sourced: "Found by a scan, not yet acted on",
  Applied: "You have applied",
  Screening: "Recruiter screen in progress",
  Interview: "Interviewing",
  Offer: "Offer on the table",
  Closed: "Rejected, withdrawn, or declined",
};
const DRAG_THRESHOLD = 5; // px before a press becomes a drag rather than a click

export default function Kanban({ onOpen, onChanged }) {
  const [jobs, setJobs] = useState(null);
  const [error, setError] = useState(null);
  const [overStage, setOverStage] = useState(null);
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
  for (const s of STAGES)
    byStage[s].sort((a, b) => b.score - a.score || a.sort_order - b.sort_order);

  return (
    <div className="kanban">
      {STAGES.map((stage) => (
        <div
          key={stage}
          data-stage={stage}
          className={`kan-col ${overStage === stage ? "drop-target" : ""}`}
        >
          <div className="kan-head">
            <span className="kan-title">{stage}</span>
            <span className="kan-count mono">{byStage[stage].length}</span>
          </div>
          <div className="kan-hint">{STAGE_HINT[stage]}</div>
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
                    <span className="job-card-title">{job.title}</span>
                    <span className="job-card-company">{job.company || job.source}</span>
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
  );
}
