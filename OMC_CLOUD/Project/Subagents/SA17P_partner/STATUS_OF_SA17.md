# Status of the main designer SA17, for its ideation partner

Coordinator, 2026-09-29 12:40 EDT.

SA17's own records are complete and current:
- `Subagents/SA17_design/DESIGN.md`: the design, with a root-cause chain for each choice.
- `Subagents/SA17_design/RESUME.md`: item status, and every rejected idea with its reason.

Read both. This page adds the coordinator's view.

## Where SA17 stands (after about 8 working hours)

**Design:**
- Continuous pair pyramid, with no slice-edge row class.
- Leaf-interval legality.
- Value-domain temporal prediction.
- Step-bucketed static tANS tables.
- Exact CBR with a 16-bit reserve.
- On-demand refresh as the primary mode.
- A one-way mode with a short refresh cycle.

**Final efficiency against today's real decodes.** 12 points, real code lengths, 0 slices over budget, 0 out-of-range. NEG mean (worst) mine vs today, with PSNR Y/Cb/Cr in DESIGN.md §2 and `out/eval_final.log`:

| cell | @0.5 mine | @0.5 today | @1.0 mine | @1.0 today |
|---|---|---|---|---|
| dng720 | 88.97 (88.10) | 90.16 (87.22) | 94.25 (93.17) | 94.05 (92.31) |
| dng1080 | 90.25 (88.56) | 91.08 (87.51) | 94.04 (92.36) | 93.51 (91.77) |
| spot | 94.41 (90.76) | 93.76 (87.10) | 97.72 (94.34) | 97.53 (95.03) |
| floor | 95.32 (91.47) | 95.98 (92.41) | 98.15 (94.46) | 98.59 (94.94) |
| hwy | 92.96 (89.73) | 93.73 (90.58) | 96.52 (93.37) | 97.29 (94.13) |
| volley | 91.17 (90.08) | 92.37 (90.83) | 95.21 (94.28) | 95.62 (94.70) |

Better on 4 of 12; worse on 8, by 0.4–1.2. The losses are concentrated on fast motion (floor, volley, hwy) and at 0.5 bpp. Volley @0.5 luma PSNR is −1.71 dB.

**What works:**
- Legality: 0 out-of-range, and gen 2 identical, including on rails.
- On-demand loss heal: exact at round trip + 1 (spot, RT 2: 3 damaged frames).
- No slice-edge row class.
- The transform price against 5/3 is about 0 at real code lengths.

**Open problems (the owner's bar is zero on each):**
1. **Goal 4, efficiency:** −0.4…−1.2 NEG on 8 of 12 points, worst on fast motion. Fast motion is exactly where OMC must beat JPEG XS.
2. **Blotches (goal 1):** the owner's artifactmap finds MORE luma regions than today at 0.5 bpp: dng720 23+6 vs 6+4; dng1080 22+20 vs 4+5; spot 3+2 vs 0+1; volley 6+6 vs 0. Chroma is clean.
3. **Still areas:** without a hold, 20–78 % of still samples change every frame. The still-hold rule (refine once, hold unless the source moves more than ¾ step, unspent bits padded) needs checking: are still areas at zero change, is texture preserved, is gen 2 exact?
4. **"Never away":** legality moves about half the changed samples farther from the source than a clip would (dng720 @0.5: 1,817 of 3,376, max 136 codes). Not met.
5. **One-way links:** the owner's ruling is recovery in under 4 frames (a refresh cycle of 2–3). Cost measured at dng720/hwy @0.5: cycle 2 is 87.41/89.82 and cycle 3 is 89.22/91.07, against 90.16/93.73 today.

## Rules the pair must respect (the full list is in the brief)
- No patches. A design-created artifact disqualifies the design choice behind it.
- No iteration, search or trial coding.
- VMAF-NEG first, then PSNR Y/Cb/Cr, always at real code lengths.
- Every figure per plane.
- Latency must match JPEG XS, and stay under 1 ms including conversion.
- 8K memory must not exceed today's.
- Royalty-free techniques only.
