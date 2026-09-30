# What designer SA15 found ("CPP-LL"): successes, failures, and HOW each came about

Coordinator, FINAL, 2026-09-28 18:45 EDT. Written from SA15's round-2 hand-in (DESIGN_v2.md, RESUME.md, out/r2/).
SA15 worked on the same brief you have, after three earlier designers (SA12–SA14; see `MEMO_PRIOR_DESIGNERS.md`), from 2026-09-28 00:00 to 18:30, over two review rounds. It was stopped under the owner's stall rule. The design is strong on seams, legality, exactness and memory. It fails on efficiency (goal 4), still-area stability under rate adaptation, loss recovery without a back channel (A5), mid-stream join, and legality on rail content. SA15 left these as "open", "structural" or "designed, not modelled".

**Sandbox:** `Subagents/SA15_design/`. Read it; do NOT modify it.
- `DESIGN.md` is round 1 and `DESIGN_v2.md` is round 2 (the authoritative one).
- `RESUME.md` holds its state and the full rejected list (§3).
- Scripts are in `notes/`: `cpp2.py` is the plane codec; `seq2.py` is the sequence codec and decoder; the rest are `run2.py`, `eval2.py`, `loss2.py`, `join2.py`, `rowstats2.py` and `render2.py`.
- Round-2 results are in `out/r2/` (logs in `log/`, `eval_final.txt`, renders in `renders/`, `rails_final.txt`), and the static tables in `out/tables_B.pkl`.

**Ledger:** S5.371, S5.372 and their addenda.

**Basis of all numbers:** numpy models, 8–12 frame sequences (steady-state frames 2–11 at 720p, 2–7 at 1080p), compared against today's REAL decodes. Round-2 rates are REAL code lengths from 60 static tANS tables trained on footage disjoint from the test cells. Round-1 rates were an entropy estimate × 1.10 and were FLATTERING (see F1a).

Treat everything below as evidence and hints, not as a design to continue.

---------------------------------------------------------------------------------------------------
## 1. The design, final state (so the evidence makes sense)
- **Transform: a "continuous pair pyramid".**
  - A Haar-type pair split: pair mean plus a pair difference predicted from neighbouring means, the "2/6 / TS" form.
  - 5 horizontal × 2 vertical levels; 4:2:0 chroma uses 1 vertical level.
  - The split never crosses a 4-row block. Each block's neighbour ("ahead") means are sent one step earlier in the stream, for EVERY block.
  - So a slice edge is an ordinary block edge, and slices are packet and rate units only: S = 4 rows at 720p and 8K, 8 at 1080p and 2160p.
- **Legality in synthesis.**
  - The decoder clamps each pair difference (and mean) into an interval computed from values that are already final. Every bit string decodes legally; there is no pixel clip.
  - Canonical index = the smallest-magnitude index that reproduces the value.
- **Lattice-locked temporal prediction.**
  - Motion compensation supplies hint INDICES; the stream carries q − h.
  - Every coefficient is reconstructed as an intra lattice point, so the picture is independent of the reference.
  - A coefficient is "kept" (hint reused) if |t − v_keep| ≤ 0.75 Δ, or if the kept value is closer than the requantised one.
- **Motion vectors, final.**
  - A block match of D(t−1) against D(t−2) (decoded history), computed while frame t−1 is being coded, so there is no extra reference read.
  - Integer-pel; half-pel was tested and gave no gain.
  - Note: an earlier round rejected "D(t−1) vs D(t−2)" for its DDR read, and its RESUME rejected list still says so. The final design re-adopted it in the "measured during t−1" form.
  - Check yourself whether vectors are transmitted or derived at the decoder: decoder-derived vectors failed loss recovery long ago (ledger S5.29).
- **Open-loop symbols,** quantised from the picture's own coefficients, so every candidate's exact code length is known in one pass.
- **Rate control.**
  - Exact CBR prefix bound; unspent bits are carried as credit, never borrowed.
  - One knot per slice on a 1/8-octave ladder, ramped linearly inside the slice; about 25 candidates costed in parallel.
  - The previous frame's knot is kept when it fits (still content).
  - A refresh reservation rho = 1/16 of the pipe.
  - No guard, no partial-slice mode.
- **Plan reading.** Each slice's knot = the coarsest candidate under which every coefficient is reproducible, read from the slice's own reconstruction plus the final data above it. Gen 1 emits exactly that reading; there is a proof by induction (DESIGN_v2 R8).
- **Entropy coding:** 60 static tANS tables (10 band classes × 2 modes × 3 contexts), L = 1024, 1.1 Mbit.
- **Loss recovery:** a one-way, bit-metered top-down refresh sweep, a clean-region rule for vectors, and on-demand refresh if a back channel exists.

## 2. SUCCESSES, and how each came about (all figures Y/Cb/Cr)
- **S1. No special row at slice edges, in any format or plane.**
  - Measured: the slice-edge row stays inside a 0.4–2.3 % spread of per-row error statistics on every format and plane, intra and inter, including 4:2:0 chroma.
  - The renders in `out/r2/renders/` (±16 and ±2 legends, grid, ×4 slice-edge strips) show no row feature.
  - Today's codec on spot has +30 % Cr and +13 % Cb row-step excess at slice edges.
  - How: SA15 traced the seam to the FILTER SHAPE. Long filters straddle any row boundary; the pair split has disjoint support, and its only cross-block element reads neighbour means that are always sent earlier, for every block alike.
  - A causal-predictor variant created a special row every 8th row (+5–9 %); SA15 rejected it rather than patch it.
- **S2. Legal by construction, at zero cost on natural and graphics content.**
  - 0 out-of-range samples in every run.
  - At 0.12–3 bpp, bits and MSE equal a "same codec + clip" arm.
  - How: each pair is written last from its final mean and its difference (a leaf), so the difference's legal set is an interval the decoder computes from final values. The synthesis is acyclic, and the pair mean IS the lowpass. This contradicts the cycle argument (ledger S5.349), which assumed a separate update step.
  - The round-1 +5.6 % at cf_gfx 0.2 bpp came from a source-side "prefer a clamped neighbour index" rule. It was removed by defining the canonical index from the decoded value only.
- **S3. Generation 2 identical (pictures AND bits) on every run tested.**
  - Natural and graphics: dng720, cf_gfx, floorball.
  - A scene-cut clip, and a mixed still/moving clip.
  - Rail extremes: cut24 at @0.5 and @1.0; ext10 full and limited range; ext8; ext12 at 4:2:2 and at 4:4:4.
  - Formats: 4:2:0, 4:4:4 12-bit, 4:2:2 8-bit and 12-bit, limited range.
  - How: the plan is read canonically from the picture, and gen 1 emits exactly that reading.
  - A one-slice "backtrack" (re-choosing an already-emitted slice) was removed after coordinator intervention; its trigger was a model defect.
  - Not run: g3/g10.
- **S4. Still input stays still at a constant step:** 0 changed samples and 0 bits per frame. Today's codec changes 60–77 % of samples every frame. BUT see F2.
- **S5. No smudges.** smudgegroups 0 and artifactmap 0/0/0 on every cell except the cut frame (see F6). Today has luma regions on 5 cells.
- **S6. No colour cast.** Position-alternating rounding: mean bias ±0.02 code (from −0.07…−0.21).
- **S7. Memory fits the ZU7EV at every format, including 8K.** This is arithmetic, by today's method in `.work/v537/docs/DDR_WINDOW_CACHE.md`.
  - Decoder URAM: 13.1 of 27 Mbit at 8K 4:2:2 10-bit, 22.4 (83 %) at 8K 4:4:4 12-bit. Today's codec does not fit the latter.
  - DDR traffic equals today's, 26 bit/sample.
  - How: short slices become possible once slices are not transform units. Per-coefficient step memory was built and rejected for 8K memory.
  - Not done: today's adversarial DDR timing simulation.
- **S8. Latency:** 18.2 lines at 720p, 26.3 at 1080p, 22.1 at 8K, excluding conversion (JPEG XS ~32). 720p50 with a 3:1 converter is 0.991 ms, which the owner accepts.
- **S9. Exact CBR in one pass,** with no guard and no partial mode. How: open-loop symbols; the cost is −0.02…−0.09 dB per plane.
- **S10. Training-set independence:** tables trained without the two clips that resemble test cells did equally well or better (floorball 95.53 vs 95.39, highwaydrive 92.56 vs 92.52).

## 3. FAILURES, and how each came about
- **F1. Efficiency (goal 4): NOT met on VMAF-NEG, the primary metric.**
  - 12 points against today's real decodes, NEG mean (worst frame where known):
    - **Better:** dng720 @0.5 90.34 (86.25) vs 90.16 (87.22); spot @0.5 93.99 (90.30) vs 93.25 (87.10); volley @0.5 92.48 (90.14) vs 92.29 (90.83).
    - **Tie:** floorball @0.5 95.53 vs 95.55.
    - **Worse:**

| point | NEG CPP | NEG today | difference |
|---|---|---|---|
| spot @1.0 | 97.21 | 97.36 | −0.15 |
| volley @1.0 | 95.09 | 95.59 | −0.50 |
| floorball @1.0 | 97.35 | 98.19 | −0.84 |
| dng720 @1.0 | 93.05 (91.49) | 94.05 (92.31) | −1.00 |
| dng1080 @1.0 | 92.29 (90.78) | 93.31 (91.77) | −1.02 |
| highwaydrive @0.5 | 92.56 (89.76) | 93.58 (90.58) | −1.02 |
| dng1080 @0.5 | 89.57 | 90.70 | −1.13 |
| highwaydrive @1.0 | 95.58 | 97.08 | −1.50 |

  - Worst-frame NEG is lower than today on most points.
  - **PSNR is HIGHER on 34 of 36 plane-points** (exceptions: spot Cr; highwaydrive @1.0 Cb 48.78 vs 48.96). PSNR up with NEG down means detail and texture are lost, not noise. The deficit grows with rate, and with the motion cells at 1.0 bpp.
  - Luma flatness is lower than today on 10 of 12 points, but dng1080 @1.0 is 42.0 % vs 27.5 %.
  - How it came about:
    - (a) Round 1 claimed a lead (dng720 @0.5 NEG 91.97 vs 90.16) from an entropy estimate × 1.10. With real code lengths it became 90.34.
    - (b) Texture is lost in INTER frames; intra retains more than today.
    - (c) Ruled out: the knot-stability rule (without it NEG 92.87, worse); the keep-hysteresis around zero hints (a "ZH"/grain-oriented variant kept texture, flatness 26.9 % vs 33.3 %, but NEG −0.8…−2.1 → rejected).
    - (d) Root cause NOT found by SA15. The coordinator's reading: lattice-locked prediction forces every inter coefficient onto the INTRA quantisation lattice, so an inter frame can never refine below the step or carry sub-step temporal detail; the 0.75 Δ keep window holds values up to ¾ of a step off. Both are design choices.
- **F2. Still areas shimmer under rate adaptation (mixed still/moving clip).**
  - 40–60 % of still samples change every frame while the step refines, about 52/48 toward/away from the source. That is the same "ants" class as today's codec (60–77 %), which the owner treats as a disqualifier.
  - How: the knot ladder moves in 1/8-octave steps. Under lattice lock a still sample is requantised whenever its step changes, and 1/8-octave lattices are not nested.
  - SA15's proposed fix, refining only by exact octaves (nested lattices), is designed but NOT modelled, and it would coarsen rate control.
- **F3. Loss recovery without a back channel (A5): NOT met.**
  - Final code: after a lost slice, the refresh sweep stalled at row 544 because one 4-row unit cost more than a frame's reservation. The loss was NEVER repaired.
  - SA15's redesign (a unit sized by worst-case cost) gives the bound T ≤ 2·c·L_max/(ρ·bpp) + 1 frames: about 1,000 frames at ρ = 1/16 and 1 bpp (4:2:2), 20 s or more. A5 requires a small, bounded number of frames.
  - Refresh costs 0.37 NEG at ρ = 1/16.
  - How: lattice-locked prediction makes refresh "picture-neutral". A refreshed coefficient must be re-sent as its full intra index, so refresh costs a full intra re-send, content-dependent, against a fixed reservation.
  - A "save the reservation up to 8 frames" rule was a patch; it was withdrawn after coordinator intervention.
  - The earlier typical case (ρ = 1/4, before the stall) repaired in 10 frames.
- **F4. Mid-stream join under exact CBR: NOT met.**
  - A 24-frame run plateaus at 43–55 of 180 slices differing from upstream. Frames 6–10 had improved 167 → 86.
  - SA15's fix, joining through the refresh, is NOT modelled; it inherits F3's refresh problem.
- **F5. Legality on rail content: NOT free and NOT "never away".**
  - Rail plates (cut24, ext10): +2–16 % bits at contribution rates, +40–112 % at 0.1–0.3 bpp. Cause: a source sample exactly on a rail sits on its coefficient's interval boundary, and the dead-zone index may fall one step short, so the encoder spends the reaching index.
  - A boundary-snap reconstruction was rejected (MSE × 7.7).
  - "Never away": the clamp preserves the pair MEAN (needed for exactness of coarser levels), so the partner sample moves the opposite way. About a 50/50 split toward/away on natural content (13–312 samples per frame at ≥ 0.5 bpp), up to 72 codes over a clip at ≥ 0.5 bpp and 259–395 at 0.1 bpp.
  - SA15 called this structural for any mean-preserving legaliser. The coordinator does NOT accept that; it is unproven.
- **F6. Cut clip:** 42 and 44 luma artifactmap regions on the scene-cut frame, not inspected by eye (the intra ramp may be exempt; see the owner's ramp rule in PROJECT_CONSTRAINTS).
- **F7. Process (do not repeat).**
  - The test queue was restarted four times: design changes mid-queue; OOM from caching shifted planes per vector; 7–10 parallel jobs of ~2.6 GB each.
  - Four model bugs were found late: snapshot aliasing, per-frame state retention, ahead data on the next slice's field, gen 1 emitting pass-1 state.
  - Two rounds took about 18 hours including three usage-limit stops.
  - Round 1's efficiency claim came from an estimate. Measure with real code lengths from the start.

## 4. Built and REJECTED by SA15 (with reasons; do not retry without a new reason)
1. Closed-loop predict-only pyramid (per-sample clamp): −1.4…−5 dB, chroma worst. Confirms ledger S5.212 and S5.349.
2. Causal vertical predictor: a special row every 8th row, +5–9 %.
3. Boundary-snap reconstruction on rails: MSE × 7.7.
4. One-slice backtrack in plan reading: a search, and rework of an emitted slice.
5. Per-coefficient step memory: 8K memory and DDR (+14 bit/sample, frame-sized state).
6. Motion search against a second reference frame read: 8K DDR. Replaced by the history search done during t−1.
7. 720 tables of L = 2048 (26.5 Mbit): not implementable.
8. Refresh cost charged to the rate lanes: starved slices.
9. Saving the refresh reservation for up to 8 frames: a symptom patch.
10. ZH / grain-oriented keep rule as the texture fix: NEG −0.8…−2.1.
11. Half-pel vectors: no gain on 3 motion cells (NEG −0.13/−0.09/+0.20 at +1.4–1.9 % bits).

## 5. What the evidence suggests (hints only)
- **The two strongest results of all four designers:**
  - S1: a slice seam is a property of the filter support, not of slices.
  - S2: legality is exact and free when the final synthesis step writes samples from one final value plus one leaf.
  - Both were measured in every format and plane.
- **F1, F2, F3 and F4 share one root: lattice-locked temporal prediction.**
  - It bought still-picture stability at a constant step, exactness through joins and loss, and memory simplicity.
  - It cost inter-frame texture (F1).
  - It made still content hostage to every step change (F2).
  - It made refresh a full intra re-send (F3, F4).
  - The open question: how can temporal prediction keep the decoded picture reproducible from the image alone, and keep refresh and joins cheap and bounded, WITHOUT forcing inter frames onto the intra lattice?
  - Earlier value-domain prediction (SA12, and today's OMC) kept texture better. SA12 showed a byte-exact mid-stream join from frame 15 with a contiguous refresh sweep plus clean-region rules.
- **F5 comes from the pair mean being preserved at a clamp.** A design must show how rail samples cost nothing and how no sample moves away from the source.
