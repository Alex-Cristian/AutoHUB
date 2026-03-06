"""
Management command: python manage.py seed_autohub

Creează:
- 6 categorii
- 30+ service-uri în orașe din România
- 6-10 ServiceItem per service
- 1-3 Reviews per service (mock users)
- Idempotent: șterge datele existente și recreează
"""
import random
from pathlib import Path
from django.conf import settings
from django.core.files import File
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from PIL import Image, ImageDraw


CATEGORIES = [
    {
        'name': 'Detailing',
        'slug': 'detailing',
        'icon': '✨',
        'color': '#4cc9f0',
        'order': 1,
        'description': 'Curățare profesională interioară și exterioară, polish, ceruire și protecție caroserie.',
    },
    {
        'name': 'Mecanică',
        'slug': 'mecanica',
        'icon': '🔧',
        'color': '#e63946',
        'order': 2,
        'description': 'Revizie, schimb ulei, frâne, ambreiaj, distribuție și orice reparație mecanică.',
    },
    {
        'name': 'Electrică',
        'slug': 'electrica',
        'icon': '⚡',
        'color': '#f4a261',
        'order': 3,
        'description': 'Diagnosticare computer, instalații electrice, alternator, demaror, baterie.',
    },
    {
        'name': 'Tractări',
        'slug': 'tractari',
        'icon': '🚛',
        'color': '#2a9d8f',
        'order': 4,
        'description': 'Tractare auto 24/7, serviciu de urgență, transport autovehicule pe platforma.',
    },
    {
        'name': 'Vulcanizări',
        'slug': 'vulcanizari',
        'icon': '🛞',
        'color': '#457b9d',
        'order': 5,
        'description': 'Montare, echilibrare și reparare anvelope. Sezon vară și iarnă.',
    },
    {
        'name': 'Tinichigerie / Vopsitorie',
        'slug': 'tinichigerie',
        'icon': '🔨',
        'color': '#e9c46a',
        'order': 6,
        'description': 'Reparații caroserie, vopsitorie auto, îndreptat tabla, înlocuit piese caroserie.',
    },
]

SERVICE_ITEMS = {
    'detailing': [
        ('Spălare exterioară completă', 50, 120, 60),
        ('Detailing interior complet', 150, 300, 180),
        ('Polish un strat', 200, 400, 240),
        ('Polish profesional 2 straturi', 400, 700, 480),
        ('Ceruire carnauba', 100, 200, 90),
        ('Protecție ceramică', 800, 1500, 360),
        ('Curățare motor', 80, 150, 60),
        ('Ozonizare habitaclu', 60, 100, 45),
        ('Curățare tapițerie cu abur', 120, 250, 120),
        ('Recondiționare faruri', 100, 180, 90),
    ],
    'mecanica': [
        ('Revizie completă', 200, 500, 120),
        ('Schimb ulei + filtru', 80, 180, 45),
        ('Schimb plăcuțe frână față', 120, 250, 60),
        ('Schimb discuri frână față', 300, 600, 90),
        ('Schimb ambreiaj', 600, 1200, 240),
        ('Schimb kit distribuție', 800, 1800, 300),
        ('Schimb bujii', 80, 200, 45),
        ('Geometrie roți', 80, 150, 60),
        ('Schimb filtru habitaclu', 50, 100, 30),
        ('Diagnosticare', 80, 120, 30),
    ],
    'electrica': [
        ('Diagnosticare computer bord', 80, 150, 45),
        ('Schimb baterie', 200, 500, 30),
        ('Reparație alternator', 400, 800, 180),
        ('Reparație demaror', 300, 600, 120),
        ('Instalație audio / navigație', 200, 800, 180),
        ('Reparație senzori parcare', 150, 350, 90),
        ('Verificare sistem electric', 100, 200, 60),
        ('Schimb becuri faruri', 50, 150, 30),
        ('Reparație geamuri electrice', 150, 400, 120),
        ('Codare cheie / telecomandă', 100, 300, 60),
    ],
    'tractari': [
        ('Tractare autovehicul (0-30km)', 150, 250, None),
        ('Tractare autovehicul (30-100km)', 250, 500, None),
        ('Tractare pe platformă', 200, 600, None),
        ('Asistență rutieră 24/7', 100, 200, None),
        ('Pornire baterie descărcată', 50, 100, 30),
        ('Deblocare roată blocată', 80, 150, 60),
        ('Transport moto pe platformă', 100, 200, None),
        ('Tractare internațională', 500, 2000, None),
    ],
    'vulcanizari': [
        ('Montare anvelopă', 15, 30, 15),
        ('Echilibrare roată', 15, 25, 10),
        ('Reparație pană (petec la cald)', 30, 60, 30),
        ('Vulcanizare tubeless', 25, 50, 20),
        ('Sezon anvelope (4 roți)', 80, 140, 45),
        ('Schimb valvă', 10, 20, 10),
        ('Verificare presiune 4 roți', 10, 20, 15),
        ('Rodare anvelope noi', 15, 30, 20),
        ('Depozitare anvelope (sezon)', 100, 200, None),
    ],
    'tinichigerie': [
        ('Vopsire capotă', 400, 800, 480),
        ('Vopsire ușă', 350, 700, 360),
        ('Vopsire aripă', 300, 600, 300),
        ('Îndreptat tablă', 100, 400, 120),
        ('Reparație zgârietură', 50, 200, 60),
        ('Anticoroziv podea', 200, 500, 120),
        ('Înlocuit parbriz', 300, 800, 90),
        ('Înlocuit geam lateral', 200, 500, 60),
        ('Reparație bară față', 150, 400, 120),
        ('Grunduire + vopsire complet', 2000, 5000, 2400),
    ],
}

CENTERS_DATA = [
    # ---- BUCUREȘTI (7) ----
    {
        'name': 'AutoPro Detailing București',
        'category': 'detailing',
        'city': 'bucuresti',
        'address': 'Str. Calea Floreasca 45, Sector 1',
        'phone': '0721 100 200',
        'email': 'contact@autopro-detailing.ro',
        'schedule': 'Lun-Sam: 08:00-19:00',
        'description': 'Service de detailing premium în inima Bucureștiului. Folosim produse Gyeon și Koch Chemie pentru rezultate impecabile. Experiență de 10 ani, echipă specializată.',
        'featured': True,
        'lat': 44.4735, 'lng': 26.0938,
    },
    {
        'name': 'Garage Expert Mecanică',
        'category': 'mecanica',
        'city': 'bucuresti',
        'address': 'Bd. Theodor Pallady 12, Sector 3',
        'phone': '0730 200 300',
        'schedule': 'Lun-Vin: 07:30-18:30',
        'description': 'Service mecanic autorizat cu diagnosticare computerizată. Specialiști în motoare diesel și benzină. Garanție 12 luni pentru toate lucrările.',
        'featured': True,
        'lat': 44.4268, 'lng': 26.1693,
    },
    {
        'name': 'Electro Auto Titan',
        'category': 'electrica',
        'city': 'bucuresti',
        'address': 'Calea Vitan 78, Sector 3',
        'phone': '0745 300 400',
        'schedule': 'Lun-Vin: 08:00-18:00',
        'description': 'Specialiști în diagnosticare și reparații electrice auto. Echipamente BOSCH KTS. Rezolvăm orice defecțiune electrică, de la baterie la injecție.',
        'lat': 44.4095, 'lng': 26.1467,
    },
    {
        'name': 'Speed Vulcanizare 24/7',
        'category': 'vulcanizari',
        'city': 'bucuresti',
        'address': 'Șos. Colentina 134, Sector 2',
        'phone': '0722 400 500',
        'schedule': 'Non-stop 24/7',
        'description': 'Vulcanizare rapidă, non-stop. Montare și echilibrare anvelope pentru orice tip de vehicul. Depozitare sezonieră disponibilă. Suntem acolo când ai nevoie!',
        'lat': 44.4642, 'lng': 26.1389,
    },
    {
        'name': 'Caroserie & Vopsitorie Floreasca',
        'category': 'tinichigerie',
        'city': 'bucuresti',
        'address': 'Str. Aviator Popa Marin 5, Sector 1',
        'phone': '0756 500 600',
        'schedule': 'Lun-Vin: 08:00-17:00',
        'description': 'Tinichigerie și vopsitorie auto cu cabin de vopsit autorizată. Vopsele SIKKENS și GLASURIT. Reparații după accidente, recondiționare completă.',
        'featured': True,
        'lat': 44.4792, 'lng': 26.0876,
    },
    {
        'name': 'RapidTract București',
        'category': 'tractari',
        'city': 'bucuresti',
        'address': 'Str. Bdul Unirii 58, Sector 4',
        'phone': '0744 600 700',
        'schedule': 'Non-stop 24/7',
        'description': 'Serviciu de tractare și asistență rutieră non-stop în București și împrejurimi. Platforma modernă pentru orice tip de mașină. Răspuns în max 30 minute.',
        'lat': 44.4273, 'lng': 26.1030,
    },
    {
        'name': 'GlossWorks Detailing Premium',
        'category': 'detailing',
        'city': 'bucuresti',
        'address': 'Str. Turda 120, Sector 1',
        'phone': '0733 700 800',
        'schedule': 'Lun-Sam: 09:00-20:00',
        'description': 'Studio de detailing high-end specializat în protecție ceramică, PPF și polish profesional. Fiecare mașină tratată ca o operă de artă.',
        'lat': 44.4622, 'lng': 26.0749,
    },
    # ---- CLUJ-NAPOCA (5) ----
    {
        'name': 'AutoService Cluj Premium',
        'category': 'mecanica',
        'city': 'cluj-napoca',
        'address': 'Calea Turzii 178',
        'phone': '0264 100 200',
        'schedule': 'Lun-Vin: 08:00-18:00, Sam: 09:00-14:00',
        'description': 'Service mecanic multi-brand în Cluj. Diagnosticare avansată, echipă de 12 mecanici certificați. Programare online disponibilă. Suntem parteneri autorizați Dacia și Renault.',
        'featured': True,
        'lat': 46.7620, 'lng': 23.6100,
    },
    {
        'name': 'Electro Diagnoza Cluj',
        'category': 'electrica',
        'city': 'cluj-napoca',
        'address': 'Str. Fabricii 20',
        'phone': '0264 200 300',
        'schedule': 'Lun-Vin: 08:30-17:30',
        'description': 'Diagnosticare și reparații electrice complexe. Specialiști în mașini premium (BMW, Mercedes, Audi). Soft update și codări originale.',
        'lat': 46.7812, 'lng': 23.5997,
    },
    {
        'name': 'Detailing Cluj Studio',
        'category': 'detailing',
        'city': 'cluj-napoca',
        'address': 'Str. Dorobanților 45',
        'phone': '0264 300 400',
        'schedule': 'Lun-Sam: 09:00-19:00',
        'description': 'Studio de detailing în Cluj cu experiență de 8 ani. Specializați în polish și protecție ceramică Gtechniq și Ceramic Pro.',
        'lat': 46.7689, 'lng': 23.5853,
    },
    {
        'name': 'Vulca Top Cluj',
        'category': 'vulcanizari',
        'city': 'cluj-napoca',
        'address': 'Calea Baciului 2A',
        'phone': '0264 400 500',
        'schedule': 'Lun-Vin: 07:00-20:00, Sam: 08:00-18:00',
        'description': 'Vulcanizare rapidă în Cluj, servicii complete de montare și echilibrare. Stocuri mari de anvelope Michelin, Continental, Bridgestone.',
        'lat': 46.7430, 'lng': 23.5675,
    },
    {
        'name': 'Tractari Rapide Cluj 24H',
        'category': 'tractari',
        'city': 'cluj-napoca',
        'address': 'Str. Aurel Vlaicu 35',
        'phone': '0264 500 600',
        'schedule': 'Non-stop 24/7',
        'description': 'Tractare și asistență rutieră 24/7 în Cluj și județul Cluj. Platformă modernă, echipaj rapid. Acoperim autostrada A3.',
        'lat': 46.7553, 'lng': 23.5740,
    },
    # ---- TIMIȘOARA (4) ----
    {
        'name': 'TimișAuto Service',
        'category': 'mecanica',
        'city': 'timisoara',
        'address': 'Calea Șagului 120',
        'phone': '0256 100 200',
        'schedule': 'Lun-Vin: 07:30-18:00, Sam: 08:00-13:00',
        'description': 'Service mecanic complet în Timișoara. Revizie, reparații, diagnosticare. Partener autorizat Volkswagen Group. Echipamente HELLA GUTMANN.',
        'featured': True,
        'lat': 45.7400, 'lng': 21.2600,
    },
    {
        'name': 'Vopsitorie Auto Timișoara',
        'category': 'tinichigerie',
        'city': 'timisoara',
        'address': 'Str. Industriilor 8',
        'phone': '0256 200 300',
        'schedule': 'Lun-Vin: 08:00-17:30',
        'description': 'Vopsitorie auto profesională, cabină de vopsit Italjet. Lucrăm pe orice marcă, restaurări complete, reparații post-accident.',
        'lat': 45.7560, 'lng': 21.2820,
    },
    {
        'name': 'Detailing Timișoara Pro',
        'category': 'detailing',
        'city': 'timisoara',
        'address': 'Bd. Take Ionescu 50',
        'phone': '0256 300 400',
        'schedule': 'Lun-Sam: 09:00-18:00',
        'description': 'Detailing auto profesional în Timișoara. Produse premium Koch Chemie și Menzerna. Pachete complete de la spălare la protecție ceramică.',
        'lat': 45.7534, 'lng': 21.2257,
    },
    {
        'name': 'Electro Service Vest',
        'category': 'electrica',
        'city': 'timisoara',
        'address': 'Calea Lipovei 45',
        'phone': '0256 400 500',
        'schedule': 'Lun-Vin: 08:00-18:00',
        'description': 'Reparații electrice auto specializate în Timișoara. Diagnosticare OBD2, reparații alternator, demaror, instalații electrice complete.',
        'lat': 45.7399, 'lng': 21.2443,
    },
    # ---- IAȘI (3) ----
    {
        'name': 'IașiMech Service',
        'category': 'mecanica',
        'city': 'iasi',
        'address': 'Str. Metalurgie 15, Iași',
        'phone': '0232 100 200',
        'schedule': 'Lun-Vin: 08:00-18:00',
        'description': 'Service mecanic de încredere în Iași. Echipă cu experiență de 15 ani, diagnosticare modernă, revizie și reparații pentru toate mărcile.',
        'lat': 47.1585, 'lng': 27.5956,
    },
    {
        'name': 'Vulcanizare Rapid Iași',
        'category': 'vulcanizari',
        'city': 'iasi',
        'address': 'Șos. Moara de Vânt 89',
        'phone': '0232 200 300',
        'schedule': 'Lun-Sam: 07:00-21:00',
        'description': 'Vulcanizare rapidă în Iași, echipamente moderne de echilibrare și montare. Depozitare anvelope, sezon și off-sezon.',
        'lat': 47.1682, 'lng': 27.6127,
    },
    {
        'name': 'AutoDetailing Iași',
        'category': 'detailing',
        'city': 'iasi',
        'address': 'Calea Chișinăului 25',
        'phone': '0232 300 400',
        'schedule': 'Lun-Sam: 09:00-19:00',
        'description': 'Servicii de detailing auto în Iași. Specializați în protecție ceramică și polish. Satisfacție garantată sau reluăm lucrarea gratuit.',
        'lat': 47.1745, 'lng': 27.5780,
    },
    # ---- BRAȘOV (3) ----
    {
        'name': 'AutoBrașov Mecanică',
        'category': 'mecanica',
        'city': 'brasov',
        'address': 'Str. Zizinului 45',
        'phone': '0268 100 200',
        'schedule': 'Lun-Vin: 07:00-18:00, Sam: 08:00-14:00',
        'description': 'Service mecanic complet în Brașov. Revizie, frâne, distribuție, ambreiaj. Lucrăm pe toate mărcile europene și asiatice. Prețuri corecte.',
        'featured': True,
        'lat': 45.6640, 'lng': 25.6119,
    },
    {
        'name': 'Caroserie Brașov',
        'category': 'tinichigerie',
        'city': 'brasov',
        'address': 'Str. Harmanului 8',
        'phone': '0268 200 300',
        'schedule': 'Lun-Vin: 08:00-17:00',
        'description': 'Reparații caroserie și vopsitorie în Brașov. Lucrăm cu piese originale și aftermarket certificat. Cabină de vopsit modernă, termostabilizată.',
        'lat': 45.6727, 'lng': 25.6287,
    },
    {
        'name': 'Tractare Brașov',
        'category': 'tractari',
        'city': 'brasov',
        'address': 'Str. Saturn 12',
        'phone': '0268 300 400',
        'schedule': 'Non-stop 24/7',
        'description': 'Tractare și depanare pe raza județului Brașov, Prahova și Covasna. Răspuns rapid pe Valea Prahovei. Platforma 24 ore.',
        'lat': 45.6520, 'lng': 25.5988,
    },
    # ---- CONSTANȚA (2) ----
    {
        'name': 'Mare Auto Service',
        'category': 'mecanica',
        'city': 'constanta',
        'address': 'Str. Brizei 34, Constanța',
        'phone': '0241 100 200',
        'schedule': 'Lun-Vin: 08:00-18:00',
        'description': 'Service mecanic complet pe litoralul Mării Negre. Specialiști în mașini afectate de umiditate și sare. Revizie, frâne, suspensii.',
        'lat': 44.1850, 'lng': 28.6418,
    },
    {
        'name': 'Detailing Constanța',
        'category': 'detailing',
        'city': 'constanta',
        'address': 'Bd. Tomis 120',
        'phone': '0241 200 300',
        'schedule': 'Lun-Sam: 09:00-18:00',
        'description': 'Detailing auto specializat în Constanța. Protecție caroserie împotriva sării marine. Servicii complete de curățare și protecție.',
        'lat': 44.1774, 'lng': 28.6357,
    },
    # ---- SIBIU (2) ----
    {
        'name': 'Sibiu Auto Expert',
        'category': 'mecanica',
        'city': 'sibiu',
        'address': 'Str. Hipodromului 15',
        'phone': '0269 100 200',
        'schedule': 'Lun-Vin: 08:00-17:30',
        'description': 'Service mecanic de calitate în Sibiu. Diagnosticare avansată, schimb distribuție, revizii. Partener autorizat Continental și Bosch Service.',
        'lat': 45.7862, 'lng': 24.1488,
    },
    {
        'name': 'Vulcanizare Sibiu Central',
        'category': 'vulcanizari',
        'city': 'sibiu',
        'address': 'Calea Dumbrăvii 89',
        'phone': '0269 200 300',
        'schedule': 'Lun-Sam: 07:00-20:00',
        'description': 'Vulcanizare rapidă în Sibiu. Toate tipurile de anvelope, depozitare sezonieră, echilibrare computerizată.',
        'lat': 45.7753, 'lng': 24.1382,
    },
    # ---- CRAIOVA (2) ----
    {
        'name': 'Auto Oltenia Service',
        'category': 'mecanica',
        'city': 'craiova',
        'address': 'Str. Calea București 45',
        'phone': '0251 100 200',
        'schedule': 'Lun-Vin: 08:00-18:00',
        'description': 'Service mecanic complet în Craiova. Revizie, reparații, diagnosticare. Specialiști în autovehicule de mari capacități.',
        'lat': 44.3262, 'lng': 23.7943,
    },
    {
        'name': 'Tractare Oltenia 24H',
        'category': 'tractari',
        'city': 'craiova',
        'address': 'Str. Calea Severinului 12',
        'phone': '0251 200 300',
        'schedule': 'Non-stop 24/7',
        'description': 'Tractare și asistență rutieră în Oltenia. Acoperim Craiova și județele Dolj, Gorj, Vâlcea. Platformă modernă, echipaj rapid.',
        'lat': 44.3192, 'lng': 23.7735,
    },
    # ---- PLOIEȘTI (2) ----
    {
        'name': 'Ploiești Auto & Mecanică',
        'category': 'mecanica',
        'city': 'ploiesti',
        'address': 'Str. Găgeni 78',
        'phone': '0244 100 200',
        'schedule': 'Lun-Vin: 07:30-18:30',
        'description': 'Service mecanic experimentat în Ploiești. Revizie, reparații, schimb distribuție. Prețuri competitive, calitate garantată.',
        'lat': 44.9445, 'lng': 26.0191,
    },
    {
        'name': 'ElectroAuto Prahova',
        'category': 'electrica',
        'city': 'ploiesti',
        'address': 'Bd. Petrolului 25',
        'phone': '0244 200 300',
        'schedule': 'Lun-Vin: 08:00-18:00',
        'description': 'Diagnosticare și reparații electrice auto în Ploiești. Specialiști în instalații electrice, sisteme de injecție și management motor.',
        'lat': 44.9380, 'lng': 26.0087,
    },
]

REVIEW_TITLES = [
    'Serviciu excelent!',
    'Recomand cu căldură',
    'Profesioniști adevărați',
    'Prețuri corecte, calitate bună',
    'Service de top!',
    'Mulțumit de rezultat',
    'Echipă de specialiști',
    'Rapid și eficient',
    'Cel mai bun service din oraș',
    'M-au ajutat rapid',
    'Calitate la preț bun',
    'Nu mai merg în altă parte',
    'Super serviciu!',
    'Comunicare excelentă',
    'Lucrare impecabilă',
]

REVIEW_BODIES = [
    'Am adus mașina cu o problemă serioasă și au rezolvat-o rapid și profesionist. Prețul a fost corect și mai mic decât m-aș fi așteptat. Recomand tuturor!',
    'Echipa este formată din oameni pasionați de mașini. Au explicat tot ce trebuia făcut înainte să înceapă lucrarea. Mașina arată impecabil.',
    'Al doilea an când vin aici pentru revizie și de fiecare dată am fost mulțumit. Punctuali, corecti și transparenți cu prețurile.',
    'Am venit cu o urgență la 7 dimineața și m-au primit imediat. Oameni de treabă, știu ce fac. Voi reveni cu siguranță.',
    'Detailing-ul a fost senzațional. Mașina mea veche de 10 ani arată ca nouă. Merită fiecare leu plătit!',
    'Service modern, echipamente noi, personal tânăr și calificat. M-am simțit în mâini bune toată timpul.',
    'Am verificat devizul înainte și după și totul a corespuns. Nicio surpriză neplăcută. Asta e ce îți dorești de la un service.',
    'Programare online simplă, au respectat ora exact. Lucrarea a durat exact cât mi-au spus. Totul a fost perfect.',
    'Mașina merge mult mai bine după revizie. Au descoperit și alte probleme mici pe care le-au remediat fără costuri suplimentare.',
    'Primeam recomandarea de la un prieten și nu regret. Sunt cei mai buni din zonă.',
]


class Command(BaseCommand):
    help = 'Populează baza de date cu date demo pentru AutoHub'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clean',
            action='store_true',
            help='Șterge datele existente înainte de import',
        )

    def _generate_seed_image(self, slug, title, color):
        seed_dir = Path(settings.MEDIA_ROOT) / 'seed'
        seed_dir.mkdir(parents=True, exist_ok=True)
        image_path = seed_dir / f'{slug}.png'
        img = Image.new('RGB', (1200, 800), color)
        draw = ImageDraw.Draw(img)
        draw.rounded_rectangle((40, 40, 1160, 760), radius=36, outline='white', width=6)
        draw.text((90, 120), title[:28], fill='white')
        draw.text((90, 190), 'AutoHub demo image', fill='white')
        img.save(image_path)
        return image_path

    def handle(self, *args, **options):
        from services.models import ServiceCategory, ServiceCenter, ServiceGarage, ServiceImage, ServiceItem, Review

        self.stdout.write(self.style.WARNING('🚀 Pornind seed AutoHub...'))

        self.stdout.write('🧹 Ștergere date anterioare...')
        Review.objects.all().delete()
        ServiceItem.objects.all().delete()
        ServiceGarage.objects.all().delete()
        ServiceImage.objects.all().delete()
        ServiceCenter.objects.all().delete()
        ServiceCategory.objects.all().delete()

        self.stdout.write('📂 Creare categorii...')
        cats = {}
        for cat_data in CATEGORIES:
            cat = ServiceCategory.objects.create(**cat_data)
            cats[cat_data['slug']] = cat
            self.stdout.write(f'  ✓ {cat.icon} {cat.name}')

        self.stdout.write('👤 Creare utilizatori mock...')
        mock_users = []
        mock_usernames = [
            ('ion_popescu', 'Ion', 'Popescu'),
            ('maria_ionescu', 'Maria', 'Ionescu'),
            ('andrei_radu', 'Andrei', 'Radu'),
            ('elena_stancu', 'Elena', 'Stancu'),
            ('mihai_dobre', 'Mihai', 'Dobre'),
            ('ana_costea', 'Ana', 'Costea'),
            ('dan_marin', 'Dan', 'Marin'),
            ('laura_popa', 'Laura', 'Popa'),
        ]
        for username, first, last in mock_usernames:
            user, _ = User.objects.get_or_create(username=username, defaults={'first_name': first, 'last_name': last, 'email': f'{username}@example.ro'})
            user.set_password('demo1234')
            user.save()
            mock_users.append(user)

        self.stdout.write(f'🏢 Creare {len(CENTERS_DATA)} service-uri...')
        created_centers = []
        all_slugs = [c['slug'] for c in CATEGORIES]
        for idx, raw in enumerate(CENTERS_DATA):
            data = raw.copy()
            cat_slug = data.pop('category')
            featured = data.pop('featured', False)
            lat = data.pop('lat', None)
            lng = data.pop('lng', None)

            extra_slugs = [slug for slug in all_slugs if slug != cat_slug]
            random.shuffle(extra_slugs)
            category_slugs = [cat_slug] + extra_slugs[:random.randint(1, 2)]

            center = ServiceCenter.objects.create(category=cats[cat_slug], is_featured=featured, latitude=lat, longitude=lng, **data)
            center.categories.set([cats[slug] for slug in category_slugs])

            card_path = self._generate_seed_image(f'card_{center.slug}', center.name, cats[cat_slug].color)
            with card_path.open('rb') as fh:
                center.card_image.save(card_path.name, File(fh), save=True)

            for gallery_index, slug in enumerate(category_slugs[:2], start=1):
                gallery_path = self._generate_seed_image(f'gallery_{center.slug}_{gallery_index}', f'{center.name} {gallery_index}', cats[slug].color)
                with gallery_path.open('rb') as fh:
                    ServiceImage.objects.create(center=center, caption=f'Zona {gallery_index} - {cats[slug].name}', image=File(fh, name=gallery_path.name))

            for garage_index, slug in enumerate(category_slugs, start=1):
                ServiceGarage.objects.create(center=center, name=f'Garaj {garage_index}', category=cats[slug])

            created_centers.append((center, cat_slug))
            self.stdout.write(f'  ✓ {center.name} ({center.get_city_display()}) - categorii: {", ".join(category_slugs)}')

        self.stdout.write('🔧 Creare servicii + prețuri...')
        for center, cat_slug in created_centers:
            items = SERVICE_ITEMS.get(cat_slug, [])
            items_copy = list(items)
            random.shuffle(items_copy)
            n = random.randint(6, min(10, len(items_copy)))
            popular_indices = random.sample(range(n), k=min(2, n))
            for i, (name, price_from, price_to, duration) in enumerate(items_copy[:n]):
                pf = round(price_from * random.uniform(0.9, 1.1))
                pt = round(price_to * random.uniform(0.9, 1.1))
                ServiceItem.objects.create(center=center, name=name, price_from=pf, price_to=pt, duration_minutes=duration, is_popular=(i in popular_indices))

        self.stdout.write('⭐ Creare recenzii...')
        for center, _ in created_centers:
            n_reviews = random.randint(1, 3)
            users_to_review = random.sample(mock_users, k=min(n_reviews, len(mock_users)))
            for user in users_to_review:
                rating = random.choices([3, 4, 4, 5, 5, 5], k=1)[0]
                Review.objects.create(center=center, user=user, rating=rating, title=random.choice(REVIEW_TITLES), body=random.choice(REVIEW_BODIES), is_approved=True)

        if not User.objects.filter(username='admin').exists():
            User.objects.create_superuser(username='admin', email='admin@autohub.ro', password='admin123', first_name='Admin', last_name='AutoHub')
            self.stdout.write(self.style.SUCCESS('👑 Superuser creat: admin / admin123'))

        from services.models import ServiceCategory, ServiceCenter, ServiceGarage, ServiceImage, ServiceItem, Review
        self.stdout.write('\n' + '='*50)
        self.stdout.write(self.style.SUCCESS('✅ Seed finalizat cu succes!'))
        self.stdout.write(f'  📂 Categorii:   {ServiceCategory.objects.count()}')
        self.stdout.write(f'  🏢 Service-uri: {ServiceCenter.objects.count()}')
        self.stdout.write(f'  🏗️ Garaje:      {ServiceGarage.objects.count()}')
        self.stdout.write(f'  🖼️ Poze:        {ServiceImage.objects.count()} + {ServiceCenter.objects.exclude(card_image='').count()} poze de card')
        self.stdout.write(f'  🔧 Servicii:    {ServiceItem.objects.count()}')
        self.stdout.write(f'  ⭐ Recenzii:    {Review.objects.count()}')
        self.stdout.write(f'  👤 Utilizatori: {User.objects.count()}')
        self.stdout.write('='*50)
        self.stdout.write(self.style.SUCCESS('🌐 Pornește serverul: python manage.py runserver'))
        self.stdout.write(self.style.SUCCESS('🔑 Admin: http://127.0.0.1:8000/admin/ (admin/admin123)'))
