import React from 'react';
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { Stars } from './UI';
import { COLORS, FONTS, RADIUS, SPACING } from '../constants/theme';

var CAT_ICONS = { detailing: 'sparkles', mecanica: 'construct', electrica: 'flash', tractari: 'car', vulcanizari: 'ellipse', tinichigerie: 'hammer' };

export default function ServiceCard({ service, onFavorite, compact }) {
  var router = useRouter();
  var icon = CAT_ICONS[service.category_slug] || 'build-outline';

  return (
    <TouchableOpacity
      style={[styles.card, compact && styles.compact]}
      onPress={function() { router.push('/service/' + service.slug); }}
      activeOpacity={0.75}
    >
      <View style={styles.iconBox}>
        <Ionicons name={icon} size={compact ? 20 : 24} color={COLORS.primary} />
      </View>

      <View style={styles.content}>
        <View style={styles.topRow}>
          <Text style={styles.name} numberOfLines={1}>{service.name}</Text>
          {service.is_featured && (
            <View style={styles.topBadge}><Text style={styles.topBadgeText}>TOP</Text></View>
          )}
        </View>
        <View style={styles.metaRow}>
          <Ionicons name="location-outline" size={11} color={COLORS.textSecondary} />
          <Text style={styles.meta}>{service.city_display || service.city}</Text>
          <Text style={styles.dot}>·</Text>
          <Text style={styles.meta}>{service.category}</Text>
        </View>
        <View style={styles.ratingRow}>
          <Stars rating={service.rating} size={12} />
          <Text style={styles.ratingText}>
            {service.rating > 0 ? service.rating.toFixed(1) : 'N/A'}
            {service.review_count > 0 ? ' (' + service.review_count + ')' : ''}
          </Text>
        </View>
        {!compact && (
          <View style={styles.bottomRow}>
            <Text style={styles.price}>{service.price_range}</Text>
            <Text style={styles.schedule} numberOfLines={1}>{service.schedule}</Text>
          </View>
        )}
      </View>

      <View style={styles.rightCol}>
        {onFavorite && (
          <TouchableOpacity onPress={function() { onFavorite(service.slug); }} hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}>
            <Ionicons name={service.is_favorited ? 'heart' : 'heart-outline'} size={18} color={service.is_favorited ? COLORS.primary : COLORS.textMuted} />
          </TouchableOpacity>
        )}
        <Ionicons name="chevron-forward" size={16} color={COLORS.textMuted} />
      </View>
    </TouchableOpacity>
  );
}

var styles = StyleSheet.create({
  card: { flexDirection: 'row', alignItems: 'center', backgroundColor: COLORS.bgCard, borderRadius: RADIUS.md, padding: SPACING.md, marginBottom: SPACING.sm, borderWidth: 1, borderColor: COLORS.border },
  compact: { padding: SPACING.sm },
  iconBox: { width: 44, height: 44, borderRadius: RADIUS.sm, backgroundColor: 'rgba(230,48,48,0.12)', justifyContent: 'center', alignItems: 'center', marginRight: SPACING.sm },
  content: { flex: 1, gap: 3 },
  topRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  name: { flex: 1, fontSize: FONTS.md, fontWeight: '700', color: COLORS.textPrimary },
  topBadge: { backgroundColor: COLORS.primary, paddingHorizontal: 5, paddingVertical: 1, borderRadius: 3 },
  topBadgeText: { fontSize: 9, fontWeight: '800', color: '#fff' },
  metaRow: { flexDirection: 'row', alignItems: 'center', gap: 3 },
  meta: { fontSize: FONTS.xs, color: COLORS.textSecondary },
  dot: { fontSize: FONTS.xs, color: COLORS.textMuted },
  ratingRow: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  ratingText: { fontSize: FONTS.xs, color: COLORS.textSecondary },
  bottomRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginTop: 2 },
  price: { fontSize: FONTS.sm, color: COLORS.primary, fontWeight: '600' },
  schedule: { fontSize: FONTS.xs, color: COLORS.textMuted, flex: 1, textAlign: 'right' },
  rightCol: { flexDirection: 'row', alignItems: 'center', gap: 6, marginLeft: SPACING.xs },
});
