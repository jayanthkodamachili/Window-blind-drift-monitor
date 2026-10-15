"""E4: what a multiplicity correction costs, and what it buys.

Experiment one establishes that monitoring many features makes a false alarm near certain.
The standard fix is to lower the per-feature threshold. That works, and it is not free: a
lower threshold raises the detection floor, so correcting the alarm rate makes the monitor
blinder. This measures both ends of that trade at once.

The uncomfortable half is the second column. A team that fixes its alarm problem by
applying Bonferroni across forty features has also quietly decided to stop seeing a range
of shifts it could previously detect, and nothing in the drift report says so.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import table, write  # noqa: E402

from drift_monitor.power import minimum_detectable_shift  # noqa: E402

FEATURE_COUNTS = (1, 5, 10, 20, 40, 80)
DETECTION_ROWS = 2000
REFERENCE_ROWS = 50000
ALPHA = 0.05
MATERIAL_SHIFT = 0.10
REPLICATES = 300
STEPS = 9
SEED = 950_000


def run() -> dict:
    cells = []
    for n_features in FEATURE_COUNTS:
        corrected_alpha = ALPHA / n_features
        rng = np.random.default_rng(SEED + n_features)
        floor = minimum_detectable_shift(
            "ks", REFERENCE_ROWS, DETECTION_ROWS, rng,
            alpha=corrected_alpha, replicates=REPLICATES, steps=STEPS,
            material_shift=MATERIAL_SHIFT,
        )
        cells.append({
            "n_features": n_features,
            "corrected_alpha": corrected_alpha,
            "uncorrected_any_alarm": float(1.0 - (1.0 - ALPHA) ** n_features),
            "corrected_any_alarm": float(1.0 - (1.0 - corrected_alpha) ** n_features),
            "floor": floor.minimum_detectable_shift,
            "blind": floor.blind,
        })

    baseline = cells[0]
    forty = next(c for c in cells if c["n_features"] == 40)
    first_blind = next((c for c in cells if c["blind"]), None)

    return {
        "experiment": "e4_what_correction_costs",
        "question": "What does controlling the alarm rate cost in detection power?",
        "detection_rows": DETECTION_ROWS,
        "alpha": ALPHA,
        "material_shift": MATERIAL_SHIFT,
        "replicates": REPLICATES,
        "cells": cells,
        "single_feature_floor": baseline["floor"],
        "forty_feature_floor": forty["floor"],
        "forty_floor_multiple": forty["floor"] / baseline["floor"],
        "forty_uncorrected_alarm": forty["uncorrected_any_alarm"],
        "forty_corrected_alarm": forty["corrected_any_alarm"],
        "first_blind_feature_count": first_blind["n_features"] if first_blind else None,
        "blind_cell_count": sum(1 for c in cells if c["blind"]),
        "cell_count": len(cells),
    }


def main() -> None:
    payload = run()
    rows = [
        [
            f"{c['n_features']}",
            f"{c['corrected_alpha']:.5f}",
            f"{c['uncorrected_any_alarm']:.3f}",
            f"{c['corrected_any_alarm']:.3f}",
            f"{c['floor']:.4f}",
            "blind" if c["blind"] else "visible",
        ]
        for c in payload["cells"]
    ]
    print(
        f"E4 Bonferroni across features, {DETECTION_ROWS} row window, "
        f"material shift {MATERIAL_SHIFT}\n"
    )
    print(table(
        ["features", "alpha", "alarm before", "alarm after", "floor", "verdict"],
        rows, [10, 10, 14, 13, 10, 10],
    ))
    print()
    print(
        f"controlling the alarm rate across 40 features raises the detection floor from "
        f"{payload['single_feature_floor']:.4f} to {payload['forty_feature_floor']:.4f} sd, "
        f"a factor of {payload['forty_floor_multiple']:.2f}"
    )
    path = write("e4_what_correction_costs", payload)
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
