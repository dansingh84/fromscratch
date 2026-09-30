# SA13 — working notes (design only)

## Structural path being pursued (2026-09-27, first entry)

Principle: **every output sample is `clamp(prediction from already-final samples + its own
quantised innovation)`** — a closed-loop, pixel-owned structure. Consequences, if it holds:
- legality by construction (one compare-and-clamp per sample, no iteration, no clip of a
  synthesis — there is no synthesis),
- generation exactness by a closed-form per-sample rule (canonical rail index = the smallest
  index whose reconstruction reaches the rail),
- the quantiser step and prediction mode are readable from the picture (odd-dyadic
  reconstruction points, per-sample count-trailing-zeros), ties broken by fewest bits, so the
  next encoder never searches,
- error is bounded per sample by the dead zone (L-infinity), so texture above ~one step cannot be
  flattened anywhere, and the error field has no block/slice structure by construction.

I KNOW this is the predict-only family: DESIGN3 (S5.212, −3 dB), S5.349 review (acyclic ⇒
predict-only, −2.4…−4.8 dB PSNR, chroma worst), S5.353 S2/S5b. I pursue it only because
(a) those verdicts were PSNR verdicts and VMAF-NEG is now primary (S5.358 rule); (b) the
tested forms were separable (row/column 2-tap); I test a non-separable, diagonal-first
(quincunx-order) interpolation where every detail sample is predicted from four final
neighbours; (c) I weigh it against the same artifact checks as the baseline.
If the first test shows the deficit is real on VMAF-NEG too, I say so and change path.

## Tests
- T1 (intra, full frame, numpy): 5/3 5-level baseline vs closed-loop hierarchical
  (separable control 'sep', quincunx-order 'qx', directional 'qxd'); PSNR Y/Cb/Cr and
  VMAF-NEG at matched bits (zeroth-order entropy per band / per level-phase).
  Script: t1_structure.py. Results: t1_results.txt.

## T1 verdict (2026-09-27): the pixel-owned closed-loop path is FALSIFIED on VMAF-NEG too
t1_results.txt. At useful rates every closed-loop hierarchical arm (separable, quincunx-order,
directional; uniform or ramped steps) is far below plain 5/3 on VMAF-NEG, not just PSNR:
dng 1080p ~1.1-1.25 bpp NEG 85.4 (best CL) vs 91.1 (5/3 @1.05); spotrobotL ~0.4-0.45 bpp 82.5 vs 91.4;
cf_gfx ~1.7 bpp 89.2 vs 92.8 (5/3 @1.53).  Parity only at >= 4 bpp.  Quincunx order does not help:
the coarse samples are the same subsampled pixels whatever the order (aliasing is the cost).
=> Path changed: keep an update (anti-aliasing) transform; legality must come from IN-CELL
reconstruction (the only zero-bit, zero-dB exact family: pigeonhole argument in DESIGN.md).

## T2 (2026-09-27): BRACKETED slice structure -- seam root removed at no efficiency cost
t2_results.txt.  Slice = its last row (anchor, coded first as a 1-D row) + interior rows coded by a
vertical 5/3 on the interval [anchor of the slice above, own anchor] with both ends FIXED (never
mirrored, never updated).  No row below is ever needed -> no mirror -> no blend.
vs OMC-shape slice-local 2-level (sl2): equal or better rate at equal NEG (spot: ~10 % fewer bits),
row-phase |err| flat (sl2 last row +20..+30 %).  vs full-frame continuous 5/3 (ff, not a
candidate): dng -14 %, spot ~0 %, d720 ~ -3 %.  Anchor step: AM=3 (1080p); 720p S=8 needs its own.
Vertical predict-only variant (bp, legality would become 1-D per row): +15..30 % bits -> rejected.
Next: T4 = does in-cell legalisation finish in bounded work on the bracketed structure (rails)?

## T4/T5/T6/T7 (2026-09-27): legality + exactness on RAILS (full-range 0/1023 arms)
- T4 (t4b_results.txt): plain in-cell alternating projection on the bracketed structure: natural and
  cf_gfx converge in <= 1-3 rounds; cut24 and ext10 do NOT converge in 200 rounds, even on the 1-D
  anchor rows.  (t4_results.txt used [4,1019] on 0..1023 arms = infeasible; superseded.)
- T5 (t5_results.txt): fixed-work "clip + next-encoder re-read + lossless pixel residual r":
  exact by construction, 0-5 % bits on natural, but r = 30-75 % of the bits on cut24/ext10 -> dead.
- T6 (rail extension, REXT): push pixels that sit exactly on a rail M codes outside it before the
  transform (every encoder, same rule, read from the picture).  cut24: +4 dB (rails exact), bits
  slightly lower, but flips from rail-straddling coefficients remain.
- T7 (t7_results.txt): REXT + in-cell projection in the EXTENDED domain (rail pixels pinned at +-M,
  others in [lo+1, hi-1]): natural 100 % within 1 round; cf_gfx max 3; ext10 95 % within 2 rounds
  (5/102 units unconverged at 64); cut24 still fails (steps 1023->0 butting onto a 0..1023 ramp).
- Lossless cost of the rail frames (zeroth order): cut24 1.9 bpp, ext10 1.7 bpp (natural 9.6).
=> Weakest point of the design = full-range steps adjacent to near-rail gradients (cut24 shape):
   no fixed-work, zero-bit exact legaliser found.

## Status 2026-09-27 (end of first pass)
DESIGN.md written: BSC-1 = bracketed slices + REXT + in-cell reconstruction (K_max = 1, lossless
fallback) + derived decisions + idempotent index choice.  Weakest point: cut24-shape rails (no
fixed-work zero-bit exact legaliser).  Half-rate mandate not demonstrated.  Awaiting review.
