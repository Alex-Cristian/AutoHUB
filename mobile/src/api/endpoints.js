import api from './client';

export var authApi = {
  login:    function(data)   { return api.post('/api/auth/login/', data); },
  register: function(data)   { return api.post('/api/auth/register/', data); },
  profile:  function()       { return api.get('/api/profile/'); },
};

export var servicesApi = {
  list:     function(params) { return api.get('/api/services/', { params: params || {} }); },
  detail:   function(slug)   { return api.get('/api/services/' + slug + '/'); },
  nearby:   function(lat, lng, params) {
    var p = Object.assign({ lat: lat, lng: lng }, params || {});
    return api.get('/api/services/nearby/', { params: p });
  },
  toggleFavorite: function(slug) { return api.post('/api/services/' + slug + '/favorite/'); },
  addReview: function(slug, data) { return api.post('/api/services/' + slug + '/review/', data); },
};

export var categoriesApi = {
  list: function() { return api.get('/api/categories/'); },
};

export var favoritesApi = {
  list: function() { return api.get('/api/favorites/'); },
};

export var carsApi = {
  list:          function()           { return api.get('/api/cars/'); },
  create:        function(data)       { return api.post('/api/cars/', data); },
  update:        function(id, data)   { return api.put('/api/cars/' + id + '/', data); },
  remove:        function(id)         { return api.delete('/api/cars/' + id + '/'); },
  updateExpiry:  function(id, data)   { return api.put('/api/cars/' + id + '/expiry/', data); },
};

export var bookingsApi = {
  myBookings: function() { return api.get('/api/my-bookings/'); },
  slots:      function(slug, params) { return api.get('/bookings/programare/' + slug + '/sloturi/', { params: params }); },
  duration:   function(slug, params) { return api.get('/bookings/programare/' + slug + '/durata/', { params: params }); },
};

export var ownerApi = {
  dashboard:     function()         { return api.get('/api/owner/dashboard/'); },
  bookings:      function(params)   { return api.get('/api/owner/bookings/', { params: params || {} }); },
  updateBooking: function(id, data) { return api.patch('/api/owner/bookings/' + id + '/', data); },
};
