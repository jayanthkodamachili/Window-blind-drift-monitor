from __future__ import annotations

from dataclasses import FrozenInstanceError

import numpy as np
import pytest

from drift_monitor.config import CORRECTIONS, ConfigError, MonitorConfig
from drift_monitor.generate import Windows, generate, null_windows

# ----- config -----

def test_default_config_is_constructible():
    assert MonitorConfig().n_features == 12


def test_config_is_frozen_so_a_detector_cannot_mutate_the_run():
    config = MonitorConfig()
    with pytest.raises(FrozenInstanceError):
        config.alpha = 0.5  # type: ignore[misc]


@pytest.mark.parametrize("rows", [0, 10, 49])
def test_a_window_too_small_to_compare_is_rejected(rows):
    with pytest.raises(ConfigError, match="rows"):
        MonitorConfig(detection_rows=rows)


def test_zero_features_is_rejected():
    with pytest.raises(ConfigError, match="n_features"):
        MonitorConfig(n_features=0)


@pytest.mark.parametrize("alpha", [0.0, 1.0, 1.5])
def test_alpha_outside_the_open_unit_interval_is_rejected(alpha):
    with pytest.raises(ConfigError, match="alpha"):
        MonitorConfig(alpha=alpha)


def test_an_unknown_correction_is_rejected():
    with pytest.raises(ConfigError, match="unknown correction"):
        MonitorConfig(correction="holm")


@pytest.mark.parametrize("correction", CORRECTIONS)
def test_every_declared_correction_is_accepted(correction):
    assert MonitorConfig(correction=correction).correction == correction


def test_a_non_positive_material_shift_is_rejected():
    """A shift of zero is invisible to every test at every window size."""
    with pytest.raises(ConfigError, match="material_shift"):
        MonitorConfig(material_shift=0.0)


@pytest.mark.parametrize("power", [0.0, 1.0])
def test_target_power_outside_the_open_unit_interval_is_rejected(power):
    with pytest.raises(ConfigError, match="target_power"):
        MonitorConfig(target_power=power)


def test_too_few_replicates_is_rejected():
    with pytest.raises(ConfigError, match="power_replicates"):
        MonitorConfig(power_replicates=5)


def test_zero_bisection_steps_is_rejected():
    with pytest.raises(ConfigError, match="bisection_steps"):
        MonitorConfig(bisection_steps=0)


def test_fewer_than_two_bins_is_rejected():
    with pytest.raises(ConfigError, match="psi_bins"):
        MonitorConfig(psi_bins=1)


def test_shifting_more_features_than_exist_is_rejected():
    with pytest.raises(ConfigError, match="more features than exist"):
        MonitorConfig(n_features=3, shifted_features=5)


def test_a_negative_shifted_count_is_rejected():
    with pytest.raises(ConfigError, match="cannot be negative"):
        MonitorConfig(shifted_features=-1)


def test_a_window_too_thin_for_its_bins_is_rejected():
    """The guard that came out of a real failure, pinned so it cannot regress.

    At fewer than five rows per bin the PSI epsilon floor dominates, and the statistic
    reports confident drift between two windows drawn from one distribution.
    """
    with pytest.raises(ConfigError, match="rows per PSI bin"):
        MonitorConfig(detection_rows=100, psi_bins=30)


def test_a_window_with_exactly_five_rows_per_bin_is_allowed():
    assert MonitorConfig(detection_rows=100, psi_bins=20).psi_bins == 20


def test_bonferroni_divides_alpha_by_the_feature_count():
    config = MonitorConfig(alpha=0.05, n_features=20, correction="bonferroni")
    assert config.effective_alpha == pytest.approx(0.0025)


def test_no_correction_leaves_alpha_alone():
    assert MonitorConfig(alpha=0.05, correction="none").effective_alpha == 0.05


def test_benjamini_hochberg_reports_the_uncorrected_alpha_as_its_threshold():
    """It is not a fixed threshold, so it is applied to sorted p-values instead."""
    assert MonitorConfig(alpha=0.05, correction="benjamini_hochberg").effective_alpha == 0.05


def test_as_dict_round_trips_into_an_equal_config():
    config = MonitorConfig(n_features=7, seed=3)
    assert MonitorConfig(**config.as_dict()) == config


# ----- generator -----

def test_windows_have_the_requested_shape(fast_config):
    windows = generate(fast_config)
    assert windows.reference.shape == (fast_config.reference_rows, fast_config.n_features)
    assert windows.detection.shape == (fast_config.detection_rows, fast_config.n_features)


def test_generation_is_reproducible_from_the_seed(fast_config):
    np.testing.assert_array_equal(
        generate(fast_config).detection, generate(fast_config).detection
    )


def test_a_different_seed_produces_different_windows(fast_config):
    other = MonitorConfig(**{**fast_config.as_dict(), "seed": fast_config.seed + 1})
    assert not np.allclose(generate(fast_config).detection, generate(other).detection)


def test_only_the_declared_features_are_shifted(fast_config):
    windows = generate(fast_config)
    assert windows.shifted == (0,)
    assert windows.is_shifted(0) is True
    assert windows.is_shifted(1) is False


def test_the_shift_moves_the_mean_by_the_requested_amount():
    config = MonitorConfig(
        reference_rows=40000, detection_rows=40000, n_features=2,
        shifted_features=1, injected_shift=0.5, seed=2,
    )
    windows = generate(config)
    moved = windows.detection[:, 0].mean() - windows.reference[:, 0].mean()
    assert moved == pytest.approx(0.5, abs=0.05)


def test_unshifted_features_stay_put():
    config = MonitorConfig(
        reference_rows=40000, detection_rows=40000, n_features=2,
        shifted_features=1, injected_shift=0.5, seed=2,
    )
    windows = generate(config)
    unmoved = windows.detection[:, 1].mean() - windows.reference[:, 1].mean()
    assert unmoved == pytest.approx(0.0, abs=0.05)


def test_shifting_nothing_is_allowed_and_is_how_false_alarms_are_measured(fast_config):
    config = MonitorConfig(**{**fast_config.as_dict(), "shifted_features": 0})
    assert generate(config).shifted == ()


def test_mismatched_feature_counts_are_refused():
    with pytest.raises(ValueError, match="same features"):
        Windows(
            reference=np.zeros((10, 3)), detection=np.zeros((10, 2)),
            shifted=(), injected_shift=0.0,
        )


def test_a_shifted_index_outside_the_window_is_refused():
    with pytest.raises(ValueError, match="outside the window"):
        Windows(
            reference=np.zeros((10, 2)), detection=np.zeros((10, 2)),
            shifted=(5,), injected_shift=0.1,
        )


def test_feature_returns_one_column_from_each_window(fast_config):
    windows = generate(fast_config)
    reference, detection = windows.feature(2)
    assert reference.shape == (fast_config.reference_rows,)
    assert detection.shape == (fast_config.detection_rows,)


def test_null_windows_carry_no_shift(rng):
    windows = null_windows(rows=200, rng=rng, reference_rows=1000)
    assert windows.shifted == ()
    assert windows.n_features == 1


def test_a_reference_window_too_small_to_compare_is_rejected():
    """Checked separately from the detection window: they are different parameters.

    A parametrised test over detection_rows alone left this branch unexecuted, which the
    coverage floor caught.
    """
    with pytest.raises(ConfigError, match="reference_rows"):
        MonitorConfig(reference_rows=10)
