"""The three detectors a drift monitor usually ships with.

Two of them return a p-value and one does not, and that asymmetry is the subject of
experiment three. A KS or chi-square statistic is compared against a reference
distribution that knows the sample size. PSI is compared against 0.1 and 0.2, two numbers
that know nothing at all, and the consequence is measured rather than asserted.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import stats

from drift_monitor.config import PSI_ACT, PSI_INVESTIGATE


@dataclass(frozen=True)
class Detection:
    """One detector's verdict on one feature."""

    detector: str
    statistic: float
    p_value: float | None
    threshold: float
    fired: bool

    def as_dict(self) -> dict:
        return {
            "detector": self.detector,
            "statistic": round(self.statistic, 8),
            "p_value": None if self.p_value is None else round(self.p_value, 8),
            "threshold": round(self.threshold, 8),
            "fired": self.fired,
        }


def ks_detector(reference: np.ndarray, detection: np.ndarray, alpha: float) -> Detection:
    """Two-sample Kolmogorov-Smirnov.

    The default, because its null distribution accounts for both sample sizes, which is
    exactly the property PSI lacks.
    """
    result = stats.ks_2samp(reference, detection)
    return Detection(
        detector="ks",
        statistic=float(result.statistic),
        p_value=float(result.pvalue),
        threshold=alpha,
        fired=bool(result.pvalue < alpha),
    )


def psi_value(
    reference: np.ndarray, detection: np.ndarray, bins: int, epsilon: float = 1e-6
) -> float:
    """Population Stability Index over quantile bins of the reference window.

    The epsilon floor is load bearing and is the reason for the bins-per-row guard in the
    config. An empty detection bin would otherwise give log(0), and clamping it to epsilon
    turns the bin into a large positive contribution, so a window too small to populate its
    bins reports a confident score built out of nothing.
    """
    edges = np.quantile(reference, np.linspace(0.0, 1.0, bins + 1))
    edges[0], edges[-1] = -np.inf, np.inf
    reference_share = np.histogram(reference, edges)[0] / reference.size
    detection_share = np.histogram(detection, edges)[0] / detection.size
    reference_share = np.clip(reference_share, epsilon, None)
    detection_share = np.clip(detection_share, epsilon, None)
    return float(
        np.sum((detection_share - reference_share) * np.log(detection_share / reference_share))
    )


def psi_detector(reference: np.ndarray, detection: np.ndarray, bins: int) -> Detection:
    """PSI against the conventional 0.2 action threshold.

    No p-value, because there is nothing to compute one against: the threshold is a fixed
    constant rather than a quantile of any null distribution. That is not an oversight in
    this implementation, it is how the statistic is used in practice, and experiment three
    measures what it costs.
    """
    value = psi_value(reference, detection, bins)
    return Detection(
        detector="psi",
        statistic=value,
        p_value=None,
        threshold=PSI_ACT,
        fired=bool(value > PSI_ACT),
    )


def psi_band(value: float) -> str:
    """The conventional three-band reading of a PSI value."""
    if value > PSI_ACT:
        return "act"
    if value > PSI_INVESTIGATE:
        return "investigate"
    return "stable"


def chi_square_detector(
    reference: np.ndarray, detection: np.ndarray, bins: int, alpha: float
) -> Detection:
    """Chi-square on the same quantile bins PSI uses.

    Included as the control that isolates the threshold from the binning. It sees exactly
    what PSI sees and differs only in comparing the result against a distribution that
    knows the sample size, so any gap between the two is attributable to the threshold
    rather than to the discretisation.
    """
    edges = np.quantile(reference, np.linspace(0.0, 1.0, bins + 1))
    edges[0], edges[-1] = -np.inf, np.inf
    observed = np.histogram(detection, edges)[0]
    expected_share = np.histogram(reference, edges)[0] / reference.size
    expected = expected_share * detection.size

    keep = expected > 0
    observed, expected = observed[keep], expected[keep]
    if expected.size < 2:
        return Detection("chi_square", 0.0, 1.0, alpha, False)

    # Rescale so the two vectors sum alike. chisquare refuses otherwise, and the rescale
    # is exact rather than a fudge: both are counts over the same detection window.
    expected = expected * (observed.sum() / expected.sum())
    result = stats.chisquare(f_obs=observed, f_exp=expected)
    return Detection(
        detector="chi_square",
        statistic=float(result.statistic),
        p_value=float(result.pvalue),
        threshold=alpha,
        fired=bool(result.pvalue < alpha),
    )


def detect(
    name: str, reference: np.ndarray, detection: np.ndarray, bins: int, alpha: float
) -> Detection:
    if name == "ks":
        return ks_detector(reference, detection, alpha)
    if name == "psi":
        return psi_detector(reference, detection, bins)
    if name == "chi_square":
        return chi_square_detector(reference, detection, bins, alpha)
    raise ValueError(f"unreachable: config validation should have rejected {name!r}")
