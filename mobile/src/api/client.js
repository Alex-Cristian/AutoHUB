import axios from 'axios';
import * as SecureStore from 'expo-secure-store';

// ⚠️ Schimba cu URL-ul tau de pe Render
export const BASE_URL = 'https://autohub-vouo.onrender.com';

const KEYS = { ACCESS: 'autoemg_access', REFRESH: 'autoemg_refresh' };

export const tokenStorage = {
  setAccess:  function(t) { return SecureStore.setItemAsync(KEYS.ACCESS, t); },
  setRefresh: function(t) { return SecureStore.setItemAsync(KEYS.REFRESH, t); },
  getAccess:  function()  { return SecureStore.getItemAsync(KEYS.ACCESS); },
  getRefresh: function()  { return SecureStore.getItemAsync(KEYS.REFRESH); },
  clearAll: async function() {
    await SecureStore.deleteItemAsync(KEYS.ACCESS);
    await SecureStore.deleteItemAsync(KEYS.REFRESH);
  },
};

var api = axios.create({
  baseURL: BASE_URL,
  timeout: 20000,
  headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
});

api.interceptors.request.use(
  async function(config) {
    var token = await tokenStorage.getAccess();
    if (token) config.headers['Authorization'] = 'Bearer ' + token;
    return config;
  },
  function(error) { return Promise.reject(error); }
);

api.interceptors.response.use(
  function(response) { return response; },
  async function(error) {
    var original = error.config;
    if (error.response && error.response.status === 401 && !original._retry) {
      original._retry = true;
      try {
        var refresh = await tokenStorage.getRefresh();
        if (refresh) {
          var res = await axios.post(BASE_URL + '/api/auth/refresh/', { refresh: refresh });
          await tokenStorage.setAccess(res.data.access);
          original.headers['Authorization'] = 'Bearer ' + res.data.access;
          return api(original);
        }
      } catch (e) {
        await tokenStorage.clearAll();
      }
    }
    var d = error.response ? error.response.data : null;
    var msg = (d && (d.detail || d.error || d.message)) || error.message || 'Eroare de retea.';
    return Promise.reject(new Error(typeof msg === 'string' ? msg : 'Eroare necunoscuta.'));
  }
);

export default api;
