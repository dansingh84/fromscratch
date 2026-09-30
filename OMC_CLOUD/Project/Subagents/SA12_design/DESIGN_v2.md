# CLP-1 — revision 2 (response to the coordinator's adversarial review)

**SA12, 2026-09-27.** This revision builds on `DESIGN.md` (revision 1). Everything in revision 1 that is not changed here stands.

The owner's current priority order governs this revision:

1. no seam lines or smudges;
2. a legal picture by construction;
3. byte-exact generations through both hop types;
4. not noticeably more bits than today's OMC for the same quality (VMAF-NEG first, every plane).

The half-rate mandate is not the acceptance bar at this stage.

**What is new in evidence.** Revision 1 judged every artifact on intra frames only. This revision adds a **sequence model**, `notes/seq.py`: the final legal pyramid, temporal prediction from one reference frame, canonical motion vectors, and rolling refresh. It is measured on steady-state **inter** frames 2–11 against **today's real decodes** (SA7 `out/DM/*_a0.d.yuv`, exact CBR) and against **JPEG XS** (SVT build `Agents/Agent3/tools/svtxs/Bin/Release`, best settings `--quantization 1 --rc 2 --slice-height 32`).

**Caveats that apply to every model number.** Rates are zeroth-order entropy estimates. The sequence model uses a fixed step per sequence, not CBR packets. It has no half-pel, no overlapped-block MC, no α field, and no refresh barrier.

---

## 1. Review items — findings, changes, measurements

### Item 4 — inter frames, still input, ants, refresh "twinkle" (measured)

**Defect found and fixed.** The first sequence run of revision 1's temporal predictor, on a truly still input (dng720 frame 0 repeated 12×), changed **73–84 % of samples every frame**. That is as bad as today's codec on the same test (S5.335: 60–77 %).

- **Cause.** The temporal term subtracted a spatial prediction computed with *extrapolation* for the reference but with *decoded-row context* for the current slice. A zero residual therefore did not reproduce the reference.
- **Fix (normative).** The reference's spatial prediction uses the *reference's own* rows above: the same rule applied to the motion-compensated reference (`seq.py`, `R['ctx']`).
- **Result.** When the input is still and the residual is zero, the prediction equals the reference exactly, by the bijection.

**Still input after the fix** (`out/v2/seq/fix_still_q6.*`):

| Measure | Result |
|---|---|
| Changed samples, every frame pair f1→f11 | **0.000 % Y / 0.000 % Cb / 0.000 % Cr**, including through refresh slices (1 in 8 slices refreshed intra each frame) |
| ants (owner's instrument) | 880/99/390 qualifying blocks; tail 0.00 %, boil 0.000 on every plane (source 0.00) |
| Bits | Inter slices ≈ 0; 0.146 bpp per frame = the refresh slices |
| Generation 2 | picture, indices and vectors identical |

**Why refresh does not "twinkle": the fixed point S5.335 asked for.**

- With identical steps, a still region's inter reconstruction never leaves the intra lattice: a zero residual keeps y = y_ref.
- Intra re-coding of the same source, with the same steps and the same (still) context rows, reproduces the same picture.
- So refresh changes nothing.
- Condition: the steps must not change between refreshes of a still region. §2.1 makes that canonical: the step is read from the picture, with a tie rule.

**Real moving input, dng720** (720p, **8-row slices**; the source changes 96 % of samples per frame, mean |Δ| 10–14 codes). Steady-state f2–11:

| | bpp | **VMAF-NEG** | PSNR mean Y/Cb/Cr | PSNR worst Y/Cb/Cr | flat % f8 Y/Cb/Cr | COR f8 Y/Cb/Cr | ants tail % Y/Cb (source 19.9/24.8) | smudge f8 |
|---|---|---|---|---|---|---|---|---|
| **today, real** | 0.500 (CBR) | **90.16** | 35.22/36.10/37.14 | 34.69/35.86/36.98 | 41.9/82.8/83.3 | .865/.290/.358 | 10.3/9.9 | 0/0/0 |
| CLP model, Qf 6 | 0.464 (max 0.62) | **91.70** | 37.46/36.38/37.55 | 37.36/36.35/37.54 | 37.0/55.9/70.8 | .922/.355/.425 | 4.7/1.6 | 0/0/0 |
| CLP model, Qf 6.5 | 0.422 (max 0.57) | **90.59** | 36.82/36.30/37.45 | 36.71/36.27/37.44 | 36.7/57.3/70.0 | .908/.347/.415 | 3.3/2.2 | 0/0/0 |

- For reference, XS on the same 12 frames: 72.11 NEG at 0.5 bpp, 89.31 at 1.0.
- Only 5 flat-and-static blocks qualify for ants here, so that column is weak evidence.
- The smudge tool finds **0 groups on today's real decode too**, so on these cells it does not discriminate. Smudge freedom is therefore argued from mechanism (no blend, no level shift), not from this tool.

**Real moving input, spotrobotL** (1080p, 16-row slices). Steady-state f2–11:

| | bpp | **VMAF-NEG** | PSNR mean Y/Cb/Cr | PSNR worst Y | flat % f8 Y/Cb/Cr | COR f8 Y/Cb/Cr | ants tail % Y/Cb/Cr (source 26.5/22.1/–) |
|---|---|---|---|---|---|---|---|
| **today, real** | 0.500 (CBR) | **93.76** | 39.54/42.80/46.31 | 36.51 | 48.0/65.1/69.0 | .849/.508/.442 | 5.2/6.7/4.5 |
| CLP model, Qf 6 | 0.383 (max 0.47) | 92.93 | 39.55/41.84/45.17 | 39.29 | 37.2/53.2/29.5 | .775/.407/.318 | 3.6/2.8/3.0 |
| CLP model, Qf 5.5 | 0.800 | 96.66 | 42.60/43.63/46.96 | 42.38 | — | — | — |
| CLP at 0.5, interpolated in log₂ bpp | 0.5 | **≈ 94.3** | ≈ 40.6 / **42.5** / **45.8** | — | — | — | — |

- XS on the same frames: 87.73 NEG at 0.5 bpp, 96.64 at 1.0.

**Reading (item 4 of the owner's list, efficiency).**

- VMAF-NEG: equal or better than today at the same or fewer bits on both cells.
- Luma PSNR: better. The worst frame is much better (spot worst-frame luma 39.3 at 0.38 bpp vs today's 36.5 at 0.5).
- Chroma PSNR: dng720 better. **spot ≈ −0.3/−0.5 dB Cb/Cr** at 0.5 bpp (interpolated). This is the chroma allocation; see item 2.
- Chroma flatness and COR are better on dng720; on spot flatness is better, while COR is lower at 38 % fewer bits.
- Nothing here yet compares at *exact* CBR with real tANS and headers. That is test T1.

**Refresh twinkle on moving content** has not been separately measured: moving content changes anyway. It is covered by the still-input result plus the steady-state PSNR rows (the spot worst frame is 0.3 dB below its mean, today's 3 dB).

### Item 3 — seams: cause found for one part, the other part equals today's (measured, not solved)

Two separate statistics:

**(a) Last-row error excess** (intra, spot/hwy, Qf 5 and 6; `out/v2/below_*.log`). Last-row error ÷ slice mean:

| Bottom context | Result |
|---|---|
| Linear extrapolation (revision 1) | 1.07–1.20 |
| **Oracle** (true rows below) | **0.89–1.02** |
| **Proxy** (co-located rows of the previous frame) | 1.02–1.07 |

- **Cause: the missing context below the slice.**
- **Change (normative).** In inter slices, the vertical predictor's two samples below the slice come from the lowpass of the **motion-compensated reference's rows below**. That data is canonical, legal-neutral and causal.
- In intra slices (frames 0–1, cuts, refresh) there is no reference and linear extrapolation stays.
- Inter model on dng720 after the other fixes (below-context not yet in `seq.py`): last-row ratio 1.05–1.08 vs today's 1.08–1.20.

**(b) Error step across the slice boundary.** Mean |e(y) − e(y−1)| at rows ≡ 0 mod 16, relative to all other rows; inter f2–11 (`notes/pitchseq.py`):

| spot, Y/Cb/Cr | slice boundary (p16+0) | internal coarse-pair boundary (p16+8) |
|---|---|---|
| **CLP** | 1.18/1.28/1.47 | 0.97/1.09/1.15 |
| **today** | 1.16/1.27/1.53 | 1.00/1.12/1.21 |
| **XS** (vertical transform across slices) | pitch16 = pitch32 = 1.02/1.12/1.22: the dyadic floor of any wavelet codec, not a seam | — |

- dng720 inter (8-row slices), v8: CLP 1.06/1.04/1.04 vs today 1.04/1.03/1.04.
- The slice-boundary excess over the internal boundary is **+0.21/+0.19/+0.32 for CLP and +0.16/+0.15/+0.32 for today**. So **CLP removes the mirror/blend seam mechanism but keeps a step of the same size as today's**.

**Cause (measured by elimination):**

- The oracle below-context does not remove it.
- Finer coarse steps reduce it only at large rate cost: Y 1.18 → 0.95 and Cr 1.47 → 1.26 at 2.3× rate (`ll_k5c2.log`).
- Inside a slice, the *difference* between the two coarse halves is itself a coded band (LH at level 3). Across a slice boundary, each slice's coarsest band is quantised independently. The cross-boundary error is therefore the difference of two independent errors, and larger.

**Root remedy — not measured; it is the first test of revision 3.** Make the cross-slice coarse difference a coded quantity, as it is inside a slice.

- Predict the coarsest band vertically from the lowpass of the decoded rows above.
- To stay loss-contained (A5), the prediction is **leaky**: weight ½ on the cross-slice term, ½ on the co-located temporal/zero term. A lost slice then decays ×½ per slice instead of propagating.
- An alternative, encoder-only and exactness-safe, is a boundary-continuity term in the two-candidate index choice for the coarse bands.

**This is the weakest point of the design against owner priority #1.**

### Item 2 — chroma flatness: cause identified (allocation), not a structural defect (measured)

Chroma level-1 step halved (`HF_CL1=0.5`; intra f8; `out/v2/cfl/`). Flatness % and COR, Cb/Cr:

| cell | today | CLP revision 1 | CLP, chroma level-1 step ½ | rate cost vs today |
|---|---|---|---|---|
| dng 0.5 | 82.9/85.7, COR .241/.296 | 89.9/88.2 | **19.1/50.4, COR .526/.491** | +27 % |
| hwy 1.0 | 58.7/45.1 | 60.9/49.9 | **44.3/8.5**, COR .632/.740 | +10 % |
| hwy 0.5 | 79.6/82.5 | 69.3/84.4 | **67.6/65.6** | +7 % |
| floor 1.0 | 41.8/46.7 | 42.2/48.6 | **7.0/9.2** | +21 % |

- **Cause.** The step rule (inherited from the record's estimator: steps from synthesis-energy weights, MSE-optimal) starves chroma level-1 in both structures. Chroma texture sits in exactly those bands. It is an allocation choice, not the pair highpass and not σ.
- The rate cost is only indicative: the model's power-of-two steps move in octaves, so the rate bisection could not land on target.
- On **inter** frames the chroma flatness of CLP is already below today's on both cells (item-4 tables), because the temporal residual frees chroma bits.
- **Change.** The per-band offset table o_b (revision 1 §2.7) is set by eye and the flatness instruments, not by the MSE weight. The chroma level-1 offset starts one octave finer than MSE (−4 quarter-octaves).
- The trade (rate vs luma NEG) is decided at matched *real* CBR (T1). It must not break item 4's "no more bits than today" guard.

### Item 1 — CBR guard: no empty path; fit by construction (design)

**What is removed.** The "coded empty" terminal of revision 1 §3.5 is removed. There is no code path in which a band is dropped.

**What replaces it** (per slice, one pass):

1. **Coarse groups.** Levels ≥ 2 and LL use step control p, chosen by open-loop cost lanes over the allowed range. Those lanes are parallel LUT sums, the same kind of computation as XS's own budget tables. The coarse groups are then coded closed-loop.
2. **Level 1** (the bulk of the bits) is quantised closed-loop in **parallel lanes** δ ∈ {0, +2, +4, +6, +8, +12} quarter-octaves.
   - All lanes share the same intervals and predictions: those depend only on final coarser values.
   - So each lane's cost is *exact*, not estimated.
   - The finest lane that fits the remaining bytes is emitted.
3. **Continuity.** δ is a control point of the continuous step field, interpolated vertically from the slice above, so there is no strip step.
4. **Second pass.** If the coarse groups alone overrun their share by more than the coarsest lane can absorb, the slice is re-coded once at p + (LUT of the overrun).
   - Worst case: one extra coarse-group pass, ≈ ¼ of the samples.
   - The number of times this happens on the corpus is test T4.

**What cannot be promised, stated plainly.** For any fixed-rate codec there are inputs whose information exceeds the pipe. Example: independent 12-bit noise in every sample at 0.5 bpp. On such inputs some texture is necessarily lost.

- That is a property of information, not of this design. JPEG XS loses bit-planes the same way.
- Constructive guarantees:
  - (i) no discrete fallback mode;
  - (ii) any loss is the same continuous step field, applied smoothly;
  - (iii) bounded work.
- On real content at ≥ 0.5 bpp the coarsest lane must never be needed. **That is measured, not constructed (T4)**, and I cannot honestly claim more.

### Item 5 — mid-stream join: every decision readable from the image (design)

Revision 1's rate control read a previous-frame record. That breaks a hop that joins mid-stream. The rule now:

> **The first encoder may use anything (source, history, lookahead-free statistics) to *choose*. Every decoder-visible parameter it emits must be *readable from the decoded picture*, and the emitted value is the one the reading rule returns on the encoder's own reconstruction.**

A later encoder, which has only the image, runs the same reading rule and gets the same value.

- **Step controls p and δ: coarsest-reproducing read.**
  - Rule: among the allowed values (at most one octave from the slice above, which is read first), take the coarsest for which every non-boundary coefficient value of the slice lies on its lattice. Boundary values are detectable (value = interval end), and K reproduces them at any step.
  - Divisibility by m·2^e is ctz plus residues mod 3/5/7, i.e. a LUT → a candidate mask per coefficient → AND over the slice → max. This is one pass, not a search.
  - Revision 1's nested-lattice argument shows that emitting the read value reproduces the reconstruction exactly and never costs more bits.
  - Tie rule for a slice whose residuals are all zero: keep the slice-above value. This matters for still regions and the refresh fixed point.
  - Slice 0 of a frame reads with a fixed default range. No state crosses frames.
- **Intra / inter per slice.**
  - Rule: the description that reproduces the slice with the fewest bits, ties → intra. Both are evaluated in the same pass: the target is v − p_spatial or v − p_spatial − temporal term, with a divisibility check.
  - This makes refresh slices *detectable* by a hop that joined mid-stream, which in turn gives it the refresh phase.
- **Vectors and α: derived from decoded pictures only.**
  - Frames t−1 and t−2, and the current slice's decoded coarse bands.
  - Previous-frame vectors are used only as a candidate, and are reset to zero in refreshed slices.
  - The block-matching window is restricted to the refreshed region during a cycle (the barrier).
- **Mid-stream convergence argument** (not measured):
  1. A joining hop detects gen-1's refresh slices by the intra read and codes them intra. They reproduce exactly.
  2. Refresh sweeps top to bottom, one slice per frame within each group (§2.9 of revision 1). A refreshed slice's context rows therefore come from a slice refreshed one frame earlier.
  3. With the barrier, the reference becomes identical region by region.
  4. Vector state resets per refresh.
  5. The joining hop becomes byte-exact within **one refresh cycle + 2 frames**. Until then it is one ordinary (non-accumulating) lossy generation.
  6. Test T8 must show this. It is the second-weakest point.

### Item 6 — efficiency against today's REAL decodes and XS (measured)

The item-4 tables give the like-for-like comparison: VMAF-NEG on steady-state frames, every plane.

- **Against today's real codec:** at equal or fewer bits, CLP (model) is ahead on NEG and luma on both cells, and ahead on chroma on dng720. It is ≈ 0.3–0.5 dB behind on spot chroma PSNR.
- **XS anchors** (12 frames, including frames 0–1):

| Cell | XS 0.5 | XS 1.0 | XS 2.0 | today real 0.5 | today real 1.0 |
|---|---|---|---|---|---|
| dng720 | 72.11 | 89.31 | 94.84 | 88.86 | 93.83 |
| spot | 87.73 | 96.64 | 98.84 | 93.47 | 97.55 |

- As instructed, no route to R = 2R is pursued. The numbers above are the record.

### Item 7 — 8K60 margin (design accounting)

**Datapath on DSP48E2 SIMD adders.** In ALU mode (TWO24 / FOUR12; adds and compares only, never multiplication), 1,728 DSPs give ≥ 3,456 adds per clock.

- The 8K60 encoder needs ≈ 855 ops per clock at 400 MHz: **≈ 25 % of DSP adder capacity**.
- LUTs then carry control, the tANS lanes, muxes and the divisibility LUTs: ≈ 45–55 k of 230 k (**≈ 20–24 %**).

**Canonical motion is specified hierarchically.** The model's full search (±8 full-res, 289 candidates) is a model convenience and not the design. The design:

- ±2 at quarter resolution (25 candidates on N_Y/16), then ±1 at full resolution (9 candidates): ≈ 21 ops per luma sample, as budgeted.
- The encoder-only reading rule adds ≈ 6 ops per sample.

**Result.** At 4K60, ≈ 6 % of DSPs and ≈ 7 % of LUTs; at 1080p, under 2 %. 8K60 at ≈ ¼ of the part is *comfortable*, but "large margin" is a judgement for the owner. 8K120 would take ≈ ½ of the part.

### Item 8 — records checked

- **Decoder-derived motion (S5.29 Design A)** failed A5 because derived state was never restored by a pixel refresh.
  - CLP transmits its vectors, so the decoder holds no state.
  - The encoder rule's only cross-frame state (previous vectors) is reset by refresh.
  - Why canonical motion is weaker than a source search: it matches *decoded* coarse or previous pictures, and "the vector's resolution is the information" (S5.29, Design C).
  - Measured here: 1/3–1/2 of the oracle gain in revision 1's probe. The sequence model still beats today's real decodes on NEG.
- **Refresh-barrier drift** (XSL.md: "loss-induced drift decayed but never cleared and crept one slice per refresh cycle", caused by cross-slice terms in refreshed slices).
  - CLP's cross-slice term is the context rows above.
  - The top-down refresh order guarantees a refreshed slice's context comes from a slice refreshed one frame earlier and kept clean by the barrier.
  - Loss probe: extra error exactly 0 from slice +3 on (revision 1 §2.9).
  - A multi-frame loss-and-recovery run is test T9.

---

## 2. Exactness and legality after the changes (measured)

- All changes keep revision 1's proofs.
  - The context fix, readable controls and below-context are deterministic functions of final or decoded data.
  - The guard lanes are encoder-only choices among lattice points.
- Sequence model: **0 out-of-range samples** in every run.
- **Generation 2 identical** (picture, every index, every derived vector):
  - still input (12 frames, through refresh);
  - graphics sequence (6 frames);
  - real moving dng720 (6 frames, 0 out-of-range): `fix_d720_g2` = picture, indices and vectors all identical.

---

## 3. Compliance: rows changed from revision 1

| Clause | Revision 2 status |
|---|---|
| A3 / G (seams) | Mirror/blend seam mechanisms absent. Last-row excess: cause found (below-context), fix specified. **Slice-boundary error step still equal to today's (measured): NOT MET, remedy specified, untested.** |
| A3 (ants / flicker) | **Still input converges to exactly zero change, including refresh (measured).** Real footage: ants tail below today on both cells. |
| A1 pipe | Guard with exact-cost level-1 lanes; no empty path. Content beyond pipe capacity degrades smoothly (information limit, stated). |
| A4 | Readable parameters; mid-stream convergence argued, **untested (T8)**. |
| Efficiency vs today (owner item 4) | **NEG ≥ today at ≤ today's bits on both cells (model).** Chroma PSNR −0.3/−0.5 dB on spot (allocation, item 2). Exact CBR comparison pending (T1). |
| C3 | 8K60 ≈ 25 % DSP / ≈ 22 % LUT |

---

## 4. Next tests (revision 3), in order

| Test | Content |
|---|---|
| **T0** | Seam root remedy: leaky cross-slice prediction of the coarsest band. Target: the p16+0 step equal to the internal p16+8 step, every plane, on inter frames. Also the encoder-only boundary-continuity index choice. Renders for the eye. |
| T1 | Exact-CBR sequence (real tANS, headers, guard lanes) vs today's real decodes at 0.5/1.0, 4 motion cells + dng + gfx, 4:2:2 and 4:4:4. NEG first, every plane. Chroma offset by eye. |
| T4 | Guard coarsest-lane / second-pass counts on the corpus, cut24 and extrema at 0.3–2 bpp. |
| T8 | Mid-stream join: a hop starting at frame 5 of a gen-1 decode reaches byte identity within one refresh cycle + 2 frames. |
| T9 | Multi-frame loss/recovery with the top-down refresh and barrier. |

---

## 5. Weakest point

**The slice-boundary error step is removed only as far as today's codec removes it.** The mirror and blend are gone and the last-row excess has a found cause, but the cross-slice step of the coarsest band remains (+0.2–0.3 over internal boundaries, per plane). By the owner's priority #1 this is not yet acceptable. Its root remedy (a leaky cross-slice coarse prediction) is specified but untested.

The second-weakest point: mid-stream-join exactness rests on an unmeasured convergence argument.

---

## Files (new in revision 2)

| File | Content |
|---|---|
| `notes/seq.py` | Sequence model |
| `notes/evalseq.py` | Steady-state battery: NEG, PSNR, ants, smudge, flatplane, texstat |
| `notes/pitchseq.py` | Seam statistics |
| `notes/below.py` | Below-context cause test |
| `notes/grid.py` | Now with `HF_CL1` / `HF_CL2` |
| `out/v2/seq/*.eval.json` | Inter evaluations |
| `out/v2/xs/xs.txt` | XS and today anchors |
| `out/v2/below_*.log`, `out/v2/ll_*.log` | Seam cause tests |
| `out/v2/cfl/` | Chroma allocation test |
