# SPICE adapter: scope and interface (E5)

**Status.** Proposal. No implementation, no solver and no code change accompanies this
document, and `emfit/spice.py` is absent from the tree before it and absent after it. Every
statement about code that exists carries a `path:line` citation checked against the working
tree this was written from. Every statement about behaviour that does not exist yet is
marked **PROPOSED**. A proposal is not evidence, and nothing here may be cited as a
measurement.

**What this document is.** Scope plus interface for the smallest circuit-facing boundary
worth building on top of `emfit/terminations.py`: what exists, what does not, what the
coupling algebra actually is, what a general netlist would cost, and what would count as
finished. It settles no physics and authorises no work (§11). It is written in the ledger's
own status vocabulary, where four labels exist and nothing else is a status word
(`docs/design/EM_SOLVER_LEDGER.md:12-21`).

---

## 1. Status of the ground this stands on

### EXISTS TODAY

| item | where | what it is |
|---|---|---|
| `TerminalPort` | `emfit/terminations.py:26` | The edge bundle one lumped termination attaches to. Constructed from `(L, W_E)` at `emfit/terminations.py:58`; exports `n_edges` (`:82`), `n_terminals` (`:87`), `voltage` (`:91`), `current_density` (`:111`), `port_power` (`:131`). |
| `RLCState` | `emfit/terminations.py:232` | Port + edge masses + field-advance hook + three history vectors; constructor at `emfit/terminations.py:264`. |
| `step_rlc` | `emfit/terminations.py:291` | One coupled trapezoidal step of a **single series RLC** load. The dense `n_t x n_t` block is assembled at `emfit/terminations.py:374-386` and solved at `:396-399`; the field back-reaction is `:403-405`. |
| the coupling derivation | `emfit/terminations.py:178-217` | Written out as a comment block above `RLCState`: field equation and branch equation, the companion coefficients, the elimination to one linear system, the definition of `M`, and the discrete energy statement. |
| tests for the above | `tests/test_terminations.py` | 605 lines, 11 test functions; the identity tests start at `:29`, the resistive-load test at `:204`, the LC-tank energy test at `:247`. |
| board-side load vocabulary | `emfit/board.py:70`, `:74`, `:119` | `LOAD_KINDS = ("series_r", "shunt_c")` (`emfit/board.py:70`), `class Load` (`:74`), `class Port` (`:119`). Two load kinds, both scalar-valued. |
| the E5 ledger row | `docs/design/EM_SOLVER_LEDGER.md:30` | Status `UNVERIFIED (Test A: algebraic identity only, 2026-11-11)`, with the TE direction and the 2026-11-11 amendment. |
| the roadmap proposal this continues | `docs/design/roadmap-next-2026-11-08.md:136-220` | §2 SPICE integration: the case for it, the format requirements, and a proposed module surface at `:181-185`. |

### DOES NOT EXIST

- `emfit/spice.py`. Verified absent: `ls emfit/spice.py` reports no such file. The roadmap
  proposes that module and three functions inside it (`docs/design/roadmap-next-2026-11-08.md:181-185`);
  none of the three is written.
- Any MNA assembly, companion-model evaluator or netlist reader in the package. Verified:
  `grep -rn "MNA\|netlist" --include=*.py emfit/` returns nothing. What exists is one
  hand-written, inlined companion for one series RLC branch (`emfit/terminations.py:389-399`).
- Any dependence on ngspice or Xyce. Verified: `which ngspice` is empty, `import ngspice`
  raises `ModuleNotFoundError`, and no `ngspice`/`ahkab`/`PySpice` package is installed.
- `TerminalImpedance`, `ModalCharacteristicImpedance` and `SParameterReferenceImpedance` as
  types. Verified: `grep -rn "TerminalImpedance\|ModalCharacteristicImpedance\|SParameterReferenceImpedance" --include=*.py .`
  returns nothing. The three names exist only as words in the E5 ledger row
  (`docs/design/EM_SOLVER_LEDGER.md:30`). They are ledger names, not classes (§6).
- Any nonlinear device, transmission line or multiport network at a port. `step_rlc` takes
  three floats, `R`, `L`, `C` (`emfit/terminations.py:291`), and the branch is one series
  path from each terminal to ground.

One staleness note, because the ledger row is load-bearing for this document and its
inventory has fallen behind its verdict. Row E5 records that `emfit/terminations.py` landed
on 2026-11-11 at "171 lines" with `tests/test_terminations.py` "carrying six gates"
(`docs/design/EM_SOLVER_LEDGER.md:30`); the file is 414 lines and the test module has 11
test functions (`wc -l emfit/terminations.py tests/test_terminations.py`). The staleness is
in the inventory, not in the verdict: the row's *status* claim, that what landed is an
algebraic identity and not a co-simulation, survives the growth, and the growth is exactly
`step_rlc`, the single-series-RLC companion, which is the object this document proposes to
generalise.

---

## 2. Why an adapter exists at all, and the one thing it must not become

Two goals get conflated every time "SPICE" is said in this tree, and they want different
programs.

**Goal (i) — a circuit simulator that consumes our port behaviour.** S-parameters or
waveforms go in; a driver network, a receiver, a termination run in a circuit solver; the
answer is a waveform the field solver never produced. The roadmap argues this one and
proposes the export path for it (`docs/design/roadmap-next-2026-11-08.md:136-150`,
`:181-185`), including the honest warning that a `.s2p` claiming `R 50` while the solver
normalised to something else produces a plausible wrong answer
(`docs/design/roadmap-next-2026-11-08.md:165-167`).

**Goal (ii) — a user putting an arbitrary network at a port instead of one series RLC.**
Here the field solver stays the outer loop; what changes is what hangs on the port. Today
that is not merely limited, it is structurally fixed: `step_rlc` consumes three scalars and
returns `(e_new, h_new, state_new)` (`emfit/terminations.py:291`), and the board model can
name only `series_r` or `shunt_c` with one scalar `value` each (`emfit/board.py:70-74`).

This document is about **(ii) and only (ii)**. The adapter proposed here is a lumped-network
evaluator that sits where `step_rlc` sits, on the same state-carrying contract, so that the
field loop cannot tell which of the two it is calling.

**The thing it must not become:** a second simulator whose agreement with the field is
established by whichever identity is cheapest to check. That failure mode has a named
specimen in this repository (§5) and it is the reason §5 exists as a section of its own
rather than as a caveat.

**Non-goals, stated plainly.**

- It is **not** a second field solver. All field motion stays in `emfit/evolve.py`; the
  adapter's only access to the field is the `advance` callable it is handed
  (`emfit/terminations.py:245-250`) and the port functionals it reuses (§3).
- It is **not** a replacement for `step_rlc`. `step_rlc` is the reference implementation of
  the coupling for a series RLC, its algebra is documented in place
  (`emfit/terminations.py:178-217`), and it is tested (`tests/test_terminations.py:247`).
  A general adapter that cannot reproduce it is wrong, and the cheapest way to say so is an
  acceptance criterion (§9.5).
- It is **not** a Touchstone exporter. That is the other goal's job and a different module
  surface (`docs/design/roadmap-next-2026-11-08.md:181-185`).

---

## 3. The existing boundary, described exactly

The boundary is two matrices and three functionals, and every one of them has a stated
meaning in the source.

**`L` is topology and carries no metric.** It is the signed incidence matrix of shape
`(n_edges, n_terminals)`; its `+-1` entries say which edge carries which terminal's current,
"it holds no length at all, so it is the same matrix whatever the grid metric is"
(`emfit/terminations.py:6-8`). Reversing a terminal's orientation flips the corresponding
column (`emfit/terminations.py:33-36`), and the flip is a joint sign flip of `v` and `i`, so
the port's power is invariant under it (`emfit/terminations.py:37-40`; pinned by
`tests/test_terminations.py:135` and `:345`).

**`W_E` is the metric.** It is the Hodge matrix of those same edges, "an edge length times a
dual face area, say", diagonal for an orthogonal grid and not diagonal for a lumped element
coupled through a non-orthogonal cell, "so nothing here assumes diagonality"
(`emfit/terminations.py:9-12`). It is used only as the coefficient matrix of a linear solve,
and **no inverse is formed** (`emfit/terminations.py:41-44`). That is a contract, not a
style preference: a write path that inverts `W_E` would turn an `O(n)` solve into an
`O(n^2)` factorisation and would change the numerical answer at round-off.

**The three functionals.**

- `voltage(e) = L.T @ e` — terminal voltages from edge voltages
  (`emfit/terminations.py:91-109`). Metric-free by construction: it reads `L` only.
- `current_density(i) = solve(W_E, L @ i)` — edge current densities from terminal currents
  (`emfit/terminations.py:111-129`). This is the one place the metric enters.
- `port_power(e, i) = v @ i` — the power at the terminals
  (`emfit/terminations.py:131-166`), with an optional second return value that evaluates the
  same power on the edges (`emfit/terminations.py:167-170`).

**Units and sign.** Edge quantities are SI in the solver's own frame; terminal quantities
are volts and amperes; `m_eps` is a per-edge capacitance in farads
(`emfit/terminations.py:239-244`). The sign convention is pinned in the class docstring: a
positive `port_power` means power is delivered from the EM field into the circuit's positive
terminal, equivalently `v @ i > 0` when the circuit absorbs, and the same power is negative
seen from the field side (`emfit/terminations.py:49-56`).

**The asymmetry that makes a boundary document necessary.** `L` is metric-free and `W_E` is
metric-ful, and they live in different spaces: `L` maps terminal currents to the edge space
without reference to lengths, while `W_E` maps that edge vector to a covector. A circuit
solver knows only terminal quantities; the field knows only edge quantities. So anything
crossing the boundary must say, in its own type, **which side's units it is in**. The
existing check for this is that a one-terminal port recovers the edge voltage itself
(`tests/test_terminations.py:85`) and that a three-terminal chain keeps the same identity
(`:96`) — a wrong unit convention survives neither.

---

## 4. The coupling mathematics, with the stamp written out

### 4.1 What the field step consumes, and what the circuit supplies

The field advances once **without** the load, `advance(e, h, dt) -> (e_star, h_new)`
(`emfit/terminations.py:245-250`, applied at `:363-368`), and everything the load does is a
correction to that. With `s = i^{n+1} + i^n` the twice-mid-step branch current, the two
equations that hold simultaneously are, verbatim from the derivation block,

```
field:   e^{n+1} = e* - (dt/2) m_eps^{-1} W_E^{-1} L s
branch:  v^{n+1} + v^n = a+ i^{n+1} + a- i^n + 2 v_c^n
```

(`emfit/terminations.py:185-186`), with `v = L.T @ e` and the companion coefficients
`a+ = R + 2L/dt + dt/(2C)`, `a- = R - 2L/dt + dt/(2C)` (`emfit/terminations.py:191-192`).
Eliminating `v` gives one linear system in `i^{n+1}`
(`[a+ I + M] i^{n+1} = v* + v^n - 2 v_c^n - [a- I + M] i^n`, `emfit/terminations.py:198-199`).

The coupling block is

```
M = (dt/2) L.T m_eps^{-1} W_E^{-1} L          (n_t x n_t)
```

described in the source as "the field's own reactance seen from the terminals"
(`emfit/terminations.py:200-201`). Read off the field equation, `v^{n+1} = v* - M s` — the
field is a Thevenin source `v* - M i^n` behind the impedance `M`, seen from the terminals,
with no inverse of `M` and no inverse of `W_E` anywhere in the step.

### 4.2 The standalone MNA system for a general network

For a general linear network of `R`, `L`, `C` and ideal sources written in companion-model
form, the trapezoidal MNA system over node voltages `u` (`n_t` rows) and the currents `i_V`
of the voltage-defined branches is

```
[ A(u)  B ] [ u^{n+1}   ]   [ r_u(history) + i_source^{n+1} ]
[ C     0 ] [ i_V^{n+1} ] = [ r_V(history) + e_source^{n+1} ]
```

with `A(u)` the node-admittance companion and `B`, `C` the incidence blocks of the
voltage-defined branches. This is textbook and it is **PROPOSED**: nothing of the kind
exists in this tree (§1).

### 4.3 The stamp: where `M` goes

Coupled, the field enters that system as a block of `n_t` voltage-defined branches whose
branch equation is the field's own discretisation:

```
field branch row m:   v_m^{n+1} + sum_k M[m,k] (i_k^{n+1} + i_k^n) = v*_m
```

so the stamp is exactly two additions: **add `M` to the `(i, i)` block** of the MNA matrix,
and **subtract `M i^n` from the corresponding source row**. `M` is dense in general, because
`W_E^{-1}` couples every edge of the port to every other.

Two equivalent readings, both of which the existing code has to satisfy:

- **field -> circuit**: a Thevenin source, `v*` in series with `M`, driving the network.
  Visible in the code as `rhs` gaining `v_star + state.v`
  (`emfit/terminations.py:397-398`).
- **circuit -> field**: a Norton-style current source. After the solve, the mean current over
  the step is injected as an edge current density and subtracted from the load-free edge
  voltages (`emfit/terminations.py:403-405`).

### 4.4 What is actually implemented today

Only the dense `n_t x n_t` trapezoidal block for **one series RLC per terminal**, assembled
in place inside `step_rlc` and never exposed: the column-by-column assembly of
`L.T m_eps^{-1} W_E^{-1} L` is `emfit/terminations.py:374-386`, the companion scalars are
`:389-392`, and the single linear solve is `:396-399`. There is no matrix object, no branch
list, no assembly step, and no device abstraction anywhere in the path — the `(i,i)` block is
`a_plus * eye + M` (`emfit/terminations.py:396`), which is diagonal-plus-dense only because a
series RLC contributes one scalar per terminal.

That is the entire generality that exists, and it is a measure of the distance to a netlist:
an arbitrary network makes `A(u)` block-sparse, puts off-diagonal terms into the circuit
block, and may need `n_t` larger than a dense `n_t x n_t` matrix and `n_t` metric solves can
comfortably carry. The cost of the present assembly is already `n_t` calls to
`current_density` plus one dense solve (`emfit/terminations.py:379-399`); it is written for
small `n_t` and nothing in the file claims otherwise.

---

## 5. The trap this document exists to keep shut

The E5 ledger row, amendment of 2026-11-11, in its own words:

> "the discrete balance of (a) is an algebraic tautology for ANY invertible `W_E` - symmetry
> is never used and no conservation law is being proven; junk matrices satisfy it."
> — `docs/design/EM_SOLVER_LEDGER.md:30`

The same fact is stated twice in the module it describes: "Symmetry of `W_E` is never used:
the identity is algebraic, not a consequence of the metric being symmetric, so a full metric
from a non-orthogonal cell is just as safe" (`emfit/terminations.py:45-47`), and, on the
`separate=True` return, "this is an algebraic identity for any invertible `W_E`, not a
physical conservation law -- it holds for junk matrices too, so it validates shapes and
conventions, not physics" (`emfit/terminations.py:150-153`).

**Consequence, stated as a rule.** `e^T j_port = v_p^T i_p` holds for any invertible `W_E`,
so a passing energy-balance test built on it is **not evidence of correct physical coupling**.
It is a shape-and-convention check. It can be a smoke test; it cannot be the acceptance
criterion for anything in §9. No subsection of this document re-introduces it as validation,
and any future test that does is testing the definition.

**What a power-conjugate (Kurokawa) interface would actually require**, and why it is
deliberately out of scope for E5: a reference impedance with a *real part*, and a
normalisation of the travelling quantities by `sqrt(Re Z_ref)` so that the squared magnitudes
of the waves are powers and `|a|^2 - |b|^2` is the power crossing the plane. The port as it
stands supplies an ideal algebraic pairing between terminals and edges; it supplies no
`Re Z_ref`, no wave normalisation, and no statement about which of the two the user means.
Building that is a separate decision with its own ledger row, and pretending the balance test
already covers it is how the tautology gets laundered into a validation. The current
S-parameters in this tree are voltage pseudo-waves, not power waves (§6).

---

## 6. Three impedance types that must never be silently converted

The E5 row names them — `TerminalImpedance`, `ModalCharacteristicImpedance`,
`SParameterReferenceImpedance` — and requires that "any use requires an explicit
normalization or transformation" (`docs/design/EM_SOLVER_LEDGER.md:30`). They are ledger
**names**, not classes; verified: no `.py` file in the tree mentions any of the three (§1).

| name | what it is the impedance *of* | what it is not |
|---|---|---|
| `TerminalImpedance` | The network hanging on the port's terminals: a property of a circuit element, defined at the terminal pairing `v` and `i` (`emfit/terminations.py:91`, `:111`). | Not a property of the line, and not normalised to any reference. |
| `ModalCharacteristicImpedance` | The line's own characteristic impedance for one mode, from a station fit of the travelling wave. | Not the port-plane V/I, and not what an S-parameter is referred to unless someone says so. |
| `SParameterReferenceImpedance` | The `z_ref` in the denominator of a wave normalisation, with a real part and a stated convention. | Not either of the above, and not transferable between them by a scalar factor when the line is lossy. |

**The confusion this prevents, from this repository's own artefacts.** One record carries two
different quantities under the name `z0`, and they differ by far more than round-off:

- `line.z0` = `42.75850315700394 - j16.046149777568516` — `z0_re` and `z0_im` at
  `evidence/termination/build_A_50ohm_p51_ghostwave.json:190-191`.
- `run.station_fit.z0` = `47.30581504575999 + j1.558214298741411` — inside `run.station_fit`
  at `evidence/termination/build_A_50ohm_p51_ghostwave.json:328-331`, a block that also
  records its own `span_m` (`:329`).

The record's own note on the station fit says which one the extraction consumes and which it
does not (`evidence/termination/build_A_50ohm_p51_ghostwave.json:400`), and this tree has
already been burned by the same collision elsewhere: two different `z0` quantities sharing a
key name is recorded as an audit finding at `decisions.md:4929`.

**And the wave convention.** The S-parameters in these records are voltage pseudo-waves
`B_v / A_v` referred to the run's own complex `zc`, not Kurokawa power waves; the record says
so in its `basis` field (`evidence/termination/build_A_50ohm_p51_ghostwave.json:335`) and
carries `validation_status: "UNVALIDATED"` (`:437`). Any adapter that converts between these
three impedances without a named transformation is producing a number nobody can refer back —
exactly the "second place for units to go wrong" the roadmap warns about
(`docs/design/roadmap-next-2026-11-08.md:152-156`).

---

## 7. Interface proposal — `emfit/spice.py`

**PROPOSED. None of this is implemented.** Signatures and contracts only; the typing is
illustrative and the module does not exist (§1). The shape is chosen so that the adapter is a
drop-in sibling of `step_rlc` (`emfit/terminations.py:291`), because that is the only way the
field loop stays unchanged.

```python
# emfit/spice.py — PROPOSED, NOT IMPLEMENTED
from dataclasses import dataclass
from typing import Literal, Sequence
import numpy as np
from emfit.terminations import RLCState, TerminalPort


@dataclass(frozen=True)
class Branch:
    """One lumped element between two nodes. Node 0 is ground; 1..n_t are port terminals."""
    kind: Literal["R", "L", "C", "V", "I"]
    nodes: tuple[int, int]
    value: float
    # Contract: SI units per kind (ohm, henry, farad, volt, ampere), non-negative for R/L/C.
    # Does NOT carry geometry, a net name or a position: placement is board.py's job.


@dataclass(frozen=True)
class CircuitNetwork:
    """A frozen branch list plus the node count it is defined on."""
    branches: tuple[Branch, ...]
    n_nodes: int
    # Contract: immutable, hashable, and ordered — branch order fixes MNA row order.
    # Does NOT parse SPICE netlist syntax, and does not accept subcircuits or .models.


@dataclass(frozen=True)
class SpiceState:
    """Everything the trapezoidal rule needs to take the next step."""
    network: CircuitNetwork
    i: np.ndarray          # port-terminal currents at t^n, shape (n_t,)
    v: np.ndarray          # terminal voltages at t^n, shape (n_t,)
    v_c: np.ndarray        # capacitor voltages at t^n, per capacitor branch
    i_l: np.ndarray        # inductor currents at t^n, per inductor branch
    # Contract: a step returns a NEW instance; the old one is never written to.
    # Does NOT hold the field, does not hold a time, and carries no adaptive controller.


class SpicePort:
    """Couples a CircuitNetwork to the field through an EXISTING TerminalPort."""

    def __init__(self, port: TerminalPort, m_eps: np.ndarray, *,
                 network: CircuitNetwork, advance=None) -> None:
        """Reuses `port` for both functionals and `m_eps` for the field inertia.

        Contract: M is built from `port.voltage` and `port.current_density` exactly as
        step_rlc builds it, so W_E is reused and never inverted and no second metric is
        introduced. `advance` is the same `(e, h, dt) -> (e*, h*)` hook RLCState takes.
        Does NOT accept a caller-supplied metric, does NOT assume W_E is diagonal, and
        does NOT re-derive the port's incidence.
        """

    def initial_state(self, *, v=None) -> SpiceState:
        """All-zero history at the terminals, then optional initial voltages.
        Contract: equivalent to RLCState(i=None, v_c=None, v=None).
        Does NOT run an operating-point solve and does NOT pre-charge anything."""

    def step(self, e, h, dt, state: SpiceState):
        """One coupled trapezoidal step. Returns (e_new, h_new, state_new).

        Contract: same signature and same return shape as emfit.terminations.step_rlc,
        e and state unmodified, h_new is h itself when advance is None.
        Does NOT iterate to convergence, does NOT adapt dt, does NOT differentiate
        through the step, and does NOT emit diagnostics.
        """


def s_parameters(port: TerminalPort, network: CircuitNetwork,
                 frequencies_hz: Sequence[float], *,
                 z_ref: complex) -> np.ndarray:
    """The network's reflection/transmission seen from `port`'s terminals, per frequency.

    Contract: returns complex S with shape (n_freq, n_t, n_t), referred to `z_ref`, and
    refuses a z_ref with no real part. The normalisation used is recorded by the caller;
    this function converts nothing between the three impedance types of §6.
    Does NOT extract the FIELD's S-parameters (that path is emfit/studies.py), does NOT
    extrapolate below the first frequency, and does NOT claim Kurokawa power waves.
    """
```

Notes on the shape, each of which is a decision rather than a preference:

- **The constructor takes a `TerminalPort`, not matrices.** `RLCState` already refuses
  anything else with a type error phrased as the reason
  (`emfit/terminations.py:265-271`), and reusing the port is what keeps the metric in one
  place (§3). A constructor that accepted `L` and `W_E` again would let two metrics drift.
- **`step` returns a triple.** The return contract is copied deliberately from
  `emfit/terminations.py:308-315` and `:411-413`, including the detail that `h_new` is `h`
  itself when `advance` is `None` (`emfit/terminations.py:312-315`).
- **The state is frozen and returns a new object.** The precedent is explicit: "A step never
  mutates a state; `step_rlc` returns a new one. Keeping the old one costs three short
  vectors and buys the ability to inspect or re-run the last step"
  (`emfit/terminations.py:259-262`).
- **`s_parameters` takes the port** so that the reference plane is the port's terminals and
  the reference impedance is a declared number rather than an assumption. It is a
  circuit-side function: it evaluates the network, not the field.

---

## 8. Decision: a minimal internal evaluator, not ngspice

Three options were considered for the storage and evaluation of the network.

**(a) A minimal internal netlist/MNA evaluator**, `R`, `L`, `C` and ideal sources only,
assembled per step in NumPy.
**(b) Drive an external ngspice through its shared-library interface** (`ngspice.so` /
Cython bindings), keeping the network in the simulator.
**(c) Emit a netlist file and shell out**, either once per run or per batch of steps.

| axis | (a) internal MNA | (b) ngspice shared library | (c) netlist + subprocess |
|---|---|---|---|
| expressiveness | R, L, C, ideal V/I. No BJT/MOS, no subcircuits, no `.model`. | whatever ngspice supports. | whatever ngspice supports. |
| dependency weight | NumPy, already required (`numpy 2.5.4` in this environment). | a simulator built from source or a distro package plus dev headers; nothing of the sort is installed (`which ngspice` empty). | the same binary, plus a text-format contract that has to be pinned. |
| runs in this container | yes: pure Python/NumPy; the cgroup limit here is 512 MB (`/sys/fs/cgroup/memory.max` = `536870912`). | no: no library, no network to fetch one. | no: no binary. |
| determinism / reproducibility | total: the same inputs give bit-identical output, and the artefact can be committed as evidence. | version- and build-dependent; a committed record would have to carry the simulator version, and the tree's records do not carry one. | worse: scheduling and file I/O enter the loop. |
| energy conservation and per-step state | the companion block is in our own array, so the per-step ledger of `emfit/terminations.py:211-213` can be extended to it term by term. | power bookkeeping would be reconstructed from the simulator's waveforms after the fact. | the same, plus a protocol. |
| debugging | a stack trace into our own assembly. | a stack trace into a C library through a binding. | a stack trace, a log file, and a schema. |

**Recommendation: (a).** The reasons are constraints, not taste. The evidence culture here is
committed, machine-checkable artefacts — the ledger is written so a later reader can decide
what is finished (`docs/design/EM_SOLVER_LEDGER.md:1-8`), and the termination records are
JSON under `evidence/termination/` with per-field notes (`evidence/termination/build_A_50ohm_p51_ghostwave.json:400`).
A result whose reproduction depends on a simulator binary that is not in the environment, and
whose version is not in the record, does not fit that culture. Option (b) also puts the
per-step state inside a library we cannot inspect, which is precisely the quantity the
coupling ledger is written in (`emfit/terminations.py:211-213`); option (c) adds a protocol
whose failure modes are invisible in an artefact.

**What (a) cannot do, stated plainly.** It cannot evaluate a nonlinear device, so it cannot
answer the question that motivates the roadmap's SPICE case — "a real driver and a real
receiver" (`docs/design/roadmap-next-2026-11-08.md:148-150`) — because a nonlinear load needs
a Newton loop and `step_rlc` is explicit by construction ("No Newton iteration is needed and
none is used", `emfit/terminations.py:209-211`). It cannot evaluate a transmission line
without a delayed-branch history. It cannot read a netlist file. Choosing (a) buys
determinism and a checkable energy statement at the price of the class of problem that made
SPICE interesting in the first place; that trade is the right one for a first slice whose
acceptance criteria (§9) are all linear, and it remains reversible, because a branch list is
also the natural input to a future ngspice driver.

---

## 9. Acceptance criteria for E5

Each is independently checkable, and none of them is the tautology of §5. Tolerances are
stated as **PROPOSED** values to be fixed, and justified, in the test that uses them; a
tolerance chosen to make a number pass is not a criterion.

1. **Resistive termination against textbook algebra.** A one-terminal port with a known
   diagonal `W_E`, a series `R` and `C = L = 0`, reproduces the analytic reflection
   coefficient of that branch, evaluated against `M` computed independently in the test, to
   `|ΔΓ| ≤ 1e-6`. This checks the circuit half only; it does not validate the field coupling,
   and it must be labelled that way in the test.
2. **Consumed power against dissipated power, with the two sides computed from different
   objects.** Over a run, `Σ_v v^T i` (from the updated field, `emfit/terminations.py:166`)
   matches `Σ_n (dt/4) R s_n^2` with `s_n = i^{n+1} + i^n` (the branch's own Joule
   accumulation, `emfit/terminations.py:213`), to a stated relative tolerance. This bites
   because a wrong back-reaction moves `v`; it would not bite if both sides were the
   `separate=True` pair (`emfit/terminations.py:167-170`), which is forbidden here.
3. **Reproduction of an existing record's S11 for the 50 ohm case.** `|S11|` within `0.001`
   of `0.32586326001662264` (`evidence/termination/build_A_50ohm_p51_ghostwave.json:337`).
   Carried with the record's own qualification: it is `UNVALIDATED` (`:437`) and sits about
   5 percent below a series-R anchor that the ledger records as retired rather than
   confirmed (`docs/design/EM_SOLVER_LEDGER.md:26`). Meeting this criterion demonstrates
   that the adapter reproduces the tree's own number; it does not make that number correct,
   and it may not be reported as validation of the record. This is the only criterion that
   needs the field loop, and it is the expensive one.
4. **State immutability across a step.** After `step(e, h, dt, state)`, the input `state`'s
   arrays are unchanged and the returned state is a different object, asserted on every
   array the state carries — the convention pinned at `emfit/terminations.py:259-262`.
5. **Absent element.** `R` only, `C = 0`, `L = 0` behaves as a resistance to ground, not as an
   open circuit: the companion convention of `emfit/terminations.py:389-390` and the test
   that already pins it for `step_rlc` (`tests/test_terminations.py:204`). The adapter must
   agree with `step_rlc` on the same inputs, which is a second, independent check that the
   general path degenerates correctly.

Criterion 3 is the only one that can move the ledger row. Criteria 1, 2, 4 and 5 can all pass
on a network evaluator that is wrong about the field, which is why they are numbered beside
it and not instead of it.

---

## 10. Open questions

- **Multi-terminal networks onto multiple ports.** One `CircuitNetwork` above one
  `TerminalPort` is the assumed shape. A network touching two port planes needs either two
  ports in one network object or a super-port, and `TerminalPort` as written describes one
  bundle (`emfit/terminations.py:26-30`). Undecided.
- **`n_t` beyond a dense block.** `M` is dense and so is `lhs` (`emfit/terminations.py:396`),
  with an `O(n_t)` assembly cost (`:379-386`). Where the crossover to a sparse solve sits,
  and whether `M` is ever assembled explicitly, is unanswered; nothing here measures it.
- **Board dataclasses.** Whether `Load` grows a branch list, gains a third `kind`, or is left
  alone beside a new type. Today it is one scalar per load with two kinds
  (`emfit/board.py:70-74`), and `Port` is a geometric plane that knowingly records an unused
  `y` (`emfit/board.py:119-140`) — neither is obviously the right home for a network.
- **Timebase.** If an external simulator is ever involved, who owns `dt`. The roadmap
  names the same question and recommends the one-way version only
  (`docs/design/roadmap-next-2026-11-08.md:196-197`, `:218-220`). Unresolved here; the
  proposal in §8 sidesteps it by never leaving the process.
- **Where the S-parameter convention is recorded.** A `.s2p` option line has one field for
  the reference impedance and none for the convention, so a voltage pseudo-wave set and a
  power-wave set are indistinguishable in the file — the laundering risk the roadmap flags
  (`docs/design/roadmap-next-2026-11-08.md:115-117`). Out of scope here, but it is the next
  place this document would need an amendment.

---

## 11. What this document does not authorise

It does not authorise a solver, a step of any study, or a change to
`emfit/terminations.py` — that file is cited here as it stands, and its algebra and sign
convention are inputs to this proposal, not subjects of it. It does not authorise adding a
dependency; the recommendation in §8 adds none. It does not authorise the three impedance
types of §6 to be created as classes, which is a separate decision with its own conversion
rules. And nothing here may be cited as evidence that the existing coupling is
power-conjugate: the balance `e^T j_port = v_p^T i_p` is an algebraic tautology for any
invertible `W_E` (`emfit/terminations.py:150-153`, `docs/design/EM_SOLVER_LEDGER.md:30`), the
S-parameters in these records are voltage pseudo-waves against the run's own complex `zc`
(`evidence/termination/build_A_50ohm_p51_ghostwave.json:335`), and E5 remains `UNVERIFIED`.
