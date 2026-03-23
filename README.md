# AutoEMG / AutoHub

Platformă Django pentru relația dintre clienți și service-uri auto: căutare service, programări online, calendar operațional, fișe de lucru, dosar digital al mașinii, inventar piese, documente și notificări.

## Ce problemă rezolvă

AutoHub transformă interacțiunea clasică dintre client și service într-un flux clar și urmărit:

- clientul găsește un service potrivit, rezervă online și vede statusul lucrării;
- service-ul își organizează programările, lucrările, mecanicii, piesele și documentele dintr-un singur loc;
- istoricul mașinii rămâne centralizat și util pe termen lung.

## Pentru cine este

- clienți care vor programare rapidă, transparență și istoric tehnic clar;
- service-uri auto care au nevoie de calendar, workflow operațional și evidență simplă;
- dezvoltatori care vor o bază reală pentru un marketplace / CRM auto vertical.

## Funcționalități principale

### Client

- înregistrare, autentificare, verificare email și acceptare documente legale;
- căutare service-uri cu filtre, rating și pagini publice detaliate;
- programare online cu alegere interval și durată estimată;
- listă „Programările mele” cu status, cost estimat/final, recomandări și fișiere;
- secțiune „Mașinile mele” și istoric auto;
- remindere pentru acte auto și revizii;
- recenzii și favorite.

### Service

- dashboard operațional cu programările zilei, lucrări active și alerte;
- calendar pe zi / săptămână / lună cu filtre și intervale blocate;
- detaliu de programare extins cu timeline, fișă de lucru și jurnal;
- fișe de lucru cu operațiuni, recomandări, costuri și piese consumate;
- inventar piese cu stoc minim, mișcări de stoc și consum pe lucrare;
- profiluri clienți și dosar digital pe mașină;
- facturi și documente legate de programare și lucrare;
- notificări interne, email și SMS unde integrarea externă este configurată.

### Capabilități pregătite pentru integrare externă

- Cloudinary pentru media;
- Twilio pentru SMS;
- OpenAI pentru fluxuri de asistență AI / scanare documente;
- Render pentru deploy web + cron jobs.

## Fluxul principal întărit în proiect

1. Clientul caută service-ul și trimite programarea.
2. Service-ul confirmă, ofertează sau reprogramează.
3. Programarea intră în calendarul operațional.
4. Din programare se creează fișa lucrării.
5. Service-ul adaugă operațiuni, recomandări, piese și costuri.
6. Clientul vede statusurile și informațiile relevante.
7. Lucrarea finalizată intră în dosarul auto și poate genera factură.

## Module și arhitectură

### Aplicații Django

- `core`:
  pagini generale, context global, middleware și servicii comune
- `accounts`:
  auth, profil utilizator, mașini, acte auto, verificare email
- `services`:
  service-uri, dashboard, calendar, mecanici, review-uri, favorite, inventar, job cards
- `bookings`:
  programări, statusuri, atașamente, activitate și remindere
- `invoices`:
  facturi, linii de factură și legătura cu programările

### Zone importante în cod

- `services/business.py`:
  logică de business pentru fișe de lucru, consum piese și dosar auto
- `services/reporting.py`:
  dashboard și rapoarte
- `templates/services/`:
  interfața service-ului
- `templates/bookings/`:
  experiența clientului pentru programări
- `services/management/commands/seed_autohub.py`:
  seed demo pentru prezentare și testare

## Stack tehnologic

- Python 3.11+
- Django 5.2
- Django Templates + Bootstrap 5
- SQLite în local, `dj-database-url` pentru Postgres în deploy
- WhiteNoise pentru fișiere statice
- Cloudinary pentru media
- WeasyPrint / ReportLab pentru PDF-uri
- Twilio pentru SMS
- OpenAI SDK pentru fluxuri AI
- Render pentru hosting și joburi cron

## Cerințe

- Python 3.11 sau mai nou
- pip
- mediu virtual recomandat

## Instalare locală

### 1. Clonează proiectul

```bash
git clone <repo-url>
cd autohub
```

### 2. Creează și activează mediul virtual

```bash
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
```

macOS / Linux:

```bash
source .venv/bin/activate
```

### 3. Instalează dependențele

```bash
pip install -r requirements.txt
```

### 4. Configurează fișierul `.env`

Creează un fișier `.env` în rădăcina proiectului.

Exemplu minim pentru local:

```env
DJANGO_SECRET_KEY=django-insecure-change-me
DEBUG=True
ALLOWED_HOSTS=127.0.0.1,localhost
CSRF_TRUSTED_ORIGINS=http://127.0.0.1:8000,http://localhost:8000
USE_CLOUDINARY=False
SITE_BASE_URL=http://127.0.0.1:8000
DEFAULT_FROM_EMAIL=AutoEMG <admin@autoemg.local>
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4.1-mini
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_PHONE_NUMBER=
TWILIO_SMS_ENABLED=False
LEGAL_DOCUMENTS_VERSION=2026-03-19
```

### 5. Rulează migrațiile

```bash
python manage.py migrate
```

### 6. Creează un superuser

```bash
python manage.py createsuperuser
```

### 7. Pornește serverul

```bash
python manage.py runserver
```

Aplicația va fi disponibilă la `http://127.0.0.1:8000/`.

## Seed / date demo

Comanda de seed creează date credibile pentru prezentare și testare:

- categorii și service-uri în mai multe orașe;
- garaje și servicii oferite;
- mecanici;
- piese în stoc;
- programări cu statusuri variate;
- fișe de lucru, recomandări și consum de piese;
- facturi demo;
- recenzii și imagini;
- conturi demo pentru client și service.

Rulare:

```bash
python manage.py seed_autohub
```

La final vei avea și conturi demo utile:

- `client_demo / client1234`
- `service_demo / service1234`
- `admin / admin123` dacă nu exista deja

Notă:
seed-ul recreează datele demo operaționale. Nu îl rula pe o bază de producție.

## Comenzi utile

```bash
python manage.py test
python manage.py check
python manage.py send_booking_reminders
python manage.py notify_stale_pending_bookings
python manage.py send_expiry_email_reminders
```

## Media și Cloudinary

Aplicația poate funcționa în două moduri:

- local, cu `FileSystemStorage` dacă `USE_CLOUDINARY=False`;
- cloud, cu Cloudinary dacă `USE_CLOUDINARY=True` și cheile sunt setate.

Variabile relevante:

```env
USE_CLOUDINARY=True
CLOUDINARY_CLOUD_NAME=
CLOUDINARY_API_KEY=
CLOUDINARY_API_SECRET=
```

## Email și SMS

### Email

Pentru local poți folosi backend-ul de consolă.

Pentru SMTP:

```env
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=
EMAIL_USE_TLS=True
EMAIL_USE_SSL=False
EMAIL_TIMEOUT=20
DEFAULT_FROM_EMAIL=AutoEMG <no-reply@autoemg.com>
```

### SMS / Twilio

```env
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_PHONE_NUMBER=
TWILIO_SMS_ENABLED=True
```

Dacă aceste variabile nu sunt configurate, proiectul rămâne funcțional și folosește fallback-ul disponibil în interfață / email.

## AI și scanare documente

Proiectul are suport pentru fluxuri AI asistate, nu pentru salvare oarbă:

- utilizatorul încarcă documentul;
- sistemul propune date extrase;
- utilizatorul confirmă sau corectează;
- abia apoi datele se salvează.

Variabile utile:

```env
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4.1-mini
```

Dacă cheia nu este setată, proiectul trebuie considerat „pregătit pentru integrare”, nu complet activ pe partea AI.

## Deploy pe Render

Fișierul [`render.yaml`](/c:/Users/alexu/Desktop/autohub/render.yaml) include:

- un serviciu web pentru aplicația Django;
- un cron pentru reminderele de programări.

Flux de bază:

1. conectezi repository-ul în Render;
2. setezi variabilele de mediu;
3. Render rulează `pip install`, `collectstatic` și `migrate`;
4. aplicația pornește cu `gunicorn autohub.wsgi:application`.

Variabile importante pentru deploy:

- `DJANGO_SECRET_KEY`
- `DEBUG=False`
- `ALLOWED_HOSTS`
- `CSRF_TRUSTED_ORIGINS`
- `USE_CLOUDINARY`
- `CLOUDINARY_*`
- `EMAIL_*`
- `TWILIO_*`
- `SITE_BASE_URL`

## Structura proiectului

```text
autohub/
├── accounts/
├── autohub/
├── bookings/
├── core/
├── invoices/
├── services/
├── templates/
├── static/
├── media/
├── requirements.txt
├── render.yaml
└── manage.py
```

## Roluri și permisiuni

### Client

- poate vedea doar programările, mașinile și documentele proprii;
- poate accepta sau refuza ofertele primite;
- poate consulta istoricul auto și documentele asociate.

### Service owner

- vede doar datele service-ului pe care îl administrează;
- gestionează programări, calendar, mecanici, piese, lucrări și documente;
- poate actualiza statusuri și comunica cu clientul.

### Admin

- are acces complet prin Django Admin și prin fluxurile interne unde este permis explicit.

## Stare actuală a produsului

Zone mature în proiect:

- fluxul principal programare -> lucrare -> istoric;
- dashboard service și calendar operațional;
- inventar și mișcări de stoc;
- dosar auto și fișe de lucru;
- seed demo pentru prezentare;
- suită de teste pentru zonele critice existente.

## Known limitations

- integrarea AI depinde de chei externe și de configurarea providerului;
- SMS-urile reale necesită cont Twilio activ;
- unele documente financiare sunt potrivite pentru demo / flux intern, dar pot necesita adaptări fiscale înainte de producție;
- proiectul folosește încă template-uri Django clasice, nu un frontend SPA;
- seed-ul este orientat spre demo și testare, nu spre migrare de date reale.

## Future improvements

- workflow complet de ofertă / deviz separat de factură;
- upload și management mai avansat pentru documente fiscale;
- audit trail extins pe toate entitățile critice;
- rapoarte financiare și operaționale mai profunde;
- permisiuni mai granulare pentru echipă / mecanici / recepție;
- integrare cu furnizori de piese și disponibilitate în timp real.

## Roadmap scurt

- consolidarea completă a fluxului ofertă -> aprobare client -> facturare;
- extinderea modulelor de CRM service;
- îmbunătățirea validărilor pentru scanare documente și review-uri cu poze;
- mai multe automatizări pentru notificări și remindere.

## Capturi de ecran

Poți adăuga ușor imagini în această secțiune, de exemplu:

```md
![Dashboard service](docs/screenshots/dashboard-service.png)
![Calendar operațional](docs/screenshots/calendar-service.png)
![Programările clientului](docs/screenshots/client-bookings.png)
```

## Verificare rapidă după setup

După instalare, un flux minim recomandat este:

1. rulezi migrațiile;
2. rulezi `python manage.py seed_autohub`;
3. pornești serverul;
4. intri cu `service_demo / service1234`;
5. verifici dashboard-ul, calendarul, piesele și programările;
6. intri cu `client_demo / client1234` și verifici istoricul clientului.

## Licență / utilizare

Adaugă aici politica de licențiere a proiectului dacă vrei să îl publici sau să îl distribui.
