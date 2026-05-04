const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  readSkillsIndex: () => ipcRenderer.invoke('read-skills-index'),
  installSkills: (options) => ipcRenderer.invoke('install-skills', options),
  openExternal: (url) => ipcRenderer.invoke('open-external', url),
  showInFolder: (filePath) => ipcRenderer.invoke('show-in-folder', filePath),
  getVersion: () => ipcRenderer.invoke('get-version')
});