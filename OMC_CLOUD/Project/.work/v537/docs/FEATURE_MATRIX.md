# Feature matrix: OMC vs JPEG XS (ISO/IEC 21122)

> ## v5.0 additions — the table below this note is the v4.9 matrix
>
> The matrix that follows was written for v4.9 and is left as written. These
> rows are what v5 adds; each is specified in `docs/OMC_V5.md` and, for the
> temporal layer, normatively in `docs/TEMPORAL_T5.md`.
>
> | feature | v5 | JPEG XS | note |
> |---|---|---|---|
> | **Generation exactness, coded-domain interchange** | **yes, unconditional** | no | decode → re-encode is byte-identical from generation 2 forever. XS erodes measurably (~0.3 dB over 10 cycles at its production rate). |
> | **Generation exactness, ordinary baseband hand-off** | **yes, with the in-gamut repair (ON by default)** | no | the case that matters for an SDI/IP link between facility hops. Every cell of this corpus passes with zero residual samples; a non-convergence found during development was reported and closed (`docs/OMC_V5.md` 6.4). Verify on your own material — the encoder exits 2 if it could not clear a frame. |
> | **Unclipped committed pixel domain** | **yes** | n/a | the property the whole exactness argument rests on; clipping is irreversible and is why the v4 temporal engine could never be exact |
> | **Always-on reversible cross-slice boundary reconstruction** | **yes, not switchable** | n/a | removes the visible slice seam while staying exactly invertible |
> | **Pad neutralization** | **yes** | n/a | a raster coded taller than its display height (1080 as 1088) is exact over a *cropped* hand-off |
> | **Temporal calm (the "ants" fix)** | **yes, on** | not applicable — XS is stateless and reads *below* the source on this instrument | closes the defect a blind viewer identified twice; VMAF-NEG rises rather than falls |
> | **Grain fill** | present, **off** by default (`--fill`) | no | measured: off is at least as good on the ants tail on all three planes *and* on VMAF-NEG, on 14 of 16 cells |
> | **Strict in-gamut repair** | **yes, on** (`--no-gamut-strict`) | n/a | encoder-side only; no bitstream syntax, no decoder change |
> | **Determinism gates on the repair** | **yes** | n/a | output *and* internal path asserted identical on re-encode, including with other content coded in between |
> | **Stream version gating** | **major 5, hard refusal across majors** | n/a | a v4 decoder rejects a v5 stream rather than mis-decoding it |
>
> Unchanged and still true from the v4.9 matrix: exact CBR, sub-1 ms latency in
> every format of the mandate, `rt = 0`, loss resilience via refresh barriers,
> resolution conversion and the colour/tone-map stage.

> **Release numbering — HISTORICAL, describes v4.9.** This was **OMC v4.9**. The codebase implements every
> feature through bitstream minor 9 (8 = upconversion / in-loop TF signaling,
> 9 = cross-slice boundary reconstruction: XSL level 3, refresh barriers,
> barrier display blend). Streams that use no post-7 feature are still written
> with minor **7** so they stay byte-identical to v4.7 encoders — the baseline
> minor is a compatibility floor, not the release number (`OMC_VERSION_MINOR`
> = 7, `OMC_RELEASE_MINOR` = 9). Mentions of v4.4–v4.7 elsewhere in the docs
> are historical records of when a feature landed and are intentionally left
> as written.


*(v4.4 note: all XS comparisons below and in REPORT §16 now use XS at full
strength — `--coding-signs 2 --coding-vpred 2 --quantization 1`.)*

Verdicts in the last column:
- **OMC ahead** — capability JPEG XS structurally lacks
- **parity** — equivalent capability
- **RECOMMEND** — XS has it, OMC lacks it, and it serves modern deployments: implement (paper-design first, per the interlace discipline)
- **SKIP (legacy)** — XS has it because a universal ISO standard must; a modern codec should not
- **SKIP (different market)** — real XS capability, but not the mezzanine/contribution market OMC targets

## Coding capability

| feature | OMC v4.1 | JPEG XS | verdict |
|---|---|---|---|
| Rate at equal appearance | VMAF at 0.5x rate: equal-or-better than XS@2R on 7 of 11 hard clips (REPORT 16.3); eye verdicts pending | reference | **OMC ahead on the perceptual instrument** (conditional on blind verdicts) |
| Equal-rate quality | above fair-strength XS on all 11 clips measured (VMAF, v4.4) and on PSNR at every equal rate | reference | **OMC ahead** |
| Temporal prediction (motion, +/-32 px/frame) | yes | none (intra only) | **OMC ahead** |
| Multi-generation re-encode | byte-exact from gen 2 (statics); convergent on pans/heavy grain | "~10 generations without significant loss" (erosion measured 0.14-0.28 dB/10 gen) | **OMC ahead** |
| Grain handling | Perception mode (energy-matched regeneration) + v4.4 two-vote invisible-grain classifier (4-17% measured rate at equal VMAF, honeypot-safe); Fidelity mode switchable | codes grain literally (cost: rate) | **OMC ahead** (novel; needs eye ratification) |
| E-9 grain-hold v3 (encoder-only, inside --grain-replace) | **yes (4.7)** — third amplitude vote (\|coef\| < 3*2^(bitdepth-7)), per-slice-band grain-carpet vote (>=25% small nonzero cells), parent threshold 8 (10-bit), LL-gradient gate removed, soft-threshold coding (eligible coded deltas shrink 1 step, cap \|q\|<=3); viewer-box ant-tail 18.0% (watched v4.4) -> 7.98%, below fair XS@2bpp (7.73%), @1.0bpp 18.6% -> 10.7%; no flattening (flat-block rate 0.08% = baseline); minor<=6 streams decode byte-identically; legacy v4.6 byte-exact via OMC_GR_SOFT=0 OMC_GR_PTHR=2 OMC_GR_CARPET=0 OMC_GR_LLTHR=24 (ENHANCEMENTS_LEDGER E-9, REPORT 18.7) | codes grain literally (cost: rate) | **OMC ahead** |
| E-10 static grain fill (--fill-static, bitstream minor 7) | **yes (4.7)** — stream byte 27 bit 2: grain-fill sign-tile offsets frame-independent (static grain texture, no temporal animation); zero new per-pixel multipliers, one per-band static offset pair (same omc_fill_offsets with f=0), latency table unchanged (BITSTREAM 9.5, ENHANCEMENTS_LEDGER E-10) | n/a | **OMC ahead** |
| Exact CBR | every frame exactly F bytes | CBR per frame/precinct | parity |
| Visually lossless operation | yes (2.0 bpp on hard content) | yes (~4 bpp on same content) | parity in kind, OMC ahead in rate |
| Lossless-preferred (CBR) mode | **yes (--lossless)**: bit-exact when budget allows, graceful CBR fallback, per-frame verified; crossover clean <=2 bpp / grain ~9 bpp | high-bpp lossless reached ~4 bpp clean, not within 11.9 on grain | **OMC ahead** (lossless at ~half the rate; guaranteed-VBR lossless deliberately not built - would break exact-CBR) |

## Formats

| feature | OMC v4.1 | JPEG XS | verdict |
|---|---|---|---|
| 4:2:2, 4:4:4 | yes, verified | yes | parity |
| 8 / 10 / 12-bit | yes, verified | yes | parity |
| Resolutions | 720p-8K verified | similar range | parity |
| HDR signaling | HLG only (PQ removed in v5.3.6, owner ruling 2026-09-06) | PQ + HLG | XS carries PQ; OMC does not |
| 4:2:0 | no | yes (2nd edition) | deferred by its own condition (needs a concrete pro-AV socket) |
| RGB via lossless RCT | **yes (4.2)** — components <= 10-bit, container-promoted, spec-decoder-verified | yes | done |
| Arbitrary raster dimensions | **yes (4.2)** — pad-and-crop, <1% cost | fixed grid (precinct padding internally) | done |
| Mono (4:0:0) single component | **yes (4.2)** — flat-chroma convention, measured lossless keys at 2.0 bpp | yes | done |
| Alpha / key channel (extra component) | **yes (4.2)** — video stream + mono key stream, frame-locked | yes (multi-component) | done |
| Interlaced (field coding) | designed, DEFERRED (INTERLACE_CONVENTION.md) | yes | **SKIP (legacy)** — decision recorded; retrofit-compatible if a customer forces it |
| 14/16-bit depths | no (12 max; 16-bit datapath is sized for it) | yes (higher profiles) | **SKIP (different market)** — cinema mastering/RAW; would force a wider datapath through the whole pipeline |
| Bayer/CFA camera RAW | no | yes (TDC profile) | **SKIP (different market)** — in-camera workflows, different buyers |
| Sub-line latency profile | no (slice = 8/16 lines, sub-ms) | yes (Light-Subline, display links) | **SKIP (different market)** — display-link/pro-AV silicon, not contribution |

## Robustness and operations

| feature | OMC v4.1 | JPEG XS | verdict |
|---|---|---|---|
| Packet-loss recovery | R-dial 1..16+ frames, measured cost table, concealment | per-frame independence (implicit R = 1) | **OMC ahead** (OMC at R = 1 = XS posture at XS-parity quality) |
| Loss concealment (what is shown during recovery) | **motion-compensated + spatial** (decoder-only): projects the reference along neighbour MVs on motion (+21 dB vs freeze on a coherent pan), spatial-interpolates when there is no temporal reference (frame 0 / intra frame, +13.7 dB); verified >= freeze across a 48-position loss sweep (worst -0.28 dB); clean decode byte-identical (REPORT 15) | freeze / hold-last only (intra-only: no MVs, no reference frame to project) | **OMC ahead** (structural: XS has no motion vectors to conceal with) |
| Stateless operation | yes (R = 1, no frame store) | always | parity (OMC makes it a mode) |
| Random access / splice anywhere | at refresh boundaries (R frames); every frame at R = 1 | every frame | parity at R = 1, XS ahead at R > 1 (inherent to prediction; the dial is the answer) |
| Latency | 0.16-0.78 ms measured (720p-8K) | same class | parity |
| Encoder/decoder determinism | bit-deterministic, verified | deterministic | parity |
| In-stream mode observability | yes (fill bits auditable from stream) | n/a | **OMC ahead** |
| Reconfiguration | stream-boundary, 2-frame ramp | per frame | parity in practice |

## Ecosystem (where the real gap is)

| feature | OMC v4.1 | JPEG XS | verdict |
|---|---|---|---|
| Normative bitstream spec | yes, proven by independent implementation | ISO/IEC 21122 | parity in quality, XS ahead in standing |
| RTP payload / ST 2110-22-style transport mapping | working note (TRANSPORT_NOTE.md); real payload spec at freeze | RFC 9134, ST 2110-22, VSF TR-08 | in progress |
| Container mappings (MXF, ISOBMFF/MP4) | no | yes (21122-3 + SMPTE) | **RECOMMEND** — needed the day a customer wants file-based workflows; documentation-level work |
| NMOS control-plane profile | schema groundwork done (CONTROL_PLANE.md) | BCP-006-01 | **RECOMMEND** — follow the XS precedent; gated on bitstream freeze |
| Profiles/levels & conformance points | **Contribution + Studio profiles, L1-L3 levels (PROFILES.md); packaged vector set with SHA-256 manifest (make_conformance.py)** | Main/High/Light profiles, conformance part | done (draft, finalizes at freeze) |
| Shipping silicon / vendor interop | none (prototype + FPGA-ready spec) | mature multi-vendor ecosystem | XS ahead — the honest moat; time, not features |
| Licensing | royalty-free by design (C1: expired-IP primitives, provenance documented) | patent-pool licensed | **OMC ahead** — a real procurement argument against the incumbent |

## Status after the 4.2 round (2026-07-28)

All originally recommended items are done or in progress: arbitrary
rasters, RGB/RCT, mono/alpha, profiles+levels, conformance packaging, and
the transport working note (final payload spec, NMOS profile, and
MXF/ISOBMFF mappings finalize at bitstream freeze). Remaining open item by
its own condition: 4:2:0 (needs a concrete pro-AV socket).

## v4.7 round (2026-08-02)

E-9 grain-hold v3 and E-10 --fill-static (bitstream minor 7) added above.
All other v4.7 changes are encoder-only policy inside --grain-replace; env
knobs OMC_GR / OMC_GR_PTHR / OMC_GR_SOFT / OMC_GR_CARPET / OMC_GR_LLTHR /
OMC_GR_QMAX / OMC_GR_SOFTCAP override. Grain sigma retained 100% on
cow/graincell; beach fine grain 67% + static fill. Confetti VMAF
98.36->98.20; aerial/couch unchanged. Matte: moving-edge boil identical,
flat boil calmer than GR-off. rt=0 422/10 + 444/12; generations converge
55.8->58.7 dB rising; exact CBR held. Minor<=6 streams decode
byte-identically (verified vs pristine v4.6 build). Details: REPORT 18.7,
ENHANCEMENTS_LEDGER E-9/E-10, BITSTREAM 9.5.

Skip list unchanged: interlace (legacy; decided and recorded), 14/16-bit,
Bayer/RAW, sub-line profiles - revisit only with a business case, never as
reflex feature-matching.


**Open work and resume points:** see docs/HANDOFF_2026-08-04.md
(spec-only decoder ladder, F-4 minor-8 checklist, mms deficit,
eye-gate pairs, documentation debt).

---

# v5.1 delta (2026-08-25)

| feature | v5.0 | v5.1 | signalled? | decoder change? |
|---|---|---|---|---|
| in-gamut repair: quantiser plan across passes | ratchets coarser, never recovers | **re-enters on the slice's pre-repair rung** | no | no |
| in-gamut repair: intra force | unconditional from pass 1 | **from pass 4, and only after a pass that removed nothing** | no | no |
| in-gamut repair: LL band level move | unbounded on the escalated path | **bounded below one lattice step**, with a two-tier boundary allowance and an unbounded redo behind it | no | no |
| in-gamut repair: the converging restart | fires on any pass that removes nothing | **only when at least `OMC_GM_HARDMIN` (5) samples remain** — below that the slice has nearly finished and the restart only re-grinds | no | no |
| in-gamut repair: boundary-row margin | chased only through the mask | **plus a 4-pass reserve on UNLOCKED slices** | no | no |
| LL bound depth scale below 10 bits | n/a | **rounds up, floor 1 code** (the `(maxv+1)>>10` truncation gives 0 at 8 bits) | no | no |
| stream major / minor | 5 / 12 | **5 / 12 (unchanged)** | — | — |
| v5.0 decoder on a v5.1 stream | — | **byte-identical output** (measured) | — | — |
| conformance vectors | pre-v5 only (unusable by a v5 decoder) | **+6 v5-class vectors**, verified by both decoders | — | — |

Everything else in this matrix is unchanged by v5.1.


## The artifact vocabulary, as of v5.1

`PROJECT_CONSTRAINTS.md` §G defines G1–G6. v5.1 adds a seventh class, because
the defect it fixes is none of them and calling it "blotches" (G4) obscured the
difference for an entire investigation:

| class | one line | detector |
|---|---|---|
| G1 | the 32×32 grid / tiles | brightness + grid overlay (§G1) |
| G2 | blockiness / banding, including colour banding | CAMBI |
| G3 | pixelation | — |
| G4 | flattening / blotches — **detail destroyed**, replaced by a flat patch | `harness/g4gate.sh` |
| G5 | hard edges | — |
| G6 | discoloration | ΔE76 |
| **G7** | **wash — one LL-support block's LEVEL shifted toward mid-grey, detail INTACT** | **`harness/levelmap.py` + `harness/blotch.py`; see `docs/ARTIFACT_DETECTION.md`** |

**G7 against G4 is the distinction that matters.** In G4 the detail is gone; in
G7 the local standard deviation is unchanged (measured ×0.94 to ×1.13) and only
the level is wrong. A G4 detector cannot see a wash, and this project's G4
guardrail did not.
