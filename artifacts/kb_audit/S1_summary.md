# S1 — Summary of the knowledge-base audit

**Scope.** 170 text files / 4,308,072 B (of 218 files / 12,753,536 B under `docs/`).
Read-only throughout.

**The corpus is not disorganised — it is unindexed, and one document it depends on is
missing.** A session today must read 78,110 B to be safe, 95.3% over a 40 kB budget.

1. **Lifecycle, not topic, is the split.** 3 CORE (47,132 B), 8 REGISTRY (595,728 B,
   header-counted), 9 WORK, 5 UNCERTAIN, 60 REFERENCE (26.0%), 85 ARCHIVE (50.4%).
   Zero deletions proposed. `S5_classification.tsv` holds all 170 rows.
2. **Header discipline is 27/170 (15.9%)**, and it is 0/3 in CORE and 0/8 in REGISTRY —
   the two classes a reader is meant to trust. S3 finds 5 Grade-A self-contradicting
   files and 3 headerless ones.
3. **The real phantom is a *successor*, not a symbol.** `docs/design/decisions.md` does
   not exist but is referenced 585 times across 63 files, and 7+ banners name it as the
   successor; `PREREG.md`/`NOTE.md` add 86 refs. By contrast, **zero** of 170 files
   asserts any of STATE.json's three rejected ghosts as fact (S3c) — the ghost list
   passes and the successor check fails.
4. **ARCHIVE is load-bearing:** 82 of 85 archive-class files still have inbound
   citations (330 total). Renaming into `docs/kb/` breaks all 1,010 already-dangling
   citations at once unless a redirect map ships in the same commit.
5. **Reorganisation alone cannot meet the budget.** As-is counted total is 60,502 B
   (51% over); optimistically 53,702 B (34% over). CORE must be *distilled*, and
   `STATE.json` (12,838 B) must sit outside the budget or the arithmetic fails outright.
6. **Recommendation:** six steps that only create files — README + 4 CORE, a
   reconstructed `REGISTRY/decisions.md`, defects/ghosts headers, generated
   `WORK/current.md` — then headers, then the redirect map, then moves. Eight standing
   tests, each with its own documented false positive.
