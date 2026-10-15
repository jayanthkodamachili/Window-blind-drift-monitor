# ADR-002: PSI is implemented and criticised rather than omitted

## Status

Accepted.

## Context

The Population Stability Index is compared against 0.1 and 0.2, two constants that take no
account of how much data produced the statistic. The measurements here show those
thresholds meaning wildly different things at different window sizes. A repository making
that argument could reasonably refuse to implement the statistic at all.

## Decision

Ship PSI as a first-class detector, with its conventional thresholds, and measure what they
do.

## Alternatives considered

**Omit it and recommend KS.** Rejected because it would make the repository an opinion. PSI
is what a large share of production monitors actually compute, so leaving it out would mean
the tool cannot be pointed at the thing that is wrong. A criticism is worth more when it
comes with the measurement attached.

**Implement PSI with a bootstrapped threshold.** This would fix it, and it would also stop
measuring what teams are running. The repository's subject is the conventional reading, so
the conventional reading is what ships. A calibrated variant is future work, not a
substitute for the finding.

**Implement PSI without the thresholds, returning only the statistic.** Rejected as a
half-measure that avoids the argument. The thresholds are the problem, so they are in the
code, named as constants, with a comment saying they appear in order to be measured rather
than because they are endorsed.

## The control

Chi-square is included for a specific reason: it bins the data exactly as PSI does and
differs only in comparing the result against a distribution that knows the sample size.
Without it, a reader could attribute PSI's behaviour to the discretisation. With it, the
gap is attributable to the threshold.

## Consequences

The repository contains a detector it advises against, and the README has to be careful not
to read as a dismissal: PSI is interpretable, cheap, and fine for ranking features within
one window. It is the fixed cross-window threshold that does not survive measurement, and
the distinction is stated wherever the criticism appears.
