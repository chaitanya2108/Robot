"""Entry point: python3 -m robot_server [--config PATH] [--fake-board] [--show-token]"""
import argparse
import asyncio
import logging
import sys

from aiohttp import web

from . import __version__, config
from .app import RobotApi, build_app
from .audio import Audio
from .board import BoardUnavailable, FakeBoard, MotorBoard
from .buttons import Buttons
from .camera import CameraService
from .drive import DriveController


def main(argv=None):
    parser = argparse.ArgumentParser(prog="robot_server")
    parser.add_argument("--config", help="path to config.yaml")
    parser.add_argument("--fake-board", action="store_true", help="run without the motor board")
    parser.add_argument("--show-token", action="store_true", help="print the access token and exit")
    args = parser.parse_args(argv)

    cfg = config.load(args.config)
    if args.show_token:
        print(cfg["auth"]["token"])
        return 0

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    log = logging.getLogger("robot_server")
    log.info("robot_server %s starting (config %s)", __version__, cfg["_path"])

    if args.fake_board:
        board = FakeBoard()
    else:
        try:
            board = MotorBoard(cfg["board"]["device"], cfg["board"]["baudrate"])
        except BoardUnavailable as exc:
            log.error("%s", exc)
            return 1

    # One loop for everything: on Python 3.6 asyncio objects are bound to the
    # loop that was current when they were created.
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    drive = DriveController(board, cfg["chassis"], cfg["safety"])
    camera = CameraService(cfg["camera"], loop)
    audio = Audio(cfg["audio"])
    api = RobotApi(cfg, board, drive, camera, audio)
    buttons = Buttons(cfg["buttons"], board, on_shutdown=board.stop_motors)

    app = build_app(api)

    async def on_startup(_app):
        drive.start(loop)
        buttons.start()
        board.beep(1900, 0.05, 0.05, 2)  # two short chirps = server ready

    async def on_shutdown(_app):
        log.info("shutting down")
        for sock in list(api.clients.values()):
            await sock.close()
        await drive.shutdown()
        camera.shutdown()
        board.close()

    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)
    web.run_app(app, host=cfg["server"]["host"], port=cfg["server"]["port"], loop=loop,
                access_log=None, print=lambda *a: log.info("listening on port %s", cfg["server"]["port"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
