# CLP-1 — revision 3 (response to the review of DESIGN_v2)

**SA12, 2026-09-27.** This revision builds on `DESIGN.md` (revision 1) and `DESIGN_v2.md` (revision 2). What is not changed here stands.

The goals follow the owner's current order:
1. no seam lines or smudges;
2. a legal picture by construction;
3. byte-exact generations through both hop types;
4. no noticeable bitrate increase over today's OMC, judged by VMAF-NEG first and then every plane.

**Evidence.** Everything comes from the sequence model `notes/seq.py`: the final legal pyramid, one reference frame, canonical vectors, rolling refresh, and now overlapped-block MC.
- Artifacts are judged on steady-state **inter** frames 2–11 with the owner's instruments.
- The comparison is against **today's real decodes** (SA7 `out/DM/*_a0`, exact CBR).
- Rates are the entropy estimate **×** a coder-overhead factor measured in §3. They are still a model, not a codec build.

---

## 1. Seams (priority #1) — the cause, located by elimination (measured)

**Statistic.** For inter frames 2–11, I take the mean |e(y) − e(y−1)| at the slice boundary and at the slice's internal half-height boundary, each relative to all other rows. The **excess** is the boundary figure minus the internal one. 0 means no seam; JPEG XS, whose vertical transform crosses slices, sits at ≈ 0.

**Elimination.** Intra frames, spotrobotL f8 (`out/v2/band/`, `out/v3/tall.log`):

| Test | Excess at the slice boundary | Conclusion |
|---|---|---|
| Any coarse band made lossless (LL, levels 5, 4, 3, level-3 LH) | +0.09 … +0.10 in every case | Revision-2 diagnosis ("independent quantisation of each slice's coarsest band") **falsified** |
| True rows below as context (oracle) | Does not remove it | Missing context below is not the cause |
| Same codec, one tall slice (no slice split) | **+0.01** (Y and chroma) | **The whole step is the causal slice split** |
| Same codec, 16-row slices | +0.16 / +0.18 | |

Interpretation:
- Inside a slice, a coarse sample's error spreads smoothly over neighbouring pairs on *both* sides, through the detail predictors.
- At a slice boundary, the bottom of slice k−1 was finalised before slice k existed, so the spread is cut. That is a block-boundary effect in the vertical direction.

**Inter frames had a second, larger component**, which the model had caused itself:
- The model used plain 16×16 motion blocks; the design (revision 1 §2.5) specifies overlapped blocks.
- The plain blocks made a **block grid in both directions**: horizontal 16-pitch excess **+0.162** in Y. That is a G1-type artifact of the model, not of the design.

**Measured on inter frames f2–11**, excess Y / Cb / Cr (`out/v3/`):

| spotrobotL (16-row slices) | coded bpp | PSNR Y/Cb/Cr | slice-boundary excess | horizontal 16-pitch excess (Y) |
|---|---|---|---|---|
| **today, real** | 0.50 | 39.54/42.80/46.31 | **+0.15 / +0.14 / +0.30** | −0.01 |
| model, plain blocks (revision 2) | 0.44 | 39.56/41.89/45.24 | +0.18 / +0.16 / +0.26 | **+0.162** |
| model + MC context below | 0.44 | — | +0.18 / +0.16 / +0.26 | — |
| model + context above *also* from the reference | 0.41 | 40.00/42.19/45.63 | +0.10 / +0.09 / +0.17 | — |
| **overlapped-block MC** (design) | 0.405 | 40.05/42.20/45.64 | **+0.07 / +0.06 / +0.11** | **−0.020** |
| **overlapped blocks + encoder error continuation** | 0.407 | 39.98/42.13/45.50 | **+0.04 / +0.03 / +0.06** | — |

- The "context above also from the reference" variant is worse than overlapped blocks alone and is dropped.
- dng720 (8-row slices), overlapped blocks: +0.05/+0.05/+0.04 vs today +0.05/+0.04/+0.05 (0.5 bpp) and +0.05/+0.06/+0.06 (1.0 bpp).

**New encoder element: error continuation (encoder-only, exactness-safe).**
- **Rule:** the encoder adds the previous slice's *low-frequency* reconstruction error to the target of this slice's top rows. The error is the mean of its last 2 rows, box-smoothed over 16 columns, and fades linearly over 8 rows.
- **Effect:** the error field continues across the boundary instead of being cut.
- **Cost:** −0.07/−0.08/−0.14 dB PSNR, no bits.
- **Why exactness is untouched:**
  - It only changes which lattice point the encoder picks.
  - At generation 2 the previous slice's error is 0, so the adjustment is 0.
  - Checked: generation-2 identity (picture, indices, vectors) holds with it on, in the final configuration (overlapped blocks + continuation + MC context below, `out/v3/final_g2`) and without overlapped blocks (`d720c8`).

**What remains:**
- **Inter frames:** +0.04/+0.03/+0.06 on spot, against today's +0.15/+0.14/+0.30.
- **Intra slices:** +0.14 on luma (frame 0, refresh slices, cuts). Neither context below nor error continuation applies there without making refresh depend on the reference.
- **Status:** this is lower than today's on every plane, but **not zero**. Whether it is visible is for the owner's eye, and **it is the weakest point** (§6).

**Bracketed slices (S5.362, SA13), judged against this evidence.**
- The tall-slice test shows the step comes from the causal cut, not from any band.
- Bracketing gives both sides of a boundary a shared, already-decoded anchor row, so it attacks the right cause.
- Two costs for this design:
  1. **Legality.** SA13's interior uses 5/3 *with* an update between anchors, which is not legal by construction in my framework. A legal version within my pair pyramid would treat the anchor as a known sample: the last pair's detail is derived rather than transmitted, and the box of its pair-sum becomes anchor + [lo, hi]. That fits my interval rules and stays acyclic, but the coding gain of the interior is unmeasured.
  2. **Rate.** It adds a 1-D coded row per slice.
- I did not build it. **Next test (T0):** the anchor-bracketed pair pyramid, **on intra slices only** (where the remaining step lives), against the +0.14 excess.
- A5: bracketing uses only the slice above's anchor, one row, so damage stops after one slice. That contains loss.

## 2. Chroma flatness at no more bits than today (measured, intra f8)

**What cannot work.** Reallocating *within* chroma cannot pay for finer level-1 steps: chroma coarse bands hold too few bits (`out/v3/cfleq_*.log`).

**What works.** Reshaping the chroma level-1 quantiser:
- the step ×√2 is a normative band offset;
- the encoder rounding offset 11/16 is an encoder-only dead-zone choice, lattice-safe (a lattice point still maps to its own index).

The result: faint chroma texture survives at nearly the same chroma bits (`out/v3/cfth_*.log`). Luma is untouched throughout.

| cell | codec | bpp | VMAF-NEG | PSNR Y/Cb/Cr | flat % Y/Cb/Cr | COR Cb/Cr |
|---|---|---|---|---|---|---|
| dng 0.5 | today (model) | 0.522 | 83.69 | 34.71/34.22/35.47 | 60.8/82.9/85.7 | .241/.296 |
| | CLP revision 2 | 0.479 | 84.35 | 34.65/34.24/35.47 | 59.3/89.9/88.2 | .198/.275 |
| | **CLP + chroma reshape** | **0.505** | **84.35** | 34.65/33.73/35.02 | 59.3/**65.7**/**80.9** | **.280/.316** |
| hwy 1.0 | today (model) | 0.942 | 92.84 | 44.16/49.01/45.78 | 24.5/58.7/45.1 | .531/.601 |
| | CLP revision 2 | 0.852 | 93.41 | 44.06/48.96/45.68 | 24.3/57.0/50.3 | .521/.575 |
| | **CLP + chroma reshape** | **0.883** | **93.41** | 44.06/48.40/44.50 | 24.3/**56.2**/**40.1** | .524/.590 |

- **Reading.** Chroma flatness and COR are now better than today's structure at *fewer* bits than today on both cells. NEG is higher.
- **The price** is chroma PSNR (−0.5 dB Cb and −0.45 dB Cr on dng; −1.3 dB Cr on hwy). PSNR is a diagnostic, but the owner should see this trade.
- **Scope.** Intra only. On **inter** frames CLP's chroma flatness was already below today's without the reshape (item-3 table below; revision 2). The reshape is specified for intra slices (ramp, cut and refresh). On inter slices it is off until measured there.

## 3. Coder fairness: model rate → coded rate (measured on the model's symbols)

Real static tANS is modelled by a normative **family of 64 tables** per band (P(0) × geometric decay):
- the encoder picks one table per band per slice and pays 6 bits for it;
- there are no contexts (conservative);
- escapes use Exp-Golomb;
- each slice pays 8 bytes of header plus 4 lane flushes × 2 bytes.

Model: `notes/cost2.py`; the tANS code length is within ≈ 0.5 % of the ideal.

| run | entropy bpp | table mismatch | + headers and table indices |
|---|---|---|---|
| dng720, Qf 6 (0.45) | 0.450 | ×1.059 | **×1.134** → 0.510 |
| dng720, Qf 6.5 | 0.409 | ×1.077 | ×1.159 → 0.474 |
| dng720, Qf 5 (1.65) | 1.648 | ×1.022 | ×1.043 → 1.718 |
| spot, Qf 6 (0.35) | 0.352 | ×1.119 | ×1.151 → 0.405 |
| spot, Qf 5.5 | 0.736 | ×1.054 | ×1.070 → 0.787 |

Every rate below is the **coded** figure.

**Efficiency against today's real decodes, inter f2–11, interpolated in log₂(bpp) to today's 0.5 bpp:**

| cell | | coded bpp | **VMAF-NEG** | PSNR Y/Cb/Cr | flat % f8 Y/Cb/Cr | COR f8 Y/Cb/Cr | ants tail % Y/Cb (source) |
|---|---|---|---|---|---|---|---|
| dng720 (8-row) | today, real | 0.500 | **90.16** | 35.22/36.10/37.14 | 41.9/82.8/83.3 | .865/.290/.358 | 10.3/9.9 (19.9/24.8) |
| | CLP, Qf 6.5 | 0.474 | 90.52 | 36.89/36.29/37.46 | 36.8/53.3/69.9 | .909/.346/.41 | 4.5/2.2 |
| | CLP, Qf 6 | 0.510 | 91.64 | 37.51/36.37/37.56 | 37.2/53.6/70.8 | .923/.355/.42 | 4.8/1.5 |
| | **CLP @ 0.5** | 0.500 | **≈ 91.3** | ≈ 37.34/36.35/37.53 | | | |
| spot (16-row) | today, real | 0.500 | **93.76** | 39.54/42.80/46.31 | 48.0/65.1/69.0 | .849/.508/.442 | 5.2/6.7 (26.5/22.1) |
| | CLP, Qf 6 | 0.405 | 92.88 | 40.05/42.20/45.64 | 50.0/66.3/55.3 | .810/.453/.37 | 2.1/1.5 |
| | CLP, Qf 5.5 | 0.787 | 96.58 | 42.92/43.91/47.32 | 33.9/39.2/43.9 | .884/.593/.49 | 1.3/2.5 |
| | **CLP @ 0.5** | 0.500 | **≈ 94.05** | ≈ 40.96/42.74/46.17 | | | |

- dng720 at 1.0 bpp: CLP at Qf 5 is 1.72 bpp (NEG 95.28), against today at 1.0 (NEG 93.83). The 1.0-bpp point was not bracketed; test T1.
- **Owner goal 4 (no noticeable bitrate increase).** At equal coded bits NEG is ahead on both cells (+1.1 and +0.3). Luma is ahead (+2.1 and +1.4 dB). Chroma is ahead on dng720 and at parity on spot (−0.06/−0.14 dB).
- **Still model numbers.** The real-codec confirmation is T1.

## 4. Smudges on the owner's marked material (measured)

Setup:
- **Material:** S3.19 (87 owner boxes, `owner_boxes.json`, the 720p cell, frame 2 by his marking) and S3.24 (the nine grille boxes: 8×8 block means of decode − source, bright > +10 / > +20, dark < −10 / < −20).
- **Frames:** 2 (the marked frame, steady state by the ramp rule), 8 and 11.
- **Tool:** his `ownerboxes.py` unchanged.

| decode | coded bpp | grille luma \|err\| | grille HP ratio / corr | rest luma \|err\| | chroma \|err\| grille / rest |
|---|---|---|---|---|---|
| **today, real 0.5** | 0.50 | **34.6** | 0.79 / 0.66 | 12.1 | 11.8 / 12.8 |
| today, real 1.0 | 1.00 | 19.1 | 0.93 / 0.85 | 9.3 | 11.2 / 11.5 |
| **CLP, Qf 6** | 0.51 | **15.7** | **0.98 / 0.92** | 10.1 | 11.5 / 12.0 |
| CLP, Qf 6.5 | 0.47 | 19.1 | 0.93 / 0.85 | 10.6 | 11.6 / 12.2 |
| CLP, Qf 5 | 1.72 | 8.3 | 0.95 / 0.98 | 7.6 | 8.2 / 8.5 |

Grille bright/dark classes (S3.24 method), % of 8×8 blocks in the nine boxes:

| decode | f2 bright >+10 / >+20 | f2 dark <−10 / <−20 | f8 | f11 |
|---|---|---|---|---|
| **today, real 0.5** | **12.9 / 3.0** | **13.9 / 2.0** | dark 3.0 / 0 | bright 6.9 / 1.0; dark 8.9 / 1.0 |
| today, real 1.0 | 0 / 0 | 0 / 0 | 0 | bright 3.0 / 0 |
| **CLP, Qf 6 and Qf 6.5** | **0 / 0** | **0 / 0** | **0** | **0** |

**Reading.** In the boxes the owner confirmed as smudges, today's 0.5-bpp decode has 13–14 % of blocks shifted by more than 10 codes at frame 2. CLP at the same or lower rate has none at any measured frame. It matches or beats today's 1.0-bpp decode at half that rate. Mechanism: no blend, no level-shifting edit, no clip or repair.

## 5. Mid-stream join (T8, measured)

**Run 1: revision-2 model as it stood.** Interleaved refresh, derived vectors from t−1/t−2, no barrier.
- Joins at frames 3, 5 and 7 of a 20-frame spotrobotL gen-1 decode.
- The joining encoder reproduced only slice 0, and only at frames 8 and 16. **The argued convergence did not happen.**
- **Cause:** a refreshed slice at gen 1 is reproduced by the joiner only if its context rows above have converged. At the next frame, inter coding of that slice reads vectors derived from, and a reference region extending into, slices the joiner has not converged on.

**Run 2: mechanism test.** Contiguous top-down refresh sweep (1/8 of the frame per frame, cycle 8), zero vectors, no context from below, and the "intra iff intra reproduces" read at the joiner. Measured on spotrobotL 1080p, 20 frames: the joiner's decoded pictures against gen 1's, counting slices identical out of 68 (`out/v3/k_*`).

| Joins at | Frames after joining, slices identical per frame | Every sample of every plane identical from |
|---|---|---|
| frame 3 | 35, 45, 55, 55, 55, 59, 64 | **frame 10** (7 frames after joining) |
| frame 5 | 31, 31, 31, 36, 41, 49, 58 | **frame 12** (7 frames) |
| frame 7 | 23, 28, 33, 41, 50, 59 | **frame 13** (6 frames) |

- All joins lock within **one refresh cycle (8 frames)** and stay locked to the last frame.
- Stream identity after lock follows from identical pictures plus identical read/derived decisions. A direct byte comparison of the two streams was not run.
- **Still open:** the same with canonical motion vectors and context from below, which requires the clean-region rules below to be modelled.

**Design consequence (normative):**
- The refresh is a contiguous top-down sweep.
- During a cycle, everything a slice inside the refreshed region reads must come from inside that region: context rows, the reference region for MC (the barrier), the reference rows below, and the data the canonical vector rule derives from.
- The vector rule therefore uses only frame t−1 and the current slice's decoded coarse bands, never t−2.

With those rules the joiner's state inside the refreshed region is a function of data identical at both encoders, so it converges region by region.

## 6. Status against the owner's list, and the weakest point

| Goal | Status (model) |
|---|---|
| 1. No seams or smudges | **Smudges:** 0 % grille level classes vs today's 13–14 %; smudge groups 0; owner-box error halved. **Seams:** slice-boundary excess below today's on every plane — inter +0.04/+0.03/+0.06 vs today +0.15/+0.14/+0.30; intra slices +0.14 (≈ today's). Block grid removed by overlapped-block MC. **Not zero: eye decides.** |
| 2. Legal by construction | Holds (revisions 1–2); 0 out-of-range in every run of this revision |
| 3. Byte-exact generations | Generation-2 identity (picture, indices, vectors) on still, graphics and moving dng720, with overlapped blocks and error continuation. Mid-stream join: **picture-identical within one refresh cycle (6–7 frames) with the contiguous sweep, measured with zero vectors**; with vectors, the clean-region rules are specified but not modelled |
| 4. No more bits than today | At equal coded bits NEG +0.3…+1.1, luma +1.4…+2.1 dB, chroma parity to +0.4 dB. Chroma flatness fixed at no more bits than today (intra reshape); already better on inter. |

**Weakest point.** The residual slice-boundary error step, **+0.14 on intra slices** (≈ today's) and +0.03–0.06 on inter slices. Its cause is now proven: the causal cut (tall-slice test +0.01). The remaining remedy for intra slices, a legal anchor-bracketed pyramid in the spirit of S5.362, is specified but unmeasured.

Second: mid-stream-join exactness with motion (§5) still depends on the clean-region rules, which are specified but not yet modelled with vectors.

## 7. Files (new in revision 3)

- `notes/seq.py`, now with:
  - overlapped-block MC (`SEQ_OBMC`);
  - context below from the MC reference (`SEQ_BELOW`);
  - encoder error continuation (`SEQ_CONT`, `SEQ_CBW`);
  - the read mode for a joining encoder (`SEQ_READ`);
  - contiguous sweep (`SEQ_SWEEP`) and zero vectors (`SEQ_ZEROMV`);
  - a symbol-histogram dump.
- `notes/cost2.py`: the coder model.
- `notes/cfleq.py`: chroma allocation and reshape.
- `notes/pitch2.py`: seam excess statistic.
- `notes/below.py`: now with band-lossless attribution.
- `out/v3/*.log`, `out/v3/*.eval.json`, `out/v2/band/`, `out/v3/tall.log`.
