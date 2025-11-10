// Use CommonJS require so the compiled preload stays compatible with Electron's loader.
// TypeScript type info is minimal here, but that's acceptable for this small bridge.
const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("desktop", {
  getVersion: () => ipcRenderer.invoke("app:version"),
});
