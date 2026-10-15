"""Print the table a reviewer should actually see, for the CI job summary.

It leads with the blind window sizes rather than the false alarm rate. The alarm rate is
the attention-getting number and it flatters the tool for finding it; the blind set is
what a team has to act on, because it is the part their current monitor is silently
wrong about.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
METRICS = ROOT / "docs" / "metrics.json"
E2 = ROOT / "docs" / "experiments" / "e2_detection_floor.json"


def main() -> int:
    if not METRICS.exists() or not E2.exists():
        print("### receipts\n\nexperiment output missing, nothing to summarise.")
        return 0

    metrics = json.loads(METRICS.read_text())["metrics"]
    e2 = json.loads(E2.read_text())

    print("### What each window size can actually see\n")
    print(
        f"Smallest shift detectable at {int(e2['cells'][0]['target_power'] * 100)} percent "
        f"power, against a material shift of {e2['material_shift']} standard deviations.\n"
    )
    print("| window rows | detection floor (sd) | verdict |")
    print("| --- | --- | --- |")
    for cell in e2["cells"]:
        verdict = "blind" if cell["blind"] else "visible"
        print(
            f"| {cell['detection_rows']} "
            f"| {cell['minimum_detectable_shift']:.4f} | {verdict} |"
        )
    print()
    print(
        f"{metrics['blind_window_count']} of the seven window sizes cannot see a shift "
        f"worth acting on. The floor times the square root of the window varies by a "
        f"factor of {metrics['invariant_spread']:.2f} across the table, which is the check "
        f"that the search found a real quantity.\n"
    )
    print(
        f"With nothing drifting at all, a forty feature monitor raises an alarm on "
        f"{metrics['forty_alarm_rate']:.3f} of runs. Correcting for that raises the "
        f"detection floor by a factor of {metrics['floor_multiple']:.2f}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
