# 1. Record architecture decisions

Date: 2026-08-17

## Status

Accepted

## Context

palm-lab involves a series of technical choices that are not obvious from
reading the code: which gesture detection library to depend on, how to render
the settings UI, how the app registers itself to start on boot, and how it is
packaged for distribution. Each of these has viable alternatives that were
considered and rejected for specific reasons.

Without a written record, that reasoning is lost. The author will not remember
in six months why a particular approach was chosen, and will be tempted to
re-litigate settled decisions or, worse, reverse one without knowing what
constraint it was satisfying. Contributors have no way to distinguish a
deliberate choice from an accident. The project is also intended to demonstrate
engineering judgement to future employers, and judgement is only visible when
the reasoning is written down.

## Decision

We will record each significant architecture decision in a numbered Markdown
file under `docs/adr/`, following the format described by Michael Nygard.

Each record states the context that forced a decision, the decision itself, and
the consequences that follow from it — including the negative ones. Records are
immutable once accepted. A decision that is later reversed is not edited or
deleted; a new record is written that supersedes it, and the original is marked
as superseded with a pointer to its replacement.

A decision qualifies as significant if reversing it would require changing code
in more than one module, if it constrains what the project can do later, or if a
reasonable developer would ask "why was it done this way?"

## Consequences

The reasoning behind the project's structure becomes readable without archaeology
through Git history. Rejected alternatives are recorded alongside the chosen
option, so a future reader can tell the difference between a considered tradeoff
and an oversight. Onboarding a contributor becomes cheaper.

The cost is friction on every significant decision: writing a record takes
fifteen to thirty minutes and must happen at the point of deciding, not
afterwards, when the alternatives have already been forgotten. This will
occasionally feel like bureaucracy on a single-developer project.

There is a failure mode where records are written but never updated, leaving
documentation that describes an architecture the code no longer has. The
immutability rule mitigates but does not eliminate this — superseding records
still have to actually be written. Some decisions will be made without a record,
and the boundary of "significant" will be applied inconsistently.
