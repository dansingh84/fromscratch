# OMC v5.1 — what changed, why, and every measurement behind it

**Subject:** OMC v5.1, stream major 5, minor 12 (unchanged from v5.0)
**Date:** 2026-08-25
**Predecessor:** `CHANGELOG_v5.md` / `docs/OMC_V5.md` (v5.0, 2026-08-19)
**Governing spec:** `PROJECT_CONSTRAINTS.md` revision 6
**Full working record, including every falsified idea:** the project ledger
`LEDGER_v5_ADVERSARIAL.md` §51 (artifact) and §52 (academia)

> **Start here** if you are picking this build up. `CHANGELOG_v5.1.md` is the
> short form. `docs/OMC_V5.md` remains the authority for everything v5.0
> established and is not superseded; this document is the delta.

---

## 1. What v5.1 is

v5.1 is **v5.0 with the in-gamut repair fixed**. It is an encoder-only change:

- the bitstream syntax is unchanged;
- every normative reconstruction rule is unchanged;
- the stream major and minor are unchanged (5, 12);
- **a v5.0 decoder decodes a v5.1 stream byte-identically**, and a v5.1 decoder
  decodes a v5.0 stream byte-identically — both measured, §7.4.

So a fleet upgrades encoders alone. There is no flag day.

## 2. The defect it fixes

A blind viewer reviewing the v5.0 eye kit reported, on `gfx` at 0.5 bpp:

1. near-white streaks "almost resembling screen glare" running the length of a
   slice, on the dark computer screen inside the picture, visible zoomed-out and
   absent from both the source and JPEG XS;
2. on the light-coloured area below it, the artifact is instead a **dark** patch;
3. in motion the artifacts persist and **move between locations frame to frame**.

Everything the v5.0 gate suite measures passed that frame: seam, flatten, CAMBI,
ΔE76, G1–G6, and VMAF-NEG rated it 85.9 either way. The instrument set was blind
to it.

### 2.1 The corpus, and how to rebuild it

The `gfx` master is the DNG take in the uncompressed footage set — a hand-held
shot of a laptop on a kitchen counter, dark screen with white text above a white
keyboard. Those are the two rail-touching regions, and that is the whole
geography of the defect.

```bash
mkdir -p dngsrc masters arms
unzip -o -q "Footage/actual_video_files/uncompressed/DNG/260806_171716_VIDEO_14mm.zip" \
      "frame00000[0-9].dng" "frame000010.dng" -d dngsrc
python3 harness/prep_master.py dng dngsrc 11 masters/gfx_3840x2160_444_12.yuv
python3 harness/derive.py masters/gfx_3840x2160_444_12.yuv 3840 2160 1920 1080 422 10 11 \
        arms/gfx_1920x1080_422_10.yuv
```

Control clips, from the uncompressed YUV set, on which the repair barely fires
and the fix must therefore change nothing:

```bash
Y=Footage/actual_video_files/uncompressed/YUV
N=16; B=$((3840*2160*3/2*2*N))
7z e -so "$Y/CityAlley_3840x2160_50fps_420_10bit_YUV_RAW.7z"   CityAlley_3840x2160_50fps_10bit.yuv        | head -c $B > masters/cityalley_420_10.raw
7z e -so "$Y/Bosphorus_3840x2160_120fps_420_10bit_YUV_RAW.7z"  Bosphorus_3840x2160_120fps_420_10bit_YUV.yuv  | head -c $B > masters/bosphorus_420_10.raw
7z e -so "$Y/ReadySetGo_3840x2160_120fps_420_10bit_YUV_RAW.7z" ReadySetGo_3840x2160_120fps_420_10bit_YUV.yuv | head -c $B > masters/readysetgo_420_10.raw
for c in cityalley bosphorus readysetgo; do
  python3 harness/prep_master.py yuv420 masters/${c}_420_10.raw 3840 2160 10 11 masters/${c}_3840x2160_444_12.yuv
  python3 harness/derive.py masters/${c}_3840x2160_444_12.yuv 3840 2160 1920 1080 422 10 11 arms/${c}_1920x1080_422_10.yuv
done
```

How much the repair fires at 0.5 bpp, per clip, over 6 frames:

| arm | slices repaired | fell back to the harsh rule |
|---|---|---|
| `gfx` (DNG laptop) | 268 | 119 |
| `cityalley` | 10 | 2 |
| `readysetgo` | 5 | 2 |
| `bosphorus` | 0 | 0 |

## 3. The cause

### 3.1 Why an LL reduction moves a level

The pixel domain handed to the forward transform is **centred on mid-grey**:

```c
/* src/codec.c, step 1 of the slice encode */
for (int x = 0; x < pw; x++)
    d[x] = (int32_t)src[x] - c->mid - OMC_REF_BIAS;      /* c->mid = 1 << (depth-1) */
```

Band 0 (LL5) is `{r0 = 0, c0 = 0, h = sh/4, w = W/32}` (`src/internal.h`), so one
LL coefficient covers **4 picture rows × 32 picture columns** at `slice_h` 16;
and the LL band's DC gain to pixels is exactly 1 (measured, and stated as such
next to the two-pass DC null in `src/codec.c`).

Therefore reducing an LL coefficient by D moves the LEVEL of a 4 × 32 block by
exactly D codes **toward mid-grey** — brightening dark content, darkening light
content — with the detail riding on top untouched. That is the artifact in both
of its reported signs, and it is why the local standard deviation of the
affected regions was measured unchanged (×0.94 to ×1.13).

**Falsification, nine control arms, all required to fail and all of which do.**
`OMC_GM_BANDHOLD` forbids the repair one named band. Holding band 0 is the only
one that reduces the artifact (dark-region severity 806 647 → 53 124); holding
any other single band makes it 1.2× to 1.8× **worse**, because the repair then
leans harder on the LL. Full table: ledger §51.4(a).

### 3.2 Why the reduction is so large — the plan ratchet

The excursions being chased are tiny: over 6 frames, 1 116 out-of-range samples
across 179 slice-visits — **4 to 44 per slice out of 30 720 luma samples, mean
depth 19 codes**. Against that the repair moved a 128-pixel block's level by up
to 194 codes. The chain that gets there, traced on the worst slice
(`gfx`, frame 3, slice 57, v5.0 as shipped):

```
GAMUT f3 s57 pass0 bad=6  need=6  Q=7 ns=2 deep=23     <- converging
GAMUT f3 s57 pass1 bad=3  need=4  Q=7 ns=2 deep=7      <- converging
GAMUT f3 s57 pass2 bad=25 need=28 Q=8 ns=0 deep=86     <- PLAN COARSENED
GAMUT f3 s57 pass0 bad=24 need=26 Q=8 ns=0 deep=69     <- restart, still at Q=8
```

1. The repair shrinks the covering coefficients; the count falls 6 → 3 and the
   depth 23 → 7. **It is working.**
2. From pass 1 the repair forces every repaired band to **intra**,
   unconditionally, to break the documented inter-inheritance failure.
3. An intra band costs more bits. The slice budget is fixed (exact CBR), so the
   encode overflows and the backoff ladder coarsens the plan one rung:
   `Q=7, ns=2` → `Q=8, ns=0`. **The quantiser step doubles.**
4. Every repair pass re-enters `encode_attempts` with `Q`, `n_steps` and
   `partial` still holding what the last overflow backed off to, so **the plan
   never recovers** — not when the shrink has since made the payload far
   smaller, and not across the converging restart, which restores the
   coefficients but not the plan. It is a ratchet.
5. On the coarser rung the reconstruction error is twice as large, so the
   violation gets **worse**: 3 → 25 samples, depth 7 → 86.
6. The convergence projection sees a slice going backwards, declares it
   hopeless, and restarts it with the rule that always converges: **3/4,
   proportional, uncapped** — which removes a quarter of the LL coefficient's
   magnitude in a single pass. The magnitude is set by the CONTENT, so a
   two-code excursion can move a level by 181 codes. On that frame **119 of 268
   repaired slices took that path.**

## 4. The fix

Four changes, all encoder-side, all inside the in-gamut repair, all default-on,
each individually switchable back to v5.0.

### F1 — break the plan ratchet (`OMC_GM_PLANRESET`, default 1)

Every repair pass, and the converging restart, re-enter the encoder on the
slice's own **pre-repair** rung. Safe because the repair only ever REDUCES
coefficient magnitudes, so the pre-repair rung fits again unless the intra force
is what tipped it — and if it still does not fit, the ordinary bounded backoff
ladder runs from there exactly as before.

### F2 — gate the intra force on evidence (`OMC_GM_INTRAEVID` 1, `OMC_GM_INTRAFROM` 4)

The inter-inheritance failure has a signature: the violation stops falling. A
band is now forced to intra only from pass 4 **and** only after a pass that
removed nothing. A converging slice never pays for it; a slice showing the
signature still gets it.

### F3 — bound the LL band's DC excursion (`OMC_GM_LLCAP` −2, `OMC_GM_LLHARD` 2)

The repair may not move a level by more than **half the LL band's own largest
quantiser step**. That is a derived constant, not a tuned one: the LL shift is
hard-capped at `OMC_LL_CAP` for anti-banding (G2), so the LL band's step never
exceeds `1 << OMC_LL_CAP` = 4 codes, and half of that is **below what the
lattice can express**. The LL is therefore effectively pinned and can move only
through the release paths below. It scales with the depth like every other
amplitude in the codec.

(`OMC_GM_LLCAP = −1` selects the development bound — the XSL blend cap itself —
which is what the first measured version of this fix used. It is kept because
it is the bound §51.4's reasoning arrives at, and because the difference
between the two is one of the measurements in §8.) The bound is on the TOTAL
excursion from the slice's untouched coefficient, so a cumulative rule cannot
evade it, and it survives the converging restart.

It stands down in exactly three places, each of which is a measured necessity:

- **the two boundary LL band rows, tier 1** (`OMC_GM_LLBND` 2 from pass
  `OMC_GM_LLBNDFROM` 8): those rows reach the previous slice's last row only
  through the XSL term `d1 = (e0 − e14)/4`, so a bound of `cap` on the
  coefficient delivers only `cap/4` where the violation is. Gating it on the
  pass index matters: a blanket allowance measured **worse** (blocks past 40
  codes 14 → 25) because it licenses a bigger move on every boundary row rather
  than on the few that need one;
- **the same two rows, tier 2**, on the final pass of the budget, where the
  bound is lifted entirely;
- **the density escape** (`OMC_GM_LLDENSE` 10, tenths of a per cent): when a
  slice is out of range over ≥1 % of its own area its LEVEL is what is wrong and
  moving it is the correct repair, not an artifact. That is the pathological
  rail-on-boundary case of gate `G-T5-GAMUT2c` (45 478 samples) and it is
  nothing like real footage (4 to 44 samples per slice, 0.01–0.14 %).

Behind all three sits **the unbounded redo**: if the budget runs out with the
slice still out of range and the bound was in force, the bounded attempt is
thrown away, the original coefficients are restored, and the slice is repaired
again with v5.0's rule and no bound anywhere. **The legal-range guarantee never
depends on the bound.** On the whole validation matrix that redo fires on 2 of
408 slice-visits of one cell and nowhere else. Worst-case per-slice work is
therefore three times the pass budget rather than two — see §6.

### F4 — the margin reserve (`OMC_GM_LOOPNEED`, default 4)

The repair loop stops on true legality and deliberately not on the blend-cap
margin: an earlier version looped on the margin AND clamped the source to it,
and when the budget ran out with the margin unmet, generation 2 clamped its own
input, the lock failed and the chain broke. That commit rule is unchanged. What
changes is that an **unlocked** slice may spend a bounded reserve of 4 passes
chasing the margin, so its last row ends inside it and the next slice never has
to make the ×4-attenuated correction. Generation safety comes from the one
condition that matters: **only an unlocked slice chases the margin**, and at
generation ≥ 2 the slice locks, so it never enters that loop.

### F6 — do not restart a slice that has nearly finished (`OMC_GM_HARDMIN`, default 5)

The convergence projection that triggers the converging restart is

```c
if (removed <= 0 || gm_bad > removed * left) gm_hard = 1;
```

and `removed <= 0` fires on **any** pass that removes nothing — including a pass
on a slice already down to ONE sample THREE codes out of range. Restarting there
throws away all the progress and re-grinds twelve passes of uncapped
proportional detail reduction to recover it, which after twelve passes has
removed 97 % of the neighbourhood's texture. **That grind, not the level move,
is where the last of the visible artifact came from**, and it was found by
tracing the exact blocks the owner pointed at:

```
GAMUT f5 s61 pass0 bad=6 need=7 Q=8 ns=12 deep=18
GAMUT f5 s61 pass1 bad=3 need=3 Q=8 ns=12 deep=18
GAMUT f5 s61 pass2 bad=1 need=2 Q=8 ns=12 deep=3    <- one sample, three codes
GAMUT f5 s61 pass3 bad=1 need=2 Q=8 ns=12 deep=3
   ... restart, then TWELVE passes at bad=1 deep=3 ...
```

A slice with only a handful of samples left is not one gentleness has failed on;
it is one gentleness has nearly finished. The restart is now gated on at least
`OMC_GM_HARDMIN` samples remaining. Measured on the block above: **−70.4 → +1.4**.

**The guarantee is preserved by making the redo lift EVERY v5.1 preference.**
The unbounded redo (F3) now also restores the restart's v5.0 eligibility, so on
that path the rule is exactly v5.0's and nothing v5.1 added can cost exactness.
That was not true when F6 first landed — 720p at 0.5 bpp committed 1 to 2
out-of-range samples — and it is the reason the redo is written the way it is.

### F5 — the 8-bit truncation in the depth scale

The blend cap scales as `xsl_lim * ((maxv + 1) >> 10)`, which **truncates to
zero below 10 bits** (`256 >> 10 == 0`). A bound of zero is a bound that does not
exist, so at 8 bits F3 silently did nothing and the first 8-bit measurement of
the fix showed the artifact getting *worse* (peak −50.5 → −84.8 codes on the
8-bit scale) while VMAF rose. The LL bound now scales with rounding and a floor
of one code. **Only the bound is repaired; the boundary edit's own scale is
normative and is untouched.**

---

## 5. The instruments

*The artifact class is named **G7 "wash"** and is defined, distinguished from
G1-G6, and given a complete detection procedure in `docs/ARTIFACT_DETECTION.md`,
which is self-contained inside this zip.*

`harness/artifactmap.py` is the **owner-verified** detector and is used
unchanged: signed luma error rendered as a colour map saturating at ±40 codes,
regions derived from the map itself (channel > 110/255, local density > 0.35 in
a 5×25 neighbourhood, area ≥ 150), **no shape, length or size prior**. Its four
rejected predecessors and why each failed are in the ledger §50.7. Use it; do
not re-invent it.

It is right for **finding** the artifact and wrong for **ranking two arms**: its
region set is scale-free, so it also flags sub-visible coding error and its
region COUNT can rise while the artifact goes away. v5.1 therefore adds two
instruments beside it.

**`harness/blotch.py` — the level metric.**

> **BLOTCH** = max over all frames and all (`slice_h`/4) × 32 blocks of the
> **mean signed luma error**, on a common 10-bit code scale, reported with the
> 99.9th percentile and the counts past 20 and past 40 codes.

The block is the LL band's support, so it asks exactly what the eye asks: *is
any level wrong, over a coherent area, by an amount a viewer can see?* It rises
when damage is CONCENTRATED, which is the failure mode a mean-square metric
rewards — and it caught a candidate that raised VMAF-NEG by 3.9 while making the
worst blotch 50 % worse.

**`harness/levelmap.py` — the coherence view.** Renders the same block means as
an image. At 0.5 bpp on detailed content the ordinary quantisation error
saturates the per-pixel map everywhere, so the per-pixel map cannot separate "a
level is wrong" from "this area is noisy". On the level map **a clean picture is
black**. Use both when showing a frame to a human.

**Neither is a verdict on picture quality.** PROJECT_CONSTRAINTS §E is explicit:
the only decisive verdict is direct human review of the full-resolution,
full-frame output, and "an automated detector reporting *no artifact* is not
proof the artifact is gone". These metrics rank candidates; the eye accepts them.

## 6. Hardware and latency (C3, A2)

- **No new buffering.** Every change is inside the existing per-slice
  encode-attempt loop, at pipeline points that already existed. `docs/LATENCY.md`
  stands unchanged and the A2 conversion table in `test_cc` re-measured
  identical: 0.13–0.86 ms across 720p50…4320p50 including up- and down-conversion.
- **Bounded work, restated.** v5.0's worst case per slice was `2 × gamut_strict`
  passes (the gentle attempt plus the converging restart). v5.1's is
  `3 × gamut_strict` (plus the unbounded redo of §4/F3). At the default budget of
  12 that is 36 passes rather than 24. Measured on the hardest cell in the
  corpus the redo fires on **2 of 408 slice-visits**; on every other cell of the
  validation matrix it never fires.
- **Measured encode cost**, best of 3 on a quiet machine, 6 frames of 1920×1080
  4:2:2 10-bit at 0.5 bpp: v5.0 **7.21 s**, v5.1 **7.41 s** — **+2.8 %**. Repair
  passes over the encode rise 457 → 563; the overflow-backoff attempt count
  *falls* 193 → 180, because the plan reset stops the ladder walking.
- **No new arithmetic class.** The changes add comparisons, one integer divide
  per LL coefficient per pass in the (already divide-bearing, encoder-only)
  repair path, and no per-pixel multiplier. The decoder is untouched.

## 7. Validation

### 7.1 Gates

`make test`: **96 assertions across six suites, rc = 0, zero failures.** The two
that the LL bound broke before the density escape existed —
`G-T5-GAMUT2c` (the pathological one-row rail features walked across slice
boundaries) and `G-T5-CUT4` (hard black and white plates at the exact rails) —
both close to **zero** residual samples again.

### 7.2 The v5.0 restore switch — the non-vacuity proof

```bash
OMC_GM_PLANRESET=0 OMC_GM_INTRAEVID=0 OMC_GM_INTRAFROM=1 OMC_GM_MODE=12 \
OMC_GM_LLCAP=0 OMC_GM_LLHARD=0 OMC_GM_LLDENSE=0 OMC_GM_LOOPNEED=0 \
OMC_GM_LLBND=1 OMC_GM_RETRO=1 OMC_GM_HARDMIN=1 OMC_GM_DETFLOOR=0 \
OMC_GM_DROPINTRA=0 OMC_GM_INTRASTICKY=1 OMC_GM_INTERABS=0 OMC_GM_VETO=2 \
OMC_FILL=0 OMC_FILLINTRA=0 OMC_ANTSGATE=24 OMC_FILLTHR=3 OMC_FILLDIV=0 \
OMC_GM_ESCMODE=0 OMC_GM_VETOAT=0 OMC_Q5FLAG=0 OMC_XSL_LOOPFREE=0 \
OMC_FILLREACH=0 OMC_FILLTHYS_C=0 OMC_PLAN_HYST=0 OMC_RBOOST=0 OMC_PLANSD=0 OMC_GM_DILFROM=0 OMC_LOCK_TIEACT=0 \
  omc_enc ...
```

produces a stream identical to a pristine v5.0 encoder **everywhere except the
stream-version field**: v5.3 moves the minor 12 -> 13, so header byte 6 differs
by design and **345 631 of 345 632 bytes match**. The change is exactly and only
what these knobs say it is; nothing else moved.

> **⚠ 2026-08-30, v5.3.** This list is **historical**. Levers have been added since,
> and a list duplicated across five documents is exactly what rotted twice
> (ledger §11.5d D12–D13, and §51.16 before that). **The single authoritative
> copy now lives in `tests/restore_check.sh`**, which is executable and therefore
> cannot rot silently. Read it there; do not copy it anywhere else.


### 7.3 rt = 0 (C4), done correctly

`--recon` writes the encoder's reconstruction as a **CDR**: biased by 2048,
unclipped, at the CODED raster. The decoder's output is the non-normative
projection `clip(v − 2048, 0, 2^depth − 1)` cropped to the display height. A
plain `cmp` of the two therefore always "fails" and proves nothing.
`harness/rt0.py` applies the projection first. **rt = 0 on every cell of the
matrix, all three planes.**

### 7.4 Decoder interoperability

| stream from | decoded by | result |
|---|---|---|
| v5.1 encoder, 1920×1080 4:2:2 10-bit @0.5 bpp | v5.0 decoder | byte-identical to the v5.1 decoder |
| v5.1 encoder, 1920×1080 4:4:4 12-bit @2.0 bpp | v5.0 decoder | byte-identical |
| v5.1 encoder, 1280×720 4:2:2 10-bit @1.0 bpp | v5.0 decoder | byte-identical |
| v5.0 encoder, 1920×1080 4:2:2 10-bit @0.5 bpp | v5.1 decoder | byte-identical to the v5.0 decoder |

### 7.5 Resolution conversion

The decoder's output-stage converter is orthogonal to this change and is
re-verified: `omc_dec --upconv 1 | 2 | 4` all produce the expected raster from a
v5.1 stream, `test_uc` and `test_cc` pass, and the A2 conversion table (§6) is
unchanged. The `--slice-h` rungs the A2 model allows are exercised in §7.6.

### 7.6 The matrix

Every cell: encode → decode → C4 `rt = 0` → gamut count → VMAF-NEG (10-bit only;
the model is defined on 10-bit) → per-plane PSNR (C5) → the level metric. Run by
`harness/matrix.sh`. The complete tables, both arms side by side, are in the
project ledger §51.10; the shape of the result is:

- **oob = 0 and rt = 0 in every cell of both arms**, at every rate 0.5–4.0, every
  raster 1280×720–7680×4320, every depth 8/10/12 and both chroma formats.
- **VMAF-NEG rises or is identical in every cell but one** — 7680×4320 @0.5 falls
  by 0.019, at the metric's noise floor, on a cell whose artifact count falls
  36 → 5.
- **All three PSNR planes rise or are identical in every cell.** Nothing is
  traded.
- **Level errors past 40 codes fall by 20× to 100×** in every cell where the
  artifact exists, and are unchanged where it does not (4.0 bpp; the control
  clips).
- The peak single block grows in three cells (§8).

### 7.7 A4 — generations

`harness/genchain.sh`, 4 generations, over both interchanges: **baseband** (each
hop hands over the decoded picture, an SDI hop) and **CDR** (each hop hands over
the coded-domain raw and the re-encode declares `--cdr-in`). The requirement is
byte-identical stream **and** picture from generation 2 onward. Cells: every
depth × chroma at 0.5 and 2.0 bpp, 1280×720 / 1920×1080 / 3840×2160 / 7680×4320,
1.0 and 4.0 bpp at 1080p, and all three control clips. **All PASS.** Full table:
ledger §51.10.

### 7.8 Conformance

The six new v5-class vectors (`delivery/conformance/`) decode to their recorded
hashes under **both** the v5.1 and the pristine v5.0 decoder.

---

## 8. Rejected — sixteen candidates that were built and measured

The full table, with the measurement that killed each, is in the project ledger
§51.7. Summarised, and worth reading before proposing any of them again:

| what was tried | what killed it |
|---|---|
| hold the LL band out of the repair entirely | 138 samples left outside the legal range: at 0.5 bpp the LL is the only band with energy left |
| hold each of the other nine bands (control arms) | all nine made the artifact **worse** — the repair leans harder on the LL |
| a flat LL bound with no release | never converged at any value from 1 to 32 codes |
| a least-norm bound sized by the mean excess | saturated at ~110 residual samples: the residual violations are on boundary rows, where the correction is attenuated by 4 |
| LL reduced by exactly N quantiser steps per pass | converges only at N ≥ 4, by which point the move is as large as the proportional rule's |
| release the bound on the final k passes | no effect — the slices that need it are inside the restart, where the pass counter has been reset |
| bound the boundary release at N × the cap | true for the neighbour it cannot reach, false for the row's own slice; broke convergence at every N |
| give the bound up on a stalled restarted pass, or near budget exhaustion | too eager on real footage (blocks past 40: 17 → 320) |
| bound tier 2 at N × the bound | one residual sample at every N |
| stop charging a previous-slice boundary violation to this slice | better picture, one residual out-of-gamut sample |
| **band-escalation repair shapes (modes 3 and 5)** | best VMAF-NEG of any single change (+2.42) **but breaks gate `G-T5-GAMUT2c`** — the pathological rail-on-boundary synthetic stops closing to zero. Not shipped |
| re-plan the shrunken slice naturally (`OMC_GM_REPLAN`) | measured worse under the final stack |
| the unbounded redo as an unconditional last resort | when it fires often it *is* v5.0 |
| no dilation of the repair mask | 6–36 residual samples: the dilation is filter reach, not slack |
| the uniform alignment veto | dark-region severity 0.81 M → 1.11 M |

**And one methodological rejection worth more than the rest:** an arm scoring
**VMAF-NEG 88.068 (+3.9 over v5.0, better than what shipped)** had a worst level
error of **−291.9**, half again worse than v5.0's. Delaying the intra force
raises the average and **concentrates** the damage. That is why `blotch.py`
exists and why PROJECT_CONSTRAINTS §E is written the way it is.

---

## 9. What v5.1 does NOT fix

1. **The slice-seam class** — the same viewer's second report, visible seam
   blends at every slice border on most clips. Untouched, and the level maps show
   it survives with the repair disabled, so it is a different mechanism.
   **It is the top open artifact item.**
2. **The flicker items, only partly.** §3 explains why the artifacts move between
   locations frame to frame, and removing 98 % of them must reduce it — but no
   temporal instrument was built, and the report of "more colour-block updating
   than JPEG XS" is a CHROMA observation that this luma-only work did not measure.
3. **HDR (PQ/HLG), interlace, and the JPEG XS comparison** were not re-measured.
   None is expected to move; "not expected to move" is not a measurement.
4. **The `--slice-h 8` rung** carries 8× the level error of `--slice-h 16` at the
   same raster and rate. 720p codes at 8 lines by default. See
   `OPEN_DECISIONS.md` A5.1-5.

---

## 10. F7 — the residual, and the reasoning that found it

The reviewer's verdict on the first v5.1 renders was *"90 % of the too
dark/bright blobs are gone; there are still some noticeable without zooming
in."* This document first explained that residual as needing more bits. **That
explanation was wrong and is withdrawn.** The objection that overturned it:

> G7 is a NEW artifact at an UNCHANGED bitrate. The slice grid was always there
> and may well be a bit problem; the washes were not. So the washes cannot be a
> bit problem.

That is correct, and re-reading the trace with the constraint "the fix must not
need a bitrate" found the real defect.

`dcoef = coef - pcoef`, so an inter band reconstructs as `pcoef + dequant(dcoef)`.
The repair shrinks **both arrays toward zero**, which on an inter band moves the
reconstruction toward the **prediction** — not toward mid-grey, where the repair
is trying to go. **That mismatch is the entire stated reason the intra force
exists**, and the intra force is what costs bits, overflows the slice and takes
the quantiser rung the slice never recovers.

The correction is arithmetic, not a mode change and not a bit:

```
new_dcoef = dcoef - (coef - reduced_coef)     ->  pcoef + new_dcoef == reduced_coef
```

**Proof it removes the demand rather than feeding it:** with the reconstruction
shrunk correctly, turning the intra force off entirely still commits **zero**
out-of-range samples — which it never does otherwise. Shipped as
`OMC_GM_INTERABS=2` (detail bands only; the LL keeps v5.0's rule because it is
the only band that reaches the previous slice's last row through the clamped XSL
term, and changing it leaves one residual sample on two pathological gates).
The margin reserve moved 4 -> 6 alongside it.

| cell @0.5 bpp | before F7 (blocks >20 / >40) | after F7 |
|---|---|---|
| 1920x1080 4:2:2 10-bit | 61 / 8 | **43 / 6** |
| 1920x1080 4:2:2 12-bit | 132 / 40 | **102 / 35** |
| 1280x720 4:2:2 10-bit | 785 / 154 | **646 / 112** |
| 3840x2160 4:2:2 10-bit | 29 / 8 | **37 / 1** |
| 7680x4320 4:2:2 10-bit | 37 / 5 | **42 / 2** |
| 1920x1080 4:2:2 8-bit | 88 / 4 | 97 / 4 |
| 1920x1080 4:4:4 10-bit | 50 / 4 | **78 / 8 — the one regression, unexplained** |

Frames 2 and 3 of the review cell now carry **zero** blocks past 40 codes.

**Still open on G7:** the 4:4:4 regression above; 720p, which remains the weak
raster (112 blocks past 40 against 1080p's 6, because it codes at `slice_h` 8
where the LL support is 2 rows); and `OMC_GM_INTERABS=1`, which is better still
on real footage and fails two synthetic gates by one sample each.

**The general lesson, recorded because this document made the mistake:** G7 is
an encoder-policy artifact, not a bitrate artifact. It appeared with the repair
at an unchanged bitrate and it is reduced at an unchanged bitrate. Any future
explanation of a residual wash that reaches for "it needs more bits" should be
treated as suspect until it has ruled that out.

> **v5.3 added six levers to this incantation** (`OMC_GM_ESCMODE`, `OMC_GM_VETOAT`,
> `OMC_Q5FLAG`, `OMC_XSL_LOOPFREE`, `OMC_FILLREACH`, `OMC_FILLTHYS_C`) and v5.3 also
> moves the stream minor 12 -> 13, so the restored stream now matches a pristine v5.0
> stream **everywhere except header byte 6, the version field** — 345 631 of 345 632
> bytes. `tests/restore_check.sh` verifies exactly that, and checks the version field
> separately against the build's own `OMC_MINOR_T5`. Ledger §11.5d D12–D13.


## Interchange modes and generation exactness (sect.B3.7f)

OMC has two interchange shapes, and the generation-exactness story differs:

* **Baseband** (default): the decoder hands out legal-range video.  The
  encoder's gamut repair (`--gamut-strict`, ON by default) keeps every
  committed sample inside the legal range, so re-encoding a decode is
  byte-exact without side information.  The repair is staged (sect.51.21)
  and its cost is at clamp parity on camera content; on dense-rail graphics
  at starvation rates a measured NEG gap vs clamp remains (ledger 51.20).
* **CDR** (`--no-gamut-strict` encode + `--cdr` interchange): the repair is
  OFF; committed stays biased and unclipped and the display projection is
  the decoder's final clip.  Chains are exact BY CONSTRUCTION: 10/10
  12-generation CDR chains byte-exact across the implemented gamut
  (tests/a4_clampcdr.sh).  The encoder prints `baseband-safe: NO` whenever
  this mode is chosen, because a BASEBAND hop of such a stream destroys the
  out-of-range information and breaks exactness -- route CDR end to end.

## Script-level gates (sect.51.29)

`tests/run_script_gates.sh` complements `test_xsl`: it runs the v5.0
restore check and `G-T5-SPEND` -- a 2-generation CDR-clamp chain per arm in
which every locked generation-2 slice must spend no more bytes than its
generation-1 self.  This is the lock's induction invariant made a gate;
its violation class has broken exactness three times in the record.

