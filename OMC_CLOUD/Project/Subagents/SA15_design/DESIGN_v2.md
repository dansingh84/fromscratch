# SA15 — CPP-LL, round 2 (answers to the coordinator's review of DESIGN.md)

Status: IN PROGRESS (sections are filled as runs finish). All numbers are numpy MODELS on real footage.
New in round 2: every rate below is a REAL CODE LENGTH from static tables (tANS-exact within table
quantisation: 1/2048 probability resolution, 11-bit state flush per plane per packet, Exp-Golomb escapes,
16-bit slice header, vectors coded), not "entropy x 1.10". Tables trained on footage disjoint from every test
cell (section R4). Scripts: `notes/cpp2.py` (plane codec v2), `notes/seq2.py` (sequence codec: rate control,
refresh, decoder simulation), `notes/run2.py`, `notes/eval2.py`; logs `out/r2/log/`, results `out/r2/`.

## Changes to the design (root causes, not patches)

1. **Symbols are open-loop** (quantised from the picture's own TS coefficients; the decoder adds the
   reconstructed predictor). WHY: with closed-loop symbols the bits of a candidate step depend on the
   reconstruction at that step, so exact CBR needs trial coding (a retry) or a guard. Open-loop makes the
   exact code length of every candidate knot computable in one pass (XS-style budget evaluation).
   Exactness is unchanged: a decoded picture re-analysed returns exactly its own values, because its own
   predictors ARE the decoder's predictors. Cost (T11, intra, matched rate, `out/t11_openloop.txt`):
   -0.07/-0.08/-0.07 dB dng720, -0.02/-0.03/-0.03 spot, -0.08/-0.08/-0.09 cf_gfx (Y/Cb/Cr).
2. **No per-coefficient state; still content kept by knot stability.** (A per-coefficient step memory was
   built first and REJECTED after the owner's 8K memory ruling: 7 bits of state per coefficient cost
   +14 bit/sample of DDR traffic and frame-sized storage; `notes/*_stepmemory_rejected.py`.) Root: the
   memory existed only because a knot change requantises still content. Removed at that root: a kept value
   lives on the CURRENT field (v_keep = R(Q(t_mc, D), D)); the rate controller keeps a slice's knot from the
   previous frame whenever that knot fits (and is at most half an octave coarser than the finest fitting
   one), so in steady content the knot, and therefore the still picture, does not change; it changes only
   when the pipe forces it. Keep decision: exact reproduction first (decoded input), then keep if
   |t - v_keep| <= 0.75 D or the kept value is closer than the requantised one.
6. **Canonical motion vectors from decoded history, measured during the previous frame (no extra read).** Vectors for frame t = block match of D(t-1) against D(t-2), computed while frame t-1 is coded (its rows as they are reconstructed against the t-2 band already resident on chip), stored per block (small). (A variant searching the current picture and re-describing with vectors searched on the reconstruction was built and abandoned: the emitted description's costs differ from those the knot was chosen with, which forces extra plan-reading passes.) Former text, kept for the record: **Canonical motion vectors from the current picture, no second reference frame.** Vectors are the
   block-match of the CURRENT picture against the reference (encoder pass on the source), and the emitted
   description uses the vectors of the same search run on the encoder's own reconstruction against the
   reference -- the function every later encoder computes from its input. Because the reconstruction does
   not depend on the vectors (lattice lock), re-describing with the canonical vectors changes symbols only.
   The previous design searched D(t-1) against D(t-2) (an extra reference frame read, rejected for DDR).
7. **Implementable tables.** 10 band classes (per luma/chroma: LL, horizontal-only levels, level 1,
   level-0 HH, level-0 LH/HL) x 2 modes (hinted / hint-free) x 3 contexts, L = 1024: 60 tables, 1.1 Mbit.
   (The first round-2 tables had 720 tables of L = 2048 = 26.5 Mbit and were not implementable.)
3. **Exact CBR without a guard** (section R1).
4. **Canonical plan recovery with legal intervals** (section R8): the knot of a slice is recovered from the
   picture as the coarsest candidate under which every coefficient is reproducible, with each coefficient's
   legal interval computed from the picture's own pyramid (clamped boundary values count as reproducible);
   the first encoder applies the same rule to its own reconstruction (one predetermined re-description).
5. **Canonical index = smallest-magnitude index that reproduces the value** (fixes the cf_gfx 0.2 bpp +5.6 %
   and removes the boundary-preference rule from the source path; section R7).

## R7 — legality cost and harm (MEASURED, `notes/t12_harm.py`, `out/t12_harm.txt`)
Same open-loop choices decoded with and without the decoder's legal intervals ("unconstrained" = no boxes,
then clipped). All planes pooled.

| cell | bpp | bits legal/unconstrained | samples changed by legality | toward source / away | max excess over clip (codes) | MSE legal / clip |
|---|---|---|---|---|---|---|
| cf_gfx | 3.05 / 1.41 / 0.67 / 0.36 / 0.17 | 1.0000 / 1.0000 / 1.0000 / 1.0000 / 1.0004 | 4 / 8 / 20 / 215 / 1701 | 3/1, 5/3, 8/12, 126/89, 843/856 | 11 / 6 / 41 / 43 / 175 | equal (<0.6 %) |
| dng720 | 2.28 / 0.99 / 0.49 / 0.26 / 0.12 | 1.0000 / 1.0000 / 1.0000 / 1.0001 / 1.0025 | 16 / 13 / 312 / 2733 / 8955 | 9/7, 7/5, 187/125, 1473/1250, 4507/4427 | 9 / 5 / 72 / 130 / 259 | equal |
| cut24 (rail plates) | 2.23 / 1.63 / 1.09 / 0.60 / 0.30 | 1.019 / 1.038 / 1.103 / 1.088 / 1.136 | 21k-30k | ~3:1 toward | 12 / 35 / 51 / 130 / 213 | -1 % / +12 % / +15 % / -1 % / -8 % |
| ext10 (rail extremes) | 0.67 / 0.52 / 0.40 / 0.29 / 0.09 | 1.144 / 1.112 / 1.159 / 1.416 / 2.117 | 86k-99k | ~2:1 toward | 12 / 27 / 30 / 209 / 395 | -17 % / -19 % / -34 % / +4 % / +9 % |

Reading. (a) Natural content and graphics: zero bit cost at every rate (0.12-3 bpp) and equal MSE; the
+5.6 % at cf_gfx 0.2 bpp of round 1 is gone — its root was the round-1 source-side rule "prefer a clamped
neighbour index", removed; the canonical index is now defined only by the decoded value. (b) Rail plates
(cut24, ext): the legal stream costs +2..+16 % bits at contribution rates (+40..+110 % at 0.1-0.3 bpp).
Root: a source sample exactly ON a rail sits on its coefficient's interval boundary; to be re-encodable
the boundary must be reproduced by an index, and the dead-zone index of the source may fall one step short
of it, so the encoder spends the reaching index (the value is then exact at the rail: MSE is 17-34 %
LOWER at 0.4-0.7 bpp on ext10, i.e. part of the bits buy quality). A boundary-snap reconstruction that
would remove this cost was built and REJECTED (`notes/cpp2_snap_rejected.py`): it snaps coarse-band means
to the rails (MSE x7.7 at 0.12 bpp dng720). OPEN: legality is not free on dense rail plates.
(c) "Never away": NOT met. Every clamp keeps the pair mean (that is what makes the next encoder recover
the coarser levels exactly), so the partner sample moves by the same amount in the opposite direction;
it moves away from the source when the pair mean itself was quantised toward the rail. Measured split
is ~50/50 on natural content (few samples: 13-312 per frame at >= 0.5 bpp), ~2-3:1 toward on rail plates;
largest excess over a clip 5-72 codes at >= 0.5 bpp, up to 259-395 codes at 0.1 bpp (coarse means).
This is structural for any mean-preserving (exactness-preserving) legaliser; the only per-sample-harmless
legaliser is a clip, and a clip is what breaks exactness (round 1, T1: the clip-compatible family costs
1.4-5 dB).

## R11 — latency margin and DDR (ESTIMATED)
- A2 bar is sub-1 ms including conversion (the coordinator cites C3's margin; C3 is the FPGA-resource
  margin clause, A2 the latency clause). 720p50 with the 3:1 converter: 18.2 + 19 lines = 0.991 ms, margin
  0.009 ms (0.9 %) — too thin to call "comfortable". Options measured (T13, `out/t13_lv.txt`): Lv = 1 at
  720p-class (look-ahead 4 lines): 14.2 + 19 lines = 0.885 ms (11.5 % margin) at a cost of -0.40/-0.27/-0.26
  dB (dng720) and -0.33/-0.27/-0.24 dB (cf_gfx) intra. Lv = 2 with 2:1 or 3:2 conversion: 0.831 / 0.751 ms
  (17 % / 25 % margin). Recommendation: Lv = 2 everywhere; the 720p->2160p (3:1) leg alone uses Lv = 1.
  (This is a per-format transform depth fixed by the format pair, like slice height — not a profile.)
- DDR, same traffic model as OMC docs/DDR_WINDOW_CACHE.md (13-bit packed store, window cache, read
  amplification 1.00): today = 1 write + 1 read per sample = 26 bit/sample. CPP = 26 (reference) + 14
  (7-bit knot state per coefficient, 1 write + 1 read) + ~3 (encoder motion search on the previous TWO
  decoded frames at half resolution, luma) = ~43 bit/sample, 1.65x today. 4320p60 4:2:2: 171 Gbit/s vs
  today's 103; today's documented 8K solution (two x64 DDR4-3200, 410 Gbit/s peak) carries it at 42 %.
  2160p60: 43 Gbit/s on one x64 DDR4-2400 (154 Gbit/s peak), 28 %.

## R1 — rate control, exact CBR, as built and modelled (`notes/seq2.py`, Codec._encode)
- **Pipe**: prefix bound, OMC's model, no overdraft: bits(slices 0..n) <= (n+1) B for every n; unspent bits
  carry forward (credit), never borrowed. Per slice the allowance is (1 - rho) B - (vector bits share) - 49
  header/flush bits; rho = 1/16 is the refresh reservation (R2); unspent reservation beyond one frame's worth
  returns to the credit at the end of each frame.
- **Knots**: one knot per slice (1/8-octave units); the step of a coefficient row ramps linearly inside its
  slice from the previous slice's knot to this slice's knot (a continuous field, both ends derive it). Ahead
  data (coarse means of the next two blocks, carried in this slice's packet) use this slice's field
  ("band lag": LL/H/LH1 8 rows, HL1/HH1/LH0 4 rows, HL0/HH0 0), so a slice's reconstruction is final
  after its own packet and depends on no later knot.
- **Exact lanes, one pass**: for each candidate knot of the ladder (previous knot + {-64..+64}, 25 values)
  the exact code length of the slice (static tables, contexts including the row above) is computed from the
  open-loop symbols -- XS-style parallel budget evaluation, no trial coding. Choice: the finest candidate whose
  cost <= target (target = allowance + credit/16, a smoothing rule), else <= hard budget (all credit).
- **Still-region rule by construction**: step memory (change 2 above); kept coefficients cost the 0-symbol at
  any knot, so the coarsest ladder candidate (every non-kept index 0, every coefficient kept where the hint is
  closer) is also the cheapest; its exact cost is known before coding.
- **No guard exists.** Nothing ever codes part of a slice differently from the rest: every coefficient of a
  slice is coded at the slice's field with the same rule. What the coordinator's review called the guard
  (hint-kept remainder) is gone. When content needs more than the pipe, the knot rises (continuously ramped
  inside the slice); in the limit the slice is coded at the ladder's coarsest step, i.e. the whole slice
  keeps its motion-compensated lattice values or, for intra, becomes very soft. This is the codec at its rate
  limit, not a mode; its frequency is reported per cell ("overflow" = no candidate within the hard budget;
  "jump>+8" = knot rises by more than an octave between adjacent slices).
- **Intra slices (frame 0, cut, join)**: the same lanes; the ladder allows +8 octaves in one slice; the only
  intra-specific element is that no keep exists, so the floor cost is the LL DPCM of the slice at the coarsest
  step (exactly computable). Frames 0-1 are the permitted ramp.
- **Measured deviation** of actual coded bits from the lane estimate (clamp sites only): 0 to +-50 bits per
  slice on natural and graphics content; on rail plates up to ~2 slice budgets over a frame (cut24 @1.0: the
  prefix bound was exceeded by up to 2183 bits, one slice at 1.0 bpp 256 wide is 2048 bits) -- OPEN (R7-b).

## R8 — plan uniquely readable from the picture, by construction (proof)
Reading rule (every encoder, every slice, top-down): given the previous slice's knot k_{s-1} (already final),
the knot of slice s is the coarsest ladder candidate under which every coefficient of the slice is
reproducible (its legal interval computed from the picture's own pyramid; a value on its interval boundary is
reproducible by the reaching index; a kept value by its hint) and whose exact cost fits; if every candidate
reproduces, the knot is k_{s-1}.
Gen-1 rule: code slice s by rate (lanes), reconstruct it (it is final after its own packet, band lag), apply
the reading rule to that reconstruction with the same k_{s-1}, and emit the knot the reading returns (the
picture is unchanged: the reading only returns knots under which the reconstruction is exactly reproducible).
Lemma: the reading of slice s by any later encoder equals gen-1's emitted knot. Proof by induction over s:
the reading is a deterministic function of (slice s's reconstruction, the reconstruction above it, k_{s-1},
the step-memory state, the reference); the first two are identical by picture exactness, k_{s-1} by the
induction hypothesis, the state and reference by induction over frames; gen-1 emitted exactly the value of
that function. Hence the "previous slice ambiguity resolved by the next slice" cannot arise: no slice's
reading depends on anything below it, and each emitted knot is the reading. No backtracking, no search: one
reading per slice (a parallel lattice test over the ladder, 25 comparators per coefficient), at most one
re-description of an already-reconstructed slice. The one-slice backtrack of the previous build was removed
(`notes/seq2_backtrack_rejected.py`); its trigger was a model defect (the model's ahead data used the next
slice's field, so a slice's reconstruction depended on a later knot) plus a state-aliasing bug in the model's
snapshot, both fixed. Model note: the model codes whole frames, so it emulates the per-slice re-description
by running the later-encoder reading on its own frame; the count of re-descriptions it needed ("reading_fixes")
is reported per run and was 0 on every run so far.

## R11b — on-chip memory and DDR at every format, owner ruling "8K must fit" (ESTIMATED, same method as OMC
docs/DDR_WINDOW_CACHE.md section 7.3)
Structures: reference band ring (URAM) = slice S + 8 look-ahead + 8 analysis support of the MC picture
+ 2 x 16 vector range + 8 OBMC overlap = S + 56 rows at the store width (depth + 1, the narrowed store
today's 8K row uses); one coefficient buffer (URAM) = S + 8 rows x 16 bit, hints written first and residual
added in place (today's single-buffer schedule); capture/output line buffers (BRAM) = 2 S rows of pixels;
tANS tables (BRAM) = 60 x 1024 x 18 bit = 1.1 Mbit; +0.5 Mbit misc. Encoder adds the source look-ahead
(S + 12 rows of pixels) and computes the source coefficients twice from it (lanes pass and coding pass)
rather than holding a second coefficient buffer. S = 8 at 1080p/2160p, S = 4 at 4320p (latency 26.3 -> 22.1
lines, still < XS; 8K rows are cheap in time: 4320p60 line = 3.7 us).

| format | S | band | coef | decoder URAM / 27 Mbit | decoder BRAM / 11 Mbit | encoder URAM | encoder BRAM | today decoder URAM |
|---|---|---|---|---|---|---|---|---|
| 1080p60 4:4:4 12b | 8 | 4.79 | 1.47 | 6.27 (23 %) | 2.71 (25 %) | 7.76 (29 %) | 2.71 (25 %) | 8.73 |
| 2160p60 4:2:2 10b | 8 | 5.41 | 1.97 | 7.37 (27 %) | 2.83 (26 %) | 8.90 (33 %) | 2.83 (26 %) | 13.61 |
| 2160p60 4:4:4 12b | 8 | 9.58 | 2.95 | 12.53 (46 %) | 3.82 (35 %) | 15.30 (57 %) | 3.82 (35 %) | 20.43 |
| 4320p60 4:2:2 10b | 4 | 10.14 | 2.95 | 13.09 (48 %) | 2.83 (26 %) | 15.55 (58 %) | 2.83 (26 %) | 24.25 (narrowed store) |
| 4320p60 4:4:4 12b | 4 | 17.97 | 4.42 | 22.39 (83 %) | 3.82 (35 %) | 22.39 (83 %) | 8.24 (75 %) source rows in BRAM | 40.85 (does not fit) |

CPP fits the ZU7EV at every format, including 8K 4:4:4 12-bit which today's codec does not; the tightest is
8K 4:4:4 12-bit at 83 % URAM (17 % margin). The difference from today is the slice height (S = 4-8 rows
instead of 16-32: CPP's slices are rate units only, so they can be short without a seam cost).
DDR: reference store write 1x + reference read 1x through the same window cache (read amplification 1.00x,
the motion search reads the same resident band) = 26 bit/sample at a 13-bit store, identical to today's
traffic model; no state, no second frame. Same memory subsystem as today at every format, including the
single-channel 8K option (today's margin +38.7 us at 4320p60 with two DDR4-3200 channels or one channel with
no other master); the per-format timing table of that document applies unchanged because the per-row read
and write pattern is the same (a band of rows ahead of the slice, one row written per row produced). NOT
re-simulated with that document's adversarial-locality model (a model run, not arithmetic, is the owner's
method; listed as open).

## Results finished so far (all planes; later rows are filled as the final-code queue completes)
- **Gen-2 exactness, final design (no state, canonical vectors, per-slice reading)**: cf_gfx @0.5 12 frames:
  identical pictures and identical bits every frame, reading re-descriptions 0 (out/r2/log/gfx_0.5.txt);
  cut24 @1.0 12 frames identical, and on the final design the prefix bound held on this rail cell (minimum
  credit +2469 bits; the earlier build overshot by 3.4k) (out/r2/log/cut24_1.0.txt).
- **Rails, previous build (step memory, before canonical vectors)**, `out/r2/rails_summary.txt`: gen-2
  identical pictures on cut24 @0.5/@1.0 (12 frames), ext10 full range, ext10 limited range (64-940/64-960),
  ext8, ext12 4:2:2, ext12 4:4:4 (4 frames each); 0 out-of-range samples everywhere; prefix bound exceeded
  on rail plates by up to 1.6k-3.4k bits (cut24) and much more on the ext extremes (lanes ignore clamp
  relabels) -- OPEN.
- **A5 one-way, previous build**, floor720 (Lanczos 720p of floorballgameL), loss of slice 60 at frame 3,
  rho = 1/4: damage grew to rows 198-305 through motion, never above the refresh front once the front had
  passed a row, decoder == encoder bit-exact from frame 13 (front advanced 20-24 rows/frame), all planes
  (out/r2/old/loss_rho4.txt). Refresh cost at rho = 1/16 on floor720 @0.5: NEG 93.61 vs 93.88 without
  refresh, PSNR -0.25/-0.06/-0.05 dB (out/r2/old/floor720_ref*.txt).
- **Efficiency, previous build (step memory), dng720 @0.5, real code lengths, 12 frames, steady 2-11**:
  NEG 90.12 (worst 86.89) vs today 90.16 (87.22); PSNR mean 37.37/36.59/37.64 vs 35.22/36.10/37.14, worst
  36.16/36.20/37.24 vs 34.69/35.86/36.98; smudge groups 0/0/0 both; artifactmap regions CPP 0/0/0, today
  16/0/0; luma flat 38.0 % vs 41.9 %. Row-phase slice-edge excess (S = 4): within +-2 % every plane.
- **Final design, rails (all g2-identical, 0 out-of-range, prefix bound held: minimum credit +1.1k..+25k bits)**:
  cut24 @0.5/@1.0 (12 frames), ext10 full/limited, ext8, ext12 4:2:2, ext12 4:4:4 (4 frames each)
  (`out/r2/rails_final.txt`). The rate limit was reached (coarsest knot, "overflow") in 1-3 slices per run on
  these synthetic extremes.
- **Final design, dng720 @1.0 (tables B, 12 frames, steady 2-11)**: NEG 93.05 (worst 91.49) vs today 94.05
  (92.31): -1.00 / -0.82 -- WORSE; PSNR 39.10/37.73/38.56 vs 38.19/37.08/37.95 (worst 38.68/37.42/38.29 vs
  37.88/36.92/37.87): better on every plane; smudge 0/0/0 both; artifactmap 0/0/0 both; luma flat 33.8 % vs
  33.2 %. (`out/r2/eval_final.txt`)
- **Refresh cost (floor720 = Lanczos 720p floorballgameL, @0.5)**: rho = 1/16 vs no refresh: NEG 94.16 vs
  94.53 (-0.37), worst 89.81 vs 90.18; PSNR -0.22/-0.18/-0.15 dB.
- **ZH (no hysteresis around zero hints) = flatness hypothesis**: floor720 flat 26.9 % vs 33.3 % (texture kept)
  but NEG 93.39 vs 94.16 (-0.77) and PSNR -0.5 dB: REJECTED as the fix (it trades NEG for flatness).
- **Final design, dng720 @0.5 (tables B, 12 frames, g2 identical all 12 frames)**: NEG 90.34 (worst 86.25) vs
  today 90.16 (87.22): +0.18 mean, -0.97 worst; PSNR 37.35/36.59/37.61 vs 35.22/36.10/37.14 (worst
  35.97/36.09/37.13 vs 34.69/35.86/36.98); smudge 0/0/0 both; artifactmap CPP 0/0/0, today 16/0/0; luma flat
  37.5 % vs 41.9 %. ZH variant: NEG 88.25 (rejected). Row phases (S = 4, `out/r2/rows_dng720_0.5_final.txt`):
  mean|e| spread 2.1/0.6/0.8 % inter, 1.6/0.8/0.7 % intra; row step spread 2.9/2.2/1.4 % inter, 5.4/3.0/4.1 %
  intra; the slice-edge phase is inside that band on every plane.
- **Mid-stream join under exact CBR (floor720 @0.5, joiner starts at frame 6 on the upstream decodes, fresh
  state, same rate)**: slices whose pictures differ from upstream: 167, 156, 128, 105, 86 of 180 at frames
  6-10 (picture difference shrinking by ~20 slices per frame; frame 6 is the joiner's intra ramp frame at its
  own knots); byte-exact from a bounded frame NOT yet shown (upstream too short); a 24-frame run is queued
  (`out/r2/log/join24_floor720.txt`).
- **Knot-stability rule is not the NEG cause**: dng720 @1.0 without it NEG 92.87 (worst 91.23), PSNR
  39.07/37.70/38.52, vs 93.05 with it.

## R2 — one-way refresh: root cause of the stall and the bound (ARGUED; model runs used the earlier unit)
Root cause. Refresh is picture-neutral: a refreshed coefficient is sent as its full index q instead of q - h,
so a unit's refresh cost is the intra cost of that unit at the knots the rate control already chose. That cost
depends on content and rate, while the reservation (rho x frame budget) depends only on rate. With the unit
fixed at a full-width 4-row block, a detailed block at 1.0 bpp cost more than one frame's reservation and the
front stalled (dng720 @1.0: front stuck at row 124 from frame 2). The "save up to 8 frames" rule added at 13:30
only moves the stall into a content-dependent delay; it is withdrawn as a design element (it is in the model
code for the running queue only).
Redesign (unit sized by construction). Cap the hint-free code: every hint-free symbol costs at most L_max bits
(static tables, escape code of fixed length for |q| beyond the table: L_max = 16 at 10-bit, 18 at 12-bit).
The refresh unit is a run of u consecutive coefficient columns of one 4-row block row, u chosen so that its
worst-case extra cost fits one frame's reservation R = rho x bpp x W x H:
    u = floor(R / L_max)  coefficients  (all planes of the block row, in the stream's coding order).
Each frame the sweep refreshes whole units, as many as the reservation pays at their actual cost (bit-metered,
the common case covers many units), but always at least one unit, which the reservation covers in the worst
case by construction. No saving, no content-dependent stall.
Recovery bound (content independent, worst case): with N_c coefficients per picture (c = 2 for 4:2:2, 1.5 for
4:2:0, 3 for 4:4:4, N_c = c W H), one sweep cycle takes at most N_c / u = c L_max / (rho bpp) frames, and a
loss is repaired within two cycles plus one frame:
    T_recover <= 2 c L_max / (rho bpp) + 1 frames.
Worked values (4:2:2, L_max 16): rho = 1/16: 1025 frames at 1.0 bpp, 2049 at 0.5 bpp; rho = 1/4: 257 / 513.
Typical (measured, earlier build, floor720 @0.5, rho = 1/4): the front advanced 20-24 rows per frame (cycle ~33
frames at 720p) and a loss at frame 3 was repaired bit-exactly by frame 13. The worst-case bound is long
because a worst-case picture costs L_max bits per coefficient to re-send; this is the price of picture-neutral
refresh with no back channel. OPEN, to be decided by the coordinator/owner: accept this bound, raise rho (NEG
cost measured at rho = 1/16: -0.37), or allow a refresh unit to be re-described at a coarser knot when the
reservation cannot pay (bounded cycle H/S frames, but a picture change in that unit).
- **A5 on the final code (before the R2 unit redesign), floor720 @0.5, rho = 1/4, loss of slice 60 at
  frame 3** (`out/r2/log/loss_rho4.txt`): the sweep covered rows 0-544 in frame 1, then stalled at row 544 for
  the rest of the run (a 4-row block's hint-free extra exceeded one frame's reservation of 115 kbit); the
  damage (rows 116-389 by frame 22) was never repaired. This is the measured instance of the root cause in R2;
  the unit redesign of R2 is to be modelled after the running queue finishes (coordinator: no restart).

### R5 — efficiency, final design, tables B, real code lengths (steady frames 2-7 for 1080p (8 frames), 2-11 for 720p)
| cell @rate | NEG CPP mean / worst | NEG today mean / worst | PSNR CPP mean (Y/Cb/Cr) | PSNR today mean | PSNR CPP worst | PSNR today worst | luma flat % CPP / today |
|---|---|---|---|---|---|---|---|
| dng720 @0.5 | 90.34 / 86.25 | 90.16 / 87.22 | 37.35/36.59/37.61 | 35.22/36.10/37.14 | 35.97/36.09/37.13 | 34.69/35.86/36.98 | 37.5 / 41.9 |
| dng720 @1.0 | 93.05 / 91.49 | 94.05 / 92.31 | 39.10/37.73/38.56 | 38.19/37.08/37.95 | 38.68/37.42/38.29 | 37.88/36.92/37.87 | 33.8 / 33.2 |
| dng1080 @1.0 | 92.29 / 90.78 | 93.31 / 91.77 | 37.44/36.38/37.16 | 36.90/36.02/36.72 | 37.35/36.24/37.05 | 36.85/35.82/36.59 | 42.0 / 27.5 |
| spotrobotL @0.5 | 93.99 / 90.30 | 93.25 / 87.10 | 41.60/42.88/45.94 | 39.35/42.76/46.24 | 40.73/42.19/45.34 | 36.51/42.10/45.65 | 44.3 / 52.7 |
| volleyballgameL @0.5 | 92.48 / 90.14 | 92.29 / 90.83 | 43.04/44.31/46.53 | 41.30/43.32/45.82 | 41.63/43.41/45.60 | 40.54/43.08/45.48 | 33.0 / 37.0 |
| highwaydriveL @0.5 | 92.56 / 89.76 | 93.58 / 90.58 | 41.85/47.47/44.37 | 40.94/47.26/43.78 | 41.69/47.34/44.22 | 40.74/47.21/43.63 | 29.1 / 42.5 |
| floorballgameL @0.5 (g2 identical) | 95.53 / 92.00 | 95.55 / 92.41 | 41.61/45.14/44.82 | 40.71/44.74/44.32 | 41.39/44.98/44.67 | 40.62/44.70/44.27 | 42.2 / 55.5 |
| floorballgameL @1.0 | 97.35 / 93.99 | 98.19 / 94.94 | 43.12/46.37/45.95 | 42.60/46.02/45.50 | 43.03/46.33/45.92 | 42.56/45.96/45.42 | 13.8 / 31.7 |
| dng1080 @0.5 | 89.57 / 87.36 | 90.70 / 87.51 | 36.27/35.20/36.20 | 35.30/34.65/35.74 | 35.96/34.99/36.03 | 35.05/34.52/35.70 | 50.9 / 53.5 |
| spotrobotL @1.0 | 97.21 / 93.94 | 97.36 / 95.03 | 44.47/45.09/47.98 | 43.28/44.76/48.14 | 43.83/44.41/47.41 | 40.70/44.08/47.54 | 32.2 / 40.8 |
| highwaydriveL @1.0 | 95.58 / 92.60 | 97.08 / 94.13 | 44.26/48.78/45.73 | 43.79/48.96/45.23 | 44.01/48.59/45.53 | 43.61/48.83/45.11 | 7.6 / 30.5 |
| volleyballgameL @1.0 | 95.09 / 93.83 | 95.59 / 94.70 | 46.18/46.78/48.77 | 45.23/45.62/48.08 | 45.50/46.20/48.25 | 45.13/45.56/47.98 | 26.9 / 33.1 |
smudgegroups 0/0/0 and artifactmap 0/0/0 regions in Y/Cb/Cr for CPP on every cell (today: 16 luma regions on
dng720 @0.5, 1 on spot @0.5). Reading (12 points; the two rows above added later: hwy @1.0 -1.50, volley @1.0 -0.50): NEG mean >= today on 3 (dng720 @0.5 +0.18, spot @0.5 +0.74, volley @0.5 +0.19), tie on
floorball @0.5 (-0.02), lower on 6 (spot @1.0 -0.15, floorball @1.0 -0.84, dng720 @1.0 -1.00, dng1080 @0.5
-1.13, dng1080 @1.0 -1.02, highwaydrive @0.5 -1.02); worst-frame NEG lower on 8 of 10; PSNR higher on 28 of 30
plane-points (spot Cr -0.30 @0.5, -0.16 @1.0); luma flatness lower than today on 8 of 10. The efficiency bar "no noticeable increase vs today" is NOT met on NEG.
(`out/r2/eval_final.txt`)
- **Mid-stream join, 24-frame upstream** (`out/r2/log/join24_floor720.txt`): differing slices 167 (f6), 156, 128,
  105, 86, 43, 26 (f12), then a plateau of 43-55 of 180 slices to frame 18: the joiner does NOT converge to
  byte-exact. Root: a joiner slice whose reference differs from upstream's has costlier hints, so the reading's
  "fits" test rejects upstream's knot and the slice is re-coded at another knot, which keeps its reference
  different. Needed (not modelled): the sweep must re-describe refreshed units hint-free AT the read knot
  (exact values, reference-independent, paid by the reservation), which syncs one unit per frame at least and
  makes the join bound equal the R2 refresh bound.
- **Tables A (training set includes floorballtrainL / highwayviewL) vs B (excludes them)**: floorballgameL @0.5
  NEG 95.39 (A) vs 95.53 (B), PSNR 41.60/45.12/44.81 vs 41.61/45.14/44.82; highwaydriveL @0.5 NEG 92.52 vs
  92.56 at equal rate (0.505-0.510 bpp): the related training clips do not flatter the result.
- **Cut sequence (floorballgameL f0-5 then volleyballgameL f6-7, 1080p @0.5)**: gen-2 identical; NEG 91.13
  (worst 83.09 = the frame after the cut); artifactmap flags 42/44 luma regions (the cut frame; not yet
  inspected by eye).
- **Mixed still/moving (dng1080 frame 0 repeated, floorball inset rows 272-808 x cols 480-1440, @0.5)**: gen-2
  identical; NEG 92.31 (worst 90.05); PSNR 39.30/38.95/39.55. STILL-AREA FAILURE: 40-60 % of the still
  background samples change every frame (frames 1-7); mean |error| of the background falls every frame
  (12.75 -> 8.32 Y), i.e. a refinement ramp, but per sample the changes split ~52/48 toward/away from the
  source -> a visible shimmer. Root: the controller refines a slice's knot by 1/8-octave steps as the still
  content becomes cheap; a non-nested step change requantises every coefficient on a new lattice. Fix
  (designed, not modelled): a knot may decrease only by exactly one octave (D(k-8) = D(k)/2, nested: every
  old value lies on the new lattice, so the keep/nearest rule changes a sample only toward the source), and
  the in-slice ramp must move by the same octave at both ends (otherwise the ramp rows re-round); coarsening
  stays free (pipe-forced).

## R3 — mid-stream join under exact CBR (MEASURED, NOT MET)
See the results list above: a fresh encoder joining at frame 6 converges from 167 to 26 differing slices of 180
in 6 frames, then plateaus at 43-55 (floor720 @0.5, 24-frame upstream). Root and fix: section "Mid-stream join,
24-frame upstream" above -- the join must ride on the R2 refresh (units re-described hint-free at the read knot),
giving join bound = refresh bound. Not modelled.

## R6 — flatness (MEASURED; root cause partly found, not fixed)
Luma flat-block fraction, final design vs today: lower on 10 of 12 points (e.g. highwaydriveL @1.0 7.6 % vs
30.5 %, floorball @1.0 13.8 % vs 31.7 %); HIGHER on dng1080 @1.0 (42.0 % vs 27.5 %) and dng720 @1.0 (33.8 vs
33.2). Per-band texture energy retention (dng720 @0.5, `out/r2/flatroot_dng720.txt`): the loss is in the
inter frames (intra retains more fine luma energy than today: HH0 0.64 vs 0.40), level-0 luma bands 0.88-0.89
vs today 0.96-0.99. Tested hypothesis: the keep hysteresis around zero hints widens the dead zone for grain
(ZH variant): flatness improved (floor720 26.9 % vs 33.3 %) but NEG fell 0.8-2.1 -> rejected. Grain (film
noise, dng) is temporally uncorrelated, so inter prediction cannot carry it and the rate spent re-sending it
competes with everything else; today spends more luma bits on it (lower PSNR, higher NEG). OPEN; candidate
root: band-step weights are MSE-derived (fixed table), not texture-aware.

## R8 — formats (MEASURED, final design, dng source, 6 frames @0.5 unless noted)
| format | gen-2 | out of range | PSNR Y/Cb/Cr last frame | row phases (S = 8): mean|e| spread Y/Cb/Cr inter; slice-edge phase |
|---|---|---|---|---|
| 4:2:0 10-bit (chroma Lv = 1) | identical | 0 | 37.08/36.48/37.49 | 1.5/0.6/0.4 %; edge +0.7/-0.1/+0.2 % |
| 4:4:4 12-bit | identical | 0 | 34.97/33.58/34.70 | 2.3/1.5/1.3 %; edge +1.2/+0.7/+0.6 % |
| 4:2:2 8-bit | identical | 0 | 35.91/34.92/35.89 | 1.0/0.8/0.9 %; edge +0.4/+0.4/+0.3 % |
| 4:2:2 12-bit | identical | 0 | 36.46/35.31/36.31 | 1.6/1.2/1.5 %; edge +0.8/+0.5/+0.9 % |
| limited range 64-940/64-960 (dngL, 4 frames) | identical | 0 (in the limited range) | 37.31/36.24/37.25 | - |
| rail extremes cut24 (0.5/1.0), ext10 full/limited, ext8, ext12 4:2:2/4:4:4 | identical (all 7) | 0 | - | - |
Files: `out/r2/log/f*.txt`, `out/r2/rows_f420.txt`, `rows_f444_12.txt`, `rows_f422_8.txt`, `out/r2/rails_final.txt`.
The 4:2:0 chroma (Lv = 1, 2-chroma-row blocks = 4 luma rows) shows no special row phase.

## R9 — half-pel (MEASURED on 3 motion cells; highwaydriveL still running)
Bilinear half-pel vectors (search refined to +-1/2 pel, OBMC gathers the average of the neighbouring integer
samples), vectors from decoded history, @0.5 1080p, 8 frames, vs integer-pel (R5):
| cell | NEG int / hp | PSNR int / hp (Y/Cb/Cr) | bpp int / hp |
|---|---|---|---|
| floorballgameL | 95.53 / 95.40 | 41.61/45.14/44.82 / 41.64/45.15/44.83 | 0.510 / 0.517 |
| volleyballgameL | 92.48 / 92.39 | 43.04/44.31/46.53 / 42.98/44.28/46.49 | 0.504 / 0.513 |
| spotrobotL | 93.99 / 94.19 | 41.60/42.88/45.94 / 41.75/42.98/46.03 | 0.508 / 0.518 |
Half-pel buys nothing measurable here (+-0.2 NEG at +1.4-1.9 % bits). Reason: the prediction's precision enters
only through the hint indices (lattice lock), and vectors extrapolated from the previous frame pair are already
the dominant error, not their precision. Integer vectors are kept.

## R10 — renders (DONE for dng720 @0.5 f8 and floorballgameL @0.5 f6)
`out/r2/renders/`: per plane Y/Cb/Cr: signed error at +-16 and +-2 codes with colour legend, unmarked and with
slice grid; level map (8x8 mean error, +-2 codes, legend, grid); slice-edge strips (16 rows around 4 slice
boundaries, full width, x4 vertical; error at +-2 and decode side by side); colour decodes (shared render.py).
My look at the Cr strips (dng720): noise-like error with no row feature at the boundaries.
