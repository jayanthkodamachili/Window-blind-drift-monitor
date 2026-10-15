from __future__ import annotations

from dataclasses import FrozenInstanceError

import numpy as np
import pytest

from drift_monitor.config import PSI_ACT, PSI_INVESTIGATE
from drift_monitor.detectors import (
    Detection,
    chi_square_detector,
    detect,
    ks_detector,
    psi_band,
    psi_detector,
    psi_value,
)
from drift_monitor.power import (
    MAX_SHIFT,
    DetectionFloor,
    minimum_detectable_shift,
    power_at_shift,
)

P_VALUE_DETECTORS = ("ks", "chi_square")


# ----- detectors -----

def test_ks_does_not_fire_on_two_windows_from_one_distribution(rng):
    reference = rng.normal(size=5000)
    detection = rng.normal(size=2000)
    assert ks_detector(reference, detection, 0.05).fired is False


def test_ks_fires_on_a_large_shift(rng):
    reference = rng.normal(size=5000)
    detection = rng.normal(1.0, 1.0, 2000)
    assert ks_detector(reference, detection, 0.05).fired is True


def test_ks_reports_a_p_value_and_psi_does_not(rng):
    """The asymmetry the repository is about, asserted rather than described."""
    reference, detection = rng.normal(size=4000), rng.normal(size=1000)
    assert ks_detector(reference, detection, 0.05).p_value is not None
    assert psi_detector(reference, detection, 10).p_value is None


def test_psi_of_a_window_against_itself_is_zero(rng):
    sample = rng.normal(size=2000)
    assert psi_value(sample, sample, bins=10) == pytest.approx(0.0, abs=1e-9)


def test_psi_grows_with_the_size_of_the_shift(rng):
    reference = rng.normal(size=20000)
    small = psi_value(reference, rng.normal(0.1, 1.0, 20000), bins=10)
    large = psi_value(reference, rng.normal(1.0, 1.0, 20000), bins=10)
    assert large > small > 0


def test_psi_is_near_zero_for_a_large_null_comparison(rng):
    """The null PSI collapses as the window grows. Experiment three is about this."""
    reference, detection = rng.normal(size=50000), rng.normal(size=50000)
    assert psi_value(reference, detection, bins=10) < 0.01


def test_psi_null_value_is_much_larger_on_a_small_window(rng):
    """The same statistic, the same absence of drift, a different number.

    This is why a fixed threshold cannot be right at every window size.
    """
    small = [
        psi_value(rng.normal(size=20000), rng.normal(size=250), bins=10) for _ in range(20)
    ]
    large = [
        psi_value(rng.normal(size=20000), rng.normal(size=20000), bins=10) for _ in range(20)
    ]
    assert float(np.median(small)) > 10 * float(np.median(large))


@pytest.mark.parametrize(
    ("value", "expected"),
    [(0.0, "stable"), (0.05, "stable"), (0.15, "investigate"), (0.5, "act")],
)
def test_psi_bands_follow_the_conventional_cutoffs(value, expected):
    assert psi_band(value) == expected


def test_the_conventional_cutoffs_are_what_the_industry_uses():
    assert (PSI_INVESTIGATE, PSI_ACT) == (0.10, 0.20)


def test_chi_square_sees_the_same_bins_as_psi_and_still_knows_the_sample_size(rng):
    """The control that isolates the threshold from the binning."""
    reference, detection = rng.normal(size=20000), rng.normal(size=2000)
    assert chi_square_detector(reference, detection, 10, 0.05).p_value is not None


def test_chi_square_fires_on_a_large_shift(rng):
    reference = rng.normal(size=20000)
    detection = rng.normal(1.0, 1.0, 2000)
    assert chi_square_detector(reference, detection, 10, 0.05).fired is True


def test_chi_square_handles_a_degenerate_binning_without_crashing():
    """A constant reference column collapses every bin edge onto one value."""
    constant = np.zeros(500)
    result = chi_square_detector(constant, np.zeros(200), 10, 0.05)
    assert result.fired is False
    assert result.p_value == 1.0


@pytest.mark.parametrize("name", ("ks", "psi", "chi_square"))
def test_every_declared_detector_can_be_dispatched(name, rng):
    reference, detection = rng.normal(size=4000), rng.normal(size=1000)
    assert detect(name, reference, detection, 10, 0.05).detector == name


def test_dispatching_an_unknown_detector_raises(rng):
    with pytest.raises(ValueError, match="unreachable"):
        detect("wishful", rng.normal(size=100), rng.normal(size=100), 10, 0.05)


def test_detections_are_frozen_so_a_report_cannot_edit_a_verdict(rng):
    detection = ks_detector(rng.normal(size=1000), rng.normal(size=500), 0.05)
    with pytest.raises(FrozenInstanceError):
        detection.fired = True  # type: ignore[misc]


def test_detection_as_dict_keeps_a_missing_p_value_as_null(rng):
    payload = psi_detector(rng.normal(size=4000), rng.normal(size=1000), 10).as_dict()
    assert payload["p_value"] is None


# ----- power -----

def test_power_rises_with_the_size_of_the_shift(rng):
    low = power_at_shift(0.05, "ks", 5000, 1000, 60, rng, 10, 0.05)
    high = power_at_shift(0.60, "ks", 5000, 1000, 60, rng, 10, 0.05)
    assert high > low


def test_power_at_a_zero_shift_is_near_alpha(rng):
    """With no shift the fire rate is the false positive rate, which is alpha."""
    measured = power_at_shift(0.0, "ks", 5000, 1000, 300, rng, 10, 0.05)
    assert measured < 0.12


def test_power_at_a_huge_shift_is_one(rng):
    assert power_at_shift(2.0, "ks", 5000, 1000, 40, rng, 10, 0.05) == 1.0


def test_the_detection_floor_falls_as_the_window_grows(rng):
    small = minimum_detectable_shift("ks", 5000, 300, rng, replicates=60, steps=5)
    large = minimum_detectable_shift("ks", 5000, 4000, rng, replicates=60, steps=5)
    assert large.minimum_detectable_shift < small.minimum_detectable_shift


def test_the_floor_times_the_square_root_of_the_window_is_roughly_constant(rng):
    """The invariant that says the bisection found a real quantity rather than noise.

    A fixed-power detection floor falls as one over the square root of the sample size, so
    this product should hold across window sizes. It is a loose bound because each floor
    is itself a simulation estimate.
    """
    floors = [
        minimum_detectable_shift("ks", 20000, rows, rng, replicates=120, steps=7)
        for rows in (500, 2000, 8000)
    ]
    invariants = [floor.sqrt_n_invariant for floor in floors]
    assert max(invariants) / min(invariants) < 1.5


def test_psi_on_a_tiny_window_has_high_power_for_the_wrong_reason(rng):
    """A result found by a test that assumed the opposite and was wrong.

    The guess was that PSI on a sixty-row window would be unable to see any shift, so the
    search would hit its ceiling. It detected a 0.44 shift comfortably. The reason is not
    that PSI is good at small windows: its null distribution is already inflated there, so
    it fires on almost anything. High power bought with a ruinous false alarm rate is not
    power worth having, and only measuring both reveals the difference.
    """
    floor = minimum_detectable_shift("psi", 2000, 60, rng, bins=10, replicates=40, steps=4)
    assert floor.minimum_detectable_shift < 1.0

    null_fire_rate = power_at_shift(0.0, "psi", 2000, 60, 200, rng, 10, 0.05)
    assert null_fire_rate > 0.20


def test_the_search_reports_its_ceiling_when_even_the_largest_shift_is_invisible(monkeypatch):
    """The ceiling branch, reached directly rather than through a contrived config.

    No sane window and detector combination was found that misses a two standard deviation
    shift, so the branch is exercised by holding power below target. It stays because
    returning a bisected number from a search that never bracketed the target would invent
    a precision the search did not have.
    """
    monkeypatch.setattr("drift_monitor.power.power_at_shift", lambda *a, **k: 0.10)
    floor = minimum_detectable_shift(
        "ks", 2000, 100, np.random.default_rng(1), replicates=20, steps=3
    )
    assert floor.minimum_detectable_shift == MAX_SHIFT
    assert floor.blind is True


def test_a_floor_above_the_material_shift_is_reported_as_blind():
    floor = DetectionFloor("ks", 300, minimum_detectable_shift=0.3,
                           target_power=0.8, material_shift=0.1)
    assert floor.blind is True


def test_a_floor_below_the_material_shift_is_not_blind():
    floor = DetectionFloor("ks", 30000, minimum_detectable_shift=0.02,
                           target_power=0.8, material_shift=0.1)
    assert floor.blind is False


def test_the_floor_is_reproducible_from_its_generator():
    first = minimum_detectable_shift(
        "ks", 4000, 800, np.random.default_rng(3), replicates=40, steps=4
    )
    second = minimum_detectable_shift(
        "ks", 4000, 800, np.random.default_rng(3), replicates=40, steps=4
    )
    assert first.minimum_detectable_shift == second.minimum_detectable_shift


def test_psi_has_a_worse_detection_floor_than_ks_on_the_same_window(rng):
    """The headline comparison, as a test rather than only as an experiment."""
    ks_floor = minimum_detectable_shift("ks", 20000, 2000, rng, replicates=80, steps=6)
    psi_floor = minimum_detectable_shift("psi", 20000, 2000, rng, replicates=80, steps=6)
    assert psi_floor.minimum_detectable_shift > ks_floor.minimum_detectable_shift


def test_floor_as_dict_publishes_the_invariant_alongside_the_floor():
    payload = DetectionFloor("ks", 2500, 0.1, 0.8, 0.1).as_dict()
    assert payload["sqrt_n_invariant"] == pytest.approx(0.1 * 50.0)
    assert set(payload) == {
        "detector", "detection_rows", "minimum_detectable_shift", "target_power",
        "material_shift", "blind", "sqrt_n_invariant",
    }


def test_detection_objects_carry_their_threshold_for_the_report(rng):
    detection: Detection = ks_detector(rng.normal(size=2000), rng.normal(size=500), 0.01)
    assert detection.threshold == 0.01
