import { app, BrowserWindow, ipcMain, dialog } from "electron";
import { join } from "node:path";

const isDev = process.env.VITE_DEV_SERVER_URL !== undefined;

let mainWindow: BrowserWindow | null = null;

async function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1366,
    height: 900,
    minWidth: 1100,
    minHeight: 720,
    backgroundColor: "#f8fafc",
    show: false,
    center: true,
    titleBarStyle: "hiddenInset",
    webPreferences: {
      preload: join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      spellcheck: false,
    },
  });

  mainWindow.on("ready-to-show", () => {
    if (!mainWindow) return;
    mainWindow.show();
    if (isDev) {
      mainWindow.webContents.openDevTools({ mode: "detach" });
    }
  });

  const pageUrl = isDev
    ? process.env.VITE_DEV_SERVER_URL!
    : join(__dirname, "../renderer/index.html");

  if (isDev) {
    await mainWindow.loadURL(pageUrl);
  } else {
    await mainWindow.loadFile(pageUrl);
  }
}

app.whenReady().then(() => {
  createWindow().catch((error) => {
    dialog.showErrorBox("启动失败", `${error}`);
  });

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow().catch(console.error);
    }
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});

ipcMain.handle("app:version", () => app.getVersion());
