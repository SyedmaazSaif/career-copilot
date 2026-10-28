const { contextBridge, ipcRenderer } = require("electron");

// Minimal API for the in-app browser shell (apply-window.html).
contextBridge.exposeInMainWorld("applyBridge", {
  openExternal: (url) => ipcRenderer.invoke("open-external", url),
  // The main process sends the job URL to open once the shell has loaded.
  onApplyUrl: (cb) => ipcRenderer.on("apply-url", (_e, url) => cb(url)),
  // The generated CV path (if any) for this job.
  onApplyCv: (cb) => ipcRenderer.on("apply-cv", (_e, p) => cb(p)),
  // Reveal a file in the OS file manager.
  revealItem: (p) => ipcRenderer.invoke("show-item", p),
  // Native picker for "upload your own CV".
  pickCv: () => ipcRenderer.invoke("pick-cv"),
});
