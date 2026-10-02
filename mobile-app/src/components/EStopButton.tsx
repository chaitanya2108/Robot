import * as Haptics from 'expo-haptics';
import React from 'react';
import { Pressable, StyleSheet, Text } from 'react-native';

import { colors } from '../lib/theme';

type Props = { engaged: boolean; onChange: (on: boolean) => void; haptics: boolean; compact?: boolean };

/** Tap to stop everything. Releasing requires a long press so it can't happen by accident. */
export function EStopButton({ engaged, onChange, haptics, compact }: Props) {
  const size = compact ? 64 : 78;
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={engaged ? 'Emergency stop engaged. Long press to release.' : 'Emergency stop'}
      onPress={() => {
        if (!engaged) {
          if (haptics) Haptics.notificationAsync(Haptics.NotificationFeedbackType.Warning);
          onChange(true);
        }
      }}
      onLongPress={() => {
        if (engaged) {
          if (haptics) Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
          onChange(false);
        }
      }}
      delayLongPress={900}
      style={({ pressed }) => [
        styles.btn,
        { width: size, height: size, borderRadius: size / 2 },
        engaged && styles.engaged,
        pressed && { transform: [{ scale: 0.94 }] },
      ]}
    >
      <Text style={styles.big}>STOP</Text>
      <Text style={styles.small}>{engaged ? 'hold to release' : 'emergency'}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  btn: {
    backgroundColor: colors.danger,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 3,
    borderColor: 'rgba(255,255,255,0.85)',
    elevation: 8,
    shadowColor: '#000',
    shadowOpacity: 0.5,
    shadowRadius: 8,
  },
  engaged: { backgroundColor: colors.dangerDim, borderColor: colors.warn },
  big: { color: '#fff', fontWeight: '800', fontSize: 16, letterSpacing: 1 },
  small: { color: 'rgba(255,255,255,0.8)', fontSize: 8, marginTop: 1 },
});
