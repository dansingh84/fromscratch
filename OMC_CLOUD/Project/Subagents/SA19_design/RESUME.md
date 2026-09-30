# SA19 RESUME — complete hand-over file (state 2026-09-29 ~22:05). A new session can continue from this + DESIGN.md.

## 0. Current priority (OWNER, binding, supersedes all efficiency work)
Legality + byte-exactness + zero legality-caused artifacts, THE BEST mechanism; never-away must be closed from the design or
declared impossible per route with evidence. Exactness bar = >= 10 generations byte-identical pictures AND bits every frame,
incl. CBR re-encode chains and baseband hops at the same and at different rates; report the generation of the fixed point per
cell. Nothing goes into today's codec; the NEW engine must meet all four goals. Full pass bar in DESIGN §L (end).
Status: §L comparison written (DESIGN §L, choice = leaf-interval clamp #9 as decoder rule). Never-away routes being measured:
- R-FIX (encoder-side in-range index choice, decoder unchanged): MEASURED DEAD (item L1 below).
- R-CLIP (pure clip decoder + nearest-lattice gen-2 reading): MEASURED DEAD — misses on natural too (dng720 @0.5 132, @0.25 754;
  gfx @0.5 33; spot @0.25 587; rails 297-3003), coarse bands first (their steps are the smallest). Logs out/clipread_*.log.
- 10-generation chains of the decoder-clamp core (#9) with BLIND re-encoders (read=False), same and mixed rates: running
  (bench/chain10.py, queue out/q_chain.txt, logs out/chain_*.log).
- R-CASCADE (ancestor inward rounding): partners predict dead (sibling conflict, support-wide away moves); record D2 0.1-56 %.
All efficiency arms (b0,c0,s0,q0,f3,r2,x0, q2) were KILLED at the directive (no eval results; partial training only).

## 1. Setup (how to run anything)
- Sandbox: Subagents/SA19_design/. bench/ = copy of SA18's bench used as INSTRUMENT (transform/legality/entropy/motion
  elements) + my own code. out/ = logs, tables (tab_*.pkl), decodes (out/dec), eval JSONs (out/eval).
- My code: bench/tpp.py (TPP sequence layer: band-split two-past prediction, Wiener weight `wk`, chained V2 `v2mode=chain`,
  still rule hold1/catch, rate split `split` [REJECTED], ECSQ `ecsq`, cheapest reading `cheap`, reconstruction offset `ro`);
  bench/tpp_run.py MODE CELL BPP TABLES TAG key=val (MODE train|eval|chain; eval = 12 frames, NEG via metrics.py = owner's
  VMAF-NEG model, frames 2-11, vs today's real decodes yuv.TODAY; chain = gen1->gen2->gen3 identity); d3_bands.py (per-band
  error vs today); bits_bands.py (bits per band group, vector share); away19.py, legal19.py, clipread19.py (legality);
  s1_bipast.py / s1b_hist.py (fusion proxies); rail19.py (SA18 rail diagnosis).
  bench/codec.py additions (all switchable, default off): catch-up hook `catch`, ECSQ `ecsq`, `alloc` rate split, `read_cheapest`,
  `ro_inter`, `enc_fix` (R-FIX); bench/pyr.py addition: FIX hook `_fix` (encoder-only, R-FIX).
- Runners: out/q.sh ABS_FILE (runs each line, <= 6 SA19 python jobs; lines get </dev/null); out/arm.sh ARM START "args"
  "cell:bpp ..." [ENV] (train bos/city/traffic x 0.5/1.0 on the exact config -> tab_ARM.pkl -> evals). Tables for a config
  are ALWAYS trained on that exact config (disjoint clips bos, city, rsg, traffic, winter; 5-clip sets f0/f1/f2, 3-clip arms).
- Kill rule: runner scripts first, then python children (by /proc/PID/cwd = SA19_design), then re-check. Never pkill -f with a
  pattern that appears in the same command line (kills your shell, exit 144).

## 1b. Latest (22:40): never-away VERDICT written (DESIGN §L3: premises, step-by-step proof, every closed route with its
measurement/command); 10-generation chains (DESIGN §L4): BLIND re-encoders are NOT exact at gen 2 (fixed point at gen 4-7
on cut24/ext10/gfx; none within 11 on mixed rates); new HOP RULE (tpp auto=1: emit the canonical reading when the input
reads at plans with all steps >= 2 and fits) makes gfx frames 0-1 identical at gen 2, frame 2 still differs (investigating).

## 2. Items (all REAL = real code lengths, exact CBR, full frames; NEG mean (worst frame), then PSNR Y/Cb/Cr; @0.5 bpp)
Today (v537 real decodes): dng720 90.16 (87.22) 35.22/36.10/37.14; dng1080 91.08 (87.51) 35.32/34.67/35.75; floor 95.98
(92.41) 40.71/44.73/44.31; spot 93.76 (87.10) 39.54/42.80/46.31; hwy 93.73 (90.58) 41.05/47.31/43.90; volley 92.37 (90.83)
41.28/43.36/45.90.
| id | item | result |
|---|---|---|
| R0 | bench reproduction (SA17 tables tab_eb_r2, SA17 config) | dng720 88.97 (88.09) 34.43/36.12/37.22 = SA17 88.97 (88.10) |
| RL | SA18 rail breaks (tab_f1, bank OFF), rail19.py | ext10 @1.0/@2.0 gen-2 pictures AND bits identical 5/5 -> SA18's break came from its table bank; gfx @0.25 49 prefix overs on frame 2 (max +85 bits) reproduce = CFV-1 pass-2 accounting (recorded only) |
| T0/T1 | TPP chains gfx @0.5 (fusion, Wiener, catch, split, ECSQ, ro2, cheap reading) | gen 2 and gen 3 pictures + bits identical every frame (5-6 frames). NOT yet 10 generations. |
| S1 | fusion proxy, ORACLE source vectors, SA17 decodes | luma fused/P1 residual L1/L2/coarse: spot .81/.82/.92, hwy .85/.88/1.01, floor .91/.93/1.03, dng720 .92/.93/.99, volley .96/1.00/1.21; chroma L1 .93-.995; fused prediction blurrier |
| S1b | fusion proxy, REAL field V2=2V1 | spot .90/.96/1.08, floor .975/1.02/1.10, hwy 1.00/1.09/1.18, dng720 1.09/1.18/1.26, volley 1.03/1.10/1.39 -> worse |
| E1 | A0 single past (tab_f0) vs A1 fused w=8 (tab_f1), 5-clip exact tables | A0: dng720 89.00 (88.09) 34.46/36.13/37.22; dng1080 90.35 (88.68) 35.09/34.73/35.98; floor 95.40 (91.55) 40.42/45.04/44.60; spot 94.54 (90.86) 40.00/42.58/46.44; hwy 93.18 (89.97) 40.88/47.82/44.15; volley 91.38 (90.29) 39.69/42.78/45.44. A1: dng720 88.96 (88.02) 34.45/36.13/37.22; dng1080 90.34 (88.61) 35.10/34.75/35.99; floor 95.48 (91.52) 40.67/45.21/44.76; spot 94.75 (90.86) 40.50/42.89/46.74; hwy 93.05 (89.98) 41.08/48.00/44.31; volley 91.33 (90.30) 39.71/42.80/45.46. CBR: A0 dng720 5 prefix overs (<= 3.3 bits), spot A0 1, A1 3 |
| A2 | Wiener fusion wk=1, luma only (tab_f2, 5 clips) | hwy 93.04 (89.88) 41.05/47.86/44.19; spot 94.68 (90.84) 40.45/42.63/46.47 |
| FV | FUSION VERDICT | +0.21 spot, +0.08 floor, -0.13 hwy, -0.05 volley, ~0 dng: FALSIFIED as a NEG lever (coordinator: drop; frees t-2 memory). Chained-V2 arm f3 was killed before eval. |
| AW | never-away, TPP legal vs PRE-LEGAL synthesis (away19.py, tab_eb_r2) | dng720 @0.5 luma 989 away (0.027 %), max 82, 0.27 % of plane SE; @1.0 51 (max 38); gfx @0.5 292 (max 120), @1.0 40 (max 35); chroma 0 natural; cut24 7.8-15.4 % (max 409); ext10 5.9-11.3 % (max 703) |
| L1 | R-FIX vs OFF, away counted vs CLIP of the legality-off decode (legal19.py, tab_f0, 3 frames) | OFF: dng720 @0.5 Y 799 away (0.029 %), 728 toward, chroma 0; gfx @0.5 Y 212/234, @1.0 24/26; cut24 @0.5 Y 10.5 % Cb 15.4 % Cr 14.8 %, @1.0 18.9/19.5/19.4 %; ext10 @0.5 Y 8.0 % Cr 12.2 %, @1.0 Y 9.8 % Cb 3.7 % Cr 32.9 %; OFF PSNR = clip arm within 0.04 dB. FIX: in-range index found for 22-89 % of clamp leaves, but away GROWS (dng720 1057, gfx 294, cut24 19-38 %, ext10 28-76 %), PSNR drops (cut24 @1.0 Y 12.95 vs clip 19.88) and prefix overs appear (dng720 98, gfx 60). -> R-FIX DEAD (relabels the partner move, SA18 L4) |
| D3 | per-band error energy ours(A0)/today, d3_bands.py | dng720 luma LL .11 H5 .15 H4 .34 H3 .61 HL2 1.19 LH2 1.19 HH2 1.12 HL1 1.29 LH1 1.19 HH1 1.34, chroma coarse .12-.69 fine 1.00-1.16; floor luma coarse .03-.55 fine .96-1.19; hwy .06-.39 / .89-1.30; spot .00-.63 / .96-1.58 |
| BB | bits per band group (bits_bands.py, tab_f0, frames 2-4) | hwy: vectors 1.6 %, luma coarse 31 % L2 22 % L1 20 %, Cb 7.6/1.3/1.9 %, Cr 9.9/2.3/2.5 %; spot: 1.6 %, 26.9/21.8/22.7 %, Cb 9.5/3.5/3.3, Cr 6.6/1.4/2.1 |
| SD | per-slice plans (A0 JSON) | bits equal per frame sixth (by construction); plan index spread spot 175..215, floor 176..208 (~1.3 octave), middle slices coarser; padding ~0 on every motion/dng cell |
| TL | ladder tilt (tables of tilt 0.25 = MISMATCHED, screening only) | floor: tilt -0.25 94.02 (89.74), 0 95.28 (91.40), 0.25 95.40 (91.55), 0.5 94.53 (90.30), 0.75 94.01 (89.85); hwy: -0.25 90.79, 0 92.94, 0.25 93.18, 0.5 91.89, 0.75 91.62 -> 0.25 is the optimum of this family |

## 3. Owner / coordinator rulings this session (binding)
- Design from scratch; earlier designs = evidence/instruments; per-element provenance lines (DESIGN §A).
- NEG first (mean + worst), then PSNR Y/Cb/Cr; chroma never optional; static control + monotone sweep for any prediction lever.
- Per-slice rate split REJECTED (starves easy slices, flattening). Per-block t-1/t-2 choice REJECTED unless proven (dropped).
  Fusion must prove compute/DDR/latency (done: DESIGN "Answer to owner: t-2 concerns"), then dropped as weak.
- Lever 1 (coarse->fine rebalance) was GO with smudge/cast gates; lever 2 (current-frame vectors) needed exact-CBR proof + latency
  arithmetic; lever 3 (cross-frame contexts) low priority. ALL SUSPENDED by the legality directive.
- Legality directive (above) and 10-generation exactness bar.

## 4. Rejected / falsified (with reason)
- Per-slice rate split (owner). Per-block t-1/t-2 choice (owner; continuous weight covers it). Two-past fusion (FV: <= +0.21).
- Rail-at-infinity companding (g^-1 many-to-one / saturation = clip; REXT relative). Private finest samples under averaging
  (critical sampling). R-FIX encoder in-range index choice (L1: more away, PSNR loss, overs). Tilt != 0.25 (TL).

## 5. Next steps
1. Read clipread logs -> DESIGN §L2 route table (R-FIX dead, R-CLIP result, R-CASCADE). Decide with partners.
2. For the chosen legality core: 10-generation chains (same rate, different rates, baseband) on rails/gfx/dng/motion cells,
   8/10/12-bit full range, 0.25-2.0 bpp, per plane; oob, away/toward vs clip arm, prefix overs, smudge/artifact/rowphase tools,
   renders, NEG/PSNR vs legality off.
3. Then efficiency (four goals): coarse->fine allocation (D3), current-frame vectors, contexts — with exact tables.
