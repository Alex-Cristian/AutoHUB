# AutoEMG Mobile — v3 Final

Aplicatie mobila completa pentru marketplace-ul AutoEMG.

## Stack
- React Native + Expo SDK 54
- Expo Router (navigare)
- Zustand (state management)
- Axios + JWT (autentificare)
- expo-secure-store (stocare sigura tokene)

## Ecrane
| Ecran | Ruta |
|-------|------|
| Acasa | `/(tabs)/` |
| Servicii + Filtre | `/(tabs)/services` |
| Favorite | `/(tabs)/favorites` |
| Masinile Mele | `/(tabs)/cars` |
| Profil + Programari | `/(tabs)/profile` |
| Detalii Service | `/service/[slug]` |
| Programare (nativ) | `/booking/[slug]` |
| Login | `/auth/login` |
| Register | `/auth/register` |
| Adauga Masina | `/cars/add` |
| Editeaza Masina | `/cars/[id]` |
| Expirari Documente | `/cars/expiry/[id]` |

## Setup

### 1. Instaleaza dependentele
```bash
npm install --legacy-peer-deps
```

### 2. Schimba BASE_URL
In `src/api/client.js`:
```js
export const BASE_URL = 'https://autohub-vouo.onrender.com';
```

### 3. Porneste
```bash
npx expo start --tunnel -c
```

## Backend Django
Urmareste instructiunile din `django_api/INSTRUCTIUNI.txt` pentru setup-ul API-ului.
