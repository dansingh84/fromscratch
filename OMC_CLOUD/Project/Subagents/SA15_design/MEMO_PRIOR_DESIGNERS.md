# What three earlier from-scratch designers found (SA12, SA13, SA14) — hints, not a recipe

Coordinator, 2026-09-28. Three designers worked in parallel on the same brief you have, 2026-09-27/28. They were stopped because progress stalled: all three got stuck on the same problem, and a stalled round is quota waste. None of their designs passed.
Everything below MIGHT work but did not fully. Use it as evidence of what was measured, not as parts to assemble.

Full records:
- Ledger `Codec/Current/LEDGER_SANDBOX_v2.md`, entries S5.349–S5.369 (grep `^### S5.36`).
- Their sandboxes, readable but DO NOT modify: `Subagents/SA12_design/` (DESIGN.md … DESIGN_v5.md, notes/seq.py, notes/hf.py, out/), `Subagents/SA13_design/` (DESIGN.md, DESIGN_v2.md, NOTES.md, t1–t10 scripts and results, renders/), `Subagents/SA14_design/` (DESIGN.md, DESIGN_v2.md, NOTES.md, notes/, renders/).

All of their numbers come from numpy MODELS: entropy rates, sometimes multiplied by a static-tANS overhead factor of about ×1.13–1.16 at 0.4–0.5 bpp and ×1.04–1.07 at 0.8–1.7 bpp. They are not coded bitstreams. "Today" means today's OMC real decodes (`Subagents/SA7_legality_v2/out/DM/*_a0.d.yuv`, and `.work/v537` binaries, read-only).

## A. THE PROBLEM THAT STOPPED ALL THREE — slice boundaries (the owner treats this as a disqualifier)

The owner's rulings on this (2026-09-28, ledger S5.369):
- A from-scratch design may NOT solve one problem by creating another somewhere else.
- It may NOT patch its own side effects.
- An artifact the design creates disqualifies the design CHOICE that creates it.
- Required: no row position is special by construction. Proof = identical per-row error statistics at every row phase of a slice, on intra and inter frames, in Y, Cb AND Cr.

What each tried:
- **SA12 (CLP-1) — causal slice cut.** Each 16-row slice (8 at 720p) is transformed on its own. The top reads the decoded rows above; the bottom uses linear extrapolation, with no mirror and no blend.
  - Cause of the step, proven: the causal slice cut. Lossless coarse bands still leave +0.09–0.10. One tall slice gives +0.01, against +0.16 at 16 rows.
  - Inter slices, with OBMC plus encoder-only "error continuation": excess (Y/Cb/Cr, boundary step minus internal half-slice step) +0.04/+0.03/+0.06, against today's +0.15/+0.14/+0.30.
  - Intra slices (first frames, cuts, the moving refresh group) stayed at about today's level: +0.16/+0.18/+0.32 on spot 1080p at 16 rows.
  - Everything tried on intra failed:
    - below-context;
    - "legal anchor bracketing": step worse, +7–11 % bits;
    - 8-row slices: +4 % bits, −0.9 NEG, step not smaller;
    - error continuation on intra: cuts ¼–⅓ of the step, costs 0.4–1.1 NEG, and is a symptom treatment;
    - a transform crossing one slice boundary with a one-slice delay: ~50 lines at 1080p against JPEG XS ~32 → latency parity broken, weaker loss containment.
- **SA13 (BSC-1) — bracketed slices.** Each slice codes its LAST row first as a 1-D anchor; interior rows are a vertical 5/3 between two decoded endpoints (the slice above's anchor and its own). There is no row below, no mirror and no blend.
  - At 16 rows the boundary rows were flat in Y/Cb/Cr, with 0 smudge groups.
  - At 8 rows the anchor row showed +7…+23 % mean |error| over mid rows on inter frames (dng1080 Cb). The designer proposed tuning the anchor's step per slice height. That is a knob patching a design-created row.
  - Latency 3S lines: S = 8 gives 24 lines.
  - Three transform passes worst case.
- **SA14 (NEST) — "shifted causal slices".** Each slice starts on a predicted row whose top neighbour is the slice above's final row.
  - The row ratio beat a mirror: spot 1.05 against 1.38.
  - It CREATED a new artifact: the first predicted row cannot update the finished row above, so its detail synthesis gain is 7/8 instead of 3/4. Error moves onto rows 0–1: dng +3…7 % in Y/Cb/Cr.
  - The two fixes it and I proposed were both patches:
    - a half step on that row: +4–5 % bits;
    - holding one row back.
- **Earlier, by the coordinator** (DESIGN_FROM_SCRATCH, falsified S5.349), a continuous vertical transform, with slices as rate and packet units only:
  - lookahead 5/3 2V: 9 lines; 3V: 21;
  - 720p50 4:2:0 misses 1 ms with conversion;
  - +3–4 Mbit state at 8K;
  - one lost packet damages neighbouring slices;
  - it resembles the JPEG XS architecture.
- **Vertical-causal coding** (each row predicted from the reconstructed row above, horizontal transform of the residual; S5.353/S5.356/S5.358):
  - −0.3…−1.2 dB, chroma worst;
  - exact only in a variant costing 3–19× the work;
  - a +1-code cast.
- **Root chain as far as it was traced:** step ← edge rows have a one-sided or extrapolated vertical neighbour ← each slice is a closed vertical-transform unit ← slices are the units of loss containment, rate control and the rolling intra refresh. Nobody solved it at that root within latency parity and loss containment.

## B. LEGALITY (every output sample in range, no clip destroying information)

- **The cycle argument** (S5.349): legality by clamping inside the synthesis needs every clamp interval to depend only on final values.
  - A symmetric update that reads CLAMPED/final samples makes the graph cyclic.
  - Acyclic one-sided updates reduce to predict-only: −2.4…−4.8 dB, chroma worst. FALSIFIED.
- **SA14's leaf-reading lifting refutes the premise:**
  - Every update step reads TRANSMITTED (dequantised, unclamped) coefficient values, never clamped samples.
  - So each predicted sample's legal window depends only on final values, and the synthesis is acyclic WITH the full symmetric 5/3 update.
  - The separable 5/3 is rewritten exactly so that all four bands are coded coefficients.
  - Measured within ±0.5 % BD-rate of the separable 5/3 on every plane (dng, spot, floor, cf_gfx).
  - The coordinator rated this the strongest idea of the round.
- **SA14 rails:** a sample exactly on the legal bound is coded as a RAIL± symbol with a fixed update value.
  - Synthetic rails: +4…9 dB, −38…65 % context bits against the same model with no rails.
  - BUT on a real frame graded 2.5× into both rails at D0 = 128: +10.9 % context bits. That is a legality bit cost, not allowed.
- **SA14 v2, injective dequantisation (IDQ):** an index beyond a sample's window decodes one-to-one to an unused off-lattice value inside the window. Every index set is then legal and exactly recoverable, and the encoder is one pass.
  - Needs step ≥ 2: +0.2–1 % BD at the highest rates.
  - The half-legal-range injectivity condition is not proven per plan.
  - FAILED the owner's rule "legality may never harm the image": a larger overshoot decodes further inside, and ~107k samples moved AWAY from the source (against 300k toward), with horizontal streaks on rail edges.
- **SA12:** per-pair interval clamps in a Haar-pair pyramid (exact sum + half-difference, half-difference predicted from final neighbouring lowpass).
  - 0 out-of-range; 216/216 synthetic rail stress cases g2-exact (8/10/12-bit, full, limited and SDI range).
- **SA13 REXT:** every encoder maps rail samples M outside the range before the transform; the decoder runs ≤ 1 in-cell projection round.
  - Fails exactness on dense full-range rail steps (cut24: 0↔1023 plates against ramps): 0/162 units converge in 200 rounds.
  - Every exact alternative needs iteration or costs 30–75 % bits; the lossless fallback reaches 3.7 bpp.
  - The owner rules out iteration: "not a codec, that's a medieval painting". At most one predetermined re-choice.
- **Today's in-cell projection** (4 rounds, S5.338–S5.342): exact on natural content, quality = clip, 0 bits. It stalls on dense rails, and 4 rounds are already more work than allowed.

## C. GENERATION EXACTNESS (byte-exact through CBR and baseband hops, image only)

What held across designers:
- Canonical decisions read from the RECONSTRUCTION:
  - plan by step divisibility or cheapest exact reading;
  - intra/inter by which description reproduces;
  - motion vectors DERIVED BY EVERY ENCODER from decoded frames and TRANSMITTED. The decoder never derives: decoder-derived vectors failed loss recovery long ago (S5.29).
- Gen 1 emits what the canonical rule returns on its own reconstruction.
- **Mid-stream join (SA12, S5.366/S5.367):**
  - Interleaved refresh FAILED.
  - This worked: a contiguous top-down refresh sweep, plus clean-region rules (a refreshed region reads only clean rows: reference rows, OBMC neighbours, below-context, vector derivation), a wrap rule, and gen-1 self-read ("intra whenever intra of own reconstruction reproduces").
  - Result: spot 1080p, joins at frames 3 and 7, pictures and streams byte-identical from frame 15.
  - The clean-region rules cost ≈ 0.2 NEG and chroma −0.1/−0.2 dB on spot (unresolved).
- **Still input** (a repeated frame; today changes 60–77 % of samples every frame, S5.335):
  - SA12: 0.000 % changed samples through the refresh;
  - SA14: 0 changed samples from frame 1, the refresh re-describing exactly with no pop;
  - SA13: ≤ 0.03 %, with an inter dead zone of 1.25Δ and a zero-vector preference.

## D. EFFICIENCY (must not be noticeably worse than today; VMAF-NEG first, PSNR Y/Cb/Cr second, eye decides)

- **SA12, coded-rate estimates against today's real decodes:**

| Cell | SA12 | Today |
|---|---|---|
| dng720 | 0.5 bpp: NEG ≈ 91.3, PSNR 37.34/36.35/37.53 | 90.16, 35.22/36.10/37.14 |
| highwaydriveL | 0.491 bpp: 93.92, 42.08/47.84/44.38 | 0.504 bpp: 93.73, 41.05/47.31/43.90 |
| spot, with the clean-region rules | 0.5 bpp: 93.83, luma +1.4 dB, chroma −0.12/−0.22 dB | 93.76 |

  Chroma flatness at 0.5 bpp: intra fix via chroma level-1 step ×√2 + an 11/16 rounding offset. Inter chroma flatness was already better than today.
- **SA14, estimated:**

| Cell | SA14 | Today |
|---|---|---|
| dng720, "tilted" plan (low bands 1–3 octaves finer) | 0.52 bpp: 90.89, 35.63/36.05/37.25 | 90.16 |
| spot, untilted | 0.53 bpp: 94.72 | 93.76 |

  The untilted plan on dng720 needed ~48 % more bits: the plan matters more than the structure, and two different plans on two cells = not a canonical rule.
- **SA13:** loses on dng, −2.8…−6.0 NEG at 0.5–1.0 bpp, chroma −1.0…−1.2 dB; beats today on spot, +0.3…+0.8.
- **Flatness bar** (zero flat textured blocks at ≥ 0.5 bpp): met by NO design and not by today's codec.
- **JPEG XS NEG at 0.5/1/2 bpp:** dng720 72.1/89.3/94.8; spot 87.7/96.6/98.8.

## E. ARTIFACTS MEASURED AS SOLVED IN THE MODELS (not yet in one design together)

- **Owner's marked grille (720p f2/f8/f11), SA12:** bright/dark 8×8 classes 0 % against today's 12.9 %/13.9 %; luma error 15.7 against 34.6.
  - These figures were LUMA-ONLY; chroma was not reported. Treat as incomplete.
- **Dark-area colour cast:**
  - SA12: within ±0.08 code, against today's +0.22 Cb / −0.15 Cr.
  - SA13: fixed with half-to-even rounding and the DC band at cell centre.
  - SA14: parity rounding removes a +0.6-code cast.
- **16×16 motion blocks** made a grid (+0.162); OBMC removed it (SA12).

## F. REVIEW LESSONS (why rounds failed review)

1. Luma-only results. The owner: "we never only look at luma" (three corrections). Every number and render per plane.
2. Efficiency claims without artifact checks are not evidence. HVBC was efficient because it let artifacts through.
3. Parts tested separately never combined in one model: SA14's slices, legality and temporal path were never run together.
4. Per-cell tuned plans: one canonical, causal plan rule for everything.
5. Fixes for the design's own side effects are patches. They disqualify the choice underneath.
6. 8×8-mean level maps cannot show a one-row step: a render must magnify the smallest feature to ≥ 4 output pixels.
