const { contextBridge, ipcRenderer } = require("electron");

// Expose a small, explicit API to the renderer. No general Node access.
contextBridge.exposeInMainWorld("copilot", {
  backendUrl: "http://127.0.0.1:8000",
  // Open a job's page in a native in-app browser window.
  openApply: (url) => ipcRenderer.invoke("open-apply", url),
  // Open a URL in the user's real browser (e.g. the releases page).
  openExternal: (url) => ipcRenderer.invoke("open-external", url),
  // Signals to the renderer that the in-app browser is available.
  hasInAppBrowser: true,
  // Fires once if a newer version is published in the repo. Returns an
  // unsubscribe function.
  onUpdateAvailable: (cb) => {
    const handler = (_e, info) => cb(info);
    ipcRenderer.on("update-available", handler);
    return () => ipcRenderer.removeListener("update-available", handler);
  },
});
