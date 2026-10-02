import { router } from 'expo-router';
import React, { useState } from 'react';
import { KeyboardAvoidingView, Platform, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { Button, Field } from '../components/ui';
import { testConnection } from '../lib/api';
import { useRobot } from '../lib/RobotProvider';
import { colors, radius } from '../lib/theme';

export default function Connect() {
  const { robot, setRobot } = useRobot();
  const insets = useSafeAreaInsets();
  const [host, setHost] = useState(robot?.host ?? '192.168.1.105');
  const [port, setPort] = useState(String(robot?.port ?? 8765));
  const [token, setToken] = useState(robot?.token ?? '');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    const cfg = { host: host.trim(), port: Number(port) || 8765, token: token.trim() };
    if (!cfg.host || !cfg.token) {
      setError('Enter the robot address and access token.');
      return;
    }
    setBusy(true);
    setError(null);
    const res = await testConnection(cfg);
    setBusy(false);
    if (!res.ok) {
      setError(res.message);
      return;
    }
    await setRobot(cfg);
    router.replace('/drive');
  };

  return (
    <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <ScrollView
        contentContainerStyle={[styles.container, { paddingBottom: insets.bottom + 24 }]}
        keyboardShouldPersistTaps="handled"
      >
        <Text style={styles.lead}>
          Your phone and the robot need to be on the same WiFi. The robot only accepts phones that have its access
          token.
        </Text>
        <Field label="Robot address" value={host} onChangeText={setHost} keyboardType="numbers-and-punctuation" placeholder="192.168.1.105" />
        <Field label="Port" value={port} onChangeText={setPort} keyboardType="number-pad" placeholder="8765" />
        <Field
          label="Access token"
          value={token}
          onChangeText={setToken}
          secureTextEntry
          placeholder="Paste the token"
          hint="Get it on your computer with:  ssh hiwonder@<robot-ip> 'cd ~/robot_app/server && python3 -m robot_server --show-token'"
        />
        {error ? (
          <View style={styles.error}>
            <Text style={styles.errorText}>{error}</Text>
          </View>
        ) : null}
        <Button title={busy ? 'Connecting...' : 'Connect'} icon="link" onPress={submit} disabled={busy} />
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: { padding: 20, gap: 18 },
  lead: { color: colors.textDim, fontSize: 14, lineHeight: 20 },
  error: { backgroundColor: 'rgba(239,68,68,0.12)', borderColor: colors.danger, borderWidth: 1, borderRadius: radius.md, padding: 12 },
  errorText: { color: '#FCA5A5', fontSize: 14 },
});
