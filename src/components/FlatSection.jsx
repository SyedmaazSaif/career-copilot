import { useEffect, useState } from "react";
import { api } from "../api.js";

// A reusable list of records with add / edit / delete. Config-driven so
// skills, education, certifications, and languages all reuse it.
export default function FlatSection({
  title,
  endpoint,
  fields,
  renderTitle,
  renderMeta,
  groupBy,
  emptyHint,
}) {
  const [items, setItems] = useState(null);
  const [error, setError] = useState(null);
  const [editing, setEditing] = useState(null); // id being edited, or "new"
  const [draft, setDraft] = useState({});

  async function load() {
    try {
      setItems(await api.get(endpoint));
      setError(null);
    } catch (err) {
      setError(err.message);
    }
  }
  useEffect(() => {
    load();
  }, [endpoint]);

  function startAdd() {
    const blank = {};
    fields.forEach((f) => (blank[f.name] = ""));
    setDraft(blank);
    setEditing("new");
  }
  function startEdit(item) {
    const d = {};
    fields.forEach((f) => (d[f.name] = item[f.name] ?? ""));
    setDraft(d);
    setEditing(item.id);
  }
  function cancel() {
    setEditing(null);
    setDraft({});
  }

  async function save() {
    try {
      if (editing === "new") await api.post(endpoint, draft);
      else await api.put(`${endpoint}/${editing}`, draft);
      cancel();
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function remove(item) {
    if (!window.confirm(`Delete "${renderTitle(item)}"?`)) return;
    try {
      await api.del(`${endpoint}/${item.id}`);
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  if (items === null && !error) return <div className="muted">Loading…</div>;

  const grouped = groupItems(items || [], groupBy);

  return (
    <div className="panel">
      <div className="panel-head">
        <h2>{title}</h2>
        <button className="btn-secondary" onClick={startAdd}>
          Add {title.replace(/s$/, "").toLowerCase()}
        </button>
      </div>

      {error && <div className="banner error">{error}</div>}

      {editing === "new" && (
        <RecordForm
          fields={fields}
          draft={draft}
          setDraft={setDraft}
          onSave={save}
          onCancel={cancel}
        />
      )}

      {items && items.length === 0 && editing !== "new" && (
        <p className="empty-hint">{emptyHint}</p>
      )}

      {grouped.map(([group, rows]) => (
        <div className="record-group" key={group || "_"}>
          {group && <div className="group-label mono">{group}</div>}
          <ul className="record-list">
            {rows.map((item) =>
              editing === item.id ? (
                <li key={item.id}>
                  <RecordForm
                    fields={fields}
                    draft={draft}
                    setDraft={setDraft}
                    onSave={save}
                    onCancel={cancel}
                  />
                </li>
              ) : (
                <li key={item.id} className="record-row">
                  <div className="record-main">
                    <span className="record-title">{renderTitle(item)}</span>
                    {renderMeta(item) && (
                      <span className="record-meta mono">{renderMeta(item)}</span>
                    )}
                  </div>
                  <div className="record-actions">
                    <button className="link-btn" onClick={() => startEdit(item)}>
                      Edit
                    </button>
                    <button className="link-btn danger" onClick={() => remove(item)}>
                      Delete
                    </button>
                  </div>
                </li>
              )
            )}
          </ul>
        </div>
      ))}
    </div>
  );
}

function RecordForm({ fields, draft, setDraft, onSave, onCancel }) {
  const canSave = fields
    .filter((f) => f.required)
    .every((f) => (draft[f.name] || "").trim());

  return (
    <div className="record-form">
      <div className="field-grid">
        {fields.map((f) => (
          <label key={f.name} className="field">
            <span className="field-label">
              {f.label}
              {f.required && <span className="req">*</span>}
            </span>
            {f.type === "select" ? (
              <select
                className={f.mono ? "mono" : ""}
                value={draft[f.name] ?? ""}
                onChange={(e) => setDraft({ ...draft, [f.name]: e.target.value })}
              >
                <option value="">—</option>
                {f.options.map((o) => (
                  <option key={o} value={o}>
                    {o}
                  </option>
                ))}
              </select>
            ) : (
              <input
                className={f.mono ? "mono" : ""}
                value={draft[f.name] ?? ""}
                onChange={(e) => setDraft({ ...draft, [f.name]: e.target.value })}
              />
            )}
          </label>
        ))}
      </div>
      <div className="form-actions">
        <button onClick={onSave} disabled={!canSave}>
          Save
        </button>
        <button className="btn-secondary" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </div>
  );
}

function groupItems(items, groupBy) {
  if (!groupBy) return [["", items]];
  const map = new Map();
  for (const item of items) {
    const key = item[groupBy] || "Other";
    if (!map.has(key)) map.set(key, []);
    map.get(key).push(item);
  }
  return [...map.entries()];
}
