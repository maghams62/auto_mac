import { app, BrowserWindow, globalShortcut, Tray, Menu, ipcMain, screen, shell } from 'electron';
import { spawn, ChildProcess, exec } from 'child_process';
import * as path from 'path';
import * as fs from 'fs';
import * as net from 'net';
import * as http from 'http';
import * as util from 'util';
import Store from 'electron-store';

const execAsync = util.promisify(exec);

/**
 * Make an HTTP GET request using Node's http module (more reliable than fetch in Electron main process)
 */
function httpGet(url: string, timeoutMs: number = 2000): Promise<{ ok: boolean; status: number; body: string }> {
  return new Promise((resolve, reject) => {
    const urlObj = new URL(url);
    const options = {
      hostname: urlObj.hostname,
      port: urlObj.port || 80,
      path: urlObj.pathname + urlObj.search,
      method: 'GET',
      timeout: timeoutMs,
    };

    const req = http.request(options, (res) => {
      let body = '';
      res.on('data', (chunk) => body += chunk);
      res.on('end', () => {
        resolve({
          ok: res.statusCode !== undefined && res.statusCode >= 200 && res.statusCode < 300,
          status: res.statusCode || 0,
          body
        });
      });
    });

    req.on('error', (err) => {
      reject(err);
    });

    req.on('timeout', () => {
      req.destroy();
      reject(new Error('Request timeout'));
    });

    req.end();
  });
}

/**
 * Structured logger for Electron main process
 * Writes logs to file and console with levels, timestamps, and context
 */
enum LogLevel {
  DEBUG = 0,
  INFO = 1,
  WARN = 2,
  ERROR = 3,
}

class Logger {
  private logFile: string;
  private logStream: fs.WriteStream | null = null;
  private minLevel: LogLevel;
  private processId: number;
  private consoleWritable = true;
  private fileWritable = true;

  constructor(logDir: string, minLevel: LogLevel = LogLevel.INFO) {
    this.minLevel = minLevel;
    this.processId = process.pid;

    // Ensure log directory exists
    fs.mkdirSync(logDir, { recursive: true });

    // Create log file with timestamp
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
    this.logFile = path.join(logDir, `cerebros-${timestamp}.log`);

    // Create write stream
    this.logStream = fs.createWriteStream(this.logFile, { flags: 'a' });
    this.logStream.on('error', (err) => {
      this.fileWritable = false;
      this.consoleFallback('warn', '[LOGGER] File stream error, disabling file logging', err);
    });

    // Write initial log entry
    this.writeLog(LogLevel.INFO, 'Logger initialized', {
      logFile: this.logFile,
      processId: this.processId,
      nodeVersion: process.version,
      electronVersion: process.versions.electron,
      platform: process.platform,
    });
  }

  private formatMessage(level: string, message: string, context?: Record<string, any>): string {
    const timestamp = new Date().toISOString();
    const contextStr = context ? ` ${JSON.stringify(context)}` : '';
    return `[${timestamp}] [${level}] [PID:${this.processId}] ${message}${contextStr}\n`;
  }

  private writeLog(level: LogLevel, message: string, context?: Record<string, any>): void {
    if (level < this.minLevel) return;

    const levelName = LogLevel[level];
    const formatted = this.formatMessage(levelName, message, context);

    // Write to file
    if (this.logStream) {
      if (this.fileWritable) {
        try {
      this.logStream.write(formatted);
        } catch (err: any) {
          this.fileWritable = false;
          this.consoleFallback('warn', '[LOGGER] Failed to write log file, disabling file logging', err);
        }
      }
    }

    // Write to console with appropriate method
    const consoleMessage = `[${levelName}] ${message}`;
    if (this.consoleWritable) {
      try {
    switch (level) {
      case LogLevel.DEBUG:
        console.debug(consoleMessage, context || '');
        break;
      case LogLevel.INFO:
        console.info(consoleMessage, context || '');
        break;
      case LogLevel.WARN:
        console.warn(consoleMessage, context || '');
        break;
      case LogLevel.ERROR:
        console.error(consoleMessage, context || '');
        break;
        }
      } catch (err: any) {
        if (this.isStdioWriteError(err)) {
          this.consoleWritable = false;
          this.safeFileOnly('[LOGGER] Console unavailable, muting console output', { error: err?.message });
        } else {
          throw err;
        }
      }
    }
  }
  private isStdioWriteError(err: any): boolean {
    if (!err) return false;
    return err.code === 'EPIPE' || err.code === 'EIO';
  }

  private consoleFallback(method: 'info' | 'warn' | 'error', message: string, err?: Error) {
    try {
      console[method](message, err ? { error: err.message } : '');
    } catch {
      // Ignore - stdout might already be closed
    }
  }

  private safeFileOnly(message: string, context?: Record<string, any>) {
    if (this.fileWritable && this.logStream) {
      try {
        const formatted = this.formatMessage('WARN', message, context);
        this.logStream.write(formatted);
      } catch {
        // ignore
      }
    }
  }

  debug(message: string, context?: Record<string, any>): void {
    this.writeLog(LogLevel.DEBUG, message, context);
  }

  info(message: string, context?: Record<string, any>): void {
    this.writeLog(LogLevel.INFO, message, context);
  }

  warn(message: string, context?: Record<string, any>): void {
    this.writeLog(LogLevel.WARN, message, context);
  }

  error(message: string, error?: Error | any, context?: Record<string, any>): void {
    const errorContext: Record<string, any> = { ...context };
    if (error instanceof Error) {
      errorContext.error = {
        name: error.name,
        message: error.message,
        stack: error.stack,
      };
    } else if (error) {
      errorContext.error = String(error);
    }
    this.writeLog(LogLevel.ERROR, message, errorContext);
  }

  close(): void {
    if (this.logStream) {
      this.logStream.end();
      this.logStream = null;
    }
  }

  getLogFile(): string {
    return this.logFile;
  }
}

// Logger will be initialized after app is ready
let logger: Logger | null = null;

type StartupEventRecord = {
  label: string;
  timestamp: number;
  elapsedMs: number;
  context?: Record<string, any>;
};
const startupTimeline: StartupEventRecord[] = [];
let startupBaseTimestamp = Date.now();

function markStartup(label: string, context?: Record<string, any>) {
  const now = Date.now();
  if (startupTimeline.length === 0) {
    startupBaseTimestamp = now;
  }
  const elapsedMs = now - startupBaseTimestamp;
  startupTimeline.push({ label, timestamp: now, elapsedMs, context });
  const payload = { elapsedMs, ...(context || {}) };
  if (logger) {
    logger.info(`[STARTUP] ${label}`, payload);
  } else {
    console.log(`[STARTUP] ${label}`, payload);
  }
}

function emitStartupSummary(stage: string) {
  const events = startupTimeline.map(({ label, elapsedMs, context }) => ({
    label,
    elapsedMs,
    ...(context ? { context } : {})
  }));
  if (logger) {
    logger.info('[STARTUP] Timeline summary', { stage, events });
  } else {
    console.log('[STARTUP] Timeline summary', { stage, events });
  }
}

// Backend output buffer to capture startup messages for diagnostics
const backendOutputBuffer: { type: 'stdout' | 'stderr'; timestamp: string; data: string }[] = [];
const MAX_BUFFER_LINES = 100;

function addToBackendBuffer(type: 'stdout' | 'stderr', data: string) {
  const lines = data.split('\n').filter(line => line.trim());
  for (const line of lines) {
    backendOutputBuffer.push({
      type,
      timestamp: new Date().toISOString(),
      data: line
    });
    // Keep only the last N lines
    if (backendOutputBuffer.length > MAX_BUFFER_LINES) {
      backendOutputBuffer.shift();
    }
  }
}

function getBackendBufferSummary(): string {
  if (backendOutputBuffer.length === 0) {
    return 'No backend output captured';
  }
  return backendOutputBuffer
    .map(entry => `[${entry.timestamp}] [${entry.type.toUpperCase()}] ${entry.data}`)
    .join('\n');
}

function getLogger(): Logger {
  if (!logger) {
    // In dev mode, also write logs to project root for easy access
    const logDir = isDev 
      ? path.join(rootDir, 'logs', 'electron')
      : path.join(app.getPath('userData'), 'logs');
    logger = new Logger(logDir, isDev ? LogLevel.DEBUG : LogLevel.INFO);
    
    // Log the log file location prominently
    console.log('========================================');
    console.log('[Cerebros] LOG FILE:', logger.getLogFile());
    console.log('========================================');
  }
  return logger;
}

// Settings interface
interface Settings {
  hotkey: string;
  hideOnBlur: boolean;
  startAtLogin: boolean;
  theme: 'dark' | 'light' | 'auto';
  miniConversationDepth: number;
}

// Settings store - initialized after app.ready to avoid calling app.getPath() before ready
let store: Store<Settings> | null = null;

function getStore(): Store<Settings> {
  if (!store) {
    if (!app.isReady()) {
      throw new Error('Attempted to access settings store before Electron app was ready');
    }

    store = new Store<Settings>({
      defaults: {
        hotkey: 'CommandOrControl+Option+K', // Option for macOS
        hideOnBlur: true,
        startAtLogin: false,
        theme: 'dark',
        miniConversationDepth: 2,
      }
    });
  }
  return store;
}

function migrateLegacyHotkey(settingsStore: Store<Settings>) {
  const existingHotkey = settingsStore.get('hotkey');
  if (
    existingHotkey === 'CommandOrControl+Alt+Space' || // original default
    existingHotkey === 'CommandOrControl+C' ||         // experimental default
    existingHotkey === 'CommandOrControl+Shift+K'      // previous safe default
  ) {
    settingsStore.set('hotkey', 'CommandOrControl+Alt+K');
  }
}

// Window visibility lock - prevents blur from hiding during query processing
let windowVisibilityLocked = false;

const SHOW_GRACE_PERIOD_MS = 250;
const TOGGLE_DEBOUNCE_MS = 220;
const WINDOW_FADE_DURATION_MS = 120;

type ToggleSource = 'globalShortcut' | 'tray' | 'trayMenu' | 'ipc' | 'system' | 'selfTest';
type HideReason = 'blur' | 'toggle' | 'selfTest' | 'ipc' | 'system';

const lastToggleBySource: Record<ToggleSource, number> = {
  globalShortcut: 0,
  tray: 0,
  trayMenu: 0,
  ipc: 0,
  system: 0,
  selfTest: 0,
};

let showGraceTimer: NodeJS.Timeout | null = null;
let showGraceActive = false;

/**
 * CRITICAL: Window Visibility Lock System
 *
 * Lock window visibility (prevent blur from hiding)
 * Call this when starting a query/command
 *
 * CONTRACT:
 * - MUST be called BEFORE starting async operations (query, voice recording, etc.)
 * - MUST have matching unlockWindowVisibility() call after operation completes
 * - MUST unlock even on error paths (use try/finally)
 *
 * Used by:
 * - showWindow() - Line 1206 (locks during show process)
 * - Frontend CommandPalette.tsx:362 (locks on query submit)
 * - Frontend CommandPalette.tsx:170 (locks on voice start)
 *
 * See CRITICAL_BEHAVIOR.md Section 1 for complete documentation.
 * DO NOT MODIFY without reading state machine documentation.
 */
function lockWindowVisibility() {
  windowVisibilityLocked = true;
  const logger = getLogger();
  if (logger) {
    logger.debug('[LAUNCHER] Window visibility locked - blur will not hide');
  }
}

/**
 * CRITICAL: Window Visibility Unlock System
 *
 * Unlock window visibility (allow blur to hide again)
 * Call this when query/command is complete
 *
 * CONTRACT:
 * - MUST be called after EVERY lockWindowVisibility() call
 * - MUST be called in success AND error paths
 * - MUST be called in finally blocks or cleanup handlers
 *
 * Called by:
 * - startShowGracePeriod() - Line 364 (after grace period ends)
 * - Frontend CommandPalette.tsx - Multiple locations after processing
 * - Frontend launcher/page.tsx:34,48 (fail-safe on window events)
 *
 * See CRITICAL_BEHAVIOR.md Section 1 for complete documentation.
 * DO NOT MODIFY without reading state machine documentation.
 */
function unlockWindowVisibility() {
  windowVisibilityLocked = false;
  if (showGraceTimer) {
    clearTimeout(showGraceTimer);
    showGraceTimer = null;
  }
  showGraceActive = false;
  const logger = getLogger();
  if (logger) {
    logger.debug('[LAUNCHER] Window visibility unlocked - blur can hide');
  }
}

// Window state tracking for telemetry and debugging
interface WindowState {
  visible: boolean;
  focused: boolean;
  bounds: Electron.Rectangle | null;
  lastShowAttempt: number;
  lastHideAttempt: number;
  showCount: number;
  hideCount: number;
  blurCount: number;
  focusCount: number;
  lastBlurTimestamp: number;
  lastToggleTimestamp: number;
  lastToggleSource: ToggleSource | null;
  lastHideReason: HideReason | null;
  lastShowSource: ToggleSource | null;
  graceActive: boolean;
}

const windowState: WindowState = {
  visible: false,
  focused: false,
  bounds: null,
  lastShowAttempt: 0,
  lastHideAttempt: 0,
  showCount: 0,
  hideCount: 0,
  blurCount: 0,
  focusCount: 0,
  lastBlurTimestamp: 0,
  lastToggleTimestamp: 0,
  lastToggleSource: null,
  lastHideReason: null,
  lastShowSource: null,
  graceActive: false,
};

/**
 * Update window state from current window
 */
function updateWindowState(): void {
  if (!mainWindow || mainWindow.isDestroyed()) {
    windowState.visible = false;
    windowState.focused = false;
    windowState.bounds = null;
    windowState.graceActive = showGraceActive;
    return;
  }
  windowState.visible = mainWindow.isVisible();
  windowState.focused = mainWindow.isFocused();
  windowState.bounds = mainWindow.getBounds();
  windowState.graceActive = showGraceActive;
}

/**
 * Get current window state for diagnostics
 */
function getWindowState(): WindowState & { mainWindowExists: boolean; isDestroyed: boolean; locked: boolean; timestamp: number } {
  updateWindowState();
  return {
    ...windowState,
    mainWindowExists: !!mainWindow,
    isDestroyed: mainWindow?.isDestroyed() ?? true,
    locked: windowVisibilityLocked,
    timestamp: Date.now(),
  };
}

function startShowGracePeriod(trigger: ToggleSource) {
  if (showGraceTimer) {
    clearTimeout(showGraceTimer);
  }
  showGraceActive = true;
  windowState.graceActive = true;
  const log = getLogger();
  log?.debug('[LAUNCHER] Show grace period started', {
    trigger,
    durationMs: SHOW_GRACE_PERIOD_MS,
  });
  showGraceTimer = setTimeout(() => {
    showGraceTimer = null;
    showGraceActive = false;
    windowState.graceActive = false;
    log?.debug('[LAUNCHER] Show grace period ended', { trigger });
    unlockWindowVisibility();
  }, SHOW_GRACE_PERIOD_MS);
}

function animateShowWindow() {
  // CRITICAL: Do NOT animate opacity on show - it causes ghost/transparent window
  // The window is already set to opacity 1 before this is called
  // Just ensure it stays at 1 (no animation needed for show)
  if (!mainWindow || mainWindow.isDestroyed()) return;

  // Force opacity to 1 (don't fade from 0.9)
  mainWindow.setOpacity(1);

  // No animation timeout needed - window should appear immediately at full opacity
}

function animateHideWindow(callback: () => void) {
  if (!mainWindow || mainWindow.isDestroyed()) {
    callback();
    return;
  }
  mainWindow.setOpacity(0.9);
  setTimeout(() => {
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.setOpacity(1);
    }
    callback();
  }, WINDOW_FADE_DURATION_MS);
}

function hideLauncherWindow(reason: HideReason) {
  if (!mainWindow) return;

  const log = getLogger();
  if (!mainWindow.isVisible()) {
    log?.debug('[LAUNCHER] hideWindow skipped - already hidden', { reason });
    return;
  }

  windowState.lastHideAttempt = Date.now();
  windowState.lastHideReason = reason;

  animateHideWindow(() => {
    if (!mainWindow || mainWindow.isDestroyed()) {
      return;
    }
    mainWindow.hide();
    log?.info('[LAUNCHER] Window hidden', { reason });

    if (reason !== 'system') {
      mainWindow.webContents.send('window-hidden');
    }
  });
}

let mainWindow: BrowserWindow | null = null;
let expandedWindow: BrowserWindow | null = null;
let diagnosticsWindow: BrowserWindow | null = null;
let tray: Tray | null = null;
let pythonProcess: ChildProcess | null = null;
let nextProcess: ChildProcess | null = null;

const WINDOW_WIDTH = 800;
const WINDOW_HEIGHT = 520;
const EXPANDED_WIDTH = 1200;
const EXPANDED_HEIGHT = 800;

// Treat non-packaged Electron (electron .) as development, even if NODE_ENV isn't set
// NOTE: app.isPackaged can't be accessed before app.ready, so we use environment detection
const isDev = process.env.NODE_ENV === 'development' || !process.resourcesPath || process.defaultApp || /[\\/]electron[\\/]/.test(process.execPath);

// Get the root directory (parent of desktop/) in development,
// or the app resources directory in production
const rootDir = isDev
  ? path.join(__dirname, '..', '..')
  : process.resourcesPath;

// Logging will be available after app is ready
// For now, use console for early initialization
console.log('[Cerebros] Root directory:', rootDir);
console.log('[Cerebros] Development mode:', isDev);

const DEFAULT_FRONTEND_PORT = 3000;
let frontendPort = DEFAULT_FRONTEND_PORT;

function getFrontendOrigin(): string {
  return `http://localhost:${frontendPort}`;
}

function getFrontendUrl(pathname: string = ''): string {
  if (!pathname) {
    return getFrontendOrigin();
  }
  const normalizedPath = pathname.startsWith('/') ? pathname : `/${pathname}`;
  return `${getFrontendOrigin()}${normalizedPath}`;
}

function updateFrontendPort(port: number) {
  if (!Number.isInteger(port) || port <= 0 || port > 65535) {
    return;
  }

  if (port === frontendPort) {
    return;
  }

  const previousPort = frontendPort;
  frontendPort = port;

  const log = logger ?? undefined;
  log?.info('[FRONTEND] Updated dev server port', { previousPort, newPort: port });

  if (!isDev) {
    return;
  }

  const launcherUrl = getFrontendUrl('/launcher');
  if (mainWindow && !mainWindow.isDestroyed()) {
    log?.info('[FRONTEND] Reloading launcher with new port', { launcherUrl });
    mainWindow.loadURL(launcherUrl);
  }

  if (expandedWindow && !expandedWindow.isDestroyed()) {
    const desktopUrl = getFrontendUrl('/desktop');
    log?.info('[FRONTEND] Reloading expanded window with new port', { desktopUrl });
    expandedWindow.loadURL(desktopUrl);
  }
}

/**
 * Check if a port is in use (fallback detection method)
 */
async function isPortInUse(port: number): Promise<boolean> {
  return new Promise((resolve) => {
    const server = net.createServer();
    server.once('error', (err: any) => {
      // Port is in use if we get EADDRINUSE error
      if (err.code === 'EADDRINUSE') {
        resolve(true);
      } else {
        resolve(false);
      }
    });
    server.once('listening', () => {
      server.close();
      resolve(false); // Port is available
    });
    server.listen(port, '127.0.0.1');
  });
}

/**
 * Log the processes currently holding onto a TCP port.
 * Helps explain why backend/frontend startup may skip or fail.
 */
async function logPortDiagnostics(port: number, context: string) {
  // lsof is available on macOS/Linux; skip on Windows to avoid errors
  if (process.platform === 'win32') {
    return;
  }

  const log = logger ?? { warn: () => {} };

  try {
    const { stdout } = await execAsync(`lsof -nP -iTCP:${port} -sTCP:LISTEN`);
    const listeners = stdout.trim();
    if (listeners) {
      log.warn('[PORT DIAGNOSTICS] Port already in use', {
        port,
        context,
        listeners,
      });
    }
  } catch (error: any) {
    // lsof exits with code 1 when no processes match—ignore silently
    if (typeof error?.code === 'number' && error.code === 1) {
      return;
    }
    log.warn('[PORT DIAGNOSTICS] Failed to inspect port', {
      port,
      context,
      error: error?.message || String(error),
    });
  }
}

/**
 * Check if a server is already running on a given URL
 * Uses retry logic and Node's http module for reliability
 */
type ServerCheckOptions = {
  allow404?: boolean;
};

async function isServerRunning(url: string, options: ServerCheckOptions = {}): Promise<boolean> {
  const log = logger ? logger : { debug: () => {} };
  
  // Try up to 2 times with retry delay
  for (let retry = 0; retry < 2; retry++) {
    try {
      const response = await httpGet(url, 3000);
      if (response.ok || (options.allow404 && response.status === 404)) {
        return true;
      }
    } catch (error: any) {
      // Log on last retry
      if (retry === 1) {
        log.debug('Server detection failed', { url, error: error.message, retry });
      }
      // Wait before retry (except on last attempt)
      if (retry < 1) {
        await new Promise(resolve => setTimeout(resolve, 500));
      }
    }
  }
  return false;
}

const DESKTOP_PING_ATTEMPTS = 8;
const DESKTOP_PING_DELAY_MS = 400;

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function buildExpandedPlaceholderHtml(options: { headline: string; subhead?: string }): string {
  const { headline, subhead } = options;
  return `
<!DOCTYPE html>
<html>
  <head>
    <meta charset="UTF-8" />
    <title>Cerebros Desktop</title>
    <style>
      body {
        margin: 0;
        padding: 0;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        background: radial-gradient(circle at top, #141414, #050505);
        color: #f5f5f5;
        display: flex;
        align-items: center;
        justify-content: center;
        height: 100vh;
      }
      .card {
        text-align: center;
        padding: 32px;
        border-radius: 24px;
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255, 255, 255, 0.08);
        width: 320px;
        box-shadow: 0 20px 60px rgba(0,0,0,0.45);
      }
      h1 {
        margin-bottom: 12px;
        font-size: 20px;
      }
      p {
        margin: 0;
        font-size: 14px;
        color: rgba(255,255,255,0.75);
      }
    </style>
  </head>
  <body>
    <div class="card">
      <h1>${headline}</h1>
      <p>${subhead ?? "Preparing the desktop workspace..."}</p>
    </div>
  </body>
</html>
`.trim();
}

function loadExpandedPlaceholderWindow(windowRef: BrowserWindow | null, options: { headline: string; subhead?: string }) {
  if (!windowRef || windowRef.isDestroyed()) {
    return;
  }
  const html = buildExpandedPlaceholderHtml(options);
  void windowRef.loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(html)}`);
}

function buildDesktopUrlWithState(state: 'ready' | 'pending' | 'error', attempts: number): string {
  const desktopUrl = new URL(getFrontendUrl('/desktop'));
  desktopUrl.searchParams.set('state', state);
  desktopUrl.searchParams.set('attempts', String(attempts));
  desktopUrl.searchParams.set('ts', Date.now().toString());
  return desktopUrl.toString();
}

async function loadExpandedDesktopWindow(windowRef: BrowserWindow | null): Promise<void> {
  if (!windowRef || windowRef.isDestroyed()) {
    return;
  }

  if (!isDev) {
    const prodUrl = `file://${path.join(process.resourcesPath, 'app', 'frontend', 'out', 'desktop.html')}`;
    await windowRef.loadURL(prodUrl);
    return;
  }

  const log = logger ?? undefined;

  for (let attempt = 1; attempt <= DESKTOP_PING_ATTEMPTS; attempt++) {
    if (!windowRef || windowRef.isDestroyed()) {
      return;
    }

    const url = buildDesktopUrlWithState('ready', attempt);
    try {
      log?.info('[EXPANDED] Attempting to load desktop route', { attempt, url });
      await windowRef.loadURL(url);
      log?.info('[EXPANDED] Desktop route loaded', { attempt });
      return;
    } catch (error: any) {
      const message = error instanceof Error ? error.message : String(error);
      log?.warn('[EXPANDED] Failed to load desktop route', { attempt, url, error: message });

      if (attempt < DESKTOP_PING_ATTEMPTS) {
        loadExpandedPlaceholderWindow(windowRef, {
          headline: 'Preparing Cerebros Desktop',
          subhead: `Retrying connection (${attempt}/${DESKTOP_PING_ATTEMPTS})…`,
        });
        const retryDelay = DESKTOP_PING_DELAY_MS * attempt;
        await sleep(retryDelay);
      }
    }
  }

  if (windowRef && !windowRef.isDestroyed()) {
    loadExpandedPlaceholderWindow(windowRef, {
      headline: 'Desktop view unavailable',
      subhead: 'Start the frontend dev server (npm run dev) and try again.',
    });
  }
}

/**
 * Get the current state of the Python backend process
 */
function getBackendProcessState(): Record<string, any> {
  if (!pythonProcess) {
    return { status: 'not_started', pythonProcess: null };
  }
  return {
    status: 'spawned',
    pid: pythonProcess.pid,
    killed: pythonProcess.killed,
    exitCode: pythonProcess.exitCode,
    signalCode: pythonProcess.signalCode,
    connected: pythonProcess.connected,
  };
}

type UrlSource = string | (() => string);

/**
 * Wait for a server to be ready by polling the health endpoint
 * Uses Node's http module for reliability in Electron main process
 */
async function waitForServer(urlSource: UrlSource, timeout: number = 30000, retries: number = 3): Promise<boolean> {
  const resolveUrl = typeof urlSource === 'function' ? urlSource : () => urlSource;
  const startTime = Date.now();
  let attempt = 0;
  let lastError: Error | null = null;
  const log = logger ? logger : { info: () => {}, error: () => {}, debug: () => {}, warn: () => {} };
  let currentUrl = resolveUrl();
  const isBackendTarget = currentUrl.includes('8000');

  log.info('=== WAITING FOR SERVER ===', { url: currentUrl, timeout, retries });

  while (Date.now() - startTime < timeout) {
    const latestUrl = resolveUrl();
    if (latestUrl !== currentUrl) {
      log.info('Health check URL updated', { previousUrl: currentUrl, newUrl: latestUrl });
      currentUrl = latestUrl;
    }

    try {
      const response = await httpGet(currentUrl, 2000);
      if (response.ok) {
        const elapsed = Date.now() - startTime;
        log.info('Server ready', { url: currentUrl, elapsedMs: elapsed, attempt, status: response.status });
        return true;
      } else {
        log.warn('Server returned non-OK status', { url: currentUrl, status: response.status, attempt });
      }
    } catch (error: any) {
      attempt++;
      lastError = error;
      const elapsed = Date.now() - startTime;
      
      // Log progress every 10 attempts (5 seconds)
      if (attempt % 10 === 0) {
        const processState = isBackendTarget ? getBackendProcessState() : null;
        log.info('Health check in progress', { 
          url: currentUrl, 
          elapsedMs: elapsed, 
          attempt,
          errorType: error.name || 'Error',
          errorMessage: error.message,
          processState,
        });
      }
      
      // Log errors at key milestones
      if (attempt === 20 || attempt === 40) { // At 10s and 20s
        const processState = isBackendTarget ? getBackendProcessState() : null;
        log.warn('Server still not ready', { 
          url: currentUrl, 
          elapsedMs: elapsed, 
          attempt,
          errorType: error.name || 'Error',
          errorMessage: error.message,
          processState,
        });
      }
      
      // Server not ready yet, wait and retry
      await new Promise(resolve => setTimeout(resolve, 500));
    }
  }

  const elapsed = Date.now() - startTime;
  const processState = isBackendTarget ? getBackendProcessState() : null;
  
  log.error('=== SERVER FAILED TO START ===', new Error('Timeout'), { 
    url: currentUrl, 
    timeout, 
    elapsedMs: elapsed,
    totalAttempts: attempt,
    lastErrorType: lastError?.name || 'Error',
    lastErrorMessage: lastError?.message,
    processState,
  });

  // If this is the backend, log the captured output buffer
  if (isBackendTarget) {
    const bufferSummary = getBackendBufferSummary();
    log.error('Backend output buffer at time of failure', new Error('Captured output'), {
      bufferLineCount: backendOutputBuffer.length,
      buffer: bufferSummary,
    });
  }

  return false;
}

/**
 * Ensure Python virtual environment exists (production only)
 */
async function ensurePythonEnvironment(): Promise<boolean> {
  if (isDev) return true; // Skip in development

  const userDataPath = app.getPath('userData');
  const venvPath = path.join(userDataPath, 'python-venv');
  const requirementsPath = path.join(process.resourcesPath, 'requirements.txt');
  const log = logger ? logger : { info: () => {}, error: () => {}, debug: () => {}, warn: () => {} };

  // Check if venv already exists
  if (fs.existsSync(path.join(venvPath, 'bin', 'python'))) {
    log.info('Python virtual environment exists', { venvPath });
    return true;
  }

  log.info('Creating Python virtual environment for first run', { venvPath, requirementsPath });

  try {
    // Check if python3 is available
    try {
      await execAsync('which python3');
      log.debug('Python3 found');
    } catch (error) {
      log.error('Python3 not found', error, { message: 'Please install Python 3.8+' });
      return false;
    }

    // Create virtual environment
    log.info('Creating Python venv', { venvPath });
    await execAsync(`python3 -m venv "${venvPath}"`);

    // Install dependencies
    if (fs.existsSync(requirementsPath)) {
      log.info('Installing Python dependencies', { requirementsPath });
      const pipPath = path.join(venvPath, 'bin', 'pip');
      await execAsync(`"${pipPath}" install -r "${requirementsPath}"`);
      log.info('Python dependencies installed successfully');
    } else {
      log.warn('Requirements file not found', { requirementsPath });
    }

    log.info('Python virtual environment ready', { venvPath });
    return true;
  } catch (error) {
    log.error('Failed to setup Python environment', error, { venvPath, requirementsPath });
    return false;
  }
}

/**
 * Start the Python backend (api_server.py)
 * Only starts if backend is not already running
 */
async function startBackend() {
  const userDataPath = app.getPath('userData');
  const log = logger ? logger : { info: () => {}, error: () => {}, warn: () => {}, debug: () => {} };

  log.info('=== STARTING BACKEND ===');

  // Check if backend is already running
  const backendUrl = 'http://127.0.0.1:8000/health';
  let isRunning = await isServerRunning(backendUrl);
  
  // Fallback: Check if port is in use
  if (!isRunning) {
    const portInUse = await isPortInUse(8000);
    if (portInUse) {
      log.info('Backend port 8000 is in use, assuming server is running', { url: backendUrl });
      await logPortDiagnostics(8000, 'backend');
      isRunning = true;
    }
  }
  
  if (isRunning) {
    log.info('Backend already running, skipping startup', { url: backendUrl });
    markStartup('backend_already_running', { url: backendUrl });
    return;
  }

  const venvPython = isDev
    ? path.join(rootDir, 'venv', 'bin', 'python')
    : path.join(userDataPath, 'python-venv', 'bin', 'python');

  const apiServer = isDev
    ? path.join(rootDir, 'api_server.py')
    : path.join(process.resourcesPath, 'api_server.py');

  const workingDir = isDev
    ? rootDir
    : process.resourcesPath;

  // Log the exact command we're about to run
  log.info('Backend spawn configuration', {
    command: venvPython,
    args: [apiServer],
    cwd: workingDir,
    venvPythonExists: fs.existsSync(venvPython),
    apiServerExists: fs.existsSync(apiServer),
    workingDirExists: fs.existsSync(workingDir),
  });

  if (!fs.existsSync(venvPython)) {
    log.error('Python venv not found', new Error('Python venv missing'), {
      venvPython,
      isDev,
      message: isDev ? 'Check venv path' : 'Run the app once to create the virtual environment',
    });
    return;
  }

  if (!fs.existsSync(apiServer)) {
    log.error('API server script not found', new Error('api_server.py missing'), { apiServer });
    return;
  }

  const spawnTimestamp = new Date().toISOString();
  log.info('Spawning Python backend process', { timestamp: spawnTimestamp, venvPython, apiServer, workingDir });

  const backendEnv = { ...process.env };
  if (!backendEnv.CEREBROS_FAST_STARTUP) {
    backendEnv.CEREBROS_FAST_STARTUP = '1';
  }

  pythonProcess = spawn(venvPython, [apiServer], {
    cwd: workingDir,
    env: backendEnv,
  });

  const pid = pythonProcess.pid;
  log.info('Backend process spawned', { pid, timestamp: new Date().toISOString() });
  markStartup('backend_process_spawned', { pid });

  // Listen for spawn event
  pythonProcess.on('spawn', () => {
    log.info('Backend process spawn event received', { pid, timestamp: new Date().toISOString() });
  });

  pythonProcess.stdout?.on('data', (data) => {
    const output = data.toString().trim();
    // Always add to buffer for diagnostics
    addToBackendBuffer('stdout', output);
    
    // Log all output during startup (first 30 seconds)
    const timeSinceSpawn = Date.now() - new Date(spawnTimestamp).getTime();
    if (timeSinceSpawn < 30000) {
      log.info('Backend stdout', { output, timeSinceSpawnMs: timeSinceSpawn });
    } else {
      // After startup, only log important messages
      if (output && !output.includes('INFO:     Uvicorn running') && !output.includes('Application startup complete')) {
        log.debug('Backend stdout', { output });
      }
    }
  });

  pythonProcess.stderr?.on('data', (data) => {
    const output = data.toString().trim();
    // Always add to buffer for diagnostics
    addToBackendBuffer('stderr', output);
    
    const timeSinceSpawn = Date.now() - new Date(spawnTimestamp).getTime();
    
    // Check for port already in use error
    if (output.includes('address already in use') || output.includes('Errno 48')) {
      log.warn('Backend port already in use, server may already be running', { output });
    } else if (output.includes('ERROR:') || output.includes('Traceback') || output.includes('Exception')) {
      log.error('Backend error detected', new Error(output.substring(0, 200)), { 
        output, 
        timeSinceSpawnMs: timeSinceSpawn,
        pid 
      });
    } else if (output.includes('WARNING:')) {
      log.warn('Backend warning', { output, timeSinceSpawnMs: timeSinceSpawn });
    } else {
      // Log all stderr during startup
      if (timeSinceSpawn < 30000) {
        log.info('Backend stderr', { output, timeSinceSpawnMs: timeSinceSpawn });
      } else if (!output.includes('INFO:')) {
        log.debug('Backend stderr', { output });
      }
    }
  });

  pythonProcess.on('exit', (code, signal) => {
    const exitTime = new Date().toISOString();
    if (code !== 0 && code !== null) {
      log.error('Backend process exited with error', new Error(`Exit code: ${code}`), { 
        code, 
        signal, 
        pid,
        exitTime,
        bufferSummary: getBackendBufferSummary()
      });
      const summary = getBackendBufferSummary().split('\n').slice(-20).join('\n');
      log.warn('[DIAGNOSTIC] Backend stderr tail', { summary });
      emitStartupSummary('backend_exit_failure');
    } else {
      log.info('Backend process exited', { code, signal, pid, exitTime });
    }
  });

  pythonProcess.on('close', (code, signal) => {
    log.info('Backend process close event', { code, signal, pid, timestamp: new Date().toISOString() });
  });

  pythonProcess.on('error', (error) => {
    log.error('Failed to start Python backend process', error, { 
      venvPython, 
      apiServer, 
      workingDir,
      pid,
      bufferSummary: getBackendBufferSummary()
    });
  });

  log.info('Backend process event listeners attached', { pid });
}

/**
 * Start the Next.js frontend
 * Only starts if frontend is not already running
 */
async function startFrontend() {
  const frontendDir = path.join(rootDir, 'frontend');
  const log = logger ? logger : { info: () => {}, error: () => {}, warn: () => {}, debug: () => {} };

  // Check if frontend is already running
  const frontendOrigin = getFrontendUrl();
  const isRunning = await isServerRunning(frontendOrigin);
  
  if (isRunning) {
    log.info('Frontend already running, skipping startup', { url: frontendOrigin });
    markStartup('frontend_already_running', { url: frontendOrigin });
    return;
  }

  const portInUse = await isPortInUse(frontendPort);
  if (portInUse) {
    log.warn('Frontend port currently in use, Next.js will attempt fallback port', {
      requestedPort: frontendPort
    });
    void logPortDiagnostics(frontendPort, 'frontend-prestart');
  }

  if (!fs.existsSync(frontendDir)) {
    log.error('Frontend directory not found', new Error('Frontend directory missing'), { frontendDir });
    return;
  }

  const command = isDev ? 'dev' : 'start';

  log.info('Starting Next.js frontend', { frontendDir, command });

  nextProcess = spawn('npm', ['run', command], {
    cwd: frontendDir,
    shell: true,
    env: { ...process.env },
  });
  markStartup('frontend_process_spawned', { command });

  nextProcess.stdout?.on('data', (data) => {
    const output = data.toString().trim();
    if (!output) {
      return;
    }

    if (output.includes('Port 3000 is in use')) {
      log.warn('Frontend dev server detected port collision', { output, expectedPort: DEFAULT_FRONTEND_PORT });
      void logPortDiagnostics(DEFAULT_FRONTEND_PORT, 'frontend-runtime');
    }

    const portMatch = output.match(/http:\/\/localhost:(\d+)/i);
    if (portMatch) {
      const detectedPort = Number(portMatch[1]);
      updateFrontendPort(detectedPort);
      if (detectedPort !== DEFAULT_FRONTEND_PORT) {
        log.warn('Frontend dev server bound unexpected port', {
          expectedPort: DEFAULT_FRONTEND_PORT,
          detectedPort,
          message: output,
        });
      } else {
        log.info('Frontend dev server bound expected port', { port: detectedPort });
      }
    } else if (!output.includes('ready') && !output.includes('compiled')) {
      // Filter out noisy Next.js logs
      log.debug('Frontend stdout', { output });
    }
  });

  nextProcess.stderr?.on('data', (data) => {
    const output = data.toString().trim();
    // Check for port already in use error
    if (output.includes('EADDRINUSE') || output.includes('address already in use')) {
      log.warn('Frontend port already in use, server may already be running', { output });
    } else if (output.includes('Error:')) {
      log.error('Frontend error', new Error(output), { output });
    } else {
      log.warn('Frontend stderr', { output });
    }
  });

  nextProcess.on('exit', (code, signal) => {
    if (code !== 0 && code !== null) {
      log.warn('Frontend process exited with error', { code, signal });
    } else {
      log.debug('Frontend process exited', { code, signal });
    }
  });

  nextProcess.on('error', (error) => {
    log.error('Failed to start frontend process', error, { frontendDir, command });
  });
}

/**
 * Create the main launcher window
 */
function createWindow() {
  mainWindow = new BrowserWindow({
    width: WINDOW_WIDTH,
    height: WINDOW_HEIGHT,
    show: false,
    frame: false,
    transparent: true,
    alwaysOnTop: true,
    skipTaskbar: true,
    resizable: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      webviewTag: true
    }
  });

  const url = isDev
    ? getFrontendUrl('/launcher')
    : `file://${path.join(process.resourcesPath, 'app', 'frontend', 'out', 'launcher.html')}`;

  if (logger) {
    logger.info('Loading window URL', { url, isDev });
  }

  if (isDev) {
    mainWindow.loadURL(url);
  } else {
    // Load launcher page in production
    const launcherPath = path.join(process.resourcesPath, 'app', 'frontend', 'out', 'launcher.html');
    if (fs.existsSync(launcherPath)) {
      mainWindow.loadFile(launcherPath);
    } else {
      // Fallback to main index if launcher page not found
      if (logger) {
        logger.warn('Launcher page not found, falling back to index.html', { launcherPath });
      }
      mainWindow.loadFile(path.join(process.resourcesPath, 'app', 'frontend', 'out', 'index.html'));
    }
  }

  // Center on screen
  mainWindow.center();

  // Don't auto-open DevTools - it steals focus and causes window to hide
  // To open DevTools manually, use View > Toggle Developer Tools or Cmd+Option+I
  // if (isDev) {
  //   mainWindow.webContents.openDevTools({ mode: 'detach' });
  // }

  // Handle blur (hide on focus loss) - Spotlight-like behavior
  // Window hides when user clicks away, just like Spotlight/Raycast
  mainWindow.on('blur', () => {
    const logger = getLogger();
    const settingsStore = getStore();
    const hideOnBlur = settingsStore.get('hideOnBlur');
    const now = Date.now();

    windowState.focused = false;
    windowState.blurCount++;
    windowState.lastBlurTimestamp = now;
    windowState.graceActive = showGraceActive;
    
    logger?.info('[LAUNCHER] Blur event received', { 
      hideOnBlur, 
      locked: windowVisibilityLocked,
      visible: mainWindow?.isVisible(),
      graceActive: showGraceActive
    });

    if (showGraceActive) {
      logger?.debug('[LAUNCHER] Blur skipped - grace period active');
      return;
    }

    // Setting disabled
    if (!hideOnBlur) {
      logger?.debug('[LAUNCHER] Blur skipped - hideOnBlur disabled in settings');
      return;
    }

    // Window locked during processing (voice recording, query processing, etc.)
    if (windowVisibilityLocked) {
      logger?.info('[LAUNCHER] Blur skipped - window locked during processing');
      return;
    }

    // Hide window after short delay (prevents hiding during focus transitions)
    // This matches Spotlight/Raycast behavior - click away to dismiss
    setTimeout(() => {
      if (windowVisibilityLocked || showGraceActive) {
        logger?.debug('[LAUNCHER] Blur timeout skipped - lock or grace active');
        return;
      }
      
      if (mainWindow && !mainWindow.isFocused() && mainWindow.isVisible()) {
        hideLauncherWindow('blur');
        logger?.info('[LAUNCHER] Window hidden - user clicked away (Spotlight behavior)');
      }
    }, 150); // Slightly faster for snappier feel
  });

  // Track window state changes for telemetry
  mainWindow.on('show', () => {
    windowState.visible = true;
    windowState.showCount++;
    const log = getLogger();
    log?.debug('[TELEMETRY] Window show event', { showCount: windowState.showCount, trigger: windowState.lastShowSource });
  });

  mainWindow.on('hide', () => {
    windowState.visible = false;
    windowState.hideCount++;
    windowState.lastHideAttempt = Date.now();
    const log = getLogger();
    log?.debug('[TELEMETRY] Window hide event', { hideCount: windowState.hideCount, reason: windowState.lastHideReason });
  });

  mainWindow.on('focus', () => {
    windowState.focused = true;
    windowState.focusCount++;
    const log = getLogger();
    log?.debug('[TELEMETRY] Window focus event', { focusCount: windowState.focusCount, graceActive: showGraceActive });
  });

  mainWindow.on('closed', () => {
    if (logger) {
      logger.info('Main window closed');
    }
    mainWindow = null;
  });

  if (logger) {
    logger.info('Main window created', { width: WINDOW_WIDTH, height: WINDOW_HEIGHT });
  }
}

/**
 * Create and show diagnostics window for startup failures
 */
function showDiagnosticsWindow(backendReady: boolean, frontendReady: boolean, errors: { backend?: string; frontend?: string; python?: string }) {
  if (diagnosticsWindow) {
    diagnosticsWindow.focus();
    return;
  }

  diagnosticsWindow = new BrowserWindow({
    width: 600,
    height: 500,
    show: false,
    frame: true,
    title: 'Cerebros Startup Diagnostics',
    resizable: true,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      webviewTag: true,
    }
  });

  // Escape special characters for HTML
  const escapeHtml = (str: string) => {
    return str
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  };

  const logFile = logger ? escapeHtml(logger.getLogFile()) : 'Not available';
  const backendError = errors.backend ? escapeHtml(errors.backend) : '';
  const frontendError = errors.frontend ? escapeHtml(errors.frontend) : '';
  const pythonError = errors.python ? escapeHtml(errors.python) : '';

  const html = `
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>Cerebros Startup Diagnostics</title>
  <style>
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      padding: 20px;
      background: #1a1a1a;
      color: #e0e0e0;
      line-height: 1.6;
    }
    h1 {
      color: #fff;
      margin-top: 0;
    }
    .status {
      padding: 15px;
      margin: 10px 0;
      border-radius: 8px;
      border-left: 4px solid;
    }
    .status.success {
      background: #1a3a1a;
      border-color: #10b981;
    }
    .status.error {
      background: #3a1a1a;
      border-color: #ef4444;
    }
    .status-label {
      font-weight: bold;
      margin-bottom: 5px;
    }
    .error-details {
      margin-top: 10px;
      padding: 10px;
      background: rgba(0, 0, 0, 0.3);
      border-radius: 4px;
      font-family: 'Monaco', 'Courier New', monospace;
      font-size: 12px;
      white-space: pre-wrap;
      word-break: break-all;
    }
    .log-path {
      margin-top: 20px;
      padding: 10px;
      background: rgba(255, 255, 255, 0.05);
      border-radius: 4px;
      font-size: 12px;
    }
    .log-path code {
      user-select: all;
      cursor: pointer;
    }
    .buttons {
      margin-top: 20px;
      display: flex;
      gap: 10px;
    }
    button {
      padding: 10px 20px;
      background: #6366f1;
      color: white;
      border: none;
      border-radius: 6px;
      cursor: pointer;
      font-size: 14px;
    }
    button:hover {
      background: #4f46e5;
    }
    button.secondary {
      background: #374151;
    }
    button.secondary:hover {
      background: #4b5563;
    }
  </style>
</head>
<body>
  <h1>🔍 Cerebros Startup Diagnostics</h1>
  
  <div class="status ${backendReady ? 'success' : 'error'}">
    <div class="status-label">Backend (Port 8000)</div>
    ${backendReady ? '✅ Ready' : '❌ Failed'}
    ${backendError ? '<div class="error-details">' + backendError + '</div>' : ''}
  </div>

  <div class="status ${frontendReady ? 'success' : 'error'}">
    <div class="status-label">Frontend (Port 3000)</div>
    ${frontendReady ? '✅ Ready' : '❌ Failed'}
    ${frontendError ? '<div class="error-details">' + frontendError + '</div>' : ''}
  </div>

  ${pythonError ? '<div class="status error"><div class="status-label">Python Environment</div>❌ Failed<div class="error-details">' + pythonError + '</div></div>' : ''}

  <div class="log-path">
    <strong>Log File:</strong><br>
    <code title="Click to select">${logFile}</code>
  </div>

  <div class="buttons">
    <button onclick="window.location.reload()">Retry</button>
    <button class="secondary" onclick="window.close()">Close</button>
  </div>
</body>
</html>
  `;

  diagnosticsWindow.loadURL('data:text/html;charset=utf-8,' + encodeURIComponent(html));
  diagnosticsWindow.once('ready-to-show', () => {
    if (diagnosticsWindow) {
      diagnosticsWindow.show();
    }
  });

  diagnosticsWindow.on('closed', () => {
    diagnosticsWindow = null;
  });
}

/**
 * Show the launcher window, centering it on the active display
 */
function showWindow(trigger: ToggleSource = 'system') {
  if (!mainWindow) return;

  const log = getLogger();
  windowState.lastShowAttempt = Date.now();
  
  log?.info('[LAUNCHER] showWindow called', {
    windowExists: !!mainWindow,
    isDestroyed: mainWindow?.isDestroyed(),
    isVisible: mainWindow?.isVisible(),
    isFocused: mainWindow?.isFocused(),
    trigger,
    windowState: { ...windowState },
  });

  // Lock visibility during show process to prevent blur race condition
  lockWindowVisibility();
  windowState.lastShowSource = trigger;

  // DIAGNOSTIC: Log all detected displays to understand multi-monitor setup
  const allDisplays = screen.getAllDisplays();
  log?.info('[LAUNCHER] ALL DISPLAYS DETECTED', {
    count: allDisplays.length,
    displays: allDisplays.map(d => ({
      id: d.id,
      bounds: d.bounds,
      workArea: d.workArea,
      scaleFactor: d.scaleFactor,
      isPrimary: d.bounds.x === 0 && d.bounds.y === 0
    }))
  });

  const cursor = screen.getCursorScreenPoint();
  log?.info('[LAUNCHER] Cursor position', { cursor });

  const cursorDisplay = screen.getDisplayNearestPoint(cursor);
  const primaryDisplay = screen.getPrimaryDisplay();
  const usingPrimaryFallback = !cursorDisplay || !cursorDisplay.bounds;
  const activeDisplay = usingPrimaryFallback ? primaryDisplay : cursorDisplay;
  const { width, height, x, y } = activeDisplay.bounds;

  if (usingPrimaryFallback) {
    log?.warn('[LAUNCHER] Cursor display unavailable, falling back to PRIMARY', {
      cursor,
      primaryDisplay: primaryDisplay.bounds,
    });
  } else if (cursorDisplay.id !== primaryDisplay.id) {
    log?.info('[LAUNCHER] Using cursor display (multi-monitor)', {
      cursorDisplay: cursorDisplay.bounds,
      primaryDisplay: primaryDisplay.bounds,
    });
  } else {
    log?.info('[LAUNCHER] Using PRIMARY display', {
      primaryDisplay: primaryDisplay.bounds,
    });
  }

  log?.debug('[LAUNCHER] Positioning window', {
    display: { width, height, x, y },
    windowSize: { width: WINDOW_WIDTH, height: WINDOW_HEIGHT },
  });

  // Center horizontally, slightly above center vertically
  mainWindow.setBounds({
    x: x + Math.floor((width - WINDOW_WIDTH) / 2),
    y: y + Math.floor((height - WINDOW_HEIGHT) / 3),
    width: WINDOW_WIDTH,
    height: WINDOW_HEIGHT
  });

  // Ensure window appears on the current workspace/space
  mainWindow.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true });

  // On macOS, activate the app properly without dock toggling
  // The dock.show()/hide() dance causes focus issues - avoid it
  if (process.platform === 'darwin') {
    // app.show() activates the app without showing dock (if LSUIElement or dock.hide was called at startup)
    app.show();
    app.focus({ steal: true });
  }

  // Show and focus the window
  // CRITICAL: Set opacity AFTER show() for better persistence across Electron versions
  mainWindow.show();
  mainWindow.setOpacity(1);

  // AGGRESSIVE: Multiple focus attempts to ensure window comes to front
  mainWindow.focus();
  mainWindow.moveTop(); // Ensure window is on top of z-order
  mainWindow.setAlwaysOnTop(true); // Force on top
  mainWindow.showInactive(); // Sometimes needed on macOS
  mainWindow.focus(); // Focus again after showInactive

  animateShowWindow();

  // Reset visible on all workspaces after showing (optional, keeps it on current space)
  mainWindow.setVisibleOnAllWorkspaces(false);

  log?.info('[LAUNCHER] Window shown and focused', {
    trigger,
    isVisible: mainWindow.isVisible(),
    isFocused: mainWindow.isFocused(),
    bounds: mainWindow.getBounds(),
    displayUsed: { width, height, x, y },
  });

  // Unlock visibility after a grace period to allow focus to stabilize
  startShowGracePeriod(trigger);

  // Notify renderer that window is now visible (for input focus)
  mainWindow.webContents.send('window-shown');

  // FAIL-SAFE: Force opacity to 1 after animation completes if it's somehow < 1
  // This catches edge cases where animations or timing issues reset opacity
  setTimeout(() => {
    if (!mainWindow || mainWindow.isDestroyed()) return;

    const currentOpacity = mainWindow.getOpacity();
    if (currentOpacity < 1) {
      log?.warn('[LAUNCHER] FAIL-SAFE: Opacity < 1 after show, forcing to 1', {
        currentOpacity,
        trigger,
        isVisible: mainWindow.isVisible()
      });
      mainWindow.setOpacity(1);
    }
  }, 300); // After grace period
}

/**
 * Toggle window visibility
 */
function toggleWindow(source: ToggleSource = 'system') {
  if (!mainWindow) return;

  const log = getLogger();
  const isVisible = mainWindow.isVisible();
  const now = Date.now();
  const lastToggle = lastToggleBySource[source] || 0;

  if (now - lastToggle < TOGGLE_DEBOUNCE_MS) {
    log?.debug('[LAUNCHER] toggleWindow debounced', { source, sinceLastMs: now - lastToggle });
    return;
  }

  lastToggleBySource[source] = now;
  windowState.lastToggleSource = source;
  windowState.lastToggleTimestamp = now;
  
  log?.debug('[LAUNCHER] toggleWindow called', { 
    isVisible, 
    source,
    windowState: { ...windowState },
  });

  if (isVisible) {
    hideLauncherWindow('toggle');
    log?.info('[LAUNCHER] Window hidden via toggle', { source });
  } else {
    showWindow(source);
  }
}

/**
 * Open expanded desktop view (ChatGPT-style full window)
 */
async function openExpandedWindow() {
  const log = getLogger();
  
  // If expanded window already exists, focus it
  if (expandedWindow && !expandedWindow.isDestroyed()) {
    log?.info('[EXPANDED] Focusing existing expanded window');
    expandedWindow.show();
    expandedWindow.focus();
    return;
  }

  log?.info('[EXPANDED] Creating new expanded window');

  // Hide the spotlight window
  hideLauncherWindow('system');

  // Create expanded window
  expandedWindow = new BrowserWindow({
    width: EXPANDED_WIDTH,
    height: EXPANDED_HEIGHT,
    minWidth: 800,
    minHeight: 600,
    show: false,
    frame: true, // Show native title bar
    titleBarStyle: 'hiddenInset', // macOS style
    trafficLightPosition: { x: 15, y: 15 },
    vibrancy: 'under-window',
    visualEffectState: 'active',
    backgroundColor: '#1a1a1a',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true,
      webviewTag: true,
    },
  });

  // Immediately show a placeholder so users see progress
  loadExpandedPlaceholderWindow(expandedWindow, {
    headline: 'Preparing Cerebros Desktop',
    subhead: isDev ? 'Connecting to the Next.js dev server…' : 'Loading workspace assets…',
  });

  expandedWindow.webContents.on('did-start-loading', () => {
    log?.debug('[EXPANDED] Renderer started loading', {
      url: expandedWindow?.webContents.getURL(),
    });
  });

  expandedWindow.webContents.on('did-finish-load', () => {
    log?.info('[EXPANDED] Renderer finished loading', {
      url: expandedWindow?.webContents.getURL(),
    });
  });

  expandedWindow.webContents.on('did-fail-load', (_event, errorCode, errorDescription, validatedURL) => {
    log?.error('[EXPANDED] Renderer failed to load', {
      errorCode,
      errorDescription,
      validatedURL,
    });
    loadExpandedPlaceholderWindow(expandedWindow, {
      headline: 'Desktop view unavailable',
      subhead: 'Start the frontend dev server (npm run dev) and try again.',
    });
  });

  // Show when ready
  expandedWindow.once('ready-to-show', () => {
    log?.info('[EXPANDED] Window ready to show');
    expandedWindow?.show();
    expandedWindow?.focus();
  });

  // Handle close
  expandedWindow.on('closed', () => {
    log?.info('[EXPANDED] Window closed');
    expandedWindow = null;
  });

  await loadExpandedDesktopWindow(expandedWindow);

  // Handle blur - don't hide expanded window on blur (it's a regular window)
  // Only spotlight window has hide-on-blur behavior
}

/**
 * Create the system tray icon
 */
function createTray() {
  // Use a simple emoji as icon for now (proper icon should be added later)
  const iconPath = path.join(__dirname, '..', 'assets', 'icon.png');

  // Create a temporary simple tray (will need proper icon later)
  try {
    tray = new Tray(iconPath);
  } catch (error) {
    console.warn('[Tray] Could not load icon, using default');
    // Electron will use a default icon
  }

  const contextMenu = Menu.buildFromTemplate([
    {
      label: 'Show Cerebros',
      click: () => showWindow('trayMenu')
    },
    {
      label: 'Preferences...',
      click: () => {
        showWindow('trayMenu');
        // Send event to renderer to open preferences modal
        if (mainWindow) {
          mainWindow.webContents.send('open-preferences');
        }
      }
    },
    { type: 'separator' },
    {
      label: 'Quit',
      click: () => {
        app.quit();
      }
    }
  ]);

  if (tray) {
    tray.setContextMenu(contextMenu);
    tray.setToolTip('Cerebros AI Launcher');

    // Click to show window
    tray.on('click', () => {
      toggleWindow('tray');
    });

    const log = logger ? logger : { info: () => {} };
    log.info('System tray icon created');
  }
}

/**
 * Register global keyboard shortcut
 */
function registerHotkey() {
  // Get hotkey from settings store (user-configurable)
  const settingsStore = getStore();
  const hotkey = settingsStore.get('hotkey');

  const log = logger ? logger : { debug: () => {}, info: () => {}, error: () => {} };
  const registered = globalShortcut.register(hotkey, () => {
    log.debug('Hotkey triggered', { hotkey });
    toggleWindow('globalShortcut');
  });

  if (registered) {
    log.info('Global hotkey registered', { hotkey });
  } else {
    log.error('Failed to register global hotkey', new Error('Registration failed'), { hotkey });
  }
}

/**
 * IPC handlers for communication with renderer
 */
function setupIPC() {
  // Hide window
  ipcMain.on('hide-window', () => {
    hideLauncherWindow('ipc');
  });

  // Lock window visibility (prevent blur from hiding during processing)
  ipcMain.on('lock-window', () => {
    lockWindowVisibility();
  });

  // Unlock window visibility (allow blur to hide again)
  ipcMain.on('unlock-window', () => {
    unlockWindowVisibility();
  });

  // Open expanded desktop view (ChatGPT-style full window)
  ipcMain.on('open-expanded-window', () => {
    const log = getLogger();
    log?.info('[LAUNCHER] Opening expanded desktop window');
    void openExpandedWindow();
  });

  // Collapse back to spotlight view
  ipcMain.on('collapse-to-spotlight', () => {
    const log = getLogger();
    log?.info('[LAUNCHER] Collapsing to spotlight view');
    if (expandedWindow) {
      expandedWindow.close();
      expandedWindow = null;
    }
    showWindow('ipc');
  });

  // Open file externally (in Finder)
  ipcMain.on('reveal-finder', (event, filePath: string) => {
    shell.showItemInFolder(filePath);
  });

  // Open URL in default browser
  ipcMain.on('open-external', (event, url: string) => {
    shell.openExternal(url);
  });

  // Open application
  ipcMain.on('open-app', (event, appName: string) => {
    const { exec } = require('child_process');
    exec(`open -a "${appName}"`, (error: any) => {
      if (error) {
        event.reply('open-app-result', { success: false, error: error.message });
      } else {
        event.reply('open-app-result', { success: true });
      }
    });
  });

  // Get all settings
  ipcMain.handle('get-settings', () => {
    const log = logger ? logger : { debug: () => {} };
    const settingsStore = getStore();
    log.debug('Fetching settings', { settings: settingsStore.store });
    return settingsStore.store;
  });

  // Get window state for diagnostics
  ipcMain.handle('get-window-state', () => {
    const log = logger ? logger : { debug: () => {} };
    const state = getWindowState();
    log.debug('Window state requested', { state });
    return state;
  });

  // DIAGNOSTIC: Force window visible (emergency recovery)
  ipcMain.handle('force-window-visible', () => {
    const log = getLogger();
    log?.warn('[DIAGNOSTIC] Force visible called - indicates potential bug');

    if (!mainWindow || mainWindow.isDestroyed()) {
      return { success: false, error: 'Window does not exist' };
    }

    const before = {
      visible: mainWindow.isVisible(),
      opacity: mainWindow.getOpacity(),
      focused: mainWindow.isFocused(),
      locked: windowVisibilityLocked
    };

    log?.info('[DIAGNOSTIC] Force visible - before state:', before);

    try {
      // Force all visibility settings
      mainWindow.show();
      mainWindow.setOpacity(1);
      mainWindow.focus();
      unlockWindowVisibility();

      const after = {
        visible: mainWindow.isVisible(),
        opacity: mainWindow.getOpacity(),
        focused: mainWindow.isFocused(),
        locked: windowVisibilityLocked
      };

      log?.info('[DIAGNOSTIC] Force visible - after state:', after);

      return { success: true, before, after };
    } catch (error) {
      log?.error('[DIAGNOSTIC] Force visible failed', error as Error);
      return { success: false, error: (error as Error).message, before };
    }
  });

  // Update settings
  ipcMain.on('update-settings', (event, newSettings: Partial<Settings>) => {
    const log = logger ? logger : { info: () => {}, error: () => {}, debug: () => {} };
    const settingsStore = getStore();
    log.info('Updating settings', { newSettings });

    // If hotkey changed, re-register it
    if (newSettings.hotkey && newSettings.hotkey !== settingsStore.get('hotkey')) {
      globalShortcut.unregisterAll();
      settingsStore.set('hotkey', newSettings.hotkey);

      const registered = globalShortcut.register(newSettings.hotkey, () => {
        log.debug('Hotkey triggered', { hotkey: newSettings.hotkey });
        toggleWindow('globalShortcut');
      });

      if (registered) {
        log.info('Hotkey re-registered', { hotkey: newSettings.hotkey });
      } else {
        log.error('Failed to re-register hotkey', new Error('Registration failed'), { hotkey: newSettings.hotkey });
      }
    }

    // Update other settings
    if (newSettings.hideOnBlur !== undefined) {
      settingsStore.set('hideOnBlur', newSettings.hideOnBlur);
    }

    if (newSettings.miniConversationDepth !== undefined) {
      settingsStore.set('miniConversationDepth', newSettings.miniConversationDepth);
    }

    if (newSettings.theme !== undefined) {
      settingsStore.set('theme', newSettings.theme);
    }

    // If startAtLogin changed, update login items
    if (newSettings.startAtLogin !== undefined) {
      settingsStore.set('startAtLogin', newSettings.startAtLogin);
      app.setLoginItemSettings({
        openAtLogin: newSettings.startAtLogin,
        openAsHidden: true,
        name: 'Cerebros'
      });
      log.info('Start at login setting updated', { startAtLogin: newSettings.startAtLogin });
    }

    event.reply('settings-updated', { success: true });
  });

  const log = logger ? logger : { info: () => {} };
  log.info('IPC handlers registered');
}

/**
 * Log detailed startup context for diagnostics
 */
function logStartupContext() {
  const log = logger!;
  const userDataPath = app.getPath('userData');
  
  // Compute all the paths that will be used
  const venvPython = isDev
    ? path.join(rootDir, 'venv', 'bin', 'python')
    : path.join(userDataPath, 'python-venv', 'bin', 'python');

  const apiServer = isDev
    ? path.join(rootDir, 'api_server.py')
    : path.join(process.resourcesPath, 'api_server.py');

  const workingDir = isDev
    ? rootDir
    : process.resourcesPath;

  const frontendDir = path.join(rootDir, 'frontend');

  log.info('=== STARTUP CONTEXT ===');
  
  // Log all paths
  log.info('Paths', {
    rootDir,
    userDataPath,
    venvPython,
    apiServer,
    workingDir,
    frontendDir,
    __dirname,
    resourcesPath: process.resourcesPath,
  });

  // Check file existence
  const fileChecks = {
    venvPythonExists: fs.existsSync(venvPython),
    apiServerExists: fs.existsSync(apiServer),
    workingDirExists: fs.existsSync(workingDir),
    frontendDirExists: fs.existsSync(frontendDir),
  };
  log.info('File existence checks', fileChecks);

  // Log any missing critical files as errors
  if (!fileChecks.venvPythonExists) {
    log.error('CRITICAL: Python venv not found', new Error('Missing file'), { path: venvPython });
  }
  if (!fileChecks.apiServerExists) {
    log.error('CRITICAL: api_server.py not found', new Error('Missing file'), { path: apiServer });
  }

  // Log relevant environment variables
  const envVars = {
    NODE_ENV: process.env.NODE_ENV || '(not set)',
    PATH: process.env.PATH ? `${process.env.PATH.substring(0, 200)}...` : '(not set)',
    PYTHONPATH: process.env.PYTHONPATH || '(not set)',
    VIRTUAL_ENV: process.env.VIRTUAL_ENV || '(not set)',
    HOME: process.env.HOME || '(not set)',
  };
  log.info('Environment variables', envVars);

  // Log Python version if venv exists
  if (fileChecks.venvPythonExists) {
    try {
      const { execSync } = require('child_process');
      const pythonVersion = execSync(`"${venvPython}" --version 2>&1`, { encoding: 'utf8' }).trim();
      log.info('Python version', { pythonVersion, path: venvPython });
    } catch (error: any) {
      log.error('Failed to get Python version', error, { path: venvPython });
    }
  }

  log.info('=== END STARTUP CONTEXT ===');
}

/**
 * App lifecycle
 */
app.on('ready', async () => {
  // Initialize logger now that app is ready
  logger = getLogger();
  const settingsStore = getStore();
  migrateLegacyHotkey(settingsStore);
  
  logger.info('App ready, starting services', {
    isDev,
    platform: process.platform,
    logFile: logger.getLogFile(),
    nodeVersion: process.version,
    electronVersion: process.versions.electron,
    pid: process.pid,
  });
  markStartup('electron_app_ready', { isDev });

  // Log detailed startup context for diagnostics
  logStartupContext();
  markStartup('startup_context_logged');

  // Hide dock icon on macOS
  if (process.platform === 'darwin') {
    app.dock.hide();
    logger.debug('Dock icon hidden (macOS)');
  }

  // Apply start-at-login setting from store
  const startAtLogin = settingsStore.get('startAtLogin');
  app.setLoginItemSettings({
    openAtLogin: startAtLogin,
    openAsHidden: true,
    name: 'Cerebros'
  });
  logger.info('Start at login setting applied', { startAtLogin });

  // Ensure Python environment exists (production only)
  if (!isDev) {
    const pythonReady = await ensurePythonEnvironment();
    if (!pythonReady) {
      logger.error('Failed to setup Python environment', new Error('Python setup failed'));
      // Show error dialog to user
      const { dialog } = require('electron');
      dialog.showErrorBox(
        'Python Setup Failed',
        'Failed to setup Python environment. Please check the logs for details.\n\n' +
        `Log file: ${logger.getLogFile()}`
      );
      app.quit();
      return;
    }
  }

  // Check if servers are already running before starting
  const backendUrl = 'http://127.0.0.1:8000/health';
  const initialFrontendUrl = getFrontendUrl();
  
  let backendAlreadyRunning = await isServerRunning(backendUrl);
  let frontendAlreadyRunning = isDev ? await isServerRunning(initialFrontendUrl) : true; // Frontend is built in production

  // Fallback: Check if ports are in use (server might be starting up)
  if (!backendAlreadyRunning) {
    const portInUse = await isPortInUse(8000);
    if (portInUse) {
      logger.info('Backend port 8000 is in use, assuming server is running', { backendUrl });
      backendAlreadyRunning = true; // Assume running, will verify with health check
    }
  }

  markStartup('backend_probe_complete', { backendAlreadyRunning });
  markStartup('frontend_probe_complete', { frontendAlreadyRunning });

  // Start backend and frontend only if not already running
  if (!backendAlreadyRunning) {
    startBackend();
  } else {
    logger.info('Backend already running, using existing instance');
  }
  
  if (isDev && !frontendAlreadyRunning) {
    startFrontend(); // Only run Next.js dev server in development
  } else if (isDev) {
    logger.info('Frontend already running, using existing instance');
  }

  // INSTANT STARTUP: Create UI immediately, load servers in background
  logger.info('🚀 INSTANT STARTUP: Creating UI immediately');
  console.log('\n');
  console.log('🚀 Starting Cerebros...');
  console.log('   UI will appear instantly, backend loading in background...');

  // Create UI immediately (instant startup)
  createWindow();
  createTray();
  registerHotkey();
  setupIPC();

  const currentHotkey = settingsStore.get('hotkey');
  logger.info('Launcher UI ready (instant startup)', {
    hotkey: currentHotkey,
    logFile: logger.getLogFile(),
  });
  markStartup('ui_ready_instant', { instant: true });

  // Print instant startup message
  console.log('\n');
  console.log('╔════════════════════════════════════════════════════════════╗');
  console.log('║                                                            ║');
  console.log('║   ✅ CEREBROS UI IS READY! (Instant Startup)               ║');
  console.log('║                                                            ║');
  console.log('║   Press ⌘ + Option + K to open the launcher                ║');
  console.log('║                                                            ║');
  console.log('║   Backend loading in background...                         ║');
  console.log('║                                                            ║');
  console.log('╚════════════════════════════════════════════════════════════╝');
  console.log('\n');

  // Load servers in background (non-blocking)
  (async () => {
    const currentFrontendUrl = getFrontendUrl();
    logger.info('Background: Waiting for servers to be ready', {
      backendUrl,
      frontendUrl: currentFrontendUrl,
      backendAlreadyRunning,
      frontendAlreadyRunning: isDev ? frontendAlreadyRunning : 'N/A (production)'
    });

    // Longer timeout since we're not blocking UI
    const timeout = (backendAlreadyRunning && (frontendAlreadyRunning || !isDev)) ? 5000 : 45000;

    const backendReady = await waitForServer(backendUrl, timeout, 3);
    if (!backendReady && pythonProcess?.exitCode && pythonProcess.exitCode !== 0) {
      logger?.warn('[BACKGROUND] Backend exited early, aborting wait loop', {
        exitCode: pythonProcess.exitCode,
        pid: pythonProcess.pid,
      });
      emitStartupSummary('backend_exit_failure');

      // Notify renderer of backend failure
      if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.webContents.send('backend-status', {
          ready: false,
          error: 'Backend process exited early'
        });
      }
      return;
    }

    const frontendReady = isDev ? await waitForServer(() => getFrontendUrl(), timeout, 3) : true;
    markStartup('backend_health_check_complete', { backendReady });
    if (isDev) {
      markStartup('frontend_health_check_complete', { frontendReady });
    }

    if (!backendReady) {
      const processState = getBackendProcessState();
      logger.error('=== BACKEND STARTUP FAILURE SUMMARY ===', new Error('Health check failed'), {
        url: 'http://127.0.0.1:8000/health',
        processState,
        message: 'Check the logs above for Python tracebacks or import errors',
      });

      // Log the full backend buffer
      logger.error('Full backend output at failure:', new Error('Backend output'), {
        bufferLineCount: backendOutputBuffer.length,
      });
      const bufferLines = getBackendBufferSummary().split('\n');
      for (const line of bufferLines.slice(-50)) {
        if (line.trim()) {
          logger.info('BACKEND OUTPUT: ' + line);
        }
      }

      // Notify renderer of backend failure
      if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.webContents.send('backend-status', {
          ready: false,
          error: 'Backend health check failed'
        });
      }
    }

    if (!frontendReady) {
      logger.error('Frontend failed to start', new Error('Health check failed'), {
        url: getFrontendUrl(),
      });
    }

    if (backendReady && frontendReady) {
      logger.info('=== ALL SERVERS READY (Background) ===');
      emitStartupSummary('servers_ready');

      // Notify renderer that backend is ready
      if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.webContents.send('backend-status', { ready: true });
      }

      console.log('\n✅ Backend server ready! You can now use all features.\n');

      // Self-test in development mode
      if (isDev) {
        const log = getLogger();
        setTimeout(() => {
          log?.info('[SELF-TEST] Starting window visibility self-test...');

          const preTestState = getWindowState();
          log?.info('[SELF-TEST] Pre-test state', { state: preTestState });

          showWindow('selfTest');

          setTimeout(() => {
            const postShowState = getWindowState();
            const testPassed = postShowState.visible && postShowState.mainWindowExists;

            log?.info('[SELF-TEST] Post-show state', {
              state: postShowState,
              testPassed,
            });

            if (testPassed) {
              log?.info('[SELF-TEST] ✅ PASSED - Window successfully shown');
              console.log('[SELF-TEST] ✅ Window visibility test PASSED');
              log?.info('[SELF-TEST] Window left visible for user testing');
            } else {
              log?.error('[SELF-TEST] ❌ FAILED - Window did not become visible', new Error('Self-test failed'), {
                preTestState,
                postShowState,
              });
              console.error('[SELF-TEST] ❌ Window visibility test FAILED - check logs for details');
            }
          }, 500);
        }, 3000);
      }
    } else {
      logger.error('=== BACKGROUND SERVER STARTUP FAILED ===', new Error('Startup failed'), {
        backendReady,
        frontendReady,
        logFile: logger.getLogFile(),
      });
      emitStartupSummary('startup_failed');

      // Build detailed error messages including process state and buffer
      const errors: { backend?: string; frontend?: string; python?: string } = {};
      if (!backendReady) {
        const processState = getBackendProcessState();
        const recentOutput = backendOutputBuffer.slice(-10).map(e => e.data).join('\n');

        errors.backend = 'Backend health check failed at http://127.0.0.1:8000/health\n\n' +
          `Process state: ${JSON.stringify(processState, null, 2)}\n\n` +
          'Recent output:\n' + (recentOutput || '(no output captured)') + '\n\n' +
          'Possible causes:\n' +
          '• Python dependencies not installed\n' +
          '• Port 8000 already in use\n' +
          '• api_server.py has import errors\n' +
          '• Missing .env file or environment variables\n\n' +
          'Check the log file for detailed error messages:\n' +
          logger.getLogFile();
      }
      if (!frontendReady) {
        errors.frontend = `Frontend health check failed at ${getFrontendUrl()}\n\n` +
          'Possible causes:\n' +
          '• Next.js dev server not starting\n' +
          '• Default dev port 3000 already in use\n' +
          '• Frontend build errors\n\n' +
          'Check the logs for detailed error messages.';
      }

      // Log the log file location prominently
      console.error('========================================');
      console.error('[Cerebros] STARTUP FAILED');
      console.error('[Cerebros] Check log file:', logger.getLogFile());
      console.error('========================================');

      // Show diagnostics window after a short delay
      setTimeout(() => {
        showDiagnosticsWindow(backendReady, frontendReady, errors);
      }, 1000);

      // Don't quit immediately - let user see diagnostics
      // app.quit();
    }
  })(); // Close async IIFE
});

// Cleanup on quit
app.on('before-quit', () => {
  if (logger) {
    logger.info('Shutting down application');

    // Unregister all shortcuts
    globalShortcut.unregisterAll();
    logger.debug('Global shortcuts unregistered');

    // Kill child processes
    if (pythonProcess) {
      logger.info('Stopping Python backend');
      pythonProcess.kill();
    }

    if (nextProcess) {
      logger.info('Stopping Next.js frontend');
      nextProcess.kill();
    }

    // Close logger
    logger.close();
  }
});

app.on('window-all-closed', () => {
  // Don't quit on window close - keep running in background
  // app.quit();
});

app.on('activate', () => {
  // On macOS, re-create window if clicked in dock (though dock is hidden)
  if (mainWindow === null) {
    createWindow();
  }
});
