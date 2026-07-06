const { contextBridge, ipcRenderer } = require("electron");

// Expose a small, explicit API to the renderer. No general Node access.
contextBridge.exposeInMainWorld("copilot", {
  backendUrl: "http://127.0.0.1:8000",
  // Open a job's page in a native in-app browser window.
  openApply: (url) => ipcRenderer.invoke("open-apply", url),
  // Signals to the renderer that the in-app browser is available.
  hasInAppBrowser: true,
});
