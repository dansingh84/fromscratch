# OMC profiles and levels (conformance points) - draft for the freeze

> **STATUS in v5.1: unchanged from v5.0.** v5.1 alters no profile and no default
> a profile names; it changes only how the in-gamut repair behaves once it fires
> (`docs/OMC_V5_1.md`). The v5.0 status below stands verbatim.
>
> **STATUS in v5.0: the profiles stand, with one default changed under them.** The grain fill is now **off** by default, so a profile that assumed it was on now describes a configuration reached with `--fill`. The strict in-gamut repair is **on** by default in every profile. See `docs/OMC_V5.md` section 2.


*(v4.4: the conformance vector set must additionally cover minor-4 streams
(entropy model v2) and minor-3 streams with the block-MV field present;
make_conformance.py needs those two vector classes added before freeze.)*

*(v4.7 rev8: three further vector classes — minor-5 streams (correlated
fill tile, `--grain-corr`), minor-6 streams (amplitude-matched fill), and
minor-7 streams (STATIC fill tile, `--fill-static`, stream byte 27 bit 2).
Grain-hold v3, plan hysteresis, and perceptual slice-budget allocation are
encoder-only decisions at existing pipeline points and need no vectors of
their own — any conforming stream exercises the decoder identically. See
BITSTREAM.md 9.3-9.5, ENHANCEMENTS_LEDGER E-9/E-10/E-11, REPORT.md 18.x.)*

A decoder claims conformance to a (profile, level) pair; an encoder claims
the streams it emits stay inside one.

## Profiles

| profile | constraints | target |
|---|---|---|
| **Contribution** | 4:2:2/4:4:4 Y'CbCr, 8/10/12-bit, progressive, R >= 1, no RCT | TV broadcast contribution (primary product) |
| **Studio** | Contribution + RCT RGB (components <= 10-bit), pad-and-crop dimensions, mono convention | media-server / LED-wall ecosystems |

Studio is a strict superset; every Contribution stream decodes on a Studio
decoder. Bitstream features are flag-gated, so a Contribution-profile
FPGA simply ties the 4.2 flags off. Note (v4.7): byte 27 (pixel_flags) is
now live in Contribution streams too — bit 0 (RCT) stays Studio-only, but
bit 1 (correlated fill tile, minor >= 5) and bit 2 (STATIC fill tile,
minor >= 7) are legal in either profile; byte 26 (scan_type) and byte 27
bits 3-7 remain reserved-zero and are still zero-checked at ingest, as are
bytes 28-31. The grain-fill bits sit at slice-header bit offsets
[328,346) in the current (minor >= 1) layout (BITSTREAM.md 9.3-9.5).

## Levels (decoder throughput/memory bounds)

| level | max luma samples/s | max width | reference store |
|---|---|---|---|
| L1 | 1920x1080x60 | 2048 | 1 frame at max format |
| L2 | 3840x2160x60 | 4096 | 1 frame |
| L3 | 7680x4320x60 | 8192 | 1 frame |

An R = 1 (stateless) stream requires no reference store at any level; a
device MAY claim "Lx-intra" to advertise that restriction.

## Conformance vectors

`harness/make_conformance.py` packages the directed vector set (every
band mode, both header generations, fill/gain states, refresh settings,
loss/resync cases, all formats, all 4.2 features) with SHA-256 manifest;
each vector ships as (input, stream, decoded reference) triple. RTL/ASIC
verification = decode stream, byte-compare against reference. The
independent Python decoder (harness/spec_decoder.py) is the second
authority for dispute resolution. Two further harnesses support hardware
bring-up: harness/loss_harness.py (burst-loss recovery vs the R bound) and
harness/hw_decoder_model.py (streaming memory-map model, byte-checked
against the reference).
