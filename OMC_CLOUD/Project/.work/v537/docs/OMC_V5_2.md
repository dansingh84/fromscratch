# OMC v5.2 — what changed, why, and what is still open

*Authority for v5.2. `docs/OMC_V5.md` and `docs/OMC_V5_1.md` remain correct as
history and are not superseded in their own scope; where they describe grain-fill
defaults they are superseded by this document. Full record with every
falsification, every rejected option and all raw measurements:
`LEDGER_v5_ADVERSARIAL.md` sections 65–67.*

## 1. The problem this release addresses

At 0.5 bpp the codec was rendering textured regions flat — visibly, in the wood
grain and dark areas of camera-original footage, and worst of all in chroma. The
mandate holder identified it by eye and asserted that earlier versions had been
better at the same bitrate.

**That assertion was correct and was verified by direct measurement.** At an
identical 783,392-byte stream on `dng_1920x1080_422_10`, percentage of textured
blocks rendered flat (frame 2):

| build | Y | Cb | Cr | VMAF-NEG |
|---|---|---|---|---|
| v4.7 / v3.1 | 26.54 % | 42.46 % | 63.57 % | 86.340 |
| v4.14 | 32.95 % | 49.37 % | 65.42 % | 88.051 |
| v5.0 | 56.61 % | 83.30 % | 85.33 % | 88.192 |
| **v5.2** | **16.94 %** | **0.00 %** | **0.00 %** | 87.932 |

Two conclusions, both load-bearing for the rest of this document:

**(a) Flatness was never a bitrate limit.** Every row above is the same number of
bytes. Any claim that flat blocks are "slices that ran out of bits" is refuted by
this table.

**(b) VMAF-NEG rewards flattening.** From v4.7 to v5.0, NEG rose by 1.85 while
luma flatness more than doubled. Regenerated grain is not in the source's exact
position, so a full-reference metric charges it as error and rewards its removal.
A codec tuned on VMAF-NEG alone is under continuous pressure to flatten, and
three releases took that pressure. This is what `PROJECT_CONSTRAINTS.md` §E
exists to prevent, and it is the strongest argument in the record for the eye
being the acceptance test.

## 2. A measurement error that had to be corrected first

`harness/flatpatch.py` reduces each block to one number:

```python
blocks(hp(y), blk) + 0.5*(blocks(hp(cbf), blk) + blocks(hp(crf), blk))
```

A block flat in one plane but textured in another does not cross that threshold.
Once chroma flatness was fixed, the restored chroma energy masked the luma, and
**the tool reported 0.00 % on a decode whose luma was 17.31 % flat.**

This is constraint C5's trap in a new form — not "luma only", but a
luma-dominated *mixture* in which either plane hides the other.

**`harness/flatplane.py`** applies the identical rule, one plane at a time,
against the SOURCE's median, and prints the textured-block count with every
figure:

```
flatplane.py <src.yuv> <dec.yuv> W H frame [--fmt 422] [--depth 10] [--blk 16] [--thr 0.35]
```

**Every per-plane flatness claim must use `flatplane.py`.** `flatpatch.py`
remains valid for what it measures — a combined-energy score — and for its
slice-phase and whole-slice-row analysis.

## 3. The fix: a chroma-specific fill divisor

The grain fill's amplitude is `1 << (s - 2 - div)` where `s` is the band's
quantiser shift. At the shipping `div = 2` that expression rounds away for
`s < 5`, so the band-offer test refuses **every band with `base_s < 6`** and
those bands receive no fill at all. **Chroma's flatness lives precisely in the
`base_s` 4–5 bands.**

The divisor is therefore made per-plane:

```c
int omc_filldiv_c = -1;  /* chroma fill divisor (env OMC_FILLDIV_C); <0 = follow omc_filldiv */
static inline int omc_filldiv_p(int pl)
{
    return (pl != 0 && omc_filldiv_c >= 0) ? omc_filldiv_c : omc_filldiv;
}
```

`fill_value_p()` gains a trailing `int pl`, threaded through the `fill_value_h`
and `fill_value` wrappers to all four call sites — the `lock_verify()` mirror,
the two encoder sites, and **the decoder site, which is the normative one**.
`fill_gain_code()` takes the same parameter so each plane's gain shifts by its
own divisor. The lattice admission window uses `omc_filldiv_p(p)`.

### Why the plane index, and not something else

**This is the central design constraint of the release.** Any quantity the fill
amplitude keys on must be **invariant between generations**, or A4 fails.

* The **plane index** is invariant. ✔
* The **quantiser shift `s`** is not — the temporal calm kill moves it. A divisor
  keyed on `s` (built as `OMC_DIVEFF`) clamps at `s - 3`, making the amplitude
  non-linear in `s` across that boundary, which breaks the gain fixed point and
  fails `G-T5-CALM2a/2b`.
* The **band mode** is not — it is a rate-distortion decision that flips on
  rate-control noise even on a frozen source.

Within a plane the amplitude stays linear in `s`, so a shift change moves it by a
matching power of two and the gain fixed point absorbs it exactly as before.

## 4. Defaults

| symbol | value | note |
|---|---|---|
| `omc_filldiv` | 2 | luma, quarter-step nominal |
| `omc_filldiv_c` | **1** | **chroma — new in v5.2** |
| `omc_fillthr` | **1** | **not 0** — 0 breaks A4, §5 below |
| `omc_fillintra` | **0** | the latch off |
| `omc_antsgate` | **0** | 24 and 48 both cost chroma flatness for no crawl gain |
| `cfg.fill_grain` | on unless `lossless_pref` | `OMC_FILL=0` restores v5.0 |

Restore v5.0 exactly:

```
OMC_FILL=0 OMC_FILLINTRA=0 OMC_ANTSGATE=24 OMC_FILLTHR=3 OMC_FILLDIV=0 OMC_FILLDIV_C=-1
```

Gate `G-T5-RESTORE` asserts this mechanically against
`delivery/conformance/vectors/c5_v50_restore_rail.omc`.

## 5. `OMC_FILLTHR=0` breaks A4 — a regression caught in development

An intermediate default of `omc_fillthr = 0` reached 0.00 % chroma flatness on
every arm and **failed A4 at generation 2** on `cf_gfx_448x256_422_10`.
Isolation, 11-generation chains:

| configuration | A4 |
|---|---|
| v5.0 restore | PASS |
| `FILLTHR=1 FILLINTRA=1` | PASS |
| `FILLTHR=1 FILLINTRA=0` | PASS |
| `FILLTHR=0 FILLINTRA=1` | **FAIL** |
| `FILLTHR=0 FILLINTRA=0` | **FAIL** |

`omc_fillthr` is the fill-bit threshold in sixteenths of a step. At 0 the test is
vacuous and every band is offered a fill bit, including bands of essentially zero
energy — where the synthetic grain, not the source, decides the quantised value
on re-encode. A nonzero threshold keeps the fill subordinate to real content,
which is what the lattice argument assumes. **A per-plane threshold does not
help: `FILLTHR_C=0` on chroma alone fails the same way.**

## 6. Known defect, open: luma flatness is not zero

`dng` 16.94 %, `bosphorus` 3.30 %, `cityalley` 1.14 %.

**The mechanism is proved.** In the in-gamut repair:

```c
if (b >= OMC_FILL_BANDS_FROM)
    gm_nofill |= 1u << (p * 6 + b - OMC_FILL_BANDS_FROM);
```

If the repair touches **one coefficient** in a fill-eligible band, grain fill is
disabled for that **entire band**. A louder fill drives more samples toward the
rails, the repair fires on more bands, and each firing costs a whole band its
texture — so **a louder fill produces more flatness**, measured:

| fixed amplitude | `dng` Y flat | NEG |
|---|---|---|
| 4 (derived) | 16.76 % | 87.785 |
| 8 | 16.09 % | 87.820 |
| 16 | 25.65 % | 87.131 |
| 32 | 54.83 % | 86.818 |
| 64 | 57.69 % | 85.111 |

Lifting the veto (`OMC_GM_KEEPFILL=1`) takes `dng` luma to **0.07 %** with
`oob = 0` and decoded samples inside `[1, 1023]` — and **fails A4 at generation 2
on every cell tested**. The veto is an **A4 convergence device**, not a gamut
device: a repaired coefficient is off the `q << s` lattice the fill's exactness
argument depends on, and fill on such a band can leave a sample near a rail that
the next generation repairs differently.

Three candidate directions, none built:

1. **Repair with a fill margin** — shrink to `[lo + a, hi - a]` on fill-eligible
   bands so the fill cannot approach a rail, then drop the veto.
2. **Confine the repair to the coarse bands** (`b < OMC_FILL_BANDS_FROM`) with a
   fallback, so the common case never vetoes a fill band.
3. **Re-lattice after repair** — snap the repaired coefficient back onto `q << s`
   for the new `q`, restoring the property the fill's A4 argument needs. Most
   principled; attacks the cause rather than avoiding it.

## 7. Switches retained as evidence, all default-off

| switch | tried | outcome |
|---|---|---|
| `OMC_DIVEFF` | divisor keyed on the shift | 2 gate failures — §3 |
| `OMC_FILLMIN1` | admit amplitude 1 code | 5 gate failures; reproduces the v4.6 taper defect |
| `OMC_GM_KEEPFILL` | drop the repair's fill veto | `dng` 16.76 → 0.07 %, fails A4 — §6 |
| `OMC_ODCAP` | restore the half-slice banking overdraft | +0.002…+0.710 NEG at unchanged byte count; costs up to +0.185 ms of A2. **Rejected — no latency change is permitted** |

Each is byte-inert at its default: with the switch off the encoder output is
identical to the tree without the patch, verified by md5.

## 8. What is not changed

The reconstruction rule (`q << s`); the CDR guarantee; exact CBR; `rt = 0`; the
latency model; the temporal engine; the transform; the entropy coder; the
banking prefix bound, still `(k+1) * bits_per_slice` with no overdraft.
