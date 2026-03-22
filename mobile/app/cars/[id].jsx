import { useEffect, useState } from 'react';
import { View, Text, ScrollView, Alert, KeyboardAvoidingView, Platform, ActivityIndicator } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { carsApi } from '../../src/api/endpoints';
import { Input, Button, Card, Chip } from '../../src/components/UI';
import { COLORS, FONTS, SPACING, FUEL_CHOICES } from '../../src/constants/theme';

export default function EditCarScreen() {
  var { id } = useLocalSearchParams();
  var router = useRouter();
  var [form, setForm] = useState({ make: '', model: '', year: '', fuel: 'benzina', plate_number: '', vin: '' });
  var [errors, setErrors] = useState({});
  var [isLoading, setIsLoading] = useState(true);
  var [isSaving, setIsSaving] = useState(false);

  useEffect(function() {
    carsApi.list().then(function(res) {
      var cars = res.data.cars || [];
      var car = cars.find(function(c) { return String(c.id) === String(id); });
      if (car) setForm({ make: car.make || '', model: car.model || '', year: car.year ? String(car.year) : '', fuel: car.fuel || 'benzina', plate_number: car.plate_number || '', vin: car.vin || '' });
      setIsLoading(false);
    }).catch(function() { setIsLoading(false); });
  }, [id]);

  function setField(k, v) { setForm(function(p) { return Object.assign({}, p, { [k]: v }); }); }

  function validate() {
    var e = {};
    if (!form.make.trim()) e.make = 'Obligatoriu';
    if (!form.model.trim()) e.model = 'Obligatoriu';
    if (!form.plate_number.trim()) e.plate_number = 'Obligatoriu';
    if (!form.vin.trim() || form.vin.trim().length !== 17) e.vin = 'VIN trebuie sa aiba exact 17 caractere';
    setErrors(e);
    return Object.keys(e).length === 0;
  }

  async function handleSave() {
    if (!validate()) return;
    setIsSaving(true);
    try {
      await carsApi.update(id, { make: form.make.trim(), model: form.model.trim(), year: form.year ? parseInt(form.year) : null, fuel: form.fuel, plate_number: form.plate_number.trim().toUpperCase(), vin: form.vin.trim().toUpperCase() });
      Alert.alert('Salvat!', 'Masina a fost actualizata.', [{ text: 'OK', onPress: function() { router.back(); } }]);
    } catch (err) {
      Alert.alert('Eroare', err.message || 'Nu s-a putut salva.');
    } finally { setIsSaving(false); }
  }

  if (isLoading) return <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: COLORS.bg }}><ActivityIndicator size="large" color={COLORS.primary} /></View>;

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: COLORS.bg }} edges={['bottom']}>
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : 'height'}>
        <ScrollView contentContainerStyle={{ padding: SPACING.md, gap: SPACING.md }} keyboardShouldPersistTaps="handled">
          <Card style={{ gap: SPACING.sm }}>
            <Text style={{ fontSize: FONTS.md, fontWeight: '700', color: COLORS.textSecondary, textTransform: 'uppercase', letterSpacing: 0.8 }}>Editeaza Masina</Text>
            <View style={{ flexDirection: 'row', gap: SPACING.sm }}>
              <View style={{ flex: 1 }}><Input label="Marca" value={form.make} onChangeText={function(v) { setField('make', v); }} autoCapitalize="words" error={errors.make} /></View>
              <View style={{ flex: 1 }}><Input label="Model" value={form.model} onChangeText={function(v) { setField('model', v); }} autoCapitalize="words" error={errors.model} /></View>
            </View>
            <Input label="An fabricatie" value={form.year} onChangeText={function(v) { setField('year', v); }} keyboardType="numeric" />
            <Text style={{ fontSize: 10, fontWeight: '700', color: COLORS.textSecondary, textTransform: 'uppercase', letterSpacing: 0.8 }}>Combustibil</Text>
            <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
              {FUEL_CHOICES.map(function(f) { return <Chip key={f.value} label={f.label} active={form.fuel === f.value} onPress={function() { setField('fuel', f.value); }} />; })}
            </View>
            <Input label="Nr. Inmatriculare" value={form.plate_number} onChangeText={function(v) { setField('plate_number', v.toUpperCase()); }} autoCapitalize="characters" error={errors.plate_number} />
            <Input label="VIN (17 caractere)" value={form.vin} onChangeText={function(v) { setField('vin', v.toUpperCase()); }} autoCapitalize="characters" error={errors.vin} />
          </Card>
          <Button label="Salveaza Modificarile" onPress={handleSave} loading={isSaving} size="lg" icon="save" />
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}
