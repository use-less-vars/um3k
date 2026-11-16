# trame hazards

Five places where this UI stack gives a confident, plausible, wrong answer. Companions: `UM3K_UI_ARCHITECTURE.md`
(the map) and `visualizer_architecture.md` (the plotter side). Three fields per entry, and `WHY IT HONESTLY
HAPPENS` always cites `file:line`: a citation you can read beats a sentence you must believe.

**Scope, honestly.** The citations are lines I read in this tree and in the package tree under `.venv/`. Figures
taken from the operator's record instead of re-run say *(as recorded)*; anything with no in-repo instance says
**INFERRED**. Where notes and code disagree, the code wins. The last section lists what is not claimed.

---

## 1. The `trame.widgets.vuetify3` shim is not a repo file, and it remembers

**SYMPTOM.** Widget behaviour changes between boots in one process. A recording subclass installed by boot
2 is still installed during boot 3, so per-boot counts drift — 16 / 21 / 16 across three boots *(as
recorded)* — and `isinstance` checks pass against your recorder instead of the canonical widget.

**WHY IT HONESTLY HAPPENS.** There is no `trame/` package in this repo; the module is a seven-line shim in
the installed tree:

```python
# .venv/lib/python3.12/site-packages/trame/widgets/vuetify3.py
from trame_vuetify.widgets.vuetify3 import *  # noqa F403
```

The only in-repo importer is the probe loop at `server/poc_app.py:5810-5817`, duplicated at `:7026-7032`:
it walks `("vuetify3", "trame.ui.vuetify3", "trame.widgets.vuetify3")` through `importlib.import_module`,
so the shim enters `sys.modules` only when that probe runs — and stays for the life of the process. A
recorder that "restores what it found" hands the next boot its own predecessor's recorder.

**WHAT TO DO.** Restore to the canonical class, not the remembered value. `tests/test_poc_run_config_panel.py:122-153`
already does it: pick `real` as the holder value where `isinstance(value, type)` (`:104-119`), wrap with
`setattr`, and in `finally:` `setattr(holder, name, real)` (`:151-153`). Its docstring (`:126-129`) gives
the reason — the canonical class "also repairs a shim that an earlier boot left holding a recorder". Reuse
`_recording`; `tests/test_poc_run_config_form.py:60-75` re-documents the same leak.

---

## 2. A `pyvista.Plotter.render` counter installed at the wrong moment counts nothing

**SYMPTOM.** `renders == []` while the frame demonstrably repainted. No error, no warning, just zero.

**WHY IT HONESTLY HAPPENS.** `tests/test_animation_volume.py:348-364` (`_render_doubled()`) saves whatever
`Plotter.render` it finds *at entry* and puts its own uncounted no-op in place:

```python
real_render = pyvista.Plotter.render                 # :359 saves YOUR counter
pyvista.Plotter.render = lambda self, *a, **k: None  # :360 shadows it
...
finally:
    pyvista.Plotter.render = real_render             # :364 hands it back
```

Install your counter *before* the `with` block and the recipe saves it as `real_render`, overwrites it with a
no-op, and restores it on exit: everything you wanted to count happened underneath the no-op. The working order
is at `tests/test_poc_run_config_solve.py:174-182` — counter installed *inside* the block (`:182`), with the
comment at `:176-181` saying exactly this.

The trap stays quiet because `render` is inherited: the package's only `def render(self)` is `BasePlotter`'s
(`.venv/lib/python3.12/site-packages/pyvista/plotting/plotter.py:2535`) and `class Plotter(_NoNewAttrMixin, BasePlotter)`
is at `:8261`, so `Plotter.__dict__` has no `render` — yet patching `Plotter.render` intercepts instance
calls by shadowing the base.

**WHAT TO DO.** Install the counting wrapper inside the borrowed context (`tests/test_poc_run_config_solve.py:174-182`),
or skip the borrow and boot via `_boot()` (`tests/test_animation_volume.py:200-202`) with your own no-op.

---

## 3. `State.flush()` on a not-ready server runs no listener and says nothing

**SYMPTOM.** You assign state, flush, and no `@state.change` listener fires. The derived field keeps its
default, so the listener-side half of the test fails while the assignment itself looks successful.

**WHY IT HONESTLY HAPPENS.** Flush is a silent refusal while the server is not ready:
`.venv/lib/python3.12/site-packages/trame_server/state.py:461-462` is `if self._status.skip_flushing: return None`,
and `skip_flushing` is `return self.flushing or not self.ready` (`:35-36`). A refused flush never dispatches
the `_pending_update` queued by `state[name] = value` (queuing only, `tests/test_poc_mode_picker.py:18-28`),
so no listener body runs — and `flush()` returning `None` reads the same as success.

**WHAT TO DO.** Make it ready, then flush — `srv.state.ready()` at `tests/test_poc_mode_picker.py:651` before
`state.flush()` at `:663`, or `with state:` at `:668`, whose `__exit__` is the listener-running flush (`:665-667`);
same rule at `tests/test_poc_run_config_panel.py:207-217`. `ready()` is process-wide: guard it
(`tests/test_poc_mode_picker.py:840-848`) and read `tests/test_poc_playback.py:4997-5001` for what breaks.

---

## 4. trame re-wraps your string attribute in double quotes, so `json.dumps` loses

**SYMPTOM.** The widget receives a mangled list — Vue parses the first token or throws — while the Python
value looks correct in a debugger.

**WHY IT HONESTLY HAPPENS.** For `v-`/`:` keys trame builds the quotes itself:
`.venv/lib/python3.12/site-packages/trame_client/widgets/vue.py:375` and `:377`,
`self._elem._attributes[name] = f'{js_key}="{translated_value}"'`. A `"`-quoted JSON payload therefore lands
inside `"`-quoted attribute text and terminates it; `repr` emits single quotes and survives —

```python
def _volume_clim_items_literal():
    """... trame re-wraps this string in DOUBLE quotes ...
    repr emits single quotes ..."""
    return repr([...])
```

— the comment at `server/poc_app.py:8887-8898` (`repr` itself `:8899-8904`), the same rule at `:11938-11944`, the
tuple/state-binding rationale at `:6286-6296`. Older notes cite "`poc_app.py:11652`", now `plotter.render()` in
the mode-vector-field toggle; the docstring's own cross-references (`server/poc_app.py:8888`, `:8894`) still
carry that stale pointer.

**WHAT TO DO.** Build `v_bind_items` literals with `repr`, never `json.dumps`, and bind a state tuple
(`v_bind_items=("name", default)`) rather than a bare list — a list passed as items reaches Vue as its first
element only (`tests/test_poc_playback.py:2323-2326`, `:2444-2446`, citing the same trame line at
`:2385-2390`).

---

## 5. `v_model` writes state but never triggers `@ctrl.set`

**SYMPTOM.** The select moves, state shows the new value, nothing downstream happens. The trigger written on
the v_model name never fires.

**WHY IT HONESTLY HAPPENS.** `server/poc_app.py:11554-11561` states the rule: a
`v_model=("volume_clim_mode", ...)` tuple only *writes* `state[...]`; trame turns a callable into a server
call for EVENT kwargs (`click=`, `change=`), never for `v_model`, so `@ctrl.set("volume_clim_mode")` is
unreachable — a `@ctrl.set` on any v_model name is dead code.

**WHAT TO DO.** Watch the state key, do not intercept the write: `@state.change("volume_clim_mode")` at
`server/poc_app.py:11561-11562`, body `:11577-11586` maintaining the derived `state.clim_relative_warning` (`:11583`)
and repainting via `_show` (`:11565-11567` explains why not `plotter.render()`); state initialised at `:9996-10004`,
widget bound at `:12054-12062` (`v_model=("volume_clim_mode", VOLUME_CLIM_DEFAULT)`, `v_bind_items=_volume_clim_items_literal()`).

---

## What is not claimed

- The 16 / 21 / 16 boot counts are the operator's record, not a measurement taken here; no `docs/` file holds them.
- No test was run to produce this file: every claim is about what the cited lines *say*, not about a suite.
- An earlier draft called `trame/widgets/vuetify3.py` a repo file; it is not: no `trame/` package exists here.
- Line numbers are exact for the tree as read and will drift — they already did once (hazard 4). Re-grep it.
