# NEST: a codec design that is legal by construction and generation-exact by reading

**SA14, 2026-09-27. Design only; nothing built in any codec tree.** Sandbox: `Subagents/SA14_design/`
(numpy models in `notes/`, logs in `out/`). Governing document: `PROJECT_CONSTRAINTS.md` rev. 6.
Owner priorities (coordinator, 2026-09-27), in order:
1. No seam lines or smudges.
2. A legal picture by construction.
3. Byte-exact generations through both hop types.
4. Efficiency not noticeably worse than today's OMC.

The half-rate goal is not the acceptance bar at this stage.

---

## 0. The design in one page

- **Transform: integer lifting in which every UPDATE step reads transmitted leaf values, never
  clamped or final sample values.** A leaf is a coded coefficient: a dequantised index plus its
  band prediction, or a "rail" symbol. Each PREDICT step reads only final samples. This is the
  whole trick. The decoder learns every value an update needs from the bitstream before it
  computes a single sample. So the legal interval of each predicted sample depends only on values
  that are already final, and the synthesis has no cycle, even though the transform keeps a full
  symmetric 5/3 update (anti-aliasing).
  - The records' finding that "legality in the synthesis = predict-only in disguise"
    (S5.349/S5.350, expert A §2.3) holds only when the update reads the clamped value. Here it
    does not.
  - A 2-D separable transform makes the horizontal detail an intermediate value. I rewrite the
    separable 5/3 exactly as a non-separable one-level lifting whose four bands (LL, HL, LH, HH)
    are all leaves (§1.2).
  - **Measured: this is the separable 5/3 to within ±0.5 % BD-rate on every plane** (§5.1).
- **Legality by rails and windows, not by a clip.**
  - Every sample carries a legal window. Pixels use the format's legal range. The low band at each
    level uses a window shifted by the update, [lo+U, hi+U], computed from the leaves.
  - A predicted sample lands strictly inside its window, or it is a **rail sample**: a one-symbol
    leaf meaning "this sample sits exactly on its window bound", whose update contribution is
    fixed (0 in intra, the band prediction in inter).
  - Even samples are legal because their low band lies in its window.
  - A safety clamp keeps even corrupted or lossy streams legal.
  - No pixel-domain clip exists anywhere.
- **Exactness by reading, with nested lattices.**
  - Reconstruction points are q·2^s: power-of-two steps with no offset, so every coarser lattice
    is a sub-lattice of every finer one.
  - The next encoder runs the exact inverse of the synthesis. Rail samples are recognised because
    they sit on their bound, and every other leaf comes back bit-exactly.
  - Per band, it then reads the coarsest shift and the cheapest mode whose lattice holds those
    leaves, using OR plus count-trailing-zeros in one pass.
  - The description it gets decodes to the same picture and never costs more bits than the one
    that made the picture. Generation 1 emits that canonical description of its own
    reconstruction. So the stream is byte-identical from generation 2 and the picture is fixed,
    for unlimited generations, at both hop types.
  - No lock, no search, no plan candidates, no signatures. Nested lattices fail to identify a
    plan's provenance (S5.70), but provenance is not needed: a canonical representative is.
    Rails do not depend on the plan, which is what broke nesting before.
- **Slices without seams: "shifted causal slices".**
  - Each 16-row slice (8 at 720p) starts on an odd (predicted) row.
  - Every vertical predict is two-sided. At the top it uses the slice above's FINAL rows, a
    closed-loop causal input.
  - The one one-sided operation is the update of the slice's last low row, which treats the
    missing detail below as zero.
  - No mirror, no blend, no lookahead, and no dependence on later slices.
  - Measured: the row-phase error profile is the continuous transform's own 4-row pattern plus
    +3…6 % on the first two rows of a slice. Today's mirrored slices show +27…+29 % on the last
    row. Mean signed error per row phase is flat, so there is no level shift and no smudge
    mechanism. It is also cheaper: −3…−4 % bits and +0.2…0.4 dB versus mirrored slices (§5.3).
- **Temporal, rate control, entropy and refresh are all made canonical from decoded data.**
  - Inter prediction works in the coefficient domain per band.
  - Motion vectors are derived only from decoded frames and then transmitted.
  - Intra or inter per band is read from lattice consistency.
  - Rolling refresh follows the picture when the input is already a decoded picture.
  - Static tANS or prefix codes with a context that includes the rail sign.
  - Exact CBR with the causal bank; at most two packs per slice.

**What is measured** (single frames, intra, full frames, all three planes; numpy integer models):
- legality: 0 out-of-range samples everywhere;
- generation exactness: gen-2 description byte-identical and gen-2 picture unchanged, on every
  cell, rate and plane tried, including synthetic full-range rail content, 10/12-bit, limited
  range;
- efficiency: no loss versus the same transform with a plain (illegal, inexact) clip;
- seam statistics of the slice structure.

**What is argued but not yet run:**
- the slice structure and legality together in one model;
- the temporal path;
- the entropy coder;
- hardware.

**Weakest point:** the encoder's rail closure has no proven small worst-case round bound (§8.1).

---

## 1. Encode and decode path

### 1.1 Frame and slice structure

- **Slices** are horizontal strips of S rows: S = 16 above 720p, 8 at 720p-class, as in today's
  latency model. Slices are the unit of rate control, packetisation, loss containment, legality
  closure and canonical reading.
- **Shifted layout.** Slice k covers source rows 16k+1 … 16k+16. Row 0 of the frame is coded as
  a one-row head, intra, a 1-D horizontal transform only. The transform's vertical polyphase
  grid is aligned so that the **first row of every slice is an odd (predicted) row** and the
  **last row is an even (low) row**. At vertical level 2 the same holds on the level-1 low rows:
  L1 rows k·8+0, 2, 4, 6 are predicted and 1, 3, 5, 7 are low.
- **Causal top.**
  - The vertical predict of the slice's first odd row reads the slice above's final even row:
    decoded pixels at level 1, the decoded level-1 low row at level 2.
  - Both are final before slice k starts. The decoder has them; the next encoder recomputes
    them from the picture (§2).
  - Nothing is mirrored or extrapolated at the top.
- **Bottom.**
  - No row below is ever read.
  - The last even row's update reads the detail rows above it, and treats the missing detail
    below as 0. That is the only one-sided operation in the design.
  - No predict is one-sided, because the last row of every level is a low row.
- **No display blend, no cross-slice "undo", nothing for the next encoder to undo.**
- **Chroma.**
  - 4:2:2 and 4:4:4 chroma have full vertical resolution and use the luma layout.
  - 4:2:0 chroma has S/2 rows per slice. It uses the same layout on its own grid, with 2
    vertical levels at S = 16 and 1 at S = 8.

### 1.2 Transform: leaf-reading lifting (normative)

**Notation.**
- ⌊x/2^k⌋ is an arithmetic right shift.
- π = (i + j) & 1 is a position-parity rounding offset. It makes every rounding unbiased: half
  the positions round a tie down and half up. This removes the +0.6-code cast measured with plain
  floor rounding (out/seam_signed.txt) and the colour-cast class the owner caught once.
- At one 2-D level, the input grid X (final samples of this level, each with a window [lo, hi])
  splits into A = even-row/even-column samples (low positions), B = even-row/odd-column samples,
  C = odd-row/even-column samples and D = odd-row/odd-column samples. In the shifted layout
  "odd rows" are the predicted rows.
- For a C/D row, "above" and "below" are the A/B rows next to it; the one above the slice's
  first C/D row is the causal top.
- `u_X` is the **update value** of leaf X: its detail value d_X if it is a lattice sample, and
  its rail value (0 intra, band prediction inter) if it is a rail sample.
- Frame left and right edges use sample and detail replication, which for 5/3 is identical to
  symmetric extension.

**Analysis** (encoder, and the next encoder's canonical analysis):
```
dB = B − ⌊(A_left_of_B + A_right_of_B + π)/2⌋                          predict, reads final A
dC = C − ⌊(A_above + A_below + π)/2⌋                                    predict, reads final A
dD = D − ( ⌊(C_left + C_right + π)/2⌋ + ⌊(B_above + B_below + π)/2⌋
           − ⌊(A_ul + A_ur + A_dl + A_dr + 1 + π)/4⌋ )                  predict, reads final A, B, C
leaves:  HH = dD
         HL = dB + ⌊(u_D above + u_D below + 1 + π)/4⌋                  inner update, reads leaves
         LH = dC + ⌊(u_D left  + u_D right + 1 + π)/4⌋                  inner update, reads leaves
         L  = A + ⌊(4(u_B left + u_B right + u_C above + u_C below)
                    + (u_D at the 4 diagonals) + 7 + π)/16⌋             update, reads leaves only
```
- The u terms from the (non-existent) row below a slice are 0.
- Algebraically (ignoring rounding) this is exactly the separable integer 5/3 (horizontal then
  vertical), rewritten so that all four bands are leaves.
- The next levels apply the same step to L: **2 levels of 2-D, then 3 horizontal 1-D levels**
  (dB = B − ⌊(A + A_right + π)/2⌋, L = A + ⌊(u_B left + u_B + 1 + π)/4⌋), matching today's
  2V×5H.
- A 4-tap horizontal predictor at the 1-D levels (−1, 9, 9, −1)/16, today's 9/7-M idea, fits
  the rule unchanged, since predicts read final samples. It is an efficiency option to measure.
  A vertical 4-tap is excluded: it would need a row below the slice.

**Synthesis** (decoder, and the encoder's reconstruction), per slice and plane:
1. Entropy-decode every symbol. Leaf values: lattice value = q·2^s (+ c_p in an inter band);
   rail = a flag and a side (+ or −).
2. Update values: u_D; then d_B = HL − ⌊(u_D above + u_D below + 1 + π)/4⌋, d_C likewise; u_B
   and u_C (rail → rail value).
3. **Windows, fine to coarse:**
   - pixel window W₀ = [lo, hi] of the format (full range 0 … 2ⁿ−1; limited 4 … 1019 at 10-bit,
     1 … 254 at 8-bit, 16 … 4079 at 12-bit);
   - the low band of level ℓ has window W_{ℓ}(A-position) + U_ℓ;
   - each sample of level ℓ+1 inherits the window of its position in level ℓ's low band.
   These are plain adds on values that are all known now.
4. Coarsest low band: lattice → min(max(v, lo_w), hi_w) (safety clamp); rail → its bound.
5. Levels, coarse to fine:
   - A = L − U;
   - B = rail ? bound : clamp(d_B + P_B(A));
   - C = rail ? bound : clamp(d_C + P_C(A, causal top));
   - D = rail ? bound : clamp(d_D + P_D(A, B, C)).
   Every read is of a value already final, so the whole synthesis is one pass, as today's inverse.

### 1.3 Quantiser (normative part: only the lattice)

- Per band and per slice, a shift s. The reconstruction of index q is **q·2^s**. Nothing else is
  normative.
- The encoder's decision rule is free and non-normative. The default is a dead-zone quantiser
  (zero cell |c| < z·2^s, z = 9/16), plus any texture-preserving rate-distortion rule.
- Because R∘Q maps every point of any finer lattice to itself, for any dead zone z ≤ 1, a decoded
  picture's leaves survive re-quantisation at their own shift or any finer one.
- **Today's reconstruction offsets (the "texture bias") are removed.** An offset breaks nesting.
  Texture preservation moves into the encoder's decisions, which cost nothing normatively.

### 1.4 Rail samples and the encoder closure (encoder-only algorithm; normative meaning)

**Normative meaning.**
- A detail sample, or the coarsest low sample, whose output equals a bound of its window is a
  rail sample, coded as the symbol RAIL±.
- Every lattice sample's output lies strictly inside its window.
- The next encoder recovers this split from the picture alone.

**Generation-1 encoder (measured version, `notes/enc3s.py`):**
1. Canonical analysis of the source. Source samples on their bound are rail samples; their update
   value is the rail value, so the low band is consistent with them.
2. Quantise the lattice samples with the chosen plan.
3. **Closure.** Repeat:
   1. Synthesise.
   2. For every lattice sample whose pre-clamp value reaches or passes its bound: if its index is
      0, it becomes RAIL (its update value does not change). Otherwise its index moves one step
      inward (q ← q∓1).

   Stop when no sample reaches its bound.

**Termination.** Indices only move toward 0, and rails never revert.

**Measured on every run** (dng, spot, floor, gfx, synthetic rails; 3 rates; out/e3s_final.txt):
- at most 6 rounds; the number of changes per round falls steeply, e.g. 903 → 227 → 65 → 4 → 1;
- changes touch 0–0.06 % of samples on natural content.

In hardware the closure is a worklist over samples near rails, not whole-slice passes (§4).

**Rejected variants** (measured, kept for the record):
- **Rail with update value 0 for every sample that overshoots:** large local errors (max error 204
  vs 65 for the clip) and oscillation-free but multi-round.
- **Rails carrying the exact clamped value:** the joint fixed point oscillates (±1 two-cycles),
  because the HH predictor couples neighbours non-monotonically.
- **One-shot "pessimistic margin" closure:** snapped hundreds of thousands of samples; −10…−25 dB.
- **Coarsest-first rounds:** up to 42–147 rounds.
- **"Source rails as lattice samples":** −11…−16 dB versus the clip on rail content.

### 1.5 Temporal prediction

**Reference and prediction.**
- One reference frame: the previous decoded frame (C2).
- The motion-compensated prediction p comes from integer and bilinear half-pel samples
  (a 2-tap average, obvious and own work).
- Vectors are per 16×S block, with a vertical range ±4 rows (today's prefetched window).

**Inter bands.** Coefficient-domain prediction, as today. The band prediction c_p is the plain
analysis (§1.2 equations, no windows) of p over the slice, with p's own rows as the causal top.
An inter lattice leaf is c_p + q·2^s, and an inter rail's update value is c_p. Static content with
q = 0 therefore reproduces the previous leaves exactly: **frozen, with no flicker in still areas**.

**Motion vectors are canonical and transmitted.**
- The encoder derives them only from data the next encoder also has: y(t−1), y(t−2) (the encoder
  keeps one extra decoded frame, quarter resolution is enough), and the current frame's final rows
  above the slice.
- The rule: constant-velocity extrapolation of the block's motion between y(t−2) and y(t−1),
  refined by matching the final rows above the slice. It is deterministic and has a fixed search.
- The decoder only reads the vectors, so its only retained frame is y(t−1) (C2 holds).
- Why canonical: the next encoder must reproduce the vector exactly, or the inter leaves of the
  decoded picture are not lattice-consistent under its prediction.

**Intra or inter per band is read** (§2.3). The generation-1 encoder chooses modes by a
leaf-value-based cost rule, the same rule the reading applies, so the two agree.

**Refresh (A5).**
- A slice-cycle schedule from the frame index: a contiguous band of about ⌈N/8⌉ slices per frame
  moving top to bottom. Every slice is refreshed within 8 frames.
- Refreshed slices have intra leaves.
- Slices above the wavefront use motion vectors clamped to the refreshed region, plus the causal
  top. That gives a documented recovery bound of 8 frames plus the vertical extent of the damage
  in slices, measured in the build.
- **Static refresh without a pop:** a static slice keeps the intra lattice values of its last
  refresh (frozen inter, q = 0), so the next refresh re-describes it with the same indices.
- **Refresh follows the picture:** the schedule forces intra only where the leaves are
  intra-consistent. On a fresh source it always forces. On a decoded picture it reproduces the
  upstream refresh pattern. So the refresh phase needs no alignment between hops.

### 1.6 Rate control and exact CBR

- **Budget.** The per-slice budget is the configuration's nominal budget plus the causal bank of
  actual unspent bits from earlier slices of the frame, capped at twice nominal (today's
  structure). The frame ends with deterministic padding, so every frame is exactly the pipe
  size. The bank is canonical by induction: identical earlier slices mean identical bits.
- **Stage 1 (fresh sources only).** Choose per-band shifts and the non-normative dead-zone field
  so that the look-up-table cost fits the budget. Quantise, run the closure, and check the fit
  with the real pack. If it overflows, one coarser step and a second pack (at most two packs).
- **Stage 2 (always): canonical reading of the encoder's own leaves.** Per band, choose the mode
  and the coarsest consistent shift with the lowest exact cost, then pack. A coarser consistent
  shift gives smaller indices and a cheaper mode gives fewer bits, so **bits(stage 2) ≤
  bits(stage 1) ≤ budget**, and the reading is always emitted.
- **E(picture)** is: if the reading of the picture's own leaves fits the budget, emit it (always
  true for a decoded picture); otherwise run stage 1 and then stage 2. On fresh sources the
  reading lands at shift 0 (lossless) and does not fit, so stage 1 runs.
- **Strip steps.** Per-band shifts may change by at most one octave between vertically adjacent
  slices. Near a change the encoder ramps its dead-zone field continuously. This is an encoder
  policy, and whether a strip step stays invisible is an eye check (§8).

### 1.7 Entropy coding

- Static tANS tables per band class, as today, or canonical prefix codes whose exact cost comes
  from a look-up table. The alphabet is {index, RAIL+, RAIL−}. Contexts: the class of the left
  and upper neighbours ∈ {0, nonzero, RAIL+, RAIL−}, plus magnitude classes.
- **The rail sign must be in the context:** without it, plates cost about 1 bit per sample
  (measured +160…+230 %); with it, rail content is **55–63 % cheaper than the clip reference**
  (out/ctx_bits_final.txt).
- Per slice header: per-band shift (4 bits each, coded differentially), per-band mode (1 bit),
  and the motion vectors of the slice's blocks (differential, static code). tANS is flushed
  deterministically at the slice end.

### 1.8 Loss resilience (A5)

- One slice per packet (or a fixed split).
- A lost slice is concealed from the reference (copy of p).
- Spatial damage: the lost slice plus the first rows of the next slice, whose causal top is
  concealed; about 2 rows at level 1 and 4 at level 2. The slice after that reads final rows that
  are correct.
- Temporal damage heals through the refresh cycle (§1.5).
- Legality holds under loss by the safety clamps.

### 1.9 Formats

- Depths: 8/10/12-bit now; the arithmetic is int32-safe for 16-bit (windows grow by the update
  sum, a few bits).
- Chroma: 4:0:0, 4:2:0, 4:2:2, 4:4:4.
- Range: full or limited. The window is the format's legal range, a video-format property rather
  than metadata.
- HDR (PQ, HLG) and SDR carry code values unchanged.
- Interlace follows today's convention.
- Resolution conversion is a separate stage. It adds its filter lines to the latency (§4); the
  codec core is unchanged.

---

## 2. Why the picture is legal and why both hops are exact (proof sketch)

**Lemma 1 (acyclic synthesis).**
- Every update value is a function of symbols only: a lattice value, or a rail value (0, or the
  band prediction c_p, which is a function of the reference).
- Windows are sums of update values, so they are known before any sample.
- A = L − U needs L, which comes from the coarser level and is already final.
- B and C need final A; D needs final A, B and C.
- So there is no cycle, and the synthesis is one pass.

**Lemma 2 (legality).**
- Lattice and rail samples are in their windows, by the clamp or by definition.
- A = L − U lies in [lo, hi] because L lies in [lo + U, hi + U], by induction from the coarsest
  band.
- So every output sample is in [lo, hi] for **any** bitstream, including corrupted ones. There is
  no pixel clip anywhere.

**Lemma 3 (exact inverse).**
- Let y = D(s) for a conforming s: every lattice sample strictly inside, rails exactly on the
  bound.
- The canonical analysis of y, run per slice top to bottom with the slice above's rows and L1 row
  taken from y itself, recomputes P_B, P_C, P_D from final samples, which are identical.
- So d = y − P equals the decoder's pre-clamp value exactly: no clamp fired, since the sample is
  strictly inside.
- A sample on its bound is a rail. The window it is tested against is computed from the update
  values already recovered at finer levels.
- The inner updates and L = A + U use the same update values, so every leaf and every low band
  is recovered bit-exactly, level after level.

**Lemma 4 (reading).**
- Each band's lattice leaves are multiples of 2^{s₀}, the transmitted shift, in the transmitted
  mode. The reading picks the mode and shift s ≥ s₀ of lowest cost among consistent ones, so every
  lattice leaf is k·2^s exactly.
- Rails are independent of s and of the mode. Rail update values depend only on the mode, and
  every consistent mode's rail value is known.
- Decoding the reading gives the same leaves, hence (Lemma 1) the same picture:
  **D(E(y)) = y.**
- Its cost is at most that of s: same leaves, coarser shift or cheaper mode. So it fits the same
  budget, the bank evolves identically, and later slices see the same budgets.

**Theorem (both hops, unlimited generations).**
- Generation 1 emits s₁ = read(y₁), its own reconstruction's canonical description, where
  y₁ = D(s₁).
- At a CBR hop (same rate) or a baseband hop (the picture only, legal by Lemma 2),
  generation 2 computes E(y₁) = read(analysis(y₁)) = read(leaves of y₁) = s₁.
- Hence s₂ = s₁ and y₂ = y₁. By induction, every generation holds.
- Motion vectors are functions of decoded frames, identical by induction from frame 0.
- Modes are read.
- Refresh follows the picture, so no phase alignment is needed.
- The bank is identical.
- **Frame 0** is intra: y₁(0)'s leaves are intra-lattice, so generation 2 reproduces it. Exactness
  therefore holds from frame 0 when the hop sees the stream from its start.
- **A hop that starts mid-stream** reproduces the picture after its own ramp and at most one
  refresh cycle, as upstream refresh slices resynchronise it slice by slice. This is a documented
  limitation (§8.4).

**Measured** (out/e3s_final.txt, e2b logs):
- gen-2 description identical and gen-2 picture unchanged in 21 of 21 runs of the final policy,
  and in every earlier variant;
- 0 out-of-range samples;
- includes 12-bit and limited-range synthetic rail pictures.

---

## 3. Why OMC's and HVBC's artifacts cannot occur

| Artifact (and who had it) | Root in the old design | Why it has no mechanism here |
|---|---|---|
| Seam line at the slice bottom (OMC) | Bottom row mirrored; its highpass becomes a first difference; duplicate rows | No row below is read. The last row of every level is a low row, and no predict is one-sided. Row-phase profile ≈ continuous transform (§5.3). |
| Smudges along the slice grid (OMC) | Display blend shifted the level of the rows either side of the boundary | No blend exists. Rounding is parity-unbiased. Signed mean error per row phase is flat (§5.3). |
| Colour cast (OMC, +1 code) | Half-up lifting rounding | π-alternating offsets make every rounding unbiased. |
| Illegal picture, clip destroying information (OMC) | Pixel clip after a lossy inverse | Legality is in the synthesis (Lemma 2); there is no clip. |
| Repair engine or lock artifacts and work (OMC) | Searching for lost information | Nothing is lost (Lemma 3); plan and modes are read, not searched. |
| Flicker in still areas (OMC) | Residual noise re-coded every frame; refresh re-randomising static regions | Inter q = 0 reproduces leaves exactly (frozen). Refresh re-describes static intra lattice values exactly (§1.5). Temporal hysteresis is an encoder policy. |
| 16×16 or 32×32 grid, blocks (HVBC; G1/G2) | Non-overlapping block synthesis | Every synthesis basis is the overlapping 5/3 (the separable 5/3 exactly). No block unit exists anywhere. The only per-region parameters are per-slice shifts, limited to one octave with a continuous dead-zone ramp. |
| Waxy flat patches (HVBC; G4) | Block-wise texture kill | No mode zeroes a block. Flattening can only come from the encoder's dead-zone policy, the same risk any wavelet codec has (§8.3). There is no LL-only rung. |
| Rail ringing and halos (G3/G5 near black and white) | Clip plus ringing | Rails reproduce black and white plates exactly. On synthetic rail content PSNR is 4–7 dB **above** the clip reference. |

---

## 4. Work, latency and FPGA fit

**Per sample** (adds, shifts, compares, table look-ups; no multiplier), all levels amortised
(level 1 dominates; ×1.33 for the rest):

| Stage | Ops / sample | Note |
|---|---|---|
| Analysis | ≈ 9 | Same count as today's 5/3 levels |
| Synthesis | ≈ 9 + 3 | +3: window adds and the compare-clamp |
| Quantisation | ≈ 3 | |
| Canonical reading | ≈ 1 | An OR per band sample; count-trailing-zeros per band |
| Motion compensation | ≈ 4 | Bilinear |
| tANS | ≈ 5 per symbol | |

**Per slice:**
```
W_dec(slice) = N_s · (c_dec ≈ 12 + 4 + 5)                                       ≈ 21 N_s
W_enc(slice) = N_s · (9 + 3 + 12 + 4 + 1) + ME + 2·Pack + Closure
             ≈ 29 N_s + ME + 2·(5 N_s) + c_cl · N_near
JPEG XS:     W_XS ≈ N_s · (analysis 9 + quantise/budget 3 + pack 5)             ≈ 17 N_s
```
N_s is the number of samples in the slice.

- **Closure.** Each index change or rail conversion re-evaluates about 12 dependants (about 6 ops
  each), so c_cl ≈ 70 ops per change.
- **Measured changes per slice:** ≤ 0.06 % of samples on natural content (worst: spot at the
  lowest rate, about 1,200 changes per 1080p luma frame, about 18 per slice); ≤ 0.13 % on the
  synthetic rail picture.
- **Proven bound:** at most Σ|q| index moves plus one rail per sample. That bound is far above
  what was measured (§8.1).
- **Motion estimation** runs on decoded data. At a fixed search (±8 horizontal, ±4 vertical,
  integer then half-pel, 16×S blocks, template on the final rows above), it costs about 40
  ops/sample.
- **Packs:** at most 2. There is no lock (today: about 50 entropy-pass equivalents).

**ZU7EV-class fit** (about 230k LUT, 460k FF, 11 Mb BRAM, 27 Mb URAM):
- 8K60 4:2:2 is about 3.98 Gsamples/s, about 13.3 samples per clock at 300 MHz.
- The encoder's ≈ 90 ops/sample at ~40 LUT per 20-bit add/compare is about 48k LUT (21 %). The
  decoder's ≈ 21 ops/sample is about 11k LUT (5 %).
- Line buffers: a slice (16 rows) plus the ±4-row motion window of the reference, about 1 MB at
  8K 4:2:2 in URAM (30 %).
- DDR: one reference read and one write per frame, plus a quarter-resolution y(t−2) at the
  encoder: about 9 GB/s at 8K60 of about 19 GB/s.
- 1080p60 is about 16× lighter.
- These are estimates to be replaced by synthesis results. They carry no parallel hardware beyond
  the throughput every 8K codec needs.

**Latency.** Today's model (LATENCY.md) applies unchanged, because the slice structure adds no
lookahead:
```
T = S source lines (capture) + one slice period (paced transmission) + 2 lines (pipeline)
```
| Format | Codec-only | Worst conversion |
|---|---|---|
| 720p50, S = 8 | 0.500 ms | 0.806 ms |
| 1080p60, S = 16 | 0.50 ms (34 lines) | |
| 2160p60 | 0.25 ms | |
| 4320p60 | 0.13 ms | |

JPEG XS is about 32 lines at 1080p, so this is at parity. The latency is constant by construction.
The encoder's closure must finish inside the slice period; at the measured load it takes under 1 %
of it. The unproven worst case is §8.1.

---

## 5. Evidence: efficiency next to artifact checks

All numbers come from numpy integer models, on single full frames (f8), with Y, Cb and Cr each
coded. Rate is the entropy of the symbols (zeroth-order unless stated); steps are powers of two
from the synthesis basis energy; D0 sweeps the rate.

### 5.1 The leaf-reading transform costs nothing

NEST-S versus the separable integer 5/3, same levels, BD-rate over D0 ∈ {12 … 256}
(out/e1s.txt):

| Cell | Y | Cb | Cr |
|---|---|---|---|
| dng 1080p | +0.06 % | +0.19 % | +0.12 % |
| spotrobotL | +0.05 % | +0.18 % | −0.47 % |
| cf_gfx | +0.09 % | +0.37 % | +0.05 % |
| floorballgameL | +0.04 % | −0.24 % | −0.43 % |

A naive non-separable variant (HH predicted from its four edge neighbours, no inner updates) lost
4–28 %. That is why the design is the exact separable-equivalent (out/e1.txt).

### 5.2 Legality and exactness cost nothing on natural content, and gain on rails

**Legal and exact NEST versus the same quantised transform with a plain clip** (the illegal,
inexact reference; out/e3s_final.txt, out/vmaf_check_final.txt, out/ctx_bits_final.txt):

| Cell, D0 | Bits (all planes) NEST / clip | VMAF-NEG NEST / clip | PSNR Y/Cb/Cr NEST | PSNR Y/Cb/Cr clip |
|---|---|---|---|---|
| dng 1080p, 48 | 1.3283 / 1.3284 | 91.249 / 91.248 | 37.702 / 36.702 / 37.405 | identical |
| dng 1080p, 128 | 0.5278 / 0.5278 | 84.100 / 84.102 | 35.050 / 34.345 / 35.527 | 35.051 / 34.345 / 35.527 |
| spot, 48 | 0.4977 / 0.4955 (+0.4 %) | 91.741 / 91.777 | 41.617 / 42.884 / 46.009 | 41.624 / 42.884 / 46.009 |
| spot, 128 | 0.2682 / 0.2656 (+1.0 %) | 84.109 / 84.267 | 38.432 / 40.504 / 42.907 | 38.459 / 40.504 / 42.907 |

Bits in this table are zeroth-order entropy per luma pixel; with the context model spot is +0.3 %
/ +0.9 %.

| Synthetic full-range rail picture (Y) | PSNR NEST | PSNR clip | Context bits NEST | Context bits clip |
|---|---|---|---|---|
| D0 = 48 | 59.7 | 55.7 | 0.131 | 0.356 (−63 %) |
| D0 = 128 | 47.7 | 43.0 | 0.124 | 0.276 (−55 %) |

- Chroma is untouched: 0 samples differ from the clip reference.
- On luma the samples that differ are the near-rail highlights (spot: 0.65–1.1 % of pixels, max
  |Δ| 61–130). **That is the price: −0.04 to −0.16 VMAF-NEG points on the highlight-heavy cell at
  low rate.**
- Out-of-range samples: 0 in every run.

### 5.3 Seams: the shifted causal slice

Luma, 16-row slices, 2V×5H, closed loop (out/seam_test*.txt, out/seam_signed.txt). Mean |error|
by row of slice (0 = first row, 15 = last); max/min ratio:

| Cell, D0 | Continuous (no slices) | Today-like mirror slices | Shifted causal (this design) |
|---|---|---|---|
| dng, 48 | 1.18 (intrinsic 4-row pattern) | 1.49; last row +27 % | 1.36; rows 0–1 +6 %; row 15 is the 4-row pattern |
| spot, 128 | 1.03 | 1.38; last row +29 % | 1.05 |

| Cell, D0 | Bits per pixel: continuous / mirror / causal | PSNR: continuous / mirror / causal |
|---|---|---|
| dng, 48 | 1.007 / 0.996 / 0.961 | 38.31 / 38.12 / 38.34 |
| spot, 128 | 0.191 / 0.177 / 0.171 | 38.64 / 38.36 / 38.72 |

- Signed mean error per row phase: causal lies inside the continuous transform's own spread
  (±0.3 code). No slice-locked level shift, so no smudge mechanism.
- **Checks not yet done** (they need a temporal build): smudgegroups/artifactmap level maps on
  frames 8–15, flatplane/texstat, full-frame colour renders with |decode − source| maps. None of
  the numbers here is an artifact verdict (Section E); they only show that no seam or smudge
  mechanism is present in the structure.

### 5.4 Against today's OMC

No full codec has been built, so there is no measured comparison. These are the parts that
differ, and their measured or recorded size:

| Difference from today's OMC | Size | Source |
|---|---|---|
| Shifted causal slice instead of mirror + cross-slice term + blend | Versus mirror: −3…−4 % bits and +0.2…0.4 dB. Today's cross-slice term is worth 0.17–0.46 dB mean. | Measured here; S5.206 |
| No vertical 9/7-M | Loss unknown | Horizontal 4-tap is kept as an option |
| No reconstruction texture bias | Moves into encoder decisions | |
| No lock, no repair engine | Removes today's quality costs; the forced re-choice alone was −0.08…−1 dB | Records |
| Motion vectors derived from decoded frames instead of chosen from the source | The main unknown on motion cells | §8.2 |

**Expected:** parity ±3 % on natural intra content, better on rail graphics, and unknown on motion.

---

## 6. IP provenance (every element; none needs a legal question)

| Element | Provenance and why it is clean |
|---|---|
| Integer lifting, 5/3 filter pair | LeGall–Tabatabai 1988; lifting (Sweldens 1996); JPEG 2000 Part 1 reversible path (royalty-free by committee). All expired or open. |
| Leaf-reading update order, windows, rail symbols, closure | Own work (this design); arithmetic on the above. |
| Non-separable rewriting of the separable 5/3 | Algebraic identity of the above; own derivation. |
| Parity-alternating rounding | Own; obvious dithered rounding. |
| Dead-zone scalar quantiser, power-of-two steps | Textbook; decades old. |
| Canonical reading (OR, count-trailing-zeros, coarsest consistent step) | Own work; nested-lattice arithmetic. Not expert A's odd-dyadic signatures: no offsets are used. |
| Coefficient-domain temporal prediction, block motion compensation, bilinear half-pel | 1970s–80s literature, expired; already in today's tree. No H.264/HEVC tap filter. |
| Motion vectors from decoded frames (extrapolation plus template on final rows) | Classic block matching on decoder-available data; own rule. |
| Rolling slice refresh with vector clamp to the refreshed region | Today's slice refresh plus an obvious reference restriction; own. |
| tANS static tables | As today (Duda, public); no rANS. Canonical prefix codes: Huffman 1952. |
| Causal bank, exact CBR, padding | Today's own work. |

---

## 7. Every prior failure checked

| Record | What failed | Why it does not apply, or what I kept |
|---|---|---|
| DESIGN3 predict-only (S5.212, −3 dB); S5.228; one-sided update (S5.349: "acyclic ⇒ optimal update weight 0") | Removing or one-siding the update | The update here is symmetric and full-weight. Acyclicity comes from what it reads (leaves), not from its taps. Measured ±0.5 % versus the 5/3. |
| Expert A: clamp in synthesis needs predict-only; cycle through U | Same premise | The cycle exists only if U reads clamped values. Clamps here act on predicted samples, whose rails carry fixed update values. |
| Nested lattices falsified for provenance (S5.70) | Recovering the originating plan | Not needed: the design emits a canonical representative (the expert's "hierarchical canonical rule"), with every generation-1 encoder emitting it (Theorem). Zero-collision is harmless: rails and zeros are plan-independent. |
| Expert A odd-dyadic signatures (S5.349: +5…75 % distortion; Δ = 1 unreadable) | Distortion cost | Not used. Reading nested lattices needs no offset; Δ = 1 reads trivially. |
| Lattice-point lock, 50 passes, R1-LOCK (HANDOFF 09-21) | Search work and failures | Replaced by a one-pass reading. Nothing is searched. |
| In-cell projection K = 4 (memo 010 §8; S5.356 E2q) | Repeated work, rail stall | No projection; one synthesis pass at the decoder. |
| Encoder index cap (S5.213, update coupling, step wider than window) | Per-coefficient windows fighting the update | The closure acts on predicted samples, and rails absorb the step-wider-than-window case (index 0 becomes a rail). Measured convergence ≤ 6 rounds, including synthetic rails. The coupling still exists (§8.1). |
| Display blend = smudge (S5.345); cross-slice undo | Level-shifting blend | No blend; the causal top reads final rows, so nothing is undone. |
| Continuous vertical transform (S5.349: latency, A5 drift, memory, cross-packet clamps) | Lookahead across slices | Not used. The shifted causal slice has no lookahead and no dependence on later slices. |
| Vertical-causal DPCM (S5.353/356/358: −0.4…−1.2 dB; cast; exactness needed projection) | Losing the vertical transform | The vertical 5/3 is kept inside the slice. Only the top is causal and only the bottom update is one-sided. Better than continuous in the measurement (§5.3). Cast removed by π rounding. |
| Haar/S+P pair pyramid (SA12's path; HVBC grid risk) | Non-overlapping units | Not used; all bases overlap. |
| Pixel-owned quincunx predict-only (SA13's path) | Predict-only family | Not used. |
| Modular (wrap-around) arithmetic: my own first idea, rejected | Black and white become neighbours on the circle | Black/white graphics would need exact edges, since any ringing wraps. Recorded in NOTES.md. |
| Decoder-derived motion vectors fail A5 (block-MV findings) | Derivation at the decoder from possibly damaged data | Vectors are derived at the encoder from its clean reconstruction and transmitted. The decoder derives nothing. |
| Half-pel gating lever (memory) | | Bilinear half-pel kept; which rule selects half-pel is an encoder-policy lever. |
| Soccer, officewalk (corpus rules) | | Not used. Cells: dng, spotrobotL, floorballgameL, cf_gfx, synthetic rails. |

---

## 8. Risks and weakest points (in order)

### 8.1 Worst-case bound of the encoder closure (weakest point)

- Termination is proven: indices only move toward 0, and rails never revert.
- The measured round count is ≤ 6 with a steep decay, and the change count is ≤ 0.13 % of samples.
- A **small, content-independent** bound is NOT proven. A demotion pushes its neighbours by about
  2^s/8, so a long chain of near-bound samples, such as fine near-white stripes, could in
  principle take many rounds.
- The decoder is unaffected; this is encoder latency and work only. It must still meet the
  slice-period rule.
- First build gate: an adversarial generator (near-rail 1-pixel stripes at every phase, cut24,
  extrema arms, 8/10/12-bit, full and limited range) to find the real worst case.
- Fallback directions, not yet worked: a rail rule whose update value is the band's dead-zone
  reconstruction; or a Gauss-Seidel worklist ordered coarse to fine, which is still exact since
  any fixed point is valid.

### 8.2 Motion efficiency

- Canonical vectors lag by a frame, being extrapolated from y(t−2) → y(t−1) and refined on the
  rows above.
- On accelerating or new motion this could cost bits versus source-chosen vectors.
- To measure first, on the four motion cells.
- A "readable refinement" (a small candidate set checked by the finest-band lattice residue at
  the next encoder) is the lever if needed. It adds bounded encoder work.

### 8.3 Visible checks not yet done

- **First-rows excess** (+3…6 % |error| on rows 0–1 of each slice) must be judged by eye on level
  maps.
- **Per-slice shift changes** (strip steps) must be judged by eye on level maps.
- **Flattening** (dead-zone policy) must be judged by eye with smudgegroups, artifactmap,
  flatplane and texstat on steady-state frames of a temporal build, every plane.

### 8.4 Hop that starts mid-stream

- Exact after its own ramp plus at most one refresh cycle; exact from frame 0 when both see the
  stream from its start (as the gate harness does).
- Also a mid-stream hop's first two frames are intra and may not fit the budget the upstream inter
  frames used. They are ramp frames.

### 8.5 Near-rail highlights

- −0.04…−0.16 VMAF-NEG on spot at low rate, from demotion versus clip.
- An encoder-side choice (rail versus demotion by expected error) may recover part of it.

### 8.6 Intra-only evidence

- The temporal path, entropy coder, bank and refresh are designed, not modelled.
- None of the efficiency numbers covers them.

### 8.7 Hardware figures

- The hardware figures are estimates and must be replaced by synthesis results.

## 9. Files

- `notes/nests.py`: transform, windows, synthesis, canonical analysis and reading (final form).
- `notes/enc3s.py`: generation-1 encoder with the closure (final policy: `SRC_ESC = True`,
  `COARSE_FIRST = False`).
- Experiment runners:
  - `notes/run_e1.py` (E1);
  - `notes/run_e3s.py` (E3);
  - `notes/vmaf_check.py`;
  - `notes/ctx_bits.py`;
  - `notes/seam_test.py` and `notes/seam_test2.py`.
- Earlier variants, kept as evidence of what failed:
  - `nest.py`, `nest2.py`, `enc2.py`, `enc3.py`;
  - `oneshot.py`, `closure_probe.py`, `conv_quality.py`.
- `out/*.txt`: logs.
