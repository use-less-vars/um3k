# Dispatch 46 acceptance criteria

These criteria are frozen before the pre-registration and before any implementation, and they are transcribed from the dispatch rather than invented here.

## A. Verbatim criteria

- The full acceptance criterion inherited from the anchor v1 + v2, unchanged: order band 1.7-2.3, absolute error bound at the finest mesh, by-order matching across all five levels, and the fundamental must be present at every level. Plus the two obligations deferred from v1 and never run: the mixed-path gate and the negative control.
- PASS / FAIL / FAILED-TO-MEASURE as the verdict vocabulary, with FAILED-TO-MEASURE meaning "the apparatus could not resolve the modes" and requiring the same diagnostic treatment this one received.

## B. Inherited numeric thresholds, quoted from the frozen amendment

"the order band 1.7 to 2.3, the absolute bound 2.0e-3 at the finest level, monotonicity, the requested candidate count of 16, the ladder geometry and the material parameters are all as frozen in v1" is quoted verbatim from section 6 of `docs/design/d45_anchor_results.md`, as that file was committed in `61bd071`. The thresholds are inherited from the v1 pre-registration through that amendment. They are not restated here as new decisions.

## C. Status

Nothing in dispatch 46 measures these criteria. This dispatch freezes them, and freezes the code they will later be applied to, before any anchor number exists. The ladder run that applies them is dispatch 47.

The two deferred obligations named in section A remain unrun. No verdict of any kind can therefore be formed in this dispatch.

Typography in section A was normalised to ASCII, meaning dash characters and quotation marks, with no change to words or numbers.
