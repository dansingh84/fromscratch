# SA18 RESUME (state file; updated after every finished item)

## State (2026-09-29, session 1)
- Read in full: BRIEF_SA18 (incl. §2b), PROJECT_CONSTRAINTS rev 6, MEMO_PRIOR_DESIGNERS, MEMO_SA15/16/17 findings,
  SA17 DESIGN + RESUME + partner notes. Ledger grepped: S5.29, S5.135, S5.137, S5.152 (today's motion = history
  vectors, transmitted; per-band intra/inter mode in today's codec; reference noise 60-72 % in LH1+HL1).
- Bench: `bench/` = copy of SA17's numpy model (measuring instrument only; every design choice re-derived).
  Reproduced SA17 exactly: dng720 @0.5 NEG 88.97 (88.10), volley @0.5 91.17 (90.08).
- Partner SA18P: id a46b6a2706e5ef93f; record in ../SA18P_partner/PARTNER_NOTES.md.

## Items
| # | item | status | numbers |
|---|---|---|---|
| R0 | reproduce SA17 rows | done | dng720@0.5 88.97 (88.10) 34.43/36.12/37.22; volley@0.5 91.17 (90.08) 39.57/42.67/45.29 = SA17 |
| D1 | chroma row signature, zero-detail synthesis (owner statistic, row mod 4) | done | kill LH1/HH1: 0.3-1.1 %; kill LH2/HH2 too: 3.4-4.5 % (rows 0,3 low); + HL1/HL2: Cb/Cr 10-12 %. Predictor tuning (108 dyadic 2/4-tap pairs, vertical-only model) best 24 -> 16 %: structural to 2 nested dyadic vertical levels |
| D2 | never-away kill test: share of away cases fixable by ONE +-1 coarse re-choice (best of 18 options, oracle) | done | cut24 0.1 % (682 cases), ext10 0.0 % (1876), dng720 32.7 % (150 sampled), cf_gfx 56 % (34) -> two-choice rounding DEAD |
| D4 | fast-motion: per-(plane,band,slice) prediction weight oracle {1,0} and {1,1/2,0} | done | {1,0}: floor 95.46 (+0.14), hwy 93.13 (+0.17), volley 91.18 (+0.01); {1,1/2,0} volley 91.14 -> not the lever |
| D1a | chroma 1 vertical level (real code lengths, SA17 tables) | done, REJECTED | zero-detail stress <= 1.8 %; dng720@0.5 86.53 (-2.4 NEG, luma -1.27 dB), volley@0.5 89.79 (-1.4) |
| D4b | static tables vs frame's own empirical class entropy (same contexts) | done | volley@0.5 hold 2.02x (class symbols ~85 % of bits), volley no-hold 1.26x, dng720 hold 1.47x, traffic (train, in-sample) 1.18x. ROOT: SA17 trained tables WITHOUT hold, measured WITH it |
| T1 | retrain tables with hold on (2 rounds, 5 train clips) | running (out/train_h.log -> out/tab_h_r2.pkl) | |
| COURSE | coordinator/owner: write 2-3 genuinely different architectures first (DESIGN §A); owner: A.0 dichotomy is not an answer, widen the search | done: §A.0-A.5 (~15 families) | |
| D6 | split of AVG away moves by overshooting partner's source (rail vs not) | done | dng720 388/36/2 @0.5/1/2 all case 3; gfx 71/7/2 all case 3; cut24 ~50/50; ext10 >95 % rail-source |
| DOL | partner's Laplacian 'decoupled output layer': gen-2 coarse re-read | done, KILLED | mismatch 11-40 % dng720, 5-36 % hwy |
| IPL | interpolating predict-only pyramid (per-sample clip): real intra A/B (tables trained identically) + inter proxy | done, KILLED | dng720@0.5 intra NEG 65.45 vs AVG 80.55 (-15), PSNR -2.1 dB all planes; inter proxy volley/hwy ~-2.7 dB |
| D7 | oracle source-searched vectors (volley, hwy @0.5; NOT gen-exact as run) | done | hwy 94.15 (90.90) 41.52/48.07/44.38 vs history 92.96 (+1.19; today 93.73); volley 91.67 (90.57) 39.90/42.85/45.57 vs 91.17 (+0.50; today 92.37) -> vectors are a major lever on hwy |
| T1 | hold-trained sequence tables round 1 (out/tab_h_r1.pkl) + eval @0.5 | done (round 2 running) | NO gain: dng720 88.93, volley 91.21, hwy 93.00, floor 95.35 (vs SA17 88.97/91.17/92.96/95.32). Table/own-entropy ratio volley still 1.87x -> the gap is content/slice non-stationarity, not train/test hold mismatch |
| D8 | why history vectors lose: MC prediction PSNR under hist / src / stale(S(t-1) vs S(t-2)) / lowpass-hist / projected | done | staleness, not coding noise: hwy Y 34.46 hist, 34.55 stale, 35.52 src; floor 34.02/34.25/35.26; volley 35.66/35.77/36.08 (94 % zero vectors); forward projection 0 gain |
| D9 | gen-2 re-derivation of source-searched vectors (search P1 vs D(t-1)) | done | equal blocks 98.5 % hwy / 99.9 % volley but predictions differ on 11.5 % / 0.85 % of blocks (OBMC spreads) -> not exact without a canonical vector reading |
| D10 | staggered level-2 vertical pairing (partner F1) zero-detail stress | done, REJECTED | vertical kills: rows 4.2->0.9 % but columns 0.9->5.3 %; with horizontal kills rows 4->40 % |
| D11 | per-(band,slice) table selection from a static variant bank (8 skew variants p*2^(-l*c), index sent) | done | class bits incl. side bits: volley -26.0 %, dng720 -5.4 %, hwy -4.7 % (real code lengths, emitted indices) |
| D12 | per-slice parametric correction (offset/scale) of the history field, oracle choice | done | recovers ~40 %: hwy pred Y 34.42 -> 34.84 (src 35.54), floor 33.96 -> 34.25 (35.14) |
| D13 | coarse-first vectors (partner idea): search on CURRENT decoded LL1(t); ccv2r = best of {hist+d, ccv2+d} by LL1 match | done | pred PSNR Y hwy 35.83 (src 35.54, hist 34.42), floor 35.31 (35.14/33.96), volley 35.98; cheap block-shift scoring (blk18) = same (35.74/35.23) -> ADOPTED (exact by construction) |
| B1 | bench: ccv (level-1 bands with V_c, one level-1 exponent re-choice d in [-4,8]) + bank (SA18_BANK) implemented | done | smoke dng720: 0 over, d mostly 0/+1 |
| E2 | eval @0.5 (tab_h_r1): bank / ccv(LL1 stage) / both | done | bank: volley 91.40, hwy 93.17, floor 95.42, dng720 88.81 (-0.12!); ccv: volley 91.33, hwy 93.32*, floor 95.59, dng720 89.01; both: volley 91.40*, hwy 93.44*, floor 95.62, dng720 88.63 (* CBR overs from a since-fixed accounting bug) |
| E3 | still areas: no-hold ceiling and events (hold lifted at frames 3,5,9), bank | done | volley no-hold 93.50 (42.14/44.10/46.79), events 92.96 (41.49/43.72/46.43) vs hold1 91.40, today 92.37; dng720 events 91.55 (35.90/36.40/37.52) vs 88.81, today 90.16. Frozen: event frames change 70 % of still samples, mean |chg| 6.2/5.7/6.9 codes, 56/44 toward/away; 0 elsewhere |
| D14 | vectors scored on quarter-res LL2(t), candidates V_h + d (|d|<=2) | done | hwy pred Y 35.51 (LL1-stage 35.74, hist 34.42), floor 34.91 (35.23/33.96) -> ADOPTED as the coarse-first stage for levels 1-2 (cfv2) |
| B2 | fine bands own plan index kf (not offset d) + canonical reading read2 + gen-2 read path | done | chain dng720 @0.5 5 frames: gen2/gen3 pictures AND bits identical, 0 prefix overs (offset-d version: reading +0.5 % bits, 150+ overs -> replaced) |
| E5 | @0.5: C1 = cfv2+bank+hold1, C2 = +still-age events 2:4:8 | done | C1: hwy 93.84 (90.07) 41.46/47.89/44.27, volley 91.72 (90.43) 40.09/43.09/45.75, dng720 89.35 (88.10) 34.80/36.23/37.31; C2: hwy 93.96, volley 92.97, dng720 91.77, floor 95.68. Today: 93.73/92.37/90.16/95.98 |
| OWNER | coordinator/owner: no scheduled or still-age events (refresh-pulse class); update only when something changed | adopted | C2 withdrawn |
| E7 | C3 error-driven hold (absolute threshold t_pix/sqrt(G_b), noise gate k 1.5), t=2 and 4 | done, REJECTED (flicker) | frozen: 62/55/38/33/47/48/51/52/45/40 % of still Y samples change f2..f11, mean 6.5->3.4 codes, per-sample count mostly 4-5+; t=2 and 4 identical (threshold never binds @0.5); dng720 NEG 89.11 (worst 85.86) vs C1 89.35 |
| DEC | still rule = hold1 (C1). Static-camera efficiency gap stated plainly (frontier: exact CBR per frame + one reference => <= one frame of bits per visible change) | decided | |
| T2 | tables retrained under the final configuration (cfv2 + bank + hold1), 1 round -> out/tab_f1.pkl | done (82 tables) | |
| E8 | texture reconstruction offset on fine bands (nonzero index at (|q| + 2^-ro) step), hold1 | done | ro2: dng720 89.59 (88.28), volley 91.86 (90.61); ro3: 89.52 / 91.83 vs C1 89.35 / 91.72 -> ADOPT ro=2; chain exact (ro3 tested) |
| E9 | tilt on training clip city @0.5 (cfv2+bank) | done | 0.25: 93.95, 0.5: 93.62, 0.75: 93.50 -> keep 0.25 (perceptual tilt toward fine bands beyond 0.25 loses) |
| E10 | bank ablation with cfv2+hold1 | done | no bank: hwy 93.77, volley 91.61 vs bank 93.84 / 91.72 (+0.07/+0.11) |
| SESSION | session limit 17:50-19:10; all queued jobs had finished with exit 0 | resumed 19:15 | |
| BANK | table bank dropped from the design: +0.07/+0.11 NEG only (E10), 8K memory/build rate infeasible | decided | |
| F | FINAL 12-point eval: cfv2 + hold1 + ro2 + tab_f1, NO bank (out/final_*.log; run_final.sh) | running | |
| POST | queued after F (out/run_post.sh): tilt 0 city, chain dng720/spot, heal dng720 RT2 / volley 8 slices, one-way c2, still frozen/mixed, owner tools on finals (art18.sh) | queued | |
| DOC | DESIGN.md §A, §B.1-B.8, §4, §6, §7 written; §3, §5, §8 await F/POST numbers | in progress | |
| D5 | context screen: +still flag (transmitted vector 0), +parent class, zero groups of 4 (in-stream only) | running (out/d5_*.log) | |
| D3 | still-hold cost decomposition | todo | |

## Rejected ideas (with reasons)
- Scheduled / still-age refinement events (C2): owner ruling (refresh-pulse class); frozen: 70 % of still samples change at each event, ~6 codes, not decaying.
- Error-driven absolute-threshold hold (C3): continuous decaying changes every frame (ants class); C4 (current-plan octave rule) = SA17 hold2 (18-71 %/frame).
- IPL predict-only structure: -15 NEG intra real, -2.7 dB inter proxy.
- DOL (Laplacian pyramid output layer): gen-2 coarse re-read mismatch 5-40 %.
- Rail-conditional structure: m<->switch fixed point. L9 lattice-preserving legaliser: moves ancestors unsigned. F3 rail-excluded structure: fixes plates only (D6).
- Two-choice (floor/ceil) coarse re-choice for never-away: oracle over 18 re-choices fixes 0-56 % (D2).
- Chroma single vertical level: -1.4..-2.4 NEG (D1a).
- Per-band intra/inter mode or prediction shrink: +0.01..+0.17 NEG oracle (D4).
- Contexts from the reference picture (partner): parsing would depend on history -> loss/join break (S5.29 class).
- 3a vertical predictor tuning for phase-uniform zero-detail synthesis: 24 -> 16 % at best (D1), not a root fix.

## Running jobs
- out/run_final.sh (12 evals), out/run_post.sh (waits for final_done), rail18.py (rails, final config).

## OPEN goal items (coordinator 2026-09-29: never-away stays OPEN, not closed)
- NEVER AWAY (goal 2), OPEN. Frontier rests on two premises, each a design choice to challenge after efficiency:
  P1 "gen 2 re-reads everything the synthesis reads"; P2 "averaging is needed for efficiency" (measured only vs IPL).
  Unexplored ways around P1: (a) a representation where the synthesis reads values gen 2 gets from somewhere other
  than the picture analysis (e.g. the reference frame, which gen 2 shares exactly, for inter frames); (b) readings
  that are many-to-one but canonical (gen 2 needs ANY representation reproducing P1 within budget).
  Unexplored ways around P2: (c) partially averaging structures (update step only where it matters for gain, e.g.
  coarse levels averaged, finest level per-sample with a different geometry); (d) adaptive predict-only with a
  better interpolator (edge-directed / longer support) -- IPL used a 4-point linear interpolator only; (e) non-dyadic
  or non-separable predict-only lattices (quincunx) whose coarse samples are less aliased; (f) averaging whose
  update reads only TRANSMITTED leaves (SA14-style) combined with a per-sample final clip, cost/exactness uncosted.

## Open problems / next
- D3, D4 results -> design decisions with partner.
