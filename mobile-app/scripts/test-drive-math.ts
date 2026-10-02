// Quick sanity test: node --experimental-strip-types scripts/test-drive-math.ts
import { applyDeadzone, mixCommand } from '../src/lib/driveMath.ts';
const opts = { deadzone: 0.1, fineControl: false };
const eq = (a: number, b: number) => Math.abs(a - b) < 1e-3;
const check = (name: string, ok: boolean) => { console.log((ok ? 'ok   ' : 'FAIL ') + name); if (!ok) process.exitCode = 1; };
let c = mixCommand('dual', { x: 0, y: 1 }, { x: 0, y: 0 }, opts);
check('left stick up = forward', eq(c.vx, 1) && c.vy === 0 && c.wz === 0);
c = mixCommand('dual', { x: 1, y: 0 }, { x: 0, y: 0 }, opts);
check('left stick right = strafe right (vy<0)', eq(c.vy, -1) && c.vx === 0);
c = mixCommand('dual', { x: 0, y: 0 }, { x: 1, y: 0 }, opts);
check('right stick right = turn clockwise (wz<0)', eq(c.wz, -1));
c = mixCommand('single', { x: -1, y: 0 }, { x: 0, y: 0 }, opts);
check('single: stick left = turn left (wz>0), no strafe', eq(c.wz, 1) && c.vy === 0);
check('inside dead zone = zero', applyDeadzone({ x: 0.05, y: 0.05 }, 0.1).x === 0);
check('edge still reaches 1', eq(Math.hypot(...Object.values(applyDeadzone({ x: 0, y: 1 }, 0.2)) as [number, number]), 1));
c = mixCommand('dual', { x: 0, y: 0.5 }, { x: 0, y: 0 }, { deadzone: 0, fineControl: true });
check('fine control squares input', eq(c.vx, 0.25));
