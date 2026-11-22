'use strict';
const { app, BrowserWindow, WebContentsView, ipcMain, shell, dialog, session, Menu } = require('electron');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const { Connector } = require('./connector');
const policy = require('./security');
const ONLINE = 'http://81.70.101.100:18083';
const SHELL_FILE = path.join(__dirname, 'shell.html');
const SHELL_URL = pathToFileURL(SHELL_FILE).href;
let window, connector, quitting = false, allowQuit = false, onlineView, localView;
let selected = 'online', localOrigin = null;
let state = { selected, online: 'idle', local: 'idle', version: app.getVersion(), errors: { online: '', local: '' } };

if (process.env.SKILLS_MANAGER_USER_DATA && path.isAbsolute(process.env.SKILLS_MANAGER_USER_DATA)) app.setPath('userData', process.env.SKILLS_MANAGER_USER_DATA);
if (!app.requestSingleInstanceLock()) app.quit();
else {
  app.on('second-instance', () => { if (window) { if (window.isMinimized()) window.restore(); window.focus(); } });
  app.whenReady().then(createWindow).catch(error => { console.error('Desktop startup failed:', error); dialog.showErrorBox('Skills Manager 启动失败', error.message); app.quit(); });
}
function update(patch = {}) {
  state = { ...state, ...patch, selected };
  if (window && !window.isDestroyed()) window.webContents.send('desktop:state', state);
}
function failed(kind, message) {
  update({ [kind]: 'error', errors: { ...state.errors, [kind]: message } });
  layout();
}
function layout() {
  if (!window || window.isDestroyed()) return;
  const [width, height] = window.getContentSize();
  for (const [name, view] of [['online', onlineView], ['local', localView]]) {
    if (!view) continue;
    view.setVisible(selected === name && state[name] === 'ready');
    view.setBounds({ x: 208, y: 76, width: Math.max(0, width - 208), height: Math.max(0, height - 76) });
  }
}
async function external(url) { if (policy.externalAllowed(url)) await shell.openExternal(url); }
function secureView(view, origin) {
  const contents = view.webContents;
  contents.setWindowOpenHandler(({ url }) => { external(url).catch(() => {}); return { action: 'deny' }; });
  contents.on('will-navigate', (event, url) => {
    if (!policy.sameOrigin(url, origin())) { event.preventDefault(); external(url).catch(() => {}); }
  });
  contents.on('will-redirect', (event, url) => { if (!policy.sameOrigin(url, origin())) event.preventDefault(); });
  contents.on('will-attach-webview', event => event.preventDefault());
}
function configureSession(name, allowed) {
  const ses = session.fromPartition(name);
  ses.setPermissionRequestHandler((_contents, _permission, callback) => callback(false));
  ses.setPermissionCheckHandler(() => false);
  ses.webRequest.onBeforeRequest((details, callback) => callback({ cancel: !allowed(details.url) }));
  ses.on('will-download', (event, item, contents) => {
    if (!contents || contents !== onlineView?.webContents || !policy.sameOrigin(item.getURL(), ONLINE)) event.preventDefault();
  });
  return ses;
}
async function show(kind, force = false) {
  if (quitting) return;
  if (!['online', 'local'].includes(kind)) throw new Error('未知页面');
  selected = kind; update(); layout();
  if (state[kind] === 'ready' && !force) return;
  if (state[kind] === 'loading') return;
  update({ [kind]: 'loading', errors: { ...state.errors, [kind]: '' } }); layout();
  try {
    if (kind === 'online') await onlineView.webContents.loadURL(ONLINE);
    else {
      const info = await connector.start();
      if (quitting) { await connector.stop(); return; }
      localOrigin = 'http://127.0.0.1:' + info.port;
      await localView.webContents.loadURL(localOrigin + '/#' + info.token);
    }
    update({ [kind]: 'ready' });
  } catch {
    failed(kind, kind === 'online' ? '在线技能库暂时无法连接。可重试，或进入本机工作区。' : '本机连接未能启动。请重试；关闭应用后重新打开也可恢复连接。');
  }
  layout();
}
async function createWindow() {
  Menu.setApplicationMenu(null);
  window = new BrowserWindow({
    width: 1440, height: 960, minWidth: 1000, minHeight: 700, title: 'Skills Manager 桌面版', backgroundColor: '#111827', show: false,
    webPreferences: { preload: path.join(__dirname, 'preload.js'), contextIsolation: true, nodeIntegration: false, sandbox: true, webviewTag: false },
  });
  const onlineSession = configureSession('persist:skills-library-v2', url => policy.onlineRequestAllowed(url, ONLINE));
  const localSession = configureSession('skills-local-v2', url => policy.sameOrigin(url, localOrigin));
  const preferences = { contextIsolation: true, nodeIntegration: false, sandbox: true, webviewTag: false, webSecurity: true, allowRunningInsecureContent: false };
  onlineView = new WebContentsView({ webPreferences: { ...preferences, session: onlineSession } });
  localView = new WebContentsView({ webPreferences: { ...preferences, session: localSession } });
  onlineView.setVisible(false); localView.setVisible(false);
  window.contentView.addChildView(onlineView); window.contentView.addChildView(localView);
  secureView(onlineView, () => ONLINE); secureView(localView, () => localOrigin);
  const command = app.isPackaged
    ? [path.join(process.resourcesPath, 'connector', 'SkillsManagerConnector.exe')]
    : [path.resolve(__dirname, '../../.uploads/installer-build/dist/SkillsManagerConnector.exe')];
  connector = new Connector({ command, sessionFile: path.join(app.getPath('userData'), 'connector', 'session.json'), onExit: () => {
    localOrigin = null; failed('local', '本机连接已关闭，点击重试可重新启动。');
  } });
  window.webContents.setWindowOpenHandler(() => ({ action: 'deny' }));
  window.webContents.on('will-navigate', (event, url) => { if (url !== SHELL_URL) event.preventDefault(); });
  window.webContents.on('will-redirect', event => event.preventDefault());
  window.on('resize', layout); window.on('closed', () => { window = null; });
  window.on('close', event => {
    if (!allowQuit) { event.preventDefault(); app.quit(); }
  });
  for (const view of [onlineView, localView]) view.webContents.on('render-process-gone', () => {
    const kind = view === onlineView ? 'online' : 'local';
    failed(kind, '页面意外退出，点击重试可重新加载。');
  });
  await window.loadFile(SHELL_FILE); layout(); window.show();
  void show('online');
}
function requireShell(event) {
  if (!policy.trustedSender(event, window?.webContents) || event.senderFrame.url !== SHELL_URL) throw new Error('不允许此页面调用桌面接口');
}
ipcMain.handle('desktop:get-state', event => { requireShell(event); return state; });
ipcMain.handle('desktop:select', async (event, kind) => { requireShell(event); await show(kind); return state; });
ipcMain.handle('desktop:reload', async event => { requireShell(event); await show(selected, true); return state; });
app.on('window-all-closed', () => app.quit());
app.on('before-quit', event => {
  if (allowQuit) return;
  event.preventDefault();
  if (quitting) return;
  quitting = true;
  Promise.resolve(connector?.stop()).finally(() => {
    allowQuit = true;
    for (const view of [onlineView, localView]) if (view && !view.webContents.isDestroyed()) view.webContents.close();
    app.quit();
  });
});
