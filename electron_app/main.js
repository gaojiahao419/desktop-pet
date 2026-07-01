const { app, BrowserWindow, Menu, dialog, ipcMain } = require("electron");
const path = require("path");

const WINDOW_TITLE = "桌面宠物控制台";

function parseControlUrl() {
  const index = process.argv.indexOf("--control-url");
  if (index >= 0 && process.argv[index + 1]) {
    return process.argv[index + 1];
  }
  return process.env.DESKTOP_PET_CONTROL_URL || "http://127.0.0.1:0";
}

const controlUrl = parseControlUrl();
let mainWindow = null;
let quitRequested = false;

async function requestPythonQuit() {
  if (quitRequested) {
    return;
  }
  quitRequested = true;
  try {
    await fetch(`${controlUrl}/api/quit`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    });
  } catch (_error) {
    return;
  }
}

function focusMainWindow() {
  if (!mainWindow) {
    return;
  }
  if (mainWindow.isMinimized()) {
    mainWindow.restore();
  }
  mainWindow.show();
  mainWindow.focus();
}

function createWindow() {
  Menu.setApplicationMenu(null);
  mainWindow = new BrowserWindow({
    title: WINDOW_TITLE,
    width: 1480,
    height: 900,
    minWidth: 1180,
    minHeight: 760,
    backgroundColor: "#0b0f10",
    autoHideMenuBar: true,
    menuBarVisible: false,
    show: false,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  });

  mainWindow.loadFile(path.join(__dirname, "..", "web_control_panel", "index.html"), {
    query: { api: controlUrl },
  });
  mainWindow.once("ready-to-show", focusMainWindow);
  mainWindow.on("close", () => {
    requestPythonQuit();
  });
  mainWindow.on("closed", () => {
    mainWindow = null;
  });
}

const gotSingleInstanceLock = app.requestSingleInstanceLock({ controlUrl });

if (!gotSingleInstanceLock) {
  app.quit();
} else {
  app.on("second-instance", focusMainWindow);

  ipcMain.handle("desktop-pet:choose-video", async () => {
    const result = await dialog.showOpenDialog(mainWindow, {
      title: "选择动作 MP4 素材",
      filters: [{ name: "MP4 视频", extensions: ["mp4"] }],
      properties: ["openFile"],
    });
    if (result.canceled || result.filePaths.length === 0) {
      return "";
    }
    return result.filePaths[0];
  });

  ipcMain.on("desktop-pet:quit-shell", () => {
    quitRequested = true;
    app.quit();
  });

  app.whenReady().then(createWindow);

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    } else {
      focusMainWindow();
    }
  });

  app.on("window-all-closed", () => {
    if (process.platform !== "darwin") {
      app.quit();
    }
  });
}
