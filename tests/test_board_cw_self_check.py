"""The cw script's self-check: silent on a healthy run, loud on a defect.

``tools/host/m3a-smoke/board_run_cw_poynting.py`` ends every run with a block
that compares five quantities as the tone path measured them against the same
quantities re-derived by emfit's bin reader off the rebuilt phasor vector.  The
claims pinned here:

  * a healthy run prints no ``MISMATCH`` at all, and its verdict reads ``OK``;
  * the |gamma| row -- the one that used to fire on every healthy run, because
    it was judged at a *relative* 1e-3 while the difference it measures is
    1.2e-2 relative -- is silent at exactly that difference when judged with
    the shipped absolute tolerance;
  * the same row still bites when |gamma| moves at order |gamma| itself, so the
    quiet is a tolerance that fits the noise and not a check switched off;
  * the four rows a healthy run agrees on keep their relative 1e-6 tolerance;
  * each printed row says which measure judged it, so a reader can tell a real
    mismatch from an unreachable tolerance;
  * a NaN never passes silently;
  * the two shipped constants are the numbers the decision names, and the
    |gamma| row would still fail under the old relative figure -- without which
    the whole item would be cosmetic.

The script is reached by path: the directory name ``m3a-smoke`` contains a
hyphen, so it is not importable as a package module.  Importing it runs nothing
but its imports and its constants (``main`` is ``__main__``-guarded), and the
solver is never invoked here.
"""

import importlib.util
import pathlib

MODULE_PATH = (pathlib.Path(__file__).resolve().parent.parent
               / "tools" / "host" / "m3a-smoke" / "board_run_cw_poynting.py")
_spec = importlib.util.spec_from_file_location("board_run_cw_poynting",
                                              MODULE_PATH)
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)

#: The healthy run's own numbers: |gamma| = 1.4e-2 as the tone path measured it,
#: and the bin path's refit of the same station phasors.  The 1.68e-4 difference
#: is the 1.2e-2 *relative* discrepancy that the old relative 1e-3 flagged.
GAMMA_TONE = 0.0140
GAMMA_BIN = 0.014168


def test_a_clean_self_check_is_silent():
    """A run whose five rows all agree prints no MISMATCH and reads OK.

    Each row is inside its own tolerance by a wide margin, which is what a
    correct rebuild produces: the four rows a healthy run agrees on are well
    inside 1e-6 relative, and |gamma| is within the absolute figure its spread
    needs.
    """
    checks = [
        ("beta", 232.0, 232.0, mod.SELF_CHECK_REL_TOL, False),
        ("eps_eff", 3.5678, 3.5678, mod.SELF_CHECK_REL_TOL, False),
        ("|S21|", 0.9931, 0.9931, mod.SELF_CHECK_REL_TOL, False),
        ("|gamma|", GAMMA_TONE, GAMMA_BIN, mod.SELF_CHECK_GAMMA_ABS_TOL, True),
        ("residual", 0.0042, 0.0042, mod.SELF_CHECK_REL_TOL, False),
    ]
    lines, bad = mod.self_check(checks)
    assert len(lines) == len(checks), (
        "one printed row per check: the verdict names rows by position, so a "
        "dropped row would silently judge nothing")
    assert not any("MISMATCH" in line for line in lines), (
        "a healthy run must be silent; every line was: %r" % (lines,))
    assert bad == [], (
        "no row is outside its tolerance, so nothing may be reported as bad: "
        "%r" % (bad,))
    assert mod.verdict_text(bad) == "OK", (
        "an empty failure list is the OK verdict, by the same function the "
        "script prints through")


def test_gamma_row_is_silent_at_the_noise_it_carries():
    """The |gamma| row is silent at the 1.2e-2 relative difference it inherits.

    This is the load-bearing case of the whole item.  Two separate
    ``fit_station_impedance`` calls -- the tone path during the run, the bin
    reader off the rebuilt vector -- are 1.2e-2 apart *relatively* and 1.7e-4
    apart *absolutely* on a |gamma| of 1.4e-2.  Judged with the SHIPPED
    absolute figure, 1.7e-4 is inside 1e-3: that row must not be reported.
    """
    line, failed = mod.self_check_row("|gamma|", GAMMA_TONE, GAMMA_BIN,
                                      mod.SELF_CHECK_GAMMA_ABS_TOL,
                                      absolute=True)
    assert not failed, (
        "1.7e-4 absolute on a |gamma| of 1.4e-2 is inside the shipped 1e-3 "
        "absolute figure (about 6x headroom), so two independent fits at that "
        "agreement must not be flagged: %r" % (line,))
    assert "MISMATCH" not in line, (
        "no flag on a passing row: %r" % (line,))
    assert "abs=1.68e-04" in line, (
        "the row must report the absolute difference it judged, so the "
        "agreement is visible in the log: %r" % (line,))


def test_gamma_row_still_bites_at_the_scale_of_a_rebuild_defect():
    """A rebuild defect that moves |gamma| at order |gamma| still fails.

    The tolerance is 1e-3 absolute and |gamma| itself is 1.4e-2, about 14x
    larger, so a rebuild that doubles the reflected magnitude is far outside
    any noise argument: the row must flag and the verdict must name it.
    """
    line, failed = mod.self_check_row("|gamma|", GAMMA_TONE, 0.0280,
                                      mod.SELF_CHECK_GAMMA_ABS_TOL,
                                      absolute=True)
    assert failed, (
        "a 1.4e-2 absolute move is 14x the 1e-3 tolerance and is not a fit "
        "disagreement, so the row must fail: %r" % (line,))
    assert "MISMATCH" in line, (
        "a failed row carries the flag, or the log reads clean while the "
        "verdict says CHECK: %r" % (line,))
    lines, bad = mod.self_check(
        [("|gamma|", GAMMA_TONE, 0.0280, mod.SELF_CHECK_GAMMA_ABS_TOL, True)])
    assert bad == ["|gamma|"], (
        "the verdict names the row that failed, in row order: %r" % (bad,))
    assert len(lines) == 1, "one check in, one line out: %r" % (lines,)
    assert mod.verdict_text(bad) == "CHECK: |gamma|", (
        "the verdict string is the one the script prints: %r"
        % (mod.verdict_text(bad),))


def test_relative_rows_keep_the_tight_relative_tolerance():
    """The four rows a healthy run agrees on are still judged relative at 1e-6.

    A healthy run matches those rows to 1e-6 relative, so a 5e-7 relative
    perturbation passes and a 1e-5 one does not: loosening the |gamma| row must
    not have loosened them, or a real drift in beta / eps_eff / |S21| /
    residual would hide.
    """
    tight_line, tight_failed = mod.self_check_row(
        "beta", 1.0, 1.0 * (1.0 + 5.0e-7), mod.SELF_CHECK_REL_TOL)
    assert not tight_failed, (
        "5e-7 relative is inside the 1e-6 these rows are held to, "
        "so this perturbation must pass: %r" % (tight_line,))
    loose_line, loose_failed = mod.self_check_row(
        "beta", 1.0, 1.0 * (1.0 + 1.0e-5), mod.SELF_CHECK_REL_TOL)
    assert loose_failed, (
        "1e-5 relative is ten times the 1e-6 these rows are held to, so it "
        "must fail: %r" % (loose_line,))
    assert "MISMATCH" in loose_line, (
        "and the failure must carry the flag: %r" % (loose_line,))


def test_the_printed_row_states_which_measure_judged_it():
    """Each row says whether it was judged relatively or absolutely.

    Without that, a reader cannot tell a real mismatch from a tolerance the
    comparison can never reach -- which is exactly the state the old row left
    the log in.
    """
    gamma_line, _ = mod.self_check_row("|gamma|", GAMMA_TONE, GAMMA_BIN,
                                       mod.SELF_CHECK_GAMMA_ABS_TOL,
                                       absolute=True)
    beta_line, _ = mod.self_check_row("beta", 232.0, 232.0,
                                      mod.SELF_CHECK_REL_TOL)
    assert "abs=" in gamma_line, (
        "the |gamma| row is judged absolutely, so it prints abs=: %r"
        % (gamma_line,))
    assert "rel=" not in gamma_line, (
        "and it must not also claim a relative measure: %r" % (gamma_line,))
    assert "rel=" in beta_line, (
        "these rows are judged relatively, so they print rel=: %r"
        % (beta_line,))
    assert "abs=" not in beta_line, (
        "and they must not claim an absolute measure: %r" % (beta_line,))


def test_nan_fails_rather_than_passing_silently():
    """A NaN fails, on either scale: a refused fit must never read as OK.

    Every comparison against NaN is False, so ``delta <= tol`` is False and
    ``not (delta <= tol)`` is True.  Written the other way round -- as
    ``delta > tol`` -- a NaN would have passed and the verdict would have read
    OK on a record whose fits never completed.
    """
    for absolute in (True, False):
        line, failed = mod.self_check_row(
            "|gamma|", float("nan"), 0.014, mod.SELF_CHECK_GAMMA_ABS_TOL,
            absolute=absolute)
        assert failed, (
            "a NaN on either scale is not agreement and must fail "
            "(absolute=%r): %r" % (absolute, line))
        assert "MISMATCH" in line, (
            "a failed row carries the flag whatever killed it: %r" % (line,))


def test_the_shipped_tolerances_are_the_ones_the_decision_names():
    """The two constants are exactly the figures the decision fixed.

    And the |gamma| row of the healthy run would still fail under the old
    relative 1e-6, so the change is load-bearing rather than cosmetic: the
    quiet comes from judging the row on the absolute scale, not from the check
    having gone slack.
    """
    assert mod.SELF_CHECK_GAMMA_ABS_TOL == 1.0e-3, (
        "the |gamma| row is absolute at 1e-3: %r"
        % (mod.SELF_CHECK_GAMMA_ABS_TOL,))
    assert mod.SELF_CHECK_REL_TOL == 1.0e-6, (
        "these rows are relative at 1e-6: %r"
        % (mod.SELF_CHECK_REL_TOL,))
    relative = abs(GAMMA_TONE - GAMMA_BIN) / max(abs(GAMMA_TONE), 1e-30)
    assert relative > 1.0e-6, (
        "the healthy run's |gamma| rows are %.2e apart relative to the tone "
        "value, so the old relative 1e-6 would flag them" % relative)
    old_line, old_failed = mod.self_check_row(
        "|gamma|", GAMMA_TONE, GAMMA_BIN, mod.SELF_CHECK_REL_TOL,
        absolute=False)
    assert old_failed, (
        "the same numbers judged relatively must fail, which is the defect "
        "being fixed: %r" % (old_line,))
