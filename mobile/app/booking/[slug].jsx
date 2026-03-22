import { useEffect, useState } from 'react';
import { View, Text, ScrollView, TouchableOpacity, StyleSheet, Alert, ActivityIndicator } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { servicesApi, bookingsApi, carsApi } from '../../src/api/endpoints';
import { useAuthStore } from '../../src/store/authStore';
import { Input, Button, Card, Chip } from '../../src/components/UI';
import { COLORS, FONTS, RADIUS, SPACING, FUEL_CHOICES } from '../../src/constants/theme';
import { BASE_URL } from '../../src/api/client';

var TODAY = new Date().toISOString().slice(0, 10);

function Section({ title, children }) {
  return (
    <Card style={{ gap: SPACING.sm, marginBottom: SPACING.md }}>
      <Text style={{ fontSize: FONTS.md, fontWeight: '700', color: COLORS.textSecondary, textTransform: 'uppercase', letterSpacing: 0.8 }}>{title}</Text>
      {children}
    </Card>
  );
}

export default function BookingScreen() {
  var { slug } = useLocalSearchParams();
  var router = useRouter();
  var { user, isLoggedIn } = useAuthStore();

  var [service, setService] = useState(null);
  var [cars, setCars] = useState([]);
  var [selectedCar, setSelectedCar] = useState(null);
  var [selectedGarage, setSelectedGarage] = useState(null);
  var [isLoading, setIsLoading] = useState(true);
  var [isSubmitting, setIsSubmitting] = useState(false);

  var [form, setForm] = useState({
    client_name: (user ? (user.first_name + ' ' + user.last_name).trim() : '') || '',
    client_phone: '',
    client_email: user ? user.email : '',
    car_brand: '', car_model: '', car_year: '', car_fuel: 'benzina',
    car_plate: '', car_vin: '',
    problem_description: '',
    booking_date: TODAY,
    booking_time: '09:00',
    wants_offer: false,
  });
  var [errors, setErrors] = useState({});

  function setField(k, v) { setForm(function(p) { return Object.assign({}, p, { [k]: v }); }); setErrors(function(p) { var n = Object.assign({}, p); delete n[k]; return n; }); }

  useEffect(function() {
    Promise.all([
      servicesApi.detail(slug),
      isLoggedIn ? carsApi.list() : Promise.resolve({ data: { cars: [] } }),
    ]).then(function(results) {
      setService(results[0].data);
      setCars(results[1].data.cars || []);
      setIsLoading(false);
    }).catch(function() { setIsLoading(false); });
  }, [slug]);

  function selectCar(car) {
    if (selectedCar && selectedCar.id === car.id) {
      setSelectedCar(null);
      setField('car_brand', ''); setField('car_model', ''); setField('car_year', '');
      setField('car_plate', ''); setField('car_vin', ''); setField('car_fuel', 'benzina');
    } else {
      setSelectedCar(car);
      setField('car_brand', car.make); setField('car_model', car.model);
      setField('car_year', car.year ? String(car.year) : '');
      setField('car_plate', car.plate_number); setField('car_vin', car.vin);
      setField('car_fuel', car.fuel || 'benzina');
    }
  }

  function validate() {
    var e = {};
    if (!form.client_name.trim()) e.client_name = 'Obligatoriu';
    if (!form.client_phone.trim()) e.client_phone = 'Obligatoriu';
    if (!form.client_email.trim()) e.client_email = 'Obligatoriu';
    if (!form.car_brand.trim()) e.car_brand = 'Obligatoriu';
    if (!form.car_model.trim()) e.car_model = 'Obligatoriu';
    if (!form.car_year || isNaN(parseInt(form.car_year))) e.car_year = 'An invalid';
    if (!form.car_plate.trim()) e.car_plate = 'Obligatoriu';
    if (!form.car_vin.trim() || form.car_vin.trim().length !== 17) e.car_vin = 'VIN trebuie sa aiba exact 17 caractere';
    if (!form.problem_description.trim()) e.problem_description = 'Descrie problema sau serviciul dorit';
    if (!form.booking_date || form.booking_date < TODAY) e.booking_date = 'Data nu poate fi in trecut';
    if (!form.booking_time) e.booking_time = 'Obligatoriu';
    setErrors(e);
    return Object.keys(e).length === 0;
  }

  async function handleSubmit() {
    if (!validate()) { Alert.alert('Date incomplete', 'Verifica campurile marcate cu rosu.'); return; }
    setIsSubmitting(true);
    try {
      var payload = {
        client_name: form.client_name.trim(),
        client_phone: form.client_phone.trim(),
        client_email: form.client_email.trim(),
        car_brand: form.car_brand.trim(),
        car_model: form.car_model.trim(),
        car_year: parseInt(form.car_year),
        car_fuel: form.car_fuel,
        car_plate: form.car_plate.trim().toUpperCase(),
        car_vin: form.car_vin.trim().toUpperCase(),
        problem_description: form.problem_description.trim(),
        booking_date: form.booking_date,
        booking_time: form.booking_time,
        wants_offer: form.wants_offer,
        garage_id: selectedGarage ? selectedGarage.id : undefined,
      };
      await bookingsApi.create ? bookingsApi.create(payload) : Promise.resolve();
      Alert.alert('Programare trimisa!', 'Vei fi contactat de service pentru confirmare.', [
        { text: 'OK', onPress: function() { router.push('/(tabs)/profile'); } }
      ]);
    } catch (err) {
      Alert.alert('Eroare', err.message || 'Nu s-a putut trimite programarea.');
    } finally {
      setIsSubmitting(false);
    }
  }

  if (isLoading) return <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: COLORS.bg }}><ActivityIndicator size="large" color={COLORS.primary} /></View>;

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: COLORS.bg }} edges={['bottom']}>
      <ScrollView contentContainerStyle={{ padding: SPACING.md }} showsVerticalScrollIndicator={false} keyboardShouldPersistTaps="handled">

        {/* Service info */}
        {service && (
          <View style={{ backgroundColor: COLORS.bgCard, borderRadius: RADIUS.md, padding: SPACING.md, marginBottom: SPACING.md, borderWidth: 1, borderColor: COLORS.border, flexDirection: 'row', alignItems: 'center', gap: SPACING.sm }}>
            <View style={{ width: 40, height: 40, borderRadius: RADIUS.sm, backgroundColor: 'rgba(230,48,48,0.12)', justifyContent: 'center', alignItems: 'center' }}>
              <Ionicons name="construct" size={20} color={COLORS.primary} />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={{ fontSize: FONTS.md, fontWeight: '700', color: COLORS.textPrimary }}>{service.name}</Text>
              <Text style={{ fontSize: FONTS.xs, color: COLORS.textSecondary }}>{service.city_display} · {service.price_range}</Text>
            </View>
          </View>
        )}

        {/* Masinile mele */}
        {isLoggedIn && cars.length > 0 && (
          <Section title="Selecteaza Masina Salvata">
            <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 8 }}>
              {cars.map(function(car) {
                var active = selectedCar && selectedCar.id === car.id;
                return (
                  <TouchableOpacity key={car.id} onPress={function() { selectCar(car); }}
                    style={{ paddingHorizontal: 12, paddingVertical: 8, borderRadius: RADIUS.md, backgroundColor: active ? COLORS.primary : COLORS.bgInput, borderWidth: 1, borderColor: active ? COLORS.primary : COLORS.border }}>
                    <Text style={{ fontSize: FONTS.sm, fontWeight: '700', color: active ? '#fff' : COLORS.textPrimary }}>{car.make} {car.model}</Text>
                    <Text style={{ fontSize: FONTS.xs, color: active ? 'rgba(255,255,255,0.8)' : COLORS.textMuted }}>{car.plate_number}</Text>
                  </TouchableOpacity>
                );
              })}
            </ScrollView>
          </Section>
        )}

        {/* Date client */}
        <Section title="Date Contact">
          <Input label="Nume Complet" placeholder="Ion Popescu" value={form.client_name} onChangeText={function(v) { setField('client_name', v); }} icon="person-outline" autoCapitalize="words" error={errors.client_name} />
          <Input label="Telefon" placeholder="07XX XXX XXX" value={form.client_phone} onChangeText={function(v) { setField('client_phone', v); }} icon="call-outline" keyboardType="phone-pad" error={errors.client_phone} />
          <Input label="Email" placeholder="email@exemplu.ro" value={form.client_email} onChangeText={function(v) { setField('client_email', v); }} icon="mail-outline" keyboardType="email-address" error={errors.client_email} />
        </Section>

        {/* Date masina */}
        <Section title="Date Masina">
          <View style={{ flexDirection: 'row', gap: SPACING.sm }}>
            <View style={{ flex: 1 }}><Input label="Marca" placeholder="Dacia" value={form.car_brand} onChangeText={function(v) { setField('car_brand', v); }} autoCapitalize="words" error={errors.car_brand} /></View>
            <View style={{ flex: 1 }}><Input label="Model" placeholder="Logan" value={form.car_model} onChangeText={function(v) { setField('car_model', v); }} autoCapitalize="words" error={errors.car_model} /></View>
          </View>
          <View style={{ flexDirection: 'row', gap: SPACING.sm }}>
            <View style={{ flex: 1 }}><Input label="An fabricatie" placeholder="2020" value={form.car_year} onChangeText={function(v) { setField('car_year', v); }} keyboardType="numeric" error={errors.car_year} /></View>
            <View style={{ flex: 1 }}>
              <Text style={{ fontSize: FONTS.xs, fontWeight: '700', color: COLORS.textSecondary, textTransform: 'uppercase', letterSpacing: 0.8, marginBottom: 4 }}>Combustibil</Text>
              <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 6 }}>
                {FUEL_CHOICES.map(function(f) { return <Chip key={f.value} label={f.label} active={form.car_fuel === f.value} onPress={function() { setField('car_fuel', f.value); }} />; })}
              </ScrollView>
            </View>
          </View>
          <Input label="Nr. Inmatriculare" placeholder="B 123 XYZ" value={form.car_plate} onChangeText={function(v) { setField('car_plate', v.toUpperCase()); }} autoCapitalize="characters" error={errors.car_plate} />
          <Input label="Serie Sasiu (VIN - 17 caractere)" placeholder="WVWZZZ1KZ..." value={form.car_vin} onChangeText={function(v) { setField('car_vin', v.toUpperCase()); }} autoCapitalize="characters" error={errors.car_vin} />
        </Section>

        {/* Problema */}
        <Section title="Descriere Problema / Serviciu">
          <Input label="Ce doresti sa repari sau sa verifici?" placeholder="Descrie problema sau serviciul dorit..." value={form.problem_description} onChangeText={function(v) { setField('problem_description', v); }} multiline numberOfLines={4} error={errors.problem_description} />
        </Section>

        {/* Data si ora */}
        <Section title="Data si Ora Programarii">
          <Input label="Data (YYYY-MM-DD)" placeholder={TODAY} value={form.booking_date} onChangeText={function(v) { setField('booking_date', v); }} keyboardType="numeric" error={errors.booking_date} />
          <Input label="Ora (HH:MM)" placeholder="09:00" value={form.booking_time} onChangeText={function(v) { setField('booking_time', v); }} keyboardType="numeric" error={errors.booking_time} />
        </Section>

        {/* Garaje */}
        {service && service.garages && service.garages.length > 0 && (
          <Section title="Alege Garaj (optional)">
            {service.garages.map(function(g) {
              var active = selectedGarage && selectedGarage.id === g.id;
              return (
                <TouchableOpacity key={g.id} onPress={function() { setSelectedGarage(active ? null : g); }}
                  style={{ flexDirection: 'row', alignItems: 'center', padding: SPACING.sm, borderRadius: RADIUS.md, backgroundColor: active ? 'rgba(230,48,48,0.12)' : COLORS.bgInput, borderWidth: 1, borderColor: active ? COLORS.primary : COLORS.border, gap: 10 }}>
                  <Ionicons name={active ? 'radio-button-on' : 'radio-button-off'} size={18} color={active ? COLORS.primary : COLORS.textMuted} />
                  <View style={{ flex: 1 }}>
                    <Text style={{ fontSize: FONTS.md, fontWeight: '600', color: COLORS.textPrimary }}>{g.name}</Text>
                    <Text style={{ fontSize: FONTS.xs, color: COLORS.textSecondary }}>{g.category} · {g.open_time}-{g.close_time} · slot {g.slot_minutes}min</Text>
                  </View>
                </TouchableOpacity>
              );
            })}
          </Section>
        )}

        {/* Optiuni */}
        <Section title="Optiuni">
          <TouchableOpacity
            style={{ flexDirection: 'row', alignItems: 'center', gap: 12, padding: SPACING.sm, borderRadius: RADIUS.md, backgroundColor: COLORS.bgInput, borderWidth: 1, borderColor: form.wants_offer ? COLORS.primary : COLORS.border }}
            onPress={function() { setField('wants_offer', !form.wants_offer); }}
          >
            <Ionicons name={form.wants_offer ? 'checkbox' : 'square-outline'} size={22} color={form.wants_offer ? COLORS.primary : COLORS.textMuted} />
            <View style={{ flex: 1 }}>
              <Text style={{ fontSize: FONTS.md, fontWeight: '600', color: COLORS.textPrimary }}>Doresc oferta inainte de confirmare</Text>
              <Text style={{ fontSize: FONTS.xs, color: COLORS.textSecondary }}>Service-ul va trimite o oferta de pret inainte sa confirme programarea</Text>
            </View>
          </TouchableOpacity>
        </Section>

        {/* Submit */}
        <Button label="Trimite Programarea" onPress={handleSubmit} loading={isSubmitting} size="lg" icon="calendar" style={{ marginBottom: SPACING.xl }} />
      </ScrollView>
    </SafeAreaView>
  );
}
