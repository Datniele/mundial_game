# Auto-popolamento bracket knockout da football-data.org

**Data:** 2026-06-28
**Stato:** approvato (design), in attesa del piano di implementazione

## Obiettivo

Permettere ai partecipanti di pronosticare le fasi a eliminazione diretta (sedicesimi,
ottavi, quarti, semifinali, finali) sugli **accoppiamenti reali** delle squadre, invece
che su slot generici con squadre "TBD" scelte a mano da una tendina.

Gli accoppiamenti vengono recuperati dall'endpoint `GET /competitions/WC/matches` di
football-data.org e salvati su disco. Lo scarico avviene **solo su trigger esplicito
dell'Admin**, **una fase per volta**: prima i sedicesimi, poi (a sedicesimi conclusi) gli
ottavi, e così via.

## Decisioni di design (dal brainstorming)

1. **Auto-popolamento delle squadre negli slot** (non scelta manuale, non solo risultati).
   Il partecipante pronostica solo il punteggio sulle squadre reali.
2. **Solo accoppiamenti, non risultati.** I risultati knockout restano a inserimento
   manuale come oggi. L'API serve solo a riempire le coppie di squadre.
3. **Approccio A completo — bracket persistito.** I nomi reali compaiono dove utili in
   Make Predictions, Real Results, Statistics e Leaderboard (al posto del nudo `S01`).
4. **Trigger solo Admin, per fase.** Niente fetch automatico all'apertura delle pagine.
   Le pagine non-admin solo leggono il bracket dal disco.
5. **Avvisa e non salva** se la fase non è ancora determinata dall'API: si salva solo
   quando **tutti** gli accoppiamenti della fase hanno entrambe le squadre note.

## Dati API verificati (live, 2026-06-28)

`GET /competitions/WC/matches` restituisce 104 partite. Distribuzione per `stage`:

| API stage        | Fase interna   | Prefisso slot | N. slot |
|------------------|----------------|---------------|---------|
| `GROUP_STAGE`    | group          | —             | 72      |
| `LAST_32`        | sedicesimi     | S             | 16      |
| `LAST_16`        | ottavi         | O             | 8       |
| `QUARTER_FINALS` | quarti         | Q             | 4       |
| `SEMI_FINALS`    | semifinali     | SF            | 2       |
| `THIRD_PLACE`    | finale_3posto  | 3P            | 1       |
| `FINAL`          | finale         | F             | 1       |

Ogni partita knockout espone: `id` (intero, stabile), `utcDate`, `status`,
`homeTeam.name`, `awayTeam.name`, `score.fullTime`. Per le partite di fasi non ancora
determinate `homeTeam.name` e `awayTeam.name` sono `null`, ma `id` e `utcDate` sono
**sempre presenti**.

## Architettura

Nuovo modulo `src/scraper/knockout_bracket.py`, affiancato a `results_scraper.py`. Riusa:
- header/auth (`X-Auth-Token`, `API_FOOTBALL_KEY`, base URL `…/v4`);
- normalizzazione nomi squadra (`_normalize`, `_TEAM_ALIASES`) per ricondurre i nomi API
  ai nomi canonici di `fixtures.json`.

### Mapping stage → fase interna

Costante `STAGE_TO_PHASE` nel modulo:
```python
STAGE_TO_PHASE = {
    "LAST_32": "sedicesimi",
    "LAST_16": "ottavi",
    "QUARTER_FINALS": "quarti",
    "SEMI_FINALS": "semifinali",
    "THIRD_PLACE": "finale_3posto",
    "FINAL": "finale",
}
```
La struttura inversa (fase → prefisso, n. slot) viene da `get_knockout_slots()` in
`src/models/tournament.py`, già esistente.

### Assegnazione slot — deterministica e stabile

Per una data fase:
1. Filtra le partite con lo `stage` corrispondente.
2. **Ordina per `api_id` crescente** (chiave più stabile: gli id non cambiano; `utcDate`
   può variare per rinvii). La prima partita → slot `01`, la seconda → `02`, ecc.
3. Costruisce gli slot id con lo stesso formato del resto del codice: `f"{prefix}{i:02d}"`.

Lo slot id resta la chiave interna stabile. L'ordine **di visualizzazione** all'utente
è invece per `utc_date` (cronologico), così le partite appaiono in ordine di calendario.

### Funzioni del modulo

```python
def fetch_matches() -> dict
    # GET /competitions/WC/matches; gestisce key mancante / 403 / 429 / timeout

def build_phase_bracket(payload: dict, phase: str) -> dict[str, dict]
    # funzione pura, testabile: restituisce {slot_id: {home, away, utc_date, api_id, determined}}
    # per la fase richiesta, con nomi normalizzati. determined = (home e away non null)
```

## Storage

`data/results/knockout_bracket.json` — nuova fonte di verità:
```json
{
  "S01": {"home": "France", "away": "Sweden", "utc_date": "2026-06-30T21:00:00Z",
          "api_id": 537416, "determined": true},
  "O01": {"home": null, "away": null, "utc_date": "2026-07-04T17:00:00Z",
          "api_id": 537376, "determined": false}
}
```

Aggiunte a `src/storage/json_storage.py`:
- `KNOCKOUT_BRACKET_PATH`
- `save_knockout_bracket(bracket: dict) -> None`
- `load_knockout_bracket() -> dict` (ritorna `{}` se il file non esiste)
- `merge_knockout_bracket(phase_bracket: dict) -> None` — carica l'esistente, sovrascrive
  solo gli slot della fase passata, preserva le altre fasi, salva.

## Wrapper di refresh

In `src/scraper/live_refresh.py` (riuso `RefreshOutcome`):
```python
def refresh_knockout_bracket_from_api(phase: str) -> RefreshOutcome
```
Logica:
1. `payload = fetch_matches()`
2. `bracket = build_phase_bracket(payload, phase)`
3. Se la fase è assente dall'API o **non tutti** gli slot hanno `determined=true`
   → `RefreshOutcome(status="error", message="Accoppiamenti non ancora determinati")`,
   **non salva**.
4. Altrimenti `merge_knockout_bracket(bracket)` → `RefreshOutcome(status="api", …)`.
5. Eccezioni (key mancante, 403, 429, timeout, rete) → `RefreshOutcome(status="error", …)`.

Stati usati: `"api"` (successo) e `"error"`. (`default`/`partial` non si applicano qui.)

## UI

### Admin — nuova sezione in `pages/9_Admin_Settings.py`
Protetta dall'email autorizzata (`_AUTHORIZED_EMAILS`), come le altre scritture.
- Selectbox con le 6 fasi knockout (etichette UI: Round of 32 → Final).
- Pulsante **"⬇️ Popola accoppiamenti da API"** → chiama `refresh_knockout_bracket_from_api(phase)`.
- Esito mostrato:
  - ✅ `N` accoppiamenti popolati + anteprima (tabella `slot → home vs away`, ordinata per data);
  - ⚠️/❌ messaggio di errore (fase non ancora determinata, key mancante, rate limit…),
    **senza scrivere nulla**.
- Riquadro di stato: quali fasi del bracket sono già popolate (lette da `load_knockout_bracket()`).

### Make Predictions — `pages/1_Make_Predictions.py`
- Carica il bracket con `load_knockout_bracket()` (nessuna chiamata API).
- Per ogni slot knockout:
  - se `determined=true`: mostra **"home vs away"** in sola lettura + i due `number_input`
    per il punteggio. La previsione resta `{home_goals, away_goals}` sullo stesso `match_id`.
  - altrimenti: **fallback** alle tendine TBD attuali (comportamento odierno invariato).
- La `home` dello slot coincide sempre con la `home` dell'API.

### Real Results / Statistics / Leaderboard
- Helper condiviso `slot_label(match_id, bracket)` → `"S01 — France vs Sweden"` se nota,
  altrimenti `"S01"`. Usato dove oggi appare l'ID slot nudo.

## Coerenza con lo scoring

Nessun impatto sul motore di calcolo. C1/C2/C3 operano su `home_goals`/`away_goals` per
`match_id`. Mappando sempre home-API → home-slot, previsione e risultato reale condividono
lo stesso orientamento. Il formato dei file di previsione non cambia.

## Gestione errori e regressioni

- API key mancante / 403 / 429 / timeout → esito di errore in pagina Admin; il bracket su
  disco resta invariato.
- Fase non ancora determinata → avviso, nessuna scrittura.
- Stage con meno partite del previsto → trattato come "non determinato" (avvisa e non salva),
  per evitare bracket parziali.
- Le pagine non-admin non chiamano mai l'API: se il bracket è assente o incompleto,
  ricadono sul comportamento TBD odierno. Nessuna regressione.

## Test

`tests/test_knockout_bracket.py`, funzioni pure su un payload campione salvato in
`tests/fixtures/wc_matches_sample.json` (nessuna chiamata di rete):
- mapping stage → fase corretto;
- assegnazione slot deterministica per `api_id` (stabile a fronte di riordino del payload);
- normalizzazione nomi squadra (alias, accenti);
- `determined` corretto (true con entrambe le squadre, false con `null`);
- una fase con squadre `null` → `build_phase_bracket` la marca non-determinata;
- merge: popolare una fase non altera le altre.

## File toccati

**Nuovi**
- `src/scraper/knockout_bracket.py`
- `tests/test_knockout_bracket.py`
- `tests/fixtures/wc_matches_sample.json`

**Modificati**
- `src/storage/json_storage.py` (path + save/load/merge bracket)
- `src/scraper/live_refresh.py` (`refresh_knockout_bracket_from_api`)
- `pages/9_Admin_Settings.py` (sezione trigger per fase)
- `pages/1_Make_Predictions.py` (auto-popolamento slot determinati, fallback TBD)
- `pages/2_Real_Results.py`, `pages/3_Statistics.py`, `pages/4_Leaderboard.py` (`slot_label`)
- `README.md` (documentazione della nuova feature e del workflow Admin)

## Fuori scope

- Auto-fetch dei risultati knockout (restano manuali).
- Fetch automatico all'apertura delle pagine non-admin.
- Modifiche al motore di punteggio.
