import { useState } from "react";
import { api } from "../api.js";
import PersonalSection from "./PersonalSection.jsx";
import ExperienceSection from "./ExperienceSection.jsx";
import FlatSection from "./FlatSection.jsx";
import ResumeUpload from "./ResumeUpload.jsx";

const SECTIONS = [
  { id: "personal", label: "Personal" },
  { id: "experience", label: "Experience" },
  { id: "skills", label: "Skills" },
  { id: "education", label: "Education" },
  { id: "certifications", label: "Certifications" },
  { id: "languages", label: "Languages" },
];

export default function ProfilePage() {
  const [section, setSection] = useState("personal");
  const [importing, setImporting] = useState(false);
  const [importMsg, setImportMsg] = useState(null);
  const [reloadKey, setReloadKey] = useState(0);

  async function runImport() {
    if (
      !window.confirm(
        "Import from master_profile.yaml? This replaces all current profile records with the file's contents."
      )
    )
      return;
    setImporting(true);
    setImportMsg(null);
    try {
      const r = await api.post("/api/import/yaml", {});
      setImportMsg(
        `Imported ${r.experiences} roles, ${r.bullets} bullets, ${r.skills} skills, ${r.education} education, ${r.certifications} certifications, ${r.languages} languages.`
      );
      setReloadKey((k) => k + 1); // force sections to refetch
    } catch (err) {
      setImportMsg(`Import failed: ${err.message}`);
    } finally {
      setImporting(false);
    }
  }

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <h1>Profile</h1>
          <p className="page-sub">
            The single source of truth. Every CV, cover letter, and screener answer is
            built only from what lives here. Nothing is ever invented.
          </p>
        </div>
        <div className="head-actions">
          <ResumeUpload onApplied={() => setReloadKey((k) => k + 1)} />
          <button className="btn-secondary" onClick={runImport} disabled={importing}>
            {importing ? "Importing…" : "Import from YAML"}
          </button>
        </div>
      </header>

      {importMsg && <div className="banner">{importMsg}</div>}

      <div className="section-tabs">
        {SECTIONS.map((s) => (
          <button
            key={s.id}
            className={`tab ${section === s.id ? "active" : ""}`}
            onClick={() => setSection(s.id)}
          >
            {s.label}
          </button>
        ))}
      </div>

      <div className="section-body" key={`${section}-${reloadKey}`}>
        {section === "personal" && <PersonalSection />}
        {section === "experience" && <ExperienceSection />}
        {section === "skills" && (
          <FlatSection
            title="Skills"
            endpoint="/api/skills"
            groupBy="category"
            emptyHint="Add the skills you can honestly claim, grouped by category, each with a proficiency."
            fields={[
              { name: "name", label: "Skill", type: "text", required: true },
              { name: "category", label: "Category", type: "text" },
              {
                name: "proficiency",
                label: "Proficiency",
                type: "select",
                options: ["Expert", "Proficient", "Familiar", "Beginner"],
                mono: true,
              },
            ]}
            renderTitle={(r) => r.name}
            renderMeta={(r) => r.proficiency}
          />
        )}
        {section === "education" && (
          <FlatSection
            title="Education"
            endpoint="/api/education"
            emptyHint="Add each qualification."
            fields={[
              { name: "degree", label: "Degree", type: "text", required: true },
              { name: "school", label: "School", type: "text" },
              { name: "location", label: "Location", type: "text" },
              { name: "dates", label: "Dates", type: "text", mono: true },
            ]}
            renderTitle={(r) => r.degree}
            renderMeta={(r) => [r.school, r.dates].filter(Boolean).join(" · ")}
          />
        )}
        {section === "certifications" && (
          <FlatSection
            title="Certifications"
            endpoint="/api/certifications"
            emptyHint="Add each certification you hold."
            fields={[
              { name: "name", label: "Certification", type: "text", required: true },
              { name: "issuer", label: "Issuer", type: "text" },
              { name: "date", label: "Date", type: "text", mono: true },
            ]}
            renderTitle={(r) => r.name}
            renderMeta={(r) => [r.issuer, r.date].filter(Boolean).join(" · ")}
          />
        )}
        {section === "languages" && (
          <FlatSection
            title="Languages"
            endpoint="/api/languages"
            emptyHint="Add each language and how well you speak it."
            fields={[
              { name: "name", label: "Language", type: "text", required: true },
              {
                name: "proficiency",
                label: "Proficiency",
                type: "select",
                options: ["Native", "Professional", "Conversational", "Basic"],
                mono: true,
              },
            ]}
            renderTitle={(r) => r.name}
            renderMeta={(r) => r.proficiency}
          />
        )}
      </div>
    </div>
  );
}
