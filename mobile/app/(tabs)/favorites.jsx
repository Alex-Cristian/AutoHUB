import { useEffect, useState, useCallback } from 'react';
import { View, FlatList, ActivityIndicator, RefreshControl } from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useAuthStore } from '../../src/store/authStore';
import { favoritesApi, servicesApi } from '../../src/api/endpoints';
import ServiceCard from '../../src/components/ServiceCard';
import { EmptyState, ErrorState } from '../../src/components/UI';
import { COLORS, SPACING } from '../../src/constants/theme';

export default function FavoritesScreen() {
  var router = useRouter();
  var { isLoggedIn } = useAuthStore();
  var [favorites, setFavorites] = useState([]);
  var [isLoading, setIsLoading] = useState(true);
  var [isRefreshing, setIsRefreshing] = useState(false);
  var [error, setError] = useState(null);

  function load(refresh) {
    if (refresh) setIsRefreshing(true);
    else setIsLoading(true);
    setError(null);
    favoritesApi.list()
      .then(function(res) { setFavorites(res.data.favorites || []); })
      .catch(function(err) { setError(err.message); })
      .finally(function() { setIsLoading(false); setIsRefreshing(false); });
  }

  useEffect(function() { if (isLoggedIn) load(); else setIsLoading(false); }, [isLoggedIn]);

  function handleToggle(slug) {
    servicesApi.toggleFavorite(slug)
      .then(function() { setFavorites(function(prev) { return prev.filter(function(s) { return s.slug !== slug; }); }); })
      .catch(function() {});
  }

  if (!isLoggedIn) {
    return (
      <SafeAreaView style={{ flex: 1, backgroundColor: COLORS.bg }} edges={['bottom']}>
        <EmptyState icon="heart-outline" title="Favorite" subtitle="Autentifica-te pentru a vedea service-urile favorite" action={function() { router.push('/auth/login'); }} actionLabel="Autentifica-te" />
      </SafeAreaView>
    );
  }

  if (isLoading) return <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: COLORS.bg }}><ActivityIndicator size="large" color={COLORS.primary} /></View>;
  if (error) return <ErrorState message={error} onRetry={function() { load(); }} />;

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: COLORS.bg }} edges={['bottom']}>
      <FlatList
        data={favorites}
        keyExtractor={function(item) { return String(item.id); }}
        renderItem={function({ item }) { return <ServiceCard service={item} onFavorite={handleToggle} />; }}
        contentContainerStyle={{ padding: SPACING.md }}
        showsVerticalScrollIndicator={false}
        refreshing={isRefreshing}
        onRefresh={function() { load(true); }}
        ListEmptyComponent={<EmptyState icon="heart-outline" title="Niciun favorit inca" subtitle="Adauga service-uri la favorite apasand iconita inima" action={function() { router.push('/(tabs)/services'); }} actionLabel="Exploreaza Service-uri" />}
      />
    </SafeAreaView>
  );
}
