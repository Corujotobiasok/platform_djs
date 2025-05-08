const { app, BrowserWindow, Menu, ipcMain } = require('electron');
const path = require('path');

let win;

function createWindow () {
  win = new BrowserWindow({
    width: 900,
    height: 600,
    resizable: false,
    maximizable: false,
    fullscreenable: false,
    frame: false, // ❗️Quita la barra nativa (reemplazaremos con personalizada)
    webPreferences: {
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js') // Para comunicar frontend <-> backend
    }
  });

  win.loadFile(path.join(__dirname, 'templates', 'index.html'));

  Menu.setApplicationMenu(null); // Elimina la barra de menú superior
}

app.whenReady().then(createWindow);

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

// Control de botones personalizados
ipcMain.on('window-minimize', () => {
  win.minimize();
});

ipcMain.on('window-maximize', () => {
  if (win.isMaximized()) {
    win.unmaximize();
  } else {
    win.maximize();
  }
});

ipcMain.on('window-close', () => {
  win.close();
});
