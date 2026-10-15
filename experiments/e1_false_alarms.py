"""E1: how often a quiet system raises an alarm anyway.

Nothing drifts in any replicate here. Every alarm counted is false. The per-feature rate
should sit at alpha, which it does, and that is not the interesting number. The interesting
number is the probability that *at least one* of the monitored features fires, because that
is what a human actually sees: one alarm in the morning, on a day when nothing happened.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import table, write  # noqa: E402

from drift_monitor.detectors import psi_detector  # noqa: E402

REPLICATES = 400
FEATURE_COUNTS = (1, 5, 10, 20, 40, 80)
REFERENCE_ROWS = 20000
DETECTION_ROWS = 2000
ALPHA = 0.05
SEED = 700_000


def run() -> dict:
    rng = np.random.default_rng(SEED)

    # One pool of per-feature decisions, reused across feature counts. Drawing fresh
    # windows per cell would make the columns independent samples of the same quantity and
    # cost eighty times the compute for a noisier answer.
    ks_fired = []
    psi_fired = []
    for _ in range(REPLICATES * max(FEATURE_COUNTS) // 10):
        reference = rng.normal(size=REFERENCE_ROWS)
        detection = rng.normal(size=DETECTION_ROWS)
        ks_fired.append(stats.ks_2samp(reference, detection).pvalue < ALPHA)
        psi_fired.append(psi_detector(reference, detection, 10).fired)

    ks_fired = np.array(ks_fired)
    psi_fired = np.array(psi_fired)
    per_feature_ks = float(ks_fired.mean())
    per_feature_psi = float(psi_fired.mean())

    cells = []
    for n_features in FEATURE_COUNTS:
        draws = rng.integers(0, ks_fired.size, size=(REPLICATES, n_features))
        any_ks = float(np.mean(ks_fired[draws].any(axis=1)))
        predicted = float(1.0 - (1.0 - per_feature_ks) ** n_features)
        cells.append({
            "n_features": n_features,
            "any_feature_alarm_rate": any_ks,
            "predicted_from_per_feature": predicted,
            "expected_alarms": per_feature_ks * n_features,
        })

    forty = next(c for c in cells if c["n_features"] == 40)
    return {
        "experiment": "e1_false_alarms",
        "question": "How often does a monitor alarm when nothing has drifted?",
        "replicates": REPLICATES,
        "alpha": ALPHA,
        "detection_rows": DETECTION_ROWS,
        "per_feature_ks_rate": per_feature_ks,
        "per_feature_psi_rate": per_feature_psi,
        "cells": cells,
        "forty_feature_alarm_rate": forty["any_feature_alarm_rate"],
        "forty_expected_alarms": forty["expected_alarms"],
        "max_prediction_gap": max(
            abs(c["any_feature_alarm_rate"] - c["predicted_from_per_feature"]) for c in cells
        ),
    }


def main() -> None:
    payload = run()
    rows = [
        [
            f"{c['n_features']}",
            f"{c['any_feature_alarm_rate']:.3f}",
            f"{c['predicted_from_per_feature']:.3f}",
            f"{c['expected_alarms']:.2f}",
        ]
        for c in payload["cells"]
    ]
    print(f"E1 false alarms with zero drift, alpha {ALPHA}, {DETECTION_ROWS} row window\n")
    headers = ["features", "any fires", "predicted", "expected count"]
    print(table(headers, rows, [11, 12, 12, 16]))
    print()
    print(
        f"per-feature rate: KS {payload['per_feature_ks_rate']:.3f}, "
        f"PSI {payload['per_feature_psi_rate']:.3f} against its fixed 0.2 threshold"
    )
    path = write("e1_false_alarms", payload)
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
