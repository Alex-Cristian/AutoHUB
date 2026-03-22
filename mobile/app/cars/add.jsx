import { useState } from 'react';
import { View, Text, ScrollView, Alert, KeyboardAvoidingView, Platform } from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { carsApi } from '../../src/api/endpoints';
import { Input, Button, Card } from '../../src/components/UI';
import { COLORS, FONTS, SPACING, FUEL_CHOICES } from '../../src/constants/theme';
import { Chip } from '../../src/components/UI';

export default function AddCarScreen() {
  var router = useRouter();
  var [form, setForm] = useState({ make: '', model: '', year: '', fuel: 'benzina', plate_number: '', vin: '' });
  var [errors, setErrors] = useState({});
  var [isLoading, setIsLoading] = useState(false);

  function setField(k, v) { setForm(function(p) { return Object.assign({}, p, { [k]: v }); }); setErrors(function(p) { var n = Object.assign({}, p); delete n[k]; return n; }); }

  function validate() {
    var e = {};
    if (!form.make.trim()) e.make = 'Obligatoriu';
    if (!form.model.trim()) e.model = 'Obligatoriu';
    if (!form.plate_number.trim()) e.plate_number = 'Obligatoriu';
    if (!form.vin.trim() || form.vin.trim().length !== 17) e.vin = 'VIN trebuie sa aiba exact 17 caractere';
    if (form.year && (isNaN(parseInt(form.year)) || parseInt(form.year) < 1950 || parseInt(form.year) > new Date().getFullYear() + 1)) e.year = 'An invalid';
    setErrors(e);
    return Object.keys(e).length === 0;
  }

  async function handleSave() {
    if (!validate()) return;
    setIsLoading(true);
    try {
      await carsApi.create({
        make: form.make.trim(),
        model: form.model.trim(),
        year: form.year ? parseInt(form.year) : null,
        fuel: form.fuel,
        plate_number: form.plate_number.trim().toUpperCase(),
        vin: form.vin.trim().toUpperCase(),
      });
      Alert.alert('Succes!', 'Masina a fost adaugata.', [{ text: 'OK', onPress: function() { router.back(); } }]);
    } catch (err) {
      Alert.alert('Eroare', err.message || 'Nu s-a putut adauga masina.');
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: COLORS.bg }} edges={['bottom']}>
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : 'height'}>
        <ScrollView contentContainerStyle={{ padding: SPACING.md, gap: SPACING.md }} keyboardShouldPersistTaps="handled">
          <Card style={{ gap: SPACING.sm }}>
            <Text style={{ fontSize: FONTS.md, fontWeight: '700', color: COLORS.textSecondary, textTransform: 'uppercase', letterSpacing: 0.8 }}>Date Masina</Text>
            <View style={{ flexDirection: 'row', gap: SPACING.sm }}>
              <View style={{ flex: 1 }}><Input label="Marca" placeholder="Dacia" value={form.make} onChangeText={function(v) { setField('make', v); }} autoCapitalize="words" error={errors.make} /></View>
              <View style={{ flex: 1 }}><Input label="Model" placeholder="Logan" value={form.model} onChangeText={function(v) { setField('model', v); }} autoCapitalize="words" error={errors.model} /></View>
            </View>
            <View style={{ flexDirection: 'row', gap: SPACING.sm }}>
              <View style={{ flex: 1 }}><Input label="An fabricatie" placeholder="2020" value={form.year} onChangeText={function(v) { setField('year', v); }} keyboardType="numeric" error={errors.year} /></View>
            </View>
            <Text style={{ fontSize: 10, fontWeight: '700', color: COLORS.textSecondary, textTransform: 'uppercase', letterSpacing: 0.8 }}>Combustibil</Text>
            <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
              {FUEL_CHOICES.map(function(f) { return <Chip key={f.value} label={f.label} active={form.fuel === f.value} onPress={function() { setField('fuel', f.value); }} />; })}
            </View>
            <Input label="Nr. Inmatriculare" placeholder="B 123 XYZ" value={form.plate_number} onChangeText={function(v) { setField('plate_number', v.toUpperCase()); }} autoCapitalize="characters" error={errors.plate_number} />
            <Input label="Serie Sasiu VIN (17 caractere)" placeholder="WVW..." value={form.vin} onChangeText={function(v) { setField('vin', v.toUpperCase()); }} autoCapitalize="characters" error={errors.vin} />
            <Text style={{ fontSize: 11, color: COLORS.textMuted }}>VIN se gaseste pe cartea de identitate a vehiculului sau pe bord (coltul din stanga jos al parbrizului)</Text>
          </Card>
          <Button label="Salveaza Masina" onPress={handleSave} loading={isLoading} size="lg" icon="save" />
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}
