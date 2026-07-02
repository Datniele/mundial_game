# Mundial Game — Il giocone ludopatico dei mondiali

App Streamlit per raccogliere i pronostici dei partecipanti sui Mondiali 2026, confrontarli con i risultati reali e produrre una classifica automatica.

---

## Struttura del progetto

```
mondiali/
├── Home.py                             # Home Streamlit (entry point)
├── config.yaml                         # Punteggi configurabili
├── requirements.txt
├── .env                                # Variabili d'ambiente (API_FOOTBALL_KEY) — non committare
│
├── pages/
│   ├── 1_Make_Predictions.py          # Form di registrazione e inserimento pronostici
│   ├── 2_Real_Results.py              # Classifiche e risultati reali da API (sola lettura)
│   ├── 3_Statistics.py                # Consenso tra i pronostici per ogni fase
│   ├── 4_Leaderboard.py               # Leaderboard e dettaglio punteggi
│   ├── 5_Rules.py                     # Regolamento e criteri di punteggio (sola lettura)
│   └── 9_Admin_Settings.py            # (Admin) Gestione partecipanti, upload JSON, reset completo
│
├── data/
│   ├── fixtures/fixtures.json         # Calendario normalizzato (non modificare a mano)
│   ├── participants/registry.json     # Registro partecipanti (creato automaticamente)
│   ├── predictions/                   # Un file .json per ogni partecipante
│   └── results/
│       ├── results.json               # Risultati reali knockout {match_id: {home_goals, away_goals, played}}
│       ├── group_rankings.json        # Classifiche finali dei gironi {girone: [1°, 2°, 3°, 4°]}
│       ├── group_standings.json       # Classifiche complete con punti e statistiche {girone: [{pos, squadra, punti, ...}]}
│       ├── group_rankings_meta.json   # Provenienza classifiche gironi: "api" | "default"
│       └── knockout_bracket.json      # Accoppiamenti knockout reali da API {slot_id: {home, away, utc_date, api_id, determined}}
│
└── src/
    ├── models/                        # Dataclass: Match, Result, Prediction, Participant
    ├── scoring/                       # Motore di calcolo punteggi + statistiche di consenso
    ├── storage/                       # Lettura/scrittura JSON su disco
    └── scraper/                       # Classifiche gironi (standings) + accoppiamenti knockout (matches) da football-data.org
```

---

## Formato torneo

**FIFA World Cup 2026** — 48 squadre, 12 gironi da 4 squadre.

| Fase | Partite |
|---|---|
| Fase a gironi | 12 gironi × 6 partite = **72 partite** |
| Sedicesimi di finale | 16 partite |
| Ottavi di finale | 8 partite |
| Quarti di finale | 4 partite |
| Semifinali | 2 partite |
| Finale 3° posto | 1 partita |
| Finale | 1 partita |

Dai gironi si qualificano: le prime 2 di ogni girone (24) + le 8 migliori terze classificate = **32 squadre** ai sedicesimi.

---

## Setup

### 1. Creare e attivare il virtualenv

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 2. Installare le dipendenze

```powershell
pip install -r requirements.txt
```

### 3. Configurare la variabile d'ambiente (opzionale — solo per lo scraper)

Crea un file `.env` nella root del progetto:

```
API_FOOTBALL_KEY=la_tua_chiave_football_data_org
```

API key gratuita: https://www.football-data.org/client/register (limite: 10 req/min)

### 4. Avviare l'app

```powershell
streamlit run Home.py
```

---

## Workflow di utilizzo

```
1. Ogni partecipante apre l'app e va su "Make Predictions"
         ↓
2. Inserisce nome e cognome → viene registrato automaticamente
         ↓
3. Seleziona la fase (Groups / Round of 32 / Round of 16 / Quarter-finals / Semi-finals / Final)
   e compila il form → clicca "Save"
   (nelle classifiche gironi le squadre già selezionate non sono riproponibili)
         ↓
4. Quando le partite vengono giocate, l'admin va su "Real Results"
   → classifiche gironi e risultati knockout si aggiornano da soli via API
     all'apertura della pagina (sola lettura, nessun inserimento manuale)
         ↓
5. Vai su "Leaderboard": all'apertura le classifiche reali vengono riscaricate
   dall'API e la graduatoria è calcolata su dati freschi
```

---

## Inserimento pronostici — pagina partecipante

La pagina **Make Predictions** permette a ogni partecipante di registrarsi e compilare i pronostici direttamente dal browser.

### Cosa si pronostica per fase

| Fase | Contenuto |
|---|---|
| `Groups` | Classifica completa 1°→4° per ognuno dei 12 gironi |
| `Round of 32` | 16 match slot: risultato esatto + chi passa il turno |
| `Round of 16` | 8 match slot: risultato esatto + chi passa il turno |
| `Quarter-finals` | 4 match slot: risultato esatto + chi passa il turno |
| `Semi-finals` | 2 match slot: risultato esatto + chi passa il turno |
| `Final` | Finale 3° posto + Finale: risultato esatto + chi passa il turno |

> Per la fase a gironi si inserisce **solo il posizionamento finale** (1°→4° posto), non i risultati delle singole partite.
> Per le fasi a eliminazione, risultato esatto e passaggio del turno si pronosticano in modo **indipendente**: non devono per forza concordare (es. pareggio nei 90' ma qualificazione ai rigori).
> Eventuali slot già disputati prima dell'apertura dei pronostici sono esclusi sia dalla pagina Make Predictions sia dal conteggio (vedi `EXCLUDED_KNOCKOUT_SLOTS` in [`src/models/tournament.py`](src/models/tournament.py)).

Il salvataggio è **incrementale**: ogni "Salva" aggiorna solo la fase corrente; le altre restano invariate. È possibile tornare in momenti diversi per completare le fasi successive.

> Il sistema usa una logica di **merge**: se lo stesso partecipante salva da browser o sessioni diverse, i pronostici già presenti vengono preservati e aggiornati solo per le fasi modificate.

### Registro partecipanti

Ogni partecipante che accede per la prima volta viene registrato in `data/participants/registry.json`:

```json
{
  "participants": [
    {
      "name": "Mario Rossi",
      "registered_at": "2026-06-01T10:00:00",
      "last_updated": "2026-06-01T14:30:00"
    }
  ]
}
```

---

## Risultati reali — pagina admin

La pagina **Real Results** è **interamente in sola lettura**: tutti i dati reali (classifiche gironi e risultati knockout) sono ricavati da football-data.org e **non sono modificabili a mano**.

### Aggiornamento automatico all'apertura (classifiche gironi + risultati knockout)

Appena si apre la pagina **Real Results**, lo scraper interroga football-data.org e popola **senza bisogno di premere alcun tasto**:

- *Classifiche gironi* — endpoint `GET /competitions/WC/standings` → `group_rankings.json` e `group_standings.json`.
- *Risultati knockout* — endpoint `GET /competitions/WC/matches` → `results.json`: per ogni partita **conclusa** (`status == FINISHED`) si ricavano il **punteggio dei 90 minuti** (`score.regularTime`, con fallback su `score.fullTime` per i match chiusi nei regolamentari) e **chi passa il turno** (`score.winner`, che include supplementari/rigori → lato `home`/`away`). I match sono mappati sugli stessi slot `S01`/`O01`/… del bracket.

L'esito di entrambi gli aggiornamenti viene mostrato in cima alla pagina; un pulsante **🔄 Refresh now** forza un nuovo scaricamento immediato (svuota entrambe le cache).

Gli stessi aggiornamenti avvengono all'apertura della pagina **Leaderboard**: prima di calcolare la graduatoria, classifiche gironi e risultati knockout vengono riscaricati, così i punteggi sono sempre basati sui dati più recenti.

> **Rate limit.** Il free tier consente 10 richieste/minuto e Streamlit ri-esegue lo script a ogni interazione. La chiamata all'API è quindi cachata con un **TTL di 60 secondi** (`st.cache_data`): la pagina è "live" a ogni visita ma i numerosi rerun entro un minuto riusano il dato già scaricato; il pulsante *Refresh now* svuota la cache quando serve un aggiornamento immediato. La logica condivisa vive in [`src/scraper/live_refresh.py`](src/scraper/live_refresh.py).

> Le classifiche vengono lette **direttamente dalle standings ufficiali** dell'API: posizione e punti sono già quelli FIFA (tie-breaker inclusi), non vengono ricalcolati partita per partita. I nomi delle squadre sono ricondotti ai nomi canonici di `fixtures.json` per restare coerenti con i pronostici e con il calcolo dei punteggi.

> Lo scraper copre le **classifiche dei gironi** e i **risultati knockout** (entrambi automatici all'apertura), oltre agli **accoppiamenti knockout** del bracket (su trigger Admin, vedi pagina Admin).

Comportamento in base alla risposta API:

| Caso | Risultato |
|---|---|
| Standings presenti e complete | Salva, mostra le classifiche con i punti e messaggio di successo |
| API senza standings o gironi a 0 partite (torneo non iniziato) | Salva l'ordine standard da `fixtures.json` e mostra un avviso |
| Dati parziali (gironi mancanti) | Non salva, mostra errore con i gironi mancanti |
| API key non configurata | Mostra errore con istruzioni di configurazione |

La provenienza delle classifiche gironi (`"api"`, `"default"`) viene salvata in `group_rankings_meta.json` e mostrata accanto al titolo della tabella. Se i dati provengono dall'ordine standard, viene mostrato un **avviso persistente** a ogni caricamento della pagina.

### Risultati knockout — sola lettura

I risultati delle fasi a eliminazione diretta sono mostrati in una tabella per fase (punteggio + squadra che passa il turno), ricavata da `results.json`. Non è previsto alcun inserimento manuale: la fonte è esclusivamente l'API. Una partita compare con punteggio e passaggio solo quando l'API la segna come conclusa.

---

## Statistiche — consenso tra i pronostici

La pagina **Statistics** (`3_Statistics.py`) mostra, per ogni fase, quanto si somigliano i
pronostici dei partecipanti. Per ciascun **evento** si misura il **gruppo più numeroso** che ha
fatto lo stesso pronostico (la "moda"), considerando solo chi ha compilato quell'evento (servono
almeno 2 partecipanti).

| Fase | Evento | Cosa conta come «uguale» |
|---|---|---|
| `Groups` | un girone (A–L) | classifica completa 1°→4° identica |
| Knockout | uno slot-partita | **chi passa il turno** (quale squadra dello slot) |

Per ogni fase la pagina mostra:

- **Quanti pronostici uguali** → numero di eventi con **unanimità totale** (tutti d'accordo)
- **Evento più condiviso** 🟢 e **evento più diviso** 🔴, con la previsione più comune
- una **tabella** di tutti gli eventi con il livello di consenso `X/N`

Per le sole fasi a eliminazione, sotto la tabella di consenso compare anche **«Who advances — by player»**: una griglia con una riga per slot-partita e una colonna per ogni giocatore che ha compilato la fase, che riassume la squadra indicata come **qualificata** da ciascuno (`—` se lo slot non è stato pronosticato). In ogni riga le celle che si discostano dalla **scelta modale** (la squadra più votata) sono evidenziate con uno sfondo tenue, così i pareri fuori dal coro saltano all'occhio. Se il tabellone non è ancora stato popolato da API la cella mostra `Team 1 / Team 2` invece del nome reale (vedi nota su Make Predictions).

> La fase a gironi richiede la classifica completa (i pronostici parziali sono esclusi dal conteggio).
> Gli slot knockout mostrano l'id (es. `S01`); una volta che l'Admin ha popolato gli accoppiamenti da API, accanto all'id compaiono le squadre reali (es. `S01 — France vs Sweden`). Il consenso knockout misura **chi i partecipanti danno per qualificato** in ciascuno slot.

La logica vive in [`src/scoring/statistics.py`](src/scoring/statistics.py) (funzioni pure, testate in
[`tests/test_statistics.py`](tests/test_statistics.py)).

---

## Pagina Admin

La pagina **Admin Settings** (`9_Admin_Settings.py`) è riservata all'amministratore e offre:

- **Gestione partecipanti**: elenco con copertura fasi (classifiche gironi + fasi knockout) ed eliminazione singola
- **Upload predictions from a file**: upload di un file `.json` esportato dall'app; i dati vengono uniti con quelli già presenti tramite merge automatico
- **Download predictions by phase**: esporta in JSON i pronostici di tutti i partecipanti per una fase selezionata
- **Populate knockout pairings from API**: scarica da football-data.org (endpoint `GET /competitions/WC/matches`) gli accoppiamenti reali di **una** fase a eliminazione diretta selezionata e popola gli slot di previsione con le squadre vere. Lo scarico è **manuale e per fase**: si popolano i sedicesimi quando il loro tabellone è definito, poi gli ottavi a sedicesimi conclusi, e così via. Se gli accoppiamenti di una fase non sono ancora determinati dall'API, l'operazione **avvisa e non salva nulla**. La fonte è il file `data/results/knockout_bracket.json`, letto dalle altre pagine senza ulteriori chiamate API.
- **Reset completo**: elimina tutti i pronostici e svuota il registry (richiede conferma esplicita)

> **Formati accettati dall'upload.** Il caricamento accetta sia l'export di un **singolo partecipante** (`{"name": ..., "match_predictions": ..., "group_rankings": ...}`) sia l'**export per fase** prodotto dal download (`{"phase": ..., "participants": [...]}`, con più partecipanti). In entrambi i casi i pronostici vengono uniti con quelli esistenti tramite merge incrementale per fase. Un file scaricato con «Download predictions by phase» può quindi essere ricaricato direttamente.

### Controllo accessi

Le operazioni di scrittura (upload e eliminazione) sono protette da accesso tramite email. Solo gli indirizzi autorizzati in `_AUTHORIZED_EMAILS` possono eseguirle.

---

## Dati persistenti (JSON)

```
data/participants/registry.json         ← registro partecipanti
data/predictions/mario_rossi.json       ← pronostici del partecipante
data/results/results.json               ← risultati reali knockout {match_id: {home_goals, away_goals, played}}
data/results/group_rankings.json        ← classifiche finali gironi {girone: [1°, 2°, 3°, 4°]}
data/results/group_standings.json       ← classifiche complete con punti/statistiche {girone: [{pos, squadra, punti, ...}]}
data/results/group_rankings_meta.json   ← provenienza classifiche: "api" | "default"
data/fixtures/fixtures.json             ← calendario ufficiale (non modificare a mano)
```

---

## Sistema di punteggio

Gironi e fasi a eliminazione diretta sono valutati con **due sistemi distinti e indipendenti**: non esiste un unico totale complessivo, ma una classifica per ciascuna fase. I criteri sono spiegati in dettaglio in app nella pagina **Rules** ([`pages/5_Rules.py`](pages/5_Rules.py)). La logica di calcolo vive in [`src/scoring/calculator.py`](src/scoring/calculator.py).

### Fase a gironi — punteggio da errore

La classifica gironi parte da un sistema a **errore**: per ogni squadra si calcola lo scarto assoluto tra posizione pronosticata e posizione reale; l'errore del partecipante è la somma su tutti i 12 gironi.

- Squadra al posto giusto → `0`
- Sbagliata di N posizioni → `N` (es. Francia pronosticata 1ª e arrivata 3ª → errore `2`)
- Squadra **non inserita** nel girone → penalità massima `3`

L'errore totale viene poi convertito in un **punteggio** tramite il fattore di correzione `(96 - errore_totale) / 9.6`: errore `0` → punteggio `10`, **più alto = meglio**. I partecipanti sono ordinati per **punteggio decrescente**. Nel dettaglio per girone ogni girone contribuisce con `(8 - errore_girone) / 9.6`, così la somma dei 12 gironi dà esattamente il punteggio totale.

### Fase a eliminazione diretta — sistema a criteri

| Criterio | Descrizione | Direzione |
|---|---|---|
| **C1 — Passaggio del turno** | Numero di partite in cui hai indovinato chi passa il turno | più alto = meglio |
| **C2 — Risultati esatti** | Numero di risultati esatti (spareggio) | più alto = meglio |
| **C3 — Errore diff. reti** | Somma degli scarti tra differenza reti prevista e reale (spareggio) | più basso = meglio |

Ordinamento: C1 decrescente → C2 decrescente → C3 crescente.

> Risultato esatto e passaggio del turno si pronosticano in modo **indipendente** e non devono per forza concordare (es. pareggio nei 90' ma qualificazione ai rigori). Il passaggio del turno reale (rigori/supplementari) si inserisce nella pagina **Real Results** accanto al punteggio.

---

## Configurazione (`config.yaml`)

Il file `config.yaml` esiste come riferimento, **ma i criteri di classifica attuali sono calcolati direttamente** in [`src/scoring/calculator.py`](src/scoring/calculator.py) (punteggio da errore per i gironi, criteri C1/C2/C3 per le fasi knockout) e non dipendono dai valori del file. Per cambiare le regole di punteggio occorre intervenire sul calcolatore, non solo sul `config.yaml`.
