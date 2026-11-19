"""Pins the pre-flight MEMORY refusal in ``evidence/termination/run_build_A.py``.

``_memory_preflight`` (:1097-1160) is the one check in this driver that can
refuse a run before it spends a timestep: ``main`` has already built ``kwargs``
(``build_kwargs``, :2094-2117) when it calls the pre-flight (:3737-3739) and
returns for ``--dry-run`` only AFTERWARDS (:3741), so a dry run proves the
refusal without an FDTD step and ``main(["--dry-run"])`` is a cheap probe of the
PASSING path.  REFUSALS ARE TESTED BY CALLING ``_memory_preflight`` DIRECTLY
WITH A SYNTHETIC ``meta``, because the effective limit is
``min(MEM_SAFE_LIMIT_MB, meta["cgroup_limit_mb"])`` (:1147-1150), this
development box's cgroup is 512 MB and a CI host's is larger, so no single
``main`` invocation could provoke a refusal on both.

Where the numbers come from.  The estimator is ``_solve_estimate_mb``
(:1057-1094): it counts EDGES and FACES -- ``nx*nyn*nzn + ...``, :1081-1088,
the counts of ``emfit/operators.py:54-64`` -- and not cells, prices them with
the named constants (:584-617: ``MEM_SAFE_LIMIT_MB`` 12000.0,
``MEM_PROCESS_OVERHEAD_MB`` 150.0, ``MEM_BYTES_PER_FLOAT64`` 8,
``MEM_EDGE_ARRAYS`` 10, ``MEM_FACE_ARRAYS`` 5, ``MEM_EDGE_MASKS`` 3,
``MEM_SPARSE_ENTRIES_PER_FACE`` 4, ``MEM_SPARSE_BYTES_PER_ENTRY`` 12) and adds
the overhead residual.  The ONE measurement this file owns is Run A's 297.82 MB
peak RSS on the 62 x 206 x 22 = 280,984-cell mesh (:2064-2066,
``build_A_50ohm.json``); the estimator returns 298.910534 MB there, 0.37 % high,
and its docstring is explicit that it is deliberately NOT tuned until it equals
the measurement (:1073-1074) -- a fit is not an estimate.

The mesh every behavioural test but the anchor runs on is the DEFAULT one:
``build_kwargs`` carries ``"n_clean": 96`` (:2099) and ``nsteps`` 2400
(:2102-2105), every other mesh key matching the ``emfit.studies`` default, so
``vis_geometry`` (:1029-1054) returns 62 x 212 x 22 = 289,168 cells.  That is
the CORRECTED grid, 212 wide rather than the recorded run's 206 (:2079-2082),
and no run of this script has been recorded on it.

The arguments namespace is hand-built: the ``ArgumentParser`` is created inside
``main`` (:3308) and there is no module-level builder, so the five attributes
the pre-flight reads for its (zero) dump terms (:1128-1138) are restated here.

This file is a CHARACTERISATION test: it pins the behaviour AS IT IS.  Whoever
moves a constant, the default mesh or the sentence is expected to update these
assertions in the same commit.
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

import pytest

#: The second line of every refusal, byte for byte (:1155-1159).
HOST_SENTENCE = ("Error: Estimated memory exceeds safe limits. "
                 "Reduce mesh density, volume_stride, or n_line.")

#: The default Run A mesh's ``build_kwargs`` mesh keys.  ``n_clean`` 96 is the
#: only one whose value differs from the ``emfit.studies`` default (12), and
#: ``nsteps`` is not a mesh key but the frame-count input the pre-flight reads.
DEFAULT_MESH_KWARGS = {"n_clean": 96, "nsteps": 2400}


def _load_run_build_a():
    """Import ``evidence/termination/run_build_A.py`` as a module."""
    evidence = Path(__file__).resolve().parents[1] / "evidence" / "termination"
    if str(evidence) not in sys.path:
        sys.path.insert(0, str(evidence))
    import run_build_A

    return run_build_A


def _dump_free_args() -> argparse.Namespace:
    """The five attributes the pre-flight reads for its dump terms (:1128-1138).

    A default Run A call asks for no dump, so ``vis_dump`` is ``None`` and every
    dump term is ZERO (:1115-1119): the recorder allocates nothing.
    """
    return argparse.Namespace(
        vis_dump=None,
        dump_stride=1,
        no_volume=False,
        volume_stride=None,
        volume_frames=None,
    )


def _source_ast(run_build_A) -> ast.Module:
    """Parse the driver's own source for the two ordering/shape pins."""
    return ast.parse(Path(run_build_A.__file__).read_text(encoding="utf-8"))


def _function(tree: ast.Module, name: str) -> ast.FunctionDef:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"no ``def {name}`` in run_build_A.py")


def test_estimator_is_anchored_on_the_measured_peak_rss():
    """The estimate sits just above Run A's measured 297.82 MB, not on it.

    The estimate is built from dtypes and entity counts, and the only figure it
    can be checked against is the recorded peak RSS of the banked 62 x 206 x 22
    mesh (:2064-2066).  Being 0.37 % HIGH is the anchor; being equal would mean
    the constants had been fitted to the measurement, which the docstring
    refuses (:1073-1074).
    """
    run_build_A = _load_run_build_a()
    nx, ny, nz = 62, 206, 22
    assert nx * ny * nz == 280_984

    est_mb = run_build_A._solve_estimate_mb(nx, ny, nz)
    assert est_mb == pytest.approx(298.910534, abs=1e-6)
    assert est_mb == pytest.approx(297.82, rel=0.01)
    assert est_mb - 297.82 > 0.5, "fitted to the measurement, not an estimate"

    # The difference IS the named residual, and that is how its number was
    # obtained: the count prices this mesh at ~149 MB (:1069-1073).
    assert run_build_A.MEM_PROCESS_OVERHEAD_MB == 150.0
    assert est_mb - run_build_A.MEM_PROCESS_OVERHEAD_MB == pytest.approx(149.0,
                                                                        abs=0.5)


def test_refusal_is_rc_2_and_the_byte_exact_two_lines(capsys):
    """A refused run exits 2 and writes ONE write: the count, then the sentence.

    ``meta`` is synthetic on purpose (see the module docstring): a cgroup of
    100 MB is below the default mesh's estimate, so the refusal fires without
    depending on what this machine's cgroup happens to be.
    """
    run_build_A = _load_run_build_a()

    rc = run_build_A._memory_preflight(dict(DEFAULT_MESH_KWARGS),
                                       _dump_free_args(),
                                       {"cgroup_limit_mb": 100.0})
    assert rc == 2

    err = capsys.readouterr().err
    assert err == (
        "MEM: estimated footprint ~303.2 MB for 62x212x22 "
        "(289168 cells, 0 volume frames) exceeds the safe limit 100.0 MB\n"
        + HOST_SENTENCE + "\n"
    )
    assert err.splitlines() == [
        "MEM: estimated footprint ~303.2 MB for 62x212x22 "
        "(289168 cells, 0 volume frames) exceeds the safe limit 100.0 MB",
        HOST_SENTENCE,
    ]


def test_limit_is_the_min_of_the_owner_ceiling_and_the_cgroup(monkeypatch,
                                                              capsys):
    """``min(12000, cgroup)``: the container can only TIGHTEN the ceiling.

    Three facts, in the order the code applies them (:1147-1150): a cgroup below
    the estimate refuses and names the cgroup number; a ``meta`` with no cgroup
    key at all leaves the owner's 12000 MB ceiling in force; and a cgroup ABOVE
    12000 cannot loosen it -- an estimate over 12000 MB is still refused at
    12000.0, which is the "unasked-for licence" the comment rejects (:1144-1146).
    """
    run_build_A = _load_run_build_a()
    args = _dump_free_args()
    assert run_build_A.MEM_SAFE_LIMIT_MB == 12000.0

    assert run_build_A._memory_preflight(dict(DEFAULT_MESH_KWARGS), args,
                                         {"cgroup_limit_mb": 100.0}) == 2
    assert "safe limit 100.0 MB" in capsys.readouterr().err

    assert run_build_A._memory_preflight(dict(DEFAULT_MESH_KWARGS), args,
                                         {}) == 0
    assert capsys.readouterr().err == ""

    # An estimate above the owner's ceiling, so the min() has something to do:
    # the real arithmetic is pinned by the other tests, only its INPUT is faked.
    monkeypatch.setattr(run_build_A, "_solve_estimate_mb",
                        lambda nx, ny, nz: 20000.0)
    for cgroup_mb in (1e9, 20000.0):
        assert run_build_A._memory_preflight(
            dict(DEFAULT_MESH_KWARGS), args,
            {"cgroup_limit_mb": cgroup_mb}) == 2
        err = capsys.readouterr().err
        assert "safe limit 12000.0 MB" in err
        assert f"safe limit {cgroup_mb:.1f}" not in err


def test_a_dry_run_passes_the_preflight_silently(capsys):
    """The PASSING path through ``main``: exit 0 and not one byte on stderr.

    Silent on purpose (:1100-1103): existing runs' stderr is compared by tests,
    and a pre-flight that passes has nothing to say.  ``--dry-run`` is the only
    ``main`` path that reaches the pre-flight without an FDTD step.
    """
    run_build_A = _load_run_build_a()

    assert run_build_A.main(["--dry-run"]) == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    assert captured.out.strip() != "", "the dry-run JSON did not reach stdout"


def test_the_preflight_call_sits_above_the_dry_run_return():
    """Ordering in ``main``: the refusal is decided BEFORE ``--dry-run`` exits.

    A dry run that could not refuse would be a dry run of the wrong thing
    (:3730-3736), so the call (:3737) must precede the ``if args.dry_run:``
    return (:3741) -- and there must be exactly one of each in ``main``.
    """
    tree = _source_ast(_load_run_build_a())
    main_fn = _function(tree, "main")

    calls = [node.lineno for node in ast.walk(main_fn)
             if isinstance(node, ast.Call)
             and isinstance(node.func, ast.Name)
             and node.func.id == "_memory_preflight"]
    assert len(calls) == 1

    dry_run_returns = [node.lineno for node in ast.walk(main_fn)
                       if isinstance(node, ast.If)
                       and isinstance(node.test, ast.Attribute)
                       and node.test.attr == "dry_run"]
    assert len(dry_run_returns) == 1
    assert calls[0] < dry_run_returns[0]


def test_the_refusal_is_one_write_whose_last_piece_is_the_sentence():
    """Two lines, ONE ``sys.stderr.write``; no ``print``, no logging in it.

    The pre-flight is called on every run, so a second write would double every
    refusal's output, and a ``print`` or a log line would put output on stderr
    that the pass path promises is empty.  The sentence is the LAST piece of one
    joined f-string (:1155-1159), closed by the newline that ends the second
    line.
    """
    tree = _source_ast(_load_run_build_a())
    fn = _function(tree, "_memory_preflight")

    writes = [node for node in ast.walk(fn)
              if isinstance(node, ast.Call)
              and isinstance(node.func, ast.Attribute)
              and node.func.attr == "write"
              and isinstance(node.func.value, ast.Attribute)
              and node.func.value.attr == "stderr"
              and isinstance(node.func.value.value, ast.Name)
              and node.func.value.value.id == "sys"]
    assert len(writes) == 1
    assert not [node for node in ast.walk(fn)
                if isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in ("info", "warning", "error")]
    assert not [node for node in ast.walk(fn)
                if isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "print"]
    assert "logging" not in ast.unparse(fn)

    (payload,) = writes[0].args
    assert isinstance(payload, ast.JoinedStr)
    assert isinstance(payload.values[-1], ast.Constant)
    # CPython merges the adjacent literals, so the last piece carries the count
    # line's own closing " MB\n" too -- and that is the point: TWO newlines in
    # ONE constant, i.e. two lines out of ONE write.
    assert payload.values[-1].value.endswith(HOST_SENTENCE + "\n")
    assert payload.values[-1].value.count("\n") == 2
    # Seven interpolations (est_mb, nx, ny, nz, cells, n_vol, limit_mb) in ONE
    # f-string group, which is why the two lines cost one write.
    assert sum(isinstance(part, ast.FormattedValue)
               for part in payload.values) == 7


def test_estimator_prices_edges_and_faces_not_cells():
    """Equal cell counts at different shapes MUST price differently.

    The counts are ``nx*nyn*nzn + ...`` (:1081-1088), so two 120-cell meshes are
    different sums; a per-cell model would return the same number for both.  The
    consequence a per-cell model also cannot produce: the price PER CELL falls as
    the mesh grows, because the node offset ``nx+1`` stops mattering.
    """
    run_build_A = _load_run_build_a()
    assert 4 * 5 * 6 == 3 * 8 * 5 == 120

    a_mb = run_build_A._solve_estimate_mb(4, 5, 6)
    b_mb = run_build_A._solve_estimate_mb(3, 8, 5)
    assert abs(a_mb - b_mb) > 1e-4, (
        "same price for the same CELL count: a per-cell model, which the "
        "docstring says is the whole reason this estimate exists"
    )
    assert min(a_mb, b_mb) > run_build_A.MEM_PROCESS_OVERHEAD_MB

    small = ((run_build_A._solve_estimate_mb(20, 20, 20)
              - run_build_A.MEM_PROCESS_OVERHEAD_MB) / 20 ** 3)
    large = ((run_build_A._solve_estimate_mb(200, 200, 200)
              - run_build_A.MEM_PROCESS_OVERHEAD_MB) / 200 ** 3)
    assert large < small
    assert small / large > 1.05
