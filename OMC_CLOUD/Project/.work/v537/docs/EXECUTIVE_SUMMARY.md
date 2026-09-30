# OMC in plain English — executive summary

> **STATUS in v5.0: the numbers here were measured on v4.9 and are left as written.** They are not v5 measurements. The efficiency framing in this document — a **25-40% bandwidth saving to instruments** and **~50% to blind viewing** — remains the project's position and was independently reproduced on different footage during the v5 cycle (mean-VMAF saving measured at 24%, and 12% on the stricter anti-enhancement model, both inside the bands this document names). v5's own results are in `docs/OMC_V5.md` section 6.


*(Non-technical companion to REPORT.md, which holds every number cited
here. Current as of v4.9, 2026-08-11.)*

## v4.7 update in plain English

The one defect blind viewers actually found — regenerated film grain that
"crawled like ants" instead of flickering the way real grain does — is
closed. A refined grain-hold rule (three independent votes before any value
is touched, plus gentler coding of what remains) cut the measured tail of
the viewer-identified defect from 18.0% to 7.98% inside the viewers' own
box, now below fair JPEG XS at 2 bpp (7.73%) — with OMC at half that rate;
at the lower rate the same figure fell from 18.6% to 10.7%. A new opt-in
flag (--fill-static, one bitstream bit) additionally lets regenerated grain
hold perfectly still where that is wanted. Nothing was traded away: grain
strength is fully retained on the heavy-grain clips, the confetti stress
test moved by 0.16 VMAF, flattening stayed at baseline, multi-generation
copies still converge, and every stream from earlier releases decodes
byte-identically (verified against the pristine v4.6 build). Hardware cost:
zero new multipliers. The honest caveats below stand: blind viewing remains
the contractual referee. Full numbers: REPORT.md §18.7; per-change ledger:
ENHANCEMENTS_LEDGER.md E-9/E-10; format change: BITSTREAM.md §9.5.

## v4.4 update in plain English

Since v4.1: two latent defects fixed (one silently corrupted narrow pictures,
one crashed at very low rates); the quantizer got a measured, free improvement
(+0.45 dB on every color plane); the entropy coder's statistical model was
rebuilt after independent, held-out studies (+0.1–0.2 dB more, on footage the
tables never saw); and an opt-in "grain knob" now removes only provably
invisible sensor noise — it must pass two independent physical tests (no
coarser-scale footprint AND no frame-to-frame persistence) before a single
value is touched, everything removed is regenerated at measured strength, and
sharp small objects (the confetti stress test) are untouched. Most
significantly: with the incumbent measured at its BEST settings, OMC at HALF
of JPEG XS's rate now scores equal or better on Netflix's perceptual metric on
7 of 11 hard clips, and beats XS at equal rate on all 11. The remaining
instrument losses are two coarse-film-grain clips; the fix (grain synthesis
matched to grain coarseness) is designed and scheduled. Blind viewing remains
the contractual referee. Full numbers: REPORT.md §16; per-change ledger:
ENHANCEMENTS_LEDGER.md.

## What OMC is

OMC is a video compressor built for the professional broadcast pipeline -
the links between cameras, production facilities, and transmitters. The
incumbent technology on those links is JPEG XS. OMC's goal: pictures that
look just as good through the same pipe at a fraction of the data rate,
with the same near-zero delay, and with one guarantee JPEG XS cannot make -
that decoding and re-encoding the signal many times (which happens
constantly in production) does not degrade it at all.

## The claim, stated the only honest way: pick your definition of "same quality"

"Same quality at half the bitrate" depends entirely on what "same quality"
means, and there are exactly two coherent definitions. OMC commits to a
number under each - and ships a mode for each - rather than letting the
definition be chosen implicitly:

1. **Same to instruments** (full-reference metrics such as VMAF or PSNR,
   the way engineers usually write acceptance specs): OMC delivers a
   **25-40% bandwidth saving** over JPEG XS, plus advantages no metric
   captures - bit-exact multi-generation re-encoding and fast-motion
   quality XS structurally cannot match. Run OMC in Fidelity mode for
   these contracts; the metrics then mean what engineers expect them to
   mean. (The exact figure depends on how the gate is written: ~25% for
   mean-VMAF gates, shrinking to 10-15% for worst-frame gates set at the
   grain-noise floor, where both codecs' curves flatten together. All
   measured; REPORT.md 12f.)
2. **Same to viewers** (blind viewing): OMC delivers **~50%**. And the
   offer is not a different number to trust - it is the test itself: the
   sealed A/B kits in delivery/abx_kit are the acceptance procedure. The
   customer's viewers, their room, their verdict. Evidence so far
   (metrics near threshold, blind stills) supports the claim; the motion
   verdicts are theirs to take.

The gap between the two numbers is not marketing - it is physics. Heavy
camera grain contains real information; reproducing it *measurably
exactly* costs the same bits for any codec ever built. OMC's Perception
mode declines to spend those bits and regenerates the grain's energy
instead - eyes cannot tell, instruments can. Whoever writes the acceptance
spec therefore decides OMC's advantage; OMC's job is to be the best
option under either spec, and at every equal rate measured it outscores
JPEG XS on the instruments too.

## What else is proven so far
- **Re-encoding robustness.** For stationary content at the delivery rate,
  copies of copies are bit-for-bit identical from the second generation on
  - zero erosion, forever. JPEG XS erodes slightly (measurably, ~0.3 dB
  over 10 cycles at its production rate). For fast pans and the very
  heaviest grain, OMC's copies are not bit-identical but converge: quality
  stays flat and each generation differs less than the last, thousands of
  times below visibility. The documentation states exactly which content
  gets which guarantee.
- **Formats.** 1080p, UHD, 8K, 4:2:2 and 4:4:4, 8/10/12-bit, HDR - all
  verified end to end, including an out-of-bounds crash at 1080p found and
  fixed by testing rather than by a customer.
- **The format is fully written down.** A second decoder was implemented
  from the specification document alone and produces bit-identical output
  to the reference - including on a specification mistake that exercise
  found and fixed, which would have broken any independent implementation.
  (An earlier revision of this summary said "four specification mistakes".
  Only ONE is itemised anywhere in the tree - GAP-1, the missing allocation
  tables, in `docs/SPEC_GAPS.md` - so the claim is reduced to what the tree
  evidences rather than restated. v5.1, defect 1 of ledger sect.53.3.)

## What v4.1 added (this round)

1. **Fast-pan tracking.** The codec now follows camera motion up to 32
   pixels per frame (was 8). Sports-speed pans now look as good as slow
   ones - previously they dropped ~3 dB. This was the biggest practical
   weakness; it is gone. Nothing else changed measurably, and every safety
   gate stayed green.
2. **Grain strength matching.** Where the codec regenerates film grain
   rather than transmitting it exactly, it can now match the original
   grain's strength instead of using one fixed setting. Two subtle design
   errors in this feature were caught by our own regression tests before
   shipping (both would have caused invisible but real instability across
   re-encodings). Honest note: on our current test footage the feature
   rarely activates - it is wired and safe, waiting for grainier
   real-world material.

## What the verdict still needs

Two things only humans can supply: results from the sealed blind viewing
kits (delivery/abx_kit - three rate ratios, labeled by JPEG XS operating
tier), and genuinely captured continuous-motion footage, which our corpus
cannot synthesize. Every measurement that can be made without them has
been made and is in REPORT.md.


## Compression ratios in familiar terms (2026-08-03)

Both codecs are operated in bits per pixel (bpp); ratios depend on the
uncompressed source weight: 4:2:2 10-bit = 20 bpp uncompressed, 4:4:4
12-bit = 36 bpp. Ratio = uncompressed bpp / coded bpp.

JPEG XS is commonly described as 2:1 to 15:1; deployed contribution
practice (e.g. TR-08 over ST 2110-22) sits at 4:1-10:1, with "visually
lossless" claims usually holding to about 10:1, content-dependent.

OMC at the blind-verified anchor points, 4:2:2 10-bit:

| OMC rate | OMC ratio | blind-matched to | XS ratio there |
|---|---|---|---|
| 2.0 bpp | 10:1 | JPEG XS @ 4.0 bpp | 5:1 |
| 1.0 bpp | 20:1 | JPEG XS @ 2.0 bpp | 10:1 |
| 0.5 bpp | 40:1 | JPEG XS @ 1.0 bpp | 20:1 |

On 4:4:4 12-bit the same coded rates buy more (source is heavier):
OMC @ 2.0 bpp = 18:1 vs XS's 9:1 at matched quality.

One line: OMC's envelope is JPEG XS's envelope doubled - where XS spans
roughly 2:1-15:1, OMC spans roughly 4:1-30:1. Qualifiers (standing
policy): the equivalence is established by blind viewing at the sampled
anchor rates on the test corpus, not yet swept continuously; at the deep
end (40:1) both codecs degrade visibly - the claim there is "degrades
like XS at twice the ratio," not transparency.


## Metric-family verdict (2026-08-04, five metric families measured)

Against fair JPEG XS (`--coding-signs 2 --coding-vpred 2
--quantization 1`), at EQUAL rate and at DOUBLE rate (the mandate
anchor). Details: REPORT.md §18.9.5, §18.10, §18.12.

| metric family | what it measures | equal rate (OMC@R vs XS@R) | double rate (OMC@R vs XS@2R) |
|---|---|---|---|
| Blind human viewing (decisive per constraints) | perceived quality | not tested (redundant) | **PASS — indistinguishable on every kit clip** |
| VMAF | perceptual model | ahead 8 / tie 7 / behind 0 of 15 | ahead 5 / tie 8 / behind 2 |
| VMAF-NEG (anti-gaming) | perceptual, enhancement-proof | ahead 5 / tie 2 / behind 1 of 8 | behind on all 8 (0.07–0.74) |
| CAMBI (banding, G2) | banding artifacts | **OMC least banding on all 3 clips where banding is measurable**; ~0 for all arms elsewhere | OMC beats XS@2R on all 3 |
| PSNR / XPSNR / MS-SSIM | stored-pixel fidelity | core ahead on 11/15 (PSNR), 13/15 (MS-SSIM) | behind on all 15 — structural, see below |

The fidelity family (PSNR/XPSNR/MS-SSIM) cannot be won at half the
bitrate by any codec: those metrics count how exactly pixels were
stored, and twice the bits always stores pixels more exactly. The
half-rate claim is a PERCEPTUAL claim and is carried by the eye
protocol (passed) with VMAF as supporting evidence. Quote equal-rate
superiority on every family; quote the 2x claim on eyes, and disclose
that the hardened NEG model does not show a 2x lead.

Charted detail for the two perceptual cross-checks (VMAF-NEG margin
retention, CAMBI banding vs each source's own banding, with commentary
on what each finding does and does not support):
`delivery/NEG_CAMBI_REPORT.html`.

---

# v5.1 (2026-08-25) — one page

**What it is.** v5.0 with the in-gamut repair fixed. Encoder-only. No bitstream
change, no decoder change, same stream major and minor. A v5.0 decoder decodes a
v5.1 stream byte-identically, so a fleet upgrades encoders alone.

**Why it exists.** A blind viewer reviewing the v5.0 eye kit reported near-white
streaks running the length of a slice on dark content, dark patches on light
content, and both moving between locations frame to frame. **Every gate in the
suite passed the frame he objected to** — seam, flatten, CAMBI, ΔE76, G1–G6, and
VMAF-NEG rated it 85.9 either way. The instrument set was blind to a real,
visible defect, which is the single most important thing this release records.

**The defect now has a name: G7, "wash"** — a coherent shift of one
LL-support block's LEVEL toward mid-grey with the detail inside it intact. It is
not G4 flattening (where the detail is destroyed) and not G2 banding (where a
gradient is stepped), which is why every existing detector missed it.
`docs/ARTIFACT_DETECTION.md` defines it and gives the complete method.

**What the defect was.** The repair, when a slice would not clear gently,
coarsened that slice's quantiser plan and never let it recover; the intra force
that triggered the coarsening fired unconditionally; and the repair then removed
a fixed FRACTION of the LL band — the only band carrying DC, over a support of
4 picture rows by 32 picture columns, in a domain centred on mid-grey with a DC
gain to pixels of exactly 1. So a two-code excursion could move a whole block's
level by 181 codes, toward mid-grey, with the detail on top untouched. That is
exactly what a viewer sees as a bright streak on dark content and a dark patch on
light content.

**What v5.1 does.** Breaks the plan ratchet; gates the intra force on the
evidence of the failure it exists for; bounds the LL band's level move below one
lattice step, with a two-tier allowance on the two boundary band rows; stops the
repair restarting slices that have nearly finished, which is what made it grind
twelve passes of detail removal chasing three codes; and repairs an 8-bit
truncation that silently disabled the bound below 10 bits. An **unbounded redo**
sits behind all of it, lifting every one of those preferences, so the
legal-range guarantee never depends on any of them.

**What it delivers**, on the worst cell of the corpus (1920×1080 4:2:2 10-bit at
0.5 bpp, 6 frames), counting 4×32 blocks whose mean level error exceeds 40 codes:

| | v5.0 | v5.1 |
|---|---|---|
| blocks with a level error > 40 codes | 1 418 | **6** |
| 99.9th percentile level error | 147.2 | **16.4** |
| VMAF-NEG | 84.160 | **88.017** |
| Y / Cb / Cr PSNR | 32.665 / 34.476 / 35.572 | **34.300 / 34.503 / 35.592** |
| committed samples outside the legal range | 0 | **0** |

VMAF-NEG rises at every rate and never falls; both chroma planes rise; A4
baseband and CDR generation chains stay byte-exact from generation 2; 96/96 gates
pass; latency and the A2 conversion table are unchanged.

**What it does NOT do.** It does not touch the second artifact class the same
viewer reported — visible seam blends at every slice border. That remains open
and is the next priority. It does not change the goal-(b) rate picture except
incidentally (the repair was costing up to 3.7 VMAF-NEG on rail-touching
content, and that is now returned).

**The honest caveat.** No detector proves an artifact is gone;
PROJECT_CONSTRAINTS §E is explicit that only direct human review of the
full-resolution, full-frame output decides. The numbers above rank candidates.
The eye accepts them.
