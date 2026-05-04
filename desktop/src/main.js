const { app, BrowserWindow, ipcMain, dialog, shell } = require('electron');
const path = require('path');
const fs = require('fs');

let mainWindow;

function createWindow() {
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
    icon: path.join(__dirname, 'assets', 'icon.png'),
    title: 'Skills Manager',
    backgroundColor: '#0f172a'
  });

  // 加载本地网页
  const isDev = process.argv.includes('--dev');
  if (isDev) {
    mainWindow.loadFile(path.join(__dirname, '..', 'web', 'templates', 'index.html'));
  } else {
    mainWindow.loadFile(path.join(__dirname, '..', 'web', 'templates', 'index.html'));
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

app.on('activate', () => {
  if (mainWindow === null) {
    createWindow();
  }
});

// IPC 处理器：读取 Skills 数据
ipcMain.handle('read-skills-index', async () => {
  const indexPath = path.join(__dirname, '..', 'data', 'skills-index.json');
  try {
    const data = fs.readFileSync(indexPath, 'utf-8');
    return JSON.parse(data);
  } catch (error) {
    console.error('Error reading skills index:', error);
    return null;
  }
});

// IPC 处理器：安装 Skills 到 IDE
ipcMain.handle('install-skills', async (event, { ide, skillsPath }) => {
  const { execSync } = require('child_process');
  
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
    const sourceDir = path.join(__dirname, '..', 'data', 'all-skills');
    fs.cpSync(sourceDir, targetDir, { recursive: true });

    return { success: true, path: targetDir };
  } catch (error) {
    return { success: false, error: error.message };
  }
});

// IPC 处理器：打开外部链接
ipcMain.handle('open-external', async (event, url) => {
  await shell.openExternal(url);
});

// IPC 处理器：显示文件夹
ipcMain.handle('show-in-folder', async (event, filePath) => {
  shell.showItemInFolder(filePath);
});

// IPC 处理器：获取版本
ipcMain.handle('get-version', () => {
  return app.getVersion();
});