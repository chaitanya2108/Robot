import type { ControlMode } from './types';

export type Stick = { x: number; y: number }; // -1..1, x right, y up

/** Radial dead zone that rescales so output still reaches 1.0 at the edge. */
export function applyDeadzone(s: Stick, deadzone: number): Stick {
  const mag = Math.hypot(s.x, s.y);
  if (mag <= deadzone || mag === 0) return { x: 0, y: 0 };
  const scaled = Math.min(1, (mag - deadzone) / (1 - deadzone));
  return { x: (s.x / mag) * scaled, y: (s.y / mag) * scaled };
}

/** Squared response keeps the same sign; gives finer control near the centre. */
export const fine = (v: number) => Math.sign(v) * v * v;

export type DriveCommand = { vx: number; vy: number; wz: number };

/**
 * Turn stick positions into a normalised robot command.
 *   vx: forward, vy: left (strafe), wz: counter-clockwise rotation
 * dual:   left stick = move + strafe, right stick (x) = rotate
 * single: one stick, up/down = forward/back, left/right = rotate
 */
export function mixCommand(
  mode: ControlMode,
  left: Stick,
  right: Stick,
  opts: { deadzone: number; fineControl: boolean },
): DriveCommand {
  const shape = (v: number) => (opts.fineControl ? fine(v) : v);
  const l = applyDeadzone(left, opts.deadzone);
  const r = applyDeadzone(right, opts.deadzone);
  const round = (v: number) => Math.round(v * 1000) / 1000 || 0;
  if (mode === 'single') {
    return { vx: round(shape(l.y)), vy: 0, wz: round(shape(-l.x)) };
  }
  return { vx: round(shape(l.y)), vy: round(shape(-l.x)), wz: round(shape(-r.x)) };
}

export const isZero = (c: DriveCommand) => c.vx === 0 && c.vy === 0 && c.wz === 0;
