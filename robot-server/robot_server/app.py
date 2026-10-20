"""HTTP + WebSocket API.

Endpoints
---------
GET  /api/health                  no auth. Liveness + name/version.
GET  /api/status                  Bearer token. Full status snapshot.
POST /api/camera/ticket           Bearer token. Returns a short-lived ticket for the MJPEG URL.
GET  /api/camera/stream?ticket=   MJPEG stream (multipart/x-mixed-replace).
GET  /api/camera/snapshot?ticket= One JPEG frame.
GET  /api/ws                      WebSocket. First message must be {"t":"auth","token":...}.

WebSocket messages (client -> robot)
  {"t":"auth","token":"...","client":"phone"}
  {"t":"drive","vx":0..1,"vy":0..1,"wz":0..1,"speed":0..1}   vx fwd, vy left, wz ccw (normalised)
  {"t":"stop"}
  {"t":"claim","force":true}   take driving control
  {"t":"release"}
  {"t":"estop","on":true|false}
  {"t":"beep"} | {"t":"sound","name":"ok"}
  {"t":"gesture","on":true|false}   hand gesture mode (robot camera)
  {"t":"ping","ts":123}

Robot -> client
  {"t":"hello",...} {"t":"telemetry",...} {"t":"pong","ts":..} {"t":"control","driver":bool}
  {"t":"error","message":"..."}
"""
import asyncio
import hmac
import itertools
import json
import logging
import os
import secrets
import time

from aiohttp import WSMsgType, web

from . import __version__

log = logging.getLogger("api")

TICKET_TTL = 120.0
_client_ids = itertools.count(1)


def _token_ok(expected, given):
    return bool(given) and hmac.compare_digest(expected.encode(), given.encode())


def _read_first(path, default=None):
    try:
        with open(path) as fh:
            return fh.read().strip()
    except Exception:
        return default


def _cpu_temp_c():
    temps = []
    base = "/sys/devices/virtual/thermal"
    if os.path.isdir(base):
        for zone in os.listdir(base):
            if zone.startswith("thermal_zone"):
                v = _read_first(os.path.join(base, zone, "temp"))
                if v and v.lstrip("-").isdigit():
                    temps.append(int(v) / 1000.0)
    return round(max(temps), 1) if temps else None


def _wifi_signal():
    raw = _read_first("/proc/net/wireless", "")
    for line in raw.splitlines():
        if line.strip().startswith("wlan0:"):
            parts = line.split()
            try:
                return {"link": float(parts[2].rstrip(".")), "dbm": float(parts[3].rstrip("."))}
            except (IndexError, ValueError):
                return None
    return None


class RobotApi(object):
    def __init__(self, cfg, board, drive, camera, audio, gestures=None):
        self.cfg = cfg
        self.gestures = gestures
        self.board = board
        self.drive = drive
        self.camera = camera
        self.audio = audio
        self.tickets = {}
        self.clients = {}
        self.started = time.time()

    # ---- helpers ----------------------------------------------------------
    def _check_bearer(self, request):
        header = request.headers.get("Authorization", "")
        token = header[7:] if header.startswith("Bearer ") else ""
        if not _token_ok(self.cfg["auth"]["token"], token):
            raise web.HTTPUnauthorized(text="invalid token")

    def _check_ticket(self, request):
        now = time.time()
        for k in [k for k, exp in self.tickets.items() if exp < now]:
            del self.tickets[k]
        ticket = request.query.get("ticket", "")
        if ticket not in self.tickets:
            raise web.HTTPUnauthorized(text="invalid or expired ticket")

    def battery(self):
        b = self.cfg["battery"]
        mv = self.board.battery_mv
        if not mv:
            return {"mv": None, "pct": None, "low": False}
        pct = (mv - b["empty_mv"]) * 100.0 / (b["full_mv"] - b["empty_mv"])
        return {"mv": mv, "pct": int(max(0, min(100, round(pct)))), "low": mv < b["low_warn_mv"]}

    def status(self, client_id=None):
        return {
            "name": self.cfg["server"]["name"],
            "version": __version__,
            "uptime_s": int(time.time() - self.started),
            "battery": self.battery(),
            "drive": self.drive.status(),
            "you_drive": client_id is not None and self.drive.driver_id == client_id,
            "camera": self.camera.status(),
            "cpu_temp_c": _cpu_temp_c(),
            "wifi": _wifi_signal(),
            "clients": len(self.clients),
            "gesture": self.gestures.status() if self.gestures else None,
        }

    # ---- HTTP handlers ----------------------------------------------------
    async def health(self, request):
        return web.json_response({"ok": True, "name": self.cfg["server"]["name"], "version": __version__})

    async def status_handler(self, request):
        self._check_bearer(request)
        return web.json_response(self.status())

    async def ticket(self, request):
        self._check_bearer(request)
        ticket = secrets.token_urlsafe(16)
        self.tickets[ticket] = time.time() + TICKET_TTL
        return web.json_response({"ticket": ticket, "expires_in": TICKET_TTL})

    async def snapshot(self, request):
        self._check_ticket(request)
        self.camera.add_viewer()
        try:
            got = await self.camera.next_frame(-1, timeout=8.0)
        finally:
            self.camera.remove_viewer()
        if not got:
            raise web.HTTPServiceUnavailable(text=self.camera.error or "no frame")
        return web.Response(body=got[1], content_type="image/jpeg", headers={"Cache-Control": "no-store"})

    async def stream(self, request):
        self._check_ticket(request)
        resp = web.StreamResponse(headers={
            "Content-Type": "multipart/x-mixed-replace; boundary=frame",
            "Cache-Control": "no-store, no-cache, must-revalidate",
            "Pragma": "no-cache",
            "Connection": "close",
        })
        await resp.prepare(request)
        self.camera.add_viewer()
        last_id = -1
        try:
            while True:
                got = await self.camera.next_frame(last_id, timeout=5.0)
                if not got:
                    continue
                last_id, jpeg = got
                await resp.write(b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: "
                                 + str(len(jpeg)).encode() + b"\r\n\r\n" + jpeg + b"\r\n")
        except (asyncio.CancelledError, ConnectionResetError):
            pass
        finally:
            self.camera.remove_viewer()
        return resp

    # ---- WebSocket --------------------------------------------------------
    async def ws(self, request):
        sock = web.WebSocketResponse(heartbeat=2.0, max_msg_size=64 * 1024)
        await sock.prepare(request)
        client_id = next(_client_ids)
        peer = request.remote
        try:
            first = await sock.receive(timeout=5.0)
            msg = json.loads(first.data) if first.type == WSMsgType.TEXT else {}
        except (asyncio.TimeoutError, ValueError):
            msg = {}
        if msg.get("t") != "auth" or not _token_ok(self.cfg["auth"]["token"], str(msg.get("token", ""))):
            log.warning("ws auth failed from %s", peer)
            await sock.send_json({"t": "error", "message": "unauthorized"})
            await sock.close(code=4401, message=b"unauthorized")
            return sock

        self.clients[client_id] = sock
        is_driver = self.drive.claim(client_id)
        log.info("client %s (%s, %s) connected, driver=%s", client_id, msg.get("client"), peer, is_driver)
        c = self.cfg["chassis"]
        await sock.send_json({
            "t": "hello", "client_id": client_id, "driver": is_driver,
            "name": self.cfg["server"]["name"], "version": __version__,
            "limits": {"max_linear": c["max_linear"], "max_angular": c["max_angular"]},
            "sounds": self.audio.sounds(),
            "features": {"gestures": bool(self.gestures and self.cfg["gestures"]["enabled"])},
        })
        telemetry = asyncio.ensure_future(self._telemetry(sock, client_id))
        try:
            async for m in sock:
                if m.type != WSMsgType.TEXT:
                    continue
                try:
                    data = json.loads(m.data)
                except ValueError:
                    continue
                await self._handle(sock, client_id, data)
        finally:
            telemetry.cancel()
            self.clients.pop(client_id, None)
            if self.drive.driver_id == client_id:
                self.drive.release(client_id)
                self.board.stop_motors()
            log.info("client %s disconnected", client_id)
        return sock

    async def _handle(self, sock, client_id, data):
        t = data.get("t")
        if t == "drive":
            ok = self.drive.command(client_id, data.get("vx", 0), data.get("vy", 0),
                                    data.get("wz", 0), data.get("speed", 1.0))
            if not ok and self.drive.driver_id != client_id:
                await sock.send_json({"t": "control", "driver": False})
        elif t == "stop":
            if self.drive.driver_id == client_id:
                self.drive.stop()
        elif t == "claim":
            if data.get("force") and self.gestures and self.gestures.enabled:
                self.gestures.disable("phone took control")
            if data.get("force") and self.drive.driver_id not in (None, client_id):
                old = self.clients.get(self.drive.driver_id)
                self.drive.release(self.drive.driver_id)
                if old is not None and not old.closed:
                    await old.send_json({"t": "control", "driver": False})
            await sock.send_json({"t": "control", "driver": self.drive.claim(client_id)})
        elif t == "release":
            self.drive.release(client_id)
            await sock.send_json({"t": "control", "driver": False})
        elif t == "estop":
            self.drive.set_estop(bool(data.get("on", True)))
            for other in list(self.clients.values()):
                if not other.closed:
                    await other.send_json({"t": "estop", "on": self.drive.estop})
        elif t == "gesture" and self.gestures:
            if data.get("on"):
                self.drive.stop()
                if not self.gestures.enable():
                    await sock.send_json({"t": "error", "message": self.gestures.error or "gestures unavailable"})
            else:
                self.gestures.disable("turned off from app")
                self.drive.claim(client_id)
                await sock.send_json({"t": "control", "driver": self.drive.driver_id == client_id})
        elif t == "beep":
            self.board.beep(1900, 0.1, 0.05, 1)
        elif t == "sound":
            self.audio.play(str(data.get("name", "")))
        elif t == "ping":
            await sock.send_json({"t": "pong", "ts": data.get("ts")})

    async def _telemetry(self, sock, client_id):
        try:
            while not sock.closed:
                payload = self.status(client_id)
                payload["t"] = "telemetry"
                await sock.send_json(payload)
                await asyncio.sleep(0.5)
        except (asyncio.CancelledError, ConnectionResetError, RuntimeError):
            pass


def build_app(api):
    app = web.Application()
    app.router.add_get("/api/health", api.health)
    app.router.add_get("/api/status", api.status_handler)
    app.router.add_post("/api/camera/ticket", api.ticket)
    app.router.add_get("/api/camera/stream", api.stream)
    app.router.add_get("/api/camera/snapshot", api.snapshot)
    app.router.add_get("/api/ws", api.ws)

    @web.middleware
    async def cors(request, handler):
        if request.method == "OPTIONS":
            resp = web.Response()
        else:
            resp = await handler(request)
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
        resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        return resp

    app.middlewares.append(cors)
    return app
