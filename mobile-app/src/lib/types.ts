export type RobotConfig = {
  host: string;
  port: number;
  token: string;
};

export type ControlMode = 'dual' | 'single';

export type Settings = {
  /** dual = left stick moves (incl. strafe), right stick turns. single = one stick, car-style. */
  controlMode: ControlMode;
  /** Index into SPEED_LEVELS. */
  speedLevel: number;
  /** 0..0.4, radial dead zone on each stick. */
  deadzone: number;
  /** Square the stick input for finer control near the centre. */
  fineControl: boolean;
  haptics: boolean;
  showStats: boolean;
  cameraEnabled: boolean;
};

export const SPEED_LEVELS = [
  { label: 'Slow', value: 0.3 },
  { label: 'Normal', value: 0.6 },
  { label: 'Fast', value: 1.0 },
] as const;

export const DEFAULT_SETTINGS: Settings = {
  controlMode: 'dual',
  speedLevel: 0,
  deadzone: 0.12,
  fineControl: true,
  haptics: true,
  showStats: true,
  cameraEnabled: true,
};

export type Battery = { mv: number | null; pct: number | null; low: boolean };

export type Telemetry = {
  name: string;
  version: string;
  uptime_s: number;
  battery: Battery;
  drive: { vx: number; vy: number; wz: number; moving: boolean; estop: boolean; has_driver: boolean };
  you_drive: boolean;
  camera: { running: boolean; fps: number; viewers: number; error: string | null };
  cpu_temp_c: number | null;
  wifi: { link: number; dbm: number } | null;
  clients: number;
  gesture: GestureStatus | null;
};

export type GestureStatus = {
  enabled: boolean;
  ready: boolean;
  mode: 'command' | 'follow' | null;
  gesture: string | null;
  action: string | null;
  fps: number;
  infer_ms: number | null;
  error: string | null;
};

export type Hello = {
  client_id: number;
  driver: boolean;
  name: string;
  version: string;
  limits: { max_linear: number; max_angular: number };
  sounds: string[];
  features?: { gestures?: boolean };
};

export type ConnectionStatus = 'idle' | 'connecting' | 'connected' | 'reconnecting' | 'unauthorized';
