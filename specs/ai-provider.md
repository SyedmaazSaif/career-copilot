# AI provider choice (Ollama vs DeepSeek / bring-your-own)

## Goal

Let the user (and anyone who installs from GitHub) pick which AI model the app
uses for resume parsing and CV writing:

- **Ollama** — free, local, no key (the current behaviour).
- **DeepSeek** — paid but cheap, needs an API key, works on any machine.
- **Custom (OpenAI-compatible)** — any "bring your own" endpoint (OpenRouter,
  Groq, a self-hosted vLLM, …) with a base URL + model name.

## Security

- The API key is **never** stored in code, `.env`, the database, git, or logs.
- Electron stores it with `safeStorage` (macOS Keychain / Windows DPAPI) — the
  same mechanism already used for website passwords — and passes it to the
  backend only as an in-memory environment variable at startup.
- Non-secret config (provider, model, base URL) is written to the git-ignored
  `.env`, like the existing Ollama settings.

## Changes

1. `backend/deepseek_client.py` — OpenAI-compatible chat completions client.
2. `backend/llm.py` — unified entry point that dispatches to Ollama or the
   remote client; `resume.py` and `cv_generator.py` switch to it.
3. `backend/envfile.py` — shared helper to write non-secret config to `.env`.
4. `backend/routers/ai.py` — `GET/PUT /api/ai/config`; `/status` reports the
   active provider.
5. Settings UI — an "AI model" section to choose provider, model, base URL and
   paste the key (saved via Electron, never shown back).
6. Electron — store/read the key via `safeStorage`, inject it into the backend
   process environment, restart the backend when the key changes.

## Not in scope

- The resume chat/editor tab (a later task).
- On-site/hybrid job sources + country filter (a later task).

## Ideas for later

- Per-feature model choice (e.g. DeepSeek for CV review, Ollama for parsing).
- Show token spend / limits in Settings.
