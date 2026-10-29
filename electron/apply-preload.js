const { contextBridge, ipcRenderer } = require("electron");

// Bridge for the in-app browser chrome (apply-window.html). The chrome is only
// the sidebar + toolbar; the main process owns each tab as a WebContentsView.
contextBridge.exposeInMainWorld("applyBridge", {
  // Tell main the chrome is ready and get the initial tab list back.
  ready: () => ipcRenderer.invoke("apply:ready"),
  getState: () => ipcRenderer.invoke("apply:get-state"),
  onState: (cb) => ipcRenderer.on("apply:state", (_e, s) => cb(s)),

  // Tab intents.
  activate: (id) => ipcRenderer.invoke("apply:activate", id),
  closeTab: (id) => ipcRenderer.invoke("apply:close-tab", id),
  newTab: () => ipcRenderer.invoke("apply:new-tab"),
  openUrl: (url) => ipcRenderer.invoke("apply:open-url", url),
  navigate: (id, raw) => ipcRenderer.invoke("apply:navigate", { id, raw }),
  back: (id) => ipcRenderer.invoke("apply:back", id),
  forward: (id) => ipcRenderer.invoke("apply:forward", id),
  reload: (id) => ipcRenderer.invoke("apply:reload", id),

  // CV helpers.
  pickCv: () => ipcRenderer.invoke("pick-cv"),
  reveal: (p) => ipcRenderer.invoke("show-item", p),

  // Job-form autofill + logins (run in the main process, on the active tab).
  autofill: () => ipcRenderer.invoke("apply:autofill"),
  fillLogin: () => ipcRenderer.invoke("apply:fill-login"),
  saveLogin: () => ipcRenderer.invoke("apply:save-login"),
  listLogins: () => ipcRenderer.invoke("login-list"),
  deleteLogin: (url) => ipcRenderer.invoke("login-delete", url),

  // Open the current page in the real browser.
  openExternal: (url) => ipcRenderer.invoke("open-external", url),
});
