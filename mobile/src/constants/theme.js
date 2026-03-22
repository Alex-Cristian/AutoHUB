export const COLORS = {
  bg: '#0A0A0A', bgCard: '#141414', bgInput: '#1C1C1C', bgSurface: '#1A1A1A',
  primary: '#E63030', primaryDark: '#B32020',
  textPrimary: '#F0F0F0', textSecondary: '#8A8A8A', textMuted: '#555555',
  border: '#2A2A2A', divider: '#222222',
  success: '#22C55E', warning: '#F59E0B', error: '#EF4444', info: '#3B82F6', star: '#F59E0B',
};
export const FONTS = { xs: 11, sm: 13, md: 15, lg: 17, xl: 20, xxl: 24, xxxl: 30 };
export const RADIUS = { sm: 6, md: 10, lg: 16, xl: 24, full: 999 };
export const SPACING = { xs: 4, sm: 8, md: 16, lg: 24, xl: 32, xxl: 48 };

export const STATUS_CONFIG = {
  pending:     { color: '#F59E0B', label: 'In asteptare',   icon: 'time-outline' },
  quoted:      { color: '#3B82F6', label: 'Oferta trimisa', icon: 'document-text-outline' },
  confirmed:   { color: '#22C55E', label: 'Confirmata',     icon: 'checkmark-circle-outline' },
  in_progress: { color: '#8B5CF6', label: 'In lucru',       icon: 'construct-outline' },
  done:        { color: '#6B7280', label: 'Finalizata',      icon: 'checkmark-done-outline' },
  cancelled:   { color: '#EF4444', label: 'Anulata',        icon: 'close-circle-outline' },
};

export const CITY_CHOICES = [
  { value: '', label: 'Toate orasele' },
  { value: 'bucuresti', label: 'Bucuresti' },
  { value: 'cluj-napoca', label: 'Cluj-Napoca' },
  { value: 'timisoara', label: 'Timisoara' },
  { value: 'iasi', label: 'Iasi' },
  { value: 'brasov', label: 'Brasov' },
  { value: 'constanta', label: 'Constanta' },
  { value: 'craiova', label: 'Craiova' },
  { value: 'ploiesti', label: 'Ploiesti' },
  { value: 'oradea', label: 'Oradea' },
  { value: 'sibiu', label: 'Sibiu' },
];

export const FUEL_CHOICES = [
  { value: 'benzina', label: 'Benzina' },
  { value: 'motorina', label: 'Motorina' },
  { value: 'hibrid', label: 'Hibrid' },
  { value: 'electric', label: 'Electric' },
  { value: 'gpl', label: 'GPL' },
];

export const CATEGORIES = [
  { slug: 'detailing',    label: 'Detailing',    icon: 'sparkles',   color: '#E63030' },
  { slug: 'mecanica',     label: 'Mecanica',     icon: 'construct',  color: '#3B82F6' },
  { slug: 'electrica',    label: 'Electrica',    icon: 'flash',      color: '#F59E0B' },
  { slug: 'tractari',     label: 'Tractari',     icon: 'car',        color: '#22C55E' },
  { slug: 'vulcanizari',  label: 'Vulcanizari',  icon: 'ellipse',    color: '#8B5CF6' },
  { slug: 'tinichigerie', label: 'Tinichigerie', icon: 'hammer',     color: '#EC4899' },
];
