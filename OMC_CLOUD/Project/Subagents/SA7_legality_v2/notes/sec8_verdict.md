## §8.11 Against the bar

> **GO** = on arm B or C: residue ≤ 0.1 % of violating samples **and** unconverged = 0 at the K
> that fits on every cell, flat share per plane not up on any cell (down where the field targets
> texture), no plane worse than 0.1 dB net, lock intact, no step visible at control-point phase.

| criterion | measured | bar | verdict |
|---|---|---|---|
| legality: violations / repair work | **up on every arm of every cell**: B +8…+90 %, C +15…+120 %, **A (the oracle arm) +92…+1078 %** | residue ≤ 0.1 %, unconverged 0 | **MISS** — and the direction is wrong, so the downstream residue figures could only be worse |
| flat share per plane | **up on every plane of every cell of every arm**, including arm C: Y +0.11…+8.72, Cb +0.45…+6.48, Cr +0.48…+4.09 points | not up on any cell; down where the field targets texture | **MISS** |
| chroma, per plane | Cb −0.109…−0.575 dB, Cr −0.071…−0.441 dB | ≤ 0.1 dB | **MISS** |
| quality at equal CBR, net of syntax | Y −0.427…−2.410 dB; **no plane of any cell improves** | ≤ 0.1 dB | **MISS** |
| the lock | see §8.6 | intact | **see §8.6** |
| steps at control-point phase | cp/mid ratio +0.017…+0.026 on luma over a base of 1.005–1.032; none visible to my eye in any plane of either cell | none visible | **the only criterion that passes** |
| legality preserved (oob) | **0 committed samples outside the legal range on every arm of every cell** | — | holds |
| exact CBR | exact on every arm | — | holds |

**Verdict: NO-GO.** Five of seven criteria missed, and missed in the same direction on every cell.
Nothing is built into any product tree. @1.0 bpp was not run, per the loop rule on a step-1
measurement that missed its bar.

## §8.12 What this result actually establishes — the reason it matters more than the verdict

The three mechanisms this session measured all take the same shape: **keep the slice's bit budget
fixed and move precision around inside it.** The plan rung (L-I19's predecessor, S5.188) moved it
between bands; the escape (L-I19) moved it inside a coefficient's own bin; the field (L-I20) moves
it between positions. All three failed, and the field failed **with an oracle that knew exactly
where the violations were**.

The common cause is now measured three times from three directions: at a fixed budget, precision
taken from anywhere in the slice makes *that* place ring harder, and the coarse-band ripple at a
hard edge is what crosses the rail (§U, §V, §8.3). There is no arrangement of a fixed budget that
removes the ripple; there is only a choice of where to put it.

**What has never failed is the other half.** The in-lattice correction pass — one exact
reconstruction, a fixed-work two-phase correction verified by an exact local inverse — is measured
at **1,274 traversals → under 3** for the worst slice (§7.6) and is the only mechanism in the whole
record that delivers legality without costing quality. Every failure this session has been an
attempt to avoid needing it. On the evidence, the question worth asking next is not *where should
the bits go* but *how cheap and how complete can the correction pass be made*, and the DESIGN's
remaining half — the two-phase pass, the exact local inverse, row-0 certification, the per-column
row-`sh−1` bound, the encode reorder, and deleting `[LEGACY-REPAIR]` — is untouched by all three
NO-GOs.
