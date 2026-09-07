import { useEffect, useState } from "react";
import { api } from "../api.js";
import CustomSources from "./CustomSources.jsx";
import DismissedJobs from "./DismissedJobs.jsx";
import AiStatus from "./AiStatus.jsx";

const SOURCE_LABELS = {
  weworkremotely: "We Work Remotely",
  remoteco: "Remote.co",
  remotive: "Remotive",
  arbeitnow: "Arbeitnow",
  himalayas: "Himalayas",
  remoteok: "RemoteOK",
  linkedin: "LinkedIn",
  hiringcafe: "Hiring.cafe",
  wellfound: "Wellfound",
  mustakbil: "Mustakbil (Pakistan)",
};

const ARRANGEMENTS = [
  { id: "remote", label: "Remote" },
  { id: "hybrid", label: "Hybrid" },
  { id: "onsite", label: "On-site" },
];

export default function SettingsPage() {
  const [config, setConfig] = useState(null);
  const [status, setStatus] = useState("loading");
  const [error, setError] = useState(null);
  const [newTerm, setNewTerm] = useState("");
  const [newLocation, setNewLocation] = useState("");

  useEffect(() => {
    api
      .get("/api/settings/search")
      .then((c) => {
        setConfig(c);
        setStatus("ready");
      })
      .catch((e) => {
        setError(e.message);
        setStatus("error");
      });
  }, []);

  function dirty() {
    if (status === "saved") setStatus("ready");
  }
  function addTerm() {
    const t = newTerm.trim();
    if (!t || config.queries.includes(t)) return;
    setConfig((c) => ({ ...c, queries: [...c.queries, t] }));
    setNewTerm("");
    dirty();
  }
  function removeTerm(t) {
    setConfig((c) => ({ ...c, queries: c.queries.filter((x) => x !== t) }));
    dirty();
  }
  function addLocation() {
    const l = newLocation.trim();
    if (!l || (config.locations || []).includes(l)) return;
    setConfig((c) => ({ ...c, locations: [...(c.locations || []), l] }));
    setNewLocation("");
    dirty();
  }
  function removeLocation(l) {
    setConfig((c) => ({
      ...c,
      locations: (c.locations || []).filter((x) => x !== l),
    }));
    dirty();
  }
  function toggleSource(s) {
    setConfig((c) => ({
      ...c,
      enabled_sources: c.enabled_sources.includes(s)
        ? c.enabled_sources.filter((x) => x !== s)
        : [...c.enabled_sources, s],
    }));
    dirty();
  }
  function toggleArrangement(a) {
    setConfig((c) => ({
      ...c,
      preferred_arrangements: c.preferred_arrangements.includes(a)
        ? c.preferred_arrangements.filter((x) => x !== a)
        : [...c.preferred_arrangements, a],
    }));
    dirty();
  }

  async function save() {
    setStatus("saving");
    setError(null);
    try {
      const saved = await api.put("/api/settings/search", {
        queries: config.queries,
        enabled_sources: config.enabled_sources,
        preferred_arrangements: config.preferred_arrangements,
        locations: config.locations || [],
      });
      setConfig(saved);
      setStatus("saved");
    } catch (e) {
      setError(e.message);
      setStatus("error");
    }
  }

  if (status === "loading")
    return <div className="page"><div className="muted">Loading settings…</div></div>;
  if (!config)
    return <div className="page"><div className="banner error">Could not load settings: {error}</div></div>;

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <h1>Settings</h1>
          <p className="page-sub">
            Control what the scanner looks for, which boards it checks, and the optional
            local AI. Changes to search apply on your next scan.
          </p>
        </div>
        <button onClick={save} disabled={status === "saving"}>
          {status === "saving" ? "Saving…" : status === "saved" ? "Saved" : "Save changes"}
        </button>
      </header>

      {status === "error" && <div className="banner error">{error}</div>}

      <AiStatus />

      <div className="panel">
        <div className="panel-head">
          <h2>Search terms</h2>
          <span className="filter-count mono">{config.queries.length} terms</span>
        </div>
        <p className="empty-hint" style={{ marginTop: 0 }}>
          Each term is searched across your enabled boards.
        </p>
        <div className="term-add">
          <input
            placeholder="e.g. voice ai product manager"
            value={newTerm}
            onChange={(e) => setNewTerm(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && addTerm()}
          />
          <button className="btn-secondary" onClick={addTerm} disabled={!newTerm.trim()}>
            Add term
          </button>
        </div>
        <div className="term-chips">
          {config.queries.map((q) => (
            <span className="term-chip" key={q}>
              {q}
              <button className="term-remove" onClick={() => removeTerm(q)} aria-label={`Remove ${q}`}>
                ✕
              </button>
            </span>
          ))}
        </div>
      </div>

      <div className="panel" style={{ marginTop: 18 }}>
        <div className="panel-head">
          <h2>Locations to search</h2>
          <span className="filter-count mono">
            {(config.locations || []).length} location
            {(config.locations || []).length === 1 ? "" : "s"}
          </span>
        </div>
        <p className="empty-hint" style={{ marginTop: 0 }}>
          Add a city or country to also search there. Boards that filter by location
          (LinkedIn, and Mustakbil for Pakistan) get a pass per location on top of the
          default global search; the remote-only boards carry no on-site roles, so they
          are searched globally either way. Leave empty to search everywhere.
        </p>
        <div className="term-add">
          <input
            placeholder="e.g. Islamabad, Dubai, United Kingdom"
            value={newLocation}
            onChange={(e) => setNewLocation(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && addLocation()}
          />
          <button
            className="btn-secondary"
            onClick={addLocation}
            disabled={!newLocation.trim()}
          >
            Add location
          </button>
        </div>
        <div className="term-chips">
          {(config.locations || []).length === 0 ? (
            <span className="empty-hint" style={{ padding: 0 }}>
              No locations added — searching globally / remote-first.
            </span>
          ) : (
            (config.locations || []).map((l) => (
              <span className="term-chip" key={l}>
                {l}
                <button
                  className="term-remove"
                  onClick={() => removeLocation(l)}
                  aria-label={`Remove ${l}`}
                >
                  ✕
                </button>
              </span>
            ))
          )}
        </div>
      </div>

      <div className="panel" style={{ marginTop: 18 }}>
        <div className="panel-head">
          <h2>Work arrangements you want</h2>
        </div>
        <p className="empty-hint" style={{ marginTop: 0 }}>
          Jobs matching these score higher. On-site is only flagged if you leave it off.
        </p>
        <div className="board-grid">
          {ARRANGEMENTS.map((a) => {
            const on = config.preferred_arrangements.includes(a.id);
            return (
              <label key={a.id} className={`board-toggle ${on ? "on" : ""}`}>
                <input type="checkbox" checked={on} onChange={() => toggleArrangement(a.id)} />
                <span>{a.label}</span>
              </label>
            );
          })}
        </div>
      </div>

      <div className="panel" style={{ marginTop: 18 }}>
        <div className="panel-head">
          <h2>Job boards</h2>
          <span className="filter-count mono">
            {config.enabled_sources.length}/{config.all_sources.length} on
          </span>
        </div>
        <p className="empty-hint" style={{ marginTop: 0 }}>
          Turn boards on or off. All are free and need no account.
        </p>
        <div className="board-grid">
          {config.all_sources.map((s) => {
            const on = config.enabled_sources.includes(s);
            return (
              <label key={s} className={`board-toggle ${on ? "on" : ""}`}>
                <input type="checkbox" checked={on} onChange={() => toggleSource(s)} />
                <span>{SOURCE_LABELS[s] || s}</span>
              </label>
            );
          })}
        </div>
      </div>

      <CustomSources />

      <DismissedJobs />
    </div>
  );
}
