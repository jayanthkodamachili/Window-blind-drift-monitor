"""Seeded windows, with shift injected into named features.

A real monitoring log cannot support the measurement this repository makes. Asking how
often a monitor alarms when nothing has drifted requires knowing that nothing has drifted,
and asking what size of shift it would have caught requires injecting shifts of known size.
Both are facts the generator supplies and a production log never can.

Features are standard normal and independent, which is the kindest possible case for a
drift detector. Correlated or heavy-tailed features would only make the blindness worse,
so the figures here read as a floor rather than a worst case.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from drift_monitor.config import MonitorConfig


@dataclass(frozen=True)
class Windows:
    """A reference window, a detection window, and the truth about what was shifted."""

    reference: np.ndarray
    detection: np.ndarray
    shifted: tuple[int, ...]
    injected_shift: float

    def __post_init__(self) -> None:
        if self.reference.shape[1] != self.detection.shape[1]:
            raise ValueError("reference and detection windows must have the same features")
        if any(index >= self.reference.shape[1] for index in self.shifted):
            raise ValueError("a shifted feature index is outside the window")

    @property
    def n_features(self) -> int:
        return int(self.reference.shape[1])

    def feature(self, index: int) -> tuple[np.ndarray, np.ndarray]:
        return self.reference[:, index], self.detection[:, index]

    def is_shifted(self, index: int) -> bool:
        return index in self.shifted


def generate(config: MonitorConfig) -> Windows:
    """Draw a reference window and a detection window, shifting the first k features."""
    rng = np.random.default_rng(config.seed)

    reference = rng.normal(size=(config.reference_rows, config.n_features))
    detection = rng.normal(size=(config.detection_rows, config.n_features))

    shifted = tuple(range(config.shifted_features))
    if shifted:
        detection[:, list(shifted)] += config.injected_shift

    return Windows(
        reference=reference,
        detection=detection,
        shifted=shifted,
        injected_shift=config.injected_shift,
    )


def null_windows(rows: int, rng: np.random.Generator, reference_rows: int) -> Windows:
    """Two windows drawn from one distribution, for measuring false alarms.

    Kept separate from generate() because the simulations need many independent draws from
    one stream, and rebuilding a config per replicate would reseed and correlate them.
    """
    return Windows(
        reference=rng.normal(size=(reference_rows, 1)),
        detection=rng.normal(size=(rows, 1)),
        shifted=(),
        injected_shift=0.0,
    )
