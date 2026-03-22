import { useEffect } from 'react';
import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { useAuthStore } from '../src/store/authStore';
import { COLORS } from '../src/constants/theme';

export default function RootLayout() {
  var hydrate = useAuthStore(function(s) { return s.hydrate; });
  useEffect(function() { hydrate(); }, []);

  return (
    <SafeAreaProvider>
      <StatusBar style="light" backgroundColor={COLORS.bg} />
      <Stack screenOptions={{ headerStyle: { backgroundColor: COLORS.bgCard }, headerTintColor: COLORS.textPrimary, headerTitleStyle: { fontWeight: '700' }, contentStyle: { backgroundColor: COLORS.bg } }}>
        <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
        <Stack.Screen name="service/[slug]" options={{ title: 'Detalii Service' }} />
        <Stack.Screen name="booking/[slug]" options={{ title: 'Programare', presentation: 'modal' }} />
        <Stack.Screen name="auth/login" options={{ title: 'Autentificare', presentation: 'modal', headerStyle: { backgroundColor: COLORS.bg } }} />
        <Stack.Screen name="auth/register" options={{ title: 'Cont Nou', presentation: 'modal', headerStyle: { backgroundColor: COLORS.bg } }} />
        <Stack.Screen name="cars/add" options={{ title: 'Adauga Masina', presentation: 'modal' }} />
        <Stack.Screen name="cars/[id]" options={{ title: 'Editeaza Masina' }} />
        <Stack.Screen name="cars/expiry/[id]" options={{ title: 'Expirari Documente', presentation: 'modal' }} />
      </Stack>
    </SafeAreaProvider>
  );
}
