# §12. Loop iteration 7 — REFINE TOWARD THE TRUTH (L-I24, arm T), step 1 — verdict: **NO-GO, and the cause is arithmetic**

## §12.1 What was built

`ptree3`, `[SA7-T]` (`diffs/sa7_t.diff`), armed by `OMC_SA7T=1`, byte-inert unset (verified: dng 720p
12 frames byte-identical to the frozen base). One deterministic pass, no search, no contention:

1. reconstruct, census the violating samples;
2. **mark every coefficient whose support covers a violating sample** (bands `blo`…9, `blo = 4` by
   default, `OMC_SA7T_BLO=7` for level-1 only);
3. for each marked coefficient, the escape is the **k-bit within-bin value nearest the coefficient's
   true source-analysis value** — `r = e->coef[p][b][i] − (dequant(q,s) + pred)`, rounded to the
   nearest granule, clamped to the §7.1 bin window and to k bits. Every move is toward the source
   by construction;
4. one exact inverse, one re-census. `ESC_MAX = 512`, no fallback.

The lock argument is sound and I did not get to test it: at generation 2 the "truth" *is* the
committed coefficient (`lattice + escape`), so `r` is the escape itself and the same value is
re-derived. That remains untested because the arm never produced a stream to chain.

## §12.2 The measurement — it does not close, and it does not fit

dng 720p @0.5, 4 frames, sweeping k, marking bands 4…9:

| k | slices | closed | residual violating samples | escapes | **max marked/slice** | **max escapes/slice** | **ESC_MAX overflows** |
|---|---|---|---|---|---|---|---|
| 2 | 156 | 79 (51 %) | 1,465 of 2,636 (56 %) | 28,256 | — | 512 | **3,984** |
| 3 | 45 | 22 (49 %) | 1,125 of 1,676 (67 %) | 10,544 | — | 512 | **2,841** |
| 4 | 165 | 97 (59 %) | 601 of 2,077 (29 %) | 38,411 | — | 512 | **10,392** |
| 5 | 33 | 18 (55 %) | 62 of 309 (20 %) | 6,786 | **856** | 493 | 0 |
| 6 | 15 | 7 (47 %) | 298 of 528 (56 %) | 4,454 | — | 512 | 129 |

Level-1-only (`blo = 7`), the variant that should have the smallest covering set:

| k | closed | residual | **max marked/slice** | max escapes | overflows | encoder |
|---|---|---|---|---|---|---|
| 4 | 91/161 (57 %) | 1,341 of 2,411 (56 %) | **1,528** | 512 | **3,979** | **rc = 2** |
| 5 | 40/76 (53 %) | 296 of 690 (43 %) | **1,020** | 512 | **1,489** | **rc = 1** |

**On a 12-frame run at k = 5 the encoder fails outright** (`omc_enc: encode failed`, rc = 1).
The reason is in the arithmetic and it is not close:

| escapes in one slice | escape-list bits at k = 5 (5-bit value + ~13-bit position delta) | **as % of the 5,120-bit 720p @0.5 slice budget** |
|---|---|---|
| 428 | ≈ 7,704 | **150 %** |
| 475 | ≈ 8,550 | **167 %** |
| 493 | ≈ 8,874 | **173 %** |

**The escape list alone is 1.5–1.7× the whole slice budget before a single coefficient is coded**,
against a normative 2× wire cap — so nothing is left for the picture and the slice cannot be
emitted.

## §12.3 Why — the covering set is three orders of magnitude larger than the idea assumed

The rationale was that the ripple is the quantisation error of "exactly these coefficients", so
refining them is cheap and its footprint is negative. The first half is right; the second is not,
because of how many "these" are:

* a violating sample is covered by supports of **209–749 samples** in bands 4–6 and 27–45 in
  level 1, so each violating sample marks several coefficients in each of six bands;
* a slice with a few hundred violating samples therefore marks **856–1,528 coefficients**, even
  with the covering set restricted to level 1;
* refining all of them is not a correction, it is **a wholesale precision increase on a large
  fraction of the slice** — which is the whole-band rung of L-I19 arriving by another route, and
  the bank cannot fund it (`ESC_MAX` overflows by 3–20×, and the list outgrows the wire cap).

**The contrast with arm R is the result worth carrying forward.** Arm R refines the **18
coefficients per slice** its greedy selects and fits in ≤ 36 % of the slice budget with
`escover = 0`; arm T refines the **~1,000** that merely *cover* a violation and needs 150–173 % of
the budget for the list alone. **The selectivity of the search is what makes the escape
affordable.** Removing the assignment problem removes the thing that made the cost work.

The footprint half of the rationale could not be tested: with 47–59 % of slices closing and the
encoder failing on the longer runs, there is no artifact or PSNR comparison worth reporting, and I
am not reporting one.

## §12.4 Against the bar

| criterion | measured | verdict |
|---|---|---|
| zero residue on every cell at every rate | 47–59 % of slices closed; 20–67 % of violating samples left | **MISS** |
| `escover = 0` | **1,489–10,392 overflows** at every k but one | **MISS** |
| bank within cap | escape list alone **150–173 %** of the slice budget; **encoder fails** | **MISS** |
| artifacts ≤ base, PSNR, lock, cycles, renders | **not established** — the arm does not produce a usable stream | — |
| unarmed ≡ base; rt = 0 where a stream existed | both hold | PASS |

**Verdict: NO-GO**, on the first three criteria, with the cause measured rather than inferred. Arm J
was again not built; on this evidence its case is unchanged and its cluster sizes are the same few
samples × few atoms that arm R's residue defines.

## §12.5 Where this leaves the engine

Seven iterations have now bracketed the problem tightly, and the bracket is narrow:

* **arm R** (greedy selection, within-bin escapes): closes **100 %** of violating slices on
  dng 720p and **89 %** on spotrobotL, `escover = 0`, bank comfortable, `rt = 0`, legality 0 — but
  its 18 escapes per slice still cost **0.8 dB** and put a **152-code** dark band on the level map;
* **arm T** (no selection, refine every covering coefficient toward truth): the footprint would be
  negative by construction, but the covering set is ~1,000 coefficients and the cost is **1.5–1.7×
  the slice budget**;
* **arm J** (per-cluster minimum-norm joint solve) is the only untried point, and it is the one
  that is *selective like R* and *minimum-footprint like T* — the minimum-norm objective is exactly
  "the smallest total coefficient movement that clears the cluster", which is the footprint metric
  the level maps are measuring.

On the evidence, arm J is no longer one of two options; it is the only formulation left that can be
both affordable and quiet, and its cost — a few samples × a few atoms per cluster — is the one
number that decides the engine.
