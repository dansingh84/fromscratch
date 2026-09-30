# CLP-1 — revision 4 (response to the review of DESIGN_v3)

**SA12, 2026-09-27.** This revision builds on revisions 1–3 (`DESIGN.md`, `DESIGN_v2.md`, `DESIGN_v3.md`). What is not changed here stands.

**Priority order (owner):**
1. No seams or smudges.
2. Legal by construction.
3. Byte-exact generations.
4. No noticeable bitrate increase over today, VMAF-NEG first, every plane.

**Scope of the numbers.** Everything is the sequence model (`notes/seq.py`), not a codec build. Steady-state inter frames 2–11 are compared with today's **real** decodes. Rates are **coded** rates: the model's entropy estimate × the static-tANS overhead model `notes/cost2.py` (§4).

**Final configuration used throughout.** Overlapped-block MC, MC context below the slice, encoder error continuation. The intra chroma reshape is included only where stated.

---

## 1. T0 — legal anchor bracketing for intra slices: FAILS on natural content (measured) → dropped

**What was built** (`notes/anchor.py`, legal, acyclic, generation-2 exact):
- Each slice first codes its last row as a 1-D legal horizontal pyramid, the anchor.
- The 16-row pyramid is then coded with that row known: its boxes collapse to the decoded values, and single-value coefficients are derived, not sent.
- The next slice's top uses the anchor as context.

**Results.** Intra f8, same Qf. Excess = slice-boundary step minus the internal half-slice step, relative to the other rows.

| cell | arm | bpp (ent) | VMAF-NEG | PSNR Y/Cb/Cr | excess Y/Cb/Cr | first / last row ratio (Y) | gen 2 |
|---|---|---|---|---|---|---|---|
| spot 1080p (16-row) | plain | 0.478 | 91.90 | 41.24/42.76/46.20 | +0.16/+0.18/+0.32 | 0.99 / 1.15 | identical |
| | **anchor** | 0.532 (+11 %) | 91.92 | 40.71/42.25/45.51 | **+0.21/+0.27/+0.50** | 0.95 / 1.03 | identical |
| dng720 (8-row) | plain | 1.174 | 91.46 | 38.25/36.93/37.95 | +0.07/+0.07/+0.07 | 1.00 / 1.07 | identical |
| | **anchor** | 1.270 (+8 %) | 91.44 | 37.50/36.29/37.41 | +0.07/+0.08/+0.07 | 0.94 / 0.95 | identical |
| cf_gfx (8-row) | plain | 1.692 | 92.77 | 36.92/36.02/36.44 | +0.06/+0.12/+0.11 | 0.99 / 1.07 | identical |
| | **anchor** | 1.804 (+7 %) | 92.72 | 36.13/35.14/35.60 | +0.06/+0.12/+0.12 | 0.93 / 0.97 | identical |

- Anchoring **flattens the per-row error magnitude**: first and last rows ≈ 0.94–0.97. That is the property S5.362 reported ("boundary-row error flat").
- It does **not** reduce the error *step* across the boundary: unchanged, or worse on spot.
- It costs 7–11 % more bits and 0.5–0.8 dB.
- **Why, and what it means for S5.362 and SA14.** The step is the discontinuity between two *independently decided* reconstructions. The tall-slice test in revision 3 isolates the causal cut as the sole cause (+0.01 without slices). A shared anchor row gives both sides a common *value*, but each side's residual is still decided without the other. "Flat boundary-row error", as measured for bracketed slices (S5.362) and shifted causal slices (SA14: row ratio 1.05), is a different statistic from the absence of a step.
- **I see no latency-free, legal remedy for the intra-slice step in this family.** The only full remedy found is a vertical transform that crosses slices (the tall slice). That costs latency and loss containment (S5.349).

**Intra-slice seam status:** +0.16/+0.18/+0.32 on spot and +0.07 on dng720. That is about today's (+0.15/+0.14/+0.30 on spot). **Inter slices:** +0.04/+0.03/+0.06 (revision 3).

## 2. Chroma reshape: renders for the owner's eye, and dark-area discolouration (measured)

**Renders.** `out/eye/`, 88 PNGs. Cell: the owner's marked 720p cell (dng720), steady-state frames **8 and 11**, three decodes at matched coded rate:
- `model_noreshape_0.52bpp`: final configuration, coded 0.518 bpp;
- `model_reshape_0.52bpp`: final configuration + intra chroma reshape, coded 0.522 bpp (Qf 6.5, rate-matched);
- `today_0.5bpp`: today's real decode.

Per decode and frame, each also as `_grid.png` (red 1-px lines at the 8-row slice grid and every 32 luma / 16 chroma columns, same raster):
- `_decode.png`: full-frame colour;
- `_level_{Y,Cb,Cr}.png`: 8×8 block mean of decode − source, red = too high, blue = too low, full scale ±10 codes;
- `_absdiff_{Y,Cb,Cr}.png`: |decode − source| × 8.

Plus `source_f8/f11_decode.png`.

**Dark areas** (source luma below 25 % of range, ≈ 246 k chroma samples per frame; `notes/render4.py`):

| decode | frame | mean signed error Cb / Cr (codes) | mean \|err\| Cb / Cr | chroma magnitude ratio, decode / source |
|---|---|---|---|---|
| model, no reshape | f8 | +0.00 / +0.07 | 11.94 / 11.08 | 0.830 |
| **model, reshape** | f8 | +0.05 / +0.08 | 12.53 / 11.54 | **0.865** |
| today, real | f8 | **+0.22 / −0.16** | 11.70 / 11.00 | 0.857 |
| model, no reshape | f11 | +0.02 / −0.00 | 11.96 / 11.10 | 0.832 |
| **model, reshape** | f11 | −0.04 / −0.08 | 12.55 / 11.59 | **0.873** |
| today, real | f11 | **+0.21 / −0.15** | 12.17 / 11.31 | 0.848 |

**Reading.**
- **No colour cast in dark areas:** the model's mean signed chroma error is within ±0.08 code; today's is +0.2 Cb / −0.15 Cr.
- The reshape's chroma-PSNR cost shows up as **+0.5 code of mean absolute error, spread as noise**, not as a colour shift or loss of saturation.
- The reshape *raises* the dark-area chroma magnitude ratio (0.865/0.873 vs 0.830/0.832 without it; today 0.857/0.848). Faint dark chroma texture is kept rather than flattened.
- By these numbers the Cr PSNR loss is **not discolouration (G6)**. The eye decides from the renders.

**Rate note.** In a sequence the reshape costs more than it did on single frames (+13 % bits at the same Qf, 0.518 → 0.573 coded), because refresh slices are intra. At matched coded rate (Qf 6.5) it is within the budget. The flatness-vs-PSNR trade is the owner's call from the renders.

## 3. T8 — mid-stream join WITH motion vectors, and a direct stream comparison (measured)

**Clean-region rules implemented** (`SEQ_CLEAN`):
1. A contiguous top-down refresh sweep (1/8 of the frame per frame, cycle 8).
2. During a cycle, a slice inside the already-refreshed region reads only clean data:
   - its MC reference rows, clamped to the clean rows of frame t−1;
   - its overlapped-block neighbour vectors: blocks outside the region count as zero;
   - its context from below: the clamped reference;
   - its canonical vectors, derived from t−1 and t−2 restricted to rows clean in both. Blocks refreshed at t−1 get a zero vector.
3. The joining encoder:
   - codes a slice intra iff intra coding reproduces it;
   - learns the sweep phase from the previous frame's detected refresh group;
   - otherwise runs the same canonical rules.

**Direct stream comparison.** A per-slice md5 over every index array plus the intra/inter flag, all planes, for both encoders (`*.hash.json`, `notes/joincmp.py`). With the per-frame vector field, which is a deterministic function of the same decoded frames, this is the stream.

**Graphics** (cf_gfx, 12 frames, join at 3):
- Before the next cycle starts (frames 3–7), nothing locks.
- From frame 8 the refreshed region matches in **picture and symbols**: 4, 8, 12, 16 of 32 slices on frames 8–11. The clip ends mid-cycle.
- Gen 1 re-encoded is byte-identical (picture, indices, vectors).

**spotrobotL 1080p, first run** (20 frames, joins at 3, 5 and 7):
- All three joins reached **68/68 slices identical in pictures and symbols at frame 15**.
- They then fell back to 57–62 slices at frames 16–19.
- **Cause:** at the cycle wrap (frame 16), the vector rule read frame t−2 = 14, whose last refresh group had not yet been refreshed in that cycle.

**Added rule (normative for the canonical vector derivation):** at the first frame of a cycle, vector derivation may not read frame t−2 rows of the last refresh group; blocks there get a zero vector.

**Re-run** (24 frames, joins at 3 and 7), per frame: slices identical in picture / in coded symbols, out of 68:

| frame | 3 | 8 | 10 | 12 | 14 | 15 | 16 | 17–23 |
|---|---|---|---|---|---|---|---|---|
| join at 3 | 6/8 | 9/10 | 27/27 | 45/45 | 63/63 | **68/68** | 68/66 | **68/68 every frame** |
| join at 7 | — | 12/11 | 27/30 | 45/46 | 63/63 | **68/68** | 68/66 | **68/68 every frame** |

- The join at 7 starts at frame 7 (3/4 slices).
- **Pictures are identical on every sample from frame 15, and the streams are byte-identical from frame 17 to the end of the sequence.**
- Frame 16, the wrap: identical pictures, but 2 slices carry a different, equivalent description. Gen 1 does not yet apply the "intra if intra reproduces" read to its own inter slices. Adding that makes the descriptions canonical. It is specified, not yet modelled.
- **Cost of the clean-region rules to gen 1:** 0.401 vs 0.414 coded bpp at equal PSNR (39.92/42.04/45.39 vs 39.91/42.03/45.38). That is not worse. The runs differ in length (24 vs 20 frames), so the sign is not meaningful.

**Bound.** The lock comes one full cycle after the first cycle start following the join: at most 8 + 8 + 1 = 17 frames. The join transient (frames before the lock) is one ordinary lossy generation, not accumulating.

**Bound (measured).** Join at 3: locked at 15, byte-identical from 17. Join at 7: the same. That is within one cycle after the next cycle start, plus one frame.

## 4. Bits guard on a second motion cell: highwaydriveL (measured)

Today real, `.work/v537` binaries run read-only: 0.504 bpp, 0 damaged slices. Model at three Qf plus two fine step multipliers (the model's power-of-two steps move rate in large jumps). Steady-state f2–11, VMAF-NEG first:

| | coded bpp | **VMAF-NEG** | PSNR Y/Cb/Cr | flat % f8 Y/Cb/Cr | ants tail % Y/Cb/Cr (source 2.83/11.73/17.24) |
|---|---|---|---|---|---|
| **today, real** | 0.504 | **93.73** | 41.05/47.31/43.90 | — | — |
| model, Qf 6 | 0.283 | 89.21 | 39.92/46.82/43.66 | 46.6/60.7/83.4 | 0.19/0.56/0.12 |
| model, Qf 5.75 | 0.311 | 90.45 | 40.20/47.03/43.75 | | |
| model, Qf 6, steps ×0.7 | 0.409 | 92.76 | 41.41/47.52/44.12 | 39.9/50.6/69.6 | |
| **model, Qf 6, steps ×0.6** | **0.491** | **93.92** | **42.08/47.84/44.38** | 35.7/46.3/60.5 | |
| model, Qf 5.5 | 0.613 | 94.72 | 42.83/48.10/44.69 | 26.6/44.2/49.0 | 0.14/1.76/0.94 |
| **model at 0.491 (below today's 0.504)** | 0.491 | **93.92 (+0.19)** | **+1.03 / +0.53 / +0.48 dB** | | |

Summary with revision 3's cells, at today's 0.5 bpp, coded rates:

| cell | model NEG | today NEG | Δ NEG | ΔPSNR Y/Cb/Cr (dB) |
|---|---|---|---|---|
| dng720 | ≈ 91.3 | 90.16 | +1.1 | +2.1 / +0.25 / +0.4 |
| spot | ≈ 94.05 | 93.76 | +0.3 | +1.4 / −0.06 / −0.14 |
| highwaydriveL | ≥ 93.92 (at 0.491) | 93.73 | ≥ +0.2 | ≥ +1.0 / +0.5 / +0.5 |

## 5. Status against the owner's list

| Goal | Status (model) |
|---|---|
| 1. No seams or smudges | **Smudges:** the owner's grille classes are 0 % vs today's 13–14 % (revision 3). **Inter seams:** +0.03…0.06 excess vs today's +0.14…0.30. **Intra-slice seams ≈ today's** (+0.07 at 8-row, +0.16/+0.18/+0.32 at 16-row). The one tested remedy, T0, failed. |
| 2. Legal by construction | Holds; 0 out-of-range in every run |
| 3. Byte-exact generations | Gen-2 identity in every configuration tested, including the clean-region rules. **Mid-stream join with motion vectors:** pictures identical from frame 15, streams byte-identical from frame 17 to the end (joins at 3 and 7, spot 1080p). |
| 4. No more bits than today | NEG +1.1 / +0.3 / ≥ +0.2 on dng720 / spot / highwaydriveL at equal coded bits; per-plane PSNR as in §4 |

## 6. Weakest point

**The intra-slice seam.** Every intra slice (frames 0–1, cuts, and one rolling refresh group per frame) carries a boundary error step about equal to today's codec: +0.16/+0.18/+0.32 Y/Cb/Cr on 16-row slices, +0.07 on 8-row slices.

- The cause is proven: the causal slice cut.
- Neither anchor bracketing (measured, T0) nor any latency-free legal variant I can derive removes it.
- Two directions I see, both costing a constraint, so they need the owner's steer:
  - (a) Slice height 8 on every format. The step is smaller at 8 rows (+0.07); cost: a rate loss to measure, and more slice headers.
  - (b) A vertical transform crossing one slice boundary with a one-slice-period delay. Cost: +16 lines of latency at 1080p (≈ 50 vs XS ≈ 32 lines) and weaker loss containment.

## 7. Files (new in revision 4)

- `notes/anchor.py`: T0.
- `notes/render4.py`: eye renders and the dark-area statistic.
- `notes/joincmp.py`: picture and symbol join comparison.
- `notes/seq.py`: now with `SEQ_CLEAN`, `SEQ_CRESHAPE`, per-slice symbol hashes.
- `out/eye/`: renders.
- `out/v4/`: anchor, join, highwaydriveL and today's highwaydriveL decode logs.
