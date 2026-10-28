# Dispatch 43b acceptance criteria (Task A-close)

Contract artifact written before any edit, per Dispatch 43b Step 1. If anything in the
tree contradicts this file, this file wins and the contradiction is reported before any
edit is made.

## Fences

- Task A-close only. Task B is not started.
- No harness code is written.
- Nothing under `emfit/` is edited.
- `decisions.md` is APPEND ONLY: no existing line is edited, reflowed or deleted.
- The supervisor commits. The worker does not commit.
- No em dashes, no en dashes, no hype, no rhetorical flourishes in the appended prose.
- Every figure written is traceable to a file read this session, and the file is named.

## The eleven corrigendum items

1. The t4b superseded marker was moved from the block opening to the sentence that makes
   the claim, in place, line neutral.
2. The `METADATA` citation is corrected from `:43` to `:44`, and the one-line-early
   citation is recorded as the supervisor's error in the brief, not a worker
   transcription fault.
3. The auditwheel SBOM claim is recorded as PROVENANCE, not as verified in sandbox:
   asserted from the earlier research report, which reported
   `dist-info/sboms/auditwheel.cdx.json` with zero `superlu` matches; not re-verifiable
   in this container; no SBOM json present in the installed dist-info. It rests on that
   report and on nothing else.
4. Section 5.6 row (ii) is M3 at 28,980 free edges, parameters `56/43/34-17-17`. The
   30,000-edge figure is an unmeasured architecture target with no mesh on disk.
5. The verdict table is relabelled to this exact wording: `1e-11` is PASS or FAIL,
   reported, not citable as validation or as port defect; `1e-8` is PASS or FAIL,
   binding, citable. Thresholds unmoved. Supersedes the Dispatch 42 labelling.
6. The Eigen licence is corrected from "BSD" to asserted MPL2, unverified, Eigen absent
   from environment.
7. The SuperLU licence is recorded as asserted BSD-3-Clause, not verifiable from this
   tree; notice not shipped in dist-info; obtaining and shipping the upstream notice is a
   prerequisite to ratification.
8. The metric-design rule from the T4_amp post-mortem: a convergence metric must be
   restricted to one homogeneous region and normalized within it. Applications: T4b
   passes because it is a normalized inner product on `strip_footprint`; T4c passes
   because it is an eigenvalue; T4_amp failed because it was a ratio over a mixed domain.
9. Superseded markers, one at the stale T4b sentence (Step 2a) and one in
   `sparse_eigenmode.md`, the second conditional on re-verification by content: if no
   such claim exists in that file, no marker is applied and the disagreement is referred
   back unresolved.
10. Forward pointer as the FINAL line of `decisions.md`: entries 8370 to 8390 and entries
    8392 to 8407 are both superseded; the last entry in this file is the operative one.
    The superseded ranges are named by content, not only by number.
11. A record that this corrigendum is the THIRD stack on entries 8370 to 8407, that the
    batching was deliberate, and that the purpose is to avoid a fourth.

## Task B's five questions

NOT TRANSMITTED. This brief (Dispatch 43b, Task A-close) does not contain Task B or its
five questions, and no earlier message in this session contains them. The heading is
recorded here so the artifact is not silently incomplete. If the five questions exist,
they must be supplied before Task B is opened; nothing in this dispatch authorises
guessing them.

## Corrections to the brief itself, already on the record

- The brief for Dispatch 43a placed the stale T4b sentence at `:511-512`; it is at the
  block opening `:516` with the claim sentence at `:518`. Supervisor's error, accepted.
- The brief cited `METADATA:43` for the bundled-software naming; the names follow line
  43 and the citation is corrected to `:44`. Supervisor's error, accepted.
- Standing rule adopted by the supervisor: no unverified line numbers in briefs; content
  citations only, worker resolves the lines.
