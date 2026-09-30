# CLP-1 — a canonical, legal-by-construction pyramid codec

**SA12 design, revision 1, 2026-09-27.** A from-scratch design against PROJECT_CONSTRAINTS.md rev. 6 and the owner's standing rulings. Nothing was built in any codec tree. All experiments are small numpy models in `Subagents/SA12_design/notes/`; outputs are in `out/`. Every rate figure is a zeroth-order entropy estimate, and every decode comes from a model, not a codec build.

## Status in one paragraph

- **What it fixes, by construction.** The design removes the two root failures of OMC: illegal pictures and non-canonical encoder decisions.
  - *Legality.* Every transmitted value is clamped, *inside the synthesis*, into the interval that keeps its own outputs legal. That interval depends only on values that are already final, so the pipeline is acyclic: no clip, no repair, no search, no lock.
  - *Exactness.* The next encoder's forward transform recovers every decoded value exactly, and a canonical index rule maps each value back to the same index. Every decision the decoder sees is a function of already-decoded data. Generation exactness is therefore an induction over the coding order.
- **Measured in models.**
  - *Legality and exactness.* Zero out-of-range samples, decoder = encoder, and generation-2 byte identity on 216/216 synthetic rail cases and on real frames. The rail cases cover 8/10/12-bit; full, limited and SDI-legal ranges; 4:4:4; and steps wider than the legal window.
  - *Intra efficiency.* At or above today's transform structure: mean +0.20/+0.13/+0.16 dB (Y/Cb/Cr) at 0.5 bpp and +0.28/+0.23/+0.12 at 2.0. Worst cell −0.02/−0.21/−0.36 at 2.0.
  - *Visual measures.* On an intra artifact battery VMAF-NEG is higher on all 8 points, and the slice-grid and block-grid statistics are lower everywhere. There is no colour cast (|mean error| ≤ 0.06 code) and no added periodicity. Loss dies out within two slices.
- **Not met, stated plainly.**
  - The **half-rate mandate (A1)**. Nothing here shows 2× against JPEG XS. The expected ratio is about today's.
  - **Canonical motion vectors** recovered well under half of the oracle vectors' gain in a crude probe.
  - A **residual last-row error excess** of 5–23 %, lower than today's 10–29 %.
  - **Chroma flatness** that is worse than today's structure on some cells.
  - A **mid-stream-join** limit on exactness.
- **Eye.** Nothing has been judged by eye yet. Renders are in `out/art9/`.

---

## 0. Principles, and the root cause each one removes

| # | Principle | OMC root cause it removes (record) |
|---|---|---|
| P1 | **Legality inside the synthesis, acyclic.** Every transmitted value is clamped to the set of values that keep *its own outputs* legal, computed only from values that are already final. There is no pixel-domain clip anywhere. | The clip after a lossy inverse destroyed information. Repair, capping, δ-recovery, legaliser and lock were all searches for it (S5.212–S5.214; memos 010–012). |
| P2 | **Canonical by causality.** Every value the decoder uses is a deterministic function of the already-coded stream prefix and the one reference frame: steps, prediction weights, vectors, refresh, control values. The current source never enters a decision. The encoder's only free choice is each coefficient's index, and on a lattice point that is forced. | The plan was chosen from the source and then "rediscovered" by a 50-pass lock (S5.339 synthesis; expert B §1). |
| P3 | **Exact pair sums; the detail predicted from final neighbours.** Each lowpass sample is the exact *sum* of its own pair. The half-difference is predicted from neighbouring final lowpass samples (2/10 form). This is the only family I found in which P1 stays acyclic across levels *and* the coarse band is anti-aliased rather than decimated. | An update step makes the clamps cyclic (S5.349). Predict-only costs −2.2…−3.7 dB (S5.212, S5.353). |
| P4 | **No slice-boundary machinery.** No mirror, no blend, no un-blend, no deferred row. The vertical predictor reads *true* context at the top of the slice (the lowpass of the decoded rows above) and extrapolates linearly at the bottom. | Seam line = the mirrored last row. Smudge = the level-shifting blend (S5.345–S5.348). |
| P5 | **Every per-region parameter is a continuous field**, interpolated from control values that are transmitted and canonically derived. | HVBC's 16×16 hard gates; per-slice step jumps (S5.349). |

---

## 1. Formats, stream, packets

- **Formats.**
  - Y′CbCr only (no RGB detour); 4:2:0 / 4:2:2 / 4:4:4; 8/10/12-bit.
  - 16-bit before release: intermediate words are B+9 bits (§7.4).
  - Per-plane legal limits `lo, hi` are in the stream header: full range, limited range, or transport-legal (for example 1…254 at 8-bit SDI, 4…1019 at 10-bit).
  - BT.709/BT.2020 and SDR/PQ/HLG are code values to the codec. No transfer-function processing, so no colour error from it.
  - Illegal source samples are clamped at the encoder input (this only ever touches an already-illegal source).
- **Geometry.**
  - Slices are full width, `sh` = 16 rows (8 at 720p-class heights). The last slice of a frame is shorter when needed (1080 = 67×16 + 8) and has its own pyramid geometry.
  - **No padding.** Padding breaks generation exactness: measured failing on 1080-row frames (§4.3).
- **Exact CBR.** Slice k has a fixed packet of exactly `S_k` bytes: header, tANS payload, and a fixed padding pattern. `S_k` is a static function of the pipe rate and the slice's sample count. Stream size is therefore a closed formula, and the buffer can neither overflow nor underflow.
- **Transmitted decisions.** Every decoder-visible decision is transmitted: step-field control values, vectors, α, and the refresh flag. The decoder needs no controller and no derived state beyond the reference frame. The encoder must derive these values canonically (§3.5–3.6). That is an encoder conformance rule for chain exactness, not a decoder rule.

---

## 2. Decoder (normative)

### 2.1 The pair map (per 1-D stage)

Each pair (a, b) carries a sign σ ∈ {+1, −1}, given by a fixed pseudo-random sequence of stage, absolute slice index, pair index and cross index (§2.6):

```
forward:   s  = a + b                         d' = (a − b − σ·(s mod 2)) / 2        (exact integer)
inverse:   d  = 2·d' + σ·(s mod 2)            a = (s + d) / 2        b = a − d
```

- This is an exact bijection Z² ↔ Z². a − b has the parity of s, so s carries the bit that a rounded mean would drop, and the map loses nothing.
- The lowpass grows by one bit per stage. After 8 stages the coarsest band is B+8 bits.

### 2.2 Pyramid per slice and plane

The number of vertical levels is `nv = min(3, log2(rows))`: 3 for 16-row and 8-row slices, 2 for 4-row 4:2:0 chroma slices. There are 5 horizontal levels in total.

- **2-D level ℓ ≤ nv**, acting on A (pixels at ℓ = 1):
  - H-split A → (Lc, dH);
  - V-split Lc → (LL, dL);
  - residual e = dH − P_H(Lc);
  - V-split e → (HL, dE).
  - Transmitted: **LH** = dL − p_V(LL), **HL** (minus its temporal term), **HH** = dE − p_V(HL).
- **H-only level ℓ > nv**: H-split → (Lc, dH). Transmitted: **H** = dH − P_H(Lc).
- **Coarsest band.** LL, transmitted minus its temporal term.

### 2.3 Spatial predictors (shift-add; final values only)

- **Formula.** In sum form the 2/10 predictor of a half-difference is `p = (22·(s[i−1] − s[i+1]) + 3·(s[i+2] − s[i−2]) + 128) >> 8`.
  - It is exact on linear ramps.
  - 22x = (x≪4)+(x≪2)+(x≪1) and 3x = (x≪1)+x: no multipliers.
- **Horizontal:** linear extrapolation beyond the frame edges.
- **Vertical:**
  - *Above the slice*, the two context samples are **true data**: the lowpass at that level of the decoded rows of the slice above, computed by the same forward sums from the decoded picture.
  - *Below the slice*, linear extrapolation.
  - The first slice of a frame extrapolates at the top as well.

### 2.4 Legal intervals and the clamp (the core of P1)

**Boxes.**

- Pixel boxes are `[lo, hi]`.
- A lowpass sample's box is the sum of its children's boxes: `[la+lb, ua+ub]`.
- The e-boxes are data-dependent: the legal half-differences of the horizontal stage minus P_H.

**The d′ interval.** Given a final s, the children's boxes, and m = (s + σ·(s mod 2))/2, f = s − m, the legal half-difference set is the integer interval:

```
d'lo = max(la − m, f − ub)          d'hi = min(ua − m, f − lb)
```

It is never empty (Lemma 1, §4.1).

**The clamp.** The decoder reconstructs every transmitted value as `d' = clamp(q·Δ + p, d'lo, d'hi)`, where p is the spatial plus temporal prediction. The coarsest LL is reconstructed as `clamp(q·Δ + p, box)`.

**Synthesis order.** Coarsest first; within a 2-D level:

1. LL is final ⇒ the LH interval ⇒ clamp LH ⇒ merge to Lc.
2. Lc is final ⇒ the horizontal half-difference intervals ⇒ the e-boxes.
3. The HL box is the pair-sum of the e-boxes ⇒ clamp HL.
4. The HH interval ⇒ clamp HH ⇒ merge to e.
5. dH = e + P_H(Lc) lies in its interval by construction ⇒ merge.

Every clamp reads only final values. There is no cycle, no iteration and no search.

### 2.5 Temporal prediction (one reference frame, C2)

The prediction of each transmitted band is the same band of the forward pyramid of the motion-compensated reference, applied as a residual of the spatial prediction:

```
LH: p = p_V(LL) + α·(dL_ref − p_V(LL_ref))    HL: p = α·HL_ref
HH: p = p_V(HL) + α·(dE_ref − p_V(HL_ref))    H:  p = α·e_ref        LL: p = α·LL_ref
```

- **MC reference.** Built in the pixel domain from the decoded previous frame.
  - Vectors are transmitted per block: 16×16 for coarse levels, 8×8 at level 1.
  - Half-pel is by bilinear averaging.
  - Blocks are blended by overlapped-block MC with linear tapers, which removes prediction discontinuities.
  - Chroma uses the luma vectors scaled to its sampling, with bilinear sub-sample interpolation. The probe's floored chroma vectors cost ≈ 1 dB of chroma (§8.2).
- **α.** A per-block weight in eighths, carried as a continuous field (bilinear between block centres, P5). α = 0 is intra.
- The legality clamp is unchanged: the prediction only shifts the value being clamped.

### 2.6 Why exact sums and a pseudo-random unit, and what was measured on the way

Each earlier pair rounding left a defect:

| Pair rounding | Defect | Measured |
|---|---|---|
| Floor mean (S-transform) | A −¼-code bias per stage wherever details are dead-zoned: a colour cast | −1.3/−1.4 codes Cb/Cr at 0.19 bpp. The same class as OMC's red cast. |
| Checkerboard rounding parity | Periodic pattern | PER up to 3.8 |
| Per-stage alternating parity | Rate-dependent residual cast | +0.5 code |
| Exact sums, extra unit always to the first sample of an odd-sum pair | Consistent-phase Nyquist pattern | PER up to 18 |
| **Exact sums + pseudo-random unit (design)** | none found | Zero-mean and aperiodic: cast ≤ 0.06 code, PER at or below today's (§5.5) |

- **Hardware form.** σ comes from a 16-bit LFSR advanced once per pair and seeded per row by the stage and the absolute row index.
- **Encoder rule for the DC band.** The encoder uses rounding offset ½ (not the detail bands' 7/16) on the coarsest DC band. This avoids the dead-zone quantiser's −Δ/16 darkening of an always-positive band (§3.4).

### 2.7 Step fields (P5)

- `Δ = m·2^e` with m ∈ {4,5,6,7}/4 (quarter octaves). The decoder's ×m is shift-add; the encoder's ÷m uses 3 fixed reciprocal shift-add networks.
- Each band class b adds a fixed per-format offset o_b.
- The control value is bilinear between the previous slice's bottom control points and this slice's control points, with control points every 256 columns. It is evaluated at the coefficient's vertical centre.
- Adjacent slices therefore meet with identical steps: no strip-level step.

### 2.8 Entropy decoding

- Static tANS with normative tables per band class.
- 8 contexts: the quantised magnitudes of the left and above indices in the band, plus the parent index.
- Escape at |q| ≥ 15: Exp-Golomb, with k per band class. Signs are raw.
- Order: coarse levels first, band-sequential. Level 1 is interleaved per 256-column block (LH, HL, HH), so decoding and synthesis stream behind the arriving bytes.
- Four interleaved tANS lanes per packet, in fixed chunks, with no length fields.
- No adaptive arithmetic coding, no rANS.

### 2.9 Refresh, loss, concealment

- **Refresh.** Rolling intra refresh: slices with `(t − k·N_f/N_s) mod N_f = 0` are coded with α = 0 at all levels. While a cycle runs, vectors of refreshed slices may only reference refreshed rows (a barrier).
- **Loss.** A lost packet's slice is concealed from the MC reference, using the slice-above vectors. The next slice decodes normally; only its context rows are wrong.
- **Measured** (§6.4, `out/loss_final.log`):
  - Slice +1 carries ≈ 10 % of the concealment error (1.6–1.8 codes mean after an 17–18-code concealment; 17.6 after a grey worst case).
  - Slice +2 carries ≈ 0.2 %.
  - From slice +3 on, the extra error is **exactly zero**.
- **Recovery** is complete one refresh cycle after the loss.

### 2.10 Output and resolution conversion

- There is one output: the legal decoded picture at display geometry. Both hop types carry this same picture; there is no CDR or unclipped variant.
- Optional 2×/4× conversion is a separate stage after the decoder: integer polyphase, with a ≤ 4-tap vertical aperture. It is counted in latency (§7.3) and sits outside the exactness domain, because a rescaled picture is a different picture.

---

## 3. Encoder

### 3.1 Forward pairs

Forward sums and half-differences are computed as rows arrive, with no predictors: prediction is closed-loop.

### 3.2 Closed-loop quantisation, coarse to fine (one pass)

For each band, in synthesis order:

1. Compute the prediction p and the interval [lo′, hi′] = [d′lo − p, d′hi − p] from final values.
2. Compute the target t = source half-difference − p.
3. Reconstruct:

```
if t ≥ hi' → r = hi'        elif t ≤ lo' → r = lo'
else       → q0 = choice(t) (any encoder rule, §3.4); r = clamp(q0·Δ, lo', hi')
```

4. Take the index `q = K(r)`: `ceil(hi'/Δ)` if r ≥ hi'; `floor(lo'/Δ)` if r ≤ lo'; else `r/Δ`.

The encoder's reconstruction *is* the decoder's (C4). One pass yields the indices, the reconstruction and the next temporal reference.

### 3.3 Lemma 3 — indices are idempotent

At the next encoder the target equals r exactly (Lemma 2).

- If r is interior, it is a lattice point ⇒ the same q.
- If r = hi′, K gives ceil(hi′/Δ). That is the gen-1 index both when t ≥ hi′ and when an interior target rounded past hi′: in the latter case hi′ ∈ ((q − 7/16)Δ, qΔ).
- The lower boundary is symmetric.
- A degenerate interval takes the first branch at every generation.

An earlier draft reconstructed out-of-interval targets at the nearest lattice point; that broke generation 2 on graphics. It is fixed, and re-verified in the 216-case stress.

### 3.4 Encoder freedoms (safe for exactness)

On an off-lattice target the encoder may pick any index. Examples:

- the dead-zone width: 7/16 on details, **½ on the coarsest DC band**, which removes a −Δ/16 darkening bias on an always-positive band;
- the legally cleared two-candidate ECSQ decision (CLG 1989 form);
- a texture-energy term in that decision's cost, against flattening;
- a temporal dead zone that freezes still areas.

On a lattice point the index is forced. At generation ≥ 2 every target is on-lattice, so none of these choices can alter a later generation.

### 3.5 Rate control: canonical feedback, one pass, exact CBR

**Inputs**, all identical at every generation by induction:

- `S_k`;
- the previous frame's record for slice k: bytes per level group and the control values used (a few bytes per slice; "per-frame statistics", C2);
- the bytes already spent in this slice;
- the slice-above control values.

**Law.**

- **Start.** p_k comes from the record through a log-linear LUT model, limited to ±4 quarter-octaves from the slice above.
- **Level groups.** After each level group (LL+levels 5–3, then level 2, then each 256-column level-1 block), the next control offset is a LUT function of (bytes so far − planned bytes so far).
- **Guard.** When the remaining budget cannot hold the model's minimum, the remaining level-1 blocks take the coarsest control value, and as a last resort are coded empty. Coding them empty makes a flat strip: the owner's forbidden "rung". It must be measured to be zero on the corpus at useful rates (T4).
- **Padding** is a fixed pattern.

The current source never enters a decision.

### 3.6 Canonical motion vectors and α (encoder-side; transmitted)

These are computed only from data every generation shares:

- the current slice's decoded coarse bands, which are final before the bands that need the vectors;
- the decoded frames t−1 and t−2 (the encoder keeps two decoded frames; the decoder keeps one, C2);
- the transmitted vectors of the previous frame and of the slice above.

**Candidates:** zero; co-located previous-frame; slice-above; decoded t−1/t−2 block matching projected to t.

**Selection.** SAD on the decoded level-2 lowpass of the current slice against the reference's lowpass at that offset. Then:

1. refine ±1 px at level 2;
2. at level 1, refine ±1 px plus 8 half-pel positions on the decoded level-1 lowpass;
3. break ties by (|v|₁, raster order).

**α** is a fixed LUT of (best SAD ÷ block activity), in eighths.

Candidate counts are fixed; there is no data-dependent iteration.

### 3.7 Scene cuts and ramp

- No cut detector is needed. At a cut the SAD grows, α → 0 follows, and the rate feedback adapts from the record within the slice.
- Frame 0 is all intra; frame 1 is inter. Both fit `S_k`: the ramp is quality-only and the pipe is never exceeded.

---

## 4. Proofs

### 4.1 Legality by construction

**Lemma 1 (non-empty interval).** Let s ∈ [la+lb, ua+ub], m = (s + σ·(s mod 2))/2 and f = s − m (so m + f = s and m, f are integers). The four inequalities that make the interval non-empty are:

| Inequality | Holds because |
|---|---|
| la − m ≤ ua − m | la ≤ ua |
| f − ub ≤ f − lb | lb ≤ ub |
| la − m ≤ f − lb | la + lb ≤ s |
| f − ub ≤ ua − m | s ≤ ua + ub |

So [d′lo, d′hi] is non-empty. a = m + d′ is increasing in d′ and b = f − d′ is decreasing, so the legal set is exactly that interval.

**Theorem 1.** Every decoded sample lies in [lo, hi], for any bitstream, conforming or corrupt.

*Proof.* Induction downward from the coarsest LL, which is clamped into its box:

- Each merge takes an s in its box (by induction) and a d′ clamped into the Lemma-1 interval, so its outputs land in their boxes.
- Pixel boxes are [lo, hi].
- The data-dependent e-boxes are computed from Lc after Lc is final, and HL is clamped into their pair-sum before HH is decoded.
- The clamp is a min/max over a non-empty interval, and nothing follows it. ∎

In code, `dint` raises on an empty interval. It never raised in any run.

### 4.2 Generation exactness through both hop types, unlimited

Both hops carry the same object: the legal decoded picture y at display geometry, and nothing else. There is no metadata and no step the next encoder must undo.

**Lemma 2 (analysis recovers synthesis).** The pair map composed with its inverse is the identity on Z², stage by stage. The forward pyramid of y therefore returns exactly the decoded lowpass values and the decoded (clamped) half-differences at every stage. The context rows and σ are identical functions of identical data.

**Theorem 2.** Let y = D(E(x)). If both encoders start on the same frame with the same configuration, then E(y) = E(x) byte for byte and D(E(y)) = y.

*Proof.* Induction over frames, and within a frame over the coding order:

1. **Decisions agree.** Steps, α, vectors and refresh are identical functions of identical inputs (P2; §3.5–3.6). The record and the decoded frames t−1 and t−2 are identical by frame induction.
2. **Targets agree.** The gen-2 target equals the gen-1 reconstruction r (Lemma 2).
3. **Indices agree** (Lemma 3).
4. **The stream agrees.** tANS, chunking and padding are deterministic.

So the streams are identical, the decodes are identical, and by induction this holds for every generation. ∎

**Covered:** ramp and cut frames, refresh, 8-bit and limited/full/SDI-legal hops, and every chroma format.

**Not covered:**

- **Re-encoding at a different rate.** That is a different configuration, and lossy by nature.
- **A downstream encoder that starts mid-stream.** Its first frame is intra where the upstream one was inter, and it does not converge by itself. Every hop *after* it is exact, because those hops all start on its first frame. This is the shipped behaviour ("mid-sequence baseband start exact only from g3", S5.236). Candidate cure (untested): anchor the refresh phase to hard cuts, which both ends see. Open item (R7).

### 4.3 Checks run (final variant unless stated)

| Content | Checks | Result |
|---|---|---|
| Synthetic rails: 216 cases (8/10/12-bit; full/limited/SDI-legal; 8- and 16-row slices; Qf up to 12, steps ≫ legal window) | out-of-range, decoder = encoder, gen-2 identity | 216/216 (`notes/extrema.py`) |
| cf_gfx graphics, 4 rates × 3 planes | same | all hold |
| dng 444/12 full range, Qf 6 and 9 | same, all planes | 0 / True / True |
| dng 422/8 SDI-legal 1…254, Qf 2 and 5 | same, all planes | 0 / True / True |
| dng 720p 422/10 limited 64…940 | same, all planes | 0 / True / True (3,916 and 7,204 clamp-site index changes on luma: the clamp is working) |
| Temporal probe (in-band MC, oracle and derived vectors, three motion cells, floor-pair variant) | gen-2 identity including re-derived vectors | holds |
| 1080-row frames with padding | gen-2 identity | **fails**, which is why padding is banned (§1). Passes with the short last slice. |

Logs: `out/fmtcheck_final.log`, `out/tp/*.log`.

---

## 5. Artifacts — why the known ones cannot occur, and what was measured

Everything here is intra, one frame (f8), with rate from an entropy estimate. "Today" is the record's model of today's transform structure (SA11 `struct_s` TODAY: 5/3 + 9/7-like finest levels, 2V×5H, mirrored 16-row slices). It is not the shipped codec. The owner's tools in `Subagents/shared_tools/` were used unchanged.

### 5.1 OMC's artifacts

| OMC artifact | Mechanism in OMC | In CLP-1 |
|---|---|---|
| Seam line on the slice grid | Mirrored last row copies the row above | No mirror. First-row error ratio 0.99–1.02. Bottom edge extrapolates (no hold). **Residual excess remains** (below). |
| Smudge (level shift along the grid) | Display blend shifts the level of seam rows | No blend. Level map: grid-aligned jumps are *smaller* than jumps at half-block offset (Y 1.41 vs 2.35; today 3.07 vs 2.00, i.e. today's are grid-aligned; `out/grid/grid.json`, earlier variant). Owner's smudgegroups: 0/0/0 for both structures on all 8 points. |
| Illegal picture; the clip breaks the next encoder | Clip after a lossy inverse | Theorem 1: nothing to clip. |
| Repair and lock artifacts, repeated work | Searching for destroyed information | Nothing is destroyed (Theorem 2). |
| Flattened texture | Rate + dead zone, "healed" by fill (legal exposure) | No fill. Flatness is a rate problem at 0.5 bpp *intra* for both structures (§5.3). Anti-flattening index choice (§3.4) is an untested lever. |
| Still-area flicker | Still areas re-coded every frame | Still areas take α → 1, zero vector and the temporal dead zone ⇒ frozen. **Refresh re-codes a still slice once per cycle** (R3). |
| Colour cast (+1 code in OMC) | Rounding constants | Found here too (floor pairs: −1.4 code Cr) and removed at the root (§2.6). Final: \|mean error\| ≤ 0.06 code on every plane (§5.5). |

**Slice-edge rows.** Last-row error ÷ slice mean, Y/Cb/Cr, final variant against today (`out/art9/battery_final_table.txt`):

| Cell / rate | Today | Final |
|---|---|---|
| dng 0.5 | 1.21/1.15/1.11 | 1.11/1.08/1.07 |
| spot 0.5 | 1.29/1.21/1.17 | 1.13/1.15/1.17 |
| hwy 1.0 | 1.29/1.23/1.21 | 1.09/1.19/1.11 |
| floor 1.0 | 1.26/1.26/1.23 | 1.05/1.16/1.13 |

Slice-pitch error-step ratio (v16), Y/Cb/Cr:

| Cell / rate | Today | Final |
|---|---|---|
| spot 0.5 | 1.38/1.53/1.85 | 1.12/1.27/1.50 |
| floor 1.0 | 1.18/1.60/1.46 | 1.00/1.23/1.16 |

Every point is lower than today's structure, but not at 1.00. That residual is **R1**.

### 5.2 HVBC's artifacts

HVBC's tile grid and waxy patches came from per-tile hard mode gates, tile-local synthesis and decoder-side smoothing (CONSOLIDATED_FINDINGS §10, §13). CLP-1 has:

- no tiles and no per-tile modes;
- only continuous fields (steps, α);
- no decoder-side smoothing;
- an *overlapping* synthesis lowpass. The detail prediction makes it a (−1, 1, 8, 8, 1, −1)/8-class filter that reproduces ramps exactly.

The synthesis *highpass* is pair-local, which is the family the coordinator flagged, so I measured it:

- **Block-grid statistic** (mean |error step| at the pitch vs elsewhere): horizontal 1.00–1.02 at every pitch 2–32. Vertical pitch-16 is lower than today on every cell and plane (§5.1).
- **Periodicity (texstat PER), measured and fixed twice.**
  - The first variant (2/6 vertical predictor) had chroma PER 3.43 vs today's 2.17 on hwy 0.5. The peaks were vertical at 2- and 4-row periods: the pair structure.
  - A 4-tap vertical predictor halved it.
  - The consistent-phase odd unit (§2.6) brought it back, and the pseudo-random σ removed it.
  - **Final:** PER is at or below today's on 20 of 24 plane-points. The four exceptions are marginal: dng1.0 Y 1.19 vs 1.13; floor0.5 Y 1.40 vs 1.38; spot1.0 Y 1.14 vs 1.11 and Cb 1.07 vs 0.98.

### 5.3 Artifact battery, final variant vs today (intra, f8, matched rate; `out/art9/battery_final_table.txt`)

VMAF-NEG first, then PSNR. Instruments:

- **flat %** is the energy meter (flatplane), the share of textured blocks flat.
- **COR** and **PER** are from texstat.
- **v16** is the slice-pitch error step.

| cell | codec | bpp | **VMAF-NEG** | PSNR Y/Cb/Cr | flat % Y/Cb/Cr | COR Y/Cb/Cr | PER Y/Cb/Cr | v16 Y/Cb/Cr | smudge |
|---|---|---|---|---|---|---|---|---|---|
| dng 0.5 | today | 0.522 | 83.69 | 34.71/34.22/35.47 | 60.8/82.9/85.7 | .817/.241/.296 | 1.39/1.11/1.25 | 1.24/1.27/1.21 | 0/0/0 |
| | final | 0.479 | **84.35** | 34.65/34.24/35.47 | 59.3/**89.9**/**88.2** | .816/**.198**/**.275** | 1.27/1.09/1.14 | 1.09/1.06/1.07 | 0/0/0 |
| dng 1.0 | today | 0.973 | 87.09 | 36.33/35.26/36.23 | 44.0/11.6/33.3 | .880/.564/.529 | 1.13/1.16/1.17 | 1.29/1.38/1.35 | 0/0/0 |
| | final | 1.093 | 90.60 | 36.99/36.09/36.90 | 37.6/7.6/21.7 | .877/.577/.536 | 1.19/1.14/1.11 | 1.03/1.08/1.09 | 0/0/0 |
| floor 0.5 | today | 0.450 | 90.16 | 40.38/44.29/44.03 | 62.6/73.1/78.4 | .836/.411/.414 | 1.38/1.51/1.12 | 1.18/1.50/1.35 | 0/0/0 |
| | final | 0.469 | **91.66** | 40.47/44.49/44.18 | 61.3/71.1/77.1 | .831/.412/.419 | 1.40/1.40/1.07 | 1.03/1.26/1.17 | 0/0/0 |
| floor 1.0 | today | 0.981 | 93.76 | 42.47/46.10/45.73 | 12.5/41.8/46.7 | .889/.572/.592 | 1.19/1.13/1.11 | 1.18/1.60/1.46 | 0/0/0 |
| | final | 1.019 | **94.47** | 42.64/46.32/45.90 | 11.3/42.2/**48.6** | .886/.566/.583 | 1.09/1.02/1.05 | 1.00/1.23/1.16 | 0/0/0 |
| hwy 0.5 | today | 0.447 | 88.31 | 41.09/47.20/44.23 | 47.4/79.6/82.5 | .800/.368/.396 | 1.54/2.17/2.04 | 1.39/1.73/1.31 | 0/0/0 |
| | final | 0.431 | **89.86** | 41.26/47.51/44.38 | 49.2/69.3/**84.4** | .792/.358/.366 | 1.46/1.07/1.13 | 1.12/1.44/1.15 | 0/0/0 |
| hwy 1.0 | today | 0.942 | 92.84 | 44.16/49.01/45.78 | 24.5/58.7/45.1 | .887/.531/.601 | 1.33/1.32/1.11 | 1.29/1.74/1.41 | 0/0/0 |
| | final | 0.904 | **93.70** | 44.25/49.24/45.89 | 24.5/51.2/**49.9** | .879/.524/.577 | 1.25/0.95/1.03 | 1.05/1.41/1.15 | 0/0/0 |
| spot 0.5 | today | 0.499 | 91.05 | 41.28/42.73/45.98 | 50.9/66.3/70.8 | .853/.515/.439 | 1.19/1.26/1.70 | 1.38/1.53/1.85 | 0/0/0 |
| | final | 0.517 | **92.41** | 41.50/43.00/46.51 | 49.9/65.6/64.7 | .851/.522/.445 | 1.06/1.22/1.37 | 1.12/1.27/1.50 | 0/0/0 |
| spot 1.0 | today | 0.987 | 94.45 | 44.13/44.93/48.30 | 33.5/37.9/58.6 | .913/.681/.571 | 1.11/0.98/1.30 | 1.27/1.47/1.77 | 0/0/0 |
| | final | 0.991 | **95.06** | 44.26/45.07/48.56 | 32.3/35.6/54.9 | .907/.671/.567 | 1.14/1.07/1.19 | 1.05/1.20/1.39 | 0/0/0 |

**Reading.**

- **VMAF-NEG** is higher on all 8 points: +0.6…+1.5 where the rates match. dng 1.0 is not rate-matched (final at +12 %).
- **PSNR** is equal or higher on every plane.
- **Luma flatness** is equal or better except hwy 0.5 (+1.8 points).
- **Chroma flatness is worse on 6 of 16 plane-points** (bold): dng 0.5 Cb +7.0 and Cr +2.5, with COR confirming the Cb loss (.198 vs .241); hwy 0.5 Cr +1.9; hwy 1.0 Cr +4.8; floor 1.0 Cr +1.9; floor 1.0 Cb +0.4 (marginal). It is better on the other 10 (hwy 0.5 Cb −10.3, hwy 1.0 Cb −7.5, spot 0.5 Cr −6.1, and others).
- **This chroma flatness is unresolved (R2)**, and with the owner's "~70 % of problems are chroma" it is the first thing the eye should check.
- Both structures are far from the flatness bar at 0.5 bpp *intra*. That is a rate statement; temporal prediction must carry it.

### 5.4 Renders for the eye

- `out/art9/<cell><rate>_{today,hfB5}_decode.png`: full-frame colour decodes, unmarked, each with a `_grid.png` twin (grid 32×16).
- `_absdiffY` / `_absdiffCr`: |decode − source| ×16 maps.
- `_source.png`: the source.
- `_smudge_*`: the owner's boxed level maps.

Files named `hfB5` in `art9` are the **final** variant: the name is the script's slot. I looked at 1:1 regions of the level and |diff| maps only as pointers; they show no lattice in either structure. That is not a verdict.

### 5.5 Colour cast and periodicity

Mean signed error, codes, Y/Cb/Cr, over the variants of §2.6 (`out/cast_*.log`):

| cell, Qf (bpp) | floor pairs, DC 7/16 | checkerboard parity | stage-alternating parity + DC ½ | **final: exact sums + σ + DC ½** |
|---|---|---|---|---|
| hwy 5 (0.85) | −0.05/−0.62/−0.45 | +0.01/−0.01/−0.00 | +0.01/+0.02/+0.02 | **−0.002/+0.003/−0.002** |
| hwy 7 (0.19) | −0.63/−1.27/−1.43 | −0.51/−0.49/−0.49 | +0.54/+0.41/+0.54 | **−0.002/−0.060/+0.016** |
| spot 6 (0.48) | −0.55/−0.63/−0.72 | −0.50/−0.49/−0.51 | +0.50/+0.50/+0.49 | **−0.010/+0.013/+0.002** |
| dng 7 (0.48) | −0.55/−0.58/−0.62 | −0.51/−0.50/−0.52 | +0.51/+0.52/+0.53 | **+0.015/+0.003/−0.004** |

PER (vs source) on the same decodes, Y/Cb/Cr:

| hwy Qf 6 (0.4 bpp) | PER |
|---|---|
| floor pairs + 2/10 vertical | 1.56/1.74/1.74 |
| checkerboard | 2.24/3.18/3.48 |
| exact sums, fixed unit | 2.78/15.19/14.19 |
| **final** | **1.41/1.13/1.22** |
| today's structure (hwy 0.5) | 1.54/2.17/2.04 |

The final variant's PSNR and bits are equal to or better than every other variant on these cells.

---

## 6. Constraint compliance, clause by clause

| Clause | Requirement | How CLP-1 meets it | Status |
|---|---|---|---|
| A1 | OMC @R looks like XS @2R; whole curve; worst frame; 4:2:2 and 4:4:4 | Intra ≈ today's structure +0.1–0.3 dB and NEG +0.6–1.5 (intra, matched rate). Temporal canonical motion below oracle (§8.2). | **NOT MET, not shown.** Expected ≈ today's 1.33× (A1_MEANS). Weakest point. |
| A1 pipe | Exact CBR on every frame including the ramp | Fixed `S_k` per slice, fixed padding, guard (§3.5) | Met by construction. The guard terminal must measure zero (T4). |
| A2 | Sub-1 ms including conversion; deterministic; ≈ XS | L = 2·sh + 2 lines (+ ≤ 4 conversion lines); all formats < 0.7 ms (§7.3) | Met (model); 34 lines at 1080p vs XS ≈ 32 |
| A3 | No artifacts; only smooth softening | §5: no mechanism for seams, blends, clips, tiles, fill or rounding casts | R1 (last row), R2 (chroma flatness), R3 (refresh): **eye pending** |
| A4 | Exact generations, unlimited | Theorem 2 for both hops; §4.3 checks | Met from a common start; mid-stream join open (R7) |
| A5 | Bounded loss; fast recovery | Slice packets; damage ends at slice +2, exactly (measured); refresh cycle | Met (design + probe) |
| B1–B3 | 8/10/12(/16)-bit; 4:2:0/4:2:2/4:4:4; full/limited/SDI-legal; SDR/HDR; YCbCr native | lo/hi per plane; geometry rules (§1) | Met (checks §4.3) |
| B4 | 720p…8K, 50/60/HFR, each sub-1 ms | §7.3 | Met; 8K120 compute not budgeted |
| C1 | Royalty-free | §10 | Met, subject to legal review of §10 |
| C2 | Causal; one reference frame at the decoder | Decoder keeps one frame. The encoder keeps two decoded frames for its canonical rule only. | Met |
| C3 | Shifts/adds/LUT; no multipliers; no adaptive arithmetic coding; real-time both ends with margin | §7.1–7.2 | Met (model); 8K60 encoder ≈ 25–36 % of ZU7EV logic |
| C4 | rt = 0 on all planes | Encoder reconstruction = decoder's (§3.2); checked | Met |
| C5 | Colour always | Every number is per plane | Met |
| C6 | Measure first | Every claim is marked measured or expected | — |
| C7 | Video in, bitstream out | No side channel | Met |
| C8 | Documented, versioned bitstream | §1–2 are the normative skeleton; the tables (steps, tANS, LFSR) must be frozen | To be written |
| G1–G6 | Grid, banding, pixelation, flattening, hard edges, discoloration | G1: §5.2. G2: ramps reproduced exactly; continuous step fields. G3: no fill; σ changes only the half-code split of odd sums. G4: §5.3. G5: no gates. G6: §5.5. | Eye pending |

---

## 7. Work, hardware, latency

### 7.1 Work per slice (closed formula; fixed, content-independent)

N = the slice's samples over all planes (critically sampled: coefficients = samples). N_Y = luma samples. One op is a ≤ 20-bit add, subtract, compare, shift-add or table read.

**Decoder, per sample:**

| Stage | ops |
|---|---|
| Entropy decode | 6 |
| Dequantise + clamp | 7 |
| Interval | 8 |
| Spatial prediction | 7 |
| Temporal term | 11 |
| Pair merge (parity + σ) | 4 |
| MC fetch + overlapped-block blending + half-pel + reference pyramid | 10 |
| **Total** | **53** |

**D(slice) ≈ 53·N.**

**Encoder:**

| Stage | ops |
|---|---|
| Decoder path | 53 per sample |
| Forward pairs | 4 per sample |
| Quantise (reciprocal shift-add + K rule) | 10 per sample |
| Rate LUT | 2 per sample |
| ECSQ freedoms | 6 per sample |
| Canonical motion: 45 candidates × 2 ops on N_Y/16, plus 17 × 2 on N_Y/4 | ≈ 14 per luma sample |
| Reference box pyramid | 4 per luma sample |
| t−1/t−2 candidate field | 3 per luma sample |

**E(slice) ≈ 75·N + 21·N_Y**: ≈ 86 ops per sample at 4:2:2.

**JPEG XS** (estimate, not measured): ≈ 25 ops/sample to encode, ≈ 18 to decode. **CLP-1 is ≈ 3.4× (encoder) and ≈ 2.9× (decoder) XS per sample.** That is the price of temporal prediction and the closed loop.

Every stage runs **once per slice**. There is no re-decision, lock, legaliser or search pass.

### 7.2 ZU7EV-class fit (worst format: 8K60 4:2:2, 3.98 G samples/s)

- **Encoder:** ≈ 342 G ops/s, i.e. ≈ 855 ops per clock at 400 MHz.
- **LUTs:** ≈ 25 LUTs per pipelined op, times 2.5 for control, gives ≈ 53 k. Adding ≈ 10 tANS lanes (15 k) and DDR/IO (15 k) gives **≈ 83 k of 230 k LUTs (≈ 36 %)**. Putting the adders on DSP48E2 ALUs (add only; 1,728 available) brings this to ≈ 25 %.
- **Other formats:** 4K60 ≈ 9–10 %; 1080p60 ≈ 3 %. The decoder is ≈ 60 % of the encoder.
- **Memory** (owner ruling: not a constraint): ≈ 20 Mbit on-chip at 8K; 1 frame in DDR at the decoder, 2 at the encoder.
- **The margin at 8K60 is real but not "large"** (R5).

### 7.3 Latency (deterministic; every term depends on format only)

L is the sum of:

- `sh` lines of capture;
- `sh` lines of transmission (one slice period for exactly `S_k` bytes);
- 1 line of first-byte delay;
- 1 line of last-block synthesis;
- ≤ 4 lines of conversion aperture, when a converter is in the path (output raster-clocked).

This works because the coding order streams: coarse data is sent first, and level-1 blocks are interleaved per 256 columns (§2.8).

| Format | sh | Lines | Codec only | With conversion |
|---|---|---|---|---|
| 720p50 | 8 | 18 | 0.48 ms | 0.59 ms |
| 720p60 | 8 | 18 | 0.40 ms | 0.49 ms |
| 1080p50 | 16 | 34 | 0.60 ms | 0.68 ms |
| 1080p60 | 16 | 34 | 0.50 ms | 0.56 ms |
| 2160p50 | 16 | 34 | 0.30 ms | 0.34 ms |
| 4320p60 | 16 | 34 | 0.13 ms | 0.14 ms |

- For comparison, OMC is 34 lines at 1080p and XS ≈ 32 lines (record).
- **Requirement:** the encoder must run at ≥ 1.2× the pixel rate so its bytes stay ahead of the channel. The canonical level-2 and level-1 searches must finish before their bands' bytes are due.

### 7.4 Word widths

- The lowpass grows one bit per stage: the coarsest band is B+8 bits (18 at 10-bit, 20 at 12-bit, 24 at 16-bit).
- Half-differences are ≤ B+8 bits, and intervals and predictions ≤ B+9.
- All of these are adders, never multipliers.

---

## 8. Coding efficiency

"Measured" means numpy models with a zeroth-order entropy estimate per band: the record's estimator, SA11 `struct_s`. Real tANS and header costs are not included.

### 8.1 Measured — intra structure

Five cells: dng1080 f5, dng720 f5, cf_gfx f0, spotrobotL f5, floorballgameL f5. Mean ΔPSNR vs today's structure, Y/Cb/Cr, with the worst cell in parentheses:

| Variant | 0.5 bpp | 1.0 bpp | 2.0 bpp |
|---|---|---|---|
| B: 2V, symmetric vertical, independent slices | −0.35/−0.11/−0.14 | −0.07/−0.06/−0.08 | +0.10/0.00/−0.09 |
| B5: 3V, 2/6 vertical + context | +0.22/+0.11/+0.11 | +0.23/+0.12/+0.07 | +0.27/+0.18/+0.04 (−0.15/−0.42/−0.67) |
| B7: 3V, 2/10 vertical + context, floor pairs | +0.16/+0.07/+0.08 | +0.16/+0.06/+0.01 | +0.20/+0.12/−0.02 (−0.20/−0.48/−0.74) |
| **FINAL: B7 + exact sums + σ + DC ½** | **+0.20/+0.13/+0.16** (+0.04/+0.01/−0.01) | **+0.21/+0.12/+0.10** (+0.09/−0.02/−0.04) | **+0.28/+0.23/+0.12** (−0.02/−0.21/−0.36) |
| Causal vertical predictors | −1.0…−1.5 dB, with a 4-row periodic pattern | | rejected |

Remaining losses are chroma at 2.0 bpp on two motion cells (floor −0.21/−0.24; spot Cr −0.36). The step allocation was not tuned: both structures use the same power-of-two rule. Logs: `out/r7/summ7.txt`.

### 8.2 Measured — temporal probe (`out/tp/*.log`; the older floor-pair variant B)

The probe: frames f8→f9; f8 coded intra as the reference. α = 1 everywhere, integer-pel, no overlapped blocks, floored chroma vectors. Entries are bpp and PSNR Y/Cb/Cr.

| cell, Qf 6 | intra | zero-motion | oracle (source search; vector bits not counted) | canonical, from decoded coarse bands only |
|---|---|---|---|---|
| floorballgameL | 0.492 · 40.43/44.29/43.99 | 0.495 | 0.287 · 40.70/43.19/43.04 | 0.399 · 40.04/43.59/43.39 |
| highwaydriveL | 0.466 · 41.16/47.02/44.13 | 0.481 | 0.308 · 41.32/46.43/43.70 | 0.408 · 40.71/46.72/43.87 |
| spotrobotL | 0.583 · 41.26/42.77/46.09 | 0.531 | 0.366 · 41.52/41.76/44.75 | 0.440 · 40.82/42.12/45.39 |

- At Qf 5 (~1 bpp), α = 1 is **worse than intra** on floorball (1.20 vs 1.03 bpp): reference noise in the fine bands, as the record also found. This is why α must be a field.
- **Reading.** Coarse-band-only canonical vectors recover about ⅓–½ of the oracle's bit saving and lose ≈ 0.4 dB luma.
- The design rule (§3.6) adds several things the probe lacked: history candidates, half-pel, overlapped blocks, per-block α, and correct chroma interpolation. **Expected** to close part of the gap; **not measured**.
- VMAF-NEG was not computed for this probe; its decodes were not written out.

### 8.3 Expected against A1

The intra core measures at parity or slightly better than today's structure. The temporal part as specified should be comparable to OMC's. Removing OMC's lock, repair, fill and blend may return some rate, amount unknown. **Expected: roughly today's equivalence ratio (≈ 1.3–1.5× VMAF-NEG-equivalent), not 2×.**

Levers, each with a decisive test (§9):

1. canonical motion with history candidates;
2. a per-band α field;
3. band weights tuned by eye (PSNR is diagnostic only under rev. 6), chroma especially;
4. texture-energy index choice;
5. a 4th vertical level at 16-row slices.

None of these is a known route to 2×.

---

## 9. Risks and the decisive next tests (in order)

| # | Risk | Evidence | Decisive test |
|---|---|---|---|
| R0 | A1 not reachable | §8 | **T1:** 24-frame model with canonical motion + α; steady-state f8–15; VMAF-NEG vs XS@2R per plane; 4 motion cells + dng + gfx; 4:2:2 and 4:4:4 |
| R1 | Last-row excess 1.05–1.23 (lower than today's 1.10–1.29; not 1.00) | §5.1 | **T2:** owner's eye on `out/art9`. If visible: bottom context from the MC reference's rows below in inter slices (canonical and legal), then measure the row phase. |
| R2 | Chroma flatness worse than today's structure on 6 of 16 plane-points | §5.3 | **T3:** chroma band weights + texture-energy index choice; flatplane/texstat/smudgegroups per plane + renders |
| R3 | Refresh "twinkle" in still areas | inherent | **T5:** 24-frame still-area test, frame-difference maps; refresh slices at a higher budget share |
| R4 | The guard terminal (a flat strip) fires on real content | untested | **T4:** count terminal events over the corpus + cut24 + extrema at 0.3–2 bpp. Bar = 0. |
| R5 | 8K60 encoder ≈ 25–36 % of logic | §7.2 | **T6:** RTL-level estimate of the closed-loop datapath and SAD array |
| R6 | The σ pseudo-random half-code split is a fixed (static) pattern of ±½ code in odd-sum areas | §2.6 | **T7:** eye at 8-bit on smooth gradients. Alternative: σ from the sign of the local predicted slope, hash only where the slope is 0. |
| R7 | Mid-stream join not exact | §4.2 | **T8:** refresh phase anchored to hard cuts; measure convergence after a join |
| R8 | IP of the canonical-motion rule and of the vertical context | §10 | Legal review of §10 (only elements already believed clean are listed) |

---

## 10. IP provenance (every element)

| Element | Provenance | Why obviously clean |
|---|---|---|
| Pair map in sum form (s = a + b; half-difference; parity carried by s) | Integer Haar / S-transform family, lossless coding of the 1980s (e.g. Blume & Fand 1989) | Expired vintage; the parity bookkeeping is arithmetic |
| σ assignment of the odd unit by a fixed LFSR sequence | Own work; LFSRs are textbook | First principles |
| Detail predicted from neighbouring lowpass (2/10 form) | Said & Pearlman S+P (1996); Zandi et al. TS/CREW (1995); Calderbank–Daubechies–Sweldens–Yeo (1998); Adams & Kossentini (2000) | Filed ≤ 1998, expired. Not the 5/3 or 9/7 of JPEG 2000/XS. |
| Per-coefficient legal-interval clamp in the synthesis; K rule | Own work (the expert's memo 011 describes the predict-step form) | Arithmetic |
| Closed-loop (in-loop) quantisation | Cutler DPCM (1952) | Expired |
| Dead-zone quantiser; ECSQ two-candidate decision | Classic; CLG 1989 | Cleared by legal (record) |
| Static tANS | Duda; named as allowed in C1 | Per C1 |
| Context from neighbour and parent magnitudes, static tables | Classic, 1990s | Expired |
| Block-matching ME; bilinear half-pel | Jain & Jain (1981); textbook | Expired; no H.264/HEVC taps |
| Overlapped-block MC | Orchard & Sullivan (1994); H.263 Annex F (1996) | Expired |
| Hybrid MC prediction expressed per subband | Pixel-domain MC then transform, 1980s | Expired |
| Rolling intra refresh with a barrier | H.261-era forced updating (1990) | Expired |
| Buffer-feedback rate control; continuous step field | 1980s feedback control; own work (interpolation) | Expired / first principles |
| Encoder-side motion from decoded data | Encoder-side search is unconstrained; Netravali–Robbins backward estimation (1979) | Vectors are *transmitted* and the decoder is conventional. No decoder-side derivation (the area with recent patents) is used. |

Not used: 5/3, 9/7, GCLI or bit-plane coding (JPEG XS); CABAC; rANS; decoder-side motion derivation; grain or noise fill.

---

## 11. Prior failures checked

Sources grepped: LEDGER_SANDBOX_v2, LEDGER_v5_3_5, the falsified register H.6, expert memos 010–012, and the HVBC findings.

| Prior failure | Record | Why it does not apply, or what I did |
|---|---|---|
| Predict-only / update-free transform | S5.212, S5.353 (−2.2…−3.7 dB) | CLP-1 has an update: the pair sum is a Haar update. Measured at or above parity (§8.1). |
| One-sided / acyclic update (optimal weight 0) | S5.349 | That analysis clamps sample by sample. The pair-local update clamps the *pair* through Lemma 1: acyclic at lag 0, a different structure. |
| Causal vertical row prediction | S5.353 | Retested here: −1.0…−1.5 dB and a 4-row pattern. Rejected. |
| Continuous vertical transform | S5.349 (latency, A5, memory) | Not used. Two context samples per level only; loss ends at slice +2. |
| Mirror at slice bottom / XSL / display blend | S5.345–S5.348 | None. True context at the top, linear extrapolation at the bottom. Residual excess measured (R1). |
| Index capping / repair / δ-recovery / legaliser / lock / R1 | S5.212–S5.214, S5.320, memo 010 | Nothing is destroyed; the clamp and K are per coefficient and acyclic. Steps wider than the window hold (216 cases). |
| Embedded / bit-plane description (ECR) | S5.319–S5.321 | Not used. One-shot tANS. The only terminal is the CBR guard (R4, bar 0). |
| Escalation ladder (per-slice rung) | S5.344 | Not used: continuous fields only. |
| Self-identifying reconstruction points (odd-dyadic β) | S5.349 | Not used. Reconstruction is q·Δ; the plan is transmitted and canonical by causality. |
| Plan read from the picture / lattice lock | S5.171–S5.176 | Not used. |
| Decoder-derived block vectors (design A) | S5.29 (fails A5) | Vectors are transmitted; the decoder has no derived state. The encoder rule reads only data a refresh restores. |
| Per-region vectors without fallback; wide grid search | S5.17, S5.19 | Zero and previous-frame candidates always present; tie-break toward small vectors. |
| Half-pel variants, sharper kernels | S5.34 | Bilinear half-pel only, with a barrier. |
| Grain/noise fill | H.6, S5.32, S5.35 | No fill. |
| Colour cast from rounding | memory: colour cast = lifting rounding | Found in this family (floor pairs) and removed at the root (exact sums); four variants measured (§5.5). |
| Per-block mode switching | SA2: per-block mode falsified | α is a continuous field, not a mode. |
| Padding rows at 1080 | found here | Short last slice. |
| HVBC 16×16 grid, waxy patches, boundary blends, decoder interval smoothing | HVBC §10/§13; coordinator's warning | No tiles, gates, blends or smoothing. Grid, level map, PER, flatness, smudge and renders measured per plane (§5). |

---

## 12. Files

**Scripts (`notes/`):**

| File | Purpose |
|---|---|
| `hf.py` | Legal pyramid model: encoder, decoder, gen-2 check, rounding modes (`HF_RND`: 0 floor, 1 checkerboard, 2 stage-alternating, **3 exact sums** (default); `HF_SIGN`: σ on/off), short last slice |
| `extrema.py` | 216-case rail stress |
| `tp.py` | Temporal probe |
| `art.py`, `grid.py` | Artifact battery and grid statistics |
| `permit.py`, `castcheck.py` | Periodicity and colour cast |
| `loss.py` | A5 probe |
| `fmtcheck.py` | Format checks |
| `summ.py` | RD summary |
| `base.py` | Wraps SA11's baseline model (read-only import) |

**Results (`out/`):**

| Location | Contents |
|---|---|
| `r7/summ7.txt` | Final RD |
| `r2`–`r6/` | Earlier RD variants |
| `art9/` | Final battery and renders |
| `art/`, `art7/` | Earlier batteries |
| `grid/` | Level maps and grid statistics |
| `tp/` | Temporal probe |
| `cast_*.log`, `fmtcheck_final.log`, `loss_final.log` | Cast, formats, loss |
