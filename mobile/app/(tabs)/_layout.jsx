import { Tabs } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { COLORS } from '../../src/constants/theme';

function Icon({ name, focused }) {
  return <Ionicons name={name} size={24} color={focused ? COLORS.primary : COLORS.textMuted} />;
}

export default function TabLayout() {
  return (
    <Tabs screenOptions={{
      headerStyle: { backgroundColor: COLORS.bgCard },
      headerTintColor: COLORS.textPrimary,
      headerTitleStyle: { fontWeight: '700' },
      tabBarStyle: { backgroundColor: COLORS.bgCard, borderTopColor: COLORS.border, borderTopWidth: 1, paddingBottom: 8, paddingTop: 6, height: 60 },
      tabBarActiveTintColor: COLORS.primary,
      tabBarInactiveTintColor: COLORS.textMuted,
      tabBarLabelStyle: { fontSize: 11, fontWeight: '600' },
    }}>
      <Tabs.Screen name="index" options={{ title: 'Acasa', tabBarIcon: function({ focused }) { return <Icon name={focused ? 'home' : 'home-outline'} focused={focused} />; }, headerTitle: 'AutoEMG', headerTitleStyle: { color: COLORS.primary, fontSize: 20, fontWeight: '800', letterSpacing: 1 } }} />
      <Tabs.Screen name="services" options={{ title: 'Servicii', tabBarIcon: function({ focused }) { return <Icon name={focused ? 'construct' : 'construct-outline'} focused={focused} />; }, headerTitle: 'Service-uri Auto' }} />
      <Tabs.Screen name="favorites" options={{ title: 'Favorite', tabBarIcon: function({ focused }) { return <Icon name={focused ? 'heart' : 'heart-outline'} focused={focused} />; }, headerTitle: 'Favorite' }} />
      <Tabs.Screen name="cars" options={{ title: 'Masini', tabBarIcon: function({ focused }) { return <Icon name={focused ? 'car-sport' : 'car-sport-outline'} focused={focused} />; }, headerTitle: 'Masinile Mele' }} />
      <Tabs.Screen name="profile" options={{ title: 'Profil', tabBarIcon: function({ focused }) { return <Icon name={focused ? 'person' : 'person-outline'} focused={focused} />; }, headerTitle: 'Contul Meu' }} />
    </Tabs>
  );
}
