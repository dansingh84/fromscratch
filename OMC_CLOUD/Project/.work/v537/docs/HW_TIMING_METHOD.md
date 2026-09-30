# How to close timing and data flow for OMC in hardware

The architectural models (hw_decoder_model.py, hw_encoder_model.py) SIZE
and SHAPE the hardware — memory map, port directions, pipeline stages — and
those numbers are verified (HARDWARE.md 9a). They deliberately do NOT prove
throughput or final bandwidth; those are the RTL team's to close. This note
is the recommended method, and what the reference codebase already provides
to feed it.

## 1. What "the models" give you as a starting point (not an answer)

- Memory sizes per format: independently measured, trustworthy (HARDWARE 8/9).
- Reference-store bandwidth: an ESTIMATE from a traffic model
  (recon-write + halo'd search-read). Use it to pick a starting memory
  technology (a single DDR4/LPDDR channel comfortably covers 4K60), then
  replace it with a measured number per step 4.
- Pipeline stage list and the control-plane pass counts (measured;
  HARDWARE 7). These tell you where the pipelining effort goes.

## 2. Throughput: the pixel datapath (the easy, deterministic part)

The forward/inverse transform, quantize, and tANS are fixed work per pixel
(HARDWARE 1: shifts/adds/LUTs, no multipliers, no data-dependent loops in
the per-pixel path). Method:

1. Fix a target: e.g. 4K60 4:2:2 = 2160 * 3840 * 60 * 2 (Y+C) ≈ 1.0 Gsample/s.
2. Choose a datapath width W_lanes (samples/clock) and clock f so that
   W_lanes * f >= target with margin. The transform is separable and
   line-parallel, so W_lanes scales by instantiating parallel column/row
   units — area-linear, no algorithmic limit.
3. The tANS stage is inherently serial per symbol (one state update per
   symbol). This is the throughput pinch point, exactly as in JPEG XS.
   Standard answer: run N independent tANS engines, one per slice, since
   slices are independent (the codec already codes each slice standalone —
   BITSTREAM.md 3). N = ceil(peak symbols-per-second / one-engine rate).
   Measure one-engine symbol rate from the RTL, then set N.

Deliverable to produce: a spreadsheet of (format, target Gsample/s,
W_lanes, f, tANS engine count) — the first real throughput closure.

## 3. Throughput: the encoder control plane (the hard part)

The pixel datapath above is shared with the decoder. The encoder adds
multi-pass control whose worst case is MEASURED (HARDWARE 7):

- overflow backoff: <= 3 attempts at 2.0 bpp, <= 9 at 0.4, <= 32
  adversarial, hard cap 40 **per entry to the loop** (HARDWARE 7: the
  measured per-SLICE worst case is 128, because the in-gamut repair
  re-enters the loop). Each attempt is one symbolize+tANS pass over
  the slice, and it SHRINKS per attempt (coarser shifts -> fewer symbols).
  **The "<= 9 at 0.4" figure is below the guarantee floor** (owner ruling
  2026-09-05: predictability is guaranteed from 0.5 bpp up) and is not a
  determinism target -- see HARDWARE 7.
- generation lock: **<= 4096 candidate reconstructions per slice**
  (`OMC_LOCK_CANDS` in `src/codec.c`; encoder-only; omit it entirely in a
  no-generation-guarantee SKU to remove this cost).
  **CORRECTION 2026-09-05 (Agent 5):** this line read "<= 48" and 48 is
  not a figure the code contains anywhere on this path. The candidate
  array is `OMC_LOCK_CANDS = 4096`, and the scan is bounded by it, so a
  **2026-09-06:** the scan is additionally bounded by progress — `OMC_LOCK_MAXTRIES` (16)
  non-improving candidates once a lock is in hand — so the per-slice verification count is
  ≤ 16 + (candidates tried before the first lock), not 4096. Measured worst 84 (gen 2) before, 17 after.
  part sized from 48 would be short by a factor of 85 on the one stage
  this document calls "the hard part". The candidates are deduplicated by
  derived plan, so the count actually *reached* is far below the cap on
  real content, but the cap is what a bound has to be taken from.
- rate-control scan: bounded table walk, cheap vs the above.
- perceptual-allocation weight (v4.7, encoder-only, DEFAULT ON,
  OMC_ALLOC=0 legacy): one energy sum over the slice plus one clamp,
  per slice, at the existing budget-assignment point (REPORT.md 18.x,
  ENHANCEMENTS_LEDGER E-11).
- plan-hysteresis check (v4.7, encoder-only): one table derive plus a
  cost sum when the plan is pinned, per slice (ENHANCEMENTS_LEDGER E-10).

Both v4.7 additions are per-slice control work at existing pipeline
points — they add no per-pixel datapath work and no buffering (the
LATENCY.md table stands).

Two RTL strategies, pick per SKU:
- **Pipeline the passes across slices** (throughput part): keep multiple
  slices in flight so a slow slice's extra attempts overlap the next
  slice's first pass. Sizing: provision the entropy stage for
  attempts_p99 * nominal (p99 = 2 at delivery rate — cheap), and treat
  > cap as the clean refusal path.
- **Budget for worst case** (latency-critical part): if a single slice must
  finish in its slice period regardless, provision attempts_max * per-pass
  cycles. At delivery rate that is 3x; only low-rate SKUs pay ~9x.

Deliverable: per target SKU, (rate range, chosen strategy, entropy-stage
overprovision factor, whether lock is included).

## 4. Bandwidth: measure it, don't trust the estimate

The model's ~0.8 GB/s (1080p50) is a traffic-model estimate. To get the
real number:

1. Interpose the reference encoder's reference-frame accesses (the reads in
   predict_plane / the motion search, and the write in the reference
   update) with a counting shim — a few lines around those call sites, or
   an LD_PRELOAD wrapper on a purpose-built access-logging build. Sum bytes
   read + written per frame; multiply by fps.
2. Compare to the model estimate. The estimate should be an upper bound
   (it assumes the halo over-fetch is not cached); real caching makes it
   lower. If it is higher, the search is re-fetching — a caching bug to fix
   before RTL.
3. Feed the measured per-frame reference traffic + the input read + the
   output write into the DDR controller's efficiency model to pick the
   channel width/speed.

The reference-store access pattern is already bounded and documented:
+/-32 columns, +/-16 lines of halo per slice, block-sum SAD on cached
lines (no per-candidate refetch). That boundedness is the property that
makes a small line-cache sufficient; verify the cache hit rate in sim.

## 5. Latency: already characterized, re-confirm in RTL

Reference latency is one slice (8 or 16 lines) plus transform depth,
sub-millisecond (docs/LATENCY.md). In RTL this is the pipeline fill depth;
confirm it matches after pipelining and that no stage stalls on the
reference store (the line-cache in step 4 is what prevents that stall).

## 6. The instruments the repo already ships for this

- `OMC_ENC_FOOTPRINT` (env): real per-class memory + measured live heap.
- `OMC_STAT_ATTEMPTS` (env): per-slice attempt-loop counts on any content.
- `harness/hw_encoder_model.py`, `hw_decoder_model.py`: memory/port/stage
  model, self-verified.
- `harness/make_conformance.py`: the vector set that proves the RTL
  computes the right bits (correctness, separate from timing).
- The reference C is the golden model: any RTL block's output is
  byte-compared against it on the vectors.

## 7. Order of operations for the RTL team

1. Decoder datapath throughput closure (step 2) - smallest, proves the
   shared datapath.
2. Decoder bandwidth measurement (step 4) - confirms the DDR interface.
3. Decoder RTL + conformance sign-off.
4. Encoder datapath (reuses 1) + control-plane strategy (step 3).
5. Encoder bandwidth (search adds the read traffic; step 4 again).
6. Encoder RTL + conformance + generation/loss re-verification against the
   harnesses.
