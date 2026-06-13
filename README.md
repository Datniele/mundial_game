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
│   ├── 1_Inserisci_Pronostici.py      # Form di registrazione e inserimento pronostici
│   ├── 2_Risultati_Reali.py           # Scraping / inserimento manuale classifiche e risultati
│   ├── 3_Classifica.py                # Leaderboard e dettaglio punteggi
│   ├── 4_Regolamento.py               # Regolamento e criteri di punteggio (sola lettura)
│   └── 9_Impostazioni_Admin.py        # (Admin) Gestione partecipanti, upload JSON, reset completo
│
├── data/
│   ├── fixtures/fixtures.json         # Calendario normalizzato (non modificare a mano)
│   ├── participants/registry.json     # Registro partecipanti (creato automaticamente)
│   ├── predictions/                   # Un file .json per ogni partecipante
│   └── results/
│       ├── results.json               # Risultati reali knockout {match_id: {home_goals, away_goals, played}}
│       ├── group_rankings.json        # Classifiche finali dei gironi {girone: [1°, 2°, 3°, 4°]}
│       ├── group_standings.json       # Classifiche complete con punti e statistiche {girone: [{pos, squadra, punti, ...}]}
│       └── group_rankings_meta.json   # Provenienza classifiche gironi: "api" | "default" | "manual"
│
└── src/
    ├── models/                        # Dataclass: Match, Result, Prediction, Participant
    ├── scoring/                       # Motore di calcolo punteggi
    ├── storage/                       # Lettura/scrittura JSON su disco
    └── scraper/                       # Lettura classifiche gironi dalle standings di football-data.org
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
1. Ogni partecipante apre l'app e va su "Inserisci Pronostici"
         ↓
2. Inserisce nome e cognome → viene registrato automaticamente
         ↓
3. Seleziona la fase (Gironi / Sedicesimi / Ottavi / Quarti / Semifinali / Finale)
   e compila il form → clicca "Salva"
   (nelle classifiche gironi le squadre già selezionate non sono riproponibili)
         ↓
4. Quando le partite vengono giocate, l'admin va su "Risultati Reali"
   → scarica le classifiche via API oppure le inserisce manualmente
         ↓
5. Vai su "Classifica" per vedere la graduatoria aggiornata
```

---

## Inserimento pronostici — pagina partecipante

La pagina **Inserisci Pronostici** permette a ogni partecipante di registrarsi e compilare i pronostici direttamente dal browser.

### Cosa si pronostica per fase

| Fase | Contenuto |
|---|---|
| `Gironi` | Classifica completa 1°→4° per ognuno dei 12 gironi |
| `Sedicesimi` | 16 match slot: score previsto |
| `Ottavi` | 8 match slot: score previsto |
| `Quarti` | 4 match slot: score previsto |
| `Semifinali` | 2 match slot: score previsto |
| `Finale` | Finale 3° posto + Finale |

> Per la fase a gironi si inserisce **solo il posizionamento finale** (1°→4° posto), non i risultati delle singole partite.

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

La pagina **Risultati Reali** consente di caricare i dati reali del torneo in due modi:

### Scraping automatico (classifiche gironi)

Tramite il pulsante **Scarica classifiche da API-Football** lo scraper interroga football-data.org (endpoint `GET /competitions/WC/standings`) e popola `group_rankings.json` e `group_standings.json` automaticamente. Dopo ogni tentativo viene mostrata una tabella con le classifiche caricate (posizione **e punti**), visibile solo nella sessione corrente dopo aver premuto il pulsante.

> Le classifiche vengono lette **direttamente dalle standings ufficiali** dell'API: posizione e punti sono già quelli FIFA (tie-breaker inclusi), non vengono ricalcolati partita per partita. I nomi delle squadre sono ricondotti ai nomi canonici di `fixtures.json` per restare coerenti con i pronostici e con il calcolo dei punteggi.

Comportamento in base alla risposta API:

| Caso | Risultato |
|---|---|
| Standings presenti e complete | Salva, mostra le classifiche con i punti e messaggio di successo |
| API senza standings o gironi a 0 partite (torneo non iniziato) | Salva l'ordine standard da `fixtures.json` e mostra un avviso |
| Dati parziali (gironi mancanti) | Non salva, mostra errore con i gironi mancanti |
| API key non configurata | Mostra errore con istruzioni di configurazione |

La provenienza dei dati (`"api"`, `"default"`, `"manual"`) viene salvata in `group_rankings_meta.json` e mostrata accanto al titolo della tabella. Se i dati provengono dall'ordine standard, viene mostrato un **avviso persistente** a ogni caricamento della pagina.

### Inserimento manuale

- *Classifiche gironi*: 12 expander con 4 selectbox (1°→4°) per ogni girone
- *Risultati knockout*: score delle partite dalla fase sedicesimi in poi

> Per la fase a gironi vengono salvate solo le classifiche finali, non i risultati delle singole partite.

---

## Pagina Admin

La pagina **Impostazioni Admin** (`9_Impostazioni_Admin.py`) è riservata all'amministratore e offre:

- **Gestione partecipanti**: elenco con copertura fasi (classifiche gironi + fasi knockout) ed eliminazione singola
- **Carica pronostici da file**: upload di un file `.json` esportato dall'app; i dati vengono uniti con quelli già presenti tramite merge automatico
- **Reset completo**: elimina tutti i pronostici e svuota il registry (richiede conferma esplicita)

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
data/results/group_rankings_meta.json   ← provenienza classifiche: "api" | "default" | "manual"
data/fixtures/fixtures.json             ← calendario ufficiale (non modificare a mano)
```

---

## Sistema di punteggio

Gironi e fasi a eliminazione diretta sono valutati con **due sistemi distinti e indipendenti**: non esiste un unico totale complessivo, ma una classifica per ciascuna fase. I criteri sono spiegati in dettaglio in app nella pagina **Regolamento** ([`pages/4_Regolamento.py`](pages/4_Regolamento.py)). La logica di calcolo vive in [`src/scoring/calculator.py`](src/scoring/calculator.py).

### Fase a gironi — sistema a errore

La classifica gironi usa un sistema a **errore** (più basso = meglio). Per ogni squadra si calcola lo scarto assoluto tra posizione pronosticata e posizione reale; l'errore del partecipante è la somma su tutti i 12 gironi.

- Squadra al posto giusto → `0`
- Sbagliata di N posizioni → `N` (es. Francia pronosticata 1ª e arrivata 3ª → errore `2`)
- Squadra **non inserita** nel girone → penalità massima `3`

I partecipanti sono ordinati per **errore totale crescente**.

### Fase a eliminazione diretta — sistema a criteri

| Criterio | Descrizione | Direzione |
|---|---|---|
| **C1 — Vincitori corretti** | Numero di partite in cui hai indovinato chi passa il turno (esito) | più alto = meglio |
| **C2 — Risultati esatti** | Numero di risultati esatti (spareggio) | più alto = meglio |
| **C3 — Errore diff. reti** | Somma degli scarti tra differenza reti prevista e reale (spareggio) | più basso = meglio |

Ordinamento: C1 decrescente → C2 decrescente → C3 crescente.

---

## Configurazione (`config.yaml`)

Il file `config.yaml` esiste come riferimento, **ma i criteri di classifica attuali sono calcolati direttamente** in [`src/scoring/calculator.py`](src/scoring/calculator.py) (sistema a errore per i gironi, criteri C1/C2/C3 per le fasi knockout) e non dipendono dai valori del file. Per cambiare le regole di punteggio occorre intervenire sul calcolatore, non solo sul `config.yaml`.
