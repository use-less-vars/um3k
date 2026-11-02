# Wiring AC-4: the grader has a Gamma *model* and no Gamma *measurement*, and the bar cannot pass

**Slug** `ac4-wiring-scope-2026-11-02`. **Status: reads, plus arithmetic over one live grading run. No edit.**
No write under `emfit/`, `evidence/termination/grade_2b.py`, `decisions.md`, `dispatch_log.md` or
`defect_register.md`; no banked artefact edited; no gate re-priced; no verdict moved; nothing committed. §C is a
**proposal, unapplied** — the fences for this pass do not reach `grade_2b.py`. Every number below is quoted from
a file named beside it, or is arithmetic over numbers so quoted, except the §D table, which is a live
`grade_2b.py --out /tmp/graded.json` over `A_v3c + E_v3c + B_v3c` — written to `/tmp`, not into the repo.

Tags: **[M]** measured, artefact named beside it · **[L]** read from the project's own record · **[R]** relayed.

---

## A. The bar, and what "wired" would mean

Verbatim, `absorbing_termination_scope.md:246-249` (and re-quoted in the grader at `:327-332`):

> **AC-4. The load value has to matter.** For at least two unmatched loads, `|Gamma|` within 3 % of
> `|R - Zc| / (R + Zc)`. The 3 % is the tolerance already recorded for the Fresnel case at `:337-339`;
> it is borrowed, not invented, and if it is the wrong tolerance for this quantity then that is a
> legitimate objection to it rather than a reason to pick another.

Three separable things must exist before that sentence is gradeable: (i) an **achieved** `|Gamma|` read from
an artefact; (ii) a **model** `|Gamma|` computed as the bar writes it; (iii) a **classification** of which loads
are "unmatched", with a count over them. "Wired" means all three exist and a boolean falls out of them. It does
not mean the criterion passes — §D.

## B. What the grader has today

`grade_2b.py:326-341`, the AC-4 block, has none of the three:

- `:327-332` the bar quoted · `:333` `"bar_source": f"{SCOPE}:246-250"` — the record half, complete.
- `:334` `"achieved": None` · `:335` `"pass": None` · `:336` `"closable_in_run_a": False`.
- `:337-340` `"status"`: "not closable in this batch: AC-4 needs at least two UNMATCHED loads, and the batch
  carries one matched load (50 ohm) plus one exploratory 100 ohm arm. No proxy is substituted -- deferred to
  dispatch 2c."

`:46` carries `GAMMA_REL_TOL = 0.03    # scope:246  AC-4`, and `:561` re-publishes it as
`"gamma_relative_AC4": GAMMA_REL_TOL` inside `bars_quoted_not_adjusted` — echoed, never applied.

**Correction to the record.** `dispatch_log.md:52`, row `blocker-recon-2026-11-02`, says the grader contains no
Gamma arithmetic at all. That is **false in one half and true in the other.** `grade_b` (`:490`) computes

```
:493    gamma_model = abs(100.0 - zc) / (100.0 + zc)
:503    "gamma_model": gamma_model,
:504    "gamma_model_basis": f"|R - Zc| / (R + Zc) with Zc = {zc:.6f} ohm",
```

which **is** Gamma arithmetic, in the bar's own model and the bar's own form, published with its basis. What is
absent is the other side of the comparison: no `|Gamma|` is read, differenced, or counted anywhere. The accurate
form is **a Gamma model and no Gamma measurement**, not "no Gamma arithmetic". `grade_b` also marks itself
`exploratory: True` (`:499`), `acceptance_criterion: False` (`:500`), `"pass": None` (`:508`), so nothing it
computes can move a verdict today — and its `100.0` is a literal, not its own arm.

So the wiring is not an idea imposed on a stranger: `:493` is two-thirds of it, hard-coded to one arm and
unreachable from `criteria`.

## C. The wiring, unapplied

Four pieces, in dependency order.

1. **`AC4_BAR`** — a module constant holding the bar text, lifted out of `grade_a`'s AC-4 block; `:327-332` and
   the new grader both reference it, so the two cannot drift.
2. **`gamma_model(r_ohm, zc, kind)`** — `series_r` → `abs(r / (2.0 * zc + r))`; `shunt_c` → `ValueError`. The
   refusal is the point, not an omission: a shunt capacitor's reflection is frequency-dependent and no arm
   carries a resistive termination — `LOAD_KINDS` (`emfit/board.py:70`) has no resistive shunt at all.
3. **`grade_ac4(docs)`** — per arm `{arm, load_ohm, load_kind, zc_ohm, achieved_gamma, source_field:
   "s11.magnitude", gamma_model, gamma_model_basis, deviation, within_tol, unmatched}`, plus top level
   `achieved: {arms, n_arms, n_readable, n_unmatched, tolerance}`, `pass_if_wired = (n_unmatched >= 2 and all
   within_tol)`, and deliberately `"pass": None`, `"closable_in_run_a": False`. `unmatched` is asked in the
   **terminating** form (`|R - Zc|/(R + Zc) > GAMMA_REL_TOL`), because matching is a property of the load
   against `Zc`, not of the series element inside the line (§D).
4. **`main`** — `criteria["AC-4"] = grade_ac4(docs)` immediately after `:582` (`criteria = grade_a(a)`), the slot
   `:584` already uses for AC-7. `docs` is in scope from `:541`, and every helper needed is already imported or
   defined: `dig`, `finite_number`, `label_of`, `json_safe`, `load_ohm`, `cut_mm`, `load`, `_MISSING`, `SCOPE`.

One knock-on: `grade_b`'s literal `100.0` (`:493`, `:504`) should read its own arm's
`run.kwargs.loads[0].value` / `.kind`, which `main` already extracts for `inputs`; its local `gamma_model`
renamed `model` so it does not shadow the new function — while **keeping** the emitted keys `gamma_model` /
`gamma_model_basis`, which are published surface already sitting in banked artefacts.

## D. Why the pass bit still does not get wired

Two independent reasons; either alone is sufficient.

**(1) The batch does not meet the bar's precondition.** With `z0 = 47.119454769635006` ohm (`AC-7.achieved.
beta_modal.z0_ohm`, live run), the terminating form gives 0.029660 at R = 50 and 0.359440 at R = 100. Both 50 Ω
arms sit at 0.0297, *inside* `GAMMA_REL_TOL` → matched. Only the 100 Ω arm is unmatched: **n_unmatched = 1**,
and the bar asks for at least two.

**(2) The bar as written cannot pass a correct answer** — DR-16. Live run:

| arm | load | `s11.magnitude` | terminating model | dev | series model | dev |
|---|---|---|---|---|---|---|
| A | 50 Ω `series_r` | 0.325565 | 0.029660 | +997.7 % | 0.346647 | −6.08 % |
| E | 50 Ω `series_r` | 0.296951 | 0.029660 | +901.2 % | 0.346647 | −14.34 % |
| B | 100 Ω `series_r` | 0.473884 | 0.359440 | +31.84 % | 0.514830 | −7.95 % |

Under the bar's own terminating form nothing is within 3 %. Under the form of the element actually built, all
three are outside 3 % too, and the *same 50 Ω load* reads 9.6 % apart between arms A and E
(0.325565 / 0.296951) — **the tolerance is narrower than the spread between two arms measuring one load**. The
two forms differ by 43.2 % at R = 100 (0.514830 / 0.359440 = 1.4321), **14×** the tolerance. A criterion that
fails every legitimate reading in either form, for reasons of form-mismatch and residual spread rather than
physics, is not a safety check:

> `defect_register.md:216-217` (DR-16, `:102`): "a criterion that cannot pass on legitimate input is a
> prohibition, not a safety check".

So `grade_ac4` ships `pass_if_wired` — the answer, computed and published — and `"pass": None` — the bit, not
set. Setting it now would either move a verdict on a batch that cannot satisfy the bar, or soften the bar in the
same edit that grades it. Both are the caller's decision, not a worker's.

## E. Which field is `|Gamma|`

`s11.magnitude` — `run_build_A.py:1458` (`s11_two_wave_mag`, the two-wave |B/A| at the port plane,
`validation_status: "UNVALIDATED"` at `:1468`). The two candidates beside it are both wrong, and one is wrong in
a way that would *flatter* the criterion:

- **`s11_at_plane.magnitude`** (`:1485`) sits on a flat floor — 0.0222068 / 0.0489985288420461 / 0.0475084 /
  0.0463117 across R = 25/50/100/200 (`dispatch_log.md:49` field D) — and does not track the load. It reads
  A = 0.049 vs E = 0.355 for the *same* 50 Ω load, so it measures the plane, not the termination. Choosing it
  would put E's 0.354909 within 2.4 % of the series model 0.346647: a pass for the wrong reason.
- **`magnitude_one_wave_station_fit`** (`:1459`) is the one-wave fit, whose `beta` is biased +27–36 %
  (`s11_one_wave_vs_two_wave_2026-11-02.md` §1). On these arms it reads 25–29 % below the two-wave value
  (0.232167 / 0.325565 = 0.713; 0.355884 / 0.473884 = 0.751) — biased low by a known, diagnosed amount, so it
  would bias `within_tol` toward passing.

Residuals of the chosen field are themselves unvalidated and configuration-dependent: 5.5 % (n=64, load 20 mm),
7.6 % (n=54, 100 Ω), 13.8 % (n=79, load 30 mm) — `run_build_A.py:1477-1478`, `UNVALIDATED`.

---

**Left open for the caller.** (a) Soften the bar — a model matching the series element, and a tolerance derived
from the A-vs-E spread rather than borrowed from the Fresnel case — or keep it and accept that AC-4 stays
unclosable. (b) Whether a second unmatched load is worth building for a criterion whose tolerance is currently
narrower than the arm-to-arm spread.
