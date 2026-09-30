## §8.7 (f) Cycles — the field derivation and the detector, per slice

**Three terms, and all three are small.**

**1. Applying the field: a per-column offset LUT, built once per slice per plane.**
Evaluating `offset(x) = (o[j]·(SP−t) + o[j+1]·t + SP/2) >> lg` inside `coeff_shift()` would put two
multiplies on the per-coefficient path, which C3 forbids. It does not have to be there. Because
`o ∈ {−1,0,1,2,3}` — five values — each product is a shift-add at most (`3t = 2t + t`), and because
the field depends only on `x`, the whole thing is evaluated **once per plane column** into a 3-bit
LUT and read once per coefficient:

| | 720p | 1080p | 4K | 8K |
|---|---|---|---|---|
| LUT entries per slice (Y + 2 chroma at 4:2:2) | 2,560 | 3,840 | 7,680 | 15,360 |
| LUT bytes (3 bits packed) | 960 | 1,440 | 2,880 | 5,760 |
| build cost (shift-adds) | 2,560 | 3,840 | 7,680 | 15,360 |
| **as traversals of N** | 0.125 | **0.0625** | 0.0625 | 0.0625 |
| per-coefficient cost | **one LUT read**, no multiplier, no branch | | | |

**2. Deriving the field (the detector, arms B and C): one traversal, and it can be fused to zero.**
The detector reads every coefficient once, accumulating `|c|` into `ncp` buckets by band class
(LL → rail score, bands 1–3 → coarse, 7–9 → fine) — that is exactly the sweep the encoder already
makes when it copies the transform output into the per-band arrays (`src/codec.c:6077`), so in a
fused design it is **free**; costed separately it is **1.0 traversal**. The rank assignment is an
insertion sort of `ncp ≤ 120` values — 14,400 compares worst case at 8K, **0.06 traversals** —
plus a fixed histogram, and it is deterministic (ties break by index).

**3. Arm A (the ideal field) costs one extra encode attempt** (`goto encode_attempts`), i.e. `+A`
traversals. It is the ceiling arm, not a product form, and it is not costed into the table below.

**Per slice, added to DESIGN §3's budget** (A = 1, reorder, `C = 4 %`, the two-phase correction
pass from §7.6):

| format | period (cyc) | traversal @ w=8 | field LUT + detector | engine total @ w=8 | of period | @ w=16 | of period |
|---|---|---|---|---|---|---|---|
| 720p60 | 55,556 | 2,560 | 1.125 traversals | (1.57 + 1.125) × 2,560 = 6,899 | **12.4 %** | 3,450 | 6.2 % |
| 1080p60 | 73,529 | 7,680 | 1.063 | 20,222 | **27.5 %** | 10,111 | 13.8 % |
| 4K60 | 37,037 | 15,360 | 1.063 | 40,443 | **109 %** ✗ | 20,222 | **54.6 %** |
| 8K60 | 18,519 | 30,720 | 1.063 | 80,887 | ✗ | 40,443 | ✗ (base alone is 83 % @ w=16) |

With the detector **fused** into the existing band-copy sweep (the form a real design would use)
the added term falls to 0.0625–0.125 traversals and the 4K/w=8 column becomes 66 % — it fits.

**So the field is essentially free on cycles**: one LUT read per coefficient, one already-existing
traversal to derive it, no multiplier, no data-dependent loop, no added latency (everything happens
inside the slice already in flight), and 1.4 kB of LUT at 1080p. **Nothing about this mechanism is
expensive. What it does, measured, is the problem (§8.3).**
