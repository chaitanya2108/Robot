import { Ionicons } from '@expo/vector-icons';
import React, { useEffect, useRef, useState } from 'react';
import { ActivityIndicator, StyleSheet, Text, View } from 'react-native';
import { WebView } from 'react-native-webview';

import { cameraStreamUrl } from '../lib/api';
import { colors } from '../lib/theme';
import type { RobotConfig } from '../lib/types';

type Props = { robot: RobotConfig; enabled: boolean; connected: boolean };

const page = (url: string) => `<!doctype html><html><head>
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<style>html,body{margin:0;height:100%;background:#000;overflow:hidden}
img{position:absolute;inset:0;width:100%;height:100%;object-fit:contain}</style></head>
<body><img id="v" src="${url}"
 onload="window.ReactNativeWebView.postMessage('load')"
 onerror="window.ReactNativeWebView.postMessage('error')"></body></html>`;

/**
 * Live MJPEG feed from the robot. React Native's <Image> can't play MJPEG, so
 * the stream is shown inside a tiny WebView. Touches pass through to the
 * joysticks on top.
 */
export function CameraView({ robot, enabled, connected }: Props) {
  const active = enabled && connected;
  const [url, setUrl] = useState<string | null>(null);
  const [live, setLive] = useState(false);
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const retryTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Fetch a fresh stream ticket whenever the camera becomes active or a retry is due.
  useEffect(() => {
    if (!active) return;
    let cancelled = false;
    cameraStreamUrl(robot)
      .then((u) => {
        if (cancelled) return;
        setUrl(u);
        setLive(false);
        setFailed(false);
      })
      .catch(() => {
        if (cancelled) return;
        setFailed(true);
        retryTimer.current = setTimeout(() => setAttempt((a) => a + 1), 3000);
      });
    return () => {
      cancelled = true;
      if (retryTimer.current) clearTimeout(retryTimer.current);
    };
  }, [active, robot, attempt]);

  const onMessage = (msg: string) => {
    if (msg === 'load') {
      setLive(true);
      setFailed(false);
    } else if (msg === 'error') {
      setLive(false);
      setFailed(true);
      if (retryTimer.current) clearTimeout(retryTimer.current);
      retryTimer.current = setTimeout(() => setAttempt((a) => a + 1), 2000);
    }
  };

  const status = !enabled ? 'off' : live && active ? 'live' : failed ? 'error' : 'loading';

  return (
    <View style={StyleSheet.absoluteFill} pointerEvents="none">
      {active && url ? (
        <WebView
          key={url}
          source={{ html: page(url), baseUrl: '' }}
          originWhitelist={['*']}
          javaScriptEnabled
          scrollEnabled={false}
          bounces={false}
          mixedContentMode="always"
          style={styles.web}
          containerStyle={styles.web}
          onMessage={(e) => onMessage(e.nativeEvent.data)}
          onError={() => onMessage('error')}
        />
      ) : null}
      {status !== 'live' && (
        <View style={styles.center}>
          {status === 'loading' && <ActivityIndicator color={colors.textDim} />}
          {status !== 'loading' && <Ionicons name="videocam-off-outline" size={28} color={colors.textDim} />}
          {status === 'error' && <Text style={styles.note}>Camera unavailable, retrying...</Text>}
          {status === 'off' && <Text style={styles.note}>Camera off</Text>}
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  web: { flex: 1, backgroundColor: '#000' },
  center: { ...StyleSheet.absoluteFill, alignItems: 'center', justifyContent: 'center', gap: 8 },
  note: { color: colors.textDim, fontSize: 13 },
});
