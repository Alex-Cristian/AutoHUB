# 🚗 AutoHub — Marketplace Service Auto

Marketplace Django pentru service-uri auto din România.

## Stack
- **Backend**: Django 5, Python 3.11+
- **DB**: SQLite (dev)
- **Frontend**: Bootstrap 5 + Django Templates
- **Design**: Temă dark industrială, roșu/negru

## Structură proiect

```
autohub/
├── autohub/           # Settings, URLs principale
├── core/              # Landing page, context processors
├── accounts/          # Auth: login, register, profil
├── services/          # Models + views service-uri, categorii, API JSON
│   ├── management/
│   │   └── commands/
│   │       └── seed_autohub.py   ← seed data
│   ├── models.py      ← ServiceCategory, ServiceCenter, ServiceItem, Review, Favorite
│   ├── views.py       ← list, detail, categories, favorite toggle
│   ├── api_views.py   ← GET /api/services/ (JsonResponse)
│   └── admin.py       ← Admin complet cu inline-uri
├── bookings/          # Programări
│   ├── models.py      ← Booking cu validare dată
│   ├── forms.py       ← BookingForm cu validări
│   ├── views.py       ← create, success, my_bookings
│   └── admin.py       ← Admin cu status badge + actions
└── templates/
    ├── base.html              ← Layout + navbar
    ├── core/home.html         ← Landing page
    ├── services/
    │   ├── categories.html    ← Grid 6 categorii
    │   ├── service_list.html  ← Filtre + listare + map placeholder
    │   └── service_detail.html← Profil + servicii + reviews
    ├── bookings/
    │   ├── booking_create.html← Form programare
    │   ├── booking_success.html
    │   └── my_bookings.html
    └── accounts/
        ├── login.html
        ├── register.html
        └── profile.html
```

## E) Instalare și rulare

### 1. Clonare / dezarhivare proiect

```bash
cd autohub/
```

### 2. Creare mediu virtual

```bash
python3 -m venv venv
source venv/bin/activate        # Linux/Mac
# SAU
venv\Scripts\activate           # Windows
```

### 3. Instalare dependențe

```bash
pip install -r requirements.txt
```

### 4. Migrații

```bash
python manage.py makemigrations core accounts services bookings
python manage.py migrate
```

### 5. Seed data (30+ service-uri, 6 categorii, recenzii mock)

```bash
python manage.py seed_autohub
```

Output așteptat:
```
✅ Seed finalizat cu succes!
  📂 Categorii:  6
  🏢 Service-uri: 30
  🔧 Servicii:   ~220
  ⭐ Recenzii:   ~60
  👤 Utilizatori: 9
```

### 6. Pornire server

```bash
python manage.py runserver
```

**Aplicație**: http://127.0.0.1:8000/  
**Admin**: http://127.0.0.1:8000/admin/ — `admin / admin123`

---

## Rute principale

| URL | Descriere |
|-----|-----------|
| `/` | Landing page |
| `/services/` | Listare cu filtre + sortare |
| `/services/categorii/` | Grid categorii |
| `/services/<slug>/` | Detalii service |
| `/bookings/programare/<slug>/` | Form programare |
| `/bookings/programarile-mele/` | Programările mele (auth) |
| `/accounts/login/` | Autentificare |
| `/accounts/register/` | Înregistrare |
| `/accounts/profil/` | Profil + favorite |
| `/api/services/` | API JSON filtrare |
| `/admin/` | Django Admin |

## API JSON

```
GET /api/services/?city=cluj-napoca&category=mecanica&min_rating=4&price_min=50&price_max=500&limit=20
```

Răspuns:
```json
{
  "count": 3,
  "results": [
    {
      "id": 8,
      "name": "AutoService Cluj Premium",
      "city": "cluj-napoca",
      "city_display": "Cluj-Napoca",
      "address": "Calea Turzii 178",
      "phone": "0264 100 200",
      "category": "Mecanică",
      "category_slug": "mecanica",
      "rating": 4.7,
      "review_count": 3,
      "price_range": "80–1800 RON",
      "availability": "Lun-Vin: 08:00-18:00, Sam: 09:00-14:00",
      "is_featured": true,
      "url": "/services/autoservice-cluj-premium/"
    }
  ]
}
```

## Filtre disponibile (query params)

| Param | Descriere | Exemplu |
|-------|-----------|---------|
| `q` | Căutare text | `q=revizie` |
| `city` | Slug oraș | `city=bucuresti` |
| `category` | Slug categorie | `category=detailing` |
| `min_rating` | Rating minim | `min_rating=4` |
| `price_min` | Preț minim | `price_min=100` |
| `price_max` | Preț maxim | `price_max=500` |
| `sort` | Sortare | `sort=rating` \| `price_asc` \| `price_desc` \| `reviews` \| `name` |

## Categorii disponibile

| Slug | Categorie |
|------|-----------|
| `detailing` | ✨ Detailing |
| `mecanica` | 🔧 Mecanică |
| `electrica` | ⚡ Electrică |
| `tractari` | 🚛 Tractări |
| `vulcanizari` | 🛞 Vulcanizări |
| `tinichigerie` | 🔨 Tinichigerie / Vopsitorie |

## Orașe disponibile

București, Cluj-Napoca, Timișoara, Iași, Brașov, Constanța, Craiova, Sibiu, Ploiești

## Funcționalități implementate

- [x] Landing page cu hero, search, categorii, "Cum funcționează"
- [x] Pagina categorii (grid 6)
- [x] Listare service-uri cu filtre server-side (categorie, oraș, rating, preț)
- [x] Sortare (rating, recenzii, preț asc/desc, nume)
- [x] Detalii service: profil, servicii + prețuri, rating breakdown, reviews
- [x] Buton Favorite (toggle, doar pentru autentificați)
- [x] Formular programare cu validare (dată nu în trecut, an mașină valid)
- [x] Programare legată de cont sau guest
- [x] "Programările mele" pentru utilizatori autentificați
- [x] Auth complet: login, register, logout, profil
- [x] Profil cu programări recente și favorite
- [x] API JSON `/api/services/` cu filtre
- [x] Admin complet: inline ServiceItem, search, filtre, actions
- [x] Seed command idempotent cu 30 service-uri
- [x] Map placeholder (pregătit pentru Google Maps / Leaflet)
