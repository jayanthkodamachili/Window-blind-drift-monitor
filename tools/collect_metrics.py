"""Re-measure every published figure and write docs/metrics.json.

Nothing here types a number. It reads the test count and coverage from the machine
readable reports, runs the four experiments, reads their JSON, and derives the values the
documents quote.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXPERIMENT_DIR = ROOT / "docs" / "experiments"
METRICS_PATH = ROOT / "docs" / "metrics.json"

EXPERIMENTS = (
    "e1_false_alarms",
    "e2_detection_floor",
    "e3_psi_threshold",
    "e4_what_correction_costs",
)

CHECKED_DOCUMENTS = (
    "README.md",
    "docs/adr/ADR-005-what-this-cannot-measure.md",
)

TABLE_ANCHOR = ["| {} |"]

ANCHORS: dict[str, list[str]] = {
    "tests_total": ["{} tests"],
    "coverage_line_pct": ["{} percent line coverage", "{}% line coverage"],
    "per_feature_rate": ["per feature it is {}", "sits at {}"],
    "forty_alarm_rate": ["fires on {} of", "alarm on {}"],
    "forty_expected_alarms": ["{} features light up", "expects {}"],
    "prediction_gap": ["within {} of", "no more than {}"],
    "psi_per_feature_rate": ["fires {} times", "rate of {}"],
    "small_window_floor": ["floor of {} sd", "{} sd at 250"],
    "large_window_floor": ["down to {} sd", "{} sd at 20000"],
    "blind_window_count": ["{} of 7 window", "{} of the seven"],
    "invariant_spread": ["factor of {}", "varies by {}"],
    "psi_investigate_threshold": ["against {} and", "over {}", "{} investigate"],
    "psi_act_threshold": ["and {}", "{} action threshold", "over {}"],
    "psi_small_median": ["median of {}", "null median {}", "| {} |"],
    "psi_collapse_ratio": ["factor of {}", "falls {}-fold"],
    "psi_act_never_fires": ["{} of 7 window sizes", "all {} window sizes"],
    "paired_share_investigate": ["{} of pure-noise", "crosses it {}"],
    "paired_median": ["median null PSI of {}", "sits at {}"],
    "paired_window": ["{} rows per window", "both windows at {}"],
    "corrected_floor": ["rises to {} sd", "floor of {} sd"],
    "uncorrected_floor": ["from {} sd", "{} sd uncorrected"],
    "floor_multiple": ["a factor of {}", "{} times worse"],
    "alarm_before": ["{} before", "from {}"],
    "alarm_after": ["to {} after", "down to {}"],
    "first_blind_features": ["at {} features", "{} features the monitor"],
}


def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=ROOT, check=False, **kwargs)


def measure_suite(skip_tests: bool) -> dict:
    """Read the test count and coverage from machine readable artefacts."""
    junit, cov = ROOT / "junit.xml", ROOT / "coverage.json"
    if skip_tests:
        missing = [p.name for p in (junit, cov) if not p.exists()]
        if missing:
            raise SystemExit(f"--skip-tests given but {', '.join(missing)} not found")
    else:
        result = run(
            [sys.executable, "-m", "pytest", f"--junitxml={junit}",
             "--cov=drift_monitor", "--cov-report=json", "-q"],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            print(result.stdout[-4000:], file=sys.stderr)
            raise SystemExit("test suite failed, refusing to publish metrics")

    suite = ET.parse(junit).getroot()
    node = suite if suite.tag == "testsuite" else suite.find("testsuite")
    total = int(node.get("tests", 0)) - int(node.get("skipped", 0))
    coverage = json.loads(cov.read_text())["totals"]["percent_covered"]
    return {"tests_total": total, "coverage_line_pct": round(coverage, 1)}


def ensure_experiments(rerun: bool) -> dict[str, dict]:
    payloads = {}
    for name in EXPERIMENTS:
        path = EXPERIMENT_DIR / f"{name}.json"
        if rerun or not path.exists():
            print(f"running experiment {name}")
            if run([sys.executable, str(ROOT / "experiments" / f"{name}.py")]).returncode:
                raise SystemExit(f"experiment {name} failed")
        payloads[name] = json.loads(path.read_text())
    return payloads


def derive(suite: dict, exp: dict[str, dict]) -> dict[str, float | int]:
    e1, e2 = exp["e1_false_alarms"], exp["e2_detection_floor"]
    e3, e4 = exp["e3_psi_threshold"], exp["e4_what_correction_costs"]

    metrics: dict[str, float | int] = {
        "tests_total": suite["tests_total"],
        "coverage_line_pct": suite["coverage_line_pct"],
        "per_feature_rate": round(e1["per_feature_ks_rate"], 3),
        "forty_alarm_rate": round(e1["forty_feature_alarm_rate"], 3),
        "forty_expected_alarms": round(e1["forty_expected_alarms"], 2),
        "prediction_gap": round(e1["max_prediction_gap"], 3),
        "psi_per_feature_rate": round(e1["per_feature_psi_rate"], 3),
        "small_window_floor": round(e2["smallest_window_floor"], 4),
        "large_window_floor": round(e2["largest_window_floor"], 4),
        "blind_window_count": e2["blind_window_count"],
        "invariant_spread": round(e2["invariant_spread"], 2),
        "psi_investigate_threshold": e3["investigate_threshold"],
        "psi_act_threshold": e3["act_threshold"],
        "psi_small_median": round(e3["smallest_median_psi"], 4),
        "psi_collapse_ratio": round(e3["median_collapse_ratio"], 0),
        "psi_act_never_fires": e3["windows_where_act_never_fires"],
        "paired_share_investigate": round(e3["worst_paired_share_investigate"], 3),
        "paired_median": round(e3["worst_paired_median"], 4),
        "paired_window": e3["worst_paired_window"],
        "uncorrected_floor": round(e4["single_feature_floor"], 4),
        "corrected_floor": round(e4["forty_feature_floor"], 4),
        "floor_multiple": round(e4["forty_floor_multiple"], 2),
        "alarm_before": round(e4["forty_uncorrected_alarm"], 3),
        "alarm_after": round(e4["forty_corrected_alarm"], 3),
        "first_blind_features": e4["first_blind_feature_count"],
    }

    # Every cell of the four published tables, so the reverse check has something to match
    # and a drifting table breaks the build like any other figure.
    for cell in e1["cells"]:
        key = cell["n_features"]
        metrics[f"e1_{key}_any"] = round(cell["any_feature_alarm_rate"], 3)
        metrics[f"e1_{key}_predicted"] = round(cell["predicted_from_per_feature"], 3)
        metrics[f"e1_{key}_expected"] = round(cell["expected_alarms"], 2)
        for suffix in ("any", "predicted", "expected"):
            ANCHORS.setdefault(f"e1_{key}_{suffix}", TABLE_ANCHOR)

    for cell in e2["cells"]:
        key = cell["detection_rows"]
        metrics[f"e2_{key}_floor"] = round(cell["minimum_detectable_shift"], 4)
        metrics[f"e2_{key}_sqrtn"] = round(cell["sqrt_n_invariant"], 2)
        ANCHORS.setdefault(f"e2_{key}_floor", TABLE_ANCHOR)
        ANCHORS.setdefault(f"e2_{key}_sqrtn", TABLE_ANCHOR)

    for cell in e3["cells"]:
        key = cell["detection_rows"]
        metrics[f"e3_{key}_median"] = round(cell["median_null_psi"], 4)
        metrics[f"e3_{key}_p95"] = round(cell["p95_null_psi"], 4)
        metrics[f"e3_{key}_inv"] = round(cell["share_over_investigate"], 3)
        metrics[f"e3_{key}_act"] = round(cell["share_over_act"], 3)
        for suffix in ("median", "p95", "inv", "act"):
            ANCHORS.setdefault(f"e3_{key}_{suffix}", TABLE_ANCHOR)

    for cell in e3["paired_cells"]:
        key = cell["window_rows"]
        metrics[f"e3p_{key}_median"] = round(cell["median_null_psi"], 4)
        metrics[f"e3p_{key}_share"] = round(cell["share_over_investigate"], 3)
        ANCHORS.setdefault(f"e3p_{key}_median", TABLE_ANCHOR)
        ANCHORS.setdefault(f"e3p_{key}_share", TABLE_ANCHOR)

    for cell in e4["cells"]:
        key = cell["n_features"]
        metrics[f"e4_{key}_floor"] = round(cell["floor"], 4)
        metrics[f"e4_{key}_before"] = round(cell["uncorrected_any_alarm"], 3)
        metrics[f"e4_{key}_after"] = round(cell["corrected_any_alarm"], 3)
        metrics[f"e4_{key}_alpha"] = cell["corrected_alpha"]
        for suffix in ("floor", "before", "after", "alpha"):
            ANCHORS.setdefault(f"e4_{key}_{suffix}", TABLE_ANCHOR)

    return metrics


FOUR_PLACE = ("_floor", "_median", "_p95", "psi_small_median", "paired_median")
THREE_PLACE = ("_any", "_predicted", "_share", "_rate", "_before", "_after",
               "_gap", "_inv", "_act")
TWO_PLACE = ("_multiple", "_spread", "_expected", "_sqrtn",
             "forty_expected_alarms")
FIVE_PLACE = ("_alpha",)
TWO_PLACE_EXACT = ("invariant_spread",)


def display_strings(metrics: dict) -> dict[str, str]:
    """How each value must appear in prose, declared rather than guessed.

    A figure rendering as 0.19 in one sentence and 0.190 in another silently defeats the
    anchor mechanism, so the format is a property of the metric rather than of the value.
    """
    out = {}
    for key, value in metrics.items():
        if isinstance(value, int):
            out[key] = str(value)
        elif key == "coverage_line_pct":
            out[key] = f"{value:.0f}" if float(value).is_integer() else f"{value:.1f}"
        elif key == "psi_collapse_ratio":
            out[key] = f"{value:.0f}"
        elif any(key.endswith(s) for s in FIVE_PLACE):
            out[key] = f"{value:.5f}"
        elif key in ("psi_investigate_threshold", "psi_act_threshold"):
            out[key] = f"{value:.1f}"
        elif any(key.endswith(s) or key == s for s in FOUR_PLACE):
            out[key] = f"{value:.4f}"
        elif any(key.endswith(s) or key == s for s in TWO_PLACE):
            out[key] = f"{value:.2f}"
        elif any(key.endswith(s) or key == s for s in THREE_PLACE):
            out[key] = f"{value:.3f}"
        else:
            out[key] = f"{value:.3f}"
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Re-measure every published figure.")
    parser.add_argument("--reuse", action="store_true")
    parser.add_argument("--skip-tests", action="store_true")
    args = parser.parse_args()

    suite = measure_suite(skip_tests=args.skip_tests)
    metrics = derive(suite, ensure_experiments(rerun=not args.reuse))

    METRICS_PATH.write_text(json.dumps({
        "metrics": metrics,
        "display": display_strings(metrics),
        "anchors": ANCHORS,
        "checked_documents": list(CHECKED_DOCUMENTS),
        "note": "every value here is produced by running the suite and the four experiments",
    }, indent=2) + "\n")
    print(f"wrote {METRICS_PATH} with {len(metrics)} metrics")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
