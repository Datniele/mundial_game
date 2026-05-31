# Mondiali 2026 — Gestione Pronostici

App Streamlit per raccogliere i pronostici dei partecipanti sulle partite dei Mondiali 2026, confrontarli con i risultati reali e produrre una classifica automatica.

---

## Struttura del progetto

```
mondiali/
├── app.py                        # Home Streamlit (entry point)
├── config.yaml                   # Punteggi configurabili
├── requirements.txt
├── calendario_gironi.json        # Calendario ufficiale (sorgente dati)
│
├── pages/
│   ├── 1_Carica_Pronostici.py   # Upload file Excel partecipanti
│   ├── 2_Risultati_Reali.py     # Scraping / inserimento manuale risultati
│   ├── 3_Classifica.py          # Leaderboard e dettaglio punteggi
│   └── 4_Configurazione.py      # Editor regole di punteggio
│
├── data/
│   ├── fixtures/fixtures.json   # Calendario normalizzato (generato da calendario_gironi.json)
│   ├── predictions/             # Un file .json per ogni partecipante
│   └── results/
│       ├── results.json         # Risultati reali scrappati o inseriti
│       └── group_rankings.json  # Classifiche finali dei gironi
│
├── scripts/
│   └── create_template.py       # Genera template_pronostici.xlsx
│
└── src/
    ├── models/                  # Dataclass: Match, Result, Prediction, Participant
    ├── scoring/                 # Regole (config.yaml) + motore di calcolo
    ├── parsers/                 # Parsing file Excel → oggetti Python
    ├── storage/                 # Lettura/scrittura JSON su disco
    └── scraper/                 # Scraping risultati reali (da completare)
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

### 3. Generare il template Excel

```powershell
python scripts\create_template.py
```

Produce `template_pronostici.xlsx` nella root del progetto. Distribuiscilo ai partecipanti.

### 4. Avviare l'app

```powershell
streamlit run app.py
```

---

## Workflow di utilizzo

```
1. Distribuisci template_pronostici.xlsx a tutti i partecipanti
         ↓
2. Raccogli i file compilati (es. mario_rossi.xlsx)
         ↓
3. Carica ogni file su "Carica Pronostici" nell'app
         ↓
4. Quando le partite vengono giocate, vai su "Risultati Reali"
   → inserisci il sito di scraping OPPURE inserisci i risultati manualmente
         ↓
5. Vai su "Classifica" e clicca "Ricalcola punteggi"
```

---

## Template Excel — formato atteso

Il file distribuito ai partecipanti contiene **8 fogli**. I nomi dei fogli sono fissi e non devono essere modificati.

| Foglio | Contenuto | Campi da compilare |
|---|---|---|
| `ISTRUZIONI` | Testo fisso con le regole | — |
| `GIRONI` | 72 partite pre-compilate (squadre fisse) | `Gol Casa`, `Gol Ospite` |
| `CLASSIFICHE_GIRONI` | 12 righe (gironi A–L) | `1° Posto`, `2° Posto` |
| `SEDICESIMI` | 16 slot | `Squadra 1`, `Squadra 2`, `Gol Sq1`, `Gol Sq2` |
| `OTTAVI` | 8 slot | idem |
| `QUARTI` | 4 slot | idem |
| `SEMIFINALI` | 2 slot | idem |
| `3_POSTO` | 1 slot (finale 3° posto) | idem |
| `FINALE` | 1 slot | idem |

> Il file deve essere rinominato con il nome del partecipante prima di caricarlo: `mario_rossi.xlsx`. Il nome del file diventa l'identificativo nell'app.

### Colonne foglio `GIRONI`

| ID Partita | Girone | Squadra Casa | Squadra Ospite | **Gol Casa** | **Gol Ospite** |
|---|---|---|---|---|---|
| A1 | A | Mexico | South Africa | *(da compilare)* | *(da compilare)* |
| A2 | A | South Korea | Czechia | | |
| ... | | | | | |

Le colonne **Gol Casa** e **Gol Ospite** sono evidenziate in giallo nel template.

---

## Sistema di punteggio

I punteggi sono configurabili da `config.yaml` o dalla pagina **Configurazione** dell'app.

### Fase a gironi

| Evento | Punti (default) |
|---|---|
| Risultato esatto (es. 2-1) | **3** |
| Esito corretto (V/P/N) | **1** |
| Classifica girone identica (1° e 2° corretti nell'ordine giusto) | **5** |
| Classifica girone parziale (1° e 2° giusti ma invertiti, oppure solo uno corretto) | **2** |

### Fase a eliminazione diretta

| Evento | Punti (default) |
|---|---|
| Chi passa il turno (vincitore corretto) | **2** |
| Risultato esatto | **4** |

---

## Dati persistenti (JSON)

Tutti i dati vengono salvati come file JSON in `data/`:

```
data/predictions/mario_rossi.json     ← pronostici del partecipante
data/results/results.json             ← risultati reali {match_id: {home_goals, away_goals, played}}
data/results/group_rankings.json      ← classifiche finali {girone: [1°, 2°, 3°]}
data/fixtures/fixtures.json           ← calendario ufficiale (non modificare a mano)
```

---

## Aggiungere lo scraper

Il file [src/scraper/results_scraper.py](src/scraper/results_scraper.py) contiene due funzioni stub da implementare:

```python
def scrape_results(url: str) -> dict[str, dict]:
    # deve restituire: {"A1": {"home_goals": 2, "away_goals": 1, "played": True}, ...}

def scrape_group_rankings(url: str) -> dict[str, list]:
    # deve restituire: {"A": ["Mexico", "South Korea"], ...}
```

Una volta comunicato il sito sorgente, implementare queste due funzioni. Le chiavi del dizionario devono corrispondere agli ID in `data/fixtures/fixtures.json`.

---

## Configurazione punteggi (`config.yaml`)

```yaml
scoring:
  group_stage:
    exact_score: 3
    correct_outcome: 1
    group_ranking_exact: 5
    group_ranking_partial: 2
  knockout:
    correct_winner: 2
    exact_score: 4
```

Modificabile anche dalla pagina **Configurazione** dell'app senza toccare il file.
