import { useEffect, useState } from "react";
import { api } from "./api.js";
import { checkForUpdate } from "./updateCheck.js";
import ProfilePage from "./components/ProfilePage.jsx";
import UpdatePopup from "./components/UpdatePopup.jsx";
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
  // Bumped each time the backend comes back after being unreachable, which
  // remounts the open page so it reloads its data instead of keeping a stale
  // "Failed to fetch" error on screen.
  const [reconnects, setReconnects] = useState(0);
  const [update, setUpdate] = useState(null); // {current, latest, url} | null
  const [updating, setUpdating] = useState(false);
  const [updateError, setUpdateError] = useState(null);
  const [updateDismissed, setUpdateDismissed] = useState(false);

  // Keep checking the backend, not just once at launch. After the laptop wakes
  // from sleep (or the window is reopened) the backend can be briefly away
  // while the app restarts it; this notices when it is back and refreshes.
  useEffect(() => {
    let alive = true;
    let last = null;
    const check = () => {
      api
        .health()
        .then(() => {
          if (!alive) return;
          if (last === false) setReconnects((n) => n + 1);
          last = true;
          setOnline(true);
        })
        .catch(() => {
          if (!alive) return;
          last = false;
          setOnline(false);
        });
    };
    check();
    // Faster while offline so recovery shows up within a couple of seconds.
    let timer;
    const loop = () => {
      timer = setTimeout(() => {
        check();
        loop();
      }, last === false ? 2000 : 10000);
    };
    loop();
    const onVisible = () => document.visibilityState === "visible" && check();
    window.addEventListener("focus", check);
    window.addEventListener("online", check);
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      alive = false;
      clearTimeout(timer);
      window.removeEventListener("focus", check);
      window.removeEventListener("online", check);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, []);

  // Inside Electron the main process runs the check and pushes the result.
  // Outside it (npm run web, or a browser tab) nothing would, so run the same
  // check here -- otherwise those users never learn an update exists.
  useEffect(() => {
    if (window.copilot?.onUpdateAvailable) {
      return window.copilot.onUpdateAvailable((info) => setUpdate(info));
    }
    let alive = true;
    checkForUpdate().then((info) => alive && info && setUpdate(info));
    return () => {
      alive = false;
    };
  }, []);

  async function applyUpdate() {
    if (!window.copilot?.updateApp) return;
    setUpdating(true);
    setUpdateError(null);
    try {
      const res = await window.copilot.updateApp();
      if (!res?.ok) {
        setUpdating(false);
        setUpdateError(
          res?.error || "Update failed. Use 'View release' to download it manually."
        );
      }
      // On success the app reloads itself; keep the button in "Updating…".
    } catch {
      setUpdating(false);
      setUpdateError("Update failed. Use 'View release' to download it manually.");
    }
  }

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
        {update && !updateDismissed && (
          <UpdatePopup
            update={update}
            updating={updating}
            updateError={updateError}
            onUpdateNow={applyUpdate}
            onRemindLater={() => setUpdateDismissed(true)}
          />
        )}
        {update && updateDismissed && (
          <div className="update-banner">
            <span>
              <strong>Update available</strong> — career-copilot {update.latest} is
              out (you have {update.current}).
              {updateError && <span className="update-error"> {updateError}</span>}
            </span>
            <span className="update-banner-actions">
              {window.copilot?.updateApp && (
                <button
                  className="btn-secondary"
                  onClick={applyUpdate}
                  disabled={updating}
                >
                  {updating ? "Updating…" : "Update now"}
                </button>
              )}
              <button
                className="link-btn"
                onClick={() =>
                  window.copilot?.openExternal
                    ? window.copilot.openExternal(update.url)
                    : window.open(update.url, "_blank", "noopener")
                }
              >
                View release
              </button>
              <button className="icon-btn" onClick={() => setUpdate(null)} aria-label="Dismiss">
                ×
              </button>
            </span>
          </div>
        )}
        {view === "profile" && <ProfilePage key={`profile-${reconnects}`} />}
        {view === "jobs" && <JobsPage key={`jobs-${reconnects}`} />}
        {view === "settings" && <SettingsPage key={`settings-${reconnects}`} />}
      </main>
    </div>
  );
}
