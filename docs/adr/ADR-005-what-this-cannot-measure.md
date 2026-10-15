# ADR-005: what this repository deliberately cannot measure

## Status

Accepted. This is the boundary record, so the limits are a decision rather than an
oversight.

## Context

The experiments produce confident numbers about a real and common blind spot in production
monitoring. Several are properties of a deliberately simple setup, and a reader who takes
them for more than they are will reach wrong conclusions about their own monitor.

## Decision

Five things are out of scope, each for a stated reason, and the README carries them in a
section of its own rather than in a footnote.

## What is out of scope, and why

**Impact, as opposed to detectability.** Everything here measures whether a shift can be
seen. Nothing measures whether seeing it would matter. A large, perfectly visible drift in
a feature the model barely uses is noise, and a small drift in a decisive feature is an
incident. This is the sharpest limitation, because a blind-feature list read as a priority
list will send effort to the wrong place. It is the Pivot, with an explicit trigger.

**Anything but an independent mean shift.** Features are standard normal and independent,
and drift arrives as a shift in the mean. Real drift changes correlations, grows tails,
adds categories, and arrives in features nobody monitors. Every floor here is therefore a
best case: a real monitor does worse, not better.

**Temporal structure.** Windows are independent draws. Production windows overlap, carry
weekly seasonality, and are autocorrelated, all of which reduce the effective sample size
below the row count the floor was computed from.

**Multivariate drift.** Each feature is tested alone. A joint distribution can move while
every marginal stays put, and nothing here would notice.

**The choice of what matters.** The material shift is an input. Every feature labelled
blind is blind relative to a threshold a human picked. The repository makes that choice
explicit and visible, which is the improvement on offer; it does not make the choice.

## Observed against declared

Everything in `docs/metrics.json` is observed: produced by code here, re-run by CI. One
thing is declared rather than observed and should be read as a modelling assumption, that a
standard normal feature resembles a production feature in any respect that matters. The
generator was chosen to be the easiest case, not a representative one.

## Floors are estimates

Every detection floor is a bisection over simulated power with a finite replicate count,
so each carries error. The square-root invariant is the published check on that, and it
holds to a factor of 1.11 across the sweep rather than exactly. No floor in any document
should be read as a constant, and the experiment JSON carries the inputs that produced each
one.

## Machine dependence

The published figures are rates, shift sizes and counts, all machine independent. No
duration is published as a headline anywhere. The detection floor search is the slowest
operation here and its runtime is a fact about the runner, so it appears in no table.

## Consequences

The repository makes a narrower claim than its numbers would support if read carelessly,
and says so in the most prominent place a limitation can go. A reviewer who reads this file
first should find nothing in the README that overreaches it.
