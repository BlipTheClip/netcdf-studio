import { app, BrowserWindow, shell, ipcMain, dialog } from "electron";
import { spawn, ChildProcess } from "child_process";
import path from "path";
import http from "http";

const isDev = !app.isPackaged;
const BACKEND_PORT = 8000;
const HEALTH_URL = `http://localhost:${BACKEND_PORT}/api/health`;

let mainWindow: BrowserWindow | null = null;
let backendProcess: ChildProcess | null = null;

// ─── Python / backend location ─────────────────────────────────────────────

function resolvePython(): string {
  if (isDev) {
    return process.platform === "win32" ? "python" : "python3";
  }
  const base = path.join(process.resourcesPath, "backend-env");
  return process.platform === "win32"
    ? path.join(base, "python.exe")
    : path.join(base, "bin", "python3");
}

function resolveRepoRoot(): string {
  // In dev: dist-electron/ → frontend/ → repo root
  return isDev
    ? path.join(__dirname, "..", "..")
    : process.resourcesPath;
}

// ─── Backend process ────────────────────────────────────────────────────────

function startBackend(): void {
  const python = resolvePython();
  const repoRoot = resolveRepoRoot();

  backendProcess = spawn(
    python,
    ["-m", "uvicorn", "backend.main:app", "--port", String(BACKEND_PORT), "--no-access-log"],
    {
      cwd: repoRoot,
      env: {
        ...process.env,
        PYTHONUTF8: "1",
        ...(isDev ? { PYTHONPATH: repoRoot } : {}),
      },
      stdio: ["ignore", "pipe", "pipe"],
    },
  );

  backendProcess.stdout?.on("data", (d: Buffer) =>
    process.stdout.write(`[backend] ${d.toString()}`),
  );
  backendProcess.stderr?.on("data", (d: Buffer) =>
    process.stderr.write(`[backend] ${d.toString()}`),
  );
  backendProcess.on("exit", (code) => {
    console.error(`[backend] exited with code ${code}`);
  });
}

// ─── Health polling ─────────────────────────────────────────────────────────

function pollHealth(maxAttempts: number, delayMs: number): Promise<void> {
  return new Promise((resolve, reject) => {
    let attempts = 0;

    const check = () => {
      const req = http.get(HEALTH_URL, (res) => {
        if (res.statusCode === 200) resolve();
        else retry();
      });
      req.on("error", retry);
      req.end();
    };

    const retry = () => {
      attempts++;
      if (attempts >= maxAttempts) {
        reject(new Error(`Backend did not respond after ${maxAttempts} attempts`));
        return;
      }
      setTimeout(check, delayMs);
    };

    check();
  });
}

// ─── Window ─────────────────────────────────────────────────────────────────

async function createWindow(): Promise<void> {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 960,
    minHeight: 600,
    show: false,
    backgroundColor: "#0f172a",
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, "preload.js"),
    },
    titleBarStyle: process.platform === "darwin" ? "hiddenInset" : "default",
    title: "NetCDF Studio",
  });

  if (isDev) {
    await mainWindow.loadURL("http://localhost:5173");
    mainWindow.webContents.openDevTools();
  } else {
    await mainWindow.loadFile(path.join(__dirname, "..", "dist", "index.html"));
  }

  mainWindow.once("ready-to-show", () => mainWindow?.show());

  // Open external links in the OS browser, not Electron
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: "deny" };
  });

  mainWindow.on("closed", () => {
    mainWindow = null;
  });
}

// ─── App lifecycle ───────────────────────────────────────────────────────────

app.whenReady().then(async () => {
  startBackend();

  try {
    await pollHealth(30, 1000);
  } catch {
    const choice = dialog.showMessageBoxSync({
      type: "error",
      title: "Backend failed to start",
      message:
        "The Python backend did not respond within 30 seconds.\n\n" +
        "Make sure the netcdf-studio conda environment is activated.",
      buttons: ["Quit", "Open anyway"],
      defaultId: 0,
    });
    if (choice === 0) {
      app.quit();
      return;
    }
  }

  await createWindow();

  app.on("activate", async () => {
    if (BrowserWindow.getAllWindows().length === 0) await createWindow();
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});

app.on("before-quit", () => {
  if (backendProcess && !backendProcess.killed) {
    backendProcess.kill("SIGTERM");
  }
});

// ─── IPC: native file dialogs ────────────────────────────────────────────────

ipcMain.handle("dialog:openFile", async () => {
  const result = await dialog.showOpenDialog({
    filters: [{ name: "NetCDF", extensions: ["nc", "nc4", "netcdf"] }],
    properties: ["openFile"],
  });
  return result.canceled ? null : result.filePaths[0] ?? null;
});

ipcMain.handle("dialog:saveFile", async (_event, defaultName: string) => {
  const result = await dialog.showSaveDialog({
    defaultPath: defaultName,
    filters: [{ name: "NetCDF", extensions: ["nc"] }],
  });
  return result.canceled ? null : result.filePath ?? null;
});
