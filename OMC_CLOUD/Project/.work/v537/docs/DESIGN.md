# OMC-1 Design — architecture, rationale, and IP provenance

OMC-1 is an intra-only, slice-based mezzanine codec for broadcast contribution: one codec
for every leg of the contribution chain (camera→switcher, switcher→broadcast center),
replacing JPEG XS at half its provisioned bitrate. This document explains *why* the design
is what it is, and records the IP provenance of every technique (C1).

## 1. Architecture in one paragraph

Each frame is cut into independent horizontal slices of 16 (or 8) luma lines. A slice is:
reversible integer wavelet (2 vertical × 5 horizontal levels; 5/3 and (9,7)-M lifting) →
power-of-two shift quantization with derived per-band shifts → context-modelled
magnitude-category symbols → static-table tANS entropy coding → fixed-format slice with
CRC. Rate control holds an exact per-frame CBR budget with causal in-frame banking. There
is no inter-frame prediction, no adaptive entropy state, no decoder-side memory: every
slice decodes from its own bytes alone.

## 1b. Temporal layer (v3, constraints rev. 3)

Rev. 3 of the constraints sanctions temporal prediction with a two-frame
visually-unnoticeable quality ramp (stream start and scene cuts) and steady-state
judgement from frame 2. The v3 layer: per-band choice between intra coding and
**coefficient-domain delta** against the single previous reconstructed frame
(no motion compensation - no search, no per-pixel multipliers; prediction = forward
transform of the co-located rows of the reference). Scene cuts cost nothing to detect:
when the delta is more expensive than intra, rate control codes intra (C7 - decisions
from the video alone). A staggered rolling intra refresh (slice s all-intra when
frame mod R == s mod R, R signalled in the stream header, default 8) bounds loss
recovery to R frames (A5). The quality floor lifts from frame 1 so prediction refines
toward transparency ("perfect" steady state) within the same CBR pipe. The generation
lock (§5) extends to the delta domain: a re-encoded generation reproduces byte-identical
output with prediction active (measured: generations 2-5 identical).

**Motion vectors (v3.1: per-region, half-pel capable).** Each inter slice signals four
motion vectors, one per horizontal quarter of the slice, in half-pel units
(dx in [-8, +7.5], dy in [-4, +3.5]; header bits 4x(5+4)). Half-pel positions
interpolate with (a+b+1)>>1 / (a+b+c+d+2)>>2 - **shifts and adds only, no
multipliers** (C3). The default encoder derives one global integer vector per slice by
a decimated whole-slice SAD over 19 candidates (adds/compares only) and writes it to
all four regions - the v3.0 search whose byte-exact generation replay is measured
(gens 2-5 identical, panning content included).

**Opt-in override search (`--mv-regions`) and its measured trade-off.** With the flag,
the encoder additionally tries global half-pel refinement and per-region
integer/half-pel overrides on a 4x2 block-sum SAD (block means cancel grain), each
accepted only on a >= 2x SAD win. Measured at 2.0 bpp on labeled synthetic tests:
divergent multi-object motion (halves panning opposite directions) **+1.8 dB** worst
steady luma over the global vector; true half-pel pan **+0.7 dB** (+1.2 dB on
fractional-position frames). The honest cost, measured over 4 re-encode generations:
decisions near any fixed acceptance threshold can decide differently on re-encoded
input, and the half-pel tap is a low-pass, so generations **accumulate loss**
(multi-object: 51.5 -> 47.7 dB gen1 -> gen4) instead of replaying byte-exactly. A fixed
threshold cannot be made replay-safe on noise-shallow SAD surfaces - this is
structural, not a tuning gap. The flag is therefore **off by default and off-spec for
multi-hop contribution chains (A4)**; it is fit for single-hop links where no
downstream re-encode exists. The bitstream is identical in capability either way
(harness/motion_tests.py reproduces all numbers).

Measured at 2.0 bpp:
- Corpus steady frames: frames 1+ gain +0.1...+2.1 dB, VMAF 97.5-100; beach steady frame
  beats JPEG XS at equal bits on every measure (+0.8 VMAF, +2.4/+1.8/+1.0 dB).
- Real cut sequence (4 concatenated scenes): each cut frame codes intra at that content's
  own frame-0 quality (no dip below the intra baseline - nothing flashes), steady state
  restored within the 2-frame rev.3 ramp.
- Panning content (1280x720 window sliding 6 px/frame over real frames): on clean content
  the global MV is worth +1.9 dB on every steady frame and holds a +2.1 dB lead over
  JPEG XS at equal bits under continuous motion. On grain-dominated content (fence pan)
  prediction gains ~nothing with or without motion compensation: the frame-to-frame delta
  is fresh grain, priced by the entropy floor of docs/FEASIBILITY.md - true for any codec.
- Worst steady-state frame under the revised A1: on calm/panning clean content the codec
  runs at 0.5x XS rate with equal-or-better VMAF and a luma lead at equal bits; on
  noise-dominated or hard-motion frames it returns toward intra parity with XS - the
  floor, not the design, is the limiter there.

## 2. Why intra-only, slice-based (v1/v2 baseline; v3 adds the layer above)

- **A1 (worst frame decides):** temporal prediction cannot help the worst frame — the
  cold intra frame — so the bitrate bar must be met intra. Once it is, temporal tools add
  only risk (drift, error propagation, generation loss), not compliance.
- **A2 (sub-1 ms):** a 16-line slice is the latency quantum: capture 16 lines, code, ship.
  See docs/LATENCY.md for the deterministic bound (< 1 ms at every format, 720p up).
- **A5 (error resilience):** slice = packet = containment unit. A lost packet damages
  16 lines of one frame; the next frame is clean by construction (1-frame recovery).
- **C2 (causality):** the encoder reads nothing below the current slice (verified by the
  poisoned-rows test); the decoder recalls no stored pictures.
- **A4 (generation robustness):** see §5 — byte-stability across generations is engineered,
  not hoped for.

## 3. Coding tools and their provenance (C1)

| Tool | Provenance | Vintage / IP status |
|---|---|---|
| CDF 5/3 integer lifting wavelet | Le Gall & Tabatabai (1988); integer lifting per ISO/IEC 15444-1:2000 (JPEG 2000 Part 1, royalty-free baseline) | >35 years; royalty-free |
| (9,7)-M reversible integer lifting (h-levels 1–2) | Interpolating (4,2) filter; reversible integer-to-integer wavelets, Adams & Kossentini, IEEE Trans. Image Processing, 2000 | >25 years; expired vintage |
| Asymmetric decomposition (2V × 5H), line-based wavelet coding | JPEG 2000 / ISO 15444 family practice (explicitly allowed: 15444-15/HTJ2K family) | royalty-free |
| Power-of-two scalar quantization, recon = q·2^s | folk/ancient (predates digital video standards) | free |
| Sign-magnitude category + raw LSB coding | JPEG (ITU T.81, 1992) category coding | >30 years; free |
| LL DPCM | DPCM, Cutler patent 1952 (expired 1969) | free |
| tANS entropy coding, static tables | Asymmetric Numeral Systems, J. Duda, arXiv:1311.2540 (2013), released with public-domain intent; table construction reimplemented from the published algorithm | royalty-free; **no rANS anywhere; no CABAC; no adaptive arithmetic coding** |
| tANS table freeze (v3.1) | Normative groups verified before freezing: retrained on a broadened corpus (intra + temporal-delta statistics, program feed, ramps, exact (9,7)-M mirror — harness/train_tables3.py); the retrained set coded the broadened training data 0.05% *worse* than the shipped tables, so the shipped tables are frozen as normative | own work |
| 2-way causal context (left-neighbour significance) | classic static context modelling (pre-1990 lossless coding literature) | free |
| CRC-32 | IEEE 802.3 (1983) | free |
| Rate control (Q + fixed refinement schedule + chunk boundary + causal banking + lattice generation-lock) | own work, this project | owned |
| Perceptual allocation tables, profiles, texture rounding bias | own work, this project | owned |

Explicitly absent: MPEG-LA pool techniques, HEVC/AVC internals, JPEG XS internals (its
GCLI/significance coding, its rate allocation), CABAC, rANS. SVT-JPEG-XS was used only as
an external benchmark instrument, never linked or consulted for design.

## 4. Rate control (exact CBR into a fixed pipe)

- Slice budget B = bits_per_slice; frame = N·B bits exactly (padding closes the frame).
- Per slice: exact per-band, per-shift cost tables (histograms × per-table bit-cost LUTs,
  integer adds), then: smallest master Q ≥ quality floor that fits → greedy refinement
  steps down the fixed schedule → partial-chunk boundary for ~256-bit granularity →
  deterministic overflow backoff (bounded retries) → zero-pad discipline at frame end.
- **Causal banking:** slices cheaper than the perceptual floor (Q=3, all steps) bank their
  surplus; later hard slices draw it, plus a bounded overdraft (≤ B/2, repaid from the
  frame's remaining budget). The prefix invariant (spent(k) ≤ (k+1)B + B/2) is what the
  latency bound uses. Look-back only; the decoder needs no knowledge of it.
- **Profile bit:** per slice, the encoder picks `balanced` or `texture` allocation by a
  deterministic high-band-sparsity statistic (texture = sparse fine grain: finer level-1
  luma bands). Signalled in the header; the decoder derives shifts from tables.
- **Texture rounding bias (encoder-only):** detail bands round at 0.375·2^s instead of
  0.5·2^s, retaining low-amplitude texture the eye values above the MSE optimum.
  Reconstruction points are unchanged, so idempotence is unaffected.

## 5. Generation robustness (A4) — by construction

Pass 1 is the only lossy pass. From pass 2 on, the pipeline is a fixed point:

1. The wavelet is exactly reversible, so re-encoding a reconstruction re-derives exactly
   the dequantized coefficients: every coefficient is a multiple of 2^s of its band shift.
2. Reconstruction points are quantizer fixed points: (q·2^s + bias) >> s = q since
   bias < 2^s.
3. **Lattice generation-lock:** the encoder measures each band's lattice exponent (trailing
   zeros of the OR of magnitudes, per 256-coefficient chunk) and searches the plan space
   for the cheapest (profile, Q, steps, partial) whose every shift is ≤ the data's lattice.
   If found and it fits the budget (the original plan always does — it fit last time), the
   encoder locks to it; quantization is then exactly neutral and the output pixels equal
   the input pixels bit-for-bit. Natural first-generation content never has ≥4 nonempty
   lattice-aligned bands, so the lock never fires on it.
4. Banking induction: locked slices reproduce identical byte counts, so budgets — and
   therefore every later slice's decision — replay identically.

Measured: generations 2–5 byte-identical to generation 1 on all planes (tests/test_acceptance.py::test_generations_byte_stable).

## 6. Error resilience (A5)

- Containment: slice-per-packet; a lost/corrupt slice affects only its 16 (8) rows.
- Detection: sync word + field range checks + CRC-32 + tANS end-state check.
- Resync: scan to next sync word (file mode); packet mode reframes for free.
- Recovery: intra-only ⇒ the next frame is clean; bounded to 1 frame, no propagation.
- Concealment: the decoder leaves the damaged rows' previous content in place
  (hold-last-good), a localized, graceful degradation; disable with --no-conceal.
- Measured: random and burst loss stay row-bounded; 30-case corruption fuzz (bit flips,
  truncation, garbage blocks) never crashes or desyncs beyond the damaged slice.

## 6b. Film-grain-aware mode — considered and NOT enabled (decision record)

The one remaining lever on grain-dominated content (cow, fence) is a grain-aware mode:
estimate the grain's statistics, code the underlying signal, and re-synthesize grain at
the decoder (the AV1-FGS idea; the technique class is royalty-free in its pre-AV1
academic vintage). It is deliberately **not** implemented, let alone enabled:

1. **It conflicts with the governing quality rule.** The mandate permits exactly one
   degradation - smooth softening of already-soft regions. Synthesized grain is not the
   captured signal: it replaces real texture with statistically similar fake texture.
   For a contribution (mezzanine) codec whose output feeds downstream grading and
   compositing, that substitution is an artifact by definition, however good it looks.
2. **It invalidates the fidelity contract.** PSNR against the source collapses on
   synthesized grain (the samples are wrong even when the look is right), so every
   full-reference number in this report would need a waiver ("judge look, not
   fidelity") from the mandate holder before the mode could count toward anything.
3. **Generation robustness breaks.** Re-encoding synthesized grain re-estimates and
   re-synthesizes it; the A4 byte-replay property cannot survive that.

If the mandate holder ever waives PSNR-on-grain for specific single-hop links, the
clean integration point exists (an encoder-side denoise + per-slice grain descriptor in
a reserved header field), but until that explicit waiver is given, the codec softens
grain smoothly - the permitted degradation - and never fakes it.

## 7. Scope and self-reliance (C7, D)

Inputs: planar Y'CbCr samples and the fixed configuration. Outputs: the bitstream.
Nothing else crosses the boundary — no camera metadata, no production state, no side
channels. Audio, timecode, captions, encryption and FEC live in the transport layer;
OMC-1's own resilience (§6) is beneath and independent of any transport FEC.


## 7. v4 — eye-targeted coding: the grain fill (constraints rev. 6)

Rev. 6 replaced PSNR/VMAF with blind human viewing as the measure of "same
quality at half the rate" (OMC @ R vs JPEG XS @ 2R). That change re-aims the
codec at a mismatch MSE optimization cannot see past: on grain-dominated
content the per-pixel-optimal answer is to shrink sub-threshold texture to
zero, which reads as a waxy, de-grained patch — while the eye does not care
which grain speckle landed where, only that grain of the right amplitude,
coarseness and motion is present. Reproducing the exact grain at half the
incumbent's rate is entropy-impossible (FEASIBILITY.md, confirmed by both
teams on real footage); reproducing its character is nearly free.

**Mechanism** (normative in BITSTREAM.md §4.6): zero-coded detail-band
coefficients in bands the encoder flags (18 header bits) reconstruct as
±quarter-step with deterministic tile signs, offset per frame/slice/plane/
band so the restored grain animates at frame rate. Two LL-derived gates keep
it honest: an activity gate (flat regions get nothing) and a clip-headroom
guard. In-loop at both ends: rt = 0 is preserved trivially, and the temporal
reference carries the fill, so prediction sees the same picture the viewer
does.

**What it does not do:** no parametric grain model, no random number
generator at the decoder, no signal invention beyond the coded quarter-step
energy bound — the fill restores measured sub-threshold energy of the actual
source, with a phase the source did not constrain (which is precisely the
degree of freedom the eye ignores). PSNR drops by construction (~0.05-0.8 dB
measured); rev. 6 makes that an accepted cost, not a regression.

**Generations (A4), upgraded from argued to checked.** Fill magnitudes are
tz = s-2 lattice exceptions, so the generation-lock lattice detector accepts
them in fill bands (never in bands 0..3, never tz = s-1). But rather than
trusting that analysis, v4's lock verifies: it collects lattice-consistent
candidate plans and locks only a plan for which `lock_verify` reproduces
every input coefficient bit-exactly - quantization, prediction, and fill
regeneration simulated in full. A slice that fails verification codes
naturally (bounded drift, converging), and measured: all slices lock on
generation 2+, outputs byte-identical through generation 5, grain fill
included.

**Hardware (C3):** per zero coefficient the fill costs two compares (gates),
one table-bit lookup (sign) and one shift (amplitude); the tile is built once
at init by a fixed LCG. No per-pixel multipliers, no adaptive state.

## 8. v4.4 — design rationale (2026-08-02)

Four changes, each carried by a measurement (full ledger with numbers:
ENHANCEMENTS_LEDGER.md; bitstream deltas: BITSTREAM.md §9):

**8.1 Detail-band deadzone (default on).** Wavelet detail coefficients are
Laplacian, not uniform; for such a source the rate-distortion-optimal zero bin
is wider than the others. 9/16 of a step is the mildest setting that measures
(+0.45 dB all planes at 2.0 bpp) and the widest that never buys one plane with
another. Reconstruction points do not move, so the decoder, the idempotence
identity and the lattice generation-lock are all untouched. LL is excluded —
a deadzone on low-frequency bands is precisely the mechanism of gradient
banding (G2).

**8.2 Entropy model v2 (minor 4).** The 4-state binary-significance context
discards most of what the causal neighbourhood knows. The 16-state magnitude
context (q2|left| × q2|above|) was selected by held-out cross-validation on
real dumped symbol streams against six alternatives (finer contexts,
forward-signalled scale, parent-band and prediction-magnitude contexts of our
own design); tables were then Lloyd-trained on the full corpus. Group count is
a BRAM decision, not a quality decision: K=8 is normative (2× the legacy table
memory; +0.08–0.21 dB on never-trained clips); K=16 measured +0.04–0.10 dB
more at 4× BRAM and is documented as an option — C3's "comfortably" is taken
literally. Capacity beyond that is measured-dead: an oracle table set fitted
to the test footage itself beats the trained tables by under 1%.

**8.3 Grain-replace classifier v2 (opt-in).** The one degradation the eye
forgives is losing the *realization* of noise; the one it never forgives is
losing structure. The classifier therefore demands two independent physical
signatures of noise before acting — no coarser-scale support (grain has no
spatial extent) AND no temporal persistence (grain is re-rolled every frame;
detail rides motion compensation) — and is structurally incapable of touching
edges (only |q|=1 values are demotable) or of flattening (demoted energy
reconstructs through the §4.6 fill at measured amplitude). Never conditioned
on luminance. Measured: ~15–17% rate at equal perceptual score on
electronic-noise content, ~4–5% on coarse film grain, zero effect on
grain-free and graphics content, and no degradation on the confetti honeypot
(dense small sharp moving objects). Default off until the rev. 6 blind-viewing
gate rules; the remaining coarse-grain headroom belongs to the v5 parametric
synthesis (matched grain coarseness), not to more aggressive killing.

**8.4 Per-block motion field (minor 3, opt-in).** Built to test — from a second
architecture — whether finer motion converts to quality here. It does not
(−0.15…+0.15 dB), independently confirming the D-1/D-2 record; retained as a
bitstream capability with the honest number attached.

### Provenance additions (C1)

| Tool | Provenance | Status |
|---|---|---|
| Deadzone scalar quantization | pre-digital-video folk practice; JPEG 2000/XS use it | free |
| Magnitude-quantized causal contexts | static context modelling, pre-1990 lossless-coding literature | free |
| Lloyd-clustered static tANS table groups | Lloyd (1957/1982) + Duda ANS (2013, public-domain intent); trainer own work | royalty-free / owned |
| Inter-scale + temporal grain classification | own work, this project | owned |
| Per-block argmin motion field | own work, this project | owned |

## 9. v4.7 — grain-hold v3 and the static fill (2026-08-02)

Two changes (full numbers: docs/REPORT.md §18.7; ledger: ENHANCEMENTS_LEDGER.md
E-9/E-10; stream field: BITSTREAM.md §9.5). Only one touches the bitstream:
`--fill-static` (stream byte 27 bit 2, minor 7) makes the grain-fill sign-tile
offsets frame-independent — a static grain texture with no temporal animation.
Everything else is encoder-only policy inside `--grain-replace`; minor ≤ 6
streams decode byte-identically (verified against a pristine v4.6 build).

**9.1 Three votes plus the carpet (E-9, part of `--grain-replace`).** The v4.4
classifier's two signatures gain a third — an amplitude vote
(|coef| < 3·2^(bitdepth−7)): grain is small, structure is not — and a
per-slice-band grain-carpet vote (≥ 25% small nonzero cells): real grain fills
a band; isolated detail does not. The parent-support threshold rises to 8
(10-bit) and the LL-gradient gate is removed — the carpet vote makes it
redundant. Env knobs OMC_GR / OMC_GR_PTHR / OMC_GR_SOFT / OMC_GR_CARPET /
OMC_GR_LLTHR / OMC_GR_QMAX / OMC_GR_SOFTCAP override every constant; the legacy
v4.6 behaviour is reproducible byte-exactly (OMC_GR_SOFT=0 OMC_GR_PTHR=2
OMC_GR_CARPET=0 OMC_GR_LLTHR=24).

**9.2 Why soft-threshold beats hold.** v4.6 held eligible coefficients at their
reference value; v4.7 instead codes eligible deltas shrunk by 1 step (cap
|q| ≤ 3). A held coefficient can only be right or stale; a shrunk one tracks
the source with a 1-step lag, so drift is bounded by construction and
generations converge rather than freeze (measured 55.8 → 58.7 dB, rising).

**9.3 Why the fill went static.** The animated fill re-injected exactly the
temporal boil the hold suppressed: soft-held coefficients calmed, then the
frame-offset sign tiles re-animated the same cells. With `--fill-static` the
offsets are frame-independent, so held grain sits still — matte flat-region
boil is calmer than with grain-replace off, and moving-edge boil is identical.

**Measured (rev. 6 metric).** Viewer-box ant-tail 18.0% (watched v4.4) → 7.98%,
below fair JPEG XS @ 2 bpp (7.73%); at 1.0 bpp 18.6% → 10.7%. Grain sigma
retained 100% on cow/graincell; beach fine grain 67% plus static fill. Confetti
honeypot VMAF 98.36 → 98.20; aerial/couch unchanged. No flattening: flat-block
rate 0.08%, equal to baseline. rt = 0 preserved at 4:2:2/10 and 4:4:4/12; exact
CBR held.

**Hardware (C3):** zero new per-pixel multipliers; the votes add per-cell
compares and shifts, and the static fill is one per-band offset pair through
the same omc_fill_offsets path with f = 0. The latency table is unchanged.

Historical note kept deliberately: §1b's motion-range text describes v3.1-era
behaviour and earlier documented stale-doc incidents; ENHANCEMENTS_LEDGER.md
is the authority for what v4.7 actually does.


## Entropy-coder IP posture (audited 2026-08-03)

The concern classes raised for commercial ANS deployments, against this
codebase (audited by grep + code review, `src/tans.c`):

1. **Core algorithm**: implemented clean-room from Duda's published
   description (arXiv:1311.2540, provenance header in `src/tans.c`).
   Static tables only; no adaptive probability estimation of any kind.
2. **rANS patents (e.g. US11277156B2)**: not applicable - the codebase
   contains ZERO rANS, by standing constraint C1 (rANS is banned even in
   experimental/disabled form; re-entry requires prior IP counsel).
   Verified by search: no rANS symbol, comment, or code path exists.
3. **Vectorization / interleaved-stream patents**: not applicable - the
   implementation is scalar C with no SIMD intrinsics and a SINGLE tANS
   stream per slice (backward encode, forward decode, one table lookup +
   one bit-read per symbol). Parallel throughput comes from slice
   independence (each slice is a self-contained stream with its own
   CRC), which is the decades-old restart-interval pattern, not
   interleaved ANS states within one stream.
4. **Hardware-acceleration ANS patents**: the FPGA mapping is the plain
   tANS automaton (state register + ROM lookup + shifter). Any future
   RTL implementation must keep to this construction and clear IP
   counsel before productization.
5. **One noted nuance**: the table-construction spread step
   `(L/2 + L/8 + 3)` is the constant familiar from the BSD-licensed FSE
   implementation. It is a one-line arithmetic choice (any odd step
   coprime with L functions), not copied code; flagged for the counsel
   list. Changing it would alter the normative tables (bitstream minor
   bump) - do not change casually.

This section is an engineering audit, not legal advice: formal IP
counsel review remains a prerequisite for commercialization (C1).
