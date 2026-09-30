## §7.x IP provenance (owner rule, 2026-09-13, as refined) — every new element, why it is obviously clean, and what I removed

The rule applied here: **an element is included only if it is already obvious that it is
open-standard, expired-vintage or own work. Anything I cannot state that way is not in the design
and no question is asked about it.** Nothing below is taken from a named standard's tool or syntax
element; the provenance line is the comment the code would carry if it is built.

| element | provenance | why it is obviously clean |
|---|---|---|
| **within-bin refinement of a quantiser index** | own work, and **already in this codebase for another purpose**: `omc_dequant1`'s centroid reconstruction (`src/internal.h:226`) moves the reconstruction point inside its own bin and argues the generation lock from bin containment. The escape makes that offset signalled and per coefficient instead of a fixed table constant | the mechanism is already ours and already shipped; the escape changes where the number comes from, not what it is |
| **dyadic subdivision of the bin** (`e·2^(s−k)`) | halving an interval k times; textbook numerical representation, pre-1900, no proprietor | it is binary place value |
| **flat escape list: explicit position + value** | own work | it is deliberately **not** a refinement layer: no embedded ordering, no quality layers, no truncation point, no progression — the decoder reads a position and a value and adds it, in one pass, and a truncated stream is simply an invalid stream. The properties that would make it resemble a layered construction are exactly the properties it does not have, and if the design ever acquired them it would leave the obviously-clean set and therefore be out |
| **escape position coding: sorted positions, Elias-gamma deltas** | Elias, *Universal codeword sets and representations of the integers*, 1975 — public-domain academic work, universally implemented, no licensing body | published academic coding, over 50 years old |
| **escape value coding: tANS** | the codebase's own entropy coder, already C1-cleared (tANS only; rANS forbidden anywhere, C1) | already the product's coder |
| **correction pass** (accumulate demands onto shared atoms → apply → verify by an exact local inverse over the support box) | own work; the "local inverse" is this codec's own lifting arithmetic restricted to a window | it is our transform, run on a sub-rectangle |
| **continuous control-point field** (control points signalled per slice, per-sample step scale by integer bilinear interpolation) | bilinear interpolation on a coarse control lattice is textbook, pre-1960; the composition with a quantiser step is own work | it is **not** a per-block delta-QP field, not a quantisation matrix, and not indexed by any standard's table: there are no regions and no per-block syntax element at all, only control points and an interpolation formula. The thing a block codec signals — a constant offset attached to a block — is the thing the owner's no-steps ruling forbids and this design does not contain |
| **integer bilinear with a 64-entry weight LUT** | shift-and-add evaluation of a linear blend; own work | arithmetic |

**Removed from the design under this rule, rather than flagged:** nothing survived from the earlier
draft's "for counsel" list because both items resolved to obviously-clean forms once stated
precisely — the escape by having no layer/ordering/truncation semantics, the field by having no
regions and no per-block element. Two candidates I considered and **left out** because I could not
state them as obviously clean without further work, and the rule says out rather than asked:

1. A **quantisation-matrix-style per-band-per-position weight table** as an alternative to the
   field (it would sit much closer to named standards' normative tables). Out.
2. An **embedded / progressively-orderable** form of the escape, which would have let the encoder
   truncate the escape list to fit the budget. That ordering is precisely what would make it a
   layered refinement construction. Out — and the budget question is instead answered by the field,
   whose cost is fixed (§7.z).
