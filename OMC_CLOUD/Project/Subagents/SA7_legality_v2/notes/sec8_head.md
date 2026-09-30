# §8. Loop iteration 3 — the CONTINUOUS QUANTISER FIELD (L-I20), step 1

**The idea (coordinator).** A per-plane, per-slice field of 3-bit step offsets (−1…+3 rungs) at one
control point per 64 luma columns, applied to **every** band's step at that position by integer
interpolation, with the plan computed *with* the field so exact CBR still holds; 1.8 % fixed syntax
cost. Arms: **A** = the ideal field from the escape demand map (the ceiling); **B** = a detector
field, legality-driven; **C** = a detector field, edge + texture driven.

## §8.1 What I built, and the two things I had to decide

Probe `[SA7-FIELD]`, `ptree/src/sa7_field.inc` + three hooks in `ptree/src/codec.c`
(`diffs/sa7_field.diff`). Byte-inert with `OMC_SA7F` unset.

**Geometry, stated.** Control points sit at the **same picture positions in every plane**: spacing
is 64 columns in luma and `64·pw/W` in each plane's own columns — **32 chroma columns at 4:2:2** —
so `ncp = W/64 + 2` per plane (32 at 1080p, 22 at 720p, 9 on cf_gfx). Interpolation is
`offset(x) = (o[j]·(SP−t) + o[j+1]·t + SP/2) >> lg`, `j = x >> lg`, `t = x − (j<<lg)`: a continuous
integer field with **no region and no region edge**, per the owner's zero-steps ruling. The field
is subtracted from **every** band's shift inside `coeff_shift()` (`src/codec.c:1079`), clamped to
`[0, OMC_MAX_SHIFT]`, and band 0 stays capped at `OMC_LL_CAP` so the anti-banding guarantee is
untouched.

**How the plan reads the field.** The field is derived **before** the rate ladder runs, and
`coeff_shift()` — which the ladder, the quantiser, the bit estimator, the entropy coder and the
reconstruction all call — returns the field-modified shift. So the ladder searches `(prof, Q,
n_steps, partial)` *with the field in force* and its coded-size check is what holds exact CBR:
if the field costs bits, the ladder answers by moving `Q`, exactly as it does for any other plan
change. Nothing extra is needed, and nothing extra was added. Exact CBR is verified below.

**The first thing I had to decide: the field must be MEAN-ZERO, and this is not a detail.** My
first detector used absolute thresholds and produced a field with mean **+0.92 rungs** — a net
precision increase. At exact CBR the ladder took it straight back through `Q`, reproducing
S5.188's failure exactly (spotrobotL 4 frames: 738 repair passes against a base of 377). The field
is a **redistribution**, so the assignment is rank-based against a fixed histogram whose signed sum
is exactly zero: with strength `g`, the top `ncp·g/100` control points get +3, the next `2g/100`
get +2, the next `5g/100` get +1, the bottom `3n3+2n2+n1` get −1 and the rest 0. Ties break by
index, so it is deterministic. `g` is swept (§8.2).

**The second: the syntax is charged, not assumed.** Each armed run is encoded at
`bpp × (1 − 3·ncp·3/slice_bits)` — **1.88 % at 1080p, 3.87 % at 720p, 4.52 % on cf_gfx** (the
coordinator's 1.8 % is the 1080p figure; it is bigger on narrow pictures, and that is stated rather
than averaged away). The base runs at the full rate. Every comparison below is therefore at equal
total rate with the field's syntax paid for.
