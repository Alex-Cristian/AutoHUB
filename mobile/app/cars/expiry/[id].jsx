import { useEffect, useState } from 'react';
import { View, Text, ScrollView, TouchableOpacity, Alert, ActivityIndicator, KeyboardAvoidingView, Platform } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { carsApi } from '../../../src/api/endpoints';
import { Card, Button, Input } from '../../../src/components/UI';
import { COLORS, FONTS, SPACING, RADIUS } from '../../../src/constants/theme';

var DOCS = [
  { field: 'itp_expiry', label: 'ITP', icon: 'shield-checkmark', soon_days: 0 },
  { field: 'rca_expiry', label: 'RCA', icon: 'document-text', soon_days: 30 },
  { field: 'rovinieta_expiry', label: 'Rovinieta', icon: 'sign-out', soon_days: 30 },
  { field: 'casco_expiry', label: 'CASCO', icon: 'shield', soon_days: 30 },
  { field: 'trusa_expiry', label: 'Trusa Auto', icon: 'medkit', soon_days: 30 },
  { field: 'extinctor_expiry', label: 'Extinctor', icon: 'flame', soon_days: 30 },
];

var STATUS_COLORS = { ok: COLORS.success, soon: COLORS.warning, expired: COLORS.error, missing: COLORS.textMuted };

export default function CarExpiryScreen() {
  var { id } = useLocalSearchParams();
  var router = useRouter();
  var [car, setCar] = useState(null);
  var [isLoading, setIsLoading] = useState(true);
  var [isSaving, setIsSaving] = useState(false);
  var [dates, setDates] = useState({});

  useEffect(function() {
    carsApi.list().then(function(res) {
      var cars = res.data.cars || [];
      var found = cars.find(function(c) { return String(c.id) === String(id); });
      if (found) {
        setCar(found);
        var d = {};
        (found.expiry_profile || []).forEach(function(doc) { d[doc.field] = doc.date || ''; });
        setDates(d);
      }
      setIsLoading(false);
    }).catch(function() { setIsLoading(false); });
  }, [id]);

  function getStatus(doc) {
    var date = dates[doc.field];
    if (!date) return 'missing';
    var today = new Date();
    var expiry = new Date(date);
    var diffDays = Math.floor((expiry - today) / (1000 * 60 * 60 * 24));
    if (diffDays < 0) return 'expired';
    if (diffDays <= doc.soon_days) return 'soon';
    return 'ok';
  }

  async function handleSave() {
    setIsSaving(true);
    try {
      var payload = {};
      DOCS.forEach(function(doc) { payload[doc.field] = dates[doc.field] || null; });
      await carsApi.updateExpiry(id, payload);
      Alert.alert('Salvat!', 'Datele de expirare au fost actualizate.', [{ text: 'OK', onPress: function() { router.back(); } }]);
    } catch (err) {
      Alert.alert('Eroare', err.message || 'Nu s-a putut salva.');
    } finally { setIsSaving(false); }
  }

  if (isLoading) return <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: COLORS.bg }}><ActivityIndicator size="large" color={COLORS.primary} /></View>;

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: COLORS.bg }} edges={['bottom']}>
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : 'height'}>
        <ScrollView contentContainerStyle={{ padding: SPACING.md, gap: SPACING.md }} keyboardShouldPersistTaps="handled">

          {car && (
            <View style={{ backgroundColor: COLORS.bgCard, borderRadius: RADIUS.md, padding: SPACING.md, borderWidth: 1, borderColor: COLORS.border, flexDirection: 'row', alignItems: 'center', gap: SPACING.sm }}>
              <Ionicons name="car-sport" size={24} color={COLORS.primary} />
              <View>
                <Text style={{ fontSize: FONTS.lg, fontWeight: '700', color: COLORS.textPrimary }}>{car.make} {car.model}</Text>
                <Text style={{ fontSize: FONTS.sm, color: COLORS.primary, fontWeight: '600' }}>{car.plate_number}</Text>
              </View>
            </View>
          )}

          <Text style={{ fontSize: FONTS.sm, color: COLORS.textSecondary }}>Introdu data de expirare pentru fiecare document in format YYYY-MM-DD (ex: 2025-12-31)</Text>

          {DOCS.map(function(doc) {
            var status = getStatus(doc);
            var color = STATUS_COLORS[status];
            var statusLabel = { ok: 'OK', soon: 'Expira curand', expired: 'Expirat', missing: 'Nesetat' }[status];
            return (
              <Card key={doc.field} style={{ gap: SPACING.sm }}>
                <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}>
                  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                    <View style={{ width: 36, height: 36, borderRadius: RADIUS.sm, backgroundColor: color + '18', justifyContent: 'center', alignItems: 'center' }}>
                      <Ionicons name={doc.icon} size={18} color={color} />
                    </View>
                    <Text style={{ fontSize: FONTS.lg, fontWeight: '700', color: COLORS.textPrimary }}>{doc.label}</Text>
                  </View>
                  <View style={{ paddingHorizontal: 8, paddingVertical: 3, borderRadius: RADIUS.full, borderWidth: 1, borderColor: color + '40', backgroundColor: color + '18' }}>
                    <Text style={{ fontSize: FONTS.xs, fontWeight: '700', color: color }}>{statusLabel}</Text>
                  </View>
                </View>
                <Input
                  label="Data expirare (YYYY-MM-DD)"
                  placeholder="2025-12-31"
                  value={dates[doc.field] || ''}
                  onChangeText={function(v) { setDates(function(p) { return Object.assign({}, p, { [doc.field]: v }); }); }}
                  keyboardType="numeric"
                  icon="calendar-outline"
                />
              </Card>
            );
          })}

          <Button label="Salveaza Documentele" onPress={handleSave} loading={isSaving} size="lg" icon="save" style={{ marginBottom: SPACING.xl }} />
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}
