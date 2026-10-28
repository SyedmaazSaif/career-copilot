const { app, BrowserWindow, dialog, ipcMain, shell } = require("electron");
const { spawn, execFile } = require("child_process");
const fs = require("fs");
const os = require("os");
const path = require("path");
const http = require("http");
const https = require("https");

const isDev = !app.isPackaged;
const BACKEND_PORT = 8000;
const BACKEND_URL = `http://127.0.0.1:${BACKEND_PORT}`;

// Update check: this app installs by cloning the repo, so the update path is a
// `git pull`. On launch we read the version in the repo's main branch and, if it
// is newer than the local one, tell the renderer to show an update banner.
const REPO = "SyedmaazSaif/career-copilot";
const REMOTE_PKG_URL = `https://raw.githubusercontent.com/${REPO}/main/package.json`;
const RELEASES_URL = `https://github.com/${REPO}/releases`;

// Compare dotted numeric versions. Returns 1 if a > b, -1 if a < b, else 0.
function compareVersions(a, b) {
  const pa = String(a).split(".").map((n) => parseInt(n, 10) || 0);
  const pb = String(b).split(".").map((n) => parseInt(n, 10) || 0);
  for (let i = 0; i < Math.max(pa.length, pb.length); i++) {
    const d = (pa[i] || 0) - (pb[i] || 0);
    if (d !== 0) return d > 0 ? 1 : -1;
  }
  return 0;
}

function checkForUpdates(win) {
  const current = app.getVersion();
  const req = https.get(
    REMOTE_PKG_URL,
    { headers: { "User-Agent": "career-copilot" } },
    (res) => {
      if (res.statusCode !== 200) {
        res.resume();
        return;
      }
      let body = "";
      res.on("data", (c) => (body += c));
      res.on("end", () => {
        try {
          const latest = JSON.parse(body).version;
          if (latest && compareVersions(latest, current) > 0 && !win.isDestroyed()) {
            win.webContents.send("update-available", {
              current,
              latest,
              url: RELEASES_URL,
            });
          }
        } catch {
          /* malformed response — ignore, this is best-effort */
        }
      });
    }
  );
  // Offline or blocked? Silently skip; an update check must never break launch.
  req.on("error", () => {});
  req.setTimeout(5000, () => req.destroy());
}

let backendProcess = null;
let mainWindow = null;

// Resolve the Python interpreter inside the backend venv, tailored to platform.
function backendPython() {
  const backendDir = path.join(__dirname, "..", "backend");
  const win = path.join(backendDir, ".venv", "Scripts", "python.exe");
  const nix = path.join(backendDir, ".venv", "bin", "python");
  return process.platform === "win32" ? win : nix;
}

function startBackend() {
  const python = backendPython();
  // Run uvicorn from the career-copilot root so the `backend` package imports.
  const cwd = path.join(__dirname, "..");
  backendProcess = spawn(
    python,
    [
      "-m",
      "uvicorn",
      "backend.main:app",
      "--host",
      "127.0.0.1",
      "--port",
      String(BACKEND_PORT),
    ],
    // windowsHide stops Windows from popping a separate console window for the
    // Python sidecar when the app is launched from the hidden VBS wrapper.
    { cwd, stdio: "inherit", windowsHide: true }
  );

  backendProcess.on("error", (err) => {
    console.error("[backend] failed to start:", err);
  });
  backendProcess.on("exit", (code, signal) => {
    console.log(`[backend] exited code=${code} signal=${signal}`);
    backendProcess = null;
  });
}

function stopBackend() {
  if (backendProcess && !backendProcess.killed) {
    // On Windows, SIGTERM maps to a hard kill of the child process.
    backendProcess.kill();
    backendProcess = null;
  }
}

// Poll /health until the sidecar answers, then resolve.
function waitForBackend(timeoutMs = 20000) {
  const start = Date.now();
  return new Promise((resolve, reject) => {
    const tryOnce = () => {
      const req = http.get(`${BACKEND_URL}/health`, (res) => {
        res.resume();
        if (res.statusCode === 200) return resolve();
        retry();
      });
      req.on("error", retry);
      req.setTimeout(1500, () => req.destroy());
    };
    const retry = () => {
      if (Date.now() - start > timeoutMs) {
        return reject(new Error("backend did not become healthy in time"));
      }
      setTimeout(tryOnce, 400);
    };
    tryOnce();
  });
}

// In-app browser: open a job's page in a native window inside the app so the
// user applies without leaving career-copilot. The window hosts a webview with
// a small toolbar (back / forward / reload / open in system browser).
const applyWindows = new Set();

function openApplyWindow(targetUrl, cvPath) {
  if (!/^https?:\/\//i.test(targetUrl)) return; // only real web pages
  const win = new BrowserWindow({
    width: 1100,
    height: 800,
    backgroundColor: "#EDEFF3",
    title: "Apply",
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, "apply-preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      webviewTag: true,
    },
  });
  // Load the local shell, then hand it the job URL over IPC once it is ready.
  // (Passing the URL via a file:// query string proved unreliable.)
  win.loadFile(path.join(__dirname, "apply-window.html"));

  win.webContents.on("did-fail-load", (_e, code, desc, failedUrl) => {
    console.error(`[apply] shell failed to load ${failedUrl}: ${code} ${desc}`);
    // If our own shell page can't load, don't dead-end — open in the system browser.
    if (code !== -3) {
      shell.openExternal(targetUrl);
      win.close();
    }
  });
  win.webContents.on("did-finish-load", () => {
    console.log("[apply] shell loaded ok; sending url");
    win.webContents.send("apply-url", targetUrl);
    if (cvPath) win.webContents.send("apply-cv", cvPath);
  });
  // Log where the inner job-page (webview) actually navigates, so a blank page
  // is distinguishable from the real page.
  win.webContents.on("did-attach-webview", (_e, wc) => {
    wc.on("did-navigate", (_ev, u) => console.log(`[apply] job page navigated to ${u}`));
    wc.on("did-fail-load", (_ev, code, desc, u) => {
      if (code !== -3) console.error(`[apply] job page failed ${u}: ${code} ${desc}`);
    });
  });
  applyWindows.add(win);
  win.on("closed", () => applyWindows.delete(win));
}

ipcMain.handle("open-apply", (_event, url, cvPath) => {
  openApplyWindow(url, cvPath);
});

// Reveal a generated CV in the OS file manager so the user can drag it into
// the job site's upload field. The app never injects files into a web page.
ipcMain.handle("show-item", (_event, p) => {
  if (typeof p === "string" && p.trim()) shell.showItemInFolder(p);
});

// Native file picker for "upload your own CV". Reveals the chosen file so it
// is one drag away from the job form. Returns the path (or null if cancelled).
ipcMain.handle("pick-cv", async () => {
  const win = BrowserWindow.getFocusedWindow();
  const res = await dialog.showOpenDialog(win, {
    title: "Choose a CV to attach",
    properties: ["openFile"],
    filters: [
      { name: "Resumes", extensions: ["pdf", "docx", "doc"] },
      { name: "All files", extensions: ["*"] },
    ],
  });
  if (res.canceled || !res.filePaths.length) return null;
  const p = res.filePaths[0];
  shell.showItemInFolder(p);
  return p;
});

// Native folder picker for choosing where generated CVs are saved.
ipcMain.handle("pick-folder", async () => {
  const win = BrowserWindow.getFocusedWindow();
  const res = await dialog.showOpenDialog(win, {
    title: "Choose where to save your CVs",
    properties: ["openDirectory", "createDirectory"],
  });
  if (res.canceled || !res.filePaths.length) return null;
  return res.filePaths[0];
});

// The apply window's toolbar asks to open the current page in the real browser.
ipcMain.handle("open-external", (_event, url) => {
  if (/^https?:\/\//i.test(url)) shell.openExternal(url);
});

// ---------------------------------------------------------------------------
// One-click update. A development install is a git clone; the distributed
// install is a zip extract with no .git, so both paths are supported. After
// the code is replaced we refresh in place (reload the window and restart the
// backend) rather than relaunching the whole process, which would fight the
// start.js supervisor that owns the window and the Vite server.
// ---------------------------------------------------------------------------
const APP_ROOT = path.join(__dirname, "..");
const REPO_ARCHIVE_URL = `https://github.com/${REPO}/archive/refs/heads/main.zip`;
const UPDATE_PATH =
  "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:" + (process.env.PATH || "");

// Files older builds left behind and that no longer belong. A git clone drops
// them via git; a zip install overlays without deleting, so these are removed
// explicitly so old shortcuts and habits converge on the single launcher.
const STALE_FILES = [
  "start.bat",
  "setup.bat",
  "setup.command",
  "career-copilot.command",
  "windows/career-copilot.vbs",
];

function run(cmd, args, opts = {}) {
  const env = { ...process.env, PATH: UPDATE_PATH };
  return new Promise((resolve) => {
    execFile(cmd, args, { env, windowsHide: true, ...opts }, (err, stdout, stderr) => {
      if (err) {
        const detail = String(stderr || "").trim() || (err && err.message) || `update failed (${cmd})`;
        resolve({ ok: false, error: detail });
      } else {
        resolve({ ok: true, output: String(stdout || "") });
      }
    });
  });
}

async function updateFromGit() {
  return run("git", ["pull", "--ff-only"], { cwd: APP_ROOT, timeout: 120000 });
}

async function updateFromZip() {
  // The distributed install has no .git, so download the source archive and
  // overlay it. The archive holds only tracked files, so the user's local data
  // (database, .env, profile, node_modules, venv) is never in it and survives.
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "cc-update-"));
  const zip = path.join(tmp, "app.zip");
  const dl = await run(
    "curl", ["-fsSL", "--retry", "3", "-o", zip, REPO_ARCHIVE_URL],
    { timeout: 300000 }
  );
  if (!dl.ok) return dl;
  const unpacked = path.join(tmp, "unpacked");
  const isWindows = process.platform === "win32";
  let un;
  if (isWindows) {
    fs.mkdirSync(unpacked, { recursive: true });
    un = await run("tar", ["-xf", zip, "-C", unpacked]);
  } else {
    un = await run("ditto", ["-x", "-k", zip, unpacked]);
  }
  if (!un.ok) return un;
  const src = path.join(unpacked, "career-copilot-main");
  let overlay;
  if (isWindows) {
    overlay = await run("xcopy", [src + "\\*", APP_ROOT + "\\", "/E", "/Y", "/I"]);
  } else {
    overlay = await run("ditto", [src + "/", APP_ROOT + "/"]);
  }
  if (!overlay.ok) return overlay;
  for (const rel of STALE_FILES) {
    try {
      fs.rmSync(path.join(APP_ROOT, rel), { force: true });
    } catch {
      /* a stale file that cannot be removed must not block the update */
    }
  }
  return { ok: true };
}

ipcMain.handle("update-app", async () => {
  const isGitClone = fs.existsSync(path.join(APP_ROOT, ".git"));
  const result = isGitClone ? await updateFromGit() : await updateFromZip();
  if (!result.ok) return result;
  stopBackend();
  startBackend();
  try {
    await waitForBackend();
  } catch (err) {
    console.error("[update] backend did not restart:", err.message);
  }
  if (mainWindow && !mainWindow.isDestroyed()) mainWindow.reload();
  return { ok: true };
});

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 820,
    minWidth: 720,
    minHeight: 560,
    backgroundColor: "#EDEFF3",
    show: false,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  if (isDev) {
    mainWindow.loadURL("http://localhost:5173");
  } else {
    mainWindow.loadFile(path.join(__dirname, "..", "dist", "index.html"));
  }

  mainWindow.once("ready-to-show", () => {
    mainWindow.show();
    // Best-effort update check once the window is up. Never blocks launch.
    checkForUpdates(mainWindow);
  });
  mainWindow.on("closed", () => {
    mainWindow = null;
  });
}

// One copy at a time. The launcher is a double-clickable file with no console
// to show that the app is already starting, so an impatient second click used
// to start a second backend, which then failed to bind port 8000 and left the
// user with a window that never loaded. Now the second copy simply raises the
// window that already exists and quits.
const gotTheLock = app.requestSingleInstanceLock();

if (!gotTheLock) {
  app.quit();
} else {
  app.on("second-instance", () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.show();
      mainWindow.focus();
    }
  });

  app.whenReady().then(async () => {
    startBackend();
    try {
      await waitForBackend();
    } catch (err) {
      console.error(err.message);
    }
    createWindow();

    app.on("activate", () => {
      if (BrowserWindow.getAllWindows().length === 0) createWindow();
    });
  });
}

app.on("window-all-closed", () => {
  stopBackend();
  if (process.platform !== "darwin") app.quit();
});

// Belt and suspenders: kill the sidecar on every exit path.
app.on("before-quit", stopBackend);
app.on("will-quit", stopBackend);
process.on("exit", stopBackend);
process.on("SIGINT", () => {
  stopBackend();
  app.quit();
});
