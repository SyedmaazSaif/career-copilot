import { useEffect, useState } from "react";
import { api } from "../api.js";

const EXP_FIELDS = [
  { name: "role", label: "Role", required: true },
  { name: "company", label: "Company", required: true },
  { name: "location", label: "Location" },
  { name: "dates", label: "Dates", mono: true },
  { name: "context", label: "One-line context", textarea: true },
];

export default function ExperienceSection() {
  const [items, setItems] = useState(null);
  const [error, setError] = useState(null);
  const [editingExp, setEditingExp] = useState(null); // id or "new"
  const [expDraft, setExpDraft] = useState({});

  async function load() {
    try {
      setItems(await api.get("/api/experiences"));
      setError(null);
    } catch (err) {
      setError(err.message);
    }
  }
  useEffect(() => {
    load();
  }, []);

  function startAddExp() {
    setExpDraft({ role: "", company: "", location: "", dates: "", context: "" });
    setEditingExp("new");
  }
  function startEditExp(exp) {
    setExpDraft({
      role: exp.role,
      company: exp.company,
      location: exp.location,
      dates: exp.dates,
      context: exp.context,
    });
    setEditingExp(exp.id);
  }
  function cancelExp() {
    setEditingExp(null);
    setExpDraft({});
  }
  async function saveExp() {
    try {
      if (editingExp === "new") await api.post("/api/experiences", expDraft);
      else await api.put(`/api/experiences/${editingExp}`, expDraft);
      cancelExp();
      await load();
    } catch (err) {
      setError(err.message);
    }
  }
  async function removeExp(exp) {
    if (!window.confirm(`Delete "${exp.role} at ${exp.company}" and all its bullets?`))
      return;
    try {
      await api.del(`/api/experiences/${exp.id}`);
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  if (items === null && !error) return <div className="muted">Loading…</div>;

  return (
    <div className="panel">
      <div className="panel-head">
        <h2>Experience</h2>
        <button className="btn-secondary" onClick={startAddExp}>
          Add role
        </button>
      </div>

      {error && <div className="banner error">{error}</div>}

      {editingExp === "new" && (
        <ExpForm
          draft={expDraft}
          setDraft={setExpDraft}
          onSave={saveExp}
          onCancel={cancelExp}
        />
      )}

      {items && items.length === 0 && editingExp !== "new" && (
        <p className="empty-hint">
          Add each role you have held. Titles, employers, and dates are the frozen facts
          every CV must trace back to.
        </p>
      )}

      {(items || []).map((exp) =>
        editingExp === exp.id ? (
          <ExpForm
            key={exp.id}
            draft={expDraft}
            setDraft={setExpDraft}
            onSave={saveExp}
            onCancel={cancelExp}
          />
        ) : (
          <ExperienceCard
            key={exp.id}
            exp={exp}
            onEdit={() => startEditExp(exp)}
            onDelete={() => removeExp(exp)}
            onChanged={load}
          />
        )
      )}
    </div>
  );
}

function ExpForm({ draft, setDraft, onSave, onCancel }) {
  const canSave = EXP_FIELDS.filter((f) => f.required).every((f) =>
    (draft[f.name] || "").trim()
  );
  return (
    <div className="record-form">
      <div className="field-grid">
        {EXP_FIELDS.map((f) => (
          <label
            key={f.name}
            className={`field ${f.textarea ? "field-wide" : ""}`}
          >
            <span className="field-label">
              {f.label}
              {f.required && <span className="req">*</span>}
            </span>
            {f.textarea ? (
              <textarea
                rows={2}
                value={draft[f.name] ?? ""}
                onChange={(e) => setDraft({ ...draft, [f.name]: e.target.value })}
              />
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
          Save role
        </button>
        <button className="btn-secondary" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </div>
  );
}

function ExperienceCard({ exp, onEdit, onDelete, onChanged }) {
  const [addingBullet, setAddingBullet] = useState(false);
  const [editingBullet, setEditingBullet] = useState(null);
  const [bDraft, setBDraft] = useState({ text: "", tags: "" });

  function startAddBullet() {
    setBDraft({ text: "", tags: "" });
    setEditingBullet(null);
    setAddingBullet(true);
  }
  function startEditBullet(b) {
    setBDraft({ text: b.text, tags: (b.skill_tags || []).join(", ") });
    setAddingBullet(false);
    setEditingBullet(b.id);
  }
  function cancelBullet() {
    setAddingBullet(false);
    setEditingBullet(null);
  }
  async function saveBullet() {
    const payload = {
      text: bDraft.text,
      skill_tags: bDraft.tags
        .split(",")
        .map((t) => t.trim())
        .filter(Boolean),
    };
    try {
      if (editingBullet) await api.put(`/api/experiences/bullets/${editingBullet}`, payload);
      else await api.post(`/api/experiences/${exp.id}/bullets`, payload);
      cancelBullet();
      await onChanged();
    } catch (err) {
      window.alert(`Could not save bullet: ${err.message}`);
    }
  }
  async function removeBullet(b) {
    if (!window.confirm("Delete this bullet?")) return;
    try {
      await api.del(`/api/experiences/bullets/${b.id}`);
      await onChanged();
    } catch (err) {
      window.alert(err.message);
    }
  }

  return (
    <article className="exp-card">
      <div className="exp-head">
        <div>
          <h3>{exp.role}</h3>
          <div className="exp-sub">
            <span>{exp.company}</span>
            {exp.location && <span className="dim"> · {exp.location}</span>}
            {exp.dates && <span className="mono exp-dates"> · {exp.dates}</span>}
          </div>
        </div>
        <div className="record-actions">
          <button className="link-btn" onClick={onEdit}>
            Edit
          </button>
          <button className="link-btn danger" onClick={onDelete}>
            Delete
          </button>
        </div>
      </div>

      {exp.context && <p className="exp-context">{exp.context}</p>}

      <ul className="bullet-list">
        {(exp.bullets || []).map((b) =>
          editingBullet === b.id ? (
            <li key={b.id}>
              <BulletForm
                draft={bDraft}
                setDraft={setBDraft}
                onSave={saveBullet}
                onCancel={cancelBullet}
              />
            </li>
          ) : (
            <li key={b.id} className="bullet-row">
              <div className="bullet-text">
                <span>{b.text}</span>
                {(b.skill_tags || []).length > 0 && (
                  <span className="tag-row">
                    {b.skill_tags.map((t) => (
                      <span className="tag" key={t}>
                        {t}
                      </span>
                    ))}
                  </span>
                )}
              </div>
              <div className="record-actions">
                <button className="link-btn" onClick={() => startEditBullet(b)}>
                  Edit
                </button>
                <button className="link-btn danger" onClick={() => removeBullet(b)}>
                  Delete
                </button>
              </div>
            </li>
          )
        )}
      </ul>

      {addingBullet ? (
        <BulletForm
          draft={bDraft}
          setDraft={setBDraft}
          onSave={saveBullet}
          onCancel={cancelBullet}
        />
      ) : (
        <button className="link-btn add-bullet" onClick={startAddBullet}>
          + Add bullet
        </button>
      )}
    </article>
  );
}

function BulletForm({ draft, setDraft, onSave, onCancel }) {
  return (
    <div className="bullet-form">
      <label className="field field-wide">
        <span className="field-label">Bullet text</span>
        <textarea
          rows={2}
          value={draft.text}
          onChange={(e) => setDraft({ ...draft, text: e.target.value })}
        />
      </label>
      <label className="field field-wide">
        <span className="field-label">Skill tags (comma separated)</span>
        <input
          value={draft.tags}
          onChange={(e) => setDraft({ ...draft, tags: e.target.value })}
          placeholder="Product strategy, CAC modeling"
        />
      </label>
      <div className="form-actions">
        <button onClick={onSave} disabled={!draft.text.trim()}>
          Save bullet
        </button>
        <button className="btn-secondary" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </div>
  );
}
