const { app, BrowserWindow, Tray, Menu, ipcMain } = require('electron');
const path = require('path');
const { spawn } = require('child_process');

let mainWindow;
let tray;
let nodeProcess;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    title: "OctaOS Enterprise AI Workspace",
    icon: path.join(__dirname, 'icon.png'),
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false
    }
  });

  // Load Next.js web application (or local production build)
  const appUrl = process.env.ELECTRON_START_URL || 'http://localhost:3000';
  mainWindow.loadURL(appUrl);

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

function startBackendNodeDaemon() {
  console.log('[OctaOS Desktop] Starting embedded backend daemon...');
  // Spawn octaos-node binary or python module
  nodeProcess = spawn('python3', ['-m', 'app.node.octaos_node', '--mode', 'SEMI_AUTONOMOUS'], {
    cwd: path.join(__dirname, '../../')
  });

  nodeProcess.stdout.on('data', (data) => {
    console.log(`[OctaOS Node] ${data}`);
  });

  nodeProcess.stderr.on('data', (data) => {
    console.error(`[OctaOS Node Err] ${data}`);
  });
}

function createSystemTray() {
  tray = new Tray(path.join(__dirname, 'tray_icon.png'));
  const contextMenu = Menu.buildFromTemplate([
    { label: 'Open OctaOS Workspace', click: () => { mainWindow.show(); } },
    { label: 'Node Status: Active', enabled: false },
    { type: 'separator' },
    { label: 'Quit OctaOS', click: () => { app.quit(); } }
  ]);
  tray.setToolTip('OctaOS Autonomous AI Workspace');
  tray.setContextMenu(contextMenu);
}

app.on('ready', () => {
  startBackendNodeDaemon();
  createWindow();
  createSystemTray();
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('will-quit', () => {
  if (nodeProcess) {
    nodeProcess.kill();
  }
});
