"""Command line entry point.

The exit codes separate three outcomes an ordinary monitor collapses into one. Code 0 is
"nothing fired and the window could have seen something", which is the only reading of
silence that carries information. Code 4 is "nothing fired and the window could not have
seen anything", which looks identical in a normal report and means the opposite.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence

from drift_monitor.config import CORRECTIONS, DETECTORS, ConfigError, MonitorConfig
from drift_monitor.monitor import MonitorReport, run_monitor

EXIT_NO_DRIFT = 0
EXIT_DRIFT_FOUND = 1
EXIT_BAD_CONFIG = 2
EXIT_INTERNAL_ERROR = 3
EXIT_BLIND = 4


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="drift-monitor",
        description="Report drift, and report which features the window cannot see.",
    )
    parser.add_argument("--reference-rows", type=int, default=20000)
    parser.add_argument("--detection-rows", type=int, default=2000)
    parser.add_argument("--n-features", type=int, default=12)
    parser.add_argument("--detector", choices=DETECTORS, default="ks")
    parser.add_argument("--alpha", type=float, default=0.05)
    parser.add_argument("--correction", choices=CORRECTIONS, default="none")
    parser.add_argument(
        "--material-shift",
        type=float,
        default=0.10,
        help="smallest shift worth detecting, in reference standard deviations",
    )
    parser.add_argument("--target-power", type=float, default=0.80)
    parser.add_argument("--power-replicates", type=int, default=200)
    parser.add_argument("--psi-bins", type=int, default=10)
    parser.add_argument("--shifted-features", type=int, default=2)
    parser.add_argument("--injected-shift", type=float, default=0.25)
    parser.add_argument("--seed", type=int, default=20260216)
    parser.add_argument("--json", action="store_true", help="emit machine readable output")
    return parser


def config_from_args(args: argparse.Namespace) -> MonitorConfig:
    return MonitorConfig(
        reference_rows=args.reference_rows,
        detection_rows=args.detection_rows,
        n_features=args.n_features,
        alpha=args.alpha,
        correction=args.correction,
        material_shift=args.material_shift,
        target_power=args.target_power,
        power_replicates=args.power_replicates,
        psi_bins=args.psi_bins,
        shifted_features=args.shifted_features,
        injected_shift=args.injected_shift,
        seed=args.seed,
    )


def render(report: MonitorReport) -> str:
    config = report.config
    floor = report.features[0].floor
    lines = [
        f"detector {report.detector}, {config.n_features} features, "
        f"{config.detection_rows} rows in the detection window",
        f"correction {config.correction}, effective alpha {report.effective_alpha:.5f}",
        "",
        f"{'feature':<10}{'statistic':>12}{'p value':>11}{'fired':>8}{'truth':>10}",
        "-" * 51,
    ]
    for feature in report.features:
        detection = feature.detection
        p_value = "n/a" if detection.p_value is None else f"{detection.p_value:.4f}"
        truth = "shifted" if feature.truly_shifted else "stable"
        lines.append(
            f"f{feature.index:<9}{detection.statistic:>12.5f}{p_value:>11}"
            f"{('yes' if detection.fired else 'no'):>8}{truth:>10}"
        )
    lines.append("-" * 51)
    lines.append(
        f"smallest shift this window could detect at {config.target_power:.0%} power: "
        f"{floor.minimum_detectable_shift:.4f} sd"
    )
    lines.append(
        f"smallest shift that would matter: {config.material_shift:.4f} sd"
        + ("  BLIND" if floor.blind else "")
    )
    lines.append(
        f"expected alarms from noise alone: {report.expected_false_alarms:.2f} of "
        f"{config.n_features}; at least one fires "
        f"{report.any_feature_alarm_probability:.1%} of the time"
    )
    if report.missed:
        indices = ", ".join(f"f{f.index}" for f in report.missed)
        lines.append(f"missed real shifts: {indices}")
    return "\n".join(lines)


def exit_code_for(report: MonitorReport) -> int:
    if report.fired:
        return EXIT_DRIFT_FOUND
    if report.blind:
        return EXIT_BLIND
    return EXIT_NO_DRIFT


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        config = config_from_args(args)
    except ConfigError as exc:
        print(f"invalid monitoring run: {exc}", file=sys.stderr)
        return EXIT_BAD_CONFIG

    try:
        report = run_monitor(config, detector=args.detector)
    except Exception as exc:  # noqa: BLE001
        print(f"monitoring run failed to complete: {exc}", file=sys.stderr)
        return EXIT_INTERNAL_ERROR

    print(json.dumps(report.as_dict(), indent=2) if args.json else render(report))
    return exit_code_for(report)


if __name__ == "__main__":
    raise SystemExit(main())
