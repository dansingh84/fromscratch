## §8.8 (h) Provenance — every element, stated as obviously clean or left out

Applying the owner's refined rule: an element is included only where it is already obvious that it
is own work, textbook, or expired vintage; anything else is **out of the design**, not flagged.

| element | provenance | why it is obviously clean |
|---|---|---|
| a per-sample step **scale** derived from a coarse lattice of signalled control points | own work | it is not a per-block QP delta and not a quantisation matrix: there is **no region and no block**, hence no syntax element attached to one. The object signalled is a list of control values; the object used is a continuous function of position |
| **bilinear (here 1-D linear) interpolation** between control points | textbook, pre-1960 numerical analysis; no proprietor | it is a weighted average of two numbers |
| integer evaluation `(o0·(SP−t) + o1·t + SP/2) >> lg` with `o ∈ {−1..3}` as shift-adds | own work | it is binary arithmetic; the small-constant products are shifts |
| the **detector** (per-span sums of `|c|` over three band classes, ranked) | own work | it is a sum of absolute values of this codec's own coefficients, ranked |
| the **mean-zero rank assignment** (fixed histogram whose signed sum is zero, ties by index) | own work | it is a sort and a fixed table |
| the field applying to **every** band's step at that position | own work | it is a single subtraction inside this codec's own `coeff_shift()` |
| the correction pass and the exact local inverse (carried over from DESIGN §2, unchanged) | own work; the local inverse is this codec's own lifting arithmetic on a sub-rectangle | already stated in §7.10 |
| the LL band remaining capped at `OMC_LL_CAP` under the field | this codec's own anti-banding rule | already shipped |

**Left out under the rule, not flagged:** (i) any **per-block or per-region** step offset — it is
both the owner's forbidden form and the construction closest to named standards; (ii) a
**quantisation weighting table** indexed by band and position; (iii) any **embedded or
progressively truncatable** ordering of the control points, for the same reason the escape's
embedded form was dropped in §7.10. None of these is in the probe or in the design.
