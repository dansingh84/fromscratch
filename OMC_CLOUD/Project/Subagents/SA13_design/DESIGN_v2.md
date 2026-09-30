# SA13 — BSC-1 v2 (Bracketed-Slice Codec), answer to the coordinator's review (2026-09-27/28)

Supersedes DESIGN.md where they differ; DESIGN.md §1–§3 (derivation, bitstream outline, exactness proof
sketch) still stands except as amended here. Goals in the owner's order: (1) no seams or smudges,
(2) legal by construction, (3) byte-exact generations through both hop types, (4) no noticeable bit
increase vs today's OMC (VMAF-NEG first, every plane). Half-rate is not a bar at this stage.

All new evidence is from an offline numpy model (`t8_inter.py`, 12 frames, one reference frame,
rolling refresh P = 8, 5/3 bracketed slices, zeroth-order entropy per band/mode, encoder-derived
transmitted vectors, 32-wide blocks, integer-pel). Today's OMC is measured from its REAL decodes
(`SA7_legality_v2/out/DM/*_a0.d.yuv`, exact CBR, tANS) with the same instruments (`eval_dec.py`:
negscore.sh over all 12 frames, PSNR frames 2+, level offset frames 8+, smudgegroups.py on frames
8–11, flatplane.py on frame 10). Result files: `t8_today.txt`, `t8b/c/d/e/f_results.txt`,
`t9_results.txt`, `t10_results.txt`.

## 0. Verdict per review item

| # | item | status after this round |
|---|---|---|
| 1 | A4 exactness on the cut24 shape | **NOT MET. No fixed-work, zero-bit, exact mechanism found; four measured, none closes; not proven impossible.** Natural content, cf_gfx and 95–97 % of ext10 units: exact by construction |
| 2 | lossless fallback = per-unit mode step | **Removed.** On cut24 it made 25 of 27 units lossless at 3.7–3.8 bpp — it is not a fallback, it is lossless coding, and does not fit the pipe |
| 3 | motion vectors | Transmitted; derived by every ENCODER from decoded data; the decoder never derives → no derived state in the decoder → pixel refresh heals (the S5.29 failure mode cannot occur). Cost vs source search: §3 |
| 4 | S = 8 at 1080p, latency | Measured: S = 8 vs S = 16 at 1080p ≈ −0.1 NEG at 1.0 bpp, −0.6 at 0.5. Latency 3S = 24 lines. Anchor row at S = 8 shows a +7…+23 % row-phase excess → seam risk, tuning in §2 |
| 5 | work vs ZU7EV | 3 transform passes worst case; ≈ 3–4 % of LUTs (decoder), ≈ 8 % (encoder), on-chip memory ≈ 26 %; §5 |
| 6 | inter smudges, ants, refresh | Smudge groups 0/0/0 in every run, every cell, frames 8–11 (today: spotrobotL Y 6 @0.5, 2 @1.0). Still input converges to ≤ 0.03 % changed samples/frame between refreshes, ants tail 0.01 % Y / 0 % Cb, Cr (today's codec changes 60–77 %, S5.335) |
| 7 | efficiency vs today | **The model loses on dng (−2.8 … −6.0 NEG at 0.5–1.0 bpp), matches or beats on spotrobotL (+0.3 … +0.8 at 0.5), mixed on cf_gfx.** Item (4) of the owner's order is NOT shown; causes and route in §4 |
| 8 | flatness bar | NOT met at 0.5 bpp (energy meter 30–80 % per plane) — but lower than today's real decodes at equal bits on every dng plane; plan §6 |
| 9 | colour cast | Measured and fixed: level offsets |≤ 0.06| codes on 29 of 36 plane-runs, worst +0.22 (cf_gfx Cb, D = 72); floor-rounding control −1.5/−1.6/−1.7 (a real cast). Second root found: the DC band reconstructed below cell centre (−0.6…−1.2 codes) |

## 1. Legality and exactness on rails (items 1, 2)

What is exact by construction (REXT + in-cell reconstruction with one projection round, DESIGN.md §2.6, §3):
natural cells (dng 720p/1080p, spotrobotL), cf_gfx, and the ext10 extrema except 2–5 of 102 units.

What fails — cut24 (0↔1023 plates butting onto 0…895 ramps), every mechanism measured:

| mechanism | fixed work? | zero bits? | cut24 result | file |
|---|---|---|---|---|
| in-cell projection (POCS), plain | no | yes | 0 of 162 units converge in 200 rounds | t4b |
| REXT + projection in extended domain | no | yes | 65/81 (D 14), 54/81 (D 40) unconverged at 64 rounds; stall: a 20-sample run of plate pixels stuck at −41 vs pin −40 — the pinned rail samples leave no in-cell freedom | t7, diag in NOTES |
| + rail-locked coefficients (coefficients whose support is all-rail fixed at their pinned value) | no | yes | 57 of 72 rows converge vs 60 without — worse | NOTES |
| clip + next-encoder re-read + lossless pixel residual | yes | **no**: residual 30–75 % of bits | t5 |
| emit what the next encoder reads, iterated at the first encoder, K = 1 or 4 projection rounds | no (iterations 0–8+) | yes (±1 %) | 20/81 (K 1, D 14), 11/81 (K 4, D 40) never reach a fixed point in 8 iterations | t10 |
| lossless unit fallback | yes | **no** | 25/27 units lossless, 3.7–3.8 bpp vs lossy 2.2–2.6 | t9 |

Why this shape is hard, stated plainly: REXT pins every rail sample to an exact value (lo − M or hi + M),
because the next encoder can only see "on the rail" and must map it to one number. A plate of pinned
samples next to a steep edge is an equality constraint on many samples at once; the quantised edge
coefficients' cells are Δ wide and their synthesis rings Δ/2-scale values into the plate, so the set of
in-cell coefficient values that reproduce the pins exactly is a thin (often single-point) set that
alternating projection only reaches after data-dependent iteration, and the first-encoder fixed-point
iteration has no convergence guarantee. I did not find a proof that no fixed-work mechanism exists.
**Consequence: the design meets A4 on everything measured except dense full-range rail steps (cut24);
on those units the picture is legal but may move at generation 2.** The lossless fallback is removed
(item 2): it cost 1.5 bpp over lossy on the only content that needs it and turned the whole frame lossless.

## 2. Structure changes this round

- **Rounding:** every lifting step rounds half-to-even (unbiased on ties), not floor and not the
  sign-symmetric form of DESIGN.md §2.3 (on all-positive pixel data a sign-symmetric rule still biases).
- **DC reconstruction:** the anchor row's coarsest band (it carries the slice's DC) is reconstructed at
  its cell centre (β = 1/2); other bands keep β = 3/8. With β = 3/8 on the DC band the model showed a
  uniform −0.6 … −1.2 code offset on all planes at D = 100 (per-frame, from frame 0) — the cast mechanism.
- **Inter dead zone 1.25 Δ** (intra 1.0 Δ) and a zero-vector preference (+1 per sample in the vector
  cost): still areas stop being re-coded. Also saves bits (dng720 at 1.0 bpp: +2.6 NEG vs dead zone 1.0).
- **Anchor step at S = 8:** the anchor (last) row shows +7…+23 % mean |error| over mid rows in inter
  frames (dng1080 Cb 15.65/14.14/17.42 at D 72). At S = 16 it was below the mid rows. The anchor step
  multiplier must be set per S; the AM sweep at S = 8 is in §7 (t8f). Until that row is flat in every
  plane, S = 8 carries a seam risk.
- Lossless fallback removed (§1).

## 3. Motion vectors (item 3)

Transmitted per 32-wide block, coded as the difference to the co-located vector of the previous frame.
Every encoder derives them from decoded data only (anchor rows vs reference; fixed candidate order;
smallest |v| on ties), so every generation derives the same values; the decoder only reads them.
There is no derived state in the decoder, so a refresh of the pixels restores it completely — the
S5.29 "never heals" mechanism (the decoder repeating the encoder's search on damaged history) has no
counterpart. Vector bits: 1.3–9.8 % of the stream in the model.
Cost of deriving from decoded anchors instead of searching the source: §7 (t8e, SRCMV control).

## 4. Efficiency vs today's real decodes (items 4, 7) — VMAF-NEG first

NEG at today's rates, interpolated in log-bpp between the model's two points (extrapolated where marked *):

| cell | today @0.5 | model @0.5 | today @1.0 | model @1.0 |
|---|---|---|---|---|
| dng 720p (S 8, v2) | 88.86 | 84.27 (−4.6) | 93.83 | 93.0* (−0.8) |
| dng 1080p (S 16, v1) | 90.50 | 85.3 (−5.1) | 93.54 | 89.85 (−3.7) |
| dng 1080p (S 8, v2) | 90.50 | 84.52 (−6.0) | 93.54 | 90.78 (−2.8) |
| spotrobotL (S 16, v1) | 93.47 | 94.28 (+0.8) | 97.55 | 98.6* (+1.0) |
| spotrobotL (S 8, v2) | 93.47 | 93.78 (+0.3) | 97.55 | — |
| cf_gfx (S 8, v2) | 81.06 | 82.6* (+1.5) | 92.47 | 89.35 (−3.1) |

Per-plane PSNR at nearest rates (frames 2+), e.g. dng 1080p: today @1.0 36.91/36.04/36.74; model S 8 v2
@1.08 36.42/34.81/35.71 (chroma −1.0 … −1.2 dB); spotrobotL today @0.5 39.54/42.80/46.31, model v2 @0.59
41.54/42.47/45.61. Chroma is where the model is weakest.

Reading: the structure itself was efficiency-neutral in the intra test (T2, DESIGN.md §1.3). The inter
model loses on dng and cf_gfx at 1.0 bpp. Differences between the model and today's codec that are not
structural: zeroth-order entropy vs context tANS; no RDO; no chroma step tuning; 5/3 at the finest levels
(today 9/7-M); integer-pel 32-wide vectors (today half-pel); no per-band inter mask; fixed D, no rate
control. None of these is ruled out by the bracketed structure, but I have not shown that adding them
closes a 3–6 NEG gap on dng. **Item (4) is not demonstrated; it is the second weakest point.**

## 5. Work and hardware (item 5)

Worst case per slice, decoder: synthesis + one projection round (analysis + synthesis) = 3 transform
passes; encoder: analysis, quantisation, the decoder's 3 passes, vector derivation. At 8K60 4:2:2
(3.98 Gsample/s, 400 MHz → 10 samples/clock): ≈ 14 adds + 6 shifts per sample per pass (HARDWARE.md §1
scaled to 3V×5H) → ≈ 420 17-bit adders ≈ 7.6 k LUTs ≈ 3.3 % of the ZU7EV's 230 k LUTs, plus clamps
≈ 1 %; encoder ≈ 8 %. On-chip memory: S = 8 bracket (9 rows × 7680 × 2 samples × 18 bit ≈ 2.5 Mbit) × 4
buffers ≈ 10 Mbit of ≈ 38 Mbit (URAM + BRAM) ≈ 26 %. No multipliers, no data-dependent loop counts.
Against JPEG XS (one synthesis pass) this is ≈ 3× the transform work — bounded, not "many times".
Since the projection round never fires on natural content, it could be clock-gated, but the hardware
must be provisioned for it.

## 6. Flatness (item 8)

Energy meter (flatplane.py, frame 10), today vs model at matched bits:
dng 1080p @≈0.5: today 52.1/81.4/83.5 %, model S 16 @0.51 41.7/27.8/58.0 %; @≈1.0–1.7: today @1.0
28.9/18.5/41.2 %, model @1.72 5.7/0.6/1.2 %. dng 720p @≈0.5: today 42.5/84.8/84.3 %, model @0.46
29.6/64.6/72.1 %. So the model is less flat than today at equal bits on every dng plane, but the bar
("zero flat textured blocks at ≥ 0.5 bpp") is not met by either. A narrower intra dead zone (0.75 Δ)
lowered it slightly (dng1080 @1.69 bpp 4.4/0.4/0.7 %) at −0.6 NEG.
Plan (untested, but specified so it is not "left to allocation"): (a) the τ field of DESIGN.md §2.5 set
from the decoded anchors' texture energy — dead zone 0.75 Δ in textured regions, 1.25 Δ in flat/static
ones, continuous in position, idempotent by construction; (b) chroma steps tied to luma texture;
(c) inter accumulation — in static textured areas each refresh adds detail that later inter frames keep.
The owner's eye and flatplane + texstat + level maps decide; nothing here claims it is met.

## 7. Evidence added late (see the files)
- t8e (SRCMV control): same model with vectors searched on the SOURCE rows (not canonical) — the gap
  between the two is the cost of canonical vectors.
- t8f (anchor step AM at S = 8): row-phase of the anchor row vs mid rows, every plane.
Figures are in NOTES.md (appended after these runs finished).

## 8. Latency (item 4)

T = capture S + wire S + decode one slice period (three passes provisioned at 1× hardware) = 3S lines,
deterministic. S = 8: 24 lines at every format → 720p50 0.64 ms (0.94 ms with the worst conversion),
1080p60 0.36 ms. Today's OMC: 2S + 2 = 18 lines at 720p. JPEG XS: ≈ 32 lines at 1080p per the ledger
(S5.349); I found no XS runner under .work to measure it at 720p. BSC-1 at S = 8 is below the ledger's XS
figure but 6 lines above today's OMC.

## 9. Weakest points, in order
1. cut24-shape rails: legal, but not generation-exact; no fixed-work zero-bit exact mechanism found (§1).
2. Efficiency vs today not demonstrated: −3 … −6 NEG on dng in the model, chroma weakest (§4).
3. The anchor row at S = 8 is a seam risk until its step is tuned per plane (§2, t8f).
4. Flatness bar not met (neither is today's codec) (§6).
