# ADR-001: a simulated detection floor rather than an analytic one

## Status

Accepted.

## Context

The repository's central output is the smallest shift a window could detect at a target
power. For some tests that quantity has a closed form. For the two-sample
Kolmogorov-Smirnov statistic it does not have a convenient one, and approximations exist
with conditions attached.

## Decision

Find the floor by bisecting on shift size over simulated power. Publish the square-root
invariant next to it as the check.

## Alternatives considered

**A normal-approximation power formula.** Fast, closed form, and wrong in a way that would
be invisible. The approximation holds asymptotically and degrades at exactly the small
windows this repository is most interested in, so the figures would be least trustworthy
where they matter most. An approximation that quietly stops holding is worse than a slow
number that cannot.

**Reuse a library's power function.** None covers the two-sample KS case against an
arbitrary shift, and wrapping one for the Gaussian case would make the floor a property of
that assumption rather than of the detector.

**Derive it and assert the algebra.** That would prove the implementation matches the
derivation, which is not the question. A practitioner wants to know what their monitor can
see, and only a simulation of the monitor reports that.

## The check

A fixed-power detection floor falls as one over the square root of the sample size, so the
floor times the square root of the window should be constant. Across an eighty-fold range
it varies by a factor of 1.11. The bisection knows nothing about that identity, so the
agreement is evidence it found a real quantity rather than noise. The invariant is
published in the table and asserted in a test.

## Consequences

The floor search is the slowest operation in the repository and dominates both the CLI and
CI runtime. Replicate count and bisection depth are configurable so a caller can trade
precision for speed deliberately, and the published figures use the slow settings. Every
floor carries simulation error, which is stated rather than hidden: the invariant holds to
a factor rather than exactly, and that factor is published.
