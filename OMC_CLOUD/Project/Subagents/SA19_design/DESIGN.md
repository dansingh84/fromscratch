# SA19 DESIGN — written incrementally (status tags: MEASURED / PROXY / PAPER)

## §A. Own architecture options (written before any design-specific measurement; owner rule S5.384 + coordinator 2026-09-29)

My root chains (own, from PROJECT_CONSTRAINTS + pack evidence):
- Seam/smudge <- some row has one-sided transform support <- slices are transform units. Root fix: the transform
  must be continuous across slices; slices are only rate/packet units.
- Illegal pictures / lost exactness <- a clip destroys what the next encoder must read <- legality applied after
  a lossy synthesis. Root fix: legality inside synthesis, on values read by nothing else.
- Still-area flicker <- exact CBR spends every bit, so still content is re-coded every frame. Root fix: coding is
  change-driven (an encoder rule); unspent bits are padding.
- Static-camera efficiency gap <- a still region may change only once <- quality of that one change is capped by
  one frame's free budget. Root lever: make the ONE change as good as possible (whole still set, once, at the finest
  step the free budget funds) and waste nothing else.
- Motion efficiency gap <- inter residual carries reference quantisation noise (S5.144/S5.152: 8-20 % of residual
  bits, 60-72 % in LH1+HL1) and stale vectors (SA18 D8). Root lever: the C2 ruling (S5.393) now allows more than one
  exact past picture; two independent past decodes averaged along motion cancel part of that noise.

Option 1 — TPP "two-past pyramid" (value-domain coefficient prediction, band-split references)
- Continuous averaging pair pyramid over the whole picture, leaf-interval legality; slices = rate units.
- Each band's prediction = analysis of a motion-compensated picture; COARSE bands from D(t-1); FINE bands (levels
  1-2) from a fused picture w*MC(D(t-1)) + (1-w)*MC(D(t-2)), w a continuous field derived from decoded data only.
- Stills: change-driven; one whole-still-set catch-up to a canonical final step, error-triggered, once.
- Rate: per-slice budget shares from the previous frame's EMITTED per-slice costs (exact at every generation).
- Memory: D(t-1) full + D(t-2) luma, raw (lossless, exact); DDR ~25 bit/sample vs today 26.

Option 2 — PRX "pixel-residual pyramid" (prediction in the pixel domain)
- Same continuous pyramid, but it codes R = x - P with per-pixel legal boxes [lo-P, hi-P]; P = per-pixel fusion of
  MC(D(t-1)), MC(D(t-2)) (sub-pel from the two references instead of interpolation filters).
- Difference from 1: one prediction for all bands (cannot give coarse and fine bands different references at no
  cost); per-pixel boxes make legality depend on P at every sample.

Option 3 — VCR "vertical-causal rows" (no vertical transform at all)
- Each row final before the next; rows predicted temporally (two-reference fusion) or from the row above (intra);
  horizontal pyramid per row. Seams impossible by construction and vertical latency minimal.
- Known cost on record: intra -0.4...-1.2 dB, inter -0.5...-3.5 dB (SA11 S5a/V5), cast from half-up rounding.

Choice: Option 1 (TPP). Reasons: (a) it is the only option whose seam-freedom, legality and exactness are backed by
measurement in the pack at zero bit cost; (b) band-split prediction lets the fine bands (where the reference noise
is) use the fused reference while the coarse bands keep the sharper single past, which Option 2 cannot do; (c)
Option 3 carries measured dB losses larger than the whole goal-4 gap. Option 2's per-pixel fusion is kept as the
FORM of the fused picture inside Option 1 (the fused picture is formed per pixel, then analysed).

Elements adopted from earlier designers (one line each: where from, why it fits):
- Continuous pair pyramid, slices as rate units (SA15/SA17): the only measured seam-free structure with 0 bit cost.
- Leaf-interval clamp legality + smallest-reproducing canonical index (SA15/SA17): legal for any stream, exact g2/g3.
- Canonical emission (gen 1 emits the reading of its own picture) (SA15 R8): exactness through hops.
- Value-domain coefficient prediction (SA12/SA16/SA17): keeps texture (lattice lock lost it, SA15).
- Transmitted vectors derived from decoded data + coarse-first refinement on decoded LL2 (SA17/SA18 D13-D14):
  exact by construction, and TPP needs vectors for BOTH references anyway.
- Static tANS tables keyed by step bucket (SA17): measured +48 % loss without it.
- On-demand heal via return path, one-way cycle-2 wave (owner rulings, SA17 mechanism): < 4 frames measured.
Status of the chosen option's weak points (to be measured, not assumed): never-away per sample (the averaging
pyramid's partner move, pack §14.2) is OPEN in this option as in every averaging design; attack plan in §C.

## §B. Measurements (see RESUME.md item table; every figure NEG mean (worst), then PSNR Y/Cb/Cr)
All REAL: real code lengths from static tANS tables trained on 5 (or 3) disjoint clips UNDER THE EXACT configuration
measured, exact CBR per slice, frames 2-11 vs today's real decodes (v537).
- Bench reproduction: SA17 dng720 @0.5 88.97 (88.09) 34.43/36.12/37.22 (= SA17).
- B1 two-past fusion, fixed w=8 (A1) vs single past (A0), @0.5: spot 94.54 (90.86) 40.00/42.58/46.44 -> 94.75 (90.86)
  40.50/42.89/46.74; floor 95.40 (91.55) 40.42/45.04/44.60 -> 95.48 (91.52) 40.67/45.21/44.76; dng720 89.00 (88.09)
  34.46/36.13/37.22 -> 88.96 (88.02) 34.45/36.13/37.22; dng1080 90.35 (88.68) 35.09/34.73/35.98 -> 90.34 (88.61)
  35.10/34.75/35.99. Today: spot 93.76 (87.10), floor 95.98 (92.41), dng720 90.16 (87.22), dng1080 91.08 (87.51).
  Proxy S1b explains the small gain: with the real field V2=2V1 the fused fine-band residual is WORSE on hwy/dng/volley.
- B2 never-away (TPP, legal vs pre-legal synthesis): natural dng720 @0.5 luma 989 samples away (0.027 %), max 82 codes,
  0.27 % of plane SE; @1.0 51 (max 38); gfx @0.5 292 (max 120); chroma 0 on natural content; rails cut24 7.8-15.4 % of
  samples (max 409 codes), ext10 5.9-11.3 % (max 703). NOT MET. Proof (group): an exact legaliser must keep every value the
  next encoder re-reads; with an averaging pair the pair sum is re-read, so the partner lands at 2m - rail; it stays on its
  source's side iff the ancestor mean error e_m <= 0, which the decoder cannot sign. Routes tested on record fail (pack
  §12.3); rail-at-infinity dropped (many-to-one g^-1). Open at the representation level.
- B3 D3 decomposition (dng720 @0.5, ours A0 vs today, error energy per band): luma LL 0.11x, H5 0.15, H4 0.34, H3 0.61,
  HL2 1.19, LH2 1.19, HH2 1.12, HL1 1.29, LH1 1.19, HH1 1.34; chroma coarse 0.12-0.69x, fine 1.00-1.16x -> we over-invest
  the coarse bands and lose fine luma texture: the dng720 gap (-1.16 NEG) is an allocation/texture gap, not a hold gap.
- B4 slice allocation: per-slice bits equal by construction, plan index spread ~1.3 octaves down the frame (spot 175..215,
  floor 176..208; middle slices coarser); padding ~0 on every motion/dng cell.

## §C. TPP path (as built in bench/tpp.py; PAPER parts marked)
1. Transform/legality (elements, §A): 2 quad levels + 3 horizontal pair levels over the whole picture; every leaf clamped into
   the set keeping its pair's outputs legal, from final values only; any stream decodes legal; canonical index = smallest
   reproducing |q|; gen 1 emits the reading of its own picture.
2. Prediction state (identical at encoder, re-encoder, decoder):
   - V1 = history field D(t-1) vs D(t-2) (64x8 blocks, +-16 x +-4, row-regularised, zero preferred), transmitted.
   - V2 = 2*V1 (constant velocity; no bits). [SA19P variant V2 = V1 + V_{t-1}(landing block): queued]
   - P1 = OBMC(D(t-1), V1) for every plane; P2 = OBMC(D(t-2) luma, V2) (LUMA ONLY -> t-2 is stored for luma only).
   - Fused luma F = (w*P1 + (16-w)*P2 + 8) >> 4; w (8..16) per pixel: 16 wherever every contributing OBMC block is still
     (exact hold keeps working); elsewhere Wiener form w2 = s2/(s2 + K*M2): M2 = 8x8 box mean of (P1-P2)^2, s2 = (D1^2 + D2^2)/12
     from the EMITTED level-1 steps of t-1 and t-2 (in both streams), bilinear between box centres (continuous, no step).
   - Coarse bands (LL, H5..H3) predicted from T(P1); fine bands (levels 1-2) from T(F) (luma) / T(P1) (chroma).
3. Still rule (encoder-only): once-then-hold (a still coefficient refined once is held until the source moves > 3/4 of its
   step) + ONE catch-up: in a frame following a frame that left >= 25 % of the pipe as padding, every still coefficient that
   was refined once and never caught up may be re-coded, only where the slice's step is >= 1 octave finer than the step it
   was refined at; then it is marked caught. No schedule, no age: triggered by free budget + remaining error (dead zone).
4. Loss (PAPER): on-demand heal of rows [kS - m, (k+1)S + m] intra at t+RT+1; in frame t+RT+2 every pixel whose P2 reads
   t-2 rows inside the heal footprint (+ 2x vector reach) uses w = 16 (single reference) -> no damage survives in t-2; m
   must cover the 2*V1 reach (m = 16 + 8(RT+1) + 8). Join: a joining decoder needs two clean frames (+1 frame).
5. Memory (PAPER): DDR = today's pair-pyramid 20 bit/sample (SA17 accounting: reference write + read at depth bits) + luma
   t-2 window read (10 bit per luma sample = 5 bit/sample at 4:2:2) = 25 bit/sample vs today's 26. On-chip: + a luma t-2
   window ring (~44 rows x 7680 x 10 bit = 3.4 Mbit at 8K) -> to be checked against today's 29.23 Mbit (narrowed store).

## Answer to owner: t-2 concerns (two-past fusion; per-block t-1/t-2 choice)
Worst case, 8K60 4:2:2 10-bit (3.98 Gsample/s), ZU7EV-class at 400 MHz; figures per 4:2:2 sample, both ends.
- No search, no choice: V2 is READ from the history field (V2 = V1 + u(landing block), one table lookup per 64x8 block); the
  per-pixel weight is a continuous function of decoded data (|P1-P2| box mean + emitted step -> 4-bit LUT). There is no
  per-block t-1/t-2 search or selection, so the "extra reference search" of the per-block choice never exists here; the
  hard per-block choice is DROPPED (the continuous weight already goes single-reference where the frames disagree).
- Compute: second OBMC fetch, luma only ~16 add/luma sample; |P1-P2| box sum + LUT ~4; 4-bit weighted blend (<= 4 shift-adds) ~6;
  fine-band analysis of the fused picture instead of P1 (levels 1-2 only) ~10 -> ~36 per luma sample = ~18 per 4:2:2
  sample; no per-pixel multiplier (squares replaced by |.|). 3.98 G x 18 = 72 Gop/s = ~180 pipelined adders = ~4-8 k LUT
  (2-3 % of 230 k) per end; decoder total ~57 -> ~75 ops/sample (SA17 accounting).
- DDR: + one luma window read of t-2 per frame = 10 bit per luma sample = +5 bit/sample -> 20 + 5 = 25 bit/sample vs
  today's 26. Jitter: t-2 is fetched through its own window ring exactly like t-1 (vector-bounded rows, fixed volume per
  slice, read amplification 1.0), so the per-slice DDR demand is constant; no new burst class. Capacity: 2 luma frames +
  1 chroma frame in DDR (t-2 chroma is never stored).
- On-chip: t-2 luma ring (S + 2x4x2 vertical reach + 8 OBMC + 8 look-ahead ~ 40 rows) x 7680 x 10 bit = ~3.1 Mbit ->
  decoder ~22.7 + 3.1 = ~25.8 Mbit at 8K 4:2:2 10-bit vs today's 29.23 (narrowed store).
- Latency: 0 added lines. P1, P2 and the weight depend only on t-1, t-2 and the transmitted history field, all known before
  frame t starts; the fused prediction of slice k is computed during slice k-1's period (the same prefetch as P1). The
  720p50 + 3:1 budget (0.991 ms, 9 us margin) is unchanged.
- Not a library: t-2 is always the frame immediately before t-1, overwritten every frame, never recalled by index, never
  used for anything but a prediction blend; after a heal the pixels whose t-2 source lies in the heal footprint use t-1
  only (known to both ends from the stream), so no damage survives in t-2.

## §L Legality comparison (owner directive 2026-09-29 ~21:45; evidence = pack sections cited + my AW run)
Columns: tested properly? (rails+natural+graphics, per plane, g2/g3) | 0 oob | exact | never-away | bit cost | seams/smudges.
1. Today: output clip + generation lock + in-gamut repair (§3, §3.8) — thoroughly tested | yes (clip) | NO (clip destroys
   information; lock 50 passes, misses on graphics/rails) | clip itself toward, repair moves away | 0 | blend = smudge.
2. Today + in-cell legaliser W/W'/X/Y/Z (§3.8) — natural+rails, g2 via lock | outer clip still fires (seam blend) | real
   cells 94-100 %, rails 0 % | quality = clip | 0 | inherits blend. Not by construction; K rounds = iteration.
3. Legality in synthesis with update reading clamped values (§4.3) — cyclic; acyclic forms = predict-only: -2.4..-4.8 dB. Dead.
4. Predict-only / per-sample leaves + plain clip (DESIGN3, SA11, SA13 T1, SA15 T1, SA17 E1d, SA18 IPL) — legal, exact, never-away
   trivially | cost -1.4..-5 dB, IPL -15 NEG intra real. Dead on efficiency.
5. SA11 vertical-causal + clamp + own-decode requant (§5.3) — exact natural except 1 index, rails settle at g3 | 3-19x work,
   -0.4..-3.9 dB chroma, +1-code cast. Dead.
6. SA12 per-pair interval clamp, exact-sum pairs (§6.1) — 216/216 rail cases g2 exact, 0 oob | never-away not measured |
   slice-closed pyramid -> intra seam step. Legal core = same family as 9.
7. SA13 REXT + <=1 projection round + lossless fallback (§7) — natural exact; cut24 not exact in fixed work; fallback +1.5 bpp. Dead.
8. SA14 leaf-reading lifting + closure (§8.1) / IDQ (§8.2) / RAIL± (§8.1-8.3) — acyclic with full 5/3 update, exact | IDQ
   moves samples AWAY (107k away vs 300k toward; v4 171-217k away) and -0.6 dB on graded rails; RAIL± +10.9..+31 % bits on
   graded natural. Not never-away, not free.
9. Leaf-interval clamp from final values, pair written last (SA15/16/17/18/SA19) — properly tested: 0 oob every run incl.
   cut24/ext10/ext12/limited/4:2:0/4:4:4 12-bit (SA15 R8), g2 AND g3 pictures+bits identical (SA17 CH, SA19 T0/T1), 0 bits
   on natural+graphics (SA15 R7 ratio 1.0000), rail plates +2..+16 % bits (SA15; SA17 "legality spends no symbols"), no seam
   (continuous pyramid, row phase within 0.4-2.3 %), smudgegroups 0 | NEVER-AWAY FAILS: SA19 AW dng720 @0.5 0.027 % of luma
   samples (max 82 codes), rails 6-15 % (max 703), SA17 ~54 %/75 % of changed samples.
10. SA15 boundary-snap of coarse means (§9.2) — removes rail bit cost, MSE x7.7. Dead.
11. SA17 plain clip + nearest-lattice reading with 5/3 (E2) — 18-282 index misses on rails. Dead.
12. SA18 families (§12.3): DOL 5-40 % g2 mismatch; RC / F2 switches = fixed points; ancestor inward rounding / offsets =
    sibling conflict + darkening (paper); D2 single ±1 coarse re-choice fixes 0.1 % (cut24) .. 56 % (gfx); censored reading
    = no one-pass reading; PREVENT not by construction. None built to the pass bar.
13. SA19Q rail-at-infinity (companding) — g^-1 many-to-one / saturating. Dead on paper.
CHOICE: #9 is the best-tested mechanism (only one that is legal for ANY stream, exact g2/g3 incl. rails, zero bits on natural
content and graphics, seam-free) and is kept as the DECODER rule. Its single failure, never-away, is attacked at the root in
§L2 on the ENCODER side (the decoder is unchanged, so every property of #9 is kept).

## §L2 Closing never-away (encoder-side, decoder unchanged) — design under test
Root: a clamp can only fire where the encoder's own leaf lands outside its feasible set; the partner then moves because the
pair mean is re-read. If the encoder never emits a leaf whose value leaves its feasible set, the decoder's clamp is a no-op on
every stream the encoder produces: nothing is moved by legality, so nothing is moved away. The decoder rule (#9) still
guarantees legality for ANY stream (corrupted, foreign).
Encoder rule (one pass, coarse to fine in synthesis order, inside the encoder's reconstruction it already runs): for each leaf,
if the quantised value lies outside the feasible set S (computed from final values), replace the index by the lattice index
INSIDE S nearest to the source leaf; if S contains no lattice point, the clamp fires (counted as "unfixable"; next step
decides what the design does there). Exactness: the emitted indices are read back canonically (they are plain lattice
points, no clamp involved). Measured next: count of clamp events, fixable share, bits, NEG/PSNR vs legality off.

## §L2 results so far (legal19.py / away19.py / clipread19.py; see RESUME items AW, L1)
- Metric (group agreement, owner's intent "never move a sample away from the SOURCE"): per sample, away iff
  |out - src| > |clip(legality-off decode of the same unconstrained indices) - src|. Measuring against the pre-legal value
  instead would pass the encoder-side idea by definition (relabeling), so it is not used for the verdict.
- Decoder clamp #9 alone: dng720 @0.5 luma 799 samples away (0.029 %), chroma 0; gfx 212 (@0.5) / 24 (@1.0); cut24 10.5-19.5 %
  per plane; ext10 up to 32.9 % (Cr @1.0). PSNR equals the clip arm within 0.04 dB (legality costs no quality on average).
- R-FIX (encoder picks the lattice index inside the feasible set nearest the source leaf; decoder unchanged): in-range index
  exists for 22-89 % of clamp leaves, but away GROWS on every cell (dng720 1057, gfx 294, cut24 19-38 %, ext10 28-76 %), PSNR
  falls (cut24 @1.0 Y 12.95 vs 19.88 clip) and CBR prefix overs appear -> DEAD. Reason: with the pair mean fixed, any legal
  finest choice puts the partner at 2m - a >= 2m - hi (SA18 L4); the constraint also perturbs finer levels.
- Proof of the limit inside any exact averaging design (group): per-sample never-away vs clip requires the ancestor mean error
  e_m <= 0 at every top-rail overshoot (>= 0 at bottom); only the ancestors' index choices set e_m; moving an ancestor moves its
  whole support and its neighbours' predictors (sibling conflict); D2 (SA18) oracle single re-choice fixes 0.1-56 %.
- R-CLIP (decoder = pure clip, never-away by construction; exactness only if gen 2 recovers every leaf by nearest-lattice
  reading of the clipped picture): measurement running (clipread19.py).
- R-CLIP MEASURED (clipread19.py, tab_f0, 3 frames; sufficient-condition proxy: a coefficient is recoverable iff
  |analysis(clip(yu)) - V0| < step/2, LL must be exact): misses on EVERY cell at <= 0.5 bpp, natural included — dng720
  @0.25/0.5/1.0: 754/132/4 misses (LL, H5, H4 first); gfx @0.25/0.5/1.0/2.0: 89/33/0/1; spot @0.25: 587; cut24 297-1127 per
  rate; ext10 1316-3003. Root: the coarse steps are the SMALLEST in the ladder (LL ~1/11 of level 1), and a coarse mean absorbs
  the summed overshoot of its support, so the clip's perturbation exceeds half a coarse step. -> R-CLIP not exact: DEAD as a
  mechanism (pure clip + reading).

## §L3 VERDICT on never-away (group claim, ledger S5.404; written for review). Bar not relaxed.
Metric: per sample, away iff |out - src| > |clip(yu) - src|, yu = synthesis of the SAME transmitted indices with legality off.
Premises of the proof (P1-P3) and what they cover:
- P1 exactness: the next encoder re-derives every value the synthesis reads (here: every pair mean m, read by the coarser level
  and by neighbours' 2/6 slope predictors) from the decoded picture alone (C7: only the image crosses a hop).
- P2 averaging: some output sample is an input to a re-read average (the pair pyramid's m = (a+b+pi)>>1; also 5/3, S-transform,
  any lapped/averaging lowpass). NOT covered: predict-only / per-sample-leaf structures (no output sample feeds a re-read average).
- P3 fixed-point reading: gen 2 recovers the transmitted lattice indices (nearest/canonical reading), not a search.
Step-by-step (finest pair, top rail; bottom rail symmetric): (1) by P1+P2 the re-read mean m is fixed, so a + b = 2m (up to
parity). (2) a legal output with a overshooting needs a <= hi, hence b = 2m - a >= 2m - hi. (3) clip(yu) leaves b at b0 = 2m - a0
with a0 > hi, so b - b0 >= a0 - hi = ov > 0: the partner moves UP by at least the overshoot under ANY legal choice (decoder clamp,
encoder in-range index, residual-domain clamp, "toward P" rules). (4) b stays no farther than b0 from its source s_b iff
b - s_b <= s_b - b0, i.e. 2m - hi <= 2 s_b - b0; with m = s_m + e_m this holds for all sources only if e_m <= 0: the SIGN of the
ancestor mean error decides, which the decoder cannot know and which only the ancestors' index choices set. (5) changing an
ancestor index moves its whole support by the same amount (and its neighbours' predictors): samples of the support whose error
already has the inward sign move farther (support-wide away) — sibling conflict.
Closed routes (evidence):
- Decoder leaf clamp #9 (base): legal, exact, 0 bits; away = dng720 @0.5 Y 799 (0.029 %) / gfx 212 / cut24 10.5-19.5 % /
  ext10 up to 32.9 % (legal19.py tab_f0 CELL 3 0.5,1.0, arm OFF). PSNR = clip arm within 0.04 dB.
- R-FIX encoder in-range index (decoder unchanged): MEASURED dead (legal19.py arm FIX): away grows (dng720 1057, gfx 294,
  cut24 19-38 %, ext10 28-76 %), PSNR -0.01..-6.9 dB, prefix overs 60-98. Algebra step (3).
- R-CLIP pure clip decoder + nearest-lattice reading (clipread19.py tab_f0 CELL 3 0.25,0.5,1.0,2.0): MEASURED not exact: misses
  dng720 754/132/4 (@0.25/0.5/1.0), gfx 89/33/0/1, spot @0.25 587, cut24 297-1127, ext10 1316-3003; LL/H5/H4 first. Violates P3.
- Ancestor inward rounding / cascade: algebra step (5) + SA18 D2 oracle (best single +-1 coarse re-choice fixes 0.1 % cut24,
  32.7 % dng720, 56 % gfx). Not built.
- Residual-domain clamp / "toward prediction P": still a re-read sum (steps 1-3); P's error sign is unknown too; no P on intra.
- Companding "rail at infinity": g^-1 many-to-one or saturating (= clip) -> violates P3 (REXT relative, SA13 T7 65/81 units).
- Censored reading, DOL, RC switch, PREVENT (pack §12.3): violate P3 or are fixed points (not one pass).
- Predict-only (P2 false): never-away by construction but IPL -15 NEG intra real, -2.7 dB inter proxy (SA18); E1d +12..60 % bits.
What an engine needs for never-away by construction at no efficiency cost: a representation in which NO output sample feeds an
average that the next encoder must re-read (P2 false) while keeping the anti-aliased (averaged) coarse bands that give the
coding gain. Under critical sampling these conflict (in any averaged group of n samples whose mean is re-read, the last sample is
fixed by the other n-1 and the mean). The only escapes left are outside P1/P3: (i) an average that the next encoder does NOT
need to re-read from the picture (e.g. carried by state both ends already share exactly — for inter frames the reference;
unmeasured, and intra/cut/heal frames have no reference), or (ii) an overcomplete representation whose re-read is exact (DOL
failed, 5-40 % mismatch). Verdict: with the averaging pyramid as the root choice, never-away per sample is NOT MET and cannot be
met by any route tested; the owner's "the design is the problem" applies to that root choice. Open: route (i).

## §L4 Exactness through generations (chain10.py tab_f0 CELL 4 RATES [AUTO]; every generation is a full encoder run on the
previous generation's decoded pictures; 4 frames; pictures AND bits compared per frame)
Blind re-encoder (auto=0: normal rate control, emits the reading of its own picture):
- gfx 0.5 x11: gen 2 differs (28080-79761 samples/frame), converges: fixed point from generation 6 (gens 6-11 identical).
- cut24 0.5 x11: fixed point from generation 4. ext10 1.0 x11: fixed point from generation 7.
- dng720 0.5 x11: gen 2 differs 157229-576360 samples/frame (run killed/incomplete at write time).
- gfx 0.5 -> 1.0 x6 -> 0.5 x4: at 1.0 fixed from gen 3; back at 0.5 the chain re-converges from scratch (gens 8-11 differ,
  NO fixed point within 11). dng720 1.0 -> 0.5: gen 2 differs 1.6 M samples/frame.
=> A blind encoder is NOT byte-exact at generation 2; exactness needs the hop rule.
Hop rule (auto=1, new, encoder-only, one predetermined choice per frame): if the input reads canonically at plans whose every
step is >= 2 (only a decoded picture does) and the reading fits the prefix bound, emit the reading; else encode.
- gfx 0.5 x4, 3 frames: frames 0, 1 identical at gen 2; frame 2 differs (32863 samples) -> fixed point from generation 3.
  Frame 2's reading was rejected by the rule (cause under investigation: no plan with all steps >= 2, or prefix bound).
