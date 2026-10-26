# Fisa de directie — atelierul 1

> **Inginerie Software 2026–27** · tema optionala, nu se noteaza.
> Atelierul 1 (S5, 26–30 oct) confirma directia in care va duceti proiectul. Echipele care vin cu fisa au o discutie mai scurta si mai precisa.
>
> **Cum:** copiati fisierul in radacina repo-ului ca `DIRECTIE.md`, completati-l si faceti commit inainte de slotul vostru de atelier. Veniti la atelier cu el in repo.
> **Atelierul:** vom posta un calendar; fiecare echipa isi rezerva slotul in intervalul de 4 ore, cu Rares si Petru.
> **Lungime:** cel mult doua pagini. Puncte scurte, nu eseuri.
> **Cand:** sectiunile 1–6 dupa cursul 2 (S3); sectiunile 7–8 dupa cursul 3 (S4).
> **AI:** permis si declarat (in mesajul de commit), ca la orice livrabil. La atelier, fiecare membru trebuie sa poata explica orice rand de aici.
>
> Indicatiile sunt comentarii `<!-- ... -->`: nu apar pe GitHub, le puteti lasa sau sterge.

| | |
|---|---|
| **Echipa** | AutoEMG |
| **Membri** | 1. Craciuenscu Cristian-Alexandru |
|            | 2. Diaconescu Stefan-Calin |
|            | 3. Anghel Eduard-Andrei |
|            | 4. Cherascu-Telitoiu Nicolae-Bogdan |
|            | 5. Buleauca Darius-Andrei |
| **Repo** | https://github.com/inginerie-software-26-27/is2627-proiect-group-56.git|

---

## 1. Sistemul, asa cum e acum (as-is)

<!-- Ce face, in 3 propozitii. Pentru cine.
     Starea reala: ce merge, ce e pe jumatate, ce nu merge deloc.
     Cum ati aflat: ce ati citit si ce ati rulat (README, issues, teste, cod). -->
     Functionalitatile sistemului sunt impartite in 2 parti:
     1. Pentru detinatorii/conducatorii de autoturisme:
          -inregistrarea datelor autoturismului in sistem(VIN, combustibil, marca, model, nr. inmatriculare, etc.)
          -calendar pentru datele de expirare ale documentelor aferente fiecarui autoturism, cu averitzare prin email/mesagerie cu o luna inainte de expirare.
          -posibilitatea de a cere oferte service-urilor pentru o problema/reparatie si acceptarea celei mai convenabile.
          -harta interactiva cu redirect catre google maps/waze spre locatia service-ului.
     2. Pentru service-uri auto:
          -panou complet de service cu dashboard, calendar programari, stoc piese, devize, facturi.
          -poze/videoclipuri inainte/in timpul/dupa reparatie.
          -istoric masini cu cautare dupa nume/numar de telefon/nr. de inmatriculare.
          -recomandari in functie de kilometraj, piese schimbate la ultima vizita.

     Stare reala: totul este 100% functional.
     Cum am aflat: Sistemul este verificat constant atat prin incercari fizice, cat si prin intermediul testelor django backend si e2e.

     

     


## 2. Directia (to-be)

<!-- Cel mult trei obiective pentru semestrul acesta: ce intariti, ce reparati, ce schimbati.
     Pentru fiecare: de ce acum si cum veti sti ca l-ati atins. -->

| # | Obiectiv | De ce acum | Cum stim ca l-am atins |
|---|---|---|---|
| O1 | Optimizarea procesului de programare | Programarea este punctul principal de pornire pentru client si service. | Atunci cand munca depusa din partea clientului, cat si a service-ului, pentru a face o programare devine mai usoara. |
| O2 | Integrarea Google Maps pentru localizarea service-urilor | Clientii trebuie sa gaseasca usor locatia service-urilor, prin inlocuirea metodei actuale de harta cu Google Maps. | Harta Google Maps este afisata in site, iar locatiile service-urilor sunt marcate corect si pot fi selectate de clienti. |
| O3 | Introducerea abonamentelor platite de service-uri pentru utilizarea platformei | Creeaza un model de venit pentru sustinerea si dezvoltarea AutoEMG. | In mediul de test, service-ul alege un plan, plateste, iar abonamentul este activat; reinnoirea, esecul platii si anularea au rezultate verificabile. |

**Ce nu facem:** 

- Nu dezvoltam plati ale soferilor catre service-uri, aplicatie mobila sau integrari cu furnizori de piese in aceasta etapa.
- Nu rescriem aplicatia; imbunatatim programarea si adaugam abonamentele in arhitectura existenta.

## 3. Stakeholderii

<!-- Nu doar utilizatorii (personas de la MDS): oricine e afectat de sistem. -->

| Cine | Ce vrea de la sistem | Cum aflam ce vrea (interviu, observatie, scenariu, repo) |
|---|---|---|
| Soferii / clientii | Gasirea unui service, programare cu putin efort, costuri si statusuri clare, acces la istoricul masinii | Observarea unei programari si discutii despre pasii confuzi; validare propusa cu soferi |
| Proprietarii de service, receptia si mecanicii | Cereri complete, calendar organizat, evidenta lucrarilor si pieselor; pret, beneficii si conditii de abonament clare | Discutie propusa cu un reprezentant de service si simularea unei zile de lucru |
| Administratorul platformei | Conturi si service-uri administrabile, acces controlat la date si evidenta abonamentelor si incasarilor | Revizuirea fluxurilor de administrare si a permisiunilor |

## 4. Resursele noastre

<!-- Realist, nu optimist. O tehnologie pe care nu o stie nimeni din echipa primeste automat risc 9 (sectiunea 6). -->

| Resursa | Ce avem, realist | Ce ne lipseste |
|---|---|---|
| **Oameni** <br><sub>membri, ore pe saptamana fiecare, cine lipseste cand</sub> | Suntem 5 membri in echipa. | Mai trebuie sa stabilim cate ore poate lucra fiecare pe saptamana si cum impartim sarcinile. |
| **Cunostinte** <br><sub>ce stapanim, ce ar fi prima data</sub> | Avem proiectul in Django si exemple de teste in repo. | Trebuie sa ne familiarizam cu partea de abonamente si integrarea platilor; experienta fiecaruia ramane de stabilit. |
| **Tehnice** <br><sub>stack, medii, CI, hosting, servicii externe</sub> | Django, Bootstrap, SQLite/PostgreSQL, teste Django si Playwright, CI si configuratie Render. | Un cont de test la un procesator de plati si configurarea mediului pentru abonamente. |
| **Financiare** <br><sub>buget (si daca e 0 lei, spunem)</sub> | Domeniu: 12$/an, Host: 7$/luna, Twilio:1,2$/SMS, Gmail: 6$/luna, OpenAI: 0,75$ input+output/1 milion token | Trebuie sa stabilim bugetul pentru hosting si eventualele costuri ale procesatorului. |
| **Acces la AI** <br><sub>modele, planuri, cine le are, limite; ce date nu avem voie sa punem in model</sub> | Folosim asistenta AI la documentare; aplicatia are si integrare OpenAI. | Trebuie sa clarificam ce acces are fiecare. Nu trimitem parole, chei API sau date personale reale. |
## 5. Fezabilitate

<!-- Dupa Sommerville, Software Engineering, ed. 10, p. 104, adaptat.
     Un „nu” sau „nu stim” e un subiect bun pentru atelier. -->

| Intrebare | Da / Nu / Nu stim | De ce |
|---|---|---|
| Contribuie directia la ce vor stakeholderii de la sectiunea 3? | Da | Vrem programari mai simple, informatii mai clare si abonamente cu beneficii usor de inteles. Le verificam prin discutii si scenarii. |
| Se poate face pana la final de semestru, cu resursele de la sectiunea 4? | Nu stim inca | Programarile exista deja, dar platile sunt o parte noua. Trebuie sa estimam timpul si sa incepem cu o varianta de test. |
| Se integreaza cu ce exista deja in sistem si in jurul lui? | Da | Pastram aplicatia actuala si legam abonamentul de contul service-ului. |

## 6. Primele cinci riscuri

<!-- Tip: estimation / organizational / people / requirements / technology / tools.
     Impact si probabilitate de la 1 la 3; scor = impact × probabilitate (1–2 mic, 3–4 mediu, 6–9 mare).
     Strategie: avoid / minimize / contingency. -->

| # | Risc | Tip | Impact | Prob. | Scor | Strategie |
|---|---|---|---|---|---|---|
| R1 | Nu intelegem bine ce ii incurca pe utilizatori la programare | requirements | 3 | 2 | 6 | minimize: cerem feedback pe un scenariu complet |
| R2 | Integrarea platilor dureaza mai mult decat estimam | estimation | 3 | 3 | 9 | minimize: incepem cu un singur plan si plati in mediul de test |
| R3 | Plata si starea abonamentului nu se actualizeaza corect | technology | 3 | 3 | 9 | minimize: testam plati reusite, esuate si notificari repetate |
| R4 | Nu reusim sa discutam cu un service real | organizational | 2 | 2 | 4 | contingency: pregatim scenarii de simulare si mentionam lipsa feedbackului real |
| R5 | Nu avem toti timp suficient din cauza altor materii | people | 3 | 2 | 6 | minimize: impartim sarcinile si verificam saptamanal progresul |

## 7. Cerintele candidate (dupa S4)

<!-- Intre 5 si 10. Cerintele stau in repo, langa cod si langa testele care le verifica (cursul 3).
     Prioritate: must / should / could / won't (won't = nu de data asta).
     Tip: functionala (F) sau nefunctionala: product / organizational / external (Sommerville, Fig. 4.3).
     Sursa: stakeholderul, issue-ul, codul sau testul din care vine, si cine a confirmat-o (o cerinta extrasa din cod nu e confirmata de cod).
     De ce: rationale, ca sa stiti pe cine intrebati cand se schimba.
     Cum verificam: un test, sau o masura cu prag. „Sa fie rapid” nu e cerinta; „harta se incarca in sub 2 s pentru 95% din cereri” este. -->

| # | Cerinta | Prioritate | Tip | Sursa · confirmata de | De ce (rationale) | Cum verificam |
|---|---|---|---|---|---|---|
| C1 | Clientul poate trimite o programare folosind datele unei masini salvate. | must | F | Client; fluxul existent din repo, de validat cu utilizatori | Sa nu completeze aceleasi date de fiecare data. | Testam preluarea datelor si salvarea programarii. |
| C2 | Clientul vede oferta si statusul lucrarii si poate accepta sau refuza oferta. | must | F | Client si service; codul existent, de validat cu ambele roluri | Ambele parti trebuie sa stie ce urmeaza. | Testam acceptarea, refuzul si afisarea statusului dupa actualizare. |
| C3 | Service-ul poate plati un abonament pentru accesul la platforma. | must | NF - product | Cerinta echipei: abonamente pentru service-uri; tariful ramane de stabilit | Sa putem sustine platforma prin abonamente. | In mediul de test verificam plata reusita, esuata si anulata. |
| C4 | Abonamentul se activeaza doar dupa confirmarea verificata a platii si respecta perioada achitata. | must | NF - product | O3; de confirmat regulile cu echipa | Sa nu oferim sau retragem accesul din greseala. | Testam confirmari repetate, reinnoire, anulare si expirare; o confirmare repetata nu prelungeste abonamentul de doua ori. |
| C5 | Fiecare cont vede doar datele private pentru care are drepturi. | must | NF - product | Datele gestionate si testele de permisiuni; de confirmat de echipa | Protejam masinile, documentele si abonamentele utilizatorilor. | Testam accesul din alt cont, inclusiv prin link direct la documente si abonamente. |

## 8. Primele trei architecture characteristics (daca ajungeti pana aici)

<!-- Doar trei: cele fara de care sistemul nu reuseste (Richards & Ford, cap. 4–5; vezi Vasa).
     Fiecare cu cerinta (C1…) sau domain concern-ul din care vine. Cele implicite conteaza: nu le scrie nimeni, dar le stiti din domeniu
     (de exemplu, toata lumea se inscrie in ultimele 10 minute). -->

| # | Architecture characteristic | Din ce cerinta sau domain concern vine | Explicita / implicita |
|---|---|---|---|
| A1 | Utilizabilitate | C1-C2: programarea si oferta trebuie sa fie usor de inteles | Explicita |
| A2 | Fiabilitate | C4: plata si perioada abonamentului trebuie sa fie corecte | Explicita |
| A3 | Securitate | C5: acces controlat la date; datele cardului sunt introduse la procesator | Explicita |

## 9. Intrebari pentru atelier

<!-- Ce nu ati putut decide singuri. -->

- Ce beneficii si pret ar trebui sa aiba primul abonament?
- Este suficienta pentru semestru integrarea platilor si al hartii Google in mediul de test?
- Cum verificam simplu ca procesul de programare a devenit mai usor?
