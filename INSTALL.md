# Install career-copilot

One installer per system. It downloads the app, installs everything the app
needs — **including Node.js and Python, if your computer does not have them** —
offers the optional local AI, and starts the app. You are never sent to another
website to install something by hand.

Jump to: **[Windows](#windows)** · **[macOS](#macos)** ·
**[First run](#first-time-in-the-app-both-systems)** ·
**[If something goes wrong](#if-something-goes-wrong)**

> **Why two downloads and not one?** Windows and macOS will not run each
> other's programs, so there is no single file both can open — the same
> reason apps ship a Windows download and a Mac download separately. Both
> installers below do exactly the same thing.

---

## Windows

**1. Download the installer:**
[**Install-Career-Copilot-Windows.zip**](https://github.com/SyedmaazSaif/career-copilot/raw/main/Install-Career-Copilot-Windows.zip)

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

**Later launches:** double-click the Desktop shortcut, or `career-copilot.vbs`
in the app folder (it opens the app with no black console window).

---

## macOS

**1. Download the installer:**
[**Install-Career-Copilot-Mac.zip**](https://github.com/SyedmaazSaif/career-copilot/raw/main/Install-Career-Copilot-Mac.zip)

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

That is the whole install. It puts the app in `~/career-copilot` and creates a
`career-copilot.command` file inside that folder.

**Later launches:** double-click **`career-copilot.command`** in the
`career-copilot` folder in your home directory. No warning this time — the
installer clears it for you.

### Or, if you prefer the Terminal

One line, no download and no security warning at all:

```bash
curl -fsSL https://raw.githubusercontent.com/SyedmaazSaif/career-copilot/main/install-macos.sh | bash
```

### Why does macOS warn about this at all?

macOS flags every file a browser downloads, and Gatekeeper then refuses to open
programs that Apple has not certified. Getting rid of that warning completely
means signing and notarising the app with Apple, which requires a paid Apple
Developer account — there is no free way around it, for any app.

The warning is about who signed the file, not about what the file does. You can
read every line of it: it is
[`install-macos.sh`](https://github.com/SyedmaazSaif/career-copilot/blob/main/install-macos.sh)
in this repository.

### Does it need my password?

No. Anything missing (Node, Python) is installed into
`~/.career-copilot/tools`, a folder your own account owns. Nothing is installed
system-wide, so macOS never asks for an administrator password.

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
| 6 | Creates a launcher for next time, then starts the app. |

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
`career-copilot.command` (macOS).

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
Desktop shortcut on Windows, and `~/.career-copilot` on macOS. If you installed
the local AI and want that gone too, uninstall Ollama the normal way for your
system.
