"""Headless behaviour proofs for the five run_web_wavedude fixes."""
import asyncio
import json
import pathlib
import re
import sys

import numpy as np
import pyvista

sys.path.insert(0, "/workspace")
sys.path.insert(0, "/workspace/server")

RENDERS, PLOTTERS = [], []
_orig_render = pyvista.Plotter.render


def counting_render(self, *a, **k):
    RENDERS.append(1)
    PLOTTERS.append(self)
    return _orig_render(self, *a, **k)


pyvista.Plotter.render = counting_render

import trame
import trame.app
import poc_app as app

OUT = {}

# spy on the trame-pyvista view factory (FIX 5) ---------------------------------
# run_web_wavedude imports plotter_ui lazily, so patch its source module.
VIEWS = []
import pyvista.trame.ui as _pvt_ui

_orig_ui = _pvt_ui.plotter_ui


def spy_ui(plotter, *a, **k):
    v = _orig_ui(plotter, *a, **k)
    VIEWS.append({"kwargs": dict(k), "type": type(v).__name__,
                  "has_update": hasattr(v, "update")})
    return v


_pvt_ui.plotter_ui = spy_ui
try:
    import trame_pyvista.ui as _tp_ui
    _tp_ui.plotter_ui = spy_ui
except Exception:  # noqa: BLE001 - optional package
    pass

# capture the html layout instance (FIX 3 widget bindings) ----------------------
LAYOUTS = []
from trame_client.ui.core import AbstractLayout as _al

_orig_layout_init = _al.__init__


def _layout_init(self, *a, **k):
    _orig_layout_init(self, *a, **k)
    LAYOUTS.append(self)


_al.__init__ = _layout_init

# record controller trigger registrations (FIX 3 / FIX 1 widget bindings) --------
TRIG = []
from trame_server.controller import Controller as _Ctrl

_orig_trigger = _Ctrl.trigger


def _spy_trigger(self, name):
    register = _orig_trigger(self, name)

    def wrap(func):
        TRIG.append((name, getattr(func, "__name__", repr(func))))
        return register(func)

    return wrap


_Ctrl.trigger = _spy_trigger

# ---------- fixture ----------
nt, nx, nz = 4, 8, 5
nt_x, ny_x = 3, 6
rng = np.random.default_rng(0)
d = {
    "schema": app.WAVEDUDE_SCHEMA,
    "ez_ycut": rng.normal(size=(nt, nx, nz)),
    "ez_xcut_near": rng.normal(size=(nt_x, ny_x, nz)),
    "ez_xcut_far": rng.normal(size=(nt_x, ny_x, nz)),
    "t_ns": np.arange(nt) * 1e-3,
    "frame_index": np.arange(nt),
    "frame_index_xcut": np.arange(nt_x) * 2,
    "x_mm": np.linspace(0.0, 7.0, nx),
    "y_mm": np.linspace(-1.0, 1.0, ny_x),
    "z_mm": np.linspace(0.0, 2.0, nz),
    "nx": np.array(nx),
    "ny": np.array(ny_x),
    "nz": np.array(nz),
    "nt": np.array(nt),
    "nt_x": np.array(nt_x),
    "dt_s": np.array(1e-13),
    "cell_m": np.array(1e-5),
    "j_cut": np.array(3),
    "dump_stride": np.array(2),
    "nsteps": np.array(6),
    "f_ref_hz": np.array(1e10),
    "f_pulse_hz": np.array(1e10),
    "xcut_near_mm": np.array(1.0),
    "xcut_far_mm": np.array(5.0),
    "port_x_mm": np.array(0.5),
    "load_x_mm": np.array(6.5),
    "substrate_h_mm": np.array(0.5),
    "strip_w_mm": np.array(1.0),
    "eps_r": np.array(10.0),
    "v_analytic_m_s": np.array(1.5e8),
    "v_measured_m_s": np.array(1.5e8),
    "t_traverse_ns": np.array(0.05),
    "v_measured_reliable": np.array(1.0),
    "velocity_note": np.array("probe"),
}
np.savez("/tmp/wd_fixture.npz", **d)
info = app.load_wavedude(pathlib.Path("/tmp/wd_fixture.npz"))


# ---------- boot the app without entering the event loop ----------
class _Stop(Exception):
    pass


real_get_server = trame.app.get_server
box = {}


def fake_get_server(*a, **k):
    s = real_get_server(*a, **k)
    box["srv"] = s

    def _no_start(*aa, **kk):
        raise _Stop()

    s.start = _no_start
    return s


trame.app.get_server = fake_get_server
try:
    app.run_web_wavedude(info, "127.0.0.1", 8999, fps=25)
except _Stop:
    pass
finally:
    trame.app.get_server = real_get_server

srv = box["srv"]
state, ctrl = srv.state, srv.controller
OUT["boot_renders"] = len(RENDERS)
view_handle = getattr(app, "_LAST_VIEW", None)
OUT["frame_listeners"] = sorted(
    {getattr(f, "__name__", repr(f)) for f in state._change_callbacks.get("frame", [])}
    if hasattr(state, "_change_callbacks")
    else []
)

pushes = []
state._push_state_fn = lambda payload: pushes.append(dict(payload))
OUT["ready_before"] = {
    "ready": bool(state._status.ready),
    "skip_flushing": bool(state._status.skip_flushing),
}
state.ready()
OUT["ready_after"] = {
    "ready": bool(state._status.ready),
    "skip_flushing": bool(state._status.skip_flushing),
}

# ---------- FIX 1: writing state.frame reaches _show (slider path) ----------
RENDERS.clear()
pushes.clear()
state.frame = 2
state.flush()
OUT["slider_path"] = {
    "renders": len(RENDERS),
    "pushed_frames": [p.get("frame") for p in pushes],
    "state_frame": int(state.frame),
}
# unbounded recursion check: extra flushes with no new value must not redraw
RENDERS.clear()
state.flush()
state.flush()
OUT["slider_path"]["renders_on_redundant_flush"] = len(RENDERS)

# ---------- FIX 3: step buttons ----------
frames_y = nt
state.frame = 1
state.flush()
RENDERS.clear()
pushes.clear()
ctrl.step_fwd()
OUT["step_fwd"] = {
    "from": 1,
    "to": int(state.frame),
    "renders": len(RENDERS),
    "pushed": [p.get("frame") for p in pushes],
    "playing": bool(state.playing),
    "label": state.play_label,
}
RENDERS.clear()
pushes.clear()
ctrl.step_back()
OUT["step_back"] = {
    "to": int(state.frame),
    "renders": len(RENDERS),
    "pushed": [p.get("frame") for p in pushes],
}
state.frame = frames_y - 1
state.flush()
ctrl.step_fwd()
OUT["step_wrap"] = {"from": frames_y - 1, "to": int(state.frame)}
ctrl.step_back()
OUT["step_wrap_back"] = {"to": int(state.frame)}

# ---------- FIX 4: camera reframe on mode change ----------
pl = PLOTTERS[-1]


def cam(plane):
    return {
        "pos": [round(float(v), 3) for v in plane.camera.position],
        "focal": [round(float(v), 3) for v in plane.camera.focal_point],
        "parallel": bool(plane.camera.parallel_projection),
        "up": [round(float(v), 3) for v in plane.camera.up],
    }


cam_y = cam(pl)
ctrl.mode_toggle()  # ycut -> xcut
pl = PLOTTERS[-1]
cam_x = cam(pl)
OUT["camera"] = {
    "ycut": cam_y,
    "xcut": cam_x,
    "mode_after": state.mode,
    "camera_moved": cam_y["pos"] != cam_x["pos"],
}
ctrl.mode_toggle()
OUT["camera"]["mode_back"] = state.mode
pl = PLOTTERS[-1]
OUT["camera"]["after_back"] = cam(pl)

# ---------- FIX 2/3: play loop stopped by a second press ----------
state.frame = 0
state.mode = "ycut"
state.flush()
RENDERS.clear()
pushes.clear()
ticks = []
orig_sleep = asyncio.sleep


async def fake_sleep(delay):
    ticks.append(delay)
    if len(ticks) == 3:
        await ctrl.play_toggle()  # second press -> stop
    return None


asyncio.sleep = fake_sleep
try:
    asyncio.run(ctrl.play_toggle())
finally:
    asyncio.sleep = orig_sleep
OUT["play"] = {
    "ticks": len(ticks),
    "delays": [round(t, 4) for t in ticks],
    "renders": len(RENDERS),
    "pushed_frames": [p.get("frame") for p in pushes],
    "pushed_labels": [p.get("play_label") for p in pushes],
    "pushed_playing": [p.get("playing") for p in pushes],
    "playing": bool(state.playing),
    "label": state.play_label,
    "frame": int(state.frame),
}

# ---------- FIX 5: widget bindings in the built layout ----------
try:
    html = LAYOUTS[-1].html if LAYOUTS else ""
    if not LAYOUTS:
        OUT["html_error"] = "no layout captured"
except Exception as exc:  # noqa: BLE001
    html = ""
    OUT["html_error"] = repr(exc)
names = sorted({n for n in re.findall(r"trigger\('([^']+)'\)", html)})
OUT["layout_count"] = len(LAYOUTS)
OUT["trigger_names"] = names
OUT["views"] = VIEWS
registered = dict(TRIG)
OUT["triggers_registered"] = TRIG
OUT["html_trigger_fns"] = {n: registered.get(n) for n in names}
OUT["bound_fns"] = sorted(
    {registered[n] for n in names if registered.get(n)}
)
OUT["bindings_in_html"] = {
    n: (n in names) for n in registered
}
snippets = {}
for n in names:
    needle = "trigger('%s')" % n
    i = html.find(needle)
    snippets[n] = html[max(0, i - 80): i + len(needle) + 40] if i >= 0 else None
OUT["html_snippets"] = snippets
OUT["buttons_in_html"] = {
    k: (k in html) for k in ["prev", "next", "Switch plane", "{{ play_label }}"]
}
OUT["html_len"] = len(html)

# ---------- drive the EXACT functions the browser would call ----------
resolved = {}
for n in names:
    fn = ctrl._triggers[n]
    target = getattr(fn, "func", fn)
    resolved[n] = getattr(target, "__name__", repr(target))
OUT["html_trigger_handler_names"] = resolved

def drive(name, frame=None, mode=None):
    if frame is not None:
        state.frame = frame
    if mode is not None:
        state.mode = mode
    state.flush()
    fn = ctrl._triggers[name]
    target = getattr(fn, "func", fn)
    out = fn()
    return {"handler": getattr(target, "__name__", None),
            "frame": int(state.frame), "mode": state.mode,
            "coro": hasattr(out, "__aclose")}

OUT["drive_next"] = drive("trigger__3", frame=0, mode="ycut")
OUT["drive_prev"] = drive("trigger__2")
OUT["drive_plane"] = drive("trigger__4")
OUT["drive_play_is_coro"] = drive("trigger__1", mode="ycut")
# the play trigger above was only created, never awaited; close it



print("===RESULT===")
print(json.dumps(OUT, indent=1, default=str))
