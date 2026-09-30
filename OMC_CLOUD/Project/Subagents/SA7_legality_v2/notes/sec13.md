# §13. Loop iteration 8 — the PER-CLUSTER MINIMUM-NORM JOINT SOLVE (L-I25, arm J), step 1

## §13.1 What was built

`ptree3`, `[SA7-J]` (`diffs/sa7_j.diff`), armed by `OMC_SA7J=1`, byte-inert unset (dng 720p 12
frames byte-identical to the frozen base).

* **cluster** = violating samples that share covering atoms, by union-find over the covering sets
  (bands 4–9, the same set that gives `nocover = 0`);
* **unknowns** = the displacements `d_a` of every atom covering the cluster;
* **constraints** = every cluster sample inside the rail with margin `m = 4` codes (the rounding
  reserve, `OMC_SA7J_M`), on the **exact local kernel** `latt_bas` (this codec's own inverse,
  measured by impulse, Q12);
* **objective** = min `Σ w_a d_a²`, `w_a = ‖g_b‖²` from `latt_g2[]` — a move charged by the picture
  change it makes, which is the quantity the level maps measure;
* **solver** = fixed-iteration projected gradient on the active constraints,
  `d_a ← d_a + (Σ_s g_a(s)·r_s / 4096) / ‖g_b‖²`, `N_iter` fixed (`OMC_SA7J_IT`, default 16), no
  data-dependent loop. **No division in the datapath**: `w_a` depends only on the **band**, so the
  ten reciprocals are a constant table (the probe divides in int64 for clarity; the table form is
  stated, not built);
* then quantise to k-bit within-bin escapes, verify by the exact inverse, **one second phase**,
  `ESC_MAX = 512`, no fallback.

**Provenance:** a fixed-iteration least-norm / projected-gradient solve is textbook (Landweber 1951,
Richardson 1910) — public-domain numerical analysis. The weights are this codec's own measured
basis energies. Nothing is taken from a named standard.

**A step-size defect found and fixed before any number was believed.** The first version diverged —
`left` grew from 1,118 to 3,569 to 5,872 — because the update mixed Q12 and code units and the
effective step was ~355× too large. Corrected to the form above; after the fix the solve converges
and `N_iter = 8` and `32` give the same closure, which is the check that it is converged rather
than truncated.

## §13.2 Cluster statistics — the number that decides the arm

dng 720p @0.5, 12 frames, k = 4, `N_iter = 8`:

| quantity | value |
|---|---|
| clusters per run | 1,390 over 335 slice-instances |
| **samples per cluster** | mean **2.5**, max **59** |
| **atoms per cluster** | mean **92**, max 512 (the array cap) |
| escapes per slice | mean ~43, **max 366** |
| `escover` | **0** |

**The clusters are tiny in samples and enormous in atoms.** 2.5 samples are covered by 92
coefficients, because a violating sample's covering set spans six bands with supports of 27–749
samples. Minimum-norm then spreads the correction over **all 92** — that is what minimum-norm
*means*. So the arm needs **366 escapes on its worst slice against arm R's 133**, for less than half
the closure.

## §13.3 Closure and legality

| | arm J (k = 4, it = 8) | arm R (k = 4) | base |
|---|---|---|---|
| slices closed, dng 720p @0.5, 12 frames | **150/335 = 45 %** | **326/326 = 100 %** | — |
| residual violating samples | 859 of 2,555 | 0 | — |
| `escover` | 0 | 0 | — |
| `rt = 0` with escapes live | **yes** | yes | — |
| committed samples out of range | **0** | 0 | 0 |
| shipped repair passes remaining | 922 | 671 | 211 |

`N_iter = 8` and `N_iter = 32` give identical closure (38 % on the 4-frame probe), so the 45 % is
the solver's converged answer, not an iteration cap.

## §13.4 The footprint — this is the result, and it splits

| dng 720p @0.5, 12 frames | dark blocks f0 (>20 / >40) | rest-of-run mean (>20 / >40) | worst >40 | **level-map block-mean range (Y, f8)** | worst sample error |
|---|---|---|---|---|---|
| frozen base | 90 / **3** | 4.2 / **0.2** | 13 | **−24.1 … +22.0** | 301 |
| **arm R** (100 % closed) | 131 / 4 | 12.5 / 3.7 | 40 | **−151.8 … +59.4** | 403 |
| **arm J** (45 % closed) | 93 / **26** | 6.9 / **1.7** | 19 | **−25.8 … +28.9** | 360 |

**The minimum-norm objective does exactly what it was chosen to do.** Arm R's correction put a
**152-code** dark band on the level map; arm J's worst block-mean is **28.9 codes**, against a base
of 22.0 — a **5× reduction in the correction's visible footprint**, and on the render the saturated
band arm R created is **gone**: the arm-J map is the base's ordinary quantisation texture, slightly
denser, with no saturated block anywhere. That is the first time in eight iterations that a
correction has been made without drawing a new artifact on the level map.

**But the footprint bar is still missed**, on the other counter: the dark 8×8 blocks deeper than
40 codes rise **3 → 26** at frame 0 and **0.2 → 1.7** across the run. The two counters disagree
because they measure different things — the level-map block is 2×32 and reports the *worst* error,
which arm J fixes; the dark-block counter is 8×8 and counts *how many* places are darkened, which
arm J makes worse because minimum-norm spreads its correction over 92 coefficients instead of
concentrating it in 18. **Spreading the error is what makes it invisible in the worst block and
visible in the count.**

Per-plane PSNR at equal window CBR: f0 31.37 vs base 31.43, f2 34.15 vs 34.69 — within 0.06 dB at
the worst frame and ~0.5 dB down in the body of the run, so the 0.1 dB bar is also missed.

Renders, unmarked and `_grid`, every plane, frame 8:
`renders/LI25_dng720_f8_armJ_{lvl,absdiff}_{Y,Cb,Cr}.png` (+ `_grid`), against
`renders/LI23_dng720_f8_{base,armR}_*`.

## §13.5 Against the bar

| criterion | measured | verdict |
|---|---|---|
| 100 % closure on every cell at every rate | **45 %** on the first cell | **MISS** |
| `escover = 0` | 0, max 366 of 512 | **PASS** |
| bank within cap | worst slice well inside the 2× allowance | **PASS** |
| footprint counters ≤ base, base's artifacts absent | level-map range **−25.8…+28.9 vs −24.1…+22.0** and **no saturated block** (arm R had −151.8); but dark > 40 **3 → 26** at f0 | **MISS on the dark-block counter, PASS on the level map** |
| no plane worse than 0.1 dB | ~0.5 dB down in the body of the run | **MISS** |
| lock reproducing the escapes | `rt = 0` with escapes live; the 8-generation chain not run (45 % closure leaves nothing worth chaining) | not established |
| cycles | `N_iter × samples × atoms` = 8 × 2.5 × 92 ≈ 1,840 multiply-free updates per cluster, 1,390 clusters per 335 slices ≈ 4 clusters/slice ≈ **7,400 updates/slice** ≈ 0.12 traversals at 1080p — **the solve is cheap**; the cost is the 366 escapes it must code | solve inside the period; bits are the constraint |

**Verdict: NO-GO.**

## §13.6 What the level maps show — and the conclusion the coordinator asked me to reach

The coordinator's contingency was: *if J cannot reach the footprint bar either, say what the level
maps show and stop.*

**What they show:** the correction's own footprint is now, for the first time, **invisible in the
level map** — arm J's worst block-mean error is 28.9 codes against the base's 22.0 and arm R's
151.8, and the saturated bands are gone. Minimum-norm is the right objective for *quietness*.

**What they also show:** quietness and affordability are in direct opposition in this engine, and
the opposition is structural rather than a tuning question. Three arms now bracket it exactly:

| | coefficients touched per slice | closure | worst block-mean |
|---|---|---|---|
| arm R (greedy, sparse) | **18** | **100 %** | **151.8** ✗ |
| arm J (minimum-norm) | **366** | 45 % | **28.9** ✓ |
| arm T (all covering, toward truth) | ~1,000 | 55 % | — (does not fit: 150–173 % of budget) |

**Sparsity buys closure and bits; spreading buys invisibility. The escape budget and the level map
pull in opposite directions**, and no objective over the detail coefficients alone gets both:
the correction needs ~100+ codes of picture movement somewhere, and it can either be concentrated
(one visible block) or spread (many small darkenings, more escapes, fewer slices closed).

On this evidence the residual cannot be paid out of the detail coefficients at a cost the slice
budget can carry **and** at a footprint the eye will not see. That is the conclusion the
coordinator reserved to himself, and I stop here with the three measurements that support it.
