# OMC-1 Hardware Audit — FPGA-native by construction (C3)

Requirement: shifts, adds and table lookups only; **no multipliers in per-pixel paths, no
adaptive arithmetic coding**; both encoder and decoder real-time in dedicated hardware,
with margin. This audit inventories every per-sample operation in the reference
implementation (`src/`) and bounds the hardware cost.

## 1. Operation inventory (per-pixel paths)

| Stage | Ops per sample (order of magnitude) | Op types |
|---|---|---|
| Centering / decentering | 1 add | add |
| DWT 5/3 lifting step | 2 adds + 1 shift (predict); 3 adds + 1 shift (update) | add, shift |
| DWT (9,7)-M predict | 9x = (x<<3)+x → 5 adds + 2 shifts | add, shift |
| Full 2V×5H transform | geometric series over levels ≈ 2.6 lifting pairs/sample ≈ **~14 adds + ~6 shifts / sample** | add, shift |
| Quantization | abs + 1 add (bias) + 1 shift | add, shift |
| Category (bit length) | priority encoder (LUT/logic) | lookup |
| LL DPCM | 1 add | add |
| tANS encode (per symbol) | 1 table lookup + 1 shift + 2 adds | lookup, shift, add |
| tANS decode (per symbol) | 1 table lookup + 1 bit-read + 1 add | lookup, shift, add |
| Raw bits | barrel shift | shift |
| CRC-32 | 1 table lookup per byte | lookup |
| RC cost histograms (encoder) | per shift candidate: quant + cat + 1 add; 16 candidates → **≤ 16 (add+shift+lookup) / coefficient** | add, shift, lookup |
| RC search (per slice, not per pixel) | Q scan (16) + refinement walk (≤ 70 steps) + lattice-lock scan (≤ 4·16·71 candidates × 30 compares) ≈ 140k compare/adds per slice | add, compare |
| Temporal prediction (v3, inter bands) | forward DWT of the co-located reference rows (same ~20 add/shift per sample as the main transform) + 1 add per coefficient (delta) | add, shift |
| Global-MV search (v3, encoder, per slice, default) | 19 candidates × decimated SAD (every 4th col, every 2nd row) ≈ 19·W·sh/8 abs-diff adds ≈ 2.4 ops/pixel | add, compare |
| Override search (v3.1, encoder, opt-in `--mv-regions`) | 4×2 block sums (1 add/px, once) + ~44 candidate passes × half-decimated block SAD ≈ 6–8 ops/pixel extra; half-pel taps are (a+b+1)>>1 / (a+b+c+d+2)>>2 | add, shift, compare |
| MV prediction fetch | clamped shifted addressing of the reference; half-pel positions (v3.1) add 1–3 adds + 1–2 shifts per sample (**no multipliers**) | add, shift |

**There is no multiplication anywhere in a per-pixel path.** The only products in the C
source are array-index/stride computations (`row * width`), which in hardware are address
counters, and test/harness code. The 9× in the (9,7)-M filter is expressed and implemented
as `(x<<3)+x`.

**There is no adaptive arithmetic coding.** tANS tables are fixed ROM constants; table
*selection* is per-band and signalled, never state-adapted mid-stream.

## 2. Memory budget (per codec instance, worst supported case 8K width, 12-bit)

| Buffer | Size |
|---|---|
| Slice pixel/coeff buffers (enc or dec) | 3 planes × 16 lines × 7680 × 2 B (16-bit datapath) ≈ **720 KB** (4K: 360 KB; 1080p: 180 KB) |
| tANS decode tables | **136 tables × 1024 states × 4 B = 557 KB = 4.46 Mbit** (68 BRAM36 blocks; see §2a) |
| tANS encode tables | **136 tables × 6304 B = 858 KB = 6.86 Mbit** (see §2a) |
| Cost LUTs (encoder) | 16 × 16 × 2 B = 512 B ROM |
| Allocation tables | < 1 KB ROM |
| Slice bitstream buffer | ≤ 2 × bits_per_slice/8 ≈ 24 KB at 4K/2 bpp |
| CRC table | 1 KB ROM |

v3 adds **one reference frame store per direction** (the single previous reconstructed
frame, 10/12-bit samples): 4:2:2 4K = ~33 MB-bit ≈ 4.2 MB, 8K ≈ 17 MB — a standard
single-frame DDR store (or HBM/URAM on larger parts), streamed in slice-order with a
±4-line window for the MV range; bandwidth = 2× video rate (write recon, read reference),
comfortably within one DDR channel at 4K60. All other state remains on-chip BRAM as
before; an intra-only (v2-mode) instance still needs no DDR at all.

### 2a. CORRECTION (2026-09-05, Agent 4, Task D) — the tANS table figures above were 8.6x too small

The two table lines in §2 read "16 tables x 1024 x 4 B = 64 KB" until today.  That predates v4.4,
which took the entropy engine to **8 table groups x 16 magnitude contexts = 128 tables**, plus 8
Q5F skip-flag contexts: **136 tables**, not 16.  The figures above are now measured from the built
tables (`src/tans.c`, `omc_tans[8][16]` + `omc_tans_q5[8]`), not estimated:

* a **decoder** needs `sym[]`, `nbits[]` and `base[]` only -- 4096 B per table, **4.46 Mbit** total;
* an **encoder** needs the whole `omc_tans_table_t` (6304 B), **6.86 Mbit** total;
* measured field widths are `sym` max 15 (4 bits), `nbits` max 10 (4 bits), `base` max **1022**
  (10 bits) = **18 bits per entry**, so `1024 x 18 x 2 = 36 864` fits one BRAM36 **exactly** and two
  tables share a block: **68 BRAM36 for a decoder**.

**Consequence for §8's "297 KB on-chip" decoder figure: it is wrong for the same reason** and is
corrected in place there.  `Issues_to_fix/20260830/DDR_jitter.txt`'s "~790 KB per engine" is the
*encoder* struct -- right for an encoder, overstated for a decoder.

## 3. Datapath width

Input ≤ 12-bit centred (±2048). Measured transform growth ≤ +3 bits ((9,7)-M predict adds
≤ 1.25× tap mass; two vertical + two (9,7)-M levels worst-case |coeff| < 2^14.2).
16-bit signed everywhere suffices with ≥ 1 bit of guard; the C reference uses int32 for
convenience and asserts the 16-bit envelope in tests.

### 3a. CORRECTION (2026-09-05, Agent 4, Task D) — §3's worst case is not a worst case

The figure in §3 ("two vertical + two (9,7)-M levels worst-case |coeff| < 2^14.2", hence "16-bit
signed everywhere suffices with ≥ 1 bit of guard") does not follow from its own derivation, for two
independent reasons that push the same way. Flagged by Agent 5 (the level count) and completed here;
`notes/coef_bound.py` in the Task D folder reproduces every number below from the lifting steps.

1. **It counts four levels; `omc_slice_fwd_p` runs seven** — V1, H1, V2, H2, H3, H4, H5 (horizontal
   levels 1–2 are (9,7)-M, the rest 5/3). H3–H5 are omitted from the stated derivation.
2. **Its input amplitude is the source path's; the prediction path is one bit wider.** "±2048" is
   right for the encoder's centred source, but `predict_plane` feeds the *same* entry point with
   `v − mid − OMC_REF_BIAS`, where `v` spans the biased range `[0, maxv + 2·bias]` — i.e. **±4096**
   at 12-bit. Same shape as the frame-store sizing error corrected earlier in Task D: the biased
   domain is one bit wider than the sample domain, and it is the biased domain that is real.

The exact L1 gain per analysis stage (sum of |taps| of the composed lifting filter — the true worst
case over bounded inputs):

| stage | lowpass | highpass |
|---|---|---|
| 5/3 | **3/2** | 2 |
| (9,7)-M | **3/2** | 9/4 |

The (9,7)-M *lowpass* gain is exactly 3/2, the same as 5/3 — the extra predict taps cancel in the
update — so only the highpass is worse, which is why the "1.25× tap mass" reasoning in §3 does not
by itself set the width.

Worst path over the seven levels is **HL5** (lowpass six times, then the 5/3 highpass):
`(3/2)^6 × 2 = 22.78`, i.e. **+4.51 bits**, not +3.

* source path, |input| ≤ 2048 → |coeff| ≤ 46,656 → **17 bits with sign**
* prediction path, |input| ≤ 4096 → |coeff| ≤ 93,312 → **18 bits with sign**

**Measured, the coefficient domain is far below all of this**: max |coeff| = **4,352** (14 bits with
sign) across 8/10/12-bit, 0.5–4.0 bpp, lossless, hard-edged graphics, 4:2:2 and 4:4:4 and `slice_h`
32 (`notes/h_cwidth.sh`, probe `OMC_CWIDTH`, byte-inert). So this is a question of what a datapath
should be **sized** from, not evidence of a defect: nothing overflows today. But 16-bit signed is a
measurement-backed choice, not the bound §3 presents it as, and a decoder additionally has to hold
whatever the *syntax* can express (`OMC_NSYM = 16` caps the coded category at 15, so `|q|` up to
32,767 before the per-band shift).

## 4. Throughput structure

- Slices are fully independent → trivially parallel (per-slice engines or line-interleaved
  pipelines). 4K60 = 8.3 Mpix/frame ≈ 500 Mpix/s ≈ 1 sample/cycle at 500 MHz for a single
  pipeline, or 2 engines at 250 MHz — comfortable in mid-range FPGA fabric.
- Encoder RC needs the 16-shift histogram pass; at 16 parallel comparators this is one
  pass at pixel rate. The bounded retry loop (§ rate control) re-runs only the tANS pack
  of one slice; worst case is capped (40) and typical is 1; a hardware implementation
  sizes for 2 packs per slice period and still has margin.
- Decoder is single-pass: parse header → derive shifts (table walk) → tANS decode →
  dequant → inverse DWT, all streaming.

## 5. "Comfortably" (the margin claim)

At the worst supported format the design needs: ~20 integer add/shift ops per sample per
direction plus one tANS lookup per symbol — an order of magnitude below what a modern
mid-range FPGA provides at video rates; memory is BRAM-resident with >2× headroom; there
is no data-dependent control flow in per-sample paths except the bounded RC retries. The
encoder and decoder are the same class of machine (the encoder adds the histogram pass
and the pack loop), satisfying the both-ends-in-hardware requirement.

## v4 addendum — grain fill and verified lock (C3 audit)

**Decoder (and encoder reconstruction) per zero-coded detail coefficient:**
two compares (LL activity gate: 2 subtractions + 2 abs + 1 add + compare;
headroom guard: 1 compare), one ROM bit lookup (the 256×256 normative sign
tile, 8 KB, a fixed constant — generated by an init-time LCG in software,
storable directly as ROM in hardware), one shift (quarter-step amplitude).
No multipliers, no adaptive state, no dependencies beyond the already-decoded
LL band of the same slice. Decoder margin is unchanged in kind: the fill adds
O(1) logic per coefficient on the existing dequant path.

**Encoder fill decision:** one pass per detail band accumulating |coef| over
gated zero positions (add + compare per coefficient), one threshold compare
per band (shift). Within the existing cost-table pass budget.

**Encoder lock verification (A4):** simulating a candidate plan costs one
reconstruction-equivalent pass over the slice. Candidate tries are capped at
16 (`LOCK_VERIFY_CAP`); measured on re-encode chains: 80% of slices verify on
try 1, worst observed 11. Bounded worst-case addition ≈ 16 slice passes,
engaged only on inputs that are previous OMC reconstructions (natural camera
content never passes the lattice mask, so the live-encode path is untouched).
A capped-out slice codes naturally — always safe. Hardware profiles may set a
smaller cap; the cap trades only re-encode byte-exactness margin, never
correctness or the pipe.

**Per-slice setup:** fill tile offsets are shift/add constant combinations
computed once per (frame, slice, plane, band) — never per pixel.

## 6. v4.1 addendum (2026-07-28) - keep the audit current

- **Motion range** is now +/-32 px horizontal, +/-16 px vertical (was +/-8/+/-4):
  the reference-fetch window per slice grows to slice_h + 32 lines and the
  DDR burst pattern must cover +/-32 columns of misalignment; bandwidth
  remains 2x video rate, but the line-buffer/burst design in section 2 must
  be re-sized for the +/-16-line vertical reach.
- **Encoder MV search** now scans ~67 fixed candidates (was 19): decimated
  SAD cost rises to ~8 ops/pixel (from 2.4) - still adds/compares only,
  parallelizable per candidate.
- **Grain fill + per-plane gain (v4.0/4.1)**: per zero coefficient, 1
  tile lookup + sign select + up to 2 add/shift for the gain scale; the
  gate is 4 LL reads + 3 adds + 2 compares. No multipliers. Tile = 8 KB ROM.
- **Per-slice control arithmetic (encoder only, NOT per-pixel):** a handful
  of true integer multiplies/divides exist in rate control and the
  generation lock (partial-chunk interpolation room*nch/delta, lattice bit
  estimate d*k/nch, fill-gain aggregate num/den). Rate: a few dozen per
  slice. In hardware these are one small sequential divider or microcoded
  block; they do not touch the C3 per-pixel claim, but an RTL team should
  know they exist. Inventory: src/codec.c lines flagged in REPORT 12g era
  audit (grep "\\* kc /\\|/ delta\\|/ den").
- **Timing items to budget before RTL:** the deterministic overflow-attempt
  loop (bounded re-encode attempts per slice; worst measured in software on
  adversarial synthetic content is high - needs a hard cap x per-attempt
  cycle budget vs slice period analysis) and the lock verify (<= 16
  candidate reconstructions per slice, encoder-only; may be pipelined
  across slices or feature-staged).

## 7. Encoder attempt-loop timing budget (measured 2026-07-28)

The overflow backoff re-runs symbolize+entropy for a slice until it fits
(hard cap 40 attempts per entry to the loop, then a clean refusal).
**40 bounds one ENTRY, not the slice** — see the correction below the
table. Measured worst cases
(OMC_STAT_ATTEMPTS instrumentation):

| content / rate | slices needing >1 attempt | max | p99 |
|---|---|---|---|
| delivery rate 2.0 bpp (program) | 2% | **3** | 2 |
| 12 px/frame pan @ 2.0 | 0.4% | 2 | 2 |
| low tier 0.4 bpp (program) — **below the guarantee floor, see note** | 79% | **9** | 6 |
| adversarial synthetic (graphics @ 0.5) | 26% | **32** | 5 |

### 7a. Per-slice compute swing, and the number to provision from

The figure an RTL team has to size the encode stage from is not the mean
slice, it is the **worst slice against the mean within one frame**, because
the slice period is fixed and a slice that runs long has nowhere to put the
overrun. Measured per-slice CPU at **0.5 bpp — the owner's guarantee floor
(2026-09-05)** — 12 frames, shipped defaults, all cells owned footage:

| cell | mean us/slice | worst slice us | **worst / mean** |
|---|---|---|---|
| spotrobot 1080p 4:2:2 10 | 39,394 | 626,782 | **15.9x** |
| dng 720p 4:2:2 10 | 10,520 | 159,136 | **15.1x** |
| dng 1080p 4:2:2 10 | 23,224 | 259,188 | 11.2x |
| highway 1080p 4:2:2 10 | 24,481 | 204,629 | 8.4x |
| cf_gfx 4:2:2 10 | 3,960 | 27,466 | 6.9x |
| runner 1080p 4:2:2 10 | 18,999 | 77,294 | 4.1x |
| dng 2160p 4:2:2 10 | 40,195 | 122,617 | 3.1x |

**These numbers are EVIDENCE OF VARIANCE. They are not a provisioning
target, and they must not be used as one.** Two reasons, both of which have
to be read before the table above is used at all:

1. **They are CPU reference timings, not a hardware work bound.** The C
   reference is written for clarity; 626,782 us is what one software
   implementation took, not what the work costs in gates. Sizing an RTL
   stage from it would be sizing from the wrong quantity entirely.
2. **The real bound does not currently exist.** The per-slice worst case is

   ```
   W_max = N_lock x (N_emit x W_emit + N_repair x W_repair + W_verify)
   ```

   `N_emit` and `N_repair` are bounded (40 per entry, 48 repair passes at
   defaults — sections 7 above). **`N_lock` is not bounded: the generation-lock
   candidate walk has no cap, deliberately** — the cap was removed in T5 so
   **Task G (2026-09-06): the walk is now bounded by progress, not by count.** On zero-residual
   content the estimate-based early exit never fires (every candidate estimates ≈ 0 against a best of
   ~1,525 bits), so all 2,656 candidates were fully verified per slice — work that fits no slice
   period. `OMC_LOCK_MAXTRIES` (16) stops the walk after 16 candidates that did not improve the best,
   and the counter starts only once a lock exists, so it cannot cause a missed lock (the objection
   that removed the old cap). Byte-identical on 26 owner cells; the expert's nine extrema all encode.
   that the previous generation's plan is always re-found, and a missed lock
   breaks generation exactness. **So `W_max` is unbounded and no finite
   hardware provision can PROVE deadline compliance at any rate.**

The table therefore says: the work is highly content-dependent at the
guarantee floor, the spread is 3.1x-15.9x across content at one rate, and it
collapses with rate (on dng 1080p: 11.2x at 0.5 bpp, 3.9x at 1.0, 1.4x at
4.0). A part targeting >= 1.0 bpp only lives in a much easier regime. **What
the table does NOT say is what to build to**, and any document that turns one
of these ratios into a sizing multiple is overstating what has been measured.

Harness `Agents/Agent5/harness/lat_slicedist.sh`, log `out/slicedist.log`.

**0.4 bpp is below the guarantee floor (owner ruling 2026-09-05).** The
"low tier 0.4 bpp" row above is retained because it is a real measurement
and it shows the shape of the cost at low rate, but **0.4 bpp is not a
determinism target**: predictability is guaranteed from **0.5 bpp** up.
0.4 bpp still encodes and still produces a conformant stream; nothing is
promised about its worst-case timing. Do not size a deterministic part
from this row, and do not read it as a supported operating point.

RTL guidance: per-attempt cost is one symbolize+tANS pass (and it SHRINKS
per attempt as shifts coarsen - fewer symbols). Provisioning the encode
stage for 4x nominal entropy throughput covers p100 at the delivery rate;
a Contribution-profile part targeting >= 1.0 bpp only can treat >4
attempts as the refusal path. Low-rate SKUs must budget ~10x or pipeline
attempts across the slice period.

**CORRECTION (2026-09-05, Agent 5 measurement).** The sentence this
replaces read *"The 40 cap is a proven bound: the hardest content ever
constructed for this codec used 32."* Both halves are misleading and an
RTL team would under-provision from them.

- **40 is a per-ENTRY cap, not a per-slice bound.** The loop is
  `for (int attempt = 0; attempt < 40; attempt++)` in `omc_enc_slice`.
  The in-gamut repair re-enters that same loop with edited source
  coefficients via `goto encode_attempts`, so a slice's total emit work
  is `40 x (repair passes)`, not 40.
- **The measured per-slice worst case is 128 emit attempts**, four times
  the "32" this table reports — officewal 1080p 4:2:2 10-bit @0.5 bpp,
  12 frames, shipped defaults (`gamut_strict = 12`, `OMC_GM_REDOMAX = 1`).
  spotrobot @0.4 measured 112. Instrumentation and method:
  `Agents/Agent5/harness/lat_repairbound.sh`, log `out/repairbound.log`.
- The **32** in the table above is the per-entry figure and is correct as
  such; it is not the number to budget a slice period against.

Provision the encode stage against the per-slice figure. The static
per-slice bound derived from the code is in the `omc_gm_redomax` comment
in `src/codec.c` (48 repair passes at defaults), and one repair pass can
cost up to 40 emits.

## 7b. Where the guarantees begin: two floors, stated deliberately

The product has **two guarantee floors and they are not the same number.
That is intended.**

| guarantee | floor | scope |
|---|---|---|
| **determinism / predictable worst-case latency** | **0.5 bpp** | every resolution |
| **flatness** (zero flat textured blocks) | **0.5 bpp** up to 4K, **1.0 bpp** above 4K | per resolution |

**Why they differ.** Determinism is a hardware-timing property: it holds
wherever the codec runs, so it takes one number at every raster. Flatness
is a picture-quality bar, and above 4K a 0.5 bpp budget is genuinely thin
-- the owner priced that deliberately rather than promising a bar the rate
cannot buy. **The consequence, written down so it is not discovered: at
2160p and above at 0.5 bpp the product promises deterministic latency and
does NOT promise flatness.** Both floors are owner rulings (determinism
2026-09-05, flatness 2026-09-02).

Neither is the same thing as the **0.3 bpp mechanical limit** in
`src/config.c`, which is where a slice stops fitting on the wire at all.
See 7c.

## 7c. The 0.3 bpp mechanical limit is not a floor

`omc_validate_config()` refuses `bits_per_slice` below the equivalent of
0.3 bpp. **That is an implementation limit, not a product floor and not a
guarantee boundary**: below it a slice cannot fit its 48-byte header plus
minimum payload inside the 2x wire cap, so the encoder would refuse
anyway and the validator refuses early with a clean message instead of a
late failure. Rates between 0.3 and 0.5 bpp encode and decode normally
and are simply outside every guarantee. **0.5 bpp is where the guarantees
begin.**

## 8. Streaming decoder model (FPGA handoff artifact, 2026-07-28)

`harness/hw_decoder_model.py` re-expresses the decoder in the memory
structure hardware uses (line buffers + explicit ports) rather than the
whole-slice random access of the C reference, and byte-compares its output
to omc_dec on every conformance stream. It emits, per format, the memory
map with port directions and reference-store bandwidth. Representative
results (this model runs the bit-exact primitives, so a MISMATCH would
mean the architecture changed results - none observed):

- **1080p-class, R=8**: 297 KB on-chip + 1 reference frame (~7.7 MB at 4K,
  proportionally less at 1080p) in DDR; 0.41 GB/s reference bandwidth at
  50 fps (2x video rate).
- **Stateless R=1**: **zero external memory / zero external bandwidth** - the
  whole decoder fits on-chip.  **CORRECTED 2026-09-05 (Agent 4, Task D):** the
  "297 KB on-chip" figure in this section and the line above inherits §2's stale
  64 KB tANS table line and is wrong.  A decoder's live table set alone is
  **557 KB** (§2a), so 1080p-class on-chip is **~740 KB** before the Task D
  reference-window cache (a further **3.72 Mbit** at 1080p 4:2:2 10-bit; see
  `DDR_WINDOW_CACHE.md`).  The reference-*bandwidth* figures in this section are
  sound; only the on-chip capacity figures were wrong.  As of 2026-09-05 the
  reference stores are also no longer *allocated* at R=1 (`[D-R1]`, measured
  8.0 MB off the decoder's peak RSS at 1080p).
- **RGB/RCT studio**: same shape; inverse RCT is an output-stage add,
  no extra frame store.

The seven-stage slice pipeline (parse -> entropy -> dequant/fill ->
predict -> inverse DWT -> reference update -> output) is documented in the
model; no stage random-accesses beyond its line window, which is the
property that makes the RTL translation mechanical. This is the decoder
side of the architectural-model handoff (roadmap C1); the encoder-side
model (search/rate-control/lock control plane) is the larger remaining
piece.

## 9. Streaming encoder model (FPGA handoff artifact, encoder side, 2026-07-28)

`harness/hw_encoder_model.py` completes the architectural handoff (roadmap
C1). The encoder's per-pixel datapath is decoder-class (shifts/adds, no
multipliers); what it adds is a CONTROL PLANE - motion search, rate
control, generation lock, and the multi-pass overflow backoff - which is
where the encoder RTL effort concentrates. The model documents:

- **8-stage pipeline**: input lines -> forward DWT -> motion search ->
  rate-control/lock -> quantize/mode -> tANS -> CBR pack/backoff ->
  reference update.
- **Memory map, byte-checked against the instrumented reference encoder**
  (OMC_ENC_FOOTPRINT ground truth; the model's slicebuf/bandbuf/refstore/
  symbuf predictions match exactly on 4:2:2, 4:4:4, and RGB/RCT formats).
  1080p-class R=8: ~1.7 MB on-chip working buffers + one reference frame
  in DDR.
- **Reference bandwidth**: recon write 1x + search read with the
  +/-16-line halo (~3x at slice_h 16) ~ 0.8 GB/s at 1080p50; block-sum SAD
  keeps the search on cached lines (no per-candidate refetch). Stateless
  (R=1) parts omit the store entirely.
- **Control-plane pass counts** tie to the measured worst cases (section
  7): rate-control scan (pruned), <=48 lock-verify reconstructions
  (encoder-only, skippable in a no-generation SKU), <=40-attempt backoff
  (measured max 32 adversarial).

Correctness of the eventual RTL is proven by the conformance vector set,
not by this model; the model's job is the memory/port/timing architecture,
verified real against the reference encoder's own allocations.

### 9a. Encoder model reliability - what is verified vs asserted (2026-07-28)

Honest calibration of hw_encoder_model.py, by claim:

| claim | strength |
|---|---|
| datapath buffer sizes (slice/band/ref/symbol) | **verified two ways**: model formula == instrumented sum, AND the sum of ALL buffer classes (datapath + control-plane) reconciles with the actual live heap measured by the allocator (mallinfo2 uordblks+hblkhd) within +0.17% - a constant ~16 KB allocator overhead, resolution-independent. The measured-heap check rules out a shared-formula error, not just a transcription slip, and covers the control-plane lattice/cost buffers too. |
| memory MAP (which RAM, port direction, on-chip vs DDR) | derived from the code's allocation structure; port directions are asserted from the dataflow, not tool-verified. |
| reference-store bandwidth (~0.8 GB/s @ 1080p50) | ESTIMATE from a documented traffic model (recon-write + halo'd search-read); NOT measured against a memory trace. Treat as a design starting point for the RTL team's own bandwidth analysis. |
| 8-stage pipeline / dataflow | DESCRIPTION matching the reference structure; not mechanically extracted. |
| control-plane pass counts (attempts, lock candidates) | attempt counts are MEASURED (HARDWARE.md 7); the lock-candidate walk is bounded by PROGRESS since 2026-09-06 (`OMC_LOCK_MAXTRIES` 16 non-improving candidates, counted only once a lock is in hand — measured 2,656 → 17 verifications per slice on an all-black frame, byte-identical output); the rate-scan bound is read from the code, not swept. |

The method for turning the estimates into closed timing/bandwidth
numbers is docs/HW_TIMING_METHOD.md.

Bottom line: the **memory sizing is trustworthy** (independently measured);
the **bandwidth and pipeline-depth figures are engineering estimates** meant
to seed, not replace, the RTL team's own timing/bandwidth closure. Neither
model proves RTL CORRECTNESS - that is the conformance vectors' job
(make_conformance.py). The models size and shape the hardware; the vectors
prove it computes the right bits.

## 10. v4.2 addendum - motion-compensated + spatial concealment (2026-07-29)

Decoder-only error-recovery path (REPORT §15), on the **exception** path
(fires only for a lost slice), never in the steady-state pixel datapath.
FPGA-comfort inventory:

- **Path selection** (per lost slice): scan neighbouring slices' captured
  coding-mode bits for the nearest INTER neighbour -> temporal MC; if none
  exists (fully intra frame) and two survivors bracket the gap -> spatial;
  else -> freeze. Comparators + a short neighbour scan; no arithmetic. There
  is deliberately NO cut-detection probe (that would need a second reference
  buffer); the rule stays within the freeze/MC family unless there is no
  motion reference at all, which is what makes it provably >= freeze.
- **Temporal MC fill**: reuses the existing predictor - clamped shifted
  reference addressing + half-pel bilinear (adds + shifts, **no
  multipliers**), run in the pixel domain instead of feeding the transform.
  No new memory: it reads the reference store the decoder already has and
  writes the output line buffer it already has. The neighbour's motion
  vectors and coding-mode bit are the only new per-slice state to retain -
  nslices x (4 regions x 13 bits + 1) = a few hundred bytes at 8K.
- **Spatial fill** (frame 0 / intra frame only): one vertical linear
  interpolation per concealed pixel - `top + (bot-top)*(y-ra)/den`. This is
  the **only** multiply/divide the concealment adds, and it is on the error
  path, not per steady-state pixel. In hardware it is a per-column
  incremental accumulator (compute the row step once per column, then add it
  down the gap - no per-pixel multiply at all), or one small sequential
  divider shared across the block. Either way it does not touch the C3
  per-pixel claim.
- **No bitstream / determinism impact**: the encoder, the bitstream, the
  generation-lock and CBR guarantees are unchanged; a clean stream decodes
  byte-for-byte identically with concealment on or off. An SKU that wants
  the simplest possible decoder can omit the MC/spatial path entirely and
  fall back to freeze (hold-last) at zero correctness cost - it is a
  quality-of-recovery feature, staged independently of conformance.

Bottom line for the RTL team: concealment adds a small exception-path block

**Task G addendum (2026-09-06).** The spatial branch is gone: concealment is upward-only MC (or
freeze on a fully-intra frame). The interpolation multiply/divide above no longer exists; the
exception path is the MC projection only, and it needs nothing from slices below the lost one, so
the loss-path deferral is zero. See BITSTREAM.md §"concealment" and CONTROL_PLANE.md §4a.
that shares the decoder's existing reference store and predictor arithmetic;
budget one shared sequential divider (or per-column accumulator) for the
spatial fallback, and a few hundred bytes of per-slice MV/mode scratch.
Nothing here changes the steady-state datapath sizing above.

## 11. v4.4 addendum — entropy tables and new per-pixel ops (C3 audit)

- New per-pixel ops: context quantizer q2 = 3 compares; ctx = (q2<<2)+q2 =
  shift+add; deadzone = 1 compare against a shifted constant. Grain-replace
  classifier v2 (encoder-only, per detail-band coefficient of inter slices):
  1 parent-band read + 1 compare (scale vote) + 1 dcoef read, 1 shift and
  1 compare (temporal vote), evaluated in one per-slice eligibility pass over
  bands 4–9; eligibility maps cost 1 byte per detail coefficient of one slice
  (≈ 0.9·W·slice_h bytes across the three planes at 4:2:2, on-chip, reused
  per slice). No multipliers anywhere new.
- Expanded tANS tables: normative 8 groups × 16 contexts = 128 tables ×
  6304 B ≈ 790 KB per engine (decode-side subset ≈ 512 KB) — 2× the v4.2 set,
  chosen over the measured 16-group variant (+0.04–0.10 dB, 4× BRAM) to keep
  C3's margin literal. Legacy tables (64 × 6304 B) are additionally resident
  in decoders that accept minor ≤ 3 streams; encoder-only parts omit them.
- Rate-control cost pass shrinks: best_group scans 8 groups × 16 contexts
  (was 16 × 4) — same 128 products per histogram row class; unchanged order.
- Block-MV search (only when --block-mv): ~24 add/compare ops per pixel worst
  case, bounded candidate list, zero when disabled (default).

## 12. v4.7 addendum — grain-hold v3 and static grain fill (C3 audit)

Encoder-only policy changes inside `--grain-replace` (E-9 grain-hold v3,
REPORT §18.7, ENHANCEMENTS_LEDGER E-9/E-10) plus one signalled decoder-side
mode, `--fill-static` (stream byte 27 bit 2, bitstream minor 7 — BITSTREAM
§9.5). FPGA-comfort inventory:

- **Grain-hold v3 votes (encoder-only, per detail-band coefficient of the
  existing eligibility pass):** third amplitude vote is 1 compare against a
  shifted constant (|coef| < 3·2^(bitdepth-7)); per-slice-band grain-carpet
  vote is a count of small nonzero cells + 1 compare per band (>= 25%);
  parent threshold compare unchanged in kind (threshold 8 at 10-bit); the
  LL-gradient gate is REMOVED (net logic decrease). Soft-threshold coding
  shrinks eligible coded deltas by 1 step with a cap |q| <= 3: 1 compare +
  1 add per eligible coefficient. Compares/shifts/adds only — **zero new
  per-pixel multipliers**.
- **Static grain fill (`--fill-static`, decoder + encoder reconstruction):**
  the grain-fill sign-tile offsets become frame-independent — the same
  `omc_fill_offsets` per-slice setup evaluated with f=0, i.e. one additional
  per-band static offset pair alongside the existing per-frame pair. Per-band
  setup constants, never per pixel; no new line buffers, no new ROM.
- **Latency/throughput:** the latency table and steady-state datapath sizing
  above are unchanged. Legacy v4.6 behaviour is byte-exactly reproducible via
  env knobs (OMC_GR_SOFT=0 OMC_GR_PTHR=2 OMC_GR_CARPET=0 OMC_GR_LLTHR=24);
  minor <= 6 streams decode byte-identically (verified vs a pristine v4.6
  build), so deployed decoder RTL is untouched unless it opts into minor 7.

## 10. OMC-UC upconverter (output stage) — FPGA cost (C3)
The upconverter obeys the same construction rules as the codec core.

- **No multipliers in the per-sample path.** The 12-tap kernel is evaluated as
  shifts and adds; `test_uc` verifies the multiplier-free evaluation equals the
  tabulated coefficients for every tap over the full value range, and equals
  the tabulated multiply for every coefficient of every published polyphase
  table (rational ratios included).
- **No dividers.** The mirror addressing needs no modulo at any supported plane
  dimension (smallest supported is 640; proven unreachable for >= 20), so the
  per-sample path is divider-free in the reference implementation too.
- **ROM, not state.** The polyphase bank is a fixed table; phase 0 is the unit
  impulse, every phase has unity DC, the 1:2 phase equals the base kernel
  exactly, and phase p mirrors phase den-p — so a hardware bank stores half the
  table and addresses the rest by symmetry.
- **Line memory.** Vertical reach is 8 source rows for 2x (12 for the 4x
  cascade), i.e. one slice period at slice_h 8 — the same order as the codec's
  own slice buffering, and it reuses the existing line-store discipline rather
  than adding a frame buffer.
- **No allocation.** `omc_uc_scale_plane_ws()` takes caller-owned workspace,
  agrees byte-for-byte with the allocating wrapper on every ratio class, and
  REFUSES an undersized workspace rather than overrunning it (test_uc G20) —
  the no-malloc shape a hardware or real-time host requires.
- **Exact integer reversibility.** `down(up(x)) == x` byte-exact at 8, 10 and
  12-bit, and the 4x cascade inherits the contract level by level, so a
  scale-out/scale-in round trip through the stage is lossless by construction.

Latency and refusal behaviour: see LATENCY.md, "OMC-UC output stage".

---

# v5.1 addendum — the in-gamut repair's work bound (2026-08-25)

*This section amends the encoder-side work budget only. Nothing about the
DECODER changes in v5.1: the decoder is byte-identical in behaviour to v5.0's
(measured both ways, `docs/OMC_V5_1.md` §7.4), so every decoder figure elsewhere
in this document stands as written.*

## The bound that changed

v5.0's worst case per slice inside the strict in-gamut repair was

    2 x gamut_strict passes      (the gentle attempt + the converging restart)

v5.1 adds one more terminal branch — the **unbounded redo** (`docs/OMC_V5_1.md`
§4/F3): if the pass budget runs out with the slice still out of the legal range
*and* the LL bound was in force, the bounded attempt is discarded, the slice's
original coefficients are restored, and the slice is repaired again under v5.0's
rule with no bound. So the worst case becomes

    3 x gamut_strict passes

which at the default `gamut_strict = 12` is **36 passes rather than 24**. It is
still a hard, statically known bound — which is the property C3 requires ("an
FPGA pipeline has to budget the worst case, and an unbounded search has none") —
and an integrator who cannot afford it lowers `gamut_strict`, exactly as before.

## What it costs in practice

| measurement | v5.0 | v5.1 |
|---|---|---|
| encode, 6 frames 1920×1080 4:2:2 10-bit @0.5 bpp, best of 3 on a quiet machine | 7.21 s | **7.41 s (+2.8 %)** |
| repair passes summed over the encode (hardest cell in the corpus) | 457 | 563 |
| slices that fell back to the converging restart | 119 | 130 |
| overflow-backoff attempts (`OMC_STAT_ATTEMPTS`) | 193 | **180** |
| times the unbounded redo fired | — | rare, and it is the backstop that makes `oob = 0` unconditional: **every v5.1 preference stands down on that path**, including the restart's eligibility gate, so the rule there is exactly v5.0's |

The backoff-attempt count *falls* because the plan reset (§4/F1) stops the
encoder walking the ladder from a rung a previous repair pass had already backed
off to.

## Arithmetic class

No new per-pixel operation, and nothing in the decoder. The additions are:

- integer comparisons and a clamp per LL coefficient per repair pass
  (`gm_llbound`);
- **one integer divide per LL coefficient per pass** in the optional
  least-norm bound (`OMC_GM_LLPROP`, default OFF and not shipped) — the shipped
  path has no divide beyond those already present;
- two extra summed-area-table passes over the slice mask, which the repair
  already built for the alignment veto.

All of it is inside the encoder's per-slice repair loop, which is a bounded,
statically scheduled block, not a per-pixel path. C3's "no multipliers in
per-pixel paths, no adaptive arithmetic coding" is unaffected.

### Memory units (reconciliation, 2026-09-06)
All memory figures in this document are decimal megabits (1 Mb = 10^6 bits) of physical block capacity: ZU7EV UltraRAM = 96 blocks × 288 Kib = 28,311,552 bits = 28.3 Mb (AMD's product table states the same capacity as 27.0 Mb, i.e. 2^20-based); Block RAM = 312 × 36 Kib = 11,501,568 bits = 11.5 Mb (AMD: 11.0). Total 39.8 Mb decimal. Structure sizes (ring 29.05 Mb etc.) are decimal too, so every comparison in this document is like-for-like. Target part: XCZU7EV for every format; speed grade to be fixed by timing closure against docs/LATENCY.md (the cheapest grade that closes) — OPEN.
