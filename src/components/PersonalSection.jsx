import { useEffect, useState } from "react";
import { api } from "../api.js";

const FIELDS = [
  { name: "name", label: "Full name", group: "Identity" },
  { name: "title", label: "Headline title", group: "Identity" },
  { name: "email", label: "Email", group: "Contact" },
  { name: "phone", label: "Phone", group: "Contact", mono: true },
  { name: "location", label: "Location", group: "Contact" },
  { name: "linkedin", label: "LinkedIn", group: "Links" },
  { name: "portfolio", label: "Portfolio", group: "Links" },
  { name: "summary", label: "Professional summary", group: "Summary", textarea: true },
  {
    name: "work_authorization",
    label: "Work authorization",
    group: "Job search",
    textarea: true,
  },
  { name: "notice_period", label: "Notice period", group: "Job search" },
  {
    name: "salary_expectation_usd",
    label: "Salary expectation (USD)",
    group: "Job search",
    mono: true,
  },
  {
    name: "salary_expectation_pkr",
    label: "Salary expectation (PKR)",
    group: "Job search",
    mono: true,
  },
];

const GROUPS = ["Identity", "Contact", "Links", "Summary", "Job search"];

export default function PersonalSection() {
  const [form, setForm] = useState(null);
  const [status, setStatus] = useState("loading"); // loading | ready | saving | saved | error
  const [error, setError] = useState(null);

  useEffect(() => {
    api
      .get("/api/profile")
      .then((p) => {
        setForm(p);
        setStatus("ready");
      })
      .catch((err) => {
        setError(err.message);
        setStatus("error");
      });
  }, []);

  function update(name, value) {
    setForm((f) => ({ ...f, [name]: value }));
    if (status === "saved") setStatus("ready");
  }

  async function save() {
    setStatus("saving");
    setError(null);
    try {
      const { id, ...payload } = form;
      const saved = await api.put("/api/profile", payload);
      setForm(saved);
      setStatus("saved");
    } catch (err) {
      setError(err.message);
      setStatus("error");
    }
  }

  if (status === "loading") return <div className="muted">Loading profile…</div>;
  if (!form) return <div className="banner error">Could not load profile: {error}</div>;

  return (
    <div className="panel">
      {GROUPS.map((group) => (
        <fieldset className="field-group" key={group}>
          <legend>{group}</legend>
          <div className="field-grid">
            {FIELDS.filter((f) => f.group === group).map((f) => (
              <label
                key={f.name}
                className={`field ${f.textarea ? "field-wide" : ""}`}
              >
                <span className="field-label">{f.label}</span>
                {f.textarea ? (
                  <textarea
                    rows={f.name === "summary" ? 5 : 2}
                    value={form[f.name] ?? ""}
                    onChange={(e) => update(f.name, e.target.value)}
                  />
                ) : (
                  <input
                    className={f.mono ? "mono" : ""}
                    value={form[f.name] ?? ""}
                    onChange={(e) => update(f.name, e.target.value)}
                  />
                )}
              </label>
            ))}
          </div>
        </fieldset>
      ))}

      <div className="panel-actions">
        <button onClick={save} disabled={status === "saving"}>
          {status === "saving" ? "Saving…" : status === "saved" ? "Saved" : "Save changes"}
        </button>
        {status === "error" && <span className="error-text">{error}</span>}
      </div>
    </div>
  );
}
