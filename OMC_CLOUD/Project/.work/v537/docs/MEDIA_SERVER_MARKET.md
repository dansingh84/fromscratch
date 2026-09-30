# Market note: OMC in a media-server / LED-wall ecosystem (2026-07-28)

Context: the mandate holder is considering a disguise-class media server
(virtual production, xR/ICVFX stages, live events) using OMC for all
transport - into, within, and out of the server, including feeds to LED
wall processors. This changes several recommendations from
FEATURE_MATRIX.md; deltas below.

## Priority and non-interference rule (mandate holder, 2026-07-28)

**TV broadcast contribution remains the primary target.** The media server
is a second use case of the same codec, and it must not bog down the
contribution product. Enforcement:

1. Every media-server feature is a **bypassable stage or wrapper**, opt-in
   via header flags; with flags off, the contribution datapath is
   bit-identical to the gated build (golden-stream byte-compare on every
   contribution case is the merge gate, as with interlace).
2. **The contribution timeline owns the bitstream-freeze date.** Server
   features that miss the pre-freeze window slip to a later minor
   revision; the freeze never waits for them.
3. **Known technical tension, decided up front:** RCT adds +1 bit of
   dynamic range; at 12-bit input this exceeds the 16-bit internal
   datapath (+3-bit transform growth -> ~16.2 bits). Decision: **RCT is
   capped at <= 10-bit RGB input in v1** so the contribution silicon's
   datapath is untouched; widening to 17 bits (~6% logic/BRAM on every
   arithmetic stage, paid by contribution hardware for a feature it never
   uses) is rejected. 12-bit RGB pipelines are a documented v1 limitation.
4. Instance density / 120 fps sizing is a product-SKU decision (same RTL,
   different part), made explicitly - the larger requirement must not
   silently size the contribution part.

## Upgraded

1. **RGB 4:4:4 + reversible color transform (RCT)** - now the top
   codec-level item, target: before bitstream freeze. Media servers and
   wall processors are RGB-native; coding RGB planes without decorrelation
   wastes ~1-1.5 bpp. An RCT (lossless, shifts/adds, XS precedent) plus a
   header flag is a small, contained change. Paper-design first.
2. **Alpha/key channel via mono (4:0:0)** - high priority; compositing is
   the server's core activity.
3. **Arbitrary raster dimensions** - NEW and in-scope (LED canvases and
   ribbons are odd-sized: 3120x1408, 5000x600...). Same wrapper pattern as
   the interlace design: pad width/height to alignment, crop on output,
   true dimensions in reserved header bytes. Core untouched.
4. **Storage/scrub posture** - R = 1 for stored clips (frame random
   access), R = 8 for live links; expose the split as presets in the
   control plane.

## Downgraded

5. **Broadcast transport ecosystem** (ST 2110-22 mapping, MXF) - no longer
   gating: in a closed ecosystem the same vendor owns both ends of every
   link, so ISO standing and third-party interop matter only at the
   broadcast-out boundary. IPMX/NMOS become the relevant interop story for
   pro-AV; keep the schema NMOS-mappable (already done).

## Amplified strengths (evidence already in REPORT.md)

- Static graphics are OMC's best case: near-free inter slices on
  frame-to-frame-identical content vs XS re-coding every frame - the
  relative advantage on wall links exceeds the broadcast case.
- Graphics safety is proven: fill never fires on text/graphics (11f);
  lossless at >= 1.0 bpp on synthetic panels; text 59 dB at 0.5 bpp.
- Sub-ms slice latency fits ICVFX glass-to-glass budgets.
- Encoder instance density: the reentrancy fix (12g) is prerequisite-grade
  here (dozens of encoder instances per server).

## Unchanged skips - reinforced

Interlace, Bayer/CFA, 4:2:0: the LED/VP world is the most
progressive-RGB market there is.

## New cautions

- **ICVFX is artifact-hostile**: wall output is re-photographed, so
  banding/moire compound through the camera. Wall links should run high
  rates in Fidelity mode until eye-validated in an actual camera loop
  (wall + camera + lens); the blind-kit protocol extends naturally.
- **High frame rate (100/120+ fps)** is standard on walls and untested;
  no structural issue expected (CBR is per-frame), but validation and
  throughput budgeting are open items.
- Guaranteed mathematical losslessness conflicts with the exact-CBR pipe
  (content-dependent lossless does occur at high rates); if pixel-exact
  wall calibration paths are required, that is a VBR-mode discussion for a
  future major version - flag early if needed.
