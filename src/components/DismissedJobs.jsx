import { useEffect, useState } from "react";
import { api } from "../api.js";

// Jobs removed from the pipeline. They are blocklisted rather than just deleted,
// so a re-scan cannot resurrect them — undoing lifts the block, and the job
// reappears the next time a board lists it.
export default function DismissedJobs() {
  const [rows, setRows] = useState(null);
  const [error, setError] = useState(null);

  async function load() {
    try {
      setRows(await api.get("/api/jobs/dismissed"));
      setError(null);
    } catch (e) {
      setError(e.message);
    }
  }
  useEffect(() => {
    load();
  }, []);

  async function undo(entry) {
    try {
      await api.del(`/api/jobs/dismissed/${entry.id}`);
      setRows((prev) => prev.filter((r) => r.id !== entry.id));
    } catch (e) {
      setError(e.message);
    }
  }

  return (
    <div className="panel" style={{ marginTop: 18 }}>
      <div className="panel-head">
        <h2>Removed jobs</h2>
        <span className="filter-count mono">
          {(rows || []).length} blocked
        </span>
      </div>
      <p className="empty-hint" style={{ marginTop: 0 }}>
        Jobs you removed. Scans skip these, so they never come back on their own.
        Undo one and the next scan can pick it up again.
      </p>

      {error && <div className="banner error">{error}</div>}

      {rows && rows.length === 0 && (
        <p className="empty-hint" style={{ padding: 0 }}>
          Nothing removed yet.
        </p>
      )}

      {rows && rows.length > 0 && (
        <ul className="cv-list">
          {rows.map((r) => (
            <li key={r.id} className="cv-item">
              <div className="cv-item-main">
                <span className="cv-name">{r.title || "Untitled role"}</span>
                <span className="dim">{r.company || "—"}</span>
                {r.source && <span className="mono cell-src">{r.source}</span>}
              </div>
              <button className="link-btn" onClick={() => undo(r)}>
                Undo
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
