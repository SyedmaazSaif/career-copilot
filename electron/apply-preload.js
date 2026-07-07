const { contextBridge, ipcRenderer } = require("electron");

// Minimal API for the in-app browser shell (apply-window.html).
contextBridge.exposeInMainWorld("applyBridge", {
  openExternal: (url) => ipcRenderer.invoke("open-external", url),
  // The main process sends the job URL to open once the shell has loaded.
  onApplyUrl: (cb) => ipcRenderer.on("apply-url", (_e, url) => cb(url)),
});
