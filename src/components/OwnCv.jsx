import { useEffect, useRef, useState } from "react";
import { api } from "../api.js";

// Keep the user's own resume file, separate from the profile-driven generated
// CVs. The apply window's "Attach CV" button reveals this file first.
export default function OwnCv() {
  const fileRef = useRef(null);
  const [items, setItems] = useState(null); // null = not loaded yet
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  async function load() {
    try {
      setItems(await api.get("/api/own-cv"));
    } catch {
      setItems([]);
    }
  }
  useEffect(() => {
    load();
  }, []);

  async function onFile(e) {
    const file = e.target.files?.[0];
    e.target.value = ""; // allow re-picking the same file
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      await api.upload("/api/own-cv", file);
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function remove(item) {
    if (!window.confirm(`Remove "${item.filename}"?`)) return;
    try {
      await api.del(`/api/own-cv/${item.id}`);
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  function reveal(item) {
    if (window.copilot?.showItem) window.copilot.showItem(item.file_path);
    else window.alert("Saved here:\n" + item.file_path);
  }

  return (
    <section className="detail-section">
      <div className="own-cv-head">
        <div>
          <h3>Your own resume</h3>
          <p className="empty-hint" style={{ marginTop: 0 }}>
            Keep your latest CV here. The "Attach CV" button in the apply window
            will use this instead of the CV generated from your profile.
          </p>
        </div>
        <input
          ref={fileRef}
          type="file"
          accept=".pdf,.docx,.doc"
          style={{ display: "none" }}
          onChange={onFile}
        />
        <button onClick={() => fileRef.current?.click()} disabled={busy}>
          {busy ? "Uploading…" : "Upload CV"}
        </button>
      </div>

      {error && <div className="banner error">{error}</div>}

      {items && items.length === 0 && (
        <p className="empty-hint">
          No CV uploaded yet — until you add one, "Attach CV" uses the generated
          CV.
        </p>
      )}

      {items && items.length > 0 && (
        <ul className="cv-list">
          {items.map((c) => (
            <li key={c.id} className="cv-item">
              <div className="cv-item-main">
                <span className="cv-name mono">{c.filename}</span>
                <span className="cv-badge">your CV</span>
              </div>
              <a className="link-btn" href={api.fileUrl(`/api/own-cv/${c.id}/download`)}>
                Download
              </a>
              <button
                className="link-btn"
                onClick={() => reveal(c)}
                title={c.file_path}
              >
                Reveal in folder
              </button>
              <button className="link-btn danger" onClick={() => remove(c)}>
                Remove
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
