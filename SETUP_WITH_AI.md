# Set up career-copilot with an AI assistant

This guide is for **anyone, technical or not.** You will not have to understand
any code.

> **Most people do not need this page.** The installer in
> **[INSTALL.md](INSTALL.md)** is one file to double-click on Windows, or one
> line to paste on macOS, and it installs everything on its own — Node, Python
> and all. Come back here if that fails and you would like an AI assistant to
> work out why, or if you simply prefer being walked through it.

Total time: about 20 minutes, most of it waiting for downloads.

---

## What you'll end up with

A desktop app on your own computer that finds jobs, scores them against your
experience, and lets you track and apply to them — all in one window, for free.

---

## Step 1 — Try the installer first

It is genuinely one step, and it installs Node and Python for you if you do not
have them:

- **Windows:** download
  [Install-Career-Copilot-Windows.zip](https://github.com/SyedmaazSaif/career-copilot/raw/main/Install-Career-Copilot-Windows.zip),
  open it, and double-click **Install Career Copilot** inside.
- **macOS:** download
  [Install-Career-Copilot-Mac.zip](https://github.com/SyedmaazSaif/career-copilot/raw/main/Install-Career-Copilot-Mac.zip),
  open it, then **right-click** **Install Career Copilot** inside and choose
  **Open** → **Open**. (Right-click, not double-click — macOS blocks a
  downloaded program until you confirm once.)

If the app window opens, you are done — **skip to Step 5**. If something goes
wrong, carry on below and let an AI assistant sort it out.

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

**Simplest:** open the `career-copilot` folder and double-click **`setup.bat`**
(Windows) or **`setup.command`** (macOS). It installs Node and Python if they
are missing, installs everything the app needs, offers the optional local AI,
and starts the app. The first run takes a few minutes. That's it — skip to
Step 5.

On macOS, if double-clicking `setup.command` is refused, **right-click it →
Open → Open**. macOS blocks downloaded scripts until you say so once.

### Or: let the AI set it up

Open the `career-copilot` folder in your AI assistant. In Claude Code, you do
this by opening a terminal in that folder and typing `claude`, or by using its
"open folder" option.

Now **copy the whole prompt below and paste it in.** Then press Enter and let it
work. It will install everything and start the app.

```
You are setting up an app called career-copilot on my computer for me. I am not
technical, so please do each step yourself and keep me informed in plain words.

1. Run the setup script in this folder: setup.bat on Windows, or
   `bash setup.command` on macOS. It handles Node, Python, the app's libraries,
   and the optional local AI. If it finishes and the app window opens, stop
   there and tell me.
2. If it fails, tell me in plain words what failed, then do the steps yourself:
   check node --version and python3 --version; run npm install; create a Python
   virtual environment in backend/.venv and install backend/requirements.txt
   into it using the venv's own python (backend/.venv/Scripts/python on
   Windows, backend/.venv/bin/python on macOS).
3. If installing Electron leaves its binary missing (a common Windows hiccup),
   fix it so `npm run dev` works.
4. Start the app with: npm run dev
5. Tell me when the app window opens, then stop and wait. Do not change any of
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

**The installer already asked you about this** during setup. If you said yes, it
is on and there is nothing to do here.

If you said no, or want it now: open the **Settings** tab in the app and click
**"Set up local AI"**. It installs Ollama, downloads the AI model, and turns it
on, showing each step. Either way it first checks your computer's memory and
graphics and tells you which model actually fits — a one-time download between
roughly 1 GB and 5 GB depending on what your machine can run. Automatic install
covers Windows and macOS.

The Settings tab always shows whether the local AI is on and ready.

## Using it day to day

- To open the app again later:
  - **Windows:** double-click **`career-copilot.vbs`** in the project folder,
    or the **career-copilot** shortcut the installer put on your Desktop.
  - **macOS:** double-click **`career-copilot.command`** in the project folder.
  - **Or** open the folder in your AI assistant and say "start the app".
- It re-scans automatically once a day while it's open, and any time you hit
  **Scan now**.
- To stop it, just close the app window.

---

## If something goes wrong

Paste the problem to your AI assistant — it can read the error and fix it. A few
common ones:

- **"node is not recognized" / "python is not recognized":** close the window
  and run the setup script once more. Windows sometimes needs a fresh window to
  notice a program it just installed.
- **macOS says a file "cannot be opened" or "will damage your computer":**
  that is Gatekeeper blocking a downloaded script, not a real warning about the
  file. Right-click it → **Open** → **Open**, or use the one-line Terminal
  install in [INSTALL.md](INSTALL.md), which avoids it entirely.
- **The window doesn't open:** tell your AI "npm run dev didn't open a window,
  please check the logs and fix it."
- **A scan finds nothing:** some boards rate-limit or block scraping on some
  days. Open Settings, make sure several boards are on, and try again later.

---

## Good to know

- It's free. No subscription, no API key, no account.
- It runs entirely on your computer. Your profile and saved jobs never leave it.
- It never applies for you. You always click apply yourself.
