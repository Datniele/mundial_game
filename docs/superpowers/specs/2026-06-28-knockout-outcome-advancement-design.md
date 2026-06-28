# Esito 90' e passaggio del turno nei pronostici knockout

**Data:** 2026-06-28
**Stato:** approvato (design)

## Obiettivo

Nella pagina **Make Predictions**, per ogni partita delle fasi a eliminazione diretta,
il partecipante deve poter indicare tre valori **indipendenti**:

1. **Risultato esatto** a 90' (già presente: `home_goals` / `away_goals`)
2. **Esito 90'** — `1` / `X` / `2`
3. **Chi passa il turno** — Team 1 / Team 2

I tre valori **non devono essere per forza concordanti**: es. punteggio `2-2`, esito `X`,
ma passa il turno il Team 2 (ai rigori).

## Impatto sullo scoring

I criteri della fase a eliminazione diretta diventano:

| | Criterio | Confronto | Direzione |
|---|---|---|---|
| **C1** | Passaggio del turno corretto | `pred.advances == result.advances` | desc |
| **C2** | Esito 90' corretto | `pred.outcome_90 == result.outcome` (esito reale derivato dal punteggio 90') | desc |
| **C3** | Errore differenza reti | `Σ \|diff_prevista − diff_reale\|` | asc |

Ordinamento: `(-C1, -C2, C3)`.

> Il vecchio criterio **"numero di risultati esatti"** viene **rimosso**. Il risultato esatto
> previsto contribuisce solo tramite C3 (errore differenza reti).

## Modello dati

### `MatchPrediction` (`src/models/match.py`)

Due campi nuovi, opzionali:

- `outcome_90: Optional[Outcome] = None` — esito a 90' (riuso enum `Outcome`: `HOME`/`DRAW`/`AWAY`, resi come `1`/`X`/`2`).
- `advances: Optional[str] = None` — chi passa il turno, memorizzato come **lato**: `"home"` o `"away"`.

> Il passaggio è memorizzato come lato (non come nome squadra) per restare robusto quando lo slot
> ha squadre ancora `TBD` (non determinate dal bracket).

La property derivata `outcome` resta (l'esito ricavato dal punteggio) e continua a essere usata dove serve.

### `Result` (`src/models/match.py`)

Campo nuovo, opzionale:

- `advances: Optional[str] = None` — chi è passato davvero (`"home"`/`"away"`).

L'esito reale a 90' resta la property `outcome` derivata dal punteggio: non serve esplicitarlo.

### Serializzazione

- `Participant.to_dict` / `from_dict` (`src/models/participant.py`): includono `outcome_90` e `advances`.
  - `outcome_90` salvato come stringa `"1"`/`"X"`/`"2"` (o `None`).
  - `advances` salvato come `"home"`/`"away"` (o `None`).
- `Result` in `json_storage.save_results` / `load_results`: l'entry knockout in `results.json`
  acquisisce `"advances": "home"|"away"` (assente → `None`).

### Migrazione

Nessuna conversione dei dati esistenti. I pronostici/risultati salvati prima della feature hanno
`outcome_90` / `advances` a `None`: semplicemente non guadagnano C1/C2 e non entrano nel consenso.

## UI — Make Predictions (`pages/1_Make_Predictions.py`)

Per ogni riga-partita knockout, oltre ai due `number_input` del punteggio, due controlli
**sempre manuali (nessun auto-fill dal punteggio)**:

- radio **Esito 90'**: opzioni `1` / `X` / `2`.
- radio **Passa il turno**: due opzioni etichettate con i nomi squadra se lo slot è `determined`
  nel bracket, altrimenti `Team 1` / `Team 2`; valore salvato = `home` / `away`.

Default di rendering: se esiste un pronostico salvato, i radio mostrano il valore salvato;
altrimenti nessuna preselezione forzata coerente col punteggio (l'utente sceglie).

`new_preds[match_id]` trasporta anche `outcome_90` e `advances`; `_save_knockout` li passa al
costruttore `MatchPrediction`.

Layout: la griglia a colonne attuale (`Team1 | g1 | – | g2 | Team2`) viene estesa con una
riga/colonna aggiuntiva per i due radio sotto ogni partita (per non comprimere troppo la riga).

## UI — Real Results (`pages/2_Real_Results.py`)

Per ogni slot knockout, accanto a punteggio 90' e checkbox **Played**, un radio
**Chi passa**: Team 1 / Team 2 (etichette dal bracket se disponibili), salvato come
`"advances": "home"|"away"` in `new_results[match_id]`.

Il radio è significativo solo se `played` è spuntato; quando si salva, `advances` viene incluso
nell'entry solo per le partite giocate.

## Scoring (`src/scoring/calculator.py`)

Riscrittura di `score_knockout_round` e di `KnockoutRoundScore`:

- `KnockoutRoundScore`: `correct_winners → correct_advances`, `exact_scores → correct_outcomes`,
  `goal_diff_error` invariato.
- C1: `correct_advances += 1` se `pred.advances is not None and result.advances is not None and pred.advances == result.advances`.
- C2: `correct_outcomes += 1` se `pred.outcome_90 is not None and pred.outcome_90 == result.outcome`.
- C3: errore differenza reti (invariato).
- Ordinamento: `key=lambda s: (-s.correct_advances, -s.correct_outcomes, s.goal_diff_error)`.

## Consumatori da aggiornare

- **Leaderboard** (`pages/4_Leaderboard.py`): etichette colonne →
  `C1 — Who advances`, `C2 — Outcome (90')`, `C3 — Goal-diff error`, e nomi campo aggiornati.
- **Statistics** (`pages/3_Statistics.py`): per il knockout si mostra **una sola metrica**:
  consenso sul **passaggio del turno**. Rimosse dalla pagina le metriche *outcome* ed *exact*.
  - `src/scoring/statistics.py`: `knockout_consensus` aggiunge la metric `"advances"`
    (raggruppa per `pred.advances`, ignorando i partecipanti con `advances is None`).
    Le metric `"outcome"` ed `"exact"` restano nella funzione (non rotte i test esistenti) ma
    non sono più usate dalla pagina.
  - Formatter dedicato che rende `"home"`/`"away"` come nome squadra (dal bracket) o `Team 1`/`Team 2`.
- **Rules** (`pages/5_Rules.py`) e **README.md**: tabella criteri C1/C2/C3 aggiornata e descrizione
  della pagina Make Predictions / Statistics allineata.

## Test

- `tests/test_calculator.py` (nuovo): casi sul `score_knockout_round` con i tre valori
  **discordanti** — verifica che C1 (passaggio), C2 (esito esplicito) e C3 (diff. reti) siano
  indipendenti e che l'ordinamento rispetti `(-C1, -C2, C3)`. Caso con campi `None` che non
  guadagnano C1/C2.
- `tests/test_statistics.py`: aggiunta di un test per la metric `"advances"`; i test esistenti
  su `"outcome"`/`"exact"` restano validi.

## Fuori scope

- Auto-fill dei radio dal punteggio inserito (deciso: input manuali).
- Conversione/migrazione dei pronostici e risultati storici.
- Popolamento di `advances` reale via API (resta inserimento manuale in Real Results).
