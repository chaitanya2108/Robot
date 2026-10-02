import { Ionicons } from '@expo/vector-icons';
import React from 'react';
import { StyleSheet, Text, View } from 'react-native';

import type { RobotState } from '../lib/robotClient';
import { colors, radius } from '../lib/theme';

function batteryIcon(pct: number | null): keyof typeof Ionicons.glyphMap {
  if (pct == null) return 'battery-dead-outline';
  if (pct > 70) return 'battery-full';
  if (pct > 30) return 'battery-half';
  return 'battery-dead';
}

function Pill({ children }: { children: React.ReactNode }) {
  return <View style={styles.pill}>{children}</View>;
}

export function Hud({ state, showStats }: { state: RobotState; showStats: boolean }) {
  const t = state.telemetry;
  const b = t?.battery;
  const batteryColor = b?.low ? colors.danger : (b?.pct ?? 100) < 30 ? colors.warn : colors.good;
  const dot =
    state.status === 'connected' ? colors.good : state.status === 'unauthorized' ? colors.danger : colors.warn;
  const statusText =
    state.status === 'connected'
      ? (state.hello?.name ?? 'Robot')
      : state.status === 'unauthorized'
        ? 'Token rejected'
        : state.status === 'idle'
          ? 'Offline'
          : 'Connecting...';

  return (
    <View style={styles.row} pointerEvents="none">
      <Pill>
        <View style={[styles.dot, { backgroundColor: dot }]} />
        <Text style={styles.text}>{statusText}</Text>
      </Pill>
      {b?.pct != null && (
        <Pill>
          <Ionicons name={batteryIcon(b.pct)} size={16} color={batteryColor} />
          <Text style={[styles.text, { color: batteryColor }]}>
            {b.pct}%{showStats && b.mv ? `  ${(b.mv / 1000).toFixed(1)}V` : ''}
          </Text>
        </Pill>
      )}
      {showStats && t?.wifi && (
        <Pill>
          <Ionicons name="wifi" size={14} color={t.wifi.dbm > -67 ? colors.good : colors.warn} />
          <Text style={styles.text}>{t.wifi.dbm} dBm</Text>
        </Pill>
      )}
      {showStats && state.latencyMs != null && (
        <Pill>
          <Ionicons name="pulse" size={14} color={state.latencyMs < 120 ? colors.good : colors.warn} />
          <Text style={styles.text}>{state.latencyMs} ms</Text>
        </Pill>
      )}
      {showStats && t?.camera.running && (
        <Pill>
          <Ionicons name="videocam" size={14} color={colors.textDim} />
          <Text style={styles.text}>{t.camera.fps.toFixed(0)} fps</Text>
        </Pill>
      )}
      {showStats && t?.cpu_temp_c != null && (
        <Pill>
          <Ionicons name="thermometer-outline" size={14} color={t.cpu_temp_c > 70 ? colors.warn : colors.textDim} />
          <Text style={styles.text}>{t.cpu_temp_c.toFixed(0)}°C</Text>
        </Pill>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, alignItems: 'center' },
  pill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: colors.overlay,
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: radius.pill,
  },
  dot: { width: 8, height: 8, borderRadius: 4 },
  text: { color: colors.text, fontSize: 12, fontVariant: ['tabular-nums'] },
});
