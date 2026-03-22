import { useEffect, useState, useCallback } from 'react';
import { View, Text, ScrollView, TouchableOpacity, StyleSheet, ActivityIndicator, Alert, RefreshControl } from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useAuthStore } from '../../src/store/authStore';
import { carsApi } from '../../src/api/endpoints';
import { Card, Button, Badge, EmptyState } from '../../src/components/UI';
import { COLORS, FONTS, RADIUS, SPACING } from '../../src/constants/theme';

var DOC_LABELS = { itp_expiry: 'ITP', rca_expiry: 'RCA', rovinieta_expiry: 'Rovinieta', casco_expiry: 'CASCO', trusa_expiry: 'Trusa', extinctor_expiry: 'Extinctor' };
var STATUS_COLORS = { ok: COLORS.success, soon: COLORS.warning, expired: COLORS.error, missing: COLORS.textMuted };

function DocBadge({ doc }) {
  var color = STATUS_COLORS[doc.status] || COLORS.textMuted;
  var label = DOC_LABELS[doc.field] || doc.field;
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 8, paddingVertical: 4, borderRadius: RADIUS.full, borderWidth: 1, borderColor: color + '40', backgroundColor: color + '18' }}>
      <Ionicons name={doc.status === 'ok' ? 'checkmark-circle' : doc.status === 'expired' ? 'alert-circle' : doc.status === 'soon' ? 'alarm' : 'help-circle'} size={11} color={color} />
      <Text style={{ fontSize: 10, fontWeight: '700', color: color }}>{label}</Text>
      {doc.days_left !== null && doc.days_left >= 0 && doc.status !== 'ok' && (
        <Text style={{ fontSize: 9, fontWeight: '700', color: color }}>{doc.days_left}z</Text>
      )}
      {doc.status === 'expired' && <Text style={{ fontSize: 9, fontWeight: '700', color: color }}>-{doc.days_overdue}z</Text>}
    </View>
  );
}

function CarCard({ car, onEdit, onDelete, onExpiry }) {
  var docs = car.expiry_profile || [];
  var expiredCount = docs.filter(function(d) { return d.status === 'expired'; }).length;
  var soonCount = docs.filter(function(d) { return d.status === 'soon'; }).length;
  var overallColor = expiredCount > 0 ? COLORS.error : soonCount > 0 ? COLORS.warning : COLORS.success;

  return (
    <Card style={{ marginBottom: SPACING.md }}>
      {/* Header */}
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: SPACING.sm, marginBottom: SPACING.sm }}>
        <View style={{ width: 48, height: 48, borderRadius: RADIUS.md, backgroundColor: COLORS.bgInput, borderWidth: 1, borderColor: overallColor + '40', justifyContent: 'center', alignItems: 'center' }}>
          <Ionicons name="car-sport" size={24} color={overallColor} />
        </View>
        <View style={{ flex: 1 }}>
          <Text style={{ fontSize: FONTS.lg, fontWeight: '700', color: COLORS.textPrimary }}>{car.make} {car.model}</Text>
          <Text style={{ fontSize: FONTS.md, fontWeight: '600', color: COLORS.primary, fontFamily: 'monospace' }}>{car.plate_number}</Text>
          {car.year && <Text style={{ fontSize: FONTS.xs, color: COLORS.textMuted }}>{car.year} · {car.fuel || 'N/A'}</Text>}
        </View>
        <View style={{ flexDirection: 'row', gap: 4 }}>
          <TouchableOpacity onPress={function() { onEdit(car); }} style={{ width: 36, height: 36, justifyContent: 'center', alignItems: 'center', borderRadius: RADIUS.sm, backgroundColor: COLORS.bgInput }}>
            <Ionicons name="create-outline" size={18} color={COLORS.textSecondary} />
          </TouchableOpacity>
          <TouchableOpacity onPress={function() { onDelete(car); }} style={{ width: 36, height: 36, justifyContent: 'center', alignItems: 'center', borderRadius: RADIUS.sm, backgroundColor: COLORS.bgInput }}>
            <Ionicons name="trash-outline" size={18} color={COLORS.error} />
          </TouchableOpacity>
        </View>
      </View>

      {/* Documente */}
      {docs.length > 0 && (
        <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6, paddingVertical: SPACING.xs }}>
          {docs.map(function(doc, i) { return <DocBadge key={i} doc={doc} />; })}
        </View>
      )}

      {/* Alerta */}
      {expiredCount > 0 && (
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: COLORS.error + '15', borderWidth: 1, borderColor: COLORS.error + '40', borderRadius: RADIUS.sm, padding: SPACING.sm }}>
          <Ionicons name="alert-circle" size={14} color={COLORS.error} />
          <Text style={{ fontSize: FONTS.sm, color: COLORS.error, fontWeight: '600' }}>{expiredCount} document(e) expirate!</Text>
        </View>
      )}
      {soonCount > 0 && expiredCount === 0 && (
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: COLORS.warning + '15', borderWidth: 1, borderColor: COLORS.warning + '40', borderRadius: RADIUS.sm, padding: SPACING.sm }}>
          <Ionicons name="alarm" size={14} color={COLORS.warning} />
          <Text style={{ fontSize: FONTS.sm, color: COLORS.warning, fontWeight: '600' }}>{soonCount} document(e) expira curand</Text>
        </View>
      )}

      {/* Buton expirari */}
      <TouchableOpacity
        style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, paddingVertical: 10, borderRadius: RADIUS.md, borderWidth: 1, borderColor: COLORS.primary + '60', backgroundColor: COLORS.primary + '10', marginTop: SPACING.xs }}
        onPress={function() { onExpiry(car); }}
      >
        <Ionicons name="document-text" size={16} color={COLORS.primary} />
        <Text style={{ fontSize: FONTS.sm, color: COLORS.primary, fontWeight: '700' }}>Gestioneaza Documente</Text>
      </TouchableOpacity>
    </Card>
  );
}

export default function CarsScreen() {
  var router = useRouter();
  var { isLoggedIn } = useAuthStore();
  var [cars, setCars] = useState([]);
  var [isLoading, setIsLoading] = useState(true);
  var [isRefreshing, setIsRefreshing] = useState(false);

  function load(refresh) {
    if (refresh) setIsRefreshing(true);
    else setIsLoading(true);
    carsApi.list()
      .then(function(res) { setCars(res.data.cars || []); })
      .catch(function() { setCars([]); })
      .finally(function() { setIsLoading(false); setIsRefreshing(false); });
  }

  useEffect(function() { if (isLoggedIn) load(); else setIsLoading(false); }, [isLoggedIn]);

  function handleDelete(car) {
    Alert.alert('Sterge masina', 'Esti sigur ca vrei sa stergi ' + car.make + ' ' + car.model + '?', [
      { text: 'Anuleaza', style: 'cancel' },
      { text: 'Sterge', style: 'destructive', onPress: function() {
        carsApi.remove(car.id).then(function() { setCars(function(p) { return p.filter(function(c) { return c.id !== car.id; }); }); }).catch(function() {});
      }}
    ]);
  }

  if (!isLoggedIn) {
    return (
      <SafeAreaView style={{ flex: 1, backgroundColor: COLORS.bg }} edges={['bottom']}>
        <EmptyState icon="car-outline" title="Masinile Tale" subtitle="Autentifica-te pentru a-ti gestiona masinile" action={function() { router.push('/auth/login'); }} actionLabel="Autentifica-te" />
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: COLORS.bg }} edges={['bottom']}>
      <ScrollView
        contentContainerStyle={{ padding: SPACING.md }}
        showsVerticalScrollIndicator={false}
        refreshControl={<RefreshControl refreshing={isRefreshing} onRefresh={function() { load(true); }} tintColor={COLORS.primary} />}
      >
        {isLoading
          ? <ActivityIndicator color={COLORS.primary} style={{ marginTop: 40 }} />
          : cars.length === 0
            ? (
              <View style={{ alignItems: 'center', paddingTop: 60, gap: SPACING.md }}>
                <Ionicons name="car-outline" size={64} color={COLORS.textMuted} />
                <Text style={{ fontSize: FONTS.xl, fontWeight: '700', color: COLORS.textPrimary }}>Nicio masina adaugata</Text>
                <Text style={{ fontSize: FONTS.md, color: COLORS.textSecondary, textAlign: 'center' }}>Adauga prima ta masina pentru a urmari documentele</Text>
                <Button label="Adauga Masina" onPress={function() { router.push('/cars/add'); }} icon="add-circle" />
              </View>
            )
            : cars.map(function(car) {
                return (
                  <CarCard
                    key={car.id} car={car}
                    onEdit={function(c) { router.push('/cars/' + c.id); }}
                    onDelete={handleDelete}
                    onExpiry={function(c) { router.push('/cars/expiry/' + c.id); }}
                  />
                );
              })
        }

        {!isLoading && cars.length > 0 && (
          <Button label="Adauga Masina Noua" onPress={function() { router.push('/cars/add'); }} icon="add-circle" variant="outline" style={{ marginTop: SPACING.sm, marginBottom: SPACING.xl }} />
        )}
      </ScrollView>
    </SafeAreaView>
  );
}
