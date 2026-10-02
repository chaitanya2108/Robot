import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import React, { useEffect } from 'react';
import { AppState } from 'react-native';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import { RobotProvider, useRobot } from '../lib/RobotProvider';
import { colors } from '../lib/theme';

/** Keeps the robot connection open while the app is in the foreground. */
function ConnectionManager() {
  const { client } = useRobot();
  useEffect(() => {
    if (!client) return;
    if (AppState.currentState === 'active') client.connect();
    const sub = AppState.addEventListener('change', (s) => {
      if (s === 'active') client.connect();
      else client.disconnect(); // backgrounded: robot stops via its watchdog too
    });
    return () => sub.remove();
  }, [client]);
  return null;
}

export default function RootLayout() {
  return (
    <GestureHandlerRootView style={{ flex: 1, backgroundColor: colors.bg }}>
      <SafeAreaProvider>
        <RobotProvider>
          <ConnectionManager />
          <StatusBar style="light" />
          <Stack
            screenOptions={{
              headerStyle: { backgroundColor: colors.bg },
              headerTintColor: colors.text,
              headerTitleStyle: { fontWeight: '600' },
              contentStyle: { backgroundColor: colors.bg },
            }}
          >
            <Stack.Screen name="index" options={{ headerShown: false }} />
            <Stack.Screen name="connect" options={{ title: 'Connect to robot' }} />
            <Stack.Screen name="drive" options={{ headerShown: false, gestureEnabled: false }} />
            <Stack.Screen name="settings" options={{ title: 'Settings' }} />
          </Stack>
        </RobotProvider>
      </SafeAreaProvider>
    </GestureHandlerRootView>
  );
}
