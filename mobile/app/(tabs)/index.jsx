import { useEffect, useState } from 'react';
import { View, Text, TextInput, ScrollView, TouchableOpacity, StyleSheet, ActivityIndicator } from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useServicesStore } from '../../src/store/servicesStore';
import { useAuthStore } from '../../src/store/authStore';
import ServiceCard from '../../src/components/ServiceCard';
import { SectionHeader } from '../../src/components/UI';
import { COLORS, FONTS, RADIUS, SPACING, CATEGORIES } from '../../src/constants/theme';

function CategoryCard({ item, onPress }) {
  return (
    <TouchableOpacity style={styles.catCard} onPress={onPress} activeOpacity={0.7}>
      <View style={[styles.catIcon, { backgroundColor: item.color + '18' }]}>
        <Ionicons name={item.icon} size={24} color={item.color} />
      </View>
      <Text style={styles.catLabel}>{item.label}</Text>
    </TouchableOpacity>
  );
}

export default function HomeScreen() {
  var router = useRouter();
  var [search, setSearch] = useState('');
  var { featured, isLoading, loadFeatured, applyFilters, toggleFavorite } = useServicesStore();
  var { user, isLoggedIn } = useAuthStore();

  useEffect(function() { loadFeatured(); }, []);

  function handleSearch() {
    if (!search.trim()) return;
    applyFilters({ q: search.trim(), category: '', city: '' });
    router.push('/(tabs)/services');
  }

  function handleCategory(slug) {
    applyFilters({ category: slug, q: '', city: '' });
    router.push('/(tabs)/services');
  }

  return (
    <SafeAreaView style={styles.safe} edges={['bottom']}>
      <ScrollView style={styles.scroll} contentContainerStyle={styles.container} showsVerticalScrollIndicator={false}>

        {/* Hero */}
        <View style={styles.hero}>
          {isLoggedIn && user
            ? <Text style={styles.heroGreet}>Buna, {user.first_name || user.username}! 👋</Text>
            : <Text style={styles.heroSub}>Gaseste cel mai bun</Text>
          }
          <Text style={styles.heroTitle}>Service Auto</Text>
          <Text style={styles.heroDesc}>Marketplace-ul #1 pentru service-uri auto din Romania</Text>
        </View>

        {/* Search */}
        <View style={styles.searchRow}>
          <View style={styles.searchBox}>
            <Ionicons name="search" size={18} color={COLORS.textSecondary} />
            <TextInput
              style={styles.searchInput}
              placeholder="Cauta service, oras..."
              placeholderTextColor={COLORS.textMuted}
              value={search}
              onChangeText={setSearch}
              onSubmitEditing={handleSearch}
              returnKeyType="search"
              selectionColor={COLORS.primary}
            />
            {search.length > 0 && (
              <TouchableOpacity onPress={function() { setSearch(''); }}>
                <Ionicons name="close-circle" size={16} color={COLORS.textMuted} />
              </TouchableOpacity>
            )}
          </View>
          <TouchableOpacity style={styles.searchBtn} onPress={handleSearch}>
            <Ionicons name="arrow-forward" size={20} color="#fff" />
          </TouchableOpacity>
        </View>

        {/* Categorii */}
        <SectionHeader title="Categorii" />
        <View style={styles.catGrid}>
          {CATEGORIES.map(function(cat) {
            return <CategoryCard key={cat.slug} item={cat} onPress={function() { handleCategory(cat.slug); }} />;
          })}
        </View>

        {/* Actiuni rapide daca e logat */}
        {isLoggedIn && (
          <View style={styles.quickRow}>
            <TouchableOpacity style={styles.quickBtn} onPress={function() { router.push('/(tabs)/cars'); }}>
              <Ionicons name="car-sport" size={20} color={COLORS.primary} />
              <Text style={styles.quickLabel}>Masinile Mele</Text>
            </TouchableOpacity>
            <TouchableOpacity style={styles.quickBtn} onPress={function() { router.push('/(tabs)/profile'); }}>
              <Ionicons name="calendar" size={20} color={COLORS.primary} />
              <Text style={styles.quickLabel}>Programarile Mele</Text>
            </TouchableOpacity>
          </View>
        )}

        {/* Recomandate */}
        <SectionHeader
          title="Recomandate"
          action={function() { applyFilters({ sort: 'rating', q: '', category: '', city: '' }); router.push('/(tabs)/services'); }}
          actionLabel="Vezi toate"
        />

        {isLoading && featured.length === 0
          ? <ActivityIndicator color={COLORS.primary} style={{ marginTop: 20 }} />
          : featured.map(function(s) {
              return <ServiceCard key={s.id} service={s} onFavorite={isLoggedIn ? function(slug) { toggleFavorite(slug); } : undefined} />;
            })
        }

        <View style={{ height: SPACING.xl }} />
      </ScrollView>
    </SafeAreaView>
  );
}

var styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: COLORS.bg },
  scroll: { flex: 1 },
  container: { paddingHorizontal: SPACING.md, paddingTop: SPACING.md },
  hero: { marginBottom: SPACING.lg, paddingTop: SPACING.sm },
  heroGreet: { fontSize: FONTS.md, color: COLORS.textSecondary },
  heroSub: { fontSize: FONTS.sm, color: COLORS.textSecondary, textTransform: 'uppercase', letterSpacing: 1.5 },
  heroTitle: { fontSize: FONTS.xxxl, fontWeight: '800', color: COLORS.textPrimary, lineHeight: 36 },
  heroDesc: { fontSize: FONTS.sm, color: COLORS.textSecondary, marginTop: 4 },
  searchRow: { flexDirection: 'row', alignItems: 'center', gap: SPACING.sm, marginBottom: SPACING.lg },
  searchBox: { flex: 1, flexDirection: 'row', alignItems: 'center', backgroundColor: COLORS.bgInput, borderRadius: RADIUS.md, paddingHorizontal: SPACING.md, height: 48, borderWidth: 1, borderColor: COLORS.border, gap: 8 },
  searchInput: { flex: 1, color: COLORS.textPrimary, fontSize: FONTS.md },
  searchBtn: { width: 48, height: 48, borderRadius: RADIUS.md, backgroundColor: COLORS.primary, justifyContent: 'center', alignItems: 'center' },
  catGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 10, marginBottom: SPACING.lg },
  catCard: { width: '30%', flexGrow: 1, backgroundColor: COLORS.bgCard, borderRadius: RADIUS.md, padding: SPACING.md, alignItems: 'center', borderWidth: 1, borderColor: COLORS.border, gap: 6 },
  catIcon: { width: 48, height: 48, borderRadius: RADIUS.sm, justifyContent: 'center', alignItems: 'center' },
  catLabel: { fontSize: FONTS.xs, fontWeight: '600', color: COLORS.textSecondary, textAlign: 'center' },
  quickRow: { flexDirection: 'row', gap: SPACING.sm, marginBottom: SPACING.lg },
  quickBtn: { flex: 1, flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: COLORS.bgCard, borderRadius: RADIUS.md, padding: SPACING.md, borderWidth: 1, borderColor: COLORS.border },
  quickLabel: { fontSize: FONTS.sm, fontWeight: '600', color: COLORS.textPrimary },
});
