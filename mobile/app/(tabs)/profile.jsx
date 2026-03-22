import { useEffect, useState } from 'react';
import { View, Text, ScrollView, TouchableOpacity, StyleSheet, ActivityIndicator, RefreshControl } from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useAuthStore } from '../../src/store/authStore';
import { bookingsApi } from '../../src/api/endpoints';
import { Card, Badge, EmptyState } from '../../src/components/UI';
import { COLORS, FONTS, RADIUS, SPACING, STATUS_CONFIG } from '../../src/constants/theme';

function BookingCard({ booking, onPress }) {
  var cfg = STATUS_CONFIG[booking.status] || { color: COLORS.textMuted, label: booking.status, icon: 'help-circle-outline' };
  return (
    <TouchableOpacity style={bS.card} onPress={onPress} activeOpacity={0.75}>
      <View style={bS.topRow}>
        <Text style={bS.centerName} numberOfLines={1}>{booking.center ? booking.center.name : 'Service'}</Text>
        <Badge label={cfg.label} color={cfg.color} />
      </View>
      <View style={bS.infoRow}>
        <Ionicons name="car-outline" size={13} color={COLORS.textSecondary} />
        <Text style={bS.infoText}>{booking.car_brand} {booking.car_model} · {booking.car_plate}</Text>
      </View>
      <View style={bS.infoRow}>
        <Ionicons name="calendar-outline" size={13} color={COLORS.textSecondary} />
        <Text style={bS.infoText}>{booking.booking_date} {booking.booking_time ? 'ora ' + booking.booking_time : ''}</Text>
      </View>
      {booking.estimated_price && (
        <View style={bS.infoRow}>
          <Ionicons name="pricetag-outline" size={13} color={COLORS.textSecondary} />
          <Text style={bS.infoText}>{booking.estimated_price} RON</Text>
        </View>
      )}
    </TouchableOpacity>
  );
}

var bS = StyleSheet.create({
  card: { backgroundColor: COLORS.bgCard, borderRadius: RADIUS.md, padding: SPACING.md, marginBottom: SPACING.sm, borderWidth: 1, borderColor: COLORS.border, gap: 6 },
  topRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 },
  centerName: { flex: 1, fontSize: FONTS.md, fontWeight: '700', color: COLORS.textPrimary, marginRight: SPACING.sm },
  infoRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  infoText: { fontSize: FONTS.sm, color: COLORS.textSecondary },
});

export default function ProfileScreen() {
  var router = useRouter();
  var { user, isLoggedIn, logout } = useAuthStore();
  var [bookings, setBookings] = useState([]);
  var [isLoading, setIsLoading] = useState(false);
  var [isRefreshing, setIsRefreshing] = useState(false);

  function loadBookings(refresh) {
    if (refresh) setIsRefreshing(true);
    else setIsLoading(true);
    bookingsApi.myBookings()
      .then(function(res) { setBookings(res.data.bookings || []); })
      .catch(function() { setBookings([]); })
      .finally(function() { setIsLoading(false); setIsRefreshing(false); });
  }

  useEffect(function() { if (isLoggedIn) loadBookings(); }, [isLoggedIn]);

  if (!isLoggedIn) {
    return (
      <SafeAreaView style={{ flex: 1, backgroundColor: COLORS.bg }} edges={['bottom']}>
        <EmptyState
          icon="person-circle-outline"
          title="Contul tau"
          subtitle="Autentifica-te pentru a vedea programarile si masinile tale"
          action={function() { router.push('/auth/login'); }}
          actionLabel="Autentifica-te"
        />
      </SafeAreaView>
    );
  }

  var initial = ((user.first_name || user.username || '?')[0]).toUpperCase();

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: COLORS.bg }} edges={['bottom']}>
      <ScrollView
        contentContainerStyle={{ padding: SPACING.md, gap: SPACING.md }}
        showsVerticalScrollIndicator={false}
        refreshControl={<RefreshControl refreshing={isRefreshing} onRefresh={function() { loadBookings(true); }} tintColor={COLORS.primary} />}
      >
        {/* Avatar */}
        <Card style={{ flexDirection: 'row', alignItems: 'center', gap: SPACING.md }}>
          <View style={{ width: 60, height: 60, borderRadius: 30, backgroundColor: COLORS.primary, justifyContent: 'center', alignItems: 'center' }}>
            <Text style={{ fontSize: FONTS.xxl, fontWeight: '800', color: '#fff' }}>{initial}</Text>
          </View>
          <View style={{ flex: 1 }}>
            <Text style={{ fontSize: FONTS.lg, fontWeight: '700', color: COLORS.textPrimary }}>
              {user.first_name && user.last_name ? user.first_name + ' ' + user.last_name : user.username}
            </Text>
            <Text style={{ fontSize: FONTS.sm, color: COLORS.textSecondary }}>{user.email}</Text>
          </View>
        </Card>

        {/* Shortcut-uri */}
        <View style={{ flexDirection: 'row', gap: SPACING.sm }}>
          <TouchableOpacity style={{ flex: 1, backgroundColor: COLORS.bgCard, borderRadius: RADIUS.md, padding: SPACING.md, alignItems: 'center', gap: 6, borderWidth: 1, borderColor: COLORS.border }} onPress={function() { router.push('/(tabs)/cars'); }}>
            <Ionicons name="car-sport" size={24} color={COLORS.primary} />
            <Text style={{ fontSize: FONTS.xs, fontWeight: '600', color: COLORS.textSecondary }}>Masinile Mele</Text>
          </TouchableOpacity>
          <TouchableOpacity style={{ flex: 1, backgroundColor: COLORS.bgCard, borderRadius: RADIUS.md, padding: SPACING.md, alignItems: 'center', gap: 6, borderWidth: 1, borderColor: COLORS.border }} onPress={function() { router.push('/(tabs)/favorites'); }}>
            <Ionicons name="heart" size={24} color={COLORS.primary} />
            <Text style={{ fontSize: FONTS.xs, fontWeight: '600', color: COLORS.textSecondary }}>Favorite</Text>
          </TouchableOpacity>
          <TouchableOpacity style={{ flex: 1, backgroundColor: COLORS.bgCard, borderRadius: RADIUS.md, padding: SPACING.md, alignItems: 'center', gap: 6, borderWidth: 1, borderColor: COLORS.border }} onPress={function() { router.push('/(tabs)/services'); }}>
            <Ionicons name="construct" size={24} color={COLORS.primary} />
            <Text style={{ fontSize: FONTS.xs, fontWeight: '600', color: COLORS.textSecondary }}>Servicii</Text>
          </TouchableOpacity>
        </View>

        {/* Programari */}
        <Text style={{ fontSize: FONTS.lg, fontWeight: '700', color: COLORS.textPrimary }}>Programarile Mele</Text>

        {isLoading
          ? <ActivityIndicator color={COLORS.primary} style={{ margin: 20 }} />
          : bookings.length === 0
            ? (
              <View style={{ alignItems: 'center', gap: SPACING.sm, paddingVertical: SPACING.xl }}>
                <Ionicons name="calendar-outline" size={48} color={COLORS.textMuted} />
                <Text style={{ fontSize: FONTS.md, color: COLORS.textSecondary }}>Nicio programare inca</Text>
                <TouchableOpacity style={{ backgroundColor: COLORS.primary, paddingVertical: 10, paddingHorizontal: 20, borderRadius: RADIUS.md }} onPress={function() { router.push('/(tabs)/services'); }}>
                  <Text style={{ color: '#fff', fontWeight: '700', fontSize: FONTS.sm }}>Exploreaza Service-uri</Text>
                </TouchableOpacity>
              </View>
            )
            : bookings.map(function(b) {
                return <BookingCard key={b.id} booking={b} onPress={function() {}} />;
              })
        }

        {/* Logout */}
        <TouchableOpacity
          style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, padding: SPACING.md, backgroundColor: 'rgba(239,68,68,0.08)', borderRadius: RADIUS.md, borderWidth: 1, borderColor: 'rgba(239,68,68,0.2)', marginTop: SPACING.sm }}
          onPress={function() { logout(); }}
        >
          <Ionicons name="log-out-outline" size={18} color={COLORS.error} />
          <Text style={{ fontSize: FONTS.md, color: COLORS.error, fontWeight: '600' }}>Deconectare</Text>
        </TouchableOpacity>

        <View style={{ height: SPACING.xl }} />
      </ScrollView>
    </SafeAreaView>
  );
}
