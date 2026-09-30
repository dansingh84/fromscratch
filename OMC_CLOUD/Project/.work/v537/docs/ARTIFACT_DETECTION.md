# G7 "WASH" — what it is, and how to detect it

*Shipped with OMC v5.1, 2026-08-25. This document is self-contained: everything
it names is in this zip. The full investigation that produced it is §51 of the
project ledger `LEDGER_v5_ADVERSARIAL.md`.*

**Standing instruction: run this before claiming any encoder change is clean,
on BOTH the candidate and the reference build.** The existing gate suite is
demonstrably blind to G7 — seam, flatten, CAMBI, ΔE76, the G1–G6 suite and
VMAF-NEG all passed the frames a blind reviewer rejected.

## 1. The name and the definition

The owner asked for an official name that collides with nothing already in the
OMC or HVBC record. Taken names, checked one by one:

| source | names already in use |
|---|---|
| `PROJECT_CONSTRAINTS.md` §G | **G1** 32×32 grid / tiles · **G2** blockiness / banding / blocks · **G3** pixelation · **G4** flattening / blotches · **G5** hard edges · **G6** discoloration |
| this project's own record | "ants" · "carpet" · "contrast collapse" (HVBC Mechanism C) · "chromatic seam" · "slice seam" · "grain" |

So *blotch*, *streak*, *band*, *block*, *tile*, *flattening*, *seam* and
*discoloration* are all spoken for or ambiguous. The proposal:

> ## **G7 — WASH**
>
> **What it is.** A coherent shift of the mean LEVEL of one wavelet LL-support
> block — `slice_h/4` picture rows by 32 picture columns, so 4 × 32 at
> `slice_h` 16 — **towards mid-grey**, with the local detail inside the block
> intact. Dark content is washed lighter; light content is washed darker.
>
> **What it looks like.** A pale wash over a dark area, or a grey wash over a
> light one, with a hard edge at the block boundary against its unwashed
> neighbours. On a 4-row block against a busy background it reads as a
> **streak**; where several adjacent blocks are washed together it reads as a
> **patch**. It appears on one frame and not the next in the same place, so in
> motion it flickers.
>
> **How it differs from the six that exist.**
> * not **G1 (grid)** — it is not a repeating lattice; it is isolated blocks on
>   a wavelet support, not a 32×32 tile grid, and it does not run in both
>   directions;
> * not **G2 (banding)** — banding steps a smooth gradient; a wash shifts a
>   whole block's level while leaving its gradient and its texture alone;
> * not **G3 (pixelation)** — it is coherent over hundreds of pixels, not
>   scattered singles;
> * **not G4 (flattening/blotches), and this is the important distinction.**
>   G4 is detail *destroyed* and replaced by a flat patch. In a wash the local
>   standard deviation is unchanged (measured ×0.94 to ×1.13) — **the detail is
>   all still there, sitting on a level that is wrong**. A G4 detector will not
>   see it, and the project's G4 guardrail (`harness/g4gate.sh`) did not;
> * not **G5 (hard edges)** — the edge a wash creates is at a *coding* boundary,
>   not at a place the source has a gradual transition;
> * not **G6 (discoloration)** — it is luma. Cb is unchanged to a fraction of a
>   code across every measured region.
>
> **How to spot it.** Not by looking for it in the picture — every instrument
> this project already runs passed the frames the owner objected to. Render the
> **mean signed luma error over each LL-support block** (§51.15). A clean
> picture is black there; a wash is a solid red or blue rectangle. The
> per-pixel error map finds it too, but at low rate that map is saturated
> everywhere by ordinary quantisation noise on any codec, so it cannot separate
> "this level is wrong" from "this area is noisy".

**Provisional until the owner confirms it.** If "wash" is not the word, the
drier alternative measured and rejected here was **"level shift"**; everything
else considered collided with G1–G6 or with the HVBC record.

**Where it came from, stated in one line so the name carries its cause:** a wash
is the footprint of the in-gamut repair reducing an LL coefficient, in a
transform domain centred on mid-grey, with a DC gain to pixels of exactly 1
(ledger §51.4).

---

## 2. The detection method

The core three tools are `harness/artifactmap.py`, `harness/levelmap.py` and
`harness/blotch.py` in this zip; four more (`strongmap.py`, `smudge.py`,
`footprint.py`/`fpscore.py`, `xrow.py`) answer questions the core three cannot,
and are described in sect. 2b. Nothing outside this zip is needed except the
footage the cell is built from.

### Why three tools and not one

| tool | what it is for | what it cannot do |
|---|---|---|
| `artifactmap.py` | **FINDING** a wash. The owner-verified instrument of ledger §50.7: signed error rendered red/blue, saturating at ±40 codes, regions derived **from the map itself** with no shape prior. **v5.3.5: `--plane Y\|Cb\|Cr`** runs the identical method on a chroma plane at its own raster (LEDGER_v5_3_5 §51.30); default Y is byte-identical to v5.3 | **Ranking two arms.** Its region test is scale-free, so it also flags sub-visible coding error, and its region COUNT can rise while the artifact goes away. ledger §50.3's "the repair amplifies artifacts that already exist" came from counts and was wrong |
| `levelmap.py` | **SEEING** a wash, and showing it to a human. Renders the **mean signed error over each LL-support block**. Zero for noise, non-zero only when a LEVEL is wrong. **A clean picture is black.** **v5.3.5: `--plane Y\|Cb\|Cr\|all`**; `all` writes three maps | It hides everything that is not a level error — by design |
| `blotch.py` | **MEASURING** a wash so two arms can be ranked: max, 99.9th percentile, the counts of blocks past 20 and past 40 codes, on a common 10-bit scale — **for all three planes (v5.3.5), each on its own LL support** — plus **`cont>20`**, the largest 4-connected run of blocks past 20 codes in any one frame, which is what separates five scattered blocks from one bar the eye reads (LEDGER_v5_3 §80.4b found a wash *relocated* into a bar that the counts could not see). The legacy luma line is printed LAST, byte-compatible with v5.3 up to `n>40` | It is a number. It is not a verdict (PROJECT_CONSTRAINTS §E). **Never rank on the luma line alone** — read all three planes (C5) |

**Why the per-pixel map is not enough on its own, stated because it cost this
investigation two rounds.** At 0.5 bpp on detailed content the ordinary
quantisation error saturates a ±40-code map *everywhere* — that is true of any
codec at that rate, including the incumbent. Shown the per-pixel map after the
first fix, the owner correctly reported that it still looked busy; the level map
of the same frame was almost black. **Show both, and say which one carries the
verdict.**

### The procedure

```bash
# 1. build both arms (the reference arm is what makes a number mean anything)
make          # this tree; build the v5.0 reference tree too, for the reference arm

# 2. encode + decode the cell under test
./omc_enc -i arms/gfx_1920x1080_422_10.yuv -o out/a.omc \
    -w 1920 -h 1080 --fmt 422 --depth 10 --bpp 0.5 -n 6
./omc_dec -i out/a.omc -o out/a.yuv

# 3. FIND  -- the owner-verified detector (sect.50.7).  Writes the map, the map
#             with every region boxed, the decode with the same boxes, and a
#             region list carrying the SLICE INDEX, which is what links an
#             artifact to the coding decision that made it.
python3 harness/artifactmap.py arms/gfx_1920x1080_422_10.yuv out/a.yuv 1920 1080 3 diag/

# 4. SEE   -- the coherence view.  A clean picture is BLACK.
python3 harness/levelmap.py  arms/gfx_1920x1080_422_10.yuv out/a.yuv 1920 1080 3 diag/level_f3.png

# 5. MEASURE -- the numbers two arms are ranked on, over the whole sequence:
#             one line per plane (Y, Cb, Cr) with worst / p99.9 / n>20 / n>40 /
#             cont>20, then the legacy luma line.  Pass --sh matching the
#             encode's slice height (720p codes at 8) and --fmt/--depth for the
#             cell, or the block grid is wrong.
python3 harness/blotch.py    arms/gfx_1920x1080_422_10.yuv out/a.yuv 1920 1080 6 --sh 16 --fmt 422 --depth 10
#    4b. the chroma views of steps 3 and 4 (C5: never luma-only)
python3 harness/artifactmap.py arms/gfx_1920x1080_422_10.yuv out/a.yuv 1920 1080 3 diag/ --plane Cb
python3 harness/levelmap.py    arms/gfx_1920x1080_422_10.yuv out/a.yuv 1920 1080 3 diag/level_f3.png --plane all

# 6. ATTRIBUTE -- when a wash is found, the trace names the slice and the pass
OMC_GAMUT_STAT=1 ./omc_enc ... 2>&1 | grep '^GAMUT f3 s25 '
#   fields: pass, bad (out-of-range samples), need (with the boundary margin),
#           Q / ns (the quantiser rung -- watch it COARSEN), deep (the worst
#           excursion in codes), dsum (their total).  A wash is a slice whose
#           rung falls and whose `deep` then jumps.
```

## 2b. The four supporting tools, and the question each one answers

The core three find, show and rank a wash. Each of the four below exists because
a specific claim made during the v5.1 investigation turned out to be
unsupportable with the core three alone; the failure that produced each one is
named, because that is what says when to reach for it.

| tool | the question it answers | the mistake that produced it |
|---|---|---|
| `strongmap.py` | *Where is EVERY strong red/blue, regardless of whether its level is wrong?* Boxes every region at the map's saturation limit with **no mean filter and no shape prior**, then classifies it WASH / SMUDGE / BOTH / RATE — the class changes only the label and the box colour, never whether the box is drawn | An earlier tool (`washmap.py`, retained in the ledger as a falsification) boxed only regions whose block MEAN was wrong. The owner corrected it: a region can have zero mean and still be the artifact, because the second face of a wash is a **smudge** — the texture is destroyed while the level stays right, and in the render it reads as a smear over the picture rather than as a dark patch |
| `smudge.py` | *Is the texture still there?* Ratio of sd(decode) to sd(source) per block | The strongest boxes on the error map were dismissed as "not the artifact" because their mean was ≈ 0. They were the artifact |
| `footprint.py`, `fpscore.py` | *How much did the REPAIR disturb the picture, as opposed to the rate?* `\|decode − the same cell with `--no-gamut-strict`\|`. `fpscore.py` adds the **flicker** columns: the sd of the per-frame footprint and its largest frame-to-frame step | Owner requirement, 2026-08-25: *"any change in prevalence of these errors between frames will appear as flicker, which we don't want."* A fix that lowers the mean while raising the step has not helped, and nothing in the core three could see that |
| `xrow.py` | *Where do these numbers land against an external reference?* The same block-level statistics plus the flicker and saturation columns, defined **only against the source**, so they can be run on any decoder's output — including JPEG XS | Every G7 number was self-relative (v5.1 against v5.0 against a repair-disabled arm). None had a zero point. See sect. 2c |

**`footprint`/`fpscore` are the sharpest attribution available and they are also
the least portable**: they are defined against an OMC arm built with the repair
disabled. That arm is a **diagnostic arm only** — it fails the baseband
generation contract and is never a quality reference point.

## 2c. Calibrating against JPEG XS gen 1

The project goal is *the same VMAF-NEG as JPEG XS gen 1 at half of JPEG XS gen
1's bitrate*, so **JPEG XS at 1.0 bpp is the reference for OMC at 0.5 bpp**, and
running `xrow.py` on an XS decode puts an external floor under every G7 number.

This is a like-for-like use of the instrument, not an OMC ruler held against a
foreign object: the 4 × 32 block it averages over is `slice_h/4` rows by the LL
band's horizontal support, which follows from *slice height 16, two vertical and
five horizontal decomposition levels* — the configuration the SVT-JPEG-XS
encoder reports for this run. It is the LL support of both codecs.

```bash
# JPEG XS gen 1 needs a real NASM >= 2.13 (the PyPI package named `nasm` is a
# broken shim and fails with ModuleNotFoundError: No module named 'convert').
SvtJpegxsEncApp -i arms/gfx_1920x1080_422_10.yuv -w 1920 -h 1080 \
    --colour-format yuv422 --input-depth 10 --bpp 1.0 -n 6 -b xs.jxs
SvtJpegxsDecApp -i xs.jxs -o xs.yuv -n 6
python3 harness/xrow.py arms/gfx_1920x1080_422_10.yuv xs.yuv 1920 1080 6 --label XS@1.0
python3 harness/xrow.py arms/gfx_1920x1080_422_10.yuv out/a.yuv 1920 1080 6 --label OMC@0.5
```

Result on the corpus's hardest cell (full table and reading: ledger §51.17):

| | OMC v5.1 @0.5 bpp | JPEG XS gen 1 @1.0 bpp |
|---|---|---|
| wash mean (mean \|block level\|) | 2.090 | 2.027 |
| worst block level, codes | 82.1 | **15.5** |
| level blocks >20 / >40 | 24 / 5 | **0 / 0** |
| wash flicker sd / max step | 0.194 / 0.218 | **0.008 / 0.027** |
| VMAF-NEG | 88.192 | **90.093** |

Three things follow, and they set the priority for any further G7 work:

1. **The average is at parity at half the bitrate** — 2.090 against 2.027 — and
   the repair-disabled arm is 2.049, so of v5.1's 2.090 only **0.041 is the
   repair**. There is nothing left to win on the mean.
2. **The tail is entirely ours.** JPEG XS never puts a block past 20 codes; v5.1
   does 24 times in 6 frames. The repair-disabled OMC arm at the *same* 0.5 bpp
   also has zero, which is what proves those 24 blocks are a defect rather than
   the price of the rate.
3. **The flicker gap is 24× but only 10% of it is the repair.** The
   repair-disabled arm is 0.175 sd against v5.1's 0.194. JPEG XS gen 1 is
   all-intra with a per-precinct budget, so its per-frame statistics are constant
   by construction; OMC is an inter codec by constraint C2 and cannot match that
   without giving up the rate advantage inter coding buys. Only the 0.019 the
   repair adds is addressable here.

### The rules this method carries, each of which was learned by getting it wrong

1. **Look at the picture before tuning a threshold.** Four detectors were built
   and owner-rejected before anyone opened the map itself (ledger §50.7).
2. **Impose no shape, length or size prior** beyond a minimum area. Every
   rejected detector assumed a shape.
3. **Never rank two arms on region COUNT.** Use area, severity, and
   `blotch.py`'s block statistics.
4. **Never accept a VMAF-NEG gain as evidence that a wash is smaller.** One arm
   in this investigation gained **+3.9 VMAF-NEG while making the worst wash 50 %
   worse**: delaying the intra force raises the average and *concentrates* the
   damage. That is the failure mode PROJECT_CONSTRAINTS §E is written about.
5. **Run it on BOTH arms before claiming a fix works**, and on the reference
   build, not only on the candidate.
6. **The existing gate suite is blind to G7.** Seam, flatten, CAMBI, ΔE76,
   G1–G6 and VMAF-NEG all passed the frames the owner objected to. A passing
   gate is not evidence of absence (ledger §50.4).
7. **Calibrate before declaring a residual acceptable — or unacceptable.**
   Self-relative numbers say whether a change helped; only an external reference
   says whether what is left is a defect. Run `xrow.py` on JPEG XS gen 1 at
   twice the rate (sect. 2c) before spending further effort, and re-read which
   rows are still gaps.
8. **A falsification is only valid against the stack it was measured on.**
   `OMC_GM_VETO=1` was correctly measured as harmful and correctly rejected, and
   then became the shipped default: F7 changed what a "reduction" displaces, so
   the quantity the veto refuses changed meaning. Re-check rejected levers after
   any change to the mechanism they act on (ledger §51.16).
9. **The eye decides.** The owner's markup of the error map located the last two
   mechanisms in this section (ledger §51.5 F6 and ledger §51.5f) after the instruments had
   stopped finding anything. When he circles a region, measure exactly that
   region — do not argue with it.

## 3. Where G7 comes from, and what v5.1 did about it

The full account is `docs/OMC_V5_1.md`. In one paragraph: the pixel domain fed
to the forward transform is centred on mid-grey and the LL band's DC gain to
pixels is exactly 1, so reducing an LL coefficient moves the LEVEL of its whole
support toward mid-grey. The in-gamut repair did exactly that, by a fraction set
by the CONTENT rather than by the violation, after a plan ratchet and an
unconditional intra force had driven it there. v5.1 breaks the ratchet, gates
the intra force on evidence, bounds the LL move below one lattice step, and
stops the repair restarting slices that have nearly finished.

**G7 is an encoder-policy artifact, not a bitrate artifact.** It appeared with
the repair at an unchanged bitrate and it is reduced at an unchanged bitrate.
Any explanation of a residual wash that reaches for "it needs more bits" should
be treated as suspect until it has ruled that out — the first version of this
document made exactly that mistake, and taking the objection seriously is what
produced F7 (`docs/OMC_V5_1.md` sect.10), the largest single further reduction.


## 2d. G4 FLATTENING and G8 GRID-LOCKED LINES — the 2026-08-26 suites

G7 "wash" is a LEVEL error over a coherent block. Two further classes need their
own instruments, and neither can be found with the G7 tools:

* **G4 flattening** — detail, colour or information lost inside a region whose
  LEVEL stays right. A mean-square metric *rewards* it, and the G7 level tools
  average over a block, which is exactly the operation flattening survives.
* **G8 grid-locked line** (named here) — a straight horizontal structure at the
  slice pitch that the source does not have. Distinct from the classical
  "slice grid": measured on this codec the DC slice-grid is **absent** (OMC's
  seam DC error is 0.97× its interior median, against JPEG XS's 1.32×), and
  what remains is an 8–11% *texture* modulation locked to the slice.

### The two suites

`harness/flat15.py` runs fifteen flattening measures (`harness/flatlib.py`);
`harness/line15.py` runs fifteen line detectors (`harness/linelib.py`). Both
write one full-frame map per measure plus a consensus map, and both are
described measure-by-measure in ledger §54.1 and §55.1.

Fifteen and not one, in both cases, because every single statistic of "detail"
has content it cannot see — a variance measure misses posterisation, a gradient
measure misses low-contrast texture, an entropy measure misses geometry, any
luma measure misses a total colour collapse, and any single-frame measure scores
a perfectly frozen decode as flawless. **Agreement between measures that fail
differently is evidence; agreement between fifteen variants of one measure is
not.** Five of the fifteen line detectors and four of the fifteen flattening
measures are chroma or colour-difference measures, because on this codec the
chroma defect is consistently the larger of the two.

### Three rules these suites carry, each learned by getting it wrong

1. **Normalise for rate before reading a flatness map.** Run raw, the fifteen
   measures called **69.6% of the frame flattened** — a true statement about
   0.5 bpp and a useless one about a defect. Each block's ratio is now divided
   by the median ratio of blocks at the same SOURCE detail level.
2. **Vote on the positive part only, for lines.** The first line consensus voted
   on the signed excess; at 0.5 bpp the decode is smoother than the source
   almost everywhere, the median went negative, and the reported index was
   2×10⁷. A line is structure the decode HAS and the source does not.
3. **Retention is not fidelity — always run `harness/fidelity.py` beside it.**
   Grain fill raises luma detail energy 0.596 → 0.830 and chroma 0.288 → 0.750,
   which looks like a spectacular repair; its correlation with the source's own
   detail *falls* (Cb 0.250 → 0.112). Retention alone would have shipped
   invented grain as a detail fix.

### Calibrate against BOTH JPEG XS rates, not one

The project goal names XS gen 1 at double the rate, so that is the quality
reference — but the same-rate arm is what says whether a defect is OMC's or the
bitrate's, and it was the missing control for a long time. On the gfx/DNG arm:

| | OMC v5.1 @0.5 | JPEG XS @0.5 | JPEG XS @1.0 |
|---|---|---|---|
| true detail Y/Cb/Cr | 0.582/0.119/0.122 | 0.460/0.041/0.051 | 0.622/0.170/0.185 |
| flattened blocks (≥10 of 15) | 719 | **4 763** | 0 |
| slice-pitch line, Y/Cb/Cr | 0.151/0.208/0.201 | 0.050/0.060/0.048 | 0.042/0.114/0.066 |
| VMAF-NEG | **88.192** | **76.922** | 90.093 |

At the same bitrate OMC is 11.27 VMAF-NEG ahead with 6.6× fewer flattened
blocks; the line is the one axis where the incumbent is ahead at equal rate.
Ledger §54.5 and §55.3.
