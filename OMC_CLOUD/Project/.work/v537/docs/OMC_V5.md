# OMC v5 — what it is, what is on, what was implemented, and why

**Release:** OMC v5.0
**Date:** 2026-08-19
**Stream:** major 5, minor 12
**Supersedes:** OMC v4.14 (`omc_v4.14_20260812.zip`)

This document is the complete account of OMC v5: every default and why it has
the value it has, everything implemented and how it works, every measurement
and the method behind it, and every decision taken in producing it — including
the ones that were **rejected**, and why, because a register that records only
the accepted ideas is a sales document rather than an engineering one.

It is written to be read by someone holding only this zip.

---

## 1. What v5 is, in one paragraph

v5 is v4.14 with the temporal layer removed and rebuilt for zero generation
loss, plus the repairs found by an adversarial review of the result. The
rebuilt layer (called T5 throughout, specified normatively in
`docs/TEMPORAL_T5.md`) replaces a temporal engine that could never be
generation-exact with one that is: decode a v5 stream, work on the pictures,
re-encode them, and from the second generation onward the result is
byte-identical forever. v5 additionally closes the "ants" defect a blind viewer
identified twice, and makes an ordinary baseband hand-off generation-exact
rather than only the codec's own interchange. The bitstream major version is 5
and a v4 decoder refuses a v5 stream outright.

## 2. Defaults: what is ON, what is OFF, and why

**This is the section to read if you read only one.** Every switch below was
decided by measurement, and the measurement is named.

| feature | default | why |
|---|---|---|
| **Cross-slice boundary reconstruction (XSL)** | **ON, and not switchable** | It is part of the exactness contract. The encoder's un-blend and the decoder's blend must agree forever, so an off switch would be a way to produce streams that do not decode. Gates `G-T5-XSL1` fails the build if it can be switched off and `G-T5-XSL2b` fails if it stops firing. |
| **Pad neutralization** | **ON, normative** | Makes a raster coded taller than its display height (1080 coded as 1088) exact over a *cropped* baseband hand-off, by making the surplus rows a pure function of the committed visible rows. |
| **Temporal calm (the ants fix)** | **ON** | Closes the defect. It only ever *removes* energy, so it cannot be bought on VMAF-NEG — and measured, VMAF-NEG **improves** in every cell of the temporal team's corpus. `OMC_CALM=0` restores the previous quantizer for A/B work. |
| **Flattest-tier grain-fill gate, static fill tile** | **ON, normative** | Both are reconstruction rules read identically by encoder and decoder; they are what take the stream to minor 12. |
| **Grain fill** | **OFF** | Changed from on. On 14 of 16 cells, running with the fill **off** is at least as good on the ants tail across all three planes **and** on VMAF-NEG at the same time. `--fill` re-enables it. This is the clearest "rejected" default in the release: the feature is kept, but it costs more than it returns on this corpus. |
| **Strict in-gamut repair (`--gamut-strict`)** | **ON, budget 12** | This is the only thing that makes an **ordinary baseband (SDI/IP) hand-off** generation-exact; the codec's own CDR interchange is exact without it. v5's promise is byte-exactness over *both* interchanges out of the box. It stands down automatically on CDR input. It has a measured cost — section 6.3 — and either `--no-gamut-strict` or `--gamut-strict 0` disables it. |
| **Deadzone (F-2)** | **ON** | Unchanged from v4. Off under `--tune-vmaf`. |
| **Grain-replace** | **OFF** | Unchanged from v4; opt-in via `--grain-replace`. |
| **`--xsl auto`** | not a default | Demonstrated defeated by a scene cut in v4.14 and kept as an explicit option only. |
| **`slice_h`** | **auto: 8 at 720p-class, 16 above** | 16 saves 15.8% / 10.1% / 8.1% of bitrate at 0.5 / 1.0 / 2.0 bpp over 8. `slice_h` 32 exists as a knob but **exceeds the 1 ms latency budget** and is marked NOT-SHIPPABLE by the encoder's own A2 check — it is a diagnostic, not an operating point. |

### 2.1 Why the in-gamut repair is on despite costing quality

It is the only default in this release that costs anything on the metric the
project treats as governing, so the reasoning is set out rather than assumed.

**The argument for on.** Byte-exactness is the guarantee v5 exists to provide.
Without this mode it holds over the codec's own coded-domain interchange but
**not** over an ordinary baseband link — and an ordinary baseband link is what a
broadcast facility actually has between hops. A guarantee that requires an
operator to know about a flag, and to have chosen it before the material was
originated, is not a guarantee.

**The argument against, stated fairly.** It costs VMAF-NEG on content graded to
the container rails, and the cost is not uniform (section 6.3). It cannot be
turned on and off per shot: a live broadcast cuts between the pitch, a beach
package, graphics and street footage under one encoder setting, so whatever the
mode costs on its worst content is paid for the whole programme.

**Why on won.** The cost is concentrated at the lowest rate and falls steeply:
on the temporal team's real-footage corpus the worst case is −1.65 VMAF-NEG at
0.5 bpp, −0.31 at 1.0, and −0.09 at 2.0. At and above one bit per pixel, one
global setting costs at most about a third of a point on the worst content in
the mix. Below that the codec is already close to its own floor for other
reasons. The mode also stands down completely on CDR input, so no cost is paid
on the interchange that was already exact.

**What it does and does not promise.** It is a best effort with a bounded
budget rather than a theorem. An earlier revision of this work did not converge
on graphics content at or below one bit per pixel; that was found here, reported,
and has been closed by a converging restart — every cell of this corpus now
passes with zero residual samples (6.4). But "no unclosable case is currently
known" is not "no unclosable case exists", and the earlier limitation was found
precisely because a corpus lacked the case that broke it. **A build relying on
baseband exactness should verify it on its own material**; one command per cell,
in 6.4, and the encoder exits 2 if it could not clear a frame.

**How to decline it.** `--no-gamut-strict` or `--gamut-strict 0` on the command
line, or `omc_enc_set_gamut_strict(e, 0)` in the library. Both spellings of the
flag are accepted.
Do that and v5 behaves like v4 in this one respect: a baseband hand-off is exact
only while no committed sample leaves the legal range, and the encoder still
reports when that condition is violated.

### 2.2 Proving the defaults yourself, from outside the binary

Reading an initialiser is not proof that a default reaches the encoder. Each
default below is demonstrated by *changing* it and observing the stream move —
and, where the default is the quiet option, by asking for it explicitly and
observing the stream **not** move. Run against a master with flat regions and
several frames; a single smooth synthetic frame cannot engage the ants fix or
the grain fill, and will report a false "identical" for both.

```bash
M=master.yuv; A="-w 1920 -h 1080 --fmt 422 --depth 10 --bpp 1.0"
enc(){ env $1 ./omc_enc -i $M -o /tmp/t.omc $A $2 2>/dev/null; md5sum /tmp/t.omc; }
enc "" ""                     # the baseline: everything at its default
enc "OMC_CALM=0" ""           # must DIFFER   -> the ants fix is on
enc "" "--fill"               # must DIFFER   -> the grain fill is off
enc "" "--no-fill"            # must MATCH    -> confirms off
enc "" "--no-gamut-strict"    # must DIFFER   -> the in-gamut repair is on
enc "" "--gamut-strict 12"    # must MATCH    -> confirms the budget is 12
enc "OMC_XSL=0" ""            # must MATCH    -> XSL cannot be switched off
```

Measured on an 11-frame 1080p 4:2:2 10-bit graphics master, every line behaves
as annotated. Where each default lives in the source, for an auditor:

| default | set at |
|---|---|
| ants fix on | `src/codec.c`, `int omc_calm = 1`, re-read from `OMC_CALM` with a default of 1 |
| grain fill off | `omc_config_t.fill_grain`, zero-valued; the tool `memset`s its config, so zero-init means off |
| in-gamut repair on | `include/omc1.h`, `OMC_GAMUT_STRICT_DEFAULT 12`; applied in the tool and in `omc_enc_create()` so the library agrees with the tool |
| cross-slice edit on | `src/codec.c`, `int omc_xsl = 7`, with gate `G-T5-XSL1` failing the build if any lever can disable it |
| deadzone on | `omc_enc_create()`, unless `--tune-vmaf` |

## 3. What an integrator must change

Four things, and one of them will not fail to compile.

1. **The stream major is 5.** A v4 decoder returns `-2` from
   `omc_read_stream_header` on a v5 stream and a v5 decoder does the same to a
   v4 stream. Deploy both ends together. This is deliberate: v5 changed
   normative reconstruction rules and there is no safe partial interoperability.
2. **`omc_config_t.no_fill` is gone**, replaced by **`omc_config_t.fill_grain`
   with the opposite sense.** A caller that zero-initialises its config now gets
   the fill **off**. A caller that was setting `no_fill = 1` must delete that
   line. **A designated initialiser will still compile** and silently mean
   something different — check for the warning.
3. **The strict in-gamut repair is on by default at the library entry point**,
   not only in the tool. A caller that never touches
   `omc_enc_set_gamut_strict()` now gets it. Call
   `omc_enc_set_gamut_strict(e, 0)` for the v4 behaviour. Declare CDR input with
   `omc_enc_set_cdr_input(e, 1)` and the mode stands down by itself.
4. **`omc_enc_oob()` returns `-1`, meaning "not measured"**, when a slice was
   encoded with `recon == NULL`. It used to return `0`, which made the tool
   print "baseband-safe: yes" for a stream nothing had examined. **Test for `0`
   exactly, never for "not positive".**

---

## 4. The temporal layer (T5), implemented

Normative specification: **`docs/TEMPORAL_T5.md`**, shipped in this zip in full.
This section is the summary and the rationale; that document is the authority,
and where the two disagree it wins.

### 4.1 What was removed, and why it had to be

The old temporal engine had two faces: prediction of later slices *within* a
frame, and a rolling reference across frames. Neither could be made
generation-exact, for a reason that is structural rather than a bug. The
reconstruction applied a **clip** to the legal range. Clipping is irreversible:
two different committed values can map to the same clipped output, so a later
encoder cannot recover what the previous one committed, and the chain drifts.
`docs/TEMPORAL_T5.md` section 4 sets this out in full.

### 4.2 What replaced it

- **A biased, unclipped pixel domain.** The committed picture carries a +2048
  offset and is *never* clipped. The reconstruction is the plain inverse
  transform of the emitted lattice point, `T⁻¹(dequant(q))`, with no clamp
  anywhere. This single property is what the whole exactness argument rests on.
- **A frame-buffer reference with derived motion**, replacing the rolling
  intra-frame prediction.
- **An always-on, exactly reversible cross-slice boundary edit**, so a slice is
  no longer reconstructed blind to the slice above it — which is what produced
  the visible seam — while remaining invertible so the next generation can undo
  it exactly.
- **Pad neutralization**, so padded rasters are exact over a cropped hand-off.

### 4.3 The three pictures, because the vocabulary matters

Confusing these is the single most common way to misread the results.

| picture | what it is |
|---|---|
| **coded** | the raster actually worked on, possibly padded (1080 coded as 1088) |
| **committed** | what encoder and decoder agree they made: coded raster, +2048 offset, **unclipped**. This is the thing that is exact. |
| **ordinary / display** | offset removed, clipped to legal range, cropped to the display raster. This is what goes down an SDI link. |

Clipping is irreversible; cropping is reversible, because the pad rows are a
replication of the last visible row. That asymmetry is why the coded-domain
hand-off was exact before the in-gamut work and the ordinary one was not.

### 4.4 The ants fix

**The defect.** In areas the source holds still, the decode does not — a carpet
of small, fast, uncorrelated movement over a wall, a sky, a graded background. A
blind viewer identified it twice and named it as the thing that gave the codec
away. It does not exist in a still frame; it exists only in time.

**Why the rebuild made it worse.** T5 removed two mechanisms from the grain fill
— a three-tier activity taper and a half-strength amplitude class — both added
in earlier rounds specifically to close this defect. The removal was correct and
for a sound reason: the taper is not a fixed point of the amplitude derivation,
so a later generation cannot re-derive what the previous one committed and the
generation guarantee fails. What was wrong was the accounting. The cost was
booked in brightness accuracy, and brightness accuracy is not the instrument
that found the defect.

**The mechanism, stated as arithmetic.** In a flat region a detail coefficient
sits near the quantizer's zero/one boundary. The source's own sub-code wobble —
sensor noise, dither, the last bit of a grade — carries it back and forth across
that boundary. Each crossing changes the coded value between 0 and ±1, and each
such change moves the reconstruction by **a full quantizer step**: 16 code
values at shift 4, 64 at shift 6. That is the ants.

**The evidence it is the mechanism, not a theory fitted afterwards.** The codec
already contains a deadzone that does one thing: it widens that same zero/one
boundary from half a step to nine sixteenths, on the flat side only. Switching
it off **triples the ants tail on every plane** — 8.68 to 26.00 on luma, 11.39
to 23.28 and 10.84 to 20.81 on the two chroma planes. A one-sixteenth change to
that boundary moving the defect by a factor of three is only possible if the
boundary is where the defect lives.

**The fix.** In positions the source holds flat, give the quantizer a **full-step
zero zone** instead of a half-step one. A position qualifies if its local source
gradient is below a ceiling *and* its own coefficient is grain-scale in absolute
terms; a qualifying coefficient whose quantized magnitude is exactly 1, and
whose magnitude is strictly less than one step, is coded as zero.

**Why it cannot break generation exactness.** Every coefficient of a previously
coded picture is exactly `q << s`. For `|q| == 1` that magnitude is exactly
`1 << s`. The calm test is a **strict** `|c| < (1 << s)`, which `1 << s` fails.
**The kill can therefore never fire on a committed picture.** The depth is
pinned at `|q| == 1` by the same inequality and cannot be widened: killing
`|q| <= 2` would need `|c| < 2 << s`, and a committed picture's `|q| == 1`
coefficient has `|c| == 1 << s`, which *is* less than `2 << s` — so a depth-2
kill would fire on a committed picture and break the lock. That is the lattice
speaking, not a tuning choice.

**Why it is safe on the governing metric.** Nothing is added to the picture;
energy is only ever removed. A model that refuses to credit energy the source
did not have cannot be gamed by a change that only removes energy. Measured, it
is stronger than "not spent": VMAF-NEG **improves**, because the bits the flat
regions stop spending on one-step flicker are redistributed by the exact-CBR
allocator to regions carrying structure.

### 4.5 The strict in-gamut repair

**The problem.** An ordinary baseband hand-off clips to the legal range, and
clipping is irreversible. So any committed sample outside `[0, 2^depth)` breaks
generation exactness over that hand-off — while the CDR path, which carries the
unclipped committed picture, is unaffected.

**Why the obvious fixes are unavailable.** Changing the reconstruction rule is
what v4.14's in-loop clip did and is exactly what destroys exactness. Clamping
the *source* into an inset window before the transform was built and measured,
and it fails in the worst possible way — silently: when a slice's budget ran out
with the window unmet but the legal range satisfied, generation 2's clamp moved
the encoder's own input, the lock failed, and the chain broke while the gamut
report still said zero and the verdict line still said "baseband-safe: yes".
**The general lesson, which applies to any future encoder-side conditioning: a
correction an encoder applies to its own input has to be a no-op at generation
2, or it is not a correction, it is a second encoder.**

**What v5 does instead.** It changes the **source coefficients before
quantization** and re-codes the slice. The reconstruction rule, the bitstream
syntax, the decoder and the generation induction are all untouched; the only
thing that changes is *which* lattice point a **first-generation** slice commits
to. The mode is inert from generation 2 by construction, because generation 2
reads a picture the repair has already placed inside the legal range, finds
nothing to do, and never enters the repair.

**The rule.** After a slice is coded and reconstructed, count the committed
samples outside the legal range. If any, and the budget is not spent, re-code
the slice: build a per-pixel mask of the offending samples; reduce every
covering source coefficient by the gentler of a proportional 63/64 cut and a
one-quantizer-step cut, subject to an alignment veto; suppress the grain fill
for the affected band; force the offending bands to intra; escalate to 15/16 for
any slice still violating at pass 4.

**And a slice that still will not clear is RESTARTED** from its original
coefficients under a rule that always converges. That fallback is what closed
the non-convergence described in 6.4: the gentle rule alone left a floor of
residual samples on rail-pinned graphics that no additional budget could clear,
because each pass was too small to cross a quantizer boundary where the whole
neighbourhood was pinned. Restarting from the original rather than continuing to
nibble at an already-reduced slice is what makes termination guaranteed rather
than hoped for.

When the budget is exhausted the slice ships as it is, `omc_enc_oob()` reports
the truth, and **`omc_enc` exits with status 2** so an automated pipeline sees
it. Exit 0 means delivered; exit 1 means the encode itself failed.

**The alignment veto, and why it charges only some reductions.** Reducing a
coefficient's magnitude moves an offending pixel one way or the other depending
on the sign of that coefficient's synthesis basis at that pixel; reducing
without checking pushed roughly a third of every pass *further* out of range
while still costing picture. The signs are measured out of the shipping inverse
transform by `repro/gen_gm_basis.c`, which the Makefile runs, so the table
cannot drift from the transform. But applied to every candidate the veto
measured slightly **worse** — because **nine reductions in ten never carry a
coefficient across a quantizer boundary at all**, and one that does not cross
emits the same coded value, the same bits and the same picture. It is free.
Every crossing is in the coarse bands; below one quantizer step 1% of reductions
cross, at eight steps and above **100%** of them do. So the veto charges only
for reductions that cross. It then refuses 0.7% of candidates instead of 28.5%,
and improves every reduction shape on every cell measured.

---

## 5. The adversarial review, implemented

An adversarial review was run against the codec and against the temporal work.
Findings were triaged into four classes: **not yet implemented**, **already
implemented**, **no longer needed because fixed another way**, and **something
else**. Only the first class needed work. This section records what was
implemented and, equally, what was examined and deliberately *not* changed.

### 5.1 Implemented in v5

| finding | what was wrong | what v5 does |
|---|---|---|
| **Undefined shifts in the normative datapath** | Five fixed-point sites left-shifted a **negative** value: the 9/7-M lifting step in `src/dwt.c`, both polyphase shift-add multipliers in `src/upconv.c`, the colour matrix multiplier and the tone-map gain promotion in `src/colour.c`. C11 6.5.7p4 does not define that. Two of the five are in the **normative transform and colour stage** — a conformance implementation on a different toolchain is not obliged to agree, and an FPGA translation from this source would have been translating undefined behaviour. | All five now shift the **unsigned representation**, which is defined for every value and compiles to the same instruction. Encoder output is unchanged to the byte. This was found independently twice: by UndefinedBehaviorSanitizer on the temporal side and by the adversarial review on the codec side. |
| **Gate binaries did not compile under a strict C11 front end** | `tests/test_xsl.c` calls `setenv()`/`unsetenv()`, which are POSIX and not ISO C. Under `-std=c11` they are undeclared and the build **fails outright**. GCC with default glibc headers happens to expose them, which is why it was invisible until the tree was built with a different toolchain. | A separate `TCFLAGS` adds `-D_POSIX_C_SOURCE=200809L` **for the gate binaries only**. The codec sources stay strictly C11 and are untouched. Verified: this tree does not build its gate suite without the change. |
| **Three sites resolved the automatic slice height differently** | `src/config.c` and the XSL rebuild used "720 or below → 8, else 16"; `xsl_lim_for()` used a bare 16 with no 720p case. A library caller reaching the encoder with `slice_h = 0` also got a literal zero, which is not a slice height. | One shared `omc_resolve_slice_h()` in `include/omc1.h` and `src/codec.c`, used by every consumer including `common_init()`. **Honest scope: through the command line this was never reachable**, because `tools/omc_enc.c` normalises before the encoder sees it — tested by building both ways and comparing, which produced byte-identical streams. It is defensive hardening plus a real fix to the library entry point, not a live defect in the tool. |
| **No register of dangling references** | Citations to files that do not exist were undetectable except by following them. | `docs/DANGLING_REFERENCES.md`, generated by a scan that is reproduced inside it. 91 in-tree paths cited, 2 missing, both assessed. One identifier-level dangling reference (`XSL-RATE-OFF`) resolved additively rather than by rewriting the v4-era documents that cite it. |
| **A leak in `tests/test_cap.c`** | 393,216 bytes in four reconstruction buffers, never freed. Harmless to the codec and fatal to the method: LeakSanitizer reported a failure on that suite unconditionally, so a *real* leak introduced later would have been invisible. | Fixed. All six suites are clean under AddressSanitizer and UndefinedBehaviorSanitizer. |

### 5.2 Examined and deliberately not changed

Recording these matters as much as the fixes, because a reader who finds them
should know they were considered.

- **The blend cap's rate threshold.** It looks like a magic constant. It is
  eye-decided and recorded as such, with the measurements behind it in
  `src/codec.c`. Changing it is a bitstream-compatibility change; it is
  registered as `A4-XSL` in `OPEN_DECISIONS.md`.
- **`slice_h` 32.** Available as a knob and it saves a further 6.5–12% at 4K,
  but it **exceeds the 1 ms latency mandate** and the encoder marks it
  NOT-SHIPPABLE. Left as a diagnostic rather than promoted.
- **The per-slice adaptive repair factor.** Would let the in-gamut repair choose
  a shape per slice. Measured: three pixel-domain distances pick the same shape
  on 343 of 348 violating slices, and mixing shapes across the slices of one
  frame scored **worse than either uniform choice**. Rejected on measurement.
- **Returning the in-gamut repair's freed bits to the rate planner.** Measured
  96.6757 against 96.6991 — nothing. The freed bits are below the granularity
  the plan can act on. Kept behind a switch, not made default.

## 6. Results, and how they were measured

### 6.1 Method

Two independent measurement efforts are reported and they are labelled
throughout, because conflating them would overstate the evidence.

**This delivery's battery.** Five clips chosen as the most different available
from the uncompressed corpus (screen graphics, sky gradient, dark interior,
walking camera, city architecture), prepared to canonical 4:4:4 12-bit BT.709
limited-range masters, then derived per arm: raster by Lanczos, 4:2:2 by pair
averaging, depth by shift. 149 cells per arm spanning 720p to 8K, both chroma
samplings, 8/10/12-bit, and nine rates from 0.5 to 4.0 bpp. Eleven frames per
cell. Instruments: per-plane PSNR and SSIM, per-plane border-seam excess,
per-slice Laplacian energy retention, a per-plane "ants" tail, VMAF and
VMAF-NEG. Every cell is written to disk the moment it completes.

**The temporal team's battery.** Their own corpus of camera and graphics
masters, three frames per cell, reported in `docs/TEMPORAL_T5.md` sections 12.22
and 12.23. Their figures are theirs; where quoted here they are named as such.

**What neither battery is.** `PROJECT_CONSTRAINTS.md` reserves the pass/fail
judgement for blind human viewing and calls every computed metric a diagnostic
*"in either direction"*. Nothing below is a verdict.

### 6.2 What holds

- **Exact constant bitrate.** Every stream is exactly
  `32 + frames × slices × bits_per_slice/8` bytes. Verified **25 of 25 cells on
  the v5 build itself**, and 149 of 149 on each of the three predecessor arms
  measured in the same battery. Not one byte of drift anywhere.
- **Constant latency.** A 1200-row sweep through the codec's own latency
  functions finds **zero** cells whose latency figures move with bitrate and
  zero whose validator verdict moves with it. `make test` re-measures the whole
  A2 table on this build, including every conversion in the mandate's range.
- **Generation exactness, CDR.** 29 of 29 cells of the CDR matrix pass,
  including 4K and 8K-class rasters and every encoder option.
- **Generation exactness, ordinary baseband.** With the repair on: the eight
  previously failing cells pass, the two largest violation counts pass, and
  three twenty-generation chains pass on the temporal team's corpus — and
  **all cells pass on this delivery's corpus, with zero residual out-of-range
  samples.** See 6.4 for the measurement and for what changed to make it so.
- **The gate suite.** **96 assertions** across six suites, all passing. These
  include five determinism gates (byte-identical output *and* an identical
  internal path on a re-encode) and five content-cut gates that encode a
  sequence switching between content types mid-chain, which is how a broadcast
  feed is actually used and which no earlier gate exercised.

### 6.3 The cost of the on-by-default in-gamut repair, measured on this build

The same v6 binary, run twice over the 1080p 4:2:2 10-bit spine — once at the
shipped default and once with `--no-gamut-strict`. Exact CBR means both arms
produce byte-identical stream *sizes*, so this is a pure picture comparison.
VMAF-NEG, decode against master, eleven frames.

| clip | 0.5 bpp | 1.0 | 2.0 | 3.0 | 4.0 |
|---|---|---|---|---|---|
| screen graphics | **−4.86** | **−0.59** | −0.04 | −0.03 | 0.00 |
| city architecture | −0.13 | −0.00 | 0.00 | 0.00 | 0.00 |
| sky gradient | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| dark interior | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| walking camera | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |

**22 of 25 cells cost essentially nothing** (within ±0.1), and three of the five
clips are untouched at every rate — their committed pictures never leave the
legal range, so the encoder emits a byte-identical stream. That is the inertness
gate `G-T5-GAMUT3` holding on real footage rather than on a synthetic.

**The whole cost is graphics content at low rate**, and it decays steeply: 4.86
points at half a bit per pixel, 0.59 at one bit, under 0.05 above that.

**The cost went UP relative to the previous revision, and that is the trade this
release deliberately took.** The same measurement on the earlier reduction rule:

| cell | earlier rule | this release |
|---|---|---|
| screen graphics @ 0.5 | −3.90 | **−4.86** |
| screen graphics @ 1.0 | −0.18 | **−0.59** |
| city architecture @ 0.5 | −0.02 | −0.13 |

The earlier rule was gentler and **did not converge**: on this same graphics
master it left 6 out-of-range samples at 0.5 bpp and 3 at 1.0, so the baseband
chain still broke at generation 2 and the guarantee was not delivered at all.
This release restarts a slice that will not clear gently, using a rule that
always converges (4.5), and pays about another point of VMAF-NEG on the worst
cell for it. **Given that the release's promise is byte-exactness over an
ordinary hand-off, a guarantee that holds is worth more than a cheaper one that
does not** — but the price is real and it is charged on graphics-like material
at the lowest rates.

Note also that the temporal team's own corpus moves the other way, from 5.44 to
2.00 on their worst real cell. Two corpora, opposite directions, same change:
which content you hold decides what this costs you, which is the argument for
measuring your own material rather than taking either figure.

**Reproduce it:**

```bash
./omc_enc -i master.yuv -o on.omc  -w 1920 -h 1080 --fmt 422 --depth 10 --bpp 0.5
./omc_enc -i master.yuv -o off.omc -w 1920 -h 1080 --fmt 422 --depth 10 --bpp 0.5 \
          --no-gamut-strict
./omc_dec -i on.omc -o on.yuv ; ./omc_dec -i off.omc -o off.yuv
bash tests/vmafneg.sh master.yuv on.yuv  1920 1080 422 10
bash tests/vmafneg.sh master.yuv off.yuv 1920 1080 422 10
```

### 6.4 Baseband exactness: a limitation that was found, reported and closed

An earlier revision of this delivery carried a section here documenting a real
failure. It is retained as a record of what happened rather than deleted,
because the sequence is the useful part.

**What was found.** On a real screen-graphics master at 1920×1080 4:2:2 10-bit,
the ordinary baseband chain FAILED at generation 2 with the repair on, at 0.5
and 1.0 bits per pixel. The repair reached its pass budget with samples still
outside the legal range — 6 at the default budget, and **4 at the hard cap of
16**, so it was a floor rather than a budget shortfall. Seven cells passed and
three failed. The specification at the time named the mechanism and called it
structural: a rail exactly on a slice boundary, where the cross-slice edit can
always carry a sample one code out and the quantizer has pinned the whole
neighbourhood to the rail. Gate `G-T5-GAMUT2c` asserted that on a *deliberately
pathological synthetic* the mode removes "at least 99% and not all". The finding
was that an ordinary graphics master at delivery rates behaves like that
synthetic.

**What changed.** It was reported to the temporal team as
`BASEBAND_NONCONVERGENCE.md`. Their response: a slice that will not clear gently
is now **restarted from its original coefficients with a rule that always
converges** (4.5). `G-T5-GAMUT2c` no longer asserts "99% and not all" — it
asserts **all**, and the specification records that no unclosable case is
currently known.

**Verified here, on the same cells that failed:**

| cell | before | now |
|---|---|---|
| screen graphics @ 0.5 bpp | FAIL at generation 2, 6 samples left | **PASS, oob = 0** |
| screen graphics @ 1.0 bpp | FAIL at generation 2, 3 samples left | **PASS, oob = 0** |
| screen graphics @ 2.0 bpp | PASS | PASS |
| city architecture @ 0.5 / 1.0 | PASS | PASS |
| sky gradient @ 0.5 | PASS | PASS |
| dark interior @ 0.5 | PASS | PASS |
| walking camera @ 0.5 | PASS | PASS |

**Eight of eight pass with zero residual samples**, where the earlier rule gave
seven passes and three failures. The price is in 6.3.

**What is still not claimed.** "No unclosable case is currently known" is not
the same as "no unclosable case exists". The corpus here is five clips and the
temporal team's is fifteen; neither is a proof of universality, and the earlier
limitation was discovered precisely because a corpus did not contain the case
that broke it. **A build relying on baseband exactness should verify it on its
own material** — one command per cell:

```bash
bash tests/genchain_bb.sh master.yuv <W> <H> <fmt> <depth> <bpp> <slice_h> 4
```

A `PASS` line with `oob=0` is the chain holding. A `FAIL pixels-gen2` line with
a non-zero `oob` means the repair reached its budget on that material. **The
encoder also now exits with status 2** when it could not clear every sample — 0
means delivered, 1 means the encode failed — so an automated pipeline can gate
on it at origination instead of discovering the problem at somebody else's
second hop.

## 7. Every decision in this cycle: adopted and rejected

The rejected column is the useful one. Each row names the evidence.

### 7.1 Adopted

| decision | evidence |
|---|---|
| Remove and rebuild the temporal engine | The old one applied a clip in reconstruction, and clipping is irreversible, so no amount of repair could make it generation-exact. Structural, not a bug. |
| Unclipped, biased committed domain | It is the property the entire exactness induction rests on. |
| Cross-slice edit always on, no switch | Encoder un-blend and decoder blend must agree forever; a switch is a way to make undecodable streams. |
| Fix the ants in the **quantizer**, not the fill | Three fill-side designs were built and measured first and none was sufficient (7.2). The deadzone experiment localised the defect to the zero/one boundary. |
| Kill depth pinned at `\|q\| == 1` | Not a tuning choice — a depth-2 kill would fire on a committed picture and break the lock. The lattice fixes it. |
| Grain fill **off** by default | On 14 of 16 cells, off is at least as good on the ants tail across all three planes **and** on VMAF-NEG simultaneously. |
| In-gamut repair by editing **source coefficients pre-quantization** | The two obvious alternatives change the reconstruction rule (destroys exactness) or search lattice points (a much larger piece of work). This third option leaves the induction untouched. |
| In-gamut repair **on by default** | Byte-exactness over an ordinary baseband hand-off is what v5 promises, and this is the only mechanism that delivers it. Cost quantified in 6.3 and disclosed. |
| Alignment veto charged only on quantizer crossings | Applied uniformly it measured worse; nine reductions in ten are free. Charging only crossings improved every shape on every cell. |
| Basis sign table **generated by the build** | A measured table is authoritative for the code that ships; generating it from `src/dwt.c` means it cannot drift when a lifting step changes. |
| Bitstream major bumped to 5 | v5 changed normative reconstruction rules. A hard refusal is safer than partial interoperability. |
| **Restart a slice that will not clear gently**, under a rule that always converges | The gentle rule alone left a floor of residual samples on rail-pinned graphics that no extra budget could clear (6.4). Termination is now guaranteed rather than hoped for, at the cost in 6.3. |
| **`omc_enc` exits 2 when the repair could not clear a frame** | A warning on stderr is easy to miss in an automated pipeline, and the cost of missing it lands at the *second* hop, in somebody else's facility. |
| **Charge the alignment test only where a reduction crosses a quantizer boundary** | 86–90% of reductions change no coded value at all and are free. Charging only the crossings takes the veto's refusal rate from 28.5% to 0.7% and improves every reduction shape on every cell measured. |
| **Content-cut gates** | Every earlier gate encoded one kind of content at a time. A broadcast chain cuts between content types in seconds, and nothing had tested that the repair behaves across a cut. |

### 7.2 Rejected, with the measurement that killed it

| idea | why it was tried | why it was rejected |
|---|---|---|
| **Restore the grain fill's activity taper** | It was what closed the ants originally. | The tapered mean is not a fixed point of the amplitude derivation. Making the derivation taper-aware restored the gain to the digit and the slice **still failed to lock**, because the candidate-plan search reads committed fill values and a tapered fill at shift *s* is indistinguishable from an untapered one at *s−t*. |
| **Pin the fill tile so it stops animating** | The fill's sign advances with frame index, so regenerated grain moves at frame rate by design. | Helps, and was **kept** (`--fill-static`, now normative when the fill runs) — but on its own recovers only about a third of the gap. |
| **All-intra (`--refresh 1`) to remove the refresh pulse** | Roughly half the ants level in *both* builds is the rolling intra refresh. | Costs up to **3.3 points of VMAF-NEG** on real footage. The refresh period is a resilience parameter, not an ants knob. |
| **Add the pixel-domain excess back as a coefficient correction** | The obvious in-gamut repair. | The correction rounds away to nothing — mean 3 codes against a quantizer step of 128, with the violation count sitting at exactly 5760 through four passes. Amplifying it diverged: the rate controller coarsened to the worst rung, violations rose from 1020 to 10414, and the encoder crashed. |
| **Clamp the source into an inset window** | Converged faster than anything else. | **Silently wrong.** Generation 2's clamp moved the encoder's own input, the lock failed and the chain broke — while the gamut report read zero and the verdict line said "baseband-safe: yes". Removed outright; removing it also measured *better*. |
| **Make the cross-slice edit conditional near the rails** | Would stop the edit carrying a rail sample out of range. | `f(x) = x + d if in range else x` is **not injective** — both branches land in the same interval — and the un-blend must invert it exactly, forever, from the post-edit value alone. Unavailable at any price. |
| **Spend the in-gamut repair in per-band leverage order** | Coarse coefficients damage far more picture per unit of correction. | Measured **worse**: 95.41 against 96.49. Holding the lowpass band back scored 93.78 against 93.89; never touching it left 74,212 samples out of range and did not converge. A region uniformly past the rail is a *mean* problem and only the lowpass band can move a mean. |
| **Density-adaptive and convergence-adaptive shape selection** | The best shape appeared to depend on how dense the violations were. | Neither beat the fixed rule it selected between; the density threshold did not separate cleanly, and the convergence watchdog landed within 0.02 of a plain rule everywhere. |
| **Per-slice trial selection** | Not a heuristic — repair each slice both ways and keep whichever is closer to the source. | Mixing shapes across the slices of one frame cost **more than either shape alone** (97.4482 against 98.1117 and 97.8220). |
| **The gentle reduction rule on its own** | It was much cheaper in picture than the rule it replaced. | It **did not converge** on rail-pinned graphics: 6 residual samples at 0.5 bpp, 4 at the hard budget cap, so the guarantee was not delivered at all. Kept as the first-choice rule, but with a converging restart behind it. |
| **Return the repair's freed bits to the rate planner** | Removing energy should buy a finer quantizer. | 96.6757 against 96.6991 — nothing. The freed bits are below the granularity the plan can act on. |
| **Tune the repair until it matches the metric on the graphics cell** | One cell scores 0.25 lower with the better rule. | That cell is **3.79 dB of luma closer to the source** with the rule the metric dislikes. Tuning to reproduce a metric's verdict against nearly four decibels of measured fidelity would be fitting the instrument rather than the picture. Left as a recorded disagreement. |
| **`slice_h` 32 as an operating point** | Saves a further 6.5–12% at 4K. | Exceeds the 1 ms latency mandate; the encoder marks it NOT-SHIPPABLE. |

### 7.3 One disagreement left standing rather than resolved

On a 4K graphics master at half a bit per pixel, the shipped repair scores 0.25
**lower** on VMAF-NEG than the rule it replaced while being **3.79 dB of luma
and about 3 dB of both chroma planes closer to the source**. Nine encoder-side
statistics were built to reconcile the two and none can. Decomposing the metric
localises the whole disagreement to ADM at the two coarse scales.

The mechanism is not mysterious: out-of-range samples *are* quantization
overshoot, which is ringing, and on a graphics master at half a bit the
coefficients around a rail excursion are almost all ringing — so a rule that
removes a lot of energy there removes a lot of ringing, and a model built to
refuse credit for detail the source did not have scores that as an improvement.
On camera footage the same neighbourhood holds real texture and removing it is
exactly what the model punishes. Every camera cell prefers the gentle rule, by
much larger margins.

**This is recorded rather than resolved**, and it is worth knowing when reading
any VMAF-NEG figure in this release: the metric has a demonstrated blind spot on
near-edge ringing in graphics content, in the direction of preferring a picture
further from the source.

---

## 8. Building and running everything in this zip

Nothing outside this zip is needed to build the codec or to run any of its
features, including resolution conversion.

### 8.1 Build

```bash
make            # codec, both tools, all six gate binaries, and the
                # conversion/colour tools.  The synthesis-basis table is
                # regenerated from src/dwt.c first, by repro/gen_gm_basis.c.
make test       # 96 assertions across six suites.  Exit code 0 and no line
                # beginning with FAIL is the pass condition.
```

The build has no dependencies beyond a C11 compiler and libm. It has been
built with GCC and with a clang-based front end; the gate binaries need POSIX
declarations, which the Makefile supplies through `TCFLAGS`.

### 8.2 Encode and decode

```bash
# ordinary encode -- strict in-gamut repair is ON by default
./omc_enc -i master.yuv -o out.omc -w 1920 -h 1080 --fmt 422 --depth 10 --bpp 1.0

# decode to ordinary baseband video
./omc_dec -i out.omc -o out.yuv

# decode to CODED-DOMAIN RAW, the interchange that is exact unconditionally
./omc_dec -i out.omc -o out.cdr --cdr

# re-encode a CDR: the repair stands down by itself, no flag needed
./omc_enc --cdr-in -i out.cdr -o gen2.omc -w 1920 -h 1080 --fmt 422 --depth 10 \
          --bpp 1.0 --display-w 1920 --display-h 1080
```

### 8.3 Resolution conversion and colour

Both are in the codec and both have standalone tools, so every feature is
exercisable from this zip alone:

```bash
./omc_uc_tool     # resolution conversion (the OMC-UC upconversion path)
./omc_tf_tool     # transfer function / tone mapping
./omc_unblend_tool  # the reversible cross-slice boundary edit, inverted
```

Conversion is also reachable from the encoder and decoder directly; the
latency model charges it on the display raster and `make test` re-measures the
whole A2 table, including every conversion in the mandate's range from 720p to
4320p at 50 to 120 fps, up and down.

### 8.4 The generation-exactness chains

```bash
# CDR chain -- the guarantee that holds unconditionally
bash tests/genchain.sh master.yuv 1920 1080 422 10 1.0 16 10

# ORDINARY BASEBAND chain -- exact because the in-gamut repair is on
bash tests/genchain_bb.sh master.yuv 1920 1080 422 10 0.5 16 10

# the full matrices
bash tests/run_matrix.sh
bash tests/run_matrix_bb.sh
```

### 8.5 The measurement harness

`tests/` contains every script that produced the temporal results:
`ants.py` (the ants instrument, all three planes), `antsmatrix.sh`,
`gamut_map.py`, `gamut_probe.py`, `strict_cost.sh`, `vmafneg.sh`, `quality.py`,
`seam_repair.py`, `prep.py`, `mkstill.py`, `mkrail.py`, `mkfullrange.py`, and
`basis.c` for the synthesis basis.

## 9. What is NOT in the zip, and why

Stated explicitly so nothing is discovered by surprise.

| not included | why | consequence |
|---|---|---|
| **Test footage** | The corpus is video, not code, and is measured in gigabytes. | Every *exactness* verdict is content-independent and reproduces on any footage. The recorded md5s are content-dependent and will not reproduce without the same masters; `docs/TEMPORAL_T5.md` Appendix C carries their checksums so a holder of the footage can confirm identity. |
| **A VMAF binary and model** | Third-party, separately licensed. | `tests/vmafneg.sh` calls it. The model must be `vmaf_v0.6.1neg` — it differs from the plain model in exactly two fields, `adm_enhn_gain_limit` and `vif_enhn_gain_limit`, both 1.0. **The score key inside libvmaf is called plain `vmaf` in both cases**, which is a trap: reading the key name does not tell you which model ran. |
| **A C compiler and Python 3** | Environment. | Needed to build and to run the harness. |
| **`delivery/clips_5s/`** | Viewing material, not code. | Cited by `docs/LETTER_TEAM_A.md`; recorded in `docs/DANGLING_REFERENCES.md`. |

## 10. Where to read further

| you want | read |
|---|---|
| the normative temporal specification, with every patch and result | `docs/TEMPORAL_T5.md` |
| the bitstream | `docs/BITSTREAM.md` |
| the latency model | `docs/LATENCY.md` |
| the constraints this project is held to | `PROJECT_CONSTRAINTS.md` |
| open decisions and their owners | `OPEN_DECISIONS.md` |
| cited paths that do not exist | `docs/DANGLING_REFERENCES.md` |
| the cross-slice story | `docs/XSL.md` |
| what changed in this release | `CHANGELOG_v5.md` |
| v4-era history, unmodified | everything else in `docs/` |

**On the historical documents.** Everything in `docs/` that predates v5 is left
exactly as it was written and still describes the version it was written for. A
document that says "v4.14" means v4.14. This release does not retroactively
relabel earlier work, and where a v4-era document disagrees with this one, this
one describes v5 and that one describes what it says it describes.
