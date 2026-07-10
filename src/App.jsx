import { useEffect, useState } from "react";
import { api } from "./api.js";
import ProfilePage from "./components/ProfilePage.jsx";
import JobsPage from "./components/JobsPage.jsx";
import SettingsPage from "./components/SettingsPage.jsx";

const NAV = [
  { id: "profile", label: "Profile" },
  { id: "jobs", label: "Jobs" },
  { id: "settings", label: "Settings" },
];

export default function App() {
  const [view, setView] = useState("profile");
  const [online, setOnline] = useState(null); // null=checking, true, false
  const [update, setUpdate] = useState(null); // {current, latest, url} | null

  useEffect(() => {
    let alive = true;
    api
      .health()
      .then(() => alive && setOnline(true))
      .catch(() => alive && setOnline(false));
    return () => {
      alive = false;
    };
  }, []);

  // Listen for the main process's update check (Electron only).
  useEffect(() => {
    const unsub = window.copilot?.onUpdateAvailable?.((info) => setUpdate(info));
    return unsub;
  }, []);

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true" />
          <span className="brand-name">career-copilot</span>
        </div>
        <nav className="nav">
          {NAV.map((item) => (
            <button
              key={item.id}
              className={`nav-item ${view === item.id ? "active" : ""}`}
              onClick={() => setView(item.id)}
            >
              <span>{item.label}</span>
            </button>
          ))}
        </nav>
        <div className="sidebar-foot">
          <span className={`status-dot ${online === true ? "ok" : online === false ? "error" : "pending"}`} />
          <span className="mono">
            {online === true ? "backend online" : online === false ? "backend offline" : "connecting"}
          </span>
        </div>
      </aside>

      <main className="content">
        {update && (
          <div className="update-banner">
            <span>
              <strong>Update available</strong> — career-copilot {update.latest} is
              out (you have {update.current}). Run <code>git pull</code> in the
              project folder, then restart.
            </span>
            <span className="update-banner-actions">
              <button
                className="link-btn"
                onClick={() => window.copilot?.openExternal?.(update.url)}
              >
                View release
              </button>
              <button className="icon-btn" onClick={() => setUpdate(null)} aria-label="Dismiss">
                ×
              </button>
            </span>
          </div>
        )}
        {view === "profile" && <ProfilePage />}
        {view === "jobs" && <JobsPage />}
        {view === "settings" && <SettingsPage />}
      </main>
    </div>
  );
}
