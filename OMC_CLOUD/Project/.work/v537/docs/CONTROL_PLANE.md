# OMC control plane — the knob inventory

> **CURRENT AS OF v5.0.** The complete, generated inventory is the last section
> of this document; it is derived from the source and covers every knob the code
> reads. The hand-written tables that follow this note are the v4-era inventory,
> left as written, and they are **incomplete** — they were 59 knobs behind the
> code when v5 was assembled. Where the two disagree, the generated table is
> derived from the code and this one is not.

> **Release numbering — HISTORICAL, describes v4.9.** This was **OMC v4.9**. The codebase implements every
> feature through bitstream minor 9 (8 = upconversion / in-loop TF signaling,
> 9 = cross-slice boundary reconstruction: XSL level 3, refresh barriers,
> barrier display blend). Streams that use no post-7 feature are still written
> with minor **7** so they stay byte-identical to v4.7 encoders — the baseline
> minor is a compatibility floor, not the release number (`OMC_VERSION_MINOR`
> = 7, `OMC_RELEASE_MINOR` = 9). Mentions of v4.4–v4.7 elsewhere in the docs
> are historical records of when a feature landed and are intentionally left
> as written.


Functional spec for production-configuration software (the "engineer's
app") and for FPGA register-map design. Every knob below is an existing
codec parameter; validation rules are enforced by the shared
`omc_validate_config()` in the C library (src/config.c) — control-plane
software and firmware MUST use it (or a bit-exact port) so all layers
accept identical configurations. The machine-readable version of this
inventory is `docs/omc_config.schema.json`.

Reconfiguration semantics: OMC streams are exact-CBR with the
configuration carried in the 32-byte stream header. **Parameters change at
stream boundaries only** — applying a new configuration means ending the
stream and starting a new one (2-frame quality ramp to steady state,
measured invisible). There is no mid-stream renegotiation.

## 1. Format knobs

| knob | values | validation | notes |
|---|---|---|---|
| width | ANY 1..8192 (v4.2 pad-and-crop) | validator (coded dims) | odd LED-wall rasters supported; alignment handled internally |
| height | ANY 1..4352 (v4.2 pad-and-crop) | validator (coded dims) | 1080 native via slice_h 8 (auto) |
| chroma | 4:2:2, 4:4:4 | validator | equal-bpp comparisons stay like-for-like |
| bitdepth | 8, 10, 12 | validator | all three verified end to end |
| slice_h | 0 (auto), 8, 16 | validator | auto = 16 if height allows, else 8 |
| fps | num/den, nonzero | validator | informational for the codec (CBR is per-frame) |
| colorimetry | BT.709 / BT.2020; SDR / HLG (PQ refused since v5.3.6); limited/full | validator | signaled, not processed |
| source_format | ycbcr / rgb / mono (v4.2) | validator | rgb = lossless RCT, components <= 10-bit; mono = key/alpha convention |
| scan | progressive only | — | interlace deferred by product decision (design on the shelf: INTERLACE_CONVENTION.md); sales answer = "available on request" |

## 2. Rate knob

| knob | range | measured guidance |
|---|---|---|
| bits_per_slice (API) / bpp (human) | 0.3 bpp mechanical limit (NOT a product floor — the guarantees begin at 0.5 bpp; see HARDWARE 7b/7c) .. 24 bpp sanity cap | delivery point 2.0 bpp; XS-parity tiers: see REPORT 11i/11j ladders |

App presentation advice: engineers think in Mbit/s. Convert:
rate_Mbps = bpp x width x height x fps / 1e6; the app should display both.
Example anchors (1080p50 4:2:2): 2.0 bpp = 207 Mb/s; 0.8 bpp = 83 Mb/s.

## 3. Loss-recovery window (refresh_r) — measured cost table

Recovery after packet loss completes within R frames (verified). Cost at
2.0 bpp on the program feed (worst steady luma dB / worst VMAF):

| R | recovery @50fps | beach | couch | fencepan | cowpan | VMAF (beach/couch min) |
|---|---|---|---|---|---|---|
| 1 (stateless) | same frame | 46.24 | 52.39 | 53.77 | 52.05 | 96.54 / 97.18 |
| 2 | 40 ms | 47.28 | 53.06 | 54.83 | 53.00 | 96.36 / 96.89 |
| 4 | 80 ms | 48.06 | 53.48 | 55.86 | 54.44 | 96.35 / 96.83 |
| 8 (default) | 160 ms | 48.53 | 53.68 | 56.45 | 55.34 | 96.36 / 96.79 |
| 16 | 320 ms | 48.78 | 53.81 | 56.76 | 55.84 | — |

No refresh flicker at any setting (pulses <= 0.17 dB, an order below
visibility). VMAF is flat across the dial; the window buys PSNR headroom.

## 4. Mode knob (the two-definition claim, REPORT 12f)

| mode | flag | what it means | when to use |
|---|---|---|---|
| Perception (default) | fill on | grain energy regenerated, not transmitted; best to eyes; full-reference metrics read ~0.1-0.8 low by design | eye-judged services; blind-kit acceptance |
| Fidelity | --no-fill (**was silently inert until 2026-09-06**: the library forced the fill on whenever `OMC_FILL` was unset; fixed via `fill_grain_explicit`) | every reconstructed value from transmitted data | metric-gated contracts; audit windows |

Mode is observable from the stream (fill bits in slice headers) — an
auditor can verify the running mode without device access. Decoders need
no configuration; they honor whatever the stream says.

### 4a. Decoder concealment (decoder-side knob, not in the bitstream)

How a decoder fills a slice it could not decode (packet loss). Not a stream
parameter — it changes only what a decoder shows during the recovery window,
never the bits, and a clean stream decodes identically either way.

| mode | selection | behavior |
|---|---|---|
| MC + spatial (default) | decoder default / `omc_dec_set_conceal(d,1)` | project the reference along the nearest good inter neighbour's motion vectors, or (fully intra frame / frame 0) vertically interpolate between two survivors. +21 dB vs freeze on a coherent pan, +13.7 dB on frame-0 loss; verified >= freeze across a 48-position sweep (REPORT 15) |
| freeze (hold-last) | CLI `--no-conceal` / `omc_dec_set_conceal(d,0)` | hold the previous frame's pixels for the lost rows (the v4.1 behavior); simplest decoder SKU |

The concealment mode is a receiver choice; senders and the bitstream are

> **Task G (2026-09-06):** the "MC + spatial" mode is now **upward-only MC**: the nearest good
> inter neighbour ABOVE supplies the vectors; a fully-intra frame (or frame 0) FREEZES the lost
> rows. The downward searches and the spatial interpolation were deleted because they made a lost
> slice wait for every slice below it — (n−1)/n of a frame period, 16.4–19.9 ms at 720p50…2160p50,
> against a sub-1 ms product — and on an isolated loss both rules chose the same upward neighbour
> anyway (byte-identical on every cell). Motion-compensated concealment of fully-intra-frame losses
> from the previous frame's vectors is the open design item.
unaffected. The recovery *bound* (R frames) is set by the encoder's refresh
and is identical under either mode.

## 5. Encoder-only options

| knob | default | notes |
|---|---|---|
| tune | plane-fair | `vmaf` = luma-weighted allocation; caps fill gain at 1.25x (idempotence); also disables the deadzone (their biases cancel) |
| deadzone (`--no-deadzone` to disable) | **on** (v4.4) | 9/16 zero zone, detail bands only; +0.45 dB all planes measured; reconstruction points unchanged (decoder unaffected) |
| grain-replace (`--grain-replace`) | off | v4.7 grain-hold v3 (E-9): third amplitude vote, per-slice-band grain-carpet vote, parent threshold 8 (10-bit), soft-threshold coding; viewer-box ant-tail 18.0% (v4.4) -> 7.98% @2bpp (below fair JPEG XS 7.73%), 18.6% -> 10.7% @1.0bpp; no flattening (flat-block rate 0.08% = baseline); enable only after blind-viewing signoff (rev. 6). Details: REPORT 18.7, ENHANCEMENTS_LEDGER E-9 |
| fill-static (`--fill-static`) | off | v4.7 (bitstream minor 7, stream byte 27 bit 2): grain-fill sign-tile offsets frame-independent — static grain texture, no temporal animation; used e.g. for beach fine grain (67% retained + static fill). Zero new per-pixel multipliers on FPGA (one per-band static offset pair, same omc_fill_offsets with f=0). Details: BITSTREAM 9.5, ENHANCEMENTS_LEDGER E-10 |
| block-mv (`--block-mv`) | off | per-block motion field (bitstream minor 3); measured ~0 on the delivery corpus - experimental capability |
| xsl level 6 (`OMC_XSL=6`) | — | **seam-keyed continuous blend.** Levels 4/5 scale the blend by how empty the slice's detail band is, which measured backwards: busy slices get almost no blend and busy slices are where the seam is worst (city @0.5: unrepaired 19.25, level 3 → 9.51, level 4 → 17.00). Level 6 scales it by the seam itself — the step across the join minus the picture's own steps either side — continuously, per slice boundary, per plane, every frame. Repairs as well as level 3 (within 0.3 codes on all nine clip/rate points) and cuts the worst generation loss from −4.66 to −3.34 dB. Cut-proof by construction; both ends derive it from reconstructions they both hold, so no signalling and no bitstream change. `rt = 0` byte-exact at 4:2:2 and 4:4:4, 10- and 12-bit, slice_h 8 and 16 |
| xsl (`--xsl auto\|0\|3`) | off (env `OMC_XSL`) | cross-slice boundary reconstruction. **`auto`** encodes frame 0 once with XSL off, measures the seam step it would repair, and switches XSL on only above 3 codes @10-bit — carried by the existing stream minor, no new field. Rationale: the seam is worth repairing at low rate and gone by 2.0 bpp, while XSL costs 2–4.7 dB across six generations exactly where the seam has gone (it puts the reconstruction off the quantiser lattice and the generation lock stops firing). Measured: `auto` removes every generation loss above 1.2 dB and keeps the seam fix wherever the seam is visible |
| mv_regions | off | per-region/half-pel search: single-hop links only (generations reconverge instead of replaying; DESIGN.md 1b) |
| lossless (--lossless) | off | lossless-preferred: bit-exact per frame when it fits the CBR budget, graceful lossy fallback otherwise (still exact-CBR); per-frame bit-exact status reported; implies no_fill; default ceiling 16 bpp. REPORT 14. Crossover: clean <=2 bpp, grain ~9 bpp (vs XS 4 / >11.9). |

### 5a. Grain-replace env overrides (experimental/diagnostic tier — NOT stable API)

Environment knobs that override the v4.7 grain-hold v3 defaults inside
`--grain-replace`. Diagnostic use only; not part of the stable API and not
surfaced in omc_config.schema.json. Encoder-only policy — decoders are
unaffected.

| knob | default (v4.7) | meaning |
|---|---|---|
| OMC_GR | — | master grain-replace control |
| OMC_GR_PTHR | 8 | parent threshold (10-bit) |
| OMC_GR_SOFT | 1 | soft-threshold coding (eligible coded deltas shrink 1 step) |
| OMC_GR_CARPET | on | per-slice-band grain-carpet vote (>= 25% small nonzero cells) |
| OMC_GR_LLTHR, OMC_GR_SOFT_COARSE, OMC_GR_INTRA, OMC_FILL_VETO_COARSE, OMC_GR_DZOFF | off (gate removed) | LL-gradient gate threshold |
| `OMC_PLAN_HYST` | **3** (v5.3.5; was 0 outside grain-replace) | plan-hysteresis level (sect.B2: the shipped config replanned 99.5% of non-refresh slices every frame on a frozen source — the plan-search limit cycle is the largest single crawl carrier). 3 = STATIC-SLICE HOLD: keep the previous committed plan iff the profile matches and est(old) ≤ budget×OMC_PLAN_STATIC/100. 1 = v4.7 reuse-if-fits: grain-replace only, ship-falsified as a default (mean NEG −0.55, cf_gfx@0.5 −7.13). 2 = pin outright: DIAGNOSTIC ONLY (−1.00 NEG, breaks grain-replace locks). 0 in the v5.0 restore incantation. |
| `OMC_PLAN_STATIC` | **35** | the level-3 static line, percent of budget. Measured separation: static slices 14–35%, moving content 77–98%; 50 clipped real grain on dng@0.5 (−0.10 NEG), 35 is byte-neutral there. |
| `OMC_RBOOST` | **50** (v5.3.5; was 0 — and the mechanism was DEAD CODE under default R until §B2.6's guard fix) | refreshed slices get +pct% of B, funded by shaving the others; CBR-neutral. |
| `OMC_PLANSD` | 0 | §38.5 distortion-scored plan choice, ||g||₂-weighted, 2% margin, repair-excluded. FALSIFIED AS DEFAULT (reopens chroma classes, §B3.4b); lever retained. |
| `OMC_TPART` | 0 | targeted partial chunks (LL-gradient rank selector). Falsified as engaged (§B3.5c: the refine order dictates the band); selector retained for PBAND. Forced 0 when OMC_FILLRUNG=0. |
| OMC_GR_QMAX | 3 | amplitude vote bound (\|coef\| < 3 x 2^(bitdepth-7)) |
| OMC_GR_SOFTCAP | 3 | soft-threshold cap (\|q\| <= 3) |

## The grain-fill control plane (v5.2)

Every value below is the **compiled-in default** in `src/codec.c`; the codec
requires no environment to reach it. Regenerated from the source on 2026-08-27.

| variable | default | meaning |
|---|---|---|
| `OMC_FILL` | on unless `lossless_pref` | master grain-fill switch. `OMC_FILL=0` is half of the v5.0 restore |
| `OMC_FILLDIV` | **2** | **luma** fill-amplitude halvings. Amplitude is `1 << (s - 2 - div)`, so 2 is a 1/16-step fill |
| `OMC_FILLDIV_C` | **1** | **chroma** fill divisor, new in v5.2. `-1` follows `OMC_FILLDIV`. Chroma flatness lives in the `base_s` 4–5 bands, which divisor 2 refuses outright |
| `OMC_FILLTHR` | **1** | fill-bit threshold in sixteenths of a step. **Must not be 0** — 0 makes the test vacuous, lets near-zero-energy bands fill, and **breaks A4** |
| `OMC_FILLINTRA` | **0** | the fill latch. 1 restricts fill to intra bands; measured worse on every arm and does not reduce crawl |
| `OMC_ANTSGATE` | **0** | LL-activity floor for the fill. 24 and 48 both cost chroma flatness and bought no crawl improvement |
| `OMC_FILLPLANE` | 7 | bitmask of planes the fill may run on |
| `OMC_FILLGAIN_MAX` | 3 | fill amplitude ceiling; inert, the derived gain is already at minimum |

### Default-off switches retained as evidence for falsified approaches

| variable | default | why it is off |
|---|---|---|
| `OMC_DIVEFF` | 0 | per-band divisor keyed on the shift `s`. Reaches 0.00 % on two arms but **fails `G-T5-CALM2a/2b`**: the calm kill moves `s` between generations and the divisor's clamp makes the amplitude non-linear in `s`, breaking the gain fixed point |
| `OMC_FILLMIN1` | 0 | admits an amplitude of 1 code so the global divisor reaches `s = 4`. **5 gate failures**; reproduces the v4.6 taper defect |
| `OMC_GM_KEEPFILL` | 0 | stops the in-gamut repair vetoing fill for a whole band. Takes `dng` luma **16.76 % → 0.07 %** with `oob = 0`, and **fails A4 at generation 2 on every cell** — the veto is a convergence device |
| `OMC_ODCAP` | 0 | restores the half-slice banking overdraft. +0.002…+0.710 VMAF-NEG at unchanged byte count, but costs up to **+0.185 ms** of the A2 budget. Rejected: no latency change is permitted |

**The invariant these establish.** Any quantity the fill amplitude is keyed on
must not change between generations. The **plane index** does not. The
**quantiser shift `s`** and the **band mode** do. `OMC_FILLDIV_C` is keyed on the
plane, which is why it holds where `OMC_DIVEFF` does not.

### Restore v5.0 exactly

```
OMC_FILL=0 OMC_FILLINTRA=0 OMC_ANTSGATE=24 OMC_FILLTHR=3 OMC_FILLDIV=0 OMC_FILLDIV_C=-1
```

Asserted mechanically by gate `G-T5-RESTORE` against
`delivery/conformance/vectors/c5_v50_restore_rail.omc`.

Legacy v4.6 behavior is reproducible byte-exactly with
`OMC_GR_SOFT=0 OMC_GR_PTHR=2 OMC_GR_CARPET=0 OMC_GR_LLTHR=24`. Minor <= 6
streams decode byte-identically (verified against a pristine v4.6 build).

## 6. Telemetry the FPGA should export (per QOE_MONITORING.md)

- slice CRC failure count, concealment-row count, resync count
- exact-CBR conformance (stream bytes == 32 + n x F)
- per-stream config readback incl. mode observability
- decoder final-state (tANS desync) error count

Alarm policy: structural counters alarm on any increment; full-reference
quality metrics must NOT gate Perception-mode links (they false-alarm by
design) — trend them, don't threshold them.

## 7. Suggested presets (annotated with measured numbers)

| preset | config | evidence |
|---|---|---|
| Contribution, clean network | 2.0 bpp, R=8, Perception | worst steady VMAF >= 96.4, blind-stills clean; REPORT 2/12e |
| Contribution, lossy network | 2.0 bpp, R=2, Perception | 40 ms recovery, -0.6..-2.3 dB vs R=8, VMAF flat; REPORT 12e |
| Metric-audited service | 2.0-2.4 bpp, R=8, Fidelity | instruments mean what engineers expect; REPORT 12f |
| Max-compression feed | 0.8 bpp, R=2, Perception | transport-tier quality at 0.4x XS-tier rate; REPORT 11i/11j |
| XS-architecture drop-in | any rate, R=1, either mode | stateless, no frame store, XS equal-rate parity; REPORT 12e |
| Lossless-preferred | --lossless, high bpp (>=10 for grain, >=3 clean) | mastering/archival/graphics; bit-exact when budget allows, CBR always, per-frame verified; REPORT 14 |

## 8. NMOS integration note

For ST 2110 facilities the app should surface OMC flows through AMWA NMOS
(IS-04 discovery / IS-05 connection), mirroring how BCP-006-01 integrates
JPEG XS. The parameter schema in omc_config.schema.json is written to map
onto NMOS flow/sender attributes; a BCP-style profile document is future
work, gated on the bitstream freeze.

---

## Complete knob inventory, generated from the source (v5.0)

**Why this section exists.** The hand-written tables above had fallen 63 knobs behind the code. This section is **generated** by scanning every
`getenv("OMC_...")` in `src/` and `tools/` and pairing it with the nearest
explanatory comment, so it cannot drift again. Knobs marked **NEW** were absent
from the hand-written inventory.

Everything here is an **instrumentation and A/B knob**, not a product control.
None of it is required to run the codec, and no knob the *decoder* sees affects
a reconstruction. Product controls are CLI flags and `omc_config_t` fields,
documented in `README.md` and `docs/OMC_V5.md`.

**75 knobs.**

| knob | first read at | what it is |
|---|---|---|
| `OMC_ALLOC` **NEW** | `src/codec.c:1440` | v4.7 rev8 default ON (REPORT 18.9); OMC_ALLOC=0 reproduces rev3 byte-exactly |
| `OMC_BANDTILT` **NEW** | `src/codec.c:1435` | and "no amplitude is too large"; nothing useful lives above it. |
| `OMC_CALM` **NEW** | `src/codec.c:1385` | (no adjacent comment; see the code) |
| `OMC_CALM_AMP` **NEW** | `src/codec.c:1387` | (no adjacent comment; see the code) |
| `OMC_CALM_THR` **NEW** | `src/codec.c:1386` | (no adjacent comment; see the code) |
| `OMC_CHROMABIAS` **NEW** | `src/codec.c:1439` | (no adjacent comment; see the code) |
| `OMC_DCFB` **NEW** | `src/codec.c:1449` | (no adjacent comment; see the code) |
| `OMC_DCFB_DBG` **NEW** | `src/codec.c:2764` | On lattice input (generation 2+) every residual is 0 and this is inert. |
| `OMC_DCFB_STAT` **NEW** | `src/codec.c:4183` | no longer buys the attempt, drop to zero directly |
| `OMC_DEBUG_LOCK` **NEW** | `src/codec.c:3804` | (no adjacent comment; see the code) |
| `OMC_DEBUG_MV` **NEW** | `src/codec.c:3224` | integer-pel: even half-pel codes |
| `OMC_DEBUG_SIZES` **NEW** | `src/codec.c:4653` | CRC over header (sans CRC field) then payload |
| `OMC_DEBUG_VERIFY` **NEW** | `src/codec.c:2620` | (no adjacent comment; see the code) |
| `OMC_DEBUG_VERIFY2` **NEW** | `src/codec.c:2696` | was fill_static; inert since minor 12 */, 0, &vfp); |
| `OMC_DEBUG_VTRIES` **NEW** | `src/codec.c:3762` | contract, which outranks encoder timing. |
| `OMC_DUMP` **NEW** | `src/codec.c:4244` | (no adjacent comment; see the code) |
| `OMC_DUMP_COEF` **NEW** | `src/codec.c:3035` | debug: dump this slice's transform coefficients (OMC_DUMP_COEF=<pfx>) |
| `OMC_DUMP_COMMITTED` **NEW** | `src/codec.c:5712` | target the un-blend must recover (OMC_DUMP_COMMITTED=<prefix>) |
| `OMC_DZ` **NEW** | `src/codec.c:1379` | (no adjacent comment; see the code) |
| `OMC_ENC_FOOTPRINT` **NEW** | `src/codec.c:1496` | tables allocated here, before the baseline |
| `OMC_FILLBANDS` **NEW** | `src/codec.c:1438` | (no adjacent comment; see the code) |
| `OMC_FILLCORR` **NEW** | `src/codec.c:1437` | (no adjacent comment; see the code) |
| `OMC_FILLCORR_STAT` **NEW** | `tools/omc_dec.c:222` | (no adjacent comment; see the code) |
| `OMC_FILLHYST` **NEW** | `src/codec.c:1458` | it would silently break the generation-exactness contract. |
| `OMC_FILL_VETO_COARSE` | `src/codec.c:1444` | v4.7 rev8 default ON (REPORT 18.9); OMC_ALLOC=0 reproduces rev3 byte-exactly |
| `OMC_FORCE_PROF` **NEW** | `src/codec.c:3825` | probe: isolate profile |
| `OMC_GAMUT_STAT` **NEW** | `src/codec.c:4828` | (no adjacent comment; see the code) |
| `OMC_GAMUT_STRICT` **NEW** | `src/codec.c:1594` | OMC_GAMUT_STRICT=0, or --gamut-strict 0, to turn it off. **v5.3.6: the default per-slice budget `OMC_GAMUT_DEFPASS` is 13 passes (was 12; `docs/TEMPORAL_T5.md` v5.3.6 addendum).** **v5.3.7: this is the budget of ONE attempt. The per-slice TOTAL across restarts and redos is now capped and ENFORCED at `(3 + omc_gm_redomax) x gamut_strict` = 52; the cap follows this lever, so lowering the budget lowers the cap with it.** |
| `OMC_GM_ALIGN` **NEW** | `src/codec.c:1395` | (no adjacent comment; see the code) |
| `OMC_GM_DEN` **NEW** | `src/codec.c:1424` | (no adjacent comment; see the code) |
| `OMC_GM_DIL` **NEW** | `src/codec.c:1388` | (no adjacent comment; see the code) |
| `OMC_LOCK_TIEACT` **NEW (sect.B5.5)** | `src/codec.c` | generation-lock tie-break by ACTUAL trial size for bands both modes reproduce (was: cost estimate, which omits the Q5 skip-flag symbol -> +1 byte -> later slice starved of its plan). Default `1`; `0` = old tie-break (in the restore incantation). |
| `OMC_GM_DILFROM` **NEW (sect.51.21)** | `src/codec.c` | staged repair dilation: passes < DILFROM repair the exact support only; dilated reach joins for persisting pixels (fallback restart: full reach at once). Default `2`; `0` = pre-51.21 bytes (in the restore incantation). |
| `OMC_GM_DTHR` **NEW** | `src/codec.c:1393` | (no adjacent comment; see the code) |
| `OMC_GM_ESC` **NEW** | `src/codec.c:1397` | (no adjacent comment; see the code) |
| `OMC_GM_ESC2` **NEW** | `src/codec.c:1402` | (no adjacent comment; see the code) |
| `OMC_GM_ESC2DEN` **NEW** | `src/codec.c:1404` | (no adjacent comment; see the code) |
| `OMC_GM_ESC2NUM` **NEW** | `src/codec.c:1403` | (no adjacent comment; see the code) |
| `OMC_GM_ESCDEN` **NEW** | `src/codec.c:1399` | (no adjacent comment; see the code) |
| `OMC_GM_ESCNUM` **NEW** | `src/codec.c:1398` | (no adjacent comment; see the code) |
| `OMC_GM_FALLBACK` **NEW** | `src/codec.c:1400` | (no adjacent comment; see the code) |
| `OMC_GM_GRADE` **NEW** | `src/codec.c:1413` | (no adjacent comment; see the code) |
| `OMC_GM_K` **NEW** | `src/codec.c:1415` | (no adjacent comment; see the code) |
| `OMC_GM_LLHOLD` **NEW** | `src/codec.c:1389` | (no adjacent comment; see the code) |
| `OMC_GM_MODE` **NEW** | `src/codec.c:1390` | (no adjacent comment; see the code) |
| `OMC_GM_NOINTRA` **NEW** | `src/codec.c:1391` | (no adjacent comment; see the code) |
| `OMC_GM_NUM` **NEW** | `src/codec.c:1423` | (no adjacent comment; see the code) |
| `OMC_GM_REPLAN` **NEW** | `src/codec.c:1392` | (no adjacent comment; see the code) |
| `OMC_GM_STAT` **NEW** | `src/codec.c:1419` | (no adjacent comment; see the code) |
| `OMC_GM_TRIAL` **NEW** | `src/codec.c:1414` | (no adjacent comment; see the code) |
| `OMC_GM_VETO` **NEW** | `src/codec.c:1396` | (no adjacent comment; see the code) |
| `OMC_GM_WATCH` **NEW** | `src/codec.c:1394` | (no adjacent comment; see the code) |
| `OMC_GR` | `src/codec.c:1380` | (no adjacent comment; see the code) |
| `OMC_GR_CARPET` | `src/codec.c:1447` | (no adjacent comment; see the code) |
| `OMC_GR_DZOFF` | `src/codec.c:1441` | v4.7 rev8 default ON (REPORT 18.9); OMC_ALLOC=0 reproduces rev3 byte-exactly |
| `OMC_GR_FILLVETO` **NEW** | `src/codec.c:1384` | (no adjacent comment; see the code) |
| `OMC_GR_INTRA` | `src/codec.c:1443` | v4.7 rev8 default ON (REPORT 18.9); OMC_ALLOC=0 reproduces rev3 byte-exactly |
| `OMC_GR_LLTHR` | `src/codec.c:1446` | v4.7 rev8 default ON (REPORT 18.9); OMC_ALLOC=0 reproduces rev3 byte-exactly |
| `OMC_GR_NOTEMP` **NEW** | `src/codec.c:1383` | (no adjacent comment; see the code) |
| `OMC_GR_PTHR` | `src/codec.c:1381` | (no adjacent comment; see the code) |
| `OMC_GR_QMAX` | `src/codec.c:1382` | (no adjacent comment; see the code) |
| `OMC_GR_SOFT` | `src/codec.c:1445` | v4.7 rev8 default ON (REPORT 18.9); OMC_ALLOC=0 reproduces rev3 byte-exactly |
| `OMC_GR_SOFTCAP` | `src/codec.c:1448` | (no adjacent comment; see the code) |
| `OMC_GR_SOFT_COARSE` | `src/codec.c:1442` | v4.7 rev8 default ON (REPORT 18.9); OMC_ALLOC=0 reproduces rev3 byte-exactly |
| `OMC_LAT_PROBE` **NEW** | `src/codec.c:3562` | every band whose lattice test fails on this slice |
| `OMC_PLAN_HYST` | `src/codec.c:1434` | and "no amplitude is too large"; nothing useful lives above it. |
| `OMC_PLAN_STAT` **NEW** | `src/codec.c:4619` | (no adjacent comment; see the code) |
| `OMC_RBOOST` **NEW** | `src/codec.c:1459` | it would silently break the generation-exactness contract. |
| `OMC_RECOFF` **NEW** | `src/codec.c:1436` | (no adjacent comment; see the code) |
| `OMC_SPC` **NEW** | `src/codec.c:1456` | it would silently break the generation-exactness contract. |
| `OMC_STAT_ATTEMPTS` **NEW** | `src/codec.c:4110` | peek before finish |
| `OMC_TAILGUARD` **NEW** | `src/codec.c:1457` | it would silently break the generation-exactness contract. |
| `OMC_TF` (validator REMOVED with OMC-TF, 2026-09-06) | `src/config.c:165` | a validator that silently does nothing is worse than no validator. |
| `OMC_TRACE` **NEW** | `src/codec.c:6005` | the encoder's OMC_DUMP symbol stream these bracket every stage. |
| `OMC_TRACE_FRAME` **NEW** | `src/codec.c:6006` | the encoder's OMC_DUMP symbol stream these bracket every stage. |
| `OMC_TRACE_SLICE` **NEW** | `src/codec.c:6007` | the encoder's OMC_DUMP symbol stream these bracket every stage. |
| `OMC_ZERO_BANDS` **NEW** | `src/codec.c:3435` | of flat-region flicker (REPORT 18.6). Not a product knob. |


---

# v5.1 — the in-gamut repair's control surface

*Added 2026-08-25. Every lever here is **encoder-side only**: none of them
changes decoder reconstruction of a fixed stream, so none is a normative leak of
the class finding F-15 records. All are default-on except where marked, and
clearing all of them reproduces a v5.0 encoder BYTE-IDENTICALLY (verified).*

## Shipped, default-on

| lever | default | what it does |
|---|---|---|
| `OMC_GM_PLANRESET` | `1` | every repair pass, and the converging restart, re-enter the encoder on the slice's own PRE-repair quantiser rung. `0` restores v5.0's ratchet |
| `OMC_GM_INTRAEVID` | `1` | a band is forced to intra only after a pass that removed no violations (the inter-inheritance signature). `0` forces it unconditionally, as v5.0 did |
| `OMC_GM_INTRAFROM` | `4` | the earliest pass at which the intra force may fire at all. v5.0 = `1` |
| `OMC_GM_LLCAP` | `-2` | the LL band's DC excursion bound in picture codes. `-2` (shipped) means **half the LL band's own largest quantiser step** — `(1 << OMC_LL_CAP)/2`, scaled to the depth — which is below what the lattice can express, so the LL is effectively pinned. `-1` means the XSL blend cap itself (the development bound). `0` disables the bound (v5.0) |
| `OMC_GM_HARDMIN` | `5` | the smallest remaining violation for which the converging RESTART may fire. Below it the slice is nearly finished and restarting only re-grinds twelve passes of detail reduction. `1` = v5.0 |
| `OMC_GM_DETFLOOR` | `0` | **measured, not shipped**: floor a detail-band reduction at N % of the untouched magnitude. Prevented convergence and drove more slices to the unbounded redo; worse at every value tried (10/25/40/50 %) |
| `OMC_GM_LLBND2FROM` | `-1` | **measured, not shipped**: make tier 2 of the boundary allowance available from an earlier pass. Decisively worse at every value (blocks past 40 codes 17 → 89…248), because the level move is expensive and reaching for it sooner spends it more often |
| `OMC_GM_LLHARD` | `2` | `2` = the bound never stands down except through the boundary rows' allowance below; `1` = it also stands down on the converging restart's second escalation; `0` = v5.0 (no bound on the escalated path) |
| `OMC_GM_LLBND` | `2` | tier 1 of the boundary allowance: the two LL band rows whose support touches a slice boundary may exceed the bound by this factor, because their reach to the previous slice's last row is attenuated by 4 |
| `OMC_GM_LLBNDFROM` | `8` | the pass from which tier 1 applies. A blanket allowance measured worse — it licenses a bigger move on every boundary row rather than on the few that need one |
| `OMC_GM_LLDENSE` | `10` | tenths of a per cent: a slice out of range over at least this fraction of its own area has its LEVEL wrong, so the bound does not apply to it. This is what keeps the pathological rail-on-boundary gates closing to zero |
| `OMC_GM_INTERABS` | `2` | **shrink the RECONSTRUCTION, not the residual, on inter bands**: `new_dcoef = dcoef - (coef - reduced_coef)`, so `pcoef + new_dcoef == reduced_coef`. Removes the intra force's bit demand at CONSTANT RATE — with it on, turning the force off entirely still commits zero out-of-range samples. `2` = DETAIL BANDS ONLY (shipped): the LL keeps v5.0's rule because it is the only band whose move reaches the previous slice's last row through the clamped XSL term, and changing it leaves one residual sample on two pathological gates. `1` = all bands (measured better on real footage, fails those two gates). `0` = v5.0 |
| `OMC_GM_VETO` | `1` | **alignment veto: refuse a reduction whose synthesis basis pushes some covered pixel FURTHER out of range.** `1` (shipped) refuses every misaligned reduction; `2` (v5.0) refuses only the ones the damage model calls expensive; `0` disables the test. **Its default changed in v5.1 and the reason is worth reading before touching it:** `1` was measured on the pre-`INTERABS` build and correctly REJECTED as harmful. `OMC_GM_INTERABS` then changed what a reduction displaces — the reconstruction rather than the residual — so the alignment test began answering the question it was written for, and `1` became better on every instrument (VMAF-NEG 88.017 → 88.192, repair footprint 2.174 → 1.615, frame-to-frame flicker sd 0.804 → 0.638, level blocks past 20 codes 43 → 24). Ledger §51.16 |
| `OMC_GM_LOOPNEED` | `6` | passes of the budget an **unlocked** slice may spend chasing the blend-cap margin on its boundary rows, so the next slice never has to make the ×4-attenuated correction. Only unlocked slices, which is what keeps generation exactness. Raised from 4 to **6** with `OMC_GM_INTERABS`: 2160p blocks past 40 codes 18 → 1, 8K 5 → 2 |

## Present, measured, NOT shipped (default-off)

Each was built and measured during the §51 investigation and rejected; the
measurement that killed it is in `docs/OMC_V5_1.md` §8 and in the project ledger
§51.7.

| lever | default | why it is off |
|---|---|---|
| `OMC_GM_LLPROP` | `0` | least-norm LL bound sized by the mean excess over the support. Saturated at ~110 residual out-of-range samples at every setting: never converged |
| `OMC_GM_LLSTEP` | `0` | LL reduced by exactly N quantiser steps per pass instead of a proportion. Converges only at N ≥ 4, by which point the level move is as large as the proportional rule's |
| `OMC_GM_LLREL` | `0` | release the bound on the final N passes. No measurable effect: the slices that need it are in the restart, where the pass counter has been reset |
| `OMC_GM_LLREACH` | `0` | bound the boundary release at N × the blend cap on the argument that beyond 4 × cap it cannot reach the neighbour. True for the neighbour, false for the row's own slice — broke convergence at every N |
| `OMC_GM_LLGIVE` / `OMC_GM_LLGIVE2` | `0` / `0` | give the bound up after a restarted pass that removed nothing / near budget exhaustion. Superseded by the density escape, which is a property of the CONTENT rather than of the search |
| `OMC_GM_LLBND2` | `0` | bound tier 2 at N × the bound. Left one residual sample at every N; `0` (unbounded on the final pass, two band rows, one pass) is what makes the guarantee unconditional |

| `OMC_GM_DROPINTRA` | `0` | measured, not shipped: drop the intra force rather than a quantiser rung when an attempt overflows. Blocks past 40 codes 8 -> 13 |
| `OMC_GM_INTRASTICKY` | `1` | `0` re-derives the intra force each pass instead of accumulating it. Measured much worse (8 -> 94) |
| `OMC_GM_REDOMAX` | `1` | how many times the unbounded redo may fire on one slice. Worst-case per-slice work is **`(3 + this) x gamut_strict`** — 52 at the shipped defaults — and from v5.3.7 that bound is ENFORCED by a per-slice total-pass counter, not merely documented. *(This row said `(1 + this)` until 2026-09-08; that formula omitted the SD-revert and harsh-rule-fallback restarts, and ordinary footage exceeded it — Agent 5's 2026-09-05 correction, `src/codec.c` `omc_gm_redomax` comment.)* |
| `OMC_GAMUT_TOTALCAP_PROBE` | unset | **TEST PROBE — never set in production.** Replaces the enforced total-pass cap with the given value so a gate can prove the cap is reachable (G-T5-CAP1). Encoder-only: the decoder never reads it, so it is not normative and carries no freeze-list entry. It is not a user control and cannot be used to *raise* the cap in any shipped path. |
| `OMC_GM_RETRO` | `1` | `0` stops charging a previous-slice boundary violation to this slice. Slightly better picture, one residual out-of-gamut sample. Kept at v5.0 behaviour |

## DIAGNOSTIC ONLY — never a ship setting

| lever | what it does |
|---|---|
| `OMC_GM_BANDHOLD` | bitmask of bands the repair may not touch. **It can leave a slice out of gamut and break A4.** It is the instrument that attributed the artifact to band 0 (`docs/OMC_V5_1.md` §3.1) and it exists so that attribution can be re-run |
| `OMC_GAMUT_STAT` | per-slice, per-pass repair trace on stderr, extended in v5.1 with the excursion depth (`deep=`) and total depth (`dsum=`), plus an `UNFIXED` line per residual sample |

## Every in-gamut-repair lever and its compiled default (generated, v5.1)

*Generated mechanically from `src/codec.c` so it cannot drift. Regenerate with*

```python
import re
src = open('src/codec.c').read()
pat = re.compile(r'omc_gm_(\w+)\s*=\s*getenv\("(OMC_GM_\w+)"\)\s*\?\s*atoi\(getenv\("OMC_GM_\w+"\)\)\s*:\s*(-?\d+);')
for m in pat.finditer(src): print(m.group(2), '=', m.group(3))
```

| lever | default | era |
|---|---|---|
| `OMC_GM_DIL` | `1` | v5.0 and earlier |
| `OMC_GM_DILFROM` | `2` | `0` restores pre-51.21 behaviour byte-for-byte |
| `OMC_LOCK_TIEACT` | `1` | `0` restores the estimate tie-break byte-for-byte |
| `OMC_GM_LLHOLD` | `0` | v5.0 and earlier |
| `OMC_GM_BANDHOLD` | `0` | v5.0 and earlier |
| `OMC_GM_LLCAP` | `-2` | **v5.1** |
| `OMC_GM_LLPROP` | `0` | v5.0 and earlier |
| `OMC_GM_LLSTEP` | `0` | v5.0 and earlier |
| `OMC_GM_INTRAFROM` | `4` | **v5.1** |
| `OMC_GM_LLHARD` | `2` | **v5.1** |
| `OMC_GM_LLREL` | `0` | v5.0 and earlier |
| `OMC_GM_PLANRESET` | `1` | **v5.1** |
| `OMC_GM_INTRAEVID` | `1` | **v5.1** |
| `OMC_GM_LLBND` | `2` | **v5.1** |
| `OMC_GM_LLREACH` | `0` | v5.0 and earlier |
| `OMC_GM_LLGIVE` | `0` | v5.0 and earlier |
| `OMC_GM_LLGIVE2` | `0` | v5.0 and earlier |
| `OMC_GM_LLDENSE` | `10` | **v5.1** |
| `OMC_GM_LOOPNEED` | `6` | **v5.1** |
| `OMC_GM_LLBNDFROM` | `8` | **v5.1** |
| `OMC_GM_RETRO` | `1` | v5.0 and earlier |
| `OMC_GM_LLBND2` | `0` | v5.0 and earlier |
| `OMC_GM_LLBND2FROM` | `-1` | v5.0 and earlier |
| `OMC_GM_DETFLOOR` | `0` | v5.0 and earlier |
| `OMC_GM_HARDMIN` | `5` | **v5.1** |
| `OMC_GM_DROPINTRA` | `0` | **v5.1** |
| `OMC_GM_INTRASTICKY` | `1` | **v5.1** |
| `OMC_GM_INTERABS` | `2` | **v5.1** |
| `OMC_GM_REDOMAX` | `1` | **v5.1** |
| `OMC_GM_MODE` | `12` | v5.0 and earlier — ⚠ **SUPERSEDED: the shipped default is 3 in v5.3.** See the v5.3 table at the end of this file |
| `OMC_GM_NOINTRA` | `0` | v5.0 and earlier |
| `OMC_GM_REPLAN` | `0` | v5.0 and earlier |
| `OMC_GM_DTHR` | `5` | v5.0 and earlier |
| `OMC_GM_WATCH` | `3` | v5.0 and earlier |
| `OMC_GM_ALIGN` | `4` | v5.0 and earlier |
| `OMC_GM_VETO` | `1` | **v5.1** |
| `OMC_DZ_PLANE` | `7` | **v5.1.1** |
| `OMC_DZ_CTO` | `9` | **v5.1.1** |
| `OMC_VEXT` | `0` (v5.3.6: the −2 level-2 candidate is qualified but NOT shipped — G-T5-CUT24) | **v5.1.1** |
| `OMC_VEXT_LVL` | `3` (v5.3.6: now pinned in the decoder freeze) | **v5.1.1** |
| `OMC_FILLGAIN_MAX` | `3` | **v5.1.1** |
| `OMC_FILLDIV_C` | `1` | **v5.2** — chroma fill divisor; the release's one enabled change |
| `OMC_DIVEFF` | `0` | **v5.2** — falsified (fails `G-T5-CALM2a/2b`), kept as evidence |
| `OMC_FILLMIN1` | `0` | **v5.2** — falsified (5 gate failures), kept as evidence |
| `OMC_GM_KEEPFILL` | `0` | **v5.2** — falsified (fails A4), kept as evidence |
| `OMC_ODCAP` | `0` | **v5.2** — rejected on latency by the mandate holder |
| `OMC_FILLROWS` | `0` | **v5.1.1** |
| `OMC_GM_LLCAPSH` | `0` | **v5.1.1** |
| `OMC_CHUNKSTAT` | `0` | **v5.1.1** |
| `OMC_GM_ESC` | `4` | v5.0 and earlier |
| `OMC_GM_ESCNUM` | `15` | v5.0 and earlier |
| `OMC_GM_ESCDEN` | `16` | v5.0 and earlier |
| `OMC_GM_FALLBACK` | `1` | v5.0 and earlier |
| `OMC_GM_ESC2` | `8` | v5.0 and earlier |
| `OMC_GM_ESC2NUM` | `3` | v5.0 and earlier |
| `OMC_GM_ESC2DEN` | `4` | v5.0 and earlier |
| `OMC_GM_GRADE` | `0` | v5.0 and earlier |
| `OMC_GM_TRIAL` | `0` | v5.0 and earlier |
| `OMC_GM_K` | `4` | v5.0 and earlier |
| `OMC_GM_STAT` | `0` | v5.0 and earlier |
| `OMC_GM_NUM` | `63` | v5.0 and earlier |
| `OMC_GM_DEN` | `64` | v5.0 and earlier |

`OMC_GM_LLHOLD` deserves a note: its default is **0**, so the v5.0 source
comment claiming *"the LL band is held back until the detail bands have had
three passes"* described an intention the code never carried out. That is the
defect `docs/OMC_V5_1.md` traces the artifact to. The comment is corrected in
v5.1 and the lever is kept at 0 so a v5.0 encoder can be reproduced exactly.

### Levers added 2026-08-26 (sections 54-59) — every one a NO-OP at its shipped default

The build is **byte-identical to v5.1.0** with all of these at their defaults;
verified by gate `G-T5-RESTORE` and by direct stream comparison. They exist so
the measurements behind sections 54-56 are reproducible by anyone holding this
zip, and so that the two that cost something can be turned on if the owner
accepts that cost.

| lever | default | what it does | measured |
|---|---|---|---|
| `OMC_DZ_PLANE` | `7` (all planes = no-op) | bitmask of planes the 9/16 deadzone applies to; `1` = luma only | chroma TRUE detail +27% Cb / +17% Cr, chroma retention above JPEG XS at DOUBLE the rate — **costs 0.71 VMAF-NEG**. Not default; owner's call under PROJECT_CONSTRAINTS §E. Ledger sect.54.6 |
| `OMC_DZ_CTO` | `9` | bounds the deadzone lift by band index on a plane the mask excludes | the sweep is monotone and the unbounded form is the efficient point. Ledger sect.54.6 |
| `OMC_VEXT` | `0` (off) | scaled linear continuation replacing the degenerate whole-sample mirror at the slice's BOTTOM edge, in quarters 0–4 | **FALSIFIED, kept as the evidence.** Removes a 25×-over-source row replication completely (Cb 0.673 → 0.101, beating JPEG XS) but costs up to 3.9 VMAF-NEG and makes the slice-pitch line WORSE (0.151 → 0.301). Ledger sect.55.5 |
| `OMC_VEXT_LVL` | `3` | which vertical level the continuation applies to | level 2 alone does nearly all the work and is no cheaper. Ledger sect.55.5 |
| **v5.3.6 REVISION of the two rows above** | `OMC_VEXT=-2`, `OMC_VEXT_LVL=2` is a QUALIFIED CANDIDATE, not shipped | a NEGATIVE strength is the two-sided 3:1 blend (the higher expert's Way 1), not the extrapolation that was falsified | quality-neutral-to-better on natural content, −0.5 NEG on a small graphics crop, seam replication cut 3–8× — and it leaks on G-T5-CUT24 at the shipped refresh period (4 samples at budget 13, 1 at 14), so it is held back (`docs/CHANGES_v5_3_6.md` §C, `src/dwt.c` §55). Both levers pinned in the decoder freeze. |
| `OMC_FILLGAIN_MAX` | `3` (no-op) | ceiling on the signalled grain-fill amplitude code | **inert on the measured corpus**: the derived gain is already 0, the minimum. Amplitude is not a lever for the fill trade. Ledger sect.54.6 |
| `OMC_FILLROWS` | `0` (every row) | restrict fill to the last N rows of each band | **FALSIFIED, kept as the evidence.** Filling only the boundary rows CREATES slice-pitch structure (0.151 → 0.315) instead of removing it — the measurement proving fill's cure is UNIFORMITY, not boundary repair. Ledger sect.55.5 |
| `OMC_GM_LLCAPSH` | `0` (off) | scale the LL DC excursion bound by `slice_h/16` | **FALSIFIED as a default.** Helps 1080p at slice_h 8 (worst block −309 → −118, NEG +0.06) and **hurts 720p** (blocks past 40: 72 → 139). Closes A5.1-5's "unmeasured". Ledger sect.58 |
| `OMC_CHUNKSTAT` | `0` (off) | dead-chunk census for Q5 sizing | 23.4% of inter chunks dead at 0.5 bpp; 5.4–8.6% of the symbol stream. Ledger sect.56 |

---

# v5.3 — the control surface as SHIPPED (generated from `src/codec.c`, 2026-08-30)

> **This table is what `tests/restore_check.sh` means when its failure message says the
> defaults and the documents must agree.** The v5.1 table below it is HISTORICAL and its
> `OMC_GM_MODE = 12` row is superseded here.

| lever | shipped default | what it is | ledger |
|---|---|---|---|
| `OMC_GM_MODE` | **3** | the repair's shape. **3 = finest bands first.** Pairs with `OMC_GM_ESCMODE`; mode 3 alone fails `G-T5-GAMUT2c/2d` | §51.18.4 |
| `OMC_GM_ESCMODE` | **2** | hand the slice to mode 12 from pass N. **The escape path.** Encoder-only | §51.18.4 |
| `OMC_GM_VETOAT` | **2** | the repair's fill veto, moved down the escalation ladder | §78.10 |
| `OMC_Q5FLAG` | **16** | Q5 block-skip pitch. **NORMATIVE** — the decoder takes it from `OMC_Q5K`, not from this | §64.7, §11.5b |
| `OMC_XSL_LOOPFREE` | **1** | the interior boundary edit becomes display-only (candidate L) | §55.7 |
| `OMC_FILLREACH` | **-1** | **−1 = auto**: 64 at `slice_h` 8, 0 at 16 | §78.10 |
| `OMC_FILLTHYS_C` | **3** | chroma temporal fill-mask dead-band, /32. Stands down at `slice_h <= 8` | §78.12 |
| `OMC_FILLTHYS_NB` | **1** | the neighbour gate on the dead-band's stay-off half | §78.12.3 |
| `OMC_FILLTHYS` | **0** | **luma dead-band — MUST stay 0** (returns `dng` blocks>40 6 → 68) | §78.12.4 |
| `OMC_FILLTHYS_1S` | **0** | FALSIFIED: one-sided dead-band moves chroma crawl under 1 % | §78.12.4 |
| `OMC_FILLTHYS_CHURN` | **0** | FALSIFIED: gating on flipped bands kills the benefit | §78.12.4 |
| `OMC_XSL_SPREAD` | **0** | FALSIFIED: **breaks A4** (`G-T5-XSL2/3a`). Split, not a cascade | §55.8a |
| `OMC_XSL_CASC` | **0** | works and passes every gate, but **relocates the artifact into G7** (`dng` blocks>40 3 → 68). NORMATIVE | §55.8c/d |
| `OMC_Q5INTRA` | **1** | intra-band Q5 block skip. **Frozen in the decoder (C8 corpus gate, 2026-09-06)**; encoder A/B only | Task G |
| `OMC_DBG_ZBAND` | **0** | was read INLINE in the decoder loop (missed by the freeze); the read is removed and the decoder announces the setting as ignored | Task G |
| | | **All of `OMC_Q5INTRA OMC_XSL_LOOPFREE OMC_TPART OMC_XSL_CASC OMC_XSL_SPREAD` are now in `omc_dec_conformance_freeze()` beside the motion levers `OMC_MVBLK OMC_MVBLK_OB OMC_MVBLK_SIG OMC_MVHP OMC_MVHP_BAR` (minor 16). v5.3.6: `OMC_MVHP` is no longer read from the environment (region half-pel is unconditional); `OMC_VEXT_LVL` joins the freeze.** | |
| `OMC_GM_UPSTEP` | **0** | FALSIFIED: move a vetoed coefficient AWAY from zero. Monotone regression | §51.18.2 |
| `OMC_GM_BITEFF` | **0** | FALSIFIED both signs: price the ranking in coded symbols | §51.18.3 |
| `OMC_FILLGHYS` | **0** | FALSIFIED: hysteresis on the transmitted 2-bit fill gain | §51.18.3 |
| `OMC_Q5LIVE` | **0** | **read-only instrument**, byte-inert: the LIVE skip census | §64.6b |

Constants, not levers:

| constant | value | why it is not an env lever |
|---|---|---|
| `OMC_Q5K` | **16** | Q5's block pitch is NORMATIVE and fixed by stream minor 13. Taking it from the environment segfaulted `omc_dec` on a valid stream (§11.5b D1). |
| `OMC_MINOR_T5` | **13** | the stream minor. v5.2 shipped 12 with minor-13 rules and a v5.1 decoder ACCEPTED it (§11.6). |

**19 further levers change normative reconstruction and are FORCED BACK to their shipped
values in the decoder** by `omc_dec_conformance_freeze()`, with a warning — so a decoder
cannot be made to disagree with the encoder by its environment. List and method: §11.5c.


## v5.3.6 notes (2026-09-08)

- **In-process A/B of a frozen lever is impossible by design.** `omc_dec_conformance_freeze()` pins the process-global lever variables when the first decoder is created; an encoder created afterwards in the same process inherits the pinned values. That is correct under C8 (the decode is a function of the bitstream alone) and harmless for the product (two processes), but it silently defeats an in-process encoder A/B such as a `test_xsl`-style harness — it cost the outside reviewer of v5.3.5 one wrong attribution. A/B a frozen lever with the encoder and decoder in separate processes, or with a scratch build whose freeze line is switchable (never shipped).
- **`slice_vis_rows()` is silent for `vv % 4 != 0`** (it returns `c->sh`): any probe that sweeps slice heights or visible-row counts must restrict itself to multiples of 4, or it will believe it exercised a case the transform never saw (Agent 3, MEMO 028 §gate (i)).
- **`OMC_GM_INTERABS` stays at 2.** Agent 4 measured 1 never worse and 2 the worst on one 4:4:4 arm, and withdrew the generalisation on replication; a bounded-effort loop that can move away from the constraint is not fixed by choosing which bands it moves (the terminal-rung argument, CHANGES_v5_3_6 §D).
- **Per-slice repair budget** `OMC_GAMUT_DEFPASS` = 13 (was 12), see the addendum in TEMPORAL_T5.md; `OMC_VEXT` = 0, `OMC_VEXT_LVL` = 3, both pinned (the −2/2 candidate is not shipped); `OMC_MVHP` no longer read.
