## §9.8 Against the bar

> **GO** = every owned cell at every rate closed with ≤ 2 whole-step passes plus bank-funded
> escapes on ≤ 3 % of slices, bank draw within the cap, no plane worse than 0.1 dB at equal CBR,
> lock argument sound in the code, cycles inside the period at 16 spc for 4K.

| criterion | measured | bar | verdict |
|---|---|---|---|
| slices closed by ≤ 2 whole-step passes | see §9.2 | — | — |
| **residue needing escapes** | see §9.2 | **≤ 3 % of slices** | **MISS** |
| **bank draw within the cap** | worst-slice escape ≤ 19.4 % of the slice budget against a **100 %** allowance; prefix surplus and the 608-bit floor never binding | within cap | **PASS** |
| per-plane dB at equal CBR | see §9.6 | ≤ 0.1 dB | see §9.6 |
| lock argument sound in the code | §9.4: the bank is already part of the locked plan input; the extension is four lines plus the window function, and the whole-step half needs **no** extension | sound | **PASS** |
| cycles, 4K at 16 spc | **32.5 %** of the period at the 4 % area cap, **57.5 %** at the 13 % bound | inside the period | **PASS** |
| exact CBR / legality | exact CBR at every rate on every cell; `oob = 0` everywhere | — | hold |

**Verdict: NO-GO** on completeness — the one criterion the iteration was built to test. Three of
the six pass, including both of the ones nobody had measured before (the bank can fund it; the
cycles fit 4K at 16 spc).

## §9.9 What this settles, and the one design change it implies

The session has now measured, four times, that **a fixed-budget redistribution cannot deliver
legality** (bands, bins, positions, and the ideal field). L-I21 adds the fourth corner: **a
whole-step correction pass cannot deliver it either**, and for a reason that is not about search
and not about budget — `nocover = 0`, the bits are available in the bank, the cycles are free, and
the pass still fails, because the smallest move it owns is 5–18× the job and it pushes neighbours
out.

Put the three results of this session side by side and they compose into one design rather than
three failures:

1. the **two-phase pass with an exact local inverse** is the cheapest correction mechanism measured
   — **0.38 traversals worst case against the shipped step's 1,273.6** — and it is complete only if
   its moves are the right size;
2. the **within-bin escape** is exactly the right size — it clears **97.9–100 %** of violating
   samples (L-I19 §7.3) — and its only failing was that it was costed as if the slice had to pay
   for it out of its own budget;
3. the **causal bank** pays for it: the worst residue slice needs **≤ 19.4 %** of its slice budget
   in escape bits against a normative **100 %** allowance that already exists in the codec, on
   18–36 % of slices at 0.5 bpp and fewer at 1.0.

**So the escape is not a residue mechanism. It is the pass's step size.** The design change is to
stop treating within-bin refinement as an escape hatch for the slices a whole-step pass cannot
close, and make it the granularity the two-phase pass uses **from its first move**, funded from the
bank on the slices that need correction at all. That is a different experiment from anything run so
far: every arm to date has either used whole steps (L-I21), or used the escape only where whole
steps had already failed and charged it to the slice (L-I19). Neither measured the combination the
numbers point at.
