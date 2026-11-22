'use strict';
const { contextBridge, ipcRenderer } = require('electron');
contextBridge.exposeInMainWorld('desktop', {
  state: () => ipcRenderer.invoke('desktop:get-state'),
  select: kind => ipcRenderer.invoke('desktop:select', kind),
  reload: () => ipcRenderer.invoke('desktop:reload'),
  onState: callback => { ipcRenderer.on('desktop:state', (_event, state) => callback(state)); },
});
