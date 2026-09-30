# SA15 RESUME — 2026-09-28 11:30 (round 2 in progress)

## 1. Design state (one paragraph)
CPP-LL: continuous 2/6 pair pyramid (5H x 2V), decoder-computed legal intervals per pair (legal for any
stream), lattice-locked temporal prediction (motion-compensated picture supplies hint indices; reconstruction
= intra lattice point, independent of the reference). Changed since DESIGN.md (round 1): (a) symbols are
OPEN-LOOP (quantised from the picture's own TS coefficients) so every candidate knot's exact code length is
computable in one pass -> exact CBR with no guard (cost -0.02..-0.09 dB, out/t11_openloop.txt); (b) rate
control = exact lanes over a 13-knot ladder per slice, prefix-bound credit, rho = 1/16 refresh pot (unspent pot
returns to credit), knot kept from last frame when it fits (still content not requantised); (c) NO
per-coefficient state (step memory rejected for 8K memory/DDR); kept values live on the current field;
(d) canonical plan reading per slice (coarsest exact-and-fitting knot; intervals from the picture's own
pyramid; band lag makes each slice final after its own packet) and gen-1 emits what the reading returns;
(e) canonical vectors from decoded history (block match of D(t-1) vs D(t-2)), measured DURING frame t-1
(its rows as reconstructed vs the resident t-2 band) -> no extra reference read, known before frame t is coded
(current-picture search + re-description was tried: emitted-vector costs differ from the rate decision's ->
plan-reading loop, abandoned); (f) canonical
index = smallest-|q| index reproducing the value; (g) one-way refresh = bit-metered top-down sweep of
hint-free symbols incl. the ahead data of refreshed blocks, clean-region vector rule (blocks feeding hints
above the front read only rows above the front); (h) static tANS tables: 10 band classes x 2 modes x 3
contexts, L = 1024 (60 tables, 1.1 Mbit), trained on footage disjoint from the test cells: set B (5 clips,
excludes floorballtrainL/highwayviewL) = primary, set A (7 clips) for comparison. Slice S = 4 at 720p,
8 at 1080p/2160p, 4 at 4320p. Model code: notes/cpp2.py (plane codec), notes/seq2.py (sequence codec +
Decoder simulation), notes/run2.py (driver, gen-2 check), notes/eval2.py (NEG per frame + PSNR + owner tools),
notes/loss2.py (packet loss + sweep), notes/join2.py, notes/rowstats2.py, notes/render2.py, notes/t12_harm.py.

## 2. Coordinator items + owner points
| item | status | result / file |
|---|---|---|
| 1 rate control modelled (CBR prefix, knots, still rule, intra sizing, cut, mixed) | RUNNING (final code) | logs out/r2/log/*.txt ("overflow", "jump>+8", credit); design text DESIGN_v2.md R1 |
| 2 A5 one-way sweep + loss | FINAL CODE: sweep STALLED at row 544 (unit extra > reserve), loss never repaired (out/r2/log/loss_rho4.txt) -> R2 unit redesign written, to model after the queue. Earlier build: (recovery complete, damage never re-entered refreshed rows, floor720 rho=1/4: decoder==encoder from frame 13 after loss at f3); RERUNNING on final code (loss_rho4) | out/r2/old/loss_rho4.txt; cost of refresh (earlier build) NEG -0.27 floor720 @0.5 |
| 3 join under exact CBR | NOT MET: 24-frame run plateaus at 43-55 of 180 slices differing (root + fix in DESIGN_v2); earlier: floor720 J=6: differing slices 167,156,128,105,86 of 180 (f6-10), converging ~20 slices/frame; 24-frame run queued (floor720_24 then join24) | out/r2/log/join_floor720.txt, join24_floor720.txt |
| 4 real entropy, disjoint tables, per-packet flush | DONE (tables); efficiency RUNNING | out/tables_A.pkl, out/tables_B.pkl, notes/train.py |
| 5 one config for all cells + highwaydriveL + worst-frame NEG | PARTLY DONE (table DESIGN_v2 R5, 10 points: NEG >= today on 3, tie 1, lower 6 (up to -1.13); PSNR better 28/30): NEG mean/worst CPP vs today: dng1080@1.0 92.29/90.78 vs 93.31/91.77; spot@0.5 93.99/90.30 vs 93.25/87.10; volley@0.5 92.48/90.14 vs 92.29/90.83; hwy@0.5 92.56/89.76 vs 93.58/90.58. RUNNING: floor, 1.0 cells, tables A, hp, formats, cut, mixed. dng720 @0.5 DONE (g2 identical): NEG 90.34/w 86.25 vs 90.16/87.22, PSNR 37.35/36.59/37.61 vs 35.22/36.10/37.14. dng720 @1.0 DONE: NEG 93.05/worst 91.49 vs today 94.05/92.31 (WORSE -1.0), PSNR 39.10/37.73/38.56 vs 38.19/37.08/37.95 | eval: notes/eval2.py (per-frame NEG cross-checked = negscore.sh 88.858) |
| 6 flatness root cause | ZH tested: floor720 flat 26.9% vs 33.3% but NEG -0.77 -> rejected as fix; refresh cost rho=1/16: NEG -0.37 (floor720). EARLIER: earlier build showed texture energy lost in INTER frames only (intra retains more than today); hypothesis = keep hysteresis window around zero hints widens the dead zone; ZH=1 variant queued | out/r2/flatroot_dng720.txt, notes/flat_root*.py; runs dng720_0.5_zh1, floor720_zh1 |
| 7 legality cost/harm | DONE: zero bit cost natural+graphics at 0.12-3 bpp (gfx 0.2 bpp fixed); rail plates +2..16 % bits (open); "never away" NOT met (structural) | out/t12_harm.txt, DESIGN_v2.md R7 |
| 8 formats | 4:2:0, 4:4:4/12, 4:2:2/8: g2 identical, oob 0, no special row phase (DESIGN_v2 R8); 4:2:2/12 and limited range: g2 identical, oob 0. RAILS DONE on final code: all 7 g2 identical, 0 oob, prefix held (min credit +1.1k..+25k) (out/r2/rails_final.txt); formats RUNNING | out/r2/rails_summary.txt; jobs f420/f444_12/f422_8/f422_12/lim |
| 9 half-pel | DONE on 3 cells (hwy running): no gain (NEG -0.13/-0.09/+0.20 at +1.4-1.9 % bits); integer kept | DESIGN_v2 R9 |
| 10 renders | DONE: out/r2/renders/ (dng720 f8, floor f6) | notes/render2.py |
| 11 latency margin + DDR | DONE (720p50 3:1 0.991 ms, owner accepted; Lv = 2 everywhere) | DESIGN_v2.md R11 |
| owner: 8K must fit (on-chip + DDR) | DONE (arithmetic): fits ZU7EV at all formats incl. 8K 4:4:4 12b (83 % URAM); DDR = today's traffic model (26 bit/sample, no state, no 2nd frame); adversarial-locality DDR simulation NOT run | DESIGN_v2.md R11b |

## 3. Built and REJECTED
- Closed-loop predict-only pyramid (per-sample clamp): -1.4..-5 dB, chroma worst. notes/t1_po_vs_53.py, out/t1b_*.txt.
- Causal vertical predictor / 3 levels: +5..9 % error on every 8th row (design-created special row). out/t4_*, out/rowstats_dng720_b0.5_v26cL3.txt.
- Boundary-snap reconstruction (legality free on rails): snaps coarse means to rails, MSE x7.7 at 0.12 bpp. notes/cpp2_snap_rejected.py.
- One-slice backtrack in plan recovery: a search + rework of an emitted slice. notes/seq2_backtrack_rejected.py.
- Per-coefficient step memory: +14 bit/sample DDR and frame-sized state (8K ruling). notes/seq2_stepmemory_rejected.py, cpp2_stepmemory_rejected.py.
- Motion from D(t-1) vs D(t-2): extra reference read (8K DDR). Replaced by current-picture search + canonical re-description.
- 720 tables of L = 2048 (26.5 Mbit): not implementable; replaced by 60 x 1024.
- Refresh-row cost charged to the rate lanes: starved slices (kmax). Now charged to the pot.
- Model bugs found and fixed (not design): OBMC cached one shifted plane per distinct vector (tens of GB on motion cells, OOM kills); snapshot aliasing (restore reused mutable state), per-frame frame_info retained (OOM), ahead data on the next slice's field (band lag), gen-1 emitting pass-1 state instead of the canonical description's state.

## 4. Jobs running now (14:15: queue notes/runlist.py jobs_final6.txt, 6 parallel, the 23 unfinished 1080p/format jobs, after fixing an OBMC memory blow-up (cached shifted planes per vector -> OOM kills); earlier: jobs_final5.txt, 7 parallel (10 caused OOM kills), 1080p runs 8 frames (steady 2-7), restarted 12:45 after the vector change; finished final-code logs copied to out/r2/keep/)
Command form: `TABLES=../out/tables_{A,B}.pkl nice -n 19 python3 run2.py SRC W H BPP N TAG [--S 4] [--gen2 0] [--hp 1] [--fmt ..] [--depth ..] [--rng ..]`
(loss: `python3 loss2.py SRC W H BPP N lossframe lossslice rho TAG` with S=4 env).
Outputs: out/r2/log/TAG.txt (per frame: bpp, PSNR, knots, overflow, credit, refresh rows, gen-2 line
"g2_vs_g1: identical / N differing samples", "GEN2 differing samples=..."), decodes out/r2/TAG.yuv.
39 jobs: dng720 0.5(g2)/1.0, dng1080 0.5/1.0, spot 0.5/1.0, floor 0.5(g2)/1.0, volley 0.5/1.0, hwy 0.5/1.0,
gfx 0.5(g2)/1.0, cut (g2), mixed (g2), floor/hwy with tables A, hp x4, formats x5, rails x7, floor720
ref16/ref0, loss_rho4, ZH x2. Expected: 720p ~1 h each, 1080p 12 frames with canonical re-description
~3-5 h each; whole queue ~12-15 h. Evaluate each with:
`python3 eval2.py TAG SRC W H today=<today decode> cpp=../out/r2/TAG.yuv` (today decodes: SA7 out/DM/*_a0.d.yuv
for dng720/dng1080/spot/gfx; out/today/{floor,volley,hwy}_b{0.5,1.0}.d.yuv) and rowstats2.py SRC DEC W H 12 S.

## 5. Known open problems
- STILL SHIMMER (mixed clip): 40-60 % of still samples change per frame during the refinement ramp, ~50/50 toward/away; root = 1/8-octave refinement steps; fix designed (octave-only refinement, nested) not modelled. hwy@1.0 NEG -1.50, volley@1.0 -0.50. Tables A vs B: no flattery. Cut: g2 identical, NEG 91.13 worst 83.09, 42/44 luma artifactmap regions on the cut frame (not inspected).
- NEG vs today: dng720 @0.5 +0.18 mean but -0.97 worst frame; @1.0 -1.00 mean (PSNR better on every plane). Efficiency bar not met at 1.0 yet. Knot-stability rule off: NEG 92.87 (not the cause).
- Refresh: root cause and redesign written in DESIGN_v2 R2 (unit sized by worst-case cost; bound T <= 2 c L_max/(rho bpp)+1 frames, long in the worst case -> decision open). Refresh stall found (a 4-row block's hint-free extra > one frame's reserve at 1.0 bpp: front stuck); fixed 13:30 (pot saves up to 8 frames when blocked); jobs started before 13:30 ran with the stall.
- Rail plates: legality costs +2..16 % bits at contribution rates (root: source samples on an interval boundary need the reaching index); lanes ignore clamp relabels, so the prefix bound was exceeded by up to ~2 slice budgets on cut24 @1.0 and one overflow on ext12 (earlier build).
- "Never away" not met: mean-preserving (exactness-preserving) clamps move the partner sample; ~50/50 on natural content (few samples), up to 259-395 codes excess at 0.1 bpp.
- Still content when the knot must move (pipe-forced): requantised (a quality change, not flicker in steady state); mixed still/moving slices are the risk -> mixed_0.5 run.
- NEG vs today at 0.5 bpp dng720 was a tie (90.12 vs 90.16) with real code lengths on the step-memory build; worst frame -0.3. Efficiency on final code unknown until runs finish.
- Inter-frame texture loss (flatness) -> ZH hypothesis under test.
- One-way refresh cycle is slow at rho = 1/16 (front 4-24 rows/frame at 720p) -> recovery bound = 2 cycles, content dependent; bound formula in DESIGN_v2 R2 still to be written.
- 8K DDR not simulated with the adversarial model; on-chip numbers are arithmetic.
- C2 note: the encoder reads only the reference frame now (issue resolved by change (e)).

## 6. Next steps, in order
0. (18:50) Round 2 handed in. Remaining: hwy_0.5_hp still running (add to R9); then fill R9 and R8 rows. Design changes pending decision: R2 refresh unit, octave-only refinement (still shimmer), join via refresh.
1. Let the queue finish; do NOT change seq2.py/cpp2.py while it runs (runs import at start; changes affect only later jobs).
2. Evaluate every cell with eval2.py (NEG mean + worst frame, PSNR mean + worst per plane, tools) and rowstats2.py; fill DESIGN_v2 R5 table (one config, tables B; A-vs-B on floor/hwy).
3. join2.py on out/r2/floor720_ref16.yuv (J=6, frames 6..11), report frames to byte-exact under CBR.
4. Loss: read out/r2/log/loss_rho4.txt; write the recovery bound (cycle length x 2) and refresh cost (floor720_ref16 vs ref0 NEG/PSNR).
5. Flatness: compare dng720_0.5 vs dng720_0.5_zh1 (NEG, flat%), and flat_root.py per-band retention; if ZH fixes inter texture loss without flicker (check still input test), adopt.
6. Renders: render2.py on dng720_0.5 and floor_0.5 frame 8, Y/Cb/Cr.
7. Write DESIGN_v2 R2 (A5 bound), R3 (join), R5 (efficiency), R6 (flatness), R8 formats table, R9 half-pel, R10 renders; final summary.
