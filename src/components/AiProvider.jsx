import { useEffect, useState } from "react";
import { api } from "../api.js";

// Choose which AI model the app uses: Ollama (free, local) or an
// OpenAI-compatible API (DeepSeek, or any "bring your own" endpoint).
// The API key is stored by the desktop app in the OS keychain — never here.
export default function AiProvider() {
  const [config, setConfig] = useState(null); // {provider, model, base_url, has_key}
  const [hasKey, setHasKey] = useState(false);
  const [provider, setProvider] = useState("ollama");
  const [model, setModel] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [key, setKey] = useState("");
  const [status, setStatus] = useState("idle"); // idle | saving | saved
  const [error, setError] = useState(null);

  async function load() {
    try {
      const c = await api.get("/api/ai/config");
      setConfig(c);
      setProvider(c.provider || "ollama");
      setModel(c.model || "");
      setBaseUrl(c.base_url || "");
      if (window.copilot?.getAiKey) {
        const k = await window.copilot.getAiKey();
        setHasKey(!!(k && k.hasKey));
      }
    } catch (e) {
      setError(e.message);
    }
  }
  useEffect(() => {
    load();
  }, []);

  async function save() {
    setStatus("saving");
    setError(null);
    try {
      await api.put("/api/ai/config", {
        provider,
        model: provider === "ollama" ? "" : model,
        base_url: provider === "custom" ? baseUrl : "",
      });
      const keyVal = key.trim();
      if (keyVal && window.copilot?.setAiKey) {
        const r = await window.copilot.setAiKey(keyVal);
        if (r && !r.ok) throw new Error(r.error || "Could not save the key");
        setKey("");
      }
      setStatus("saved");
      await load();
      setTimeout(() => setStatus("idle"), 2000);
    } catch (e) {
      setError(e.message);
      setStatus("idle");
    }
  }

  async function removeKey() {
    if (!window.confirm("Remove the saved API key from this device?")) return;
    if (window.copilot?.setAiKey) {
      const r = await window.copilot.setAiKey("");
      if (r && !r.ok) {
        setError(r.error || "Could not remove the key");
        return;
      }
      setHasKey(false);
      await load();
    }
  }

  const remote = provider !== "ollama";

  return (
    <div className="panel" style={{ marginBottom: 18 }}>
      <div className="panel-head">
        <h2>AI model</h2>
        <span className="filter-count mono">
          {config ? (config.provider === "ollama" ? "Ollama" : config.provider) : "…"}
        </span>
      </div>
      <p className="empty-hint" style={{ marginTop: 0 }}>
        Used for resume reading and CV writing. Ollama is free and stays on your
        device; DeepSeek (or any OpenAI-compatible API) works anywhere but needs
        your own key.
      </p>

      <label className="field" style={{ maxWidth: 420 }}>
        <span className="field-label">Provider</span>
        <select value={provider} onChange={(e) => setProvider(e.target.value)}>
          <option value="ollama">Ollama — free, on this device</option>
          <option value="deepseek">DeepSeek — paid, needs an API key</option>
          <option value="custom">Custom API — bring your own model</option>
        </select>
      </label>

      {remote && (
        <>
          <label className="field" style={{ maxWidth: 420, marginTop: 12 }}>
            <span className="field-label">Model name</span>
            <input
              className="mono"
              value={model}
              placeholder={provider === "deepseek" ? "deepseek-chat" : "e.g. gpt-4o-mini"}
              onChange={(e) => setModel(e.target.value)}
            />
          </label>

          {provider === "custom" && (
            <label className="field" style={{ maxWidth: 420, marginTop: 12 }}>
              <span className="field-label">Base URL (OpenAI-compatible)</span>
              <input
                className="mono"
                value={baseUrl}
                placeholder="https://api.openai.com"
                onChange={(e) => setBaseUrl(e.target.value)}
              />
            </label>
          )}

          <label className="field" style={{ maxWidth: 420, marginTop: 12 }}>
            <span className="field-label">API key</span>
            <input
              type="password"
              value={key}
              placeholder={hasKey ? "•••••••• (a key is saved)" : "Paste your API key"}
              onChange={(e) => setKey(e.target.value)}
              autoComplete="off"
            />
            <span className="empty-hint" style={{ padding: 0 }}>
              {hasKey
                ? "A key is saved securely on this device. Type a new one to replace it."
                : "Saved only on this device, encrypted by your operating system. Never stored in the app files or GitHub."}
            </span>
          </label>

          {hasKey && (
            <div className="form-actions" style={{ marginTop: 6 }}>
              <button className="link-btn danger" onClick={removeKey} type="button">
                Remove saved key
              </button>
            </div>
          )}
        </>
      )}

      <div className="panel-actions">
        <button onClick={save} disabled={status === "saving"}>
          {status === "saving" ? "Saving…" : status === "saved" ? "Saved" : "Save AI model"}
        </button>
        {error && <span className="error-text">{error}</span>}
      </div>
    </div>
  );
}
