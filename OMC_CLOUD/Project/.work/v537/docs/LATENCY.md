# OMC-1 Latency Model — deterministic, sub-1 ms at every format (A2)

> **STATUS in v5.1: the model is UNCHANGED and was re-measured on this build.**
> `make test` re-runs the whole A2 table and every cell is identical to v5.0's
> (0.13-0.86 ms, 720p50 to 4320p50, including up- and down-conversion). v5.1
> adds no buffering: every change is inside the existing per-slice
> encode-attempt loop. The one number that DOES move is the encoder's
> worst-case repair work. See the v5.1 addendum in `docs/HARDWARE.md` and
> `docs/OMC_V5_1.md` §6.
>
> **CORRECTED AND ENFORCED in v5.3.7.** This paragraph said "3x
> `gamut_strict`" and the v5.0 note below said "(1 + N)". Both were wrong, and
> they disagreed with each other: at the shipped budget of 13 they read 39 and
> 14 passes. The true static bound counts all four paths that hand a slice a
> fresh budget -- the initial budget, the SD-revert restart, the harsh-rule
> fallback restart, and `omc_gm_redomax` redos:
>
> **`(3 + omc_gm_redomax) x gamut_strict` = 52 passes at the shipped defaults.**
>
> From v5.3.7 that is **enforced** by a per-slice total-pass counter that no
> restart, fallback or redo resets, not merely documented: at the cap the slice
> takes the existing exhaustion path (committed, counted, reported, CLI exit 2).
> Measured worst on the corpus at budget 13: **35** passes on one slice
> (spotrobotL 1080p 4:2:2 @0.5, 12 frames), and **45** on the G-T5-CUT24
> rail-cut synthetic (24 frames). At budget 12 the worst is 35, at budget 16 it
> is 39. The distribution is heavily skewed -- on the worst cell p50 = 2,
> p90 = 23, p99 = 29 against a max of 35 -- which is why the worst case, not the
> average, is the number hardware must hold.
>
> **What hardware must provision, stated in the unit that matters.** This
> document is a delay model in lines and slice periods, and it says the repair
> adds no latency *because it assumes the back half finishes inside the slice
> period*. That assumption holds only if the pipeline is provisioned for the
> worst-case passes; if it is not, the pipeline stalls by the shortfall, and a
> stall is latency. So: **provision 52 back-half passes per slice period at the
> shipped budget**, where this document previously implied 39. The per-pass
> cycle cost stays an RTL deliverable per `docs/HW_TIMING_METHOD.md` §3 and is
> deliberately not invented here.
>
> **STATUS in v5.0: the model is UNCHANGED and was re-measured on this build.** `make test` re-runs the whole A2 table and every cell is unchanged; a 1200-row sweep finds zero cells whose latency moves with bitrate. Two v5 notes: `slice_h` 32 remains **over budget and NOT-SHIPPABLE** (the encoder says so itself), and the strict in-gamut repair adds no latency — it adds no vertical reach and no slice period — but it does multiply the *back half* of the encode by up to `(3 + omc_gm_redomax) x gamut_strict` passes on slices it repairs -- **52 at the shipped defaults, enforced from v5.3.7** -- which hardware must budget as worst case. *(This line read "(1 + N)" until 2026-09-08; that omitted three of the four fresh-budget paths.)* See `docs/TEMPORAL_T5.md` 12.22.8.


*(v4.5–v4.7 (rev8, bitstream minor 7): verified unchanged — every addition since v4.4
(correlated/amplitude-matched/STATIC fill tiles, grain-hold v3, plan hysteresis, E-11
perceptual slice-budget allocation) is an encoder-side decision at existing pipeline
points and adds no buffering; E-11 allocation operates strictly inside the existing
§7 banking bounds. The 720p auto slice_h is 8 (E-8). See ENHANCEMENTS_LEDGER
E-9/E-10/E-11, REPORT.md 18.x, and BITSTREAM.md 9.3–9.5.)*

Latency here is **algorithmic codec latency**: capture wait + paced slice transmission +
decode start — the quantity that survives into any competent hardware implementation.
It is **constant by construction**: every component below is fixed by the format
configuration, entirely independent of picture content, so the figure never wanders
frame-to-frame (genlock-safe; lip-sync-safe).

## Model

```
T_total = T_capture + T_transmit + T_pipeline
  T_capture   = slice_h source lines            (the encoder can start when the slice's
                                                 last line arrives; strictly causal)
  T_transmit  = one slice period = frame_time/N (CBR pipe drains one slice per period)
  T_pipeline  = 2 source lines                  (transform/entropy pipeline depth)

  T_overdraft = 0   since 2026-08-12.  It used to be 0.5 slice periods -- a FIFTH of
                the whole budget -- because the encoder was allowed to overdraw the
                prefix by B/2 and exact CBR made later slices repay.  Measured across
                three clips at 0.5 and 1.0 bpp, removing that allowance moves quality
                by under 0.1 dB on every plane, moves VMAF and VMAF-NEG by under a
                twentieth of a point on five of six arms, leaves exact CBR untouched
                and leaves the overflow retry count unchanged -- and it improves the
                tail-debt signature, because the overdraft was the mechanism that made
                the LAST slices of a frame repay what the first ones overspent.
                Tightening is backward-compatible: BITSTREAM sect 5's bound is an
                UPPER bound, decoders keep the wider tolerance, and the per-slice wire
                cap is deliberately unchanged so older streams still decode.
                OMC_OD=<percent of B> restores it for experiments.
```

The decoder begins reconstructing slice k the moment its bytes are in; the prefix bound
caps that moment at (k+1.5) slice periods after the slice's first line was captured at
the far end. No B-frames, no rate-control lookahead: nothing else can add latency.
Temporal prediction (v3) does not change the bound: the reference is the *previous*
frame, fully available before the current slice's first line is even captured, and the
±4-line MV window is prefetched with the co-located rows.

## Per-format worst-case table (generated by harness/latency_model.py)

The per-format table below is regenerated by harness/latency_model.py; the figures
in `docs/BITSTREAM.md` §7, in the A2 guard of `omc_validate_config()` and in gate
G21 of `tests/test_uc.c` all follow the same model and are checked against each
other. With the default slice heights (16 above 720p, 8 at 720p-class) and no
overdraft, the worst supported case is **720p50 at 0.500 ms codec-only and
0.806 ms with the worst conversion in the path**.

All formats < 1 ms: YES

All supported formats — from the 720p floor upward, including HFR and 8K — are below
1 ms with margin; the worst case (720p50, the slowest line rate) is 0.61 ms.

Notes:
- **slice_h defaults to 16 lines.** 720p-class heights use 8. Since the banking
  overdraft went to zero this is no longer a hard impossibility — 720p50 at 16
  lines is 0.945 ms codec-only and 720p60 is 0.789 — but 720p50 **with a
  conversion** is 1.140 ms, and `uc_ratio` is advisory, so 8 is the default that
  holds whatever the far end decides to do. Heights that do not divide by 16 (1080) are
  coded padded to the next multiple and cropped on output, so they take the
  default like every other format — the older rule dropped them to 8 for an
  arithmetic reason and paid ~10 % of rate for it.
- The table above is the **8-line** figure for 720p and the **16-line** figure
  everywhere else. At 1080p, 16 lines doubles the capture and pacing terms:
  0.775 ms at 50 Hz, 0.646 ms at 60 Hz — both inside the bar with no conversion in
  the path. **With** a vertical rescale at 1080p50, `omc_validate_config()`
  refuses it under the shipped conversion charge (1.069 ms); run that leg at
  `--slice-h 8`, or adopt the raster-clocked output converter.
- One codec, one bitstream — slice_h is a coded parameter (stream header), read
  by every decoder, not a per-leg profile.
- Determinism: T_capture, T_transmit, T_overdraft, T_pipeline are all functions of the
  format only. The encoder's banking never violates the prefix bound (asserted in code),
  so the bound holds for every slice of every frame.

## OMC_XSL note
XSL level 3 finalizes ONE row (the previous slice's last) at the next
slice's reconstruction: the emission of that single row is deferred by one
slice period. Within a pipelined output stage this is absorbed by the
existing slice-period buffering; a strictly row-streaming sink must account
one extra slice period for the last row of each slice. No other term
changes; the per-slice cost is O(width) adds/shifts.


## The decoder's output stage — the contract, and what it is worth (2026-08-12)

The vertical rescaler needs a few source rows **beyond** the row it is producing:
6 for any interpolation, 9 for 3:2, 12 for 2:1, 18 for 3:1. What that costs
depends entirely on **how the decoder hands rows to it**, and that is now a
declared property of the implementation rather than an assumption:

| `cfg.uc_out_batched` | the contract | the charge |
|---|---|---|
| `OMC_OUT_RASTER` (0, **default**) | rows go downstream as they become final; the output is clocked at the destination raster rate | **`reach` lines + 1** |
| `OMC_OUT_SLICE_BATCHED` (1) | rows go downstream one whole slice at a time | `ceil(reach / slice_h)` whole **slice periods** |

**Why `reach × line_time`.** Output for source row *r* is producible once slice
`floor((r + reach) / slice_h)` has landed, and is due at `r · line + T`.
Maximising over *r* puts the worst case at `r = m · slice_h − reach`, which gives
`T ≥ reach × line_time` — independent of slice height. This is verified by
**row-by-row simulation over every supported (format, slice height, ratio)**
combination, not by algebra: gate **G21** in `tests/test_uc.c`, 165 cases, none
over the bound.

**The +1 line is OMC_XSL.** At level 3, slice *k* rewrites the **last row of
slice k−1** when it reconstructs, so that row is not final until one slice period
later. `LATENCY.md` used to warn that a strictly row-streaming sink must
therefore account a whole extra slice period — and a raster-clocked converter is
exactly such a sink. Simulated, the true cost is **one line**: the deferred row
sits at the *end* of its slice and already had `slice_h − 1` lines of slack.

**The price.** An output buffer of the filter aperture plus one slice — at most
68 rows, at 2160p → 720p with 32-line slices — and a free-running output clock. A
genlocked facility has both. An integration that cannot meet this must declare
`uc_out_batched` and take the higher figure; `omc_validate_config()` then refuses
what that figure cannot support, exactly as before.

**What it is worth.** Every conversion path in the product got cheaper, at every
slice height, immediately:

| path | before | after |
|---|---|---|
| 1080p50 → 720p50 (slice_h 8, ships today) | 0.705 ms | **0.594 ms** |
| 2160p50 → 1080p50 (slice_h 16, ships today) | 0.538 ms | **0.510 ms** |
| 720p50 → 1080p50 (slice_h 8, ships today) | 0.834 ms | **0.806 ms** |
| 1080p50 → 2160p50 at slice_h 16 | 1.069 ms — refused | **0.961 ms** |
| 2160p50 → 1080p50 at slice_h 32 | 1.061 ms — refused | **0.883 ms** |

The last two are the reason it was done: they are the only cells in the whole
supported matrix where the slice-height ladder was blocked, and both are 50 Hz.


## Task G addendum (2026-09-06) — the loss path carries no deferral

The reference decoder's concealment used to run once per frame AFTER every slice had been read,
because it searched DOWNWARD for a bracketing survivor. That put (n−1)/n of a frame period on the
loss path — 19.8 ms at 720p50, 19.7 ms at 1080p50, 19.9 ms at 2160p50 — a term this model never
counted and 16–20× the whole budget. Concealment is now upward-only (BITSTREAM.md, CONTROL_PLANE.md
§4a): a concealed slice needs nothing that has not already arrived, so the deferral term is 0.
Loss DETECTION remains one slice period (slices are variable length on the wire —
`48 + ceil(used_bits/8)` bytes — so a loss is confirmed when the next sync word is found), which is
structural and already inside the slice-period accounting above.

Every figure in this document is raster arithmetic (rows × line period, slice periods, conversion
periods). No C wall-clock measurement is a latency figure anywhere in this project.
