# NEST v2: legal and generation-exact in ONE pass, with no closure

**SA14, 2026-09-27, round 2.** This answers the coordinator's review of DESIGN.md (v1). DESIGN.md
stays as the record; this file supersedes it wherever they differ. Everything is a numpy integer
model in `notes/`; logs are in `out/` and renders in `renders/`. Nothing is built in any codec tree.

## 0. What changed, in one paragraph

- **The closure is gone.** v1's rail closure (synthesise, adjust, repeat) is replaced by
  **injective dequantisation (IDQ)**. Every index the decoder can receive maps to a legal value,
  one to one:
  - an index whose lattice point pred + q·Δ lies inside the sample's window decodes to that point;
  - an index beyond the window decodes to one of the window's **off-lattice** values (integers
    that are not lattice points). They are ranked from the top bound for overshoots above and from
    the bottom bound for overshoots below, with the unused values split half and half.
- There is nothing to repair and no constraint for the encoder to satisfy. Any index set is legal
  and exact, so encoding is one pass: analysis → quantisation → the one synthesis the encoder
  needs anyway for its reference.
- **Exactness** now comes from exact index recovery under canonical parameters: the next encoder
  inverts IDQ sample by sample, with the same predictions taken from final samples. Reading
  coarser lattices ("nesting") is no longer needed. The plan comes from a causal (canonical) rate
  controller. As a result reconstruction offsets (today's texture bias) are allowed again.
- **Rail symbols stay, as an encoder option.** A sample exactly on its window bound is a RAIL
  symbol (update value 0); every other sample uses IDQ inside the open interior. The next encoder
  therefore reads "on the bound ⇒ rail" without ambiguity, and the encoder may choose rail or
  lattice per sample.
- **Intra or inter mode is read** as the cheapest exact reading.
- **A temporal model** (inter per band, vectors from decoded frames, rolling refresh, exact hold)
  is built and measured against today's real decodes.

## 1. Review item 1: the closure, now one pass by construction

**Decoder, per predicted sample.**
- Inputs: the raw prediction `raw` (from final samples plus the band prediction; not clamped),
  the sample's window [lo, hi] (from the update values, as in v1), the step Δ = 2^s (s ≥ 1), and
  the index q (or RAIL±).
- Top lattice index: `qhi = ⌊(hi−1 − raw)/Δ⌋`. Bottom lattice index: `qlo = −⌊(raw − lo−1)/Δ⌋`.
  Lattice indices in [qlo, qhi] decode to raw + qΔ.
- Pool: the off-lattice values in [lo+1, hi−1]. It holds at least (M−1)(Δ−1)/Δ values for a
  window of width M. Split it: T = ⌊pool/2⌋ for the top side, pool − T for the bottom.
- An index qhi + k (1 ≤ k ≤ T) decodes to the k-th off-lattice value counted down from hi−1. The
  closed form is two cases:
  - within the t₀ values above the top lattice point: hi−1−(k−1);
  - otherwise: Lt − gΔ − 1 − r, where g, r are the quotient and remainder of k − t₀ − 1 by Δ−1.
- The bottom side is symmetric.
- RAIL+ decodes to hi, RAIL− to lo.
- **Update values are functions of symbols only:** band prediction + q·Δ for lattice and beyond
  indices, 0 for rails. So the synthesis stays acyclic (v1 Lemma 1 unchanged) and legal (Lemma 2
  unchanged: every predicted sample is decoded into its window, and even samples are legal through
  the low-band windows).
- **Hardware cost:** a compare pair, one subtract, and the closed form. The closed form runs only
  for beyond indices, which occur only near rails, and uses a multiply-free reciprocal of Δ−1 per
  shift s (a small constant table).

**Next encoder.** It computes raw from the final samples, exactly as the decoder did:
- value on the bound ⇒ RAIL;
- value on the lattice ⇒ q = (v − raw)/Δ;
- otherwise rank from the top: if the rank is ≤ T it is qhi + k, else qlo − (bottom rank).

This reproduces every index. Rails and lattice samples are unambiguous because non-rail samples
never decode onto the bound.

**Capacity (injectivity) bound.**
- An index overshoots by more than T steps only if its virtual value (raw + qΔ) is more than about
  M(Δ−1)/2 ≥ M/2 codes outside the window.
- IDQ only moves values toward the window, so the virtual error is bounded by the linear L∞ bound
  E = Σ_b (Δ_b/2)·‖ψ_b‖₁.
- **Plans with E ≤ M/2 are therefore guaranteed**: a per-plan table, checked once.
- Measured: 0 saturations in every run (intra, 13 cell/plane/depth/range combinations × 3 rates;
  temporal, 4 runs × 12 frames).

**Cost of the step ≥ 2 rule**, which IDQ needs because Δ = 1 has no off-lattice values:
- +0.2…+1.0 % BD-rate, all at the highest rates;
- rail picture +0.18 % (out/minshift.txt).

**Measured, intra, full frames, all planes** (out/v3_intra.txt, out/v3_ctx.txt, out/v2_vs_clip.txt):

| Cell | Legal | Generation 2 | Quality vs the same indices with a plain clip | Bits |
|---|---|---|---|---|
| dng 1080p, spot, cf_gfx (Y, Cb, Cr) | 0 out of range | indices identical, 0 samples moved | PSNR identical to ±0.01 dB | identical; spot +0.1…0.9 % from rail symbols (context estimate) |
| Synthetic rails, 8/10/12-bit, full and limited range | 0 out of range | identical | +4…+9 dB versus the same codec without rails | −38…−65 % (context with rail sign) |

## 2. Review item 2: the first-row excess (explained; not removed for free)

**Explanation.** The first predicted row of a causal slice cannot update the row above, which is
final. So the synthesis gain of its detail is 7/8 instead of the interior 3/4: its quantisation
error lands more on rows 0–1 and less on the row above. It is a redistribution. Over the three
boundary rows the total error changes by +1.7 %.

**Measured** (causal slice, bottom update zero; mean |error| by row of slice versus the continuous
transform at the same absolute rows; out/seam_test_bot0.txt, out/seam_chroma.txt):

| Plane | dng @ D0 = 48, rows 0–1 | Last row | dng @ D0 = 128 | spot |
|---|---|---|---|---|
| Y | +6 % | −8 % | +3…+5 % | none |
| Cb | +6…+7 % (11.80 / 11.90 vs 11.11 / 11.15) | | +4…+7 % | none |
| Cr | +5…+7 % (11.08 / 11.31 vs 10.46 / 10.65) | | +4…+5 % | none |

This is not below the continuous transform's own 4-row pattern on dng at D0 = 48.

**Lever measured.**
- Step Δ/2 on the finest horizontal subband of the first detail row, at vertical levels 1 and 2
  (a fixed, normative per-row step): rows 0–1 come to −7 % at D0 = 48 and ±0 at D0 = 128, but
  cost **+4…+5 % bits**.
- Encoder-side dead-zone changes do not remove it.

**Status: open.** Either pay about 4 % bits, or accept a +3…+7 % row-0–1 excess that must pass the
owner's eye on level maps.

## 3. Review item 3: temporal model

**What the model does** (`notes/temporal3.py`):
- whole-frame transform, not slices (§6);
- inter per band in the coefficient domain;
- band prediction = the previous frame's leaves where the block vector is zero (the decoder
  recomputes or keeps them; exact hold), otherwise the plain analysis of the motion-compensated
  prediction;
- vectors: 16×16 blocks, derived by the encoder from decoded frames only (match y(t−1) → y(t−2),
  applied forward; ±8 horizontal, ±4 vertical, integer), then transmitted;
- mode per band per 16-row stripe chosen by cost; refresh = one eighth of the rows intra per
  frame, cycled.

**Measured:**

| Check | Result |
|---|---|
| Still input: dng720 frame 0 repeated 10× (out/t3_still_dng720.txt) | **0 changed samples in every plane from frame 1**; generation 2 identical; 0 out of range. Today changes 60–77 % per frame (S5.335). Refresh re-describes the frozen intra lattice exactly, so there is no pop. |
| Generation 2 on moving content: dng720 (12 frames, 4 rates) and spotrobotL (12 frames, 3 rates) | Indices identical on **every frame**; 0 out of range. |
| Mode readability: flip each band-stripe's mode and recover (out/mode_readability.txt) | The wrong mode is always more expensive: 0 of 93–99 stripes per frame. So "cheapest exact reading" recovers the mode. |

**Smudges** (smudgegroups, owner threshold 6 / density 0.4, dng720 frames 8–11, Y / Cb / Cr;
out/smudge6_dng720.txt, out/smudge_plan_tilt.txt):

| Arm | Y groups | Chroma groups |
|---|---|---|
| Today @ 0.5 | 0–5 (0–91 blocks) | 0 |
| NEST untilted, 0.39 bpp | 33–42 | 3–10 |
| NEST untilted, 0.66 bpp | 3–6 | 0–2 |
| NEST with plan tilt (low bands one to three octaves finer), 0.52 bpp | 4–6 (78–102 blocks) | 0–1 |

Smudges here are a plan property (coarse low bands), not structural. There are no slices in this
model, so these groups are not slice-grid ones.

**Owner boxes** (am720, frame 2; out/ownerboxes.txt):

| Arm | Grille luma \|err\| | Grille HP correlation | Rest luma \|err\| |
|---|---|---|---|
| Today @ 0.5 | 34.6 | 0.66 | 12.1 |
| NEST @ 0.39 | 23.5 | 0.88 | 12.1 |
| NEST @ 0.66 | 17.2 | 0.92 | 10.4 |

Chroma |err| is within ±1 across arms.

## 4. Review item 4: against today's real decodes

Setup:
- Today: SA7 DM `*_a0.d.yuv` at exact CBR.
- Steady-state frames 2–11.
- NEST coded rate = zeroth-order entropy × tANS overhead (1.15 at ≤ 0.5 bpp, 1.06 at ≥ 0.8,
  linear between); vector bits included; no rate control (fixed plan per run), averaged over the
  12 frames like today's CBR.

Measured (out/cmp_dng720_tilt.txt, out/cmp_spot.txt):

| Cell | Arm | bpp | VMAF-NEG | PSNR mean Y / Cb / Cr | PSNR worst Y |
|---|---|---|---|---|---|
| dng720 | today | 0.50 | 90.16 | 35.22 / 36.10 / 37.14 | 34.69 |
| dng720 | NEST, tilt | 0.52 | **90.89** | 35.63 / 36.05 / 37.25 | 35.62 |
| dng720 | today | 1.00 | 94.05 | 38.19 / 37.08 / 37.95 | 37.88 |
| dng720 | NEST, tilt | 0.97 | **94.24** | 38.33 / 37.27 / 38.22 | 38.27 |
| spotrobotL | today | 0.50 | 93.76 | 39.54 / 42.80 / 46.31 | 36.51 |
| spotrobotL | NEST, untilted | 0.53 | **94.72** | 41.53 / 42.76 / 45.81 | 41.10 |

- By interpolation, NEST matches today's VMAF-NEG on spot at about 0.49 bpp.
- **Parity or slightly better at matched estimated rate, every plane within ±0.5 dB, and a much
  better worst frame.**
- Without the plan tilt, dng720 was +48 % bits at matched VMAF-NEG (out/cmp_dng720_modes.txt).
  The plan matters more than the structure.

## 5. Review item 5: rail graphics

The model has no cut24 generator, so a rail-graded dng720 frame (luma stretched 2.5× into both
rails, chroma 2×) stands in, with cf_gfx. Intra, full frames (out/rails_render.txt).

| Case | VMAF-NEG NEST / clip-codec | Y PSNR NEST / clip | Bits (context) | Samples differing from the clip codec |
|---|---|---|---|---|
| Rail-graded, D0 = 48 | 94.81 / 93.29 | 39.91 / 39.28 | −2.3 % | 304,607 toward the source, 106,960 away |
| Rail-graded, D0 = 128 | 91.41 / 88.21 | 35.59 / 34.88 | +10.9 % | 301,701 toward the source, 107,701 away |
| cf_gfx (no rails in the source) | 92.271 / 92.272 and 86.241 / 86.245 | identical | identical | 3 and 41 |

- Chroma PSNR is equal in every case.
- Because rails are an encoder choice, the D0 = 128 bit cost can be traded per sample. Not yet done.
- **Not everything moves toward the source.** NEST is a different quantisation from the clip codec
  (the low band sees rails), not a correction of it. The differences are concentrated on rail
  edges and show horizontal streaks from the 1-D levels: see
  `renders/railgraded720_D128_absdiff_nest_vs_clip.png` (×8 gain).
- Renders for the eye, unmarked + `_grid` (32 px): source, NEST, clip codec,
  |NEST − source|, |clip − source|, |NEST − clip|, at D0 = 48 and 128.

## 6. What is still NOT measured together (weakest points)

1. **The shifted causal slice has not been run together with IDQ/rails and the temporal path in
   one model.** The temporal and legality model uses a whole-frame transform. The combination is
   algebraically compatible (causal tops are final values; windows and IDQ are per sample), but
   it is unmeasured.
2. **The first-row excess** (§2) is open: about 4 % bits, or the owner's eye.
3. **Efficiency is estimated**, not coded: entropy × overhead, fixed plan, two cells, 12 frames.
   The plan tilt was tuned on dng720 only. The causal rate controller (canonical plan) is not
   built; its quality cost versus free per-slice plans is unknown.
4. **The IDQ capacity guarantee** relies on a per-plan error-bound admissibility table (E ≤ M/2),
   which is not yet computed.
5. **Rail-graded content** shows NEST-vs-clip differences with a horizontal-streak character.
   It needs the eye.
