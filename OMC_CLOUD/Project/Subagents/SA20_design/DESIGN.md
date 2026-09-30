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
