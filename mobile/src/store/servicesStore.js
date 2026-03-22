import { create } from 'zustand';
import { servicesApi, favoritesApi } from '../api/endpoints';

export var useServicesStore = create(function(set, get) {
  return {
    services: [],
    featured: [],
    total: 0,
    filters: { q: '', city: '', category: '', min_rating: '', price_min: '', price_max: '', sort: '', limit: 20 },
    isLoading: false,
    isRefreshing: false,
    error: null,

    loadServices: async function(refresh) {
      var filters = get().filters;
      var clean = {};
      Object.keys(filters).forEach(function(k) { if (filters[k] !== '') clean[k] = filters[k]; });
      if (refresh) set({ isRefreshing: true, error: null });
      else set({ isLoading: true, error: null });
      try {
        var res = await servicesApi.list(clean);
        set({ services: res.data.results || [], total: res.data.count || 0, isLoading: false, isRefreshing: false });
      } catch (err) {
        set({ error: err.message, isLoading: false, isRefreshing: false });
      }
    },

    loadFeatured: async function() {
      try {
        var res = await servicesApi.list({ sort: 'rating', limit: 6 });
        set({ featured: res.data.results || [] });
      } catch (e) {}
    },

    setFilter: function(key, value) {
      set(function(s) { return { filters: Object.assign({}, s.filters, { [key]: value }) }; });
      get().loadServices();
    },

    applyFilters: function(newFilters) {
      set(function(s) { return { filters: Object.assign({}, s.filters, newFilters) }; });
      get().loadServices();
    },

    resetFilters: function() {
      set({ filters: { q: '', city: '', category: '', min_rating: '', price_min: '', price_max: '', sort: '', limit: 20 } });
      get().loadServices();
    },

    toggleFavorite: async function(slug) {
      try {
        var res = await servicesApi.toggleFavorite(slug);
        var isFav = res.data.is_favorited;
        set(function(s) {
          return {
            services: s.services.map(function(sv) {
              return sv.slug === slug ? Object.assign({}, sv, { is_favorited: isFav }) : sv;
            }),
            featured: s.featured.map(function(sv) {
              return sv.slug === slug ? Object.assign({}, sv, { is_favorited: isFav }) : sv;
            }),
          };
        });
      } catch (e) {}
    },

    clearError: function() { set({ error: null }); },
  };
});
