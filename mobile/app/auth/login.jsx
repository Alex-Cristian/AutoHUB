import { useState } from 'react';
import { View, Text, ScrollView, TouchableOpacity, StyleSheet, KeyboardAvoidingView, Platform } from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useAuthStore } from '../../src/store/authStore';
import { Input, Button } from '../../src/components/UI';
import { COLORS, FONTS, RADIUS, SPACING } from '../../src/constants/theme';

export default function LoginScreen() {
  var router = useRouter();
  var { login, isLoading, error, clearError } = useAuthStore();
  var [username, setUsername] = useState('');
  var [password, setPassword] = useState('');

  async function handleLogin() {
    if (!username.trim() || !password.trim()) return;
    clearError();
    var result = await login(username.trim(), password);
    if (result.success) router.back();
  }

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: COLORS.bg }} edges={['bottom']}>
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : 'height'}>
        <ScrollView contentContainerStyle={{ flexGrow: 1, padding: SPACING.lg, justifyContent: 'center', gap: SPACING.md }} keyboardShouldPersistTaps="handled">

          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: SPACING.sm }}>
            <View style={{ width: 10, height: 10, borderRadius: 5, backgroundColor: COLORS.primary }} />
            <Text style={{ fontSize: FONTS.xxl, fontWeight: '900', color: COLORS.primary, letterSpacing: 2 }}>AutoEMG</Text>
          </View>

          <Text style={{ fontSize: FONTS.xxxl, fontWeight: '800', color: COLORS.textPrimary }}>Bun venit inapoi</Text>
          <Text style={{ fontSize: FONTS.md, color: COLORS.textSecondary, marginTop: -8 }}>Autentifica-te in contul tau</Text>

          {error && (
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: 'rgba(239,68,68,0.12)', padding: SPACING.md, borderRadius: RADIUS.md, borderWidth: 1, borderColor: 'rgba(239,68,68,0.3)' }}>
              <Ionicons name="alert-circle" size={16} color={COLORS.error} />
              <Text style={{ flex: 1, fontSize: FONTS.sm, color: COLORS.error }}>{error}</Text>
            </View>
          )}

          <Input label="Utilizator" placeholder="username" value={username} onChangeText={setUsername} icon="person-outline" />
          <Input label="Parola" placeholder="parola ta" value={password} onChangeText={setPassword} icon="lock-closed-outline" secureTextEntry />

          <Button label="Autentifica-te" onPress={handleLogin} loading={isLoading} disabled={!username.trim() || !password.trim()} size="lg" icon="log-in" style={{ marginTop: SPACING.sm }} />

          <TouchableOpacity style={{ alignItems: 'center', paddingVertical: SPACING.sm }} onPress={function() { router.push('/auth/register'); }}>
            <Text style={{ fontSize: FONTS.md, color: COLORS.textSecondary }}>
              Nu ai cont? <Text style={{ color: COLORS.primary, fontWeight: '700' }}>Inregistreaza-te</Text>
            </Text>
          </TouchableOpacity>

          <TouchableOpacity style={{ alignItems: 'center' }} onPress={function() { router.back(); }}>
            <Text style={{ fontSize: FONTS.md, color: COLORS.textMuted }}>Anuleaza</Text>
          </TouchableOpacity>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}
