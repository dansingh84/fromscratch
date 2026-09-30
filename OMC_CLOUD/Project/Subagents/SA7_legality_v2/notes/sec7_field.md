## §7.z Sizing the CONTINUOUS QUANTISER FIELD from these numbers (coordinator request)

The escape measurement is, read the other way, a **map of where the slice needs more precision and
how much** — which is exactly the field's parameterisation. Four numbers size it.

**(1) How much precision, and where it saturates.** The escape displacement `d = e·2^(s−k)` is a
sub-step refinement of magnitude `|e|/2^k` of a step. Converting `|e|` at `k = 4` into an
equivalent rung offset `δ = log2(2^(k−1)/|e|)` — "how many rungs finer would this coefficient's
step have to be for the base index alone to land here":

| `|e|` at k = 4 | equivalent rung offset δ | spotrobotL | volleyballgameL | cf_gfx |
|---|---|---|---|---|
| 1 | **3 rungs finer** | 51.3 % | 43.5 % | 37.7 % |
| 2 | 2 | 18.2 % | 18.9 % | 14.0 % |
| 3–4 | ~1.2 | 14.8 % | 17.3 % | 15.2 % |
| 5–6 | ~0.6 | 7.5 % | 8.4 % | 7.9 % |
| **7–8 (at the bin edge)** | **0 — the base index itself is wrong** | **8.1 %** | **11.9 %** | **25.2 %** |

So the correction asks for **1 to 3 rungs of extra precision on ~92 % of the coefficients it
touches, and for a different base index on the remaining 8–25 %**. A field carrying **±3 rungs**
(3 bits signed, or 2 bits if the range is 0…+3) covers the first group outright; the second group
is the residue that a *within-bin* mechanism cannot reach by definition and a *step-scale* field
can, because changing the step changes which bin the coefficient lands in.

**(2) Where, spatially — and it is strongly clustered, which is what makes a coarse field viable.**
Escapes per 32nd of the plane width (uniform would be 3.12 % each):

| cell | max bucket | min bucket | max/min | buckets with **zero** escapes |
|---|---|---|---|---|
| spotrobotL | 11.2 % | 0.00 % | 1181 | 6 of 32 |
| volleyballgameL | 7.9 % | 0.00 % | 813 | 5 of 32 |
| cf_gfx | 9.5 % | 0.00 % | 202 | 7 of 32 |

A 1920-wide luma plane at one control point per 64 columns is 31 control points — the same
resolution as these buckets. The measured concentration says a field at that pitch would spend its
precision on 6–11 buckets and leave the rest at zero offset, which is what "slice budget unchanged"
requires. **A coarser pitch (128 or 256 columns) would smear the demand across buckets that need
nothing** — 1 control point per 64 luma columns is the pitch these numbers support, and I would not
go coarser without re-measuring.

**(3) Which bands need it — and it is not only level 1.** Share of escapes by band:

| | HL5 | HL4 | HL3 | LH2 | HL2 | HH2 | LH1 | HL1 | HH1 |
|---|---|---|---|---|---|---|---|---|---|
| spotrobotL | 2.3 | 4.5 | 8.2 | 14.6 | 13.3 | 6.0 | 27.9 | 18.1 | 5.0 |
| volleyballgameL | 1.7 | 4.8 | 6.3 | 11.1 | 11.6 | 4.7 | 23.9 | 26.1 | 9.6 |
| **cf_gfx** | 4.8 | **14.2** | **22.1** | 15.6 | **22.1** | 3.1 | 6.0 | 9.0 | 3.1 |

On natural content the demand is ~51–60 % level-1, ~34 % level-2, ~15 % coarse. **On graphics it
inverts: 63 % of the demand is in the coarse and level-2 bands and only 18 % in level 1.** A field
that scales only the finest bands would miss cf_gfx entirely. The field must apply a step *scale*
to **every band** at that spatial position (the natural form: one field, and each band's step is
`shift[p][b] − offset(x,y)`), not a finest-band-only refinement — which is also the form that
composes with the plan instead of fighting it.

**(4) Precision of the field itself.** The demand is 1–3 rungs, clustered, and the residue that
wants a *different* base index is 8–25 %. So: **offset range −1…+3 rungs (3 bits per control
point), one control point per 64 luma columns, one row of control points per slice** (the slice is
8 or 16 rows; a vertical dimension inside the slice buys little at 8 rows and is untested at 16).
Cost: 31 × 3 = 93 bits per slice per plane at 1080p, 279 bits for three planes = **1.8 % of a
15,360-bit slice budget at 0.5 bpp**, and it is a *fixed* cost with no position coding — against
the escape's measured 2.4–7.9 % mean and 14–36 % worst-slice cost. **The field is cheaper than the
escape by a factor of 2–20 and its cost does not spike on the hard slices**, which is the property
the escape most conspicuously lacks (§7.3).

**What the per-region form would need beyond the escape**, and how to keep them compatible:

* **One lattice, one lock.** The field changes `shift[p][b]` per coefficient position. The
  committed picture stays `INV(dequant(q, shift_field))` — a lattice point of a *signalled* plan,
  so the T5 lock argument is the shipped one, unchanged, and `verify_candidate` needs no escape
  extension at all. The field is therefore **lock-simpler than the escape**, not lock-harder.
* **Continuity, per the owner's ruling.** The offset must be a continuous integer field, not a
  constant per region: control points `o[j]` at 64-column pitch, and per sample
  `offset(x) = (o[j]·(64−t) + o[j+1]·t + 32) >> 6` with `t = x mod 64` — integer, shift-and-add,
  no multiplier if the 64 weights are a small LUT, identical at both ends. No region has an edge,
  so there is no boundary to step at. Bilinear in two dimensions if a vertical control row is ever
  added.
* **What it needs that the escape does not:** the shift becomes a function of `(p, b, x)` rather
  than `(p, b)`, so `coeff_shift()` becomes a per-coefficient lookup — it already is one
  (`coeff_shift(sp, p, b, i)` exists for the partial-chunk rule), so the plumbing is present. The
  rate ladder must choose the control points, which is a genuinely new encoder decision and the
  main build cost. The bit estimator `bits[OMC_MAX_SHIFT+1]` is already per-shift, so a
  field-aware estimate is a weighted sum over the field's histogram.
* **How to keep the escape compatible rather than a dead end:** the escape's syntax is a flat list
  of `(position, e)` applied *after* dequantisation at whatever step the plan gives that
  coefficient. It therefore composes with a field unchanged — the field sets the step, the escape
  refines within whatever bin that step produces. Both are read from the stream, both are in the
  same lattice, and the correction pass is the same pass in both cases: accumulate demands onto
  atoms, apply, verify by exact local inverse. **The escape should be specified as "refine within
  the bin of the coefficient's effective step", never "within the bin of the band's step"** — that
  one wording keeps it composable.
* **The eye risk the field must be judged on** (owner ruling, and it is the reason for the
  continuity requirement): a continuous field still varies, and a *gradient* of precision can show
  as a gradient of texture. The level maps must carry the control-point columns marked, on
  steady-state frames, every plane, so a human can look for a step or a ramp at control-point
  phase. `notes/gridmap.py` in my folder draws exactly that and is used below.
