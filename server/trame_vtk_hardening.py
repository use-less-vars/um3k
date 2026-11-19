"""Runtime hardening for trame_vtk's VTK scene serializers.

WHAT THIS IS.  ``trame_vtk`` 2.11.17 keeps per-object bookkeeping that a page
which re-draws every tick cannot afford and that, in the worst case, hands one
array's hash to another array:

* ``serializers/serialize.py:44-46`` -- ``remove()`` calls
  ``DELETE_CALLBACKS.remove(instance_id)`` on a plain list, so a delete event for
  an id that is no longer tracked raises ``ValueError`` out of a VTK observer
  callback (VTK prints it and carries on), and every ``serialize()`` call pays an
  O(n) scan of that list (``serialize.py:27``).
* ``serializers/helpers.py:41-57`` -- ``data_array_sha_mapping`` is keyed on the
  array pointer (``utils.reference_id``) and NOTHING ever prunes it, so it grows
  with the number of arrays the page has ever built (measured 7 -> 3941 entries
  over 2000 churn ticks before this patch).
* ``serializers/helpers.py:16-30`` -- ``data_table_to_list`` re-unpacks the whole
  table (a 256-entry LUT is ~1300 Python objects) on every export, and
  ``cache.py``/``synchronization_context.py`` keep their caches without bound.

WHAT IT DOES.  Monkey-patching only, applied at runtime, undoable with
``uninstall()``; not one byte of ``site-packages`` is touched.  Three groups:

P1  ``serialize.remove`` becomes total (guarded, discard semantics, cheap) and
    ``serialize.DELETE_CALLBACKS`` becomes a list with O(1) membership and a hard
    cap.  Both keep their module-global names and their list behaviour, because
    ``serialize.serialize`` itself and ``vtkWebLocalRendering`` read them.
P2  ``helpers.digest`` gets an identity-validated, LRU-capped cache (it can never
    answer with another array's hash); ``cache.PROP_CACHE`` and
    ``SynchronizationContext.data_array_cache`` get hard caps that only ever
    evict what has stopped being serialized.
P3  ``helpers.data_table_to_list`` is memoised on (identity, mtime) and returns an
    immutable tuple-of-tuples -- the same JSON as the list-of-lists it replaces.
P4  ``serialize.serialize`` no longer attaches a ``vtkCommand.DeleteEvent``
    observer to every object it exports (``serialize.py:27-31``); ``cache.PROP_CACHE``
    gains a *witness* that drops a record for an id that is PROVABLY recycled.
    See the two sections below.

WHY THE CACHE IS KEYED ON ``id()`` AND NOT ON A WEAKREF KEY.  A weakref to a VTK
array CAN be created (``weakref.ref(vtk.vtkFloatArray())`` works), but the
wrapper is UNHASHABLE (``hash(vtkFloatArray())`` raises ``TypeError``), so a
weakref cannot be a dict key -- ``hash(weakref.ref(obj))`` is
``hash(obj)``.  The cache therefore keys on ``id(array)`` and validates every hit
with the weakref it stores in the record: a record only ever answers for the very
object it was made from, and the weakref's callback drops the record when that
object dies.  Address reuse is thus harmless; the fingerprint
(``reference_id``, mtime, shape, type) is kept in the record for diagnostics and
is the whole key only on the (never observed) path where weakrefs are refused.

WHY THERE IS NO DeleteEvent OBSERVER ANY MORE (DO NOT PUT IT BACK).  Stock
``serialize()`` attaches ``lambda *_a, **_k: remove(instance_id)`` as a
``vtkCommand.DeleteEvent`` observer to EVERY object it exports, and a page that
re-draws every tick exports thousands of short-lived Python wrappers per frame
(``GetTable()``, ``GetProperty()``, ``GetInput()`` and friends).  When a garbage
collection reclaims one of those wrappers the VTK destructor fires the event and
VTK calls back into Python: ``remove()`` runs dict/list surgery from inside a
destructor, during a collection pass, while ``vtkPythonCommand`` is also dropping
the callable it holds.  That re-entrancy is the landmine this module used to step
on: the first crash died inside ``helpers.data_table_to_list`` (the allocation
storm P3 removes); with that storm gone the next collection to happen was in the
state-flush/publish path (``state.flush`` -> ``protocol.push_state_change`` ->
``wslink.publish`` -> the serializer's lambda -> Garbage-collecting) and it died
there instead.  P1 made the callback raise-proof, which was never enough: it must
not run at all.  So ``serialize()`` does not attach it.

WHAT REPLACES THE OBSERVER.  Nothing is told that an object died, and nothing
runs during a collection: the witness ``serialize()`` records is a plain
``weakref`` with NO callback, so reclaiming an object cannot re-enter this module
at all.  Invalidation instead rides on the properties the caches already have:
they are BOUNDED (nothing accumulates for a long-lived page), and
``cache.PROP_CACHE`` drops an id at the next export, from ordinary Python, when
that id is PROVABLY recycled -- i.e. when it is claimed by a different live
wrapper, or by a different class, than the one that cached it.  What is
deliberately NOT done is dropping the record merely because the wrapper died:
trame_vtk re-wraps the same C++ object on every export (``GetProperty()``,
``GetLookupTable()``, ``GetInput()`` and friends hand back a fresh short-lived
wrapper), so wrapper death is the normal case and not a death certificate.
Treating it as one re-sends every object's full property set on every frame --
measured 17,167 B -> 23,629 B on a two-export scene, i.e. the delta protocol
defeated.  The residual case is accepted and named here: a new object at a
recycled address OF THE SAME CLASS can be answered with a delta computed against
the dead object's values.  That is a short property set, never a crash, and it
clears as soon as that object changes.

``DELETE_CALLBACKS``, ``remove()`` and ``remove_from_cache()`` still exist and
still work (they are part of ``serialize``'s surface); nothing drives them from
destruction any more, so ``DELETE_CALLBACKS`` simply stays empty.

FAIL SAFE.  ``install()`` verifies every attribute it means to wrap -- existence,
kind, callable, defining module, signature -- BEFORE it patches anything.  Any
surprise means nothing is patched, the report says ``not_patched`` with the list
of problems, and no exception escapes.  ``POC_NO_VTK_PATCH`` set to anything but
``0``/empty disables the module entirely.  A successful install prints exactly
one ``[poc_app]`` line to stderr and nothing else; a disabled or refused install
prints nothing.

The sanity rule this module is written against: the serialised payload must be
byte-for-byte what unpatched trame_vtk produces.  Nothing here changes what is
emitted; the caches only change how often the same value is recomputed.
"""

from __future__ import annotations

import importlib
import inspect
import os
import sys
import weakref
from collections import OrderedDict

#: Non-empty and not ``"0"`` -> the module does nothing at all.
_ENV_KILL = "POC_NO_VTK_PATCH"

#: Caps.  Every one of them is a number of ENTRIES, and every one of them is
#: several times what a page with a few thousand actors needs, so that eviction
#: is a runaway-pager safety valve and not part of normal operation.
SHA_CACHE_MAX = 4096
PROP_CACHE_MAX = 20000
DATA_ARRAY_CACHE_MAX = 4096
DATA_TABLE_CACHE_MAX = 256
DELETE_CALLBACKS_MAX = 65536

_MODULES = {
    "serialize": "trame_vtk.modules.vtk.serializers.serialize",
    "cache": "trame_vtk.modules.vtk.serializers.cache",
    "helpers": "trame_vtk.modules.vtk.serializers.helpers",
    "sync": "trame_vtk.modules.vtk.serializers.synchronization_context",
}

#: ``SynchronizationContext`` methods P2 leans on (class attributes).
_CTX_MEMBERS = (
    "cache_data_array",
    "check_for_arrays_to_release",
    "get_cached_data_array",
)

#: Instance state those methods keep.  ``data_array_cache`` is created in
#: ``SynchronizationContext.__init__`` (``self.data_array_cache = {}``), so it is
#: verified through ``__init__``'s code object, not with ``hasattr`` on the class.
_CTX_STATE = ("data_array_cache",)

#: Attributes of ``serialize`` the P4 replacement reads at call time.
_SERIALIZE_GLOBALS = ("SERIALIZERS", "class_name", "NO_SERIALIZER_FOR_INSTANCE", "logger")

_MISSING = object()

#: (module key, attribute, kind, expected leading parameter names)
_SPEC = (
    ("serialize", "serialize", "callable",
     ("parent", "instance", "instance_id", "context", "depth")),
    ("serialize", "remove", "callable", ("instance_id",)),
    ("serialize", "remove_from_cache", "callable", ("obj_id",)),
    ("serialize", "DELETE_CALLBACKS", "list", ()),
    ("cache", "PROP_CACHE", "dict", ()),
    ("cache", "cache_properties", "callable", ("obj_id", "ctx", "props")),
    ("cache", "remove_from_cache", "callable", ("obj_id",)),
    ("cache", "get_cached_property", "callable", ("obj_id", "prop")),
    ("helpers", "digest", "callable", ("array",)),
    ("helpers", "data_table_to_list", "callable", ("data_table",)),
    ("helpers", "hash_data_array", "callable", ("data_array",)),
    ("helpers", "reference_id", "callable", ("ref",)),
    ("helpers", "data_array_sha_mapping", "dict", ()),
    ("sync", "SynchronizationContext", "class", ()),
)

#: The names reported back in ``report["patches"]``.
_PATCHES = (
    "serialize.serialize(no observer, PROP_CACHE dropped on recycling)",
    "serialize.remove",
    "serialize.DELETE_CALLBACKS",
    "helpers.digest",
    "helpers.data_array_sha_mapping",
    "helpers.data_table_to_list",
    "cache.cache_properties(PROP_CACHE cap)",
    "sync.SynchronizationContext.data_array_cache",
)

_STATE = {"installed": False, "report": None}

#: (module, attribute, value to put back) for everything ``_apply`` changed, most
#: recent last, so ``uninstall()`` can walk it backwards.
_RESTORE: list = []

#: The live caches (None until ``install()``): the digest cache doubles as the
#: new value of ``helpers.data_array_sha_mapping``.
_DIGEST_CACHE = None
_TABLE_CACHE = None

#: ``instance_id`` (pointer string) -> ``(weakref to the wrapper that claimed it,
#: that wrapper's class name)``, or ``(_UNWITNESSED, name)`` when no weakref could
#: be taken.  This is what P4 uses instead of a ``DeleteEvent`` observer.
_WITNESS: dict = {}
_UNWITNESSED = object()


# ---------------------------------------------------------------------------
# report + environment
# ---------------------------------------------------------------------------


def _disabled() -> bool:
    value = os.environ.get(_ENV_KILL)
    return bool(value) and value != "0"


def _version():
    try:
        mod = importlib.import_module("trame_vtk")
    except Exception:  # noqa: BLE001 - a report field, never a hard stop
        return None
    version = getattr(mod, "__version__", None)
    if version:
        return str(version)
    try:
        from importlib.metadata import version as _dist_version

        return _dist_version("trame-vtk")
    except Exception:  # noqa: BLE001 - ditto
        return None


def _probe_vtk_object(mods=None):
    """What a VTK array wrapper supports: ``weakref`` and ``hash``.

    Both are asked of a real instance of the array class the serializers import
    (``synchronization_context.vtkFloatArray``), so the answer describes the
    objects the caches will actually see.
    """
    cls = None
    if mods:
        cls = getattr(mods.get("sync"), "vtkFloatArray", None)
    if cls is None:
        try:
            from vtkmodules.vtkCommonCore import vtkFloatArray as cls  # noqa: N813
        except Exception:  # noqa: BLE001 - not fatal, the report says unknown
            return {"weakref": "unknown", "hashable": "unknown"}
    try:
        probe = cls()
    except Exception:  # noqa: BLE001
        return {"weakref": "unknown", "hashable": "unknown"}
    try:
        weakref.ref(probe)
        weakref_ok = "supported"
    except TypeError:
        weakref_ok = "unsupported"
    try:
        hash(probe)
        hashable = "hashable"
    except TypeError:
        hashable = "unhashable"
    return {"weakref": weakref_ok, "hashable": hashable}


def _report(status, patches=(), problems=(), reason=None, mods=None):
    return {
        "status": status,
        "installed": status in ("patched", "already_installed"),
        "reason": reason,
        "problems": list(problems),
        "patches": list(patches),
        "trame_vtk_version": _version(),
        "vtk_array_wrapper": _probe_vtk_object(mods),
        "caps": {
            "sha_cache": SHA_CACHE_MAX,
            "prop_cache": PROP_CACHE_MAX,
            "data_array_cache": DATA_ARRAY_CACHE_MAX,
            "data_table_cache": DATA_TABLE_CACHE_MAX,
            "delete_callbacks": DELETE_CALLBACKS_MAX,
        },
    }


def _line(report) -> str:
    """The ONE stderr line a successful install prints."""
    return (
        f"[poc_app] trame_vtk hardening: trame_vtk {report['trame_vtk_version']} "
        f"patched {', '.join(report['patches'])} "
        f"(caps sha={SHA_CACHE_MAX} prop={PROP_CACHE_MAX} "
        f"ctx={DATA_ARRAY_CACHE_MAX} table={DATA_TABLE_CACHE_MAX} "
        f"ids={DELETE_CALLBACKS_MAX})"
    )


# ---------------------------------------------------------------------------
# fail-safe verification
# ---------------------------------------------------------------------------


def _resolve(modules):
    """The four module objects to patch, plus whatever could not be resolved."""
    if modules is not None:
        return dict(modules), []
    resolved, problems = {}, []
    for key, name in _MODULES.items():
        try:
            resolved[key] = importlib.import_module(name)
        except Exception as exc:  # noqa: BLE001 - reported, never raised
            problems.append(f"{name}: {type(exc).__name__}: {exc}")
    return resolved, problems


def _params_ok(fn, expected):
    try:
        signature = inspect.signature(fn)
    except (TypeError, ValueError):
        return False
    names = [name for name in signature.parameters if name != "self"]
    return tuple(names[: len(expected)]) == tuple(expected)


def _verify(mods):
    """Everything ``_apply`` would wrap, checked against ``_SPEC``."""
    problems = []
    for key, mod in mods.items():
        if mod is None:
            problems.append(f"{key}: module not resolved")
            continue
        name = getattr(mod, "__name__", "")
        if not str(name).startswith("trame_vtk"):
            problems.append(f"{key}: {name!r} is not a trame_vtk module")

    for key, attr, kind, expected in _SPEC:
        mod = mods.get(key)
        if mod is None:
            continue  # already reported above
        where = f"{_MODULES[key]}.{attr}"
        obj = getattr(mod, attr, _MISSING)
        if obj is _MISSING:
            problems.append(f"{where}: missing")
            continue
        if kind == "callable":
            if not callable(obj):
                problems.append(f"{where}: not callable ({type(obj)!r})")
                continue
            origin = getattr(obj, "__module__", "") or ""
            if origin and not str(origin).startswith("trame_vtk"):
                problems.append(f"{where}: defined in {origin!r}, not trame_vtk")
                continue
            if not _params_ok(obj, expected):
                problems.append(
                    f"{where}: signature is not {tuple(expected)} ({inspect.signature(obj)})"
                )
        elif kind == "list":
            if not isinstance(obj, list):
                problems.append(f"{where}: not a list ({type(obj)!r})")
        elif kind == "dict":
            if not isinstance(obj, dict):
                problems.append(f"{where}: not a dict ({type(obj)!r})")
        elif kind == "class":
            if not isinstance(obj, type):
                problems.append(f"{where}: not a class ({type(obj)!r})")
                continue
            for member in _CTX_MEMBERS:
                if not hasattr(obj, member):
                    problems.append(f"{where}.{member}: missing")
            init_code = getattr(getattr(obj, "__init__", None), "__code__", None)
            init_names = init_code.co_names if init_code is not None else ()
            for member in _CTX_STATE:
                if not hasattr(obj, member) and member not in init_names:
                    problems.append(f"{where}.{member}: missing")

    # P4's replacement dispatches through these globals of ``serialize``.
    serialize_mod = mods.get("serialize")
    if serialize_mod is not None:
        for attribute in _SERIALIZE_GLOBALS:
            if not hasattr(serialize_mod, attribute):
                problems.append(f"{_MODULES['serialize']}.{attribute}: missing")
    return problems


# ---------------------------------------------------------------------------
# small shared helpers
# ---------------------------------------------------------------------------


def _trim(mapping, cap):
    """Drop the oldest ``len(mapping) - cap`` entries of an insertion-ordered dict."""
    excess = len(mapping) - int(cap)
    if excess <= 0:
        return 0
    for key in list(mapping)[:excess]:
        mapping.pop(key, None)
    return excess


def _forget_record(cache, key):
    """Weakref callback: the record goes when the object it describes goes."""

    def _forget(ref):
        record = cache.data.get(key)
        if record is not None and record["ref"] is ref:
            cache.data.pop(key, None)

    return _forget


def _safe_pop(mapping, key):
    """``mapping.pop(key, None)`` that cannot raise into a serializer."""
    try:
        mapping.pop(key, None)
    except Exception:  # noqa: BLE001 - a cache lookup must never break an export
        pass


def _instance_of(array, reference_id):
    try:
        return reference_id(array)
    except Exception:  # noqa: BLE001 - diagnostics only
        return None


def _shape_of(array):
    try:
        return (
            array.GetNumberOfValues(),
            array.GetNumberOfComponents(),
            array.GetDataType(),
        )
    except Exception:  # noqa: BLE001
        return None


# ---------------------------------------------------------------------------
# P1 -- DELETE_CALLBACKS / remove()
# ---------------------------------------------------------------------------


class _IdRegistry(list):
    """``serialize.DELETE_CALLBACKS``: still a list, O(1) ``in``, hard cap.

    ``serialize.serialize`` does ``if instance_id not in DELETE_CALLBACKS`` on
    every object it exports; against the stock list that is a linear scan, and it
    is the scan -- not the append -- that a per-tick page pays for.  The set
    behind this list answers it in constant time.  Membership is the only thing
    the cap can change: an evicted id only costs a duplicate ``DeleteEvent``
    observer if that same object is exported again, and ``remove()`` below is
    idempotent, so the duplicate is harmless.
    """

    __slots__ = ("_ids", "_max")

    def __init__(self, iterable=(), maxlen=DELETE_CALLBACKS_MAX):
        super().__init__(iterable)
        self._ids = set(iterable)
        self._max = int(maxlen)

    def __contains__(self, instance_id):
        return instance_id in self._ids

    def append(self, instance_id):
        if instance_id not in self._ids:
            list.append(self, instance_id)
            self._ids.add(instance_id)
            if len(self) > self._max:
                self._evict()

    def discard(self, instance_id):
        if instance_id in self._ids:
            self._ids.discard(instance_id)
            try:
                list.remove(self, instance_id)
            except ValueError:  # pragma: no cover - set and list cannot disagree
                pass

    # ``remove`` is what the stock code calls; discarding instead of raising is
    # the whole point of the patch.
    remove = discard

    def clear(self):
        list.clear(self)
        self._ids.clear()

    def _evict(self):
        excess = len(self) - self._max
        if excess <= 0:
            return
        for instance_id in self[:excess]:
            self._ids.discard(instance_id)
        del self[:excess]


# ---------------------------------------------------------------------------
# P4 -- the witness that replaces the DeleteEvent observer
# ---------------------------------------------------------------------------


def _witness(instance_id, instance) -> bool:
    """Record that ``instance`` owns ``instance_id``; True if the id is PROVABLY recycled.

    No callback is attached to the weakref on purpose: nothing of this module may
    run when an object is reclaimed (that re-entrancy is the crash P4 removes).
    A dead wrapper is not a death certificate either -- trame_vtk re-wraps the
    same C++ object on every export -- so only proof of recycling drops the
    record: a DIFFERENT live owner for one address, or a different class at it.
    """
    entry = _WITNESS.get(instance_id, _MISSING)
    recycled = False
    if entry is not _MISSING:
        ref, owner_type = entry
        if ref is not _UNWITNESSED:
            owner = ref()
            if owner is instance:
                return False  # the same live wrapper: nothing to record
            if owner is not None:
                recycled = True  # two live wrappers cannot own one address
        if not recycled and owner_type != type(instance).__name__:
            recycled = True
    try:
        record = (weakref.ref(instance), type(instance).__name__)
    except TypeError:  # pragma: no cover - VTK wrappers do support weakrefs
        record = (_UNWITNESSED, type(instance).__name__)
    _WITNESS[instance_id] = record
    _trim(_WITNESS, PROP_CACHE_MAX)
    return recycled


# ---------------------------------------------------------------------------
# P2 -- digest cache
# ---------------------------------------------------------------------------


class _DigestCache:
    """``helpers.data_array_sha_mapping``: bounded, identity-validated records.

    A record answers only for the object it was built from, so a hash can never
    be handed to a different array -- not even to one that a freed array's
    address was recycled into.  Entries disappear with their object (weakref
    callback) and the LRU cap bounds what a long-lived page accumulates.
    """

    def __init__(self, maxsize=SHA_CACHE_MAX):
        self.maxsize = int(maxsize)
        self.data = OrderedDict()
        self.hits = 0
        self.recomputed = 0
        self.dead_keys = 0

    # -- mapping surface, for callers of the module-global name -------------
    def __len__(self):
        return len(self.data)

    def __contains__(self, key):
        return key in self.data

    def __iter__(self):
        return iter(self.keys())

    def __getitem__(self, key):
        return self.data[key]

    def __setitem__(self, key, record):
        self.data[key] = record

    def __delitem__(self, key):
        del self.data[key]

    def get(self, key, default=None):
        return self.data.get(key, default)

    def pop(self, key, default=None):
        return self.data.pop(key, default)

    def keys(self):
        return [record["instance"] for record in self.data.values()]

    def values(self):
        return list(self.data.values())

    def items(self):
        return [(record["instance"], record) for record in self.data.values()]

    def clear(self):
        self.data.clear()

    # -- the cache itself ---------------------------------------------------
    def lookup(self, array, hash_data_array, reference_id):
        key = id(array)
        try:
            mtime = array.GetMTime()
        except Exception:  # noqa: BLE001 - not something we can key on
            return hash_data_array(array)

        record = self.data.get(key)
        if record is not None and record["mtime"] == mtime:
            ref = record["ref"]
            if ref is not None:
                if ref() is array:
                    self.hits += 1
                    self.data.move_to_end(key)
                    return record["sha"]
            elif record["fingerprint"] == (
                _instance_of(array, reference_id),
                mtime,
                _shape_of(array),
            ):
                # No weakref available for this object: the fingerprint is the
                # whole key, so a recorded shape/mtime/pointer triple may answer.
                self.hits += 1
                self.data.move_to_end(key)
                return record["sha"]

        sha = hash_data_array(array)
        self.recomputed += 1
        try:
            ref = weakref.ref(array, _forget_record(self, key))
        except TypeError:
            ref = None
        self.data[key] = {
            "sha": sha,
            "mtime": mtime,
            "ref": ref,
            "instance": _instance_of(array, reference_id),
            "fingerprint": (_instance_of(array, reference_id), mtime, _shape_of(array)),
        }
        self.data.move_to_end(key)
        while len(self.data) > self.maxsize:
            self.data.popitem(last=False)
            self.dead_keys += 1
        return sha


# ---------------------------------------------------------------------------
# P3 -- data_table_to_list memo
# ---------------------------------------------------------------------------


class _TableCache:
    """``helpers.data_table_to_list`` memo: (identity, mtime) -> tuple-of-tuples.

    The record holds a STRONG reference to the table on purpose: VTK hands out a
    fresh Python proxy for the same C++ object once the previous proxy is gone,
    so a weak record would miss on every export and buy nothing.  The LRU cap is
    therefore also the bound on what this cache keeps alive.
    """

    def __init__(self, maxsize=DATA_TABLE_CACHE_MAX):
        self.maxsize = int(maxsize)
        self.data = OrderedDict()
        self.hits = 0
        self.recomputed = 0

    def lookup(self, data_table, build):
        try:
            key = id(data_table)
            mtime = data_table.GetMTime()
        except Exception:  # noqa: BLE001 - not a table we can memoise
            value = build(data_table)
            return None if value is None else tuple(tuple(row) for row in value)

        record = self.data.get(key)
        if record is not None and record["mtime"] == mtime and record["table"] is data_table:
            self.hits += 1
            self.data.move_to_end(key)
            return record["value"]

        value = build(data_table)
        if value is not None:
            value = tuple(tuple(row) for row in value)
        self.recomputed += 1
        self.data[key] = {"table": data_table, "mtime": mtime, "value": value}
        self.data.move_to_end(key)
        while len(self.data) > self.maxsize:
            self.data.popitem(last=False)
        return value

    def clear(self):
        self.data.clear()


# ---------------------------------------------------------------------------
# patching
# ---------------------------------------------------------------------------


def _rebind(original, replacement):
    """Point every ``trame_vtk`` module attribute that holds ``original`` at the double.

    ``lookup_tables.py`` does ``from .helpers import data_table_to_list`` at import
    time, so patching ``helpers`` alone would leave the serializers calling the
    original.  This walks the already-imported trame_vtk modules and rewrites
    those bound names; every write is recorded for ``uninstall()``.
    """
    for name, module in list(sys.modules.items()):
        if not name.startswith("trame_vtk") or module is None:
            continue
        try:
            attributes = list(vars(module).items())
        except Exception:  # noqa: BLE001 - a module object we cannot read
            continue
        for attribute, value in attributes:
            if value is not original:
                continue
            try:
                setattr(module, attribute, replacement)
            except Exception:  # noqa: BLE001 - read-only module
                continue
            _RESTORE.append((module, attribute, original))


def _apply(mods):
    """Patch the four verified modules; returns the names that were applied."""
    global _DIGEST_CACHE, _TABLE_CACHE

    serialize_mod = mods["serialize"]
    cache_mod = mods["cache"]
    helpers_mod = mods["helpers"]
    sync_mod = mods["sync"]

    # -- P1: DELETE_CALLBACKS ------------------------------------------------
    original_registry = serialize_mod.DELETE_CALLBACKS
    registry = _IdRegistry(original_registry, DELETE_CALLBACKS_MAX)
    serialize_mod.DELETE_CALLBACKS = registry
    _RESTORE.append((serialize_mod, "DELETE_CALLBACKS", original_registry))

    # -- P1: remove() --------------------------------------------------------
    original_remove = serialize_mod.remove
    remove_from_cache = serialize_mod.remove_from_cache

    def remove(instance_id):
        """Total ``serialize.remove``: clears the property cache, forgets the id."""
        try:
            remove_from_cache(instance_id)
        except Exception:  # noqa: BLE001 - a delete observer must never raise
            pass
        try:
            registry.discard(instance_id)
        except Exception:  # noqa: BLE001 - ditto
            pass

    remove.__doc__ = original_remove.__doc__
    serialize_mod.remove = remove
    _RESTORE.append((serialize_mod, "remove", original_remove))

    # -- P4: serialize() without the DeleteEvent observer ---------------------
    original_serialize = serialize_mod.serialize
    _WITNESS.clear()

    def serialize(parent, instance, instance_id, context, depth):
        """``serialize.serialize`` minus the per-object ``DeleteEvent`` observer.

        Stock ``serialize`` attaches ``lambda: remove(instance_id)`` as a Python
        ``DeleteEvent`` observer to every object it exports, which fires from a
        VTK destructor during garbage collection.  That attachment is the crash;
        cache invalidation is carried by the bounded/identity-validated caches
        and by the witness recorded here instead (see the module docstring).
        """
        if _witness(instance_id, instance):
            _safe_pop(cache_mod.PROP_CACHE, instance_id)
        instance_type = serialize_mod.class_name(instance)
        serializer = serialize_mod.SERIALIZERS.get(instance_type, None)
        if serializer:
            return serializer(parent, instance, instance_id, context, depth)
        if instance_type not in serialize_mod.NO_SERIALIZER_FOR_INSTANCE:
            serialize_mod.logger.warning(
                "!!!No serializer for %s with id %s", instance_type, instance_id
            )
            serialize_mod.NO_SERIALIZER_FOR_INSTANCE[instance_type] = instance_id
        return None

    serialize.__doc__ = original_serialize.__doc__
    serialize_mod.serialize = serialize
    _RESTORE.append((serialize_mod, "serialize", original_serialize))
    _rebind(original_serialize, serialize)

    # -- P2: digest ----------------------------------------------------------
    _DIGEST_CACHE = _DigestCache(SHA_CACHE_MAX)
    original_digest = helpers_mod.digest
    original_mapping = helpers_mod.data_array_sha_mapping

    def digest(array):
        """``helpers.digest`` backed by the bounded, identity-validated cache."""
        return _DIGEST_CACHE.lookup(
            array, helpers_mod.hash_data_array, helpers_mod.reference_id
        )

    digest.__doc__ = original_digest.__doc__
    helpers_mod.digest = digest
    _RESTORE.append((helpers_mod, "digest", original_digest))
    helpers_mod.data_array_sha_mapping = _DIGEST_CACHE
    _RESTORE.append((helpers_mod, "data_array_sha_mapping", original_mapping))
    _rebind(original_digest, digest)

    # -- P3: data_table_to_list ---------------------------------------------
    _TABLE_CACHE = _TableCache(DATA_TABLE_CACHE_MAX)
    original_table_to_list = helpers_mod.data_table_to_list

    def data_table_to_list(data_table):
        """``helpers.data_table_to_list`` memoised on (identity, mtime)."""
        return _TABLE_CACHE.lookup(data_table, original_table_to_list)

    data_table_to_list.__doc__ = original_table_to_list.__doc__
    helpers_mod.data_table_to_list = data_table_to_list
    _RESTORE.append((helpers_mod, "data_table_to_list", original_table_to_list))
    _rebind(original_table_to_list, data_table_to_list)

    # -- P2: PROP_CACHE (cap) ------------------------------------------------
    original_cache_properties = cache_mod.cache_properties

    def cache_properties(obj_id, ctx, props):
        """``cache.cache_properties`` with ``PROP_CACHE`` capped."""
        delta = original_cache_properties(obj_id, ctx, props)
        _trim(cache_mod.PROP_CACHE, PROP_CACHE_MAX)
        return delta

    cache_properties.__doc__ = original_cache_properties.__doc__
    cache_mod.cache_properties = cache_properties
    _RESTORE.append((cache_mod, "cache_properties", original_cache_properties))
    _rebind(original_cache_properties, cache_properties)

    # -- P2: ctx.data_array_cache -------------------------------------------
    original_cache_data_array = sync_mod.SynchronizationContext.cache_data_array

    def cache_data_array(self, p_md5, data):
        """``SynchronizationContext.cache_data_array`` with an LRU re-touch and cap.

        Re-touching matters: every array in the scene is cached again on every
        export, so the least-recently-used end of this dict is exactly the set of
        arrays the page has stopped drawing -- the only ones a cap may drop.
        """
        cache = self.data_array_cache
        if p_md5 in cache:
            del cache[p_md5]
        cache[p_md5] = data
        _trim(cache, DATA_ARRAY_CACHE_MAX)

    cache_data_array.__doc__ = original_cache_data_array.__doc__
    sync_mod.SynchronizationContext.cache_data_array = cache_data_array
    _RESTORE.append(
        (sync_mod.SynchronizationContext, "cache_data_array", original_cache_data_array)
    )

    return list(_PATCHES)


def install(modules=None):
    """Install the hardening patches. Returns the report; never raises.

    ``modules`` is the verification/introspection hook: pass a mapping with the
    four keys ``serialize``, ``cache``, ``helpers``, ``sync`` to point the same
    checks at stand-in module objects (a report-only run: it does not touch the
    process state, does not count as installed and prints nothing).
    """
    try:
        return _install(modules)
    except Exception as exc:  # noqa: BLE001 - a boot must not be taken down by this
        return _report("not_patched", reason=f"{type(exc).__name__}: {exc}")


def _install(modules):
    if _disabled():
        return _report(
            "disabled", reason=f"{_ENV_KILL}={os.environ.get(_ENV_KILL)!r}"
        )
    if modules is None and _STATE["installed"]:
        return dict(_STATE["report"], status="already_installed")

    resolved, problems = _resolve(modules)
    if not problems:
        problems = _verify(resolved)
    if problems:
        return _report(
            "not_patched",
            problems=problems,
            reason="; ".join(problems[:3]),
            mods=resolved,
        )

    report = _report("patched", patches=_apply(resolved), mods=resolved)
    if modules is None:
        _STATE["installed"] = True
        _STATE["report"] = report
        print(_line(report), file=sys.stderr)
    return report


def uninstall():
    """Put back every attribute ``install()`` replaced. Safe to call twice."""
    was_installed = bool(_STATE["installed"])
    while _RESTORE:
        module, attribute, original = _RESTORE.pop()
        try:
            setattr(module, attribute, original)
        except Exception:  # noqa: BLE001
            pass
    for cache in (_DIGEST_CACHE, _TABLE_CACHE):
        if cache is not None:
            cache.clear()
    _WITNESS.clear()
    _STATE["installed"] = False
    _STATE["report"] = None
    return {"status": "uninstalled", "was_installed": was_installed}
