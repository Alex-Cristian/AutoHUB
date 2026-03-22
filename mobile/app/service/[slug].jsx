import { useEffect, useState } from 'react';
import { View, Text, ScrollView, TouchableOpacity, StyleSheet, ActivityIndicator, Linking, Alert } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { servicesApi } from '../../src/api/endpoints';
import { useAuthStore } from '../../src/store/authStore';
import { Stars, Badge, Card, Button, ErrorState } from '../../src/components/UI';
import { COLORS, FONTS, RADIUS, SPACING } from '../../src/constants/theme';

function InfoRow({ icon, label, value, onPress, color }) {
  if (!value) return null;
  return (
    <TouchableOpacity style={styles.infoRow} onPress={onPress} disabled={!onPress}>
      <Ionicons name={icon} size={16} color={color || COLORS.primary} style={{ marginTop: 2 }} />
      <View style={{ flex: 1 }}>
        <Text style={styles.infoLabel}>{label}</Text>
        <Text style={[styles.infoValue, color && { color: color }]}>{value}</Text>
      </View>
      {onPress && <Ionicons name="open-outline" size={14} color={COLORS.textMuted} />}
    </TouchableOpacity>
  );
}

function ReviewCard({ review }) {
  return (
    <View style={styles.reviewCard}>
      <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
        <Text style={styles.reviewAuthor}>{review.author}</Text>
        <Stars rating={review.rating} size={12} />
      </View>
      {review.comment && <Text style={styles.reviewComment}>{review.comment}</Text>}
      {review.created_at && <Text style={styles.reviewDate}>{review.created_at.slice(0, 10)}</Text>}
    </View>
  );
}

export default function ServiceDetailScreen() {
  var { slug } = useLocalSearchParams();
  var router = useRouter();
  var { isLoggedIn } = useAuthStore();
  var [service, setService] = useState(null);
  var [isLoading, setIsLoading] = useState(true);
  var [error, setError] = useState(null);
  var [isFav, setIsFav] = useState(false);
  var [showAllReviews, setShowAllReviews] = useState(false);

  useEffect(function() {
    setIsLoading(true);
    servicesApi.detail(slug)
      .then(function(res) { setService(res.data); setIsFav(res.data.is_favorited); setIsLoading(false); })
      .catch(function(err) { setError(err.message); setIsLoading(false); });
  }, [slug]);

  function handleFavorite() {
    if (!isLoggedIn) { router.push('/auth/login'); return; }
    servicesApi.toggleFavorite(slug)
      .then(function(res) { setIsFav(res.data.is_favorited); })
      .catch(function() {});
  }

  if (isLoading) return <View style={styles.center}><ActivityIndicator size="large" color={COLORS.primary} /></View>;
  if (error || !service) return <ErrorState message={error || 'Service negasit'} onRetry={function() { router.back(); }} />;

  var reviews = showAllReviews ? service.reviews : service.reviews.slice(0, 3);

  return (
    <SafeAreaView style={styles.safe} edges={['bottom']}>
      <ScrollView contentContainerStyle={styles.container} showsVerticalScrollIndicator={false}>

        {/* Header card */}
        <Card style={{ gap: SPACING.sm, marginBottom: SPACING.md }}>
          <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <View style={styles.catPill}>
              <Text style={styles.catPillText}>{service.category}</Text>
            </View>
            <TouchableOpacity onPress={handleFavorite} hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}>
              <Ionicons name={isFav ? 'heart' : 'heart-outline'} size={24} color={isFav ? COLORS.primary : COLORS.textMuted} />
            </TouchableOpacity>
          </View>
          <Text style={styles.serviceName}>{service.name}</Text>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
            <Stars rating={service.rating} size={16} />
            <Text style={{ fontSize: FONTS.lg, fontWeight: '800', color: COLORS.textPrimary }}>
              {service.rating > 0 ? service.rating.toFixed(1) : 'N/A'}
            </Text>
            {service.review_count > 0 && (
              <Text style={{ fontSize: FONTS.sm, color: COLORS.textSecondary }}>{service.review_count} recenzii</Text>
            )}
          </View>
          {service.is_featured && (
            <View style={styles.featuredBadge}>
              <Ionicons name="ribbon" size={14} color={COLORS.star} />
              <Text style={{ fontSize: FONTS.sm, color: COLORS.star, fontWeight: '600' }}>Service Recomandat</Text>
            </View>
          )}
          {service.description && <Text style={styles.description}>{service.description}</Text>}
        </Card>

        {/* Pret */}
        <Card style={{ marginBottom: SPACING.md }}>
          <Text style={styles.sectionTitle}>Preturi</Text>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: 'rgba(230,48,48,0.08)', padding: SPACING.md, borderRadius: RADIUS.sm }}>
            <Ionicons name="pricetag" size={20} color={COLORS.primary} />
            <Text style={{ fontSize: FONTS.xl, fontWeight: '800', color: COLORS.primary }}>{service.price_range}</Text>
          </View>
        </Card>

        {/* Servicii oferite */}
        {service.service_items && service.service_items.length > 0 && (
          <Card style={{ marginBottom: SPACING.md }}>
            <Text style={styles.sectionTitle}>Servicii si Preturi</Text>
            {service.service_items.map(function(item) {
              return (
                <View key={item.id} style={styles.serviceItem}>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.itemName}>{item.name}</Text>
                    {item.description ? <Text style={styles.itemDesc}>{item.description}</Text> : null}
                  </View>
                  <Text style={styles.itemPrice}>
                    {item.price_from ? parseInt(item.price_from) + (item.price_to ? '-' + parseInt(item.price_to) : '') + ' RON' : 'La cerere'}
                  </Text>
                </View>
              );
            })}
          </Card>
        )}

        {/* Contact */}
        <Card style={{ marginBottom: SPACING.md }}>
          <Text style={styles.sectionTitle}>Contact si Locatie</Text>
          <InfoRow icon="location" label="Adresa" value={service.address} />
          <InfoRow icon="business" label="Oras" value={service.city_display} />
          <InfoRow icon="time" label="Program" value={service.schedule} />
          <InfoRow icon="call" label="Telefon" value={service.phone} color={COLORS.primary} onPress={function() { Linking.openURL('tel:' + service.phone); }} />
          {service.email && <InfoRow icon="mail" label="Email" value={service.email} onPress={function() { Linking.openURL('mailto:' + service.email); }} />}
          {service.website && <InfoRow icon="globe" label="Website" value={service.website} color={COLORS.info} onPress={function() { Linking.openURL(service.website); }} />}
        </Card>

        {/* Harta */}
        {service.lat && service.lng && (
          <TouchableOpacity
            style={[styles.mapBtn]}
            onPress={function() { Linking.openURL('https://www.google.com/maps?q=' + service.lat + ',' + service.lng); }}
          >
            <Ionicons name="map" size={18} color={COLORS.primary} />
            <Text style={{ flex: 1, fontSize: FONTS.md, color: COLORS.textPrimary, fontWeight: '600' }}>Deschide in Google Maps</Text>
            <Ionicons name="open-outline" size={14} color={COLORS.textMuted} />
          </TouchableOpacity>
        )}

        {/* Recenzii */}
        {service.reviews && service.reviews.length > 0 && (
          <Card style={{ marginBottom: SPACING.md }}>
            <Text style={styles.sectionTitle}>Recenzii</Text>
            {reviews.map(function(r) { return <ReviewCard key={r.id} review={r} />; })}
            {service.reviews.length > 3 && (
              <TouchableOpacity onPress={function() { setShowAllReviews(function(p) { return !p; }); }} style={{ alignItems: 'center', paddingTop: SPACING.sm }}>
                <Text style={{ color: COLORS.primary, fontWeight: '600', fontSize: FONTS.sm }}>
                  {showAllReviews ? 'Arata mai putine' : 'Arata toate ' + service.reviews.length + ' recenzii'}
                </Text>
              </TouchableOpacity>
            )}
          </Card>
        )}

        <View style={{ height: 100 }} />
      </ScrollView>

      {/* CTA Fix */}
      <View style={styles.ctaBar}>
        <View>
          <Text style={{ fontSize: FONTS.xs, color: COLORS.textMuted }}>Preturi de la</Text>
          <Text style={{ fontSize: FONTS.lg, fontWeight: '800', color: COLORS.primary }}>{service.price_range}</Text>
        </View>
        <TouchableOpacity
          style={styles.bookBtn}
          onPress={function() {
            if (!isLoggedIn) { router.push('/auth/login'); return; }
            router.push('/booking/' + slug);
          }}
        >
          <Ionicons name="calendar" size={18} color="#fff" />
          <Text style={{ color: '#fff', fontSize: FONTS.md, fontWeight: '700' }}>Programeaza-te</Text>
        </TouchableOpacity>
      </View>
    </SafeAreaView>
  );
}

var styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: COLORS.bg },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: COLORS.bg },
  container: { padding: SPACING.md },
  catPill: { alignSelf: 'flex-start', backgroundColor: 'rgba(230,48,48,0.15)', paddingHorizontal: 10, paddingVertical: 4, borderRadius: RADIUS.full, borderWidth: 1, borderColor: 'rgba(230,48,48,0.3)' },
  catPillText: { fontSize: FONTS.xs, color: COLORS.primary, fontWeight: '700', textTransform: 'uppercase', letterSpacing: 1 },
  serviceName: { fontSize: FONTS.xxl, fontWeight: '800', color: COLORS.textPrimary, lineHeight: 30 },
  featuredBadge: { flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: 'rgba(245,158,11,0.12)', paddingHorizontal: 10, paddingVertical: 5, borderRadius: RADIUS.sm, alignSelf: 'flex-start', borderWidth: 1, borderColor: 'rgba(245,158,11,0.3)' },
  description: { fontSize: FONTS.sm, color: COLORS.textSecondary, lineHeight: 20 },
  sectionTitle: { fontSize: FONTS.md, fontWeight: '700', color: COLORS.textSecondary, textTransform: 'uppercase', letterSpacing: 0.8, marginBottom: SPACING.sm },
  infoRow: { flexDirection: 'row', alignItems: 'flex-start', gap: 10, paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: COLORS.divider },
  infoLabel: { fontSize: FONTS.xs, color: COLORS.textMuted, marginBottom: 1 },
  infoValue: { fontSize: FONTS.md, color: COLORS.textPrimary, fontWeight: '500' },
  serviceItem: { flexDirection: 'row', alignItems: 'center', paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: COLORS.divider, gap: SPACING.sm },
  itemName: { fontSize: FONTS.md, fontWeight: '600', color: COLORS.textPrimary },
  itemDesc: { fontSize: FONTS.xs, color: COLORS.textSecondary, marginTop: 2 },
  itemPrice: { fontSize: FONTS.sm, color: COLORS.primary, fontWeight: '700' },
  mapBtn: { flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: COLORS.bgCard, borderRadius: RADIUS.md, padding: SPACING.md, borderWidth: 1, borderColor: COLORS.border, marginBottom: SPACING.md },
  reviewCard: { paddingVertical: SPACING.sm, borderBottomWidth: 1, borderBottomColor: COLORS.divider },
  reviewAuthor: { fontSize: FONTS.sm, fontWeight: '700', color: COLORS.textPrimary },
  reviewComment: { fontSize: FONTS.sm, color: COLORS.textSecondary, marginTop: 4, lineHeight: 18 },
  reviewDate: { fontSize: FONTS.xs, color: COLORS.textMuted, marginTop: 4 },
  ctaBar: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', backgroundColor: COLORS.bgCard, padding: SPACING.md, borderTopWidth: 1, borderTopColor: COLORS.border },
  bookBtn: { flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: COLORS.primary, paddingVertical: 12, paddingHorizontal: SPACING.lg, borderRadius: RADIUS.md },
});
