const { app, BrowserWindow, ipcMain, shell } = require("electron");
const { spawn } = require("child_process");
const path = require("path");
const http = require("http");

const isDev = !app.isPackaged;
const BACKEND_PORT = 8000;
const BACKEND_URL = `http://127.0.0.1:${BACKEND_PORT}`;

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
    { cwd, stdio: "inherit" }
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

function openApplyWindow(targetUrl) {
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
  // loadFile builds a correct file:// URL across platforms (a hand-built
  // "file://" + a Windows backslash path does not load). query -> ?url=...
  win.loadFile(path.join(__dirname, "apply-window.html"), {
    query: { url: targetUrl },
  });
  win.webContents.on("did-fail-load", (_e, code, desc, failedUrl) => {
    console.error(`[apply] shell failed to load ${failedUrl}: ${code} ${desc}`);
    // If our own shell page can't load, don't dead-end — open in the system browser.
    if (code !== -3) {
      shell.openExternal(targetUrl);
      win.close();
    }
  });
  win.webContents.on("did-finish-load", () => {
    console.log("[apply] shell loaded ok");
  });
  // Log inner job-page (webview) load results too.
  win.webContents.on("did-attach-webview", (_e, wc) => {
    wc.on("did-finish-load", () => console.log("[apply] job page loaded ok"));
    wc.on("did-fail-load", (_ev, code, desc, u) => {
      if (code !== -3) console.error(`[apply] job page failed ${u}: ${code} ${desc}`);
    });
  });
  applyWindows.add(win);
  win.on("closed", () => applyWindows.delete(win));
}

ipcMain.handle("open-apply", (_event, url) => {
  openApplyWindow(url);
});

// The apply window's toolbar asks to open the current page in the real browser.
ipcMain.handle("open-external", (_event, url) => {
  if (/^https?:\/\//i.test(url)) shell.openExternal(url);
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

  mainWindow.once("ready-to-show", () => mainWindow.show());
  mainWindow.on("closed", () => {
    mainWindow = null;
  });
}

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
