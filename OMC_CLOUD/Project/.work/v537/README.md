# OMC-1 — Open Mezzanine Codec (**v5.3.6**)

> **v5.3.6, 2026-09-08. Stream: major 5, minor 16 — unchanged from v5.3.5** (`OMC_MINOR_T5` in
> `include/omc1.h` is the authority; the v5.3.5 tree shipped minor 16 while this header still said 14 -- corrected).
> No normative change ships in v5.3.6: a v5.3.5 decoder decodes v5.3.6 streams and vice versa.
> v5.3.6 is the merge of everything the five agents and the outside adversarial review established
> on v5.3.5, applied to the codec: read **`docs/CHANGES_v5_3_6.md`** first (what landed, what was
> deliberately not landed and why, the defects still carried, and every gate with its result).
> The level-2 two-sided slice-boundary predictor was built and quality-qualified but is NOT shipped:
> it fails the new legality gate at the shipped refresh period (`src/dwt.c` §55, CHANGES §C).
> Headline changes: the per-slice in-gamut
> repair budget is 13 (a 24-frame cut sequence at the shipped refresh period breached at 12 -- new
> gate G-T5-CUT24), the CDR re-encode path no longer skips the repair on an out-of-range slice, the
> CLIs no longer segfault on a trailing option, PQ (ST 2084) is removed from the tree (HLG stays),
> 28 compiler warnings are gone byte-inertly, the 16 conformance vectors are back and the restore
> gate is re-based on a v5.3.6 golden vector, and a CRC-valid decoder fuzz gate is added -- which
> found and fixed a decoder crash on a hostile slice header.
>
> *The v5.3.5 note that follows is kept for history.*

> **v5.3.5, 2026-09-01. Stream: major 5, minor 14 at that date (16 as shipped on 2026-09-06).** A v5.3-or-earlier decoder refuses
> and expects minor **12** and will refuse a v5.3 stream. That refusal is correct —
> v5.3 changes normative reconstruction. **Deploy both ends together.**
>
> ### What v5.3 changes, in one paragraph
>
> The in-gamut repair gets an **escape path**: it runs a cheap detail-bands-first
> shape for the first two passes and hands anything that shape cannot clear to the
> proven rule for the rest of its budget (`omc_gm_mode 3` + `omc_gm_escmode 2` —
> **these two are a pair and must move together**). The temporal engine gains
> **Q5 block skip** (`omc_q5flag 16`): at 0.5 bpp roughly **two coefficients in
> three are never transmitted**. A **chroma fill-mask dead-band** holds a
> slice-band's grain decision still between frames. Both new levers stand down
> automatically at `slice_h <= 8`, from the stream header — there is no switch and
> nothing is content-classified.
>
> ### Measured, v5.2 → v5.3, at IDENTICAL byte counts on all 13 corpus cells
>
> | cell | bpp | VMAF-NEG | blocks >20 | blocks >40 |
> |---|---|---|---|---|
> | `cf_gfx_448x256_422_10` | 0.5 | 67.493 → **74.420** (+6.93) | 611 → 404 | 159 → 91 |
> | `dng_1280x720_422_10` | 0.5 | 85.107 → **86.074** (+0.97) | 534 → 426 | 56 → 63 |
> | `dng_1920x1080_444_12` | 0.5 | 85.216 → **86.045** (+0.83) | 18190 → 17760 | 2744 → 2584 |
> | `dng_1920x1080_422_12` | 0.5 | 87.722 → **88.327** (+0.61) | 6473 → 5976 | 620 → **418** |
> | `dng_1920x1080_422_10` | 0.5 | 88.569 → **88.971** (+0.40) | 37 → **20** | 6 → **3** |
> | `dng_1920x1080_444_10` | 0.5 | 87.591 → **87.854** (+0.26) | 78 → 68 | 9 → 8 |
> | `dng_1920x1080_444_8` | 0.5 | 85.878 → **86.100** (+0.22) | 0 → 2 | 0 → 0 |
> | `dng_1920x1080_422_8` | 0.5 | 86.576 → **86.745** (+0.17) | 0 → 0 | 0 → 0 |
> | `readysetgo_1920x1080_422_10` | 0.5 | 90.869 → **90.935** (+0.07) | 19 → 17 | 0 → 0 |
> | `dng_1920x1080_422_10` | 1.0 | 93.307 → **93.346** (+0.04) | 3 → **0** | 0 → 0 |
> | `cityalley_1920x1080_422_10` | 0.5 | 93.540 → **93.550** (+0.01) | 0 → 0 | 0 → 0 |
> | `bosphorus_1920x1080_422_10` | 0.5 | 92.740 → 92.714 (−0.03) | 0 → 0 | 0 → 0 |
> | `dng_3840x2160_422_10` | 0.5 | 85.654 → 85.639 (−0.02) | 7 → **5** | 0 → 0 |
>
> **11 of 13 improve; the two that do not move by −0.026 and −0.015.** Luma flatness
> moves by under 0.02 points anywhere. Slice-pitch improves on 11 of 13.
>
> "Blocks" are LL-support blocks — `slice_h/4` rows by 32 columns — counted where the
> **mean signed error** over the block exceeds 20 and 40 codes on a 10-bit scale.
> That is the G7 "wash" measure: coherent level error, which a mean-square metric
> under-weights by construction. `harness/blotch.py`.
>
> ### What the temporal layer is worth
>
> `--refresh 1` makes every slice intra in every frame — all-intra, the same
> architecture as JPEG XS gen 1. Against the shipped R=8, at identical byte counts:
> **+2.6 to +14.8 VMAF-NEG**, largest on graphics. Q5 accounts for +0.04 to +1.83 of
> that, and contributes **exactly nothing** with the temporal layer off (identical to
> three decimals at R=1) — the two are one mechanism.
>
> ### Restoring v5.0 behaviour
>
> **The authoritative incantation lives in `tests/restore_check.sh` and nowhere else.**
> It used to be duplicated across five documents, and that duplication is what let it
> rot twice (ledger §11.5d D12–D13, and §51.16 before that). The gate is executable,
> so it cannot rot silently. It verifies two things separately: every byte outside the
> version field is identical to a pristine v5.0 stream, and the version field says what
> this build's `OMC_MINOR_T5` says.
>
> ### Validation
>
> * **A4: 12 of 12** cells, 11 generations at 11 frames, at the compiled defaults with
>   **no environment set**.
> * **`make test`: exit 0**, 97 `ok:` assertions across 6 suites — including
>   `G-T5-RESTORE` and the new `tests/levercheck.sh`, which asserts every documented
>   lever changes the stream, every short-rung stand-down does not, and every read-only
>   instrument is byte-inert.
> * **Exact CBR** and **`oob = 0`** on every arm.
> * **Not done:** the owner's eye has not seen this build, and by this project's rules
>   that is the decisive test, not any number above.
>
> **Start here:** `CHANGELOG_v5.3.md` — every change, every measurement, and every lever
> that was built and *not* shipped with the numbers that killed it. Then
> `docs/TEMPORAL_T5.md` §12.22 (v5.3 addendum) for the repair, and
> `LEDGER_v5_ADVERSARIAL.md` §11.5d for the full defect register.

## Product modes

One bitstream (v4.0), one decoder, two encoder postures — switchable per
deployment (or per stream) with zero interoperability cost, because the
grain-fill decision travels in per-slice header bits that every v4 decoder
honors:

| mode | flag | optimizes | posture |
|---|---|---|---|
| **Perception** (default) | — | what the eye sees: sub-threshold texture is regenerated at its measured amplitude (animated deterministic grain) instead of erased | run the pipe at **0.5× JPEG XS** and judge by blind viewing (constraints rev. 6): the codec's picture keeps its grain character where MSE-optimal coding goes waxy |
| **Fidelity** | `--no-fill` | PSNR/VMAF per bit: the v3.1-style MSE-optimal reconstruction | for customers who buy on metrics: at **equal bits** OMC measures equal-or-better than JPEG XS on every plane and metric measured (a strictly-better-per-bit codec), with no up-front commitment to the perceptual claim |

The modes share everything else — exact-CBR, latency, generations, loss
resilience — and a fleet can switch between them without touching decoders.


## v5.1 in one paragraph

v5.1 = v5.0 with the **in-gamut repair fixed**, and nothing else. A blind viewer
reported near-white streaks running the length of a slice on dark content and
dark patches on light content, moving frame to frame; every gate in the suite
passed the frame he objected to. The cause was three coupled defects in the
repair: the quantiser plan **ratcheted** coarser and never recovered, the intra
force fired **unconditionally** and is what tipped it, and the LL band — the only
band that carries DC, over a support of 4 picture rows by 32 picture columns —
was reduced by a fixed FRACTION of a value set by the content, so a two-code
excursion could move a block's level by 181 codes. v5.1 breaks the ratchet,
gates the intra force on evidence, bounds the LL level move below one lattice
step, stops the repair restarting slices that have nearly finished, and — the
change that removes the whole bit demand at constant rate — makes the inter
repair move the RECONSTRUCTION rather than the residual,
with a two-tier boundary allowance and an unbounded redo behind it so that the
legal-range guarantee never depends on the bound. It also repairs an 8-bit
truncation that silently disabled the new bound below 10 bits. Measured on the
worst cell: the count of 4×32 blocks whose level is wrong by more than 40 codes
falls **1 418 → 6**, VMAF-NEG rises **84.16 → 88.02**, luma PSNR **+1.64 dB**,
both chroma planes rise, and committed out-of-gamut samples stay at **zero**.
Encoder-only; no bitstream change; 96/96 gates pass. Everything, including every
rejected option and its measurement: `docs/OMC_V5_1.md`.

## v5.0 in one paragraph

v5.0 = v4.14 + the T5 temporal layer + the adversarial-review repairs, at
bitstream **major 5, minor 12**.  The temporal engine was removed and rebuilt:
the reconstruction no longer clips, so the committed picture is an exact
function of the emitted lattice point and a decode/re-encode chain is
byte-identical from generation 2 forever.  Cross-slice boundary reconstruction
is always on and exactly reversible; padded rasters have surplus rows that are a
pure function of the visible rows.  The "ants" defect a blind viewer identified
twice is closed in the quantizer by giving flat positions a full-step zero zone
— which only ever removes energy, so VMAF-NEG rises rather than falls.  The
grain fill is now **off** by default.  A strict in-gamut repair is **on** by
default and is what makes an ordinary baseband hand-off generation-exact, not
just the codec's own coded-domain interchange.  Five undefined left-shifts of
negative values were removed from the normative transform and colour stage
(output unchanged to the byte).  **A v4 decoder refuses a v5 stream and vice
versa.**  Everything, including every rejected option and its measurement:
`docs/OMC_V5.md`.

## v4.9 in one paragraph

v4.9 = v4.8 + cross-slice boundary reconstruction (bitstream minor 9): the
vertical lifting's boundary term reads the previous slice's committed
reconstruction, bounded continuity blends join the rows either side of a slice
seam, A5 refresh barriers keep a refreshed slice's coding loop independent (so
a lost slice still heals byte-exact within one refresh cycle), and the
boundaries those barriers leave raw are blended on the emitted picture only.
Encoder-side allocation gained a refresh boost (intra-refreshed slices no
longer starve, CBR unchanged), a boost-aware tail reserve and tail-local
guards.  Measured: beach@0.5bpp scores VMAF 95.21 vs JPEG XS@1.0's 94.94 —
the eye-quality stack and the metric stack no longer disagree.  Streams using
no post-7 feature remain byte-identical to v4.7 encoders.

## v4.7 in one paragraph

v4.7 = v4.4 + the correlated fill tile (`--grain-corr`, bitstream minor 5) +
amplitude-matched fill (minor 6) + the STATIC fill tile (`--fill-static`,
minor 7) + grain-hold v3 (encoder-only, part of `--grain-replace`:
amplitude+carpet votes, soft threshold, intra coarse-band classification,
coarse fill veto) + plan hysteresis (encoder-only) + perceptual slice-budget
allocation (encoder-only, default on; `OMC_ALLOC=0` restores the legacy
allocator). No change adds any buffering: all v4.5–v4.7 decisions are
encoder-side at existing pipeline points, so the docs/LATENCY.md table stands.
Every change ledgered with its measurement in docs/ENHANCEMENTS_LEDGER.md
(E-9/E-10/E-11); bitstream deltas normative in docs/BITSTREAM.md §9.3–9.5;
analysis in docs/REPORT.md §18. Old streams decode byte-identically; old
decoders correctly reject minor-7 streams.

## What this zip needs from outside (v5.1 — stated so it can be checked)

**The codec and its 96 gates need a C11 compiler and `make`. Nothing else.**

    make && make test     # gcc 16.2.1 and GNU make were used for v5.3.6 (16.1.1 for v5.3.5);
                          # any C11 compiler works.  rc = 0 is the pass.

There is no build-system dependency beyond that, no library to link but `libm`,
and no network access at any point. (An earlier session's notes describe a
private zig/musl toolchain; that was a property of that machine, not of this
tree.)

**The test HARNESS — not the codec — additionally needs**, and only for the
scripts that use them:

| dependency | needed by | why |
|---|---|---|
| `numpy` | most of `harness/` | array arithmetic on raw planes |
| `Pillow` (`PIL`) | `artifactmap.py`, `levelmap.py`, `gallery.py` | writing PNGs |
| `ffmpeg` with `libvmaf` + the `vmaf_v0.6.1neg` model | `vmafneg.sh`, `matrix.sh` | VMAF-NEG. Every VMAF number in this delivery used ffmpeg 8.1.2 |
| `rawpy` | `prep_master.py dng` only | demosaicing the DNG masters |
| `scipy` | two older research scripts | not needed for anything in `docs/OMC_V5_1.md` |
| `7z` | rebuilding the corpus from the `.7z` YUV sets | extraction only |

**The only thing deliberately NOT in this zip is footage.** `Footage/` is the
corpus and is orders of magnitude larger than the codec. Everything needed to
rebuild every master and arm from it is here (`harness/prep_master.py`,
`harness/derive.py`, and the exact commands in `docs/OMC_V5_1.md` §2.1), and the
six conformance vectors in `delivery/conformance/` are real streams that need no
footage at all — a decoder can be brought up from this zip alone.

## Layout

- `include/omc1.h`, `src/` — C11 reference implementation (encoder + decoder)
- `tools/omc_enc.c`, `tools/omc_dec.c` — CLI (raw planar LE16 Y'CbCr ↔ `.omc` stream)
- `docs/BITSTREAM.md` — **normative bitstream specification** (C8).  v5 ships
  stream **major 5, minor 12**; `docs/TEMPORAL_T5.md` is normative for the
  temporal layer and for the minor-12 reconstruction rules.
- `docs/ARTIFACT_DETECTION.md` — **G7 "wash"**: the artifact class v5.1 exists
  to remove, its definition against G1–G6, and the complete, self-contained
  method for detecting it. **Run it on both arms before claiming any encoder
  change is clean** — the existing gate suite is blind to G7
- `docs/OMC_V5_1.md` — **start here**: what v5.1 changed and why, every
  measurement and method, and every rejected option with the measurement that
  killed it
- `docs/OMC_V5.md` — the v5.0 account: defaults, everything implemented, every
  measurement and method, and every decision including the rejected ones. Not
  superseded; v5.1 is a delta on it
- `docs/TEMPORAL_T5.md` — the normative temporal specification, in full
- `docs/DANGLING_REFERENCES.md` — cited paths that do not exist, and why
- `repro/` — table generators run by the build (synthesis basis, polyphase,
  colour), so no shipped table can drift from the code it describes
- `docs/DESIGN.md`, `docs/HARDWARE.md`, `docs/LATENCY.md`, `docs/REPORT.md`
- `harness/` — masters prep, metrics (per-plane PSNR/SSIM/VMAF), JPEG XS comparison
  driver, loss simulator, latency model, inspection-gallery generator, tANS training,
  and (v5.1) the artifact instruments: `artifactmap.py` (owner-verified detector),
  `levelmap.py` (the coherence view — a clean picture is black), `blotch.py` (the
  level metric), `rt0.py` (the C4 check with the CDR projection applied),
  `matrix.sh` / `genchain.sh` (matrix cell and generation chain),
  `prep_master.py` / `derive.py` (corpus construction from `Footage/`)
- `tests/` — C unit tests (`make test`) + pytest acceptance gates

## Build & use

```
make                      # codec, both CLIs, both conversion tools, all six
                          # gate binaries.  Regenerates src/gm_basis_tab.c.inc
                          # from src/dwt.c first, so it cannot drift.
make test                 # 96 assertions across six suites; rc=0 is the pass

./omc_enc -i in.yuv -o out.omc -w 1920 -h 1056 --fmt 422 --depth 10 --bpp 2.0 \
          [--recon rec.yuv] [--slice-h N] [--primaries 9 --transfer 16 --matrix 9] \
          [--tune vmaf] [--refresh N] [--mv-regions] [--block-mv|--no-block-mv] \
          [--grain-replace] [--grain-corr] [--fill-static] [--no-deadzone] \
          [--fill] [--no-gamut-strict] [--gamut-strict N] [--cdr-in]
# v5 DEFAULTS THAT CHANGED:
#   the grain fill is OFF -- pass --fill to enable it (--no-fill still means off)
#   the strict in-gamut repair is ON (budget 12) -- it is what makes an ordinary
#     baseband hand-off generation-exact.  --no-gamut-strict or --gamut-strict 0
#     turns it off; it stands down by itself when --cdr-in declares coded-domain
#     input.  omc_enc EXITS 2 if it could not clear every sample (0 = delivered,
#     1 = encode failed), so a pipeline can gate on it at origination.
#   --mv-regions: single-hop only
./omc_dec -i out.omc -o dec.yuv [-v] [--cdr] [--upconv 1|2|4]
# v5.1 DEFAULTS THAT CHANGED (encoder policy only -- the bitstream is unchanged):
#   the in-gamut repair no longer ratchets the quantiser plan coarser, forces a
#   band to intra only on evidence, and may not move a band's LEVEL by more than
#   the blend cap.  docs/OMC_V5_1.md sect.4.  To restore v5.0 EXACTLY (verified
#   byte-identical):
#     >>> The incantation is NOT reproduced here.  It lived in five documents
#     >>> and rotted twice (ledger sect.11.5d D12-D13, and sect.51.16 before
#     >>> that).  The single authoritative copy is in tests/restore_check.sh,
#     >>> which is executable and therefore cannot rot silently.  Read it there.
#
# v5.2 DEFAULTS THAT CHANGED: the grain fill is ON, with a chroma-specific
#   divisor (omc_filldiv_c).  NORMATIVE -- this is why the stream minor moved.
#
# v5.3 DEFAULTS THAT CHANGED:
#   omc_gm_mode 12 -> 3 AND omc_gm_escmode 0 -> 2.  A PAIR: mode 3 alone fails
#     gates G-T5-GAMUT2c and 2d.  Detail bands first as an escape path, then the
#     proven rule as a guaranteed fallback.  Encoder-only.
#   omc_q5flag 0 -> 16.  Q5 block skip: stop re-sending 16x16 coefficient blocks
#     the decoder can already produce.  NORMATIVE; the pitch is the fixed
#     constant OMC_Q5K and the decoder ignores the environment (sect.11.5b).
#   omc_gm_vetoat 0 -> 2, omc_xsl_loopfree 0 -> 1, omc_fillreach 0 -> -1 (auto).
#   omc_fillthys_c 0 -> 3, with omc_fillthys_nb 1.  Chroma-only fill-mask
#     dead-band; LUMA MUST STAY 0 (a luma dead-band takes dng blocks>40 6 -> 68).
#   omc_fillthys_c and the seam cascade both stand down at slice_h <= 8,
#     derived from the stream header -- automatic, not a switch.
#   OMC_MINOR_T5 12 -> 13.
```

**`--slice-h` — the coding-unit height. Default 16; you rarely need to set it.**
The encoder picks **16 lines** for every format above 720p, and **8 lines** for
720p-class heights because 16 would breach the sub-1 ms bar there (A2). A height
that does not divide by 16 — 1080 above all — is coded at 1088 and cropped on
output automatically; you pass `-h 1080` and get a 1080-line picture back. The
value travels in the stream header, so any decoder sizes itself from it.

**Legal values are 8, 16 and 32.** Override the default when you have a reason:

- `--slice-h 8` costs about 10 % of rate at 1.0 bpp and 16 % at 0.5 bpp against
  the default, and buys latency headroom. The one case that needs it today is
  1080p50 with a vertical rescale in the decoder's output path, which the config
  validator refuses at 16 lines.
- `--slice-h 32` is for **2160p and 4320p only** and buys a further 6.5–12 % of
  rate. It fits the 1 ms budget with a conversion in the path from 59.94 Hz
  upward; at 2160p50 it needs the raster-clocked output converter. Below 2160p it
  breaches the budget on the codec term alone and the validator will say so.
  Decoder memory scales with it.

See `docs/BITSTREAM.md` §7 and `docs/LATENCY.md`.

Acceptance suite (needs prepared masters and the comparison instruments; see
`harness/prep_masters.py`, `harness/xs_sweep.py`):

```
python3 harness/prep_masters.py   # once: PNG masters -> Y'CbCr raws
pytest tests/                     # gates: rt0, CBR, generations, loss, fuzz, 12-bit,
                                  # HDR signalling, gradient banding tripwire
python3 harness/eval_omc.py --fmt 422 --bpp 2.0    # corpus quality vs targets
python3 harness/gallery.py                          # Section-G inspection gallery
python3 harness/artifactmap.py SRC.yuv DEC.yuv W H FRAME OUTDIR   # v5.1: the
                                  # owner-verified artifact detector (sect.5 of
                                  # docs/OMC_V5_1.md).  Run it on BOTH arms
                                  # before claiming any change is clean.
python3 harness/levelmap.py  SRC.yuv DEC.yuv W H FRAME OUT.png    # the coherence
                                  # view: a clean picture is BLACK
python3 harness/blotch.py    SRC.yuv DEC.yuv W H NFRAMES          # the level metric
```
