# Memo 011 — to Fable (OMC-1 coordinator), from the codec expert, 2026-09-27

## Summary

The clip is the only operator in the pipeline that is neither invertible nor computable from the decoded picture, and every attempt in section 4 of Memo 010 was a way of living with it. The fix is to remove it from the pixel domain and fold legality into the synthesis itself, where it becomes a per-coefficient clamp that the next encoder can recompute exactly. Doing that requires one structural change to the transform (no update step), one change to the quantiser (closed-loop, interval-aware, with self-identifying reconstruction points), and one change to the encoder's order of decisions (the first encoder's last act is to run the second encoder's procedure on its own reconstruction and emit what that returns). With those in place the lock disappears, the legaliser disappears, the δ search disappears, and the worst case is one synthesis pass at the decoder and one closed-loop quantisation pass plus at most two packs at the encoder.

Appendix A writes out the lifting equations per level, with the clamps in place, for the hardware team.

## 1. What exactness requires, stated once

Write E for the encoder as a function of a picture and D for the decoder as a function of a bitstream. Byte-exactness through a baseband hop is the single condition

    E(D(E(x))) = E(x)

for every legal source x, which in turn implies that D is a fixed point from generation 2 onward. Two things must hold for that to be true:

1. **The decoded picture must lie in the set of pictures the codec can describe.** If y = D(b) and there is no bitstream that reproduces y exactly, no encoder can be exact on it. The clip violates this: clip(T⁻¹(R(I))) is in general outside the image of D.
2. **E must be a canonical function of the picture.** Every decision — step size per band, intra/inter per band, refinement and chunk boundaries, refresh phase, bank state — must be either recomputable from y alone or pinned by a fixed tie-break rule applied identically by every encoder.

Condition 1 is about what the decoder emits. Condition 2 is about what the encoder decides. The work so far went mostly into condition 2 (the lock) while condition 1 was broken, which is why every lock result was polluted by clipped samples.

## 2. Legality inside the synthesis, without search

### 2.1 The observation

In an inverse lifting step of the form `odd = d + P(even)`, the decoder knows P(even) before it computes odd. So it also knows the exact interval of d for which odd is legal:

    d ∈ [lo − P(even), hi − P(even)].

If the decoder reconstructs d as `r = clamp(R(q), interval)` instead of the bare cell point R(q), the output sample is legal by construction, and the next encoder, whose forward lifting computes `d′ = odd − P(even)` with the same evens, gets d′ = r exactly. Nothing has been destroyed; the clamp has been moved to a place where both sides can compute it.

### 2.2 Making the clamped value quantise back to its own index

The clamped point r may fall inside a different cell than R(q), so the first encoder cannot simply emit q. It emits the fixed point of one re-quantisation:

    q* = Q(clamp(R(q), interval))
    r* = clamp(R(q*), interval)

One step suffices. Either R(q*) lies inside the interval, in which case r* = R(q*) is an ordinary lattice point and Q(r*) = q*; or R(q*) lies outside on the same side as R(q), in which case r* is the interval boundary b, and Q(b) = q* by definition of q*. In both cases the next encoder computes Q(r*) = q*. This is provable per coefficient with no dependence on neighbours, which is what index capping lacked.

The encoder's own reconstruction is r*, and its quality equals the plain clip measured today: the interval is exactly the set of d values giving a legal pixel, so the clamp lands where the clip would have landed. No bits change because the index alphabet and the tANS tables are untouched; only the reconstruction rule and the choice of index at overshoot sites change.

### 2.3 Why this needs a predict-only transform

The argument in 2.1 requires that when a sample is being produced, all the values its clamp interval depends on are already final. That is a statement about the synthesis being a directed acyclic chain. The 5/3 update step breaks it: `even = a − U(d)` makes the even pixel depend on the high band, while the interval of d depends on the even pixel. Every local fix then cascades through U into the neighbouring band. The "fix at one sample breaks its neighbour" measured with capping, and the slow convergence of the K-round legaliser on dense content, are both this cycle. The legaliser is in fact the correct projection (onto cell ∩ range); the cycle is what stops it from finishing in bounded work.

With a predict-only lifting — the interpolating (N,0) family: low band = the even samples untouched, high band = odd − P(even) — the chain is acyclic at every level, in both directions:

- Reconstruct L fully first, coarsest level upward. At each level the even rows are the coarser output (already legal), and each odd row is LH + P(even rows), clamped into [lo, hi]. The LL band at the coarsest level is quantised directly with interval [lo, hi].
- Then reconstruct H. Every H sample, whether it comes straight from HL or from HH + P(even H rows), is clamped into [lo − Pcol(L), hi − Pcol(L)], where Pcol(L) is the horizontal predictor from the already-final L columns.
- Odd pixels = H + Pcol(L) are then legal without any further operation.

Dense rail plates are handled by the same per-coefficient clamp as sparse edges; there is no coupling for density to amplify. The two finest levels, where the 9/7-like filter lives, become (4,0) or (6,0) predictors; longer predictors buy back some of the high-band compaction the update step gave.

This is the one place where a cost could appear. Predict-only lifting has an aliased low band and lower coding gain at low rates than 5/3. At contribution rates, where every band is coded finely, I expect the loss to be small (a few tenths of a dB at most, possibly nil once the predictor length is chosen), but I have no measurement and this should be the first experiment. If it fails the 2× target, I have no bounded-iteration proof for any transform with an update step, and that should be treated as the open problem rather than re-adding the update and hoping.

The cross-slice term is compatible: the rows of the slice above are final before this slice starts, so they are legitimate predictor inputs. The display blend is compatible as long as it remains an exactly invertible integer blend of legal values, which it is today.

## 3. Making every decision canonical

### 3.1 Step sizes: read them off the picture

Replace the lock's enumeration with a reconstruction alphabet that is self-identifying. Reconstruct each nonzero index as

    r(q, Δ) = sign(q) · (|q| + β) · Δ,   β = m / 2ᵏ,  m odd, fixed per band.

Then 2ᵏ · r = sign(q) · (2ᵏ|q| + m) · Δ, and the odd factor guarantees that the number of trailing zeros of 2ᵏ · r equals that of Δ, for every q. Any single nonzero, non-clamped coefficient reveals the band's Δ with a count-trailing-zeros operation. The texture bias survives as the choice of m; all that is required is that the reconstruction sets of different Δ be pairwise disjoint, which any odd-numerator dyadic β with Δ ≥ 2ᵏ satisfies (for finer Δ use a small per-Δ table with the same disjointness, checked once offline).

Clamped coefficients are excluded from inference by a test the next encoder can perform locally: a coefficient equal to its own interval boundary is a clamped one. A lattice point that coincidentally equals the boundary is excluded harmlessly, since quantising it returns the same index either way.

Refinement steps and partial chunks are then a question of syntax, and the rule is the same: any spatial granularity of Δ must be recoverable from the signatures in a fixed coding order. A chunk boundary is the first coefficient whose signature shows the coarser step. If the syntax cannot be recovered this way, simplify the syntax rather than adding a search.

### 3.2 Tie-breaks where the picture underdetermines the description

A band whose coefficients are all zero or all clamped reveals no Δ. Fix a total order over descriptions and take the first consistent one — coarsest step, then a fixed mode order — and require every encoder to apply it. The first encoder does this inline during its coarse-to-fine pass: after quantising a band it checks whether its own y would let the next encoder infer the Δ it used; if not, it adopts the tie-break Δ and requantises that band before moving to the finer ones (whose intervals depend on it). At most one requantisation per band, and a coarser step on an already-empty band costs fewer bits, never more.

### 3.3 Intra/inter per band

Both encoders identify the mode from the picture: a band is intra if its non-clamped nonzero coefficients share one signature, inter if the same holds for c − pred. If both hold, the fixed order decides. The first encoder may choose its mode from the source by any heuristic, but it then applies the identification rule to its own reconstruction and emits whatever the rule returns; both descriptions reproduce y exactly whenever both are consistent, so the swap is free. Motion vectors are already decoder-derived, so they are canonical once the previous decoded frames are identical, which holds by induction from frame 1.

### 3.4 Sequence-level state

Frame 1 is always intra, the bank starts empty, and the refresh phase is a function of frame index from stream start. These are conventions rather than things recoverable from the picture, and they are the only ones. A hop that starts mid-stream will produce identical pictures once every slice has been refreshed and identical bytes once its refresh phase coincides with the upstream one; if byte identity from a mid-stream start is required, pin the phase to something both sides observe (frame count modulo 8 from the first frame both have seen).

### 3.5 The encoder's order of decisions

The principle behind all of the above: **the first encoder encodes its own reconstruction, and its final emitted description is the output of the canonical procedure applied to that reconstruction.** Concretely, per slice:

1. Forward transform of the source; open-loop plan choice from source coefficients, as today (estimated bits from the static tables).
2. One closed-loop pass, coarse-to-fine, band by band: quantise, reconstruct with interval clamps, re-quantise at clamped sites, check signature determinacy, apply tie-breaks. This pass produces both the indices and y.
3. Pack. If the closed-loop indices exceed the budget (they differ from the open-loop ones only at overshoot sites, so this is rare), step Q one notch coarser and repeat step 2 once; the bank absorbs the rest.

The second encoder runs the same forward transform, recognises the slice as already-canonical during the same pass (every band consistent, every non-boundary coefficient on-lattice), and packs. If recognition fails — the input is fresh source, or a region was damaged by packet loss — it falls through to steps 1–3. A false positive on fresh source is harmless: it can only occur when the slice already lies exactly on a lattice, and the emitted stream then reproduces it exactly.

## 4. Worst-case work per slice

- Decoder: one inverse pass with a compare-and-clamp per sample. The K-round legaliser goes away.
- Fresh encode: one forward pass with open-loop plan estimate (today's cost), one closed-loop quantise/reconstruct pass, at most two packs. The 50-pass lock and the repair engine go away.
- Encode at a hop: one forward pass with inline signature inference and boundary detection, one pack. Optionally one decode to verify, which fits the "one pass plus two packs" budget.

All operations are shifts, adds, compares and count-trailing-zeros; no per-pixel multipliers, no iteration whose count depends on content. Latency is unchanged from today's forward and inverse passes; the closed-loop pass replaces the plain quantise rather than adding to it, because reconstruction is already computed for temporal prediction.

## 5. Where the project went astray

1. **Legality was treated as post-processing.** The clip sat outside the invertible chain, so every later mechanism — repair, capping, δ recovery, the legaliser — was an attempt to reconstruct information after it had been thrown away. Attempt 3 asked the second encoder to invert a many-to-one map; on dense content that is unbounded by construction.
2. **The plan was treated as a search problem.** A lock that enumerates candidates and tests lattice membership pays fifty passes for something the reconstruction alphabet can hand over for free. The lattice-point test was also the wrong test after attempt 8: the legaliser had already produced in-cell coefficients that would have re-quantised correctly, and the lock rejected them for being off-point.
3. **Open-loop quantisation.** The first encoder decided from the source and never checked whether its own reconstruction would lead a second encoder to the same decisions. Attempt 5 got close to the right idea (re-choose the plan for the next encoder's benefit) but searched over alternative plans instead of re-quantising within the plan.
4. **The update step.** It is the source of every neighbour-coupling failure measured, and the 9/7-like filter at the two finest levels put the strongest coupling exactly where the overshoot lives.
5. **The embedded bit-plane attempt** had the right instinct — make the description canonical from the picture — at the wrong layer, paying 1–17 % of bits for a property that reconstruction-point signatures give at zero cost.

The slice structure, the bank, the static tANS tables, the decoder-side motion derivation and the rolling refresh are all fine and can stay as they are.

## 6. What to measure first, in order

1. Predict-only (4,0)/(6,0) vs. current transform, luma dB at equal bits on the reference set. This decides whether the design is viable within the 2× target.
2. Interval-clamped closed-loop quantisation on the dense rail set: count of samples reaching the final stage out of range (should be zero by construction) and generation-2 byte identity.
3. Signature inference success rate on natural and graphics content, and the frequency of tie-break bands.

---

# Appendix A — Lifting equations per level, with clamps

## A.1 Notation

- `lo`, `hi`: legal range of the signal format (e.g. 4 and 1019 for 10-bit SDI).
- `clamp(v, a, b) = min(max(v, a), b)`.
- `x[i]` are samples of a 1-D signal (a row or a column); `e[i] = x[2i]` (even), `o[i] = x[2i+1]` (odd).
- `P(e)[i]`: predictor of the odd sample at position 2i+1 from even samples. Symmetric extension at the ends.
- All predictors are integer with a final arithmetic right shift; every constant below decomposes into at most four shift-adds, so no per-pixel multiplier is needed.

Predictors (Deslauriers–Dubuc interpolating family):

    (2,0):  P(e)[i] = (e[i] + e[i+1] + 1) >> 1
    (4,0):  P(e)[i] = (9·(e[i] + e[i+1]) − (e[i−1] + e[i+2]) + 8) >> 4
    (6,0):  P(e)[i] = (150·(e[i] + e[i+1]) − 25·(e[i−1] + e[i+2]) + 3·(e[i−2] + e[i+3]) + 128) >> 8

Shift-add forms: 9v = (v<<3)+v; 150v = (v<<7)+(v<<4)+(v<<2)+(v<<1); 25v = (v<<4)+(v<<3)+v; 3v = (v<<1)+v.

Suggested assignment: (6,0) or (4,0) at the finest level, (4,0) at the second, (2,0) at coarser levels; to be settled by measurement 1 of section 6.

## A.2 One-dimensional forward step (encoder), predict-only

    L[i] = e[i]                      (low band = even samples, unchanged)
    H[i] = o[i] − P(e)[i]            (high band)

Exactly invertible for any integers, as with all lifting.

## A.3 One-dimensional inverse step (decoder and encoder reconstruction), with clamp

Given reconstructed L (already final and legal for its own interval) and the transmitted/predicted high-band value, the odd sample is produced as

    p       = P(L)[i]
    Hmin[i] = lo_H − p
    Hmax[i] = hi_H − p
    Hrec[i] = clamp(Hval[i], Hmin[i], Hmax[i])
    o[i]    = Hrec[i] + p
    e[i]    = L[i]

where `[lo_H, hi_H]` is the legal interval of the *output* signal of this step: `[lo, hi]` when the outputs are pixels or L samples (see A.5), and the H-sample interval derived from the column predictor when the outputs are H samples. `Hval[i]` is the dequantised value (plus the temporal prediction in inter mode), before clamping.

## A.4 Two-dimensional structure per level

Forward (encoder), level ℓ operating on the input image (or the LL of level ℓ−1) of size W×Hgt:

    Horizontal first, on every row:      Lcol = even columns;   Hcol = odd columns − Prow(even columns)
    Vertical on Lcol, every column:      LL = even rows of Lcol; LH = odd rows of Lcol − Pcol(even rows of Lcol)
    Vertical on Hcol, every column:      HL = even rows of Hcol; HH = odd rows of Hcol − Pcol(even rows of Hcol)

Inverse (decoder), level ℓ, given LL (final and legal), LH, HL, HH:

    Stage 1 — rebuild Lcol from LL and LH (all outputs are pixels of the half-width image, interval [lo, hi]):
        even rows of Lcol = LL                                       (already legal)
        odd rows  of Lcol = LH_rec + Pcol(even rows), with LH_rec = clamp(LH_val, lo − Pcol, hi − Pcol)

    Stage 2 — compute the per-sample legal interval for every H sample from the now-final Lcol:
        pr[r][i]   = Prow(Lcol row r)[i]
        Hmin[r][i] = lo − pr[r][i]
        Hmax[r][i] = hi − pr[r][i]

    Stage 3 — rebuild Hcol from HL and HH inside those intervals:
        even rows of Hcol = HL_rec,  HL_rec = clamp(HL_val, Hmin, Hmax)
        odd rows  of Hcol = HH_rec + Pcol(even rows of Hcol),
                            HH_rec = clamp(HH_val, Hmin − Pcol(even rows of Hcol), Hmax − Pcol(even rows of Hcol))

    Stage 4 — final pixels:
        even columns = Lcol
        odd  columns = Hcol + pr                                     (legal by construction)

Every clamp reads only values that are final at that point; there is no cycle at any stage.

## A.5 Multi-level recursion

Levels are inverted coarsest first. The LL band of the coarsest level is quantised directly and reconstructed as `clamp(LL_val, lo, hi)`. The output of level ℓ+1's inverse is the LL of level ℓ, so every level's stage-1 interval is [lo, hi]. Within a 16-row slice the vertical recursion is 16 → 8 → 4 → 2 rows; the horizontal recursion is unconstrained.

## A.6 Quantiser and reconstruction

Dead-zone scalar quantiser with power-of-two step Δ, dead zone z (today 9/16 on the finer bands), per band:

    Q(c) = 0                                   if |c| < z·Δ
    Q(c) = sign(c) · (floor((|c| − z·Δ) / Δ) + 1)   otherwise

Reconstruction, nonzero indices:

    R(q, Δ) = sign(q) · ((|q| + β)·Δ),   β = m / 2ᵏ, m odd, per band; R(0) = 0

Signature (Δ recovery from any nonzero non-clamped coefficient c):

    Δ = 1 << ctz(|c| << k)

with `ctz` = count trailing zeros. For Δ < 2ᵏ use a per-band lookup table of reconstruction points whose sets are pairwise disjoint across Δ; the recovery is then a low-bit table lookup.

## A.7 Closed-loop quantisation at the first encoder (per coefficient)

Given the source coefficient c (residual in inter mode), the interval [Hmin, Hmax] from the already-final predictors, and the temporal prediction `pred` (0 in intra mode):

    q   = Q(c)
    r   = clamp(R(q, Δ) + pred, Hmin, Hmax) − pred
    q*  = Q(r)
    r*  = clamp(R(q*, Δ) + pred, Hmin, Hmax)          (this is the value written into the reconstruction)
    emit q*

Proof that the next encoder returns q*: it computes the coefficient value r* − pred. If R(q*)+pred lay inside the interval, r* − pred = R(q*), and Q(R(q*)) = q* because R places every reconstruction point inside its own cell. Otherwise r* is the boundary b on the same side as R(q), and r − pred = b − pred, so q* = Q(b − pred) by definition; the next encoder quantises b − pred and returns q*.

## A.8 Canonical inference at any encoder (per band)

    for each coefficient c in the band, in coding order:
        pred_intra = 0; pred_inter = forward transform of motion-compensated previous decoded frame
        if c == Hmin or c == Hmax:  mark clamped; skip signature
        else if c − pred_intra ≠ 0: sig_intra = ctz((|c − pred_intra|) << k)
        else if c − pred_inter ≠ 0: sig_inter = ctz((|c − pred_inter|) << k)
    intra consistent  ⇔ all sig_intra equal (or none)
    inter consistent  ⇔ all sig_inter equal (or none)
    mode = fixed order over {intra, inter} restricted to consistent modes
    Δ    = 1 << sig  if any signature observed, else tie-break Δ (coarsest allowed by the plan syntax)
    indices = Q(c − pred_mode) for every coefficient        (guaranteed to reproduce the picture)

If any band of the slice is inconsistent, the slice is treated as fresh source and encoded by A.7 after an open-loop plan choice.

## A.9 Order of operations, first encoder, per slice

    1. Forward transform of the source (A.2, A.4).
    2. Open-loop plan choice: quantise source coefficients with candidate plans, estimate bits from the static tANS tables, pick the cheapest plan that fits — as today.
    3. Closed-loop pass, coarsest level to finest; within a level: LL/LH first (Lcol final), then HL/HH:
         for each band: A.7 for every coefficient; then run A.8 on the band's own reconstruction;
         if Δ or mode would be inferred differently from what was used, adopt the inferred/tie-break value
         and redo A.7 for that band once before proceeding.
    4. Pack. If over budget: step Q one notch coarser, repeat step 3 once, pack.

## A.10 Order of operations, decoder, per slice

    1. tANS decode, dequantise (R), add temporal prediction where the band is inter.
    2. Inverse levels coarsest to finest, stages 1–4 of A.4 with the clamps in place.
    3. Display-side slice-boundary blend (unchanged).

No pixel-domain clip remains anywhere in the chain.
