const { app, BrowserWindow, WebContentsView, dialog, ipcMain, shell, safeStorage } = require("electron");
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

// ===========================================================================
// In-app browser (Arc-style).
//
// Architecture: the main process owns one WebContentsView per tab. The window's
// own webContents is only the chrome (sidebar + toolbar). This is how a real
// multi-tab browser is built in Electron — NOT the deprecated <webview> tag,
// which is fragile and was causing pages to fail to render.
// ===========================================================================

// Keep these in sync with the CSS in apply-window.html (.sidebar width, .toolbar height).
const SIDEBAR_WIDTH = 232;
const TOOLBAR_HEIGHT = 49;

let applyWindow = null; // BrowserWindow hosting the chrome + tab views
let applyTabs = []; // { id, view, url, title, favicon, cvPath, showingError }
let applyActiveId = null;
let applyNextId = 1;
let pendingFirstUrl = null; // { url, cvPath } held until the chrome reports ready

function tabById(id) {
  return applyTabs.find((t) => t.id === id) || null;
}
function activeTab() {
  return tabById(applyActiveId);
}
function contentBounds() {
  if (!applyWindow || applyWindow.isDestroyed()) {
    return { x: SIDEBAR_WIDTH, y: TOOLBAR_HEIGHT, width: 0, height: 0 };
  }
  const [w, h] = applyWindow.getContentSize();
  return {
    x: SIDEBAR_WIDTH,
    y: TOOLBAR_HEIGHT,
    width: Math.max(0, w - SIDEBAR_WIDTH),
    height: Math.max(0, h - TOOLBAR_HEIGHT),
  };
}

function escapeHtml(s) {
  return String(s == null ? "" : s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function errorPageDataUrl(url, desc) {
  const html =
    "<!doctype html><html><head><meta charset=\"utf-8\"><title>Couldn't open page</title>" +
    "<style>body{font-family:system-ui,-apple-system,sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;background:#edeff3;color:#1b2733;text-align:center;padding:30px}div{max-width:460px}h2{font-size:17px;margin:0 0 8px}p{color:#667284;font-size:13px}</style></head>" +
    "<body><div><h2>This page could not open inside the app</h2>" +
    "<p>" + escapeHtml(desc || "Load error") + "</p>" +
    "<p>Use the &#8635; Reload button to try again, or <b>Open &#8599;</b> in the toolbar to open it in your normal browser.</p>" +
    "</div></body></html>";
  return "data:text/html;charset=utf-8," + encodeURIComponent(html);
}

function sendState() {
  if (!applyWindow || applyWindow.isDestroyed()) return;
  const tabs = applyTabs.map((t) => ({
    id: t.id,
    url: t.url,
    title: t.title || t.url || "New Tab",
    favicon: t.favicon,
    cvPath: t.cvPath || null,
    canGoBack: !!(t.view && t.view.webContents.canGoBack()),
    canGoForward: !!(t.view && t.view.webContents.canGoForward()),
    isNew: !t.view,
  }));
  let savedLogin = null;
  const t = activeTab();
  if (t && t.url) {
    const entry = readLoginEntry(t.url);
    if (entry) savedLogin = { username: entry.username || "" };
  }
  applyWindow.webContents.send("apply:state", { tabs, activeId: applyActiveId, savedLogin });
}

function layoutTabs() {
  const b = contentBounds();
  applyTabs.forEach((t) => {
    if (!t.view) return;
    if (t.id === applyActiveId) {
      t.view.setBounds(b);
    } else {
      // Keep the page alive but parked off-screen; only the active tab is shown.
      t.view.setBounds({ x: -100000, y: -100000, width: 1, height: 1 });
    }
  });
}

function refreshTab() {
  sendState();
}

function createTabView(tab, url) {
  const view = new WebContentsView({
    webPreferences: {
      partition: "persist:apply", // shared cookies across tabs, persisted to disk
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });
  applyWindow.contentView.addChildView(view);
  tab.view = view;
  const wc = view.webContents;

  wc.on("did-navigate", (_e, u) => {
    if (u && u.startsWith("data:")) return; // our own error page — keep the real URL
    console.log("[apply] tab navigated to", u);
    tab.url = u;
    tab.showingError = false;
    sendState();
  });
  wc.on("did-navigate-in-page", (_e, u, isMainFrame) => {
    if (isMainFrame) {
      tab.url = u;
      sendState();
    }
  });
  wc.on("page-title-updated", (_e, title) => {
    tab.title = title || tab.url;
    sendState();
  });
  wc.on("page-favicon-updated", (_e, favicons) => {
    tab.favicon = (favicons && favicons[0]) || null;
    sendState();
  });
  wc.on("did-fail-load", (_e, code, desc, validatedURL, isMainFrame) => {
    if (code === -3) return; // aborted (redirect) — not a real failure
    if (!isMainFrame) return;
    console.error("[apply] tab failed to load", validatedURL, desc);
    tab.showingError = true;
    if (validatedURL) tab.url = validatedURL;
    wc.loadURL(errorPageDataUrl(tab.url, desc)).catch(() => {});
    sendState();
  });
  // Links that ask for a new window (target=_blank, window.open) open as tabs.
  wc.setWindowOpenHandler(({ url }) => {
    if (/^https?:\/\//i.test(url)) openTab(url, null);
    return { action: "deny" };
  });
  wc.loadURL(url).catch(() => {});
  layoutTabs();
}

function openTab(url, cvPath) {
  const tab = {
    id: applyNextId++,
    view: null,
    url: url || null,
    title: url || "New Tab",
    favicon: null,
    cvPath: cvPath || null,
    showingError: false,
  };
  applyTabs.push(tab);
  if (url) createTabView(tab, url);
  applyActiveId = tab.id;
  layoutTabs();
  sendState();
  return tab;
}

function closeTab(id) {
  const idx = applyTabs.findIndex((t) => t.id === id);
  if (idx < 0) return;
  const tab = applyTabs[idx];
  if (tab.view) {
    try {
      applyWindow.contentView.removeChildView(tab.view);
      tab.view.webContents.close();
    } catch {
      /* already gone */
    }
  }
  applyTabs.splice(idx, 1);
  if (applyTabs.length === 0) {
    openTab(null, null); // never leave an empty window — show a new-tab page
  } else if (applyActiveId === id) {
    applyActiveId = applyTabs[Math.min(idx, applyTabs.length - 1)].id;
    layoutTabs();
    sendState();
  } else {
    sendState();
  }
}

function activateTab(id) {
  applyActiveId = id;
  layoutTabs();
  sendState();
}

function normalizeUrl(raw) {
  let s = String(raw || "").trim();
  if (!s) return null;
  if (/^https?:\/\//i.test(s)) return s;
  if (/^[\w-]+(\.[\w-]+)+([/?#].*)?$/.test(s)) return "https://" + s;
  return "https://www.google.com/search?q=" + encodeURIComponent(s);
}

function navigateTab(id, raw) {
  const tab = tabById(id);
  if (!tab) return;
  const u = normalizeUrl(raw);
  if (!u) return;
  tab.showingError = false;
  if (!tab.view) {
    tab.url = u;
    createTabView(tab, u);
  } else {
    tab.url = u;
    tab.view.webContents.loadURL(u).catch(() => {});
  }
  sendState();
}

function openApplyWindow(targetUrl, cvPath) {
  if (!/^https?:\/\//i.test(targetUrl)) return; // only real web pages

  // Reuse the existing apply window: a second job opens as another tab.
  if (applyWindow && !applyWindow.isDestroyed()) {
    if (applyWindow.isMinimized()) applyWindow.restore();
    applyWindow.show();
    applyWindow.focus();
    openTab(targetUrl, cvPath || null);
    return;
  }

  const win = new BrowserWindow({
    width: 1200,
    height: 820,
    minWidth: 760,
    minHeight: 560,
    backgroundColor: "#EDEFF3",
    title: "Apply",
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, "apply-preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });
  win.loadFile(path.join(__dirname, "apply-window.html"));
  applyWindow = win;
  pendingFirstUrl = { url: targetUrl, cvPath: cvPath || null };

  win.on("resize", layoutTabs);
  win.on("closed", () => {
    applyTabs = [];
    applyActiveId = null;
    pendingFirstUrl = null;
    applyWindow = null;
  });
}

ipcMain.handle("open-apply", (_event, url, cvPath) => {
  openApplyWindow(url, cvPath);
});

// ---- Chrome (sidebar/toolbar) <-> main intents ----
ipcMain.handle("apply:ready", () => {
  if (applyTabs.length === 0) {
    if (pendingFirstUrl) {
      const p = pendingFirstUrl;
      pendingFirstUrl = null;
      openTab(p.url, p.cvPath);
    } else {
      openTab(null, null);
    }
  }
  return {
    tabs: applyTabs.map((t) => ({ id: t.id, url: t.url, title: t.title, favicon: t.favicon, cvPath: t.cvPath, isNew: !t.view })),
    activeId: applyActiveId,
  };
});

ipcMain.handle("apply:get-state", () => {
  if (!applyWindow) return null;
  const tabs = applyTabs.map((t) => ({ id: t.id, url: t.url, title: t.title, favicon: t.favicon, cvPath: t.cvPath, isNew: !t.view }));
  return { tabs, activeId: applyActiveId };
});

ipcMain.handle("apply:activate", (_e, id) => { activateTab(id); });
ipcMain.handle("apply:close-tab", (_e, id) => { closeTab(id); });
ipcMain.handle("apply:new-tab", () => { openTab(null, null); });
ipcMain.handle("apply:open-url", (_e, url) => {
  if (/^https?:\/\//i.test(url)) openTab(url, null);
});
ipcMain.handle("apply:navigate", (_e, payload) => {
  navigateTab(payload && payload.id, payload && payload.raw);
});
ipcMain.handle("apply:back", (_e, id) => {
  const t = tabById(id);
  if (t && t.view && t.view.webContents.canGoBack()) t.view.webContents.goBack();
});
ipcMain.handle("apply:forward", (_e, id) => {
  const t = tabById(id);
  if (t && t.view && t.view.webContents.canGoForward()) t.view.webContents.goForward();
});
ipcMain.handle("apply:reload", (_e, id) => {
  const t = tabById(id);
  if (!t || !t.view) return;
  if (t.showingError && t.url) t.view.webContents.loadURL(t.url).catch(() => {});
  else t.view.webContents.reload();
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
// Local logins for the in-app browser.
//
// HUMAN REVIEW NEEDED: this code stores and retrieves website passwords.
// Passwords are encrypted with Electron safeStorage (macOS Keychain / Windows
// DPAPI) and only the encrypted blob is written to disk; the plaintext never
// touches a file or log. A login is keyed by origin (scheme+host+port), filled
// only on that exact origin, only on the user's click, and never auto-submitted.
// ---------------------------------------------------------------------------
function loginsFile() {
  return path.join(app.getPath("userData"), "logins.json");
}

function readLogins() {
  try {
    return JSON.parse(fs.readFileSync(loginsFile(), "utf8"));
  } catch {
    return {};
  }
}

function writeLogins(data) {
  fs.writeFileSync(loginsFile(), JSON.stringify(data, null, 2), { mode: 0o600 });
}

// Reduce a URL to its origin (e.g. https://www.linkedin.com). Anything that is
// not a plain http(s) URL is rejected so a page can't smuggle in a bogus key.
function normalizeOrigin(url) {
  if (typeof url !== "string") return null;
  try {
    const u = new URL(url);
    if (u.protocol !== "http:" && u.protocol !== "https:") return null;
    return u.origin;
  } catch {
    return null;
  }
}

function readLoginEntry(url) {
  const origin = normalizeOrigin(url);
  if (!origin) return null;
  const entry = readLogins()[origin];
  if (!entry || !safeStorage.isEncryptionAvailable()) return null;
  try {
    // HUMAN REVIEW NEEDED: password is decrypted only in memory, on demand.
    return {
      username: entry.username || "",
      password: safeStorage.decryptString(Buffer.from(entry.passwordB64, "base64")),
    };
  } catch {
    return null;
  }
}

ipcMain.handle("login-save", (_event, payload) => {
  const origin = normalizeOrigin(payload && payload.origin);
  const username = payload && typeof payload.username === "string" ? payload.username : "";
  const password = payload && typeof payload.password === "string" ? payload.password : "";
  if (!origin || !password) return { ok: false, error: "Nothing to save" };
  if (!safeStorage.isEncryptionAvailable()) {
    return { ok: false, error: "Secure storage is unavailable on this device" };
  }
  const data = readLogins();
  // HUMAN REVIEW NEEDED: password encrypted before it is persisted.
  data[origin] = {
    username,
    passwordB64: safeStorage.encryptString(password).toString("base64"),
  };
  writeLogins(data);
  return { ok: true };
});

ipcMain.handle("login-get", (_event, url) => {
  return readLoginEntry(url);
});

ipcMain.handle("login-list", () => {
  return Object.entries(readLogins()).map(([origin, entry]) => ({
    origin,
    username: entry.username || "",
  }));
});

ipcMain.handle("login-delete", (_event, url) => {
  const origin = normalizeOrigin(url);
  if (!origin) return { ok: false };
  const data = readLogins();
  delete data[origin];
  writeLogins(data);
  return { ok: true };
});

// ---------------------------------------------------------------------------
// Autofill + login fill scripts. These run inside the page (via executeJavaScript
// on the tab's webContents), fill only empty fields, and never submit a form.
// ---------------------------------------------------------------------------

function buildProfileData(profile) {
  const name = (profile.name || "").trim();
  const parts = name.split(/\s+/).filter(Boolean);
  const loc = (profile.location || "").split(",").map((s) => s.trim()).filter(Boolean);
  return {
    fullName: name,
    firstName: parts[0] || "",
    lastName: parts.length > 1 ? parts.slice(1).join(" ") : "",
    email: profile.email || "",
    phone: profile.phone || "",
    linkedin: profile.linkedin || "",
    portfolio: profile.portfolio || "",
    location: profile.location || "",
    city: loc[0] || "",
    country: loc.length > 1 ? loc[loc.length - 1] : "",
    salary: profile.salary_expectation_usd || "",
    notice: profile.notice_period || "",
    workAuth: profile.work_authorization || "",
  };
}

function buildFillScript(data) {
  return "(function(){" +
    "var d=" + JSON.stringify(data) + ";" +
    "var pats=[" +
      "{k:['email'],re:/e-?mail/i,ex:/confirm/i}," +
      "{k:['phone'],re:/phone|mobile|telephone|^tel$/i}," +
      "{k:['firstName'],re:/first[ _-]*name|given[ _-]*name|fname/i}," +
      "{k:['lastName'],re:/last[ _-]*name|surname|family[ _-]*name|lname/i}," +
      "{k:['fullName'],re:/full[ _-]*name|your[ _-]*name|applicant[ _-]*name|candidate[ _-]*name|^name$|legal[ _-]*name/i,ex:/user|company|file/i}," +
      "{k:['linkedin'],re:/linked-?in/i}," +
      "{k:['portfolio'],re:/portfolio|website|personal[ _-]*site|github|^url$/i,ex:/company/i}," +
      "{k:['city'],re:/^city$|town/i}," +
      "{k:['country'],re:/country/i}," +
      "{k:['location'],re:/location|current[ _-]*address|^address$/i,ex:/email|ip|line2/i}," +
      "{k:['salary'],re:/salary|compensation|expected[ _-]*pay|desired[ _-]*pay/i}," +
      "{k:['notice'],re:/notice[ _-]*period|availab/i}," +
      "{k:['workAuth'],re:/authoriz|visa|sponsor|work[ _-]*permit|eligib|right[ _-]*to[ _-]*work/i}" +
    "];" +
    "function lbl(el){var t='';try{if(el.id){var l=document.querySelector('label[for=\"'+(window.CSS&&CSS.escape?CSS.escape(el.id):el.id)+'\"]');if(l)t+=' '+l.textContent;}}catch(e){}var p=el.closest&&el.closest('label');if(p)t+=' '+p.textContent;return t;}" +
    "function sig(el){return [el.name,el.id,el.placeholder,el.getAttribute('aria-label'),el.getAttribute('autocomplete'),lbl(el)].filter(Boolean).join(' ').toLowerCase();}" +
    "function setVal(el,val){try{var proto=el.tagName==='TEXTAREA'?window.HTMLTextAreaElement.prototype:window.HTMLInputElement.prototype;var s=Object.getOwnPropertyDescriptor(proto,'value').set;s.call(el,val);}catch(e){el.value=val;}el.dispatchEvent(new Event('input',{bubbles:true}));el.dispatchEvent(new Event('change',{bubbles:true}));}" +
    "var skip=['password','hidden','file','checkbox','radio','submit','button','search','range','color','image','reset'];" +
    "var count=0;" +
    "function fillDoc(doc){var els=doc.querySelectorAll('input,textarea');Array.prototype.forEach.call(els,function(el){var type=(el.type||'text').toLowerCase();if(skip.indexOf(type)>=0)return;if(el.disabled||el.readOnly)return;if(el.value&&el.value.trim())return;var s=sig(el);if(!s)return;for(var i=0;i<pats.length;i++){var pat=pats[i];if(pat.ex&&pat.ex.test(s))continue;if(pat.re.test(s)){var val='';for(var j=0;j<pat.k.length;j++){if(d[pat.k[j]]){val=d[pat.k[j]];break;}}if(val){setVal(el,val);count++;}break;}}});}" +
    "fillDoc(document);" +
    "try{var fr=document.querySelectorAll('iframe');Array.prototype.forEach.call(fr,function(f){try{if(f.contentDocument)fillDoc(f.contentDocument);}catch(e){}});}catch(e){}" +
    "return count;" +
  "})();";
}

function fillLoginScript(username, password) {
  return "(function(){" +
    "var u=" + JSON.stringify(username) + ",p=" + JSON.stringify(password) + ";" +
    "function setVal(el,val){try{var proto=el.tagName==='TEXTAREA'?window.HTMLTextAreaElement.prototype:window.HTMLInputElement.prototype;var s=Object.getOwnPropertyDescriptor(proto,'value').set;s.call(el,val);}catch(e){el.value=val;}el.dispatchEvent(new Event('input',{bubbles:true}));el.dispatchEvent(new Event('change',{bubbles:true}));}" +
    "var inputs=document.querySelectorAll('input');" +
    "var pw=null;for(var i=0;i<inputs.length;i++){if((inputs[i].type||'').toLowerCase()==='password'){pw=inputs[i];break;}}" +
    "if(!pw)return {found:false};" +
    "var un=null;" +
    "for(var j=0;j<inputs.length;j++){var e=inputs[j];var t=(e.type||'').toLowerCase();if(t==='email'){un=e;break;}if(t==='text'||t==='tel'){var s=(e.name+' '+e.id+' '+(e.autocomplete||'')).toLowerCase();if(/user|email|login|account|username/i.test(s)){un=e;break;}}}" +
    "if(un)setVal(un,u);" +
    "setVal(pw,p);" +
    "return {found:true};" +
  "})();";
}

function readLoginScript() {
  return "(function(){" +
    "function get(el){return el.value||'';}" +
    "var inputs=Array.prototype.slice.call(document.querySelectorAll('input'));" +
    "var pw=null;for(var i=0;i<inputs.length;i++){if((inputs[i].type||'').toLowerCase()==='password'&&inputs[i].value){pw=inputs[i];break;}}" +
    "if(!pw)return {found:false};" +
    "var un=null;" +
    "for(var j=0;j<inputs.length;j++){var e=inputs[j];var t=(e.type||'').toLowerCase();var s=(e.name+' '+e.id+' '+(e.autocomplete||'')+' '+(e.placeholder||'')).toLowerCase();if(t==='email'){un=e;break;}if(t==='text'&&/user|email|login|account|username/i.test(s)){un=e;break;}}" +
    "return {found:true,username:un?get(un):'',password:get(pw)};" +
  "})();";
}

ipcMain.handle("apply:autofill", async () => {
  const t = activeTab();
  if (!t || !t.view) return { ok: false, msg: "No page open" };
  let profile;
  try {
    const res = await fetch(`${BACKEND_URL}/api/profile`);
    if (!res.ok) throw new Error("profile " + res.status);
    profile = await res.json();
  } catch (e) {
    return { ok: false, msg: "No profile found" };
  }
  const data = buildProfileData(profile);
  let count = 0;
  try {
    count = await t.view.webContents.executeJavaScript(buildFillScript(data), true);
  } catch (e) {
    return { ok: false, msg: "Can't fill here" };
  }
  return { ok: true, count };
});

ipcMain.handle("apply:fill-login", async () => {
  const t = activeTab();
  if (!t || !t.view || !t.url) return { ok: false, msg: "No page open" };
  const entry = readLoginEntry(t.url);
  if (!entry) return { ok: false, msg: "No saved login" };
  let res;
  try {
    res = await t.view.webContents.executeJavaScript(fillLoginScript(entry.username, entry.password), true);
  } catch (e) {
    return { ok: false, msg: "Can't fill here" };
  }
  return { ok: true, msg: res && res.found ? "Filled login" : "No login form found" };
});

ipcMain.handle("apply:save-login", async () => {
  const t = activeTab();
  if (!t || !t.view || !t.url) return { ok: false, msg: "No page open" };
  let creds;
  try {
    creds = await t.view.webContents.executeJavaScript(readLoginScript(), true);
  } catch (e) {
    return { ok: false, msg: "Can't read page" };
  }
  if (!creds || !creds.found || !creds.password) {
    return { ok: false, msg: "Type your password first" };
  }
  const origin = normalizeOrigin(t.url);
  if (!origin) return { ok: false, msg: "Nothing to save" };
  if (!safeStorage.isEncryptionAvailable()) {
    return { ok: false, msg: "Secure storage is unavailable" };
  }
  const data = readLogins();
  data[origin] = {
    username: creds.username || "",
    passwordB64: safeStorage.encryptString(creds.password).toString("base64"),
  };
  writeLogins(data);
  sendState();
  return { ok: true, msg: "Login saved" };
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
