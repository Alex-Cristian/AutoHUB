# Raportare bug-uri si rezolvare prin pull request-uri

## Scop

Acest document centralizeaza exemple de bug-uri, riscuri sau imbunatatiri rezolvate in proiectul AutoHUB prin branch-uri si pull request-uri. El poate fi folosit ca dovada pentru cerinta de raportare bug si rezolvare cu pull request.

## Dovezi Git

Repository: `https://github.com/Alex-Cristian/AutoHUB`

Exemple de pull request-uri/merge-uri existente in istoricul Git:

- PR #34: `login`
- PR #33: `teste`
- PR #32: `teste`
- PR #31: `polish`
- PR #30: `polish`
- PR #29: `polish`
- PR #28: `polish`
- PR #27: `service`
- PR #26: `sitemaps`
- PR #25: `service`

Branch-uri relevante observate in proiect:

- `login`
- `service`
- `dashboard`
- `scan`
- `expiry-dates`
- `bookings-reviews`
- `invoice-repair`
- `teste`
- `polish`
- `mobile-api`

## Exemple de raportare si rezolvare

### Bug 1: programari suprapuse in calendar

- Problema: o programare mutata putea intra peste un interval deja ocupat sau blocat.
- Impact: service-ul putea ajunge la doua lucrari in acelasi slot.
- Rezolvare: validari suplimentare pentru disponibilitatea garajului/mecanicului si teste dedicate.
- Dovezi in cod: `services/test_calendar_and_reports_round3.py`, `bookings/test_backend_critical.py`, `services/test_edge_cases_round6.py`.
- PR/branch relevant: `dashboard`, `service`, `teste`.

### Bug 2: acces la datele altui utilizator

- Problema: anumite pagini sau actiuni trebuiau protejate astfel incat un client/service sa nu acceseze date straine.
- Impact: risc de expunere a programarilor, masinilor sau facturilor altui cont.
- Rezolvare: verificari de ownership si teste pentru permisiuni.
- Dovezi in cod: `accounts/test_vehicle_permissions.py`, `services/test_permissions_and_public.py`, `invoices/test_invoice_flows.py`.
- PR/branch relevant: `service`, `login`, `teste`.

### Bug 3: scanare documente cu raspuns AI incomplet sau eroare provider

- Problema: providerul AI poate raspunde cu date partiale, poate returna eroare sau poate lipsi cheia API.
- Impact: salvare gresita a datelor masinii sau experienta confuza pentru utilizator.
- Rezolvare: tratare explicita a erorilor si confirmare manuala inainte de salvare.
- Dovezi in cod: `accounts/test_document_scan_and_reminders.py`, `accounts/test_document_scan_round3.py`, `accounts/views.py`.
- PR/branch relevant: `scan`, `teste`.

### Bug 4: miscari de stoc care ar duce la valori negative

- Problema: consumul sau rollback-ul pieselor putea produce inconsistente in inventar daca nu era validat.
- Impact: rapoarte si fise de lucru incorecte.
- Rezolvare: reguli de business pentru miscari de stoc si teste de edge case.
- Dovezi in cod: `services/test_reports_inventory_round2.py`, `services/test_edge_cases_round6.py`, `services/business.py`.
- PR/branch relevant: `service`, `teste`.

### Bug 5: emiterea facturii pentru lucrare nefinalizata

- Problema: factura finala trebuie conditionata de starea lucrarii/programarii.
- Impact: documente generate inainte ca lucrarea sa fie finalizata.
- Rezolvare: validare in logica de business si teste pentru fluxul de factura.
- Dovezi in cod: `invoices/test_invoice_more_flows.py`, `services/test_business_logic.py`.
- PR/branch relevant: `invoice-repair`, `teste`.

## Cum se foloseste acest raport

Pentru prezentare, se poate alege orice bug din lista si se pot arata:

1. descrierea problemei;
2. branch-ul sau pull request-ul asociat;
3. fisierele modificate sau testele adaugate;
4. rezultatul testelor dupa rezolvare.

Comenzi utile:

```bash
git log --all --oneline --merges
git branch -a
python manage.py test
```

## Concluzie

Proiectul foloseste branch-uri si pull request-uri pentru integrarea schimbarilor, iar bug-urile si riscurile importante sunt acoperite prin teste automate. Acest document leaga explicit istoricul Git de probleme concrete rezolvate in aplicatie.
