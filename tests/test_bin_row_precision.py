"""Tests for the precision of one broadband bin's report row.

:func:`emfit.studies._bin_row` prints the two ``|S21|`` columns as linear
amplitudes to four decimals, tagged ``(lin)``, and ``|S11|`` as a two-decimal
decibel figure.  Three claims are pinned here, and no more:

* *The decimals survive.*  A bin whose ``|S21|`` is ``1.00844`` prints
  ``1.0084``: the amplitude the passivity budget is built from is the number
  on the page, not a decibel figure rounded to a tenth.
* *Neighbours are distinguishable.*  Two bins a thousandth of an amplitude
  apart print different rows.  At one decimal of a decibel they printed the
  same one, and a row that cannot tell two measurements apart is not a report
  of either.
* *The layout did not move.*  The number of whitespace-separated tokens in the
  row is unchanged, because the S21 unit became ``(lin)`` in place of ``dB``
  rather than gaining a word.  Anything that reads the row by position -- the
  helper scripts in ``.scratch/m2`` do exactly that -- keeps working.

No physics is asserted: the numbers are put into the dataclass by hand and the
row is a format string.
"""

from __future__ import annotations

import math

from emfit import studies
from emfit.studies import BinMetric


#: The row as it read before this change, used only to pin the token count.
#: Built from the retired specifiers: ``|S11|`` at one decimal of a decibel and
#: both ``|S21|`` columns in dB, which is the same one token as ``(lin)``.
_OLD_ROW = (
    "beta = 41.00 rad/m, eps_eff = 3.5000, |S11| = -10.5 dB (measured plane) / "
    "-9.9 dB (port plane), |S21| = 0.1 dB, passivity = |S11|^2 + |S21|^2 = "
    "1.000000, power-normalised: |S21| = 0.1 dB, passivity = |S11|^2 + "
    "|S21_power|^2 = 1.000000, fit residual = 0.0100")


def _metric(**overrides: float) -> BinMetric:
    """One bin with plausible numbers; nothing here is measured or fitted."""
    fields = dict(
        f=4.92e9, beta=41.0, s11_measured=0.30, s11_port=0.32,
        s21=1.00844, passivity=1.0, s21_power=1.00844, passivity_power=1.0,
        eps_eff=3.5, residual=0.01)
    fields.update(overrides)
    return BinMetric(**fields)


def _retired_db_1dp(magnitude: float) -> str:
    """The S21 form this change retired: ``20 log10``, one decimal."""
    return f"{20.0 * math.log10(magnitude):.1f} dB"


# ---------------------------------------------------------------------------
# (a) the amplitude column carries four decimals and says which unit it is
# ---------------------------------------------------------------------------
def test_s21_is_printed_as_a_four_decimal_linear_magnitude():
    row = studies._bin_row(_metric(s21=1.00844, s21_power=1.00844))
    assert ", |S21| = 1.0084 (lin)," in row
    assert "power-normalised: |S21| = 1.0084 (lin)," in row
    # both S21 columns are tagged, and nothing else is: S11 stays in decibels
    assert row.count("(lin)") == 2


def test_s21_rounding_is_the_printed_digit_and_not_the_decibel_rung():
    assert "|S21| = 1.0448 (lin)" in studies._bin_row(_metric(s21=1.04479))


def test_s11_keeps_decibels_but_at_two_of_them():
    row = studies._bin_row(_metric(s11_measured=0.30, s11_port=0.32))
    assert "|S11| = -10.46 dB (measured plane) / -9.90 dB (port plane)," in row


# ---------------------------------------------------------------------------
# (b) two bins that differ in transmission no longer print the same row
# ---------------------------------------------------------------------------
def test_bins_a_thousandth_apart_print_different_rows():
    lo = studies._bin_row(_metric(s21=1.0084, s21_power=1.0084))
    hi = studies._bin_row(_metric(s21=1.0094, s21_power=1.0094))
    assert lo != hi
    # the defect being fixed: at one decimal of a decibel these two collapsed
    # onto the same figure, so the rows were identical
    assert _retired_db_1dp(1.0084) == _retired_db_1dp(1.0094)


# ---------------------------------------------------------------------------
# (c) the row's token count is unchanged
# ---------------------------------------------------------------------------
def test_the_row_has_the_same_token_count_as_the_decibel_form():
    row = studies._bin_row(_metric())
    assert "BUG: passivity exceeds 1" not in row
    assert len(row.split()) == len(_OLD_ROW.split())
