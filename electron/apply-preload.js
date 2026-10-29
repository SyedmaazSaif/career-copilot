const { contextBridge, ipcRenderer } = require("electron");

// Minimal API for the in-app browser shell (apply-window.html).
contextBridge.exposeInMainWorld("applyBridge", {
  openExternal: (url) => ipcRenderer.invoke("open-external", url),
  // The main process sends each tab to open (url + optional generated CV path).
  onOpenTab: (cb) =>
    ipcRenderer.on("apply-open-tab", (_e, tab) => cb(tab || {})),
  // Reveal a file in the OS file manager.
  revealItem: (p) => ipcRenderer.invoke("show-item", p),
  // Native picker for "upload your own CV".
  pickCv: () => ipcRenderer.invoke("pick-cv"),

  // Local logins (encrypted in the main process via OS keychain/DPAPI).
  saveLogin: (origin, username, password) =>
    ipcRenderer.invoke("login-save", { origin, username, password }),
  getLogin: (url) => ipcRenderer.invoke("login-get", url),
  listLogins: () => ipcRenderer.invoke("login-list"),
  deleteLogin: (url) => ipcRenderer.invoke("login-delete", url),
});
