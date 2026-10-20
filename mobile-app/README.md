# Robot Remote (mobile app)

Expo / React Native app (TypeScript, Expo SDK 57, Expo Router) that drives the robot with on-screen joysticks and shows its live camera.

## Run it on your phone (development)

1. Install **Expo Go** on your phone (App Store / Play Store).
2. On your PC, in this folder:
   ```bash
   npm install
   npx expo start
   ```
3. Scan the QR code with your phone (Camera app on iPhone, Expo Go on Android). Phone, PC and robot must all be on the same WiFi.
4. In the app, enter the robot address (`192.168.1.105`), port `8765` and the access token.

Get the token from the robot:

```bash
ssh hiwonder@192.168.1.105 "cd ~/robot_app/server && python3 -m robot_server --show-token"
```

## Controls

| Control | What it does |
|---|---|
| Left stick (MOVE) | Forward/back and strafe left/right (mecanum) |
| Right stick (TURN) | Rotate in place |
| Slow / Normal / Fast | 30% / 60% / 100% of the robot's top speed |
| STOP | Emergency stop. Tap to engage, **hold** to release |
| Megaphone | Horn (buzzer) |
| Notes | Play a sound clip on the robot speaker |
| Camera icon | Turn the video feed on/off (saves battery and WiFi) |
| Hand icon | Gesture control: drive the robot with hand signs in front of its camera (see below) |

## Gesture control

Tap the hand icon. The robot starts watching its own camera (the video shows your hand skeleton) and the joysticks are disabled. Tap **Use joysticks** to take over again. STOP on the phone always stops the robot, in any mode.

| Your hand | Robot |
|---|---|
| Open palm or fist | Stop (instant) |
| Thumbs up / down | Forward / backward |
| One finger pointing left / right | Turn that way |
| Two fingers pointing left / right | Slide sideways that way |
| Peace sign, hold 1 s | **Follow me**: keeps your hand centred and at the same distance |
| In Follow me: fist, hold 1 s | Back to gesture commands |
| Hand out of view | Stop (Follow me ends after 5 s) |

Left/right is the way you point, so the robot goes where you point. Gesture mode keeps running if you put the phone away; show an open palm or fist to stop. The ? in the gesture panel shows this list in the app.

Settings let you switch to one-stick (car-style) driving, change the dead zone, turn off fine control, haptics and the stats overlay. Rotate the phone for the full-screen landscape layout.

## Safety model

- The robot enforces its own top speed and acceleration limits (in `~/robot_app/config.yaml` on the robot). The app only sends -1..1 stick values.
- The app sends commands 20 times a second while a stick is held. If the robot hears nothing for 0.4 s (WiFi drop, app killed, phone locked) it stops by itself.
- In joystick mode, going to the background, leaving the drive screen or losing the connection stops the robot. Gesture mode is hands-free, so it keeps running without the phone; any stop pose or losing sight of your hand stops it.
- Only one phone can drive at a time. A second phone sees a "Take control" button.

## Project layout

```
src/
  app/                 Screens (Expo Router)
    _layout.tsx        Providers, navigation, keeps the connection open in the foreground
    index.tsx          Sends you to Connect or Drive
    connect.tsx        Robot address + token, tests the connection
    drive.tsx          Camera + joysticks + HUD + gesture mode (portrait and landscape layouts)
    settings.tsx       Driving and display settings, robot info
  components/          Joystick, CameraView (MJPEG in a WebView), Hud, EStopButton, GesturePanel, UI kit
  lib/
    robotClient.ts     WebSocket client: auth, auto-reconnect, telemetry, commands
    api.ts             HTTP calls: health check, camera ticket
    driveMath.ts       Dead zone, response curve, stick -> robot command mixing
    storage.ts         Token in the OS keychain (SecureStore), settings in AsyncStorage
    RobotProvider.tsx  App-wide state
scripts/test-drive-math.ts   npm test
```

## Checks

```bash
npm run typecheck
npm test
```

## Building an installable app

All native modules used are included in Expo Go, so no custom dev client is needed for development. To make a standalone app:

```bash
npx eas-cli@latest login
npx eas-cli@latest build -p android --profile preview    # APK you can sideload
npx eas-cli@latest build -p ios --profile production      # needs an Apple developer account
```

`app.json` already allows plain `http://` / `ws://` to the robot on your LAN (Android cleartext, iOS local networking).
