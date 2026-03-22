import { create } from 'zustand';
import * as SecureStore from 'expo-secure-store';
import { authApi } from '../api/endpoints';
import { tokenStorage } from '../api/client';

var USER_KEY = 'autoemg_user';

export var useAuthStore = create(function(set, get) {
  return {
    user: null,
    isLoggedIn: false,
    isLoading: false,
    error: null,

    hydrate: async function() {
      try {
        var json = await SecureStore.getItemAsync(USER_KEY);
        var access = await tokenStorage.getAccess();
        if (json && access) {
          set({ user: JSON.parse(json), isLoggedIn: true });
        }
      } catch (e) {}
    },

    login: async function(username, password) {
      set({ isLoading: true, error: null });
      try {
        var res = await authApi.login({ username: username, password: password });
        var access = res.data.access;
        var refresh = res.data.refresh;
        var user = res.data.user;
        await tokenStorage.setAccess(access);
        await tokenStorage.setRefresh(refresh);
        await SecureStore.setItemAsync(USER_KEY, JSON.stringify(user));
        set({ user: user, isLoggedIn: true, isLoading: false, error: null });
        return { success: true };
      } catch (err) {
        var msg = err.message || 'Date incorecte.';
        set({ isLoading: false, error: msg });
        return { success: false, error: msg };
      }
    },

    register: async function(data) {
      set({ isLoading: true, error: null });
      try {
        var res = await authApi.register(data);
        await tokenStorage.setAccess(res.data.access);
        await tokenStorage.setRefresh(res.data.refresh);
        await SecureStore.setItemAsync(USER_KEY, JSON.stringify(res.data.user));
        set({ user: res.data.user, isLoggedIn: true, isLoading: false, error: null });
        return { success: true };
      } catch (err) {
        var msg = err.message || 'Eroare la inregistrare.';
        set({ isLoading: false, error: msg });
        return { success: false, error: msg };
      }
    },

    logout: async function() {
      await tokenStorage.clearAll();
      await SecureStore.deleteItemAsync(USER_KEY);
      set({ user: null, isLoggedIn: false, error: null });
    },

    clearError: function() { set({ error: null }); },
  };
});
