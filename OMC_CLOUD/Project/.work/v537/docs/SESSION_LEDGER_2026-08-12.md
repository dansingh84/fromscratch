# OMC SESSION LEDGER — 2026-08-11 / 2026-08-12
## Self-contained record of everything built, tested, falsified and shipped since v4.9

**Companion artefact:** `omc_v4.9_full_20260811.zip` (SHA below). Everything in
this document is expressed as a change *to that archive*. With the archive and
this document alone you can rebuild the delivered `omc_v4.14_20260812.zip`
byte-for-byte in behaviour, re-run every measurement, and check every claim.

**How to use this document**

| you want to | go to |
|---|---|
| rebuild the code | Part A (build), Part R (the complete patches) |
| re-run a measurement | Part S (every script, in full) |
| check a number | Part M (every result table) |
| know what was tried and failed | Part F (falsifications) |
| know what is still open | Part O |
| understand the generation problem | Part G, and `HANDOFF_BIT_EXACTNESS.md` |
| read the session as it happened, in full detail | Part N (Parts 0–XXVI as kept during the session) |
| verify this document is complete | Part V |

**One external reference.** Part F.13 cites
`new_ideas/08112026/SESSION_LEDGER_FULL.md`, a document from the input material
that was given to me to review. It is cited as the source of a lesson, not
needed to build or check anything here. Every other file this document names is
either reproduced in full below or present in one of the two zips.

---

# PART 0 — Provenance, and an honest boundary

Three trees are involved. Confusing them wasted real time, so they are named
once here and used consistently.

| name | what it is |
|---|---|
| **v4.9** | `omc_v4.9_full_20260811.zip`, the archive. The baseline for this document. |
| **inherited** | the working tree as I found it: v4.9 plus ~14 hours of work by others (grain-fill correction `omc_fillcorr`, `omc_recoff`, `omc_fc_tot`, the fill-probe hints, and scaler edits). **I did not write this and do not claim it.** |
| **delivered** | `omc_v4.14_20260812.zip`, the tree at the end of this session. |

The two patch sets in Part R are split on exactly that boundary:
`R.1` is v4.9 → inherited (**not mine**), `R.2` is inherited → delivered (**mine**).

The archive was verified byte-identical to the copy Dan re-uploaded, and the
pristine reference used throughout matched it.

---

# PART A — Building

No `make` is required (the session used `zig cc` as a hermetic compiler), but the
Makefile in the delivered zip is complete and `make && make test` works.

```bash
# 1. start from the archive
unzip omc_v4.9_full_20260811.zip
cd .work/final/omc_v4.9

# 2. apply the two patches from Part R, in order
patch -p1 < R1_inherited.patch     # v4.9 -> the tree I inherited (not my work)
patch -p1 < R2_session.patch       # -> the delivered v4.14

# 3. build and gate
make
make test          # test_unit test_uc test_tf test_cc test_cap test_xsl
```

The session's own build script, which compiles without make and — critically —
**checks every background compile** (an earlier version did not, printed
BUILD-OK over a failed compile, left a stale binary, and produced one
meaningless byte-identity result):


```bash
#!/bin/bash
set -eu
CC=[machine-path-redacted]/.work/tools/zcc
CFLAGS="-O2 -g -std=c11 -Wall -Wextra -Iinclude"
cd "$1"
SRC="src/dwt.c src/tans.c src/bitio.c src/alloc.c src/codec.c src/tables.c src/config.c src/upconv.c src/tfilt.c src/colour.c"
OBJ=""
pids=""
for f in $SRC; do o="${f%.c}.o"; $CC $CFLAGS -c "$f" -o "$o" & pids="$pids $!"; OBJ="$OBJ $o"; done
for pid in $pids; do wait $pid || { echo "COMPILE FAILED"; exit 1; }; done
pids=""
for t in omc_enc omc_dec omc_uc_tool omc_tf_tool omc_unblend_tool; do $CC $CFLAGS tools/$t.c $OBJ -o $t -lm & pids="$pids $!"; done
for t in test_unit test_uc test_tf test_cc; do $CC $CFLAGS tests/$t.c $OBJ -o $t -lm & pids="$pids $!"; done
for pid in $pids; do wait $pid || { echo "LINK FAILED"; exit 1; }; done
echo BUILD-OK
```

---

# PART C — What changed in the codec, and why (narrative)

Each item states the change, the evidence, and the thing in the build that now
asserts it. An item with no asserting artefact is marked as such.

## C.1 `slice_h` default 8 → 16

**Change.** `slice_h` defaults to 16 luma lines; 720p and below stay at 8 for the
A2 latency bound. 8 / 16 / 32 are all user-selectable.

**Why.** The slice header is a fixed cost per slice; halving the slice count
halves it, and larger slices give the wavelet more vertical support.

**Measured** (1920×1080 4:2:2 10-bit, production width):

| rate | bitrate saved by 16 over 8 |
|---|---|
| 0.5 bpp | **15.8%** |
| 1.0 bpp | **10.1%** |
| 2.0 bpp | **8.1%** |

**Cost.** 1080 is not a multiple of 16, so the coded raster becomes 1088 and the
extra 8 lines are padded and cropped on output (`display_height`). At 2160 the
coded raster becomes 2176. The rate figures above already carry that cost.

**Asserted by.** `docs/BITSTREAM.md` §7 table, `LATENCY.md`, `README.md`, and the
config validator, which accepts only 8/16/32.

## C.2 The blend cap became per-context, and its threshold was corrected

**Two separate faults, found by review and by measurement.**

**Fault 1 (CRITICAL).** The cap was a process-wide global. A multi-channel server
runs several encoders at different rates in one process; the last context created
would decide the blend for all of them, and a stream encoded under one cap does
not reconstruct under another. Moved into `ctx_common_t`.

**Fault 2.** The threshold `4·bits_per_slice < 3·px` counted luma samples only, so
4:4:4 — which codes three full planes — was tested against a luma-only budget and
landed on the wrong side. Corrected to count **coded samples**:

```c
return (8 * (int64_t)cfg->bits_per_slice
        < 3 * px * (cfg->chroma == OMC_CF_444 ? 3 : 2))
       ? OMC_XSL_LIM_MINOR9 : 4;
```

0.75 bpp at 4:2:2 is unchanged; 4:4:4 now switches at 1.125 bpp, which is the
same amount of information per coded sample.

**The cap values themselves are eye-approved**, not derived: cap 8 below the
threshold, cap 4 above, chosen in a three-arm blind comparison of caps 4/8/16.

**Asserted by.** `tests/test_cap.c` — builds two contexts at different rates in
one process, interleaves their frames, and requires each to produce exactly what
it produces alone **and to round-trip through its own decoder**. The first
version of this test compared bitstreams only and passed on the broken tree; it
compares reconstructions now.

## C.3 Banking overdraft removed

**Change.** The `B/2` prefix allowance is gone, and there is no knob for it.
`avail_prefix = slice_idx·B + B − spent`.

**Why.** It complicated the latency model and the exact-CBR argument for a
benefit that did not survive review. Removed after Dan reviewed the pictures.

**Asserted by.** The A2 latency guard in `src/config.c` no longer carries the
overdraft term, so re-introducing it would break the bound the guard enforces.

## C.4 Output-stage latency is raster-clocked

**Change.** `omc_uc_scale_latency_ex()` charges the resampler by the **lines** it
must wait for (`reach`), not by whole slice periods.

**Why.** The converter is a streaming line buffer clocked at the destination
raster rate. Charging `ceil(reach/slice_h)` whole slice periods over-charges it —
badly, at large `slice_h`.

**Asserted by.** Gate **G21** in `tests/test_uc.c` — 165 geometries, each
simulated row by row against the bound, 0 over.

## C.5 The two sample-siting conventions, separated

**Change.** `OMC_SITE_CENTRE` and `OMC_SITE_COSITED` are explicit;
`omc_uc_scale_plane_sited()` takes one. The 4:2:2 chroma detour asks for
**co-sited**; picture resizing uses **centred**.

**Why.** Centre alignment is correct when resizing a picture and wrong for the
chroma detour, which must land chroma samples on their luma. The rational path
had been re-centred for picture resizing and the chroma detour went with it,
putting colour a quarter sample off its luma and doubling the round-trip loss.

**Measured.** Co-sited needs **0 of 16,384** runtime-derived coefficients versus
centred's 8,192 — clearing `C3_AUDIT` H-1 for the chroma path. Colour gate 8c
back to 0.02 / worst 2.

**Asserted by.** Gate **G22** in `tests/test_uc.c` — resamples a ramp and reads
the sample positions off the values: co-sited must put output 40 at source
20.000; centred must put it at 19.750 with output 41 at 20.250.

**This one deserves emphasis.** The distinction had been made before, written
down in a session ledger, and lost anyway. A comment did not prevent it. That is
why the rule is now a test.

## C.6 XSL level 6 and `--xsl auto`

**Level 6** measures the actual step at each join and applies full blend strength
only where a step is present. Repairs as well as level 3, cuts the worst
generation loss to −3.34 dB, and is immune to the scene cut that defeats
`--xsl auto`.

**`--xsl auto`** probes frame 0 and picks a level. **Demonstrated defeated by a
scene cut** — the probe's frame is not representative of the rest. Kept as an
explicit option; not a default.

## C.7 XSL level 7 — the reversible boundary edit (experimental)

Full treatment in `docs/XSL.md` and `HANDOFF_BIT_EXACTNESS.md`. Summary: the edit
rewritten as two lifting steps in a fixed order, each reading only rows it does
not touch, so `omc_xsl_unblend()` recovers the original exactly. Off by default;
reachable with `OMC_XSL=7`.

**Asserted by.** Gate `G-XSL2` in `tests/test_xsl.c`.

---

---

# PART N — The session as it was written, in full

What follows is the working ledger exactly as it was kept during the session,
Parts 0 through XXVI. Part C above is a summary of the changes; **this is the
detail behind them** — the slice-height study re-measured at 30x the data, the
latency work, the entropy-layer results, the half-rate comparison against the
incumbent, the overdraft pricing, the colour fault, and every decision with who
took it. Nothing here is superseded by the parts above; where the two differ, the
later correction is Part F.

Its internal Part numbering is its own and does not correspond to the letters
used elsewhere in this document.

## OMC session ledger — 2026-08-11 → 12

**Self-contained.** With this document and `Codec/Current/omc_v4.10_20260812.zip`
you have everything: what was tested, every number, every code change, every
falsification (the study's, the codec's, and mine), every decision and who took
it, and how to reproduce all of it. Nothing here is quoted from memory; every
figure was produced this session on the machine.

**The job:** test everything in `new_ideas/08112026` — the JPEG 2000 study and
the write-up bundle — in extreme detail; check nothing breaks; look for
improvements beyond what was proposed; adversarially review; report.

---

## PART 0 — Environment, trees and discipline

## 0.1 Build

No system compiler and no `make` on this host. The project's own toolchain
(`.work/tools/zcc` → zig cc) was used with a hand-written build script,
`.work/ni0811/build.sh`, that reproduces the archive `Makefile` exactly:
`-O2 -g -std=c11 -Wall -Wextra -Iinclude`. The build emits the archive's own
single pre-existing warning (`upconv.c:469 'uc_get_i32' defined but not used`),
which is the first corroboration that the study built this same tree.

> **A trap worth recording.** The first version of `build.sh` backgrounded its
> compiles and did not check their exit status, so a failed compile printed
> `BUILD-OK` and left a **stale binary** in place. It cost one wrong
> byte-identity result before it was caught. Every build since checks each `wait`.

## 0.2 Trees

| tree | what it is |
|---|---|
| `.work/ni0811/v49/` | pristine unpack of `omc_v4.9_full_20260811.zip` — the reference for every byte-identity check |
| `.work/ni0811/v49p/` | + symbol-dump instrumentation + relaxed `slice_h` validator. **Verified byte-identical to pristine at `slice_h` 8 and 16 with every knob unset, after every rebuild** |
| `.work/ni0811/v49cap/` | the tree all shipped changes were made in |
| `.work/ni0811/v49live/` | copy of the live working tree `.work/final/omc_v4.9` |
| `.work/ni0811/verify1..5/` | clean unpacks of each delivered archive, built and gated from scratch |

## 0.3 The configuration used throughout

The ship stack of record (`SESSION_LEDGER.md` line 13, `RESUME.md` LATEST 27):

```
OMC_XSL=3 OMC_RBOOST=50 OMC_TAILGUARD=2 OMC_FILLHYST=2
OMC_SPC=4 OMC_FORCE_PROF=2 OMC_ALLOC=2 OMC_DCFB=3 --refresh 16
```

`decode env-less` is part of that record, and it was **verified**: decoder output
is byte-identical with and without the environment, and `rt = 0` holds against a
completely env-less decoder. The decoder takes XSL from the stream minor, as
designed.

## 0.4 Masters — all prepared this session from the project's own footage

Native pixels only: crops, never rescales.

| name | geometry | source |
|---|---|---|
| `beach`, `heli`, `city` | 1920×1080 4:2:2 10-bit, 8 frames | centre crop of `beach.mov`, `alpine_helicopter.mov`, `city_aerial.mov` (2048×1152 ProRes) |
| `beach16` | same, 16 frames | for the extended A5 recovery test |
| `heli` | 2048×1152, 4 frames | native, for generation chains |
| `beach444_10/12`, `city444`, `couch444/422_12` | 1920×1080 4:4:4 and 12-bit | `beach.mov`, `city_aerial.mov`, `couch_dark_with_movement.mov` (native 12-bit) |
| `cow422_10/12` | 1920×1080, 3 frames | crop of `cow.mxf` (4480×3096, native 12-bit, heavy film grain) |
| `trees4` | 3840×2160 4:2:2 10-bit, 4 frames | crop of `trees.mov` (4096×2160) |
| `dngA4`, `dngB4` | 3840×2160, 4 frames | `260804_173316` and `260806_171716` from the DNG set |

## 0.5 Working discipline

- Absolute paths everywhere. One path-drift incident happened anyway (a `verify`
  directory created under `stage/`) and is recorded below.
- Byte-identity against the pristine tree re-checked after **every** rebuild of
  the instrumented tree.
- Control arms before blaming any change — this is what showed the generation
  behaviour and the seam ridge were both pre-existing, not caused by the work.
- Every delivered archive re-verified from a **clean unpack**, not from the
  working tree.

---

## PART I — Slice height: the study's headline, re-measured

## 1.1 What the study claimed, and why it needed re-testing

`OMC_JPEG2000_STUDY.md` §3.7: coding 16 lines at a time instead of 8 is worth
**1.23× at 0.5 bpp and 1.15× at 1.0 bpp**, measured on 256- and 768-pixel-wide
pictures recovered from review panels. Its own Part VII names re-confirmation at
1920 px as *"the single most important follow-up"*.

## 1.2 Method, and two things the small-picture study did not have to face

1. **Pad-and-crop is not free.** At 1080p, `slice_h = 16` codes 1088 rows and the
   encoder sizes the budget from the **coded** height — so equal `--bpp` hands
   the taller arm **0.74 % more wire bytes** (261 120 vs 259 200 at 1.0 bpp).
   Every ratio below is measured on **wire bytes actually spent** for the same
   delivered 1920×1080 picture. The study's test picture was 304 rows, which
   divides by both 8 and 16, so it never met this.
2. **Quality is read off the decoder output** (cropped to display), never the
   encoder's padded reconstruction.

Judged on the **worst steady-state frame** with **all three planes** required to
match, temporal prediction active, 8 frames.

## 1.3 1080p — how many bytes `slice_h = 8` needs to match the taller slice

| clip | sh16 @0.5 | sh16 @1.0 | sh16 @2.0 | sh12 @0.5 | sh12 @1.0 | sh12 @2.0 |
|---|---|---|---|---|---|---|
| beach | 1.217× | 1.087× | 1.086× | 1.062× | 1.053× | 1.067× |
| heli | 1.144× | 1.072× | 1.066× | 1.076× | 1.064× | 1.055× |
| city | 1.200× | 1.176× | 1.111× | 1.153× | 1.094× | 1.071× |
| **mean** | **1.187×** | **1.112×** | **1.088×** | **1.097×** | **1.070×** | **1.064×** |

As rate savings: **sh16 = 15.8 % / 10.1 % / 8.1 %**, **sh12 = 8.8 % / 6.5 % / 6.0 %**.

Re-run later with the blend-cap rule active (§VI), which slightly improves it:
beach 1.236× / 1.101×, city 1.203× / 1.174× at 0.5 / 1.0 bpp.

**Falsification:** the study predicted "~12–13 % at 1920 px at 1.0 bpp".
Measured: **10.1 %**. Real, and about 2–3 points optimistic.

## 1.4 Intra versus temporal — the answer to "does it help prediction?"

Cold intra frame (frame 0), 1.0 bpp: **beach 1.280×** (21.9 % saving),
**city 1.136×** (12.0 %), against 8.0 % and 15.0 % with prediction running.

**It does not improve prediction.** It is a transform-support gain, and on
content where prediction already works (beach) it partly overlaps with what
prediction has removed — the saving falls from 21.9 % to 8.0 %. On content where
prediction works poorly (city aerial) it holds. The gain is largest on the cold
intra frame, which is the frame A1's worst-frame rule judges.

## 1.5 2160p — a 5× disagreement with the study

Baseline `slice_h = 16` (what 4K ships), 4 frames, same protocol:

| clip | sh24 @0.5 | sh24 @1.0 | sh32 @0.5 | sh32 @1.0 |
|---|---|---|---|---|
| trees | 1.030× (2.9 %) | 1.047× (4.5 %) | 1.070× (6.6 %) | 1.092× (8.5 %) |
| dngA | 1.082× (7.6 %) | 1.031× (3.0 %) | 1.137× (12.0 %) | 1.123× (11.0 %) |
| dngB | 1.221× (18.1 %) | 1.306× (23.4 %) | 1.219× (18.0 %) | 1.291× (22.5 %) |

**Falsification:** the study estimated `slice_h = 32` at 2160p was worth
"roughly 2 % beyond 16". Measured on the shipped codec at 3840 px: **6.6–12 %**
excluding dngB, whose 30 dB U plane binds the all-planes match and inflates it.

The study's 2 % came from a Python transform model on a 256-px picture where LL5
is 8 columns wide. It cannot see the mechanism that dominates at real width:
**fewer, larger slices give the rate controller finer granularity** — 3 840 B per
slice at sh16 against 7 680 B at sh32.

**Why it does not plateau:** 32 lines at 2160p is the same fraction of picture
height that 16 lines is at 1080p. It is the *same step* on a raster with twice
the lines, not a second helping. That also says where the ladder ends: 64 lines
at 4K would be the genuinely new step, and it was not tested.

## 1.6 Side effects — every guarantee re-checked at the taller height

| check | slice_h 8 | slice_h 16 (1080 → 1088) |
|---|---|---|
| `rt = 0`, 4:2:2/10 | OK | OK |
| `rt = 0`, 4:4:4/10 and 4:4:4/12 | OK | OK |
| Exact CBR (frame bytes == N·B) | OK | OK |
| Generations | converge byte-exact by gen 4 | converge byte-exact by gen 4 |
| A5 containment, one slice smashed | 11 rows hit, healed at frame 14 | 19 rows hit, healed at frame 3 |
| MSE-optimal band offsets vs the shipped table | reference | **shift by < 0.05 of a step** |
| `rt = 0` and exact CBR at slice_h 32 (2160 → 2176) | — | OK, byte-exact |

**Generations — a pre-existing finding, not a side effect.** `DESIGN.md` §5 claims
generations 2–5 byte-identical to generation 1. On real 2048×1152 footage the
chain is **not** byte-identical at gen 2→3: it differs by ~76 dB — a handful of
±1-code samples — and then locks byte-exact from generation 4 onward. **Identical
at both slice heights**, at 1 and 3 frames, at 1.0 and 2.0 bpp. The substance of
A4 (no accumulating loss) holds; the documentation's "byte-identical from gen 2"
is optimistic on this content.

**A5.** The containment unit doubles, as expected. Both heights stayed row-bounded
and both recovered byte-exact inside the refresh period. The faster heal at sh16
is one sample and is not claimed as a benefit.

**Band gains — a check the study never did.** Every band's synthesis energy gain
was re-measured through OMC's own inverse transform at 1920 px (`bandgain.c`).
The MSE-optimal offsets shift by ≤ 0.05 of a step from sh 8 to sh 16, so the
**normative allocation tables remain correct at the taller slice** — no retuning.
At sh 32 the drift reaches 0.11 step; still small.

---

## PART II — Latency

## 2.1 The independent simulation

The study's §4.4 repair was re-derived from first principles rather than checked:
a row-by-row simulation of when each source row is final and when each output row
is due, with the dependency geometry read off `omc_uc_scale_plane_ws()`
(`latsim.py`). **The study's raster figures reproduce exactly** — 1080p50 sh16 →
2160p50: 0.886 ms; → 720p50: 0.942 ms; 2160p50 sh32 → 720p50: 0.924 ms.

## 2.2 Three corrections to it

1. **It omits v4.9's own headline feature.** With `OMC_XSL = 3`, slice *k*
   rewrites the **last row of slice k−1** when it reconstructs. `LATENCY.md` warns
   that a strictly row-streaming sink must account an extra slice period — and a
   raster-clocked converter is exactly that sink. Simulated, the true cost is
   **+1 line, not +1 slice period**: the deferred row sits at the end of its slice
   and already had `slice_h − 1` lines of slack. 1080p50 sh16 worst path becomes
   **0.961 ms, not 0.942**.
2. **It credits itself with padding.** The study reports 45 of 120 cases "just
   under" the bound "because a padded coded height makes slices land marginally
   early". That assumes a slice can be transmitted before its last **real** row is
   captured. It cannot. With capture-limited pacing the bound is exactly
   `reach × line`, with nothing under it.
3. **The buffer price is understated.** "An output buffer of `reach` rows — at
   most 18 lines" ignores the polyphase aperture and the burstiness of
   slice-at-a-time arrival. The real figure is of order `taps + slice_h` — about
   **68 rows** at 2160p → 720p with 32-line slices.

## 2.3 The full A2 table, 720p50 → 8K

Milliseconds; budget 1.000. **Bold** = over. **⚑** = over under the old charging,
fits at the figure shown with the raster-clocked stage. **—** = the codec term
alone is over, so the conversion figure is moot.

| format | 8 codec | 8 +conv | 16 codec | 16 +conv | 24 codec | 24 +conv | 32 codec | 32 +conv |
|---|---|---|---|---|---|---|---|---|
| 720p50 | 0.612 | 0.834 | **1.168** | — | **1.723** | — | **2.250** | — |
| 720p59.94 | 0.511 | 0.696 | 0.974 | **1.345** | **1.437** | — | **1.877** | — |
| 720p60 | 0.510 | 0.695 | 0.973 | **1.343** | **1.436** | — | **1.875** | — |
| 720p100 | 0.306 | 0.418 | 0.584 | 0.806 | 0.862 | **1.195** ⚑0.959 | **1.125** | — |
| 720p120 | 0.255 | 0.348 | 0.487 | 0.672 | 0.718 | 0.996 | 0.938 | **1.300** |
| 1080p50 | 0.408 | 0.705 | 0.775 | **1.069** ⚑0.961 | **1.149** | — | **1.513** | — |
| 1080p59.94 | 0.341 | 0.588 | 0.647 | 0.892 | 0.959 | **1.329** | **1.262** | — |
| 1080p60 | 0.340 | 0.587 | 0.646 | 0.891 | 0.958 | **1.328** | **1.261** | — |
| 1080p100 | 0.205 | 0.353 | 0.388 | 0.535 | 0.575 | 0.797 | 0.757 | **1.051** ⚑0.849 |
| 1080p120 | 0.171 | 0.294 | 0.324 | 0.446 | 0.479 | 0.664 | 0.631 | 0.876 |
| 2160p50 | 0.205 | 0.427 | 0.390 | 0.686 | 0.575 | 0.797 | 0.757 | **1.051** ⚑0.933 |
| 2160p59.94 | 0.171 | 0.356 | 0.325 | 0.572 | 0.480 | 0.665 | 0.631 | 0.877 |
| 2160p60 | 0.171 | 0.356 | 0.325 | 0.572 | 0.479 | 0.664 | 0.631 | 0.876 |
| 2160p100 | 0.103 | 0.214 | 0.195 | 0.343 | 0.288 | 0.399 | 0.379 | 0.526 |
| 2160p120 | 0.086 | 0.178 | 0.163 | 0.286 | 0.240 | 0.333 | 0.316 | 0.438 |
| 4320p50 | 0.103 | 0.214 | 0.195 | 0.343 | 0.288 | 0.399 | 0.380 | 0.529 |
| 4320p59.94 | 0.086 | 0.179 | 0.163 | 0.287 | 0.240 | 0.333 | 0.318 | 0.441 |
| 4320p60 | 0.086 | 0.178 | 0.163 | 0.286 | 0.240 | 0.333 | 0.317 | 0.441 |

Three readings: **720p is stuck at 8 lines permanently**; **1080p at 16 fits
everywhere except 50 Hz with a conversion**; **32 lines at 4K fits today from
59.94 Hz upward, and 8K takes 32 everywhere with enormous margin.**

## 2.4 A ladder the study never looked for

The study only ever tried *doubling*. But **1080 = 90 × 12** and
**2160 = 90 × 24** — both exact, no padding at all, and both fit A2 under the
codec's **own conservative** charging: 0.816 ms and 0.797 ms. They capture about
60 % of the doubling's gain with no architecture dependency whatsoever.
Recorded as the fallback if the converter change had been refused; not
implemented, because it was not.

## 2.5 Mixed slice heights within a frame — simulated, does not work

Idea: tall slices for most of the picture, short ones at the bottom, to pull the
latency down. Simulated at 2160p50 (worst-row end-to-end latency):

| arrangement | latency |
|---|---|
| uniform 16 (ships today) | 0.389 ms |
| uniform 32 | 0.759 ms |
| 32 everywhere, 8 for the last 10 slices | **0.759 ms** |
| 32 for the top half, 8 for the whole bottom half | **0.759 ms** |
| 32 for just the top 10 %, 8 for the other 90 % | **0.759 ms** |
| uniform 8 | 0.204 ms |

**Latency is a worst-row property.** A slice cannot start coding until its *last*
row is captured, so the *first* row of a 32-line slice waits 32 line-times
regardless of what the other slices do. And a genlocked output emits at a fixed
line rate, so the output stage must hold **every** row for the worst row's delay.
One tall slice anywhere costs the whole frame.

One real thing inside the idea: a short *final* slice would let 1080 and 2160
divide exactly and avoid the padded rows (~0.74 %). It needs per-slice height
signalling — a format change — to recover under one percent. Not worth it.

---

## PART III — The entropy layer

All on the real symbol stream at production resolution: three 1920×1080 clips,
4 147 200 coefficients each per rate, contexts accumulated as exact
(context × symbol) histograms, **leave-one-clip-out** — the protocol a
static-table codec has to be judged under. Instrumentation is env-gated and the
encoder is byte-identical with it unset.

## 3.1 The study's "unresolved" question, settled

Category-symbol bits against the shipped 16-state context (negative = better):

| model | contexts | 0.5 bpp | 1.0 bpp | 2.0 bpp |
|---|---|---|---|---|
| +diagonal significance | 32 | −0.60 % | −0.66 % | −0.58 % |
| +diagonal magnitude | 64 | −0.56 % | −0.75 % | −0.78 % |
| +diagonal sum | 80 | −0.34 % | −0.59 % | −0.62 % |
| **+parent band (inter-scale)** | **48** | **−1.77 %** | **−1.91 %** | **−1.18 %** |
| +parent + diagonal | 96 | −2.15 % | −2.34 % | −1.57 % |

The study's §3.2 saw every candidate lose, monotonically with context count, and
called it unresolved. With adequate data they win — so that was overfitting, as
the study suspected. **But the JPEG 2000 axis is the wrong axis.** Every
spatial-neighbour idea is worth under 0.8 % of category bits (≈ 0.5 % of
payload). The **inter-scale** context — the coarser band's co-located magnitude,
already coded, already used by OMC's own grain classifier, and *not* something
JPEG 2000 does because EBCOT works within one subband — is worth **three times as
much at fewer contexts**.

Honest counterweight: 48 contexts is 3× the table BRAM (~790 KB → ~2.4 MB per
engine) for ~1.3 % of payload — the same shape as the K=16 group option this
project already rejected on memory grounds. The conclusion is not "build it": it
is that **the entropy layer is nearly exhausted and what remains costs memory in
proportion to what it pays.**

## 3.2 Sign and magnitude-LSB coding — the study's estimate, made firm

| | 0.5 bpp | 1.0 bpp | 2.0 bpp |
|---|---|---|---|
| sign context (36 ctx) | −5.31 % of sign bits | −4.40 % | −4.48 % |
| top magnitude LSB (16/band) | −12.81 % of those bits | −12.50 % | −12.91 % |
| **combined, share of payload** | **≈ 2.0 %** | **≈ 1.9 %** | **≈ 1.9 %** |

The study estimated 1–3 % "with proper corpus training". Measured: **1.9 %**, for
about 20 % more entropy-stage symbol throughput. A real RTL trade, now priced.

## 3.3 Run and skip — three falsifications, confirmed at 30× the data

| model | 0.5 bpp | 1.0 bpp | 2.0 bpp | study (beach @2.0) |
|---|---|---|---|---|
| binary significance (EBCOT) | +2.47 % | +2.76 % | +3.20 % | +3.1 % |
| 2×2 quad skip (cleanup run) | +4.04 % | +5.44 % | +6.53 % | +8.0 % |
| HTJ2K quad + exponent prediction | +1.06 % | +1.36 % | +1.31 % | +3.4 % |

Every one **worse** than what ships, at every rate, on real footage. "Do not port
any of the three" — confirmed independently. This also reproduces OMC's own v4.4
finding that the magnitude context beats binary significance.

## 3.4 PCRD-opt — confirmed exhausted

Band synthesis gains measured through OMC's own inverse transform at 1920 px, and
the high-rate MSE-optimal offsets derived from them:

| band | LL5 | HL5 | HL4 | HL3 | LH2 | HL2 | HH2 | LH1 | HL1 | HH1 |
|---|---|---|---|---|---|---|---|---|---|---|
| MSE-optimal | −2.97 | −2.12 | −1.70 | −1.30 | −0.83 | −0.80 | 0.00 | −0.05 | −0.04 | +0.56 |
| shipped `omc_off[0]` | −4 | −3 | −3 | −2 | −1 | −1 | 0 | 0 | 0 | +1 |

The shipped ladder **is** the MSE-optimal rule, rounded, with a deliberate
one-step-finer bias on the four low bands — the anti-banding (G2) protection. A λ
allocator would spend RTL recovering a gap that is partly not a gap. The study's
"do not build it" stands.

---

## PART IV — Slice-header redundancy: the study's smallest number, 4× understated

§5.11 measured the 120-bit table-group field as 84 % redundant on a 768-px
picture, estimated 0.65 % of the wire, and dropped it. At production width the
**whole** header is far more compressible. Measured by parsing real streams, no
code change — 1920×1080, `slice_h = 8`: the header is **5.0 % of the wire at
0.5 bpp** and **2.5 % at 1.0 bpp**.

| field | raw bits | order-0 | given the slice above |
|---|---|---|---|
| table-group ids | 120 | 68 | **21** |
| motion, 4 regions | 52 | — | **all four identical in 100 % of slices** |
| used_bits | 24 | 10 | **0.3** |
| tANS final state | 16 | 9 | 1.2 |
| partial_chunks | 16 | 2 | 1.7 |
| mode mask | 30 | 7 | 2 |
| slice index / frame index | 24 | — | 0 |
| fill bits | 18 | 6 | 3 |
| n_steps, Q, gain | 18 | 8 | 5 |
| sync + CRC | 64 | keep — A5 needs both | |

Keeping sync, CRC and the two indices for A5 and monitoring, the remaining
296 bits carry roughly 40–60 bits. A 48-byte header becomes ~18–20 bytes:
**~1.6 % of the wire at 1.0 bpp and ~3.1 % at 0.5 bpp, with zero latency cost.**
Realistically ~2 % — a static-table implementation will not reach ideal entropy.

It **overlaps** with the slice height (both attack per-slice overhead), so it adds
about 1 point on top of 16 lines rather than stacking fully. Its strongest case is
**720p**, which can never take a taller slice and whose header share is worse
because the picture is smaller: **7.5 % of the wire at 0.5 bpp**.

Simplest piece: the default encoder writes one global motion vector into all four
region slots in **100 %** of slices. One flag bit recovers 39 of those 52.

Measured, not built. It is a bitstream change and needs its own review.

---

## PART V — The blend cap: found by the eye, and the archive was wrong

## 5.1 What happened

Dan reported horizontal banding in the renders, worst on frame 0. Verified first
that nothing was switched off: streams carry **minor 9** (XSL level 3 active),
grain fill on, and encoder and decoder agree **byte-for-byte**.

The banding was real. Seam step excess — the extra row-to-row step at a slice
boundary over the picture's own interior step, in 10-bit codes. The source
measures ±0.2. `BITSTREAM.md` §f's own reference points: **3.1 clean, 6.6 = the
visibility regression that was bisected, 3.3 after the fix.**

| clip | rate | frame | slice_h 8 | slice_h 16 |
|---|---|---|---|---|
| city | 0.5 | **0 (cold intra)** | **+12.71** | **+10.32** |
| city | 0.5 | 5 (steady) | +7.37 | +5.01 |
| city | 1.0 | 0 | +2.63 | +1.35 |
| beach | 0.5 | **0** | **+5.53** | **+4.96** |
| beach | 0.5 | 5 | +0.38 | +0.24 |
| heli | 0.5 | 0 | +1.87 | +1.60 |

**The cold intra frame is 3–14× worse than the steady frame**, and every eye gate
this project has passed was judged on beach's *steady* frame (+0.38). The slice
height was **not** the cause — every row is lower at 16 lines.

## 5.2 The archive was 14 hours behind the working tree

Dan recalled a reviewed decision: **cap 8 below 0.75 bpp, cap 4 at or above**.
`SESSION_LEDGER.md` §2.3 carries the sweep he judged, and the working tree's code
comment records it as eye-chosen:

| rate | cap 4 (seam / VMAF) | cap 8 | cap 16 |
|---|---|---|---|
| 0.5 | +1.23 / 95.21 | **+0.67 / 94.89** | +0.40 / 94.34 |
| 1.0 | **+0.00 / 97.67** | −0.35 / 97.23 | — |
| 2.0 | **−0.38 / 98.59** | −0.68 / 98.12 | — |

**It was never in the delivered archive.** `omc_v4.9_full_20260811.zip` was packed
at 02:45 from a `codec.c` dated 02:43; `xsl_lim_for()` landed in the working tree
at 17:02 the same day. The archive has a flat `omc_xsl_lim = 4`.

Proved by construction: the live tree at 0.5 bpp produces numbers **identical to
three decimals** to the archive with the cap forced to 8.

The archive was also missing `omc_fillcorr` (the parent-band grain fill, E-1 from
`ENERGY_GAPS.md`), `upconv.c` changes, and the OMC-UC latency table in
`LATENCY.md`.

## 5.3 What the rule is worth

beach, frame 0, 0.5 bpp: **+5.53 → +3.59** with the rule, **→ +2.98** with 16
lines as well — better than the +3.1 the project called clean.

## 5.4 A rendering error of mine, on top of the real one

The first eye kit converted 10-bit limited range to **8-bit full range** PNG. In
the flattest regions of the source that collapses ~2 200 distinct levels to ~250
— contouring of my own, laid on top of the real ridge. Every render since is
16-bit or dithered 8-bit.

## 5.5 The CRITICAL that was blocking the rule

`CAP_RULE_REVIEW.md` F1: the cap was a **process-wide global**. A multi-channel
server running two rates in one process lets whichever context was created last
decide the blend for both — and a stream encoded under one cap does not
reconstruct under another.

Fixed: the cap lives in `ctx_common_t`, set in `common_init()`, the one function
both encoder and decoder call. New gate `tests/test_cap.c` builds that situation
on purpose — two contexts at different rates, interleaved, high-rate created last
— and requires each to produce byte-identically what it produces alone, **stream
and reconstruction**, and to round-trip through its own decoder.

**That test passes on the fixed build and FAILED on the live working tree.** The
defect was real and reproducible there; both trees are now fixed.

> A note on the test itself: its first version compared only bitstreams and
> passed everywhere, because the random content it used never selected temporal
> prediction and the cap reaches the bitstream only through the temporal
> reference. Comparing the **reconstruction** made it bite. A test that cannot
> fail proves nothing.

## 5.6 4:4:4 — the threshold was on the wrong denominator

The trigger counted **luma pixels**. A 4:4:4 picture carries 3 samples per pixel
against 4:2:2's 2, so at the same nominal bpp it is materially coarser — and
coarseness is what the cap responds to.

city aerial, 4:4:4 10-bit, frame 0:

| bpp | old rule picks | cap 4 | cap 8 |
|---|---|---|---|
| 0.80 | cap 4 | **+5.42** | +3.10 |
| 1.00 | cap 4 | +2.86 | +1.15 |
| 1.10 | cap 4 | +2.26 | +0.65 |
| 1.50 | cap 4 | +0.59 | −0.48 |

beach 4:4:4: +2.13 / +0.68 at 0.85 bpp — **below the visible line either way,
which is why beach could not settle it and city could.**

Fixed by counting **coded samples**: the single reviewed threshold then lands at
**0.75 bpp for 4:2:2** (byte-identical to the approved rule, verified at 0.5,
0.74, 0.75, 1.0, 2.0) and **1.125 bpp for 4:4:4** (verified: cap 8 at 0.85, 1.0,
1.1; cap 4 at 1.2, 1.5).

## 5.7 Bit depth — measured, no change needed

The cap **already scales with depth** in the reconstruction —
`cap × ((maxv + 1) >> 10)`, so ±4 at 10-bit and ±16 at 12-bit are the same
fraction of full scale. The only question was whether the *threshold* must move.

cow (native 12-bit, heavy film grain), identical content at both depths, seam
excess as a fraction of full scale ×1000:

| depth | 0.5 bpp | 0.8 bpp | 1.0 bpp |
|---|---|---|---|
| 10-bit | +1.01 | +0.60 | +0.40 |
| **12-bit** | **+0.62** | **+0.17** | **+0.05** |

12-bit is **better behaved**, not worse, and cap 4 against cap 8 barely registers.
Same on couch (native 12-bit interior). Caveat stated: neither 12-bit clip shows a
seam problem at all, so this shows 12-bit is not *worse*, not that it behaves
under content that bands.

---

## PART VI — Half-rate quality: OMC @ R against JPEG XS @ 2R

Ship stack, delivered build, libvmaf and libvmaf-NEG, PSNR on all three planes.

## 6.1 1080p, 8 frames — VMAF-NEG gap (negative = OMC behind)

| clip | rate | 8 lines | 16 lines |
|---|---|---|---|
| beach | 0.5 vs XS 1.0 | −2.08 | **−0.80** |
| beach | 1.0 vs XS 2.0 | −1.40 | **−0.89** |
| heli | 0.5 vs XS 1.0 | −2.73 | **−1.98** |
| heli | 1.0 vs XS 2.0 | −1.53 | **−1.16** |
| city | 0.5 vs XS 1.0 | −7.43 | **−3.89** |
| city | 1.0 vs XS 2.0 | −0.48 | **−0.36** |
| **mean** | | **−2.61** | **−1.51** |

Plain VMAF gap: **−1.87 → −0.76**. So the slice height closed **42 %** of the NEG
gap and **59 %** of the VMAF gap — and OMC is **still behind on all six pairs**.

## 6.2 4K, 4 frames — VMAF-NEG gap

| clip | rate | 16 lines | 32 lines |
|---|---|---|---|
| trees | 0.5 vs XS 1.0 | −3.47 | **−2.11** |
| trees | 1.0 vs XS 2.0 | −0.47 | **−0.38** |
| dngA | 0.5 vs XS 1.0 | −1.22 | **−0.95** |
| dngA | 1.0 vs XS 2.0 | −0.66 | **−0.53** |
| dngB | 0.5 vs XS 1.0 | −2.76 | **−1.48** |
| dngB | 1.0 vs XS 2.0 | −0.18 | **−0.07** |
| **mean** | | **−1.46** | **−0.92** |

Plain VMAF mean gap **−0.63 → −0.34**, and **dngB at 1.0 bpp beats XS at 2.0 bpp
on plain VMAF** (+0.01 at 16 lines, +0.12 at 32) — a genuine half-rate win on one
arm. 16 → 32 at 4K closes 37 % of the gap, against 42 % for 8 → 16 at 1080p: it
does **not** plateau.

Caution: three clips at four frames; the earlier corpus runs used different clips
over 24 frames. Same direction, not stackable.

## 6.3 "The saved bitrate should let us add detail" — half right

The saving is not spare bits: the mandate fixes R, so it arrives as a better
picture at the same R, which is what the tables show. But spending it on **more
detail** would go backwards. VMAF-NEG punishes **enhancement-like energy**, and
`ENERGY_GAPS.md` measured that OMC already keeps **3.5× more fine luma energy
than XS with only a third of the correlation** — its fine detail is largely
invented, and the NEG deficit tracks how much of it there is. The efficiency
helped for the right reason: more accurate coefficients, so less has to be filled
in.

---

## PART VII — Other findings, and one confirmed from the write-up bundle

## 7.1 CHROMA_PLAN finding A1 — discharged

Its central claim rested on one clip. Re-measured at 1920×1080 on three clips at
0.5 and 1.0 bpp, `OMC_FORCE_PROF=2` against auto:

| | ΔY | ΔU | ΔV |
|---|---|---|---|
| mean of beach/heli/city at both rates | **+0.69 dB** | **−1.04 dB** | **−1.06 dB** |

The ship stack buys ~0.7 dB of luma with ~1 dB of **both** chroma planes, on every
clip and both rates. Under A1's "every measure at once" and C5, that is a live
problem, independent of anything in the JPEG 2000 study.

## 7.2 LATENCY_KNOB_PLAN — two claims checked

- **R-4 correct.** The band layout does generalise to any multiple of 4 and still
  yields two vertical levels — built and round-tripped at `slice_h` 12, 24 and 32
  with `rt = 0` intact.
- **R-6 answered.** At 4K, 16 → 32 is a 6.6–12 % rate saving, not the diminishing
  return the finding feared.
- **Its premise is wrong for the first step.** Taller slices do not need a
  relaxed-latency knob: 12 at 1080p and 24 at 2160p fit sub-1 ms with margin under
  the shipped model, and 16 and 32 fit with the converter repair. No knob, no
  second conformance point.

## 7.3 Not re-tested, stated plainly

- **§3.7.1** (extra vertical DWT levels measure worse) rests on a Python
  re-implementation, not the shipped codec. It is a "do not do it" conclusion, so
  the risk of leaving it unverified is low — but it is unverified.
- `CAP_RULE_REVIEW.md` is byte-identical to the copy already in `.work/`; its
  experiments were not re-run except where §V above did so.

---

## PART VIII — Falsifications and errors, all of them

## 8.1 In the study under test

| claim | verdict |
|---|---|
| 8 → 16 lines worth ~12–13 % at 1920 px, 1.0 bpp | **optimistic** — 10.1 % measured |
| 2160p 16 → 32 worth "roughly 2 %" | **5× low** — 6.6–12 % measured |
| The raster-clocked bound is `reach × line_time` | **incomplete** — omits XSL's deferred row; +1 line |
| 45 of 120 cases fall under the bound | **wrong** — that credits padding the encoder cannot have |
| Output buffer "at most 18 lines" | **understated** — order `taps + slice_h`, ~68 rows worst case |
| §3.2 context modelling "unresolved" | **resolved** — and measured on the wrong axis; inter-scale beats every JPEG 2000 spatial idea by 3× |
| Header work worth ~0.65 % | **4× low** — ~1.6 % at 1.0 bpp, ~3.1 % at 0.5 |
| PCRD-opt nearly exhausted | **confirmed** |
| Binary significance / quad skip / HTJ2K all negative | **confirmed at 30× the data** |
| Sign + LSB worth 1–3 % | **confirmed and made firm: 1.9 %** |
| 2V × 5H asymmetry is correct | **not re-tested** |

## 8.2 In the codec and its documentation

| claim | verdict |
|---|---|
| `DESIGN.md` §5: generations 2–5 byte-identical to gen 1 | **optimistic on real footage** — differs by ~76 dB at gen 2→3, locks byte-exact from gen 4. Same at both slice heights |
| The delivered v4.9 archive is the codec | **it was 14 hours behind the working tree** and missing an eye-approved rule |
| `CAP_RULE_REVIEW.md` F1 was an avoided hazard | **it was a live defect**, reproducible, now fixed in both trees |
| The 0.75 bpp cap threshold | **wrong denominator for 4:4:4** — fixed |
| Bit depth might need its own threshold term | **falsified** — 12-bit measures better than 10-bit |
| Mixed slice heights could buy latency | **falsified by simulation** — latency is a worst-row property |

## 8.3 Mine

Recorded because they cost time and one of them nearly produced a false verdict.

| error | consequence | fix |
|---|---|---|
| `build.sh` did not check background compile status | printed `BUILD-OK` over a failed compile and left a stale binary; one byte-identity result was meaningless | every `wait` is checked |
| Rendered 10-bit limited range to 8-bit full range PNG | ~2 200 levels collapsed to ~250 in flat areas — contouring of my own on top of a real artifact, which is what Dan was shown first | 16-bit and dithered 8-bit renders |
| First 4K half-rate run: `--slice-h 32` was refused by the delivered validator | the arm **silently reused the previous decode** and reported identical numbers | harness aborts on a failed encode |
| Same run: DNG masters are 24 frames, encode was 4 | libvmaf compared 4 decoded frames against 24 reference frames; VMAF 16 at 33 dB PSNR was the tell | harness asserts frame counts match |
| `test_cap` v1 compared bitstreams only | passed everywhere including on the broken tree — a test that could not fail | compares the reconstruction too |
| Created a directory with a relative path after cwd drift | `verify/` landed under `stage/`; build failed confusingly | absolute paths |
| Recommended against 32 lines as the 4K default | reasoning was **inconsistent** — the same objection applied to 1080p/16, which we had just approved | retracted; the real reason is that the eye has not seen it |
| Wrote a table legend naming labels that were not in the table | unreadable | table redone with the labels on it |
| Explained the two charging models as "with and without conversion" | implied a conversion makes things faster, which is nonsense | rewritten: same conversion, two ways of charging for the wait |
| Asked a vague question ("it is your call") | Dan had to ask what I was actually asking | ask a yes/no question |

---

## PART IX — Decisions taken, and by whom

| # | decision | who | what was done |
|---|---|---|---|
| 1 | `slice_h = 16` approved by eye; make it a **knob defaulting to 16** | mandate holder | auto rule is now `(height ≤ 720) ? 8 : 16` in both the CLI and the validator; documented in `BITSTREAM.md` §7, byte 12, `LATENCY.md`, `README.md` |
| 2 | The rate-derived blend cap (8 below 0.75 bpp, 4 at or above) is **the default** | mandate holder, confirming an earlier eye review | implemented, frozen normatively in `BITSTREAM.md`, `OMC_XSL_LIM` retained as an override |
| 3 | **cap 8 for 4:4:4** | mandate holder | threshold now counts coded samples: 0.75 bpp at 4:2:2 (unchanged), 1.125 at 4:4:4 |
| 4 | **Close the bit-depth item** | mandate holder | entry deleted, both hooks removed, `BITSTREAM.md` states the measured finding |
| 5 | Keep **8 / 16 / 32** as user-selectable | mandate holder | validator accepts exactly those; 12, 20, 24, 64 refused with a reason |
| 6 | **Implement the raster-clocked output stage as proposed** | mandate holder | `cfg.uc_out_batched`, new charging model, gate G21, `LATENCY.md` rewritten |

**Not decided, deliberately:** whether 32 lines becomes the 4K/8K *default*. My
corrected recommendation is yes on the same basis 16 was approved at 1080p — the
blocker is that the eye has not seen 32-line 4K output, and the A/B is staged
(`AB_4K_32lines_2026-08-12.zip`).

---

## PART X — What is open

Kept in `/OPEN_DECISIONS.md`, under one rule: **an entry may only exist there if
it also has a hook — something that runs and speaks up.** Prose has already failed
this project once (F1 was CRITICAL in writing and stayed live until a test failed).

| item | state | hook |
|---|---|---|
| **CAP-STEP** — should the cap key on the quantizer step, not the rate? | open. The same clip at the same rate needs different caps on different frames (beach 0.5 bpp: f0 +5.53, f5 +0.38 — fourteenfold). No rate rule can express that | **weak — this file only.** Flagged as such; wants a test pinning the frame-0 numbers |
| **TREE-SPLIT** — two copies of the codec | open. The working tree is ahead and **currently fails `test_cc`** ("4:2:2 detour: the chroma round trip is worse than stated") | `make test` is red there |
| Chroma profile trade (§7.1) | open, not in the register | none — should be added |
| Slice-header prediction (Part IV) | measured, not built | none |
| Sign + LSB context coding (§3.2) | measured, not built | none |
| 32 lines as the 4K default | awaiting the eye | A/B staged |

---

## PART XI — Every code change

Diffs: `writeups/capfix.diff` (the blend cap and F1) and
`writeups/converter.diff` (the output stage). Summary:

| file | change |
|---|---|
| `include/omc1.h` | `OMC_XSL_LIM_MINOR9 8`; `OMC_OUT_RASTER` / `OMC_OUT_SLICE_BATCHED`; `cfg.uc_out_batched` |
| `src/codec.c` | `xsl_lim_for()` — the rate-derived cap on coded samples; cap moved into `ctx_common_t` and set in `common_init()`; three blend sites read the per-context value |
| `src/config.c` | auto `slice_h` = 16 above 720p; validator accepts 8/16/32; A2 guard charges by the declared output-stage contract and names it in the refusal |
| `src/upconv.c` | `omc_uc_scale_latency()` is now the raster-clocked form; `omc_uc_scale_latency_ex()` takes the contract explicitly |
| `include/omc_uc.h` | declares `_ex` and documents both contracts |
| `tools/omc_enc.c` | auto `slice_h` rule + the reasoning in comment |
| `tests/test_cap.c` | **new** — multi-context cap gate (F1), wired into `make test` |
| `tests/test_uc.c` | **new gate G21** — row-by-row simulation of the output stage, 165 cases |
| `tests/test_unit.c` | validator test updated to the new pad-and-crop contract |
| `docs/BITSTREAM.md` | `slice_h` table and legal values; the cap rule frozen normatively with its derivation, sample-count denominator and per-context requirement |
| `docs/LATENCY.md` | `slice_h` default and the 720p exception; the whole output-stage contract section |
| `README.md` | the `--slice-h` knob explained in the usage section |

## 11.1 Everything that was verified about those changes

- **Byte-identity where nothing should change:** XSL off, every rate; and at and
  above 0.75 bpp with XSL on, byte-identical to the 2026-08-11 archive.
- **Byte-identity where it should change:** below 0.75 bpp, identical to the
  archive forced to cap 8.
- `OMC_XSL_LIM` override still exact at 4, 8, 16 and both rates.
- `rt = 0` byte-exact at 4:2:2/10, 4:4:4/10, 4:4:4/12, slice heights 8, 16 and 32.
- Exact CBR at every slice height including the padded rasters (1088 and 2176).
- All five suites green **from a clean unpack of the delivered archive**, five
  times over (one per delivered zip).
- Single-context output byte-identical before and after the F1 fix.
- The live working tree mirrored; its pre-existing `test_cc` failure unchanged,
  and its originals backed up in `.work/ni0811/backup_livetree/`.

---

## PART XII — File manifest

**Where the referenced files live.** Anything named as a source file
(`src/codec.c`, `src/config.c`, `src/upconv.c`, `include/omc1.h`,
`tools/omc_enc.c`, `tests/*.c`) or a codec document (`docs/BITSTREAM.md`,
`docs/LATENCY.md`, `docs/DESIGN.md`, `README.md`) is **inside
`Codec/Current/omc_v4.10_20260812.zip`**, in its final state. The documents under
test (`OMC_JPEG2000_STUDY.md`, `CAP_RULE_REVIEW.md`, `CHROMA_PLAN.md`,
`ENERGY_GAPS.md`, `LATENCY_KNOB_PLAN.md`) are in `new_ideas/08112026/`, unchanged.
`SESSION_LEDGER.md` and `.work/RESUME.md` are the project's own running records
and are also unchanged except for appended entries. Everything else is listed
below.

## Delivered

| path | what |
|---|---|
| `Codec/Current/omc_v4.10_20260812.zip` | **the codec.** Every change above, gates green from a clean unpack |
| `Codec/Current/omc_v4.9_full_20260811.zip` | untouched, for reference |
| `OPEN_DECISIONS.md` | the register and its rule |
| `writeups/SESSION_LEDGER_2026-08-12.md` | this file |
| `writeups/NEW_IDEAS_08112026_TEST_REPORT.md` | the first full report, with its addendum |
| `writeups/capfix.diff`, `writeups/converter.diff` | the code changes |

## Eye kits

| zip | contents |
|---|---|
| `eyekit_slice_height_2026-08-11.zip` | 24 images, 8 vs 16 lines — **superseded: rendered before the cap fix and with the 8-bit contouring** |
| `eye_f0_seams_2026-08-11.zip`, `eye_f0_beach_2026-08-11.zip` | frame 0, cap 4 vs cap 12, both slice heights |
| `eye_CAP8_f0_2026-08-11.zip` | frame 0 with the cap-8 rule |
| `AB_beach_slice_height_2026-08-12.zip` | beach, 8 vs 16 lines, cold intra and steady, cap 8 |
| `AB_444_cap_2026-08-12.zip` | 4:4:4 cap 4 vs 8, beach and city |
| `AB_4K_32lines_2026-08-12.zip` | **4K, 16 vs 32 lines — awaiting the eye** |

## Working directory `.work/ni0811/`

| file | what |
|---|---|
| `build.sh` | the build |
| `psnr.py` | per-plane PSNR, mean and worst-frame |
| `sh_test.py`, `sh_test2.py` | slice-height rate ratios at matched all-plane quality |
| `latsim.py` | the independent A2 simulation |
| `bandgain.c` | band synthesis gains through the codec's own inverse transform |
| `ctx_test.py`, `runskip_test.py` | the entropy-model studies |
| `hdr_study.py` | slice-header redundancy |
| `gates.sh`, `a5.py` | side-effect gates, loss containment |
| `eyekit.sh` | byte-fair render kit |
| `halfrate.sh`, `halfrate4k.sh` | OMC @ R vs XS @ 2R |
| `hr/halfrate_results.txt`, `hr/halfrate_4k.txt` | the half-rate results |
| `shrun*/`, `*.log` | every slice-height run, raw |
| `mast/` | every master |
| `backup_livetree/` | the live tree's originals before I touched it |

---

## PART XIII — How to reproduce

```bash
R=[machine-path-redacted]/.work/ni0811
mkdir -p $R/repro && cd $R/repro
unzip -q [machine-path-redacted]/Codec/Current/omc_v4.10_20260812.zip
$R/build.sh $PWD/.work/final/omc_v4.9          # zig cc; no make needed
V=$PWD/.work/final/omc_v4.9
$V/test_unit; $V/test_uc; $V/test_tf; $V/test_cc   # G21 prints inside test_uc

python3 $R/latsim.py                            # the full A2 table
$R/halfrate.sh                                  # OMC @ R vs XS @ 2R, 1080p
$R/halfrate4k.sh                                # the same at 4K
python3 $R/ctx_test.py  beach=$R/sym/beach_1.0.bin heli=... city=...
python3 $R/runskip_test.py  <same arguments>
python3 $R/hdr_study.py $R/gates/hdr05.omc
```

The symbol dumps for the entropy studies come from the instrumented tree:

```bash
OMC_SYMDUMP=$R/sym/beach_1.0.bin $R/v49p/omc_enc \
  -i $R/mast/beach_1920x1080_422_10.yuv -o /dev/null \
  -w 1920 -h 1080 --fmt 422 --depth 10 --bpp 1.0 --slice-h 8 -n 1
```

---

## PART XIII.5 — What must survive this session

If everything else in this document is lost, these are the things that cost the
most to learn and would cost the most to learn again. Each one now has something
in the build that says it, because prose in a document is exactly what failed.

| what | where it now lives so it cannot be lost again |
|---|---|
| The blend cap must be per encoder context, never process-wide | `tests/test_cap.c` — builds two contexts at different rates on purpose |
| The conversion charge is `reach` LINES, not whole slice periods | gate **G21** in `tests/test_uc.c` — 165 cases simulated row by row |
| 4:2:2 chroma is **co-sited**; picture resizing is **centred**; they are not interchangeable | gate **G22** in `tests/test_uc.c` — resamples a ramp and reads the offset off the values |
| The 0.75 bpp cap threshold counts **coded samples**, so 4:4:4 lands at 1.125 | `BITSTREAM.md`, normative, with the derivation |
| `slice_h` defaults to 16; 720p stays at 8 for A2 | `BITSTREAM.md` §7 table, `LATENCY.md`, `README.md`, and the validator |
| No banking overdraft, and no knob for it | the constant, its reasoning, and the whole latency model |
| An open decision may only exist if something in the build speaks up about it | the rule at the top of `OPEN_DECISIONS.md` |

And the four lessons that are not code:

1. **Never mirror a change by copying a whole file into a tree you did not
   write.** Apply the edit. Copying `codec.c` silently deleted 307 lines of
   someone else's work and only failed to build much later.
2. **Read every file in the folder you were asked to review**, even one that looks
   like a duplicate. The answer to "why was the scaler changed" sat in
   `new_ideas/08112026/SESSION_LEDGER_FULL.md` §1.1 the whole time.
3. **Control-arm before blaming.** The generation behaviour, the seam ridge and
   the colour fault were all pre-existing; each looked like a regression until a
   control arm said otherwise.
4. **A test that cannot fail proves nothing.** `test_cap` v1 passed on the broken
   tree because it compared bitstreams on content that never used prediction.

---

## PART XIV — The short version

1. **The study's headline is real and slightly optimistic.** 16-line slices are
   worth 10.1 % at 1.0 bpp and 15.8 % at 0.5 bpp at production width, not 12–13 %.
   Approved by eye and now the default.
2. **Its latency repair is right, with one term missing** (XSL's deferred row) and
   two accounting corrections. Implemented, and every conversion path in the
   product got cheaper today.
3. **Its negative results all hold**, re-tested at thirty times the data. Do not
   build a λ allocator, a run mode, or an HTJ2K block coder.
4. **Its one open question is settled, and it was asked on the wrong axis** —
   inter-scale context beats every JPEG 2000 spatial idea by 3×, and still costs
   more memory than it is worth.
5. **The thing it measured and dropped is four times bigger than it thought**, and
   it is the only lever 720p has.
6. **The delivered archive was not the codec.** An eye-approved decision had never
   reached it, and a CRITICAL review finding was live in the tree it was cut from.
   Both fixed; the discipline that failed is recorded.
7. **The eye caught what the metrics did not.** Every gate this project passed was
   judged on a steady frame; the cold intra frame at 0.5 bpp was three to fourteen
   times worse and nobody had looked at it.

---

## PART XV — Addendum: the banking overdraft, priced

The A2 budget is `slice_h·line + slice_period + **0.5·slice_period** + 2·line`.
That third term is the **banking overdraft** — the prefix bound of
`BITSTREAM.md` §5, `spent(k) ≤ (k+1)B + B/2` — and it is **20 % of the whole
budget**. The JPEG 2000 study named it as an available lever and did not measure
it: *"the quality cost of removing it was not measured"*.

It is measured now. `OMC_OD` (percent of B) was added to the research tree only;
the encoder is byte-identical to pristine with it unset.

**Tightening it is backward-compatible by construction.** §5's prefix bound is an
UPPER bound, so a stream that overdraws less decodes on any decoder built for the
looser one. No bitstream change, no minor bump.

## 15.1 What it costs in picture — essentially nothing

1080p, `slice_h` 8, ship stack, three clips, worst steady-state frame, all three
planes, against the shipped B/2:

| overdraft | beach 0.5 | beach 1.0 | heli 0.5 | heli 1.0 | city 0.5 | city 1.0 |
|---|---|---|---|---|---|---|
| 25 % of B | +0.01 / −0.02 / +0.00 | +0.01 / +0.01 / +0.01 | +0.01 / −0.01 / −0.03 | +0.01 / +0.01 / +0.02 | −0.04 / +0.00 / +0.02 | −0.04 / −0.01 / +0.00 |
| 12 % of B | +0.02 / +0.01 / +0.01 | +0.03 / +0.01 / −0.04 | +0.02 / +0.03 / +0.01 | +0.03 / +0.01 / +0.02 | −0.04 / −0.00 / +0.00 | +0.00 / −0.01 / −0.02 |
| **0** | +0.04 / +0.01 / +0.01 | +0.05 / +0.02 / −0.09 | +0.02 / +0.06 / +0.01 | +0.03 / +0.00 / +0.03 | −0.04 / −0.02 / −0.01 | −0.04 / −0.01 / −0.01 |

Every figure is within ±0.09 dB — noise. **Exact CBR is unchanged** (identical
byte counts throughout). At 0.4 and 0.5 bpp including the cold intra frame, the
same: ±0.04 dB. **Overflow retry counts are unchanged** (beach 0.4 bpp: 300
slices needing >1 attempt at B/2, 290 at zero), so there is no hardware
throughput penalty either.

## 15.2 And it *improves* the artifact class this project has been fighting

PSNR would average a localised effect away, so two decode-internal detectors were
run as well. **The tail-debt signature** — mean squared error of the last 8 slices
divided by the rest, the mechanism behind the bottom-band work that RBOOST and
the tail guard exist to mitigate:

| clip / rate | B/2 (ship) | 25 % | 12 % | 0 |
|---|---|---|---|---|
| beach 0.5, cold frame | 1.404 | 1.195 | 1.173 | **1.134** |
| beach 1.0, steady | 2.897 | 2.809 | 2.516 | **2.466** |
| heli 0.5, cold frame | 1.417 | 1.171 | 1.113 | **1.089** |
| heli 1.0, steady | 1.190 | 1.079 | 1.006 | **0.964** |
| city 0.5, cold frame | 0.646 | 0.561 | 0.556 | **0.543** |

Seam step excess is unchanged throughout (within noise).

The mechanism is plain: **the overdraft is exactly what lets early slices
overspend, and exact CBR then makes the last slices repay.** That debt is the
tail-debt artifact class. Removing the overdraft removes the mechanism that
creates it — a 15–30 % improvement in the signature.

## 15.3 What it would buy

The overdraft is 0.5 slice periods:

| case | with B/2 | with no overdraft |
|---|---|---|
| 1080p50, 16 lines, with a conversion | 0.961 ms | **0.814 ms** |
| 2160p50, 32 lines, with a conversion | 0.933 ms | **0.786 ms** |
| 720p50, 12 lines, with a conversion | 0.917 ms | **0.722 ms** |
| 720p50, 16 lines, codec alone | 1.168 ms | 1.057 ms — still over |

## 15.4 What is NOT established

- **No eye check.** Banking exists so hard slices can borrow; the risk is a
  localised failure on one hard slice that PSNR averages away and these two
  detectors do not happen to catch. This project's own history says that is
  exactly how such things hide.
- **RBOOST and the tail guard were tuned WITH the overdraft present.** At zero
  overdraft they may now over-correct. Their constants want re-checking before
  adoption, not after.
- Three clips, 1080p, `slice_h` 8. Not swept over 4K or over slice heights.

**Status: a strong candidate, not a decision.** It costs no bitrate, needs no
bitstream change, is backward-compatible, appears to *reduce* an artifact class,
and returns a fifth of the latency budget. It needs an eye pass and a re-check of
the two mechanisms that were tuned around it.

---

## PART XVI — Overdraft removed (approved), and what fell out of the control arm

**Delivered: `Codec/Current/omc_v4.11_20260812.zip`.** `OD_CAP_PCT = 0`;
`OMC_OD=<percent of B>` restores the old behaviour and was verified to reproduce
the pre-change encoder **byte-exactly**. The 0.5-slice-period term was removed
from the latency model in all four places that carried it. Decoder tolerance is
deliberately unchanged — the per-slice 2·B wire cap and every buffer sized from it
stay, so streams from older, overdrawing encoders still decode.

Verified from a clean unpack: five suites green, `rt = 0` and exact CBR at
4:2:2/10 and 4:4:4/12 at slice heights 8 and 16.

## 16.1 It changes the latency picture more than expected

With no overdraft **and** the raster-clocked output stage:

| | before today | now |
|---|---|---|
| 1080p50, 16 lines, with a conversion | 1.069 ms (refused) | **0.813 ms** |
| 2160p50, 32 lines, with a conversion | 1.061 ms (refused) | **0.786 ms** |
| 720p50, 16 lines, codec only | 1.168 ms | **0.945 ms** |
| 720p50, 16 lines, with a conversion | 1.612 ms | 1.140 ms — still over |
| 720p59.94, 16 lines, with a conversion | 1.345 ms | **0.951 ms** |

**720p is no longer categorically stuck at 8 lines.** It fits at 59.94/60 Hz
including conversions, and at 50 Hz on a leg that never converts. The default
stays 8 because `uc_ratio` is advisory — a decoder may convert on its own
initiative, and 8 is the choice that holds whatever the far end does. The claim in
`BITSTREAM.md` §7 and `LATENCY.md` that 16 lines put 720p50 at ~1.17 ms has been
corrected; it is 0.945 ms.

## 16.2 The control arm found something else: A4 does not hold with XSL on

Running the generation chain on the new build showed no lock. **The control arm
showed it was not the overdraft:**

| configuration | generation chain, 2048×1152 @ 2.0 bpp |
|---|---|
| pristine defaults (no env) | **locks** — byte-identical from generation 4 |
| ship stack, old overdraft | does not lock: g3→g4 67.3 dB, g4→g5 68.9, g5→g6 69.8 |
| ship stack, no overdraft | does not lock: 68.0, 68.8, 69.5 |

Bisected knob by knob. Dropping `OMC_DCFB`, `OMC_SPC`, `OMC_RBOOST`,
`OMC_FORCE_PROF`, `OMC_ALLOC`, `OMC_TAILGUARD` or `OMC_FILLHYST` changes nothing.
**Dropping `OMC_XSL` makes it lock.**

The mechanism: the generation lock verifies that a candidate plan reproduces its
input bit-exactly, but XSL level 3 lets slice *k* **edit the previous slice's last
row after the fact** — so the reconstruction the lock verified is not the one
emitted.

The deltas are tiny and **shrinking**, so A4's substance (no accumulating loss)
holds; the documented and tested claim (byte-identical from generation 2) does
not, in the configuration that actually ships. `test_generations_byte_stable` runs
at pristine defaults, where the chain locks, so it has never seen this. Entered in
`OPEN_DECISIONS.md` as **A4-XSL**, flagged as having no hook until that test is
run with the ship stack.

---

## PART XVII — Overdraft knob removed; and A4-XSL is degradation, not drift

The overdraft knob is gone — no `OMC_OD`, no variable, no term in the expression.
The prefix bound is simply `(k+1)·bits_per_slice`. Delivered as
**`Codec/Current/omc_v4.11.1_20260812.zip`**, verified byte-identical to v4.11 at
its default and green on all five suites from a clean unpack.

Chasing the generation behaviour to its end changed the severity of PART XVI's
finding. Measuring each generation against the **original master** rather than
against the previous generation:

| clip / rate, generation 1 → 6 | XSL off | XSL on |
|---|---|---|
| heli 2048×1152 @ 2.0 bpp | +0.18 dB | **−3.22 dB** |
| beach 1920×1080 @ 1.0 bpp | +0.01 dB | −0.09 dB |
| city 1920×1080 @ 0.5 bpp | — | −0.51 dB |

This is **degradation, not drift**. It is still falling at generation 8 (−4.08 dB
from generation 1); generation 2 against generation 8 differs on 15.6 % of samples,
worst by 43 code values. It is worst at **high rate** — where a contribution codec
runs for quality-critical work.

A4 names this failure mode in terms: *"quality quietly eroding every time the
signal is re-encoded — a classic failure mode of codecs not built for
contribution, and it is fatal here."*

Bisected within XSL: **level 1, the boundary term alone, already breaks it**
(g4→g5 85.4 dB), level 2 makes it worse (71.4), level 3 worse again (68.8).
Turning the barrier display blend off does not help — so it is the **in-loop**
coupling, not the display edit.

Full diagnosis, proposed fix and interim posture: `OPEN_DECISIONS.md`, entry
**A4-XSL**.

---

## PART XVIII — The self-detection idea, tested: it fails, and the failure is the diagnosis

Proposed in PART XVII: let the encoder detect from the picture alone that it is
not the first OMC in the chain, using the lattice signature the generation lock
already computes, and self-disable XSL. Tested with a standalone probe
(`probe.c`) so the signal could be seen before anything was built on it.

Fraction of nonempty bands whose lattice exponent is ≥ 1:

| input | XSL off | XSL on |
|---|---|---|
| camera masters — beach, heli, city, trees, 1080p and 4K | **0.00 %** | 0.00 % |
| one OMC pass @ 0.5 bpp | **82–100 %** | **0.38 %** |
| one OMC pass @ 2.0 bpp | **63–74 %** | **0.03 %** |

Slices that lock when re-encoding a first-hop decode: **31 of 72 with XSL off,
0 of 72 with XSL on.**

**With XSL off the detector is perfect** — total separation, zero false positives
on five masters across two resolutions. **With XSL on the signature is erased.**
XSL edits the reconstruction at every slice boundary by a sub-step amount; the
vertical transform touches all of a slice's rows, so a perturbation in rows 0 and
15 propagates into every band and every lattice exponent collapses to zero.

**XSL erases the evidence that it has been applied.** That is not a side effect of
the generation problem — it is the generation problem, stated exactly.

Three consequences, one of which is a retraction:

- The self-detection idea **cannot work**: the thing to detect has hidden itself.
- The **frame-scoped lock proposed in PART XVI is retracted**. It has nothing to
  verify: the lock needs lattice-aligned candidates and XSL leaves none.
- **Folding the blend into the coding decision is not viable either.** The blend
  moves rows by ≤ 4 codes; at 0.5 bpp the affected bands have steps of 16–64. The
  correction is finer than one quantiser step, which is *why* it is a
  post-reconstruction edit and not a coding decision.

What survives is in `OPEN_DECISIONS.md` under **A4-XSL**: operator declaration
(the `--tf` pattern, available today), declaring XSL single-hop, or making the
boundary edit a reversible integer lifting step — the construction `omc_uc`
already uses. The last is a design sketch, untested.

---

## PART XIX — Where each problem actually lives, and the fix that needs no format change

Dan pushed back on the reversible-edit sketch: *"each generation removes the blend
and reapplies it — that sounds a bit non-neat."* The mechanical answer is that the
reapplied blend cannot differ, because the undo restores a bit-identical picture
and the same function on the same input gives the same output. But the instinct was
right, and following it produced a better option.

Measuring **when** each problem happens — generation loss (gen 1 → 6, luma against
the master) and seam step at generation 1, same clips, three rates:

| clip | 0.5 bpp | 1.0 bpp | 2.0 bpp |
|---|---|---|---|
| heli — loss / seam | −1.19 / **+1.47** | −1.96 / +0.31 | **−4.66** / −0.42 |
| beach — loss / seam | −0.13 / **+3.60** | −0.19 / +1.42 | **−3.30** / −1.04 |
| city — loss / seam | −0.44 / **+9.71** | +0.03 / +2.64 | **−2.09** / −0.43 |

**The two problems are at opposite ends of the rate range on every clip.** By
2.0 bpp the seam excess has gone *negative* — the boundary rows come out smoother
than the interior, so the blend is over-smoothing rather than repairing — while
the generation loss is 2 to 4.7 dB. At 0.5 bpp the seam is the whole story and the
generation loss is 0.1 to 1.2 dB.

So XSL earns its keep exactly where generations do not care, and costs the most
exactly where it is not needed.

That points at a fix with none of the cost of the reversible-edit design:
**decide XSL per stream from the boundary step the encoder can already measure.**
Encoder-side, carried by the existing minor, no new field, no decoder change, no
format change, no operator setting. It is the same principle
`CAP_RULE_REVIEW.md` F3/F4 reached for the blend cap — key it on the thing it is
there to fix — turned on the feature itself. Recorded in `OPEN_DECISIONS.md`
under A4-XSL as option 1. Not built.

---

## PART XX — `--xsl auto`: built and tested

The proposal from PART XIX, implemented and measured. Delivered as
**`Codec/Current/omc_v4.12_20260812.zip`**.

**What it does.** `omc_xsl_probe_frame()` encodes frame 0 once with XSL off and
measures, on its own reconstruction, how much bigger the row-to-row step is *at*
the slice boundaries than everywhere else. Above 3 codes at 10-bit —
`BITSTREAM.md`'s own "clean" reference — there is a seam worth repairing and XSL
goes on; at or below it there is not, and the stream is written without XSL. The
threshold scales with bit depth. Encoder-side, once per stream, and **the existing
stream minor already carries the decision** — no new field, no decoder change, no
format change, no operator setting.

**The decision matches the analysis 9 times out of 9:**

| clip | 0.5 bpp | 1.0 bpp | 2.0 bpp |
|---|---|---|---|
| beach | 9.60 → **on** | 4.55 → **on** | 0.61 → off |
| heli | 4.31 → **on** | 1.92 → off | 0.59 → off |
| city | 19.25 → **on** | 6.86 → **on** | 1.93 → off |

**End to end, six generations** — generation loss with XSL forced on, against the
same chain under `--xsl auto`:

| clip | rate | forced on | `--xsl auto` | outcome |
|---|---|---|---|---|
| beach | 0.5 | −0.13 | −0.06 | XSL on, seam repaired |
| beach | 1.0 | −0.19 | −0.37 | on (flaps, see below) |
| beach | 2.0 | **−3.30** | **−0.07** | off |
| heli | 0.5 | −1.19 | −1.12 | on, seam repaired |
| heli | 1.0 | **−1.96** | **+0.08** | off — **chain LOCKS byte-exactly** |
| heli | 2.0 | **−4.66** | **+0.25** | off — **chain LOCKS byte-exactly** |
| city | 0.5 | −0.44 | −0.37 | on, seam repaired |
| city | 1.0 | +0.03 | +0.02 | on |
| city | 2.0 | **−2.09** | **−0.11** | off |

**Every generation loss above 1.2 dB is gone**, and two chains now lock
byte-exactly — full A4 compliance restored where XSL was not earning its keep. The
seam fix is kept wherever the seam is visible: city at 0.5 bpp still goes 19.25 →
9.51, beach 9.60 → 3.56.

**Verified:** nothing changes unless asked — without the flag the encoder is
byte-identical to v4.11.1 at every rate, with XSL off and on; `--xsl 0` and
`--xsl 3` force correctly (minor 7 / 9); `rt = 0` byte-exact with an automatic
decision in play; all five suites green from a clean unpack.

**Two honest weaknesses.**
1. **The decision can flap near the threshold.** beach at 1.0 bpp switched off at
   generation 5 and back on at 6, and its loss (−0.37) is slightly worse than
   forced-on (−0.19). A hysteresis band would fix it; I have not added one because
   tuning it on the three clips it was measured on is how thresholds get fitted to
   their test set.
2. **One residual trade remains.** heli at 0.5 bpp still loses 1.12 dB across six
   generations, because there the seam *is* worth repairing (4.31 unrepaired) and
   XSL is correctly switched on. The rule does not remove the trade — it stops
   paying for it where there is nothing to buy.

---

## PART XXI — Can the codec know when a seam needs repairing? Tested, and the answer splits

Dan's concern about `--xsl auto`: *"my only concern is the codec's ability to truly
know when a seam is needed."* Tested three ways.

## 21.1 The frame-0 probe is defeated by a scene cut — demonstrated

A stream of 8 frames: 4 easy, a cut, then 4 hard, at 1.0 bpp. The probe measured
1.92 on frame 0 and correctly decided XSL off *for that content*. Then the cut:

| frame | unrepaired | `--xsl auto` | XSL forced on |
|---|---|---|---|
| 0–3 (easy) | 1.5–1.9 | 1.5–1.9 | 0.0–0.3 |
| **4 (the cut)** | **7.69** | **7.69** | **3.24** |
| 5–7 (hard) | 5.2–5.6 | 5.2–5.6 | 1.3–1.6 |

After the cut the seam is 7.69 — above the 6.6 the project itself called a
visibility regression — and `--xsl auto` leaves it entirely unrepaired. **A
once-per-stream decision cannot survive a scene cut, and cuts are routine.**

## 21.2 The codec already had a per-slice mechanism, keyed on the wrong thing

XSL levels 4/5 scale the blend continuously per slice from how empty the slice's
detail band is — no thresholds, no signalling, cut-proof by construction. Exactly
the right architecture. But the proxy is **backwards for this job**:

| | unrepaired | level 3 | level 4 |
|---|---|---|---|
| city @ 0.5 bpp | 19.25 | **9.51** | 17.00 |
| beach @ 0.5 bpp | 9.60 | **3.56** | 8.37 |

Busy slices get almost no blend — and busy slices are where the seam is worst.
Level 4's smaller generation loss is not a virtue; it is the arithmetic of barely
editing anything.

## 21.3 Level 6: same architecture, keyed on the seam itself. Built and shipped

`OMC_XSL=6` scales the blend by what it is actually there to fix — the step across
the join minus the picture's own steps either side of it — continuously, per slice
boundary, per plane, recomputed every frame. Zero when the join is no sharper than
the surrounding texture; rising to full above that. No threshold, no cliff at a
content transition. Both ends derive it from reconstructions they both hold, so
there is **no side information, no new field and no bitstream change.**

| clip / rate | unrepaired | level 3 seam / loss | **level 6 seam / loss** |
|---|---|---|---|
| beach 0.5 | 9.60 | +3.56 / −0.06 | +3.87 / −0.34 |
| beach 2.0 | 0.61 | −1.04 / **−3.30** | −0.01 / **−1.74** |
| heli 1.0 | 1.92 | +0.30 / −1.94 | +0.69 / −1.59 |
| heli 2.0 | 0.59 | −0.42 / **−4.66** | +0.15 / **−3.34** |
| city 0.5 | 19.25 | +9.51 / −0.37 | +9.80 / −0.45 |
| city 2.0 | 1.93 | −0.43 / **−2.09** | +0.46 / **−1.77** |

**Repairs as well as level 3** — within 0.3 codes on all nine points — **and cuts
the worst generation loss from −4.66 to −3.34 dB**, while being cut-proof.
Verified `rt = 0` byte-exact at 4:2:2 and 4:4:4, 10- and 12-bit, slice heights 8
and 16; levels 0–5 byte-identical to the previous build. Delivered in
`omc_v4.13_20260812.zip`.

## 21.4 The structural finding, which no tuning escapes

**Seam repair and generation locking are mutually exclusive per slice.** The lock
needs a slice's coefficients on the quantiser lattice; *any* edit at all, however
small, puts them off it. Level 6 still touches 91–100 % of boundaries — 0 % get
zero blend at 0.5 bpp, 6–9 % at 2.0 — which is exactly why it recovers only about
a third of the loss.

Widening the dead zone would trade repair for generations one for one. There is
no setting that gives both.

So the answer to the question as asked: **per slice, yes, the codec can know —
level 6 measures it directly and survives cuts. Per stream from frame 0, no.** But
knowing was never the hard part. Acting on the knowledge is what costs generations,
and that is structural until the edit itself is made reversible.

---

## PART XXII — Does level 6 create a new kind of "ants"? Measured with the project's own instrument

Dan: *"'recomputed every frame' — are we creating a new form of ants, where there
is a ton of business because it gets recomputed every frame?"*

The mechanism he names is real: if the blend strength changes frame to frame, the
boundary rows are nudged by a different amount each frame, and that is temporal
activity concentrated on horizontal lines — which is what E-10 fixed for the grain
fill by making the sign tile frame-independent.

Measured with the ledger's own metric (E-9 viewer box: beach 2048×1152,
x[1434,1608], y[1093,1146], 12 frames; ant-tail = P(|Δ| > 6)), plus a
seam-specific version — how much more the boundary rows change frame to frame
than the rest of the picture:

| rate | arm | ant-tail % | box boil | seam TEMPORAL excess | seam SPATIAL |
|---|---|---|---|---|---|
| — | source | 15.36 | 3.739 | +0.104 | — |
| 0.5 | XSL off | 23.47 | 4.709 | +0.515 | +8.86 |
| 0.5 | level 3 | 23.49 | 4.751 | −0.928 | +2.59 |
| 0.5 | **level 6** | **22.45** | **4.585** | −0.789 | +3.07 |
| 1.0 | XSL off | 15.61 | 3.839 | +0.287 | +3.68 |
| 1.0 | level 3 | **15.01** | **3.767** | −0.579 | +0.82 |
| 1.0 | **level 6** | **17.07** | **3.970** | −0.253 | +1.03 |
| 2.0 | level 3 | 17.21 | 3.906 | −0.472 | — |
| 2.0 | level 6 | 17.58 | 3.950 | −0.027 | — |

**His concern is real, and it appears exactly where the mechanism predicts.** At
0.5 bpp the strength is saturated almost everywhere, so level 6 behaves like level
3 — and in fact measures *better* on both ant metrics. At 1.0 bpp the strength sits
in the middle of its range and varies frame to frame, and that is where the cost
shows: **+2.06 points of ant-tail and +0.20 of box boil against level 3.** At
2.0 bpp it is +0.37 points.

Two things worth noting alongside it. Level 6's *seam temporal excess* is the
closest to neutral of any arm at every rate (−0.03 to −0.79 against level 3's
−0.47 to −0.93): the joins neither stand out nor are unnaturally calmed. And at
0.5 bpp — where the seam is the actual problem — level 6 is the best arm on both
ant metrics.

**The obvious fix is blocked by the architecture.** Smoothing the strength across
frames would remove the variation, but `BITSTREAM.md`'s opening paragraph is
explicit: *"the decoder holds no state across slices or frames (each slice is
decoded from its own bytes alone)."* A temporal filter on the strength would break
that, and it is a property the whole error-containment design rests on.

**Status: this needs the eye, and it should not ship on a metric.** 2 points on a
scale where the E-9/E-10 work moved 18.0 → 7.98 is not large, but it is in the
direction of a defect this project spent a release closing, and ants are a
temporal defect that a still frame cannot show. Delivered
`AB_seam_boil_2026-08-12.zip`: the E-9 viewer box at 1.0 bpp, 2× nearest,
losslessly encoded so the container adds nothing — source, level 3, level 6.

---

## PART XXIII — The colour conversion fault, found and fixed

## 23.1 What was failing

`tests/test_cc.c` gate 8c, in the codec's own suite. A colour-space conversion
mixes the three components together, which only means anything where all three
sit at the same pixel — and 4:2:2 chroma does not. So the tool takes a detour:
stretch chroma to full width, convert, shrink back. The gate measures what that
costs on picture-like chroma and allows an average error of 0.1 code with no
pixel worse than 3.

| | average | worst | verdict |
|---|---|---|---|
| delivered archive | 0.02 | 2 | passes |
| working tree | **0.10** | **4** | **fails** |

The white-noise reading, not a pass criterion but a good thermometer, had gone
from 37.20 to 69.61 — the filter had genuinely changed, not drifted.

## 23.2 Why

The tree had moved the rational scaler to **centre-aligned** sampling: output
sample *r* maps to source position `(2r+1)·num/(2·den) − ½` instead of `r·num/den`.
That is a real improvement for **resizing a picture** — 1080p → 2160p then keeps
the picture where it was instead of shifting it half a source sample.

It was applied to every caller, including the chroma detour. But in 4:2:2 chroma
sample *k* is **co-sited** with luma sample *2k* — `BITSTREAM.md`'s own
`[1,2,1]/4` convention — so re-centring the chroma grid puts the colour a quarter
sample off the luma it belongs to. And centring needs filters at half-phases,
which the code derives by averaging two published phases; that average is a
blunter filter, which is where the round-trip accuracy went.

Confirmed by experiment: restoring the old mapping put the figures back to
0.02 / worst 2 exactly.

## 23.3 The fix — not a revert

Both conventions are correct, for different jobs, so the siting is now an
explicit choice:

```
OMC_SITE_CENTRE    output grid centred on the source grid  — resizing a picture
OMC_SITE_COSITED   output sample 0 on source sample 0      — chroma siting
```

`omc_uc_scale_plane()` keeps the centred behaviour, since resizing is the common
case; `omc_uc_scale_plane_sited()` names it. The chroma detour asks for co-sited,
and gate 8c now exercises the same path the tool uses.

It is a **parameter, not a field of `omc_uc_t`** — the reason is already in the
header, written about `mirror`: *"a flag inside the operator config is one a
caller can forget to initialise, and a stack-allocated omc_uc_t with a garbage
byte in it would mirror at random."*

**Verified.** On a ramp through a 1:2 upscale, co-sited puts output 40 at source
position **20.000** and centred puts it at **19.750** with output 41 at **20.250** —
both exactly where their convention says. Gate 8c back to 0.02 / worst 2. All
five suites green on the working tree. Encoder output byte-identical to
`omc_v4.13_20260812.zip`.

## 23.4 A mistake of mine, found while fixing it

Mirroring my changes into the working tree, I had copied `src/codec.c` **wholesale**
from my archive-derived tree. That silently dropped 307 lines of the working
tree's own newer work — `omc_fillcorr` (the parent-band grain fill, E-1 from
`ENERGY_GAPS.md`) and its counters, plus `omc_recoff`. The build only failed later,
when `omc_dec.c` went looking for symbols that were no longer there.

Repaired from the snapshot I had taken before touching that tree: its own
`codec.c` restored, and every one of my changes re-applied as **targeted edits**
rather than a file copy — the per-context cap, the 4:4:4 threshold, the overdraft
removal, XSL level 6 and the `--xsl auto` probe. Verified afterwards that all
three of their symbols are back, all six of my changes are present, five suites
green, and the encoder is byte-identical to the delivered codec.

The other files I had copied — `config.c`, `omc_enc.c`, `test_unit.c`,
`test_uc.c` — were checked and are identical to the archive in that tree, so they
lost nothing.

**The lesson, recorded because it nearly destroyed someone else's work:** never
mirror a change by copying a whole file into a tree you did not write. Apply the
edit.

---

## PART XXIV — Why the scaler edits were made, and a miss of mine

## 24.1 The record exists, and it was in the folder I was asked to review

`new_ideas/08112026/SESSION_LEDGER_FULL.md` §1.1, *"upconverter centre alignment
(FIXES A REAL DEFECT)"*. **I skipped that file, believing it duplicated the
project-root ledger. It does not** — it is the record of the work done after the
2026-08-11 archive was cut, and it answers the question directly. That is a miss
on my part in the reading the prompt asked for.

## 24.2 What it says

**The defect.** The rational scaler mapped output pixel *r* to source position
`r·num`, which is corner-aligned; every standard scaler is centre-aligned. At 3:1
the picture landed **one source pixel up and to the left**, and the error grows
with the ratio. The symptom that exposed it: a 4K → 720p round trip lost
**3.65–6.73 dB against lanczos** while a chirp test showed OMC actually *aliases
less* — so the filter was right and the geometry was wrong.

**The result.** Measured on three clips, 4K → 720p:

| clip | vs box, before → after | vs lanczos | round trip (lanczos = reference) |
|---|---|---|---|
| Bosphorus | 39.18 → **53.21** | 39.08 → **62.74** | 37.89 → **44.66** (lanczos 44.55) |
| CityAlley | 36.62 → **47.33** | 36.74 → **57.70** | 34.11 → **37.84** (lanczos 37.76) |
| ReadySetGo | 32.13 → **45.32** | 32.08 → **55.45** | 30.92 → **37.82** (lanczos 37.66) |

Residual sub-pixel shift search returns exactly (0.00, 0.00) on all three. After
the fix OMC's downscale is **ahead of lanczos** on information retention by
0.08–0.17 dB. This is good work and it should stay.

## 24.3 The record already contains the principle my fix restores

From the same section, verbatim:

> *"The dyadic 2× path is deliberately untouched (its corner alignment is what
> preserves source samples exactly and keeps `down(up(x))` byte-exact)."*

They knew corner alignment is what makes the exact round trip work, and spared the
**dyadic** path for exactly that reason. The 4:2:2 chroma detour is dyadic in
ratio — 1:2 out, 2:1 back — but it runs through the **rational** code path, so it
was re-centred along with everything else. That is the whole gap, and my fix
applies their own stated principle to the one path it was missed on. It is not a
disagreement with the work; it completes it.

## 24.4 A bonus: it also clears their own MUST-FIX from the chroma path

`writeups/C3_AUDIT.md` raises **H-1 (MUST FIX before a hardware claim)**: the
derived half-phase coefficients are computed at *runtime*, and C3's guarantee rests
on coefficients being compile-time constants — *"a runtime coefficient times a
pixel is a real multiplier"*. Counted over every ratio up to 16:16 and 64 output
samples:

| mapping | needs a derived half-phase |
|---|---|
| centred | **8 192 of 16 384** (exactly half) |
| co-sited | **0 of 16 384** |

So the chroma detour, now co-sited, never reaches the derived coefficients at all
and is free of H-1 entirely. H-1 still stands for genuine picture resizes, and the
fix proposed there — emit the derived phases into the generated table so hardware
gets a `2·den`-entry ROM — is still the right answer for those.

## 24.5 Two more documents I had not read

`writeups/FILL_CORRELATION.md` and `FILL_CORRELATION_REVIEW.md` — the record of
the `omc_fillcorr` work, which is the work I nearly destroyed by copying a file.
Read now. Its own adversarial review is blunt about it: the mechanism is real and
correctly implemented, but worth **~2.5 % of the half-rate NEG gap**, measured on
one clip which is the mildest of the set, with a stage-3 result that contradicts
its own explanation. Retained as a small confirmed gain, not a route to the goal.

Also noted: the project-root ledgers are now `SESSION_LEDGER_20260811.md` and
`SESSION_LEDGER_FULL_20260811.md` — renamed, same byte counts, nothing lost.


---

## PART XXV — The reversible boundary edit, built and tested

## What was built

XSL level 7: the boundary edit rewritten as a two-step lifting cascade, in
`src/codec.c`, with its inverse `omc_xsl_unblend()` and a tool to apply it.

    forward   step 1   row15 += clamp((row0   - row14) / 4)   -- row15 not read
              step 2   row0  += clamp((row15' - row1 ) / 4)   -- row0  not read
    inverse            row0  -= clamp((row15' - row1 ) / 4)
                       row15 -= clamp((row0   - row14) / 4)

Each step adds a correction built only from rows it does not touch, so
subtracting the same correction returns the original exactly. The shipped level
3 instead moves each row toward a target computed from its own value, which
discards what the row was -- that is why it cannot be undone.

The inverse also had to repeat the A5 refresh-barrier rules, because the forward
edit is suppressed on refreshed slices and an inverse that "undoes" an edit that
never happened is worse than no inverse at all. Both are derivable from the
slice header and config alone, which is what makes this possible at all.

## Result 1 — the inverse is exact

Ground truth is a decode with `OMC_XSL_NOEDIT=1`: every other level-7 behaviour
kept, only the edit skipped. (Decoding at level 0 is NOT ground truth -- it also
drops the cross-slice wavelet term and changes the whole slice. Measuring
against it produced a spurious "6.1% wrong" that cost an hour.)

    the edit changed 314,036 samples, worst 4 codes
    unblend(edit(recon)) == recon, byte for byte

## Result 2 — it repairs the seam

Seam step excess, codes, 0.5 bpp / slice_h 16 (lower is flatter):

| clip  | no repair | level 3 | level 6 | level 7 |
|-------|-----------|---------|---------|---------|
| city  | +15.978   | +6.831  | +6.750  | +6.978  |
| beach | +8.611    | +2.489  | +2.751  | +2.903  |
| heli  | +3.717    | +1.029  | +1.201  | +1.193  |

## Result 3 — it removes most of the generation loss

Six generations, beach, 3.0 bpp, slice_h 8 -- the setting where the CONTROL
locks hardest (73/270), so a failure to lock fails against a live signal:

| arm | lock @g2 | g1 | g6 | loss |
|---|---|---|---|---|
| level 0, no repair at all | 73/270 | 55.404 | 55.107 | **-0.30 dB** |
| level 3, shipped | 0/270 | 53.785 | 45.611 | **-8.17 dB** |
| level 7, no undo | 0/270 | 53.399 | 41.716 | -11.68 dB |
| level 7, always undo | 34/270 | 55.230 | 52.639 | -2.59 dB |
| level 7, undo when input IS a decode | 31/270 | 53.399 | 51.587 | **-1.81 dB** |

78% of the generation damage removed, with the seam repair intact.

## Result 4 — it needs a detector, and blind undoing costs real quality

An encoder that always undoes also undoes on FIRST-generation material, where
there was nothing to undo. The decoder then re-applies the edit and the two
cancel:

    seam step excess, first generation, 0.5 bpp / sh 16
    clip    no repair   level 3   level 7   level 7 + blind undo
    city    +15.978     +6.831    +6.978    +9.648
    beach    +8.611     +2.489    +2.903    +4.873

About a third of the repair is lost. So the scheme is only as good as the
"is my input a previous decode?" test -- and it is wrong in both directions:
say "decode" on a master and you lose the repair, say "master" on a decode and
you take the full -8 dB slide.

## Result 5 — the finding that matters more than the idea

The ridge the edit exists to repair COLLAPSES with rate, and the lock only fires
at high rate. They occupy nearly disjoint ranges.

Un-repaired seam, absolute and scale-free (x1.000 = join no worse than interior):

| clip  | 0.5 bpp | 1.0 bpp | 2.0 bpp | 3.0 bpp |
|-------|---------|---------|---------|---------|
| city  | x1.824  | x1.269  | x1.067  | x1.013  |
| beach | x1.705  | x1.294  | x1.048  | x1.021  |

And above ~1.5 bpp both level 3 and level 7 overshoot -- they make the join
SMOOTHER than the picture around it (city at 3.0 bpp: level 3 -1.707, level 7
-3.119 codes), while control lock rises with rate (heli 0/68 at 0.5 bpp, 26/68
at 3.0 bpp).

**So above roughly 1.5 bpp the edit repairs nothing, over-smooths the joins, and
blocks the lock.** Switching it off there gets full repair where it is needed,
no over-smoothing, and the full generation lock -- with no format change and no
detector. That is a better answer than the reversible edit for most of the
operating range. The reversible edit remains the only answer if both are ever
needed at the SAME rate.

## Discarded results

The first two generation tables measured with `OMC_XSL=7` were meaningless: a
minor-9 stream always decodes at level 3 regardless of the environment, so a
level-7 encoder was silently paired with a level-3 decoder. Found by
instrumenting the edit and seeing it fire zero times. `OMC_XSL_FORCE=1` is
required for any level-7 measurement.


---

## PART XXVI — Correction: the rate threshold is NOT the better answer

Result 5 of Part XXV recommended switching the boundary edit off above ~1.5 bpp
instead of making it reversible. That recommendation was wrong, and the reason
is that it never checked the rates OMC actually runs at.

Six generations, slice_h 16, at 0.5 and 1.0 bpp. "No repair" is the ceiling --
what generation behaviour looks like with nothing in the way.

| clip / rate | arm | lock @g2 | g1 -> g6 |
|---|---|---|---|
| city 0.5 | no repair | 0/136 | -0.61 dB |
| city 0.5 | level 3 shipped | 0/136 | -0.48 dB |
| city 0.5 | level 7 + oracle | 0/136 | -0.45 dB |
| beach 0.5 | no repair | 0/136 | -0.64 dB |
| beach 0.5 | level 3 shipped | 0/136 | -0.93 dB |
| beach 0.5 | level 7 + oracle | 0/136 | -0.56 dB |
| city 1.0 | no repair | 0/136 | -0.33 dB |
| city 1.0 | level 3 shipped | 0/136 | -0.23 dB |
| city 1.0 | level 7 + oracle | 0/136 | -0.22 dB |
| **beach 1.0** | **no repair** | **10/136** | **-0.37 dB** |
| **beach 1.0** | **level 3 shipped** | **0/136** | **-1.26 dB** |
| **beach 1.0** | **level 7 + oracle** | **3/136** | **-0.45 dB** |

Three regions, not two:

* **At 0.5 bpp nothing locks, for anybody.** Losses are 0.5-0.9 dB whatever is
  done. There is no lock to protect and no threshold to set. Keep the repair --
  the ridge is 1.7-1.8x the interior step down here and it is the whole reason
  the edit exists.
* **Around 1.0 bpp the two genuinely collide.** On beach the lock starts firing
  (10/136 with no repair), level 3 kills it outright (0/136), and the
  six-generation loss triples: -1.26 dB against a -0.37 dB ceiling. A rate
  threshold cannot help here -- the ridge is still 1.29x at 1.0 bpp, so the
  repair cannot be switched off. **This is inside OMC's operating range and it
  is exactly what the reversible edit is for.** It recovers the lock (3/136)
  and brings the loss back to -0.45 dB against a -0.37 dB ceiling, with the
  seam repair intact.
* **Above ~1.5 bpp** the ridge is gone, the edit over-smooths, and the lock is
  strongest. Either fix works; the threshold is simpler and also removes the
  over-smoothing.

The collision is content-dependent: beach (clean, low detail) locks at 1.0 bpp,
city (busy) does not. Content that locks is content where generations matter
most -- graphics, titles, gradients, skies.

**Revised standing:** the reversible edit is not superseded by the threshold. It
is the answer in the band that matters most, and the threshold is a
complementary simplification above it.


---

# PART G — The generation problem, in full

The complete account, including the resolution sweep, the mechanism, and every
arm tested, is `HANDOFF_BIT_EXACTNESS.md`, delivered alongside this ledger. It is
not duplicated here. The single most important number:

**The goal, stated the way the project means it:** from the first decode onward
the picture must never change again. Decode once, then re-encode and decode as
many times as you like, and the picture must come back byte-identical every time.
Writing `D1` for the first decode, the requirement is `D(E(D1)) == D1`. Stream
equality from generation 2 onward follows from it; **generation 1's stream is not
expected to equal generation 2's**, because they encode different inputs.

The findings, in order of importance:

> 1. **The project's own gate for this fails** —
>    `tests/test_acceptance.py::test_generations_byte_stable`, 1 failed / 8 passed
>    — and it had been silently **skipping** because its masters path defaults to
>    another machine's scratch directory.
> 2. **It is not a regression.** It fails identically on the pristine v4.9
>    archive, the inherited tree, and the delivered v4.14.
> 3. **It fails on genuinely static content with the seam edit switched off**,
>    19.44% of samples moving at generation 2 either way. So there is a baseline
>    failure underneath the seam edit's contribution that has nothing to do with
>    it, and it is the larger problem. `rt = 0` holds, so the fault is in
>    re-encoding, not in encoder/decoder disagreement.
> 4. **Generations converge rather than accumulate** — 26.76% of samples differ
>    at generation 2, 4.62% at generation 3.
> 5. **The seam edit takes the per-slice lock to zero** in all 21 `edit ON` cells
>    of the resolution sweep, though under plain defaults on a different clip it
>    made no difference at all — that dependence is unmapped.
> 6. **Nothing measured this session reached the goal at any resolution.**

Part W records the documentation review that produced 1–4, and the measurement
error of mine that the review exposed.

---

# PART M — Every measurement

Raw transcripts of each run are reproduced verbatim. Where a run was later found
invalid it is kept, and marked, in Part F.


## M.1 Six generations, four arms, beach 3.0 bpp slice_h 8 — the decisive comparison

Produced by `gen7c.sh` (Part S).

```
=== beach  3.0bpp  sh8   (* = stream identical to the one before it)
XSL0 control           lock@g2 73/270    g1=55.404 g2=55.113 g3=55.105 g4=55.107 g5=55.107 g6=55.107*
XSL3 shipped           lock@g2 0/270     g1=53.785 g2=51.152 g3=49.178 g4=47.718 g5=46.558 g6=45.611
XSL7 no undo           lock@g2 0/270     g1=53.399 g2=49.900 g3=47.124 g4=44.976 g5=43.212 g6=41.716
XSL7 + undo            lock@g2 34/270    g1=55.230 g2=54.512 g3=53.916 g4=53.457 g5=53.013 g6=52.639
```

## M.2 The oracle-detection ceiling

Produced by `gen7d.sh` (Part S).

```
XSL7 + ORACLE undo     lock@g2 31/270    g1=53.399 g2=52.948 g3=52.521 g4=52.172 g5=51.862 g6=51.587
  seam step excess at generation 1: -2.632
```

## M.3 Second operating point, and seam context at 3.0 bpp

Produced by `gen7e.sh` (Part S).

```
--- seam step excess at 3.0 bpp / sh 8 (context for the oracle run) ---
    L0 = +0.176
    L3 = -1.396
    L7 = -2.632
--- six generations at city / 1.0 bpp / sh 16 ---
  L0 control          g1=40.556 g2=40.302 g3=40.209 g4=40.227 g5=40.226 g6=40.229   seam@g1 +5.452
  L3 shipped          g1=40.490 g2=40.460 g3=40.472 g4=40.411 g5=40.326 g6=40.255   seam@g1 +1.227
  L7 oracle           g1=40.542 g2=40.362 g3=40.329 g4=40.323 g5=40.322 g6=40.320   seam@g1 +0.941
```

## M.4 Seam ridge and lock availability against rate

Produced by `ridge.sh` (Part S).

```
clip    bpp   sh   | no repair level 3   level 7   | control lock @g2
city    0.5   16   | +15.978   +6.831    +6.978    | 0/68
city    1.0   16   | +5.452    +1.227    +0.941    | 0/68
city    1.5   16   | +2.810    -0.406    -1.135    | 0/68
city    2.0   16   | +1.343    -1.154    -2.241    | 0/68
city    3.0   16   | +0.274    -1.707    -3.119    | 0/68
beach   0.5   16   | +8.611    +2.489    +2.903    | 0/68
beach   1.0   16   | +3.673    +0.766    +0.497    | 8/68
beach   1.5   16   | +1.419    -0.762    -1.398    | 4/68
beach   2.0   16   | +0.631    -1.209    -2.048    | 9/68
beach   3.0   16   | +0.265    -1.385    -2.350    | 19/68
heli    0.5   16   | +3.717    +1.029    +1.193    | 0/68
heli    1.0   16   | +1.616    +0.038    -0.035    | 13/68
heli    1.5   16   | +0.903    -0.317    -0.591    | 12/68
heli    2.0   16   | +0.518    -0.559    -0.920    | 15/68
heli    3.0   16   | +0.131    -0.736    -1.249    | 26/68
```

## M.5 Six generations at the rates OMC actually targets

Produced by `lowrate.sh` (Part S).

```
=== city @ 0.5 bpp, slice_h 16
   no repair (ceiling)      lock 0/136     35.080 34.726 34.625 34.520 34.522 34.473   -> -0.61 dB
   level 3 (shipped)        lock 0/136     35.317 35.145 35.060 35.018 34.960 34.838   -> -0.48 dB
   level 7 + oracle         lock 0/136     35.323 35.189 34.960 34.891 34.886 34.868   -> -0.45 dB
=== city @ 1.0 bpp, slice_h 16
   no repair (ceiling)      lock 0/136     40.556 40.302 40.209 40.227 40.226 40.229   -> -0.33 dB
   level 3 (shipped)        lock 0/136     40.490 40.460 40.472 40.411 40.326 40.255   -> -0.23 dB
   level 7 + oracle         lock 0/136     40.542 40.362 40.329 40.323 40.322 40.320   -> -0.22 dB
=== beach @ 0.5 bpp, slice_h 16
   no repair (ceiling)      lock 0/136     39.813 39.149 39.083 39.054 39.115 39.169   -> -0.64 dB
   level 3 (shipped)        lock 0/136     39.830 39.624 39.466 39.276 39.031 38.897   -> -0.93 dB
   level 7 + oracle         lock 0/136     39.853 39.234 39.285 39.360 39.336 39.294   -> -0.56 dB
=== beach @ 1.0 bpp, slice_h 16
   no repair (ceiling)      lock 10/136    44.957 44.592 44.580 44.594 44.590 44.585   -> -0.37 dB
   level 3 (shipped)        lock 0/136     44.895 44.517 44.279 44.042 43.840 43.639   -> -1.26 dB
   level 7 + oracle         lock 3/136     44.856 44.513 44.457 44.438 44.420 44.404   -> -0.45 dB
```

## M.6 Per-slice lock rate across resolutions

Produced by `resweep.sh` (Part S).

**Read the `id=` column as void.** It compares generation 1's bitstream with
generation 2's, which encode different inputs and were never expected to match;
the comparison means nothing (Part W.6). The transcript is reproduced unedited
rather than re-cut, so the error stays visible. **The lock counts are valid and
stand.** For the goal measured properly, see Part W.4 and `genfix.sh`.

```
BUILD-OK
master                     WxH    sh   bpp   | edit ON        | edit OFF (ceiling)
heli_1920x1080_422_10.yuv  1920x1080 16   0.5   |  0/68 id=no    | 0/68 id=no    |
beach_1920x1080_422_10.yuv 1920x1080 16   0.5   |  0/68 id=no    | 0/68 id=no    |
city_1920x1080_422_10.yuv  1920x1080 16   0.5   |  0/68 id=no    | 0/68 id=no    |
heli_2048x1152_422_10.yuv  2048x1152 16   0.5   |  0/72 id=no    | 1/72 id=no    |
beachbox_2048x1152_422_10.yuv 2048x1152 16   0.5   |  0/72 id=no    | 0/72 id=no    |
dngA4_3840x2160_422_10.yuv 3840x2160 16   0.5   |  0/135 id=no   | 0/135 id=no   |
beach444_1920x1080_444_10.yuv 1920x1080 16   0.5   |  0/68 id=no    | 0/68 id=no    |

heli_1920x1080_422_10.yuv  1920x1080 16   1.0   |  0/68 id=no    | 13/68 id=no   |
beach_1920x1080_422_10.yuv 1920x1080 16   1.0   |  0/68 id=no    | 8/68 id=no    |
city_1920x1080_422_10.yuv  1920x1080 16   1.0   |  0/68 id=no    | 0/68 id=no    |
heli_2048x1152_422_10.yuv  2048x1152 16   1.0   |  0/72 id=no    | 16/72 id=no   |
beachbox_2048x1152_422_10.yuv 2048x1152 16   1.0   |  0/72 id=no    | 4/72 id=no    |
dngA4_3840x2160_422_10.yuv 3840x2160 16   1.0   |  0/135 id=no   | 0/135 id=no   |
beach444_1920x1080_444_10.yuv 1920x1080 16   1.0   |  0/68 id=no    | 6/68 id=no    |

heli_1920x1080_422_10.yuv  1920x1080 16   3.0   |  0/68 id=no    | 26/68 id=no   |
beach_1920x1080_422_10.yuv 1920x1080 16   3.0   |  0/68 id=no    | 19/68 id=no   |
city_1920x1080_422_10.yuv  1920x1080 16   3.0   |  0/68 id=no    | 0/68 id=no    |
heli_2048x1152_422_10.yuv  2048x1152 16   3.0   |  0/72 id=no    | 28/72 id=no   |
beachbox_2048x1152_422_10.yuv 2048x1152 16   3.0   |  0/72 id=no    | 17/72 id=no   |
dngA4_3840x2160_422_10.yuv 3840x2160 16   3.0   |  0/135 id=no   | 0/135 id=no   |
beach444_1920x1080_444_10.yuv 1920x1080 16   3.0   |  0/68 id=no    | 13/68 id=no   |
```

## M.7 Where the generation lock fires at all

Produced by `g7scan.sh` (Part S).

```
beach  bpp 1.0  sh 8    control lock  19/270
beach  bpp 1.0  sh 16   control lock  10/136
beach  bpp 2.0  sh 8    control lock  39/270
beach  bpp 2.0  sh 16   control lock  17/136
beach  bpp 3.0  sh 8    control lock  73/270
beach  bpp 3.0  sh 16   control lock  30/136
city   bpp 1.0  sh 8    control lock   0/270
city   bpp 1.0  sh 16   control lock   0/136
city   bpp 2.0  sh 8    control lock   0/270
city   bpp 2.0  sh 16   control lock   0/136
city   bpp 3.0  sh 8    control lock   0/270
city   bpp 3.0  sh 16   control lock   0/136
```

## M.8 First arm comparison (superseded — see Part F)

Produced by `gen7b.sh` (Part S).

```
city   XSL0-control  lock   0/272  g1 41.182  g2 40.688  drop -0.494
city   XSL3-shipped  lock   0/272  g1 41.130  g2 40.849  drop -0.281
city   XSL7-noundo   lock   0/272  g1 41.163  g2 40.660  drop -0.503
city   XSL7-undo     lock   0/272  g1 41.158  g2 40.762  drop -0.396
beach  XSL0-control  lock  11/272  g1 46.560  g2 46.220  drop -0.340
beach  XSL3-shipped  lock   0/272  g1 46.466  g2 45.919  drop -0.547
beach  XSL7-noundo   lock   0/272  g1 46.415  g2 45.734  drop -0.681
beach  XSL7-undo     lock   2/272  g1 46.616  g2 46.031  drop -0.585
```

## M.9 Measurements carried from earlier in the session

| what | result |
|---|---|
| slice_h 16 vs 8, bitrate saved | 15.8% / 10.1% / 8.1% at 0.5 / 1.0 / 2.0 bpp |
| co-sited vs centred, runtime-derived coefficients | 0 of 16,384 vs 8,192 |
| colour gate 8c after the siting fix | 0.02, worst 2 |
| lattice-aligned bands, master vs decode (edit off) | 0.00% vs 82–100% |
| lattice-aligned bands, decode with level-3 edit on | 0.03–0.38% |
| XSL generation cost across six generations, worst case | −4.66 dB (level 3, earlier corpus) |
| level 6 worst-case generation loss | −3.34 dB |
| lock firing, level 3 off vs on (earlier corpus) | 31/72 vs 0/72 |
| level-7 inverse on a 1080p decode | 314,036 samples edited, all recovered byte-exactly |
| A2 output-stage bound, raster-clocked | 165 geometries simulated row by row, 0 over |

---

# PART F — Falsifications, retractions, and invalid runs

Kept because a result that was thrown away is worth more to the next person than
a result that was kept: it stops them repeating it.

## F.1 Self-detection under the irreversible edit — FALSIFIED

Detecting "is my input my own previous output?" from the quantiser lattice, with
the shipped level-3 edit in place. The edit erases its own fingerprint:

| picture | bands lattice-aligned |
|---|---|
| master (first generation) | 0.00% |
| decode, edit off | 82–100% |
| decode, edit on | **0.03–0.38%** |

## F.2 Frame-scoped generation lock — RETRACTED BEFORE IMPLEMENTATION

Proposed on the assumption that the fingerprint survives within a frame. F.1
disproves that. Retracted by its author.

## F.3 Pre-blending instead of post-editing — ARITHMETICALLY IMPOSSIBLE

Carry the smoothing in the coded signal so there is nothing to undo. The
smoothing moves rows by ≤4 codes; the affected bands have quantiser steps of
16–64. **The correction is finer than one quantiser step**, so it cannot be
expressed in the coded signal. This is why it is a post-edit.

## F.4 `--xsl auto` — BUILT, THEN DEMONSTRATED DEFEATED

A frame-0 probe picks the level for the sequence. A scene cut makes frame 0
unrepresentative. Kept as an explicit option, never a default.

## F.5 "The rate threshold is the better answer" — WITHDRAWN

Recommended, then withdrawn the same session after Dan pointed out it restores
the lock only *above* the threshold while OMC runs *below* it. Measurement
confirmed him: at 1.0 bpp the ridge is still 1.27–1.29× and cannot be switched
off, yet the lock has started firing and the edit annihilates it. See M.5.
The threshold remains worthwhile above ~1.5 bpp and nothing more.

## F.6 `OMC_XSL_FORCE` widening — ADDED ON A WRONG DIAGNOSIS, REVERTED

I believed the environment could not reach the decoder's XSL level, because
`omc_read_stream_header()` sets it to 3 for any minor-9 stream. It can:
`common_init()` re-reads `OMC_XSL` afterwards and lets it win. The widening was
unnecessary and weakened the stream-authority rule; reverted.

**Consequence for Part M.** I had recorded that two early generation tables were
invalid because "a level-7 encoder was paired with a level-3 decoder". **That
reason was wrong** — the decoder was running level 7. The early tables (M.8) are
valid; they simply measured a weak operating point (1.0 bpp, slice_h 16, where
the ceiling itself is only 8–11 locks) and were superseded by M.1 at 3.0 bpp /
slice_h 8, where the ceiling is 73. Both are retained.

## F.7 "Ground truth" that was not — TWO SEPARATE VERSIONS

**Version 1.** Decoding at XSL level 0 to obtain "the reconstruction without the
edit". Level 0 also drops the cross-slice wavelet term and changes the whole
slice. Reported a spurious **6.1% of samples wrong**. Fixed by adding
`OMC_XSL_NOEDIT`, which skips only the edit.

**Version 2.** Comparing two decodes on an **inter** frame. The edit is in-loop,
so it changes the reference and the two decodes diverge through prediction, not
through the edit. Reported 2,229 wrong samples on frame 1 while frame 0 was
exact. The exactness gate is intra-only for this reason, and the limitation is
stated in `HANDOFF_BIT_EXACTNESS.md`.

**Version 3, same family.** The un-blend tool defaulted to a `bits_per_slice`
that did not match the encoder's, so it selected cap 8 where the encoder had used
cap 4, and reported 5.6–6.3% wrong. The tool now takes the value.

## F.8 A test that could not fail

`test_cap` v1 compared bitstreams only, on content that never selected
prediction. It passed on the broken tree. It compares reconstructions now.

## F.9 A build script that did not check its compiles

`build.sh` launched compiles in the background and printed BUILD-OK regardless.
It printed BUILD-OK over a failed compile, left a stale binary in place, and
produced one meaningless byte-identity result. Now every `wait` is checked.

## F.10 Two 4K half-rate runs, invalid two different ways

`--slice-h 32` was silently refused by the delivered build and the arm reused the
previous decode; and the DNG masters were 24 frames against a 4-frame encode.
The tell was VMAF 16 at 33 dB PSNR. The harness now aborts on a failed encode and
asserts frame counts.

## F.11 Rendering faults of my own making

10-bit limited-range material rendered to 8-bit full-range PNG collapsed ~2,200
levels to ~250 in flat areas, adding contouring on top of a real artefact — Dan
spotted it before I did. Re-rendered at 16-bit and dithered.

## F.12 Copying a whole file into a tree I did not write

Mirroring a change by copying `src/codec.c` wholesale silently deleted **307
lines** of someone else's newer work (`omc_fillcorr`, `omc_recoff`,
`omc_fc_tot`). It surfaced only when an unrelated tool failed to link. Repaired
from a pre-change snapshot by re-applying each change as a targeted edit, and
verified: 8 lines removed, all deliberate; every symbol of theirs present at the
same count.

**Rule: never mirror a change by copying a whole file into a tree you did not
write. Apply the edit.**

## F.13 Skipping a file because it looked like a duplicate

`new_ideas/08112026/SESSION_LEDGER_FULL.md` was skipped as a duplicate of the
project-root ledger. Its §1.1 is the explanation for the scaler edits — the exact
thing I later spent time reconstructing.

**Rule: read every file in the folder you were asked to review.**

## F.14 This ledger itself

Dan asked for a self-contained ledger kept **for the entire session**. I appended
to it instead of keeping it complete, which is why assembling it at the end was a
large job rather than no job at all. Recorded because the failure mode is the
same one as F.13: deferring something whose whole value is that it is current.

---

# PART O — Open items

Every entry obeys one rule: **an open decision may only exist if something in the
build speaks up about it.** Prose in a document is what failed before.

| item | status | the hook that speaks |
|---|---|---|
| `XSL-RATE-OFF` — switch the boundary edit off above ~1.5 bpp | needs an eye check that joins are invisible unrepaired at 1.5–2.0 bpp, and that the over-smoothing above it is not visible | `ridge.sh` reprints the table on demand; numbers in Part M.4 |
| `A4-XSL` — the generation problem | open; the whole of `HANDOFF_BIT_EXACTNESS.md` | `resweep.sh`, and gate `G-XSL2` fails if the reversible edit stops being reversible |
| `CAP-STEP` — whether the cap should have a third step at high rate | weak hook, acknowledged | none that runs; flagged as weak in `OPEN_DECISIONS.md` |
| level-7 detector | not built | `HANDOFF_BIT_EXACTNESS.md` §5 item 4 |
| pre-edit reconstruction hook, for inter-frame exactness | not built | gate `G-XSL2` is intra-only and says so in its own comment |
| clean-content 4K master | missing from the corpus | `HANDOFF_BIT_EXACTNESS.md` §2 fact 4 |

## Awaiting Dan's eye

| kit | question |
|---|---|
| `AB_seam_boil_2026-08-12.zip` | does XSL level 6 crawl along the joins? |
| `AB_4K_32lines_2026-08-12.zip` | 16 versus 32 lines at 4K |
| (not yet built) | joins at 1.5–2.0 bpp with no repair at all — the `XSL-RATE-OFF` question |

---

# PART V — Verification of this document

Everything below was run against a **fresh extraction of the archive**, not
against my working copy. (My earlier working copy of v4.9 turned out to contain
build artefacts and one file I had created inside it — harmless for source and
documentation, all of which were byte-identical, but it is why this section
exists.)

## V.1 The archive

| file | sha256 | size |
|---|---|---|
| omc_v4.9_full_20260811.zip (baseline) | `15cccfdff9057c7cddb9de53531fb814aa8dba26986e165f78c34b2c8f4f88a5` | 9854895 |
| omc_v4.14_20260812.zip (delivered) | `3deff3ef36b640785c73b004ba836a1789685fb0ca279790bf99163516c926ec` | 7677824 |

The baseline archive was verified byte-identical to both copies Dan re-uploaded
during the session.

## V.2 The patches reproduce the delivered tree

```
$ cp -r <clean extraction> rebuild && cd rebuild
$ git apply --whitespace=nowarn R1_inherited.patch   -> R1 applied
$ git apply --whitespace=nowarn R2_session.patch     -> R2 applied
$ compare every .c .h .md .inc + Makefile against the delivered tree
    none -- byte-identical
```

## V.3 The reconstruction builds and passes every gate

```
BUILD-OK
  test_unit  all ok
  test_uc    all ok
  test_tf    all ok
  test_cc    all ok
  test_cap   all ok
  test_xsl   all ok
```

## V.4 File-by-file status against v4.9

Code (source, headers, tools, tests, Makefile):

| file | status |
|---|---|
| `src/alloc.c` | identical |
| `src/bitio.c` | identical |
| `src/cc_tab.c.inc` | identical |
| `src/codec.c` | **modified** (+530 lines) |
| `src/colour.c` | identical |
| `src/config.c` | **modified** (+7 lines) |
| `src/dwt.c` | identical |
| `src/internal.h` | **modified** (+15 lines) |
| `src/tables.c` | identical |
| `src/tables_v4.c.inc` | identical |
| `src/tans.c` | identical |
| `src/tfilt.c` | identical |
| `src/uc_poly_tab.c.inc` | identical |
| `src/upconv.c` | **modified** (+122 lines) |
| `include/omc1.h` | **modified** (+37 lines) |
| `include/omc_cc.h` | identical |
| `include/omc_tf.h` | identical |
| `include/omc_uc.h` | **modified** (+38 lines) |
| `include/tables.h` | identical |
| `tools/omc_dec.c` | **modified** (+4 lines) |
| `tools/omc_enc.c` | **modified** (+41 lines) |
| `tools/omc_tf_tool.c` | identical |
| `tools/omc_uc_tool.c` | **modified** (+3 lines) |
| `tests/test_cc.c` | **modified** (+0 lines) |
| `tests/test_tf.c` | identical |
| `tests/test_threads.c` | identical |
| `tests/test_uc.c` | **modified** (+125 lines) |
| `tests/test_unit.c` | **modified** (+11 lines) |
| `Makefile` | **modified** (+11 lines) |
| `tests/test_cap.c` | **new** |
| `tests/test_xsl.c` | **new** |
| `tools/omc_unblend_tool.c` | **new** |

Documentation:

| file | status |
|---|---|
| `PROJECT_CONSTRAINTS.md` | identical |
| `README.md` | **modified** (+21 lines) |
| `docs/BITSTREAM.md` | **modified** (+82 lines) |
| `docs/CONTROL_PLANE.md` | **modified** (+2 lines) |
| `docs/DESIGN.md` | identical |
| `docs/ENHANCEMENTS_LEDGER.md` | identical |
| `docs/EXECUTIVE_SUMMARY.md` | identical |
| `docs/FEASIBILITY.md` | identical |
| `docs/FEATURE_MATRIX.md` | identical |
| `docs/HANDOFF_2026-08-04.md` | identical |
| `docs/HARDWARE.md` | **modified** (+29 lines) |
| `docs/HW_TIMING_METHOD.md` | identical |
| `docs/INTERLACE_CONVENTION.md` | identical |
| `docs/LATENCY.md` | **modified** (+64 lines) |
| `docs/LETTER_TEAM_A.md` | identical |
| `docs/MEDIA_SERVER_MARKET.md` | identical |
| `docs/PROFILES.md` | identical |
| `docs/QOE_MONITORING.md` | identical |
| `docs/REPORT.md` | identical |
| `docs/REPORT_V44_SESSION.md` | identical |
| `docs/ROADMAP.md` | identical |
| `docs/STATIC_ANALYSIS.md` | identical |
| `docs/STEP3_ARCHITECTURE_DECISION.md` | identical |
| `docs/TRANSPORT_NOTE.md` | identical |
| `docs/experiments_alloc_eye.c.txt` | identical |
| `docs/omc_config.schema.json` | identical |
| `docs/XSL.md` | **new** |
| `OPEN_DECISIONS.md` | **new** |
| `CHANGELOG_v4.14.md` | **new** |

Every documentation file not listed as modified or new is **byte-identical to
v4.9** — nothing was silently rewritten.

---

---

# PART W — Documentation review on bit exactness, and what it overturned

Added after Dan asked two questions: does the ledger contain all updated code,
and had I reviewed the existing documentation on bit exactness. The second
question overturned a headline finding of this session and exposed a
long-standing fault in the project.

## W.1 What the documentation claims

| document | claim |
|---|---|
| `docs/DESIGN.md` §5 | "generations 2–5 byte-identical to generation 1 on all planes (`tests/test_acceptance.py::test_generations_byte_stable`)" |
| `docs/DESIGN.md` §7 | "all slices lock on generation 2+, outputs byte-identical through generation 5" |
| `docs/EXECUTIVE_SUMMARY.md` | "copies of copies are bit-for-bit identical from the second generation on" |
| `docs/FEASIBILITY.md` | "generations 2–5 byte-identical to generation 1" |
| `docs/FEATURE_MATRIX.md` | the careful version: "byte-exact from gen 2 **(statics)**; convergent on pans/heavy grain" |
| `docs/CONTROL_PLANE.md` | already documents the XSL/rate interaction I had presented as new in Part XXV Result 5 — see W.5 |

## W.2 The project's own gate fails, and had been inert

```
$ OMC_SCRATCH=<real masters> python3 -m pytest tests/test_acceptance.py -q
    AssertionError: generation 2 != generation 1
    At index 198 diff: b'\xcb' != b'\xca'
    1 failed, 8 passed in 41.73s
```

Eight of nine acceptance gates pass, including `rt = 0`. Only the generation gate
fails.

`MASTERS_DIR` derives from `OMC_SCRATCH`, whose default is a scratch path from a
different machine. On any other machine the gate reports **`1 skipped`**. It has
been reading as green by not running.

## W.3 It is not a regression from this session

Same gate, same failure, on all three trees:

| tree | result |
|---|---|
| pristine `omc_v4.9_full_20260811.zip` | **1 failed** |
| the tree this session inherited | **1 failed** |
| delivered v4.14 | **1 failed** |

## W.4 It fails on static content, with the seam edit off

Built a genuinely static clip (alpine frame 0 repeated five times):

| arm | out2 == out1 | samples differing at gen 2 | worst | lock |
|---|---|---|---|---|
| defaults (XSL level 3) | no | 19.44% | 20 codes | 27/360 |
| XSL off | no | **19.44%** | 20 codes | 27/360 |

Identical either way. **So underneath the seam edit's contribution there is a
baseline failure that has nothing to do with it, and it is the larger problem.**
`rt = 0` holds, so encoder and decoder agree; the fault is in re-encoding.

Generations do converge — alpine, 2.0 bpp: 26.76% of samples differ at generation
2, 4.62% at generation 3, a sixfold reduction. `FEATURE_MATRIX.md`'s "convergent,
non-accumulating" is supported. The byte-exact claims in the other three
documents are not.

## W.5 Two things I presented as new that the documentation already had

**The XSL / rate interaction.** `CONTROL_PLANE.md` already states: *"the seam is
worth repairing at low rate and gone by 2.0 bpp, while XSL costs 2–4.7 dB across
six generations exactly where the seam has gone (it puts the reconstruction off
the quantiser lattice and the generation lock stops firing)."* Part XXV Result 5
presented that as a discovery. It was a **confirmation**, at finer rate
granularity and with the scale-free ratio added — worth having, but not new.

**`--xsl auto` already existed for that reason** and is documented as removing
every generation loss above 1.2 dB. What this session actually added there is the
demonstration that it is **defeated by a scene cut**, which the documentation did
not know.

## W.6 My own measurement error

Part M.6 / the first handoff reported "42 configurations, 42 × not byte-identical"
from a column comparing **generation 1's bitstream with generation 2's**. Those
encode different inputs — the master and a decode — so they were never expected to
match. The comparison was meaningless.

The correct tests are the project's own: does generation 2's decoded **output**
equal generation 1's, and does generation 3's **bitstream** equal generation 2's.
Re-run that way, nothing reached exactness either — the conclusion survives, but
it now rests on the right measurement. The `id` column has been removed from the
table in the handoff; the lock counts in it are unaffected and stand.

## W.7 Answer to "does the ledger contain all updated code"

Yes, and it is verified rather than asserted: Part R carries both patches in full,
Part V records that applying them to a clean extraction of the v4.9 archive
reproduces the delivered tree **byte-identically**, builds, and passes all six
C gates. The three new files (`tests/test_cap.c`, `tests/test_xsl.c`,
`tools/omc_unblend_tool.c`) appear in the patches in full, as additions.

Reproduce the check with `research/scripts/` and the two patch files, both in the
delivered zip.

---

# PART R — The complete patches

Two patches, split on authorship. Applied in order to a clean extraction of
`omc_v4.9_full_20260811.zip`, they reproduce the delivered tree **byte for byte**
— verified, transcript in Part V.

```bash
unzip omc_v4.9_full_20260811.zip
cd .work/final/omc_v4.9
git init -q .                                  # or use patch -p1
git apply --whitespace=nowarn R1_inherited.patch
git apply --whitespace=nowarn R2_session.patch
```

## R.1 — v4.9 → the tree I inherited (NOT MY WORK)

Roughly 14 hours of work by others between the archive being cut and this session
starting: the grain-fill correction (`omc_fillcorr`, `omc_recoff`, `omc_fc_tot`),
fill-probe hints, scaler edits, and the `HARDWARE.md` / `LATENCY.md` notes that
go with them. Reproduced in full so the baseline is unambiguous, **not claimed**.

**One correction to the split.** `tests/test_cap.c` appears in this patch but is
**mine**. The snapshot I use as the boundary was taken a few hours into the
session, after I had written that file. v4.9 itself has no `tests/test_cap.c` —
confirmed against the zip listing. Everything else in R.1 is the inherited work.


```diff
diff -ruN '--exclude=*.o' '--exclude=*.yuv' '--exclude=__pycache__' '--exclude=.pytest_cache' '--exclude=work' '--exclude=_xc' '--exclude=repro' '--exclude=harness' '--exclude=delivery' '--exclude=*.log' '--exclude=omc_enc' '--exclude=omc_dec' '--exclude=omc_uc_tool' '--exclude=omc_tf_tool' '--exclude=omc_unblend_tool' '--exclude=test_cap' '--exclude=test_cap_old' '--exclude=test_cap_live' '--exclude=test_cc' '--exclude=test_tf' '--exclude=test_uc' '--exclude=test_unit' '--exclude=test_xsl' ./docs/HARDWARE.md [machine-path-redacted]/.work/ni0811/v49live/docs/HARDWARE.md
--- a/docs/HARDWARE.md	2026-08-12 22:41:44.978342490 -0400
+++ b/docs/HARDWARE.md	2026-08-11 23:33:50.667442845 -0400
@@ -323,3 +323,32 @@
   env knobs (OMC_GR_SOFT=0 OMC_GR_PTHR=2 OMC_GR_CARPET=0 OMC_GR_LLTHR=24);
   minor <= 6 streams decode byte-identically (verified vs a pristine v4.6
   build), so deployed decoder RTL is untouched unless it opts into minor 7.
+
+## 10. OMC-UC upconverter (output stage) — FPGA cost (C3)
+The upconverter obeys the same construction rules as the codec core.
+
+- **No multipliers in the per-sample path.** The 12-tap kernel is evaluated as
+  shifts and adds; `test_uc` verifies the multiplier-free evaluation equals the
+  tabulated coefficients for every tap over the full value range, and equals
+  the tabulated multiply for every coefficient of every published polyphase
+  table (rational ratios included).
+- **No dividers.** The mirror addressing needs no modulo at any supported plane
+  dimension (smallest supported is 640; proven unreachable for >= 20), so the
+  per-sample path is divider-free in the reference implementation too.
+- **ROM, not state.** The polyphase bank is a fixed table; phase 0 is the unit
+  impulse, every phase has unity DC, the 1:2 phase equals the base kernel
+  exactly, and phase p mirrors phase den-p — so a hardware bank stores half the
+  table and addresses the rest by symmetry.
+- **Line memory.** Vertical reach is 8 source rows for 2x (12 for the 4x
+  cascade), i.e. one slice period at slice_h 8 — the same order as the codec's
+  own slice buffering, and it reuses the existing line-store discipline rather
+  than adding a frame buffer.
+- **No allocation.** `omc_uc_scale_plane_ws()` takes caller-owned workspace,
+  agrees byte-for-byte with the allocating wrapper on every ratio class, and
+  REFUSES an undersized workspace rather than overrunning it (test_uc G20) —
+  the no-malloc shape a hardware or real-time host requires.
+- **Exact integer reversibility.** `down(up(x)) == x` byte-exact at 8, 10 and
+  12-bit, and the 4x cascade inherits the contract level by level, so a
+  scale-out/scale-in round trip through the stage is lossless by construction.
+
+Latency and refusal behaviour: see LATENCY.md, "OMC-UC output stage".
diff -ruN '--exclude=*.o' '--exclude=*.yuv' '--exclude=__pycache__' '--exclude=.pytest_cache' '--exclude=work' '--exclude=_xc' '--exclude=repro' '--exclude=harness' '--exclude=delivery' '--exclude=*.log' '--exclude=omc_enc' '--exclude=omc_dec' '--exclude=omc_uc_tool' '--exclude=omc_tf_tool' '--exclude=omc_unblend_tool' '--exclude=test_cap' '--exclude=test_cap_old' '--exclude=test_cap_live' '--exclude=test_cc' '--exclude=test_tf' '--exclude=test_uc' '--exclude=test_unit' '--exclude=test_xsl' ./docs/LATENCY.md [machine-path-redacted]/.work/ni0811/v49live/docs/LATENCY.md
--- a/docs/LATENCY.md	2026-08-12 22:41:44.978251428 -0400
+++ b/docs/LATENCY.md	2026-08-11 23:33:50.667442845 -0400
@@ -70,3 +70,23 @@
 existing slice-period buffering; a strictly row-streaming sink must account
 one extra slice period for the last row of each slice. No other term
 changes; the per-slice cost is O(width) adds/shifts.
+
+## OMC-UC output stage (upconversion), when enabled
+The upconverter is an OUTPUT-STAGE resampler: it runs after slice
+reconstruction and never feeds the coding loop, so none of the terms in the
+model above change. Its own cost is bounded and declared:
+
+| ratio / mode | added latency | why |
+|---|---|---|
+| 2x vertical (or 2x both axes) | **+1 slice period** | the 12-tap kernel's vertical reach is 8 source rows, i.e. within one 8-row slice floor either side; verified against the analytic bound `omc_uc_analytic_reach()` and measured in test_uc |
+| 4x (cascade of two 2x levels) | +2 slice periods at slice_h 8, **+1** at slice_h 16 | the cascade's measured reach stays inside the analytic bound |
+| horizontal-only scale (e.g. chroma resample along the line) | **0** | output row r depends on source row r alone — zero vertical reach (test_uc G19) |
+| horizontal mirror | **0** | an exact in-line reversal; vertical flip and 90-degree rotation are whole-frame operations and are NOT part of the sub-1 ms path |
+
+`omc_validate_config()` REFUSES any (format, ratio) combination whose total
+would exceed the 1 ms budget rather than silently exceeding it — the refusal
+is part of the contract, not a runtime surprise. Banded operation is exact:
+1/2/4/8/16/32-row band output is byte-identical to whole-plane output, so a
+streaming sink may pull any band size without changing the result. The stage
+is stateless and deterministic (no history, no RNG), which is what keeps
+generation chains and A4 intact when the scaler is in the path.
diff -ruN '--exclude=*.o' '--exclude=*.yuv' '--exclude=__pycache__' '--exclude=.pytest_cache' '--exclude=work' '--exclude=_xc' '--exclude=repro' '--exclude=harness' '--exclude=delivery' '--exclude=*.log' '--exclude=omc_enc' '--exclude=omc_dec' '--exclude=omc_uc_tool' '--exclude=omc_tf_tool' '--exclude=omc_unblend_tool' '--exclude=test_cap' '--exclude=test_cap_old' '--exclude=test_cap_live' '--exclude=test_cc' '--exclude=test_tf' '--exclude=test_uc' '--exclude=test_unit' '--exclude=test_xsl' ./include/omc1.h [machine-path-redacted]/.work/ni0811/v49live/include/omc1.h
--- a/include/omc1.h	2026-08-12 22:41:44.976345721 -0400
+++ b/include/omc1.h	2026-08-11 23:33:50.663207850 -0400
@@ -26,6 +26,7 @@
 #define OMC_RELEASE_MINOR 9
 #define OMC_VERSION_MINOR 7 /* 3 block MC; 4 entropy v2; 5 corr tile; 6 amplitude-matched fill (0.5x code) */
 #define OMC_MINOR_UC 8
+#define OMC_XSL_LIM_MINOR9 8  /* normative boundary-blend cap, codes @10-bit (minor 9) */
 #define OMC_MINOR_XSL 9     /* 9: cross-slice boundary reconstruction (XSL level 3 +
                                refresh barriers) is NORMATIVE-ON for the whole stream.
                                No per-slice bits; the minor IS the signal. */      /* 8: stream byte 26 carries uc_ratio (OMC-UC upconversion).
diff -ruN '--exclude=*.o' '--exclude=*.yuv' '--exclude=__pycache__' '--exclude=.pytest_cache' '--exclude=work' '--exclude=_xc' '--exclude=repro' '--exclude=harness' '--exclude=delivery' '--exclude=*.log' '--exclude=omc_enc' '--exclude=omc_dec' '--exclude=omc_uc_tool' '--exclude=omc_tf_tool' '--exclude=omc_unblend_tool' '--exclude=test_cap' '--exclude=test_cap_old' '--exclude=test_cap_live' '--exclude=test_cc' '--exclude=test_tf' '--exclude=test_uc' '--exclude=test_unit' '--exclude=test_xsl' ./include/omc_uc.h [machine-path-redacted]/.work/ni0811/v49live/include/omc_uc.h
--- a/include/omc_uc.h	2026-08-12 22:41:44.976261458 -0400
+++ b/include/omc_uc.h	2026-08-11 23:33:50.663207850 -0400
@@ -167,6 +167,15 @@
  * for.  Returns 1 if supported, 0 if below the floor. */
 int omc_uc_format_supported(int w, int h);
 
+/* 1 when the rational scale from (sw,sh) to (dw,dh) is CENTRE-aligned on both
+ * axes — i.e. the output grid sits on the centres of the source intervals it
+ * represents, so scaled content stays registered with unscaled content.  0
+ * when an axis falls back to the historical corner-aligned mapping, which
+ * displaces the picture by (num-den)/(2*den) output pixels on that axis.
+ * Mixed-parity ratios (e.g. 2:1, 3:2, 4:3) need a 2*den phase bank to centre
+ * exactly and are the cases that return 0. */
+int omc_uc_scale_aligned(int sw, int sh, int dw, int dh);
+
 /* Latency of a rational conversion.  Always writes the total and the extra
  * slice periods when the conversion is possible at all.  Returns:
  *    0  the conversion holds sub-1 ms -- A2 met
diff -ruN '--exclude=*.o' '--exclude=*.yuv' '--exclude=__pycache__' '--exclude=.pytest_cache' '--exclude=work' '--exclude=_xc' '--exclude=repro' '--exclude=harness' '--exclude=delivery' '--exclude=*.log' '--exclude=omc_enc' '--exclude=omc_dec' '--exclude=omc_uc_tool' '--exclude=omc_tf_tool' '--exclude=omc_unblend_tool' '--exclude=test_cap' '--exclude=test_cap_old' '--exclude=test_cap_live' '--exclude=test_cc' '--exclude=test_tf' '--exclude=test_uc' '--exclude=test_unit' '--exclude=test_xsl' ./src/codec.c [machine-path-redacted]/.work/ni0811/v49live/src/codec.c
--- a/src/codec.c	2026-08-12 22:41:44.975345096 -0400
+++ b/src/codec.c	2026-08-11 23:33:50.656540896 -0400
@@ -8,6 +8,9 @@
 #include "internal.h"
 #include "omc_tf.h"
 
+extern int omc_xsl;       /* defined below; read by the header parser */
+extern int omc_xsl_lim;   /* ditto: minor 9 pins the boundary-blend cap */
+
 /* ------------------------------------------------------------------ common */
 
 typedef struct {
@@ -339,7 +342,11 @@
      * with XSL level 3 regardless of environment; env OMC_XSL affects only
      * what an ENCODER writes.  (Experimental builds may still force the
      * decoder with OMC_XSL_FORCE for instrumentation.) */
-    if (src[5] >= OMC_MINOR_XSL) omc_xsl = 3;
+    if (src[5] >= OMC_MINOR_XSL) {
+        omc_xsl = 3;
+        /* cap is rate-derived; cfg is filled in below, so the
+         * decoder pins it in omc_dec_create() instead. */
+    }
     else if (!getenv("OMC_XSL_FORCE")) omc_xsl = 0;
     const uint8_t *o = src + 6;
     memcpy(&cfg->width, o, 2); o += 2;
@@ -405,10 +412,17 @@
     }
 }
 
+extern int omc_chromabias;   /* chroma detail bias (test lever, defined below) */
+extern int omc_bandtilt;     /* fine-band precision tilt (defined below) */
 /* shift for coefficient index i of band (p,b) under plan sp */
 static inline int coeff_shift(const shift_plan_t *sp, int p, int b, int i)
 {
     int s = sp->shift[p][b];
+    if (omc_chromabias && p > 0 && b > 0) s += omc_chromabias;
+    if (omc_bandtilt) {
+        if (b >= 7) { s -= omc_bandtilt; if (s < 0) s = 0; }
+        else if (b >= 1 && b <= 3) s += omc_bandtilt;
+    }
     if (p == sp->partial_p && b == sp->partial_b && (i >> 8) < sp->partial_chunks)
         s--;
     return s;
@@ -425,6 +439,28 @@
 int omc_gr_softcap = 3; /* soft-threshold only |q| <= cap (env OMC_GR_SOFTCAP) */
 int omc_gr_llthr = 24; /* flat-class LL-gradient threshold (env OMC_GR_LLTHR) */
 int omc_gr_soft = 0;   /* flat-class soft-threshold: coded |q| shrinks by n (env OMC_GR_SOFT) */
+extern long long omc_fc_fire, omc_fc_tot;
+int omc_fillbands = 0;   /* 0 = all; else bitmask of bands allowed to fill
+    (test lever: the finest fill bands carry the least source correlation, so
+    they are the most likely to cost VMAF-NEG for the least perceptual gain) */
+int omc_chromabias = 0;  /* extra quantiser shift applied to CHROMA detail bands
+    (test lever: VMAF and VMAF-NEG are luma-only, so bits moved off chroma are
+    free from their point of view) */
+int omc_bandtilt = 0;    /* move quantiser precision toward the FINEST bands:
+    shift[7,8,9] -= n (finer) and shift[1,2,3] += n (coarser).  Exact CBR does the
+    rebalancing.  Rationale (measured): the VMAF-NEG gap to XS@2R is almost entirely
+    one feature — VIF scale 0 (OMC 0.691 vs XS 0.773, -0.0815) — while VIF scales
+    1-3 sit at 0.97-0.99 and are SATURATED (gaps -0.011/-0.006/-0.004).  Bits spent
+    on coarse scales buy almost nothing; the finest scale has all the headroom. */
+int omc_recoff = 0;      /* centroid dequantisation, n/16 step (env OMC_RECOFF) */
+int omc_fillcorr = 0;  /* E-1: causal sign correlation for grain fill (env
+    OMC_FILLCORR, normative when on).  The fill's SIGN follows the local coded
+    structure — left and up coded coefficients, when both non-zero and in
+    agreement — instead of the decorrelated tile.  Measured motivation: at the
+    finest luma band OMC retains 3.5x JPEG XS's energy but only a third of its
+    correlation with the source (0.059 vs 0.161), i.e. the texture is plausible
+    but not the source's.  Reads coded values only, so no filled cell can feed
+    another; costs one sign register plus one 2-bit sign line per band. */
 int omc_plan_hyst = 0; /* v4.7 plan hysteresis (env OMC_PLAN_HYST) */
 int omc_alloc = 0;     /* perceptual slice-budget weighting (env OMC_ALLOC): cap low-energy slices at 3/4 share, bank surplus forward */
 int omc_gr_dzoff = 0;  /* skip deadzone in flat-carpet cells (env OMC_GR_DZOFF) */
@@ -594,6 +630,11 @@
     omc_gr_fillveto = getenv("OMC_GR_FILLVETO") ? atoi(getenv("OMC_GR_FILLVETO")) : 0;
     omc_fill_static = getenv("OMC_FILL_STATIC") ? atoi(getenv("OMC_FILL_STATIC")) : 0;
     omc_plan_hyst = getenv("OMC_PLAN_HYST") ? atoi(getenv("OMC_PLAN_HYST")) : 0;
+    omc_bandtilt = getenv("OMC_BANDTILT") ? atoi(getenv("OMC_BANDTILT")) : 0;
+    omc_recoff = getenv("OMC_RECOFF") ? atoi(getenv("OMC_RECOFF")) : 0;
+    omc_fillcorr = getenv("OMC_FILLCORR") ? atoi(getenv("OMC_FILLCORR")) : 0;
+    omc_fillbands = getenv("OMC_FILLBANDS") ? atoi(getenv("OMC_FILLBANDS")) : 0;
+    omc_chromabias = getenv("OMC_CHROMABIAS") ? atoi(getenv("OMC_CHROMABIAS")) : 0;
     omc_alloc = getenv("OMC_ALLOC") ? atoi(getenv("OMC_ALLOC")) : 1; /* v4.7 rev8 default ON (REPORT 18.9); OMC_ALLOC=0 reproduces rev3 byte-exactly */
     omc_gr_dzoff = getenv("OMC_GR_DZOFF") ? atoi(getenv("OMC_GR_DZOFF")) : 0;
     omc_gr_soft_coarse = getenv("OMC_GR_SOFT_COARSE") ? atoi(getenv("OMC_GR_SOFT_COARSE")) : 0;
@@ -606,6 +647,15 @@
     omc_ref_unclipped = getenv("OMC_REF_UNCLIPPED") ? atoi(getenv("OMC_REF_UNCLIPPED")) : 0;
     omc_dcfb = getenv("OMC_DCFB") ? atoi(getenv("OMC_DCFB")) : 0;
     if (getenv("OMC_XSL")) omc_xsl = atoi(getenv("OMC_XSL"));  /* preserve stream-derived value otherwise (C1) */
+    /* NORMATIVE (minor 9): the boundary blend cap is 8 codes at 10-bit.
+     * Both sides derive it from the stream minor, never from the
+     * environment.  Chosen by eye (three-arm blind comparison, caps
+     * 4/8/16) with the measurements as support: cap 8 halves the
+     * seam excess of cap 4 (all-seam +1.23 -> +0.67 codes, JPEG XS
+     * floor = 0.00) while beach@0.5bpp keeps VMAF parity with XS@1.0
+     * (94.89 vs 94.94); cap 16 reaches +0.40 but drops to 94.34 and
+     * risks trading a hard seam line for a soft two-row smear.
+     * OMC_XSL_LIM remains for experiments only. */
     omc_xsl_lim = getenv("OMC_XSL_LIM") ? atoi(getenv("OMC_XSL_LIM")) : 4;
     omc_spc = getenv("OMC_SPC") ? atoi(getenv("OMC_SPC")) : 0;
     omc_xsl_nodisp = getenv("OMC_XSL_NODISP") ? atoi(getenv("OMC_XSL_NODISP")) : 0;
@@ -614,9 +664,29 @@
     omc_rboost = getenv("OMC_RBOOST") ? atoi(getenv("OMC_RBOOST")) : 0;
 }
 
+
+/* NORMATIVE (minor 9): boundary-blend cap, in codes at 10-bit scale.
+ * The blend exists to bridge QUANTIZATION error at a slice seam, so its cap
+ * must follow the coarseness of the quantizer, and both sides derive it from
+ * the stream header alone: bpp = bits_per_slice / (width * slice_h).
+ *   bpp <  0.75  -> 8   (coarse: seams carry real steps)
+ *   bpp >= 0.75  -> 4   (fine: seams are already at the JPEG XS floor)
+ * Measured on beach (all-seam excess, XS floor 0.00; VMAF vs source):
+ *   0.5bpp  cap4 +1.23 / 95.21   cap8 +0.67 / 94.89  -> cap 8 (eye-chosen)
+ *   1.0bpp  cap4 +0.00 / 97.67   cap8 -0.35 / 97.23  -> cap 4 (8 over-smooths
+ *   2.0bpp  cap4 -0.38 / 98.59   cap8 -0.68 / 98.12     and costs ~0.45 VMAF)
+ * OMC_XSL_LIM overrides for experiments only. */
+static int xsl_lim_for(const omc_config_t *cfg)
+{
+    if (getenv("OMC_XSL_LIM")) return atoi(getenv("OMC_XSL_LIM"));
+    int64_t px = (int64_t)cfg->width * (cfg->slice_h ? cfg->slice_h : 16);
+    return (4 * (int64_t)cfg->bits_per_slice < 3 * px) ? OMC_XSL_LIM_MINOR9 : 4;
+}
+
 omc_enc_t *omc_enc_create(const omc_config_t *cfg)
 {
     omc_global_init(); /* tables allocated here, before the baseline */
+    if (omc_xsl) omc_xsl_lim = xsl_lim_for(cfg);
     size_t heap_base = 0;
     if (getenv("OMC_ENC_FOOTPRINT")) {
         struct mallinfo2 mi0 = mallinfo2();
@@ -1090,8 +1160,9 @@
  * reconstruction and decoder (in-loop; the temporal reference includes it). */
 
 /* local LL activity at the LL cell co-located with (row, col) of band b */
-static inline int fill_gate(const int32_t *ll, int llstride, int llw, int llh,
-                            int b, int row, int col, int32_t lllim)
+static inline int fill_gate_g(const int32_t *ll, int llstride, int llw, int llh,
+                            int b, int row, int col, int32_t lllim,
+                            int *sgh, int *sgv)
 {
     int rL = (b >= 7) ? (row >> 1) : row;
     int xL = col >> ((b >= 7) ? 4 : 3);
@@ -1117,6 +1188,8 @@
     if (c0 > lllim || c0 < -lllim) return 0; /* clip headroom guard */
     int32_t gh = ll[(size_t)rL * llstride + xhi] - ll[(size_t)rL * llstride + xlo];
     int32_t gv = ll[(size_t)rhi * llstride + xL] - ll[(size_t)rlo * llstride + xL];
+    if (sgh) *sgh = (gh > 0) - (gh < 0);
+    if (sgv) *sgv = (gv > 0) - (gv < 0);
     if (gh < 0) gh = -gh;
     if (gv < 0) gv = -gv;
     if (gh + gv < OMC_FILL_GATE) return 0;
@@ -1128,16 +1201,72 @@
     int act = gh + gv;
     return act < 2 * OMC_FILL_GATE ? 1 : act < 4 * OMC_FILL_GATE ? 2 : 3;
 }
+static inline int fill_gate(const int32_t *ll, int llstride, int llw, int llh,
+                            int b, int row, int col, int32_t lllim)
+{
+    return fill_gate_g(ll, llstride, llw, llh, b, row, col, lllim, 0, 0);
+}
 
 /* fill value for a zero coefficient, or 0 if gated off / not eligible */
-static inline int32_t fill_value(const int32_t *ll, int llstride, int llw, int llh,
+/* Parent-band hint descriptor: where the parent's coefficients live inside the
+ * plane reconstruction buffer, and the step that separates coded from filled. */
+typedef struct {
+    const int32_t *base;   /* &sbuf[p][r0*stride + c0] of the parent band, or NULL */
+    int stride, w, h;      /* parent geometry */
+    int half;              /* half a parent step: |v| >= half  =>  coded */
+    int rsh, csh;          /* child->parent index shifts */
+} fp_t;
+
+static inline int fp_hint(const fp_t *fp, int row, int col)
+{
+    int pr, pc; int32_t v;
+    if (!fp->base) return 0;
+    pr = row >> fp->rsh; pc = col >> fp->csh;
+    if (pr >= fp->h) pr = fp->h - 1;
+    if (pc >= fp->w) pc = fp->w - 1;
+    v = fp->base[(size_t)pr * fp->stride + pc];
+    if (v >= fp->half) return 1;
+    if (v <= -fp->half) return -1;
+    return 0;               /* zero, or a filled cell (always below half-step) */
+}
+
+
+static inline int32_t fill_value_p(const int32_t *ll, int llstride, int llw, int llh,
                                  int b, int row, int col, int s, int fox, int foy,
                                  int sfox, int sfoy,
-                                 int32_t lllim, int gain, int corr, int v6)
+                                 int32_t lllim, int gain, int corr, int v6, int hint,
+                                 const fp_t *fp)
 {
+    if (omc_fillbands && !((omc_fillbands >> b) & 1)) return 0;
     if (s < OMC_FILL_MIN_SHIFT) return 0;
-    int act = fill_gate(ll, llstride, llw, llh, b, row, col, lllim);
+    int sgh = 0, sgv = 0;
+    int act = fill_gate_g(ll, llstride, llw, llh, b, row, col, lllim,
+                          omc_fillcorr ? &sgh : 0, omc_fillcorr ? &sgv : 0);
     if (!act) return 0;
+    /* E-1 (structural): a detail coefficient at an edge carries the sign of
+     * the local derivative in ITS orientation, and the fill gate has already
+     * read the LL neighbourhood to compute exactly those derivatives.  Bands
+     * 4/7 are LH (vertical detail -> vertical gradient), 5/8 are HL, 6/9 are
+     * HH (diagonal -> product of the two).  Costs nothing: the loads are
+     * already done, the sign bits are already computed, and the LL band is
+     * decoded before every detail band, so it is causal and parallel by
+     * construction — no filled cell can influence another. */
+    /* E-1 stage 2: the PARENT band coefficient, one octave coarser — the right
+     * scale for a fine-band hint, and at low rate far more likely to hold coded
+     * energy than a same-band neighbour.  A filled parent is excluded by
+     * magnitude alone: fill is always below half a step, so |parent| >= half
+     * means coded.  Coded-only, parent decoded before child: no fill-to-fill
+     * dependency is expressible.
+     *   Amplitude gating on the same signal was measured and NOT adopted:
+     *   0.5x -> VMAF 96.400 / NEG 94.313 / PSNR-Y 44.49, 0.75x -> 96.396 /
+     *   94.311 / 44.40, against 96.447 / 94.332 / 44.33 for the sign hint
+     *   alone.  It trades texture both VMAF models want for fidelity, and NEG
+     *   prefers the sign hint. */
+    if (omc_fillcorr && !hint && fp) hint = fp_hint(fp, row, col);
+    if (omc_fillcorr && !hint) {
+        int o = (b == 4 || b == 7) ? sgv : (b == 5 || b == 8) ? sgh : sgh * sgv;
+        if (o) hint = o;
+    }
     int32_t a = (int32_t)1 << (s - 2);
     /* v4.1 per-plane amplitude scale (shifts/adds): 0 = 1.0x quarter-step,
      * 1 = 1.25x, 2 = 1.5x, 3 = 1.75x. All strictly below half-step, so
@@ -1164,8 +1293,91 @@
         if (a < 1) a = 1;
     }
     if (v6 >= 2 || (omc_fill_static && act <= omc_fill_static)) { fox = sfox; foy = sfoy; }
+    if (hint) return hint > 0 ? a : -a;   /* local coded structure wins */
     return omc_fill_sign_sel(col + fox, row + foy, corr) ? a : -a;
 }
+static inline int32_t fill_value_h(const int32_t *ll, int llstride, int llw, int llh,
+                                 int b, int row, int col, int s, int fox, int foy,
+                                 int sfox, int sfoy,
+                                 int32_t lllim, int gain, int corr, int v6, int hint)
+{
+    return fill_value_p(ll, llstride, llw, llh, b, row, col, s, fox, foy,
+                        sfox, sfoy, lllim, gain, corr, v6, hint, 0);
+}
+static inline int32_t fill_value(const int32_t *ll, int llstride, int llw, int llh,
+                                 int b, int row, int col, int s, int fox, int foy,
+                                 int sfox, int sfoy,
+                                 int32_t lllim, int gain, int corr, int v6)
+{
+    return fill_value_h(ll, llstride, llw, llh, b, row, col, s, fox, foy,
+                        sfox, sfoy, lllim, gain, corr, v6, 0);
+}
+
+/* Parent descriptor when the bands live in SEPARATE arrays (lock_verify).
+ * Same rule, same numbers — it must agree with fp_build or the A4 generation
+ * lock cannot verify a filled band. */
+static inline void fp_build_arr(fp_t *fp, const omc_band_t *bl,
+                                int32_t *const bandarr[OMC_NBANDS],
+                                int b, const shift_plan_t *sp, int p)
+{
+    static const signed char PAR[OMC_NBANDS] = {-1,-1,-1,-1,-1,3,-1,4,5,6};
+    int pb = PAR[b];
+    fp->base = 0;
+    if (!omc_fillcorr || pb < 0) return;
+    {
+        int ps = sp->shift[p][pb];
+        if (ps < 1) return;
+        fp->base = bandarr[pb];
+        fp->stride = bl[pb].w; fp->w = bl[pb].w; fp->h = bl[pb].h;
+        fp->half = (int32_t)1 << (ps - 1);
+        fp->rsh = (b >= 7) ? 1 : 0;
+        fp->csh = 1;
+    }
+}
+
+/* Build the parent descriptor for band b of plane p.  bl[] is the band layout
+ * already computed by the caller; `sb` is the plane's reconstruction buffer and
+ * `stride` its width.  Identical on both sides: every input is derived from the
+ * slice header. */
+static inline void fp_build(fp_t *fp, const omc_band_t *bl, const int32_t *sb,
+                            int stride, int b, const shift_plan_t *sp, int p)
+{
+    static const signed char PAR[OMC_NBANDS] = {-1,-1,-1,-1,-1,3,-1,4,5,6};
+    int pb = PAR[b];
+    fp->base = 0;
+    if (!omc_fillcorr || pb < 0) return;
+    {
+        const omc_band_t *P = &bl[pb];
+        int ps = sp->shift[p][pb];
+        if (ps < 1) return;                      /* no step, no discrimination */
+        fp->base = sb + (size_t)P->r0 * stride + P->c0;
+        fp->stride = stride; fp->w = P->w; fp->h = P->h;
+        fp->half = (int32_t)1 << (ps - 1);
+        fp->rsh = (b >= 7) ? 1 : 0;              /* L1 children halve rows */
+        fp->csh = 1;                             /* every child halves columns */
+    }
+}
+
+/* Causal sign state for one band: `up` holds the previous row's coded signs,
+ * `left` the previous cell's.  Both are coded-data only. */
+#define OMC_UC_SIGNROW 4096   /* widest band row: max plane width 8192 / 2 */
+typedef struct { signed char *up; int left; int w; } fc_state_t;
+long long omc_fc_fire, omc_fc_tot;
+static inline int fc_hint(const fc_state_t *fc, int col)
+{
+    int u, h;
+    if (!omc_fillcorr || !fc->up) return 0;
+    u = fc->up[col];
+    h = (fc->left && u && fc->left == u) ? fc->left : 0;
+    omc_fc_tot++; if (h) omc_fc_fire++;
+    return h;
+}
+static inline void fc_push(fc_state_t *fc, int col, int32_t q)
+{
+    int s = (q > 0) - (q < 0);
+    if (fc->up) fc->up[col] = (signed char)s;
+    fc->left = s;
+}
 
 /* v4.1 per-plane fill-gain code from the aggregate measured amplitude of the
  * gated zero-coded positions of the plane's FILLED bands, in 1/64-step units
@@ -1395,6 +1607,7 @@
             const int32_t *pc = e->pcoef[p][b];
             int n = bands[b].h * bands[b].w, w = bands[b].w;
             tex_vmaf = OMC_BAND_TEXTURE(b) && c->cfg.tune_vmaf;
+            fp_t vfp; fp_build_arr(&vfp, bands, e->coef[p], b, &sp, p);
             for (int i = 0; i < n; i++) {
                 int s = coeff_shift(&sp, p, b, i);
                 int32_t q = omc_quant1b_dz(cf[i], s, tex_vmaf,
@@ -1402,9 +1615,9 @@
                 int32_t v = omc_dequant1(q, s);
                 if (m) v += pc[i];
                 if (fb && v == 0 && q == 0)
-                    v = fill_value(llbuf, llw, llw, llh, b, i / w, i % w,
+                    v = fill_value_p(llbuf, llw, llw, llh, b, i / w, i % w,
                                    s, fox, foy, sfox, sfoy, lllim, pgain, c->cfg.grain_corr,
-                                   1 + (c->cfg.fill_static ? 1 : 0));
+                                   1 + (c->cfg.fill_static ? 1 : 0), 0, &vfp);
                 if (v != e->coef[p][b][i]) {
                     if (getenv("OMC_DEBUG_VERIFY"))
                         fprintf(stderr, "verify fail sl=%d p=%d b=%d i=%d m=%d fb=%d "
@@ -1628,14 +1841,40 @@
              * bottom (tail debt on top).  +boost%% of B for refreshed
              * slices, funded by shaving the others — CBR total unchanged.
              * 50 measured: refresh parity, PSNR/VMAF unchanged. */
-            if (omc_rboost > 0 && c->cfg.refresh_r) {
+            /* MIN SLICE DEPTH: the refresh boost redistributes budget
+             * THROUGH the causal bank, which only has room when a frame has
+             * many slices.  On short pipelines the reserve for the boosted
+             * slices still ahead can starve the refreshed slice it is meant
+             * to protect (measured: 256x32, 4 slices, R=2 — the encoder
+             * cannot meet exact CBR at all).  Shipping formats are 72+
+             * slices; below 16 the boost stands down entirely. */
+            if (omc_rboost > 0 && c->cfg.refresh_r && c->nslices >= 16) {
                 int Rr = c->cfg.refresh_r;
-                int64_t bump = (B8 * omc_rboost) / 100;
-                if (((frame_idx & 0xFF) % Rr) == (slice_idx % Rr)) {
-                    target += bump; hi += bump;
-                } else {
-                    int nref = (c->nslices + Rr - 1) / Rr;
-                    if (c->nslices > nref) {   /* tiny frames: all slices refresh */
+                int phase = (frame_idx & 0xFF) % Rr;
+                /* EXACT count of slices refreshed in THIS frame (k % R ==
+                 * phase).  The old ceil(nslices/R) estimate over-counted on
+                 * phases past nslices % R, so the shave did not match the
+                 * bump and the frame's targets drifted off the CBR budget.
+                 * When every slice refreshes (R == 1, or a single-slice
+                 * frame) there is nothing left to fund the boost, so the
+                 * boost stands down entirely — measured: without this the
+                 * encoder simply fails to meet exact CBR (256x32 R=1). */
+                int nref = phase < c->nslices
+                         ? (c->nslices - 1 - phase) / Rr + 1 : 0;
+                if (nref > 0 && c->nslices > nref) {
+                    int64_t bump = (B8 * omc_rboost) / 100;
+                    /* self-limit: the shave must be absorbable.  Every
+                     * non-refreshed slice can give back at most (B8 - lo)
+                     * before its own floor, so the boost pool is capped at
+                     * (nslices-nref)*(B8-lo).  Without this, small frames
+                     * (few slices, e.g. 4) let the boosted slices claim the
+                     * whole frame budget and the encoder cannot meet exact
+                     * CBR at all — measured: 256x32 R=2 failed to encode. */
+                    int64_t pool = (int64_t)(c->nslices - nref) * (B8 - lo);
+                    if (bump * nref > pool) bump = pool / nref;
+                    if ((slice_idx % Rr) == phase) {
+                        target += bump; hi += bump;
+                    } else {
                         int64_t shave = bump * nref / (c->nslices - nref);
                         target -= shave; hi -= shave;
                         if (hi < lo) hi = lo;
@@ -1672,11 +1911,22 @@
                  * their boosted share held back too, or earlier boosted
                  * slices drain the bank and the LAST refreshed slice pays
                  * for all of them (s71 tex 7.2 -> 5.0 measured). */
-                if (omc_rboost > 0 && c->cfg.refresh_r) {
+                int phase2 = c->cfg.refresh_r
+                           ? (frame_idx & 0xFF) % c->cfg.refresh_r : 0;
+                int nref2 = c->cfg.refresh_r && phase2 < c->nslices
+                          ? (c->nslices - 1 - phase2) / c->cfg.refresh_r + 1 : 0;
+                /* mirror the allocator's stand-down: no boost, no reserve */
+                if (omc_rboost > 0 && c->cfg.refresh_r && c->nslices >= 16 &&
+                    nref2 > 0 && c->nslices > nref2) {
                     int Rr2 = c->cfg.refresh_r;
                     int64_t bump2 = (B8w * omc_rboost) / 100;
+                    {   /* mirror the allocator's self-limit exactly */
+                        int64_t lo2 = omc_alloc >= 3 ? B8w - (B8w >> 3) : (B8w >> 1);
+                        int64_t pool2 = (int64_t)(c->nslices - nref2) * (B8w - lo2);
+                        if (bump2 * nref2 > pool2) bump2 = pool2 / nref2;
+                    }
                     for (int j = slice_idx + 1; j < c->nslices; j++)
-                        if (((frame_idx & 0xFF) % Rr2) == (j % Rr2))
+                        if (phase2 == (j % Rr2))
                             reserve += bump2 + (B8w >> 5) + (B8w >> 6);
                 }
                 int64_t avail = frame_total - (int64_t)e->spent_bits - reserve;
@@ -2841,15 +3091,18 @@
                 }
                 const int32_t *pc = e->pcoef[p][b];
                 const int32_t *ll = e->sbuf[p];
+                fp_t fp; fp_build(&fp, bl, e->sbuf[p], pw, b, &sp, p);
                 for (int i = 0; i < band_n[p][b]; i++) {
+                    int fcol = i % B->w;
                     int sft = coeff_shift(&sp, p, b, i);
                     int32_t v = omc_dequant1(e->qbuf[p][b][i], sft);
                     if (m) v += pc[i];
                     if (fb && v == 0 && e->qbuf[p][b][i] == 0)
-                        v = fill_value(ll, pw, llw, llh, b, i / B->w, i % B->w,
+                        v = fill_value_p(ll, pw, llw, llh, b, i / B->w, fcol,
                                        sft, fox, foy, sfox, sfoy, lllim,
                                        fill_gain[p], c->cfg.grain_corr,
-                                       1 + (c->cfg.fill_static ? 1 : 0));
+                                       1 + (c->cfg.fill_static ? 1 : 0),
+                                       0, &fp);
                     e->sbuf[p][(size_t)(B->r0 + i / B->w) * pw + B->c0 + i % B->w] = v;
                 }
             }
@@ -3079,16 +3332,19 @@
             }
                 const int32_t *pc = e->pcoef[p][b];
                 const int32_t *ll = e->sbuf[p]; /* LL rect written first (b=0) */
+                fp_t fp; fp_build(&fp, bl, e->sbuf[p], pw, b, &sp, p);
                 for (int i = 0; i < band_n[p][b]; i++) {
                     int s = coeff_shift(&sp, p, b, i);
+                    int fcol = i % B->w;
                     int32_t v = omc_dequant1(e->qbuf[p][b][i], s);
                     if (m) v += pc[i];
                     if (fb && v == 0 && e->qbuf[p][b][i] == 0)
-                        v = fill_value(ll, pw, llw, llh, b, i / B->w, i % B->w,
+                        v = fill_value_p(ll, pw, llw, llh, b, i / B->w, fcol,
                                        s, fox, foy, sfox, sfoy, lllim, fill_gain[p],
                                        c->cfg.grain_corr,
-                                       1 + (c->cfg.fill_static ? 1 : 0));
-                    e->sbuf[p][(size_t)(B->r0 + i / B->w) * pw + B->c0 + i % B->w] = v;
+                                       1 + (c->cfg.fill_static ? 1 : 0),
+                                       0, &fp);
+                    e->sbuf[p][(size_t)(B->r0 + i / B->w) * pw + B->c0 + fcol] = v;
                 }
             }
         }
@@ -3184,6 +3440,7 @@
 omc_dec_t *omc_dec_create(const omc_config_t *cfg)
 {
     omc_global_init();
+    if (omc_xsl) omc_xsl_lim = xsl_lim_for(cfg);
     /* The STREAM is authoritative for the in-loop filter, not the environment.
      * omc_global_init() seeds omc_tf_mode from OMC_TF because that is how an
      * ENCODER is asked for the filter; a decoder must instead take what the
@@ -3391,6 +3648,7 @@
             const omc_tans_table_t *grp = v44 ? omc_tans[gids[p][b] & (OMC_NTABLES - 1)]
                                               : omc_tans_legacy[gids[p][b]];
             memset(d->rowsig, 0, (size_t)B->w);
+            fp_t fp; fp_build(&fp, bands, d->sbuf[p], pw, b, &sp, p);
             int col = 0, left = 0, row = 0;
             int32_t prev_q = 0;
             for (int i = 0; i < n; i++) {
@@ -3418,10 +3676,11 @@
                 int32_t rec = omc_dequant1(q, s);
                 if (m) rec += pc[i];
                 if (fb && rec == 0 && q == 0)
-                    rec = fill_value(ll, pw, llw, llh, b, row, col, s, fox, foy, sfox, sfoy,
+                    rec = fill_value_p(ll, pw, llw, llh, b, row, col, s, fox, foy, sfox, sfoy,
                                      lllim, fill_gain[p], c->cfg.grain_corr,
                                      (c->cfg.ver_minor >= 6) +
-                                     (c->cfg.fill_static && c->cfg.ver_minor >= 7 ? 1 : 0));
+                                     (c->cfg.fill_static && c->cfg.ver_minor >= 7 ? 1 : 0),
+                                     0, &fp);
                 d->sbuf[p][(size_t)(B->r0 + i / B->w) * pw + B->c0 + col] = rec;
                 left = v44 ? omc_q2(v < 0 ? -v : v) : (v != 0);
                 d->rowsig[col] = (uint8_t)left;
diff -ruN '--exclude=*.o' '--exclude=*.yuv' '--exclude=__pycache__' '--exclude=.pytest_cache' '--exclude=work' '--exclude=_xc' '--exclude=repro' '--exclude=harness' '--exclude=delivery' '--exclude=*.log' '--exclude=omc_enc' '--exclude=omc_dec' '--exclude=omc_uc_tool' '--exclude=omc_tf_tool' '--exclude=omc_unblend_tool' '--exclude=test_cap' '--exclude=test_cap_old' '--exclude=test_cap_live' '--exclude=test_cc' '--exclude=test_tf' '--exclude=test_uc' '--exclude=test_unit' '--exclude=test_xsl' ./src/internal.h [machine-path-redacted]/.work/ni0811/v49live/src/internal.h
--- a/src/internal.h	2026-08-12 22:41:44.975258791 -0400
+++ b/src/internal.h	2026-08-11 23:33:50.656540896 -0400
@@ -172,10 +172,25 @@
 static inline int32_t omc_quant1(int32_t c, int s) { return omc_quant1b(c, s, 1); }
 /* texture bias applies to the level-1/2 detail bands only */
 #define OMC_BAND_TEXTURE(b) ((b) >= 4)
+extern int omc_recoff;   /* codec.c: centroid dequantisation, n/16 of a step */
 static inline int32_t omc_dequant1(int32_t q, int s)
 {
     int32_t a = q < 0 ? -q : q;
     a <<= s;
+    /* CENTROID RECONSTRUCTION (normative when omc_recoff != 0).  The quantiser
+     * rounds to nearest, so q<<s is the bin CENTRE.  Wavelet detail coefficients
+     * are Laplacian, for which the MMSE reconstruction point lies TOWARD ZERO of
+     * the centre — reconstructing at the centre systematically over-states
+     * energy, which is exactly what the measured retention shows (finest luma
+     * band 0.283 of source against JPEG XS's 0.080) and exactly what VMAF-NEG
+     * refuses to credit.  Shift by n/16 of a step: shifts and adds only, and
+     * with n < 8 the point stays inside its own bin, so re-quantising the
+     * reconstruction still yields q — the generation lock is preserved. */
+    if (omc_recoff && a) {
+        int32_t d = (omc_recoff << s) >> 4;
+        a -= d;
+        if (a < 0) a = 0;
+    }
     return q < 0 ? -a : a;
 }
 static inline int omc_cat(int32_t q) /* magnitude category = bit length of |q| */
diff -ruN '--exclude=*.o' '--exclude=*.yuv' '--exclude=__pycache__' '--exclude=.pytest_cache' '--exclude=work' '--exclude=_xc' '--exclude=repro' '--exclude=harness' '--exclude=delivery' '--exclude=*.log' '--exclude=omc_enc' '--exclude=omc_dec' '--exclude=omc_uc_tool' '--exclude=omc_tf_tool' '--exclude=omc_unblend_tool' '--exclude=test_cap' '--exclude=test_cap_old' '--exclude=test_cap_live' '--exclude=test_cc' '--exclude=test_tf' '--exclude=test_uc' '--exclude=test_unit' '--exclude=test_xsl' ./src/upconv.c [machine-path-redacted]/.work/ni0811/v49live/src/upconv.c
--- a/src/upconv.c	2026-08-12 22:41:44.975569814 -0400
+++ b/src/upconv.c	2026-08-11 23:33:50.656540896 -0400
@@ -572,6 +572,35 @@
  * result stands.  DOWNCONVERSION (num > den) is decimation: the cutoff must
  * move DOWN to the OUTPUT Nyquist or everything above it folds back into the
  * picture, and a lowpass with D times the period needs D times the aperture. */
+
+static int uc_gcd(int a, int b);   /* defined below */
+
+/* Centre-aligned output->source mapping for the rational path (see
+ * omc_uc_scale_aligned).  Returns the integer source index in *ip and the
+ * phase in *php.  When the ratio's parity does not admit an exact phase the
+ * function falls back to the historical corner-aligned mapping and returns 0,
+ * so the caller can report the ratio as un-aligned rather than pretend. */
+static int uc_map_pos(int r, int num, int den, int *ip, int *hph)
+{
+    int64_t den2 = 2 * (int64_t)den;
+    int64_t N = (int64_t)(2 * r + 1) * num - den;   /* units of 1/(2*den) */
+    int64_t i = N / den2, h = N - i * den2;
+    if (h < 0) { h += den2; i -= 1; }               /* floor, not truncate */
+    *ip = (int)i; *hph = (int)h;                    /* h in [0, 2*den)     */
+    return 1;
+}
+
+/* 1 when the (sw,sh)->(dw,dh) conversion is centre-aligned on both axes, 0 when
+ * an axis falls back to the corner mapping (mixed-parity ratio: exact centring
+ * would need a 2*den phase bank).  Callers that care about geometric
+ * registration should test this. */
+int omc_uc_scale_aligned(int sw, int sh, int dw, int dh)
+{
+    (void)sw; (void)sh; (void)dw; (void)dh;
+    return 1;   /* every rational ratio is centre-aligned: even half-phases use
+                 * a published phase, odd ones use the derived half-phase */
+}
+
 int omc_uc_scale_taps(int num, int den)
 {
     int nt;
@@ -842,16 +871,39 @@
 
 static int uc_gcd(int a, int b) { while (b) { int t = a % b; a = b; b = t; } return a; }
 
+
+/* Derive the filter at half-phase (p0 + 1/2) from the two published phases.
+ * dst must hold bk->nt entries.  See the file-level note on centre alignment. */
+static void uc_halfphase(const uc_bank_t *bk, int p0, int32_t *dst)
+{
+    int k, nt = bk->nt, big = 0;
+    const int32_t *a = bk->c + (size_t)p0 * nt;
+    const int32_t *b;
+    int shift_b = 0;
+    int32_t sum = 0;
+    if (p0 + 1 < bk->den) b = bk->c + (size_t)(p0 + 1) * nt;
+    else { b = bk->c; shift_b = 1; }   /* wrap: phase 0, one sample later */
+    for (k = 0; k < nt; k++) {
+        int32_t bv = shift_b ? (k >= 1 ? b[k - 1] : 0) : b[k];
+        int32_t v = a[k] + bv;
+        dst[k] = v >= 0 ? (v + 1) >> 1 : -((-v + 1) >> 1);
+        sum += dst[k];
+        if (dst[k] > dst[big]) big = k;
+    }
+    dst[big] += 1024 - sum;            /* exact unity DC, as the generator does */
+}
+
 /* One 1-D polyphase pass over `n` output lines of length `len`.
  * get(ctx, i, out) writes source line i.  Output line o samples source position
  * o * num / den.  Returns via cb(o, line). */
 static void uc_scale_line(const omc_uc_t *u, const uc_bank_t *bk,
                           const int32_t *lines, int nl, int len,
-                          int i0, int ph, const int32_t *dcorr, int32_t *out)
+                          int i0, int ph, const int32_t *dcorr, int32_t *out,
+                          const int32_t *cov)
 {
     int j;
     int32_t maxv = (int32_t)((1u << u->depth) - 1);
-    const int32_t *c = bk->c + (size_t)ph * bk->nt;
+    const int32_t *c = cov ? cov : bk->c + (size_t)ph * bk->nt;
     int nt = bk->nt;
     /* Limiter envelope.  For interpolation the bounding pair IS the envelope,
      * which is what makes the ringing guarantee exact.  For decimation the
@@ -997,8 +1049,12 @@
         goto hpass;
     }
     for (r = 0; r < dh; r++) {                       /* vertical pass */
-        int64_t pos = (int64_t)r * numv;
-        int i = (int)(pos / denv), ph = (int)(pos % denv);
+        int32_t hcv[OMC_UC_MAXTAPS];
+        const int32_t *covv = NULL;
+        int i, hp, ph;
+        uc_map_pos(r, numv, denv, &i, &hp);
+        ph = hp >> 1;
+        if (hp & 1) { uc_halfphase(&bkv, ph, hcv); covv = hcv; }
         for (t = 0; t < ntv; t++) {
             const uint16_t *sp = src + (size_t)uc_mir(i + t - (ntv / 2 - 1), sh) * ss;
             for (j = 0; j < sw; j++) lines[(size_t)t * sw + j] = sp[j];
@@ -1021,7 +1077,7 @@
                                dcorr, dtmp);
                 dc = dcorr;
             }
-            uc_scale_line(u, &bkv, lines, sh, sw, i, ph, dc, row);
+            uc_scale_line(u, &bkv, lines, sh, sw, i, ph, dc, row, covv);
         }
         memcpy(mid + (size_t)r * sw, row, sizeof(int32_t) * sw);
     }
@@ -1030,13 +1086,17 @@
       if (!e) { rc = -3; goto out; }
       bkh.c = e->c; bkh.den = denh; bkh.nt = e->nt; }
     for (j = 0; j < dw; j++) {                       /* horizontal pass */
-        int64_t pos = (int64_t)j * numh;
-        int i = (int)(pos / denh), ph = (int)(pos % denh);
+        int32_t hch[OMC_UC_MAXTAPS];
+        const int32_t *covh = NULL;
+        int i, hp, ph;
+        uc_map_pos(j, numh, denh, &i, &hp);
+        ph = hp >> 1;
+        if (hp & 1) { uc_halfphase(&bkh, ph, hch); covh = hch; }
         for (t = 0; t < nth; t++) {
             int c = uc_mir(i + t - (nth / 2 - 1), sw);
             for (r = 0; r < dh; r++) cols[(size_t)t * dh + r] = mid[(size_t)r * sw + c];
         }
-        uc_scale_line(u, &bkh, cols, sw, dh, i, ph, NULL, orow);
+        uc_scale_line(u, &bkh, cols, sw, dh, i, ph, NULL, orow, covh);
         for (r = 0; r < dh; r++) dst[(size_t)r * ds + j] = (uint16_t)orow[r];
     }
     rc = 0;
diff -ruN '--exclude=*.o' '--exclude=*.yuv' '--exclude=__pycache__' '--exclude=.pytest_cache' '--exclude=work' '--exclude=_xc' '--exclude=repro' '--exclude=harness' '--exclude=delivery' '--exclude=*.log' '--exclude=omc_enc' '--exclude=omc_dec' '--exclude=omc_uc_tool' '--exclude=omc_tf_tool' '--exclude=omc_unblend_tool' '--exclude=test_cap' '--exclude=test_cap_old' '--exclude=test_cap_live' '--exclude=test_cc' '--exclude=test_tf' '--exclude=test_uc' '--exclude=test_unit' '--exclude=test_xsl' ./tests/test_cap.c [machine-path-redacted]/.work/ni0811/v49live/tests/test_cap.c
--- a/tests/test_cap.c	1969-12-31 19:00:00.000000000 -0500
+++ b/tests/test_cap.c	2026-08-12 00:35:34.701671930 -0400
@@ -0,0 +1,145 @@
+/* The boundary-blend cap is per-CONTEXT, not per-process (CAP_RULE_REVIEW F1).
+ *
+ * A multi-channel server runs several encoders in one process at DIFFERENT
+ * rates, which is exactly what a process-wide cap cannot survive: the last
+ * context created would decide the blend for all of them, and a stream encoded
+ * with one cap does not reconstruct under another.  This test builds that
+ * situation on purpose -- one context below 0.75 bpp (cap 8) and one above
+ * (cap 4), alive at the same time, frames interleaved -- and requires each to
+ * produce exactly what it produces alone, and to round-trip through its own
+ * decoder byte-exactly.
+ */
+#include <stdio.h>
+#include <stdlib.h>
+#include <string.h>
+#include "omc1.h"
+
+static int fails = 0;
+#define CHECK(c, m) do { printf("%s: %s\n", (c) ? "ok" : "FAIL", m); \
+                         if (!(c)) fails++; } while (0)
+
+enum { W = 256, H = 32, SH = 16, NF = 3 };
+#define WC (W / 2)
+#define WORDS ((size_t)W * H + 2 * (size_t)WC * H)
+
+static void fill(uint16_t *p, size_t n, uint32_t seed)
+{
+    uint32_t x = seed;
+    for (size_t i = 0; i < n; i++) { x = x * 1103515245u + 12345u;
+                                     p[i] = (uint16_t)(64 + ((x >> 16) % 800)); }
+}
+
+static void cfg_at(omc_config_t *c, uint32_t bps)
+{
+    memset(c, 0, sizeof(*c));
+    c->width = W; c->height = H; c->bitdepth = 10; c->chroma = OMC_CF_422;
+    c->ver_minor = OMC_VERSION_MINOR; c->slice_h = SH;
+    c->fps_num = 50; c->fps_den = 1; c->bits_per_slice = bps;
+}
+
+/* The cap edits the RECONSTRUCTION (and through it the temporal reference), so
+ * the reconstruction is the sensitive observable -- a bitstream comparison only
+ * bites once prediction is actually selected, which needs real content. */
+static void run(omc_enc_t *e, const uint16_t *pix, uint8_t *out, size_t fb,
+                uint16_t *rec)
+{
+    for (int f = 0; f < NF; f++) {
+        const uint16_t *px = pix + WORDS * f;
+        omc_frame_t fr = {{(uint16_t *)px, (uint16_t *)(px + (size_t)W * H),
+                           (uint16_t *)(px + (size_t)W * H + (size_t)WC * H)},
+                          {W, WC, WC}};
+        uint16_t *r = rec + WORDS * f;
+        omc_frame_t fo = {{r, r + (size_t)W * H,
+                           r + (size_t)W * H + (size_t)WC * H}, {W, WC, WC}};
+        omc_enc_frame(e, &fr, f, out + fb * f, fb, rec ? &fo : NULL);
+    }
+}
+
+int main(void)
+{
+    /* 0.5 bpp and 1.5 bpp at this geometry: the rule picks 8 and 4 */
+    const uint32_t LO = (uint32_t)(0.5 * W * SH), HI = (uint32_t)(1.5 * W * SH);
+    omc_config_t clo, chi;
+    cfg_at(&clo, LO); cfg_at(&chi, HI);
+    int nsl = H / SH;
+    size_t flo = (size_t)LO / 8 * nsl, fhi = (size_t)HI / 8 * nsl;
+    uint16_t *pa = malloc(WORDS * 2 * NF), *pb = malloc(WORDS * 2 * NF);
+    for (int f = 0; f < NF; f++) {
+        fill(pa + WORDS * f, WORDS, 0xA0000000u + (uint32_t)f);
+        fill(pb + WORDS * f, WORDS, 0xB0000000u + (uint32_t)f);
+    }
+    uint8_t *a1 = malloc(flo * NF), *b1 = malloc(fhi * NF);
+    uint8_t *a2 = malloc(flo * NF), *b2 = malloc(fhi * NF);
+    uint16_t *ra1 = malloc(WORDS * 2 * NF), *ra2 = malloc(WORDS * 2 * NF);
+    uint16_t *rb1 = malloc(WORDS * 2 * NF), *rb2 = malloc(WORDS * 2 * NF);
+
+    /* alone */
+    omc_enc_t *e = omc_enc_create(&clo); run(e, pa, a1, flo, ra1); omc_enc_destroy(e);
+    e = omc_enc_create(&chi);            run(e, pb, b1, fhi, rb1); omc_enc_destroy(e);
+
+    /* together, interleaved, in the order that breaks a process-wide cap:
+     * the HIGH-rate context is created last, so a global would force cap 4
+     * onto the low-rate stream too. */
+    omc_enc_t *ea = omc_enc_create(&clo);
+    omc_enc_t *eb = omc_enc_create(&chi);
+    for (int f = 0; f < NF; f++) {
+        const uint16_t *px = pa + WORDS * f;
+        omc_frame_t fa = {{(uint16_t *)px, (uint16_t *)(px + (size_t)W * H),
+                           (uint16_t *)(px + (size_t)W * H + (size_t)WC * H)},
+                          {W, WC, WC}};
+        { uint16_t *r = ra2 + WORDS * f;
+          omc_frame_t fo = {{r, r + (size_t)W * H,
+                             r + (size_t)W * H + (size_t)WC * H}, {W, WC, WC}};
+          omc_enc_frame(ea, &fa, f, a2 + flo * f, flo, &fo); }
+        px = pb + WORDS * f;
+        omc_frame_t fb2 = {{(uint16_t *)px, (uint16_t *)(px + (size_t)W * H),
+                            (uint16_t *)(px + (size_t)W * H + (size_t)WC * H)},
+                           {W, WC, WC}};
+        { uint16_t *r = rb2 + WORDS * f;
+          omc_frame_t fo = {{r, r + (size_t)W * H,
+                             r + (size_t)W * H + (size_t)WC * H}, {W, WC, WC}};
+          omc_enc_frame(eb, &fb2, f, b2 + fhi * f, fhi, &fo); }
+    }
+    omc_enc_destroy(ea); omc_enc_destroy(eb);
+
+    CHECK(memcmp(a1, a2, flo * NF) == 0 && memcmp(ra1, ra2, WORDS * 2 * NF) == 0,
+          "low-rate context: stream AND reconstruction unchanged by a "
+          "high-rate context in the same process");
+    CHECK(memcmp(b1, b2, fhi * NF) == 0 && memcmp(rb1, rb2, WORDS * 2 * NF) == 0,
+          "high-rate context: stream AND reconstruction unchanged by a "
+          "low-rate context in the same process");
+
+    /* and each must reconstruct under its own decoder */
+    for (int which = 0; which < 2; which++) {
+        omc_config_t *c = which ? &chi : &clo;
+        uint8_t *bs = which ? b2 : a2;
+        size_t fb = which ? fhi : flo;
+        const uint16_t *src = which ? pb : pa;
+        omc_enc_t *ee = omc_enc_create(c);
+        omc_dec_t *dd = omc_dec_create(c);
+        uint16_t *rec = malloc(WORDS * 2), *dec = malloc(WORDS * 2);
+        int ok = 1;
+        for (int f = 0; f < NF; f++) {
+            const uint16_t *px = src + WORDS * f;
+            omc_frame_t fr = {{(uint16_t *)px, (uint16_t *)(px + (size_t)W * H),
+                               (uint16_t *)(px + (size_t)W * H + (size_t)WC * H)},
+                              {W, WC, WC}};
+            omc_frame_t fo = {{rec, rec + (size_t)W * H,
+                               rec + (size_t)W * H + (size_t)WC * H}, {W, WC, WC}};
+            omc_frame_t fd = {{dec, dec + (size_t)W * H,
+                               dec + (size_t)W * H + (size_t)WC * H}, {W, WC, WC}};
+            uint8_t *tmp = malloc(fb);
+            omc_enc_frame(ee, &fr, f, tmp, fb, &fo);
+            omc_dec_frame(dd, bs + fb * f, fb, &fd);
+            if (memcmp(tmp, bs + fb * f, fb) != 0) ok = 0;
+            if (memcmp(rec, dec, WORDS * 2) != 0) ok = 0;
+            free(tmp);
+        }
+        CHECK(ok, which ? "rt=0 on the high-rate context (cap 4)"
+                        : "rt=0 on the low-rate context (cap 8)");
+        omc_enc_destroy(ee); omc_dec_destroy(dd); free(rec); free(dec);
+    }
+    free(pa); free(pb); free(a1); free(b1); free(a2); free(b2);
+    printf(fails ? "FAILURES: %d\n" : "all ok\n", fails);
+    return fails ? 1 : 0;
+}
diff -ruN '--exclude=*.o' '--exclude=*.yuv' '--exclude=__pycache__' '--exclude=.pytest_cache' '--exclude=work' '--exclude=_xc' '--exclude=repro' '--exclude=harness' '--exclude=delivery' '--exclude=*.log' '--exclude=omc_enc' '--exclude=omc_dec' '--exclude=omc_uc_tool' '--exclude=omc_tf_tool' '--exclude=omc_unblend_tool' '--exclude=test_cap' '--exclude=test_cap_old' '--exclude=test_cap_live' '--exclude=test_cc' '--exclude=test_tf' '--exclude=test_uc' '--exclude=test_unit' '--exclude=test_xsl' ./tools/omc_dec.c [machine-path-redacted]/.work/ni0811/v49live/tools/omc_dec.c
--- a/tools/omc_dec.c	2026-08-12 22:41:44.974661280 -0400
+++ b/tools/omc_dec.c	2026-08-11 23:33:50.655592279 -0400
@@ -178,5 +178,9 @@
     omc_dec_destroy(dec);
     fclose(fi); fclose(fo);
     free(pix); free(sb); free(fb); free(obuf); free(upix); free(utmp);
+    { extern long long omc_fc_fire, omc_fc_tot;
+      if (getenv("OMC_FILLCORR_STAT") && omc_fc_tot)
+        fprintf(stderr, "FILLCORR fires %lld/%lld = %.2f%%\n", omc_fc_fire, omc_fc_tot, 100.0*omc_fc_fire/omc_fc_tot); }
     return 0;
 }
+
```

## R.2 — the inherited tree → the delivered v4.14 (this session)


```diff
diff -ruN '--exclude=*.o' '--exclude=*.yuv' '--exclude=__pycache__' '--exclude=.pytest_cache' '--exclude=work' '--exclude=_xc' '--exclude=repro' '--exclude=harness' '--exclude=delivery' '--exclude=*.log' '--exclude=omc_enc' '--exclude=omc_dec' '--exclude=omc_uc_tool' '--exclude=omc_tf_tool' '--exclude=omc_unblend_tool' '--exclude=test_cap' '--exclude=test_cap_old' '--exclude=test_cap_live' '--exclude=test_cc' '--exclude=test_tf' '--exclude=test_uc' '--exclude=test_unit' '--exclude=test_xsl' ./CHANGELOG_v4.14.md [machine-path-redacted]/.work/final/omc_v4.9/CHANGELOG_v4.14.md
--- a/CHANGELOG_v4.14.md	1969-12-31 19:00:00.000000000 -0500
+++ b/CHANGELOG_v4.14.md	2026-08-12 22:34:06.516752080 -0400
@@ -0,0 +1,44 @@
+# OMC v4.14 — 2026-08-12
+
+No bitstream change. `ver_minor` stays 9; every v4.13 stream decodes identically.
+
+## Defaults changed
+
+| what | was | is | why |
+|---|---|---|---|
+| `slice_h` | 8 | **16** (8 below 720p) | 15.8% / 10.1% / 8.1% bitrate saved at 0.5 / 1.0 / 2.0 bpp, measured at production width |
+| banking overdraft | B/2 prefix allowance | **none**, no knob | removed; the latency model is simpler and the pictures were approved |
+| blend cap scope | process-wide global | **per encoder context** | a multi-channel server at mixed rates could not work otherwise (CAP_RULE_REVIEW F1) |
+| blend cap threshold | `4·bits < 3·px` | `8·bits < 3·px·(3 or 2)` | counts **coded samples**, so 4:4:4 lands at 1.125 bpp instead of 0.75 |
+| output-stage latency | whole slice periods | **raster-clocked**, charged in lines | the converter is a streaming line buffer, not a slice-batched stage |
+| 4:2:2 chroma resample | centre-aligned | **co-sited** | centre alignment is right for picture resizing and wrong for the chroma detour |
+
+## Added
+
+- **XSL level 6** — seam-strength measurement; repairs as well as level 3 and
+  cuts the worst generation loss, cut-proof where `--xsl auto` was not.
+- **XSL level 7** (experimental, environment-only) — the boundary edit as an
+  exactly reversible lifting cascade, plus `omc_xsl_unblend()` and
+  `omc_unblend_tool`.
+- **`--xsl auto`** — frame-0 probe. Demonstrated defeated by a scene cut; kept
+  as an explicit option, not a default.
+- **`slice_h` 32** as a user-selectable knob (8 / 16 / 32).
+- **`docs/XSL.md`** — the cross-slice story in one place, first time.
+- **`OPEN_DECISIONS.md`** — register with one rule: an entry may only exist if
+  something in the build speaks up about it.
+
+## Gates added
+
+| gate | what it prevents |
+|---|---|
+| `tests/test_cap.c` | a process-wide blend cap; compares reconstruction, not just bitstreams |
+| `G21` in `test_uc.c` | the output-stage latency bound, simulated row by row, 165 cases |
+| `G22` in `test_uc.c` | the two sample-siting conventions drifting into each other |
+| `G-XSL1` in `test_xsl.c` | the environment silently deciding a decode that the stream should decide |
+| `G-XSL2` in `test_xsl.c` | the level-7 edit ceasing to be exactly reversible |
+
+## Reverted during this session
+
+An `OMC_XSL_FORCE` widening in `omc_read_stream_header()`, added on the mistaken
+belief that the environment could not reach the decoder's XSL level. It can, via
+`common_init()`. Measured, reverted, and recorded in `docs/XSL.md`.
diff -ruN '--exclude=*.o' '--exclude=*.yuv' '--exclude=__pycache__' '--exclude=.pytest_cache' '--exclude=work' '--exclude=_xc' '--exclude=repro' '--exclude=harness' '--exclude=delivery' '--exclude=*.log' '--exclude=omc_enc' '--exclude=omc_dec' '--exclude=omc_uc_tool' '--exclude=omc_tf_tool' '--exclude=omc_unblend_tool' '--exclude=test_cap' '--exclude=test_cap_old' '--exclude=test_cap_live' '--exclude=test_cc' '--exclude=test_tf' '--exclude=test_uc' '--exclude=test_unit' '--exclude=test_xsl' ./docs/BITSTREAM.md [machine-path-redacted]/.work/final/omc_v4.9/docs/BITSTREAM.md
--- a/docs/BITSTREAM.md	2026-08-11 23:33:50.667442845 -0400
+++ b/docs/BITSTREAM.md	2026-08-12 13:32:57.599091150 -0400
@@ -45,7 +45,7 @@
 | 8 | 2 | height |
 | 10 | 1 | bit depth: 8, 10 or 12 |
 | 11 | 1 | chroma format: 0 = 4:2:2, 1 = 4:4:4 |
-| 12 | 1 | slice_h: 8 or 16 luma lines |
+| 12 | 1 | slice_h: coding-unit height in luma lines. Legal values **8, 16, 32**. **16 is the default**; 8 is used for 720p-class heights (A2); 32 is an explicit choice for 2160p/4320p only. A knob, not a profile — see §7 |
 | 13 | 2 | fps numerator |
 | 15 | 2 | fps denominator |
 | 17 | 1 | colour primaries (ISO/IEC 23001-8 code point: 1 = BT.709, 9 = BT.2020) |
@@ -340,9 +340,44 @@
 ## 7. Constraints
 
 - Width: multiple of 32 (4:4:4) or 64 (4:2:2). Height: multiple of slice_h.
-- slice_h = 16; formats whose height is not divisible by 16 (e.g. 1080) and 720p-class
-  formats use slice_h = 8. One codec, one format: slice_h is a coded parameter, not a
-  profile.
+- **`slice_h` is a knob with a default, and the default is 16.**
+
+  **Legal values: 8, 16 and 32** (and 0 in an API config, meaning "use the
+  default"). The default:
+
+  | height | slice_h | why |
+  |---|---|---|
+  | > 720 (1080p, 2160p, 4320p …) | **16** | the default. Heights that do not divide by 16 — **1080 above all** — are coded at the next multiple (1088) and cropped on output by the pad-and-crop path of §8. This costs under 1 % of rate in padded rows and is worth roughly **10 % of rate at 1.0 bpp and 16 % at 0.5 bpp** against 8-line slices, measured at 1920 px on real footage, on every plane at once |
+  | ≤ 720 (720p-class) | **8** | **A2.** With the banking overdraft removed (2026-08-12) 16-line slices now fit 720p on the codec term alone — 0.945 ms at 50 Hz, 0.789 at 59.94/60 — but **720p50 with a vertical rescale in the output path is 1.140 ms and does not fit.** Since `uc_ratio` is advisory and a decoder may convert on its own initiative, 8 is the default that is safe whatever the far end does. `--slice-h 16` is available at 720p and is sound at 59.94 Hz and above (0.951 ms with the worst conversion), or at 50 Hz on a leg that will never convert |
+
+  An encoder MAY be told otherwise: `--slice-h N` (CLI) or `cfg.slice_h` (API)
+  overrides the default, and the value written into byte 12 is what the decoder
+  obeys. `slice_h = 0` selects the default above. The **coded** height must be a
+  whole number of slices; a picture whose true height is not (1080 at slice_h 16)
+  is coded padded and cropped with `display_height`, which is what
+  `tools/omc_enc.c` does for you.
+
+  **32 lines** is available as an explicit choice and is never the default. At
+  2160p it is the same fraction of picture height that 16 lines is at 1080p —
+  the same step, not a second helping — and it measures a further 6.5–12 % of
+  rate there. Its latency is the constraint: 32 lines fits with a conversion in
+  the path at 2160p and 4320p from 59.94 Hz upward, and at 2160p50 only with the
+  raster-clocked output converter. Below 2160p, 32 lines exceeds the budget on
+  the codec term alone at broadcast rates and must not be used. Decoder buffers
+  scale linearly with `slice_h`; an implementation that declares support for 32
+  must size for it.
+
+  One codec, one format: `slice_h` is a coded stream parameter that every decoder
+  already reads and sizes itself from — not a per-leg profile and not a
+  conformance point.
+
+  **A2 interaction, stated so it is not discovered.** At 1080p50 with a vertical
+  rescale in the decoder's output path, 16-line slices are refused by
+  `omc_validate_config()` under the shipped conversion charge (1.069 ms). Without
+  a conversion, 1080p50 at 16 lines is 0.775 ms and fits with margin. The refusal
+  is the contract working, not a surprise; a facility that needs both must either
+  run that leg at `--slice-h 8` or adopt the raster-clocked output converter
+  (`writeups/NEW_IDEAS_08112026_TEST_REPORT.md` §2).
 - Bit depth 8, 10, 12. Internal datapath fits 16-bit signed at 12-bit input with the
   documented +3-bit transform growth (see docs/HARDWARE.md).
 
@@ -631,6 +666,53 @@
 OMC_XSL_LIM); (c) when slice k reconstructs, slice k-1's row 15 receives the
 mirrored averaging blend toward (its row 14 + k's row 0)/2, same cap,
 applied to reference AND display on both sides. Slice 0 rows untouched.
+
+**The blend cap is normative and rate-derived (minor 9).** The cap named
+`OMC_XSL_LIM` above is not a constant: it is **8 codes (10-bit scale) below
+0.75 bpp and 4 codes at or above it**, derived by both ends from fields the
+stream header already carries:
+
+```
+px  = width * slice_h                      (luma samples per slice)
+cap = (4 * bits_per_slice < 3 * px) ? 8 : 4        (exact integer comparison)
+```
+
+The comparison is exact integer arithmetic, so 0.75 bpp itself takes cap 4 by
+definition and two implementations cannot round it differently. Both ends
+derive the same value from the same header fields, so nothing new is signalled.
+The cap scales with the *depth* of the codes, `cap * ((maxv + 1) >> 10)`, so it
+means the same thing at 8, 10 and 12 bits.
+
+Rationale (blind review of cap 4 / 8 / 16 at three rates; SESSION_LEDGER 2.3):
+below 0.75 bpp the quantizer step at a slice seam exceeds what a 4-code blend
+can repair and the seam reads as a visible horizontal line; at and above
+0.75 bpp the wider blend over-smooths the boundary rows and costs fidelity for
+no visible benefit.
+
+**The cap is per-encoder-context state, never a process-wide global.** A
+multi-channel server runs several contexts at different rates in one process; a
+shared cap would let the last context created decide the blend for all of them
+and produce a stream its own decoder does not reconstruct. Conformance requires
+per-context derivation (`tests/test_cap.c` builds exactly that situation).
+
+**The threshold counts CODED SAMPLES, not luma pixels.** A 4:2:2 picture carries
+2 samples per luma pixel and a 4:4:4 picture carries 3, so at the same nominal
+bpp a 4:4:4 stream is materially coarser — and it is coarseness the cap responds
+to. Expressed on samples, the single reviewed threshold lands at **0.75 bpp for
+4:2:2** (unchanged, byte-identical to the rule as originally approved) and
+**1.125 bpp for 4:4:4**, which is the same picture coarseness. Both were
+confirmed by eye (2026-08-12); the 4:4:4 arm was measured at +5.42 codes of seam
+excess under the narrow cap against +3.10 under the wide one.
+
+**Bit depth needs no term of its own** (measured 2026-08-12). The cap already
+scales with depth in the reconstruction — `cap * ((maxv + 1) >> 10)`, so ±4 at
+10-bit and ±16 at 12-bit are the same fraction of full scale. On identical
+content coded at both depths, 12-bit measures *less* seam structure than 10-bit
+at the same bitrate, and the cap choice barely registers at either. The
+threshold is therefore a function of chroma format and rate only.
+
+`OMC_XSL_LIM` remains available as an experimental override and is not part of
+this specification.
 Encoder and decoder MUST apply identical arithmetic (round-trip is verified
 byte-exact). Rationale + measurements: band-fix memo §21-26 (boundary rows
 carry 30-60% excess quantization noise; the eye integrates the ridge into a
diff -ruN '--exclude=*.o' '--exclude=*.yuv' '--exclude=__pycache__' '--exclude=.pytest_cache' '--exclude=work' '--exclude=_xc' '--exclude=repro' '--exclude=harness' '--exclude=delivery' '--exclude=*.log' '--exclude=omc_enc' '--exclude=omc_dec' '--exclude=omc_uc_tool' '--exclude=omc_tf_tool' '--exclude=omc_unblend_tool' '--exclude=test_cap' '--exclude=test_cap_old' '--exclude=test_cap_live' '--exclude=test_cc' '--exclude=test_tf' '--exclude=test_uc' '--exclude=test_unit' '--exclude=test_xsl' ./docs/CONTROL_PLANE.md [machine-path-redacted]/.work/final/omc_v4.9/docs/CONTROL_PLANE.md
--- a/docs/CONTROL_PLANE.md	2026-08-11 23:33:50.667442845 -0400
+++ b/docs/CONTROL_PLANE.md	2026-08-12 15:36:50.893515745 -0400
@@ -100,6 +100,8 @@
 | grain-replace (`--grain-replace`) | off | v4.7 grain-hold v3 (E-9): third amplitude vote, per-slice-band grain-carpet vote, parent threshold 8 (10-bit), soft-threshold coding; viewer-box ant-tail 18.0% (v4.4) -> 7.98% @2bpp (below fair JPEG XS 7.73%), 18.6% -> 10.7% @1.0bpp; no flattening (flat-block rate 0.08% = baseline); enable only after blind-viewing signoff (rev. 6). Details: REPORT 18.7, ENHANCEMENTS_LEDGER E-9 |
 | fill-static (`--fill-static`) | off | v4.7 (bitstream minor 7, stream byte 27 bit 2): grain-fill sign-tile offsets frame-independent — static grain texture, no temporal animation; used e.g. for beach fine grain (67% retained + static fill). Zero new per-pixel multipliers on FPGA (one per-band static offset pair, same omc_fill_offsets with f=0). Details: BITSTREAM 9.5, ENHANCEMENTS_LEDGER E-10 |
 | block-mv (`--block-mv`) | off | per-block motion field (bitstream minor 3); measured ~0 on the delivery corpus - experimental capability |
+| xsl level 6 (`OMC_XSL=6`) | — | **seam-keyed continuous blend.** Levels 4/5 scale the blend by how empty the slice's detail band is, which measured backwards: busy slices get almost no blend and busy slices are where the seam is worst (city @0.5: unrepaired 19.25, level 3 → 9.51, level 4 → 17.00). Level 6 scales it by the seam itself — the step across the join minus the picture's own steps either side — continuously, per slice boundary, per plane, every frame. Repairs as well as level 3 (within 0.3 codes on all nine clip/rate points) and cuts the worst generation loss from −4.66 to −3.34 dB. Cut-proof by construction; both ends derive it from reconstructions they both hold, so no signalling and no bitstream change. `rt = 0` byte-exact at 4:2:2 and 4:4:4, 10- and 12-bit, slice_h 8 and 16 |
+| xsl (`--xsl auto\|0\|3`) | off (env `OMC_XSL`) | cross-slice boundary reconstruction. **`auto`** encodes frame 0 once with XSL off, measures the seam step it would repair, and switches XSL on only above 3 codes @10-bit — carried by the existing stream minor, no new field. Rationale: the seam is worth repairing at low rate and gone by 2.0 bpp, while XSL costs 2–4.7 dB across six generations exactly where the seam has gone (it puts the reconstruction off the quantiser lattice and the generation lock stops firing). Measured: `auto` removes every generation loss above 1.2 dB and keeps the seam fix wherever the seam is visible |
 | mv_regions | off | per-region/half-pel search: single-hop links only (generations reconverge instead of replaying; DESIGN.md 1b) |
 | lossless (--lossless) | off | lossless-preferred: bit-exact per frame when it fits the CBR budget, graceful lossy fallback otherwise (still exact-CBR); per-frame bit-exact status reported; implies no_fill; default ceiling 16 bpp. REPORT 14. Crossover: clean <=2 bpp, grain ~9 bpp (vs XS 4 / >11.9). |
 
diff -ruN '--exclude=*.o' '--exclude=*.yuv' '--exclude=__pycache__' '--exclude=.pytest_cache' '--exclude=work' '--exclude=_xc' '--exclude=repro' '--exclude=harness' '--exclude=delivery' '--exclude=*.log' '--exclude=omc_enc' '--exclude=omc_dec' '--exclude=omc_uc_tool' '--exclude=omc_tf_tool' '--exclude=omc_unblend_tool' '--exclude=test_cap' '--exclude=test_cap_old' '--exclude=test_cap_live' '--exclude=test_cc' '--exclude=test_tf' '--exclude=test_uc' '--exclude=test_unit' '--exclude=test_xsl' ./docs/LATENCY.md [machine-path-redacted]/.work/final/omc_v4.9/docs/LATENCY.md
--- a/docs/LATENCY.md	2026-08-11 23:33:50.667442845 -0400
+++ b/docs/LATENCY.md	2026-08-12 13:32:57.603091169 -0400
@@ -16,15 +16,25 @@
 ## Model
 
 ```
-T_total = T_capture + T_transmit + T_overdraft + T_pipeline
+T_total = T_capture + T_transmit + T_pipeline
   T_capture   = slice_h source lines            (the encoder can start when the slice's
                                                  last line arrives; strictly causal)
   T_transmit  = one slice period = frame_time/N (CBR pipe drains one slice per period)
-  T_overdraft = 0.5 slice periods               (banking prefix bound: byte prefix of
-                                                 slices 0..k never exceeds (k+1)B + B/2,
-                                                 enforced by the encoder — see §5 of
-                                                 docs/BITSTREAM.md)
   T_pipeline  = 2 source lines                  (transform/entropy pipeline depth)
+
+  T_overdraft = 0   since 2026-08-12.  It used to be 0.5 slice periods -- a FIFTH of
+                the whole budget -- because the encoder was allowed to overdraw the
+                prefix by B/2 and exact CBR made later slices repay.  Measured across
+                three clips at 0.5 and 1.0 bpp, removing that allowance moves quality
+                by under 0.1 dB on every plane, moves VMAF and VMAF-NEG by under a
+                twentieth of a point on five of six arms, leaves exact CBR untouched
+                and leaves the overflow retry count unchanged -- and it improves the
+                tail-debt signature, because the overdraft was the mechanism that made
+                the LAST slices of a frame repay what the first ones overspent.
+                Tightening is backward-compatible: BITSTREAM sect 5's bound is an
+                UPPER bound, decoders keep the wider tolerance, and the per-slice wire
+                cap is deliberately unchanged so older streams still decode.
+                OMC_OD=<percent of B> restores it for experiments.
 ```
 
 The decoder begins reconstructing slice k the moment its bytes are in; the prefix bound
@@ -36,19 +46,12 @@
 
 ## Per-format worst-case table (generated by harness/latency_model.py)
 
-| Format | Slice h | Slices | Capture | Transmit | Overdraft | Pipeline | **Total** |
-|---|---|---|---|---|---|---|---|
-| 720p50 | 8 | 90 | 0.222 ms | 0.222 ms | 0.111 ms | 0.056 ms | **0.611 ms** |
-| 720p59.94 | 8 | 90 | 0.185 ms | 0.185 ms | 0.093 ms | 0.046 ms | **0.510 ms** |
-| 720p60 | 8 | 90 | 0.185 ms | 0.185 ms | 0.093 ms | 0.046 ms | **0.509 ms** |
-| 1080p50 | 8 | 135 | 0.148 ms | 0.148 ms | 0.074 ms | 0.037 ms | **0.407 ms** |
-| 1080p59.94 | 8 | 135 | 0.124 ms | 0.124 ms | 0.062 ms | 0.031 ms | **0.340 ms** |
-| 1080p60 | 8 | 135 | 0.123 ms | 0.123 ms | 0.062 ms | 0.031 ms | **0.340 ms** |
-| 2160p50 | 16 | 135 | 0.148 ms | 0.148 ms | 0.074 ms | 0.019 ms | **0.389 ms** |
-| 2160p60 | 16 | 135 | 0.123 ms | 0.123 ms | 0.062 ms | 0.015 ms | **0.324 ms** |
-| 2160p100 | 16 | 135 | 0.074 ms | 0.074 ms | 0.037 ms | 0.009 ms | **0.194 ms** |
-| 2160p120 | 16 | 135 | 0.062 ms | 0.062 ms | 0.031 ms | 0.008 ms | **0.162 ms** |
-| 4320p60 (8K) | 16 | 270 | 0.062 ms | 0.062 ms | 0.031 ms | 0.008 ms | **0.162 ms** |
+The per-format table below is regenerated by harness/latency_model.py; the figures
+in `docs/BITSTREAM.md` §7, in the A2 guard of `omc_validate_config()` and in gate
+G21 of `tests/test_uc.c` all follow the same model and are checked against each
+other. With the default slice heights (16 above 720p, 8 at 720p-class) and no
+overdraft, the worst supported case is **720p50 at 0.500 ms codec-only and
+0.806 ms with the worst conversion in the path**.
 
 All formats < 1 ms: YES
 
@@ -56,9 +59,22 @@
 1 ms with margin; the worst case (720p50, the slowest line rate) is 0.61 ms.
 
 Notes:
-- slice_h: 16 lines; 8 for 720p-class heights and heights not divisible by 16 (1080p),
-  which also lowers their latency. One codec, one bitstream — slice_h is a coded
-  parameter (stream header), not a per-leg profile.
+- **slice_h defaults to 16 lines.** 720p-class heights use 8. Since the banking
+  overdraft went to zero this is no longer a hard impossibility — 720p50 at 16
+  lines is 0.945 ms codec-only and 720p60 is 0.789 — but 720p50 **with a
+  conversion** is 1.140 ms, and `uc_ratio` is advisory, so 8 is the default that
+  holds whatever the far end decides to do. Heights that do not divide by 16 (1080) are
+  coded padded to the next multiple and cropped on output, so they take the
+  default like every other format — the older rule dropped them to 8 for an
+  arithmetic reason and paid ~10 % of rate for it.
+- The table above is the **8-line** figure for 720p and the **16-line** figure
+  everywhere else. At 1080p, 16 lines doubles the capture and pacing terms:
+  0.775 ms at 50 Hz, 0.646 ms at 60 Hz — both inside the bar with no conversion in
+  the path. **With** a vertical rescale at 1080p50, `omc_validate_config()`
+  refuses it under the shipped conversion charge (1.069 ms); run that leg at
+  `--slice-h 8`, or adopt the raster-clocked output converter.
+- One codec, one bitstream — slice_h is a coded parameter (stream header), read
+  by every decoder, not a per-leg profile.
 - Determinism: T_capture, T_transmit, T_overdraft, T_pipeline are all functions of the
   format only. The encoder's banking never violates the prefix bound (asserted in code),
   so the bound holds for every slice of every frame.
@@ -71,22 +87,50 @@
 one extra slice period for the last row of each slice. No other term
 changes; the per-slice cost is O(width) adds/shifts.
 
-## OMC-UC output stage (upconversion), when enabled
-The upconverter is an OUTPUT-STAGE resampler: it runs after slice
-reconstruction and never feeds the coding loop, so none of the terms in the
-model above change. Its own cost is bounded and declared:
 
-| ratio / mode | added latency | why |
+## The decoder's output stage — the contract, and what it is worth (2026-08-12)
+
+The vertical rescaler needs a few source rows **beyond** the row it is producing:
+6 for any interpolation, 9 for 3:2, 12 for 2:1, 18 for 3:1. What that costs
+depends entirely on **how the decoder hands rows to it**, and that is now a
+declared property of the implementation rather than an assumption:
+
+| `cfg.uc_out_batched` | the contract | the charge |
+|---|---|---|
+| `OMC_OUT_RASTER` (0, **default**) | rows go downstream as they become final; the output is clocked at the destination raster rate | **`reach` lines + 1** |
+| `OMC_OUT_SLICE_BATCHED` (1) | rows go downstream one whole slice at a time | `ceil(reach / slice_h)` whole **slice periods** |
+
+**Why `reach × line_time`.** Output for source row *r* is producible once slice
+`floor((r + reach) / slice_h)` has landed, and is due at `r · line + T`.
+Maximising over *r* puts the worst case at `r = m · slice_h − reach`, which gives
+`T ≥ reach × line_time` — independent of slice height. This is verified by
+**row-by-row simulation over every supported (format, slice height, ratio)**
+combination, not by algebra: gate **G21** in `tests/test_uc.c`, 165 cases, none
+over the bound.
+
+**The +1 line is OMC_XSL.** At level 3, slice *k* rewrites the **last row of
+slice k−1** when it reconstructs, so that row is not final until one slice period
+later. `LATENCY.md` used to warn that a strictly row-streaming sink must
+therefore account a whole extra slice period — and a raster-clocked converter is
+exactly such a sink. Simulated, the true cost is **one line**: the deferred row
+sits at the *end* of its slice and already had `slice_h − 1` lines of slack.
+
+**The price.** An output buffer of the filter aperture plus one slice — at most
+68 rows, at 2160p → 720p with 32-line slices — and a free-running output clock. A
+genlocked facility has both. An integration that cannot meet this must declare
+`uc_out_batched` and take the higher figure; `omc_validate_config()` then refuses
+what that figure cannot support, exactly as before.
+
+**What it is worth.** Every conversion path in the product got cheaper, at every
+slice height, immediately:
+
+| path | before | after |
 |---|---|---|
-| 2x vertical (or 2x both axes) | **+1 slice period** | the 12-tap kernel's vertical reach is 8 source rows, i.e. within one 8-row slice floor either side; verified against the analytic bound `omc_uc_analytic_reach()` and measured in test_uc |
-| 4x (cascade of two 2x levels) | +2 slice periods at slice_h 8, **+1** at slice_h 16 | the cascade's measured reach stays inside the analytic bound |
-| horizontal-only scale (e.g. chroma resample along the line) | **0** | output row r depends on source row r alone — zero vertical reach (test_uc G19) |
-| horizontal mirror | **0** | an exact in-line reversal; vertical flip and 90-degree rotation are whole-frame operations and are NOT part of the sub-1 ms path |
-
-`omc_validate_config()` REFUSES any (format, ratio) combination whose total
-would exceed the 1 ms budget rather than silently exceeding it — the refusal
-is part of the contract, not a runtime surprise. Banded operation is exact:
-1/2/4/8/16/32-row band output is byte-identical to whole-plane output, so a
-streaming sink may pull any band size without changing the result. The stage
-is stateless and deterministic (no history, no RNG), which is what keeps
-generation chains and A4 intact when the scaler is in the path.
+| 1080p50 → 720p50 (slice_h 8, ships today) | 0.705 ms | **0.594 ms** |
+| 2160p50 → 1080p50 (slice_h 16, ships today) | 0.538 ms | **0.510 ms** |
+| 720p50 → 1080p50 (slice_h 8, ships today) | 0.834 ms | **0.806 ms** |
+| 1080p50 → 2160p50 at slice_h 16 | 1.069 ms — refused | **0.961 ms** |
+| 2160p50 → 1080p50 at slice_h 32 | 1.061 ms — refused | **0.883 ms** |
+
+The last two are the reason it was done: they are the only cells in the whole
+supported matrix where the slice-height ladder was blocked, and both are 50 Hz.
diff -ruN '--exclude=*.o' '--exclude=*.yuv' '--exclude=__pycache__' '--exclude=.pytest_cache' '--exclude=work' '--exclude=_xc' '--exclude=repro' '--exclude=harness' '--exclude=delivery' '--exclude=*.log' '--exclude=omc_enc' '--exclude=omc_dec' '--exclude=omc_uc_tool' '--exclude=omc_tf_tool' '--exclude=omc_unblend_tool' '--exclude=test_cap' '--exclude=test_cap_old' '--exclude=test_cap_live' '--exclude=test_cc' '--exclude=test_tf' '--exclude=test_uc' '--exclude=test_unit' '--exclude=test_xsl' ./docs/XSL.md [machine-path-redacted]/.work/final/omc_v4.9/docs/XSL.md
--- a/docs/XSL.md	1969-12-31 19:00:00.000000000 -0500
+++ b/docs/XSL.md	2026-08-12 22:33:42.897632560 -0400
@@ -0,0 +1,157 @@
+# Cross-slice boundary handling (XSL)
+
+Status as of 2026-08-12. Levels 0–6 ship; level 7 is experimental and reachable
+only from the environment.
+
+## Why it exists
+
+OMC codes the picture in independent slices of `slice_h` luma lines. Rows 0 and
+15 of every slice sit at the edge of the wavelet's support, where the basis
+functions concentrate quantisation error — measured at 30–60% excess noise
+energy on those rows (band-fix §22). The eye integrates the resulting full-width
+disturbance into a visible horizontal line at every slice join. The incumbent
+has no internal edges and no such line, so this is a difference the eye can find
+in an A/B.
+
+Two things address it, both in-loop so encoder and decoder stay in step:
+
+1. **The cross-slice wavelet term.** The previous slice's final rows supply the
+   boundary term `d[-1]` to this slice's inverse transform, so the reconstruction
+   is continuous across the join rather than reflected at it.
+2. **The boundary edit.** A bounded blend applied to the reconstruction after
+   the inverse transform, pulling rows 0 and 15 toward their neighbours.
+
+## Levels
+
+| level | behaviour |
+|---|---|
+| 0 | off: no wavelet term, no edit |
+| 2 | wavelet term + forward blend on row 0 |
+| 3 | + deferred edit of the previous slice's row 15 (**the shipped default**) |
+| 4–5 | blend strength scales continuously with slice emptiness |
+| 6 | + seam-strength measurement: full strength only where a step is actually present |
+| 7 | **experimental**: the edit rewritten as an exactly reversible lifting cascade |
+
+A minor-9 stream decodes at level 3 on its own say-so. `OMC_XSL` in the
+environment overrides that — the deliberate instrumentation path (C1) and the
+only way to reach level 7. Gate `G-XSL1` in `tests/test_xsl.c` pins the other
+half: with the environment silent, the stream decides.
+
+## The blend cap
+
+Normative, minor 9: **8 codes at 10-bit below 0.75 bpp, 4 codes at or above it**,
+scaled by `(maxv + 1) >> 10` for other depths. The threshold counts **coded
+samples**, so at 4:4:4 it lands at 1.125 bpp. Chosen by eye in a three-arm blind
+comparison (caps 4/8/16).
+
+The cap lives in `ctx_common_t`, **per context, never process-wide** — a
+multi-channel server runs several encoders at different rates in one process and
+a process-wide cap would let the last one created decide the blend for all of
+them. Gate: `tests/test_cap.c`.
+
+## Refresh barriers (A5)
+
+A slice being intra-refreshed this frame takes no cross-slice terms, and a slice
+whose predecessor was refreshed this frame does not retro-edit its last row.
+Both are derived from the slice header (`fidx8`) and config alone, so encoder and
+decoder agree without signalling. Without them, loss-induced drift decayed but
+never cleared and crept one slice per refresh cycle.
+
+Anything that inverts the edit **must repeat these rules**, or it will undo an
+edit that never happened. `omc_xsl_unblend()` does.
+
+## What the edit costs: generation loss
+
+The level-3 edit moves each row **toward a target computed from that row's own
+value**. That discards what the row was, so it cannot be undone. A later encoder
+therefore cannot recover the reconstruction its predecessor coded, cannot lock
+onto it, and smooths an already smoothed picture.
+
+Six generations, 1920×1080 4:2:2 10-bit, PSNR-Y:
+
+| content / rate | no edit at all | level 3 (shipped) |
+|---|---|---|
+| beach, 3.0 bpp, sh 8 | −0.30 dB | **−8.17 dB** |
+| beach, 1.0 bpp, sh 16 | −0.37 dB | **−1.26 dB** |
+| beach, 0.5 bpp, sh 16 | −0.64 dB | −0.93 dB |
+| city, 0.5 bpp, sh 16 | −0.61 dB | −0.48 dB |
+
+The generation lock fires 73/270 slices with the edit off at 3.0 bpp and
+**0/270** with it on. Seam repair and generation locking are mutually exclusive
+per slice under level 3.
+
+## The seam is rate-dependent; the lock is too, in the opposite direction
+
+Un-repaired seam step across a join, as a multiple of the step inside the slice
+(1.000 = the join is no worse than the picture around it):
+
+| clip | 0.5 bpp | 1.0 bpp | 2.0 bpp | 3.0 bpp |
+|---|---|---|---|---|
+| city | 1.824 | 1.269 | 1.067 | 1.013 |
+| beach | 1.705 | 1.294 | 1.048 | 1.021 |
+
+The ridge is real at low rate and gone by 2 bpp. Above ~1.5 bpp both level 3 and
+level 7 **overshoot**, leaving joins smoother than the picture around them (city
+at 3.0 bpp: level 3 −1.707, level 7 −3.119 codes). Meanwhile the lock fires more
+as rate rises. See `OPEN_DECISIONS.md` entry `XSL-RATE-OFF`.
+
+## Level 7: the reversible edit
+
+A lifting step is invertible when its correction depends only on values it does
+not touch. Two of them in a fixed order edit both rows and stay invertible:
+
+```
+forward   step 1   row15 += clamp((row0   - row14) / 4, ±lim)   /* row15 unread */
+          step 2   row0  += clamp((row15' - row1 ) / 4, ±lim)   /* row0  unread */
+
+inverse            row0  -= clamp((row15' - row1 ) / 4, ±lim)
+                   row15 -= clamp((row0   - row14) / 4, ±lim)
+```
+
+Step 2 reads `row15'` — the value step 1 left — and the inverse reads the same
+value, so the two agree. Rows 14 and 1 are never touched by either.
+
+`omc_xsl_unblend(frame, cfg, frame_idx)` applies the inverse to a whole picture.
+An encoder calls it on its input when that input is a previous decode. Proven
+exact: gate `G-XSL2`.
+
+**Results.** Six generations, beach:
+
+| arm | 3.0 bpp / sh 8 | 1.0 bpp / sh 16 |
+|---|---|---|
+| no edit (ceiling) | −0.30 dB | −0.37 dB |
+| level 3 (shipped) | −8.17 dB | −1.26 dB |
+| level 7 + un-blend | **−1.81 dB** | **−0.45 dB** |
+
+Seam repair at 0.5 bpp / sh 16 (step excess, codes): level 3 gives city +6.831,
+beach +2.489, heli +1.029; level 7 gives +6.978, +2.903, +1.193 — within a few
+percent, and better than level 3 at 1.0 bpp.
+
+**Two limits, both open.**
+
+1. **It needs to know when to un-blend.** An encoder that always un-blends also
+   un-blends first-generation material, where there was nothing to undo; the
+   decoder then re-applies the edit and the two cancel. About a third of the
+   seam repair is lost (beach 0.5 bpp: +2.903 becomes +4.873). The results above
+   use an oracle. A detector is wrong in both directions: say "decode" on a
+   master and lose the repair, say "master" on a decode and take the full slide.
+2. **Exactness is verified intra-only.** The edit is in-loop, so two decodes of
+   the same stream diverge from frame 1 onward through prediction. Verifying an
+   inter frame needs that decode's own pre-edit reconstruction, which the decoder
+   does not expose.
+
+See `HANDOFF_BIT_EXACTNESS.md`.
+
+## Instrumentation
+
+| variable | effect |
+|---|---|
+| `OMC_XSL=n` | force level n (overrides the stream) |
+| `OMC_XSL_NOEDIT=1` | level 7 only: keep everything, skip the boundary edit — the ground truth for exactness testing |
+| `OMC_XSL_UNBLEND=1` | `omc_enc`: un-blend the input frame before coding |
+| `OMC_DEBUG_L7=1` | trace level-7 firing per plane and slice |
+| `OMC_DEBUG_LOCK=1` | per-slice generation-lock trace |
+
+**Decoding at level 0 is not a substitute for `OMC_XSL_NOEDIT`.** Level 0 also
+drops the cross-slice wavelet term and changes the whole slice; using it as
+ground truth produced a spurious "6.1% of samples wrong".
diff -ruN '--exclude=*.o' '--exclude=*.yuv' '--exclude=__pycache__' '--exclude=.pytest_cache' '--exclude=work' '--exclude=_xc' '--exclude=repro' '--exclude=harness' '--exclude=delivery' '--exclude=*.log' '--exclude=omc_enc' '--exclude=omc_dec' '--exclude=omc_uc_tool' '--exclude=omc_tf_tool' '--exclude=omc_unblend_tool' '--exclude=test_cap' '--exclude=test_cap_old' '--exclude=test_cap_live' '--exclude=test_cc' '--exclude=test_tf' '--exclude=test_uc' '--exclude=test_unit' '--exclude=test_xsl' ./include/omc1.h [machine-path-redacted]/.work/final/omc_v4.9/include/omc1.h
--- a/include/omc1.h	2026-08-11 23:33:50.663207850 -0400
+++ b/include/omc1.h	2026-08-12 20:20:53.380029437 -0400
@@ -25,8 +25,25 @@
  * reconstruction (XSL + refresh barriers + barrier display blend). */
 #define OMC_RELEASE_MINOR 9
 #define OMC_VERSION_MINOR 7 /* 3 block MC; 4 entropy v2; 5 corr tile; 6 amplitude-matched fill (0.5x code) */
+/* Decoder output-stage contract (A2).  The vertical rescaler needs a few source
+ * rows beyond the row it is producing.  HOW the decoder hands rows to it decides
+ * what that costs:
+ *   OMC_OUT_RASTER  (0, the product's design and the default) -- rows are handed
+ *      over as they become final and the output is clocked at the destination
+ *      raster rate, so the wait is `reach` LINES.  Requires a `reach`-row output
+ *      buffer (<= 68 lines at the steepest supported ratio) and a free-running
+ *      output clock, which a genlocked facility already has.
+ *   OMC_OUT_SLICE_BATCHED (1) -- rows are handed over one whole slice at a time,
+ *      so the wait rounds up to ceil(reach/slice_h) whole SLICE PERIODS.  This is
+ *      what the model charged before 2026-08-12; declare it if an integration
+ *      cannot meet the raster contract, and take the higher figure. */
+#define OMC_OUT_RASTER 0
+#define OMC_OUT_SLICE_BATCHED 1
+
+#define OMC_XSL_LIM_MINOR9 8 /* normative boundary-blend cap below 0.75 bpp,
+                                 * in codes at 10-bit scale (minor 9).  See
+                                 * src/codec.c xsl_lim_for(). */
 #define OMC_MINOR_UC 8
-#define OMC_XSL_LIM_MINOR9 8  /* normative boundary-blend cap, codes @10-bit (minor 9) */
 #define OMC_MINOR_XSL 9     /* 9: cross-slice boundary reconstruction (XSL level 3 +
                                refresh barriers) is NORMATIVE-ON for the whole stream.
                                No per-slice bits; the minor IS the signal. */      /* 8: stream byte 26 carries uc_ratio (OMC-UC upconversion).
@@ -128,6 +145,14 @@
                                 configuration. Conformance is defined on the pair
                                 (stream, ratio): the upconverted output is bit-exact.
                                 Setting it makes the encoder write minor 8. */
+    uint8_t uc_out_batched;  /* how the DECODER hands rows to the rescaler.
+                                0 = OMC_OUT_RASTER (default, the product's
+                                design): rows go downstream as they become final
+                                and the wait is `reach` LINES.  1 =
+                                OMC_OUT_SLICE_BATCHED: a whole slice at a time,
+                                so the wait rounds up to whole slice periods.
+                                Affects the LATENCY FIGURE only -- never the
+                                bitstream, never a pixel. */
     uint8_t a2_strict;       /* 1 = REFUSE any (format, uc_ratio) pair whose total
                                 latency reaches 1 ms; 0 (default) = permit it and
                                 let the caller declare the figure, which
@@ -153,6 +178,17 @@
 typedef struct omc_dec omc_dec_t;
 
 /* ---- encoder ---- */
+/* Should this stream use cross-slice boundary reconstruction?  Encodes frame 0
+ * once with XSL off and measures the seam step in its own reconstruction; above
+ * the threshold there is a seam worth repairing, at or below it there is not and
+ * the generation lock is worth more.  Encoder-side, once per stream; the minor
+ * already carries the result, so nothing new is signalled.  Returns 1, 0, or -1
+ * if the probe could not run.  Call it before omc_write_stream_header(). */
+/* XSL level 7 only: undo the reversible boundary edit on a picture, recovering
+ * the exact reconstruction that produced it.  See codec.c. */
+void omc_xsl_unblend(omc_frame_t *f, const omc_config_t *cfg, int frame_idx);
+int omc_xsl_probe_frame(const omc_config_t *cfg, const omc_frame_t *in);
+
 omc_enc_t *omc_enc_create(const omc_config_t *cfg);
 void omc_enc_destroy(omc_enc_t *e);
 /* Encode one slice (rows [slice_idx*slice_h, +slice_h)). Strictly causal: touches
diff -ruN '--exclude=*.o' '--exclude=*.yuv' '--exclude=__pycache__' '--exclude=.pytest_cache' '--exclude=work' '--exclude=_xc' '--exclude=repro' '--exclude=harness' '--exclude=delivery' '--exclude=*.log' '--exclude=omc_enc' '--exclude=omc_dec' '--exclude=omc_uc_tool' '--exclude=omc_tf_tool' '--exclude=omc_unblend_tool' '--exclude=test_cap' '--exclude=test_cap_old' '--exclude=test_cap_live' '--exclude=test_cc' '--exclude=test_tf' '--exclude=test_uc' '--exclude=test_unit' '--exclude=test_xsl' ./include/omc_uc.h [machine-path-redacted]/.work/final/omc_v4.9/include/omc_uc.h
--- a/include/omc_uc.h	2026-08-11 23:33:50.663207850 -0400
+++ b/include/omc_uc.h	2026-08-12 18:19:06.027120889 -0400
@@ -97,9 +97,33 @@
  * n*num/den, so at ratio 2 it reduces exactly to the dyadic path.
  * NOT REVERSIBLE -- down(up(x)) == x is a dyadic-only guarantee.
  * Returns 0, -1 on a bad argument, -2 if the ratio needs more than 16 phases. */
+/* Sample siting for the rational scaler.  Two different jobs need two different
+ * answers and they are not interchangeable:
+ *
+ *   OMC_SITE_CENTRE  — the output grid is centred on the source grid.  This is
+ *      what RESIZING A PICTURE wants: 1080p -> 2160p keeps the picture where it
+ *      was instead of shifting it half a source sample.
+ *   OMC_SITE_COSITED — output sample 0 lands exactly on source sample 0.  This
+ *      is what CHROMA SITING wants: in 4:2:2, chroma sample k is co-sited with
+ *      luma sample 2k (BITSTREAM's own [1,2,1]/4 convention), so re-centring the
+ *      chroma grid puts the colour a quarter sample off the luma it belongs to.
+ *
+ * It is a PARAMETER and not a field of omc_uc_t for the same reason `mirror`
+ * is: a flag inside the operator config is one a caller can forget to set, and
+ * a stack-allocated omc_uc_t with a garbage byte in it would then resample to
+ * the wrong grid at random. */
+#define OMC_SITE_CENTRE  0
+#define OMC_SITE_COSITED 1
+
 int omc_uc_scale_plane(const omc_uc_t *u, const uint16_t *src, int ss, int sw, int sh,
                        uint16_t *dst, int ds, int dw, int dh);
 
+/* The same, with the siting stated.  omc_uc_scale_plane() above is the
+ * OMC_SITE_CENTRE form, because resizing a picture is the common case. */
+int omc_uc_scale_plane_sited(const omc_uc_t *u, const uint16_t *src, int ss,
+                             int sw, int sh, uint16_t *dst, int ds,
+                             int dw, int dh, int siting);
+
 /* Aspect framing: scale a source CROP into a destination RECT and fill the rest
  * of the output with `fill` (pillarbox, letterbox, 14:9, centre cut).  The bars
  * are written once and the scaler never touches them, so they carry exactly the
@@ -152,6 +176,9 @@
 size_t omc_uc_scale_scratch_bytes(int sw, int sh, int dw, int dh);
 int omc_uc_scale_plane_ws(const omc_uc_t *u, const uint16_t *src, int ss, int sw, int sh,
                           uint16_t *dst, int ds, int dw, int dh, void *ws, size_t wsz);
+int omc_uc_scale_plane_ws_sited(const omc_uc_t *u, const uint16_t *src, int ss,
+                                int sw, int sh, uint16_t *dst, int ds, int dw,
+                                int dh, void *ws, size_t wsz, int siting);
 
 /* B4's floor: "the supported range starts at 720p and scales upward". */
 #define OMC_UC_MIN_HEIGHT 720
@@ -167,15 +194,6 @@
  * for.  Returns 1 if supported, 0 if below the floor. */
 int omc_uc_format_supported(int w, int h);
 
-/* 1 when the rational scale from (sw,sh) to (dw,dh) is CENTRE-aligned on both
- * axes — i.e. the output grid sits on the centres of the source intervals it
- * represents, so scaled content stays registered with unscaled content.  0
- * when an axis falls back to the historical corner-aligned mapping, which
- * displaces the picture by (num-den)/(2*den) output pixels on that axis.
- * Mixed-parity ratios (e.g. 2:1, 3:2, 4:3) need a 2*den phase bank to centre
- * exactly and are the cases that return 0. */
-int omc_uc_scale_aligned(int sw, int sh, int dw, int dh);
-
 /* Latency of a rational conversion.  Always writes the total and the extra
  * slice periods when the conversion is possible at all.  Returns:
  *    0  the conversion holds sub-1 ms -- A2 met
@@ -201,4 +219,15 @@
 int omc_uc_scale_latency(int sw, int sh, int dw, int dh, int slice_h,
                          int fps_num, int fps_den, double *total_ms, int *periods);
 
+/* The same, with the decoder's output-stage contract stated explicitly:
+ * `batched` = OMC_OUT_RASTER (0) charges `reach` lines plus one for the XSL
+ * deferred row; OMC_OUT_SLICE_BATCHED (1) charges ceil(reach/slice_h) whole
+ * slice periods, which is what the model assumed before 2026-08-12.  The
+ * no-suffix form above is the raster-clocked one, because that is the product's
+ * decoder.  `*periods` is meaningful only in the batched case and is 0
+ * otherwise -- the raster charge is in LINES and is already in the total. */
+int omc_uc_scale_latency_ex(int sw, int sh, int dw, int dh, int slice_h,
+                            int fps_num, int fps_den, int batched,
+                            double *total_ms, int *periods);
+
 #endif
diff -ruN '--exclude=*.o' '--exclude=*.yuv' '--exclude=__pycache__' '--exclude=.pytest_cache' '--exclude=work' '--exclude=_xc' '--exclude=repro' '--exclude=harness' '--exclude=delivery' '--exclude=*.log' '--exclude=omc_enc' '--exclude=omc_dec' '--exclude=omc_uc_tool' '--exclude=omc_tf_tool' '--exclude=omc_unblend_tool' '--exclude=test_cap' '--exclude=test_cap_old' '--exclude=test_cap_live' '--exclude=test_cc' '--exclude=test_tf' '--exclude=test_uc' '--exclude=test_unit' '--exclude=test_xsl' ./Makefile [machine-path-redacted]/.work/final/omc_v4.9/Makefile
--- a/Makefile	2026-08-11 23:33:50.655345702 -0400
+++ b/Makefile	2026-08-12 22:33:03.749240896 -0400
@@ -3,7 +3,7 @@
 SRC = src/dwt.c src/tans.c src/bitio.c src/alloc.c src/codec.c src/tables.c src/config.c src/upconv.c src/tfilt.c src/colour.c
 OBJ = $(SRC:.c=.o)
 
-all: omc_enc omc_dec test_unit test_uc test_tf test_cc omc_uc_tool omc_tf_tool
+all: omc_enc omc_dec test_unit test_uc test_tf test_cc test_cap test_xsl omc_uc_tool omc_tf_tool omc_unblend_tool
 
 %.o: %.c include/omc1.h include/tables.h include/omc_uc.h include/omc_tf.h include/omc_cc.h src/internal.h src/uc_poly_tab.c.inc src/cc_tab.c.inc
 	$(CC) $(CFLAGS) -c $< -o $@
@@ -23,6 +23,15 @@
 test_unit: tests/test_unit.c $(OBJ)
 	$(CC) $(CFLAGS) $^ -o $@ -lm
 
+test_cap: tests/test_cap.c $(OBJ)
+	$(CC) $(CFLAGS) $< $(OBJ) -o $@ -lm
+
+test_xsl: tests/test_xsl.c $(OBJ)
+	$(CC) $(CFLAGS) $< $(OBJ) -o $@ -lm
+
+omc_unblend_tool: tools/omc_unblend_tool.c $(OBJ)
+	$(CC) $(CFLAGS) $< $(OBJ) -o $@ -lm
+
 test_uc: tests/test_uc.c $(OBJ)
 	$(CC) $(CFLAGS) $^ -o $@ -lm
 
@@ -32,14 +41,16 @@
 test_cc: tests/test_cc.c $(OBJ)
 	$(CC) $(CFLAGS) $^ -o $@ -lm
 
-test: test_unit test_uc test_tf test_cc
+test: test_unit test_uc test_tf test_cc test_cap test_xsl
 	./test_unit
 	./test_uc
+	./test_cap
+	./test_xsl
 	./test_tf
 	./test_cc
 
 clean:
-	rm -f $(OBJ) omc_enc omc_dec test_unit omc_uc_tool omc_tf_tool test_uc test_tf test_cc
+	rm -f $(OBJ) omc_enc omc_dec test_unit omc_uc_tool omc_tf_tool omc_unblend_tool test_uc test_tf test_cc test_cap test_xsl
 
 .PHONY: all test clean
 
diff -ruN '--exclude=*.o' '--exclude=*.yuv' '--exclude=__pycache__' '--exclude=.pytest_cache' '--exclude=work' '--exclude=_xc' '--exclude=repro' '--exclude=harness' '--exclude=delivery' '--exclude=*.log' '--exclude=omc_enc' '--exclude=omc_dec' '--exclude=omc_uc_tool' '--exclude=omc_tf_tool' '--exclude=omc_unblend_tool' '--exclude=test_cap' '--exclude=test_cap_old' '--exclude=test_cap_live' '--exclude=test_cc' '--exclude=test_tf' '--exclude=test_uc' '--exclude=test_unit' '--exclude=test_xsl' ./OPEN_DECISIONS.md [machine-path-redacted]/.work/final/omc_v4.9/OPEN_DECISIONS.md
--- a/OPEN_DECISIONS.md	1969-12-31 19:00:00.000000000 -0500
+++ b/OPEN_DECISIONS.md	2026-08-12 18:22:07.433003085 -0400
@@ -0,0 +1,260 @@
+# Open decisions — things a person must decide, and what makes them impossible to forget
+
+**The rule of this file:** an entry may only exist here if it also has a
+**hook** — something that runs and speaks up. Prose alone has already failed
+this project once: `CAP_RULE_REVIEW.md` marked the process-wide blend cap
+**CRITICAL** in writing, and the defect still sat live in the working tree until
+a *test* failed on it a day later. A line in a document is not a reminder; a red
+test or a line on stderr is.
+
+An entry is closed by deleting it here **and** removing its hook, in the same
+change. If the hook is still firing, the decision is not made.
+
+---
+
+## CAP-STEP — should the cap key on the quantizer step instead of the rate?
+
+**The question.** `CAP_RULE_REVIEW.md` F3/F4 rejected a *rate*-keyed cap on the
+grounds that the benefit is content-dependent in a way a rate threshold cannot
+express. This session's measurements make that concrete and worse than the review
+knew: **the same clip at the same rate needs different caps on different frames.**
+
+city aerial, 0.5 bpp, seam step excess:
+
+| frame | cap 4 | cap 8 |
+|---|---|---|
+| 0 (cold intra) | **+12.71** | +9.56 |
+| 5 (steady state) | +7.37 | +4.87 |
+
+beach at 0.5 bpp: frame 0 **+5.53**, frame 5 **+0.38** — a factor of fourteen on
+one clip at one rate. No rate rule can separate those, because the rate is
+identical.
+
+**The principled form** the review named: key the cap on the quantizer step
+actually in force at the seam, which **both ends already derive** from the slice
+header. That makes it content-adaptive and frame-adaptive by construction, and it
+is normative-legal without a new field.
+
+**What closes it.** Either a decision to leave the rate rule as shipped (it is
+eye-approved and safe), or a step-keyed implementation with its own adversarial
+review and eye gate.
+
+**Hook — WEAK, and that is a problem.** This file and nothing else. Every other
+entry here has something that runs. If this one is to stay open it wants a test
+that pins the frame-0 seam numbers above, so a regression is caught mechanically
+rather than remembered. Until then it is exactly the kind of entry the rule at
+the top of this file exists to prevent.
+
+---
+
+## SLICE-H — CLOSED 2026-08-12
+
+16 lines approved by eye. `slice_h` is a knob taking **8, 16 or 32**, defaulting
+to **16** for every format above 720p; 720p-class stays at **8** because A2
+forbids otherwise. 32 is an explicit choice for 2160p/4320p and is never a
+default — see CONVERTER below, which gates whether it can become one.
+Documented in `BITSTREAM.md` §7 (with the table), `docs/LATENCY.md` and
+`README.md`. 1080p codes 1088 rows and crops on output.
+
+---
+
+## CONVERTER — CLOSED 2026-08-12, implemented
+
+The decoder's output stage is now **raster-clocked by contract**: rows go
+downstream as they become final and the output is clocked at the destination
+raster rate, so a conversion costs `reach` lines plus one (the OMC_XSL deferred
+row) instead of `ceil(reach / slice_h)` whole slice periods.
+
+Declared, not assumed: `cfg.uc_out_batched` (`OMC_OUT_RASTER` = 0 default,
+`OMC_OUT_SLICE_BATCHED` = 1). An integration that cannot stream rows declares it
+and gets the older, higher figure, and `omc_validate_config()` refuses what that
+figure cannot support. Proved by row-by-row simulation over 165 (format, slice
+height, ratio) combinations — gate **G21**, `tests/test_uc.c` — not by algebra.
+
+Every conversion path got cheaper: 1080p50 → 720p50 at 8 lines, which ships
+today, went 0.705 → 0.594 ms. And it unblocked the two cells that were refused:
+1080p50 at 16 lines with a conversion (1.069 → 0.961) and 2160p50 at 32 lines
+(1.061 → 0.883).
+
+**Carried forward:** the RTL team owns an output buffer of the filter aperture
+plus one slice — at most 68 rows — and a free-running output clock. That is now a
+stated requirement in `docs/LATENCY.md`, not an assumption inside a model.
+
+---
+
+## A4-XSL — XSL costs generation robustness, and A4 is a hard mandate
+
+**Found 2026-08-12 while control-arming the overdraft change; not caused by it.**
+The overdraft is neutral here — the chain behaves identically with and without it.
+
+Re-encode chains, PSNR of each generation against the **original master** (not
+against the previous generation — this is degradation, not drift):
+
+| clip / rate | XSL off | XSL on |
+|---|---|---|
+| heli 2048×1152 @ 2.0 bpp, gen 1 → 6 | +0.18 dB | **−3.22 dB** |
+| beach 1920×1080 @ 1.0 bpp, gen 1 → 6 | +0.01 dB | −0.09 dB |
+| city 1920×1080 @ 0.5 bpp, gen 1 → 6 | — | −0.51 dB |
+
+**With XSL off the chain locks byte-exactly and loses nothing. With XSL on it
+loses, and the loss is worst at high rate** — which is where a contribution codec
+runs for quality-critical work and where the generation claim matters most. At
+2.0 bpp the luma is still falling at generation 8 (−4.08 dB from generation 1),
+and generation 2 against generation 8 differs on 15.6 % of samples, worst by 43
+code values.
+
+`PROJECT_CONSTRAINTS.md` A4 names this exact failure: *"quality quietly eroding
+every time the signal is re-encoded — a classic failure mode of codecs not built
+for contribution, and it is fatal here."*
+
+**Which part of XSL.** Bisected: level 1 (the boundary term alone) already breaks
+the lock; each further level makes it worse (g4→g5: 85.4 dB at level 1, 71.4 at
+level 2, 68.8 at level 3). Turning the barrier **display** blend off does not
+help, so it is the **in-loop** coupling, not the display edit.
+
+**Why.** The generation lock proves "this plan reproduces **this slice's** input
+bit-exactly". With XSL, slice *k*'s coefficients depend on slice *k−1*'s
+reconstruction, and the reconstruction blends edit rows after they were coded — so
+proving it for a slice no longer proves it for the frame. The lock fires on a
+premise that no longer holds and the residuals compound.
+
+**The self-detection idea was tested on 2026-08-12 and it does not work — for a
+reason that is itself the diagnosis.**
+
+The generation lock relies on a lattice signature: a previous OMC reconstruction
+has coefficients that are multiples of their band's quantiser step, and camera
+content does not. Measured directly (`probe.c`, fraction of nonempty bands whose
+lattice exponent is ≥ 1):
+
+| input | XSL off | XSL on |
+|---|---|---|
+| camera master (beach, heli, city, trees, 1080p and 4K) | **0.00 %** | 0.00 % |
+| one OMC pass @ 0.5 bpp | **82–100 %** | **0.38 %** |
+| one OMC pass @ 2.0 bpp | **63–74 %** | **0.03 %** |
+
+With XSL off the separation is total and the idea would work. **With XSL on the
+signature is erased**: a picture that has been through an XSL-enabled OMC is
+indistinguishable from camera content. Slices that lock when re-encoding a
+first-hop decode: **31 of 72 with XSL off, 0 of 72 with XSL on.**
+
+XSL edits the reconstruction at every slice boundary by a sub-step amount. The
+vertical transform of a slice touches all of its rows, so a perturbation in rows
+0 and 15 propagates into every band, and every band's lattice exponent collapses
+to zero.
+
+**So XSL erases the evidence that it has been applied.** That is not a side effect
+of the generation problem — it *is* the generation problem, stated exactly.
+
+**What this rules out.**
+- *Self-detection* (the idea above): the encoder cannot tell it is a later hop,
+  because the thing it would detect has hidden itself.
+- *A frame-scoped lock* (proposed earlier, now **retracted**): there is nothing
+  to verify. The lock needs lattice-aligned candidates and there are none.
+- *Folding the blend into the coding decision* ("code it, don't patch it"): not
+  viable. The blend's correction is **finer than one quantiser step** — at 0.5 bpp
+  the affected bands have steps of 16–64 codes and the blend moves rows by ≤ 4.
+  It is a post-reconstruction edit precisely because the quantiser cannot express
+  it.
+
+**What survives — and there is a much neater option than the reversible-edit
+sketch, found by measuring when each problem actually happens.**
+
+Generation loss and seam visibility sit at **opposite ends of the rate range**, on
+every clip (gen 1 → 6 luma loss against the master, and the seam step at gen 1):
+
+| clip | 0.5 bpp | 1.0 bpp | 2.0 bpp |
+|---|---|---|---|
+| heli — loss / seam | −1.19 / **+1.47** | −1.96 / +0.31 | **−4.66** / −0.42 |
+| beach — loss / seam | −0.13 / **+3.60** | −0.19 / +1.42 | **−3.30** / −1.04 |
+| city — loss / seam | −0.44 / **+9.71** | +0.03 / +2.64 | **−2.09** / −0.43 |
+
+**XSL earns its keep exactly where generations do not care, and costs the most
+exactly where it is not needed.** By 2.0 bpp the seam excess is *negative* on all
+three clips — the boundary rows come out smoother than the interior, so the blend
+is over-smoothing rather than repairing — while the generation loss is 2 to 4.7 dB.
+
+1. **Decide XSL per stream from what it is actually worth.** The encoder already
+   reconstructs; it can measure the boundary step it would be repairing. If that
+   step is small, XSL is buying nothing and should be off. This is exactly the
+   principle `CAP_RULE_REVIEW.md` F3/F4 reached for the blend cap — *key it on the
+   thing it is there to fix* — applied to the feature itself. **Encoder-side,
+   signalled by the existing minor, no new field, no decoder change, no format
+   change, no operator setting.** The cheapest fix available and the one to try
+   first. Not built.
+2. **Operator declaration**, the pattern `--tf` already documents: on at the first
+   hop, off downstream. Free today since XSL is env-gated, but it depends on an
+   operator knowing, which the TF help text itself calls out as fragile.
+3. **Declare XSL single-hop** in the documentation, as `--mv-regions` already is.
+4. **Make the boundary edit a reversible integer lifting step** — the construction
+   `omc_uc` already uses. It would fix generations *and* restore detectability
+   (apply the inverse; if the result lands on the quantiser lattice, the picture
+   was an OMC decode). But it is a format change on both ends, and option 1 gets
+   most of the benefit for none of the cost. **Design sketch, untested.**
+
+**Hook — MISSING, and that is the point.** Until item 1 is done, nothing in the
+build catches this. It is exactly the kind of entry the rule at the top of this
+file exists to prevent.
+
+---
+
+## TREE-SPLIT — the working tree's red gate is FIXED (2026-08-12)
+
+**What was failing.** `tests/test_cc.c` gate 8c — the cost of the 4:2:2 colour
+detour. A colour-space conversion mixes the three components, which only means
+anything where all three sit at the same pixel; 4:2:2 chroma does not, so the
+tool stretches chroma to full width, converts, and shrinks back. The gate allows
+an average error of 0.1 code and a worst pixel of 3 on picture-like chroma. The
+working tree measured **0.10 / worst 4** against the archive's **0.02 / worst 2**,
+and the white-noise thermometer had gone from 37.20 to 69.61 — the filter had
+genuinely changed, not drifted.
+
+**Why.** The tree had moved the rational scaler to **centre-aligned** sampling —
+correct, and a real improvement for RESIZING A PICTURE, which should stay centred
+rather than shift half a source sample. But it was applied to every caller,
+including the chroma detour. In 4:2:2, chroma sample *k* is **co-sited** with luma
+sample *2k*; re-centring the chroma grid puts the colour a quarter sample off the
+luma it belongs to, and the derived half-phase filters that centring needs are an
+average of two published phases, which is a blunter filter.
+
+**The fix is not a revert — both conventions are needed, for different jobs.** The
+siting is now an explicit parameter, `OMC_SITE_CENTRE` / `OMC_SITE_COSITED`, with
+`omc_uc_scale_plane()` keeping the centred behaviour (resizing is the common case)
+and `omc_uc_scale_plane_sited()` naming it. The chroma detour in `omc_uc_tool.c`
+asks for co-sited, and gate 8c now exercises the same path the tool uses.
+
+It is a parameter rather than a field of `omc_uc_t` for the reason the header
+already gives for `mirror`: a flag inside the operator config is one a caller can
+forget to set, and a stack-allocated struct with a garbage byte would resample to
+the wrong grid at random.
+
+**Verified.** Both conventions land where they should — on a ramp through a 1:2
+upscale, co-sited puts output 40 at source position 20.000 and centred puts it at
+19.750 with output 41 at 20.250. Gate 8c is back to 0.02 / worst 2. All five
+suites green on the working tree. The encoder is byte-identical to
+`omc_v4.13_20260812.zip`.
+
+**Still open, and it is only bookkeeping now:** the working tree and the delivered
+archive are still two different codecs — the tree carries the parent-band grain
+fill (`omc_fillcorr`) and the centre-aligned scaler, the archive does not. Both
+are green. Someone should decide which is the codec and cut one archive from it.
+
+**Hook.** `make test` on both trees. Both pass, so this entry is now a decision
+about housekeeping rather than a defect.
+
+---
+
+**The state.** `Codec/Current/omc_v4.9.1_capfix_20260812.zip` (the delivery) and
+`.work/final/omc_v4.9` (the working tree) are not the same codec. The working
+tree is ahead — it carries `omc_fillcorr` (the parent-band grain fill from
+`ENERGY_GAPS.md` E-1) and changes to `upconv.c` and `LATENCY.md` — and it is
+**currently failing `test_cc`**: *"4:2:2 detour: the chroma round trip is worse
+than stated."* The 2026-08-11 archive it was cut from was already missing the
+blend-cap rule, which is how a reviewed, eye-approved decision reached a delivered
+codec as a flat constant.
+
+**What closes it.** Someone decides which tree is the codec, fixes the red gate,
+and cuts one archive from it.
+
+**Hook.** `make test` is red on the working tree. That is the hook, and it is
+doing its job — provided the delivery is always cut from a green tree, which is
+the discipline that failed on 2026-08-11.
diff -ruN '--exclude=*.o' '--exclude=*.yuv' '--exclude=__pycache__' '--exclude=.pytest_cache' '--exclude=work' '--exclude=_xc' '--exclude=repro' '--exclude=harness' '--exclude=delivery' '--exclude=*.log' '--exclude=omc_enc' '--exclude=omc_dec' '--exclude=omc_uc_tool' '--exclude=omc_tf_tool' '--exclude=omc_unblend_tool' '--exclude=test_cap' '--exclude=test_cap_old' '--exclude=test_cap_live' '--exclude=test_cc' '--exclude=test_tf' '--exclude=test_uc' '--exclude=test_unit' '--exclude=test_xsl' ./README.md [machine-path-redacted]/.work/final/omc_v4.9/README.md
--- a/README.md	2026-08-11 23:33:50.655345702 -0400
+++ b/README.md	2026-08-12 05:02:24.357589541 -0400
@@ -98,13 +98,34 @@
 make test                 # DWT/quant/tANS/rt0/causality unit gates
 
 ./omc_enc -i in.yuv -o out.omc -w 1920 -h 1056 --fmt 422 --depth 10 --bpp 2.0 \
-          [--recon rec.yuv] [--slice-h 16] [--primaries 9 --transfer 16 --matrix 9] \
+          [--recon rec.yuv] [--slice-h N] [--primaries 9 --transfer 16 --matrix 9] \
           [--tune vmaf] [--refresh N] [--mv-regions] [--block-mv|--no-block-mv] \
           [--grain-replace] [--grain-corr] [--fill-static] [--no-deadzone] \
           [--no-fill]  # --no-fill: fidelity mode; --mv-regions: single-hop only
 ./omc_dec -i out.omc -o dec.yuv [-v]
 ```
 
+**`--slice-h` — the coding-unit height. Default 16; you rarely need to set it.**
+The encoder picks **16 lines** for every format above 720p, and **8 lines** for
+720p-class heights because 16 would breach the sub-1 ms bar there (A2). A height
+that does not divide by 16 — 1080 above all — is coded at 1088 and cropped on
+output automatically; you pass `-h 1080` and get a 1080-line picture back. The
+value travels in the stream header, so any decoder sizes itself from it.
+
+**Legal values are 8, 16 and 32.** Override the default when you have a reason:
+
+- `--slice-h 8` costs about 10 % of rate at 1.0 bpp and 16 % at 0.5 bpp against
+  the default, and buys latency headroom. The one case that needs it today is
+  1080p50 with a vertical rescale in the decoder's output path, which the config
+  validator refuses at 16 lines.
+- `--slice-h 32` is for **2160p and 4320p only** and buys a further 6.5–12 % of
+  rate. It fits the 1 ms budget with a conversion in the path from 59.94 Hz
+  upward; at 2160p50 it needs the raster-clocked output converter. Below 2160p it
+  breaches the budget on the codec term alone and the validator will say so.
+  Decoder memory scales with it.
+
+See `docs/BITSTREAM.md` §7 and `docs/LATENCY.md`.
+
 Acceptance suite (needs prepared masters and the comparison instruments; see
 `harness/prep_masters.py`, `harness/xs_sweep.py`):
 
diff -ruN '--exclude=*.o' '--exclude=*.yuv' '--exclude=__pycache__' '--exclude=.pytest_cache' '--exclude=work' '--exclude=_xc' '--exclude=repro' '--exclude=harness' '--exclude=delivery' '--exclude=*.log' '--exclude=omc_enc' '--exclude=omc_dec' '--exclude=omc_uc_tool' '--exclude=omc_tf_tool' '--exclude=omc_unblend_tool' '--exclude=test_cap' '--exclude=test_cap_old' '--exclude=test_cap_live' '--exclude=test_cc' '--exclude=test_tf' '--exclude=test_uc' '--exclude=test_unit' '--exclude=test_xsl' ./src/codec.c [machine-path-redacted]/.work/final/omc_v4.9/src/codec.c
--- a/src/codec.c	2026-08-11 23:33:50.656540896 -0400
+++ b/src/codec.c	2026-08-12 22:31:25.666381382 -0400
@@ -17,6 +17,7 @@
     omc_config_t cfg;
     int W, H, Wc, sh, nslices;
     int mid, maxv;
+    int xsl_lim;                 /* boundary-blend cap, codes @10-bit (minor 9) */
     size_t slice_bytes, payload_bytes;
 } ctx_common_t;
 
@@ -102,8 +103,13 @@
 /* banking parameters (normative for the latency bound, see docs/LATENCY.md):
  * prefix sum of emitted bits through slice k never exceeds (k+1)*bits_per_slice
  * + OD_CAP_NUM/OD_CAP_DEN * bits_per_slice. */
-#define OD_CAP_NUM 1
-#define OD_CAP_DEN 2
+/* OD_CAP_PCT = 0 since 2026-08-12: the banking overdraft was half a slice and
+ * cost 0.5 slice periods of the A2 budget.  Measured neutral in quality, exact
+ * CBR untouched, retry counts unchanged, tail-debt signature improved.
+ * Tightening is backward-compatible (BITSTREAM sect 5 is an UPPER bound);
+ * decoders keep the wider tolerance and the per-slice wire cap is unchanged.
+ * There is no knob: the prefix bound is (k+1)*bits_per_slice, full stop. */
+#define OD_CAP_PCT 0
 #define OMC_QUALITY_FLOOR_Q 3 /* stop refining below (Q=3, all steps): bank bits */
 
 struct omc_dec {
@@ -146,9 +152,14 @@
     return cfg->chroma == OMC_CF_422 ? cfg->width / 2 : cfg->width;
 }
 
+static int xsl_lim_for(const omc_config_t *cfg);
+
 static void common_init(ctx_common_t *c, const omc_config_t *cfg)
 {
     c->cfg = *cfg;
+    /* CAP_RULE_REVIEW F1: per-CONTEXT, never a process-wide global -- a
+     * multi-channel server runs contexts at different rates in one process. */
+    c->xsl_lim = xsl_lim_for(cfg);
     c->W = cfg->width;
     c->H = cfg->height;
     c->Wc = omc_chroma_width(cfg);
@@ -343,6 +354,12 @@
      * what an ENCODER writes.  (Experimental builds may still force the
      * decoder with OMC_XSL_FORCE for instrumentation.) */
     if (src[5] >= OMC_MINOR_XSL) {
+        /* Stream-authoritative when the environment is silent.  common_init()
+         * below re-reads OMC_XSL and lets it win -- that is the deliberate
+         * instrumentation path (C1), NOT an accident, and it is why level 7 can
+         * be measured at all.  A widening of OMC_XSL_FORCE was added here on
+         * 2026-08-12 on the mistaken belief that the environment could not
+         * reach the decoder; it could, and the widening was reverted. */
         omc_xsl = 3;
         /* cap is rate-derived; cfg is filled in below, so the
          * decoder pins it in omc_dec_create() instead. */
@@ -497,7 +514,9 @@
     border one-sidedly.  Ship = bitstream minor bump. */
 static int32_t omc_xsl_buf[OMC_NPLANES][8192]; /* sized to validated max width (review C5: 4096 overflowed at legal 8K 4:4:4) */
 static int32_t omc_xsl_prev[OMC_NPLANES][8192]; /* k-1's last row, centered */
+static int32_t omc_xsl_prev14[OMC_NPLANES][8192]; /* and the row before it (XSL 6) */
 static int omc_xsl_live[OMC_NPLANES];
+static int omc_xsl_noedit = 0;  /* test hook, see the level-7 block */
 static int omc_xsl_noretro; /* prev slice refreshed this frame: protect it */
 /* fill the per-plane boundary arrays from the reference frame's slice k-1 */
 int omc_xsl_nodisp = 0;  /* env OMC_XSL_NODISP=1: disable barrier display blend (A/B) */
@@ -516,6 +535,53 @@
  * the two skipped retro edits (by k at its top edge, by k+1 via the
  * noretro gate at its bottom edge; XSL>=3 features).  Both sides derive
  * the condition from fidx8 + refresh config alone. */
+#define OMC_XSL_FULL_AT 4   /* codes @10-bit: excess at which the blend is full */
+
+/* XSL level 6: blend strength from the SEAM ITSELF, continuously.
+ *
+ * Levels 4/5 scale the blend by how empty the slice's detail band is.  That is a
+ * texture proxy, and measured it is backwards for this job: busy slices get
+ * almost no blend, and busy slices are exactly where the seam is worst (city at
+ * 0.5 bpp: unrepaired 19.25 codes, level 3 repairs to 9.51, level 4 only to
+ * 17.00).
+ *
+ * Level 6 measures the thing the blend exists to fix.  At a boundary, compare the
+ * step ACROSS it with the steps either side of it inside the picture:
+ *
+ *      excess = mean|row0 - prev15|  -  (mean|prev15 - prev14| + mean|row1 - row0|)/2
+ *
+ * If the join is no sharper than the picture's own texture there, excess <= 0 and
+ * nothing is done -- which is also what keeps the reconstruction on the quantiser
+ * lattice, so the generation lock survives wherever there was no seam to repair.
+ * Above that it rises CONTINUOUSLY to full strength; there is no threshold and no
+ * cliff at a content transition (the hard-won rule from the band work).
+ *
+ * Per slice boundary, per plane, recomputed every frame -- so a scene cut is
+ * handled by construction, which a once-per-stream decision cannot do.  Both ends
+ * derive it from reconstructions they both hold: no side information, no new
+ * field, no bitstream change. */
+static int xsl_seam_strength(const int32_t *r0, const int32_t *r1,
+                             const int32_t *prev14, const int32_t *prev15,
+                             int pw, int maxv)
+{
+    int64_t across = 0, inside = 0;
+    for (int x = 0; x < pw; x++) {
+        int32_t d = r0[x] - prev15[x];        across += d < 0 ? -d : d;
+        d = prev15[x] - prev14[x];            inside += d < 0 ? -d : d;
+        d = r1[x] - r0[x];                    inside += d < 0 ? -d : d;
+    }
+    if (!pw) return 0;
+    /* excess in 1/2 units to keep the halving exact in integers */
+    int64_t ex2 = 2 * across / pw - inside / pw;
+    if (ex2 <= 0) return 0;
+    /* full strength once the join is one blend-cap worth sharper than the
+     * picture's own texture; linear below that.  The cap scales with depth, so
+     * this does too. */
+    int64_t full = 2 * (int64_t)OMC_XSL_FULL_AT * ((maxv + 1) >> 10);
+    int64_t z = ex2 * 256 / (full > 0 ? full : 1);
+    return z > 256 ? 256 : (int)z;
+}
+
 static void xsl_display_blend(ctx_common_t *c, omc_frame_t *fr, int slice_idx,
                               int fidx8)
 {
@@ -530,7 +596,7 @@
     }
     if (!do_r0 && !do_r15) return;
     int sh = c->sh;
-    int32_t lim = omc_xsl_lim * ((c->maxv + 1) >> 10);
+    int32_t lim = c->xsl_lim * ((c->maxv + 1) >> 10);
     for (int p = 0; p < OMC_NPLANES; p++) {
         int pw = (p == 0 || c->cfg.chroma == OMC_CF_444) ? c->W : c->W / 2;
         if (c->W > 8192) return;
@@ -599,10 +665,65 @@
                               - 2 * ((int32_t)r14[x] - rbias)
                               + ((int32_t)r13[x] - rbias);
             omc_xsl_prev[p][x] = (int32_t)r15[x] - rbias - c->mid;
+            omc_xsl_prev14[p][x] = (int32_t)r14[x] - rbias - c->mid;   /* XSL 6 */
         }
         omc_xsl_live[p] = 1;
     }
 }
+/* ---- the inverse of the level-7 boundary edit, applied to a whole picture.
+ *
+ * A later encoder calls this on its input.  Because every step of the forward
+ * edit added a correction built only from rows it did not touch, running the
+ * two steps backwards with the same arithmetic returns the exact reconstruction
+ * the previous encoder coded -- so it lands back on the quantiser lattice and
+ * can be re-emitted unchanged instead of being smoothed a second time.
+ *
+ * Boundaries are walked from the BOTTOM UP.  The forward pass runs top-down and
+ * slice k's edit writes row 0 of slice k, which is two rows below the row 15
+ * that slice k+1's edit reads -- so the passes do not overlap and either order
+ * works, but bottom-up mirrors the forward order exactly and costs nothing. */
+void omc_xsl_unblend(omc_frame_t *f, const omc_config_t *cfg, int frame_idx)
+{
+    /* The forward edit is SUPPRESSED on refresh barriers, and both sides derive
+     * that from the slice header and config alone (xsl_prep, A5).  The inverse
+     * must make the same decision on the same information or it will "undo" an
+     * edit that never happened -- so the same two rules are repeated here, from
+     * the frame index and refresh period, with nothing else consulted. */
+    int Rr = cfg->refresh_r ? cfg->refresh_r : 8;
+    int fidx8 = frame_idx & 0xff;
+    if (cfg->width > 8192) return;
+    int sh = cfg->slice_h ? cfg->slice_h : 16;
+    int lim = xsl_lim_for(cfg) * ((1 << cfg->bitdepth) >> 10);
+    int hi = (1 << cfg->bitdepth) - 1;
+    int nsl = (cfg->height + sh - 1) / sh;
+    int np = OMC_NPLANES;
+    for (int p = 0; p < np; p++) {
+        int pw = (p == 0) ? cfg->width
+                          : (cfg->chroma == OMC_CF_444 ? cfg->width : cfg->width / 2);
+        if (!f->p[p]) continue;
+        for (int k = nsl - 1; k >= 1; k--) {
+            if ((fidx8 % Rr) == (k % Rr)) continue;            /* slice k refreshed */
+            if ((fidx8 % Rr) == ((k - 1 + Rr) % Rr)) continue; /* noretro gate */
+            int base = k * sh;
+            uint16_t *e15 = f->p[p] + (size_t)(base - 1) * f->stride[p];
+            const uint16_t *e14 = f->p[p] + (size_t)(base - 2) * f->stride[p];
+            uint16_t *e0 = f->p[p] + (size_t)base * f->stride[p];
+            const uint16_t *e1 = f->p[p] + (size_t)(base + 1) * f->stride[p];
+            for (int x = 0; x < pw; x++) {
+                /* undo step 2 first: it used the FINAL e15 and the untouched e1 */
+                int32_t d2 = ((int32_t)e15[x] - (int32_t)e1[x]) / 4;
+                if (d2 > lim) d2 = lim; if (d2 < -lim) d2 = -lim;
+                int32_t v = (int32_t)e0[x] - d2;
+                if (v >= 0 && v <= hi) e0[x] = (uint16_t)v;
+                /* then step 1: it used the RECOVERED e0 and the untouched e14 */
+                int32_t d1 = ((int32_t)e0[x] - (int32_t)e14[x]) / 4;
+                if (d1 > lim) d1 = lim; if (d1 < -lim) d1 = -lim;
+                v = (int32_t)e15[x] - d1;
+                if (v >= 0 && v <= hi) e15[x] = (uint16_t)v;
+            }
+        }
+    }
+}
 int omc_spc = 0;  /* OMC_SPC=K: cap a slice's refinement depth at (previous
     same-frame slice's depth + K) when profile and Q match.  Adjacent slices
     otherwise land 0 vs 12+ refinement steps on similar content (measured,
@@ -680,13 +801,92 @@
 {
     if (getenv("OMC_XSL_LIM")) return atoi(getenv("OMC_XSL_LIM"));
     int64_t px = (int64_t)cfg->width * (cfg->slice_h ? cfg->slice_h : 16);
-    return (4 * (int64_t)cfg->bits_per_slice < 3 * px) ? OMC_XSL_LIM_MINOR9 : 4;
+    /* counts CODED SAMPLES, not luma pixels: 0.75 bpp at 4:2:2 (unchanged) and
+     * 1.125 bpp at 4:4:4, which is the same coarseness.  Eye-decided 2026-08-12. */
+    return (8 * (int64_t)cfg->bits_per_slice
+            < 3 * px * (cfg->chroma == OMC_CF_444 ? 3 : 2))
+           ? OMC_XSL_LIM_MINOR9 : 4;
+}
+
+/* Is the cross-slice boundary reconstruction worth switching on for THIS stream?
+ *
+ * XSL repairs the brightness step at a slice seam, and it costs generation
+ * robustness: it edits the reconstruction by a sub-step amount, which puts the
+ * coefficients off the quantiser lattice and stops the generation lock from
+ * firing (measured: 31 of 72 slices lock without it, 0 of 72 with it).
+ *
+ * Measured across three clips at three rates, the two effects sit at OPPOSITE
+ * ends of the rate range.  Where the seam is large the generation cost is 0.1-1.2
+ * dB; where the seam has already gone the cost is 2.1-4.7 dB and the blend is
+ * over-smoothing rather than repairing (the boundary rows come out SMOOTHER than
+ * the interior).  So the honest switch is not the rate but the thing the feature
+ * exists to fix -- the same principle CAP_RULE_REVIEW F3/F4 reached for the blend
+ * cap, applied to the feature itself.
+ *
+ * This encodes frame 0 once with XSL off and measures, on its own
+ * reconstruction, how much bigger the row-to-row step is AT the slice boundaries
+ * than everywhere else.  Above OMC_XSL_SEAM_ON codes there is a seam worth
+ * repairing; at or below it there is not, and the stream is written without XSL
+ * (minor 7), which any decoder already handles.
+ *
+ * Encoder-side and once per stream.  No new bitstream field: the minor already
+ * carries the decision.  Returns 1 for "use XSL", 0 for "do not". */
+#define OMC_XSL_SEAM_ON 3.0   /* codes @10-bit; BITSTREAM's own "clean" reference */
+
+int omc_xsl_probe_frame(const omc_config_t *cfg, const omc_frame_t *in)
+{
+    int saved = omc_xsl;
+    omc_xsl = 0;                       /* measure the UNREPAIRED seam */
+    omc_config_t c = *cfg;
+    omc_enc_t *e = omc_enc_create(&c);
+    int rc = -1;
+    double excess = 0.0;
+    if (e) {
+        int W = c.width, H = c.height, Wc = omc_chroma_width(&c);
+        size_t words = (size_t)W * H + 2 * (size_t)Wc * H;
+        uint16_t *rec = malloc(words * 2);
+        size_t nsl = (size_t)omc_num_slices(&c);
+        uint8_t *bs = malloc((size_t)c.bits_per_slice / 8 * nsl);
+        if (rec && bs) {
+            omc_frame_t fr = {{rec, rec + (size_t)W * H,
+                               rec + (size_t)W * H + (size_t)Wc * H}, {W, Wc, Wc}};
+            if (omc_enc_frame(e, in, 0, bs, (size_t)c.bits_per_slice / 8 * nsl,
+                              &fr) >= 0) {
+                double bsum = 0, isum = 0; long bn = 0, in_ = 0;
+                for (int r = 1; r < H; r++) {
+                    double acc = 0;
+                    const uint16_t *a = rec + (size_t)(r - 1) * W;
+                    const uint16_t *b = rec + (size_t)r * W;
+                    for (int x = 0; x < W; x++) {
+                        int d = (int)b[x] - (int)a[x];
+                        acc += d < 0 ? -d : d;
+                    }
+                    acc /= W;
+                    if (r % c.slice_h == 0) { bsum += acc; bn++; }
+                    else { isum += acc; in_++; }
+                }
+                if (bn && in_) {
+                    excess = bsum / bn - isum / in_;
+                    /* the cap scales with depth, so the threshold does too */
+                    rc = excess > OMC_XSL_SEAM_ON * (double)((c.bitdepth > 10)
+                          ? (1 << (c.bitdepth - 10)) : 1) ? 1 : 0;
+                }
+            }
+        }
+        free(rec); free(bs);
+        omc_enc_destroy(e);
+    }
+    omc_xsl = saved;
+    if (getenv("OMC_XSL_PROBE_DEBUG"))
+        fprintf(stderr, "XSLPROBE seam=%.3f decision=%d\n", excess, rc);
+    return rc;
 }
 
 omc_enc_t *omc_enc_create(const omc_config_t *cfg)
 {
     omc_global_init(); /* tables allocated here, before the baseline */
     if (omc_xsl) omc_xsl_lim = xsl_lim_for(cfg);
+    { const char *ne = getenv("OMC_XSL_NOEDIT"); omc_xsl_noedit = ne && atoi(ne); }
     size_t heap_base = 0;
     if (getenv("OMC_ENC_FOOTPRINT")) {
         struct mallinfo2 mi0 = mallinfo2();
@@ -1411,6 +1611,10 @@
     int sh = c->sh;
     int bias = (omc_ref_unclipped && to_ref) ? OMC_REF_BIAS : 0;
     int32_t hi = bias ? c->maxv + 2 * OMC_REF_BIAS : c->maxv;
+    if (getenv("OMC_DEBUG_L7") && slice_idx == 1)
+        fprintf(stderr, "L7 state: omc_xsl=%d live=%d,%d,%d noretro=%d to_ref=%d\n",
+                omc_xsl, omc_xsl_live[0], omc_xsl_live[1], omc_xsl_live[2],
+                omc_xsl_noretro, to_ref);
     for (int p = 0; p < OMC_NPLANES; p++) {
         int pw = plane_width(c, p);
         omc_dwt_d1m = omc_xsl_live[p] ? omc_xsl_buf[p] : 0;
@@ -1426,8 +1630,9 @@
          * row 1, capped at +-XSL2_LIM codes so the move stays inside the
          * coded information's uncertainty.  Same arithmetic both sides
          * (in-loop, causal); slice 0 untouched. */
-        if (omc_xsl >= 2 && omc_xsl_live[p]) {
-            int32_t lim = omc_xsl_lim * ((c->maxv + 1) >> 10);
+        if (omc_xsl == 7) { /* level 7 does both edits at the deferred site */ }
+        else if (omc_xsl >= 2 && omc_xsl_live[p]) {
+            int32_t lim = c->xsl_lim * ((c->maxv + 1) >> 10);
             /* Blend strength scales CONTINUOUSLY with how empty this
              * slice's coded vertical-detail band is: the boundary noise
              * ridge exists exactly when detail was zeroed (measured: fixed
@@ -1443,6 +1648,9 @@
             if (omc_xsl < 4) zq8 = 256;   /* XSL=3: fixed strength */
             int32_t *r0 = sbuf[p];
             const int32_t *r1 = sbuf[p] + (size_t)pw;
+            if (omc_xsl >= 6)
+                zq8 = xsl_seam_strength(r0, r1, omc_xsl_prev14[p],
+                                        omc_xsl_prev[p], pw, c->maxv);
             int32_t *r15 = sbuf[p] + (size_t)(sh - 1) * pw;
             const int32_t *r13 = sbuf[p] + (size_t)(sh - 3) * pw;
             const int32_t *r14 = sbuf[p] + (size_t)(sh - 2) * pw;
@@ -1491,8 +1699,57 @@
          * unedited row on both sides, so the loops stay in lockstep.  The
          * callers refresh their recon/display/ref copies of this one row
          * (see the three sync sites). */
-        if (omc_xsl >= 3 && omc_xsl_live[p] && slice_idx > 0 && !omc_xsl_noretro) {
-            int32_t lim = omc_xsl_lim * ((c->maxv + 1) >> 10);
+        /* ---- XSL level 7: the boundary edit as a REVERSIBLE lifting cascade.
+         *
+         * The level 2/3 blends move a row toward a target computed from its own
+         * neighbours, and each of the two rows uses the other.  That is mutual,
+         * and "move toward a target" discards what the row was, so no later
+         * encoder can undo it -- which is why re-encoding piles blend on blend.
+         *
+         * A lifting step is different: it adds a correction computed ONLY from
+         * values it does not touch, so subtracting the same correction returns
+         * the original exactly.  Two of them in a fixed order edit both rows and
+         * stay invertible:
+         *
+         *   step 1   row15 += clamp((row0  - row14) / 4)      (row15 not used)
+         *   step 2   row0  += clamp((row15' - row1 ) / 4)      (row0  not used)
+         *
+         * and the inverse is the same two, backwards, with the same arithmetic:
+         *
+         *   row0  -= clamp((row15' - row1 ) / 4)
+         *   row15 -= clamp((row0   - row14) / 4)
+         *
+         * omc_xsl_unblend() below applies that inverse to a whole picture, which
+         * is what lets a later encoder recover the reconstruction its
+         * predecessor coded and re-emit it unchanged. */
+        /* OMC_XSL_NOEDIT=1: keep every other level-7 behaviour (including the
+         * cross-slice wavelet term, which is what makes the reconstruction what
+         * it is) and skip ONLY the boundary edit.  This is the ground truth the
+         * inverse must reproduce; decoding at level 0 is NOT, because level 0
+         * also drops the wavelet term and changes the whole slice. */
+        if (omc_xsl == 7 && omc_xsl_live[p] && slice_idx > 0 && !omc_xsl_noretro
+            && !omc_xsl_noedit) {
+            int32_t lim = c->xsl_lim * ((c->maxv + 1) >> 10);
+            int base = slice_idx * sh;
+            uint16_t *e15 = out->p[p] + (size_t)(base - 1) * out->stride[p];
+            const uint16_t *e14 = out->p[p] + (size_t)(base - 2) * out->stride[p];
+            uint16_t *e0 = out->p[p] + (size_t)base * out->stride[p];
+            const uint16_t *e1 = out->p[p] + (size_t)(base + 1) * out->stride[p];
+            if (getenv("OMC_DEBUG_L7"))
+                fprintf(stderr, "L7 fire p%d slice %d lim %d\n", p, slice_idx, lim);
+            for (int x = 0; x < pw; x++) {
+                int32_t d1 = ((int32_t)e0[x] - (int32_t)e14[x]) / 4;
+                if (d1 > lim) d1 = lim; if (d1 < -lim) d1 = -lim;
+                int32_t v = (int32_t)e15[x] + d1;
+                if (v >= 0 && v <= hi) e15[x] = (uint16_t)v;   /* skip at the rails */
+                int32_t d2 = ((int32_t)e15[x] - (int32_t)e1[x]) / 4;
+                if (d2 > lim) d2 = lim; if (d2 < -lim) d2 = -lim;
+                v = (int32_t)e0[x] + d2;
+                if (v >= 0 && v <= hi) e0[x] = (uint16_t)v;
+            }
+        }
+        if (omc_xsl >= 3 && omc_xsl != 7 && omc_xsl_live[p] && slice_idx > 0 && !omc_xsl_noretro) {
+            int32_t lim = c->xsl_lim * ((c->maxv + 1) >> 10);
             int base = slice_idx * sh;
             uint16_t *e15 = out->p[p] + (size_t)(base - 1) * out->stride[p];
             const uint16_t *e14 = out->p[p] + (size_t)(base - 2) * out->stride[p];
@@ -1505,6 +1762,19 @@
             int zq8b = (int)((nz2 << 8) / (nt2 ? nt2 : 1));
             zq8b = (zq8b * zq8b) >> 8;
             if (omc_xsl < 4) zq8b = 256;
+            if (omc_xsl >= 6) {
+                int64_t across = 0, inside = 0;
+                for (int x = 0; x < pw; x++) {
+                    int32_t d = (int32_t)e0[x] - (int32_t)e15[x];
+                    across += d < 0 ? -d : d;
+                    d = (int32_t)e15[x] - (int32_t)e14[x];
+                    inside += d < 0 ? -d : d;
+                }
+                int64_t ex2 = 2 * across / pw - 2 * (inside / pw);
+                int64_t full = 2 * (int64_t)OMC_XSL_FULL_AT * ((c->maxv + 1) >> 10);
+                int64_t z = ex2 <= 0 ? 0 : ex2 * 256 / (full > 0 ? full : 1);
+                zq8b = z > 256 ? 256 : (int)z;
+            }
             for (int x = 0; x < pw; x++) {
                 int32_t tgt = ((int32_t)e14[x] + (int32_t)e0[x]) >> 1;
                 int32_t dchg = ((tgt - (int32_t)e15[x]) / 2 * zq8b) >> 8;
@@ -1756,10 +2026,10 @@
     /* ---- causal bit banking: budget for this slice ---- */
     if (slice_idx == 0) e->spent_bits = 0;
     int64_t B = (int64_t)c->cfg.bits_per_slice;
-    int64_t od_cap = B * OD_CAP_NUM / OD_CAP_DEN;
+    /* no banking overdraft (see OD_CAP_PCT above) */
     int64_t F = B * c->nslices;
     int64_t min_slice = (OMC_SLICE_HDR_BYTES + 32) * 8;
-    int64_t avail_prefix = (int64_t)slice_idx * B + B + od_cap - e->spent_bits;
+    int64_t avail_prefix = (int64_t)slice_idx * B + B - e->spent_bits;
     int64_t reserve = (int64_t)(c->nslices - 1 - slice_idx) * min_slice;
     int64_t avail_frame = F - e->spent_bits - reserve;
     int64_t budget_wire = avail_prefix < avail_frame ? avail_prefix : avail_frame;
@@ -3441,6 +3711,7 @@
 {
     omc_global_init();
     if (omc_xsl) omc_xsl_lim = xsl_lim_for(cfg);
+    { const char *ne = getenv("OMC_XSL_NOEDIT"); omc_xsl_noedit = ne && atoi(ne); }
     /* The STREAM is authoritative for the in-loop filter, not the environment.
      * omc_global_init() seeds omc_tf_mode from OMC_TF because that is how an
      * ENCODER is asked for the filter; a decoder must instead take what the
diff -ruN '--exclude=*.o' '--exclude=*.yuv' '--exclude=__pycache__' '--exclude=.pytest_cache' '--exclude=work' '--exclude=_xc' '--exclude=repro' '--exclude=harness' '--exclude=delivery' '--exclude=*.log' '--exclude=omc_enc' '--exclude=omc_dec' '--exclude=omc_uc_tool' '--exclude=omc_tf_tool' '--exclude=omc_unblend_tool' '--exclude=test_cap' '--exclude=test_cap_old' '--exclude=test_cap_live' '--exclude=test_cc' '--exclude=test_tf' '--exclude=test_uc' '--exclude=test_unit' '--exclude=test_xsl' ./src/config.c [machine-path-redacted]/.work/final/omc_v4.9/src/config.c
--- a/src/config.c	2026-08-11 23:33:50.656540896 -0400
+++ b/src/config.c	2026-08-12 13:32:57.595091132 -0400
@@ -33,9 +33,10 @@
         FAIL("width %u exceeds the validated maximum 8192", cfg->width);
 
     int sh = cfg->slice_h;
-    if (sh == 0) sh = (cfg->height <= 720) ? 8 : (cfg->height % 16 == 0) ? 16 : 8; /* CLI auto rule (720p-class -> 8, A2) */
-    if (sh != 8 && sh != 16)
-        FAIL("slice_h must be 8, 16 or 0 (auto); got %u", cfg->slice_h);
+    if (sh == 0) sh = (cfg->height <= 720) ? 8 : 16; /* default 16; 720p-class -> 8 (A2) */
+    if (sh != 8 && sh != 16 && sh != 32)
+        FAIL("slice_h must be 8, 16, 32 or 0 (auto, = 16 above 720p and 8 at "
+             "720p-class); got %u", cfg->slice_h);
     if (cfg->height == 0 || cfg->height % sh)
         FAIL("height %u must be a nonzero multiple of slice_h %d "
              "(interlaced 1080i fields use the 4.2 padding convention, "
@@ -180,15 +181,21 @@
         double frame_ms = 1000.0 * (double)cfg->fps_den / (double)cfg->fps_num;
         double line_ms = frame_ms / (double)cfg->height;
         double slice_ms = frame_ms / (double)nsl;
+        /* the decoder's output stage decides what the rescaler's reach costs;
+         * see omc1.h OMC_OUT_RASTER / OMC_OUT_SLICE_BATCHED */
         int periods = (reach + sh - 1) / sh;
-        double total = sh * line_ms + slice_ms + 0.5 * slice_ms + 2 * line_ms
-                       + periods * slice_ms;
+        double conv = cfg->uc_out_batched ? periods * slice_ms
+                                          : (reach ? (reach + 1) * line_ms : 0.0);
+        /* no banking overdraft term since 2026-08-12: OD_CAP_PCT = 0 */
+        double total = sh * line_ms + slice_ms + 2 * line_ms + conv;
         if (total >= 1.0)
             FAIL("uc_ratio %u at %ux%u@%u/%u would take %.3f ms total "
-                 "(%d extra slice period(s) for a %d-source-row reach at "
-                 "slice_h %d); A2 requires < 1 ms",
+                 "(%d-source-row reach at slice_h %d, charged as %s); "
+                 "A2 requires < 1 ms",
                  cfg->uc_ratio, cfg->width, cfg->height, cfg->fps_num,
-                 cfg->fps_den, total, periods, reach, sh);
+                 cfg->fps_den, total, reach, sh,
+                 cfg->uc_out_batched ? "whole slice periods (slice-batched "
+                 "output stage)" : "lines (raster-clocked output stage)");
     }
 
     /* --- decode-side stream version --- */
@@ -218,7 +225,7 @@
     frame_ms = 1000.0 * (double)cfg->fps_den / (double)cfg->fps_num;
     line_ms = frame_ms / (double)cfg->height;
     slice_ms = frame_ms / (double)nsl;
-    total = sh * line_ms + slice_ms + 0.5 * slice_ms + 2 * line_ms
+    total = sh * line_ms + slice_ms + 2 * line_ms
             + per * slice_ms;
     if (total_ms) *total_ms = total;
     if (periods) *periods = per;
diff -ruN '--exclude=*.o' '--exclude=*.yuv' '--exclude=__pycache__' '--exclude=.pytest_cache' '--exclude=work' '--exclude=_xc' '--exclude=repro' '--exclude=harness' '--exclude=delivery' '--exclude=*.log' '--exclude=omc_enc' '--exclude=omc_dec' '--exclude=omc_uc_tool' '--exclude=omc_tf_tool' '--exclude=omc_unblend_tool' '--exclude=test_cap' '--exclude=test_cap_old' '--exclude=test_cap_live' '--exclude=test_cc' '--exclude=test_tf' '--exclude=test_uc' '--exclude=test_unit' '--exclude=test_xsl' ./src/upconv.c [machine-path-redacted]/.work/final/omc_v4.9/src/upconv.c
--- a/src/upconv.c	2026-08-11 23:33:50.656540896 -0400
+++ b/src/upconv.c	2026-08-12 18:19:06.040120952 -0400
@@ -28,6 +28,7 @@
 #include <stdlib.h>
 #include <string.h>
 
+#include "omc1.h"
 #include "omc_uc.h"
 
 /* ------------------------------------------------------------------ kernel
@@ -580,11 +581,21 @@
  * phase in *php.  When the ratio's parity does not admit an exact phase the
  * function falls back to the historical corner-aligned mapping and returns 0,
  * so the caller can report the ratio as un-aligned rather than pretend. */
-static int uc_map_pos(int r, int num, int den, int *ip, int *hph)
+static int uc_map_pos(int r, int num, int den, int *ip, int *hph, int siting)
 {
     int64_t den2 = 2 * (int64_t)den;
-    int64_t N = (int64_t)(2 * r + 1) * num - den;   /* units of 1/(2*den) */
-    int64_t i = N / den2, h = N - i * den2;
+    int64_t N, i, h;
+    if (siting == OMC_SITE_COSITED) {
+        /* output sample 0 on source sample 0 -- chroma siting.  Exactly the
+         * mapping this scaler had before centre alignment, and the only one
+         * that keeps 4:2:2 chroma on the luma it belongs to. */
+        int64_t pos = (int64_t)r * num;
+        *ip = (int)(pos / den);
+        *hph = (int)(2 * (pos % den));
+        return 1;
+    }
+    N = (int64_t)(2 * r + 1) * num - den;           /* units of 1/(2*den) */
+    i = N / den2; h = N - i * den2;
     if (h < 0) { h += den2; i -= 1; }               /* floor, not truncate */
     *ip = (int)i; *hph = (int)h;                    /* h in [0, 2*den)     */
     return 1;
@@ -989,6 +1000,14 @@
 int omc_uc_scale_plane_ws(const omc_uc_t *u, const uint16_t *src, int ss, int sw, int sh,
                           uint16_t *dst, int ds, int dw, int dh, void *ws, size_t wsz)
 {
+    return omc_uc_scale_plane_ws_sited(u, src, ss, sw, sh, dst, ds, dw, dh,
+                                       ws, wsz, OMC_SITE_CENTRE);
+}
+
+int omc_uc_scale_plane_ws_sited(const omc_uc_t *u, const uint16_t *src, int ss,
+                                int sw, int sh, uint16_t *dst, int ds, int dw,
+                                int dh, void *ws, size_t wsz, int siting)
+{
     int gv, gh, denv, denh, numv, numh, r, j, t;
     int ntv, nth, ntmax;
     int32_t *lines = NULL, *mid = NULL, *row = NULL, *cols = NULL, *orow = NULL;
@@ -1052,7 +1071,7 @@
         int32_t hcv[OMC_UC_MAXTAPS];
         const int32_t *covv = NULL;
         int i, hp, ph;
-        uc_map_pos(r, numv, denv, &i, &hp);
+        uc_map_pos(r, numv, denv, &i, &hp, siting);
         ph = hp >> 1;
         if (hp & 1) { uc_halfphase(&bkv, ph, hcv); covv = hcv; }
         for (t = 0; t < ntv; t++) {
@@ -1089,7 +1108,7 @@
         int32_t hch[OMC_UC_MAXTAPS];
         const int32_t *covh = NULL;
         int i, hp, ph;
-        uc_map_pos(j, numh, denh, &i, &hp);
+        uc_map_pos(j, numh, denh, &i, &hp, siting);
         ph = hp >> 1;
         if (hp & 1) { uc_halfphase(&bkh, ph, hch); covh = hch; }
         for (t = 0; t < nth; t++) {
@@ -1110,13 +1129,22 @@
 int omc_uc_scale_plane(const omc_uc_t *u, const uint16_t *src, int ss, int sw, int sh,
                        uint16_t *dst, int ds, int dw, int dh)
 {
+    return omc_uc_scale_plane_sited(u, src, ss, sw, sh, dst, ds, dw, dh,
+                                    OMC_SITE_CENTRE);
+}
+
+int omc_uc_scale_plane_sited(const omc_uc_t *u, const uint16_t *src, int ss,
+                             int sw, int sh, uint16_t *dst, int ds, int dw,
+                             int dh, int siting)
+{
     size_t n = omc_uc_scale_scratch_bytes(sw, sh, dw, dh);
     void *ws;
     int rc;
     if (!n) return -1;
     ws = malloc(n);
     if (!ws) return -1;
-    rc = omc_uc_scale_plane_ws(u, src, ss, sw, sh, dst, ds, dw, dh, ws, n);
+    rc = omc_uc_scale_plane_ws_sited(u, src, ss, sw, sh, dst, ds, dw, dh, ws, n,
+                                     siting);
     free(ws);
     return rc;
 }
@@ -1142,6 +1170,14 @@
 int omc_uc_scale_latency(int sw, int sh, int dw, int dh, int slice_h,
                          int fps_num, int fps_den, double *total_ms, int *periods)
 {
+    return omc_uc_scale_latency_ex(sw, sh, dw, dh, slice_h, fps_num, fps_den,
+                                   OMC_OUT_RASTER, total_ms, periods);
+}
+
+int omc_uc_scale_latency_ex(int sw, int sh, int dw, int dh, int slice_h,
+                            int fps_num, int fps_den, int batched,
+                            double *total_ms, int *periods)
+{
     int gv = uc_gcd(sh, dh), numv = sh / gv, denv = dh / gv;
     int gh = uc_gcd(sw, dw), numh = sw / gh, denh = dw / gh;
     int reach, per, nsl;
@@ -1161,9 +1197,35 @@
     frame_ms = 1000.0 * (double)fps_den / (double)fps_num;
     line_ms = frame_ms / (double)sh;
     slice_ms = frame_ms / (double)nsl;
-    per = (reach + slice_h - 1) / slice_h;
-    total = slice_h * line_ms + slice_ms + 0.5 * slice_ms + 2 * line_ms
-            + per * slice_ms;
+    /* RASTER-CLOCKED OUTPUT STAGE (the default; omc_uc_scale_latency_ex() takes
+     * the slice-batched figure).  The converter needs `reach` source rows beyond
+     * the row it is producing.  When rows go downstream as they become final and
+     * the output is clocked at the destination raster rate, the requirement is
+     *
+     *      T >= reach * line_time
+     *
+     * independent of slice height -- output for source row r is producible once
+     * slice floor((r+reach)/sh) has landed and is due at r*line + T, and
+     * maximising over r puts the worst case at r = m*sh - reach.  Verified by
+     * row-by-row simulation over every supported (format, slice height, reach),
+     * not by algebra alone (tests/test_uc.c).
+     *
+     * PLUS ONE LINE for OMC_XSL level 3: slice k rewrites the LAST ROW of slice
+     * k-1 when it reconstructs, so that row is not final until one slice period
+     * later.  It sits at the end of its slice and therefore already had sh-1
+     * lines of slack, so the net cost is exactly one line -- not the whole slice
+     * period a strictly row-streaming sink would otherwise have to assume.
+     *
+     * The price is an output buffer of the filter aperture plus one slice
+     * (<= 68 rows at the steepest supported ratio) and a free-running output
+     * clock; a genlocked facility has both.  An integration that cannot hand
+     * rows over this way must declare cfg.uc_out_batched and take the older,
+     * higher figure. */
+    per = (reach + slice_h - 1) / slice_h;      /* slice-batched charge */
+    total = slice_h * line_ms + slice_ms + 2 * line_ms
+            + (batched ? per * slice_ms
+                       : (reach ? (reach + 1) * line_ms : 0.0));
+    if (!batched) per = 0;                      /* the charge is in LINES now */
     if (total_ms) *total_ms = total;
     if (periods) *periods = per;
     /* Below B4's floor is a FORMAT refusal, and it outranks the latency verdict
diff -ruN '--exclude=*.o' '--exclude=*.yuv' '--exclude=__pycache__' '--exclude=.pytest_cache' '--exclude=work' '--exclude=_xc' '--exclude=repro' '--exclude=harness' '--exclude=delivery' '--exclude=*.log' '--exclude=omc_enc' '--exclude=omc_dec' '--exclude=omc_uc_tool' '--exclude=omc_tf_tool' '--exclude=omc_unblend_tool' '--exclude=test_cap' '--exclude=test_cap_old' '--exclude=test_cap_live' '--exclude=test_cc' '--exclude=test_tf' '--exclude=test_uc' '--exclude=test_unit' '--exclude=test_xsl' ./tests/test_cap.c [machine-path-redacted]/.work/final/omc_v4.9/tests/test_cap.c
--- a/tests/test_cap.c	2026-08-12 00:35:34.701671930 -0400
+++ b/tests/test_cap.c	2026-08-12 04:29:36.367988740 -0400
@@ -55,6 +55,20 @@
     }
 }
 
+/* Bit depth was the last open half of this rule and it is CLOSED (2026-08-12,
+ * measured, no change needed).  On identical content coded at both depths --
+ * cow, native 12-bit, heavy film grain -- the seam excess as a fraction of full
+ * scale (x1000) came out:
+ *
+ *      depth    0.5 bpp   0.8 bpp   1.0 bpp
+ *      10-bit    +1.01     +0.60     +0.40
+ *      12-bit    +0.62     +0.17     +0.05
+ *
+ * 12-bit is BETTER behaved than 10-bit at the same bitrate, not worse, and cap 4
+ * against cap 8 barely registers at either depth.  The cap itself already scales
+ * with depth in the reconstruction (cap * ((maxv+1)>>10)), so ±4 at 10-bit and
+ * ±16 at 12-bit are the same fraction of full scale.  Nothing to fix. */
+
 int main(void)
 {
     /* 0.5 bpp and 1.5 bpp at this geometry: the rule picks 8 and 4 */
diff -ruN '--exclude=*.o' '--exclude=*.yuv' '--exclude=__pycache__' '--exclude=.pytest_cache' '--exclude=work' '--exclude=_xc' '--exclude=repro' '--exclude=harness' '--exclude=delivery' '--exclude=*.log' '--exclude=omc_enc' '--exclude=omc_dec' '--exclude=omc_uc_tool' '--exclude=omc_tf_tool' '--exclude=omc_unblend_tool' '--exclude=test_cap' '--exclude=test_cap_old' '--exclude=test_cap_live' '--exclude=test_cc' '--exclude=test_tf' '--exclude=test_uc' '--exclude=test_unit' '--exclude=test_xsl' ./tests/test_cc.c [machine-path-redacted]/.work/final/omc_v4.9/tests/test_cc.c
--- a/tests/test_cc.c	2026-08-11 23:33:50.656234494 -0400
+++ b/tests/test_cc.c	2026-08-12 18:19:06.052121011 -0400
@@ -636,8 +636,8 @@
         int w_noise, w_smooth;
         u.depth = 10; u.direction = 1;
         for (i = 0; i < Wc * H; i++) c[i] = (uint16_t)(64 + rnd() % 897);
-        omc_uc_scale_plane(&u, c, Wc, Wc, H, f, W, W, H);
-        omc_uc_scale_plane(&u, f, W, W, H, b, Wc, Wc, H);
+        omc_uc_scale_plane_sited(&u, c, Wc, Wc, H, f, W, W, H, OMC_SITE_COSITED);
+        omc_uc_scale_plane_sited(&u, f, W, W, H, b, Wc, Wc, H, OMC_SITE_COSITED);
         tot = 0; worst = 0;
         for (i = 0; i < Wc * H; i++) {
             int d = abs((int)b[i] - (int)c[i]);
@@ -650,8 +650,8 @@
             double v = 512 + 300.0 * sin(x / 9.0) * cos(y / 7.0);
             c[i] = (uint16_t)v;
         }
-        omc_uc_scale_plane(&u, c, Wc, Wc, H, f, W, W, H);
-        omc_uc_scale_plane(&u, f, W, W, H, b, Wc, Wc, H);
+        omc_uc_scale_plane_sited(&u, c, Wc, Wc, H, f, W, W, H, OMC_SITE_COSITED);
+        omc_uc_scale_plane_sited(&u, f, W, W, H, b, Wc, Wc, H, OMC_SITE_COSITED);
         tot = 0; worst = 0;
         for (i = 0; i < Wc * H; i++) {
             int d = abs((int)b[i] - (int)c[i]);
diff -ruN '--exclude=*.o' '--exclude=*.yuv' '--exclude=__pycache__' '--exclude=.pytest_cache' '--exclude=work' '--exclude=_xc' '--exclude=repro' '--exclude=harness' '--exclude=delivery' '--exclude=*.log' '--exclude=omc_enc' '--exclude=omc_dec' '--exclude=omc_uc_tool' '--exclude=omc_tf_tool' '--exclude=omc_unblend_tool' '--exclude=test_cap' '--exclude=test_cap_old' '--exclude=test_cap_live' '--exclude=test_cc' '--exclude=test_tf' '--exclude=test_uc' '--exclude=test_unit' '--exclude=test_xsl' ./tests/test_uc.c [machine-path-redacted]/.work/final/omc_v4.9/tests/test_uc.c
--- a/tests/test_uc.c	2026-08-11 23:33:50.656234494 -0400
+++ b/tests/test_uc.c	2026-08-12 20:04:26.500963965 -0400
@@ -54,12 +54,137 @@
         }
 }
 
+/* G21: the raster-clocked output stage, proved by ROW-BY-ROW SIMULATION rather
+ * than by re-deriving the algebra that produced the figure.
+ *
+ * The claim under test: when the decoder hands rows to the rescaler as they
+ * become final and the output is clocked at the destination raster rate, the
+ * conversion costs `reach` lines (plus one for OMC_XSL's deferred last row) --
+ * NOT ceil(reach/slice_h) whole slice periods, which is what the model charged
+ * before 2026-08-12.
+ *
+ * The simulation walks every output row, works out which source row it needs,
+ * when that row is final (honouring both the slice schedule AND the XSL rewrite
+ * of the previous slice's last row), and when it is due.  It asserts that the
+ * worst requirement never exceeds the bound, over every supported format, slice
+ * height and conversion ratio.  It also asserts the batched form still returns
+ * the older, higher figure, so an integration that cannot meet the contract is
+ * not silently handed the better number. */
+static int sim_out_stage(void)
+{
+    static const int HS[] = { 720, 1080, 2160, 4320 };
+    static const double FPS[] = { 50.0, 59.94, 60.0, 100.0, 120.0 };
+    static const int SHS[] = { 8, 16, 32 };
+    int bad = 0, cases = 0, tight = 0;
+    for (unsigned h = 0; h < 4; h++)
+      for (unsigned f = 0; f < 5; f++)
+        for (unsigned k = 0; k < 3; k++)
+          for (unsigned d = 0; d < 4; d++) {
+            int disp = HS[h], dst = HS[d], sh = SHS[k];
+            if (dst == disp) continue;
+            int g = 0, a = disp, b = dst;
+            while (b) { int t = a % b; a = b; b = t; }
+            g = a;
+            int num = disp / g, den = dst / g;
+            if (!omc_uc_scale_taps(num, den)) continue;
+            int reach = omc_uc_scale_reach_r(num, den);
+            int coded = disp % sh ? (disp / sh + 1) * sh : disp;
+            int nsl = coded / sh;
+            double frame = 1000.0 / FPS[f];
+            double line = frame / disp, sp = frame / nsl;
+            double worst = 0.0;
+            for (int r = 0; r < dst; r++) {
+                long long i = ((long long)r * num) / den;
+                int srow = (int)(i + reach);
+                if (srow > disp - 1) srow = disp - 1;
+                int j = srow / sh;
+                /* XSL 3: the last row of a slice is rewritten by the next one */
+                if ((srow % sh) == sh - 1 && j + 1 < nsl) j++;
+                double avail = sh * line + sp + 2 * line + j * sp;
+                double due = r * (frame / dst);
+                double need = avail - due;
+                if (need > worst) worst = need;
+            }
+            double base = sh * line + sp + 2 * line;
+            double bound = base + (reach + 1) * line;
+            cases++;
+            if (worst > bound + 1e-9) bad++;
+            if (worst > bound - line * 0.5) tight++;
+          }
+    printf("   output-stage simulation: %d (format, slice height, ratio) cases, "
+           "%d over the bound, %d within half a line of it\n", cases, bad, tight);
+    return bad;
+}
+
 int main(void)
 {
     const int W = 96, H = 64;
     omc_uc_t uc;
     uc.direction = 1;
 
+    {   /* G22: the two sample-siting conventions, pinned.
+         *
+         * This exists because the distinction was made once, written down in a
+         * session ledger, and then lost -- the rational path was re-centred for
+         * picture resizing and the 4:2:2 chroma detour was re-centred with it,
+         * which put the colour a quarter sample off its luma and doubled the
+         * round-trip loss.  A comment did not prevent that.  A gate does.
+         *
+         * Resample a ramp and read the offset straight off the values:
+         *   co-sited  -> output 2k lands exactly on source k
+         *   centred   -> output 2k lands a quarter sample early, 2k+1 a quarter late
+         * If either drifts, or if one convention is ever quietly made to behave
+         * like the other, this fails and says which. */
+        enum { GW = 64, GH = 32, GDW = 128 };
+        static uint16_t gs[GW * GH], gc[GDW * GH], gp[GDW * GH];
+        omc_uc_t gu; int gx, gy, okg = 1;
+        double pc, pp, pc1;
+        gu.depth = 10; gu.direction = 0;
+        for (gy = 0; gy < GH; gy++)
+            for (gx = 0; gx < GW; gx++)
+                gs[gy * GW + gx] = (uint16_t)(100 + 8 * gx);
+        omc_uc_scale_plane_sited(&gu, gs, GW, GW, GH, gc, GDW, GDW, GH,
+                                 OMC_SITE_CENTRE);
+        omc_uc_scale_plane_sited(&gu, gs, GW, GW, GH, gp, GDW, GDW, GH,
+                                 OMC_SITE_COSITED);
+        gy = GH / 2;
+        pp  = (gp[gy * GDW + 40] - 100.0) / 8.0;   /* co-sited, wants 20.00 */
+        pc  = (gc[gy * GDW + 40] - 100.0) / 8.0;   /* centred,  wants 19.75 */
+        pc1 = (gc[gy * GDW + 41] - 100.0) / 8.0;   /* centred,  wants 20.25 */
+        if (pp < 19.99 || pp > 20.01) okg = 0;
+        if (pc < 19.74 || pc > 19.76) okg = 0;
+        if (pc1 < 20.24 || pc1 > 20.26) okg = 0;
+        printf("   siting: co-sited out[40] -> source %.3f (20.000); "
+               "centred out[40] -> %.3f (19.750), out[41] -> %.3f (20.250)\n",
+               pp, pc, pc1);
+        okg ? ok("G22 sample siting: co-sited puts output 2k exactly on source k "
+                 "(what 4:2:2 chroma needs, and what keeps a shrink-and-expand "
+                 "landing back on the original samples); centred puts it half a "
+                 "source sample later (what resizing a picture needs).  Neither "
+                 "convention may drift into the other")
+            : bad("G22 sample siting: a convention moved");
+    }
+
+    {   /* G21 -- see above */
+        double t_raster = 0, t_batched = 0;
+        int p1 = 0, p2 = 0;
+        int bad = sim_out_stage();
+        omc_uc_scale_latency(3840, 2160, 1920, 1080, 32, 50, 1, &t_raster, &p1);
+        omc_uc_scale_latency_ex(3840, 2160, 1920, 1080, 32, 50, 1,
+                                OMC_OUT_SLICE_BATCHED, &t_batched, &p2);
+        printf("   2160p50 -> 1080p50 at slice_h 32: raster %.4f ms (%d periods), "
+               "slice-batched %.4f ms (%d periods)\n", t_raster, p1, t_batched, p2);
+        if (bad || t_raster >= t_batched || p1 != 0 || p2 <= 0) {
+            printf("FAIL: raster-clocked output stage\n");
+            fails++;
+        } else
+            ok("G21 raster-clocked output stage: simulated row by row over every "
+               "format, slice height and ratio, the conversion never costs more "
+               "than reach+1 lines -- and the slice-batched contract still "
+               "reports its own, higher figure so an integration that cannot "
+               "stream rows is not handed the better number");
+    }
+
     {   /* The reach must be bounded from the CONSTANTS, not from a picture:
          * the direction search only exercises its extreme taps when an extreme
          * candidate wins, so benign content under-reports it (this test used to
diff -ruN '--exclude=*.o' '--exclude=*.yuv' '--exclude=__pycache__' '--exclude=.pytest_cache' '--exclude=work' '--exclude=_xc' '--exclude=repro' '--exclude=harness' '--exclude=delivery' '--exclude=*.log' '--exclude=omc_enc' '--exclude=omc_dec' '--exclude=omc_uc_tool' '--exclude=omc_tf_tool' '--exclude=omc_unblend_tool' '--exclude=test_cap' '--exclude=test_cap_old' '--exclude=test_cap_live' '--exclude=test_cc' '--exclude=test_tf' '--exclude=test_uc' '--exclude=test_unit' '--exclude=test_xsl' ./tests/test_unit.c [machine-path-redacted]/.work/final/omc_v4.9/tests/test_unit.c
--- a/tests/test_unit.c	2026-08-11 23:33:50.655830750 -0400
+++ b/tests/test_unit.c	2026-08-12 03:22:45.984763556 -0400
@@ -234,10 +234,21 @@
     omc_config_t cfg;
     char err[160];
     memset(&cfg, 0, sizeof(cfg));
-    cfg.width = 1920; cfg.height = 1080; cfg.bitdepth = 10;
+    /* slice_h now DEFAULTS TO 16 (720p-class excepted, A2), so a 1080-row
+     * CODED raster is no longer a legal geometry on its own: 1080 does not
+     * divide by 16.  A caller with a 1080 picture codes 1088 rows and sets
+     * display_height, exactly as tools/omc_enc.c does (BITSTREAM sec 8
+     * pad-and-crop).  Both halves of that contract are asserted here. */
+    cfg.width = 1920; cfg.height = 1088; cfg.display_height = 1080;
+    cfg.bitdepth = 10;
     cfg.chroma = OMC_CF_422; cfg.slice_h = 0; cfg.fps_num = 50; cfg.fps_den = 1;
     cfg.bits_per_slice = 30720;
     int ok = omc_validate_config(&cfg, err, sizeof err) == 0;
+    cfg.height = 1080;                       /* unpadded: must be refused now */
+    ok = ok && omc_validate_config(&cfg, err, sizeof err) != 0;
+    cfg.slice_h = 8;                         /* ...unless the caller asks for 8 */
+    ok = ok && omc_validate_config(&cfg, err, sizeof err) == 0;
+    cfg.slice_h = 0; cfg.height = 1088;
     cfg.width = 1900;  /* bad alignment */
     ok = ok && omc_validate_config(&cfg, err, sizeof err) != 0;
     cfg.width = 1920; cfg.bits_per_slice = 3840; /* below 0.3 bpp floor */
@@ -246,7 +257,7 @@
     ok = ok && omc_validate_config(&cfg, err, sizeof err) != 0;
     cfg.bitdepth = 10; cfg.height = 1084; /* bad height for any slice_h */
     ok = ok && omc_validate_config(&cfg, err, sizeof err) != 0;
-    cfg.height = 1080; cfg.color.transfer = 16; /* PQ ok */
+    cfg.height = 1088; cfg.color.transfer = 16; /* PQ ok */
     ok = ok && omc_validate_config(&cfg, err, sizeof err) == 0;
     CHECK(ok, "config validator: accepts valid, rejects invalid with reasons");
 }
diff -ruN '--exclude=*.o' '--exclude=*.yuv' '--exclude=__pycache__' '--exclude=.pytest_cache' '--exclude=work' '--exclude=_xc' '--exclude=repro' '--exclude=harness' '--exclude=delivery' '--exclude=*.log' '--exclude=omc_enc' '--exclude=omc_dec' '--exclude=omc_uc_tool' '--exclude=omc_tf_tool' '--exclude=omc_unblend_tool' '--exclude=test_cap' '--exclude=test_cap_old' '--exclude=test_cap_live' '--exclude=test_cc' '--exclude=test_tf' '--exclude=test_uc' '--exclude=test_unit' '--exclude=test_xsl' ./tests/test_xsl.c [machine-path-redacted]/.work/final/omc_v4.9/tests/test_xsl.c
--- a/tests/test_xsl.c	1969-12-31 19:00:00.000000000 -0500
+++ b/tests/test_xsl.c	2026-08-12 22:32:12.567175470 -0400
@@ -0,0 +1,154 @@
+/* The two things the 2026-08-12 cross-slice work must never lose.
+ *
+ * G-XSL1  STREAM AUTHORITY WHEN THE ENVIRONMENT IS SILENT.  A minor-9 stream
+ *         decodes at XSL level 3 on its own say-so.  OMC_XSL still wins when it
+ *         is set -- that is the deliberate instrumentation path (C1) and it is
+ *         the only reason level 7 can be measured at all -- so what must be
+ *         pinned is the OTHER half: with nothing in the environment, the stream
+ *         decides, and it decides 3.
+ *
+ *         This is recorded because the rule was misread during the level-7 work:
+ *         omc_read_stream_header() sets the level from the stream and
+ *         common_init() then re-reads OMC_XSL, so the environment reaches the
+ *         decoder after all.  An OMC_XSL_FORCE widening was added on the
+ *         mistaken belief that it could not, and reverted once measured.
+ *
+ * G-XSL2  THE LEVEL-7 EDIT IS EXACTLY REVERSIBLE.  Level 7 exists because the
+ *         shipped level-3 boundary edit cannot be undone: it moves a row toward
+ *         a target computed from that row's own value, which discards what the
+ *         row was.  A later encoder therefore cannot recover the reconstruction
+ *         its predecessor coded, cannot lock onto it, and re-smooths an already
+ *         smoothed picture -- measured at -8.17 dB over six generations at
+ *         3.0 bpp, and -1.26 dB against a -0.37 dB ceiling at 1.0 bpp.
+ *
+ *         Level 7 replaces it with two lifting steps in a fixed order, each
+ *         adding a correction built ONLY from rows it does not touch:
+ *             step 1   row15 += clamp((row0   - row14) / 4)
+ *             step 2   row0  += clamp((row15' - row1 ) / 4)
+ *         so omc_xsl_unblend() returns the original exactly.  If that exactness
+ *         ever breaks, the scheme degrades into a lossy edit that merely LOOKS
+ *         reversible, which is worse than not having it.  Hence a gate.
+ *
+ *         GROUND TRUTH is a decode with OMC_XSL_NOEDIT=1: every other level-7
+ *         behaviour kept, only the boundary edit skipped.  Two things that are
+ *         NOT ground truth, both learned the hard way:
+ *           - decoding at level 0, which also drops the cross-slice wavelet term
+ *             and changes the whole slice (produced a spurious "6.1% wrong");
+ *           - any frame after the first, because the edit is IN-LOOP: it changes
+ *             the reference, so two decodes of the same stream diverge from
+ *             frame 1 onward through prediction, not through the edit.  The
+ *             check is therefore intra-only.  Verifying it on an inter frame
+ *             needs the pre-edit reconstruction of that same decode, which the
+ *             decoder does not expose -- see HANDOFF_BIT_EXACTNESS.md.
+ */
+#include <stdio.h>
+#include <stdlib.h>
+#include <string.h>
+#include "omc1.h"
+
+static int fails = 0;
+#define CHECK(c, m) do { printf("%s: %s\n", (c) ? "ok" : "FAIL", m); \
+                         if (!(c)) fails++; } while (0)
+
+enum { W = 256, H = 64, SH = 16 };
+#define WC (W / 2)
+#define WORDS ((size_t)W * H + 2 * (size_t)WC * H)
+
+/* Content with real vertical structure: a flat ramp would put every slice
+ * boundary at the same place in the gradient and hide a sign error. */
+static void fill(uint16_t *p, uint32_t seed)
+{
+    uint32_t x = seed;
+    for (int y = 0; y < H; y++)
+        for (int i = 0; i < W + 2 * WC; i++) {
+            x = x * 1103515245u + 12345u;
+            int base = 200 + 6 * y + ((y / 5) % 3) * 40;
+            p[(size_t)y * (W + 2 * WC) + i] = (uint16_t)(base + ((x >> 18) % 24));
+        }
+}
+
+static void cfg_init(omc_config_t *c)
+{
+    memset(c, 0, sizeof(*c));
+    c->width = W; c->height = H; c->bitdepth = 10; c->chroma = OMC_CF_422;
+    c->ver_minor = OMC_VERSION_MINOR; c->slice_h = SH;
+    c->fps_num = 50; c->fps_den = 1;
+    c->bits_per_slice = 2 * W * SH;   /* 1.0 bpp on coded samples */
+}
+
+static void planes(omc_frame_t *fr, uint16_t *b)
+{
+    fr->p[0] = b; fr->p[1] = b + (size_t)W * H;
+    fr->p[2] = b + (size_t)W * H + (size_t)WC * H;
+    fr->stride[0] = W; fr->stride[1] = WC; fr->stride[2] = WC;
+}
+
+static size_t encode(const omc_config_t *c, const uint16_t *pix, uint8_t *bs)
+{
+    size_t fb = (size_t)(c->bits_per_slice / 8) * (H / SH);
+    omc_enc_t *e = omc_enc_create(c);
+    omc_frame_t fr; planes(&fr, (uint16_t *)pix);
+    omc_enc_frame(e, &fr, 0, bs, fb, NULL);
+    omc_enc_destroy(e);
+    return fb;
+}
+
+static void decode(const omc_config_t *c, const uint8_t *bs, size_t fb, uint16_t *out)
+{
+    omc_dec_t *d = omc_dec_create(c);
+    omc_frame_t fr; planes(&fr, out);
+    omc_dec_frame(d, bs, fb, &fr);
+    omc_dec_destroy(d);
+}
+
+int main(void)
+{
+    omc_config_t c; cfg_init(&c);
+    uint16_t *pix = malloc(WORDS * 2);
+    uint16_t *a = malloc(WORDS * 2), *b = malloc(WORDS * 2);
+    uint8_t *bs = malloc(WORDS * 2 + 65536);
+    uint8_t hdr[OMC_STREAM_HDR_BYTES];
+    if (!pix || !a || !b || !bs) { printf("FAIL: alloc\n"); return 1; }
+    fill(pix, 12345u);
+
+    /* ---------------------------------------------------------- G-XSL1 */
+    unsetenv("OMC_XSL_NOEDIT"); unsetenv("OMC_XSL_FORCE");
+    setenv("OMC_XSL", "3", 1);
+    size_t fb = encode(&c, pix, bs);
+    decode(&c, bs, fb, a);                    /* level 3, stated explicitly */
+
+    /* now the real path: environment silent, level taken from the stream */
+    unsetenv("OMC_XSL");
+    omc_config_t c2;
+    omc_write_stream_header(&c, hdr);
+    CHECK(omc_read_stream_header(hdr, &c2) > 0, "G-XSL1a a minor-9 header parses");
+    decode(&c2, bs, fb, b);
+    CHECK(memcmp(a, b, WORDS * 2) == 0,
+          "G-XSL1b stream authority: with OMC_XSL unset a minor-9 stream "
+          "decodes at level 3");
+
+    /* ---------------------------------------------------------- G-XSL2 */
+    setenv("OMC_XSL", "7", 1);
+    unsetenv("OMC_XSL_NOEDIT");
+    fb = encode(&c, pix, bs);
+    decode(&c, bs, fb, a);                    /* WITH the boundary edit */
+    setenv("OMC_XSL_NOEDIT", "1", 1);
+    decode(&c, bs, fb, b);                    /* ground truth: edit skipped only */
+    unsetenv("OMC_XSL_NOEDIT");
+
+    size_t edited = 0;
+    for (size_t i = 0; i < WORDS; i++) edited += (a[i] != b[i]);
+    CHECK(edited > 0, "G-XSL2a the level-7 boundary edit actually fires");
+
+    omc_frame_t fr; planes(&fr, a);
+    omc_xsl_unblend(&fr, &c, 0);
+    CHECK(memcmp(a, b, WORDS * 2) == 0,
+          "G-XSL2b unblend(edit(recon)) == recon, byte for byte");
+    printf("   (the edit touched %zu samples; the inverse recovered %s)\n", edited,
+           memcmp(a, b, WORDS * 2) == 0 ? "every one" : "SOME BUT NOT ALL");
+
+    unsetenv("OMC_XSL");
+    free(pix); free(a); free(b); free(bs);
+    printf("test_xsl: %s\n", fails ? "FAILURES" : "all ok");
+    return fails != 0;
+}
diff -ruN '--exclude=*.o' '--exclude=*.yuv' '--exclude=__pycache__' '--exclude=.pytest_cache' '--exclude=work' '--exclude=_xc' '--exclude=repro' '--exclude=harness' '--exclude=delivery' '--exclude=*.log' '--exclude=omc_enc' '--exclude=omc_dec' '--exclude=omc_uc_tool' '--exclude=omc_tf_tool' '--exclude=omc_unblend_tool' '--exclude=test_cap' '--exclude=test_cap_old' '--exclude=test_cap_live' '--exclude=test_cc' '--exclude=test_tf' '--exclude=test_uc' '--exclude=test_unit' '--exclude=test_xsl' ./tools/omc_enc.c [machine-path-redacted]/.work/final/omc_v4.9/tools/omc_enc.c
--- a/tools/omc_enc.c	2026-08-11 23:33:50.655592279 -0400
+++ b/tools/omc_enc.c	2026-08-12 20:20:53.380330812 -0400
@@ -9,6 +9,44 @@
 
 #include "omc1.h"
 
+extern int omc_xsl;   /* set by omc_global_init from OMC_XSL; --xsl overrides */
+
+/* Assemble the padded, coded-geometry planes from a true-dimension input frame
+ * (edge replication for the pad, optional RCT).  Factored out of the frame loop
+ * so the --xsl auto probe can build frame 0 the same way the encoder will. */
+static void assemble(uint16_t *pix, const uint16_t *inbuf, int W, int H, int Wc,
+                     int iW, int iH, int iWc, int mono, int rgb,
+                     int32_t mid_c, int32_t yoff, size_t ysz, size_t csz)
+{
+    const uint16_t *sp[3];
+    sp[0] = inbuf;
+    sp[1] = mono ? NULL : inbuf + (size_t)iW * iH;
+    sp[2] = mono ? NULL : inbuf + (size_t)iW * iH + (size_t)iWc * iH;
+    for (int p = 0; p < 3; p++) {
+        int pw = p == 0 ? W : Wc;
+        int ipw = p == 0 ? iW : iWc;
+        uint16_t *dst = pix + (p == 0 ? 0 : (p == 1 ? ysz : ysz + csz));
+        for (int r = 0; r < H; r++) {
+            int sr = r < iH ? r : iH - 1;
+            for (int x = 0; x < pw; x++) {
+                int sx = x < ipw ? x : (ipw ? ipw - 1 : 0);
+                uint16_t v;
+                if (mono && p > 0) v = (uint16_t)mid_c;
+                else if (rgb) {
+                    size_t si = (size_t)sr * iW + sx;
+                    int32_t R = sp[0][si], G = sp[1][si], B = sp[2][si];
+                    int32_t Y = (R + 2 * G + B) >> 2;
+                    if (p == 0) v = (uint16_t)(Y + yoff);
+                    else if (p == 1) v = (uint16_t)(B - G + mid_c);
+                    else v = (uint16_t)(R - G + mid_c);
+                } else
+                    v = sp[p][(size_t)sr * ipw + sx];
+                dst[(size_t)r * pw + x] = v;
+            }
+        }
+    }
+}
+
 static void die(const char *m) { fprintf(stderr, "omc_enc: %s\n", m); exit(1); }
 
 int main(int argc, char **argv)
@@ -16,6 +54,7 @@
     const char *inp = NULL, *outp = NULL, *reconp = NULL;
     int rgb = 0, mono = 0, verbose_ll = 0, lossless_frames = 0, bpp_set = 0;
     int tf_flag = -1;   /* -1 = not given; fall back to the OMC_TF variable */
+    int xsl_flag = -1;  /* -1 = not given; 0/3 = force; 2 = auto (probe) */
     omc_config_t cfg;
     memset(&cfg, 0, sizeof(cfg));
     cfg.bitdepth = 10;
@@ -49,6 +88,7 @@
         else if (!strcmp(argv[i], "--block-mv")) cfg.no_block_mv = 2;
         else if (!strcmp(argv[i], "--no-fill")) cfg.no_fill = 1;
         else if (!strcmp(argv[i], "--tf")) tf_flag = atoi(argv[++i]);
+        else if (!strcmp(argv[i], "--xsl")) xsl_flag = !strcmp(argv[i+1], "auto") ? 2 : atoi(argv[i+1]), i++;
         else if (!strcmp(argv[i], "--no-deadzone")) cfg.no_deadzone = 1;
         else if (!strcmp(argv[i], "--grain-replace")) cfg.grain_replace = 1;
         else if (!strcmp(argv[i], "--grain-corr")) cfg.grain_corr = 1;
@@ -104,10 +144,15 @@
     {
         int wal = cfg.chroma == OMC_CF_422 ? 64 : 32;
         uint16_t cw = (uint16_t)((cfg.width + wal - 1) / wal * wal);
-        /* A2: 720p-class heights MUST use slice_h 8 (LATENCY.md: 16-line
-         * slices put 720p50 at ~1.2 ms). BITSTREAM sec 7 documents this; the
-         * old auto rule contradicted it for heights divisible by 16. */
-        if (!cfg.slice_h) cfg.slice_h = (cfg.height <= 720) ? 8 : (cfg.height % 16 == 0) ? 16 : 8;
+        /* slice_h DEFAULTS TO 16 (--slice-h overrides).  The one exception
+         * is a hard one: 720p-class heights MUST use 8, because 16-line
+         * slices put 720p50 at ~1.17 ms and A2 is not negotiable
+         * (docs/LATENCY.md, BITSTREAM sec 7).  Heights that do not divide by
+         * 16 -- 1080 above all -- are coded at the next multiple and cropped
+         * on output by the existing pad-and-crop path (BITSTREAM sec 8); the
+         * old rule dropped those to 8 instead, which cost ~10 % of rate at
+         * 1.0 bpp and ~16 % at 0.5 for an arithmetic reason. */
+        if (!cfg.slice_h) cfg.slice_h = (cfg.height <= 720) ? 8 : 16;
         uint16_t chh = (uint16_t)((cfg.height + cfg.slice_h - 1) / cfg.slice_h * cfg.slice_h);
         if (cw != cfg.width || chh != cfg.height) {
             cfg.display_width = dispW; cfg.display_height = dispH;
@@ -188,6 +233,24 @@
      * flag existed the field could not be set from the shipped CLI at all, so
      * no stream could ever carry it and the whole minor-8 path was
      * unexercisable. */
+    /* --xsl auto: decide cross-slice boundary reconstruction from what it is
+     * worth on THIS material, before the header commits the minor.  Encodes
+     * frame 0 once with XSL off and measures the seam it would repair.  See
+     * omc_xsl_probe_frame(). */
+    if (xsl_flag >= 0) {
+        if (xsl_flag == 2) {
+            uint16_t *p0 = malloc(frame_words * 2);
+            if (p0 && fread(inbuf, 2, in_words, fi) == in_words) {
+                assemble(p0, inbuf, W, H, Wc, iW, iH, iWc, mono, rgb,
+                         mid_c, yoff, ysz, csz);
+                omc_frame_t probe = {{p0, p0 + ysz, p0 + ysz + csz}, {W, Wc, Wc}};
+                int d = omc_xsl_probe_frame(&cfg, &probe);
+                if (d >= 0) omc_xsl = d ? 3 : 0;
+            }
+            free(p0);
+            fseek(fi, 0, SEEK_SET);
+        } else omc_xsl = xsl_flag;
+    }
     omc_write_stream_header(&cfg, shdr);
     fwrite(shdr, 1, OMC_STREAM_HDR_BYTES, fo);
 
@@ -195,42 +258,20 @@
     omc_frame_t fin = {{pix, pix + ysz, pix + ysz + csz}, {W, Wc, Wc}};
     omc_frame_t frec = {{rec, rec ? rec + ysz : NULL, rec ? rec + ysz + csz : NULL}, {W, Wc, Wc}};
 
+    const char *ub = getenv("OMC_XSL_UNBLEND");
+    int unblend_in = ub && atoi(ub);
     int fidx = 0;
     while (nframes < 0 || fidx < nframes) {
         if (fread(inbuf, 2, in_words, fi) != in_words) break;
-        /* assemble padded coded planes from true-dim input */
-        {
-            const uint16_t *sp[3];
-            sp[0] = inbuf;
-            sp[1] = mono ? NULL : inbuf + (size_t)iW * iH;
-            sp[2] = mono ? NULL : inbuf + (size_t)iW * iH + (size_t)iWc * iH;
-            for (int p = 0; p < 3; p++) {
-                int pw = p == 0 ? W : Wc;
-                int ipw = p == 0 ? iW : iWc;
-                uint16_t *dst = pix + (p == 0 ? 0 : (p == 1 ? ysz : ysz + csz));
-                for (int r = 0; r < H; r++) {
-                    int sr = r < iH ? r : iH - 1;
-                    for (int x = 0; x < pw; x++) {
-                        int sx = x < ipw ? x : (ipw ? ipw - 1 : 0);
-                        uint16_t v;
-                        if (mono && p > 0) v = (uint16_t)mid_c;
-                        else if (rgb) {
-                            /* RCT from planar R,G,B; container-promoted
-                             * offsets keep every plane in container range
-                             * (BITSTREAM.md section 8) */
-                            size_t si = (size_t)sr * iW + sx;
-                            int32_t R = sp[0][si], G = sp[1][si], B = sp[2][si];
-                            int32_t Y = (R + 2 * G + B) >> 2;
-                            if (p == 0) v = (uint16_t)(Y + yoff);
-                            else if (p == 1) v = (uint16_t)(B - G + mid_c);
-                            else v = (uint16_t)(R - G + mid_c);
-                        } else
-                            v = sp[p][(size_t)sr * ipw + sx];
-                        dst[(size_t)r * pw + x] = v;
-                    }
-                }
-            }
-        }
+        assemble(pix, inbuf, W, H, Wc, iW, iH, iWc, mono, rgb,
+                 mid_c, yoff, ysz, csz);
+        /* OMC_XSL_UNBLEND=1 (level 7 only): the input is a previous decode, so
+         * strip its boundary edit before coding.  Because the edit is a
+         * reversible lifting cascade this recovers the exact reconstruction the
+         * previous encoder produced -- the picture lands back on the quantiser
+         * lattice, generation lock fires, and the decoder re-applies the edit on
+         * output.  One edit, not one per generation. */
+        if (unblend_in) omc_xsl_unblend(&fin, &cfg, fidx);
         int64_t n = omc_enc_frame(enc, &fin, fidx, bs, slice_bytes * (size_t)nsl,
                                   rec ? &frec : NULL);
         if (n < 0) die("encode failed");
diff -ruN '--exclude=*.o' '--exclude=*.yuv' '--exclude=__pycache__' '--exclude=.pytest_cache' '--exclude=work' '--exclude=_xc' '--exclude=repro' '--exclude=harness' '--exclude=delivery' '--exclude=*.log' '--exclude=omc_enc' '--exclude=omc_dec' '--exclude=omc_uc_tool' '--exclude=omc_tf_tool' '--exclude=omc_unblend_tool' '--exclude=test_cap' '--exclude=test_cap_old' '--exclude=test_cap_live' '--exclude=test_cc' '--exclude=test_tf' '--exclude=test_uc' '--exclude=test_unit' '--exclude=test_xsl' ./tools/omc_uc_tool.c [machine-path-redacted]/.work/final/omc_v4.9/tools/omc_uc_tool.c
--- a/tools/omc_uc_tool.c	2026-08-11 23:33:50.655592279 -0400
+++ b/tools/omc_uc_tool.c	2026-08-12 18:19:06.054121020 -0400
@@ -289,13 +289,16 @@
                     if (omc_cc_convert(&cc, sp[0], W, sp[1], W, sp[2], W, W, H))
                         die("colour: conversion failed");
                 } else {
-                    if (omc_uc_scale_plane(&uc, sp[1], Wc, Wc, H, u444, W, W, H) < 0 ||
-                        omc_uc_scale_plane(&uc, sp[2], Wc, Wc, H, v444, W, W, H) < 0)
+                    /* CO-SITED, not centre-aligned: in 4:2:2 chroma sample k
+                     * belongs to luma sample 2k, so re-centring the chroma grid
+                     * would put the colour a quarter sample off its luma. */
+                    if (omc_uc_scale_plane_sited(&uc, sp[1], Wc, Wc, H, u444, W, W, H, OMC_SITE_COSITED) < 0 ||
+                        omc_uc_scale_plane_sited(&uc, sp[2], Wc, Wc, H, v444, W, W, H, OMC_SITE_COSITED) < 0)
                         die("colour: chroma upsample failed");
                     if (omc_cc_convert(&cc, sp[0], W, u444, W, v444, W, W, H))
                         die("colour: conversion failed");
-                    if (omc_uc_scale_plane(&uc, u444, W, W, H, sp[1], Wc, Wc, H) < 0 ||
-                        omc_uc_scale_plane(&uc, v444, W, W, H, sp[2], Wc, Wc, H) < 0)
+                    if (omc_uc_scale_plane_sited(&uc, u444, W, W, H, sp[1], Wc, Wc, H, OMC_SITE_COSITED) < 0 ||
+                        omc_uc_scale_plane_sited(&uc, v444, W, W, H, sp[2], Wc, Wc, H, OMC_SITE_COSITED) < 0)
                         die("colour: chroma decimate failed");
                 }
                 if (fwrite(sm, 2, small, fo) != small) die("write");
diff -ruN '--exclude=*.o' '--exclude=*.yuv' '--exclude=__pycache__' '--exclude=.pytest_cache' '--exclude=work' '--exclude=_xc' '--exclude=repro' '--exclude=harness' '--exclude=delivery' '--exclude=*.log' '--exclude=omc_enc' '--exclude=omc_dec' '--exclude=omc_uc_tool' '--exclude=omc_tf_tool' '--exclude=omc_unblend_tool' '--exclude=test_cap' '--exclude=test_cap_old' '--exclude=test_cap_live' '--exclude=test_cc' '--exclude=test_tf' '--exclude=test_uc' '--exclude=test_unit' '--exclude=test_xsl' ./tools/omc_unblend_tool.c [machine-path-redacted]/.work/final/omc_v4.9/tools/omc_unblend_tool.c
--- a/tools/omc_unblend_tool.c	1969-12-31 19:00:00.000000000 -0500
+++ b/tools/omc_unblend_tool.c	2026-08-12 20:22:26.502600504 -0400
@@ -0,0 +1,30 @@
+/* Apply omc_xsl_unblend() to a raw picture.  Exists so the inverse can be tested
+ * against ground truth: decoding an all-intra frame with the edit switched off
+ * yields the un-edited reconstruction, and unblend(decode-with-edit) must equal
+ * it byte for byte. */
+#include <stdio.h>
+#include <stdlib.h>
+#include <string.h>
+#include "omc1.h"
+int main(int argc, char **argv)
+{
+    if (argc < 7) { fprintf(stderr, "usage: in out W H depth slice_h [refresh] [nframes] [bits_per_slice]\n"); return 2; }
+    int W = atoi(argv[3]), H = atoi(argv[4]), depth = atoi(argv[5]), sh = atoi(argv[6]);
+    int rr = argc > 7 ? atoi(argv[7]) : 8, nf = argc > 8 ? atoi(argv[8]) : 1;
+    omc_config_t cfg; memset(&cfg, 0, sizeof cfg);
+    cfg.width = (uint16_t)W; cfg.height = (uint16_t)H; cfg.bitdepth = (uint8_t)depth;
+    cfg.chroma = OMC_CF_422; cfg.slice_h = (uint8_t)sh; cfg.refresh_r = (uint8_t)rr;
+    cfg.bits_per_slice = argc > 9 ? (uint32_t)strtoul(argv[9], 0, 10)
+                                  : (uint32_t)(2 * W * sh);  /* must MATCH the encoder: it selects the cap */
+    size_t ysz = (size_t)W * H, csz = ysz / 2, words = ysz + 2 * csz;
+    uint16_t *pix = malloc(words * 2);
+    FILE *fi = fopen(argv[1], "rb"), *fo = fopen(argv[2], "wb");
+    if (!fi || !fo || !pix) { fprintf(stderr, "io\n"); return 2; }
+    for (int f = 0; f < nf; f++) {
+        if (fread(pix, 2, words, fi) != words) break;
+        omc_frame_t fr = {{pix, pix + ysz, pix + ysz + csz}, {W, W / 2, W / 2}};
+        omc_xsl_unblend(&fr, &cfg, f);
+        fwrite(pix, 2, words, fo);
+    }
+    fclose(fi); fclose(fo); free(pix); return 0;
+}
```

---

# PART S — Every script, in full

Each produced numbers quoted in this document. They assume masters in
`$R/mast/<clip>_<W>x<H>_<fmt>_<depth>.yuv` and a built tree at `$L`.


## `build.sh`

```bash
#!/bin/bash
set -eu
CC=[machine-path-redacted]/.work/tools/zcc
CFLAGS="-O2 -g -std=c11 -Wall -Wextra -Iinclude"
cd "$1"
SRC="src/dwt.c src/tans.c src/bitio.c src/alloc.c src/codec.c src/tables.c src/config.c src/upconv.c src/tfilt.c src/colour.c"
OBJ=""
pids=""
for f in $SRC; do o="${f%.c}.o"; $CC $CFLAGS -c "$f" -o "$o" & pids="$pids $!"; OBJ="$OBJ $o"; done
for pid in $pids; do wait $pid || { echo "COMPILE FAILED"; exit 1; }; done
pids=""
for t in omc_enc omc_dec omc_uc_tool omc_tf_tool omc_unblend_tool; do $CC $CFLAGS tools/$t.c $OBJ -o $t -lm & pids="$pids $!"; done
for t in test_unit test_uc test_tf test_cc; do $CC $CFLAGS tests/$t.c $OBJ -o $t -lm & pids="$pids $!"; done
for pid in $pids; do wait $pid || { echo "LINK FAILED"; exit 1; }; done
echo BUILD-OK
```

## `psnr.py`

```python
#!/usr/bin/env python3
"""Per-plane PSNR for planar LE16 Y'CbCr sequences.

usage: psnr.py SRC DEC W H FMT [FIRSTFRAME]
  FMT: 422 or 444.  FIRSTFRAME: 0 = all frames (default), 2 = steady state.
Prints one line per plane set:
   mean_Y mean_U mean_V  worst_Y worst_U worst_V  nframes
Worst = minimum over the frames considered (the mandate's worst-frame rule).
"""
import sys
import numpy as np

src, dec, W, H, fmt = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), sys.argv[5]
first = int(sys.argv[6]) if len(sys.argv) > 6 else 0
Wc = W // 2 if fmt == "422" else W
fw = W * H + 2 * Wc * H            # samples per frame
A = np.memmap(src, dtype="<u2", mode="r")
B = np.memmap(dec, dtype="<u2", mode="r")
n = min(len(A), len(B)) // fw
peak = 1023.0 ** 2 if A[:1000].max() < 1024 else 4095.0 ** 2
rows = []
for f in range(first, n):
    o = f * fw
    out = []
    for s, e in ((0, W * H), (W * H, W * H + Wc * H), (W * H + Wc * H, fw)):
        x = A[o + s:o + e].astype(np.float64)
        y = B[o + s:o + e].astype(np.float64)
        mse = ((x - y) ** 2).mean()
        out.append(99.0 if mse == 0 else 10 * np.log10(peak / mse))
    rows.append(out)
r = np.array(rows)
print(" ".join(f"{v:.3f}" for v in r.mean(0)) + " " +
      " ".join(f"{v:.3f}" for v in r.min(0)) + f" {len(rows)}")
```

## `seam7.py`

```python
#!/usr/bin/env python3
"""Seam step excess: how much bigger the vertical step is ACROSS a slice join
than the steps just inside the slices.  0 means the join is invisible in this
measure; positive means a ridge the eye can integrate into a line."""
import sys, numpy as np
f, W, H, sh = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
y = np.fromfile(f, dtype='<u2', count=W*H).astype(np.int32).reshape(H, W)
d = np.abs(np.diff(y, axis=0)).mean(axis=1)          # mean |step| per row gap
b = [k*sh-1 for k in range(1, H//sh) if k*sh-1 < H-1]
inside = [r for r in range(H-1) if r not in b and (r+1) not in b and r not in [x-1 for x in b]]
print(f"{np.mean(d[b]) - np.mean(d[inside]):+.3f}")
```

## `seam8.py`

```python
#!/usr/bin/env python3
"""Same seam metric, plus the scale-free version.  A difference of +0.27 codes at
3 bpp could just mean everything is small at 3 bpp, so report the RATIO of the
step across a join to the step inside the slice as well."""
import sys, numpy as np
f, W, H, sh = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
y = np.fromfile(f, dtype='<u2', count=W*H).astype(np.int32).reshape(H, W)
d = np.abs(np.diff(y, axis=0)).mean(axis=1)
b = [k*sh-1 for k in range(1, H//sh) if k*sh-1 < H-1]
ins = [r for r in range(H-1) if r not in b and (r+1) not in b and (r-1) not in b]
j, i = float(np.mean(d[b])), float(np.mean(d[ins]))
print(f"{j-i:+7.3f}  x{j/i:5.3f}  (join {j:6.3f} / interior {i:6.3f})")
```

## `gen7.sh`

```bash
#!/bin/bash
# Does the reversible boundary edit stop the generation loss?
# Six generations. An arm "locks" if generation N's bitstream is byte-identical
# to generation N-1's -- that is the codec recognising its own output.
set -u
R=[machine-path-redacted]/.work/ni0811
L=[machine-path-redacted]/.work/final/omc_v4.9
W=1920; H=1080; NF=4
export OMC_RBOOST=50 OMC_TAILGUARD=2 OMC_FILLHYST=2 OMC_SPC=4 \
       OMC_FORCE_PROF=2 OMC_ALLOC=2 OMC_DCFB=3 OMC_NO_DECL=1
mkdir -p $R/g7; cd $R/g7
run() {  # name  XSL  UNBLEND
  local nm=$1 xsl=$2 ub=$3 clip=$4
  local M=$R/mast/${clip}_${W}x${H}_422_10.yuv
  cp $M cur.yuv
  local prev=""
  local line="$clip $nm:"
  for g in 1 2 3 4 5 6; do
    OMC_XSL=$xsl OMC_XSL_UNBLEND=$ub $L/omc_enc -i cur.yuv -o g$g.omc \
       -w $W -h $H --fmt 422 --depth 10 --bpp 1.0 --slice-h 16 -n $NF \
       --refresh 16 >/dev/null 2>&1 || { echo "$line ENCODE-FAIL g$g"; return; }
    OMC_XSL=$xsl $L/omc_dec -i g$g.omc -o cur.yuv >/dev/null 2>&1
    local ps=$(python3 $R/psnr.py $M cur.yuv $W $H 422 0 | cut -d' ' -f1)
    local mark=""
    [ -n "$prev" ] && { cmp -s g$g.omc $prev && mark="=LOCK"; }
    line="$line  g$g=$ps$mark"
    prev=g$g.omc
  done
  echo "$line"
}
for clip in city beach; do
  run "XSL3 (shipped)      " 3 0 $clip
  run "XSL7 no unblend     " 7 0 $clip
  run "XSL7 + unblend      " 7 1 $clip
  run "XSL0 (control)      " 0 0 $clip
done
```

## `gen7b.sh`

```bash
#!/bin/bash
# The direct measurement: how many slices does generation lock fire on?
# Generation 2 encodes generation 1's decode; a locked slice is one the encoder
# recognised as its own previous output and re-emitted unchanged.
set -u
R=[machine-path-redacted]/.work/ni0811
L=[machine-path-redacted]/.work/final/omc_v4.9
W=1920; H=1080; NF=4
export OMC_RBOOST=50 OMC_TAILGUARD=2 OMC_FILLHYST=2 OMC_SPC=4 \
       OMC_FORCE_PROF=2 OMC_ALLOC=2 OMC_DCFB=3 OMC_NO_DECL=1
mkdir -p $R/g7b; cd $R/g7b
for clip in city beach; do
  M=$R/mast/${clip}_${W}x${H}_422_10.yuv
  for arm in "XSL0-control 0 0" "XSL3-shipped 3 0" "XSL7-noundo 7 0" "XSL7-undo 7 1"; do
    set -- $arm; nm=$1; xsl=$2; ub=$3
    OMC_XSL=$xsl OMC_XSL_UNBLEND=$ub $L/omc_enc -i $M -o g1.omc -w $W -h $H \
       --fmt 422 --depth 10 --bpp 1.0 --slice-h 16 -n $NF --refresh 16 >/dev/null 2>&1
    OMC_XSL=$xsl $L/omc_dec -i g1.omc -o d1.yuv >/dev/null 2>&1
    OMC_DEBUG_LOCK=1 OMC_XSL=$xsl OMC_XSL_UNBLEND=$ub $L/omc_enc -i d1.yuv -o g2.omc \
       -w $W -h $H --fmt 422 --depth 10 --bpp 1.0 --slice-h 16 -n $NF --refresh 16 \
       2>lock.txt >/dev/null
    tot=$(grep -c "locked=" lock.txt); hit=$(grep -c "locked=1" lock.txt)
    OMC_XSL=$xsl $L/omc_dec -i g2.omc -o d2.yuv >/dev/null 2>&1
    p1=$(python3 $R/psnr.py $M d1.yuv $W $H 422 0 | cut -d' ' -f1)
    p2=$(python3 $R/psnr.py $M d2.yuv $W $H 422 0 | cut -d' ' -f1)
    id=""; cmp -s g1.omc g2.omc && id=" STREAM-IDENTICAL"
    printf "%-6s %-13s lock %3d/%-3d  g1 %s  g2 %s  drop %s%s\n" \
       "$clip" "$nm" "$hit" "$tot" "$p1" "$p2" \
       "$(python3 -c "print(f'{$p2-$p1:+.3f}')")" "$id"
  done
done
```

## `gen7c.sh`

```bash
#!/bin/bash
# THE test.  Six generations, four arms, at beach/3.0bpp/sh8 -- the setting the
# scan showed the CONTROL locking hardest (73/270), so an arm that fails to lock
# is failing against a live signal rather than against noise.
#
# OMC_XSL_FORCE=1 is essential: without it a minor-9 stream always decodes at
# level 3, silently pairing a level-7 encoder with a level-3 decoder.
set -u
R=[machine-path-redacted]/.work/ni0811
L=[machine-path-redacted]/.work/final/omc_v4.9
W=1920; H=1080; NF=2; BPP=3.0; SH=8
export OMC_RBOOST=50 OMC_TAILGUARD=2 OMC_FILLHYST=2 OMC_SPC=4 \
       OMC_FORCE_PROF=2 OMC_ALLOC=2 OMC_DCFB=3 OMC_NO_DECL=1 OMC_XSL_FORCE=1
mkdir -p $R/g7c; cd $R/g7c
run() {
  local nm=$1 xsl=$2 ub=$3 clip=$4
  local M=$R/mast/${clip}_${W}x${H}_422_10.yuv
  cp $M cur.yuv; local prev="" line="" lk=""
  for g in 1 2 3 4 5 6; do
    OMC_XSL=$xsl OMC_XSL_UNBLEND=$ub OMC_DEBUG_LOCK=1 $L/omc_enc -i cur.yuv -o g$g.omc \
       -w $W -h $H --fmt 422 --depth 10 --bpp $BPP --slice-h $SH -n $NF --refresh 16 \
       2>lk.txt >/dev/null || { echo "$clip $nm ENCODE-FAIL"; return; }
    OMC_XSL=$xsl $L/omc_dec -i g$g.omc -o cur.yuv >/dev/null 2>&1
    local ps=$(python3 $R/psnr.py $M cur.yuv $W $H 422 0 | cut -d' ' -f1)
    local m=""; [ -n "$prev" ] && { cmp -s g$g.omc $prev && m="*"; }
    line="$line g$g=$ps$m"
    [ $g = 2 ] && lk="$(grep -c 'locked=1' lk.txt)/$(grep -c 'locked=' lk.txt)"
    prev=g$g.omc
  done
  printf "%-22s lock@g2 %-8s %s\n" "$nm" "$lk" "$line"
}
for clip in beach; do
  echo "=== $clip  ${BPP}bpp  sh$SH   (* = stream identical to the one before it)"
  run "XSL0 control" 0 0 $clip
  run "XSL3 shipped" 3 0 $clip
  run "XSL7 no undo" 7 0 $clip
  run "XSL7 + undo " 7 1 $clip
done
```

## `gen7d.sh`

```bash
#!/bin/bash
# The ceiling test.  An ORACLE arm: the encoder is simply TOLD whether its input
# is a previous decode (undo off at generation 1, on from generation 2).  If the
# oracle arm keeps the seam repair AND the generation resistance, then the whole
# idea reduces to building a detector, and this is the best it could ever do.
set -u
R=[machine-path-redacted]/.work/ni0811
L=[machine-path-redacted]/.work/final/omc_v4.9
W=1920; H=1080; NF=2; BPP=3.0; SH=8
export OMC_RBOOST=50 OMC_TAILGUARD=2 OMC_FILLHYST=2 OMC_SPC=4 \
       OMC_FORCE_PROF=2 OMC_ALLOC=2 OMC_DCFB=3 OMC_NO_DECL=1 OMC_XSL_FORCE=1
mkdir -p $R/g7d; cd $R/g7d
clip=beach; M=$R/mast/${clip}_${W}x${H}_422_10.yuv
cp $M cur.yuv; line=""; prev=""
for g in 1 2 3 4 5 6; do
  ub=1; [ $g = 1 ] && ub=0        # <-- the oracle
  OMC_XSL=7 OMC_XSL_UNBLEND=$ub OMC_DEBUG_LOCK=1 $L/omc_enc -i cur.yuv -o g$g.omc \
     -w $W -h $H --fmt 422 --depth 10 --bpp $BPP --slice-h $SH -n $NF --refresh 16 \
     2>lk.txt >/dev/null || { echo FAIL; exit 1; }
  OMC_XSL=7 $L/omc_dec -i g$g.omc -o cur.yuv >/dev/null 2>&1
  ps=$(python3 $R/psnr.py $M cur.yuv $W $H 422 0 | cut -d' ' -f1)
  m=""; [ -n "$prev" ] && { cmp -s g$g.omc $prev && m="*"; }
  [ $g = 2 ] && lk="$(grep -c 'locked=1' lk.txt)/$(grep -c 'locked=' lk.txt)"
  [ $g = 1 ] && cp cur.yuv gen1.yuv
  line="$line g$g=$ps$m"; prev=g$g.omc
done
printf "%-22s lock@g2 %-8s %s\n" "XSL7 + ORACLE undo" "$lk" "$line"
echo "  seam step excess at generation 1: $(python3 $R/seam7.py gen1.yuv $W $H $SH)"
```

## `gen7e.sh`

```bash
#!/bin/bash
# Confirmation at a second operating point, and the seam numbers at the first
# point so -2.632 can be read against something.
set -u
R=[machine-path-redacted]/.work/ni0811
L=[machine-path-redacted]/.work/final/omc_v4.9
W=1920; H=1080; NF=2
export OMC_RBOOST=50 OMC_TAILGUARD=2 OMC_FILLHYST=2 OMC_SPC=4 \
       OMC_FORCE_PROF=2 OMC_ALLOC=2 OMC_DCFB=3 OMC_NO_DECL=1 OMC_XSL_FORCE=1
mkdir -p $R/g7e; cd $R/g7e
echo "--- seam step excess at 3.0 bpp / sh 8 (context for the oracle run) ---"
M=$R/mast/beach_1920x1080_422_10.yuv
for x in 0 3 7; do
  OMC_XSL=$x $L/omc_enc -i $M -o s.omc -w $W -h $H --fmt 422 --depth 10 --bpp 3.0 \
     --slice-h 8 -n 1 --refresh 16 >/dev/null 2>&1
  OMC_XSL=$x $L/omc_dec -i s.omc -o s.yuv >/dev/null 2>&1
  echo "    L$x = $(python3 $R/seam7.py s.yuv $W $H 8)"
done
echo "--- six generations at city / 1.0 bpp / sh 16 ---"
run() {
  local nm=$1 xsl=$2 mode=$3 clip=$4
  local M=$R/mast/${clip}_${W}x${H}_422_10.yuv
  cp $M cur.yuv; local line="" prev=""
  for g in 1 2 3 4 5 6; do
    local ub=0
    [ "$mode" = always ] && ub=1
    [ "$mode" = oracle ] && { [ $g -gt 1 ] && ub=1; }
    OMC_XSL=$xsl OMC_XSL_UNBLEND=$ub $L/omc_enc -i cur.yuv -o g$g.omc -w $W -h $H \
      --fmt 422 --depth 10 --bpp 1.0 --slice-h 16 -n $NF --refresh 16 >/dev/null 2>&1
    OMC_XSL=$xsl $L/omc_dec -i g$g.omc -o cur.yuv >/dev/null 2>&1
    line="$line g$g=$(python3 $R/psnr.py $M cur.yuv $W $H 422 0 | cut -d' ' -f1)"
    [ $g = 1 ] && cp cur.yuv ${nm// /_}_g1.yuv
  done
  printf "  %-18s %s   seam@g1 %s\n" "$nm" "$line" \
     "$(python3 $R/seam7.py ${nm// /_}_g1.yuv $W $H 16)"
}
run "L0 control" 0 never city
run "L3 shipped" 3 never city
run "L7 oracle"  7 oracle city
```

## `g7scan.sh`

```bash
#!/bin/bash
# Where does generation lock actually fire?  Without a configuration in which the
# CONTROL locks strongly, an arm that fails to lock proves nothing.
set -u
R=[machine-path-redacted]/.work/ni0811
L=[machine-path-redacted]/.work/final/omc_v4.9
W=1920; H=1080; NF=2
export OMC_RBOOST=50 OMC_TAILGUARD=2 OMC_FILLHYST=2 OMC_SPC=4 \
       OMC_FORCE_PROF=2 OMC_ALLOC=2 OMC_DCFB=3 OMC_NO_DECL=1
mkdir -p $R/g7s; cd $R/g7s
for clip in beach city; do
 M=$R/mast/${clip}_${W}x${H}_422_10.yuv
 for bpp in 1.0 2.0 3.0; do
  for sh in 8 16; do
    OMC_XSL=0 $L/omc_enc -i $M -o a.omc -w $W -h $H --fmt 422 --depth 10 \
      --bpp $bpp --slice-h $sh -n $NF --refresh 16 >/dev/null 2>&1
    OMC_XSL=0 $L/omc_dec -i a.omc -o a.yuv >/dev/null 2>&1
    OMC_DEBUG_LOCK=1 OMC_XSL=0 $L/omc_enc -i a.yuv -o b.omc -w $W -h $H --fmt 422 \
      --depth 10 --bpp $bpp --slice-h $sh -n $NF --refresh 16 2>k.txt >/dev/null
    printf "%-6s bpp %-4s sh %-3s  control lock %3d/%-3d\n" "$clip" "$bpp" "$sh" \
      "$(grep -c 'locked=1' k.txt)" "$(grep -c 'locked=' k.txt)"
  done
 done
done
```

## `ridge.sh`

```bash
#!/bin/bash
# Where does the un-repaired seam ridge actually disappear?  If it is already
# flat above some rate, the edit up there repairs nothing and only blocks the
# generation lock -- and switching it off would be strictly better than any
# amount of cleverness about making it reversible.
set -u
R=[machine-path-redacted]/.work/ni0811
L=[machine-path-redacted]/.work/final/omc_v4.9
export OMC_RBOOST=50 OMC_TAILGUARD=2 OMC_FILLHYST=2 OMC_SPC=4 \
       OMC_FORCE_PROF=2 OMC_ALLOC=2 OMC_DCFB=3 OMC_NO_DECL=1 OMC_XSL_FORCE=1
mkdir -p $R/rg; cd $R/rg
printf "%-7s %-5s %-4s | %-9s %-9s %-9s | %s\n" clip bpp sh "no repair" "level 3" "level 7" "control lock @g2"
for clip in city beach heli; do
 M=$R/mast/${clip}_1920x1080_422_10.yuv; [ -s "$M" ] || continue
 for bpp in 0.5 1.0 1.5 2.0 3.0; do
  for sh in 16; do
   out=""
   for x in 0 3 7; do
     OMC_XSL=$x $L/omc_enc -i $M -o r.omc -w 1920 -h 1080 --fmt 422 --depth 10 \
        --bpp $bpp --slice-h $sh -n 1 --refresh 16 >/dev/null 2>&1
     OMC_XSL=$x $L/omc_dec -i r.omc -o r.yuv >/dev/null 2>&1
     out="$out $(printf '%-9s' $(python3 $R/seam7.py r.yuv 1920 1080 $sh))"
     [ $x = 0 ] && cp r.yuv r0.yuv
   done
   OMC_DEBUG_LOCK=1 OMC_XSL=0 $L/omc_enc -i r0.yuv -o r2.omc -w 1920 -h 1080 --fmt 422 \
      --depth 10 --bpp $bpp --slice-h $sh -n 1 --refresh 16 2>lk.txt >/dev/null
   printf "%-7s %-5s %-4s |%s | %d/%d\n" "$clip" "$bpp" "$sh" "$out" \
      "$(grep -c 'locked=1' lk.txt)" "$(grep -c 'locked=' lk.txt)"
  done
 done
done
```

## `lowrate.sh`

```bash
#!/bin/bash
# Dan's question: a rate threshold restores the lock only ABOVE it, and OMC lives
# BELOW it.  So what actually happens at 0.5-1.0 bpp?
#
# The control arm (no seam repair at all) is the ceiling: it is what generation
# behaviour looks like with nothing in the way.  If the control ALSO slides down
# there, then the lock is missing at low rate for reasons that have nothing to do
# with the seam edit, and neither the threshold nor the reversible edit can help.
set -u
R=[machine-path-redacted]/.work/ni0811
L=[machine-path-redacted]/.work/final/omc_v4.9
W=1920; H=1080; NF=2; SH=16
export OMC_RBOOST=50 OMC_TAILGUARD=2 OMC_FILLHYST=2 OMC_SPC=4 \
       OMC_FORCE_PROF=2 OMC_ALLOC=2 OMC_DCFB=3 OMC_NO_DECL=1 OMC_XSL_FORCE=1
mkdir -p $R/lr; cd $R/lr
run() {
  local nm=$1 xsl=$2 mode=$3 clip=$4 bpp=$5
  local M=$R/mast/${clip}_${W}x${H}_422_10.yuv
  cp $M cur.yuv; local line="" lk=""
  for g in 1 2 3 4 5 6; do
    local ub=0
    [ "$mode" = always ] && ub=1
    [ "$mode" = oracle ] && { [ $g -gt 1 ] && ub=1; }
    OMC_XSL=$xsl OMC_XSL_UNBLEND=$ub OMC_DEBUG_LOCK=1 $L/omc_enc -i cur.yuv -o g.omc \
      -w $W -h $H --fmt 422 --depth 10 --bpp $bpp --slice-h $SH -n $NF --refresh 16 \
      2>lk.txt >/dev/null || { echo "$nm FAIL"; return; }
    OMC_XSL=$xsl $L/omc_dec -i g.omc -o cur.yuv >/dev/null 2>&1
    line="$line $(python3 $R/psnr.py $M cur.yuv $W $H 422 0 | cut -d' ' -f1)"
    [ $g = 2 ] && lk="$(grep -c 'locked=1' lk.txt)/$(grep -c 'locked=' lk.txt)"
  done
  local g1=$(echo $line|cut -d' ' -f1) g6=$(echo $line|cut -d' ' -f6)
  printf "   %-24s lock %-8s %s   -> %s\n" "$nm" "$lk" "$line" \
     "$(python3 -c "print(f'{$g6-$g1:+.2f} dB')")"
}
for clip in city beach; do
 for bpp in 0.5 1.0; do
  echo "=== $clip @ $bpp bpp, slice_h $SH"
  run "no repair (ceiling)" 0 never $clip $bpp
  run "level 3 (shipped)"   3 never $clip $bpp
  run "level 7 + oracle"    7 oracle $clip $bpp
 done
done
```

## `resweep.sh`

```bash
#!/bin/bash
# Bit-exactness across resolutions.  For each geometry: encode the master, decode,
# re-encode the decode, and ask two questions --
#   how many slices did the encoder recognise as its own previous output (lock),
#   and is generation 2's bitstream byte-identical to generation 1's?
# Run with the seam edit ON (as shipped) and OFF (the ceiling), so the edit's
# contribution is separated from everything else.
set -u
R=[machine-path-redacted]/.work/ni0811
L=[machine-path-redacted]/.work/final/omc_v4.9
export OMC_RBOOST=50 OMC_TAILGUARD=2 OMC_FILLHYST=2 OMC_SPC=4 \
       OMC_FORCE_PROF=2 OMC_ALLOC=2 OMC_DCFB=3 OMC_NO_DECL=1
mkdir -p $R/rs; cd $R/rs
printf "%-26s %-6s %-4s %-5s | %-14s | %-14s\n" master WxH sh bpp "edit ON" "edit OFF (ceiling)"
row() {
  local m=$1 W=$2 H=$3 sh=$4 bpp=$5 fmt=$6
  local M=$R/mast/$m; [ -s "$M" ] || { echo "  $m MISSING"; return; }
  local out=""
  for x in 3 0; do
    OMC_XSL=$x $L/omc_enc -i $M -o a.omc -w $W -h $H --fmt $fmt --depth 10 \
      --bpp $bpp --slice-h $sh -n 1 --refresh 16 >/dev/null 2>&1 || { out="$out ENC-FAIL"; continue; }
    OMC_XSL=$x $L/omc_dec -i a.omc -o a.yuv >/dev/null 2>&1
    OMC_DEBUG_LOCK=1 OMC_XSL=$x $L/omc_enc -i a.yuv -o b.omc -w $W -h $H --fmt $fmt \
      --depth 10 --bpp $bpp --slice-h $sh -n 1 --refresh 16 2>k.txt >/dev/null
    local id="no"; cmp -s a.omc b.omc && id="YES"
    out="$out $(printf '%-14s' "$(grep -c 'locked=1' k.txt)/$(grep -c 'locked=' k.txt) id=$id")|"
  done
  printf "%-26s %-6s %-4s %-5s | %s\n" "$m" "${W}x${H}" "$sh" "$bpp" "$out"
}
for bpp in 0.5 1.0 3.0; do
  row heli_1920x1080_422_10.yuv     1920 1080 16 $bpp 422
  row beach_1920x1080_422_10.yuv    1920 1080 16 $bpp 422
  row city_1920x1080_422_10.yuv     1920 1080 16 $bpp 422
  row heli_2048x1152_422_10.yuv     2048 1152 16 $bpp 422
  row beachbox_2048x1152_422_10.yuv 2048 1152 16 $bpp 422
  row dngA4_3840x2160_422_10.yuv    3840 2160 16 $bpp 422
  row beach444_1920x1080_444_10.yuv 1920 1080 16 $bpp 444
  echo
done
```

## `latsim.py`

```python
#!/usr/bin/env python3
"""Independent end-to-end A2 simulation for the decoder output stage.

Three charging models are simulated from first principles, row by row, rather
than evaluated from a closed form:

  shipped  : omc_uc_scale_latency() -- ceil(reach/slice_h) whole slice periods
  raster   : the study's repair -- streaming line-buffer converter, output
             clocked at the destination raster rate
  raster+X : the same, but honouring what v4.9 actually does to the picture:
             with OMC_XSL level 3 the LAST ROW of slice k-1 is rewritten when
             slice k reconstructs (codec.c, the deferred row-15 edit), so that
             row is not final until one slice period later.  LATENCY.md says
             so in one line and the study does not model it at all.

Slice availability is also capture-limited: a slice cannot be sent before its
last REAL (unpadded) source row has been captured, so a padded coded raster
earns no credit.  The study's simulation gave itself that credit and reported
the results as "just under the bound".

Dependency geometry is read off the shipped scaler (upconv.c
omc_uc_scale_plane_ws): output row r reads source rows
   [ i(r) - (nt/2 - 1) , i(r) + nt/2 ],  i(r) = floor(r*num/den)
so the forward reach is nt/2 = omc_uc_scale_reach_r().
"""
import math

KTAPS, MAXTAPS, MAXPHASE = 12, 48, 16
CC_MS = 64 / (74.25 * 1000.0)          # colour stage, omc_cc_pipeline_clocks(1)


def taps(num, den):
    if num <= den:
        return KTAPS
    nt = (KTAPS * num + den - 1) // den
    nt = (nt + 1) & ~1
    return 0 if nt > MAXTAPS else nt


def reach_r(num, den):
    if num == den:
        return 0
    nt = taps(num, den)
    return nt // 2 if nt else 0


def sim(disp_h, dst_h, slice_h, fps, xsl=True, capture_limited=True):
    """Return (T_shipped, T_raster, T_raster_xsl) in ms, or None if refused."""
    g = math.gcd(disp_h, dst_h)
    num, den = disp_h // g, dst_h // g
    if den > MAXPHASE or num > MAXPHASE:
        return None
    if dst_h != disp_h and not taps(num, den):
        return None
    reach = reach_r(num, den) if dst_h != disp_h else 0

    coded = disp_h if disp_h % slice_h == 0 else (disp_h // slice_h + 1) * slice_h
    nsl = coded // slice_h
    frame = 1000.0 / fps
    line = frame / disp_h               # real capture line rate
    S = frame / nsl                     # CBR slice period

    # ---- when is slice j's payload fully in the decoder?
    # capture of its last REAL row, + transmit (1 period) + overdraft (0.5) +
    # 2 lines of pipeline.  The pure CBR pacing view is base + j*S; the capture
    # view is min((j+1)*sh, disp_h)*line + 1.5*S + 2*line.  Both must hold.
    def land(j):
        cbr = slice_h * line + S + 2 * line + j * S
        if not capture_limited:
            return cbr
        cap = min((j + 1) * slice_h, disp_h) * line + S + 2 * line
        return max(cbr, cap)

    # ---- when is SOURCE ROW s final?
    def final(s, with_xsl):
        j = s // slice_h
        if with_xsl and (s % slice_h) == slice_h - 1 and j + 1 < nsl:
            j += 1                      # deferred row-15 edit by slice j+1
        return land(j)

    def worst(with_xsl):
        t = 0.0
        for r in range(dst_h):
            i = (r * num) // den
            s = min(i + reach, disp_h - 1)
            need = final(s, with_xsl) - r * (frame / dst_h)
            if need > t:
                t = need
        return t + CC_MS

    # shipped: whole slice periods, no row-level scheduling at all
    per = (reach + slice_h - 1) // slice_h
    shipped = slice_h * line + S + 2 * line + per * S + CC_MS
    return shipped, worst(False), worst(True)


if __name__ == "__main__":
    HS = [720, 1080, 2160, 4320]
    FPS = [50, 59.94, 60, 100, 120]
    print(f"{'src':>6s} {'fps':>6s} {'sh':>3s} {'dst':>6s} {'reach':>5s} "
          f"{'shipped':>8s} {'raster':>8s} {'rast+XSL':>9s}  verdicts(ship/rast/xsl)")
    for h in HS:
        for f in FPS:
            if h >= 4320 and f > 60:
                continue
            if h >= 2160 and f > 120:
                continue
            cur = 16 if h >= 2160 else 8
            for sh in (cur, cur * 2):
                for d in HS:
                    if d < 720:
                        continue
                    r = sim(h, d, sh, f)
                    if r is None:
                        continue
                    a, b, c = r
                    v = "".join("O" if x >= 1.0 else "." for x in (a, b, c))
                    if v == "...":
                        continue          # only print rows that matter
                    print(f"{h:6d} {f:6.2f} {sh:3d} {d:6d} "
                          f"{reach_r(h // math.gcd(h, d), d // math.gcd(h, d)) if d != h else 0:5d} "
                          f"{a:8.3f} {b:8.3f} {c:9.3f}  {v}")
```

## `halfrate.sh`

```bash
#!/bin/bash
# The mandate's own test, re-run with the new default: OMC @ R against JPEG XS @ 2R.
# Three arms per rate so the slice-height change can be attributed:
#   OMC sh8   = the old default
#   OMC sh16  = the new default
#   XS  @2R   = the incumbent at double the rate
set -u
R=[machine-path-redacted]/.work/ni0811
V=$R/verify3/.work/final/omc_v4.9          # the delivered v4.9.2 archive
XS=[machine-path-redacted]/.work/svt/Bin/Release
W=1920; H=1080; NF=8
export OMC_XSL=3 OMC_RBOOST=50 OMC_TAILGUARD=2 OMC_FILLHYST=2 \
       OMC_SPC=4 OMC_FORCE_PROF=2 OMC_ALLOC=2 OMC_DCFB=3 OMC_NO_DECL=1
mkdir -p $R/hr
vmafs() {
  local v n
  v=$(ffmpeg -loglevel info -f rawvideo -pix_fmt yuv422p10le -s ${W}x${H} -r 25 -i "$1" \
      -f rawvideo -pix_fmt yuv422p10le -s ${W}x${H} -r 25 -i "$2" \
      -lavfi "libvmaf=n_threads=8" -f null - 2>&1 | grep -oP 'VMAF score: \K[0-9.]+')
  n=$(ffmpeg -loglevel info -f rawvideo -pix_fmt yuv422p10le -s ${W}x${H} -r 25 -i "$1" \
      -f rawvideo -pix_fmt yuv422p10le -s ${W}x${H} -r 25 -i "$2" \
      -lavfi "libvmaf=model=version=vmaf_v0.6.1neg:n_threads=8" -f null - 2>&1 | grep -oP 'VMAF score: \K[0-9.]+')
  echo "$v $n"
}
OUT=$R/hr/halfrate_results.txt
: > $OUT
echo "# clip arm bpp vmaf neg psnrY psnrU psnrV" >> $OUT
for clip in beach heli city; do
  M=$R/mast/${clip}_${W}x${H}_422_10.yuv
  for RATE in 0.5 1.0; do
    for SH in 8 16; do
      B=$RATE
      [ $SH = 16 ] && B=$(python3 -c "print(f'{$RATE*1080/1088:.6f}')")
      $V/omc_enc -i $M -o $R/hr/t.omc -w $W -h $H --fmt 422 --depth 10 \
         --bpp $B --slice-h $SH -n $NF --refresh 16 2>/dev/null
      $V/omc_dec -i $R/hr/t.omc -o $R/hr/t.yuv 2>/dev/null
      read v n <<< "$(vmafs $R/hr/t.yuv $M)"
      read py pu pv <<< "$(python3 $R/psnr.py $M $R/hr/t.yuv $W $H 422 0 | cut -d' ' -f1-3)"
      echo "$clip OMC_sh$SH $RATE $v $n $py $pu $pv" >> $OUT
      echo "  $clip OMC sh$SH @$RATE : vmaf $v neg $n" >&2
    done
    X=$(python3 -c "print($RATE*2)")
    $XS/SvtJpegxsEncApp -i $M -w $W -h $H --colour-format yuv422 --input-depth 10 \
       --bpp $X --coding-signs 2 --coding-vpred 2 --quantization 1 \
       -b $R/hr/t.jxs --no-progress 1 >/dev/null 2>&1
    $XS/SvtJpegxsDecApp -i $R/hr/t.jxs -o $R/hr/x.yuv >/dev/null 2>&1
    read v n <<< "$(vmafs $R/hr/x.yuv $M)"
    read py pu pv <<< "$(python3 $R/psnr.py $M $R/hr/x.yuv $W $H 422 0 | cut -d' ' -f1-3)"
    echo "$clip XS $X $v $n $py $pu $pv" >> $OUT
    echo "  $clip XS @$X : vmaf $v neg $n" >&2
  done
done
echo DONE >> $OUT
cat $OUT
```

## `halfrate4k.sh`

```bash
#!/bin/bash
# 4K: OMC @ R against JPEG XS @ 2R, and whether 16 -> 32 lines keeps paying.
# Every encode is CHECKED; a refused or failed arm aborts instead of silently
# leaving the previous arm's decode in place (which is what invalidated the
# first attempt).
set -u
R=[machine-path-redacted]/.work/ni0811
D=$R/verify3/.work/final/omc_v4.9      # the DELIVERED archive: slice_h 8/16 only
P=$R/v49p                              # research tree: slice_h any multiple of 4
XS=[machine-path-redacted]/.work/svt/Bin/Release
W=3840; H=2160; NF=4
export OMC_XSL=3 OMC_RBOOST=50 OMC_TAILGUARD=2 OMC_FILLHYST=2 \
       OMC_SPC=4 OMC_FORCE_PROF=2 OMC_ALLOC=2 OMC_DCFB=3 OMC_NO_DECL=1
mkdir -p $R/hr
vmafs() {
  local v n
  v=$(ffmpeg -loglevel info -f rawvideo -pix_fmt yuv422p10le -s ${W}x${H} -r 25 -i "$1" \
      -f rawvideo -pix_fmt yuv422p10le -s ${W}x${H} -r 25 -i "$2" \
      -lavfi "libvmaf=n_threads=8" -f null - 2>&1 | grep -oP 'VMAF score: \K[0-9.]+')
  n=$(ffmpeg -loglevel info -f rawvideo -pix_fmt yuv422p10le -s ${W}x${H} -r 25 -i "$1" \
      -f rawvideo -pix_fmt yuv422p10le -s ${W}x${H} -r 25 -i "$2" \
      -lavfi "libvmaf=model=version=vmaf_v0.6.1neg:n_threads=8" -f null - 2>&1 | grep -oP 'VMAF score: \K[0-9.]+')
  echo "$v $n"
}
OUT=$R/hr/halfrate_4k.txt
: > $OUT
echo "# clip arm bpp vmaf neg psnrY psnrU psnrV" >> $OUT
for clip in trees4 dngA4 dngB4; do
  M=$R/mast/${clip}_${W}x${H}_422_10.yuv
  [ -s "$M" ] || { echo "$clip MISSING" >> $OUT; continue; }
  # frame counts must match or libvmaf scores nonsense
  MF=$(python3 -c "import os;print(os.path.getsize('$M')//33177600)")
  [ "$MF" = "$NF" ] || { echo "$clip FRAME-COUNT $MF != $NF" >> $OUT; continue; }
  for RATE in 0.5 1.0; do
    for SH in 16 32; do
      E=$D; [ $SH = 32 ] && E=$P                 # 32 needs the research tree
      B=$RATE
      [ $SH = 32 ] && B=$(python3 -c "print(f'{$RATE*2160/2176:.6f}')")
      rm -f $R/hr/t.yuv
      $E/omc_enc -i $M -o $R/hr/t.omc -w $W -h $H --fmt 422 --depth 10 \
         --bpp $B --slice-h $SH -n $NF --refresh 16 2>$R/hr/err.txt >/dev/null \
         || { echo "ENCODE FAILED $clip sh$SH: $(head -1 $R/hr/err.txt)" >> $OUT; continue; }
      $E/omc_dec -i $R/hr/t.omc -o $R/hr/t.yuv 2>/dev/null
      [ -s $R/hr/t.yuv ] || { echo "DECODE FAILED $clip sh$SH" >> $OUT; continue; }
      read v n <<< "$(vmafs $R/hr/t.yuv $M)"
      read py pu pv <<< "$(python3 $R/psnr.py $M $R/hr/t.yuv $W $H 422 0 | cut -d' ' -f1-3)"
      echo "$clip OMC_sh$SH $RATE $v $n $py $pu $pv" >> $OUT
      echo "  $clip sh$SH @$RATE : vmaf $v neg $n" >&2
    done
    X=$(python3 -c "print($RATE*2)")
    $XS/SvtJpegxsEncApp -i $M -w $W -h $H --colour-format yuv422 --input-depth 10 \
       --bpp $X --coding-signs 2 --coding-vpred 2 --quantization 1 \
       -b $R/hr/t.jxs --no-progress 1 >/dev/null 2>&1
    $XS/SvtJpegxsDecApp -i $R/hr/t.jxs -o $R/hr/x.yuv >/dev/null 2>&1
    read v n <<< "$(vmafs $R/hr/x.yuv $M)"
    read py pu pv <<< "$(python3 $R/psnr.py $M $R/hr/x.yuv $W $H 422 0 | cut -d' ' -f1-3)"
    echo "$clip XS $X $v $n $py $pu $pv" >> $OUT
    echo "  $clip XS @$X : vmaf $v neg $n" >&2
  done
done
echo DONE >> $OUT
cat $OUT
```

## `sh_test.py`

```python
#!/usr/bin/env python3
"""slice_h 8 vs 16 at PRODUCTION width, on real footage, wire-byte honest.

The study's headline (1.15x at 1.0 bpp) was measured on 256/768-px pictures
recovered from review panels, and its own Part VII names re-confirmation at
1920 px as the single most important follow-up.  This is that re-confirmation.

Honest accounting, which the small-picture study did not have to face:
  * at 1080p, slice_h=16 pads the coded raster to 1088 rows, and the encoder
    sizes the budget from the CODED height -- so equal --bpp gives the sh=16
    arm 0.74 % MORE wire bytes.  Every comparison here is made on MEASURED
    WIRE BYTES of the delivered (cropped) picture, never on nominal bpp.
  * quality is read off the DECODER output (cropped to display), not the
    encoder's padded reconstruction.
"""
import os
import subprocess
import sys
import itertools
import json
from concurrent.futures import ThreadPoolExecutor

ROOT = "[machine-path-redacted]/.work/ni0811"
OMC = f"{ROOT}/v49/.work/final/omc_v4.9"
WORK = f"{ROOT}/shrun"
os.makedirs(WORK, exist_ok=True)

SHIP = dict(OMC_XSL="3", OMC_RBOOST="50", OMC_TAILGUARD="2", OMC_FILLHYST="2",
            OMC_SPC="4", OMC_FORCE_PROF="2", OMC_ALLOC="2", OMC_DCFB="3")


def enc_dec(clip, W, H, bpp, sh, tag, cfgname, nframes=8, extra=()):
    """Encode + decode; return (wire_bytes_per_frame, decoded_path)."""
    env = dict(os.environ)
    if cfgname == "ship":
        env.update(SHIP)
    base = f"{WORK}/{clip}_{cfgname}_{tag}"
    src = f"{ROOT}/mast/{clip}_{W}x{H}_422_10.yuv"
    cmd = [f"{OMC}/omc_enc", "-i", src, "-o", base + ".omc",
           "-w", str(W), "-h", str(H), "--fmt", "422", "--depth", "10",
           "--bpp", f"{bpp:.6f}", "--slice-h", str(sh), "-n", str(nframes)]
    if cfgname == "ship":
        cmd += ["--refresh", "16"]
    cmd += list(extra)
    r = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if r.returncode:
        raise RuntimeError(r.stderr[:400])
    subprocess.run([f"{OMC}/omc_dec", "-i", base + ".omc", "-o", base + ".yuv"],
                   capture_output=True, env=env, check=True)
    total = os.path.getsize(base + ".omc")
    per_frame = (total - 32) / nframes
    return per_frame, base + ".yuv"


def psnr(clip, W, H, dec, first):
    src = f"{ROOT}/mast/{clip}_{W}x{H}_422_10.yuv"
    out = subprocess.run(["python3", f"{ROOT}/psnr.py", src, dec, str(W),
                          str(H), "422", str(first)],
                         capture_output=True, text=True, check=True).stdout.split()
    return [float(x) for x in out[:3]], [float(x) for x in out[3:6]]


def run_point(clip, W, H, rate, cfgname, nframes):
    """Return dict with the sh16 anchor and the sh8 rate needed to match it."""
    # anchor: sh=16 at the nominal rate
    b16, d16 = enc_dec(clip, W, H, rate, 16, f"a16_{rate}", cfgname, nframes)
    mean16, worst16 = psnr(clip, W, H, d16, 2 if nframes > 2 else 0)
    m16_0, _ = psnr(clip, W, H, d16, 0)
    # sh=8 at the same nominal rate, for the equal-rate view
    b8, d8 = enc_dec(clip, W, H, rate, 8, f"a8_{rate}", cfgname, nframes)
    mean8, worst8 = psnr(clip, W, H, d8, 2 if nframes > 2 else 0)
    # bisect sh=8's rate until every plane's WORST steady frame matches sh16's
    lo, hi = rate, rate * 1.8
    best = None
    for i in range(11):
        mid = (lo + hi) / 2
        bm, dm = enc_dec(clip, W, H, mid, 8, f"bi{i}_{rate}", cfgname, nframes)
        _, wm = psnr(clip, W, H, dm, 2 if nframes > 2 else 0)
        if all(a >= b for a, b in zip(wm, worst16)):
            hi = mid
            best = bm
        else:
            lo = mid
    return dict(clip=clip, rate=rate, cfg=cfgname,
                bytes16=b16, bytes8=b8, worst16=worst16, worst8=worst8,
                mean16=mean16, mean8=mean8,
                sh8_needs_bytes=best, ratio=(best / b16) if best else None)


if __name__ == "__main__":
    W, H = 1920, 1080
    clips = sys.argv[1].split(",") if len(sys.argv) > 1 else ["beach", "heli", "city"]
    rates = [float(x) for x in sys.argv[2].split(",")] if len(sys.argv) > 2 else [0.5, 1.0, 2.0]
    cfgs = sys.argv[3].split(",") if len(sys.argv) > 3 else ["ship"]
    nframes = int(sys.argv[4]) if len(sys.argv) > 4 else 8
    jobs = [(c, W, H, r, g, nframes) for g in cfgs for c in clips for r in rates]
    res = []
    with ThreadPoolExecutor(max_workers=4) as ex:
        for r in ex.map(lambda a: run_point(*a), jobs):
            res.append(r)
            print(f"{r['cfg']:5s} {r['clip']:6s} {r['rate']:4.2f} "
                  f"sh16 {r['bytes16']:9.0f}B worstYUV "
                  + "/".join(f"{v:.2f}" for v in r['worst16'])
                  + f" | sh8 {r['bytes8']:9.0f}B "
                  + "/".join(f"{v:.2f}" for v in r['worst8'])
                  + f" | sh8 needs {r['sh8_needs_bytes'] or float('nan'):9.0f}B "
                  + f"ratio {r['ratio'] or float('nan'):.3f}x", flush=True)
    json.dump(res, open(f"{WORK}/results_{'_'.join(cfgs)}.json", "w"), indent=1)
```

## `sh_test2.py`

```python
#!/usr/bin/env python3
"""Generalised slice-height comparison: how many bytes does the CURRENT
slice height need to match a taller one, on the delivered picture?

usage: sh_test2.py CLIPS RATES ANCHOR_SHS BASE_SH W H CFG NFRAMES OMCDIR
"""
import os
import subprocess
import sys
import json
from concurrent.futures import ThreadPoolExecutor

ROOT = "[machine-path-redacted]/.work/ni0811"
WORK = f"{ROOT}/shrun2"
os.makedirs(WORK, exist_ok=True)
SHIP = dict(OMC_XSL="3", OMC_RBOOST="50", OMC_TAILGUARD="2", OMC_FILLHYST="2",
            OMC_SPC="4", OMC_FORCE_PROF="2", OMC_ALLOC="2", OMC_DCFB="3")

CLIPS, RATES, ANCH, BASE, W, H, CFG, NF, OMC = (
    sys.argv[1].split(","), [float(x) for x in sys.argv[2].split(",")],
    [int(x) for x in sys.argv[3].split(",")], int(sys.argv[4]),
    int(sys.argv[5]), int(sys.argv[6]), sys.argv[7], int(sys.argv[8]), sys.argv[9])


def run(clip, bpp, sh, tag):
    env = dict(os.environ)
    if CFG == "ship":
        env.update(SHIP)
    base = f"{WORK}/{clip}_{W}_{CFG}_{tag}"
    src = f"{ROOT}/mast/{clip}_{W}x{H}_422_10.yuv"
    cmd = [f"{OMC}/omc_enc", "-i", src, "-o", base + ".omc", "-w", str(W),
           "-h", str(H), "--fmt", "422", "--depth", "10", "--bpp", f"{bpp:.6f}",
           "--slice-h", str(sh), "-n", str(NF)]
    if CFG == "ship":
        cmd += ["--refresh", "16"]
    r = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if r.returncode:
        raise RuntimeError(r.stderr[:300])
    subprocess.run([f"{OMC}/omc_dec", "-i", base + ".omc", "-o", base + ".yuv"],
                   capture_output=True, env=env, check=True)
    b = (os.path.getsize(base + ".omc") - 32) / NF
    out = subprocess.run(["python3", f"{ROOT}/psnr.py", src, base + ".yuv",
                          str(W), str(H), "422", "2" if NF > 2 else "0"],
                         capture_output=True, text=True, check=True).stdout.split()
    return b, [float(x) for x in out[3:6]]


def point(clip, rate, anchor):
    ba, wa = run(clip, rate, anchor, f"a{anchor}_{rate}")
    lo, hi, best = rate, rate * 1.9, None
    for i in range(11):
        mid = (lo + hi) / 2
        bm, wm = run(clip, mid, BASE, f"b{anchor}_{i}_{rate}")
        if all(x >= y for x, y in zip(wm, wa)):
            hi, best = mid, bm
        else:
            lo = mid
    return dict(clip=clip, rate=rate, anchor=anchor, bytes_anchor=ba,
                worst=wa, base_needs=best, ratio=best / ba if best else None)


jobs = [(c, r, a) for a in ANCH for c in CLIPS for r in RATES]
res = []
with ThreadPoolExecutor(max_workers=4) as ex:
    for r in ex.map(lambda a: point(*a), jobs):
        res.append(r)
        print(f"{W}x{H} {CFG} {r['clip']:6s} {r['rate']:4.2f} sh{r['anchor']:<3d}"
              f" {r['bytes_anchor']:10.0f}B worst "
              + "/".join(f"{v:.2f}" for v in r['worst'])
              + f" | sh{BASE} needs {r['base_needs'] or float('nan'):10.0f}B "
              f"ratio {r['ratio'] or float('nan'):.3f}x", flush=True)
json.dump(res, open(f"{WORK}/res_{W}_{CFG}_{BASE}.json", "w"), indent=1)
```

## `ctx_test.py`

```python
#!/usr/bin/env python3
"""Entropy-model study on the REAL symbol stream at production resolution.

The JPEG 2000 study left §3.2 "unresolved": its held-out experiment trained on
two 256x304 clips, and every candidate -- including a retrained copy of OMC's
own context -- came out worse than the shipped tables, which is the signature
of a training set ~30x too small rather than a verdict.  Its recommendation #5
was to re-run the experiment on real material.  This is that re-run: real
1920x1080 broadcast footage, ~4.1 M coefficients per clip per rate, contexts
accumulated as (context x symbol) histograms so leave-one-clip-out
cross-entropy is exact.

Every candidate is CAUSAL (left / above / above-left / above-right only), so
it survives OMC's single raster pass over a slice.  Context count is printed
because context count is BRAM (C3).
"""
import sys
import os
import numpy as np

BT = {0: 0, 1: 1, 2: 1, 3: 1, 4: 2, 5: 1, 6: 3, 7: 2, 8: 1, 9: 3}
NSYM = 16


def q2v(a):
    return np.where(a == 0, 0, np.where(a == 1, 1, np.where(a <= 3, 2, 3)))


def catv(a):
    out = np.zeros(a.shape, dtype=np.int64)
    x = a.copy()
    while x.any():
        out += x > 0
        x >>= 1
    return out


def bands(path):
    """Yield (plane, band, 2-D coded values) for every band instance."""
    a = np.fromfile(path, dtype="<i4")
    a = a.reshape(-1, 4)
    key, row, col, v = a[:, 0], a[:, 1], a[:, 2], a[:, 3]
    # a band instance is a maximal run where (key) is constant AND row/col
    # restart; runs are contiguous by construction of the dump
    brk = np.flatnonzero(np.diff(key) != 0) + 1
    starts = np.concatenate(([0], brk, [len(key)]))
    for i in range(len(starts) - 1):
        s, e = starts[i], starts[i + 1]
        r, c, w = row[s:e], col[s:e], v[s:e]
        h, wd = int(r.max()) + 1, int(c.max()) + 1
        if h * wd != e - s:
            continue
        g = w.reshape(h, wd).astype(np.int64)
        yield int(key[s]) >> 4, int(key[s]) & 15, g


# ---------------------------------------------------------------- candidates
def ctx_omc16(L, A, AL, AR, bt):
    return L * 4 + A, 16


def ctx_diag2(L, A, AL, AR, bt):
    return (L * 4 + A) * 2 + ((AL > 0) | (AR > 0)), 32


def ctx_diag3(L, A, AL, AR, bt):
    return (L * 4 + A) * 3 + np.minimum((AL > 0) + (AR > 0), 2), 48


def ctx_diagmax(L, A, AL, AR, bt):
    return (L * 4 + A) * 4 + np.maximum(AL, AR), 64


def ctx_sum5(L, A, AL, AR, bt):
    return (L * 4 + A) * 5 + np.minimum(AL + AR, 4), 80


def ctx_parent(L, A, AL, AR, bt, P=None):
    """OMC's own inter-scale idea: the coarser-scale co-located magnitude.
    Causal by band order (bands are coded 0..9, so the parent is already
    coded), which is what makes it implementable in one raster pass."""
    return (L * 4 + A) * 3 + np.minimum(P, 2), 48


def ctx_parent_diag(L, A, AL, AR, bt, P=None):
    """parent + the above-diagonals: everything causal, combined."""
    return ((L * 4 + A) * 3 + np.minimum(P, 2)) * 2 + ((AL > 0) | (AR > 0)), 96


CANDS = [("omc16 (shipped)", ctx_omc16), ("+diag sig", ctx_diag2),
         ("+diag count", ctx_diag3), ("+diag mag", ctx_diagmax),
         ("+diag sum", ctx_sum5), ("+parent (inter-scale)", ctx_parent),
         ("+parent+diag", ctx_parent_diag)]
PARENT = {7: 4, 8: 5, 9: 6, 4: 3, 5: 3, 6: 3}   # BITSTREAM 9.3's own mapping


def accumulate(path):
    """-> dict model -> (nctx_total, count table), plus sign and LSB tables."""
    tabs = {name: None for name, _ in CANDS}
    sgn = np.zeros((3 * 3 * 4, 2), dtype=np.int64)      # bandtype x L x A signs
    lsb = np.zeros((3 * 16 * 16, 2), dtype=np.int64)    # (plane,band) x cat
    nz = 0
    ncoef = 0
    cache = {}
    for p, b, g in bands(path):
        if b == 0:
            cache = {}
        cache[b] = g
        # parent magnitude bucket, co-located, per BITSTREAM 9.3's mapping
        if b in PARENT and PARENT[b] in cache:
            pb = np.abs(cache[PARENT[b]])
            rr = np.arange(g.shape[0]) >> (1 if b >= 7 else 0)
            cc = np.arange(g.shape[1]) >> 1
            rr = np.minimum(rr, pb.shape[0] - 1)
            cc = np.minimum(cc, pb.shape[1] - 1)
            P = q2v(pb[np.ix_(rr, cc)])
        else:
            P = np.zeros_like(g)
        Ab = np.abs(g)
        K = catv(Ab)
        pq = np.pad(q2v(Ab), 1)
        pn = np.pad(np.sign(g), 1)
        L, A = pq[1:-1, :-2], pq[:-2, 1:-1]
        AL, AR = pq[:-2, :-2], pq[:-2, 2:]
        ncoef += g.size
        for name, fn in CANDS:
            cid, nctx = (fn(L, A, AL, AR, BT[b], P) if "parent" in name
                         else fn(L, A, AL, AR, BT[b]))
            key = (p * 16 + b) * nctx
            n = 3 * 16 * nctx
            if tabs[name] is None:
                tabs[name] = (nctx, np.zeros((n, NSYM), dtype=np.int64))
            t = tabs[name][1]
            np.add.at(t, ((key + cid).ravel(), K.ravel()), 1)
        m = Ab > 0
        if m.any():
            nz += int(m.sum())
            sc = (BT[b] * 3 + (pn[1:-1, :-2][m] + 1)) * 3 + (pn[:-2, 1:-1][m] + 1)
            np.add.at(sgn, (sc, (g[m] < 0).astype(np.int64)), 1)
            Km, Am = K[m], Ab[m]
            t2 = Km >= 2
            if t2.any():
                idx = (p * 16 + b) * 16 + np.minimum(Km[t2], 15)
                np.add.at(lsb, (idx, ((Am[t2] >> (Km[t2] - 2)) & 1).astype(np.int64)), 1)
    return tabs, sgn, lsb, ncoef, nz


def xent(train, test, alpha=0.5):
    """Bits to code `test` counts with tables trained on `train` counts."""
    t = train.astype(np.float64) + alpha
    p = t / t.sum(1, keepdims=True)
    m = test > 0
    return float(-(test[m] * np.log2(p[m])).sum())


if __name__ == "__main__":
    dumps = sys.argv[1:]          # each is  name=path
    data = {}
    for d in dumps:
        name, path = d.split("=", 1)
        print(f"loading {name} ...", file=sys.stderr)
        data[name] = accumulate(path)
    names = list(data)
    print(f"\n{'model':20s} {'ctx':>5s} | " + " ".join(f"{n:>10s}" for n in names)
          + f" {'total':>12s} {'vs omc16':>9s}")
    base = None
    for cname, _ in CANDS:
        row, tot = [], 0.0
        for n in names:
            tabs = data[n][0]
            nctx, mine = tabs[cname]
            train = sum(data[o][0][cname][1] for o in names if o != n)
            bits = xent(train, mine)
            row.append(bits)
            tot += bits
        if base is None:
            base = tot
        print(f"{cname:20s} {nctx:5d} | " + " ".join(f"{b:10.0f}" for b in row)
              + f" {tot:12.0f} {100 * (tot / base - 1):+8.2f}%")
    # sign and magnitude-LSB, same leave-one-out protocol, against raw bits
    for label, slot in (("sign (36 ctx)", 1), ("top mag LSB (16/band)", 2)):
        tot, raw = 0.0, 0
        row = []
        for n in names:
            mine = data[n][slot]
            train = sum(data[o][slot] for o in names if o != n)
            bits = xent(train, mine)
            row.append(bits)
            tot += bits
            raw += int(mine.sum())
        print(f"{label:20s} {'':5s} | " + " ".join(f"{b:10.0f}" for b in row)
              + f" {tot:12.0f} {100 * (tot / raw - 1):+8.2f}% vs raw ({raw} raw bits)")
    print("\ncoefficients per clip:", {n: data[n][3] for n in names})
    print("nonzero per clip:", {n: data[n][4] for n in names})
```

## `runskip_test.py`

```python
#!/usr/bin/env python3
"""Do JPEG 2000 / HTJ2K run-and-skip mechanisms pay inside OMC?  Re-tested on
the real 1920x1080 symbol stream, leave-one-clip-out, which is the protocol a
STATIC-table codec has to be judged under.

Models (all scored as total bits to code every coefficient of every band):
  omc16     the shipped 16-state magnitude context               [baseline]
  j2k_sig   binary-significance context, orientation-typed        (EBCOT)
  quadskip  one significance flag per 2x2 quad, then the four
            symbols inside significant quads only                 (cleanup run)
  htj2k     quad flag + category predicted from the max category
            of the already-coded left/above quads                 (HTJ2K)
"""
import sys
import numpy as np
from ctx_test import bands, q2v, catv, xent, BT

NSYM = 16


def acc(path):
    T = {}

    def add(name, shape, ctx, sym):
        if name not in T:
            T[name] = np.zeros(shape, dtype=np.int64)
        np.add.at(T[name], (ctx.ravel(), sym.ravel()), 1)

    for p, b, g in bands(path):
        Ab = np.abs(g)
        K = catv(Ab)
        H, W = g.shape
        key = p * 16 + b
        pq = np.pad(q2v(Ab), 1)
        ps = np.pad((Ab > 0).astype(np.int64), 1)
        L, A = pq[1:-1, :-2], pq[:-2, 1:-1]
        add("omc16", (3 * 16 * 16, NSYM), key * 16 + L * 4 + A, K)
        # EBCOT-style binary significance over the CAUSAL neighbourhood,
        # orientation-typed: left, above, and how many above-diagonals
        jc = (ps[1:-1, :-2] * 3 + ps[:-2, 1:-1]) * 3 \
            + np.minimum(ps[:-2, :-2] + ps[:-2, 2:], 2)
        add("j2k_sig", (3 * 16 * 4 * 9, NSYM), (key * 4 + BT[b]) * 9 + jc, K)
        # 2x2 quads
        qh, qw = (H + 1) // 2, (W + 1) // 2
        P = np.zeros((qh * 2, qw * 2), dtype=np.int64)
        P[:H, :W] = Ab
        Q = P.reshape(qh, 2, qw, 2).transpose(0, 2, 1, 3).reshape(qh, qw, 4)
        qsig = (Q > 0).any(2).astype(np.int64)
        pqs = np.pad(qsig, 1)
        qctx = pqs[1:-1, :-2] * 2 + pqs[:-2, 1:-1]
        add("quadflag", (3 * 16 * 4, 2), key * 4 + qctx, qsig)
        ins = qsig.astype(bool)
        if ins.any():
            Kq = catv(Q).reshape(qh, qw, 4)[ins]
            pos = np.tile(np.arange(4), (Kq.shape[0], 1))
            add("quadsym", (3 * 16 * 4, NSYM), key * 4 + pos, Kq)
            emax = catv(Q).reshape(qh, qw, 4).max(2)
            pe = np.pad(emax, 1)
            pc = np.minimum(np.maximum(pe[1:-1, :-2], pe[:-2, 1:-1]), 7)
            add("htj2ksym", (3 * 16 * 4 * 8, NSYM),
                (key * 4 + pos) * 8 + np.repeat(pc[ins][:, None], 4, axis=1), Kq)
    return T


data = {}
for a in sys.argv[1:]:
    n, p = a.split("=", 1)
    print(f"loading {n} ...", file=sys.stderr)
    data[n] = acc(p)
names = list(data)


def loo(key):
    return sum(xent(sum(data[o][key] for o in names if o != n), data[n][key])
               for n in names)


res = {"omc16": loo("omc16"), "j2k_sig": loo("j2k_sig"),
       "quadskip": loo("quadflag") + loo("quadsym"),
       "htj2k": loo("quadflag") + loo("htj2ksym")}
base = res["omc16"]
print(f"\n{'model':12s} {'bits (3 clips)':>16s} {'vs shipped omc16':>18s}")
for k in ("omc16", "j2k_sig", "quadskip", "htj2k"):
    print(f"{k:12s} {res[k]:16.0f} {100 * (res[k] / base - 1):+17.2f}%")
```

## `hdr_study.py`

```python
#!/usr/bin/env python3
"""How much of the 48-byte slice header is redundant, at production width?

The JPEG 2000 study measured the table-group field (120 bits) as 84 % redundant
on a 768-px picture and left it as "measured but not developed".  At 1920 px and
slice_h = 8 the header is 2.5 % of the wire at 1.0 bpp and 5.0 % at 0.5 bpp, so
this is the one lever that helps exactly the formats that must stay at 8 lines.

Parses real streams, no code change.  Reports the order-0 entropy, the entropy
conditioned on the slice above (the co-located slice of the previous frame is
NOT used -- an encoder may only look back within its own causal window, and the
slice above is already decoded at both ends), and, for the motion field, how
often the four region vectors are simply equal (the default encoder writes one
global vector into all four).
"""
import sys
import math
import numpy as np
from collections import Counter

HDR = 48
STREAM_HDR = 32


def bits(buf, off, n):
    v = 0
    for i in range(n):
        b = off + i
        v |= ((buf[b >> 3] >> (b & 7)) & 1) << i
    return v


def parse(path):
    d = open(path, "rb").read()
    w = int.from_bytes(d[6:8], "little")
    h = int.from_bytes(d[8:10], "little")
    sh = d[12]
    bps = int.from_bytes(d[21:25], "little")
    nsl = h // sh
    fbytes = nsl * bps // 8
    out = []
    off = STREAM_HDR
    while off + fbytes <= len(d):
        fr = d[off:off + fbytes]
        p = 0
        for s in range(nsl):
            hd = fr[p:p + HDR]
            if len(hd) < HDR:
                break
            o = 0
            f = {}
            for name, n in (("sync", 32), ("fidx", 8), ("sidx", 16), ("Q", 4),
                            ("prof", 2), ("nsteps", 8), ("partial", 16),
                            ("used", 24), ("state", 16)):
                f[name] = bits(hd, o, n)
                o += n
            f["gid"] = [bits(hd, o + 4 * i, 4) for i in range(30)]
            o += 120
            f["mode"] = bits(hd, o, 30)
            o += 30
            f["mv"] = [(bits(hd, o + 13 * i, 7), bits(hd, o + 13 * i + 7, 6))
                       for i in range(4)]
            o += 52
            f["fill"] = bits(hd, o, 18)
            o += 18
            f["gain"] = bits(hd, o, 6)
            out.append(f)
            p += HDR + (f["used"] + 7) // 8
        off += fbytes
    return out, w, h, sh, bps, nsl


def H(counter, n):
    return -sum(c * math.log2(c / n) for c in counter.values())


def cond_H(pairs):
    """H(x | ctx) in bits, summed."""
    joint = Counter(pairs)
    marg = Counter(c for c, _ in pairs)
    return -sum(n * math.log2(n / marg[c]) for (c, _), n in joint.items())


for path in sys.argv[1:]:
    sl, w, h, sh, bps, nsl = parse(path)
    nf = len(sl) // nsl
    wire = nf * nsl * bps / 8
    print(f"\n=== {path}  {w}x{h} slice_h={sh} slices={nsl} frames={nf} "
          f"wire={wire:.0f}B  header share={100 * nsl * nf * HDR / wire:.2f}%")
    n = len(sl)
    # table-group ids: raw 120 bits/slice
    flat = [(i, s["gid"][i]) for s in sl for i in range(30)]
    raw = 120 * n
    o0 = H(Counter(g for _, g in flat), len(flat))
    perpos = cond_H(flat)
    above = cond_H([(sl[k - 1]["gid"][i] * 30 + i, sl[k]["gid"][i])
                    for k in range(len(sl)) if sl[k]["sidx"] > 0
                    for i in range(30)])
    same = sum(1 for k in range(len(sl)) if sl[k]["sidx"] > 0
               and sl[k]["gid"] == sl[k - 1]["gid"])
    print(f"  table-group ids : raw {raw:8d} b | order-0 {o0:8.0f} "
          f"({100 * (1 - o0 / raw):.0f}%) | per-position {perpos:8.0f} "
          f"({100 * (1 - perpos / raw):.0f}%) | given slice above {above:8.0f} "
          f"({100 * (1 - above / (120 * max(1, n - nf))):.0f}%)"
          f" | identical to above {100 * same / max(1, n - nf):.1f}%")
    # motion: 52 bits/slice
    eq = sum(1 for s in sl if len(set(s["mv"])) == 1)
    inter = sum(1 for s in sl if s["mode"])
    mvraw = 52 * n
    mv1 = cond_H([(0, s["mv"][0]) for s in sl])
    print(f"  motion field    : raw {mvraw:8d} b | all-4-regions-equal "
          f"{100 * eq / n:.1f}% of slices | inter slices {100 * inter / n:.1f}%"
          f" | one-vector entropy {mv1:.0f} b "
          f"(=> {100 * (1 - (mv1 + n) / mvraw):.0f}% recoverable)")
    # mode mask, fill bits, gain, Q/profile/nsteps/partial
    for name, nb in (("mode", 30), ("fill", 18), ("gain", 6), ("Q", 4),
                     ("prof", 2), ("nsteps", 8), ("partial", 16),
                     ("used", 24), ("state", 16), ("sidx", 16), ("fidx", 8)):
        vals = [s[name] for s in sl]
        e0 = H(Counter(vals), n)
        ca = cond_H([(sl[k - 1][name], sl[k][name]) for k in range(len(sl))
                     if sl[k]["sidx"] > 0])
        print(f"  {name:8s}: raw {nb * n:8d} b | order-0 {e0:8.0f} "
              f"({100 * (1 - e0 / (nb * n)):3.0f}%) | given above {ca:8.0f} "
              f"({100 * (1 - ca / (nb * max(1, n - nf))):3.0f}%)")
```

## `a5.py`

```python
#!/usr/bin/env python3
"""A5 at the taller slice height: is loss still row-contained, and does it
still heal within one refresh cycle?

Corrupts one slice of frame 0 (bit flips in its payload), decodes, and reports
per frame which luma rows differ from the clean decode.  The containment unit
grows with slice_h -- that is a declared consequence, not a defect -- but the
CONTAINMENT and the RECOVERY BOUND must not change.
"""
import os
import subprocess
import sys
import numpy as np

R = "[machine-path-redacted]/.work/ni0811"
OMC = f"{R}/v49p"
import sys as _s
W, H, NF = 1920, 1080, int(_s.argv[1]) if len(_s.argv)>1 else 8
CLIP = _s.argv[2] if len(_s.argv)>2 else "beach"
SHIP = dict(OMC_XSL="3", OMC_RBOOST="50", OMC_TAILGUARD="2", OMC_FILLHYST="2",
            OMC_SPC="4", OMC_FORCE_PROF="2", OMC_ALLOC="2", OMC_DCFB="3")


def enc(sh, out, refresh):
    env = dict(os.environ); env.update(SHIP)
    subprocess.run([f"{OMC}/omc_enc", "-i", f"{R}/mast/{CLIP}_{W}x{H}_422_10.yuv",
                    "-o", out, "-w", str(W), "-h", str(H), "--fmt", "422",
                    "--depth", "10", "--bpp", "1.0", "--slice-h", str(sh),
                    "-n", str(NF), "--refresh", str(refresh)],
                   capture_output=True, env=env, check=True)


def dec(bs, out):
    env = dict(os.environ); env.update(SHIP)
    subprocess.run([f"{OMC}/omc_dec", "-i", bs, "-o", out],
                   capture_output=True, env=env, check=True)


for sh in (8, 16):
    coded = H if H % sh == 0 else (H // sh + 1) * sh
    nsl = coded // sh
    bs = f"{R}/gates/a5_{sh}.omc"
    enc(sh, bs, 16)
    dec(bs, f"{R}/gates/a5_{sh}_clean.yuv")
    d = bytearray(open(bs, "rb").read())
    bps = int.from_bytes(d[21:25], "little")
    fbytes = nsl * bps // 8
    victim = nsl // 2
    # walk frame 0's slices to find the victim's byte offset
    def rd(buf, base, bit, n):
        v = 0
        for i in range(n):
            b = bit + i
            v |= ((buf[base + (b >> 3)] >> (b & 7)) & 1) << i
        return v
    off = 32
    for s in range(victim):
        used = rd(d, off, 86, 24)          # used_bits sits at bit 86, unaligned
        off += 48 + (used + 7) // 8
    for i in range(48, 80):
        d[off + i] ^= 0xFF                     # smash the payload
    open(f"{R}/gates/a5_{sh}_bad.omc", "wb").write(bytes(d))
    dec(f"{R}/gates/a5_{sh}_bad.omc", f"{R}/gates/a5_{sh}_bad.yuv")
    A = np.memmap(f"{R}/gates/a5_{sh}_clean.yuv", dtype="<u2", mode="r")
    B = np.memmap(f"{R}/gates/a5_{sh}_bad.yuv", dtype="<u2", mode="r")
    fw = W * H + 2 * (W // 2) * H
    print(f"--- slice_h={sh}: {nsl} slices, victim slice {victim} "
          f"(rows {victim*sh}..{victim*sh+sh-1} of the coded raster)")
    for f in range(NF):
        o = f * fw
        y = (np.asarray(A[o:o + W * H]).reshape(H, W) !=
             np.asarray(B[o:o + W * H]).reshape(H, W))
        rows = np.flatnonzero(y.any(1))
        c = (np.asarray(A[o + W * H:o + fw]) != np.asarray(B[o + W * H:o + fw])).sum()
        if len(rows) == 0:
            print(f"   frame {f}: CLEAN (luma and chroma identical)")
        else:
            print(f"   frame {f}: luma rows {rows.min()}..{rows.max()} "
                  f"({len(rows)} rows), chroma samples differing {c}")
```

## `gates.sh`

```bash
#!/bin/bash
# Side-effect gates for the slice-height change at 1080p (pad-and-crop to 1088).
# Everything the codec already guarantees must still hold at slice_h=16 on a
# height that does not divide by 16.
set -u
R=[machine-path-redacted]/.work/ni0811
O=$R/v49/.work/final/omc_v4.9
G=$R/gates; mkdir -p $G
M=$R/mast/beach_1920x1080_422_10.yuv
PASS=0; FAIL=0
ok(){ echo "  PASS  $1"; PASS=$((PASS+1)); }
no(){ echo "  FAIL  $1"; FAIL=$((FAIL+1)); }

echo "=== G1/G2: rt=0 (display region) and exact CBR, 4:2:2/10, both slice heights"
for SH in 8 16; do
  $O/omc_enc -i $M -o $G/g_$SH.omc -w 1920 -h 1080 --fmt 422 --depth 10 \
     --bpp 1.0 --slice-h $SH -n 4 --recon $G/g_$SH.rec >/dev/null 2>&1
  $O/omc_dec -i $G/g_$SH.omc -o $G/g_$SH.dec >/dev/null 2>&1
  python3 - "$SH" "$G" <<'PY'
import sys, numpy as np, os
sh, G = sys.argv[1], sys.argv[2]
W, H = 1920, 1080
CH = 1088 if sh == "16" else 1080          # coded height
rec = np.memmap(f"{G}/g_{sh}.rec", dtype="<u2", mode="r")
dec = np.memmap(f"{G}/g_{sh}.dec", dtype="<u2", mode="r")
fr_c = W*CH + 2*(W//2)*CH
fr_d = W*H  + 2*(W//2)*H
bad = 0
for f in range(4):
    o_c, o_d = f*fr_c, f*fr_d
    for (cs, ce, ds, de, w) in ((0, W*CH, 0, W*H, W),
                                (W*CH, W*CH+(W//2)*CH, W*H, W*H+(W//2)*H, W//2),
                                (W*CH+(W//2)*CH, fr_c, W*H+(W//2)*H, fr_d, W//2)):
        a = np.asarray(rec[o_c+cs:o_c+ce]).reshape(CH, w)[:H]
        b = np.asarray(dec[o_d+ds:o_d+de]).reshape(H, w)
        bad += int((a != b).sum())
print("RT0", "OK" if bad == 0 else f"MISMATCH {bad}")
PY
  SZ=$(stat -c%s $G/g_$SH.omc)
  python3 -c "
sh=$SH; W=1920; H=1080; ch=(H+sh-1)//sh*sh; nsl=ch//sh
bps=int((1.0*W*ch/nsl))//8*8
exp=32+4*nsl*bps//8
print('CBR','OK' if exp==$SZ else f'MISMATCH exp={exp} got=$SZ', $SZ)"
done

echo "=== G3: generation stability (g1->g4 byte-identical from g2 on), slice_h=16"
cp $G/g_16.dec $G/gen1.yuv
for g in 2 3 4; do
  p=$((g-1))
  $O/omc_enc -i $G/gen$p.yuv -o $G/gen$g.omc -w 1920 -h 1080 --fmt 422 \
     --depth 10 --bpp 1.0 --slice-h 16 -n 4 >/dev/null 2>&1
  $O/omc_dec -i $G/gen$g.omc -o $G/gen$g.yuv >/dev/null 2>&1
done
if cmp -s $G/gen2.yuv $G/gen3.yuv && cmp -s $G/gen3.yuv $G/gen4.yuv; then
  ok "generations 2-4 byte-identical at slice_h=16 (padded raster)"
else no "generation drift at slice_h=16"; fi
cmp -s $G/gen2.omc $G/gen3.omc && ok "gen2/gen3 BITSTREAMS identical" || no "gen bitstream drift"

echo "=== G5: rt=0 + CBR at 4:4:4 and 12-bit, both slice heights"
ffmpeg -v error -y -i [machine-path-redacted]/Footage/actual_video_files/prores_footage/beach.mov \
  -frames:v 2 -vf crop=1920:1080:64:36 -pix_fmt yuv444p12le -f rawvideo $G/b444_12.yuv 2>/dev/null
for FMT in 444; do for D in 10 12; do for SH in 8 16; do
  if [ $D = 12 ]; then IN=$G/b444_12.yuv; else
    ffmpeg -v error -y -i [machine-path-redacted]/Footage/actual_video_files/prores_footage/beach.mov \
      -frames:v 2 -vf crop=1920:1080:64:36 -pix_fmt yuv444p10le -f rawvideo $G/b444_10.yuv 2>/dev/null
    IN=$G/b444_10.yuv; fi
  $O/omc_enc -i $IN -o $G/f.omc -w 1920 -h 1080 --fmt $FMT --depth $D --bpp 2.0 \
     --slice-h $SH -n 2 --recon $G/f.rec >/dev/null 2>&1 && \
  $O/omc_dec -i $G/f.omc -o $G/f.dec >/dev/null 2>&1
  python3 - "$SH" "$D" "$G" <<'PY'
import sys, numpy as np
sh, d, G = int(sys.argv[1]), sys.argv[2], sys.argv[3]
W, H = 1920, 1080; CH = (H+sh-1)//sh*sh
rec = np.memmap(f"{G}/f.rec", dtype="<u2", mode="r"); dec = np.memmap(f"{G}/f.dec", dtype="<u2", mode="r")
fc, fd = 3*W*CH, 3*W*H; bad = 0
for f in range(2):
    for p in range(3):
        a = np.asarray(rec[f*fc+p*W*CH:f*fc+(p+1)*W*CH]).reshape(CH, W)[:H]
        b = np.asarray(dec[f*fd+p*W*H:f*fd+(p+1)*W*H]).reshape(H, W)
        bad += int((a != b).sum())
print(f"  444/{d}-bit sh={sh}: rt0", "OK" if bad == 0 else f"MISMATCH {bad}")
PY
done; done; done
echo "PASS=$PASS FAIL=$FAIL"
```

## `eyekit.sh`

```bash
#!/bin/bash
# Full-frame, full-resolution, FULL-COLOUR renders for the eye.
# Byte-fair A/B: both arms get the same wire bytes for the same delivered
# 1920x1080 picture (slice_h=16 codes 1088 rows, so its --bpp is scaled by
# 1080/1088 to land on the same frame size).
set -eu
R=[machine-path-redacted]/.work/ni0811
O=$R/v49p
K=$R/eyekit; mkdir -p $K
export OMC_XSL=3 OMC_RBOOST=50 OMC_TAILGUARD=2 OMC_FILLHYST=2 \
       OMC_SPC=4 OMC_FORCE_PROF=2 OMC_ALLOC=2 OMC_DCFB=3
for CLIP in beach city heli; do
  for RATE in 0.5 1.0; do
    B16=$(python3 -c "print(f'{$RATE*1080/1088:.6f}')")
    for ARM in "8 $RATE" "16 $B16"; do
      set -- $ARM; SH=$1; BPP=$2
      $O/omc_enc -i $R/mast/${CLIP}_1920x1080_422_10.yuv \
        -o $K/${CLIP}_${RATE}_sh${SH}.omc -w 1920 -h 1080 --fmt 422 --depth 10 \
        --bpp $BPP --slice-h $SH -n 8 --refresh 16 >/dev/null 2>&1
      $O/omc_dec -i $K/${CLIP}_${RATE}_sh${SH}.omc -o $K/${CLIP}_${RATE}_sh${SH}.yuv >/dev/null 2>&1
      SZ=$(stat -c%s $K/${CLIP}_${RATE}_sh${SH}.omc)
      echo "$CLIP $RATE sh=$SH  wire=$SZ bytes"
      for FR in 0 5; do
        ffmpeg -v error -y -f rawvideo -pix_fmt yuv422p10le -s 1920x1080 \
          -colorspace bt709 -color_primaries bt709 -color_trc bt709 \
          -color_range tv -i $K/${CLIP}_${RATE}_sh${SH}.yuv \
          -vf "select=eq(n\,$FR),scale=in_range=tv:out_range=pc:in_color_matrix=bt709" \
          -frames:v 1 -pix_fmt rgb24 $K/${CLIP}_${RATE}_f${FR}_sh${SH}.png
      done
    done
  done
done
ls -la $K/*.png | head -30
```

## `odvmaf.sh`

```bash
#!/bin/bash
set -u
R=[machine-path-redacted]/.work/ni0811
W=1920; H=1080
vmafs() {
  local v n
  v=$(ffmpeg -loglevel info -f rawvideo -pix_fmt yuv422p10le -s ${W}x${H} -r 25 -i "$1" \
      -f rawvideo -pix_fmt yuv422p10le -s ${W}x${H} -r 25 -i "$2" \
      -lavfi "libvmaf=n_threads=8" -f null - 2>&1 | grep -oP 'VMAF score: \K[0-9.]+')
  n=$(ffmpeg -loglevel info -f rawvideo -pix_fmt yuv422p10le -s ${W}x${H} -r 25 -i "$1" \
      -f rawvideo -pix_fmt yuv422p10le -s ${W}x${H} -r 25 -i "$2" \
      -lavfi "libvmaf=model=version=vmaf_v0.6.1neg:n_threads=8" -f null - 2>&1 | grep -oP 'VMAF score: \K[0-9.]+')
  echo "$v $n"
}
OUT=$R/od/vmaf.txt; : > $OUT
for C in beach heli city; do
  M=$R/mast/${C}_${W}x${H}_422_10.yuv
  for B in 0.5 1.0; do
    for OD in ship 25 12 0; do
      f=$R/od/${C}_${B}_${OD}.yuv
      [ -s "$f" ] || continue
      read v n <<< "$(vmafs $f $M)"
      echo "$C $B $OD $v $n" >> $OUT
      echo "  $C $B od=$OD vmaf=$v neg=$n" >&2
    done
  done
done
echo DONE >> $OUT
```

## `probe.c`

```c
/* Can the encoder tell, from the picture alone, that it is NOT the first OMC in
 * the chain?
 *
 * The generation lock already relies on this: a previous OMC reconstruction has
 * coefficients that are multiples of their band's quantiser step (the wavelet is
 * exactly reversible, so re-transforming a decode returns the dequantised
 * values), while natural camera content does not.  DESIGN sect 5 states it as
 * "natural first generation content never has >= 4 nonempty lattice-aligned
 * bands".  This measures the signal directly, with no codec change, so its
 * separation can be seen before anything is built on it.
 *
 * Statistic: per (plane, band) of every slice, the count of trailing zeros of
 * the OR of the coefficient magnitudes -- the band's lattice exponent.  Report
 * the fraction of nonempty band-instances with exponent >= 1 and >= 2.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "internal.h"

static int tz(uint32_t v) { int n = 0; if (!v) return 31; while (!(v & 1)) { v >>= 1; n++; } return n; }

int main(int argc, char **argv)
{
    if (argc < 6) { fprintf(stderr, "usage: probe file W H sh fmt [nframes]\n"); return 1; }
    const char *path = argv[1];
    int W = atoi(argv[2]), H = atoi(argv[3]), sh = atoi(argv[4]);
    int c444 = !strcmp(argv[5], "444");
    int nf = argc > 6 ? atoi(argv[6]) : 1;
    int Wc = c444 ? W : W / 2;
    size_t fw = (size_t)W * H + 2 * (size_t)Wc * H;
    uint16_t *pix = malloc(fw * 2);
    int32_t *buf = malloc(sizeof(int32_t) * (size_t)W * sh);
    int32_t *tmp = malloc(sizeof(int32_t) * (size_t)(W > sh ? W : sh) * 4 + 256);
    FILE *f = fopen(path, "rb");
    if (!f) { perror(path); return 1; }
    long long nband = 0, a1 = 0, a2 = 0;
    for (int fr = 0; fr < nf; fr++) {
        if (fread(pix, 2, fw, f) != fw) break;
        for (int p = 0; p < 3; p++) {
            int pw = p ? Wc : W;
            const uint16_t *plane = pix + (p == 0 ? 0 : (size_t)W * H + (size_t)(p - 1) * Wc * H);
            for (int s = 0; s + sh <= H; s += sh) {
                for (int r = 0; r < sh; r++)
                    for (int x = 0; x < pw; x++)
                        buf[(size_t)r * pw + x] = (int32_t)plane[(size_t)(s + r) * pw + x] - 512;
                omc_slice_fwd(buf, pw, sh, tmp);
                omc_band_t bands[OMC_NBANDS];
                omc_band_layout(pw, sh, bands);
                for (int b = 1; b < OMC_NBANDS; b++) {   /* skip LL: DPCM domain */
                    uint32_t orv = 0;
                    for (int r = 0; r < bands[b].h; r++)
                        for (int x = 0; x < bands[b].w; x++) {
                            int32_t v = buf[(size_t)(bands[b].r0 + r) * pw + bands[b].c0 + x];
                            orv |= (uint32_t)(v < 0 ? -v : v);
                        }
                    if (!orv) continue;                  /* empty band says nothing */
                    nband++;
                    int e = tz(orv);
                    if (e >= 1) a1++;
                    if (e >= 2) a2++;
                }
            }
        }
    }
    fclose(f);
    printf("%-52s bands=%-7lld  exp>=1 %6.2f%%   exp>=2 %6.2f%%\n",
           path + (strlen(path) > 52 ? strlen(path) - 52 : 0), nband,
           100.0 * a1 / (nband ? nband : 1), 100.0 * a2 / (nband ? nband : 1));
    return 0;
}
```

## `bandgain.c`

```c
/* Band synthesis energy gains through OMC's OWN inverse transform.
 * MSE_picture = (1/N) * sum_b G_b * SSE_b, so the MSE-optimal dyadic band
 * offset relative to a reference band is -0.5*log2(G_b) + const -- which is
 * what a Lagrangian (PCRD) allocator would converge to at high rate.  Printing
 * it beside the shipped omc_off[] table is the whole of the study's 3.1
 * argument, checked independently and at production width. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "internal.h"

int main(int argc, char **argv)
{
    int W = argc > 1 ? atoi(argv[1]) : 1920;
    int sh = argc > 2 ? atoi(argv[2]) : 8;
    int A = 4096;
    omc_band_t bands[OMC_NBANDS];
    omc_band_layout(W, sh, bands);
    int32_t *buf = calloc((size_t)W * sh, sizeof(int32_t));
    int32_t *tmp = calloc((size_t)(W > sh ? W : sh) * 4 + 64, sizeof(int32_t));
    double G[OMC_NBANDS];
    static const char *bn[10] = {"LL5","HL5","HL4","HL3","LH2","HL2","HH2","LH1","HL1","HH1"};
    for (int b = 0; b < OMC_NBANDS; b++) {
        double acc = 0.0; int trials = 0;
        for (int ry = 0; ry < bands[b].h; ry += (bands[b].h + 3) / 4)
            for (int rx = 0; rx < bands[b].w; rx += (bands[b].w + 3) / 4) {
                memset(buf, 0, (size_t)W * sh * sizeof(int32_t));
                buf[(size_t)(bands[b].r0 + ry) * W + bands[b].c0 + rx] = A;
                omc_slice_inv(buf, W, sh, tmp);
                double e = 0.0;
                for (int i = 0; i < W * sh; i++) e += (double)buf[i] * (double)buf[i];
                acc += e / ((double)A * A); trials++;
            }
        G[b] = acc / trials;
    }
    printf("W=%d sh=%d\n", W, sh);
    printf("%-6s %5s %6s %10s %10s %8s %8s\n", "band", "h", "w", "G_b",
           "-.5log2G", "MSEopt", "shipped");
    static const int ship[10] = {-4,-3,-3,-2,-1,-1,0,0,0,1};
    double ref = -0.5 * log2(G[6]);         /* normalise to HH2, as the study did */
    for (int b = 0; b < OMC_NBANDS; b++)
        printf("%-6s %5d %6d %10.4f %10.3f %8.2f %8d\n", bn[b], bands[b].h,
               bands[b].w, G[b], -0.5 * log2(G[b]), -0.5 * log2(G[b]) - ref, ship[b]);
    free(buf); free(tmp);
    return 0;
}
```

*Scripts included: 27.*


---

**Redaction note (2026-08-27, v5.2 packaging).** Absolute paths of the
machine that produced this log have been replaced with
`[machine-path-redacted]`. Nothing else in this document was altered: the
figures, commands, verdicts and prose are exactly as written on
2026-08-12. The redaction is marked in place rather than silent, so the
record is not falsified, and it discharges the self-containment rule that
the shipped zip may carry no reference outside itself.
