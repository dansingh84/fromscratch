# To Team A — OMC status letter, rev. 2 (v3.1)

Date: 2026-07-27. Supersedes the response memo you received with v2
(`docs/FEASIBILITY.md`, which remains the normative rate-feasibility analysis).
Governing spec: `PROJECT_CONSTRAINTS.md` rev. 4.

## 1. What changed since your evaluation

Your memo's central findings were accepted and acted on rather than argued with:

1. **"Half holds only at one threshold"** → the mandate holder amended the constraint
   (rev. 4): the pipe is fixed at **0.50× JPEG XS on every frame, no exceptions**, and
   quality is judged at that pipe — worst frame first, eyes decisive. The codec now
   holds an exact-CBR 2.0 bpp pipe (measured XS reference: 4.0 bpp at 4:2:2 *and*
   4:4:4 for corpus-wide VMAF ≥ 97): stream ≡ 32 + n·F bytes, every frame exactly
   F bytes, prefix-bounded slices inside the frame.
2. **"Temporal prediction is the right lever"** (your colleague-review point) →
   implemented (v3, rev. 3 of the constraints): per-band intra/inter against the single
   previous reconstructed frame, rolling intra refresh (default R = 8), 2-frame
   invisible ramp at stream start and cuts, steady state judged from frame 2.
3. **"Chroma starvation"** → the delivery configuration codes with the plane-fair
   allocation (equal ladders, MSE rounding); the luma-weighted tables are an explicit
   `--tune vmaf` opt-in, not the default.

## 2. Current measured state (all at the 0.50× pipe, 4:2:2, delivery config)

- **Corpus (your reproduction set):** frame 0 (ramp) VMAF 96.66–97.24 against a
  first-frame self-ceiling of 97.43; frame 1 ≥ 97.46; steady frames 97.16–100.
- **64-frame program feed** (4 shots × 16 frames, 3 hard cuts, built from the customer
  footage — construction script `harness/build_program.py`; static shots ping-pong
  genuinely captured frames so every delta is a real camera delta; pan shots are
  rigid single-capture window pans):
  - worst steady frame VMAF **97.11**, VMAF ≥ 97 on every steady frame;
  - at equal bits OMC beats JPEG XS on **every shot and every measure** — worst
    steady frame 97.11 vs 96.59 VMAF (+2.2 dB Y, +1.8 dB Cb, +1.0 dB Cr); on the
    pans the luma lead is +2.5 dB (fence) and +4.1 dB (cow) with VMAF 98.9–100.0;
  - vs XS at 4.0 bpp (double the pipe): VMAF within 0.67; PSNR on grain content sits
    at the entropy-floor distance documented in FEASIBILITY.md — that bound binds any
    codec of this class, including XS itself at 2.0 bpp.
- **Worst-frame flicker guards (measured, not assumed):** refresh-pulse period-8
  amplitude ≤ 0.10 dB luma / ≤ 0.015 VMAF on every shot; borrow–payback oscillation
  structurally impossible (banking is in-frame only; every frame closes at exactly
  F bytes); ramp monotone at start and after every cut.
- **Generations (A4):** encode→decode chains, generations 2–5 byte-identical to
  generation 1, including with the motion search live on panning content.
- **Loss (A5):** slice loss is row-contained on every subsequent frame; decode is
  bit-identical to the clean run within R frames (verified at R = 2 and R = 8).
- **Latency (A2):** deterministic 0.16–0.78 ms across 720p50…8K60 (docs/LATENCY.md).
- **Formats:** 10/12-bit, 4:2:2 + 4:4:4; 12-bit real content, a PQ-statistics HDR
  stress (dark-region PSNR ≥ 51.8 dB, PQ dark-ramp max step 1), and an 8K canvas all
  pass rt=0 + exact CBR (`harness/hdr8k_tests.py`).
- **Section G:** full-frame human review at the delivery rate found none of the six
  artifact classes; the gallery ships with the code so you can repeat the review —
  per Section E that review, not the numbers above, is the verdict.

## 3. v3.1 — motion capability and an honest trade-off

The bitstream (v3.1, normative spec `docs/BITSTREAM.md`) now carries four per-region
motion vectors per slice in half-pel units; all interpolation taps are shifts/adds
(C3). Two encoder postures:

- **Default:** one global integer vector per slice (the v3.0 search). Metrically
  identical to v3.0 (worst per-frame delta −0.02 dB on the program feed) and
  **byte-exact across generations** — this is the delivery configuration.
- **`--mv-regions` (opt-in):** per-region + half-pel override search. Buys +1.8 dB on
  divergent multi-object motion and +0.7 dB on true fractional pans, but measured
  re-encode chains accumulate loss (51.5 → 47.7 dB over 4 generations): decision
  thresholds on noisy SAD surfaces cannot replay byte-exactly, and the half-pel tap is
  a low-pass. It is therefore **off-spec for multi-hop chains** and documented as
  single-hop-only (`docs/DESIGN.md` §1b). We chose to ship the capability with its
  cost stated rather than hide either.

Also frozen: the normative tANS tables. A retraining pass on a broadened corpus
(temporal-delta statistics, the program feed, ramps, and a transform mirror corrected
to the shipped (9,7)-M levels) coded the broadened training set 0.05% *worse* than the
shipped tables — they generalize, and they are now frozen
(`harness/train_tables3.py`).

A film-grain-synthesis mode was evaluated and **not** built: it conflicts with the
zero-artifact rule (synthesized grain is not the signal), collapses full-reference
fidelity, and breaks A4. Decision record: `docs/DESIGN.md` §6b.

## 4. What we ask of Team A

1. **Run the in-motion review.** `delivery/clips_5s/` in this repository holds
   16 five-second clips — each program shot four ways (source, OMC @ 2.0 bpp,
   XS @ 2.0, XS @ 4.0), lossless 10-bit wraps of the actual decoded outputs, with
   the shot repeated *inside* each file so every cut-like join and every steady
   stretch is judged mid-playback, free of any player-loop confound. Start with
   `delivery/clips_5s/CLIPS_MEMO.md`: it documents the construction, the fidelity
   claim and its verification command, playback requirements (desktop VLC/mpv —
   no phone hardware decodes this profile), and the review protocol. The question
   the numbers cannot answer is whether the softening on grain content is visible
   in motion. That verdict is yours and the mandate holder's.
2. **Reproduce at will.** The repo is self-contained: `make test` runs the unit gates;
   `python3 -m pytest tests/test_acceptance.py` runs the 8 acceptance gates;
   `harness/` rebuilds every number in this letter (XS reference sweep included,
   using your own SVT build and VMAF binary as before).
3. **Send real continuous-motion footage.** The program feed's motion is windowed from
   stills (labeled as such throughout). The one open evidence gap is genuinely
   captured 25–50-frame motion/cut clips for the definitive worst-steady-frame and
   real-time ramp verdicts; the harness protocol is ready.

— OMC engineering


---

# Addendum - v4 (bitstream 4.0), for your rebuild and review (2026-07-27)

Since your second evaluation, the mandate was restated by its holder
(constraints rev. 5 then rev. 6 - both in PROJECT_CONSTRAINTS.md): the test
is OMC @ R vs JPEG XS @ 2R at every useful R, judged by blind full-frame
viewing; PSNR and VMAF are demoted to diagnostics. Your finding that v3.1 is
a parity codec on metrics stands unchallenged - v4 does not dispute it, it
changes what the codec spends the eye's error budget on.

**What v4 is:** zero-coded detail coefficients in flagged bands reconstruct
as animated quarter-step grain (normative fill, BITSTREAM.md 4.6) instead of
flat zero - the measured sub-threshold texture energy is kept, its exact
realization (which the eye cannot verify) is not. In-loop, deterministic,
rt = 0, generations 2-5 byte-exact (the generation lock now verifies
bit-exact reproduction per slice before locking - A4 is checked, not
argued). PSNR drops ~0.05-0.8 dB by design.

**For your rebuild:** bitstream major version is 4 (48-byte slice headers).
BITSTREAM.md was substantially hardened after an independent decoder was
written from the spec text alone and brought to byte-exactness - the
rolling-reference semantics (4.2b), exact lifting arithmetic and reflection
(4.1), and tANS table construction (4.5) are now normative text; your own
implementation-from-spec is the strongest check we could ask for.

**What we ask:** (1) run the blind kits in delivery/abx_kit/ - three ratio
anchors (2.0-vs-4.0, 1.0-vs-2.0, 1.6-vs-4.0), sealed keys, size-padded
pairs; (2) send - or run yourselves and report - the real captured
continuous-motion material from your second evaluation: grain behavior under
real motion (does predicted grain visibly ride objects within the 8-frame
refresh?) is the one question our corpus structurally cannot answer; (3) the
fill-safety stress suite (harness/build_stress.py: text crawls, star fields,
graphics; REPORT 11f) is reproducible if you want to attack the fill's
gates - we found no leakage; you may find what we did not.

- OMC engineering


---

# Addendum 2 - how the rate claim should be stated (2026-07-28)

Your metric findings and ours now agree end to end, so the claim language
should be pinned down before anyone repeats it to a customer. The honest
formulation is conditional, and we ask you to ratify it in this form:

- **Under instrument-defined quality** (VMAF/PSNR acceptance gates): OMC is
  a 25-40% rate saving in Fidelity mode - ~25% under mean-VMAF gates,
  compressing to 10-15% under worst-frame gates set at the grain entropy
  floor, where both codecs' rate-quality curves flatten together
  (measured, both codecs, same harness: REPORT.md 12f). At every equal
  rate measured OMC scores above JPEG XS; generation exactness and motion
  behavior come on top.
- **Under viewer-defined quality** (blind viewing): ~50%, with the sealed
  kits in delivery/abx_kit as the acceptance procedure itself - your
  viewers, your verdict, no metric arguments.

We will not argue that JPEG XS should be evaluated below its own operating
rate - that line of argument concedes the reference and contradicts the
claim's premise. Either definition above stands on its own measurements.
What we ask of the mandate holder, through you: an explicit decision that
the eye-judged definition is the one the product leads with, with the
instrument-defined number stated alongside it - because the market's
engineers may insist on the instrument definition, and that is a
positioning decision, not an engineering one.

- OMC engineering
