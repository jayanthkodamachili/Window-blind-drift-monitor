"""E2: what size of shift each window can actually see.

A drift report says whether something fired. This asks the question the report omits: what
is the smallest shift that would have fired, at this window size, with this detector. The
answer is the detection floor, and a feature whose floor sits above anything worth
detecting is one the monitor cannot speak about either way.

The right-hand column is the check. A fixed-power detection floor falls as one over the
square root of the window size, so the floor times the square root of the window should be
roughly constant down the table. The bisection knows nothing about that identity.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import table, write  # noqa: E402

from drift_monitor.power import minimum_detectable_shift  # noqa: E402

WINDOWS = (250, 500, 1000, 2000, 5000, 10000, 20000)
REFERENCE_ROWS = 50000
MATERIAL_SHIFT = 0.10
REPLICATES = 300
STEPS = 9
SEED = 800_000


def run() -> dict:
    cells = []
    for rows in WINDOWS:
        rng = np.random.default_rng(SEED + rows)
        floor = minimum_detectable_shift(
            "ks", REFERENCE_ROWS, rows, rng,
            replicates=REPLICATES, steps=STEPS, material_shift=MATERIAL_SHIFT,
        )
        cells.append(floor.as_dict())

    invariants = [c["sqrt_n_invariant"] for c in cells]
    blind = [c for c in cells if c["blind"]]
    visible = [c for c in cells if not c["blind"]]

    return {
        "experiment": "e2_detection_floor",
        "question": "What is the smallest shift each window size can see?",
        "detector": "ks",
        "material_shift": MATERIAL_SHIFT,
        "replicates": REPLICATES,
        "cells": cells,
        "smallest_window": WINDOWS[0],
        "smallest_window_floor": cells[0]["minimum_detectable_shift"],
        "largest_window": WINDOWS[-1],
        "largest_window_floor": cells[-1]["minimum_detectable_shift"],
        "blind_window_count": len(blind),
        "window_count": len(cells),
        "first_visible_window": visible[0]["detection_rows"] if visible else None,
        "invariant_spread": max(invariants) / min(invariants),
    }


def main() -> None:
    payload = run()
    rows = [
        [
            f"{c['detection_rows']}",
            f"{c['minimum_detectable_shift']:.4f}",
            "blind" if c["blind"] else "visible",
            f"{c['sqrt_n_invariant']:.2f}",
        ]
        for c in payload["cells"]
    ]
    print(
        f"E2 detection floor by window size, KS, 80% power, "
        f"material shift {MATERIAL_SHIFT}\n"
    )
    print(table(["window rows", "floor (sd)", "verdict", "floor x sqrt(n)"],
                rows, [13, 12, 10, 17]))
    print()
    print(
        f"{payload['blind_window_count']} of {payload['window_count']} window sizes "
        f"cannot see a {MATERIAL_SHIFT} sd shift; the invariant varies by a factor of "
        f"{payload['invariant_spread']:.2f} across the table"
    )
    path = write("e2_detection_floor", payload)
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
