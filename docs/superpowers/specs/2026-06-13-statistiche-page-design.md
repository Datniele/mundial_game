# Design — Pagina "Statistiche"

Data: 2026-06-13

## Obiettivo

Aggiungere una pagina **Statistiche** (tra la pagina 2 e l'attuale 3) che, per ogni fase
del gioco (gironi, sedicesimi, ottavi, quarti, semifinali, finale), mostra il livello di
**consenso** tra i pronostici dei partecipanti:

- quanti pronostici uguali sono stati fatti → **numero di eventi con unanimità totale** nella fase;
- l'evento con il **numero più alto** di pronostici uguali (più condiviso);
- l'evento con il **numero più basso** di pronostici uguali (più diviso).

## Definizioni concordate

- **Fase a gironi**: l'"evento" è il girone (A–L). Due pronostici sono "uguali" solo se la
  **classifica completa** (1°→4°) coincide in tutte le posizioni.
- **Fasi a eliminazione**: l'"evento" è lo slot-partita (es. `S01`, `O01`, `F01`).
  Si calcolano **due metriche**: consenso sull'**esito** (1/X/2) e consenso sul
  **risultato esatto** (punteggio identico).
- **Metrica di consenso per evento**: dimensione del **gruppo più numeroso** di partecipanti
  con lo stesso pronostico (la "moda"), sul denominatore di chi ha compilato quell'evento.
- **Unanimità**: `top_count == total` con `total ≥ 2`.
- Un evento è considerato solo se `total ≥ 2` (serve almeno una coppia per parlare di "uguali").
- I pronostici gironi **parziali** (qualche posizione non valorizzata) sono esclusi dal conteggio.

## Ordinamento pagine

Streamlit ordina le pagine dal prefisso numerico del filename; non esistono link interni
`page_link`/`switch_page` tra le pagine, quindi rinominare i file cambia solo l'ordine in sidebar.

- `pages/3_Statistiche.py` ← **nuova**
- `pages/3_Classifica.py` → `pages/4_Classifica.py`
- `pages/4_Regolamento.py` → `pages/5_Regolamento.py`
- `pages/9_Impostazioni_Admin.py` → invariata

## Logica di calcolo — `src/scoring/statistics.py`

Funzioni pure (nessuna dipendenza da Streamlit), testabili in isolamento.

```python
@dataclass
class EventConsensus:
    label: str            # es. "A" oppure "S01"
    total: int            # partecipanti che hanno compilato l'evento
    top_count: int        # dimensione del gruppo più numeroso
    top_value: object     # previsione più comune (lista per gironi, tupla/str per knockout)

    @property
    def is_unanimous(self) -> bool:
        return self.total >= 2 and self.top_count == self.total
```

- `group_consensus(participants) -> list[EventConsensus]`
  - per ogni girone, considera solo partecipanti con classifica completa (4 valori non None);
  - chiave di raggruppamento = tupla delle 4 squadre; `top_value` = lista delle 4 squadre più gettonata.
- `knockout_consensus(participants, match_ids, metric) -> list[EventConsensus]`
  - `metric="outcome"`: chiave = esito (`home`/`away`/`draw`);
  - `metric="exact"`: chiave = `(home_goals, away_goals)`.
  - considera solo gli slot presenti nei `match_predictions` del partecipante.

Helper di selezione su una lista di `EventConsensus`:
- `most_shared(events)` / `least_shared(events)` → eventi con `top_count` max/min (su quelli con `total ≥ 2`);
- `unanimous_count(events)` → numero di eventi unanimi.

## UI — `pages/3_Statistiche.py`

Stesso pattern di `Classifica`: tab `Fase Gironi` + `Sedicesimi / Ottavi / Quarti / Semifinali / Finale`
(la tab Finale aggrega `finale_3posto` + `finale`).

Per ogni tab:
- **Riepilogo** in cima con `st.metric`: n° eventi con unanimità totale (per il knockout due metriche:
  unanimi per esito e per risultato esatto).
- **Callout**: evento più condiviso 🟢 e più diviso 🔴, con valore `X/N` e previsione.
- **Tabella** ordinabile di tutti gli eventi: per i gironi `Girone | Più condiviso (X/N) | Classifica più comune`;
  per il knockout `Slot | Esito (X/N) | Esito comune | Risultato (X/N) | Risultato comune`.
- Gestione casi vuoti come in `Classifica` (nessun partecipante / nessun pronostico nella fase).

Rappresentazione `top_value`:
- gironi → `Team1 › Team2 › Team3 › Team4`;
- knockout esito → `1 (casa)` / `X (pareggio)` / `2 (trasferta)`; risultato → `home-away`.
  Gli slot mostrano l'id (es. `S01`) perché le squadre non sono note finché non escono i risultati.

## Test — `tests/test_statistics.py`

Test unitari per `statistics.py`: unanimità, divisione totale, pronostici parziali esclusi,
evento con `< 2` partecipanti ignorato, selezione most/least shared.

## README

Aggiornare la sezione "Struttura del progetto" e la tabella pagine con la nuova Statistiche
e i nuovi numeri (Classifica→4, Regolamento→5).
