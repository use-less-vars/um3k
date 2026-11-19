"""``RunConfig`` -- the declarative form of one reference-simulation run.

WHAT THIS IS.  ``scripts/run_reference_sim.py`` drives
``evidence/termination/run_build_A.py`` (arm A: the microstrip terminated in a
50 ohm ``series_r`` load) with a 3-D ``|E|`` volume dump.  Every number that run
prices -- the step count, the plane dump stride, the volume cadence, the mesh's
line length, the two x-cut positions, the pulse centre, the load resistance, the
wall ceiling and the two output paths -- is a flag on that script, and a flag is
a thing you have to retype (and can mistype in the one direction that costs
1400 s: the volume budget REFUSES rather than thins).  This dataclass is those
numbers in one JSON document, so a run can be handed to somebody else, diffed
against another run, or committed next to the artefact it produced.

WHY THE FIELD NAMES ARE THE REFERENCE'S NAMES.  A configuration file is a second
place for a name to live, and the only thing that keeps it honest is that the
name it carries is the name the code already uses: ``nsteps``, ``dump_stride``,
``volume_stride``, ``volume_frames``, ``pulse_freq_ghz``, ``n_line``,
``xcut_near_mm``, ``xcut_far_mm``, ``wall_limit_s``, ``load_ohm`` -- each is the
validator's own flag spelling in ``run_build_A.py``, so ``grep xcut_near_mm``
finds the flag, the plan line and this field and they cannot drift apart
silently.  Two of the names asked for when this was specified do NOT exist
anywhere in the FDTD path and are deliberately absent rather than invented here:

* there is no ``modes_to_calculate`` / ``n_modes``: the reference is a
  time-domain march, it computes no modes.  (``nmodes`` exists only in the
  unrelated cavity ``_run_modes`` study, ``emfit/studies.py:5889``.)
* there is no ``geometry`` object either: the mesh is ``vis_geometry``'s seven
  integers plus ``h``, derived inside ``build_kwargs``.  Of those, exactly ONE is
  reachable from the command line (``--n-line``, which sets
  ``nx = n_pml + n_ref + n_line`` and therefore moves the cell count and the
  volume price), so that is the one this file carries -- as ``n_line``, not as a
  nested object pretending to own the other six.

WHAT VALIDATION IS FOR.  ``to_dict``/``from_dict`` are a round trip, so the
cheap failure mode is a document that parses and then means something else: a
stray key that nobody reads (a typo like ``nstep`` is silently the default), a
JSON number where an int is required (``2400.0`` divides fine and prints as
``2400``), a stride of ``0`` (selects no step at all), a negative x-cut, or a
schema version from a newer file.  Every one of those is refused by
:meth:`RunConfig.validate` with the offending value and field named, so the
refusal arrives where the file is read and not after the solve.

The module is pure stdlib (``json``/``dataclasses``/``math``): importing it must
never pull in numpy or the compiled kernel, because it is read by a script whose
whole point is to answer "what would this run cost" before anything heavy is
imported.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from dataclasses import asdict, dataclass, fields, replace
from pathlib import Path
from typing import Any

__all__ = [
    "SCHEMA_VERSION",
    "RunConfig",
    "DEFAULT_NSTEPS",
    "DEFAULT_DUMP_STRIDE",
    "DEFAULT_VOLUME_STRIDE",
    "DEFAULT_N_LINE",
    "DEFAULT_XCUT_NEAR_MM",
    "DEFAULT_XCUT_FAR_MM",
    "DEFAULT_WALL_LIMIT_S",
    "DEFAULT_LOAD_OHM",
]

#: Bumped when a field is removed or its meaning changes; a document that names a
#: version this module does not implement is REFUSED rather than guessed at.
SCHEMA_VERSION = 1

# The defaults are the reference simulation's own (run_build_A.py: 2400 steps,
# dump stride 1) and this script's documented ones (volume stride 100).  They are
# repeated here rather than imported because a config file that only means
# something when ``evidence/`` is importable is not a config file.
DEFAULT_NSTEPS = 2400
DEFAULT_DUMP_STRIDE = 1
DEFAULT_VOLUME_STRIDE = 100
DEFAULT_N_LINE = 54          # -> nx = n_pml 6 + n_ref 2 + 54 = 62 columns
DEFAULT_XCUT_NEAR_MM = 20.4  # run_build_A.py --xcut-near-mm
DEFAULT_XCUT_FAR_MM = 22.0   # run_build_A.py --xcut-far-mm

#: The wall ceiling ``--wall-limit-s`` falls back to (``run_build_A.py:128``
#: ``WALL_LIMIT_S_DEFAULT``), and the number the reference TRIPS on rather than
#: spends (:427-430 -> exit 4).  A literal for the reason above: a config file
#: that only means something when ``evidence/`` is importable is not a config
#: file.
DEFAULT_WALL_LIMIT_S = 1400.0

#: What ``--load-ohm`` falls back to: ``None``, i.e. "the ARM's own resistance"
#: (``run_build_A.py:3593-3594`` resolves an absent flag from
#: ``STRUCTURES[structure]["load_ohm"]`` -- 50 ohm for A at :692 through the
#: ``LOAD_VALUE_OHM`` constant (:137), 100 ohm for B's literal at :703).  Not
#: 50.0: a document that named 50 would silently re-terminate a 100 ohm arm,
#: which is the trap the WARNING at :3585-3588 names (:3589-3592 is only the
#: comment explaining why an explicit flag wins).
DEFAULT_LOAD_OHM = None


def _is_int(value: Any) -> bool:
    """True for a real int.  ``bool`` is an int subclass and is NOT one here."""
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value: Any) -> bool:
    """True for a finite int/float (again excluding ``bool``)."""
    return (_is_int(value) or isinstance(value, float)) and math.isfinite(value)


@dataclass(frozen=True)
class RunConfig:
    """One reference-simulation run: the flags, in JSON-native types.

    Frozen: a run's configuration is a record of what was asked for, so a
    mutation after construction is a bug and not a feature (use
    :func:`dataclasses.replace` for a variant).  Every field is a JSON scalar
    (``int``/``float``/``str``/``None``) so ``to_json`` and ``from_json`` are a
    true round trip with no custom encoder.

    Paths (:attr:`npz`, :attr:`out`) default to ``None`` meaning "the script's
    own default".  A relative path in a config file would otherwise be read
    against whatever directory the run was typed from, which is exactly the
    ambiguity that makes a stored run unreproducible.
    """

    #: Version of this document's schema (see :data:`SCHEMA_VERSION`).
    schema_version: int = SCHEMA_VERSION

    #: FDTD steps.  Moves the frame count, and so the volume's price.
    nsteps: int = DEFAULT_NSTEPS

    #: Keep every Nth solver step's planes.  A FLOOR, not a guarantee:
    #: ``_vis_plan_stride`` raises it when the 45 MB plane budget demands.
    dump_stride: int = DEFAULT_DUMP_STRIDE

    #: Keep every Nth y-cut FRAME's ``|E|`` volume (frames, not solver steps).
    volume_stride: int = DEFAULT_VOLUME_STRIDE

    #: Cap the volume at N frames; ``None`` is no cap (a shorter tail, not a
    #: thinner march -- ``volume_stride`` is the budget lever).
    volume_frames: int | None = None

    #: Ricker pulse centre [GHz]; ``None`` is the reference's ``VIS_F_PULSE_HZ``
    #: (15 GHz).  There is no CW ``f_target`` knob for a pulse dump.
    pulse_freq_ghz: float | None = None

    #: Line cells between the reference plane and the top of the grid
    #: (``nx = n_pml + n_ref + n_line``).  The one mesh integer a flag reaches.
    n_line: int = DEFAULT_N_LINE

    #: x position of the near x-cut frame [mm] (on the line, before the load).
    xcut_near_mm: float = DEFAULT_XCUT_NEAR_MM

    #: x position of the far x-cut frame [mm] (past the load).
    xcut_far_mm: float = DEFAULT_XCUT_FAR_MM

    #: Hard wall ceiling [s]; ``None`` is the reference's own 1400 s.  The trip
    #: thread exits 4 past it, so this is the run's worst case, not its cost.
    wall_limit_s: float | None = DEFAULT_WALL_LIMIT_S

    #: ``series_r`` load resistance [ohm]; ``None`` is the ARM's own value (A
    #: 50 ohm, B 100 ohm), and a number here is the same explicit override the
    #: flag is.  ``scripts/run_reference_sim.py``'s CONFIG_DRIVEN table (:209-220)
    #: does not forward this field yet; ``server/poc_app.py`` does.
    load_ohm: float | None = DEFAULT_LOAD_OHM

    #: Where the field dump goes; ``None`` is the script's ``artifacts/`` default.
    npz: str | None = None

    #: Where the run's JSON artefact goes; ``None`` is the script's default.
    out: str | None = None

    def __post_init__(self) -> None:
        self.validate()

    # ------------------------------------------------------------------ #
    # validation
    # ------------------------------------------------------------------ #
    def validate(self) -> "RunConfig":
        """Refuse a document that would mean something other than it says.

        Returns ``self`` so a caller can write ``RunConfig(**doc).validate()``
        (``__post_init__`` already calls it; the second call is idempotent).
        """
        if not _is_int(self.schema_version):
            raise TypeError(
                f"schema_version must be an int, not {self.schema_version!r} "
                f"({type(self.schema_version).__name__})")
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(
                f"schema_version {self.schema_version} is not the version this "
                f"module implements ({SCHEMA_VERSION}); refusing to guess at a "
                "document whose field meanings may have changed")

        for name in ("nsteps", "dump_stride", "volume_stride", "n_line"):
            value = getattr(self, name)
            if not _is_int(value):
                raise TypeError(
                    f"{name} must be an int, not {value!r} "
                    f"({type(value).__name__}); a JSON 2400.0 is not 2400")
            if value < 1:
                raise ValueError(f"{name} must be at least 1, not {value}")

        if self.volume_frames is not None:
            if not _is_int(self.volume_frames):
                raise TypeError(
                    f"volume_frames must be an int or null, not "
                    f"{self.volume_frames!r} ({type(self.volume_frames).__name__})")
            if self.volume_frames < 1:
                raise ValueError(
                    f"volume_frames must be at least 1 or null, not "
                    f"{self.volume_frames}: a dump with no frames is not a "
                    "smaller dump, it is a file claiming a volume it lacks")

        if self.pulse_freq_ghz is not None:
            if not _is_number(self.pulse_freq_ghz):
                raise TypeError(
                    f"pulse_freq_ghz must be a finite number or null, not "
                    f"{self.pulse_freq_ghz!r} ({type(self.pulse_freq_ghz).__name__})")
            if self.pulse_freq_ghz <= 0.0:
                raise ValueError(
                    f"pulse_freq_ghz must be positive, not {self.pulse_freq_ghz}")

        for name in ("xcut_near_mm", "xcut_far_mm"):
            value = getattr(self, name)
            if not _is_number(value):
                raise TypeError(
                    f"{name} must be a finite number, not {value!r} "
                    f"({type(value).__name__})")
            if value <= 0.0:
                raise ValueError(
                    f"{name} must be positive (it is an x position on the "
                    f"mesh, measured from the reference plane), not {value}")
        if self.xcut_near_mm >= self.xcut_far_mm:
            raise ValueError(
                f"xcut_near_mm {self.xcut_near_mm} must be less than "
                f"xcut_far_mm {self.xcut_far_mm}: 'near' is the frame before "
                "the load and 'far' the one past it, and a swapped pair silently "
                "labels the two pictures the wrong way round")

        # The run's two runtime guards.  Both are plain ``type=float`` flags on
        # the reference's parser (run_build_A.py:3380 ``--wall-limit-s``, :3344
        # ``--load-ohm``) with NO range check of their own, so nothing here
        # refuses a value the command line accepts: a form or a file that were
        # the stricter of the two would be the drift this module exists to stop.
        # Non-finite is the one refusal, and it is about THIS document rather
        # than about the physics: ``NaN``/``Infinity`` are tokens no strict JSON
        # reader takes back, and a lossless round trip is the file's promise.
        for name in ("wall_limit_s", "load_ohm"):
            value = getattr(self, name)
            if value is None:
                continue
            if not _is_number(value):
                raise TypeError(
                    f"{name} must be a finite number or null, not {value!r} "
                    f"({type(value).__name__})")

        for name in ("npz", "out"):
            value = getattr(self, name)
            if value is None:
                continue
            if not isinstance(value, str):
                raise TypeError(
                    f"{name} must be a str or null, not {value!r} "
                    f"({type(value).__name__})")
            if not value.strip():
                raise ValueError(f"{name} must be a non-empty path or null")
        return self

    # ------------------------------------------------------------------ #
    # JSON round trip
    # ------------------------------------------------------------------ #
    def to_dict(self) -> dict[str, Any]:
        """The document, exactly as it is written to / read from JSON."""
        return asdict(self)

    @classmethod
    def from_dict(cls, doc: Mapping[str, Any]) -> "RunConfig":
        """Build from a parsed document, refusing unknown keys.

        An unknown key is the quiet failure this exists to stop: a typo
        (``nstep``) or a field from a newer schema would otherwise be dropped on
        the floor and the run would price the DEFAULT, which looks like success.
        A missing key is not an error -- absent means "the default".
        """
        if not isinstance(doc, Mapping):
            raise TypeError(
                f"a RunConfig document must be a JSON object, not "
                f"{type(doc).__name__}")
        known = [f.name for f in fields(cls)]
        unknown = sorted(set(doc) - set(known))
        if unknown:
            raise ValueError(
                f"unknown key(s) in the RunConfig document: {unknown}; the "
                f"known keys are {known}. Refused rather than ignored: a "
                "misspelled field would silently fall back to its default")
        return cls(**{str(k): v for k, v in doc.items()})

    def to_json(self, *, indent: int = 2) -> str:
        """The document as JSON text (sorted keys, trailing newline: diffable)."""
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True) + "\n"

    @classmethod
    def from_json(cls, text: str) -> "RunConfig":
        """Parse JSON text into a validated configuration."""
        try:
            doc = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"not JSON: {exc}") from None
        return cls.from_dict(doc)

    @classmethod
    def from_json_file(cls, path: str | Path) -> "RunConfig":
        """Read and validate a config file (``OSError`` if it cannot be read)."""
        target = Path(path)
        return cls.from_json(target.read_text(encoding="utf-8"))

    # ------------------------------------------------------------------ #
    # variants
    # ------------------------------------------------------------------ #
    def replace(self, **changes: Any) -> "RunConfig":
        """A validated variant of this configuration."""
        return replace(self, **changes)
