# Handoff — bit exactness across generations

> **STATUS in v5.0: superseded.** The conditional case this document describes — a baseband hand-off exact only while no committed sample leaves the legal range — is closed in v5 by the strict in-gamut repair, on by default. See `docs/TEMPORAL_T5.md` 12.22.


**To:** the team taking on generation-loss research
**From:** the 2026-08-12 OMC session
**Companion artefacts:** `omc_v4.14_20260812.zip` (the codec),
`SESSION_LEDGER_2026-08-12.md` (everything else)

---

## 1. The goal, stated precisely

**From the first decode onward, the picture must never change again.**

Decode a stream once. That decoded picture is the reference. Re-encode it,
decode it, and you must get **the same picture, byte for byte**. Do it ten more
times and you must still get the same picture. The first decode is where quality
is allowed to be lost, and it is the *last* place — every generation after it is
free.

Writing `E` for encode and `D` for decode, and `D1 = D(E(x))` for that first
decode:

```
required:   D(E(D1)) == D1               and therefore, by induction,
            D(E(D(E(...D1...)))) == D1   for any number of generations
```

Two consequences worth stating, because both have been got wrong in this project
and once in this document:

1. **The bitstreams from generation 2 onward are identical too.** If `D(E(D1)) ==
   D1` then generation 3 encodes exactly what generation 2 encoded, so
   `E(D(E(D1))) == E(D1)`. Stream equality from generation 2 is a *consequence*
   of the goal, and a fair way to test it.
2. **Generation 1's stream is NOT expected to equal generation 2's.** Generation
   1 encodes the master; generation 2 encodes a decode. They have different
   inputs and there is no reason for them to match, in this codec or any other.
   An earlier version of this document compared exactly those two and concluded
   the codec "never" reaches exactness. That comparison was meaningless — see
   §2.4. **Do not repeat it.**

So the tests that mean something are:

| test | what it establishes |
|---|---|
| `D(E(D1)) == D1` | the goal itself — the fixed point is reached at the first decode |
| `E(D(E(D1))) == E(D1)` | the fixed point holds, checked on the stream |
| per-slice lock count | *how far* from the goal, when it is not met |

This is exactly what the project's own gate asserts —
`tests/test_acceptance.py::test_generations_byte_stable` compares the **decoded
output** of generations 2 through 5 against generation 1's decoded output — and
it is the definition used everywhere below.

The codec already has the machinery for it. It is called the **generation lock**:
before coding a slice, the encoder tries to prove that its input slice *is* a
reconstruction it could have produced, and if it proves it, re-emits the previous
plan verbatim (`lock_verify` in `src/codec.c`). The lock exists and fires. It
does not fire often enough, and on some content it does not fire at all.

---

## 2. Where things actually stand — measured, all of it

### 2.0 The project already claims this, its own gate tests it, and that gate fails

Before anything else, the documentation. Four documents state the guarantee:

| document | claim |
|---|---|
| `docs/DESIGN.md` §5 | "Measured: generations 2–5 byte-identical to generation 1 on all planes (`tests/test_acceptance.py::test_generations_byte_stable`)" |
| `docs/DESIGN.md` §7 | "all slices lock on generation 2+, outputs byte-identical through generation 5" |
| `docs/EXECUTIVE_SUMMARY.md` | "copies of copies are bit-for-bit identical from the second generation on" |
| `docs/FEASIBILITY.md` | "generations 2–5 byte-identical to generation 1" |
| `docs/FEATURE_MATRIX.md` | the careful version: "byte-exact from gen 2 **(statics)**; convergent on pans/heavy grain" |

**The gate exists, and it fails.**

```
$ OMC_SCRATCH=<real masters> python3 -m pytest tests/test_acceptance.py -q
    AssertionError: generation 2 != generation 1
    At index 198 diff: b'\xcb' != b'\xca'
    1 failed, 8 passed in 41.73s
```

Only that one gate fails; the other eight acceptance gates pass, including
`rt = 0`. So encoder and decoder agree with each other perfectly — the fault is
entirely in **re-encoding a decode**, not in the codec's internal consistency.

**It is not a regression.** The same gate fails identically on the pristine
`omc_v4.9_full_20260811.zip`, on the tree this session inherited, and on the
delivered v4.14. It has been failing at least since the archive was cut.

**It failed silently because the gate was inert.** `MASTERS_DIR` derives from
`OMC_SCRATCH`, which defaults to a scratch path belonging to a different machine.
On any other machine `pytest` reports `1 skipped`, not `1 failed`. **Point
`OMC_SCRATCH` at real masters before believing any acceptance result.**

### 2.1 It fails on static content too — so this is not the seam edit

`FEATURE_MATRIX.md` reserves byte-exactness for statics. Built a genuinely static
clip (alpine frame 0 repeated five times) and ran the chain:

| arm | out2 == out1 | samples differing at gen 2 | worst |
|---|---|---|---|
| defaults (XSL level 3) | **no** | 19.44% | 20 codes |
| XSL off | **no** | **19.44%** | 20 codes |

**Identical with the seam edit switched off**, and the per-slice lock fires
27/360 either way. On this clip and these settings the cross-slice edit is not
the differentiator at all. It is a large contributor in the configurations of
§3.3, but there is a **baseline failure underneath it that has nothing to do with
it**, and that baseline is the bigger problem.

### 2.2 Generations converge; they do not accumulate

alpine, 2048×1152, 2.0 bpp, defaults:

| comparison | samples differing | worst | mean of non-zero |
|---|---|---|---|
| gen 2 vs gen 1 | 26.76% | 19 codes | 1.39 |
| gen 3 vs gen 2 | 4.62% | 8 codes | 1.16 |

Sixfold reduction per generation. So `FEATURE_MATRIX.md`'s "convergent,
non-accumulating" is supported; the byte-exact claims in the other three
documents are not. **The documentation is internally inconsistent and the
optimistic version is the one in the executive summary.**

### 2.3 Per-slice lock rate across resolutions

The sweep below measures how many slices the encoder recognises as its own
previous output. **The `id` column of the first version of this table was
meaningless and has been removed** — see §2.4.

| master | geometry | bpp | edit ON (shipped) | edit OFF |
|---|---|---|---|---|
| heli | 1920×1080 4:2:2 | 0.5 | 0/68 | 0/68 |
| beach | 1920×1080 4:2:2 | 0.5 | 0/68 | 0/68 |
| city | 1920×1080 4:2:2 | 0.5 | 0/68 | 0/68 |
| heli | 2048×1152 4:2:2 | 0.5 | 0/72 | 1/72 |
| beachbox | 2048×1152 4:2:2 | 0.5 | 0/72 | 0/72 |
| dngA4 | 3840×2160 4:2:2 | 0.5 | 0/135 | 0/135 |
| beach444 | 1920×1080 4:4:4 | 0.5 | 0/68 | 0/68 |
| heli | 1920×1080 4:2:2 | 1.0 | 0/68 | **13/68** |
| beach | 1920×1080 4:2:2 | 1.0 | 0/68 | **8/68** |
| city | 1920×1080 4:2:2 | 1.0 | 0/68 | 0/68 |
| heli | 2048×1152 4:2:2 | 1.0 | 0/72 | **16/72** |
| beachbox | 2048×1152 4:2:2 | 1.0 | 0/72 | **4/72** |
| dngA4 | 3840×2160 4:2:2 | 1.0 | 0/135 | 0/135 |
| beach444 | 1920×1080 4:4:4 | 1.0 | 0/68 | **6/68** |
| heli | 1920×1080 4:2:2 | 3.0 | 0/68 | **26/68** |
| beach | 1920×1080 4:2:2 | 3.0 | 0/68 | **19/68** |
| city | 1920×1080 4:2:2 | 3.0 | 0/68 | 0/68 |
| heli | 2048×1152 4:2:2 | 3.0 | 0/72 | **28/72** |
| beachbox | 2048×1152 4:2:2 | 3.0 | 0/72 | **17/72** |
| dngA4 | 3840×2160 4:2:2 | 3.0 | 0/135 | 0/135 |
| beach444 | 1920×1080 4:4:4 | 3.0 | 0/68 | **13/68** |

*(These runs carry the session's tuning environment — `OMC_RBOOST=50
OMC_TAILGUARD=2 OMC_FILLHYST=2 OMC_SPC=4 OMC_FORCE_PROF=2 OMC_ALLOC=2
OMC_DCFB=3 OMC_NO_DECL=1`. Under plain defaults on alpine the edit made no
difference to the lock at all (§2.1), so **the edit's effect on the lock is
configuration-dependent and that dependence has not been mapped.** Doing so is
worth an afternoon.)*

**What holds from it:** the lock strengthens sharply with rate (0 at 0.5 bpp,
up to 28/72 at 3.0), and content dominates resolution — `city` scores 0 at every
rate at 1080p while `heli` scores 26/68 at the same geometry. The 4K master
scores 0 everywhere but is grainy camera-raw material like `city`, so
**resolution and content are confounded above 1080p; there is no clean-content 4K
master in the corpus.** No conclusion about 4K is safe until there is one.

Even at the best measured lock rate — 28 of 72 slices — the other 44 differ, so
the frame differs. **Nothing measured in this session reached byte exactness at
any resolution.**

### 2.4 A methodological correction, stated plainly

The first version of this document reported "42 configurations, 42 × not
byte-identical" from a column comparing **generation 1's bitstream with
generation 2's**. Those two encode *different inputs* — generation 1 encodes the
master, generation 2 encodes a decode — so they were never expected to match,
even in the ideal case. The comparison was meaningless and the "never" conclusion
drawn from it was not supported by it.

The correct tests, and the ones used above, are the project's own: **does
generation 2's decoded output equal generation 1's** (the fixed point), and
**does generation 3's bitstream equal generation 2's** (the fixed point holding).
The conclusion happens to survive the correction — nothing reached exactness —
but it now rests on the right measurement.

---

## 3. Why the lock fails — mechanism, not speculation

### 3.1 What the lock needs

OMC's wavelet is exactly reversible and the quantiser is a power-of-two shift.
So a decoded picture, re-transformed, yields coefficients that are **exact
multiples of their band's quantiser step**. Natural camera content never is:
`DESIGN.md` §5 states that first-generation content never has ≥4 non-empty
lattice-aligned bands, and the measurement holds — 0.00% of bands on a master
versus 82–100% on a clean decode.

The encoder detects that lattice, reads off the exponent, reconstructs the
candidate plan, and `lock_verify` demands bit-exact reproduction before using it.

**So the lock needs the input picture to still be on the quantiser lattice.**
Everything below is a way of falling off it.

### 3.2 Cause 0 — whatever breaks it on static content with the edit off (UNIDENTIFIED, and the largest)

§2.1 is the uncomfortable one: a still frame, coded five times, at 2.0 bpp, with
the seam edit disabled, still fails to reach a fixed point — 19.4% of samples
move at generation 2, worst 20 codes, and the lock fires on 27 of 360 slices.
`rt = 0` holds, so the encoder and decoder agree; the failure is in re-encoding.

**This is not diagnosed. It should be the first thing anyone works on**, because
everything in §3.3 onward is a contribution *on top of* a baseline that already
fails. The documentation asserts this case works; the project's own gate says it
does not; and the gate was never running.

### 3.3 Cause 1 — the seam edit knocks the picture off the lattice (identified, quantified, configuration-dependent)

The shipped boundary edit (XSL level 3, `docs/XSL.md`) rewrites rows 0 and 15 of
every slice **after** the inverse transform, by up to 4–8 codes. The wavelet
mixes rows within a slice, so perturbing two of sixteen moves coefficients right
across that slice's band structure — by sub-step amounts, which is exactly what
takes them off the lattice.

Measured, six generations, PSNR-Y:

| content / rate | no edit | level 3 (shipped) |
|---|---|---|
| beach 3.0 bpp sh 8 | −0.30 dB | **−8.17 dB** |
| beach 1.0 bpp sh 16 | −0.37 dB | **−1.26 dB** |
| beach 0.5 bpp sh 16 | −0.64 dB | −0.93 dB |
| city 0.5 bpp sh 16 | −0.61 dB | −0.48 dB |

The edit fires on 2 rows in 16 and costs, at worst, **7.9 dB over six
generations**. It is the highest-leverage single item in this document.

### 3.4 Cause 2 — the lock is absent at low rate even with nothing in the way

At 0.5 bpp the ceiling is 0–1 slices out of 68–135 on every master tested. The
seam edit is irrelevant there; the lock simply is not firing.

The likely mechanism (**not yet confirmed — this is the main open question**):
at coarse quantisation, many bands quantise to zero or to a single significant
bit, so the lattice exponent is unidentifiable — there is no evidence left to
read. `DESIGN.md`'s "≥4 non-empty lattice-aligned bands" threshold cannot be met
if there are not 4 non-empty bands. **This has not been instrumented.** The first
diagnostic to build is a per-slice report of how many non-empty bands there were
and how many were lattice-aligned, at 0.5 versus 3.0 bpp. If the count of
non-empty bands is the binding constraint, the threshold rule needs rethinking
for low rate, not the detector.

### 3.5 Cause 3 — the rest of the plan must also reproduce

`lock_verify` demands bit-exact reproduction of the *whole slice*, which means
the profile, quantiser, refinement-step count, fill mask and fill gains all have
to come out the same. Several of these are chosen by searches driven by
rate-control state, and rate-control state depends on what earlier slices spent —
which differs the moment any one slice differs. **This is a plausible cascade
that has not been isolated.** It would explain why locks come in runs and why
even 28/72 never becomes 72/72.

Diagnostic to build: with the seam edit off, log for each *failed* lock which
component of the plan mismatched. If it is dominated by rate-control-derived
fields, the cascade is real and the fix is upstream of the detector.

---

## 4. What was tried, and what happened

### 4.1 Tried and works — the reversible boundary edit (XSL level 7)

**Idea.** The level-3 edit moves each row *toward a target computed from that
row's own value*, which discards the row's previous value and cannot be undone.
Replace it with a lifting cascade, where each step adds a correction built only
from rows it does not touch:

```
forward   step 1   row15 += clamp((row0   - row14) / 4, ±lim)   /* row15 unread */
          step 2   row0  += clamp((row15' - row1 ) / 4, ±lim)   /* row0  unread */
inverse            row0  -= clamp((row15' - row1 ) / 4, ±lim)
                   row15 -= clamp((row0   - row14) / 4, ±lim)
```

A later encoder calls `omc_xsl_unblend()` on its input, recovers the exact
reconstruction its predecessor coded, locks onto it, codes it, and the decoder
re-applies the edit on output. **One edit in the chain instead of one per
generation.**

**Status: built, in the delivered zip, experimental, off by default.** Reachable
with `OMC_XSL=7`; encoder-side un-blend with `OMC_XSL_UNBLEND=1`.

| claim | evidence |
|---|---|
| the inverse is exact | gate `G-XSL2`, and on a 1080p decode: 314,036 samples edited, every one recovered byte-exactly |
| it repairs the seam | 0.5 bpp step excess: level 3 gives city +6.831 / beach +2.489 / heli +1.029; level 7 gives +6.978 / +2.903 / +1.193 |
| it restores locking | beach 3.0 bpp sh 8: 0/270 → 31–34/270 (ceiling 73/270) |
| it removes most of the loss | beach 3.0 bpp: −8.17 dB → **−1.81 dB** (ceiling −0.30). beach 1.0 bpp: −1.26 dB → **−0.45 dB** (ceiling −0.37) |

**Its two unsolved problems:**

1. **It needs a detector.** An encoder that always un-blends also un-blends
   first-generation material, where there was nothing to undo; the decoder
   re-applies the edit and the two cancel, costing about a third of the seam
   repair (beach 0.5 bpp: +2.903 → +4.873). The numbers above use an **oracle**
   — the encoder was simply told. A detector is costly when wrong in either
   direction. The natural detector is "un-blend, then test the lattice", and it
   should work *because* the edit is now invertible, but it has not been built.
2. **Exactness is verified intra-only.** The edit is in-loop, so two decodes of
   one stream diverge from frame 1 onward through prediction. Verifying an inter
   frame needs that decode's own pre-edit reconstruction, which the decoder does
   not expose. **Adding that hook is a small, high-value piece of work.**

### 4.2 Tried and rejected — self-detection under the irreversible edit

Detecting "am I looking at my own output?" directly from the lattice, with the
shipped level-3 edit in place. **The edit erases its own fingerprint:** 0.00% of
bands lattice-aligned on source, 82–100% on a decode with the edit off, and only
**0.03–0.38%** with it on. Rejected on measurement.

### 4.3 Tried and rejected — frame-scoped locking

Proposed and then retracted by its own author (me) before implementation: it
assumed the fingerprint survived within a frame, which 4.2 disproves.

### 4.4 Tried and rejected — pre-blending instead of post-editing

Apply the smoothing to the picture *before* coding, so it is carried in the coded
signal rather than as an edit afterwards; then there is nothing to undo.
**Arithmetically impossible at the relevant rates:** the smoothing moves rows by
up to 4 codes while the affected bands have quantiser steps of 16–64. The
correction is finer than one quantiser step, so it cannot be expressed in the
coded signal at all. This is why it is a post-edit in the first place.

### 4.5 Tried, works, but narrower than it first appeared — the rate threshold

The un-repaired seam ridge collapses with rate. As a multiple of the step inside
the slice (1.000 = the join is no worse than the picture around it):

| clip | 0.5 bpp | 1.0 bpp | 2.0 bpp | 3.0 bpp |
|---|---|---|---|---|
| city | 1.824 | 1.269 | 1.067 | 1.013 |
| beach | 1.705 | 1.294 | 1.048 | 1.021 |

Above ~1.5 bpp there is no ridge to repair, both level 3 and level 7 *overshoot*
(joins end up 1.4–3.1 codes smoother than the surrounding picture), and the lock
is at its strongest. Switching the edit off above a rate threshold therefore buys
the lock back for free up there.

**But it does not help where OMC lives.** At ~1.0 bpp the ridge is still 1.27–1.29×
and cannot be switched off, while the lock has already started firing (8–16 of
68–72 slices) and the edit still annihilates it. That band needs the reversible
edit or something else. **Do not treat the threshold as a solution to this
problem** — it is a worthwhile simplification at high rate and nothing more.
Registered as `XSL-RATE-OFF` in `OPEN_DECISIONS.md`; needs an eye check that the
joins really are invisible unrepaired at 1.5–2.0 bpp.

### 4.6 Tried and rejected as a framing — "put the generation problem inside the coding loop"

It is already inside the loop; that is the cause, not the cure. The edit is
in-loop by design so both ends stay in step, and being in-loop is exactly what
makes it accumulate across re-encodes.

---

## 5. Recommended order of work

0. **Make the gate run, and keep it running.** `test_generations_byte_stable`
   has been silently skipping. Give `OMC_SCRATCH` a real default or make a
   missing masters directory an error rather than a skip. A gate that skips is
   worse than no gate: it reads as green.
1. **Diagnose §3.2 before anything else** — static content, seam edit off, still
   not reaching a fixed point. Everything else is a refinement on top of it.
2. **Reconcile the documentation with the measurement.** `DESIGN.md` §5 and §7,
   `EXECUTIVE_SUMMARY.md` and `FEASIBILITY.md` state byte-exactness as measured
   fact; `FEATURE_MATRIX.md` states the weaker convergent claim; the measurement
   supports only the weaker one. Whichever way it is resolved, four documents
   currently mislead.
3. **Instrument before building anything else.** Two diagnostics, both small:
   (a) per-slice non-empty band count and lattice-aligned count, at 0.5 vs 3.0 bpp
   — tests §3.4;
   (b) for each failed lock, which plan component mismatched — tests §3.5.
   Everything below is guesswork until these exist.
4. **Get a clean-content 4K master.** Resolution and content are confounded
   above 1080p (§2, fact 4). No conclusion about 4K is safe until this is fixed.
5. **Expose the pre-edit reconstruction** from a decode, so level-7 exactness can
   be verified on inter frames rather than intra-only (§4.1, limit 2).
6. **Build the "un-blend then test the lattice" detector** and measure its error
   rate in both directions (§4.1, limit 1). It is the only missing piece between
   the oracle results and a shipping feature.
7. **Then, and only then**, decide between: reversible edit everywhere; reversible
   edit below the rate threshold and no edit above it; or something new that
   §3.3/§3.4 suggest.

**A caution on measurement.** Three separate results in this session were invalid
for reasons that were invisible until instrumented: a build script that did not
check its compiles, a "ground truth" that was not one, and a test that could not
fail. Before trusting any generation number, confirm the arm you think you ran is
the arm that ran. `OMC_DEBUG_LOCK=1` and `OMC_DEBUG_L7=1` exist for that.

---

## 6. Everything you need, by name

| item | where |
|---|---|
| the codec | `omc_v4.14_20260812.zip` |
| cross-slice design, levels, caps, barriers | `docs/XSL.md` |
| the reversible edit and its inverse | `src/codec.c`, `omc_xsl_unblend()` |
| the exactness gate | `tests/test_xsl.c`, `G-XSL2` |
| the cap-scope gate | `tests/test_cap.c` |
| apply the inverse to a raw file | `tools/omc_unblend_tool.c` |
| the lattice probe | ledger Part S, `probe.c` |
| every script that produced every number here | ledger Part S |
| every measurement, including the discarded ones | ledger Part M and Part F |
| open items with the hook that will speak up | `OPEN_DECISIONS.md` |
