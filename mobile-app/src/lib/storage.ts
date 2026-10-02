import AsyncStorage from '@react-native-async-storage/async-storage';
import * as SecureStore from 'expo-secure-store';
import { Platform } from 'react-native';

import { DEFAULT_SETTINGS, type RobotConfig, type Settings } from './types';

const ROBOT_KEY = 'robot.config.v1';
const TOKEN_KEY = 'robot.token.v1';
const SETTINGS_KEY = 'app.settings.v1';

// The token lives in the OS keychain/keystore; everything else in AsyncStorage.
const secure = {
  get: (k: string) => (Platform.OS === 'web' ? AsyncStorage.getItem(k) : SecureStore.getItemAsync(k)),
  set: (k: string, v: string) => (Platform.OS === 'web' ? AsyncStorage.setItem(k, v) : SecureStore.setItemAsync(k, v)),
  del: (k: string) => (Platform.OS === 'web' ? AsyncStorage.removeItem(k) : SecureStore.deleteItemAsync(k)),
};

export async function loadRobot(): Promise<RobotConfig | null> {
  const raw = await AsyncStorage.getItem(ROBOT_KEY);
  const token = await secure.get(TOKEN_KEY);
  if (!raw || !token) return null;
  try {
    const { host, port } = JSON.parse(raw) as { host: string; port: number };
    return { host, port, token };
  } catch {
    return null;
  }
}

export async function saveRobot(c: RobotConfig) {
  await AsyncStorage.setItem(ROBOT_KEY, JSON.stringify({ host: c.host.trim(), port: c.port }));
  await secure.set(TOKEN_KEY, c.token.trim());
}

export async function forgetRobot() {
  await AsyncStorage.removeItem(ROBOT_KEY);
  await secure.del(TOKEN_KEY);
}

export async function loadSettings(): Promise<Settings> {
  try {
    const raw = await AsyncStorage.getItem(SETTINGS_KEY);
    return raw ? { ...DEFAULT_SETTINGS, ...(JSON.parse(raw) as Partial<Settings>) } : DEFAULT_SETTINGS;
  } catch {
    return DEFAULT_SETTINGS;
  }
}

export async function saveSettings(s: Settings) {
  await AsyncStorage.setItem(SETTINGS_KEY, JSON.stringify(s));
}
