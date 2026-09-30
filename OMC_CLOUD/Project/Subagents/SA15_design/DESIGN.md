# SA15 — CPP-LL: Continuous Pair Pyramid with Lattice-Locked temporal prediction

Designer SA15, 2026-09-28. Written incrementally; every figure cites a script and an output file in
`Subagents/SA15_design/` (notes/ = scripts, out/ = results). **All measurements are numpy MODELS**: entropy
rates from a causal-context model, not coded bitstreams; "today" = OMC's real decodes
(`Subagents/SA7_legality_v2/out/DM/*_a0.d.yuv`). Where a rate is compared with today's coded rate, the model
entropy target is today's rate / 1.10 (1.10 = ASSUMED static-tANS overhead, not measured). Status tags:
MEASURED (model output on real footage), ARGUED (proof or reasoning, no run), ESTIMATED (arithmetic).

---------------------------------------------------------------------------------------------------------
## 0. Summary

Three ideas, each fixing a root cause rather than a symptom:

1. **No transform unit ends at a slice edge (seams, smudges).** The vertical transform is a Haar-*pair*
   pyramid (pair mean + predicted pair difference, "2/6 / TS form", 5 horizontal x 2 vertical levels). Its
   split never straddles a 4-row block; only the difference *predictor* reads the neighbouring blocks'
   means. Every block's neighbour means are sent one step earlier in the stream than the block that needs
   them — for every block, not only at slice edges — so all blocks are decoded by one rule and a slice edge
   is an ordinary block edge. Slices are packet / rate units only. MEASURED: per-row error statistics are
   flat across all 16 row phases, intra and inter, Y/Cb/Cr (section 5). A causal (look-back-only) variant
   was built and REJECTED because it created a 1-in-8-row special row (+5..9 % error), exactly the
   design-created artifact the owner forbids.
2. **Legality is a property of the synthesis, not a clip (legal, exact, zero bits).** Each pair is written
   last from its mean (already final) and its difference (a leaf). The set of differences that keeps both
   output samples inside their legal boxes is an integer interval the DECODER computes from final values
   only; the decoder clamps the difference into it. No cycle (the mean is never re-read), no search, no
   clip. The next encoder recomputes the same interval and a canonical index rule maps the clamped value
   back to the same index. MEASURED: 0 out-of-range samples, generation-2 identical pictures and indices on
   every run (natural, graphics, 0.2-2.7 bpp); bits and PSNR equal to "same codec + clip" within noise.
3. **The reconstruction never depends on the reference (exactness through hops, refresh, joins, loss).**
   Temporal prediction does not predict sample VALUES; it predicts quantisation INDICES. Every coefficient
   is always reconstructed as an intra lattice point `p_intra + R(q)`; the motion-compensated picture only
   supplies a hint index h and the stream carries q - h. So the decoded picture is a function of the
   indices and steps alone. A refresh (hint-free coding) re-describes the same picture bit-for-bit, a
   joining encoder reproduces the upstream picture from its first affordable frame, and a decoder that
   lost a packet becomes bit-exact again as soon as the damaged region is refreshed. MEASURED: equal or
   better efficiency than value-domain prediction at matched entropy; generation-2 exact even with a
   different reference or none (section 4).

Efficiency vs today's real decodes (steady state, frames 2-11, entropy x 1.10 estimate for the rate):
see section 7 — VMAF-NEG >= today on every measured cell with the adopted config (dng720 @0.5 91.97 vs 90.16,
@1.0 94.21 vs 94.05; dng1080 @1.0 93.78 vs 93.51) and with the first config on the cells B was not re-run on
(dng1080 @0.5 91.09 vs 91.08 = tie; spotrobotL @0.5/1.0 95.50/97.65 vs 93.76/97.53; floorballgameL @0.5
96.63 vs 95.98; cf_gfx 88.39/93.36 vs 83.11/92.67). Mean PSNR higher on every plane of every point:
Y +0.8..+4.0 dB, Cb +0.6..+1.1, Cr +0.4..+1.3.

Weakest point (section 10): rate control. Lattice-locked prediction makes a still area change whenever its
quantiser step changes, so the rate controller must never coarsen still regions; that policy, and a
provable exact-CBR fit without a flat fallback, are designed (2.8) but NOT measured in the model (the model
uses one step per frame).

---------------------------------------------------------------------------------------------------------
## 1. Measurements (chronological; later sections cite them)

| id | question | script | output | result |
|---|---|---|---|---|
| T1 | per-sample-clamp family (closed-loop predict-only pyramid) | notes/t1_po_vs_53.py, t1b.py | out/t1b_*.txt | -1.4..-5.0 dB Y, chroma to -7.7 dB vs 5/3 at matched entropy: DROPPED (agrees with S5.212/S5.349) |
| T2 | pair pyramid (2/6) with decoder boxes, intra | notes/tsx.py, t2.py | out/t2_*.txt | oob 0; gen-2 identical; within +-0.3 dB of 5/3 (dng720 -0.11 Y @0.78 bpp, +0.1 @1.43; spot -0.27/-0.10/+0.07 @0.45) |
| T3 | sequence, value-domain inter | notes/cpp.py, seq.py | out/seq_*.txt | oob 0; gen-2 0 differing samples, identical bits (dng720, gfx, both rates) |
| T3b | sequence, lattice-locked inter | same, TMODE=idx | out/seqidx_*.txt | adopted (section 2.5, 7) |
| T4 | causal vertical predictor / 3 levels | t2.py | out/t4_*.txt, out/rowstats_dng720_b0.5_v26cL3.txt | +2..9 % intra bits and a period-8 special row: REJECTED |
| T5 | legality cost vs "no legality + clip" | notes/t5_harm.py | out/t5_*_v*.txt | bits ratio 0.999-1.006 at operating rates; PSNR equal within 0.03 dB |
| T6 | still input | notes/t678.py still | out/t6_still.txt | 0 changed samples / 0 bits per frame at constant step |
| T7 | mid-stream join | notes/t678.py join | out/t7_join.txt | joiner (no history) at frame 4: 0 differing samples from its FIRST frame, all planes; bits 2.06x upstream on that frame (hint-free), 0.97x next, identical from the 3rd (vectors equal) |
| T8 | packet loss + on-demand refresh | notes/t678.py loss | out/t8_loss.txt, out/t8_loss_rm3.txt | slice 20 lost at f4 (dng720 @0.5): damage rows 314-341, spreads to 298-357 by f5; refresh at f6 (RTT 2) of slices 17-23 hint-free -> decoder == encoder bit-exact from f6 on (0/0/0 samples), encoder picture unchanged by the refresh, refresh frame 1.29x bits. A refresh of only slices 19-21 (narrower than the footprint) left 1-4k dirty samples that re-grew: the refresh must cover the damage footprint (lost slice + motion spread x RTT + 8 look-ahead rows) |
| T9 | DC bias (cast) | inline, see 5.3 | — | floor rounding gave -0.07..-0.21 code; position-alternating rounding: -0.01..+0.02 (intra), -0.02/+0.02/-0.01 over frames 2-11 |
| T10 | NEG levers | seq.py DZ=0.45 / THETA=0 | out/ev_*dz45*.txt, out/ev_dng720_1.0_th0.txt | offset 0.45: NEG +0.3..+0.5 over offset 1/3; THETA=0 worse; config B adopted |

---------------------------------------------------------------------------------------------------------
## 2. The codec

### 2.1 Signal, planes, legal range
Y, Cb, Cr are coded as three independent planes (no cross-plane transform, so legality is per plane;
RGB is out of scope, B2). Bit depth B = 8/10/12 (16 later): all arithmetic is integer, widths grow by <= 3
bits over B. The legal range [lo, hi] of each plane is a stream-header parameter (full range [0, 2^B-1],
SDI-legal [2^(B-8), 2^B-1-2^(B-8)], or any narrower range); nothing else in the codec depends on the range.
4:4:4 and 4:2:2 chroma use the luma structure at their own width; 4:2:0 chroma uses Lv = 1 (section 2.2)
so its look-ahead in luma lines stays within the luma look-ahead. SDR/HDR (PQ/HLG) are transparent: the
codec sees code values only.

### 2.2 Blocks, units, slices, packets (the coding order)
- **Block** = 2^Lv rows of a plane (Lv = 2: 4 rows; 4:2:0 chroma Lv = 1: 2 chroma rows = 4 luma rows).
- **Unit b** = the data needed to finish block b, sent in this fixed order for EVERY block:
  (i) level-1 vertical-lowpass bands (LH1, LL coarse chain) of block b+2; (ii) level-1 vertical-difference
  bands (HL1, HH1) of block b+1; (iii) level-0 vertical-lowpass band (LH0) of block b+1; (iv) level-0
  vertical-difference bands (HL0, HH0) of block b. After unit b a decoder holds every neighbour mean that
  block b's symmetric predictors read, so block b is final — no waiting for later units.
- **Slice** = S rows = an integer number of blocks (S = 4 at 720p-class, S = 8 at 1080p and above); the
  rate-control and packet unit. A packet = the units of one slice, one static-tANS state, fixed position
  in the CBR stream. Nothing in the decoded values depends on where slices begin: the model decodes the
  whole frame as one continuous pyramid and the packetised decoder produces the identical picture.
- Look-ahead: to emit unit b the encoder needs source rows to the end of block b+2 = 8 lines (Lv = 2).

### 2.3 Transform — continuous pair pyramid (CPP)
One 1-D pair step along an axis, pair (a, b), rounding offset r = (i + j) mod 2 (i = pair index along the
axis, j = position across it; alternating, so the mean is unbiased — T9):
```
analysis :  m = floor((a + b + r) / 2)          d = a - b
            d' = d - P(m)                       (only d' and the coarsest means are coded)
synthesis:  s = 2m + ((d + r) & 1) - r          a = (s + d) / 2      b = (s - d) / 2
P(m)_i   =  floor((16*m[i-1] - 16*m[i+1] + 32) / 64)           ("2/6" slope predictor, both axes)
```
All adds and shifts; the predictor is symmetric and reads only means. Levels: 5 horizontal, the first 2
also vertical (5H x 2V). Per 2-D level the synthesis order is: horizontal pair synthesis of (LL, LH) ->
vertical lowpass rows L_v; horizontal pair synthesis of (HL, HH) -> predicted vertical differences D_v';
D_v = D_v' + P_v(L_v); vertical pair synthesis (L_v, D_v) -> the level's output rows. The coarsest band
(LL after 5 horizontal levels, one coefficient per 32 x 4 samples) is coded by DPCM from its left neighbour
(column 0 from mid-range). Picture edges replicate. Measured cost vs an open-loop 5/3 with the same
quantiser and entropy model: within +-0.3 dB (T2).

### 2.4 Quantisation and the step field
Dead-zone uniform quantiser `q = sign(x) floor(|x|/D + 0.45)` (0.45 adopted over 1/3 for texture, T10), reconstruction `R(q) = round(q D)`; the
division is a multiply by a table reciprocal realised as shift-adds (8 steps per octave) plus one compare
(C3). `D = W_band * 2^(s/8)`: W_band = the band's synthesis-gain weight (fixed table), s = the **step field**.
The step field is continuous by construction: knots on a grid of regions (block rows x 256-column strips),
bilinear interpolation of s between knot centres, both ends derive every coefficient's D from the knots, no
region boundary exists in the field (owner rule: every per-region parameter is a continuous field). The
knots are the only rate-control output (2.8).

### 2.5 Temporal prediction — lattice-locked (index-domain) hints
For each coded quantity x with intra predictor p (P(m) for differences, 0 for mean bands, DPCM for LL):
```
reconstruction (always):   v = clamp(p + R(q), [vlo, vhi])          (the legal interval, section 3)
inter coding transmits:    r = q - h
hint:                      h = canonical index of x_mc  (x_mc = the same quantity computed on the
                               motion-compensated picture, with the same reconstructed-mean predictors)
encoder choice of q:       exact index if x is exactly representable (always true on a decoded input);
                           else h if |x - v(h)| <= (1/2 + 1/4) D   (temporal hysteresis: still content
                           keeps its indices, no flicker);  else the dead-zone index of x
```
- Motion: 16x16 luma blocks, integer-pel, vectors estimated by EVERY encoder from its two previous decoded
  frames (block match D(t-1) against D(t-2), constant-motion assumption) and TRANSMITTED; the decoder never
  derives vectors (S5.29). Prediction picture = OBMC: per pixel a bilinear blend of the four nearest block
  vectors with dyadic weights (sum 256, shift-add), from the previous decoded frame only (C2).
- Because v never depends on the reference, vectors and the reference influence BITS only, never pixels.
- Hint-free coding (h = 0) is used for frame 0, for scene cuts (per slice: whichever of hinted / hint-free
  costs fewer bits — both costs are computed exactly in the same pass because q is the same) and for
  refresh units (2.9).
- Measured vs value-domain prediction (T3 vs T3b, same model, matched entropy): equal or better on every
  point (dng720 @0.5 f6 38.41/37.01/38.01 at 0.432 bpp vs 38.08/36.79/37.87 at 0.425; @1.0 f7
  40.08/38.63/39.27 at 0.830 vs 39.66/38.24/38.94 at 0.862; spot @1.0 f3 45.04/45.70/48.53 vs
  44.72/45.38/48.23).

### 2.6 Entropy coding
Static tANS (C1: tANS only). Symbol = q (hint-free) or r (hinted), per band class, 9 contexts from the
magnitude classes (0, 1, >=2) of the left and upper already-coded symbols of the same band; |symbol| > 15
escapes to an Exp-Golomb suffix (raw bits). Tables are fixed in the specification (trained offline, per band
class x context x mode). One tANS state per packet, flushed at the packet end (loss containment). The model
measures the adaptive conditional entropy of exactly these symbols; the real static-table cost is ASSUMED
+10 % (prior designers used x1.04..x1.16 depending on rate).

### 2.7 Resolution / format conversion
Outside the codec core, as today: the raster-clocked output converter (OMC docs/LATENCY.md) with charge
reach + 1 lines (reach 6/9/12/18). Its negative-lobe kernels can leave [lo, hi]; the converter clips — this
is after the decoder, on a different raster, and is not part of any generation loop (a hop re-encodes the
converted picture as fresh source). Stated, not redesigned.

### 2.8 Rate control — exact CBR, one pass (DESIGNED, not modelled)
- Budget: the CBR prefix bound (OMC's, no overdraft): bits of slices 0..k <= (k+1) x B_slice for every k;
  unspent bits carry forward as credit, never borrowed ahead.
- Per slice, one pass: the encoder forms, from the OPEN-LOOP coefficients of the slice (already computed
  for the look-ahead), a magnitude histogram per band class; for each candidate knot shift (-2..+2 ladder
  steps per region, 1/8 octave each, continuity-limited) the bit estimate is a dot product of that
  histogram with the static code-length table — cost independent of the number of pixels. It picks the
  finest candidate whose estimate fits budget + credit - margin, codes the slice ONCE, and carries the exact
  difference into the credit.
- **Still-region rule** (lattice-locked prediction needs it): the knot of a region whose previous-frame
  symbols were all hint-kept (r = 0) may only stay or become exactly one octave finer (nested lattice: the
  old reconstruction is a point of the new lattice, so nothing changes); it is never coarsened. Only active
  regions carry the rate adaptation. Refinement frames quantise fresh (no hint) so the region settles in one
  frame (T6 showed a 2-frame settling without this).
- Terminal guard (never flat): if the exact count would break the prefix bound, the remaining coefficients
  of the slice are coded as r = 0 (hint-kept, the cheapest symbol, exactly countable in advance), i.e. the
  rest of the slice shows the motion-compensated lattice prediction — not an LL-only rung. Intra (frame 0,
  cut) slices have no hint; they are the ramp and are sized with a larger margin. RISK: the guard's
  frequency and visibility are unmeasured (section 10).
- Plan recovery (for exactness): the knots of a decoded input are the coarsest candidates under which every
  coefficient of the region is exactly representable (a parallel lattice test over the <= 5
  continuity-limited candidates, one comparator per candidate per coefficient). The first encoder applies
  the same rule to its own reconstruction and emits the result (gen-1 self-read).

### 2.9 Loss resilience and refresh
- A lost packet (slice k) loses slice k's units: the rows of slice k and the look-ahead means of the next 8
  rows. The decoder conceals with r = 0 (the hint, i.e. the motion-compensated lattice prediction): a
  bounded, soft, localized defect. Decoded damage then spreads only through motion (<= 16 rows per frame).
- **On-demand refresh** (back channel allowed, owner ruling 2026-09-04): the decoder reports the lost slice;
  the encoder codes the affected slices (+ the motion spread margin: lost slice +- ceil((16 x RTT_frames + 8)/S) slices) hint-free, choosing the SAME indices as the hinted coding would (the hint still steers the choice; only the transmitted symbol is q instead of q-h). Because the reconstruction is
  reference-independent, the refreshed region is bit-identical to the encoder's picture immediately and the
  encoder's own picture does not change at all (no pop). Recovery = round trip + 1 frame.
- For one-way links (no back channel, detected automatically when no reports arrive) a **bit-metered
  background sweep**: each frame, consecutive blocks along a top-down sweep are coded hint-free until a fixed
  reservation R_ref bits is spent; clean-region rule for vectors of blocks above the sweep front (they may
  not read reference rows below the previous front). The frame budget always accounts the full R_ref (the
  unspent remainder, < one block's refresh overhead, is padding), so ANY encoder's sweep phase fits the
  budget — the phase need not be known downstream. Recovery bound = N_blocks x (max per-block refresh
  overhead) / R_ref frames (bounded; typical far lower).

---------------------------------------------------------------------------------------------------------
## 3. Legality by construction (ARGUED + MEASURED)

Per pair step the decoder knows, before it reads the difference: the pair mean m (final), the predictor
offset p (from final means), and the legal box of each output sample ([lo,hi] for picture samples; for the
intermediate vertical differences D_v, the interval that keeps both final rows legal given the final L_v).

Lemma 1 (difference interval). For boxes [A0,A1], [B0,B1] and rounding offset r, the set of d giving
a in [A0,A1] and b in [B0,B1] is the integer interval
`r=0: [max(2(A0-m)-1, 2(m-B1)), min(2(A1-m), 2(m-B0)+1)]`,
`r=1: [max(2(A0-m), 2(m-B1)-1), min(2(A1-m)+1, 2(m-B0))]`; it is non-empty whenever m lies in
Lemma 2's interval.
Lemma 2 (mean interval). The set of means m = floor((a+b+r)/2) over a, b in their boxes is
`[floor((A0+B0+r)/2), floor((A1+B1+r)/2)]` (a+b takes every integer between A0+B0 and A1+B1).
Decoder rule: every mean-type coefficient is clamped into its Lemma-2 interval, every difference into its
Lemma-1 interval, top-down in the synthesis order of 2.3. By induction over levels every intermediate mean
is feasible and every output sample lies in its box. This holds for ANY bit string (corrupt streams too),
so the decoder needs no clip. The intervals depend only on already-final values: no cycle, one pass, a
compare-and-clamp per coefficient.

Why the clamp never works against the picture: the interval is exactly the set of legal outcomes given the
already-fixed mean, so the clamped value is the closest legal description of that pair on its own
mean-preserving line; the overshooting sample moves toward its box (the source is inside it); the pair's
lowpass is untouched. MEASURED (T5, same codec with and without boxes, the latter clipped): bits ratio
0.998-1.006 and PSNR identical within 0.03 dB per plane at 0.3-2.7 bpp on dng720 and cf_gfx; at 0.2 bpp on
cf_gfx +5.6 % Y bits (-4 % chroma) from the boundary-preference rule, which is to be restricted to
exact-target cases (canonicality needs only that). Honest limit: because every later decision is
closed-loop, "with boxes" and "clip" decodes differ in samples far from any clamp; per-sample they split
~50/50 better/worse. The claim is therefore zero cost in bits and dB, not a per-sample dominance over a
clip; a clip is not an option anyway (it is what breaks exactness).

---------------------------------------------------------------------------------------------------------
## 4. Generation exactness (ARGUED + MEASURED)

Notation: D = the decoder (indices, knots, vectors -> picture), E = the encoder.

(a) Integer invertibility. The pair step is a bijection on integers for any r, so the analysis of a decoded
picture returns exactly the reconstructed means and differences v (clamped ones included).
(b) Canonical indices. For an unclamped v, `Q(v - p) = q` because |R(q) - qD| <= 1/2 < min(0.45, 0.55) D for
D >= 2 (enforced). For a clamped v (equal to its interval boundary) the canonical index is the
smallest-magnitude index whose reconstruction reaches that boundary; the first encoder emits exactly this
index (its own choice rule returns it), so the second encoder, computing the same interval from the same
final values, returns the same index.
(c) Canonical plan. Knots = coarsest candidates under which every coefficient is representable, applied by
gen-1 to its own reconstruction (2.8).
(d) **Reference independence (lattice lock).** The picture is `D(q, knots)`; hints, vectors, reference and
refresh phase enter only r = q - h, i.e. bits. Hence:
- Baseband hop: E(D1) finds every v exactly representable -> the same q (b), the same knots (c) -> D2 = D1
  for every frame, whatever D2's own reference, vectors or refresh phase are. Bits are identical too when
  the histories are identical (same vectors, same hints) — which they are by induction from frame 0.
- CBR hop at the same rate: the same, plus the fit: gen-2's bits equal gen-1's, so it fits; the
  background-refresh reservation is accounted in full by every encoder (2.9), so a different sweep phase
  cannot push gen-2 over budget.
- Unlimited generations: D_n = D_1 by induction.
- Mid-stream join: a new encoder's first frame has no reference, so it must code hint-free; at gen-1's knots
  that usually exceeds the budget, so its first frames are a ramp at coarser knots. It then runs a SYNC
  SWEEP: top-down, one slice per frame is coded at the upstream knots (exact by (d) whatever its reference),
  funded by coding the not-yet-synced slices coarser; synced slices stay exact (their pictures do not depend
  on the reference) and their bits converge to upstream's once two consecutive frames are exact (vectors).
  Bound: slices-per-frame + 2 frames. MEASURED (T7, dng720 @0.5, no budget cap in the model): the joiner's
  pictures equal upstream's from its first frame (0 differing samples, Y/Cb/Cr); its bits are 2.06x upstream's
  on that frame (no reference), 0.97x on the next, identical from the third. The 2.06x is what the sync sweep
  must fund; the sweep itself is not modelled.
- After a packet loss, the refreshed region is bit-exact again in the refresh frame and stays so (T8: 0 differing
  samples from the refresh frame on, all planes), provided the refresh covers the whole damage footprint.
MEASURED: T3/T3b gen-2 0 differing samples and identical bits on every sequence run (value-domain and
lattice-locked, dng720 and cf_gfx at 0.5/1.0 bpp); the lattice-locked plane codec reproduces a decoded
input exactly with a DIFFERENT reference and with NO reference (inline test, section 1).

---------------------------------------------------------------------------------------------------------
## 5. Why none of the known artifacts can occur

### 5.1 Seams and special rows at slice boundaries — root removed, per-row-phase evidence (MEASURED)
`notes/rowstats.py`: per plane, for every row phase of a 16-row slice, mean |error|, mean signed error and
the row-to-row step (mean |e(r+1) - e(r)|); frame 0 = intra, frames 2-11 inter (refresh rows separate).
dng720 @0.5, lattice-locked (`out/rowstats_dng720_b0.5_idx0.25.txt`): mean |error| spread across the 16
phases 3.1/1.2/1.9 % (Y/Cb/Cr) inter, 4.6/2.9/2.9 % intra; step spread 2.5/2.7/1.8 % inter, 3.2/2.4/2.9 %
intra; phase 15 (slice boundary) inside the band on every plane. The only structure is the +-1..2 %
period-2 alternation of the step (inside-pair vs across-pair), identical in every pair of the slice. Value
domain and @1.0: same picture (`out/rowstats_dng720_b*_val.txt`). (Further cells: section 5.6.)
Counter-example kept as evidence: the causal-predictor variant (T4) shows +5..9 % mean |error| on every
8th row (phases 7 and 15) — a design-created special row, so it was rejected, not patched.

### 5.2 Smudges (level-map groupings along the grid)
Causes in OMC: the mirrored bottom row, the boundary blend that shifts row levels, per-slice plan jumps.
CPP has no mirror, no blend, no per-slice parameter (the step field is continuous), and the rounding bias
that makes level offsets is removed (5.3). MEASURED: smudgegroups.py 0 groups in Y, Cb and Cr on dng720
@0.5 (today also 0 on this cell/frame); artifactmap.py 0 bright / 0 dark regions in Y, Cb and Cr
(today: 7 bright, 9 dark in Y). Further cells: 5.6.

### 5.3 Casts (T9, MEASURED)
With floor rounding of the pair mean the intra reconstruction carried -0.07/-0.10/-0.14 code (dng720)
and the lattice-locked inter frames kept it (-0.08/-0.08/-0.15 over frames 2-11). Root: floor in
`m = floor((a+b)/2)` loses the odd half-code whenever the difference is quantised to an even value.
Position-alternating rounding r (2.3) removes it: -0.013/+0.021/-0.013 at identical bits and PSNR, legality
and gen-2 exactness unchanged.

### 5.4 Flicker in still areas (T6, MEASURED)
Still input (dng720 frame 8 repeated), constant step: 0 changed samples and 0.0000 bpp on every frame after
the first, all three planes (hysteresis keeps every index). A one-octave refinement changes the picture
toward the source (PSNR +2.8 dB) and, without the fresh-quantisation rule of 2.8, settles over two more
frames (1.5 % then 0.02 % of samples); a coarsening requantises (that is why 2.8 forbids coarsening still
regions).

### 5.5 Blocks, tiles, hard edges, flat patches (HVBC's and OMC's)
- No block-wise mode, no per-block parameter: the only per-region parameter (step) is a continuous field;
  temporal prediction has no per-block intra/inter switch (hints everywhere; hint-free only per slice for
  cuts/refresh, and there the picture is identical either way).
- Motion blocks: OBMC removes the 16x16 prediction grid (SA12 measured +0.162 grid without OBMC).
- Flat patches (G4): the reconstruction of a zeroed difference is the 2/6 slope prediction, not a flat
  pair; measured flatplane on dng720 @0.5: 38.2/48.5/69.3 % of textured blocks flat (today
  41.9/82.8/83.3 %). Better, but the owner's zero-flat bar is NOT met (the dng grain at 0.5 bpp).

### 5.6 Slice-boundary excess on every modelled cell (MEASURED, out/rowstats_block_vs_slice.txt)
The L arms (spotrobotL, volleyballgameL, floorballgameL) have a period-4 row structure in their SOURCE
chroma (the source's own row-to-row step is +10..+21 % at phases 3,7,11,15 — from their 4:2:0 master;
`notes` check above), so the right test there is slice edge (phase 15) against the three internal 4-row
edges (phases 3,7,11), which see the same source structure:
| cell | excess ph15 - ph3/7/11, mean|e| Y/Cb/Cr (inter) | same, row step Y/Cb/Cr (inter) | same, intra frame |
|---|---|---|---|
| spotrobotL @0.5 | -0.2/-0.3/-0.4 % | -0.4/-0.5/-0.5 % | within +-0.8 % |
| spotrobotL @1.0 | -0.2/-0.2/-0.0 % | -0.4/-0.5/-0.3 % | within +-0.8 % |
| volleyballgameL @0.5 | -0.1/+0.1/+0.9 % | -0.3/-0.5/-0.4 % | Cb/Cr mean|e| +1.6/+2.1 % (one frame) |
| floorballgameL @0.5 | -0.2/-0.0/-0.2 % | -0.2/-0.3/-0.5 % | within +-0.4 % |
| dng1080 @1.0 | -0.1/-0.2/-0.1 % | -0.3/-0.4/-0.2 % | within +-0.5 % |
| cf_gfx @0.5 | +0.3/+0.4/+0.9 % | +0.3/-0.3/+1.1 % | within +-2.1 % (small picture) |
Today's codec on spotrobotL @0.5, same statistic: Cr row step phase 15 +48 % against +16..+19 % at phases
3/7/11 (excess ~+30 %), Cb +24 % against +9..+11 % (~+13 %).
dng1080 (no source period-4 structure) also shows no 4-row block signature (phases 3/7/11/15 at -2..+0.6 %).

---------------------------------------------------------------------------------------------------------
## 6. Work, FPGA fit, latency

### 6.1 Latency (ESTIMATED, raster arithmetic, same model as OMC docs/LATENCY.md)
`T = S (capture) + 8 (look-ahead) + S x total/active lines (transmit one slice period) + 2 (pipeline)`;
conversion charge = reach + 1 lines (raster-clocked converter). S = 4 at 720p, 8 above.

| format | lines | codec ms | +3:2 conv | +2:1 conv | +3:1 conv | OMC today (same model) |
|---|---|---|---|---|---|---|
| 720p50 | 18.2 | 0.484 | 0.751 | 0.831 | 0.991 | 0.489 |
| 720p60 | 18.2 | 0.404 | 0.626 | 0.693 | 0.826 | 0.407 |
| 1080p50 | 26.3 | 0.468 | 0.646 | 0.699 | 0.806 | 0.616 |
| 1080p60 | 26.3 | 0.390 | 0.538 | 0.583 | 0.672 | 0.514 |
| 2160p50 | 26.3 | 0.234 | 0.323 | 0.350 | 0.403 | 0.308 |
| 2160p60 | 26.3 | 0.195 | 0.269 | 0.291 | 0.336 | 0.257 |
| 4320p50 | 26.3 | 0.117 | 0.161 | 0.175 | 0.201 | 0.154 |

JPEG XS reference: ~32 lines end to end (project record). CPP is 18-26 lines excluding conversion, i.e. at
or below XS at every format, and below 1 ms with every conversion; the tightest case, 720p50 with a 3:1
converter, is 0.991 ms — identical to today's codec in the same case (0.996). Deterministic: every term is
a fixed number of lines; no retry can lengthen a slice (one pass).

### 6.2 Work per sample, closed form (ESTIMATED)
Counts per coefficient (= per sample, the pyramid is critically sampled); A = adder/subtractor or compare.
- Decoder: tANS symbol 1 LUT + ~3 A; dequant q x D as <=3-term shift-add ~3 A; hint (inter): forward pair
  step of the MC picture ~4 A + quantise (reciprocal shift-add ~4 A + 1 compare) ~5 A; predictor 2 A; box
  interval 6 A + clamp 2 A; pair synthesis 3 A; OBMC 4 fetches x (2 A weight) + 3 A sum ~11 A.
  Total ~ **40 A + 1 LUT per sample**, fixed.
- Encoder: forward pair analysis of source and of the MC picture ~8 A; quantise + hint + hysteresis ~12 A;
  decoder loop (it must reconstruct) ~20 A; rate estimate: histogram increment 1 A (the candidate dot
  products are per slice, not per sample); plan-recovery lattice test 5 candidates x 2 A = 10 A; motion
  search on decoded frames: +-16 pel at half resolution, 289 candidates per 8x8 half-res block + 9-point
  refinement ~ 90 A per full-res luma sample (luma only; chroma reuses vectors), i.e. ~45 A per 4:2:2
  sample. Total ~ **135 A per sample** (motion search is ~1/3).
- JPEG XS for comparison (ESTIMATED): 5/3 lifting 2V: ~12 A, quantisation/GCLI/budget scenarios ~20 A,
  packing ~5 A: ~40 A per sample, decoder ~25 A. CPP: decoder ~1.6x XS, encoder ~3.4x XS — the extra is
  temporal prediction (motion search + MC + hint), which XS does not do. No work repeats: one analysis, one
  quantise/reconstruct pass, one entropy pass per slice.

### 6.3 ZU7EV fit (ESTIMATED)
Worst case 4320p60 4:2:2: 7680 x 4320 x 60 x 2 = 3.98 Gsample/s -> 10 lanes at 400 MHz.
Encoder ~135 A x 10 lanes = 1350 adders of 12-20 bits (~20 LUT each) ~ 27 k LUT + motion SAD trees and
control ~20 k + 10 tANS encoders (~1.5 k LUT, 2 BRAM each) ~ 15 k + rate/plan logic ~10 k: ~ **70-80 k LUT
of 230 k (30-35 %)**, 0 DSP needed. Decoder ~40 k LUT (17 %). Memory: line buffers (look-ahead 8 + block
+ pipeline ~16 rows x 7680 x 2 x 12 bit ~ 3 Mbit), motion window cache for OBMC (+-16 rows + block: 41 rows
~ 7.6 Mbit) — in UltraRAM (27 Mb). Reference frame in DDR: one write + ~1 read per sample with the window
cache: 2 x 3.98 G x 12 bit ~ 96 Gbit/s at 8K60 — the binding resource (one 64-bit DDR4-2400 = 154 Gbit/s
peak, ~62 %); at 4K60 ~24 Gbit/s. 8K60 therefore needs the PL DDR interface in addition to PS DDR, as any
temporal codec does. At 4K60 and below everything is < 10 % of the part.

---------------------------------------------------------------------------------------------------------
## 7. Efficiency vs today's real decodes (MEASURED model entropy, ESTIMATED coded rate)

Steady state = frames 2-11 of 12; CPP rate per frame <= today's coded rate / 1.10; VMAF-NEG by
shared_tools/negscore.sh over frames 2-11; PSNR mean (and worst frame) Y/Cb/Cr.

Config A = as first modelled (dead-zone rounding offset 1/3, floor mean rounding). Config B = the adopted
config (offset 0.45 + position-alternating rounding, T10). Today = OMC real decode (floorball: produced
here with `.work/v537/omc_enc/omc_dec --bpp 0.5 -n 12`, out/today/).

| cell @rate | cfg | NEG CPP | NEG today | PSNR mean CPP | PSNR mean today | worst frame CPP | worst frame today |
|---|---|---|---|---|---|---|---|
| dng720 @0.5 | A | 91.48 | 90.16 | 37.99/36.77/37.84 | 35.22/36.10/37.14 | 37.28/36.38/37.52 | 34.69/35.86/36.98 |
| dng720 @0.5 | B | **91.97** | 90.16 | 37.98/36.75/37.82 | 35.22/36.10/37.14 | 37.04/36.25/37.41 | 34.69/35.86/36.98 |
| dng720 @1.0 | A | 93.85 | 94.05 | 39.69/38.22/38.94 | 38.19/37.08/37.95 | 39.38/37.87/38.67 | 37.88/36.92/37.87 |
| dng720 @1.0 | B | **94.21** | 94.05 | 39.64/38.13/38.87 | 38.19/37.08/37.95 | 39.18/37.63/38.49 | 37.88/36.92/37.87 |
| dng1080 @0.5 | A | 91.09 | 91.08 | 36.63/35.39/36.40 | 35.32/34.67/35.75 | 36.24/35.02/36.12 | 35.05/34.52/35.70 |
| dng1080 @1.0 | A | 93.40 | 93.51 | 37.83/36.86/37.53 | 36.91/36.04/36.74 | 37.53/36.46/37.21 | 36.85/35.82/36.59 |
| dng1080 @1.0 | B | **93.78** | 93.51 | 37.72/36.69/37.39 | 36.91/36.04/36.74 | 37.54/36.46/37.19 | 36.85/35.82/36.59 |
| spotrobotL @0.5 | A | 95.50 | 93.76 | 42.50/43.55/46.81 | 39.54/42.80/46.31 | 41.71/42.92/46.21 | 36.51/42.10/45.65 |
| spotrobotL @1.0 | A | 97.65 | 97.53 | 44.89/45.56/48.54 | 42.94/44.79/48.16 | 44.14/44.80/47.88 | 40.70/44.08/47.54 |
| floorballgameL @0.5 | A | 96.63 | 95.98 | 41.87/45.48/45.15 | 40.71/44.73/44.31 | 41.72/45.34/45.02 | 40.62/44.68/44.26 |
| cf_gfx @0.5 | A | 88.39 | 83.11 | 34.10/34.09/34.39 | 30.11/33.45/33.41 | 33.09/33.79/33.95 | 28.93/33.18/33.18 |
| cf_gfx @1.0 | A | 93.36 | 92.67 | 36.60/35.60/36.01 | 34.23/34.68/34.75 | 36.17/35.11/35.57 | 33.77/34.38/34.40 |

Reading: with config A, NEG was 0.1-0.2 below today on the two grainy 1.0 points while PSNR was +0.8..+1.5
dB on every plane — the 1/3 dead zone and the hysteresis erased grain. Config B (offset 0.45) recovers it
(+0.17, +0.27 NEG) at unchanged PSNR class; T10 also tried "no hysteresis" (THETA=0): NEG 93.46, worse,
so the 1/4 hysteresis stays. Config B was not re-run on spot/floor/gfx/dng1080 @0.5 (budget); A already
beats today there. All CPP rates are model entropy <= today's coded rate / 1.10 (ESTIMATED overhead).
Motion cells highwaydriveL and volleyballgameL: volleyball modelled (row stats, legality, exactness) without
a today decode; highwaydriveL not run.

Artifact tools on frame 8 (steady), both codecs, `out/eval/<cell>/*_tools.txt`:
| cell | smudgegroups Y/Cb/Cr CPP / today | artifactmap regions Y/Cb/Cr CPP / today | flatplane % flat textured blocks Y/Cb/Cr CPP / today |
|---|---|---|---|
| dng720 @0.5 | 0/0/0 / 0/0/0 | 0/0/0 / 16/0/0 | 38.2/48.5/69.3 / 41.9/82.8/83.3 |
| dng720 @1.0 | 0/0/0 / 0/0/0 | 0/0/0 / 0/0/0 | 34.0/9.0/31.1 / 33.2/25.2/50.8 |
| cf_gfx @0.5 | 0/0/0 / 0/0/0 | 0/0/0 / 35/0/3 | 46.6/73.2/64.8 / 47.5/82.1/75.8 |
| cf_gfx @1.0 | 0/0/0 / 0/0/0 | 0/0/0 / 0/0/0 | 45.5/16.1/32.9 / 41.4/52.7/46.1 |
| dng720 @0.5 B | 0/0/0 / 0/0/0 | 0/0/0 / 16/0/0 | 37.4/46.5/69.5 / 41.9/82.8/83.3 |
| dng1080 @0.5 | 0/0/0 / 0/0/0 | 0/0/0 / 6/0/0 | 49.6/39.7/69.3 / 52.3/82.0/84.1 |
| dng1080 @1.0 A | 0/0/0 / 0/0/0 | 0/0/0 / 0/0/0 | 41.2/9.3/26.1 / 27.5/14.5/36.6 |
| dng1080 @1.0 B | 0/0/0 / 0/0/0 | 0/0/0 / 0/0/0 | 41.5/10.2/29.7 / 27.5/14.5/36.6 |
| spotrobotL @0.5 | 0/0/0 / 0/0/0 | 0/0/0 / 0/0/0 | 49.0/62.3/67.1 / 48.0/65.1/69.0 |
| spotrobotL @1.0 | 0/0/0 / 0/0/0 | 0/0/0 / 3/0/0 | 33.0/34.9/57.6 / 38.7/44.6/56.7 |
| floorballgameL @0.5 | 0/0/0 / 0/0/0 | 0/0/0 / 1/0/0 | 52.4/68.3/72.9 / 57.0/70.7/76.0 |

Flatness: CPP flat-block fraction is lower than today on 26 of 30 plane-points; it is HIGHER on dng1080
@1.0 luma (41 % vs 27 %) and marginally on 3 others (spot @0.5 Y +1.0, spot @1.0 Cr +0.9, cf_gfx @1.0 Y +4.1).
The owner's zero-flat bar is not met by either codec.


---------------------------------------------------------------------------------------------------------
## 8. IP provenance
- Haar / S-transform pair (Haar 1910; S-transform integer form, 1980s) — expired/public.
- Predicted pair difference, 2/6 ("TS") form: Zandi et al. CREW (Ricoh, 1995); Said & Pearlman S+P (1996);
  Villasenor et al. filter evaluation (1995). Any patents filed 1994-96 have expired.
- Lifting integer invertibility: Sweldens (1996), Calderbank et al. (1998) — public.
- Position-alternating rounding: own work (a dither-free parity alternation; classical round-half-even idea).
- Decoder-computed legal intervals for a pair difference: own work (interval arithmetic on a two-sample
  box); related to SA12's per-pair clamp (own work of this project).
- Canonical boundary index: own work of this project (expert memo 011 §2.2 form).
- Lattice-locked (index-domain) temporal prediction: own work in this form; the underlying idea — using the
  previous frame to predict/condition the coding of current quantisation indices — is old public practice
  (motion-compensated context modelling, 1990s; conditional coding of indices). Not an MPEG/AVC/HEVC tool;
  no coded residual in the value domain.
- OBMC: Orchard & Sullivan (1994) and H.263 Annex F (1996): 30 years old, expired. (H.263 is named only as
  the dating source; nothing from AVC/HEVC is used.)
- Block matching motion search: public since the 1970s-80s.
- tANS: Duda (2013/14), public-domain algorithm, used by zstd; allowed by C1. No rANS, no CABAC.
- Dead-zone scalar quantiser, DPCM: public for decades.
- Line-/precinct-based continuous wavelet processing with slices as coding units: JPEG 2000 Part 1 (2000,
  royalty-free baseline) precincts; line-based DWT (Chrysafis & Ortega, 1998-2000). Note: the owner rule
  "legal-clean outranks quality" — the resemblance to JPEG XS's architecture (continuous transform, slices
  as rate units) must go to the legal team for confirmation BEFORE building; the elements themselves predate
  XS (2019).

---------------------------------------------------------------------------------------------------------
## 9. Prior failures checked (records grepped: LEDGER_SANDBOX_v2.md, LEDGER_v5_3_5.md, memo)
| failed element | where recorded | why it does not apply / what CPP does instead |
|---|---|---|
| mirrored bottom row + boundary blend (OMC seams, smudges) | S5.344-S5.347 | no slice-local transform: nothing to mirror or blend |
| closed slices, extrapolated bottom (SA12 CLP-1, step +0.16) | S5.361, S5.366 | CPP is not closed at slices; causal/extrapolated variant measured and rejected (T4) |
| bracketed slices, anchor row (SA13, +7..23 % at 8 rows) | S5.362 | no anchor row; every block uses the same symmetric predictor |
| shifted causal slices, first-row gain 7/8 (SA14) | S5.365, S5.369 | no row has a different synthesis gain: all pairs identical |
| continuous 5/3 (coordinator, S5.349): latency 720p50 4:2:0, 8K memory, A5 damage, XS resemblance | S5.349 | pair pyramid look-ahead is 8 lines (not 9-21), S = 4 at 720p keeps 720p50 at today's figure; 4:2:0 chroma Lv=1; memory: owner ruling (URAM, no memory constraint) and ~11 Mbit total; A5: damage = slice + 8 rows, refresh is picture-neutral (lattice lock), so the "refresh no longer isolates" failure does not arise; resemblance: legal team (section 8) |
| "slice k's clamps depend on slice k+1" (S5.349) | S5.349 | CPP's clamps depend only on already-received units (look-ahead means are sent earlier) |
| predict-only / per-sample clamp legality (-2.4..-4.8 dB) | S5.212, S5.349 | confirmed dead (T1); CPP keeps the lowpass (pair mean) |
| index capping, repair engine, K-round projection, plan-search lock | S5.212-S5.342 | none: legality is a decoder rule; no iteration; plan read off the lattice |
| injective dequantisation moving samples away (SA14 v2) | S5.368 | no off-lattice values; clamped values sit on the legal boundary |
| rails bit cost (SA14 RAIL symbols, +10.9 %) | S5.368 | no rail symbol; T5 bits ratio ~1.000 at operating rates |
| REXT dense-rail non-convergence (SA13) | S5.362 | no iteration; the interval rule is per coefficient |
| vertical-causal coding (-0.3..-1.2 dB, cast) | S5.353-S5.358 | not used |
| 16x16 motion grid; per-block mode | S5.366, S5.180 | OBMC; no per-block mode |
| decoder-derived vectors fail loss recovery | S5.29 | vectors transmitted |
| refresh phase not in the image (S5.235), interleaved refresh | S5.235, S5.366 | irrelevant under lattice lock: refresh does not change the picture |
| clean-region rule cost 0.2 NEG (SA12) | S5.366/367 | only for the one-way-link background sweep; joins use the lattice lock instead |
| rung / flat fallback, escalation ladder | S5.344, memo | terminal guard is hint-kept (MC lattice prediction), never LL-only |
| HVBC 16x16 tile grid, waxy flat patches | Issues_to_fix, memory | no tiles, no per-tile parameter; zeroed detail = slope prediction |
| floor rounding cast | memory (colour cast = lifting rounding) | position-alternating rounding (T9) |

---------------------------------------------------------------------------------------------------------
## 10. Risks (ordered)
1. **Rate control is the weakest point.** (a) The still-region rule (2.8) is required by lattice-locked
   prediction and is unmeasured; mixed regions (a moving object over a still background inside one
   256-column knot region) would requantise their still part when the knot changes. (b) Exact CBR relies on
   a one-pass estimate + credit + a hint-kept terminal guard; how often the guard fires and whether a
   partly hint-kept slice is visible in fast motion is unmeasured. The model used one step per frame.
2. Coded rate: all rates are entropy x 1.10 (assumed static-tANS overhead).
3. Motion: integer-pel vectors estimated from decoded history (one frame late by construction); half-pel
   is the known open lever (memory) and is not modelled. Motion cells measured only in part (5.6).
4. Legal: the JPEG-XS-like architecture (continuous transform, slices as rate units) — legal team first.
5. Flatness bar (zero flat textured blocks >= 0.5 bpp) not met on grainy content (38-69 % flat blocks at
   dng720 @0.5, better than today's 42-83 %).
6. Graphics at very low rate: the boundary-preference rule costs +5.6 % Y bits at 0.2 bpp on cf_gfx (fix:
   use it only for exact targets).
7. 8K60 DDR bandwidth ~62 % of one DDR4-2400 interface (needs the PL DDR port).
8. Luma flatness regression on dng1080 @1.0 (41 % flat textured blocks vs today's 27 %) although NEG and PSNR
   are higher: the owner's eye must judge that cell first.
9. Model gaps: the sequence runs used a scheduled one-slice-per-frame refresh coded with hint-free CHOICES
   (the later-fixed rule keeps the hinted choice; picture-neutral refresh was verified only in T8); no
   4:2:0, 4:4:4, 8/12-bit or limited-range sequence was run (legality boxes were exercised only at full
   10-bit range; the interval algebra is range-agnostic); highwaydriveL not run; half-pel absent.
10. Loss recovery needs the refresh to cover the full damage footprint (T8): a too-narrow refresh leaves a
   residue that re-grows through the hints. The footprint rule (2.9) is derived, measured on one case.
