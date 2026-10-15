"""The frozen description of a monitoring run.

Two parameters decide everything this repository measures: how many rows the detection
window holds, and how many features are tested in one pass. The first sets what the
monitor can see at all; the second sets how often it cries wolf. Teams tune neither,
because the usual report shows neither.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

DETECTORS = ("ks", "psi", "chi_square")
CORRECTIONS = ("none", "bonferroni", "benjamini_hochberg")

# The thresholds the industry treats as universal constants. They appear here so the
# repository can measure what they mean at a given window size, not because they are
# endorsed. Experiment three is about how badly they travel.
PSI_INVESTIGATE = 0.10
PSI_ACT = 0.20


class ConfigError(ValueError):
    """Raised when a monitoring run cannot be constructed, rather than merely being odd."""


@dataclass(frozen=True)
class MonitorConfig:
    """One fully specified monitoring run.

    Attributes:
        reference_rows: rows in the baseline window the monitor compares against.
        detection_rows: rows in the window under test. The number that decides what is
            visible, and the one no drift report prints.
        n_features: numeric features tested in a single pass.
        alpha: per-feature significance level.
        correction: how, if at all, the per-feature alpha is adjusted for testing many
            features at once.
        material_shift: the smallest shift, in reference standard deviations, that would
            matter to someone. A feature whose minimum detectable shift exceeds this is
            structurally blind and is reported as such.
        target_power: the power at which the minimum detectable shift is defined.
        power_replicates: simulation replicates per power evaluation.
        bisection_steps: halvings used to locate the minimum detectable shift.
        psi_bins: quantile bins used by the PSI detector.
        shifted_features: how many features actually carry an injected shift.
        injected_shift: size of that shift, in reference standard deviations.
        seed: controls window generation and every simulation.
    """

    reference_rows: int = 20000
    detection_rows: int = 2000
    n_features: int = 12
    alpha: float = 0.05
    correction: str = "none"
    material_shift: float = 0.10
    target_power: float = 0.80
    power_replicates: int = 200
    bisection_steps: int = 8
    psi_bins: int = 10
    shifted_features: int = 2
    injected_shift: float = 0.25
    seed: int = 20260216

    def __post_init__(self) -> None:
        if self.reference_rows < 50:
            raise ConfigError("reference_rows must be at least 50")
        if self.detection_rows < 50:
            raise ConfigError("detection_rows must be at least 50")
        if self.n_features < 1:
            raise ConfigError("n_features must be at least 1")
        if not 0.0 < self.alpha < 1.0:
            raise ConfigError("alpha must sit strictly between 0 and 1")
        if self.correction not in CORRECTIONS:
            raise ConfigError(f"unknown correction {self.correction!r}, expected {CORRECTIONS}")
        if self.material_shift <= 0.0:
            raise ConfigError("material_shift must be positive, a zero shift is always invisible")
        if not 0.0 < self.target_power < 1.0:
            raise ConfigError("target_power must sit strictly between 0 and 1")
        if self.power_replicates < 20:
            raise ConfigError("power_replicates below 20 cannot estimate a power")
        if self.bisection_steps < 1:
            raise ConfigError("bisection_steps must be at least 1")
        if self.psi_bins < 2:
            raise ConfigError("psi_bins must be at least 2")
        if self.shifted_features > self.n_features:
            raise ConfigError("cannot shift more features than exist")
        if self.shifted_features < 0:
            raise ConfigError("shifted_features cannot be negative")
        self._check_bins_against_window()

    def _check_bins_against_window(self) -> None:
        """Reject a bin count the detection window cannot populate.

        This guard exists because of a real failure during the build. A window sweep
        reached 50 rows against 20 PSI bins, several bins came back empty, the epsilon
        floor in the PSI formula turned each empty bin into a large positive contribution,
        and PSI reported a confident drift score on two windows drawn from one
        distribution. The sweep looked successful. Five rows per bin is a low bar and it
        catches that case where the run is described.
        """
        per_bin = self.detection_rows / self.psi_bins
        if per_bin < 5:
            raise ConfigError(
                f"detection window gives {per_bin:.1f} rows per PSI bin; "
                "below five the empty-bin floor dominates the statistic"
            )

    @property
    def effective_alpha(self) -> float:
        """The per-feature threshold after whatever correction is configured.

        Benjamini-Hochberg is not a fixed threshold, so it reports the uncorrected alpha
        here and is applied to the sorted p-values in the monitor instead.
        """
        if self.correction == "bonferroni":
            return self.alpha / self.n_features
        return self.alpha

    def as_dict(self) -> dict:
        return asdict(self)
