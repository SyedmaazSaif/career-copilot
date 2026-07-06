const { contextBridge, ipcRenderer } = require("electron");

// Minimal API for the in-app browser shell (apply-window.html).
contextBridge.exposeInMainWorld("applyBridge", {
  openExternal: (url) => ipcRenderer.invoke("open-external", url),
});
