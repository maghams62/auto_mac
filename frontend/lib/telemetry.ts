/**
 * OpenTelemetry configuration for frontend runtime.
 * Provides shared correlation IDs (session_id + run_id) and heartbeat monitoring.
 */

// Safe StatusCode constants (OpenTelemetry StatusCode enum values)
// Using fallback constants since OpenTelemetry may not be available in Next.js browser builds
const STATUS_CODE = {
  UNSET: 0,
  OK: 1,
  ERROR: 2,
};

// Type definitions for Span (simplified for browser environment)
interface Span {
  setAttribute?(key: string, value: any): void;
  setStatus?(status: { code: number; message?: string }): void;
  addEvent?(name: string, attributes?: Record<string, any>): void;
  recordException?(error: Error): void;
  end?(): void;
}

// Telemetry configuration
export const TELEMETRY_CONFIG = {
  serviceName: 'auto_mac_frontend',
  serviceVersion: '1.0.0',
  environment: process.env.NODE_ENV || 'development',
  otlpEndpoint: process.env.NEXT_PUBLIC_OTLP_ENDPOINT || 'http://localhost:4318',
  sampleRate: parseFloat(process.env.NEXT_PUBLIC_TELEMETRY_SAMPLE_RATE || '1.0'),
  redactSensitiveFields: [
    'password', 'token', 'key', 'secret', 'auth', 'credential',
    'api_key', 'access_token', 'refresh_token', 'bearer'
  ],
  maxAttributeLength: 2048,
  maxLogMessageLength: 4096,
};

// Global tracer instance
let _tracer: any = null;

export function getTracer() {
  if (!_tracer) {
    // In browser environment, we might not have full OpenTelemetry SDK
    // This is a simplified version for frontend with proper typing
    const createSpan = (name: string): Span => ({
      setAttribute: (key: string, value: any) => {
        // No-op in browser - telemetry is logged via console
      },
      setStatus: (status: { code: number; message?: string }) => {
        // No-op in browser - telemetry is logged via console
      },
      addEvent: (name: string, attributes?: Record<string, any>) => {
        // No-op in browser - telemetry is logged via console
      },
      recordException: (error: Error) => {
        // No-op in browser - telemetry is logged via console
      },
      end: () => {
        // No-op in browser - telemetry is logged via console
      },
    });

    _tracer = {
      startSpan: createSpan,
      startActiveSpan: (name: string, fn: (span: Span) => any) => {
        const span: Span = createSpan(name);
        return fn(span);
      },
    };
  }
  return _tracer;
}

export function sanitizeValue(value: any, fieldName: string = ''): any {
  if (typeof value === 'object' && value !== null) {
    if (Array.isArray(value)) {
      return value.map(item => sanitizeValue(item));
    }
    const sanitized: any = {};
    for (const [key, val] of Object.entries(value)) {
      sanitized[key] = sanitizeValue(val, key);
    }
    return sanitized;
  }

  if (typeof value === 'string') {
    const fieldLower = fieldName.toLowerCase();
    const valueLower = value.toLowerCase();

    for (const sensitive of TELEMETRY_CONFIG.redactSensitiveFields) {
      if (fieldLower.includes(sensitive) || valueLower.includes(sensitive)) {
        return '[REDACTED]';
      }
    }

    if (value.length > TELEMETRY_CONFIG.maxAttributeLength) {
      return value.substring(0, TELEMETRY_CONFIG.maxAttributeLength) + '...';
    }

    return value;
  }

  return value;
}

export function createCorrelationId(sessionId: string, runId?: string): string {
  if (runId) {
    return `${sessionId}:${runId}`;
  }
  return `${sessionId}:default`;
}

export function extractSessionFromCorrelation(correlationId: string): string {
  return correlationId.split(':')[0] || correlationId;
}

export function extractRunFromCorrelation(correlationId: string): string {
  const parts = correlationId.split(':');
  return parts.length > 1 ? parts[1] : 'default';
}

export function recordEvent(span: Span, name: string, attributes?: Record<string, any>) {
  if (!span || typeof span.addEvent !== 'function') {
    // Span not available or doesn't support addEvent - skip silently
    return;
  }

  try {
    if (attributes) {
      const sanitized = Object.fromEntries(
        Object.entries(attributes).map(([key, value]) => [key, sanitizeValue(value, key)])
      );
      span.addEvent(name, sanitized);
    } else {
      span.addEvent(name);
    }
  } catch (e) {
    console.warn('[TELEMETRY] Could not record event:', e);
  }
}

export function setSpanError(span: Span, error: Error, attributes?: Record<string, any>) {
  // Use fallback StatusCode constant
  const errorCode = STATUS_CODE.ERROR;
  
  try {
    if (span && span.setStatus) {
      span.setStatus({ code: errorCode, message: error.message });
    }
    if (span && span.recordException) {
      span.recordException(error);
    }
  } catch (e) {
    // Span methods may not be available - log warning but continue
    console.warn('[TELEMETRY] Could not set span error status:', e);
  }

  if (attributes) {
    const sanitized = Object.fromEntries(
      Object.entries(attributes).map(([key, value]) => [key, sanitizeValue(value, key)])
    );
    try {
      Object.entries(sanitized).forEach(([key, value]) => {
        if (span && span.setAttribute) {
          span.setAttribute(key, value);
        }
      });
    } catch (e) {
      console.warn('[TELEMETRY] Could not set span attributes:', e);
    }
  }
}

export function logStructured(level: 'info' | 'error' | 'warning' | 'debug', message: string, ...args: any[]) {
  const sanitizedArgs = args.map(arg => sanitizeValue(arg));

  if (message.length > TELEMETRY_CONFIG.maxLogMessageLength) {
    message = message.substring(0, TELEMETRY_CONFIG.maxLogMessageLength) + '...';
  }

  const logData = {
    level,
    message,
    timestamp: new Date().toISOString(),
    ...sanitizedArgs
  };

  // In browser, use console
  const consoleMethod = level === 'error' ? 'error' :
                       level === 'warning' ? 'warn' :
                       level === 'debug' ? 'debug' : 'log';

  console[consoleMethod](`[TELEMETRY] ${message}`, logData);
}

// WebSocket heartbeat monitoring
export class WebSocketMonitor {
  private sessionId: string | null = null;
  private lastHeartbeat: number = 0;
  private connectionState: 'connected' | 'disconnected' | 'connecting' = 'disconnected';
  private heartbeatInterval: ReturnType<typeof setInterval> | null = null;

  constructor() {
    // Only start heartbeat in browser environment
    if (typeof window !== 'undefined') {
      this.startHeartbeat();
    }
  }

  setSessionId(sessionId: string) {
    this.sessionId = sessionId;
    logStructured('info', 'WebSocket session ID set', { sessionId });
  }

  updateConnectionState(state: 'connected' | 'disconnected' | 'connecting') {
    const previousState = this.connectionState;
    this.connectionState = state;

    if (state === 'connected') {
      this.lastHeartbeat = Date.now();
    }

    const tracer = getTracer();
    const span = tracer.startSpan('websocket.state_change');
    span.setAttribute?.('previous_state', previousState);
    span.setAttribute?.('new_state', state);
    span.setAttribute?.('session_id', this.sessionId || 'unknown');
    span.setAttribute?.('timestamp', Date.now());

    recordEvent(span, 'websocket_connection_change', {
      previous_state: previousState,
      new_state: state,
      session_id: this.sessionId,
      timestamp: Date.now()
    });

    span.end?.();

    logStructured('info', `WebSocket state: ${previousState} -> ${state}`, {
      sessionId: this.sessionId,
      previousState,
      newState: state
    });
  }

  recordHeartbeat() {
    this.lastHeartbeat = Date.now();

    logStructured('debug', 'WebSocket heartbeat', {
      sessionId: this.sessionId,
      connectionState: this.connectionState,
      timestamp: this.lastHeartbeat
    });
  }

  recordConnectionFailure(error?: Error) {
    const tracer = getTracer();
    const span = tracer.startSpan('websocket.connection_failure');
    span.setAttribute?.('session_id', this.sessionId || 'unknown');
    span.setAttribute?.('connection_state', this.connectionState);

    if (error) {
      setSpanError(span, error, {
        session_id: this.sessionId,
        connection_state: this.connectionState
      });
    }

    recordEvent(span, 'websocket_connection_failed', {
      session_id: this.sessionId,
      connection_state: this.connectionState,
      error_message: error?.message,
      timestamp: Date.now()
    });

    span.end?.();

    logStructured('error', 'WebSocket connection failed', {
      sessionId: this.sessionId,
      connectionState: this.connectionState,
      errorMessage: error?.message
    });
  }

  private startHeartbeat() {
    // Only start heartbeat in browser environment
    if (typeof window === 'undefined') {
      return;
    }

    // Clear any existing interval
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval);
    }

    this.heartbeatInterval = setInterval(() => {
      if (this.connectionState === 'connected') {
        this.recordHeartbeat();
      }
    }, 30000); // 30 seconds
  }

  destroy() {
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval);
      this.heartbeatInterval = null;
    }
  }
}

// Global WebSocket monitor instance - lazy initialization for browser-only
let _wsMonitor: WebSocketMonitor | null = null;

export function getWebSocketMonitor(): WebSocketMonitor {
  // Only create monitor in browser environment
  if (typeof window === 'undefined') {
    // Return a no-op monitor for SSR/Node.js
    return {
      setSessionId: () => {},
      updateConnectionState: () => {},
      recordHeartbeat: () => {},
      recordConnectionFailure: () => {},
      destroy: () => {},
    } as WebSocketMonitor;
  }

  if (!_wsMonitor) {
    _wsMonitor = new WebSocketMonitor();
    
    // Cleanup on page unload
    window.addEventListener('beforeunload', () => {
      if (_wsMonitor) {
        _wsMonitor.destroy();
      }
    });
  }

  return _wsMonitor;
}

// Export wsMonitor for backward compatibility (lazy getter)
export const wsMonitor = new Proxy({} as WebSocketMonitor, {
  get(target, prop) {
    const monitor = getWebSocketMonitor();
    const value = monitor[prop as keyof WebSocketMonitor];
    // Bind methods to the monitor instance to preserve 'this' context
    if (typeof value === 'function') {
      return value.bind(monitor);
    }
    return value;
  }
});
