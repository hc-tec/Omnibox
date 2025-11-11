import { app, BrowserWindow, ipcMain, dialog, Menu } from "electron";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const isDev = process.env.VITE_DEV_SERVER_URL !== undefined;

let mainWindow: BrowserWindow | null = null;

async function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1100,
    height: 720,
    minWidth: 1100,
    minHeight: 720,
    backgroundColor: "#050814",
    show: false,
    frame: false,
    titleBarStyle: "hidden",
    autoHideMenuBar: true,
    webPreferences: {
      preload: join(__dirname, "electron", "preload.js"),
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

  mainWindow.on("maximize", () => {
    mainWindow?.webContents.send("window:maximized", true);
  });

  mainWindow.on("unmaximize", () => {
    mainWindow?.webContents.send("window:maximized", false);
  });

  const pageUrl = isDev
    ? process.env.VITE_DEV_SERVER_URL!
    : join(__dirname, "../../dist/index.html");

  if (isDev) {
    await mainWindow.loadURL(pageUrl);
  } else {
    await mainWindow.loadFile(pageUrl);
  }
}

app.whenReady().then(() => {
  Menu.setApplicationMenu(null);
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
ipcMain.handle("window:command", (_, command: "minimize" | "maximize" | "restore" | "close") => {
  if (!mainWindow) return;
  switch (command) {
    case "minimize":
      mainWindow.minimize();
      break;
    case "maximize":
      if (mainWindow.isMaximized()) {
        mainWindow.unmaximize();
      } else {
        mainWindow.maximize();
      }
      break;
    case "restore":
      if (!mainWindow.isMaximized()) mainWindow.restore();
      break;
    case "close":
      mainWindow.close();
      break;
    default:
      break;
  }
});

ipcMain.handle("window:is-maximized", () => mainWindow?.isMaximized() ?? false);
