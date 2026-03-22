import { useEffect, useState, useCallback } from 'react';
import { View, Text, TextInput, FlatList, TouchableOpacity, StyleSheet, ActivityIndicator, Modal, ScrollView, RefreshControl } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useServicesStore } from '../../src/store/servicesStore';
import { useAuthStore } from '../../src/store/authStore';
import ServiceCard from '../../src/components/ServiceCard';
import { Chip, SkeletonCard, EmptyState, ErrorState } from '../../src/components/UI';
import { COLORS, FONTS, RADIUS, SPACING, CATEGORIES, CITY_CHOICES } from '../../src/constants/theme';

var SORT_OPTIONS = [
  { value: '', label: 'Implicit' }, { value: 'rating', label: 'Rating' },
  { value: 'price_asc', label: 'Pret ↑' }, { value: 'price_desc', label: 'Pret ↓' },
  { value: 'reviews', label: 'Recenzii' }, { value: 'name', label: 'Nume A-Z' },
];

function FiltersModal({ visible, filters, onApply, onClose }) {
  var [local, setLocal] = useState(Object.assign({}, filters));
  function update(k, v) { setLocal(function(p) { return Object.assign({}, p, { [k]: v }); }); }

  return (
    <Modal visible={visible} animationType="slide" presentationStyle="pageSheet">
      <View style={{ flex: 1, backgroundColor: COLORS.bg }}>
        <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', padding: SPACING.md, borderBottomWidth: 1, borderBottomColor: COLORS.border }}>
          <Text style={{ fontSize: FONTS.xl, fontWeight: '700', color: COLORS.textPrimary }}>Filtre</Text>
          <TouchableOpacity onPress={onClose}><Ionicons name="close" size={24} color={COLORS.textPrimary} /></TouchableOpacity>
        </View>
        <ScrollView contentContainerStyle={{ padding: SPACING.md, gap: SPACING.sm }}>
          <Text style={fS.label}>Sortare</Text>
          <View style={fS.chipRow}>{SORT_OPTIONS.map(function(o) { return <Chip key={o.value} label={o.label} active={local.sort === o.value} onPress={function() { update('sort', o.value); }} />; })}</View>
          <Text style={fS.label}>Categorie</Text>
          <View style={fS.chipRow}>
            <Chip label="Toate" active={local.category === ''} onPress={function() { update('category', ''); }} />
            {CATEGORIES.map(function(c) { return <Chip key={c.slug} label={c.label} active={local.category === c.slug} onPress={function() { update('category', c.slug); }} />; })}
          </View>
          <Text style={fS.label}>Oras</Text>
          <View style={fS.chipRow}>{CITY_CHOICES.map(function(c) { return <Chip key={c.value} label={c.label} active={local.city === c.value} onPress={function() { update('city', c.value); }} />; })}</View>
          <Text style={fS.label}>Rating minim</Text>
          <View style={fS.chipRow}>{['', '3', '4', '4.5'].map(function(r) { return <Chip key={r} label={r ? r + '★+' : 'Oricare'} active={local.min_rating === r} onPress={function() { update('min_rating', r); }} />; })}</View>
          <Text style={fS.label}>Pret (RON)</Text>
          <View style={{ flexDirection: 'row', gap: SPACING.sm, alignItems: 'center' }}>
            <TextInput style={fS.priceInput} placeholder="Min" placeholderTextColor={COLORS.textMuted} keyboardType="numeric" value={local.price_min} onChangeText={function(v) { update('price_min', v); }} selectionColor={COLORS.primary} />
            <Text style={{ color: COLORS.textMuted }}>–</Text>
            <TextInput style={fS.priceInput} placeholder="Max" placeholderTextColor={COLORS.textMuted} keyboardType="numeric" value={local.price_max} onChangeText={function(v) { update('price_max', v); }} selectionColor={COLORS.primary} />
          </View>
        </ScrollView>
        <View style={{ flexDirection: 'row', gap: SPACING.sm, padding: SPACING.md, borderTopWidth: 1, borderTopColor: COLORS.border }}>
          <TouchableOpacity style={fS.resetBtn} onPress={function() { setLocal({ q: local.q, category: '', city: '', sort: '', min_rating: '', price_min: '', price_max: '' }); }}>
            <Text style={{ color: COLORS.textSecondary, fontWeight: '600' }}>Reseteaza</Text>
          </TouchableOpacity>
          <TouchableOpacity style={fS.applyBtn} onPress={function() { onApply(local); }}>
            <Text style={{ color: '#fff', fontWeight: '700', fontSize: FONTS.md }}>Aplica Filtrele</Text>
          </TouchableOpacity>
        </View>
      </View>
    </Modal>
  );
}

var fS = StyleSheet.create({
  label: { fontSize: FONTS.xs, fontWeight: '700', color: COLORS.textSecondary, textTransform: 'uppercase', letterSpacing: 1, marginTop: SPACING.md },
  chipRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  priceInput: { flex: 1, backgroundColor: COLORS.bgInput, borderRadius: RADIUS.md, padding: SPACING.sm, paddingHorizontal: SPACING.md, color: COLORS.textPrimary, fontSize: FONTS.md, borderWidth: 1, borderColor: COLORS.border, height: 44 },
  resetBtn: { flex: 1, height: 48, borderRadius: RADIUS.md, borderWidth: 1, borderColor: COLORS.border, justifyContent: 'center', alignItems: 'center' },
  applyBtn: { flex: 2, height: 48, borderRadius: RADIUS.md, backgroundColor: COLORS.primary, justifyContent: 'center', alignItems: 'center' },
});

export default function ServicesScreen() {
  var { services, total, filters, isLoading, isRefreshing, error, loadServices, applyFilters, resetFilters, setFilter, toggleFavorite } = useServicesStore();
  var { isLoggedIn } = useAuthStore();
  var [showFilters, setShowFilters] = useState(false);
  var [localSearch, setLocalSearch] = useState(filters.q || '');

  useEffect(function() { loadServices(); }, []);

  var activeCount = [filters.category, filters.city, filters.sort, filters.min_rating, filters.price_min, filters.price_max].filter(Boolean).length;

  var header = (
    <View>
      <View style={{ flexDirection: 'row', gap: 8, marginBottom: SPACING.sm }}>
        <View style={{ flex: 1, flexDirection: 'row', alignItems: 'center', backgroundColor: COLORS.bgInput, borderRadius: RADIUS.md, paddingHorizontal: 12, height: 44, borderWidth: 1, borderColor: COLORS.border, gap: 8 }}>
          <Ionicons name="search" size={16} color={COLORS.textSecondary} />
          <TextInput style={{ flex: 1, color: COLORS.textPrimary, fontSize: FONTS.sm }} placeholder="Cauta service..." placeholderTextColor={COLORS.textMuted} value={localSearch} onChangeText={setLocalSearch} onSubmitEditing={function() { setFilter('q', localSearch.trim()); }} returnKeyType="search" selectionColor={COLORS.primary} />
        </View>
        <TouchableOpacity style={[{ width: 44, height: 44, borderRadius: RADIUS.md, backgroundColor: COLORS.bgInput, borderWidth: 1, borderColor: COLORS.border, justifyContent: 'center', alignItems: 'center' }, activeCount > 0 && { backgroundColor: COLORS.primary, borderColor: COLORS.primary }]} onPress={function() { setShowFilters(true); }}>
          <Ionicons name="options" size={18} color={activeCount > 0 ? '#fff' : COLORS.textSecondary} />
          {activeCount > 0 && <View style={{ position: 'absolute', top: 4, right: 4, backgroundColor: '#fff', borderRadius: 6, width: 12, height: 12, justifyContent: 'center', alignItems: 'center' }}><Text style={{ fontSize: 8, fontWeight: '800', color: COLORS.primary }}>{activeCount}</Text></View>}
        </TouchableOpacity>
      </View>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginBottom: SPACING.sm }} contentContainerStyle={{ gap: 8 }}>
        <Chip label="Toate" active={filters.category === ''} onPress={function() { setFilter('category', ''); }} />
        {CATEGORIES.map(function(c) { return <Chip key={c.slug} label={c.label} active={filters.category === c.slug} onPress={function() { setFilter('category', c.slug); }} />; })}
      </ScrollView>
      <Text style={{ fontSize: FONTS.xs, color: COLORS.textMuted, marginBottom: SPACING.sm }}>{isLoading ? 'Se incarca...' : total + ' service-uri gasite'}</Text>
    </View>
  );

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: COLORS.bg }} edges={['bottom']}>
      <FlatList
        data={services}
        keyExtractor={function(item) { return String(item.id); }}
        renderItem={function({ item }) { return <ServiceCard service={item} onFavorite={isLoggedIn ? function(slug) { toggleFavorite(slug); } : undefined} />; }}
        ListHeaderComponent={header}
        contentContainerStyle={{ padding: SPACING.md }}
        showsVerticalScrollIndicator={false}
        refreshing={isRefreshing}
        onRefresh={function() { loadServices(true); }}
        ListEmptyComponent={!isLoading && !error && <EmptyState icon="search-outline" title="Niciun service gasit" subtitle="Incearca sa modifici filtrele" action={resetFilters} actionLabel="Reseteaza Filtrele" />}
        ListFooterComponent={isLoading && <ActivityIndicator color={COLORS.primary} style={{ padding: 20 }} />}
      />
      {error && <View style={{ flexDirection: 'row', alignItems: 'center', backgroundColor: 'rgba(239,68,68,0.15)', padding: SPACING.sm, paddingHorizontal: SPACING.md, gap: 6 }}><Ionicons name="warning" size={14} color={COLORS.error} /><Text style={{ fontSize: FONTS.sm, color: COLORS.error, flex: 1 }}>{error}</Text></View>}
      <FiltersModal visible={showFilters} filters={filters} onApply={function(f) { applyFilters(f); setShowFilters(false); }} onClose={function() { setShowFilters(false); }} />
    </SafeAreaView>
  );
}
