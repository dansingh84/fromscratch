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
