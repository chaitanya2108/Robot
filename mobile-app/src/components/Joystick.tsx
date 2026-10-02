import React, { useMemo, useState } from 'react';
import { Animated, StyleSheet, Text, View } from 'react-native';
import { Gesture, GestureDetector } from 'react-native-gesture-handler';

import type { Stick } from '../lib/driveMath';
import { colors } from '../lib/theme';

/** onChange / onActiveChange should be stable (useCallback) to avoid rebuilding the gesture. */
type Props = {
  size?: number;
  /** Lock the stick to one axis. */
  axis?: 'both' | 'x' | 'y';
  label?: string;
  onChange: (s: Stick) => void;
  onActiveChange?: (active: boolean) => void;
  disabled?: boolean;
};

/**
 * Virtual thumbstick. Each Joystick owns its own gesture, so two can be used
 * at the same time (multi-touch). Output: x right, y up, both -1..1.
 */
export function Joystick({ size = 170, axis = 'both', label, onChange, onActiveChange, disabled }: Props) {
  const radius = size / 2;
  const knob = size * 0.38;
  const travel = radius - knob / 2;
  const [pos] = useState(() => new Animated.ValueXY({ x: 0, y: 0 }));

  const gesture = useMemo(() => {
    const update = (px: number, py: number) => {
      let dx = axis === 'y' ? 0 : px - radius;
      let dy = axis === 'x' ? 0 : py - radius;
      const dist = Math.hypot(dx, dy);
      if (dist > travel) {
        dx = (dx / dist) * travel;
        dy = (dy / dist) * travel;
      }
      pos.setValue({ x: dx, y: dy });
      onChange({ x: dx / travel, y: -dy / travel });
    };
    const reset = () => {
      Animated.spring(pos, { toValue: { x: 0, y: 0 }, useNativeDriver: true, speed: 40, bounciness: 0 }).start();
      onChange({ x: 0, y: 0 });
      onActiveChange?.(false);
    };
    return Gesture.Pan()
      .enabled(!disabled)
      .runOnJS(true)
      .minDistance(0)
      .shouldCancelWhenOutside(false)
      .onBegin((e) => {
        onActiveChange?.(true);
        update(e.x, e.y);
      })
      .onUpdate((e) => update(e.x, e.y))
      .onFinalize(reset);
  }, [axis, radius, travel, disabled, pos, onChange, onActiveChange]);

  return (
    <View style={{ alignItems: 'center' }}>
      <GestureDetector gesture={gesture}>
        <View
          style={[
            styles.base,
            { width: size, height: size, borderRadius: radius, opacity: disabled ? 0.35 : 1 },
            axis === 'x' && { height: knob + 24, borderRadius: (knob + 24) / 2, marginVertical: (size - knob - 24) / 2 },
          ]}
          collapsable={false}
        >
          <View style={[styles.cross, { width: axis === 'y' ? 2 : size * 0.7, height: 2 }]} />
          {axis !== 'x' && <View style={[styles.cross, { width: 2, height: size * 0.7 }]} />}
          <Animated.View
            pointerEvents="none"
            style={[
              styles.knob,
              { width: knob, height: knob, borderRadius: knob / 2, transform: pos.getTranslateTransform() },
            ]}
          />
        </View>
      </GestureDetector>
      {label ? <Text style={styles.label}>{label}</Text> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  base: {
    backgroundColor: 'rgba(20,26,34,0.55)',
    borderWidth: 2,
    borderColor: 'rgba(138,151,168,0.35)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  cross: { position: 'absolute', backgroundColor: 'rgba(138,151,168,0.18)' },
  knob: {
    backgroundColor: colors.accent,
    borderWidth: 3,
    borderColor: 'rgba(255,255,255,0.85)',
    shadowColor: '#000',
    shadowOpacity: 0.4,
    shadowRadius: 6,
    elevation: 6,
  },
  label: { color: colors.textDim, fontSize: 12, marginTop: 6, letterSpacing: 0.5 },
});
