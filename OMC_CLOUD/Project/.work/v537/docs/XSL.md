# Cross-slice boundary handling (XSL)

> **STATUS in v5.0: superseded in part.** The cross-slice edit is now **always on and not switchable**, and is exactly reversible; `docs/TEMPORAL_T5.md` is normative for it. This document's account of XSL levels and of the `--xsl` option describes v4.14.


Status as of 2026-08-12. Levels 0–6 ship; level 7 is experimental and reachable
only from the environment.

## Why it exists

OMC codes the picture in independent slices of `slice_h` luma lines. Rows 0 and
15 of every slice sit at the edge of the wavelet's support, where the basis
functions concentrate quantisation error — measured at 30–60% excess noise
energy on those rows (band-fix §22). The eye integrates the resulting full-width
disturbance into a visible horizontal line at every slice join. The incumbent
has no internal edges and no such line, so this is a difference the eye can find
in an A/B.

Two things address it, both in-loop so encoder and decoder stay in step:

1. **The cross-slice wavelet term.** The previous slice's final rows supply the
   boundary term `d[-1]` to this slice's inverse transform, so the reconstruction
   is continuous across the join rather than reflected at it.
2. **The boundary edit.** A bounded blend applied to the reconstruction after
   the inverse transform, pulling rows 0 and 15 toward their neighbours.

## Levels

| level | behaviour |
|---|---|
| 0 | off: no wavelet term, no edit |
| 2 | wavelet term + forward blend on row 0 |
| 3 | + deferred edit of the previous slice's row 15 (**the shipped default**) |
| 4–5 | blend strength scales continuously with slice emptiness |
| 6 | + seam-strength measurement: full strength only where a step is actually present |
| 7 | **experimental**: the edit rewritten as an exactly reversible lifting cascade |

A minor-9 stream decodes at level 3 on its own say-so. `OMC_XSL` in the
environment overrides that — the deliberate instrumentation path (C1) and the
only way to reach level 7. Gate `G-XSL1` in `tests/test_xsl.c` pins the other
half: with the environment silent, the stream decides.

## The blend cap

Normative, minor 9: **8 codes at 10-bit below 0.75 bpp, 4 codes at or above it**,
scaled by `(maxv + 1) >> 10` for other depths. The threshold counts **coded
samples**, so at 4:4:4 it lands at 1.125 bpp. Chosen by eye in a three-arm blind
comparison (caps 4/8/16).

The cap lives in `ctx_common_t`, **per context, never process-wide** — a
multi-channel server runs several encoders at different rates in one process and
a process-wide cap would let the last one created decide the blend for all of
them. Gate: `tests/test_cap.c`.

## Refresh barriers (A5)

A slice being intra-refreshed this frame takes no cross-slice terms, and a slice
whose predecessor was refreshed this frame does not retro-edit its last row.
Both are derived from the slice header (`fidx8`) and config alone, so encoder and
decoder agree without signalling. Without them, loss-induced drift decayed but
never cleared and crept one slice per refresh cycle.

Anything that inverts the edit **must repeat these rules**, or it will undo an
edit that never happened. `omc_xsl_unblend()` does.

## What the edit costs: generation loss

The level-3 edit moves each row **toward a target computed from that row's own
value**. That discards what the row was, so it cannot be undone. A later encoder
therefore cannot recover the reconstruction its predecessor coded, cannot lock
onto it, and smooths an already smoothed picture.

Six generations, 1920×1080 4:2:2 10-bit, PSNR-Y:

| content / rate | no edit at all | level 3 (shipped) |
|---|---|---|
| beach, 3.0 bpp, sh 8 | −0.30 dB | **−8.17 dB** |
| beach, 1.0 bpp, sh 16 | −0.37 dB | **−1.26 dB** |
| beach, 0.5 bpp, sh 16 | −0.64 dB | −0.93 dB |
| city, 0.5 bpp, sh 16 | −0.61 dB | −0.48 dB |

The generation lock fires 73/270 slices with the edit off at 3.0 bpp and
**0/270** with it on. Seam repair and generation locking are mutually exclusive
per slice under level 3.

## The seam is rate-dependent; the lock is too, in the opposite direction

Un-repaired seam step across a join, as a multiple of the step inside the slice
(1.000 = the join is no worse than the picture around it):

| clip | 0.5 bpp | 1.0 bpp | 2.0 bpp | 3.0 bpp |
|---|---|---|---|---|
| city | 1.824 | 1.269 | 1.067 | 1.013 |
| beach | 1.705 | 1.294 | 1.048 | 1.021 |

The ridge is real at low rate and gone by 2 bpp. Above ~1.5 bpp both level 3 and
level 7 **overshoot**, leaving joins smoother than the picture around them (city
at 3.0 bpp: level 3 −1.707, level 7 −3.119 codes). Meanwhile the lock fires more
as rate rises. See `OPEN_DECISIONS.md` entry `XSL-RATE-OFF`.

## Level 7: the reversible edit

A lifting step is invertible when its correction depends only on values it does
not touch. Two of them in a fixed order edit both rows and stay invertible:

```
forward   step 1   row15 += clamp((row0   - row14) / 4, ±lim)   /* row15 unread */
          step 2   row0  += clamp((row15' - row1 ) / 4, ±lim)   /* row0  unread */

inverse            row0  -= clamp((row15' - row1 ) / 4, ±lim)
                   row15 -= clamp((row0   - row14) / 4, ±lim)
```

Step 2 reads `row15'` — the value step 1 left — and the inverse reads the same
value, so the two agree. Rows 14 and 1 are never touched by either.

`omc_xsl_unblend(frame, cfg, frame_idx)` applies the inverse to a whole picture.
An encoder calls it on its input when that input is a previous decode. Proven
exact: gate `G-XSL2`.

**Results.** Six generations, beach:

| arm | 3.0 bpp / sh 8 | 1.0 bpp / sh 16 |
|---|---|---|
| no edit (ceiling) | −0.30 dB | −0.37 dB |
| level 3 (shipped) | −8.17 dB | −1.26 dB |
| level 7 + un-blend | **−1.81 dB** | **−0.45 dB** |

Seam repair at 0.5 bpp / sh 16 (step excess, codes): level 3 gives city +6.831,
beach +2.489, heli +1.029; level 7 gives +6.978, +2.903, +1.193 — within a few
percent, and better than level 3 at 1.0 bpp.

**Two limits, both open.**

1. **It needs to know when to un-blend.** An encoder that always un-blends also
   un-blends first-generation material, where there was nothing to undo; the
   decoder then re-applies the edit and the two cancel. About a third of the
   seam repair is lost (beach 0.5 bpp: +2.903 becomes +4.873). The results above
   use an oracle. A detector is wrong in both directions: say "decode" on a
   master and lose the repair, say "master" on a decode and take the full slide.
2. **Exactness is verified intra-only.** The edit is in-loop, so two decodes of
   the same stream diverge from frame 1 onward through prediction. Verifying an
   inter frame needs that decode's own pre-edit reconstruction, which the decoder
   does not expose.

See `HANDOFF_BIT_EXACTNESS.md`.

## Instrumentation

| variable | effect |
|---|---|
| `OMC_XSL=n` | force level n (overrides the stream) |
| `OMC_XSL_NOEDIT=1` | level 7 only: keep everything, skip the boundary edit — the ground truth for exactness testing |
| `OMC_XSL_UNBLEND=1` | `omc_enc`: un-blend the input frame before coding |
| `OMC_DEBUG_L7=1` | trace level-7 firing per plane and slice |
| `OMC_DEBUG_LOCK=1` | per-slice generation-lock trace |

**Decoding at level 0 is not a substitute for `OMC_XSL_NOEDIT`.** Level 0 also
drops the cross-slice wavelet term and changes the whole slice; using it as
ground truth produced a spurious "6.1% of samples wrong".
