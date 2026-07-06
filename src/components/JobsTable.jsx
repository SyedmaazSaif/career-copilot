import { useEffect, useMemo, useState } from "react";
import { api } from "../api.js";
import MatchMeter from "./MatchMeter.jsx";

const STAGES = ["Sourced", "Applied", "Screening", "Interview", "Offer", "Closed"];

export default function JobsTable({ onOpen }) {
  const [jobs, setJobs] = useState(null);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState("");
  const [stage, setStage] = useState("");
  const [source, setSource] = useState("");
  const [workType, setWorkType] = useState("");
  const [empType, setEmpType] = useState("");
  const [minScore, setMinScore] = useState(0);
  const [flagsOnly, setFlagsOnly] = useState(false);

  useEffect(() => {
    api
      .get("/api/jobs?limit=1000")
      .then(setJobs)
      .catch((e) => setError(e.message));
  }, []);

  const sources = useMemo(
    () => [...new Set((jobs || []).map((j) => j.source))].sort(),
    [jobs]
  );

  const empTypes = useMemo(
    () => [...new Set((jobs || []).map((j) => j.employment_type).filter((t) => t && t !== "unknown"))].sort(),
    [jobs]
  );

  const filtered = useMemo(() => {
    if (!jobs) return [];
    const s = search.toLowerCase();
    return jobs
      .filter((j) => (stage ? j.stage === stage : true))
      .filter((j) => (source ? j.source === source : true))
      .filter((j) => (workType ? j.work_type === workType : true))
      .filter((j) => (empType ? j.employment_type === empType : true))
      .filter((j) => j.score >= minScore)
      .filter((j) => (flagsOnly ? j.red_flags.length > 0 : true))
      .filter((j) =>
        s
          ? j.title.toLowerCase().includes(s) ||
            j.company.toLowerCase().includes(s)
          : true
      )
      .sort((a, b) => b.score - a.score);
  }, [jobs, search, stage, source, workType, empType, minScore, flagsOnly]);

  if (jobs === null && !error) return <div className="muted">Loading…</div>;
  if (error) return <div className="banner error">{error}</div>;

  return (
    <div className="panel">
      <div className="filters">
        <input
          className="filter-search"
          placeholder="Search title or company"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <select value={stage} onChange={(e) => setStage(e.target.value)}>
          <option value="">All stages</option>
          {STAGES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <select value={source} onChange={(e) => setSource(e.target.value)}>
          <option value="">All sources</option>
          {sources.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <select value={workType} onChange={(e) => setWorkType(e.target.value)}>
          <option value="">Any location</option>
          <option value="remote">Remote</option>
          <option value="hybrid">Hybrid</option>
          <option value="onsite">On-site</option>
          <option value="unknown">Unspecified</option>
        </select>
        <select value={empType} onChange={(e) => setEmpType(e.target.value)}>
          <option value="">Any type</option>
          {empTypes.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
        <label className="filter-score">
          <span className="mono">min {minScore}</span>
          <input
            type="range"
            min="0"
            max="100"
            step="5"
            value={minScore}
            onChange={(e) => setMinScore(Number(e.target.value))}
          />
        </label>
        <label className="filter-check">
          <input
            type="checkbox"
            checked={flagsOnly}
            onChange={(e) => setFlagsOnly(e.target.checked)}
          />
          Red flags only
        </label>
        <span className="filter-count mono">{filtered.length} jobs</span>
      </div>

      <div className="table-scroll">
        <table className="jobs-table">
          <thead>
            <tr>
              <th className="col-meter">Match</th>
              <th>Role</th>
              <th>Work</th>
              <th>Requirements</th>
              <th>Stage</th>
              <th>Source</th>
              <th>Flags</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((job) => (
              <tr key={job.id} onClick={() => onOpen(job.id)}>
                <td className="col-meter">
                  <MatchMeter score={job.score} size={42} stroke={5} />
                </td>
                <td>
                  <div className="cell-title">{job.title}</div>
                  <div className="cell-company">{job.company || "—"}</div>
                </td>
                <td>
                  <span className={`work-pill work-${job.work_type}`}>
                    {job.work_type === "unknown" ? "—" : job.work_type}
                  </span>
                  {job.employment_type && job.employment_type !== "unknown" && (
                    <div className="cell-emp mono">{job.employment_type}</div>
                  )}
                </td>
                <td className="cell-reqs">
                  {job.requirements.length > 0 ? (
                    <span>{job.requirements.slice(0, 2).join(" · ")}</span>
                  ) : (
                    <span className="dim">Open listing for details</span>
                  )}
                </td>
                <td>
                  <span className={`stage-pill stage-${job.stage.toLowerCase()}`}>
                    {job.stage}
                  </span>
                </td>
                <td className="mono cell-src">{job.source}</td>
                <td>
                  {job.red_flags.length > 0 ? (
                    <span className="flag-pill">{job.red_flags.length}</span>
                  ) : (
                    <span className="dim">—</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {filtered.length === 0 && (
          <p className="empty-hint" style={{ padding: "16px" }}>
            No jobs match these filters.
          </p>
        )}
      </div>
    </div>
  );
}
