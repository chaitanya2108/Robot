# Robot

Personal remote-control system for the Hiwonder ROSOrin mecanum robot (Jetson Nano).

```
Phone app (Expo/React Native)  <--- home WiFi --->  robot-server (Python, on the Jetson)
   joysticks, camera view,         WebSocket            motor board (/dev/rrc)
   battery, e-stop                 + MJPEG              Aurora 930 camera
```

| Folder | What it is |
|---|---|
| `mobile-app/` | The phone app. See `mobile-app/README.md` |
| `robot-server/` | The service running on the robot. See `robot-server/README.md` |

## Quick start

1. Robot: already installed and starts on boot. Address `192.168.1.105:8765`.
2. Token: `ssh hiwonder@192.168.1.105 "cd ~/robot_app/server && python3 -m robot_server --show-token"`
3. Phone: `cd mobile-app && npm install && npx expo start`, scan the QR code with Expo Go, enter the address and token.

## Robot facts

- NVIDIA Jetson Nano 4GB, Ubuntu 18.04, JetPack R32.7.4, Python 3.6
- STM32 motor board on `/dev/rrc` (1 Mbaud): 4 mecanum motors, battery voltage, IMU, buzzer, LED
- Deptrum Aurora 930 depth camera (RGB 640x400 via vendor SDK)
- LD19 lidar on `/dev/lidar` (driver source kept in `~/robot_app/vendor/lidar`, not used yet)
- USB speaker (ALSA card 2), physical buttons on GPIO 25 / 4
- SSH: `hiwonder@192.168.1.105`

## History

- 2026-09-30: Original Hiwonder software backed up to the PC Desktop (`robot_backup_2026-09-30`), removed from the robot, replaced by `robot-server`. Useful hardware code kept in `~/robot_app/vendor`.

## Ideas for later

- Hand gesture control using the camera
- Lidar: obstacle stop + radar view in the app
- Depth stream / point cloud
- ROS 2 bridge for mapping and navigation
