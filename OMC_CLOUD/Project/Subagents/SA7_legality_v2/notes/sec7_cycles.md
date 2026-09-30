## §7.6 (f) The cycle table with the escape pass in place of the constructive step

Two of DESIGN §3's assumed constants are now measured, and both were conservative.

| quantity | DESIGN §3 assumed | **measured here** (12 frames, 5 cells, 0.5 bpp) |
|---|---|---|
| `V`, violating samples per slice | cap `N/32` = 3.1 % | p50 **2–13**, p99 25–143, **max 183** = **0.30 % of N** at 1080p |
| escaped coefficients per slice | — | p50 6–27, p99 33–247, **max 311** |
| `C`, union of touched supports | cap 4 % | **not measured**; bounded above by `V × 45` (a level-1 support) = 13 % of N at 1080p before overlap, and the violations cluster, so the true figure is well below that. It is the one input still to measure |

With `V/N` at its measured worst (0.32 %), `P = 3`, `Ka = 4`:

`T_sel = 3 × 4 × 0.0032 = 0.038 traversals` (DESIGN assumed 0.375 — **10× conservative**)
`T_corr = 3 × 4.4375 × C` = **0.53** traversals at `C = 4 %`, **1.73** at the 13 % upper bound
`T_emit = 1` traversal, or **0** with the Stage-B reorder
Escape payload: bits, not cycles — the entropy coder already makes exactly one pass.

**Per slice, escape pass instead of `[S2-STEP]`, worst case, A = 1:**

| | shipped `[S2-STEP]`, **measured** (§1) | escape pass, `C = 4 %` | escape pass, `C = 13 %` |
|---|---|---|---|
| median slice | 17 inverses = **29.2 traversals** | 1.57 (0.57 with the reorder) | 2.77 (1.77) |
| worst slice | 741 inverses = **1,273.6 traversals** | 1.57 | 2.77 |
| available in one 1080p slice period @ 8 spc | **9.57 traversals, base included** | | |

| format | period (cyc) | traversal @ w=8 | escape pass total @ w=8 (A=1, reorder, C=4 %) | of period | @ w=16 | of period |
|---|---|---|---|---|---|---|
| 720p60 | 55,556 | 2,560 | 1.57 × 2,560 = 4,019 | **7.2 %** | 2,010 | 3.6 % |
| 1080p60 | 73,529 | 7,680 | 12,058 | **16.4 %** | 6,029 | 8.2 % |
| 4K60 | 37,037 | 15,360 | 24,115 | **65.1 %** | 12,058 | 32.6 % |
| 8K60 | 18,519 | 30,720 | 48,230 | ✗ | 24,115 | ✗ (base alone is 83 % at w=16) |

At the 13 % upper bound on `C` the 4K/w=8 column becomes 115 % and fails; 4K/w=16 is 57.5 % and
holds. Everything else is unchanged from DESIGN §3, including the 8K finding (a base-encode
throughput fact, not a legality one).

**The cost result stands independently of the NO-GO, and it is the one thing this iteration
proves outright:** replacing the shipped greedy's full-plane inverse per candidate with a
two-phase pass verified by an exact local inverse takes the worst slice from **1,274 traversals to
under 3** — a factor of ~450 — and the median from 29 to 1.6. **The escape does not fail on
cycles. It fails on bits**, whose cost is per escaped coefficient and spikes exactly on the slices
that need it most (19–36 % of the worst slice's budget), which is the wrong cost shape for a codec
at exact CBR. That is the argument for the fixed-cost field.
