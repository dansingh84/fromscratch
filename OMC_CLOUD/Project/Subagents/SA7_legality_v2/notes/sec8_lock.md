## §8.5 (e) The lock, checked in the code — and the field is **lock-simpler than the escape**

**What the field writes.** The probe's only functional change is inside `coeff_shift()`
(`src/codec.c:1079`): the per-coefficient shift becomes `s − offset(x)`, clamped to
`[0, OMC_MAX_SHIFT]` and, for band 0, still capped at `OMC_LL_CAP` so the anti-banding guarantee
(G2) is untouched. Nothing else is written: no pixel, no residual, no side value. The committed
picture therefore remains

    INV( dequant( q , shift_plan − field ) )

— **a lattice point of a signalled plan**, which is exactly the shipped situation with a larger
plan. That is the whole in-lattice requirement, and unlike the escape it needs **no change to
`verify_candidate`** (§7.1): the verification's `dequant(quant(c, s), s) == c` test works
unchanged once `s` is the field-modified shift.

**Where the lock does need something new, stated precisely.** `verify_candidate` is called on
*enumerated candidate plans* (`omc_lockcand_t`, `src/codec.c:90`, "on generation ≥ 2 input the
previous generation's own committed plan MUST be in the list"). A field of 32 control points × 3
planes × 3 bits is **288 bits of plan**, and no enumeration can cover 2^288 candidates. So the
field cannot be *searched* at generation 2.

**It does not need to be: it can be DERIVED, constructively, in one pass.** With the
round-to-nearest quantiser and `omc_recoff = 0`, `dequant(quant(c, s), s) == c` **iff `c` is a
multiple of `2^s`** (plus the two exceptions below). So for each coefficient the largest shift that
reproduces it is `ntz(c_i)`, its count of trailing zeros — a priority encoder in hardware, free.
The field must satisfy, per control-point span `j` and plane `p`,

    offset(j) ≥ max over coefficients i in the span of ( base_shift[p][b(i)] − ntz(c_i) )

and because `offset(x)` interpolates monotonically between `o[j]` and `o[j+1]`, taking each
control point as the maximum requirement over the two spans it touches is sufficient and
deterministic. **Generation 2 therefore recovers a field that reproduces the picture exactly,
without search, in one traversal.** It need not be generation 1's field: any field that reproduces
`c` locks the *picture* at generation 2, and generation 3 then sees the same input and makes the
same choice, so the *stream* locks at 3 — which is exactly the required behaviour.

**Two exceptions that must be handled and are already in the code's verification**, recorded so
they are not rediscovered: (i) the **deadzone** (`omc_quant1b_dz`) sends `|q| = 1` to 0 when
`|c| < 9·2^s/16`, so "multiple of `2^s`" is not sufficient for the smallest non-zero index — the
constraint there is `|c| ≥ 9·2^s/16` as well; (ii) the **grain fill** paints a value where
`q == 0` reconstructs 0 in a fill band, which `verify_candidate`'s existing "potential fill
position" clause already covers.

**What I measured, and what I did not.** The derivation above is a build, not an oracle, and it is
not in the probe — so I could not run a chain that tests *field recovery*. What I could isolate is
the other half, which is the half that has killed every previous mechanism: **does a
field-modified plan preserve the lattice property at all?** For that I added arm 4, a
**content-independent** field (a fixed function of slice index and control-point index, computed
identically at both ends with no signalling), and ran the 8-generation display-decode chain on two
cells. Results in §8.6. A chain on arms A/B/C would test the probe's missing recovery step, not
the mechanism, and is not reported as if it did.
