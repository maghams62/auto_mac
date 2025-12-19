/**
 * Electron API type definitions for renderer process
 * These APIs are exposed via the preload script
 */

export interface Settings {
  hotkey: string;
  hideOnBlur: boolean;
  startAtLogin: boolean;
  theme: 'dark' | 'light' | 'auto';
  miniConversationDepth: number;
}

/**
 * Window state for diagnostics
 */
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

export interface ElectronAPI {
  /**
   * Hide the launcher window
   */
  hideWindow: () => void;

  /**
   * Lock window visibility (prevents blur from hiding during query processing)
   */
  lockWindow: () => void;

  /**
   * Unlock window visibility (allows blur to hide again)
   */
  unlockWindow: () => void;

  /**
   * Reveal a file in Finder
   */
  revealInFinder: (filePath: string) => void;

  /**
   * Open a URL in the default browser
   */
  openExternal: (url: string) => void;

  /**
   * Open an application by name
   */
  openApp: (appName: string) => Promise<{ success: boolean }>;

  /**
   * Listen for window shown event
   */
  onWindowShown: (callback: () => void) => void;

  /**
   * Listen for window hidden event (user clicked away - Spotlight behavior)
   */
  onWindowHidden: (callback: () => void) => void;

  /**
   * Open expanded desktop view (ChatGPT-style full window)
   */
  openExpandedWindow: () => void;

  /**
   * Collapse back to spotlight view
   */
  collapseToSpotlight: () => void;

  /**
   * Listen for open preferences event
   */
  onOpenPreferences: (callback: () => void) => void;

  /**
   * Get current settings
   */
  getSettings: () => Promise<Settings>;

  /**
   * Update settings
   */
  updateSettings: (settings: Partial<Settings>) => Promise<{ success: boolean }>;

  /**
   * Get window state for diagnostics
   */
  getWindowState: () => Promise<WindowState>;

  /**
   * Force window visible (emergency recovery for stuck hidden state)
   */
  forceWindowVisible: () => Promise<{ success: boolean; before?: any; after?: any; error?: string }>;
}

// Extend the Window interface
declare global {
  interface Window {
    electronAPI?: ElectronAPI;
  }
}

export {};
