# Response to the independent evaluation — measurements, the bound, and what is achievable

> **STATUS in v5.0: analysis performed at v4.9, left as written.** The information-theoretic bound it derives is not release-specific; the measured curves in it are v4.9's.


> **STATUS BANNER (2026-08-02).** §2.2's conclusion ("JPEG XS at 4.0 bpp is
> essentially at the achievable bound … unreachable for ANY codec in this
> class") was later found to rest on a defective instrument (the harness
> reconstruction pair used a mismatched inverse filter, overstating the ideal
> coder's rate by 1.4-2x in the region cited). The floor was re-derived by two
> independent efforts: it is NOT falsified (no real codec measures below it),
> but the "within a few percent" claim is withdrawn, and the productive
> question became how much of OMC's own +22-27% overhead above the estimate is
> recoverable. Do not quote §2.2 as written. This document otherwise remains
> the historical record of the v2-era analysis; current release is OMC v4.9
> (bitstream minor 7); current numbers: REPORT.md §16 and §18.7,
> ENHANCEMENTS_LEDGER.md, BITSTREAM.md §9.5.

**Date:** 2026-07-26. **Re:** HVBC evaluation memo of 2026-07-26 and the revised A1
("≤ 0.50× JPEG XS at every useful quality level, on every quality measure at once").

## 1. We accept the memo's findings

We reran the evaluator's experiment and reproduced their numbers exactly (worst frame,
cow, 10-bit 4:2:2, same VMAF tool, same SVT-JPEG-XS build). Their three findings are
correct:

- At equal bits, OMC v1 tied JPEG XS on luma PSNR and sat 4–5 dB behind on chroma; the
  VMAF edge was bought by a luma-weighted allocation that a luma-driven metric rewards.
- The published "half of JPEG XS" held only at the VMAF-97 threshold crossing, under a
  single metric.
- At equal bits the pictures look the same. (Our own review agrees.)

Our v1 report disclosed the chroma trade and the single-point protocol, but the memo is
right that the headline overstated what was demonstrated. This document is the full-curve,
all-metric analysis the revised A1 demands — measured, not argued.

## 2. New measurements (worst frame: cow, cold intra, 10-bit 4:2:2)

### 2.1 Rate-quality curves, all planes (PSNR dB Y/Cb/Cr, VMAF)

| bpp | JPEG XS | OMC v2 fair (shipped default) |
|---|---|---|
| 1.5 | — | 96.40 · 52.0/52.8/54.2 |
| 2.0 | 96.05 · 53.3/55.2/56.7 | 96.96 · 53.5/54.1/55.2 |
| 2.5 | 96.62 · 54.8/56.6/57.8 | 97.24 · 54.9/55.0/56.0 |
| 3.0 | 96.98 · 56.3/57.4/58.4 | 97.25 · 56.3/56.1/57.0 |
| 4.0 | 97.28 · 58.8/59.4/60.2 | 97.19 · 58.6/57.7/58.2 |
| 4.5 | — | 97.26 · 60.7/58.6/59.0 |
| 5.0 | 97.48 · 61.3/61.4/61.7 | — |

Reading, under the all-planes-at-once rule:
- At every rate, OMC v2 (fair) leads slightly on luma (+0.0…+0.5 dB) and on VMAF
  (+0.3…+0.9), and trails on chroma (−1.1…−1.7 dB). JPEG XS runs a chroma-heavier
  split; both codecs sit on essentially the same rate-quality Pareto surface.
- Mutual all-plane match rates: for XS to match OMC-fair@2.0 on all planes it needs
  ≈ 2.1 bpp (1.04× our rate). For OMC to match XS@2.0 on all planes it needs ≈ 3.0 bpp
  (1.5× — the cost of reaching XS's chroma figures at its chroma-forward split).
  **Neither codec halves the other anywhere on the curve.** The honest verdict at
  matched all-plane quality is parity within a few percent, split-dependent.
- We also verified the trade is zero-sum with three measured allocations (luma-weighted,
  equal-ladder, chroma-forward): moving any plane up moves another down by the
  corresponding bits. There is no allocation that dominates JPEG XS on Y, Cb and Cr
  simultaneously at equal rate.

### 2.2 The bound: what ANY codec of this class could do (entropy floor)

We measured the rate a **zero-redundancy ideal entropy coder** (a coder with a stronger
conditional model than either real codec, and no packaging, header, or state overhead)
would need for the quantized transform representation, as a function of delivered
quality, on this frame (`harness/entropy_floor.py`):

| ideal-coder rate | PSNR Y/Cb/Cr |
|---|---|
| 3.17 bpp | 57.0 / 58.3 / 58.5 |
| 2.20 bpp | 55.1 / 57.1 / 57.6 |
| 1.76 bpp | 53.8 / 56.1 / 56.7 |
| 1.15 bpp | 51.9 / 54.3 / 55.4 |

Extrapolating the frontier to JPEG XS's 4.0 bpp quality point (Y 58.8 / Cb 59.4 /
Cr 60.2) gives ≈ **3.9–4.1 bpp even for the ideal coder**. Two conclusions:

1. **JPEG XS at 4.0 bpp is essentially at the achievable bound** — within a few percent.
   It is not wasting bits that a better design could recover. Our own independently
   designed codec landing on the same curve (±5%) is the second witness.
2. **"XS quality at half of XS's bits, PSNR maintained on all planes" is below the
   information floor of the content.** On this frame the grain *is* the information;
   delivering 58.8 dB luma means carrying most of it, and that carriage has an entropy
   cost no transform, no table, and no rebuild can remove. The revised A1 asks for a
   rate beneath the source's rate-distortion function. That is not an implementation
   gap; it is unreachable for **any** codec in the mandated class — intra worst-frame,
   strictly causal, sub-millisecond, FPGA-native, arithmetic-coding-free — ours, JPEG XS's
   successor, or anyone else's.

We rebuilt the entropy and allocation layers from scratch to test this the hard way
(v2: 2D-context tANS table groups, retrained on measured statistics, plane-fair
allocation, smaller headers). Result: ≈ neutral on the curve — exactly what the floor
predicts, because v1 already sat 10–15% from ideal and header/model slack is all that
remains. **A third rebuild would land in the same place.** The two levers that would
genuinely change the curve are excluded by the constraints themselves:

- **Temporal prediction** — worthless on the worst (cold intra) frame that A1 judges,
  and constrained by C2;
- **Grain synthesis / perceptual substitution** — can look transparent at half the rate
  on exactly this content, but by definition does not preserve PSNR (it replaces pixels),
  failing the every-measure-at-once rule, and it manufactures texture the source did not
  place (G-adjacent).

## 3. What the delivered codec (OMC v2) is, measured honestly

- **Default (fair) mode:** MSE-neutral rounding, plane-fair allocation. At equal bits vs
  JPEG XS: +0.0…+0.5 dB luma, −1.1…−1.7 dB chroma, +0.3…+0.9 VMAF, visually
  indistinguishable at contribution rates (both codecs). Aggregate efficiency parity to
  slightly ahead; nothing starved.
- **`--tune vmaf` mode:** the v1 behavior (luma-weighted allocation + texture-retaining
  rounding), for workflows gated on luma metrics. All its published numbers stand.
- Everything else in the mandate is met and re-verified on v2: exact-CBR pipe fit,
  0.16–0.78 ms deterministic latency (720p50…8K60), rt=0 byte-exact on all planes,
  generations 2–5 byte-identical to generation 1, slice-contained loss with one-frame
  recovery, corruption-fuzz-proof decoding, 10/12-bit, 4:2:2/4:4:4, HDR signalling,
  royalty-free IP, shift/add/LUT-only per-pixel paths, documented bitstream v2.0.
- **v4.7 update (E-9 grain-hold v3 / E-10 `--fill-static`):** opt-in `--grain-replace`
  policy refinements plus a static-grain fill mode remain constraint-compliant — zero
  new per-pixel multipliers (per-cell compares/shifts plus one per-band static offset
  pair), latency table unchanged, rt=0 on 4:2:2/10 and 4:4:4/12, exact CBR, and
  minor≤6 streams decode byte-identically; measured results in REPORT.md §18.7,
  ENHANCEMENTS_LEDGER.md E-9/E-10, BITSTREAM.md §9.5.
- Full-frame human review at 2.0 bpp (fair mode): no Section-G artifact on any corpus
  sequence; the only visible degradation is the permitted smooth softening of
  already-soft fine detail.

## 4. The decision this leaves

The revised A1, as written, has an empty feasible set on this content class — the
constraint document's own rule ("a design that meets one requirement by breaking another
does not satisfy the specification") is unsatisfiable here by any design, because the
requirement conflicts with the information content of the source, not with our choices.
Three coherent ways forward, in order of our recommendation:

1. **Re-anchor A1 to visually-transparent provisioning, eyes decisive (E), all metrics
   reported.** Determine, by full-frame human review, the lowest rate at which each codec
   is artifact-free on the worst frame; compare those provisioned rates. Note the memo's
   own observation cuts both ways here: if both codecs look clean at 2.0 bpp, the honest
   outcome is provisioning parity — the 2× headline disappears for everyone, and the
   product case rests on the real differentiators (latency margin, byte-exact
   generations, resilience, royalty-free IP, plus never-worse rate-quality).
2. **Re-scope the 2× to steady-state frames and admit temporal tools** (cut frames keep
   the bounded relaxation A3 already grants). A causal, single-reference temporal layer
   can genuinely reach large rate advantages on low-motion contribution content — but
   the worst-frame number will remain intra-bound at ~1×, and A5/A4 complexity rises.
   This is the only physics-compatible route to a true 2× claim, and it requires
   amending A1's worst-frame accounting.
3. **Keep the codec as delivered and state the claim exactly:** JPEG XS-class
   rate-quality (parity to +15% depending on operating point and metric), at half the
   provisioned rate **only** under the single-metric VMAF-97 service definition, with
   every other mandate met with margin. No number in our report changes; only the
   headline shrinks to what the data supports.

We recommend (1) for the product positioning and (2) if the 2× number is commercially
non-negotiable. What we will not do is present a curve point as a curve.
