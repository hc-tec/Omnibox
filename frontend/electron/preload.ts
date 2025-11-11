// Use CommonJS require so the compiled preload stays compatible with Electron's loader.
// TypeScript type info is minimal here, but that's acceptable for this small bridge.
const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("desktop", {
  getVersion: () => ipcRenderer.invoke("app:version"),
  windowControls: {
    command: (action: "minimize" | "maximize" | "restore" | "close") =>
      ipcRenderer.invoke("window:command", action),
    isMaximized: () => ipcRenderer.invoke("window:is-maximized"),
    onStateChange: (callback: (isMaximized: boolean) => void) => {
      const listener = (_event: unknown, state: boolean) => callback(state);
      ipcRenderer.on("window:maximized", listener);
      return () => ipcRenderer.removeListener("window:maximized", listener);
    },
  },
});
