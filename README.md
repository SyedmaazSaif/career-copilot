# Career Copilot — Free AI Job Search Assistant & Application Tracker

**Career Copilot is a free job search app for job seekers.** It runs
your whole job hunt from one desktop window: it scans job boards daily, scores
every role against your resume, generates tailored ATS-friendly CVs, and tracks
your job applications through a drag-and-drop Kanban pipeline — with a built-in
browser so you apply without ever leaving the app.

Think of it as a private, local alternative to a job application tracker,
resume/CV builder, and applicant tracking system rolled into one. Everything runs
on your own computer. There is **no paid API, no subscription, and no account to
create.** Your data never leaves your machine.

**Keywords:** job search, job hunt, job application tracker, resume builder, CV
generator, ATS resume, AI job search assistant, remote jobs, applicant tracking
system, job board aggregator.

> **Just want to install it?** See **[INSTALL.md](INSTALL.md)** for step-by-step
> Windows and macOS instructions. Prefer to let an AI do the whole setup? See
> **[SETUP_WITH_AI.md](SETUP_WITH_AI.md)**.

---

## What it does

**Jobs**
- Scans 9 free job boards (Remotive, We Work Remotely, Himalayas, RemoteOK,
  Arbeitnow, LinkedIn, Hiring.cafe, Wellfound, Remote.co) on demand and daily.
- Add your own sources too: any RSS feed, a Greenhouse or Lever company board, or
  a single job by pasting its URL.
- Scores every job 0–100 against your profile — skills, seniority, work
  arrangement, visa-friendliness, and domain overlap — shown as a small "match
  meter" gauge. Each score explains itself.
- Classifies each job as remote / hybrid / on-site and full-time / contract, with
  filters for both. Not remote-only.
- De-duplicates the same role posted to several boards, and flags red flags.
- A Kanban pipeline (Sourced → Applied → Screening → Interview → Offer → Closed)
  with draggable cards, a filterable jobs table, and an analytics tab.

**Tailored CV**
- Generate an ATS-friendly Word CV for any job, built from your profile facts
  only, ordered and reworded for that role. A verification pass flags anything
  not traceable to your profile. With the optional local AI on, the wording is
  smarter; without it, your original wording is kept.

**Apply from inside the app**
- Click "Open listing to apply" and the job opens in a browser window built into
  the app, with back / forward / reload and an "open in your normal browser"
  button. You apply yourself; the app never submits anything for you.

**Your profile, your rules**
- A built-in editor for your experience, skills, education, certifications, and
  job-search preferences — or **upload your resume (PDF/DOCX)** and it fills the
  profile for you. This profile is the single source of truth. The app only ever
  uses facts you entered — it never invents anything.

**Settings**
- Edit which job titles/keywords to search, which boards are on, your preferred
  work arrangements, and add your own job sources.

## Optional free local AI (Ollama)

Resume parsing and CV wording are smarter with a local AI model, and it stays
free and private. The easiest way to turn it on: open **Settings** in the app and
click **"Set up local AI"** — it installs Ollama, downloads the model, and enables
it, showing each step (a one-time ~4 GB download; automatic install is
Windows-only).

Prefer to do it yourself? Install Ollama (<https://ollama.com>), run
`ollama pull llama3.1`, and set `OLLAMA_ENABLED=true` in `.env`.

The app works fully without this — it just falls back to a simpler built-in
method. No paid API is ever called either way.

---

## How it works (under the hood)

```
Electron desktop window
   ├─ React front end (the UI you see)
   └─ Python FastAPI backend (started automatically, stopped on quit)
         └─ SQLite database (one file on your disk: your profile + jobs)
```

- **Front end:** Electron + React (Vite).
- **Back end:** a local Python FastAPI server that Electron launches on start and
  shuts down on quit. It does the scanning, scoring, and storage.
- **Data:** a single SQLite file at `backend/data/career_copilot.db`. It never
  leaves your computer and is never committed to git.
- **Scanning:** reuses a set of board scrapers (`backend/fetch_jobs_vendored.py`)
  that need no API keys.

There is an optional, off-by-default hook for a local AI model (Ollama) for
nicer wording later. Nothing requires it, and no paid AI service is ever called.

---

## Requirements

- **Node.js** 18 or newer — <https://nodejs.org>
- **Python** 3.10 or newer — <https://python.org>
- Windows or macOS. (These are the only two things you install; the app handles
  the rest.)

---

## Install and run

The friendly, guided version is in **[SETUP_WITH_AI.md](SETUP_WITH_AI.md)**. The
short technical version:

```bash
# 1. Front-end dependencies
npm install

# 2. Back-end: create a Python virtual environment and install into it
python -m venv backend/.venv
# Windows:
backend/.venv/Scripts/python -m pip install -r backend/requirements.txt
# macOS/Linux:
backend/.venv/bin/python -m pip install -r backend/requirements.txt

# 3. Start everything (Electron + React + Python together)
npm run dev
```

**Even simpler on Windows:** double-click **`setup.bat`** — it checks for Node and
Python (installing them via winget if missing), installs everything, and starts
the app. After the first run, launch anytime by double-clicking
**`career-copilot.vbs`** (no console window).

### First run
1. Open the **Profile** tab and fill in your details, or copy
   `master_profile.example.yaml` to `master_profile.yaml`, edit it, and click
   **Import from YAML**.
2. Open **Settings** and adjust the search terms and boards if you like.
3. Open **Jobs** and click **Scan now**. The first scan takes a few minutes.
4. Drag roles you like into **Applied** and open each one to apply.

---

## Your privacy

- Your profile and scanned jobs live only in `backend/data/` on your computer.
- Secrets live in `.env` (git-ignored).
- Your real `master_profile.yaml` is git-ignored. Only the fake
  `master_profile.example.yaml` template is shared.
- If you fork or publish this, do not commit those files. The included
  `.gitignore` already excludes them.

---

## License

Personal-use license — see [LICENSE](LICENSE). You can download it, run it, and
make your own version for your own job search. Please don't sell it.

---

## Roadmap

Built: profile editor with resume upload, job scanning + scoring + CRM,
configurable search and custom sources, work-arrangement filters, an in-app apply
browser, and a tailored ATS CV generator. Planned: cover letters and screener
answers, built the same profile-facts-only way.
