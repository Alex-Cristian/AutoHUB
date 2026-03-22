import { useState } from 'react';
import { View, Text, ScrollView, TouchableOpacity, KeyboardAvoidingView, Platform } from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useAuthStore } from '../../src/store/authStore';
import { Input, Button } from '../../src/components/UI';
import { COLORS, FONTS, RADIUS, SPACING } from '../../src/constants/theme';

export default function RegisterScreen() {
  var router = useRouter();
  var { register, isLoading, error, clearError } = useAuthStore();
  var [form, setForm] = useState({ username: '', email: '', password: '', first_name: '', last_name: '' });
  var [errors, setErrors] = useState({});

  function setField(k, v) { setForm(function(p) { return Object.assign({}, p, { [k]: v }); }); }

  function validate() {
    var e = {};
    if (!form.username.trim() || form.username.length < 3) e.username = 'Minim 3 caractere';
    if (!form.email.includes('@')) e.email = 'Email invalid';
    if (form.password.length < 6) e.password = 'Minim 6 caractere';
    if (!form.first_name.trim()) e.first_name = 'Obligatoriu';
    setErrors(e);
    return Object.keys(e).length === 0;
  }

  async function handleRegister() {
    if (!validate()) return;
    clearError();
    var result = await register(form);
    if (result.success) router.back();
  }

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: COLORS.bg }} edges={['bottom']}>
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : 'height'}>
        <ScrollView contentContainerStyle={{ flexGrow: 1, padding: SPACING.lg, gap: SPACING.md }} keyboardShouldPersistTaps="handled">
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: SPACING.sm }}>
            <View style={{ width: 10, height: 10, borderRadius: 5, backgroundColor: COLORS.primary }} />
            <Text style={{ fontSize: FONTS.xxl, fontWeight: '900', color: COLORS.primary, letterSpacing: 2 }}>AutoEMG</Text>
          </View>
          <Text style={{ fontSize: FONTS.xxxl, fontWeight: '800', color: COLORS.textPrimary }}>Cont Nou</Text>
          <Text style={{ fontSize: FONTS.md, color: COLORS.textSecondary, marginTop: -8 }}>Creeaza-ti contul gratuit</Text>

          {error && (
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: 'rgba(239,68,68,0.12)', padding: SPACING.md, borderRadius: RADIUS.md, borderWidth: 1, borderColor: 'rgba(239,68,68,0.3)' }}>
              <Ionicons name="alert-circle" size={16} color={COLORS.error} />
              <Text style={{ flex: 1, fontSize: FONTS.sm, color: COLORS.error }}>{error}</Text>
            </View>
          )}

          <View style={{ flexDirection: 'row', gap: SPACING.sm }}>
            <View style={{ flex: 1 }}><Input label="Prenume" placeholder="Ion" value={form.first_name} onChangeText={function(v) { setField('first_name', v); }} autoCapitalize="words" error={errors.first_name} /></View>
            <View style={{ flex: 1 }}><Input label="Nume" placeholder="Popescu" value={form.last_name} onChangeText={function(v) { setField('last_name', v); }} autoCapitalize="words" /></View>
          </View>
          <Input label="Username" placeholder="username unic" value={form.username} onChangeText={function(v) { setField('username', v); }} icon="person-outline" error={errors.username} />
          <Input label="Email" placeholder="email@exemplu.ro" value={form.email} onChangeText={function(v) { setField('email', v); }} icon="mail-outline" keyboardType="email-address" error={errors.email} />
          <Input label="Parola" placeholder="minim 6 caractere" value={form.password} onChangeText={function(v) { setField('password', v); }} icon="lock-closed-outline" secureTextEntry error={errors.password} />

          <Button label="Creeaza Contul" onPress={handleRegister} loading={isLoading} size="lg" icon="person-add" style={{ marginTop: SPACING.sm }} />

          <TouchableOpacity style={{ alignItems: 'center', paddingVertical: SPACING.sm }} onPress={function() { router.push('/auth/login'); }}>
            <Text style={{ fontSize: FONTS.md, color: COLORS.textSecondary }}>
              Ai deja cont? <Text style={{ color: COLORS.primary, fontWeight: '700' }}>Autentifica-te</Text>
            </Text>
          </TouchableOpacity>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}
