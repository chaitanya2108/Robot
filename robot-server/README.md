# robot-server

Runs on the robot (Jetson Nano, Ubuntu 18.04, Python 3.6). Replaces the Hiwonder ROS stack with one small service:

- **Driving**: WebSocket commands -> mecanum kinematics -> STM32 motor board on `/dev/rrc`
- **Camera**: `camera_bridge` (C++, Deptrum Aurora 930 SDK) -> MJPEG over HTTP, only while someone watches
- **Telemetry**: battery, WiFi signal, CPU temperature, camera fps, drive state
- **Extras**: buzzer horn, sound clips on the USB speaker, physical buttons (KEY1 = back to hotspot mode, hold KEY2 = shut down)
- **Security**: every request needs the access token; camera URLs use short-lived tickets so the token never appears in a URL

No ROS required. ROS 1 Melodic is still installed in `/opt/ros` if you want it later.

## Layout on the robot

```
~/robot_app/
  config.yaml        your settings + access token (created on first start, chmod 600)
  server/            this folder
  vendor/            hardware code kept from Hiwonder (board SDK, camera SDK, lidar driver, sounds, udev rules)
```

## Install / update

From your Windows PC, in the Robot folder:

```powershell
powershell -ExecutionPolicy Bypass -File robot-server\scripts\deploy.ps1
```

Or on the robot itself: `bash ~/robot_app/server/scripts/install.sh`

The installer builds the camera bridge, installs Python deps, creates the token and (re)starts the `robot-server` systemd service. It prints the address and token at the end.

## Everyday commands (on the robot)

```bash
journalctl -u robot-server -f                 # live logs (alias: robot-logs)
sudo systemctl restart robot-server           # restart (alias: robot-restart)
python3 -m robot_server --show-token          # print the access token (run in ~/robot_app/server)
```

To change the token: delete the `auth:` block from `~/robot_app/config.yaml` and restart. A new one is generated.

## Tuning

Edit `~/robot_app/config.yaml` (see `config.example.yaml`) and restart the service:

- `chassis.max_linear` / `max_angular`: top speed at full stick
- `chassis.invert_x` / `invert_y` / `invert_rotation`: flip a direction if it's backwards
- `safety.command_timeout`: how quickly the robot stops when commands stop arriving
- `camera.mode` / `quality` / `fps`: video resolution and bandwidth

## API

See the docstring at the top of `robot_server/app.py`. Summary:

| Endpoint | Auth | Purpose |
|---|---|---|
| `GET /api/health` | none | liveness |
| `GET /api/status` | Bearer token | status snapshot |
| `POST /api/camera/ticket` | Bearer token | 2-minute ticket for the camera URLs |
| `GET /api/camera/stream?ticket=` | ticket | MJPEG stream |
| `GET /api/camera/snapshot?ticket=` | ticket | single JPEG |
| `GET /api/ws` | first message `{"t":"auth","token":...}` | drive commands + telemetry |

## Tests

```bash
python3 -m pytest tests       # on a PC
```
