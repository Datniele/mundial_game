import streamlit as st

st.set_page_config(page_title="Rules", page_icon="📋", layout="centered")
st.title("📋 The Rules")
st.caption("How the points get crunched in the Mundial Game 2026.")

st.markdown("---")

# ── Fase a gironi ────────────────────────────────────────────────────────────

st.subheader("⚽ Group stage — scoring by error")

st.markdown(
    """
For each group you predict the full **final standings**, from 1st all the way down to 4th.

Behind the scenes we measure the **error** — basically how far your table drifts from the real one —
and then turn that error into a **score** that shows up on the leaderboard. The golden rule:

> ### 🎯 The higher the score, the sharper your prediction.

#### How a group's error is worked out

For each team we check **how many spots you got it wrong by**, and add up all the gaps:

$$\\text{team error} = |\\,\\text{predicted position} - \\text{actual position}\\,|$$

- Team in the right spot → **0** error
- Off by one spot → **1**
- Off by two spots → **2**, and so on
- Team you **left out** of your prediction → maximum penalty of **3**

A group's error is the **sum** of the gaps across all 4 teams. Your total error is the sum of
the errors across **all 12 groups**.

#### From error to score

That total error then gets turned into a score with a little **scaling factor**:

$$\\text{score} = \\frac{96 - \\text{total error}}{9.6}$$

So a **flawless** prediction (error of 0) is worth a perfect **10**, and the higher the score the
better you did. In the *Group-by-group breakdown*, each group shows its own contribution, computed
as $(8 - \\text{group error}) / 9.6$: add up all 12 and you get exactly the total score.
"""
)

with st.expander("📊 Worked example — one group"):
    st.markdown(
        """
Let's take **Group A**.

| Team | Your pick | Real result | Gap |
|---|:---:|:---:|:---:|
| France | 1st | 2nd | \\|1−2\\| = **1** |
| Netherlands | 2nd | 1st | \\|2−1\\| = **1** |
| Senegal | 3rd | 3rd | \\|3−3\\| = **0** |
| Australia | 4th | 4th | \\|4−4\\| = **0** |

**Group A error = 1 + 1 + 0 + 0 = 2**

You nailed the order almost perfectly — just the top two swapped, for a tiny error of 2.
This group's contribution to the score is $(8 - 2)/9.6 = 0.625$.
A table **identical** to the real one would have scored an error of **0** and, across the whole
tournament, the maximum score of **10**.
"""
    )

with st.expander("⚠️ What happens if you leave a team out"):
    st.markdown(
        """
If you skip a team in a group that actually shows up in the real standings,
that team slaps you with the **maximum penalty of 3** (the biggest possible gap
between two positions in a 4-team group).

Moral of the story: **always fill all 4 slots** in every group. Leaving a blank costs you more
than taking a wild guess — so go on, take the punt.
"""
    )

st.info(
    "In **Leaderboard → Group Stage**, players are ranked by score, highest first "
    "(top score takes the crown). The *Group-by-group breakdown* expander shows "
    "the score group by group."
)

st.markdown("---")

# ── Fasi a eliminazione diretta ──────────────────────────────────────────────

st.subheader("🏆 Knockout rounds — the criteria system")

st.markdown(
    """
From the **Round of 32** onwards (Round of 32, Round of 16, Quarter-finals, Semi-finals,
Third-place play-off and Final) you predict the **exact score** of every match (e.g. 2–1).

For each phase the ranking is built on **three criteria**, applied in order:

| | Criterion | What it means | Direction |
|---|---|---|:---:|
| **C1** | Correct winners | How often you called **who goes through** (the outcome: win, draw or loss) | higher = better |
| **C2** | Exact scores | How often you nailed the **precise score** (e.g. 2–1) — *tiebreaker* | higher = better |
| **C3** | Goal-difference error | Sum of the gaps between your predicted **goal difference** and the real one — *tiebreaker* | lower = better |

#### How the ranking is decided

1. First we look at **C1** (correct winners): whoever has more sits higher.
2. Tied on C1? **C2** (exact scores) settles it: the more, the merrier.
3. Still tied? **C3** (goal-difference error) breaks the deadlock: the lower, the better.
"""
)

with st.expander("📊 Worked example — one match"):
    st.markdown(
        """
Your pick: **Brazil 2 – 1 Croatia** · Real result: **Brazil 3 – 0 Croatia**

| Criterion | Calculation | Outcome |
|---|---|:---:|
| **C1** — winner | You said "Brazil wins" and Brazil won | ✅ +1 |
| **C2** — exact score | 2–1 ≠ 3–0 | ❌ |
| **C3** — goal-diff error | predicted diff = +1, real diff = +3 → \\|1−3\\| = **2** | +2 |

You called the outcome right (C1) but missed the exact score (C2); your goal-difference error
on this match is 2 (C3).
"""
    )

st.info(
    "In the **Leaderboard**, each knockout phase has its own table with C1, C2 and C3 columns."
)

st.markdown("---")

# ── Flusso operativo ─────────────────────────────────────────────────────────

st.subheader("🔄 When the scores get updated")
st.markdown(
    """
1. As matches are played, the admin loads the real data into the **Real Results** section
   (group standings and knockout match results).
2. The **Leaderboard** page automatically recalculates and shows the fresh ranking,
   with a separate tab for the group stage and for each knockout round.

> Group and knockout predictions are scored **independently**: there's no single grand total,
> just one leaderboard per phase.
"""
)
