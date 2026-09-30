# OMC-1 external-memory subsystem — what the RTL must implement
Task D deliverable, Agent 4, 2026-09-04.  Written against the integration tree
(`.work/v54tree_int`, stream minor 15).  Every number in it comes from the
model in `src/ddr_model.c`, which runs inside the real encoder and decoder and
is proven not to change a decoded byte (`notes/h_ddr_ident.sh`, 9 cells).

This document specifies the memory subsystem only.  It changes no bitstream
field and adds no codec behaviour; the one codec-side constraint it asks for
(§7) is encoder-only and non-normative.

---

## 1. What actually has to be in external memory

| store | side | needed when | size (packed, `depth` bits/sample) |
|---|---|---|---|
| previous frame, final committed picture (`refprev`) | encoder + decoder | `refresh_r != 1` | 1 frame |
| current frame, rolling reconstruction (`ref`) | encoder + decoder | always at `refresh_r != 1` | 1 frame |
| frame before that (`refprev2`) | encoder only | `refresh_r != 1` | 1 luma frame |

Everything else the reference software allocates is a software artefact and
must not be built in hardware:

* **the decoder's frame promotion is a `memcpy`** (`src/codec.c`, the `fidx8`
  change in `omc_dec_slice_ex`).  In hardware it is a rotation of two buffer
  base addresses and moves no bytes.  Charging it would have added a whole
  extra frame read + write per frame.
* **the encoder's `inub` un-blend copy is frame-sized in software** but
  `omc_xsl_unblend` touches only rows `k*sh-2 … k*sh+1` at each slice boundary
  — four rows per boundary.  It is a line-buffer operation on the capture
  stream, not a frame store.
* **`refprev` was allocated even at `refresh_r == 1`**, where it is never read
  (ledger S5.38, and the audit quoted in `DDR_jitter.txt`).  **Fixed** in this
  delivery (`[D-R1]`): the previous-frame stores are allocated only when
  `refresh_r != 1`, and an explicit inter-without-reference guard rejects a
  malformed stream that declares R = 1 and then signals inter data.  Measured
  at 1080p 4:2:2 10-bit: encoder peak RSS 66.1 → **49.6 MB** (two frame stores
  gone), decoder 44.9 → **37.0 MB** (one), stream and decode byte-identical to
  the base tree at R = 1 and at R = 8.  **A `refresh_r == 1` SKU needs no
  external frame memory at all.**

**Sample width — 13 bits at every depth.**  The bound is the one the DECODER
itself enforces in `reconstruct_slice()`:

```
    0  <=  committed sample  <=  maxv + 2 * OMC_REF_BIAS
```

= 4351 / 5119 / 8191 at 8 / 10 / 12-bit, i.e. **13 bits, the same at every
source depth**, because the ±2048 wide-domain window dominates.

*This corrects the first version of this document*, which stored the sample
bias-removed in `depth` bits on the strength of a measurement that the
committed picture is exactly `OMC_PIX_BIAS + [0, maxv]` over the gamut.  That
measurement is correct and it is what **our** encoder emits — but a decoder
must decode any conformant stream, and nothing in the format stops another
vendor's encoder from reconstructing anywhere inside the clamp.  **A resource
bound that depends on what an encoder chooses to emit is not a bound.**  The
correction costs ~30 % of traffic and of band memory at 10-bit.

---

## 2. Window geometry — the whole design rests on this

The predictor's vertical reach for slice *k* is fixed by the **slice-header
field widths**, not by the vector chosen: `src/codec.c` writes `mvy2` in 6 bits
biased by 32, so `mvy2 ∈ [-32, 31]` half-pel; `predict_plane` uses
`iy = mvy2 >> 1 ∈ [-16, 15]` plus one row for the half-pel tap.  Rows read:

```
 [ k*sh - 16 , k*sh + sh - 1 + 15 + 1 ]      = sh + 32 rows, clamped to [0, H-1]
```

Three consequences, all measured:

1. **The window is known the moment the slice header is parsed** — in fact
   before it, because the bound does not depend on the vector at all.
2. **Windows advance monotonically by `sh` rows.**  A cache that is a sliding
   band therefore fetches each row exactly **once**: read amplification is
   1.00×, not `(sh+32)/sh` (3.06× at `sh` 16, 5.0× at `sh` 8).  Measured
   `refread` is exactly one frame of samples per frame at every format.
3. **The "adversarial vector pattern" cannot exist.**  Alternating vectors at
   the range limits every slice changes which cached rows are *read*; it never
   changes which rows are *fetched*, because the band is addressed by row
   position.  There is no vector sequence that increases DDR traffic by one
   byte.

Band and ring:

```
 band_rows = (lead + 1) * sh + up + dn            up = 16, dn = 16
 ring_rows = max( band_rows ,
                  (sh + up + dn) + ((lead+1)*sh + dn + 1) )   with the cross-frame prefetch
 ring_rows = band_rows                                        without it
```

**`sh` here is the worst `slice_h` the decoder must accept, not the one our
encoder emits.**  `BITSTREAM.md` §7 makes **8, 16 and 32** all legal values of
header byte 12.  Sizing the ring at 97 rows — the `sh` 16 figure with the
cross-frame prefetch — happens also to cover `sh` 32 **without** the
cross-frame prefetch (96 rows), and both configurations meet their deadline,
so one physical store of 97 rows serves every legal slice height.  That is the
number this document uses.

> **Open point for the format owner.**  `BITSTREAM.md` §7 is self-contradictory
> on whether `slice_h` 32 is optional.  It says *"an implementation that
> declares support for 32 must size for it"* — which makes 32 a declared
> capability — and, four paragraphs later, *"not a per-leg profile and **not a
> conformance point**"* — which makes it mandatory for every decoder.  The two
> readings differ by roughly 10 Mbit of on-chip memory at 8K and they decide
> which FPGA the 8K product needs.  It needs a ruling.

The second term is the **frame boundary**, where the outgoing picture's bottom
window and the incoming picture's top are live at the same time.  At `sh` 16,
`lead` 1 that is 96 rows, not 64: sizing the BRAM on the steady band alone
understates it by 1.5×.

---

## 3. The prefetch schedule and the admission rule

```
 on parsing the header of slice k:
     issue burst reads for rows  (y1+1 … (k+lead)*sh + sh - 1 + dn)   into the ring
 during the last ceil(ring/sh) slices of a frame:
     issue burst reads for rows  (0 … (lead+1)*sh - 1 + dn)  of the NEXT reference
     picture, at the steady rate, into the ring's spare rows
 before slice k enters the prediction pipeline:
     ADMIT only when every row up to (k*sh + sh - 1 + dn) is resident
```

* The admission stall is **before** the slice pipeline.  Nothing inside the
  transform, prediction, entropy or reconstruction stages may ever wait on
  DDR: the inner pipeline reads BRAM only.
* **Prefetch on the real-time slice schedule; admit on pipeline progress.**
  These are two different clocks and the distinction is load-bearing.  The
  compute pipeline can stall on a slice by an order of magnitude and then
  sprint to catch up (measured: 13× the mean on 1 slice in 90).  A stall is
  harmless — it gives the memory *more* time.  The **sprint** is the dangerous
  direction: if the prefetch is triggered by the pipeline, the catch-up issues
  prefetches back to back and each must complete in the sprint's compute time
  rather than a slice period.  Measured, 2160p60 4:2:2 10-bit under that
  stall/sprint profile: prefetch on the real-time clock **+123.5 µs, 0 stalls**;
  prefetch chained to the pipeline **+113.9 µs, 6 stalls, worst 9.5 µs**.  The
  ring bounds how far ahead the prefetch may run, so the rule is self-limiting:
  a pipeline more than `lead` slices behind simply stalls the prefetch, which
  is correct and costs nothing.
* The available service time for a window is `lead * slice_period`.  At `lead`
  1 that is one whole slice period at every format (185 µs at 720p60 down to
  61.7 µs at 8K60).
* The cross-frame prefetch is what removes the frame-boundary burst.  Without
  it the boundary costs a whole band fill in one slice period: measured
  1080p60 margin falls from +245.1 µs to +191.5 µs, 8K60 4:2:2 from +56.8 µs
  to **−15.3 µs** (a deadline miss).
* Frame 0 of a stream is all-intra and reads no reference; the model's only
  stall anywhere is that stream-start band fill, which is not a real stall.

---

## 4. The DDR service side

* **Layout: row-major.**  A window is whole plane rows, so a row is one long
  sequential burst run.  Tiling or swizzling breaks it into short segments and
  costs an activation per segment: measured, a 512-byte tiled store turns 8K60
  4:2:2's +56.8 µs margin into **−21 254 µs**.  Do not tile.
* **Bank interleave — two separate address-map requirements, and the second one
  is the one that bites.**

  *(a) ACTIVATE hiding.*  Consecutive pages must map to different banks so the
  next `ACTIVATE` overlaps the current row's streaming.  A 2 KB page at
  64-byte bursts lasts **106.7 ns** at x64-2400 (2048 B ÷ 19.2 GB/s) — an
  earlier draft of this document said 213 ns, which was the x32 figure printed
  against the x64 label; the conclusion is unchanged and gets stronger, because
  the real DDR4 page is 8 KB per rank, not 2 KB, giving ~427 ns.  Against
  tFAW/4 ≈ 3–7 ns and tRRD_L ≈ 5–6 ns the activation hides by 20–80×.  Worth
  ~5× at 8K and the difference between the design passing and failing.

  *(b) BANK-GROUP rotation — tCCD.*  Within one DDR4 bank group consecutive
  column commands are separated by **tCCD_L = max(5 tCK, 5 ns)**; across bank
  groups by **tCCD_S = 4 tCK**.  At DDR4-3200 the 5 ns floor dominates, so a
  sequential run that stays inside one bank group runs at **~50 % of pin rate**
  no matter how good its page locality is.  Whether a run rotates bank groups
  is a property of the **memory controller's address map**, not of our access
  pattern, and vendor defaults are frequently tuned for page-hit locality
  rather than bank-group rotation.

  **Requirement on the integrator: extract the actual address map from the
  memory-controller configuration and confirm that low-order address bits
  select the bank group.**  Measured consequence at 8K 4:4:4 12-bit, two x64
  DDR4-3200 channels, adversarial traffic with 30 % contention: with a
  bank-group-interleaved map the margin is **+61.7 µs**; without one the design
  **misses its deadline**.  Model it with `OMC_DDR_BGILV=0`.

  *Component choice follows from the same mechanism:* specify **x8 components,
  not x16**.  x16 has 2 bank groups against x8's 4, and the worst tFAW (30 ns)
  and tRRD (6.4/5.3 ns) of the three widths.
* **Burst size** makes almost no difference (64/128/256 B are within 1 µs of
  each other at every format).  Use 64 B or 128 B — whatever the controller
  prefers.
* **QoS**: give reference reads priority over reconstruction writes.  It is
  free and it costs nothing when the bus is not busy; it is insurance for the
  contended case, not a load-bearing rule (measured: ±0.7 µs).
* **Read/write turnaround: make it a design parameter, not a controller
  property.**  This model charges a turnaround per request, which is
  conservative but depends on a controller that batches writes in a reorder
  window we do not control.  The reviewable form is *turnaround cost × number
  of forced direction switches*, with the number of switches bounded by **our
  own write-buffer depth** — which converts a controller-dependent quantity
  into one we set.  Size the reconstruction write buffer to whatever bound the
  deadline needs.
* **Refresh granularity.**  tRFC is ~350 ns at 8 Gb and ~550 ns at 16 Gb, so
  eight bunched refreshes are **2.8–4.4 µs** of dead bus — not a rounding error
  against a 61.7 µs slice period at 8K.  Check whether fine-granularity refresh
  (FGR 2× or 4×) improves the worst case; it usually does for latency-bounded
  designs, at some throughput cost, and it is a controller configuration item.
* **Refresh** is absorbed by the lead time.  Up to **eight** postponed
  refreshes bunched immediately before the request a window's deadline depends
  on (the DDR4 maximum) change no margin anywhere the design passes.
* **Contention**: a second master taking 30 % of the bus is inside the margin
  at every format except 8K 4:4:4 at 10/12-bit, which needs the second channel
  anyway (§6).

---

## 5. Capture and output

The codec's own cadence *is* the line cadence: the encoder consumes exactly
`sh` source lines per slice period and the decoder produces exactly `sh` lines
per slice period.  So the capture and output paths need a **2·sh-line buffer on
chip**, not a frame staged through DDR.

**2·sh lines of FULL PIXELS — all planes, not one plane.** (Corrected 2026-09-05,
Agent 4; the ambiguity was flagged by Agent 5.) The output packer emits ST 2110-20
pgroups, which interleave Y/Cb/Cr, so it cannot emit anything for a row-position
until all three planes' rows for it exist. A reader was free to assume the
cheaper reading and the number is 2–3× different, so it is now stated.

Two consequences:

* **A plane-sequential coefficient row order needs no growth here.** Holding `sh`
  rows of Y and `sh` of Cb while Cr still arrives is exactly what this buffer
  already does.
* **It is not "small and shallow" at 8K, and §7.1 said it was.** Sized at full
  pixels (`notes/onchip_total.py`):

| format | `sh` 16 | `sh` 32 |
|---|---|---|
| 1080p 4:2:2 10-bit | 1.23 Mbit (34 BRAM36) | 2.46 Mbit (67) |
| 2160p 4:2:2 10-bit | 2.46 Mbit (67) | 4.92 Mbit (134) |
| **4320p 4:2:2 10-bit** | **4.92 Mbit (134)** | **9.83 Mbit (267 of 312)** |
| 4320p 4:4:4 12-bit | 8.85 Mbit (240) | 17.69 Mbit (480 — over) |

At 8K this is the **largest single BRAM consumer in the decoder**, ahead of the
tANS tables (4.46 Mbit, 121 BRAM36). It scales with `sh`, so it is the term that
keeps a `slice_h` penalty alive after the line-based scan removes the coefficient
buffers' one.  Measured cost of getting this wrong
(staging both through DDR): 8K60 4:2:2's margin goes from +56.8 µs to
**−19 231 µs**, and 2160p120 4:2:2 10-bit from +61.7 µs to −1 726 µs.

Pixel packing/unpacking (ST 2110-20 pgroups, or SDI 10-bit words) is a
combinational stage over one pgroup: 5 bytes at 4:2:2 10-bit, 15 bytes at
4:4:4 10-bit.  Its latency is 0.001–0.036 µs; even a line-aligned
implementation costs one line (3.9 µs at 8K60, 23.1 µs at 720p60).

**The pgroup table has been verified** against SMPTE ST 2110-20:2022 by an
outside reviewer: all six implemented cells (4:2:2 at 8/10/12-bit → 4/5/6 octets
per 2 pixels; 4:4:4 at 8/10/12-bit → 3 octets per pixel, **15 per 4 pixels**,
9 per 2 pixels) match the standard, including the sample orders
C'B Y'0 C'R Y'1 and C'B Y' C'R.  The same table applies to constant-luminance
CLYCbCr, so no separate path is needed if that is ever signalled.  What has
**not** been verified and still needs a line-by-line check before ship: the RGB
and XYZ pgroup tables, 4:2:0 (added in the 2022 revision), and the interlace /
segmented-frame signalling — none of which we implement today.

---

## 6. Per-format verdict — bandwidth and deadline

Adversarial locality and refresh **plus** a second master taking 30 % of the
bus, both ends, packed 13-bit store, line-buffered pixel paths, row-major,
`lead` 1, prefetch on the real-time clock, band sized for the worst legal
`slice_h`:

| formats | memory subsystem | worst margin |
|---|---|---|
| 720p50/60 … 2160p60, 4:2:2 and 4:4:4, 8/10/12-bit, and 2160p120 4:2:2 | **one x64 DDR4-2400 channel** | +61.7 µs (one whole slice period) |
| 2160p120 4:4:4 (all depths) | **one x64 DDR4-3200 channel** | +61.7 µs |
| 4320p60, every chroma and depth | **two x64 DDR4-3200 channels**, split by row parity, or one channel with no other master on it | +38.7 µs |

**Every format in the constraint set meets its deadline with positive margin.**
The two channels split cleanly because a band is a contiguous row range: even
rows on channel 0, odd rows on channel 1 halves each channel's traffic exactly
and keeps the sequential run inside each.

**Compute jitter does not change this**, provided the scheduling rule in §3 is
followed. With the encoder stalling 13× its mean on one slice in 90 and then
sprinting at 15 % duty to catch up (measured pipeline behaviour, Agent 5),
margins are unchanged at 1080p and 4K. Chaining the prefetch to the pipeline
instead of the real-time clock costs 6 deadline misses at 4K — the sprint, not
the stall, is the dangerous direction.

## 7. On-chip memory — the budget, the mapping, and the part

Reviewed by an outside codec/FPGA expert on 2026-09-05; four of their
corrections are folded in below and each is marked.

### 7.1 The structures, and which memory each belongs in

| structure | belongs in | why |
|---|---|---|
| reference band ring | **UltraRAM** | one writer (prefetch DMA), one reader (predictor and concealment), long sequential rows. Fragmentation is negligible: an 8K luma row is 7680 × 13 = 99 840 bits = 1386.67 URAM words, so word-aligning each row wastes ≤ 71 bits (< 0.07 %) |
| slice coefficient buffer | **UltraRAM** (or BRAM on a part with BRAM to spare) | *corrected:* UltraRAM is **two ports, each doing one read OR one write per cycle** — not one read port plus one write port. The obstacle to a column pass is the fixed 72-bit word, not the ports, and a **tiled 4-row address map** fixes it: one tile row per 72-bit word, so a column pass fetches 4 vertically adjacent samples per access instead of 1. Build it as several shallow parallel banks selected by tile index, **not** one deep cascade — 82 blocks in one column would put >5 clock regions of pipeline in the read path |
| tANS decode tables | **BRAM** | random access by state, one lookup per symbol, wants replication for parallel decode contexts |
| XSL line buffer | **BRAM** | small and shallow: one row of `Wp` per plane |
| capture / output line buffers | **BRAM, and at 8K partly UltraRAM** | *corrected:* **not** small — 2·`sh` lines of FULL PIXELS, 9.83 Mbit at 8K 4:2:2 10-bit `sh` 32 (267 of 312 BRAM36), the largest single BRAM consumer in the decoder. At `sh` 32 the BRAM budget overflows and ~2.8 Mbit must move into spare UltraRAM; at `sh` 16 it fits BRAM comfortably. See §5 |

### 7.2 Two corrections that changed the numbers

**(a) The tANS entry is 18 bits, not 19 — measured, and it halves the table
BRAM.** Measured over all 136 built tables (128 coefficient + 8 Q5): `sym` max
15 → 4 bits, `nbits` max 10 → 4 bits, `base` max **1022** → 10 bits. Total
**18**. `1024 × 18 × 2 = 36 864` = exactly one BRAM36, so **two tables share a
block: 68 blocks, 2.51 Mbit**. An earlier draft claimed packing "saves no BRAM
blocks because 19 bits and 32 bits both occupy one block per table" — wrong by
a factor of two, and wrong because the entry width was assumed, not measured.

Both existing project figures are wrong for a decoder, in opposite directions:
`HARDWARE.md` §2's "16 tables × 1024 × 4 B = 64 KB" predates v4.4's 8 × 16
table set and **understates by 8.6×**; `DDR_jitter.txt`'s "~790 KB / 6.46 Mbit"
is the C struct including the *encode* fields — right for an encoder
(6.86 Mbit with Q5), overstated for a decoder.

**(b) The coefficient buffer is single, not double.** An earlier draft costed
two — decoded coefficients and prediction — and flagged that generating the
prediction band-by-band in step with entropy decode would need only one but
might not be implementable. It is not implementable that way, and it does not
need to be: **run the prediction's forward DWT one slice period EARLY**,
writing prediction coefficients into the buffer, and let entropy decode do
read-modify-write (`buf[k] += dequant(residual[k])`). The admission rule
already guarantees the reference window is resident before the slice enters the
pipeline, so the schedule exists; the forward transform still produces all bands
together, it just has to *finish* before rather than run *during*. Costs a
second port, which UltraRAM has. Worth **5.9–11.8 Mbit at 8K**.

(A pixel-domain variant — inverse-transform the residual and add motion-
compensated reference pixels at the output, deleting the forward DWT from the
decoder entirely — is what mainstream hybrid codecs do, but it is available
only if the inter mode is defined as residual-in-pixel-domain. OMC codes the
transform of the residual against the transform of the prediction, so that one
is a bitstream change, not an implementation change. Noted as a candidate for a
future profile, not proposed here.)

### 7.3 The budget

> **Open with the codec expert:** the single coefficient buffer below depends on
> running the prediction's forward DWT one slice period early.  The vector and
> the reference window are both available a slice ahead, but one buffer must
> then hold slice *k*'s live coefficients and slice *k+1*'s incoming prediction
> at once, and the inverse DWT needs the whole slice.  If the answer is two
> buffers, add the `coef buf` column again to URAM: 8K 4:2:2 then needs a
> ZU11EG rather than a ZU7EV.

Decoder, worst legal `slice_h`, 16-bit coefficient datapath, one coefficient
buffer, 68-block tANS tables:

| format | store | band (URAM) | coef buf | URAM | BRAM | total | ZU7EV (11 + 27)? |
|---|---|---|---|---|---|---|---|
| 1080p60 4:4:4 12b | 13 b | 7.26 | 1.47 | 8.73 | 3.10 | 11.83 | **yes** |
| 2160p60 4:2:2 10b | 13 b | 9.68 | 3.93 | 13.61 | 3.79 | 17.40 | **yes** |
| 2160p60 4:4:4 12b | 13 b | 14.53 | 5.90 | 20.43 | 4.43 | 24.86 | **yes** |
| 4320p60 4:2:2 10b | 13 b | 19.37 | 7.86 | 27.23 | 5.07 | 32.31 | no (URAM 27.2 of 27) |
| 4320p60 4:2:2 10b | **depth+1 (§7.4)** | 16.39 | 7.86 | **24.25** | 4.98 | **29.23** | **yes** |
| 4320p60 4:4:4 12b | 13 b | 29.05 | 11.80 | 40.85 | 6.35 | 47.20 | no |

**ZU7EV holds everything up to and including 2160p 4:4:4 12-bit**, and holds
**8K 4:2:2 10-bit if the store narrows** (§7.4). **8K 4:4:4 12-bit needs a
larger part** — but note it is *UltraRAM*-bound, not capacity-bound: on a part
with BRAM to spare the coefficient buffer moves to BRAM (URAM 29.0 / BRAM 18.2),
which a ZU19EG/KU15P-class device holds with room.

| requirement | smallest part with ≥ 10 % spare on both memories |
|---|---|
| up to 2160p 4:4:4 12-bit | **ZU7EV**, coefficient buffer in UltraRAM |
| 4320p 4:2:2 10-bit, 13-bit store | ZU11EG, coefficient buffer in BRAM |
| 4320p 4:2:2 10-bit, narrowed store | **ZU7EV**, coefficient buffer in UltraRAM |
| 4320p 4:4:4 12-bit | ZU19EG / KU15P, coefficient buffer in BRAM |

Device capacities are from memory and **must be confirmed against the
datasheets before anyone commits**; the requirement columns are computed.

### 7.4 The open question that decides 8K 4:2:2 — narrowing the store

§2 states the store at 13 bits because that is the clamp the decoder enforces.
**Carrying an unclipped reconstruction into the reference store is not normal.**
Every mainstream inter codec clips reconstruction to the sample range; so does
**VC-2 (SMPTE ST 2042-1)** — a royalty-free wavelet codec with no arithmetic
coder, i.e. our nearest relative — which uses the same bipolar-plus-offset
representation we do and then *normatively clips* before output.

The route that would narrow our store is a drafting change, not a technique:
**make in-gamut reconstruction a bitstream conformance requirement** ("it is a
requirement of bitstream conformance that reconstructed sample values, prior to
clipping, shall lie within `bias + [0, maxv]`"). The decoder is then entitled to
clip, the store is `depth` bits plus a guard, and a stream that violates it is
non-conformant rather than something we must reproduce. That is the same move
that lets HEVC hardware be built to a 16-bit datapath — the *convention* is free
to adopt, the processes are not, and we would take only the convention.

**One measurement says it is not free today — but it misses by very little.**
With the clamp instrumented (`OMC_CLIPSTAT`, byte-inert) and swept over 13 clips
× 4 rates (52 cells, 6 frames each), the committed picture leaves
`bias + [0, maxv]` **3 times in the whole sweep**: 2 samples at 720p 4:2:2 @0.5
(5 codes over) and 1 on graphics @0.5 (3 codes over). Every 1080p and 4K cell at
every depth and both chroma formats is clean.

So the conformance requirement is **not** one our encoder meets exactly today,
and it misses by a handful of samples at tens of codes — comfortably inside
**one guard bit**. Adopting the route therefore means either tightening the
in-gamut repair until it holds exactly, or sizing for `depth + 1` bits and
requiring only that. `depth + 1` is what §7.3 assumes and what buys 8K 4:2:2 its
place on a ZU7EV.

Two items belong with that decision and are not mine to settle:

1. **Derive the bound rather than assert it.** BBC R&D's `vc2_bit_widths` uses
   affine arithmetic to compute hard, never-under-estimating signal ranges for
   exactly this filter class (lifting DWT, integer arithmetic, quantiser), with
   heuristic near-worst-case patterns to corroborate. Open source, aimed at a
   royalty-free codec. Whatever range it yields should be **written into the
   spec as the clamp** — deriving a tight bound and leaving a loose clamp
   constant in the syntax buys nothing, because a conformant stream is entitled
   to the clamp.
2. **Or signal it.** JPEG 2000 / HTJ2K — explicitly permitted under C1 —
   signals the number of guard bits normatively rather than assuming fixed
   headroom, so the decoder's required dynamic range is a transmitted syntax
   element sized per stream.

**Caution before narrowing anything:** VC-2's documentation warns that per-level
accuracy shifts can themselves *cause* multi-generation loss. If OMC's 9/7-M
path carries such shifts, generation exactness may be partly relying on the wide
domain to absorb them. The 8-generation chains must be re-run with the store
narrowed, **on 9/7-M specifically** — the 5/3 path will very likely pass and
would mislead.

### 7.5 The one rule this document asks of the codec

Only one, and it is not a constraint on picture quality:

**Any per-block motion-vector field must be clamped so that *region vector +
block delta* stays inside the slice header's ±16 px vertical range.** This is a
**normative decoder-side expectation**, not a property of the current encoder
search: an encoder that widened its offset table or dropped its bounds test
would take the guarantee with it, and a decoder cannot detect that until its
cache misses. If the effective range doubles to ±32 px the band ring grows from
97 to 147 rows — **+51 % of the largest on-chip structure**, with no change in
bandwidth — and 8K stops fitting the part class in §7.3.

**The rule costs nothing today, and the reason is structural rather than
empirical.**  The block field codes a *delta* on the region vector, but the
block search rejects any candidate failing `dy < -30 || dy > 30` in half-pel
units — **applied to the absolute total, not to the delta** — so the sum is
bounded at ±15 px vertical / ±31 px horizontal by construction and cannot leave
the header field.

That structural bound is the guarantee.  A measurement confirms it holds in
practice but is not itself the guarantee: measured over 17 820 committed block
vectors per cell (Agent 1, `[A1-MVYRANGE]`, 2026-09-05) — vertical
[−15, +12] / [−15, +10] / [−9, +9] px and horizontal
[−26, +26] / [−8, +31] / [−25, +23] px on soccer2, runC and runner.  Read the
pair in that order: *"the search bounds the total, and the measurement confirms
it"*, never *"±15 was measured, so ±16 is safe"* — the second is the
encoder-behaviour-is-not-a-bound error in a smaller costume.

**Horizontal range is free and vertical is not** — the window is whole rows, so
anything inside the header's ±32 px horizontal field costs nothing in memory or
in bandwidth, and read amplification stays 1.00× whatever the vectors do. The
vectors already go that way: the same measurement puts the horizontal spread at
±26 to ±31 px against a vertical ±9 to ±15. **If range ever has to be traded,
trade into the horizontal field.**

**There is no vertical vector cap in this codec.** An earlier draft of this
document proposed one as an encoder-only setting to fit a mid-range part. That
was wrong twice over: the owner ruled for the larger part, and — independently —
an encoder-only limit would not have bought what it appeared to buy, because a
conformant decoder must reserve the full header range whatever our encoder
emits. `OMC_MVYCAP` survives only as a measurement instrument.

**A note on the half-pel tap.** The vertical fractional tap reads `sy0` and
`sy0 + 1` only — that is the "+1 row" already in the `sh + 32` figure of §2. The
A5 refresh barrier makes a fractional tap drop its fractional part when its two
source rows straddle a slice boundary, but that does **not** shrink the band: the
integer displacement of up to ±16 px still reaches rows belonging to other
slices, and the band must be sized for the case where the tap does not cross.

## 8. Interfaces the RTL owns

```
  DDR controller  ──AXI4 read ch──►  window prefetch DMA ──►  BRAM ring (ping-pong)
                  ◄─AXI4 write ch──  reconstruction writeback     │
                                                                  ▼
   capture pgroup unpack ──► 2·sh-line buffer ──► slice pipeline ──► 2·sh-line buffer ──► output pgroup pack
                                                        ▲
                                              admission gate (before the pipeline)
```

* one AXI4 read channel for reference windows, one write channel for the
  committed frame, with the read channel at higher QoS;
* outstanding-transaction limit sized so one window's rows are in flight
  together (`ring_rows` × planes descriptors is ample);
* the admission gate holds the slice scheduler, never the inner pipeline;
* the ring's write port is the prefetch DMA, its read port the predictor and
  the concealment projector — the same two readers, the same geometry.

## 9. The packet format's two forward-compatibility fields

Transport is out of the codec's scope (constraint D), but two header fields are
much cheaper to define now than to retrofit, and both are implemented:

* **An INTRA flag on each slice packet** (`OMC_PF_INTRA`).  A late joiner or a
  recovering receiver needs to know when it may start outputting.  The rolling
  refresh makes that derivable from slice index and frame phase, but requiring a
  receiver to reimplement our refresh schedule to find it out is exactly the
  coupling that makes a later RTP mapping painful.  One bit.  The packetiser
  derives it from the slice header's 30-bit mode mask at bit 246 (zero = no band
  of any plane is inter).  Verified against the shipped R = 8 rota: frame 0
  flags 68 of 68 slices intra, and each later frame flags exactly the nine
  slices of that frame's refresh wave.
* **A parameter-set generation counter**, carried on both the repeated
  parameter packet and every slice packet, so a receiver can detect that the
  stream header changed mid-stream and reject slices belonging to the previous
  format.  C8 versioning makes a mid-stream format change a near-certainty
  eventually.

The **absolute frame offset** in the slice header is confirmed as the right
choice and is well precedented for video payloads: RFC 2435 (RTP for JPEG)
carries a 24-bit fragment offset within the frame's scan data, and
RFC 4175 / ST 2110-20 carry line number plus offset within the line — absolute
position, not a fragment counter.  The fragment-offset-plus-unit-counter shape
used by H.264/HEVC FUs and by JPEG XS's codestream mode exists because those
payload units are variable-length entropy-coded blobs whose byte positions mean
nothing to the decoder and where losing one fragment destroys the whole unit.
OMC's slices are self-contained and independently decodable and a lost slice is
a bounded hole, so the offset is what makes "any subset in any order rebuilds
the frame at the right addresses" true.  **One sizing note for the eventual RTP
mapping:** our offset field is 32-bit; do not inherit RFC 2435's 24 bits (16 MB)
by habit — size it from the worst-case frame at the highest provisioned rate.


## Addendum (v5.3.6, 2026-09-08): the in-codec hooks are landed; one accounting difference recorded

The `[D-DDR]` hooks and `src/ddr_model.c` are compiled into the codec from v5.3.6 (`ddr_model.c` is
in the Makefile's `SRC`; in v5.3.5 it was linked only into `omc_ddr_sweep`, so the model could be
driven by synthetic references only). With `OMC_DDR=1` the model is driven by the real predictor;
`OMC_DDR` unset is byte-inert (six cells incl. 4K, Agent 4 `notes/h_ddrhooks_535.sh`).

First real-vs-synthetic comparison (Agent 4, Message 28 §4): `refread` agrees exactly (33,792,000 /
67,215,360 / 100,638,720 bytes at 4/8/12 frames); **`mvread` disagreed by a constant one luma
frame (+4,177,920 bytes)** because the encoder ran a wasted motion search against the mid-grey
initial `refprev2` at frame 1 -- fixed in v5.3.6 by the `[D-MV1]` frame-1 guard (byte-inert: the
search returned (0,0) on every one of 1,224 frame-1 slice instances). The verdict of this document
is untouched: worst wait 0.0 ns, stalls 0/272, slice margin 245,098.0 ns identical; peak bandwidth
agrees to 0.2 %. At x32 the synthetic driver is optimistic by ~50 % where there is no margin
(real worst wait 5,333,982 ns vs synthetic 3,500,973; 399 stalls vs 262) -- outside the shipped
x64 regime, recorded so nobody quotes the x32 synthetic figure. `store_bits()` returns 16 by default
(13 only under `OMC_DDR_PACK=1`): every figure here was measured at 16 bits per stored sample,
the conservative width; 13 is the bound on the sample value, not the stored width.
