import { contextBridge, ipcRenderer } from 'electron';

/**
 * Preload script - exposes safe APIs to the renderer process
 * This runs in an isolated context with access to both Node and DOM APIs
 */

// Expose Electron APIs to the renderer
contextBridge.exposeInMainWorld('electronAPI', {
  /**
   * Hide the launcher window
   */
  hideWindow: () => {
    ipcRenderer.send('hide-window');
  },

  /**
   * Lock window visibility (prevents blur from hiding during query processing)
   */
  lockWindow: () => {
    ipcRenderer.send('lock-window');
  },

  /**
   * Unlock window visibility (allows blur to hide again)
   */
  unlockWindow: () => {
    ipcRenderer.send('unlock-window');
  },

  /**
   * Reveal a file in Finder
   */
  revealInFinder: (filePath: string) => {
    ipcRenderer.send('reveal-finder', filePath);
  },

  /**
   * Open a URL in the default browser
   */
  openExternal: (url: string) => {
    ipcRenderer.send('open-external', url);
  },

  /**
   * Open an application by name
   */
  openApp: (appName: string) => {
    return new Promise((resolve, reject) => {
      ipcRenderer.send('open-app', appName);

      ipcRenderer.once('open-app-result', (event, result) => {
        if (result.success) {
          resolve(result);
        } else {
          reject(new Error(result.error));
        }
      });
    });
  },

  /**
   * Listen for window shown event
   */
  onWindowShown: (callback: () => void) => {
    ipcRenderer.on('window-shown', callback);
  },

  /**
   * Listen for window hidden event (user clicked away - Spotlight behavior)
   */
  onWindowHidden: (callback: () => void) => {
    ipcRenderer.on('window-hidden', callback);
  },

  /**
   * Open expanded desktop view (ChatGPT-style full window)
   */
  openExpandedWindow: () => {
    ipcRenderer.send('open-expanded-window');
  },

  /**
   * Collapse back to spotlight view
   */
  collapseToSpotlight: () => {
    ipcRenderer.send('collapse-to-spotlight');
  },

  /**
   * Listen for open preferences event
   */
  onOpenPreferences: (callback: () => void) => {
    ipcRenderer.on('open-preferences', callback);
  },

  /**
   * Get current settings
   */
  getSettings: () => {
    return ipcRenderer.invoke('get-settings');
  },

  /**
   * Update settings
   */
  updateSettings: (settings: any) => {
    return new Promise((resolve) => {
      ipcRenderer.send('update-settings', settings);
      ipcRenderer.once('settings-updated', (event, result) => {
        resolve(result);
      });
    });
  },

  /**
   * Get window state for diagnostics
   */
  getWindowState: () => {
    return ipcRenderer.invoke('get-window-state');
  },

  /**
   * DIAGNOSTIC: Force window visible (emergency recovery)
   */
  forceWindowVisible: () => {
    return ipcRenderer.invoke('force-window-visible');
  }
});

// Window state interface for diagnostics
export interface WindowState {
  visible: boolean;
  focused: boolean;
  bounds: { x: number; y: number; width: number; height: number } | null;
  lastShowAttempt: number;
  lastHideAttempt: number;
  showCount: number;
  hideCount: number;
  blurCount: number;
  focusCount: number;
  mainWindowExists: boolean;
  isDestroyed: boolean;
  locked: boolean;
  timestamp: number;
}

// Type definitions for TypeScript (to be used in renderer)
export interface ElectronAPI {
  hideWindow: () => void;
  lockWindow: () => void;
  unlockWindow: () => void;
  openExpandedWindow: () => void;
  collapseToSpotlight: () => void;
  revealInFinder: (filePath: string) => void;
  openExternal: (url: string) => void;
  openApp: (appName: string) => Promise<{ success: boolean }>;
  onWindowShown: (callback: () => void) => void;
  onWindowHidden: (callback: () => void) => void;
  onOpenPreferences: (callback: () => void) => void;
  getSettings: () => Promise<any>;
  updateSettings: (settings: any) => Promise<any>;
  getWindowState: () => Promise<WindowState>;
  forceWindowVisible: () => Promise<{ success: boolean; before?: any; after?: any; error?: string }>;
}

// Extend Window interface
declare global {
  interface Window {
    electronAPI?: ElectronAPI;
  }
}
