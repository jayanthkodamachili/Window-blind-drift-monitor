# ADR-003: one shared floor per run rather than one per feature

## Status

Accepted.

## Context

Every feature in a report carries a detection floor. The floor is computed by simulating
windows of the configured size and bisecting on shift, and for the generator used here
every feature is standard normal, so the computation would return the same number for each
one.

## Decision

Compute the floor once per run and share the object across every feature.

## Alternatives considered

**Compute it per feature.** Honest for a general case and wasteful for this one: with
twelve features it multiplies the slowest operation in the repository by twelve to produce
twelve copies of one number. The CLI would take minutes instead of seconds for no
information gained.

**Compute it lazily on first access.** Rejected as a complication that saves nothing,
because every report prints the floor.

## Consequences and the boundary this creates

This is correct only while features share a distribution, which is a property of the
generator rather than of the world. On real data a feature's detection floor depends on its
own distribution: a heavily skewed feature and a symmetric one with the same window size do
not have the same floor.

That boundary is recorded here rather than left implicit, because it is the first thing to
change when the repository meets real data. The function signature already takes the
per-feature information it would need, so the change is to call it per feature and cache
by distribution rather than to restructure anything.

A test pins the current behaviour: every feature in a report carries one floor, and varying
the injected shift does not move it. The second half of that test matters more than the
first, because it catches the floor accidentally being computed from the data it is
judging.
