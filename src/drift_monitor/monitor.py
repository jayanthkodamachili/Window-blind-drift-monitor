"""Run the detectors, apply the multiplicity correction, and report the blind set.

The report carries two things an ordinary drift report does not: what the monitor could
have seen, and how many alarms to expect from pure noise given how many features were
tested. Both are properties of the monitoring setup rather than of the data, which is why
no amount of staring at the data reveals them.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from drift_monitor.config import MonitorConfig
from drift_monitor.detectors import Detection, detect, psi_band
from drift_monitor.generate import Windows, generate
from drift_monitor.power import DetectionFloor, minimum_detectable_shift


@dataclass(frozen=True)
class FeatureResult:
    """One feature, as seen by one detector, with what the monitor could have seen."""

    index: int
    detection: Detection
    floor: DetectionFloor
    truly_shifted: bool

    @property
    def missed(self) -> bool:
        """A real shift that did not fire. Only knowable because the truth was injected."""
        return self.truly_shifted and not self.detection.fired

    @property
    def false_alarm(self) -> bool:
        return not self.truly_shifted and self.detection.fired

    def as_dict(self) -> dict:
        return {
            "index": self.index,
            "detection": self.detection.as_dict(),
            "floor": self.floor.as_dict(),
            "truly_shifted": self.truly_shifted,
            "missed": self.missed,
            "false_alarm": self.false_alarm,
        }


@dataclass(frozen=True)
class MonitorReport:
    """Everything one monitoring pass has to say, including about itself."""

    config: MonitorConfig
    detector: str
    features: tuple[FeatureResult, ...]
    effective_alpha: float

    @property
    def fired(self) -> tuple[FeatureResult, ...]:
        return tuple(f for f in self.features if f.detection.fired)

    @property
    def blind(self) -> tuple[FeatureResult, ...]:
        """Features where a shift worth caring about would not have been seen."""
        return tuple(f for f in self.features if f.floor.blind)

    @property
    def missed(self) -> tuple[FeatureResult, ...]:
        return tuple(f for f in self.features if f.missed)

    @property
    def expected_false_alarms(self) -> float:
        """How many features should fire on noise alone, given the correction in force.

        Printed next to the alarm count because a count of two means something different
        when the setup produces 0.6 by chance than when it produces 0.05.
        """
        return self.effective_alpha * len(self.features)

    @property
    def any_feature_alarm_probability(self) -> float:
        """Probability that at least one feature fires when nothing has drifted."""
        return float(1.0 - (1.0 - self.effective_alpha) ** len(self.features))

    def as_dict(self) -> dict:
        return {
            "config": self.config.as_dict(),
            "detector": self.detector,
            "effective_alpha": round(self.effective_alpha, 8),
            "features": [f.as_dict() for f in self.features],
            "n_fired": len(self.fired),
            "n_blind": len(self.blind),
            "n_missed": len(self.missed),
            "expected_false_alarms": round(self.expected_false_alarms, 4),
            "any_feature_alarm_probability": round(self.any_feature_alarm_probability, 6),
        }


def _apply_benjamini_hochberg(
    detections: list[Detection], alpha: float
) -> list[Detection]:
    """Re-decide which detections fire, controlling the false discovery rate.

    Only touches detectors that produced a p-value. PSI has none, so under this correction
    it is left exactly as it was, which is itself worth seeing: a multiplicity correction
    cannot protect a detector that never computed a null distribution.
    """
    indexed = [(i, d) for i, d in enumerate(detections) if d.p_value is not None]
    if not indexed:
        return detections

    indexed.sort(key=lambda pair: pair[1].p_value)
    total = len(indexed)
    cutoff_rank = 0
    for rank, (_, detection) in enumerate(indexed, start=1):
        if detection.p_value <= alpha * rank / total:
            cutoff_rank = rank

    updated = list(detections)
    for rank, (position, detection) in enumerate(indexed, start=1):
        updated[position] = Detection(
            detector=detection.detector,
            statistic=detection.statistic,
            p_value=detection.p_value,
            threshold=alpha * rank / total,
            fired=rank <= cutoff_rank,
        )
    return updated


def run_monitor(
    config: MonitorConfig,
    detector: str = "ks",
    windows: Windows | None = None,
) -> MonitorReport:
    """Run one monitoring pass and report what it saw and what it could not have seen."""
    if windows is None:
        windows = generate(config)

    alpha = config.effective_alpha
    detections = [
        detect(detector, *windows.feature(index), config.psi_bins, alpha)
        for index in range(windows.n_features)
    ]

    if config.correction == "benjamini_hochberg":
        detections = _apply_benjamini_hochberg(detections, config.alpha)

    # The detection floor depends on the window size and the detector, not on the feature,
    # so it is computed once and shared. Recomputing it per feature would multiply the
    # runtime by the feature count for identical numbers.
    rng = np.random.default_rng(config.seed + 1)
    floor = minimum_detectable_shift(
        detector=detector,
        reference_rows=config.reference_rows,
        detection_rows=config.detection_rows,
        rng=rng,
        bins=config.psi_bins,
        alpha=alpha,
        target_power=config.target_power,
        replicates=config.power_replicates,
        steps=config.bisection_steps,
        material_shift=config.material_shift,
    )

    features = tuple(
        FeatureResult(
            index=index,
            detection=detections[index],
            floor=floor,
            truly_shifted=windows.is_shifted(index),
        )
        for index in range(windows.n_features)
    )

    return MonitorReport(
        config=config, detector=detector, features=features, effective_alpha=alpha
    )


def describe_psi(report: MonitorReport) -> list[str]:
    """Band each PSI statistic, for a report built on the conventional reading."""
    return [psi_band(f.detection.statistic) for f in report.features]
