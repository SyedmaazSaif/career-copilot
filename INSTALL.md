# Install career-copilot

Pick your system below. Either way you install two free tools once (Node.js and
Python), then a single script sets up and starts the app.

Not comfortable with any of this? See **[SETUP_WITH_AI.md](SETUP_WITH_AI.md)** —
it lets an AI assistant do the whole setup for you.

---

## Windows

1. **Install Node.js** — <https://nodejs.org> (click the "LTS" download, run it,
   click Next through the installer).
2. **Install Python** — <https://python.org/downloads> (click the yellow
   "Download" button). **On the first screen, tick "Add Python to PATH"** before
   installing.
3. **Get the app** — on the project page, click the green **Code** button →
   **Download ZIP**, and unzip it (e.g. to your Desktop).
4. **Run setup** — open the `career-copilot` folder and **double-click
   `setup.bat`**. It installs everything and starts the app. The first run takes
   a few minutes.
   - On Windows 11, if Node or Python are missing, `setup.bat` can install them
     for you and will ask you to run it once more.
5. **Later launches** — double-click **`career-copilot.vbs`** (opens the app with
   no black console window).

---

## macOS

1. **Install Node.js** — <https://nodejs.org> (the "LTS" download). Or, if you
   have Homebrew: `brew install node`.
2. **Install Python 3** — <https://python.org/downloads>. Or with Homebrew:
   `brew install python`.
3. **Get the app** — on the project page, click the green **Code** button →
   **Download ZIP**, and unzip it.
4. **Run setup** — in the `career-copilot` folder, **double-click
   `setup.command`**. (If macOS blocks it the first time: right-click the file →
   **Open** → **Open**, or run `chmod +x setup.command` in Terminal once.) It
   installs everything and starts the app.
5. **Later launches** — run `setup.command` again, or in Terminal from the folder
   run `npm run dev`.

---

## First time in the app (both systems)

1. **Profile** — click **Upload resume** and pick your PDF or Word file, or fill
   it in by hand. This is the only source of facts the app uses; it never invents
   anything.
2. **Settings** — adjust the job titles to search, which boards are on, and your
   preferred work arrangements. You can also add your own job sources.
3. **Jobs** — click **Scan now** (the first scan takes a few minutes). Each job
   gets a match score. Open one to see details, generate a tailored CV, and click
   **Open listing to apply** to apply from inside the app.

## Optional: free local AI

In **Settings**, click **Set up local AI**. It installs Ollama, downloads the AI
model, and turns it on, showing each step. This makes resume reading and CV
wording smarter and stays free and private on your computer. Automatic install is
Windows-only; on macOS, install Ollama from <https://ollama.com> first, then click
the button. The app works fully without this.

## Requirements

- Node.js 18+ and Python 3.10+.
- A few GB of free disk space (more if you use the optional local AI model).
- Everything runs locally. No account, no paid API, no data leaves your computer.
