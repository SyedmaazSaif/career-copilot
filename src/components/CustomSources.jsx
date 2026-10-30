import { useEffect, useState } from "react";
import { api } from "../api.js";

const KINDS = [
  { id: "rss", label: "RSS feed", hint: "Paste a job-board RSS/Atom feed URL" },
  { id: "company", label: "Company careers page", hint: "Paste a company's careers URL — auto-detects its ATS" },
  { id: "greenhouse", label: "Greenhouse", hint: "Company slug, e.g. stripe" },
  { id: "lever", label: "Lever", hint: "Company slug, e.g. netflix" },
  { id: "ashby", label: "Ashby", hint: "Company slug, e.g. openai" },
  { id: "url", label: "Website URL", hint: "Any careers/job page (best-effort)" },
];

export default function CustomSources() {
  const [sources, setSources] = useState(null);
  const [error, setError] = useState(null);
  const [draft, setDraft] = useState({ kind: "rss", value: "", label: "" });
  const [adding, setAdding] = useState(false);
  const [companyName, setCompanyName] = useState("");
  const [resolving, setResolving] = useState(false);
  const [resolved, setResolved] = useState(null);
  const [companies, setCompanies] = useState([]);
  const [comp, setComp] = useState({ name: "", ats: "greenhouse", slug: "" });

  async function load() {
    try {
      setSources(await api.get("/api/settings/sources"));
      setError(null);
    } catch (e) {
      setError(e.message);
    }
  }
  useEffect(() => {
    load();
    loadCompanies();
  }, []);

  async function add() {
    if (!draft.value.trim()) return;
    setAdding(true);
    try {
      await api.post("/api/settings/sources", draft);
      setDraft({ kind: "rss", value: "", label: "" });
      await load();
    } catch (e) {
      setError(e.message);
    } finally {
      setAdding(false);
    }
  }
  async function remove(id) {
    try {
      await api.del(`/api/settings/sources/${id}`);
      await load();
    } catch (e) {
      setError(e.message);
    }
  }
  async function toggle(src) {
    try {
      await api.put(`/api/settings/sources/${src.id}`, { ...src, enabled: !src.enabled });
      await load();
    } catch (e) {
      setError(e.message);
    }
  }
  async function findCompany() {
    const name = companyName.trim();
    if (!name) return;
    setResolving(true);
    setResolved(null);
    setError(null);
    try {
      setResolved(await api.post("/api/settings/sources/resolve", { name }));
    } catch (e) {
      setError(e.message);
    } finally {
      setResolving(false);
    }
  }
  async function addResolved() {
    if (!resolved || !resolved.found) return;
    setAdding(true);
    try {
      await api.post("/api/settings/sources", {
        kind: resolved.kind,
        value: resolved.value,
        label: resolved.label,
      });
      setResolved(null);
      setCompanyName("");
      await load();
    } catch (e) {
      setError(e.message);
    } finally {
      setAdding(false);
    }
  }
  async function loadCompanies() {
    try {
      setCompanies(await api.get("/api/settings/companies"));
    } catch (e) {
      setError(e.message);
    }
  }
  async function addCompany() {
    if (!comp.name.trim() || !comp.slug.trim()) return;
    setAdding(true);
    try {
      await api.post("/api/settings/companies", comp);
      setComp({ name: "", ats: "greenhouse", slug: "" });
      await loadCompanies();
    } catch (e) {
      setError(e.message);
    } finally {
      setAdding(false);
    }
  }
  async function removeCompany(id) {
    try {
      await api.del(`/api/settings/companies/${id}`);
      await loadCompanies();
    } catch (e) {
      setError(e.message);
    }
  }

  const kind = KINDS.find((k) => k.id === draft.kind);

  return (
    <div className="panel" style={{ marginTop: 18 }}>
      <div className="panel-head">
        <h2>Your own job sources</h2>
        <span className="filter-count mono">{sources?.length ?? 0} added</span>
      </div>
      <p className="empty-hint" style={{ marginTop: 0 }}>
        Add job boards beyond the built-in ones. RSS feeds and Greenhouse/Lever company
        boards are the most reliable. These are scanned alongside the built-in boards.
      </p>

      {error && <div className="banner error">{error}</div>}

      <div className="source-add">
        <select
          value={draft.kind}
          onChange={(e) => setDraft({ ...draft, kind: e.target.value })}
        >
          {KINDS.map((k) => (
            <option key={k.id} value={k.id}>
              {k.label}
            </option>
          ))}
        </select>
        <input
          placeholder={kind?.hint}
          value={draft.value}
          onChange={(e) => setDraft({ ...draft, value: e.target.value })}
          onKeyDown={(e) => e.key === "Enter" && add()}
        />
        <input
          className="source-label"
          placeholder="Label (optional)"
          value={draft.label}
          onChange={(e) => setDraft({ ...draft, label: e.target.value })}
        />
        <button className="btn-secondary" onClick={add} disabled={adding || !draft.value.trim()}>
          Add source
        </button>
      </div>

      <div className="source-add" style={{ marginTop: 10 }}>
        <input
          placeholder="Find a company by name — e.g. Stripe"
          value={companyName}
          onChange={(e) => setCompanyName(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && findCompany()}
        />
        <button className="btn-secondary" onClick={findCompany} disabled={resolving || !companyName.trim()}>
          {resolving ? "Searching…" : "Find company"}
        </button>
      </div>
      {resolved &&
        (resolved.found ? (
          <div style={{ marginTop: 10, display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
            <span className="mono" style={{ fontSize: 12, color: "#667284" }}>Found:</span>
            <strong>{resolved.label}</strong>
            <span className="mono" style={{ fontSize: 12, color: "#667284" }}>{resolved.url}</span>
            <button className="btn-secondary" onClick={addResolved} disabled={adding}>Add</button>
          </div>
        ) : (
          <div className="banner error" style={{ marginTop: 10 }}>
            Couldn't find a careers page for that name. Try the full company name, or add it manually above.
          </div>
        ))}

      <div className="panel" style={{ marginTop: 18 }}>
        <div className="panel-head">
          <h2>Target companies</h2>
          <span className="filter-count mono">{companies?.length ?? 0} tracked</span>
        </div>
        <p className="empty-hint" style={{ marginTop: 0 }}>
          Track a company's own job board. The app pulls all of its open jobs every
          scan and scores them.
        </p>
        <div className="source-add">
          <input
            placeholder="Company name"
            value={comp.name}
            onChange={(e) => setComp({ ...comp, name: e.target.value })}
          />
          <select value={comp.ats} onChange={(e) => setComp({ ...comp, ats: e.target.value })}>
            <option value="greenhouse">Greenhouse</option>
            <option value="lever">Lever</option>
            <option value="ashby">Ashby</option>
            <option value="workable">Workable</option>
          </select>
          <input
            placeholder="Board slug (e.g. stripe)"
            value={comp.slug}
            onChange={(e) => setComp({ ...comp, slug: e.target.value })}
            onKeyDown={(e) => e.key === "Enter" && addCompany()}
          />
          <button
            className="btn-secondary"
            onClick={addCompany}
            disabled={adding || !comp.name.trim() || !comp.slug.trim()}
          >
            Add company
          </button>
        </div>
        {companies && companies.length > 0 && (
          <ul className="record-list" style={{ marginTop: 12 }}>
            {companies.map((c) => (
              <li key={c.id} className="record-row">
                <div className="record-main">
                  <span className="source-kind mono">{c.ats}</span>
                  <span className="record-title">{c.name}</span>
                  <span className="record-meta mono">{c.slug}</span>
                  {c.auto_added && <span className="record-meta">auto-added</span>}
                </div>
                <div className="record-actions">
                  <button className="link-btn danger" onClick={() => removeCompany(c.id)}>Remove</button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      {sources && sources.length > 0 && (
        <ul className="record-list" style={{ marginTop: 12 }}>
          {sources.map((s) => (
            <li key={s.id} className="record-row">
              <div className="record-main">
                <span className="source-kind mono">{s.kind}</span>
                <span className="record-title">{s.label || s.value}</span>
                {s.label && <span className="record-meta mono">{s.value}</span>}
              </div>
              <div className="record-actions">
                <button className="link-btn" onClick={() => toggle(s)}>
                  {s.enabled ? "On" : "Off"}
                </button>
                <button className="link-btn danger" onClick={() => remove(s.id)}>
                  Remove
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
