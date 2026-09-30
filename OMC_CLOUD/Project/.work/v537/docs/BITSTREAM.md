# OMC Bitstream Specification

> ## CURRENT AS OF v5.1 — READ THIS BEFORE THE BLOCK BELOW
>
> **v5.1 changes NOTHING in this document.** It is an encoder-policy release:
> the syntax below, the stream major and minor, and every normative
> reconstruction rule are exactly v5.0's. Measured both ways — a v5.0 decoder
> decodes a v5.1 stream byte-identically and vice versa (`docs/OMC_V5_1.md`
> §7.4), and the six v5-class conformance vectors in `delivery/conformance/`
> verify under both decoders. The paragraph below therefore still reads
> "v5.0" where it names the build the syntax was frozen in, which is correct.
>
> **This build is OMC v5.0: stream major 5, minor 12.** The release-identity
> block that follows was written for v4.9 and is left as written, because it is
> the record of what that release did. It does **not** describe this build.
>
> What is different in v5, and where each is specified normatively:
>
> | | |
> |---|---|
> | **major 5** | carried at stream header byte 4. A decoder refuses any stream whose major differs from its own; a v4 decoder rejects a v5 stream and vice versa. |
> | **minor 12, always** | v5 does not write a lower baseline minor for streams using no recent feature. The v4 practice of writing minor 7 for compatibility ended when the temporal semantics changed: there is no subset of v5 a v4 decoder can read. |
> | **minor 10** | the rebuilt T5 temporal layer — frame-buffer reference, derived motion, always-on reversible cross-slice edit, biased **unclipped** pixel domain |
> | **minor 11** | pad neutralization: on a raster coded taller than its display height, the surplus rows are a pure function of the committed visible rows |
> | **minor 12** | the flattest-tier grain-fill gate and the frame-independent (static) fill tile — both **normative reconstruction rules**, which is why they force a minor rather than being an encoder option |
>
> **`docs/TEMPORAL_T5.md` is normative for all of the above** and takes
> precedence over this document wherever the two disagree. This document remains
> normative for everything it describes that T5 did not change: header syntax and
> field layout, the tANS coder, the transform, quantization, the slice structure
> and the rate model. `docs/OMC_V5.md` is the plain-English account of what
> changed and why.

> **Release identity (2026-08-11) — HISTORICAL, describes v4.9.** This build is **v4.9**: it implements every
> feature through stream minor 9. The *baseline* minor written for streams using
> no post-7 feature stays **7** by design, so those streams stay byte-identical
> to v4.7 encoders (`OMC_VERSION_MINOR`); `OMC_RELEASE_MINOR` = 9 names the
> release. Minor escalates per feature: 8 = upconversion / in-loop TF, 9 =
> cross-slice boundary reconstruction (XSL 3 + refresh barriers + barrier
> display blend).

This document is the **normative** definition of the OMC compressed video bitstream (C8:
stable, fully documented, versioned). An encoder from one vendor and a decoder from another
interoperate by implementing exactly what is written here. Everything a decoder needs is in
the bitstream; the decoder holds **no state across slices or frames** (each slice is decoded
from its own bytes alone).

Version identification: stream header bytes 4–5 carry `major.minor`.

> **In OMC v5 this is `5.12`, on every stream.** A decoder MUST reject any
> stream whose `major` differs from its own, and v5 additionally rejects any
> `minor` that is not exactly 12 — the rebuilt temporal semantics are not a
> superset of earlier minors, so a decoder that accepted an older one would
> mis-decode it rather than degrade. `docs/TEMPORAL_T5.md` is normative for the
> minor-10/11/12 rules; `docs/OMC_V5.md` section 3 states the deployment
> consequence.
>
> The sentence that follows is the **v4** rule and is retained because it
> describes how minors 0–9 related to one another: baseline write `4.7`, `4.8`
> with upconversion/TF signaling, `4.9` with cross-slice boundary
> reconstruction, with a decoder of minor m decoding every minor ≤ m
> bit-exactly. That graded-compatibility model does not apply across the v4/v5
> boundary.

Decoders must reject streams with a different `major`
and any `minor` newer than they implement; a decoder of minor m decodes every
minor ≤ m bit-exactly (§9). All multi-byte integer fields in the **stream header**
are little-endian. All **bit-packed fields** (slice header, payload) use the LSB-first bit
convention of §4.

## 1. Stream layout

```
[stream header: 32 bytes] [frame 0] [frame 1] ...
frame  := [slice 0] [slice 1] ... [slice N-1] [frame padding to exactly F bytes]
```

- `N = height / slice_h` slices per frame; slices appear in raster order (top to bottom).
- `F = N * bits_per_slice / 8` bytes: **every frame occupies exactly F bytes on the wire**
  (constant bitrate; A1). Individual slices vary in size within the bounds of §5; the frame
  remainder is zero padding.
- For packet transport, one slice = one packet (the slice is the error-containment unit);
  the frame padding is not transmitted on packet networks.

## 2. Stream header (32 bytes)

| offset | size | field |
|---|---|---|
| 0 | 4 | magic `0x4F4D4331` ("OMC1", LE) |
| 4 | 1 | version major — **= 5 in OMC v5** (was 4 through v4.14). A decoder MUST reject any stream whose major differs from its own. |
| 5 | 1 | version minor — **= 12 in OMC v5, always**. v5 does not write a lower baseline minor: there is no subset of v5 an older decoder can read, so the compatibility-floor practice described below ended with v4. |
| 6 | 2 | width (luma samples; see constraints §7) |
| 8 | 2 | height |
| 10 | 1 | bit depth: 8, 10 or 12 |
| 11 | 1 | chroma format: 0 = 4:2:2, 1 = 4:4:4 |
| 12 | 1 | slice_h: coding-unit height in luma lines. Legal values **8 and 16 at every raster; 32 ONLY when coded height >= 2160**. **16 is the default**; 8 is used for 720p-class heights (A2). A stream carrying slice_h = 32 with a coded height below 2160 is **non-conformant** and a decoder shall reject it — see §7 |
| 13 | 2 | fps numerator |
| 15 | 2 | fps denominator |
| 17 | 1 | colour primaries (ISO/IEC 23001-8 code point: 1 = BT.709, 9 = BT.2020) |
| 18 | 1 | transfer characteristics (1 = BT.709/SDR, 18 = HLG; 16 = PQ is refused by the validator since v5.3.6 -- PQ is not carried by this codec) |
| 19 | 1 | matrix coefficients (1 = BT.709, 9 = BT.2020 ncl) |
| 20 | 1 | full-range flag (0 = video/limited range, 1 = full range) |
| 21 | 4 | bits_per_slice (CBR budget per slice period, multiple of 8) |
| 25 | 1 | refresh_r: rolling intra-refresh period in frames (0 -> 8). Encoders MUST code slice s all-intra on every frame where frame_idx mod refresh_r == s mod refresh_r (A5 recovery bound) |
| 26 | 1 | scan_type: reserved 0 (held by docs/INTERLACE_CONVENTION.md) |
| 27 | 1 | pixel_flags; bits 3-4 uc_ratio, bits 5-6 tf_mode (minor >= 8) |
| 28 | 4 | display_height / display_width (LE u16 each) |

Colour fields are carried transparently (B3): the codec never converts or interprets them.

## 3. Slice

A slice codes `slice_h` luma lines (and the co-located chroma lines) with its own header
and entropy stream. Spatially it references nothing outside its own rows. Temporally
(v3, constraints rev. 3) a band flagged `inter` predicts from the **co-located slice of
the single previous reconstructed frame**: the prediction is the forward transform of
those rows of the previous frame's decode — one frame of look-back, no libraries (C2).
A decoder therefore needs only the previous frame's reconstruction; slices whose mode
mask is all-intra decode from their own bytes alone. Frame 0 of a stream is all-intra.

```
slice := [slice header: 48 bytes] [payload: ceil(used_bits/8) bytes]
```

### 3.1 Slice header (bit-packed LSB-first, zero-padded to 44 bytes, then CRC)

| bits | field |
|---|---|
| 32 | sync word `0x4F4D5331` |
| 8 | frame index mod 256 (monitoring/resync aid) |
| 16 | slice index |
| 4 | Q (master quantization parameter) |
| 2 | profile (0 = fair/balanced, 1 = fair/texture, 2 = luma-weighted/balanced, 3 = luma-weighted/texture) |
| 8 | bit 7 = `mv_field` (minor 16; RESERVED 0 in minors 10-15), bits 6..0 = n_steps (refinement steps applied, 0..R) |
| 16 | partial_chunks (leading 256-coefficient chunks of the step-n_steps band coded one shift finer) |
| 24 | used_bits (payload length in bits) |
| 16 | tANS final state minus 1024 (10 significant bits) |
| 90 | per band, plane-major (Y,Cb,Cr × band 0..9): tANS table-group id (3 bits; minor 14 -- `OMC_NTABLES` = 8; was 4 bits through minor 13) |
| 16 | `state_hash`: hash of this slice's committed rows in the previous frame (minor 14, `[S3-HASH]`; the decoder verifies it against its own committed rows) |
| 14 | reserved, must be zero (minor 14) |
| 30 | mode mask, plane-major bit per band: 0 = intra, 1 = inter (temporal delta) |
| 52 | 4 motion regions × (mvx: 7 bits, offset −64; mvy: 6 bits, offset −32), **half-pel units** (v4.1) |
| 18 | grain-fill bits (v4.0), plane-major: one bit per detail band 4..9 per plane (§4.6) |
| 6 | per-plane grain-fill gain (v4.1): 2 bits each for Y, Cb, Cr (§4.6) |

The fields above fill bits [0, 352) = bytes [0, 44) exactly. **Version-0 minor
layout** (stream header minor = 0): the motion fields are 4 × (mvx: 5 bits,
offset −16; mvy: 4 bits, offset −8), the fill bits follow at bit 312, there is
no gain field, and the remainder to byte 44 is zero padding. Decoders select
the layout from the stream header's minor version.
| 32 | CRC-32 (IEEE 802.3, reflected 0xEDB88320) over header bytes [0,44) then payload bytes |

Motion regions (v3.1): the slice is split into 4 equal horizontal regions; region r
covers luma columns [r·W/4, (r+1)·W/4). Each region carries one motion vector in
half-pel units: displacement = (mvx/2, mvy/2) luma pixels, mvx ∈ [−64, 63],
mvy ∈ [−32, 31] (v4.1; ±8/±4 px in minor-0 streams) — a horizontal reach of
±32 luma pixels per frame and vertical ±16. The prediction fetch reads the reference clamped at frame edges;
half-pel positions interpolate with (a+b+1)>>1 (one axis) or (a+b+c+d+2)>>2 (both) —
shifts and adds only. For 4:2:2 chroma the horizontal displacement is mvx/2 in
half-chroma-pel units (integer division, truncating toward zero). An encoder using one
global vector per slice writes it into all four regions. Vectors are ignored for slices
whose mode mask is all-intra.

**Block motion field (minor 16).** Bit 7 of the `n_steps` byte is `mv_field`. It was the
v4.3 per-block motion-field flag, RESERVED 0 through minors 10-15, and minor 16 takes it
back for the same purpose. `mv_field = 0` means the slice carries no block field and is
byte-identical to a slice coded by an encoder without the feature; `mv_field = 1` means
the payload opens with the field, before the coefficient symbols.

The picture is divided into `nblk` equal-width vertical blocks, `nblk` derived normatively
from the picture width alone:

    block_width = clamp(round_to_nearest_multiple_of_8(width / 30), 32, 128)
    nblk        = ceil(width / block_width)

so both ends compute `nblk` without signalling. Blocks are coded left to right. Each block
carries one binary flag, tANS-coded, whose context is the flags of the two blocks to its
left. A flag of 0 means the block uses the vector of the region containing it, unchanged.
A flag of 1 is followed by the block's vector as a delta against that region vector, coded
as two magnitude-category symbols (x then y), each followed by `category` raw bits, in the
same **half-pel units** as the region vectors above. Six dedicated tANS tables carry these
symbols (constants in `src/tans.c`). The field costs nothing when absent and the decoder
performs no search: the vectors are transmitted, never re-derived.

**A5 refresh barrier on the motion fetch (minor 16, normative).** A fractional VERTICAL
interpolation whose two source rows lie in different slices drops its fractional part for
that row and uses the integer row alone; the horizontal fraction is unaffected, as are
rows whose pair lies within one slice. Both ends derive this from slice geometry alone and
nothing is signalled. The rule bounds loss recovery: without it an injected error is
duplicated across a slice boundary instead of merely transported, and the heal lag on the
reference probe rises from 10 frames to 16 (measured; see TEMPORAL_T5.md).

A decoder validates sync, ranges, and CRC before using a slice; a slice failing any check
is treated as lost (the decoder resynchronizes by scanning for the next sync word; the
affected rows are concealed by the application, e.g. hold-last-frame).

> **Task G (2026-09-06), concealment is upward-only.** A lost slice is concealed from the nearest
> surviving INTER neighbour ABOVE it (motion-compensated projection of the reference along that
> neighbour's vectors); if no inter neighbour exists above, the slice freezes (zero-vector
> projection). The former downward search and the two-sided spatial interpolation are removed, so a
> concealed slice depends on nothing that has not already arrived and the decoder's loss-path
> deferral is zero. Concealment output is not normative. Measured span of a single lost slice k on
> the loss frame: k−1 … k+1 (one code to k+3 on two cells), k+2 onward exact.

### 3.2 Band shifts are derived, not transmitted

The per-band quantizer shifts are a pure function of (chroma format, profile, Q, n_steps,
partial_chunks) and the **normative allocation tables** (§6):

```
shift[p][b] = clamp(Q + off[profile][p][b] + (chroma==444 && p>0 ? off444[b] : 0), 0, 15)
shift[0..n_steps) bands per refine_order are decremented by 1 (floor 0)
band at refine_order[n_steps]: its first partial_chunks chunks use shift-1
LL band (b=0) is additionally capped at shift <= 2   (anti-banding, G2)
```

## 4. Payload coding

### 4.1 Transform

Each plane's slice rectangle is transformed with a reversible integer wavelet,
2 vertical × 5 horizontal levels (Mallat for levels 1–2, horizontal-only for 3–5):

- Vertical: CDF 5/3 integer lifting (both levels).
- Horizontal levels 1–2: (9,7)-M reversible integer lifting
  (predict taps (−1, 9, 9, −1)/16, update (1,1)/4).
- Horizontal levels 3–5: CDF 5/3.
- Input samples are centred by subtracting 2^(depth−1) before the transform;
  output reconstruction adds 2^(depth−1) back and clips to [0, 2^depth − 1].

**Exact integer lifting (normative).** For a length-n (n even) signal x with
even samples s_i = x[2i] and odd samples x[2i+1], half = n/2:

```
5/3 forward:   d[i] = x[2i+1] − ((s_i + s_{i+1}) >> 1)         s_half := s_{half−1}
               L[i] = s_i + ((d[i−1] + d[i] + 2) >> 2)          d[−1]  := d[0]
(9,7)-M fwd:   d[i] = x[2i+1] − ((9·(s_i + s_{i+1}) − (s_{i−1} + s_{i+2}) + 8) >> 4)
               L[i] = s_i + ((d[i−1] + d[i] + 2) >> 2)          d[−1]  := d[0]
```

All shifts are arithmetic (floor). Even-sample indices outside [0, half) use
whole-sample symmetric reflection: `j < 0 → −j; j ≥ half → 2·half − 1 − j`
(clamped to ≥ 0). The inverse undoes update then predict with identical
arithmetic. Coded layout per band is L | H (low half then high half).

**Cascade order (normative).** Forward: vertical level 1 (5/3, all columns,
rows reordered L|H), horizontal level 1 ((9,7)-M, all rows), vertical level 2
(5/3, columns [0, W/2), rows [0, sh/2)), horizontal level 2 ((9,7)-M, rows
[0, sh/2), cols [0, W/2)), then horizontal-only 5/3 levels 3, 4, 5 over rows
[0, sh/4) at widths W/4, W/8, W/16. The inverse applies the exact reverse
sequence. Integer results depend on this order; it is not a convention.

Band layout inside the slice_h × W buffer (r2 = slice_h/4, r1 = slice_h/2):

| id | band | rows | cols |
|---|---|---|---|
| 0 | LL5 | [0,r2) | [0,W/32) |
| 1 | HL5 | [0,r2) | [W/32,W/16) |
| 2 | HL4 | [0,r2) | [W/16,W/8) |
| 3 | HL3 | [0,r2) | [W/8,W/4) |
| 4 | LH2 | [r2,2r2) | [0,W/4) |
| 5 | HL2 | [0,r2) | [W/4,W/2) |
| 6 | HH2 | [r2,2r2) | [W/4,W/2) |
| 7 | LH1 | [r1,sh) | [0,W/2) |
| 8 | HL1 | [0,r1) | [W/2,W) |
| 9 | HH1 | [r1,sh) | [W/2,W) |

(chroma planes: W replaced by the chroma width.)

### 4.2 Quantization

Per coefficient, shift s from §3.2: the coded value is q with reconstruction
`c' = sign(q) * (|q| << s)`. (Encoders quantize by biased rounding; the decoder only
dequantizes, so the rounding rule is not normative — reconstruction points are.)

### 4.2a.1 Vertical level-2 bottom-edge predictor (CANDIDATE — not in any shipped minor; would be normative)

**Status (v5.3.6):** qualified but NOT shipped; the shipped transform keeps the whole-sample mirror at every level (`OMC_VEXT = 0`). Reason: with the predictor on, the rail-plate cut gate G-T5-CUT24 leaks at the shipped refresh period at repair budgets 13 and 14 (`src/dwt.c` §55 decision note; `docs/CHANGES_v5_3_6.md` §C). The rule below is what would ship, under a minor bump, once the repair granularity question is settled.

In the vertical **level-2** 5/3 lifting, forward and inverse, the sample one past the last
even sample of a run of `nv` visible samples is

    x[2i+2] := x[2i] + round_half_away((x[2i-2] - x[2i]) / 2)        for i >= 1

(the midpoint of the two even rows above), so the last predict step becomes the two-sided
blend `(3·x[2i] + x[2i-2]) / 4` to rounding. The whole-sample mirror is kept for `i = 0`
(a two-sample run). Level 1 and every horizontal level are unchanged (they keep the mirror).
`round_half_away` is the symmetric rounding of `src/dwt.c` `vext_hi()`: `d = 2·(x[2i-2] - x[2i])`,
`d >= 0 ? (d + 2) >> 2 : -((-d + 2) >> 2)`. The predict step reads only even samples both ends
already hold, so the lifting remains an exact integer bijection (rt = 0, lossless and the
generation lock untouched); shifts, adds and one compare (C3). Slice header and payload syntax
would be unchanged; it carries a minor bump when it ships.
Rationale and measurements: `src/dwt.c` §55 and `docs/CHANGES_v5_3_6.md` §C.

### 4.2a Coefficient range and decoder saturation (minor 16, normative)

A conformant decoder shall represent each reconstructed transform coefficient of band *b*
(dequantised value plus, for inter bands, the prediction) over at least the signed range
`[-2^(W_b-1), 2^(W_b-1)-1]`, where `W_b` is given for each band by the table below. It is a
requirement of bitstream conformance that no reconstructed coefficient lie outside that range;
a decoder shall saturate to `[-(2^(W_b-1)-1), 2^(W_b-1)-1]` any value that does, and the values so
produced shall be treated as conformant for all subsequent decoding.

The range is derived, not measured: composed L1 analysis gain of the tree (lowpass 3/2 per
stage; highpass 2 for 5/3, 9/4 for (9,7)-M — the (9,7)-M highpasses are H1 and H2 only) on the
biased prediction-path input `±4096`, plus the dequantiser overshoot `Δ_max/2 = 16384`
(`OMC_MAX_SHIFT` 15). On every legal stream the saturation is provably a no-op, so it cannot
perturb the generation fixed point; on a corrupted stream it bounds the failure and makes it
identical across implementations (`src/internal.h` `omc_band_wbits[]`, `omc_sat_band()`;
decoder site in `omc_dec_slice`). The committed PICTURE is never clipped (§"legal range"): a
picture clip is active on legal content and breaks the lattice; this coefficient saturation is
not. Datapaths are sized from `W_b`; 18 bits packs four per 72-bit UltraRAM word.

| band | name | composed L1 gain | bound (gain×4096 + 16384) | `W_b` (signed) |
|---|---|---|---|---|
| 0 | LL5 | 2187/128 = 17.086 | 86368 | **18** |
| 1 | HL5 | 729/32 = 22.781 | 109696 | **18** |
| 2 | HL4 | 243/16 = 15.188 | 78592 | **18** |
| 3 | HL3 | 81/8 = 10.125 | 57856 | **17** |
| 4 | LH2 | 27/4 = 6.750 | 44032 | **17** |
| 5 | HL2 | 243/32 = 7.594 | 47488 | **17** |
| 6 | HH2 | 81/8 = 10.125 | 57856 | **17** |
| 7 | LH1 | 3 = 3.000 | 28672 | **16** |
| 8 | HL1 | 27/8 = 3.375 | 30208 | **16** |
| 9 | HH1 | 9/2 = 4.500 | 34816 | **17** |

### 4.2b Temporal prediction (inter bands)

For a band with mode bit 1, the coded values are quantized **deltas**: the decoder
reconstructs `coef = pred + sign(q)*(|q|<<s)`, where `pred` is that band of the forward
transform (§4.1) of the motion-compensated fetch (§3.1) of `slice_h` rows from the
**rolling reference buffer**. Encoder and decoder derive `pred` identically and
deterministically. Mode is chosen per band by the encoder (rate cost); a scene cut
naturally selects intra everywhere.

**Rolling reference (normative).** The reference buffer is one frame-sized picture
per plane, updated with each slice's reconstruction **immediately after that slice
decodes**. Consequently a motion vector reaching rows above the current slice reads
already-decoded rows of the *current* frame, while rows at and below the current
slice still hold the *previous* frame. This is causal at both ends and both
implementations must follow it exactly; treating the reference as a frame-level
double buffer decodes zero-vertical-MV streams correctly but diverges on any
vertical displacement. Before the first slice of a stream the buffer holds
2^(depth−1) in every sample.

### 4.3 LL DPCM

Band 0 (LL5) is coded as horizontal first-order differences of the quantized values,
predictor reset to 0 at the start of each band row.

### 4.4 Symbols and contexts

Bands are coded in order p = Y,Cb,Cr × b = 0..9, coefficients in raster order within the
band. Each coefficient (for LL: each DPCM difference) v produces:

- symbol `cat` = bit length of |v| (0..15; 0 means v = 0), coded with tANS;
- if cat > 0: `cat` raw bits = (cat−1) magnitude LSBs (the MSB is implicit), then 1 sign bit
  (1 = negative).

Context: `ctx` = sig(left) + 2·sig(above) in {0..3}, where sig(x) = 1 if that
neighbouring value (same band; post-DPCM for LL) was nonzero. Left is 0 in column 0;
above is 0 in the band's first row (one row of significance flags is the only context
memory — strictly within-slice, within-band). The tANS table for the symbol is context
`ctx` of the band's signalled table group.

### 4.5 tANS entropy coding

- Table size L = 1024 states, 16 symbols; 16 normative static table GROUPS of 4 context tables each (§6, `omc_tans_counts`).
- Spread: step (L/2 + L/8 + 3) symbol spreading (position = (pos+step) mod L),
  symbols in ascending order, counts[s] slots each.
- Decode-table construction (normative): visiting states i = 0..L−1, let s =
  spread[i] and x = counts[s] plus the number of earlier states assigned to s;
  then `nbits[i] = 10 − floor(log2 x)` and `base[i] = (x << nbits[i]) − L`.
  Decoding at state st ∈ [0, L): emit sym[st], read nbits[st] payload bits b,
  next state = base[st] + b.
- Decode: state x ∈ [0,1024); entry (sym, nbits, base) := table[x]; emit sym; read nbits
  from the stream; x' = base + bits. Initial state = header field. After the last symbol,
  x must equal 0 (encoder start state 1024); mismatch = corrupt slice.
- Bit order: the payload is one LSB-first-written bit string; the decoder reads it
  **backwards** from bit `used_bits` (stream-ANS convention). Per coefficient, the decoder
  reads the tANS bits first, then the raw bits — the encoder, processing coefficients in
  reverse, wrote raw bits before tANS bits so that the backward read yields them in order.
- State remains in [1024,2048) across table switches (single interleaved stream).

### 4.6 Grain fill (v4.0)

Rev. 6 of the constraints judges quality by eye; the dominant visible loss of
MSE-optimal quantization on grainy content is texture erased to zero. The fill
mechanism reconstructs that erased energy deterministically, in-loop, without
spending payload bits on its realization.

**Semantics.** For a detail band b ∈ [4,9] of plane p whose header fill bit is
set: every coefficient whose **coded value q is 0** and whose reconstruction
before fill is exactly 0 (for inter bands this means the co-located prediction
coefficient is also 0), and whose per-coefficient shift s ≥ 3, reconstructs as

```
a  = 1 << (s-2)                                   (quarter-step magnitude)
if s >= 4: a scales by the plane's gain code (v4.1, header bits [346,352)):
    0: a            (1.0x)
    1: a + (a>>2)   (1.25x)
    2: a + (a>>1)   (1.5x)
    3: a + (a>>1) + (a>>2)  (1.75x)
c' = sign ? +a : -a
```

Gain codes scale only coefficients with s >= 4: there every scaled amplitude
is an exact integer that re-measures to itself (12/64-, 20/64-, 24/64-,
28/64-step aggregates are generation fixed points), and every amplitude stays
strictly below the quantizer zero zone 2^(s-1), preserving idempotence. At
s = 3 the amplitude is always the plain quarter-step. Encoders derive the
code from the aggregate measured amplitude of the gated zero-coded positions
across the plane's filled bands with base shift >= 4, in 1/64-step units:
< 18 -> 0, < 22 -> 1, < 26 -> 2, else 3; under `--tune vmaf` the code is
clamped to <= 1 (the narrowed zero zone 0.375*2^s would break idempotence at
1.5x and above).

subject to two gates evaluated on the **final reconstructed LL band** (band 0)
of the same plane and slice, at the LL cell co-located with the coefficient
(band rows map 1:1 for bands 4..6 and 2:1 for bands 7..9; band columns map 8:1
for bands 4..6 and 16:1 for bands 7..9; cell indices clamp to [1, dim−2]):

- **activity gate:** |LL[r][x_hi] − LL[r][x_lo]| + |LL[r_hi][x] − LL[r_lo][x]| ≥ 12,
  so genuinely flat regions (graphics, clean gradients) receive no fill.
  Cell clamping is ordered: first raise to ≥ 1, then cap to ≤ dim−2; the
  neighbour indices then clamp in-bounds independently:
  r_lo = max(r−1, 0), r_hi = min(r+1, dim−1) (likewise x_lo/x_hi). For an LL
  of ≥ 3 cells in a dimension the neighbour clamp is a no-op; for the 2-row
  LL of slice_h = 8 it defines the gate (this corner was undefined - and an
  out-of-bounds read in the reference - until the second implementation
  exposed it);
- **headroom guard:** |LL[r][x]| ≤ mid − (mid >> 4) where mid = 2^(depth−1),
  so fill never lands near clip range.

**Sign.** The sign bit is `tile[(row + foy) & 255][(col + fox) & 255]` of the
normative 256×256 sign tile: generated once by the LCG
`x ← x·1103515245 + 12345` seeded with `0x4F4D4331`, taking bit 30 per step,
32 bits per row-word, rows filled word-major (tans.c `build_sign_tile`). The
offsets decorrelate frame/slice/plane/band and animate the fill at frame rate:

```
fox = (97·f + 21·b + 124·p) & 255,  foy = (61·f + 37·slice_idx) & 255
```

with f = frame index mod 256 (from the slice header), row/col band-local.
All multiplies are by constants expressible as shifts/adds (C3), computed per
band setup, never per pixel.

**Encoder policy (informative but recommended):** set a band's fill bit iff
the mean |source coefficient| over its gated zero-coded positions (at the
band's base shift) is ≥ 3/16 of the step and at least 16 such positions exist.
This measurement is exactly idempotent under re-encoding: a filled band
re-measures to step/4 ≥ 3/16 step, so generation chains reproduce the bit.

**Idempotence (normative consequence).** Fill magnitudes are 2^(s−2): under
the same shift they re-quantize to 0 and regenerate identically (same frame
index, tile, gates), which is what keeps multi-generation chains byte-exact.

## 5. Rate constraints (normative for buffer/latency analysis)

- Every slice: `48 + ceil(used_bits/8) <= bits_per_slice/8 * 2` bytes.
- Prefix bound: for every k, the total bytes of slices 0..k of a frame do not exceed
  `(k+1) * bits_per_slice/8 + bits_per_slice/16` (banking overdraft ≤ ½ slice).
- Frame bound: total slice bytes ≤ F; the frame is padded to exactly F.

## 6. Normative tables

- `omc_tans_counts_legacy[16][4][16]` — legacy tANS symbol counts per (group,
  context), sum 1024 each (normative for minor ≤ 3 streams): src/tables.c.
- `omc_tans_counts_v4[8][16][16]` — v4.4 tANS symbol counts, 8 groups × 16
  magnitude-contexts (normative for minor ≥ 4 streams): src/tables_v4.c.inc.
- `omc_off[4][3][10]`, `omc_off_c444[10]`, `omc_refine_order[]` — allocation
  tables, NORMATIVE and reproduced in full in Annex A of this document
  (source of record: src/alloc.c; a decoder implemented from this
  specification alone requires Annex A - see GAP-1, docs/HANDOFF_2026-08-04.md).
These tables are part of this specification; changing them is a version change.

## 7. Constraints

- Width: multiple of 32 (4:4:4) or 64 (4:2:2). Height: multiple of slice_h.
- **`slice_h` is a knob with a default, and the default is 16.**

  **Legal values: 8 and 16 at every raster, and 32 only when the coded
  height is 2160 or greater** (and 0 in an API config, meaning "use the
  default"). The default:

  | height | slice_h | why |
  |---|---|---|
  | > 720 (1080p, 2160p, 4320p …) | **16** | the default. Heights that do not divide by 16 — **1080 above all** — are coded at the next multiple (1088) and cropped on output by the pad-and-crop path of §8. This costs under 1 % of rate in padded rows and is worth roughly **10 % of rate at 1.0 bpp and 16 % at 0.5 bpp** against 8-line slices, measured at 1920 px on real footage, on every plane at once |
  | ≤ 720 (720p-class) | **8** | **A2.** With the banking overdraft removed (2026-08-12) 16-line slices now fit 720p on the codec term alone — 0.945 ms at 50 Hz, 0.789 at 59.94/60 — but **720p50 with a vertical rescale in the output path is 1.140 ms and does not fit.** Since `uc_ratio` is advisory and a decoder may convert on its own initiative, 8 is the default that is safe whatever the far end does. `--slice-h 16` is available at 720p and is sound at 59.94 Hz and above (0.951 ms with the worst conversion), or at 50 Hz on a leg that will never convert |

  An encoder MAY be told otherwise: `--slice-h N` (CLI) or `cfg.slice_h` (API)
  overrides the default, and the value written into byte 12 is what the decoder
  obeys. `slice_h = 0` selects the default above. The **coded** height must be a
  whole number of slices; a picture whose true height is not (1080 at slice_h 16)
  is coded padded and cropped with `display_height`, which is what
  `tools/omc_enc.c` does for you.

  **32 lines** is available as an explicit choice and is never the default. At
  2160p it is the same fraction of picture height that 16 lines is at 1080p —
  the same step, not a second helping — and it measures a further 6.5–12 % of
  rate there. Its latency is the constraint: 32 lines fits with a conversion in
  the path at 2160p and 4320p from 59.94 Hz upward, and at 2160p50 only with the
  raster-clocked output converter.

  **Below a coded height of 2160, `slice_h = 32` is not a legal value.** This is
  a SYNTAX restriction, not encoder guidance: an encoder shall not emit it and a
  decoder shall reject a stream that carries it.

  *Why it is normative rather than advisory* (ruling 2026-09-05). 32 lines
  breaches A2 on the codec term alone at 720p50 (**1.794 ms**), 1080p50
  (**1.213 ms**) and 1080p60 (**1.011 ms**) against the 1 ms budget, so the
  prohibition already existed in prose. But **an encoder-only prohibition is not
  a bound.** Left advisory, a conformant decoder could be handed `slice_h = 32`
  at 1080p by any other encoder and would have to size its buffers for it — and
  decoder buffers scale linearly with `slice_h`, so that sizing is what decides
  whether the 8K memory budget fits the target part. At 16 it fits; at 32 it does
  not. Narrowing the syntax is what turns the prose into something a decoder can
  be built against.

  This supersedes two sentences that could not both be operative: *"an
  implementation that declares support for 32 must size for it"* and *"not a
  per-leg profile and not a conformance point"*. `slice_h` remains a coded stream
  parameter that every decoder reads and sizes itself from, and it is still not a
  per-leg profile — but its legal range now depends on the coded height, and that
  dependence IS a conformance point.

  **A2 interaction, stated so it is not discovered.** At 1080p50 with a vertical
  rescale in the decoder's output path, 16-line slices are refused by
  `omc_validate_config()` under the shipped conversion charge (1.069 ms). Without
  a conversion, 1080p50 at 16 lines is 0.775 ms and fits with margin. The refusal
  is the contract working, not a surprise; a facility that needs both must either
  run that leg at `--slice-h 8` or adopt the raster-clocked output converter
  (`writeups/NEW_IDEAS_08112026_TEST_REPORT.md` §2).
- Bit depth 8, 10, 12. Internal datapath fits 16-bit signed at 12-bit input with the
  documented +3-bit transform growth (see docs/HARDWARE.md).

## 8. Version 4.2 extensions (all bypassable; flags off = bit-identical 4.1 behavior)

Stream-header bytes [26, 32), previously reserved-as-zero, become:

| byte | field | values |
|---|---|---|
| 26 | scan_type | 0 = progressive (only defined value; 1 and 2 reserved for the deferred interlace convention — see docs/INTERLACE_CONVENTION.md. **This byte is NOT available for other use:** v4.8's `uc_ratio` deliberately lives in byte 27 rather than here, because 0/1/2 would have collided value-for-value with that convention) |
| 27 | pixel_flags | bit 0: RCT applied; bit 1 (minor ≥ 5): grain-fill signs come from the CORRELATED tile (§9.4); bit 2 (minor ≥ 7): grain-fill tile offsets are STATIC (§9.5); **bits 3-4 (minor ≥ 8): `uc_ratio` — 0 = none, 1 = 2×, 2 = 4×; bits 5-6 (minor ≥ 8): `tf_mode` — 0 = off, 1/2 = OMC-TF strength**; bit 7 reserved 0 |
| 28-29 | display_height (LE u16) | true picture height before padding; 0 = coded height |
| 30-31 | display_width (LE u16) | true picture width before padding; 0 = coded width |

A 4.1 decoder ignores these bytes (decodes the padded/coded picture without
crop or inverse RCT); a 4.2 decoder reading zeros behaves exactly as 4.1.

**Arbitrary picture dimensions (pad-and-crop).** A picture whose width or
height does not meet the alignment constraints of section 7 is coded at the
next compliant size; the encoder fills the extension columns/rows by edge
replication (last true column/row) before coding, and the decoder crops
output to display_width x display_height. Replicated extensions are smooth
and cost <1% of rate in typical geometries (measured per release).

**Mono / key channel (convention, not a chroma code).** Single-component
content (key/alpha channels, mono cameras) is carried as 4:2:2 with both
chroma planes constant at midscale (2^(depth-1)). Flat chroma planes code
to all-zero bands (measured overhead 0.3% at 2.0 bpp); the receiving
application uses plane 0 and discards chroma. A true 4:0:0 chroma code is
deliberately deferred until the overhead matters to a real deployment -
this convention needs no decoder change at all. Alpha delivery = one video
stream + one mono stream, frame-index-locked.

**RCT (pixel_flags bit 0).** For RGB content the encoder MAY apply the
reversible lossless transform (JPEG 2000 RCT, shifts/adds only). Planar
file/API order is R, G, B; coded planes are:

```
Y  = (R + 2G + B) >> 2       (plane 0)
Cb = B - G                    (plane 1, offset by 2^(depth-1) after transform)
Cr = R - G                    (plane 2, offset likewise)
inverse:  G = Y - ((Cb + Cr) >> 2);  B = Cb + G;  R = Cr + G
(Cb/Cr de-offset by 2^(depth-1) before the inverse; all values clamped to
[0, 2^depth - 1] on output)
```

Cb/Cr span depth+1 bits, so RCT streams promote the coded container two
depth steps: d-bit RGB (d <= 10) codes in a container of depth d+2 (8 -> 10,
10 -> 12; the header's depth field carries the CONTAINER depth, and RCT
implies component depth = container - 2). Plane offsets make all values
container-legal and symmetric about the container midpoint mid_c:

```
plane 0 = Y  + (mid_c - mid_in)      Y  in [0, 2^d)   -> centered +/- 2^(d-1)
plane 1 = Cb + mid_c                 Cb in (-2^d, 2^d) -> centered +/- (2^d - 1)
plane 2 = Cr + mid_c                 (likewise)
```

**RCT is restricted to component depths <= 10** so the container stays
within the validated 12-bit input class and the 16-bit internal datapath is
untouched (decision record: docs/MEDIA_SERVER_MARKET.md). The transform is
applied before encode and inverted after decode, outside the coding core;
4:4:4 chroma format is REQUIRED when RCT is set. Note the coding loss on
Cb/Cr in this container is identical in scale to coding them at component
depth - the promotion changes representation, not fidelity.

## 9. Version 4.3+ extensions (minors 3–7)

Stream-header minor is 7. Decoders reject minor > theirs; a 4.7 decoder decodes
all prior minors bit-exactly (the legacy entropy tables of §6 remain normative
for minor ≤ 3 streams).

### 9.1 Minor 3 — per-block motion field (optional, flagged per slice)

Bit 7 of the slice header's `n_steps` byte (always 0 in prior streams, since
the refinement schedule has **49** steps and 49 < 128, so bit 7 can never be
set by a step count) flags a **block motion field** between
the 48-byte header and the payload, `ceil(W/16)` bytes: per 16-luma-px block,
LSB-first, `[mode:1][dx+8:4][dy+4:3]`. `mode` 1 selects intra (mid)
composition for that block; offsets are full-pel displacements added to the
block's region vector (offsets halve with 4:2:2 chroma exactly as region
vectors do). The CRC covers header + field + payload; `used_bits` counts the
payload alone. Encoders emit the field only when some block departs from the
region vector; decoders of minor ≥ 3 must parse it.

### 9.2 Minor 4 — entropy model v2 (normative for minor ≥ 4 streams)

The coefficient-category context becomes a 16-state magnitude context:

```
q2(a) = 0 if a == 0, 1 if a == 1, 2 if a <= 3, else 3
ctx   = q2(|left_v|) * 4 + q2(|above_v|)
```

(v is the coded value: post-DPCM for LL, delta-domain for inter bands; the
row buffer carries q2 codes, 2 bits per column, reset per band per slice.)
The normative table set is `omc_tans_counts_v4[8][16][16]` (8 groups × 16
contexts, counts sum 1024) in src/tables_v4.c.inc, trained on the delivery
corpus; the slice-header group id (4 bits) selects a group, values 0–7.
tANS construction, state discipline, raw-bit layout and everything else in
§4.4–4.5 are unchanged. Minor ≤ 3 streams use the §6 legacy tables and the
binary-significance context exactly as before.

### 9.3 Encoder-only (non-normative) behaviours, v4.4–v4.7

These change only which coefficients the ENCODER quantizes to zero, or
which of several equally-legal signaled plans it picks; reconstruction
points, parsing and conformance are untouched. Any decoder of the
stream's minor decodes these streams with no knowledge of them.

- **Detail-band deadzone** (default ON; `--no-deadzone` to disable; auto-off
  under `--tune vmaf`): the zero zone of detail bands 4–9 widens from 1/2 to
  9/16 of a step (`q == ±1` demoted to 0 when `|c|·16 < 9·2^s`). One compare
  against a shifted constant per coefficient.
- **Grain-replace classifier v2** (`--grain-replace`, default OFF pending the
  blind-viewing gate): in motion-predicted slices only, a detail-band
  coefficient is classified *invisible grain* when BOTH hold —
  (1) scale vote: its coarser-scale parent magnitude is ≤ 2^(depth−9)
      (bands 7–9 → co-located level-2 band b−3 at (row>>1, col>>1);
       bands 4–6 → co-located level-3 region, band 3 at (row, col>>1)); and
  (2) temporal vote: it does not persist under motion compensation
      (eligible only if 2·|delta| ≥ |coef|; persistent energy is never
      eligible).
  For classified positions ONLY, the zero zone widens to a full step — and
  only `|q| == 1` values can be demoted, so large (edge/texture) coefficients
  are structurally untouchable. Demoted energy reconstructs through the
  normative grain fill (§4.6) at measured amplitude: nothing is flattened.
  The classifier never reads luminance and never touches LL or bands 1–3.
- **Grain-hold v3** (v4.7, REPORT §18.7–18.8, part of `--grain-replace`):
  adds a per-cell amplitude vote (|coef| < 3·2^(depth−7)), a per-slice-band
  grain-carpet vote (≥ 55 % small nonzero cells), a soft threshold (eligible
  coded values shrink by 1 step — 2 in bands ≤ 6 — capped), intra-slice
  classification for coarse bands (locked slices excluded), and a coarse-band
  fill-bit veto in flat-carpet slice-bands. All still encoder-side zeroing /
  fill-bit choices.
- **Plan hysteresis** (v4.7): an inter slice whose previous committed
  (Q, n_steps, partial) plan still fits its budget reuses it verbatim, and
  freezes its fill bits/gain codes. Any fitting signaled plan is legal.
- **Perceptual slice-budget allocation** (v4.7, default on): each slice's
  wire budget is capped by a weight from the previous frame's per-slice
  detail energy (max of luma and chroma shares, clamp [0.75, 1.5]× the
  nominal share). Pure rate-control policy inside the §7 banking bounds;
  the wire caps, exact-CBR closure and slice syntax are unchanged.

### 9.4 Minor 5 — correlated grain-fill sign tile (normative)

When stream-header pixel_flags bit 1 is set, §4.6's fill sign is read from a
second normative 256×256 tile instead of the white tile. Construction (both
ends, init-time): for each (y, x), sum the four white-tile signs of the 2×2
block at (y, x)…(y+1, x+1) (wrapping mod 256, +1 for bit set, −1 clear); the
correlated bit is 1 if the sum is positive (ties take the white tile's own
bit), then XOR'd with (x+y)&1 (checkerboard flip). The resulting field has
lag-1 correlation ≈ −0.33 horizontally/vertically and positive diagonally —
the measured signature of organic film grain (REPORT §17.3: cow −0.34,
couch −0.32); electronic noise (lag ≈ 0) keeps the white tile. Amplitudes,
gates, gains and offsets are unchanged, so idempotence and generation
behaviour are identical to §4.6. Encoders choose the tile per stream
(`--grain-corr`); decoders honor the header bit.


### 9.5 Minor 7 — static grain-fill tile (`pixel_flags` bit 2)

When stream-header byte 27 bit 2 is set (encoder flag `--fill-static`), the
grain-fill sign-tile offsets of §9.4 are computed with **f = 0** instead of
f = frame index mod 256, for every filled coefficient (all activity classes).
Slice/plane/band offset diversity is unchanged; amplitudes, gates, gain codes
and the §9.2 fill-bit rule are unchanged, so idempotence and the A4 lock are
unaffected (a static tile is a strict fixed point of the animated scheme).
Rationale (REPORT §18.7): the frame-animated tile re-injects temporal boil
into held flat regions — the viewer-visible "ants". Decoders of minor ≤ 6
never see this bit set (encoders only set it with minor 7); minor-7 decoders
reproduce minor ≤ 6 streams byte-exactly (verified against the pristine v4.6
reference build). All v4.7 grain-hold changes besides this bit are
encoder-side coding decisions and need no decode-side support.

## Annex A — Allocation tables (normative)

Complete and normative: a decoder implemented from this specification
alone needs nothing beyond these tables to derive per-band quantizer
shifts (§6). Source of record: src/alloc.c; transcribed mechanically.
Effective band shift = clamp(Q + omc_off[profile][plane][band]
(+ omc_off_c444[band] for chroma in 4:4:4), 0, 15), minus refinement
steps in omc_refine_order; LL is capped at OMC_LL_CAP.

Band order: LL5 HL5 HL4 HL3 LH2 HL2 HH2 LH1 HL1 HH1.

### A.1 omc_off[profile][plane][band]

| profile | plane | b0 | b1 | b2 | b3 | b4 | b5 | b6 | b7 | b8 | b9 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | Y | -4 | -3 | -3 | -2 | -1 | -1 | 0 | 0 | 0 | 1 |
| 0 | Cb | -4 | -3 | -3 | -2 | -1 | -1 | 0 | 0 | 0 | 1 |
| 0 | Cr | -4 | -3 | -3 | -2 | -1 | -1 | 0 | 0 | 0 | 1 |
| 1 | Y | -4 | -3 | -3 | -2 | -1 | -1 | -1 | -1 | -1 | 0 |
| 1 | Cb | -4 | -3 | -3 | -2 | -1 | -1 | 0 | 0 | 0 | 1 |
| 1 | Cr | -4 | -3 | -3 | -2 | -1 | -1 | 0 | 0 | 0 | 1 |
| 2 | Y | -4 | -3 | -3 | -2 | -1 | -1 | 0 | 0 | 0 | 1 |
| 2 | Cb | -4 | -3 | -2 | -1 | 0 | 1 | 2 | 2 | 2 | 3 |
| 2 | Cr | -4 | -3 | -2 | -1 | 0 | 1 | 2 | 2 | 2 | 3 |
| 3 | Y | -4 | -3 | -3 | -2 | -1 | -1 | -1 | -1 | -1 | 0 |
| 3 | Cb | -4 | -3 | -2 | -1 | 0 | 1 | 2 | 2 | 2 | 3 |
| 3 | Cr | -4 | -3 | -2 | -1 | 0 | 1 | 2 | 2 | 2 | 3 |

Profiles 0–1 are plane-fair (default); 2–3 are the luma-weighted pair
(encoder --tune vmaf). Within each pair the second is the texture variant.

### A.2 omc_off_c444[band] (added to chroma planes in 4:4:4)

| b0 | b1 | b2 | b3 | b4 | b5 | b6 | b7 | b8 | b9 |
|---|---|---|---|---|---|---|---|---|---|
| 0 | 0 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |

### A.3 omc_refine_order[] — (plane, band) pairs in order

Step i decrements shift[plane][band] of entry i by 1 (floor 0); the band
at entry n_steps takes the partial-chunk refinement (§3.2).

| step | plane | band | | step | plane | band |
|---|---|---|---|---|---|---|
| 0 | Y | 3 | | 25 | Cr | 3 |
| 1 | Y | 4 | | 26 | Cb | 4 |
| 2 | Y | 5 | | 27 | Cb | 5 |
| 3 | Cb | 3 | | 28 | Cr | 4 |
| 4 | Cr | 3 | | 29 | Cr | 5 |
| 5 | Cb | 4 | | 30 | Y | 6 |
| 6 | Cb | 5 | | 31 | Cb | 6 |
| 7 | Cr | 4 | | 32 | Cr | 6 |
| 8 | Cr | 5 | | 33 | Y | 7 |
| 9 | Y | 6 | | 34 | Y | 8 |
| 10 | Cb | 6 | | 35 | Cb | 7 |
| 11 | Cr | 6 | | 36 | Cb | 8 |
| 12 | Y | 7 | | 37 | Cr | 7 |
| 13 | Y | 8 | | 38 | Cr | 8 |
| 14 | Cb | 7 | | 39 | Y | 9 |
| 15 | Cb | 8 | | 40 | Cb | 9 |
| 16 | Cr | 7 | | 41 | Cr | 9 |
| 17 | Cr | 8 | | 42 | Y | 3 |
| 18 | Y | 9 | | 43 | Y | 4 |
| 19 | Cb | 9 | | 44 | Y | 5 |
| 20 | Cr | 9 | | 45 | Y | 6 |
| 21 | Y | 3 | | 46 | Y | 7 |
| 22 | Y | 4 | | 47 | Y | 8 |
| 23 | Y | 5 | | 48 | Y | 9 |
| 24 | Cb | 3 | | | | |

Total refinement steps (omc_refine_steps): 49.


## v4.8 (minor 8) — output conversion and the in-loop temporal filter

Two fields are added, both in byte 27's previously-reserved bits, and both zero
on every earlier stream — so byte 27 is unchanged for minor ≤ 7 and every
existing hash stands.

| field | bits | values |
|---|---|---|
| `uc_ratio` | 27[3:4] | 0 = no conversion (**the default**), 1 = 2×, 2 = 4× |
| `tf_mode` | 27[5:6] | 0 = filter off (**the default**), 1 / 2 = OMC-TF strength — **OMC-TF was deleted 2026-09-06 (Task G, legal review action 3); the field MUST be 0 and a nonzero value is a header error** |

The stream's minor is written **8 only when at least one of them is non-zero**,
so a stream that uses neither is byte-identical to the v4.7 encoder's output
and a pre-v4.8 decoder accepts it unchanged. A pre-v4.8 decoder presented with
a minor-8 stream rejects it at the existing version check rather than
misinterpreting the new bits.

**`uc_ratio` is a recommendation and conversion is OFF by default.** It tells a
decoder what output raster the encoder believes suits the material; it does not
oblige one. A decoder MAY override it from its own output-port configuration —
which is what a facility needs when the same feed drives an HD monitor and a
UHD switcher — and MUST perform no conversion at all when the field is 0 and no
local override is set. Conformance is defined on the pair *(stream, ratio)*:
given both, the output is bit-exact and hash-pinnable.

**`tf_mode` is normative, not advisory.** A decoder MUST apply the signalled
filter strength. The filter is in-loop, so a decoder that ignored it would
reconstruct a different picture from the encoder's own reference and drift
further with every frame, breaking `rt = 0` (C4). This is the reason the field
exists: without it the two ends cannot agree, and the tool could only ever be
deployed as a matched pair rather than as a documented bitstream feature (C8).

## Cross-slice boundary reconstruction (OMC_XSL, proposed minor 9)
Level 3 (proposed normative default at minor >= 9; experimental env knob in
this build): (a) the vertical level-1 lifting's d[-1] term for slice k > 0 is
r15 - 2*r14 + r13 of slice k-1's committed reconstruction (was: copy of
d[0]); (b) after inverse, row 0 receives a bounded continuity blend toward
(prev row 15 + row 1)/2, half-step, capped at +-4 codes (10-bit scale,
OMC_XSL_LIM); (c) when slice k reconstructs, slice k-1's row 15 receives the
mirrored averaging blend toward (its row 14 + k's row 0)/2, same cap,
applied to reference AND display on both sides. Slice 0 rows untouched.

**The blend cap is normative and rate-derived (minor 9).** The cap named
`OMC_XSL_LIM` above is not a constant: it is **8 codes (10-bit scale) below
0.75 bpp and 4 codes at or above it**, derived by both ends from fields the
stream header already carries:

```
px  = width * slice_h                      (luma samples per slice)
cap = (4 * bits_per_slice < 3 * px) ? 8 : 4        (exact integer comparison)
```

The comparison is exact integer arithmetic, so 0.75 bpp itself takes cap 4 by
definition and two implementations cannot round it differently. Both ends
derive the same value from the same header fields, so nothing new is signalled.
The cap scales with the *depth* of the codes, `cap * ((maxv + 1) >> 10)`, so it
means the same thing at 8, 10 and 12 bits.

Rationale (blind review of cap 4 / 8 / 16 at three rates; SESSION_LEDGER 2.3):
below 0.75 bpp the quantizer step at a slice seam exceeds what a 4-code blend
can repair and the seam reads as a visible horizontal line; at and above
0.75 bpp the wider blend over-smooths the boundary rows and costs fidelity for
no visible benefit.

**The cap is per-encoder-context state, never a process-wide global.** A
multi-channel server runs several contexts at different rates in one process; a
shared cap would let the last context created decide the blend for all of them
and produce a stream its own decoder does not reconstruct. Conformance requires
per-context derivation (`tests/test_cap.c` builds exactly that situation).

**The threshold counts CODED SAMPLES, not luma pixels.** A 4:2:2 picture carries
2 samples per luma pixel and a 4:4:4 picture carries 3, so at the same nominal
bpp a 4:4:4 stream is materially coarser — and it is coarseness the cap responds
to. Expressed on samples, the single reviewed threshold lands at **0.75 bpp for
4:2:2** (unchanged, byte-identical to the rule as originally approved) and
**1.125 bpp for 4:4:4**, which is the same picture coarseness. Both were
confirmed by eye (2026-08-12); the 4:4:4 arm was measured at +5.42 codes of seam
excess under the narrow cap against +3.10 under the wide one.

**Bit depth needs no term of its own** (measured 2026-08-12). The cap already
scales with depth in the reconstruction — `cap * ((maxv + 1) >> 10)`, so ±4 at
10-bit and ±16 at 12-bit are the same fraction of full scale. On identical
content coded at both depths, 12-bit measures *less* seam structure than 10-bit
at the same bitrate, and the cap choice barely registers at either. The
threshold is therefore a function of chroma format and rate only.

`OMC_XSL_LIM` remains available as an experimental override and is not part of
this specification.
Encoder and decoder MUST apply identical arithmetic (round-trip is verified
byte-exact). Rationale + measurements: band-fix memo §21-26 (boundary rows
carry 30-60% excess quantization noise; the eye integrates the ridge into a
visible border line; eye gate passed with this fix).

### XSL refresh barriers (A5, required)
(d) A slice takes NO cross-slice terms (levels 1-3 inert) on the frame in
which it is intra-refreshed ((fidx8 mod R) == (slice mod R)); (e) slice k
skips the deferred row-15 edit of slice k-1 when k-1 is refreshed in the
current frame. Both rules are derivable from the slice header and
configuration on both sides. Rationale: without them a lost slice's
concealment divergence rides the coupling indefinitely (measured: decay
stalls at ~10 codes and creeps one slice per cycle); with them, full
bit-exact recovery within one refresh-wave pass is restored (measured:
clean 6 frames after a mid-stream slice corruption, R=16).

### XSL barrier display blend (minor 9, decoder display path — 2026-08-11)
(f) The boundaries the refresh barriers leave raw are blended on the EMITTED
picture only: on the frame where slice k is refreshed, k's row 0 receives the
(b) blend and k-1's row 15 the (c) blend; on the frame where k-1 is refreshed
(rule (e) suppressed the deferred edit), k-1's row 15 receives the (c) blend.
Same arithmetic and ±4-code cap as (b)/(c); conditions derive from fidx8 and
the header's refresh R on both sides. The temporal reference, banking, lock
lattice and loss-containment loop never observe these edits (both call sites
run after the reference update; verified: containment heals byte-exact in one
refresh cycle with the blend active, and the encode loop's bitstream is
byte-identical with the blend compiled out). Rationale: bisection against the
eye-passed configuration put the entire visibility regression on the barrier
boundaries (step excess 3.1 → 6.6 codes; back to 3.3 with this). Debug
override: OMC_XSL_NODISP=1 disables (A/B only, not normative).

### Encoder-only allocation notes (no bitstream impact)
REFRESH BOOST (OMC_RBOOST=pct): intra-refreshed slices receive +pct% of B on
their allocation target/cap, funded by shaving non-refreshed slices; exact
CBR is unchanged (targets only). Measured at 50: refreshed slices reach
texture parity with neighbours (0.81 vs 0.79 luma, 0.39 vs 0.38 chroma
dec/src retention); beach@0.5 VMAF 95.21 vs XS@1.0 94.94. The tail guard
reserve is boost-aware (holds the bump for refreshed slices still ahead), and
tail guard / fill hysteresis gained tail-local modes (=2: last 8 slices only)
so mid-frame plans match the eye-passed allocator. These knobs are encoder
policy; any decoder decodes the result.
