import { Ionicons } from '@expo/vector-icons';
import React from 'react';
import { FlatList, Modal, Pressable, StyleSheet, Text, View } from 'react-native';

import { colors, radius } from '../lib/theme';
import type { GestureStatus } from '../lib/types';

const GESTURE_LABELS: Record<string, string> = {
  none: 'No hand',
  open_palm: 'Open palm',
  fist: 'Fist',
  thumbs_up: 'Thumbs up',
  thumbs_down: 'Thumbs down',
  point_left: 'Pointing left',
  point_right: 'Pointing right',
  point_up: 'Pointing up',
  two_left: 'Two fingers left',
  two_right: 'Two fingers right',
  peace: 'Peace sign',
  unknown: 'Unknown pose',
};

const ACTION_LABELS: Record<string, string> = {
  idle: 'Waiting',
  no_hand: 'Stopped: no hand',
  stop: 'Stopped',
  confirming: 'Recognising...',
  forward: 'Driving forward',
  backward: 'Driving backward',
  turn_left: 'Turning left',
  turn_right: 'Turning right',
  strafe_left: 'Sliding left',
  strafe_right: 'Sliding right',
  hold_for_follow: 'Keep holding for follow mode...',
  follow: 'Follow mode on',
  locking_distance: 'Locking your distance...',
  following: 'Following your hand',
  holding: 'Holding position',
};

const tone = (action: string | null) =>
  !action || ['idle', 'no_hand', 'stop'].includes(action)
    ? colors.textDim
    : ['confirming', 'hold_for_follow', 'locking_distance'].includes(action)
      ? colors.warn
      : colors.good;

export function GesturePanel({
  status,
  onStop,
  onHelp,
}: {
  status: GestureStatus;
  onStop: () => void;
  onHelp: () => void;
}) {
  const follow = status.mode === 'follow';
  return (
    <View style={[styles.panel, follow && { borderColor: colors.accent }]}>
      <View style={styles.header}>
        <Ionicons name={follow ? 'walk' : 'hand-left'} size={18} color={follow ? colors.accent : colors.text} />
        <Text style={styles.title}>{follow ? 'Follow me' : 'Gesture control'}</Text>
        <Pressable onPress={onHelp} hitSlop={10} accessibilityLabel="Gesture help">
          <Ionicons name="help-circle-outline" size={20} color={colors.textDim} />
        </Pressable>
      </View>
      {status.error ? (
        <Text style={[styles.action, { color: colors.danger }]}>{status.error}</Text>
      ) : !status.ready ? (
        <Text style={[styles.action, { color: colors.warn }]}>Starting hand tracking...</Text>
      ) : (
        <>
          <Text style={[styles.action, { color: tone(status.action) }]}>
            {ACTION_LABELS[status.action ?? 'idle'] ?? status.action}
          </Text>
          <Text style={styles.sub}>
            {GESTURE_LABELS[status.gesture ?? 'none'] ?? status.gesture}
            {status.fps ? `  ·  ${status.fps.toFixed(0)} fps` : ''}
          </Text>
        </>
      )}
      <Pressable onPress={onStop} style={({ pressed }) => [styles.stop, pressed && { opacity: 0.7 }]}>
        <Text style={styles.stopText}>Use joysticks</Text>
      </Pressable>
    </View>
  );
}

const HELP: { pose: string; does: string }[] = [
  { pose: 'Open palm or fist', does: 'Stop (instant)' },
  { pose: 'Thumbs up', does: 'Drive forward' },
  { pose: 'Thumbs down', does: 'Drive backward' },
  { pose: 'Point one finger left / right', does: 'Turn that way' },
  { pose: 'Two fingers left / right', does: 'Slide sideways that way' },
  { pose: 'Peace sign, hold 1 s', does: 'Start Follow me' },
  { pose: 'Follow me: show your hand', does: 'Robot keeps it centred and keeps its distance' },
  { pose: 'Follow me: fist, hold 1 s', does: 'Back to gesture commands' },
  { pose: 'Hand leaves the view', does: 'Robot stops' },
];

export function GestureHelp({ visible, onClose }: { visible: boolean; onClose: () => void }) {
  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onClose}>
      <Pressable style={styles.backdrop} onPress={onClose}>
        <View style={styles.card}>
          <Text style={styles.cardTitle}>Hand gestures</Text>
          <Text style={styles.cardLead}>
            Stand 1 to 2 m in front of the robot and hold your hand up so the camera sees it. Left and right mean the
            way you point, and the robot goes that way.
          </Text>
          <FlatList
            data={HELP}
            keyExtractor={(h) => h.pose}
            renderItem={({ item }) => (
              <View style={styles.helpRow}>
                <Text style={styles.helpPose}>{item.pose}</Text>
                <Text style={styles.helpDoes}>{item.does}</Text>
              </View>
            )}
          />
        </View>
      </Pressable>
    </Modal>
  );
}

const styles = StyleSheet.create({
  panel: {
    backgroundColor: colors.overlay,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radius.lg,
    padding: 12,
    gap: 4,
    minWidth: 230,
    maxWidth: 320,
    alignSelf: 'center',
  },
  header: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  title: { color: colors.text, fontWeight: '700', fontSize: 14, flex: 1 },
  action: { fontSize: 17, fontWeight: '700', marginTop: 2 },
  sub: { color: colors.textDim, fontSize: 12 },
  stop: {
    marginTop: 8,
    alignSelf: 'flex-start',
    backgroundColor: colors.surfaceHi,
    paddingHorizontal: 12,
    paddingVertical: 7,
    borderRadius: radius.pill,
  },
  stopText: { color: colors.text, fontSize: 13, fontWeight: '600' },
  backdrop: { flex: 1, backgroundColor: 'rgba(0,0,0,0.6)', alignItems: 'center', justifyContent: 'center', padding: 24 },
  card: { backgroundColor: colors.surface, borderRadius: radius.lg, padding: 18, width: '100%', maxWidth: 460, maxHeight: '85%' },
  cardTitle: { color: colors.text, fontSize: 17, fontWeight: '700' },
  cardLead: { color: colors.textDim, fontSize: 13, lineHeight: 18, marginTop: 6, marginBottom: 8 },
  helpRow: { paddingVertical: 9, borderBottomColor: colors.border, borderBottomWidth: StyleSheet.hairlineWidth },
  helpPose: { color: colors.text, fontSize: 14, fontWeight: '600' },
  helpDoes: { color: colors.textDim, fontSize: 13, marginTop: 2 },
});
