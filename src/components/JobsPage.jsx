import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api.js";
import Kanban from "./Kanban.jsx";
import JobsTable from "./JobsTable.jsx";
import Analytics from "./Analytics.jsx";
import JobDetail from "./JobDetail.jsx";

const SUBVIEWS = [
  { id: "pipeline", label: "Pipeline" },
  { id: "table", label: "Jobs table" },
  { id: "analytics", label: "Analytics" },
];

// Auto-refresh the listing when the page opens if the last scan is older than
// this. Keeps jobs fresh without re-scanning on every rapid re-open (a scan
// takes a few minutes and hits external boards).
const AUTO_REFRESH_HOURS = 3;

export default function JobsPage() {
  const [subview, setSubview] = useState("pipeline");
  const [status, setStatus] = useState(null); // {running, run}
  const [dataVersion, setDataVersion] = useState(0);
  const [selectedId, setSelectedId] = useState(null);
  const [tableNewOnly, setTableNewOnly] = useState(false);
  const [showAddUrl, setShowAddUrl] = useState(false);
  const [addUrl, setAddUrl] = useState("");
  const [addingUrl, setAddingUrl] = useState(false);
  const wasRunning = useRef(false);
  const poll = useRef(null);

  const refreshStatus = useCallback(async () => {
    try {
      const st = await api.get("/api/jobs/scan/status");
      setStatus(st);
      if (wasRunning.current && !st.running) {
        // a scan just finished — refresh all job views
        setDataVersion((v) => v + 1);
      }
      wasRunning.current = st.running;
      return st.running;
    } catch {
      return false;
    }
  }, []);

  // On open: read scan status, and auto-kick a fresh scan if the last one is
  // stale. The very first scan stays user-initiated (nothing to refresh yet).
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const st = await api.get("/api/jobs/scan/status").catch(() => null);
      if (cancelled || !st) return;
      setStatus(st);
      wasRunning.current = st.running;
      const finished =
        st.run?.status === "done" && st.run?.finished_at
          ? new Date(st.run.finished_at).getTime()
          : null;
      const isStale =
        finished !== null &&
        Date.now() - finished > AUTO_REFRESH_HOURS * 3600 * 1000;
      if (!st.running && isStale) startScan();
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // poll while a scan is running
  useEffect(() => {
    if (status?.running && !poll.current) {
      poll.current = setInterval(refreshStatus, 2000);
    }
    if (!status?.running && poll.current) {
      clearInterval(poll.current);
      poll.current = null;
    }
    return () => {
      if (poll.current) {
        clearInterval(poll.current);
        poll.current = null;
      }
    };
  }, [status?.running, refreshStatus]);

  async function startScan() {
    try {
      const st = await api.post("/api/jobs/scan", {});
      setStatus(st);
      wasRunning.current = true;
    } catch (err) {
      window.alert(`Could not start scan: ${err.message}`);
    }
  }

  async function addByUrl() {
    const url = addUrl.trim();
    if (!url) return;
    setAddingUrl(true);
    try {
      await api.post("/api/jobs/add-by-url", { url });
      setAddUrl("");
      setShowAddUrl(false);
      setDataVersion((v) => v + 1);
    } catch (err) {
      window.alert(`Could not add that job: ${err.message}`);
    } finally {
      setAddingUrl(false);
    }
  }

  const run = status?.run;
  const running = status?.running;
  const scannedTotal =
    run?.source_counts
      ? Object.values(run.source_counts).reduce((a, b) => a + b, 0)
      : 0;

  return (
    <div className="page page-wide">
      <header className="page-head">
        <div>
          <h1>Jobs</h1>
          <p className="page-sub">
            Scanned from your job boards, scored against your profile, and tracked
            through the pipeline. Apply from the card; the app never submits for you.
          </p>
        </div>
        <div className="head-actions">
          <button className="btn-secondary" onClick={() => setShowAddUrl((v) => !v)}>
            Add job by URL
          </button>
          <button onClick={startScan} disabled={running}>
            {running ? "Scanning…" : "Scan now"}
          </button>
        </div>
      </header>

      {showAddUrl && (
        <div className="add-url-row">
          <input
            placeholder="Paste a job posting URL"
            value={addUrl}
            onChange={(e) => setAddUrl(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && addByUrl()}
            autoFocus
          />
          <button onClick={addByUrl} disabled={addingUrl || !addUrl.trim()}>
            {addingUrl ? "Adding…" : "Add"}
          </button>
          <button className="btn-secondary" onClick={() => setShowAddUrl(false)}>
            Cancel
          </button>
        </div>
      )}

      {running && (
        <div className="banner scan-banner">
          <span className="scan-spinner" />
          <span>
            Scanning your sources — {scannedTotal} found so far
            {run?.source_counts && Object.keys(run.source_counts).length > 0 && (
              <span className="mono scan-sources">
                {"  "}
                {Object.entries(run.source_counts)
                  .map(([s, n]) => `${s} ${n}`)
                  .join("  ·  ")}
              </span>
            )}
          </span>
        </div>
      )}
      {!running && run?.status === "done" && (
        <div className="banner">
          Last scan found {run.total_found} listings,{" "}
          {run.total_new > 0 ? (
            <button
              className="link-inline"
              onClick={() => {
                setTableNewOnly(true);
                setSubview("table");
              }}
            >
              {run.total_new} new
            </button>
          ) : (
            <>{run.total_new} new</>
          )}
          . Runs daily and whenever you hit Scan now.
        </div>
      )}
      {!running && run?.status === "error" && (
        <div className="banner error">Last scan failed: {run.error}</div>
      )}

      <div className="section-tabs">
        {SUBVIEWS.map((v) => (
          <button
            key={v.id}
            className={`tab ${subview === v.id ? "active" : ""}`}
            onClick={() => setSubview(v.id)}
          >
            {v.label}
          </button>
        ))}
      </div>

      <div className="section-body">
        {subview === "pipeline" && (
          <Kanban
            key={`k-${dataVersion}`}
            scanAt={!running && run?.status === "done" ? run.started_at : null}
            onOpen={setSelectedId}
            onChanged={() => setDataVersion((v) => v + 1)}
          />
        )}
        {subview === "table" && (
          <JobsTable
            key={`t-${dataVersion}`}
            onOpen={setSelectedId}
            newOnly={tableNewOnly}
            onNewOnlyChange={setTableNewOnly}
          />
        )}
        {subview === "analytics" && <Analytics key={`a-${dataVersion}`} />}
      </div>

      {selectedId && (
        <JobDetail
          jobId={selectedId}
          onClose={() => setSelectedId(null)}
          onChanged={() => {
            setDataVersion((v) => v + 1);
          }}
        />
      )}
    </div>
  );
}
