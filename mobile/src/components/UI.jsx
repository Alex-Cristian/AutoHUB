import React, { useState } from 'react';
import { View, Text, TextInput, TouchableOpacity, ActivityIndicator, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { COLORS, FONTS, RADIUS, SPACING } from '../constants/theme';

// ─── Button ───────────────────────────────────────────────────────────────────
export function Button({ label, onPress, variant, size, loading, disabled, icon, style }) {
  var v = variant || 'primary';
  var s = size || 'md';
  var bg = { primary: COLORS.primary, secondary: COLORS.bgInput, outline: 'transparent', danger: COLORS.error }[v];
  var textColor = v === 'secondary' ? COLORS.textPrimary : '#fff';
  var height = { sm: 38, md: 48, lg: 56 }[s];
  var fontSize = { sm: FONTS.sm, md: FONTS.md, lg: FONTS.lg }[s];
  return (
    <TouchableOpacity
      style={[
        btnS.base, { backgroundColor: bg, height: height, borderRadius: RADIUS.md },
        v === 'outline' && { borderWidth: 1, borderColor: COLORS.primary },
        (disabled || loading) && { opacity: 0.5 }, style,
      ]}
      onPress={onPress} disabled={!!disabled || !!loading} activeOpacity={0.8}
    >
      {loading
        ? <ActivityIndicator color={textColor} size="small" />
        : <>
            {icon && <Ionicons name={icon} size={fontSize + 2} color={textColor} />}
            <Text style={[btnS.label, { color: textColor, fontSize: fontSize }]}>{label}</Text>
          </>
      }
    </TouchableOpacity>
  );
}
var btnS = StyleSheet.create({
  base: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, paddingHorizontal: SPACING.lg },
  label: { fontWeight: '700' },
});

// ─── Input ────────────────────────────────────────────────────────────────────
export function Input({ label, placeholder, value, onChangeText, secureTextEntry, keyboardType, autoCapitalize, error, icon, multiline, numberOfLines, editable }) {
  var [showPass, setShowPass] = useState(false);
  var isEditable = editable !== false;
  return (
    <View style={inpS.wrapper}>
      {label && <Text style={inpS.label}>{label}</Text>}
      <View style={[inpS.box, error && inpS.boxError, !isEditable && inpS.boxDisabled]}>
        {icon && <Ionicons name={icon} size={16} color={COLORS.textMuted} />}
        <TextInput
          style={[inpS.input, multiline && { height: (numberOfLines || 3) * 24, textAlignVertical: 'top' }]}
          placeholder={placeholder} placeholderTextColor={COLORS.textMuted}
          value={value} onChangeText={onChangeText}
          secureTextEntry={!!secureTextEntry && !showPass}
          keyboardType={keyboardType || 'default'}
          autoCapitalize={autoCapitalize || 'none'}
          selectionColor={COLORS.primary}
          multiline={!!multiline} numberOfLines={numberOfLines} editable={isEditable}
        />
        {secureTextEntry && (
          <TouchableOpacity onPress={function() { setShowPass(function(p) { return !p; }); }}>
            <Ionicons name={showPass ? 'eye-off-outline' : 'eye-outline'} size={18} color={COLORS.textMuted} />
          </TouchableOpacity>
        )}
      </View>
      {error && <Text style={inpS.error}>{error}</Text>}
    </View>
  );
}
var inpS = StyleSheet.create({
  wrapper: { gap: 4 },
  label: { fontSize: FONTS.xs, fontWeight: '700', color: COLORS.textSecondary, textTransform: 'uppercase', letterSpacing: 0.8 },
  box: { flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: COLORS.bgInput, borderRadius: RADIUS.md, paddingHorizontal: SPACING.md, minHeight: 48, borderWidth: 1, borderColor: COLORS.border },
  boxError: { borderColor: COLORS.error },
  boxDisabled: { opacity: 0.6 },
  input: { flex: 1, color: COLORS.textPrimary, fontSize: FONTS.md },
  error: { fontSize: FONTS.xs, color: COLORS.error },
});

// ─── Card ─────────────────────────────────────────────────────────────────────
export function Card({ children, style }) {
  return <View style={[{ backgroundColor: COLORS.bgCard, borderRadius: RADIUS.lg, padding: SPACING.md, borderWidth: 1, borderColor: COLORS.border }, style]}>{children}</View>;
}

// ─── Badge ────────────────────────────────────────────────────────────────────
export function Badge({ label, color, small }) {
  return (
    <View style={{ paddingHorizontal: 8, paddingVertical: 3, borderRadius: RADIUS.full, borderWidth: 1, borderColor: color + '40', backgroundColor: color + '18' }}>
      <Text style={{ fontSize: small ? 10 : FONTS.xs, fontWeight: '700', color: color }}>{label}</Text>
    </View>
  );
}

// ─── Skeleton ─────────────────────────────────────────────────────────────────
export function Skeleton({ width, height, style }) {
  return <View style={[{ width: width || '100%', height: height || 16, backgroundColor: COLORS.bgSurface, borderRadius: RADIUS.sm }, style]} />;
}

export function SkeletonCard() {
  return (
    <View style={{ backgroundColor: COLORS.bgCard, borderRadius: RADIUS.lg, padding: SPACING.md, borderWidth: 1, borderColor: COLORS.border, gap: SPACING.sm, marginBottom: SPACING.sm }}>
      <View style={{ flexDirection: 'row', gap: SPACING.sm }}>
        <Skeleton width={48} height={48} style={{ borderRadius: RADIUS.md }} />
        <View style={{ flex: 1, gap: 6 }}>
          <Skeleton height={16} width="70%" />
          <Skeleton height={12} width="40%" />
        </View>
      </View>
      <Skeleton height={12} />
      <Skeleton height={12} width="80%" />
    </View>
  );
}

// ─── Empty State ──────────────────────────────────────────────────────────────
export function EmptyState({ icon, title, subtitle, action, actionLabel }) {
  return (
    <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', gap: SPACING.sm, padding: SPACING.xl }}>
      <Ionicons name={icon} size={64} color={COLORS.textMuted} />
      <Text style={{ fontSize: FONTS.xl, fontWeight: '700', color: COLORS.textPrimary, textAlign: 'center' }}>{title}</Text>
      {subtitle && <Text style={{ fontSize: FONTS.md, color: COLORS.textSecondary, textAlign: 'center' }}>{subtitle}</Text>}
      {action && actionLabel && <Button label={actionLabel} onPress={action} style={{ marginTop: SPACING.sm }} />}
    </View>
  );
}

// ─── Error State ──────────────────────────────────────────────────────────────
export function ErrorState({ message, onRetry }) {
  return (
    <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', gap: SPACING.sm, padding: SPACING.xl }}>
      <Ionicons name="alert-circle-outline" size={64} color={COLORS.error} />
      <Text style={{ fontSize: FONTS.xl, fontWeight: '700', color: COLORS.textPrimary }}>Ceva nu a mers</Text>
      <Text style={{ fontSize: FONTS.md, color: COLORS.textSecondary, textAlign: 'center' }}>{message}</Text>
      {onRetry && <Button label="Incearca din nou" onPress={onRetry} style={{ marginTop: SPACING.sm }} />}
    </View>
  );
}

// ─── Section Header ───────────────────────────────────────────────────────────
export function SectionHeader({ title, action, actionLabel }) {
  return (
    <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: SPACING.sm }}>
      <Text style={{ fontSize: FONTS.lg, fontWeight: '700', color: COLORS.textPrimary }}>{title}</Text>
      {action && actionLabel && (
        <TouchableOpacity onPress={action}>
          <Text style={{ fontSize: FONTS.sm, color: COLORS.primary, fontWeight: '600' }}>{actionLabel} →</Text>
        </TouchableOpacity>
      )}
    </View>
  );
}

// ─── Stars ────────────────────────────────────────────────────────────────────
export function Stars({ rating, size }) {
  var s = size || 14;
  var filled = Math.round(rating || 0);
  return (
    <View style={{ flexDirection: 'row', gap: 2 }}>
      {[1,2,3,4,5].map(function(i) {
        return <Ionicons key={i} name={i <= filled ? 'star' : 'star-outline'} size={s} color={i <= filled ? COLORS.star : COLORS.textMuted} />;
      })}
    </View>
  );
}

// ─── Chip ─────────────────────────────────────────────────────────────────────
export function Chip({ label, active, onPress }) {
  return (
    <TouchableOpacity
      style={{ paddingHorizontal: 12, paddingVertical: 6, borderRadius: RADIUS.full, backgroundColor: active ? COLORS.primary : COLORS.bgInput, borderWidth: 1, borderColor: active ? COLORS.primary : COLORS.border }}
      onPress={onPress} activeOpacity={0.7}
    >
      <Text style={{ fontSize: FONTS.sm, color: active ? '#fff' : COLORS.textSecondary, fontWeight: active ? '700' : '500' }}>{label}</Text>
    </TouchableOpacity>
  );
}
