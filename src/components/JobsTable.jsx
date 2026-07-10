import { useEffect, useMemo, useState } from "react";
import { api } from "../api.js";
import MatchMeter from "./MatchMeter.jsx";

const STAGES = ["Sourced", "Applied", "Screening", "Interview", "Offer", "Closed"];

// "$120k", "$120k–$150k", or null when unknown.
function fmtSalary(job) {
  const lo = job.salary_min;
  const hi = job.salary_max;
  if (!lo && !hi) return null;
  const k = (n) => "$" + Math.round(n / 1000) + "k";
  if (lo && hi && lo !== hi) return k(lo) + "–" + k(hi);
  return k(hi || lo);
}

export default function JobsTable({ onOpen }) {
  const [jobs, setJobs] = useState(null);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState("");
  const [locationQ, setLocationQ] = useState("");
  const [stage, setStage] = useState("");
  const [source, setSource] = useState("");
  const [workType, setWorkType] = useState("");
  const [empType, setEmpType] = useState("");
  const [minScore, setMinScore] = useState(0);
  const [minSalary, setMinSalary] = useState(0); // in $k
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

  // Relevance search: every whitespace-separated token must appear somewhere in
  // the job's text (title, company, tags, requirements, description). Partial
  // and any-order — "fintech pm" matches "Senior Product Manager, Fintech".
  function matchesRelevance(job, tokens) {
    if (tokens.length === 0) return true;
    const hay = [
      job.title,
      job.company,
      job.location,
      (job.tags || []).join(" "),
      (job.requirements || []).join(" "),
      job.description,
    ]
      .join(" ")
      .toLowerCase();
    return tokens.every((t) => hay.includes(t));
  }

  // Filters are NOT absolute. Each active filter scores a job (1 = match,
  // 0.5 = soft/unknown, 0 = miss). Jobs matching ANY active filter are kept and
  // ranked by how many they match, so a strict combination never returns zero —
  // the closest matches surface at the top instead.
  const { rows, activeCount } = useMemo(() => {
    if (!jobs) return { rows: [], activeCount: 0 };
    const tokens = search.toLowerCase().split(/\s+/).filter(Boolean);
    const loc = locationQ.trim().toLowerCase();

    const criteria = [];
    if (tokens.length) criteria.push((j) => (matchesRelevance(j, tokens) ? 1 : 0));
    if (loc) criteria.push((j) => ((j.location || "").toLowerCase().includes(loc) ? 1 : 0));
    if (stage) criteria.push((j) => (j.stage === stage ? 1 : 0));
    if (source) criteria.push((j) => (j.source === source ? 1 : 0));
    if (workType) criteria.push((j) => (j.work_type === workType ? 1 : 0));
    if (empType) criteria.push((j) => (j.employment_type === empType ? 1 : 0));
    if (minScore > 0) criteria.push((j) => (j.score >= minScore ? 1 : 0));
    if (flagsOnly) criteria.push((j) => (j.red_flags.length > 0 ? 1 : 0));
    if (minSalary > 0)
      criteria.push((j) => {
        const top = j.salary_max ?? j.salary_min;
        if (top == null) return 0.5; // unknown salary: surfaced low, never dropped
        return top >= minSalary * 1000 ? 1 : 0;
      });

    const active = criteria.length;
    if (active === 0) {
      const all = [...jobs]
        .sort((a, b) => b.score - a.score)
        .map((j) => ({ job: j, matched: 0 }));
      return { rows: all, activeCount: 0 };
    }

    const scored = jobs
      .map((j) => {
        let sum = 0;
        let matched = 0;
        for (const c of criteria) {
          const v = c(j);
          sum += v;
          if (v >= 1) matched += 1;
        }
        return { job: j, matched, relevance: sum };
      })
      .filter((x) => x.relevance > 0)
      .sort((a, b) => b.relevance - a.relevance || b.job.score - a.job.score);
    return { rows: scored, activeCount: active };
  }, [jobs, search, locationQ, stage, source, workType, empType, minScore, minSalary, flagsOnly]);

  if (jobs === null && !error) return <div className="muted">Loading…</div>;
  if (error) return <div className="banner error">{error}</div>;

  return (
    <div className="panel">
      <div className="filters">
        <input
          className="filter-search"
          placeholder="Search role, company, industry, salary… (any order)"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <input
          className="filter-location"
          placeholder="Filter by location"
          value={locationQ}
          onChange={(e) => setLocationQ(e.target.value)}
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
          <option value="">Any arrangement</option>
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
        <label className="filter-salary">
          <span className="mono">min $</span>
          <input
            type="number"
            min="0"
            step="10"
            placeholder="k/yr"
            value={minSalary || ""}
            onChange={(e) => setMinSalary(Number(e.target.value) || 0)}
          />
          <span className="mono">k</span>
        </label>
        <label className="filter-check">
          <input
            type="checkbox"
            checked={flagsOnly}
            onChange={(e) => setFlagsOnly(e.target.checked)}
          />
          Red flags only
        </label>
        <span className="filter-count mono">
          {rows.length} jobs{activeCount > 0 ? " · ranked by match" : ""}
        </span>
      </div>

      {activeCount > 0 && (
        <p className="empty-hint" style={{ marginTop: 0 }}>
          Filters are relaxed — jobs matching more of your {activeCount} filter
          {activeCount > 1 ? "s" : ""} rank first, and close matches still show
          instead of an empty list.
        </p>
      )}

      <div className="table-scroll">
        <table className="jobs-table">
          <thead>
            <tr>
              <th className="col-meter">Match</th>
              <th>Role</th>
              <th>Work</th>
              <th>Pay</th>
              <th>Stage</th>
              <th>Source</th>
              <th>Flags</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(({ job, matched }) => {
              const pay = fmtSalary(job);
              return (
                <tr key={job.id} onClick={() => onOpen(job.id)}>
                  <td className="col-meter">
                    <MatchMeter score={job.score} size={42} stroke={5} />
                  </td>
                  <td>
                    <div className="cell-title">{job.title}</div>
                    <div className="cell-company">{job.company || "—"}</div>
                    {activeCount > 0 && (
                      <span
                        className={`match-tally ${matched === activeCount ? "full" : ""}`}
                      >
                        {matched}/{activeCount} filters
                      </span>
                    )}
                  </td>
                  <td>
                    <span className={`work-pill work-${job.work_type}`}>
                      {job.work_type === "unknown" ? "—" : job.work_type}
                    </span>
                    {job.employment_type && job.employment_type !== "unknown" && (
                      <div className="cell-emp mono">{job.employment_type}</div>
                    )}
                  </td>
                  <td>
                    {pay ? (
                      <span className="pay-pill mono" title={job.salary_text}>
                        {pay}
                      </span>
                    ) : (
                      <span className="dim">—</span>
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
              );
            })}
          </tbody>
        </table>
        {rows.length === 0 && (
          <p className="empty-hint" style={{ padding: "16px" }}>
            No jobs yet — run a scan to populate the list.
          </p>
        )}
      </div>
    </div>
  );
}
