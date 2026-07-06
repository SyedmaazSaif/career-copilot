import { useEffect, useState } from "react";
import { api } from "../api.js";

export default function Analytics() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    api
      .get("/api/jobs/analytics")
      .then(setData)
      .catch((e) => setError(e.message));
  }, []);

  if (!data && !error) return <div className="muted">Loading analytics…</div>;
  if (error) return <div className="banner error">{error}</div>;

  const pct = (v) => (v == null ? "—" : `${Math.round(v * 100)}%`);
  const maxWeek = Math.max(1, ...data.applications_per_week.map((w) => w.count));
  const maxSourced = Math.max(1, ...data.source_conversion.map((s) => s.sourced));

  return (
    <div className="analytics">
      <div className="stat-row">
        <Stat label="Total jobs" value={data.total_jobs} />
        <Stat label="Applied" value={data.total_applied} />
        <Stat label="Response rate" value={pct(data.response_rate)} />
        <Stat
          label="Avg days to reply"
          value={data.avg_days_to_first_reply ?? "—"}
        />
      </div>

      <div className="analytics-grid">
        <div className="panel">
          <h2>Applications per week</h2>
          {data.applications_per_week.length === 0 ? (
            <p className="empty-hint">
              No applications yet. Move a card to Applied to start tracking.
            </p>
          ) : (
            <div className="bar-chart">
              {data.applications_per_week.map((w) => (
                <div className="bar-col" key={w.week}>
                  <div className="bar-track">
                    <div
                      className="bar-fill"
                      style={{ height: `${(w.count / maxWeek) * 100}%` }}
                    />
                  </div>
                  <span className="bar-value mono">{w.count}</span>
                  <span className="bar-label mono">{w.week.split("-")[1]}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="panel">
          <h2>Pipeline</h2>
          <div className="stage-bars">
            {Object.entries(data.stage_counts).map(([stage, count]) => (
              <div className="stage-bar-row" key={stage}>
                <span className="stage-bar-label">{stage}</span>
                <div className="stage-bar-track">
                  <div
                    className={`stage-bar-fill stage-${stage.toLowerCase()}`}
                    style={{
                      width: `${(count / Math.max(1, data.total_jobs)) * 100}%`,
                    }}
                  />
                </div>
                <span className="stage-bar-count mono">{count}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="panel">
        <h2>Source conversion</h2>
        <table className="conv-table">
          <thead>
            <tr>
              <th>Source</th>
              <th>Sourced</th>
              <th>Applied</th>
              <th>Rate</th>
              <th className="conv-bar-head">Volume</th>
            </tr>
          </thead>
          <tbody>
            {data.source_conversion.map((s) => (
              <tr key={s.source}>
                <td className="mono">{s.source}</td>
                <td className="mono">{s.sourced}</td>
                <td className="mono">{s.applied}</td>
                <td className="mono">{pct(s.rate)}</td>
                <td>
                  <div className="conv-bar-track">
                    <div
                      className="conv-bar-fill"
                      style={{ width: `${(s.sourced / maxSourced) * 100}%` }}
                    />
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Stat({ label, value }) {
  return (
    <div className="stat-tile">
      <span className="stat-value mono">{value}</span>
      <span className="stat-label">{label}</span>
    </div>
  );
}
