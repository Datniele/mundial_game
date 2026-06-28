# Auto-popolamento bracket knockout da API — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Recuperare gli accoppiamenti reali delle fasi knockout da football-data.org (su trigger Admin, una fase per volta) e popolare automaticamente le squadre negli slot di previsione, mostrandole anche nelle pagine di consultazione.

**Architecture:** Nuovo modulo `src/scraper/knockout_bracket.py` chiama `GET /competitions/WC/matches`, raggruppa per `stage`, assegna ogni partita a uno slot fisso ordinando per `api_id`, normalizza i nomi e produce un dict `{slot_id: {home, away, utc_date, api_id, determined}}`. Un wrapper in `live_refresh.py` salva il bracket (merge per fase) solo se tutti gli accoppiamenti sono determinati. Le pagine Streamlit leggono il bracket da disco; solo la pagina Admin lo scarica.

**Tech Stack:** Python, Streamlit, `requests`, `python-dotenv`, pytest. Tutti i test girano dalla root con `python -m pytest`.

---

## File Structure

**Nuovi**
- `src/scraper/knockout_bracket.py` — fetch `/matches`, `build_phase_bracket`, `slot_label`, `STAGE_TO_PHASE`
- `tests/test_knockout_bracket.py` — test puri su payload campione
- `tests/fixtures/wc_matches_sample.json` — payload `/matches` campione (no rete)

**Modificati**
- `src/storage/json_storage.py` — path + `save/load/merge_knockout_bracket`
- `src/scraper/live_refresh.py` — `refresh_knockout_bracket_from_api(phase)`
- `pages/9_Admin_Settings.py` — sezione trigger per fase
- `pages/1_Make_Predictions.py` — auto-popolamento slot determinati, fallback TBD
- `pages/2_Real_Results.py` — prefill nomi squadra knockout dal bracket
- `pages/3_Statistics.py` — etichetta slot con nomi reali
- `README.md` — documentazione feature + workflow Admin

> **Nota su Leaderboard:** la tab knockout di `pages/4_Leaderboard.py` mostra solo punteggi aggregati per giocatore (C1/C2/C3), **non** gli ID slot. Quindi non richiede modifiche — lo segnaliamo qui per evitare di cercare un punto di integrazione inesistente.

---

## Task 1: Storage del bracket (save / load / merge)

**Files:**
- Modify: `src/storage/json_storage.py`
- Test: `tests/test_knockout_bracket.py` (creato qui, ampliato nei task successivi)

- [ ] **Step 1: Write the failing test**

Crea `tests/test_knockout_bracket.py`:

```python
import importlib

from src.storage import json_storage


def _isolate_bracket(tmp_path, monkeypatch):
    """Reindirizza il file del bracket in una cartella temporanea."""
    path = tmp_path / "knockout_bracket.json"
    monkeypatch.setattr(json_storage, "KNOCKOUT_BRACKET_PATH", path)
    return path


def test_load_bracket_missing_returns_empty(tmp_path, monkeypatch):
    _isolate_bracket(tmp_path, monkeypatch)
    assert json_storage.load_knockout_bracket() == {}


def test_save_then_load_bracket_roundtrip(tmp_path, monkeypatch):
    _isolate_bracket(tmp_path, monkeypatch)
    bracket = {"S01": {"home": "France", "away": "Sweden",
                       "utc_date": "2026-06-30T21:00:00Z",
                       "api_id": 537416, "determined": True}}
    json_storage.save_knockout_bracket(bracket)
    assert json_storage.load_knockout_bracket() == bracket


def test_merge_bracket_preserves_other_phases(tmp_path, monkeypatch):
    _isolate_bracket(tmp_path, monkeypatch)
    json_storage.save_knockout_bracket(
        {"S01": {"home": "A", "away": "B", "utc_date": None,
                 "api_id": 1, "determined": True}}
    )
    json_storage.merge_knockout_bracket(
        {"O01": {"home": "C", "away": "D", "utc_date": None,
                 "api_id": 2, "determined": True}}
    )
    merged = json_storage.load_knockout_bracket()
    assert set(merged.keys()) == {"S01", "O01"}
    assert merged["S01"]["home"] == "A"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_knockout_bracket.py -v`
Expected: FAIL — `AttributeError: module 'src.storage.json_storage' has no attribute 'KNOCKOUT_BRACKET_PATH'` (e `load_knockout_bracket` non definita).

- [ ] **Step 3: Write minimal implementation**

In `src/storage/json_storage.py`, dopo la riga `PHASE_LOCKS_PATH = ...` (riga 16) aggiungi la costante:

```python
KNOCKOUT_BRACKET_PATH = DATA_DIR / "results" / "knockout_bracket.json"
```

In fondo al file (dopo `is_phase_locked`, riga 218) aggiungi:

```python
# ---------- Knockout bracket (accoppiamenti reali da API) ----------

def save_knockout_bracket(bracket: Dict[str, dict]) -> None:
    """Salva l'intero bracket knockout {slot_id: {home, away, utc_date, api_id, determined}}."""
    _ensure_dirs()
    with open(KNOCKOUT_BRACKET_PATH, "w", encoding="utf-8") as f:
        json.dump(bracket, f, ensure_ascii=False, indent=2)


def load_knockout_bracket() -> Dict[str, dict]:
    """Restituisce il bracket knockout salvato, o {} se non disponibile."""
    if not KNOCKOUT_BRACKET_PATH.exists():
        return {}
    with open(KNOCKOUT_BRACKET_PATH, encoding="utf-8") as f:
        return json.load(f)


def merge_knockout_bracket(phase_bracket: Dict[str, dict]) -> None:
    """Sovrascrive solo gli slot passati (di una fase), preservando le altre fasi."""
    existing = load_knockout_bracket()
    existing.update(phase_bracket)
    save_knockout_bracket(existing)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_knockout_bracket.py -v`
Expected: PASS (3 test).

- [ ] **Step 5: Commit**

```bash
git add src/storage/json_storage.py tests/test_knockout_bracket.py
git commit -m "feat: storage del bracket knockout (save/load/merge)"
```

---

## Task 2: Modulo knockout_bracket — build_phase_bracket e slot_label

**Files:**
- Create: `src/scraper/knockout_bracket.py`
- Create: `tests/fixtures/wc_matches_sample.json`
- Test: `tests/test_knockout_bracket.py` (ampliato)

- [ ] **Step 1: Create the sample payload fixture**

Crea `tests/fixtures/wc_matches_sample.json` (id volutamente non ordinati per testare il sort per `api_id`; "Korea Republic" verifica la normalizzazione alias → "South Korea"; gli ottavi hanno squadre `null`):

```json
{
  "matches": [
    {"id": 200, "stage": "LAST_32", "utcDate": "2026-06-30T21:00:00Z", "status": "TIMED",
     "homeTeam": {"name": "France"}, "awayTeam": {"name": "Sweden"}},
    {"id": 100, "stage": "LAST_32", "utcDate": "2026-06-28T19:00:00Z", "status": "IN_PLAY",
     "homeTeam": {"name": "Korea Republic"}, "awayTeam": {"name": "Brazil"}},
    {"id": 300, "stage": "LAST_16", "utcDate": "2026-07-04T17:00:00Z", "status": "TIMED",
     "homeTeam": {"name": null}, "awayTeam": {"name": null}},
    {"id": 50, "stage": "GROUP_STAGE", "utcDate": "2026-06-12T19:00:00Z", "status": "FINISHED",
     "homeTeam": {"name": "Mexico"}, "awayTeam": {"name": "South Africa"}}
  ]
}
```

- [ ] **Step 2: Write the failing test**

Aggiungi in coda a `tests/test_knockout_bracket.py`:

```python
import json
from pathlib import Path

from src.scraper import knockout_bracket as kb

_SAMPLE = json.loads(
    (Path(__file__).parent / "fixtures" / "wc_matches_sample.json").read_text(encoding="utf-8")
)


def test_build_phase_bracket_assigns_slots_by_api_id():
    bracket = kb.build_phase_bracket(_SAMPLE, "sedicesimi")
    # id 100 viene prima di id 200 -> S01, S02
    assert list(bracket.keys()) == ["S01", "S02"]
    assert bracket["S01"]["api_id"] == 100
    assert bracket["S02"]["api_id"] == 200


def test_build_phase_bracket_normalizes_team_names():
    bracket = kb.build_phase_bracket(_SAMPLE, "sedicesimi")
    assert bracket["S01"]["home"] == "South Korea"  # "Korea Republic" -> alias
    assert bracket["S01"]["away"] == "Brazil"
    assert bracket["S01"]["determined"] is True


def test_build_phase_bracket_marks_undetermined():
    bracket = kb.build_phase_bracket(_SAMPLE, "ottavi")
    assert bracket["O01"]["home"] is None
    assert bracket["O01"]["determined"] is False


def test_slot_label_uses_real_teams_when_determined():
    bracket = kb.build_phase_bracket(_SAMPLE, "sedicesimi")
    assert kb.slot_label("S01", bracket) == "S01 — South Korea vs Brazil"


def test_slot_label_falls_back_to_id():
    assert kb.slot_label("S99", {}) == "S99"
    bracket = kb.build_phase_bracket(_SAMPLE, "ottavi")
    assert kb.slot_label("O01", bracket) == "O01"  # non determinato -> solo id
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m pytest tests/test_knockout_bracket.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.scraper.knockout_bracket'`.

- [ ] **Step 4: Write minimal implementation**

Crea `src/scraper/knockout_bracket.py`:

```python
"""
Accoppiamenti delle fasi a eliminazione diretta — football-data.org (free tier).
Endpoint: GET https://api.football-data.org/v4/competitions/WC/matches

A differenza delle standings (solo gironi), questo modulo recupera gli accoppiamenti
reali del tabellone knockout e li mappa sugli slot interni (S01…, O01…). Lo scarico è
pensato per essere innescato manualmente dall'Admin, una fase per volta.
"""

from typing import Dict

import requests

from src.models.tournament import load_fixtures, get_knockout_slots
from src.scraper.results_scraper import (
    BASE_URL,
    HEADERS,
    _build_team_resolver,
    _resolve_team,
)

# API stage -> fase interna (coerente con src/models/match.py Phase)
STAGE_TO_PHASE = {
    "LAST_32": "sedicesimi",
    "LAST_16": "ottavi",
    "QUARTER_FINALS": "quarti",
    "SEMI_FINALS": "semifinali",
    "THIRD_PLACE": "finale_3posto",
    "FINAL": "finale",
}


def fetch_matches() -> dict:
    """Scarica tutte le partite del Mondiale corrente (gironi + knockout)."""
    resp = requests.get(
        f"{BASE_URL}/competitions/WC/matches",
        headers=HEADERS,
        timeout=15,
    )
    if resp.status_code == 403:
        raise PermissionError(
            "403 Forbidden — la tua API key non ha accesso a questa risorsa."
        )
    if resp.status_code == 429:
        raise RuntimeError("429 Too Many Requests — superate le 10 req/min del free tier.")
    resp.raise_for_status()
    return resp.json()


def build_phase_bracket(payload: dict, phase: str) -> Dict[str, dict]:
    """Costruisce {slot_id: {...}} per la fase richiesta a partire dal payload /matches.

    Funzione pura (nessuna rete): filtra le partite dello stage corrispondente, le ordina
    per `api_id` crescente (chiave stabile) e le assegna agli slot S01/O01/… normalizzando
    i nomi squadra ai nomi canonici di fixtures.json.
    """
    slot_cfg = next((s for s in get_knockout_slots() if s["phase"] == phase), None)
    if slot_cfg is None:
        return {}
    prefix = slot_cfg["prefix"]

    stages = [api for api, ph in STAGE_TO_PHASE.items() if ph == phase]
    matches = [m for m in payload.get("matches", []) if m.get("stage") in stages]
    matches.sort(key=lambda m: m.get("id", 0))

    _, groups = load_fixtures()
    lookup = _build_team_resolver(groups)

    bracket: Dict[str, dict] = {}
    for i, m in enumerate(matches, 1):
        slot_id = f"{prefix}{i:02d}"
        home_raw = (m.get("homeTeam") or {}).get("name")
        away_raw = (m.get("awayTeam") or {}).get("name")
        determined = bool(home_raw) and bool(away_raw)
        bracket[slot_id] = {
            "home": _resolve_team(home_raw, lookup) if home_raw else None,
            "away": _resolve_team(away_raw, lookup) if away_raw else None,
            "utc_date": m.get("utcDate"),
            "api_id": m.get("id"),
            "determined": determined,
        }
    return bracket


def slot_label(match_id: str, bracket: Dict[str, dict]) -> str:
    """'S01 — France vs Sweden' se l'accoppiamento è noto, altrimenti il solo id."""
    entry = bracket.get(match_id)
    if entry and entry.get("determined"):
        return f"{match_id} — {entry['home']} vs {entry['away']}"
    return match_id
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_knockout_bracket.py -v`
Expected: PASS (tutti i test, inclusi quelli del Task 1).

- [ ] **Step 6: Commit**

```bash
git add src/scraper/knockout_bracket.py tests/test_knockout_bracket.py tests/fixtures/wc_matches_sample.json
git commit -m "feat: modulo knockout_bracket (build_phase_bracket, slot_label)"
```

---

## Task 3: Wrapper di refresh con guard "tutti determinati"

**Files:**
- Modify: `src/scraper/live_refresh.py`
- Test: `tests/test_knockout_bracket.py` (ampliato)

- [ ] **Step 1: Write the failing test**

Aggiungi in coda a `tests/test_knockout_bracket.py`:

```python
from src.scraper import live_refresh


def test_refresh_saves_when_all_determined(monkeypatch):
    payload = {"matches": [
        {"id": 1, "stage": "LAST_32", "utcDate": "x", "status": "TIMED",
         "homeTeam": {"name": "France"}, "awayTeam": {"name": "Sweden"}},
    ]}
    captured = {}
    monkeypatch.setattr(live_refresh, "fetch_matches", lambda: payload)
    monkeypatch.setattr(live_refresh, "merge_knockout_bracket",
                        lambda b: captured.update(b))
    outcome = live_refresh.refresh_knockout_bracket_from_api("sedicesimi")
    assert outcome.status == "api"
    assert "S01" in captured


def test_refresh_skips_when_undetermined(monkeypatch):
    payload = {"matches": [
        {"id": 1, "stage": "LAST_16", "utcDate": "x", "status": "TIMED",
         "homeTeam": {"name": None}, "awayTeam": {"name": None}},
    ]}
    called = {"merged": False}
    monkeypatch.setattr(live_refresh, "fetch_matches", lambda: payload)
    monkeypatch.setattr(live_refresh, "merge_knockout_bracket",
                        lambda b: called.update(merged=True))
    outcome = live_refresh.refresh_knockout_bracket_from_api("ottavi")
    assert outcome.status == "error"
    assert called["merged"] is False


def test_refresh_reports_error_on_exception(monkeypatch):
    def boom():
        raise RuntimeError("429 Too Many Requests")
    monkeypatch.setattr(live_refresh, "fetch_matches", boom)
    outcome = live_refresh.refresh_knockout_bracket_from_api("sedicesimi")
    assert outcome.status == "error"
    assert "429" in outcome.message
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_knockout_bracket.py -v`
Expected: FAIL — `AttributeError: module 'src.scraper.live_refresh' has no attribute 'fetch_matches'` (e `refresh_knockout_bracket_from_api` non definita).

- [ ] **Step 3: Write minimal implementation**

In `src/scraper/live_refresh.py`, aggiungi agli import in testa (dopo la riga 19, dopo gli import esistenti):

```python
from src.scraper.knockout_bracket import fetch_matches, build_phase_bracket
from src.storage.json_storage import merge_knockout_bracket
```

In fondo al file aggiungi:

```python
def refresh_knockout_bracket_from_api(phase: str) -> RefreshOutcome:
    """Scarica gli accoppiamenti di UNA fase knockout e li salva (merge) su disco.

    Salva solo se tutti gli accoppiamenti della fase sono determinati; altrimenti
    avvisa senza scrivere nulla. Non solleva eccezioni: ogni errore diventa un
    RefreshOutcome di stato "error".
    """
    try:
        payload = fetch_matches()
        bracket = build_phase_bracket(payload, phase)
        if not bracket:
            return RefreshOutcome(
                status="error",
                message="The API has no matches for this phase yet — nothing saved.",
            )
        undetermined = [sid for sid, e in bracket.items() if not e["determined"]]
        if undetermined:
            return RefreshOutcome(
                status="error",
                message="Pairings for this phase aren't determined yet — nothing saved.",
            )
        merge_knockout_bracket(bracket)
        return RefreshOutcome(
            status="api",
            message=f"{len(bracket)} pairings populated from the API.",
        )
    except Exception as e:  # noqa: BLE001 — qualsiasi errore va riportato alla pagina
        return RefreshOutcome(status="error", message=f"Bracket refresh failed: {e}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_knockout_bracket.py -v`
Expected: PASS (tutti i test del file).

- [ ] **Step 5: Commit**

```bash
git add src/scraper/live_refresh.py tests/test_knockout_bracket.py
git commit -m "feat: refresh_knockout_bracket_from_api con guard tutti-determinati"
```

---

## Task 4: Sezione Admin — trigger per fase

**Files:**
- Modify: `pages/9_Admin_Settings.py`

- [ ] **Step 1: Aggiungi gli import**

In `pages/9_Admin_Settings.py`, modifica il blocco import dello storage (righe 8-17) aggiungendo `load_knockout_bracket`, e aggiungi l'import del wrapper. Sostituisci:

```python
from src.storage.json_storage import (
    delete_participant,
    load_all_participants,
    load_phase_locks,
    merge_participant,
    register_participant,
    reset_all_predictions,
    set_phase_lock,
    update_registry_timestamp,
)
```

con:

```python
from src.storage.json_storage import (
    delete_participant,
    load_all_participants,
    load_knockout_bracket,
    load_phase_locks,
    merge_participant,
    register_participant,
    reset_all_predictions,
    set_phase_lock,
    update_registry_timestamp,
)
from src.models.tournament import get_knockout_slots
from src.scraper.live_refresh import refresh_knockout_bracket_from_api
```

- [ ] **Step 2: Aggiungi la sezione UI**

In `pages/9_Admin_Settings.py`, subito prima del blocco "Full reset" (la riga `st.subheader("⚠️ Full reset")`, riga 276), inserisci:

```python
# ── Popola accoppiamenti knockout da API ────────────────────────────────────────

st.subheader("🎯 Populate knockout pairings from API")
st.caption(
    "Pull the real team match-ups for a knockout phase from football-data.org. "
    "Do it once a phase's bracket is set (e.g. after the previous round ends). "
    "Players will then predict on the real teams instead of TBD slots."
)

# (etichetta UI, fase interna) — 1:1, così la Finale 3°/Finale si popolano separatamente
_BRACKET_PHASES = [
    ("Round of 32", "sedicesimi"),
    ("Round of 16", "ottavi"),
    ("Quarter-finals", "quarti"),
    ("Semi-finals", "semifinali"),
    ("Third-place play-off", "finale_3posto"),
    ("Final", "finale"),
]

# fase interna -> prefisso slot (es. "sedicesimi" -> "S")
_PHASE_PREFIX = {s["phase"]: s["prefix"] for s in get_knockout_slots()}

_current_bracket = load_knockout_bracket()

col_bk, col_btn = st.columns([2, 1])
with col_bk:
    bracket_label = st.selectbox(
        "Knockout phase",
        options=[label for label, _ in _BRACKET_PHASES],
        key="bracket_phase",
    )
bracket_internal = next(ph for label, ph in _BRACKET_PHASES if label == bracket_label)

with col_btn:
    st.write("")
    st.write("")
    do_populate = st.button(
        "⬇️ Populate from API",
        key="btn_populate_bracket",
        disabled=not is_authorized,
    )

if do_populate and is_authorized:
    outcome = refresh_knockout_bracket_from_api(bracket_internal)
    if outcome.status == "api":
        st.success(outcome.message)
        bracket = load_knockout_bracket()
        rows = sorted(
            (
                {"Slot": sid, "Home": e["home"], "Away": e["away"], "Kick-off (UTC)": e["utc_date"]}
                for sid, e in bracket.items()
                if e.get("determined")
            ),
            key=lambda r: r["Kick-off (UTC)"] or "",
        )
        st.dataframe(rows, use_container_width=True, hide_index=True)
        st.rerun()
    else:
        st.warning(outcome.message)

if not is_authorized:
    st.caption("Access denied.")

# Stato corrente del bracket salvato
if _current_bracket:
    determined_phases = [
        label
        for label, ph in _BRACKET_PHASES
        if any(
            sid.startswith(_PHASE_PREFIX[ph]) and e.get("determined")
            for sid, e in _current_bracket.items()
        )
    ]
    if determined_phases:
        st.caption("Bracket already populated for: " + ", ".join(f"**{p}**" for p in determined_phases))

st.divider()
```

> **Attenzione ai prefissi sovrapposti:** i prefissi `S` (sedicesimi) ed `SF` (semifinali) e `F` (finale) condividono lettere iniziali, ma gli slot id sono sempre prefisso+cifre (`S01`, `SF01`, `F01`), quindi `sid.startswith("S")` matcha anche `SF01`. Per la sola riga di stato informativa questo è accettabile (al più segnala una fase in più); non incide su salvataggio o previsioni, che lavorano per `match_id` esatto. Se vuoi precisione assoluta, confronta con regex `^S\d` come fa già `pages/9_Admin_Settings.py` nelle righe di copertura fase.

- [ ] **Step 3: Smoke check (sintassi/import)**

Run: `python -c "import ast; ast.parse(open('pages/9_Admin_Settings.py', encoding='utf-8').read()); print('OK')"`
Expected: `OK`

- [ ] **Step 4: Verifica manuale**

Run: `streamlit run Home.py` → apri **Admin Settings** → inserisci un'email autorizzata → nella nuova sezione seleziona "Round of 32" → clicca "Populate from API".
Expected: messaggio di successo con la tabella degli accoppiamenti (oggi, 28/06/2026, i sedicesimi sono determinati). Selezionando "Round of 16" e cliccando: avviso "Pairings for this phase aren't determined yet — nothing saved." Verifica che `data/results/knockout_bracket.json` contenga le voci `S01…S16`.

- [ ] **Step 5: Commit**

```bash
git add pages/9_Admin_Settings.py
git commit -m "feat: sezione Admin per popolare il bracket knockout da API"
```

---

## Task 5: Make Predictions — auto-popolamento slot determinati

**Files:**
- Modify: `pages/1_Make_Predictions.py`

- [ ] **Step 1: Aggiungi l'import**

In `pages/1_Make_Predictions.py`, modifica il blocco import dello storage (righe 6-13) aggiungendo `load_knockout_bracket`. Sostituisci:

```python
from src.storage.json_storage import (
    is_phase_locked,
    load_participant,
    load_registry,
    merge_participant,
    register_participant,
    update_registry_timestamp,
)
```

con:

```python
from src.storage.json_storage import (
    is_phase_locked,
    load_knockout_bracket,
    load_participant,
    load_registry,
    merge_participant,
    register_participant,
    update_registry_timestamp,
)
```

- [ ] **Step 2: Carica il bracket nel ramo knockout**

In `pages/1_Make_Predictions.py`, nel ramo `else` delle fasi a eliminazione (dopo la riga 183 `team_opts = ["TBD"] + all_teams`), aggiungi:

```python
    bracket = load_knockout_bracket()
```

- [ ] **Step 3: Ordina gli slot per data e auto-popola le squadre determinate**

Sostituisci l'intero loop interno degli slot (righe 207-231, dal `for i in range(1, n_slots + 1):` fino a `new_preds[match_id] = {...}` incluso) con:

```python
        match_ids = [f"{prefix}{i:02d}" for i in range(1, n_slots + 1)]
        # Mostra in ordine cronologico se il bracket conosce le date; altrimenti ordine slot.
        match_ids.sort(key=lambda mid: (bracket.get(mid, {}).get("utc_date") or "", mid))

        for match_id in match_ids:
            pred = participant.match_predictions.get(match_id)
            home_g = pred.home_goals if pred else 0
            away_g = pred.away_goals if pred else 0
            entry = bracket.get(match_id)
            determined = bool(entry and entry.get("determined"))

            cols = st.columns([3, 0.8, 0.5, 0.8, 3])
            if determined:
                cols[0].markdown(f"**{entry['home']}**")
            else:
                cols[0].selectbox(
                    f"t1_{match_id}", team_opts,
                    key=f"t1_{match_id}", label_visibility="collapsed",
                )
            g1 = cols[1].number_input(
                f"g1_{match_id}", min_value=0, max_value=20, value=home_g, step=1,
                key=f"g1_{match_id}", label_visibility="collapsed",
            )
            cols[2].write("–")
            g2 = cols[3].number_input(
                f"g2_{match_id}", min_value=0, max_value=20, value=away_g, step=1,
                key=f"g2_{match_id}", label_visibility="collapsed",
            )
            if determined:
                cols[4].markdown(f"**{entry['away']}**")
            else:
                cols[4].selectbox(
                    f"t2_{match_id}", team_opts,
                    key=f"t2_{match_id}", label_visibility="collapsed",
                )
            new_preds[match_id] = {"home_goals": int(g1), "away_goals": int(g2)}
```

> La previsione resta `{home_goals, away_goals}` sullo stesso `match_id`: nessun impatto su storage o scoring.

- [ ] **Step 4: Smoke check (sintassi)**

Run: `python -c "import ast; ast.parse(open('pages/1_Make_Predictions.py', encoding='utf-8').read()); print('OK')"`
Expected: `OK`

- [ ] **Step 5: Verifica manuale**

Run: `streamlit run Home.py` → **Make Predictions** → scegli un nome → fase "Round of 32".
Expected: con il bracket popolato (Task 4), ogni riga mostra le squadre reali (es. "France" / "Sweden") in grassetto al posto delle tendine, in ordine di data, con i due campi gol. Per una fase non popolata (es. "Quarter-finals") restano le tendine TBD come prima.

- [ ] **Step 6: Commit**

```bash
git add pages/1_Make_Predictions.py
git commit -m "feat: auto-popolamento squadre reali negli slot di previsione knockout"
```

---

## Task 6: Real Results — prefill nomi squadra dal bracket

**Files:**
- Modify: `pages/2_Real_Results.py`

- [ ] **Step 1: Aggiungi l'import di load_knockout_bracket**

In `pages/2_Real_Results.py`, individua il blocco `from src.storage.json_storage import (...)` e aggiungi `load_knockout_bracket` all'elenco (ordine alfabetico coerente con gli altri import del file).

- [ ] **Step 2: Carica il bracket prima del loop knockout**

In `pages/2_Real_Results.py`, subito prima di `new_results: dict = {}` (riga 154) aggiungi:

```python
ko_bracket = load_knockout_bracket()
```

- [ ] **Step 3: Prefilla i campi nome squadra**

Nel loop knockout, sostituisci le due righe dei `text_input` (righe 176 e 188) per usare il nome dal bracket come valore iniziale. Sostituisci:

```python
            cols[1].text_input("sq1", value="", key=f"sq1_{match_id}", label_visibility="collapsed")
```
con:
```python
            _entry = ko_bracket.get(match_id) or {}
            cols[1].text_input(
                "sq1", value=_entry.get("home") or "",
                key=f"sq1_{match_id}", label_visibility="collapsed",
            )
```

e sostituisci:

```python
            cols[5].text_input("sq2", value="", key=f"sq2_{match_id}", label_visibility="collapsed")
```
con:
```python
            cols[5].text_input(
                "sq2", value=_entry.get("away") or "",
                key=f"sq2_{match_id}", label_visibility="collapsed",
            )
```

> I nomi squadra in Real Results sono puramente informativi (i risultati si salvano per `match_id`); il prefill evita di doverli ridigitare ma resta modificabile.

- [ ] **Step 4: Smoke check (sintassi)**

Run: `python -c "import ast; ast.parse(open('pages/2_Real_Results.py', encoding='utf-8').read()); print('OK')"`
Expected: `OK`

- [ ] **Step 5: Verifica manuale**

Run: `streamlit run Home.py` → **Real Results** → espandi "Round of 32".
Expected: i campi Team 1 / Team 2 risultano pre-compilati con le squadre reali del bracket (modificabili). Le fasi non popolate restano con campi vuoti.

- [ ] **Step 6: Commit**

```bash
git add pages/2_Real_Results.py
git commit -m "feat: prefill nomi squadra knockout in Real Results dal bracket"
```

---

## Task 7: Statistics — etichetta slot con nomi reali

**Files:**
- Modify: `pages/3_Statistics.py`

- [ ] **Step 1: Aggiungi gli import**

In `pages/3_Statistics.py`, aggiungi in testa (vicino agli altri import `from src...`):

```python
from src.scraper.knockout_bracket import slot_label
from src.storage.json_storage import load_knockout_bracket
```

> Se `pages/3_Statistics.py` importa già qualcosa da `src.storage.json_storage`, aggiungi `load_knockout_bracket` a quell'elenco invece di duplicare la riga.

- [ ] **Step 2: Carica il bracket una volta**

In `pages/3_Statistics.py`, subito dopo il caricamento di `ko_ids`/partecipanti in testa allo script (dopo la riga che definisce `ko_ids`, attorno alla riga 27-30), aggiungi:

```python
bracket = load_knockout_bracket()
```

- [ ] **Step 3: Usa slot_label nella colonna "Slot"**

In `pages/3_Statistics.py`, nella costruzione del DataFrame della tab knockout (riga 143), sostituisci:

```python
                "Slot": o.label,
```
con:
```python
                "Slot": slot_label(o.label, bracket),
```

> La chiave `exact_by_label[o.label]` resta invariata: usa ancora il `match_id` grezzo, cambiamo solo il testo mostrato.

- [ ] **Step 4: Smoke check (sintassi)**

Run: `python -c "import ast; ast.parse(open('pages/3_Statistics.py', encoding='utf-8').read()); print('OK')"`
Expected: `OK`

- [ ] **Step 5: Verifica manuale**

Run: `streamlit run Home.py` → **Statistics** → tab "Round of 32" (servono ≥2 partecipanti con pronostici su quella fase).
Expected: la colonna "Slot" mostra "S01 — France vs Sweden" dove il bracket è noto, altrimenti il solo "S01".

- [ ] **Step 6: Commit**

```bash
git add pages/3_Statistics.py
git commit -m "feat: etichette slot con squadre reali nelle statistiche knockout"
```

---

## Task 8: Documentazione README

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Aggiorna la struttura del progetto**

In `README.md`, nella sezione "Struttura del progetto" sotto `data/results/`, aggiungi la riga del nuovo file (dopo `group_rankings_meta.json`, riga 32):

```
│       ├── group_rankings_meta.json   # Provenienza classifiche gironi: "api" | "default" | "manual"
│       └── knockout_bracket.json      # Accoppiamenti knockout reali da API {slot_id: {home, away, utc_date, api_id, determined}}
```

E nella descrizione di `src/scraper/` (riga 38) aggiorna a:

```
    └── scraper/                       # Classifiche gironi (standings) + accoppiamenti knockout (matches) da football-data.org
```

- [ ] **Step 2: Documenta il workflow Admin del bracket**

In `README.md`, nella sezione "Pagina Admin" (dopo l'elenco puntato che inizia a riga 219), aggiungi un punto:

```markdown
- **Populate knockout pairings from API**: scarica da football-data.org (endpoint `GET /competitions/WC/matches`) gli accoppiamenti reali di **una** fase a eliminazione diretta selezionata e popola gli slot di previsione con le squadre vere. Lo scarico è **manuale e per fase**: si popolano i sedicesimi quando il loro tabellone è definito, poi gli ottavi a sedicesimi conclusi, e così via. Se gli accoppiamenti di una fase non sono ancora determinati dall'API, l'operazione **avvisa e non salva nulla**. La fonte è il file `data/results/knockout_bracket.json`, letto dalle altre pagine senza ulteriori chiamate API.
```

- [ ] **Step 3: Aggiorna la nota sugli slot in Statistics**

In `README.md`, sostituisci la riga (≈209):

```
> Gli slot knockout mostrano l'id (es. `S01`) perché le squadre non sono note finché non escono i risultati.
```
con:
```
> Gli slot knockout mostrano l'id (es. `S01`); una volta che l'Admin ha popolato gli accoppiamenti da API, accanto all'id compaiono le squadre reali (es. `S01 — France vs Sweden`).
```

- [ ] **Step 4: Aggiorna la nota sulla copertura dello scraper**

In `README.md`, sostituisci la riga (≈168):

```
> Lo scraper copre **solo le classifiche dei gironi**; i risultati delle fasi a eliminazione diretta restano a inserimento manuale.
```
con:
```
> Lo scraper copre le **classifiche dei gironi** (automatiche all'apertura) e gli **accoppiamenti knockout** (su trigger Admin, vedi pagina Admin). I **risultati** delle fasi a eliminazione diretta restano a inserimento manuale.
```

- [ ] **Step 5: Commit**

```bash
git add README.md
git commit -m "docs: documenta popolamento bracket knockout da API"
```

---

## Task 9: Verifica finale completa

- [ ] **Step 1: Suite di test**

Run: `python -m pytest -v`
Expected: tutti i test passano (inclusi i preesistenti `test_statistics.py` e i nuovi `test_knockout_bracket.py`).

- [ ] **Step 2: Smoke check di tutte le pagine modificate**

Run:
```bash
python -c "import ast,glob; [ast.parse(open(f,encoding='utf-8').read()) for f in ['pages/1_Make_Predictions.py','pages/2_Real_Results.py','pages/3_Statistics.py','pages/9_Admin_Settings.py']]; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Verifica end-to-end manuale**

Run: `streamlit run Home.py`. Sequenza:
1. **Admin Settings** (email autorizzata) → "Populate from API" su "Round of 32" → successo + tabella.
2. **Make Predictions** → "Round of 32" → squadre reali nei 16 slot, salva un pronostico.
3. **Real Results** → "Round of 32" → nomi squadra pre-compilati.
4. **Statistics** → tab "Round of 32" → colonna Slot con nomi reali.

Expected: ogni passo come descritto; nessuna regressione sulle fasi non ancora popolate (restano TBD/vuote).
