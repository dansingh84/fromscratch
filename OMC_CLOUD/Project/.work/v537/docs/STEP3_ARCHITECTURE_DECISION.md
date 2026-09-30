# Step 3 — Architecture decision: merge verdict (measured, not argued)

## What I measured myself (all on this machine, this footage)

| claim | source | my measurement | verdict |
|---|---|---|---|
| XS harness handicap (+1.7 dB) | findings pt.2 §1.1 | beach24 @4bpp: Y 53.64 → 56.09 (+2.46), mean +1.75 with `--coding-signs 2 --coding-vpred 2 --quantization 1` | **CONFIRMED** — all comparisons now use fair flags |
| OMC rt=0, exact CBR | README/REPORT | beach24 @2bpp: recon == decode byte-exact; every frame exactly F bytes | **CONFIRMED** |
| OMC ~parity at equal rate | findings pt.2 §2.2 | OMC@2 = 49.92 worst-steady avg-plane on beach24; fair-XS@2 ≈ 49.4 | **CONFIRMED** (slightly ahead here) |
| 0.5× mandate unmet on instruments | findings pt.1 §1 | Kestrel@2 SS 51.5 vs fair-XS@4 ≈ 55.9 → −4.4 dB (their beachdusk: −4.31) | **CONFIRMED** |
| Kestrel block-MC beats OMC temporal | my hypothesis | beach24 @2bpp steady: Kestrel 51.5 vs OMC 49.9 (+1.6 dB, all planes) | **CONFIRMED** — the unshipped lever is real |
| OMC A4: static ≈ byte-exact, heavy grain converges | REPORT 12c, 13b.5 | static beach: frames 0–3 byte-exact; late frames diverge g1→g2 76.6 dB then g2→g3 97.1 dB (converging) | **CONFIRMED** (incl. documented lock-miss scope) |
| Kestrel A4 | — | moving: 51.6→47.9 dB over 5 gens (~1 dB/gen, ACCUMULATING); static: ~58 dB churn/gen | **Kestrel v1 FALSIFIED for A4** |

## The load-bearing design lessons

1. **Power-of-2 shift quantization with lattice reconstruction (q<<s) is what makes
   generations converge**: re-encoding lattice data at the same or finer shift is
   *exactly lossless*. My geometric 2^(s/8) ladder + 3/8-offset reconstruction is
   structurally generation-hostile. (Independently: freeing steps from pow2 is worth
   only +2% — R8.) → Adopt OMC's quantizer class wholesale.
2. **Per-block spatial-domain MC composition fixes OMC's D-1 bottleneck** (the
   per-slice-band mode mask that could not localize) *without* touching the mode
   mask: localization moves into the prediction composition, before the transform.
   Their own pixel-domain data (7b): 16×16 MC cuts soccer residual 64%.
3. **Decision replay is the A4 battle**: block-sum SAD (means cancel coding noise),
   strict argmin over fixed candidate lists, no adaptive thresholds, and the
   existing lattice lock_verify carries over (it verifies reproduction under the
   *current* decisions; stable decisions ⇒ stable lock).
4. **Deadzone (R1)**: +9.8% verified in OMC; my codec's next quantizer keeps recon
   points unchanged so it composes with the lock. A4 interaction must be re-measured.
5. **Seam veto (G1)**: block-composited prediction has fixed-column block edges —
   composition must be seam-suppressed (deterministic overlapped blending, plus MV
   cost predicting from neighbors), and validated by tripwire + human review.
6. **The remaining octave is perceptual, by mandate design**: both teams' measurements
   agree fidelity coding tops out ≈1.2–1.4× vs fair XS. Rev. 6 (eyes decisive) +
   grain fill (their v4) + R6-class masking is the sanctioned route for the rest;
   the blind kit is the acceptance instrument.

## The build plan (executed next)

- Phase A: apply verified fixes F-1 (fill_gate clamp), F-3 (low-rate guard) to OMC.
- Phase B: R1 deadzone (bundle patch, adapted); measure RD + A4 on real footage.
- Phase C: **v5 temporal layer**: per-block (16×16) MC composition in pixel domain,
  MV field entropy-coded in payload (header keeps 4-region fields for v4 compat;
  v5 streams flag block-MV mode), stable search (slice-global stage-A + fixed
  per-block candidate offsets, block-sum SAD, strict argmin), seam-suppressed
  composition. Measure: RD on motion content, A4 chains, seam tripwire, loss, CBR.
- Phase D: R7a saturation fix; (stretch) R2c/R3 entropy upgrade.
- Phase E: full-footage curve OMC2@R vs fair-XS@2R at R ∈ {0.5, 1, 2, 3}; CBR audit;
  generations; loss; visual review pack; final report.

Kestrel (my clean-sheet v1) is retained as evidence and testbed; the deliverable
inherits OMC's verified machinery because the measurements above say each of its
core choices (quant lattice, entropy, RC, lock, fill) survives contact with reality,
while its temporal layer does not — and mine does, but nothing else of mine does.
