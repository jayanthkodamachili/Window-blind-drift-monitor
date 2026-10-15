"""Report which features a drift monitor is structurally unable to see.

The package exists because a drift monitor's silence is unreadable. "No drift detected"
and "I could not have detected drift of this size" produce identical output, and which one
a team is looking at depends on the window size, which the alarm never reports. A monitor
that says nothing is making a claim about the world or a confession about itself, and
nothing in the usual report distinguishes them.

So this computes, per feature, the smallest shift the monitor could detect at its current
window, and names the features where that floor sits above anything worth detecting.
"""

from drift_monitor.config import MonitorConfig
from drift_monitor.monitor import MonitorReport, run_monitor

__all__ = ["MonitorConfig", "MonitorReport", "run_monitor"]
__version__ = "0.1.0"
