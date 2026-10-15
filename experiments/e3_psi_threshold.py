"""E3: what the PSI thresholds mean at each window size.

PSI is compared against 0.1 and 0.2, two numbers that appear in every drift runbook and
know nothing about how much data was used to compute the statistic. A KS p-value is
compared against a distribution that does. This measures what that difference costs, by
computing PSI many times on windows where nothing has drifted and asking how often the
conventional reading fires.

If the thresholds travelled, the share crossing them would be roughly constant down the
table. The question is whether they do.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import table, write  # noqa: E402

from drift_monitor.config import PSI_ACT, PSI_INVESTIGATE  # noqa: E402
from drift_monitor.detectors import psi_value  # noqa: E402

WINDOWS = (250, 500, 1000, 2000, 5000, 20000, 100000)
REFERENCE_ROWS = 50000
BINS = 10
REPLICATES = 400
SEED = 900_000


def run() -> dict:
    cells = []
    for rows in WINDOWS:
        rng = np.random.default_rng(SEED + rows)
        values = np.array([
            psi_value(rng.normal(size=REFERENCE_ROWS), rng.normal(size=rows), BINS)
            for _ in range(REPLICATES)
        ])
        cells.append({
            "detection_rows": rows,
            "median_null_psi": float(np.median(values)),
            "p95_null_psi": float(np.quantile(values, 0.95)),
            "share_over_investigate": float(np.mean(values > PSI_INVESTIGATE)),
            "share_over_act": float(np.mean(values > PSI_ACT)),
        })

    # The sweep above holds the reference window large and stable. A team that retrains
    # monthly compares last month against the month before, so both windows are small and
    # both carry sampling noise. That case is measured separately because it is the one
    # the runbook thresholds were never checked against, and it behaves very differently.
    paired = []
    for rows in (250, 1000, 5000, 20000):
        rng = np.random.default_rng(SEED + 7 + rows)
        values = np.array([
            psi_value(rng.normal(size=rows), rng.normal(size=rows), BINS)
            for _ in range(REPLICATES)
        ])
        paired.append({
            "window_rows": rows,
            "median_null_psi": float(np.median(values)),
            "share_over_investigate": float(np.mean(values > PSI_INVESTIGATE)),
            "share_over_act": float(np.mean(values > PSI_ACT)),
        })

    smallest, largest = cells[0], cells[-1]
    worst_paired = max(paired, key=lambda c: c["share_over_investigate"])
    return {
        "paired_cells": paired,
        "worst_paired_window": worst_paired["window_rows"],
        "worst_paired_share_investigate": worst_paired["share_over_investigate"],
        "worst_paired_median": worst_paired["median_null_psi"],
        "experiment": "e3_psi_threshold",
        "question": "Do the fixed PSI thresholds mean the same thing at every window size?",
        "replicates": REPLICATES,
        "bins": BINS,
        "investigate_threshold": PSI_INVESTIGATE,
        "act_threshold": PSI_ACT,
        "cells": cells,
        "smallest_window": smallest["detection_rows"],
        "smallest_median_psi": smallest["median_null_psi"],
        "smallest_share_investigate": smallest["share_over_investigate"],
        "largest_window": largest["detection_rows"],
        "largest_median_psi": largest["median_null_psi"],
        "median_collapse_ratio": smallest["median_null_psi"] / largest["median_null_psi"],
        "windows_where_act_never_fires": sum(
            1 for c in cells if c["share_over_act"] == 0.0
        ),
        "window_count": len(cells),
    }


def main() -> None:
    payload = run()
    rows = [
        [
            f"{c['detection_rows']}",
            f"{c['median_null_psi']:.4f}",
            f"{c['p95_null_psi']:.4f}",
            f"{c['share_over_investigate']:.3f}",
            f"{c['share_over_act']:.3f}",
        ]
        for c in payload["cells"]
    ]
    print(f"E3 PSI with no drift at all, {REPLICATES} replicates, {BINS} bins\n")
    print(table(
        ["window rows", "median PSI", "p95 PSI", "share > 0.1", "share > 0.2"],
        rows, [13, 12, 11, 13, 13],
    ))
    print()
    print()
    print("same statistic, both windows small, which is what a monthly retrain compares:")
    paired_rows = [
        [
            f"{c['window_rows']}",
            f"{c['median_null_psi']:.4f}",
            f"{c['share_over_investigate']:.3f}",
            f"{c['share_over_act']:.3f}",
        ]
        for c in payload["paired_cells"]
    ]
    print(table(
        ["both windows", "median PSI", "share > 0.1", "share > 0.2"],
        paired_rows, [14, 12, 13, 13],
    ))
    print()
    print(
        f"the null median falls by a factor of {payload['median_collapse_ratio']:.0f} "
        f"from {payload['smallest_window']} to {payload['largest_window']} rows; "
        f"the act threshold never fires in {payload['windows_where_act_never_fires']} "
        f"of {payload['window_count']} window sizes"
    )
    path = write("e3_psi_threshold", payload)
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
