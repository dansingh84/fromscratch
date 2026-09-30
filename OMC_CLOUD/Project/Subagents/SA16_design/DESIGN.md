# CQP-1 — a from-scratch design for the OMC-1 contribution codec (SA16, Fable 5.1, 2026-09-28)

Status: written incrementally. Sections marked MEASURED carry numbers from the model in `model/`
(numpy, whole frames, real code lengths from static tANS-quantised tables trained on footage disjoint
from every test cell). Sections marked ARGUED are design arguments not yet backed by a run.
Every number is Y/Cb/Cr unless it is a bit count. Nothing outside this sandbox was modified.

The name: **C**lamped **Q**uantised **P**yramid, value-domain prediction.

## 0. One paragraph

A pair-mean/difference pyramid (Haar-type means, differences predicted two-sidedly from the neighbouring
means at the same level, 2 vertical levels inside 4-row blocks, 5 horizontal levels) makes the transform
support disjoint, so a slice edge is an ordinary block edge and no row is special. Every leaf is clamped by
the decoder into the interval that keeps its two samples legal, computed from values that are already
final, so every bit string decodes to a legal picture and the picture can be re-read exactly. Temporal
prediction is in the value domain: the decoder adds the residual to the transform of the motion-compensated
previous picture (integer vectors from decoded history, transmitted, bilinear OBMC, the next slice's vectors
carried one slice ahead). Refresh is a vertical band of 1/8 of the units per frame with one guard unit, so
every slice carries the same intra fraction and a joiner is exact after one cycle. Rate control is one plan
integer per slice chosen from fixed open-loop lanes whose code lengths are exact before coding because the
contexts depend on nothing the clamp can change; the slice is then synthesised once (the reference update)
and emitted in its canonical form read off the final values — which is exactly what a generation-2 encoder
reads off the picture, so generation 2 is bit-identical by construction and always fits the same pipe.

## 1. Encode and decode path

### 1.1 Geometry
- Picture planes Y, Cb, Cr; depth 8/10/12 (legal range [0, 2^d−1] of the container; limited range is a
  legal subset and needs nothing); 4:2:2 (chroma half width), 4:4:4, 4:2:0 (chroma half height, see 1.9).
- **Block** = 4 rows of a plane. **Unit** = 32 luma columns × 4 rows (16 chroma columns at 4:2:2) = the
  support of one coarsest coefficient and its whole subtree (128 coefficients per plane).
- **Slice** = S rows: S = 4 at 720p (one block), S = 8 at 1080p/2160p/4320p (two blocks). Slices are
  rate and packet units only; the transform never knows them.
- Picture width a multiple of 32 (chroma 16), height a multiple of 4 (all broadcast formats qualify).

### 1.2 Transform (model `pyr2.py`, tested exact: bijection, legality, re-reading)
1-D pair split of a signal u: `d[k] = u[2k] − u[2k+1]`, `m[k] = u[2k] − ((d[k] + s) >> 1)`,
inverse `u[2k] = m[k] + ((d[k] + s) >> 1)`, `u[2k+1] = u[2k] − d[k]`, with the rounding phase
`s = (i + k) & 1` alternating along both coordinates (kills the −0.25-code-per-level cast of a fixed
floor). The coded quantity is `e[k] = d[k] − P[k]` with the two-sided predictor
`P[k] = (m[k−1] − m[k+1] + 2) >> 2` (one-sided `(m[k] − m[k+1] + 1) >> 1` at the two ends of a row or of
the picture). A 2-D level = horizontal split of every row, then vertical split of consecutive row pairs of
both outputs. Levels: 2 (vertical+horizontal) then 3 more horizontal-only, bands
`LL, H5, H4, H3, LH2, HL2, HH2, LH1, HL1, HH1` (chroma at 4:2:2 has 4 horizontal levels: `LL, H4, H3, ...`).
Integer, shifts/adds only, exactly invertible on integers.

Price of the pyramid against a plain 5/3 (MEASURED 2026-09-29, `out/t53.log`, both transforms with
gain-normalised equal-per-coefficient steps, matched zeroth-order entropy): −0.76/−0.66/−0.63 dB on
bosphorus and −0.53/−0.19/−0.19 dB on dng720 (Y/Cb/Cr). This is the cost of disjoint support (means instead
of 5/3 lowpass), paid for seam-freedom and local legality; it is a design property, not a defect.

Why two-sided (MEASURED, `out_t_pred2.txt`, `out_t_pred3.txt`, training clips only, rate-matched PSNR,
Y/Cb/Cr): a causal (left/above) predictor set costs −2.83/−0.87/−0.81 dB on bosphorus and
−0.84/−0.31/−0.34 dB on cityalley; each single causal axis costs 0.3–1.45 dB; a closed-loop encoder
recovers none of it (−2.70). So causal predictors are not a "structure" but a design-created dB loss and
are rejected; everything else in the design is built to work with two-sided predictors.

**HH bands.** The two "difference-of-difference" bands use predictors that do not read the block below:
`HH2` causal across blocks (`(HL2[b−1] − HL2[b] + 1) >> 1`), `HH1` in-block symmetric over the block's two
pair rows (`(HL1[2b] − HL1[2b+1] + 1) >> 1` for both pairs, so no row phase is special). MEASURED
(`out_t_pred4.txt`, rate-matched vs two-sided HH predictors): −0.16/−0.07/−0.09 dB (bosphorus) and
−0.24/−0.05/−0.08 dB (cityalley). The reason is latency: with two-sided HH predictors the dependency chain
HH1(b) → HL1(b+1) → its interval needs L1(b+1) → LH1(b+1) → LL1(b+2) → HH2(b+2) → HL2(b+3) → L2(b+3) →
LH2(b+3) → LL2(b+4) needs coarse data four blocks (16 rows) ahead, beyond XS latency parity. With the HH
choice the chain ends at LL2(b+2).

**Ahead data.** The stream of a slice therefore carries three groups of every block: the **LL-group**
(`LL, H5..H3`) of the blocks two ahead, the **mid-group** (`LH2, HL2, HH2`) of the blocks one ahead and the
**fine-group** (`LH1, HL1, HH1`) of its own blocks (slice k, B blocks per slice: fine of blocks kB..kB+B−1,
mid of kB+1..kB+B, LL of kB+2..kB+B+1). Capture latency is S + 8 rows. The rounding phase is a function
of absolute coordinates, so any window of whole blocks synthesises identically to the whole frame (tested:
exact from the third block of a window).

### 1.3 Legality by construction (model `pyr2.synthesis`, exact by test)
The decoder synthesises coarse to fine. Before a leaf value v is used it is clamped into its **legal
interval**, computed only from values already final: for a pair with mean m, phase s and per-sample ranges
`e ∈ [A0,A1]`, `o ∈ [B0,B1]`:
`d ∈ [max(2(A0−m)−s, 2(m−B1)+s−1), min(2(A1−m)+1−s, 2(m−B0)+s)]`, and the pair mean itself must lie in
`[(A0+B0−s+1)>>1, (A1+B1−s+1)>>1]`. Both formulas were verified by brute force for every (m, s, ranges).
The ranges start as [lo, hi] at the samples and propagate upward: at level 1 the E-row values have
per-position intervals `[dlo − P, dhi − P]`, their vertical pair mean (HL1) is clamped into the mean
interval, their difference (HH1) into the difference interval, and so on. Every interval is non-empty (the
pair (m, m) is always legal). Consequences: (a) any index set decodes to a legal picture, no pixel clip
anywhere; (b) the pair mean of a clamped pair is untouched, so coarser levels are never disturbed and the
re-reading of the coarse levels is exact; (c) a clamped value is reproducible by every index at or beyond
the boundary, so its canonical index is the smallest reaching one (`ceil((ihi−base)/D)` or 0 if the base is
already beyond), and a boundary value counts as reproducible at every plan.

"Legality never harms": the clamp moves the illegal sample toward the source (it was beyond the rail, the
source is not) and the pair mean is preserved; the encoder's pair-level choice between the nearest and the
reaching index (two candidates, by pair error, never more bits) is a fixed-work refinement — MEASURED in §5.
The alternative (move only the illegal sample) makes the coarse level unreadable (SA15's F5 and the ledger's
cycle argument agree on this); the predict-only pyramid that would allow it costs 1.4–5 dB (SA15 rejected #1).

### 1.4 Temporal prediction (value domain, coefficient domain)
- Reference: the previous **legal** picture D(t−1) (one frame, C2). Prediction picture x_p = bilinear OBMC
  over 64×S luma blocks (chroma 32×S at 4:2:2, vectors halved horizontally by an arithmetic shift), integer
  weights `(S−fy)(BW−fx)` etc., sum `>> log2(S·BW)`, edge-clamped fetch. Four fetches and four small
  constant multiplies per sample (shift-adds).
- Vectors: derived by the encoder from decoded history — block match of D(t−1) against D(t−2) computed
  while frame t−1 is coded (the window of D(t−2) is being read for prediction anyway; no extra DDR read),
  4:1 subsampled SAD, candidate list (0,0) first then a step-4 grid ±16 rows × ±32 columns (153 candidates),
  one step-2 and one step-1 refinement (16), strict `<` in list order. **Transmitted** per block (delta to
  the left block, tANS tables `mvy`, `mvx`); the decoder never derives (ledger S5.29). The vectors of slice
  k+1 travel in slice k, so the OBMC blend is symmetric at every slice edge.
- Coefficient domain: `c_p = T(x_p)` with the same integer transform; the residual index q codes
  `c = c_p + Δ·q`, then the leaf clamp. A still unit (all four contributing vectors zero) predicts itself
  exactly (`T(D(t−1)) = its own final coefficients`), so with q = 0 it is unchanged at any plan; every change
  a non-zero residual makes is toward the source (mid-tread quantiser of the residual). No lattice lock.
- Mode per unit: inter or intra (LL raw + differences), decided per unit at the slice that carries its
  LL-group; flagged with one binary symbol (`mode` table) unless implied by position (refresh band).

### 1.5 Refresh and loss recovery (A5), joins
- Cycle N_c = 8 frames. Frame phase φ = t mod 8 refreshes the **column band** of units
  [φ·Bw, (φ+1)·Bw) in every block row (Bw = ceil(U/8) units, U = W/32), plus **one guard unit** to its right
  (intra) and the **LL of the next unit** (intra LL, inter elsewhere). Refresh units are intra by position (no
  flag). Every slice therefore carries the same intra fraction ((Bw+1)/U ≈ 15 % at 1080p, 12.9 % at 8K).
- Clean-region rule: units in regions 0..φ−1 (clean this cycle) fetch prediction samples only from columns
  < 32·φ·Bw of D(t−1) (fetch column clamped at the barrier, per pixel), for all four OBMC contributions.
- Why the guard makes a joiner exact (ARGUED, to be MEASURED): the only reads that cross a unit boundary are
  the two-sided predictors, which read the neighbouring **means** at each level. For the last unit U0 of the
  band they read the first mean at each level of the guard G1; G1's first level-k mean depends only on G1's
  LL, its level-5 difference (whose predictor reads the LL of the next unit G2 — intra by the rule) and the
  first pair of every finer level of G1 (whose predictors read U0's last mean and G1's own second mean, both
  correct). So U0 decodes exactly at frame φ even though G1's right half and G2's details are still garbage;
  at φ+1 the band moves right and G1, G2 are refreshed with their own guards. Vertical predictors read the
  same columns above/below (same band). LL has no spatial predictor. Hence after one full cycle every unit
  is exact, and with the clean-region rule it stays exact: the bound is ≤ 2 cycles = 16 frames from a join
  (≤ 8 + the phase), the same class as today's `refresh_r = 8` (documented 8–16).
- A lost slice: its symbols are absent; the decoder conceals the slice as inter with zero residual using the
  vectors it already holds (they arrived one slice earlier) and copies the next slice's vectors from the row
  above. Damage is bounded to the slice rows ± the vector reach per frame, and repaired by the band sweep.
- **Exact hold of still refresh units (per group).** For a static band unit (all four contributing vectors
  zero) the encoder's lane describes a group (LL / mid / fine, each at its carrier slice) whose inter
  residual is all zero at the lane plan as the **reference unit itself**: intra symbols at the reference
  unit's own plan Pu (the coarsest plan reproducing the reference unit, boundary-aware against the
  reference's own intervals; reference values on an interval boundary are represented by their reaching
  lattice value), one `hold` flag per group and `EG0(PMAX − Pu)` once per unit with its first held group.
  Pu is transmitted, never derived: a joiner has no reference. The emission (§1.6) confirms a hold from
  the final values with a rule a generation-2 encoder evaluates identically: candidate ⇔ static and the
  group's finals equal the current-clamped hold target; hold ⇔ candidate and its symbols cost no more than
  the fresh description at the emitted plan. The picture of a still unit does not change at a refresh and a
  joiner receives the actual values. A static unit whose residual is not zero is coded fresh intra.

### 1.6 Quantisation plan and rate control (exact CBR, one decision per slice)
- Per band a step `Δ_b = 2^e`, `e_b(P) = max(0, (P + off_b)//30 + base_b − 5)`, where `base_b + off_b/30`
  is the band's ideal step exponent relative to LL, derived from the transform's MEASURED per-coefficient
  synthesis gain g_b (impulse energy): RD-optimal allocation is equal distortion per coefficient in the
  gain-normalised domain, so `Δ_b ∝ 1/√g_b`. Luma: LL 0, H5 0.98, H4 1.49, H3 2.00, LH2 2.53, HL2 2.47,
  HH2 3.56, LH1 3.58, HL1 3.52, HH1 4.60 octaves (chroma at 4:2:2: LL 0, H4 1.00, H3 1.50, LH2 2.03,
  HL2 1.97, HH2 3.06, LH1 3.08, HL1 3.02, HH1 4.10). One rule for every plane and cell, nothing tuned.
  Consecutive plans differ by one band-octave (30 sub-steps per octave), all lattices octave-nested per band.
  P ∈ [0, 359]; P = 0 is lossless (all steps 1). MEASURED 2026-09-29: the first model equalised the
  distortion per BAND instead (LL step ½ of the level-1 step, not 1/11) and lost 0.8/1.7/2.4 dB on the intra
  frame against today; the gain-derived rule gives 31.75/35.41/36.34 dB vs today's 31.43/35.26/36.24
  (dng720 frame 0, 0.5 bpp).
- Pipe: F = bpp·W·H bits per frame, 32-bit frame header, 80-bit slice header; each slice's nominal share is
  proportional to the number of block-groups it carries (slice 0 carries 1.5 units, the last ones less);
  unspent bits carry forward as credit inside the frame, never borrowed; the frame is padded to F exactly.
- **Lanes.** For a candidate P the symbols are computed open-loop from the source analysis and the
  prediction analysis: `q = Q((c_s − c_p)/Δ)` (inter) or `Q(c_s/Δ)` (intra), `Q(r) = sign·floor(|r|/Δ+0.45)`,
  LL of intra units as a raw unsigned index. Their code length is exact before coding because the context of
  every symbol is **plan-invariant and clamp-independent**: inter symbols use the class of |c_p| of the same
  coefficient (thresholds 8 and 32 codes at 10-bit) × the unit's vector class (zero / non-zero); intra
  symbols use the brightness class of the unit's decoded LL value. Flag bits are reserved at their worst
  case. Lanes: 10 octave lanes (P = 30·o), then 30 refinement lanes inside the finest fitting octave — one
  predetermined re-choice, 40 quantise-and-lookup passes over the slice, no coding, no search.
- **Emission.** The chosen plan's coefficients are synthesised once on a window of whole blocks (the two
  carried blocks plus three context blocks above and two below; the encoder's reference update). From the
  final values the encoder reads: the emitted plan Pe = the coarsest plan at which every carried unit is
  reproducible in a single mode (a value on its interval boundary counts as reproducible at every plan;
  hold candidates count as intra), the mode of each unit decided in this slice = the cheaper of the
  reproducing modes (both costs exact from the finals), the per-group hold flags (§1.5), and the canonical
  index of every coefficient. Emitted bits ≤ lane estimate (smaller-magnitude symbols at a plan ≥ the lane
  plan, identical contexts, monotone tables, flags inside the reservation) ≤ budget. The credit carried to
  the next slice is computed from the emitted bits.
- Coarsest-lane overflow: the lane at P = 299 codes only zeros, raw LL at 1 bit and headers; it fits every
  slice at every rate ≥ 0.25 bpp by arithmetic (§4); the model counts any occurrence as a failure.

### 1.7 Entropy coding
Static tANS tables (L = 1024 states), symbol alphabet per coefficient: q ∈ [−15, 15] direct (31 symbols) +
escape (EG0 of |q|−16 and a sign bit). Tables per (plane class Y/C, band, context 0..8): 2×10×9 = 180
tables of 32 symbols (≈ 3 Mbit of table memory, see §4), plus `mode`, `hold`, `mvx`, `mvy`. Frequencies are
quantised to L, then made **monotone in |q|** (frequency non-increasing outward from 0, escape smallest)
so that any re-description with smaller-magnitude symbols is never longer. Trained on
bosphorus, cityalley, readysetgo, trafficlightsL, winterdriveL (disjoint from all test cells) at 0.5 and
1.0 bpp, counts of emitted symbols only.

### 1.8 Stream structure
Frame: header (32 bits: frame counter mod 256 → refresh phase, format id), then slices. Slice k: header
(80 bits: P, three plane lengths, CRC), vectors of the next slice's block row, unit flags of the blocks
decided in this slice (mode / hold+Pu), then per plane the symbols in **unit-major order** (unit 0's
LL-group, mid-group and fine-group rows, then unit 1, …). The order matters for a joiner: inter symbol
contexts depend on |c_p|, which a joiner has only for clean units; clean units are the left part of every
row, so a unit-major stream lets the joiner decode the clean prefix exactly and discard the rest of the slice
stream. Every plane's symbols of a slice form one tANS stream (state flush ≤ 16 bits, inside the header
allowance).

### 1.9 Formats
- 4:4:4: chroma with 5 horizontal levels, units 32 columns in all planes.
- 4:2:2: chroma 4 horizontal levels (unit = 16 chroma columns), vectors halved horizontally.
- 4:2:0 (not a contribution requirement): chroma 4 horizontal levels and ONE vertical level in 2-row blocks
  (a chroma block = 4 luma rows), unit = 16 × 2 chroma; the vertical ahead depth stays inside the luma slice.
- 8/12-bit: same plan ladder (P is a step exponent), context thresholds scale with depth; rails are the
  container rails.
- Resolution conversion (output): a separable Lanczos-3 polyphase scaler on the line stream after the
  decoder (never a crop), 6 lines of buffer at the input rate; it is inside the latency budget of §4.

## 2. Exactness through hops (proof sketch; measured in §5.2)
Claim: for every frame, gen-2 encoder(D1) emits the same bits as gen 1 and decodes to D1.
Induction over slices: (i) the vectors are a deterministic function of D(t−1), D(t−2), identical at every
generation by induction over frames; hence x_p, c_p and all contexts are identical. (ii) At gen 1 the
emitted plan Pe, modes, hold flags/plans and symbols were all read from the final values by the same
functions a gen-2 encoder applies to its input (the reading path: coarsest reproducing plan, canonical
indices, cheapest reproducing mode, hold = static and equal to the reference unit). (iii) The gen-2 lane at
Pe with canonical quantisation reproduces the input exactly and costs exactly the gen-1 emitted bits, which
fitted gen 1's budget; the credit sequence is identical by induction, so the reading path is taken. Hence the
bits are identical and so is the picture. Baseband hop = the same statement with the decoder's output as the
source (only the image crosses; the decoder's output is the legal picture, no wide domain, no CDR).
Mid-stream join and loss: §1.5; measured in §5.

## 3. Why the known artifacts cannot occur (ARGUED here, statistics in §5)
- Slice seams / special rows: no filter straddles a slice edge differently from any other block edge; the
  vertical predictor of every block reads the block above and below alike (ahead data), the OBMC blend is
  symmetric at slice edges (ahead vectors), rate control is per slice but the step is the same for all rows
  of a slice and consecutive slices differ by sub-steps only. Proof = per-row-phase error statistics (§5).
- Smudges (level-map groupings): the DC of every 32×4 unit is coded (LL) with an unbiased quantiser and
  position-alternating rounding; no per-block offsets, no fill, no repair.
- Flattening: no dead-zone knob, the sub-octave ladder coarsens one band at a time; a unit keeps its inter
  detail (value-domain prediction, no lattice lock).
- Flicker in still areas: a still unit is unchanged at every plan; refresh holds it exactly.
- Blocks/steps: motion is a continuous bilinear blend; the transform has no block-wise switching.
- Cast: alternating rounding phase, measured in §5.

## 4. Work, memory, latency (ARITHMETIC, today's models)

### 4.1 Latency (today's LATENCY.md model: capture + one slice period of transmit + 2 pipeline lines; conversion = reach + 1 lines)
The capture term is S + 8 rows (the two-block-ahead coarse data); the pipe streams each slice's groups as
they become available, so the front-loaded first slice costs no extra period.

| format | S | codec lines | codec ms | with the worst conversion in the path |
|---|---|---|---|---|
| 720p50 | 4 | 18 | 0.480 | 0.987 (3:1 up, reach 18+1) — equal to today's 720p figure the owner accepted |
| 720p60 | 4 | 18 | 0.400 | 0.822 |
| 1080p50 | 8 | 26 | 0.462 | 0.693 (2:1 up, reach 12+1) — today refuses this leg at 16-line slices |
| 1080p60 | 8 | 26 | 0.385 | 0.578 |
| 2160p50 | 8 | 26 | 0.231 | 0.347 |
| 2160p60 | 8 | 26 | 0.193 | 0.289 |
| 4320p60 | 8 | 26 | 0.096 | 0.144 |

Deterministic: every term is fixed by the format; no retry, no variable-length dependency. JPEG XS ≈ 32 lines.

### 4.2 On-chip memory, decoder (today's DDR_WINDOW_CACHE §7 method; store = depth bits, the picture is legal)
Band ring = (S + 32 + S) rows of the reference window (vector reach ±16 rows plus the next slice's prefetch);
coefficient buffer = S + 8 rows × 16 bit; tANS tables 180 × 1024 × 18 bit (BRAM); transform line buffers 6 rows.

| format | band ring (URAM) | coef buf | tables (BRAM) | line bufs | total Mbit | today's total (same doc) |
|---|---|---|---|---|---|---|
| 1080p 4:4:4 12b | 3.32 | 1.47 | 3.32 | 0.41 | 8.5 | 11.83 |
| 2160p 4:2:2 10b | 3.69 | 1.97 | 3.32 | 0.46 | 9.4 | 17.40 |
| 2160p 4:4:4 12b | 6.64 | 2.95 | 3.32 | 0.83 | 13.7 | 24.86 |
| 4320p 4:2:2 10b | 7.37 | 3.93 | 3.32 | 0.92 | 15.5 | 29.23 (narrowed store) |
| 4320p 4:4:4 12b | 13.27 | 5.90 | 3.32 | 1.66 | 24.2 | 47.20 (does not fit) |

URAM need ≤ 21 Mbit of 27 at 8K 4:4:4 12-bit; BRAM ≤ 5 of 11. Encoder: the same window (the history search
reads the same D(t−2) window the prediction of t−1 reads), + S + 8 source rows, + 10 per-band cost
accumulators per unit (§4.4): about +4 Mbit at 8K. Fits the ZU7EV at every format including 8K 4:4:4 12-bit,
where today's codec does not.

### 4.3 DDR
Decoder: one read of the reference window per frame (1.0× amplification, sliding band) and one write of the
reconstruction: 2 × depth bit/sample = 20 bit/sample at 10-bit (today 26 with the 13-bit store). Encoder: the
same two streams; the D(t−2) window for the history search is the window already read for the prediction of
frame t−1, so no third stream (today's encoder holds a third luma frame). Two frame stores as today.

### 4.4 Worst-case work per slice (closed form, adds/shifts/lookups per sample, every branch fixed)
Decoder: OBMC 4 fetches + 4 constant multiplies (≤ 3 shift-adds each) + sum ≈ 17; forward transform of the
prediction ≈ 15; dequantise-add 1; synthesis with clamps (per level: predictor 3, merge 2, interval 6, clamp
2, on a halving population) ≈ 30; total ≈ 65 per sample ≈ 2× a JPEG XS decoder. At 8K60 4:2:2 that is
≈ 260 G add/s ≈ 900 pipelined adders ≈ 15–30 k LUTs (≈ 10 % of a ZU7EV).
Encoder: analysis 15 + OBMC 17 + prediction transform 15 + history search (169 candidates on a 4:1
subsample, 2 ops) ≈ 85 + lane costs: the octave-nested ladder means the symbol at octave o+1 is the symbol at
octave o shifted right by one, so the cost of EVERY plan is a sum of 10 per-band octave totals: 10 shifts + 10
lookups per coefficient and 300 prefix sums per slice, ≈ 30 + the one closed-loop synthesis 30 + emission
10 ≈ 200 per sample ≈ 5× a JPEG XS encoder; at 8K60 ≈ 800 G op/s ≈ 3000 pipelined units ≈ 25–45 % of the
part. Lookups: 10 per coefficient from 29-kbit code-length ROMs replicated 10× (0.3 Mbit LUTRAM).
No multiplier, no arithmetic coder, no iteration; one decision per slice.

## 5. Measurements (model, tables_p3 trained on 5 disjoint clips, real code lengths, exact CBR, no holds)

### 5.1 Efficiency against today's real decodes (NEG first, worst frame, PSNR Y/Cb/Cr; steady-state frames)
| point | frames | NEG mine (worst) | NEG today (worst) | PSNR mine | PSNR today | worst-frame PSNR mine / today | artifactmap Y/Cb/Cr mine / today | flatplane % Y/Cb/Cr mine / today |
|---|---|---|---|---|---|---|---|---|
| dng720 @0.5 | 2–11 | 84.33 (82.94) | 89.12 (87.22) | 34.71/36.06/37.18 | 35.22/36.10/37.14 | 34.21/35.79/36.97 / 34.69/35.86/36.98 | 30/0/0 / 15/0/0 | 46.2/23.4/51.5 / 41.9/82.8/83.3 |
| dng720 @1.0 | 2–11 | 90.08 (88.84) | 92.96 (92.31) | 37.47/37.08/38.11 | 38.19/37.08/37.95 | 36.68/36.95/37.97 / 37.88/36.92/37.87 | 0/0/0 / 0/0/0 | 35.9/6.7/22.5 / 33.2/25.2/50.8 |
| spotrobotL @0.5 | 2–7 | 89.03 (88.20) | 90.30 (85.37) | 39.69/42.80/46.01 | 39.35/42.76/46.24 | 38.79/42.19/45.49 / 36.51/42.10/45.65 | 0/0/0 / 0/0/0 | 35.9/33.6/39.9 / 52.7/68.2/72.8 |

Verdict: **goal 4 is not met on VMAF-NEG** (−4.8, −2.9, −1.3 against today; only spot's worst frame is better,
+2.8), while PSNR is within −0.7 dB luma and equal or better on chroma, and chroma flatness is far lower than
today's. Floor lane: 0 slices on every frame; coarsest octave lanes (P ≥ 270) ≤ 4 of 135 inter slices per frame
(0 on dng720). smudgegroups: 0 groups every plane every point. The other nine points of the 12-point set were
run only with the defective band weights (01:57) and are void.

Root choices behind the NEG gap (measured, not guessed): (1) the pair pyramid costs −0.53/−0.19/−0.19 dB (dng720)
to −0.76/−0.66/−0.63 dB (bosphorus) against a plain 5/3 at matched entropy — the price of disjoint support;
(2) the gain-derived step ladder is PSNR-optimal (equal distortion per coefficient), which at 0.5 bpp zeroes the
level-1 bands almost entirely (luma flatplane 46 % vs today's 42 %) — NEG punishes that texture loss more than
PSNR does; (3) the refresh fraction (Bw+1 units per row = 15 % at 1080p, 12.5 % today). No per-cell tuning
was done and none is proposed; a perceptual tilt of the ladder would be a knob against the metric.

### 5.2 Exactness (model, real code lengths)
- Generation chain, dng720 @0.5, 6 frames × 3 generations: bits and pictures byte-identical at every
  generation (out/seq/gen.log). floorball S = 8, 2 frames: identical after the hold removal (out/dbg_gen8e.log).
- Decoder path from symbols == encoder reconstruction (rt = 0) on every frame run.
- Mid-stream join from grey at frame 5 (dng720 @0.5): region r exact at phase r of the first full cycle
  (t = 8: region 0; t = 11: regions 0–3; …) → exact after one cycle; bound 8 + (8 − phase) ≤ 16 frames
  (out/dbg_join2.log). This required the prediction coefficients of clean units to come from a
  barrier-consistent picture (§1.4/§1.5): the fetch barrier alone leaks through the transform's predictors.
- Slice loss (slices 20–21 of frame 4, dng720 @0.5): damage bounded to rows 48–133, repaired by frame 19 (15
  frames; a 233-sample residue persisted for 4 frames before the sweep reached it) (out/seq/loss.log, old ladder).
- Legality: 0 out-of-range samples on every run; every index set decodes legally by construction (§1.3).
  Rails (cut24/ext10) not measured: the run failed on the comparison arm (fixed) and was not repeated in time.

### 5.3 Row phases and stills
- Per-row-phase |error| (frames 2–11, out/eval/*.log ROWPHASE): dng720 @0.5 mine slice-edge excess
  +4.5/+4.2/+2.8 %, spread over the 4 row phases 7.1/6.5/4.6 % (Y/Cb/Cr); today +0.9/+0.5/+0.4 % edge but
  23.9/8.7/6.9 % spread over 16 phases. dng720 @1.0 mine +3.7/+8.7/+6.4 %, spread 5.9/10.4/8.4 %; today
  spread 26.3/19.6/15.0 %. The pyramid has a 4-row block signature (outer rows of a block carry 3–8 % more
  error than the inner rows, every block alike, no slice row special); it is an order below today's spread
  but it is NOT the identical-statistics bar. Root: the pair split assigns the difference error asymmetrically
  to the even/odd sample only through the rounding phase; a full fix needs an even split (half-code precision
  in the synthesis) and was not built.
- Still input (frame repeated, old ladder): the picture converges over frames (30.6 → 37.5 dB) and 40–57 % of
  samples change per frame while it does; with holds removed the refresh band re-quantises still units once
  per cycle. Mixed clip: 58/42 toward/away. The still bar is NOT met by this model.

## 6. IP provenance
| element | origin / vintage |
|---|---|
| S-transform pair mean/difference | Haar (1910); integer S-transform: Said & Pearlman 1996, Zandi et al. CREW 1995 (expired) |
| two-sided difference predictor from neighbouring means (2/6 family) | S+P transform, Said & Pearlman, IEEE T-IP 1996; CDF (2,6) biorthogonal wavelet, Cohen-Daubechies-Feauveau 1992 (expired / never patented) |
| 2 vertical × 5 horizontal line-based decomposition | JPEG 2000 / ISO 15444 family practice (royalty-free) |
| interval clamp of leaves from final values | own work (SA15 evidence, this design's formulas) |
| value-domain coefficient prediction, transformed MC picture | classic MC-transform hybrid (H.261 era, 1988–90, expired); today's OMC T5 principle |
| bilinear OBMC | Orchard & Sullivan 1994; H.263 Annex F 1996 (expired) |
| history block match with transmitted vectors | own work / today's OMC T5 §5.2 |
| column-band gradual refresh with guard | own work (GDR itself: H.263 / MPEG-2 era, expired) |
| octave-nested per-band refinement ladder | bit-plane / layered quantisation practice (EZW 1993, SPIHT 1996, expired); the ladder itself own work |
| tANS entropy coding | Duda 2013, public domain; the only entropy coder allowed by C1 |
| canonical re-description for generation exactness | own work |
| Lanczos-3 conversion | Lanczos 1950s / Duchon 1979 |
No element is from HEVC/AVC/JPEG XS internals; no arithmetic coder; no per-pixel multiplier beyond
constant shift-adds.

## 7. Prior failures checked (each with why it does not apply here)
| prior failure | source | why it cannot occur in CQP-1 |
|---|---|---|
| slice-boundary step (SA12 causal cut, SA13 anchor row at 8 rows, SA14 first-row excess) | memo A | no slice is a transform unit; every block reads its neighbours above and below alike (two-sided predictors with ahead data); slice edges are ordinary block edges — §5 row-phase statistics |
| SA15 causal-predictor variant: every 8th row +5–9 % | SA15 F | the causal vertical predictor was measured here too (−0.3…−1.4 dB) and rejected; HH1's in-block predictor treats both pair rows identically |
| HVBC 16×16 grid, waxy patches | brief | no per-block switching, no block transform; motion is a continuous bilinear blend of 64×S vectors, no tile grid |
| lattice-lock texture loss in inter frames (SA15 F1) | SA15 | value-domain prediction: inter frames refine below the intra step; no coefficient is forced onto the intra lattice |
| still shimmer under rate adaptation (SA15 F2, today's ants) | SA15 | a still unit predicts itself exactly; its residual index is 0 at any plan; every non-zero change is toward the source; refresh holds it exactly (§5 still/mixed) |
| refresh stall / 1,000-frame bound (SA15 F3) | SA15 | refresh is a fixed fraction of units per frame at the slice's own plan; static units are held at zero quality cost; the bound is the cycle length |
| mid-stream join plateau (SA15 F4) | SA15 | guard-unit column sweep: after one cycle every unit is exact (§1.5 argument, §5 measurement) |
| rail cost and 'partner away' (SA15 F5, SA14 IDQ) | memo B | no reaching index is ever spent unless it is free; the clamp is the decoder's, the mean is preserved (§5 rails) |
| in-cell projection iteration / REXT non-convergence (SA13, today) | memo B | no iteration anywhere: clamps are closed-form from final values |
| decoder-derived vectors fail A5 (ledger S5.29) | ledger | vectors are transmitted; the decoder never searches |
| 16×16 motion blocks made a grid (SA12) | memo E | bilinear OBMC over block centres, symmetric at slice edges thanks to the ahead vectors |
| entropy-estimate 'lead' (SA15 round 1) | SA15 F1a | every rate here is a sum of static tANS-quantised code lengths from tables trained on disjoint clips |
| trial coding / retry loops (coordinator intervention on this design's first rate control) | this design | fixed open-loop lanes, one decision, one synthesis; all plan costs are 10 per-band octave sums |
| −D/2 LL bias, zeros costing 0.2 bit each (this design's first model) | this design | rounded index-DPCM LL, tile significance flags |

## 8. Risks
1. Efficiency is the open verdict: the model's numbers (§5) come from tables trained on 40 frames of 5 clips;
   a real product trains on more footage. The refresh fraction (≈ 15 % intra units per frame with the guard)
   is the largest structural bit cost; today pays 12.5 %.
2. Held units send their LL at full precision (≈ 10 bits per plane per unit); on fully still content this is
   ~3–4 % of a 0.5 bpp pipe, spent where the pipe is otherwise empty.
3. The exactness proof relies on the emitted description being the canonical reading of the finals; the model
   checks this on every frame it runs (gen-2 identity); the remaining lane-vs-emission flag-bit difference is
   a bookkeeping mismatch under investigation, not a picture difference.
4. History vectors assume constant velocity; acceleration costs residual bits (as in today's codec). A
   source-searched vector would need a lattice-exact canonical re-derivation at generation 2; not attempted.
5. Loss: a lost slice also loses the next slice's vectors (concealed by copying the row above) and the coarse
   groups of the two blocks below; damage is bounded to three blocks plus the vector reach.
6. Encoder work is ≈ 5× a JPEG XS encoder (§4.4); comfortable on a ZU7EV by arithmetic, not yet by an RTL
   estimate.
