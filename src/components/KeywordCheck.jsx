import { useState } from "react";
import { api } from "../api.js";

const chipStyle = {
  background: "#f4f6f9",
  border: "1px solid rgba(102,114,132,0.3)",
  borderRadius: 6,
  padding: "2px 8px",
  fontSize: 12,
};

export default function KeywordCheck({ jobId }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  async function check() {
    setLoading(true);
    setError(null);
    try {
      setData(await api.get(`/api/jobs/${jobId}/keyword-gaps`));
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="detail-section">
      <h3>ATS keyword check</h3>
      <p className="empty-hint" style={{ marginTop: 0 }}>
        See which words the job asks for that your profile doesn't mention — plus
        quick fixes to get past the first screen.
      </p>
      <div className="form-actions">
        <button onClick={check} disabled={loading}>
          {loading ? "Checking…" : "Run keyword check"}
        </button>
      </div>
      {error && <div className="banner error" style={{ marginTop: 10 }}>{error}</div>}
      {data && (
        <div style={{ marginTop: 12 }}>
          {data.coverage != null && (
            <p style={{ marginBottom: 4 }}>
              <strong>Coverage:</strong> {Math.round(data.coverage * 100)}% ({data.present}/{data.total} keywords found)
            </p>
          )}
          {data.missing.length > 0 && (
            <>
              <p className="empty-hint" style={{ margin: "4px 0" }}>
                Missing from your profile (only add what is true):
              </p>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                {data.missing.map((w) => (
                  <span key={w} className="mono" style={chipStyle}>{w}</span>
                ))}
              </div>
            </>
          )}
          {data.missing.length === 0 && (
            <p className="empty-hint" style={{ margin: "4px 0" }}>
              Great — your profile already covers this job's keywords.
            </p>
          )}
          {data.tips.length > 0 && (
            <ul style={{ marginTop: 10, paddingLeft: 18 }}>
              {data.tips.map((t, i) => (
                <li key={i} style={{ fontSize: 13, color: "#3d4856" }}>{t}</li>
              ))}
            </ul>
          )}
        </div>
      )}
    </section>
  );
}
