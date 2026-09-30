# SA17 design — "CPV-1" (Continuous Pair pyramid, Value-domain prediction)

Status 2026-09-29, evening. All figures come from the numpy model in `model/`: real code lengths from static
tANS tables trained on 5 clips disjoint from every test cell, exact CBR, full frames, compared against today's
REAL decodes (frames 2–11 = steady state). PROXY = entropy proxy, screening only. PAPER = argument, not measured.

**Verdict in one line.** Goals 1 (seams/smudges) and 3 (exactness, join by reading, loss < 4 frames) are met in
the measurements; goal 2 is met for legality and cost but NOT for "never away" (the legaliser moves some partner
samples away from the source, proven structural for any exact lowpass design — §3); goal 4 is NOT met: VMAF-NEG
is below today on 8 of 12 points (−0.4 … −1.2), above on 4.

---------------------------------------------------------------------------------------------------------------
## 0. Root-cause chain that fixed each choice

| Goal | Root cause found | Choice it forces | Evidence |
|---|---|---|---|
| 1 seams | a slice that is a closed transform unit gives its edge rows one-sided support | transform continuous over the whole frame; a slice is only a rate/packet unit | today's rowphase dng720 @0.5 (owner tool, sh=S): Y 4.6 / Cb 20.5 / Cr 18.1 % |
| 1 (2nd order) | a continuous dyadic 5/3 still treats even (updated) and odd (predicted) rows differently | vertical split = symmetric PAIR (both rows of a pair are mirror images) | E1 PROXY: dng720 row spread 5/3 2.3/15.4/14.6 % vs pair 0.3/0.5/1.7 % |
| 2+3 | with an UPDATE step, a clipped sample's lost overshoot is read by the lowpass; a re-encoder cannot recover it | every output pair written LAST from a final mean and a leaf read by nothing else; legality = interval clamp of that leaf; index = smallest magnitude that reproduces | E2: 5/3 + clip + reading: 18–282 index mismatches, 820–24 769 differing pixels on cut24/ext10 |
| same | per-sample leaves (predict-only) would make a plain clip exact | rejected | E1d PROXY +12…60 % bits |
| 4 (transform) | is the pair costing bits? | kept: at REAL code lengths the pair equals 5/3 | EV-B: 5/3 backend (not legal, not exact) hwy 91.47 / floor 93.88 vs pair 91.69 / 93.65 NEG @0.5 |
| 4 (entropy) | tables pooled over all step sizes | tables keyed by (plane class, band group, inter/intra, step bucket) | ENT1: pooled tables +47.8 % class bits over per-band empirical on a training clip |
| 4 (refresh) | a rolling wave costs 0.8–1.0 NEG | owner ruling: on-demand heal over the return path is primary; a wave exists only for one-way links | EV-B |
| still areas | exact CBR spends every bit; with nothing to code, still content is re-refined every frame; history vectors read refinement as motion | one refinement per still coefficient then hold (encoder-only), padding; zero-vector tolerance 2 codes/pixel | §7 |

---------------------------------------------------------------------------------------------------------------
## 1. Encode and decode path (normative unless marked "encoder")

### 1.1 Transform — continuous pair pyramid
- Per plane, 2 "quad" levels then 3 horizontal pair levels (2V × 5H), over the WHOLE picture. Mirror extension only
  at picture edges; slices never close the transform.
- Pair step (both axes): S-transform `m = (a + b + π) >> 1`, `d = a − b`, with position-parity rounding π
  (unbiased: removes the +1-code cast class). The difference is predicted from the neighbouring FINAL means
  (2/6 slope): `leaf = d − ((m[−1] − m[+1] + 1 + π') >> 2)`.
- Quad level ℓ: vertical pair → mean row VM, difference row VD; horizontal pairs of VM → (LL, HL leaf),
  of VD → (LH mean-leaf, HH leaf); HH predicted from the vertical slope of HL and the horizontal slope of LH
  (`(ΔHL + ΔLH + 3 + π) >> 3`). Synthesis order (all reads final values): LL → HL → VM → LH → HH → VD → pixel pairs.
- Every leaf is read by nothing but its own pair: this is what makes legality exact (§3).

### 1.2 Quantiser, plan ladder, rate control (exact CBR)
- Lattice: leaf value = base + q·2^e (base: 0 intra; left final LL for intra LL DPCM; the prediction's leaf for
  inter). Nothing else normative. Encoder dead zone ρ = 0.35 (floor(|r|/s + 0.35)).
- Plan ladder: M = 30 (plane, band) exponents; plan k raises exactly one band exponent by 1 per step, in an order
  fixed by the synthesis gains plus a tilt of 0.25 octave per level toward finer fine bands (tuned on training
  clips only: traffic @0.5 +1.0 NEG vs no tilt). Lattices are NESTED (dyadic), so any value read at plan k is on
  every finer plan's lattice.
- One decision per slice: all 16 exponents' code lengths per band are computed in parallel from open-loop
  symbols; the finest plan that fits `B + credit − header − 16` is taken. The 16-bit reserve covers the canonical
  emission (measured excess at most 5.5 bits on 1 slice in 180); with it every measured run has 0 prefix
  violations. Unused bits are carried as credit; bits the content does not need are padding.
- Emission: after synthesis the encoder emits the canonical READING of its own picture (coarsest consistent
  plan, smallest-magnitude indices) — one fixed second pass, no search, no iteration.

### 1.3 Entropy coding
- Per leaf: magnitude class (0; 1 + ⌊log2|q|⌋) coded with static tANS (L = 1024), context = (left + above class)
  within the slice (above cut at the slice top: packets are independent), then raw mantissa bits and a sign bit.
- Tables: (luma / chroma) × 8 band groups × (intra / inter) × 3 step buckets (e ≤ 2, 3–4, ≥ 5) × 4 contexts.
  Contexts use INDICES only, so they are independent of the decoder's clamps (a re-encoder computes the same bits).

### 1.4 Temporal prediction
- One reference: D(t−1). Prediction P = OBMC (bilinear block-centre weights, 4-bit, shift 8) of D(t−1) with integer
  vectors per 64 × 8 luma block (4:2:2 chroma: half-sample by a 2-tap average).
- Vectors are DERIVED by every encoder from decoded history (block match of D(t−1) against D(t−2), ±16 × ±4,
  row-wise regularised toward the left vector, zero unless motion explains the block better by > 2 codes per
  pixel) and TRANSMITTED (Exp-Golomb differences). The decoder never derives (S5.29).
- Value-domain coefficient prediction: inter leaf value = leaf of T(P) + q·2^e (texture carried at full
  precision; SA15's lattice lock is not used).

### 1.5 Slices and packets, latency
- A slice is S rows (4 at 720p, 8 above), one packet, one plan. Because slice k's pairs read the final means of the
  blocks below, packet k also carries the level-2 leaves of the next block and the coarse leaves two blocks ahead
  (a packing order, PAPER — the model is frame-level).

### 1.6 Loss resilience and refresh — two modes
- Return path (primary): per-slice loss flags; on-demand heal (§6.1). No scheduled refresh at all.
- One-way links: a column wave of cycle 2 (§6.2).

### 1.7 Legality: §3. Resolution conversion: unchanged from today (outside the codec core).

---------------------------------------------------------------------------------------------------------------
## 2. Measured efficiency — on-demand mode (no scheduled wave), against today's REAL decodes

Frames 2–11, NEG mean (worst frame) then PSNR Y/Cb/Cr (dB). Tables `out/tab_eb_r2.pkl`; config tilt 0.25, ρ 0.35,
64-column blocks, λ 4, still-hold on, reserve 16 bits. Every run: max frame bits/target ≤ 1.0000, 0 prefix
violations, 0 out-of-range samples. (`out/eval_final.log`, `out/eval/final_*.json`, decodes `out/dec/final_*`.)

| cell @bpp | SA17 NEG (worst) | today NEG (worst) | ΔNEG | SA17 PSNR Y/Cb/Cr | today PSNR Y/Cb/Cr |
|---|---|---|---|---|---|
| dng720 @0.5 | 88.97 (88.10) | 90.16 (87.22) | −1.19 | 34.43/36.12/37.22 | 35.22/36.10/37.14 |
| dng720 @1.0 | 94.25 (93.17) | 94.05 (92.31) | +0.20 | 38.43/37.01/38.27 | 38.19/37.08/37.95 |
| dng1080 @0.5 | 90.25 (88.56) | 91.08 (87.51) | −0.83 | 35.05/34.73/35.98 | 35.32/34.67/35.75 |
| dng1080 @1.0 | 94.04 (92.36) | 93.51 (91.77) | +0.53 | 37.12/35.53/36.73 | 36.91/36.04/36.74 |
| spot @0.5 | 94.41 (90.76) | 93.76 (87.10) | +0.65 | 39.89/42.52/46.38 | 39.54/42.80/46.31 |
| spot @1.0 | 97.72 (94.34) | 97.53 (95.03) | +0.19 | 43.42/44.43/48.10 | 42.94/44.79/48.16 |
| floor @0.5 | 95.32 (91.47) | 95.98 (92.41) | −0.66 | 40.35/44.99/44.58 | 40.71/44.73/44.31 |
| floor @1.0 | 98.15 (94.46) | 98.59 (94.94) | −0.44 | 42.32/46.32/45.89 | 42.60/46.01/45.48 |
| hwy @0.5 | 92.96 (89.73) | 93.73 (90.58) | −0.77 | 40.78/47.76/44.11 | 41.05/47.31/43.90 |
| hwy @1.0 | 96.52 (93.37) | 97.29 (94.13) | −0.77 | 43.75/49.09/45.39 | 43.90/49.00/45.36 |
| volley @0.5 | 91.17 (90.08) | 92.37 (90.83) | −1.20 | 39.57/42.67/45.29 | 41.28/43.36/45.90 |
| volley @1.0 | 95.21 (94.28) | 95.62 (94.70) | −0.41 | 44.50/45.39/48.20 | 45.20/45.63/48.10 |

- NEG: better on 4 of 12 (dng720 @1.0, dng1080 @1.0, spot both); worse on 8, by 0.41–1.20. Worst frame better on 5
  (dng720 both, dng1080 both, spot @0.5), worse on 7. **Goal 4 is not met.**
- Where the loss is (measured, not guessed): at 0.5 bpp on dng the luma artifactmap finds dense error groups on
  the laptop-screen TEXT (22 bright + 20 dark regions on dng1080 @0.5 vs today 4 + 5; err ±1 code mean, dense
  |error| along text strokes = fine detail lost, not a grid; `out/art/`). On the motion cells the gap at 0.5 bpp
  shrank from −2.0…−2.3 (with a wave, old tables) to −0.7…−1.2.
- The still-hold rule (§7) costs 0…1.7 NEG on static content (training clips city −1.69, traffic −0.30, winter
  −0.01): it is the price of zero flicker and is inside the numbers above.
- Motion levers tried with the partner (training clips traffic/winter @0.5, `out/tune7.log`): vertical search ±8
  instead of ±4 (hwy has 11 % of |vy| > 4, others ≤ 3 %): −0.00…−0.02 NEG; zero-vector tolerance 0/1 instead of 2:
  +0.05…+0.13 NEG but 0 re-creates still-area flicker; level-1 ladder shift by the moving-block share (K = 0.5):
  −0.85 / −0.02. None closes the gap.
- History of the efficiency levers (all on training clips or diagnostics): step-bucket tables (largest single
  gain), no wave (+0.8–1.0), tilt 0.25, ρ 0.35, 64-column blocks + regularised vectors (+0.3). Tried and dropped:
  TVD slope limiters (−1.3…−2.8 intra), pair updates, 2/10 prediction, chroma offsets (trade planes), per-unit
  plans (side info pushes every slice over budget).

---------------------------------------------------------------------------------------------------------------
## 3. Legality

### 3.1 Achieved by construction (measured)
- Every output sample is in [lo, hi] for ANY bitstream: each pair is written last from a final mean and a leaf;
  the leaf is clamped into the exact integer feasible set (per parity) computed from final values only. Acyclic:
  predictors read final values, no leaf is read by anything else. No pixel clip, no symbol spent.
- Measured: 0 out-of-range samples in every run (24 efficiency decodes, rails, gfx). A legal source passes the
  synthesis with 0 samples changed. Rails cut24 / ext10 full range / ext10 limited at 0.25–2 bpp: 0 out-of-range,
  generation-2 pictures identical, zero legality bits.

### 3.2 NOT achieved: "never away"
- The clamp preserves the pair mean (the mean was already read by the neighbours' slope predictors and is what
  the coarser level's reading recovers), so the partner moves by the overshoot in the other direction. It moves
  toward its own source iff the mean's error is ≤ 0 at the upper rail (≥ 0 at the lower).
- Measured against the SAME leaves + plain clip: natural dng720 @0.5: 3 376 samples differ, 1 817 farther
  (p99 94, max 136 codes), @1.0 263 / 137 farther, @2.0 15 / 4; cf_gfx @0.5 965 / 544; rails cut24 @1.0
  6 191 of 16 109 farther (max 258); ext10 @2.0 32 445 of 43 240 (max 137). Plane MSE is LOWER than the clip arm.
- Proof sketch that no exact design with a lowpass escapes it: exactness needs every value read before the
  clamp (the mean) to be recoverable from the final picture; for a pair the only such functional is the sum, so an
  exact legaliser preserves the sum and moves the partner by −overshoot; the direction relative to the partner's
  source is the sign of the mean's reconstruction error, unknowable to the decoder. The two escapes are measured
  dead: per-sample leaves (+12…60 % bits, E1d) and plain clip with a lowpass (not exact, E2). Two limiter variants
  that keep predictions from overshooting (TVD and range-limited slopes) did not reduce away-moves (L3).
- **This is a design failure under the owner's rule, stated plainly.**

---------------------------------------------------------------------------------------------------------------
## 4. Exactness through generations (proof sketch + measurements)
- R1: pair analysis of D returns the final (clamped) leaves exactly (integer S-transform with parity rounding is
  bijective). R2: canonical reading — smallest |q| with clamp(base + q·2^e) = v exists at every e ≤ e_read
  (nesting); the slice plan read is the coarsest at which all leaves have one; generation 1 emits that reading.
- R3: vectors are functions of decoded pictures (derived by every encoder, transmitted); a re-encoder reads the
  refresh/heal structure from the picture (units that read as intra at a plan with every step ≥ 2 exist only
  where the upstream coded intra; camera input reads 0, decoded dng720 ≥ 216).
- R4 (CBR): a re-encoder forces every readable unit to the read plan; its cost equals generation 1's emitted
  bits; by induction its carried credit ≥ generation 1's (it spends E_j ≤ C_j), so the forced reading always
  fits. Generation ≥ 3: identical credits.
- Measured: final configuration (on-demand mode, still-hold, reserve), dng720 @0.5 14 frames and spot @0.5 7
  frames: generation 2 AND generation 3 pictures and bits identical on every frame (`out/chain_final_*.log`);
  earlier configurations 24 frames dng720 / 30 frames spot identical (`join_v1.log`, `join_v2*.log`); rails
  0.25–2 bpp identical.
- Mid-stream join by an ENCODER on a two-way link: exact once every unit has been coded intra upstream; on the
  primary (no-wave) mode that happens only through heals, so an encoder joining a clean two-way stream is NOT
  guaranteed to converge (measured in wave mode only: 1.3–1.6 M samples still differing after 20 frames; not
  fixed). Decoder join: exact after one cycle in the one-way mode. **Open.**

---------------------------------------------------------------------------------------------------------------
## 5. Row phases, smudges, flatness (owner tools, unmodified; frame 6 / frames 0–11)

| cell @bpp | rowphase spread Y/Cb/Cr, sh = S (mine) | (today) | artifactmap regions Y (b+d) mine / today | Cb, Cr | smudgegroups Y/Cb/Cr | flatplane Y/Cb/Cr % mine | today |
|---|---|---|---|---|---|---|---|
| dng720 @0.5 | 1.0/5.1/4.8 | 4.6/20.5/18.1 | 29 / 10 | 0 / 0 | 0 / 0 | 47.4/88.8/86.1 | 42.7/85.3/84.6 |
| dng720 @1.0 | 0.5/2.8/3.2 | 3.1/24.9/21.9 | 0 / 0 | 0 / 0 | 0 / 0 | 38.4/56.3/66.1 | 33.6/24.9/50.5 |
| dng1080 @0.5 | 1.2/7.1/6.8 | 12.8/39.2/38.3 | 42 / 9 | 0 / 0 | 0 / 0 | 57.4/85.7/84.0 | 53.5/80.6/83.6 |
| dng1080 @1.0 | 1.0/2.5/4.0 | 12.0/28.3/29.7 | 0 / 0 | 0 / 0 | 0 / 0 | 47.8/37.9/60.7 | 27.5/15.4/37.1 |
| spot @0.5 | 1.4/10.5/16.9* | 7.4/18.6/10.4* | 5 / 1 | Cb 1 / 0 | 0 / 0 | 38.3/50.6/34.0 | 52.7/68.2/72.8 |
| spot @1.0 | 1.0/9.6/16.4* | 8.4/21.5/10.3* | 0 / 1 | 0 / 0 | 0 / 0 | 27.5/25.4/21.7 | 40.8/51.4/64.5 |
| floor @0.5 | 2.5/9.6/9.9* | 13.5/23.6/20.0* | 0 / 0 | 0 / 0 | 0 / 0 | 48.6/54.7/61.9 | 55.5/69.6/75.8 |
| floor @1.0 | 2.0/8.7/8.5* | 16.2/24.3/19.6* | 0 / 0 | 0 / 0 | 0 / 0 | 25.2/32.4/34.5 | 31.7/59.1/66.5 |
| hwy @0.5 | 1.7/18.7/11.8* | 13.6/25.1/27.3* | 2 / 0 | 0 / 0 | 0 / 0 | 36.0/29.2/59.2 | 42.5/78.1/75.9 |
| hwy @1.0 | 0.8/17.9/8.5* | 11.9/28.5/23.3* | 0 / 0 | 0 / 0 | 0 / 0 | 6.2/24.9/19.7 | 30.5/58.5/53.2 |
| volley @0.5 | 1.2/13.9/16.1* | 4.6/21.4/7.4* | 12 / 0 | 0 / 0 | 0 / 0 | 35.7/59.9/57.0 | 37.0/58.0/63.0 |
| volley @1.0 | 0.4/11.7/14.4* | 5.0/21.2/8.5* | 0 / 0 | 0 / 0 | 0 / 0 | 29.9/38.7/45.7 | 33.1/49.0/54.7 |

`*` The long "L" clips carry a SOURCE chroma row-phase structure (4:2:0 origin: source Cb gradient energy by row
phase differs by ±6 %, adjacent-row differences differ by parity; measured). Chroma row spreads on those cells
are therefore not codec evidence; dng (clean source) is. From the same decodes, mean |error| by row phase
(S = 8, dng720): spread 3.9/1.5/1.8 % @0.5, 2.2/1.7/1.9 % @1.0 (today 33.9/16.4/13.4 %).

- Slice edges are not special: the slice-edge row sits inside the spread; the residual pattern is the 4-row
  signature of 2 vertical pair levels (rows 0,3 vs 1,2 of each 4-row group, chroma 2.5–7 % at 0.5 bpp on dng).
  **By the owner's rule that is a design-created row class** (smaller than SA16's 3–8 % and today's 18–39 %,
  larger than SA15's 0.4–2.3 %). Removing it by one vertical level costs −1.8 dB intra (LV1, rejected).
- Smudges: smudgegroups 0 groups on Y, Cb and Cr on all 12 of my final decodes (and 0 on Cb/Cr for today's).
  No grid-aligned structure in any artifactmap.
- Luma artifactmap regions at 0.5 bpp are MORE than today on dng/volley (text strokes, see §2): detail loss, the
  efficiency gap made visible.

---------------------------------------------------------------------------------------------------------------
## 6. Loss recovery (A5; owner correction: recovery in fewer than 4 frames)

### 6.1 Primary — on-demand heal over the return path (owner ruling S5.37)
- Decoder: a lost slice is concealed at once (its indices taken as 0 → motion-compensated prediction, soft and
  bounded); the per-slice flag goes back.
- Encoder: rows [kS − m, (k + NL)S + m], m = 16 + 8(RT + 1), coded INTRA in frame t + RT + 1 inside the fixed CBR
  budget; refreshes capped per frame and per receiver.
- Exact in one frame because every read of the healed rows is an intra leaf or a final value outside them, which
  is already exact at the decoder; the damage cannot exceed m rows (transform reach 16 rows incl. ahead data,
  vertical vector reach 4 rows per frame + OBMC). No clean-region machinery is needed on this path.
- Measured (`heal.py`, no wave, exact CBR held on every frame):

| cell @bpp | loss | RT | damaged frames | exact from | damaged samples per frame |
|---|---|---|---|---|---|
| dng720 @0.5 | 1 slice | 1 | t, t+1 (2) | t+2 | 30 005 / 37 497 |
| dng720 @0.5 | 1 slice | 2 | t…t+2 (3) | t+3 | 30 005 / 37 497 / 43 589 |
| spot @0.5 | 1 slice | 2 | t…t+2 (3) | t+3 | 35 438 / 53 991 / 74 459 |
| volley @0.5 | 8 slices (64 rows) | 2 | t…t+2 (3) | t+3 | 173 067 / 174 811 / 175 444 |
| dng1080 @1.0 | 4 slices | 2 | t…t+2 (3) | t+3 | 137 080 / 153 838 / 172 330 |

  Damage visible for RT + 1 frames: under 4 for RT ≤ 2.

### 6.2 One-way links (satellite, multicast) — cycle-2 column wave
- Owner ruling: recovery under 4 frames → cycle 2 (not all-intra, not 8+). Half the 64-column units are intra in
  each frame (plus one guard unit and one LL-intra unit), with the clean-region rule on the reference fetch, the
  OBMC block choice, the prediction's analysis and the vector derivation (a clean block whose search window is not
  wholly clean at t−2 takes the vector of the nearest fully clean block to its left).
- Recovery bound (PAPER, cycle c): damage in the half already refreshed this cycle is healed when the next cycle
  refreshes it and the other half reads only clean data: ≤ 2c − 1 = 3 frames for c = 2 (c = 3 would be 5).
  Measured (dng720 @0.5, one slice lost, `out/oneway_c*.log`): c = 2, loss at phase 1: damaged 2 frames
  (27 970 / 16 599 samples), loss at phase 0: 3 frames (28 893 / 34 797 / 14 550) → under 4; c = 3: 4 frames
  (loss at phase 1: 22 985 / 25 765 / 19 530 / 6 740) → does not meet the bar. The one-way mode is cycle 2.
- Cost @0.5 (`out/eval_wave.log`, frames 2–11, NEG mean (worst), PSNR Y/Cb/Cr):

| cycle | dng720 @0.5 | hwy @0.5 |
|---|---|---|
| 1 (all intra) | 80.94 (79.26) 31.43/35.56/36.57 | 87.88 (85.15) 39.55/47.36/43.91 |
| 2 | 87.41 (85.32) 33.52/35.96/37.03 | 89.82 (87.59) 39.95/47.49/44.03 |
| 3 | 89.22 (87.10) 34.54/36.08/37.19 | 91.07 (88.36) 40.33/47.59/44.11 |
| 4 | 89.59 (85.80) 34.81/36.11/37.25 | 91.40 (88.25) 40.44/47.64/44.11 |
| 8 | 90.23 (87.77) 35.13/36.18/37.33 | 92.14 (88.90) 40.52/47.66/44.10 |
| none (on-demand mode) | 88.97 (88.10) 34.43/36.12/37.22 | 92.96 (89.73) 40.78/47.76/44.11 |

  (dng720 improves with a wave because intra units reset the still-hold state and re-refine; see §7.)
- 12 points, one-way mode (cycle 2), `out/eval_oneway.log`, NEG (worst) / PSNR Y/Cb/Cr, today in brackets:

| cell | @0.5 | @1.0 |
|---|---|---|
| dng720 | 87.41 (85.38) 33.52/35.96/37.03 [90.16] | 93.49 (91.89) 37.63/36.92/38.07 [94.05] |
| dng1080 | 89.06 (86.61) 34.54/34.62/35.82 [91.08] | 93.63 (91.78) 36.96/35.68/36.84 [93.51] |
| spot | 92.36 (88.51) 39.55/42.24/46.14 [93.76] | 97.27 (93.88) 43.70/44.67/48.39 [97.53] |
| floor | 91.93 (89.49) 39.62/44.38/44.05 [95.98] | 97.07 (93.77) 42.27/46.16/45.83 [98.59] |
| hwy | 89.82 (87.59) 39.95/47.49/44.03 [93.73] | 95.26 (92.58) 43.34/49.02/45.45 [97.29] |
| volley | 88.33 (87.13) 38.31/42.11/44.54 [92.37] | 94.03 (93.05) 43.18/44.63/47.36 [95.62] |

  The one-way mode costs 1.0–3.4 NEG against the on-demand mode (the owner accepts a quality cost there).

---------------------------------------------------------------------------------------------------------------
## 7. Still areas (no flicker)
- Failure first (no hold, no wave, dng1080 background @0.5): 20–78 % of still samples changed EVERY frame, ≈55/45
  toward/away, not converging.
- Roots: (a) exact CBR spends the whole budget and the plan gets finer every frame on still content; (b) history
  vectors read the refinement as motion (71 non-zero vectors on a frozen dng720 frame) and reset the still state.
- Fix (encoder-only, re-encoders reproduce by reading): a zero-vector coefficient is refined ONCE after it becomes
  still (or after intra/heal), then held unless the source moves by more than ¾ of the step it was refined at;
  unused bits are padding. Vector derivation keeps zero unless motion is better by > 2 codes per pixel.
- Measured: frozen dng720 @0.5: frame 1 (ramp) changes, frames 2, 3, …: 0/0/0 samples (Y/Cb/Cr). Frozen dng1080:
  11/6/1 % at frames 2–4 before the vector fix, 0 from frame 5. Mixed clip (still dng1080 + moving PiP), still
  region beyond 40 rows / 160 columns of the PiP: Y 0.000 %, Cb/Cr ≤ 0.011 % per frame; within that margin 0.6–1 %
  chroma = the moving object's transform/OBMC halo (≤ 160 px).
- Rejected: octave refinements (hold2) recover efficiency (city +1.6 NEG) but re-create flicker (18–71 % per frame).

---------------------------------------------------------------------------------------------------------------
## 8. Latency, work, memory (PAPER; model is frame-level)
- Latency (lines, excluding conversion): capture S + 8 (two blocks ahead) + one slice period (exact CBR prefix
  bound) + ≈ 2 pipeline = 2S + 10: 18 lines at 720p (S = 4; with today's 3:1 conversion ≈ 0.99 ms, the same line
  count as today's model 8 + 8 + 2), 26 lines at 1080p–8K (S = 8). JPEG XS ≈ 32. Constant by construction.
- Work per sample (fixed, every branch fixed): decoder ≈ 57 adds/compares (synthesis ≈ 25 incl. clamps, OBMC ≈ 16,
  prediction analysis ≈ 12, entropy ≈ 4) ≈ 2× JPEG XS decode; encoder ≈ 330 (source + prediction analysis, 16
  exponent costs in parallel, canonical reading ≈ 48, vector derivation ≈ 150 on a 1:4 decimated match). No
  multipliers (4-bit shift-add weights). One plan decision per slice + one fixed emission pass.
- Memory at 8K 4:2:2 10-bit, decoder: reference ring ≈ 40 rows × 15 360 samples × 10 bit = 6.1 Mbit (samples
  legal by construction → depth bits), coefficient buffers ≈ 7.9, output lines 1.2, tANS tables 384 × 1024 ×
  ≈ 19 bit ≈ 7.5 Mbit → ≈ 22.7 Mbit (today, narrowed store: 29.2). 8K 4:4:4 12-bit ≈ 34 Mbit: over the comfortable
  margin of a ZU7EV-class part (27 + 11) unless the tables drop to 2 contexts (−3.7 Mbit). DDR: reference read +
  write at depth bits → 20 bit/sample (today 26); the vector field for frame t is derived during frame t−1 from
  rows already fetched (no extra read). The encoder's still-hold state is one exponent per (band, unit, slice):
  a few kbit.

---------------------------------------------------------------------------------------------------------------
## 9. IP provenance
| element | source | status |
|---|---|---|
| S-transform pair, 2/6 slope prediction | Haar / S-transform (1970s–80s); TS/CREW 2/6 family (Ricoh, mid-1990s) | expired |
| lifting framework, parity rounding | Sweldens 1996; own work (rounding) | open / own |
| leaf-interval legality, canonical reading, nested dyadic ladder | own work (after SA15's leaf clamps) | own |
| OBMC bilinear weights | H.263 Annex F era (1996), bilinear window generic | expired |
| block matching, Exp-Golomb | textbook; Exp-Golomb 1978 | expired |
| static tANS | Duda 2009+ (tANS only; no rANS) | open |
| on-demand refresh over a return path | owner ruling S5.37; generic ARQ-style intra refresh | own / generic |
| column-band gradual refresh | GDR, H.263/MPEG-2 era | expired |

---------------------------------------------------------------------------------------------------------------
## 10. Prior failures checked
| failure | where | status here |
|---|---|---|
| slice-closed transforms: edge step (SA12), anchor row (SA13), first-row excess (SA14) | memo A | no slice closes the transform; slice-edge row inside the spread (§5) |
| continuous 5/3: even/odd rows | E1 | pair vertical |
| pair pyramid transform price (SA16 −0.2…−0.8 dB) | SA16 F1a | measured ≈ 0 at real code lengths vs 5/3 in this codec (EV-B) |
| PSNR-optimal ladder zeroing level-1 (SA16) | SA16 F1b | tilt 0.25 toward fine bands (training clips); still −0.4…−1.2 NEG on 8 points |
| lattice lock (SA15 texture loss, ants, 1 000-frame refresh) | SA15 | value-domain prediction; heals are rows, not lattice re-sends |
| decoder-derived vectors (S5.29) | ledger | vectors derived by encoders, transmitted |
| exact hold not gen-2 consistent (SA16) | SA16 F2 | hold is an ENCODER choice of zero indices; re-encoders read it (gen 2/3 identical with hold on) |
| entropy-estimate lead (SA15) | SA15 F1a | every number here is a real code length; entropy proxy used only for screening |
| rail cost (SA15 +2–16 %) | SA15 F5 | legality spends no symbols; rails exact; cost is in "away" moves instead (§3.2) |
| partner moves away (SA15 F5) | SA15 | NOT solved (§3.2) |
| 4-row signature (SA16 3–8 %) | SA16 F3 | still present in chroma at 0.5 bpp, 2.5–7 % on dng (§5) |
| mid-stream join plateau (SA15 F4) | SA15 | encoder join on the no-wave primary mode not solved (§4) |
| ants / still flicker (today, SA15, SA16) | memos | 0 changed samples from frame 2 on frozen input; halo ≤ 160 px around moving objects |

---------------------------------------------------------------------------------------------------------------
## 11. Risks and open items (plainly)
1. **Goal 4 fails**: −0.4…−1.2 NEG on 8 of 12 points; fine text/detail at 0.5 bpp is lost more than today.
2. **"Never away" fails** (§3.2), with a proof sketch that exact lowpass designs cannot meet it.
3. **Row class**: 2-level pair signature 2.5–7 % in chroma at 0.5 bpp on dng.
4. **Encoder join on the primary two-way mode** has no convergence mechanism (only heals and the one-way wave).
5. CBR: exact emission relies on a 16-bit reserve covering the reading's excess (measured ≤ 5.5 bits), not proven.
6. Only 4:2:2 10-bit measured end to end; 4:2:0 / 4:4:4 / 8- and 12-bit are argued, not run (the legality and
   reading code is depth- and range-agnostic; rails were run at full and limited range).
7. Ahead-data packing, latency and memory are PAPER; the model is frame-level.
8. The still-hold costs up to 1.7 NEG on static scenes (included in §2).

## 12. Files
- Model: `model/pyr.py` (transform, legality, canonical index), `codec.py` (frame coder, rate control, reading,
  decoder), `ent.py` (tables), `motion.py`, `seq.py` (sequence, refresh/heal, still-hold, re-encoder), `heal.py`,
  `oneway.py`, `stilltest.py`, `railtest.py`, `awaytest.py`, `join2.py`, `evalcell.py`, `metrics.py` (NEG, verified
  against the owner's negscore.sh: 88.858 = 88.858).
- Results: `out/eval_final.log`, `out/eval/*.json`, `out/dec/*.d.yuv`, `out/art/` (owner tools, maps per plane),
  `out/heal_*.log`, `out/eval_wave.log`, `out/still_*.log`, `out/join_v*.log`, `out/rail_v1.log`, `out/away_*.log`.
