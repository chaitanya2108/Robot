import { wsUrl } from './api';
import type { ConnectionStatus, Hello, RobotConfig, Telemetry } from './types';

export type RobotState = {
  status: ConnectionStatus;
  hello: Hello | null;
  telemetry: Telemetry | null;
  isDriver: boolean;
  estop: boolean;
  latencyMs: number | null;
  lastError: string | null;
};

const INITIAL: RobotState = {
  status: 'idle',
  hello: null,
  telemetry: null,
  isDriver: false,
  estop: false,
  latencyMs: null,
  lastError: null,
};

/**
 * WebSocket connection to the robot server.
 * - Authenticates with the token as the first message.
 * - Reconnects automatically with backoff.
 * - Exposes an immutable snapshot for React (useSyncExternalStore).
 */
export class RobotClient {
  private ws: WebSocket | null = null;
  private listeners = new Set<() => void>();
  private state: RobotState = INITIAL;
  private wantOpen = false;
  private attempts = 0;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private pingTimer: ReturnType<typeof setInterval> | null = null;

  constructor(private config: RobotConfig) {}

  // ---- store ----------------------------------------------------------------
  subscribe = (fn: () => void) => {
    this.listeners.add(fn);
    return () => {
      this.listeners.delete(fn);
    };
  };
  getSnapshot = () => this.state;
  private set(patch: Partial<RobotState>) {
    this.state = { ...this.state, ...patch };
    this.listeners.forEach((l) => l());
  }

  // ---- lifecycle --------------------------------------------------------------
  connect() {
    this.wantOpen = true;
    if (this.ws) return;
    this.open();
  }

  disconnect() {
    this.wantOpen = false;
    this.clearTimers();
    if (this.ws) {
      this.send({ t: 'stop' });
      this.ws.close();
      this.ws = null;
    }
    this.set({ ...INITIAL });
  }

  private open() {
    this.set({ status: this.attempts > 0 ? 'reconnecting' : 'connecting' });
    const ws = new WebSocket(wsUrl(this.config));
    this.ws = ws;
    ws.onopen = () => {
      ws.send(JSON.stringify({ t: 'auth', token: this.config.token.trim(), client: 'phone' }));
    };
    ws.onmessage = (ev) => {
      let msg: any;
      try {
        msg = JSON.parse(String(ev.data));
      } catch {
        return;
      }
      this.handle(msg);
    };
    ws.onerror = () => {
      this.set({ lastError: 'Connection error' });
    };
    ws.onclose = (ev) => {
      if (this.ws !== ws) return;
      this.ws = null;
      this.clearTimers();
      if (ev.code === 4401) {
        this.wantOpen = false;
        this.set({ status: 'unauthorized', isDriver: false, lastError: 'Access token rejected' });
        return;
      }
      if (this.wantOpen) {
        this.attempts += 1;
        const delay = Math.min(5000, 500 * 2 ** Math.min(this.attempts, 4));
        this.set({ status: 'reconnecting', isDriver: false, latencyMs: null });
        this.reconnectTimer = setTimeout(() => {
          this.reconnectTimer = null;
          if (this.wantOpen) this.open();
        }, delay);
      } else {
        this.set({ status: 'idle' });
      }
    };
  }

  private clearTimers() {
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    if (this.pingTimer) clearInterval(this.pingTimer);
    this.reconnectTimer = null;
    this.pingTimer = null;
  }

  private handle(msg: any) {
    switch (msg.t) {
      case 'hello':
        this.attempts = 0;
        this.set({ status: 'connected', hello: msg as Hello, isDriver: !!msg.driver, lastError: null });
        this.pingTimer = setInterval(() => this.send({ t: 'ping', ts: Date.now() }), 1000);
        break;
      case 'telemetry':
        this.set({
          telemetry: msg as Telemetry,
          isDriver: !!msg.you_drive,
          estop: !!msg.drive?.estop,
        });
        break;
      case 'pong':
        if (typeof msg.ts === 'number') this.set({ latencyMs: Date.now() - msg.ts });
        break;
      case 'control':
        this.set({ isDriver: !!msg.driver });
        break;
      case 'estop':
        this.set({ estop: !!msg.on });
        break;
      case 'error':
        this.set({ lastError: String(msg.message ?? 'error') });
        break;
    }
  }

  private send(obj: object) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(obj));
      return true;
    }
    return false;
  }

  // ---- commands ------------------------------------------------------------------
  /** Normalised -1..1: vx forward, vy left, wz counter-clockwise. speed 0..1 */
  drive(vx: number, vy: number, wz: number, speed: number) {
    return this.send({ t: 'drive', vx, vy, wz, speed });
  }
  stop() {
    return this.send({ t: 'stop' });
  }
  takeControl() {
    return this.send({ t: 'claim', force: true });
  }
  setEstop(on: boolean) {
    this.set({ estop: on });
    return this.send({ t: 'estop', on });
  }
  beep() {
    return this.send({ t: 'beep' });
  }
  playSound(name: string) {
    return this.send({ t: 'sound', name });
  }
  /** Hand gesture mode: the robot watches its own camera for gestures. */
  setGestureMode(on: boolean) {
    this.set({ lastError: null });
    return this.send({ t: 'gesture', on });
  }
}
