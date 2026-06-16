# A model-research loop with PriorStates

**What this shows:** how PriorStates turns a one-off experiment into a
*compounding* research loop. The payoff isn't any single tool call — it's the
bracket: you **recall before you work** and **record as you finish**, so the
thing you learned in iteration *N* is waiting for you in iteration *N+1* (and in
a brand-new agent session, and for your teammates).

This file is **runnable**. Every fenced `bash` / `python` / `journal` /
`journal-search` block has a ▶ Run button in the PriorStates cockpit, or run the
whole file headless:

```console
$ cd docs/research-demo            # run from this directory
$ priorstates mdlab run model-research-loop.mdlab.md
```

> For the cockpit's ▶ Run button, start it with **`priorstates cockpit --allow-write`** —
> Run executes code on the host, so it's off unless you opt in. The headless
> `mdlab run` above always works.

Results are written back into the file beneath each block, inside
`<!-- priorstates:result … -->` markers. Nothing here touches your real project —
the setup block gives the demo its own sandbox store under
`docs/research-demo/.priorstates/` (gitignored).

> **Two readings of this doc.** The runnable spine is a generic
> *model-research* loop (tuning a classifier) so any data scientist can follow
> it. The grey **“On a trading desk”** sidebars map each step to a
> quant-strategy workflow — the same loop, with sims and Sharpe instead of
> AUC. Read whichever speaks to you; they're the same five moves.

---

## The loop in one picture

```
                ┌─────────────────────────────────────────────┐
                │  1. RECALL   journal_search / memory_search   │ ◄── start here,
                │     "what did we already learn about this?"   │     not at step 3
                └───────────────────┬─────────────────────────┘
                                    ▼
   5. RECALL AGAIN ◄──┐   2. HYPOTHESIZE  (theory + data, not a blind sweep)
   next session sees  │            │
   what you wrote ────┘            ▼
                ▲          3. RUN / MEASURE  (train, sim, eval → a number)
                │                   │
                └─── 4. RECORD ◄────┘  journal_add (winner|loser|…) + memory_add
                     the finding + any durable preference
```

Most people only ever do steps 2–3. PriorStates is steps **1, 4, 5** — the
brackets that make the work accumulate.

---

## Step 0 — give the demo a sandbox

`priorstates init` makes the current directory a project: it gets its own
`memory/` and `journal/`. (Idempotent — safe to re-run.)

```bash
priorstates init . >/dev/null 2>&1 || true
echo "project store: ./.priorstates (under this folder)"
ls .priorstates
```

<!-- priorstates:result src=fa5269158155 kind=output -->
```output
project store: ./.priorstates (under this folder)
config.toml
journal
memory
memory.psmem
```
<!-- priorstates:result-end -->

---

## Step 0b — seed "previous sessions"

So the recall in Step 1 has something to find, we first replay a few findings
**as if earlier sessions had recorded them.** In real life you don't write these
by hand — your agent does, at the end of each session (Step 4). Run them once.

A prior **loser** — a dead end worth never repeating:

```journal
---
topic: churn-model
outcome: loser
title: Blind grid search over 64 hyper-param cells was noise
tags: [tuning, methodology]
---
**TL;DR**: a 64-cell grid (lr × depth × subsample) produced a "winner" whose
+0.4% AUC lift vanished on a fresh split. At our validation-set size the cell
differences were inside the noise band. Grid winners told us a number, never a
mechanism. Tune from a hypothesis about what the knob *does* instead.
```

<!-- priorstates:result src=1c48810e4679 kind=result -->
Journal entry recorded → entries/20260615_churn-model_8e501b.md  (loser)
<!-- priorstates:result-end -->

A prior **decision** — a standing choice the team already made:

```journal
---
topic: churn-model
outcome: decision
title: Optimize PR-AUC, not accuracy (4% positive class)
tags: [metrics]
---
**TL;DR**: classes are ~4% positive; accuracy is dominated by the majority and
moved the wrong way vs business value. We evaluate on PR-AUC and pick thresholds
by expected $ retained. Don't report accuracy as the headline.
```

<!-- priorstates:result src=b6ad77d26194 kind=result -->
Journal entry recorded → entries/20260615_churn-model_7c393a.md  (decision)
<!-- priorstates:result-end -->

A prior **gotcha** — a trap that already bit us once:

```journal
---
topic: churn-model
outcome: gotcha
title: tenure_days leaks the label via a churn-date join
tags: [leakage, features]
---
**TL;DR**: `tenure_days` was computed to the account-close date, so it encoded
the answer. OOS AUC looked great, live performance didn't. Cut any feature
derived from an event at/after the prediction horizon.
```

<!-- priorstates:result src=7f41fda98004 kind=result -->
Journal entry recorded → entries/20260615_churn-model_585140.md  (gotcha)
<!-- priorstates:result-end -->

And one durable **preference** into memory (memories are facts/preferences;
journal entries are time-stamped findings):

```python
from priorstates.core.config import load_config
from priorstates.memory import api as mem

cfg = load_config()
res = mem.add_memory(
    cfg,
    name="prefer-hypothesis-tuning",
    type_str="preference",
    description="Tune from theory + data, not a blind grid",
    body=("When tuning model or strategy parameters, start from a hypothesis "
          "grounded in how the knob affects behavior plus the relevant data "
          "distribution — then test that specific value. Fall back to a sweep "
          "only when the mechanism is genuinely unclear, and even then pick "
          "2–3 targeted points, not a grid."),
    scope="project",
    tags=["methodology", "tuning"],
    overwrite=True,   # idempotent for the demo
)
print(f"memory saved → {res['scope']} scope: prefer-hypothesis-tuning")
```

<!-- priorstates:result src=511d29ccba5e kind=output -->
```output
memory saved → project scope: prefer-hypothesis-tuning
```
<!-- priorstates:result-end -->

> **On a trading desk.** These three seeds are exactly the kind of thing a BTS
> session learns and must not relearn: *“don't grid-search params”* (loser),
> *“fix maker OTR by suppressing placement, not loosening cancels”* (decision),
> *“prediction r² is not a maker-PnL proxy — always validate with a sim”*
> (gotcha). Swap `churn-model` for `asmkr-30a` and AUC for Sharpe; the loop is
> identical.

---

## Step 1 — RECALL first (the move people skip)

Before touching the model, ask what's already known. This is a structured
journal lookup — it surfaces the loser, the decision, and the gotcha you'd
otherwise have to rediscover the hard way:

```journal-search {topic=churn-model}
```

<!-- priorstates:result src=8704318966c2 kind=result -->
| date | outcome | topic | title | TL;DR |
|---|---|---|---|---|
| 2026-06-15 | gotcha | churn-model | [tenure_days leaks the label via a churn-date join](entries/20260615_churn-model_585140.md) | `tenure_days` was computed to the account-close date, so it encoded the answer. OOS AUC looked grea… |
| 2026-06-15 | decision | churn-model | [Optimize PR-AUC, not accuracy (4% positive class)](entries/20260615_churn-model_7c393a.md) | classes are ~4% positive; accuracy is dominated by the majority and moved the wrong way vs business… |
| 2026-06-15 | loser | churn-model | [Blind grid search over 64 hyper-param cells was noise](entries/20260615_churn-model_8e501b.md) | a 64-cell grid (lr × depth × subsample) produced a "winner" whose +0.4% AUC lift vanished on a fres… |
<!-- priorstates:result-end -->

And a *semantic* memory lookup — note we search by meaning ("how should I pick
parameters"), not by keyword, and still hit the tuning preference:

```python
from priorstates.core.config import load_config
from priorstates.memory import api as mem

cfg = load_config()
hits = mem.search_memory(cfg, "how should I choose model hyper-parameters?", k=3)
for h in hits:
    print(f"[{h['type']:>10}] {h['name']}  (score {h['score']})")
    print(f"             {h['description']}")
```

<!-- priorstates:result src=160d35f5de95 kind=output -->
```output
[preference] prefer-hypothesis-tuning  (score 0.0925)
             Tune from theory + data, not a blind grid
[   project] churn-recency-features-help  (score 0.0483)
             Recent-behavior features carry signal the churn model under-weights
```
<!-- priorstates:result-end -->

**Read what came back before writing any code.** You now know, for free:
don't grid-search, optimize PR-AUC, and don't trust `tenure_days`. That's three
mistakes you won't make this iteration.

---

## Step 2 — HYPOTHESIZE

Recall shaped the plan. Grid search is off the table (loser); accuracy is off
the table (decision); `tenure_days` is out (gotcha). So we form **one specific,
mechanism-driven hypothesis**:

> *The model under-weights recent behavior. Adding a 7-day rolling
> `events_recent` feature and lowering `min_child_weight` (currently over-
> regularizing the sparse positive class) should lift **PR-AUC** without the
> leakage risk of `tenure_days`.*

One hypothesis, one change to measure. That's it.

---

## Step 3 — RUN / MEASURE

Here you'd train and evaluate for real. To keep the demo dependency-free and
deterministic, this block stands in for your `fit + eval` with a fixed
computation — **replace the body with your real pipeline.** What matters is that
it ends with *a number you can record.*

```python
# --- stand-in for your real train/eval; swap in sklearn/xgboost/torch/a sim ---
baseline_pr_auc = 0.612
# our hypothesis: +events_recent feature, min_child_weight 5 -> 2
lift_from_feature = 0.021     # measured on the held-out split
lift_from_regular = 0.008
new_pr_auc = round(baseline_pr_auc + lift_from_feature + lift_from_regular, 3)

print(f"baseline PR-AUC : {baseline_pr_auc}")
print(f"candidate PR-AUC: {new_pr_auc}")
print(f"delta           : {round(new_pr_auc - baseline_pr_auc, 3)}  "
      f"({'win' if new_pr_auc > baseline_pr_auc else 'no'})")
result = {"baseline": baseline_pr_auc, "candidate": new_pr_auc}
```

<!-- priorstates:result src=9f06d6602ad0 kind=output -->
```output
baseline PR-AUC : 0.612
candidate PR-AUC: 0.641
delta           : 0.029  (win)
```
<!-- priorstates:result-end -->

> **On a trading desk.** This block is where a `sim` runs and you read back
> `acctPnl` / Sharpe / per-fill edge across an IS **and** an OOS window. Same
> shape: the step ends with a number (and, per the desk's own rule, you
> validate it on a ≥3× window before believing it).

*(Optional)* If you have an agent CLI on PATH, a `prompt` block can synthesize
the recall + result into a plain-English call. Cached by body hash so editing
prose around it doesn't re-burn tokens:

```prompt {cache=true}
In two sentences: given a churn model where blind grid search was a known loser,
PR-AUC is the agreed metric, and tenure_days is a known leak, a candidate adds a
7-day events_recent feature and loosens regularization for +0.029 PR-AUC on a
held-out split. State whether this is worth recording as a winner and the single
biggest risk to check before trusting it.
```

---

## Step 4 — RECORD the finding

The iteration isn't done when the number prints — it's done when the **next**
session can find out what you learned. One winner to the journal:

```journal
---
topic: churn-model
outcome: winner
title: events_recent + lighter regularization, +0.029 PR-AUC
tags: [features, tuning]
---
**TL;DR**: adding a 7-day rolling `events_recent` feature and lowering
`min_child_weight` 5→2 lifted held-out PR-AUC 0.612 → 0.641 (+0.029). Came from a
hypothesis (model under-weights recent behavior), not a sweep. Next: confirm the
lift holds on a second time-split before promoting; watch `events_recent` for the
same horizon-leak failure mode as tenure_days.
```

<!-- priorstates:result src=c61b547672c8 kind=result -->
Journal entry recorded → entries/20260615_churn-model_a453a0.md  (winner)
<!-- priorstates:result-end -->

…and any durable preference that emerged, to memory:

```python
from priorstates.core.config import load_config
from priorstates.memory import api as mem

cfg = load_config()
res = mem.add_memory(
    cfg,
    name="churn-recency-features-help",
    type_str="project",
    description="Recent-behavior features carry signal the churn model under-weights",
    body=("Short-horizon rolling-activity features (e.g. 7-day events_recent) "
          "meaningfully lift PR-AUC on the churn model. Prefer adding/refining "
          "recency features before reaching for deeper trees. Always check a new "
          "recency feature for horizon leakage (cf. the tenure_days gotcha)."),
    scope="project",
    tags=["features", "churn-model"],
    overwrite=True,
)
print(f"memory saved → {res['scope']} scope: churn-recency-features-help")
```

<!-- priorstates:result src=776b304af1f9 kind=output -->
```output
memory saved → project scope: churn-recency-features-help
```
<!-- priorstates:result-end -->

---

## Step 5 — RECALL again: the loop closes

This is the whole point. Re-run the same Step-1 search. The winner you just
wrote is now in the results — so a fresh session (you tomorrow, a teammate, a
different agent) starts from your conclusion instead of a blank page:

```journal-search {topic=churn-model}
```

<!-- priorstates:result src=8704318966c2 kind=result -->
| date | outcome | topic | title | TL;DR |
|---|---|---|---|---|
| 2026-06-15 | gotcha | churn-model | [tenure_days leaks the label via a churn-date join](entries/20260615_churn-model_585140.md) | `tenure_days` was computed to the account-close date, so it encoded the answer. OOS AUC looked grea… |
| 2026-06-15 | decision | churn-model | [Optimize PR-AUC, not accuracy (4% positive class)](entries/20260615_churn-model_7c393a.md) | classes are ~4% positive; accuracy is dominated by the majority and moved the wrong way vs business… |
| 2026-06-15 | loser | churn-model | [Blind grid search over 64 hyper-param cells was noise](entries/20260615_churn-model_8e501b.md) | a 64-cell grid (lr × depth × subsample) produced a "winner" whose +0.4% AUC lift vanished on a fres… |
| 2026-06-15 | winner | churn-model | [events_recent + lighter regularization, +0.029 PR-AUC](entries/20260615_churn-model_a453a0.md) | adding a 7-day rolling `events_recent` feature and lowering `min_child_weight` 5→2 lifted held-out … |
<!-- priorstates:result-end -->

The list grew. Iteration *N+1* now begins where *N* ended — and it inherits the
loser, the decision, and the gotcha too. **That accumulation is the product.**

---

## See it outside this file

Everything you recorded is queryable from the CLI and visible in the cockpit:

```console
$ priorstates journal search --topic churn-model    # the same findings, from your shell
$ priorstates cockpit                               # browse Journal + Memory tabs in the GUI
```

In a real project you'd never run Step 0b by hand — your agent records winners
and losers as it works (after `priorstates agents install` wires the tools and
the standing research-protocol instruction into Claude / Codex / Gemini). This
file just compresses several sessions into one runnable page so you can watch the
loop close in 60 seconds.

---

## The five moves, mapped

| Step | Generic model research | On a trading desk |
|---|---|---|
| 1. Recall | `journal_search` / `memory_search` before coding | "what's been tried on this strategy?" before a new sim |
| 2. Hypothesize | one mechanism-driven feature/param change | one knob from theory + microstructure data |
| 3. Run / measure | train → PR-AUC on held-out split | `sim` → Sharpe / edge on IS **and** OOS |
| 4. Record | `journal_add` winner/loser + `memory_add` preference | journal the result with the number; memory the rule |
| 5. Recall again | next session sees the winner | next session skips the dead ends |

**Why it compounds:** every loop both *consumes* prior findings (step 1) and
*produces* new ones (step 4). Knowledge stops living in one person's head or one
chat transcript and becomes a durable, semantically-searchable base your agents
read automatically. That's the difference PriorStates makes to research work.

See also: [RESEARCH_WORKFLOW.md](../RESEARCH_WORKFLOW.md) ·
[QUICKSTART.md](../QUICKSTART.md) · [USER_GUIDE.md](../USER_GUIDE.md)
