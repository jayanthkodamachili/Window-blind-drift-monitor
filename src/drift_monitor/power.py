"""The minimum detectable shift, and the invariant that makes it checkable.

This is the module the repository exists for. A drift report says whether a shift was
found. It does not say what size of shift could have been found, and without that the
absence of an alarm carries no information. The function below answers the second question
by simulation: inject a shift of known size many times, count how often the detector
fires, and bisect on the shift until that rate reaches the target power.

Simulation rather than a closed form because the two-sample KS statistic has no convenient
power function, and a convenient approximation that quietly stopped holding would be worse
than a slower number that cannot.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from drift_monitor.detectors import detect

MAX_SHIFT = 2.0


@dataclass(frozen=True)
class DetectionFloor:
    """What a detector can and cannot see at one window size."""

    detector: str
    detection_rows: int
    minimum_detectable_shift: float
    target_power: float
    material_shift: float

    @property
    def blind(self) -> bool:
        """True when the smallest visible shift is larger than the smallest that matters.

        The whole point. A blind feature is not one where nothing happened; it is one where
        the monitor would have reported nothing either way.
        """
        return self.minimum_detectable_shift > self.material_shift

    @property
    def sqrt_n_invariant(self) -> float:
        """The minimum detectable shift scaled by the square root of the window size.

        Detection floors for a fixed-power test fall as one over the square root of the
        sample size, so this product should be roughly constant across window sizes. It is
        published next to the measurements as a check that the bisection is finding a real
        quantity rather than noise.
        """
        return self.minimum_detectable_shift * float(np.sqrt(self.detection_rows))

    def as_dict(self) -> dict:
        return {
            "detector": self.detector,
            "detection_rows": self.detection_rows,
            "minimum_detectable_shift": round(self.minimum_detectable_shift, 6),
            "target_power": self.target_power,
            "material_shift": self.material_shift,
            "blind": self.blind,
            "sqrt_n_invariant": round(self.sqrt_n_invariant, 4),
        }


def power_at_shift(
    shift: float,
    detector: str,
    reference_rows: int,
    detection_rows: int,
    replicates: int,
    rng: np.random.Generator,
    bins: int,
    alpha: float,
) -> float:
    """Share of replicates where the detector fires on a shift of this size."""
    fired = 0
    for _ in range(replicates):
        reference = rng.normal(0.0, 1.0, reference_rows)
        detection = rng.normal(shift, 1.0, detection_rows)
        if detect(detector, reference, detection, bins, alpha).fired:
            fired += 1
    return fired / replicates


def minimum_detectable_shift(
    detector: str,
    reference_rows: int,
    detection_rows: int,
    rng: np.random.Generator,
    bins: int = 10,
    alpha: float = 0.05,
    target_power: float = 0.80,
    replicates: int = 200,
    steps: int = 8,
    material_shift: float = 0.10,
) -> DetectionFloor:
    """Bisect on shift size until the detector reaches the target power.

    Returns MAX_SHIFT when even that is not enough, which is a real outcome rather than a
    failure: a window can be small enough that no shift worth calling drift is visible, and
    reporting a number there would invent a precision the search never had.
    """
    low, high = 0.0, MAX_SHIFT

    ceiling_power = power_at_shift(
        MAX_SHIFT, detector, reference_rows, detection_rows, replicates, rng, bins, alpha
    )
    if ceiling_power < target_power:
        return DetectionFloor(detector, detection_rows, MAX_SHIFT, target_power, material_shift)

    for _ in range(steps):
        middle = (low + high) / 2.0
        power = power_at_shift(
            middle, detector, reference_rows, detection_rows, replicates, rng, bins, alpha
        )
        if power < target_power:
            low = middle
        else:
            high = middle

    return DetectionFloor(
        detector=detector,
        detection_rows=detection_rows,
        minimum_detectable_shift=(low + high) / 2.0,
        target_power=target_power,
        material_shift=material_shift,
    )
