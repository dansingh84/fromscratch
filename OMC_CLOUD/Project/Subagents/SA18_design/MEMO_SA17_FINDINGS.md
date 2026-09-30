# What designer SA17 ("CPV-1", Opus 5.5, with ideation partner SA17P) found: successes, failures, HOW each came about, what was falsified

Coordinator, FINAL, 2026-09-29 13:30 EDT. Written from SA17's final report.

**Sandbox:** `Subagents/SA17_design/`. Read it; do NOT modify it.
- `DESIGN.md` §0–12, with a root-cause chain for every choice.
- `RESUME.md`: the item table and the rejected list.
- `model/`, and `out/` (`eval_final.log`, `eval_wave.log`, `eval_oneway.log`, chain logs, `art/`).

**The partner's notes:** `Subagents/SA17P_partner/PARTNER_NOTES.md`.

**Ledger:** S5.376–S5.382.

**Basis of all numbers:**
- numpy model at REAL code lengths;
- static tables trained on 5 clips disjoint from the test cells;
- exact CBR;
- steady frames 2–11;
- compared against today's REAL decodes.

**Status:**
- **Stopped** by the owner's stall rule. SA17 left goal 4 and "never away" as failures labelled "price of no flicker" and "structural".
- **The closest design so far:** first on legality, exactness, still areas and loss recovery.

Treat this as evidence, not a design to continue.

---------------------------------------------------------------------------------------------------
## 1. The design (final)
- **Transform:** a continuous pair pyramid (mean + predicted difference), 2 vertical × 5 horizontal levels, over the whole picture. Slices are rate and packet units only.
- **Legality:** each pair is written last from a final mean plus a leaf, with the leaf clamped into its legal set.
- **Exactness:** the encoder emits the canonical reading of its own picture.
- **Temporal:** value-domain prediction; vectors derived by every encoder from decoded history (D(t−1) vs D(t−2)) and TRANSMITTED.
- **Refresh:**
  - PRIMARY: on-demand heal over the return path (owner ruling S5.37).
  - One-way links: a 2-frame column wave (owner ruling: under 4 frames).
- **Still areas:** an encoder-only hold rule. A zero-vector coefficient is refined once when it becomes still, then held unless the source moves by more than ¾ of that step; unspent bits become padding.
- **Entropy coding:** static tANS tables keyed by step bucket.
- **Exact CBR:** a 16-bit reserve per slice.

## 2. SUCCESSES, and how each came about
- **S1. No seams or smudges.**
  - smudgegroups finds 0 groups on Y, Cb and Cr on all 12 decodes.
  - Owner rowphase spread on dng: Y 0.5–1.2 %, Cb/Cr 2.5–7.1 %, against today's Y 3–13 % and Cb/Cr 18–39 %. See F3 for the remaining chroma signature.
  - How: a continuous transform with disjoint pair support; slices are not transform units.
- **S2. Legality:** 0 out-of-range samples everywhere, including the rail cells cut24/ext10 at 0.25–2 bpp, with zero bits spent on it.
  - How: leaf-interval clamps from final values (the SA15 mechanism).
- **S3. Exactness:** generations 2 and 3 identical in pictures AND bits on every frame tested (dng720, spot, rail cells).
- **S4. Still areas: SOLVED on still content.**
  - Frozen input: 0 samples change on Y, Cb and Cr from frame 2 on.
  - Mixed clip, beyond 40 rows / 160 columns of the moving object: Y 0 %, Cb/Cr ≤ 0.011 % per frame.
  - Inside that margin: a chroma halo of 0.6–1 % per frame.
  - How: the hold rule above. Its cost is up to 1.7 NEG on static content (training clip city), and see F1.
- **S5. Loss recovery with a return path: exact heal at frame t + RT + 1.**
  - 3 damaged frames at RT = 2; 2 at RT = 1.
  - Confirmed on dng720, spot, volley (8 slices lost) and dng1080 @1.0 (4 slices lost).
- **S6. One-way links:** a 2-frame cycle gives 2–3 damaged frames, under 4. A 3-frame cycle gives 4 and fails. Cost: 1.0–3.4 NEG below the return-path mode.
- **S7. Efficiency facts established:**
  - (a) **The transform price is 0.** Pair against 5/3 at real code lengths: hwy 91.69 vs 91.47, floor 93.65 vs 93.88 NEG. The entropy-proxy screen had wrongly suggested +2–6 %.
  - (b) **Table pooling was the big loss.** Entropy tables pooled over all step sizes cost +48 % class bits; the fix is to key the tables by step.
  - (c) **The rolling wave costs 0.8–1.0 NEG.** Hence on-demand refresh is primary.
- **S8. Exact CBR:** 0 prefix violations and 0 over-budget slices with the 16-bit reserve (measured excess ≤ 5.5 bits; not proven).

## 3. FAILURES, and how each came about
- **F1. Goal 4: NEG below today on 8 of 12 points.** Return-path mode; NEG mean (worst) mine vs today, then PSNR Y/Cb/Cr:

| cell @bpp | NEG mine (worst) | NEG today (worst) | Δ NEG | PSNR mine | PSNR today |
|---|---|---|---|---|---|
| dng720 @0.5 | 88.97 (88.10) | 90.16 (87.22) | −1.19 | 34.43/36.12/37.22 | 35.22/36.10/37.14 |
| dng720 @1.0 | 94.25 (93.17) | 94.05 (92.31) | +0.20 | 38.43/37.01/38.27 | 38.19/37.08/37.95 |
| dng1080 @0.5 | 90.25 (88.56) | 91.08 (87.51) | −0.83 | 35.05/34.73/35.98 | 35.32/34.67/35.75 |
| dng1080 @1.0 | 94.04 (92.36) | 93.51 (91.77) | +0.53 | 37.12/35.53/36.73 | 36.91/36.04/36.74 |
| spot @0.5 | 94.41 (90.76) | 93.76 (87.10) | +0.65 | 39.89/42.52/46.38 | 39.54/42.80/46.31 |
| spot @1.0 | 97.72 (94.34) | 97.53 (95.03) | +0.19 | 43.42/44.43/48.10 | 42.94/44.79/48.16 |
| floor @0.5 | 95.32 (91.47) | 95.98 (92.41) | −0.66 | 40.35/44.99/44.58 | 40.71/44.73/44.31 |
| floor @1.0 | 98.15 (94.46) | 98.59 (94.94) | −0.44 | 42.32/46.32/45.89 | 42.60/46.01/45.48 |
| hwy @0.5 | 92.96 (89.73) | 93.73 (90.58) | −0.77 | 40.78/47.76/44.11 | 41.05/47.31/43.90 |
| hwy @1.0 | 96.52 (93.37) | 97.29 (94.13) | −0.77 | 43.75/49.09/45.39 | 43.90/49.00/45.36 |
| volley @0.5 | 91.17 (90.08) | 92.37 (90.83) | −1.20 | 39.57/42.67/45.29 | 41.28/43.36/45.90 |
| volley @1.0 | 95.21 (94.28) | 95.62 (94.70) | −0.41 | 44.50/45.39/48.20 | 45.20/45.63/48.10 |

  - Losses concentrate on fast motion (floor, volley, hwy: the cells where OMC must beat JPEG XS) and at 0.5 bpp.
  - **The owner's artifactmap finds MORE luma regions than today at 0.5 bpp,** dense error groups on fine text and textured still content: dng1080 42 vs 9, dng720 29 vs 10, spot 5 vs 1, volley 12 vs 0. Chroma is 0.
  - How, per SA17:
    - (a) The still-hold rule freezes still content at the step it had when it went still, costing up to 1.7 NEG on static content. It is SA17's price for no flicker, and a design-created cost by the owner's rules.
    - (b) Fast motion: the cause was NOT found. Ruled out: vertical search reach (±8 changed nothing, ±0.02); zero-vector tolerance (0/1 gives only +0.05–0.13 and brings flicker back); a level-1 rule-based "investment" (−0.85 / −0.02).
- **F2. "Never away" (goal 2): NOT met.** The clamp keeps the pair mean, so the partner sample moves by the overshoot. On dng720 @0.5, 1,817 of 3,376 changed samples (about 54 %) move away from the source, by up to 136 codes; up to 75 % on the ext10 rail cell.
  - SA17 argues in DESIGN §3.2 that no exact design with a lowpass can avoid this. The coordinator and the partner do NOT accept that as proven.
  - The partner's "one predetermined re-choice of the parent mean's rounding near rails" was NOT built; SA17 said it only moves neighbours.
  - Plane MSE is still lower than a plain clip.
- **F3. Row signature:** 2 vertical pair levels leave a 2.5–7 % pattern in chroma at 0.5 bpp. One vertical level removes it but costs −1.8 dB.
- **F4. Encoder mid-stream join in return-path mode:** no guaranteed convergence.
- **F5. Not done end to end:** formats other than 4:2:2 10-bit. Latency (18 lines at 720p, 26 at 1080p–8K) and memory (about 22.7 Mbit at 8K 4:2:2 10-bit; 8K 4:4:4 12-bit tight) are paper figures.

## 4. Built and REJECTED by SA17 (with reasons; do not retry without a new reason)
1. Continuous 5/3 vertical: 5–15 % chroma row-phase signature.
2. Plain output clip plus reading back (any update-lifting transform): gen-2 misses on rails.
3. Predict-only or per-sample-leaf structures: +12…60 % bits.
4. Pair lowpass updates, 2/10 predictor, (9,7)-M: no gain.
5. Cell-bounded clamp in 5/3: misses are unbounded near rails.
6. TVD slope limiter: −1.3…−2.8 NEG.
7. Rail-conditional limiter for "never away": no reduction; ext10 worse.
8. 1 vertical pair level: −1.8 dB intra.
9. Spatial refinement sweep for still areas (partner's idea): a wait longer than the 2-frame ramp.
10. Vertical search ±8 / ±16: no gain.
11. Level-1 rule-based investment for motion: −0.85 NEG.
12. A 3-frame one-way cycle: 4 damaged frames, which fails the bar.

## 5. What the evidence of all six designers suggests (hints only)
- **What has been SHOWN ACHIEVABLE** (evidence, NOT a template; a new design should find its own way and may use none of these parts):
  - pair-pyramid continuous transform (no seams, transform price 0);
  - leaf-interval legality (0 out-of-range, exact);
  - canonical emission (gen 2 and 3 exact);
  - value-domain prediction with transmitted history vectors;
  - on-demand heal (RT + 1 frames);
  - step-keyed static tables.

  Owner, 2026-09-29: designers must design FROM SCRATCH; repairing SA17's design is patching and loses innovation.
- **Open problem 1 (efficiency):** detail loss at 0.5 bpp on text and textured still content, from how still content is held, plus an unexplained fast-motion deficit.
  - Today's codec wins there with perceptual allocation and texture rounding bias; these are design elements, not knobs.
  - Still areas must stay at zero change: flicker is forbidden.
- **Open problem 2 ("never away"):** the pair-mean-preserving clamp moves the partner away from the source. The claim that this is unavoidable is unproven.
- **Open problem 3:** the chroma row signature of the 2-level vertical pair (2.5–7 %).
