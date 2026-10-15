"""Shared fixtures.

Everything here is small and fast. The detection floor search is the expensive operation
in this repository, so test configs use few replicates and few bisection steps: a test
needs the search to run and return a sane number, not to return a publishable one. The
published floors come from the experiments.
"""

from __future__ import annotations

import numpy as np
import pytest

from drift_monitor.config import MonitorConfig
from drift_monitor.generate import generate


@pytest.fixture
def fast_config() -> MonitorConfig:
    return MonitorConfig(
        reference_rows=2000,
        detection_rows=500,
        n_features=4,
        power_replicates=20,
        bisection_steps=2,
        shifted_features=1,
        injected_shift=0.5,
        seed=5,
    )


@pytest.fixture
def fast_windows(fast_config):
    return generate(fast_config)


@pytest.fixture
def rng() -> np.random.Generator:
    return np.random.default_rng(99)
