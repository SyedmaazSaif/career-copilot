# Set up career-copilot with an AI assistant

This guide is for **anyone, technical or not.** You will not have to understand
any code. The plan is simple: you install two free tools, then let an AI
assistant do the setup for you by pasting in one prompt.

Total time: about 20 minutes, most of it waiting for downloads.

---

## What you'll end up with

A desktop app on your own computer that finds jobs, scores them against your
experience, and lets you track and apply to them — all in one window, for free.

---

## Step 1 — Install two free tools

You only need these two. Click, download, run the installer, click Next until
it's done.

1. **Node.js** — <https://nodejs.org> (download the button that says "LTS").
2. **Python** — <https://python.org/downloads> (click the big yellow "Download"
   button).
   - **Windows users:** on the first screen of the Python installer, tick the
     box that says **"Add Python to PATH"** before clicking Install. This matters.

You do not need to open these after installing. They just need to be on your
computer.

---

## Step 2 — Get an AI assistant that can use your files

The easiest is **Claude Code** (a free-to-try coding assistant from Anthropic):
<https://claude.com/claude-code>. Install it and sign in.

(If you already use another AI coding tool that can read and run files in a
folder — Cursor, GitHub Copilot in VS Code, etc. — that works too.)

---

## Step 3 — Download this project

- On the project's web page, click the green **Code** button, then
  **Download ZIP**.
- Unzip it somewhere easy to find, like your Desktop. You'll get a folder called
  `career-copilot`.

---

## Step 4 — Set it up

**Simplest (Windows):** open the `career-copilot` folder and **double-click
`setup.bat`**. It checks for Node and Python (and installs them for you if your
Windows has the App Installer), installs everything the app needs, and starts it.
The first run takes a few minutes. That's it — skip to Step 5.

If you would rather have an AI do it, or you are on a Mac, use the prompt below.

### Or: let the AI set it up

Open the `career-copilot` folder in your AI assistant. In Claude Code, you do
this by opening a terminal in that folder and typing `claude`, or by using its
"open folder" option.

Now **copy the whole prompt below and paste it in.** Then press Enter and let it
work. It will install everything and start the app.

```
You are setting up an app called career-copilot on my computer for me. I am not
technical, so please do each step yourself and keep me informed in plain words.

1. Check that Node.js and Python are installed (node --version, python --version).
   If either is missing, stop and tell me which one to install.
2. In this folder, run: npm install
3. Create a Python virtual environment in backend/.venv and install the backend
   requirements from backend/requirements.txt into it. Use the venv's own python
   for the install (backend/.venv/Scripts/python on Windows,
   backend/.venv/bin/python on macOS).
4. If installing Electron leaves its binary missing (a common Windows hiccup),
   fix it so `npm run dev` works.
5. Start the app with: npm run dev
6. Tell me when the app window opens, then stop and wait. Do not change any of
   the app's code or features — only set it up and run it.
```

When it's finished, the career-copilot window opens on your screen.

---

## Step 5 — Put in your details

The app only ever uses facts you give it. It never makes anything up.

- **Easiest: upload your resume.** In the **Profile** tab click **Upload resume**,
  pick your PDF or Word file, review what it read, and click Apply. (Reading the
  full experience section works best with the optional local AI turned on — see
  Step 7 below. Without it, your contact details and summary are filled and you
  add the rest by hand.)
- **Or fill it in by hand** in the Profile tab.
- **Or use the template:** copy `master_profile.example.yaml` to
  `master_profile.yaml`, edit it in a text editor, and click **Import from YAML**.

Your details are saved only on your computer.

---

## Step 6 — Find and track jobs

1. Click the **Settings** tab. Adjust the job titles you want to search for and
   turn job boards on or off. Save.
2. Click the **Jobs** tab, then **Scan now**. The first scan takes a few minutes.
3. Each job shows a **match score**. Click one to read the full details and see
   why it scored that way.
4. Drag jobs you like into the **Applied** column, and click
   **Open listing to apply** to open the real posting inside the app and apply.

---

## Step 7 (optional) — turn on the free local AI

The app works without this. But a free local AI makes resume reading and CV
writing much better, and it stays completely private on your computer.

**Easiest:** open the **Settings** tab in the app and click **"Set up local AI"**.
It installs Ollama, downloads the AI model, and turns it on for you, showing each
step. It is a one-time, roughly 4 GB download and needs a reasonably capable
computer. (Automatic install is Windows-only; on a Mac, install Ollama from
<https://ollama.com> first, then click the button.)

The Settings tab always shows whether the local AI is on and ready.

## Using it day to day

- To open the app again later:
  - **Windows:** double-click **`career-copilot.vbs`** in the project folder.
  - **Or** open the folder in your AI assistant and say "start the app".
- It re-scans automatically once a day while it's open, and any time you hit
  **Scan now**.
- To stop it, just close the app window.

---

## If something goes wrong

Paste the problem to your AI assistant — it can read the error and fix it. A few
common ones:

- **"node is not recognized" / "python is not recognized":** the tool from
  Step 1 didn't install correctly. Re-run its installer (Windows Python users:
  tick "Add Python to PATH").
- **The window doesn't open:** tell your AI "npm run dev didn't open a window,
  please check the logs and fix it."
- **A scan finds nothing:** some boards rate-limit or block scraping on some
  days. Open Settings, make sure several boards are on, and try again later.

---

## Good to know

- It's free. No subscription, no API key, no account.
- It runs entirely on your computer. Your profile and saved jobs never leave it.
- It never applies for you. You always click apply yourself.
