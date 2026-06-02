# Raport privind folosirea toolurilor AI in dezvoltarea AutoHUB

## Context

AutoHUB este o aplicatie web Django pentru programari service auto, dashboard operational, calendar, fise de lucru, inventar, facturi si dosar digital al masinii. In timpul dezvoltarii au fost folosite tooluri AI pentru accelerarea analizei, generarea de variante de implementare, verificarea fluxurilor si documentarea deciziilor.

## Tooluri AI folosite

- ChatGPT / Codex: asistenta pentru analiza codului, propuneri de structura, generare si revizuire de cod, documentatie si teste.
- OpenAI API: integrare pregatita in aplicatie pentru scanarea documentelor auto si extragerea asistata a datelor.
- Anthropic / Claude: suport configurabil pentru asistenta de dezvoltare si analiza, documentat in `ANTHROPIC_SETUP.txt`.

## Moduri concrete de utilizare

1. Analiza cerintelor si impartirea functionalitatilor pe module Django: `accounts`, `services`, `bookings`, `invoices`, `core`.
2. Generarea de variante pentru fluxuri importante: programare, oferta, acceptare/refuz, finalizare lucrare si emitere factura.
3. Identificarea cazurilor limita pentru testare: suprapuneri de programari, sloturi indisponibile, permisiuni, fisiere incarcate si stoc negativ.
4. Scrierea si rafinarea testelor automate Django si Playwright pentru fluxuri critice.
5. Documentarea arhitecturii, a limitelor cunoscute si a modului de rulare local/deploy.
6. Pregatirea integrarii OpenAI pentru scanare documente, cu confirmare manuala inainte de salvarea datelor.

## Exemple din proiect

- `accounts/views.py`: fluxuri pentru scanarea documentelor auto si apelarea OpenAI.
- `bookings/ai.py`: estimarea duratei lucrarilor folosind reguli, istoric si fallback AI.
- `accounts/test_document_scan_and_reminders.py`: teste pentru scanarea documentelor si salvarea datelor confirmate manual.
- `accounts/test_document_scan_round3.py`: teste pentru erori de provider AI si date partiale.
- `bookings/tests.py`: teste pentru estimari de durata, istoric si reprogramare.
- `README.md`: sectiuni despre arhitectura, testare, AI si deploy.

## Control uman si siguranta

Toolurile AI au fost folosite ca asistenti, nu ca sursa finala neverificata. Codul generat sau propus a fost verificat prin:

- citirea si adaptarea la structura existenta a proiectului;
- teste automate Django;
- teste end-to-end Playwright pentru fluxuri de browser;
- validari de permisiuni si izolare a datelor;
- confirmare manuala a datelor extrase prin AI inainte de salvare.

Pentru scanarea documentelor, aplicatia nu salveaza automat rezultatul AI. Utilizatorul incarca documentul, sistemul propune date extrase, iar utilizatorul confirma sau corecteaza datele inainte de persistare.

## Limitari

- Integrarea OpenAI depinde de `OPENAI_API_KEY` si de configurarea providerului.
- Testele evita dependenta de servicii externe reale prin mock-uri sau fallback-uri controlate.
- Toolurile AI pot produce raspunsuri incomplete sau gresite, de aceea rezultatele au fost validate prin teste si verificare manuala.

## Concluzie

Folosirea toolurilor AI a redus timpul de analiza, implementare si testare, dar deciziile finale de arhitectura, validare si integrare au ramas controlate de dezvoltator. In proiect, AI-ul apare atat ca suport de dezvoltare, cat si ca functionalitate pregatita pentru utilizatorii aplicatiei prin scanarea documentelor auto.
