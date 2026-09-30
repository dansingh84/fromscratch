# SA20 DESIGN (cloud session 2026-09-30) — written incrementally (tags: MEASURED / PROXY / PAPER)

## §0 Task and footage limits
- Task (CLOUD_README §1.3, HANDOFF §10.2): (1) adversarially verify the SA19 never-away verdict (ledger S5.404,
  SA19 DESIGN §L3); (2) if it holds, find an engine where never-away holds by construction at zero efficiency cost,
  meeting all four goals, legality first.
- Footage for this session is NOT the project footage (RESUME §2): 6 clips, 2-3 frames each, from lossy RGB PNGs.
  Consequences: steady state = frame 2 only; no long motion cells; the content is soft (today's codec reaches
  46-56 dB PSNR at 0.5 bpp), so NEG saturates near 94-97 at 0.5/1.0 bpp -> 0.25 and 0.125 bpp added to separate
  designs. The bundled rail extremes (cut24, ext*) are the project's own and are used unchanged.

## §1 Instruments (MEASURED)
- R0 bench reproduction: SA19 legal19.py (copy in instr19/, unmodified) on cut24 @0.5, tab_f0, 3 frames:
  legality-off Y away 5,185 (10.5489 %), Cb 3,774 (15.3564 %), Cr 3,644 (14.8275 %) = SA19's log exactly.
- eval20.py: VMAF-NEG per frame over ALL frames (frame 2 keeps its motion feature), PSNR Y/Cb/Cr per frame;
  steady = frames 2..N-1.
- Today (v537 real encode/decode on the new clips), frame 2 NEG, PSNR Y/Cb/Cr (out/today_eval.txt):
  cine_A005C031 720p @0.5 94.20, 46.38/53.29/51.86; @1.0 96.11. 1080p @0.5 95.68, 49.03/54.31/52.58; @1.0 97.09.
  gfx444_B001C001 720p @0.5 95.27, 52.02/53.65/55.66; @1.0 96.50. 1080p @0.5 96.07; @1.0 96.76.
  prores_sample 720p @0.5 93.40, 47.07/54.14/52.66; @1.0 95.38. 1080p @0.5 94.40; @1.0 95.90.

## §V Adversarial verification of the S5.404 never-away verdict (in progress with SA20P/SA20Q)
Own check of SA19 §L3 (PAPER):
- Steps (1)-(4) are correct for every legaliser that keeps the re-read pair sum: with a+b = 2m fixed and a
  overshooting by ov, any legal a gives b >= b0 + ov; b stays on its source's side iff e_m <= 0 (top rail).
  The metric (away iff |out - src| > |clip(yu) - src|) is the right strict reading: for the partner b the
  pre-legal value and the clip value coincide (b0 was legal), so no relabelling hides a move.
- Step (5) (sibling conflict) is argued and backed by SA18 D2 (best single +-1 coarse re-choice fixes 0.1-56 %).
- The R-CLIP measurement tested a SUFFICIENT condition (gen 2 recovers the original indices V0). The necessary
  condition with canonical emission is weaker: gen 1 may emit any description whose clipped synthesis is its own
  output. It still fails: a clipped picture has off-lattice analysis coefficients, so its nearest-lattice
  reading synthesises a different picture (SA19 L4: blind re-encoders reach a fixed point only at gen 4-7).
- What the verdict does NOT cover (its premises P1-P3 are restrictions, not laws): (a) structures where the
  partner is not tied to the overshooting sample by a re-read sum, e.g. an update that reads TRANSMITTED leaves
  (SA14 NEST: the legaliser then touches only the overshooting sample; NEST's exactness came from IDQ, which moved
  samples away; a plain clip there breaks exactness because the clipped leaf cannot be re-read); (b) averages
  carried by state both ends share (the reference on inter frames); (c) overcomplete layers with an exact re-read.
  These are the open routes; the averaging pyramid with a re-read pair mean is closed.

## §E Escape routes of the never-away dichotomy (SA20P/SA20Q: an averaged coarse band survives a per-sample clip
## only if (1) the average is taken of state both ends share, or (2) redundancy gives the re-read slack)
- E1 D1 "slack-read Laplacian" (SA20Q; route 2): coarse ĉ = Δc·k at quarter resolution, k coded LOSSLESSLY by an
  integer 5/3 (bijective re-read), out = clip(up(ĉ) + Δr·q) per sample. PROXY screen (bench/d1_screen.py; intra
  frame 0, 720p, zeroth-order entropy + 1-bit context, read-slack steering IGNORED = optimistic), vs an integer 5/3
  transform coder at matched rate, dB Y/Cb/Cr @0.25/0.5/1.0:
  cine Δc/Δr = 4: -0.98/-6.43/-6.14, -4.27/-8.90/-8.18, -7.92/-10.96/-9.97; 2: -1.4..-11.4; 1.25: -0.7..-10.5;
  0.5: -1.02/-4.96/-4.74, -3.45/-6.64/-5.68, -2.37/-2.84/-1.73; 0.25 (not exact: needs steering): +1.07/+0.43/+0.71,
  -2.22/-2.05/-1.32, -3.30/-0.61/-0.13. gfx: every arm -0.2..-12.6 dB at 0.5 (best 0.25: -5.44/-2.03/-4.06).
  prores like cine. -> KILLED (SA20P's bit-floor argument confirmed: a lossless coarse layer cannot dead-zone).
- E2 D-P "update from the prediction" (SA20P; route 1) = predict-only coding of e = x - P, per-sample clip.
  PROXY screen (bench/dp_screen.py + dp_score.py): 3 frames, f0 intra (P = 0), f1-2 inter, same 16x16 block motion
  for both arms, D-P given the best of three level ladders; frame-2 NEG and PSNR, D-P minus averaging 5/3:
  cine @0.25 -4.01 NEG (-2.81/-3.04/-3.07), @0.5 -0.98 (-1.81/-1.46/-1.90), @1.0 -0.24 (-1.52/-0.84/-1.19);
  gfx -1.62 (-2.90/-2.12/-1.69), -0.30 (-1.32/-1.33/-0.85), +0.15 (-0.46/-0.39/+0.04);
  prores -3.74 (-2.91/-3.26/-3.25), -0.94 (-1.84/-1.26/-1.68), +0.05 (-1.01/-0.88/-1.26).
  Pre-agreed kill (> 0.1 NEG below AVG) -> DEAD at 0.25/0.5. Unmeasurable here: poor-P regions, heal quality.
- Today (v537 real) frame-2 NEG, PSNR Y/Cb/Cr @0.3: cine 90.70, 44.15/51.81/50.55; gfx 93.24; prores 90.65
  (0.3 bpp is today's encoder floor at 720p).
- E3 DPI DIAGNOSTIC (not a design: averaging intra frame 0 at 1.6Q + predict-only inter frames 1-2), frame-2 NEG,
  PSNR Y/Cb/Cr minus AVG: cine @0.25 -2.04 (-1.30/-1.79/-1.58), @0.5 -0.57 (-0.47/-1.08/-1.09), @1.0 +0.23
  (+0.20/-0.74/-0.62); gfx -0.44, -0.15 (+0.05/-0.50/-0.31), +0.22 (+0.31/+0.20/+0.46); prores -1.64,
  -0.54 (-0.51/-0.81/-0.94), +0.26 (+0.48/-0.50/-0.40). About half of D-P's 0.5-bpp deficit is intra.

## §F From-scratch round (owner directive 2026-09-30)
Group result (SA20P, accepted by SA20 and SA20Q): with never-away judged against the clip of the legality-blind
decode, a decoder must equal clip(unconstrained decode) sample by sample, so the value a clip removes must be
needed by nothing else: (i) every sample's last write private, (ii) slack for the re-read, or (iii) averages of
state both ends share. Measured so far: (ii) D1 dead, (iii) D-P dead as an all-frame engine, (i) inter price
moderate (E3), intra price large (IPL -15 NEG real; D-P f0). Open question = intra and chroma efficiency inside (i).
- F1 Definition we measure against (SA20Q, accepted by all): "moved away" is judged against the clip of a synthesis
  that never references lo/hi. Against a rail-aware synthesis (the leaf clamp #9 itself is one) any geometry
  "passes" by relabelling. Only a clip-invariant coarse functional survives that definition: the order-statistic
  class (L3). The owner is asked to CONFIRM this definition, not to change it.
- F2 L3 "inner member" pair pyramid (SA20Q), PROXY intra f0, dB Y/Cb/Cr vs int 5/3: cine @0.25 -2.42/-3.33/-4.45,
  @0.5 -5.71/-5.81/-6.48, @1.0 -9.36/-7.87/-8.27; gfx -12.1..-18.2; mean cast up to +-2 codes (G6). DEAD.
- F3 N4 (SA20; form i): private interpolating pyramid, decoder unchanged; the ENCODER aims prediction-source samples
  at a low-passed target where their detail would die anyway (T = pull strength). PROXY intra f0, dB vs int 5/3:
  cine @0.25 PO -3.87/-7.74/-7.59 -> N4 T1 -1.43/-2.06/-1.86; @0.5 PO -1.76/-0.45/-0.71 -> T1 -1.62/-0.27/-0.38;
  @1.0 PO -0.90/-0.06/-0.23, T1 -0.94/-0.43/-0.40; T=inf worst everywhere (-4.2..-5.7 Y at 0.5/1.0).
  gfx @0.5 PO -1.34/-0.69/-0.16, T1 -2.20/-0.78/-0.17; @1.0 PO -0.51/-0.58/-0.40, T1 -0.25/-0.26/+0.10.
  -> helps only at 0.25 on cine; the aliasing-free bound (T=inf) does not rescue form-(i) intra. NKV (SA20Q) is a
  subset of N4's freedom (withdrawn).

## §G Real code lengths (static tables trained on the 3 disjoint training clips under the exact arm/Q/config;
## ideal static code ≈ tANS; model has no headers/rate control), intra frame 0, vs TODAY's frame 0 (v537 real,
## pure intra at exactly the stream rate). Rates 0.5-4.0 only.
- G1 cine 720p, ours - today, NEG then PSNR Y/Cb/Cr (bench/rcl_intra.py + intra_vs_today.py):
  PO (form-i private-leaf pyramid, DD4, f 0.7): @0.5 +0.90, +1.55/-0.81/-0.95; @1.0 +0.07, +2.11/-0.64/-0.59;
  @1.5 +0.17, +2.70/-0.26/-0.25; @2.0 +0.13, +2.47/-0.09/+0.13; @2.5 +0.11, +2.63/+0.01/+0.62; @3.0 +0.08,
  +2.66/+0.46/+1.15. N4 T1 (earlier run): ~88.7 NEG @0.5 (worse than PO) -> dropped.
  Integer 5/3 averaging reference (LL DPCM, rho 0.35): @0.5 +1.14, +2.52/+0.68/+0.48; @1.0..4.0 NEG -0.42..-0.57.
  -> Form-(i) intra >= today on NEG at every measured owner rate on cine; the failing item is chroma at 0.5-1.5.
- G2 all three clips, PO intra (real code lengths) minus today's frame 0, NEG then PSNR Y/Cb/Cr (out/rcl2/intra_vs_today.txt):
  cine: 0.5 +0.90 (+1.55/-0.81/-0.95), 1.0 +0.07 (+2.11/-0.64/-0.59), 1.5 +0.17 (+2.70/-0.26/-0.25),
        2.0 +0.13 (+2.47/-0.09/+0.13), 2.5 +0.11 (+2.63/+0.01/+0.62), 3.0 +0.08 (+2.66/+0.46/+1.15).
  gfx:  0.5 +1.12 (+2.60/+0.23/-0.07), 1.0 +0.15 (+0.88/+0.01/-0.48), 1.5 +0.04 (+0.32/+0.33/-0.38),
        2.0 +0.02 (+0.40/+0.72/-0.01), 2.5 -0.01 (-0.14/+1.09/+0.25), 3.0 0.00 (-0.21/+1.52/+0.76), 4.0 0.00 (-0.29/+2.16/+1.67).
  prores: 0.5 +0.85 (+1.57/-0.88/-0.98), 1.0 +0.18 (+2.22/-0.67/-0.77), 1.5 +0.18 (+2.73/-0.40/-0.34),
        2.0 +0.16 (+2.60/-0.20/+0.08), 2.5 +0.14 (+2.72/-0.10/+0.61), 3.0 +0.11 (+2.75/+0.39/+1.03), 4.0 +0.13 (+2.18/+1.23/+2.18).
  -> NEG parity or better at every owner rate on all 3 clips (gfx 2.5-4.0 exactly at parity); failing items:
     chroma on cine/prores 0.5-2.0, gfx Cr 1.0-1.5, gfx luma 2.5-4.0 (-0.14..-0.29 dB).
- G3 3-frame PROXY sweep (entropy), frame 2, DP = form (i) end to end, vs today's frame 2 (real):
  cine DP 94.18/96.22/97.10/97.39/97.69/97.84/98.01 vs today 94.20/96.11/97.05/97.41/97.64/97.72/97.92 at 0.5..4.0;
  PSNR @0.5 47.17/52.17/50.49 vs 46.38/53.29/51.86. (proxy vs real: indicative only; real-code 3-frame run queued.)
- G4 chroma allocation arms (pre-registered pass: ONE fixed chroma-step curve of the step, same for all clips, all planes
  AND NEG >= today after a 1 % header deduction, every rate 0.5-4.0, 3 clips). out/rcl_fi/intra_vs_today.txt.
  cm = chroma step multiplier; _cl = chroma-from-final-luma (alpha per 16x16 block, eighths).
  At 1.0 bpp (ours - today, NEG; Cb/Cr): cine cm1 +0.07; -0.64/-0.59 | cm0.7 -0.21; +0.33/+0.36
                                         gfx  cm1 +0.15; +0.01/-0.48 | cm0.7 -0.14; +0.73/+0.07
                                         prores cm1 +0.18; -0.67/-0.77 | cm0.7 -0.13; +0.27/+0.16
  Interpolated to the cm where the worse chroma plane reaches today: NEG -0.12 cine, -0.10 gfx, -0.08 prores, before
  the header charge. 1.5 bpp behaves the same way (cine cm0.7 -0.09 NEG, cm1 Cb -0.26). 0.5 passes with cm0.7
  (cine +0.35, Cr +0.04); 2.0-4.0 pass or are within reach of a curve rising above 1 (gfx 4.0 chroma +2.2/+1.7
  funds luma -0.29).
  -> VERDICT: allocation alone FAILS the pre-registered rule at 1.0-1.5 on all 3 clips. The intra coder sits on a
     luma/chroma frontier ~0.1 NEG below today's point there; it needs ~3-5 % more coding efficiency, which no
     allocation curve supplies. Chroma-from-luma (_cl): +/-0.02 NEG, +/-0.1 dB chroma = no effect -> KILLED.
  Next intra lever: entropy-model context from decoded data only (1-bit neighbour context -> neighbour bit x
  prediction-support activity normalised by the level step, activity read from this frame's final coarser samples).
- G5 context lever (C2) constraints and pre-registered pass (SA20P, accepted):
  - lanes use a source-derived activity ESTIMATE; the emitted cost must be covered by a fixed reserve, with 0 prefix overs;
  - contexts must be packet-local: taps clamped at the packet edge (changes bits only, never pixels);
  - the diagonal phase reads an earlier sub-pass only;
  - tables must fit today's 8K on-chip budget (state the Mbit total), else merge classes;
  - gen 2 identical.
  PASS: at 1.0 and 1.5, after the 1 % header charge, NEG >= today AND the worse chroma plane >= today (cm
  re-interpolated) on 3 clips; otherwise drop. The screen (rcl_ctx.py) does not clamp at packet edges yet: optimistic.
  Queued next (SA20P): luma-guided chroma INTERPOLATION (0 bits; DD4 weights steered by final co-located luma
  gradients, shift-add LUT). Kill if < +0.1 dB on the worse chroma plane at 1.0 on 2 of 3 clips; guard: cast/bleed level maps.
- G6 SA20Q flags (accepted):
  (1) rcl_cbr picks Q by coding the frame at several Q = trial coding, which the pack bans (§1.4). It is only an upper
      screen. The admissible rule chooses Q from the previous frame's EMITTED cost/Q (gen-2 reproducible), with at most
      one predetermined re-choice. rcl_cbr gets a "plan" variant under that rule, measuring overs and gen-2 bits.
  (2) Contexts reset at each slice top or stay packet-local; a loss test drops one slice and the next must parse.
  (3) Overfit: the test clips are already disjoint from the 3 training clips (held out by design). Table Mbit at 8K
      to be stated.
  (4) Recon identical with and without contexts (verified: same po output; the ctx arm only re-costs symbols).
  Falsifier: gain >= 3 % bits at 1.0 AND 1.5 on EACH test clip, AND after re-spending with cm such that chroma >= today,
  NEG >= today after the 1 % header charge on all 3 clips; else killed.
  Queued lever (SA20Q): conditional-mean reconstruction, delta(class of the final-neighbour gradient vs prediction),
  static LUT, |delta| <= step/8, continuous; guard texstat/flatplane/renders + static control.
- G7 luma-guided chroma interpolation (LG, SA20P; bench/n4_core.po LG=k): where the final co-located luma between the two
  inner DD4 taps differs by more than k x step, chroma is predicted a + w(b - a), w = target luma position in eighths
  (shift-add). Smoke (cine f0, Cb, Q16, intra): nonzero symbols 8657 -> 7196 (LG1), PSNR 53.44 -> 53.80. Real-code arms
  cm1_lg1, cm0.85_lg1, cm1_lg2 queued (out/rcl_fi/lg_vs_today.txt). Kill: < +0.1 dB worse chroma plane @1.0 on 2 of 3 clips.
- G8 engine rate-control rule (SA20Q flag, both agree): plan from the previous frame's emitted cost, one predetermined
  coarser re-choice, proof the coarsest plan fits, gen 1 emits the plan read from its own picture (joiner needs no
  history). rcl_cbr's multi-Q search is a screen (upper bound) only.
- G9 conditional-mean reconstruction (SA20Q; po RO/RS, LUT trained on the 3 training clips, class = level x min(|q|,4)
  x decoder-side activity class, |delta| <= step/8), intra luma cine frame 0, recon PSNR (bits unchanged except via the loop):
  Q8 53.662 -> 53.723 (+0.06), Q16 49.410 -> 49.412, Q32 45.449 -> 45.463. Per-|q| only: +0.004 / -0.05 dB.
  In-bin means sit at +0.0..+0.16 step, near the dead-zone bin midpoint (+0.15) in every class: the in-bin
  distribution is nearly flat, so no class split carries a usable offset. -> KILLED (< 0.1 dB at every step).
