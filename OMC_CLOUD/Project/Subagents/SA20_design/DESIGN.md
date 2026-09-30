# SA20 DESIGN — from-scratch engine for OMC (cloud session 2026-09-30)

This document is self-contained. It refers only to the project pack (PROJECT_CONSTRAINTS.md, the ledger
LEDGER_SANDBOX_v2.md with its S5.xxx sections, HANDOFF_2026-09-28.md, earlier designers' SAxx records) and to the
owner's footage. "The bench" means SA20's own measurement scripts, shipped with this document together with REPRODUCE.md (bench/, tools/, queues/, history/). Sections §0-§G below
are the running log in the order work happened; this front section is the current summary.

## Summary (kept current)
Goal (owner, priority one): an engine where never-away legality holds by construction, exact over >= 10
generations incl. CBR and baseband hops, free of seams/smudges/streaks, and at least as efficient as today's codec
(v537), legality first. Benchmark = v537 run on the same 3-frame clips at 0.5/1.0/1.5/2.0/2.5/3.0/4.0 bpp.

Engine ("form (i)", private last write): a predict-only interpolating pyramid (4-tap DD interpolator
(-1,9,9,-1)/16; two 2-D levels + three horizontal levels; the coarsest "kept" grid coded directly). Every sample is
written exactly once as clip(P + prediction + leaf), where P is the motion-compensated reference (0 in intra), the
prediction is interpolated from already-final coarser samples, and the leaf is the quantised residual. Consequences:
never-away holds per sample by construction (each correction moves that sample toward the source; 0 out-of-range
everywhere), and a zero leaf copies the prediction exactly (still areas can be held with no change).

Status (latest):
- Legality: 0 out-of-range on every clip; rail extremes (cut24, ext10): error next to clipped samples is lower than
  a plain clip of the legality-blind decode (G72); smudge groups on rail clips no worse than today (G67).
- Entropy coding: S16 = 16 static tables shared by every step, level and plane (context = class of the local |q|
  scale from decoded neighbours + step-normalised activity of final coarser samples). Fits today's table budget
  (60 tables, 1.1 Mbit) with room to spare (G18-G23).
- Intra vs today (VMAF-NEG): best settings = kept samples rounded to nearest + leaf dead zone rho 0.42 (G73):
  cine_4k_A006 +0.41/+0.05, cine_A005C021 +2.17/+1.39, gfx F003 -0.28/-0.09 at 1.0/1.5 bpp; chroma PSNR still
  behind on the textured and gfx clips (up to -1.9 dB at 1.0).
- Inter (3-frame exact per-frame CBR): worst inter frame from parity to +0.93 NEG vs today (G32); inter chroma
  0.3-2.1 dB behind.
- Still areas: byte-identical frozen input -> one catch-up then 0 changes (G66/G68). Open: grainy/noisy still
  content (the rule must not flicker more than the source: G60-G68); noise-floor sweep pre-registered (G71a).
- Owner record applied: per-region parameters must be continuous fields ("zero visible steps"), so block-keyed
  still/moving steps are dropped; a visible fallback plan is disqualifying (S5.344). Owner guidance 2026-09-30
  (working guidance, not a rule): proceed with the current never-away reading as long as the output is
  artifact-free.
- Not yet run: >= 10-generation chains, per-slice exact CBR, owner's visual tools on inter frames, renders review.

Clips. Owner footage (720p, 4:2:2 10-bit, 2-3 frames, from lossy PNG): test = cine_A005C031, gfx444_B001C001,
prores_sample; training = cine_4k_A006, cine_A005C021, gfx444_F003C012 (tables and lever constants fitted on
training clips, leave-one-out where a training clip is the test cell). Synthetic clips built from cine_A005C031
frame 0: cine_frozen/frozen10 (repeated, 3/10 frames), cine_nfrozen1/2/3 (repeated + fresh Gaussian noise
sigma 1/2/3 per frame), cine_pan0.25/0.5/1.0 (Lanczos-shifted 0.25/0.5/1 px per frame), cine_npan0.5s2 (pan + noise
sigma 2). Rail extremes: the pack's cut24 and ext_10 clips.

Metrics. NEG = VMAF-NEG (owner's model). PSNR per plane Y/Cb/Cr. Churn = share of source-still samples whose output
changes between frames. Boil = mean |frame-to-frame change| per plane; ants = share of changes > 6 codes (both vs
the source's own). Owner tools: smudgegroups (thr 6, dens 0.4), artifactmap, texstat (AMP/PER/COR), render.

Arm tokens used in the log (CBR bench arm names are "_"-joined tokens):
cm<x> chroma step multiplier; ci<x> inter chroma multiplier; fi<x> inter ladder factor; zb<Z> zero-vector bias
(Z codes/sample); hy<k> hysteresis kappa x step of the block's last write; sg still gate on; keep keep the
last-write step on still blocks; rs +0.5-code rounding slack; ng noise-aware gate; nf<k> noise floor k sigma;
bz still block -> all leaves zero; ramp1 no hysteresis in frames 0-1; cu<o> one catch-up per still episode
(o octaves finer); cua catch-up decided after the frame step; rg region plan (moving step + catch-up step);
rr per-connected-region catch-ups; mf moving step floored at the still step; dr drift release; acc
accumulated-since-last-write still test with 3-frame hysteresis; g2 higher-confidence gate; sh 1-px shift test;
win windowed re-hold; eh exact-equality hold (split rule); sl asymmetric step slew limit; chp exact 4:2:2 chroma
motion compensation; s16 S16 tables. Intra settings: rho = leaf dead-zone rounding offset; rho_kept (RHOK) =
rounding of kept/coarse samples; F = intra ladder factor; RCL = range-clamped interpolation; LG = luma-guided
chroma interpolation. S16i/S16u/S16l2 = context variants (indices only / no left neighbour / left at distance 2).

# Running log (tags: MEASURED / PROXY / PAPER)

## §0 Task and footage limits
- Task (CLOUD_README §1.3, HANDOFF §10.2): (1) adversarially verify the SA19 never-away verdict (ledger S5.404,
  SA19 DESIGN §L3); (2) if it holds, find an engine where never-away holds by construction at zero efficiency cost,
  meeting all four goals, legality first.
- Footage for this session is NOT the project footage: 6 clips, 2-3 frames each, from lossy RGB PNGs.
  Consequences: steady state = frame 2 only; no long motion cells; the content is soft (today's codec reaches
  46-56 dB PSNR at 0.5 bpp), so NEG saturates near 94-97 at 0.5/1.0 bpp. Owner rule: rates are 0.5, 1.0, 1.5, 2.0, 2.5,
  3.0 and 4.0 bpp only (nothing below 0.5). The bundled rail extremes (cut24, ext*) are the project's own and are used unchanged.

## §1 Instruments (MEASURED)
- R0 bench reproduction: SA19's own measurement script (unmodified copy) on cut24 @0.5, tab_f0, 3 frames:
  legality-off Y away 5,185 (10.5489 %), Cb 3,774 (15.3564 %), Cr 3,644 (14.8275 %) = SA19's log exactly.
- the bench: VMAF-NEG per frame over ALL frames (frame 2 keeps its motion feature), PSNR Y/Cb/Cr per frame;
  steady = frames 2..N-1.
- Today (v537 real encode/decode on the new clips), frame 2 NEG, PSNR Y/Cb/Cr:
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
  integer 5/3 (bijective re-read), out = clip(up(ĉ) + Δr·q) per sample. PROXY screen, vs an integer 5/3
  transform coder at matched rate, dB Y/Cb/Cr @0.25/0.5/1.0:
  cine Δc/Δr = 4: -0.98/-6.43/-6.14, -4.27/-8.90/-8.18, -7.92/-10.96/-9.97; 2: -1.4..-11.4; 1.25: -0.7..-10.5;
  0.5: -1.02/-4.96/-4.74, -3.45/-6.64/-5.68, -2.37/-2.84/-1.73; 0.25 (not exact: needs steering): +1.07/+0.43/+0.71,
  -2.22/-2.05/-1.32, -3.30/-0.61/-0.13. gfx: every arm -0.2..-12.6 dB at 0.5 (best 0.25: -5.44/-2.03/-4.06).
  prores like cine. -> KILLED (SA20P's bit-floor argument confirmed: a lossless coarse layer cannot dead-zone).
- E2 D-P "update from the prediction" (SA20P; route 1) = predict-only coding of e = x - P, per-sample clip.
  PROXY screen: 3 frames, f0 intra (P = 0), f1-2 inter, same 16x16 block motion
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
- G1 cine 720p, ours - today, NEG then PSNR Y/Cb/Cr:
  PO (form-i private-leaf pyramid, DD4, f 0.7): @0.5 +0.90, +1.55/-0.81/-0.95; @1.0 +0.07, +2.11/-0.64/-0.59;
  @1.5 +0.17, +2.70/-0.26/-0.25; @2.0 +0.13, +2.47/-0.09/+0.13; @2.5 +0.11, +2.63/+0.01/+0.62; @3.0 +0.08,
  +2.66/+0.46/+1.15. N4 T1 (earlier run): ~88.7 NEG @0.5 (worse than PO) -> dropped.
  Integer 5/3 averaging reference (LL DPCM, rho 0.35): @0.5 +1.14, +2.52/+0.68/+0.48; @1.0..4.0 NEG -0.42..-0.57.
  -> Form-(i) intra >= today on NEG at every measured owner rate on cine; the failing item is chroma at 0.5-1.5.
- G2 all three clips, PO intra (real code lengths) minus today's frame 0, NEG then PSNR Y/Cb/Cr:
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
  AND NEG >= today after a 1 % header deduction, every rate 0.5-4.0, 3 clips). the bench
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
  re-interpolated) on 3 clips; otherwise drop. The screen does not clamp at packet edges yet: optimistic.
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
- G7 luma-guided chroma interpolation: where the final co-located luma between the two
  inner DD4 taps differs by more than k x step, chroma is predicted a + w(b - a), w = target luma position in eighths
  (shift-add). Smoke (cine f0, Cb, Q16, intra): nonzero symbols 8657 -> 7196 (LG1), PSNR 53.44 -> 53.80. Real-code arms
  cm1_lg1, cm0.85_lg1, cm1_lg2 queued. Kill: < +0.1 dB worse chroma plane @1.0 on 2 of 3 clips.
- G8 engine rate-control rule (SA20Q flag, both agree): plan from the previous frame's emitted cost, one predetermined
  coarser re-choice, proof the coarsest plan fits, gen 1 emits the plan read from its own picture (joiner needs no
  history). rcl_cbr's multi-Q search is a screen (upper bound) only.
- G9 conditional-mean reconstruction (SA20Q; po RO/RS, LUT trained on the 3 training clips, class = level x min(|q|,4)
  x decoder-side activity class, |delta| <= step/8), intra luma cine frame 0, recon PSNR (bits unchanged except via the loop):
  Q8 53.662 -> 53.723 (+0.06), Q16 49.410 -> 49.412, Q32 45.449 -> 45.463. Per-|q| only: +0.004 / -0.05 dB.
  In-bin means sit at +0.0..+0.16 step, near the dead-zone bin midpoint (+0.15) in every class: the in-bin
  distribution is nearly flat, so no class split carries a usable offset. -> KILLED (< 0.1 dB at every step).
- G10 context lever C2,
  cine cm1, interim: bit saving 7-13 % across Q (9.7-10.6 % at 1.0-1.5 bpp). Versus today, NEG then Y/Cb/Cr:
  @0.5 +1.91 (+2.27/-0.25/-0.42), @1.0 +0.39 (+2.79/-0.28/-0.27), @1.5 +0.28 (+3.29/+0.15/+0.21), @2.0 +0.24,
  @2.5 +0.21, @3.0 +0.14, @4.0 +0.08 (all planes >= today from 1.5 up). Pending: gfx, prores, cm0.85 (chroma at 0.5-1.0),
  packet-edge clamping, table Mbit, 2->1 cross-training.
- G11 exact per-frame CBR screen, cine cm1 (intra ladder f 0.7 in inter frames) @0.5: Q 32.0/26.9/26.9, bpp
  0.465/0.476/0.475, NEG 90.00/93.18/93.03 (today f2 94.20 from the proxy notes). CHURN on source-still samples:
  f0>1 89.7/84.8/86.0 %, f1>2 89.5/85.2/86.6 % (Y/Cb/Cr) = FAILS the churn check (SA17 failure was 20-78 %).
  Bits per level f2 (bpp): kept 0.056, L4 .025, L3 .038, L2 .041, L1 .121, L0 .155.
  Mechanism: with the intra ladder the coarse levels run at 0.17-0.5 Q, so the reference's own coding error is
  re-quantised at the kept/coarse grids, and every coarse change reaches all its descendants through interpolation.
  Arms fi1.0/fi1.4 (flat / coarser-at-coarse ladders) are running.
- G12 TABLE-COUNT FLAG (SA20 on the handoff: today = 60 static tANS tables, L 1024, 1.1 Mbit; a 720-table set,
  26.5 Mbit, was ruled not implementable). All our real-code figures used one table set per quarter-octave step
  (baseline 24 tables x 36 steps). Screen the bench measures the cost of pooling tables over step buckets
  (per-Q, octave, 2, 4 octaves, all) for the base and activity models. Every real-code result is optimistic until then.
- G13 TABLE POOLING:
  base (24 tables/bucket): Q9.5 per-Q 1.476 | octave buckets 1.556 | 2-octave 1.694 | 2 buckets 1.962 | one set 1.630;
                           Q16 0.916 | 0.931 | 0.890 | 0.873 | 1.116 ; Q32 0.458 | 0.466 | 0.510 | 0.482 | 0.702.
  ctx (112 tables/bucket, already > 60): Q9.5 1.334 | 1.377 | 1.453 | 1.565 | 1.377 ; Q16 0.813 | ... | 0.872.
  -> Under today's cap (60 tables) the base model fits only 2 buckets: +10..+33 % bits at mid steps (bucket-edge
     steps worst). EVERY real-code figure (G1-G11) is optimistic by up to that amount; the parity claims vs today
     stand only if a model inside 60 tables recovers the per-Q cost. Next: step-INVARIANT model:
     context = class of an estimated local |q| scale (causal neighbour |q| + step-normalised activity), one table
     family for every step / level (16-64 tables).
- G14 zero-churn rule (agreed SA20P/SA20Q): encoder-only hysteresis dead zone; a leaf is nonzero only if
  |e| > kappa x the step its BLOCK was last written at (state: exponent + mode per block, ~0.1-0.16 bit/sample;
  the per-sample state is SA15's rejected class). Bar: 0 changes on frozen input from frame 2 (one catch-up);
  0 on real still regions beyond the halo; level map at block pitch + rowphase/colphase per plane.
- G15 CHURN ROOT CAUSES (found with the frozen clip = cine frame 0 x 3):
  (a) BUG: the kept DPCM grid started every row at 512 also in inter frames (residual domain needs 0 = copy of P);
      the whole kept grid was re-coded each inter frame and the DPCM chain carried it across. Fixed in n4_core.po.
      All earlier inter/CBR figures (G3 proxy DP, G11) carry this bug; logs moved to the bench
  (b) The encoder motion search (source vs own reconstruction) picked nonzero vectors on 1950 of 3726 blocks of a
      FROZEN clip. Encoder fix: zero-vector bias (keep v = 0 unless the best beats it by > Z codes/sample; Z = 2).
  (c) Hysteresis dead zone (G14) on top: single-frame frozen test at Q 32 -> 26.9: changed samples 66.4 % (a+b fixed,
      no hysteresis) -> 0.12 % (kappa 0.75). CBR arms cm1_zb2_hy0.75 and control cm1_zb2 queued on frozen, cine, gfx, prores.
- G16 (SA20P) zero-vector bias: admissible (on record as SA17 ZTOL 2; ZTOL 0/1 gained +0.05-0.13 NEG but brought the
  flicker back). OPEN RISK: vectors searched against the SOURCE are not reproducible at gen 2 (SA18 D9: 11.5 % of hwy
  block predictions differed). Still areas are safe (gen 2 gets 0). Moving areas need a vector rule that is a function
  of decoded data, or a canonical re-derivation of gen 1's vectors; a moving cell goes into the 10-generation chain.
  Catch-up (encoder-only, per-block state, once per still episode). A block catches up only if ALL hold:
  - still (vector 0, source within the noise tolerance);
  - its caught flag is clear;
  - the current step is >= 1 octave finer than the block's last-write step;
  - the free budget covers the WHOLE connected still region, else it waits (no partial mosaic).
  Clear caught when the source changes. Pass: frozen changes/sample <= 1 over the run per plane; render of the
  catch-up frame; worst-case wait on a busy clip.
- G17 agreed tests for the still rule (SA20P + SA20Q):
  - hysteresis only on SOURCE-still blocks (>= 95 % of the block's luma within 2 codes of the previous source;
    arm token _sg), encoder-only; Z bounded by source noise, never step-scaled;
  - vectors for the product must come from decoded data (gen-2 reproducibility); the bench still searches the source;
  - 10-frame clips: cine_frozen10 (0 changes per plane from frame 2) and Lanczos pans 0.25/0.5/1 px/frame
    (moving-region error must not grow with frame index; control = cm1_zb2 without hysteresis). Queue q_cbr3.
- G18 STEP-INVARIANT TABLES. Context = 16 classes of log2(1 + m),
  m = causal neighbour |q| (left + up + half diagonals) + step-normalised activity. ONE set of 16 tables for every
  step, level and plane (S16). Versus the per-step 1-bit-context sets (24 x 27 tables, the optimistic figure used before):
  cine -10..-16 %, gfx -13..-22 %, prores -11..-18 % bits over the owner-rate range (Q ~3.4..32); +6 % only at
  Q 0.7 (~8 bpp, outside the range). S16p/S16pk/S12pk (32/64/48 tables) within +-0.6 % of S16 -> the plane/level
  split buys nothing. PASSES SA20Q's pre-registered table rule (<= 60 tables, within +1 % of per-step sets).
  Intra vs today with S16 bits, NEG; Y/Cb/Cr:
  cine   0.5 +2.05 (+2.45/-0.15/-0.33) 1.0 +0.60 (+3.18/0.00/0.00) 1.5 +0.35 2.0 +0.30 2.5 +0.24 3.0 +0.17 (all planes +)
  gfx    0.5 +1.85 (+3.62/+0.73/+0.42) 1.0 +0.41 1.5 +0.19 2.0 +0.10 2.5 +0.06 3.0 +0.03 (all planes + everywhere)
  prores 0.5 +1.97 (+2.56/-0.24/-0.36) 1.0 +0.82 (Cr -0.03) 1.5 +0.42 2.0 +0.31 2.5 +0.27 3.0 +0.20 4.0 +0.16
  -> remaining misses: chroma at 0.5 on cine/prores and prores Cr at 1.0; NEG margin there is +0.6..+2.0.
     S16 with cm 0.85 / 0.7 queued to fit the one fixed chroma curve.
- G19 (SA20P on S16): admissible for memory: 16 x 1024 x ~19 bit = 0.31 Mbit per set, ~4 Mbit over 13 lanes at 8K,
  under the 4-5 Mbit cap. Neighbour INDEX contexts are on record (SA17 in-slice left+above, reset at the slice top).
  Conditions:
  - up/diagonal neighbours only from complete rows: define the lane partition (column stripes, left context reset
    at stripe edges);
  - the ACTIVITY term reads reconstructed samples (SA16 bug-4 class: clamp- and plan-dependent), so it needs an
    estimate + reserve, else drop it; S16i (indices only) is being measured to decide;
  - tables trained on the exact inter config; gen-2 bits identical; per-slice exact CBR.
- G20 (SA20Q + SA20P) before S16 counts:
  (1) 8K lanes: the same-array left-neighbour context closes a per-symbol loop. Either show it fits one clock, or use
      contexts from the row above and the previous level only (S16u, measured next). The lane layout must be explicit.
  (2) Quote only NEG vs today (the per-step baseline was undertrained).
  (3) Fit the chroma curve on the TRAINING clips, then
      verify once on the test clips. The test-clip cm runs were stopped.
  (4) Escape share and table size at 3-4 bpp (rcl_s16 prints the share).
  (5) Gen-2/3 bits identical; after one lost slice the next slice parses.
  (6) Header/plan/vector bits counted exactly under per-slice CBR.
  (7) Pass on the worst steady-state frame of the CBR runs.
- G21 S16i (neighbour INDICES only, no activity) vs per-step sets: cine -10 % @Q8, -3.7 % @Q22.6, +7.1 % @Q38, +29 % @Q64;
  gfx/prores alike. S16 (with activity) -13..-16 % at the same steps. At the owner's low rates most q are 0, so indices
  carry little; the step-normalised ACTIVITY from final coarser samples carries the gain. It is plan-dependent
  (SA20P condition): lane costing must use an ESTIMATE (activity from source coarse samples) plus a fixed reserve;
  measuring the emitted-minus-estimate distribution next (rcl_s16 est mode).
- G22 (SA20P accepts) the activity term is admissible: it adds no dependence class (every q already depends on the
  plan in the closed loop), it is deterministic from finals at both ends, and gen 2 gets the same bits. SA16 bug 4
  (estimate/emission context mismatch, clamp-dependent at gen 2) does not apply.
  CBR by construction:
  (a) lane choice from the estimate (source activity + reserve);
  (b) ONE predetermined re-choice when the emitted slice exceeds its budget: re-code at a plan whose worst-case bound
      (max code length over activity classes per symbol) fits, with the coarsest plan proven to fit any content;
  (c) report how often (b) fires per owner rate, including cut frames: often means the reserve is too small, never
      means it is too big.
  The estimate distribution also runs on gfx and a rail clip.
- G23 (SA20Q) the source-activity estimate is signed and content-dependent: final coarse samples are smoother, so
  their activity class is lower. Bound by construction: a final coarse value lies within half a coarse step of the
  source, so the class moves by about one at most. Cost each symbol at its MAX code length over classes c-1..c+1:
  an upper bound, 0 overs, and the price is padding. Pre-registered: 0 overs on every slice (cut frame 0, gfx,
  cut24/ext10, 0.5-4.0), padding <= 1-2 % of bits; else a different bound. Combined with SA20P's single re-choice
  as the backstop. rcl_s16 EST=1 reports est / emitted / upper bound per step on the 3 test clips.
  G23 addendum (SA20P): +-1-class costing bounds the context error but not closed-loop symbol drift, so it is not a full bound. 0 overs by construction = +-1-class lane costing PLUS the single predetermined re-choice (coarsest plan proven to fit). Report re-choice firing rate (<= a few %) and padding (<= 1-2 %).
  G23 addendum 2 (SA20Q): the re-choice is exactly one quarter-octave coarser (the coarsest only in the proven worst case). Where it fires: rowphase + level map per plane vs neighbours + render, no visible strip (S5.344 escalation-ladder visual). Worst-case work = 2 slice codings within the 720p50 3:1 latency slot (9 us margin).
  G23 final (SA20P, converged): the re-choice goes to the FINEST plan whose worst-case bound fits (one pass over precomputed worst-case costs; the coarsest plan only in the true worst case). A fixed quarter-octave step cannot guarantee the fit. SA20Q's visibility checks all stay. The second coding is encoder work only; decoder latency is unchanged.
  G23 latency (SA20Q): A2 counts encode + decode latency. The 2-coding worst case must fit the slice's own slot without extra parallel hardware (pack 1.4); report work per slice vs slot at 720p50 3:1 and 8K; the emission start must not move, else it counts in total latency.
- G24 still-rule results (3-frame frozen, ungated hysteresis): changes per transition 0.12/0.23 % @0.5, 0.00 % @1.0
  and 1.5, 0.04/2.8 % Y @2.0, and 20-59 % @2.5-4.0. frozen10 control without hysteresis (cm1_zb2): 44-71 % for 3
  transitions while Q refines 32 -> 16, then 0.00 % once Q stops moving (re-quantising at the same step is idempotent).
  frozen10 with gated hysteresis @0.5: 0.1 % creeping to 7.7 % by frame 9. Two causes:
  (a) STATE BUG: any changed sample reset the whole block's last-write step to the finer current step, so the block's
      untouched samples were re-coded next frame (an uncontrolled partial catch-up). Fix (_keep): the last-write step
      is kept on source-still blocks; only the source changing (or the explicit catch-up) lowers it.
  (b) ROUNDING: at fine steps the coarse-level steps are ~1 code; integer rounding adds up to 0.5 code, so the old
      error exceeds kappa x s. Fix (_rs): threshold = kappa x s_last + 0.5.
  pan 0.5 px/f (gated): Y PSNR per frame flat 46.29 -> 46.16 (no lag); the "still" churn figure is not meaningful on
  pans (flat moving areas pass the frame-difference test). Arm _sg_keep_rs running on frozen10 at 0.5/2.5/4.0.
- G25 frozen10 @1.0 (gated hysteresis, before the fixes): 0.00 % changes on all 9 transitions, but quality frozen at
  frame 0 (Y 49.41, NEG 93.70; 0.814 bpp spent coding zeros = padding under CBR). Control without hysteresis: ONE
  74 % transition (Y 49.41 -> 52.33, NEG 93.70 -> 95.07), then 0.00 % on all later transitions (re-quantising at
  the same step is idempotent). That single step is what the catch-up must deliver, once, on purpose. Arm _cu
  (SA20P rule): per block still & not caught & step <= last-write step / 2 -> no hysteresis in that frame (the plan
  search costs it), last-write step := current, caught until the source moves. Running on frozen10 at 0.5/1.0/2.5.
- G26 frozen10 @0.5 with _sg_keep_rs (no catch-up): changes per transition 0.11/0.10/0.09 %, 0.02/0.02/0.03 %, then 0.00 % on all 7 remaining. The state bug and rounding fixes work. Residual 0.1 % in transition 1: suspected the 4 blocks with nonzero vectors on frozen input (to verify). Quality is held at frame 0 (NEG 90.00); the catch-up arm (_cu) is next.
- G27 frozen10 with the fixed hold (_sg_keep_rs): 0.00 % changes on every transition at 2.5 and 4.0 (0.11/0.02 % then
  0 at 0.5). The catch-up with a ONE-OCTAVE condition (_cu) never fired: under exact per-frame CBR, re-coding the whole
  still region an octave finer costs more than one frame's budget, so the plan search stops just above the threshold
  (Q 19 vs threshold 16 @0.5, 9.5 vs 8 @1.0). The control's natural single step was ~0.75 octave. Testing thresholds
  of 0.5 and 0.25 octave (_cu0.5, _cu0.25); the caught flag keeps it to ONE catch-up per still episode.
- G28 the residual 0.11/0.02 % on frozen10 @0.5 is NAMED: all 972 changed luma samples lie in the 4 blocks where the
  motion search still picks a nonzero vector (right frame edge, edge padding); none are at the rails. Fix (encoder):
  a source-still block gets the zero vector.
  SA20Q/SA20P: the 2-code gate will not fire on real grain (noise 1.5-3 codes -> frame differences 2-4 codes).
  Noise-aware gate (_ng):
  - noise per luma bucket (8 buckets) = 20th percentile of block mean |d| among that bucket's blocks;
  - a block is still if mean |d| <= 1.5 x noise and |mean d| <= 3 x noise / 16;
  - hysteresis threshold >= 2 sigma-hat.
  Catch-up sized by the budget (_cu0: any finer step the frame funds, once per episode; SA20P).
  Clips (10 frames): frozen10, noisy frozen sigma 1/2/3, pan 0.5 and noisy pan 0.5 sigma 2; 0.5/1.0/2.5/4.0.
  Snap checks pre-registered (SA20Q, S5.390 list):
  - share, mean and max |delta| per plane;
  - <= 1 change per sample per episode;
  - uniform |delta| map, smudgegroups/artifactmap;
  - renders before/after;
  - mean |delta| <= source temporal noise in moving areas;
  - worst-case wait.
- G29 frozen10 with _ng_cu0: ONE catch-up of the whole frame in frame 1 (all 3600 blocks; @1.0 74 % of samples,
  Y 49.41 -> 52.33, NEG 93.70 -> 95.07; @0.5 45.45 -> 47.23, NEG 90.00 -> 92.58), then 0.00 % on all 8 later
  transitions. This is the pre-registered pattern.
  Noisy frozen sigma 2 FAILED: 83 % changes per frame, although 98 % of blocks were labelled still. My bug: the 2 sigma
  floor was put inside KQ, which is scaled by 0.7^level, so the coarse levels had ~0.17 x 2 sigma. Predict-only levels
  keep RAW samples with full noise, so the floor must be additive at every level. Fixed; re-queued.
- G30 S16u (row above + diagonals + activity, NO left neighbour) vs S16: +3..+6 % bits at high rates, +18..+32 % at
  Q 16-27 (0.5-0.9 bpp) on all 3 clips. Vs today: cine @0.5 -0.32 NEG, and chroma fails at 0.5-1.0 on cine and prores.
  -> the same-row left neighbour carries a large share of the gain; the per-symbol loop is real. Next: S16l2 (left
  neighbour at distance 2 -> a 2-cycle loop in a lane, the standard relaxation).
- G31 lane-costing estimate (rcl_s16 EST=1, intra f0, S16):
  - emitted minus estimate (activity from SOURCE coarse samples) stays within -0.9..+0.45 % on all 3 clips at every
    step (both signs, no rate trend);
  - the +-1-class upper bound (SA20Q) pads +12..+126 % (the max over classes charges zeros at high-activity
    classes), far above the 1-2 % pass -> REJECTED as a costing rule.
  Rule adopted: estimate + ~1 % reserve for the lanes, SA20P's single re-choice (finest plan whose worst-case bound
  fits) as the guarantee. Firing rate and padding still to be measured under per-slice CBR (intra here; inter,
  cut frames and rails pending).
- G32 3-frame exact per-frame CBR, S16 tables (32: 16 classes x intra/inter), still rule _sg (pre keep/rs/ng),
  cm1, vs today per frame:
  - worst inter frame NEG, ours - today: cine +0.36/-0.04/0.00/+0.01/+0.04/-0.01/+0.01;
    gfx +0.93/+0.02/-0.11/-0.06/-0.13/-0.01/-0.01; prores +0.26/+0.44/+0.06/-0.07/+0.06/-0.02/+0.03 (0.5..4.0);
  - frame 0 ahead at every rate up to +1.49;
  - f2 CHROMA -0.3..-2.1 dB on every clip at 0.5-3.0; gfx f2 luma -0.8..-2.1 dB at 1.0-4.0.
  -> worst-frame NEG ranges from parity to ahead, but inter chroma is short. Levers: a separate INTER chroma multiplier
     (fitted on the training clips), the chroma curve, and the fixed still rule (keep/rs/ng/cu0) under S16.
     Caveats: one Q per frame, source-searched vectors, 10-bit vector charge.
- G33 (SA20P) gfx inter luma deficit (-0.8..-2.1 dB, against -0.14..-0.29 for intra) points to PREDICTION.
  Discriminator before any lever:
  (a) f1 intra vs inter bits/PSNR at the same step;
  (b) MC PSNR for 16x16 vs 8x8 blocks, Z2 vs Z0 (ceilings only: half-pel is on SA17P's do-not list, source vectors are
      not gen-2 exact);
  (c) bits by level at text edges.
  Levers by outcome:
  - prediction loses to intra -> a continuous prediction-weight field from decoded data (per-block modes are falsified);
  - vector precision or staleness -> coarse-first current-frame vectors on decoded coarse data (SA18 D13/D14, exact by
    construction; SA20P's first pick);
  - interpolator -> the gradient-weighted blend.
- G34 (SA20Q) worst-case fit proof MISSING for this engine: every sample carries a leaf; at 0.5 bpp that is <= 0.5 bit
  per leaf while an escape costs >= 10 bits, so no ordinary plan has a provable worst case below budget on hostile
  content. A provable fallback must bound the symbol COUNT (e.g. finest levels signalled as zero runs, kept coarse part
  bounded analytically). It would be a visible strip step if it fired, so it is the proven-worst-case plan only;
  pre-register: fired 0 times on all test and cut24/ext10/gfx cells at 0.5-4.0; ordinary re-choice <= a few %.
  If no bounded plan exists, exact CBR is NOT proven for this engine. OPEN.
  Inter chroma gap, causes to rule out before any multiplier:
  1. chroma MC rounded the halved luma vector to whole chroma samples: half-sample misalignment for odd dx (TRUE in
     the bench) -> arm _chp (exact half-sample average);
  2. luma still gate and luma noise floor applied to chroma (TRUE) -> a per-plane gate and noise estimate to do;
  3. last-write state is already per plane;
  4. inherited intra chroma deficit: S16 intra f0 chroma -0.15..-0.36 dB at 0.5, while f2 is -1.8 -> inter adds most;
  5. inter ladder tuned on luma.
- G35 OWNER CALL TO FLAG (SA20P + SA20Q): a provable exact-CBR fit in form (i) needs a bounded plan (finest leaves
  forced to zero), which would be a visible rung if it fired (S5.361 class). Question for the owner: is a proven
  worst-case plan that never fires on any test cell acceptable, or must the rung be impossible by construction? Under
  the second reading no fixed-rate codec qualifies, today's included (pathological input such as 12-bit noise at
  0.5 bpp loses the picture in any CBR codec).
  Chroma ablation (one switch per run, cine + prores, 0.5/1.0/2.0, same S16 tables): base = fixed still rule
  (_sg_keep_rs_ng_cu0); +_chp (exact 4:2:2 chroma MC); +_pp (per-plane gate and noise); +both.
- G36 gfx discriminator:
  - intra vs inter at the same step: Q4.76 1.640 vs 1.561 bpp (Y 57.33 vs 57.19); Q8 0.959 vs 0.842; Q16 0.447 vs 0.294;
  - MC prediction PSNR ~ the reference copied as is: 53.26 (16x16 Z2) / 53.40 (Z0) / 53.80 (8x8) vs 53.25 at Q4.76.
  -> gfx is essentially static; inter re-codes the reference's error at nearly the same step, so there is no build-up.
     Consistent with the old 2-code gate missing gfx noise, so the hold never applied. The noise-aware gate plus the
     budget-sized catch-up (base arm of G35) is the lever; now also run on gfx at 1/2/4. 8x8 blocks +0.4..+0.7 dB MC
     (ceiling, vector bits x4).
- G37 noisy frozen sigma 2 with the additive 2 sigma floor: still 54-73 % changes per frame. Mechanism: at the kept
  coarse grid the threshold (kappa s_L + 2 sigma ~ 8 codes) is exceeded by ~2 % of samples from fresh noise alone, and
  each coarse change spreads through interpolation to ~500 finer samples. A hold against i.i.d. noise needs a far
  smaller exceedance at coarse levels. Floor multiplier made a parameter (_nf<k>); testing 5 sigma on sigma 2 and 3.
- G38 gfx @1.0 with the fixed still rule (_sg_keep_rs_ng_cu0_s16): 66-71 % of blocks labelled still, but inter
  frames spend 0.49/0.55 bpp of 1.0 with Q stuck at 8; f2 Y 52.93 vs today 55.45; changes 71-76 % (the G37 coarse-grid
  noise mechanism). PLAN PROBLEM: with ONE step per frame, any finer step triggers the whole-region catch-up and
  overshoots, so the search keeps the coarse step and the rest is padding. The moving-region step and the still-region
  catch-up must be decoupled (a per-region step, i.e. a signalled plan), or the catch-up made independent of the
  frame step. Taken to SA20P/SA20Q; the answer must keep continuity at region edges (heal-edge test).
- G39 CONVERGED plan structure (SA20Q proposal, SA20P conceded (c)):
  - per-block steps read canonically, gen 1 emits its own reading;
  - moving step Q_m per slice; the still, not-caught blocks caught ONCE at Q_c = the finest step whose cost fits the
    padding (>= 0.25 octave finer than their last step), whole set, else wait;
  - (b) = separate connected regions may catch up in different frames, one region never split;
  - ramp rule (SA20P): no hysteresis in frames 0-1 (stream start and after cuts);
  - block-level still gate: a noise-consistent block gets ALL leaves 0 (_bz).
  OWNER FLAG: a per-region step is a per-region parameter; its boundary follows the block-shaped still/moving mask
  (HVBC-class risk under the zero-visible-steps rule). Hard kill test: level map and |diff| per plane at boundaries,
  rowphase/colphase at block pitch, real-time render. The same boundary exists under any hold, (c) included.
  Also fixed: the INTER kept grid now predicts residuals by 0 (the residual DPCM chained along rows: noisy frozen
  45 % -> 8.7 % changes before the block gate). po takes a per-sample step map QM (bit-identical at QM = 1).
  Bench: _rg (the (a)+(b) plan, 1 bit/block map charge) vs _cua (c) on gfx 1/2, cine 0.5/1, noisy frozen sigma 2
  (10 f) and noisy pan (10 f).
- G40 TRAINING-CLIP FIT, NEG at 1.0..4.0:
  - cine_A005C021 cm1: +2.09/+1.37/+0.75/+0.71/+0.50/+0.40 (and +6.05 @0.5);
  - cine_4k_A006 cm1: -0.77/-0.39/-0.22/-0.31/-0.17/-0.00 (+8.15 @0.5), although luma PSNR is +2.1 dB;
  - gfx F003 cm1: -1.18/-0.57/-0.20/-0.24/-0.01/-0.05 (-0.17 @0.5), luma PSNR +1.3..+2.2 dB.
  cm0.85/0.7 lower NEG further on every clip. -> The intra "NEG >= today everywhere" of G18 (3 test clips) does NOT
  generalise: on the fine-texture 4K-downscaled clip and on gfx F003 we are BEHIND on NEG while AHEAD on PSNR, the
  signature of detail loss (VMAF-NEG rewards kept texture; PSNR rewards smoothing). Suspect: the dead zone (rho 0.35)
  zeroes small leaves, and interpolation fills smooth. Screen: rho 0.35 / 0.42 / 0.5 on A006 (RHO env).
  No chroma curve is fitted until this is understood (every cm < 1 lowers NEG).
- G41 PRE-REGISTERED intra verdict (SA20Q):
  - all 6 clips, tables disjoint (leave-one-out for the training clips, all-3-trained for the test clips);
  - every clip x rate 0.5-4.0, no averaging;
  - PASS: NEG >= today - 0.05 AND PSNR Y/Cb/Cr >= today - 0.1 dB, after the 1 % header charge;
  - any cell below FAILS and is reported.
  Intra is a diagnostic; the binding verdict is the worst steady-state CBR frame (f2+) on the same 6 x 7 grid, same
  rule. Levers are fitted on the 3 training clips and verified ONCE on the test clips.
  Detail-loss confirmation:
  - per-band error energy ours/today (D3 method);
  - texstat/flatplane per plane at 1.0/2.0.
  Candidate levers (fitted on training clips): rho; a finer level-1 step relative to coarse (tilt to fine levels);
  a smaller dead zone on level 1 only.
- G42 per-band error energy, ours/today:
  A006 @1.0 Y 0.54 0.62 0.93 1.39 1.64 1.71, Cb 1.04..2.72, Cr 1.08..3.30; A006 @2.0 Y 0.55 0.71 0.90 1.03 0.89 0.39;
  gfx F003 @1.0 Y 0.60 0.69 0.78 1.37 1.16 0.40; C021 @1.0 Y 0.38 0.36 0.42 0.64 0.89 0.79 (C021 is ahead on NEG).
  -> NOT detail loss: we have LESS fine-band error than today and MORE 8-32 px (mid/coarse) error, chroma worst.
  A tilt toward fine levels would be the wrong direction. Lever to screen: a steeper intra ladder (f 0.6 / 0.5 =
  finer coarse steps), fitted with nested leave-one-out (SA20P: lever constants fitted per test cell on the other clips
  only). Record from SA20P (do NOT repeat): SA15 offset 1/3 erased grain, SA14 narrower dead zones cost bits, SA13 dz
  0.75 -0.64, SA16 PSNR-optimal ladder zeroed level 1 (-4.8); grain fill and synthesized texture banned; per-cell
  tuned dead zones banned.
  Intra verdict rule (G41) agreed by both thinkers, plus nested leave-one-out for levers.
- G43 VMAF-NEG feature breakdown ours - today:
  A006: VIF s0 +0.051, s1 -0.021, s2 -0.015, s3 -0.008; ADM s0 +0.023, s1 +0.005, s2 -0.003, s3 -0.001; NEG -0.99.
  gfx F003: VIF s0 +0.037, s1 -0.009, s2 -0.007, s3 -0.004; ADM s0 +0.008, s2 -0.005, s3 -0.002; NEG -0.70.
  -> Confirms G42: we lead at the finest scale and trail at VIF scales 1-3 / ADM 2-3 (mid/coarse fidelity). The
     lever is more precision at the coarse levels (steeper ladder, f < 0.7), not texture keeping.
- G44 SMUDGE: cine_4k_A006 OURS Y 1 group (10 blocks,
  rows 442-451 cols 704-799), Cb 1 (8), Cr 2 (17); TODAY 0/0/0. gfx F003 ours 0/0/0, today 0/0/0.
  -> intra form (i) at the G18 ladder FAILS goal 1 (no smudges) on A006. The coarse-scale error of G42/G43 is visible.
  Pass rule for every ladder/rounding arm (SA20P + SA20Q), all required:
  - smudgegroups + artifactmap clean per plane;
  - per-scale VIF/ADM >= today;
  - error ratio vs today <= ~1 at 8-32 px.
  Kept-sample rounding: report bits per level alongside. The chroma offset merges into one chroma-step function.
- G45 A006 (fine texture) intra vs today, NEG at 0.5..4.0:
  in-sample tables  +8.09/-0.79/-0.40/-0.22/-0.31/-0.17/0.00  (= leave-one-out within 0.02: tables are NOT the cause)
  rho 0.35 (base)   +8.15/-0.77/-0.39/-0.22/-0.31/-0.17/0.00
  rho 0.42          +10.81/+0.11/-0.05/0.00/-0.16/-0.04/+0.01  (Y PSNR +2.0; Cb/Cr -0.8/-1.6 @1.0)
  rho 0.50          +11.96/+0.36/-0.09/0.00/-0.15/-0.03/0.00  (Y PSNR +1.2..1.6; chroma lower)
  -> a smaller dead zone recovers most of the NEG deficit on A006. It runs against the SA14 record (narrower dead
     zones lost), plausibly because S16's activity contexts make +-1 leaves cheap. Nested fit needs F003 and C021 at
     rho 0.42/0.5, plus the smudge/feature/band check per arm.
- G46 (SA20P) dead-zone record: none covers an intra dead zone in a predict-only private-leaf pyramid at real code
  lengths, so this is a new regime.
  - SA15 config B (0.45 vs 1/3) +0.36/+0.38 is the same direction.
  - SA15 ZH lost by re-sending grain in INTER (lattice-lock hysteresis removed): that is the trap for us.
  - SA14 compared unmatched bpp (weak evidence); SA13/SA17 were the averaging family, inter-heavy.
  Why form (i) differs: a zeroed leaf becomes a smooth DD4 fill and a kept sample's error is final, so a higher optimum
  rho is expected. Watch-outs:
  (i) rho fitted separately for intra/kept and inter leaves, and the still hysteresis stays authoritative (frozen and
      noisy-frozen churn must stay 0);
  (ii) rho 0.42 must REMOVE A006's smudge groups (checked in ieval_rho);
  (iii) a static-control arm against the bits-only trap.
- G47 A006 @1.0 with rho 0.42 (intra_eval at the nearest logged step, 1.07 bpp; not rate-matched):
  - smudge groups ours Y0/Cb0/Cr0 (was Y1/Cb1/Cr2), today 0/0/0 -> the goal-1 failure is removed on this cell;
  - VIF s1..s3 -0.002/-0.004/-0.001 (was -0.021/-0.015/-0.008); ADM s2/s3 +0.002/+0.001;
  - band ratio Y 0.51 0.53 0.75 1.11 1.12 1.13 (coarse was 1.39..1.71); Cb coarse 1.22..1.79, Cr 1.47..2.58;
  - PSNR Y +2.55, Cb -0.38, Cr -1.29.
  The rate-matched NEG (interpolated, G45) is +0.11. Chroma coarse error remains the open item -> fold into the single
  chroma-step function (nested).
  SA20Q: rho is a legitimate encoder constant: exactness is free (the canonical reading does not use rho; rho < 0.5
  is idempotent, 0.5 needs a tie rule); the CBR estimate must use the same rho; tables per rho arm (the bench already
  retrains: RHO also applies in training). Remaining checks per arm:
  - the 2x2 (base vs S16 contexts x rho 0.35/0.42);
  - Q and bits per level;
  - texstat vs SOURCE (grain amplification);
  - inter still churn;
  - a static control.
- G48 texstat (owner tool, vs SOURCE) A006 f0 @1.0 (AMP: 1 = source texture energy; PER: > 1 = periodic structure
  the source lacks; COR: correlation with the source texture):
  rho 0.35: Y AMP 0.960 COR 0.891 | Cb 0.708/0.465 | Cr 0.455/0.254 | PER 0.83-0.85
  rho 0.42: Y AMP 1.005 COR 0.901 | Cb 0.836/0.503 | Cr 0.591/0.304 | PER 0.79-0.86
  today:    Y AMP 0.987 COR 0.788 | Cb 0.657/0.419 | Cr 0.331/0.204 | PER Cb 1.05, Cr 1.43 (periodic chroma structure)
  -> rho 0.42 keeps texture at source energy (no amplification), with higher correlation to the source than today on
     every plane. No grain-amplification trap on this cell. the bench now prints texstat per arm.
- G49 NESTED rho fit, training clips, rate-matched intra NEG vs today, 0.5..4.0:
  A006  rho .35 +8.15/-0.77/-0.39/-0.22/-0.31/-0.17/0.00 | .42 +10.81/+0.11/-0.05/0.00/-0.16/-0.04/+0.01 | .50 +11.96/+0.36/-0.09/0.00/-0.15/-0.03/0.00
  C021  rho .35 +6.05/+2.09/+1.37/+0.75/+0.71/+0.50/+0.40 | .42 +6.04/+2.26/+1.45/+0.79/+0.67/+0.52/+0.42 | .50 +5.65/+1.97/+1.26/+0.69/+0.59/+0.42/+0.38
  F003  rho .35 -0.17/-1.18/-0.57/-0.20/-0.24/-0.01/-0.05 | .42 +0.65/-0.70/-0.25/-0.04/-0.09/+0.05/-0.03 | .50 +0.94/-0.44/-0.10/+0.01/-0.10/+0.07
  Nested choice (fit on the other two clips): 0.42 for every clip (0.5 wins A006/F003 NEG slightly but loses chroma
  0.5-1.0 dB everywhere). Spread: 0.42-0.5, same direction everywhere -> ship rho 0.42 (intra), per SA20Q's rule.
  G41 VERDICT (intra, rho 0.42), cells FAILING (NEG < -0.05 or a plane < -0.1 dB):
  - A006: NEG @2.5 -0.16; Cb/Cr @0.5 -2.46/-3.89, @1.0 -0.81/-1.62, @1.5 Cr -0.70, @2.0 Cr -0.11;
  - F003: NEG @1.0 -0.70, @1.5 -0.25, @2.5 -0.09; Cb/Cr @0.5-2.5 -0.07..-0.50;
  - C021: Cb/Cr @0.5 -0.84/-1.33.
  -> Form (i) intra with S16 + rho 0.42 is NOT yet >= today on every cell. Luma PSNR leads by 1-4.7 dB everywhere, so
     bits are spent on luma that chroma and NEG need. Next lever: the single chroma-step function (nested) at rho 0.42.
- G50 region plan (A = _rg) first results:
  - noisy frozen sigma 2: 5-9 % changes per frame, no catch-up ever. The greedy moving step (Q 0.25-0.71) spends the
    whole budget coding the ~2 % of blocks the gate mislabels as moving, nearly losslessly.
  - noisy slow pan (0.5 px/f, sigma 2): 57 % of blocks labelled still; Y 45.98 -> 43.61 over frames = hold drift (smear).
    The source-difference gate cannot see low-contrast slow motion inside noise (SA20Q's warning).
  - gfx @1/2: 37-44 % of samples change per transition.
  - C arm crashed: token parser bug ('cua' read as 'cu' + 'a'); fixed.
  Fixes (_mf, _dr):
  - moving step never finer than the still region's median step, leaving padding for the catch-up;
  - DRIFT RELEASE: a block stays still only while MAD(x_t - own recon) <= its error at last write + 1.5 noise
    (error-triggered, S5.390); slow motion accumulates error and releases the hold.
  Re-run A2/C2 on the same clips (rg2_*).
- G51 (SA20P) both rules admissible.
  Moving-step floor: equal-slope allocation means one gain-normalised step, so "moving never finer than still"
  approximates the RD optimum. Conditions:
  - fix the ~2 % mislabelled blocks at the GATE, with 5-9 %/frame -> 0 with the floor on and off;
  - on a mostly-moving clip (whole-frame pan) the floor must not bind: report Q with the floor on/off, NEG unchanged.
  Drift release = the S5.390 error-triggered form. It must be hysteretic (release at E_last + 1.5 sigma-hat, E_last
  resets at the re-code, re-entry only via the normal still test). Report release events per block per 10 frames:
  0 on noisy frozen, ~1 per block crossing on slow pans.
- G52 (SA20Q, SA20P agrees) the drift release can oscillate on slow pans (hold -> drift -> re-code -> hold: periodic
  jumps = judder, killed by S5.390). Root fix (_acc):
  - still = the source is unchanged since the block's LAST WRITE (accumulated: MAD(x_t - x_last) <= 1.3 x noise)
    AND frame-to-frame noise-consistent;
  - temporal hysteresis: still only after M = 3 consecutive passes.
  The bench stores the last-write source frame; SA20P's memory form = per-block source mean (+ gradient) at last write
  + MAD(x_t - decode_(t-1)) for mean-preserving texture shifts; per-block state at 8K to report.
  Pre-registered (SA20Q), pans 0.25/0.5/1 px clean and noisy, >= 10 frames:
  - per block, changes 0 or >= N-2; intermittent (2..N-3) <= 1 % of pan blocks, no periodic pattern;
  - moving-region error flat (slope, peak-to-peak);
  - render for judder;
  - frozen/noisy frozen 0 after the one catch-up.
  Output now prints the per-block change histogram. Queue q_acc.
  G52 addendum: memory form agreed. Per 64x8 block: step exponent + still flag + caught flag + 4 sub-block source means (2x2, ~40 bits) at last write + M counter, plus MAD(x_t - held recon) for mean-preserving texture shifts; well under 1 bit/sample at 8K (exact figure to report). The bench's stored source frame is a screen stand-in.
- G53 plan comparison with drift release (A2 = (a)+(b) _rg_mf_dr, C2 = (c) _cua_dr), last-frame NEG:
  cine 0.5/1.0: A2 93.08/96.43, C2 93.02/96.43 (equal).
  noisy frozen sigma2 0.5/1.0: A2 92.64/94.03 vs C2 91.79/94.08. BOTH FAIL churn: A2 8-10 %/frame with a repeated
    re-catch-up of 71-87 blocks at Q 0.2-0.4 every frame (blocks flipping still/moving clear CAUGHT and re-fire);
    C2 5-7 %/frame, per-block histogram 67-71 % intermittent.
  noisy slow pan: both decay (A2 91.99 -> 89.89, C2 92.28 -> 89.31); the drift release did not stop the smear.
  gfx 1.0/2.0: A2 96.44/96.43, C2 96.41/96.69. A2 @2.0 spends only 0.73 of 2.0 bpp in f2: the moving floor blocks the
    moving step while the whole-region catch-up does not fit (waste).
  -> Root of the churn and smear = frame-to-frame gate mislabels (the accumulated test + M=3 hysteresis, q_acc, targets
     exactly this). Plan flaws to fix: (i) the moving floor must apply only when a catch-up can use the padding;
     (ii) the catch-up step must be bounded below (never finer than ~the moving step), not 0.2.
- G54 accumulated still test + M=3 hysteresis (A3 = _rg_mf_acc):
  - frozen10 @0.5: ramp frames 0-1, ONE whole-frame catch-up in f2 (3600 blocks @Q16), then 0.00 % on all 7 later
    transitions; NEG 91.22 -> 93.91 held. PASS pattern (ramp + one catch-up + zero).
  - noisy frozen sigma 2: 13-16 %/frame; ~6 % of blocks fail the gate each frame on pure noise, their caught flag clears
    and they are re-caught at Q 0.2-0.4 (lossless-grade) each frame. Gate confidence too low (the 20th-percentile noise
    estimate and the 3 sigma/16 mean test fail ~1-2 % of noise blocks each, compounded).
  - clean pans 0.25/1 px: catch-ups every frame, 13-29 % intermittent blocks (bound 1 %) -> FAIL.
  - noisy pan 0.5 px: NEG decays f1 -> f9 (0.5: 91.99 -> 90.68, 2.0: 95.65 -> 93.66).
  - gfx: 96.43 / 96.60 (2.0 f2 spends 1.0 of 2.0 bpp).
  Needed: gate thresholds at higher confidence; the caught flag must not clear on a single failed frame; a floor on
  the catch-up step (never finer than the moving step). Today's codec is running on the synthetic clips (frozen10,
  nfrozen2, npan, pans) as the reference for decay and churn.
- G55 gate g2 (35th-pct noise, 1.5 n / 5 n/16, release after 2 fails, catch-up step >= moving/2):
  - noisy frozen sigma 2: ONE whole-frame catch-up in f2, then 0.00 % on all 7 transitions @0.5 and @1.0 -> PASS;
    frozen10 still passes.
  - noisy slow pan: 65 % held and severe smear (NEG 0.5: 92.01 -> 87.51; 2.0: 95.65 -> 88.53) -> FAIL (gate cannot
    separate slow low-contrast motion from noise).
  - clean pans: 31-40 % intermittent (bound 1 %) -> FAIL.
  - gfx: f2 spends 0.25/0.35 of 1.0/2.0 bpp; NEG 95.87/96.16 < f1 -> FAIL (floor binds with no catch-up = G53 flaw i).
  Next (_sh + floor release):
  - MOTION-AWARE hold: release when a 1-px shift of the last-write source explains x_t better than zero shift
    (margin 0.15 n); flat blocks stay held (harmless);
  - if no catch-up fires, re-search the moving step without the floor.
  today's codec on the synthetic clips (0.5/2.0, NEG3): frozen10 92.01/95.80, nfrozen2 91.87/95.59,
  npan 91.69/95.70, pan0.25 92.01/95.89, pan1.0 92.02/96.13.
- G56 (SA20Q) motion-aware hold:
  - noise false releases are negligible at a 0.15 n margin (>= 3.5-5 sd of the MAD-difference spread); textured still
    blocks never falsely release;
  - MEMORY: run the shift test against the stored reference D(t-1), already in DDR, not a stored source copy;
  - sub-pixel onset: also test +-0.5 px (bilinear), so drift is caught at ~0.25-0.4 px; judge the one-time onset lag by eye.
  Pre-registered pan bound (0.25/0.5/1 px, clean and sigma 2-3, N >= 10-12, 0.5-4.0), blocks classed by source texture:
  - textured: changes >= N - L with L <= 2 (0.25 px), <= 1 (0.5 px), 0 (>= 1 px);
  - flat: 0 changes allowed; intermittent textured <= 1 %;
  - per-frame error flat after onset;
  - CONTROL no-hold arm: hold on vs off within 0.1 NEG (mean and worst frame) and 0.1 dB per plane on pans.
- G57 motion-aware hold (_sh, integer 1-px shift test at 16x16):
  - clean pan 1 px: 96.9 % continuous, 3.1 % intermittent (bound 1 %: close, fails);
  - pan 0.25 px: 40 % intermittent (FAIL);
  - noisy pan 0.5: still smears (2.0: 95.65 -> 89.00), low-contrast motion in noise invisible to the shift test;
  - frozen and noisy frozen: still PASS;
  - gfx: the floor release sends the moving step to Q 1.0/0.25 while the still set stays at f1 quality; f2 NEG
    96.35/96.43 < today 96.50/96.88 -> per-connected-region catch-ups ((b)) needed.
  today frozen10 @0.5 per frame: 89.82 92.48 93.74 94.03 ... 94.10 (keeps building through churn); ours plateaus at
  93.91 after the single catch-up.
- G58 (SA20P) M-hysteresis alone still oscillates on slow pans: while a block is coded every frame, "last write" =
  the previous frame, so 0.25 px/f passes the still test, re-holds, drifts, releases (judder, period M+k). Cure =
  stillness over a TIME WINDOW (_win):
  - re-hold only if the 8x8 sub-block means are unchanged vs W = 4 frames back (within ~1.5 sd of noise);
  - held blocks release from the RECONSTRUCTION side (MAD(x - D) > E_last + 1.5 n).
  State: W sets of 4 sub-means per block (a few hundred bits/block, << 1 bit/sample).
  Per-region catch-ups (_rr): each connected still region whole, once, fixed order, at the finest step the padding
  funds for the whole region (>= 0.25 octave finer), else wait. The gfx Q 0.25 moving step in G57 was my floor
  release (G55), not an inactive floor. Arm A7 = _rg_rr_mf_acc_g2_sh_win queued on all still/pan clips + gfx.
- G59 per-region catch-ups (_rr) on gfx @1.0/2.0: 89 % of the frame is ONE connected still region; re-coding it even
  0.25 octave finer costs ~1.1x a frame's budget, so it never fits under exact per-frame CBR; only small regions
  (4-13 blocks) are caught. f2 spends 0.28/0.39 bpp of 1.0/2.0; NEG 95.97/96.25 < f1 96.55/96.78 < today f2 96.50/96.88.
  cine @0.5/1.0: regions of 550-574 blocks caught; NEG f2 92.97/95.96 (G32 no-hold arm 93.18/96.07).
  READING: the held region LOSES NEG vs its own f1 value, so the hold is not free on real (grainy) footage. Holding
  freezes the grain while the source grain moves; the error = fresh source noise each frame. Today follows the grain
  (= churn). If the no-hold control confirms it, this is the measured PRICE of the owner's zero-churn rule on grainy
  still content, to be reported rather than engineered around (grain synthesis is banned).
- G60 (SA20Q) G59 is NOT yet a price: the owner's zero-change bar was set on byte-identical frozen input; for real
  grainy content the recorded bar is A2 "sub-source calm" (output boil and ants tail <= the source's). Freezing
  grain is our gate's choice. The compliant third arm is GRAIN-FOLLOW: the still gate off, per-sample hysteresis
  (kappa Q_last + rounding slack) kept, so leaves track the real grain once it exceeds the step, with no sub-code wobble.
  Three arms on gfx B001 and cine C031 @1.0: HOLD (_win arm), NO-HOLD (cm1_zb2_chp_s16), GRAIN-FOLLOW
  (cm1_zb2_hy0.75_rs_chp_s16). Output now reports boil and ants (|delta| > 6) per plane vs the source.
  PASS grain-follow: NEG >= today, boil <= source, ants <= source per plane, no visible shimmer; frozen input still 0.
  Judge NEG against the source everywhere; the eye decides (the renders go to the owner).
  today @1.0 (3 frames), boil = mean |delta| per plane, ants = share |delta| > 6:
  gfx B001: Y boil 1.518 (src 1.585) ants 2.06 % (src 1.17 %) | Cb 1.158 (1.569) 0.37 % (0.49 %) | Cr 0.820 (1.133) 0.11 % (0.02 %)
  cine C031: Y 7.527 (8.129) 28.49 % (31.13 %) | Cb 1.360 (1.546) 1.13 % (2.54 %) | Cr 1.642 (2.133) 1.84 % (3.92 %)
  -> today's boil is below the source everywhere, but its ants tail on gfx luma and Cr is ABOVE the source.
- G61 GRAIN arms @1.0 (f2 NEG; boil/ants vs source):
  gfx B001: HOLD 95.98 (boil 1.00 < 1.59 src; ants 1.55 % > 1.17 %) | NO-HOLD 96.43 (1.62 > src; 1.89 %) |
            GRAIN-FOLLOW 96.53 (1.51 < src; 1.78 %) | today 96.50 (1.52; 2.06 %).
            GF f2 PSNR vs today -0.05/-0.09/-0.95; GF f1 NEG 96.14 < today f1 96.40.
  cine C031: HOLD 96.03 | NO-HOLD 96.09 | GRAIN-FOLLOW 96.07 (boil/ants below source on every plane) | today 96.11.
  -> GRAIN-FOLLOW is the best arm: NEG >= today at f2 on gfx, parity on cine; boil below source on every plane, ants
     tail below today's (above the source on gfx, as in every arm and today). Open: gfx Cr -0.95 dB, the f1 dip, and
     the frozen/noisy-frozen/noisy-pan behaviour of GF (no still gate): running (gf_*).
- G62 (SA20Q) the bar stays "ants <= source per plane" (today's ants ARE the named failure; the pack's bar is XS
  sub-source calm): GF currently FAILS gfx luma ants (1.78 vs 1.17 %). Locate the tail first: the f1 -> f2 re-code
  (ramp Q 4 -> steady = a ramp-snap question judged by eye) or steady grain following. Output now prints Y ants per
  transition. Ramp frames 0-1 run with no hysteresis (_ramp1 on GF), switched on at f2; check that the switch-on shows
  no snap (change map f1 -> f2 + render). GF gfx f2 Cr -0.95 dB is a chroma fail (chroma-step function).
- G63 windowed hold (_win) vs the NO-HOLD control (cm1_zb2_chp_s16), last-frame NEG:
  noisy pan 0.5 px: 0.5 bpp win 90.40 vs control 90.74; 2.0 bpp win 93.69 vs control 95.35 (the control is flat
  95.3 over 10 frames; win decays) -> the hold FAILS the pre-registered control test (within 0.1) by 0.3-1.7 NEG.
  clean pans: win 93.21/93.68 vs control 93.40/93.70 @0.5 (within 0.2).
  frozen/noisy frozen: win passes (0 changes after the catch-up; noisy frozen @1.0 all blocks exactly 1 change).
  gfx: win 95.98/96.26 = the hold's grain cost (G59).
  The control shows 26.8 % "intermittent" blocks on the clean 0.25 px pan with no hold at all: the intermittency
  count is only meaningful split by source texture (as SA20Q specified); the raw histogram is not a verdict.
  -> Every gated hold costs NEG on noisy slow pans and on grainy stills. GRAIN-FOLLOW (no gate, per-sample
     hysteresis) is the candidate if it holds frozen input (gf_* running).
- G64 GRAIN-FOLLOW (no gate, per-sample hysteresis):
  - frozen10: @2.0 0.00 % changes; @0.5 creep 0.03 -> 0.84 % over 9 transitions;
  - noisy frozen sigma 2: FAIL. The frame step ALTERNATES 22.6/5.66 (period-2 rate-control oscillation), 57-83 %
    changes per frame, Y ants 5.2 % vs source 2.2 % (amplified flicker; per transition 9.0/2.9/7.2/2.4 %...);
  - noisy pan @2.0: 95.11 (control 95.35), Y ants 14.7 % vs source 13.4 %;
  - gfx with ramp1: 96.26/96.68 (< non-ramp GF 96.53 @1.0; today 96.50/96.88).
  STATE OF THE STILL RULE: the gated hold passes frozen/noisy frozen but costs NEG on noisy pans (-1.7) and grain
  (-0.5); grain-follow passes pans/grain but oscillates on noisy frozen. Suspect the oscillation is rate control (a
  fine frame lowers the next thresholds), not the rule -> step slew limit (_sl: +-1 quarter-octave per frame after
  the ramp) on GF, queued.
- G65 (SA20P) GF + slew is admissible as THE still rule if it passes the full battery (simpler; removes the
  per-region HVBC risk). Conditions:
  (a) the slew is ASYMMETRIC: refine <= 1 quarter-octave per frame, coarsen freely (exact CBR at bursts/cuts); fixed.
  (b) a second root of period-2: following noise at a step larger than the noise AMPLIFIES it (lattice
      amplification, pack 3.3 A1). If ants stay above the source, add a block-gated noise-floor term,
      max(kappa Delta_last, k sigma-hat).
  Pulse pass (steady frames, >= 12, per plane):
  - changed-sample share s_t: max/min <= 1.5, lag-2 autocorrelation <= 0.3, no spectral peak at periods 2-8
    above 2x the mean power;
  - step sequence: sign changes of the step <= 20 % of frames;
  - boil/ants <= source on noisy frozen, gfx, cine;
  - frozen: 0 changes after the ramp;
  - pans: within 0.1 of the no-hold control, histogram split by texture;
  - renders.
- G66 SPLIT STILL RULE (SA20Q, SA20P agrees), replacing the noise gate:
  - HOLD only where the block's source is byte-identical to its last write (per-plane 64-bit hash on the encoder
    input, ~13 KB at 8K; at gen 2 the input is the decode, whose held blocks are identical, so the rule fires the
    same); one catch-up per episode, zero change after;
  - everything else (grain, pans, motion): grain-follow with asymmetric slew and kappa-hysteresis, judged by
    sub-source calm;
  - partly frozen blocks fall to grain-follow; the held/GF boundary gets a block-pitch level map + render.
  GF alone fails the frozen bar (creep 0.03 -> 0.84 % = repeated refinement, banned).
  Pre-registered (SA20Q):
  - byte-identical frozen: <= 1 change per sample over the run, 0 after the catch-up;
  - noisy frozen sigma 1/2/3: boil/ants <= source, change share stationary (no period 2-4, trend within +-10 %),
    NEG >= no-hold control;
  - pans: within 0.1 of the control;
  - gfx boundaries.
  Arm _eh (split) queued on all clips (split_*).
- G67 RAIL CLIPS, intra rho 0.42. The rate choice failed on these tiny extreme cells:
  every rate landed on the coarsest step, so this is a worst case.
  - oob 0 everywhere (today on cut24 @0.5 and ext10 @2.0: "EXACTNESS NOT DELIVERED", out-of-gamut samples).
  - CORRECTION of the F1 claim: against a fully rail-free decode of the same picture, 26-76 k samples differ and some
    are farther from the source (AWAY 37-76 k on cut24/ext10, 455 on ext10l1). In the closed loop a clipped coarse
    final predicts its finer samples, so correcting it changes what they become. What holds by construction is the
    per-sample form: every write is clip(P + pred + leaf) and each correction moves that sample toward the source
    (the owner's documented wording); "identical to the clip of a rail-free decode" does NOT hold.
  - near-rail level shift: 8x8 blocks with source mean within 32 codes of a rail average -2.4 (Y) / -3.9 (C) codes on
    cut24 (rail-free +0.9/+0.4), max block error 23-35 codes.
  - owner smudgegroups per frame: ours cut24 Y1 Cb1 Cr1 (5 of 6 frames; Y0 on one), ext10 Y2-3; TODAY cut24 Y1 Cb1 Cr1
    every frame, ext10 Y2-5 -> no worse than today; the groups appear in both codecs on these synthetic extremes.
    Renders (src/ours/today f0) in the bench for the eye.
- G68 split rule (_eh) + slew results (split_*, gf3_*):
  - byte-identical frozen10: ONE catch-up in f2 then 0.00 % changes (@0.5 and @2.0) -> PASS (the ramp frames change,
    as allowed).
  - noisy frozen sigma 2: FAIL. The split arm's step still alternates 22.6/5.66: MY BUG, the region plan's fallback
    search bypasses the slew limit. Pure GF + slew (gf3, no region plan) has no alternation but Y ants 3.7-4.8 % vs
    source 2.2 % = flicker amplification (SA20P's second root) -> needs the noise-floor term.
  - noisy pan: ants 15-16 % vs source 13.4 % (above the source).
  - gfx: 96.26 / 96.68 (today 96.50 / 96.88).
  - cine C031: 91.74 / 96.22 (today f2 94.20 / 96.11).
  Owner record (G67 context): per-region steps must be continuous fields -> the region plan's per-region catch-up step
  is dropped; the next still rule = exact hold (catch-up at the FRAME step) + GF + asymmetric slew + noise floor.
- G69 intra levers at rate:
  - steeper ladder f 0.6 / 0.5: worse everywhere (F003 @1.0 -1.27 / -2.03; A006 -0.55 / -0.76) -> KILLED;
  - kept-sample rounding rho_kept 0.5 (leaves 0.35): A006 +0.33/-0.02/0.00/-0.21, C021 +2.10.., F003 +0.24/-0.22/+0.03/-0.13
    @1.0-2.5 = the best F003 NEG so far, but F003 chroma -2.39/-1.96 @1.0;
  - chroma multiplier at rho 0.42: cm 0.85 / 0.7 lift chroma and lower NEG on A006 (-0.22/-0.76 @1.0) and F003
    (-1.05/-1.38) -> no single cm passes both NEG and chroma on A006/F003 at 1.0-1.5.
  Open: the intra luma/chroma frontier sits ~0.2-1.0 NEG short of today on gfx F003 at 1.0-1.5, whichever
  allocation. Next combination: rho_kept 0.5 + leaf rho 0.42 + cm (nested).
- G70 (SA20P) F003 frontier = the DD4 interpolator on hard edges (linear 4-tap overshoot ~1/8 at steps: big leaves or
  halos that ADM/DLM punish; consistent with kept rounding helping while allocation cannot). Lever (decoder rule,
  0 bits, exact, reads only finals): RANGE-CLAMPED interpolation (RCL=1: prediction clamped to the range of its two
  nearest kept samples). A different mechanism from SA17's rejected TVD limiter (2/6 difference predictor in the
  averaging pyramid); same risk class: flattened fine texture peaks. Pre-registered:
  - F003 NEG >= today @1.0/1.5 AND no natural clip worse by > 0.05 NEG / 0.1 dB per plane;
  - texstat per plane; full-res renders of text edges and fine texture;
  - if natural clips lose, a continuous edge-strength weight as a fixed curve.
  Running at rho 0.42 on F003, A006, C021, B001.
- G71 (SA20Q) next pre-registrations:
  (a) GF noise floor: a leaf fires iff |x - P| > max(dz Delta, kappa Delta_last, k sigma-hat(level)), k_kept = k + 1
      (fired kept samples move interpolated neighbours). Monotone sweep k in {1.5, 2, 2.5, 3} on noisy frozen sigma
      1/2/3 (12 f) and pans. Pick the SMALLEST k with ants and boil <= source per plane and a stationary change
      fraction; pans: textured-block lag <= ceil(k sigma / (g v)) + 1, intermittent <= 1 %, within 0.1 NEG of the
      control. If no k passes both, report the two curves as a measured conflict.
  (b) rail rerun: match today's ACTUAL coded bits per frame (7 owner rates, 12 frames), per plane oob/PSNR/smudge,
      >= 10-generation chains.
  (c) never-away definitional flag: in the closed loop a clipped final changes the PREDICTION of later samples
      (coded, not moved). Measure the error of samples downstream of clipped samples vs same-level samples elsewhere,
      per plane, on cut24/ext10. No excess -> the per-sample form stands; excess -> a legality-caused away effect to
      fix at the root.
- G72 (G71c) downstream-of-clip error, mean |error|, ours vs clip of the rail-free decode on the SAME samples:
  cut24  Q8 Y 0.39 vs 0.62, C 0.75 vs 0.79 | Q32 Y 1.69 vs 1.99, C 2.57 vs 2.71 | Q128 Y 17.91 vs 21.87, C 23.27 vs 24.44
  ext10  Q8 Y 0.47 vs 0.54 | Q32 Y 1.94 vs 2.48, C 0.25 vs 0.50 | Q128 Y 11.34 vs 19.28, C 0.00 vs 3.50
  ext10l1: none / equal.
  -> excess is NEGATIVE in every cell and plane: clipping inside the loop IMPROVES the predictions it feeds; no
     legality-caused away effect in aggregate. The per-sample form stands (single samples can still land farther
     than the rail-free clip, G67; on average they land closer). The higher error near rails vs elsewhere is equal
     in both decodes = content, not legality.
- G73 intra @1.0/1.5, NEG vs today:
  range-clamped interpolation (rho .42): F003 -1.08/-0.45 (worse than rho .42 alone, -0.70/-0.25); A006 -0.22/-0.26;
    C021 +2.17/+1.41; B001 +0.38/+0.21 -> fails its pre-registered pass (F003) -> KILLED.
  kept rounding 0.5 + leaf rho 0.42, cm1 (BEST so far): A006 +0.41/+0.05, C021 +2.17/+1.39, F003 -0.28/-0.09;
    chroma still behind on A006 (Cb/Cr -0.88/-1.88 @1.0) and F003 (-0.66/-0.17). cm0.85: chroma nearer, NEG lower.
- G74 noise-floor sweep (G71a) launched: grain-follow (no still gate) + asymmetric slew + ramp1; a leaf fires iff
  |residual| > max(dead zone, kappa x last-write step, k sigma-hat), with k+1 on the kept grid; k = 1.5, 2, 2.5, 3
  on noisy frozen sigma 2/3, noisy pan and clean 0.25 px pan (10 frames, 0.5/2.0 bpp).
- G75 noise-floor sweep, interim (k = 2, 3; grain-follow + asymmetric slew + ramp1):
  - noisy frozen sigma 2 @0.5: k=3 boil 0.44 (src 2.26), ants 1.68 % (src 2.22 %); k=2 boil 0.84, ants 3.27 %.
    BUT the per-transition ants TREND upward (k=3: 0.05 -> 1.51 %) because the frame step keeps refining one
    quarter-octave per frame (32 -> 6.7): held frames cost almost nothing, so a finer step always fits = slow
    repeated refinement (the banned creep class; fails the stationarity bound).
  - noisy pan: ants 15.1 % vs source 13.4 %; clean 0.25 px pan: ants 6.8 % vs 2.9 %.
  Principle added (_qn<c>): no frame step below c x the source noise (median luma sigma-hat): quantising finer than
  the grain only re-codes grain. Queued at k = 3 with c = 2, 3 (queues/q_qn.sh).
