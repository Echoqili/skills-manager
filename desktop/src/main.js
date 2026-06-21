const { app, BrowserWindow, ipcMain, shell } = require('electron');
const path = require('path');
const fs = require('fs');
const { spawn } = require('child_process');
const http = require('http');

let mainWindow;
let backendProcess = null;

const BACKEND_PORT = process.env.SKILLS_MANAGER_PORT || '5555';

function getProjectRoot() {
  if (app.isPackaged) {
    return process.resourcesPath;
  }
  return path.resolve(__dirname, '..', '..');
}

const PROJECT_ROOT = getProjectRoot();
const WEB_DIR = path.join(PROJECT_ROOT, 'web');
const DATA_DIR = path.join(PROJECT_ROOT, 'data');
const SKILLS_ROOT = path.join(DATA_DIR, 'all-skills');
const WEB_APP = path.join(WEB_DIR, 'app.py');

function waitForBackend(retries = 60) {
  return new Promise((resolve, reject) => {
    const check = (remaining) => {
      const req = http.get({
        hostname: '127.0.0.1',
        port: BACKEND_PORT,
        path: '/api/stats',
        timeout: 1000
      }, (res) => {
        res.resume();
        if (res.statusCode && res.statusCode < 500) {
          resolve();
        } else if (remaining > 0) {
          setTimeout(() => check(remaining - 1), 300);
        } else {
          reject(new Error(`Backend responded with ${res.statusCode}`));
        }
      });

      req.on('timeout', () => req.destroy());
      req.on('error', () => {
        if (remaining > 0) {
          setTimeout(() => check(remaining - 1), 300);
        } else {
          reject(new Error('Backend did not start'));
        }
      });
    };

    check(retries);
  });
}

function startBackend() {
  if (backendProcess) {
    return;
  }

  if (!fs.existsSync(WEB_APP)) {
    throw new Error(`Web app not found: ${WEB_APP}`);
  }

  const python = process.env.PYTHON || 'python';
  backendProcess = spawn(python, [WEB_APP], {
    cwd: PROJECT_ROOT,
    env: {
      ...process.env,
      HOST: '127.0.0.1',
      PORT: BACKEND_PORT,
      FLASK_DEBUG: '0',
      PYTHONIOENCODING: 'utf-8'
    },
    windowsHide: true
  });

  if (process.argv.includes('--dev')) {
    backendProcess.stdout.on('data', (data) => console.log(`[web] ${data}`));
    backendProcess.stderr.on('data', (data) => console.error(`[web] ${data}`));
  }

  backendProcess.on('exit', () => {
    backendProcess = null;
  });
}

async function loadWebApp(window) {
  try {
    await waitForBackend(3);
  } catch {
    startBackend();
    await waitForBackend();
  }

  await window.loadURL(`http://127.0.0.1:${BACKEND_PORT}`);
}

async function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1000,
    minHeight: 700,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js')
    },
    title: 'Skills Manager',
    backgroundColor: '#0f172a'
  });

  // 加载本地网页
  try {
    await loadWebApp(mainWindow);
  } catch (error) {
    console.error('Failed to load web app:', error);
    const indexPath = path.join(WEB_DIR, 'templates', 'index.html');
    mainWindow.loadFile(indexPath);
  }

  // 开发模式打开开发者工具
  if (process.argv.includes('--dev')) {
    mainWindow.webContents.openDevTools();
  }

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

app.whenReady().then(createWindow);

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('before-quit', () => {
  if (backendProcess && !backendProcess.killed) {
    backendProcess.kill();
  }
});

app.on('activate', () => {
  if (mainWindow === null) {
    createWindow();
  }
});

// IPC 处理器：读取 Skills 索引
ipcMain.handle('read-skills-index', async () => {
  const indexPath = path.join(DATA_DIR, 'skills-index.json');
  try {
    const data = fs.readFileSync(indexPath, 'utf-8');
    return JSON.parse(data);
  } catch (error) {
    console.error('Error reading skills index:', error);
    return null;
  }
});

// IPC 处理器：读取 Skills 文件
ipcMain.handle('read-skill-file', async (event, skillPath) => {
  const fullPath = resolveSkillFile(skillPath);
  try {
    return fs.readFileSync(fullPath, 'utf-8');
  } catch (error) {
    console.error('Error reading skill file:', error);
    return null;
  }
});

// IPC 处理器：安装 Skills 到 IDE
function resolveSkillFile(skillPath) {
  if (!skillPath) {
    return null;
  }

  const normalizedPath = path.normalize(skillPath);
  if (path.isAbsolute(normalizedPath)) {
    return normalizedPath;
  }

  const dataPrefix = `data${path.sep}all-skills${path.sep}`;
  const allSkillsPrefix = `all-skills${path.sep}`;

  if (normalizedPath.startsWith(dataPrefix)) {
    return path.join(PROJECT_ROOT, normalizedPath);
  }
  if (normalizedPath.startsWith(allSkillsPrefix)) {
    return path.join(DATA_DIR, normalizedPath);
  }
  return path.join(SKILLS_ROOT, normalizedPath);
}

ipcMain.handle('install-skills', async (event, { ide, skillsPath }) => {
  const targetDirs = {
    claude: path.join(app.getPath('home'), '.claude', 'skills'),
    cursor: path.join(app.getPath('home'), '.cursor', 'skills'),
    windsurf: path.join(app.getPath('home'), '.windsurf', 'skills'),
    kiro: path.join(app.getPath('home'), '.kiro', 'skills'),
    opencode: path.join(app.getPath('home'), '.config', 'opencode', 'skills'),
    codex: path.join(app.getPath('home'), '.codex', 'skills'),
    continue: path.join(app.getPath('home'), '.continue', 'skills')
  };

  const targetDir = targetDirs[ide];
  if (!targetDir) {
    return { success: false, error: 'Unknown IDE' };
  }

  try {
    // 确保目标目录存在
    if (!fs.existsSync(targetDir)) {
      fs.mkdirSync(targetDir, { recursive: true });
    }

    // 复制 Skills 文件
    const sourceDir = SKILLS_ROOT;
    fs.cpSync(sourceDir, targetDir, { recursive: true });

    return { success: true, path: targetDir };
  } catch (error) {
    console.error('Error installing skills:', error);
    return { success: false, error: error.message };
  }
});

// IPC 处理器：打开外部链接
ipcMain.handle('open-external', async (event, url) => {
  await shell.openExternal(url);
});

// IPC 处理器：显示文件夹
ipcMain.handle('show-in-folder', async (event, filePath) => {
  const fullPath = path.join(DATA_DIR, filePath);
  shell.showItemInFolder(fullPath);
});

// IPC 处理器：获取版本
ipcMain.handle('get-version', () => {
  return app.getVersion();
});
