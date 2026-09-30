# SA16 RESUME (state file; updated after every finished item)

## State (2026-09-28, session 1)
- Read in full: BRIEF_SA16.md, PROJECT_CONSTRAINTS.md rev 6, MEMO_PRIOR_DESIGNERS.md, MEMO_SA15_FINDINGS.md.
- Grepped: v537 TEMPORAL_T5.md 5.1-5.5 (today = coefficient-domain value prediction `coef = pred + q*2^s`,
  ONE history vector per slice transmitted, interleaved rolling refresh refresh_r = 8, unclipped biased pixel
  domain), DDR_WINDOW_CACHE.md 1-2, LATENCY.md, ledger S5.29 (decoder-derived vectors fail A5), S5.369-S5.373.
- Design name: **CQP-1** (causal-pyramid, value-domain prediction). See DESIGN.md (written incrementally).

## Design decisions taken (with the root reason)
1. Transform = pair mean/difference pyramid (S-transform mean, difference predicted from means), 2V x 5H,
   4-row blocks, predictors TWO-SIDED in both axes (coarse data of the next two blocks carried one/two
   blocks ahead). MEASURED (out_t_pred2.txt, out_t_pred3.txt, training clips bosphorus/cityalley, rate-matched
   PSNR vs two-sided/two-sided, Y/Cb/Cr): causal-both -2.83/-0.87/-0.81 dB (bosphorus) and -0.84/-0.31/-0.34
   (cityalley); H causal only -1.45/.../...; V causal only (both levels) -1.38; V level-1 in-block only
   -0.96/-0.40/-0.35 and -0.47/-0.07/-0.10; V level-2 causal only -0.44/-0.45/-0.43 and -0.34/-0.21/-0.21;
   closed-loop encoding recovers nothing (-2.70). DECISION: two-sided everywhere (no dB left on the table);
   the causal idea (first plan) is REJECTED as a design-created dB loss.
1b. Refresh with two-sided predictors: column band of Bw units per frame (8-frame cycle) plus ONE guard unit
   (intra) and one LL-only-intra unit to its right: the two-sided reads at every level enter the next unit only
   through its left-most chain, which is exact when the guard is intra and the second unit's LL is intra
   (proof in DESIGN.md). Every slice carries the same intra fraction -> no starved band (a ROW band is starved
   at every cycle start under the CBR prefix bound: latency cost proportional to the band height, rejected).
2. Legality = interval clamp at each leaf from final values (the SA15 evidence), plus an encoder two-candidate
   rail choice (reach / not reach) by pair error, so legality can never make a pair worse.
3. Temporal = value-domain prediction in the coefficient domain c = T(MC pred) + step*q (today's principle,
   proven generation-exact when the reference is the legal picture), vectors from decoded history
   (D(t-1) vs D(t-2), during t-1), TRANSMITTED per 64x8 block, bilinear OBMC, next slice's vectors carried
   one slice ahead (symmetric OBMC at every slice edge, no special row).
4. Refresh = vertical band of 1/8 of the units per frame, 8-frame cycle; a static unit (all 4 OBMC vectors
   zero) is re-sent as an exact hold of its inter result (no pop); clean-region barrier on the fetch.
5. Rate control (REDESIGNED after the coordinator's intervention on trial coding): octave-nested per-band
   steps, 30-entry refinement order, one plan integer P per slice. OPEN-LOOP lanes (10 octave lanes, then 30
   refinement lanes inside the finest fitting octave = one predetermined re-choice), each lane = quantise +
   table lookup, exact symbol bits because contexts are PLAN-INVARIANT and clamp-independent (inter: |c_p|
   class x vector class; intra: the unit's decoded LL brightness class), flag bits reserved at their worst case.
   Then ONE closed-loop synthesis of the slice (the reference update the encoder does anyway) and canonical
   EMISSION from the final values: plan self-read (boundary-aware), cheapest reproducing mode, hold =
   'static and finals == reference unit', hold plan read from finals. These are exactly the rules a gen-2
   encoder applies to the picture -> gen 2 bit-identical by construction; emitted <= lane estimate <= budget.
   Tables monotone in |q|; hold plans coded as EG0(PMAX - Pu) (monotone under re-description).
6. Hold rule in the lane: a static band unit whose inter residual is all-zero at the lane plan is described as
   the reference unit itself (canonical against the reference's own intervals). The earlier 'hold of the inter
   result' was REJECTED: after a clamp-heavy reference its coefficients are off every coarse lattice (measured:
   Pu = 0, symbols at step 1, slice cost 10x the budget).

## Model correctness status (23:50)
- gen-1 encode -> decode: rt = 0 on every frame tested (decoder path from symbols == encoder reconstruction).
- gen 2 (encode of the decode): pictures AND bits IDENTICAL on dng720 frames 0, 1, 2 (180/180 slices via the
  reading path). Bugs found and fixed on the way (all root causes, no patches):
  1. rounding phase was array-relative (window synthesis != frame synthesis by one code) -> absolute phase;
  2. HL1's interval depends on its own block's fine means -> HL1 moved to the fine group; HH predictors chosen
     not to read the block below (HH2 causal, HH1 in-block; cost measured, out_t_pred4.txt);
  3. hold of the 'inter result' is on no coarse lattice -> hold = the reference unit itself, per group, LL at
     full precision (signed EG0 residual), rule 'static and group residual all zero at the plan' (lane) ==
     'static and finals == reference' (emission and gen-2 reading);
  4. contexts from neighbour magnitudes are clamp-dependent -> plan-invariant contexts (|c_p| class x vector
     class; intra: LL brightness class); tile significance flags per (unit, band) so zeros cost ~0;
  5. intra LL raw index had a -D/2 bias (floor) -> rounded index; intra LL now index-domain DPCM from the left
     unit (absolute lattice kept);
  6. mode rule: emission reads 'inter iff the LL-group finals are inter-reproducible', the lane codes inter
     when the emission will read inter (cost preference, or prediction on the lattice);
  7. degenerate interval (ilo == ihi): canonical index 0 in the lane too;
  8. flag bits in the lane made exact (worst-case reservation caused gen-2 read-misses by a few bits).
  9. (00:05) the emitted-vs-estimate gap was a stray `elif` from an earlier edit that added hold symbol bits a
     second time in the emission; removed -> estimate >= emitted on every slice, no 'emit_over_est'. The first
     dng720 evaluation (started before this fix) collapsed from frame 6 on (credit driven negative) and was
     discarded; evaluations restarted 00:06 with the corrected code and pass-1 tables.
  10. the floor lane (P = 299): LL still coded (intra index-DPCM at D = 128, inter LL residual), no detail
     symbols. INTER slice on it = the prediction + LL correction (prediction texture kept, no new detail);
     INTRA slice on it (frame 0, cut, join, refresh unit) = LL-only 32x4 blocks = a flat rung slice. It is a
     documented failure mode, NOT a guarantee (coordinator's question, 00:25). Structural facts: a slice
     always has >= its nominal share (credit only adds); lane costs are content-dependent, so no analytic bound
     excludes the floor on full-amplitude noise at 0.25 bit/sample. Claim to be MEASURED: at >= 0.5 bpp on
     every cell incl. rails and cuts, the floor lane and the coarsest octave lanes are never chosen (per-cell
     plan histograms added to every evaluation: floor / >=270 / >=240, intra and inter separately). The
     collapses seen so far came from the accounting bugs (9, 11), not from content.
  11. (00:20) holds: a unit's hold plan Pu was dragged to <= 89 by one off-lattice LL value (units that moved
     before becoming static), turning a hold into a near-lossless re-send (> 1 kbit/unit) that the lane took
     regardless of cost -> budgets exhausted -> floor. Root fixes: the LL (sent at full precision anyway) no
     longer constrains Pu; hold only if Pu >= the previous slice's emitted plan (known at both generations),
     else fresh intra at the slice plan.

## Item status
| item | status | numbers |
|---|---|---|
| model written (omc16.py) | DONE (open-loop lanes, one synthesis, canonical emission) | rt0, g2 identical f0-f2 dng720 |
| transform bijection + legality intervals | DONE | pyr.py/pyr2.py self-tests pass; intervals brute-force exact; window phase exact from block b0+2 |
| HH predictor decision | DONE | out_t_pred4.txt: causal HH2 + in-block HH1 cost -0.16/-0.07/-0.09 (bosph) -0.24/-0.05/-0.08 (city) dB; taken for XS latency parity |
| tables trained on disjoint footage | pass 1 running (5 clips x 2 rates x 4 frames), pass 2 next | - |
| efficiency vs today (6 cells x 2 rates, Y/Cb/Cr, NEG first, worst frame) | todo | - |
| row-phase statistics | todo | - |
| g2 exactness (incl. rails, formats) | todo | - |
| still / mixed clip | todo | - |
| loss + join | todo | - |
| memory / latency / work | todo | - |

## Rejected ideas (with reasons)
- Two-sided horizontal predictor + column sweep: the clean region's right edge would read a dirty mean -> a
  special column during refresh. Rejected before modelling (design-created artifact).
- Two-sided predictors + ROW sweep: the top band at each cycle start has no credit under the CBR prefix bound
  -> a coarser band once per cycle (visible band). Rejected before modelling.
- Ahead means (SA15) : not needed once predictors are causal; +4 lines latency avoided.
- Lattice-locked prediction (SA15): root of F1-F4 per the memo; not used.
- Source-searched vectors: not reproducible at gen 2 without a fragile lattice-exact vector search; history
  search kept (today's principle, SA15 measured).
- Dead-zone width as the sub-octave rate knob: kills texture (flatness class). Per-band octave refinement
  order used instead.
- Contexts from neighbouring symbol magnitudes (SA15-style): the decoder's clamp legitimately changes many
  zero-index coefficients in dark regions (measured: 207 of 1280 in one LH1 band row of dng720), so any
  open-loop cost with value- or magnitude-based neighbour contexts mis-states the decoder's bits and a gen-2
  encoder can fail a budget gen 1 fitted. Replaced by clamp-independent contexts (see 5).
- Closed-loop lanes (one full slice coding per candidate plan): trial coding (coordinator: forbidden).

## QUOTA STOP 00:35 2026-09-29 — resume here at 03:40
Detached master queue: `model/queue_all.sh` (setsid nohup; log `out/queue_all.log`; status lines with exit
codes in `out/eval/queue_status.txt`; `QUEUE_ALL done <date>` marks completion). Phases:
0. waits for the jobs started 00:23 (all nohup, all on the CURRENT code, tables_p2):
   - `evalcell.py dng720 0.5|1.0 12 tables_p2` -> `out/eval/dng720_0.5.log` / `_1.0.log` (summary line 'NEG mine
     ... today ...'), per-frame `out/eval/dng720_*.enclog` incl. `planhist {floor, ge270, ge240, n, intra}` per
     frame (the floor-lane / coarsest-lane counts the coordinator asked for), json in `out/eval/dng720_*.json`;
   - `t_hh.py` HH_TWO=0/1 -> `out/eval/hh0.log`, `hh1.log` (last line: NEG mean/worst + PSNR Y/Cb/Cr, bosphorus
     6 frames 0.5 bpp; the NEG-first restatement of the HH predictor choice);
   - `t_seq.py still dng720 0.5` -> `out/seq/still.log` (changed samples per frame must be [0,0,0] from t=1);
   - `run_train.sh p3` (corrected code, init tables_p2) -> counts `out/tables/cnt_*_p3.pkl`, merged by the queue
     into `out/tables/tables_p3.pkl` (informational; all evaluations use tables_p2 for consistency).
1. `run_queue.sh tables_p2 6 dng1080:0.5 ... volley:1.0` (10 points, 6 parallel): per point
   `out/eval/<cell>_<rate>.log` (summary + ROWPHASE json lines for mine and today), `.enclog`, `.json`,
   renders in `out/renders/<cell>_<rate>_{mine,today}_*.png` (decode, decode+grid, per-plane signed x4,
   |diff| x4, 8x8 level maps, all with legends); decodes deleted after scoring. Expected ~2 h after phase 0
   (1080p frame ~4-5 min under load).
2. sequence tests (6 in parallel): `out/seq/mixed.log` (still half: changed / toward / away per frame),
   `gen.log` and `gen_floor.log` (3 generations: bits per gen and differing samples vs gen 1 per frame),
   `loss.log` (slices 20,21 lost at frame 4: damaged samples / rows per frame until 0), `join.log` (join at
   frame 5 from grey: differing samples per frame until 0; bound expected <= 16), `rails.log` (cut24, ext10,
   ext10b @0.5/1.0: oob, PSNR legal vs clip arm, samples worse than clip, g2 identity).
How to check: `tail out/eval/queue_status.txt`; every job line carries its exit code; a missing 'NEG mine' line
or a Traceback in a .log = failed run.

## 03:40 session: efficiency verdict = DEFECT in the plan weights (root), not the transform or prediction
- Queue results: NEG far below today on all 12 points (dng720 @0.5 71.1 vs 89.1 ...), PSNR -1..-3 dB; floor
  lane never used (planhist floor 0, ge270 0). Loss already present on the intra frame 0: 30.60/33.56/33.88 vs
  today 31.43/35.26/36.24. No column phase (mod 32: 16.1-17.1) or row phase (mod 4: spread 4 %) pattern.
- Per-band error energy (dng720 f2 @0.5, mine | today): LL 70|7, H5 219|27, H4 167|45, H3 138|84, LH2 191|147,
  LH1 226|369, HL1 188|325, HH1 796|887 -> my allocation is tilted to the fine bands. Cause: the step weights
  equalise TOTAL distortion per band (lw = number of difference stages); RD-optimal is equal distortion per
  COEFFICIENT in the synthesis-gain-normalised domain: step_b ~ 1/sqrt(gain_b), gain_LL5 = 128 -> LL step 1/11 of
  the level-1 step, not 1/2. Fix: gain-derived ladder (base exponent + sub-octave offset from the measured
  synthesis gains, no tuning), retrain tables, rerun dng720 @0.5/@1.0 + spot @0.5.
- RAILS exit 1: t_rails.py's clip arm (legal=False) has no prediction boundary masks (MP None) and hold_target
  dereferences them -> code bug in the comparison arm only; fix: hold_target without masks when MP is None.
- HH NEG check (bosphorus 6 f, 0.5 bpp, tables_p2): hh0 (chosen, causal HH2 + in-block HH1) NEG 85.06 worst
  83.65 PSNR 41.59/45.57/45.43; hh1 (two-sided, 4-block-ahead latency) NEG 85.16 worst 83.64 PSNR
  41.72/45.68/45.53 -> +0.10 NEG / +0.1 dB for the two-sided form; the chosen form stands (latency parity).
- still test (dng720 f0 repeated, 0.5 bpp): 40-57 % of samples change per frame while the picture converges
  from 30.6 to 37.5 dB (all refinement of a coarse intra frame); to be re-judged after the weight fix.

- 04:20 transform check (t_53.py, out/t53.log): CQP pyramid vs plain 5/3 (2V x 5H), BOTH with gain-normalised
  equal-per-coefficient steps, matched zeroth-order entropy: bosphorus -0.76/-0.66/-0.63 dB, dng720
  -0.53/-0.19/-0.19 dB (Y/Cb/Cr). That is the transform's real price (Haar means vs 5/3), a design property to
  report; the -1..-2.5 dB seen in the codec came from the plan weights (defect, fixed 04:15: XEXP ladder from
  measured gains, PMAX 359, P=0 lossless). Variants rejected: chroma-first priority (no change), DZ 0.5 (-0.6 dB).
- 04:20 running: run_train.sh p3 (init tables_p2, new ladder) -> out/tables/tables_p3.pkl (~25 min);
  t_var.py NEWLADDER (3 frames, old tables) -> out/var_ladder.log. Then: run_queue.sh tables_p3 3 dng720:0.5
  dng720:1.0 spot:0.5 (spot with 8 frames to fit the time box) and report NEG mean/worst + PSNR Y/Cb/Cr.

- 04:40 NEW LADDER, intra frame 0 dng720 @0.5 (old tables): 31.75/35.41/36.34 vs today 31.43/35.26/36.24 dB
  -> defect confirmed and fixed at the root (was -0.8/-1.7/-2.4). Queue results from 01:57 are VOID for efficiency.
- 04:40 sequence results (old ladder, mechanics only): gen chain dng720 3 generations byte-identical (bits +
  pictures) 6/6 frames; floorball S=8: gen3 == gen2 but gen2 != gen1 from frame 1 (S=8 bug, diagnostic
  out/dbg_gen8.log); loss: bounded rows 48-133, repaired by frame 19 (15 frames), 233-sample residue for 4
  frames; join at f5: NOT exact after a cycle (204k luma at t=15, 16.5k at t=23; diagnostic out/dbg_join.log);
  mixed clip: still half 60 % samples change per frame, 58/42 toward/away (shimmer class; root = the rate
  control refining still content at ever finer steps; not solved).
- NOTE for the stream design: inter contexts use |c_p|, so a joiner cannot entropy-decode dirty units; the
  symbol stream must be unit-major (clean prefix decodable) - to be written into DESIGN.md.

- 05:15 S=8 gen-2 flip root: hold decided from the SOURCE residual at gen 1 but from the finals at gen 2; a
  boundary clamp can return a non-zero residual to the reference value -> hold flips (floor f1 slice 103 unit
  14). Fix: holds decided from FINALS on both sides (static & band & finals == clamped hold target), the lane
  reserves max(hold, fresh) symbol bits for static band units (stats 'hold_flip' counts lane/emission
  differences). Re-check running: out/dbg_gen8c.log (expect t 1 diff [0,0,0]).

- 05:55 JOIN LEAK root (dbg_join.log: even the intra band differed at the join frame): the barrier limited the
  FETCH, but T(x_p) is computed on the whole prediction picture, whose two-sided predictors read across the
  barrier column -> the last clean units' c_p depend on dirty samples and the contamination walks left each
  frame. Fix (prepare()): clean units take c_p from the transform of a barrier-consistent picture (columns
  beyond the barrier replicated from the last clean column). Re-check: out/dbg_join2.log.
- 05:55 HOLD mechanism REMOVED (HOLD=0): (12) the dead-zone hold test is inconsistent between a source input
  (gen 1) and a finals input (gen 2): a fresh-coded static group whose finals quantise to a zero residual at
  Pe is held by the gen-2 lane -> picture flip (floor f1 slice 20 unit 14, HL1: gen1 final 0, gen2 64);
  (13) a held group re-sends the reference at the reference's own (fine) plan: the lane reservation for it
  inflated estimates 15 % and drove 4 slices to the floor lane (dng720 @0.5 f3). Refresh units are now
  always fresh intra at the slice plan; consequence: still content is re-quantised once per 8 frames in the
  refresh band (pop class) - documented weakness, not patched. Three points rerun without holds (run3a/b).

- 06:20 S=8 gen-2 (floorball f0-f1, no holds): pictures identical [0,0,0] both frames (out/dbg_gen8e.log).

- 06:40 FIRST VALID EFFICIENCY POINT (tables_p3, no holds, real code lengths, exact CBR): spot @0.5, frames 2-7:
  NEG mine 89.03 (worst 88.20) vs today 90.30 (worst 85.37); PSNR Y/Cb/Cr mine 39.69/42.80/46.01 vs today
  39.35/42.76/46.24; worst-frame PSNR mine 38.79/42.19/45.49 vs 36.51/42.10/45.65. artifactmap 0/0/0 both;
  smudgegroups 0 both; flatplane mine 35.9/33.6/39.9 % vs today 52.7/68.2/72.8 % textured blocks. Plan hist:
  floor 0 every frame; inter frames ge270 <= 4/135 (that is octave 9 of the NEW ladder = LL step 16, not a rung).
  Mean NEG -1.27 below today, worst frame +2.8 above; PSNR higher on Y, equal Cb, -0.2 Cr.

- 06:55 dng720 @1.0 (frames 2-11): NEG mine 90.08 (worst 88.84) vs today 92.96 (92.31); PSNR mine
  37.47/37.08/38.11 vs today 38.19/37.08/37.95; worst-frame 36.68/36.95/37.97 vs 37.88/36.92/37.87; artifactmap
  0/0/0 both; flatplane mine 35.9/6.7/22.5 % vs today 33.2/25.2/50.8 %. Floor 0; ge270 0.
- 06:55 JOIN (dng720 @0.5, join at f5 from grey, barrier-consistent c_p): region r becomes exact at phase r of
  the first full cycle (t=8: region 0 exact; t=9: 0-1; t=10: 0-2; t=11: 0-3 ...) -> exact after one cycle,
  bound = 8 + (8 - phase at join) <= 16 frames, as argued in DESIGN 1.5. (out/dbg_join2.log)

- 07:05 dng720 @0.5 (2-11): NEG 84.33 (82.94) vs 89.12 (87.22); PSNR 34.71/36.06/37.18 vs 35.22/36.10/37.14;
  artifactmap 30/0/0 vs 15/0/0; flatplane 46.2/23.4/51.5 vs 41.9/82.8/83.3 %; floor 0, ge270 0 inter.
  Row phases mine edge +4.5/+4.2/+2.8 % spread 7.1/6.5/4.6 % (4-row block signature) vs today spread 23.9/8.7/6.9 %.
- FINAL STATE written to DESIGN.md 5.1-5.3. Verdict: goal 4 not met on NEG; root choices named (pyramid price
  vs 5/3, PSNR-optimal ladder zeroing level-1 bands at 0.5 bpp, 15 % refresh). Not measured in time: rails,
  formats other than 4:2:2 10-bit, the other 9 efficiency points on valid code, renders of the valid runs
  (out/renders/ has the valid dng720/spot renders from the 06:00 runs).

## Where debugging resumes (03:40)
- First read `out/eval/dng720_0.5.log` and `_1.0.log`: NEG mean/worst and PSNR vs today (the direction decision).
  With the last 8-frame check (out/smoke3.log): bits <= pipe on every frame, no overflow, estimate >= emitted,
  PSNR 30.6 -> 34.6/35.1/35.9 dB by frame 7 at 0.5 bpp (today's 12-frame mean 35.2/36.1/37.1).
- Floor-lane question (coordinator 00:25): answer recorded under bug 10 above; verify with the planhist lines
  (expected floor 0, ge270 0 at >= 0.5 bpp on every cell); if not 0, the budget structure must change.
- HH NEG check: compare hh0 (chosen) vs hh1 (two-sided, 4-block-ahead latency); state NEG mean/worst + PSNR.
- Open: gen-2 identity beyond 3 frames (gen.log), the join bound (join.log), rails harm (rails.log), and the
  still shimmer on the mixed clip (mixed.log). Then DESIGN.md sections 2, 3, 5 with the numbers.

## Running jobs (session 2, resumed 22:40 after a session limit)
- evalcell dng720 0.5 and 1.0 (tables_p1, corrected code) -> out/eval/dng720_*.log (coordinator priority);
- t_hh.py (HH predictor NEG restatement, bosphorus 6 frames 0.5 bpp, HH_TWO=0/1) -> out/eval/hh0.log, hh1.log;
- run_train.sh p2 (started 23:46 with the double-count code; a p3 pass with the corrected code follows before the
  main queue: model/run_queue.sh TABLES NPAR cell:rate ...).

## Open problems
- ROOT CAUSES FOUND AND FIXED so far: (a) rounding phase used array-relative rows (window vs frame mismatch by 1 code);
  (b) mean-type leaf interval depends on the fine means of its own block -> HL1 moved to the fine group, HH predictors
  not reading below; (c) hold of the inter result off every coarse lattice -> per-group reference-unit hold.
- then: table training (run_train.sh p1/p2) and the 12-point efficiency queue.
- Not yet measured: efficiency, row phases, still/mixed, loss/join, rails, formats, memory/latency arithmetic.

## Next steps
1. write omc16.py; unit-test bijection/legality; 2. train tables; 3. run the 12-point efficiency set;
4. row phase, g2, still, loss, join; 5. DESIGN.md sections 4-8.
