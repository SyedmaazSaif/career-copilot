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
  const [newCompany, setNewCompany] = useState("");
  const [newKeyword, setNewKeyword] = useState("");
  const [newIndustry, setNewIndustry] = useState("");

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

  // Three states per category, because "show it" and "never scan it" are
  // genuinely different instructions: hiding narrows the view for now,
  // excluding stops the scanner storing those postings at all.
  function cycleCategory(code) {
    setConfig((c) => {
      const shown = new Set(c.shown_categories || []);
      const excluded = new Set(c.excluded_categories || []);
      if (excluded.has(code)) {
        excluded.delete(code);           // excluded -> default (shown)
      } else if (shown.has(code)) {
        shown.delete(code);
        excluded.add(code);              // only-shown -> excluded
      } else if (shown.size > 0) {
        shown.add(code);                 // hidden -> shown
      } else {
        // Nothing pinned yet: pinning the first one means "only this".
        shown.add(code);
      }
      return {
        ...c,
        shown_categories: [...shown],
        excluded_categories: [...excluded],
      };
    });
    dirty();
  }

  function showAllCategories() {
    setConfig((c) => ({ ...c, shown_categories: [], excluded_categories: [] }));
    dirty();
  }

  function addBlockedCompany() {
    const name = newCompany.trim();
    if (!name) return;
    setConfig((c) => ({
      ...c,
      company_block_list: [...new Set([...(c.company_block_list || []), name])],
    }));
    setNewCompany("");
    dirty();
  }

  function removeBlockedCompany(name) {
    setConfig((c) => ({
      ...c,
      company_block_list: (c.company_block_list || []).filter((x) => x !== name),
    }));
    dirty();
  }

  function addExclusionKeyword() {
    const k = newKeyword.trim().toLowerCase();
    if (!k) return;
    setConfig((c) => ({
      ...c,
      exclusion_keywords: [...new Set([...(c.exclusion_keywords || []), k])],
    }));
    setNewKeyword("");
    dirty();
  }
  function removeExclusionKeyword(k) {
    setConfig((c) => ({
      ...c,
      exclusion_keywords: (c.exclusion_keywords || []).filter((x) => x !== k),
    }));
    dirty();
  }
  function addExcludedIndustry() {
    const i = newIndustry.trim().toLowerCase();
    if (!i) return;
    setConfig((c) => ({
      ...c,
      excluded_industries: [...new Set([...(c.excluded_industries || []), i])],
    }));
    setNewIndustry("");
    dirty();
  }
  function removeExcludedIndustry(i) {
    setConfig((c) => ({
      ...c,
      excluded_industries: (c.excluded_industries || []).filter((x) => x !== i),
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
        shown_categories: config.shown_categories || [],
        excluded_categories: config.excluded_categories || [],
        company_block_list: config.company_block_list || [],
        exclusion_keywords: config.exclusion_keywords || [],
        excluded_industries: config.excluded_industries || [],
        max_age_days: config.max_age_days ?? 30,
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
          <h2>Kinds of work</h2>
          <button className="btn-secondary btn-sm" onClick={showAllCategories}>
            Show everything
          </button>
        </div>
        <p className="empty-hint" style={{ marginTop: 0 }}>
          Click once to show only that kind of work, again to never scan it, and
          again to go back to normal. Leave them all alone to see everything.
        </p>
        <div className="board-grid">
          {(config.all_categories || []).map((cat) => {
            const shown = (config.shown_categories || []).includes(cat.code);
            const excluded = (config.excluded_categories || []).includes(cat.code);
            const cls = excluded ? "excluded" : shown ? "on" : "";
            return (
              <button
                key={cat.code}
                type="button"
                className={`board-toggle category-toggle ${cls}`}
                onClick={() => cycleCategory(cat.code)}
                title={
                  excluded
                    ? "Never scanned — click to allow again"
                    : shown
                    ? "Shown — click to exclude from scans"
                    : "Click to show only this"
                }
              >
                <span>{cat.name}</span>
                {excluded && <span className="category-mark">never</span>}
                {shown && <span className="category-mark">only</span>}
              </button>
            );
          })}
        </div>
      </div>

      <div className="panel" style={{ marginTop: 18 }}>
        <div className="panel-head">
          <h2>Companies to never show</h2>
          <span className="filter-count mono">
            {(config.company_block_list || []).length} blocked
          </span>
        </div>
        <p className="empty-hint" style={{ marginTop: 0 }}>
          Postings from these companies are dropped during the scan. Useful for
          agencies that repost the same role every week.
        </p>
        <div className="term-add">
          <input
            value={newCompany}
            onChange={(e) => setNewCompany(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && addBlockedCompany()}
            placeholder="Company name"
          />
          <button className="btn-secondary" onClick={addBlockedCompany}>
            Block
          </button>
        </div>
        <div className="term-chips">
          {(config.company_block_list || []).map((name) => (
            <span key={name} className="term-chip">
              {name}
              <button
                className="term-remove"
                onClick={() => removeBlockedCompany(name)}
                aria-label={`Unblock ${name}`}
              >
                ✕
              </button>
            </span>
          ))}
        </div>
      </div>

      <div className="panel" style={{ marginTop: 18 }}>
        <div className="panel-head">
          <h2>Words to never show</h2>
          <span className="filter-count mono">{(config.exclusion_keywords || []).length} words</span>
        </div>
        <p className="empty-hint" style={{ marginTop: 0 }}>
          A job whose title or description contains any of these is dropped.
        </p>
        <div className="term-add">
          <input
            value={newKeyword}
            onChange={(e) => setNewKeyword(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && addExclusionKeyword()}
            placeholder="e.g. crypto, gambling"
          />
          <button className="btn-secondary" onClick={addExclusionKeyword}>Add word</button>
        </div>
        <div className="term-chips">
          {(config.exclusion_keywords || []).map((k) => (
            <span key={k} className="term-chip">
              {k}
              <button className="term-remove" onClick={() => removeExclusionKeyword(k)} aria-label={`Remove ${k}`}>✕</button>
            </span>
          ))}
        </div>
      </div>

      <div className="panel" style={{ marginTop: 18 }}>
        <div className="panel-head">
          <h2>Industries to never show</h2>
          <span className="filter-count mono">{(config.excluded_industries || []).length} industries</span>
        </div>
        <p className="empty-hint" style={{ marginTop: 0 }}>
          A job whose text mentions any of these industries is dropped.
        </p>
        <div className="term-add">
          <input
            value={newIndustry}
            onChange={(e) => setNewIndustry(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && addExcludedIndustry()}
            placeholder="e.g. healthcare, finance"
          />
          <button className="btn-secondary" onClick={addExcludedIndustry}>Add industry</button>
        </div>
        <div className="term-chips">
          {(config.excluded_industries || []).map((i) => (
            <span key={i} className="term-chip">
              {i}
              <button className="term-remove" onClick={() => removeExcludedIndustry(i)} aria-label={`Remove ${i}`}>✕</button>
            </span>
          ))}
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
