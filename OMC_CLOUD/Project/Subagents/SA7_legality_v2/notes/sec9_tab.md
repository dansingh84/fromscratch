## §9.2 (a) Completeness of the two-phase whole-step pass — 12 frames, both rates

`slices` = slices entering the pass (≥ 1 violating sample); `left after 1 / 2` = violating samples
remaining after one and two phase pairs, summed over the run.

| cell | bpp | slices | **closed ≤ 2 passes** | bad0 | left after 1 | left after 2 | moves | sign conflicts | **nocover** | guard fired | deepest before | deepest after |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| spotrobotL | 0.5 | 393 | **97 (25 %)** | 7,625 | **8,082** | **8,696** | 15,566 | 133 | **0** | 47 | 102 | **356** |
| spotrobotL | 1.0 | 277 | 126 (45 %) | 4,134 | 3,015 | 2,268 | 7,113 | 36 | **0** | 5 | 43 | 168 |
| volleyballgameL | 0.5 | 309 | **89 (29 %)** | 6,171 | 5,586 | **5,740** | 11,693 | 61 | **0** | 16 | 119 | **390** |
| volleyballgameL | 1.0 | 280 | 195 (70 %) | 2,756 | 1,318 | 767 | 4,065 | 9 | **0** | 0 | 82 | 165 |
| cf_gfx | 0.5 | 249 | 140 (56 %) | 934 | 594 | 543 | 1,453 | 10 | **0** | 85 | 307 | 382 |
| cf_gfx | 1.0 | 79 | 66 (84 %) | 121 | 38 | 20 | 158 | 0 | **0** | 2 | 141 | 87 |
| dng 1080p | 0.5 | 265 | 177 (67 %) | 1,197 | 542 | 340 | 1,739 | 0 | **0** | 2 | 163 | 203 |
| dng 1080p | 1.0 | 105 | 97 (92 %) | 194 | 37 | 10 | 231 | 0 | **0** | 0 | 69 | 26 |
| dng 720p | 0.5 | 310 | 143 (46 %) | 2,374 | 1,408 | 1,088 | 3,672 | 4 | **0** | 57 | 223 | 248 |
| dng 720p | 1.0 | 154 | 125 (81 %) | 444 | 152 | 59 | 596 | 0 | **0** | 0 | 75 | 29 |

## §9.3b (b) The residue against the bank

`escape bits` = the L-I19 within-bin escape at k = 2 on **those slices only**, positions as sorted
Elias-gamma deltas plus 2 value bits.

| cell | bpp | residue slices | **% of all slices** | escape coefficients p50/p90/max | escape **bits** p50/p90/max | **worst-slice bits as % of the slice budget** | **% of the 2× bank allowance used** |
|---|---|---|---|---|---|---|---|
| spotrobotL | 0.5 | 296 | **36.3 %** | 23 / 100 / 250 | 353 / 1,326 / 2,985 | 19.4 % | 19.4 % |
| spotrobotL | 1.0 | 151 | 18.5 % | 22 / 111 / 198 | 339 / 1,455 / 2,430 | 7.9 % | 7.9 % |
| volleyballgameL | 0.5 | 220 | 27.0 % | 39 / 109 / 311 | 570 / 1,432 / 3,615 | 23.5 % | 23.5 % |
| volleyballgameL | 1.0 | 85 | 10.4 % | 24 / 161 / 209 | 367 / 2,024 / 2,549 | 8.3 % | 8.3 % |
| cf_gfx | 0.5 | 109 | 28.4 % | 12 / 30 / 58 | 158 / 357 / 635 | **35.4 %** | 35.4 % |
| cf_gfx | 1.0 | 13 | **3.4 %** | 7 / 29 / 34 | 98 / 346 / 398 | 11.1 % | 11.1 % |
| dng 1080p | 0.5 | 88 | 10.8 % | 21 / 52 / 109 | 325 / 738 / 1,432 | 9.3 % | 9.3 % |
| dng 1080p | 1.0 | 8 | **1.0 %** | 20 / 39 / 56 | 311 / 570 / 789 | 2.6 % | 2.6 % |
| dng 720p | 0.5 | 167 | 15.5 % | 36 / 88 / 135 | 473 / 1,043 / 1,518 | 29.7 % | 29.7 % |
| dng 720p | 1.0 | 29 | **2.7 %** | 18 / 65 / 86 | 254 / 799 / 1,023 | 10.0 % | 10.0 % |

**The bank answer is unambiguous and it is a PASS.** The worst residue slice on any cell at any
rate needs **35.4 %** of its own slice budget in escape bits, against a normative allowance of
**100 %** (`wire_cap = 2 × slice_bytes`). The 608-bit floor for later slices is never approached
— the largest draw is 3,615 bits out of a 15,360-bit slice. **Whatever else fails, the cost shape
is one the CBR pipe can absorb.**

The residue **count** is the failure: the bar is ≤ 3 % of slices and the measurement is
**1.0 %–36.3 %**, met only on dng 1080p @1.0 (1.0 %), dng 720p @1.0 (2.7 %) and cf_gfx @1.0
(3.4 %, at the bar). At 0.5 bpp — the rate where legality is a problem at all — it is 10.8 % to
36.3 %.

## §9.6 (d) Quality at equal CBR, and the eye

The armed arm emits ordinary lattice points at the signalled plan, so this is a real stream at
exactly the same rate as the base (verified byte counts, §9.1).

| cell | bpp | ΔY | ΔCb | ΔCr |
|---|---|---|---|---|
| spotrobotL | 0.5 | **−0.911** | −0.014 | −0.015 |
| spotrobotL | 1.0 | −0.048 | −0.010 | +0.003 |
| volleyballgameL | 0.5 | **−0.997** | +0.004 | +0.028 |
| volleyballgameL | 1.0 | −0.085 | −0.005 | −0.016 |
| cf_gfx | 0.5 | −0.213 | −0.015 | −0.022 |
| cf_gfx | 1.0 | +0.021 | −0.002 | +0.006 |
| dng 1080p | 0.5 | −0.033 | −0.003 | −0.002 |
| dng 1080p | 1.0 | +0.002 | +0.001 | +0.002 |
| dng 720p | 0.5 | −0.116 | −0.003 | −0.003 |
| dng 720p | 1.0 | +0.008 | −0.002 | +0.000 |

**Chroma is untouched** (±0.03 dB everywhere — the pass only moves luma-plane and chroma-plane
detail coefficients that cover a violating sample, and chroma violations are rare). **Luma fails
the 0.1 dB bar at 0.5 bpp on four of five cells** and passes at 1.0 bpp on all five. The cost is
the forced whole-step move: where `round(need/step)` is 0 the pass must move a full step anyway.

**The eye** (`renders/{spot,dng720}_f8_2ph_{base,twophase}_{lvl,absdiff}_{Y,Cb,Cr}.png`, frame 8,
steady state, every plane, control-point and slice grid marked):

| | block-mean range (codes) | worst sample error |
|---|---|---|
| spotrobotL base | −37.0 … +18.4 | 190 |
| **spotrobotL two-phase** | **−285.2 … +278.1** | **450** |
| dng 720p base | −24.1 … +22.0 | 301 |
| dng 720p two-phase | −34.2 … +22.0 | 398 |

Looking at `spot_f8_2ph_twophase_lvl_Y.png` against the base: the base's three saturated streaks
become **a dozen or more**, several of them full-brightness red or blue bands running horizontally
across a third of the frame. **The whole-step pass manufactures a new and severe smudge class on
spotrobotL.** On dng 720p the change is much smaller and the maps are close. The error still traces
picture structure and shows no alignment with the 64-column grid or the slice grid.

## §9.7b (e) — note on what the renders show

The renders are of the **corrected, emitted** picture, not a model of one: the armed encoder writes
whole-step lattice points and the stream decodes to exactly what is rendered (`--recon − 2048`, the
identity verified over 3.69 M samples). No syntax was added to produce them.
