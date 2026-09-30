## §8.3 (a) Legality — every arm is worse than doing nothing, including the oracle arm

12 frames, 0.5 bpp, `g = 2`, armed arms at the reduced rate that pays for the syntax. Repair
passes are the shipped engine's work on what the field left behind; `oob` is the committed
out-of-range count at the display decode.

| cell | base | **A — ideal field** | **B — detector, legality** | **C — detector, texture** |
|---|---|---|---|---|
| spotrobotL | **965** passes / 71 fallbacks | 1855 / 106 (**+92 %**) | 1146 / 80 (+19 %) | 1108 / 74 (+15 %) |
| volleyballgameL | **434** / 30 | 1596 / 120 (**+268 %**) | 468 / 37 (+8 %) | 514 / 40 (+18 %) |
| cf_gfx | **41** / 1 | 64 / 1 | 64 / 1 | 64 / 1 (field identically zero — §8.2) |
| dng 1080p | **80** / 0 | 942 / 77 (**+1078 %**) | 152 / 7 (+90 %) | 176 / 9 (+120 %) |
| dng 720p | **211** / 11 | 885 / 59 (**+319 %**) | 249 / 17 (+18 %) | 356 / 32 (+69 %) |
| **oob, every arm, every cell** | **0** | **0** | **0** | **0** |

**Arm A is the result that decides this.** It is the *ideal* field: it is derived from the slice's
own committed violations after a first reconstruction, so it knows exactly where the illegality is
— knowledge no shippable detector can have — and it is allowed a second encode to use it. It is
the **worst arm on every cell**, by 92 % to 1078 %. A mechanism whose oracle arm is far worse than
doing nothing is not failing for want of a better detector.

**The mechanism of the failure, and it is §U's mechanism at spatial granularity.** The field is
mean-zero by construction (§8.1), so every rung of extra precision at an edge is paid for by a
rung of coarseness somewhere else in the same slice. Measured, **the coarsened spans manufacture
more new rail crossings than the refined spans remove** — the coarse bands ring harder there, which
is exactly what §U measured when it coarsened them globally and what §V measured from the other
side. Spreading the same total precision around inside the slice does not change that arithmetic;
it only decides where the ringing happens.

**Residue and unconverged at the K that fits** were not computed per arm: with every arm's repair
passes *above* the base, the K-that-fits question (720p 5, 1080p 2, 4K 1 at 16 spc) can only be
worse than the base's, which §T already measured as missing the zero-rung bar. Running the escape
probe on top of a field that increased the violation count would have priced a combination that
is already behind on its first term.

## §8.4 (b)(c)(d) Flatness, chroma and quality at equal CBR — worse on every plane of every cell

Per-plane PSNR against the source, 12 frames, **net of the field's syntax cost** (armed runs at
0.4906 / 0.4807 / 0.4774 bpp against a base at 0.5000).

| cell | arm | Y | Cb | Cr | worst frame Y |
|---|---|---|---|---|---|
| spotrobotL | base | 39.491 | 42.636 | 46.103 | 36.51 |
| | A | **−0.455** | −0.296 | −0.235 | 36.92 |
| | B | **−0.913** | −0.260 | −0.071 | 36.37 |
| | C | −0.796 | −0.274 | −0.105 | 35.63 |
| volleyballgameL | base | 40.652 | 43.119 | 45.617 | 35.96 |
| | A | **−2.410** | −0.350 | −0.429 | 35.08 |
| | B | −1.915 | **−0.574** | −0.394 | 34.79 |
| | C | −1.863 | −0.575 | −0.441 | 34.49 |
| cf_gfx | base | 29.657 | 33.347 | 33.343 | 26.46 |
| | A/B/C (field ≡ 0) | −0.427 | −0.109 | −0.093 | 26.11 |
| dng 1080p | base | 35.101 | 34.629 | 35.712 | 33.31 |
| | A | −0.765 | −0.163 | −0.168 | 32.73 |
| | B | **−1.618** | −0.291 | −0.201 | 32.40 |
| | C | −1.466 | −0.328 | −0.218 | 32.46 |
| dng 720p | base | 34.788 | 35.998 | 37.033 | 31.43 |
| | A | −0.773 | −0.112 | −0.116 | 30.91 |
| | B | −1.016 | −0.197 | −0.128 | 30.53 |
| | C | **−1.525** | −0.317 | −0.233 | 30.50 |

**Not one plane of one cell of one arm improves.** The bar is ≤ 0.1 dB worse on any plane; the
best single figure in the table is −0.071 dB (spotrobotL Cr, arm B) and the worst is −2.410 dB.

**Energy-meter flat share per plane** (`flatplane.py`, frames 8 and 11, mean of the two) —
**a number, not a verdict**, per COMMON_RULES:

| cell | base Y / Cb / Cr | Δ arm A | Δ arm B | Δ arm C |
|---|---|---|---|---|
| spotrobotL | 51.5 / 66.5 / 70.0 | +0.33 / +1.29 / +0.48 | +0.33 / **+4.20** / **+2.91** | +0.98 / +3.56 / +2.88 |
| volleyballgameL | 37.5 / 57.6 / 63.0 | +0.78 / +3.07 / +0.55 | +1.66 / **+4.98** / +2.54 | **+2.55** / **+6.27** / +2.92 |
| cf_gfx | 47.5 / 86.4 / 82.5 | +0.11 / +0.45 / +3.66 | same | same |
| dng 1080p | 52.4 / 81.3 / 83.8 | +1.45 / +2.70 / +1.84 | **+8.18** / +5.11 / +4.09 | **+8.72** / +6.48 / +3.88 |
| dng 720p | 42.1 / 84.2 / 83.9 | +1.59 / +1.18 / +1.17 | +5.42 / +0.90 / +0.48 | +6.29 / +3.86 / +2.56 |

**The energy meter says the flat share rises on every plane of every cell under every arm**,
including **arm C**, whose entire purpose was to put precision where the source has texture the
base plan zeroes. The bar was "not up on any cell, down where the field targets texture"; it is up
everywhere and by the most on the cell where the field is most active. Chroma is hit harder than
luma on the two motion cells (+4.2 to +6.3 points on Cb).

**The eye, on the level maps.** `renders/{spot,dng720}_f8_field_a{0,2,3}_{lvl,absdiff}_{Y,Cb,Cr}.png`,
frame 8, steady state, every plane, control-point grid and slice grid marked. The
block-mean extremes tell the story before the eye does: spotrobotL Y goes from **−37.0 … +18.4**
codes in the base to **−283.2 … +125.9** under arm B and −57.8 … +16.2 under arm C, and the worst
sample error from 190 to 420 codes. Looking at `spot_f8_field_a2_lvl_Y.png`, the base's three
saturated streaks become **more numerous and much brighter** — a new saturated red/blue pair across
the top right, a bright blue band centre-left and another centre-right. **The field introduces a
new smudge class, and a severe one.** It does not align with the control-point grid (below); it
follows the picture's horizontal structures.
