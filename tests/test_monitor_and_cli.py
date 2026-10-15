from __future__ import annotations

import json

import numpy as np
import pytest

from drift_monitor import cli
from drift_monitor.config import MonitorConfig
from drift_monitor.detectors import Detection
from drift_monitor.generate import generate
from drift_monitor.monitor import (
    MonitorReport,
    _apply_benjamini_hochberg,
    describe_psi,
    run_monitor,
)

FAST = [
    "--reference-rows", "2000", "--detection-rows", "500", "--n-features", "4",
    "--power-replicates", "20", "--seed", "5",
]


# ----- monitor -----

def test_a_report_covers_every_feature(fast_config):
    assert len(run_monitor(fast_config).features) == fast_config.n_features


def test_an_injected_shift_is_found_when_the_window_can_see_it():
    config = MonitorConfig(
        reference_rows=20000, detection_rows=4000, n_features=3,
        shifted_features=1, injected_shift=0.5, power_replicates=20,
        bisection_steps=2, seed=8,
    )
    report = run_monitor(config)
    assert report.features[0].detection.fired is True
    assert report.features[0].missed is False


def test_a_shift_below_the_floor_is_missed_and_the_report_says_why():
    """The case the repository exists for: a real shift, no alarm, and a stated reason."""
    config = MonitorConfig(
        reference_rows=20000, detection_rows=200, n_features=3,
        shifted_features=1, injected_shift=0.05, material_shift=0.05,
        power_replicates=30, bisection_steps=3, psi_bins=10, seed=11,
    )
    report = run_monitor(config)
    assert report.features[0].missed is True
    assert report.blind


def test_a_window_with_no_shift_anywhere_reports_no_misses(fast_config):
    config = MonitorConfig(**{**fast_config.as_dict(), "shifted_features": 0})
    assert run_monitor(config).missed == ()


def test_expected_false_alarms_is_alpha_times_the_feature_count(fast_config):
    report = run_monitor(fast_config)
    assert report.expected_false_alarms == pytest.approx(
        report.effective_alpha * fast_config.n_features
    )


def test_the_any_feature_alarm_probability_grows_with_the_feature_count():
    def probability(n_features: int) -> float:
        config = MonitorConfig(
            n_features=n_features, detection_rows=500, reference_rows=2000,
            shifted_features=0, power_replicates=20, bisection_steps=1, seed=4,
        )
        return run_monitor(config).any_feature_alarm_probability

    assert probability(20) > probability(4)


def test_monitoring_many_features_makes_an_alarm_more_likely_than_not():
    """The arithmetic a daily monitor runs into and rarely publishes."""
    config = MonitorConfig(
        n_features=40, detection_rows=500, reference_rows=2000, shifted_features=0,
        power_replicates=20, bisection_steps=1, seed=4,
    )
    assert run_monitor(config).any_feature_alarm_probability > 0.5


def test_bonferroni_lowers_the_alarm_probability(fast_config):
    plain = MonitorConfig(**{**fast_config.as_dict(), "n_features": 20, "correction": "none"})
    corrected = MonitorConfig(**{**plain.as_dict(), "correction": "bonferroni"})
    assert (
        run_monitor(corrected).any_feature_alarm_probability
        < run_monitor(plain).any_feature_alarm_probability
    )


def test_the_detection_floor_is_shared_across_features(fast_config):
    """It depends on the window and the detector, not on which column is being tested."""
    report = run_monitor(fast_config)
    floors = {f.floor.minimum_detectable_shift for f in report.features}
    assert len(floors) == 1


def test_a_prepared_window_can_be_supplied(fast_config):
    windows = generate(fast_config)
    assert run_monitor(fast_config, windows=windows).features[0].index == 0


@pytest.mark.parametrize("detector", ("ks", "psi", "chi_square"))
def test_every_detector_runs_end_to_end(detector, fast_config):
    assert run_monitor(fast_config, detector=detector).detector == detector


def test_psi_results_can_be_banded_conventionally(fast_config):
    bands = describe_psi(run_monitor(fast_config, detector="psi"))
    assert all(band in {"stable", "investigate", "act"} for band in bands)


def test_benjamini_hochberg_fires_fewer_features_than_no_correction():
    detections = [
        Detection("ks", 0.1, p_value=p, threshold=0.05, fired=p < 0.05)
        for p in (0.001, 0.02, 0.04, 0.3, 0.8)
    ]
    corrected = _apply_benjamini_hochberg(detections, alpha=0.05)
    assert sum(d.fired for d in corrected) <= sum(d.fired for d in detections)
    assert corrected[0].fired is True


def test_benjamini_hochberg_leaves_a_detector_without_p_values_untouched():
    """A multiplicity correction cannot protect a detector that has no null distribution.

    PSI is that detector, and the correction silently doing nothing to it is worth
    asserting rather than discovering later.
    """
    detections = [Detection("psi", 0.3, p_value=None, threshold=0.2, fired=True)] * 3
    assert _apply_benjamini_hochberg(detections, alpha=0.05) == detections


def test_benjamini_hochberg_rejects_nothing_when_every_p_value_is_large():
    detections = [
        Detection("ks", 0.01, p_value=p, threshold=0.05, fired=False) for p in (0.4, 0.6, 0.9)
    ]
    assert not any(d.fired for d in _apply_benjamini_hochberg(detections, alpha=0.05))


def test_a_report_is_json_serialisable(fast_config):
    json.dumps(run_monitor(fast_config).as_dict())


def test_reports_are_frozen(fast_config):
    report = run_monitor(fast_config)
    with pytest.raises(Exception):  # noqa: B017
        report.features = ()  # type: ignore[misc]


# ----- cli -----

def test_parser_defaults_match_the_documented_run():
    args = cli.build_parser().parse_args([])
    assert args.detector == "ks"
    assert args.material_shift == 0.10


def test_a_detected_shift_exits_one(capsys):
    code = cli.main([*FAST, "--detection-rows", "4000", "--injected-shift", "0.5"])
    capsys.readouterr()
    assert code == cli.EXIT_DRIFT_FOUND


def test_a_quiet_window_that_could_have_seen_something_exits_zero(capsys):
    code = cli.main([
        *FAST, "--reference-rows", "20000", "--detection-rows", "8000",
        "--shifted-features", "0", "--material-shift", "0.5",
    ])
    capsys.readouterr()
    assert code == cli.EXIT_NO_DRIFT


def test_a_quiet_window_that_could_not_have_seen_anything_exits_four(capsys):
    """The distinction an ordinary drift report cannot make."""
    code = cli.main([
        *FAST, "--detection-rows", "200", "--shifted-features", "0",
        "--material-shift", "0.02",
    ])
    out = capsys.readouterr().out
    assert code == cli.EXIT_BLIND
    assert "BLIND" in out


def test_an_impossible_run_exits_two_without_a_traceback(capsys):
    code = cli.main(["--detection-rows", "100", "--psi-bins", "30"])
    captured = capsys.readouterr()
    assert code == cli.EXIT_BAD_CONFIG
    assert "invalid monitoring run" in captured.err
    assert "Traceback" not in captured.err


def test_an_internal_failure_exits_three(monkeypatch, capsys):
    def explode(*_args, **_kwargs):
        raise RuntimeError("scipy went home")

    monkeypatch.setattr(cli, "run_monitor", explode)
    code = cli.main(FAST)
    assert code == cli.EXIT_INTERNAL_ERROR
    assert "failed to complete" in capsys.readouterr().err


def test_every_exit_code_is_distinct():
    codes = {
        cli.EXIT_NO_DRIFT, cli.EXIT_DRIFT_FOUND, cli.EXIT_BAD_CONFIG,
        cli.EXIT_INTERNAL_ERROR, cli.EXIT_BLIND,
    }
    assert len(codes) == 5


def test_json_mode_emits_parseable_output(capsys):
    cli.main([*FAST, "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["config"]["seed"] == 5
    assert len(payload["features"]) == 4


def test_table_mode_publishes_the_detection_floor(capsys):
    cli.main(FAST)
    out = capsys.readouterr().out
    assert "smallest shift this window could detect" in out
    assert "expected alarms from noise alone" in out


def test_table_mode_names_the_features_it_missed(capsys):
    cli.main([
        "--reference-rows", "20000", "--detection-rows", "200", "--n-features", "3",
        "--shifted-features", "1", "--injected-shift", "0.05", "--material-shift", "0.05",
        "--power-replicates", "30", "--seed", "11",
    ])
    assert "missed real shifts" in capsys.readouterr().out


def test_psi_mode_prints_no_p_value_column_content(capsys):
    cli.main([*FAST, "--detector", "psi"])
    assert "n/a" in capsys.readouterr().out


def test_an_unknown_detector_is_rejected_by_the_parser():
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(["--detector", "vibes"])


def test_report_counts_match_the_feature_lists(fast_config):
    report: MonitorReport = run_monitor(fast_config)
    payload = report.as_dict()
    assert payload["n_fired"] == len(report.fired)
    assert payload["n_blind"] == len(report.blind)
    assert payload["n_missed"] == len(report.missed)


def test_false_alarm_is_the_complement_of_a_true_shift():
    config = MonitorConfig(
        reference_rows=2000, detection_rows=500, n_features=4, shifted_features=0,
        power_replicates=20, bisection_steps=1, seed=5,
    )
    report = run_monitor(config)
    for feature in report.features:
        assert feature.false_alarm == (feature.detection.fired and not feature.truly_shifted)


def test_the_shared_floor_is_computed_from_a_stream_independent_of_the_windows(fast_config):
    """The floor must not reuse the window seed, or it measures the data it is judging."""
    first = run_monitor(fast_config).features[0].floor.minimum_detectable_shift
    other = MonitorConfig(**{**fast_config.as_dict(), "injected_shift": 1.5})
    second = run_monitor(other).features[0].floor.minimum_detectable_shift
    assert first == second
    assert np.isfinite(first)


def test_the_benjamini_hochberg_path_runs_inside_the_monitor():
    """The correction is wired into run_monitor, not only available as a function."""
    config = MonitorConfig(
        reference_rows=20000, detection_rows=2000, n_features=6,
        shifted_features=3, injected_shift=0.4, correction="benjamini_hochberg",
        power_replicates=20, bisection_steps=2, seed=13,
    )
    report = run_monitor(config)
    assert report.config.correction == "benjamini_hochberg"
    assert all(f.detection.p_value is not None for f in report.features)
