# Install career-copilot

One installer per system. It downloads the app, installs everything the app
needs — **including Node.js and Python, if your computer does not have them** —
offers the optional local AI, and starts the app. You are never sent to another
website to install something by hand.

Jump to: **[Windows](#windows)** · **[macOS](#macos)** ·
**[Starting the app](#starting-the-app)** ·
**[First run](#first-time-in-the-app-both-systems)** ·
**[If something goes wrong](#if-something-goes-wrong)**

> **One window, not two.** The installer shows its progress in a Terminal or
> console window, because an install that takes minutes in silence looks
> broken. After that, starting the app opens the app window and nothing else —
> no Terminal on macOS, no console or PowerShell on Windows. Everything the app
> would have printed goes to a log file instead.

> **Why two downloads and not one?** Windows and macOS will not run each
> other's programs, so there is no single file both can open — the same
> reason apps ship a Windows download and a Mac download separately. Both
> installers below do exactly the same thing.

---

## Windows

**1. Download the installer:**
[**Install-Career-Copilot-Windows.zip**](https://github.com/SyedmaazSaif/career-copilot/raw/main/installer/Install-Career-Copilot-Windows.zip)

**2. Open the downloaded zip** and double-click **Install Career Copilot**
inside it.

**3. If Windows says "Windows protected your PC"**, click **More info**, then
**Run anyway**. That warning appears for every file downloaded from the
internet that Microsoft has not been paid to certify; it is not about this
file specifically.

**4. Wait.** A black window shows each step. The first install takes a few
minutes — it is downloading Node, Python, and the app's libraries. The app
window opens on its own when it finishes.

That is the whole install. It puts the app in `C:\Users\<you>\career-copilot`
and creates a **career-copilot** shortcut on your Desktop.

**Later launches:** double-click the **career-copilot** shortcut on your
Desktop, or `career-copilot.vbs` in the app folder. Nothing appears except the
app window — no console, no PowerShell.

---

## macOS

**1. Download the installer:**
[**Install-Career-Copilot-Mac.zip**](https://github.com/SyedmaazSaif/career-copilot/raw/main/installer/Install-Career-Copilot-Mac.zip)

**2. Open the downloaded zip** (double-click it, if your browser has not
already unzipped it). You get a file called **Install Career Copilot**.

**3. Right-click that file and choose Open.** Then click **Open** again in the
box that appears.

> **Right-click → Open, not double-click.** This one matters. A plain
> double-click gets refused the first time, with *"cannot be opened because it
> is from an unidentified developer"* or *"will damage your computer"*.
> Right-clicking and choosing **Open** gives you the same box with an **Open**
> button on it. You only do this once, ever.
>
> On macOS Sequoia (15) and newer, if there is no Open button: go to
> **System Settings → Privacy & Security**, scroll down to the message about
> the blocked file, and click **Open Anyway**.

**4. Wait.** A Terminal window opens and shows each step. The first install
takes a few minutes. The app window opens on its own when it finishes.

That is the whole install. It puts the app in `~/career-copilot` and creates
**Career Copilot.app** inside that folder, plus a copy in Applications.

**Later launches:** open **Career Copilot** from Launchpad or Spotlight, or
double-click **`Career Copilot.app`** in the `career-copilot` folder in your
home directory. No warning this time — the installer clears it for you — and no
Terminal window: the app window is the only thing that opens.

Once setup has finished you can close its Terminal window. The app keeps
running; it is not tied to that window.

### Or, if you prefer the Terminal

One line, no download and no security warning at all:

```bash
curl -fsSL https://raw.githubusercontent.com/SyedmaazSaif/career-copilot/main/installer/install-macos.sh | bash
```

### Why does macOS warn about this at all?

macOS flags every file a browser downloads, and Gatekeeper then refuses to open
programs that Apple has not certified. Getting rid of that warning completely
means signing and notarising the app with Apple, which requires a paid Apple
Developer account — there is no free way around it, for any app.

The warning is about who signed the file, not about what the file does. You can
read every line of it: it is
[`install-macos.sh`](https://github.com/SyedmaazSaif/career-copilot/blob/main/installer/install-macos.sh)
in this repository.

### Does it need my password?

No. Anything missing (Node, Python) is installed into
`~/.career-copilot/tools`, a folder your own account owns. Nothing is installed
system-wide, so macOS never asks for an administrator password.

---

## Starting the app

Once it is installed, this is all there is to it — and on both systems the app
window is the only thing that appears.

| | Start it with | Stop it with |
|---|---|---|
| **Windows** | The **career-copilot** shortcut on your Desktop, or `career-copilot.vbs` in the app folder | Close the app window |
| **macOS** | **Career Copilot** in Launchpad or Spotlight, or `Career Copilot.app` in the `career-copilot` folder | Close the app window |

Closing the window shuts down the background pieces too — the local web server
and the Python backend — so nothing is left running.

Starting it a second time while it is already open just brings the existing
window to the front rather than starting a second copy.

**Where the log lives.** Because there is no console, the app writes what it
would have printed to:

- **Windows:** `%USERPROFILE%\.career-copilot\logs\app.log`
- **macOS:** `~/.career-copilot/logs/app.log`

That file is the first place to look if the app does not open, and the thing to
attach to a bug report.

**Running it from a terminal on purpose** (for development): `npm start` in the
app folder does the same thing as the launchers, and `npm run dev` runs it with
all the output live in your terminal.

---

## What the installer actually does

Both installers run the same six steps, and print each one as it goes:

| Step | What happens |
|---|---|
| 1 | Checks for **Node.js 18+**. Installs it if missing — winget on Windows, the official Node build into `~/.career-copilot/tools` on macOS. |
| 2 | Checks for **Python 3.10+**. Installs it if missing, the same way. |
| 3 | Installs the app's front-end libraries (`npm install`). |
| 4 | Creates the Python environment for the local backend and installs its libraries. |
| 5 | **Offers the optional local AI** — see below. |
| 6 | Creates a launcher for next time (**Career Copilot.app** on macOS, a Desktop shortcut on Windows), then starts the app in the background. |

Re-running an installer is safe. It updates the app to the latest version and
keeps your profile, your saved jobs, your settings and your generated CVs.

---

## Optional: the free local AI

Step 5 of the install stops and asks whether you want it. Before asking, it
reads your computer's memory and graphics and tells you **which model it can
actually run**, how big the download is, and why — so you are choosing with the
facts in front of you rather than guessing.

Say yes and it installs Ollama, downloads that model, and switches it on. Say
no and nothing is installed; the app works fully without it, just with simpler
wording. Either way there is no account, no paid API, and nothing you write
leaves your computer.

Changed your mind later? Open **Settings** in the app and click **Set up local
AI** — the same thing, at any time.

Prefer to do it by hand? Install Ollama from <https://ollama.com>, run
`ollama pull llama3.2:1b`, and set `OLLAMA_ENABLED=true` in `.env`.

---

## First time in the app (both systems)

1. **Profile** — click **Upload resume** and pick your PDF or Word file, or
   fill it in by hand. This is the only source of facts the app uses; it never
   invents anything.
2. **Settings** — adjust the job titles to search, which boards are on, which
   locations to search, and your preferred work arrangements. You can add your
   own job sources here too.
3. **Jobs** — click **Scan now**. The first scan takes a few minutes. Each job
   gets a match score that explains itself. Open one to see the details,
   generate a tailored CV, and click **Open listing to apply**.

---

## If something goes wrong

**"Windows protected your PC"** — click **More info** → **Run anyway**. See
step 3 above.

**macOS: "cannot be opened" / "will damage your computer"** — **right-click**
the file and choose **Open**, then **Open** again. A double-click will not do
it the first time. See [why](#why-does-macos-warn-about-this-at-all).

**"Node.js was installed but is not visible yet"** (Windows) — close the window
and double-click the installer once more. Windows sometimes needs a fresh
window to notice a newly installed program.

**The download fails or times out** — check your internet connection and run
the installer again. It picks up from where it left off and will not lose
anything.

**The install finished but no window opened** — start it by hand: open the
`career-copilot` folder and double-click `career-copilot.vbs` (Windows) or
`Career Copilot.app` (macOS). If still nothing happens, the reason is in the
log — see below.

**Nothing on screen and you want to know why** — the app writes everything it
would otherwise print to a log file, because it deliberately runs without a
console:

- **Windows:** `%USERPROFILE%\.career-copilot\logs\app.log`
- **macOS:** `~/.career-copilot/logs/app.log`

Open that file (or paste it into an issue) — the last few lines say what
stopped it.

**A Terminal or PowerShell window opens when you start the app** — you are
launching it the old way. On macOS use `Career Copilot.app`, not the retired
`career-copilot.command`; on Windows use the Desktop shortcut or
`career-copilot.vbs`, not the setup file. Re-running setup replaces the old
launchers with the new ones.

**Anything else** — open an issue with what the window printed.

---

## Requirements

- Windows 10/11, or macOS on Intel or Apple Silicon.
- About 2 GB of free disk space, plus 1–5 GB more if you choose the local AI.
- An internet connection for the install and for scanning job boards.
- **Node.js 18+ and Python 3.10+** — the installer handles these for you; you
  do not need to install them yourself.

Everything runs locally. No account, no paid API, and no data leaves your
computer.

---

## Uninstall

Delete the `career-copilot` folder (in your user folder on both systems), the
Desktop shortcut on Windows, `Career Copilot.app` from Applications on macOS,
and the `.career-copilot` folder in your user folder (it holds the tools the
installer downloaded and the log file). If you installed
the local AI and want that gone too, uninstall Ollama the normal way for your
system.
