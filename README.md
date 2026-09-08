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

> **Just want to install it?** Jump to **[Install](#install)** below, or see
> **[INSTALL.md](INSTALL.md)** for the same thing with every step spelled out
> and a troubleshooting section. Prefer to let an AI do the whole setup? See
> **[SETUP_WITH_AI.md](SETUP_WITH_AI.md)**.

---

## What it does

**Jobs**
- Scans 10 free job boards (Remotive, We Work Remotely, Himalayas, RemoteOK,
  Arbeitnow, LinkedIn, Hiring.cafe, Wellfound, Remote.co, Mustakbil) on demand
  and daily.
- Add your own sources too: any RSS feed, a Greenhouse or Lever company board, or
  a single job by pasting its URL.
- **Real location search.** Boards that filter by location natively (LinkedIn,
  and Mustakbil for Pakistan) are searched once per location you configure, on
  top of the default global pass — so on-site roles in Islamabad, Karachi,
  Lahore or anywhere else actually show up. The remote-only boards are searched
  globally, which also makes scans considerably faster.
- Scores every job 0–100 against your profile — skills, seniority, work
  arrangement, visa-friendliness, and domain overlap — shown as a small "match
  meter" gauge. Each score explains itself. A role where you already live is not
  penalised for "requires being based in…".
- Classifies each job as remote / hybrid / on-site and full-time / contract, with
  filters for both. Not remote-only.
- **See what's new.** Every job first found by the latest scan is badged "NEW" on
  the board and in the table. The post-scan banner's "N new" is a link straight
  to them, and the table can filter to new-only or sort by newest first.
- **Remove jobs you don't qualify for**, from the table, a card, or the job
  window. Removed jobs are blocklisted, so the next scan cannot resurrect them —
  and Settings lists them with an Undo if you change your mind.
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
- Every job shows its **application links** as plain, selectable text you can
  copy, or open in your real browser (handy when a board paywalls the listing but
  you are signed in elsewhere). "Find company site" looks up the employer's own
  careers page — following the listing's redirects to its ATS (Greenhouse, Lever,
  Workable, Ashby, BambooHR, SmartRecruiters), or searching for it — and you can
  paste or correct the link yourself whenever the guess is off.

**Your profile, your rules**
- A built-in editor for your experience, skills, education, certifications, and
  job-search preferences — or **upload your resume (PDF/DOCX)** and it fills the
  profile for you. This profile is the single source of truth. The app only ever
  uses facts you entered — it never invents anything.

**Settings**
- Edit which job titles/keywords to search, which locations to search in, which
  boards are on, your preferred work arrangements, and add your own job sources.
- Review the jobs you removed, and undo any of them.

## Optional free local AI (Ollama)

Resume parsing and CV wording are smarter with a local AI model, and it stays
free and private. **The installer offers it during setup** — it reads your
computer's memory and graphics, tells you which model it can actually run and
what a larger one would do, and installs it only if you say yes. You can also
turn it on at any time afterwards: open **Settings** in the app and click
**"Set up local AI"**, which runs the identical steps. Automatic install covers
Windows and macOS.

Prefer to do it yourself? Install Ollama (<https://ollama.com>), run
`ollama pull llama3.2:1b`, and set `OLLAMA_ENABLED=true` in `.env`.

The default model is deliberately small so it runs on a laptop with 8 GB of RAM
and no dedicated GPU. A bigger model (`llama3.1`, say) reads a resume more
accurately, but only pick one that fits in the RAM you have free — once Ollama
has to page the model to disk it slows by a factor of ~100 and every request
times out. Set `OLLAMA_MODEL` in `.env` to change it.

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

- Windows 10/11, or macOS on Intel or Apple Silicon.
- About 2 GB of free disk space, plus 1–5 GB more if you choose the local AI.
- Node.js 18+ and Python 3.10+ — **the installer installs these for you if they
  are missing.** You do not need to install anything yourself first.

---

## Install

One installer per system. It downloads the app, installs everything it needs —
**including Node.js and Python if your computer does not have them** — offers
the optional local AI, and starts the app. You are never sent to another website
to install something by hand, and on macOS it never asks for your password.

### Windows

1. Download **[Install-Career-Copilot-Windows.zip](https://github.com/SyedmaazSaif/career-copilot/raw/main/Install-Career-Copilot-Windows.zip)**.
2. Open the zip and double-click **Install Career Copilot** inside it.
3. If Windows says *"Windows protected your PC"*, click **More info** →
   **Run anyway**. That warning is about the file being downloaded, not
   about this file.

It installs to `C:\Users\<you>\career-copilot` and puts a **career-copilot**
shortcut on your Desktop. Launch it from there next time.

### macOS

1. Download **[Install-Career-Copilot-Mac.zip](https://github.com/SyedmaazSaif/career-copilot/raw/main/Install-Career-Copilot-Mac.zip)**.
2. Open the zip. **Right-click** the **Install Career Copilot** file inside
   and choose **Open**, then **Open** again.
3. A Terminal window opens and shows each step.

**Right-click → Open, not double-click** — a plain double-click is refused
the first time with *"cannot be opened"* or *"will damage your computer"*.
macOS flags everything a browser downloads, and clearing that warning for
good requires a paid Apple Developer account to sign and notarise the app.
You only do the right-click once.

It installs to `~/career-copilot`. Launch it next time by double-clicking
`career-copilot.command` in that folder — no warning, the installer clears
it. Prefer the Terminal? One line, no warning at all:
`curl -fsSL https://raw.githubusercontent.com/SyedmaazSaif/career-copilot/main/install-macos.sh | bash`

### Running from source instead

```bash
npm install                                                   # front end
python -m venv backend/.venv                                  # back end
backend/.venv/Scripts/python -m pip install -r backend/requirements.txt   # Windows
backend/.venv/bin/python -m pip install -r backend/requirements.txt       # macOS
npm run dev                                                   # start everything
```

Or double-click `setup.bat` (Windows) / `setup.command` (macOS) in a copy of the
repo, which does all of the above plus the local-AI offer.

### First run
1. Open the **Profile** tab and click **Upload resume**, or fill in your details
   by hand — or copy `master_profile.example.yaml` to `master_profile.yaml`,
   edit it, and click **Import from YAML**.
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
