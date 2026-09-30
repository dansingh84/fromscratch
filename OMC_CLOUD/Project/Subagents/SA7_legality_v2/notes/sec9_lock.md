## §9.4 (c) The lock, and the one code change it needs — designed, not built

**Why bank-funded escapes reproduce.** The bank state at slice *k* is `e->spent_bits`, the sum of
the wire sizes of slices 0…k−1 **of the same frame**, and those wire sizes are a function of the
emitted stream alone. In a T5-locked chain every slice of the frame reproduces its generation-1
stream byte for byte, so `spent_bits` at slice *k* is **identical at every generation**, and so are
`avail_prefix`, `avail_frame` and `budget`. The bank is therefore already part of the plan input in
the locked chain — it is not new state and it introduces no new dependency. A slice that drew
1,200 bank bits at generation 1 finds the same 1,200 bits available at generation 2, because every
slice before it emitted the same number of bytes.

The induction is the one already in `docs/TEMPORAL_T5.md` §5 (the prefix induction, quoted in the
code at `src/codec.c:6003` as the reason a locked slice plans against `budget_hard`): if slices
0…k−1 reproduce, slice *k*'s budget reproduces; if slice *k*'s budget and its input coefficients
reproduce, its plan reproduces; hence slice *k* reproduces. Bank-funded escapes sit inside that
induction unchanged — they change *what* slice *k* spends its bits on, not *how many* it may have.

**The one code change: extend `verify_candidate` to accept an escape-representable residual.**
Today (`src/codec.c:5387`):

```c
int32_t q = (b == 0) ? omc_quant1b(cf[i], s, 0)
                     : omc_quant1b_dz(cf[i], s, tex_vmaf, dz);
int32_t v = omc_dequant1(q, s);
if (m) v += pc[i];
if (v == e->coef[p][b][i]) continue;
/* … potential-fill clause … */
okv = 0; break;                       /* candidate rejected */
```

The extension, in full:

```c
int32_t r = e->coef[p][b][i] - v;                 /* what the base plan cannot reach */
if (r == 0) continue;
/* … potential-fill clause unchanged … */
if (esc_ok(r, q, s, b, dz, k_esc) && n_esc < ESC_MAX) { esc_pos[n_esc] = …; n_esc++; continue; }
okv = 0; break;

static inline int esc_ok(int32_t r, int32_t q, int s, int b, int dz, int k)
{
    if (s <= k) return 0;                          /* no sub-step exists */
    int32_t g = 1 << (s - k);
    if (r % g) return 0;                           /* not on the escape grid */
    int32_t dlo, dhi; esc_window(q, s, dz, &dlo, &dhi);   /* sect.7.1(1)(2) */
    return r >= dlo && r <= dhi;                   /* stays inside bin q */
}
```

`esc_window()` is the corrected bin, **not** `±s/2`: the displacement applies to the **magnitude**
and runs `[−2^(s−1), 2^(s−1)−1]`; for `|q| = 1` in a deadzone band (every band ≥ 4 by default) it
runs `[−7·2^s/16, 2^(s−1)−1]`; for `q = 0` it is `(−9·2^s/16, +9·2^s/16)` in a deadzone band and
`±2^(s−1)` otherwise; and a `q = 0` position in a fill-enabled band is **excluded** because the
decoder paints a fill value there. Those four cases are §7.1's findings, and they are the whole
content of the change beyond the four lines above.

**Why this closes the argument rather than patching it.** With the extension, generation 2 does not
need the correction pass to be a pure function of anything: the slice **locks** on the generation-1
plan, and the escapes it emits are the *lock residual*, which is by construction exactly
generation-1's escape set. The picture locks at generation 2; generation 3 sees the same input and
the same deterministic candidate order and makes the same choice, so the stream locks at 3. The
whole-step half of the pass needs no extension at all — it emits ordinary lattice points at the
signalled plan, which is why §9.2's arm could be **emitted and measured** with no syntax change.

**What must be signalled** (the escape half only): `n_esc`, then per escape a position and a
`k`-bit value. Positions coded as sorted deltas (Elias gamma, 1975, public domain); values raw or
tANS. `ESC_MAX` is a normative constant so the lock trial's work is bounded; §9.3's bank numbers
size it.
