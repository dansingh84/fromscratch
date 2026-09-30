# What designer SA16 found ("CQP-1", Fable 5.1 trial): successes, failures, and HOW each came about

Coordinator, FINAL, 2026-09-29 04:50 EDT. Written from SA16's hand-in.

**Sandbox:** `Subagents/SA16_design/`. Read it; do NOT modify it.
- `DESIGN.md`: sections 1–8; the measured results are in §5.
- `RESUME.md`: the state, the bug ledger and the rejected list.
- Model in `model/`: `omc16.py` is the codec, `pyr2.py` the transform.
- Results in `out/`: `eval/`, `seq/`, and `tables/tables_p3.pkl`.

**Ledger:** S5.374–S5.375 and their addenda.

**Timeline and working basis.** SA16 worked 2026-09-28 18:50 → 2026-09-29 04:45, with two usage-limit stops. It followed the same brief after four earlier designers (see `MEMO_PRIOR_DESIGNERS.md` for SA12–14 and `MEMO_SA15_FINDINGS.md` for SA15). All numbers come from numpy models: static tANS tables trained on 5 clips disjoint from the test cells, REAL code lengths, exact CBR, compared against today's REAL decodes.

**Status:**
- **Stopped:** by the stall rule. SA16 itself declared goal 4 (efficiency) not met, and named root design choices as the cause.
- **Better than SA15:** loss recovery, mid-stream join, and memory.
- **Worse than SA15:** efficiency, still areas, and row phases.

Treat everything below as evidence and hints, not a design to continue.

---------------------------------------------------------------------------------------------------
## 1. The design (final)
- **Transform:** pair mean/difference pyramid (S-transform mean, difference predicted from means), 2V × 5H, 4-row blocks.
  - Two-sided predictors, with the coarse data of the next two blocks carried ahead.
  - HH predictors: causal HH2 plus in-block HH1, chosen for latency parity.
- **Legality:** an interval clamp of every leaf, computed from final values (SA15's mechanism). Legal by construction, canonical re-reading.
- **Temporal:** VALUE-domain prediction in the coefficient domain (today's principle), c = T(MC pred) + step·q.
  - History vectors D(t−1) vs D(t−2), TRANSMITTED per 64 × S block.
  - Bilinear OBMC, with the next slice's vectors carried ahead.
- **Refresh:** a COLUMN band of units per frame on an 8-frame cycle, plus one guard unit, so every slice carries a uniform intra fraction (about 15 % refresh units against today's 12.5 %).
- **Rate control:** one plan integer per slice from fixed open-loop lanes (octave lanes, then refinement lanes; one predetermined re-choice).
  - Plan-invariant, clamp-independent contexts, with tile significance flags.
  - One synthesis, then canonical emission: what a gen-2 encoder reads.
  - Step ladder derived from the measured synthesis gains, equal distortion per coefficient.

## 2. SUCCESSES, and how each came about
- **S1. Generation exactness.** Chain byte-identical (bits and pictures) for 3 generations × 6 frames on dng720; gen 2 identical at S = 8; 0 out-of-range everywhere.
  - How: SA15's leaf-interval legality, plus canonical emission from the final values, plus clamp-independent contexts.
  - Why clamp-independent: the decoder's clamp legitimately changes many zero-index coefficients in dark regions (207 of 1,280 in one LH1 band row of dng720). Magnitude-based neighbour contexts would therefore mis-state the decoder's bits, and a gen-2 encoder could fail a budget that gen 1 fitted.
- **S2. Mid-stream join: EXACT after one 8-frame cycle** (region r exact at phase r; bound ≤ 16 frames).
  - How: value-domain prediction with a column-band refresh and a clean-region barrier. A leak through T(x_p) across the barrier was found and fixed.
  - SA15 failed this; SA12 had a row-sweep variant.
- **S3. Loss recovery without a back channel: a lost slice was repaired in 15 frames,** with the damage bounded to rows 48–133. This meets A5 in the one test run; SA15 failed it (about 1,000 frames).
- **S4. Memory and latency.**
  - Latency: 18 lines at 720p (S = 4), 26 at 1080p+; 0.987 ms at 720p50 with 3:1 conversion, matching today's.
  - On-chip memory: 15.5 Mbit at 8K 4:2:2 10-bit and 24.2 at 8K 4:4:4 12-bit. Today's needs 29.2, and 8K 4:4:4 12-bit does not fit.
  - DDR: 20 bit/sample, against today's 26.
  - Work: decoder about 65 adds/sample (2× JPEG XS), encoder about 200 (5× XS), every branch fixed.
- **S5. Smudges:** smudgegroups 0 on every plane at every measured point; artifactmap 0/0/0 at @1.0 and on spot.
- **S6. No rate-control collapse:** the floor lane was used by 0 slices, and the coarsest octave lanes by ≤ 4 of 135 inter slices.
- **S7. Chroma:** equal to or better than today in PSNR; chroma flatness far better than today.
  - dng720 @0.5: flatplane Cb/Cr 23.4/51.5 % vs today's 82.8/83.3 %.
  - spot @0.5: 33.6/39.9 % vs 68.2/72.8 %.
- **S8. Fable's good process habits:**
  - rejected ideas on paper before building them (two refresh geometries that would create a special column or band);
  - measured and rejected its own causal-predictor plan (−0.8…−2.8 dB);
  - restated the HH choice in NEG when asked;
  - found the plan-weight defect by per-band error-energy analysis.

## 3. FAILURES, and how each came about
- **F1. Efficiency (goal 4): NOT met on VMAF-NEG.**
  - Valid points only, tables_p3; NEG mean (worst) / PSNR Y/Cb/Cr:

| point | SA16 | today | NEG difference |
|---|---|---|---|
| dng720 @0.5 | 84.33 (82.94) / 34.71/36.06/37.18 | 89.12 (87.22) / 35.22/36.10/37.14 | −4.8 |
| dng720 @1.0 | 90.08 (88.84) / 37.47/37.08/38.11 | 92.96 (92.31) / 38.19/37.08/37.95 | −2.9 |
| spot @0.5 | 89.03 (88.20) / 39.69/42.80/46.01 | 90.30 (85.37) / 39.35/42.76/46.24 | −1.3 (worst frame better) |

  - The other 9 points were not rerun; the 01:57 queue numbers are VOID (a plan-weight defect).
  - How it came about (SA16's own reading, measured):
    - (a) **The pair pyramid costs −0.53/−0.19/−0.19 dB (dng720) to −0.76/−0.66/−0.63 dB (bosphorus) against a plain 5/3** at matched entropy, with both using gain-normalised steps. This is the price of disjoint support, the very property that removes slice seams. **Conflict with SA15:** its round-1 T2 measured its 2/6 TS pair form within −0.11…−0.27 dB luma of 5/3. The two measurements differ in quantiser, entropy model and cells; the true transform price is unresolved.
    - (b) **The gain-derived, PSNR-optimal step ladder zeroes the level-1 (finest) bands at 0.5 bpp.** NEG punishes this more than PSNR does: luma flatness is 46 % against today's 42 %, and luma artifactmap regions at dng720 @0.5 are 30 against today's 15. Today's codec uses perceptual allocation tables and a texture rounding bias.
    - (c) About 15 % of units are refresh units, against today's 12.5 %.
  - **A defect found on the way (DO NOT REPEAT):** the first plan weights equalised TOTAL distortion per band instead of distortion per COEFFICIENT in the gain-normalised domain. The LL step came out about 1/2 of level 1 instead of about 1/11. That cost −5…−19 NEG and was mistaken for the design's efficiency until per-band error energies exposed it.
- **F2. Still areas: NOT met.** Still input converges over several frames, with 40–57 % of samples changing.
  - An exact-hold mechanism existed but was REMOVED: it was not gen-2 consistent, because after a clamp-heavy reference the held coefficients sit off every coarse lattice (Pu = 0, symbols at step 1, slice cost 10× the budget).
  - So refresh re-quantises still units once per cycle.
  - Mixed clip: shimmer 58/42 toward/away.
- **F3. Row phases: a 4-row block signature of 3–8 %** on the outer rows of every block. That is an order below today's 24 % spread but not identical statistics. SA15 reached a 0.4–2.3 % spread. By the owner's rule this is a design-created special row class; the likely source is the HH causal/in-block predictors and the two-blocks-ahead structure.
- **F4. Not done:** rails (cut24/ext10; the RAILS job failed on a comparison-arm code bug), formats other than 4:2:2 10-bit, renders of the valid runs, and the 9 remaining efficiency points.

## 4. Built and REJECTED by SA16 (with reasons)
1. All-causal predictors (for an exact column refresh): −0.8…−2.8 dB luma, −0.3…−0.9 chroma.
2. Two-sided horizontal predictor with a column sweep but no guard unit: the clean region's right edge reads a dirty mean → a special column during refresh.
3. Two-sided predictors with a ROW sweep: the top band at each cycle start gets no credit under the prefix bound → a coarser band once per cycle.
4. Lattice-locked prediction (SA15's): the root of SA15's failures.
5. Source-searched vectors: not reproducible at gen 2.
6. Dead-zone width as the sub-octave rate knob: kills texture. DZ 0.5: −0.6 dB.
7. Magnitude-based neighbour contexts: clamp-dependent, so gen 2 can fail the budget.
8. Closed-loop lanes (trial coding): forbidden.
9. Exact hold of the inter result: off-lattice after a clamp-heavy reference, cost 10× the budget.
10. Chroma-first priority: no change.
11. A perceptual tilt of the ladder was NOT tried (SA16 called it "a knob"). Note, though, that today's codec's perceptual allocation is part of its design, not a per-cell knob.

## 5. What the evidence of all five designers suggests (hints only)
- **Slice seams.** Disjoint-support pair pyramids remove seams (SA15: 0.4–2.3 % row spread). But the pair form may cost 0.1–0.8 dB against 5/3 (conflicting measurements). SA14's leaf-reading lifting kept the full 5/3 update with acyclic legality, within ±0.5 % BD-rate of 5/3, but its shifted causal slices created a first-row excess. Seam-freedom WITHOUT a transform price is still open.
- **Legality.** Leaf-interval clamps from final values: 0 out-of-range and exact (SA15, SA16). Open: rail-plate bit cost and "never away" (SA15). SA16 adds that contexts must be clamp-independent.
- **Temporal, exactness, join and loss.** Value-domain prediction with a column-band refresh, a guard unit and a clean-region barrier (SA16) gives an exact join within 16 frames and loss repair in 15 frames. Lattice lock (SA15) cannot. Open: still-area stability without an exact-hold that breaks gen 2.
- **Efficiency.** Only SA15 reached ≥ today on some points (3 of 12). Both SA15 and SA16 lost NEG through texture loss at the finest bands: SA15 from the lattice lock, SA16 from the PSNR-optimal allocation. A perceptual allocation that is canonical (derived by rule, the same at both ends) is not a patch, and today's codec has one.
