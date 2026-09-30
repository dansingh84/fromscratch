# SA13 — BSC-1, the Bracketed-Slice Codec (design only, 2026-09-27)

Designer: SA13 (Opus 5.5). Sandbox: `Subagents/SA13_design/`. Nothing outside it was changed.
Governing document: `Project/PROJECT_CONSTRAINTS.md` rev. 6, plus the owner rulings in the brief.
Evidence: `t1_structure.py`…`t7_rext_pocs.py` and their `*_results.txt` in this folder (numpy, intra,
full frames, every plane). Working log: `NOTES.md`.

---

## 0. Summary and constraint status

BSC-1 is a slice-based integer-wavelet codec with one-frame temporal prediction, like OMC, but
three of its structural decisions are different, each taken to remove the *root* of an OMC failure
rather than patch it:

1. **Bracketed slices (no row below is ever needed).** Each slice codes its last row first (the
   *anchor*, a 1-D row). The other rows are coded by a vertical 5/3 lifting transform on the
   closed interval [anchor of the slice above … own anchor], with both ends **fixed, decoded
   values** — never mirrored, never updated, never blended. The mirror that caused OMC's seam,
   and the blend that caused its grid smudges, do not exist. Measured (T2): same bits as the
   OMC-shape slice-local transform at equal VMAF-NEG (−10 % on spotrobotL), flat row-phase error
   in all three planes, one-slice loss reach.
2. **Legality inside the reconstruction, exactness by reading, not by searching.** The decoder's
   picture is defined as a legal picture whose analysis lies **inside every transmitted
   quantisation cell** ("in-cell"); any encoder that receives that picture recovers exactly the
   same indices by plain quantisation. Rails are handled by a new input rule, **rail extension
   (REXT)**: every encoder pushes pixels that sit exactly on a rail M codes outside the legal
   range before the transform; the decoder's reconstruction puts them back exactly on the rail.
3. **Every decision is either a deterministic function of already-decoded data, or an index
   choice whose reading is idempotent.** The quantiser plan, the prediction modes and the motion
   vectors are derived from decoded data (the anchors, the previous frame, the bit history); the
   encoder's only freedom is which index it writes, restricted so that the next encoder's plain
   reading returns the same index. No lock, no plan search, no inference, no repair engine.

| Clause | Status | Where |
|---|---|---|
| A1 half-rate (OMC@R = XS@2R, whole curve, 4:2:2 & 4:4:4) | **NOT demonstrated.** The structure is efficiency-neutral vs today's OMC (T2); the half-rate gap (≈1.33× short) is not closed by anything measured here | §6, §9 |
| A1 exact CBR, bounded buffer, worst frame fits | Met by construction for the pipe; **one open case**: a sudden, very complex slice after easy ones can exhaust index-choice range + bank → last-resort truncation (visible) | §2.8, §9 |
| A1 ramp (frames 0–1, cuts) | Met by design (plan backward-adapts; ramp only relaxes quality) | §2.8 |
| A2 latency sub-1 ms, deterministic, XS parity | Sub-1 ms met at every format with S chosen per format; worst-case 3S lines (≈1.5× XS at 1080p60 with S=16; ≤ XS with S=8) — **parity not guaranteed at S=16** | §5 |
| A3 no Section-G artifact | Seam/smudge/blend roots removed; flatness is an allocation problem the structure does not solve (§4) | §4 |
| A4 generations, both hop types, unlimited | Met by construction **when the in-cell projection converges within K_max (=1) or the lossless fallback fits**; **NOT met** on full-range hard steps butting onto near-rail gradients (cut24 shape) that fit neither | §3, §9 |
| A5 loss | Met: one-slice reach, rolling refresh with clean-region vectors, bound P+1 frames | §2.10 |
| B1–B4 formats | 8/10/12-bit (16-bit parametric), 4:0:0/4:2:0/4:2:2/4:4:4, full & limited range, SDR/HDR (transfer-agnostic), 720p–8K | §2.1 |
| C1 IP | Every element first-principles or expired art (§7); REXT, bracketed slices, idempotent index choice are own work | §7 |
| C2 causal, one reference | Met | §2.4 |
| C3 FPGA, shifts/adds/LUT, no adaptive arithmetic coding | Met; worst-case transform work ≈ 3–4× an XS decoder at K_max = 1 — within the ZU7EV with margin, but it IS repeated work (3 passes) | §5 |
| C4 rt = 0 all planes | Met by construction (decoder and encoder run the same deterministic reconstruction) | §3 |
| C5 colour always | All tests report Y, Cb, Cr | §6 |
| C7 video only | Met: every decision from the picture and the bitstream | §2.7 |
| C8 documented bitstream | Syntax defined in §2.9 (to be written as BITSTREAM spec) | §2.9 |
| Zero cost for legality/exactness | Met on natural content (REXT inactive, projection inactive or ≤1 round, 0 bits); lossless fallback on rail slices costs nothing when it fits | §3 |

**Weakest point (stated first, not last):** rails. On full-range content where a 0↔1023 step
butts onto pixels a few codes from the rail (the cut24 plates), no fixed-work, zero-bit, exact
legaliser was found — the in-cell projection does not converge (T4, T7), the fixed-work residual
layer costs 30–75 % of the bits (T5), and the lossless fallback does not fit below ≈2 bpp
(zeroth-order estimate). Second weakest: the half-rate mandate is not demonstrated.

---

## 1. How the structure was derived (first principles, with the evidence)

### 1.1 Why legality must live inside the reconstruction (pigeonhole)
A lossy transform decoder produces values z; some z exceed the legal range [lo, hi]. The output
must be legal, so some map f: z → y ∈ [lo, hi] is applied. If f is a clip, every z ≥ hi becomes hi:
the overshoot is destroyed, and the next encoder, which sees only y, cannot know it. Any f from a
larger set onto the legal set is many-to-one for the same reason (pigeonhole). Therefore the only
way the next encoder can recover the stream from y alone is if **y itself is a point the stream
describes**: the analysis of y must fall in the transmitted quantisation cells. Every family that
tries to "undo" a clip afterwards (repair engine, index capping, search recovery, plan lock) is
fighting information that is already gone. This is the in-cell principle; I derived it
independently and it agrees with expert B (Communication/202600927) and the ledger (S5.338).

### 1.2 Why not "legal by construction" through predict-only / pixel-owned structures (T1)
If every output sample owns one innovation and is produced last (`y = clamp(pred + R(q))`), legality
and exactness are trivial per sample. I tested the strongest forms I could build — closed-loop
hierarchical interpolation, separable, quincunx-order and directional, uniform and ramped steps —
against plain 5/3, **on VMAF-NEG, not only PSNR** (`t1_results.txt`):

| cell | 5/3 (clip) | best closed-loop arm |
|---|---|---|
| dng 1080p 4:2:2 | 1.049 bpp NEG 91.12, Y/Cb/Cr 37.50/36.28/37.05 | qx ramp 0.8: 1.247 bpp NEG 85.41, 36.90/36.02/36.56 |
| spotrobotL 1080p | 0.429 bpp NEG 91.41, 41.37/42.67/45.90 | qxd ramp 0.8: 0.403 bpp NEG 82.45, 39.26/39.97/41.37 |
| cf_gfx | 1.534 bpp NEG 92.76 | qx ramp 0.8: 1.829 bpp NEG 89.22 |

Parity appears only at ≥ 4 bpp. The quincunx order does not help because the coarse samples are
the same subsampled pixels whatever the order: the loss is aliasing, not the predictor. **This
family is falsified on VMAF-NEG as well as on PSNR** (it adds to DESIGN3/S5.212 and S5.349). An
anti-aliasing (update) transform is required, so legality cannot be a per-sample clamp; it must
be the in-cell reconstruction of §1.1.

### 1.3 Why the seam has a structural root and how brackets remove it (T2)
OMC's slice-local vertical transform needs rows below the slice, which do not exist yet (latency),
so it mirrors; the mirrored boundary row carries 20–30 % more error (measured again: row-phase
last row Y 12.84 vs 10.65 mid, dng 1080p, `sl2`), and the blend added to hide it shifts levels
(the grid smudge, S5.345). A continuous vertical transform (XS shape) needs rows below across the
slice boundary: latency, loss reach, memory (review S5.349). **Brackets** need no row below: the
slice's bottom row is coded first, as a 1-D row, and becomes the lower end of the vertical
interval; the upper end is the previous slice's anchor, already decoded. The vertical transform
is complete (log2 S levels) with *real* data at both ends. Measured, 5/3 everywhere, same
quantiser, zeroth-order entropy (`t2_results.txt`; `ff` = continuous full-frame, not a candidate):

| cell (S) | arm | bpp | NEG | PSNR Y/Cb/Cr | row-phase mean\|err\| Y first/mid/last |
|---|---|---|---|---|---|
| dng 1080p (16) | ff | 1.049 | 91.12 | 37.50/36.28/37.05 | 9.62/10.76/11.04 |
| | sl2 (OMC shape) | 1.195 | 90.83 | 37.42/36.17/36.97 | 10.42/10.65/**12.84** |
| | **br** | 1.215 | 91.00 | 37.52/36.32/37.06 | 11.21/10.67/10.33 |
| spotrobotL (16) | ff | 1.255 | 95.27 | 45.85/46.39/49.10 | 3.65/4.11/4.27 |
| | sl2 | 1.359 | 95.20 | 45.86/46.41/49.19 | 3.88/4.01/**5.03** |
| | **br** | **1.228** | **95.28** | 45.88/46.46/49.10 | 4.33/4.06/3.93 |
| dng 720p (8) | ff | 1.068 | 91.12 | 38.63/36.99/37.99 | 8.27/9.29/9.59 |
| | sl2 | 1.218 | 90.46 | 38.42/36.81/37.83 | 9.00/9.12/**11.26** |
| | **br** | 1.098 | 90.07 | 38.39/36.79/37.77 | 9.78/9.20/10.57 |

Brackets cost nothing against the OMC shape (−10 % bits on spotrobotL, ≈ equal elsewhere) and
flatten the boundary row in every plane (Cb/Cr similar; see file). The anchor step multiplier
(AM = 3) was tuned only at S = 16; at S = 8 the last row is still +15 % (tuning open). A variant
with a vertical predict-only bracket (`bp`, which would make legality 1-D) cost +15…30 % bits and
was rejected. The owner's smudge tool (smudgegroups.py, --sh 16, intra frame, D = 64) finds 0
groups in every plane for all three arms; the energy flatness meter says the three arms are
equally flat at ≈0.6 bpp intra (§4) — the structure does not change flatness.

### 1.4 Why rails need their own rule (T4–T7)
The in-cell reconstruction is found by alternating projection (legal set ↔ cells). On natural
content it converges in ≤ 1 round; on the full-range rail arms (`cut24` 256×64, `ext_10_422_l0`
512×128, values 0/1023) it does not converge in 200 rounds even on 1-D anchor rows (`t4b`). The
cause is structural: the clip residual on a plate is one-signed, its low-pass part is large, and
detail-band moves cannot lower a plate's mean. **REXT** removes the one-signed part: pixels exactly
on a rail are pushed M codes outside it before the transform, so the reconstruction of a plate
lands *beyond* the rail and the clip brings it back to the rail exactly, while ringing inside the
plate becomes zero-mean. Measured on cut24 (T6, M = D): PSNR Y 45.8 → 49.7 dB at D = 40, rails
exact, bits slightly lower (2.28 → 2.13 bpp; T5 averaged 6 rail frames, T6 3 rail frames). With the projection run in the extended domain (T7):
natural 100 % within 1 round, cf_gfx ≤ 3 rounds, ext10 95 % within 2 rounds, **cut24 still
fails** (§9).

---

## 2. The codec

### 2.1 Signal, formats, legal ranges
- Planes coded independently as delivered (Y, Cb, Cr; or R, G, B for 4:4:4 graphics — no colour
  transform, so legality stays per plane). 4:0:0 = one plane.
- Bit depth B ∈ {8, 10, 12} (16 parametric: all arithmetic widths below are B + 6 bits).
- Legal range per plane `[lo, hi]` from a normative table indexed by (B, range flag, plane):
  full range `[0, 2^B − 1]` unless the transport restricts it (10-bit SDI `[4, 1019]`), limited
  range the SDI legal extremes (10-bit `[4, 1019]`). SDR/HDR (BT.709/BT.2020, PQ, HLG) only change
  what the codes mean, never the arithmetic: the codec is transfer-agnostic, so it cannot add
  colour error by assuming a matrix (B3).
- 4:2:0: the chroma slice is S/2 rows with its own anchor (its last chroma row).

### 2.2 Slice geometry (normative)
- Frame height padded to a multiple of S by replicating the last row (cropped on output).
- S = 16 above 720p, S = 8 at 720p-class heights; S is a header field. (§5 gives S = 8 at 1080p
  as the XS-parity option.)
- Slice k covers rows `kS … kS+S−1`. Its **anchor** is row `kS+S−1`. Its **bracket** is the
  interval of positions `0 … S` where position 0 is the decoded anchor of slice k−1 (for k = 0, a
  *virtual anchor*: row 0 coded once more as a 1-D row, cost one row per plane per frame),
  positions `1 … S−1` are rows `kS … kS+S−2`, position S is slice k's own decoded anchor.

### 2.3 Transform (exact integer lifting; P and U below are the only per-sample arithmetic)
- **Horizontal** (anchor rows and every interior coefficient row): 5 levels of 5/3 lifting with
  whole-sample symmetric extension at the *frame* left/right edges only (no internal vertical
  edges exist: slices are full width).
  `d[i] = o[i] − P(e[i], e[i+1])`, `s[i] = e[i] + U(d[i−1], d[i])`.
- **Vertical bracket** (interior only), on positions 0…S, fine → coarse:
  level ℓ uses the current even list; odd positions p get `X[p] −= P(X[p−h], X[p+h])`; interior even
  positions (never 0, never S) get `X[e] += U(X[e−h], X[e+h])`; repeat on the evens until only
  {0, S} remain (log2 S levels; S = 16 → coefficient rows at level 1 (8 rows), 2 (4), 3 (2), 4 (1)).
  The inverse runs the steps in reverse. Endpoints are inputs, never outputs.
- **Rounding (normative, sign-symmetric):** `P(a,b) = (a + b + [a+b<0]) >> 1` (halves toward
  zero on both signs), `U(a,b) = (a + b + 2 − [a+b<0]) >> 2` (halves away from zero on both
  signs), so the rounding is odd-symmetric and the reconstruction error has no DC bias (the +1-code cast of S5.358 came from half-up rounding). Test T2 used plain
  floors; its level maps show a mild one-signed bias — the symmetric form is required, and its
  zero-mean property must be measured on the level map of every plane before any build is
  accepted.
- Order per slice: anchor row (1-D) → interior (vertical bracket, then horizontal on each of the
  S−1 coefficient rows).

### 2.4 Temporal prediction (one reference, C2)
- Reference = the previous decoded frame (exactly one; nothing else is stored).
- Prediction is applied in the pixel domain before the transform: residual `x − pred`, and the
  bracket endpoints are taken as `decoded anchor − pred` at those rows, so the bracket is exact in
  the residual domain as well.
- **Motion vectors are derived, not searched on the source** (this is what makes them canonical):
  - the anchor row's vector field: the previous frame's field at the co-located blocks
    (temporal continuity), refined ±1 half-pel by matching the previous slice's decoded anchor;
  - the interior's vector per 32-wide block: a fixed search (±R integer, then half-pel) that
    minimises the absolute difference between the two **decoded anchors bracketing the block**
    (above and own) and the reference at the displaced positions; fixed scan order and a fixed
    tie-break (smallest |v|, then raster order).
  Both are deterministic functions of data every encoder and decoder already holds. Vectors are
  transmitted (so the decoder never searches) and every re-encoder recomputes the same ones.
- Half-pel = the two-tap average of neighbouring integer positions (first principles; no named
  standard's taps).
- Per-band inter mask (which bands use the prediction): a deterministic function of the previous
  frame's co-located statistics (band energy with vs without prediction, decoded data only);
  finest bands go intra on noisy content (the "reference noise in level-1 bands" finding, S5.x).
- Clean-region rule for refresh (A5): during a refresh wave, vectors of slices already refreshed
  in this wave are clamped so their support stays above the wave front in the reference.

### 2.5 Quantisation
- Per band b a step `Δ_b = 2^{e_b}` (exponent from the plan, §2.8), dead-zone cells
  `q = sgn(c)·⌊|c|/Δ_b⌋`, i.e. cell 0 = (−Δ, Δ), cell q = [|q|Δ, (|q|+1)Δ).
- Nominal reconstruction `R(q) = sgn(q)·⌊(|q| + 3/8)·Δ_b + ½⌋`, 0 for q = 0.
- **Encoder freedom = index choice, restricted to be idempotent.** The first encoder may write any
  index its rate–distortion rule prefers (two-candidate choice, zeroing; the ECSQ form already
  cleared by legal), **provided every decision threshold lies at or below the nominal
  reconstruction point of the cell it is choosing**: e.g. "write |q|−1 instead of |q| if
  |c| < (|q| + τ)Δ" with 0 ≤ τ ≤ 3/8, and "write 0 instead of ±1 if |c| < (1 + τ)Δ". Applied to a
  decoded picture, whose coefficients sit at (or, after the projection, above) nominal points, the
  same rule changes nothing. So a re-encoder running the *same* procedure returns the same indices
  — no recognition step, no special re-encode mode. τ is a continuous per-position field (rate
  control and texture protection), never a step.
- The projection (§2.6) may move a nonzero-index coefficient only within the **upper part** of its
  cell `[(|q| + 3/8)Δ, (|q|+1)Δ)` and a zero-index coefficient anywhere in the dead zone; this keeps
  the idempotence of the previous paragraph.

### 2.6 Legality: REXT + in-cell reconstruction
- **REXT (input rule, every encoder, every input):** `u = x + M·[x = hi] − M·[x = lo]` per sample,
  M = the band-1 step of the plane (M = D in T6/T7). Source and decoded pictures get exactly the
  same rule; it is part of encoding, not something a later encoder must undo.
- **Decoder reconstruction of a unit** (anchor row, or slice interior):
  1. `w = R(q)`, `z = S(w)` (synthesis, with the bracket endpoints in the extended domain).
  2. Rail set `Rs = {z ≥ hi} ∪ {z ≤ lo}` (from the first synthesis only; fixed thereafter).
  3. Up to K_max rounds: target `t = hi + M` on top rails, `lo − M` on bottom rails, `clip(z, lo+1,
     hi−1)` elsewhere; stop if `t = z`; else `w ← clamp(T(t), cell_low', cell_high)` (cells as
     restricted in §2.5), `z = S(w)`.
  4. Output `y = clip(z, lo, hi)`.
- If step 3 ends converged, y is legal and `T(REXT(y)) = w` lies in the cells: the next encoder's
  plain quantisation returns q (§3). On natural content the loop does 0 rounds on > 99 % of units
  and ≤ 1 elsewhere (T7: dng 720p 543 units, 4 needed 1 round).
- **K_max = 1** (normative). If the first encoder sees that a unit does not converge within K_max,
  it switches that unit to **lossless** (all its steps Δ = 1; flag in the unit header) if the
  lossless bits fit the unit's budget: the lossless picture is the source, legal and trivially
  exact, and a re-encoder given that picture reaches the same decision because it evaluates the
  same rule on the same input (the source) — the decision is a fixed point by construction. If
  lossless does not fit, the unit keeps its lossy indices and the final clip of step 4 fires:
  **legal, but generation exactness is not guaranteed for that unit** (§9).

### 2.7 Canonical decisions (the complete list)
| decision | made from | why every generation makes the same one |
|---|---|---|
| plan (e_b per band) | bit history + bank + decoded anchors of this slice | functions of identical decoded data (induction from frame 0) |
| indices | first encoder's idempotent choice | the re-encoder's same rule returns them (§2.5) |
| in-cell values | decoder projection | deterministic function of the indices |
| motion vectors | decoded anchors + reference + previous field | identical decoded data |
| inter mask per band | previous frame statistics | identical decoded data |
| intra refresh | frame index mod P from stream start | stream position |
| scene-cut intra | decoded anchor's prediction error vs threshold | identical decoded data |
| lossless unit | "does not converge in K_max and lossless fits" evaluated on the unit's input | the input is the same picture at every generation (the source was reproduced exactly) |
| padding | leftover bytes at frame end | identical bit counts |
Mid-stream hops (a re-encoder that joins after frame 0): its refresh phase is read from the
picture — a slice whose *intra* analysis lies exactly on nominal points is the upstream refresh
slice — and adopted at the first such slice; frames before that are the hop's own ramp.

### 2.8 Rate control and exact CBR (A1)
- Wire: CBR; frame = `frame_bytes` exactly; slices variable length with the causal prefix bound
  (slice k complete by (k+1) slice periods), unspent bytes carried forward (bank ≤ ½ slice),
  canonical padding at the frame end.
- Plan: per band exponents `e_b = base_b + ⌊(k + φ_b)/4⌋`, a single integer k per slice interior,
  staggered phases φ_b so one step of k changes one band (≈ 1.5 dB aggregate). k for the anchor =
  k of the previous slice; k for the interior = f(bank, bits of the anchor, activity of the two
  decoded anchors, bits of the co-located slice in the previous frame). The anchor is the rate
  controller's probe: it is coded before the bulk of the slice and every encoder sees the same
  decoded anchor.
- Band exponent changes between slices are softened by the τ field: near the boundary the finer
  side raises τ (zeroes more), so the *texture-kill threshold* is continuous across the boundary
  even though the step is not (zero-visible-step rule; must be checked by eye on level maps).
- Fit: the index-choice freedom (τ ∈ [0, 3/8], zeroing) and the bank absorb the error of the
  plan. **Last resort** if both are exhausted: the unit's finest-level coefficients are dropped
  after the last one that fits (end-of-band codes). This is the only non-smooth mechanism in the
  codec; it is exact and legal but visible, and its frequency on the corpus must be measured (§9).
- Ramp: frame 0 and cut frames use the same machinery; the plan adapts from the first slice on.

### 2.9 Entropy coding and syntax (C3, C8)
- Static tANS tables (normative, small set per band class × context), context = magnitude class
  of the left and upper neighbours in the same band (3 classes), zero-run symbol, sign raw,
  refinement bits raw. No adaptive arithmetic coding, no rANS.
- Unit order in a slice packet: header (k, lossless flags, per-unit K-convergence not signalled),
  per plane: anchor row bands coarse→fine, then interior bands coarse→fine (vertical level 4 first),
  each band terminated by an end-of-band code (canonical: never followed by coded zeros).
- Vectors: transmitted per block, coded as the difference to the previous frame's co-located
  vector (static tANS). The decoder only reads them; every encoder derives them (§2.4), so the
  values are canonical without any decoder-side search.

### 2.10 Loss resilience (A5)
- Packet = one slice. A lost slice is concealed by the motion-compensated reference.
- Reach: slice k+1's interior uses slice k's anchor as its upper bracket end, so a loss of slice k
  also perturbs slice k+1's upper rows (the bracket interpolates the error away towards k+1's own
  anchor). Slice k+1's anchor does not depend on slice k, so slice k+2 is untouched: **reach = the
  lost slice + the upper part of the next one**, never a chain.
- Temporal recovery: rolling intra refresh, one wave per P frames top to bottom, clean-region
  vector rule (§2.4). Bound: P + 1 frames (P = 8 → 9 frames). Rails and lossless units are inside
  the same wave.

### 2.11 Resolution conversion
Outside the codec (the codec never resamples); its latency is accounted in §5 (the OMC model's
worst conversion charge, ≈ 0.3 ms at 720p50).

---

## 3. Legality and exactness — proof sketch

Definitions: E = encoder procedure (REXT, derived decisions, idempotent index choice, pack);
D = decoder (unpack, R, S, projection, clip). y₁ = D(E(x)).

1. **Legal:** step 4 of §2.6 clips; every output sample is in [lo, hi], always (every path,
   including the non-converged last resort).
2. **rt = 0:** the encoder's reconstruction is D applied to its own stream; integer lifting,
   integer projection with a fixed round count, no data-dependent loop count beyond K_max.
3. **Picture fixed point (baseband hop):** assume every unit of y₁ converged (or is lossless).
   (a) Decoded data used by derived decisions are identical at generation 2 by induction over
   slices and frames (frame 0 intra: no reference; each slice uses only earlier slices/frames).
   (b) REXT(y₁) = the projection's final target t (rail pixels are exactly the decoder's rail set,
   pushed by the same M; the others are in [lo+1, hi−1] and untouched), and T(t) = w lies in the
   cells, in the upper part of nonzero cells.
   (c) The re-encoder computes T(REXT(y₁)) = w and applies the same idempotent index rule: every
   threshold is ≤ the nominal point ≤ the value, so it returns q. Lossless units: the input is the
   source, the same rule gives the same decision and the same (lossless) indices.
   (d) Same q, same plan, same vectors → same bits → same bank → same stream. Hence E(y₁) = E(x)
   (byte-identical from generation 2, not just from 3) and D(E(y₁)) = y₁; by induction, unlimited
   generations.
4. **CBR hop** (re-encode into the same pipe): identical to 3 — the pipe parameters are the same,
   so the stream is the same bytes.
5. **Where the proof does not hold:** a unit that neither converges in K_max nor fits losslessly.
   Its picture is legal, but T(REXT(y₁)) is not guaranteed in the cells, so generation 2 may move
   it. This is exactly the cut24 shape (§9).

---

## 4. Artifacts — why each observed failure cannot occur (or what remains)

| artifact (who had it) | root | in BSC-1 |
|---|---|---|
| seam line at every slice join (OMC) | mirrored bottom row + boundary gains | no mirror anywhere; bracket ends are real decoded rows; measured flat row phase (T2) |
| grid smudges along slice rows (OMC) | display blend shifting row levels | no blend exists; nothing is added after reconstruction except the clip on non-converged units |
| still-area flicker (OMC) | inter residual requantised every frame | on a still input the residual is minus the previous coding error, inside the dead zone → held; intra-masked bands re-code the same input to the same indices; projection deterministic; plan hysteresis. Flicker can only come from a plan change, which moves one band by one step |
| clip destroying exactness (OMC) | pixel clip after a lossy inverse | in-cell reconstruction; clip only on the last-resort unit |
| repair/lock/search work (OMC) | undoing lost information | none; the re-encoder reads |
| colour cast (OMC, S5.358) | half-up lifting rounding | sign-symmetric rounding (§2.3), to be verified on level maps |
| 16×16/32×32 tile grid, patchwork (HVBC) | per-tile decisions, non-overlapping synthesis | no tiles; overlapping 5/3 synthesis; all per-region parameters are continuous (τ) or slice-wide with τ softening |
| waxy flat patches (HVBC, OMC) | dead-zone texture kill at low rate | **not solved by structure.** Energy meter at ≈0.6 bpp intra (dng 1080p, D = 64): ff 66.7/92.5/90.2 %, sl2 56.2/75.5/84.3 %, br 57.9/75.6/83.7 % of textured blocks (Y/Cb/Cr) — "the energy meter says" all arms flatten equally with a plain MSE allocation. Remedies are allocation and temporal: chroma steps, τ field that protects texture (lower τ where the source has texture), inter accumulation in static areas. Unmeasured here. |
| banding (G2) | coarse LL steps on gradients | LL steps are the finest; REXT keeps rail plates exact; unmeasured on sky content |
| pixelation (G3) | isolated wrong samples | no per-sample decisions in the transform path; the projection moves whole coefficients within cells |
| hard edges (G5) | block/tile boundaries | none |
| strip-level quality step (S5.344) | per-slice plan | τ softening across slice joins; must be shown by eye |

Artifact checks actually run in this design phase: row-phase per plane (T2), smudgegroups
(0 groups, all arms, intra, D = 64), flatplane (above), one level-map render
(`renders/dng_br_D64_lvl_Y.png`: no slice-row structure visible; mild one-signed bias from the
floor rounding used in the test). No temporal (steady-state frames 8–15) checks were possible
without a build.

---

## 5. Work, hardware fit, latency

### 5.1 Work per slice (closed form)
N = samples in the slice (all planes). Constants (adds/shifts per sample, from HARDWARE.md §1
scaled to 5H × log2(S)V): c_T ≈ 24 per full analysis or synthesis pass (OMC 2V×5H ≈ 20),
c_Q ≈ 3, c_E ≈ 1 tANS lookup + 4, c_P ≈ 4 (REXT, targets, clamps), c_ME per sample for the
anchor-bracket search (±R, two rows per block): ≈ (2R+1)²·2/S.

- Decoder: `W_dec = N · [c_E + c_Q + c_T·(1 + 2·K_max) + c_P·K_max]` → K_max = 1: ≈ 84 N.
- Encoder: `W_enc = N · [c_T + c_RDO + c_E + c_T·(1 + 2·K_max) + c_P·K_max + c_ME] + N·c_E`
  (the last term = the lossless-fit bit count, evaluated only when a unit fails to converge but
  provisioned always) → ≈ 110 N + c_ME·N.
- JPEG XS (for comparison): ≈ N·(14 + 3 + 5) ≈ 22 N each end.
So BSC-1 is ≈ 4× XS at the decoder and ≈ 5× at the encoder, worst case, **fixed** (no
content-dependent loop). This is three transform passes where XS has one: bounded, but it is
repeated work, and the owner may judge it too much (K_max = 0 would make it 1×, and is exactly
what the rails prevent).

### 5.2 ZU7EV fit (worst format 8K60 4:2:2, ≈ 4.0 Gsample/s)
- Transform: 3 passes × 24 ops × 4.0 G ≈ 290 Gops/s → at 300 MHz ≈ 970 adders ≈ 20 k LUTs
  (≈ 9 % of 230 k) at the decoder; encoder ≈ 13 %.
- tANS: ≈ 13 symbols/cycle → 13 interleaved lanes (BRAM tables).
- Buffers: a slice with bracket at 8K 4:2:2 ≈ 7680 × 17 × 2 × 18 bit ≈ 4.7 Mbit; three buffers
  (input, projection, output) ≈ 14 Mbit of 27 Mbit URAM; reference frame and search window in DDR.
- No multipliers in per-sample paths; the only data-dependent choice is the fixed-count projection.
Margin: comfortably inside the part in logic; URAM is the tight resource at 8K.

### 5.3 Latency (deterministic)
T = S lines (capture) + S lines (one slice period on the wire) + S lines (decoder processing
provisioned at 3 passes per slice period) = **3S lines**, independent of content.

| format | S | lines | ms | XS reference |
|---|---|---|---|---|
| 720p50 | 8 | 24 | 0.64 (+0.3 conversion = 0.94) | not measured here |
| 720p60 | 8 | 24 | 0.53 | not measured here |
| 1080p50 | 16 / 8 | 48 / 24 | 0.85 / 0.43 | ≈ 32 lines ≈ 0.57 (review S5.349) |
| 1080p60 | 16 / 8 | 48 / 24 | 0.71 / 0.36 | ≈ 32 lines ≈ 0.47 |
| 2160p60 | 16 | 48 | 0.36 | not measured here |
| 4320p60 | 16 | 48 | 0.18 | not measured here |

Sub-1 ms everywhere. XS parity holds with S = 8 (then the anchor overhead doubles; its cost at
1080p is not measured — only 720p S = 8, where br ≈ sl2). With S = 16 at 1080p the design is
≈ 1.5× XS: **noticeably longer**, so the XS-parity rule forces S = 8 at 1080p and below.

---

## 6. Expected coding efficiency (VMAF-NEG first, per-plane PSNR second)

- Intra structure (T2): bracketed = OMC-shape slice-local at equal NEG (dng 1080p 91.00 vs 90.83
  at 1.215 vs 1.195 bpp; spotrobotL 95.28 vs 95.20 at 1.228 vs 1.359; dng 720p 90.07 @1.098 vs
  90.46 @1.218), per-plane PSNR within ±0.2 dB, and within 0–14 % of a continuous full-frame
  transform. Artifact checks next to these numbers in §1.3/§4.
- Rails (T6): REXT raises cut24 from 45.8 to 49.7 dB Y (D = 40) at slightly fewer bits.
- Legality/exactness: 0 bits and 0 dB on natural content (projection inactive or ≤ 1 round, REXT
  inactive). Idempotent index choice lets the first encoder use full two-candidate RDO — a lever
  OMC's lock could not use freely.
- Unmeasured and possibly negative: derived motion vectors (from two decoded rows) vs a free
  source search; the anchor row's 1-D coding in intra/refresh slices.
- **Net expectation: efficiency ≈ today's OMC, i.e. still ≈ 1.33× short of the half-rate
  mandate. BSC-1 removes the structural blockers; it does not by itself close the rate gap.**
  The gap has to come from levers that this structure leaves open and compatible with
  canonicity: per-band inter masks tuned on noisy content, RDO/ECSQ at gen 1, context-modelled
  tANS, texture-protecting τ, chroma allocation.

Tests are intra, zeroth-order entropy, 5/3 only, one frame per cell, not tANS, not temporal —
diagnostics, not verdicts.

---

## 7. IP provenance (every element)

| element | provenance | why obviously clean |
|---|---|---|
| 5/3 integer lifting | Le Gall & Tabatabai 1988; lifting (Sweldens 1996) | expired / JPEG 2000 Part 1 royalty-free baseline |
| bracketed vertical interval transform | own work (lifting on an interval with fixed ends, first principles) | no borrowed tool; interval lifting is elementary |
| slice anchors coded first | own work | — |
| dead-zone scalar quantiser, power-of-two steps | textbook (1960s–80s) | expired |
| two-candidate index choice (ECSQ form) | Chou–Lookabaugh–Gray 1989 | expired; already cleared by legal |
| idempotent-threshold restriction | own work | — |
| in-cell reconstruction by alternating projection | POCS (Youla 1978, Gubin et al. 1967) | expired |
| REXT rail extension | own work | — |
| lossless fallback | integer 5/3 lossless (JPEG 2000 Part 1) | royalty-free |
| static tANS | Duda (ANS family); tANS only, no rANS (C1) | per C1 |
| block motion compensation, half-pel two-tap average | 1970s–80s (expired) | expired; no standard's taps |
| motion vectors derived from decoded anchor rows at the encoder, transmitted | own work; encoder-side matching (1970s block matching) | the decoder does not search; not decoder-side derivation |
| rolling intra refresh with clean-region vectors | 1990s practice (expired) | encoder behaviour only, no syntax borrowed |
| context modelling by neighbour magnitude classes | 1980s–90s (expired) | generic |
Nothing in BSC-1 is taken from JPEG XS internals, HEVC/AVC/VVC tools, CABAC or rANS. The
bracketed structure is not the XS architecture (XS has a continuous vertical transform across
precincts; BSC-1 has none).

---

## 8. Prior failures checked (grep of LEDGER_SANDBOX_v2 / LEDGER_v5_3_5 / HVBC findings)

| prior attempt | record | why it does not apply / what I did |
|---|---|---|
| predict-only transform (DESIGN3) | S5.212, S5.349 | **I re-tested the family (T1) on VMAF-NEG and it failed; not used.** |
| vertical-causal row prediction | S5.353/356/358 | not used: A5 chain (a lost slice would propagate down the frame) and −0.4…−1.2 dB; brackets get the seam removal without the chain |
| continuous vertical transform | S5.349 (2) | not used (latency, A5, memory, XS resemblance); brackets are slice-local plus one decoded row above |
| cross-slice term + blend (XSL) | S5.206, S5.345 | replaced: the row above is a *fixed endpoint*, not a term added into the update; no blend |
| repair engine, index capping, δ search, plan lock | S5.213–S5.323 | none present; exactness by reading (§3) |
| in-cell projection (expert B, SA9 Step W) | S5.333, S5.338 | used — but in the REXT domain, with K_max = 1 and a lossless fallback; the rails failure it had is reduced (ext10) but not removed (cut24) |
| signatures / odd-dyadic points (expert A) | S5.349 (3) | not needed: the plan is derived, not inferred |
| embedded bit-plane exactness | S5.320/321 (+1…17 %) | not used |
| per-block mode | per-block-mode-falsified | not used; modes are per band and derived |
| decoder-derived motion (Design A) | S5.29 | vectors are *transmitted*; only their derivation at the encoder uses decoded data, so a decoder never depends on a derivation |
| per-slice plan steps | S5.344 | softened by the τ field; must be shown by eye |
| lossless-if-fits | not found in the records | new; canonical because the lossless output is the input |
| HVBC mechanism C texture-kill | HVBC §6 | the τ field is continuous; dead-zone thresholds identical everywhere within a slice |
| HVBC tile grid | HVBC §1 | no tiles |

---

## 9. Risks and open items (in order of severity)

1. **Rails (the weakest point).** Full-range content where a 0↔1023 step butts onto near-rail
   pixels (cut24): the extended-domain projection does not converge (T7: 65/81 units at D = 14,
   54/81 at D = 40, cap 64), and lossless does not fit below ≈ 2 bpp by a zeroth-order estimate
   (1.88 bpp cut24 rail frames; a context coder may bring this under 1 bpp — unmeasured). Such
   units stay legal but lose the generation guarantee. Candidate next steps, each to be tested
   before anything is built: (a) a finer-grained rail set (plates vs isolated rail samples) so
   ramp-start samples are not extended; (b) M chosen per unit from decoded data; (c) a
   context-modelled lossless coder for synthetic units. No candidate is known to close it.
2. **Half-rate mandate** not demonstrated (§6).
3. **Latency parity** requires S = 8 at ≤ 1080p; its efficiency at 1080p is unmeasured.
4. **Work** ≈ 4–5× XS worst case (three passes) — bounded but repeated.
5. **Derived motion vectors** may cost efficiency on motion cells (floorballgameL, highwaydriveL,
   spotrobotL, volleyballgameL) — unmeasured.
6. **Rate-control last resort** (truncation) is visible if it fires; its frequency is unmeasured.
7. **Band-exponent change between slices** must be invisible after τ softening — only the eye on
   level maps can say.
8. **Flatness** at ≥ 0.5 bpp is an allocation problem this structure does not solve (§4).
9. The projection's restricted cells (upper part of nonzero cells) remove the feasibility
   guarantee even in principle; convergence was measured only with full cells (T4/T7).

Decisive next tests (cheap, offline, same scripts): (i) T7 with the restricted cells and K_max = 1
+ lossless-fit accounting on all rail arms at 0.5/1.0/2.0 bpp; (ii) T2 at 1080p with S = 8;
(iii) a two-frame inter model (anchor-derived vectors vs source search) on the four motion cells,
NEG + per-plane PSNR + row phase; (iv) the symmetric-rounding level maps per plane.
