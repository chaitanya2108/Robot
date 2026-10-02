import React, { createContext, useCallback, useContext, useEffect, useMemo, useState, useSyncExternalStore } from 'react';

import { RobotClient, type RobotState } from './robotClient';
import { forgetRobot, loadRobot, loadSettings, saveRobot, saveSettings } from './storage';
import { DEFAULT_SETTINGS, type RobotConfig, type Settings } from './types';

type Ctx = {
  ready: boolean;
  robot: RobotConfig | null;
  client: RobotClient | null;
  settings: Settings;
  setRobot: (c: RobotConfig) => Promise<void>;
  clearRobot: () => Promise<void>;
  updateSettings: (patch: Partial<Settings>) => void;
};

const RobotContext = createContext<Ctx | null>(null);

export function RobotProvider({ children }: { children: React.ReactNode }) {
  const [ready, setReady] = useState(false);
  const [robot, setRobotState] = useState<RobotConfig | null>(null);
  const [settings, setSettings] = useState<Settings>(DEFAULT_SETTINGS);

  useEffect(() => {
    Promise.all([loadRobot(), loadSettings()]).then(([r, s]) => {
      setRobotState(r);
      setSettings(s);
      setReady(true);
    });
  }, []);

  // One client per saved robot config
  const client = useMemo(() => (robot ? new RobotClient(robot) : null), [robot]);
  useEffect(() => () => client?.disconnect(), [client]);

  const setRobot = useCallback(async (c: RobotConfig) => {
    await saveRobot(c);
    setRobotState({ ...c, host: c.host.trim(), token: c.token.trim() });
  }, []);

  const clearRobot = useCallback(async () => {
    await forgetRobot();
    setRobotState(null);
  }, []);

  const updateSettings = useCallback((patch: Partial<Settings>) => {
    setSettings((prev) => {
      const next = { ...prev, ...patch };
      saveSettings(next);
      return next;
    });
  }, []);

  const value = useMemo(
    () => ({ ready, robot, client, settings, setRobot, clearRobot, updateSettings }),
    [ready, robot, client, settings, setRobot, clearRobot, updateSettings],
  );
  return <RobotContext.Provider value={value}>{children}</RobotContext.Provider>;
}

export function useRobot() {
  const ctx = useContext(RobotContext);
  if (!ctx) throw new Error('useRobot must be used inside RobotProvider');
  return ctx;
}

const EMPTY_STATE: RobotState = {
  status: 'idle',
  hello: null,
  telemetry: null,
  isDriver: false,
  estop: false,
  latencyMs: null,
  lastError: null,
};
const noopSubscribe = () => () => {};

/** Live connection state (re-renders on every telemetry update). */
export function useRobotState(): RobotState {
  const { client } = useRobot();
  return useSyncExternalStore(
    client ? client.subscribe : noopSubscribe,
    client ? client.getSnapshot : () => EMPTY_STATE,
  );
}
