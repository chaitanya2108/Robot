import { Redirect, router, useFocusEffect } from 'expo-router';
import * as Haptics from 'expo-haptics';
import { useKeepAwake } from 'expo-keep-awake';
import React, { useCallback, useEffect, useRef, useState } from 'react';
import { FlatList, Modal, Pressable, StyleSheet, Text, useWindowDimensions, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { CameraView } from '../components/CameraView';
import { EStopButton } from '../components/EStopButton';
import { GestureHelp, GesturePanel } from '../components/GesturePanel';
import { Hud } from '../components/Hud';
import { Joystick } from '../components/Joystick';
import { Button, IconButton, Segmented } from '../components/ui';
import { isZero, mixCommand, type Stick } from '../lib/driveMath';
import { useRobot, useRobotState } from '../lib/RobotProvider';
import { colors, radius } from '../lib/theme';
import { SPEED_LEVELS } from '../lib/types';

const SEND_INTERVAL_MS = 50; // 20 Hz, well inside the robot's 400 ms watchdog

export default function Drive() {
  useKeepAwake();
  const { robot, client, settings, updateSettings } = useRobot();
  const state = useRobotState();
  const { width, height } = useWindowDimensions();
  const insets = useSafeAreaInsets();
  const landscape = width > height;
  const [soundsOpen, setSoundsOpen] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);
  const [dismissedError, setDismissedError] = useState<string | null>(null);

  const left = useRef<Stick>({ x: 0, y: 0 });
  const right = useRef<Stick>({ x: 0, y: 0 });
  const sentZero = useRef(true);
  const settingsRef = useRef(settings);
  useEffect(() => {
    settingsRef.current = settings;
  }, [settings]);
  const onLeft = useCallback((s: Stick) => {
    left.current = s;
  }, []);
  const onRight = useCallback((s: Stick) => {
    right.current = s;
  }, []);
  const hapticsOn = settings.haptics;
  const onStickActive = useCallback(
    (active: boolean) => {
      if (active && hapticsOn) Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    },
    [hapticsOn],
  );

  // Drive loop: stream commands while a stick is off-centre, one stop when released.
  useEffect(() => {
    if (!client) return;
    const timer = setInterval(() => {
      const s = settingsRef.current;
      const cmd = mixCommand(s.controlMode, left.current, right.current, s);
      const speed = SPEED_LEVELS[s.speedLevel]?.value ?? SPEED_LEVELS[0].value;
      if (!isZero(cmd)) {
        client.drive(cmd.vx, cmd.vy, cmd.wz, speed);
        sentZero.current = false;
      } else if (!sentZero.current) {
        client.drive(0, 0, 0, speed);
        client.stop();
        sentZero.current = true;
      }
    }, SEND_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [client]);

  // Leaving the screen always stops the robot.
  useFocusEffect(
    useCallback(
      () => () => {
        left.current = { x: 0, y: 0 };
        right.current = { x: 0, y: 0 };
        client?.stop();
      },
      [client],
    ),
  );

  if (!robot || !client) return <Redirect href="/connect" />;

  const connected = state.status === 'connected';
  const gesture = state.telemetry?.gesture ?? null;
  const gestureOn = connected && !!gesture?.enabled;
  const gesturesAvailable = !!state.hello?.features?.gestures;
  const gestureError = !gestureOn && gesture?.error && gesture.error !== dismissedError ? gesture.error : null;
  const canDrive = connected && state.isDriver && !state.estop && !gestureOn;
  const toggleGestures = () => {
    if (settings.haptics) Haptics.selectionAsync();
    client.setGestureMode(!gestureOn);
    if (!gestureOn && !settings.cameraEnabled) updateSettings({ cameraEnabled: true });
  };
  const stickSize = Math.min(landscape ? height * 0.42 : width * 0.4, 190);
  const dual = settings.controlMode === 'dual';

  const speedPicker = (
    <Segmented
      options={SPEED_LEVELS.map((l, i) => ({ label: l.label, value: i }))}
      value={settings.speedLevel}
      onChange={(v) => updateSettings({ speedLevel: v })}
    />
  );
  const estop = (
    <EStopButton
      engaged={state.estop}
      haptics={settings.haptics}
      compact={!landscape}
      onChange={(on) => client.setEstop(on)}
    />
  );
  const leftStick = (
    <Joystick
      size={stickSize}
      label={dual ? 'MOVE' : 'DRIVE'}
      disabled={!canDrive}
      onActiveChange={onStickActive}
      onChange={onLeft}
    />
  );
  const rightStick = dual ? (
    <Joystick
      size={stickSize}
      axis="x"
      label="TURN"
      disabled={!canDrive}
      onActiveChange={onStickActive}
      onChange={onRight}
    />
  ) : (
    <View style={{ width: stickSize }} />
  );
  const toolbar = (
    <View style={styles.toolbar}>
      <IconButton
        icon={settings.cameraEnabled ? 'videocam' : 'videocam-off'}
        label="Toggle camera"
        onPress={() => updateSettings({ cameraEnabled: !settings.cameraEnabled })}
      />
      {gesturesAvailable && (
        <IconButton icon="hand-left-outline" label="Gesture control" active={gestureOn} onPress={toggleGestures} />
      )}
      <IconButton icon="megaphone-outline" label="Horn" onPress={() => client.beep()} />
      {(state.hello?.sounds.length ?? 0) > 0 && (
        <IconButton icon="musical-notes-outline" label="Sounds" onPress={() => setSoundsOpen(true)} />
      )}
      <IconButton icon="settings-outline" label="Settings" onPress={() => router.push('/settings')} />
    </View>
  );

  const banner = !connected ? (
    <View style={styles.banner}>
      <Text style={styles.bannerTitle}>
        {state.status === 'unauthorized' ? 'The robot rejected your access token' : 'Connecting to robot...'}
      </Text>
      {state.status === 'unauthorized' ? (
        <Button title="Update connection" onPress={() => router.push('/connect')} />
      ) : (
        <Text style={styles.bannerText}>
          {robot.host}:{robot.port}. The robot stops by itself if the connection drops.
        </Text>
      )}
    </View>
  ) : gestureOn && gesture ? (
    <GesturePanel status={gesture} onStop={() => client.setGestureMode(false)} onHelp={() => setHelpOpen(true)} />
  ) : gestureError ? (
    <View style={[styles.banner, { borderColor: colors.warn }]}>
      <Text style={styles.bannerTitle}>Gesture control stopped</Text>
      <Text style={styles.bannerText}>{gestureError}</Text>
      <Button title="OK" variant="secondary" onPress={() => setDismissedError(gestureError)} />
    </View>
  ) : !state.isDriver ? (
    <View style={styles.banner}>
      <Text style={styles.bannerTitle}>Another device is driving</Text>
      <Button title="Take control" icon="hand-left-outline" onPress={() => client.takeControl()} />
    </View>
  ) : state.estop ? (
    <View style={[styles.banner, { borderColor: colors.danger }]}>
      <Text style={styles.bannerTitle}>Emergency stop is on</Text>
      <Text style={styles.bannerText}>Hold the STOP button to release it.</Text>
    </View>
  ) : null;

  return (
    <View style={styles.root}>
      {landscape ? (
        <>
          <CameraView robot={robot} enabled={settings.cameraEnabled} connected={connected} />
          <View style={[styles.topBar, { paddingTop: insets.top + 8, paddingLeft: insets.left + 12, paddingRight: insets.right + 12 }]}>
            <View style={{ flex: 1 }}>
              <Hud state={state} showStats={settings.showStats} />
            </View>
            {toolbar}
          </View>
          {banner && (
            <View
              style={[styles.bannerWrap, gestureOn && { justifyContent: 'flex-start', paddingTop: insets.top + 64 }]}
              pointerEvents="box-none"
            >
              {banner}
            </View>
          )}
          <View
            style={[
              styles.bottomRow,
              { paddingBottom: insets.bottom + 12, paddingLeft: insets.left + 20, paddingRight: insets.right + 20 },
            ]}
            pointerEvents="box-none"
          >
            {leftStick}
            <View style={styles.center}>
              {speedPicker}
              {estop}
            </View>
            {rightStick}
          </View>
        </>
      ) : (
        <>
          <View style={[styles.portraitCamera, { height: Math.min(width * 0.625, height * 0.45) + insets.top }]}>
            <CameraView robot={robot} enabled={settings.cameraEnabled} connected={connected} />
            <View style={[styles.topBar, { paddingTop: insets.top + 8, paddingHorizontal: 12 }]}>
              <View style={{ flex: 1 }}>
                <Hud state={state} showStats={settings.showStats} />
              </View>
            </View>
          </View>
          <View style={[styles.portraitControls, { paddingBottom: insets.bottom + 16 }]}>
            <View style={styles.portraitTop}>
              {toolbar}
              {estop}
            </View>
            {banner}
            <View style={{ alignItems: 'center' }}>{speedPicker}</View>
            <View style={styles.portraitSticks}>
              {leftStick}
              {rightStick}
            </View>
          </View>
        </>
      )}

      <GestureHelp visible={helpOpen} onClose={() => setHelpOpen(false)} />
      <Modal visible={soundsOpen} transparent animationType="fade" onRequestClose={() => setSoundsOpen(false)}>
        <Pressable style={styles.modalBackdrop} onPress={() => setSoundsOpen(false)}>
          <View style={styles.modalCard}>
            <Text style={styles.modalTitle}>Play a sound on the robot</Text>
            <FlatList
              data={state.hello?.sounds ?? []}
              keyExtractor={(s) => s}
              renderItem={({ item }) => (
                <Pressable style={styles.soundItem} onPress={() => client.playSound(item)}>
                  <Text style={styles.soundText}>{item.replace(/_/g, ' ')}</Text>
                </Pressable>
              )}
            />
          </View>
        </Pressable>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#000' },
  topBar: { position: 'absolute', top: 0, left: 0, right: 0, flexDirection: 'row', alignItems: 'flex-start', gap: 12 },
  toolbar: { flexDirection: 'row', gap: 8 },
  bottomRow: {
    position: 'absolute',
    left: 0,
    right: 0,
    bottom: 0,
    flexDirection: 'row',
    alignItems: 'flex-end',
    justifyContent: 'space-between',
  },
  center: { alignItems: 'center', gap: 12, paddingBottom: 8 },
  bannerWrap: { ...StyleSheet.absoluteFill, alignItems: 'center', justifyContent: 'center' },
  banner: {
    backgroundColor: colors.overlay,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radius.lg,
    padding: 16,
    gap: 10,
    alignItems: 'center',
    maxWidth: 420,
    alignSelf: 'center',
  },
  bannerTitle: { color: colors.text, fontSize: 16, fontWeight: '700', textAlign: 'center' },
  bannerText: { color: colors.textDim, fontSize: 13, textAlign: 'center' },
  portraitCamera: { width: '100%', backgroundColor: '#000' },
  portraitControls: { flex: 1, backgroundColor: colors.bg, paddingHorizontal: 16, paddingTop: 14, gap: 14 },
  portraitTop: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  portraitSticks: { flex: 1, flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  modalBackdrop: { flex: 1, backgroundColor: 'rgba(0,0,0,0.6)', alignItems: 'center', justifyContent: 'center', padding: 24 },
  modalCard: { backgroundColor: colors.surface, borderRadius: radius.lg, padding: 16, width: '100%', maxWidth: 420, maxHeight: '80%' },
  modalTitle: { color: colors.text, fontSize: 16, fontWeight: '700', marginBottom: 8 },
  soundItem: { paddingVertical: 12, borderBottomColor: colors.border, borderBottomWidth: StyleSheet.hairlineWidth },
  soundText: { color: colors.text, fontSize: 15, textTransform: 'capitalize' },
});
