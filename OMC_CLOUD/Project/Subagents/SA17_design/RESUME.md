# SA17 RESUME (state file; updated after every finished item)

## State (2026-09-29, session 1)
- Read in full: BRIEF_SA17.md, PROJECT_CONSTRAINTS.md rev 6, MEMO_PRIOR_DESIGNERS.md (SA12-14),
  MEMO_SA15_FINDINGS.md, MEMO_SA16_FINDINGS.md. SA14 DESIGN.md sections 1.2-1.5, 2 (legality) read.
- Owner tools located: Subagents/shared_tools/{rowphase.py, smudgegroups.py, artifactmap.py, flatplane.py, negscore.sh}.
- Today's rowphase (owner tool, sh=16) dng720 @0.5: spread Y 11.9 % / Cb 57.8 % / Cr 52.4 %.

## Items
| # | item | status | numbers |
|---|---|---|---|
| E1 | vertical filter choice (intra, entropy PROXY + PSNR BD, gain-normalised; SCREENING ONLY -- to be confirmed with NEG at real code lengths) | done (PROXY) | V pair(2/6) vs V 5/3 (H 5/3 both): BD +2.0 % dng720, +2.5 % hwy, +6.3 % spot. Row-phase spread (sh=4) dng720 @~1.3 bpp: 5/3 2.3/15.4/14.6 %, pair 0.3/0.5/1.7 % (Y/Cb/Cr). Long L-clips have source chroma row-phase structure (4:2:0 origin) -> use dng for row tests |
| E1b (PROXY) | pair + update (both signs, causal), 2/10 predict, (9,7)-M horizontal | done | none helps: updates +-0.3 % or worse; 2/10 worse; 9,7-M +1.6..+2.3 % under this proxy |
| E1d (PROXY) | predict-only (no update) at level 1 / 1-2 / all | done | +12..29 % / +37..52 % / +48..60 % -> per-sample-leaf legality structures are dead (confirms S5.349) |
| E2 | plain clip + gen-2 nearest-lattice reading, continuous 5/3 | done | cf_gfx: 0 misses at every rate; cut24/ext10: 18..282 index mismatches, 820..24769 pixels differ -> clip+reading is NOT exact on rails |

| M1 | model built: model/pyr.py (pair pyramid + legality + canonical index), ent.py (tANS code lengths), codec.py (frame coder, rate control, reading, decoder), motion.py (history vectors, OBMC, barrier), seq.py (sequence), evalcell.py, metrics.py (NEG per frame, validated = owner negscore 88.858) | done | legality stress 0 oob; gen-2 reading: dng720 @0.5 5 frames pictures+bits+plans identical; decoder==encoder |
| T1 | intra tables trained (5 disjoint clips, 3 rounds): out/tab_intra_pair.pkl, tab_intra_53.pkl | done | |
| T2 | seq tables (intra+inter): out/tab_seq_pair.pkl DONE (2 rounds, 5 disjoint clips); tab_seq_53 RETRAINING (LL bug fixed; out/run53.sh) | pair done |  |
| P0 | first real eval, untuned, r0 tables: dng720 (evalcell, frames 2-11 vs today's real decodes) | done | @0.5 NEG 89.08 (worst 86.03) PSNR 35.18/36.04/37.17 vs today 90.16 (87.22) 35.22/36.10/37.14; @1.0 94.09 (92.56) 38.78/37.23/38.37 vs 94.05 (92.31) 38.19/37.08/37.95 |
| R1 | row phase (owner rowphase.py) on P0 dng720@0.5 | done | sh=8 spread 1.3/3.6/4.2 % (today 9.8/53.0/50.8); sh=4 0.6/3.0/3.1 (outer vs inner rows of a 4-row block, chroma); mean|err| by phase (S=8) spread 3.9/1.5/1.8 % (today 33.9/16.4/13.4) |
| TU1 | tuning on TRAINING clips (city, traffic): tilt +0.25 better (traffic +1.0 NEG @0.5), tilt -0.25 worse; rho 0.35 slightly better than 0.42; rho 0.5 worse | done | out/tune1.log |
| J1 | gen chain (g2,g3) + joiner + loss decoder, dng720 @0.5, 24 frames (join at f3, slice 40 lost at f4) | done out/join_v1.log | gen2 AND gen3 identical pictures+bits all 24 frames; loss repaired at f13 (9 frames; cycle 7); JOINER NEVER CONVERGES (1.3-1.6 M samples differ through f23; phase lock found at f4) -> FAIL, debugging |
| EV-A1 | 12 points vs today, tables_seq_pair, tilt .25 rho .35 bx64 lam4 (out/eval_a1.log) | done | NEG diff: dng720 -0.41/+0.43, dng1080 -0.79/+0.77, spot -1.31/-0.02, floor -2.33/-0.70, hwy -2.04/-0.90, volley -1.32/-0.32 (@0.5/@1.0). 2 better, 10 worse; motion cells @0.5 lose 1.3-2.3. CBR prefix overs on 5 runs (defect) |
| L2 | legality away-moves on NATURAL content (out/away_nat.log) | done | dng720 @0.5: 3376 samples differ from clip arm, 1817 farther (p99 94, max 136 codes); gfx @0.5 544 of 965 farther |
| L3 | rail-conditional TVD limiter / continuous range-limited slope (away_rl, away_rg) | REJECTED | no reduction of away-moves; ext10 worse (102641 farther @2.0) |
| TU2 | tuning batch 2 (train clips city/traffic/winter) | done | best: tilt .25 rho .35 bx64 lam4 (all 6 points >= others within 0.3); chroma offsets trade planes; rho_still 0.2 no gain |

| L1 | rail legality (intra frames, pair backend, out/rail_v1.log + analysis): cut24/ext10/ext10l1 at 0.25-2 bpp | done | 0 out-of-range; gen-2 differing samples 0 on every rail cell/rate. BUT vs the same pre-canonical leaves + plain clip: 30-75 % of samples changed by legality end FARTHER than clip (cut24 @1.0: 6191 of 16109; excess p50/p90/p99 8/68/147, max 258 codes; ext10 @2.0: 32445 of 43240, max 137). Overall Y MSE legal < clip (6833 vs 7167). Cause: mean-preserving pair clamp moves the partner; toward iff mean error <= 0 at the upper rail. |
| A1 | TVD slope limiter (to cut prediction-made overshoot) | REJECTED | intra real code lengths: NEG -1.3..-2.8 (dng720/spot/gfx), chroma PSNR down |

| J2 | joiner fixes: (a) readable unit = consistent at a plan with every band step>=2 (camera ku=0, decoded ku>=216 on dng720); forced slice plan = min ku over readable units (the coarse g1 reading; NOT capped at own plan, that broke gen2 by credit divergence); (b) clean-region rule added to VECTOR DERIVATION (clean blocks derive from barrier-replicated D(t-1),D(t-2); zero at cycle start). Per-unit plans tried and REJECTED (plan side info ~78 bits/slice, 1.5 %, pushed every slice over budget) | running out/join_v2*.log | gen2 exact restored (24 f) |
| EV-B | diagnostics: refresh cost (refresh=0) and transform price (5/3 backend, clip, NOT exact) on hwy/floor @0.5 | running out/eval_b.log | |

| EV-B | diagnostics hwy/floor @0.5 (out/eval_b.log) | done | refresh costs 0.98/0.77 NEG (no-refresh 92.67/94.42 vs 91.69/93.65); 5/3 backend (not legal/exact) 91.47/93.88 = pair within +-0.23 -> TRANSFORM PRICE ~0 at real code lengths (E1 proxy +2..6 % did not materialise) |
| ENT1 | static tables vs per-band empirical class entropy (traffic @0.5, training clip) | done | class bits +47.8 % over empirical (812 k vs 550 k per frame) -> tables pooled over all steps are the big loss; now keyed by step bucket (3), retraining out/tab_seq_pair_eb.pkl (train_seq_pair_eb.log, 3 rounds) |
| TU3 | refresh cycle on train clips (traffic @0.5) | done | cycle 8 84.11, 12 84.90, 16 85.60 NEG |
| V1 | clean-region rule for vector derivation, v1 (barrier-replicated matching) cost ~1.4 NEG on traffic; v2 = spatial extension of the nearest fully-clean block vector | v2 testing (tune4.log, join_v3*.log) | |

| OWN1 | OWNER CORRECTION (coordinator 2026-09-29 ~11:00): loss recovery < 4 frames; PRIMARY = on-demand refresh over a return path (per-slice loss flags, refreshed rows intra inside the fixed CBR budget, capped per frame); rolling wave = fallback for one-way links only, as slow as A5 allows. Efficiency to be reported with NO wave; wave cost + one-way bound separately | adopted | |
| H1 | on-demand heal model (heal.py): slice k lost at t, flag after RT frames, rows [kS-m,(k+1)S+m] intra at t+RT+1, m = 16 + 8(RT+1), no wave | done out/heal_*.log | dng720 @0.5 RT=1: damaged frames t, t+1, exact at t+2; RT=2: exact at t+3 (damage 30k->37k->44k samples, rows 302..345); spot RT=2 exact at t+3. Visible frames = RT+1 < 4 for RT<=2. CBR held (bits/target <= 1.0000, over 0) |

| ST1 | still areas, no wave, no hold (still_frozen.log, still_mixed.log; dng1080 bg frozen / + floorball PiP) @0.5 | done | FAIL: 20-78 % of still samples change EVERY frame (frames 2-10), ~55/45 toward/away, not converging. Root: exact CBR spends the whole budget; with nothing else to code the plan gets finer and every frame re-refines still content |
| ST2 | fix at that root (encoder-only): a zero-vector coefficient gets ONE refinement after it becomes still/intra, then is held unless the source changes by > 3/4 of that step; unspent bits = padding | done | frozen dng1080: 11/6/1 % changes frames 2-4 then 0; mixed: 0.1-1.2 %/frame persisting (50/50). Second root: history vectors read refinement as motion (71 nonzero V on frozen dng720) |
| ST3 | zero-vector tolerance in derivation (ZTOL 2 codes/pixel) | done | frozen dng720: frame 1 (ramp) changes, frames 2,3: 0/0/0 samples. Mixed rerun pending |
| H2 | heal, second cells + larger loss (RT=2): volley @0.5 8 slices lost (64 rows), dng1080 @1.0 4 slices lost | done | both exact at t+3 (damaged f3,f4,f5 = 3 frames < 4); damage 173-175k / 137-172k samples; CBR held |
| OWN2 | owner: one-way links = SHORT cycles (2,3,4) or all-intra, accept quality cost; drop long-wave-only machinery; report NEG/PSNR + bound for c=1,2,3,4,8 | planned after tables | |
| TR-EB | step-bucket tables, no wave, 2 rounds parallel (tab_eb_r2.pkl, 79 keys) | done | |
| EV-C | MAIN efficiency: 12 points, no wave (on-demand), still_hold, ZTOL 2, tab_eb_r2 (eval_c.log) | done | NEG diff vs today @0.5/@1.0: dng720 -1.18/+0.20, dng1080 -0.80/+0.53, spot +0.64/+0.19, floor -0.68/-0.45, hwy -0.78/-0.77, volley -1.19/-0.41 -> 4 better, 8 worse. Worst frame better on dng720@0.5/@1.0, dng1080 both, spot@0.5. CBR prefix overs 7/1/2/1 on 4 runs (emission > chosen by fractions; defect) |
| EV-W | one-way fallback wave, cycle c=1(all-intra),2,3,4,8 @0.5 (eval_wave.log) | done | dng720 NEG 80.94/87.41/89.22/89.59/90.23 (worst 79.26/85.32/87.10/85.80/87.77); hwy 87.88/89.82/91.07/91.40/92.14 (worst 85.15/87.59/88.36/88.25/88.90). Recovery bound one-way <= 2c frames (c=1: 1 frame) |
| ST4 | mixed clip, hold+ZTOL2, eb tables (margin 24 rows/64 cols) | done | Y 0.05-0.29 %, Cb/Cr 0.6-1.1 % of still samples change per frame, 50/50 -> suspect transform halo of the moving PiP; wide-margin rerun (40/160) running |
| CBR | emission excess over chosen cost: 1 slice of 180, +5.5 bits (dng720) -> fixed 16-bit per-slice reserve, carried in the credit | added (not yet in any measured table) | |
| TU5/6 | still-hold cost on train clips @0.5 (NEG): no hold city 95.55 / traffic 88.68 / winter 93.26; hold1 (one refinement) 93.85/88.37/93.25; hold2 (octave refinements) 95.47/88.58/93.30 BUT hold2 flickers (frozen: 18-71 % changes every frame through f11) -> hold1 KEPT; its cost 0-1.7 NEG on static content is the price of no flicker | done | |
| ST5 | mixed clip, wide margin 40 rows/160 cols (still_mixed_h3_wide.log) | done | Y 0.000 %, Cb/Cr <= 0.011 % per frame -> the 0.6-1 % at 24/64 margin is the moving object's transform/OBMC halo (<= 160 px) |
| LV1 | 1 vertical pair level (row-symmetric by construction) | REJECTED | intra dng720 frame 0 @0.5 Y 29.69 vs 31.5 dB (-1.8 dB) |
| ART | owner tools on all 24 decodes (art/summary.log) | done | smudgegroups Cb/Cr 0 everywhere (Y line to re-extract); artifactmap Y regions mine vs today @0.5: dng720 23+6 vs 6+4, dng1080 22+20 vs 4+5, spot 3+2 vs 0+1, volley 6+6 vs 0; chroma 0 (spot Cb 1 dark); @1.0 all 0. Flat Y lower than today on motion cells, higher on dng; rowphase (owner, sh=S) dng Y 0.5-1.2 %, Cb/Cr 2.5-7.1 % (today 3-13 / 18-39) |
| EV-F | FINAL 12 points with 16-bit reserve (eval_final.log) | done | same as EV-C within 0.03 NEG; 0 prefix overs on all 12; smudgegroups Y 0 on all 12 |
| DOC | DESIGN.md rewritten complete (sections 0-12) | done | |
| OW1 | one-way loss: c=2 damaged 2-3 frames (<4); c=3 4 frames (fails) -> one-way mode = cycle 2 | done | oneway_c*.log |
| OW | 12-point cycle-2 eval: done (DESIGN §6.2 table), costs 1.0-3.4 NEG vs on-demand | done |
| CH | final-config gen chain: dng720 14 f, spot 7 f identical pics+bits gen2/gen3 | done |
| P1 | partner levers (tune7): ry8 ~0, ztol0/1 +0.05..0.13 (ztol0 flickers), l1k 0.5 -0.85/-0.02 -> none adopted | done |

## Rejected ideas (with reasons)
- Continuous 5/3 vertical: 5-15 % row-phase signature in chroma (E1) = design-created special row class.
- Plain output clip + reading (any update-lifting transform): gen-2 misses on rails (E2); info lost by clip is read by the update.
- Predict-only / per-sample-leaf structures (would make clip exact): +12..60 % bits (E1d).
- Pair lowpass updates: no gain (E1b).
- Cell-bounded clamp in 5/3 (reconstruct in cell ∩ window, update reads index): exact only if no 'miss'; misses unbounded near rails with open-loop leaves; closed-loop impossible because the update couples the leaf to its own predictor. (paper)

## Running jobs
- tune7.sh remainder (ftrain/hview clips, l1k 1 and 2) -> out/tune7.log; informational only.
- NOTE: never use pgrep -f / pkill -f with a pattern that appears in the same command line.

## Open problems
- Goal 4: -0.4..-1.2 NEG on 8/12 (text/detail at 0.5 bpp). - Never away (structural, sec 3.2). - 2-level chroma row signature 2.5-7 %. - Encoder join on two-way mode. - CBR reserve unproven. - Formats other than 4:2:2 10-bit not run.

## Next steps

## Coordinator note 2026-09-29
- Proxy results are screening only. Decisive choices (pair vs 5/3 transform price, allocation) must be confirmed with VMAF-NEG mean+worst frame, then PSNR Y/Cb/Cr, at REAL code lengths before being final. Planned: item C1 once the tANS coder exists.
