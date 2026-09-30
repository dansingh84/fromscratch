# §7. Loop iteration 2 — the WITHIN-BIN PER-COEFFICIENT ESCAPE (L-I19), step 1

**The idea (coordinator).** A coefficient with base index `q` at step `s` carries `k` extra bits
`e`, reconstructing to `v_e = q·s + e·s/2^k`, which stays inside bin `q`. Emitted only for the
coefficients the correction pass touches; position + `e` in the stream (free syntax, minor 17).

## §7.1 The lock argument, checked line by line in the code — **it does NOT hold as written, and I can say exactly where**

The coordinator's chain was: *(i)* at generation 2 the analysis returns `v_e` exactly; *(ii)* its
base quantisation is `q` again because `v_e` is inside bin `q`; *(iii)* so the base-quantised state
at generation 2 equals generation 1's; *(iv)* the correction pass is a pure function of that base
state and the budget, so it selects the same escapes; *(v)* the stream reproduces.

**(i) holds.** The integer wavelet is a bijection; `--recon` minus bias is byte-identical to
`omc_dec`'s output over 7.37 M samples (REPORT §R.0), and the committed picture is
`INV(dequant(q) + escape)`, so `FWD` returns `v_e` exactly.

**(ii) holds only with a corrected definition of "inside bin q" — the bin is not ±s/2.** The
quantiser is `src/internal.h:177`

```c
static inline int32_t omc_quant1b_dz(int32_t c, int s, int texture, int dz_band)
{
    int32_t a = c < 0 ? -c : c;
    int32_t bias = (1 << (s - 1)) + ((texture && s >= 3) ? (1 << (s - 3)) : 0);
    int32_t q = (a + bias) >> s;
    if (dz_band && !texture && q == 1 && ((int64_t)a << 4) < ((int64_t)9 << s)) q = 0;
    return c < 0 ? -q : q;
}
```

and `omc_dequant1(q, s) = q << s` (`omc_recoff` is 0 by default, `src/codec.c:1567`). Three
corrections follow, all in the bands the escape would actually use:

1. **The bin is half-open in the magnitude, not symmetric.** With `bias = 2^(s−1)` the magnitude
   bin of `q` is `[|q|·2^s − 2^(s−1), |q|·2^s + 2^(s−1) − 1]`. So the escape displacement must be
   applied to the **magnitude** (`|v_e| = |q|·2^s + d`), not to the signed value, and its range is
   `d ∈ [−2^(s−1), 2^(s−1) − 1]`. Applying `e·s/2^k` to the signed value, as written, walks a
   negative coefficient out of its bin at the bottom end.
2. **The deadzone lifts the lower edge of bin 1, and it is ON by default in exactly the escape's
   bands.** `dz_band` is `e->dz_enabled && b >= OMC_FILL_BANDS_FROM && omc_dz_on(p,b)`;
   `OMC_FILL_BANDS_FROM = 4` (`src/internal.h:276`), `dz_enabled = 1` unless `--tune vmaf`
   (`src/codec.c:3342`), `omc_dz_plane = 7` and `omc_dz_cto = 9` (`src/codec.c:1098`), so
   `omc_dz_on` is true for every plane and band. For `|q| = 1` the bin is therefore
   `[9·2^s/16, 2^s + 2^(s−1) − 1]` and the safe displacement is `d ∈ [−7·2^s/16, 2^(s−1) − 1]`.
   A symmetric `−s/2` escape on `|q| = 1` **falls into bin 0** — and `|q| = 1` is the single most
   common non-zero index at 0.5 bpp. At `k = 1` this leaves a `|q| = 1` coefficient with **no
   downward escape at all**; at `k = 2` it has one; at `k = 4`, seven of the eight.
3. **The texture bias breaks the symmetry outright under `--tune vmaf`.** There
   `bias = 2^(s−1) + 2^(s−3)` on bands ≥ 4, so the bin runs `[−5/8·s, +3/8·s)` about the
   reconstruction and a `+s/2` escape lands in `q+1`. Not the default path, but it is a supported
   configuration and the escape definition must be written against the bin, not against `s/2`.

All three are fixable by deriving the window from `(q, s, band, deadzone state)` — all of which
both ends already have — rather than from `s` alone. My probe does exactly that
(`sa7_window()` in `ptree/src/latt_probe.inc`), and the measurements below use the corrected
windows.

**A fourth case has no fix and must be excluded: the grain fill.** When `q == 0` in a fill-enabled
band the decoder does not reconstruct 0 at all — it paints `fill_value_p(...)`
(`src/codec.c:8574`). An escape there is undefined, and a non-zero escape would also switch the
fill off, changing the picture a second way. The shipped constructive step already refuses such
moves (`if (nq == 0 && fb) continue;`); the escape must refuse them too. My probe does
(`if (aq == 0 && fb) ...`).

**(iii) holds** once (ii) is stated correctly: the base index is unchanged by construction.

**(iv) is where it breaks, and it breaks in the code, not in the argument.** At generation 2 a
slice does not reach the correction pass by the ordinary route — it reaches it (or rather bypasses
it) through the **T5 lock**, and the lock's verification is `verify_candidate`, `src/codec.c:5326`:

```c
int32_t q = (b == 0) ? omc_quant1b(cf[i], s, 0)
                     : omc_quant1b_dz(cf[i], s, tex_vmaf, e->dz_enabled && ...);
int32_t v = omc_dequant1(q, s);
if (m) v += pc[i];
if (v == e->coef[p][b][i]) continue;
...
okv = 0; break;                       /* candidate rejected */
```

**It demands exact reproduction of every coefficient.** With an escape, `v = dequant(q)` and the
input is `v_e = dequant(q) + d` with `d ≠ 0`, so **every candidate plan is rejected and the slice
does not lock at generation 2.** It then goes through the ordinary rate ladder, whose input is
`v_e` rather than generation 1's source analysis, so it may choose a different `(prof, Q, n_steps,
partial)` — and once the plan moves, the base state moves and the picture moves. S5.176 measured
that the shipped chain locks the picture at generation 2 and the stream at 3; the lock path is
what delivers that, and the escape as specified disables it.

**The fix, and it is small and decidable.** Extend the verification to accept an escape-
representable residual:

```c
int32_t r = e->coef[p][b][i] - v;          /* what the base plan cannot reach */
if (r == 0) continue;
if (escape_representable(r, q, s, band, dz) && n_esc < ESC_MAX) { n_esc++; continue; }
okv = 0; break;
```

where `escape_representable(r, …)` is `r` being a multiple of `2^(s−k)` **and** `v + r` lying
inside the bin window of §7.1(1)-(2). Then:

* at generation 2 the slice locks on the generation-1 plan, the encoder emits the same `q` **and
  the same escapes** (they are the lock residual, which is exactly generation 1's escape set), and
  the committed picture is reproduced — picture locks at generation 2;
* generation 3 sees the same input and the same deterministic candidate order, so it makes the
  same choice — stream locks at generation 3;
* the escape set is bounded by `ESC_MAX`, so the lock path cannot invent an unbounded escape list;
* **the argument no longer needs step (iv) at all.** It does not matter whether the correction
  pass is a pure function of the base state, because at generation 2 the correction pass never
  runs: the lock reproduces the escapes directly from the residual. That is strictly more robust
  than the chain as sent, and it is the version I would build.

**Two further code facts that would have broken step (iv) had we relied on it**, recorded so they
are not rediscovered: the encoder-side `elig` noise-class kill (`src/codec.c:3812`) rewrites `q`
from `|coef[i]|`, and the rate ladder reads the coefficients, not the base state — both see `v_e`
at generation 2 and `a` at generation 1. Both are bypassed on the lock path and only on the lock
path.

**What does *not* need changing.** The coefficient saturation of BITSTREAM §4.2a already budgets
"the dequantiser overshoot `Δ_max/2 = 16384`" into every `W_b`, and `|d| ≤ 2^(s−1) ≤ 16384`, so an
escaped coefficient is **already inside the declared conformance range** — no change to §4.2a, no
change to the datapath widths. And the shipped codec already carries the same in-bin argument for
a different purpose: `omc_dequant1`'s centroid-reconstruction comment (`src/internal.h:226`) says
"with n < 8 the point stays inside its own bin, so re-quantising the reconstruction still yields
q — the generation lock is preserved." The escape is that argument made signalled and per
coefficient.

**Verdict on the lock: it holds, with one code change (the verify) and three corrections to the
bin definition. It does not hold as specified.**
