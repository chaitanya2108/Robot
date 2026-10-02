import { router } from 'expo-router';
import React from 'react';
import { Alert, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { Button, Row, Section, Segmented, ToggleRow } from '../components/ui';
import { useRobot, useRobotState } from '../lib/RobotProvider';
import { colors } from '../lib/theme';
import { SPEED_LEVELS } from '../lib/types';

function Stepper({ value, onChange, step, min, max, format }: {
  value: number; onChange: (v: number) => void; step: number; min: number; max: number; format: (v: number) => string;
}) {
  const set = (v: number) => onChange(Math.round(Math.min(max, Math.max(min, v)) * 100) / 100);
  return (
    <View style={styles.stepper}>
      <Pressable style={styles.stepBtn} onPress={() => set(value - step)}><Text style={styles.stepText}>-</Text></Pressable>
      <Text style={styles.stepValue}>{format(value)}</Text>
      <Pressable style={styles.stepBtn} onPress={() => set(value + step)}><Text style={styles.stepText}>+</Text></Pressable>
    </View>
  );
}

export default function SettingsScreen() {
  const { robot, settings, updateSettings, clearRobot } = useRobot();
  const state = useRobotState();
  const insets = useSafeAreaInsets();
  const t = state.telemetry;
  const limits = state.hello?.limits;

  return (
    <ScrollView contentContainerStyle={[styles.container, { paddingBottom: insets.bottom + 24 }]}>
      <Section title="Driving">
        <Row label="Controls" detail={settings.controlMode === 'dual' ? 'Left stick moves and strafes, right stick turns' : 'One stick, like a car'}>
          <Segmented
            options={[{ label: 'Two sticks', value: 'dual' }, { label: 'One stick', value: 'single' }]}
            value={settings.controlMode}
            onChange={(v) => updateSettings({ controlMode: v })}
          />
        </Row>
        <Row label="Default speed">
          <Segmented
            options={SPEED_LEVELS.map((l, i) => ({ label: l.label, value: i }))}
            value={settings.speedLevel}
            onChange={(v) => updateSettings({ speedLevel: v })}
          />
        </Row>
        <Row label="Stick dead zone" detail="How far you must push before the robot moves">
          <Stepper value={settings.deadzone} onChange={(v) => updateSettings({ deadzone: v })} step={0.02} min={0} max={0.4}
            format={(v) => `${Math.round(v * 100)}%`} />
        </Row>
        <ToggleRow label="Fine control" detail="Gentler response near the centre of the stick"
          value={settings.fineControl} onChange={(v) => updateSettings({ fineControl: v })} />
        <ToggleRow label="Haptics" value={settings.haptics} onChange={(v) => updateSettings({ haptics: v })} />
      </Section>

      <Section title="Display">
        <ToggleRow label="Camera" value={settings.cameraEnabled} onChange={(v) => updateSettings({ cameraEnabled: v })} />
        <ToggleRow label="Show stats" detail="Voltage, WiFi, latency, fps, temperature"
          value={settings.showStats} onChange={(v) => updateSettings({ showStats: v })} />
      </Section>

      <Section title="Robot">
        <Row label="Address" detail={robot ? `${robot.host}:${robot.port}` : 'Not set'} />
        <Row label="Status" detail={state.status === 'connected' ? `Connected, server v${state.hello?.version}` : state.status} />
        {t?.battery.mv ? <Row label="Battery" detail={`${(t.battery.mv / 1000).toFixed(2)} V (${t.battery.pct}%)`} /> : null}
        {limits ? <Row label="Top speed" detail={`${limits.max_linear} m/s, ${limits.max_angular} rad/s (set on the robot)`} /> : null}
        {t ? <Row label="Uptime" detail={`${Math.floor(t.uptime_s / 60)} min`} /> : null}
      </Section>

      <View style={{ gap: 10 }}>
        <Button title="Change robot or token" variant="secondary" icon="swap-horizontal" onPress={() => router.push('/connect')} />
        <Button
          title="Forget this robot"
          variant="danger"
          icon="trash-outline"
          onPress={() =>
            Alert.alert('Forget robot?', 'The saved address and token will be removed from this phone.', [
              { text: 'Cancel', style: 'cancel' },
              { text: 'Forget', style: 'destructive', onPress: async () => { await clearRobot(); router.replace('/connect'); } },
            ])
          }
        />
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { padding: 16, gap: 22 },
  stepper: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  stepBtn: { width: 34, height: 34, borderRadius: 17, backgroundColor: colors.surfaceHi, alignItems: 'center', justifyContent: 'center' },
  stepText: { color: colors.text, fontSize: 18, fontWeight: '700' },
  stepValue: { color: colors.text, width: 44, textAlign: 'center', fontVariant: ['tabular-nums'] },
});
