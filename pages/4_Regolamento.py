import streamlit as st

st.set_page_config(page_title="Regolamento", page_icon="📋", layout="centered")
st.title("📋 Regolamento")
st.caption("Come vengono calcolati i punteggi nel Mundial Game 2026.")

st.markdown("---")

# ── Fase a gironi ────────────────────────────────────────────────────────────

st.subheader("⚽ Fase a gironi — sistema a errore")

st.markdown(
    """
Per ogni girone pronostichi la **classifica finale** completa, dal 1° al 4° posto.

A differenza delle fasi successive, **qui non si accumulano punti**: si misura l'**errore**,
cioè quanto la tua classifica si discosta da quella reale. Vale la regola:

> ### 🎯 Più basso è l'errore, migliore è il pronostico.

#### Come si calcola l'errore di un girone

Per ogni squadra si guarda **di quante posizioni hai sbagliato**, e si sommano tutti gli scarti:

$$\\text{errore squadra} = |\\,\\text{posizione pronosticata} - \\text{posizione reale}\\,|$$

- Squadra al posto giusto → **0** di errore
- Sbagliata di una posizione → **1**
- Sbagliata di due posizioni → **2**, e così via
- Squadra **non inserita** nel pronostico → penalità massima di **3**

L'errore del girone è la **somma** degli scarti delle 4 squadre. L'errore totale del partecipante
è la somma degli errori su **tutti i 12 gironi**.
"""
)

with st.expander("📊 Esempio pratico — un girone"):
    st.markdown(
        """
Supponiamo il **Girone A**.

| Squadra | Tuo pronostico | Risultato reale | Scarto |
|---|:---:|:---:|:---:|
| Francia | 1° | 2° | \\|1−2\\| = **1** |
| Olanda | 2° | 1° | \\|2−1\\| = **1** |
| Senegal | 3° | 3° | \\|3−3\\| = **0** |
| Australia | 4° | 4° | \\|4−4\\| = **0** |

**Errore del Girone A = 1 + 1 + 0 + 0 = 2**

Hai centrato l'ordine quasi perfettamente: solo le prime due invertite, per un errore di appena 2.
Una classifica **identica** a quella reale avrebbe dato errore **0** (il punteggio migliore possibile).
"""
    )

with st.expander("⚠️ Cosa succede se non inserisci una squadra"):
    st.markdown(
        """
Se in un girone non hai indicato una squadra che invece compare nella classifica reale,
quella squadra contribuisce con la **penalità massima di 3** (lo scarto più grande possibile
tra due posizioni in un girone da 4).

Conviene quindi **completare sempre tutti e 4 i posti** di ogni girone: lasciare un buco
costa più che tentare un piazzamento, anche incerto.
"""
    )

st.info(
    "In **Classifica → Fase Gironi** i partecipanti sono ordinati per errore totale crescente "
    "(chi ha l'errore più basso è primo). L'espander *Dettaglio per girone* mostra "
    "l'errore girone per girone."
)

st.markdown("---")

# ── Fasi a eliminazione diretta ──────────────────────────────────────────────

st.subheader("🏆 Fasi a eliminazione diretta — sistema a criteri")

st.markdown(
    """
Dalla fase a **Sedicesimi** in poi (Sedicesimi, Ottavi, Quarti, Semifinali,
Finale 3° posto e Finale) per ogni partita pronostichi il **risultato esatto** (es. 2–1).

Per ogni fase la graduatoria si costruisce su **tre criteri**, applicati in ordine:

| | Criterio | Significato | Direzione |
|---|---|---|:---:|
| **C1** | Vincitori corretti | Quante volte hai indovinato **chi passa il turno** (l'esito: vittoria, pareggio o sconfitta) | più alto = meglio |
| **C2** | Risultati esatti | Quante volte hai azzeccato il **punteggio preciso** (es. 2–1) — *spareggio* | più alto = meglio |
| **C3** | Errore differenza reti | Somma degli scarti tra la **differenza reti** pronosticata e quella reale — *spareggio* | più basso = meglio |

#### Ordine di classifica

1. Prima si guarda **C1** (vincitori corretti): chi ne ha di più sta davanti.
2. A parità di C1, decide **C2** (risultati esatti): più ne hai, meglio è.
3. A parità anche di C2, decide **C3** (errore differenza reti): più è basso, meglio è.
"""
)

with st.expander("📊 Esempio pratico — una partita"):
    st.markdown(
        """
Pronostico: **Brasile 2 – 1 Croazia** · Risultato reale: **Brasile 3 – 0 Croazia**

| Criterio | Calcolo | Esito |
|---|---|:---:|
| **C1** — vincitore | Hai detto "vince il Brasile" e il Brasile ha vinto | ✅ +1 |
| **C2** — risultato esatto | 2–1 ≠ 3–0 | ❌ |
| **C3** — errore diff. reti | diff. prevista = +1, diff. reale = +3 → \\|1−3\\| = **2** | +2 |

Hai preso l'esito (C1), ma non il punteggio esatto (C2); il tuo errore sulla differenza reti
in questa partita è 2 (C3).
"""
    )

st.info(
    "In **Classifica** ogni fase knockout ha la sua tabella con le colonne C1, C2 e C3."
)

st.markdown("---")

# ── Flusso operativo ─────────────────────────────────────────────────────────

st.subheader("🔄 Quando vengono aggiornati i punteggi")
st.markdown(
    """
1. Man mano che le partite vengono giocate, l'admin carica i dati reali nella sezione **Risultati Reali**
   (classifiche dei gironi e risultati delle partite knockout).
2. La pagina **Classifica** ricalcola e mostra automaticamente la graduatoria aggiornata,
   con una tab separata per la fase a gironi e per ogni turno a eliminazione diretta.

> I pronostici di gironi e fasi knockout vengono valutati **in modo indipendente**:
> non esiste un unico totale complessivo, ma una classifica per ciascuna fase.
"""
)
