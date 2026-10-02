import { Redirect } from 'expo-router';
import React from 'react';
import { ActivityIndicator, View } from 'react-native';

import { useRobot } from '../lib/RobotProvider';
import { colors } from '../lib/theme';

export default function Index() {
  const { ready, robot } = useRobot();
  if (!ready) {
    return (
      <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.bg }}>
        <ActivityIndicator color={colors.accent} />
      </View>
    );
  }
  return <Redirect href={robot ? '/drive' : '/connect'} />;
}
