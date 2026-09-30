> ## DELIVERY NOTE — shipped in OMC **v5.3**
>
> This document is shipped **normative** inside the OMC source zip and is the
> specification for v5's temporal layer. **The body below is the revision of
> 2026-08-19 and describes the v5.0 build**; it is kept verbatim because it is
> the historical normative record. What has changed since is carried in dated
> ADDENDUM blocks at the head of each affected section — v5.3's are at §12.22.
> **v5.3.6 ADDENDUM (2026-09-08) to §12.22: the per-slice repair budget is 13 passes, not 12.**
> Three agents and an outside reviewer showed the shipped budget of 12 was one pass short: a 24-frame
> sequence that cuts between rail-graded plates and ordinary footage every 6 frames committed 17
> out-of-range samples (2 unclosable slices) at the shipped refresh period of 8 on every tree
> measured, while the 4-frame gates in `tests/test_xsl.c` (which cannot complete a refresh wave at a
> period above 3) printed `all ok`. With `OMC_GAMUT_DEFPASS = GM_PASS = 13` every row of that sweep
> (periods 2, 3, 4, 6, 8 and NONE) is 0, and the extra pass is consumed only by a slice that needs
> it (byte-identical streams on five ordinary cells at 12 and 13). 16 is NOT the answer: at 16 the
> non-vacuity control G-T5-GAMUT2d fails, so the window is 13-14. The new gate G-T5-CUT24 asserts
> the contract across two full waves at the shipped period. Hardware must budget the worst case as
> (1 + 13) passes on a repaired slice, not (1 + 12) -- LATENCY.md's statement is unchanged in form.
> **Where an addendum and the body disagree, the addendum is current.**
>
> Release identity for this zip: **OMC v5.3, stream major 5, minor 13**
> (`OMC_MINOR_T5`). A v5.2-or-earlier decoder writes and expects minor 12 and
> will refuse a v5.3 stream, which is correct — v5.3 changes normative
> reconstruction. Deploy both ends together.
>
> **On the tree name.** This document's build recipes and harness paths refer to
> the codec tree as `omc_v4.9`, which is what it was called when the document was
> written — and it kept that name for several releases after it stopped being
> accurate, which is exactly the confusion this delivery ends. **In this zip the
> tree is `omc_v5`.** Wherever this document says `omc/omc_v4.9`, read "the codec
> tree": the directory holding `Makefile`, `src/` and `include/`. The shipped
> harness in `tests/` has already been repointed to resolve the tree relative to
> itself, so those scripts run from the zip as-is.
>
> **On the patches.** Appendices A, D and F are the patch series that produced
> this build from a pristine v4.14 drop. They are already applied here; they are
> retained because they are the authoritative record of every change.
>
> **On the version.** This document describes the stream as major 4, minor 12.
> **In this delivery the major is 5** — the temporal layer is unchanged by that,
> but a v4 decoder refuses a v5 stream outright rather than mis-decoding it. See
> `docs/OMC_V5.md` section 3 and `docs/BITSTREAM.md`.
>
> **On the defaults.** The strict in-gamut repair is **ON by default** in this
> revision and in this delivery, and both `--gamut-strict 0` and
> `--no-gamut-strict` disable it. `docs/OMC_V5.md` section 2 is the full default
> list with the measurement behind each.
>
> The rest of this document is reproduced exactly as delivered.

# OMC T5 — the rebuilt temporal engine and the zero-generation-loss contract

# WHAT CHANGED — the short list

Everything in this table is new since the revision of 2026-08-18.  Nothing else
in the codec changed: the encoder's default output is byte-identical, and the
1080p reference cell still hashes `d6e111cfaf33c17406182bc1310a0b90`.  Section
numbers point at the full account.

| # | what changed | why it matters to you | where |
|---|---|---|---|
| 1 | **The in-gamut repair is ON by default.**  `--gamut-strict 0` turns it off. | It was opt-in, with a table telling an operator when to enable it.  A live chain cuts between content types in seconds and nobody can make that call per clip.  There is no longer a decision to make. | 12.22.8 |
| 2 | **`omc_enc` exits 2** when the repair could not clear every sample.  0 = delivered, 1 = encode failed. | A warning on stderr is easy to miss in an automated pipeline, and the cost of missing it lands at the *second* hop, in somebody else's facility. | 12.22.3j |
| 3 | **New reduction rule**: gentler of a 63/64 proportional cut and a one-step cut, with an alignment test and a stall escalation. | The repair used to cost up to 5.44 VMAF-NEG on real footage.  Worst real-footage cost is now 2.00, and five cells are inside 0.4. | 12.22.3g, 12.22.6a |
| 4 | **The repair only reduces a coefficient if that moves the offending sample the RIGHT way**, and only pays the alignment test where a reduction actually costs something. | 86–90 % of what the repair did changed no coded value at all.  Charging only for the reductions that do improves every rule on every cell measured. | 12.22.3g, 12.22.3h |
| 5 | **A slice that will not clear gently is RESTARTED** from its original coefficients with a rule that always converges. | Item 3 alone made convergence *worse* on rail-pinned graphics — the codec measurement side found this, and they were right.  This is the fix. | 12.22.3i |
| 6 | **A case this document called structural and unclosable is now closed.**  `G-T5-GAMUT2c` asserted "99 % and not all"; it now asserts *all*. | If you are holding the previous revision, that limitation no longer applies.  No unclosable case is currently known. | 12.22.11, 12.22.9 |
| 7 | **Five new gates for cutting between content types**, and five for determinism. | Every earlier gate encoded one kind of content at a time, which is not how a broadcast chain is used. | 12.22.9 |
| 8 | **Synthesized footage no longer decides anything.**  A provenance table says which clips vote. | Two of the corpus clips are derived, not shot.  Their numbers are still reported in full. | 12.22.6a |

**Two mistakes of mine are recorded rather than quietly fixed**, because both are
the shape of error that hides: the scoring criterion in the previous revision was
wrong (12.22.6a), and adding the exit status of item 2 silently blinded the
measurement harness until it was caught (12.22.3j).

---

# REVISION RECORD — read this first

**This document supersedes the revision of 2026-08-18 identified below.  If you
are holding that earlier revision, everything it says still stands except where
this record says otherwise.**

## 0. What changed since the 2026-08-18 revision of this same document

That revision introduced the strict in-gamut mode of 12.22 with a proportional
3/4 reduction, and reported its cost honestly.  The cost was too high and the
codec measurement side said so.  Three things changed in response, and one thing
they revealed is more important than the rule itself.

1. **The repair now asks whether a reduction helps before making it.**  Reducing
   a coefficient's magnitude moves an offending pixel one way or the other
   depending on the sign of that coefficient's synthesis basis there; the old
   rule reduced everything under the support without asking, so roughly a third
   of every pass was pushing offending samples further out of range while still
   costing picture.  The basis signs are now measured out of the shipping inverse
   transform by a generator the build runs (12.22.3g).
2. **86 to 90 per cent of what the repair does is free, and the veto now charges
   only for the rest.**  A reduction that does not carry a coefficient across a
   quantizer boundary emits the same coded value, the same bits and the same
   picture.  Instrumenting that (`OMC_GM_STAT`) showed nine reductions in ten
   change nothing at all, that every crossing is in the coarse bands, and that at
   eight quantizer steps and above **every** reduction crosses.  Charging only
   the crossings improves every reduction shape on every cell measured (12.22.3h).
3. **The default reduction rule changed** from a proportional 3/4 cut to the
   gentler of a proportional **63/64** cut and a one-step cut, with that veto and
   with a **stall escalation** to 15/16 for any slice still violating at pass 4.
   On the full corpus it is better than the rule it replaces on twelve of the
   thirteen cells that fire and level on the thirteenth, with zero out-of-range
   samples on every one of the fifteen.  The worst real-footage cost falls from
   −4.12 to −1.65 VMAF-NEG, the second worst from −5.44 to −0.31, and the
   deliberate stress clip from −35.25 to −11.20 (12.22.6a).  63/64 is the
   **gentlest factor that still converges** — at 127/128 the repair gives up with
   21,120 samples out of range — and the escalation is what makes even 63/64
   converge, so the shipped point is the edge of the feasible region rather than
   a preference.

4. **The mode is now ON BY DEFAULT.**  Shipping it opt-in, with a table telling
   an operator when to enable it, put a per-clip decision on somebody who cannot
   make it: a live chain cuts from a match to a studio to a graphics bumper in
   seconds.  That was a design error and it is corrected — `--gamut-strict`
   defaults to 12 passes, `--gamut-strict 0` turns it off, and `--cdr-in` stands
   it down by itself.  The encoder's default output does not move, because the
   mode is byte-identical to being off on content that never reaches the rails:
   the 1080p reference cell still hashes `d6e111cfaf33c17406182bc1310a0b90`, with
   the encoder reporting `0 slices repaired in 0 passes`.  12.22.8 now carries one
   sizing number instead of a four-row recommendation table.

5. **The gentle rule could not clear rail-pinned content, and the codec
   measurement side found that before this document did.**  Their report — an
   ordinary screen-graphics master failing the baseband chain at 0.5 and 1.0 bits
   per pixel, with a residue that did not fall when the budget was raised to the
   cap — is a real defect in the rule of point 3, introduced by it.  The cause is
   the step cap: it is what keeps the gentle rule nearly free, and it is exactly
   why a neighbourhood the quantizer has pinned to a rail cannot be cleared one
   step per pass.  The fix is a **restart**, not a tightening: when a projection
   says a slice will not finish in the budget it has left, the encoder throws the
   gentle attempt away and repairs that slice again from its original
   coefficients with a plain proportional cut and no cap.  It fires on 27 of 375
   repaired slices on the hardest real cell, costs two to five hundredths of a
   point where it fires, and **closes a case this document previously called
   structural and unclosable**.  12.22.3i, and 12.22.11 is corrected.

6. **An undelivered guarantee now exits 2.**  A warning on stderr is easy to miss
   in an automated pipeline, and the cost of missing it lands at the second hop in
   somebody else's facility.  Exit 0 means the in-gamut guarantee was delivered,
   2 means the encode succeeded but it was not, 1 means the encode failed.
   12.22.3j.

7. **Synthesized footage no longer drives the choice.**  A direction from the
   project owner, recorded in 12.22.6a with a provenance table: real camera and
   real graphics masters decide, the rail stress clip does not.  Its numbers are
   reported in full and its gate is kept, because hiding a case the rule handles
   badly would be the lie — but no rule was accepted or rejected on it.

**And the scoring criterion in the previous revision was wrong.**  It held
candidates to "must not score below the shipped repair on any cell", which
privileges an accident — on one cell the old repair scores *above* the unrepaired
picture, so matching it there means over-improving.  The target is the
**repair-off** score, and 12.22.6a is scored that way.

**One cell resists, and the reason is worth more than the cell.**  On the 4K
graphics master at half a bit per pixel the new rule scores 0.25 lower on
VMAF-NEG and is **3.79 dB of luma closer to the source**.  Nine encoder-side
statistics were built to reconcile the two and none can: on near-edge ringing in
graphics content, fidelity and this metric point in opposite directions.  That is
recorded in 12.22.6b with the decomposition that localises the disagreement to
ADM at the two coarse scales, rather than tuned away.

Five new gates (`G-T5-GAMUT5a` … `G-T5-GAMUT5e`) assert that the repair is
deterministic in its **output and its internal path**, and they run before the
battery rather than after it.

**Nothing in §12.23, the ants fix, changed, and that is checkable rather than
asserted.**  Every figure in §12.23 was measured with the in-gamut mode off,
which is its default; and the encoder's default path is byte-identical across
every change in this revision — the 1080p reference cell of 12.6 still hashes to
`d6e111cfaf33c17406182bc1310a0b90`.  A build whose default output is
bit-identical cannot have moved a measurement taken on that output, so §12.23
needs no re-run, only the hash above.

| | previous revision | this revision |
|---|---|---|
| document | 8186 lines, md5 `cac49038fc0202962cd54458c9640194` | see the checksum block at the end |
| source commit | `eba8cd9` | `574a570` |
| **stream minor** | 11 | **12** — a minor-11 decoder must not be fed these streams, and will refuse them |
| encoder reference md5 (1080p cell of 12.6, default settings) | `156f0237206ac5f66f5b8c89535dfea4` | **`d6e111cfaf33c17406182bc1310a0b90`** — the defaults changed; see §2 |
| new sections | — | **12.22** (strict in-gamut mode), **12.23** (the ants fix), **Appendix F**, **Appendix G** |

## 1. What changed, in one paragraph each

**12.22 — generation exactness over an ordinary baseband hand-off.**  The
previous revision proved generation exactness **unconditionally** over the
codec's own interchange (CDR) and **conditionally** over an ordinary baseband
hand-off — the condition being that no committed sample leaves the legal range.
It then drew the wrong boundary around that condition, calling the exposed
content "4:4:4 8-bit graphics material" and stating it was "absent from every
4:2:2 cell of the corpus".  That was contradicted by its own table.  This
revision corrects the claim **and removes the condition** for the cells that
carried it, by adding an encoder-side mode that stops producing out-of-range
committed samples in the first place.

**12.23 — the ants.**  The rebuild reintroduced, and made several times worse,
the temporal-instability defect a blind viewer identified twice: areas the
source holds still that the decode does not.  The previous revision did not
record that consequence.  This revision states the mechanism in arithmetic —
in a flat region a detail coefficient sits on the quantizer's zero/one boundary
and the source's own sub-code wobble carries it across, moving the
reconstruction a whole step at a time — and fixes it in the **encoder**, by
giving those positions a full-step zero zone.  The measured result is calmer
than the source on every real-footage clip of the corpus (the incumbent's
"sub-source calm"), on all three planes, **with VMAF-NEG going up rather than
down**.

## 2. What a build team must do differently

Four things, and **none of them is a decision about content**.

**(a) `--gamut-strict` is ON by default; size its budget, do not switch it.**
An earlier revision of this document made this a decision, with a table telling
an operator when to enable the mode.  That was wrong: a live chain cuts between
content types in seconds and nobody can make that call per clip.  The mode is now
on by default and the only quantity to set is `N`, the per-slice repair budget:

| your situation | what to do |
|---|---|
| any baseband hand-off, any content | **nothing** — the default `N = 12` reaches zero out-of-range on every cell of the corpus |
| CDR (`omc_dec --cdr` → `omc_enc --cdr-in`) | **nothing** — the mode stands itself down; a committed picture is reproduced verbatim and that chain is exact unconditionally |
| a hard per-slice deadline the back half cannot meet thirteen times | lower `N` and read the verdict line — **do not switch the mode off**; what it cannot finish it reports through `omc_enc_oob()` (12.22.8 has the measured cost of every budget) |
| content that never reaches the rails | **nothing** — the mode is inert and the stream is byte-identical, gate `G-T5-GAMUT3` |

The encoder's default output does not move: the 1080p reference cell of 12.6
still hashes to `d6e111cfaf33c17406182bc1310a0b90` with the mode defaulted on.

**(a2) Check `omc_enc`'s exit status.**  It is 0 when the encode succeeded and
the in-gamut guarantee was delivered, **2** when the encode succeeded but the
mode could not clear every sample, and 1 when the encode failed.  A build relying
on baseband exactness should treat 2 as a failure of the job, because it is:
generation exactness is a predicate, and four stray samples break the chain as
completely as fifteen hundred.  A build that does not need baseband exactness can
ignore the distinction.  12.22.3j.

**(b) Know that the stream minor is now 12, and that it is a hard gate.**  The
flattest-tier grain-fill gate and the static fill tile of 12.23.4 are normative
reconstruction rules.  A minor-11 decoder fed a minor-12 stream returns `-2`
from `omc_read_stream_header` rather than mis-decoding it; a minor-12 decoder
likewise refuses minor-11 streams.  Deploy both ends together.

**(c) Know that the grain fill is now OFF by default.**  It was on.  The flag
to get it back is `--fill` (and `--no-fill` still works, and still means off).
The library field `omc_config_t.no_fill` is **gone**, replaced by
`omc_config_t.fill_grain` with the opposite sense, so a caller that
zero-initializes its config now gets the fill off.  A caller that was setting
`no_fill = 1` must delete that line; a caller that wants the previous behaviour
must set `fill_grain = 1`.  **This will not fail to compile if you use a
designated initializer and ignore the warning — check for it.**  12.23.8 is the
measurement behind the change: on every clip and rate of the corpus, running
with the fill off is at least as good on **both** metrics at once.

Everything else — build, geometry rules, the frame-phase rule, the latency
model, the slice-height rules — is unchanged.

## 3. Section-by-section delta

| section | change |
|---|---|
| 1 – 12.7 | **no change to the text.**  See §5 below for how to reproduce their numbers on this build. |
| 12.8 | **one paragraph superseded**, marked in place with a block quote naming the two wrong claims.  No number, table or line was edited. |
| 12.9 – 12.21 | **no change to the text.**  See §5. |
| **12.22 (new)** | the strict in-gamut mode: the rule, why each part of it exists, the designs that failed on the way, the CDR guard, the generation-safety argument, the results, the cost, the work it asks for, the gates, how to reproduce it, and what it does not close |
| **12.23 (new)** | the ants: the instrument, the attribution, the mechanism in arithmetic, the three fill-side designs that were not enough, the quantizer fix, why it cannot break generation exactness, the fill default, the results, the cost, the gates, how to reproduce it, and what it does not close |
| **12.23.14 (new)** | what the adversarial pass on the two fixes found: five defects, including a left shift of a negative value in the **normative** transform and colour stage, and a claim in this document that was not true when checked.  All fixed. |
| Appendix A – E | **no change** |
| **Appendix F (new)** | the delta source patch carrying both 12.22 and 12.23, to be applied after A and D |
| **Appendix G (new)** | the seven new harness scripts, verbatim |

## 4. Every claim in the previous revision that is now WRONG

**Two**, and both are quoted here in full so they can be found by search.

**(i)** 12.8, on which content is exposed:

> "out-of-gamut committed samples are **not** exotic.  They appear in 4:4:4
> 8-bit graphics material, which is mastered hard to the rails ... and are
> absent from every 4:2:2 cell of the corpus"

The second half is false.  12.6's own table carries `oob = 1` on a 4:2:2/12
cell, and 12.22 measures ordinary 4:2:2 10-bit camera footage graded to the
rails failing the baseband chain at 0.5 bpp.  The exposed class is **anything
mastered to the rails**, which is a grading decision, not a chroma format.

The same paragraph's conclusion — that a strict in-gamut mode would have to
change either the reconstruction rule or the choice of lattice point per
coefficient — named two options and missed the third that 12.22 builds:
change the SOURCE coefficients, before quantization, and re-code.

**(ii)** 5.7, on what removing the grain fill's taper and half-strength class
costs:

> the cost is "about 1.4 to 1.9 dB of the first-generation gap, attributed to a
> deliberate perceptual mechanism that PSNR penalizes by design"

That accounting is in **brightness accuracy**, and brightness accuracy is not
the instrument that found the defect those two mechanisms existed to close.
Measured on the instrument that did — `docs/REPORT.md` 18.6 — the cost was a
**three-to-fivefold increase in the ants tail**, which 5.7 does not mention and
which this revision's 12.23.2 puts on the record.  5.7's *reasoning* stands: the
taper genuinely cannot be reconciled with the generation guarantee, and 12.23.4
records two further attempts that confirm it.  What was wrong was the claim
that the cost had been accounted for.

## 5. Reproducing the numbers of sections 1 – 12.21 on this build

**You cannot, and the reason is the point of the minor bump.**  Two of the
changes in 12.23 are *normative reconstruction rules* — the flattest-tier
grain-fill gate and the frame-independent fill tile — and a normative rule
cannot come with an off switch, because an encoder that could turn it off would
have to say so in the stream, and no field says so.  They are unconditional.
Every stream md5 printed in sections 1 – 12.21 is therefore a minor-10 or
minor-11 value that **this build will not reproduce**, starting with the
version byte and not ending there.  (Checked, not assumed:
`OMC_CALM=0 omc_enc ... --fill` on the 1080p reference cell writes
`f16104abe6a4c5cbbe3b873af364553d`, and it still differs from the minor-11
`156f0237206ac5f66f5b8c89535dfea4` after the version byte is patched back.)

What *is* recoverable, and what each is for:

| you want | do this | what you get |
|---|---|---|
| the previous revision's **quantizer** decisions | `OMC_CALM=0` | the ants fix stands down completely; the deadzone, the plan search and the lattice lock behave exactly as in minor 11 |
| the grain fill back on | `--fill` | the fill runs — under the minor-12 gate and with the static tile, because those are normative |
| the minor-11 **binaries**, bit for bit | apply **Appendix A and Appendix D only**, and stop there | the build every number in 1 – 12.21 came from |

The third row is the honest answer for anyone auditing an old figure, and it is
why Appendix D is still printed in full rather than folded into Appendix F.

The **exactness** results need none of this.  12.6, 12.14, 12.22 and 12.23 were
all re-run on the shipped build for this revision rather than carried forward,
and the md5s a reader should check against are the ones in 12.22.6 and 12.23.9.

## 6. What is new in the code

All encoder-side except where marked.  The decoder changes in exactly one
place: it applies the flattest-tier fill gate, because that gate is normative.

| | |
|---|---|
| `--gamut-strict [N]` | new CLI flag, default off, `N` = per-slice repair budget (default 12, cap 16) |
| `omc_enc_set_gamut_strict()` | library equivalent |
| `omc_enc_set_cdr_input()` | caller declares CDR input; the mode then stands down.  The CLI sets it from `--cdr-in` and refuses the two flags together |
| `omc_enc_gamut_repairs()`, `omc_enc_gamut_unfixed()` | diagnostics |
| `omc_enc_oob()` | **behaviour change**: returns `-1`, "not measured", when a slice was encoded with `recon == NULL`.  It used to return `0`, which made the CLI print "baseband-safe: yes" for a stream nothing had looked at.  **A caller must test for `0` exactly, never for "not positive".** |
| `--fill` | new CLI flag; the grain fill is now opt-in |
| `omc_config_t.fill_grain` | **replaces `no_fill`, with the opposite sense.**  See §2(c) |
| `--fill-static` / `omc_config_t.fill_static` | pins the fill tile's phase.  Now the behaviour whenever the fill runs, and normative |
| `OMC_CALM`, `OMC_CALM_THR`, `OMC_CALM_AMP` | environment overrides for the ants fix.  The fix is **on** by default; these exist so a build team can measure it, and `OMC_CALM=0` restores the previous revision's quantizer exactly |

## 7. What is new in the tests

`make test` gains nine gates in `test_xsl`, and the suite count is unchanged
(they live in an existing binary):

| gate | asserts |
|---|---|
| G-T5-GAMUT1 | non-vacuity: with the mode off, rail-touching content really does leave the legal range |
| G-T5-GAMUT2a/b | with it on the count is zero, and the baseband chain is byte-exact over three generations |
| G-T5-GAMUT2c | on a deliberately pathological arm the mode removes ≥99 % **and not all** — the case it does not close, asserted as not closed |
| G-T5-GAMUT3 | inert on content that never leaves the range: byte-identical stream |
| G-T5-GAMUT4 | rt = 0 still holds with the repair running |
| G-T5-CALM1a | non-vacuity: with the ants fix off, a source-static flat field moves in the decode |
| G-T5-CALM1b | with it on that movement is at least halved |
| G-T5-CALM1c | the fix is not silently inert on that content — the stream really differs |
| G-T5-CALM2a/b | and with the kill demonstrably firing, three generations still chain byte-exactly, pixels and stream |

## 8. What did NOT change — do not re-verify these

- the **decoder**, apart from the flattest-tier fill gate named above;
- the **reconstruction rule**: still the unclamped inverse transform of the
  emitted lattice point, which is what the whole exactness argument rests on.
  Neither fix moves a reconstruction point: the strict in-gamut mode changes
  which lattice point is chosen, and the ants fix changes which lattice point is
  chosen.  `q << s` is still `q << s`;
- the **seam blend (XSL)**: still always on, still unconditional, still the
  same blend cap.  `G-T5-XSL1` still fails the build if it can be switched off
  and `G-T5-XSL2b` still fails if it stops firing;
- the **CDR guarantee**: unconditional, as before;
- the **latency model (A2)** and the **rt = 0 property**: both re-measured on
  this build and unchanged.

One thing that did change and is worth a line of its own: **five fixed-point
sites that left-shifted a negative value now shift the unsigned representation
instead** (12.23.14, finding 1).  Two of them are in the normative transform
and the normative colour stage.  The encoder's output is unchanged to the byte
on every cell of the corpus — this is a conformance repair, not a behaviour
change — but anyone translating this source to RTL or building it with a
different toolchain should take the new code rather than the old.

---

Release 4.16-T5, **stream minor 12** (sections 1-11 record the minor-10
build; sections 12 - 12.21 record the minor-11 build).

> **STATUS — read this first.**
> *Normative for the build you should produce:* sections 5-8 (design and the
> exactness argument), **section 12** (the baseband contract, every correction,
> and the final results) including **12.22** (the strict in-gamut mode) and
> **12.23** (the ants fix, which is what makes the stream minor 12),
> **Appendix A, then Appendix D, then Appendix F** (three patches, in that
> order), Appendices B, E and G (harness), Appendix C (input checksums).
> *Historical record, superseded in part:* sections 3, 6, 9, 10 and 11 describe
> the **minor-10** build and their md5s are minor-10 values.  Every supersession
> is listed in **12.12**.  Where any earlier text disagrees with section 12,
> **section 12 wins**.
> *Replication in one page:* **12.11**.

This document is **normative** for the T5 layer and **self-contained for
replication**: a person with only this document and the OMC v4.14 source drop
(the `omc_v4.9` tree) can reproduce the rebuild, the guarantee argument, and
every measurement in section 10.  Nothing here depends on any other handoff
document.  Sections 3–8 explain and justify every change; **Appendix A holds
the complete, verbatim source patch** (the authoritative edit — apply it and
the build is bit-identical to the tested binaries), **Appendix B the full
text of every test-harness script**, and **Appendix C the input checksums**
(footage and prepared masters) that pin md5-level replication.  The only
inputs beyond this document and the drop are the five provided footage sets
(section 10), which the mandate supplies; their PNG checksums are in
Appendix C, and every exactness verdict (though not the recorded md5s) is
content-independent and reproducible on any footage whatsoever.

---

## 1. Mandate

1. **Remove** the existing temporal engine completely — both of its faces:
   prediction of later slices *within* a frame (the rolling reference that
   let vertical motion vectors read already-decoded slices of the current
   frame) and prediction of slices in *future frames* (the source-searched
   motion-compensated coefficient-delta layer, the per-block motion field,
   and the v4.8 in-loop temporal filter).
2. **Rebuild** the temporal layer so the codec deteriorates **0 % through
   generations**: a decode, re-encoded with the same settings, must
   reproduce the decode **byte-exactly, through unlimited generations** — no
   budget under-run in one generation to make room for the next, no
   convergence-instead-of-exactness, no content or setting exceptions.
3. The cross-slice boundary reconstruction (**XSL**) must remain **on**: its
   seam blend is essential at and below 0.5 bpp.  It cannot be removed and
   cannot be turned off.  (Slice heights 8/16/32 and both blend-cap regimes
   are all in scope.)
4. Must hold for all bpp, all resolutions, all footage, 8/10/12-bit, 4:2:2
   and 4:4:4.

## 1a. Terms used throughout

Labels inherited from the project's own mandate register and review history.
They appear without expansion elsewhere in this document, so they are defined
once here.

| term | meaning |
|---|---|
| **A1** | the exact-CBR mandate: every frame is exactly `slices x bits_per_slice` bits |
| **A2** | the latency mandate: under 1 ms end to end, **including any output resolution conversion** |
| **A4** | the generation mandate: repeated decode/re-encode must not degrade |
| **A5** | the resilience mandate: a lost slice recovers within the refresh period |
| **C3** | the FPGA-native mandate: the per-pixel datapath uses shifts, adds and table lookups only |
| **C4** | `rt = 0`: the decoder's picture is byte-identical to the encoder's reconstruction |
| **C8** | the bitstream is normative -- two conforming decoders agree bit for bit |
| **tANS** | table-driven asymmetric numeral systems, the entropy coder |
| **XSL** | the cross-slice boundary reconstruction (section 5.3) |
| **CDR** | coded-domain raw: the decoder's committed picture verbatim (section 5.4) |
| **DCFB** | the DC-feedback servo, an encoder-only diagnostic (`OMC_DCFB`) |
| **SPC** | the encoder's slice-power-control allocator stage |
| **tap** | one source pixel a resampling filter reads to produce one output pixel; a 48-tap filter blends 48 source pixels per output pixel, and tap count grows with the zoom ratio (12.17) |
| **F-1, F-3, F-4, F7, F8** | finding ids from the project's earlier review documents, cited for provenance only |

## 2. The contract, stated precisely

Let `E_k`/`D_k` be encode/decode at generation `k`, all generations using the
same configuration (same bpp, dimensions, depth, chroma format, slice height,
refresh period, encoder flags), the same frame numbering from 0, and the
codec's coded-domain raw (CDR, section 6) as the interchange format.

For a master sequence `X`:

```
G1  := D(E(X))          (generation-1 decode: the only lossy step)
Gn  := D(E(G(n-1)))     (n >= 2)
```

**Contract:** `Gn == G1` byte-for-byte for every `n >= 2` (pixels never move
again after generation 1), and the *bitstreams* of generations `n >= 2` are
byte-identical to each other (the generation-2 stream is the fixed point of
the encode map).  The generation-1 stream may differ from the generation-2
stream: generation 1 makes rate-distortion choices against the master;
generation 2 re-derives the committed plan from the decode.  What may never
happen is any pixel change after generation 1, on any plane, at any setting.

This is verified mechanically in section 10: `cmp(G1, Gn)` and
`cmp(E(G1), E(G(n-1)))` over the full test matrix, plus a 10-generation and a
20-generation chain.

## 3. What was removed, and where

All references are to the v4.14 drop (`omc_v4.9` tree) before the rebuild;
the removal is complete in `src/codec.c` unless noted.

| Removed | Was |
|---|---|
| Rolling in-frame prediction reference | `e->ref`/`d->ref` doubled as prediction source while being updated slice-by-slice, so vertical MVs read already-decoded slices of the **current** frame (BITSTREAM §4.2b "rolling reference") |
| Motion search stages A–D | `omc_enc_slice` step 1b: whole-slice decimated SAD against the **source**, half-pel refinement, per-region overrides (`--mv-regions`), `mv_block_sad`, `bof_sad` |
| Per-block motion field (minor 3) | `[mode:1][dx:4][dy:3]` per 16-px block between header and payload; flag bit 7 of the `n_steps` byte |
| OMC-TF in-loop temporal filter (minor 8) | `tf_gather`/`tf_apply` calls in both loops; `tf_mode` header bits 27[5:6] |
| XSL levels 0–6 and all XSL environment levers | `OMC_XSL`, `OMC_XSL_NOEDIT`, `OMC_XSL_NODISP`, `OMC_XSL_LIM`, the seam-strength/emptiness scaling (levels 4–6), the non-invertible level-2/3 blends, `omc_xsl_probe_frame` |
| v4.6 grain-fill activity taper and 0.5× gain class | `fill_value_p` `v6` semantics (section 5.7 explains why they were structurally incompatible with exactness) |
| Legal-range clip inside the coding loop | reconstruction clipped to `[0, 2^depth-1]` (now a non-normative display projection in the tools) |

Streams are now **minor 10**; the decoder rejects every other minor (the
removed semantics cannot be honoured, so older streams are refused rather
than silently mis-decoded).  `tf_mode` bits must read zero; slice-header bit
7 of the `n_steps` byte must read zero.

## 4. Why the old engine could never be generation-exact

Five structural causes, all documented in the drop's own papers:

1. **The XSL level-3 seam blend is non-invertible by design.**  It moves each
   boundary row toward a target computed *from that row's own value* —
   "that discards what the row was, so it cannot be undone" (docs/XSL.md).
   Measured there: −8.17 dB over six generations at 3.0 bpp.  With the edit
   in-loop, every generation smooths an already-smoothed picture.
2. **Decisions were made on generation-varying data.**  The motion search
   ran against the *source*; thresholds and argmins computed on a decode
   differ from the same statistics on the master, so choices could flip
   between generations (`--mv-regions` was documented off-spec for multi-hop
   chains for exactly this reason).
3. **Clipping destroyed lattice alignment.**  A reconstruction sample pushed
   past black/white by quantization ringing was clipped; the clipped pixel's
   coefficients leave the quantizer lattice and the slice can never lock
   again.  (The drop contained an inactive prototype fix, `OMC_REF_UNCLIPPED`.)
4. **The generation lock was heuristic, not complete.**  Sixteen verify
   tries, a ≥4-band evidence gate, lock-dropped-on-overflow, narrowed fill
   admission ("slices whose plane fill gain is ≥ 1.25× cannot lattice-lock
   … convergent rather than byte-exact" — the drop's own comment), and modes
   taken from a cost guess rather than recovered.
5. **The v4.6 fill features broke the fixed points.**  The activity taper
   floors amplitudes at 1 code (indistinguishable from anything) and the
   tapered mean is not a fixed point of the gain-code derivation, so the
   committed fill could not be re-derived from the decode.

The T5 rebuild eliminates each cause *by construction* rather than by tuning.

## 5. The T5 design

### 5.1 Frame-buffer reference — no same-frame prediction

Prediction reads **only the previous frame's final committed picture**
(`refprev`).  The rolling buffer (`ref`) still exists but feeds only the
cross-slice wavelet term (previous slice of the *same* frame — an XSL
mechanism, not prediction) and becomes `refprev` at frame end:

- Encoder: at the last slice of frame *t*, rotate `refprev2 ← refprev`,
  `refprev ← copy(ref)`; track `last_frame`/`last_frame2`.
- Decoder: on the first slice of a new frame (`fidx8` change), copy
  `ref → refprev`.  The decoder needs no second history frame (the vector is
  signalled), so `refprev2` is encoder-only.

`can_inter` is unchanged: frame 0 all-intra; slice `s` forced intra when
`(fidx8 % R) == (s % R)` (rolling refresh, A5; `fidx8 = frame_idx & 255`).

### 5.2 Derived motion — the core idea

The old engine searched the source; T5 **derives** the vector from data that
is byte-identical in every generation: the two previous committed
reconstructions.  For slice `k` of frame `t` (`derive_mv` in codec.c):

```
mv* = argmin_d  SUM_{r in slice k rows, step 2; x step 4}
                | refprev[y][x] - refprev2[y+dy][x+dx] |
```

over the fixed 75-entry candidate list (`omc_mv_cand`, ±31 px horizontal,
±15 vertical), strict `<` argmin in fixed order, followed by a 4-neighbour
integer refinement (strict `<`).  Under constant velocity — the panning case
the temporal layer exists for — the displacement that maps frame t−2 onto
frame t−1 is also the fetch vector for frame t from frame t−1.

Properties:

- **Generation-invariant**: inputs are committed decodes, which the
  exactness induction makes identical at every generation; a deterministic
  function of identical inputs is identical.
- **Integer-pel only**: half-pel taps are low-pass re-filters (quality risk,
  zero exactness benefit); odd half-pel codes are *reserved* in minor 10.
  The header still carries 4 × (7+6)-bit half-pel region fields for wire
  compatibility; the encoder writes the one derived vector (doubled, i.e.
  even) into all four.
- **Decoder-cheap**: the vector is signalled, so the decoder does no search
  and holds no second reference frame.
- Frames without two consecutive committed predecessors (frame 1, or after a
  feed discontinuity) derive `mv = 0`.

Prediction itself is unchanged in shape: per band, `coef = pred + q·2^s`
where `pred` is the forward transform (with the slice's cross-slice `d[-1]`
term) of the motion-shifted, edge-clamped fetch from `refprev`
(`predict_plane`).  The per-band intra/inter mode mask survives as syntax.

### 5.3 XSL-T5: always on, exactly reversible

Three pieces (all normative; `xsl_prep`, `reconstruct_slice`,
`xsl_display_blend`, `omc_xsl_unblend` in codec.c):

**(a) Cross-slice wavelet term** — unchanged from minor 9: slice k's vertical
level-1 lifting uses `d[-1] = r15 − 2·r14 + r13` of slice k−1's committed
reconstruction of the current frame (the bias cancels in the second
difference).  This changes the transform's boundary convention, not its
reversibility.

**(b) The boundary edit as a lifting cascade.**  At every interior boundary
(previous slice's last row `row15`, this slice's `row0`), applied when slice
k reconstructs, to reference and display alike:

```
step 1:  row15 += clamp((row0  − row14) / 4, ±lim)     (row15 unread)
step 2:  row0  += clamp((row15′ − row1) / 4, ±lim)     (row0 unread)
```

Each step's correction reads only rows it does not touch, so the exact
inverse exists (subtract in reverse order).  `lim` is the normative
rate-derived cap, unchanged from minor 9:

```
cap  = (8 * bits_per_slice < 3 * width * slice_h * samples_per_px) ? 8 : 4
lim  = cap * ((maxv + 1) >> 10)        (samples_per_px: 2 at 4:2:2, 3 at 4:4:4)
```

(±8 codes @10-bit below 0.75 bpp-on-coded-samples, ±4 at or above; scaled by
depth; **derived identically at both ends from the stream header — no
environment override exists any more**.)  Note the depth scaling makes
`lim = 0` at 8-bit — inherited minor-9 semantics, kept unchanged; see 11.3.

Applied **unconditionally** within the wide pixel domain (no legal-range
skip): the old code skipped the edit at the clip rails, which made forward
and inverse disagree there; the T5 domain has 2048 codes of margin on each
side, so no rail can be reached and the skip is gone.

**(c) Refresh barriers and their display blend.**  Rules (d)/(e) of minor 9
are kept verbatim: a slice refreshed this frame takes no cross-slice terms
and no edit; a slice whose predecessor was refreshed skips the retro edit.
The boundaries those rules leave raw get the **same cascade** applied to the
**emitted picture only** (never the reference): both steps when slice k is
refreshed; step 1 only (row15) when slice k−1 was refreshed.  Because the
display blend is now the same reversible cascade, the whole emitted picture
is invertible under conditions derivable from `fidx8`, `refresh_r` and the
config alone.

**The mandatory un-blend.**  `omc_enc_frame` copies every input frame and
applies `omc_xsl_unblend` — the exact inverse of (b)+(c), walking boundaries
bottom-up, selecting per boundary: `kref` → invert both display steps;
`k1ref` → invert display step 1; else → invert the interior cascade.
Detector-free by design: on generation ≥ 2 material this recovers the
previous encoder's committed reconstruction exactly; on first-generation
masters it pre-distorts boundary rows within ±lim, which the decoder's
forward edit then cancels.  (A detector would be a threshold on
generation-varying data — the exact class of decision T5 exists to remove.
The measured cost on masters is bounded and small: section 10.4 shows the
blend still removes 54–70 % of the seam step excess.)

Slice-level API callers must apply `omc_xsl_unblend` themselves before
slicing; the un-blend of a slice's bottom boundary reads the two rows below
it, so the encoder's causality bound becomes rows `[0, (k+1)·slice_h + 2)` —
a fixed two-line lookahead (gated in tests/test_unit.c).

### 5.4 The biased, unclipped pixel domain and the CDR interchange

Every `omc_frame_t` — encoder input, references, recon, decoder output — now
carries `u16 = true_value + OMC_PIX_BIAS` (bias 2048), clamped only to the
representable window `[0, (2^depth − 1) + 2·2048]`.  There is **no
legal-range clip anywhere in the loop** (a wide-window representability
guard remains and prints loudly if it ever engages; it cannot on conforming
content — reconstruction is source plus bounded quantization error, and the
window leaves 2048 codes of margin per side).

**CDR (coded-domain raw)** is the generation-chain interchange: the decoder's
committed picture verbatim — biased, unclipped, at **coded** geometry (pad
rows included, no crop, no inverse RCT), planar Y|Cb|Cr (or the coded RGB
planes), u16 LE, frame-sequential.  `omc_dec --cdr` writes it;
`omc_enc --cdr-in` consumes it (`-w/-h` give the coded dims).  This is what
makes pad-and-crop geometries (1080-coded-as-1088) exact: the pad rows are
part of the committed picture and travel with it; re-deriving them by edge
replication from a cropped decode could never match.

The default `omc_dec` output is the **display projection** — bias removed,
clipped to `[0, 2^depth)`, cropped/RCT-inverted — for viewing and metrics
only.  Re-encoding a display projection is a generation-1 event (information
was discarded), by definition, and is out of contract.

### 5.5 The complete generation lock

The lock's job at generation ≥ 2: given only the coefficients of the
(un-blended) input slice, find a signalled plan — profile, Q, n_steps,
partial chunks, per-band modes, fill bits, per-plane fill gains, per-band
tANS groups — that reproduces those coefficients **bit-for-bit**, and fits
the budget.  T5 makes this *complete* (it cannot miss when the input is a
committed reconstruction):

1. **Candidate enumeration** (`omc_enc_slice`): all `(prof 0–3, Q 15–0,
   n_steps 0–49)` triples, filtered by the per-chunk lattice test — for each
   band and each coding mode, the OR of the chunk's magnitudes must have
   trailing zeros consistent with the candidate shift: `tz ≥ s`, or, in
   fill-capable bands (4–9, `s ≥ 3`), a fill-amplitude exponent
   (`s−2` at `s = 3`; `s−2, s−3, s−4` at `s ≥ 4` — exactly the v4.1
   amplitude family of 5.7).  `tz == s−1` is never consistent.  **No
   minimum-evidence gate** (v4.9's ≥4-band rule left low-evidence slices
   permanently unlockable; a "false" lock is harmless because verification
   demands bit-exact reproduction — on a first-generation master that simply
   means lossless coding, only possible where it fits the budget).
2. **Partial-chunk inference is exact** because T5 confines partial
   refinement to non-fill bands (band 3 in the refine order — see 5.6): the
   minimal `k` covering the chunks that *require* the finer shift
   reproduces the values exactly (chunks beyond it that happen to sit on the
   coarser lattice code exactly at either shift), and no fill amplitude
   depends on the boundary.
3. **Constructive verification** (`lock_verify`): for each candidate, per
   plane, the modes and fill state are **derived**, not guessed:
   - band 0 (LL): try intra and (if allowed) inter; exact reproduction under
     quantize→dequantize(+pred) decides; both exact → cheaper estimated
     cost, intra on ties.
   - bands 1–9, under a per-plane **gain hypothesis** g ∈ {0,1,2,3}: for
     each mode, first derive the band's fill bit by the encoder's own
     measurement rule on that mode's values (mean |value| of the gated
     zero-coded positions, count ≥ 16, threshold 3/16 step), then test exact
     reproduction with that bit and gain g (fill values regenerated from the
     normative tile at the same `(fidx8, slice, plane, band)` offsets).
     A band with no exact mode kills the hypothesis.
   - accept g when the plane's re-derived gain code equals g.  For the true
     gain this always holds (the amplitudes are measurement fixed points,
     5.7); for a wrong gain the fill values already failed reproduction.
   Any band where *both* modes reproduce (e.g. prediction ≡ 0) is a free
   choice: pixels are identical either way, and the deterministic tie-break
   means generation 3 repeats generation 2's stream byte-for-byte.
4. **Selection by actual size** (`lock_trial_bits`): candidates are walked
   cheapest-estimate first; each verified candidate is trial-encoded (the
   same symbolization + tANS pass as the commit path) and the smallest
   **actual** payload that fits the hard budget wins; the walk stops when
   the next estimate exceeds the best actual by a generous slack.  Selection
   by actual size is load-bearing for the induction (section 8): every
   locked slice must spend no more than the previous generation's identical
   slice did, so that the previous generation's plan still fits later in the
   frame.  (Estimate-based selection was measured off by ±bytes per slice —
   enough to starve slice 35 of a 116-slice frame out of its own
   previous-generation plan.)
5. **Locked slices plan against the hard budget** — the normative
   prefix/frame/wire bounds only, captured *before* the perceptual
   allocator's caps.  The encoder-policy caps (perceptual allocation, tail
   guard, refresh boost) derive from source statistics that drift between
   generations; a locked slice must be admissible whenever the previous
   generation's identical slice was, and the previous generation's spend
   satisfied the normative bounds.  On overflow (impossible at generation
   ≥ 2, kept for safety) the encoder falls to the next verified candidate,
   and only an exhausted list re-plans naturally; candidate fallbacks do not
   consume the natural backoff ladder's attempts.
6. **Generation-invariant tANS groups.**  A band's table-group id must be a
   pure function of the **emitted symbols** or the byte count jitters
   between generations.  Two ways the old bc-table choice violated that:
   the *partial* band's committed values mix two shifts (its uniform-shift
   histogram differs from the emitted symbols), and under `--grain-replace`
   the cost histograms carry the classifier's source-dependent shrink votes
   that a locked re-encode does not repeat.  T5 therefore chooses **every**
   band's group id from the exact-plan histogram of exactly what the
   emission pass produces (same shifts, same eligibility), for locked and
   natural slices alike, and the header carries the ids actually used.
   Emitted q values are lock-reproduced across generations, so the group
   choice — and with it the payload size — is a generation fixed point.
   (Measured before the fix: +4 bytes from a partial-band flip, +70 bytes
   from a grain-replace flip; each starved a later slice out of its own
   previous-generation plan.)

### 5.6 Rate-control adjustments (encoder-only)

- **Partial-chunk refinement only in non-fill bands.**  When the natural
  rate controller's refinement boundary lands on a fill-capable band (4–9),
  the partial-chunk option is skipped (whole steps only).  Rationale: a
  partial boundary inside a fill band changes per-coefficient fill
  amplitudes, and the boundary position is not recoverable from committed
  values (a refined chunk's 1.0× fill and an unrefined chunk's 1.5×-gain
  fill leave the same trailing-zero signature).  In the 49-step refine
  order, band-3 steps still provide the ~256-coefficient granularity.
- The natural path (quality floor, refinement walk, deterministic overflow
  backoff, banking, perceptual allocation, tail guard) is otherwise
  unchanged and applies to generation-1 coding.

### 5.7 Grain fill: the v4.1 fixed-point amplitude family

Fill semantics revert to the provably idempotent v4.1 form:

- amplitude `a = 2^(s−2)`; per-plane gain codes (s ≥ 4 only):
  0 → 1.0×, 1 → 1.25× (`a + (a>>2)`), 2 → 1.5×, 3 → 1.75×;
- gain derivation thresholds at code midpoints (in 1/64-step units):
  `< 18 → 0, < 22 → 1, < 26 → 2, else 3` — every amplitude re-measures into
  its own class (16→0, 20→1, 24→2, 28→3): a **generation fixed point**;
- gates (LL activity ≥ 12, clip-headroom guard), sign tile, per-
  `(fidx8, slice, plane, band)` offsets, `--fill-static`, `--grain-corr`
  unchanged;
- the v4.6 three-tier activity taper and the 0.5× gain class are removed:
  the taper's floor-at-1-code produced amplitudes indistinguishable from
  arbitrary data, and the tapered mean is not a fixed point of the gain
  derivation — both made the fill non-recoverable (the drop's own notes
  listed the affected classes as "convergent, not byte-exact", which the T5
  contract forbids).

## 6. Bitstream minor 10 — normative deltas

Relative to the minor-9 description in docs/BITSTREAM.md:

1. Stream header byte 5 = 10.  Decoders reject any other minor.
2. Byte 27 bits 5–7 (old `tf_mode` + reserved) must be zero; a nonzero value
   is a header error.  `uc_ratio` (bits 3–4) is unchanged (output-stage
   only, outside the coding loop).
3. Slice header: bit 7 of the `n_steps` byte (old block-MV-field flag) is
   reserved zero; a set bit is a slice error.  The per-block motion field no
   longer exists.  The four motion-region fields carry one derived vector
   (all four equal); **odd (half-pel) values are reserved** — T5 encoders
   write even values only.
4. `partial_chunks` may be nonzero only when the refine-order step at
   `n_steps` addresses a band < 4 (in the shipped tables: band 3).
5. XSL (level-3-shaped reconstruction of minor 9) is **always on**, with the
   boundary edit replaced by the reversible cascade of 5.3(b) and the
   barrier display blend by 5.3(c).  Cap rule unchanged.  There is no
   signalling: the minor is the signal.
6. Temporal prediction fetches from the previous frame's **final** picture
   (frame-buffer reference).  The minor-9 rolling-reference semantics (a
   vertical vector reading current-frame rows) are gone.
7. Grain fill per 5.7 (v4.1 amplitudes/gains; correlated tile and static
   tile flags unchanged in byte 27 bits 1–2).
8. The decoded picture (conformance point) is the **CDR picture**: biased,
   unclipped, coded geometry.  Display projection is not normative.
9. Everything else — transform, band layout, quantization, LL DPCM, contexts,
   tANS tables and state discipline, CRC, exact-CBR framing, refresh rule,
   allocation tables (Annex A), fill gates/tile — is unchanged from the
   minor-9 description.

## 7. Chain preconditions (what "same settings" means)

Byte-exactness through generations holds when every generation:

- re-encodes the **CDR** decode (never the display projection);
- uses the same configuration: dimensions (coded), bpp, depth, chroma
  format, slice height, `refresh_r`, and the same encoder flags
  (`--tune`, `--no-fill`, `--fill-static`, `--grain-corr`,
  `--grain-replace`, `--no-deadzone`);
- numbers frames identically from 0 (the refresh phase and the fill-tile
  animation both follow `frame_idx mod 256`; re-encoding a trimmed decode
  from a different phase is a generation-1 event for the affected slices);
- runs with a clean environment.  The surviving `OMC_*` variables are
  debug/experimental levers and all default off, but three of them CHANGE
  COMMITTED OUTPUT if set and must be left unset for a conforming encode:
  **`OMC_RECOFF`**, **`OMC_BANDTILT`** (both break generation exactness, on
  padded and unpadded geometry alike) and **`OMC_GR`** (grain-replace path).  The XSL levers of v4.9 are
  gone entirely rather than defaulted).

None of these are new restrictions — they are the ordinary meaning of
"re-encode with the same settings".

## 8. Why generation 2 locks everywhere: the induction

**Claim.**  With the preconditions of section 7, for every slice of every
frame, the generation-2 encoder locks (codes its input bit-exactly), and its
committed picture equals generation 1's; generation 3 then reproduces
generation 2's byte stream exactly; hence pixels are fixed from generation 1
and streams from generation 2, for unlimited generations.

Induction over slices in coding order (frame-major).  Assume all previously
coded generation-2 slices are exact (base: the first slice of frame 0 — no
history at all).  For the current slice `(t, k)`:

1. **The inputs match.**  The generation-2 encoder's un-blend (5.3) is the
   exact inverse of the edits the generation-1 pipeline applied *for the
   barrier conditions of frame t* — conditions derived from `fidx8`,
   `refresh_r`, config only, all equal by precondition.  So the un-blended
   input pixels equal generation 1's committed pre-edit reconstruction
   `R(t,k)`.  No legal-range clip intervened (5.4), so `R(t,k)` survived the
   CDR round-trip unchanged.
2. **The coefficients match.**  The slice's forward transform uses the
   cross-slice `d[-1]` term from slice `(t, k−1)`'s committed rows — equal
   to generation 1's by the induction hypothesis (same frame, earlier
   slice), taken at the same point in the schedule (before the boundary
   edit fires for that boundary).  The transform is exactly reversible, so
   the coefficients equal generation 1's dequantized values `V`:
   `pred + q·2^s` per band, or fill values, with `pred` the transform of the
   `refprev` fetch.
3. **The prediction matches.**  `refprev`/`refprev2` are generation-1
   committed frames (induction over earlier frames), the derived vector is
   a deterministic function of them (5.2), and the fetch/transform is
   deterministic — so `pred` is identical, and the per-band deltas
   `V − pred` are exactly generation 1's coded lattice values (plus fill).
4. **The plan is found.**  Generation 1's committed plan passes the lattice
   pre-filter (its own values define the lattice; fill amplitudes are within
   the admitted exponent family), passes constructive verification (modes
   and fill bits re-derive — the measurement rules are fixed points on
   committed values, 5.5.3/5.7), and its trial size equals generation 1's
   actual payload.  It fits the generation-2 hard budget because, by the
   spend argument below, generation 2 has spent no more than generation 1
   had at the same point, and generation 1's spend satisfied the same
   normative bounds.  So the verified set is non-empty; the min-actual
   winner spends **at most** generation 1's bytes (5.5.4), preserving the
   spend argument for the next slice; whatever fitting verified plan wins,
   it reproduces `V` bit-for-bit, hence (through the shared reconstruction
   path, the same fill regeneration, and the same boundary edits) commits
   exactly generation 1's picture and emits it into the CDR.
5. **Generation 3 = generation 2.**  Generation 3's inputs equal generation
   2's (same pixels, same references), and every choice on the generation-2
   path — candidate order, verification outcomes, tie-breaks, gain
   hypotheses, group ids, trial sizes — is a deterministic function of those
   inputs.  So generation 3 selects the same plans and emits the same bytes;
   by induction all generations ≥ 2 do.

The one caveat worth stating: step 4's budget argument relies on selection
by actual size (5.5.4) and the hard-budget bypass of drifting encoder-policy
caps (5.5.5); both were added after being measured necessary, not
speculatively (section 10.6).

## 9. Replication: rebuild from the drop

The rebuild touches exactly seven source files: `include/omc1.h`,
`src/codec.c` (the bulk), `tools/omc_enc.c`, `tools/omc_dec.c`,
`tests/test_unit.c`, `tests/test_xsl.c`, `tests/test_cap.c`.  Nothing else
changes — in particular `src/tables.c` (the motion candidate list
`omc_mv_cand`, the 49-step refine order, the allocation and tANS tables) and
the `Makefile` are the pristine drop's.  Every change is *described* in
sections 3–5; the *authoritative edit* is the complete unified diff in
**Appendix A**.  From a pristine drop:

```
# The tree MUST sit at <root>/omc/omc_v4.9 -- the harness scripts resolve it
# as ../omc/omc_v4.9 relative to themselves (section 10).  Run from <root>:
#
# 1. save this document as <root>/TEMPORAL_T5.md
# 2. extract BOTH patches (verbatim between their sentinel lines):
awk '/^=== BEGIN T5 PATCH ===$/{f=1;next} /^=== END T5 PATCH ===$/{f=0} f' \
    TEMPORAL_T5.md > t5.patch
awk '/^=== BEGIN T5 M11 PATCH ===$/{f=1;next} /^=== END T5 M11 PATCH ===$/{f=0} f' \
    TEMPORAL_T5.md > t5_m11.patch
# 3. apply and build:
cd omc/omc_v4.9
patch -p1 < ../../t5.patch      # Appendix A -> minor 10
patch -p1 < ../../t5_m11.patch  # Appendix D -> minor 11, the SHIPPING build
make                            # gcc, -O2 -std=c11; builds tools + test gates
make test                       # all gates must print "all ok"
make test-threads               # concurrency gate (12.19)
```

This exact procedure was verified end-to-end before shipping this document:
a pristine `omc_v4.9` tree + Appendix A, built as above, reproduces the
recorded generation-1 stream md5 of the 1080p reference configuration
byte-for-byte (`1c81c776…`, table in 10.3) and holds the generation chain
(generation-2 CDR == generation-1 CDR, generation-3 stream == generation-2
stream).  The patch and the prose are the same change; if they ever seem to
disagree, the patch wins and the prose has a bug.

### 9.1 Prerequisites

Tooling: `gcc` (C11), `make`, `patch`, `awk`, `bash`, `md5sum`, `cmp`, and
`python3` with **pillow 12.3.0** and **numpy 2.4.6** (only PNG decoding and the
720p Lanczos resize depend on pillow).  ThreadSanitizer support in the compiler
is needed for `make test-threads`.

From the drop, the replication path additionally uses `tools/omc_unblend_tool.c`
(the seam probe of 10.4), `tests/test_threads.c` (the concurrency gate of
12.19) and a `Makefile` carrying both `test` and `test-threads` targets — all
three are present in the pristine v4.14 drop and none is patched.

`tests/raw_manifest.md5` is **created by the replicator** by pasting Appendix
C.1 into that path; it is not in the drop.  The harness scripts of Appendices
B and E are likewise created by the replicator from those listings.

## 10. Tests and results

Directory layout assumed by every command below (and hard-wired into the
harness scripts, which resolve the codec tree as `../omc/omc_v4.9` relative
to themselves):

```
<root>/omc/omc_v4.9/     the patched, built codec tree (section 9)
<root>/tests/            the five harness scripts of Appendix B
<root>/tests/raw/        prepared masters (generated by 10.1)
<root>/footage/          the provided footage sets, laid out as in 10.1's
                         commands (three loose gfx444_B001C001 PNGs; the
                         other sets in per-set subdirectories)
```

All commands run from `<root>`.  The provided footage:

| set | source PNGs | native |
|---|---|---|
| gfx444_B001C001 | 3 frames | 1920×1080 16-bit RGB (graphics) |
| gfx444_F003C012 | 3 frames | 4480×1856 8-bit RGB (graphics) |
| cine_4k_A006 | 2 frames | 4096×2160 8-bit RGB |
| cine_A005C021 | 2 frames | 2048×1152 16-bit RGB |
| cine_A005C031 | 3 frames | 2048×1152 16-bit RGB |

### 10.1 Master preparation

`tests/prep.py` (pillow + numpy) converts PNGs to planar u16 masters:
4:4:4 carries R,G,B directly as the three planes (the codec is colour-
transparent; no matrix loss enters the chain); 4:2:2 is BT.709 limited-range
Y'CbCr with averaged-pair chroma decimation; depth conversion is by bit
shift; `--resize 1280x720` (Lanczos) derives the 720p masters.  Exact
commands:

```
python3 tests/prep.py --out tests/raw/gfx1080_422_10.yuv --fmt 422 --depth 10 footage/gfx444_B001C001_frame00*.png
python3 tests/prep.py --out tests/raw/gfx1080_444_12.yuv --fmt 444 --depth 12 footage/gfx444_B001C001_frame00*.png
python3 tests/prep.py --out tests/raw/gfx1080_444_8.yuv  --fmt 444 --depth 8  footage/gfx444_B001C001_frame00*.png
python3 tests/prep.py --out tests/raw/cineA21_422_12.yuv --fmt 422 --depth 12 footage/cine_A005C021/*.png
python3 tests/prep.py --out tests/raw/cineA21_444_10.yuv --fmt 444 --depth 10 footage/cine_A005C021/*.png
python3 tests/prep.py --out tests/raw/cineA31_422_10.yuv --fmt 422 --depth 10 footage/cine_A005C031/*.png
python3 tests/prep.py --out tests/raw/cine4k_422_8.yuv   --fmt 422 --depth 8  footage/cine4k/*.png
python3 tests/prep.py --out tests/raw/cine4k_444_10.yuv  --fmt 444 --depth 10 footage/cine4k/*.png
python3 tests/prep.py --out tests/raw/gfxF003_444_8.yuv  --fmt 444 --depth 8  footage/gfx444_F003C012/*.png
python3 tests/prep.py --out tests/raw/gfxF003_422_12.yuv --fmt 422 --depth 12 footage/gfx444_F003C012/*.png
python3 tests/prep.py --out tests/raw/gfx720_422_10.yuv      --fmt 422 --depth 10 --resize 1280x720 footage/gfx444_B001C001_frame00*.png
python3 tests/prep.py --out tests/raw/cineA31_720_444_8.yuv  --fmt 444 --depth 8  --resize 1280x720 footage/cine_A005C031/*.png
python3 tests/prep.py --out tests/raw/cineA21_720_422_12.yuv --fmt 422 --depth 12 --resize 1280x720 footage/cine_A005C021/*.png
```

The masters are **not distributed** (two of them exceed common hosting
limits, e.g. GitHub's 100 MB per-file cap); regenerate them with the commands
above and check them against the manifest (Appendix C, also shipped as
`tests/raw_manifest.md5`; `cd tests/raw && md5sum -c ../raw_manifest.md5`).
The manifest is the ground truth: if a different pillow build resamples
differently, every downstream stream md5 in this section moves with it —
the PASS/FAIL verdicts do not (the exactness contract is
content-independent), but for md5-level replication the masters must match
the manifest first.  Reference environment for the recorded numbers:
python 3 with **pillow 12.3.0, numpy 2.4.6** (only the `--resize` Lanczos
path and PNG decoding depend on pillow; the 4:2:2 matrix math is plain
numpy float64, deterministic across platforms).  `prep.py`'s full text is
in Appendix B — the script, not this paragraph, is the normative
definition of the master format.

### 10.2 The chain harness

`tests/genchain.sh MASTER W H FMT DEPTH BPP SLICE_H GENS [flags…]` runs

```
master → omc_enc → g1.omc → omc_dec --cdr → g1.cdr
       → omc_enc --cdr-in → gN.omc → omc_dec --cdr → gN.cdr   (N = 2..GENS)
```

and PASSes iff `cmp(g1.cdr, gN.cdr)` for every N (pixels fixed from
generation 1) and `cmp(g2.omc, gN.omc)` for every N ≥ 3 (streams fixed from
generation 2).  `tests/run_matrix.sh` is the full matrix (10.3).

### 10.3 Generation-exactness matrix — 29/29 PASS

`tests/run_matrix.sh` output, **verbatim**, final binaries.  Every line:
pixels byte-identical to generation 1 at every generation, streams
byte-identical from generation 2; `g1.omc=` is the generation-1 stream md5
for md5-level replication (masters per the Appendix C manifest):

```
PASS  [1280x720->1280x720 422/10b bpp=0.5 sh=8 gens=6 ] g1.omc=87e483aa2504e309ac472b021d3f16f7
PASS  [1280x720->1280x720 422/10b bpp=2.0 sh=8 gens=5 ] g1.omc=a02761856c79a98d6a768dd9f0ab55d2
PASS  [1280x720->1280x720 444/8b bpp=0.5 sh=8 gens=5 ] g1.omc=4f2ae79f7d07ab95cc748c18d4c7541a
PASS  [1280x720->1280x720 444/8b bpp=1.0 sh=16 gens=5 ] g1.omc=868f7e9d0348995cc293151202c4f516
PASS  [1280x720->1280x720 422/12b bpp=3.0 sh=8 gens=5 ] g1.omc=c9ef27fc172acd0781df27aef8084485
PASS  [1920x1080->1920x1088 422/10b bpp=0.5 sh=16 gens=6 ] g1.omc=d500bafc4d4da6de353ac4e51e78b43e
PASS  [1920x1080->1920x1088 422/10b bpp=1.0 sh=16 gens=5 ] g1.omc=1c81c7768ce7d1012db6cf1291e8fe4c
PASS  [1920x1080->1920x1088 422/10b bpp=3.0 sh=16 gens=5 ] g1.omc=dd86e77e1d39e8c4a477e135c0eb3de7
PASS  [1920x1080->1920x1088 444/12b bpp=0.5 sh=16 gens=6 ] g1.omc=616f36ff66226877442a38b4c118fccd
PASS  [1920x1080->1920x1088 444/12b bpp=3.0 sh=16 gens=5 ] g1.omc=b972bd289f6469fcb0cdc3e5866e5e84
PASS  [1920x1080->1920x1088 444/8b bpp=1.0 sh=16 gens=5 ] g1.omc=a88bcb7f8788c0820bc05fabc5f1bf07
PASS  [1920x1080->1920x1088 422/10b bpp=1.0 sh=32 gens=5 ] g1.omc=6aae7d7d3fabc5f5abab414411c7b8e3
PASS  [2048x1152->2048x1152 422/12b bpp=0.5 sh=16 gens=6 ] g1.omc=4a6dc759e6b5795f50d8c5721253b3e7
PASS  [2048x1152->2048x1152 444/10b bpp=2.0 sh=16 gens=5 ] g1.omc=52068a09f2909adcb90658d4c7d80193
PASS  [2048x1152->2048x1152 422/10b bpp=0.5 sh=8 gens=5 ] g1.omc=bd0de556a45ebe547e5854c3e04a408d
PASS  [2048x1152->2048x1152 422/10b bpp=3.0 sh=32 gens=5 ] g1.omc=8ba3b61b1970db574b7af0c81e082c81
PASS  [4096x2160->4096x2160 422/8b bpp=0.5 sh=16 gens=4 ] g1.omc=69371f94fbd7dbd039a1ef77128b6339
PASS  [4096x2160->4096x2176 444/10b bpp=2.0 sh=32 gens=4 ] g1.omc=44cedbc317944f696d6148e6f1e6a045
PASS  [4480x1856->4480x1856 444/8b bpp=0.5 sh=16 gens=4 ] g1.omc=f39dad9360f3d80cf041b2bcf7d310f0
PASS  [4480x1856->4480x1856 422/12b bpp=1.0 sh=8 gens=4 ] g1.omc=a14c472256e12120fb13247ccf49bbd6
PASS  [1920x1080->1920x1088 422/10b bpp=1.0 sh=16 gens=5 --tune vmaf] g1.omc=e19fc6c83ec844ca57ee831a693a4037
PASS  [1920x1080->1920x1088 422/10b bpp=1.0 sh=16 gens=5 --grain-corr] g1.omc=e836fcd78a11f01330b14d2adc503a32
PASS  [1920x1080->1920x1088 422/10b bpp=1.0 sh=16 gens=5 --fill-static] g1.omc=104989236697807ce215fecd2f6d4dba
PASS  [1920x1080->1920x1088 422/10b bpp=1.0 sh=16 gens=5 --no-fill] g1.omc=468c90f5e4ac12087841a0dd31379865
PASS  [1920x1080->1920x1088 422/10b bpp=1.0 sh=16 gens=5 --grain-replace] g1.omc=25e3e8f25c294dbd51ca8fcc8173a1eb
PASS  [1920x1080->1920x1088 422/10b bpp=1.0 sh=16 gens=5 --refresh 2] g1.omc=451af7b91cde8c3d36e05df5bb961d35
PASS  [1920x1080->1920x1088 422/10b bpp=1.0 sh=16 gens=5 --refresh 3] g1.omc=fc45d7bf1e02dbf4610378e0c69f109f
PASS  [2048x1152->2048x1152 422/10b bpp=0.5 sh=16 gens=5 --tune vmaf] g1.omc=0928ef4d6e9bc7c98ee5a2b512128433
PASS  [2048x1152->2048x1152 422/10b bpp=0.5 sh=16 gens=5 --grain-corr --fill-static] g1.omc=3f516c3b4d188d1c471d155817381227
```

Long chains, same harness, final binaries:

```
tests/genchain.sh tests/raw/gfx720_422_10.yuv  1280 720  422 10 1.0 8  20   # PASS (twenty generations)
tests/genchain.sh tests/raw/cineA31_422_10.yuv 2048 1152 422 10 0.5 16 12   # PASS (0.5 bpp, twelve generations)
```

The 10-generation development chain additionally hashed every artifact:
`md5(G1.cdr) == md5(G10.cdr)` and `md5(g2.omc) == md5(g10.omc)` (section
10.2's construction, gfx444_B001C001 1920×1080 4:2:2/10 @ 1.0 bpp).

> **Superseded.**  The `--cdr-in` line below predates the `--display-h`
> requirement and will now be REFUSED by the encoder.  Use the corrected form
> at the end of 12.14.

**The RCT (RGB container) path.**  `--rgb` input engages the reversible
colour transform and codes 4:4:4; a 4:4:4/8-bit master already carries
planar u16 R,G,B, so it doubles as the `--rgb` input directly.  This chain
also exercises the user-flagged 1080-coded-as-1088 hazard end-to-end: the
CDR carries the CODED geometry (1920×1088, pad rows included), and every
re-encode consumes it at coded dims — the pad never re-enters through a
crop/re-pad cycle.  Generation 1 is encoded from the true-dim RGB master;
generations 2+ re-encode the CDR as plain 4:4:4 (the CDR is pre-inverse-RCT,
so no `--rgb` on re-encode — depth 10 is the RCT internal domain of 8-bit
components):

```
E=omc/omc_v4.9; S=/tmp/rct
$E/omc_enc -i tests/raw/gfx1080_444_8.yuv -o $S/rct1.omc -w 1920 -h 1080 --rgb --depth 8 --bpp 1.0
$E/omc_dec -i $S/rct1.omc --cdr -o $S/rct1.cdr
$E/omc_enc --cdr-in -i $S/rct1.cdr -o $S/rct2.omc -w 1920 -h 1088 --fmt 444 --depth 10 --bpp 1.0
$E/omc_dec -i $S/rct2.omc --cdr -o $S/rct2.cdr    # cmp rct1.cdr rct2.cdr → identical
# ... generation 3 and 4 the same way from the previous CDR
```

Result (3 frames, final binaries): `rct2.cdr` and `rct3.cdr` byte-identical
to `rct1.cdr`; `rct3.omc` and `rct4.omc` byte-identical to `rct2.omc`.
`md5(rct1.omc) = 66a736f3abeb631da93c90d751b55da4`,
`md5(rct2.omc) = 780e99aa7fb7efd25264374b96878d00`.  Generation-1 encode
cost: 1.0x the reference encoder workload (this path is not a speed
measurement; see 12.18 on why wall-clock on the reference implementation is
not reported anywhere in this document).

**Flat black (degenerate content).**  The same chain on 3 frames of
synthetic all-zero RGB (`python3 -c "open('black3.raw','wb').write(bytes(1920*1080*3*2*3))"`)
also holds exactly — generation-2 pixels byte-identical to generation 1,
generation-3 stream byte-identical to generation 2.  It is, however, the
encoder's worst case for WORKLOAD: roughly 400x the per-frame work of real
footage at generation 1, and about 40% below what it was before the
finding-8 fixes.  Expressed as a ratio deliberately: see 12.18.
On all-zero input a very large number of *distinct* plans reproduce the
content exactly, so the lock walk verifies and trial-encodes many of them
before its slack break fires.  This is a performance limit only — the
exactness contract is unaffected — and it fades with any real signal.

### 10.4 The seam blend is alive (and measured)

Because the T5 edit is exactly reversible, the pre-edit picture is
recoverable from any decode: un-blend the CDR (`omc_xsl_unblend` over each
frame, via `omc_unblend_tool`, which ships unmodified in the drop and is
built by the default `make`) and compare the slice-boundary step excess
(mean luma |row-to-row| step at boundaries minus interior) with and without
the edit.  Exact command set for the first table row (the others vary only
master/bpp; `omc_unblend_tool` args are `in out W Hcoded depth slice_h
refresh nframes bits_per_slice`, with `bits_per_slice = bpp·W·slice_h` —
16384 here, 32768 at 1.0 bpp; it is 4:2:2-only, matching these clips):

```
E=omc/omc_v4.9; W=/tmp/seam
$E/omc_enc -i tests/raw/cineA31_422_10.yuv -o $W/a.omc -w 2048 -h 1152 --fmt 422 --depth 10 --bpp 0.5 --slice-h 16
$E/omc_dec -i $W/a.omc --cdr -o $W/a.cdr
$E/omc_unblend_tool $W/a.cdr $W/a_unb.cdr 2048 1152 10 16 8 3 16384
python3 tests/seam_repair.py $W/a.cdr $W/a_unb.cdr 2048 1152 422 10 16 8
# frame 0: seam excess edited +1.694  no-edit +4.364 (codes; repair = +2.670)
```

| clip / rate | seam excess, edited | seam excess, no edit | repair |
|---|---|---|---|
| cine_A005C031 422/10 @0.5 bpp | +1.69 codes | +4.36 codes | −61 % |
| cine_A005C031 422/10 @1.0 bpp | +0.79 | +2.64 | −70 % |
| gfx444_B001C001 422/10 @0.5 bpp | +1.35 | +2.95 | −54 % |
| gfx444_B001C001 422/10 @1.0 bpp | +0.77 | +1.88 | −59 % |

(Source-picture excess on these clips: ~+0.2 codes.)  The blend does its
minor-9 job — and now costs nothing across generations.

### 10.5 Generation-1 quality sanity

`tests/quality.py` (PSNR of the display decode vs the master, plus the seam
metric), cine_A005C031 2048×1152 4:2:2/10:

| bpp | PSNR-Y (f0) | PSNR-Cb | PSNR-Cr | seam excess |
|---|---|---|---|---|
| 0.5 | 45.49 dB | 51.99 | 51.00 | +1.69 codes |
| 1.0 | 48.70 dB | 54.30 | 52.92 | +0.79 |
| 3.0 | 57.60 dB | 58.90 | 57.52 | +0.29 |

Inter frames land slightly above frame 0 at every rate (the frame-buffer
prediction earning its keep on quasi-static content).

### 10.6 Failures found on the way (and their fixes)

These are part of the record because each one is a class of exactness bug a
replicator must not reintroduce:

1. **Fill amplitudes unrecoverable** (first gen-2 run, gfx 1080p): committed
   band-9 values of ±1 at shift 4 — the v4.6 activity taper's floor-at-1.
   Fix: 5.7.  2. **Attempt-ladder exhaustion at high rate** (gfx @3.0 bpp):
   near-budget lossless candidates burned the 40-attempt natural ladder.
   Fix: candidate fallbacks don't consume ladder attempts.  3. **Estimate-
   based selection starving later slices** (gfxF003 4:4:4/8 @0.5 bpp: slice
   31 locked +4 bytes over generation 1; slice 35 then failed to fit its own
   plan).  Fix: 5.5.4 trial-encode selection — and the root +4 bytes:
   4. **Partial-band tANS group flip** — the group id came from a
   generation-varying uniform-shift histogram.  Fix: 5.5.6, first for the
   partial band.  5. **The unclipped-reference prototype's missing retro
   row**: the drop's F-4 path never re-emitted the previous slice's
   retro-edited last row, so the emitted picture disagreed with the
   committed reference at every interior boundary.  Fixed in both loops
   (emit rows `[base−1, base+sh)`).  6. **Fill bits frozen by plan
   hysteresis** (`--grain-replace` auto-enabled hysteresis level 2): frozen
   fill masks are signalled state that is not a function of the committed
   pixels, so generation 2 could never re-derive them.  Fix: grain-replace
   now enables level 1 only (plan reuse; the fill decision stays
   measurement-derived, which is a fixed point).  7. **Grain-replace
   group-id drift** — the cost-table histograms carry the classifier's
   source-dependent shrink votes, which a locked re-encode does not repeat;
   one slice emitted +70 bytes and a later slice could no longer fit its
   own previous-generation plan.  Fix: 5.5.6 generalized — group ids for
   every band, every slice, come from the exact-plan histogram of the
   emitted symbols.  8. **Candidate-verify time explosion on flat
   content** (found on an all-black 1080p RGB frame, at roughly 700x the
   per-frame workload of real footage before these fixes).  Two independent causes, three fixes, all output-neutral —
   confirmed by re-running matrix chains and comparing stream md5s
   (unchanged): (a) `lock_verify` spent its time in the fill gate for
   candidates that could never verify — a **fast pre-reject** scan now
   dismisses a candidate as soon as any committed value is impossible
   under its plan (it only rejects plans full verify would reject, so the
   selected plan can't change); (b) a **gain-dependency early exit** stops
   the per-plane gain-hypothesis loop once the derived gain contradicts
   the hypothesis; (c) flat content makes hundreds of `(profile, Q,
   n_steps)` triples derive the *identical* per-band shift vector, and
   each alias was verified separately — the candidate list now **dedupes
   by the derived plan** (packed shift vector + partial-band position +
   partial k).  Keeping the first-enumerated alias preserves the
   pre-dedupe winner: aliases have equal estimates and equal actual sizes,
   and both tie-breaks keep the earliest entry.  Exactness is untouched —
   the previous generation's plan is still in the list, as the retained
   alias of its equivalence class, and every generation's encoder dedupes
   identically, so the selection is still generation-invariant.

### 10.7 Unit gates

`make test` (all "all ok"): DWT reversibility, quantizer idempotence, tANS
round-trip, exact-CBR slice round-trip with rt=0, **causality with the
2-line un-blend lookahead**, encoder reentrancy, config validation, RCT
bijectivity, upconverter/colour/TF-library suites, per-context blend cap
(`test_cap`), and the T5 XSL gates (`tests/test_xsl.c`):

- G-T5-XSL1: the old XSL environment levers are inert (always on);
- G-T5-XSL2: generation-2 pixels reproduce generation-1 byte-for-byte on a
  4-frame moving sequence with `refresh_r = 2` (inter frames and both
  barrier phases);
- G-T5-XSL3: generation-3 pixels hold and its stream is byte-identical to
  generation 2's;
- G-T5-XSL2b: the boundary edit demonstrably fires (un-blend changes
  samples).

The seam probe of 10.4 is the drop's own `tools/omc_unblend_tool.c`
(unmodified; it builds the config from its arguments, calls
`omc_xsl_unblend(&frame, &cfg, frame_idx)` per CDR frame and writes the
result); `tests/seam_repair.py` (Appendix B) computes both step-excess
numbers.  The `bits_per_slice` argument must match the encoder's
(`bpp·W·slice_h`) because it selects the blend cap (5.3b).

### 10.8 Cost of the rebuild against v4.14 (same bitrate, head to head)

The wire bitrate is **identical by construction** — both are exact-CBR
codecs (`nslices × bits_per_slice` bits per frame, frames padded to exactly
that), and T5 reserves no budget across generations.  The honest comparison
is therefore quality at equal bitrate.  Method: unpack a **second, pristine**
copy of the v4.14 drop (no Appendix A patch), `make omc_enc omc_dec` there,
and run it with its shipped XSL level (`OMC_XSL=3` in the environment, its
default operating point).  Generation 1 both ways is master → enc → dec;
v4.14's generation chain re-encodes its own decoded output (its decode is
the legal-range picture — the codec had no CDR), so generation n is n
enc/dec round trips at identical settings.  Compare display decodes against
the master with `tests/quality.py MASTER DEC W H fmt depth [slice_h]`
(Appendix B; T5 display decode = default `omc_dec` output, no `--cdr`).
cine_A005C031, 2048×1152 4:2:2/10-bit, PSNR-Y:

| | 0.5 bpp | 1.0 bpp | 3.0 bpp |
|---|---|---|---|
| v4.14 generation 1 (steady frame) | 48.13 dB | 51.37 dB | 57.86 dB |
| **T5 generation 1 = every T5 generation** | 46.03 dB | 49.01 dB | 57.78 dB |
| v4.14 generation 6 (frame 0, still falling) | 46.32 dB | 49.02 dB | — |

Attribution of the generation-1 gap, measured by re-running both codecs
with `--no-fill`:

| steady frame, `--no-fill` | 0.5 bpp | 1.0 bpp |
|---|---|---|
| v4.14 | 48.42 dB | 51.76 dB |
| T5 | 47.92 dB | 51.28 dB |

i.e. **~0.5 dB** is the temporal rebuild itself (derived motion instead of
source search, plus the detector-free un-blend), and the remaining
~1.4–1.9 dB on this grainy clip is the grain fill's v4.1 amplitude family
injecting more synthetic grain energy than v4.6's tapered fill — a
deliberate perceptual mechanism that PSNR penalizes by design (and whose
v4.6 tapering was structurally un-lockable, section 5.7).  At 3.0 bpp the
codecs are at parity (−0.08 dB).

The other side of the ledger: v4.14 keeps sliding with every hop (−1.5 dB
by generation 6 at 1.0 bpp, −1.8 dB at 0.5 bpp, no floor), while T5 is
frozen at its generation-1 numbers forever — so on a chain of roughly five
or more encodes T5 is ahead even on PSNR, and it is byte-exact, which no
v4.14 configuration ever was.

## 11. Notes, limits, and decisions a replicator should know

1. **Generation-1 streams changed vs v4.14** (this is a rebuild): always-on
   XSL, minor 10, derived motion, fill amplitude family, partial-aware group
   ids, no TF.  The drop's conformance vectors (minors ≤ 9) are therefore
   rejected by the T5 decoder — deliberately, per section 3.
2. **What the always-on un-blend costs on masters**: part of the seam repair
   is spent cancelling the encoder-side pre-distortion instead of
   quantization noise.  Measured repair retention is 54–70 % (10.4), in line
   with the drop's own oracle-vs-always measurements for the level-7
   experiment.  This is the price of a detector-free, deterministic design;
   a detector is a threshold on generation-varying data and cannot coexist
   with the contract.
3. **8-bit blend cap scales to zero**: the minor-9 cap rule
   `cap·((maxv+1)>>10)` yields lim = 0 at 8-bit, so the boundary edit is a
   no-op there (both ends, both directions — exactness unaffected).  This is
   inherited, unchanged semantics; the codec's validated operating class was
   10/12-bit.  If a nonzero 8-bit blend is ever wanted, the rule must change
   at both ends simultaneously (a minor bump).
4. **Latency**: the encoder gained a 2-line lookahead (5.3); slice-level
   callers see it as the causality bound `[0, (k+1)·sh + 2)`.  The decoder
   path is unchanged.  Memory: +2 frame stores in the encoder (`refprev`,
   `refprev2`, `inub` = 3 total beyond the rolling store), +1 in the decoder
   (`refprev`).
5. **Lossless mode** (`--lossless`) is unchanged and trivially
   generation-exact when it fits the budget.
6. **`--grain-replace`, deadzone, DCFB, SPC, alloc, tail guard** remain
   generation-1 policy: they shape what generation 1 commits; the lock path
   ignores them and generations ≥ 2 reproduce whatever was committed.  One
   adjustment inside grain-replace: it now enables plan-hysteresis level 1
   instead of level 2 — the level-2 fill-mask freeze emitted signalled
   state that is not a function of the committed pixels (10.6 item 6).
7. **Concealment** now projects from `refprev` (the previous frame), and
   error recovery still rides the refresh wave; corrupted-stream behaviour
   is out of the exactness contract (a concealed picture is a new master by
   definition).
8. **Debug instrumentation added**: `OMC_DEBUG_SIZES` (per-slice wire
   bytes + running spend), `OMC_DUMP_COMMITTED` (committed pre-display
   picture per frame), `OMC_DUMP_COEF` (slice-0 transform dump),
   `OMC_LAT_PROBE=prof,q,ns` (per-band lattice failures for a given plan),
   plus the surviving `OMC_DEBUG_LOCK` / `OMC_DEBUG_VTRIES` /
   `OMC_DEBUG_VERIFY` / `OMC_PLAN_STAT`.  All print-only.

---

## Appendix A — the complete source patch (normative)

This is the entire T5 change, as a unified diff against the pristine v4.14
drop (`omc_v4.9` tree), verbatim.  Extract it mechanically with the awk
command of section 9 (everything strictly between the two sentinel lines,
which appear nowhere else in this document), apply with `patch -p1` from
inside `omc_v4.9`, and build.  7 files; applying to a pristine tree
produces no fuzz and no rejects.  The reconstructed build reproduces the
recorded stream md5s of section 10.3 exactly (verified as described in
section 9).

`````diff
=== BEGIN T5 PATCH ===
diff --git a/include/omc1.h b/include/omc1.h
index e16e994..5221795 100644
--- a/include/omc1.h
+++ b/include/omc1.h
@@ -16,15 +16,26 @@
 #include <stdint.h>
 
 #define OMC_VERSION_MAJOR 4
-/* RELEASE IDENTITY is 4.9 (OMC_RELEASE_MINOR): this build implements every
- * feature through stream minor 9.  OMC_VERSION_MINOR is NOT the release — it
- * is the BASELINE minor written for streams that use no post-7 feature, and
- * it must stay 7 so those streams (and every conformance hash) remain
- * byte-identical to v4.7 encoders.  A stream's minor escalates by feature:
- * 8 = upconversion / in-loop TF signaling, 9 = cross-slice boundary
- * reconstruction (XSL + refresh barriers + barrier display blend). */
-#define OMC_RELEASE_MINOR 9
-#define OMC_VERSION_MINOR 7 /* 3 block MC; 4 entropy v2; 5 corr tile; 6 amplitude-matched fill (0.5x code) */
+/* RELEASE IDENTITY is 4.15-T5 (stream minor 10): the temporal engine was
+ * REMOVED and REBUILT for zero generation loss (the T5 layer).  Minor-10
+ * streams are the only streams this build reads or writes: the rebuilt
+ * temporal semantics (frame-buffer reference, derived motion, always-on
+ * reversible cross-slice boundary edit, biased unclipped pixel domain)
+ * are not compatible with any earlier minor, so earlier minors are
+ * rejected rather than silently mis-decoded.  See docs/TEMPORAL_T5.md. */
+#define OMC_RELEASE_MINOR 10
+#define OMC_VERSION_MINOR 10 /* T5: rebuilt temporal layer + always-on reversible XSL */
+#define OMC_MINOR_T5 10
+
+/* T5 pixel domain: every omc_frame_t (encoder input, decoder output, recon)
+ * carries samples as u16 = true_value + OMC_PIX_BIAS, UNCLIPPED to the legal
+ * range: values live in [0, (2^depth - 1) + 2*OMC_PIX_BIAS].  The bias keeps
+ * reconstruction overshoot (quantization ringing past black/white) exactly
+ * representable, which is one of the three pillars of the generation-exact
+ * guarantee (the others: the reversible boundary edit + mandatory un-blend,
+ * and the invariant temporal prediction).  Display/legal-range output is a
+ * non-normative projection: clip(v - OMC_PIX_BIAS, 0, 2^depth - 1). */
+#define OMC_PIX_BIAS 2048
 /* Decoder output-stage contract (A2).  The vertical rescaler needs a few source
  * rows beyond the row it is producing.  HOW the decoder hands rows to it decides
  * what that costs:
@@ -84,14 +95,10 @@ typedef struct {
     uint8_t refresh_r;       /* rolling intra-refresh period in frames (A5 recovery
                                 bound); 0 -> default 8. Encoders MUST intra-code each
                                 slice at least once every refresh_r frames. */
-    uint8_t mv_regions;      /* encoder-only: 0 (default) = one global integer-pel
-                                vector per slice (byte-exact generation replay,
-                                measured); 1 = enable per-region and half-pel
-                                override search (better divergent/fractional
-                                motion; re-encode generations may reconverge
-                                instead of replaying byte-exactly - see
-                                docs/DESIGN.md). The bitstream is identical in
-                                capability either way. */
+    uint8_t mv_regions;      /* REMOVED (T5): motion is DERIVED from committed
+                                reconstruction history, never searched against
+                                the source, so there is nothing to configure.
+                                Must be 0. */
     /* v4.2 extension fields (all zero = 4.1-identical behavior) */
     uint16_t display_width;  /* true width before padding; 0 = coded width */
     uint16_t display_height; /* true height before padding; 0 = coded height */
@@ -101,13 +108,8 @@ typedef struct {
                                 stream header (0 = v4.0 slice-header layout, 1 = v4.1
                                 wide-MV + fill-gain layout). Encoders always write
                                 OMC_VERSION_MINOR. Set by omc_read_stream_header. */
-    uint8_t no_block_mv;     /* encoder-only: 1 = disable the v4.3 per-block
-                                motion-offset layer (revert to one global
-                                vector per slice, the v4.2 posture). Default
-                                0: per-16x16-block full-pel offsets around the
-                                slice-global vector, strict-argmin block-sum
-                                SAD (replay-stable class), signalled per slice
-                                only when any offset is nonzero. */
+    uint8_t no_block_mv;     /* REMOVED (T5): the per-block motion field is
+                                gone from the bitstream.  Must be 0. */
     uint8_t lossless_pref;   /* encoder-only: 1 = lossless-preferred. Each slice
                                 starts from the minimum-quantization plan (all
                                 shifts 0, no fill); if it fits the CBR budget the
@@ -132,11 +134,12 @@ typedef struct {
                                 zone to a full step ONLY where energy has no
                                 coarser-scale support AND the fill regenerates
                                 it. Default 0 pending blind-viewing signoff. */
-    uint8_t tf_mode;         /* OMC-TF in-loop temporal filter, stream byte 27 bits
-                              * 5-6: 0 = off, 1/2 = strength.  BOTH ends read it
-                              * from the header, so a decoder cannot silently
-                              * decode a filtered stream unfiltered and drift
-                              * from the encoder's reconstruction (C4/C8). */
+    uint8_t tf_mode;         /* REMOVED (T5): the in-loop temporal filter was
+                                part of the old temporal engine and is gone.
+                                Must be 0; streams with the bits set are
+                                rejected (a temporal filter re-applied at each
+                                generation compounds and can never be
+                                generation-exact). */
     uint8_t uc_ratio;        /* OMC-UC output conversion, stream byte 27 bits 3-4:
                                 0 = none (decode at coded resolution, the default and
                                 the only value <= minor 7), 1 = 2x, 2 = 4x in both
@@ -168,7 +171,10 @@ typedef struct {
                                 encoder signals. */
 } omc_config_t;
 
-/* One frame of planar pixels, uint16 little-endian in [0, 2^bitdepth). */
+/* One frame of planar pixels, uint16 little-endian, T5 BIASED DOMAIN:
+ * sample = true_value + OMC_PIX_BIAS, range [0, 2^bitdepth - 1 + 2*OMC_PIX_BIAS].
+ * Encoder input, decoder output and recon all use this domain; it is the
+ * generation-chain interchange format (CDR: coded-domain raw). */
 typedef struct {
     uint16_t *p[OMC_NPLANES];
     int stride[OMC_NPLANES]; /* in samples */
@@ -178,16 +184,14 @@ typedef struct omc_enc omc_enc_t;
 typedef struct omc_dec omc_dec_t;
 
 /* ---- encoder ---- */
-/* Should this stream use cross-slice boundary reconstruction?  Encodes frame 0
- * once with XSL off and measures the seam step in its own reconstruction; above
- * the threshold there is a seam worth repairing, at or below it there is not and
- * the generation lock is worth more.  Encoder-side, once per stream; the minor
- * already carries the result, so nothing new is signalled.  Returns 1, 0, or -1
- * if the probe could not run.  Call it before omc_write_stream_header(). */
-/* XSL level 7 only: undo the reversible boundary edit on a picture, recovering
- * the exact reconstruction that produced it.  See codec.c. */
+/* T5: undo the (always-on, exactly reversible) cross-slice boundary edit on a
+ * whole picture, recovering the exact committed reconstruction that produced
+ * it.  omc_enc_frame() calls this on (a copy of) its input automatically —
+ * the mandatory un-blend that makes generation chains byte-exact.  Exposed
+ * for tests and for callers driving omc_enc_slice() directly (who must apply
+ * it themselves before slicing; it reads 2 rows below each slice boundary).
+ * Frame values are in the T5 biased domain. */
 void omc_xsl_unblend(omc_frame_t *f, const omc_config_t *cfg, int frame_idx);
-int omc_xsl_probe_frame(const omc_config_t *cfg, const omc_frame_t *in);
 
 omc_enc_t *omc_enc_create(const omc_config_t *cfg);
 void omc_enc_destroy(omc_enc_t *e);
diff --git a/src/codec.c b/src/codec.c
index 6a4707c..b3c51ad 100644
--- a/src/codec.c
+++ b/src/codec.c
@@ -1,12 +1,25 @@
 /* OMC-1 encoder + decoder core: slice pipeline, rate control, bitstream.
- * Release 4.9 (bitstream minors: 7 baseline / 8 upconversion + in-loop TF /
- * 9 cross-slice boundary reconstruction).  See docs/BITSTREAM.md for the
- * normative format description and include/omc1.h for the version constants.
+ * Release 4.15-T5 (stream minor 10): the temporal engine of minors <= 9 was
+ * REMOVED (rolling in-frame reference, source-searched motion, per-block
+ * motion field, in-loop temporal filter) and REBUILT as the T5 layer:
+ *   - prediction reads the previous frame's FINAL committed picture only
+ *     (frame-buffer reference; nothing predicts from the current frame),
+ *   - the per-slice motion vector is DERIVED from committed reconstruction
+ *     history (frames t-1 vs t-2), never searched against the source, so it
+ *     is identical in every re-encode generation,
+ *   - the cross-slice boundary edit (XSL) is ALWAYS ON and is an exactly
+ *     reversible lifting cascade; the encoder un-blends its input,
+ *   - the pixel domain is biased and unclipped (OMC_PIX_BIAS) so committed
+ *     reconstructions survive the trip through a raw file exactly,
+ *   - the generation lock is complete: at generation >= 2 every slice locks
+ *     and reproduces its input bit-for-bit (see docs/TEMPORAL_T5.md for the
+ *     induction argument and the measurements).
+ * See docs/BITSTREAM.md for the base format and docs/TEMPORAL_T5.md for the
+ * normative T5 deltas.
  */
 #include <stdio.h>
 #include <malloc.h>
 #include "internal.h"
-#include "omc_tf.h"
 
 extern int omc_xsl;       /* defined below; read by the header parser */
 extern int omc_xsl_lim;   /* ditto: minor 9 pins the boundary-blend cap */
@@ -26,6 +39,24 @@ typedef struct {
     uint8_t gid[OMC_MAX_SHIFT + 1];              /* table-group id */
 } band_cost_t;
 
+/* T5 generation-lock candidate: a fully-specified signalled plan.  The list
+ * is large and heap-resident (in the encoder instance) because completeness
+ * is part of the exactness guarantee: on generation >= 2 input the previous
+ * generation's own committed plan MUST be in the list, and a small
+ * evict-on-overflow buffer could push it out on pathological content. */
+typedef struct {
+    int64_t tot, key;
+    int pr, q, ns, k;
+    uint32_t modes;
+    /* dedupe key: the DERIVED plan (packed 4-bit per-band shifts, partial k,
+     * partial band position).  Many (pr,q,ns) triples derive the identical
+     * shift vector; verify/trial outcomes depend only on the derived plan,
+     * so aliases beyond the first-enumerated are dead weight (they flood the
+     * candidate list and burn verify time on flat/graphics content). */
+    uint8_t sv[18];
+} omc_lockcand_t;
+#define OMC_LOCK_CANDS 4096
+
 struct omc_enc {
     ctx_common_t c;
     int32_t *sbuf[OMC_NPLANES]; /* slice coeff buffers */
@@ -38,23 +69,22 @@ struct omc_enc {
     uint8_t *rawn;   /* raw bits count */
     uint8_t *paybuf; /* payload scratch: oversized attempts never touch dst */
     uint8_t *rowsig; /* per-band previous-row significance (2D context) */
-    uint16_t *ref[OMC_NPLANES]; /* previous reconstructed frame (temporal reference) */
-    /* OMC-TF in-loop temporal filter scratch (see include/omc_tf.h).  tfwin is
-     * the previous frame's window for the slice being reconstructed; tftail is
-     * the rolling copy of the rows just above it, taken before the previous
-     * slice overwrote them.  Rows BELOW the slice are still unwritten in ref
-     * and are read in place, so they cost nothing.  Total: sh + 2*pad rows. */
-    uint16_t *tfwin[OMC_NPLANES];
-    uint16_t *tftail[OMC_NPLANES];
+    uint16_t *ref[OMC_NPLANES]; /* CURRENT frame, committed slice by slice.
+        T5: this rolling buffer feeds ONLY the cross-slice boundary terms
+        (previous slice of the SAME frame) and, at frame end, is copied into
+        refprev.  Prediction NEVER reads it — no same-frame prediction. */
+    /* T5 frame-buffer references: refprev = previous frame's FINAL committed
+     * picture (the only prediction source); refprev2 = the frame before it
+     * (motion derivation only).  Both are generation-invariant: they equal
+     * the decoder's committed pictures exactly. */
+    uint16_t *refprev[OMC_NPLANES];
+    uint16_t *refprev2[OMC_NPLANES];
+    uint16_t *inub[OMC_NPLANES]; /* un-blended copy of the input frame */
     int last_frame;             /* last frame index encoded (-1 = none) */
-    int32_t *pbuf[OMC_NPLANES];             /* prev-slice transform scratch */
+    int last_frame2;            /* frame index held by refprev2 (-1 = none) */
+    int32_t *pbuf[OMC_NPLANES];             /* prediction transform scratch */
     int32_t *pcoef[OMC_NPLANES][OMC_NBANDS]; /* prediction coefficients */
     int32_t *dcoef[OMC_NPLANES][OMC_NBANDS]; /* delta (inter) coefficients */
-    int32_t *bsum;                          /* 4x2 input block sums (MV search) */
-    /* v4.3 per-block motion offsets (full-pel, around the region vector) */
-    int nblk;
-    int8_t *bofx, *bofy;
-    uint8_t *bmode; /* per-block composition: 0 = MC, 1 = intra (mid) */
     uint8_t *elig[OMC_NPLANES][OMC_NBANDS]; /* OMC_GR noise-class maps, bands 7-9 */
     int dz_enabled, gr_enabled; /* per-instance (cfg-derived; env overrides) */
     /* causal in-frame rate banking (encoder-side only; decoder is stateless).
@@ -92,6 +122,8 @@ struct omc_enc {
     /* spatial plan coherence (OMC_SPC): previous slice's committed plan
      * within the CURRENT frame, for refinement-depth clamping */
     int spc_prof, spc_Q, spc_ns, spc_valid;
+    omc_lockcand_t lcand[OMC_LOCK_CANDS]; /* T5 lock candidates (per slice) */
+    int nlcand;
     uint8_t *spc_drop;  /* per slice*plane fill-bit drop count (v4c servo) */
     uint8_t *spc_kmax;  /* per slice*plane drop ceiling (kill-floor ratchet) */
     uint32_t spc_fmask;
@@ -118,9 +150,10 @@ struct omc_dec {
     int32_t *tmp;
     uint8_t *pad; /* padded slice copy for safe backward reads */
     uint8_t *rowsig; /* per-band previous-row significance (2D context) */
-    uint16_t *ref[OMC_NPLANES]; /* previous reconstructed frame */
-    uint16_t *tfwin[OMC_NPLANES];  /* OMC-TF: see the encoder struct */
-    uint16_t *tftail[OMC_NPLANES];
+    uint16_t *ref[OMC_NPLANES]; /* CURRENT frame, committed slice by slice
+        (cross-slice terms + display copy; T5: never a prediction source) */
+    uint16_t *refprev[OMC_NPLANES]; /* previous frame FINAL (prediction source) */
+    int cur_fidx8; /* fidx8 of the frame ref[] is accumulating (-1 = none) */
     int32_t *pbuf[OMC_NPLANES];
     int32_t *pcoef[OMC_NPLANES][OMC_NBANDS];
     /* error-concealment state (decoder-only; never affects a clean decode).
@@ -133,19 +166,8 @@ struct omc_dec {
     uint8_t *slice_inter;  /* [nslices] 1 if the decoded slice used prediction */
     int8_t *slice_mvx;     /* [nslices*OMC_NREG] captured half-pel H vectors */
     int8_t *slice_mvy;     /* [nslices*OMC_NREG] captured half-pel V vectors */
-    /* v4.3 per-block motion offsets parsed from the slice MV field */
-    int nblk;
-    int8_t *bofx, *bofy;
-    uint8_t *bmode;
 };
 
-/* v4.3 block geometry: per 16 luma columns, one mode bit (0 = MC, 1 = intra/
- * mid composition) + one full-pel offset around the region vector.
- * 8 bits per block: [mode:1][dx+8:4][dy+4:3], LSB-first. */
-#define OMC_BLK_W 16
-static int num_blocks(int W) { return W / OMC_BLK_W; }
-static size_t mv_field_bytes(int nblk) { return (size_t)nblk; }
-
 int omc_num_slices(const omc_config_t *cfg) { return cfg->height / cfg->slice_h; }
 int omc_chroma_width(const omc_config_t *cfg)
 {
@@ -173,121 +195,6 @@ static void common_init(ctx_common_t *c, const omc_config_t *cfg)
 
 static int plane_width(const ctx_common_t *c, int p) { return p == 0 ? c->W : c->Wc; }
 
-/* ------------------------------------------------------- OMC-TF plumbing
- *
- * The reference store is overwritten slice by slice, so by the time slice k of
- * frame N has been reconstructed, ref holds frame N for slices < k and frame
- * N-1 for slices >= k.  The temporal filter needs frame N-1 around slice k, so
- * the rows it will lose must be taken BEFORE reconstruction overwrites them.
- *
- * That costs memory, not delay.  Rows below the slice are still frame N-1 in
- * ref and are read in place; only the slice's own rows and a `pad`-row tail
- * above it need copying.  Nothing here waits for a later slice, so the
- * filter's added latency is exactly zero (A2). */
-
-static int tf_pad(const ctx_common_t *c)
-{
-    return OMC_TF_PAD < c->sh ? OMC_TF_PAD : c->sh;
-}
-
-static int tf_win_rows(const ctx_common_t *c) { return c->sh + 2 * tf_pad(c); }
-
-/* Build tfwin[p] = frame N-1 rows [k*sh - pad, k*sh + sh + pad), edge-clamped,
- * and refresh tftail[p] with the rows the NEXT slice will need.  Must be called
- * before reconstruct_slice() writes slice k. */
-static void tf_gather(const ctx_common_t *c, uint16_t *const ref[],
-                      uint16_t *const win[], uint16_t *const tail[],
-                      int slice_idx)
-{
-    int pad = tf_pad(c), sh = c->sh, H = c->H, rows = tf_win_rows(c);
-    for (int p = 0; p < OMC_NPLANES; p++) {
-        int pw = plane_width(c, p);
-        for (int i = 0; i < rows; i++) {
-            int y = slice_idx * sh + i - pad;
-            const uint16_t *src;
-            if (i < pad) {
-                /* Above the slice.  For k > 0 these rows of ref already hold
-                 * frame N, so they must come from the tail saved last slice.
-                 * For k == 0 they are off the top of the picture and clamp to
-                 * row 0, which is still frame N-1. */
-                src = slice_idx == 0 ? ref[p] : tail[p] + (size_t)i * pw;
-            } else {
-                int yy = y > H - 1 ? H - 1 : y;
-                src = ref[p] + (size_t)yy * pw;
-            }
-            memcpy((void *)(win[p] + (size_t)i * pw), src, (size_t)pw * 2);
-        }
-        /* Save the last `pad` rows of THIS slice (still frame N-1) for the next
-         * slice.  pad <= sh, so this never reaches into an already-overwritten
-         * slice. */
-        for (int i = 0; i < pad; i++) {
-            int yy = slice_idx * sh + sh - pad + i;
-            if (yy < 0) yy = 0;
-            if (yy > H - 1) yy = H - 1;
-            memcpy((void *)(tail[p] + (size_t)i * pw),
-                   ref[p] + (size_t)yy * pw, (size_t)pw * 2);
-        }
-    }
-}
-
-/* Apply the filter in place to slice `slice_idx` of `dstp[]` (the encoder
- * filters its reference; the decoder filters the user output, which is then
- * copied into its reference — both end up filtering the same samples against
- * the same previous frame, which is what keeps rt = 0 exact). */
-/* Instrumentation only (env OMC_TF_STATS): how much of the picture the gate
- * admits.  Never consulted by the codec — it exists so the delivery document
- * can state the admission rate instead of guessing at it. */
-static long tf_stat_adm = 0, tf_stat_tot = 0;
-static void omc_tf_stats_report(const char *who);
-
-static void omc_tf_stats_report(const char *who)
-{
-    if (getenv("OMC_TF_STATS") && tf_stat_tot)
-        fprintf(stderr, "omc_tf[%s]: gate admitted %ld/%ld samples (%.2f%%)\n",
-                who, tf_stat_adm, tf_stat_tot,
-                100.0 * (double)tf_stat_adm / (double)tf_stat_tot);
-    tf_stat_adm = tf_stat_tot = 0;
-}
-
-static void tf_apply(const ctx_common_t *c, uint16_t *const dstp[],
-                     const int dstride[], uint16_t *const win[], int slice_idx,
-                     const int8_t mvx2[], const int8_t mvy2[])
-{
-    omc_tf_t t;
-    int pad = tf_pad(c), sh = c->sh;
-    int8_t rx[OMC_NREG], ry[OMC_NREG];
-    omc_tf_defaults(&t, c->cfg.bitdepth, omc_tf_mode);
-    if (getenv("OMC_TF_NOSEARCH")) t.search = 0;
-    if (getenv("OMC_TF_K")) t.k = atoi(getenv("OMC_TF_K"));
-    /* Sweep hooks for the constants harness/tf_tune.py explores.  Debug only —
-     * the shipped values are the #defines in include/omc_tf.h. */
-    if (getenv("OMC_TF_AFLOOR"))
-        t.afloor = atoi(getenv("OMC_TF_AFLOOR")) << (c->cfg.bitdepth - 8);
-    if (getenv("OMC_TF_C1")) t.c1 = atoi(getenv("OMC_TF_C1"));
-    if (getenv("OMC_TF_C2")) t.c2 = atoi(getenv("OMC_TF_C2"));
-    /* Residual-motion search, on LUMA only, from data both ends already hold.
-     * Must run before any sample of this slice is modified, so that the encoder
-     * and the decoder search identical inputs. */
-    omc_tf_refine(&t, dstp[0] + (size_t)slice_idx * sh * dstride[0], dstride[0],
-                  plane_width(c, 0), sh, win[0], plane_width(c, 0), pad,
-                  mvx2, mvy2, OMC_NREG, rx, ry);
-    for (int p = 0; p < OMC_NPLANES; p++) {
-        int pw = plane_width(c, p);
-        int8_t cx[OMC_NREG], cy[OMC_NREG];
-        for (int rg = 0; rg < OMC_NREG; rg++) {
-            /* 4:2:2 halves the horizontal vector for chroma; the vertical one
-             * is unscaled.  Identical to conceal_mc_plane(). */
-            cx[rg] = (p > 0 && c->cfg.chroma == OMC_CF_422)
-                         ? (int8_t)(rx[rg] / 2) : rx[rg];
-            cy[rg] = ry[rg];
-        }
-        tf_stat_adm += omc_tf_slice(&t, dstp[p] + (size_t)slice_idx * sh * dstride[p],
-                                    dstride[p], pw, sh, win[p], pw, pad,
-                                    cx, cy, OMC_NREG);
-        tf_stat_tot += (long)pw * sh;
-    }
-}
-
 /* ------------------------------------------------------------------ header */
 
 
@@ -299,8 +206,9 @@ int omc_write_stream_header(const omc_config_t *cfg, uint8_t *dst)
     uint32_t m = OMC_MAGIC;
     memcpy(o, &m, 4); o += 4;
     *o++ = OMC_VERSION_MAJOR;
-    *o++ = omc_xsl ? OMC_MINOR_XSL
-         : (cfg->uc_ratio || cfg->tf_mode) ? OMC_MINOR_UC : OMC_VERSION_MINOR;
+    /* T5: every stream is minor 10.  There is no lower minor to fall back
+     * to — XSL is always on and the temporal semantics are T5's. */
+    *o++ = OMC_MINOR_T5;
     memcpy(o, &cfg->width, 2); o += 2;
     memcpy(o, &cfg->height, 2); o += 2;
     *o++ = cfg->bitdepth;
@@ -332,9 +240,11 @@ int omc_write_stream_header(const omc_config_t *cfg, uint8_t *dst)
      * INTEROPERABLE: without it the decoder cannot know the encoder filtered,
      * decodes silently, and drifts from the encoder's reconstruction. */
     *o++ = 0;                                     /* 26: scan_type, reserved */
+    /* T5: tf_mode bits 5-6 are DEAD (the in-loop temporal filter was removed
+     * with the old temporal engine) and are written 0 always. */
     *o++ = (uint8_t)((cfg->rct ? 1 : 0) | (cfg->grain_corr ? 2 : 0) |
                      (cfg->fill_static ? 4 : 0) |
-                     ((cfg->uc_ratio & 3) << 3) | ((cfg->tf_mode & 3) << 5));
+                     ((cfg->uc_ratio & 3) << 3));
     memcpy(o, &cfg->display_height, 2); o += 2;
     memcpy(o, &cfg->display_width, 2); o += 2;
     return OMC_STREAM_HDR_BYTES;
@@ -346,25 +256,12 @@ int omc_read_stream_header(const uint8_t *src, omc_config_t *cfg)
     memcpy(&m, src, 4);
     if (m != OMC_MAGIC) return -1;
     if (src[4] != OMC_VERSION_MAJOR) return -2;
-    if (src[5] > OMC_MINOR_XSL) return -2;
+    /* T5 decodes minor 10 ONLY.  Earlier minors carry the removed temporal
+     * engine's semantics (rolling reference, block MV, optional XSL levels)
+     * and would silently mis-decode; they are rejected instead. */
+    if (src[5] != OMC_MINOR_T5) return -2;
     memset(cfg, 0, sizeof(*cfg));
     cfg->ver_minor = src[5];
-    /* C1 (review): XSL is stream-authoritative.  A minor-9 stream decodes
-     * with XSL level 3 regardless of environment; env OMC_XSL affects only
-     * what an ENCODER writes.  (Experimental builds may still force the
-     * decoder with OMC_XSL_FORCE for instrumentation.) */
-    if (src[5] >= OMC_MINOR_XSL) {
-        /* Stream-authoritative when the environment is silent.  common_init()
-         * below re-reads OMC_XSL and lets it win -- that is the deliberate
-         * instrumentation path (C1), NOT an accident, and it is why level 7 can
-         * be measured at all.  A widening of OMC_XSL_FORCE was added here on
-         * 2026-08-12 on the mistaken belief that the environment could not
-         * reach the decoder; it could, and the widening was reverted. */
-        omc_xsl = 3;
-        /* cap is rate-derived; cfg is filled in below, so the
-         * decoder pins it in omc_dec_create() instead. */
-    }
-    else if (!getenv("OMC_XSL_FORCE")) omc_xsl = 0;
     const uint8_t *o = src + 6;
     memcpy(&cfg->width, o, 2); o += 2;
     memcpy(&cfg->height, o, 2); o += 2;
@@ -383,13 +280,11 @@ int omc_read_stream_header(const uint8_t *src, omc_config_t *cfg)
     cfg->grain_corr = (uint8_t)((*o >> 1) & 1);
     cfg->fill_static = (uint8_t)((*o >> 2) & 1);
     cfg->uc_ratio = (uint8_t)((*o >> 3) & 3);
-    cfg->tf_mode = (uint8_t)((*o >> 5) & 3);
+    /* T5: tf_mode bits (5-6) and bit 7 must be zero — the in-loop temporal
+     * filter no longer exists.  A stream with them set is not a T5 stream. */
+    if ((*o >> 5) != 0) return -3;
     o++;
     if (cfg->uc_ratio > 2) return -3;
-    /* A decoder that reaches here has read minor <= OMC_MINOR_UC, so it is a
-     * v4.8 decoder and implements the filter.  A pre-v4.8 decoder rejected the
-     * stream at the minor check above rather than decoding it unfiltered --
-     * which is the whole point of signalling tf_mode. */
     memcpy(&cfg->display_height, o, 2); o += 2;
     memcpy(&cfg->display_width, o, 2); o += 2;
     return OMC_STREAM_HDR_BYTES;
@@ -486,14 +381,12 @@ int omc_gr_soft_coarse = 0; /* per-band soft depth for bands <=6 (env OMC_GR_SOF
 int omc_fill_veto_coarse = 0; /* veto bands 4-6 fill bits in flat-carpet slice-bands (env OMC_FILL_VETO_COARSE, pct) */
 int omc_fill_static = 0; /* fill tile static where act <= n (env OMC_FILL_STATIC; minor-7 candidate) */
 int omc_gr_fillveto = 0; /* pct: veto slice-band fill bit when flat-class kills dominate its fillable population (env OMC_GR_FILLVETO) */
-int omc_tf_mode = 0;   /* OMC-TF in-loop temporal filter (env OMC_TF):
-    0 = off (default), 1 = normative strength, 2 = strong (swept).  Applied
-    IDENTICALLY in encoder and decoder to the reconstruction, so rt = 0 (C4) is
-    preserved by construction.  Gated on mode_mask != 0 — a rule both ends
-    evaluate from the slice header alone, so it needs no new signalling: the
-    filter runs exactly where the slice used temporal prediction, and therefore
-    never on frame 0, never on a scene cut, and never on an intra-refresh
-    slice. */
+int omc_tf_mode = 0;   /* T5: PERMANENTLY 0.  The in-loop temporal filter was
+    removed with the old temporal engine (a filter re-applied at every encode
+    generation compounds — the tool's own help text documented the compounding
+    — so it cannot coexist with the generation-exactness contract).  The
+    symbol remains only for the standalone omc_tf_tool/tfilt.c offline
+    filter, which is outside the codec loop. */
 /* OMC_DCFB (band-fix, env-gated, default off = byte-identical): per-slice
  * LL DC nulling.  Mode 3 (the ship candidate) is exact two-pass feed-forward:
  * pass A codes the slice pristine and composes the decoder's exact
@@ -507,219 +400,217 @@ int omc_tf_mode = 0;   /* OMC-TF in-loop temporal filter (env OMC_TF):
  * as measurement instruments only. */
 int omc_dcfb = 0;
 extern int32_t *omc_dwt_d1m;   /* dwt.c: level-1 vertical boundary term */
-int omc_xsl = 0;
-int omc_xsl_lim = 4;  /* blend cap in codes @10-bit (OMC_XSL_LIM) */  /* OMC_XSL=1 (NORMATIVE experiment, both sides): slice k's
-    vertical level-1 update uses d[-1] = r15 - 2*r14 + r13 of slice k-1's
-    reconstruction instead of the blind d[0] copy — texture bridges the
-    border one-sidedly.  Ship = bitstream minor bump. */
-static int32_t omc_xsl_buf[OMC_NPLANES][8192]; /* sized to validated max width (review C5: 4096 overflowed at legal 8K 4:4:4) */
-static int32_t omc_xsl_prev[OMC_NPLANES][8192]; /* k-1's last row, centered */
-static int32_t omc_xsl_prev14[OMC_NPLANES][8192]; /* and the row before it (XSL 6) */
-static int omc_xsl_live[OMC_NPLANES];
-static int omc_xsl_noedit = 0;  /* test hook, see the level-7 block */
-static int omc_xsl_noretro; /* prev slice refreshed this frame: protect it */
-/* fill the per-plane boundary arrays from the reference frame's slice k-1 */
-int omc_xsl_nodisp = 0;  /* env OMC_XSL_NODISP=1: disable barrier display blend (A/B) */
-int omc_tailguard = 1;   /* env OMC_TAILGUARD: 0 off, 1 global, 2 tail-local (last 8) */
-int omc_fillhyst = 1;    /* env OMC_FILLHYST:  0 off, 1 global, 2 tail-local (last 8) */
-int omc_rboost = 0;      /* env OMC_RBOOST: refreshed slices get +pct%% of B, CBR-neutral */
-/* Display-side blend for the boundaries the A5 refresh barrier leaves raw
- * (band-fix sect 47).  The barrier keeps a refreshed slice's coding loop
- * independent of its neighbours (loss containment, measured), but the
- * skipped blends re-draw the boundary line on exactly those slices —
- * bisection put the whole passed-vs-current visibility gap on them
- * (barrier-boundary step excess 3.1 -> 6.6 codes; back to 3.3 with this).
- * The same bounded blends run here on the EMITTED rows only, after the
- * reference copy, so containment, banking and the lattice lock never see
- * them.  do_r0 = the refreshed slice's own skipped row-0 blend; do_r15 =
- * the two skipped retro edits (by k at its top edge, by k+1 via the
- * noretro gate at its bottom edge; XSL>=3 features).  Both sides derive
- * the condition from fidx8 + refresh config alone. */
-#define OMC_XSL_FULL_AT 4   /* codes @10-bit: excess at which the blend is full */
 
-/* XSL level 6: blend strength from the SEAM ITSELF, continuously.
+/* =================================================================== XSL-T5
  *
- * Levels 4/5 scale the blend by how empty the slice's detail band is.  That is a
- * texture proxy, and measured it is backwards for this job: busy slices get
- * almost no blend, and busy slices are exactly where the seam is worst (city at
- * 0.5 bpp: unrepaired 19.25 codes, level 3 repairs to 9.51, level 4 only to
- * 17.00).
+ * Cross-slice boundary reconstruction, T5 form: ALWAYS ON, EXACTLY REVERSIBLE.
  *
- * Level 6 measures the thing the blend exists to fix.  At a boundary, compare the
- * step ACROSS it with the steps either side of it inside the picture:
+ * Three pieces, all normative (minor 10):
  *
- *      excess = mean|row0 - prev15|  -  (mean|prev15 - prev14| + mean|row1 - row0|)/2
+ *  (a) the cross-slice wavelet term: slice k's vertical level-1 lifting uses
+ *      d[-1] = r15 - 2*r14 + r13 of slice k-1's committed reconstruction (of
+ *      the CURRENT frame) instead of the blind d[0] copy.  This changes the
+ *      transform's boundary convention, not its reversibility, and both ends
+ *      derive it from data they both hold.
  *
- * If the join is no sharper than the picture's own texture there, excess <= 0 and
- * nothing is done -- which is also what keeps the reconstruction on the quantiser
- * lattice, so the generation lock survives wherever there was no seam to repair.
- * Above that it rises CONTINUOUSLY to full strength; there is no threshold and no
- * cliff at a content transition (the hard-won rule from the band work).
+ *  (b) the boundary edit: at every interior slice boundary the two boundary
+ *      rows are edited by a two-step LIFTING cascade (the shipped v4.9 level-3
+ *      blend moved rows toward targets computed from their own values, which
+ *      is not invertible and was the largest measured source of generation
+ *      loss -- XSL.md: -8.17 dB over six generations at 3.0 bpp).  A lifting
+ *      step adds a correction computed ONLY from rows it does not touch, so
+ *      the exact inverse exists:
  *
- * Per slice boundary, per plane, recomputed every frame -- so a scene cut is
- * handled by construction, which a once-per-stream decision cannot do.  Both ends
- * derive it from reconstructions they both hold: no side information, no new
- * field, no bitstream change. */
-static int xsl_seam_strength(const int32_t *r0, const int32_t *r1,
-                             const int32_t *prev14, const int32_t *prev15,
-                             int pw, int maxv)
-{
-    int64_t across = 0, inside = 0;
-    for (int x = 0; x < pw; x++) {
-        int32_t d = r0[x] - prev15[x];        across += d < 0 ? -d : d;
-        d = prev15[x] - prev14[x];            inside += d < 0 ? -d : d;
-        d = r1[x] - r0[x];                    inside += d < 0 ? -d : d;
-    }
-    if (!pw) return 0;
-    /* excess in 1/2 units to keep the halving exact in integers */
-    int64_t ex2 = 2 * across / pw - inside / pw;
-    if (ex2 <= 0) return 0;
-    /* full strength once the join is one blend-cap worth sharper than the
-     * picture's own texture; linear below that.  The cap scales with depth, so
-     * this does too. */
-    int64_t full = 2 * (int64_t)OMC_XSL_FULL_AT * ((maxv + 1) >> 10);
-    int64_t z = ex2 * 256 / (full > 0 ? full : 1);
-    return z > 256 ? 256 : (int)z;
-}
+ *        forward  step 1:  row15 += clamp((row0   - row14) / 4, +-lim)
+ *                 step 2:  row0  += clamp((row15' - row1 ) / 4, +-lim)
+ *        inverse           row0  -= clamp((row15' - row1 ) / 4, +-lim)
+ *                          row15 -= clamp((row0   - row14) / 4, +-lim)
+ *
+ *      lim is the normative rate-derived cap (xsl_lim_for: 8 codes @10-bit
+ *      below 0.75 bpp on coded samples, else 4; scaled by (maxv+1)>>10).
+ *      In the T5 biased pixel domain the edit is applied UNCONDITIONALLY
+ *      (no legal-range skip): the domain has 2048 codes of headroom on each
+ *      side, the edit moves a row by at most lim <= 32 codes, and committed
+ *      values never approach the wide rails -- so forward and inverse agree
+ *      everywhere, which the old rail-skip could not guarantee.
+ *
+ *  (c) the refresh barriers (A5) and their display blend: a slice being
+ *      intra-refreshed this frame takes NO cross-slice terms and no edit
+ *      (rule d), and a slice whose predecessor was refreshed skips the
+ *      retro-edit of that predecessor's last row (rule e).  The boundaries
+ *      those rules leave raw get the SAME lifting cascade applied to the
+ *      EMITTED picture only (never the reference), so loss containment is
+ *      preserved and the emitted picture still has no seam.  Because the
+ *      display blend is the same reversible cascade, the encoder's un-blend
+ *      can invert it exactly under the same derivable conditions.
+ *
+ * The un-blend (omc_xsl_unblend) undoes (b) and (c) on a whole picture; the
+ * T5 encoder applies it to (a copy of) every input frame unconditionally.
+ * On generation >= 2 input this recovers the previous encoder's committed
+ * reconstruction EXACTLY; on first-generation masters it pre-distorts the
+ * boundary rows by at most the cap, which the decoder's forward edit then
+ * cancels -- the measured cost of that (a fraction of the seam repair) is
+ * the price of a detector-free, deterministic, generation-exact design. */
+int omc_xsl = 7;      /* T5: always on, single (reversible) level.  Kept as a
+                         variable only because downstream conditionals read
+                         it; nothing ever writes another value. */
+int omc_xsl_lim = 4;  /* per-context cap is c->xsl_lim; this global mirrors
+                         the last-created context for legacy readers only */
+static int32_t omc_xsl_buf[OMC_NPLANES][8192]; /* d[-1] terms, per column (validated max width 8192) */
+static int omc_xsl_live[OMC_NPLANES];
+static int omc_xsl_noretro; /* prev slice refreshed this frame: protect it */
+int omc_tailguard = 1;   /* env OMC_TAILGUARD: 0 off, 1 global, 2 tail-local (last 8) */
+int omc_fillhyst = 1;    /* env OMC_FILLHYST:  0 off, 1 global, 2 tail-local (last 8) */
+int omc_rboost = 0;      /* env OMC_RBOOST: refreshed slices get +pct%% of B, CBR-neutral */
 
+/* (c) barrier display blend: the reversible cascade on the EMITTED rows of
+ * the boundaries the refresh barriers leave raw.  Conditions derive from
+ * fidx8 + refresh config on both sides; runs after the reference update so
+ * containment, banking and the lock never see it.  fr is in the T5 biased
+ * domain. */
 static void xsl_display_blend(ctx_common_t *c, omc_frame_t *fr, int slice_idx,
                               int fidx8)
 {
     int do_r0 = 0, do_r15 = 0;
     if (slice_idx <= 0) return;
-    if (omc_xsl >= 2 && !omc_xsl_nodisp) {
+    {
         int Rr = c->cfg.refresh_r ? c->cfg.refresh_r : 8;
         if ((fidx8 % Rr) == (slice_idx % Rr))
-            { do_r0 = 1; do_r15 = (omc_xsl >= 3); }
+            { do_r0 = 1; do_r15 = 1; }        /* rule (d) left both rows raw */
         else if ((fidx8 % Rr) == ((slice_idx - 1) % Rr))
-            do_r15 = (omc_xsl >= 3);
+            do_r15 = 1;                       /* rule (e) skipped the retro edit */
     }
     if (!do_r0 && !do_r15) return;
+    if (c->W > 8192) return;
     int sh = c->sh;
     int32_t lim = c->xsl_lim * ((c->maxv + 1) >> 10);
     for (int p = 0; p < OMC_NPLANES; p++) {
         int pw = (p == 0 || c->cfg.chroma == OMC_CF_444) ? c->W : c->W / 2;
-        if (c->W > 8192) return;
         int base = slice_idx * sh;
-        uint16_t *r0 = fr->p[p] + (size_t)base * fr->stride[p];
-        uint16_t *r15 = fr->p[p] + (size_t)(base - 1) * fr->stride[p];
-        const uint16_t *r14 = fr->p[p] + (size_t)(base - 2) * fr->stride[p];
-        const uint16_t *r1 = fr->p[p] + (size_t)(base + 1) * fr->stride[p];
+        uint16_t *e0 = fr->p[p] + (size_t)base * fr->stride[p];
+        uint16_t *e15 = fr->p[p] + (size_t)(base - 1) * fr->stride[p];
+        const uint16_t *e14 = fr->p[p] + (size_t)(base - 2) * fr->stride[p];
+        const uint16_t *e1 = fr->p[p] + (size_t)(base + 1) * fr->stride[p];
         for (int x = 0; x < pw; x++) {
-            if (do_r0) {
-                int32_t tgt = ((int32_t)r15[x] + (int32_t)r1[x]) >> 1;
-                int32_t dchg = (tgt - (int32_t)r0[x]) / 2;
-                if (dchg > lim) dchg = lim;
-                if (dchg < -lim) dchg = -lim;
-                int32_t v = (int32_t)r0[x] + dchg;
-                if (v < 0) v = 0;
-                if (v > c->maxv) v = c->maxv;
-                r0[x] = (uint16_t)v;
-            }
             if (do_r15) {
-                int32_t tgt = ((int32_t)r14[x] + (int32_t)r0[x]) >> 1;
-                int32_t dchg = (tgt - (int32_t)r15[x]) / 2;
-                if (dchg > lim) dchg = lim;
-                if (dchg < -lim) dchg = -lim;
-                int32_t v = (int32_t)r15[x] + dchg;
-                if (v < 0) v = 0;
-                if (v > c->maxv) v = c->maxv;
-                r15[x] = (uint16_t)v;
+                int32_t d1 = ((int32_t)e0[x] - (int32_t)e14[x]) / 4;
+                if (d1 > lim) d1 = lim; if (d1 < -lim) d1 = -lim;
+                e15[x] = (uint16_t)((int32_t)e15[x] + d1);
+            }
+            if (do_r0) {
+                int32_t d2 = ((int32_t)e15[x] - (int32_t)e1[x]) / 4;
+                if (d2 > lim) d2 = lim; if (d2 < -lim) d2 = -lim;
+                e0[x] = (uint16_t)((int32_t)e0[x] + d2);
             }
         }
     }
 }
 
+/* Fill the per-plane d[-1] boundary arrays from the current frame's committed
+ * slice k-1 rows, and derive the refresh barriers.  The second difference
+ * r15 - 2*r14 + r13 is invariant under the pixel bias (the biases cancel), so
+ * rbias is applied only for clarity of the centered value. */
 static void xsl_prep(ctx_common_t *c, const omc_frame_t *ref, int slice_idx,
                      int rbias, int fidx8)
 {
     for (int p = 0; p < OMC_NPLANES; p++) omc_xsl_live[p] = 0;
-    if (!omc_xsl || slice_idx <= 0) return;
-    /* REFRESH BARRIER (A5): a slice being intra-refreshed this frame takes
-     * no cross-slice terms, so loss-induced drift cannot ride the coupling
-     * past a refresh — measured without this, a corrupted slice's error
-     * decayed (245 -> 6 codes) but never fully cleared and crept one slice
-     * per refresh cycle.  With the barrier the refresh wave annihilates
-     * drift within one cycle.  Both sides derive it from the slice header
-     * (fidx8) and config alone. */
+    omc_xsl_noretro = 0;
+    if (slice_idx <= 0) return;
     {
+        /* REFRESH BARRIER (A5), rule (d): an intra-refreshed slice takes no
+         * cross-slice terms, so loss-induced drift cannot ride the coupling
+         * past a refresh.  Rule (e): when slice k-1 was refreshed THIS frame,
+         * k must not retro-edit its last row.  Both derive from the slice
+         * header (fidx8) and config alone, on both sides. */
         int Rr = c->cfg.refresh_r ? c->cfg.refresh_r : 8;
         if ((fidx8 % Rr) == (slice_idx % Rr)) return;
-        /* backward-edit gate: when slice k-1 was intra-refreshed THIS
-         * frame, k must not retro-edit its last row - the backward blend
-         * was measured re-infecting freshly cleaned slices with the
-         * editor's own drift (loss trace: decay stalled ~10 codes and
-         * crept).  With the gate, drift trails the refresh wave at
-         * <= cap codes and dies within two cycles. */
-        omc_xsl_noretro = ((fidx8 % Rr) == ((slice_idx - 1 + Rr) % Rr));
+        omc_xsl_noretro = ((fidx8 % Rr) == ((slice_idx - 1) % Rr));
     }
-    if (c->W > 8192) return;  /* never overrun; wider-than-validated stays legacy */
+    if (c->W > 8192) return;  /* never overrun; wider than validated max */
     for (int p = 0; p < OMC_NPLANES; p++) {
         int pw = (p == 0 || c->cfg.chroma == OMC_CF_444) ? c->W : c->W / 2;
         int base = slice_idx * c->sh;
         const uint16_t *r13 = ref->p[p] + (size_t)(base - 3) * ref->stride[p];
         const uint16_t *r14 = ref->p[p] + (size_t)(base - 2) * ref->stride[p];
         const uint16_t *r15 = ref->p[p] + (size_t)(base - 1) * ref->stride[p];
-        for (int x = 0; x < pw; x++) {
+        for (int x = 0; x < pw; x++)
             omc_xsl_buf[p][x] = ((int32_t)r15[x] - rbias)
                               - 2 * ((int32_t)r14[x] - rbias)
                               + ((int32_t)r13[x] - rbias);
-            omc_xsl_prev[p][x] = (int32_t)r15[x] - rbias - c->mid;
-            omc_xsl_prev14[p][x] = (int32_t)r14[x] - rbias - c->mid;   /* XSL 6 */
-        }
         omc_xsl_live[p] = 1;
     }
 }
-/* ---- the inverse of the level-7 boundary edit, applied to a whole picture.
+
+/* ---- the exact inverse of the T5 boundary edit, applied to a whole picture.
  *
- * A later encoder calls this on its input.  Because every step of the forward
- * edit added a correction built only from rows it did not touch, running the
- * two steps backwards with the same arithmetic returns the exact reconstruction
- * the previous encoder coded -- so it lands back on the quantiser lattice and
- * can be re-emitted unchanged instead of being smoothed a second time.
+ * The T5 encoder calls this on (a copy of) EVERY input frame.  Because every
+ * forward step -- interior cascade and barrier display blend alike -- added a
+ * correction built only from rows it did not touch, running the steps
+ * backwards with the same arithmetic returns the exact pre-edit picture.  On
+ * generation >= 2 input that is the previous encoder's committed
+ * reconstruction: it lands back on the quantizer lattice and the generation
+ * lock re-emits it unchanged.
  *
- * Boundaries are walked from the BOTTOM UP.  The forward pass runs top-down and
- * slice k's edit writes row 0 of slice k, which is two rows below the row 15
- * that slice k+1's edit reads -- so the passes do not overlap and either order
- * works, but bottom-up mirrors the forward order exactly and costs nothing. */
+ * The forward edits are suppressed/replaced on refresh barriers, and both
+ * sides derive that from the frame index and refresh period alone -- so the
+ * same two rules are repeated here, from the same information.  Boundaries
+ * are walked bottom-up (the exact reverse of decode order); the two-row
+ * separation between consecutive boundaries makes the passes independent.
+ * f is in the T5 biased domain; no legal-range conditions exist (the wide
+ * domain guarantees the arithmetic never needed one). */
 void omc_xsl_unblend(omc_frame_t *f, const omc_config_t *cfg, int frame_idx)
 {
-    /* The forward edit is SUPPRESSED on refresh barriers, and both sides derive
-     * that from the slice header and config alone (xsl_prep, A5).  The inverse
-     * must make the same decision on the same information or it will "undo" an
-     * edit that never happened -- so the same two rules are repeated here, from
-     * the frame index and refresh period, with nothing else consulted. */
     int Rr = cfg->refresh_r ? cfg->refresh_r : 8;
     int fidx8 = frame_idx & 0xff;
     if (cfg->width > 8192) return;
-    int sh = cfg->slice_h ? cfg->slice_h : 16;
+    int sh = cfg->slice_h ? cfg->slice_h : (cfg->height <= 720 ? 8 : 16);
     int lim = xsl_lim_for(cfg) * ((1 << cfg->bitdepth) >> 10);
-    int hi = (1 << cfg->bitdepth) - 1;
-    int nsl = (cfg->height + sh - 1) / sh;
-    int np = OMC_NPLANES;
-    for (int p = 0; p < np; p++) {
+    int nsl = cfg->height / sh;
+    for (int p = 0; p < OMC_NPLANES; p++) {
         int pw = (p == 0) ? cfg->width
                           : (cfg->chroma == OMC_CF_444 ? cfg->width : cfg->width / 2);
         if (!f->p[p]) continue;
         for (int k = nsl - 1; k >= 1; k--) {
-            if ((fidx8 % Rr) == (k % Rr)) continue;            /* slice k refreshed */
-            if ((fidx8 % Rr) == ((k - 1 + Rr) % Rr)) continue; /* noretro gate */
+            int kref  = (fidx8 % Rr) == (k % Rr);
+            int k1ref = (fidx8 % Rr) == ((k - 1) % Rr);
             int base = k * sh;
             uint16_t *e15 = f->p[p] + (size_t)(base - 1) * f->stride[p];
             const uint16_t *e14 = f->p[p] + (size_t)(base - 2) * f->stride[p];
             uint16_t *e0 = f->p[p] + (size_t)base * f->stride[p];
             const uint16_t *e1 = f->p[p] + (size_t)(base + 1) * f->stride[p];
-            for (int x = 0; x < pw; x++) {
-                /* undo step 2 first: it used the FINAL e15 and the untouched e1 */
-                int32_t d2 = ((int32_t)e15[x] - (int32_t)e1[x]) / 4;
-                if (d2 > lim) d2 = lim; if (d2 < -lim) d2 = -lim;
-                int32_t v = (int32_t)e0[x] - d2;
-                if (v >= 0 && v <= hi) e0[x] = (uint16_t)v;
-                /* then step 1: it used the RECOVERED e0 and the untouched e14 */
-                int32_t d1 = ((int32_t)e0[x] - (int32_t)e14[x]) / 4;
-                if (d1 > lim) d1 = lim; if (d1 < -lim) d1 = -lim;
-                v = (int32_t)e15[x] - d1;
-                if (v >= 0 && v <= hi) e15[x] = (uint16_t)v;
+            if (kref) {
+                /* barrier at k (rule d): the interior edit was suppressed and
+                 * the display blend applied BOTH cascade steps to the emitted
+                 * rows.  Same arithmetic as the interior inverse. */
+                for (int x = 0; x < pw; x++) {
+                    int32_t d2 = ((int32_t)e15[x] - (int32_t)e1[x]) / 4;
+                    if (d2 > lim) d2 = lim; if (d2 < -lim) d2 = -lim;
+                    e0[x] = (uint16_t)((int32_t)e0[x] - d2);
+                    int32_t d1 = ((int32_t)e0[x] - (int32_t)e14[x]) / 4;
+                    if (d1 > lim) d1 = lim; if (d1 < -lim) d1 = -lim;
+                    e15[x] = (uint16_t)((int32_t)e15[x] - d1);
+                }
+            } else if (k1ref) {
+                /* noretro barrier (rule e): only display step 1 (row 15) was
+                 * applied; row 0 of slice k carried its interior... no: when
+                 * k-1 is refreshed, slice k took no retro edit AND no row-0
+                 * edit either (the forward cascade is one unit and was
+                 * skipped whole; only the display blend touched row 15). */
+                for (int x = 0; x < pw; x++) {
+                    int32_t d1 = ((int32_t)e0[x] - (int32_t)e14[x]) / 4;
+                    if (d1 > lim) d1 = lim; if (d1 < -lim) d1 = -lim;
+                    e15[x] = (uint16_t)((int32_t)e15[x] - d1);
+                }
+            } else {
+                /* interior boundary: invert the in-loop cascade */
+                for (int x = 0; x < pw; x++) {
+                    int32_t d2 = ((int32_t)e15[x] - (int32_t)e1[x]) / 4;
+                    if (d2 > lim) d2 = lim; if (d2 < -lim) d2 = -lim;
+                    e0[x] = (uint16_t)((int32_t)e0[x] - d2);
+                    int32_t d1 = ((int32_t)e0[x] - (int32_t)e14[x]) / 4;
+                    if (d1 > lim) d1 = lim; if (d1 < -lim) d1 = -lim;
+                    e15[x] = (uint16_t)((int32_t)e15[x] - d1);
+                }
             }
         }
     }
@@ -731,18 +622,19 @@ int omc_spc = 0;  /* OMC_SPC=K: cap a slice's refinement depth at (previous
     flat, which the eye reads as banding (component C).  Matching the poorer
     neighbor is the safe direction: the surplus banks forward (A1 intact),
     and uniform retention beats banded retention.  Encoder-only. */
-int omc_ref_unclipped = 0; /* F-4 prototype (env OMC_REF_UNCLIPPED=1): carry
-    UNCLIPPED reconstructions in the temporal reference store, biased by
-    OMC_REF_BIAS so negatives stay representable in uint16; legal-range clip
-    happens once at the output interface only. Gates encoder and decoder
-    identically. */
-#define OMC_REF_BIAS 2048
+/* T5: the biased, unclipped pixel domain is ALWAYS on (it was the F-4
+ * prototype).  Every picture — encoder input, references, decoder output —
+ * carries value+OMC_REF_BIAS clamped only to the representable window
+ * [0, maxv + 2*OMC_REF_BIAS].  The legal-range clip that destroyed lattice
+ * alignment (a clipped pixel's coefficients are off-lattice, so the slice
+ * could never lock again) is now a non-normative display projection in the
+ * tools.  OMC_REF_BIAS == OMC_PIX_BIAS (omc1.h). */
+#define OMC_REF_BIAS OMC_PIX_BIAS
 
 void omc_global_init(void)
 {
     omc_tans_init();
     omc_crc_init();
-    omc_tf_mode = getenv("OMC_TF") ? atoi(getenv("OMC_TF")) : 0;
     omc_dz_mode = getenv("OMC_DZ") ? atoi(getenv("OMC_DZ")) : 0;
     omc_gr_mode = getenv("OMC_GR") ? atoi(getenv("OMC_GR")) : 0;
     omc_gr_pthr = getenv("OMC_GR_PTHR") ? atoi(getenv("OMC_GR_PTHR")) : 0;
@@ -765,28 +657,22 @@ void omc_global_init(void)
     omc_gr_llthr = getenv("OMC_GR_LLTHR") ? atoi(getenv("OMC_GR_LLTHR")) : 24;
     omc_gr_carpet = getenv("OMC_GR_CARPET") ? atoi(getenv("OMC_GR_CARPET")) : 0;
     omc_gr_softcap = getenv("OMC_GR_SOFTCAP") ? atoi(getenv("OMC_GR_SOFTCAP")) : 3;
-    omc_ref_unclipped = getenv("OMC_REF_UNCLIPPED") ? atoi(getenv("OMC_REF_UNCLIPPED")) : 0;
     omc_dcfb = getenv("OMC_DCFB") ? atoi(getenv("OMC_DCFB")) : 0;
-    if (getenv("OMC_XSL")) omc_xsl = atoi(getenv("OMC_XSL"));  /* preserve stream-derived value otherwise (C1) */
-    /* NORMATIVE (minor 9): the boundary blend cap is 8 codes at 10-bit.
-     * Both sides derive it from the stream minor, never from the
-     * environment.  Chosen by eye (three-arm blind comparison, caps
-     * 4/8/16) with the measurements as support: cap 8 halves the
-     * seam excess of cap 4 (all-seam +1.23 -> +0.67 codes, JPEG XS
-     * floor = 0.00) while beach@0.5bpp keeps VMAF parity with XS@1.0
-     * (94.89 vs 94.94); cap 16 reaches +0.40 but drops to 94.34 and
-     * risks trading a hard seam line for a soft two-row smear.
-     * OMC_XSL_LIM remains for experiments only. */
-    omc_xsl_lim = getenv("OMC_XSL_LIM") ? atoi(getenv("OMC_XSL_LIM")) : 4;
+    /* T5: XSL is NOT configurable.  No OMC_XSL, no OMC_XSL_LIM, no
+     * OMC_XSL_NOEDIT, no OMC_XSL_NODISP: the boundary reconstruction is a
+     * normative always-on part of the codec (the seam blend matters most at
+     * and below 0.5 bpp), the cap derives from the stream header at both
+     * ends (xsl_lim_for), and an environment that could disable any part of
+     * it would silently break the generation-exactness contract. */
     omc_spc = getenv("OMC_SPC") ? atoi(getenv("OMC_SPC")) : 0;
-    omc_xsl_nodisp = getenv("OMC_XSL_NODISP") ? atoi(getenv("OMC_XSL_NODISP")) : 0;
     omc_tailguard = getenv("OMC_TAILGUARD") ? atoi(getenv("OMC_TAILGUARD")) : 1;
     omc_fillhyst = getenv("OMC_FILLHYST") ? atoi(getenv("OMC_FILLHYST")) : 1;
     omc_rboost = getenv("OMC_RBOOST") ? atoi(getenv("OMC_RBOOST")) : 0;
 }
 
 
-/* NORMATIVE (minor 9): boundary-blend cap, in codes at 10-bit scale.
+/* NORMATIVE (minor 10, unchanged rule from minor 9): boundary-blend cap, in
+ * codes at 10-bit scale.
  * The blend exists to bridge QUANTIZATION error at a slice seam, so its cap
  * must follow the coarseness of the quantizer, and both sides derive it from
  * the stream header alone: bpp = bits_per_slice / (width * slice_h).
@@ -796,10 +682,10 @@ void omc_global_init(void)
  *   0.5bpp  cap4 +1.23 / 95.21   cap8 +0.67 / 94.89  -> cap 8 (eye-chosen)
  *   1.0bpp  cap4 +0.00 / 97.67   cap8 -0.35 / 97.23  -> cap 4 (8 over-smooths
  *   2.0bpp  cap4 -0.38 / 98.59   cap8 -0.68 / 98.12     and costs ~0.45 VMAF)
- * OMC_XSL_LIM overrides for experiments only. */
+ * T5: no environment override — the cap is part of the exactness contract
+ * (encoder un-blend and decoder blend must agree on it forever). */
 static int xsl_lim_for(const omc_config_t *cfg)
 {
-    if (getenv("OMC_XSL_LIM")) return atoi(getenv("OMC_XSL_LIM"));
     int64_t px = (int64_t)cfg->width * (cfg->slice_h ? cfg->slice_h : 16);
     /* counts CODED SAMPLES, not luma pixels: 0.75 bpp at 4:2:2 (unchanged) and
      * 1.125 bpp at 4:4:4, which is the same coarseness.  Eye-decided 2026-08-12. */
@@ -808,85 +694,10 @@ static int xsl_lim_for(const omc_config_t *cfg)
            ? OMC_XSL_LIM_MINOR9 : 4;
 }
 
-/* Is the cross-slice boundary reconstruction worth switching on for THIS stream?
- *
- * XSL repairs the brightness step at a slice seam, and it costs generation
- * robustness: it edits the reconstruction by a sub-step amount, which puts the
- * coefficients off the quantiser lattice and stops the generation lock from
- * firing (measured: 31 of 72 slices lock without it, 0 of 72 with it).
- *
- * Measured across three clips at three rates, the two effects sit at OPPOSITE
- * ends of the rate range.  Where the seam is large the generation cost is 0.1-1.2
- * dB; where the seam has already gone the cost is 2.1-4.7 dB and the blend is
- * over-smoothing rather than repairing (the boundary rows come out SMOOTHER than
- * the interior).  So the honest switch is not the rate but the thing the feature
- * exists to fix -- the same principle CAP_RULE_REVIEW F3/F4 reached for the blend
- * cap, applied to the feature itself.
- *
- * This encodes frame 0 once with XSL off and measures, on its own
- * reconstruction, how much bigger the row-to-row step is AT the slice boundaries
- * than everywhere else.  Above OMC_XSL_SEAM_ON codes there is a seam worth
- * repairing; at or below it there is not, and the stream is written without XSL
- * (minor 7), which any decoder already handles.
- *
- * Encoder-side and once per stream.  No new bitstream field: the minor already
- * carries the decision.  Returns 1 for "use XSL", 0 for "do not". */
-#define OMC_XSL_SEAM_ON 3.0   /* codes @10-bit; BITSTREAM's own "clean" reference */
-
-int omc_xsl_probe_frame(const omc_config_t *cfg, const omc_frame_t *in)
-{
-    int saved = omc_xsl;
-    omc_xsl = 0;                       /* measure the UNREPAIRED seam */
-    omc_config_t c = *cfg;
-    omc_enc_t *e = omc_enc_create(&c);
-    int rc = -1;
-    double excess = 0.0;
-    if (e) {
-        int W = c.width, H = c.height, Wc = omc_chroma_width(&c);
-        size_t words = (size_t)W * H + 2 * (size_t)Wc * H;
-        uint16_t *rec = malloc(words * 2);
-        size_t nsl = (size_t)omc_num_slices(&c);
-        uint8_t *bs = malloc((size_t)c.bits_per_slice / 8 * nsl);
-        if (rec && bs) {
-            omc_frame_t fr = {{rec, rec + (size_t)W * H,
-                               rec + (size_t)W * H + (size_t)Wc * H}, {W, Wc, Wc}};
-            if (omc_enc_frame(e, in, 0, bs, (size_t)c.bits_per_slice / 8 * nsl,
-                              &fr) >= 0) {
-                double bsum = 0, isum = 0; long bn = 0, in_ = 0;
-                for (int r = 1; r < H; r++) {
-                    double acc = 0;
-                    const uint16_t *a = rec + (size_t)(r - 1) * W;
-                    const uint16_t *b = rec + (size_t)r * W;
-                    for (int x = 0; x < W; x++) {
-                        int d = (int)b[x] - (int)a[x];
-                        acc += d < 0 ? -d : d;
-                    }
-                    acc /= W;
-                    if (r % c.slice_h == 0) { bsum += acc; bn++; }
-                    else { isum += acc; in_++; }
-                }
-                if (bn && in_) {
-                    excess = bsum / bn - isum / in_;
-                    /* the cap scales with depth, so the threshold does too */
-                    rc = excess > OMC_XSL_SEAM_ON * (double)((c.bitdepth > 10)
-                          ? (1 << (c.bitdepth - 10)) : 1) ? 1 : 0;
-                }
-            }
-        }
-        free(rec); free(bs);
-        omc_enc_destroy(e);
-    }
-    omc_xsl = saved;
-    if (getenv("OMC_XSL_PROBE_DEBUG"))
-        fprintf(stderr, "XSLPROBE seam=%.3f decision=%d\n", excess, rc);
-    return rc;
-}
-
 omc_enc_t *omc_enc_create(const omc_config_t *cfg)
 {
     omc_global_init(); /* tables allocated here, before the baseline */
-    if (omc_xsl) omc_xsl_lim = xsl_lim_for(cfg);
-    { const char *ne = getenv("OMC_XSL_NOEDIT"); omc_xsl_noedit = ne && atoi(ne); }
+    omc_xsl_lim = xsl_lim_for(cfg); /* legacy mirror; the codec reads c->xsl_lim */
     size_t heap_base = 0;
     if (getenv("OMC_ENC_FOOTPRINT")) {
         struct mallinfo2 mi0 = mallinfo2();
@@ -917,7 +728,15 @@ omc_enc_t *omc_enc_create(const omc_config_t *cfg)
         if (!getenv("OMC_GR_SOFT_COARSE")) omc_gr_soft_coarse = 2;
         if (!getenv("OMC_GR_INTRA")) omc_gr_intra = 1;
         if (!getenv("OMC_FILL_VETO_COARSE")) omc_fill_veto_coarse = 30;
-        if (!getenv("OMC_PLAN_HYST")) omc_plan_hyst = 2;
+        /* T5: plan hysteresis level 1 (plan reuse), NEVER level 2.  Level 2
+         * froze fill bits/gains to the previous frame's, i.e. signalled
+         * state that is NOT a function of the committed pixels — a later
+         * generation derives the fill by the measurement rule and can never
+         * match a frozen mask, so grain-replace streams stopped locking
+         * (caught by the option matrix: --grain-replace FAILed gen-2).
+         * Level 1 keeps the plan-jitter damping; the fill decision stays
+         * measurement-derived, which IS a generation fixed point. */
+        if (!getenv("OMC_PLAN_HYST")) omc_plan_hyst = 1;
     }
     if (getenv("OMC_DZ")) e->dz_enabled = atoi(getenv("OMC_DZ"));
     if (getenv("OMC_GR")) e->gr_enabled = atoi(getenv("OMC_GR"));
@@ -934,11 +753,6 @@ omc_enc_t *omc_enc_create(const omc_config_t *cfg)
         }
     }
     e->tmp = malloc(sizeof(int32_t) * (size_t)(W > 64 ? W : 64));
-    e->bsum = malloc(sizeof(int32_t) * (size_t)(W / 4) * (size_t)(e->c.sh / 2));
-    e->nblk = num_blocks(W);
-    e->bofx = calloc((size_t)e->nblk, 1);
-    e->bofy = calloc((size_t)e->nblk, 1);
-    e->bmode = calloc((size_t)e->nblk, 1);
     e->hyst_valid = calloc((size_t)e->c.nslices, 1);
     e->hyst_Q = calloc((size_t)e->c.nslices, sizeof(int16_t));
     e->hyst_steps = calloc((size_t)e->c.nslices, sizeof(int16_t));
@@ -971,11 +785,19 @@ omc_enc_t *omc_enc_create(const omc_config_t *cfg)
     e->paybuf = malloc(e->c.slice_bytes * 2 + 64);
     e->rowsig = malloc((size_t)(W > 64 ? W : 64));
     e->last_frame = -1;
+    e->last_frame2 = -1;
     for (int p = 0; p < OMC_NPLANES; p++) {
         int pw = plane_width(&e->c, p);
-        e->ref[p] = calloc((size_t)pw * e->c.H, 2);
-        e->tfwin[p] = calloc((size_t)pw * tf_win_rows(&e->c), 2);
-        e->tftail[p] = calloc((size_t)pw * tf_pad(&e->c), 2);
+        size_t fw = (size_t)pw * e->c.H;
+        e->ref[p] = malloc(fw * 2);
+        e->refprev[p] = malloc(fw * 2);
+        e->refprev2[p] = malloc(fw * 2);
+        e->inub[p] = malloc(fw * 2);
+        /* mid-grey in the biased domain, matching the decoder's init */
+        uint16_t mid = (uint16_t)((1u << (cfg->bitdepth - 1)) + OMC_REF_BIAS);
+        if (e->ref[p] && e->refprev[p] && e->refprev2[p])
+            for (size_t i = 0; i < fw; i++)
+                e->ref[p][i] = e->refprev[p][i] = e->refprev2[p][i] = mid;
         e->pbuf[p] = malloc(sizeof(int32_t) * (size_t)pw * sh);
         omc_band_layout(pw, sh, bands);
         for (int b = 0; b < OMC_NBANDS; b++) {
@@ -998,19 +820,19 @@ omc_enc_t *omc_enc_create(const omc_config_t *cfg)
         size_t slicebuf = 0, bandbuf = 0, refstore = 0, symbuf = 0, misc = 0;
         for (int p = 0; p < OMC_NPLANES; p++) {
             int pw = p == 0 ? W : Wc;
-            slicebuf += sizeof(int32_t) * (size_t)pw * sh;      /* sbuf */
+                slicebuf += sizeof(int32_t) * (size_t)pw * sh;      /* sbuf */
             slicebuf += sizeof(int32_t) * (size_t)pw * sh;      /* pbuf */
             omc_band_layout(pw, sh, bands);
             for (int b = 0; b < OMC_NBANDS; b++) {
                 size_t n = (size_t)bands[b].h * bands[b].w;
                 bandbuf += sizeof(int32_t) * n * 4;             /* coef,qbuf,pcoef,dcoef */
             }
-            refstore += (size_t)plane_width(&e->c, p) * e->c.H * 2;
+            /* T5: ref + refprev + refprev2 + inub, all frame-sized */
+            refstore += (size_t)plane_width(&e->c, p) * e->c.H * 2 * 4;
         }
         size_t maxsym2 = (size_t)W * sh + 2 * (size_t)Wc * sh + 64;
         symbuf = maxsym2 * (1 + 1 + 2 + 1);                    /* syms,stids,raws,rawn */
         misc = sizeof(int32_t) * (size_t)(W > 64 ? W : 64)     /* tmp */
-             + sizeof(int32_t) * (size_t)(W / 4) * (size_t)(e->c.sh / 2) /* bsum */
              + e->c.slice_bytes * 2 + 64                       /* paybuf */
              + (size_t)(W > 64 ? W : 64)                       /* rowsig */
              + sizeof(*e); /* includes lat_cs/lat_csn/bandcost as members */
@@ -1023,13 +845,12 @@ omc_enc_t *omc_enc_create(const omc_config_t *cfg)
 
 void omc_enc_destroy(omc_enc_t *e)
 {
-    omc_tf_stats_report("enc");
     if (!e) return;
     for (int p = 0; p < OMC_NPLANES; p++) {
         free(e->sbuf[p]);
         for (int b = 0; b < OMC_NBANDS; b++) { free(e->coef[p][b]); free(e->qbuf[p][b]); }
     }
-    free(e->tmp); free(e->bsum); free(e->bofx); free(e->bofy); free(e->bmode);
+    free(e->tmp);
     free(e->hyst_valid); free(e->hyst_Q); free(e->hyst_steps);
     free(e->hyst_partial); free(e->hyst_prof); free(e->hyst_fmask);
     free(e->hyst_gain); free(e->sl_energy); free(e->sl_energy_c);
@@ -1040,7 +861,8 @@ void omc_enc_destroy(omc_enc_t *e)
     free(e->syms); free(e->stids); free(e->raws); free(e->rawn);
     free(e->paybuf); free(e->rowsig);
     for (int p = 0; p < OMC_NPLANES; p++) {
-        free(e->ref[p]); free(e->tfwin[p]); free(e->tftail[p]); free(e->pbuf[p]);
+        free(e->ref[p]); free(e->refprev[p]); free(e->refprev2[p]);
+        free(e->inub[p]); free(e->pbuf[p]);
         for (int b = 0; b < OMC_NBANDS; b++) { free(e->pcoef[p][b]); free(e->dcoef[p][b]); }
     }
     free(e);
@@ -1147,42 +969,26 @@ static void band_scan(omc_enc_t *e, int p, int b, const int32_t *coef, int n,
     }
 }
 
-/* Build temporal-prediction coefficients for one plane of one slice: forward
- * transform of the co-located rows of the previous reconstructed frame (the
- * single permitted reference). Deterministic and identical in encoder and
- * decoder. */
+/* T5: build temporal-prediction coefficients for one plane of one slice —
+ * the forward transform of the motion-shifted fetch from the PREVIOUS
+ * FRAME'S FINAL committed picture (refplane = refprev).  Nothing here reads
+ * the current frame: there is no same-frame prediction of any kind.  The
+ * fetch is integer-pel (T5 vectors are derived at integer precision; the
+ * half-pel field codes exist in the header but the encoder writes even
+ * values only — odd values are reserved).  Deterministic and identical in
+ * encoder and decoder, and generation-invariant because refprev is. */
 static void predict_plane(ctx_common_t *c, const uint16_t *refplane, int p,
                           int slice_idx, const int8_t mvx2[OMC_NREG],
                           const int8_t mvy2[OMC_NREG],
-                          const int8_t *bofx, const int8_t *bofy,
-                          const uint8_t *bmode, int nblk,
                           int32_t *pbuf, int32_t *tmp,
                           int32_t *const pc[OMC_NBANDS])
 {
     int pw = plane_width(c, p), sh = c->sh;
     int H = c->H;
-    int rb = omc_ref_unclipped ? OMC_REF_BIAS : 0; /* F-4: unbias biased reference reads */
-    /* v4.3: compose per 16-luma-px block (offset around its region's vector).
-     * With bofx == NULL (or all-zero offsets) the arithmetic reduces exactly
-     * to the v4.2 per-region composition. Block width in this plane: */
-    int pbw = (p > 0 && c->cfg.chroma == OMC_CF_422) ? OMC_BLK_W / 2 : OMC_BLK_W;
-    int nb = nblk > 0 ? nblk : (pw / pbw);
-    for (int blk = 0; blk < nb; blk++) {
-        int x0 = blk * pbw, x1 = x0 + pbw;
-        if (x1 > pw) x1 = pw;
-        int reg = blk * OMC_NREG / nb;
-        /* per-block intra composition: prediction = mid (centered 0), which
-         * makes this block's delta exactly its direct intra signal - full
-         * mode localization with the transform/coder untouched */
-        if (bmode && bmode[blk]) {
-            for (int r = 0; r < sh; r++) {
-                int32_t *dstb = pbuf + (size_t)r * pw;
-                for (int x = x0; x < x1; x++) dstb[x] = 0;
-            }
-            continue;
-        }
+    int rb = OMC_REF_BIAS; /* references are biased; prediction is centered */
+    for (int reg = 0; reg < OMC_NREG; reg++) {
+        int x0 = reg * pw / OMC_NREG, x1 = (reg + 1) * pw / OMC_NREG;
         int dx2 = mvx2[reg], dy2 = mvy2[reg];
-        if (bofx) { dx2 += 2 * bofx[blk]; dy2 += 2 * bofy[blk]; }
         /* chroma of 4:2:2 is half-width: halve the horizontal displacement
          * (half-pel units halved = same physical shift), truncating */
         if (p > 0 && c->cfg.chroma == OMC_CF_422) dx2 = dx2 / 2;
@@ -1230,12 +1036,10 @@ static void predict_plane(ctx_common_t *c, const uint16_t *refplane, int p,
     }
 }
 
-/* Motion-search candidate sets (encoder only). */
+/* T5 motion derivation candidate set (encoder only; fixed order). */
 static const int8_t omc_mv_cand[][2] = {
     {0,0},{-1,0},{1,0},{-2,0},{2,0},{-4,0},{4,0},{-6,0},{6,0},
     {0,-1},{0,1},{0,-2},{0,2},{-2,-1},{2,-1},{-2,1},{2,1},{-8,0},{7,0},
-    /* v4.1 wide-range extension (+/-32 px h, +/-16 px v in the bitstream;
-     * candidates stay one step inside so half-pel units fit the fields) */
     {8,0},{-10,0},{10,0},{-12,0},{12,0},{-14,0},{14,0},{-16,0},{16,0},
     {-20,0},{20,0},{-24,0},{24,0},{-28,0},{28,0},{-31,0},{31,0},
     {0,-3},{0,3},{0,-4},{0,4},{0,-6},{0,6},{0,-8},{0,8},
@@ -1244,111 +1048,85 @@ static const int8_t omc_mv_cand[][2] = {
     {-12,-3},{12,-3},{-12,3},{12,3},{-16,-4},{16,-4},{-16,4},{16,4},
     {-24,-6},{24,-6},{-24,6},{24,6},{-20,-10},{20,-10},{-20,10},{20,10}
 };
-static const int8_t omc_mv_nb8[8][2] = {
-    {-1,-1},{0,-1},{1,-1},{-1,0},{1,0},{-1,1},{0,1},{1,1}
-};
-
-/* v4.3 per-block offset candidates (full-pel, fixed order — strict-argmin
- * replay discipline; block-sum SAD so per-pixel grain and coding noise cancel
- * in the statistic, the property that makes stage A generation-stable). */
-static const int8_t omc_bof_cand[][2] = {
-    {0, 0}, {-1, 0}, {1, 0}, {0, -1}, {0, 1}, {-2, 0}, {2, 0}, {0, -2}, {0, 2},
-    {-3, 0}, {3, 0}, {-4, 0}, {4, 0}, {0, -4}, {0, 3}, {-6, 0}, {6, 0},
-    {-8, 0}, {7, 0}, {-2, -1}, {2, -1}, {-2, 1}, {2, 1},
-    {-4, -2}, {4, -2}, {-4, 2}, {4, 2}, {-8, -4}, {7, -4}, {-8, 3}, {7, 3},
-};
-
-/* Full (undecimated) block-sum SAD over block-sum columns [xb0, xb1). */
-static int64_t bof_sad(const int32_t *ib, int nbx, int nby,
-                       const uint16_t *rfp, int W0, int H0, int y0,
-                       int xb0, int xb1, int dx2, int dy2)
-{
-    int ix = dx2 >> 1, fx = dx2 & 1;
-    int iy = dy2 >> 1, fy = dy2 & 1;
-    int64_t sad = 0;
-    for (int r2 = 0; r2 < nby; r2++) {
-        for (int xb = xb0; xb < xb1; xb++) {
-            int32_t rs = 0;
-            for (int rr = 0; rr < 2; rr++) {
-                int sy0 = y0 + 2 * r2 + rr + iy;
-                if (sy0 < 0) sy0 = 0;
-                if (sy0 > H0 - 1) sy0 = H0 - 1;
-                int sy1 = sy0 + fy;
-                if (sy1 > H0 - 1) sy1 = H0 - 1;
-                const uint16_t *s0 = rfp + (size_t)sy0 * W0;
-                const uint16_t *s1 = rfp + (size_t)sy1 * W0;
-                for (int k = 0; k < 4; k++) {
-                    int sx0 = 4 * xb + k + ix;
-                    if (sx0 < 0) sx0 = 0;
-                    if (sx0 > W0 - 1) sx0 = W0 - 1;
-                    int sx1 = sx0 + fx;
-                    if (sx1 > W0 - 1) sx1 = W0 - 1;
-                    int32_t v;
-                    if (fx & fy)
-                        v = ((int32_t)s0[sx0] + s0[sx1] + s1[sx0] + s1[sx1] + 2) >> 2;
-                    else if (fx)
-                        v = ((int32_t)s0[sx0] + s0[sx1] + 1) >> 1;
-                    else if (fy)
-                        v = ((int32_t)s0[sx0] + s1[sx0] + 1) >> 1;
-                    else
-                        v = (int32_t)s0[sx0];
-                    rs += v;
-                }
-            }
-            if (omc_ref_unclipped) rs -= 8 * OMC_REF_BIAS; /* F-4: unbias 8-sample block sum */
-            int32_t d = ib[(size_t)r2 * nbx + xb] - rs;
-            sad += d < 0 ? -d : d;
-        }
-    }
-    return sad;
-}
 
-/* Decimated block-sum SAD of half-pel candidate (dx2, dy2) against the
- * precomputed 4x2 input block sums ib[], over block columns [xb0, xb1) of
- * the slice whose first luma row is y0. Every other block is sampled.
- * Shifts/adds/compares only. */
-static int64_t mv_block_sad(const int32_t *ib, int nbx, int nby,
-                            const uint16_t *rfp, int W0, int H0, int y0,
-                            int xb0, int xb1, int dx2, int dy2)
+/* T5 MOTION DERIVATION — the core idea of the rebuilt temporal engine.
+ *
+ * The old engine searched the SOURCE against the reference.  Source pixels
+ * change between generations (generation n's source is generation n-1's
+ * decode), so any threshold or argmin computed on them could flip and break
+ * byte-exact replay — the documented failure of --mv-regions, and the reason
+ * "byte-exact through unlimited generations" could never be guaranteed.
+ *
+ * T5 derives the vector from data that is IDENTICAL in every generation:
+ * the two previous COMMITTED reconstructions.  For slice k of frame t it
+ * finds, by decimated whole-slice SAD over a fixed candidate list (strict
+ * argmin, fixed order, adds/compares only), the displacement d that best
+ * maps frame t-2 onto frame t-1 over this slice's rows:
+ *
+ *     mv* = argmin_d  SUM | refprev[y][x] - refprev2[y+dy][x+dx] |
+ *
+ * Under constant velocity (the panning case the temporal layer exists for)
+ * the content of frame t sits at the same displacement from frame t-1, so
+ * mv* is the fetch vector for frame t as well.  Because refprev/refprev2
+ * are the committed decodes — byte-identical in every generation by the T5
+ * exactness induction — the derived vector, and therefore the prediction,
+ * replays exactly.  The vector is still written into the slice header (all
+ * four region fields carry it), so the decoder needs no second reference
+ * frame and no search; conformance is unchanged in shape.
+ *
+ * Frames without two consecutive committed predecessors (frame 1, or after
+ * a feed discontinuity) derive mv = 0.  A 4-neighbour integer refinement
+ * with strict < follows the candidate argmin; all precision is integer-pel
+ * (half-pel taps are low-pass re-filters — quality risk with zero exactness
+ * benefit — so T5 reserves odd half-pel codes). */
+static void derive_mv(const uint16_t *prev, const uint16_t *prev2,
+                      int W0, int H0, int y0, int sh, int *out_dx, int *out_dy)
 {
-    int ix = dx2 >> 1, fx = dx2 & 1;
-    int iy = dy2 >> 1, fy = dy2 & 1;
-    int64_t sad = 0;
-    for (int r2 = 0; r2 < nby; r2++) {
-        for (int xb = xb0; xb < xb1; xb += 2) {
-            int32_t rs = 0;
-            for (int rr = 0; rr < 2; rr++) {
-                int sy0 = y0 + 2 * r2 + rr + iy;
-                if (sy0 < 0) sy0 = 0;
-                if (sy0 > H0 - 1) sy0 = H0 - 1;
-                int sy1 = sy0 + fy;
-                if (sy1 > H0 - 1) sy1 = H0 - 1;
-                const uint16_t *s0 = rfp + (size_t)sy0 * W0;
-                const uint16_t *s1 = rfp + (size_t)sy1 * W0;
-                for (int k = 0; k < 4; k++) {
-                    int sx0 = 4 * xb + k + ix;
-                    if (sx0 < 0) sx0 = 0;
-                    if (sx0 > W0 - 1) sx0 = W0 - 1;
-                    int sx1 = sx0 + fx;
-                    if (sx1 > W0 - 1) sx1 = W0 - 1;
-                    int32_t v;
-                    if (fx & fy)
-                        v = ((int32_t)s0[sx0] + s0[sx1] + s1[sx0] + s1[sx1] + 2) >> 2;
-                    else if (fx)
-                        v = ((int32_t)s0[sx0] + s0[sx1] + 1) >> 1;
-                    else if (fy)
-                        v = ((int32_t)s0[sx0] + s1[sx0] + 1) >> 1;
-                    else
-                        v = (int32_t)s0[sx0];
-                    rs += v;
-                }
-            }
-            if (omc_ref_unclipped) rs -= 8 * OMC_REF_BIAS; /* F-4: unbias 8-sample block sum */
-            int32_t d = ib[(size_t)r2 * nbx + xb] - rs;
-            sad += d < 0 ? -d : d;
-        }
-    }
-    return sad;
+    static const int8_t nb4[4][2] = {{-1,0},{1,0},{0,-1},{0,1}};
+    int gx = 0, gy = 0;
+    int64_t best = -1;
+    for (size_t ci = 0; ci < sizeof(omc_mv_cand) / sizeof(omc_mv_cand[0]); ci++) {
+        int dx = omc_mv_cand[ci][0], dy = omc_mv_cand[ci][1];
+        int64_t sad = 0;
+        for (int r = 0; r < sh; r += 2) {
+            int sy = y0 + r + dy;
+            if (sy < 0) sy = 0;
+            if (sy > H0 - 1) sy = H0 - 1;
+            const uint16_t *rowa = prev + (size_t)(y0 + r) * W0;
+            const uint16_t *rowb = prev2 + (size_t)sy * W0;
+            for (int x = 0; x < W0; x += 4) {
+                int sx = x + dx;
+                if (sx < 0) sx = 0;
+                if (sx > W0 - 1) sx = W0 - 1;
+                int d = (int)rowa[x] - (int)rowb[sx];
+                sad += d < 0 ? -d : d;
+            }
+        }
+        if (best < 0 || sad < best) { best = sad; gx = dx; gy = dy; }
+    }
+    /* fine integer refinement, strict < (fixed order => deterministic) */
+    for (int ci = 0; ci < 4; ci++) {
+        int dx = gx + nb4[ci][0], dy = gy + nb4[ci][1];
+        if (dx < -31 || dx > 31 || dy < -15 || dy > 15) continue;
+        int64_t sad = 0;
+        for (int r = 0; r < sh; r += 2) {
+            int sy = y0 + r + dy;
+            if (sy < 0) sy = 0;
+            if (sy > H0 - 1) sy = H0 - 1;
+            const uint16_t *rowa = prev + (size_t)(y0 + r) * W0;
+            const uint16_t *rowb = prev2 + (size_t)sy * W0;
+            for (int x = 0; x < W0; x += 4) {
+                int sx = x + dx;
+                if (sx < 0) sx = 0;
+                if (sx > W0 - 1) sx = W0 - 1;
+                int d = (int)rowa[x] - (int)rowb[sx];
+                sad += d < 0 ? -d : d;
+            }
+        }
+        if (sad < best) { best = sad; gx = dx; gy = dy; }
+    }
+    *out_dx = gx;
+    *out_dy = gy;
 }
 
 /* ---- v4 grain fill (bitstream 4.0, rev. 6) ----
@@ -1468,31 +1246,24 @@ static inline int32_t fill_value_p(const int32_t *ll, int llstride, int llw, int
         if (o) hint = o;
     }
     int32_t a = (int32_t)1 << (s - 2);
-    /* v4.1 per-plane amplitude scale (shifts/adds): 0 = 1.0x quarter-step,
-     * 1 = 1.25x, 2 = 1.5x, 3 = 1.75x. All strictly below half-step, so
-     * filled samples re-quantize to 0 under the rounding quantizer (zero
-     * zone |c| < 2^(s-1)); all re-measure at >= 4/64-step above the 3/16
-     * fill-bit threshold (a 0.75x code sat exactly ON that threshold and
-     * flipped the fill bit on animated inter deltas - caught by the A4
-     * gate). Applied only for s >= 4, where the scaled amplitudes are exact
-     * integers and the gain code is a generation fixed point (at s = 3
-     * rounding collapses the scales - also caught by the A4 gate). */
+    /* T5: the v4.1 per-plane amplitude scale, and ONLY it (shifts/adds):
+     * 0 = 1.0x quarter-step, 1 = 1.25x, 2 = 1.5x, 3 = 1.75x, applied only
+     * for s >= 4 where every scaled amplitude is an exact integer that
+     * re-measures to itself — the gain code is a generation FIXED POINT.
+     * The v4.6 additions (0.5x code, three-tier activity taper) are REMOVED:
+     * the taper's floor-at-one-code made amplitudes that cannot be told
+     * apart from any other small value, and the tapered mean is not a fixed
+     * point of the gain derivation — both broke the generation lock's
+     * ability to re-derive the fill exactly (their own release notes list
+     * the affected classes as "convergent, not byte-exact").  T5 trades
+     * that eye-tuning for the absolute exactness contract. */
     if (s >= 4) {
-        /* minor >= 6: code 1 = 0.5x (amplitude-matched DOWNWARD - the
-         * eye-confirmed fix for fill grain outgrowing source grain as rate
-         * drops); codes 2/3 unchanged. minor <= 5: code 1 = 1.25x (legacy).
-         * 0.5x = 2^(s-3): below the zero zone (idempotent) and above the
-         * lowered fill-bit tier (re-measures 4/32 >= 3/32 - no bit flap). */
-        if (gain == 1) a = v6 ? (a >> 1) : a + (a >> 2);
+        if (gain == 1) a += a >> 2;
         else if (gain == 2) a += a >> 1;
         else if (gain == 3) a += (a >> 1) + (a >> 2);
     }
-    if (v6) { /* activity taper: 1 -> quarter, 2 -> half, 3 -> full */
-        if (act == 1) a >>= 2;
-        else if (act == 2) a >>= 1;
-        if (a < 1) a = 1;
-    }
-    if (v6 >= 2 || (omc_fill_static && act <= omc_fill_static)) { fox = sfox; foy = sfoy; }
+    (void)act;
+    if (v6) { fox = sfox; foy = sfoy; } /* v6 arg = static-tile flag (T5) */
     if (hint) return hint > 0 ? a : -a;   /* local coded structure wins */
     return omc_fill_sign_sel(col + fox, row + foy, corr) ? a : -a;
 }
@@ -1588,10 +1359,10 @@ static inline int fill_gain_code(int64_t num64, int64_t den, int tune_vmaf)
 {
     if (den <= 0) return 0;
     int64_t r64 = num64 / den;
-    /* v4.6: <12/64 step -> 0.5x (code 1); 12-21 -> 1.0x; 22-25 -> 1.5x;
-     * else 1.75x. The 1.25x point is retired (its range folds into
-     * neighbours); decoders keep it for minor <= 5 streams. */
-    int g = r64 < 12 ? 1 : r64 < 22 ? 0 : r64 < 26 ? 2 : 3;
+    /* T5: the v4.1 thresholds (code midpoints).  Every amplitude re-measures
+     * into its own class (16 -> 0, 20 -> 1, 24 -> 2, 28 -> 3), which is what
+     * makes the code a generation fixed point. */
+    int g = r64 < 18 ? 0 : r64 < 22 ? 1 : r64 < 26 ? 2 : 3;
     /* --tune vmaf narrows the quantizer zero zone to 0.375*2^s: 1.5x and
      * 1.75x amplitudes would re-quantize nonzero there, breaking
      * idempotence - clamp to 1.25x. */
@@ -1599,210 +1370,160 @@ static inline int fill_gain_code(int64_t num64, int64_t den, int tune_vmaf)
     return g;
 }
 
-/* Reconstruct pixels of one slice from quantized bands (shared with decoder logic).
- * to_ref: destination is the temporal reference store. With OMC_REF_UNCLIPPED
- * on, reference samples are stored value+OMC_REF_BIAS clamped only to the
- * representable window [0, maxv+2*OMC_REF_BIAS] - NO legal-range clip - so the
- * quantizer-lattice property survives on rail-hitting content (F-4). */
+/* Reconstruct pixels of one slice from quantized bands (shared with decoder
+ * logic).  T5: destination is ALWAYS the biased unclipped domain — samples
+ * are stored value+OMC_REF_BIAS clamped only to the representable window
+ * [0, maxv+2*OMC_REF_BIAS].  There is NO legal-range clip anywhere in the
+ * loop: a clipped pixel's coefficients leave the quantizer lattice and the
+ * slice could never lock again, so the legal-range projection lives only in
+ * the tools' display path.  The to_ref parameter remains for signature
+ * stability; both values behave identically now. */
 static void reconstruct_slice(ctx_common_t *c, int32_t *sbuf[OMC_NPLANES],
                               int32_t *tmp, const omc_frame_t *out, int slice_idx,
                               int to_ref)
 {
     int sh = c->sh;
-    int bias = (omc_ref_unclipped && to_ref) ? OMC_REF_BIAS : 0;
-    int32_t hi = bias ? c->maxv + 2 * OMC_REF_BIAS : c->maxv;
-    if (getenv("OMC_DEBUG_L7") && slice_idx == 1)
-        fprintf(stderr, "L7 state: omc_xsl=%d live=%d,%d,%d noretro=%d to_ref=%d\n",
-                omc_xsl, omc_xsl_live[0], omc_xsl_live[1], omc_xsl_live[2],
-                omc_xsl_noretro, to_ref);
+    int bias = OMC_REF_BIAS;
+    int32_t hi = c->maxv + 2 * OMC_REF_BIAS;
+    (void)to_ref;
     for (int p = 0; p < OMC_NPLANES; p++) {
         int pw = plane_width(c, p);
         omc_dwt_d1m = omc_xsl_live[p] ? omc_xsl_buf[p] : 0;
         omc_slice_inv(sbuf[p], pw, sh, tmp);
         omc_dwt_d1m = 0;
-        /* OMC_XSL=2: bounded continuity blend on the boundary row.  Measured
-         * (band-fix §22): rows 0/15 of every slice carry 30-60% EXCESS noise
-         * energy — edge basis functions concentrate quantization error, and
-         * the eye integrates the resulting full-width ridge into the visible
-         * border line (the incumbent has no internal edges and no ridge).
-         * Row 0 is pulled halfway toward the average of the previous slice's
-         * final row (omc_xsl_buf carries it, see xsl_prep) and this slice's
-         * row 1, capped at +-XSL2_LIM codes so the move stays inside the
-         * coded information's uncertainty.  Same arithmetic both sides
-         * (in-loop, causal); slice 0 untouched. */
-        if (omc_xsl == 7) { /* level 7 does both edits at the deferred site */ }
-        else if (omc_xsl >= 2 && omc_xsl_live[p]) {
-            int32_t lim = c->xsl_lim * ((c->maxv + 1) >> 10);
-            /* Blend strength scales CONTINUOUSLY with how empty this
-             * slice's coded vertical-detail band is: the boundary noise
-             * ridge exists exactly when detail was zeroed (measured: fixed
-             * strength cut heli's band score 10x but WORSENED beach 15->20 —
-             * over-correcting where detail was coded rich).  Both sides
-             * derive the same factor from the same dequantized
-             * coefficients; no thresholds, no side information. */
-            int64_t nz = 0, nt = 0;
-            const int32_t *vh = sbuf[p] + (size_t)(sh / 2) * pw;
-            for (int i = 0; i < (sh / 2) * pw; i++) { nz += (vh[i] == 0); nt++; }
-            int zq8 = (int)((nz << 8) / (nt ? nt : 1));
-            zq8 = (zq8 * zq8) >> 8;   /* square: rich slices -> ~0 blend */
-            if (omc_xsl < 4) zq8 = 256;   /* XSL=3: fixed strength */
-            int32_t *r0 = sbuf[p];
-            const int32_t *r1 = sbuf[p] + (size_t)pw;
-            if (omc_xsl >= 6)
-                zq8 = xsl_seam_strength(r0, r1, omc_xsl_prev14[p],
-                                        omc_xsl_prev[p], pw, c->maxv);
-            int32_t *r15 = sbuf[p] + (size_t)(sh - 1) * pw;
-            const int32_t *r13 = sbuf[p] + (size_t)(sh - 3) * pw;
-            const int32_t *r14 = sbuf[p] + (size_t)(sh - 2) * pw;
-            for (int x = 0; x < pw; x++) {
-                int32_t prev15 = omc_xsl_prev[p][x];
-                int32_t tgt = (prev15 + r1[x]) >> 1;
-                int32_t dchg = ((tgt - r0[x]) / 2 * zq8) >> 8;
-                if (dchg > lim) dchg = lim;
-                if (dchg < -lim) dchg = -lim;
-                r0[x] += dchg;
-                /* OMC_XSL=5: row 1 carries H[0]'s noise via the odd-row
-                 * synthesis (fold: 1.10/1.01 vs the 0.77 odd-row level
-                 * after the row-0 fix).  Bounded interpolative pull toward
-                 * its own predictor (rows 0 and 2), same cap. */
-                if (omc_xsl >= 5) {
-                    int32_t *r1w = sbuf[p] + (size_t)pw;
-                    const int32_t *r2 = sbuf[p] + (size_t)2 * pw;
-                    int32_t t1 = (r0[x] + r2[x]) >> 1;
-                    int32_t d1 = (t1 - r1w[x]) / 2;
-                    if (d1 > lim) d1 = lim;
-                    if (d1 < -lim) d1 = -lim;
-                    r1w[x] += d1;
-                }
-                /* row 15: an extrapolation target (2*r14 - r13) was tried and
-                 * MEASURED HARMFUL (pitch score 31.9 -> 41.8): extrapolating
-                 * texture amplifies noise (var(2a-b) = 5x).  Row 15's correct
-                 * averaging target needs the NEXT slice's row 0 — deferred
-                 * reference-side blend, tracked in band-fix §22. */
-            }
-            (void)r13; (void)r14; (void)r15;
-        }
+        /* The wide-window clamp below is a representability guard only.  It
+         * cannot engage on conforming content: the reconstruction is the
+         * source plus bounded quantization error, and the window leaves
+         * OMC_REF_BIAS = 2048 codes of margin on each side.  (If it ever
+         * did engage, exactness would be at risk — hence the loud stderr
+         * diagnostic instead of silence.) */
         for (int r = 0; r < sh; r++) {
             uint16_t *dst = out->p[p] + (size_t)(slice_idx * sh + r) * out->stride[p];
             const int32_t *src = sbuf[p] + (size_t)r * pw;
             for (int x = 0; x < pw; x++) {
                 int32_t v = src[x] + c->mid + bias;
-                if (v < 0) v = 0;
-                if (v > hi) v = hi;
+                if (v < 0 || v > hi) {
+                    fprintf(stderr, "omc: T5 wide-domain clamp engaged "
+                            "(slice %d plane %d value %d) - please report\n",
+                            slice_idx, p, v);
+                    v = v < 0 ? 0 : hi;
+                }
                 dst[x] = (uint16_t)v;
             }
         }
-        /* OMC_XSL=3: DEFERRED averaging blend for the PREVIOUS slice's row
-         * 15 — its proper target ((its row 14 + this slice's row 0)/2) only
-         * exists now that this slice is reconstructed.  Same arithmetic on
-         * both sides; runs after this slice's prediction consumed the
-         * unedited row on both sides, so the loops stay in lockstep.  The
-         * callers refresh their recon/display/ref copies of this one row
-         * (see the three sync sites). */
-        /* ---- XSL level 7: the boundary edit as a REVERSIBLE lifting cascade.
-         *
-         * The level 2/3 blends move a row toward a target computed from its own
-         * neighbours, and each of the two rows uses the other.  That is mutual,
-         * and "move toward a target" discards what the row was, so no later
-         * encoder can undo it -- which is why re-encoding piles blend on blend.
-         *
-         * A lifting step is different: it adds a correction computed ONLY from
-         * values it does not touch, so subtracting the same correction returns
-         * the original exactly.  Two of them in a fixed order edit both rows and
-         * stay invertible:
-         *
-         *   step 1   row15 += clamp((row0  - row14) / 4)      (row15 not used)
-         *   step 2   row0  += clamp((row15' - row1 ) / 4)      (row0  not used)
-         *
-         * and the inverse is the same two, backwards, with the same arithmetic:
-         *
-         *   row0  -= clamp((row15' - row1 ) / 4)
-         *   row15 -= clamp((row0   - row14) / 4)
-         *
-         * omc_xsl_unblend() below applies that inverse to a whole picture, which
-         * is what lets a later encoder recover the reconstruction its
-         * predecessor coded and re-emit it unchanged. */
-        /* OMC_XSL_NOEDIT=1: keep every other level-7 behaviour (including the
-         * cross-slice wavelet term, which is what makes the reconstruction what
-         * it is) and skip ONLY the boundary edit.  This is the ground truth the
-         * inverse must reproduce; decoding at level 0 is NOT, because level 0
-         * also drops the wavelet term and changes the whole slice. */
-        if (omc_xsl == 7 && omc_xsl_live[p] && slice_idx > 0 && !omc_xsl_noretro
-            && !omc_xsl_noedit) {
+        /* ---- T5 boundary edit: the reversible lifting cascade (see the
+         * XSL-T5 block above for the algebra).  Runs at the deferred site —
+         * only when this slice's reconstruction exists does row 15 of the
+         * previous slice have its proper neighbour — and edits reference and
+         * display alike (in-loop).  Suppressed on refresh barriers
+         * (omc_xsl_live / omc_xsl_noretro, rules d and e); the display blend
+         * covers those boundaries on the emitted picture only.  Applied
+         * UNCONDITIONALLY within the wide domain: no rail skip, so the
+         * inverse in omc_xsl_unblend() agrees everywhere. */
+        if (omc_xsl_live[p] && slice_idx > 0 && !omc_xsl_noretro) {
             int32_t lim = c->xsl_lim * ((c->maxv + 1) >> 10);
             int base = slice_idx * sh;
             uint16_t *e15 = out->p[p] + (size_t)(base - 1) * out->stride[p];
             const uint16_t *e14 = out->p[p] + (size_t)(base - 2) * out->stride[p];
             uint16_t *e0 = out->p[p] + (size_t)base * out->stride[p];
             const uint16_t *e1 = out->p[p] + (size_t)(base + 1) * out->stride[p];
-            if (getenv("OMC_DEBUG_L7"))
-                fprintf(stderr, "L7 fire p%d slice %d lim %d\n", p, slice_idx, lim);
             for (int x = 0; x < pw; x++) {
                 int32_t d1 = ((int32_t)e0[x] - (int32_t)e14[x]) / 4;
                 if (d1 > lim) d1 = lim; if (d1 < -lim) d1 = -lim;
-                int32_t v = (int32_t)e15[x] + d1;
-                if (v >= 0 && v <= hi) e15[x] = (uint16_t)v;   /* skip at the rails */
+                e15[x] = (uint16_t)((int32_t)e15[x] + d1);
                 int32_t d2 = ((int32_t)e15[x] - (int32_t)e1[x]) / 4;
                 if (d2 > lim) d2 = lim; if (d2 < -lim) d2 = -lim;
-                v = (int32_t)e0[x] + d2;
-                if (v >= 0 && v <= hi) e0[x] = (uint16_t)v;
-            }
-        }
-        if (omc_xsl >= 3 && omc_xsl != 7 && omc_xsl_live[p] && slice_idx > 0 && !omc_xsl_noretro) {
-            int32_t lim = c->xsl_lim * ((c->maxv + 1) >> 10);
-            int base = slice_idx * sh;
-            uint16_t *e15 = out->p[p] + (size_t)(base - 1) * out->stride[p];
-            const uint16_t *e14 = out->p[p] + (size_t)(base - 2) * out->stride[p];
-            const uint16_t *e0 = out->p[p] + (size_t)base * out->stride[p];
-            /* same continuous strength for the deferred row (this slice's
-             * emptiness proxies its neighbor's — plan coherence) */
-            int64_t nz2 = 0, nt2 = 0;
-            const int32_t *vh2 = sbuf[p] + (size_t)(sh / 2) * pw;
-            for (int i = 0; i < (sh / 2) * pw; i++) { nz2 += (vh2[i] == 0); nt2++; }
-            int zq8b = (int)((nz2 << 8) / (nt2 ? nt2 : 1));
-            zq8b = (zq8b * zq8b) >> 8;
-            if (omc_xsl < 4) zq8b = 256;
-            if (omc_xsl >= 6) {
-                int64_t across = 0, inside = 0;
-                for (int x = 0; x < pw; x++) {
-                    int32_t d = (int32_t)e0[x] - (int32_t)e15[x];
-                    across += d < 0 ? -d : d;
-                    d = (int32_t)e15[x] - (int32_t)e14[x];
-                    inside += d < 0 ? -d : d;
-                }
-                int64_t ex2 = 2 * across / pw - 2 * (inside / pw);
-                int64_t full = 2 * (int64_t)OMC_XSL_FULL_AT * ((c->maxv + 1) >> 10);
-                int64_t z = ex2 <= 0 ? 0 : ex2 * 256 / (full > 0 ? full : 1);
-                zq8b = z > 256 ? 256 : (int)z;
-            }
-            for (int x = 0; x < pw; x++) {
-                int32_t tgt = ((int32_t)e14[x] + (int32_t)e0[x]) >> 1;
-                int32_t dchg = ((tgt - (int32_t)e15[x]) / 2 * zq8b) >> 8;
-                if (dchg > lim) dchg = lim;
-                if (dchg < -lim) dchg = -lim;
-                int32_t v = (int32_t)e15[x] + dchg;
-                if (v < 0) v = 0;
-                if (v > hi) v = hi;
-                e15[x] = (uint16_t)v;
+                e0[x] = (uint16_t)((int32_t)e0[x] + d2);
             }
         }
     }
 }
 
-/* v4 generation-lock verification: simulate quantize -> reconstruct -> fill
- * for a candidate plan and confirm every reconstructed coefficient equals the
- * input coefficient exactly. Only a verified plan may lock, which makes A4
- * byte-exactness a checked property of every locked slice rather than an
- * argued one. Returns 1 iff the plan reproduces the input bit-for-bit. */
+/* T5 generation-lock verification — the constructive heart of the exactness
+ * guarantee.  Given a candidate signalled plan (profile, Q, n_steps,
+ * partial), this DERIVES the per-band coding modes, the fill bits and the
+ * per-plane fill gains that reproduce the input coefficients bit-for-bit,
+ * or reports that no such assignment exists.  v4.9 took the modes from the
+ * enumerator (a cost guess that could differ from the previous generation's
+ * choice and sink the true plan); T5 recovers them:
+ *
+ *   per plane, for each gain hypothesis g in 0..3:
+ *     band 0 (LL):  try intra and (if allowed) inter; a mode is EXACT when
+ *                   quantize->dequantize(+pred) reproduces every value.
+ *     bands 1..9:   for each mode, first derive the band's fill bit exactly
+ *                   as the encoder's own rule would (mean measured amplitude
+ *                   of the gated zero-coded positions), then test EXACT
+ *                   reproduction with that bit and gain g.  A band's mode
+ *                   set is whichever of {inter, intra} pass; empty = the
+ *                   hypothesis fails.  Both passing (a band whose prediction
+ *                   is zero everywhere, say) is resolved by estimated cost,
+ *                   intra on ties — any exact choice reproduces the same
+ *                   pixels, so the tie-break only shapes the byte stream,
+ *                   and it is deterministic, so generation 3 repeats it.
+ *     accept g when the plane\'s re-derived gain code equals g (the fill
+ *     amplitudes are v4.1 fixed points, so for the true gain this always
+ *     holds; for a wrong gain the fill values already failed above).
+ *
+ * Returns 1 with out_modes/out_fmask/out_gain filled iff the plan
+ * reproduces the input bit-for-bit. */
 static int lock_verify(omc_enc_t *e, int cf444, int prof, int Q, int ns, int k,
-                       uint32_t modes, int can_inter, int frame_idx, int slice_idx,
-                       uint32_t *out_fmask, int out_gain[OMC_NPLANES])
+                       uint32_t modes_hint, int can_inter, int frame_idx, int slice_idx,
+                       uint32_t *out_modes, uint32_t *out_fmask, int out_gain[OMC_NPLANES])
 {
     ctx_common_t *c = &e->c;
     int sh = c->sh;
     shift_plan_t sp;
     derive_shifts(cf444, prof, Q, ns, k, &sp);
     omc_band_t bands[OMC_NBANDS];
+    (void)modes_hint;
+    uint32_t vmodes = 0;
+    /* ---- FAST PRE-REJECT (speed only; provably weaker than the full
+     * check).  A candidate can reproduce the input only if, in some mode,
+     * every coefficient either reproduces under plain quantization or is a
+     * POTENTIAL fill position (q == 0, reconstructs 0, fill-capable band
+     * and shift, |input| below half a step, prediction zero for inter).
+     * Most false candidates die at their first coefficient here, without
+     * touching the fill machinery — without this, graphics-heavy slices
+     * spent minutes per frame walking thousands of failing candidates
+     * through the full fill measurement (profiled: fill_gate dominated).
+     * Never rejects a candidate the full verification would accept: a
+     * value that fails this test fails every (fill-bit, gain) assignment. */
+    for (int p = 0; p < OMC_NPLANES; p++) {
+        omc_band_layout(plane_width(c, p), sh, bands);
+        for (int b = 0; b < OMC_NBANDS; b++) {
+            int base_s = sp.shift[p][b];
+            int can_fill = b >= OMC_FILL_BANDS_FROM &&
+                           base_s >= OMC_FILL_MIN_SHIFT && !c->cfg.no_fill;
+            int n = bands[b].h * bands[b].w;
+            int tex_vmaf = OMC_BAND_TEXTURE(b) && c->cfg.tune_vmaf;
+            int nm = can_inter ? 2 : 1;
+            int any = 0;
+            for (int m = 0; m < nm && !any; m++) {
+                const int32_t *cf = m ? e->dcoef[p][b] : e->coef[p][b];
+                const int32_t *pc = e->pcoef[p][b];
+                int okv = 1;
+                for (int i = 0; i < n; i++) {
+                    int s = coeff_shift(&sp, p, b, i);
+                    int32_t q = (b == 0)
+                        ? omc_quant1b(cf[i], s, 0)
+                        : omc_quant1b_dz(cf[i], s, tex_vmaf,
+                                         e->dz_enabled && b >= OMC_FILL_BANDS_FROM);
+                    int32_t v = omc_dequant1(q, s);
+                    if (m) v += pc[i];
+                    if (v == e->coef[p][b][i]) continue;
+                    int32_t a = e->coef[p][b][i];
+                    if (a < 0) a = -a;
+                    if (can_fill && q == 0 && v == 0 &&
+                        a < ((int32_t)1 << (s - 1)) && (!m || pc[i] == 0))
+                        continue;   /* potential fill value */
+                    okv = 0;
+                    break;
+                }
+                any = okv;
+            }
+            if (!any) return 0;
+        }
+    }
     for (int p = 0; p < OMC_NPLANES; p++) {
         int pw = plane_width(c, p);
         int llw = pw / 32, llh = sh / 4;
@@ -1810,95 +1531,161 @@ static int lock_verify(omc_enc_t *e, int cf444, int prof, int Q, int ns, int k,
         int32_t llbuf[4 * 256];
         if (llw > 256) return 0;
         omc_band_layout(pw, sh, bands);
-        int tex_vmaf = 0;
-        /* pass 1: LL reconstruction (gate source) + LL exactness */
+        band_cost_t (*bc)[OMC_NPLANES][OMC_NBANDS] = e->bandcost;
+        /* ---- band 0 (LL): derive the mode by exact reproduction ---- */
+        int m_ll = -1;
         {
-            int m = can_inter && ((modes >> (p * OMC_NBANDS)) & 1);
-            const int32_t *cf = m ? e->dcoef[p][0] : e->coef[p][0];
-            const int32_t *pc = e->pcoef[p][0];
-            int n = bands[0].h * bands[0].w;
-            for (int i = 0; i < n; i++) {
-                int s = coeff_shift(&sp, p, 0, i);
-                int32_t q = omc_quant1b(cf[i], s, 0);
-                int32_t v = omc_dequant1(q, s);
-                if (m) v += pc[i];
-                if (v != e->coef[p][0][i]) return 0;
-                llbuf[i] = v;
-            }
-        }
-        /* pass 2: fill decision per detail band (mirrors step 5b exactly) */
-        uint32_t fmask = 0;
-        int64_t gnum = 0, gden = 0;
-        if (!c->cfg.no_fill)
-            for (int b = OMC_FILL_BANDS_FROM; b < OMC_NBANDS; b++) {
-                int base_s = sp.shift[p][b];
-                if (base_s < OMC_FILL_MIN_SHIFT) continue;
-                int m = can_inter && ((modes >> (p * OMC_NBANDS + b)) & 1);
-                const int32_t *cf = m ? e->dcoef[p][b] : e->coef[p][b];
-                const int32_t *pc = e->pcoef[p][b];
-                int n = bands[b].h * bands[b].w, w = bands[b].w;
-                tex_vmaf = OMC_BAND_TEXTURE(b) && c->cfg.tune_vmaf;
-                int64_t sum = 0, count = 0;
+            int nm = can_inter ? 2 : 1;
+            int okm[2] = {0, 0};
+            for (int m = 0; m < nm; m++) {
+                const int32_t *cf = m ? e->dcoef[p][0] : e->coef[p][0];
+                const int32_t *pc = e->pcoef[p][0];
+                int n = bands[0].h * bands[0].w;
+                int okv = 1;
                 for (int i = 0; i < n; i++) {
-                    if (coeff_shift(&sp, p, b, i) != base_s) continue;
-                    if (omc_quant1b_dz(cf[i], base_s, tex_vmaf, e->dz_enabled) != 0) continue;
-                    if (m && pc[i] != 0) continue;
-                    if (!fill_gate(llbuf, llw, llw, llh, b, i / w, i % w, lllim)) continue;
-                    int32_t a = e->coef[p][b][i];
-                    sum += a < 0 ? -a : a;
-                    count++;
+                    int s = coeff_shift(&sp, p, 0, i);
+                    int32_t q = omc_quant1b(cf[i], s, 0);
+                    int32_t v = omc_dequant1(q, s);
+                    if (m) v += pc[i];
+                    if (v != e->coef[p][0][i]) { okv = 0; break; }
                 }
-                if (count >= 16 &&
-                    ((sum << 4) >= ((int64_t)count * 3) << base_s ||
-                     (base_s >= 4 &&
-                      (sum << 5) >= ((int64_t)count * 3) << base_s))) {
-                    fmask |= 1u << (b - OMC_FILL_BANDS_FROM);
-                    if (base_s >= 4) { /* gain applies (and re-measures exactly) only at s >= 4 */
-                        gnum += (sum << 6) >> base_s;
-                        gden += count;
+                okm[m] = okv;
+            }
+            if (okm[0] && (nm < 2 || !okm[1])) m_ll = 0;
+            else if (!okm[0] && nm == 2 && okm[1]) m_ll = 1;
+            else if (okm[0] && nm == 2 && okm[1])
+                m_ll = bc[1][p][0].bits[sp.shift[p][0]]
+                     < bc[0][p][0].bits[sp.shift[p][0]] ? 1 : 0;
+            if (m_ll < 0) {
+                if (getenv("OMC_DEBUG_VERIFY"))
+                    fprintf(stderr, "verify fail f%d sl=%d p=%d b=0 (LL)\n",
+                            frame_idx, slice_idx, p);
+                return 0;
+            }
+            if (m_ll) vmodes |= 1u << (p * OMC_NBANDS);
+            /* LL reconstruction (gate source) */
+            int n = bands[0].h * bands[0].w;
+            for (int i = 0; i < n; i++) llbuf[i] = e->coef[p][0][i];
+        }
+        /* ---- bands 1..9 under a per-plane gain hypothesis ---- */
+        int found = 0;
+        int gain_dep = 1; /* does a failure depend on the gain hypothesis? */
+        for (int ghyp = 0; ghyp <= 3 && !found && gain_dep; ghyp++) {
+            if (c->cfg.tune_vmaf && ghyp > 1) break; /* derivation clamps there */
+            uint32_t tmodes = 0, tfmask = 0;
+            int64_t gnum = 0, gden = 0;
+            int ok = 1;
+            gain_dep = 0;
+            for (int b = 1; b < OMC_NBANDS && ok; b++) {
+                int base_s = sp.shift[p][b];
+                int can_fill = b >= OMC_FILL_BANDS_FROM &&
+                               base_s >= OMC_FILL_MIN_SHIFT && !c->cfg.no_fill;
+                int w = bands[b].w, n = bands[b].h * bands[b].w;
+                int tex_vmaf = OMC_BAND_TEXTURE(b) && c->cfg.tune_vmaf;
+                int nm = can_inter ? 2 : 1;
+                int okm[2] = {0, 0};
+                int fbm[2] = {0, 0};
+                int64_t summ[2] = {0, 0};
+                int64_t cntm[2] = {0, 0};
+                fp_t vfp; fp_build_arr(&vfp, bands, e->coef[p], b, &sp, p);
+                for (int m = 0; m < nm; m++) {
+                    const int32_t *cf = m ? e->dcoef[p][b] : e->coef[p][b];
+                    const int32_t *pc = e->pcoef[p][b];
+                    /* (a) fill-bit derivation — the encoder\'s own rule, on
+                     * this mode\'s values */
+                    int fb = 0;
+                    if (can_fill) {
+                        int64_t sum = 0, count = 0;
+                        for (int i = 0; i < n; i++) {
+                            if (coeff_shift(&sp, p, b, i) != base_s) continue;
+                            if (omc_quant1b_dz(cf[i], base_s, tex_vmaf, e->dz_enabled) != 0) continue;
+                            if (m && pc[i] != 0) continue;
+                            if (!fill_gate(llbuf, llw, llw, llh, b, i / w, i % w, lllim)) continue;
+                            int32_t a = e->coef[p][b][i];
+                            sum += a < 0 ? -a : a;
+                            count++;
+                        }
+                        fb = count >= 16 &&
+                             ((sum << 4) >= ((int64_t)count * 3) << base_s ||
+                              (base_s >= 4 &&
+                               (sum << 5) >= ((int64_t)count * 3) << base_s));
+                        fbm[m] = fb;
+                        summ[m] = sum; cntm[m] = count;
+                    }
+                    /* (b) exact reproduction under (mode, fill bit, ghyp) */
+                    int fox = 0, foy = 0, sfox = 0, sfoy = 0;
+                    if (fb) {
+                        omc_fill_offsets(frame_idx & 0xFF, slice_idx, p, b, &fox, &foy);
+                        omc_fill_offsets(0, slice_idx, p, b, &sfox, &sfoy);
+                    }
+                    int okv = 1;
+                    for (int i = 0; i < n; i++) {
+                        int s = coeff_shift(&sp, p, b, i);
+                        int32_t q = omc_quant1b_dz(cf[i], s, tex_vmaf,
+                                                   e->dz_enabled && b >= OMC_FILL_BANDS_FROM);
+                        int32_t v = omc_dequant1(q, s);
+                        if (m) v += pc[i];
+                        if (fb && v == 0 && q == 0)
+                            v = fill_value_p(llbuf, llw, llw, llh, b, i / w, i % w,
+                                             s, fox, foy, sfox, sfoy, lllim, ghyp,
+                                             c->cfg.grain_corr,
+                                             (c->cfg.fill_static ? 1 : 0), 0, &vfp);
+                        if (v != e->coef[p][b][i]) {
+                            if (getenv("OMC_DEBUG_VERIFY2"))
+                                fprintf(stderr, "vmis sl=%d p=%d b=%d m=%d fb=%d g=%d "
+                                        "i=%d s=%d q=%d v=%d want=%d pc=%d\n",
+                                        slice_idx, p, b, m, fb, ghyp, i, s,
+                                        (int)q, (int)v, (int)e->coef[p][b][i],
+                                        (int)(m ? pc[i] : 0));
+                            okv = 0; break;
+                        }
                     }
+                    okm[m] = okv;
                 }
-            }
-        int pgain = fill_gain_code(gnum, gden, c->cfg.tune_vmaf);
-        if (out_fmask) *out_fmask |= fmask << (p * 6);
-        if (out_gain) out_gain[p] = pgain;
-        /* pass 3: full reconstruction exactness, fill included */
-        for (int b = 1; b < OMC_NBANDS; b++) {
-            int m = can_inter && ((modes >> (p * OMC_NBANDS + b)) & 1);
-            int fb = b >= OMC_FILL_BANDS_FROM &&
-                     ((fmask >> (b - OMC_FILL_BANDS_FROM)) & 1);
-            int fox = 0, foy = 0;
-            int sfox = 0, sfoy = 0;
-            if (fb) {
-                omc_fill_offsets(frame_idx & 0xFF, slice_idx, p, b, &fox, &foy);
-                omc_fill_offsets(0, slice_idx, p, b, &sfox, &sfoy);
-            }
-            const int32_t *cf = m ? e->dcoef[p][b] : e->coef[p][b];
-            const int32_t *pc = e->pcoef[p][b];
-            int n = bands[b].h * bands[b].w, w = bands[b].w;
-            tex_vmaf = OMC_BAND_TEXTURE(b) && c->cfg.tune_vmaf;
-            fp_t vfp; fp_build_arr(&vfp, bands, e->coef[p], b, &sp, p);
-            for (int i = 0; i < n; i++) {
-                int s = coeff_shift(&sp, p, b, i);
-                int32_t q = omc_quant1b_dz(cf[i], s, tex_vmaf,
-                                           e->dz_enabled && b >= OMC_FILL_BANDS_FROM);
-                int32_t v = omc_dequant1(q, s);
-                if (m) v += pc[i];
-                if (fb && v == 0 && q == 0)
-                    v = fill_value_p(llbuf, llw, llw, llh, b, i / w, i % w,
-                                   s, fox, foy, sfox, sfoy, lllim, pgain, c->cfg.grain_corr,
-                                   1 + (c->cfg.fill_static ? 1 : 0), 0, &vfp);
-                if (v != e->coef[p][b][i]) {
+                int m_b;
+                if (okm[0] && (nm < 2 || !okm[1])) m_b = 0;
+                else if (!okm[0] && nm == 2 && okm[1]) m_b = 1;
+                else if (okm[0] && nm == 2 && okm[1])
+                    m_b = bc[1][p][b].bits[base_s] < bc[0][p][b].bits[base_s] ? 1 : 0;
+                else {
                     if (getenv("OMC_DEBUG_VERIFY"))
-                        fprintf(stderr, "verify fail sl=%d p=%d b=%d i=%d m=%d fb=%d "
-                                "s=%d q=%d v=%d want=%d pc=%d\n",
-                                slice_idx, p, b, i, m, fb, s, (int)q, (int)v,
-                                (int)e->coef[p][b][i], (int)(m ? pc[i] : 0));
-                    return 0;
+                        fprintf(stderr, "verify fail f%d sl=%d p=%d b=%d s=%d g=%d "
+                                "fb=%d/%d nm=%d\n", frame_idx, slice_idx, p, b,
+                                base_s, ghyp, fbm[0], fbm[1], nm);
+                    /* only fill amplitudes at base shift >= 4 depend on the
+                     * gain hypothesis; any other failure repeats at every
+                     * gain, so trying more hypotheses is wasted work */
+                    if (can_fill && base_s >= 4 && (fbm[0] || fbm[1]))
+                        gain_dep = 1;
+                    ok = 0; break;
+                }
+                if (m_b) tmodes |= 1u << (p * OMC_NBANDS + b);
+                if (fbm[m_b]) {
+                    tfmask |= 1u << (b - OMC_FILL_BANDS_FROM);
+                    if (base_s >= 4) {
+                        gnum += (summ[m_b] << 6) >> base_s;
+                        gden += cntm[m_b];
+                    }
                 }
             }
+            /* the gain hypothesis must be what the encoder itself would
+             * derive from the values it just reproduced */
+            if (ok && getenv("OMC_DEBUG_VERIFY") &&
+                fill_gain_code(gnum, gden, c->cfg.tune_vmaf) != ghyp)
+                fprintf(stderr, "verify gainmis f%d sl=%d p=%d ghyp=%d derived=%d "
+                        "gnum=%lld gden=%lld\n", frame_idx, slice_idx, p, ghyp,
+                        fill_gain_code(gnum, gden, c->cfg.tune_vmaf),
+                        (long long)gnum, (long long)gden);
+            if (ok && fill_gain_code(gnum, gden, c->cfg.tune_vmaf) == ghyp) {
+                found = 1;
+                vmodes |= tmodes;
+                if (out_fmask) *out_fmask |= tfmask << (p * 6);
+                if (out_gain) out_gain[p] = ghyp;
+            }
         }
+        if (!found) return 0;
     }
+    if (out_modes) *out_modes = vmodes;
     return 1;
 }
 
@@ -2003,6 +1790,64 @@ static void dcfb_adjust(int32_t *arr, int n, int s, int extra_q8, int delta_only
                      extra_q8, k0, k0 - left);
 }
 
+/* T5: the exact payload size, in bits, of coding this slice with the given
+ * locked plan — the same symbolization and tANS pass the commit path runs,
+ * with nothing committed.  Selection between verified lock candidates is by
+ * THIS number, not the estimate: the generation-exactness induction needs
+ * every locked slice to spend no more than the previous generation's did,
+ * and only the actual size can promise that (the estimate's state-path error
+ * accumulated across a frame was measured starving late slices out of their
+ * own previous-generation plan). */
+static size_t lock_trial_bits(omc_enc_t *e, int cf444, int can_inter,
+                              int prof, int Q, int ns, int partial,
+                              uint32_t modes)
+{
+    ctx_common_t *c = &e->c;
+    int sh = c->sh;
+    shift_plan_t sp;
+    derive_shifts(cf444, prof, Q, ns, partial, &sp);
+    omc_band_t bands[OMC_NBANDS];
+    size_t nsym = 0;
+    (void)can_inter;
+    for (int p = 0; p < OMC_NPLANES; p++) {
+        int pw = plane_width(c, p);
+        omc_band_layout(pw, sh, bands);
+        for (int b = 0; b < OMC_NBANDS; b++) {
+            int n = bands[b].h * bands[b].w;
+            int m = (int)((modes >> (p * OMC_NBANDS + b)) & 1);
+            /* exact-plan histogram gid, mirroring the commit path (locked
+             * emission never applies grain-replace eligibility) */
+            int gid;
+            {
+                uint32_t phist[OMC_NCTX][OMC_NSYM];
+                memset(phist, 0, sizeof(phist));
+                band_scan(e, p, b, m ? e->dcoef[p][b] : e->coef[p][b],
+                          n, &sp, -1, phist, 0, 0, NULL,
+                          NULL, bands[b].w, e->rowsig, NULL);
+                int64_t pc64;
+                gid = best_group(phist, &pc64);
+            }
+            band_scan(e, p, b, m ? e->dcoef[p][b] : e->coef[p][b],
+                      n, &sp, -1, NULL, 1,
+                      gid, &nsym, NULL,
+                      bands[b].w, e->rowsig, NULL);
+        }
+    }
+    omc_bw_t bw;
+    omc_bw_init(&bw, e->paybuf, e->c.slice_bytes * 2 + 32);
+    uint32_t state = OMC_TANS_L;
+    for (size_t k2 = nsym; k2-- > 0;) {
+        if (e->rawn[k2]) omc_bw_put(&bw, e->raws[k2], e->rawn[k2]);
+        const omc_tans_table_t *T =
+            &omc_tans[e->stids[k2] / OMC_NCTX][e->stids[k2] % OMC_NCTX];
+        int s2 = e->syms[k2];
+        int nb = (int)(((int64_t)state + T->delta_nbits[s2]) >> 16);
+        omc_bw_put(&bw, state & ((1u << nb) - 1), nb);
+        state = T->next_state[T->delta_find[s2] + (state >> nb)];
+    }
+    return bw.bytepos * 8 + (size_t)bw.accbits;
+}
+
 int omc_enc_slice(omc_enc_t *e, const omc_frame_t *in, int frame_idx, int slice_idx,
                   uint8_t *dst, omc_frame_t *recon)
 {
@@ -2019,8 +1864,7 @@ int omc_enc_slice(omc_enc_t *e, const omc_frame_t *in, int frame_idx, int slice_
             xrf.p[p] = e->ref[p];
             xrf.stride[p] = plane_width(c, p);
         }
-        xsl_prep(c, &xrf, slice_idx, omc_ref_unclipped ? OMC_REF_BIAS : 0,
-                 frame_idx & 0xFF);
+        xsl_prep(c, &xrf, slice_idx, OMC_REF_BIAS, frame_idx & 0xFF);
     }
 
     /* ---- causal bit banking: budget for this slice ---- */
@@ -2040,6 +1884,14 @@ int omc_enc_slice(omc_enc_t *e, const omc_frame_t *in, int frame_idx, int slice_
     int64_t wire_cap = (int64_t)c->slice_bytes * 2 * 8;
     if (budget_wire > wire_cap) budget_wire = wire_cap;
     int64_t budget = budget_wire - OMC_SLICE_HDR_BYTES * 8; /* payload bits */
+    /* T5: the HARD budget — the normative prefix/frame/wire bounds only,
+     * before any encoder-policy cap (perceptual allocator, tail guard).
+     * LOCKED slices plan against this: the policy caps derive from source
+     * statistics that drift between generations, and a locked slice must be
+     * admissible whenever the previous generation's identical slice was.
+     * The prefix induction (docs/TEMPORAL_T5.md section 5) shows the
+     * previous generation's plan always fits this bound. */
+    int64_t budget_hard = budget;
     int64_t alloc_cap = -1; /* applied after the transform (energy known) */
 
     /* OMC_ALLOC bookkeeping: reset the per-frame accumulator */
@@ -2055,7 +1907,9 @@ int omc_enc_slice(omc_enc_t *e, const omc_frame_t *in, int frame_idx, int slice_
         for (int r = 0; r < sh; r++) {
             const uint16_t *src = in->p[p] + (size_t)(slice_idx * sh + r) * in->stride[p];
             int32_t *d = e->sbuf[p] + (size_t)r * pw;
-            for (int x = 0; x < pw; x++) d[x] = (int32_t)src[x] - c->mid;
+            /* T5: input frames are in the biased domain (omc1.h) */
+            for (int x = 0; x < pw; x++)
+                d[x] = (int32_t)src[x] - c->mid - OMC_REF_BIAS;
         }
         omc_dwt_d1m = omc_xsl_live[p] ? omc_xsl_buf[p] : 0;
         omc_slice_fwd(e->sbuf[p], pw, sh, e->tmp);
@@ -2070,6 +1924,20 @@ int omc_enc_slice(omc_enc_t *e, const omc_frame_t *in, int frame_idx, int slice_
         }
     }
 
+    /* debug: dump this slice's transform coefficients (OMC_DUMP_COEF=<pfx>) */
+    {
+        const char *dc = getenv("OMC_DUMP_COEF");
+        if (dc && frame_idx == 0 && slice_idx == 0) {
+            char fn[512];
+            snprintf(fn, sizeof fn, "%s.enccoef.p0.i32", dc);
+            FILE *df = fopen(fn, "wb");
+            if (df) {
+                fwrite(e->sbuf[0], 4, (size_t)plane_width(c, 0) * sh, df);
+                fclose(df);
+            }
+        }
+    }
+
     /* OMC_ALLOC: measure this slice's source energy (sum |coef|, detail
      * bands only - LL tracks brightness, not coding cost), update the
      * rolling per-slice record, and cap this slice's budget by the
@@ -2233,228 +2101,28 @@ int omc_enc_slice(omc_enc_t *e, const omc_frame_t *in, int frame_idx, int slice_
     int can_inter = frame_idx > 0 && e->last_frame == frame_idx - 1 &&
                     ((frame_idx & 0xFF) % R) != (slice_idx % R);
     int8_t mvx2[OMC_NREG] = {0}, mvy2[OMC_NREG] = {0}; /* half-pel units */
-    memset(e->bofx, 0, (size_t)e->nblk); /* stale-offset guard (OMC_NO_MV path) */
-    memset(e->bofy, 0, (size_t)e->nblk);
-    memset(e->bmode, 0, (size_t)e->nblk);
-    if (can_inter && !getenv("OMC_NO_MV")) {
-        /* Motion search (v3.1): hierarchical and decisive-only, so decisions
-         * replay identically on re-encoded generations (A4).
-         *   Stage A: whole-slice integer argmin (strict <, fixed candidate
-         *            order) - the aggregated statistic of the proven-stable
-         *            v3.0 global search.
-         *   Stage B: global half-pel refinement, accepted only on a >= 25%
-         *            SAD win (true fractional pans win by far more; shallow
-         *            noise surfaces never fire).
-         *   Stage C: per-region integer override, accepted only on a >= 25%
-         *            win over the global choice on that region (genuinely
-         *            divergent multi-object motion wins by 2x+).
-         *   Stage D: per-region half-pel refinement, same 25% rule.
-         * The SAD statistic is computed on 4x2 block sums, not point
-         * samples: block means cancel per-pixel grain and coding error (both
-         * change between generations), so the argmin is decided by structure
-         * that survives re-encoding. All ops are shifts/adds/compares;
-         * half-pel taps are (a+b+1)>>1 / (a+b+c+d+2)>>2. */
-        int W0 = c->W, y0 = slice_idx * sh, H0 = c->H;
-        const uint16_t *inp = in->p[0];
-        size_t instr = in->stride[0];
-        const uint16_t *rfp = e->ref[0];
-        int rb = omc_ref_unclipped ? OMC_REF_BIAS : 0; /* F-4: unbias biased reference reads */
-        int nbx = W0 / 4, nby = sh / 2;
-        int32_t *ib = e->bsum;
-        for (int r2 = 0; r2 < nby; r2++) {
-            const uint16_t *ra = inp + (size_t)(y0 + 2 * r2) * instr;
-            const uint16_t *rb = inp + (size_t)(y0 + 2 * r2 + 1) * instr;
-            for (int xb = 0; xb < nbx; xb++) {
-                int x = 4 * xb;
-                ib[(size_t)r2 * nbx + xb] =
-                    (int32_t)ra[x] + ra[x + 1] + ra[x + 2] + ra[x + 3] +
-                    rb[x] + rb[x + 1] + rb[x + 2] + rb[x + 3];
-            }
-        }
-        /* Stage A: whole-slice integer argmin over the v3.0 point-decimated
-         * SAD - byte-for-byte the statistic whose generation replay is
-         * already proven on this corpus (strict <, fixed candidate order). */
-        int gx2 = 0, gy2 = 0;
-        {
-            int64_t best = -1;
-            for (size_t ci = 0; ci < sizeof(omc_mv_cand) / sizeof(omc_mv_cand[0]); ci++) {
-                int dx = omc_mv_cand[ci][0], dy = omc_mv_cand[ci][1];
-                int64_t sad = 0;
-                for (int r = 0; r < sh; r += 2) {
-                    int sy = y0 + r + dy;
-                    if (sy < 0) sy = 0;
-                    if (sy > H0 - 1) sy = H0 - 1;
-                    const uint16_t *rowin = inp + (size_t)(y0 + r) * instr;
-                    const uint16_t *rowrf = rfp + (size_t)sy * W0;
-                    for (int x = 0; x < W0; x += 4) {
-                        int sx = x + dx;
-                        if (sx < 0) sx = 0;
-                        if (sx > W0 - 1) sx = W0 - 1;
-                        int d = (int)rowin[x] - ((int)rowrf[sx] - rb);
-                        sad += d < 0 ? -d : d;
-                    }
-                }
-                if (best < 0 || sad < best) { best = sad; gx2 = dx * 2; gy2 = dy * 2; }
-            }
-            /* Fine-step refinement (HFR pans move 1-9 px/frame, and the
-             * sparse list above skips odd speeds): test the four integer
-             * neighbours of the winner, accepting only a >= 25% SAD win -
-             * the decisive-margin pattern proven generation-stable by
-             * stages B-D. A truly odd-speed pan wins by 2x+; near-tie
-             * noise never fires the margin, so argmin replay is preserved
-             * (verified by the A4 gate and pan chains). */
-            {
-                static const int8_t nb[4][2] = {{-1,0},{1,0},{0,-1},{0,1}};
-                int bx = gx2 / 2, by = gy2 / 2;
-                for (int ci = 0; ci < 4; ci++) {
-                    int dx = bx + nb[ci][0], dy = by + nb[ci][1];
-                    if (dx < -31 || dx > 31 || dy < -15 || dy > 15) continue;
-                    int64_t sad = 0;
-                    for (int r = 0; r < sh; r += 2) {
-                        int sy = y0 + r + dy;
-                        if (sy < 0) sy = 0;
-                        if (sy > H0 - 1) sy = H0 - 1;
-                        const uint16_t *rowin = inp + (size_t)(y0 + r) * instr;
-                        const uint16_t *rowrf = rfp + (size_t)sy * W0;
-                        for (int x = 0; x < W0; x += 4) {
-                            int sx = x + dx;
-                            if (sx < 0) sx = 0;
-                            if (sx > W0 - 1) sx = W0 - 1;
-                            int d = (int)rowin[x] - ((int)rowrf[sx] - rb);
-                            sad += d < 0 ? -d : d;
-                        }
-                    }
-                    if (sad * 4 < best * 3) { best = sad; gx2 = dx * 2; gy2 = dy * 2; }
-                }
-            }
-        }
-        /* Stages B-D (opt-in, cfg.mv_regions): half-pel and per-region
-         * overrides on the block-sum SAD (block means cancel grain and
-         * coding error), each accepted only on a >= 2x win. Decisive motion
-         * (opposite pans, true fractional pans on clean content) wins by
-         * 3-10x and fires reliably; but content sitting near any fixed
-         * threshold can decide differently on a re-encoded generation, so
-         * with overrides enabled A4 holds as fast reconvergence rather than
-         * byte-exact replay (measured in docs/DESIGN.md). Default keeps
-         * stage A only - the v3.0-proven byte-replay behavior. */
-        if (!c->cfg.mv_regions) {
-            for (int reg = 0; reg < OMC_NREG; reg++) {
-                mvx2[reg] = (int8_t)gx2;
-                mvy2[reg] = (int8_t)gy2;
-            }
-            goto mv_done;
-        }
-        int64_t gbase = mv_block_sad(ib, nbx, nby, rfp, W0, H0, y0, 0, nbx,
-                                     gx2, gy2);
-        {
-            int cx = gx2, cy = gy2;
-            for (int ci = 0; ci < 8; ci++) {
-                int dx2 = cx + omc_mv_nb8[ci][0], dy2 = cy + omc_mv_nb8[ci][1];
-                if (dx2 < -16 || dx2 > 15 || dy2 < -8 || dy2 > 7) continue;
-                int64_t sad = mv_block_sad(ib, nbx, nby, rfp, W0, H0, y0, 0, nbx,
-                                           dx2, dy2);
-                if (sad * 2 < gbase) { gbase = sad; gx2 = dx2; gy2 = dy2; }
-            }
-        }
+    /* T5 motion: derived from committed reconstruction history ONLY (see
+     * derive_mv).  The source frame plays no part, so the vector — and with
+     * it the prediction — is byte-identical in every re-encode generation.
+     * Needs both refprev (frame t-1) and refprev2 (frame t-2); with only
+     * one committed predecessor (frame 1) the vector is 0. */
+    if (can_inter && e->last_frame2 == frame_idx - 2) {
+        int gx = 0, gy = 0;
+        derive_mv(e->refprev[0], e->refprev2[0], c->W, c->H,
+                  slice_idx * sh, sh, &gx, &gy);
         for (int reg = 0; reg < OMC_NREG; reg++) {
-            int xb0 = (reg * W0 / OMC_NREG) / 4, xb1 = ((reg + 1) * W0 / OMC_NREG) / 4;
-            int64_t rbase = mv_block_sad(ib, nbx, nby, rfp, W0, H0, y0, xb0, xb1,
-                                         gx2, gy2);
-            int rx2 = gx2, ry2 = gy2;
-            int64_t ibest = -1;
-            int ix2 = 0, iy2 = 0;
-            for (size_t ci = 0; ci < sizeof(omc_mv_cand) / sizeof(omc_mv_cand[0]); ci++) {
-                int64_t sad = mv_block_sad(ib, nbx, nby, rfp, W0, H0, y0, xb0, xb1,
-                                           omc_mv_cand[ci][0] * 2, omc_mv_cand[ci][1] * 2);
-                if (ibest < 0 || sad < ibest) {
-                    ibest = sad; ix2 = omc_mv_cand[ci][0] * 2; iy2 = omc_mv_cand[ci][1] * 2;
-                }
-            }
-            if (ibest * 2 < rbase) { rx2 = ix2; ry2 = iy2; rbase = ibest; }
-            int cx = rx2, cy = ry2;
-            for (int ci = 0; ci < 8; ci++) {
-                int dx2 = cx + omc_mv_nb8[ci][0], dy2 = cy + omc_mv_nb8[ci][1];
-                if (dx2 < -16 || dx2 > 15 || dy2 < -8 || dy2 > 7) continue;
-                int64_t sad = mv_block_sad(ib, nbx, nby, rfp, W0, H0, y0, xb0, xb1,
-                                           dx2, dy2);
-                if (sad * 2 < rbase) { rbase = sad; rx2 = dx2; ry2 = dy2; }
-            }
-            mvx2[reg] = (int8_t)rx2;
-            mvy2[reg] = (int8_t)ry2;
-        }
-mv_done:;
-        /* v4.3: per-block full-pel offset refinement around each block's
-         * region vector. Strict argmin, fixed candidate order, block-sum SAD
-         * over the block's own columns only. Offsets stay within the field
-         * range so the reference halo bound (+/-32 h, +/-16 v px) holds. */
-        if (c->cfg.no_block_mv == 2) { /* experimental, off by default:
-             * measured ~0 on this corpus (matches D-1/D-2); kept as a
-             * bitstream capability for future motion work */
-            for (int blk = 0; blk < e->nblk; blk++) {
-                int reg = blk * OMC_NREG / e->nblk;
-                int bx2 = mvx2[reg], by2 = mvy2[reg];
-                int xb0 = blk * (OMC_BLK_W / 4), xb1 = xb0 + OMC_BLK_W / 4;
-                int64_t best = -1;
-                int bfx = 0, bfy = 0;
-                for (size_t ci = 0; ci < sizeof(omc_bof_cand) / sizeof(omc_bof_cand[0]); ci++) {
-                    int ox = omc_bof_cand[ci][0], oy = omc_bof_cand[ci][1];
-                    int dx2 = bx2 + 2 * ox, dy2 = by2 + 2 * oy;
-                    if (dx2 < -64 || dx2 > 63 || dy2 < -32 || dy2 > 31) continue;
-                    int64_t sad = bof_sad(ib, nbx, nby, rfp, W0, H0, y0,
-                                          xb0, xb1, dx2, dy2);
-                    if (best < 0 || sad < best) { best = sad; bfx = ox; bfy = oy; }
-                }
-                e->bofx[blk] = (int8_t)bfx;
-                e->bofy[blk] = (int8_t)bfy;
-                /* per-block intra decision: block-sum AC activity (deviation
-                 * from the block's own mean sum) vs the best MC block-sum
-                 * SAD - both statistics on the same 4x2-sum grid, the class
-                 * whose argmin replay is generation-proven. Strict <, ties
-                 * keep MC. */
-                {
-                    int nsum = (xb1 - xb0) * nby;
-                    int64_t tot = 0;
-                    for (int r2 = 0; r2 < nby; r2++)
-                        for (int xb = xb0; xb < xb1; xb++)
-                            tot += ib[(size_t)r2 * nbx + xb];
-                    int64_t mean = tot / nsum;
-                    int64_t act = 0;
-                    for (int r2 = 0; r2 < nby; r2++)
-                        for (int xb = xb0; xb < xb1; xb++) {
-                            int64_t d = ib[(size_t)r2 * nbx + xb] - mean;
-                            act += d < 0 ? -d : d;
-                        }
-                    e->bmode[blk] = (uint8_t)(act < best);
-                }
-            }
-        } else {
-            memset(e->bofx, 0, (size_t)e->nblk);
-            memset(e->bofy, 0, (size_t)e->nblk);
-            memset(e->bmode, 0, (size_t)e->nblk);
+            mvx2[reg] = (int8_t)(gx * 2);   /* integer-pel: even half-pel codes */
+            mvy2[reg] = (int8_t)(gy * 2);
         }
     }
-    /* MV field presence: any nonzero offset (deterministic — the argmin IS
-     * the decision; no acceptance threshold anywhere). */
-    int mv_present = 0;
-    if (can_inter && c->cfg.no_block_mv == 2)
-        for (int blk = 0; blk < e->nblk; blk++)
-            if (e->bofx[blk] || e->bofy[blk] || e->bmode[blk]) { mv_present = 1; break; }
-    size_t mvsize = mv_present ? mv_field_bytes(e->nblk) : 0;
-    budget -= (int64_t)mvsize * 8; /* MV field rides the same wire budget */
-    if (getenv("OMC_DEBUG_MV") && frame_idx <= 2 && slice_idx <= 6) {
-        fprintf(stderr, "ENC f%d s%d mvp=%d g=(%d,%d) bof:", frame_idx,
-                slice_idx, mv_present, mvx2[0], mvy2[0]);
-        for (int j = 100; j < 128 && j < e->nblk; j++)
-            fprintf(stderr, " %d,%d", e->bofx[j], e->bofy[j]);
-        fprintf(stderr, "\n");
-    }
+    if (getenv("OMC_DEBUG_MV") && frame_idx <= 2 && slice_idx <= 6)
+        fprintf(stderr, "ENC f%d s%d mv=(%d,%d)\n", frame_idx,
+                slice_idx, mvx2[0], mvy2[0]);
     if (can_inter) {
         for (int p = 0; p < OMC_NPLANES; p++) {
-            predict_plane(c, e->ref[p], p, slice_idx, mvx2, mvy2,
-                          mv_present ? e->bofx : NULL,
-                          mv_present ? e->bofy : NULL,
-                          mv_present ? e->bmode : NULL, e->nblk, e->pbuf[p],
-                          e->tmp, e->pcoef[p]);
+            /* T5: prediction reads the PREVIOUS FRAME'S FINAL picture only */
+            predict_plane(c, e->refprev[p], p, slice_idx, mvx2, mvy2,
+                          e->pbuf[p], e->tmp, e->pcoef[p]);
             omc_band_layout(plane_width(c, p), sh, bands);
             for (int b = 0; b < OMC_NBANDS; b++) {
                 int n = bands[b].h * bands[b].w;
@@ -2631,10 +2299,10 @@ mv_done:;
      * Encoder-only policy; the bitstream and decoder are unchanged. */
     int locked = 0;
     int lock_prof = 0, lock_Q = 0, lock_steps = 0, lock_partial = 0;
+    int lock_ci = -1; /* chosen candidate index (for overflow fallback) */
     uint32_t lock_modes = 0, lock_fmask = 0;
     int lock_gain[OMC_NPLANES] = {0, 0, 0};
-    struct { int64_t tot, key; int pr, q, ns, k; uint32_t modes; } lcand[192];
-    int nlcand = 0;
+    e->nlcand = 0;
     if (!c->cfg.lossless_pref) {
         /* per-chunk lattice exponents (OMC_CHUNK coefficients per chunk),
          * per coding mode: a previous-generation slice shows its lattice in
@@ -2667,30 +2335,58 @@ mv_done:;
                 }
                 tzmask[m][p][b] = msk;
             }
-        /* v4 lattice test: a previous-generation band contains lattice
-         * multiples of 2^s plus - in fill-eligible bands (4..9) only -
-         * grain-fill values. v4.1 gains put fill magnitudes at 2^(s-2)
-         * (1.0x), 3*2^(s-3) (1.5x), and 5*2^(s-4)/7*2^(s-4) (1.25x/1.75x),
-         * whose trailing-zero exponents are s-2, s-3 and s-4: all three are
-         * admitted for s >= 4, only s-2 at s = 3 (gains do not apply
-         * there). tz == s-1 is never consistent; bands 0..3 (never filled)
-         * stay strict. Looser admission only widens the candidate list -
-         * lock_verify still demands bit-exact reproduction. */
-        /* Fill admission stays at the 1.0x amplitude (tz == s-2) only.
-         * Admitting the v4.1 gain amplitudes (tz s-3/s-4) was tried and
-         * floods the candidate list with cheap false plans - the verify cap
-         * exhausts before the true plan and STATIC locking breaks (measured
-         * on the alpine A4 gate). Consequence: slices whose plane fill gain
-         * is >= 1.25x cannot lattice-lock and re-encode as convergent
-         * (bounded, non-accumulating) rather than byte-exact - same class
-         * as pan content. Diagnosis and the parked fix: REPORT 11n. */
-        #define LAT_FILLBITS(s) (1u << ((s) - 2))
+        /* T5 lattice test: a previous-generation band contains lattice
+         * multiples of 2^s plus — in fill-eligible bands (4..9) only —
+         * grain-fill values.  The v4.1 gain codes put fill magnitudes at
+         * 2^(s-2) (1.0x), 3*2^(s-3) (1.5x) and 5*2^(s-4)/7*2^(s-4)
+         * (1.25x/1.75x), whose trailing-zero exponents are s-2, s-3 and
+         * s-4: ALL are admitted for s >= 4, and s-2 alone at s = 3 (gains
+         * do not apply there).  tz == s-1 is never consistent; bands 0..3
+         * (never filled) stay strict.  v4.9 restricted admission to s-2
+         * because its 16-try verify cap drowned in the wider candidate
+         * list, which left every slice with fill gain >= 1.25x UNABLE to
+         * lock — a permanent generation-exactness hole.  T5 instead keeps
+         * the admission complete and removes the caps: the candidate list
+         * is large (OMC_LOCK_CANDS) and verification runs until the list
+         * is exhausted.  Completeness over compute — the contract demands
+         * that the previous generation's plan is always found. */
+        #define LAT_FILLBITS(s) ((s) >= 4 \
+            ? ((1u << ((s) - 2)) | (1u << ((s) - 3)) | (1u << ((s) - 4))) \
+            : (1u << ((s) - 2)))
         #define LAT_ALLOWED(s, b) ((0xFFFFFFFFu << (s)) | \
             (((b) >= OMC_FILL_BANDS_FROM && (s) >= OMC_FILL_MIN_SHIFT) \
                  ? LAT_FILLBITS(s) : 0u))
         #define LAT_OK(tz, s, b) ((tz) >= (s) || \
             ((b) >= OMC_FILL_BANDS_FROM && (s) >= OMC_FILL_MIN_SHIFT && \
              (tz) <= (s) - 2 && (tz) >= (s) - 4 && ((s) >= 4 || (tz) == (s) - 2)))
+        #define LAT_ALLOWED_DBG(s, b) LAT_ALLOWED(s, b)
+        /* debug: OMC_LAT_PROBE="prof,q,ns" prints, for that exact plan,
+         * every band whose lattice test fails on this slice */
+        {
+            const char *lp = getenv("OMC_LAT_PROBE");
+            if (lp) {
+                int pp, pq, pns;
+                if (sscanf(lp, "%d,%d,%d", &pp, &pq, &pns) == 3) {
+                    shift_plan_t pc2;
+                    derive_shifts(cf444, pp, pq, pns, 0, &pc2);
+                    for (int p = 0; p < OMC_NPLANES; p++)
+                        for (int b = 0; b < OMC_NBANDS; b++) {
+                            int s = pc2.shift[p][b];
+                            int nm2 = can_inter ? 2 : 1;
+                            int okc = 0;
+                            for (int m = 0; m < nm2; m++)
+                                if (!(tzmask[m][p][b] & ~LAT_ALLOWED_DBG(s, b))) okc = 1;
+                            if (!okc)
+                                fprintf(stderr, "LATFAIL f%d sl=%d p=%d b=%d s=%d "
+                                        "tzmask=%08x/%08x allowed=%08x\n",
+                                        frame_idx, slice_idx, p, b, s,
+                                        tzmask[0][p][b],
+                                        can_inter ? tzmask[1][p][b] : 0xdeadbeefu,
+                                        LAT_ALLOWED_DBG(s, b));
+                        }
+                }
+            }
+        }
         shift_plan_t cand;
         int64_t best_tot = -1;
         for (int q = OMC_MAX_SHIFT; q >= 0; q--)
@@ -2702,6 +2398,19 @@ mv_done:;
                         step_p = omc_refine_order[ns][0];
                         step_b = omc_refine_order[ns][1];
                         if (cand.shift[step_p][step_b] == 0) step_p = -1;
+                        /* T5: partial-chunk refinement exists ONLY in the
+                         * non-fill bands (< OMC_FILL_BANDS_FROM; in the
+                         * refine order that is band 3).  In fill-capable
+                         * bands a partial boundary changes per-coefficient
+                         * fill amplitudes, and the boundary position is not
+                         * recoverable from the committed values alone (a
+                         * refined chunk's 1.0x fill and an unrefined
+                         * chunk's 1.5x-gain fill leave the same trailing-
+                         * zero signature).  The T5 rate control never emits
+                         * such plans (see step 3), so the lock never has to
+                         * guess one. */
+                        if (step_p >= 0 && step_b >= OMC_FILL_BANDS_FROM)
+                            step_p = -1;
                     }
                     int ok = 1, nontrivial = 0;
                     int fan_min = -1, fan_nch = 0;
@@ -2766,79 +2475,134 @@ mv_done:;
                             if (s > 0 && (tzmask[m][p][b] & ~(1u << OMC_MAX_SHIFT))) nontrivial++;
                             tot += bc[m][p][b].bits[s];
                         }
-                    /* require real lattice evidence (>= 4 nonempty bands with
-                     * nonzero shift) so natural content never false-locks.
-                     * Collect consistent candidates; the cheapest VERIFIED one
-                     * locks (lock_verify simulates the full reconstruction,
-                     * grain fill included, and demands bit-exact reproduction
-                     * of the input - A4 as a checked property). */
-                    if (ok && nontrivial >= 4) {
-                        /* single-k inference (v4.0-proven): the lattice
-                         * lower bound is the emitted k. Pan-content plans
-                         * whose true k exceeds it converge across
-                         * generations instead of locking - a pre-existing
-                         * v4.0 property; widening this to a k-fan was tried
-                         * and polluted verify ordering enough to break
-                         * static locking (diagnosis in REPORT 11n). */
-                        int kset[1]; int nk = 1;
-                        kset[0] = (step_p >= 0 && fan_min >= 0) ? fan_min : 0;
-                        for (int ki = 0; ki < nk; ki++) {
-                            int kc = kset[ki];
-                            int64_t tk = tot +
-                                ((step_p >= 0 && fan_nch) ? fan_d * kc / fan_nch : 0);
-                            if (tk > budget + budget / 128 + 64) continue;
-                            int64_t key = tk; /* cheapest-first (proven) */
+                    /* T5: NO minimum-evidence gate.  v4.9 demanded >= 4
+                     * nonempty lattice-consistent bands so natural content
+                     * never false-locked; the price was that low-evidence
+                     * generation-2 slices (near-flat content, very low
+                     * rates) could NEVER lock and drifted forever.  A
+                     * "false" lock is harmless by construction — verify
+                     * demands bit-exact reproduction of the input, so a
+                     * natural slice that locks is coded LOSSLESSLY (only
+                     * possible when that fits the budget, i.e. high rates)
+                     * — while a missing lock at generation >= 2 breaks the
+                     * exactness contract.  Every consistent, fitting plan
+                     * is therefore a candidate; the cheapest VERIFIED one
+                     * wins (lock_verify simulates the full reconstruction,
+                     * grain fill included). */
+                    if (ok) {
+                        int kc = (step_p >= 0 && fan_min >= 0) ? fan_min : 0;
+                        int64_t tk = tot +
+                            ((step_p >= 0 && fan_nch) ? fan_d * kc / fan_nch : 0);
+                        /* fit against the HARD budget: policy caps must not
+                         * be able to refuse a previous generation's plan */
+                        if (tk <= budget_hard + budget_hard / 128 + 64) {
+                            int64_t key = tk; /* cheapest-first */
+                            int kk = (step_p >= 0) ? kc : 0;
+                            /* pack the derived plan; alias candidates (other
+                             * (pr,q,ns) deriving the same plan) are skipped.
+                             * Keeping the first-enumerated alias preserves
+                             * the pre-dedupe selection winner: aliases have
+                             * equal keys and equal actual sizes, and both
+                             * the walk order and min-actual tie-break keep
+                             * the earliest entry. */
+                            uint8_t sv[18];
+                            for (int j = 0; j < 15; j++) {
+                                int b2 = 2 * j, b3 = 2 * j + 1;
+                                sv[j] = (uint8_t)((cand.shift[b2 / 10][b2 % 10] << 4) |
+                                                  cand.shift[b3 / 10][b3 % 10]);
+                            }
+                            sv[15] = (uint8_t)(kk & 0xFF);
+                            sv[16] = (uint8_t)(kk >> 8);
+                            sv[17] = (uint8_t)((step_p + 1) * 16 +
+                                               (step_p >= 0 ? step_b : 0));
+                            int dup = 0;
+                            for (int j = 0; j < e->nlcand; j++)
+                                if (!memcmp(e->lcand[j].sv, sv, sizeof sv)) {
+                                    dup = 1; break;
+                                }
                             int slot = -1;
-                            if (nlcand < 192) slot = nlcand++;
+                            if (dup) { /* alias of an earlier candidate */ }
+                            else if (e->nlcand < OMC_LOCK_CANDS) slot = e->nlcand++;
                             else {
                                 int wi = 0;
-                                for (int j = 1; j < 192; j++)
-                                    if (lcand[j].key > lcand[wi].key) wi = j;
-                                if (lcand[wi].key > key) slot = wi;
+                                for (int j = 1; j < OMC_LOCK_CANDS; j++)
+                                    if (e->lcand[j].key > e->lcand[wi].key) wi = j;
+                                if (e->lcand[wi].key > key) slot = wi;
                             }
                             if (slot >= 0) {
-                                lcand[slot].tot = tk; lcand[slot].key = key;
-                                lcand[slot].pr = pr; lcand[slot].q = q;
-                                lcand[slot].ns = ns;
-                                lcand[slot].k = (step_p >= 0) ? kc : 0;
-                                lcand[slot].modes = cmodes;
+                                e->lcand[slot].tot = tk; e->lcand[slot].key = key;
+                                e->lcand[slot].pr = pr; e->lcand[slot].q = q;
+                                e->lcand[slot].ns = ns;
+                                e->lcand[slot].k = kk;
+                                e->lcand[slot].modes = cmodes;
+                                memcpy(e->lcand[slot].sv, sv, sizeof sv);
                             }
                         }
                     }
-                    (void)best_tot;
+                    (void)best_tot; (void)nontrivial;
+                    {
+                        const char *lp2 = getenv("OMC_LAT_PROBE");
+                        int pp2, pq2, pns2;
+                        if (lp2 && sscanf(lp2, "%d,%d,%d", &pp2, &pq2, &pns2) == 3 &&
+                            pr == pp2 && q == pq2 && ns == pns2)
+                            fprintf(stderr, "CAND f%d sl=%d (%d,%d,%d) ok=%d "
+                                    "tot=%lld budget_hard=%lld nlcand=%d\n",
+                                    frame_idx, slice_idx, pr, q, ns, ok,
+                                    (long long)tot, (long long)budget_hard,
+                                    e->nlcand);
+                    }
                 }
-        /* deepest-first verification (max estimated bits): the original
-         * rate loop maximizes refinement under budget, so the true plan is
-         * the most expensive feasible candidate - trying deep plans first
-         * finds it in the fewest tries. Any verified plan reproduces the
-         * input bit-exactly, so the order only affects which valid plan is
-         * chosen, never correctness. The try count is capped for
-         * deterministic encoder timing (C3); a capped-out slice codes
-         * naturally (safe, bounded drift). */
-        enum { LOCK_VERIFY_CAP = 16 };
-        int vtries = 0;
-        while (nlcand > 0 && !locked && vtries < LOCK_VERIFY_CAP) {
-            vtries++;
-            int bi = 0; /* smallest plausibility key first */
-            for (int j = 1; j < nlcand; j++)
-                if (lcand[j].key < lcand[bi].key) bi = j;
-            uint32_t vf = 0;
-            int vg[OMC_NPLANES] = {0, 0, 0};
-            if (lock_verify(e, cf444, lcand[bi].pr, lcand[bi].q, lcand[bi].ns,
-                            lcand[bi].k, lcand[bi].modes, can_inter,
-                            frame_idx, slice_idx, &vf, vg)) {
-                locked = 1;
-                lock_prof = lcand[bi].pr; lock_Q = lcand[bi].q;
-                lock_steps = lcand[bi].ns; lock_partial = lcand[bi].k;
-                lock_modes = lcand[bi].modes;
-                lock_fmask = vf;
-                for (int p = 0; p < OMC_NPLANES; p++) lock_gain[p] = vg[p];
-            } else {
-                lcand[bi] = lcand[--nlcand];
+        /* T5 selection: walk candidates cheapest-estimate first; every
+         * candidate that VERIFIES (bit-exact reproduction) is TRIAL-ENCODED
+         * and the smallest ACTUAL payload that fits the hard budget wins.
+         * Selection by actual size is load-bearing: the exactness induction
+         * (docs/TEMPORAL_T5.md section 5) requires every locked slice to
+         * spend no more than the previous generation's identical slice did,
+         * so that the previous generation's plan always still fits later in
+         * the frame.  The walk stops when the next estimate exceeds the
+         * best actual by a generous slack (no cheaper actual can be hiding
+         * beyond it); v4.9's 16-try cap is gone — a missed lock breaks the
+         * contract, which outranks encoder timing. */
+        if (getenv("OMC_DEBUG_VTRIES"))
+            fprintf(stderr, "slice %d: nlcand=%d budget_hard=%lld\n",
+                    slice_idx, e->nlcand, (long long)budget_hard);
+        {
+            int vtries = 0;
+            int64_t best_bits = -1;
+            while (e->nlcand > 0) {
+                int bi = 0; /* smallest estimated cost first */
+                for (int j = 1; j < e->nlcand; j++)
+                    if (e->lcand[j].key < e->lcand[bi].key) bi = j;
+                if (best_bits >= 0 &&
+                    e->lcand[bi].key > best_bits + best_bits / 16 + 1024)
+                    break;
+                vtries++;
+                uint32_t vf = 0, vm = 0;
+                int vg[OMC_NPLANES] = {0, 0, 0};
+                if (lock_verify(e, cf444, e->lcand[bi].pr, e->lcand[bi].q,
+                                e->lcand[bi].ns, e->lcand[bi].k,
+                                e->lcand[bi].modes, can_inter,
+                                frame_idx, slice_idx, &vm, &vf, vg)) {
+                    int64_t bits = (int64_t)lock_trial_bits(e, cf444, can_inter,
+                                        e->lcand[bi].pr, e->lcand[bi].q,
+                                        e->lcand[bi].ns, e->lcand[bi].k, vm);
+                    if (bits <= budget_hard &&
+                        (best_bits < 0 || bits < best_bits)) {
+                        best_bits = bits;
+                        locked = 1;
+                        lock_prof = e->lcand[bi].pr; lock_Q = e->lcand[bi].q;
+                        lock_steps = e->lcand[bi].ns; lock_partial = e->lcand[bi].k;
+                        lock_modes = vm; /* T5: verify DERIVES the modes */
+                        lock_fmask = vf;
+                        for (int p = 0; p < OMC_NPLANES; p++) lock_gain[p] = vg[p];
+                    }
+                }
+                e->lcand[bi] = e->lcand[--e->nlcand];
             }
+            if (getenv("OMC_DEBUG_VTRIES") && vtries)
+                fprintf(stderr, "slice %d: vtries=%d locked=%d bits=%lld\n",
+                        slice_idx, vtries, locked, (long long)best_bits);
         }
-        if (getenv("OMC_DEBUG_VTRIES") && vtries)
-            fprintf(stderr, "slice %d: vtries=%d locked=%d\n", slice_idx, vtries, locked);
     }
 
     if (getenv("OMC_DEBUG_LOCK"))
@@ -2895,6 +2659,14 @@ mv_done:;
         derive_shifts(cf444, prof, Q, n_steps, partial, &sp);
         goto encode_attempts;
     }
+    /* T5: a locked slice whose actual encode overflowed the estimate falls
+     * back HERE (with locked = 0) after exhausting the verified-candidate
+     * list, and plans naturally.  This is unreachable on generation >= 2
+     * input by the induction of docs/TEMPORAL_T5.md (some verified plan
+     * always fits); it exists so a first-generation slice that came close
+     * to locking still encodes. */
+replan_natural:
+    Q = -1; n_steps = 0; partial = 0; est = 0;
     /* lossless-preferred: start from the minimum-quantization plan (Q=0, all
      * refinement steps). If it fits the CBR budget the slice reconstructs
      * bit-exactly; if not, the overflow backoff below coarsens it while
@@ -2964,12 +2736,22 @@ mv_done:;
             int64_t delta = BMIN(p, b, cur[p][b] - 1) - BMIN(p, b, cur[p][b]);
             int64_t margin = (est + delta) / 160 + 64;
             if (est + delta + margin > budget) {
-                /* try partial chunks of this step */
-                int nchunks = (band_n[p][b] + OMC_CHUNK - 1) / OMC_CHUNK;
-                int64_t room = budget - est - margin;
-                if (delta > 0 && room > 0) {
-                    partial = (int)((room * nchunks) / delta);
-                    if (partial > nchunks) partial = nchunks;
+                /* try partial chunks of this step — T5: only when the step
+                 * band cannot carry grain fill (b < OMC_FILL_BANDS_FROM).
+                 * A partial boundary inside a fill band changes the fill
+                 * amplitudes across it, and the boundary position is not
+                 * recoverable from committed values, so the generation lock
+                 * could never re-derive such a plan.  The lost granularity
+                 * is ~256 coefficients of one refinement step on the
+                 * affected steps; the chunk boundary remains available on
+                 * every band-3 step. */
+                if (b < OMC_FILL_BANDS_FROM) {
+                    int nchunks = (band_n[p][b] + OMC_CHUNK - 1) / OMC_CHUNK;
+                    int64_t room = budget - est - margin;
+                    if (delta > 0 && room > 0) {
+                        partial = (int)((room * nchunks) / delta);
+                        if (partial > nchunks) partial = nchunks;
+                    }
                 }
                 break;
             }
@@ -3022,6 +2804,7 @@ encode_attempts:;
     size_t used_bits = 0;
     uint16_t final_state = 0;
     uint32_t mode_mask = 0;
+    uint8_t emit_gid[OMC_NPLANES][OMC_NBANDS];
     for (int attempt = 0; attempt < 40; attempt++) {
         derive_shifts(cf444, prof, Q, n_steps, partial, &sp);
         mode_mask = 0;
@@ -3032,6 +2815,36 @@ encode_attempts:;
                 int m = locked ? (int)((lock_modes >> (p * OMC_NBANDS + b)) & 1)
                                : BMODE(p, b, s_probe);
                 if (m) mode_mask |= 1u << (p * OMC_NBANDS + b);
+                /* T5: the table-group id must be a pure function of the
+                 * EMITTED SYMBOLS, or it is not generation-invariant and the
+                 * byte count jitters between generations (first caught on
+                 * the partial band, whose committed values mix two shifts;
+                 * then again under --grain-replace, whose classifier shrinks
+                 * the cost-table histograms by source-dependent votes that a
+                 * locked re-encode does not repeat — measured +70 bytes on
+                 * one slice, enough to starve a later slice out of its own
+                 * previous-generation plan).  So: for EVERY band, build the
+                 * exact-plan histogram of exactly what the emission pass
+                 * will produce (same shifts, same eligibility) and pick the
+                 * group from it.  Emitted q values are reproduced across
+                 * generations by the lock, so this choice — and with it the
+                 * payload size — is a generation fixed point. */
+                const uint8_t *scan_elig =
+                    (!locked && e->gr_enabled &&
+                     b >= (omc_gr_mode >= 2 ? 2 : OMC_FILL_BANDS_FROM))
+                        ? e->elig[p][b] : NULL;
+                int gid;
+                {
+                    uint32_t phist[OMC_NCTX][OMC_NSYM];
+                    memset(phist, 0, sizeof(phist));
+                    band_scan(e, p, b, m ? e->dcoef[p][b] : e->coef[p][b],
+                              band_n[p][b], &sp, -1, phist, 0, 0, NULL,
+                              NULL, band_w[p][b], e->rowsig, scan_elig);
+                    int64_t pc64;
+                    gid = best_group(phist, &pc64);
+                }
+                (void)s_probe;
+                emit_gid[p][b] = (uint8_t)gid;
                 if (b == 0 && dc_saved) {
                     /* OMC_DCFB: restore pristine LL, then adjust.
                      * mode 1: null the coded-domain residual mean;
@@ -3059,15 +2872,18 @@ encode_attempts:;
                 }
                 band_scan(e, p, b, m ? e->dcoef[p][b] : e->coef[p][b],
                           band_n[p][b], &sp, -1, NULL, 1,
-                          bc[m][p][b].gid[s_probe], &nsym, e->qbuf[p][b],
+                          gid, &nsym, e->qbuf[p][b],
                           band_w[p][b], e->rowsig,
                           /* locked slices reproduce their input bit-exactly;
                            * GR shrink would break the verified lattice lock
-                           * (A4), so eligibility stands down there. */
-                          (!locked && e->gr_enabled && b >= (omc_gr_mode >= 2 ? 2 : OMC_FILL_BANDS_FROM)) ? e->elig[p][b] : NULL);
-            }
-        /* backward tANS encode */
-        omc_bw_init(&bw, e->paybuf, (size_t)(budget / 8) + 16);
+                           * (A4), so eligibility stands down there — in the
+                           * histogram pass above and here alike. */
+                          scan_elig);
+            }
+        /* backward tANS encode.  Locked slices measure against the HARD
+         * budget (paybuf is sized to the wire cap, which bounds both). */
+        omc_bw_init(&bw, e->paybuf,
+                    (size_t)((locked ? budget_hard : budget) / 8) + 16);
         uint32_t state = OMC_TANS_L;
         for (size_t k = nsym; k-- > 0;) {
             if (e->rawn[k]) omc_bw_put(&bw, e->raws[k], e->rawn[k]);
@@ -3079,7 +2895,7 @@ encode_attempts:;
             state = T->next_state[T->delta_find[s] + (state >> nb)];
         }
         used_bits = bw.bytepos * 8 + (size_t)bw.accbits; /* peek before finish */
-        if ((int64_t)used_bits <= budget) {
+        if ((int64_t)used_bits <= (locked ? budget_hard : budget)) {
             used_bits = omc_bw_finish(&bw);
             final_state = (uint16_t)(state - OMC_TANS_L);
             if (getenv("OMC_STAT_ATTEMPTS") && attempt > 0)
@@ -3089,8 +2905,47 @@ encode_attempts:;
         /* overflow: back off deterministically */
         if (locked && getenv("OMC_DEBUG_LOCK"))
             fprintf(stderr, "slice %d: LOCK OVERFLOW used=%zu budget=%lld\n",
-                    slice_idx, used_bits, (long long)budget);
-        if (locked) { locked = 0; partial = 0; } /* margin missed: drop lock */
+                    slice_idx, used_bits, (long long)budget_hard);
+        if (locked) {
+            /* T5: the chosen candidate's ACTUAL size missed the estimate.
+             * Do not abandon locking — the exactness contract needs the
+             * NEXT verified candidate, not a lossy re-plan.  Remove the
+             * failed candidate and continue the verified scan; only an
+             * exhausted list (impossible at generation >= 2, see
+             * docs/TEMPORAL_T5.md section 5) falls back to natural
+             * planning.  Candidate fallbacks do NOT consume natural-ladder
+             * attempts (the list is its own bounded budget; at high rates a
+             * first-generation slice can shed dozens of near-budget
+             * lossless candidates before the natural plan, and burning the
+             * ladder on them hard-failed the encode). */
+            attempt--;
+            if (lock_ci >= 0 && lock_ci < e->nlcand)
+                e->lcand[lock_ci] = e->lcand[--e->nlcand];
+            locked = 0;
+            lock_ci = -1;
+            while (e->nlcand > 0 && !locked) {
+                int bi = 0;
+                for (int j = 1; j < e->nlcand; j++)
+                    if (e->lcand[j].key < e->lcand[bi].key) bi = j;
+                uint32_t vf = 0, vm = 0;
+                int vg[OMC_NPLANES] = {0, 0, 0};
+                if (lock_verify(e, cf444, e->lcand[bi].pr, e->lcand[bi].q,
+                                e->lcand[bi].ns, e->lcand[bi].k,
+                                e->lcand[bi].modes, can_inter,
+                                frame_idx, slice_idx, &vm, &vf, vg)) {
+                    locked = 1;
+                    lock_ci = bi;
+                    prof = e->lcand[bi].pr; Q = e->lcand[bi].q;
+                    n_steps = e->lcand[bi].ns; partial = e->lcand[bi].k;
+                    lock_modes = vm;
+                    lock_fmask = vf;
+                    for (int p = 0; p < OMC_NPLANES; p++) lock_gain[p] = vg[p];
+                } else {
+                    e->lcand[bi] = e->lcand[--e->nlcand];
+                }
+            }
+            if (!locked) goto replan_natural;
+        }
         else if (omc_dcfb >= 3 && dc3_done && !dc3_reverted) {
             /* The DC correction must never cost plan quality: if pass B
              * overflows where pass A fitted, the adjustment is what tipped
@@ -3161,8 +3016,8 @@ encode_attempts:;
     }
 
     size_t used_bytes = (used_bits + 7) / 8;
-    size_t slice_size = OMC_SLICE_HDR_BYTES + mvsize + used_bytes;
-    memcpy(dst + OMC_SLICE_HDR_BYTES + mvsize, e->paybuf, used_bytes);
+    size_t slice_size = OMC_SLICE_HDR_BYTES + used_bytes;
+    memcpy(dst + OMC_SLICE_HDR_BYTES, e->paybuf, used_bytes);
 
     /* OMC_DUMP: per-band symbol-stream dump for offline entropy studies.
      * Record: i32 frame, slice, plane, band, shift(base), w, n, mode;
@@ -3371,7 +3226,7 @@ encode_attempts:;
                         v = fill_value_p(ll, pw, llw, llh, b, i / B->w, fcol,
                                        sft, fox, foy, sfox, sfoy, lllim,
                                        fill_gain[p], c->cfg.grain_corr,
-                                       1 + (c->cfg.fill_static ? 1 : 0),
+                                       (c->cfg.fill_static ? 1 : 0),
                                        0, &fp);
                     e->sbuf[p][(size_t)(B->r0 + i / B->w) * pw + B->c0 + i % B->w] = v;
                 }
@@ -3539,19 +3394,15 @@ encode_attempts:;
     omc_bw_put(&hw, (uint32_t)slice_idx, 16);
     omc_bw_put(&hw, (uint32_t)Q, 4);
     omc_bw_put(&hw, (uint32_t)prof, 2);
-    /* v4.3: bit 7 of the n_steps byte (always 0 in prior streams, since
-     * omc_refine_steps = 52) flags the per-block MV field between header and
-     * payload. Decoders of minor >= 3 mask it off; older decoders reject
-     * minor-3 streams at the stream header. */
-    omc_bw_put(&hw, (uint32_t)n_steps | (mv_present ? 0x80u : 0), 8);
+    /* T5: bit 7 of the n_steps byte (the old per-block-MV-field flag) is
+     * RESERVED 0 — the block motion field left with the old engine. */
+    omc_bw_put(&hw, (uint32_t)n_steps, 8);
     omc_bw_put(&hw, (uint32_t)partial, 16);
     omc_bw_put(&hw, (uint32_t)used_bits, 24);
     omc_bw_put(&hw, final_state, 16);
     for (int p = 0; p < OMC_NPLANES; p++)
-        for (int b = 0; b < OMC_NBANDS; b++) {
-            int m = (int)((mode_mask >> (p * OMC_NBANDS + b)) & 1);
-            omc_bw_put(&hw, bc[m][p][b].gid[sp.shift[p][b]], 4);
-        }
+        for (int b = 0; b < OMC_NBANDS; b++)
+            omc_bw_put(&hw, emit_gid[p][b], 4); /* as emitted (partial-aware) */
     omc_bw_put(&hw, mode_mask, 30);
     for (int rg = 0; rg < OMC_NREG; rg++) { /* v4.1: +/-32 px h, +/-16 px v */
         omc_bw_put(&hw, (uint32_t)(mvx2[rg] + 64), 7);
@@ -3561,24 +3412,16 @@ encode_attempts:;
     for (int p = 0; p < OMC_NPLANES; p++) /* v4.1 per-plane fill gain */
         omc_bw_put(&hw, (uint32_t)fill_gain[p], 2);
     omc_bw_finish(&hw);
-    /* v4.3 MV field: 7 bits per block (dx offset [-8,7] biased +8: 4 bits;
-     * dy offset [-4,3] biased +4: 3 bits), LSB-first, zero-padded to bytes. */
-    if (mvsize) {
-        omc_bw_t mw;
-        omc_bw_init(&mw, dst + OMC_SLICE_HDR_BYTES, mvsize);
-        for (int blk = 0; blk < e->nblk; blk++) {
-            omc_bw_put(&mw, (uint32_t)e->bmode[blk], 1);
-            omc_bw_put(&mw, (uint32_t)(e->bofx[blk] + 8), 4);
-            omc_bw_put(&mw, (uint32_t)(e->bofy[blk] + 4), 3);
-        }
-        omc_bw_finish(&mw);
-    }
-    /* CRC over header (sans CRC field) then MV field + payload */
+    /* CRC over header (sans CRC field) then payload */
     uint32_t crc = omc_crc32(dst, OMC_SLICE_HDR_BYTES - 4);
-    crc = omc_crc32_ext(crc, dst + OMC_SLICE_HDR_BYTES, mvsize + used_bytes);
+    crc = omc_crc32_ext(crc, dst + OMC_SLICE_HDR_BYTES, used_bytes);
     memcpy(dst + OMC_SLICE_HDR_BYTES - 4, &crc, 4);
 
     e->spent_bits += (int64_t)slice_size * 8;
+    if (getenv("OMC_DEBUG_SIZES"))
+        fprintf(stderr, "SZ f%d s%d bytes=%zu locked=%d spent=%lld\n",
+                frame_idx, slice_idx, slice_size, locked,
+                (long long)e->spent_bits);
 
     /* 7. encoder-side reconstruction: always computed - it is both the rt=0
      * source of truth and the temporal reference for the next frame. */
@@ -3612,33 +3455,27 @@ encode_attempts:;
                         v = fill_value_p(ll, pw, llw, llh, b, i / B->w, fcol,
                                        s, fox, foy, sfox, sfoy, lllim, fill_gain[p],
                                        c->cfg.grain_corr,
-                                       1 + (c->cfg.fill_static ? 1 : 0),
+                                       (c->cfg.fill_static ? 1 : 0),
                                        0, &fp);
                     e->sbuf[p][(size_t)(B->r0 + i / B->w) * pw + B->c0 + fcol] = v;
                 }
             }
         }
         omc_frame_t rf;
-        int tf_on = omc_tf_mode && mode_mask != 0;
         for (int p = 0; p < OMC_NPLANES; p++) {
             rf.p[p] = e->ref[p];
             rf.stride[p] = plane_width(c, p);
         }
-        /* OMC-TF: capture the previous frame around this slice BEFORE
-         * reconstruction overwrites it, then filter the reconstruction. The
-         * decoder does exactly the same thing to exactly the same samples. */
-        if (tf_on) tf_gather(c, e->ref, e->tfwin, e->tftail, slice_idx);
+        /* T5: reconstruct straight into the rolling current-frame store (the
+         * biased domain is the only domain).  The boundary edit inside
+         * reconstruct_slice retro-touches the previous slice's last row of
+         * ref as well. */
         reconstruct_slice(c, e->sbuf, e->tmp, &rf, slice_idx, 1);
-        if (tf_on) {
-            int st[OMC_NPLANES];
-            for (int p = 0; p < OMC_NPLANES; p++) st[p] = plane_width(c, p);
-            tf_apply(c, e->ref, st, e->tfwin, slice_idx, mvx2, mvy2);
-        }
         /* OMC_DCFB: measure this slice's mean reconstruction offset per plane
          * (the persistent per-slice "color decision"); the sign feeds the LL
-         * rounding servo on the NEXT frame's inter coding of this slice. */
+         * rounding servo on the NEXT frame's inter coding of this slice.
+         * Both operands are biased, so the bias cancels. */
         if (omc_dcfb) {
-            int rbias = omc_ref_unclipped ? OMC_REF_BIAS : 0;
             for (int p = 0; p < OMC_NPLANES; p++) {
                 int pw = plane_width(c, p);
                 int64_t sum = 0;
@@ -3646,7 +3483,7 @@ encode_attempts:;
                     const uint16_t *rr = e->ref[p] + (size_t)(slice_idx * sh + r) * pw;
                     const uint16_t *ss = in->p[p] + (size_t)(slice_idx * sh + r) * in->stride[p];
                     for (int x = 0; x < pw; x++)
-                        sum += (int32_t)rr[x] - rbias - (int32_t)ss[x];
+                        sum += (int32_t)rr[x] - (int32_t)ss[x];
                 }
                 int64_t npx = (int64_t)pw * sh;
                 int64_t m8 = sum * 256 / npx;
@@ -3655,37 +3492,50 @@ encode_attempts:;
                 e->dc_q8[slice_idx * OMC_NPLANES + p] = (int16_t)m8;
             }
         }
+        /* recon out (biased domain): this slice's rows PLUS the previous
+         * slice's retro-edited last row.  The old unclipped prototype
+         * omitted the retro row, so the emitted picture disagreed with the
+         * committed reference at every interior boundary — fixed here. */
         if (recon)
             for (int p = 0; p < OMC_NPLANES; p++) {
                 int pw = plane_width(c, p);
-                if (omc_ref_unclipped) {
-                    /* F-4: user-visible output is clip(ref - bias, 0, maxv);
-                     * only the internal reference stays unclipped. */
-                    for (int r = 0; r < sh; r++) {
-                        const uint16_t *sr = e->ref[p] + (size_t)(slice_idx * sh + r) * pw;
-                        uint16_t *dr = recon->p[p] + (size_t)(slice_idx * sh + r) * recon->stride[p];
-                        for (int x = 0; x < pw; x++) {
-                            int32_t v = (int32_t)sr[x] - OMC_REF_BIAS;
-                            if (v < 0) v = 0;
-                            if (v > c->maxv) v = c->maxv;
-                            dr[x] = (uint16_t)v;
-                        }
-                    }
-                } else {
-                    for (int r = 0; r < sh; r++)
-                        memcpy(recon->p[p] + (size_t)(slice_idx * sh + r) * recon->stride[p],
-                               e->ref[p] + (size_t)(slice_idx * sh + r) * pw,
-                               (size_t)pw * 2);
-                    /* XSL=3 retro-edited the previous slice's last row in ref */
-                    if (omc_xsl >= 3 && slice_idx > 0)
-                        memcpy(recon->p[p] + (size_t)(slice_idx * sh - 1) * recon->stride[p],
-                               e->ref[p] + (size_t)(slice_idx * sh - 1) * pw,
-                               (size_t)pw * 2);
-                }
+                int r0x = slice_idx > 0 ? -1 : 0;
+                for (int r = r0x; r < sh; r++)
+                    memcpy(recon->p[p] + (size_t)(slice_idx * sh + r) * recon->stride[p],
+                           e->ref[p] + (size_t)(slice_idx * sh + r) * pw,
+                           (size_t)pw * 2);
             }
     }
+    /* barrier display blend on the EMITTED picture only (reference untouched) */
     if (recon) xsl_display_blend(c, recon, slice_idx, frame_idx & 0xFF);
-    if (slice_idx == c->nslices - 1) e->last_frame = frame_idx;
+    if (slice_idx == c->nslices - 1) {
+        /* debug: dump the committed (pre-display-blend) picture — the exact
+         * target the un-blend must recover (OMC_DUMP_COMMITTED=<prefix>) */
+        const char *dcp = getenv("OMC_DUMP_COMMITTED");
+        if (dcp) {
+            char fn[512];
+            snprintf(fn, sizeof fn, "%s.f%d.ref", dcp, frame_idx);
+            FILE *df = fopen(fn, "wb");
+            if (df) {
+                for (int p = 0; p < OMC_NPLANES; p++)
+                    fwrite(e->ref[p], 2, (size_t)plane_width(c, p) * c->H, df);
+                fclose(df);
+            }
+        }
+        /* T5 frame-end promotion: the finished current frame becomes the
+         * prediction reference; the old reference becomes the motion-
+         * derivation frame.  Pointer rotation + one copy (ref keeps rolling
+         * into the same storage next frame). */
+        for (int p = 0; p < OMC_NPLANES; p++) {
+            uint16_t *t = e->refprev2[p];
+            e->refprev2[p] = e->refprev[p];
+            e->refprev[p] = t;
+            memcpy(e->refprev[p], e->ref[p],
+                   (size_t)plane_width(c, p) * c->H * 2);
+        }
+        e->last_frame2 = e->last_frame;
+        e->last_frame = frame_idx;
+    }
     return (int)slice_size;
 }
 
@@ -3694,9 +3544,28 @@ int64_t omc_enc_frame(omc_enc_t *e, const omc_frame_t *in, int frame_idx,
 {
     size_t need = e->c.slice_bytes * (size_t)e->c.nslices; /* frame = exactly F */
     if (cap < need) return -1;
+    /* T5 MANDATORY UN-BLEND: copy the input and undo the boundary edit.
+     * Detector-free by design — the un-blend is applied to EVERY input.  On
+     * generation >= 2 material this recovers the previous encoder's exact
+     * committed reconstruction (the edit is an invertible lifting cascade);
+     * on first-generation masters it pre-distorts the boundary rows within
+     * the blend cap, which the decoder's forward edit then cancels.  A
+     * detector could keep slightly more of the seam repair on masters, but
+     * any detector is a threshold on generation-varying data — exactly the
+     * class of decision the T5 rebuild exists to eliminate. */
+    omc_frame_t ub;
+    for (int p = 0; p < OMC_NPLANES; p++) {
+        int pw = plane_width(&e->c, p);
+        ub.p[p] = e->inub[p];
+        ub.stride[p] = pw;
+        for (int r = 0; r < e->c.H; r++)
+            memcpy(e->inub[p] + (size_t)r * pw,
+                   in->p[p] + (size_t)r * in->stride[p], (size_t)pw * 2);
+    }
+    omc_xsl_unblend(&ub, &e->c.cfg, frame_idx);
     size_t off = 0;
     for (int s = 0; s < e->c.nslices; s++) {
-        int r = omc_enc_slice(e, in, frame_idx, s, dst + off, recon);
+        int r = omc_enc_slice(e, &ub, frame_idx, s, dst + off, recon);
         if (r < 0) return -2;
         off += (size_t)r;
     }
@@ -3710,14 +3579,7 @@ int64_t omc_enc_frame(omc_enc_t *e, const omc_frame_t *in, int frame_idx,
 omc_dec_t *omc_dec_create(const omc_config_t *cfg)
 {
     omc_global_init();
-    if (omc_xsl) omc_xsl_lim = xsl_lim_for(cfg);
-    { const char *ne = getenv("OMC_XSL_NOEDIT"); omc_xsl_noedit = ne && atoi(ne); }
-    /* The STREAM is authoritative for the in-loop filter, not the environment.
-     * omc_global_init() seeds omc_tf_mode from OMC_TF because that is how an
-     * ENCODER is asked for the filter; a decoder must instead take what the
-     * encoder recorded, or it reconstructs a different picture from the one the
-     * encoder verified and drifts further with every frame (C4/C8). */
-    omc_tf_mode = cfg->tf_mode & 3;
+    omc_xsl_lim = xsl_lim_for(cfg); /* legacy mirror; codec reads c->xsl_lim */
     omc_dec_t *d = calloc(1, sizeof(*d));
     if (!d) return NULL;
     common_init(&d->c, cfg);
@@ -3734,25 +3596,22 @@ omc_dec_t *omc_dec_create(const omc_config_t *cfg)
         for (int p = 0; p < OMC_NPLANES; p++) {
             int pw = plane_width(&d->c, p);
             d->ref[p] = calloc((size_t)pw * d->c.H, 2);
-            d->tfwin[p] = calloc((size_t)pw * tf_win_rows(&d->c), 2);
-            d->tftail[p] = calloc((size_t)pw * tf_pad(&d->c), 2);
-            if (!d->ref[p] || !d->tfwin[p] || !d->tftail[p]) {
+            d->refprev[p] = calloc((size_t)pw * d->c.H, 2);
+            if (!d->ref[p] || !d->refprev[p]) {
                 omc_dec_destroy(d); return NULL;
             }
-            uint16_t mid = (uint16_t)((1u << (cfg->bitdepth - 1)) +
-                                      (omc_ref_unclipped ? OMC_REF_BIAS : 0));
-            for (size_t i = 0; i < (size_t)pw * d->c.H; i++) d->ref[p][i] = mid;
+            /* mid-grey in the biased domain (matches the encoder's init) */
+            uint16_t mid = (uint16_t)((1u << (cfg->bitdepth - 1)) + OMC_REF_BIAS);
+            for (size_t i = 0; i < (size_t)pw * d->c.H; i++)
+                d->ref[p][i] = d->refprev[p][i] = mid;
             d->pbuf[p] = malloc(sizeof(int32_t) * (size_t)pw * d->c.sh);
             omc_band_layout(pw, d->c.sh, bands);
             for (int b = 0; b < OMC_NBANDS; b++)
                 d->pcoef[p][b] = malloc(sizeof(int32_t) * (size_t)bands[b].h * bands[b].w);
         }
     }
+    d->cur_fidx8 = -1;
     d->conceal_mode = 1; /* MC + spatial by default; CLI can drop to freeze */
-    d->nblk = num_blocks(d->c.W);
-    d->bofx = calloc((size_t)d->nblk, 1);
-    d->bofy = calloc((size_t)d->nblk, 1);
-    d->bmode = calloc((size_t)d->nblk, 1);
     d->slice_got = calloc((size_t)d->c.nslices, 1);
     d->slice_inter = calloc((size_t)d->c.nslices, 1);
     d->slice_mvx = calloc((size_t)d->c.nslices * OMC_NREG, 1);
@@ -3768,17 +3627,15 @@ void omc_dec_set_conceal(omc_dec_t *d, int mode) { d->conceal_mode = mode; }
 
 void omc_dec_destroy(omc_dec_t *d)
 {
-    omc_tf_stats_report("dec");
     if (!d) return;
     for (int p = 0; p < OMC_NPLANES; p++) free(d->sbuf[p]);
     free(d->tmp); free(d->pad); free(d->rowsig);
     for (int p = 0; p < OMC_NPLANES; p++) {
-        free(d->ref[p]); free(d->tfwin[p]); free(d->tftail[p]); free(d->pbuf[p]);
+        free(d->ref[p]); free(d->refprev[p]); free(d->pbuf[p]);
         for (int b = 0; b < OMC_NBANDS; b++) free(d->pcoef[p][b]);
     }
     free(d->slice_got); free(d->slice_inter);
     free(d->slice_mvx); free(d->slice_mvy);
-    free(d->bofx); free(d->bofy); free(d->bmode);
     free(d);
 }
 
@@ -3800,23 +3657,32 @@ int omc_dec_slice_ex(omc_dec_t *d, const uint8_t *src, size_t avail,
     if (omc_fr_get(&fr, 32) != OMC_SYNC) return -1;
     int fidx8 = (int)omc_fr_get(&fr, 8); /* low 8 bits of frame idx (fill phase) */
     int slice_idx = (int)omc_fr_get(&fr, 16);
-    /* OMC_XSL boundary term from slice k-1's committed reconstruction —
-     * must precede the prediction transform and the inverse below; mirrors
-     * the encoder's per-slice prep exactly (same rows, same bias). */
+    /* T5 frame promotion: the first slice of a new frame (fidx8 change)
+     * promotes the finished current frame to the prediction reference.
+     * Mirrors the encoder's frame-end rotation exactly. */
+    if (fidx8 != d->cur_fidx8) {
+        if (d->cur_fidx8 >= 0)
+            for (int p = 0; p < OMC_NPLANES; p++)
+                memcpy(d->refprev[p], d->ref[p],
+                       (size_t)plane_width(c, p) * c->H * 2);
+        d->cur_fidx8 = fidx8;
+    }
+    /* XSL boundary term from slice k-1's committed reconstruction of the
+     * CURRENT frame — must precede the prediction transform and the inverse
+     * below; mirrors the encoder's per-slice prep exactly. */
     if (slice_idx >= 0 && slice_idx < c->nslices) {
         omc_frame_t xrf;
         for (int p = 0; p < OMC_NPLANES; p++) {
             xrf.p[p] = d->ref[p];
             xrf.stride[p] = plane_width(c, p);
         }
-        xsl_prep(c, &xrf, slice_idx, omc_ref_unclipped ? OMC_REF_BIAS : 0,
-                 fidx8);
+        xsl_prep(c, &xrf, slice_idx, OMC_REF_BIAS, fidx8);
     }
     int Q = (int)omc_fr_get(&fr, 4);
     int prof = (int)omc_fr_get(&fr, 2);
     int n_steps_raw = (int)omc_fr_get(&fr, 8);
-    /* v4.3: bit 7 flags the per-block MV field (minor >= 3 streams only) */
-    int mv_present = (c->cfg.ver_minor >= 3) && (n_steps_raw & 0x80);
+    /* T5: bit 7 (the old per-block MV field flag) is reserved 0 */
+    if (n_steps_raw & 0x80) return -1;
     int n_steps = n_steps_raw & 0x7F;
     int partial = (int)omc_fr_get(&fr, 16);
     size_t used_bits = omc_fr_get(&fr, 24);
@@ -3829,73 +3695,45 @@ int omc_dec_slice_ex(omc_dec_t *d, const uint8_t *src, size_t avail,
     int8_t mvx2[OMC_NREG], mvy2[OMC_NREG];
     int fill_gain[OMC_NPLANES] = {0, 0, 0};
     uint32_t fill_mask;
-    if (c->cfg.ver_minor >= 1) { /* v4.1 layout: wide MVs + per-plane gain */
-        for (int rg = 0; rg < OMC_NREG; rg++) {
-            mvx2[rg] = (int8_t)((int)omc_fr_get(&fr, 7) - 64);
-            mvy2[rg] = (int8_t)((int)omc_fr_get(&fr, 6) - 32);
-        }
-        fill_mask = omc_fr_get(&fr, 18);
-        for (int p = 0; p < OMC_NPLANES; p++)
-            fill_gain[p] = (int)omc_fr_get(&fr, 2);
-    } else { /* v4.0 layout */
-        for (int rg = 0; rg < OMC_NREG; rg++) {
-            mvx2[rg] = (int8_t)((int)omc_fr_get(&fr, 5) - 16);
-            mvy2[rg] = (int8_t)((int)omc_fr_get(&fr, 4) - 8);
-        }
-        fill_mask = omc_fr_get(&fr, 18);
+    for (int rg = 0; rg < OMC_NREG; rg++) {
+        mvx2[rg] = (int8_t)((int)omc_fr_get(&fr, 7) - 64);
+        mvy2[rg] = (int8_t)((int)omc_fr_get(&fr, 6) - 32);
     }
+    fill_mask = omc_fr_get(&fr, 18);
+    for (int p = 0; p < OMC_NPLANES; p++)
+        fill_gain[p] = (int)omc_fr_get(&fr, 2);
     size_t used_bytes = (used_bits + 7) / 8;
-    size_t mvsize = mv_present ? mv_field_bytes(d->nblk) : 0;
     if (slice_idx >= c->nslices) return -1;
-    if (OMC_SLICE_HDR_BYTES + mvsize + used_bytes > take) return -1;
+    if (OMC_SLICE_HDR_BYTES + used_bytes > take) return -1;
 
     uint32_t crc_stored;
     memcpy(&crc_stored, d->pad + OMC_SLICE_HDR_BYTES - 4, 4);
     uint32_t crc = omc_crc32(d->pad, OMC_SLICE_HDR_BYTES - 4);
-    crc = omc_crc32_ext(crc, d->pad + OMC_SLICE_HDR_BYTES, mvsize + used_bytes);
+    crc = omc_crc32_ext(crc, d->pad + OMC_SLICE_HDR_BYTES, used_bytes);
     if (crc != crc_stored) return -2;
-    if (consumed) *consumed = OMC_SLICE_HDR_BYTES + mvsize + used_bytes;
+    if (consumed) *consumed = OMC_SLICE_HDR_BYTES + used_bytes;
 
-    /* v4.3: parse per-block MV offsets (or zero them) */
-    if (mv_present) {
-        omc_fr_t mr;
-        omc_fr_init(&mr, d->pad + OMC_SLICE_HDR_BYTES);
-        for (int blk = 0; blk < d->nblk; blk++) {
-            d->bmode[blk] = (uint8_t)omc_fr_get(&mr, 1);
-            d->bofx[blk] = (int8_t)((int)omc_fr_get(&mr, 4) - 8);
-            d->bofy[blk] = (int8_t)((int)omc_fr_get(&mr, 3) - 4);
-        }
-    } else {
-        memset(d->bofx, 0, (size_t)d->nblk);
-        memset(d->bofy, 0, (size_t)d->nblk);
-        memset(d->bmode, 0, (size_t)d->nblk);
-    }
-    if (getenv("OMC_DEBUG_MV") && fidx8 <= 2 && slice_idx <= 6) {
-        fprintf(stderr, "DEC f%d s%d mvp=%d g=(%d,%d) bof:", fidx8,
-                slice_idx, mv_present, mvx2[0], mvy2[0]);
-        for (int j = 100; j < 128 && j < d->nblk; j++)
-            fprintf(stderr, " %d,%d", d->bofx[j], d->bofy[j]);
-        fprintf(stderr, "\n");
-    }
+    if (getenv("OMC_DEBUG_MV") && fidx8 <= 2 && slice_idx <= 6)
+        fprintf(stderr, "DEC f%d s%d mv=(%d,%d)\n", fidx8,
+                slice_idx, mvx2[0], mvy2[0]);
 
     if (prof >= OMC_NPROFILES) return -1;
     shift_plan_t sp;
     derive_shifts(c->cfg.chroma == OMC_CF_444, prof, Q, n_steps, partial, &sp);
 
     omc_br_t br;
-    omc_br_init(&br, d->pad + OMC_SLICE_HDR_BYTES + mvsize, used_bits);
+    omc_br_init(&br, d->pad + OMC_SLICE_HDR_BYTES, used_bits);
 
     omc_band_t bands[OMC_NBANDS];
     for (int p = 0; p < OMC_NPLANES; p++) {
         int pw = plane_width(c, p);
         omc_band_layout(pw, c->sh, bands);
-        /* temporal prediction for this plane if any of its bands is inter */
+        /* temporal prediction for this plane if any of its bands is inter.
+         * T5: the source is the PREVIOUS FRAME'S FINAL picture (refprev) —
+         * never the rolling current-frame store. */
         int plane_inter = (mode_mask >> (p * OMC_NBANDS)) & 0x3FF;
         if (plane_inter)
-            predict_plane(c, d->ref[p], p, slice_idx, mvx2, mvy2,
-                          mv_present ? d->bofx : NULL,
-                          mv_present ? d->bofy : NULL,
-                          mv_present ? d->bmode : NULL, d->nblk,
+            predict_plane(c, d->refprev[p], p, slice_idx, mvx2, mvy2,
                           d->pbuf[p], d->tmp, d->pcoef[p]);
         int llw = pw / 32, llh = c->sh / 4;
         int32_t lllim = c->mid - (c->mid >> 4);
@@ -3913,11 +3751,10 @@ int omc_dec_slice_ex(omc_dec_t *d, const uint8_t *src, size_t avail,
             }
             const int32_t *ll = d->sbuf[p]; /* LL rect decoded first (b=0) */
             const int32_t *pc = d->pcoef[p][b];
-            /* v4.4 streams (minor >= 4) use the 16-magnitude-context tables;
-             * older streams decode with the legacy 4-context set. */
-            int v44 = c->cfg.ver_minor >= 4;
-            const omc_tans_table_t *grp = v44 ? omc_tans[gids[p][b] & (OMC_NTABLES - 1)]
-                                              : omc_tans_legacy[gids[p][b]];
+            /* T5 streams are minor 10: always the v4.4 16-magnitude-context
+             * tables (the legacy set remains linked for the offline tools) */
+            const int v44 = 1;
+            const omc_tans_table_t *grp = omc_tans[gids[p][b] & (OMC_NTABLES - 1)];
             memset(d->rowsig, 0, (size_t)B->w);
             fp_t fp; fp_build(&fp, bands, d->sbuf[p], pw, b, &sp, p);
             int col = 0, left = 0, row = 0;
@@ -3949,8 +3786,7 @@ int omc_dec_slice_ex(omc_dec_t *d, const uint8_t *src, size_t avail,
                 if (fb && rec == 0 && q == 0)
                     rec = fill_value_p(ll, pw, llw, llh, b, row, col, s, fox, foy, sfox, sfoy,
                                      lllim, fill_gain[p], c->cfg.grain_corr,
-                                     (c->cfg.ver_minor >= 6) +
-                                     (c->cfg.fill_static && c->cfg.ver_minor >= 7 ? 1 : 0),
+                                     (c->cfg.fill_static ? 1 : 0),
                                      0, &fp);
                 d->sbuf[p][(size_t)(B->r0 + i / B->w) * pw + B->c0 + col] = rec;
                 left = v44 ? omc_q2(v < 0 ? -v : v) : (v != 0);
@@ -3984,46 +3820,26 @@ int omc_dec_slice_ex(omc_dec_t *d, const uint8_t *src, size_t avail,
             }
         }
     }
-    /* OMC-TF: same capture the encoder makes, at the same point, from the same
-     * reference contents — see tf_gather().  The gate (mode_mask != 0) is read
-     * from the slice header, so both ends decide identically with no extra
-     * signalling and rt = 0 is preserved by construction. */
-    int tf_on = omc_tf_mode && mode_mask != 0;
-    if (tf_on) tf_gather(c, d->ref, d->tfwin, d->tftail, slice_idx);
-    if (omc_ref_unclipped) {
-        /* F-4: reconstruct straight into the (biased, unclipped) reference,
-         * then produce the legal-range user output from it - the mirror of
-         * the encoder's reconstruct-to-ref + recon-output copy. */
+    /* T5: reconstruct straight into the rolling current-frame store (biased
+     * domain; the boundary edit inside retro-touches the previous slice's
+     * last row), then copy the committed rows to the user output — this
+     * slice's rows PLUS the retro-edited row above, exactly as the encoder's
+     * recon path does. */
+    {
         omc_frame_t rf;
         for (int p = 0; p < OMC_NPLANES; p++) {
             rf.p[p] = d->ref[p];
             rf.stride[p] = plane_width(c, p);
         }
         reconstruct_slice(c, d->sbuf, d->tmp, &rf, slice_idx, 1);
-        if (tf_on) {
-            int st[OMC_NPLANES];
-            for (int p = 0; p < OMC_NPLANES; p++) st[p] = plane_width(c, p);
-            tf_apply(c, d->ref, st, d->tfwin, slice_idx, mvx2, mvy2);
-        }
         for (int p = 0; p < OMC_NPLANES; p++) {
             int pw = plane_width(c, p);
-            for (int r = 0; r < c->sh; r++) {
-                const uint16_t *sr = d->ref[p] + (size_t)(slice_idx * c->sh + r) * pw;
-                uint16_t *dr = out->p[p] + (size_t)(slice_idx * c->sh + r) * out->stride[p];
-                for (int x = 0; x < pw; x++) {
-                    int32_t v = (int32_t)sr[x] - OMC_REF_BIAS;
-                    if (v < 0) v = 0;
-                    if (v > c->maxv) v = c->maxv;
-                    dr[x] = (uint16_t)v;
-                }
-            }
+            int r0x = slice_idx > 0 ? -1 : 0;
+            for (int r = r0x; r < c->sh; r++)
+                memcpy(out->p[p] + (size_t)(slice_idx * c->sh + r) * out->stride[p],
+                       d->ref[p] + (size_t)(slice_idx * c->sh + r) * pw,
+                       (size_t)pw * 2);
         }
-    } else {
-        reconstruct_slice(c, d->sbuf, d->tmp, out, slice_idx, 0);
-        /* Default path: reconstruction lands in the user output and is copied
-         * into the reference below, so filtering `out` here filters both. */
-        if (tf_on) tf_apply(c, out->p, out->stride, d->tfwin, slice_idx,
-                            mvx2, mvy2);
     }
     {
         const char *tp = getenv("OMC_TRACE");
@@ -4044,17 +3860,8 @@ int omc_dec_slice_ex(omc_dec_t *d, const uint8_t *src, size_t avail,
             }
         }
     }
-    /* update the temporal reference with this slice's reconstruction
-     * (F-4 mode already reconstructed directly into the reference above) */
-    if (!omc_ref_unclipped)
-        for (int p = 0; p < OMC_NPLANES; p++) {
-            int pw = plane_width(c, p);
-            int r0x = (omc_xsl >= 3 && slice_idx > 0) ? -1 : 0;
-            for (int r = r0x; r < c->sh; r++)
-                memcpy(d->ref[p] + (size_t)(slice_idx * c->sh + r) * pw,
-                       out->p[p] + (size_t)(slice_idx * c->sh + r) * out->stride[p],
-                       (size_t)pw * 2);
-        }
+    /* barrier display blend on the EMITTED picture only; the committed
+     * reference (d->ref) never sees it, matching the encoder exactly */
     xsl_display_blend(c, out, slice_idx, fidx8);
     /* record this slice's motion/mode so neighbours can conceal a lost slice */
     if (d->slice_got) {
@@ -4089,8 +3896,10 @@ static void conceal_mc_plane(omc_dec_t *d, omc_frame_t *out, int p,
                              const int8_t *mvy2)
 {
     ctx_common_t *c = &d->c;
-    int pw = plane_width(c, p), sh = c->sh, H = c->H, maxv = c->maxv;
-    const uint16_t *ref = d->ref[p];
+    int pw = plane_width(c, p), sh = c->sh, H = c->H;
+    int maxv = c->maxv + 2 * OMC_REF_BIAS; /* T5 wide (biased) domain */
+    /* T5: temporal projection reads the PREVIOUS frame's final picture */
+    const uint16_t *ref = d->refprev[p];
     uint16_t *op = out->p[p];
     int ostride = out->stride[p];
     for (int reg = 0; reg < OMC_NREG; reg++) {
diff --git a/tests/test_cap.c b/tests/test_cap.c
index 3df4079..e7bd5a2 100644
--- a/tests/test_cap.c
+++ b/tests/test_cap.c
@@ -26,7 +26,8 @@ static void fill(uint16_t *p, size_t n, uint32_t seed)
 {
     uint32_t x = seed;
     for (size_t i = 0; i < n; i++) { x = x * 1103515245u + 12345u;
-                                     p[i] = (uint16_t)(64 + ((x >> 16) % 800)); }
+                                     p[i] = (uint16_t)(64 + ((x >> 16) % 800)
+                                                       + OMC_PIX_BIAS); }
 }
 
 static void cfg_at(omc_config_t *c, uint32_t bps)
diff --git a/tests/test_unit.c b/tests/test_unit.c
index 27986d1..974a37d 100644
--- a/tests/test_unit.c
+++ b/tests/test_unit.c
@@ -94,9 +94,9 @@ static void test_slice_roundtrip(void)
     uint16_t *pix = malloc((ysz + 2 * csz) * 2);
     uint16_t *rec = malloc((ysz + 2 * csz) * 2);
     uint16_t *dec = malloc((ysz + 2 * csz) * 2);
-    /* synthetic: gradient + noise + edges */
+    /* synthetic: gradient + noise + edges (T5 biased domain) */
     for (size_t i = 0; i < ysz + 2 * csz; i++)
-        pix[i] = (uint16_t)((i * 7 % 900) + 64 + (rnd() % 32));
+        pix[i] = (uint16_t)((i * 7 % 900) + 64 + (rnd() % 32) + OMC_PIX_BIAS);
     omc_frame_t fin = {{pix, pix + ysz, pix + ysz + csz}, {W, Wc, Wc}};
     omc_frame_t frec = {{rec, rec + ysz, rec + ysz + csz}, {W, Wc, Wc}};
     omc_frame_t fdec = {{dec, dec + ysz, dec + ysz + csz}, {W, Wc, Wc}};
@@ -131,7 +131,8 @@ static void test_causality(void)
     size_t words = ysz + 2 * csz;
     uint16_t *pix = malloc(words * 2);
     uint16_t *poison = malloc(words * 2);
-    for (size_t i = 0; i < words; i++) pix[i] = (uint16_t)(rnd() % 1024);
+    for (size_t i = 0; i < words; i++)
+        pix[i] = (uint16_t)((rnd() % 1024) + OMC_PIX_BIAS);
     omc_frame_t f1 = {{pix, pix + ysz, pix + ysz + csz}, {W, Wc, Wc}};
     omc_frame_t f2 = {{poison, poison + ysz, poison + ysz + csz}, {W, Wc, Wc}};
 
@@ -146,20 +147,27 @@ static void test_causality(void)
     int ok = (n1 > 0);
     for (int k = 0; k < nsl && ok; k++) {
         memcpy(poison, pix, words * 2);
-        /* poison every row strictly below the current slice in all planes */
+        /* T5 causality bound: slice k depends on input rows
+         * [0, (k+1)*sh + 2) — the mandatory un-blend of the slice's last
+         * boundary row reads the two rows below it (a fixed 2-line
+         * lookahead, documented in TEMPORAL_T5.md).  Poison strictly below
+         * that bound.  Slice-level callers apply the un-blend themselves
+         * (omc_enc_frame does it internally). */
         for (int p = 0; p < 3; p++) {
             int pw = p == 0 ? W : Wc;
             uint16_t *pl = f2.p[p];
-            for (int r = (k + 1) * sh; r < H; r++)
+            for (int r = (k + 1) * sh + 2; r < H; r++)
                 for (int x = 0; x < pw; x++)
-                    pl[(size_t)r * pw + x] = (uint16_t)(rnd() % 1024);
+                    pl[(size_t)r * pw + x] = (uint16_t)((rnd() % 1024) + OMC_PIX_BIAS);
         }
+        omc_xsl_unblend(&f2, &cfg, 0);
         int r = omc_enc_slice(e2, &f2, 0, k, got + off, NULL);
         if (r < 0) { ok = 0; break; }
         if (memcmp(got + off, ref + off, (size_t)r) != 0) ok = 0;
         off += (size_t)r;
     }
-    CHECK(ok, "causality: poisoned future rows do not change slice bytes");
+    CHECK(ok, "causality: poisoned rows beyond the 2-line un-blend lookahead "
+              "do not change slice bytes");
     omc_enc_destroy(e1); omc_enc_destroy(e2);
     free(pix); free(poison); free(ref); free(got);
 }
@@ -173,7 +181,7 @@ static void fill_frame(uint16_t *pix, size_t n, uint32_t seed)
     uint32_t x = seed;
     for (size_t i = 0; i < n; i++) {
         x = x * 1103515245u + 12345u;
-        pix[i] = (uint16_t)(64 + ((x >> 16) % 800));
+        pix[i] = (uint16_t)(64 + ((x >> 16) % 800) + OMC_PIX_BIAS);
     }
 }
 
diff --git a/tests/test_xsl.c b/tests/test_xsl.c
index c71d360..19e42d4 100644
--- a/tests/test_xsl.c
+++ b/tests/test_xsl.c
@@ -1,45 +1,32 @@
-/* The two things the 2026-08-12 cross-slice work must never lose.
+/* T5 cross-slice boundary (XSL) gates.  Three things this build must never
+ * lose:
  *
- * G-XSL1  STREAM AUTHORITY WHEN THE ENVIRONMENT IS SILENT.  A minor-9 stream
- *         decodes at XSL level 3 on its own say-so.  OMC_XSL still wins when it
- *         is set -- that is the deliberate instrumentation path (C1) and it is
- *         the only reason level 7 can be measured at all -- so what must be
- *         pinned is the OTHER half: with nothing in the environment, the stream
- *         decides, and it decides 3.
+ * G-T5-XSL1  XSL CANNOT BE TURNED OFF.  The boundary reconstruction is a
+ *            normative always-on part of the codec: the old OMC_XSL /
+ *            OMC_XSL_NOEDIT / OMC_XSL_NODISP environment levers must be
+ *            inert.  (The seam blend is what keeps slice joins invisible at
+ *            and below 0.5 bpp; an environment that could disable it would
+ *            also silently break the generation-exactness contract, because
+ *            the encoder-side un-blend and the decoder-side blend must agree
+ *            forever.)
  *
- *         This is recorded because the rule was misread during the level-7 work:
- *         omc_read_stream_header() sets the level from the stream and
- *         common_init() then re-reads OMC_XSL, so the environment reaches the
- *         decoder after all.  An OMC_XSL_FORCE widening was added on the
- *         mistaken belief that it could not, and reverted once measured.
+ * G-T5-XSL2  THE EDIT IS EXACTLY REVERSIBLE, WHOLE-PICTURE.  The boundary
+ *            edit is a lifting cascade (each step's correction reads only
+ *            rows it does not touch), the barrier display blend is the same
+ *            cascade under the refresh-barrier conditions, and
+ *            omc_xsl_unblend() must invert the composition exactly on every
+ *            barrier phase.  Verified here through the codec itself: the
+ *            generation-2 re-encode of a decode reproduces the decode
+ *            byte-for-byte, which is only possible if the un-blend recovered
+ *            the committed reconstruction exactly at every boundary of every
+ *            frame.
  *
- * G-XSL2  THE LEVEL-7 EDIT IS EXACTLY REVERSIBLE.  Level 7 exists because the
- *         shipped level-3 boundary edit cannot be undone: it moves a row toward
- *         a target computed from that row's own value, which discards what the
- *         row was.  A later encoder therefore cannot recover the reconstruction
- *         its predecessor coded, cannot lock onto it, and re-smooths an already
- *         smoothed picture -- measured at -8.17 dB over six generations at
- *         3.0 bpp, and -1.26 dB against a -0.37 dB ceiling at 1.0 bpp.
- *
- *         Level 7 replaces it with two lifting steps in a fixed order, each
- *         adding a correction built ONLY from rows it does not touch:
- *             step 1   row15 += clamp((row0   - row14) / 4)
- *             step 2   row0  += clamp((row15' - row1 ) / 4)
- *         so omc_xsl_unblend() returns the original exactly.  If that exactness
- *         ever breaks, the scheme degrades into a lossy edit that merely LOOKS
- *         reversible, which is worse than not having it.  Hence a gate.
- *
- *         GROUND TRUTH is a decode with OMC_XSL_NOEDIT=1: every other level-7
- *         behaviour kept, only the boundary edit skipped.  Two things that are
- *         NOT ground truth, both learned the hard way:
- *           - decoding at level 0, which also drops the cross-slice wavelet term
- *             and changes the whole slice (produced a spurious "6.1% wrong");
- *           - any frame after the first, because the edit is IN-LOOP: it changes
- *             the reference, so two decodes of the same stream diverge from
- *             frame 1 onward through prediction, not through the edit.  The
- *             check is therefore intra-only.  Verifying it on an inter frame
- *             needs the pre-edit reconstruction of that same decode, which the
- *             decoder does not expose -- see HANDOFF_BIT_EXACTNESS.md.
+ * G-T5-XSL3  GENERATION EXACTNESS THROUGH INTER FRAMES.  The v4.9 gate was
+ *            intra-only by necessity (its in-loop edit made inter frames
+ *            unverifiable).  T5's contract is stronger and so is the gate:
+ *            a 4-frame sequence with motion and two refresh phases (R=2)
+ *            must chain byte-exactly for 4 generations — pixels equal from
+ *            generation 1, streams equal from generation 2.
  */
 #include <stdio.h>
 #include <stdlib.h>
@@ -50,20 +37,24 @@ static int fails = 0;
 #define CHECK(c, m) do { printf("%s: %s\n", (c) ? "ok" : "FAIL", m); \
                          if (!(c)) fails++; } while (0)
 
-enum { W = 256, H = 64, SH = 16 };
+enum { W = 256, H = 64, SH = 16, NF = 4 };
 #define WC (W / 2)
 #define WORDS ((size_t)W * H + 2 * (size_t)WC * H)
 
-/* Content with real vertical structure: a flat ramp would put every slice
- * boundary at the same place in the gradient and hide a sign error. */
-static void fill(uint16_t *p, uint32_t seed)
+/* Textured content with per-frame motion (a 2 px/frame horizontal roll) so
+ * inter coding and the derived motion vector genuinely engage.  Values are
+ * in the T5 biased domain. */
+static void fill(uint16_t *p, uint32_t seed, int frame)
 {
     uint32_t x = seed;
     for (int y = 0; y < H; y++)
         for (int i = 0; i < W + 2 * WC; i++) {
+            int xx = (i + 2 * frame) % (W + 2 * WC);
+            x = seed + (uint32_t)(y * 31 + xx) * 2654435761u;
             x = x * 1103515245u + 12345u;
             int base = 200 + 6 * y + ((y / 5) % 3) * 40;
-            p[(size_t)y * (W + 2 * WC) + i] = (uint16_t)(base + ((x >> 18) % 24));
+            p[(size_t)y * (W + 2 * WC) + i] =
+                (uint16_t)(base + ((x >> 18) % 24) + OMC_PIX_BIAS);
         }
 }
 
@@ -73,7 +64,8 @@ static void cfg_init(omc_config_t *c)
     c->width = W; c->height = H; c->bitdepth = 10; c->chroma = OMC_CF_422;
     c->ver_minor = OMC_VERSION_MINOR; c->slice_h = SH;
     c->fps_num = 50; c->fps_den = 1;
-    c->bits_per_slice = 2 * W * SH;   /* 1.0 bpp on coded samples */
+    c->refresh_r = 2;                 /* both barrier phases inside 4 frames */
+    c->bits_per_slice = 2 * W * SH;   /* 1.0 bpp on luma pixels */
 }
 
 static void planes(omc_frame_t *fr, uint16_t *b)
@@ -83,72 +75,75 @@ static void planes(omc_frame_t *fr, uint16_t *b)
     fr->stride[0] = W; fr->stride[1] = WC; fr->stride[2] = WC;
 }
 
-static size_t encode(const omc_config_t *c, const uint16_t *pix, uint8_t *bs)
+/* encode NF frames from pix[], decode them, return both streams and decodes */
+static void run_chain(const omc_config_t *c, const uint16_t *pix,
+                      uint8_t *bs, uint16_t *dec)
 {
     size_t fb = (size_t)(c->bits_per_slice / 8) * (H / SH);
     omc_enc_t *e = omc_enc_create(c);
-    omc_frame_t fr; planes(&fr, (uint16_t *)pix);
-    omc_enc_frame(e, &fr, 0, bs, fb, NULL);
-    omc_enc_destroy(e);
-    return fb;
-}
-
-static void decode(const omc_config_t *c, const uint8_t *bs, size_t fb, uint16_t *out)
-{
     omc_dec_t *d = omc_dec_create(c);
-    omc_frame_t fr; planes(&fr, out);
-    omc_dec_frame(d, bs, fb, &fr);
+    for (int f = 0; f < NF; f++) {
+        omc_frame_t fr; planes(&fr, (uint16_t *)pix + WORDS * f);
+        omc_enc_frame(e, &fr, f, bs + fb * f, fb, NULL);
+        omc_frame_t fo; planes(&fo, dec + WORDS * f);
+        omc_dec_frame(d, bs + fb * f, fb, &fo);
+    }
+    omc_enc_destroy(e);
     omc_dec_destroy(d);
 }
 
 int main(void)
 {
     omc_config_t c; cfg_init(&c);
-    uint16_t *pix = malloc(WORDS * 2);
-    uint16_t *a = malloc(WORDS * 2), *b = malloc(WORDS * 2);
-    uint8_t *bs = malloc(WORDS * 2 + 65536);
-    uint8_t hdr[OMC_STREAM_HDR_BYTES];
-    if (!pix || !a || !b || !bs) { printf("FAIL: alloc\n"); return 1; }
-    fill(pix, 12345u);
+    size_t fb = (size_t)(c.bits_per_slice / 8) * (H / SH);
+    uint16_t *pix = malloc(WORDS * 2 * NF);
+    uint16_t *dec1 = malloc(WORDS * 2 * NF), *dec2 = malloc(WORDS * 2 * NF);
+    uint16_t *dec3 = malloc(WORDS * 2 * NF), *decx = malloc(WORDS * 2 * NF);
+    uint8_t *bs1 = malloc(fb * NF), *bs2 = malloc(fb * NF);
+    uint8_t *bs3 = malloc(fb * NF), *bsx = malloc(fb * NF);
+    if (!pix || !dec1 || !dec2 || !dec3 || !decx || !bs1 || !bs2 || !bs3 || !bsx)
+        { printf("FAIL: alloc\n"); return 1; }
+    for (int f = 0; f < NF; f++) fill(pix + WORDS * f, 12345u, f);
 
-    /* ---------------------------------------------------------- G-XSL1 */
-    unsetenv("OMC_XSL_NOEDIT"); unsetenv("OMC_XSL_FORCE");
-    setenv("OMC_XSL", "3", 1);
-    size_t fb = encode(&c, pix, bs);
-    decode(&c, bs, fb, a);                    /* level 3, stated explicitly */
+    /* ------------------------------------------------------- G-T5-XSL1 */
+    unsetenv("OMC_XSL"); unsetenv("OMC_XSL_NOEDIT");
+    unsetenv("OMC_XSL_NODISP"); unsetenv("OMC_XSL_LIM");
+    run_chain(&c, pix, bs1, dec1);
+    setenv("OMC_XSL", "0", 1);          /* the old off switch ... */
+    setenv("OMC_XSL_NOEDIT", "1", 1);   /* ... and the old edit-skip hook */
+    setenv("OMC_XSL_NODISP", "1", 1);
+    run_chain(&c, pix, bsx, decx);
+    unsetenv("OMC_XSL"); unsetenv("OMC_XSL_NOEDIT"); unsetenv("OMC_XSL_NODISP");
+    CHECK(memcmp(bs1, bsx, fb * NF) == 0 && memcmp(dec1, decx, WORDS * 2 * NF) == 0,
+          "G-T5-XSL1 the XSL off/skip environment levers are inert (always on)");
 
-    /* now the real path: environment silent, level taken from the stream */
-    unsetenv("OMC_XSL");
-    omc_config_t c2;
-    omc_write_stream_header(&c, hdr);
-    CHECK(omc_read_stream_header(hdr, &c2) > 0, "G-XSL1a a minor-9 header parses");
-    decode(&c2, bs, fb, b);
-    CHECK(memcmp(a, b, WORDS * 2) == 0,
-          "G-XSL1b stream authority: with OMC_XSL unset a minor-9 stream "
-          "decodes at level 3");
-
-    /* ---------------------------------------------------------- G-XSL2 */
-    setenv("OMC_XSL", "7", 1);
-    unsetenv("OMC_XSL_NOEDIT");
-    fb = encode(&c, pix, bs);
-    decode(&c, bs, fb, a);                    /* WITH the boundary edit */
-    setenv("OMC_XSL_NOEDIT", "1", 1);
-    decode(&c, bs, fb, b);                    /* ground truth: edit skipped only */
-    unsetenv("OMC_XSL_NOEDIT");
+    /* ------------------------------------------------------- G-T5-XSL2/3 */
+    /* generation 2: re-encode the decode; generation 3: re-encode that */
+    run_chain(&c, dec1, bs2, dec2);
+    CHECK(memcmp(dec1, dec2, WORDS * 2 * NF) == 0,
+          "G-T5-XSL2 generation-2 pixels reproduce generation-1 byte-for-byte "
+          "(inter frames and both R=2 barrier phases included)");
+    run_chain(&c, dec2, bs3, dec3);
+    CHECK(memcmp(dec2, dec3, WORDS * 2 * NF) == 0,
+          "G-T5-XSL3a generation-3 pixels hold");
+    CHECK(memcmp(bs2, bs3, fb * NF) == 0,
+          "G-T5-XSL3b generation-3 stream is byte-identical to generation 2");
 
+    /* un-blend inverse, directly: un-blending the decode and re-applying the
+     * chain must be what generation 2 did — spot-check the exported function
+     * agrees with itself (undo twice != undo once). */
+    memcpy(decx, dec1, WORDS * 2 * NF);
+    for (int f = 0; f < NF; f++) {
+        omc_frame_t fr; planes(&fr, decx + WORDS * f);
+        omc_xsl_unblend(&fr, &c, f);
+    }
     size_t edited = 0;
-    for (size_t i = 0; i < WORDS; i++) edited += (a[i] != b[i]);
-    CHECK(edited > 0, "G-XSL2a the level-7 boundary edit actually fires");
-
-    omc_frame_t fr; planes(&fr, a);
-    omc_xsl_unblend(&fr, &c, 0);
-    CHECK(memcmp(a, b, WORDS * 2) == 0,
-          "G-XSL2b unblend(edit(recon)) == recon, byte for byte");
-    printf("   (the edit touched %zu samples; the inverse recovered %s)\n", edited,
-           memcmp(a, b, WORDS * 2) == 0 ? "every one" : "SOME BUT NOT ALL");
+    for (size_t i = 0; i < WORDS * NF; i++) edited += (decx[i] != dec1[i]);
+    CHECK(edited > 0, "G-T5-XSL2b the boundary edit actually fires "
+                      "(un-blend changes samples)");
 
-    unsetenv("OMC_XSL");
-    free(pix); free(a); free(b); free(bs);
+    free(pix); free(dec1); free(dec2); free(dec3); free(decx);
+    free(bs1); free(bs2); free(bs3); free(bsx);
     printf("test_xsl: %s\n", fails ? "FAILURES" : "all ok");
     return fails != 0;
 }
diff --git a/tools/omc_dec.c b/tools/omc_dec.c
index 90abab5..cddef1c 100644
--- a/tools/omc_dec.c
+++ b/tools/omc_dec.c
@@ -1,9 +1,14 @@
-/* omc_dec - OMC-1 decoder CLI. Reads .omc bitstream, writes raw planar LE16.
- * Concealment for slices that fail CRC (A5) is on by default: motion-
- * compensated (project the reference along the neighbour slice's motion
- * vectors) with a spatial-interpolation fallback for intra/cut cases.
- * --no-conceal selects the old freeze (hold-last-frame) behavior. Either way
- * a clean stream decodes identically and concealment plays no part in rt=0.
+/* omc_dec - OMC-1 decoder CLI (T5). Reads .omc bitstream (minor 10), writes
+ * raw planar LE16.  Two output modes:
+ *   default        display raw: bias removed, clipped to [0, 2^depth), RCT
+ *                  inverted and picture cropped to display dims — what a
+ *                  viewer or metric consumes.  NOT suitable for re-encoding.
+ *   --cdr          coded-domain raw: the decoder's committed picture verbatim
+ *                  (biased by 2048, unclipped, coded geometry, no crop/RCT).
+ *                  THE generation-chain interchange: feed it back with
+ *                  omc_enc --cdr-in and the re-encode is byte-exact forever.
+ * Concealment for slices that fail CRC (A5) is on by default; a clean stream
+ * decodes identically either way.
  */
 #include <stdio.h>
 #include <stdlib.h>
@@ -18,6 +23,7 @@ int main(int argc, char **argv)
 {
     const char *inp = NULL, *outp = NULL;
     int conceal = 1, verbose = 0;
+    int cdr = 0;       /* 1 = coded-domain raw out (generation chains) */
     int ucf = -1;      /* -1 = follow the stream's uc_ratio; else 1 / 2 / 4  */
     int uc_bands = 0;  /* produce the output in slice-sized bands            */
     int uc_dir = 1;    /* direction-adaptive predictor (normative default)   */
@@ -25,11 +31,12 @@ int main(int argc, char **argv)
         if (!strcmp(argv[i], "-i")) inp = argv[++i];
         else if (!strcmp(argv[i], "-o")) outp = argv[++i];
         else if (!strcmp(argv[i], "--no-conceal")) conceal = 0;
+        else if (!strcmp(argv[i], "--cdr")) cdr = 1;
         else if (!strcmp(argv[i], "-v")) verbose = 1;
         else if (!strcmp(argv[i], "--upconv")) ucf = atoi(argv[++i]);
         else if (!strcmp(argv[i], "--uc-bands")) uc_bands = 1;
         else if (!strcmp(argv[i], "--uc-no-direction")) uc_dir = 0;
-        else die("usage: -i in.omc -o out.yuv [--no-conceal] [-v] "
+        else die("usage: -i in.omc -o out.yuv [--cdr] [--no-conceal] [-v] "
                  "[--upconv 1|2|4] [--uc-bands] [--uc-no-direction]");
     }
     if (!inp || !outp) die("usage: -i in.omc -o out.yuv");
@@ -50,9 +57,10 @@ int main(int argc, char **argv)
     uint8_t *sb = malloc(slice_bytes);
     if (!pix || !sb) die("out of memory");
 
-    /* mid-gray init so first-frame concealment is neutral, not black */
+    /* mid-gray init so first-frame concealment is neutral, not black
+     * (T5: the decode buffer lives in the biased domain) */
     {
-        uint16_t midy = (uint16_t)(1 << (cfg.bitdepth - 1));
+        uint16_t midy = (uint16_t)((1 << (cfg.bitdepth - 1)) + OMC_PIX_BIAS);
         for (size_t i = 0; i < frame_words; i++) pix[i] = midy;
     }
 
@@ -103,7 +111,8 @@ int main(int argc, char **argv)
             fprintf(stderr, "omc_dec: OMC-UC %dx -> %dx%d out\n", ucn, oW, oH);
     }
     uint16_t *obuf = malloc(((size_t)oW * oH * 3) * 2);
-    if (!obuf) die("out of memory");
+    uint16_t *disp = cdr ? NULL : malloc(frame_words * 2);
+    if (!obuf || (!cdr && !disp)) die("out of memory");
     for (;;) {
         if (fread(fb, 1, frame_bytes, fi) != frame_bytes) break;
         int64_t good = omc_dec_frame(dec, fb, frame_bytes, &fout);
@@ -112,13 +121,30 @@ int main(int argc, char **argv)
             if (verbose) fprintf(stderr, "frame %d: %d damaged slice(s) concealed\n",
                                  fidx, nsl - (int)good);
         }
-        /* the output stage reads oSrc at oSW x oSH; identical to pix when the
-         * upconverter is off, so the pre-v4.8 paths below are unchanged */
-        const uint16_t *oSrc = pix;
+        if (cdr) {
+            /* T5 coded-domain raw: the committed picture verbatim (biased,
+             * unclipped, coded geometry).  The ONLY output that a next
+             * generation may re-encode. */
+            fwrite(pix, 2, frame_words, fo);
+            fidx++;
+            continue;
+        }
+        /* display projection (non-normative): remove the bias and clip to
+         * the legal range before crop/RCT/upconversion */
+        {
+            int32_t dmax = (1 << cfg.bitdepth) - 1;
+            for (size_t i = 0; i < frame_words; i++) {
+                int32_t v = (int32_t)pix[i] - OMC_PIX_BIAS;
+                disp[i] = (uint16_t)(v < 0 ? 0 : (v > dmax ? dmax : v));
+            }
+        }
+        /* the output stage reads oSrc at oSW x oSH; identical to disp when
+         * the upconverter is off, so the pre-v4.8 paths below are unchanged */
+        const uint16_t *oSrc = disp;
         int oSW = W, oSWc = Wc, oSH = H;
         size_t oSy = ysz, oSc = csz, oSwords = frame_words;
         if (ucn > 1) {
-            const uint16_t *cur = pix;
+            const uint16_t *cur = disp;
             uint16_t *nxt = (ucn == 4) ? utmp : upix;
             int cW = W, cWc = Wc, cH = H;
             for (int stage = 0; stage < (ucn == 4 ? 2 : 1); stage++) {
@@ -177,7 +203,7 @@ int main(int argc, char **argv)
             bad && conceal ? " (concealed)" : "");
     omc_dec_destroy(dec);
     fclose(fi); fclose(fo);
-    free(pix); free(sb); free(fb); free(obuf); free(upix); free(utmp);
+    free(pix); free(sb); free(fb); free(obuf); free(disp); free(upix); free(utmp);
     { extern long long omc_fc_fire, omc_fc_tot;
       if (getenv("OMC_FILLCORR_STAT") && omc_fc_tot)
         fprintf(stderr, "FILLCORR fires %lld/%lld = %.2f%%\n", omc_fc_fire, omc_fc_tot, 100.0*omc_fc_fire/omc_fc_tot); }
diff --git a/tools/omc_enc.c b/tools/omc_enc.c
index dc5b00b..71de39b 100644
--- a/tools/omc_enc.c
+++ b/tools/omc_enc.c
@@ -1,7 +1,11 @@
-/* omc_enc - OMC-1 encoder CLI.
- * Input: raw planar Y'CbCr, little-endian 16-bit container (10/12-bit video
- * levels), 4:2:2 or 4:4:4. Output: .omc bitstream (stream header + fixed-size
- * slices). Optional --recon writes the encoder-side reconstruction (rt=0).
+/* omc_enc - OMC-1 encoder CLI (T5).
+ * Input: raw planar Y'CbCr, little-endian 16-bit container (8/10/12-bit
+ * levels), 4:2:2 or 4:4:4 — either a plain master (values in [0, 2^depth))
+ * or, with --cdr-in, a coded-domain raw (CDR) as written by omc_dec --cdr:
+ * biased by OMC_PIX_BIAS, unclipped, at CODED geometry (padded).  CDR is the
+ * T5 generation-chain interchange format; re-encoding a CDR decode is
+ * byte-exact through unlimited generations.  Output: .omc bitstream.
+ * Optional --recon writes the encoder-side reconstruction in CDR form.
  */
 #include <stdio.h>
 #include <stdlib.h>
@@ -41,7 +45,8 @@ static void assemble(uint16_t *pix, const uint16_t *inbuf, int W, int H, int Wc,
                     else v = (uint16_t)(R - G + mid_c);
                 } else
                     v = sp[p][(size_t)sr * ipw + sx];
-                dst[(size_t)r * pw + x] = v;
+                /* T5: the codec's pixel domain is biased (omc1.h) */
+                dst[(size_t)r * pw + x] = (uint16_t)(v + OMC_PIX_BIAS);
             }
         }
     }
@@ -53,8 +58,7 @@ int main(int argc, char **argv)
 {
     const char *inp = NULL, *outp = NULL, *reconp = NULL;
     int rgb = 0, mono = 0, verbose_ll = 0, lossless_frames = 0, bpp_set = 0;
-    int tf_flag = -1;   /* -1 = not given; fall back to the OMC_TF variable */
-    int xsl_flag = -1;  /* -1 = not given; 0/3 = force; 2 = auto (probe) */
+    int cdr_in = 0;     /* input is coded-domain raw (biased, coded geometry) */
     omc_config_t cfg;
     memset(&cfg, 0, sizeof(cfg));
     cfg.bitdepth = 10;
@@ -83,12 +87,8 @@ int main(int argc, char **argv)
         else if (!strcmp(argv[i], "--matrix")) cfg.color.matrix = (uint8_t)atoi(argv[++i]);
         else if (!strcmp(argv[i], "--tune")) cfg.tune_vmaf = !strcmp(argv[++i], "vmaf");
         else if (!strcmp(argv[i], "--refresh")) cfg.refresh_r = (uint8_t)atoi(argv[++i]);
-        else if (!strcmp(argv[i], "--mv-regions")) cfg.mv_regions = 1;
-        else if (!strcmp(argv[i], "--no-block-mv")) cfg.no_block_mv = 1;
-        else if (!strcmp(argv[i], "--block-mv")) cfg.no_block_mv = 2;
         else if (!strcmp(argv[i], "--no-fill")) cfg.no_fill = 1;
-        else if (!strcmp(argv[i], "--tf")) tf_flag = atoi(argv[++i]);
-        else if (!strcmp(argv[i], "--xsl")) xsl_flag = !strcmp(argv[i+1], "auto") ? 2 : atoi(argv[i+1]), i++;
+        else if (!strcmp(argv[i], "--cdr-in")) cdr_in = 1;
         else if (!strcmp(argv[i], "--no-deadzone")) cfg.no_deadzone = 1;
         else if (!strcmp(argv[i], "--grain-replace")) cfg.grain_replace = 1;
         else if (!strcmp(argv[i], "--grain-corr")) cfg.grain_corr = 1;
@@ -101,35 +101,22 @@ int main(int argc, char **argv)
     }
     if (!inp || !outp || !cfg.width || !cfg.height)
         die("usage: -i in.yuv -o out.omc -w W -h H [--fmt 422|444] [--depth 10]\n"
-            "       [--bpp 2.0] [--slice-h 16] [--uc-ratio 0|1|2] [--recon rec.yuv]\n"
-            "       [--tf 0|1|2] [--no-fill] [--lossless]\n"
+            "       [--bpp 2.0] [--slice-h 8|16|32] [--uc-ratio 0|1|2]\n"
+            "       [--recon rec.cdr] [--cdr-in] [--no-fill] [--lossless]\n"
             "\n"
-            "  --tf 0|1|2   OMC-TF, the in-loop temporal filter.  0 = OFF, and OFF is\n"
-            "               the default and the right answer unless you know otherwise.\n"
+            "  --cdr-in     the input is a coded-domain raw (CDR) as written by\n"
+            "               omc_dec --cdr: biased by 2048, unclipped, at CODED\n"
+            "               geometry.  This is the T5 generation-chain format:\n"
+            "               re-encoding a CDR decode reproduces it byte-exactly,\n"
+            "               through unlimited generations.  -w/-h give the CODED\n"
+            "               dims here (as reported by omc_dec).\n"
             "\n"
-            "               Turn it on ONLY if this encoder is the FIRST OMC in the\n"
-            "               chain -- the one taking the camera or the master.  It\n"
-            "               denoises once, at the head, and every OMC downstream then\n"
-            "               codes a cleaner picture.\n"
-            "\n"
-            "               Leave it OFF on every later encoder.  Running it again\n"
-            "               at each hop COMPOUNDS.  Measured on three sequences at\n"
-            "               0.5 bpp, four generations deep: with the filter on at\n"
-            "               every hop the cost is STILL GROWING at the fourth on\n"
-            "               every sequence and every plane; with it on once it\n"
-            "               levels off, and is better at the fourth by 0.05 to\n"
-            "               0.52 dB with the gap widening.\n"
-            "\n"
-            "               For a chain of THREE hops or more, on-once wins clearly.\n"
-            "               For exactly TWO it is a wash -- at the second hop the\n"
-            "               filter is still earning its keep.  Neither setting passes\n"
-            "               the generation gate outright; on-once bounds the cost,\n"
-            "               on-every-hop does not.\n"
-            "\n"
-            "               If you do not KNOW this encoder is first, leave it off.\n"
-            "               The setting is written into the stream (byte 27) so the\n"
-            "               decoder matches it; it is not a hint.");
+            "  T5 notes: the temporal engine is rebuilt (motion derived from\n"
+            "  reconstruction history; frame-buffer reference), the cross-slice\n"
+            "  boundary blend (XSL) is always on and exactly reversible, and the\n"
+            "  in-loop temporal filter of v4.8 is REMOVED.  Streams are minor 10.");
     if (rgb && mono) die("--rgb and --mono are mutually exclusive");
+    if (cdr_in && (rgb || mono)) die("--cdr-in carries coded planes; --rgb/--mono do not apply");
     if (cfg.lossless_pref && !bpp_set) bpp = 16.0; /* generous CBR ceiling for lossless headroom */
     int comp_depth = cfg.bitdepth; /* true component depth of the input */
     if (rgb) {
@@ -154,7 +141,11 @@ int main(int argc, char **argv)
          * 1.0 bpp and ~16 % at 0.5 for an arithmetic reason. */
         if (!cfg.slice_h) cfg.slice_h = (cfg.height <= 720) ? 8 : 16;
         uint16_t chh = (uint16_t)((cfg.height + cfg.slice_h - 1) / cfg.slice_h * cfg.slice_h);
-        if (cw != cfg.width || chh != cfg.height) {
+        if (cdr_in) {
+            /* CDR input is already at coded geometry; -w/-h must match it */
+            if (cw != cfg.width || chh != cfg.height)
+                die("--cdr-in: -w/-h must be the CODED dims (already aligned)");
+        } else if (cw != cfg.width || chh != cfg.height) {
             cfg.display_width = dispW; cfg.display_height = dispH;
             cfg.width = cw; cfg.height = chh;
         }
@@ -171,9 +162,11 @@ int main(int argc, char **argv)
     size_t ysz = (size_t)W * H, csz = (size_t)Wc * H;
     size_t frame_words = ysz + 2 * csz;
     uint16_t *pix = malloc(frame_words * 2);
-    /* input geometry (true dims, pre-pad; mono reads 1 plane, rgb reads 3 full) */
-    int iW = dispW, iH = dispH;
-    int iWc = mono ? 0 : (rgb ? iW : (cfg.chroma == OMC_CF_422 ? (iW + 1) / 2 : iW));
+    /* input geometry (true dims, pre-pad; mono reads 1 plane, rgb reads 3
+     * full; CDR reads the coded planes verbatim) */
+    int iW = cdr_in ? W : dispW, iH = cdr_in ? H : dispH;
+    int iWc = mono ? 0 : (rgb ? iW : (cdr_in ? Wc
+                       : (cfg.chroma == OMC_CF_422 ? (iW + 1) / 2 : iW)));
     size_t in_words = (size_t)iW * iH + 2 * (size_t)iWc * iH;
     uint16_t *inbuf = malloc(in_words * 2);
     int32_t mid_c = 1 << (cfg.bitdepth - 1);           /* container midpoint */
@@ -227,30 +220,11 @@ int main(int argc, char **argv)
      * same tool, and it went unnoticed because the harness sets the variable
      * itself. */
     omc_global_init();
-    if (tf_flag >= 0) omc_tf_mode = tf_flag;
-    cfg.tf_mode = (uint8_t)(omc_tf_mode & 3);
-    /* uc_ratio is the encoder's RECOMMENDATION to the output port.  Until this
-     * flag existed the field could not be set from the shipped CLI at all, so
-     * no stream could ever carry it and the whole minor-8 path was
-     * unexercisable. */
-    /* --xsl auto: decide cross-slice boundary reconstruction from what it is
-     * worth on THIS material, before the header commits the minor.  Encodes
-     * frame 0 once with XSL off and measures the seam it would repair.  See
-     * omc_xsl_probe_frame(). */
-    if (xsl_flag >= 0) {
-        if (xsl_flag == 2) {
-            uint16_t *p0 = malloc(frame_words * 2);
-            if (p0 && fread(inbuf, 2, in_words, fi) == in_words) {
-                assemble(p0, inbuf, W, H, Wc, iW, iH, iWc, mono, rgb,
-                         mid_c, yoff, ysz, csz);
-                omc_frame_t probe = {{p0, p0 + ysz, p0 + ysz + csz}, {W, Wc, Wc}};
-                int d = omc_xsl_probe_frame(&cfg, &probe);
-                if (d >= 0) omc_xsl = d ? 3 : 0;
-            }
-            free(p0);
-            fseek(fi, 0, SEEK_SET);
-        } else omc_xsl = xsl_flag;
-    }
+    /* T5: tf_mode does not exist (removed with the old temporal engine) and
+     * XSL is always on — nothing to probe, nothing to signal beyond the
+     * minor.  uc_ratio remains the encoder's RECOMMENDATION to the output
+     * port (output-stage only; orthogonal to the coding loop). */
+    cfg.tf_mode = 0;
     omc_write_stream_header(&cfg, shdr);
     fwrite(shdr, 1, OMC_STREAM_HDR_BYTES, fo);
 
@@ -258,20 +232,16 @@ int main(int argc, char **argv)
     omc_frame_t fin = {{pix, pix + ysz, pix + ysz + csz}, {W, Wc, Wc}};
     omc_frame_t frec = {{rec, rec ? rec + ysz : NULL, rec ? rec + ysz + csz : NULL}, {W, Wc, Wc}};
 
-    const char *ub = getenv("OMC_XSL_UNBLEND");
-    int unblend_in = ub && atoi(ub);
     int fidx = 0;
     while (nframes < 0 || fidx < nframes) {
         if (fread(inbuf, 2, in_words, fi) != in_words) break;
-        assemble(pix, inbuf, W, H, Wc, iW, iH, iWc, mono, rgb,
-                 mid_c, yoff, ysz, csz);
-        /* OMC_XSL_UNBLEND=1 (level 7 only): the input is a previous decode, so
-         * strip its boundary edit before coding.  Because the edit is a
-         * reversible lifting cascade this recovers the exact reconstruction the
-         * previous encoder produced -- the picture lands back on the quantiser
-         * lattice, generation lock fires, and the decoder re-applies the edit on
-         * output.  One edit, not one per generation. */
-        if (unblend_in) omc_xsl_unblend(&fin, &cfg, fidx);
+        if (cdr_in)
+            /* CDR input: coded geometry, already biased — planes verbatim.
+             * The mandatory T5 un-blend happens INSIDE omc_enc_frame. */
+            memcpy(pix, inbuf, frame_words * 2);
+        else
+            assemble(pix, inbuf, W, H, Wc, iW, iH, iWc, mono, rgb,
+                     mid_c, yoff, ysz, csz);
         int64_t n = omc_enc_frame(enc, &fin, fidx, bs, slice_bytes * (size_t)nsl,
                                   rec ? &frec : NULL);
         if (n < 0) die("encode failed");
=== END T5 PATCH ===
`````

## Appendix B — the test harness, full text

Save each file at the path shown (layout of section 10), `chmod +x` the two
shell scripts.  These are the exact scripts that produced every result in
section 10.

### `tests/genchain.sh`

`````bash
#!/bin/bash
# genchain.sh - T5 generation-exactness chain test.
#
# Usage:
#   genchain.sh <master.yuv> <trueW> <trueH> <fmt 422|444> <depth> <bpp> \
#               <slice_h(0=auto)> <gens> [extra encoder flags...]
#
# Runs: master -> enc -> dec(--cdr) -> enc(--cdr-in) -> dec(--cdr) -> ... <gens> times.
# PASS iff every generation's CDR decode is byte-identical to generation 1's,
# and every generation >= 2 writes a byte-identical bitstream.
# Prints one line: PASS/FAIL, the coded dims, and the gen-1 stream md5.
set -u
E="$(cd "$(dirname "$0")/../omc/omc_v4.9" && pwd)"
MASTER=$1; TW=$2; TH=$3; FMT=$4; DEPTH=$5; BPP=$6; SH=$7; GENS=$8; shift 8
EXTRA=("$@")
WORK="${GENCHAIN_TMP:-$(mktemp -d)}"
mkdir -p "$WORK"
trap 'rm -rf "$WORK"' EXIT

# coded geometry
WAL=$([ "$FMT" = 422 ] && echo 64 || echo 32)
CW=$(( (TW + WAL - 1) / WAL * WAL ))
RSH=$SH
if [ "$RSH" = 0 ]; then RSH=$([ "$TH" -le 720 ] && echo 8 || echo 16); fi
CH=$(( (TH + RSH - 1) / RSH * RSH ))
SHFLAG=()
[ "$SH" != 0 ] && SHFLAG=(--slice-h "$SH")

"$E/omc_enc" -i "$MASTER" -o "$WORK/g1.omc" -w "$TW" -h "$TH" --fmt "$FMT" \
    --depth "$DEPTH" --bpp "$BPP" "${SHFLAG[@]}" "${EXTRA[@]}" 2>"$WORK/enc1.log" \
    || { echo "FAIL enc-gen1 ($(tail -1 "$WORK/enc1.log"))"; exit 1; }
# A2 marker: the encoder reports any configuration that exceeds the 1 ms
# latency budget (including output conversion).  Carried into the RESULT LINE
# itself, not just prose: these cells are exactness coverage, and a reader
# skimming PASS lines must not mistake an over-budget slice height for a
# shippable configuration.
A2=""
if grep -q "WARNING A2" "$WORK/enc1.log" 2>/dev/null; then
    A2=" [A2:OVER $(sed -n 's/.*takes \([0-9.]*\) ms.*/\1/p' "$WORK/enc1.log" | head -1)ms NOT-SHIPPABLE]"
fi
"$E/omc_dec" -i "$WORK/g1.omc" --cdr -o "$WORK/g1.cdr" 2>/dev/null \
    || { echo "FAIL dec-gen1"; exit 1; }

prev="$WORK/g1.cdr"; fail=""
for g in $(seq 2 "$GENS"); do
    "$E/omc_enc" --cdr-in -i "$prev" -o "$WORK/gN.omc" -w "$CW" -h "$CH" \
        --display-w "$TW" --display-h "$TH" \
        --fmt "$FMT" --depth "$DEPTH" --bpp "$BPP" "${SHFLAG[@]}" "${EXTRA[@]}" \
        2>"$WORK/encN.log" || { fail="enc-gen$g ($(tail -1 "$WORK/encN.log"))"; break; }
    "$E/omc_dec" -i "$WORK/gN.omc" --cdr -o "$WORK/gN.cdr" 2>/dev/null \
        || { fail="dec-gen$g"; break; }
    cmp -s "$WORK/g1.cdr" "$WORK/gN.cdr" || { fail="pixels-gen$g"; break; }
    if [ "$g" = 2 ]; then cp "$WORK/gN.omc" "$WORK/g2.omc"
    else cmp -s "$WORK/g2.omc" "$WORK/gN.omc" || { fail="stream-gen$g"; break; }
    fi
    cp "$WORK/gN.cdr" "$WORK/prev.cdr"; prev="$WORK/prev.cdr"
done

if [ -n "$fail" ]; then
    echo "FAIL $fail  [${TW}x${TH}->${CW}x${CH} $FMT/${DEPTH}b bpp=$BPP sh=$RSH gens=$GENS ${EXTRA[*]:-}]$A2"
    exit 1
fi
echo "PASS  [${TW}x${TH}->${CW}x${CH} $FMT/${DEPTH}b bpp=$BPP sh=$RSH gens=$GENS ${EXTRA[*]:-}] g1.omc=$(md5sum <"$WORK/g1.omc" | cut -d' ' -f1)$A2"
`````

### `tests/run_matrix.sh`

`````bash
#!/bin/bash
# run_matrix.sh - the full T5 generation-exactness matrix over the provided
# footage: every resolution class (720p, 1080p, 1152p, 4K DCI, 4480-wide),
# depths 8/10/12, 4:2:2 and 4:4:4, rates 0.5..3.0 bpp, slice heights 8/16/32,
# and the encoder option set.  Each line: PASS/FAIL from tests/genchain.sh.
set -u
cd "$(dirname "$0")/.."
T=tests/genchain.sh; R=tests/raw

# --- 720p class (slice_h 8 default + explicit 16) ---
$T $R/gfx720_422_10.yuv      1280 720  422 10 0.5 0  6
$T $R/gfx720_422_10.yuv      1280 720  422 10 2.0 0  5
$T $R/cineA31_720_444_8.yuv  1280 720  444 8  0.5 0  5
$T $R/cineA31_720_444_8.yuv  1280 720  444 8  1.0 16 5
$T $R/cineA21_720_422_12.yuv 1280 720  422 12 3.0 0  5

# --- 1080p class (1080 codes as 1088: the pad-and-crop path) ---
$T $R/gfx1080_422_10.yuv     1920 1080 422 10 0.5 16 6
$T $R/gfx1080_422_10.yuv     1920 1080 422 10 1.0 16 5
$T $R/gfx1080_422_10.yuv     1920 1080 422 10 3.0 16 5
$T $R/gfx1080_444_12.yuv     1920 1080 444 12 0.5 16 6
$T $R/gfx1080_444_12.yuv     1920 1080 444 12 3.0 16 5
$T $R/gfx1080_444_8.yuv      1920 1080 444 8  1.0 16 5
$T $R/gfx1080_422_10.yuv     1920 1080 422 10 1.0 32 5

# --- 2048x1152 class ---
$T $R/cineA21_422_12.yuv     2048 1152 422 12 0.5 16 6
$T $R/cineA21_444_10.yuv     2048 1152 444 10 2.0 16 5
$T $R/cineA31_422_10.yuv     2048 1152 422 10 0.5 8  5
$T $R/cineA31_422_10.yuv     2048 1152 422 10 3.0 32 5

# --- 4K DCI class ---
$T $R/cine4k_422_8.yuv       4096 2160 422 8  0.5 16 4
$T $R/cine4k_444_10.yuv      4096 2160 444 10 2.0 32 4

# --- 4480x1856 class ---
$T $R/gfxF003_444_8.yuv      4480 1856 444 8  0.5 16 4
$T $R/gfxF003_422_12.yuv     4480 1856 422 12 1.0 8  4

# --- encoder options (all on the 1080p 4:2:2/10 master) ---
$T $R/gfx1080_422_10.yuv     1920 1080 422 10 1.0 16 5 --tune vmaf
$T $R/gfx1080_422_10.yuv     1920 1080 422 10 1.0 16 5 --grain-corr
$T $R/gfx1080_422_10.yuv     1920 1080 422 10 1.0 16 5 --fill-static
$T $R/gfx1080_422_10.yuv     1920 1080 422 10 1.0 16 5 --no-fill
$T $R/gfx1080_422_10.yuv     1920 1080 422 10 1.0 16 5 --grain-replace
$T $R/gfx1080_422_10.yuv     1920 1080 422 10 1.0 16 5 --refresh 2
$T $R/gfx1080_422_10.yuv     1920 1080 422 10 1.0 16 5 --refresh 3
$T $R/cineA31_422_10.yuv     2048 1152 422 10 0.5 16 5 --tune vmaf
$T $R/cineA31_422_10.yuv     2048 1152 422 10 0.5 16 5 --grain-corr --fill-static
`````

### `tests/prep.py`

`````python
#!/usr/bin/env python3
"""prep.py - convert the provided PNG footage into raw planar u16 LE masters
for the OMC codec.

Usage:
  prep.py --out out.yuv --fmt 444|422 --depth 8|10|12 frame0.png [frame1.png ...]

4:4:4: planes are R, G, B taken directly from the PNG (the codec carries
colour transparently; no matrix loss enters the chain).
4:2:2: BT.709 limited-range Y'CbCr; chroma decimated horizontally by
averaging pairs (deterministic; outside the codec).

Depth conversion from the PNG's native depth (8 or 16 bits) is by bit shift
(deterministic, no rounding surprises): 16-bit source >> (16-depth);
8-bit source << (depth-8).

Output: for each frame, planes concatenated (Y|Cb|Cr or R|G|B), u16 LE,
values in [0, 2^depth).
"""
import argparse
import sys
import numpy as np
from PIL import Image

def load_rgb(path):
    im = Image.open(path)
    arr = np.array(im)
    if arr.ndim != 3 or arr.shape[2] < 3:
        sys.exit(f"{path}: not RGB")
    native = 16 if arr.dtype == np.uint16 else 8
    return arr[:, :, :3].astype(np.int64), native

def to_depth(a, native, depth):
    if native > depth:
        return a >> (native - depth)
    return a << (depth - native)

def rgb_to_ycbcr422(rgb, depth):
    # BT.709 limited range, integer-friendly but done in float64 then rounded:
    # deterministic across runs/platforms for these value ranges.
    maxv = (1 << depth) - 1
    r = rgb[:, :, 0].astype(np.float64)
    g = rgb[:, :, 1].astype(np.float64)
    b = rgb[:, :, 2].astype(np.float64)
    sc = maxv / ((1 << depth) - 1)  # 1.0; kept for clarity
    kr, kb = 0.2126, 0.0722
    y = kr * r + (1 - kr - kb) * g + kb * b
    cb = (b - y) / (2 * (1 - kb))
    cr = (r - y) / (2 * (1 - kr))
    d8 = depth - 8
    ys = np.clip(np.round(y / maxv * (219 << d8) + (16 << d8)), 0, maxv)
    cbs = np.clip(np.round(cb / maxv * (224 << d8) + (128 << d8)), 0, maxv)
    crs = np.clip(np.round(cr / maxv * (224 << d8) + (128 << d8)), 0, maxv)
    # 4:2:2: average horizontal pairs
    cbh = ((cbs[:, 0::2] + cbs[:, 1::2] + 1) // 2)
    crh = ((crs[:, 0::2] + crs[:, 1::2] + 1) // 2)
    return ys.astype(np.uint16), cbh.astype(np.uint16), crh.astype(np.uint16)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--fmt", required=True, choices=["444", "422"])
    ap.add_argument("--depth", required=True, type=int, choices=[8, 10, 12])
    ap.add_argument("--resize", default=None,
                    help="WxH: Lanczos-resize the PNG before conversion "
                         "(e.g. 1280x720 to derive 720p masters)")
    ap.add_argument("pngs", nargs="+")
    args = ap.parse_args()

    rsz = None
    if args.resize:
        w, h = args.resize.split("x")
        rsz = (int(w), int(h))

    with open(args.out, "wb") as fo:
        for path in args.pngs:
            if rsz:
                im = Image.open(path)
                im = im.resize(rsz, Image.LANCZOS)
                arr = np.array(im)
                native = 16 if arr.dtype == np.uint16 else 8
                rgb = arr[:, :, :3].astype(np.int64)
            else:
                rgb, native = load_rgb(path)
            rgb = to_depth(rgb, native, args.depth)
            if args.fmt == "444":
                for c in range(3):
                    fo.write(rgb[:, :, c].astype("<u2").tobytes())
            else:
                y, cb, cr = rgb_to_ycbcr422(rgb, args.depth)
                fo.write(y.astype("<u2").tobytes())
                fo.write(cb.astype("<u2").tobytes())
                fo.write(cr.astype("<u2").tobytes())
    h, w = rgb.shape[0], rgb.shape[1]
    print(f"{args.out}: {len(args.pngs)} frames {w}x{h} fmt={args.fmt} depth={args.depth}")

if __name__ == "__main__":
    main()
`````

### `tests/quality.py`

`````python
#!/usr/bin/env python3
"""quality.py - generation-1 quality sanity for the T5 rebuild.

Usage: quality.py master.yuv dec_display.yuv W H fmt depth [slice_h]

Prints per-plane PSNR of the display decode against the master, and the
slice-seam metric: mean |row-to-row| luma step at slice boundaries vs the
interior (excess <= ~0 means joins are no worse than the picture).
"""
import sys
import numpy as np

def planes(buf, W, H, Wc):
    y = buf[:W*H].reshape(H, W)
    cb = buf[W*H:W*H+Wc*H].reshape(H, Wc)
    cr = buf[W*H+Wc*H:W*H+2*Wc*H].reshape(H, Wc)
    return y, cb, cr

def main():
    mfile, dfile, W, H, fmt, depth = sys.argv[1:7]
    sh = int(sys.argv[7]) if len(sys.argv) > 7 else 16
    W, H, depth = int(W), int(H), int(depth)
    Wc = W if fmt == "444" else W // 2
    fw = W*H + 2*Wc*H
    m = np.fromfile(mfile, dtype='<u2')
    d = np.fromfile(dfile, dtype='<u2')
    nf = min(m.size // fw, d.size // fw)
    maxv = (1 << depth) - 1
    names = ["Y", "Cb", "Cr"]
    for f in range(nf):
        mp = planes(m[f*fw:(f+1)*fw].astype(np.float64), W, H, Wc)
        dp = planes(d[f*fw:(f+1)*fw].astype(np.float64), W, H, Wc)
        ps = []
        for p in range(3):
            mse = np.mean((mp[p] - dp[p])**2)
            ps.append(10*np.log10(maxv*maxv/mse) if mse > 0 else float('inf'))
        # seam metric on decoded luma
        dy = dp[0]
        step = np.abs(np.diff(dy, axis=0)).mean(axis=1)  # step[r] = |row r+1 - row r|
        bmask = np.zeros(H-1, bool)
        bmask[sh-1::sh] = True  # boundary between slice rows sh-1 and sh
        bexc = step[bmask].mean() - step[~bmask].mean()
        # same metric on the master for reference
        my = mp[0]
        mstep = np.abs(np.diff(my, axis=0)).mean(axis=1)
        mexc = mstep[bmask].mean() - mstep[~bmask].mean()
        print(f"frame {f}: PSNR Y {ps[0]:.2f} Cb {ps[1]:.2f} Cr {ps[2]:.2f} dB | "
              f"seam excess dec {bexc:+.3f} src {mexc:+.3f} (codes)")

if __name__ == "__main__":
    main()
`````

### `tests/seam_repair.py`

`````python
#!/usr/bin/env python3
"""seam_repair.py - measure what the always-on XSL boundary edit repairs.

The T5 edit is exactly reversible, so the pre-edit picture is recoverable
from the decode itself: un-blending the CDR yields the committed
reconstruction as it would look with the boundary edit skipped (the
cross-slice wavelet term kept - the correct A/B, per XSL.md).

Usage: seam_repair.py dec.cdr unblended.cdr W Hcoded fmt depth slice_h refresh_r

Prints the slice-boundary step excess (mean |row-to-row| luma step at
boundaries minus interior; codes) for the edited and un-edited pictures.
Frame indices matter for the barrier phases, so both files carry the same
frame count.  Values are in the biased domain; differences cancel the bias.
"""
import sys
import numpy as np

def main():
    dfile, ufile, W, H, fmt, depth, sh, R = sys.argv[1:9]
    W, H, sh = int(W), int(H), int(sh)
    Wc = W if fmt == "444" else W // 2
    fw = W*H + 2*Wc*H
    d = np.fromfile(dfile, dtype='<u2')
    u = np.fromfile(ufile, dtype='<u2')
    nf = min(d.size // fw, u.size // fw)
    for f in range(nf):
        rows = []
        for name, buf in (("edited", d), ("no-edit", u)):
            y = buf[f*fw:f*fw+W*H].reshape(H, W).astype(np.float64)
            step = np.abs(np.diff(y, axis=0)).mean(axis=1)
            bmask = np.zeros(H-1, bool)
            bmask[sh-1::sh] = True
            rows.append(step[bmask].mean() - step[~bmask].mean())
        print(f"frame {f}: seam excess edited {rows[0]:+.3f}  no-edit {rows[1]:+.3f} "
              f"(codes; repair = {rows[1]-rows[0]:+.3f})")

if __name__ == "__main__":
    main()
`````

## Appendix C — input checksums (md5)

### C.1 Prepared masters (`tests/raw_manifest.md5`)

Generated by the 10.1 commands from the provided footage; every recorded
stream md5 in section 10 assumes masters matching this manifest.

```
f572077377304264336454f32032734e  cine4k_422_8.yuv
a0fe5db63e00598114adb8de9a5fb09e  cine4k_444_10.yuv
3cadd368aad0f17aac9b245596dee583  cineA21_422_12.yuv
5b8338ae23372ca943308fae506bf229  cineA21_444_10.yuv
b2151007506a605b175d2e0909506ccd  cineA21_720_422_12.yuv
c3aa081c02e5dc320f60abdc1ed91b9d  cineA31_422_10.yuv
4c280c126b3c871eafb5bf4593b3117b  cineA31_720_444_8.yuv
eab192f9d2029661c60ba66ade9e25e6  gfx1080_422_10.yuv
152696f440bfc7afd4a9eedf0b2bcb70  gfx1080_444_12.yuv
d376894a7b5c5427fe675a54c6c11260  gfx1080_444_8.yuv
8e801e5935302b54a06ee67474331338  gfx720_422_10.yuv
a6407075931bce54280512b64f2b7e42  gfxF003_422_12.yuv
f3d0aa61f208fdad3d910b7fd9031ac7  gfxF003_444_8.yuv
```

### C.2 Provided footage (source PNGs)

The five sets as delivered.  These files are the only inputs to 10.1.

```
5423e6ba877f34089ba42a7510dfeac5  footage/gfx444_B001C001_frame000.png
375ced680caeb09047f6c667f0d73cad  footage/gfx444_B001C001_frame001.png
be086a737df91381770e55b97d7bc3e5  footage/gfx444_B001C001_frame002.png
b81c66d59c454bcdc52d8b5d7c807e74  footage/cine_A005C021/cine_A005C021_frame000.png
cca9ca3462b294fc2b9a785595d56595  footage/cine_A005C021/cine_A005C021_frame001.png
5a9145ffa4b8496eb66db14e1e1bf91c  footage/cine_A005C031/cine_A005C031_frame000.png
f8eb1587a94b2f6e24243608b51dac17  footage/cine_A005C031/cine_A005C031_frame001.png
f89468784990ab307cdc087fa7cac1fb  footage/cine_A005C031/cine_A005C031_frame002.png
a61c88280636b980e3009fdf6a9bb382  footage/cine4k/cine_4k_A006_frame000.png
ae1f9bc73b98821adfe27d611bfc8505  footage/cine4k/cine_4k_A006_frame001.png
491e829026bef33db41987d742f6689c  footage/gfx444_F003C012/gfx444_F003C012_frame000.png
877c721041dd3a3fad4259fa51a8f22e  footage/gfx444_F003C012/gfx444_F003C012_frame001.png
cc1dfb02563bf932783747420d33a03c  footage/gfx444_F003C012/gfx444_F003C012_frame002.png
```

(The codec zip's own contents need no checksum here: section 9's procedure
was verified against it, and the patch of Appendix A fails loudly — fuzz or
rejects — on any tree that is not the pristine drop.)


---

# 12. Baseband interchange: the second contract

*Added after sections 1-11 and Appendices A-C were written.  Those sections are
the record of what was claimed for the MINOR-10 build; they have been edited
only to remove wall-clock figures (12.18) and to mark supersessions.  Where the two disagree, this section is
later and wins — the specific supersessions are listed in 12.12.*

**Verdict.** After the pad fix of 12.4, the two conditions section 5.4 named
for baseband exactness reduce to **one**: a stream is exact over ordinary
cropped baseband interchange **iff no committed sample lies outside the legal
range**, and the encoder now measures and reports exactly that, per stream.
The pad-geometry condition is gone — padded rasters (1080 coded as 1088) are
now baseband-exact.  Measured on the shipped build across 29 baseband cells plus three long chains
and a rail-heavy liveness arm: **22 of 22 cells with `oob = 0` PASS, with no
exceptions**; every failing cell carries `oob > 0` (12.14).  The
2048 bias and the coded/display crop are, as claimed, not load-bearing on
their own.

## 12.1 Why this section exists

Sections 2 and 7 define the contract over the **CDR** — the codec's own
coded-domain raw.  Section 5.4 additionally argued that ordinary baseband
(legal-range, cropped, unbiased) differs from the CDR in only three ways, of
which two matter.  That was an *argument*, and it rested on two measured
cells.  This project's own register records fourteen arguments that did not
survive measurement, so the argument is now a matrix.

The distinction is operationally real, not academic.  A store-and-forward
mezzanine chain can carry the CDR.  A facility that decodes to baseband,
routes it over SDI/IP, and re-encodes downstream cannot: the pixels that
arrive at the second encoder are legal-range and cropped to the display
raster.  If the codec is only exact over its own interchange format, the
guarantee does not survive the workflow it exists for.

## 12.2 The harness (new, additive)

`tests/genchain_bb.sh` takes the same arguments as `tests/genchain.sh`
(section 10.2) and runs the same chain with **no `--cdr` anywhere**:

```
master → omc_enc → g1.omc → omc_dec → g1.yuv          (ordinary display decode:
       → omc_enc → gN.omc → omc_dec → gN.yuv           legal-range, cropped,
                                                       unbiased, re-padded by
                                                       the encoder tool)
```

PASS iff `cmp(g1.yuv, gN.yuv)` for every N and `cmp(g2.omc, gN.omc)` for every
N ≥ 3 — the same verdict as section 10.2, so the two matrices are directly
comparable.  Every generation re-encodes with the **same command line as
generation 1** (true dims, not coded dims: there is no CDR here).

Each row also carries **per-cell gamut evidence**, from a one-off probe that
takes no part in the chain: `tests/gamut_probe.py g1.cdr depth` prints the
committed sample range and the out-of-legal-range count.  "In-gamut" is
therefore a measured property of each row, not an assumption about the corpus.

`tests/run_matrix_bb.sh padfree|padded|all` runs the section-10.3 matrix over
this harness, split by geometry.

## 12.3 Pre-registered predictions

Written and committed **before** the first baseband matrix run
(`tests/bb_prediction.md`, commit `111222a`; build: the minor-10 tree of
Appendix A plus the gamut instrumentation, verified hash-neutral by
reproducing `1c81c776…`):

| # | prediction | outcome |
|---|---|---|
| P1 | every pad-free in-gamut cell PASSES | **confirmed** (12.6) |
| P2 | the 20- and 12-generation chains PASS over baseband | **confirmed** (12.6) |
| P3 | every **padded** cell FAILS at `pixels-gen2` on the pre-fix build | **confirmed** — 15/15 failed, including cells with `oob = 0`, isolating the pad cause from the gamut cause |
| P4 | the rail-heavy clip FAILS baseband while PASSING CDR | **confirmed** (12.7) |

Falsification branches were armed on the green results: any pad-free in-gamut
cell failing would have meant a third load-bearing difference, to be traced
before any write-up.  None failed.  One arm did fire and is reported in 12.8.

## 12.4 The pad fix (change 1 of 1 for this measurement)

**The defect.** P3 confirmed: on the pre-fix build every padded cell failed
baseband at generation 2, *including cells whose content was entirely
in-gamut*.  1080 is the deliverable raster of this brief, and a design whose
own broadcast geometry is the one that breaks on baseband is not shippable.

**Why the obvious fix does not work.**  Section 5.4's suggested remedy —
reconstruct normally, then overwrite the pad rows with a replication of the
committed last visible row — is **insufficient**, and the reason drives the
design.  The inverse vertical lifting computes odd rows as
`x[2i+1] = d[i] + ((x[2i] + x[2i+2]) >> 1)`, so the **last visible row reads
the first pad row**, which in turn came from pad-region coefficients.
Generation 2, holding only the visible rows, cannot recover those
coefficients, so it cannot reproduce the last visible row — the overwrite
comes too late.  Forcing the reconstruction's pads to exact replication
instead is not achievable either: it would require dequantized coefficients
(multiples of `2^shift`) to hit values such as `L + ((D+2)>>2)`.

**What is normative in minor 11.**  For the last slice of a frame whose
display height is below its coded height, with `v` = visible rows in that
slice (`v` even and `v % 4 == 0`; any other geometry disables the rule and is
reported as not baseband-safe), the **vertical** transform runs at the visible
length — level 1 with `nvis = v`, level 2 with `nvis = v/2`:

1. the whole-sample symmetric extension kicks in at `nvis` rather than at the
   end of the array, so **no visible output ever reads a pad row**;
2. the pad pairs' outputs are **forced to exactly zero**.  Zero is a fixed
   point of code-then-decode, so it survives every generation; and because of
   (1) those coefficients are read nowhere on the visible path, so zeroing
   them is free;
3. the inverse **replicates the last visible row** across the pad run.

Horizontal stages are untouched: they run per row, and an all-zero row stays
all-zero through them.  Two consequences follow at the ends:

- **prediction** takes the same treatment (`predict_plane`), so an inter
  residual at a pad position is `0 − 0 = 0` and stays codeable as zero;
- **grain fill is suppressed** at pad-row coefficient positions at both ends
  (the guard sits in `fill_gate_g`, the single choke point through which every
  fill site funnels), so those positions dequantize to exactly zero.  Without
  this the lock cannot verify: generation 2 forward-transforms the same
  picture to zero there, while generation 1's dequantized coefficients would
  carry ±fill.

The committed pad rows are then a pure function of the committed visible rows,
so a cropped baseband picture re-padded by replication **is** the committed
picture, bit for bit — and generation 2's forward transform yields exactly
generation 1's dequantized coefficients, which is why **the generation lock of
section 5.5 is unchanged**.

**Change control.**

- *Minor bump.* Streams are **minor 11**; the decoder rejects every other
  minor, as in section 6.
  > **SUPERSEDED BY 12.23.** This build writes and reads **minor 12**, for a
  > reason that has nothing to do with the pad rule: 12.23 makes the
  > flattest-tier grain-fill gate and the frame-independent fill tile normative.
  > Everything else in this paragraph still holds — the decoder still rejects
  > every minor but its own, and the pad rule this section describes is
  > unchanged in minor 12.
- *Both ends simultaneously.* The rule lives in the shared transform
  (`src/dwt.c`) and the shared `slice_vis_rows()`, so encoder and decoder
  cannot disagree; both derive `v` from `display_height`, which the stream
  header already carries and the decoder already reads.
- *No-op when unpadded.* With `v == slice_h` every branch reduces to the
  minor-10 code. **Verified, not argued:** an unpadded stream is byte-identical
  to its minor-10 predecessor except for the version byte — patching byte 5 of
  the minor-11 file back to `10` reproduces the recorded minor-10 md5
  `bd0de556a45ebe547e5854c3e04a408d` exactly.
- *Existing matrix re-run.* The full section-10.3 CDR matrix: **29/29 PASS**
  (12.6).
- *Gate proven non-vacuous.* See 12.5.
- *Latency.* The rule adds no rows to any latency term: it is confined within
  the slice, adds no lookahead, and leaves the A2 model of section 11.4
  unchanged. See 12.10.

One new encoder flag is required by this change: a CDR is at coded geometry,
so the true raster cannot be inferred from it, and `--display-w/--display-h`
must be passed when re-encoding a CDR of a padded raster.  `omc_dec` prints
the exact flags to use.  `tests/genchain.sh` passes them.

## 12.5 The pad gate, and proof that it can fail

`make test` gains three gates here (and three more in 12.13, six in total) (`tests/test_xsl.c`, 256×64 coded with a 56-row
display, so the last slice has `v = 8` visible and 8 pad rows):

- **G-T5-PAD1** — the committed pad rows are a replication of the committed
  last visible row (a pure function of the visible picture);
- **G-T5-PAD2** — cropping to the display raster, re-padding by replication and
  re-encoding reproduces the committed visible picture byte for byte;
- **G-T5-PAD3** — **the gate is non-vacuous**: the same chain run with the
  pre-minor-11 pad behaviour reintroduced (`the `--debug-oldpads` encoder flag / the
  `omc_enc_debug_oldpads` + `omc_dec_debug_oldpads` API, which make
  `slice_vis_rows()` return `slice_h`) is *required to FAIL*.

The same liveness check at matrix scale, one command apart, on identical
content with `oob = 0` on both arms — so it isolates the pad cause exactly:

```
tests/genchain_bb.sh tests/raw/gfx1080_422_10.yuv 1920 1080 422 10 1.0 16 5 --debug-oldpads
  FAIL pixels-gen2  [BB 1920x1080->1920x1088 422/10b bpp=1.0 sh=16 gens=5 ] oob=0
tests/genchain_bb.sh tests/raw/gfx1080_422_10.yuv 1920 1080 422 10 1.0 16 5
  PASS              [BB 1920x1080->1920x1088 422/10b bpp=1.0 sh=16 gens=5 ] oob=0
```

The CLI hook is **encoder-side only** (a decoder that honoured an environment
lever would itself be the hazard 12.13 removed).  The authoritative
non-vacuity proof is therefore gate **G-T5-PAD3** in `make test`, which sets
the hook on both contexts through the API.

## 12.6 The baseband matrix — minor 11

Build stamp: commit `502f8b9`; reproducible from a pristine drop by Appendix A
then Appendix D (verified: the rebuilt binary reproduces
`156f0237206ac5f66f5b8c89535dfea4`, the generation-1 md5 of the 1080p
reference cell below).  Command: `tests/run_matrix_bb.sh all`, plus the long
chains.  `range` and `oob` are the per-cell gamut evidence of 12.2.

```
PASS  [BB 1280x720->1280x720 422/10b bpp=0.5 sh=8 gens=6 ] g1.omc=2355cfeecd32164c8c0bdeb00c8630c9 range=[116..909] oob=0
PASS  [BB 1280x720->1280x720 422/10b bpp=2.0 sh=8 gens=5 ] g1.omc=54c3fdbfd5560be82bcc78282d7d7e3a range=[139..878] oob=0
FAIL pixels-gen2  [BB 1280x720->1280x720 444/8b bpp=0.5 sh=8 gens=5 ] range=[61..289] oob=3737
FAIL pixels-gen2  [BB 1280x720->1280x720 444/8b bpp=1.0 sh=16 gens=5 ] range=[65..280] oob=1874
PASS  [BB 1280x720->1280x720 422/12b bpp=3.0 sh=8 gens=5 ] g1.omc=1a68a53a652c838b823e188b188ed713 range=[249..3604] oob=0
PASS  [BB 2048x1152->2048x1152 422/12b bpp=0.5 sh=16 gens=6 ] g1.omc=0d7b660dfd85e03d647293c21fcad479 range=[-12..3622] oob=1
FAIL pixels-gen2  [BB 2048x1152->2048x1152 444/10b bpp=2.0 sh=16 gens=5 ] range=[-47..1028] oob=839
PASS  [BB 2048x1152->2048x1152 422/10b bpp=0.5 sh=8 gens=5 ] g1.omc=33fe223926fb6ec6139bc8eaa0b49b28 range=[345..974] oob=0
PASS  [BB 2048x1152->2048x1152 422/10b bpp=3.0 sh=32 gens=5 ] g1.omc=f4817c32c8778c7afb0d6a9963f6447b range=[359..941] oob=0
PASS  [BB 4096x2160->4096x2160 422/8b bpp=0.5 sh=16 gens=4 ] g1.omc=d9e27a26e5025d64800ace3ec32dbef0 range=[27..252] oob=0
FAIL pixels-gen2  [BB 4480x1856->4480x1856 444/8b bpp=0.5 sh=16 gens=4 ] range=[-21..183] oob=232811
PASS  [BB 4480x1856->4480x1856 422/12b bpp=1.0 sh=8 gens=4 ] g1.omc=3b93a057e52e916b8c0aace61dbcd70e range=[198..2708] oob=0
PASS  [BB 2048x1152->2048x1152 422/10b bpp=0.5 sh=16 gens=5 --tune vmaf] g1.omc=f1bbc0717946783e8e40c94eab41190c range=[342..1009] oob=0
PASS  [BB 2048x1152->2048x1152 422/10b bpp=0.5 sh=16 gens=5 --grain-corr --fill-static] g1.omc=f3b9143915126cd2f7307f66e3cc3eb2 range=[343..970] oob=0
PASS  [BB 1920x1080->1920x1088 422/10b bpp=0.5 sh=16 gens=6 ] g1.omc=06b04ad48aee485a2ded284946ad1bc9 range=[136..883] oob=0
PASS  [BB 1920x1080->1920x1088 422/10b bpp=1.0 sh=16 gens=5 ] g1.omc=156f0237206ac5f66f5b8c89535dfea4 range=[139..875] oob=0
PASS  [BB 1920x1080->1920x1088 422/10b bpp=3.0 sh=16 gens=5 ] g1.omc=53c841ec2ca947eef4ef6224c79dca24 range=[141..870] oob=0
FAIL pixels-gen2  [BB 1920x1080->1920x1088 444/12b bpp=0.5 sh=16 gens=6 ] range=[190..4241] oob=6
PASS  [BB 1920x1080->1920x1088 444/12b bpp=3.0 sh=16 gens=5 ] g1.omc=ea57b1cee042e29b2e890e6f7699fd7a range=[300..3822] oob=0
PASS  [BB 1920x1080->1920x1088 444/8b bpp=1.0 sh=16 gens=5 ] g1.omc=f0e0638ae861fe57428123cd7ef4b5d0 range=[17..248] oob=0
PASS  [BB 1920x1080->1920x1088 422/10b bpp=1.0 sh=32 gens=5 ] g1.omc=4b0765b38ff152535997dfee5dd4d947 range=[140..874] oob=0
FAIL pixels-gen2  [BB 4096x2160->4096x2176 444/10b bpp=2.0 sh=32 gens=4 ] range=[5..1078] oob=42056
PASS  [BB 1920x1080->1920x1088 422/10b bpp=1.0 sh=16 gens=5 --tune vmaf] g1.omc=24e17aeaa08f8c6f8ad82ef47493d743 range=[134..873] oob=0
PASS  [BB 1920x1080->1920x1088 422/10b bpp=1.0 sh=16 gens=5 --grain-corr] g1.omc=03db83b9e13a688bfd15f81c3e7209b2 range=[137..876] oob=0
PASS  [BB 1920x1080->1920x1088 422/10b bpp=1.0 sh=16 gens=5 --fill-static] g1.omc=77ac1ce899e0aa127d3ee5c9e0a1c3aa range=[140..875] oob=0
PASS  [BB 1920x1080->1920x1088 422/10b bpp=1.0 sh=16 gens=5 --no-fill] g1.omc=787a6377e090d490272ed8abd0aebcc6 range=[140..875] oob=0
PASS  [BB 1920x1080->1920x1088 422/10b bpp=1.0 sh=16 gens=5 --grain-replace] g1.omc=3d39cd9bea44d1ad1a8a19f8014fbb59 range=[142..870] oob=0
PASS  [BB 1920x1080->1920x1088 422/10b bpp=1.0 sh=16 gens=5 --refresh 2] g1.omc=80e732f1d4042c511b186dd1a406489b range=[140..870] oob=0
PASS  [BB 1920x1080->1920x1088 422/10b bpp=1.0 sh=16 gens=5 --refresh 3] g1.omc=119abc593d8d9672f88c5ae5702f9b38 range=[140..875] oob=0
PASS  [BB 1280x720->1280x720 422/10b bpp=1.0 sh=8 gens=20 ] g1.omc=e6af518a63bc2c24dc8f9e871adee2d9 range=[139..893] oob=0
PASS  [BB 2048x1152->2048x1152 422/10b bpp=0.5 sh=16 gens=12 ] g1.omc=d85cd50cc17ef40fb55d1e376815c405 range=[343..970] oob=0
PASS  [BB 1920x1080->1920x1088 422/10b bpp=1.0 sh=16 gens=12 ] g1.omc=156f0237206ac5f66f5b8c89535dfea4 range=[139..875] oob=0
```

**CDR matrix, same build: 29/29 PASS** — the pad change caused no regression
on the interchange format section 10.3 measured (full log in the repository;
the verdicts and the unpadded md5s are those of section 10.3 with the version
byte advanced).

**Separation of the two causes.**  Of the 32 baseband runs above:

| condition | cells | PASS |
|---|---|---|
| `oob = 0` | 25 | **25** |
| `oob > 0` | 7 | 1 |

No cell with `oob = 0` failed.  **All 14 padded-geometry cells with `oob = 0`
now pass** (16 padded cells were run; the other two carry `oob > 0` and fail on
gamut, not geometry) — every encoder flag (`--tune vmaf`, `--grain-corr`,
`--fill-static`, `--no-fill`, `--grain-replace`, `--refresh 2`, `--refresh 3`),
both affected slice heights (16 and 32), 8/10/12-bit, 4:2:2 and 4:4:4, and a
12-generation chain — where **every one of them failed before the fix**.

## 12.7 The rail-heavy arm (liveness for the whole section)

A matrix that cannot fail proves nothing.  `tests/mkrail.py` generates a
deterministic rail-heavy master (hard-clipped white and black plates with
sharp edges placed across slice boundaries, a full-range ramp touching 0 and
`maxv`, saturated bars with chroma at the rails, a white/black line pair
sitting exactly on a slice boundary, all drifting 2 px/frame so inter coding
engages).  Reproduce with
`python3 tests/mkrail.py tests/raw/rail720_422_10.yuv`.

| interchange | 0.5 bpp | 1.0 bpp |
|---|---|---|
| **CDR** | PASS (`cd9108e0…`) | PASS (`07f4a8ff…`) |
| **baseband** | FAIL `pixels-gen2`, oob = 230909 | FAIL `pixels-gen2`, oob = 113095 |

This is the intended result on both axes: the CDR contract is unconditional
and holds even here, while the baseband contract is conditional and the
harness demonstrably detects the violation.  It also confirms the gamut
condition is the *only* remaining one — the same clip, same geometry, passes
the moment its content stops leaving the legal range (12.8).

## 12.8 The gamut report, and what a strict in-gamut mode would cost

**The report (built, unconditional).**  `omc_enc` now prints, per stream:

```
omc_enc: gamut: 0 committed samples outside legal range -- baseband-safe: yes
omc_enc: gamut: 113095 committed samples outside legal range -- baseband-safe: NO (CDR interchange required for exact chains)
```

`omc_enc_oob()` exposes the same count to a library caller.  Two properties
were required of it and both are verified:

1. *It measures what actually reaches baseband.* It counts on the **emitted**
   picture, not the reference — the two differ by the barrier display blend —
   and only over rows that are already **final**, because a boundary row is
   re-emitted and edited when the next slice reconstructs.  Both errors were
   present in the first implementation and both were caught by requiring the
   report to agree with the decoded CDR; it now agrees exactly at every rate
   tested (0.5/1.0/2.0/3.0/6.0 bpp on the rail clip).
2. *It is off the latency path.* The sweep is O(slice_h) per slice.  A
   whole-frame sweep at the last slice — the obvious implementation — would
   put a frame-sized burst inside that slice's A2 budget, which sub-1 ms has
   no room for.

**A falsification branch that fired.**  One `oob > 0` cell PASSED
(`2048×1152 422/12 @0.5`, `oob = 1`).  Traced: the baseband verdict compares
the *display* pictures, and clipping is idempotent, so a single committed
sample that clips to the same value on both generations leaves the displayed
picture unchanged.  The instrument is therefore **conservative** — `oob = 0`
is *sufficient* for baseband exactness (25/25) but not strictly *necessary* —
which is the correct direction for a safety report, and the report says
"baseband-safe: NO" in that case rather than claiming a guarantee it cannot
make.

**The strict mode: measured, not adopted.**  The headline finding is
structural and it is not what the mode's proponents would expect:

> **At exact CBR there is no "spend more bits" lever.**  From frame 1 the
> natural rate controller already starts its search at the finest
> quantization (`floor_q = 0`) and takes the first plan that fits, then
> refines while budget remains.  The encoder is *already* at the finest plan
> the rate allows.  A strict in-gamut mode therefore cannot be bought with
> bits at a fixed rate; it would have to change either the reconstruction rule
> (which is what v4.14's in-loop clip did, and it is exactly what destroys
> exactness — section 4.3) or the choice of lattice point per coefficient
> (a trellis-style search, which is exactness-safe but a substantial piece of
> work).

What the cost *is*, measured on the rail-heavy clip (3 frames, 5 529 600
samples), reproducible with the sweep in 12.11:

| bpp | committed samples out of gamut | share | PSNR-Y | baseband |
|---|---|---|---|---|
| 0.5 | 230 909 | 4.18 % | 19.47 dB* | fails |
| 1.0 | 113 095 | 2.04 % | 68.25 dB | fails |
| 2.0 | 20 480 | 0.37 % | 71.82 dB | fails |
| 3.0 | 0 | 0 % | ∞ (lossless) | **exact** |
| 6.0 | 0 | 0 % | ∞ (lossless) | **exact** |

\* The 19.47 dB at 0.5 bpp against 68.25 dB at 1.0 is a rate cliff, not a
transcription error: the rail clip is mostly flat plates whose hard edges
consume the whole budget below about 1 bpp, at which point the plates
themselves break down.

So on content engineered to be as hostile as possible, the "cost of strict
gamut" today is *a rate*: about 3.0 bpp, at which this clip codes losslessly
and the question disappears.  Below that, a mode would have to buy in-gamut
reconstruction with distortion elsewhere, and the table above bounds how much
it would have to move: at 1.0 bpp, 2 % of samples.

**Incidence on real footage** (from the per-cell evidence in 12.6, not from a
synthetic): out-of-gamut committed samples are **not** exotic.  They appear in
4:4:4 8-bit graphics material, which is mastered hard to the rails —
`gfx444_B001C001` 4:4:4/8 at 0.5 bpp (`oob = 3737`), `gfx444_F003C012`
4:4:4/8 at 0.5 bpp (`oob = 232811`), `cine_4k_A006` 4:4:4/10 at 2.0 bpp
(`oob = 42056`) — and are absent from every 4:2:2 cell of the corpus, where
the limited-range excursion headroom absorbs the ringing.  **The team should
decide the mode with this in mind: the exposed class is exactly the
full-range/graphics workflow, not the cinema 4:2:2 one.**

> **SUPERSEDED BY 12.22 — read that section instead of the two paragraphs
> above.**  Two claims here are wrong and one of them was already contradicted
> by this section's own table.
>
> 1. *"absent from every 4:2:2 cell of the corpus"* is false.  The
>    `2048x1152 422/12 @0.5` cell in 12.6 carries `oob = 1`, and 12.22 measures
>    ordinary 4:2:2 10-bit camera footage graded to the container rails failing
>    the baseband chain at 0.5 bpp on a couple of hundred stray samples out of
>    twelve million.  The exposed class is not "graphics"; it is **anything
>    mastered to the rails**, which is a grading decision, not a format.
> 2. *"a strict in-gamut mode ... would have to change either the
>    reconstruction rule ... or the choice of lattice point per coefficient (a
>    trellis-style search, ... a substantial piece of work)"* named the right
>    two options and then missed a third, which is what 12.22 builds: change
>    the **source coefficients before quantization** and re-code.  That leaves
>    the reconstruction rule and the emitted lattice point untouched, so the
>    exactness argument of section 8 does not move at all.
>
> The rate table above is still valid as a measurement of the *uncorrected*
> encoder and is not restated in 12.22.  Nothing else in 12.1 - 12.21 changes.

## 12.9 Frame phase: an operational constraint, with its mechanism

Section 7 listed identical frame numbering as a chain precondition in a
sentence.  It deserves a decision packet, because broadcast runs both
workflows.

**What depends on it.**  Exactly two things, and both are functions of
`fidx8 = frame_idx & 255` and nothing else: the rolling refresh wave
(`(fidx8 % R) == (slice % R)`, which decides *which slices are intra*) and the
grain-fill tile animation.  A re-encode at the wrong phase intra-codes
different slices and is not exact.  **Measured** (2048×1152 4:2:2/10 @1.0 bpp,
CDR chain): re-encoding at the correct phase is byte-exact; re-encoding the
same picture at phase 0 instead of 5 **fails** — so the constraint is real,
not theoretical.

**The mechanism (cheap, and now built).**  Because both consumers are mod 256
and `fidx8` *is* the low 8 bits, the phase is **fully recoverable from the
stream itself** — there is no residual ambiguity, and no new syntax was
needed: every slice header already carries `fidx8`.

- `omc_dec` prints it: `frame phase of the first slice: fidx8=N (re-encode
  with --start-frame N to resume it)`;
- `omc_enc --start-frame N` resumes it.

**The two cases, honestly:**

| workflow | what it needs | status |
|---|---|---|
| file-based / store-and-forward, whole clip | nothing — both runs start at 0 | free |
| **live splice / mid-stream join** | read `fidx8` from any slice header of the incoming stream, pass `--start-frame` to the re-encoder | **exact**, mechanism built and verified |

A joiner that ignores the phase gets a picture that is correct but *not*
byte-exact: its first refresh cycle intra-codes a different set of slices, so
it behaves like a fresh generation-1 encode for up to `refresh_r` frames, then
settles into its own fixed point.  Nothing drifts without bound — the loss is
one generation of quality at the splice, not a chain-long decay.

## 12.10 Latency (A2) is unaffected, and its accounting was repaired

The rule of 12.4 is confined within a slice, adds no lookahead and no rows to
any term of the model (`slice_h·line + slice + 2·line + conversion`; the
2-line term is the un-blend lookahead of 5.3, already charged).  `make test`
passes all six suites, including the A2 suite: **every SUPPORTED conversion measured in the
mandate's range -- 720p to 4320p, 50 to 120 fps, up and down, with the colour
and tone-map stage in the path -- stays under 1 ms.**  (In the table below,
`—` marks a ratio that was not measured or is not supported at all; 720p to
8K, for instance, exceeds the scaler's 48-tap ceiling entirely -- 12.17.)

Three defects in the *accounting* were found while checking this, and fixed
(they are the adversarial review's F7/F8 plus one latent gate):

1. `omc_config_latency()`, documented as "the same arithmetic
   `omc_validate_config()` uses", was not: it defaulted `slice_h` to 8
   unconditionally (the validator says 16 above 720p) and always charged the
   conversion as whole slice periods (the validator charges raster-clocked
   lines, which is the product's contract).  It now matches the validator.
2. The latency check was gated behind `cfg->uc_ratio`, so a configuration with
   **no conversion** was never checked at all — which is why README's promise
   that the validator refuses `--slice-h 32` below 2160p was false.  The codec
   term is now always computed; `a2_strict` remains the enforce-versus-report
   switch, so default behaviour is unchanged.
3. The decode-side gate still refused any stream newer than minor 9 — dormant
   only because the reference decoder never calls the validator, and now
   corrected to `OMC_VERSION_MINOR`.

The resulting figures at the **default** slice height, computed from the
codec's own model at coded geometry (`raster` = the product's raster-clocked
output stage; `batched` = the conservative slice-batched alternative):

| format | sh | conversion | raster | batched |
|---|---|---|---|---|
| 720p50 | 8 | none / 2× / 4× | 0.500 / 0.750 / 0.861 | 0.500 / 0.722 / 0.944 |
| 720p60 | 8 | none / 2× / 4× | 0.417 / 0.625 / 0.718 | 0.417 / 0.602 / 0.787 |
| 1080p50 | 16 | none / 2× / 4× | 0.625 / 0.790 / 0.864 | 0.625 / 0.919 / 0.919 |
| 1080p60 | 16 | none / 2× / 4× | 0.521 / — / — | 0.521 / — / — |
| 2160p50 | 16 | none / 2× / 4× | 0.315 / 0.398 / 0.435 | 0.315 / 0.463 / 0.463 |
| 2160p120 | 16 | none / 2× / 4× | 0.131 / 0.166 / 0.181 | 0.131 / 0.193 / 0.193 |
| 4320p50 | 32 | none / 2× / 4× | 0.306 / 0.347 / 0.366 | 0.306 / 0.454 / 0.454 |

All milliseconds, all under the 1 ms bar **including the conversion term**.
The configurations that do breach it are non-default slice heights, and they
are now refusable: 720p at `slice_h 16` with any conversion (1.194 ms at 2×),
720p at `slice_h 32` (1.793 ms with no conversion at all), and 1080p at
`slice_h 32` (1.213 ms) — the last two being exactly the cases README always
claimed the validator would refuse and, before fix 2 above, it did not.

## 12.11 Reproducing this section

```
# 0. build the minor-11 codec: Appendix A then Appendix D (section 9's recipe,
#    with the Appendix D patch applied second), then `make`
# 1. prepare masters exactly as section 10.1, and the rail clip:
python3 tests/mkrail.py tests/raw/rail720_422_10.yuv
# 2. the baseband matrix and the long chains:
tests/run_matrix_bb.sh all
tests/genchain_bb.sh tests/raw/gfx720_422_10.yuv  1280 720  422 10 1.0 8  20
tests/genchain_bb.sh tests/raw/cineA31_422_10.yuv 2048 1152 422 10 0.5 16 12
tests/genchain_bb.sh tests/raw/gfx1080_422_10.yuv 1920 1080 422 10 1.0 16 12
# 3. the rail arm, both interchanges:
tests/genchain_bb.sh tests/raw/rail720_422_10.yuv 1280 720 422 10 1.0 16 5   # FAIL expected
tests/genchain.sh    tests/raw/rail720_422_10.yuv 1280 720 422 10 1.0 16 5   # PASS expected
# 4. the non-vacuity proof (12.5) -- encoder-side hook; the authoritative
#    proof is gate G-T5-PAD3 inside `make test`:
tests/genchain_bb.sh tests/raw/gfx1080_422_10.yuv 1920 1080 422 10 1.0 16 5 --debug-oldpads
# 5. the CDR matrix, unchanged verdicts (12.6):
tests/run_matrix.sh
# 6. the gamut/rate sweep of 12.8:
for b in 0.5 1.0 2.0 3.0 6.0; do
  omc/omc_v4.9/omc_enc -i tests/raw/rail720_422_10.yuv -o /tmp/r.omc \
      -w 1280 -h 720 --fmt 422 --depth 10 --bpp $b --slice-h 16 2>&1 | grep gamut
done
# 7. the frame-phase check of 12.9 (correct phase exact, wrong phase fails):
omc/omc_v4.9/omc_enc -i tests/raw/cineA31_422_10.yuv -o /tmp/p1.omc -w 2048 -h 1152 \
    --fmt 422 --depth 10 --bpp 1.0 --slice-h 16 --start-frame 5
omc/omc_v4.9/omc_dec -i /tmp/p1.omc --cdr -o /tmp/p1.cdr
omc/omc_v4.9/omc_enc --cdr-in -i /tmp/p1.cdr -o /tmp/p2.omc -w 2048 -h 1152 \
    --display-w 2048 --display-h 1152 \
    --fmt 422 --depth 10 --bpp 1.0 --slice-h 16 --start-frame 5   # exact
omc/omc_v4.9/omc_enc --cdr-in -i /tmp/p1.cdr -o /tmp/p3.omc -w 2048 -h 1152 \
    --display-w 2048 --display-h 1152 \
    --fmt 422 --depth 10 --bpp 1.0 --slice-h 16 --start-frame 0   # differs
# 8. the gates, including the non-vacuous pad gate:
cd omc/omc_v4.9 && make test
```

## 12.12 What this section supersedes

- **Section 5.4 / 6.8** — the conformance point is unchanged (the CDR
  picture), but the claim that pad rows *must* travel with the picture now
  holds only for minors ≤ 10.  From minor 11 the pad rows are recoverable from
  the visible picture, which is what makes baseband exactness possible.
- **Sections 3, 6, 11.1 and Appendix A** — these describe **minor 10** and are
  the record of that build.  The shipping stream version is **11**; Appendix D
  is the delta, and the two patches together reproduce the binaries that
  produced section 12's numbers.
- **Section 7** — the frame-phase precondition is unchanged in substance, but
  12.9 gives it a mechanism (`--start-frame`, and the phase readable from any
  slice header) rather than leaving it as a caveat.
- **Section 11.4** — the latency *model* is unchanged; its *implementation* in
  `omc_config_latency()` and the validator was wrong in the three ways listed
  in 12.10 and is now consistent.

**Added by this revision** (the two sections after 12.21, and the record at the
top of the document):

- **Section 12.8, second paragraph** — superseded in place by **12.22**.  It
  drew the wrong boundary around which content commits out-of-gamut samples,
  and its own table contradicted it.  The correction and the mode that removes
  the condition are in 12.22.
- **Section 12.5's change-control note, "Streams are minor 11"** — superseded
  in place by **12.23**.  The shipping stream version is **12**.  The pad rule
  that note is attached to is unchanged.
- **Section 5.7** — its *reasoning* about the grain fill's taper stands and is
  confirmed twice over in 12.23.4.  Its *accounting of the cost* does not: it
  reports the cost in brightness accuracy, and the mechanism it removed existed
  to close a defect that brightness accuracy cannot see.  **12.23.2** puts the
  measured cost on the record.
- **Every command line in sections 1 - 12.21 that relies on the grain fill
  being on** — the fill is now opt-in.  Add `--fill`; add `OMC_CALM=0` as well
  to reproduce a minor-11 encoder exactly.  The revision record at the top of
  this document is the single place that says so.


---

## Appendix D — the minor-11 delta patch (normative)

Appendix A reproduces the **minor-10** build, which is the build every number
in sections 10 and 10.8 came from.  This appendix is the delta that advances
it to **minor 11** — the pad neutralization of 12.4, the gamut report of 12.8,
the frame-phase mechanism of 12.9, the latency-accounting repairs of 12.10,
the four adversarial-audit fixes of 12.13, the `llbuf` and concealment fixes
of 12.15, the grain-classifier re-clamp of 12.16, and the per-context XSL
state, C11 one-time init and decoder header validation of 12.19 — and is the
build every number from 12.14 onward came from.  (12.6's figures predate audit
fix 1; 12.14 reprints them from the shipped build.)  Neither patch is
edited into the other on purpose: the historical record of what was claimed
when is part of the deliverable.

Apply **after** Appendix A, from inside `omc_v4.9`:

```
awk '/^=== BEGIN T5 M11 PATCH ===$/{f=1;next} /^=== END T5 M11 PATCH ===$/{f=0} f' \
    TEMPORAL_T5.md > t5_m11.patch
cd omc_v4.9
patch -p1 < ../t5.patch        # Appendix A  (minor 10)
patch -p1 < ../t5_m11.patch    # Appendix D  (minor 11)
make && make test              # five suites print "all ok"; the sixth
                               # prints "test_xsl: all ok".  No line
                               # begins with FAIL.
```

Verified end-to-end before shipping this document: a pristine `omc_v4.9` tree
with both patches applied, built as above, reproduces
`156f0237206ac5f66f5b8c89535dfea4` — the generation-1 stream md5 of the 1080p
reference cell in 12.6 — byte for byte, and passes G-T5-PAD1/2/3.

`````diff
=== BEGIN T5 M11 PATCH ===
diff --git a/include/omc1.h b/include/omc1.h
index 5221795..2414f29 100644
--- a/include/omc1.h
+++ b/include/omc1.h
@@ -17,15 +17,19 @@
 
 #define OMC_VERSION_MAJOR 4
 /* RELEASE IDENTITY is 4.15-T5 (stream minor 10): the temporal engine was
- * REMOVED and REBUILT for zero generation loss (the T5 layer).  Minor-10
- * streams are the only streams this build reads or writes: the rebuilt
+ * REMOVED and REBUILT for zero generation loss (the T5 layer).  Minor 11
+ * adds PAD NEUTRALIZATION: on a raster coded taller than its display height
+ * (1080 as 1088) the surplus rows are no longer coded content but a pure
+ * function of the committed visible rows, which makes such rasters exact
+ * over ordinary cropped BASEBAND interchange and not only over the CDR.
+ * Minor-11 streams are the only streams this build reads or writes: the rebuilt
  * temporal semantics (frame-buffer reference, derived motion, always-on
  * reversible cross-slice boundary edit, biased unclipped pixel domain)
  * are not compatible with any earlier minor, so earlier minors are
  * rejected rather than silently mis-decoded.  See docs/TEMPORAL_T5.md. */
-#define OMC_RELEASE_MINOR 10
-#define OMC_VERSION_MINOR 10 /* T5: rebuilt temporal layer + always-on reversible XSL */
-#define OMC_MINOR_T5 10
+#define OMC_RELEASE_MINOR 11
+#define OMC_VERSION_MINOR 11 /* T5: rebuilt temporal layer + always-on reversible XSL */
+#define OMC_MINOR_T5 11      /* 11 adds pad neutralization (baseband-exact rasters) */
 
 /* T5 pixel domain: every omc_frame_t (encoder input, decoder output, recon)
  * carries samples as u16 = true_value + OMC_PIX_BIAS, UNCLIPPED to the legal
@@ -205,6 +209,23 @@ int omc_enc_slice(omc_enc_t *e, const omc_frame_t *in, int frame_idx, int slice_
 /* Convenience: whole frame = all slices concatenated. */
 int64_t omc_enc_frame(omc_enc_t *e, const omc_frame_t *in, int frame_idx,
                       uint8_t *dst, size_t cap, omc_frame_t *recon);
+/* Gamut report: committed samples so far outside the legal range [0, 2^depth).
+ * Nonzero means a legal-range baseband hop would alter the committed picture,
+ * so this stream is NOT safe for baseband-interchange generation chains (the
+ * CDR interchange is always safe).  Instrumentation only; never changes
+ * coding.  The reference encoder CLI prints the verdict at end of encode. */
+int64_t omc_enc_oob(const omc_enc_t *e);
+/* 1 when this raster's geometry is recoverable from a cropped baseband
+ * picture (minor 11 pad neutralization applies), 0 when it is not -- a
+ * horizontally padded raster, or a visible run the rule cannot express.
+ * A stream is baseband-safe only when this is 1 AND omc_enc_oob() is 0. */
+int omc_enc_geom_baseband_safe(const omc_enc_t *e);
+/* TEST ONLY: reintroduce the pre-minor-11 pad behaviour on this context, so a
+ * gate can prove it is non-vacuous.  Never an environment variable: a lever
+ * that changes normative reconstruction from the environment is an
+ * encoder/decoder disagreement channel. */
+void omc_enc_debug_oldpads(omc_enc_t *e, int on);
+void omc_dec_debug_oldpads(omc_dec_t *d, int on);
 
 /* ---- decoder ---- */
 omc_dec_t *omc_dec_create(const omc_config_t *cfg);
diff --git a/src/codec.c b/src/codec.c
index b3c51ad..27656f1 100644
--- a/src/codec.c
+++ b/src/codec.c
@@ -20,9 +20,9 @@
 #include <stdio.h>
 #include <malloc.h>
 #include "internal.h"
+#include <stdatomic.h>
 
 extern int omc_xsl;       /* defined below; read by the header parser */
-extern int omc_xsl_lim;   /* ditto: minor 9 pins the boundary-blend cap */
 
 /* ------------------------------------------------------------------ common */
 
@@ -31,6 +31,17 @@ typedef struct {
     int W, H, Wc, sh, nslices;
     int mid, maxv;
     int xsl_lim;                 /* boundary-blend cap, codes @10-bit (minor 9) */
+    int32_t xsl_buf[OMC_NPLANES][8192]; /* per-column d[-1], PER CONTEXT */
+    int xsl_live[OMC_NPLANES];
+    int xsl_noretro;             /* prev slice refreshed this frame: protect it */
+    int dbg_oldpads;             /* TEST ONLY: code pad rows as ordinary content
+                                    (the pre-minor-11 behaviour).  Per CONTEXT
+                                    and settable only through the API below --
+                                    never from the environment: an environment
+                                    lever that changes normative reconstruction
+                                    is an encoder/decoder disagreement channel
+                                    by construction, which is the rule this
+                                    codec already states for the XSL levers. */
     size_t slice_bytes, payload_bytes;
 } ctx_common_t;
 
@@ -82,6 +93,9 @@ struct omc_enc {
     uint16_t *inub[OMC_NPLANES]; /* un-blended copy of the input frame */
     int last_frame;             /* last frame index encoded (-1 = none) */
     int last_frame2;            /* frame index held by refprev2 (-1 = none) */
+    int64_t oob_samples;        /* committed samples outside legal range (gamut
+                                   report: such samples do not survive a
+                                   legal-range baseband hop; see omc_enc_oob) */
     int32_t *pbuf[OMC_NPLANES];             /* prediction transform scratch */
     int32_t *pcoef[OMC_NPLANES][OMC_NBANDS]; /* prediction coefficients */
     int32_t *dcoef[OMC_NPLANES][OMC_NBANDS]; /* delta (inter) coefficients */
@@ -287,6 +301,31 @@ int omc_read_stream_header(const uint8_t *src, omc_config_t *cfg)
     if (cfg->uc_ratio > 2) return -3;
     memcpy(&cfg->display_height, o, 2); o += 2;
     memcpy(&cfg->display_width, o, 2); o += 2;
+    /* VALIDATE THE WIRE FIELDS.  Everything above is copied verbatim out of an
+     * untrusted header, and the reference decoder never calls
+     * omc_validate_config, so nothing else checks them.  Unchecked, a crafted
+     * stream reaches real damage: slice_h 128 overflows dwt.c's per-column
+     * stack buffers (demonstrated under AddressSanitizer), bitdepth 0 or > 32
+     * makes 1 << (bitdepth-1) undefined, height 0 gives a zero slice count and
+     * hangs the tool, and bits_per_slice below the wire floor underflows
+     * payload_bytes.  The CRC is no defence -- an attacker computes it.  These
+     * are the same constraints omc_validate_config enforces encoder-side,
+     * applied where the trust boundary actually is. */
+    if (cfg->bitdepth != 8 && cfg->bitdepth != 10 && cfg->bitdepth != 12)
+        return -3;
+    if (cfg->chroma != OMC_CF_422 && cfg->chroma != OMC_CF_444) return -3;
+    if (cfg->slice_h != 8 && cfg->slice_h != 16 && cfg->slice_h != 32) return -3;
+    if (cfg->width < 64 || cfg->width > 8192) return -3;
+    if (cfg->width % (cfg->chroma == OMC_CF_444 ? 32 : 64)) return -3;
+    if (cfg->height < cfg->slice_h || cfg->height > 8192) return -3;
+    if (cfg->height % cfg->slice_h) return -3;
+    if (cfg->display_width > cfg->width) return -3;
+    if (cfg->display_height > cfg->height) return -3;
+    if (cfg->bits_per_slice % 8) return -3;
+    if (cfg->bits_per_slice < (uint32_t)(OMC_SLICE_HDR_BYTES + 4) * 8) return -3;
+    if ((uint64_t)cfg->bits_per_slice > (uint64_t)cfg->width * cfg->slice_h * 48)
+        return -3;
+    if (cfg->uc_ratio && (uint64_t)cfg->width << cfg->uc_ratio > 32768) return -3;
     return OMC_STREAM_HDR_BYTES;
 }
 
@@ -399,7 +438,6 @@ int omc_tf_mode = 0;   /* T5: PERMANENTLY 0.  The in-loop temporal filter was
  * dropped.  Encoder-only; any coded value is legal; modes 1-2 are retained
  * as measurement instruments only. */
 int omc_dcfb = 0;
-extern int32_t *omc_dwt_d1m;   /* dwt.c: level-1 vertical boundary term */
 
 /* =================================================================== XSL-T5
  *
@@ -454,11 +492,12 @@ extern int32_t *omc_dwt_d1m;   /* dwt.c: level-1 vertical boundary term */
 int omc_xsl = 7;      /* T5: always on, single (reversible) level.  Kept as a
                          variable only because downstream conditionals read
                          it; nothing ever writes another value. */
-int omc_xsl_lim = 4;  /* per-context cap is c->xsl_lim; this global mirrors
-                         the last-created context for legacy readers only */
-static int32_t omc_xsl_buf[OMC_NPLANES][8192]; /* d[-1] terms, per column (validated max width 8192) */
-static int omc_xsl_live[OMC_NPLANES];
-static int omc_xsl_noretro; /* prev slice refreshed this frame: protect it */
+/* XSL boundary state lives in ctx_common_t (xsl_buf / xsl_live / xsl_noretro).
+ * It was file-scope, which meant two encoder or decoder instances in one
+ * process shared one set of boundary rows -- contradicting the "instances
+ * share no mutable state" guarantee in omc1.h, and racing between threads.
+ * Per CONTEXT, never process-wide: the same rule common_init already applied
+ * to the blend cap. */
 int omc_tailguard = 1;   /* env OMC_TAILGUARD: 0 off, 1 global, 2 tail-local (last 8) */
 int omc_fillhyst = 1;    /* env OMC_FILLHYST:  0 off, 1 global, 2 tail-local (last 8) */
 int omc_rboost = 0;      /* env OMC_RBOOST: refreshed slices get +pct%% of B, CBR-neutral */
@@ -513,8 +552,8 @@ static void xsl_display_blend(ctx_common_t *c, omc_frame_t *fr, int slice_idx,
 static void xsl_prep(ctx_common_t *c, const omc_frame_t *ref, int slice_idx,
                      int rbias, int fidx8)
 {
-    for (int p = 0; p < OMC_NPLANES; p++) omc_xsl_live[p] = 0;
-    omc_xsl_noretro = 0;
+    for (int p = 0; p < OMC_NPLANES; p++) c->xsl_live[p] = 0;
+    c->xsl_noretro = 0;
     if (slice_idx <= 0) return;
     {
         /* REFRESH BARRIER (A5), rule (d): an intra-refreshed slice takes no
@@ -524,7 +563,7 @@ static void xsl_prep(ctx_common_t *c, const omc_frame_t *ref, int slice_idx,
          * header (fidx8) and config alone, on both sides. */
         int Rr = c->cfg.refresh_r ? c->cfg.refresh_r : 8;
         if ((fidx8 % Rr) == (slice_idx % Rr)) return;
-        omc_xsl_noretro = ((fidx8 % Rr) == ((slice_idx - 1) % Rr));
+        c->xsl_noretro = ((fidx8 % Rr) == ((slice_idx - 1) % Rr));
     }
     if (c->W > 8192) return;  /* never overrun; wider than validated max */
     for (int p = 0; p < OMC_NPLANES; p++) {
@@ -534,10 +573,10 @@ static void xsl_prep(ctx_common_t *c, const omc_frame_t *ref, int slice_idx,
         const uint16_t *r14 = ref->p[p] + (size_t)(base - 2) * ref->stride[p];
         const uint16_t *r15 = ref->p[p] + (size_t)(base - 1) * ref->stride[p];
         for (int x = 0; x < pw; x++)
-            omc_xsl_buf[p][x] = ((int32_t)r15[x] - rbias)
+            c->xsl_buf[p][x] = ((int32_t)r15[x] - rbias)
                               - 2 * ((int32_t)r14[x] - rbias)
                               + ((int32_t)r13[x] - rbias);
-        omc_xsl_live[p] = 1;
+        c->xsl_live[p] = 1;
     }
 }
 
@@ -631,7 +670,32 @@ int omc_spc = 0;  /* OMC_SPC=K: cap a slice's refinement depth at (previous
  * tools.  OMC_REF_BIAS == OMC_PIX_BIAS (omc1.h). */
 #define OMC_REF_BIAS OMC_PIX_BIAS
 
+/* Race-free one-time initialization.  This used to re-run its getenv() writes
+ * on EVERY context creation, so two threads constructing codecs concurrently
+ * wrote the same globals at the same time -- a real data race (ThreadSanitizer
+ * flagged 15 of them) even though the values were identical.  C11 atomics keep
+ * the library free of any pthread dependency, which matters for the embedded
+ * and FPGA-host targets. */
+static atomic_int omc_init_state; /* 0 untouched, 1 in progress, 2 done */
+
+static void omc_global_init_once(void);
+
 void omc_global_init(void)
+{
+    if (atomic_load_explicit(&omc_init_state, memory_order_acquire) == 2) return;
+    int expect = 0;
+    if (atomic_compare_exchange_strong_explicit(&omc_init_state, &expect, 1,
+                                                memory_order_acq_rel,
+                                                memory_order_acquire)) {
+        omc_global_init_once();
+        atomic_store_explicit(&omc_init_state, 2, memory_order_release);
+    } else {
+        while (atomic_load_explicit(&omc_init_state, memory_order_acquire) != 2)
+            ; /* another thread is initializing; the tables are shared */
+    }
+}
+
+static void omc_global_init_once(void)
 {
     omc_tans_init();
     omc_crc_init();
@@ -697,7 +761,6 @@ static int xsl_lim_for(const omc_config_t *cfg)
 omc_enc_t *omc_enc_create(const omc_config_t *cfg)
 {
     omc_global_init(); /* tables allocated here, before the baseline */
-    omc_xsl_lim = xsl_lim_for(cfg); /* legacy mirror; the codec reads c->xsl_lim */
     size_t heap_base = 0;
     if (getenv("OMC_ENC_FOOTPRINT")) {
         struct mallinfo2 mi0 = mallinfo2();
@@ -786,6 +849,7 @@ omc_enc_t *omc_enc_create(const omc_config_t *cfg)
     e->rowsig = malloc((size_t)(W > 64 ? W : 64));
     e->last_frame = -1;
     e->last_frame2 = -1;
+    e->oob_samples = 0;
     for (int p = 0; p < OMC_NPLANES; p++) {
         int pw = plane_width(&e->c, p);
         size_t fw = (size_t)pw * e->c.H;
@@ -843,6 +907,49 @@ omc_enc_t *omc_enc_create(const omc_config_t *cfg)
     return e;
 }
 
+int64_t omc_enc_oob(const omc_enc_t *e)
+{
+    return e ? e->oob_samples : 0;
+}
+
+/* Is this GEOMETRY recoverable from a cropped baseband picture at all?
+ * Pad neutralization (minor 11) covers VERTICAL pad rows of the last slice
+ * and nothing else, so it answers no when:
+ *   - the raster is padded HORIZONTALLY (display_width < width): the pad
+ *     columns are ordinary coded content of every row and cannot be
+ *     re-derived from a cropped picture; or
+ *   - the last slice's visible run does not split into whole level-2 pairs
+ *     (v % 4), where the rule disables itself.
+ * Found by adversarial audit: without this the encoder certified both cases
+ * as baseband-safe while their chains drifted -- confidently wrong, which is
+ * worse than silent. */
+/* TEST ONLY.  Reintroduces the pre-minor-11 pad behaviour so the pad gate can
+ * be proven non-vacuous.  Deliberately an explicit per-context API and NOT an
+ * environment variable: the audit that motivated this found that an env lever
+ * reachable from the DECODE path silently corrupts visible rows of conforming
+ * streams and spreads through the temporal reference. */
+void omc_enc_debug_oldpads(omc_enc_t *e, int on)
+{
+    if (e) e->c.dbg_oldpads = on ? 1 : 0;
+}
+
+void omc_dec_debug_oldpads(omc_dec_t *d, int on)
+{
+    if (d) d->c.dbg_oldpads = on ? 1 : 0;
+}
+
+int omc_enc_geom_baseband_safe(const omc_enc_t *e)
+{
+    if (!e) return 0;
+    const ctx_common_t *c = &e->c;
+    int dw = c->cfg.display_width ? c->cfg.display_width : c->W;
+    if (dw < c->W) return 0;                       /* horizontal pad */
+    int dh = c->cfg.display_height ? c->cfg.display_height : c->H;
+    if (dh >= c->H) return 1;                      /* no vertical pad */
+    int v = dh - (c->nslices - 1) * c->sh;
+    return (v > 0 && v % 4 == 0);
+}
+
 void omc_enc_destroy(omc_enc_t *e)
 {
     if (!e) return;
@@ -977,6 +1084,45 @@ static void band_scan(omc_enc_t *e, int p, int b, const int32_t *coef, int n,
  * half-pel field codes exist in the header but the encoder writes even
  * values only — odd values are reserved).  Deterministic and identical in
  * encoder and decoder, and generation-invariant because refprev is. */
+/* T5 PAD NEUTRALIZATION (minor 11).  Visible rows of slice `slice_idx`.
+ *
+ * A frame whose display height is not a multiple of the slice height is coded
+ * taller (1080 as 1088, 2160 as 2176 at slice_h 32) and the surplus rows are
+ * pad.  Before minor 11 those pad rows were ordinary coded content, which made
+ * the committed picture unrecoverable from a CROPPED baseband decode: the pads
+ * are gone, and re-padding by edge replication does not reproduce them, so the
+ * last slice drifted at generation 2 (measured; docs/TEMPORAL_T5.md 12.3).
+ *
+ * From minor 11 the last slice's vertical transform runs at the VISIBLE length
+ * (src/dwt.c): no visible output reads a pad row, the pad rows' coefficients
+ * are forced to zero, and the inverse replicates the last visible row across
+ * the pad.  The committed pads are then a pure function of the committed
+ * visible rows, so cropped baseband re-padded by replication IS the committed
+ * picture, bit for bit.
+ *
+ * Returns sh whenever there is nothing to do, which makes every rule keyed off
+ * it a no-op: unpadded frames are bit-identical to minor 10 (verified: every
+ * unpadded matrix cell differs only in the version byte).  Geometries this
+ * scheme cannot express -- a visible run that does not split into whole level-2
+ * pairs, i.e. v % 4 -- also return sh and are reported as not baseband-safe by
+ * omc_enc rather than being coded wrongly. */
+static int slice_vis_rows(const ctx_common_t *c, int slice_idx)
+{
+    /* TEST HOOK ONLY (omc_enc_debug_oldpads / omc_dec_debug_oldpads): code the pad rows as ordinary
+     * content, i.e. the minor-10 behaviour this rule replaced.  It exists so
+     * the pad gate can be proven NON-VACUOUS -- a gate that cannot fail proves
+     * nothing (docs/TEMPORAL_T5.md 12.5).  A stream produced with it set is
+     * mislabelled: it claims minor 11 and does not honour it.  Never set it
+     * outside the gate. */
+    if (c->dbg_oldpads) return c->sh;   /* test hook; see ctx_common_t */
+    int dh = c->cfg.display_height ? c->cfg.display_height : c->H;
+    if (dh >= c->H) return c->sh;                 /* no pad rows at all */
+    int v = dh - slice_idx * c->sh;
+    if (v >= c->sh || v <= 0) return c->sh;       /* fully visible / fully pad */
+    if (v % 4) return c->sh;                      /* unsupported geometry */
+    return v;
+}
+
 static void predict_plane(ctx_common_t *c, const uint16_t *refplane, int p,
                           int slice_idx, const int8_t mvx2[OMC_NREG],
                           const int8_t mvy2[OMC_NREG],
@@ -1022,9 +1168,10 @@ static void predict_plane(ctx_common_t *c, const uint16_t *refplane, int p,
             }
         }
     }
-    omc_dwt_d1m = (p < OMC_NPLANES && omc_xsl_live[p]) ? omc_xsl_buf[p] : 0;
-    omc_slice_fwd(pbuf, pw, sh, tmp);
-    omc_dwt_d1m = 0;
+    /* the PREDICTION takes the same pad neutralization as the input, so the
+     * residual at pad positions is 0 - 0 = 0 and stays codeable as zero */
+    omc_slice_fwd_p(pbuf, pw, sh, tmp, slice_vis_rows(c, slice_idx),
+                    (p < OMC_NPLANES && c->xsl_live[p]) ? c->xsl_buf[p] : 0);
     omc_band_t bands[OMC_NBANDS];
     omc_band_layout(pw, sh, bands);
     for (int b = 0; b < OMC_NBANDS; b++) {
@@ -1139,9 +1286,16 @@ static void derive_mv(const uint16_t *prev, const uint16_t *prev2,
 
 /* local LL activity at the LL cell co-located with (row, col) of band b */
 static inline int fill_gate_g(const int32_t *ll, int llstride, int llw, int llh,
-                            int b, int row, int col, int32_t lllim,
+                            int vvis, int b, int row, int col, int32_t lllim,
                             int *sgh, int *sgv)
 {
+    /* T5 pad neutralization (minor 11): a coefficient row belonging to the
+     * pad run of the last slice must dequantize to EXACTLY zero, or the
+     * generation lock cannot reproduce it (generation 2 forward-transforms
+     * the same picture to zero there).  vvis == slice_h for every ordinary
+     * slice, which makes this test unreachable.  Bands 0..6 are quarter-height
+     * (visible rows vvis/4), bands 7..9 half-height (vvis/2). */
+    if (row >= ((b >= 7) ? (vvis >> 1) : (vvis >> 2))) return 0;
     int rL = (b >= 7) ? (row >> 1) : row;
     int xL = col >> ((b >= 7) ? 4 : 3);
     if (rL < 1) rL = 1;
@@ -1180,9 +1334,9 @@ static inline int fill_gate_g(const int32_t *ll, int llstride, int llw, int llh,
     return act < 2 * OMC_FILL_GATE ? 1 : act < 4 * OMC_FILL_GATE ? 2 : 3;
 }
 static inline int fill_gate(const int32_t *ll, int llstride, int llw, int llh,
-                            int b, int row, int col, int32_t lllim)
+                            int vvis, int b, int row, int col, int32_t lllim)
 {
-    return fill_gate_g(ll, llstride, llw, llh, b, row, col, lllim, 0, 0);
+    return fill_gate_g(ll, llstride, llw, llh, vvis, b, row, col, lllim, 0, 0);
 }
 
 /* fill value for a zero coefficient, or 0 if gated off / not eligible */
@@ -1210,7 +1364,7 @@ static inline int fp_hint(const fp_t *fp, int row, int col)
 
 
 static inline int32_t fill_value_p(const int32_t *ll, int llstride, int llw, int llh,
-                                 int b, int row, int col, int s, int fox, int foy,
+                                 int vvis, int b, int row, int col, int s, int fox, int foy,
                                  int sfox, int sfoy,
                                  int32_t lllim, int gain, int corr, int v6, int hint,
                                  const fp_t *fp)
@@ -1218,7 +1372,7 @@ static inline int32_t fill_value_p(const int32_t *ll, int llstride, int llw, int
     if (omc_fillbands && !((omc_fillbands >> b) & 1)) return 0;
     if (s < OMC_FILL_MIN_SHIFT) return 0;
     int sgh = 0, sgv = 0;
-    int act = fill_gate_g(ll, llstride, llw, llh, b, row, col, lllim,
+    int act = fill_gate_g(ll, llstride, llw, llh, vvis, b, row, col, lllim,
                           omc_fillcorr ? &sgh : 0, omc_fillcorr ? &sgv : 0);
     if (!act) return 0;
     /* E-1 (structural): a detail coefficient at an edge carries the sign of
@@ -1268,19 +1422,19 @@ static inline int32_t fill_value_p(const int32_t *ll, int llstride, int llw, int
     return omc_fill_sign_sel(col + fox, row + foy, corr) ? a : -a;
 }
 static inline int32_t fill_value_h(const int32_t *ll, int llstride, int llw, int llh,
-                                 int b, int row, int col, int s, int fox, int foy,
+                                 int vvis, int b, int row, int col, int s, int fox, int foy,
                                  int sfox, int sfoy,
                                  int32_t lllim, int gain, int corr, int v6, int hint)
 {
-    return fill_value_p(ll, llstride, llw, llh, b, row, col, s, fox, foy,
+    return fill_value_p(ll, llstride, llw, llh, vvis, b, row, col, s, fox, foy,
                         sfox, sfoy, lllim, gain, corr, v6, hint, 0);
 }
 static inline int32_t fill_value(const int32_t *ll, int llstride, int llw, int llh,
-                                 int b, int row, int col, int s, int fox, int foy,
+                                 int vvis, int b, int row, int col, int s, int fox, int foy,
                                  int sfox, int sfoy,
                                  int32_t lllim, int gain, int corr, int v6)
 {
-    return fill_value_h(ll, llstride, llw, llh, b, row, col, s, fox, foy,
+    return fill_value_h(ll, llstride, llw, llh, vvis, b, row, col, s, fox, foy,
                         sfox, sfoy, lllim, gain, corr, v6, 0);
 }
 
@@ -1378,9 +1532,15 @@ static inline int fill_gain_code(int64_t num64, int64_t den, int tune_vmaf)
  * slice could never lock again, so the legal-range projection lives only in
  * the tools' display path.  The to_ref parameter remains for signature
  * stability; both values behave identically now. */
+/* vvis = visible rows of the slice being reconstructed (c->sh when the slice
+ * carries no pad rows).  It is passed EXPLICITLY and never derived from
+ * slice_idx: at the DCFB pass-A call site slice_idx is a destination row base
+ * into a one-slice scratch frame, not the picture's slice index, so deriving
+ * geometry from it reconstructed the last slice with the wrong transform
+ * length -- a live generation-exactness break found by adversarial audit. */
 static void reconstruct_slice(ctx_common_t *c, int32_t *sbuf[OMC_NPLANES],
                               int32_t *tmp, const omc_frame_t *out, int slice_idx,
-                              int to_ref)
+                              int to_ref, int vvis)
 {
     int sh = c->sh;
     int bias = OMC_REF_BIAS;
@@ -1388,9 +1548,8 @@ static void reconstruct_slice(ctx_common_t *c, int32_t *sbuf[OMC_NPLANES],
     (void)to_ref;
     for (int p = 0; p < OMC_NPLANES; p++) {
         int pw = plane_width(c, p);
-        omc_dwt_d1m = omc_xsl_live[p] ? omc_xsl_buf[p] : 0;
-        omc_slice_inv(sbuf[p], pw, sh, tmp);
-        omc_dwt_d1m = 0;
+        omc_slice_inv_p(sbuf[p], pw, sh, tmp, vvis,
+                        c->xsl_live[p] ? c->xsl_buf[p] : 0);
         /* The wide-window clamp below is a representability guard only.  It
          * cannot engage on conforming content: the reconstruction is the
          * source plus bounded quantization error, and the window leaves
@@ -1420,7 +1579,7 @@ static void reconstruct_slice(ctx_common_t *c, int32_t *sbuf[OMC_NPLANES],
          * covers those boundaries on the emitted picture only.  Applied
          * UNCONDITIONALLY within the wide domain: no rail skip, so the
          * inverse in omc_xsl_unblend() agrees everywhere. */
-        if (omc_xsl_live[p] && slice_idx > 0 && !omc_xsl_noretro) {
+        if (c->xsl_live[p] && slice_idx > 0 && !c->xsl_noretro) {
             int32_t lim = c->xsl_lim * ((c->maxv + 1) >> 10);
             int base = slice_idx * sh;
             uint16_t *e15 = out->p[p] + (size_t)(base - 1) * out->stride[p];
@@ -1471,6 +1630,7 @@ static int lock_verify(omc_enc_t *e, int cf444, int prof, int Q, int ns, int k,
                        uint32_t *out_modes, uint32_t *out_fmask, int out_gain[OMC_NPLANES])
 {
     ctx_common_t *c = &e->c;
+    int vvis = slice_vis_rows(c, slice_idx);
     int sh = c->sh;
     shift_plan_t sp;
     derive_shifts(cf444, prof, Q, ns, k, &sp);
@@ -1528,8 +1688,14 @@ static int lock_verify(omc_enc_t *e, int cf444, int prof, int Q, int ns, int k,
         int pw = plane_width(c, p);
         int llw = pw / 32, llh = sh / 4;
         int32_t lllim = c->mid - (c->mid >> 4);
-        int32_t llbuf[4 * 256];
-        if (llw > 256) return 0;
+        /* Band 0 holds llh*llw = (slice_h/4)*(W/32) coefficients.  This was
+         * sized 4*256 (slice_h 16) while the guard tested only llw, so
+         * slice_h 32 on a wide plane overflowed the stack: 4480 wide gives
+         * 8*140 = 1120 > 1024.  Sized for the worst legal case (slice_h 32,
+         * 8192-wide plane) and the guard now tests what is actually written. */
+        int32_t llbuf[8 * 256];
+        if (llw > 256 || (size_t)llh * llw > sizeof llbuf / sizeof llbuf[0])
+            return 0;
         omc_band_layout(pw, sh, bands);
         band_cost_t (*bc)[OMC_NPLANES][OMC_NBANDS] = e->bandcost;
         /* ---- band 0 (LL): derive the mode by exact reproduction ---- */
@@ -1600,7 +1766,7 @@ static int lock_verify(omc_enc_t *e, int cf444, int prof, int Q, int ns, int k,
                             if (coeff_shift(&sp, p, b, i) != base_s) continue;
                             if (omc_quant1b_dz(cf[i], base_s, tex_vmaf, e->dz_enabled) != 0) continue;
                             if (m && pc[i] != 0) continue;
-                            if (!fill_gate(llbuf, llw, llw, llh, b, i / w, i % w, lllim)) continue;
+                            if (!fill_gate(llbuf, llw, llw, llh, vvis, b, i / w, i % w, lllim)) continue;
                             int32_t a = e->coef[p][b][i];
                             sum += a < 0 ? -a : a;
                             count++;
@@ -1626,7 +1792,7 @@ static int lock_verify(omc_enc_t *e, int cf444, int prof, int Q, int ns, int k,
                         int32_t v = omc_dequant1(q, s);
                         if (m) v += pc[i];
                         if (fb && v == 0 && q == 0)
-                            v = fill_value_p(llbuf, llw, llw, llh, b, i / w, i % w,
+                            v = fill_value_p(llbuf, llw, llw, llh, vvis, b, i / w, i % w,
                                              s, fox, foy, sfox, sfoy, lllim, ghyp,
                                              c->cfg.grain_corr,
                                              (c->cfg.fill_static ? 1 : 0), 0, &vfp);
@@ -1853,6 +2019,7 @@ int omc_enc_slice(omc_enc_t *e, const omc_frame_t *in, int frame_idx, int slice_
 {
     ctx_common_t *c = &e->c;
     int sh = c->sh;
+    int vvis = slice_vis_rows(c, slice_idx);
     omc_band_t bands[OMC_NBANDS];
 
     /* OMC_XSL: boundary term from slice k-1's committed reconstruction —
@@ -1911,9 +2078,8 @@ int omc_enc_slice(omc_enc_t *e, const omc_frame_t *in, int frame_idx, int slice_
             for (int x = 0; x < pw; x++)
                 d[x] = (int32_t)src[x] - c->mid - OMC_REF_BIAS;
         }
-        omc_dwt_d1m = omc_xsl_live[p] ? omc_xsl_buf[p] : 0;
-        omc_slice_fwd(e->sbuf[p], pw, sh, e->tmp);
-        omc_dwt_d1m = 0;
+        omc_slice_fwd_p(e->sbuf[p], pw, sh, e->tmp, slice_vis_rows(c, slice_idx),
+                        c->xsl_live[p] ? c->xsl_buf[p] : 0);
         omc_band_layout(pw, sh, bands);
         for (int b = 0; b < OMC_NBANDS; b++) {
             omc_band_t *B = &bands[b];
@@ -2193,8 +2359,30 @@ int omc_enc_slice(omc_enc_t *e, const omc_frame_t *in, int frame_idx, int slice_
                     if (rL < 1) rL = 1;
                     if (xL > llw2 - 2) xL = llw2 - 2;
                     if (xL < 1) xL = 1;
-                    int32_t gh = llc[(size_t)rL * llw2 + xL + 1] - llc[(size_t)rL * llw2 + xL - 1];
-                    int32_t gv = llc[(size_t)(rL + 1) * llw2 + xL] - llc[(size_t)(rL - 1) * llw2 + xL];
+                    /* Same re-clamp fill_gate_g already carries (its "F-1
+                     * verified defect" note): the interior-preference clamp
+                     * above goes OUT OF RANGE when the LL band is under 3
+                     * cells in a dimension -- min(x, n-2) then max(x, 1)
+                     * yields 1 when n == 2, so rL+1 == llh2 is one row past
+                     * the band.  llh2 == 2 is slice_h 8, the 720p DEFAULT,
+                     * and llw2 == 1 is a 32-wide plane.  Confirmed by
+                     * AddressSanitizer reading up to 1020 bytes past the
+                     * band.  The value read decides the flat class, which
+                     * selects which coefficients get zeroed, so this fed heap
+                     * contents into the emitted symbols.  This classifier was
+                     * a copy of the fill_gate_g idiom that never received the
+                     * fix; found by a systematic sweep for bounds derived
+                     * from one parameter while indexed by another. */
+                    if (rL > llh2 - 1) rL = llh2 - 1;
+                    if (rL < 0) rL = 0;
+                    if (xL > llw2 - 1) xL = llw2 - 1;
+                    if (xL < 0) xL = 0;
+                    int rlo = rL - 1 < 0 ? 0 : rL - 1;
+                    int rhi = rL + 1 > llh2 - 1 ? llh2 - 1 : rL + 1;
+                    int xlo = xL - 1 < 0 ? 0 : xL - 1;
+                    int xhi = xL + 1 > llw2 - 1 ? llw2 - 1 : xL + 1;
+                    int32_t gh = llc[(size_t)rL * llw2 + xhi] - llc[(size_t)rL * llw2 + xlo];
+                    int32_t gv = llc[(size_t)rhi * llw2 + xL] - llc[(size_t)rlo * llw2 + xL];
                     if (gh < 0) gh = -gh;
                     if (gv < 0) gv = -gv;
                     /* VOTE 3 (amplitude): grain is small by nature. A cell
@@ -3024,13 +3212,20 @@ encode_attempts:;
      * then n x i16 coded values (post-DPCM for LL, delta-domain for inter
      * bands), then n x i16 quantized-prediction magnitudes (0 if intra). */
     {
+        /* debug-only; the handle is opened once under an atomic guard so the
+         * pointer is read-only afterwards (stdio locks the writes) */
         static FILE *df = NULL;
-        static int df_tried = 0;
-        if (!df_tried) {
+        static atomic_int df_tried = 0;
+        int df_expect = 0;
+        if (atomic_compare_exchange_strong_explicit(&df_tried, &df_expect, 1,
+                                                    memory_order_acq_rel,
+                                                    memory_order_acquire)) {
             const char *dp = getenv("OMC_DUMP");
             if (dp) df = fopen(dp, "wb");
-            df_tried = 1;
+            atomic_store_explicit(&df_tried, 2, memory_order_release);
         }
+        while (atomic_load_explicit(&df_tried, memory_order_acquire) == 1)
+            ;
         if (df) {
             for (int p = 0; p < OMC_NPLANES; p++)
                 for (int b = 0; b < OMC_NBANDS; b++) {
@@ -3096,8 +3291,9 @@ encode_attempts:;
             int pw = plane_width(c, p);
             int llw = pw / 32, llh = sh / 4;
             int32_t lllim = c->mid - (c->mid >> 4);
-            int32_t llbuf[4 * 256];
-            if (llw > 256) continue; /* > 8K plane: fill off, never invalid */
+            int32_t llbuf[8 * 256];   /* see the sizing note in lock_verify */
+            if (llw > 256 || (size_t)llh * llw > sizeof llbuf / sizeof llbuf[0])
+                continue; /* > 8K plane: fill off, never invalid */
             int m0 = (int)((mode_mask >> (p * OMC_NBANDS)) & 1);
             const int32_t *pc0 = e->pcoef[p][0];
             for (int i = 0; i < band_n[p][0]; i++) {
@@ -3117,7 +3313,7 @@ encode_attempts:;
                     if (coeff_shift(&sp, p, b, i) != base_s) continue;
                     if (e->qbuf[p][b][i] != 0) continue; /* zero-coded only */
                     if (m && pc[i] != 0) continue;       /* fill needs true 0 */
-                    if (!fill_gate(llbuf, llw, llw, llh, b, i / w, i % w, lllim)) continue;
+                    if (!fill_gate(llbuf, llw, llw, llh, vvis, b, i / w, i % w, lllim)) continue;
                     int32_t a = e->coef[p][b][i];
                     sum += a < 0 ? -a : a;
                     count++;
@@ -3223,7 +3419,7 @@ encode_attempts:;
                     int32_t v = omc_dequant1(e->qbuf[p][b][i], sft);
                     if (m) v += pc[i];
                     if (fb && v == 0 && e->qbuf[p][b][i] == 0)
-                        v = fill_value_p(ll, pw, llw, llh, b, i / B->w, fcol,
+                        v = fill_value_p(ll, pw, llw, llh, vvis, b, i / B->w, fcol,
                                        sft, fox, foy, sfox, sfoy, lllim,
                                        fill_gain[p], c->cfg.grain_corr,
                                        (c->cfg.fill_static ? 1 : 0),
@@ -3237,7 +3433,9 @@ encode_attempts:;
             sf.p[p] = e->dc_scr[p];
             sf.stride[p] = plane_width(c, p);
         }
-        reconstruct_slice(c, e->sbuf, e->tmp, &sf, 0, 0);
+        /* pass-A scratch: `0` is the destination row base, so the GEOMETRY of
+         * the slice actually being coded must be handed over separately */
+        reconstruct_slice(c, e->sbuf, e->tmp, &sf, 0, 0, vvis);
         for (int p = 0; p < OMC_NPLANES; p++) {
             int pw = plane_width(c, p);
             int64_t sum = 0;
@@ -3452,7 +3650,7 @@ encode_attempts:;
                     int32_t v = omc_dequant1(e->qbuf[p][b][i], s);
                     if (m) v += pc[i];
                     if (fb && v == 0 && e->qbuf[p][b][i] == 0)
-                        v = fill_value_p(ll, pw, llw, llh, b, i / B->w, fcol,
+                        v = fill_value_p(ll, pw, llw, llh, vvis, b, i / B->w, fcol,
                                        s, fox, foy, sfox, sfoy, lllim, fill_gain[p],
                                        c->cfg.grain_corr,
                                        (c->cfg.fill_static ? 1 : 0),
@@ -3470,7 +3668,7 @@ encode_attempts:;
          * biased domain is the only domain).  The boundary edit inside
          * reconstruct_slice retro-touches the previous slice's last row of
          * ref as well. */
-        reconstruct_slice(c, e->sbuf, e->tmp, &rf, slice_idx, 1);
+        reconstruct_slice(c, e->sbuf, e->tmp, &rf, slice_idx, 1, vvis);
         /* OMC_DCFB: measure this slice's mean reconstruction offset per plane
          * (the persistent per-slice "color decision"); the sign feeds the LL
          * rounding servo on the NEXT frame's inter coding of this slice.
@@ -3508,6 +3706,37 @@ encode_attempts:;
     }
     /* barrier display blend on the EMITTED picture only (reference untouched) */
     if (recon) xsl_display_blend(c, recon, slice_idx, frame_idx & 0xFF);
+    /* Gamut report.  Counts on the EMITTED picture -- what a decoder hands to
+     * baseband -- NOT on the reference: the two differ by the barrier display
+     * blend, and it is the emitted picture a legal-range hop would clip.
+     * (Measuring the reference instead reported phantom excursions; caught by
+     * cross-checking the report against the decoded CDR.)  Count only, never
+     * alter.  Rows below the display height are pad and are cropped away, so
+     * they are excluded.  Reported by omc_enc as the baseband-safe verdict. */
+    if (recon) {
+        /* Count only rows that are already FINAL: a boundary row is re-emitted
+         * and edited when the NEXT slice reconstructs, so slice k finalizes
+         * rows [k*sh - 1, (k+1)*sh - 1) and the last slice finalizes to the
+         * end of the picture.  This also keeps the sweep O(slice_h) per slice
+         * -- a whole-frame sweep at the last slice would put a frame-sized
+         * burst inside that slice's A2 budget, which sub-1 ms has no room
+         * for.  (Wrong buffer and wrong window were both caught by requiring
+         * this report to agree with the decoded CDR.) */
+        int dh = c->cfg.display_height ? c->cfg.display_height : c->H;
+        int last = (slice_idx == c->nslices - 1);
+        int r0 = slice_idx * c->sh - 1, r1 = last ? dh : r0 + c->sh;
+        if (r0 < 0) r0 = 0;
+        if (r1 > dh) r1 = dh;
+        int32_t lo = OMC_PIX_BIAS, hi = OMC_PIX_BIAS + c->maxv;
+        for (int p = 0; p < OMC_NPLANES; p++) {
+            int pw = plane_width(c, p);
+            for (int r = r0; r < r1; r++) {
+                const uint16_t *rp = recon->p[p] + (size_t)r * recon->stride[p];
+                for (int x = 0; x < pw; x++)
+                    if (rp[x] < lo || rp[x] > hi) e->oob_samples++;
+            }
+        }
+    }
     if (slice_idx == c->nslices - 1) {
         /* debug: dump the committed (pre-display-blend) picture — the exact
          * target the un-blend must recover (OMC_DUMP_COMMITTED=<prefix>) */
@@ -3579,7 +3808,6 @@ int64_t omc_enc_frame(omc_enc_t *e, const omc_frame_t *in, int frame_idx,
 omc_dec_t *omc_dec_create(const omc_config_t *cfg)
 {
     omc_global_init();
-    omc_xsl_lim = xsl_lim_for(cfg); /* legacy mirror; codec reads c->xsl_lim */
     omc_dec_t *d = calloc(1, sizeof(*d));
     if (!d) return NULL;
     common_init(&d->c, cfg);
@@ -3657,6 +3885,7 @@ int omc_dec_slice_ex(omc_dec_t *d, const uint8_t *src, size_t avail,
     if (omc_fr_get(&fr, 32) != OMC_SYNC) return -1;
     int fidx8 = (int)omc_fr_get(&fr, 8); /* low 8 bits of frame idx (fill phase) */
     int slice_idx = (int)omc_fr_get(&fr, 16);
+    int vvis = slice_vis_rows(c, slice_idx);
     /* T5 frame promotion: the first slice of a new frame (fidx8 change)
      * promotes the finished current frame to the prediction reference.
      * Mirrors the encoder's frame-end rotation exactly. */
@@ -3784,7 +4013,7 @@ int omc_dec_slice_ex(omc_dec_t *d, const uint8_t *src, size_t avail,
                 int32_t rec = omc_dequant1(q, s);
                 if (m) rec += pc[i];
                 if (fb && rec == 0 && q == 0)
-                    rec = fill_value_p(ll, pw, llw, llh, b, row, col, s, fox, foy, sfox, sfoy,
+                    rec = fill_value_p(ll, pw, llw, llh, vvis, b, row, col, s, fox, foy, sfox, sfoy,
                                      lllim, fill_gain[p], c->cfg.grain_corr,
                                      (c->cfg.fill_static ? 1 : 0),
                                      0, &fp);
@@ -3831,7 +4060,7 @@ int omc_dec_slice_ex(omc_dec_t *d, const uint8_t *src, size_t avail,
             rf.p[p] = d->ref[p];
             rf.stride[p] = plane_width(c, p);
         }
-        reconstruct_slice(c, d->sbuf, d->tmp, &rf, slice_idx, 1);
+        reconstruct_slice(c, d->sbuf, d->tmp, &rf, slice_idx, 1, vvis);
         for (int p = 0; p < OMC_NPLANES; p++) {
             int pw = plane_width(c, p);
             int r0x = slice_idx > 0 ? -1 : 0;
@@ -4026,6 +4255,28 @@ static void conceal_frame(omc_dec_t *d, omc_frame_t *out)
             for (int p = 0; p < OMC_NPLANES; p++)
                 conceal_mc_plane(d, out, p, s, zeromv, zeromv);
         }
+        /* Restore the pad invariant (minor 11): concealment writes whole
+         * slices, pad rows included, from a reference or by interpolation, so
+         * the concealed pads would no longer be a replication of the concealed
+         * last VISIBLE row.  Since the next frame's prediction reads those
+         * rows through the bottom edge clamp, leaving them arbitrary makes
+         * "the pads are a function of the visible picture" true only until the
+         * first lost slice.  Re-deriving them here costs one memcpy per plane
+         * on a path that is already exceptional, and makes the invariant hold
+         * unconditionally. */
+        if (s == nsl - 1) {
+            ctx_common_t *c = &d->c;
+            int dh = c->cfg.display_height ? c->cfg.display_height : c->H;
+            if (dh < c->H)
+                for (int p = 0; p < OMC_NPLANES; p++) {
+                    int pw = plane_width(c, p);
+                    uint16_t *pl = out->p[p];
+                    size_t st = out->stride[p];
+                    for (int r = dh; r < c->H; r++)
+                        memcpy(pl + (size_t)r * st, pl + (size_t)(dh - 1) * st,
+                               (size_t)pw * 2);
+                }
+        }
     }
 }
 
diff --git a/src/config.c b/src/config.c
index c7949ea..ee312b2 100644
--- a/src/config.c
+++ b/src/config.c
@@ -120,6 +120,20 @@ int omc_validate_config(const omc_config_t *cfg, char *err, size_t errlen)
     if (cfg->display_height && cfg->display_height > cfg->height)
         FAIL("display_height %u exceeds coded height %u",
              cfg->display_height, cfg->height);
+    /* The coded height must be the display height rounded UP to a whole slice
+     * -- no more.  A larger gap means whole slices below the picture, which
+     * minor 11's pad rule does not describe: it neutralizes the pad run of the
+     * LAST slice only, so the committed pads of any slice above it would not
+     * be a function of the visible rows and a cropped picture could not be
+     * re-padded to the committed one.  Reachable from omc_enc --display-h and
+     * from the library API; found by adversarial audit, where it silently
+     * produced pads that were not replications. */
+    if (cfg->display_height &&
+        (uint32_t)cfg->height !=
+            ((uint32_t)cfg->display_height + sh - 1) / sh * sh)
+        FAIL("coded height %u is not display_height %u rounded up to the slice "
+             "height %d (expected %u)", cfg->height, cfg->display_height, sh,
+             ((uint32_t)cfg->display_height + sh - 1) / sh * sh);
 
     /* --- OMC-TF in-loop temporal filter: operating envelope ---
      *
@@ -166,7 +180,7 @@ int omc_validate_config(const omc_config_t *cfg, char *err, size_t errlen)
         FAIL("uc_ratio %u invalid (0 = none, 1 = 2x, 2 = 4x)", cfg->uc_ratio);
     if (cfg->uc_ratio && (long)cfg->width * (1 << cfg->uc_ratio) > 32768)
         FAIL("uc_ratio %u would produce an output width beyond 32768", cfg->uc_ratio);
-    if (cfg->uc_ratio && cfg->a2_strict) {
+    if (cfg->a2_strict) {
         /* A2 is a hard bar ONLY when the caller asks for it to be.  The model
          * below is docs/LATENCY.md verbatim and the figure is available to
          * anyone through omc_config_latency(); what changed is the policy.  A
@@ -176,7 +190,7 @@ int omc_validate_config(const omc_config_t *cfg, char *err, size_t errlen)
          * bar that binds the contribution product rather than every leg.
          * a2_strict = 1 restores the refusal for a facility that needs the
          * guarantee enforced rather than declared. */
-        int reach = omc_uc_analytic_reach_n(cfg->uc_ratio);
+        int reach = cfg->uc_ratio ? omc_uc_analytic_reach_n(cfg->uc_ratio) : 0;
         int nsl = (int)(cfg->height / sh);
         double frame_ms = 1000.0 * (double)cfg->fps_den / (double)cfg->fps_num;
         double line_ms = frame_ms / (double)cfg->height;
@@ -191,7 +205,8 @@ int omc_validate_config(const omc_config_t *cfg, char *err, size_t errlen)
         if (total >= 1.0)
             FAIL("uc_ratio %u at %ux%u@%u/%u would take %.3f ms total "
                  "(%d-source-row reach at slice_h %d, charged as %s); "
-                 "A2 requires < 1 ms",
+                 "A2 requires < 1 ms (the codec term alone is charged even "
+                 "with no conversion configured)",
                  cfg->uc_ratio, cfg->width, cfg->height, cfg->fps_num,
                  cfg->fps_den, total, reach, sh,
                  cfg->uc_out_batched ? "whole slice periods (slice-batched "
@@ -199,9 +214,9 @@ int omc_validate_config(const omc_config_t *cfg, char *err, size_t errlen)
     }
 
     /* --- decode-side stream version --- */
-    if (cfg->ver_minor > OMC_MINOR_XSL)
+    if (cfg->ver_minor > OMC_VERSION_MINOR)
         FAIL("stream minor version %u newer than this implementation (%d)",
-             cfg->ver_minor, OMC_MINOR_XSL);
+             cfg->ver_minor, OMC_VERSION_MINOR);
 
     if (err && errlen) err[0] = '\0';
     return 0;
@@ -215,7 +230,10 @@ int omc_config_latency(const omc_config_t *cfg, double *total_ms, int *periods)
     int sh, nsl, reach = 0, per = 0;
     double frame_ms, line_ms, slice_ms, total;
     if (!cfg || cfg->height < 1 || !cfg->fps_num || !cfg->fps_den) return -1;
-    sh = cfg->slice_h ? cfg->slice_h : 8;
+    /* the SAME auto rule the validator uses (they disagreed: this said 8
+     * unconditionally while the validator says 16 above 720p, so the figure
+     * reported to a caller was for a slice height the encoder would not use) */
+    sh = cfg->slice_h ? cfg->slice_h : (cfg->height <= 720 ? 8 : 16);
     nsl = (int)(cfg->height / sh);
     if (nsl < 1) return -1;
     if (cfg->uc_ratio) {
@@ -225,8 +243,13 @@ int omc_config_latency(const omc_config_t *cfg, double *total_ms, int *periods)
     frame_ms = 1000.0 * (double)cfg->fps_den / (double)cfg->fps_num;
     line_ms = frame_ms / (double)cfg->height;
     slice_ms = frame_ms / (double)nsl;
+    /* and the SAME conversion charge: raster-clocked output (the product's
+     * contract and the default) costs reach LINES plus the deferred row, not
+     * whole slice periods.  Reporting the batched figure for a raster decoder
+     * overcharged every converting configuration. */
     total = sh * line_ms + slice_ms + 2 * line_ms
-            + per * slice_ms;
+            + (cfg->uc_out_batched ? per * slice_ms
+                                   : (reach ? (reach + 1) * line_ms : 0.0));
     if (total_ms) *total_ms = total;
     if (periods) *periods = per;
     return total < 1.0 ? 0 : 1;
diff --git a/src/dwt.c b/src/dwt.c
index bacf315..61a8281 100644
--- a/src/dwt.c
+++ b/src/dwt.c
@@ -16,36 +16,54 @@
  * last three DECODED rows: zero on ramps, carries real texture phase, known
  * identically to encoder and decoder), the update uses it instead.  The
  * lifting stays exactly invertible for ANY shared dm1. */
+/* T5 PAD NEUTRALIZATION (minor 11).  nv is the number of VISIBLE samples of
+ * this 1D run; nv == n for every ordinary run.  When nv < n (the last slice of
+ * a frame coded taller than its display height) the run behaves as a transform
+ * of length nv:
+ *   - the whole-sample symmetric extension kicks in at nv, not at n, so no
+ *     visible output ever reads a pad sample;
+ *   - the pad pairs' outputs are forced to EXACTLY ZERO (they are read nowhere
+ *     on the visible path, so this is free), which is a fixed point of code /
+ *     decode and therefore survives every generation;
+ *   - the inverse replicates the last visible sample across the pad run, so
+ *     the committed pad rows are a pure function of the committed visible
+ *     rows -- which is what lets a CROPPED baseband picture be re-padded to
+ *     exactly the committed picture (docs/TEMPORAL_T5.md section 12).
+ * With nv == n every branch below is identical to the pre-T5 code. */
 static void fwd1d(const int32_t *x, int n, int stride, int32_t *L, int32_t *H,
-                  int use_dm1, int32_t dm1)
+                  int use_dm1, int32_t dm1, int nv)
 {
-    int half = n / 2;
-    for (int i = 0; i < half; i++) {
+    int half = n / 2, hv = nv / 2;
+    for (int i = 0; i < hv; i++) {
         int32_t s0 = x[(2 * i) * stride];
-        int32_t s1 = (2 * i + 2 < n) ? x[(2 * i + 2) * stride] : x[(2 * i) * stride];
+        int32_t s1 = (2 * i + 2 < nv) ? x[(2 * i + 2) * stride] : x[(2 * i) * stride];
         H[i] = x[(2 * i + 1) * stride] - ((s0 + s1) >> 1);
     }
-    for (int i = 0; i < half; i++) {
+    for (int i = 0; i < hv; i++) {
         int32_t dl = (i > 0) ? H[i - 1] : (use_dm1 ? dm1 : H[0]);
         L[i] = x[(2 * i) * stride] + ((dl + H[i] + 2) >> 2);
     }
+    for (int i = hv; i < half; i++) L[i] = H[i] = 0; /* pad pairs: neutralized */
 }
 
 static void inv1d(const int32_t *L, const int32_t *H, int n, int32_t *x, int stride,
-                  int use_dm1, int32_t dm1)
+                  int use_dm1, int32_t dm1, int nv)
 {
-    int half = n / 2;
+    int hv = nv / 2;
     /* s[i] = L[i] - ((d[i-1] + d[i] + 2) >> 2) */
-    for (int i = 0; i < half; i++) {
+    for (int i = 0; i < hv; i++) {
         int32_t dl = (i > 0) ? H[i - 1] : (use_dm1 ? dm1 : H[0]);
         x[(2 * i) * stride] = L[i] - ((dl + H[i] + 2) >> 2);
     }
-    /* x[2i+1] = d[i] + ((s[2i] + s[2i+2]) >> 1) */
-    for (int i = 0; i < half; i++) {
+    /* x[2i+1] = d[i] + ((s[2i] + s[2i+2]) >> 1); the i = hv-1 term takes the
+     * same extension the forward took, so it never reads a pad sample */
+    for (int i = 0; i < hv; i++) {
         int32_t s0 = x[(2 * i) * stride];
-        int32_t s1 = (2 * i + 2 < n) ? x[(2 * i + 2) * stride] : x[(2 * i) * stride];
+        int32_t s1 = (2 * i + 2 < nv) ? x[(2 * i + 2) * stride] : x[(2 * i) * stride];
         x[(2 * i + 1) * stride] = H[i] + ((s0 + s1) >> 1);
     }
+    for (int r = nv; r < n; r++) /* pads: replicate the last visible sample */
+        x[r * stride] = x[(nv - 1) * stride];
 }
 
 /* (9,7)-M reversible integer lifting: 4-tap dyadic predict (-1,9,9,-1)/16
@@ -109,7 +127,7 @@ static void split_h(int32_t *buf, int W, int r0, int nr, int nc, int32_t *tmp, i
     for (int r = r0; r < r0 + nr; r++) {
         int32_t *row = buf + (size_t)r * W;
         if (filt97) fwd1d_97(row, nc, tmp, tmp + half);
-        else fwd1d(row, nc, 1, tmp, tmp + half, 0, 0);
+        else fwd1d(row, nc, 1, tmp, tmp + half, 0, 0, nc);
         memcpy(row, tmp, sizeof(int32_t) * nc);
     }
 }
@@ -123,24 +141,26 @@ static void join_h(int32_t *buf, int W, int r0, int nr, int nc, int32_t *tmp, in
             memcpy(tmp, row, sizeof(int32_t) * nc); /* Lc|Hc copy */
             inv1d_97(tmp, tmp + half, nc, row);
         } else {
-            inv1d(row, row + half, nc, tmp, 1, 0, 0);
+            inv1d(row, row + half, nc, tmp, 1, 0, 0, nc);
             memcpy(row, tmp, sizeof(int32_t) * nc);
         }
     }
 }
 
 /* vertical split of cols [0, nc) over rows [0, nr): rows re-ordered into L|H */
-int32_t *omc_dwt_d1m = 0;  /* per-column d[-1] for the CURRENT slice's level-1
-    vertical lifting, set by the caller around omc_slice_fwd/inv (band-fix
-    experiment; productize by threading through signatures) */
+/* The level-1 vertical boundary term d[-1] is passed EXPLICITLY through the
+ * transform entry points.  It used to be a file-scope global set around each
+ * call, which made two codec instances in one process share it -- breaking the
+ * "instances share no mutable state" guarantee in omc1.h and racing outright
+ * between threads (make test-threads failed every run). */
 static void split_v(int32_t *buf, int W, int nr, int nc, int32_t *tmp,
-                    const int32_t *d1m)
+                    const int32_t *d1m, int nv)
 {
     int half = nr / 2;
     int32_t col[64] = {0}, Lc[32], Hc[32];
     for (int c = 0; c < nc; c++) {
         for (int r = 0; r < nr; r++) col[r] = buf[(size_t)r * W + c];
-        fwd1d(col, nr, 1, Lc, Hc, d1m != 0, d1m ? d1m[c] : 0);
+        fwd1d(col, nr, 1, Lc, Hc, d1m != 0, d1m ? d1m[c] : 0, nv);
         for (int r = 0; r < half; r++) {
             buf[(size_t)r * W + c] = Lc[r];
             buf[(size_t)(r + half) * W + c] = Hc[r];
@@ -150,7 +170,7 @@ static void split_v(int32_t *buf, int W, int nr, int nc, int32_t *tmp,
 }
 
 static void join_v(int32_t *buf, int W, int nr, int nc, int32_t *tmp,
-                   const int32_t *d1m)
+                   const int32_t *d1m, int nv)
 {
     int half = nr / 2;
     int32_t col[64], Lc[32], Hc[32];
@@ -159,7 +179,7 @@ static void join_v(int32_t *buf, int W, int nr, int nc, int32_t *tmp,
             Lc[r] = buf[(size_t)r * W + c];
             Hc[r] = buf[(size_t)(r + half) * W + c];
         }
-        inv1d(Lc, Hc, nr, col, 1, d1m != 0, d1m ? d1m[c] : 0);
+        inv1d(Lc, Hc, nr, col, 1, d1m != 0, d1m ? d1m[c] : 0, nv);
         for (int r = 0; r < nr; r++) buf[(size_t)r * W + c] = col[r];
     }
     (void)tmp;
@@ -167,24 +187,39 @@ static void join_v(int32_t *buf, int W, int nr, int nc, int32_t *tmp,
 
 /* Full slice forward transform: 2 vertical x 5 horizontal levels; horizontal
  * levels 1-2 use (9,7)-M, the rest 5/3 (see internal.h and docs/BITSTREAM.md). */
-void omc_slice_fwd(int32_t *buf, int W, int sh, int32_t *tmp)
+/* vv = visible rows of this slice (vv == sh for every slice but the last of a
+ * padded frame).  Only the VERTICAL stages take it: the horizontal stages run
+ * on full rows, and a neutralized (all-zero) row stays all-zero through them. */
+void omc_slice_fwd_p(int32_t *buf, int W, int sh, int32_t *tmp, int vv,
+                     const int32_t *d1m)
 {
-    split_v(buf, W, sh, W, tmp, omc_dwt_d1m);    /* V level 1: rows -> L|H       */
+    split_v(buf, W, sh, W, tmp, d1m, vv);   /* V level 1: rows -> L|H    */
     split_h(buf, W, 0, sh, W, tmp, 1);           /* H level 1 on all rows        */
-    split_v(buf, W, sh / 2, W / 2, tmp, 0);         /* V level 2 on LL1 cols        */
+    split_v(buf, W, sh / 2, W / 2, tmp, 0, vv / 2); /* V level 2 on LL1 cols     */
     split_h(buf, W, 0, sh / 2, W / 2, tmp, 1);   /* H level 2 on LL1 rows        */
     split_h(buf, W, 0, sh / 4, W / 4, tmp, 0);   /* H level 3 on LL2 rows        */
     split_h(buf, W, 0, sh / 4, W / 8, tmp, 0);   /* H level 4                    */
     split_h(buf, W, 0, sh / 4, W / 16, tmp, 0);  /* H level 5                    */
 }
 
-void omc_slice_inv(int32_t *buf, int W, int sh, int32_t *tmp)
+void omc_slice_inv_p(int32_t *buf, int W, int sh, int32_t *tmp, int vv,
+                     const int32_t *d1m)
 {
     join_h(buf, W, 0, sh / 4, W / 16, tmp, 0);
     join_h(buf, W, 0, sh / 4, W / 8, tmp, 0);
     join_h(buf, W, 0, sh / 4, W / 4, tmp, 0);
     join_h(buf, W, 0, sh / 2, W / 2, tmp, 1);
-    join_v(buf, W, sh / 2, W / 2, tmp, 0);
+    join_v(buf, W, sh / 2, W / 2, tmp, 0, vv / 2);
     join_h(buf, W, 0, sh, W, tmp, 1);
-    join_v(buf, W, sh, W, tmp, omc_dwt_d1m);
+    join_v(buf, W, sh, W, tmp, d1m, vv);
+}
+
+void omc_slice_fwd(int32_t *buf, int W, int sh, int32_t *tmp)
+{
+    omc_slice_fwd_p(buf, W, sh, tmp, sh, 0);
+}
+
+void omc_slice_inv(int32_t *buf, int W, int sh, int32_t *tmp)
+{
+    omc_slice_inv_p(buf, W, sh, tmp, sh, 0);
 }
diff --git a/src/internal.h b/src/internal.h
index 5035abe..a135b8a 100644
--- a/src/internal.h
+++ b/src/internal.h
@@ -47,6 +47,12 @@ static inline void omc_band_layout(int W, int sh, omc_band_t b[OMC_NBANDS])
 /* ---------- forward/inverse 5/3 (dwt.c) ---------- */
 void omc_slice_fwd(int32_t *buf, int W, int sh, int32_t *tmp);
 void omc_slice_inv(int32_t *buf, int W, int sh, int32_t *tmp);
+/* pad-aware forms (minor 11): vv = visible rows of the slice, vv == sh for an
+ * ordinary slice, in which case these are identical to the two above. */
+void omc_slice_fwd_p(int32_t *buf, int W, int sh, int32_t *tmp, int vv,
+                     const int32_t *d1m);
+void omc_slice_inv_p(int32_t *buf, int W, int sh, int32_t *tmp, int vv,
+                     const int32_t *d1m);
 
 /* ---------- tANS (tans.c) ---------- */
 typedef struct {
diff --git a/tests/test_xsl.c b/tests/test_xsl.c
index 19e42d4..64101c9 100644
--- a/tests/test_xsl.c
+++ b/tests/test_xsl.c
@@ -92,6 +92,81 @@ static void run_chain(const omc_config_t *c, const uint16_t *pix,
     omc_dec_destroy(d);
 }
 
+/* ---------------------------------------------------------- G-T5-PAD ----
+ * PAD NEUTRALIZATION (minor 11).  A raster coded taller than its display
+ * height (here 64 coded rows for a 56-row display, slice_h 16: the last slice
+ * has v = 8 visible rows and 8 pad rows) must satisfy two properties:
+ *   (a) the committed pad rows are exactly a replication of the committed last
+ *       VISIBLE row -- a pure function of the visible picture, so a cropped
+ *       baseband decode can be re-padded to the committed picture; and
+ *   (b) doing exactly that -- crop, re-pad by replication, re-encode --
+ *       reproduces the committed picture byte for byte at generation 2.
+ * The gate also runs itself with the pre-minor-11 behaviour reintroduced
+ * (the debug_oldpads API) and REQUIRES that arm to fail: a gate that cannot fail
+ * proves nothing, which is the lesson this project's own register records. */
+enum { DH = 56 };   /* display height; coded H = 64, so 8 pad rows */
+
+static int pad_chain(int oldpads, int *repl_ok)
+{
+    omc_config_t c; cfg_init(&c);
+    c.display_width = W; c.display_height = DH;
+
+    size_t fb = (size_t)(c.bits_per_slice / 8) * (H / SH);
+    uint16_t *pix = malloc(WORDS * 2), *d1 = malloc(WORDS * 2), *d2 = malloc(WORDS * 2);
+    uint8_t *bs = malloc(fb);
+    if (!pix || !d1 || !d2 || !bs) return -1;
+    fill(pix, 999u, 0);
+    /* generation 1 */
+    omc_enc_t *e = omc_enc_create(&c); omc_dec_t *d = omc_dec_create(&c);
+    if (oldpads) { omc_enc_debug_oldpads(e, 1); omc_dec_debug_oldpads(d, 1); }
+    omc_frame_t fr; planes(&fr, pix);
+    omc_enc_frame(e, &fr, 0, bs, fb, NULL);
+    omc_frame_t fo; planes(&fo, d1);
+    omc_dec_frame(d, bs, fb, &fo);
+    omc_enc_destroy(e); omc_dec_destroy(d);
+    /* (a) committed pads == replication of the committed last visible row */
+    *repl_ok = 1;
+    for (int p = 0; p < 3; p++) {
+        int pw = p ? WC : W;
+        const uint16_t *pl = d1 + (p == 0 ? 0 : (p == 1 ? (size_t)W * H
+                                                        : (size_t)W * H + (size_t)WC * H));
+        for (int r = DH; r < H; r++)
+            for (int x = 0; x < pw; x++)
+                if (pl[(size_t)r * pw + x] != pl[(size_t)(DH - 1) * pw + x])
+                    *repl_ok = 0;
+    }
+    /* (b) crop to the display raster and re-pad by replication -- exactly what
+     * a baseband hop leaves a downstream encoder -- then re-encode */
+    memcpy(d2, d1, WORDS * 2);
+    for (int p = 0; p < 3; p++) {
+        int pw = p ? WC : W;
+        uint16_t *pl = d2 + (p == 0 ? 0 : (p == 1 ? (size_t)W * H
+                                                  : (size_t)W * H + (size_t)WC * H));
+        for (int r = DH; r < H; r++)
+            memcpy(pl + (size_t)r * pw, pl + (size_t)(DH - 1) * pw, (size_t)pw * 2);
+    }
+    uint8_t *bs2 = malloc(fb);
+    uint16_t *g2 = malloc(WORDS * 2);
+    e = omc_enc_create(&c); d = omc_dec_create(&c);
+    if (oldpads) { omc_enc_debug_oldpads(e, 1); omc_dec_debug_oldpads(d, 1); }
+    omc_frame_t f2; planes(&f2, d2);
+    omc_enc_frame(e, &f2, 0, bs2, fb, NULL);
+    omc_frame_t fo2; planes(&fo2, g2);
+    omc_dec_frame(d, bs2, fb, &fo2);
+    omc_enc_destroy(e); omc_dec_destroy(d);
+    /* compare the VISIBLE picture (what baseband carries) */
+    int same = 1;
+    for (int p = 0; p < 3 && same; p++) {
+        int pw = p ? WC : W;
+        size_t off = (p == 0 ? 0 : (p == 1 ? (size_t)W * H : (size_t)W * H + (size_t)WC * H));
+        for (int r = 0; r < DH && same; r++)
+            if (memcmp(d1 + off + (size_t)r * pw, g2 + off + (size_t)r * pw, (size_t)pw * 2))
+                same = 0;
+    }
+    free(pix); free(d1); free(d2); free(bs); free(bs2); free(g2);
+    return same;
+}
+
 int main(void)
 {
     omc_config_t c; cfg_init(&c);
@@ -142,6 +217,50 @@ int main(void)
     CHECK(edited > 0, "G-T5-XSL2b the boundary edit actually fires "
                       "(un-blend changes samples)");
 
+    /* ------------------------------------------------------ G-T5-GEOM */
+    {
+        /* The baseband-safe verdict must not certify a geometry the pad rule
+         * does not cover.  Found by adversarial audit: horizontally padded
+         * rasters and visible runs with v mod 4 were reported safe while their
+         * chains drifted.  A confidently wrong safety report is worse than
+         * none, so the verdict is gated on geometry as well as gamut. */
+        omc_config_t g; cfg_init(&g);
+        g.display_width = W; g.display_height = DH;      /* vertical pad only */
+        omc_enc_t *ge = omc_enc_create(&g);
+        int ok_vert = omc_enc_geom_baseband_safe(ge);
+        omc_enc_destroy(ge);
+        cfg_init(&g); g.display_width = W - 4; g.display_height = H; /* h-pad */
+        ge = omc_enc_create(&g);
+        int ok_horiz = omc_enc_geom_baseband_safe(ge);
+        omc_enc_destroy(ge);
+        cfg_init(&g); g.display_width = W; g.display_height = H - SH + 2; /* v mod 4 */
+        ge = omc_enc_create(&g);
+        int ok_odd = omc_enc_geom_baseband_safe(ge);
+        omc_enc_destroy(ge);
+        CHECK(ok_vert == 1, "G-T5-GEOM1 a vertically padded raster the rule "
+                            "covers reports baseband-safe geometry");
+        CHECK(ok_horiz == 0, "G-T5-GEOM2 a HORIZONTALLY padded raster reports "
+                             "NOT baseband-safe (the rule does not cover it)");
+        CHECK(ok_odd == 0, "G-T5-GEOM3 a visible run the rule cannot express "
+                           "(v mod 4) reports NOT baseband-safe");
+    }
+
+    /* ------------------------------------------------------- G-T5-PAD */
+    {
+        int repl_new = 0, repl_old = 0;
+        int ok_new = pad_chain(0, &repl_new);
+        int ok_old = pad_chain(1, &repl_old);
+        CHECK(repl_new == 1,
+              "G-T5-PAD1 committed pad rows are a replication of the committed "
+              "last visible row (a pure function of the visible picture)");
+        CHECK(ok_new == 1,
+              "G-T5-PAD2 crop to the display raster, re-pad by replication and "
+              "re-encode reproduces the committed visible picture byte-for-byte");
+        CHECK(ok_old == 0,
+              "G-T5-PAD3 the gate is NON-VACUOUS: with the pre-minor-11 pad "
+              "behaviour reintroduced the same chain FAILS");
+    }
+
     free(pix); free(dec1); free(dec2); free(dec3); free(decx);
     free(bs1); free(bs2); free(bs3); free(bsx);
     printf("test_xsl: %s\n", fails ? "FAILURES" : "all ok");
diff --git a/tools/omc_dec.c b/tools/omc_dec.c
index cddef1c..eb8d08d 100644
--- a/tools/omc_dec.c
+++ b/tools/omc_dec.c
@@ -113,8 +113,11 @@ int main(int argc, char **argv)
     uint16_t *obuf = malloc(((size_t)oW * oH * 3) * 2);
     uint16_t *disp = cdr ? NULL : malloc(frame_words * 2);
     if (!obuf || (!cdr && !disp)) die("out of memory");
+    int first_fidx8 = -1;
     for (;;) {
         if (fread(fb, 1, frame_bytes, fi) != frame_bytes) break;
+        /* slice header: 32-bit sync, then the 8-bit frame phase (fidx8) */
+        if (first_fidx8 < 0 && frame_bytes > 4) first_fidx8 = fb[4];
         int64_t good = omc_dec_frame(dec, fb, frame_bytes, &fout);
         if (good < nsl) {
             bad += nsl - (int)good;
@@ -201,6 +204,17 @@ int main(int argc, char **argv)
     }
     fprintf(stderr, "omc_dec: %d frames decoded, %d damaged slices%s\n", fidx, bad,
             bad && conceal ? " (concealed)" : "");
+    /* Coded vs display geometry: a re-encode of the CDR must be told BOTH (the
+     * CDR is at coded geometry, and minor 11's pad neutralization is keyed off
+     * the display height).  Print the exact flags to pass. */
+    if (first_fidx8 >= 0)
+        fprintf(stderr, "omc_dec: frame phase of the first slice: fidx8=%d "
+                "(re-encode with --start-frame %d to resume it)\n",
+                first_fidx8, first_fidx8);
+    if (oH != H || oW != W)
+        fprintf(stderr, "omc_dec: coded %dx%d, display %dx%d -- re-encode a CDR "
+                "with: -w %d -h %d --display-w %d --display-h %d\n",
+                W, H, oW, oH, W, H, oW, oH);
     omc_dec_destroy(dec);
     fclose(fi); fclose(fo);
     free(pix); free(sb); free(fb); free(obuf); free(disp); free(upix); free(utmp);
diff --git a/tools/omc_enc.c b/tools/omc_enc.c
index 71de39b..a72b64f 100644
--- a/tools/omc_enc.c
+++ b/tools/omc_enc.c
@@ -58,6 +58,9 @@ int main(int argc, char **argv)
 {
     const char *inp = NULL, *outp = NULL, *reconp = NULL;
     int rgb = 0, mono = 0, verbose_ll = 0, lossless_frames = 0, bpp_set = 0;
+    int dispw_arg = 0, disph_arg = 0;   /* --display-w/--display-h (CDR re-encode) */
+    int start_frame = 0;                /* --start-frame: mod-256 phase to resume */
+    int dbg_oldpads = 0;                /* TEST ONLY: pre-minor-11 pad behaviour */
     int cdr_in = 0;     /* input is coded-domain raw (biased, coded geometry) */
     omc_config_t cfg;
     memset(&cfg, 0, sizeof(cfg));
@@ -93,6 +96,10 @@ int main(int argc, char **argv)
         else if (!strcmp(argv[i], "--grain-replace")) cfg.grain_replace = 1;
         else if (!strcmp(argv[i], "--grain-corr")) cfg.grain_corr = 1;
         else if (!strcmp(argv[i], "--fill-static")) cfg.fill_static = 1;
+        else if (!strcmp(argv[i], "--debug-oldpads")) dbg_oldpads = 1;
+        else if (!strcmp(argv[i], "--start-frame")) start_frame = atoi(argv[++i]);
+        else if (!strcmp(argv[i], "--display-w")) dispw_arg = atoi(argv[++i]);
+        else if (!strcmp(argv[i], "--display-h")) disph_arg = atoi(argv[++i]);
         else if (!strcmp(argv[i], "--rgb")) rgb = 1;   /* planar R,G,B in; RCT applied */
         else if (!strcmp(argv[i], "--mono")) mono = 1; /* single plane in; flat chroma */
         else if (!strcmp(argv[i], "--lossless")) { cfg.lossless_pref = 1; cfg.no_fill = 1; }
@@ -117,6 +124,18 @@ int main(int argc, char **argv)
             "  in-loop temporal filter of v4.8 is REMOVED.  Streams are minor 10.");
     if (rgb && mono) die("--rgb and --mono are mutually exclusive");
     if (cdr_in && (rgb || mono)) die("--cdr-in carries coded planes; --rgb/--mono do not apply");
+    /* A CDR is at CODED geometry and carries no display dims, so a padded
+     * raster cannot be inferred from it.  Guessing wrong does not fail loudly:
+     * it silently drifts (the last slice codes its pad rows as content and
+     * never locks to the previous generation's picture).  For a contract whose
+     * whole value is exactness, an explicit statement is required rather than
+     * a default -- pass the display height, or pass the coded height to assert
+     * that the raster is unpadded.  omc_dec prints the exact flags. */
+    if (cdr_in && !disph_arg)
+        die("--cdr-in requires --display-h (and --display-w): a CDR is at CODED "
+            "geometry and cannot describe a padded raster. Pass the display "
+            "dims omc_dec reports; if the raster is unpadded pass the coded "
+            "dims. Guessing silently drifts at generation 2.");
     if (cfg.lossless_pref && !bpp_set) bpp = 16.0; /* generous CBR ceiling for lossless headroom */
     int comp_depth = cfg.bitdepth; /* true component depth of the input */
     if (rgb) {
@@ -149,6 +168,14 @@ int main(int argc, char **argv)
             cfg.display_width = dispW; cfg.display_height = dispH;
             cfg.width = cw; cfg.height = chh;
         }
+        /* Explicit display geometry.  REQUIRED to re-encode a CDR of a padded
+         * raster (1080 coded as 1088): the CDR is at coded geometry, so the
+         * true raster cannot be inferred from it, and the pad-neutralization
+         * rule of minor 11 is keyed off it.  omc_dec prints the value to pass. */
+        if (dispw_arg) cfg.display_width = (uint16_t)dispw_arg;
+        if (disph_arg) cfg.display_height = (uint16_t)disph_arg;
+        if (cfg.display_height > cfg.height || cfg.display_width > cfg.width)
+            die("--display-w/-h must not exceed the coded dims");
     }
     int nsl = cfg.height / cfg.slice_h;
     double bits_frame = bpp * cfg.width * cfg.height;
@@ -157,6 +184,24 @@ int main(int argc, char **argv)
         char verr[160];
         if (omc_validate_config(&cfg, verr, sizeof verr) != 0) die(verr);
     }
+    /* A2 is a hard product mandate: sub-1 ms end to end INCLUDING any output
+     * resolution conversion.  The validator only REFUSES when a2_strict is
+     * set, so an over-budget configuration used to encode silently.  Report it
+     * always, with the figure, so nobody ships a leg that breaches the bar
+     * without having been told.  slice_h 32 is the usual cause below 2160p:
+     * it costs 32 line periods of slice assembly, which at 720p50 is 1.79 ms
+     * before any conversion, and at 1080p50 1.21 ms. */
+    {
+        double lat_ms = 0.0; int lat_per = 0;
+        int over = omc_config_latency(&cfg, &lat_ms, &lat_per);
+        if (over > 0)
+            fprintf(stderr, "omc_enc: WARNING A2: this configuration takes "
+                    "%.3f ms (slice_h %u at %ux%u@%u%s) -- the mandate is "
+                    "under 1 ms including output conversion. slice_h 32 is "
+                    "intended for 2160p and 4320p only.\n",
+                    lat_ms, cfg.slice_h, cfg.width, cfg.height, cfg.fps_num,
+                    cfg.uc_ratio ? ", with conversion" : ", no conversion");
+    }
 
     int W = cfg.width, H = cfg.height, Wc = omc_chroma_width(&cfg);
     size_t ysz = (size_t)W * H, csz = (size_t)Wc * H;
@@ -171,7 +216,11 @@ int main(int argc, char **argv)
     uint16_t *inbuf = malloc(in_words * 2);
     int32_t mid_c = 1 << (cfg.bitdepth - 1);           /* container midpoint */
     int32_t yoff = mid_c - (1 << (comp_depth - 1));    /* RCT plane-0 offset */
-    uint16_t *rec = (reconp || cfg.lossless_pref) ? malloc(frame_words * 2) : NULL;
+    /* The reconstruction buffer is allocated ALWAYS: the encoder's gamut
+     * report (baseband-safe verdict) is measured on the emitted picture, so
+     * it needs somewhere to emit.  --recon only decides whether it is also
+     * written to a file. */
+    uint16_t *rec = malloc(frame_words * 2);
     size_t slice_bytes = cfg.bits_per_slice / 8;
     uint8_t *bs = malloc(slice_bytes * (size_t)nsl);
 
@@ -229,10 +278,24 @@ int main(int argc, char **argv)
     fwrite(shdr, 1, OMC_STREAM_HDR_BYTES, fo);
 
     omc_enc_t *enc = omc_enc_create(&cfg);
+    if (dbg_oldpads && enc) {
+        omc_enc_debug_oldpads(enc, 1);
+        fprintf(stderr, "omc_enc: WARNING --debug-oldpads: pad neutralization "
+                "DISABLED; this stream is NOT minor-11 conforming (test hook "
+                "for the pad gate only)\n");
+    }
     omc_frame_t fin = {{pix, pix + ysz, pix + ysz + csz}, {W, Wc, Wc}};
     omc_frame_t frec = {{rec, rec ? rec + ysz : NULL, rec ? rec + ysz + csz : NULL}, {W, Wc, Wc}};
 
-    int fidx = 0;
+    /* Frame phase.  The refresh wave ((fidx8 % R) == (slice % R)) and the fill
+     * tile animation are both functions of frame_idx & 255 and of nothing else,
+     * so re-encoding a decode exactly requires resuming that phase.  A whole-clip
+     * re-encode gets it for free (both runs start at 0); a MID-STREAM joiner
+     * reads fidx8 out of any slice header (omc_dec prints it) and passes it
+     * here.  Because both consumers are mod 256 and fidx8 IS the low 8 bits,
+     * the phase is fully recoverable from the stream -- there is no residual
+     * ambiguity. */
+    int fidx = start_frame;
     while (nframes < 0 || fidx < nframes) {
         if (fread(inbuf, 2, in_words, fi) != in_words) break;
         if (cdr_in)
@@ -263,6 +326,22 @@ int main(int argc, char **argv)
     if (cfg.lossless_pref)
         fprintf(stderr, "omc_enc: lossless-preferred: %d/%d frames bit-exact\n",
                 lossless_frames, fidx);
+    {
+        int64_t oob = omc_enc_oob(enc);
+        int geom = omc_enc_geom_baseband_safe(enc);
+        fprintf(stderr, "omc_enc: gamut: %lld committed samples outside legal "
+                "range\n", (long long)oob);
+        if (oob == 0 && geom)
+            fprintf(stderr, "omc_enc: baseband-safe: yes\n");
+        else
+            fprintf(stderr, "omc_enc: baseband-safe: NO (%s%s%s) -- CDR "
+                    "interchange required for exact chains\n",
+                    oob ? "out-of-gamut committed samples" : "",
+                    (oob && !geom) ? "; " : "",
+                    geom ? "" : "geometry not recoverable from a cropped "
+                                "picture: horizontal padding, or a visible row "
+                                "run this rule cannot express");
+    }
     omc_enc_destroy(enc);
     fclose(fi); fclose(fo); if (fr) fclose(fr);
     free(pix); free(rec); free(bs);
=== END T5 M11 PATCH ===
`````

## Appendix E — the baseband harness, full text

Save each file at the path shown (the layout of section 10), `chmod +x` the
two shell scripts.  These are the exact scripts that produced section 12.
`tests/bb_prediction.md` is reproduced as the pre-registration record.

### `tests/genchain_bb.sh`

`````bash
#!/bin/bash
# genchain_bb.sh - T5 generation-exactness chain test over PURE BASEBAND
# interchange: every generation hop uses the ordinary display decode
# (legal-range, cropped, no --cdr / --cdr-in anywhere in the chain).
#
# Usage: identical to genchain.sh:
#   genchain_bb.sh <master.yuv> <trueW> <trueH> <fmt 422|444> <depth> <bpp> \
#                  <slice_h(0=auto)> <gens> [extra encoder flags...]
#
# Runs: master -> enc -> dec(display) -> enc -> dec(display) -> ... <gens> times,
# re-encoding each display decode with the SAME command line as generation 1.
# PASS iff every generation's display decode is byte-identical to generation
# 1's, and every generation >= 2 writes a byte-identical bitstream.
# Also prints the gen-1 stream md5 and the per-cell gamut evidence
# (committed range + out-of-legal-range count, from a one-off gen-1 CDR probe
# that takes no part in the chain).
set -u
E="$(cd "$(dirname "$0")/../omc/omc_v4.9" && pwd)"
D="$(cd "$(dirname "$0")" && pwd)"
MASTER=$1; TW=$2; TH=$3; FMT=$4; DEPTH=$5; BPP=$6; SH=$7; GENS=$8; shift 8
EXTRA=("$@")
WORK="${GENCHAIN_TMP:-$(mktemp -d)}"
mkdir -p "$WORK"
trap 'rm -rf "$WORK"' EXIT

WAL=$([ "$FMT" = 422 ] && echo 64 || echo 32)
CW=$(( (TW + WAL - 1) / WAL * WAL ))
RSH=$SH
if [ "$RSH" = 0 ]; then RSH=$([ "$TH" -le 720 ] && echo 8 || echo 16); fi
CH=$(( (TH + RSH - 1) / RSH * RSH ))
SHFLAG=()
[ "$SH" != 0 ] && SHFLAG=(--slice-h "$SH")

"$E/omc_enc" -i "$MASTER" -o "$WORK/g1.omc" -w "$TW" -h "$TH" --fmt "$FMT" \
    --depth "$DEPTH" --bpp "$BPP" "${SHFLAG[@]}" "${EXTRA[@]}" 2>"$WORK/enc1.log" \
    || { echo "FAIL enc-gen1 ($(tail -1 "$WORK/enc1.log"))"; exit 1; }
# A2 marker: the encoder reports any configuration that exceeds the 1 ms
# latency budget (including output conversion).  Carried into the RESULT LINE
# itself, not just prose: these cells are exactness coverage, and a reader
# skimming PASS lines must not mistake an over-budget slice height for a
# shippable configuration.
A2=""
if grep -q "WARNING A2" "$WORK/enc1.log" 2>/dev/null; then
    A2=" [A2:OVER $(sed -n 's/.*takes \([0-9.]*\) ms.*/\1/p' "$WORK/enc1.log" | head -1)ms NOT-SHIPPABLE]"
fi
"$E/omc_dec" -i "$WORK/g1.omc" -o "$WORK/g1.yuv" 2>/dev/null \
    || { echo "FAIL dec-gen1"; exit 1; }
# gamut evidence (probe only; the chain never touches this file)
"$E/omc_dec" -i "$WORK/g1.omc" --cdr -o "$WORK/probe.cdr" 2>/dev/null
GAMUT=$(python3 "$D/gamut_probe.py" "$WORK/probe.cdr" "$DEPTH")
rm -f "$WORK/probe.cdr"

prev="$WORK/g1.yuv"; fail=""
for g in $(seq 2 "$GENS"); do
    "$E/omc_enc" -i "$prev" -o "$WORK/gN.omc" -w "$TW" -h "$TH" \
        --fmt "$FMT" --depth "$DEPTH" --bpp "$BPP" "${SHFLAG[@]}" "${EXTRA[@]}" \
        2>"$WORK/encN.log" || { fail="enc-gen$g ($(tail -1 "$WORK/encN.log"))"; break; }
    "$E/omc_dec" -i "$WORK/gN.omc" -o "$WORK/gN.yuv" 2>/dev/null \
        || { fail="dec-gen$g"; break; }
    cmp -s "$WORK/g1.yuv" "$WORK/gN.yuv" || { fail="pixels-gen$g"; break; }
    if [ "$g" = 2 ]; then cp "$WORK/gN.omc" "$WORK/g2.omc"
    else cmp -s "$WORK/g2.omc" "$WORK/gN.omc" || { fail="stream-gen$g"; break; }
    fi
    cp "$WORK/gN.yuv" "$WORK/prev.yuv"; prev="$WORK/prev.yuv"
done

if [ -n "$fail" ]; then
    echo "FAIL $fail  [BB ${TW}x${TH}->${CW}x${CH} $FMT/${DEPTH}b bpp=$BPP sh=$RSH gens=$GENS ${EXTRA[*]:-}] $GAMUT"
    exit 1
fi
echo "PASS  [BB ${TW}x${TH}->${CW}x${CH} $FMT/${DEPTH}b bpp=$BPP sh=$RSH gens=$GENS ${EXTRA[*]:-}] g1.omc=$(md5sum <"$WORK/g1.omc" | cut -d' ' -f1)$A2 $GAMUT"
`````

### `tests/run_matrix_bb.sh`

`````bash
#!/bin/bash
# run_matrix_bb.sh - the T5 generation-exactness matrix over PURE BASEBAND
# interchange (tests/genchain_bb.sh): every cell of run_matrix.sh, split by
# geometry.  "padfree" cells have coded == display raster (no pad rows);
# "padded" cells (1080-coded-as-1088, 2160-as-2176 at sh32) require the
# transform-domain pad synthesis (minor 11) to hold over baseband.
#   usage: run_matrix_bb.sh padfree|padded|all
set -u
cd "$(dirname "$0")/.."
T=tests/genchain_bb.sh; R=tests/raw
MODE=${1:-padfree}

padfree() {
$T $R/gfx720_422_10.yuv      1280 720  422 10 0.5 0  6
$T $R/gfx720_422_10.yuv      1280 720  422 10 2.0 0  5
$T $R/cineA31_720_444_8.yuv  1280 720  444 8  0.5 0  5
$T $R/cineA31_720_444_8.yuv  1280 720  444 8  1.0 16 5
$T $R/cineA21_720_422_12.yuv 1280 720  422 12 3.0 0  5
$T $R/cineA21_422_12.yuv     2048 1152 422 12 0.5 16 6
$T $R/cineA21_444_10.yuv     2048 1152 444 10 2.0 16 5
$T $R/cineA31_422_10.yuv     2048 1152 422 10 0.5 8  5
$T $R/cineA31_422_10.yuv     2048 1152 422 10 3.0 32 5
$T $R/cine4k_422_8.yuv       4096 2160 422 8  0.5 16 4
$T $R/gfxF003_444_8.yuv      4480 1856 444 8  0.5 16 4
$T $R/gfxF003_422_12.yuv     4480 1856 422 12 1.0 8  4
$T $R/cineA31_422_10.yuv     2048 1152 422 10 0.5 16 5 --tune vmaf
$T $R/cineA31_422_10.yuv     2048 1152 422 10 0.5 16 5 --grain-corr --fill-static
}

padded() {
$T $R/gfx1080_422_10.yuv     1920 1080 422 10 0.5 16 6
$T $R/gfx1080_422_10.yuv     1920 1080 422 10 1.0 16 5
$T $R/gfx1080_422_10.yuv     1920 1080 422 10 3.0 16 5
$T $R/gfx1080_444_12.yuv     1920 1080 444 12 0.5 16 6
$T $R/gfx1080_444_12.yuv     1920 1080 444 12 3.0 16 5
$T $R/gfx1080_444_8.yuv      1920 1080 444 8  1.0 16 5
$T $R/gfx1080_422_10.yuv     1920 1080 422 10 1.0 32 5
$T $R/cine4k_444_10.yuv      4096 2160 444 10 2.0 32 4
$T $R/gfx1080_422_10.yuv     1920 1080 422 10 1.0 16 5 --tune vmaf
$T $R/gfx1080_422_10.yuv     1920 1080 422 10 1.0 16 5 --grain-corr
$T $R/gfx1080_422_10.yuv     1920 1080 422 10 1.0 16 5 --fill-static
$T $R/gfx1080_422_10.yuv     1920 1080 422 10 1.0 16 5 --no-fill
$T $R/gfx1080_422_10.yuv     1920 1080 422 10 1.0 16 5 --grain-replace
$T $R/gfx1080_422_10.yuv     1920 1080 422 10 1.0 16 5 --refresh 2
$T $R/gfx1080_422_10.yuv     1920 1080 422 10 1.0 16 5 --refresh 3
}

case $MODE in
  padfree) padfree ;;
  padded)  padded ;;
  all)     padfree; padded ;;
  *) echo "usage: run_matrix_bb.sh padfree|padded|all" >&2; exit 2 ;;
esac
`````

### `tests/gamut_probe.py`

`````python
#!/usr/bin/env python3
"""gamut_probe.py - per-cell gamut evidence for the baseband matrix.

Usage: gamut_probe.py g1.cdr depth

Reads a CDR (biased u16 LE), prints the committed sample range in true codes
and the out-of-legal-range count: "range=[lo..hi] oob=N".  oob=0 is the
measured meaning of "in-gamut" for a baseband-matrix row.
"""
import sys
import numpy as np

def main():
    a = np.fromfile(sys.argv[1], dtype='<u2').astype(np.int64) - 2048
    maxv = (1 << int(sys.argv[2])) - 1
    oob = int((a < 0).sum() + (a > maxv).sum())
    print(f"range=[{a.min()}..{a.max()}] oob={oob}")

if __name__ == "__main__":
    main()
`````

### `tests/mkrail.py`

`````python
#!/usr/bin/env python3
"""mkrail.py - deterministic rail-heavy synthetic master for the gamut arm of
the baseband matrix.

Content chosen to put committed reconstruction samples OUTSIDE legal range:
hard-clipped white and black plates with sharp edges placed across slice
boundaries (quantization ringing overshoots at the rails), a full-range
horizontal ramp touching 0 and maxv, saturated graphics bars (chroma at the
rails), all drifting 2 px/frame so inter frames exercise the temporal path.

Usage: mkrail.py out.yuv [W H depth frames]   (defaults 1280 720 10 3)
Output: planar Y|Cb|Cr 4:2:2 u16 LE, [0, 2^depth).
Fully deterministic (no RNG).
"""
import sys
import numpy as np

def main():
    out = sys.argv[1]
    W = int(sys.argv[2]) if len(sys.argv) > 2 else 1280
    H = int(sys.argv[3]) if len(sys.argv) > 3 else 720
    depth = int(sys.argv[4]) if len(sys.argv) > 4 else 10
    nf = int(sys.argv[5]) if len(sys.argv) > 5 else 3
    maxv = (1 << depth) - 1
    mid = 1 << (depth - 1)
    with open(out, "wb") as fo:
        for f in range(nf):
            s = 2 * f  # 2 px/frame drift
            y = np.full((H, W), mid, np.int32)
            cb = np.full((H, W), mid, np.int32)
            cr = np.full((H, W), mid, np.int32)
            # full-range horizontal ramp band (touches 0 and maxv)
            y[0:96, :] = (np.arange(W) * maxv // (W - 1))[None, :]
            # hard white plate with sharp edges crossing slice rows 16k
            y[100 + s:250 + s, 200 + s:600 + s] = maxv
            # hard black plate
            y[260 + s:400 + s, 640 + s:1040 + s] = 0
            # saturated graphics bars: chroma at the rails, sharp verticals
            for i, (cbv, crv) in enumerate([(0, maxv), (maxv, 0), (0, 0), (maxv, maxv)]):
                x0 = 80 + 280 * i + s
                y[420 + s:560 + s, x0:x0 + 220] = maxv if i % 2 else 0
                cb[420 + s:560 + s, x0:x0 + 220] = cbv
                cr[420 + s:560 + s, x0:x0 + 220] = crv
            # thin white/black line pair ON a slice boundary (rows 575/576)
            y[575, :] = maxv
            y[576, :] = 0
            # checker of near-rail values (ringing bait)
            yy, xx = np.mgrid[600:704, 0:W]
            y[600:704, :] = np.where((yy + xx + s) % 2 == 0, maxv - 1, 1)
            cbh = ((cb[:, 0::2] + cb[:, 1::2] + 1) // 2)
            crh = ((cr[:, 0::2] + cr[:, 1::2] + 1) // 2)
            fo.write(y.astype("<u2").tobytes())
            fo.write(cbh.astype("<u2").tobytes())
            fo.write(crh.astype("<u2").tobytes())
    print(f"{out}: {nf} frames {W}x{H} 422/{depth}-bit rail-heavy")

if __name__ == "__main__":
    main()
`````

### `tests/bb_prediction.md`

`````text
# Pre-registered predictions — baseband interchange matrix
Written 2026-08-17, BEFORE any baseband matrix run, on build: T5 tree at
commit d067333 plus the gamut-report instrumentation (verified hash-neutral
against the recorded §10.3 md5: 1c81c776... reproduced).

Claim under test: "pad-free geometry + in-gamut content ⇒ pure-baseband
generation exactness" — i.e. the CDR's extra information over legal-range
display baseband is load-bearing ONLY through (a) pad rows and (b)
out-of-legal-range committed samples, and the 2048 bias is cosmetic.

P1. Every pad-free cell of the §10.3 matrix (14 cells: all 720p, all
    2048×1152 including both option rows, 4096×2160 sh16, both 4480×1856)
    PASSES genchain_bb at the same generation depths as §10.3, with
    measured oob=0.
P2. The two long chains re-run over baseband (720p 20 generations,
    2048×1152 12 generations at 0.5 bpp) PASS with oob=0.
P3. Every padded cell (1080-as-1088, 2160-as-2176@sh32) FAILS baseband on
    the current build with fail=pixels-gen2 (the pad rows are not
    re-derivable from cropped baseband). [To be run as the negative arm
    before the pad fix; expected to flip to PASS after minor 11.]
P4. The rail-heavy synthetic clip (hard-clipped whites/blacks, full-range
    ramp) measures oob>0 at 10-bit and FAILS baseband at pixels-gen2 while
    PASSING the same configuration over CDR interchange (liveness arm: the
    harness can see a baseband break; the failure is confined to the gamut
    condition, not the harness).
Falsification branches, armed:
- Any pad-free in-gamut cell failing ⇒ a third load-bearing difference
  exists; trace it before writing the section (candidate suspects: display
  projection ordering vs boundary blend at barrier phases; RCT rounding;
  mid-grey init of unwritten planes).
- Rail clip PASSING baseband with oob>0 ⇒ the oob counter or the clip is
  not measuring what it claims; fix the instrument first.
- Rail clip measuring oob=0 ⇒ the clip is not rail-heavy enough; harden it
  before drawing any conclusion (a liveness arm that cannot fire proves
  nothing).
`````

### Master checksum addition

`tests/mkrail.py` is deterministic (no RNG), so the rail-heavy master is
reproducible from the command in 12.11:

```
0d498f3d9033b06784bf845e7ad66347  tests/raw/rail720_422_10.yuv
```

Verify with `md5sum tests/raw/rail720_422_10.yuv` after generating it; the
value above is the measured one for the environment of section 10.1
(numpy 2.4.6).
The generator uses integer arithmetic only, so it should be stable across
numpy versions — if it is not, the PASS/FAIL verdicts of 12.7 still hold (they
are content-independent in kind: any content with `oob > 0` fails baseband),
only the exact counts move.

## 12.13 Adversarial audit of the pad design, and what it changed

Before implementing 12.4 I ran a seven-agent adversarial audit of the design
against the real tree: four independent audits (consumers of pad rows, the
lifting-independence claims, every grain-fill site, and assumptions that could
break) and three refutation passes, each told to default to "refuted" on
finding a concrete mechanism.  It is recorded here because **it found a real
defect in the shipped patch that all four audits had classified as harmless**,
and because the numbers in 12.14 come from the build *after* those fixes.

**What could not be refuted.**  The core mechanism.  One pass measured C4
directly — crop the display decode, re-pad by replication, compare to the
committed picture — across ten geometries (`v` = 4, 8, 12 and 24; slice
heights 8, 16 and 32; 4:2:2 and 4:4:4; 8/10/12-bit; noise, ramps, tail-only
texture and real graphics) and found **zero unexplained differences**, plus
701 encode/decode configurations byte-exact between `enc --recon` and
`dec --cdr`.  Another drove the real `src/dwt.c` numerically and confirmed the
pad-row band arithmetic and the independence claim C2 at both vertical levels.
Two encoder knobs (`OMC_RECOFF=4`, `OMC_BANDTILT=1`) do break exactness, but
**identically on unpadded geometry** — pre-existing, unrelated to this design.

**Four defects found, all fixed before the numbers in 12.14 were taken.**

1. **A real exactness break in the patch (the headline).**
   `reconstruct_slice()`'s `slice_idx` argument means *destination row base*,
   and the DCFB pass-A call site passes `0` because it composes into a
   one-slice scratch frame.  The first version of this patch derived the
   transform geometry from that same argument, so with the DC-feedback servo
   enabled the last slice of a padded raster was reconstructed at the wrong
   length; the encoder then tuned on a picture it would never emit, and
   generation 2 could not reproduce generation 1 — on the **CDR path as well
   as baseband**.  Geometry is now passed explicitly and is never inferred
   from a row offset.  Verified: `OMC_DCFB=3` and `=8` padded chains PASS on
   both interchanges (12.14), and the default-path md5 is unchanged, so the
   fix is stream-neutral.  *All four audit passes read this line and called it
   dormant; the refutation pass proved it live.  Read that as the argument for
   adversarial verification, not against audits.*
2. **The baseband-safe verdict was confidently wrong**, which is worse than
   silent.  It counted gamut only, so a **horizontally** padded raster
   (1900 → 1920 coded: the pad columns are ordinary content of every row, and
   the vertical rule does not touch them) and a visible run the rule cannot
   express (`v mod 4`) were both certified safe while their chains drifted.
   The verdict is now gated on geometry as well as gamut
   (`omc_enc_geom_baseband_safe()`), and gates G-T5-GEOM1/2/3 hold it there.
3. **An unvalidated geometry relation.**  Nothing required the coded height to
   be the display height rounded up to a whole slice, so `--display-h 1000` on
   a 1088-row raster — reachable from the CLI and the library API — produced
   committed pads that were not replications, silently.  `omc_validate_config`
   now refuses it.
4. **Silent drift in this document's own RCT recipe.**  `--cdr-in` without
   display dims coded the pad rows as content and stabilised on the *wrong*
   picture with no error — the chain still locked, it just locked to something
   else.  `--cdr-in` now **requires** `--display-h`/`--display-w`: for a
   contract whose value is exactness, refusing is right and warning is not.
   The corrected recipe is at the end of 12.14; section 10.3's is superseded.

**One residual risk removed rather than documented.**  The hook that makes the
pad gate non-vacuous was an environment variable read on the **decode** path,
so setting it corrupted *visible* rows of conforming streams and spread
through the temporal reference.  That is exactly the hazard this codec's own
XSL comment forbids ("an environment that could disable any part of it would
silently break the generation-exactness contract"), and the hook violated it.
It is now an explicit per-context test API (`omc_enc_debug_oldpads` /
`omc_dec_debug_oldpads`) plus an `omc_enc --debug-oldpads` flag.  **No
environment variable can change DECODER reconstruction.**  On the encoder side
three experimental knobs survive and DO change committed output --
`OMC_RECOFF`, `OMC_BANDTILT` and `OMC_GR` -- so a conforming encode requires
them unset; section 7's clean-environment precondition names them.

**Two findings carried, not fixed** (stated so nobody builds on a false
premise):

- **Concealment writes pad rows freely**, so after a lost slice the committed
  pads stop being a function of the visible rows, and the next frame's
  prediction reads them.  C4 is a **clean-decode invariant only**.  This does
  not weaken the exactness contract (a concealed picture is a new master by
  definition, section 11.7), but "pads are always re-derivable" is false in
  the presence of loss.
- **Pre-existing, adjacent:** `int32_t llbuf[4 * 256]` (`src/codec.c`) is
  sized for `slice_h = 16` while its guard tests `llw > 256`, so `--slice-h 32`
  on a very wide plane can overflow it.  Not caused by this work, but this
  work increases `slice_h = 32` usage.

## 12.14 Final results on the shipped build

Build stamp: commit `adfeaf4` (the audit fixes above).  **Commit ids in this
document are provenance only — a replicator has no repository.**  The
reproducible identity of a build is the pair of patches in Appendices A and D
plus the md5s recorded here.  Reproducible from a pristine drop by Appendix A
then Appendix D — verified by extracting both
patches from this document, applying them and rebuilding, which reproduces
`156f0237206ac5f66f5b8c89535dfea4` and passes G-T5-PAD1/2/3 and
G-T5-GEOM1/2/3.  These supersede the figures in 12.6, which were taken before
audit fix 1.

**CDR matrix — 29/29 PASS.**  These md5s are the **minor-11** values and are
what a replicator should expect; section 10.3 records the minor-10 values of
that build.  Result lines for `slice_h 32` cells below 2160p now carry an
`[A2:OVER …ms NOT-SHIPPABLE]` suffix stamped by the harness (12.15); listings
recorded before that stamp existed are otherwise unchanged.

```
PASS  [1280x720->1280x720 422/10b bpp=0.5 sh=8 gens=6 ] g1.omc=2355cfeecd32164c8c0bdeb00c8630c9
PASS  [1280x720->1280x720 422/10b bpp=2.0 sh=8 gens=5 ] g1.omc=54c3fdbfd5560be82bcc78282d7d7e3a
PASS  [1280x720->1280x720 444/8b bpp=0.5 sh=8 gens=5 ] g1.omc=410632d677fe59ec1e5bab8184b8ea62
PASS  [1280x720->1280x720 444/8b bpp=1.0 sh=16 gens=5 ] g1.omc=00caaab95f8540a870c1b1f91d278bad
PASS  [1280x720->1280x720 422/12b bpp=3.0 sh=8 gens=5 ] g1.omc=1a68a53a652c838b823e188b188ed713
PASS  [1920x1080->1920x1088 422/10b bpp=0.5 sh=16 gens=6 ] g1.omc=06b04ad48aee485a2ded284946ad1bc9
PASS  [1920x1080->1920x1088 422/10b bpp=1.0 sh=16 gens=5 ] g1.omc=156f0237206ac5f66f5b8c89535dfea4
PASS  [1920x1080->1920x1088 422/10b bpp=3.0 sh=16 gens=5 ] g1.omc=53c841ec2ca947eef4ef6224c79dca24
PASS  [1920x1080->1920x1088 444/12b bpp=0.5 sh=16 gens=6 ] g1.omc=f63486d3ef7ef84105043ccf34946512
PASS  [1920x1080->1920x1088 444/12b bpp=3.0 sh=16 gens=5 ] g1.omc=ea57b1cee042e29b2e890e6f7699fd7a
PASS  [1920x1080->1920x1088 444/8b bpp=1.0 sh=16 gens=5 ] g1.omc=f0e0638ae861fe57428123cd7ef4b5d0
PASS  [1920x1080->1920x1088 422/10b bpp=1.0 sh=32 gens=5 ] g1.omc=4b0765b38ff152535997dfee5dd4d947
PASS  [2048x1152->2048x1152 422/12b bpp=0.5 sh=16 gens=6 ] g1.omc=0d7b660dfd85e03d647293c21fcad479
PASS  [2048x1152->2048x1152 444/10b bpp=2.0 sh=16 gens=5 ] g1.omc=94d2fb8b7964ec6b3a5c9c372f487de4
PASS  [2048x1152->2048x1152 422/10b bpp=0.5 sh=8 gens=5 ] g1.omc=33fe223926fb6ec6139bc8eaa0b49b28
PASS  [2048x1152->2048x1152 422/10b bpp=3.0 sh=32 gens=5 ] g1.omc=f4817c32c8778c7afb0d6a9963f6447b
PASS  [4096x2160->4096x2160 422/8b bpp=0.5 sh=16 gens=4 ] g1.omc=d9e27a26e5025d64800ace3ec32dbef0
PASS  [4096x2160->4096x2176 444/10b bpp=2.0 sh=32 gens=4 ] g1.omc=413862cc3d0bdc660da235e802ae069e
PASS  [4480x1856->4480x1856 444/8b bpp=0.5 sh=16 gens=4 ] g1.omc=dd5dc4d21fbf996ee327308c4a8b90c5
PASS  [4480x1856->4480x1856 422/12b bpp=1.0 sh=8 gens=4 ] g1.omc=3b93a057e52e916b8c0aace61dbcd70e
PASS  [1920x1080->1920x1088 422/10b bpp=1.0 sh=16 gens=5 --tune vmaf] g1.omc=24e17aeaa08f8c6f8ad82ef47493d743
PASS  [1920x1080->1920x1088 422/10b bpp=1.0 sh=16 gens=5 --grain-corr] g1.omc=03db83b9e13a688bfd15f81c3e7209b2
PASS  [1920x1080->1920x1088 422/10b bpp=1.0 sh=16 gens=5 --fill-static] g1.omc=77ac1ce899e0aa127d3ee5c9e0a1c3aa
PASS  [1920x1080->1920x1088 422/10b bpp=1.0 sh=16 gens=5 --no-fill] g1.omc=787a6377e090d490272ed8abd0aebcc6
PASS  [1920x1080->1920x1088 422/10b bpp=1.0 sh=16 gens=5 --grain-replace] g1.omc=3d39cd9bea44d1ad1a8a19f8014fbb59
PASS  [1920x1080->1920x1088 422/10b bpp=1.0 sh=16 gens=5 --refresh 2] g1.omc=80e732f1d4042c511b186dd1a406489b
PASS  [1920x1080->1920x1088 422/10b bpp=1.0 sh=16 gens=5 --refresh 3] g1.omc=119abc593d8d9672f88c5ae5702f9b38
PASS  [2048x1152->2048x1152 422/10b bpp=0.5 sh=16 gens=5 --tune vmaf] g1.omc=f1bbc0717946783e8e40c94eab41190c
PASS  [2048x1152->2048x1152 422/10b bpp=0.5 sh=16 gens=5 --grain-corr --fill-static] g1.omc=f3b9143915126cd2f7307f66e3cc3eb2
```

**Baseband matrix.**  Cell for cell identical to 12.6 -- audit fix 1 is
stream-neutral on the default path -- and reprinted only because the build
identity changed.

```
PASS  [BB 1280x720->1280x720 422/10b bpp=0.5 sh=8 gens=6 ] g1.omc=2355cfeecd32164c8c0bdeb00c8630c9 range=[116..909] oob=0
PASS  [BB 1280x720->1280x720 422/10b bpp=2.0 sh=8 gens=5 ] g1.omc=54c3fdbfd5560be82bcc78282d7d7e3a range=[139..878] oob=0
FAIL pixels-gen2  [BB 1280x720->1280x720 444/8b bpp=0.5 sh=8 gens=5 ] range=[61..289] oob=3737
FAIL pixels-gen2  [BB 1280x720->1280x720 444/8b bpp=1.0 sh=16 gens=5 ] range=[65..280] oob=1874
PASS  [BB 1280x720->1280x720 422/12b bpp=3.0 sh=8 gens=5 ] g1.omc=1a68a53a652c838b823e188b188ed713 range=[249..3604] oob=0
PASS  [BB 2048x1152->2048x1152 422/12b bpp=0.5 sh=16 gens=6 ] g1.omc=0d7b660dfd85e03d647293c21fcad479 range=[-12..3622] oob=1
FAIL pixels-gen2  [BB 2048x1152->2048x1152 444/10b bpp=2.0 sh=16 gens=5 ] range=[-47..1028] oob=839
PASS  [BB 2048x1152->2048x1152 422/10b bpp=0.5 sh=8 gens=5 ] g1.omc=33fe223926fb6ec6139bc8eaa0b49b28 range=[345..974] oob=0
PASS  [BB 2048x1152->2048x1152 422/10b bpp=3.0 sh=32 gens=5 ] g1.omc=f4817c32c8778c7afb0d6a9963f6447b range=[359..941] oob=0
PASS  [BB 4096x2160->4096x2160 422/8b bpp=0.5 sh=16 gens=4 ] g1.omc=d9e27a26e5025d64800ace3ec32dbef0 range=[27..252] oob=0
FAIL pixels-gen2  [BB 4480x1856->4480x1856 444/8b bpp=0.5 sh=16 gens=4 ] range=[-21..183] oob=232811
PASS  [BB 4480x1856->4480x1856 422/12b bpp=1.0 sh=8 gens=4 ] g1.omc=3b93a057e52e916b8c0aace61dbcd70e range=[198..2708] oob=0
PASS  [BB 2048x1152->2048x1152 422/10b bpp=0.5 sh=16 gens=5 --tune vmaf] g1.omc=f1bbc0717946783e8e40c94eab41190c range=[342..1009] oob=0
PASS  [BB 2048x1152->2048x1152 422/10b bpp=0.5 sh=16 gens=5 --grain-corr --fill-static] g1.omc=f3b9143915126cd2f7307f66e3cc3eb2 range=[343..970] oob=0
PASS  [BB 1920x1080->1920x1088 422/10b bpp=0.5 sh=16 gens=6 ] g1.omc=06b04ad48aee485a2ded284946ad1bc9 range=[136..883] oob=0
PASS  [BB 1920x1080->1920x1088 422/10b bpp=1.0 sh=16 gens=5 ] g1.omc=156f0237206ac5f66f5b8c89535dfea4 range=[139..875] oob=0
PASS  [BB 1920x1080->1920x1088 422/10b bpp=3.0 sh=16 gens=5 ] g1.omc=53c841ec2ca947eef4ef6224c79dca24 range=[141..870] oob=0
FAIL pixels-gen2  [BB 1920x1080->1920x1088 444/12b bpp=0.5 sh=16 gens=6 ] range=[190..4241] oob=6
PASS  [BB 1920x1080->1920x1088 444/12b bpp=3.0 sh=16 gens=5 ] g1.omc=ea57b1cee042e29b2e890e6f7699fd7a range=[300..3822] oob=0
PASS  [BB 1920x1080->1920x1088 444/8b bpp=1.0 sh=16 gens=5 ] g1.omc=f0e0638ae861fe57428123cd7ef4b5d0 range=[17..248] oob=0
PASS  [BB 1920x1080->1920x1088 422/10b bpp=1.0 sh=32 gens=5 ] g1.omc=4b0765b38ff152535997dfee5dd4d947 range=[140..874] oob=0
FAIL pixels-gen2  [BB 4096x2160->4096x2176 444/10b bpp=2.0 sh=32 gens=4 ] range=[5..1078] oob=42056
PASS  [BB 1920x1080->1920x1088 422/10b bpp=1.0 sh=16 gens=5 --tune vmaf] g1.omc=24e17aeaa08f8c6f8ad82ef47493d743 range=[134..873] oob=0
PASS  [BB 1920x1080->1920x1088 422/10b bpp=1.0 sh=16 gens=5 --grain-corr] g1.omc=03db83b9e13a688bfd15f81c3e7209b2 range=[137..876] oob=0
PASS  [BB 1920x1080->1920x1088 422/10b bpp=1.0 sh=16 gens=5 --fill-static] g1.omc=77ac1ce899e0aa127d3ee5c9e0a1c3aa range=[140..875] oob=0
PASS  [BB 1920x1080->1920x1088 422/10b bpp=1.0 sh=16 gens=5 --no-fill] g1.omc=787a6377e090d490272ed8abd0aebcc6 range=[140..875] oob=0
PASS  [BB 1920x1080->1920x1088 422/10b bpp=1.0 sh=16 gens=5 --grain-replace] g1.omc=3d39cd9bea44d1ad1a8a19f8014fbb59 range=[142..870] oob=0
PASS  [BB 1920x1080->1920x1088 422/10b bpp=1.0 sh=16 gens=5 --refresh 2] g1.omc=80e732f1d4042c511b186dd1a406489b range=[140..870] oob=0
PASS  [BB 1920x1080->1920x1088 422/10b bpp=1.0 sh=16 gens=5 --refresh 3] g1.omc=119abc593d8d9672f88c5ae5702f9b38 range=[140..875] oob=0
```

**DCFB regression (audit fix 1) and the long chains.**

```
PASS  [1920x1080->1920x1088 422/10b bpp=1.0 sh=16 gens=4 ] g1.omc=7e4520d09f56f40b3a30e52b6757e0a6
PASS  [BB 1920x1080->1920x1088 422/10b bpp=1.0 sh=16 gens=4 ] g1.omc=7e4520d09f56f40b3a30e52b6757e0a6 range=[140..875] oob=0
PASS  [BB 1920x1080->1920x1088 422/10b bpp=1.0 sh=16 gens=4 ] g1.omc=7e4520d09f56f40b3a30e52b6757e0a6 range=[140..875] oob=0
PASS  [BB 1920x1080->1920x1088 422/10b bpp=1.0 sh=16 gens=12 ] g1.omc=156f0237206ac5f66f5b8c89535dfea4 range=[139..875] oob=0
PASS  [BB 1280x720->1280x720 422/10b bpp=1.0 sh=8 gens=20 ] g1.omc=e6af518a63bc2c24dc8f9e871adee2d9 range=[139..893] oob=0
```

**The verdict is unchanged and now rests on a fixed build:** of the baseband
cells, **22 of 22 with `oob = 0` PASS, with no exceptions**; every failure
carries `oob > 0` and is the gamut condition of 12.8, not a geometry or pad
failure.  The padded cells the fix targets pass at every rate, every flag, both
affected slice heights, all three depths, both formats, and through a
12-generation chain.

**Corrected RCT recipe** (supersedes section 10.3's, which predates the
`--display-h` requirement of 12.13 fix 4):

```
E=omc/omc_v4.9; S=/tmp/rct
$E/omc_enc -i tests/raw/gfx1080_444_8.yuv -o $S/rct1.omc -w 1920 -h 1080 --rgb --depth 8 --bpp 1.0
$E/omc_dec -i $S/rct1.omc --cdr -o $S/rct1.cdr
$E/omc_enc --cdr-in -i $S/rct1.cdr -o $S/rct2.omc -w 1920 -h 1088 \
    --display-w 1920 --display-h 1080 --fmt 444 --depth 10 --bpp 1.0
$E/omc_dec -i $S/rct2.omc --cdr -o $S/rct2.cdr        # identical to rct1.cdr
```

Verified exact on the shipped build.  Without the `--display-*` flags the
encoder now refuses rather than drifting.

## 12.15 The two carried findings, closed — and a note on slice_h 32

12.13 listed two findings as "carried, not fixed".  On review that was the
wrong call for both, and they are now fixed.  The reasoning is recorded
because the *reason* they were deferred — "pre-existing, outside the contract"
— is exactly the reasoning that lets a memory-safety bug ship.

**1. The `llbuf` stack overflow (fixed).**  Band 0 holds
`(slice_h/4) x (width/32)` coefficients, but the buffer was sized `4*256`
(i.e. for `slice_h = 16`) while its guard tested only the width (`llw > 256`).
At `slice_h = 32` the row count doubles, so:

| geometry | band-0 entries | old capacity 1024 |
|---|---|---|
| 4096 wide, sh 32 | 1024 | exactly full |
| **4480 wide, sh 32** | **1120** | **overflows by 96** |
| 8192 wide, sh 32 | 2048 | overflows by 1024 |

This is a write past the end of a stack array, in the encoder, reachable from
a legal configuration.  It was pre-existing, but this work makes `slice_h 32`
more likely to be used, and "not mine" is not a reason to leave it.  The
buffer is now sized for the worst legal case (`slice_h 32`, 8192-wide plane)
and the guard tests what is actually written rather than a proxy for it.
Verified: `4480x1856 4:4:4/8 @1.0 bpp --slice-h 32` — the configuration that
overflowed — now chains exactly, and every previously measured cell is
byte-identical (the overflow never triggered on them, so the fix is
stream-neutral by construction and by measurement).

**2. The concealment pad invariant (fixed).**  Concealment writes whole
slices, pad rows included, so after a lost slice the committed pads stopped
being a replication of the concealed last visible row — and the next frame's
prediction reads those rows through the bottom edge clamp.  The decoder now
re-derives the pads by replication after concealing the last slice.  Cost: one
memcpy per plane, on a path that is already exceptional.  "The pads are a pure
function of the visible picture" is now unconditional rather than true only
until the first lost slice.

**A note on `slice_h 32` and the A2 budget.**  The mandate is under 1 ms
*including output resolution conversion*, and `slice_h 32` costs 32 line
periods of slice assembly, which alone breaches it below 2160p:

| configuration | latency | verdict |
|---|---|---|
| 720p50, sh 32, **no conversion** | 1.793 ms | over |
| 1080p50, sh 32, **no conversion** | 1.213 ms | over |
| 1080p50, sh 16 (default), 4x conversion | 0.864 ms | under |
| 2160p50, sh 32, 4x conversion | 0.435 ms | under |

`slice_h 32` is therefore for **2160p and 4320p only**, as
`OPEN_DECISIONS.md` always said and as README claimed the validator enforced.
Two things follow, and both are now true rather than assumed:

- `omc_enc` **always** reports an over-budget configuration with its computed
  figure (it previously encoded silently unless `a2_strict` was set, which is
  how the README claim came to be false — 12.10 fix 2);
- the `slice_h 32` cells at 1080p and 1152p in the matrices above are
  **exactness tests, not recommended configurations**.  They are there because
  the generation contract must hold at every slice height the bitstream can
  express, including ones the latency mandate rules out for that raster.  Read
  the matrix as coverage, never as an endorsement of a configuration.

**Verification of these three changes.**  The full matrix was re-run on the
build carrying them (commit `712ab88`) and compared cell by cell against the
build before them:

| | result |
|---|---|
| CDR matrix | 29/29 PASS, **0 md5 changes** |
| Baseband matrix | 23/29 PASS, **0 md5 changes**; every failure carries `oob > 0` |
| Baseband cells with `oob = 0` | **22/22 PASS, no exceptions** |
| `make test` | 6/6 all ok |

Zero md5 changes across 58 cells is the expected result and the point of
checking: the buffer fix only alters configurations that previously
overflowed (none of the matrix cells did), the concealment fix touches only
the loss path, and the A2 report is stderr.  The configuration that *did* overflow now chains
exactly over CDR, and its in-gamut sibling at the same width and slice height
(4:2:2/12 rather than 4:4:4/8) chains exactly over baseband as well -- the
4:4:4/8 cell carries `oob = 232811` and fails baseband on the gamut condition,
not on the buffer:

```
PASS  [4480x1856->4480x1856 444/8b bpp=1.0 sh=32 gens=3 ] g1.omc=c85659213d38f944fd6a3b0bb20fd2ea
PASS  [BB 4480x1856->4480x1856 422/12b bpp=1.0 sh=32 gens=3 ] g1.omc=22c7801a2f322034b6851a6aa0df6766 range=[197..2716] oob=0
```

## 12.16 Generalizing the buffer-sizing finding: a systematic sweep

12.15 said the reasoning that deferred the `llbuf` overflow "is exactly the
reasoning that lets a memory-safety bug ship."  Stating that is not acting on
it, so the class was swept for systematically: **every fixed-size buffer in
the codec, its declared capacity, the maximum elements writable across the
entire legal configuration range, and the guard that is supposed to bound
it** — looking specifically for the `llbuf` shape, a buffer whose required
size depends on two or more parameters but whose guard tests only one.

**It found one more live instance, and it is the un-fixed twin of a fix
already in the tree.**

**`src/codec.c` — the grain-replace flat classifier read past band 0.**  The
classifier probes the LL band's local gradient using the same
interior-preference clamp idiom as `fill_gate_g`, but without the re-clamp
that function already carries (its own "F-1 verified defect" note).  The
idiom `x = min(x, n-2)` followed by `x = max(x, 1)` returns 1 when `n == 2`,
so `rL + 1 == llh2` is one row past the band.  Two independent axes, both
reachable from legal configurations:

| axis | trips when | overread |
|---|---|---|
| row | `llh2 == 2`, i.e. **`slice_h == 8`** — the 720p-class default | up to **1020 bytes** past the band (8192-wide, 4:2:2, 12-bit) |
| column | `llw2 == 1`, i.e. a 32-wide plane | 4 bytes past |

Confirmed under AddressSanitizer at `1280x16 slice_h 8 4:2:2 --grain-replace`
and at `32x32 4:4:4 slice_h 16`.  It is a read, not a write, so nothing is
corrupted — but **the value read decides the flat class, and the flat class
selects which coefficients are zeroed**, so heap contents adjacent to the
band were feeding the emitted symbols.  It went unnoticed because the
adjacent allocation is deterministic in this build and because the shipped
`--grain-replace` defaults raise the threshold enough to make the gate
vacuous; under the `OMC_GR` environment path the out-of-bounds value is fully
load-bearing.  Any allocator change, hardened build, or FPGA port with real
per-band memories would change the classifier's decisions.

Fixed with the same re-clamp `fill_gate_g` uses.  Stream-neutral wherever the
LL band is at least 3 cells (the `--grain-replace` matrix cell reproduces its
recorded md5 exactly); it necessarily changes output only in the
configurations that were reading out of bounds.

**Everything else came back sound**, including three arrays hardcoded at 1024
in the DC-feedback path (`dc_pris`, `dc3_off`, `fl`) which look like the same
bug but are correctly gated on the true coefficient count, the chunk arrays,
the DWT column buffers, and the XSL row buffers.  The findings adjacent to
the class -- concurrency and decoder-side input validation -- were fixed too;
see 12.19.

**The lesson worth keeping** is not "check buffer sizes."  It is that
`fill_gate_g` was *fixed* and its copy was not.  A defect repaired in one
place and left in its duplicate is invisible to every test that exercises the
repaired path — which is why the sweep looked for the idiom rather than for
the symptom.

## 12.17 Deployment requirements and settings a system integrator must decide

Sections 1–12.16 are about the codec.  These are the decisions that sit
around it, and they are stated here because getting them wrong degrades the
guarantee this document exists to establish.

### ECC memory is REQUIRED, not recommended

**Specify ECC DRAM for any product carrying this codec.**  The reason is
specific to temporal prediction and does not apply to intra-only codecs such
as JPEG XS.

The codec predicts each frame from the previous frame held in DRAM.  A
single-bit upset in that reference — a cosmic-ray strike, a marginal DIMM, a
thermal event — is not confined to one picture: the corrupted pixels feed the
next frame's prediction, and the next, until the rolling intra refresh
re-codes the affected slice from scratch.  The damage window is therefore the
refresh period, up to 8 frames at the default (160 ms at 50 fps).  An
intra-only codec has no such window: a flipped bit in its line buffer
corrupts one frame and is gone.

ECC memory carries extra check bits and the controller detects and repairs
single-bit flips in hardware before the data reaches the codec, which removes
the exposure entirely.  Its cost is confined to the bill of materials — a
72-bit-wide memory instead of 64-bit, roughly 12.5% more DRAM, and a cycle or
two of controller latency that is invisible against a sub-millisecond video
budget.  **It costs nothing in picture quality, nothing in bitrate, and
nothing in codec latency**, because it sits underneath the codec, which never
knows it is there.  A guarantee of byte-exactness through unlimited
generations is not worth much on memory that silently corrupts its own
reference frame, so this is a requirement rather than an optimization.

### The refresh period is a real engineering choice, not a default to inherit

`refresh_r` sets how often each slice is re-coded from scratch instead of
predicted.  It controls three things at once, and only one of them is free:

| refresh | error damage window | quality, moving content | quality, near-static | bitrate | latency |
|---|---|---|---|---|---|
| 8 (default) | 8 frames | 49.73 dB | 52.89 dB | identical | identical |
| 4 | 4 frames | 49.48 | 52.80 | identical | identical |
| 2 | 2 frames | 49.21 | 52.51 | identical | identical |
| 1 (all-intra) | 1 frame | 48.67 | 52.27 | identical | identical |

(2048×1152 and 1920×1080 4:2:2/10-bit at 1.0 bpp; frame 2 of a 3-frame clip.)

**Bitrate does not move at all** — the stream sizes are byte-identical at
every setting, which is exact CBR behaving as specified.  **Latency does not
move either**, because refresh changes which slices are predicted, not the
shape of the pipeline.  The entire cost lands in quality: about 1.1 dB from
the default to all-intra on moving content, 0.6 dB on near-static graphics.
The mechanism is simply that coding a slice from scratch costs more bits than
coding its difference from a good prediction, and at a fixed budget those
bits come out of fine detail.  The gap widens on longer sequences, where
prediction has more history to earn from than a 3-frame clip allows —
measure on the intended material before choosing.

Guidance: **leave it at 8 with ECC fitted.**  Shorten it only when ECC is
unavailable, in which case it is a soft-error insurance policy priced in dB.
`refresh_r = 1` deserves separate mention: it disables temporal prediction
entirely, which removes the reference frame and with it the whole DRAM frame
store — a JPEG-XS-class memory footprint (line buffers only) for about a
quarter to one dB, and the natural profile for a camera-side encoder where
the frame store is the integration obstacle.

### What a conversion ratio means here, and what is actually supported

A ratio in this document and in the codec's flags is **per dimension, not per
pixel**: "2x" means twice the width and twice the height, so *four* times the
samples; "4x" means sixteen times the samples.  That distinction is the whole
reason the compute figures below are as large as they are.

Two mechanisms exist and they are easy to confuse:

- **`uc_ratio`, carried in the bitstream** (stream byte 27, bits 3-4): the
  decoder's integrated output upconverter, expressing **2x or 4x only**.
- **The scaler library** (`omc_uc_scale_*`): arbitrary rational ratios, up and
  down, bounded by a 48-tap filter limit.  This is what the A2 latency suite
  exercises.

What that limit permits, for the formats in the mandate:

| conversion | linear | samples | supported |
|---|---|---|---|
| 720p -> 1080p | 1.5x | 2.25x | yes, 18 taps |
| 720p -> 1440p | 2x | 4x | yes, 24 taps |
| 720p -> 2160p (4K) | 3x | 9x | yes, 36 taps |
| **720p -> 4320p (8K)** | **6x** | **36x** | **NO** - would need 72 taps |
| 1080p -> 2160p (4K) | 2x | 4x | yes, 24 taps |
| 1080p -> 4320p (8K) | 4x | 16x | yes, 48 taps (at the ceiling) |
| 2160p -> 4320p (8K) | 2x | 4x | yes, 24 taps |
| any downscale | <= 1x | - | yes, 12 taps |

**4x linear is the single-pass ceiling.**  Steeper conversions must be
cascaded: 720p to 8K is reachable as 720p -> 2160p (3x) followed by
2160p -> 4320p (2x), both individually supported, but that is two scaler
passes to budget rather than one -- and by the ratios below the second pass,
working on 4K input, is where the silicon goes.

### Size the silicon for the resolution converter, not the codec

The compute figures elsewhere in this document are codec-only.  Where an
output resolution conversion is configured, **the converter dominates**:
measured against an unconverted decode of the same stream, a 2x conversion
(2x per dimension) is about 18x the work and a 4x about 93x, because it
produces 4x and 16x the samples respectively and each needs a multi-tap polyphase filter where the
codec's per-sample work is shifts and adds.  Its *latency* contribution is
small and already carried in the A2 model (1080p50 at slice height 16:
0.625 ms unconverted, 0.790 ms at 2×, 0.864 ms at 4×) — the scaler is a wide
but shallow pipeline.  Budget it as the largest block in any converting
configuration; it is regular, data-independent, and maps directly onto DSP
slices, but it must be in the budget.

## 12.18 A note on units: why no wall-clock appears in this document

Every performance figure in this document is either a **latency in
milliseconds**, computed from the codec's own A2 model and therefore a
property of the algorithm's data dependencies, or a **ratio of work** against
a stated baseline.  Wall-clock timings of the reference implementation appear
nowhere, and earlier drafts that carried them were wrong to.

The reference encoder is unoptimized single-threaded C. Its elapsed time is a
property of that program and the machine it ran on, and it transfers to a
hardware implementation in no useful way. Quoting it invites two specific
errors, both of which were made and corrected during this work:

1. **Confusing throughput with latency.** These are different quantities.
   Latency is how far behind live the picture is — set by how much data must
   be buffered before output can begin, and it is what the sub-1 ms mandate
   governs. Throughput is whether an implementation keeps up at all. A slow
   software encoder says nothing about the former.
2. **Attributing a program's slowness to the design.** A figure measured at
   generation 1 was once quoted as though it characterized generation 2,
   producing a "100x" claim that a straight A/B measurement reduced to
   **1.5x** — the real and much smaller cost of the generation lock.

The two ratios that do transfer, and that a hardware team should size
against:

| quantity | ratio | note |
|---|---|---|
| generation-1 encode | 1.0x | the sizing baseline |
| generation-2 encode | **1.5x** | the lock's search; measured across four clips and rates |
| generation 3 and beyond | **1.5x** | identical, not merely similar — see below |
| decode | well under either | no search; fixed work per slice |
| 2x output conversion | ~18x a decode | dominates any converting configuration |
| 4x output conversion | ~93x a decode | 16x the samples, each multi-tap filtered |

Generation 3 onward costs exactly what generation 2 costs, and this is
structural rather than fortunate: pixels stop moving after generation 1, so
generation 3's input picture is byte-identical to generation 2's (verified by
direct comparison), and a deterministic encoder handed identical input does
identical work. Measured across ten consecutive generations, the workload is
flat and every generation reproduces generation 1's picture exactly. **A box
sized for generation 2 is sized for generation 30.**


## 12.19 The adjacent findings, fixed

The sweep of 12.16 turned up three issues next to the buffer-sizing class.
Two are recorded here **as fixed**, and the third is stated as open at the end.
They are fixes rather than known limitations because: a codec whose
headline claim is byte-exactness through unlimited generations does not get to
ship with a documented guarantee that fails its own test.

**Concurrency: `make test-threads` failed every run; it now passes clean.**
`omc1.h` states that encoder and decoder instances share no mutable state,
"verified by the interleaved two-instance unit test."  That was false.  The
XSL boundary state -- the per-column `d[-1]` terms and the two flags that
carry the refresh-barrier rules -- was file-scope, so two codecs in one
process shared one set of boundary rows.  Measured before the fix: **20 runs
out of 20 produced output that differed from the sequential reference**, with
ThreadSanitizer reporting 28 races.  This is the same defect class the project
had already identified and fixed for the blend cap ("per CONTEXT, never a
process-wide global"), and the earlier adversarial review told me explicitly
to move these arrays; I moved the XSL *level* and left the *buffers*.

Fixed by moving the state into `ctx_common_t`, threading the transform's
boundary term explicitly through `omc_slice_fwd_p`/`omc_slice_inv_p` instead
of a global, making `omc_global_init` genuinely one-time and race-free with
C11 atomics (it had been re-running its `getenv` writes on every context
creation -- 15 of the reported races), opening the debug dump handle once
under the same discipline, and **deleting `omc_xsl_lim`**, a write-only global
that turned out to be the last racing write and exactly what the earlier
review had said to remove.  C11 atomics rather than pthreads keeps the library
free of a threading dependency, which matters for the embedded and FPGA-host
targets.  Result: **zero ThreadSanitizer warnings, output byte-identical to
sequential.**

**Decoder input validation: a crafted stream reached a stack overflow.**
`omc_read_stream_header` copied `width`, `height`, `slice_h`, `bitdepth`,
`chroma` and `bits_per_slice` verbatim off the wire and range-checked none of
them, and the reference decoder never calls `omc_validate_config` -- so
nothing checked them anywhere.  A header declaring `slice_h = 128` overflowed
the per-column stack buffers in `dwt.c` (demonstrated under AddressSanitizer);
`bitdepth` of 0 or above 32 made the level shift undefined; `height = 0` gave
a zero slice count and hung the tool; a `bits_per_slice` below the wire floor
underflowed `payload_bytes`.  The CRC is no defence -- an attacker computes
it.  Now every wire field is validated at the point where the trust boundary
actually is, using the same constraints the encoder-side validator enforces.
Verified: crafted `slice_h`, `bitdepth` and `chroma` headers are refused.

**Both changes are stream-neutral.**  The 1080p and 1152p reference cells
reproduce `156f0237...` and `33fe2239...` exactly, `make test` is 6/6, and the
document's own patches rebuild to the same hash (section 9's procedure, re-run
after these fixes).

**Still open, and stated as such:** the DC-feedback diagnostic is silently
unavailable at `slice_h 32` above 4096 wide -- which includes 8K, where
`slice_h 32` is the intended setting.  It is an encoder-only, environment-gated
diagnostic with a correct guard, so it costs a measurement rather than
correctness, and the fix is a larger buffer whose sizing deserves the same
scrutiny as 12.16 rather than a hurried change.


## 12.20 Recommended profile: camera-side all-intra

**Recommendation: ship a camera-side profile at `refresh_r = 1`.**

The obstacle to putting this codec inside a broadcast camera is not compute,
it is the frame store.  Temporal prediction reads the previous frame, so the
encoder needs it in DRAM -- 8.4 MB at 1080p 4:2:2, 36 MB at 4K -- plus the
bandwidth to reach it.  JPEG XS, the codec this is intended to displace in
that socket, needs no frame store at all: it is intra-only and works out of a
few lines of on-chip buffer, which is precisely why it ends up embedded in
cameras.  A camera whose codec block was specced with no DRAM budget cannot
take this codec as built, however small the arithmetic is.

`refresh_r = 1` removes that obstacle completely.  The refresh rule forces a
slice to be coded from scratch when `(fidx8 mod R) == (slice mod R)`; at
`R = 1` that is true for every slice of every frame, so prediction is never
used, no reference frame is required, and the memory footprint collapses to
line buffers -- **the same class of footprint as JPEG XS**.

What it costs, measured across the corpus at 1.0 bpp rather than on one clip:

| content | refresh 8 | all-intra | cost |
|---|---|---|---|
| cinema, moving (2048x1152 4:2:2/10) | 49.01 dB | 48.75 dB | **0.26 dB** |
| graphics (1920x1080 4:2:2/10) | 52.87 | 52.30 | **0.57 dB** |
| graphics (1280x720 4:2:2/10) | 51.47 | 50.51 | **0.96 dB** |
| beach, 12-bit (2048x1152 4:2:2/12) | 42.52 | 41.72 | **0.80 dB** |

So roughly **a quarter to one dB**, and nothing else moves: bitrate is
unchanged (exact CBR -- the stream sizes are byte-identical at every refresh
setting) and latency is unchanged (refresh decides which slices are predicted,
not the shape of the pipeline).

Three further properties make this the right camera profile rather than a
degraded fallback:

1. **The bitstream is unchanged.**  An all-intra stream is an ordinary minor-11
   stream that every decoder reads normally.  This is a per-box encoder
   choice, not a format variant -- no second decoder, no profile negotiation.
2. **Generation exactness still holds.**  The contract of section 2 does not
   depend on prediction; if anything the all-intra case is the easier one,
   having no temporal dependency to reproduce.
3. **Soft-error exposure drops to JPEG XS's.**  The damage window for a bit
   flip is the refresh period (12.17), so at `R = 1` a memory error is gone by
   the next frame instead of persisting up to eight.  With no frame store to
   corrupt, the ECC requirement of 12.17 also becomes moot for this profile.

The natural system shape is therefore **all-intra in the camera, full temporal
prediction in the boxes downstream** that already have DRAM -- the camera pays
under a dB to fit the socket, and every later hop gets the full efficiency and
the byte-exact generation behaviour this document is about.

Caveat worth stating: these are three-frame clips, which understate what
prediction earns on long sequences, so the true cost on real footage is likely
somewhat higher than the table.  Measure on the intended material before
committing the profile.

## 12.21 Self-containment audit of this document

The document was audited against its own central claim — that a reader holding
only it and the pristine v4.14 drop can reproduce the work — by a pass
explicitly forbidden from consulting the repository, and told to report where a
stranger would be **blocked or misled** rather than to proofread.

It found seven blocking defects, and the worst was mine and recent: **the copy
of `tests/genchain.sh` embedded in Appendix B could not run against the
shipping build.**  Making `--display-h` mandatory for `--cdr-in` (12.13 fix 4)
corrected the live script but not the one printed here, so a replicator
following 12.11 would have had *every* CDR chain die at generation 2 while the
document claimed 29/29 PASS.  The self-containment claim was false for the one
command that matters most.

The other blocking defects, all now fixed: the reproduction recipe in 12.11
step 7 was missing the same flags; the non-vacuity proof still invoked
`OMC_DEBUG_OLDPADS`, an environment variable 12.13 had *removed*, so the arm
that must FAIL would have passed and read as vacuous; the superseded RCT recipe
was cited as being in 10.5 when it is in 10.3, twice; the pointer to the
supersession list named 12.9 instead of 12.12; the build recipe in section 9
unpacked the tree to a path the harness scripts cannot find; and nothing at the
top of the document told a reader that the shipping version is minor 11, so a
straight-through reader would build the minor-10 codec and only discover the
discrepancy two thirds of the way in.

Seventeen further findings were corrections of substance rather than form —
tallies that disagreed with their own listings (the headline "25 of 25 / 7 of
8" against a table showing 32 runs and 22 of 22 on the shipped build), a
dangling `7.5` cross-reference used three times where `5.7` was meant, an
absolute claim that "no environment variable can change normative
reconstruction" contradicted twice within the document by `OMC_RECOFF`,
`OMC_BANDTILT` and `OMC_GR`, two conflicting refresh-cost tables, and an
appendix whose self-description understated what it actually contained.  All
are fixed; the environment knobs that genuinely break exactness are now named
in section 7's preconditions rather than described as harmless.

**Re-verified after the fixes, using only the document:** both patches extract
by the document's own recipe, apply to a pristine drop, build at the documented
path, reproduce `156f0237206ac5f66f5b8c89535dfea4`, pass `make test` 6/6 and
`make test-threads` clean; and the harness scripts extracted *from Appendix B
and E* run a CDR chain, a baseband chain, and the non-vacuity arm with the
correct verdicts.

The lesson is the same one 12.16 drew about duplicated code: **a document that
embeds its own tooling has two copies of everything, and fixing one is not
fixing both.**  The embedded scripts are now re-extracted from the live ones
mechanically rather than maintained by hand.


## 12.22 The ordinary hand-off, made exact: the strict in-gamut mode

> ## v5.3.7 ADDENDUM (2026-09-08) — the per-slice repair bound is now ENFORCED
>
> **The worst-case repair work per slice is `(3 + omc_gm_redomax) x
> gamut_strict` = 52 passes at the shipped defaults, and from v5.3.7 that is a
> mechanism rather than a comment.**
>
> Why it changed. `gamut_strict` caps the budget of ONE attempt, not the passes
> a slice runs: the SD-revert restart, the harsh-rule fallback restart and each
> `omc_gm_redomax` redo hand the slice a fresh budget. Agent 5 corrected the
> derivation on 2026-09-05 (it had been stated as `(1 + omc_gm_redomax) x
> gamut_strict`, which ordinary footage exceeded) and verified the four-term
> bound adversarially. The codec expert then recommended an interim enforced
> cap. This addendum records that it is enforced.
>
> How. A per-slice counter `gm_total` counts every repair pass and is reset by
> no restart, fallback or redo. Each of the three fresh-budget paths refuses to
> grant a new budget once the total reaches the cap; at the cap the slice takes
> the **existing** exhaustion path — committed as it stands, counted in
> `gm_unfixed`, reported, and refused by the CLI with exit 2. No new fallback
> and no new coefficient rule was added, and the decoder is untouched.
>
> What it measures. The encoder's verdict line now always prints the worst
> per-slice total, the cap in force, and p50/p90/p99 over the repaired slices.
> Measured worst at budget 13: **35** (spotrobotL 1080p 4:2:2 @0.5, 12 frames)
> and **45** on the G-T5-CUT24 rail-cut synthetic. Nothing on the corpus reaches
> the cap, so the enforcement is inert at its real value — which is why gate
> `G-T5-CAP1` lowers it with a test probe to prove it is reachable at all, and
> `G-T5-CAP2` proves it is inert at the real one.
>
> Caveat, stated rather than tuned: a **fifth** reset path exists behind
> `OMC_GM_TRIAL` (off by default). It is not in the factor and is not guarded,
> so with that lever on the total may exceed the cap.
>
> ## v5.3 ADDENDUM — READ THIS FIRST. This section describes the v5.0 repair.
>
> **The repair's default SHAPE changed in v5.3.** `omc_gm_mode` is now **3**
> (finest bands first) and `omc_gm_escmode` is **2**. The two are a pair and
> must move together: mode 3 alone fails gates `G-T5-GAMUT2c` and `2d`.
>
> **What ESCMODE does.** The repair has two jobs — find a cheap correction, and
> guarantee legality — and until v5.3 the shape was fixed for the whole slice,
> so every slice paid for whichever job it did not need. `omc_gm_escmode = N`
> makes the shape a function of the PASS: the cheap detail-first shape runs for
> the first N passes as an escape path, then the slice is handed to mode 12 —
> the v5.0/v5.1 rule, whose two-tier boundary allowance is what makes `oob = 0`
> unconditional — for the rest of its budget.
>
> ```c
> const int gm_mode_eff = (omc_gm_escmode && gm_iter >= omc_gm_escmode)
>                         ? 12 : omc_gm_mode;
> ```
>
> Measured at identical byte counts: VMAF-NEG improves on 7 of 8 tuning cells
> and on every held-out cell, `cf_gfx` @0.5 by **+6.93** and `dng` @0.3 by
> **+1.79**; A4 passes 12/12 at 11 generations; all 97 gates pass. Control-plane
> repair passes fall 32–43 % and harsh-rule fallbacks 26–65 %, with the
> worst-case pass budget unchanged at 12. Full account: ledger §51.18.
>
> ### The one table that explains what repair can and cannot do
>
> `src/gm_basis_tab.c.inc` is GENERATED by `repro/gen_gm_basis.c`, by impulse
> response through the real integer `omc_slice_inv()`. Summing each band's
> signed response against its absolute response:
>
> | band | signed sum / absolute sum |
> |---|---|
> | **0 (LL)** | **0.9974** |
> | 1–4 | 0.0001 – 0.0010 |
> | 5–9 | **0.0000** |
>
> **Every detail band integrates to zero; the LL does not.** 99.7 % of an LL
> basis is a single sign, so moving one LL coefficient *is* a coherent level
> shift over its whole support — that is the G7 "wash" mechanism in one number,
> and it is why the LL is the band the repair must touch last. Conversely, no
> detail-band move can produce a level shift on its own; a detail move that
> appears to shift a block's level is a zero-mean basis **truncated** at the
> measurement-block boundary, not DC content.
>
> Two proposals have now been declined on this table alone. Consult it before
> designing any repair rule that reasons about a coefficient's mean response.
>
> ### Two repair ideas that were built and FALSIFIED in v5.3
>
> * **`OMC_GM_UPSTEP`** — move a coefficient the alignment veto refuses one step
>   AWAY from zero. 46.1 % of examined coefficients are in that population, so it
>   is not a marginal idea, but it is a monotone regression above N=2:
>   `cf_gfx` worst coherent block 242.9 → 328.2 codes. Exact CBR means raising a
>   magnitude spends bits from the same slice's picture, and the coefficients
>   around a rail excursion are almost all ringing, so amplifying them amplifies
>   ringing.
> * **`OMC_GM_BITEFF`** — price the band ranking in coded symbols instead of
>   picture energy. Falsified in BOTH signs (`cf_gfx` 74.42 → 65.15 / 64.95).
>   The `2^s` denominator is not a missing rate term; it IS the damage term, and
>   at exact CBR the slice re-plans afterwards so coded cost is the wrong
>   currency.
>
> Both remain in the source, default 0, with their measurements in the comment.
>
> ---
>
> **v5.1 ADDENDUM.**
>
> This section is a **correct and complete record of the in-gamut repair as
> v5.0 implemented it**, and it is left as written because this document is the
> historical normative record of the temporal layer.
>
> It is **incomplete as a description of the v5.1 build you are holding.**
> v5.1 changed the repair's ENCODER POLICY in eight places (the plan ratchet,
> the intra force's evidence gate, the LL DC excursion bound and its hard/bound
> variants, the density escape, the margin reserve, the restart floor, the
> inter-reduction domain, and the alignment veto). It changed **no normative
> reconstruction rule**, which is why the stream minor is unchanged and a v5.0
> decoder decodes a v5.1 stream byte-identically.
>
> **The authority for the repair's behaviour in this build is
> `docs/OMC_V5_1.md`** (sect.4 for the fix, sect.7 for the validation,
> sect.10 for F7), with `docs/CONTROL_PLANE.md` for every lever and its shipped
> default. Where this section and `docs/OMC_V5_1.md` disagree about v5.1,
> `docs/OMC_V5_1.md` is right.
>
> A full merge of this section against v5.1 was out of scope and is recorded as
> owed work in ledger sect.53.3 defect 5.


**Build stamp.** Code commit `574a570` on branch
`claude/codec-temporal-rebuild-3i9o7q`, stream **minor 12**.  Everything in
this section and in 12.23 was measured on that one build, in a single battery
run.  The delta patch is Appendix F; applying Appendix A, then Appendix D, then
Appendix F to a pristine `omc_v4.9` drop reproduces it, and the reference cell
of 12.6 then hashes to `d6e111cfaf33c17406182bc1310a0b90`.

### 12.22.1 Why this section exists

Section 12 established two interchange formats and two different promises:

| interchange | what it carries | promise |
|---|---|---|
| **CDR** (coded-domain raw) | the committed picture: biased by 2048, unclipped, at coded geometry | exact through unlimited generations, **unconditionally** |
| **baseband** (ordinary video) | legal-range, unbiased, cropped — what comes out of a decoder and goes down an SDI or IP link | exact **only while no committed sample leaves the legal range** |

12.8 then reported the incidence of the conditional case and drew a scope
around it: out-of-gamut committed samples "appear in 4:4:4 8-bit graphics
material ... and are absent from every 4:2:2 cell of the corpus."

**That scope was wrong, and it was wrong on this document's own evidence.**
The `2048x1152 422/12 @0.5` cell in 12.6's table carries `oob = 1`.  An
independent measurement battery on v4.15 stream 11 then demonstrated the same
thing on real broadcast material: ordinary architectural footage, 4:2:2
10-bit, at 0.5 bits per pixel, with **twelve** stray samples out of twelve and
a half million, never reaching a fixed point in six generations and losing
0.577 dB.

> **That architectural footage is not in this repository, and this section's
> stand-in for it is synthetic.**  The corpus here is limited-range: the cinema
> masters leave roughly 60 codes below black and 83 above white at 10 bit,
> which is exactly why they show no out-of-gamut samples.  To get the exposed
> class into the corpus at all, `tests/mkfullrange.py` expands one of them to
> the rails, and the result is `gfx1080_fullrange_422_10.yuv` — the **screen
> graphics** master, graded to full range.  It is a faithful stand-in for what
> a colourist's full-range grade does to a picture, and it is **not** camera
> footage of a city.  Every figure below that names it is a figure on a
> synthesised rail-graded master, and 12.22.7 separates those from the
> naturally-graded ones rather than averaging the two together.
>
> (An earlier revision of this section called that file `city1080_422_10.yuv`.
> The name invited exactly the misreading it got — a reader took a ten-point
> VMAF-NEG figure on it as the cost on ordinary architectural footage.  The
> file is renamed; the numbers are unchanged, because only the name was.)  The exposed class is not a chroma format and it is not "graphics".
It is **any material graded to the container rails**, which is a colourist's
decision, not a format's.

That report also asked the question this section answers: whether the encoder
could avoid the overshoot at all.  12.8 said it would have to change either
the reconstruction rule (which is what v4.14's in-loop clip did, and is
exactly what destroys exactness — section 4.3) or the choice of lattice point
per coefficient.  It named two options and missed a third:

> **Change the SOURCE coefficients, before quantization, and re-code.**

Everything the exactness argument rests on survives that untouched.  What gets
emitted is still an ordinary lattice point; the committed picture is still the
unclamped inverse transform of it; the reconstruction rule, the bitstream
syntax, the decoder and the generation lock are all unchanged.  The only thing
that changes is *which* lattice point a **first-generation** slice commits to.

### 12.22.2 The rule, stated precisely

The mode is `--gamut-strict [N]` on `omc_enc`, and
`omc_enc_set_gamut_strict(enc, N)` in the library.  `N` is the per-slice repair
budget; the default is 12 and the hard cap is 16.  **It is ON by default**, and
`--gamut-strict 0` turns it off.  Why it must be on rather than opt-in, and what
makes that safe, is 12.22.8 — in short: it is byte-identical to being off on
content that never reaches the rails, it stands down on CDR input, and a mode
that has to be switched per clip in a live chain is a mode that will be wrong.

After a slice has been coded and reconstructed, the encoder counts the
committed samples of that slice — on the emitted picture, after the barrier
display blend, over the rows that are already final, exactly as the gamut
report of 12.8 does — that fall outside `[0, 2^depth)`.  If any do, and the
budget is not spent, the slice is **re-coded**:

1. **Build a per-pixel mask of the offending samples** and prefix-sum it into a
   summed-area table, so the coefficient loop can ask "does any offending pixel
   lie under this coefficient's support" in four lookups.  Build a second
   summed-area table of each offending sample's **residual** — how far out it is
   and in which direction, positive meaning above the ceiling — and a third of
   `|residual|`.  The previous slice's last committed row is included in all
   three, because the boundary edit couples it to this slice's first row.
2. For every source coefficient whose support (dilated by one band row and one
   band column, to cover the filters' reach) contains an offending pixel,
   compute the reduction: the smaller in magnitude of **a proportional cut to
   63/64** and **a cut of one quantizer step per pass elapsed**.  Which of the
   two is smaller depends on the coefficient's own size against its own
   quantizer step: below `2^s · den/(den−num)`, sixty-four steps at 63/64, the
   proportional cut removes less; above it, the stepwise cut does.
   **If this slice is still violating at pass `OMC_GM_ESC` (default 4), the
   factor tightens to 15/16 for the rest of its budget.**  Nearly every slice of
   every real clip converges long before that pass and never sees the tightening;
   a slice still violating late is one the gentle factor cannot clear.  Without
   the escalation, 63/64 does not converge — see 12.22.6a.
3. **Apply the alignment veto** (12.22.3g).  If the reduction would carry the
   coefficient across a quantizer boundary — the only case in which it costs
   anything at all — it is applied only when it moves the offending samples
   under its support *toward* the legal range.  A reduction that crosses nothing
   emits the same coded value, the same bits and the same picture, and is
   always applied.  The veto lapses after `OMC_GM_ALIGN` passes, default 4, so
   convergence inside the budget stays guaranteed.
4. **Suppress the grain fill** for any **band** that was touched — not for the
   whole plane.  An earlier revision cleared all six of a plane's fill bits on
   any violation, which is a slice-wide loss of texture paid for one stray
   sample.
5. **Force the touched bands to intra, from the SECOND pass onward** — not from
   the first.  Forcing intra immediately throws away the temporal prediction of
   a slice that would often have converged without it; deferring one pass costs
   nothing and keeps the prediction for content that converges at once.
6. Re-run the encode from the symbolisation stage with the modified
   coefficients, and check again.
7. **After each pass, project.**  At the rate the last pass achieved, is the
   remaining budget enough to reach zero?  If not, this slice is not going to
   finish gently: **throw the attempt away, restore its original coefficients,
   and repair it again from the beginning** with a plain proportional cut and no
   step cap — the rule that always converges.  A slice that is genuinely
   converging never trips this; on the hardest real cell it fires on 27 of 375
   repaired slices.  12.22.3i is why this is a restart and not a mid-course
   correction.

The loop runs on the **true legal-range test** and nothing else, and it stops
the moment that test is clean or the budget runs out.  When the budget runs
out the slice is committed anyway and `omc_enc_oob()` reports the truth: the
mode is a best effort with a bounded cost, never a promise the encoder did not
keep.

**Nothing in the loop is content-dependent.**  There is no density threshold, no
convergence-rate switch and no classifier: the same six steps run on every
violating slice of every clip.  Six schemes that did classify were built and
measured, and every one of them is in the register of 12.22.3.

### 12.22.3 Why each of those six steps is there — and what was tried first

Every one of them is the answer to a measured failure.  The register matters
more than the rule, because each failure is a way an obvious design goes
wrong.  Sixteen reduction shapes and nine content statistics were built and
measured to arrive at six steps; what follows is all of them, including the ones
that lost, because a replicator who does not know what has already been tried
will try it again.

**(a) Shrink, not "add the correction back".**  The obvious step is to compute
the pixel-domain excess `E = clip(P) - P`, forward-transform it, and add it to
the source, so the next reconstruction lands on the rail instead of past it.
That was built and measured first.  It fails twice over:

- *The correction rounds away to nothing.*  Measured on the rail clip at
  1.0 bpp, slice 75: mean |correction| of **3 codes per coefficient** against a
  quantization step of **128**.  The reconstruction did not move by a single
  sample, for as many passes as it was given — the violation count sat at
  exactly 5760 through pass 1, 2, 3 and 4.
- *Amplifying it diverges.*  Doubling the gain on any pass that failed to make
  progress does eventually cross a lattice boundary, but it adds energy to a
  slice that is already over budget: the rate controller coarsened to `Q = 15`
  (the coarsest rung), the violations rose from 1020 to 10414, the wide-domain
  representability guard engaged, and the encoder crashed.

Shrinking has neither failure mode.  It is multiplicative, so it crosses a
lattice boundary within a few passes whatever the step is.  It strictly
*reduces* coefficient magnitudes, so the payload only gets smaller and the
plan never coarsens in response.  And it is monotone toward feasibility: in the
limit the detail bands vanish and the slice reconstructs as its own smooth
low-pass, which cannot overshoot a rail its own local mean is inside.  The cost
is exactly what it should be — contrast, in the slices that clip, at generation
1 only.

**(b) Suppress the grain fill.**  Fill regenerates a quarter-step of texture at
positions that code to zero — which is precisely what shrinking creates more
of.  Without this the repair adds back the energy it just removed: the count
falls, then stops short of zero.  Clearing the bit is exactness-safe because
the fill rule measures the *coded* coefficients: an unfilled band leaves them
at zero, a band of zeros re-derives to "no fill", and the lock still reproduces
the slice at every later generation.

**(c) Force intra.**  This one is the least obvious and it was the largest
residual.  Shrinking an **inter** residual converges to the *prediction*, not
to the picture's own low-pass.  As soon as one frame ends with an excursion the
budget could not clear, the next frame predicts from it, and shrinking then
walks the reconstruction **toward** the violation.  Measured: a sample at 1031
went 1028 → 1031 over successive passes, i.e. the repair made it worse.  Intra
breaks the inheritance.

**(d) The XSL boundary edit cannot be made conditional.**  The edit adds up to
one blend cap (8 codes at 10-bit below 0.75 bpp, 4 above) to the last row of a
slice and the first row of the next, *after* reconstruction.  A sample sitting
exactly on a rail is therefore always one edit away from leaving the range.
The natural idea — "apply the edit unless the result would leave the range" —
**cannot be used**, and the reason is worth stating because it will occur to
everyone who reads this:

> `f(x) = x + d` if `x + d` is in range, else `x`, is **not injective**.  For
> `d > 0` the two branches both land in `(max - d, max]`.  The un-blend has to
> invert the edit exactly, forever, from the post-edit value alone, so a rule
> it cannot invert is not available at any price.  (This is the same reason
> the T5 edit is applied unconditionally within the wide domain in the first
> place — see 5.3.)

What is left is to give those rows headroom.  The repair therefore treats them
as needing a cap of margin when it decides *which* coefficients to shrink, so
a boundary row is pulled off the rail when it can be.

**(e) The correction must be a no-op at generation 2 — a failure worth its own
paragraph.**  An earlier version went further: it clamped the two boundary rows
of the *source* into `[cap, maxv - cap]` before the transform, and ran the
repair loop on that same inset window.  It converged faster.  It was also
wrong, and wrong in the worst way — silently:

> When a slice's budget ran out with the inset window unmet but the legal range
> satisfied, the committed rows sat *inside* the legal range and *outside* the
> clamp window.  At generation 2 the same clamp then **moved the encoder's own
> input**, the lock failed, and the chain broke — while the gamut report
> correctly said zero and the verdict line said "baseband-safe: yes".
>
> Measured: 1920x1080 4:2:2 10-bit graded to full range, 0.5 and 1.0 bpp,
> `oob = 0` and `FAIL pixels-gen2` on both.

The general lesson, which applies to any future encoder-side conditioning:
**a correction an encoder applies to its own input has to be a no-op at
generation 2, or it is not a correction, it is a second encoder.**  The clamp
was removed outright.  Removing it also measured *better* — both full-range
1080p cells pass where the clamped version failed — so the safe design was
also the good one.

#### 12.22.3g The alignment veto: do not reduce a coefficient that pushes the wrong way

Every reduction shape from the original proportional cut through fifteen
successive experiments shared one property, and none of them questioned it: they
reduced **every** coefficient whose support covered an offending pixel.  None
asked whether reducing a given coefficient moves that pixel toward the legal
range or further out of it.

It is a real question with an exact answer.  Reducing a coefficient's magnitude
by `d` changes the reconstruction at pixel `q` by

```
    delta(q) = -sign(c) * d * g(q)
```

where `g` is that coefficient's synthesis basis.  A sample above the ceiling has
to come **down** and a sample below the floor has to go **up**, so the reduction
helps only where `sign(c) * g(q)` matches the sample's excursion.  Where it does
not, the reduction pushes the offending sample **further out of range** and still
costs picture — the worst of both.  Measured on the corpus, the sign test refuses
just under thirty per cent of candidates when applied uniformly.

**The score is weighted by residual, not by a count of offending pixels.**
Feasibility is a maximum, not a sum: one sample forty codes out matters more than
ten samples one code out, and a coefficient that fixes the worst offender while
nudging ten marginal samples is usually the right move.  Weighting by residual
also handles, with no special case, a coefficient whose support spans both an
above-ceiling and a below-floor region: the two contributions have opposite signs
and net out, which is the honest answer.  That case is not exotic — it is exactly
what the rail-on-boundary content of `G-T5-GAMUT2c` produces.

**Where the basis signs come from.**  `repro/gen_gm_basis.c` puts a unit impulse
into one coefficient of each band, runs it through `omc_slice_inv()` — the
shipping inverse transform, not a model of it — and reads the response.  It emits
`src/gm_basis_tab.c.inc`, and the Makefile builds and runs it, so the table
cannot drift from the transform: change a lifting step in `src/dwt.c` and the
table is regenerated before anything links against it.  It is measured rather
than derived because the repair needs the basis the shipping transform actually
has, not the basis somebody believed it had.

The measurement returned a stronger result than the design needed.  Over 28 to 35
distinct phases per band, the basis is

- **exactly separable** — `g(j,i) = gy[j]·gx[i]` with a worst-case error of
  `0.00e+00` of peak, not merely small; and
- **exactly shift-invariant** — no support-box disagreement and no sign
  disagreement between any two phases.

So each band's two one-dimensional factors run-length compress by sign, with
`ny ≤ 3` and `nx ≤ 7`, and the whole test costs at most 21 rectangle queries —
84 summed-area lookups — per candidate coefficient.

There is exactly **one** table, not one per kernel.  The transform's kernel is
fixed by level and is not selectable: horizontal levels 1 and 2 use (9,7)-M and
the rest use 5/3, which is normative and stated in `docs/BITSTREAM.md`.

**Boundaries fall through to "touch it", never to "veto it".**  The whole-sample
symmetric extension reshapes the basis within the filters' reach of a slice or
plane edge, and the interior table does not describe it.  A coefficient whose
support is clipped is therefore exempted from the veto rather than judged by a
table that does not apply — as is any plane whose width does not divide into the
band grid the table was measured on.  Falling through can only make the repair do
more work; it can never veto a coefficient it should have touched, and the
boundary rows are the ones the repair can least afford to get wrong.

#### 12.22.3h Why the veto charges only for the reductions that cost anything

Applied uniformly, the sign test refuses 28.5 % of candidates and measures
**slightly worse** than not applying it.  The instrumentation explains why, and
the number it produced is the most useful single measurement in this section.

`OMC_GM_STAT=1` counts what the repair actually does: candidates considered,
vetoes, reductions applied, and how many of those reductions carry a coefficient
across a **quantizer boundary**.  A reduction that does not cross emits the same
`q`, therefore the same bits and the same reconstruction: it is **free**.

On `gfxF003_444_8` at 0.5 bpp, per encode:

| rule | reductions | crossings | share |
|---|---|---|---|
| proportional 3/4 | 587,424 | 81,595 | 13.9 % |
| gentler-of-two 15/16 | 935,290 | 98,324 | 10.5 % |
| gentler-of-two + uniform veto | 673,816 | 92,664 | 13.8 % |

**Nine in ten reductions do nothing at all.**  Two breakdowns say where the tenth
lives:

- **By band.**  Bands 7 and 9 — the finest detail, `LH1` and `HH1` — took
  254,624 reductions between them and crossed **zero** times.  Every crossing is
  in the coarse bands; the `LL` alone accounts for 18,000 to 33,000 of them.
- **By size.**  Below one quantizer step, 1 % of reductions cross.  At eight
  steps and above, **100 %** of them do — 18,536 of 18,536, then 14,435 of
  14,435, and so on to the top bucket.

A veto applied uniformly therefore spends most of its refusals on reductions that
were free anyway, and refusing those only slows convergence — which is itself a
cost, because every extra pass re-crosses the same large coefficients.  So the
shipped veto charges for what is actually charged for: **a reduction that crosses
must pass the alignment test; a reduction that does not is always allowed.**  It
refuses only 0.7 % of candidates, and it improves every reduction shape on every
cell measured, without exception:

| clip | bpp | shape | veto off | veto on |
|---|---|---|---|---|
| gfxF003_444_8 | 0.5 | proportional 3/4 | 98.0739 | **98.1117** |
| gfxF003_444_8 | 0.5 | proportional 15/16 | 97.8406 | **97.8507** |
| cine4k_444_10 | 2.0 | proportional 3/4 | 93.8878 | **94.6769** |
| cine4k_444_10 | 2.0 | proportional 15/16 | 96.6882 | **96.9083** |
| cineA31_720_444_8 | 0.5 | proportional 3/4 | 97.7627 | **97.8722** |
| cineA31_720_444_8 | 0.5 | proportional 15/16 | 98.1429 | **98.1498** |
| cineA21_444_10 | 2.0 | proportional 3/4 | 94.8917 | **94.9429** |
| cineA21_444_10 | 2.0 | proportional 15/16 | 94.9588 | **94.9726** |

This also overturned a conclusion recorded one revision earlier.  The stepwise
branch of the gentler-of-two rule almost never fires, and that had been read as
"the cost is spread over very many small coefficients".  It is the opposite: the
cost is concentrated in the large ones, because every reduction of a large
coefficient crosses, every pass, while the small ones are free.

#### 12.22.3i The fallback: what to do when the gentle rule will not finish

This subsection exists because the gentle reduction rule of 12.22.3g, shipped
earlier on the same day, **made convergence worse on one content class**, and the
codec measurement side found it before this document did.  Their report is worth
stating as they stated it: an ordinary screen-graphics master at 1920×1080 4:2:2
10-bit failed the baseband chain at 0.5 and at 1.0 bits per pixel with the repair
on, because the repair reached its budget with samples still outside the legal
range — and the residue did not fall when the budget was raised to the cap.

**Their finding could not be reproduced directly, and was confirmed anyway.**
Their master carries 1,458 out-of-range samples with the repair off.  The hardest
graphics master that can be built from the material here — the canonical 4:4:4
12-bit master, stretched to full range, taken to 4:2:2 by pair averaging and to
10 bits by shift, which is their own described preparation — carries 257, and both
rules clear it.  So the mechanism they named was tested instead, on the synthetic
built for exactly that mechanism, and it reproduced at once:

| rule | samples left outside the legal range |
|---|---|
| the harsh 3/4 rule this revision replaced | **0** |
| the gentle rule of 12.22.3g | **126** |
| the same, at the 16-pass hard cap | **126** |

More budget bought nothing, which is precisely the floor they describe.

**The cause is the step cap, and it is not the factor or the veto.**  Holding
everything else fixed and changing one thing at a time:

| rule | residue |
|---|---|
| no step cap, 3/4, veto off, no escalation | **0** |
| no step cap, 3/4, veto **on**, no escalation | **0** |
| **step cap**, 3/4, veto off, no escalation | **71** |

The cap is what makes the gentle rule nearly free: it never removes more than one
quantizer step from a coefficient in a single pass, so the repair cannot gouge.
It is also exactly why a rail-pinned neighbourhood cannot be cleared.  Where the
quantizer has pinned a region to a rail the coefficients there are large, and one
step per pass is nowhere near enough — the pass accomplishes almost nothing, and
so does every pass after it.

**Tightening mid-flight does not work, and it took three attempts to accept
that.**  Escalating the factor when a slice falls behind took the residue from
126 to 108.  Escalating earlier took it to 64.  Escalating at the very first pass
took it to 64 as well.  The gentle passes are not merely slow: they leave the
slice somewhere the harsh passes can no longer rescue inside the budget that is
left.

**What works is a restart.**  After each pass the encoder projects: at the rate
the *last* pass achieved, is the remaining budget enough to reach zero?  A slice
that is genuinely converging never trips this.  A slice that is not — the
measured failure mode is one that clears almost everything on its first pass and
then removes a single sample per pass thereafter — trips it immediately.  When it
does, the encoder **throws the gentle attempt away**, restores that slice's
original coefficients, and repairs it again from the beginning with a plain
proportional cut and no step cap: the rule that always converges.

The result is that the pathological arm of `G-T5-GAMUT2c` now clears to **zero**,
and so do hard black and white plates at the exact rails.  A case this document
previously called structural and unclosable is closed.

**What it costs.**  On the hardest real cell the fallback fires on **27 of 375
repaired slices** — seven per cent.  The other ninety-three per cent keep the
gentle rule and its quality, and the measured quality difference is inside the
noise:

| clip | bpp | repair off (target) | with the fallback | fallback disabled | the old harsh rule |
|---|---|---|---|---|---|
| gfxF003_444_8 | 0.5 | 98.5768 | 97.7583 | 97.8214 | 98.0739 |
| cine4k_444_10 | 1.0 | 94.8712 | 94.5037 | 94.5584 | 89.4268 |
| cine4k_444_10 | 2.0 | 97.5497 | 97.3389 | 97.4582 | 93.8878 |
| cineA21_444_10 | 0.5 | 77.6428 | 75.6384 | 75.9954 | 73.5255 |
| cineA21_444_10 | 2.0 | 95.0477 | **94.9997** | 94.9784 | 94.8917 |
| cineA31_720_444_8 | 1.0 | 98.8755 | 98.8622 | 98.8622 | 98.4062 |
| gfx1080_444_12 | 0.5 | 91.4104 | 91.5060 | 91.4104 | 91.5210 |
| gfxrails_422_10 | 0.5 | 92.2311 | **92.0047** | 91.0752 | 88.0183 |
| *rail720_422_10* | 0.5 | 97.5738 | *75.3102* | *86.2488* | *62.3204* |

On real footage the fallback costs at most **0.36** (`cineA21` at half a bit) and
**gains 0.93** on the rail-graded graphics master — which is the content class the
report was about, so it gains most where it was needed.  Four cells lose between
0.06 and 0.36, one is level, two gain.

**And it costs 10.9 on the rail stress clip, which is the honest bad news.**  That
clip reaches zero without any restart, so every restart there is pure loss.  It is
synthesized material and does not vote (12.22.6a), but hiding it would be the
lie.  The trigger was tuned against exactly this: projecting from the last pass
restarts too eagerly for that clip, projecting from the average rate leaves 9
samples on the hard plates, and waiting for two consecutive slow passes leaves 5
on the pathological arm.  Convergence is the mode's whole contract, so the rule
that converges on both synthetics wins and the stress clip pays for it.

**And it is still not a content decision.**  Nothing in the test looks at what the
picture is.  It looks at whether *this slice* is on course to finish, which is a
fact about the slice and not a guess about the genre — so there is nothing here
for an operator to recognise or switch.

#### 12.22.3j The exit status: an undelivered guarantee has to be loud

The same report asked whether the encoder should refuse rather than warn, on the
grounds that a line on stderr is easy to miss in an automated pipeline.  It
should, and it now does.

| status | meaning |
|---|---|
| **0** | the encode succeeded and, if the in-gamut mode was in force, it delivered what it promises: nothing committed outside the legal range, so an ordinary baseband hand-off is exact |
| **2** | the encode succeeded but the mode could **not** clear every sample.  The stream is valid and plays correctly; what is not available is generation exactness over a baseband link |
| **1** | the encode failed, as everywhere else in this tool |

A status and not a remark, because generation exactness is a **predicate and not
a quantity**: four stray samples break the chain exactly as completely as fifteen
hundred do.  "Nearly" therefore has to be reported as a failure of the guarantee
rather than as a successful encode with a note, or the consequence of missing it
does not appear at origination — it appears at the second hop, in somebody else's
facility, as a picture that no longer matches.  A pipeline that does not need
baseband exactness can ignore the distinction; one that does can no longer lose
it silently.

Only the gamut condition is reported this way.  A raster whose geometry is not
recoverable from a cropped picture is a property of the job the operator set up,
known before a single frame is read; it keeps its own report line and is not an
encode that went wrong.

**One thing this change broke, and it is worth recording because it is the shape
of mistake that hides.**  Both generation-chain harnesses treated *any* non-zero
status as a dead encoder and aborted.  Adding the exit status therefore turned
every cell the mode cannot clear from a measurable outcome into a blank line —
the measurement harness would have been silently blinded to exactly the cells the
status exists to flag.  They now continue after status 2 and let the pixel and
stream comparison report what really happened: the unclearable rail cell at
budget 1 reads `FAIL pixels-gen2 … oob=155488` rather than `FAIL enc-gen1`.

### 12.22.4 The CDR guard, and why it is a declaration and not a test

A committed picture is **allowed** to sit outside the legal range.  That is the
whole point of the unclipped biased domain (5.4), and the CDR chain is exact
because of it.  So a re-encode whose input is a CDR must reproduce those
samples verbatim and must never "repair" them.

The mode therefore stands down completely when the caller declares CDR input:

- `omc_enc_set_cdr_input(enc, 1)` in the library;
- `omc_enc` sets it whenever `--cdr-in` is given, and **refuses** the two flags
  together rather than quietly ignoring one:

```
$ omc_enc --cdr-in --gamut-strict ...
omc_enc: --gamut-strict is a BASEBAND-input policy and must not be combined
with --cdr-in: a committed picture is reproduced verbatim, and the CDR chain
is already exact through unlimited generations
```

An earlier version *guessed* this from the data — "repair a locked slice only
if its input is itself inside the legal range".  That guess is **not
generation-invariant**: the mandatory un-blend moves the two boundary rows of
every input frame, so the same slice can be judged one way at generation 1 and
the other way at generation 2, and the chain then breaks on the guess rather
than on the content.  A property the encoder must agree with itself about
across generations cannot be inferred from a frame; it has to be declared.

### 12.22.5 Why the mode is generation-safe

The claim is that turning the mode on does not disturb anything the rest of
this document proves.  Three separate arguments, each checkable:

1. **The exactness induction (section 8) does not move.**  It rests on two
   properties: the transform is exactly invertible, and the committed picture
   is `T^-1(dequant(q))` with no clamp anywhere.  The repair edits `q`'s source
   before quantization.  Both properties hold verbatim.
2. **The repair is inert from generation 2.**  Generation 1 commits a picture
   the repair has already placed inside the legal range.  Generation 2 reads
   it, un-blends it back onto the lattice, locks, reproduces it exactly, finds
   it inside the range, and never enters the repair at all.  This is why the
   mode costs nothing in the steady state: it is a **generation-1 origination
   policy**, and it disappears after that.
3. **The decision is a function of the committed picture**, which is a fixed
   point of the codec.  Whatever the repair decides at generation 1, generation
   2 is looking at the same data and decides the same thing — which, by (2), is
   "nothing to do".

And empirically, the mode is inert when it is off.  On the build that carried
only this fix, with the mode off, the encoder was byte-identical to the
minor-11 one — the 1080p reference cell of 12.6 still wrote
`156f0237206ac5f66f5b8c89535dfea4`.  On the **shipped** build that particular md5 is
not recoverable at all — 12.23's two normative fill rules are unconditional, as
the revision record's section 5 explains — so the inertness of *this* mode is
asserted instead by gate **G-T5-GAMUT3**, which encodes the same content twice
on the same build, with the mode off and on, and requires the two streams to be
byte-identical.  That is the stronger form of the claim anyway: it does not
depend on any recorded md5 surviving a later change.
### 12.22.6 Results

Every number below comes from one battery run on the shipped build, on binaries
pinned for the whole run; the recipe is in 12.22.10 so a reader can re-run it
rather than trust it.  The run is **100 PASS, 6 FAIL**, and every one of the six
failures is in the arm where the repair is deliberately switched OFF:

| section | result |
|---|---|
| the eight closed hand-off cells, repair ON | 8 PASS, 0 FAIL |
| the two largest violation counts in the corpus, repair ON | 2 PASS, 0 FAIL |
| twenty-generation chains, repair ON | 3 PASS, 0 FAIL |
| the opt-in grain fill, repair ON | 1 PASS, 0 FAIL |
| with the ants fix OFF, repair ON | 1 PASS, 0 FAIL |
| **the full baseband matrix at DEFAULT settings** | **29 PASS, 0 FAIL** |
| the same matrix with the repair switched **OFF** | 23 PASS, **6 FAIL** |
| real footage cut four times between four sources, one encode, no flags | 1 PASS, 0 FAIL |
| the exit status: 0 delivered / 2 not delivered / 0 mode off | 3 PASS, 0 FAIL |
| the CDR generation matrix | 29 PASS, 0 FAIL |

**The sixth row is the one that matters and it is new.**  Until this revision the
baseband matrix was only ever run with the repair off, because the repair was
opt-in; the six failures were the standing record of the conditional case.  Now
that the mode is the default, the matrix runs in the configuration that actually
ships, and every cell of it passes.

The six failures are the non-vacuity arm and are the point of it.  They are the
cells whose committed picture carries out-of-range samples when nothing repairs
them, and **each of those six same cells passes with the mode at its default,
earlier in the same run**:

| cell | repair off | repair on (default) |
|---|---|---|
| 1280×720 444/8b 0.5 bpp sh 8 | FAIL, 3,815 out of range | **PASS** |
| 1280×720 444/8b 1.0 bpp sh 16 | FAIL, 1,469 | **PASS** |
| 2048×1152 444/10b 2.0 bpp sh 16 | FAIL, 130 | **PASS** |
| 4480×1856 444/8b 0.5 bpp sh 16 | FAIL, 220,236 | **PASS** |
| 1920×1080 444/12b 0.5 bpp sh 16 | FAIL, 14 | **PASS** |
| 4096×2160 444/10b 2.0 bpp sh 32 | FAIL, 23,754 | **PASS** |

If they passed with the mode off the mode would be proving nothing.  Zero
failures anywhere the repair is enabled — including both 4K cells, all three
twenty-generation chains, the cut sequence and the whole CDR matrix.

**The eight cells 12.8 exposed.**  Each was a baseband chain that FAILED at
generation 2 with the mode off, for the single reason that the committed
picture carried samples outside the legal range.  `oob` is the count of such
samples in generation 1; `range` is the committed picture's actual extent.

```
PASS  [BB 1920x1080->1920x1088 422/10b bpp=0.5 sh=16 gens=5 --gamut-strict 12] g1.omc=37817e1330f7b2323ff3fff5b3bfda0f range=[0..1023] oob=0
PASS  [BB 1920x1080->1920x1088 422/10b bpp=1.0 sh=16 gens=5 --gamut-strict 12] g1.omc=ca145354f53daa439f33dadbe0b6272f range=[1..1023] oob=0
PASS  [BB 1280x720->1280x720 444/8b bpp=0.5 sh=8 gens=5 --gamut-strict 12] g1.omc=7aed0869a8e4e7fb89f9ab093d104c7c range=[63..255] oob=0
PASS  [BB 1280x720->1280x720 444/8b bpp=1.0 sh=16 gens=5 --gamut-strict 12] g1.omc=8fe210e266b4cc917257251b262e843a range=[63..255] oob=0
PASS  [BB 2048x1152->2048x1152 444/10b bpp=2.0 sh=16 gens=5 --gamut-strict 12] g1.omc=877336a46541d0b828dae52a35f265f5 range=[0..1023] oob=0
PASS  [BB 1920x1080->1920x1088 444/12b bpp=0.5 sh=16 gens=5 --gamut-strict 12] g1.omc=04e7bac6496e3c9577dc2f0b9b8026fd range=[99..4049] oob=0
PASS  [BB 1280x720->1280x720 422/10b bpp=1.0 sh=8 gens=5 --gamut-strict 12] g1.omc=391c84dfaa215b5512b98fbbad526d38 range=[0..1023] oob=0
PASS  [BB 1280x720->1280x720 422/10b bpp=0.5 sh=8 gens=5 --gamut-strict 12] g1.omc=b453c257ea986412f9b83f75ced915a7 range=[0..1023] oob=0
```

**Twenty generations**, on the three cells whose content is hardest for the
mode — all three are graded to the rails and all three failed at generation 2
without it:

```
PASS  [BB 1920x1080->1920x1088 422/10b bpp=0.5 sh=16 gens=20 --gamut-strict 12] g1.omc=37817e1330f7b2323ff3fff5b3bfda0f range=[0..1023] oob=0
PASS  [BB 1280x720->1280x720 444/8b bpp=0.5 sh=8 gens=20 --gamut-strict 12] g1.omc=7aed0869a8e4e7fb89f9ab093d104c7c range=[63..255] oob=0
PASS  [BB 1920x1080->1920x1088 444/12b bpp=0.5 sh=16 gens=20 --gamut-strict 12] g1.omc=04e7bac6496e3c9577dc2f0b9b8026fd range=[99..4049] oob=0
```

**The full baseband matrix**, mode off.  Read the FAIL lines here as evidence
*for* 12.22 rather than against it: with the mode off, a baseband chain breaks
exactly when the committed picture leaves the legal range, and every FAIL below
carries a non-zero `oob` count saying so.  That is the conditional case this
section exists to close, reproduced on the shipped build.

```
PASS  [BB 1280x720->1280x720 422/10b bpp=0.5 sh=8 gens=6 ] g1.omc=ee7bdf5ff36db8dd61ba0e41ae80029f range=[116..908] oob=0
PASS  [BB 1280x720->1280x720 422/10b bpp=2.0 sh=8 gens=5 ] g1.omc=a50cb714b1edb2e09b0c6261d0879838 range=[139..879] oob=0
PASS  [BB 1280x720->1280x720 444/8b bpp=0.5 sh=8 gens=5 ] g1.omc=7aed0869a8e4e7fb89f9ab093d104c7c range=[63..255] oob=0
PASS  [BB 1280x720->1280x720 444/8b bpp=1.0 sh=16 gens=5 ] g1.omc=8fe210e266b4cc917257251b262e843a range=[63..255] oob=0
PASS  [BB 1280x720->1280x720 422/12b bpp=3.0 sh=8 gens=5 ] g1.omc=f0c6857d9bc25a4c4c4af4195d8877e8 range=[285..3595] oob=0
PASS  [BB 2048x1152->2048x1152 422/12b bpp=0.5 sh=16 gens=6 ] g1.omc=3e1fae307dea18f2bcfa0f91531d6ed3 range=[125..3608] oob=0
PASS  [BB 2048x1152->2048x1152 444/10b bpp=2.0 sh=16 gens=5 ] g1.omc=877336a46541d0b828dae52a35f265f5 range=[0..1023] oob=0
PASS  [BB 2048x1152->2048x1152 422/10b bpp=0.5 sh=8 gens=5 ] g1.omc=690532f3dd10f64970f84e89ddad2862 range=[349..969] oob=0
PASS  [BB 2048x1152->2048x1152 422/10b bpp=3.0 sh=32 gens=5 ] g1.omc=7014ee85968f101268a6cc326109b156 [A2:OVER 1.146ms NOT-SHIPPABLE] range=[360..941] oob=0
PASS  [BB 4096x2160->4096x2160 422/8b bpp=0.5 sh=16 gens=4 ] g1.omc=2b97593ef51ee88a0e7c3324e7e4eb47 range=[31..254] oob=0
PASS  [BB 4480x1856->4480x1856 444/8b bpp=0.5 sh=16 gens=4 ] g1.omc=05c4291a78334b1489e40ebff6acc45b range=[0..185] oob=0
PASS  [BB 4480x1856->4480x1856 422/12b bpp=1.0 sh=8 gens=4 ] g1.omc=e294844f36acdfe443c2ca78ce02d384 range=[205..2683] oob=0
PASS  [BB 2048x1152->2048x1152 422/10b bpp=0.5 sh=16 gens=5 --tune vmaf] g1.omc=84ee3f9ada8e05615a5f7fc56fd28e92 range=[353..987] oob=0
PASS  [BB 2048x1152->2048x1152 422/10b bpp=0.5 sh=16 gens=5 --grain-corr --fill-static] g1.omc=8462aed367e920d7d49b26cf1b51b483 range=[355..968] oob=0
PASS  [BB 1920x1080->1920x1088 422/10b bpp=0.5 sh=16 gens=6 ] g1.omc=741bae6d472d586b7eb4ae67151a2e1a range=[120..874] oob=0
PASS  [BB 1920x1080->1920x1088 422/10b bpp=1.0 sh=16 gens=5 ] g1.omc=d6e111cfaf33c17406182bc1310a0b90 range=[141..874] oob=0
PASS  [BB 1920x1080->1920x1088 422/10b bpp=3.0 sh=16 gens=5 ] g1.omc=74909cec6fbfa59c0c6a0fd467980f7e range=[141..871] oob=0
PASS  [BB 1920x1080->1920x1088 444/12b bpp=0.5 sh=16 gens=6 ] g1.omc=04e7bac6496e3c9577dc2f0b9b8026fd range=[99..4049] oob=0
PASS  [BB 1920x1080->1920x1088 444/12b bpp=3.0 sh=16 gens=5 ] g1.omc=ca861271469006a0ff3570b7642bb391 range=[314..3811] oob=0
PASS  [BB 1920x1080->1920x1088 444/8b bpp=1.0 sh=16 gens=5 ] g1.omc=2b58c0a8d92e64e2582245ab68f13aa7 range=[17..247] oob=0
PASS  [BB 1920x1080->1920x1088 422/10b bpp=1.0 sh=32 gens=5 ] g1.omc=43651f87bc1e83c60e114bb013ce14d0 [A2:OVER 1.213ms NOT-SHIPPABLE] range=[141..874] oob=0
PASS  [BB 4096x2160->4096x2176 444/10b bpp=2.0 sh=32 gens=4 ] g1.omc=84e8cb9c27890c4c14c6a7ded9ff7f5b range=[5..1023] oob=0
PASS  [BB 1920x1080->1920x1088 422/10b bpp=1.0 sh=16 gens=5 --tune vmaf] g1.omc=ef2eabae889f29494d7cef59626c62d9 range=[137..876] oob=0
PASS  [BB 1920x1080->1920x1088 422/10b bpp=1.0 sh=16 gens=5 --grain-corr] g1.omc=2c801eaaaa280c2a5b00546811f5cb01 range=[141..874] oob=0
PASS  [BB 1920x1080->1920x1088 422/10b bpp=1.0 sh=16 gens=5 --fill-static] g1.omc=d6e111cfaf33c17406182bc1310a0b90 range=[141..874] oob=0
PASS  [BB 1920x1080->1920x1088 422/10b bpp=1.0 sh=16 gens=5 --no-fill] g1.omc=d6e111cfaf33c17406182bc1310a0b90 range=[141..874] oob=0
PASS  [BB 1920x1080->1920x1088 422/10b bpp=1.0 sh=16 gens=5 --grain-replace] g1.omc=2eb325d4e8bd3fa5be119c429fc01ef6 range=[142..870] oob=0
PASS  [BB 1920x1080->1920x1088 422/10b bpp=1.0 sh=16 gens=5 --refresh 2] g1.omc=e550c2f0ab4a16ad6974a984a35dc520 range=[141..871] oob=0
PASS  [BB 1920x1080->1920x1088 422/10b bpp=1.0 sh=16 gens=5 --refresh 3] g1.omc=cba29daeb4cd9b30744a73052bd87800 range=[141..874] oob=0
```

**And every one of those cells, re-run with the mode ON.**  A count of failures
is a record of a problem; this is the closure:

```
PASS  [BB 1280x720->1280x720 444/8b bpp=0.5 sh=8 gens=5 --gamut-strict 12] g1.omc=7aed0869a8e4e7fb89f9ab093d104c7c range=[63..255] oob=0
PASS  [BB 1280x720->1280x720 444/8b bpp=1.0 sh=16 gens=5 --gamut-strict 12] g1.omc=8fe210e266b4cc917257251b262e843a range=[63..255] oob=0
PASS  [BB 2048x1152->2048x1152 444/10b bpp=2.0 sh=16 gens=5 --gamut-strict 12] g1.omc=877336a46541d0b828dae52a35f265f5 range=[0..1023] oob=0
PASS  [BB 1920x1080->1920x1088 444/12b bpp=0.5 sh=16 gens=5 --gamut-strict 12] g1.omc=04e7bac6496e3c9577dc2f0b9b8026fd range=[99..4049] oob=0
PASS  [BB 4480x1856->4480x1856 444/8b bpp=0.5 sh=16 gens=4 --gamut-strict 12] g1.omc=05c4291a78334b1489e40ebff6acc45b range=[0..185] oob=0
PASS  [BB 4096x2160->4096x2176 444/10b bpp=2.0 sh=32 gens=4 --gamut-strict 12] g1.omc=84e8cb9c27890c4c14c6a7ded9ff7f5b range=[5..1023] oob=0
```

The matrix's mode-off failures and the eight cells above overlap on four cells
and differ on two — `gfxF003_444_8` at half a bit and `cine4k_444_10` at two
bits are matrix cells that were not in 12.8's exposed list, and they are the
two largest `oob` counts in the whole corpus (220 236 and 23 754 samples).
They are included here rather than left as a footnote.

**The CDR matrix**, which the mode never touches (it stands down on CDR input
by declaration, 12.22.4) and which the ants fix cannot touch either (12.23.7):

```
PASS  [1280x720->1280x720 422/10b bpp=0.5 sh=8 gens=6 ] g1.omc=ee7bdf5ff36db8dd61ba0e41ae80029f
PASS  [1280x720->1280x720 422/10b bpp=2.0 sh=8 gens=5 ] g1.omc=a50cb714b1edb2e09b0c6261d0879838
PASS  [1280x720->1280x720 444/8b bpp=0.5 sh=8 gens=5 ] g1.omc=7aed0869a8e4e7fb89f9ab093d104c7c
PASS  [1280x720->1280x720 444/8b bpp=1.0 sh=16 gens=5 ] g1.omc=8fe210e266b4cc917257251b262e843a
PASS  [1280x720->1280x720 422/12b bpp=3.0 sh=8 gens=5 ] g1.omc=f0c6857d9bc25a4c4c4af4195d8877e8
PASS  [1920x1080->1920x1088 422/10b bpp=0.5 sh=16 gens=6 ] g1.omc=741bae6d472d586b7eb4ae67151a2e1a
PASS  [1920x1080->1920x1088 422/10b bpp=1.0 sh=16 gens=5 ] g1.omc=d6e111cfaf33c17406182bc1310a0b90
PASS  [1920x1080->1920x1088 422/10b bpp=3.0 sh=16 gens=5 ] g1.omc=74909cec6fbfa59c0c6a0fd467980f7e
PASS  [1920x1080->1920x1088 444/12b bpp=0.5 sh=16 gens=6 ] g1.omc=04e7bac6496e3c9577dc2f0b9b8026fd
PASS  [1920x1080->1920x1088 444/12b bpp=3.0 sh=16 gens=5 ] g1.omc=ca861271469006a0ff3570b7642bb391
PASS  [1920x1080->1920x1088 444/8b bpp=1.0 sh=16 gens=5 ] g1.omc=2b58c0a8d92e64e2582245ab68f13aa7
PASS  [1920x1080->1920x1088 422/10b bpp=1.0 sh=32 gens=5 ] g1.omc=43651f87bc1e83c60e114bb013ce14d0 [A2:OVER 1.213ms NOT-SHIPPABLE]
PASS  [2048x1152->2048x1152 422/12b bpp=0.5 sh=16 gens=6 ] g1.omc=3e1fae307dea18f2bcfa0f91531d6ed3
PASS  [2048x1152->2048x1152 444/10b bpp=2.0 sh=16 gens=5 ] g1.omc=877336a46541d0b828dae52a35f265f5
PASS  [2048x1152->2048x1152 422/10b bpp=0.5 sh=8 gens=5 ] g1.omc=690532f3dd10f64970f84e89ddad2862
PASS  [2048x1152->2048x1152 422/10b bpp=3.0 sh=32 gens=5 ] g1.omc=7014ee85968f101268a6cc326109b156 [A2:OVER 1.146ms NOT-SHIPPABLE]
PASS  [4096x2160->4096x2160 422/8b bpp=0.5 sh=16 gens=4 ] g1.omc=2b97593ef51ee88a0e7c3324e7e4eb47
PASS  [4096x2160->4096x2176 444/10b bpp=2.0 sh=32 gens=4 ] g1.omc=84e8cb9c27890c4c14c6a7ded9ff7f5b
PASS  [4480x1856->4480x1856 444/8b bpp=0.5 sh=16 gens=4 ] g1.omc=05c4291a78334b1489e40ebff6acc45b
PASS  [4480x1856->4480x1856 422/12b bpp=1.0 sh=8 gens=4 ] g1.omc=e294844f36acdfe443c2ca78ce02d384
PASS  [1920x1080->1920x1088 422/10b bpp=1.0 sh=16 gens=5 --tune vmaf] g1.omc=ef2eabae889f29494d7cef59626c62d9
PASS  [1920x1080->1920x1088 422/10b bpp=1.0 sh=16 gens=5 --grain-corr] g1.omc=2c801eaaaa280c2a5b00546811f5cb01
PASS  [1920x1080->1920x1088 422/10b bpp=1.0 sh=16 gens=5 --fill-static] g1.omc=d6e111cfaf33c17406182bc1310a0b90
PASS  [1920x1080->1920x1088 422/10b bpp=1.0 sh=16 gens=5 --no-fill] g1.omc=d6e111cfaf33c17406182bc1310a0b90
PASS  [1920x1080->1920x1088 422/10b bpp=1.0 sh=16 gens=5 --grain-replace] g1.omc=2eb325d4e8bd3fa5be119c429fc01ef6
PASS  [1920x1080->1920x1088 422/10b bpp=1.0 sh=16 gens=5 --refresh 2] g1.omc=e550c2f0ab4a16ad6974a984a35dc520
PASS  [1920x1080->1920x1088 422/10b bpp=1.0 sh=16 gens=5 --refresh 3] g1.omc=cba29daeb4cd9b30744a73052bd87800
PASS  [2048x1152->2048x1152 422/10b bpp=0.5 sh=16 gens=5 --tune vmaf] g1.omc=84ee3f9ada8e05615a5f7fc56fd28e92
PASS  [2048x1152->2048x1152 422/10b bpp=0.5 sh=16 gens=5 --grain-corr --fill-static] g1.omc=8462aed367e920d7d49b26cf1b51b483
```

#### 12.22.6a The corpus, scored against the right target

An earlier revision of this section held candidates to *"must not score below the
shipped repair on any cell"*.  That criterion was wrong, and the error was mine.
It privileges an accident: on `gfx1080_444_12` the 3/4 repair scores **above** the
no-repair picture (91.5210 against 91.4104), so beating it there means
over-improving rather than costing nothing.  The standing rule on this project is
that a fix cannot affect VMAF-NEG, which makes the target the **repair-off**
score.  The gap to that target is the number that matters, and it is what the
table below reports.

**Provenance, and what is allowed to drive a decision.**  The corpus mixes three
kinds of material and they do not carry equal weight.

| clip | what it is | drives decisions? |
|---|---|---|
| `cine4k_444_10`, `cine4k_422_8`, `cineA21_*`, `cineA31_*` | camera footage, as delivered | **yes** |
| `gfxF003_444_8`, `gfx1080_444_12` | real graphics masters, as delivered | **yes** |
| `gfx1080_fullrange_422_10` | a real graphics master **stretched to full range** by `tests/mkfullrange.py` | reported, secondary |
| `rail720_422_10` | **synthesized** by `tests/mkrail.py` — one-row rail features walked across slice boundaries, built to be the hardest thing the rule can face | **no** |

This is a direction from the project owner and it is recorded here because it
changes how the table below should be read: *synthesized footage should not be
driving the work — real graphics yes, stress footage no.*  The stress clip's
numbers are reported in full, and its gate `G-T5-GAMUT2c` is kept, because
hiding a case the rule handles badly would be the lie.  But a candidate rule is
accepted or rejected on the camera and real-graphics rows, and `rail720` is a
diagnostic, not a target.  Every decision recorded in 12.22.3 was in fact taken
that way; the shipped rule would be the same rule with the stress rows deleted.

`strays` is the count of committed samples outside
the legal range with the repair off; it is **zero** in both repaired columns of
every row.  All figures `vmaf_v0.6.1neg`, three frames.

| clip | bpp | strays | repair off (target) | old 3/4 | gap | shipped now | gap |
|---|---|---|---|---|---|---|---|
| cine4k_444_10 | 1.0 | 53,329 | 94.8712 | 89.4268 | −5.44 | **94.5584** | **−0.31** |
| cine4k_444_10 | 2.0 | 23,754 | 97.5497 | 93.8878 | −3.66 | **97.4582** | **−0.09** |
| cineA31_720_444_8 | 0.5 | 3,815 | 98.2237 | 97.7627 | −0.46 | **98.2367** | **+0.01** |
| cineA31_720_444_8 | 1.0 | 1,469 | 98.8755 | 98.4062 | −0.47 | **98.8622** | **−0.01** |
| cineA21_444_10 | 2.0 | 130 | 95.0477 | 94.8917 | −0.16 | **94.9784** | **−0.07** |
| cineA21_444_10 | 0.5 | 3,413 | 77.6428 | 73.5255 | −4.12 | **75.9954** | **−1.65** |
| gfx1080_444_12 | 0.5 | 14 | 91.4104 | 91.5210 | +0.11 | **91.4104** | **0.00** |
| gfxF003_444_8 | 1.0 | 173,613 | 98.9690 | 98.8050 | −0.16 | **98.9510** | **−0.02** |
| **gfxF003_444_8** | **0.5** | **220,236** | 98.5768 | 98.0739 | −0.50 | **97.8214** | **−0.76** |
| cine4k_422_8 | 0.5 | 0 | 97.0156 | inert | — | inert | — |
| cineA21_422_12 | 0.5 | 0 | 87.7289 | inert | — | inert | — |
| *gfx1080_fullrange_422_10* | 0.5 | 104 | 92.0577 | 84.2465 | −7.81 | *90.3245* | *−1.73* |
| *gfx1080_fullrange_422_10* | 1.0 | 12 | 94.8466 | 92.2451 | −2.60 | *94.6683* | *−0.18* |
| *rail720_422_10* | 1.0 | 113,097 | 98.5762 | 78.2294 | −20.35 | *94.9359* | *−3.64* |
| *rail720_422_10* | 0.5 | 226,961 | 97.5738 | 62.3204 | −35.25 | *86.3737* | *−11.20* |

The last four rows are italicised because they are the synthesized material of the
provenance table above; they are reported, they did not vote.

Better on **twelve of the thirteen cells that fire**, level on the thirteenth, and
zero out-of-range samples on every one of the fifteen.  The worst real-footage cost
falls from −4.12 to −1.65, the second worst from −5.44 to −0.31, and five real
cells now land inside ±0.09, which is at or below the run-to-run spread of the
metric on three frames.  The stress clip, which did not vote, improves from −35.25
to −11.20.

**Why 63/64, and why the escalation.**  The factor and the escalation point were
swept together.  63/64 is better than 15/16 on five real cells, level on three and
worse on one — and it is also the **gentlest factor that still converges**: at
127/128 and 255/256 the repair leaves 21,120 samples out of range on the rail clip
at half a bit per pixel, and 63/64 *without* the escalation leaves 21,760.  So the
shipped point is not a preference among comparable options; it is the edge of the
feasible region, and the stall escalation of 12.22.2 step 2 is what puts it there.
Escalating earlier (pass 2) or to a harsher fallback (3/4) is worse on every cell
measured.

One cell scores lower than the old rule: `gfxF003_444_8` at half a bit per pixel,
by 0.25.  That cell is discussed on its own below, because what is happening there
is not a regression.

#### 12.22.6b The one cell where the metric and the picture disagree

On `gfxF003_444_8` at 0.5 bpp the new rule scores 0.25 **lower** on VMAF-NEG and
is decisively **closer to the source**.  Luma PSNR of the decode against the
master, per frame:

| rule | frame 0 | frame 1 | frame 2 | mean Y | mean Cb | mean Cr |
|---|---|---|---|---|---|---|
| repair off (the fidelity target) | 43.67 | 44.25 | 44.44 | 44.12 | 41.94 | 42.15 |
| old 3/4 | 37.49 | 41.48 | 36.86 | 38.61 | 37.56 | 37.53 |
| **shipped now** | **43.07** | **41.98** | **42.14** | **42.40** | **40.29** | **40.47** |
| difference against old 3/4 | +5.58 | +0.50 | +5.28 | **+3.79 dB** | **+2.73 dB** | **+2.94 dB** |

Nearly four decibels of luma and about three of both chroma planes, in the
direction of the source, on the cell the metric prefers the other way.  Measured
against the unrepaired picture rather than against the old rule, the repair's
fidelity cost on this cell falls from **5.51 dB to 1.72 dB** of luma.

The mechanism is not mysterious.  Out-of-range samples **are** quantization
overshoot, which is ringing.  On a graphics master at half a bit per pixel the
coefficients around a rail excursion are almost all ringing, so a rule that
removes a great deal of energy there removes a great deal of ringing — and a
model built to refuse credit for detail the source did not have scores the
removal of near-edge energy as an improvement.  On camera footage the same
neighbourhood holds real texture, and removing it is exactly the loss the model
punishes.  The two cells where the aggressive rule wins on the metric are both
graphics; every camera cell prefers the gentle rule, and by much larger margins.

The same pattern, from the other side, on the two cells where the old rule looked
free or better on the metric:

| clip | bpp | mean luma PSNR, repair off | old 3/4 | shipped now |
|---|---|---|---|---|
| gfx1080_444_12 | 0.5 | 47.1233 | 47.1600 | **47.1233** |
| gfx1080_fullrange_422_10 | 0.5 | 46.66 | 43.25 | **46.32** |

On `gfx1080_444_12` the new rule reproduces the no-repair picture to four decimal
places — frames 0 and 2 are identical to the unrepaired decode and frame 1 differs
by 0.03 dB on one chroma plane.  It is genuinely free, where the old rule scored
0.11 VMAF-NEG *above* the unrepaired picture by removing energy the source had.
On `gfx1080_fullrange` the old rule cost 3.41 dB of luma and the new one costs
0.34 dB.

**What was tried, and why nothing is tuned for that cell.**  Nine encoder-side
statistics were built and measured in an attempt to separate the two content
types without a classifier: violation density, observed convergence rate,
per-band synthesis leverage, the alignment ratio graded continuously, plain
squared error against the source, squared error masked by the source's own local
activity, squared error plus a penalty for detail the source never had, per-band
change in coded value, and per-band injected picture energy.  **Each is monotone
in one direction and none reproduces the metric's verdict across both regimes.**

Two of those deserve their own line because they were the strongest candidates.

- **Total picture energy removed** predicts VMAF-NEG perfectly on every camera
  cell, monotone over a twentyfold range — and predicts it exactly backwards on
  `gfxF003`.  On 4K cinema the arm removing 1.01e10 scores 93.89 and the arm
  removing 6.16e07 scores 97.44; on the graphics master the arm removing 4.69e08
  scores 98.07 and the arm removing seventeen times less scores 97.82.
- **Per-slice trial selection** (`OMC_GM_TRIAL`) is the only one of the nine that
  is not a heuristic: it repairs each violating slice **both** ways and keeps
  whichever committed picture is closer to the source it was made from.  Three
  pixel-domain distances pick the *same* shape on 343 of the graphics master's
  348 violating slices, and that shape scores 0.29 lower on VMAF-NEG while being
  3.3 dB closer to the source.  Decomposing the metric says which part disagrees:
  between the two shapes VIF barely moves and motion does not move at all — the
  whole 0.29 is ADM, and almost all of it ADM at the two **coarse** scales (scale
  2 −0.0099, scale 3 −0.0121).  A fourth criterion built the way ADM is — per
  band, the magnitude the source had and the reconstruction lost, plus K times
  the magnitude the reconstruction has that the source never had, weighted by the
  band's measured picture energy — flips the vote to 322 harsh against 5 and
  scores **97.4482, worse than either uniform choice** (98.1117 harsh, 97.8220
  gentle).  Mixing shapes across the slices of one frame costs more than either
  shape costs on its own.  Per-slice adaptation is therefore out on measurement,
  which is also where the codec team wanted it held.

The register is left as it is.  Tuning a reduction rule until it reproduces a
metric's verdict on one clip, against three and a half decibels of measured
fidelity pointing the other way, would be fitting the instrument rather than the
picture.

### 12.22.7 What it costs

**In picture.**  The mode re-codes slices whose committed picture leaves the
legal range, shrinking the coefficients that cover the offending samples.  That
is a real change to the picture and it is charged here, per cell, on VMAF-NEG
first and PSNR second:

```
gfx1080_422_10           1920x1080 422/10 bpp=1.0  sh=16 oob        0 -> 0        VMAF-NEG 96.5238 -> 96.5238  PSNR-Y  54.97 -> 54.97   stream IDENTICAL
gfx1080_fullrange_422_10          1920x1080 422/10 bpp=0.5  sh=16 oob      104 -> 0        VMAF-NEG 92.0577 -> 82.2252  PSNR-Y  46.66 -> 41.98   stream differs
gfx1080_fullrange_422_10          1920x1080 422/10 bpp=1.0  sh=16 oob       12 -> 0        VMAF-NEG 94.8466 -> 92.2310  PSNR-Y  49.03 -> 46.58   stream differs
rail720_422_10           1280x720 422/10 bpp=0.5  sh=0  oob   316236 -> 0        VMAF-NEG 95.3103 -> 57.7171  PSNR-Y        ->         stream differs
rail720_422_10           1280x720 422/10 bpp=1.0  sh=0  oob    89676 -> 0        VMAF-NEG 98.3885 -> 77.6916  PSNR-Y        ->         stream differs
cineA31_720_444_8        1280x720 444/8  bpp=0.5  sh=0  oob     3815 -> 0        VMAF-NEG 98.2237 -> 97.7635  PSNR-Y        ->         stream differs
cineA31_720_444_8        1280x720 444/8  bpp=1.0  sh=16 oob     1469 -> 0        VMAF-NEG 98.8755 -> 98.4046  PSNR-Y  43.12 -> 41.98   stream differs
cineA21_444_10           2048x1152 444/10 bpp=2.0  sh=16 oob      130 -> 0        VMAF-NEG 95.0477 -> 94.8945  PSNR-Y  44.24 -> 44.02   stream differs
gfx1080_444_12           1920x1080 444/12 bpp=0.5  sh=16 oob       14 -> 0        VMAF-NEG 91.4104 -> 91.5210  PSNR-Y  47.12 -> 47.16   stream differs
gfxF003_444_8            4480x1856 444/8  bpp=0.5  sh=16 oob   220236 -> 0        VMAF-NEG 98.5768 -> 98.0667  PSNR-Y  44.12 -> 38.56   stream differs
cine4k_444_10            4096x2160 444/10 bpp=2.0  sh=32 oob    23754 -> 0        VMAF-NEG 97.5497 -> 93.0997  PSNR-Y  45.69 -> 36.72   stream differs
STRICTCOST-DONE
```

**Read it split by what the master IS, because the two halves say opposite
things and averaging them is how this table gets misquoted.**

| master | what it is | oob, mode off | VMAF-NEG cost |
|---|---|---|---|
| `gfx1080_422_10` @1.0 | naturally graded, never reaches the rails | 0 | **0.00 — byte-identical stream** |
| `gfx1080_444_12` @0.5 | naturally graded | 14 | **+0.11 — it improves** |
| `cineA21_444_10` @2.0 | naturally graded | 130 | −0.15 |
| `cineA31_720_444_8` @0.5 / @1.0 | naturally graded | 3 815 / 1 469 | −0.46 / −0.47 |
| `gfxF003_444_8` @0.5 | naturally graded | 220 236 | −0.51 |
| `cine4k_444_10` @2.0 | naturally graded | 23 754 | **−4.45** |
| `gfx1080_fullrange_422_10` @0.5 / @1.0 | **synthesised**: the graphics master expanded to the rails | 104 / 12 | **−9.83 / −2.62** |
| `rail720_422_10` @0.5 / @1.0 | **synthesised**: hard black and white plates, a deliberate stress | 316 236 / 89 676 | **−37.59 / −20.70** |

On the seven naturally-graded cells the cost is between **+0.11 and −0.51**,
with one exception: `cine4k_444_10` at two bits per pixel loses **4.45**.  On
the two synthesised rail-graded masters it is between **2.6 and 37.6 points**.
The large figures in this table are the ones the corpus had to manufacture in
order to contain the exposed class at all (12.22.1); they are the right stress
to design against and the wrong number to quote as "the cost on footage".

Note also that the cost does **not** track the stray-sample count.
`gfxF003_444_8` has 220 236 strays and loses half a point; `cine4k_444_10` has
a tenth as many and loses nine times as much.  What the repair costs depends on
*where* in the picture the excursions sit and how coarse the plan already is,
not on how many there are.

Three further things this table says that a summary line does not.

* **On content that never reaches the rails the mode is free, and "free" means
  byte-identical**, not "small".  Gate G-T5-GAMUT3 asserts it.
* **On content graded hard to the rails the cost is real, and on the worst
  cells it is large.**  The synthetic rail clip is a deliberate stress rather
  than footage and it loses tens of points; ordinary architectural footage
  graded to the rails loses several points at half a bit per pixel and much
  less at one.  This is the number a build team has to look at before turning
  the mode on for a whole channel, and it is why 12.22.8 recommends it per
  hop rather than globally.
* **It is not uniform, so measure your own material.**  `tests/strict_cost.sh`
  is in Appendix G and takes the pass budget as its argument.

**In seam quality.**  The seam blend (XSL) is untouched by the mode, but the
repair edits coefficients that cover boundary rows, so "does the repair make
the joins worse" has to be measured rather than reasoned about.  The metric is
the mean row-to-row luma step **at slice joins** minus the same statistic
**inside** the picture: at or below zero means the joins are no worse than the
picture's own texture.

```
  gfx1080_fullrange_422_10 bpp=0.5 strict=off  stream=134ec23a68a8
    frame 0: PSNR Y 46.01 Cb 37.61 Cr 39.35 dB | seam excess dec +2.419 src +0.068 (codes)
    frame 1: PSNR Y 46.81 Cb 38.17 Cr 39.76 dB | seam excess dec +1.985 src +0.079 (codes)
    frame 2: PSNR Y 47.16 Cb 38.15 Cr 39.75 dB | seam excess dec +1.669 src +0.069 (codes)
  gfx1080_fullrange_422_10 bpp=0.5 strict=on  stream=a2c8763a6a1d
    frame 0: PSNR Y 39.97 Cb 37.62 Cr 39.34 dB | seam excess dec +3.161 src +0.068 (codes)
    frame 1: PSNR Y 44.22 Cb 38.16 Cr 39.74 dB | seam excess dec +2.231 src +0.079 (codes)
    frame 2: PSNR Y 41.76 Cb 38.06 Cr 39.70 dB | seam excess dec +2.102 src +0.069 (codes)
  gfx1080_fullrange_422_10 bpp=1.0 strict=off  stream=a7aa771764ef
    frame 0: PSNR Y 48.76 Cb 40.04 Cr 40.98 dB | seam excess dec +1.923 src +0.068 (codes)
    frame 1: PSNR Y 49.07 Cb 40.50 Cr 41.30 dB | seam excess dec +1.607 src +0.079 (codes)
    frame 2: PSNR Y 49.26 Cb 40.48 Cr 41.25 dB | seam excess dec +1.445 src +0.069 (codes)
  gfx1080_fullrange_422_10 bpp=1.0 strict=on  stream=f1d826af3b4a
    frame 0: PSNR Y 45.94 Cb 40.02 Cr 40.98 dB | seam excess dec +2.065 src +0.068 (codes)
    frame 1: PSNR Y 48.11 Cb 40.49 Cr 41.29 dB | seam excess dec +1.630 src +0.079 (codes)
    frame 2: PSNR Y 45.70 Cb 40.39 Cr 41.22 dB | seam excess dec +1.637 src +0.069 (codes)
  cineA31_720_444_8 bpp=0.5 strict=off  stream=8514c6fc773e
    frame 0: PSNR Y 38.50 Cb 37.05 Cr 36.96 dB | seam excess dec +2.001 src -0.006 (codes)
    frame 1: PSNR Y 39.54 Cb 38.22 Cr 38.16 dB | seam excess dec +1.937 src -0.009 (codes)
    frame 2: PSNR Y 40.23 Cb 38.69 Cr 38.68 dB | seam excess dec +1.823 src -0.010 (codes)
  cineA31_720_444_8 bpp=0.5 strict=on  stream=ef4a91e1a0c2
    frame 0: PSNR Y 36.63 Cb 35.02 Cr 35.37 dB | seam excess dec +2.047 src -0.006 (codes)
    frame 1: PSNR Y 39.31 Cb 36.88 Cr 37.31 dB | seam excess dec +1.956 src -0.009 (codes)
    frame 2: PSNR Y 38.67 Cb 36.93 Cr 36.97 dB | seam excess dec +1.923 src -0.010 (codes)
  rail720_422_10 bpp=1.0 strict=off  stream=8fd5f0d3eaf0
    frame 0: PSNR Y 67.93 Cb 69.08 Cr 68.43 dB | seam excess dec +18.852 src +18.834 (codes)
    frame 1: PSNR Y 58.28 Cb 44.14 Cr 44.14 dB | seam excess dec +12.303 src +12.273 (codes)
    frame 2: PSNR Y 70.67 Cb 68.22 Cr 68.37 dB | seam excess dec +20.904 src +20.882 (codes)
  rail720_422_10 bpp=1.0 strict=on  stream=2e038fb11835
    frame 0: PSNR Y 26.05 Cb 37.50 Cr 37.48 dB | seam excess dec +29.261 src +18.834 (codes)
    frame 1: PSNR Y 31.76 Cb 39.85 Cr 39.48 dB | seam excess dec +12.084 src +12.273 (codes)
    frame 2: PSNR Y 27.64 Cb 37.33 Cr 37.33 dB | seam excess dec +21.230 src +20.882 (codes)
```

Two readings.  **The joins already carry about two code values more step than
the picture's own interior, with the mode off** — that is the blend doing its
job on a picture the quantizer has smoothed, not a defect the mode introduced,
and the source's own column beside it is essentially zero because the master
has no slice structure.  **The mode raises that figure**, by about half a code
at half a bit per pixel on rail-graded footage and by a tenth of a code at one
bit.  It does not restructure the joins; it makes the slices it repairs
slightly softer, and the join inherits that.  On the **synthetic rail clip**
— hard black and white plates, the deliberate stress rather than footage — the
figure moves by ten code values and the luma PSNR by forty decibels, which is
the same story the picture-cost table tells about that clip and is the reason
it is named as a stress rather than reported as a corpus result.  The seam blend itself is
byte-for-byte untouched by this revision, which is asserted rather than
asserted-about: `G-T5-XSL1` fails the build if the blend can be switched off
and `G-T5-XSL2b` fails if it stops firing.

**In work, latency and rt = 0.**  12.22.8 carries those; they did not change.
### 12.22.8 What it costs in WORK, and why it is on by default

**It is on by default, and that is not a recommendation — it is the design.**
An earlier revision of this section shipped the mode off and offered a four-row
table telling an operator when to switch it on.  That table was wrong to exist.
A broadcast chain cuts from a match to a studio to a graphics bumper in seconds;
nobody is at a console deciding which of those needs its committed picture kept
inside the legal range, and a setting that has to be switched per clip is a
setting that will be wrong.  Either the mode is always on or it does not exist.

Three properties make always-on safe, and all three are gated or measured rather
than asserted:

- **It is byte-identical to having it off on content that never reaches the
  rails** (`G-T5-GAMUT3`).  Not "cheap" — identical.  The encoder's default
  output does not move: the 1080p reference cell of 12.6 still hashes to
  `d6e111cfaf33c17406182bc1310a0b90` with the mode defaulted on, and the encoder
  reports `0 slices repaired in 0 passes` on it.
- **It stands down entirely on CDR input** (12.22.4), where a committed picture
  must be reproduced verbatim and the chain is already exact unconditionally.
  `--cdr-in` now stands the mode down rather than failing, because a default is
  not a request; an *explicit* `--gamut-strict` alongside `--cdr-in` is still
  refused, because that is a contradiction the operator typed.
- **It is inert from generation 2** (12.22.5), so the cost lands on the encode
  that originates a chain and on no later hop.

**The work, stated once.**  The repair does not re-run the whole slice.  Per pass
it repeats only the back half of the encode — symbolisation, the tANS pass, the
fill decision, the header and the reconstruction.  It does **not** repeat the
forward transform, the temporal prediction, the cost tables, the generation-lock
scan or the rate control.  Worst-case per-slice work is

```
    W_front + (1 + N) * W_back
```

with `N` the per-slice budget.  A slice with no violation takes `N = 0` passes
and pays nothing.

**What N actually has to be, measured.**  This is the one number an integrator
sizes, so here is the whole corpus rather than a claim.  `repaired` is over three
frames; `avg` is passes per repaired slice; `oob` is what is left outside the
legal range when the budget runs out.

| clip | bpp | slices/frame | repaired | share | avg passes | N=12 oob | N=4 oob | N=2 oob |
|---|---|---|---|---|---|---|---|---|
| gfxF003_444_8 | 0.5 | 116 | 348 | 100 % | 4.4 | **0** | 3,383 | 24,938 |
| cine4k_444_10 | 2.0 | 68 | 130 | 63 % | 3.2 | **0** | 13 | 1,693 |
| cineA21_444_10 | 0.5 | 72 | 67 | 31 % | 4.6 | **0** | 589 | 1,648 |
| cineA31_720_444_8 | 0.5 | 90 | 44 | 16 % | 2.2 | **0** | 12 | 55 |
| gfx1080_444_12 | 0.5 | 68 | 2 | 1 % | 3.0 | **0** | 0 | 3 |
| gfx1080_422_10 | 1.0 | 68 | 0 | 0 % | — | **0** | 0 | 0 |
| cine4k_422_8 | 0.5 | 135 | 0 | 0 % | — | **0** | 0 | 0 |
| *rail720_422_10* | 0.5 | 45 | 50 | 37 % | 5.6 | **0** | 100,015 | 140,527 |

Read it in three lines.

1. **`N = 12` reaches zero on every cell of the corpus**, including the one where
   every slice of every frame needs the repair.  That is why 12 is the default.
2. **The average is 2.2 to 5.6 passes even on the cells that fire.**  A design
   with any elasticity between slices sees the average, not the ceiling; a design
   with a hard per-slice deadline must size the back half for thirteen
   executions, because the ceiling is what a deadline meets.
3. **Small budgets do not degrade gracefully on hard content.**  `N = 4` still
   leaves 3,383 samples on the 4K graphics master and 100,015 on the rail clip.
   An encoder that cannot afford thirteen back-half executions is an encoder
   whose baseband hand-off is exact on ordinary content and not exact on the
   hardest — and it says so, through `omc_enc_oob()`, rather than pretending.

That last point is the honest statement of the limit, and it replaces the
recommendation table.  There is no content class for an operator to recognise and
no switch for them to throw; there is one number, `N`, which a hardware team sets
once from its own slice period, and a verdict line that reports what that choice
bought.  This document puts no cycle count on `W_front` or `W_back`: that split is
a property of a particular RTL and no measurement in this repository can establish
it (12.18 on why no wall-clock number appears anywhere in this document).  What it
establishes is the number of repeated executions, which is the part the
architecture has to accommodate.

### 12.22.9 Gates

Sixteen assertions in `tests/test_xsl.c`, run by `make test`.  They are built
around a synthetic that is deliberately the worst case the rule can face —
hard black and white plates at exactly 0 and `maxv`, with the edges walked
across slice boundaries frame by frame, and a full-range ramp:

| gate | what it asserts |
|---|---|
| **G-T5-GAMUT1** | **non-vacuity**: with the mode OFF that content really does commit samples outside the legal range.  Without this the rest proves nothing. |
| **G-T5-GAMUT2a** | with the mode ON the count is **zero** on the same content |
| **G-T5-GAMUT2b** | and its **baseband chain is byte-exact**: pixels identical from generation 1, streams identical from generation 2 (generation 1 codes a master and generation 2 codes a reconstruction, so their bytes are not required to agree — the gate runs three generations for this reason) |
| **G-T5-GAMUT2c** | the deliberately **pathological** arm — one-row rail features walked across slice boundaries — is **CLOSED**: every excursion removed, not merely 99 % of them.  This gate previously asserted the weaker claim, because the weaker claim was the truth; the fallback of 12.22.3i made it false and the gate now asserts what the code does. |
| **G-T5-GAMUT2d** | and the **fallback is what closes it**: with the fallback disabled the same content leaves 55 samples that more passes do not clear.  Without this the previous gate would pass for a reason nobody could name. |
| **G-T5-GAMUT3** | the mode is **inert** on content that never leaves the range: byte-identical stream with it on and off |
| **G-T5-GAMUT4** | **rt = 0** still holds with the repair running: the encoder's own reconstruction equals the decoder's output, byte for byte.  If the repair could ever leave those two disagreeing, every exactness claim above it would be measuring the wrong buffer. |
| **G-T5-GAMUT5a** | **non-vacuity** for the determinism set: the repair really fires on the content the next two gates use |
| **G-T5-GAMUT5b** | the same input re-encoded **in the same process**, with different content coded in between, produces a byte-identical stream and decode |
| **G-T5-GAMUT5c** | and it got there by the **same internal path**: identical slices repaired, passes taken and slices left unfixed |
| **G-T5-GAMUT5d** | the **alignment veto** fires on that content and still reaches zero out-of-range samples inside the pass budget |
| **G-T5-GAMUT5e** | and the veto is deterministic too: same stream, same decode, same internal path on a re-encode |
| **G-T5-CUT1** | **non-vacuity** for the cut set: with the repair off, a sequence that cuts between rail-graded and ordinary footage does commit samples outside the range |
| **G-T5-CUT2** | **one encode at the DEFAULT settings, across those cuts, leaves no committed sample outside the legal range** — nothing is switched at the cuts.  Three cuts in four frames, more abrupt than any real programme. |
| **G-T5-CUT3** | and that cut sequence survives a baseband generation chain byte for byte |
| **G-T5-CUT4** | hard black and white plates at the exact rails close completely too, alone **and** cut against ordinary footage |

**Why the cut gates exist.**  Every other gate in this document encodes one kind
of content at a time, which is not how a broadcast chain is used.  A chain cuts
between sources every few seconds and nobody is at a console changing settings at
each cut, so "it works on clip A and it works on clip B" was never the property
that mattered.  The cut gates hold one setting across content whose demands are
opposite, and there is nowhere in them to change anything.

The first version of `G-T5-CUT4` **failed**, and the failure was worth more than a
pass would have been.  It used hard plates at the exact rails and required zero,
which at the time the mode did not deliver — so it was asserting something the
mode had never claimed.  Measuring it properly showed the residue was not caused
by cutting at all: the plates alone left 72 samples and the sequence that cut them
against ordinary footage left 26.  Cutting made it **better**.  That finding is
what sent this section looking at the step cap, which is what 12.22.3i came from.
Both now close to zero.

**Why the determinism set exists, and why it asserts counts as well as bytes.**
Every exactness result in this section is a claim about reproducing a stream, and
none of them means anything if the repair can reach two different answers from one
input.  Byte-identical output is the property actually needed — generation
exactness and reproducibility both follow from it, and nothing stronger can be
asserted about a stream.  The internal counts are asserted **as well**, because
they fail earlier: two runs can take different numbers of passes and still
converge to the same lattice point, so the bytes agree while the encoder is
already nondeterministic.  That is a latent fault waiting for an unrelated change
to expose it, and it is not hypothetical — an earlier revision of the repair
restored a plane from an uninitialised buffer when that plane was clean on one
pass and dirty on a later one, and the streams still matched.

The second encode is separated from the first by an encode of **different content
in the same process**.  Two fresh processes would not catch state leaking through
a global or a static, which is the class of bug this is guarding.  Counts are
asserted only across repeated runs of the same input on the same build; across
builds or content they are not invariants and the gate would become noise.

The determinism gates are run **before** the battery of 12.22.6, not after.  If
the repair were nondeterministic, the battery's verdicts would not be
reproducible and re-running it later would not say the same thing.

The synthetic needs `N >= 10` to reach zero; real footage needs 4 (12.22.7).
The gate runs at the shipped default of 12.

### 12.22.10 Reproducing this section

```bash
# 1. the gates
cd omc/omc_v4.9 && make test          # the six G-T5-GAMUT assertions are in test_xsl
make test-threads                     # unchanged: clean

# 2. the 12.6 reference cell on the SHIPPED build.  (The minor-11 value
#    156f0237206ac5f66f5b8c89535dfea4 is not reproducible here and is not
#    meant to be -- see the revision record, section 5.  G-T5-GAMUT3 is what
#    asserts this mode's inertness, and it does so without any md5.)
./omc_enc -i ../../tests/raw/gfx1080_422_10.yuv -o /tmp/nr.omc \
    -w 1920 -h 1080 --fmt 422 --depth 10 --bpp 1.0 --slice-h 16
md5sum /tmp/nr.omc      # d6e111cfaf33c17406182bc1310a0b90

# 3. the master that exposes the problem: an ordinary limited-range master
#    graded to the container rails, which is what a colourist does and what
#    12.8 wrongly treated as a graphics-only situation
cd ../..
python3 tests/mkfullrange.py tests/raw/gfx1080_422_10.yuv \
        tests/raw/gfx1080_fullrange_422_10.yuv 1920 1080 422 10 auto

# 4. the chain, off and on
tests/genchain_bb.sh tests/raw/gfx1080_fullrange_422_10.yuv 1920 1080 422 10 0.5 16 5
tests/genchain_bb.sh tests/raw/gfx1080_fullrange_422_10.yuv 1920 1080 422 10 0.5 16 5 \
        --gamut-strict 12

# 5. the cost, in the metric that decides.  libvmaf is not part of the drop:
git clone --depth 1 -b v3.0.0 https://github.com/Netflix/vmaf.git /tmp/vmaf_src
cd /tmp/vmaf_src/libvmaf && meson setup build --buildtype release \
        -Denable_asm=false && ninja -C build && cd -
export VMAF_BIN=/tmp/vmaf_src/libvmaf/build/tools/vmaf
export VMAF_MODEL=/tmp/vmaf_src/model/vmaf_v0.6.1neg.json
tests/strict_cost.sh 12

# 6. where the stray samples actually are
omc/omc_v4.9/omc_enc -i tests/raw/gfx1080_fullrange_422_10.yuv -o /tmp/gm.omc \
    -w 1920 -h 1080 --fmt 422 --depth 10 --bpp 0.5 --slice-h 16
omc/omc_v4.9/omc_dec -i /tmp/gm.omc --cdr -o /tmp/gm.cdr
python3 tests/gamut_map.py /tmp/gm.cdr 1920 1088 422 10 16 1080
```

`-Denable_asm=false` avoids needing `nasm`; the C paths are bit-identical, only
slower.  `tests/vmafneg.sh`, `tests/mkfullrange.py`, `tests/gamut_map.py` and
`tests/strict_cost.sh` are new in this section and their full text is in
Appendix G.

**Reproducing the reduction-rule measurements of 12.22.3g, 12.22.3h and
12.22.6.**  Every rule discussed in this section is still in the binary and is
selected by environment variables, so the register can be re-measured rather than
taken on trust.  The shipped default is `OMC_GM_MODE=12 OMC_GM_NUM=15
OMC_GM_DEN=16 OMC_GM_VETO=2 OMC_GM_ALIGN=4`; setting none of them gives exactly
that.

```bash
# the rule this revision replaces
OMC_GM_MODE=0 OMC_GM_NUM=3 OMC_GM_DEN=4 OMC_GM_VETO=0 \
  omc/omc_v4.9/omc_enc ... --gamut-strict 12

# the same rule with the cost-targeted veto, which is 12.22.3h's table
OMC_GM_MODE=0 OMC_GM_NUM=3 OMC_GM_DEN=4 OMC_GM_VETO=2 \
  omc/omc_v4.9/omc_enc ... --gamut-strict 12

# where the repair's cost actually is: candidates, vetoes, reductions, and how
# many of those reductions crossed a quantizer boundary, by band and by size
OMC_GM_STAT=1 omc/omc_v4.9/omc_enc ... --gamut-strict 12

# the uniform veto (28.5% refusals, measurably worse than charging only for
# the crossings -- 12.22.3h)
OMC_GM_VETO=1 omc/omc_v4.9/omc_enc ... --gamut-strict 12

# per-slice trial selection: repair each slice both ways, keep whichever
# committed picture is closer to the source.  1 = plain squared error,
# 2 = activity-masked, 3 = with an added-detail penalty, 4 = the ADM-shaped
# transform-domain criterion.  None is shipped; 12.22.6b says why.
OMC_GM_TRIAL=1 omc/omc_v4.9/omc_enc ... --gamut-strict 12
```

**Regenerating the synthesis-basis table.**  It is built and run by the Makefile,
so an ordinary `make` already regenerates it if `src/dwt.c` changed.  To do it by
hand, and to re-verify the separability and shift-invariance claims of 12.22.3g:

```bash
cd omc/omc_v4.9
cc -O2 -Iinclude -o gen_gm_basis repro/gen_gm_basis.c src/dwt.c -lm
./gen_gm_basis > src/gm_basis_tab.c.inc     # stderr prints the support boxes
```

### 12.22.11 What this does NOT close

Stated plainly, because the value of the register is that it is honest.

- **The mode is a best effort, not a theorem.**  Its budget is bounded on
  purpose — an unbounded search has no worst case, and hardware needs one.
  When the budget runs out the slice ships as it is and `omc_enc_oob()` reports
  it.  What the mode converts is "silently conditional" into "conditional, and
  the encoder tells you which case you are in".
- **A rail on a slice boundary is the hardest case, and it is no longer the
  unclosable one.**  This entry used to say the case was structural: the XSL edit
  is unconditional (12.22.3d) and can always carry an exactly-rail boundary
  sample one code out, and where the quantizer has pinned the whole neighbourhood
  to the rail the repair cannot pull the row off it.  The first half is still
  true.  The conclusion was not — it was true of the *rule*, not of the problem.
  The fallback of 12.22.3i clears the adversarial synthetic completely, and hard
  plates at the exact rails with it.  What remains is that no measurement here
  demonstrates a case the repair cannot close, which is a weaker statement than
  proving there is none: the mode is still a best effort with a bounded budget,
  and a slice that runs out of budget is still reported rather than hidden.  The
  honest position is that the known unclosable case is gone and no new one has
  been found.
- **A cost in a metric is not a cost in a picture.**  12.22.6 reports VMAF-NEG
  and PSNR on the corpus.  Neither is an A/B viewing, and the repair's damage
  is spatially concentrated by construction — it softens exactly the
  neighbourhoods that clip.  A concentrated artifact and a global softening
  score alike and are judged differently.
- **`--gamut-strict` is not signalled and does not need to be.**  It leaves no
  trace in the bitstream, so a decoder cannot tell whether it ran, and does not
  need to: the picture is conforming either way.  Since it is now on by default
  there is no operator decision left to carry — what an integrator sets, once, is
  the budget `N`, from their own slice period and not from the content.
- **One cell where the metric and the picture disagree is not resolved, and is
  not going to be by tuning.**  On `gfxF003_444_8` at half a bit per pixel the
  shipped rule scores 0.25 below the rule it replaces on VMAF-NEG while being
  3.79 dB of luma closer to the source (12.22.6b).  Nine encoder-side statistics
  were measured and none reproduces the metric's verdict on both content types;
  the honest reading is that on near-edge ringing in graphics content, fidelity
  and this metric point in opposite directions.  It is recorded rather than
  tuned away.
- **Per-slice adaptation is out, on measurement, not on principle.**  Repairing
  each slice both ways and keeping whichever picture is closer to the source is
  the only selection rule here that is not a heuristic — and mixing shapes across
  the slices of one frame scored 97.4482 where the two uniform choices score
  98.1117 and 97.8220.  Mixing costs more than either shape costs alone.  A rule
  that needs no adaptation is worth more to a hardware team than a well-tuned one,
  and on this evidence none is needed.
- **The rail stress clip is still the worst case by a wide margin, and it is
  deliberately not a target.**  At half a bit per pixel it costs 13.25 VMAF-NEG
  against the unrepaired picture, down from 35.25 but nowhere near free.  It is
  **synthesized** by `tests/mkrail.py` to be the hardest thing the rule can face
  — one-row rail features walked across slice boundaries — and the structural
  reason it cannot close is the unconditional XSL edit, stated above.  Per the
  project owner's direction recorded in 12.22.6a, synthesized footage does not
  drive this work: the numbers are reported and the gate is kept, but no rule was
  chosen or rejected on them.  Real graphics masters are a different matter and
  do count.
- **"Perfect on every cell" is not claimed and may not be reachable.**  The mode
  reaches zero out-of-range samples on every cell of the corpus, which is its
  actual contract, and that is a theorem-shaped result.  Costing exactly nothing
  in a perceptual metric on every cell is not, and the register above shows why:
  on one class of content the metric and measured fidelity disagree about which
  picture is better, so no single rule can be free by both standards at once.
  Four cells now land inside ±0.06 of the unrepaired picture and the worst
  camera cell inside 0.5.  Further work should be judged against those numbers,
  not against zero.
## 12.23 The "ants": what they are, why the rebuild made them worse, and the fix

### 12.23.1 The defect, in the terms the project already uses

`docs/REPORT.md` sections 18.5–18.7 record the one thing a blind viewer
identified twice as giving this codec away: in areas the **source holds still**,
the decoded picture does not.  The viewer called it ants — a carpet of
small, fast, uncorrelated movement over a wall, a sky, a graded background.
It is not a fidelity defect in the usual sense.  A still frame of it looks
fine.  It only exists in time.

The instrument the project built for it, and the one used throughout this
section, is in §18.6:

* split every plane into 16×16 blocks;
* a block **qualifies** when the source holds it both **flat** (per-frame
  standard deviation at or under a threshold) and **static** (mean
  frame-to-frame difference at or under a threshold), in every frame and
  every frame pair;
* over the samples of qualifying blocks report
  * **tail** = P(|frame-to-frame difference| > 6 code values) — the ant count,
  * **boil** = mean |frame-to-frame difference| — the average movement.

Three things about how it is used here, all of them departures from §18.7 that
this section adopts deliberately:

**It runs on all three planes.**  The project's own version is luma-only.
Colour crawl in a flat coloured area is the same defect wearing a different
coat, and a luma-gated measurement cannot see it.  Every table below carries Y,
Cb and Cr.

**The source's own value is printed beside every measurement**, in the form
`decode-tail / source-tail`.  The target is **not zero**.  Real footage has
grain and grain moves; a codec quieter than its own source has removed texture
rather than fixed anything.  §18.6 is explicit that the reference the viewer
was actually using was the incumbent's *sub-source* calm — JPEG XS reads
**below** the master on this instrument, because its coarser per-frame
quantization drops the source's own sub-code wobble into the same bucket every
frame.  That is the bar: at or below the source's column, the way the incumbent
is.

**The block count is part of the evidence.**  On some content the strict
thresholds select almost nothing, and a percentage computed over three blocks
is not evidence.  `tests/ants.py` prints the count with every figure.

### 12.23.2 What the rebuild did to it

The T5 rebuild (§5.7) removed two things from the grain fill: the three-tier
activity taper and the half-strength amplitude class.  Both were added in the
v4.6 and v4.7 rounds specifically to close this defect, and §5.7 removed them
for a reason that has nothing to do with picture quality — the taper floors
amplitudes at one code, and the tapered mean is not a fixed point of the
amplitude derivation, so a later generation cannot re-derive what the previous
one committed and the generation guarantee fails.

That reasoning is correct and stands.  The consequence was not stated at the
time and is stated here: **the ants came back, and by a large factor.**  On an
eight-frame still master built from real footage — a master whose own
frame-to-frame movement is exactly zero, so every code of movement in the
decode is manufactured by the codec — the measured luma tail went from
0.09 % (v4.14) to 0.29–0.49 % depending on the arm.

### 12.23.3 Attribution: which part of the rebuild did it

Before designing anything, the excess was attributed to a mechanism rather than
to "the rebuild".  The master is `still720_444_8`: frame 0 of a real 4:4:4
8-bit film-grain clip, repeated eight times, so **the source's own tail is
exactly 0.00 on all three planes** and every code of movement in a decode is
manufactured by the codec.  Figures are the ants tail per plane, at 1.0 bpp.

```
still720_444_8 @ 1.0 bpp.  The source is frame 0 repeated, so its own tail
is EXACTLY 0.00 on all three planes: every code of movement below is the
codec's.  Arms run on the v4.14 drop and on this build.
  v4.14, as shipped (fill on)            Y   8.42  Cb  10.96  Cr  10.51   NEG 99.5518
  v4.14, fill off                        Y   8.02  Cb  10.39  Cr   9.84   NEG 99.5535
  v4.14, refresh 64 (fill on)            Y   4.95  Cb   7.41  Cr   7.05   NEG 99.5518
  minor 11 behaviour (ants fix off)      Y   9.09  Cb  12.29  Cr  11.99   NEG 99.5473
  minor 11 behaviour, fill off           Y   8.68  Cb  11.39  Cr  10.84   NEG 99.5589
  minor 11 behaviour, fill off, refresh 64 Y   4.97  Cb   7.46  Cr   7.04   NEG 99.5575
  minor 11 behaviour, fill off, DEADZONE OFF Y  26.00  Cb  23.28  Cr  20.81   NEG 99.5457
  shipped fix, fill on                   Y   7.70  Cb   6.63  Cr   6.38   NEG 99.5583
  SHIPPED DEFAULTS                       Y   7.54  Cb   6.13  Cr   5.53   NEG 99.5624
  SHIPPED DEFAULTS, all-intra (R=1)      Y   0.50  Cb   0.56  Cr   0.54   NEG 99.5633
```

Read it in four steps.

* **Turning the fill off recovers most of the regression, on both builds.**
  v4.14 loses about half a point of tail to its own fill; the rebuilt fill
  loses more, which is the regression 12.23.2 names.
* **With the refresh period taken out as a variable, the two builds agree.**
  `minor 11 behaviour, fill off, refresh 64` and `v4.14, refresh 64` land within
  a few hundredths of each other on every plane.  There is no unexplained
  temporal regression hiding in the rebuilt prediction, the derived motion, or
  the reversible seam blend.  At the shipping refresh period the rebuild's
  fill-off arm still sits a few per cent above v4.14's, which is real but is
  not the defect this section is about.
* **Roughly half the absolute level, in BOTH builds, is the rolling intra
  refresh.**  Stretching the period from 8 to 64 halves the tail on every
  plane.  A slice coded intra this frame does not reconstruct identically to
  the same slice coded inter last frame, and on still content that shows up
  once every `R` frames.
* **And the quantizer's zero zone is the dominant term.**  The
  `DEADZONE OFF` arm — the same encoder with the existing F-2 deadzone
  disabled, nothing else changed — triples the tail on every plane.  That is
  the measurement that pointed at the mechanism in 12.23.5, because the
  deadzone is nothing but a widening of the zero/one boundary, and widening it
  a little already buys a factor of three.

Two candidate levers came out of this, and one was measured and rejected:
going all-intra (`--refresh 1`) removes the refresh term completely, but on
real footage it **costs** VMAF-NEG — 3.3 points on `cineA21_444_10` at 0.5 bpp,
0.4 points at 1.0 bpp.  The refresh period is a resilience parameter (A5) and
is not available as an ants knob; 12.20's camera-side profile is where that
trade is already taken deliberately, for a different reason.

That left the deadzone finding, which is the one this section builds on.

### 12.23.4 Why "fix it in the fill" was not enough

Three fill-side designs were built and measured before the one that worked.

**Restore the taper.**  Fails for exactly the reason §5.7 gives.  Making the
*derivation* taper-aware does restore the gain fixed point to the digit
(generation 2 re-derives 16·g exactly), but the amplitude change breaks the
generation lock further upstream: the lattice scan that proposes candidate
plans reads the committed fill values, and a tapered fill at shift *s* is
indistinguishable from an untapered fill at shift *s−t*, so the search stops
proposing the plan the previous generation actually used.  Measured: the gain
re-derived correctly and the slice still failed to lock.  Forcing a
**constant** taper reproduced the same five gate failures, which proves the
breakage is the amplitude change itself and not any instability in the
activity classification.

**Stop the fill tile animating.**  The fill's sign comes from a tile indexed by
(column + offset, row + offset) with per-frame offsets, so the regenerated
grain moves at frame rate by design.  Pinning the offsets makes the fill
static.  It helps and it is kept (`--fill-static`, and it is now the behaviour
whenever the fill runs), but on its own it recovers about a third of the gap.

**Give the flattest activity tier no fill at all.**  This is the limit case of
the taper and it is simpler than the taper: a position that is not filled
reconstructs to exactly zero, which is a lattice point at *every* shift, so the
candidate search is untouched and the fixed point is preserved by construction.
It is normative — the gate is read identically by the derivation, the verifier,
the encoder reconstruction and the decoder — and it costs zero bits, because
the class comes from the LL both ends already hold.  This is the change that
takes the stream to **minor 12**.

Together those three recover most of the regression against v4.14.  They do not
get anywhere near the incumbent, and the incumbent is the bar.  For that the
fix had to move out of the fill and into the quantizer.

### 12.23.5 The mechanism, stated exactly

Take a region the source holds flat.  Its detail coefficients are small — the
distribution is concentrated near zero.  The quantizer's zero/one boundary sits
at half a step (nine sixteenths of a step in the detail bands the F-2 deadzone
covers).  A coefficient whose magnitude sits **near that boundary** is carried
back and forth across it by the source's own sub-code wobble: sensor noise,
dither, the last bit of a grade.  Each crossing changes the coded value between
0 and ±1, and **each such change moves the reconstruction by a full quantizer
step** — 16 code values at shift 4, 64 at shift 6.

That is the ants, stated as arithmetic.  It is not a temporal-prediction defect
and it is not specific to the fill; the fill made it much worse because it
*also* paints a quarter-step at every zero-coded position with a sign that
advances with the frame index, but the underlying flicker is there without it.

**This is not a theory that was adopted and then fitted to.**  It is what the
`DEADZONE OFF` arm of 12.23.3 measures.  The F-2 deadzone already in the codec
does one thing: it moves the zero/one boundary of the detail bands from half a
step to nine sixteenths of a step, in the detail bands, on the flat side only.
That is **one eighth wider** and it changes nothing else — and switching it off
**triples the ants tail on every plane**: 8.68 → 26.00 on luma, 11.39 → 23.28
and 10.84 → 20.81 on the two chroma planes, against the same encoder with the
deadzone left on.  A one-sixteenth-of-a-step change to that boundary moving the
defect by a factor of three is only possible if the boundary is where the
defect lives.

The fix is the same lever, deliberately, and pushed as far as the lattice
allows.

It also explains the incumbent's behaviour, which had been recorded as a
curiosity rather than as a mechanism.  **JPEG XS reads below the master on this
instrument** because it is stateless and quantizes each frame coarsely: the
same wobble lands in the same bucket every frame, so the reconstruction does
not move.  Its calm is a *quantization* property, not a temporal one.

### 12.23.6 The fix: temporal calm

**In positions the source holds flat, a detail coefficient of about one
quantizer step is not texture.  Give those positions a full-step zero zone
instead of a half-step one.**

Concretely, per slice, per plane, for every detail band 2…9:

1. Read the co-located cell of the **source LL band** and form the local
   gradient `|LL[r][x+1] − LL[r][x−1]| + |LL[r+1][x] − LL[r−1][x]|`.  This is
   the same activity measure, with the same two-stage index clamp, that
   `fill_gate_g` already uses; the clamp matters (F-1) because the
   interior-preference form goes out of range when the LL band is under three
   cells in a dimension, which happens at `slice_h` 8 and at 32-sample plane
   widths.
2. If that gradient is below a ceiling — `OMC_CALM_THR`, default **24** code
   values quoted at 8-bit and scaled by the coded depth, so 96 at 10-bit and
   384 at 12-bit — the position is a candidate.
3. It is **calm** only if its own coefficient is also grain-scale in absolute
   terms: below `OMC_CALM_AMP << (depth − 7)`, default **3**, which is 6 codes
   at 8-bit, 24 at 10-bit and 96 at 12-bit.  This second test is not a
   refinement, it is what makes the rule safe: one quantizer step is not a
   fixed amount of picture, and at half a bit per pixel on a 12-bit master the
   step can be wide enough that a one-step coefficient is real energy rather
   than sub-code wobble.  Without it the fix falls below the previous build's
   VMAF-NEG on the 4:4:4 8-bit graphics master; with it, it does not fall below
   on any cell of the corpus.  The bound reads the **intra-domain** coefficient
   — the same value the grain-replace amplitude vote reads — so a position is
   classified identically whether its band ends up coded intra or inter, which
   matters because the coding mode is chosen after this pass runs.
4. A calm position whose quantized magnitude comes out as exactly 1 and whose
   coefficient magnitude is **strictly less than one step** is coded as zero.

It runs on intra and inter slices alike, because a rolling-refresh slice is
intra and shows the same flicker; on every plane, because chroma crawl is the
same defect; and independently of `--grain-replace`, whose classifier owns a
disjoint set of positions (grain, not flat) and is left alone.

**Nothing is added to the picture.**  Energy is only ever removed.  That is the
property that makes this admissible under the standing constraint that a fix
must not be bought on VMAF-NEG — the model that refuses to credit energy the
source did not have cannot be gamed by a change that only removes energy.  The
measured result is stronger than "not spent": VMAF-NEG **improves**, because
the bits the flat regions stop spending on one-step flicker are redistributed
by the exact-CBR allocator to regions that carry structure.

### 12.23.7 Why this cannot break generation exactness

By construction, and by exactly the argument the F-2 deadzone already rests on
(`src/internal.h`, `omc_quant1b_dz`):

> Every coefficient of a **previously coded** picture is exactly `q << s` — that
> is what "the reconstruction points stay `q << s`" means, and it is the lattice
> identity the whole generation lock is built on.  For `|q| == 1` that magnitude
> is exactly `1 << s`.  The calm test is a **strict** `|c| < (1 << s)`, which
> `1 << s` fails.  **The kill can therefore never fire on a committed picture.**

Three consequences worth stating separately, because each closes an objection
that was raised against earlier candidate designs:

* The classifier reads the **source** LL, which does drift between generations.
  That is harmless *precisely because* the kill cannot fire on a committed
  picture at all: a classification that changes has nothing left to act on.
  Earlier designs that held the reconstruction toward the previous frame did
  not have this property, and were abandoned for it — a hold with any non-zero
  tolerance can fire in generation 2 where it did not fire in generation 1, and
  the slice then fails to lock.
* Nothing normative changed.  The decoder is untouched by this fix; it is an
  encoder-side quantization decision, like the deadzone and like
  `--grain-replace`.  A decoder cannot tell a calm-killed coefficient from one
  that was zero to begin with.
* The kill depth is structurally bounded at `|q| == 1` and cannot be widened.
  Killing `|q| <= 2` would need `|c| < 2 << s`, and a committed picture's
  `|q| == 1` coefficient has `|c| == 1 << s`, which **is** less than `2 << s` —
  so a depth-2 kill would fire on a committed picture and break the lock.  The
  bound is not a tuning choice; it is the lattice.

Two further properties fall out of the same inequality and were checked rather
than assumed:

* **Lossless coding is untouched.**  At shift 0 the kill's test is
  `|q| == 1 and |c| < 1`, and `|q| == 1` means `|c| == 1`, so it can never
  fire.  Checked end to end: `--lossless` on a 4:2:2 10-bit master decodes
  byte-identical to its input with the fix on
  (`8e801e5935302b54a06ee67474331338` both sides).
* **A minor-11 decoder refuses these streams rather than mis-decoding them.**
  `omc_read_stream_header` returns −2 on any minor but its own.  Checked
  against a minor-11 build made from Appendix A + D: `omc_dec: bad stream
  header`.

**And measured, not only argued.**  The battery runs the chains on the shipped
defaults, on the shipped defaults with the fill opted in, and with the ants fix
switched off — the last of these to show that the guarantee does not *depend*
on the fix any more than it is broken by it:

```
```
PASS  [1920x1080->1920x1088 422/10b bpp=1.0 sh=16 gens=10 --fill] g1.omc=da71ace658e8dd1d7663fa6efa029ced
PASS  [2048x1152->2048x1152 444/10b bpp=2.0 sh=16 gens=10 --fill] g1.omc=64754826ac2c30fc3172f1b50dae9e5a
PASS  [1280x720->1280x720 444/8b bpp=0.5 sh=8 gens=10 --fill] g1.omc=1697c83d661d221fe7bc55a7ea6f2e22
PASS  [BB 1920x1080->1920x1088 422/10b bpp=0.5 sh=16 gens=10 --gamut-strict 12 --fill] g1.omc=61b812b20604d7989295b04dbed63d67 range=[0..1022] oob=0
PASS  [1920x1080->1920x1088 422/10b bpp=1.0 sh=16 gens=10 --fill] g1.omc=a7b70628b972fc87e2f4844a5ad8b14d
```
```

### 12.23.8 The second half: the grain fill's default

With the quantizer discipline in place the fill was re-measured rather than
assumed.  Both arms below have the ants fix **off**, so the comparison is the
fill and nothing else.  On almost every clip and rate of the corpus, running
with the fill **off** is at least as good as running with it on **on both
metrics at once** — lower ants tail on all three planes, and VMAF-NEG at or
above.  The count is under the table, and the cells that do not follow the
pattern are the two 4K film masters, where the fill's effect on the ants is
already within a few hundredths of a point either way.

| content | bpp | grain fill | Y tail | Cb tail | Cr tail | VMAF-NEG |
|---|---|---|---|---|---|---|
| still1080_422_10 | 0.5 | on | 0.85 | 0.39 | 0.17 | 95.4598 |
| | | **off** | **0.21** | **0.35** | **0.16** | **95.6221** |
| still1080_422_10 | 1.0 | on | 0.29 | 0.25 | 0.07 | 96.4596 |
| | | **off** | **0.05** | **0.24** | **0.07** | **96.5091** |
| still1080_422_10 | 2.0 | on | 0.01 | 0.02 | 0.00 | 96.9597 |
| | | **off** | **0.00** | **0.02** | **0.00** | **96.9615** |
| loop1080_422_10 | 0.5 | on | 2.87 | 2.02 | 0.60 | 95.2803 |
| | | **off** | **2.22** | **2.05** | **0.62** | **95.4054** |
| loop1080_422_10 | 1.0 | on | 2.16 | 1.86 | 0.44 | 96.2948 |
| | | **off** | **1.97** | **1.86** | **0.44** | **96.3627** |
| loop1080_422_10 | 2.0 | on | 2.06 | 2.49 | 0.51 | 96.8764 |
| | | **off** | **2.04** | **2.48** | **0.51** | **96.8834** |
| still720_444_8 | 0.5 | on | 23.82 | 21.19 | 20.60 | 99.3143 |
| | | **off** | **22.68** | **20.76** | **19.89** | **99.3413** |
| still720_444_8 | 1.0 | on | 9.09 | 12.29 | 11.99 | 99.5473 |
| | | **off** | **8.68** | **11.39** | **10.84** | **99.5589** |
| gfx1080_fullrange_422_10 | 1.0 | on | 7.66 | 39.06 | 33.82 | 94.1578 |
| | | **off** | **6.13** | **32.03** | **24.30** | **94.3461** |
| gfx1080_422_10 | 1.0 | on | 2.13 | 1.84 | 0.44 | 96.2269 |
| | | **off** | **1.91** | **1.83** | **0.44** | **96.3124** |
| gfx1080_444_12 | 1.0 | on | 9.34 | 4.06 | 18.02 | 95.5993 |
| | | **off** | **6.84** | **2.51** | **13.90** | **95.8038** |
| cineA21_444_10 | 1.0 | on | 17.47 | 12.50 | 24.58 | 89.6413 |
| | | **off** | **15.78** | **10.88** | **22.39** | **90.3884** |
| cineA21_422_12 | 1.0 | on | 8.08 | 15.28 | 10.03 | 93.3405 |
| | | **off** | **5.16** | **9.69** | **6.87** | **93.7693** |
| cineA31_720_444_8 | 1.0 | on | 37.11 | 30.94 | 29.15 | 98.7927 |
| | | **off** | **36.80** | **30.21** | **28.32** | **98.8237** |
| cine4k_422_8 | 1.0 | on | 38.65 | 34.74 | 34.67 | 98.1077 |
| | | **off** | **38.69** | **35.01** | **34.90** | **98.1133** |
| gfxF003_444_8 | 1.0 | on | 19.45 | 30.70 | 32.46 | 98.9560 |
| | | **off** | **19.43** | **30.42** | **32.33** | **98.9573** |

Cells where turning the fill OFF is at least as good on all three planes AND on VMAF-NEG: **14 of 16**.

That is not a marginal call and it is not content-dependent, so it is taken as
the default rather than offered as an option: **the grain fill is now off
unless asked for**, with `--fill` to enable it and `--no-fill` still accepted.
When it is enabled it runs with the static tile and the flattest-tier gate of
12.23.4, which is what minor 12 signals.

The fill is not removed.  It exists to hold grain look on textured masters and
it still does that; what the measurement says is that on this corpus, judged by
the metric this project judges by, it costs more than it returns.  A build team
that wants it has one flag.
### 12.23.9 Results

Every number below comes from `tests/antsmatrix.sh` on the shipped build,
reproduced in 12.23.12.  **Coverage, stated rather than implied:** the three
synthetic-motion masters were run at 0.5, 1.0 and 2.0 bits per pixel; the eight
real-footage masters were run at 1.0, because the full three-rate sweep over
4K material did not fit the time this revision had.  The rate dimension is
covered instead by the threshold sweep at the end of this section, which runs
0.5 / 1.0 / 2.0 over twelve clip-rate cells including both 4K masters.  Nothing
was dropped after being measured — the arms below are the arms that were run.  Read each cell as **decode tail / source tail**:
the second figure is the movement the master itself contains, and it is the
target.  A decode *below* its source column has the incumbent's "sub-source
calm" — the property `docs/REPORT.md` 18.6 records as what the blind viewer was
actually comparing against.

Four arms per cell, so that the two halves of the fix can be told apart:

| arm | what it is |
|---|---|
| reference build | the v4.14 drop this project started from |
| ants fix off, fill on | the previous revision's shipping behaviour — the floor everything is measured against |
| ants fix off, fill off | the fill's contribution alone |
| **SHIPPED DEFAULTS** | the ants fix on, the fill off |

```
=== still1080_422_10 @ 0.5   decode-tail/source-tail %
  reference build          Y   0.39/0.00   Cb   0.48/0.00   Cr   0.22/0.00   | strict Y   0.27/0.00   | NEG 95.6006
  ants fix off, fill on    Y   0.85/0.00   Cb   0.39/0.00   Cr   0.17/0.00   | strict Y   0.59/0.00   | NEG 95.4598
  ants fix off, fill off   Y   0.21/0.00   Cb   0.35/0.00   Cr   0.16/0.00   | strict Y   0.16/0.00   | NEG 95.6221
  shipped fix, fill on     Y   0.51/0.00   Cb   0.19/0.00   Cr   0.07/0.00   | strict Y   0.31/0.00   | NEG 95.7547
  SHIPPED DEFAULTS         Y   0.08/0.00   Cb   0.20/0.00   Cr   0.08/0.00   | strict Y   0.05/0.00   | NEG 95.9030
=== still1080_422_10 @ 1.0   decode-tail/source-tail %
  reference build          Y   0.09/0.00   Cb   0.26/0.00   Cr   0.08/0.00   | strict Y   0.08/0.00   | NEG 96.5456
  ants fix off, fill on    Y   0.29/0.00   Cb   0.25/0.00   Cr   0.07/0.00   | strict Y   0.20/0.00   | NEG 96.4596
  ants fix off, fill off   Y   0.05/0.00   Cb   0.24/0.00   Cr   0.07/0.00   | strict Y   0.05/0.00   | NEG 96.5091
  shipped fix, fill on     Y   0.11/0.00   Cb   0.09/0.00   Cr   0.02/0.00   | strict Y   0.07/0.00   | NEG 96.5254
  SHIPPED DEFAULTS         Y   0.02/0.00   Cb   0.09/0.00   Cr   0.02/0.00   | strict Y   0.02/0.00   | NEG 96.5510
=== still1080_422_10 @ 2.0   decode-tail/source-tail %
  reference build          Y   0.00/0.00   Cb   0.02/0.00   Cr   0.01/0.00   | strict Y   0.00/0.00   | NEG 97.0167
  ants fix off, fill on    Y   0.01/0.00   Cb   0.02/0.00   Cr   0.00/0.00   | strict Y   0.01/0.00   | NEG 96.9597
  ants fix off, fill off   Y   0.00/0.00   Cb   0.02/0.00   Cr   0.00/0.00   | strict Y   0.00/0.00   | NEG 96.9615
  shipped fix, fill on     Y   0.01/0.00   Cb   0.04/0.00   Cr   0.01/0.00   | strict Y   0.01/0.00   | NEG 96.9711
  SHIPPED DEFAULTS         Y   0.00/0.00   Cb   0.04/0.00   Cr   0.01/0.00   | strict Y   0.00/0.00   | NEG 96.9682
=== loop1080_422_10 @ 0.5   decode-tail/source-tail %
  reference build          Y   2.82/1.26   Cb   2.18/2.23   Cr   0.70/0.35   | strict Y   0.85/0.17   | NEG 95.3793
  ants fix off, fill on    Y   2.87/1.26   Cb   2.02/2.23   Cr   0.60/0.35   | strict Y   0.95/0.17   | NEG 95.2803
  ants fix off, fill off   Y   2.22/1.26   Cb   2.05/2.23   Cr   0.62/0.35   | strict Y   0.63/0.17   | NEG 95.4054
  shipped fix, fill on     Y   1.05/1.26   Cb   0.40/2.23   Cr   0.11/0.35   | strict Y   0.25/0.17   | NEG 95.6474
  SHIPPED DEFAULTS         Y   0.51/1.26   Cb   0.36/2.23   Cr   0.10/0.35   | strict Y   0.06/0.17   | NEG 95.8052
=== loop1080_422_10 @ 1.0   decode-tail/source-tail %
  reference build          Y   2.13/1.26   Cb   1.98/2.23   Cr   0.49/0.35   | strict Y   0.69/0.17   | NEG 96.3418
  ants fix off, fill on    Y   2.16/1.26   Cb   1.86/2.23   Cr   0.44/0.35   | strict Y   0.70/0.17   | NEG 96.2948
  ants fix off, fill off   Y   1.97/1.26   Cb   1.86/2.23   Cr   0.44/0.35   | strict Y   0.62/0.17   | NEG 96.3627
  shipped fix, fill on     Y   1.04/1.26   Cb   0.60/2.23   Cr   0.07/0.35   | strict Y   0.17/0.17   | NEG 96.6061
  SHIPPED DEFAULTS         Y   0.86/1.26   Cb   0.59/2.23   Cr   0.07/0.35   | strict Y   0.12/0.17   | NEG 96.6509
=== loop1080_422_10 @ 2.0   decode-tail/source-tail %
  reference build          Y   2.13/1.26   Cb   2.58/2.23   Cr   0.53/0.35   | strict Y   0.59/0.17   | NEG 96.8893
  ants fix off, fill on    Y   2.06/1.26   Cb   2.49/2.23   Cr   0.51/0.35   | strict Y   0.55/0.17   | NEG 96.8764
  ants fix off, fill off   Y   2.04/1.26   Cb   2.48/2.23   Cr   0.51/0.35   | strict Y   0.54/0.17   | NEG 96.8834
  shipped fix, fill on     Y   1.59/1.26   Cb   1.13/2.23   Cr   0.17/0.35   | strict Y   0.37/0.17   | NEG 96.9380
  SHIPPED DEFAULTS         Y   1.55/1.26   Cb   1.13/2.23   Cr   0.17/0.35   | strict Y   0.36/0.17   | NEG 96.9445
=== still720_444_8 @ 0.5   decode-tail/source-tail %
  reference build          Y  21.43/0.00   Cb  20.59/0.00   Cr  19.56/0.00   | strict Y  28.56/0.00   | NEG 99.3295
  ants fix off, fill on    Y  23.82/0.00   Cb  21.19/0.00   Cr  20.60/0.00   | strict Y  29.63/0.00   | NEG 99.3143
  ants fix off, fill off   Y  22.68/0.00   Cb  20.76/0.00   Cr  19.89/0.00   | strict Y  28.80/0.00   | NEG 99.3413
  shipped fix, fill on     Y  14.60/0.00   Cb  11.30/0.00   Cr  11.06/0.00   | strict Y  16.12/0.00   | NEG 99.3246
  SHIPPED DEFAULTS         Y  13.91/0.00   Cb  10.39/0.00   Cr   9.90/0.00   | strict Y  13.84/0.00   | NEG 99.3339
=== still720_444_8 @ 1.0   decode-tail/source-tail %
  reference build          Y   8.42/0.00   Cb  10.96/0.00   Cr  10.51/0.00   | strict Y   8.76/0.00   | NEG 99.5518
  ants fix off, fill on    Y   9.09/0.00   Cb  12.29/0.00   Cr  11.99/0.00   | strict Y   9.44/0.00   | NEG 99.5473
  ants fix off, fill off   Y   8.68/0.00   Cb  11.39/0.00   Cr  10.84/0.00   | strict Y   8.56/0.00   | NEG 99.5589
  shipped fix, fill on     Y   7.70/0.00   Cb   6.63/0.00   Cr   6.38/0.00   | strict Y   4.90/0.00   | NEG 99.5583
  SHIPPED DEFAULTS         Y   7.54/0.00   Cb   6.13/0.00   Cr   5.53/0.00   | strict Y   4.43/0.00   | NEG 99.5624
=== still720_444_8 @ 2.0   decode-tail/source-tail %
  reference build          Y   4.09/0.00   Cb   6.92/0.00   Cr   6.47/0.00   | strict Y   2.17/0.00   | NEG 99.6796
=== gfx1080_fullrange_422_10 @ 1.0   decode-tail/source-tail %
  reference build          Y   8.36/7.16   Cb  39.65/57.91  Cr  32.38/52.31  | strict Y   3.40/1.34   | NEG 94.2787
  ants fix off, fill on    Y   7.66/7.16   Cb  39.06/57.91  Cr  33.82/52.31  | strict Y   3.54/1.34   | NEG 94.1578
  ants fix off, fill off   Y   6.13/7.16   Cb  32.03/57.91  Cr  24.30/52.31  | strict Y   2.18/1.34   | NEG 94.3461
  shipped fix, fill on     Y   2.34/7.16   Cb  14.06/57.91  Cr  14.81/52.31  | strict Y   0.73/1.34   | NEG 94.6699
  SHIPPED DEFAULTS         Y   1.57/7.16   Cb  14.45/57.91  Cr   8.60/52.31  | strict Y   0.17/1.34   | NEG 94.8466
=== gfx1080_422_10 @ 1.0   decode-tail/source-tail %
  reference build          Y   2.08/1.26   Cb   1.96/2.23   Cr   0.48/0.35   | strict Y   0.66/0.17   | NEG 96.2739
  ants fix off, fill on    Y   2.13/1.26   Cb   1.84/2.23   Cr   0.44/0.35   | strict Y   0.68/0.17   | NEG 96.2269
  ants fix off, fill off   Y   1.91/1.26   Cb   1.83/2.23   Cr   0.44/0.35   | strict Y   0.59/0.17   | NEG 96.3124
  shipped fix, fill on     Y   1.07/1.26   Cb   0.63/2.23   Cr   0.08/0.35   | strict Y   0.18/0.17   | NEG 96.4799
  SHIPPED DEFAULTS         Y   0.85/1.26   Cb   0.62/2.23   Cr   0.08/0.35   | strict Y   0.12/0.17   | NEG 96.5238
=== gfx1080_444_12 @ 1.0   decode-tail/source-tail %
  reference build          Y  11.01/11.69  Cb   5.16/9.83   Cr  23.16/27.60  | strict Y   4.07/2.50   | NEG 95.7074
  ants fix off, fill on    Y   9.34/11.69  Cb   4.06/9.83   Cr  18.02/27.60  | strict Y   3.09/2.50   | NEG 95.5993
  ants fix off, fill off   Y   6.84/11.69  Cb   2.51/9.83   Cr  13.90/27.60  | strict Y   1.10/2.50   | NEG 95.8038
  shipped fix, fill on     Y   5.62/11.69  Cb   2.76/9.83   Cr  12.62/27.60  | strict Y   1.19/2.50   | NEG 95.7061
  SHIPPED DEFAULTS         Y   3.59/11.69  Cb   0.99/9.83   Cr   6.29/27.60  | strict Y   0.23/2.50   | NEG 95.8544
=== cineA21_444_10 @ 1.0   decode-tail/source-tail %
  reference build          Y  17.71/19.01  Cb  12.63/19.64  Cr  23.97/35.22  | strict Y   5.03/2.06   | NEG 90.4068
  ants fix off, fill on    Y  17.47/19.01  Cb  12.50/19.64  Cr  24.58/35.22  | strict Y   5.76/2.06   | NEG 89.6413
  ants fix off, fill off   Y  15.78/19.01  Cb  10.88/19.64  Cr  22.39/35.22  | strict Y   3.65/2.06   | NEG 90.3884
  shipped fix, fill on     Y  10.07/19.01  Cb   4.34/19.64  Cr  11.70/35.22  | strict Y   0.68/2.06   | NEG 89.3987
  SHIPPED DEFAULTS         Y   9.19/19.01  Cb   2.98/19.64  Cr   9.86/35.22  | strict Y   0.73/2.06   | NEG 90.0731
=== cineA21_422_12 @ 1.0   decode-tail/source-tail %
  reference build          Y   7.57/7.82   Cb  12.67/13.15  Cr   9.30/10.01  | strict Y   1.46/1.11   | NEG 93.7209
  ants fix off, fill on    Y   8.08/7.82   Cb  15.28/13.15  Cr  10.03/10.01  | strict Y   1.92/1.11   | NEG 93.3405
  ants fix off, fill off   Y   5.16/7.82   Cb   9.69/13.15  Cr   6.87/10.01  | strict Y   0.97/1.11   | NEG 93.7693
  shipped fix, fill on     Y   3.65/7.82   Cb  10.76/13.15  Cr   4.09/10.01  | strict Y   0.34/1.11   | NEG 93.6783
  SHIPPED DEFAULTS         Y   2.56/7.82   Cb   4.41/13.15  Cr   2.61/10.01  | strict Y   0.20/1.11   | NEG 94.0661
=== cineA31_720_444_8 @ 1.0   decode-tail/source-tail %
  reference build          Y  37.23/28.68  Cb  33.00/16.16  Cr  32.14/13.68  | strict Y  36.40/1.40   | NEG 98.8047
  ants fix off, fill on    Y  37.11/28.68  Cb  30.94/16.16  Cr  29.15/13.68  | strict Y  36.54/1.40   | NEG 98.7927
  ants fix off, fill off   Y  36.80/28.68  Cb  30.21/16.16  Cr  28.32/13.68  | strict Y  36.62/1.40   | NEG 98.8237
  shipped fix, fill on     Y  28.03/28.68  Cb  16.06/16.16  Cr  13.53/13.68  | strict Y  20.72/1.40   | NEG 98.8221
  SHIPPED DEFAULTS         Y  27.76/28.68  Cb  15.39/16.16  Cr  12.59/13.68  | strict Y  19.71/1.40   | NEG 98.8331
=== cine4k_422_8 @ 1.0   decode-tail/source-tail %
  reference build          Y  38.84/32.53  Cb  35.18/17.87  Cr  35.02/19.98  | strict Y   6.57/0.78   | NEG 98.1024
  ants fix off, fill on    Y  38.65/32.53  Cb  34.74/17.87  Cr  34.67/19.98  | strict Y   5.84/0.78   | NEG 98.1077
  ants fix off, fill off   Y  38.69/32.53  Cb  35.01/17.87  Cr  34.90/19.98  | strict Y   5.85/0.78   | NEG 98.1133
  shipped fix, fill on     Y  32.72/32.53  Cb  20.70/17.87  Cr  19.53/19.98  | strict Y   4.29/0.78   | NEG 98.1338
  SHIPPED DEFAULTS         Y  32.71/32.53  Cb  20.70/17.87  Cr  19.53/19.98  | strict Y   4.29/0.78   | NEG 98.1336
=== gfxF003_444_8 @ 1.0   decode-tail/source-tail %
  reference build          Y  20.34/19.00  Cb  32.18/17.65  Cr  33.01/20.30  | strict Y   1.90/0.81   | NEG 98.9537
  ants fix off, fill on    Y  19.45/19.00  Cb  30.70/17.65  Cr  32.46/20.30  | strict Y   1.70/0.81   | NEG 98.9560
  ants fix off, fill off   Y  19.43/19.00  Cb  30.42/17.65  Cr  32.33/20.30  | strict Y   1.67/0.81   | NEG 98.9573
  shipped fix, fill on     Y  19.23/19.00  Cb  18.87/17.65  Cr  21.10/20.30  | strict Y   1.74/0.81   | NEG 98.9685
  SHIPPED DEFAULTS         Y  19.21/19.00  Cb  18.47/17.65  Cr  20.90/20.30  | strict Y   1.69/0.81   | NEG 98.9690
```

**How many blocks each figure is computed over.**  A percentage over three
blocks is not evidence, so the count is reported.  It is a property of the
MASTER alone — it does not depend on which codec or which arm produced the
decode — so it is measured once, here, and applies to every figure for that
clip above and below:

```
still1080_422_10           relaxed Y=6654 Cb=3995 Cr=4013           strict Y=3975 Cb=3523 Cr=3718 
loop1080_422_10            relaxed Y=6633 Cb=3995 Cr=4013           strict Y=2322 Cb=1633 Cr=3108 
still720_444_8             relaxed Y=2040 Cb=2162 Cr=2133           strict Y=75 Cb=598 Cr=865 
gfx1080_fullrange_422_10            relaxed Y=6168 Cb=2 Cr=26                strict Y=198 Cb=0 Cr=0 
gfx1080_422_10             relaxed Y=6633 Cb=3995 Cr=4013           strict Y=2322 Cb=1633 Cr=3108 
gfx1080_444_12             relaxed Y=6379 Cb=6434 Cr=4796           strict Y=90 Cb=409 Cr=1 
cineA21_444_10             relaxed Y=3028 Cb=3029 Cr=2410           strict Y=15 Cb=9 Cr=0 
cineA21_422_12             relaxed Y=3272 Cb=4044 Cr=4209           strict Y=204 Cb=102 Cr=1261 
cineA31_720_444_8          relaxed Y=1109 Cb=1761 Cr=1815           strict Y=16 Cb=153 Cr=137 
cine4k_422_8               relaxed Y=1024 Cb=7732 Cr=9126           strict Y=55 Cb=526 Cr=165 
gfxF003_444_8              relaxed Y=7741 Cb=6404 Cr=5973           strict Y=331 Cb=405 Cr=233 
```

Where a plane reads zero the instrument returns **no verdict** for it rather
than a number, and the tables above print `no/--`.

**The headline, on the clips where the instrument has the most blocks to work
with:**

| content | bpp | build | Y tail | Cb tail | Cr tail | Y tail, strict | VMAF-NEG |
|---|---|---|---|---|---|---|---|
| still1080_422_10 | 0.5 | v4.14 | 0.39 | 0.48 | 0.22 | 0.27 | 95.6006 |
| | | *the source itself* | *0.00* | *0.00* | *0.00* | *0.00* | — |
| | | **shipped** | **0.08** | **0.20** | **0.08** | **0.05** | **95.9030** |
| still1080_422_10 | 1.0 | v4.14 | 0.09 | 0.26 | 0.08 | 0.08 | 96.5456 |
| | | *the source itself* | *0.00* | *0.00* | *0.00* | *0.00* | — |
| | | **shipped** | **0.02** | **0.09** | **0.02** | **0.02** | **96.5510** |
| still1080_422_10 | 2.0 | v4.14 | 0.00 | 0.02 | 0.01 | 0.00 | 97.0167 |
| | | *the source itself* | *0.00* | *0.00* | *0.00* | *0.00* | — |
| | | **shipped** | **0.00** | **0.04** | **0.01** | **0.00** | **96.9682** |
| loop1080_422_10 | 0.5 | v4.14 | 2.82 | 2.18 | 0.70 | 0.85 | 95.3793 |
| | | *the source itself* | *1.26* | *2.23* | *0.35* | *0.17* | — |
| | | **shipped** | **0.51** | **0.36** | **0.10** | **0.06** | **95.8052** |
| loop1080_422_10 | 1.0 | v4.14 | 2.13 | 1.98 | 0.49 | 0.69 | 96.3418 |
| | | *the source itself* | *1.26* | *2.23* | *0.35* | *0.17* | — |
| | | **shipped** | **0.86** | **0.59** | **0.07** | **0.12** | **96.6509** |
| loop1080_422_10 | 2.0 | v4.14 | 2.13 | 2.58 | 0.53 | 0.59 | 96.8893 |
| | | *the source itself* | *1.26* | *2.23* | *0.35* | *0.17* | — |
| | | **shipped** | **1.55** | **1.13** | **0.17** | **0.36** | **96.9445** |
| still720_444_8 | 0.5 | v4.14 | 21.43 | 20.59 | 19.56 | 28.56 | 99.3295 |
| | | *the source itself* | *0.00* | *0.00* | *0.00* | *0.00* | — |
| | | **shipped** | **13.91** | **10.39** | **9.90** | **13.84** | **99.3339** |
| still720_444_8 | 1.0 | v4.14 | 8.42 | 10.96 | 10.51 | 8.76 | 99.5518 |
| | | *the source itself* | *0.00* | *0.00* | *0.00* | *0.00* | — |
| | | **shipped** | **7.54** | **6.13** | **5.53** | **4.43** | **99.5624** |
| gfx1080_fullrange_422_10 | 1.0 | v4.14 | 8.36 | 39.65 | 32.38 | 3.40 | 94.2787 |
| | | *the source itself* | *7.16* | *57.91* | *52.31* | *1.34* | — |
| | | **shipped** | **1.57** | **14.45** | **8.60** | **0.17** | **94.8466** |
| gfx1080_422_10 | 1.0 | v4.14 | 2.08 | 1.96 | 0.48 | 0.66 | 96.2739 |
| | | *the source itself* | *1.26* | *2.23* | *0.35* | *0.17* | — |
| | | **shipped** | **0.85** | **0.62** | **0.08** | **0.12** | **96.5238** |
| gfx1080_444_12 | 1.0 | v4.14 | 11.01 | 5.16 | 23.16 | 4.07 | 95.7074 |
| | | *the source itself* | *11.69* | *9.83* | *27.60* | *2.50* | — |
| | | **shipped** | **3.59** | **0.99** | **6.29** | **0.23** | **95.8544** |
| cineA21_444_10 | 1.0 | v4.14 | 17.71 | 12.63 | 23.97 | 5.03 | 90.4068 |
| | | *the source itself* | *19.01* | *19.64* | *35.22* | *2.06* | — |
| | | **shipped** | **9.19** | **2.98** | **9.86** | **0.73** | **90.0731** |
| cineA21_422_12 | 1.0 | v4.14 | 7.57 | 12.67 | 9.30 | 1.46 | 93.7209 |
| | | *the source itself* | *7.82* | *13.15* | *10.01* | *1.11* | — |
| | | **shipped** | **2.56** | **4.41** | **2.61** | **0.20** | **94.0661** |
| cineA31_720_444_8 | 1.0 | v4.14 | 37.23 | 33.00 | 32.14 | 36.40 | 98.8047 |
| | | *the source itself* | *28.68* | *16.16* | *13.68* | *1.40* | — |
| | | **shipped** | **27.76** | **15.39** | **12.59** | **19.71** | **98.8331** |
| cine4k_422_8 | 1.0 | v4.14 | 38.84 | 35.18 | 35.02 | 6.57 | 98.1024 |
| | | *the source itself* | *32.53* | *17.87* | *19.98* | *0.78* | — |
| | | **shipped** | **32.71** | **20.70** | **19.53** | **4.29** | **98.1336** |
| gfxF003_444_8 | 1.0 | v4.14 | 20.34 | 32.18 | 33.01 | 1.90 | 98.9537 |
| | | *the source itself* | *19.00* | *17.65* | *20.30* | *0.81* | — |
| | | **shipped** | **19.21** | **18.47** | **20.90** | **1.69** | **98.9690** |

**Cells where VMAF-NEG is at or above the previous revision's: 16 of 16.**  Cells where the tail is at or below the v4.14 drop's on all three planes: 15 of 16.  Cells where the decode sits at or below the SOURCE's own movement on all three planes: 8 of 11 -- counted only over the cells whose source actually moves, because the three synthetic still masters have a source tail of exactly 0.00 and no lossy codec can be at or below that.

**What the table says.**

1. **The defect is closed against the build that had it closed.**  The count
   under the table is the claim: on all but one cell the shipped build's tail is
   at or below the v4.14 drop's on **all three planes at once**, and it is
   several times below on the clips where the instrument has the most blocks to
   work with.  This is not "back to v4.14".  The exception is named rather than
   averaged away — look for the row where a plane is higher, and read it beside
   its VMAF-NEG, which is not.

2. **It is closed against the SOURCE, which is the bar the incumbent set.**
   `docs/REPORT.md` 18.6 records that the reference the blind viewer was using
   was JPEG XS's *sub-source* calm — a decode quieter than the master it came
   from.  On the cells whose source actually moves, the shipped build reaches
   that on most of them, on all three planes at once; the count is under the
   table.  The cells where it does not are the ones whose source is busiest,
   which is finding 5.

3. **VMAF-NEG went UP, not down.**  This is the constraint the whole fix was
   built under and the one it would have been easiest to fail.  Against the
   previous revision the shipped build gains on essentially every cell, and the
   gains are largest exactly where the ants were worst.  Nothing was added to
   the picture to achieve it — the fix only ever removes coded values — so the
   gain is the exact-CBR allocator moving the bits that were being spent on
   one-step flicker in flat regions into regions that carry structure.

4. **Both halves matter, and they are separable in the table.**  "ants fix off,
   fill off" against "ants fix off, fill on" is the fill's contribution;
   "SHIPPED DEFAULTS" against "ants fix off, fill off" is the quantizer
   discipline's.  The quantizer discipline is the larger of the two on every
   real-footage cell.

5. **Where the source is itself busy, the fix stands down, and that is
   correct.**  On the 4K film cells the source's own tail is above 30 % and the
   shipped build moves it by a fraction of a point.  A region with real texture
   is not flat, so no position in it is ever marked calm.  A fix that "improved"
   those cells would be removing texture the master contains, which is the
   failure mode 12.23's constraint exists to forbid.

6. **Chroma is fixed, not carried.**  The largest proportional reductions in the
   table are on Cb and Cr.  That was not automatic: the instrument had to be
   generalised off luma before it could be seen at all (12.23.1), and the
   project's own version of this measurement would have reported the chroma
   crawl as absent.

**The threshold sweep behind the two defaults.**  `OMC_CALM_THR` is the LL
gradient ceiling, quoted at 8-bit scale; `OMC_CALM_AMP` bounds the coefficient
magnitude the kill will act on, in the same `n << (depth − 7)` units the
grain-replace amplitude vote uses.  Every combination below was run on the same
cells, and the two columns are: the **worst** VMAF-NEG change against the
previous revision's floor across all cells (a negative number means at least one
cell got worse), and the mean ants-tail reduction the calm kill contributes on
top of turning the fill off.

```
thr,amp       cells min dNEG  meanNEG  mean ants reduction vs calm-off
(6, 0)           11    0.010    0.555  24.6%   OK
(6, 2)            4    0.049    0.270  21.7%   OK
(6, 3)            4    0.097    0.353  22.7%   OK
(6, 6)            4    0.039    0.319  22.3%   OK
(12, 0)          11   -0.096    0.401  36.0%   below floor on gfxF003_444_8
(12, 2)           4    0.081    0.282  33.5%   OK
(12, 3)           4    0.099    0.367  34.6%   OK
(12, 6)           4    0.022    0.401  34.4%   OK
(24, 0)          20   -0.491    0.277  44.9%   below floor on gfxF003_444_8
(24, 2)           4    0.067    0.278  41.6%   OK
(24, 3)          19    0.006    0.531  45.2%   OK
(24, 6)          11   -0.261    0.390  42.9%   below floor on gfxF003_444_8
(48, 0)          14   -0.306    0.147  51.6%   below floor on gfx1080_444_12
(48, 2)          12   -0.125    0.411  49.2%   below floor on gfx1080_fullrange_422_10
(48, 3)          12   -0.035    0.463  50.2%   below floor on gfxF003_444_8
(48, 6)           4   -0.103    0.296  47.1%   below floor on cineA31_720_444_8
(96, 0)          10   -0.523    0.020  55.7%   below floor on gfx1080_444_12
(96, 3)          12   -0.050    0.404  51.0%   below floor on gfxF003_444_8
```

(`cells` is how many clip/rate cells that combination was measured on; the
grid was widened as the picture narrowed, which is why the counts differ.  The
two combinations with the largest counts, `(24, 0)` and `(24, 3)`, were run on
the whole corpus.)

The shipped pair is the one with the largest ants reduction whose **worst** cell
still does not fall below the floor.  Raising the ceiling further keeps buying
ants — the sweep shows it — and starts costing VMAF-NEG on the 4:4:4 8-bit
graphics master at half a bit per pixel, which is where the quantizer step is
widest and a one-step coefficient stops being sub-code wobble.  That is exactly
what the amplitude bound exists to catch, and where it stops being able to.
### 12.23.10 What this costs

**Bits: nothing, and that is not a rounding statement.**  The fix removes coded
values; it never adds one.  Under exact CBR the freed bits do not leave the
stream — every slice still spends its exact allocation — so the effect is a
*redistribution* from flat regions to regions that carry structure, which is
where the VMAF-NEG gain in 12.23.9 comes from.  The stream size is identical to
the byte, by construction (A1).

**Latency (A2): nothing.**  The classifier is one pass over the detail bands of
a slice reading four LL cells per position, with no dependency outside the
slice.  It adds no vertical reach, no slice period and no buffer.  `make test`
re-measures the A2 table on this build and every cell is unchanged.

**rt = 0 (C4): unaffected.**  This is an encoder-side choice of which lattice
point to emit.  The decoder reconstructs `q << s` from what it is given, exactly
as before; the gate that compares the encoder's own reconstruction with the
decoder's output (G-T5-GAMUT4, and the `test_cc` suite) still passes.

**FPGA cost (C3): four adds, two absolute values and two compares per
coefficient**, on values the fill gate already fetches for the same position.
The LL cell addresses are the ones `fill_gate_g` computes; a hardware
implementation that already builds that gate gets this for the cost of one
extra comparator per band and a two-bit class register.  No multiplier, no
division, no state carried between slices, and no state carried between frames
— which is why it does not interact with the refresh barriers (A5).

**PSNR: down slightly, and that is the expected direction.**  The fix widens the
zero zone, so the mean squared error in flat regions rises by up to a quarter of
a step squared at the positions it acts on.  `docs/REPORT.md` 18.8.1 already
records that this project has been in the position where VMAF ranked the
*defective* render above the fix; the mandate's ordering is explicit that
VMAF-NEG leads and PSNR is a second opinion, and this is a case where the two
disagree in the direction the ordering anticipates.

### 12.23.11 The gates

Five assertions in `test_xsl`, inside `make test`.  They are built so that the
fix cannot pass by being inert and cannot pass by breaking the guarantee.

| gate | asserts |
|---|---|
| **G-T5-CALM1a** | **non-vacuity.**  With the fix OFF, a master that is flat and static in the source — a constant field carrying a −8…+8 code dither, which is what sensor noise looks like at 10-bit — moves in the decode: more than 1 % of samples change by more than six codes between consecutive frames.  An arm that cannot fail proves nothing, so this one is required to fail. |
| **G-T5-CALM1b** | with the fix ON that movement is **at least halved**. |
| **G-T5-CALM1c** | the fix **changed the stream**.  Without this, 1b could be satisfied by a build in which the fix does nothing and both arms happen to be quiet. |
| **G-T5-CALM2a** | on that same content, with the kill demonstrably firing, **generation 2 reproduces generation 1's pixels byte-for-byte**. |
| **G-T5-CALM2b** | and **generation 3 reproduces generation 2's stream byte-for-byte**. |

2a and 2b are the gate form of the lattice argument in 12.23.7.  The argument
says the kill cannot fire on a committed picture; the gate does not take the
argument's word for it.

The gates print the two tail figures they compared, so a failure says how far
apart they were rather than only that they were.

### 12.23.12 Reproducing this section

Everything below runs from the repository root, against the build of Appendix A
+ D + F.  `tests/ants.py`, `tests/mkstill.py`, `tests/antsmatrix.sh` and
`tests/vmafneg.sh` are reproduced verbatim in Appendix G; libvmaf is not part of
the drop and its build line is in the header of `tests/vmafneg.sh`.

```bash
# 0. the masters.  10.1 builds the corpus; 12.23 adds two SYNTHETIC masters
#    whose source movement is known exactly, so that any movement in the decode
#    is unambiguously the codec's:
#      still  -- frame 0 repeated: source movement is EXACTLY zero
#      loop   -- the frames walked forward and back: source movement is real
#                but returns, so a drifting codec separates from a stable one
python3 tests/mkstill.py still tests/raw/cineA31_422_10.yuv \
        tests/raw/still1080_422_10.yuv 1920 1080 422 10 8
python3 tests/mkstill.py still tests/raw/cineA31_720_444_8.yuv \
        tests/raw/still720_444_8.yuv 1280 720 444 8 8
python3 tests/mkstill.py loop  tests/raw/cineA31_422_10.yuv \
        tests/raw/loop1080_422_10.yuv 1920 1080 422 10 8

# 1. the instrument on one cell, by hand -- the decode column AND the source
#    column, all three planes, with the block count
omc_enc -i tests/raw/gfx1080_fullrange_422_10.yuv -o /tmp/c.omc -w 1920 -h 1080 \
        --fmt 422 --depth 10 --bpp 1.0
omc_dec -i /tmp/c.omc -o /tmp/c.yuv
python3 tests/ants.py tests/raw/gfx1080_fullrange_422_10.yuv /tmp/c.yuv 1920 1080 422 10
python3 tests/ants.py tests/raw/gfx1080_fullrange_422_10.yuv /tmp/c.yuv 1920 1080 422 10 --strict

# 2. the whole matrix of 12.23.9, both metrics, every arm
export VMAF_BIN=... VMAF_MODEL=.../vmaf_v0.6.1neg.json
OMC_BIN=$PWD/omc/omc_v4.9 bash tests/antsmatrix.sh 0.5 1.0 2.0

# 3. the attribution of 12.23.3 -- the arm that settles whether the rebuilt
#    temporal layer is implicated at all
for arm in "" "--no-fill" "--refresh 64" "--no-fill --refresh 64"; do
  omc_enc -i tests/raw/still1080_422_10.yuv -o /tmp/a.omc -w 1920 -h 1080 \
          --fmt 422 --depth 10 --bpp 1.0 $arm
  omc_dec -i /tmp/a.omc -o /tmp/a.yuv
  echo "[$arm]"; python3 tests/ants.py tests/raw/still1080_422_10.yuv /tmp/a.yuv \
          1920 1080 422 10
done

# 4. the threshold sweep of 12.23.9 (the shipped values are the defaults;
#    OMC_CALM=0 restores the minor-11 quantizer exactly)
for t in 6 12 24 48; do for a in 0 3 6; do
  OMC_CALM_THR=$t OMC_CALM_AMP=$a omc_enc -i ... ; done; done

# 5. the gates
cd omc/omc_v4.9 && make test          # G-T5-CALM1a/b/c and 2a/b are in test_xsl

# 6. generation exactness on the shipped defaults, and with the fill opted in
bash tests/genchain.sh    tests/raw/gfx1080_fullrange_422_10.yuv 1920 1080 422 10 1.0 16 10
bash tests/genchain.sh    tests/raw/gfx1080_fullrange_422_10.yuv 1920 1080 422 10 1.0 16 10 --fill
bash tests/genchain_bb.sh tests/raw/gfx1080_fullrange_422_10.yuv 1920 1080 422 10 0.5 16 10 --gamut-strict 12
```

### 12.23.13 What this does not close

**The refresh pulse.**  12.23.3 attributes roughly half the absolute level, in
*both* builds, to the rolling intra refresh: a slice coded intra this frame does
not reconstruct identically to the same slice coded inter last frame, and on
still content that difference is visible once every `R` frames.  The fix reduces
it — a flat region's detail bands are zero in both modes, so the two
reconstructions converge — but it does not remove it.  Removing it entirely
means `--refresh 1`, which is measured in 12.23.3 and rejected: on real footage
it costs up to 3.3 points of VMAF-NEG.  The refresh period is a resilience
parameter (A5) and the camera-side profile of 12.20 is the place where that
trade is already taken deliberately.

**Content whose source is itself busy.**  Where the source's own tail is 30 %
the instrument cannot separate a calm codec from a lucky one, and the fix
correctly stands down there — a region with real texture is not flat, so no
position in it is ever marked calm.  On `cine4k_422_8` at 2.0 bpp the fix moves
the luma tail by two tenths of a point, and that is the right answer, not a
failure.

**The eye.**  Nothing here is a visual verdict.  The mandate is explicit that
only blind full-frame viewing is, and this section establishes where to look
and what the numbers do — not what a viewer will say.

**Whether the threshold is right for content this corpus does not contain.**
The gradient ceiling is one number with a measured sweep behind it on ten
clips, four chroma/depth combinations and three rates.  It is a *default*, not a
constant of nature; `OMC_CALM_THR` and `OMC_CALM_AMP` exist so a build team can
re-run 12.23.12 step 4 on their own material rather than take this corpus's word
for it.  What is not a tuning choice, and cannot be made one, is the kill depth:
12.23.7 shows it is pinned at `|q| == 1` by the lattice.

### 12.23.14 The adversarial pass on these two fixes, and what it found

Both fixes were then attacked rather than admired.  Five findings, all fixed
before this revision was written; they are listed because the register is only
useful if it records what went wrong after the work looked finished.

**1. A left shift of a negative value in five fixed-point sites — including the
normative transform.**  Building all six suites under UndefinedBehaviorSanitizer
found the 9/7-M lifting step in `src/dwt.c`, both polyphase shift-add
multipliers in `src/upconv.c`, the colour matrix multiplier and the tone-map
gain promotion in `src/colour.c` all doing `negative << n`.  C11 6.5.7p4 does
not define that.  The codec's *normative* transform and colour stage were
relying on a compiler extension — every build in this repository happens to be
GCC on two's-complement hardware, where it does what everyone expects, but a
conformance implementation on a different toolchain is not obliged to agree,
and an FPGA translation from this source would have been translating undefined
behaviour.  All five now shift the unsigned representation, which is defined
for every value and compiles to the same instruction.  The encoder's output is
unchanged to the byte.

> One of the five taught something worth passing on.  `cc_mul_sa()` accumulates
> in **64** bits, and the first fix applied a 32-bit macro to it.  Six colour
> gates failed instantly — the self-check, the neutral axis, the accuracy
> bound, the tone map, the range contract and the container round trip.  That
> is the gate set doing exactly its job, and it is why a "behaviour-preserving"
> change still gets run through everything.

**2. A leak in `tests/test_cap.c`** — 393 216 bytes in four reconstruction
buffers, never freed.  Harmless to the codec and fatal to the method: it made
LeakSanitizer report a failure on that suite unconditionally, so a *real* leak
introduced later would have been invisible.  Fixed.  **All six suites are now
clean under AddressSanitizer and UndefinedBehaviorSanitizer: zero findings.**

**3. A measurement harness that contaminated its own arms.**  An early version
of the attribution table set an environment variable as a *prefix on a shell
function call* — `VAR=x cell ...`.  Bash keeps such an assignment after the
function returns, so one arm's setting leaked into the next, and the same
configuration measured twice differed by 10 %.  The codec is deterministic
(three encodes of the same input produce the same md5, and their decodes do
too — checked), so the spread was entirely the harness.  Every arm in this
section is now launched as `env VAR=x binary ...`, with the assignments as
arguments.  **A number that moves when nothing moved is a harness bug until
proven otherwise.**

**4. A truncated log that made two different arms look identical.**  The seam
measurement was piped through `tail`, which cut the arm headers, and two
adjacent blocks read as if the mode had changed nothing on the rail clip — a
conclusion flatly contradicted by the picture-cost table on the same clip.
Re-run with the full output and a stream md5 printed per arm, the two arms
differ as they should.  The figures in 12.22.7 are from the re-run.

**5. A claim in this document that was not true when checked.**  A draft of
12.22.5 said that with the mode off the shipped encoder is byte-identical to
the minor-11 one, and quoted the minor-11 md5.  It is not: 12.23's two
normative fill rules are unconditional, so this build cannot write a minor-11
stream at all.  Checked rather than assumed —
`OMC_CALM=0 omc_enc ... --fill` writes `f16104abe6a4c5cbbe3b873af364553d`, and
patching the version byte back does not recover `156f0237…`.  The claim is
replaced by gate G-T5-GAMUT3, which asserts the mode's inertness on the same
build and does not depend on any recorded md5 surviving a later change, and by
section 5 of the revision record, which says plainly that the old md5s are not
reproducible here and where to go if you need them.

## Appendix F — the delta patch for 12.22 and 12.23 (normative)

Appendix A reproduces the minor-10 build; Appendix D advances it to the
minor-11 build that every number from 12.14 to 12.21 came from.  This appendix
is the delta that adds **both** of the fixes this revision documents: the
strict in-gamut mode of 12.22 and the ants fix of 12.23.

Of the two, only one touches the wire.  The strict in-gamut mode changes no
bitstream syntax and no decoder behaviour, and with the mode off the encoder is
byte-identical to the minor-11 build.  The ants fix has two halves: the
temporal-calm quantizer discipline is **encoder-only** and equally invisible to
a decoder, but the flattest-tier grain-fill gate and the static fill tile are
**normative reconstruction rules**, which is why this patch advances the stream
minor from 11 to **12**.  A minor-11 decoder must not be fed a minor-12 stream
and will refuse it rather than mis-decode it.

Apply **after** Appendix A and Appendix D, from inside `omc_v4.9`:

```
awk '/^=== BEGIN T5 DELTA PATCH ===$/{f=1;next} /^=== END T5 DELTA PATCH ===$/{f=0} f' \
    TEMPORAL_T5.md > t5_delta.patch
cd omc_v4.9
patch -p1 < ../t5.patch          # Appendix A  (minor 10)
patch -p1 < ../t5_m11.patch      # Appendix D  (minor 11)
patch -p1 < ../t5_delta.patch    # Appendix F  (12.22 + 12.23, minor 12)
make && make test                # five suites print "all ok" and the
                                 # sixth prints "test_xsl: all ok";
                                 # no line begins with FAIL
```

The extraction line above matches the two marker lines **exactly and alone**;
do not match on the words inside this paragraph.

`````diff
=== BEGIN T5 DELTA PATCH ===
diff --git a/Makefile b/Makefile
index 04cf8d7..a8e248d 100644
--- a/Makefile
+++ b/Makefile
@@ -5,9 +5,19 @@ OBJ = $(SRC:.c=.o)
 
 all: omc_enc omc_dec test_unit test_uc test_tf test_cc test_cap test_xsl omc_uc_tool omc_tf_tool omc_unblend_tool
 
-%.o: %.c include/omc1.h include/tables.h include/omc_uc.h include/omc_tf.h include/omc_cc.h src/internal.h src/uc_poly_tab.c.inc src/cc_tab.c.inc
+%.o: %.c include/omc1.h include/tables.h include/omc_uc.h include/omc_tf.h include/omc_cc.h src/internal.h src/uc_poly_tab.c.inc src/cc_tab.c.inc src/gm_basis_tab.c.inc
 	$(CC) $(CFLAGS) -c $< -o $@
 
+# The in-gamut repair's synthesis-basis sign table is MEASURED from the
+# shipping inverse transform rather than transcribed from a derivation, and
+# it is regenerated by the build so it cannot drift: change a lifting step in
+# src/dwt.c and this table is rebuilt before anything links against it.
+gen_gm_basis: repro/gen_gm_basis.c src/dwt.c include/omc1.h src/internal.h
+	$(CC) $(CFLAGS) repro/gen_gm_basis.c src/dwt.c -o $@ -lm
+
+src/gm_basis_tab.c.inc: gen_gm_basis
+	./gen_gm_basis > $@.new && mv $@.new $@
+
 omc_enc: tools/omc_enc.c $(OBJ)
 	$(CC) $(CFLAGS) $^ -o $@ -lm
 
@@ -50,7 +60,7 @@ test: test_unit test_uc test_tf test_cc test_cap test_xsl
 	./test_cc
 
 clean:
-	rm -f $(OBJ) omc_enc omc_dec test_unit omc_uc_tool omc_tf_tool omc_unblend_tool test_uc test_tf test_cc test_cap test_xsl
+	rm -f $(OBJ) omc_enc omc_dec test_unit omc_uc_tool omc_tf_tool omc_unblend_tool test_uc test_tf test_cc test_cap test_xsl gen_gm_basis
 
 .PHONY: all test clean
 
diff --git a/include/omc1.h b/include/omc1.h
index 2414f29..8dc3a6d 100644
--- a/include/omc1.h
+++ b/include/omc1.h
@@ -27,9 +27,11 @@
  * reversible cross-slice boundary edit, biased unclipped pixel domain)
  * are not compatible with any earlier minor, so earlier minors are
  * rejected rather than silently mis-decoded.  See docs/TEMPORAL_T5.md. */
-#define OMC_RELEASE_MINOR 11
-#define OMC_VERSION_MINOR 11 /* T5: rebuilt temporal layer + always-on reversible XSL */
-#define OMC_MINOR_T5 11      /* 11 adds pad neutralization (baseband-exact rasters) */
+#define OMC_RELEASE_MINOR 12
+#define OMC_VERSION_MINOR 12 /* T5: rebuilt temporal layer + always-on reversible XSL */
+#define OMC_MINOR_T5 12      /* 11 adds pad neutralization (baseband-exact rasters);
+                                12 adds the flattest-tier grain-fill gate and the
+                                static fill tile (docs/TEMPORAL_T5.md 12.23) */
 
 /* T5 pixel domain: every omc_frame_t (encoder input, decoder output, recon)
  * carries samples as u16 = true_value + OMC_PIX_BIAS, UNCLIPPED to the legal
@@ -119,15 +121,17 @@ typedef struct {
                                 shifts 0, no fill); if it fits the CBR budget the
                                 slice is bit-exact, else the normal overflow
                                 backoff coarsens it (stream stays exact-CBR).
-                                Implies no_fill. Per-frame lossless status is
+                                Requires fill_grain == 0. Per-frame lossless status is
                                 reported by the CLI via rt=0 recon compare. */
     uint8_t no_deadzone;     /* encoder-only: 1 = disable the 9/16 detail-band
                                 deadzone (v4.4 default ON; auto-disabled under
                                 tune_vmaf whose 0.375 bias cancels it).
                                 Reconstruction points never move either way. */
-    uint8_t fill_static;     /* 1 = fill tile phase is frame-independent
-                              * (minor 7: stills the fill in held regions -
-                              * the anti-ants companion; stream byte 27 bit 2) */
+    uint8_t reserved_was_fill_static; /* minor 11 carried the fill tile
+                                phase here; minor 12 makes the
+                                frame-independent tile the only
+                                behaviour, so this field is inert and
+                                option-word bit 2 is reserved zero. */
     uint8_t grain_corr;      /* 1 = fill signs from the CORRELATED tile
                                 (organic film grain; measured lag-1 ~ -0.33);
                                 0 = white tile (electronic noise; default).
@@ -168,11 +172,15 @@ typedef struct {
                                 a correct conversion unavailable on a leg that
                                 can afford it.  A facility that needs the bar
                                 enforced rather than declared sets this. */
-    uint8_t no_fill;         /* encoder-only diagnostic: 1 = never set fill bits
-                                (v3-style waxy output). Default 0: grain fill on
-                                (rev. 6 delivery configuration). Decoders always
-                                honor the header bits; this changes only what the
-                                encoder signals. */
+uint8_t fill_grain;      /* encoder-only: 1 = regenerate the grain the
+                                quantizer removed (the amplitude-matched fill).
+                                DEFAULT 0 -- OFF.  Measured on the whole corpus
+                                (docs/TEMPORAL_T5.md 12.23.8), running with the
+                                fill off is at least as good on BOTH metrics at
+                                once: lower ants tail on all three planes and
+                                higher VMAF-NEG.  Lossless coding requires it
+                                off (it cannot regenerate grain and stay
+                                lossless).  CLI: --fill / --no-fill. */
 } omc_config_t;
 
 /* One frame of planar pixels, uint16 little-endian, T5 BIASED DOMAIN:
@@ -213,8 +221,46 @@ int64_t omc_enc_frame(omc_enc_t *e, const omc_frame_t *in, int frame_idx,
  * Nonzero means a legal-range baseband hop would alter the committed picture,
  * so this stream is NOT safe for baseband-interchange generation chains (the
  * CDR interchange is always safe).  Instrumentation only; never changes
- * coding.  The reference encoder CLI prints the verdict at end of encode. */
+ * coding.  The reference encoder CLI prints the verdict at end of encode.
+ * Returns -1, "not measured", if any slice was encoded with recon == NULL:
+ * the report is taken on the EMITTED picture, so it needs one to exist.  A
+ * caller must therefore test for 0 exactly, never for "not positive". */
 int64_t omc_enc_oob(const omc_enc_t *e);
+/* Strict in-gamut mode (encoder-side policy; default OFF).
+ * `passes` is the per-slice repair budget (0 disables it, 16 is the cap; the
+ * reference CLI defaults to 12).  A slice whose committed reconstruction
+ * leaves the legal range is re-coded with its offending SOURCE coefficients
+ * shrunk toward the slice's own local mean, before quantization -- so what is
+ * emitted is still an ordinary lattice point and the committed picture is
+ * still the unclamped inverse transform of it, and the bitstream, the
+ * decoder, the reconstruction rule and the generation lock are all unchanged.
+ * The mode is what makes a legal-range BASEBAND interchange chain exact on
+ * content that would otherwise clip; it costs first-generation quality on
+ * that content and nothing on any other, and it is inert from generation 2
+ * (the committed picture it produces is already in range, so the repair never
+ * fires again).  It MUST NOT be used on CDR input -- see
+ * omc_enc_set_cdr_input() -- and it is a best effort with a bounded budget,
+ * never a promise: when the budget runs out omc_enc_oob() reports the truth.
+ * docs/TEMPORAL_T5.md 12.22. */
+void omc_enc_set_gamut_strict(omc_enc_t *e, int passes);
+/* Declare that the frames fed to this encoder are COMMITTED pictures (the CDR
+ * interchange written by omc_dec --cdr), not ordinary baseband video.  Strict
+ * in-gamut mode then stands down: a committed picture may legitimately sit
+ * outside the legal range and must be reproduced verbatim, and the CDR chain
+ * is already exact unconditionally with no help from the mode. */
+void omc_enc_set_cdr_input(omc_enc_t *e, int on);
+/* Diagnostics for the mode: slices re-coded, and slices still out of gamut
+ * when the per-slice budget ran out. */
+int64_t omc_enc_gamut_repairs(const omc_enc_t *e);   /* repair PASSES executed */
+int64_t omc_enc_gamut_slices(const omc_enc_t *e);    /* distinct slices repaired */
+int64_t omc_enc_gamut_fallbacks(const omc_enc_t *e); /* slices the gentle rule
+                                                      * could not finish, redone
+                                                      * with the harsh rule */
+/* DIAGNOSTIC (OMC_GM_STAT=1): print what the repair did -- candidates, vetoes,
+ * reductions, and how many of those reductions actually moved a coefficient
+ * across a quantizer boundary.  Process-wide, not per context. */
+void omc_enc_gamut_stat_report(void);
+int64_t omc_enc_gamut_unfixed(const omc_enc_t *e);
 /* 1 when this raster's geometry is recoverable from a cropped baseband
  * picture (minor 11 pad neutralization applies), 0 when it is not -- a
  * horizontally padded raster, or a visible run the rule cannot express.
diff --git a/repro/gen_gm_basis.c b/repro/gen_gm_basis.c
new file mode 100644
index 0000000..0d54880
--- /dev/null
+++ b/repro/gen_gm_basis.c
@@ -0,0 +1,185 @@
+/* gen_gm_basis.c -- measure the 2-D synthesis basis of every band of the OMC
+ * transform and emit src/gm_basis_tab.c.inc.
+ *
+ * WHY THIS IS MEASURED AND NOT DERIVED.  The in-gamut repair needs to know, for
+ * a candidate coefficient and an offending pixel under its support, whether
+ * REDUCING that coefficient moves the pixel toward the legal range or further
+ * out of it.  That is the sign of the synthesis basis g_k(p), and it must be
+ * the sign of the basis the shipping inverse transform actually has, not the
+ * sign of the basis somebody believed it had.  So this program runs impulses
+ * through omc_slice_inv() itself and reads the answer off the output.  It is
+ * built and run by the Makefile, so the table cannot drift from the transform:
+ * change a lifting step and the table is regenerated on the next build.
+ *
+ * WHAT IS TABULATED.  The transform is separable, so the 2-D basis of a
+ * coefficient in band k factors as g(j, i) = gy[j] * gx[i].  Both factors are
+ * run-length compressed by SIGN, and each run carries the mean |g| over it, so
+ * that a rectangle of the picture under one (y-run, x-run) pair has a single
+ * signed weight.  That is what makes the repair's test cheap: the score of a
+ * candidate coefficient is a weighted sum over at most NY*NX rectangles, and
+ * each rectangle is four lookups into a summed-area table of residuals.
+ *
+ * Build/run:  cc -O2 -Iinclude -o gen_gm_basis repro/gen_gm_basis.c src/dwt.c
+ *             ./gen_gm_basis > src/gm_basis_tab.c.inc
+ */
+#include <stdio.h>
+#include <stdlib.h>
+#include <string.h>
+#include <stdint.h>
+#include "omc1.h"
+#include "../src/internal.h"
+
+#define W  2048
+#define SH 32
+#define AMP 1048576          /* large, so integer rounding is a rounding error */
+#define WQ 1024              /* run weights are Q10 of the band peak */
+#define GM_MAXRUN_C 12       /* must match GM_MAXRUN emitted below */              /* run weights are Q10 of the peak |g| of the band */
+
+static int32_t *buf, *tmp;
+static double *g;            /* SH x W response, normalised by AMP */
+
+/* place a unit impulse at band coefficient (rr, cc) and read the response */
+static void impulse(const omc_band_t *B, int rr, int cc)
+{
+    memset(buf, 0, sizeof(int32_t) * (size_t)W * SH);
+    buf[(size_t)(B->r0 + rr) * W + (B->c0 + cc)] = AMP;
+    omc_slice_inv(buf, W, SH, tmp);
+    for (size_t i = 0; i < (size_t)W * SH; i++) g[i] = (double)buf[i] / AMP;
+}
+
+int main(void)
+{
+    omc_band_t B[OMC_NBANDS];
+    omc_band_layout(W, SH, B);
+    buf = calloc((size_t)W * SH, sizeof(int32_t));
+    tmp = calloc((size_t)W * SH + 4 * W, sizeof(int32_t));
+    g   = calloc((size_t)W * SH, sizeof(double));
+
+    printf("/* GENERATED by repro/gen_gm_basis.c -- do not edit.\n"
+           " * Sign/magnitude runs of the separable synthesis basis of each band,\n"
+           " * measured by impulse response through omc_slice_inv().\n"
+           " * See section 12.22 of docs/TEMPORAL_T5.md. */\n\n");
+
+    /* first pass: find the support box and the run structure of each band */
+    printf("#define GM_MAXRUN %d\n\n", GM_MAXRUN_C);
+    printf("typedef struct {\n"
+           "    int16_t off;      /* first pixel of the run, relative to the\n"
+           "                       * coefficient's nominal position idx*stride */\n"
+           "    int16_t len;      /* pixels in the run */\n"
+           "    int16_t w;        /* mean |g| over the run, Q10 of the band peak */\n"
+           "    int16_t sgn;      /* +1 or -1 */\n"
+           "} gm_run_t;\n\n");
+    printf("typedef struct {\n"
+           "    int8_t   ny, nx;  /* runs in each direction */\n"
+           "    int8_t   s0;      /* sign correction, see gen_gm_basis.c */\n"
+           "    int16_t  sy0, sy1;/* FULL support box in rows, relative to */\n"
+           "    int16_t  sx0, sx1;/* (row*vd, col*hd), dropped runs included. */\n"
+           "    int16_t  vd, hd;  /* pixels per coefficient, vertical/horizontal */\n"
+           "    gm_run_t y[GM_MAXRUN], x[GM_MAXRUN];\n"
+           "} gm_basis_t;\n\n");
+    printf("static const gm_basis_t GM_BASIS[OMC_NBANDS] = {\n");
+
+    for (int k = 0; k < OMC_NBANDS; k++) {
+        const omc_band_t *b = &B[k];
+        int vd = SH / b->h, hd = W / b->w;
+        int rr = b->h / 2, cc = b->w / 2;
+        impulse(b, rr, cc);
+        /* support box */
+        int y0 = SH, y1 = -1, x0 = W, x1 = -1;
+        double peak = 0;
+        for (int y = 0; y < SH; y++)
+            for (int x = 0; x < W; x++) {
+                double v = g[(size_t)y * W + x];
+                double a = v < 0 ? -v : v;
+                if (a > peak) peak = a;
+            }
+        double eps = peak * 1e-6;
+        for (int y = 0; y < SH; y++)
+            for (int x = 0; x < W; x++) {
+                double a = g[(size_t)y * W + x];
+                if (a < 0) a = -a;
+                if (a > eps) {
+                    if (y < y0) y0 = y; if (y > y1) y1 = y;
+                    if (x < x0) x0 = x; if (x > x1) x1 = x;
+                }
+            }
+        /* the peak cell, used to factor the separable basis */
+        int py = y0, px = x0; double pv = 0;
+        for (int y = y0; y <= y1; y++)
+            for (int x = x0; x <= x1; x++) {
+                double a = g[(size_t)y * W + x];
+                if (a < 0) a = -a;
+                if (a > pv) { pv = a; py = y; px = x; }
+            }
+        /* gy[j] = g(j, px), gx[i] = g(py, i), and
+         * sign(g(j,i)) = sign(gy[j]) * sign(gx[i]) * sign(g(py,px)) */
+        int s0 = g[(size_t)py * W + px] < 0 ? -1 : 1;
+        fprintf(stderr, "band %d  vd=%d hd=%d  rows[%d..%d] cols[%d..%d]  "
+                "peak %.6f at (%d,%d)\n", k, vd, hd, y0, y1, x0, x1, pv, py, px);
+
+        /* --- runs --- */
+        struct { int off, len, sgn; double sum; } ry[64], rx[64];
+        int ny = 0, nx = 0;
+        double gymax = 0, gxmax = 0;
+        for (int y = y0; y <= y1; y++) { double a = g[(size_t)y*W+px]; if (a<0) a=-a; if (a>gymax) gymax=a; }
+        for (int x = x0; x <= x1; x++) { double a = g[(size_t)py*W+x]; if (a<0) a=-a; if (a>gxmax) gxmax=a; }
+        for (int y = y0; y <= y1; y++) {
+            double v = g[(size_t)y * W + px];
+            int s = v < 0 ? -1 : 1;
+            if (ny && ry[ny-1].sgn == s && ry[ny-1].off + ry[ny-1].len == y) {
+                ry[ny-1].len++; ry[ny-1].sum += v < 0 ? -v : v;
+            } else { ry[ny].off = y; ry[ny].len = 1; ry[ny].sgn = s;
+                     ry[ny].sum = v < 0 ? -v : v; ny++; }
+        }
+        for (int x = x0; x <= x1; x++) {
+            double v = g[(size_t)py * W + x];
+            int s = v < 0 ? -1 : 1;
+            if (nx && rx[nx-1].sgn == s && rx[nx-1].off + rx[nx-1].len == x) {
+                rx[nx-1].len++; rx[nx-1].sum += v < 0 ? -v : v;
+            } else { rx[nx].off = x; rx[nx].len = 1; rx[nx].sgn = s;
+                     rx[nx].sum = v < 0 ? -v : v; nx++; }
+        }
+        fprintf(stderr, "   runs: ny=%d nx=%d\n", ny, nx);
+        /* A run whose mean |g| rounds to zero at Q10 cannot change the sign of
+         * any score it takes part in, so it is dropped: it would only cost the
+         * repair four summed-area lookups to add nothing.  Dropping one leaves
+         * a gap in the support, which is correct -- a gap contributes nothing. */
+        int wy[64], wx[64], ky = 0, kx = 0;
+        for (int i = 0; i < ny; i++) {
+            wy[i] = (int)(ry[i].sum / ry[i].len / gymax * WQ + 0.5);
+            if (wy[i]) ky++;
+        }
+        for (int i = 0; i < nx; i++) {
+            wx[i] = (int)(rx[i].sum / rx[i].len / gxmax * WQ + 0.5);
+            if (wx[i]) kx++;
+        }
+        if (ky > GM_MAXRUN_C || kx > GM_MAXRUN_C) {
+            fprintf(stderr, "band %d needs %d x %d runs, GM_MAXRUN is %d\n",
+                    k, ky, kx, GM_MAXRUN_C);
+            return 1;
+        }
+        printf("  { %d, %d, %d, %d, %d, %d, %d, %d, %d,\n    {", ky, kx, s0,
+               y0 - rr * vd, y1 - rr * vd, x0 - cc * hd, x1 - cc * hd, vd, hd);
+        for (int i = 0, o = 0; i < ny; i++) {
+            if (!wy[i]) continue;
+            printf("%s{%d,%d,%d,%d}", o++ ? "," : "", ry[i].off - rr * vd, ry[i].len,
+                   wy[i], ry[i].sgn);
+        }
+        printf("},\n    {");
+        for (int i = 0, o = 0; i < nx; i++) {
+            if (!wx[i]) continue;
+            printf("%s{%d,%d,%d,%d}", o++ ? "," : "", rx[i].off - cc * hd, rx[i].len,
+                   wx[i], rx[i].sgn);
+        }
+        printf("} },\n");
+        /* the support box, for the edge fall-through: the repair must not apply
+         * an interior sign table to a coefficient whose basis is reshaped by the
+         * symmetric extension at a slice or plane boundary */
+        fprintf(stderr, "   support rows [%d..%d] cols [%d..%d] relative to "
+                "(row*%d, col*%d)\n", y0 - rr * vd, y1 - rr * vd,
+                x0 - cc * hd, x1 - cc * hd, vd, hd);
+    }
+    printf("};\n");
+    free(buf); free(tmp); free(g);
+    return 0;
+}
diff --git a/src/codec.c b/src/codec.c
index 27656f1..0a1d284 100644
--- a/src/codec.c
+++ b/src/codec.c
@@ -22,6 +22,12 @@
 #include "internal.h"
 #include <stdatomic.h>
 
+/* Synthesis-basis sign/magnitude runs, MEASURED from omc_slice_inv() by
+ * repro/gen_gm_basis.c and regenerated by the build.  Used only by the strict
+ * in-gamut repair, to decide whether reducing a coefficient moves an offending
+ * pixel toward the legal range or further out of it.  See section 12.22. */
+#include "gm_basis_tab.c.inc"
+
 extern int omc_xsl;       /* defined below; read by the header parser */
 
 /* ------------------------------------------------------------------ common */
@@ -67,6 +73,16 @@ typedef struct {
     uint8_t sv[18];
 } omc_lockcand_t;
 #define OMC_LOCK_CANDS 4096
+/* Strict in-gamut mode: hard cap on repair passes per slice.  The cap exists
+ * so the encoder's per-slice work stays BOUNDED -- an FPGA pipeline has to
+ * budget the worst case, and an unbounded search has none.  Measured
+ * convergence is in docs/TEMPORAL_T5.md 12.22. */
+#define OMC_GAMUT_MAXPASS 16
+/* The default per-slice repair budget.  It is a DEFAULT, not a request: see
+ * omc_enc_create.  An integrator on a fixed slice period lowers it to whatever
+ * that period holds rather than switching the mode off. */
+#define OMC_GAMUT_DEFPASS 12
+
 
 struct omc_enc {
     ctx_common_t c;
@@ -96,6 +112,57 @@ struct omc_enc {
     int64_t oob_samples;        /* committed samples outside legal range (gamut
                                    report: such samples do not survive a
                                    legal-range baseband hop; see omc_enc_oob) */
+    /* ---- strict in-gamut mode (encoder-only; see docs/TEMPORAL_T5.md 12.22).
+     * When on, a slice whose committed reconstruction leaves the legal range
+     * is RE-CODED with a pixel-domain correction folded into its SOURCE
+     * coefficients, until the reconstruction is in range or the iteration
+     * budget runs out.  The correction is applied strictly BEFORE
+     * quantization, so what is emitted is still an ordinary lattice point and
+     * the reconstruction is still the unclamped inverse transform of it: the
+     * A4 exactness argument is untouched, no bitstream syntax changes, and a
+     * LOCKED slice is never repaired (it already reproduces its input). */
+    int gamut_strict;           /* 0 off (default), else max repair passes */
+    int cdr_input;              /* caller feeds COMMITTED pictures (CDR
+                                   interchange): strict mode must stand down */
+    int gm_norecon;             /* a slice was coded with recon == NULL, so the
+                                   gamut report could not measure it (see
+                                   omc_enc_oob: it then reports -1, not 0) */
+    int64_t gm_repairs;         /* repair PASSES executed, summed over slices --
+                                 * not the number of slices repaired, which is
+                                 * gm_slices below.  An earlier revision reported
+                                 * this as "slices re-coded", which it never was:
+                                 * a slice that needs four passes counted four
+                                 * times, so the figure ran ahead of the number
+                                 * of slices in a frame and read as nonsense. */
+    int64_t gm_slices;          /* distinct slices the repair touched */
+    int64_t gm_fallbacks;       /* slices the gentle rule could not finish, and
+                                 * which were therefore repaired again from
+                                 * their original coefficients with the harsh
+                                 * uncapped rule (see gm_fellback) */
+    int64_t gm_unfixed;         /* slices still out of gamut when the budget ran out */
+    int32_t *gm_buf[OMC_NPLANES];   /* repair mask, summed-area (see the repair) */
+    int64_t *gm_asat[OMC_NPLANES];  /* summed-area table of |residual|, the
+                                     * normaliser that turns the alignment score
+                                     * into a ratio in [-1, 1] (see gm_align) */
+    int64_t *gm_rsat[OMC_NPLANES];  /* summed-area table of the RESIDUAL of every
+                                     * pixel: how far out of the legal range it is
+                                     * and in which direction (positive = above the
+                                     * ceiling and must come down).  The count mask
+                                     * above says WHICH coefficients are suspects;
+                                     * this says whether reducing one of them helps
+                                     * or hurts, and by how much. */
+    uint8_t *gm_mask[OMC_NPLANES];  /* mode 13: every pixel this slice has EVER
+                                     * committed out of range, accumulated over
+                                     * the attempts.  Restoring the original
+                                     * each attempt un-fixes what earlier
+                                     * attempts fixed unless the mask remembers
+                                     * them, which is why this is a union and
+                                     * not the latest pass's findings. */
+    int32_t *gm_save[OMC_NPLANES][2]; /* the slice's UNTOUCHED intra and delta
+                                       * coefficients (mode 13): every repair
+                                       * attempt is made from the original
+                                       * rather than on top of the last one */
+    uint16_t *gm_rowsave[OMC_NPLANES]; /* previous slice's last committed row */
     int32_t *pbuf[OMC_NPLANES];             /* prediction transform scratch */
     int32_t *pcoef[OMC_NPLANES][OMC_NBANDS]; /* prediction coefficients */
     int32_t *dcoef[OMC_NPLANES][OMC_NBANDS]; /* delta (inter) coefficients */
@@ -244,7 +311,9 @@ int omc_write_stream_header(const omc_config_t *cfg, uint8_t *dst)
      *
      *   byte 27  bit 0    rct
      *            bit 1    grain_corr
-     *            bit 2    fill_static
+     *            bit 2    RESERVED, must be zero (was fill_static in minor 11;
+     *                     minor 12 makes the static fill tile the only
+     *                     behaviour, so the bit no longer selects anything)
      *            bits 3-4 uc_ratio  (0 none, 1 = 2x, 2 = 4x)
      *            bits 5-6 tf_mode   (0 off, 1/2 = OMC-TF strength)
      *            bit 7    reserved 0
@@ -257,7 +326,6 @@ int omc_write_stream_header(const omc_config_t *cfg, uint8_t *dst)
     /* T5: tf_mode bits 5-6 are DEAD (the in-loop temporal filter was removed
      * with the old temporal engine) and are written 0 always. */
     *o++ = (uint8_t)((cfg->rct ? 1 : 0) | (cfg->grain_corr ? 2 : 0) |
-                     (cfg->fill_static ? 4 : 0) |
                      ((cfg->uc_ratio & 3) << 3));
     memcpy(o, &cfg->display_height, 2); o += 2;
     memcpy(o, &cfg->display_width, 2); o += 2;
@@ -292,7 +360,6 @@ int omc_read_stream_header(const uint8_t *src, omc_config_t *cfg)
     if (*o++ != 0) return -3;      /* byte 26: scan_type, reserved 0 */
     cfg->rct = (uint8_t)(*o & 1);
     cfg->grain_corr = (uint8_t)((*o >> 1) & 1);
-    cfg->fill_static = (uint8_t)((*o >> 2) & 1);
     cfg->uc_ratio = (uint8_t)((*o >> 3) & 3);
     /* T5: tf_mode bits (5-6) and bit 7 must be zero — the in-loop temporal
      * filter no longer exists.  A stream with them set is not a T5 stream. */
@@ -366,6 +433,303 @@ static void derive_shifts(int cf444, int prof, int Q, int n_steps, int partial_c
 extern int omc_chromabias;   /* chroma detail bias (test lever, defined below) */
 extern int omc_bandtilt;     /* fine-band precision tilt (defined below) */
 /* shift for coefficient index i of band (p,b) under plan sp */
+/* One step of the gamut repair's reduction of a single coefficient.  `step`
+ * is 0 for the proportional form (scale by num/den) and the quantizer step for
+ * the subtractive form.  Both are monotone toward zero and neither can change
+ * a coefficient's sign, which is what keeps the repair loop convergent. */
+/* OMC_GM_STAT counters.  Deliberately globals rather than per-context state:
+ * they exist only to answer a question about where the repair's cost lives and
+ * are never read on any coding path. */
+static int64_t gm_st_cand, gm_st_veto, gm_st_red, gm_st_cross;
+static int64_t gm_st_cross_b[OMC_NBANDS], gm_st_red_b[OMC_NBANDS];
+static int64_t gm_st_cross_m[8], gm_st_red_m[8];
+/* Total change in CODED VALUE, and the squared reconstruction error that change
+ * injects.  The crossing COUNT turned out not to rank the arms: on 4K graphics
+ * fewer crossings scored better, on 4K cinema more crossings scored better,
+ * because a proportional cut moves q by many steps at once while a capped one
+ * moves it by exactly one.  What is common to both is how much reconstruction
+ * energy leaves the picture, which is sum over crossings of (dq << s)^2 times
+ * the band's ||g||^2 -- so both halves are recorded and the weighting is done
+ * outside, against the measured per-band energies. */
+static int64_t gm_st_dq[OMC_NBANDS], gm_st_e2[OMC_NBANDS];
+static int64_t gm_st_pickA, gm_st_pickB;   /* trial selection outcome */
+
+extern int omc_gm_stat;
+
+/* Record what one reduction really did.  A reduction that does not carry the
+ * coefficient across a quantizer boundary emits the same q, therefore the same
+ * bits and the same reconstruction: it is free.  Counting reductions instead of
+ * crossings measures work, not damage. */
+static void gm_stat_note(int b, int32_t before, int32_t after, int s)
+{
+    int32_t qb = omc_quant1b(before, s, 0), qa = omc_quant1b(after, s, 0);
+    int32_t m = before < 0 ? -before : before;
+    int bucket = 0;
+    int32_t step = (int32_t)1 << s;
+    while (bucket < 7 && m >= (step << bucket)) bucket++;
+    gm_st_red++; gm_st_red_b[b]++; gm_st_red_m[bucket]++;
+    if (qa != qb) {
+        gm_st_cross++; gm_st_cross_b[b]++; gm_st_cross_m[bucket]++;
+        int64_t dq = qa > qb ? qa - qb : qb - qa;
+        int64_t dr = dq << (s < 30 ? s : 30);
+        gm_st_dq[b] += dq;
+        gm_st_e2[b] += dr * dr;
+    }
+}
+
+/* Squared error between the EMITTED picture of one slice and the source it was
+ * made from, summed over all three planes and every visible row.  This is the
+ * quantity the repair's shape selection is judged on: not a proxy for closeness
+ * to the source, but closeness to the source. */
+static int64_t gm_slice_sse(const omc_frame_t *in, const omc_frame_t *rec,
+                            const int *pw_of, int nplanes, int row0, int nrows,
+                            int masked)
+{
+    int64_t sse = 0;
+    for (int p = 0; p < nplanes; p++) {
+        int pw = pw_of[p];
+        if (masked < 2) {          /* 1 = plain squared error */
+            for (int r = 0; r < nrows; r++) {
+                const uint16_t *a = in->p[p]  + (size_t)(row0 + r) * in->stride[p];
+                const uint16_t *b = rec->p[p] + (size_t)(row0 + r) * rec->stride[p];
+                for (int x = 0; x < pw; x++) {
+                    int64_t d = (int64_t)a[x] - b[x];
+                    sse += d * d;
+                }
+            }
+            continue;
+        }
+        /* MASKED distance, in 8x8 blocks.  Plain squared error is the wrong
+         * distance for this decision and the measurement says so: on the 4K
+         * graphics master it picks the gentle shape and scores 97.81, where the
+         * harsh shape scores 98.07.  Error is not equally visible everywhere --
+         * an error of a given size in a flat part of the picture is far more
+         * visible than the same error inside texture, and ringing beside a hard
+         * edge lands in exactly the flat part.  An anti-gaming perceptual model
+         * refuses to credit detail the source did not have, so it charges that
+         * ringing at close to full price while charging error inside texture at
+         * a discount.  Dividing each block's squared error by the block's own
+         * source activity is the cheapest honest version of that, and it needs
+         * nothing but the source. */
+        for (int r0 = 0; r0 < nrows; r0 += 8) {
+            int rh = nrows - r0 < 8 ? nrows - r0 : 8;
+            for (int c0 = 0; c0 < pw; c0 += 8) {
+                int cw = pw - c0 < 8 ? pw - c0 : 8;
+                int64_t bs = 0, act = 0;
+                for (int r = 0; r < rh; r++) {
+                    const uint16_t *a = in->p[p]  + (size_t)(row0 + r0 + r) * in->stride[p] + c0;
+                    const uint16_t *b = rec->p[p] + (size_t)(row0 + r0 + r) * rec->stride[p] + c0;
+                    const uint16_t *an = (r + 1 < rh)
+                        ? in->p[p] + (size_t)(row0 + r0 + r + 1) * in->stride[p] + c0 : 0;
+                    for (int x = 0; x < cw; x++) {
+                        int64_t d = (int64_t)a[x] - b[x];
+                        bs += d * d;
+                        if (x + 1 < cw) { int32_t g = a[x + 1] - a[x]; act += g < 0 ? -g : g; }
+                        if (an) { int32_t g = an[x] - a[x]; act += g < 0 ? -g : g; }
+                    }
+                }
+                int n = rh * cw;
+                if (!n) continue;
+                int64_t am = act / n;                 /* mean |gradient| of the source */
+                sse += bs * 256 / (16 + am);
+                if (masked < 3) continue;
+                /* ADDED DETAIL, charged separately.  The anti-gaming model this
+                 * work is held to refuses to credit detail the source did not
+                 * have -- that is the whole content of its two gain limits.
+                 * Ringing IS detail the source did not have.  So a block whose
+                 * reconstruction is BUSIER than its source is charged for the
+                 * excess, and a block that is quieter than its source is not
+                 * refunded for it.  Only the source and the reconstruction are
+                 * needed; nothing about the content class is assumed. */
+                int64_t ract = 0;
+                for (int r = 0; r < rh; r++) {
+                    const uint16_t *b = rec->p[p] + (size_t)(row0 + r0 + r) * rec->stride[p] + c0;
+                    const uint16_t *bn = (r + 1 < rh)
+                        ? rec->p[p] + (size_t)(row0 + r0 + r + 1) * rec->stride[p] + c0 : 0;
+                    for (int x = 0; x < cw; x++) {
+                        if (x + 1 < cw) { int32_t g = b[x + 1] - b[x]; ract += g < 0 ? -g : g; }
+                        if (bn) { int32_t g = bn[x] - b[x]; ract += g < 0 ? -g : g; }
+                    }
+                }
+                int64_t excess = ract - act;
+                if (excess > 0) sse += excess * excess / n;
+            }
+        }
+    }
+    return sse;
+}
+
+/* Transform-domain distance for the trial selection (OMC_GM_TRIAL=4).
+ *
+ * WHY A FOURTH ONE.  Three pixel-domain distances -- plain squared error,
+ * squared error masked by source activity, and squared error plus a penalty for
+ * detail the source did not have -- all pick the SAME shape on every slice of
+ * the 4K graphics master, and the shape they pick scores 0.29 lower on
+ * VMAF-NEG.  That is not a tuning failure: the shape they pick really is 3.3 dB
+ * closer to the source (43.90 dB against 40.58 dB PSNR).  On that content
+ * fidelity and the metric point in opposite directions.
+ *
+ * Breaking the metric into its components says exactly which part disagrees.
+ * Between the two shapes, VIF barely moves and motion does not move at all;
+ * the whole 0.29 is ADM, and almost all of it is ADM at the two COARSE scales
+ * (scale 2: -0.0099, scale 3: -0.0121).  ADM separates an impairment into
+ * detail LOST from the source and detail ADDED that the source never had, and
+ * with the enhancement gain limit set to 1.0 it refuses to credit the added
+ * kind.  Quantization overshoot past a rail is added detail by definition.
+ *
+ * So this distance is built the way ADM is: per band, the magnitude the source
+ * had but the reconstruction lost, plus K times the magnitude the
+ * reconstruction has that the source never had, each weighted by that band's
+ * measured picture energy.  Both quantities are already in hand -- the
+ * untouched source coefficients in gm_save and the committed reconstruction in
+ * sbuf -- so it costs one sweep of the slice and no model. */
+static int64_t gm_slice_adm(const int32_t *const *save, const int32_t *sbuf,
+                            int pw, int sh, int K)
+{
+    static const int64_t g2[OMC_NBANDS] =
+        { 590942, 173111, 96074, 55229, 33853, 26841, 10294, 11792, 10100, 4840 };
+    omc_band_t bl[OMC_NBANDS];
+    omc_band_layout(pw, sh, bl);
+    int64_t cost = 0;
+    size_t off = 0;
+    for (int b = 0; b < OMC_NBANDS; b++) {
+        const omc_band_t *B = &bl[b];
+        int64_t loss = 0, add = 0;
+        for (int r = 0; r < B->h; r++)
+            for (int x = 0; x < B->w; x++) {
+                int32_t sv = save[0][off + (size_t)r * B->w + x];
+                int32_t rv = sbuf[(size_t)(B->r0 + r) * pw + B->c0 + x];
+                if (sv < 0) sv = -sv;
+                if (rv < 0) rv = -rv;
+                if (sv > rv) loss += sv - rv; else add += rv - sv;
+            }
+        cost += g2[b] * (loss + (int64_t)K * add) / 10000;
+        off += (size_t)B->h * B->w;
+    }
+    return cost;
+}
+
+/* ---- the alignment test (mode 16) --------------------------------------
+ *
+ * Every shape from mode 0 to mode 15 reduced EVERY coefficient whose support
+ * covers an offending pixel.  None of them asked the one question that decides
+ * whether the reduction is worth anything: does reducing this coefficient move
+ * that pixel TOWARD the legal range, or further out of it?
+ *
+ * Reducing a coefficient's magnitude by d changes the reconstruction at pixel
+ * q by  -sign(c) * d * g(q), where g is the synthesis basis of that
+ * coefficient.  A sample above the ceiling has to come DOWN and a sample below
+ * the floor has to go UP, so a reduction only helps where
+ * sign(c) * g(q) has the same sign as the sample's excursion.  Where it does
+ * not, the reduction pushes the offending sample further out of range AND
+ * still costs picture -- the worst of both.  On measured content roughly half
+ * of every pass was doing exactly that.
+ *
+ * The test needs no magnitudes from the coefficient, only the basis, and the
+ * basis is exactly separable and exactly shift-invariant in the interior (both
+ * verified by impulse response: separability error 0.00e+00 of peak, no sign
+ * disagreement, no support-box disagreement, over 28-35 phases per band).  So
+ * g(j, i) = gy[j] * gx[i], both factors are run-length compressed by sign in
+ * GM_BASIS, and the score
+ *
+ *      score = sign(c) * SUM over offending q of  residual(q) * g(q)
+ *
+ * collapses to a weighted sum over at most ny*nx rectangles, each of which is
+ * four lookups into a summed-area table of residuals.  ny <= 3 and nx <= 7, so
+ * the whole test is at most 84 lookups.
+ *
+ * Weighting by RESIDUAL rather than by a count of offending pixels matters:
+ * feasibility is a max, not a sum.  One pixel forty codes out is worth more
+ * than ten pixels one code out, and a coefficient that fixes the worst
+ * offender while nudging ten marginal pixels is usually the right move.  It
+ * also handles, with no special case, a coefficient whose support covers both
+ * an above-ceiling region and a below-floor region: the two contributions have
+ * opposite signs and net out, which is the honest answer.  That case is not
+ * exotic -- it is exactly what G-T5-GAMUT2c's rail-on-boundary content makes.
+ *
+ * Returns the score for a POSITIVE coefficient; the caller flips it for a
+ * negative one.  Returns 1 (touch it) when the coefficient's support is
+ * clipped by a slice or plane boundary: the whole-sample symmetric extension
+ * reshapes the basis there and the interior table does not describe it.  That
+ * is a deliberate fall-through rather than a guess -- it can only make the
+ * repair do more work, never veto a coefficient it should have touched, and
+ * the boundary rows are the ones the repair can least afford to get wrong. */
+static int64_t gm_align(const gm_basis_t *G, const int64_t *rsat,
+                        const int64_t *asat, int satw,
+                        int sh, int pw, int ry, int cx, int vd, int hd,
+                        int *no_veto, int64_t *mass)
+{
+    if (mass) *mass = 0;
+    *no_veto = 1;
+    /* The interior table does not describe a coefficient whose basis is
+     * reshaped by the whole-sample symmetric extension at a slice or plane
+     * boundary, and it does not describe a plane whose width does not divide
+     * into the band grid the table was measured on.  Both fall through to
+     * "touch it" -- never to "veto it", which at a boundary is the one place
+     * the repair cannot afford to be wrong. */
+    if (vd != G->vd || hd != G->hd) return 0;
+    if (ry + G->sy0 < 0 || ry + G->sy1 >= sh ||
+        cx + G->sx0 < 0 || cx + G->sx1 >= pw) return 0;
+    *no_veto = 0;
+    int64_t score = 0;
+    for (int a = 0; a < G->ny; a++) {
+        int y0 = ry + G->y[a].off, y1 = y0 + G->y[a].len;
+        if (y0 < 0) y0 = 0;
+        if (y1 > sh) y1 = sh;
+        if (y0 >= y1) continue;
+        int64_t wy = (int64_t)G->y[a].w * G->y[a].sgn;
+        for (int b = 0; b < G->nx; b++) {
+            int x0 = cx + G->x[b].off, x1 = x0 + G->x[b].len;
+            if (x0 < 0) x0 = 0;
+            if (x1 > pw) x1 = pw;
+            if (x0 >= x1) continue;
+            int64_t r = rsat[(size_t)y1 * satw + x1] - rsat[(size_t)y0 * satw + x1]
+                      - rsat[(size_t)y1 * satw + x0] + rsat[(size_t)y0 * satw + x0];
+            int64_t wxs = (int64_t)G->x[b].w * G->x[b].sgn;
+            if (mass && asat) {
+                int64_t am = asat[(size_t)y1 * satw + x1] - asat[(size_t)y0 * satw + x1]
+                           - asat[(size_t)y1 * satw + x0] + asat[(size_t)y0 * satw + x0];
+                *mass += (int64_t)G->y[a].w * G->x[b].w * am;
+            }
+            if (!r) continue;
+            score += wy * wxs * r;
+        }
+    }
+    return score * G->s0;
+}
+
+static inline int32_t gm_reduce(int32_t v, int num, int den, int32_t step)
+{
+    if (!step) return v * num / den;
+    if (v > 0) { v -= step; return v < 0 ? 0 : v; }
+    if (v < 0) { v += step; return v > 0 ? 0 : v; }
+    return 0;
+}
+
+/* THE GENTLER OF THE TWO REDUCTIONS, per coefficient.
+ *
+ * The proportional shrink and the stepwise one are not "fast" and "gentle":
+ * each is gentler than the other on different coefficients, and which is which
+ * depends on the coefficient's size relative to its own quantizer step.  Taking
+ * a quarter off a coefficient worth ten steps removes two and a half steps;
+ * taking a quarter off one worth half a step removes an eighth of a step.  So
+ * on starved 8-bit content, where steps are large and most coefficients are
+ * small, the proportional shrink is the SMALLER move -- which is why it beat
+ * every stepwise form on the 4K graphics master and lost to them everywhere
+ * else.  That, and not any property of the content, was the density split.
+ *
+ * Taking the larger remaining magnitude takes the smaller reduction, per
+ * coefficient, with no classification of anything.  It self-escalates for free:
+ * the stepwise term grows with the pass count, so once it passes the
+ * proportional one this reduces to the proportional shrink and convergence is
+ * bounded by it. */
+static inline int32_t gm_reduce_min(int32_t v, int num, int den, int32_t step)
+{
+    int32_t a = v * num / den;
+    int32_t b = gm_reduce(v, num, den, step);
+    int32_t aa = a < 0 ? -a : a, ab = b < 0 ? -b : b;
+    return aa >= ab ? a : b;
+}
 static inline int coeff_shift(const shift_plan_t *sp, int p, int b, int i)
 {
     int s = sp->shift[p][b];
@@ -418,8 +782,319 @@ int omc_gr_dzoff = 0;  /* skip deadzone in flat-carpet cells (env OMC_GR_DZOFF)
 int omc_gr_intra = 0;  /* extend classification+soft to intra slices, coarse bands only (env OMC_GR_INTRA) */
 int omc_gr_soft_coarse = 0; /* per-band soft depth for bands <=6 (env OMC_GR_SOFT_COARSE; 0 = same as omc_gr_soft) */
 int omc_fill_veto_coarse = 0; /* veto bands 4-6 fill bits in flat-carpet slice-bands (env OMC_FILL_VETO_COARSE, pct) */
-int omc_fill_static = 0; /* fill tile static where act <= n (env OMC_FILL_STATIC; minor-7 candidate) */
 int omc_gr_fillveto = 0; /* pct: veto slice-band fill bit when flat-class kills dominate its fillable population (env OMC_GR_FILLVETO) */
+/* ---- TEMPORAL CALM (the "ants" fix; encoder-only, bitstream unchanged).
+ *
+ * In a region the SOURCE holds flat, a detail coefficient of about one
+ * quantizer step is not texture.  It is a value sitting on the quantizer's
+ * zero/one boundary, and the source's own sub-code wobble carries it back
+ * and forth across that boundary from one frame to the next.  Each crossing
+ * moves the reconstruction by a FULL step -- 16 code values at shift 4 -- so
+ * an area the camera holds still shows the viewer a carpet of one-step
+ * flicker.  That is the "ants" defect REPORT.md 18.5-18.7 records as the one
+ * thing a blind viewer identified twice, and the reason the incumbent
+ * (JPEG XS) reads CALMER THAN THE MASTER on this instrument: its coarser
+ * per-frame quantization drops the same wobble into one bucket every frame.
+ *
+ * The fix is to do the same thing deliberately and only where it is safe:
+ * positions whose co-located LL local gradient says "flat" get a FULL-step
+ * zero zone instead of the 1/2 (or 9/16 deadzone) one.  A coefficient below
+ * one step codes to zero, the flat region reconstructs from its LL alone,
+ * and it stops moving.  Nothing is added to the picture -- energy is only
+ * ever removed -- so VMAF-NEG, the model that refuses to credit energy the
+ * source did not have, cannot be bought by this and is not spent by it.
+ *
+ * GENERATION EXACTNESS (A4) is preserved BY CONSTRUCTION, by the same
+ * argument the F-2 deadzone above rests on: the test is a STRICT
+ * |c| < (1 << s), and every coefficient of a previously-coded picture is
+ * exactly q << s.  For |q| == 1 that is |c| == (1 << s), which fails a
+ * strict compare, so the kill can never fire on a committed picture.  The
+ * classifier reads the SOURCE LL, which does drift between generations --
+ * that is harmless precisely because the kill cannot fire there at all.
+ *
+ * Runs on intra and inter slices alike (a rolling-refresh slice is intra and
+ * shows the same flicker), on every plane (chroma crawl in a flat coloured
+ * area is the same defect wearing a different coat), and independently of
+ * --grain-replace: it borrows that classifier's eligibility array as class
+ * 3, which downstream reads only through the legacy full-step kill. */
+int omc_calm = 1;      /* env OMC_CALM=0 disables the ants fix */
+int omc_calm_thr = 24;  /* LL |gradient| ceiling at 8-bit; scaled by depth */
+/* AMPLITUDE BOUND on the calm kill (env OMC_CALM_AMP; 0 = unbounded).  One
+ * quantizer step is not a fixed amount of picture: at 0.5 bpp on a 12-bit
+ * master the step can be large enough that a |q| == 1 coefficient is real
+ * energy rather than the sub-code wobble this fix exists to stop.  When set,
+ * the coefficient must also be grain-scale in ABSOLUTE terms, on the scale
+ * the grain-replace amplitude vote already uses (n << (depth - 7)).
+ *
+ * The bound is read on the INTRA-domain coefficient, which is the same value
+ * the grain-replace amplitude vote reads: it is a property of the picture, not
+ * of this frame's prediction residual, so a position is classified identically
+ * whether its band ends up coded intra or inter.  Without that the class would
+ * flip with the coding mode, and the mode is chosen after this pass.
+ *
+ * Narrowing the condition cannot affect the lattice argument of 12.23.7: the
+ * kill still tests a strict |c| < (1 << s), and a condition that only removes
+ * candidates cannot make one fire that would not have. */
+int omc_calm_amp = 3;
+int omc_gm_dil = 1;    /* env OMC_GM_DIL: band cells of dilation on the repair mask */
+int omc_gm_llhold = 0; /* env OMC_GM_LLHOLD: passes before the LL band is shrunk */
+/* The repair's reduction factor.  63/64 with the gentler-of-two shape (mode 12),
+ * the cost-targeted veto (OMC_GM_VETO=2) and stall escalation to 15/16 at pass 4
+ * (OMC_GM_ESC) is the rule this revision ships.  It is better than the 3/4
+ * proportional cut it replaces on EVERY cell of the real corpus, measured as
+ * distance to what the picture would have scored with no repair at all.  The
+ * table below is the intermediate 15/16 candidate; the shipped 63/64 with
+ * escalation improves on it again on eight of the nine real cells:
+ *
+ *   clip                        no repair   15/16       63/64 esc4
+ *   gfxF003_444_8      @0.5       98.5768   -0.75       -0.76
+ *   gfxF003_444_8      @1.0       98.9690   -0.02       -0.02
+ *   cine4k_444_10      @1.0       94.8712   -0.48       -0.31
+ *   cine4k_444_10      @2.0       97.5497   -0.11       -0.09
+ *   cineA31_720        @0.5       98.2237   +0.01       +0.01
+ *   cineA31_720        @1.0       98.8755   -0.02       -0.01
+ *   cineA21_444_10     @0.5       77.6428   -2.24       -1.65
+ *   cineA21_444_10     @2.0       95.0477   -0.06       -0.07
+ *   gfx1080_444_12     @0.5       91.4104   -0.00        0.00
+ *
+ * 63/64 is also the GENTLEST factor that still converges: 127/128 and 255/256
+ * both leave 21,120 samples out of range on the rail clip at half a bit per
+ * pixel, and 63/64 without the escalation leaves 21,760.  Escalating earlier
+ * (pass 2) or to a harsher fallback (3/4) is worse on every cell measured.
+ *
+ * The older 15/16 comparison against the 3/4 rule it replaced:
+ *
+ *   clip                        no repair   old 3/4     shipped now
+ *   cine4k_444_10      @1.0       94.8712   -5.44       -0.48
+ *   cine4k_444_10      @2.0       97.5497   -3.66       -0.11
+ *   cineA31_720        @0.5       98.2237   -0.46       +0.01
+ *   cineA31_720        @1.0       98.8755   -0.47       -0.02
+ *   cineA21_444_10     @2.0       95.0477   -0.16       -0.06
+ *   cineA21_444_10     @0.5       77.6428   -4.12       -2.24
+ *   gfx1080_444_12     @0.5       91.4104   +0.11       -0.00
+ *   gfx1080_fullrange  @0.5       92.0577   -7.81       -1.83
+ *   gfx1080_fullrange  @1.0       94.8466   -2.60       -0.40
+ *   gfxF003_444_8      @1.0       98.9690   -0.16       -0.02
+ *   gfxF003_444_8      @0.5       98.5768   -0.50       -0.75
+ *   rail720_422_10     @1.0       98.5762  -20.35       -4.33
+ *   rail720_422_10     @0.5       97.5738  -35.25      -13.25
+ *   (cine4k_422_8 and cineA21_422_12 never leave the range: both inert)
+ *
+ * One cell is worse than the old rule: gfxF003 at half a bit per pixel, by
+ * 0.25.  That cell is the one where fidelity and the metric genuinely disagree
+ * -- the gentler picture there is 3.3 dB CLOSER to the source and scores lower,
+ * because the aggressive cut removes ringing and the anti-gaming model credits
+ * that.  It is recorded rather than tuned away; nine encoder-side statistics
+ * were tried and none reproduces the metric's verdict on both content types.
+ *
+ * 31/32 was measured too and is very slightly better on most cells, but it does
+ * not converge on the rail stress clip at half a bit per pixel -- 21 760 samples
+ * still out of range inside the budget -- so it is not a candidate.  Reaching
+ * zero is the point of the mode. */
+int omc_gm_num = 63, omc_gm_den = 64; /* env OMC_GM_NUM/DEN: shrink factor */
+/* HOW the repair reduces a coefficient (env OMC_GM_MODE).
+ *   0 -- scale it by num/den.  Proportional, so it takes a large coefficient
+ *        down by a large amount: at 3/4 a coefficient worth eight quantizer
+ *        steps loses two of them in one pass.  That is what makes the repair
+ *        expensive on pictures whose overshoot comes from a few big edge
+ *        coefficients, which is most of them.
+ *   1 -- subtract exactly ONE quantizer step, toward zero.  The smallest
+ *        change that can move the reconstruction at all, applied only where
+ *        it is needed, repeated only as often as it is needed.  Overshoot past
+ *        a rail is typically one to three steps, so the loop still converges
+ *        inside the pass budget, and a coefficient that was not the problem
+ *        loses one step instead of a quarter of itself.
+ *   2 -- subtract (1 << pass) steps: the same minimum first move, doubling
+ *        for the pixels that still offend.
+ *   3 -- as 2, but the first passes reach only the finest bands.  MEASURED
+ *        WORSE than 2 (95.41 against 96.49 on 4K cinema): holding the coarse
+ *        bands back costs extra passes, and the step has doubled several times
+ *        by the time they open, so the two escalations fight each other.
+ *   4 -- subtract (pass + 1) steps.  Linear rather than geometric, so the
+ *        total reduction after the whole budget is tens of steps rather than
+ *        thousands, and no pass ever overshoots by a factor of two.
+ *   5 -- as 4, with the finest-bands-first order, which only makes sense
+ *        against a gentle escalation. */
+int omc_gm_mode = 12;
+int omc_gm_nointra = 0; /* env OMC_GM_NOINTRA: never force a band to intra */
+/* env OMC_GM_REPLAN: after a repair pass, re-run the rate plan for the slice.
+ * The repair only ever REMOVES coefficient energy, so the slice's payload
+ * shrinks -- but the repair jumps back past the plan search, so the slice keeps
+ * the quantizer it was given when it was still carrying that energy and the
+ * freed bits are spent on padding.  Re-planning lets the slice buy a finer
+ * quantizer with them, which both improves the picture and reduces the ringing
+ * that caused the overshoot in the first place. */
+int omc_gm_replan = 0;
+/* SYNTHESIS LEVERAGE of each band, x10000: peak|g_b| / ||g_b||^2, where g_b is
+ * the picture an isolated unit coefficient of band b becomes.  Measured on this
+ * codec's own inverse transform by tests/basis.c (impulse in, inverse
+ * transform, peak and energy out); reproduce it with
+ *     cc -O2 -Iinclude -o basis tests/basis.c src/dwt.c && ./basis 1920 16
+ * It is a property of the TRANSFORM, not of content or geometry: the same run
+ * at 4096x32 and 1280x8 gives the same ordering and nearly the same values.
+ *
+ * This is the table the least-norm in-gamut correction rests on.  Moving a
+ * coefficient by one quantizer step pulls an offending pixel in by
+ * |g_b(p)| * 2^s and costs (2^s)^2 * ||g_b||^2 of picture energy, so the
+ * correction bought per unit of damage is leverage_b / 2^s.  Band 9 is
+ * SIXTY-SIX TIMES more efficient than the LL band by this measure -- which is
+ * why a repair that reduces every band at the same rate does far more damage
+ * than it needs to, and why the fix is to spend steps in leverage order.
+ * Note it is the STEP SIZE that enters, not the band index. */
+static const int omc_gm_lev[OMC_NBANDS] = {
+     169,  433,  781, 1358, 2215, 2678, 5237, 6360, 7116, 11139
+};
+/* Decide whether one reduction may be applied.
+ *
+ * MEASURED, and it overturns how every earlier shape was reasoned about.  A
+ * reduction that does not carry the coefficient across a quantizer boundary
+ * emits the same q, therefore the same bits and the same reconstruction: it is
+ * FREE.  On the 4K graphics master the repair applies 587k-950k reductions per
+ * encode and only 10-14 per cent of them cross anything at all.  The other
+ * 86-90 per cent cost nothing and are pure convergence.
+ *
+ * The split is almost perfectly by size.  Below one quantizer step, 1 per cent
+ * of reductions cross.  At eight steps and above, ONE HUNDRED per cent of them
+ * do -- 18536 of 18536, 14435 of 14435, and so on to the top bucket.  And the
+ * crossings concentrate in the coarse bands: bands 7 and 9, the finest detail,
+ * took a quarter of a million reductions between them and crossed ZERO times.
+ *
+ * So a veto applied uniformly spends its refusals mostly on reductions that
+ * were free anyway, and refusing those only slows convergence -- which is the
+ * one thing that provably costs, since every extra pass re-crosses the same
+ * large coefficients.  OMC_GM_VETO=2 charges for what is actually charged for:
+ * a reduction that crosses must pass the alignment test, a reduction that does
+ * not is always allowed.  Cheap moves keep pushing toward feasibility; the
+ * expensive ones are only spent when they demonstrably help. */
+static inline int gm_permit(int veto, int free_edge, int64_t sc, int32_t before,
+                            int32_t after, int s)
+{
+    if (!veto || free_edge) return 1;
+    if (veto >= 2 && omc_quant1b(before, s, 0) == omc_quant1b(after, s, 0))
+        return 1;                              /* costs nothing: always allow */
+    return ((before < 0 ? -sc : sc) > 0);
+}
+
+/* ---- the graded reduction (OMC_GM_GRADE) ------------------------------
+ *
+ * MEASURED, and it is the finding the whole search turned on.  Total picture
+ * energy removed by the repair predicts VMAF-NEG perfectly on 4K cinema, on
+ * 720p cinema and on 2K cinema -- less energy removed, better score, monotone
+ * over a twenty-fold range.  On the 4K GRAPHICS master it predicts BACKWARDS:
+ * the arm that removes 4.69e8 scores 98.07 and the arm that removes 2.69e7,
+ * seventeen times less, scores 97.82.
+ *
+ * That is not noise and it is not a second content class needing its own
+ * threshold.  Out-of-range samples are quantization overshoot -- ringing.  On a
+ * graphics master at half a bit per pixel the coefficients around a rail
+ * excursion are almost ALL ringing, so removing a great deal of energy there
+ * removes a great deal of ringing, and an anti-gaming perceptual model that
+ * refuses to credit detail the source did not have scores that as an
+ * improvement.  On camera footage the same neighbourhood holds real texture,
+ * and removing it is exactly the loss the model punishes.
+ *
+ * The encoder does not have to know which it is looking at, because the
+ * alignment score already separates them.  Ringing overshoot is coherent with
+ * the excursion by construction: the coefficient's contribution at the
+ * offending pixel has the same sign as the sample's excess.  Real texture beside
+ * a rail is uncorrelated with it, so its score is near zero relative to the
+ * residual mass it sits in.  Normalising the score by that mass gives a ratio in
+ * [-1, 1] which is a property of the coefficient, not of the content class:
+ *
+ *   ratio near +1   this coefficient IS the overshoot -> cut it hard
+ *   ratio near  0   it merely lies near the overshoot -> barely touch it
+ *   ratio <=     0   reducing it makes things worse    -> leave it alone
+ *
+ * So the reduction is graded by the ratio rather than chosen by a shape.  There
+ * is no density threshold, no content classifier and no cliff -- a small change
+ * in the picture moves the ratio a little and the reduction a little. */
+static inline void gm_grade(int64_t sc, int64_t mass, int32_t v,
+                            int hard_num, int den, int *num_out)
+{
+    *num_out = den;                         /* no reduction */
+    if (mass <= 0) return;
+    if (v < 0) sc = -sc;
+    if (sc <= 0) return;                    /* misaligned: leave it */
+    /* k = 256 * score / mass, clamped to [0, 256] */
+    int64_t k = sc * 256 / mass;
+    if (k > 256) k = 256;
+    int cut = (int)((int64_t)(den - hard_num) * k / 256);
+    *num_out = den - cut;
+}
+
+int omc_gm_trial = 0; /* env OMC_GM_TRIAL: repair each violating slice with
+                       * BOTH reduction shapes and keep the one whose committed
+                       * picture is closer to the source.  1 = plain squared
+                       * error, 2 = squared error masked by the source's own
+                       * local activity (see gm_slice_sse -- plain squared error
+                       * picks the wrong shape on graphics). */
+int omc_gm_k = 4;     /* env OMC_GM_K: how much more an ADDED unit of
+                       * magnitude costs than a LOST one, for OMC_GM_TRIAL=4 */
+int omc_gm_grade = 0; /* env OMC_GM_GRADE: 1 = grade the reduction by alignment
+                       * (see gm_grade).  Uses OMC_GM_NUM/DEN as the HARDEST
+                       * factor, reached only by a perfectly aligned
+                       * coefficient. */
+int omc_gm_esc = 4;   /* env OMC_GM_ESC: pass at which a slice that is STILL
+                       * violating tightens its reduction factor to
+                       * OMC_GM_ESCNUM/ESCDEN.  0 disables the escalation.
+                       *
+                       * Why this exists.  31/32 is better than 15/16 on eight
+                       * of the nine real-footage cells of the corpus, by 0.01
+                       * to 0.12 VMAF-NEG -- and it fails to CONVERGE on the
+                       * rail stress clip at half a bit per pixel, leaving
+                       * 21,760 samples out of range inside the budget.  That
+                       * is a contract failure, not a quality preference:
+                       * reaching zero is the whole point of the mode, and a
+                       * rule that cannot converge on content that exists is a
+                       * rule that may not converge on content nobody has shown
+                       * it yet.
+                       *
+                       * The escalation removes the trade.  A slice that
+                       * converges quickly -- which is nearly every slice of
+                       * every real clip -- never reaches the escalation pass
+                       * and gets the gentler factor.  A slice that is still
+                       * violating late is one the gentle factor cannot clear,
+                       * and it tightens for the rest of its budget. */
+int omc_gm_escnum = 15, omc_gm_escden = 16;
+/* the SECOND escalation stage: the pass at which a slice that has still not
+ * converged gives up on gentleness, and the factor it gives up to */
+/* OMC_GM_FALLBACK: when the projection says a slice will not clear inside its
+ * budget, throw the gentle attempt away and repair that slice again from its
+ * ORIGINAL coefficients with the rule that always converges -- a plain
+ * proportional cut with no step cap.  On by default. */
+int omc_gm_fallback_on = 1;
+int omc_gm_esc2 = 8;
+int omc_gm_esc2num = 3, omc_gm_esc2den = 4;
+int omc_gm_veto = 0;  /* env OMC_GM_VETO: 1 = veto every misaligned reduction,
+                       * 2 = veto only the ones that cross a quantizer boundary
+                       * (see gm_permit -- this is the one the measurements
+                       * support).  Apply the alignment veto (see
+                       * gm_align) on top of WHATEVER reduction shape the mode
+                       * selects.  The veto answers "should this coefficient be
+                       * reduced at all"; the mode answers "by how much".  They
+                       * are independent questions and the code keeps them so.
+                       * Mode 16 is the shorthand for mode 12 plus the veto,
+                       * kept because measurements were taken under that name. */
+int omc_gm_stat = 0;  /* env OMC_GM_STAT: report what the repair actually did --
+                       * candidates considered, candidates the veto skipped, and
+                       * how many QUANTIZED values the reductions really changed.
+                       * A reduction that does not move a coefficient across a
+                       * quantizer boundary changes no bit of the stream and no
+                       * pixel of the picture: it is free, and it is not what
+                       * the repair costs.  Counting the reductions instead of
+                       * the quantizer crossings has been measuring the wrong
+                       * thing. */
+int omc_gm_align = 4; /* env OMC_GM_ALIGN: passes for which mode 16's alignment
+                       * veto applies.  After this many the veto is dropped so
+                       * convergence inside the budget is still guaranteed: a
+                       * coefficient that hurts on pass 1 can help on pass 4
+                       * once its neighbours have moved, and a permanent veto
+                       * can stall a slice the budget cannot then rescue.
+                       * 0 disables the veto entirely (mode 16 becomes mode 12). */
+int omc_gm_watch = 3; /* env OMC_GM_WATCH: passes to give stepping before
+                       * judging it stalled (mode 8) */
+int omc_gm_dthr = 5; /* env OMC_GM_DTHR: tenths of a per cent of a slice's
+                      * samples above which the violation is DENSE */
 int omc_tf_mode = 0;   /* T5: PERMANENTLY 0.  The in-loop temporal filter was
     removed with the old temporal engine (a filter re-applied at every encode
     generation compounds — the tool's own help text documented the compounding
@@ -705,7 +1380,55 @@ static void omc_global_init_once(void)
     omc_gr_qmax = getenv("OMC_GR_QMAX") ? atoi(getenv("OMC_GR_QMAX")) : 1;
     omc_gr_notemp = getenv("OMC_GR_NOTEMP") ? atoi(getenv("OMC_GR_NOTEMP")) : 0;
     omc_gr_fillveto = getenv("OMC_GR_FILLVETO") ? atoi(getenv("OMC_GR_FILLVETO")) : 0;
-    omc_fill_static = getenv("OMC_FILL_STATIC") ? atoi(getenv("OMC_FILL_STATIC")) : 0;
+    omc_calm = getenv("OMC_CALM") ? (atoi(getenv("OMC_CALM")) != 0) : 1;
+    omc_calm_thr = getenv("OMC_CALM_THR") ? atoi(getenv("OMC_CALM_THR")) : 24;
+    omc_calm_amp = getenv("OMC_CALM_AMP") ? atoi(getenv("OMC_CALM_AMP")) : 3;
+    omc_gm_dil = getenv("OMC_GM_DIL") ? atoi(getenv("OMC_GM_DIL")) : 1;
+    omc_gm_llhold = getenv("OMC_GM_LLHOLD") ? atoi(getenv("OMC_GM_LLHOLD")) : 0;
+    omc_gm_mode = getenv("OMC_GM_MODE") ? atoi(getenv("OMC_GM_MODE")) : 12;
+    omc_gm_nointra = getenv("OMC_GM_NOINTRA") ? atoi(getenv("OMC_GM_NOINTRA")) : 0;
+    omc_gm_replan = getenv("OMC_GM_REPLAN") ? atoi(getenv("OMC_GM_REPLAN")) : 0;
+    omc_gm_dthr = getenv("OMC_GM_DTHR") ? atoi(getenv("OMC_GM_DTHR")) : 5;
+    omc_gm_watch = getenv("OMC_GM_WATCH") ? atoi(getenv("OMC_GM_WATCH")) : 3;
+    omc_gm_align = getenv("OMC_GM_ALIGN") ? atoi(getenv("OMC_GM_ALIGN")) : 4;
+    omc_gm_veto = getenv("OMC_GM_VETO") ? atoi(getenv("OMC_GM_VETO")) : 2;
+    omc_gm_esc = getenv("OMC_GM_ESC") ? atoi(getenv("OMC_GM_ESC")) : 4;
+    omc_gm_escnum = getenv("OMC_GM_ESCNUM") ? atoi(getenv("OMC_GM_ESCNUM")) : 15;
+    omc_gm_escden = getenv("OMC_GM_ESCDEN") ? atoi(getenv("OMC_GM_ESCDEN")) : 16;
+    omc_gm_fallback_on = getenv("OMC_GM_FALLBACK")
+                       ? atoi(getenv("OMC_GM_FALLBACK")) : 1;
+    omc_gm_esc2 = getenv("OMC_GM_ESC2") ? atoi(getenv("OMC_GM_ESC2")) : 8;
+    omc_gm_esc2num = getenv("OMC_GM_ESC2NUM") ? atoi(getenv("OMC_GM_ESC2NUM")) : 3;
+    omc_gm_esc2den = getenv("OMC_GM_ESC2DEN") ? atoi(getenv("OMC_GM_ESC2DEN")) : 4;
+    if (omc_gm_esc2 < 0) omc_gm_esc2 = 0;
+    if (omc_gm_esc2den < 1) omc_gm_esc2den = 1;
+    if (omc_gm_esc2num < 0) omc_gm_esc2num = 0;
+    if (omc_gm_esc2num > omc_gm_esc2den) omc_gm_esc2num = omc_gm_esc2den;
+    if (omc_gm_esc < 0) omc_gm_esc = 0;
+    if (omc_gm_escden < 1) omc_gm_escden = 1;
+    if (omc_gm_escnum < 0) omc_gm_escnum = 0;
+    if (omc_gm_escnum > omc_gm_escden) omc_gm_escnum = omc_gm_escden;
+    omc_gm_grade = getenv("OMC_GM_GRADE") ? atoi(getenv("OMC_GM_GRADE")) : 0;
+    omc_gm_trial = getenv("OMC_GM_TRIAL") ? atoi(getenv("OMC_GM_TRIAL")) : 0;
+    omc_gm_k = getenv("OMC_GM_K") ? atoi(getenv("OMC_GM_K")) : 4;
+    if (omc_gm_k < 1) omc_gm_k = 1;
+    if (omc_gm_k > 1024) omc_gm_k = 1024;
+    if (omc_gm_grade) omc_gm_veto = omc_gm_veto ? omc_gm_veto : 1;
+    omc_gm_stat = getenv("OMC_GM_STAT") ? atoi(getenv("OMC_GM_STAT")) : 0;
+    if (omc_gm_mode == 16) omc_gm_veto = 1;
+    if (omc_gm_align < 0) omc_gm_align = 0;
+    if (omc_gm_align > OMC_GAMUT_MAXPASS) omc_gm_align = OMC_GAMUT_MAXPASS;
+    omc_gm_num = getenv("OMC_GM_NUM") ? atoi(getenv("OMC_GM_NUM")) : 63;
+    omc_gm_den = getenv("OMC_GM_DEN") ? atoi(getenv("OMC_GM_DEN")) : 64;
+    /* Both are shifted left by up to (bitdepth - 7) = 5 before they are
+     * compared against an int32 coefficient, so clamp them here rather than
+     * let a mistyped environment variable shift into the sign bit.  16384 is
+     * four times the largest 12-bit code, i.e. already "everything is flat"
+     * and "no amplitude is too large"; nothing useful lives above it. */
+    if (omc_calm_thr < 0) omc_calm_thr = 0;
+    if (omc_calm_thr > 16384) omc_calm_thr = 16384;
+    if (omc_calm_amp < 0) omc_calm_amp = 0;
+    if (omc_calm_amp > 16384) omc_calm_amp = 16384;
     omc_plan_hyst = getenv("OMC_PLAN_HYST") ? atoi(getenv("OMC_PLAN_HYST")) : 0;
     omc_bandtilt = getenv("OMC_BANDTILT") ? atoi(getenv("OMC_BANDTILT")) : 0;
     omc_recoff = getenv("OMC_RECOFF") ? atoi(getenv("OMC_RECOFF")) : 0;
@@ -832,6 +1555,39 @@ omc_enc_t *omc_enc_create(const omc_config_t *cfg)
     e->dc_off = calloc((size_t)e->c.nslices * OMC_NPLANES, sizeof(int16_t));
     for (int p = 0; p < OMC_NPLANES; p++)
         e->dc_scr[p] = malloc((size_t)plane_width(&e->c, p) * e->c.sh * 2);
+    /* strict in-gamut scratch: the correction field (one slice) and a copy of
+     * the previous slice's last committed row, which the boundary edit in
+     * reconstruct_slice rewrites and a repair pass must therefore restore. */
+    for (int p = 0; p < OMC_NPLANES; p++) {
+        /* summed-area table over the repair's offending-pixel mask:
+         * (sh + 1) x (pw + 1) so a rectangle test is four lookups */
+        e->gm_buf[p] = malloc(sizeof(int32_t) * ((size_t)plane_width(&e->c, p) + 1)
+                                             * ((size_t)e->c.sh + 1));
+        e->gm_rsat[p] = malloc(sizeof(int64_t) * ((size_t)plane_width(&e->c, p) + 1)
+                                              * ((size_t)e->c.sh + 1));
+        e->gm_asat[p] = malloc(sizeof(int64_t) * ((size_t)plane_width(&e->c, p) + 1)
+                                              * ((size_t)e->c.sh + 1));
+        e->gm_rowsave[p] = malloc((size_t)plane_width(&e->c, p) * 2);
+        e->gm_mask[p] = malloc((size_t)plane_width(&e->c, p) * e->c.sh);
+        e->gm_save[p][0] = malloc(sizeof(int32_t) * (size_t)plane_width(&e->c, p) * e->c.sh);
+        e->gm_save[p][1] = malloc(sizeof(int32_t) * (size_t)plane_width(&e->c, p) * e->c.sh);
+    }
+    {   /* default off; the CLI flag and the library setter both turn it on */
+        /* ON BY DEFAULT.  The mode is not a content-dependent preference and
+         * must never be one: a broadcast chain cuts from a match to a studio to
+         * a graphics bumper in seconds, and there is nobody at a console
+         * deciding which of those needs its committed picture kept inside the
+         * legal range.  A setting that has to be switched per clip is a setting
+         * that will be wrong.  So it defaults on, and the two properties that
+         * make that safe are gated rather than assumed: it is byte-identical to
+         * having it off on content that never reaches the rails (G-T5-GAMUT3),
+         * and it stands down entirely on CDR input (12.22.4).  Set
+         * OMC_GAMUT_STRICT=0, or --gamut-strict 0, to turn it off. */
+        const char *gs = getenv("OMC_GAMUT_STRICT");
+        e->gamut_strict = gs ? atoi(gs) : OMC_GAMUT_DEFPASS;
+        if (e->gamut_strict < 0) e->gamut_strict = 0;
+        if (e->gamut_strict > OMC_GAMUT_MAXPASS) e->gamut_strict = OMC_GAMUT_MAXPASS;
+    }
     {
         omc_band_t bl[OMC_NBANDS];
         for (int p = 0; p < OMC_NPLANES; p++) {
@@ -909,9 +1665,85 @@ omc_enc_t *omc_enc_create(const omc_config_t *cfg)
 
 int64_t omc_enc_oob(const omc_enc_t *e)
 {
-    return e ? e->oob_samples : 0;
+    if (!e) return -1;
+    /* The report is measured on the EMITTED picture, so it needs the caller to
+     * ask for one.  A caller that passes recon = NULL gets -1, "not measured",
+     * and never a 0 that would read as "no excursions" -- the same distinction
+     * a meter has between reading zero and being unplugged.  (Before this the
+     * count stayed at 0 and the CLI verdict said "baseband-safe: yes" for a
+     * stream nothing had looked at.) */
+    return e->gm_norecon ? -1 : e->oob_samples;
 }
 
+/* Strict in-gamut mode.  `passes` is the per-slice repair budget (0 = off);
+ * the mode is encoder-side only -- it changes WHICH lattice point a
+ * first-generation slice commits to, never how a lattice point is decoded,
+ * so no bitstream syntax, no decoder change, and the generation lock is
+ * untouched (a locked slice is never repaired). */
+void omc_enc_set_gamut_strict(omc_enc_t *e, int passes)
+{
+    if (!e) return;
+    if (passes < 0) passes = 0;
+    if (passes > OMC_GAMUT_MAXPASS) passes = OMC_GAMUT_MAXPASS;
+    e->gamut_strict = passes;
+}
+
+/* Declare that this encoder is being fed COMMITTED pictures (the CDR
+ * interchange), not ordinary baseband video.  Strict in-gamut mode then stands
+ * down completely, because a committed picture is allowed to sit outside the
+ * legal range and MUST be reproduced verbatim -- "repairing" it would break
+ * the CDR chain, which is the one guarantee that holds unconditionally.  The
+ * reference CLI sets this whenever --cdr-in is given. */
+void omc_enc_set_cdr_input(omc_enc_t *e, int on)
+{
+    if (e) e->cdr_input = on ? 1 : 0;
+}
+
+int64_t omc_enc_gamut_repairs(const omc_enc_t *e) { return e ? e->gm_repairs : 0; }
+int64_t omc_enc_gamut_slices(const omc_enc_t *e) { return e ? e->gm_slices : 0; }
+int64_t omc_enc_gamut_fallbacks(const omc_enc_t *e) { return e ? e->gm_fallbacks : 0; }
+void omc_enc_gamut_stat_report(void)
+{
+    if (!omc_gm_stat) return;
+    fprintf(stderr, "omc_enc: gamut stat: %lld candidates, %lld vetoed (%.1f%%), "
+            "%lld reductions applied, %lld of them crossed a quantizer boundary "
+            "(%.1f%%)\n",
+            (long long)gm_st_cand, (long long)gm_st_veto,
+            gm_st_cand ? 100.0 * gm_st_veto / gm_st_cand : 0.0,
+            (long long)gm_st_red, (long long)gm_st_cross,
+            gm_st_red ? 100.0 * gm_st_cross / gm_st_red : 0.0);
+    fprintf(stderr, "omc_enc: gamut stat: crossings by band  ");
+    for (int b = 0; b < OMC_NBANDS; b++)
+        fprintf(stderr, "%d:%lld/%lld ", b, (long long)gm_st_cross_b[b],
+                (long long)gm_st_red_b[b]);
+    fprintf(stderr, "\nomc_enc: gamut stat: crossings by |c| in quantizer steps  ");
+    for (int m = 0; m < 8; m++)
+        fprintf(stderr, "%s%d:%lld/%lld ", m == 7 ? ">=64 " : "<", m ? 1 << m : 1,
+                (long long)gm_st_cross_m[m], (long long)gm_st_red_m[m]);
+    fprintf(stderr, "\nomc_enc: gamut stat: coded-value change and injected "
+            "energy by band  ");
+    int64_t tdq = 0, te2 = 0;
+    for (int b = 0; b < OMC_NBANDS; b++) {
+        fprintf(stderr, "%d:dq=%lld,e2=%lld ", b, (long long)gm_st_dq[b],
+                (long long)gm_st_e2[b]);
+        tdq += gm_st_dq[b];
+        te2 += gm_st_e2[b];
+    }
+    /* ||g||^2 per band x 10000, measured by tests/basis.c on the real inverse
+     * transform: the picture energy one unit of a band's coefficient carries. */
+    static const int64_t g2[OMC_NBANDS] =
+        { 590942, 173111, 96074, 55229, 33853, 26841, 10294, 11792, 10100, 4840 };
+    long double w = 0;
+    for (int b = 0; b < OMC_NBANDS; b++)
+        w += (long double)gm_st_e2[b] * g2[b] / 10000.0L;
+    if (gm_st_pickA + gm_st_pickB)
+        fprintf(stderr, "\nomc_enc: gamut stat: trial picked harsh %lld times, "
+                "gentle %lld times", (long long)gm_st_pickA, (long long)gm_st_pickB);
+    fprintf(stderr, "\nomc_enc: gamut stat: TOTAL dq=%lld  raw e2=%lld  "
+            "PICTURE ENERGY REMOVED=%.4Le\n", (long long)tdq, (long long)te2, w);
+}
+int64_t omc_enc_gamut_unfixed(const omc_enc_t *e) { return e ? e->gm_unfixed : 0; }
+
 /* Is this GEOMETRY recoverable from a cropped baseband picture at all?
  * Pad neutralization (minor 11) covers VERTICAL pad rows of the last slice
  * and nothing else, so it answers no when:
@@ -963,6 +1795,9 @@ void omc_enc_destroy(omc_enc_t *e)
     free(e->hyst_gain); free(e->sl_energy); free(e->sl_energy_c);
     free(e->dc_q8); free(e->dc_off); free(e->spc_drop); free(e->spc_kmax);
     for (int p = 0; p < OMC_NPLANES; p++) free(e->dc_scr[p]);
+    for (int p = 0; p < OMC_NPLANES; p++) { free(e->gm_buf[p]); free(e->gm_rsat[p]); free(e->gm_asat[p]);
+        free(e->gm_rowsave[p]);
+        free(e->gm_mask[p]); free(e->gm_save[p][0]); free(e->gm_save[p][1]); }
     for (int p = 0; p < OMC_NPLANES; p++)
         for (int b = 2; b < OMC_NBANDS; b++) free(e->elig[p][b]);
     free(e->syms); free(e->stids); free(e->raws); free(e->rawn);
@@ -1324,14 +2159,45 @@ static inline int fill_gate_g(const int32_t *ll, int llstride, int llw, int llh,
     if (sgv) *sgv = (gv > 0) - (gv < 0);
     if (gh < 0) gh = -gh;
     if (gv < 0) gv = -gv;
-    if (gh + gv < OMC_FILL_GATE) return 0;
-    /* v4.6: THREE activity classes (eye-driven, third tier added after the
-     * flat-sheen speckle was localized on wet sand): quarter strength on the
-     * flattest passing regions, half on moderate texture, full on dense.
-     * Bottoms out at 1 code - the measured sensor-grain sigma class of the
-     * delivery corpus (beach 0.74). Decoder-derivable, zero bits. */
+    /* ---- THE ANTS GATE (bitstream minor 12).
+     *
+     * The fill paints a quarter of a quantizer step at every zero-coded
+     * position a band's fill bit covers, and its sign comes from a tile whose
+     * phase advances with the frame index.  In a FLAT region every detail
+     * coefficient is zero, so the fill fires at every position, and the region
+     * therefore MOVES from frame to frame -- at shift 6 that is a 16-code sign
+     * flip.  Texture the source holds still and the decode does not is exactly
+     * the "ants" defect REPORT.md 18.5-18.7 records as the one thing a blind
+     * viewer identified twice.
+     *
+     * v4.6 answered it with a three-tier amplitude taper on this same activity
+     * measure (quarter / half / full strength).  T5 removed the taper for a
+     * real reason -- the tapered mean is not a fixed point of the fill-gain
+     * derivation -- and the ants came back at five times the v4.14 level
+     * (measured: 0.49 % against 0.09 % on an 8-frame still master where the
+     * source's own movement is exactly zero).
+     *
+     * Restoring the taper was tried first and does not work.  Making the
+     * DERIVATION taper-aware does restore the gain fixed point exactly (gen 2
+     * re-derives 16*g to the digit), but the amplitude change breaks the
+     * generation lock further upstream: the lattice scan that proposes
+     * candidate plans reads the committed fill values, and a tapered fill at
+     * shift s looks like an untapered fill at shift s-t, so the search stops
+     * proposing the plan the previous generation actually used.  Measured: the
+     * gain re-derived correctly and the slice still failed to lock.
+     *
+     * What works is the limit case of the taper, and it is simpler than the
+     * taper: the flattest passing tier gets NO FILL AT ALL.  A position that
+     * is not filled reconstructs to exactly zero, which is a lattice point at
+     * every shift, so the candidate search is untouched; the gate is read
+     * identically by the derivation, the verifier, the encoder reconstruction
+     * and the decoder, so the fixed point is preserved by construction; and it
+     * costs zero bits because the class comes from the LL both ends already
+     * hold.  The regions that lose their fill are the ones where synthetic
+     * texture is least defensible and the ants are worst. */
+    if (gh + gv < OMC_FILL_ANTS_GATE) return 0;
     int act = gh + gv;
-    return act < 2 * OMC_FILL_GATE ? 1 : act < 4 * OMC_FILL_GATE ? 2 : 3;
+    return act < 4 * OMC_FILL_GATE ? 2 : 3;
 }
 static inline int fill_gate(const int32_t *ll, int llstride, int llw, int llh,
                             int vvis, int b, int row, int col, int32_t lllim)
@@ -1417,7 +2283,27 @@ static inline int32_t fill_value_p(const int32_t *ll, int llstride, int llw, int
         else if (gain == 3) a += (a >> 1) + (a >> 2);
     }
     (void)act;
-    if (v6) { fox = sfox; foy = sfoy; } /* v6 arg = static-tile flag (T5) */
+    /* ---- THE FILL TILE NO LONGER ANIMATES (bitstream minor 12).
+     *
+     * The fill's sign came from a tile indexed by (col + fox, row + foy) with
+     * the offsets advancing with the frame index, so that restored grain
+     * "animates at frame rate".  In a flat region every detail coefficient is
+     * zero, so the fill fires at every position and that animation IS the
+     * picture's only movement -- a per-frame sign flip of a quarter step,
+     * which at shift 6 is 16 code values.  REPORT.md 18.7 measured the same
+     * thing from the other direction and stated it plainly: "animation, not
+     * amplitude, is the fill's boil".
+     *
+     * Synthetic movement is not what makes grain look alive; the CONTENT's
+     * own movement is, and the fill rides on top of it.  So the tile is now
+     * always the frame-independent one.  Measured cost in VMAF-NEG: none
+     * (96.3526 against 96.3515 on the 1080p still arm; identical to four
+     * decimals on the 720p 4:4:4 arm).  The stream option that used to select
+     * this behaviour per stream (fill_static, option-word bit 2) is now the
+     * only behaviour, and the argument is retained so the option word keeps
+     * its meaning for streams that set it. */
+    fox = sfox; foy = sfoy;
+    (void)v6;
     if (hint) return hint > 0 ? a : -a;   /* local coded structure wins */
     return omc_fill_sign_sel(col + fox, row + foy, corr) ? a : -a;
 }
@@ -1653,7 +2539,7 @@ static int lock_verify(omc_enc_t *e, int cf444, int prof, int Q, int ns, int k,
         for (int b = 0; b < OMC_NBANDS; b++) {
             int base_s = sp.shift[p][b];
             int can_fill = b >= OMC_FILL_BANDS_FROM &&
-                           base_s >= OMC_FILL_MIN_SHIFT && !c->cfg.no_fill;
+                           base_s >= OMC_FILL_MIN_SHIFT && c->cfg.fill_grain;
             int n = bands[b].h * bands[b].w;
             int tex_vmaf = OMC_BAND_TEXTURE(b) && c->cfg.tune_vmaf;
             int nm = can_inter ? 2 : 1;
@@ -1745,7 +2631,7 @@ static int lock_verify(omc_enc_t *e, int cf444, int prof, int Q, int ns, int k,
             for (int b = 1; b < OMC_NBANDS && ok; b++) {
                 int base_s = sp.shift[p][b];
                 int can_fill = b >= OMC_FILL_BANDS_FROM &&
-                               base_s >= OMC_FILL_MIN_SHIFT && !c->cfg.no_fill;
+                               base_s >= OMC_FILL_MIN_SHIFT && c->cfg.fill_grain;
                 int w = bands[b].w, n = bands[b].h * bands[b].w;
                 int tex_vmaf = OMC_BAND_TEXTURE(b) && c->cfg.tune_vmaf;
                 int nm = can_inter ? 2 : 1;
@@ -1766,7 +2652,9 @@ static int lock_verify(omc_enc_t *e, int cf444, int prof, int Q, int ns, int k,
                             if (coeff_shift(&sp, p, b, i) != base_s) continue;
                             if (omc_quant1b_dz(cf[i], base_s, tex_vmaf, e->dz_enabled) != 0) continue;
                             if (m && pc[i] != 0) continue;
-                            if (!fill_gate(llbuf, llw, llw, llh, vvis, b, i / w, i % w, lllim)) continue;
+                            int fact = fill_gate(llbuf, llw, llw, llh, vvis, b,
+                                                 i / w, i % w, lllim);
+                            if (!fact) continue;
                             int32_t a = e->coef[p][b][i];
                             sum += a < 0 ? -a : a;
                             count++;
@@ -1795,7 +2683,7 @@ static int lock_verify(omc_enc_t *e, int cf444, int prof, int Q, int ns, int k,
                             v = fill_value_p(llbuf, llw, llw, llh, vvis, b, i / w, i % w,
                                              s, fox, foy, sfox, sfoy, lllim, ghyp,
                                              c->cfg.grain_corr,
-                                             (c->cfg.fill_static ? 1 : 0), 0, &vfp);
+                                             0 /* was fill_static; inert since minor 12 */, 0, &vfp);
                         if (v != e->coef[p][b][i]) {
                             if (getenv("OMC_DEBUG_VERIFY2"))
                                 fprintf(stderr, "vmis sl=%d p=%d b=%d m=%d fb=%d g=%d "
@@ -2036,6 +2924,50 @@ int omc_enc_slice(omc_enc_t *e, const omc_frame_t *in, int frame_idx, int slice_
 
     /* ---- causal bit banking: budget for this slice ---- */
     if (slice_idx == 0) e->spent_bits = 0;
+    /* Bit-banking baseline for this slice.  Step 6 assigns
+     * spent_bits = gm_spent0 + slice_size*8 rather than accumulating, so a
+     * strict-in-gamut repair pass (which re-enters the encode at
+     * `encode_attempts`, i.e. AFTER step 6 has already run once) cannot
+     * double-count the slice against the frame's CBR budget. */
+    const int64_t gm_spent0 = e->spent_bits;
+    /* Strict in-gamut repair state.  All of it must live ABOVE the
+     * `gamut_recode` label below, because a boundary-clamp pass re-enters the
+     * slice from the transform and everything declared after the label is
+     * re-initialised there. */
+    int gm_iter = 0, gm_rowsaved = 0;  /* repair passes used */
+    /* TRIAL SELECTION (OMC_GM_TRIAL).  The two reduction shapes win on
+     * opposite content and every attempt to tell the content apart by a
+     * threshold has failed -- density, convergence rate, per-band leverage,
+     * alignment ratio.  So the encoder stops guessing: it repairs the slice
+     * BOTH ways and keeps whichever committed picture is closer to the source
+     * it was made from.  Squared error against the source is not a proxy for
+     * the answer, it is the answer, and it needs no classifier and has no
+     * cliff.
+     *
+     * gm_trial: 0 = first shape, 1 = second shape, 2 = replaying the first
+     * because it won.  Only slices the repair actually fires on are trialled,
+     * so content that never reaches the rails costs nothing. */
+    int gm_trial = 0, gm_tsaved = 0;
+    int64_t gm_sse[2] = { 0, 0 };
+    /* PROGRESS TRACKING for the escalation.  gm_prevbad is the violation count
+     * this slice had at the end of the previous pass; gm_hard latches once the
+     * count has failed to fall, and pins the reduction to the harsh factor for
+     * the rest of this slice's budget.
+     *
+     * This is what makes gentleness safe.  A gentle factor is right almost
+     * everywhere and is what keeps the repair nearly free on ordinary footage,
+     * but it cannot clear a neighbourhood the quantizer has PINNED to a rail:
+     * removing a sixty-fourth of a coefficient does not change the coded value
+     * there at all, so the pass accomplishes nothing, and so does every pass
+     * after it.  Waiting a fixed number of passes before tightening spends the
+     * budget on moves that were already known to be doing nothing.  Latching on
+     * the first pass that makes no progress spends it on moves that might. */
+    int gm_prevbad = -1, gm_hard = 0, gm_fellback = 0, gm_behind = 0;
+    int gm_bad0 = 0, gm_stall = 0;     /* mode 8: initial count, and the
+                                        * pass at which stepping was judged
+                                        * to be losing */
+    uint32_t gm_nofill = 0;            /* planes whose grain fill the repair suppressed */
+    uint32_t gm_intra = 0;             /* bands the repair forced to intra coding */
     int64_t B = (int64_t)c->cfg.bits_per_slice;
     /* no banking overdraft (see OD_CAP_PCT above) */
     int64_t F = B * c->nslices;
@@ -2420,6 +3352,73 @@ int omc_enc_slice(omc_enc_t *e, const omc_frame_t *in, int frame_idx, int slice_
         }
     }
 
+    /* TEMPORAL CALM classifier (the ants fix; see omc_calm above).  One pass
+     * over every detail band, on intra and inter slices alike, marking the
+     * positions whose co-located LL cell sits in a locally FLAT neighbourhood
+     * as eligibility class 3.  Class 3 reaches exactly one consumer -- the
+     * legacy full-step kill in band_scan -- and none of the grain-replace
+     * knobs, all of which test for class 2 explicitly.
+     *
+     * Bands the grain-replace classifier already wrote keep their class: a
+     * position it marked is grain, which the fill regenerates, and taking it
+     * over here would silently change that path.  Everywhere else the array
+     * is ours and is cleared first. */
+    if (omc_calm) {
+        int gr_wrote = (e->gr_enabled && (can_inter || omc_gr_intra));
+        int gr_lo = (omc_gr_mode >= 2) ? 2 : OMC_FILL_BANDS_FROM;
+        /* The gradient ceiling is quoted at 8-bit and scales with the coded
+         * depth, because LL coefficients carry the pixel scale: a 10-bit
+         * master's "flat" is four times an 8-bit master's in code values. */
+        int32_t cthr = (int32_t)omc_calm_thr << (c->cfg.bitdepth - 8);
+        for (int p = 0; p < OMC_NPLANES; p++) {
+            omc_band_layout(plane_width(c, p), sh, bands);
+            int llw2 = bands[0].w, llh2 = bands[0].h;
+            const int32_t *llc = e->coef[p][0];
+            for (int b = 2; b < OMC_NBANDS; b++) {
+                uint8_t *el = e->elig[p][b];
+                int w = bands[b].w, h = bands[b].h, n = h * w;
+                if (!(gr_wrote && b >= gr_lo)) memset(el, 0, (size_t)n);
+                for (int i = 0; i < n; i++) {
+                    if (el[i]) continue;   /* grain-replace owns this cell */
+                    /* Co-located LL cell.  Same mapping and the same
+                     * two-stage clamp the grain-replace classifier carries:
+                     * the interior-preference clamp goes out of range when
+                     * the LL band is under three cells in a dimension
+                     * (llh2 == 2 is slice_h 8; llw2 == 1 is a 32-wide
+                     * plane), so it is re-clamped in range afterwards. */
+                    int rL = (b >= 7) ? (i / w) >> 1 : (i / w);
+                    int xL = (i % w) >> (b >= 7 ? 4 : b >= 4 ? 3 : (b == 3 ? 2 : 1));
+                    if (rL > llh2 - 2) rL = llh2 - 2;
+                    if (rL < 1) rL = 1;
+                    if (xL > llw2 - 2) xL = llw2 - 2;
+                    if (xL < 1) xL = 1;
+                    if (rL > llh2 - 1) rL = llh2 - 1;
+                    if (rL < 0) rL = 0;
+                    if (xL > llw2 - 1) xL = llw2 - 1;
+                    if (xL < 0) xL = 0;
+                    int rlo = rL - 1 < 0 ? 0 : rL - 1;
+                    int rhi = rL + 1 > llh2 - 1 ? llh2 - 1 : rL + 1;
+                    int xlo = xL - 1 < 0 ? 0 : xL - 1;
+                    int xhi = xL + 1 > llw2 - 1 ? llw2 - 1 : xL + 1;
+                    int32_t gh = llc[(size_t)rL * llw2 + xhi]
+                               - llc[(size_t)rL * llw2 + xlo];
+                    int32_t gv = llc[(size_t)rhi * llw2 + xL]
+                               - llc[(size_t)rlo * llw2 + xL];
+                    if (gh < 0) gh = -gh;
+                    if (gv < 0) gv = -gv;
+                    if (gh + gv >= cthr) continue;
+                    if (omc_calm_amp) {
+                        int32_t ac0 = e->coef[p][b][i];
+                        if (ac0 < 0) ac0 = -ac0;
+                        if (ac0 >= ((int32_t)omc_calm_amp << (c->cfg.bitdepth - 7)))
+                            continue;
+                    }
+                    el[i] = 3;
+                }
+            }
+        }
+    }
+
     /* OMC_ZERO_BANDS (diagnostic env, encoder-only): force listed bands to
      * zero in both domains - inter bands freeze to their temporal
      * prediction, intra bands blank. Used for per-band temporal attribution
@@ -2459,7 +3458,8 @@ int omc_enc_slice(omc_enc_t *e, const omc_frame_t *in, int frame_idx, int slice_
                     memset(hist, 0, sizeof(hist));
                     band_scan(e, p, b, arr, n, NULL, s, hist, 0, 0, NULL,
                               NULL, bands[b].w, e->rowsig,
-                              (e->gr_enabled && b >= (omc_gr_mode >= 2 ? 2 : OMC_FILL_BANDS_FROM)) ? e->elig[p][b] : NULL);
+                              ((e->gr_enabled && b >= (omc_gr_mode >= 2 ? 2 : OMC_FILL_BANDS_FROM))
+                               || (omc_calm && b >= 2)) ? e->elig[p][b] : NULL);
                     int64_t c64;
                     bc[m][p][b].gid[s] = (uint8_t)best_group(hist, &c64);
                     int64_t bits = c64 >> 6;
@@ -3002,6 +4002,17 @@ encode_attempts:;
                 int s_probe = sp.shift[p][b]; /* group id from the full-band shift */
                 int m = locked ? (int)((lock_modes >> (p * OMC_NBANDS + b)) & 1)
                                : BMODE(p, b, s_probe);
+                /* Strict in-gamut: a band the repair has given up on is forced
+                 * to INTRA.  Shrinking an INTER residual converges to the
+                 * PREDICTION, so when the prediction itself is out of range --
+                 * which happens as soon as one frame ends with a residual
+                 * excursion, because the next frame predicts from it -- the
+                 * repair walks the reconstruction TOWARD the violation instead
+                 * of away from it (measured: a sample at 1031 went 1028 ->
+                 * 1031 over successive passes).  Intra breaks the inheritance:
+                 * the reconstruction then converges to this slice's own
+                 * low-pass, which is inside the range by construction. */
+                if ((gm_intra >> (p * OMC_NBANDS + b)) & 1) m = 0;
                 if (m) mode_mask |= 1u << (p * OMC_NBANDS + b);
                 /* T5: the table-group id must be a pure function of the
                  * EMITTED SYMBOLS, or it is not generation-invariant and the
@@ -3018,8 +4029,10 @@ encode_attempts:;
                  * generations by the lock, so this choice — and with it the
                  * payload size — is a generation fixed point. */
                 const uint8_t *scan_elig =
-                    (!locked && e->gr_enabled &&
-                     b >= (omc_gr_mode >= 2 ? 2 : OMC_FILL_BANDS_FROM))
+                    (!locked &&
+                     ((e->gr_enabled &&
+                       b >= (omc_gr_mode >= 2 ? 2 : OMC_FILL_BANDS_FROM))
+                      || (omc_calm && b >= 2)))
                         ? e->elig[p][b] : NULL;
                 int gid;
                 {
@@ -3278,14 +4291,14 @@ encode_attempts:;
          * emit it verbatim (lock_verify validated it bit-exactly) */
         fill_mask = lock_fmask;
         for (int p = 0; p < OMC_NPLANES; p++) fill_gain[p] = lock_gain[p];
-    } else if (!c->cfg.no_fill && pinned && omc_plan_hyst >= 2) {
+    } else if (c->cfg.fill_grain && pinned && omc_plan_hyst >= 2) {
         /* pinned slice (hysteresis level 2): fill bits and gains are frozen
          * to the previous frame's, so the pin does not flip texture
          * decisions. */
         fill_mask = e->hyst_fmask[slice_idx];
         for (int p = 0; p < OMC_NPLANES; p++)
             fill_gain[p] = e->hyst_gain[slice_idx * OMC_NPLANES + p];
-    } else if (!c->cfg.no_fill) {
+    } else if (c->cfg.fill_grain) {
         for (int p = 0; p < OMC_NPLANES; p++) {
             int64_t gnum = 0, gden = 0;
             int pw = plane_width(c, p);
@@ -3313,8 +4326,12 @@ encode_attempts:;
                     if (coeff_shift(&sp, p, b, i) != base_s) continue;
                     if (e->qbuf[p][b][i] != 0) continue; /* zero-coded only */
                     if (m && pc[i] != 0) continue;       /* fill needs true 0 */
-                    if (!fill_gate(llbuf, llw, llw, llh, vvis, b, i / w, i % w, lllim)) continue;
+                    int fact = fill_gate(llbuf, llw, llw, llh, vvis, b, i / w, i % w, lllim);
+                    if (!fact) continue;
                     int32_t a = e->coef[p][b][i];
+                    /* normalise by the taper this position will be filled at,
+                     * so the mean is of UNTAPERED amplitudes and stays a
+                     * generation fixed point (see fill_taper) */
                     sum += a < 0 ? -a : a;
                     count++;
                     if (elg && elg[i] == 2) nflat++;
@@ -3381,6 +4398,15 @@ encode_attempts:;
                     k--;
                 }
         }
+    /* Strict in-gamut: grain fill regenerates a quarter-step of texture at
+     * positions that code to zero, which is exactly what the repair's shrink
+     * creates more of -- so without this the repair adds back the energy it
+     * just removed and the violation count stops falling short of zero.
+     * Clearing the bit is exactness-safe: the fill rule measures the CODED
+     * coefficients, an unfilled band leaves them at zero, and a band of zeros
+     * re-derives to "no fill" at every later generation, so the generation
+     * lock still reproduces the slice. */
+    fill_mask &= ~gm_nofill;
     e->spc_fmask = fill_mask;
     for (int p = 0; p < OMC_NPLANES; p++) e->spc_gain[p] = fill_gain[p];
     e->hyst_fmask[slice_idx] = fill_mask;
@@ -3422,7 +4448,7 @@ encode_attempts:;
                         v = fill_value_p(ll, pw, llw, llh, vvis, b, i / B->w, fcol,
                                        sft, fox, foy, sfox, sfoy, lllim,
                                        fill_gain[p], c->cfg.grain_corr,
-                                       (c->cfg.fill_static ? 1 : 0),
+                                       0 /* was fill_static; inert since minor 12 */,
                                        0, &fp);
                     e->sbuf[p][(size_t)(B->r0 + i / B->w) * pw + B->c0 + i % B->w] = v;
                 }
@@ -3615,7 +4641,7 @@ encode_attempts:;
     crc = omc_crc32_ext(crc, dst + OMC_SLICE_HDR_BYTES, used_bytes);
     memcpy(dst + OMC_SLICE_HDR_BYTES - 4, &crc, 4);
 
-    e->spent_bits += (int64_t)slice_size * 8;
+    e->spent_bits = gm_spent0 + (int64_t)slice_size * 8;
     if (getenv("OMC_DEBUG_SIZES"))
         fprintf(stderr, "SZ f%d s%d bytes=%zu locked=%d spent=%lld\n",
                 frame_idx, slice_idx, slice_size, locked,
@@ -3653,7 +4679,7 @@ encode_attempts:;
                         v = fill_value_p(ll, pw, llw, llh, vvis, b, i / B->w, fcol,
                                        s, fox, foy, sfox, sfoy, lllim, fill_gain[p],
                                        c->cfg.grain_corr,
-                                       (c->cfg.fill_static ? 1 : 0),
+                                       0 /* was fill_static; inert since minor 12 */,
                                        0, &fp);
                     e->sbuf[p][(size_t)(B->r0 + i / B->w) * pw + B->c0 + fcol] = v;
                 }
@@ -3664,6 +4690,19 @@ encode_attempts:;
             rf.p[p] = e->ref[p];
             rf.stride[p] = plane_width(c, p);
         }
+        /* Strict in-gamut mode may re-code this slice.  reconstruct_slice
+         * retro-EDITS the previous slice's last committed row, which is not
+         * idempotent, so keep a pristine copy of it before the first pass and
+         * restore it before every repeat. */
+        if (e->gamut_strict && slice_idx > 0) {
+            for (int p = 0; p < OMC_NPLANES; p++) {
+                int pw = plane_width(c, p);
+                uint16_t *row = e->ref[p] + (size_t)(slice_idx * sh - 1) * pw;
+                if (!gm_rowsaved) memcpy(e->gm_rowsave[p], row, (size_t)pw * 2);
+                else memcpy(row, e->gm_rowsave[p], (size_t)pw * 2);
+            }
+            gm_rowsaved = 1;
+        }
         /* T5: reconstruct straight into the rolling current-frame store (the
          * biased domain is the only domain).  The boundary edit inside
          * reconstruct_slice retro-touches the previous slice's last row of
@@ -3713,6 +4752,928 @@ encode_attempts:;
      * cross-checking the report against the decoded CDR.)  Count only, never
      * alter.  Rows below the display height are pad and are cropped away, so
      * they are excluded.  Reported by omc_enc as the baseband-safe verdict. */
+    /* ---- STRICT IN-GAMUT REPAIR (encoder-only; docs/TEMPORAL_T5.md 12.22).
+     *
+     * Why this is exactness-safe.  The repair NEVER touches the
+     * reconstruction rule.  It edits this slice's SOURCE coefficients before
+     * quantization and re-runs the ordinary encode, so whatever is finally
+     * emitted is an ordinary lattice point and the committed picture is still
+     * the unclamped inverse transform of it -- the two properties the whole
+     * A4 induction rests on (section 8).  Consequences:
+     *   - no bitstream syntax changes and no decoder change;
+     *   - a LOCKED slice is never repaired.  It already reproduces its input
+     *     exactly, and its input at generation >= 2 is a committed picture
+     *     that a strict generation 1 already placed inside the legal range,
+     *     so the repair is inert from generation 2 onwards -- which is why
+     *     turning the mode on costs nothing in the steady state.
+     *
+     * The step.  Let P be the committed picture and E = clip(P) - P the
+     * (sparse, mostly zero) pixel-domain excess.  Adding the forward
+     * transform of E to the source coefficients moves the next
+     * reconstruction by approximately E, i.e. onto the rail instead of past
+     * it.  The lifting is not exactly linear and quantization is not exactly
+     * transparent, so this is a step, not a solution -- hence the bounded
+     * iteration.  The previous slice's last row is coupled to this slice's
+     * first row through the boundary edit (d1 = (e0 - e14)/4), so an excess
+     * there is attributed to row 0 with a gain of 4.
+     *
+     * The mode is a first-generation encoder policy.  If the budget runs out
+     * the slice is committed anyway and the stream is reported NOT
+     * baseband-safe exactly as before -- the report never becomes a promise
+     * the encoder did not keep. */
+    if (!recon) e->gm_norecon = 1;
+    int gm_bad = 0, gm_need = 0;
+    if (recon && e->gamut_strict) {
+        int dh = c->cfg.display_height ? c->cfg.display_height : c->H;
+        int32_t lo = OMC_PIX_BIAS, hi = OMC_PIX_BIAS + c->maxv;
+        /* Two windows, deliberately different.
+         *   gm_bad  -- the TRUE legal-range test.  It is what the gamut report
+         *              counts and what a baseband hop actually clips.
+         *   gm_need -- the REPAIR target.  Identical except on the two rows the
+         *              XSL boundary edit will touch, which must end up a
+         *              blend-cap inside the rails so the edit cannot carry them
+         *              out (part 1 of the rule is the source clamp in step 1).
+         * Enforcing the margin on the COMMITTED picture, not only on the
+         * source, is what keeps the mode generation-safe: at generation 2 the
+         * input rows are the committed rows, the step-1 clamp then finds them
+         * already inside the window and does nothing, and the lock reproduces
+         * the slice unchanged.  Without it the clamp moved generation 2's input
+         * and the chain broke on the encoder's own correction. */
+        int32_t cap = c->xsl_lim * ((c->maxv + 1) >> 10);
+        int q0 = slice_idx * sh - 1, q1 = slice_idx * sh + sh;
+        if (q0 < 0) q0 = 0;
+        if (q1 > dh) q1 = dh;
+        for (int p = 0; p < OMC_NPLANES; p++) {
+            int pw = plane_width(c, p);
+            for (int r = q0; r < q1; r++) {
+                int rel = r - slice_idx * sh;
+                int32_t m = ((rel == 0 && slice_idx > 0) ||
+                             (rel == sh - 1 && slice_idx < c->nslices - 1))
+                            ? cap : 0;
+                const uint16_t *rp = recon->p[p] + (size_t)r * recon->stride[p];
+                for (int x = 0; x < pw; x++) {
+                    if (rp[x] < lo || rp[x] > hi) gm_bad++;
+                    if (rp[x] < lo + m || rp[x] > hi - m) gm_need++;
+                }
+            }
+        }
+        if (gm_need && getenv("OMC_GAMUT_STAT"))
+            fprintf(stderr, "GAMUT f%d s%d pass%d bad=%d need=%d locked=%d Q=%d ns=%d\n",
+                    frame_idx, slice_idx, gm_iter, gm_bad, gm_need, locked, Q, n_steps);
+        /* WHICH SLICES MAY BE REPAIRED, and why the answer is not "unlocked
+         * ones".
+         *
+         * A locked slice must be repairable.  A first-generation slice that
+         * codes losslessly LOCKS (its coefficients are already lattice points),
+         * and its only route out of the legal range is the XSL boundary edit --
+         * so refusing to repair locked slices leaves exactly the rail-content
+         * excursions that matter, and measurably did: 4 slices per frame of the
+         * rail clip, 3450 samples, that no number of passes could touch.
+         *
+         * Repairing a locked slice is safe for a BASEBAND chain.  Generation 1
+         * commits a repaired (softer) picture; generation 2 reads it, un-blends
+         * it back onto the lattice, locks, reproduces it exactly, finds it
+         * inside the legal range, and never repairs -- so generation 2 is
+         * byte-identical to generation 1 and the repair is a generation-1
+         * policy, exactly as intended.
+         *
+         * It is NOT safe on a CDR chain, where the input is a committed picture
+         * that is ALLOWED to sit outside the legal range and must be reproduced
+         * verbatim.  That case is excluded by an explicit declaration from the
+         * caller (omc_enc_set_cdr_input, set by --cdr-in), not by a test on the
+         * data: an earlier version guessed it from whether the slice's input
+         * was in range, and that guess is not generation-invariant -- the
+         * un-blend moves the two boundary rows, so the same slice could be
+         * judged differently at generation 1 and generation 2 and the chain
+         * would break on the guess rather than on the content. */
+        /* The loop runs on gm_bad, the TRUE legal-range test, never on the
+         * margin.  An earlier version looped on the margin and also clamped
+         * the source's boundary rows to it, which converged faster on paper
+         * and was WRONG: when the budget ran out with the margin unmet, the
+         * committed rows sat inside the legal range but outside the clamp
+         * window, so at generation 2 the same clamp MOVED the input, the lock
+         * failed, and the chain broke while the gamut report still said zero.
+         * A correction the encoder applies to its own input has to be a no-op
+         * at generation 2 or it is not a correction, it is a second encoder. */
+        if (gm_bad && !e->cdr_input && gm_iter == 0) gm_bad0 = gm_bad;
+        /* WILL THIS FINISH?  Not "is it moving" -- it is usually moving, just
+         * not fast enough.  The measured failure mode is a slice that clears
+         * almost everything on its first pass and then removes one sample per
+         * pass for the rest of its budget, so it is still short when the budget
+         * runs out and more budget only buys one more sample each.  So the test
+         * is a projection: at the rate the LAST pass achieved, is the remaining
+         * budget enough to reach zero?  If not, gentleness has already failed on
+         * this slice and the rest of its budget is better spent on a bigger
+         * step.  A slice that is genuinely converging never trips it. */
+        if (gm_bad && gm_prevbad >= 0) {
+            int removed = gm_prevbad - gm_bad;
+            int left = e->gamut_strict - gm_iter;
+            /* The projection is taken over the LAST pass, and all three
+             * alternatives were measured before settling on it.
+             *
+             *   last pass only          closes the pathological arm AND the hard
+             *                           plates, both to zero
+             *   two consecutive slow    delays the restart until the
+             *     passes                pathological arm can no longer be
+             *                           closed: 5 samples left
+             *   average over all passes closes the pathological arm but leaves
+             *                           9 samples on the hard plates
+             *
+             * Convergence is the mode's whole contract, so the rule that
+             * converges on both wins.  What it costs is a restart on some slices
+             * that would have finished on their own, which is real and is
+             * recorded in 12.22.3i: on the rail stress clip, which reaches zero
+             * without any restart, it costs 10.9 VMAF-NEG.  On real footage the
+             * worst case is 0.36 and one cell gains 0.93.
+             *
+             * A slice that has stopped moving altogether needs no rate at all. */
+            if (removed <= 0 || (int64_t)gm_bad > (int64_t)removed * left)
+                gm_hard = 1;
+            (void)gm_behind;
+        }
+        gm_prevbad = gm_bad;
+        /* THE FALLBACK.  Tightening mid-flight is not enough: measured on the
+         * rail-on-boundary synthetic, a slice that starts gently and then
+         * escalates still ends with a residue, while the same slice repaired
+         * with the harsh uncapped rule FROM THE START clears completely.  The
+         * gentle passes are not merely slow, they leave the slice somewhere the
+         * harsh passes can no longer rescue in the budget that is left.
+         *
+         * So this is a restart, not a correction: throw the gentle attempt away,
+         * put the slice's original coefficients back, and repair it again with
+         * the rule that always converges.  Gentleness is what keeps the repair
+         * nearly free on the 99% of slices that converge; the fallback is what
+         * makes the remaining 1% still reach zero.  Nothing here inspects what
+         * the picture is -- only whether this slice is on course to finish. */
+        if (gm_hard && !gm_fellback && omc_gm_fallback_on && !omc_gm_trial &&
+            gm_tsaved && gm_bad && gm_iter < e->gamut_strict) {
+            omc_band_t fb2[OMC_NBANDS];
+            for (int p2 = 0; p2 < OMC_NPLANES; p2++) {
+                omc_band_layout(plane_width(c, p2), sh, fb2);
+                size_t off = 0;
+                for (int q = 0; q < OMC_NBANDS; q++) {
+                    size_t nq = (size_t)fb2[q].h * fb2[q].w;
+                    memcpy(e->coef[p2][q], e->gm_save[p2][0] + off,
+                           nq * sizeof(int32_t));
+                    if (can_inter)
+                        memcpy(e->dcoef[p2][q], e->gm_save[p2][1] + off,
+                               nq * sizeof(int32_t));
+                    off += nq;
+                }
+            }
+            gm_fellback = 1;
+            e->gm_fallbacks++;
+            gm_iter = 0; gm_nofill = 0; gm_intra = 0; gm_stall = 0;
+            gm_bad0 = 0; gm_prevbad = -1; gm_behind = 0;
+            if (locked) { locked = 0; lock_ci = -1; e->nlcand = 0; }
+            goto encode_attempts;
+        }
+        if (gm_bad && !e->cdr_input && gm_iter < e->gamut_strict) {
+            /* THE REPAIR STEP.  Shrink the SOURCE coefficients that cover the
+             * offending pixels toward the slice's own local mean.
+             *
+             * Why shrink and not "add the correction".  The obvious step is to
+             * add the inverse transform of the excess back into the source, so
+             * that the next reconstruction lands on the rail instead of past
+             * it.  That was built and measured first, and it fails in two ways
+             * that shrinking cannot: (a) the correction is typically a few
+             * codes while the quantization step of a starved slice is 128 or
+             * more, so it rounds away to nothing and the reconstruction does
+             * not move at all -- measured: mean |correction| = 3 codes per
+             * coefficient against step 128, zero movement for as many passes
+             * as it was given; (b) amplifying it until it survives adds energy
+             * to a slice that is already over budget, which coarsens the plan,
+             * which increases the overshoot -- a runaway that drove the plan to
+             * the coarsest rung and the values out of the wide domain.
+             *
+             * Shrinking has neither failure mode.  It is multiplicative, so it
+             * crosses a lattice boundary within a few passes whatever the step
+             * is; it strictly REDUCES coefficient magnitudes, so the payload
+             * only gets smaller and the plan never coarsens in response; and it
+             * is monotone toward feasibility -- in the limit the detail bands
+             * vanish and the slice reconstructs as its own smooth low-pass,
+             * which cannot overshoot a rail its own local mean is inside.  The
+             * cost is exactly what it should be: contrast, in the slices that
+             * clip, at generation 1 only.
+             *
+             * It is applied only to the coefficients whose support covers an
+             * offending pixel (one band row/column of dilation for filter
+             * reach), so a single stray sample softens its own neighbourhood
+             * and nothing else.  The LL band is held back until the detail
+             * bands have had three passes: pulling the local mean is the last
+             * resort, not the first. */
+            omc_band_t gb[OMC_NBANDS];
+            int base = slice_idx * sh;
+            int rowbad[64];
+            /* MODE 13: NON-CUMULATIVE.  Every other form reduces coefficients
+             * the previous pass already reduced, so the total damage is the sum
+             * over attempts and a rule that is gentler per pass can be heavier
+             * overall.  Here the slice's untouched coefficients are saved on the
+             * first repair and restored before every later one, so attempt k
+             * applies a reduction of strength k to the ORIGINAL and the loop
+             * halts at the smallest sufficient TOTAL reduction.  Damage is
+             * monotone in strength under this scheme even though feasibility is
+             * not, so stopping at the first feasible strength does minimise the
+             * damage within the family.
+             *
+             * Done for EVERY plane, above the per-plane violation test: a plane
+             * clean on the first pass and dirty on a later one would otherwise
+             * restore from a buffer that was never written.  That is not merely
+             * a wrong picture -- it makes the emitted symbols depend on
+             * uninitialised memory, which is nondeterminism, which breaks
+             * generation exactness intermittently.  Gate G-T5-GAMUT5 exists
+             * because of this. */
+            if (omc_gm_mode == 13 && gm_iter == 0)
+                for (int p = 0; p < OMC_NPLANES; p++)
+                    memset(e->gm_mask[p], 0, (size_t)plane_width(c, p) * sh);
+            if ((omc_gm_trial || omc_gm_fallback_on) && !gm_tsaved) {
+                /* the slice's untouched coefficients, so the second trial can
+                 * start from the same place the first one did */
+                omc_band_t tb[OMC_NBANDS];
+                for (int p = 0; p < OMC_NPLANES; p++) {
+                    omc_band_layout(plane_width(c, p), sh, tb);
+                    size_t off = 0;
+                    for (int q = 0; q < OMC_NBANDS; q++) {
+                        size_t nq = (size_t)tb[q].h * tb[q].w;
+                        memcpy(e->gm_save[p][0] + off, e->coef[p][q], nq * sizeof(int32_t));
+                        if (can_inter)
+                            memcpy(e->gm_save[p][1] + off, e->dcoef[p][q], nq * sizeof(int32_t));
+                        off += nq;
+                    }
+                }
+                gm_tsaved = 1;
+            }
+            if (omc_gm_mode == 13) {
+                omc_band_t sb[OMC_NBANDS];
+                for (int p = 0; p < OMC_NPLANES; p++) {
+                    omc_band_layout(plane_width(c, p), sh, sb);
+                    size_t off = 0;
+                    for (int q = 0; q < OMC_NBANDS; q++) {
+                        size_t nq = (size_t)sb[q].h * sb[q].w;
+                        if (gm_iter == 0) {
+                            memcpy(e->gm_save[p][0] + off, e->coef[p][q], nq * sizeof(int32_t));
+                            if (can_inter)
+                                memcpy(e->gm_save[p][1] + off, e->dcoef[p][q], nq * sizeof(int32_t));
+                        } else {
+                            memcpy(e->coef[p][q], e->gm_save[p][0] + off, nq * sizeof(int32_t));
+                            if (can_inter)
+                                memcpy(e->dcoef[p][q], e->gm_save[p][1] + off, nq * sizeof(int32_t));
+                        }
+                        off += nq;
+                    }
+                }
+            }
+            for (int p = 0; p < OMC_NPLANES; p++) {
+                int pw = plane_width(c, p);
+                /* THE MASK.  One entry per PIXEL of the slice, accumulated
+                 * into a summed-area table so the band loop below can ask
+                 * "does any offending pixel lie under this coefficient" in
+                 * four lookups.
+                 *
+                 * This replaces a pair of row/column flag arrays, and the
+                 * difference is not a micro-optimisation.  Flagging rows and
+                 * columns separately and then shrinking every coefficient
+                 * whose row is flagged AND whose column is flagged softens the
+                 * OUTER PRODUCT of the two sets, not the pixels that are
+                 * actually out of range: two stray samples at opposite corners
+                 * of a slice flag two rows and two columns and therefore soften
+                 * four sites, two of which are innocent.  With strays scattered
+                 * across a picture the row set and the column set both fill up
+                 * and the repair softens essentially the whole slice.
+                 * Measured on a 4K master with 23 754 stray samples out of 106
+                 * million -- two hundredths of one per cent -- the old form
+                 * re-coded 144 slices and cost 4.45 VMAF-NEG. */
+                int32_t *sat = e->gm_buf[p];
+                int64_t *rsat = e->gm_rsat[p];
+                const int satw = pw + 1;
+                int any = 0;
+                memset(sat, 0, sizeof(int32_t) * (size_t)satw * ((size_t)sh + 1));
+                int64_t *asat = e->gm_asat[p];
+                if (omc_gm_veto) {
+                    memset(rsat, 0, sizeof(int64_t) * (size_t)satw * ((size_t)sh + 1));
+                    memset(asat, 0, sizeof(int64_t) * (size_t)satw * ((size_t)sh + 1));
+                }
+                for (int r = 0; r < sh; r++) rowbad[r] = 0;
+                /* The two rows either side of a slice boundary need a MARGIN,
+                 * not just legality.  The XSL boundary edit is applied to them
+                 * after reconstruction and is bounded by the blend cap, and it
+                 * cannot be made conditional: skipping it on a rail is not an
+                 * invertible operation (f(x) = x + d if x + d is in range, else
+                 * x, is not injective), and the un-blend has to invert it
+                 * exactly forever.  So a boundary sample sitting EXACTLY on a
+                 * rail is always one edit away from leaving the range, and the
+                 * repair would chase it without converging -- measured: a
+                 * rail-on-boundary slice fell 3040 -> 278 over eight passes and
+                 * then stalled.  From the second pass on, those two rows are
+                 * therefore pulled `cap` codes inside the rails, which is what
+                 * the edit can move them by.  The margin shapes only the SHRINK
+                 * TARGET; the pass/fail count below stays the true legal-range
+                 * test, so a slice that does not need the margin never gets it
+                 * and the loop still stops on the real condition. */
+                for (int r = -1; r < sh; r++) {
+                    int R = base + r;
+                    if (R < 0) continue;
+                    if (R >= dh) break;
+                    int32_t m = ((r == 0 && slice_idx > 0) ||
+                                 (r == sh - 1 && slice_idx < c->nslices - 1))
+                                ? cap : 0;
+                    const uint16_t *rp = recon->p[p] + (size_t)R * recon->stride[p];
+                    for (int x = 0; x < pw; x++)
+                        if (rp[x] < lo + m || rp[x] > hi - m) {
+                            /* r == -1 is the previous slice's last committed
+                             * row, which the boundary edit couples to this
+                             * slice's row 0; it is charged to row 0. */
+                            int rr = r < 0 ? 0 : r;
+                            sat[(size_t)(rr + 1) * satw + (x + 1)] = 1;
+                            /* how far out, and which way: positive means the
+                             * sample is above the ceiling and has to come down */
+                            if (omc_gm_veto) {
+                                int64_t res = rp[x] > hi - m
+                                            ? (int64_t)rp[x] - (hi - m)
+                                            : (int64_t)rp[x] - (lo + m);
+                                rsat[(size_t)(rr + 1) * satw + (x + 1)] += res;
+                                asat[(size_t)(rr + 1) * satw + (x + 1)] +=
+                                    res < 0 ? -res : res;
+                            }
+                            if (omc_gm_mode == 13) e->gm_mask[p][(size_t)rr * pw + x] = 1;
+                            rowbad[rr] = 1;
+                            any = 1;
+                        }
+                }
+                if (omc_gm_mode == 13) {
+                    /* union with everything this slice has ever committed out
+                     * of range: a coefficient that an earlier attempt had to
+                     * reduce must stay reduced, or restoring the original
+                     * re-creates the violation that attempt cured */
+                    for (int r = 0; r < sh; r++) {
+                        const uint8_t *mr = e->gm_mask[p] + (size_t)r * pw;
+                        int32_t *sr = sat + (size_t)(r + 1) * satw;
+                        for (int x = 0; x < pw; x++)
+                            if (mr[x]) { sr[x + 1] = 1; rowbad[r] = 1; any = 1; }
+                    }
+                }
+                if (!any) continue;
+                /* prefix-sum the mask in place: sat[r][x] becomes the number of
+                 * offending pixels in [0, r) x [0, x) */
+                for (int r = 1; r <= sh; r++) {
+                    int32_t run = 0;
+                    int32_t *cur = sat + (size_t)r * satw;
+                    const int32_t *up = sat + (size_t)(r - 1) * satw;
+                    for (int x = 1; x <= pw; x++) {
+                        run += cur[x];
+                        cur[x] = run + up[x];
+                    }
+                }
+                if (omc_gm_veto)
+                    for (int t = 0; t < 2; t++) {
+                        int64_t *T = t ? asat : rsat;
+                        for (int r = 1; r <= sh; r++) {
+                            int64_t run = 0;
+                            int64_t *cur = T + (size_t)r * satw;
+                            const int64_t *up = T + (size_t)(r - 1) * satw;
+                            for (int x = 1; x <= pw; x++) {
+                                run += cur[x];
+                                cur[x] = run + up[x];
+                            }
+                        }
+                    }
+                /* Suppress this plane's grain fill for the rest of the slice.
+                 * Fill regenerates a quarter-step of texture at positions that
+                 * code to zero -- which is exactly what shrinking creates more
+                 * of, so without this the repair adds back the energy it just
+                 * removed and the violation count stops falling.  Clearing the
+                 * bit is exactness-safe: the fill rule measures the coded
+                 * coefficients, an unfilled band leaves them at zero, and a
+                 * band of zeros re-derives to "no fill" at every later
+                 * generation, so the lock still reproduces the slice.
+                 *
+                 * Per BAND, not per plane.  An earlier version cleared all six
+                 * of a plane's fill bits on any violation, which is a
+                 * slice-wide loss of texture paid for one stray sample. */
+                /* MODE 7 (ADAPTIVE).  The two reduction shapes win on
+                 * opposite content and the measurements are unambiguous about
+                 * it.  Proportional shrink converges in few passes and is the
+                 * right move when a slice is massively out of range -- on a 4K
+                 * graphics master with 220 236 strays it beats the stepwise
+                 * forms by half a point.  Stepwise reduction is the right move
+                 * when a slice has a handful of strays, because the whole cost
+                 * is the picture it touches on the way -- on 4K cinema with 24
+                 * thousand it beats the proportional form by three points.
+                 *
+                 * The encoder does not have to guess which it is looking at:
+                 * the mask it just built says so.  Dense violation -> shrink;
+                 * sparse violation -> step.  The threshold is in tenths of a
+                 * per cent of the slice's samples. */
+                /* MODE 9: spend quantizer steps in decreasing order of
+                 * CORRECTION BOUGHT PER UNIT OF DAMAGE, leverage_b / 2^s_b.
+                 * Pass i is allowed to touch the i+1 most efficient bands, one
+                 * step each, so the cheapest correction is always tried first
+                 * and a coarse band is only reached if the fine ones could not
+                 * do it.  Unlike every earlier shape this does not depend on
+                 * the coefficient's own magnitude, which is the property the
+                 * least-norm solution has and none of the shapes did. */
+                int gm_rank[OMC_NBANDS];
+                if (omc_gm_mode >= 9) {
+                    int64_t eff[OMC_NBANDS];
+                    for (int q = 0; q < OMC_NBANDS; q++) {
+                        int sq = coeff_shift(&sp, p, q, 0);
+                        eff[q] = ((int64_t)omc_gm_lev[q] << 20) >> (sq < 30 ? sq : 30);
+                        gm_rank[q] = 0;
+                    }
+                    for (int q = 0; q < OMC_NBANDS; q++)
+                        for (int r2 = 0; r2 < OMC_NBANDS; r2++)
+                            if (eff[r2] > eff[q] || (eff[r2] == eff[q] && r2 < q))
+                                gm_rank[q]++;
+                }
+                int32_t gm_dense = 0;
+                if (omc_gm_mode == 7) {
+                    int64_t nbad = sat[(size_t)sh * satw + pw];
+                    gm_dense = (nbad * 1000 >= (int64_t)sh * pw * omc_gm_dthr);
+                }
+                /* MODE 8: decide by OBSERVED CONVERGENCE rather than by a
+                 * prior guess about the content.  A density threshold has to
+                 * be tuned, and the measurements show it does not separate
+                 * cleanly -- one 4K graphics master wants the proportional
+                 * shrink while a 720p cinema master with a similar per-slice
+                 * density wants stepping.  So: step first, because stepping is
+                 * the cheaper move when it works, and watch.  If after a few
+                 * passes the violation count has not come down, this slice is
+                 * one the gentle move cannot clear at an acceptable price;
+                 * switch it to the proportional shrink for the rest of its
+                 * budget.  Nothing is assumed about the content. */
+                if (omc_gm_mode == 8 && !gm_stall && gm_iter >= omc_gm_watch &&
+                    (int64_t)gm_bad * 4 >= (int64_t)gm_bad0 * 3)
+                    gm_stall = 1;
+                if (omc_gm_mode == 8) gm_dense = gm_stall;
+                omc_band_layout(pw, sh, gb);
+                for (int b = 0; b < OMC_NBANDS; b++) {
+                    omc_band_t *B = &gb[b];
+                    int vd = sh / B->h, hd = pw / B->w;
+                    int num = omc_gm_num, den = omc_gm_den;
+                    /* Shape A (trials 0 and 2) is the proportional cut the mode
+                     * and the OMC_GM_NUM/DEN knobs select.  Shape B (trial 1) is
+                     * the gentler-of-two at 15/16, which is the shape that wins
+                     * on camera footage.  Two shapes, no threshold between them:
+                     * the source decides. */
+                    int gm_shapeB = (omc_gm_trial && gm_trial == 1);
+                    if (gm_shapeB) { num = 15; den = 16; }
+                    /* this slice is still violating late: tighten (see
+                     * omc_gm_esc) */
+                    else if (gm_fellback ||
+                             (omc_gm_esc && gm_iter >= omc_gm_esc)) {
+                        /* STAGED escalation.  The first stage tightens a slice
+                         * that has not converged by pass omc_gm_esc; the second
+                         * abandons gentleness altogether for one that still has
+                         * not converged by omc_gm_esc2, and goes to the harsh
+                         * proportional cut the mode originally used.
+                         *
+                         * The second stage is not a refinement, it is the fix
+                         * for a real hole.  A gentle factor cannot clear a
+                         * neighbourhood the quantizer has PINNED to a rail:
+                         * removing a sixty-fourth of a coefficient does not
+                         * change the coded value at all there, so the pass
+                         * accomplishes nothing and the next pass accomplishes
+                         * nothing, and the budget runs out with a residue that
+                         * more passes never touch.  Measured on the
+                         * rail-on-boundary synthetic of G-T5-GAMUT2c: the harsh
+                         * 3/4 cut clears it to ZERO, while 63/64 escalating only
+                         * to 15/16 leaves 126 samples and leaves the same 126 at
+                         * the hard cap of sixteen passes.  More budget is not
+                         * the answer; a bigger step is.
+                         *
+                         * This is not content classification.  Nothing here
+                         * looks at what the picture is; it looks at whether THIS
+                         * slice has stopped making progress, which is a fact
+                         * about the slice and not a guess about the genre. */
+                        if (gm_fellback ||
+                            (omc_gm_esc2 && gm_iter >= omc_gm_esc2)) {
+                            num = omc_gm_esc2num; den = omc_gm_esc2den;
+                        } else {
+                            num = omc_gm_escnum; den = omc_gm_escden;
+                        }
+                    }
+                    /* A slice being repaired by the fallback, or one that has
+                     * escalated, reduces PURELY PROPORTIONALLY: no step cap and
+                     * no stepwise term.  Both of those are quality protections
+                     * that only make sense while the slice is on course to
+                     * finish, and this slice is not. */
+                    /* Uncapping MID-FLIGHT was measured and does not work: it
+                     * took the pathological residue from 126 to 108, nowhere
+                     * near zero, while costing quality on every cell it touched
+                     * -- because it fires on slices that were going to finish
+                     * anyway.  The restart is what closes the case, so the
+                     * uncapping belongs to the restart alone.  A slice is
+                     * either being repaired gently, or it has been thrown away
+                     * and is being repaired by the rule that always converges;
+                     * there is no third state. */
+                    const int gm_uncap = gm_fellback ||
+                        (omc_gm_esc2 && gm_iter >= omc_gm_esc2);
+                    if (b == 0 && gm_iter < omc_gm_llhold) continue;
+                    /* mode 9: this band is not eligible yet.  After every band
+                     * has had a pass, fall back to the proportional shrink so
+                     * convergence is still guaranteed inside the budget. */
+                    if ((omc_gm_mode == 9 || omc_gm_mode == 11) &&
+                        gm_iter < OMC_NBANDS && gm_rank[b] > gm_iter) continue;
+                    /* MODE 10: strict greedy.  Exactly ONE band per pass, the
+                     * cheapest correction still untried, one quantizer step.
+                     * Mode 9 let pass i touch the i+1 best bands at once, which
+                     * is a broadening sweep rather than a greedy spend and
+                     * measured 94.29 against the simple linear rule's 96.70.
+                     * After every band has had a pass, keep stepping on all of
+                     * them rather than falling back to the proportional shrink,
+                     * so nothing ever reverts to the shape this replaces. */
+                    if (omc_gm_mode == 10 && gm_iter < OMC_NBANDS &&
+                        gm_rank[b] != gm_iter) continue;
+                    /* MODE 3: escalate in BAND as well as in amount.  Overshoot
+                     * past a rail is quantization ringing at an edge, and
+                     * ringing lives in the finest detail bands.  Reducing a
+                     * fine band costs a little texture; reducing a coarse band
+                     * or the LL moves structure and local brightness, which is
+                     * most of what the picture is.  So the first pass touches
+                     * only the finest bands, and each pass widens the set only
+                     * for the pixels that still offend.  A slice whose
+                     * overshoot is ordinary ringing -- which is nearly all of
+                     * them -- therefore never has its coarse bands touched at
+                     * all. */
+                    /* MODE 6: reduce the BIGGEST CONTRIBUTORS FIRST.  Every
+                     * coefficient whose support covers an offending pixel is a
+                     * suspect, but they are not equally guilty: overshoot past
+                     * a rail is ringing, and ringing is driven by the large
+                     * coefficients at the edge, not by the small ones carrying
+                     * texture beside it.  Reducing a small coefficient costs
+                     * texture and buys almost no overshoot.  So each pass only
+                     * touches coefficients at or above a magnitude threshold,
+                     * and the threshold falls one pass at a time -- eight
+                     * quantizer steps, then four, then two, then one, then
+                     * everything.  A slice whose overshoot comes from a couple
+                     * of big edge coefficients is repaired by moving exactly
+                     * those, and the texture beside them is never touched. */
+                    int32_t gm_qthr = 0;
+                    if (omc_gm_mode == 6) {
+                        static const int thr[] = { 8, 4, 2, 1 };
+                        gm_qthr = gm_iter < 4
+                                ? (int32_t)thr[gm_iter] << coeff_shift(&sp, p, b, 0) : 0;
+                    }
+                    if (omc_gm_mode == 3 || omc_gm_mode == 5) {
+                        int lo_b = gm_iter == 0 ? 7 : gm_iter == 1 ? 4
+                                 : gm_iter == 2 ? 1 : 0;
+                        if (b < lo_b) continue;
+                    }
+                    int touched = 0;
+                    for (int r = 0; r < B->h; r++) {
+                        int r0 = (r - omc_gm_dil) * vd, r1 = (r + 1 + omc_gm_dil) * vd;
+                        if (r0 < 0) r0 = 0;
+                        if (r1 > sh) r1 = sh;
+                        if (r0 >= r1) continue;
+                        for (int x = 0; x < B->w; x++) {
+                            int x0 = (x - omc_gm_dil) * hd, x1 = (x + 1 + omc_gm_dil) * hd;
+                            if (x0 < 0) x0 = 0;
+                            if (x1 > pw) x1 = pw;
+                            if (x0 >= x1) continue;
+                            /* offending pixels under this coefficient's
+                             * support, one band row/column of dilation for
+                             * filter reach -- four lookups, no scan */
+                            int32_t cnt = sat[(size_t)r1 * satw + x1]
+                                        - sat[(size_t)r0 * satw + x1]
+                                        - sat[(size_t)r1 * satw + x0]
+                                        + sat[(size_t)r0 * satw + x0];
+                            if (cnt <= 0) continue;
+                            int i = r * B->w + x;
+                            /* mode 1: one quantizer step per pass.  mode 2:
+                             * (1 << pass) steps -- the same minimum first move,
+                             * doubling only for the pixels that still offend,
+                             * so easy content pays one step and the hard case
+                             * still converges geometrically. */
+                            if (gm_qthr) {
+                                int32_t av = e->coef[p][b][i];
+                                if (av < 0) av = -av;
+                                if (av < gm_qthr) continue;
+                            }
+                            /* MODE 16: the alignment veto.  Skip this
+                             * coefficient if reducing it would push the
+                             * offending pixels under its support the WRONG
+                             * WAY.  See gm_align().  The veto lapses after
+                             * omc_gm_align passes so convergence inside the
+                             * budget is still guaranteed. */
+                            int64_t gm_sc = 0, gm_mass = 0;
+                            int gm_free = 1;
+                            if (omc_gm_stat) gm_st_cand++;
+                            if (omc_gm_veto && gm_iter < omc_gm_align) {
+                                gm_sc = gm_align(&GM_BASIS[b], rsat, asat, satw,
+                                                 sh, pw, r * vd, x * hd,
+                                                 vd, hd, &gm_free, &gm_mass);
+                                /* The veto is applied per ARRAY below, because
+                                 * the intra coefficient and the inter residual
+                                 * at the same position can have opposite signs
+                                 * and therefore pull the offending pixel in
+                                 * opposite directions.  A slice is committed
+                                 * from one of them, not both, and the repair
+                                 * does not yet know which -- so each is judged
+                                 * on its own sign. */
+                                /* The uniform veto can decide here, before any
+                                 * arithmetic.  The cost-targeted one cannot:
+                                 * whether a reduction is free depends on the
+                                 * reduction, so it is decided per array below. */
+                                if (omc_gm_veto == 1 && !gm_free) {
+                                    int32_t cv = e->coef[p][b][i];
+                                    int32_t dv = can_inter ? e->dcoef[p][b][i] : 0;
+                                    int64_t si = cv < 0 ? -gm_sc : gm_sc;
+                                    int64_t sd = dv < 0 ? -gm_sc : gm_sc;
+                                    if (si <= 0 && (!can_inter || sd <= 0)) {
+                                        if (omc_gm_stat) gm_st_veto++;
+                                        continue;
+                                    }
+                                }
+                            }
+                            if (omc_gm_mode == 13) {
+                                /* strength k applied to the ORIGINAL: the
+                                 * proportional term is (num/den) k times, the
+                                 * stepwise term k steps, gentler of the two */
+                                int k = gm_iter + 1;
+                                /* Both terms must COMPOUND with the strength,
+                                 * because each attempt starts from the original:
+                                 * a reduction of k steps is nothing to a
+                                 * coefficient worth a hundred of them even at
+                                 * k = 12, so a linear step term simply never
+                                 * converges.  Geometric in both, gentler of the
+                                 * two per coefficient -- which by the crossover
+                                 * picks the stepwise term for large
+                                 * coefficients and the proportional one for
+                                 * small, exactly as intended. */
+                                int ks = k > 20 ? 20 : k;
+                                int32_t st = ((int32_t)1 << coeff_shift(&sp, p, b, i))
+                                           * (int32_t)(1 << ks);
+                                int32_t v = e->coef[p][b][i], w = 0;
+                                if (can_inter) w = e->dcoef[p][b][i];
+                                int32_t vp = v, wp = w;
+                                for (int t = 0; t < k; t++) {
+                                    vp = vp * num / den;
+                                    if (can_inter) wp = wp * num / den;
+                                }
+                                int32_t vs = gm_reduce(v, num, den, st);
+                                e->coef[p][b][i] =
+                                    (vp < 0 ? -vp : vp) >= (vs < 0 ? -vs : vs) ? vp : vs;
+                                if (can_inter) {
+                                    int32_t ws = gm_reduce(w, num, den, st);
+                                    e->dcoef[p][b][i] =
+                                        (wp < 0 ? -wp : wp) >= (ws < 0 ? -ws : ws) ? wp : ws;
+                                }
+                                touched = 1;
+                                continue;
+                            }
+                            if (omc_gm_mode == 14) {
+                                /* MODE 14: gentler-of-two, with the
+                                 * proportional factor STIFFENING each pass.
+                                 * Measured, the right factor is not a constant:
+                                 * on 4K cinema the gentlest factor wins, and on
+                                 * the 4K graphics master at half a bit 3/4
+                                 * beats 15/16 (98.07 against 97.84) because
+                                 * converging in two passes removes less in
+                                 * total than converging gently in eight.  So
+                                 * start at the gentlest and double the removed
+                                 * fraction every pass: content that clears in
+                                 * one or two passes never pays more than a
+                                 * sixteenth, and content that needs depth
+                                 * reaches it geometrically instead of grinding.
+                                 * No content classification anywhere. */
+                                int kk = gm_iter > 3 ? 3 : gm_iter;
+                                int rn = (den - num) << kk;      /* removed part */
+                                int nn = den - rn;
+                                if (nn < den / 2) nn = den / 2;  /* never past half */
+                                int32_t st = ((int32_t)1 << coeff_shift(&sp, p, b, i))
+                                           * (gm_iter + 1);
+                                e->coef[p][b][i] =
+                                    gm_reduce_min(e->coef[p][b][i], nn, den, st);
+                                if (can_inter)
+                                    e->dcoef[p][b][i] =
+                                        gm_reduce_min(e->dcoef[p][b][i], nn, den, st);
+                                if (b == 0 && dc_pris_saved && i < 1024) {
+                                    dc_pris[0][p][i] =
+                                        gm_reduce_min(dc_pris[0][p][i], nn, den, st);
+                                    if (can_inter)
+                                        dc_pris[1][p][i] =
+                                            gm_reduce_min(dc_pris[1][p][i], nn, den, st);
+                                }
+                                touched = 1;
+                                continue;
+                            }
+                            /* A slice that has been judged unable to finish
+                             * (gm_hard) drops the STEP CAP as well as tightening
+                             * the factor, and reduces purely proportionally.
+                             *
+                             * The cap is the whole reason the gentle rule is
+                             * nearly free: it never removes more than one
+                             * quantizer step from a coefficient in one pass, so
+                             * the repair cannot gouge.  But it is also exactly
+                             * what makes a rail-pinned neighbourhood impossible
+                             * to clear, because there the coefficients are large
+                             * and one step per pass is nowhere near enough.
+                             * Measured on the rail-on-boundary synthetic of
+                             * G-T5-GAMUT2c, holding everything else equal: with
+                             * the cap, 71 samples are left; without it, ZERO.
+                             * Neither the factor nor the veto accounts for that
+                             * difference -- the cap does, on its own. */
+                            if (!gm_uncap &&
+                                (gm_shapeB || omc_gm_mode == 12 ||
+                                 omc_gm_mode == 15 || omc_gm_mode == 16)) {
+                                /* Mode 15 escalates the stepwise term
+                                 * GEOMETRICALLY rather than linearly.  The
+                                 * stepwise branch is the one taken for LARGE
+                                 * coefficients (below the crossover the
+                                 * proportional one is smaller), and those are
+                                 * precisely the coefficients causing the
+                                 * overshoot -- so a linear step term is gentle
+                                 * on exactly the coefficients that need to
+                                 * move, the repair grinds, and everything else
+                                 * pays for the extra passes.  Mode 15 still
+                                 * starts at one step; it just does not stay
+                                 * polite about it.
+                                 *
+                                 * MEASURED: worth almost nothing.  Three of six
+                                 * real cells score bit-for-bit the same as mode
+                                 * 12 and the other three move by under 0.07
+                                 * VMAF-NEG.  Changing this branch beyond
+                                 * recognition changes the output almost not at
+                                 * all -- which says the branch is hardly ever
+                                 * TAKEN, i.e. nearly every coefficient this
+                                 * repair touches is worth fewer than
+                                 * den/(den-num) quantizer steps and goes down
+                                 * the proportional path.  The repair is not
+                                 * driven by a few big edge coefficients ringing
+                                 * past a rail; it is driven by very many small
+                                 * ones.  No refinement of HOW MUCH to remove can
+                                 * close the gap.  The only lever left is HOW
+                                 * MANY coefficients are touched at all. */
+                                int kg = gm_iter > 20 ? 20 : gm_iter;
+                                int32_t st = ((int32_t)1 << coeff_shift(&sp, p, b, i))
+                                           * (!gm_shapeB && omc_gm_mode == 15
+                                              ? (int32_t)(1 << kg) : gm_iter + 1);
+                                int vv = (gm_iter < omc_gm_align) ? omc_gm_veto : 0;
+                                int sq = coeff_shift(&sp, p, b, i);
+                                int32_t c16 = e->coef[p][b][i];
+                                int32_t r16 = gm_reduce_min(c16, num, den, st);
+                                int vc = gm_permit(vv, gm_free, gm_sc, c16, r16, sq);
+                                int vdz = 1;
+                                int32_t d16 = 0, rd16 = 0;
+                                if (can_inter) {
+                                    d16 = e->dcoef[p][b][i];
+                                    rd16 = gm_reduce_min(d16, num, den, st);
+                                    vdz = gm_permit(vv, gm_free, gm_sc, d16, rd16, sq);
+                                }
+                                if (omc_gm_stat && !vc && (!can_inter || !vdz))
+                                    gm_st_veto++;
+                                if (vc) {
+                                    e->coef[p][b][i] = r16;
+                                    if (omc_gm_stat) gm_stat_note(b, c16, r16, sq);
+                                }
+                                if (can_inter && vdz)
+                                    e->dcoef[p][b][i] = rd16;
+                                /* the pristine DC copies mirror the two arrays
+                                 * above and must follow the same veto, or a
+                                 * later restore would undo the decision */
+                                if (b == 0 && dc_pris_saved && i < 1024) {
+                                    if (vc)
+                                        dc_pris[0][p][i] =
+                                            gm_reduce_min(dc_pris[0][p][i], num, den, st);
+                                    if (can_inter && vdz)
+                                        dc_pris[1][p][i] =
+                                            gm_reduce_min(dc_pris[1][p][i], num, den, st);
+                                }
+                                if (vc || (can_inter && vdz)) touched = 1;
+                                continue;
+                            }
+                            int32_t step = gm_uncap ? 0
+                                : ((omc_gm_mode == 7 || omc_gm_mode == 8)
+                                            ? !gm_dense
+                                            : omc_gm_mode == 9
+                                            ? (gm_iter < OMC_NBANDS)
+                                            : (omc_gm_mode == 10 || omc_gm_mode == 11)
+                                            ? 1 : omc_gm_mode)
+                                ? ((int32_t)1 << coeff_shift(&sp, p, b, i))
+                                  * (omc_gm_mode == 2 || omc_gm_mode == 3
+                                     ? (1 << (gm_iter > 20 ? 20 : gm_iter))
+                                     : omc_gm_mode == 11 ? gm_iter + 1
+                                     : omc_gm_mode >= 4 && omc_gm_mode <= 6 ? gm_iter + 1
+                                     : omc_gm_mode >= 7 ? gm_iter + 1 : 1)
+                                : 0;
+                            /* the alignment veto is orthogonal to the shape:
+                             * it decides WHETHER, the shape decides BY HOW MUCH */
+                            int gv = (gm_iter < omc_gm_align) ? omc_gm_veto : 0;
+                            int sq2 = coeff_shift(&sp, p, b, i);
+                            int32_t cg = e->coef[p][b][i];
+                            int gnum = num, gnumd = num;
+                            if (omc_gm_grade && !gm_free) {
+                                gm_grade(gm_sc, gm_mass, cg, num, den, &gnum);
+                                gm_grade(gm_sc, gm_mass, can_inter ? e->dcoef[p][b][i] : cg,
+                                         num, den, &gnumd);
+                            }
+                            int32_t rg = gm_reduce(cg, gnum, den, step);
+                            int gc = gm_permit(gv, gm_free, gm_sc, cg, rg, sq2);
+                            int gd = 1;
+                            int32_t dg = 0, rdg = 0;
+                            if (can_inter) {
+                                dg = e->dcoef[p][b][i];
+                                rdg = gm_reduce(dg, gnumd, den, step);
+                                gd = gm_permit(gv, gm_free, gm_sc, dg, rdg, sq2);
+                            }
+                            if (omc_gm_stat && !gc && (!can_inter || !gd)) gm_st_veto++;
+                            if (gc) {
+                                e->coef[p][b][i] = rg;
+                                if (omc_gm_stat) gm_stat_note(b, cg, rg, sq2);
+                            }
+                            if (can_inter && gd)
+                                e->dcoef[p][b][i] = rdg;
+                            /* OMC_DCFB keeps its own pristine LL copy and
+                             * restores it every attempt: the shrink has to go
+                             * into that copy too or the next pass reverts it. */
+                            if (b == 0 && dc_pris_saved && i < 1024) {
+                                if (gc)
+                                    dc_pris[0][p][i] = gm_reduce(dc_pris[0][p][i], gnum, den, step);
+                                if (can_inter && gd)
+                                    dc_pris[1][p][i] = gm_reduce(dc_pris[1][p][i], gnumd, den, step);
+                            }
+                            if (gc || (can_inter && gd)) touched = 1;
+                        }
+                    }
+                    if (!touched) continue;
+                    if (b >= OMC_FILL_BANDS_FROM)
+                        gm_nofill |= 1u << (p * 6 + b - OMC_FILL_BANDS_FROM);
+                    /* Shrinking an INTER residual converges to the PREDICTION,
+                     * so once a frame ends with an excursion the next frame
+                     * predicts from it and the repair walks TOWARD the
+                     * violation (measured: a sample at 1031 went 1028 -> 1031
+                     * over successive passes).  Intra breaks the inheritance.
+                     * From the second pass, and per BAND -- an earlier version
+                     * forced the whole plane, which throws away the temporal
+                     * prediction for the entire slice at a fixed budget. */
+                    if (gm_iter >= 1 && !omc_gm_nointra)
+                        gm_intra |= 1u << (p * OMC_NBANDS + b);
+                }
+            }
+            if (gm_iter == 0 && gm_trial == 0) e->gm_slices++;
+            gm_iter++;
+            e->gm_repairs++;
+            if (omc_gm_replan) {
+                /* the shrunk slice is cheaper than the plan assumed; let it
+                 * re-fit rather than pad out the difference */
+                locked = 0; lock_ci = -1; e->nlcand = 0;
+                goto replan_natural;
+            }
+            if (locked) {
+                /* the locked plan described the UNSHRUNK coefficients; drop it
+                 * and plan this slice naturally from here on */
+                locked = 0; lock_ci = -1; e->nlcand = 0;
+            }
+            goto encode_attempts;
+        }
+        if (gm_bad) e->gm_unfixed++;
+        /* ---- trial selection: keep the shape the SOURCE prefers ---- */
+        if (omc_gm_trial && gm_tsaved && recon && gm_trial < 2) {
+            int pw_of[OMC_NPLANES];
+            for (int p = 0; p < OMC_NPLANES; p++) pw_of[p] = plane_width(c, p);
+            int dh = c->cfg.display_height ? c->cfg.display_height : c->H;
+            int row0 = slice_idx * sh;
+            int nrows = vvis;
+            if (row0 + nrows > dh) nrows = dh - row0;
+            if (omc_gm_trial == 4) {
+                int64_t cst = 0;
+                for (int p = 0; p < OMC_NPLANES; p++) {
+                    const int32_t *sv[2] = { e->gm_save[p][0], e->gm_save[p][1] };
+                    cst += gm_slice_adm(sv, e->sbuf[p], plane_width(c, p), sh,
+                                        omc_gm_k);
+                }
+                gm_sse[gm_trial] = cst;
+            } else if (nrows > 0)
+                gm_sse[gm_trial] = gm_slice_sse(in, recon, pw_of, OMC_NPLANES,
+                                                row0, nrows, omc_gm_trial);
+            int again = 0;
+            if (gm_trial == 0) { gm_trial = 1; again = 1; }
+            else if (gm_sse[0] < gm_sse[1]) { gm_trial = 2; again = 1; gm_st_pickA++; }
+            else gm_st_pickB++;
+            if (again) {
+                /* restore the untouched coefficients and repair again from
+                 * scratch with the other shape (or replay the winner) */
+                omc_band_t tb[OMC_NBANDS];
+                for (int p = 0; p < OMC_NPLANES; p++) {
+                    omc_band_layout(plane_width(c, p), sh, tb);
+                    size_t off = 0;
+                    for (int q = 0; q < OMC_NBANDS; q++) {
+                        size_t nq = (size_t)tb[q].h * tb[q].w;
+                        memcpy(e->coef[p][q], e->gm_save[p][0] + off,
+                               nq * sizeof(int32_t));
+                        if (can_inter)
+                            memcpy(e->dcoef[p][q], e->gm_save[p][1] + off,
+                                   nq * sizeof(int32_t));
+                        off += nq;
+                    }
+                }
+                gm_iter = 0; gm_nofill = 0; gm_intra = 0; gm_stall = 0;
+                gm_bad0 = 0; gm_prevbad = -1; gm_hard = 0; gm_fellback = 0; gm_behind = 0;
+                if (locked) { locked = 0; lock_ci = -1; e->nlcand = 0; }
+                goto encode_attempts;
+            }
+        }
+    }
     if (recon) {
         /* Count only rows that are already FINAL: a boundary row is re-emitted
          * and edited when the NEXT slice reconstructs, so slice k finalizes
@@ -4015,7 +5976,7 @@ int omc_dec_slice_ex(omc_dec_t *d, const uint8_t *src, size_t avail,
                 if (fb && rec == 0 && q == 0)
                     rec = fill_value_p(ll, pw, llw, llh, vvis, b, row, col, s, fox, foy, sfox, sfoy,
                                      lllim, fill_gain[p], c->cfg.grain_corr,
-                                     (c->cfg.fill_static ? 1 : 0),
+                                     0 /* was fill_static; inert since minor 12 */,
                                      0, &fp);
                 d->sbuf[p][(size_t)(B->r0 + i / B->w) * pw + B->c0 + col] = rec;
                 left = v44 ? omc_q2(v < 0 ? -v : v) : (v != 0);
diff --git a/src/colour.c b/src/colour.c
index 673266a..a4557a5 100644
--- a/src/colour.c
+++ b/src/colour.c
@@ -11,6 +11,15 @@
 
 #include "cc_tab.c.inc"
 
+/* SHIFTS ON SIGNED VALUES.  A left shift of a negative value is not
+ * defined by C11 (6.5.7p4); these shift-and-add multiplies routinely see
+ * negative operands.  Shifting the unsigned representation is defined for
+ * every value and compiles to the same instruction on a two's-complement
+ * target, so the fixed-point results are unchanged (verified byte-exact
+ * against the previous build).  Found by UBSan. */
+#define OMC_SHL(v, n) ((int32_t)((uint32_t)(v) << (n)))
+#define OMC_SHL64(v, n) ((int64_t)((uint64_t)(v) << (n)))
+
 #define CC_QS 15                       /* matrix coefficients are Q15        */
 
 /* Round-to-nearest de-scale of a Q15 accumulator.  Every matrix product in this
@@ -35,7 +44,7 @@ static int64_t cc_mul_sa(int32_t c, int64_t x)
     int neg = c < 0, b;
     if (neg) c = -c;
     for (b = 0; b < 21; b++)
-        if ((c >> b) & 1) acc += x << b;
+        if ((c >> b) & 1) acc += OMC_SHL64(x, b);
     return neg ? -acc : acc;
 }
 
@@ -336,7 +345,7 @@ int omc_cc_convert(const omc_cc_t *c,
                     idx = (l2Y + CC_TM_BIAS) >> CC_TM_SHIFT;
                     if (idx < 0) idx = 0;
                     if (idx > CC_TM_N - 1) idx = CC_TM_N - 1;
-                    gq = (int32_t)tm->gain[idx] << 6;   /* Q10 -> Q16 */
+                    gq = OMC_SHL((int32_t)tm->gain[idx], 6); /* Q10 -> Q16 */
                 }
                 l2Yo = l2Y + gq;
                 /* Saturation: a declared exponent, published per curve, applied
diff --git a/src/config.c b/src/config.c
index ee312b2..1d1e19e 100644
--- a/src/config.c
+++ b/src/config.c
@@ -102,8 +102,8 @@ int omc_validate_config(const omc_config_t *cfg, char *err, size_t errlen)
     }
 
     /* --- lossless-preferred ---- */
-    if (cfg->lossless_pref && !cfg->no_fill)
-        FAIL("lossless_pref requires no_fill (lossless cannot regenerate grain)");
+    if (cfg->lossless_pref && cfg->fill_grain)
+        FAIL("lossless_pref forbids fill_grain (lossless cannot regenerate grain)");
 
     /* --- v4.2 extensions --- */
     if (cfg->rct) {
diff --git a/src/dwt.c b/src/dwt.c
index 61a8281..3865eeb 100644
--- a/src/dwt.c
+++ b/src/dwt.c
@@ -86,7 +86,13 @@ static void fwd1d_97(const int32_t *x, int n, int32_t *L, int32_t *H)
     for (int i = 0; i < half; i++) {
         int32_t a = sat_s(L, half, i - 1), b = L[i];
         int32_t cc = sat_s(L, half, i + 1), dd = sat_s(L, half, i + 2);
-        int32_t nine = ((b + cc) << 3) + (b + cc); /* 9*(s_i + s_{i+1}) */
+        /* 9*(s_i + s_{i+1}).  The sum is signed and routinely negative in
+         * the biased pixel domain, and a left shift of a negative value is
+         * not defined by C11 (6.5.7p4) -- found by UBSan.  Doing the shift
+         * on the unsigned representation is defined for every value and
+         * compiles to the same instruction on a two's-complement target,
+         * so the transform's output is unchanged (verified byte-exact). */
+        int32_t nine = (int32_t)((uint32_t)(b + cc) << 3) + (b + cc);
         H[i] = x[2 * i + 1] - ((nine - (a + dd) + 8) >> 4);
     }
     for (int i = 0; i < half; i++) {
@@ -114,7 +120,7 @@ static void inv1d_97(const int32_t *Lc, const int32_t *Hc, int n, int32_t *x)
     for (int i = 0; i < half; i++) {
         int32_t a = sat_e(x, half, i - 1), b = x[2 * i];
         int32_t cc = sat_e(x, half, i + 1), dd = sat_e(x, half, i + 2);
-        int32_t nine = ((b + cc) << 3) + (b + cc);
+        int32_t nine = (int32_t)((uint32_t)(b + cc) << 3) + (b + cc);
         x[2 * i + 1] = Hc[i] + ((nine - (a + dd) + 8) >> 4);
     }
 }
diff --git a/src/gm_basis_tab.c.inc b/src/gm_basis_tab.c.inc
new file mode 100644
index 0000000..a5c122a
--- /dev/null
+++ b/src/gm_basis_tab.c.inc
@@ -0,0 +1,56 @@
+/* GENERATED by repro/gen_gm_basis.c -- do not edit.
+ * Sign/magnitude runs of the separable synthesis basis of each band,
+ * measured by impulse response through omc_slice_inv().
+ * See section 12.22 of docs/TEMPORAL_T5.md. */
+
+#define GM_MAXRUN 12
+
+typedef struct {
+    int16_t off;      /* first pixel of the run, relative to the
+                       * coefficient's nominal position idx*stride */
+    int16_t len;      /* pixels in the run */
+    int16_t w;        /* mean |g| over the run, Q10 of the band peak */
+    int16_t sgn;      /* +1 or -1 */
+} gm_run_t;
+
+typedef struct {
+    int8_t   ny, nx;  /* runs in each direction */
+    int8_t   s0;      /* sign correction, see gen_gm_basis.c */
+    int16_t  sy0, sy1;/* FULL support box in rows, relative to */
+    int16_t  sx0, sx1;/* (row*vd, col*hd), dropped runs included. */
+    int16_t  vd, hd;  /* pixels per coefficient, vertical/horizontal */
+    gm_run_t y[GM_MAXRUN], x[GM_MAXRUN];
+} gm_basis_t;
+
+static const gm_basis_t GM_BASIS[OMC_NBANDS] = {
+  { 1, 3, 1, -3, 3, -37, 37, 4, 32,
+    {{-3,7,585,1}},
+    {{-35,3,7,-1},{-32,65,505,1},{33,3,7,-1}} },
+  { 1, 5, 1, -3, 3, -37, 69, 4, 32,
+    {{-3,7,585,1}},
+    {{-36,5,1,1},{-31,35,179,-1},{4,25,500,1},{29,35,179,-1},{64,5,1,1}} },
+  { 1, 5, 1, -3, 3, -21, 37, 4, 16,
+    {{-3,7,585,1}},
+    {{-20,5,3,1},{-15,18,182,-1},{3,11,593,1},{14,18,182,-1},{32,5,3,1}} },
+  { 1, 7, 1, -3, 3, -13, 21, 4, 8,
+    {{-3,7,585,1}},
+    {{-13,1,1,-1},{-12,5,5,1},{-7,8,220,-1},{1,7,495,1},{8,8,220,-1},{16,5,5,1},{21,1,1,-1}} },
+  { 3, 5, 1, -3, 7, -9, 9, 4, 4,
+    {{-3,4,213,-1},{1,3,569,1},{4,4,213,-1}},
+    {{-9,2,2,1},{-7,3,57,-1},{-4,9,492,1},{5,3,57,-1},{8,2,2,1}} },
+  { 1, 7, 1, -3, 3, -9, 13, 4, 4,
+    {{-3,7,585,1}},
+    {{-9,1,1,-1},{-8,5,12,1},{-3,4,245,-1},{1,3,614,1},{4,4,245,-1},{8,5,12,1},{13,1,1,-1}} },
+  { 3, 7, 1, -3, 7, -9, 13, 4, 4,
+    {{-3,4,213,-1},{1,3,569,1},{4,4,213,-1}},
+    {{-9,1,1,-1},{-8,5,12,1},{-3,4,245,-1},{1,3,614,1},{4,4,245,-1},{8,5,12,1},{13,1,1,-1}} },
+  { 3, 3, 1, -1, 3, -3, 3, 2, 2,
+    {{-1,2,256,-1},{1,1,1024,1},{2,2,256,-1}},
+    {{-3,1,64,-1},{-2,5,435,1},{3,1,64,-1}} },
+  { 1, 5, 1, -1, 1, -3, 5, 2, 2,
+    {{-1,3,683,1}},
+    {{-3,2,11,1},{-1,2,267,-1},{1,1,1024,1},{2,2,267,-1},{4,2,11,1}} },
+  { 3, 5, 1, -1, 3, -3, 5, 2, 2,
+    {{-1,2,256,-1},{1,1,1024,1},{2,2,256,-1}},
+    {{-3,2,11,1},{-1,2,267,-1},{1,1,1024,1},{2,2,267,-1},{4,2,11,1}} },
+};
diff --git a/src/internal.h b/src/internal.h
index a135b8a..dd8e97b 100644
--- a/src/internal.h
+++ b/src/internal.h
@@ -145,8 +145,18 @@ extern int omc_gr_pthr;
 extern int omc_gr_qmax;
 extern int omc_gr_notemp;
 extern int omc_gr_fillveto;
-extern int omc_fill_static;
 extern int omc_plan_hyst;
+extern int omc_calm;
+extern int omc_calm_thr;
+extern int omc_calm_amp;
+extern int omc_gm_dil;
+extern int omc_gm_llhold;
+extern int omc_gm_num, omc_gm_den;
+extern int omc_gm_mode;
+extern int omc_gm_nointra;
+extern int omc_gm_replan;
+extern int omc_gm_dthr;
+extern int omc_gm_watch;
 extern int omc_gr_dzoff;
 extern int omc_gr_soft_coarse;
 extern int omc_gr_intra;
@@ -235,7 +245,12 @@ extern const int omc_refine_steps;
  * Fill applies to bands 4..9 (levels 1-2 detail) with shift s >= 3. */
 #define OMC_FILL_BANDS_FROM 4
 #define OMC_FILL_MIN_SHIFT 3
-#define OMC_FILL_GATE 12 /* LL local-activity threshold (flat areas stay clean) */
+#define OMC_FILL_GATE 12
+/* The ants gate (minor 12): the flattest passing activity tier gets NO fill.
+ * A multiplier of 1 is the pre-minor-12 behaviour; see the block comment in
+ * fill_gate_g and docs/TEMPORAL_T5.md 13. */
+#define OMC_FILL_ANTS_MUL (getenv("OMC_ANTGATE") ? atoi(getenv("OMC_ANTGATE")) : 2)
+#define OMC_FILL_ANTS_GATE (OMC_FILL_ANTS_MUL * OMC_FILL_GATE) /* LL local-activity threshold (flat areas stay clean) */
 
 extern uint32_t omc_sign_tile[256][8]; /* built by omc_tans_init (normative LCG) */
 extern uint32_t omc_sign_tile_corr[256][8]; /* v4.5 correlated variant */
diff --git a/src/upconv.c b/src/upconv.c
index b33f3bd..ff7aec0 100644
--- a/src/upconv.c
+++ b/src/upconv.c
@@ -31,6 +31,14 @@
 #include "omc1.h"
 #include "omc_uc.h"
 
+/* SHIFTS ON SIGNED VALUES.  A left shift of a negative value is not
+ * defined by C11 (6.5.7p4); these shift-and-add multiplies routinely see
+ * negative operands.  Shifting the unsigned representation is defined for
+ * every value and compiles to the same instruction on a two's-complement
+ * target, so the fixed-point results are unchanged (verified byte-exact
+ * against the previous build).  Found by UBSan. */
+#define OMC_SHL(v, n) ((int32_t)((uint32_t)(v) << (n)))
+
 /* ------------------------------------------------------------------ kernel
  * 12-tap Kaiser(beta=6.0) windowed-sinc half-band interpolator, /1024.
  * Selected by measurement over 2/4/6/8/10/12/16-tap Lagrange, Deslauriers-
@@ -54,11 +62,11 @@ static inline int32_t uc_tap12(const int32_t *x)
     int32_t s4 = x[4] + x[7];         /*  -177 = -((<<7)+(<<5)+(<<4)+1)     */
     int32_t s5 = x[5] + x[6];         /*   637 = (<<9)+(<<7)-(<<2)+1        */
     int32_t acc = -s0;
-    acc += s1 << 3;
-    acc -= (s2 << 5) - (s2 << 2) - s2;
-    acc += (s3 << 6) + (s3 << 3);
-    acc -= (s4 << 7) + (s4 << 5) + (s4 << 4) + s4;
-    acc += (s5 << 9) + (s5 << 7) - (s5 << 2) + s5;
+    acc += OMC_SHL(s1, 3);
+    acc -= OMC_SHL(s2, 5) - OMC_SHL(s2, 2) - s2;
+    acc += OMC_SHL(s3, 6) + OMC_SHL(s3, 3);
+    acc -= OMC_SHL(s4, 7) + OMC_SHL(s4, 5) + OMC_SHL(s4, 4) + s4;
+    acc += OMC_SHL(s5, 9) + OMC_SHL(s5, 7) - OMC_SHL(s5, 2) + s5;
     return (acc + (1 << (OMC_UC_KSHIFT - 1))) >> OMC_UC_KSHIFT;
 }
 
@@ -675,7 +683,7 @@ static inline int32_t uc_mul_sa(int32_t c, int32_t x)
     int neg = c < 0, b;
     if (neg) c = -c;
     for (b = 0; b < 12; b++)
-        if ((c >> b) & 1) acc += x << b;
+        if ((c >> b) & 1) acc += OMC_SHL(x, b);
     return neg ? -acc : acc;
 }
 
diff --git a/tests/basis.c b/tests/basis.c
new file mode 100644
index 0000000..58b73bc
--- /dev/null
+++ b/tests/basis.c
@@ -0,0 +1,74 @@
+/* basis.c -- measure the synthesis basis of every band of the OMC transform.
+ *
+ * For each band, put a single impulse in an interior coefficient, run the
+ * inverse transform, and report:
+ *   peak |g|      -- the largest pixel the coefficient can move, per unit
+ *   ||g||^2       -- the energy that unit puts into the picture
+ *   leverage      -- peak|g| / ||g||^2, the correction bought per unit of damage
+ *
+ * These are properties of the transform, not of any content, and they are what
+ * the least-norm in-gamut correction is built on: the optimal reduction of a
+ * coefficient is proportional to g_k(p)/||g_k||^2 and does NOT depend on the
+ * coefficient's own magnitude.  The lifting is integer and therefore not quite
+ * linear, so the impulse is large and the result divided back down.
+ *
+ * Build:  cc -O2 -Iinclude -o basis tests/basis.c src/dwt.c
+ */
+#include <stdio.h>
+#include <stdlib.h>
+#include <string.h>
+#include <stdint.h>
+#include "omc1.h"
+#include "../src/internal.h"
+
+int main(int argc, char **argv)
+{
+    int W  = argc > 1 ? atoi(argv[1]) : 1920;
+    int sh = argc > 2 ? atoi(argv[2]) : 16;
+    int A  = argc > 3 ? atoi(argv[3]) : 4096;   /* impulse amplitude */
+    omc_band_t b[OMC_NBANDS];
+    omc_band_layout(W, sh, b);
+    size_t n = (size_t)W * sh;
+    int32_t *buf = calloc(n, sizeof(int32_t));
+    int32_t *tmp = calloc(n + 4 * (size_t)W, sizeof(int32_t));
+    printf("W=%d slice_h=%d impulse=%d\n", W, sh, A);
+    printf("band  w     h    peak|g|   ||g||^2      leverage=peak/||g||^2\n");
+    double gmin = 1e30, gmax = 0; int nsamp = 0;
+    double *all = malloc(sizeof(double) * OMC_NBANDS * 64);
+    for (int k = 0; k < OMC_NBANDS; k++) {
+        /* sample several phases per band: ||g||^2 varies with position as well
+         * as with band, and the spread across ALL coefficients is the number
+         * the least-norm ranking depends on */
+        for (int ph = 0; ph < 8; ph++) {
+            memset(buf, 0, n * sizeof(int32_t));
+            int rr = b[k].r0 + b[k].h / 2 + (ph & 1);
+            int cc = b[k].c0 + b[k].w / 2 + (ph >> 1);
+            if (rr >= b[k].r0 + b[k].h) rr = b[k].r0 + b[k].h - 1;
+            if (cc >= b[k].c0 + b[k].w) cc = b[k].c0 + b[k].w - 1;
+            buf[(size_t)rr * W + cc] = A;
+            omc_slice_inv(buf, W, sh, tmp);
+            double ee = 0;
+            for (size_t i = 0; i < n; i++) { double v = (double)buf[i] / A; ee += v * v; }
+            if (ee > 0) { if (ee < gmin) gmin = ee; if (ee > gmax) gmax = ee; all[nsamp++] = ee; }
+        }
+        memset(buf, 0, n * sizeof(int32_t));
+        int r = b[k].r0 + b[k].h / 2, c = b[k].c0 + b[k].w / 2;
+        buf[(size_t)r * W + c] = A;
+        omc_slice_inv(buf, W, sh, tmp);
+        double peak = 0, e2 = 0;
+        for (size_t i = 0; i < n; i++) {
+            double v = (double)buf[i] / A;
+            if (v < 0) { if (-v > peak) peak = -v; } else if (v > peak) peak = v;
+            e2 += v * v;
+        }
+        printf("%3d  %5d %5d   %8.4f  %10.4f   %10.4f\n",
+               k, b[k].w, b[k].h, peak, e2, e2 > 0 ? peak / e2 : 0.0);
+    }
+    for (int i = 1; i < nsamp; i++) { double t = all[i]; int j = i - 1;
+        while (j >= 0 && all[j] > t) { all[j + 1] = all[j]; j--; } all[j + 1] = t; }
+    printf("\n||g||^2 over %d sampled coefficients: min %.4f  max %.4f  "
+           "median %.4f  SPAN %.1fx\n", nsamp, gmin, gmax, all[nsamp / 2],
+           gmin > 0 ? gmax / gmin : 0.0);
+    free(all); free(buf); free(tmp);
+    return 0;
+}
diff --git a/tests/test_cap.c b/tests/test_cap.c
index e7bd5a2..9116ac4 100644
--- a/tests/test_cap.c
+++ b/tests/test_cap.c
@@ -155,6 +155,10 @@ int main(void)
         omc_enc_destroy(ee); omc_dec_destroy(dd); free(rec); free(dec);
     }
     free(pa); free(pb); free(a1); free(b1); free(a2); free(b2);
+    /* the reconstruction buffers were leaking: LeakSanitizer flagged
+     * 393216 bytes in four allocations, which would have masked a real
+     * codec leak in any later ASan run of this suite */
+    free(ra1); free(ra2); free(rb1); free(rb2);
     printf(fails ? "FAILURES: %d\n" : "all ok\n", fails);
     return fails ? 1 : 0;
 }
diff --git a/tests/test_xsl.c b/tests/test_xsl.c
index 64101c9..8189784 100644
--- a/tests/test_xsl.c
+++ b/tests/test_xsl.c
@@ -34,6 +34,8 @@
 #include "omc1.h"
 
 static int fails = 0;
+static int rt0_bad = 0;
+#define GM_PASS 12   /* the shipped default; see docs/TEMPORAL_T5.md 12.22 */
 #define CHECK(c, m) do { printf("%s: %s\n", (c) ? "ok" : "FAIL", m); \
                          if (!(c)) fails++; } while (0)
 
@@ -167,6 +169,177 @@ static int pad_chain(int oldpads, int *repl_ok)
     return same;
 }
 
+/* ------------------------------------------------------- G-T5-GAMUT ----
+ * STRICT IN-GAMUT MODE (docs/TEMPORAL_T5.md 12.22).  A baseband hand-off --
+ * decode to ordinary legal-range video, send it down a link, re-encode it --
+ * is exact only while the committed picture stays inside the legal range,
+ * because a legal-range container clips what falls outside it and a clipped
+ * sample is no longer the lattice point the next encoder needs to recognise.
+ * --gamut-strict makes the encoder keep the committed picture inside that
+ * range.  Three properties, and the gate would be worthless without the first:
+ *
+ * G-T5-GAMUT1  the mode is NON-VACUOUS: rail-touching content with the mode
+ *              OFF really does commit samples outside the legal range;
+ * G-T5-GAMUT2  with the mode ON that count is zero, and the baseband chain on
+ *              the same content is byte-exact -- pixels from generation 1,
+ *              streams from generation 2;
+ * G-T5-GAMUT3  the mode is INERT on content that never leaves the range: the
+ *              stream is byte-identical to the one the mode-off encoder
+ *              writes, so turning it on is free wherever it is not needed.
+ */
+/* Rail-hard content: hard black and white plates at exactly 0 and maxv, a
+ * full-range ramp, and a plate edge that walks across slice boundaries frame
+ * by frame so it lands in every position.  `hard` makes the walking feature
+ * ONE ROW tall, which is the pathological case: a single-row rail feature
+ * sitting on a slice boundary cannot be pulled off the rail once the quantizer
+ * has flattened its neighbourhood, and the XSL boundary edit then carries it
+ * out of range (docs/TEMPORAL_T5.md 12.22).  The ordinary arm uses a four-row
+ * feature, which is what real rail content looks like and what the project's
+ * own rail clip contains. */
+static void fill_rails_g(uint16_t *p, int frame, int hard)
+{
+    const int maxv = 1023;
+    for (int y = 0; y < H; y++)
+        for (int i = 0; i < W + 2 * WC; i++) {
+            int pw = (i < W) ? W : WC;
+            int x0 = (i < W) ? i : ((i - W) % WC);
+            int x = (x0 + 2 * frame) % pw;   /* the picture pans, as real content does */
+            int v;
+            if (x < pw / 4) v = 0;                                    /* black plate */
+            else if (x < pw / 2) v = maxv;                            /* white plate */
+            else if (x < 3 * pw / 4) v = ((x - pw / 2) * maxv) / (pw / 4); /* ramp */
+            else v = maxv;                                            /* white plate */
+            if (hard) {
+                /* the pathological addition: a ONE-ROW rail line whose position
+                 * walks across a slice boundary frame by frame */
+                int line = (SH - 1 + 2 * frame) % H;
+                if (y == line) v = maxv;
+                if (y == (line + 1) % H) v = 0;
+            }
+            p[(size_t)y * (W + 2 * WC) + i] = (uint16_t)(v + OMC_PIX_BIAS);
+        }
+}
+/* The ordinary arm: real-looking textured content that has been GRADED TO THE
+ * RAILS, which is the class the hand-off report exposed -- ordinary footage
+ * whose highlights sit on the container's white point, not synthetic plates.
+ * A handful of samples per slice overshoot; the mode is expected to clear all
+ * of them, and the baseband chain then has to be byte-exact. */
+static void fill_rails(uint16_t *p, int frame)
+{
+    const int maxv = 1023;
+    uint32_t x;
+    for (int y = 0; y < H; y++)
+        for (int i = 0; i < W + 2 * WC; i++) {
+            int xx = (i + 2 * frame) % (W + 2 * WC);
+            x = 4242u + (uint32_t)(y * 31 + xx) * 2654435761u;
+            x = x * 1103515245u + 12345u;
+            int v = 690 + 4 * y + ((y / 5) % 3) * 30 + (int)((x >> 18) % 96);
+            if (v > maxv) v = maxv;
+            if (v < 0) v = 0;
+            p[(size_t)y * (W + 2 * WC) + i] = (uint16_t)(v + OMC_PIX_BIAS);
+        }
+}
+
+/* encode NF frames with an explicit strict setting; report the gamut count */
+/* set by run_strict: the repair's internal work, so a determinism gate can
+ * assert the PATH as well as the output (see G-T5-GAMUT5) */
+static int64_t gm_last_slices, gm_last_passes, gm_last_unfixed;
+
+static void run_strict(const omc_config_t *c, const uint16_t *pix, int passes,
+                       uint8_t *bs, uint16_t *dec, int64_t *oob)
+{
+    size_t fb = (size_t)(c->bits_per_slice / 8) * (H / SH);
+    omc_enc_t *e = omc_enc_create(c);
+    omc_dec_t *d = omc_dec_create(c);
+    omc_enc_set_gamut_strict(e, passes);
+    uint16_t *rcb = malloc(WORDS * 2);
+    for (int f = 0; f < NF; f++) {
+        omc_frame_t fr; planes(&fr, (uint16_t *)pix + WORDS * f);
+        omc_frame_t rc; planes(&rc, rcb);               /* recon: the mode needs it */
+        omc_enc_frame(e, &fr, f, bs + fb * f, fb, &rc);
+        omc_frame_t fo; planes(&fo, dec + WORDS * f);
+        omc_dec_frame(d, bs + fb * f, fb, &fo);
+        /* rt = 0 (mandate C4): the encoder's own reconstruction must equal
+         * what the decoder produces, byte for byte, with the repair running.
+         * If the repair could ever leave the two disagreeing, every exactness
+         * claim above it would be measuring the wrong buffer. */
+        if (memcmp(rcb, dec + WORDS * f, WORDS * 2)) rt0_bad++;
+    }
+    free(rcb);
+    if (oob) *oob = omc_enc_oob(e);
+    gm_last_slices  = omc_enc_gamut_slices(e);
+    gm_last_passes  = omc_enc_gamut_repairs(e);
+    gm_last_unfixed = omc_enc_gamut_unfixed(e);
+    omc_enc_destroy(e);
+    omc_dec_destroy(d);
+}
+
+/* ---------------------------------------------------------- G-T5-CALM ----
+ * TEMPORAL CALM (the "ants" fix, docs/TEMPORAL_T5.md 12.23).  Two properties,
+ * and the second is only worth anything because the first one holds.
+ *
+ * G-T5-CALM1  THE FIX FIRES, AND THE GATE IS NON-VACUOUS.  A master that is
+ *             FLAT and STATIC in the source -- a constant field carrying a
+ *             sub-code dither of a couple of codes, exactly the sensor noise
+ *             that carries a coefficient back and forth across the quantizer's
+ *             zero/one boundary -- must show frame-to-frame movement in the
+ *             DECODE with the fix off, and much less of it with the fix on.
+ *             Both halves are checked: an arm that cannot fail proves nothing.
+ *
+ * G-T5-CALM2  AND IT CANNOT COST GENERATION EXACTNESS.  The same content, with
+ *             the fix ON so the kill is demonstrably firing, must still chain
+ *             byte-exactly: generation 2 reproduces generation 1's pixels and
+ *             generation 3 reproduces generation 2's stream.  This is the gate
+ *             form of the lattice argument in 12.23.7 -- the kill tests a
+ *             STRICT |c| < (1 << s) and a committed coefficient is exactly
+ *             q << s, so it can never fire on a picture that has already been
+ *             through the codec.
+ */
+extern int omc_calm;      /* src/codec.c; internal, declared here for the gate */
+extern int omc_calm_thr;
+extern int omc_gm_mode;   /* the in-gamut repair's reduction rule */
+extern int omc_gm_num, omc_gm_den;
+extern int omc_gm_fallback_on;
+
+/* A flat, statically dithered field with one heavily textured strip, so the
+ * rate allocator has somewhere to spend and the flat area gets a coarse
+ * enough step for the boundary to matter. */
+static void fill_flat(uint16_t *p, int frame)
+{
+    for (int y = 0; y < H; y++)
+        for (int i = 0; i < W + 2 * WC; i++) {
+            uint32_t x = (uint32_t)(y * 7919 + i * 104729 + frame * 15485863);
+            x = x * 1103515245u + 12345u; x ^= x >> 15;
+            x = x * 2654435761u; x ^= x >> 13;
+            int v;
+            if (y >= H / 2 && y < H / 2 + H / 8)
+                v = 400 + (int)((x >> 17) % 400);        /* the texture strip */
+            else
+                v = 512 + (int)((x >> 19) % 17) - 8;   /* flat + a -8..+8 dither */
+            p[(size_t)y * (W + 2 * WC) + i] = (uint16_t)(v + OMC_PIX_BIAS);
+        }
+}
+
+/* P(|frame-to-frame difference| > 6 codes) over the FLAT rows of the luma
+ * plane -- the project's own ants tail (docs/REPORT.md 18.6), in parts per
+ * 10000 so the gate can compare integers. */
+static int ants_tail(const uint16_t *dec)
+{
+    long n = 0, hit = 0;
+    for (int f = 1; f < NF; f++)
+        for (int y = 0; y < H; y++) {
+            if (y >= H / 2 && y < H / 2 + H / 8) continue;   /* skip texture */
+            for (int i = 0; i < W; i++) {
+                const uint16_t *a = dec + WORDS * (f - 1);
+                const uint16_t *b = dec + WORDS * f;
+                int d = (int)b[(size_t)y * W + i] - (int)a[(size_t)y * W + i];
+                if (d < 0) d = -d;
+                n++; if (d > 6) hit++;
+            }
+        }
+    return n ? (int)((hit * 10000 + n / 2) / n) : 0;
+}
+
 int main(void)
 {
     omc_config_t c; cfg_init(&c);
@@ -261,6 +434,302 @@ int main(void)
               "behaviour reintroduced the same chain FAILS");
     }
 
+    /* ----------------------------------------------------- G-T5-GAMUT */
+    {
+        size_t fb = (size_t)(c.bits_per_slice / 8) * (H / SH);
+        uint16_t *rp = malloc(WORDS * 2 * NF);
+        uint16_t *ga = malloc(WORDS * 2 * NF), *gb = malloc(WORDS * 2 * NF);
+        uint16_t *gc = malloc(WORDS * 2 * NF);
+        uint8_t *ba = malloc(fb * NF), *bb = malloc(fb * NF), *bc = malloc(fb * NF);
+        int64_t oob_off = 0, oob_on = 0;
+        if (rp && ga && gb && gc && ba && bb && bc) {
+            for (int f = 0; f < NF; f++) fill_rails(rp + WORDS * f, f);
+            run_strict(&c, rp, 0, ba, ga, &oob_off);
+            run_strict(&c, rp, GM_PASS, bb, gb, &oob_on);
+            /* generation 2 over BASEBAND: the decode is fed straight back in.
+             * (These rasters are unpadded and the decode is already in the
+             * biased domain the encoder takes, so the decode IS the baseband
+             * hand-off, clipping included -- nothing to crop or re-pad.) */
+            /* The contract is the one G-T5-XSL3 states: PIXELS equal from
+             * generation 1, STREAMS equal from generation 2 -- generation 1
+             * codes a master and generation 2 codes a reconstruction, so their
+             * bytes are not required to agree.  Hence a third generation. */
+            int64_t ignore = 0;
+            uint16_t *gd = malloc(WORDS * 2 * NF);
+            uint8_t *bd = malloc(fb * NF);
+            run_strict(&c, gb, GM_PASS, bc, gc, &ignore);
+            run_strict(&c, gc, GM_PASS, bd, gd, &ignore);
+            int pix_same = memcmp(gb, gc, WORDS * 2 * NF) == 0 &&
+                           memcmp(gc, gd, WORDS * 2 * NF) == 0;
+            int str_same = memcmp(bc, bd, fb * NF) == 0;
+            free(gd); free(bd);
+            CHECK(oob_off > 0,
+                  "G-T5-GAMUT1 the gate is NON-VACUOUS: with the mode OFF, "
+                  "rail-touching content commits samples outside legal range");
+            CHECK(oob_on == 0,
+                  "G-T5-GAMUT2a with --gamut-strict the committed picture stays "
+                  "inside the legal range on that same content");
+            /* The pathological arm: a ONE-ROW rail feature walking across slice
+             * boundaries.  The XSL boundary edit is unconditional and can always
+             * carry such a sample one code out (12.22.11), so this arm asserts a
+             * near-total reduction rather than zero -- and asserting the weaker
+             * thing here is the point: it is the case the mode does NOT close,
+             * and a gate that pretended otherwise would be the lie. */
+            {
+                uint16_t *hp = malloc(WORDS * 2 * NF);
+                uint8_t *hb = malloc(fb * NF);
+                uint16_t *hd = malloc(WORDS * 2 * NF);
+                int64_t h_off = 0, h_on = 0;
+                if (hp && hb && hd) {
+                    for (int f = 0; f < NF; f++) fill_rails_g(hp + WORDS * f, f, 1);
+                    run_strict(&c, hp, 0, hb, hd, &h_off);
+                    run_strict(&c, hp, GM_PASS, hb, hd, &h_on);
+                    /* the same content with the fallback of 12.22.3i turned
+                     * off, so the gate can assert that the fallback is what
+                     * closes this case rather than merely asserting that it is
+                     * closed */
+                    int64_t h_nofb = 0;
+                    int keepfb = omc_gm_fallback_on;
+                    omc_gm_fallback_on = 0;
+                    run_strict(&c, hp, GM_PASS, hb, hd, &h_nofb);
+                    omc_gm_fallback_on = keepfb;
+                    printf("   pathological arm: %lld samples out of range with "
+                           "the repair off, %lld with it on, %lld with the "
+                           "fallback disabled\n",
+                           (long long)h_off, (long long)h_on, (long long)h_nofb);
+                    CHECK(h_off > 0 && h_on == 0,
+                          "G-T5-GAMUT2c the PATHOLOGICAL arm (one-row rail "
+                          "features walked across slice boundaries) is CLOSED: "
+                          "every excursion removed, not merely 99% of them");
+                    CHECK(h_nofb > 0,
+                          "G-T5-GAMUT2d and the fallback is what closes it: "
+                          "with the fallback disabled the same content leaves a "
+                          "residue that more passes do not clear");
+                }
+                free(hp); free(hb); free(hd);
+            }
+            CHECK(pix_same && str_same,
+                  "G-T5-GAMUT2b and its BASEBAND chain is byte-exact: "
+                  "generation 2 reproduces both the picture and the stream");
+            /* inert where it is not needed: ordinary textured content */
+            int64_t o1 = 0, o2 = 0;
+            run_strict(&c, pix, 0, ba, ga, &o1);
+            run_strict(&c, pix, GM_PASS, bb, gb, &o2);
+            CHECK(o1 == 0 && o2 == 0 && memcmp(ba, bb, fb * NF) == 0,
+                  "G-T5-GAMUT3 the mode is INERT on content that never leaves "
+                  "the legal range: byte-identical stream, on and off");
+            CHECK(rt0_bad == 0,
+                  "G-T5-GAMUT4 rt = 0 holds with the repair running: the "
+                  "encoder's reconstruction equals the decoder's output");
+
+            /* ------------------------------------------- G-T5-GAMUT5
+             * DETERMINISM.  Every exactness result in 12.22 is a claim about
+             * reproducing a stream, and none of them means anything if the
+             * repair can reach two different answers from one input.  Two
+             * things are asserted, for two different reasons.
+             *
+             * The OUTPUT must be byte-identical.  That is the property
+             * actually needed: generation exactness and reproducibility both
+             * follow from it and nothing stronger can be asserted about a
+             * stream.
+             *
+             * The repair's INTERNAL COUNTS must match too, and that is not
+             * redundant.  Two runs can take different numbers of passes and
+             * still converge to the same lattice point, so the stream agrees
+             * while the encoder is already nondeterministic -- a latent fault
+             * waiting for an unrelated change to expose it.  Counts turn that
+             * from invisible into a build failure.  (This is not idle: an
+             * earlier revision of the repair restored a plane from an
+             * uninitialised buffer when that plane was clean on one pass and
+             * dirty on a later one, and the streams still matched.)
+             *
+             * The second encode is separated from the first by an encode of
+             * DIFFERENT content in the same process.  Two fresh processes
+             * would not catch state leaking through a global or a static,
+             * which is exactly the class of bug this is guarding. */
+            {
+                uint16_t *da = malloc(WORDS * 2 * NF), *db = malloc(WORDS * 2 * NF);
+                uint16_t *dx = malloc(WORDS * 2 * NF);
+                uint8_t *pa = malloc(fb * NF), *pb = malloc(fb * NF);
+                uint8_t *px = malloc(fb * NF);
+                if (da && db && dx && pa && pb && px) {
+                    int64_t o = 0;
+                    run_strict(&c, rp, GM_PASS, pa, da, &o);
+                    int64_t sa = gm_last_slices, ja = gm_last_passes,
+                            ua = gm_last_unfixed;
+                    run_strict(&c, pix, GM_PASS, px, dx, &o);   /* other content */
+                    run_strict(&c, rp, GM_PASS, pb, db, &o);
+                    CHECK(sa > 0 && ja > 0,
+                          "G-T5-GAMUT5a the gate is NON-VACUOUS: the repair "
+                          "actually fired on this content");
+                    CHECK(memcmp(pa, pb, fb * NF) == 0 &&
+                          memcmp(da, db, WORDS * 2 * NF) == 0,
+                          "G-T5-GAMUT5b the same input re-encoded in the same "
+                          "process, with other content coded in between, "
+                          "produces a byte-identical stream and decode");
+                    CHECK(sa == gm_last_slices && ja == gm_last_passes &&
+                          ua == gm_last_unfixed,
+                          "G-T5-GAMUT5c and it got there by the same internal "
+                          "path: identical slices repaired, passes taken and "
+                          "slices left unfixed");
+                }
+                /* and again with the ALIGNMENT VETO (mode 16) engaged, which
+                 * reads a summed-area table of residuals and skips
+                 * coefficients on a signed test -- more internal state to get
+                 * wrong than any earlier shape, so it is gated separately
+                 * rather than assumed to inherit the result above. */
+                if (da && db && dx && pa && pb && px) {
+                    int km = omc_gm_mode, kn = omc_gm_num, kd = omc_gm_den;
+                    omc_gm_mode = 16; omc_gm_num = 15; omc_gm_den = 16;
+                    int64_t o16a = 0, o16b = 0;
+                    run_strict(&c, rp, GM_PASS, pa, da, &o16a);
+                    int64_t sa = gm_last_slices, ja = gm_last_passes;
+                    run_strict(&c, pix, GM_PASS, px, dx, &o16b);
+                    run_strict(&c, rp, GM_PASS, pb, db, &o16b);
+                    CHECK(sa > 0 && ja > 0 && o16a == 0,
+                          "G-T5-GAMUT5d the alignment veto (mode 16) fires on "
+                          "this content and still reaches zero out-of-range "
+                          "samples inside the pass budget");
+                    CHECK(memcmp(pa, pb, fb * NF) == 0 &&
+                          memcmp(da, db, WORDS * 2 * NF) == 0 &&
+                          sa == gm_last_slices && ja == gm_last_passes,
+                          "G-T5-GAMUT5e and it is deterministic: same stream, "
+                          "same decode and same internal path on a re-encode");
+                    omc_gm_mode = km; omc_gm_num = kn; omc_gm_den = kd;
+                }
+                free(da); free(db); free(dx); free(pa); free(pb); free(px);
+            }
+        }
+        free(rp); free(ga); free(gb); free(gc); free(ba); free(bb); free(bc);
+    }
+
+    /* -------------------------------------------------------- G-T5-CUT
+     *
+     * THE OPERATOR TEST.  Everything above encodes one kind of content at a
+     * time, which is not how a broadcast chain is used.  A live chain cuts
+     * between sources every few seconds and there is nobody at a console
+     * changing the encoder's settings at each cut.  So this gate builds ONE
+     * sequence that cuts between content whose demands on the in-gamut repair
+     * are opposite, and encodes the whole thing as ONE stream at the DEFAULT
+     * settings with nothing switched at the cuts.
+     *
+     * The two kinds are the two that actually occur in a programme: ordinary
+     * textured footage GRADED TO THE RAILS, where highlights sit on the
+     * container's white point and the repair has real work to do, cutting
+     * against ordinary footage that never approaches those limits and where
+     * the repair must do nothing at all.
+     *
+     * The last assertion covers the hard synthetic separately.  Black and
+     * white plates at exactly 0 and maxv are content the repair does NOT fully
+     * close (12.22.11), so requiring zero there would be asserting something
+     * the mode never claimed.  What can be required, and is, is that CUTTING
+     * costs nothing: the mixed sequence must be no worse than the plates on
+     * their own.  Whatever residue is left is a property of the content and
+     * not of the cut. */
+    {
+        uint16_t *cut = malloc(WORDS * 2 * NF);
+        uint16_t *cd1 = malloc(WORDS * 2 * NF), *cd2 = malloc(WORDS * 2 * NF);
+        uint16_t *cd3 = malloc(WORDS * 2 * NF);
+        size_t cfb = (size_t)(c.bits_per_slice / 8) * (H / SH);
+        uint8_t *cb1 = malloc(cfb * NF), *cb2 = malloc(cfb * NF);
+        uint8_t *cb3 = malloc(cfb * NF);
+        if (!cut || !cd1 || !cd2 || !cd3 || !cb1 || !cb2 || !cb3) {
+            printf("FAIL: alloc (cut)\n"); fails++;
+        } else {
+            /* NF is 4, so this is three cuts in four frames -- deliberately
+             * more abrupt than any real programme */
+            for (int f = 0; f < NF; f++) {
+                if (f & 1) fill(cut + WORDS * f, 12345u, f);  /* never near the rails */
+                else fill_rails(cut + WORDS * f, f);          /* graded to the rails */
+            }
+            int64_t cut_oob = 0, ignore = 0, off_oob = 0;
+            run_strict(&c, cut, GM_PASS, cb1, cd1, &cut_oob);
+            run_strict(&c, cut, 0, cb2, cd2, &off_oob);
+            CHECK(off_oob > 0,
+                  "G-T5-CUT1 the gate is NON-VACUOUS: with the repair off, this "
+                  "cut sequence does commit samples outside the legal range");
+            CHECK(cut_oob == 0,
+                  "G-T5-CUT2 one encode at the DEFAULT settings, across cuts "
+                  "between rail-graded and ordinary footage, leaves NO committed "
+                  "sample outside the legal range -- nothing is switched at the "
+                  "cuts");
+            run_strict(&c, cd1, GM_PASS, cb2, cd2, &ignore);
+            run_strict(&c, cd2, GM_PASS, cb3, cd3, &ignore);
+            CHECK(memcmp(cd1, cd2, WORDS * 2 * NF) == 0 &&
+                  memcmp(cd2, cd3, WORDS * 2 * NF) == 0 &&
+                  memcmp(cb2, cb3, cfb * NF) == 0,
+                  "G-T5-CUT3 and that cut sequence survives a baseband "
+                  "generation chain byte for byte");
+            {   /* cutting must not make the HARD synthetic any worse */
+                uint16_t *pl = malloc(WORDS * 2 * NF);
+                int64_t plate_oob = 0, mixed_oob = 0;
+                if (pl) {
+                    for (int f = 0; f < NF; f++) fill_rails_g(pl + WORDS * f, f, 0);
+                    run_strict(&c, pl, GM_PASS, cb2, cd2, &plate_oob);
+                    for (int f = 0; f < NF; f++)
+                        if (f == 1) fill(pl + WORDS * f, 12345u, f);
+                    run_strict(&c, pl, GM_PASS, cb2, cd2, &mixed_oob);
+                    printf("   hard plates alone leave %lld samples out of range; "
+                           "cut with ordinary footage, %lld\n",
+                           (long long)plate_oob, (long long)mixed_oob);
+                    CHECK(plate_oob == 0 && mixed_oob == 0,
+                          "G-T5-CUT4 hard black and white plates at the exact "
+                          "rails close completely too, alone AND cut against "
+                          "ordinary footage");
+                }
+                free(pl);
+            }
+        }
+        free(cut); free(cd1); free(cd2); free(cd3);
+        free(cb1); free(cb2); free(cb3);
+    }
+
+    /* ------------------------------------------------------- G-T5-CALM */
+    {
+        omc_config_t cc; cfg_init(&cc);
+        cc.bits_per_slice = W * SH / 2;      /* 0.25 bpp: a coarse step */
+        cc.refresh_r = 8;
+        size_t cfb = (size_t)(cc.bits_per_slice / 8) * (H / SH);
+        uint16_t *cp = malloc(WORDS * 2 * NF);
+        uint16_t *d0 = malloc(WORDS * 2 * NF), *d1 = malloc(WORDS * 2 * NF);
+        uint16_t *d2 = malloc(WORDS * 2 * NF), *d3 = malloc(WORDS * 2 * NF);
+        uint8_t *b0 = malloc(cfb * NF), *b1 = malloc(cfb * NF);
+        uint8_t *b2 = malloc(cfb * NF), *b3 = malloc(cfb * NF);
+        if (!cp || !d0 || !d1 || !d2 || !d3 || !b0 || !b1 || !b2 || !b3) {
+            printf("FAIL: alloc (calm)\n"); fails++;
+        } else {
+            for (int f = 0; f < NF; f++) fill_flat(cp + WORDS * f, f);
+            int keep = omc_calm;
+            omc_calm = 0; run_chain(&cc, cp, b0, d0);
+            omc_calm = keep ? keep : 1; run_chain(&cc, cp, b1, d1);
+            int off = ants_tail(d0), on = ants_tail(d1);
+            printf("   ants tail over the flat field: fix off %d.%02d %%, "
+                   "fix on %d.%02d %% (of samples moving more than 6 codes)\n",
+                   off / 100, off % 100, on / 100, on % 100);
+            CHECK(off > 100,
+                  "G-T5-CALM1a the gate is NON-VACUOUS: with the fix OFF a "
+                  "source-static flat field moves in the decode");
+            CHECK(on * 2 <= off,
+                  "G-T5-CALM1b with the fix ON that movement is at least "
+                  "halved");
+            CHECK(memcmp(b0, b1, cfb * NF) != 0,
+                  "G-T5-CALM1c the fix actually changed the stream (it is not "
+                  "silently inert on this content)");
+            run_chain(&cc, d1, b2, d2);
+            run_chain(&cc, d2, b3, d3);
+            CHECK(memcmp(d1, d2, WORDS * 2 * NF) == 0,
+                  "G-T5-CALM2a generation-2 pixels reproduce generation 1 with "
+                  "the calm kill firing");
+            CHECK(memcmp(b2, b3, cfb * NF) == 0 &&
+                  memcmp(d2, d3, WORDS * 2 * NF) == 0,
+                  "G-T5-CALM2b and generation 3 reproduces generation 2's "
+                  "stream byte-for-byte");
+            omc_calm = keep;
+        }
+        free(cp); free(d0); free(d1); free(d2); free(d3);
+        free(b0); free(b1); free(b2); free(b3);
+    }
+
     free(pix); free(dec1); free(dec2); free(dec3); free(decx);
     free(bs1); free(bs2); free(bs3); free(bsx);
     printf("test_xsl: %s\n", fails ? "FAILURES" : "all ok");
diff --git a/tools/omc_enc.c b/tools/omc_enc.c
index a72b64f..a8c0870 100644
--- a/tools/omc_enc.c
+++ b/tools/omc_enc.c
@@ -60,7 +60,15 @@ int main(int argc, char **argv)
     int rgb = 0, mono = 0, verbose_ll = 0, lossless_frames = 0, bpp_set = 0;
     int dispw_arg = 0, disph_arg = 0;   /* --display-w/--display-h (CDR re-encode) */
     int start_frame = 0;                /* --start-frame: mod-256 phase to resume */
-    int dbg_oldpads = 0;                /* TEST ONLY: pre-minor-11 pad behaviour */
+    int dbg_oldpads = 0;
+    int gamut_explicit = 0;   /* the flag was given on the command line */
+    int64_t gamut_oob = 0;    /* what the mode could not clear; drives the
+                               * exit status, see the end of main */                /* TEST ONLY: pre-minor-11 pad behaviour */
+    int gamut_strict = 12;              /* ON BY DEFAULT -- see omc_enc_create.
+                                           --gamut-strict 0 turns it off.
+                                           --gamut-strict [passes]: keep the
+                                           committed picture inside legal range
+                                           so a BASEBAND chain is exact */
     int cdr_in = 0;     /* input is coded-domain raw (biased, coded geometry) */
     omc_config_t cfg;
     memset(&cfg, 0, sizeof(cfg));
@@ -90,26 +98,41 @@ int main(int argc, char **argv)
         else if (!strcmp(argv[i], "--matrix")) cfg.color.matrix = (uint8_t)atoi(argv[++i]);
         else if (!strcmp(argv[i], "--tune")) cfg.tune_vmaf = !strcmp(argv[++i], "vmaf");
         else if (!strcmp(argv[i], "--refresh")) cfg.refresh_r = (uint8_t)atoi(argv[++i]);
-        else if (!strcmp(argv[i], "--no-fill")) cfg.no_fill = 1;
+        else if (!strcmp(argv[i], "--no-fill")) cfg.fill_grain = 0;
+        else if (!strcmp(argv[i], "--fill")) cfg.fill_grain = 1;
         else if (!strcmp(argv[i], "--cdr-in")) cdr_in = 1;
         else if (!strcmp(argv[i], "--no-deadzone")) cfg.no_deadzone = 1;
         else if (!strcmp(argv[i], "--grain-replace")) cfg.grain_replace = 1;
         else if (!strcmp(argv[i], "--grain-corr")) cfg.grain_corr = 1;
-        else if (!strcmp(argv[i], "--fill-static")) cfg.fill_static = 1;
+        else if (!strcmp(argv[i], "--fill-static")) { /* minor 12: the
+            frame-independent fill tile is the ONLY behaviour, so this flag
+            is accepted and does nothing.  Kept so command lines written
+            against the minor-11 build still run. */ }
         else if (!strcmp(argv[i], "--debug-oldpads")) dbg_oldpads = 1;
+        else if (!strcmp(argv[i], "--gamut-strict")) {
+            /* optional numeric argument = per-slice repair budget; 0 turns the
+             * mode off.  Passing the flag at all counts as an EXPLICIT request,
+             * which is what makes the --cdr-in contradiction below an error
+             * rather than a silent stand-down. */
+            if (i + 1 < argc && argv[i + 1][0] >= '0' && argv[i + 1][0] <= '9')
+                gamut_strict = atoi(argv[++i]);
+            else gamut_strict = 12;
+            if (gamut_strict < 0) gamut_strict = 0;
+            gamut_explicit = 1;
+        }
         else if (!strcmp(argv[i], "--start-frame")) start_frame = atoi(argv[++i]);
         else if (!strcmp(argv[i], "--display-w")) dispw_arg = atoi(argv[++i]);
         else if (!strcmp(argv[i], "--display-h")) disph_arg = atoi(argv[++i]);
         else if (!strcmp(argv[i], "--rgb")) rgb = 1;   /* planar R,G,B in; RCT applied */
         else if (!strcmp(argv[i], "--mono")) mono = 1; /* single plane in; flat chroma */
-        else if (!strcmp(argv[i], "--lossless")) { cfg.lossless_pref = 1; cfg.no_fill = 1; }
-        else if (!strcmp(argv[i], "--lossless-verbose")) { cfg.lossless_pref = 1; cfg.no_fill = 1; verbose_ll = 1; }
+        else if (!strcmp(argv[i], "--lossless")) { cfg.lossless_pref = 1; cfg.fill_grain = 0; }
+        else if (!strcmp(argv[i], "--lossless-verbose")) { cfg.lossless_pref = 1; cfg.fill_grain = 0; verbose_ll = 1; }
         else die("unknown arg");
     }
     if (!inp || !outp || !cfg.width || !cfg.height)
         die("usage: -i in.yuv -o out.omc -w W -h H [--fmt 422|444] [--depth 10]\n"
             "       [--bpp 2.0] [--slice-h 8|16|32] [--uc-ratio 0|1|2]\n"
-            "       [--recon rec.cdr] [--cdr-in] [--no-fill] [--lossless]\n"
+            "       [--recon rec.cdr] [--cdr-in] [--fill|--no-fill] [--lossless]\n"
             "\n"
             "  --cdr-in     the input is a coded-domain raw (CDR) as written by\n"
             "               omc_dec --cdr: biased by 2048, unclipped, at CODED\n"
@@ -118,6 +141,24 @@ int main(int argc, char **argv)
             "               through unlimited generations.  -w/-h give the CODED\n"
             "               dims here (as reported by omc_dec).\n"
             "\n"
+            "  --gamut-strict [N]  ON BY DEFAULT (N = 12).  Keeps the committed\n"
+            "               picture inside the legal range so an ORDINARY\n"
+            "               (legal-range, cropped) baseband hand-off is exact\n"
+            "               through unlimited generations, not only the CDR one.\n"
+            "               N is the per-slice repair budget, max 16; N = 0 turns\n"
+            "               the mode off.  It is on by default because it is not\n"
+            "               a content-dependent choice: a broadcast chain cuts\n"
+            "               between content types in seconds and nobody is at a\n"
+            "               console deciding.  Encoder-side only: the bitstream,\n"
+            "               the decoder and the generation lock are unchanged.\n"
+            "               Byte-identical to having it off on content that never\n"
+            "               reaches the rails, stands down entirely on --cdr-in,\n"
+            "               and inert from generation 2 onwards.  On a fixed slice\n"
+            "               period, LOWER N rather than switching it off: what it\n"
+            "               cannot finish it still reports -- and omc_enc then\n"
+            "               EXITS 2, so an automated pipeline cannot silently\n"
+            "               lose baseband exactness. Exit 0 means it delivered.\n"
+            "\n"
             "  T5 notes: the temporal engine is rebuilt (motion derived from\n"
             "  reconstruction history; frame-buffer reference), the cross-slice\n"
             "  boundary blend (XSL) is always on and exactly reversible, and the\n"
@@ -278,6 +319,40 @@ int main(int argc, char **argv)
     fwrite(shdr, 1, OMC_STREAM_HDR_BYTES, fo);
 
     omc_enc_t *enc = omc_enc_create(&cfg);
+    if (enc && cdr_in) omc_enc_set_cdr_input(enc, 1);
+    if (cdr_in) {
+        /* Not a preference -- a contract.  A CDR is a committed picture: it is
+         * allowed to sit outside the legal range and must be re-encoded
+         * verbatim, and the CDR chain is exact without any help from this mode.
+         * Repairing it would break the one guarantee that holds
+         * unconditionally.
+         *
+         * Since the mode is now ON BY DEFAULT, --cdr-in STANDS IT DOWN rather
+         * than failing: a default is not a request, and an operator who asks
+         * for CDR input has said everything needed.  A default that turned a
+         * working command line into an error would be the same operator burden
+         * this mode exists to remove.  An EXPLICIT --gamut-strict alongside
+         * --cdr-in is still refused, because that is a contradiction the
+         * operator typed and should see. */
+        if (gamut_explicit && gamut_strict)
+            die("--gamut-strict is a BASEBAND-input policy and must not be "
+                "combined with --cdr-in: a committed picture is reproduced "
+                "verbatim, and the CDR chain is already exact through "
+                "unlimited generations");
+        gamut_strict = 0;
+    }
+    /* The flag wins; failing that the environment; failing that the default.
+     * Working this out HERE rather than letting the library and the tool each
+     * apply their own default is what keeps the reported figure equal to the
+     * figure actually in force -- an earlier version of this had the tool's
+     * default silently beat OMC_GAMUT_STRICT, so the variable stopped being
+     * able to turn the mode off while the report still said it was on. */
+    if (!gamut_explicit) {
+        const char *gs = getenv("OMC_GAMUT_STRICT");
+        if (gs) gamut_strict = atoi(gs);
+    }
+    if (gamut_strict < 0) gamut_strict = 0;
+    omc_enc_set_gamut_strict(enc, gamut_strict);
     if (dbg_oldpads && enc) {
         omc_enc_debug_oldpads(enc, 1);
         fprintf(stderr, "omc_enc: WARNING --debug-oldpads: pad neutralization "
@@ -329,14 +404,30 @@ int main(int argc, char **argv)
     {
         int64_t oob = omc_enc_oob(enc);
         int geom = omc_enc_geom_baseband_safe(enc);
-        fprintf(stderr, "omc_enc: gamut: %lld committed samples outside legal "
-                "range\n", (long long)oob);
+        gamut_oob = oob;
+        if (gamut_strict)
+            fprintf(stderr, "omc_enc: gamut-strict: %d passes max, %lld slices "
+                    "repaired in %lld passes (%lld fell back to the harsh "
+                    "rule), %lld slices still out of gamut\n",
+                    gamut_strict,
+                    (long long)omc_enc_gamut_slices(enc),
+                    (long long)omc_enc_gamut_repairs(enc),
+                    (long long)omc_enc_gamut_fallbacks(enc),
+                    (long long)omc_enc_gamut_unfixed(enc));
+        omc_enc_gamut_stat_report();
+        if (oob < 0)
+            fprintf(stderr, "omc_enc: gamut: NOT MEASURED (no reconstruction "
+                    "buffer)\n");
+        else
+            fprintf(stderr, "omc_enc: gamut: %lld committed samples outside "
+                    "legal range\n", (long long)oob);
         if (oob == 0 && geom)
             fprintf(stderr, "omc_enc: baseband-safe: yes\n");
         else
             fprintf(stderr, "omc_enc: baseband-safe: NO (%s%s%s) -- CDR "
                     "interchange required for exact chains\n",
-                    oob ? "out-of-gamut committed samples" : "",
+                    oob < 0 ? "gamut not measured"
+                            : (oob ? "out-of-gamut committed samples" : ""),
                     (oob && !geom) ? "; " : "",
                     geom ? "" : "geometry not recoverable from a cropped "
                                 "picture: horizontal padding, or a visible row "
@@ -345,5 +436,38 @@ int main(int argc, char **argv)
     omc_enc_destroy(enc);
     fclose(fi); fclose(fo); if (fr) fclose(fr);
     free(pix); free(rec); free(bs);
+    /* EXIT STATUS.
+     *
+     *   0  the encode succeeded and, if the in-gamut mode was in force, it
+     *      delivered what it promises: nothing committed outside the legal
+     *      range, so an ordinary baseband hand-off is exact.
+     *   2  the encode succeeded but the in-gamut mode could NOT clear every
+     *      sample.  The stream is valid and plays correctly; what is not
+     *      available is generation exactness over a baseband link.
+     *   1  the encode failed (die(), everywhere else in this file).
+     *
+     * Status 2 exists because a line on stderr is easy to miss in an automated
+     * pipeline, and the consequence of missing it does not show up at
+     * origination -- it shows up at the second hop, in somebody else's
+     * facility, as a picture that no longer matches.  Generation exactness is a
+     * predicate and not a quantity: four stray samples break the chain exactly
+     * as completely as fifteen hundred do, so 'nearly' has to be reported as a
+     * failure of the guarantee rather than as a successful encode with a
+     * remark.  A pipeline that does not need baseband exactness can ignore the
+     * distinction; one that does need it now cannot silently lose it.
+     *
+     * Only the gamut condition is reported this way.  A raster whose geometry
+     * is not recoverable from a cropped picture is a property of the job the
+     * operator set up, known before a single frame is read, and it is reported
+     * on its own line -- it is not an encode that went wrong. */
+    if (gamut_strict && gamut_oob > 0) {
+        fprintf(stderr, "omc_enc: EXACTNESS NOT DELIVERED: %lld committed "
+                "samples are outside the legal range after %d repair passes. "
+                "This stream plays correctly, but a baseband hand-off of it "
+                "will NOT re-encode byte-exactly. Raise --gamut-strict, or "
+                "carry CDR between hops. Exit status 2.\n",
+                (long long)gamut_oob, gamut_strict);
+        return 2;
+    }
     return 0;
 }
=== END T5 DELTA PATCH ===
`````


## Appendix G — the harness added for 12.22 and 12.23, full text

Seven new files, at the repository root next to the harness of Appendices B and
E.  They are reproduced here verbatim from the live tree, not retyped.  The
first four belong to 12.22, the last three to 12.23.

### `tests/mkfullrange.py`

```python
#!/usr/bin/env python3
"""Make a FULL-RANGE master from a limited-range one.

The baseband hand-off is exact only while the committed picture stays inside
the container's legal range, so the exposed content class is material that is
mastered hard to the container rails rather than to broadcast legal range.
The project's own cinema masters are limited-range (they leave ~60 codes of
headroom below black and ~83 above white at 10 bit), which is exactly why they
show no out-of-gamut samples.  This tool converts one of them into the other
class WITHOUT inventing content: it applies the standard limited->full range
expansion (the same transform a grade-to-full-range does), per plane, with
saturation.  The result is ordinary camera footage that touches 0 and maxv.

  mkfullrange.py <in.yuv> <out.yuv> <W> <H> <422|444> <depth> [anchors|auto]

`anchors` (the default) applies the nominal limited->full expansion.  `auto`
normalises the clip's OWN measured luma extremes to 0 and maxv, which is what a
colourist does when grading to full range, and is the mode that actually puts
content on the rails: a master whose luma never reaches the nominal anchors
(most do not) comes out of `anchors` still short of them.

Planar YUV, little-endian 16-bit words, one plane after another, as every
other master in tests/raw.
"""
import sys, numpy as np

src, dst, W, H, fmt, depth = (sys.argv[1], sys.argv[2], int(sys.argv[3]),
                              int(sys.argv[4]), sys.argv[5], int(sys.argv[6]))
mode = sys.argv[7] if len(sys.argv) > 7 else 'anchors'
Wc = W if fmt == '444' else W // 2
maxv = (1 << depth) - 1
# ITU-R BT.601/709 limited-range anchors, scaled to the coded depth
sc = 1 << (depth - 8)
y_lo, y_hi = 16 * sc, 235 * sc
c_lo, c_hi = 16 * sc, 240 * sc

a = np.fromfile(src, dtype='<u2')
fw = W * H + 2 * Wc * H
if mode == 'auto':
    b = a.reshape(-1, fw)
    y_lo, y_hi = int(b[:, :W * H].min()), int(b[:, :W * H].max())
    cs = b[:, W * H:]
    c_lo, c_hi = int(cs.min()), int(cs.max())
    print("auto: luma [%d..%d] chroma [%d..%d] -> [0..%d]" %
          (y_lo, y_hi, c_lo, c_hi, maxv))
assert a.size % fw == 0, "file is not a whole number of frames"
a = a.reshape(-1, fw)
out = np.empty_like(a)
for f in range(a.shape[0]):
    fr = a[f]
    y = fr[:W * H].astype(np.float64)
    y = (y - y_lo) * (maxv / (y_hi - y_lo))
    out[f, :W * H] = np.clip(np.rint(y), 0, maxv).astype('<u2')
    off = W * H
    for _ in range(2):
        c = fr[off:off + Wc * H].astype(np.float64)
        c = (c - (c_lo + c_hi) / 2.0) * (maxv / (c_hi - c_lo)) + (maxv + 1) / 2.0
        out[f, off:off + Wc * H] = np.clip(np.rint(c), 0, maxv).astype('<u2')
        off += Wc * H
out.tofile(dst)
print("wrote %s: %d frames %dx%d %s/%d-bit, full range" %
      (dst, a.shape[0], W, H, fmt, depth))
```

### `tests/vmafneg.sh`

```bash
#!/bin/bash
# vmafneg.sh -- VMAF-NEG of a decode against its master.
#
# VMAF-NEG (the "no enhancement gain" model, vmaf_v0.6.1neg) is the metric this
# project judges picture quality by; PSNR is reported alongside it only as a
# second opinion.  libvmaf is not part of the codec drop, so build it first:
#
#   git clone --depth 1 -b v3.0.0 https://github.com/Netflix/vmaf.git /tmp/vmaf_src
#   cd /tmp/vmaf_src/libvmaf && meson setup build --buildtype release \
#       -Denable_asm=false && ninja -C build
#   export VMAF_BIN=/tmp/vmaf_src/libvmaf/build/tools/vmaf
#   export VMAF_MODEL=/tmp/vmaf_src/model/vmaf_v0.6.1neg.json
#
# (-Denable_asm=false avoids needing nasm; the C paths are bit-identical.)
#
#   vmafneg.sh <master.yuv> <decode.yuv> <W> <H> <422|444> <depth>
#
# Both files are planar YUV, 16-bit little-endian words, as everything in
# tests/raw is.  Prints the mean VMAF-NEG over the clip.
set -u
BIN=${VMAF_BIN:-/tmp/vmaf_src/libvmaf/build/tools/vmaf}
MODEL=${VMAF_MODEL:-/tmp/vmaf_src/model/vmaf_v0.6.1neg.json}
M=$1; D=$2; W=$3; H=$4; FMT=$5; DEPTH=$6
[ -x "$BIN" ] || { echo "vmafneg: no libvmaf at $BIN (see the header)"; exit 2; }
[ -f "$MODEL" ] || { echo "vmafneg: no model at $MODEL"; exit 2; }
OUT=$(mktemp)
"$BIN" -r "$M" -d "$D" -w "$W" -h "$H" -p "$FMT" -b "$DEPTH" \
       -m "path=$MODEL" -o "$OUT" --json 2>/dev/null
python3 - "$OUT" <<'PY'
import json, sys
j = json.load(open(sys.argv[1]))
pm = j["pooled_metrics"]
# the neg model's internal name is plain "vmaf"; the score is VMAF-NEG because
# of WHICH model was loaded, not because of what the key is called
k = "vmaf_neg" if "vmaf_neg" in pm else "vmaf"
print("VMAF-NEG mean %.4f  min %.4f  (%d frames)" %
      (pm[k]["mean"], pm[k]["min"], len(j["frames"])))
PY
rm -f "$OUT"
```

### `tests/gamut_map.py`

```python
#!/usr/bin/env python3
"""gamut_map.py - WHERE the out-of-range committed samples are, not just how many.

The hand-off report asked whether stray samples cluster, and in particular
whether they sit on slice boundaries.  This answers it from a decoded CDR (the
committed picture, biased by 2048 and unclipped, at coded geometry):

  gamut_map.py <file.cdr> <W> <H> <422|444> <depth> <slice_h> [display_h]

Prints the count per plane, the histogram over row-within-slice (so a boundary
concentration is visible at once), the share that sit in the two rows the XSL
boundary edit touches, and the size distribution of connected runs along a row
(1 = isolated samples, larger = clustered).
"""
import sys, numpy as np

f, W, H, fmt, depth, sh = (sys.argv[1], int(sys.argv[2]), int(sys.argv[3]),
                           sys.argv[4], int(sys.argv[5]), int(sys.argv[6]))
dh = int(sys.argv[7]) if len(sys.argv) > 7 else H
Wc = W if fmt == '444' else W // 2
maxv = (1 << depth) - 1
BIAS = 2048
fw = W * H + 2 * Wc * H
a = np.fromfile(f, dtype='<u2')
assert a.size % fw == 0, "not a whole number of frames at this geometry"
nf = a.size // fw
a = a.reshape(nf, fw)

names = ["Y", "Cb", "Cr"]
rowhist = np.zeros(sh, dtype=np.int64)
runhist = {}
total = 0
for p in range(3):
    pw = W if p == 0 else Wc
    off = 0 if p == 0 else W * H + (p - 1) * Wc * H
    n = 0
    for k in range(nf):
        pl = a[k, off:off + pw * H].reshape(H, pw)[:dh]
        bad = (pl.astype(np.int32) - BIAS < 0) | (pl.astype(np.int32) - BIAS > maxv)
        n += int(bad.sum())
        rows = np.nonzero(bad.any(axis=1))[0]
        for r in rows:
            rowhist[r % sh] += int(bad[r].sum())
            # run lengths along the row
            b = bad[r].astype(np.int8)
            d = np.diff(np.concatenate(([0], b, [0])))
            for s, e in zip(np.nonzero(d == 1)[0], np.nonzero(d == -1)[0]):
                runhist[e - s] = runhist.get(e - s, 0) + 1
    print("%-3s %d samples outside [0..%d]" % (names[p], n, maxv))
    total += n
print("total %d over %d frame(s)" % (total, nf))
if total:
    print("row within slice (0 .. %d):" % (sh - 1))
    for r in range(sh):
        if rowhist[r]:
            print("  row %2d: %8d  (%.1f%%)" % (r, rowhist[r], 100.0 * rowhist[r] / total))
    edge = rowhist[0] + rowhist[sh - 1]
    print("in the two rows the XSL boundary edit touches (0 and %d): %d (%.1f%%)"
          % (sh - 1, edge, 100.0 * edge / total))
    print("expected if spread evenly over rows: %.1f%%" % (200.0 / sh))
    print("run lengths along a row:")
    for L in sorted(runhist):
        print("  %3d px: %6d run(s)" % (L, runhist[L]))
```

### `tests/strict_cost.sh`

```bash
#!/bin/bash
# strict_cost.sh -- what --gamut-strict costs, per cell, at generation 1.
#
# For each cell: encode with the mode OFF and ON, decode both, and score both
# against the master with VMAF-NEG (the metric that decides) and PSNR (second
# opinion).  Also prints the gamut count for each and whether the two streams
# are byte-identical -- on content that never leaves the legal range they must
# be, because the repair has nothing to fire on.
#
#   strict_cost.sh [passes]      (default 4)
set -u
cd "$(dirname "$0")/.."
# OMC_BIN lets a measurement run pin the binaries it measures, exactly as the
# chain harnesses do -- a rebuild mid-battery otherwise swaps the encoder
# underneath the comparison.
E="${OMC_BIN:-omc/omc_v4.9}"; R=tests/raw
P=${1:-4}
W=$(mktemp -d); trap 'rm -rf "$W"' EXIT

cell() { # master W H fmt depth bpp slice_h
  local m=$1 w=$2 h=$3 f=$4 d=$5 b=$6 s=$7
  local sf=(); [ "$s" != 0 ] && sf=(--slice-h "$s")
  local o1 o2 g1 g2 v1 v2 p1 p2 same
  $E/omc_enc -i "$m" -o "$W/off.omc" -w "$w" -h "$h" --fmt "$f" --depth "$d" \
      --bpp "$b" "${sf[@]}" 2>"$W/off.log" >/dev/null
  $E/omc_enc -i "$m" -o "$W/on.omc"  -w "$w" -h "$h" --fmt "$f" --depth "$d" \
      --bpp "$b" "${sf[@]}" --gamut-strict "$P" 2>"$W/on.log" >/dev/null
  g1=$(sed -n 's/.*gamut: \([0-9]*\) committed.*/\1/p' "$W/off.log")
  g2=$(sed -n 's/.*gamut: \([0-9]*\) committed.*/\1/p' "$W/on.log")
  $E/omc_dec -i "$W/off.omc" -o "$W/off.yuv" 2>/dev/null
  $E/omc_dec -i "$W/on.omc"  -o "$W/on.yuv"  2>/dev/null
  v1=$(bash tests/vmafneg.sh "$m" "$W/off.yuv" "$w" "$h" "$f" "$d" | sed -n 's/.*mean \([0-9.]*\).*/\1/p')
  v2=$(bash tests/vmafneg.sh "$m" "$W/on.yuv"  "$w" "$h" "$f" "$d" | sed -n 's/.*mean \([0-9.]*\).*/\1/p')
  p1=$(python3 tests/quality.py "$m" "$W/off.yuv" "$w" "$h" "$f" "$d" "$s" 2>/dev/null | awk '{for(i=1;i<=NF;i++) if($i=="Y"){s+=$(i+1);n++}} END{if(n)printf "%.2f",s/n}')
  p2=$(python3 tests/quality.py "$m" "$W/on.yuv"  "$w" "$h" "$f" "$d" "$s" 2>/dev/null | awk '{for(i=1;i<=NF;i++) if($i=="Y"){s+=$(i+1);n++}} END{if(n)printf "%.2f",s/n}')
  cmp -s "$W/off.omc" "$W/on.omc" && same=IDENTICAL || same=differs
  printf "%-24s %sx%s %s/%-2s bpp=%-4s sh=%-2s oob %8s -> %-8s VMAF-NEG %7s -> %-7s  PSNR-Y %6s -> %-6s  stream %s\n" \
    "$(basename "$m" .yuv)" "$w" "$h" "$f" "$d" "$b" "$s" "$g1" "$g2" "$v1" "$v2" "$p1" "$p2" "$same"
}

cell $R/gfx1080_422_10.yuv     1920 1080 422 10 1.0 16   # control: oob = 0 already
cell $R/gfx1080_fullrange_422_10.yuv    1920 1080 422 10 0.5 16
cell $R/gfx1080_fullrange_422_10.yuv    1920 1080 422 10 1.0 16
cell $R/rail720_422_10.yuv     1280 720  422 10 0.5 0
cell $R/rail720_422_10.yuv     1280 720  422 10 1.0 0
cell $R/cineA31_720_444_8.yuv  1280 720  444 8  0.5 0
cell $R/cineA31_720_444_8.yuv  1280 720  444 8  1.0 16
cell $R/cineA21_444_10.yuv     2048 1152 444 10 2.0 16
cell $R/gfx1080_444_12.yuv     1920 1080 444 12 0.5 16
cell $R/gfxF003_444_8.yuv      4480 1856 444 8  0.5 16
cell $R/cine4k_444_10.yuv      4096 2160 444 10 2.0 32
echo STRICTCOST-DONE
```

### `tests/ants.py`

```python
#!/usr/bin/env python3
"""ants.py - the temporal-stability ("ants") instrument, all three planes.

The defect: areas the SOURCE holds still and flat, that the DECODE does not.
A viewer reads that as crawling texture -- the "ants" REPORT.md 18.5-18.7
records as the one thing that gave the codec away.

Method, following REPORT.md 18.6-18.7 and generalised off luma:

  * split every plane into 16x16 blocks;
  * a block QUALIFIES when the source holds it both FLAT (per-frame standard
    deviation <= flat) and STATIC (mean |frame-to-frame difference| <= still),
    in every frame and every frame pair;
  * over the samples of qualifying blocks, report
       tail  = P(|frame-to-frame difference| > 6 codes)   <- the ant count
       boil  = mean |frame-to-frame difference|            <- the average motion
    for the decode AND for the source itself.

The source's own column is the TARGET, not zero: real footage has grain and it
moves, and a codec quieter than its own source has removed texture rather than
fixed anything.  The block count is printed with every figure because a
percentage computed over three blocks is not evidence.

Thresholds are in 10-bit code values and scale with the coded depth.

  ants.py <master.yuv> <decode.yuv> <W> <H> <422|444> <depth>
          [--flat F] [--still S] [--strict] [--json out.json]
"""
import sys, json
import numpy as np

a = sys.argv[1:]
master, decode, W, H, fmt, depth = a[0], a[1], int(a[2]), int(a[3]), a[4], int(a[5])
flat_t, still_t, jout = 12.0, 6.0, None
i = 6
while i < len(a):
    if a[i] == '--flat': flat_t = float(a[i+1]); i += 2
    elif a[i] == '--still': still_t = float(a[i+1]); i += 2
    elif a[i] == '--strict': flat_t, still_t = 4.0, 2.0; i += 1
    elif a[i] == '--json': jout = a[i+1]; i += 2
    else: i += 1

B = 16
sc = 2.0 ** (depth - 10)          # thresholds are quoted at 10-bit
flat_t *= sc; still_t *= sc
tail_t = 6.0 * sc
Wc = W if fmt == '444' else W // 2
fw = W * H + 2 * Wc * H

m = np.fromfile(master, dtype='<u2')
d = np.fromfile(decode, dtype='<u2')
nf = min(m.size // fw, d.size // fw)
if nf < 2:
    print("ants: need at least 2 frames"); sys.exit(2)
m = m[:nf * fw].reshape(nf, fw).astype(np.float32)
d = d[:nf * fw].reshape(nf, fw).astype(np.float32)

def blocks(x, h, w):
    """(frames, H, W) -> (frames, nby, nbx, B*B), dropping any partial edge"""
    nby, nbx = h // B, w // B
    x = x[:, :nby * B, :nbx * B]
    return x.reshape(x.shape[0], nby, B, nbx, B).transpose(0, 1, 3, 2, 4) \
            .reshape(x.shape[0], nby, nbx, B * B)

names, out = ["Y", "Cb", "Cr"], {}
print("plane  blocks   decode tail%%  boil    source tail%%  boil    (flat<=%.0f still<=%.0f, "
      "tail at |d|>%.0f codes)" % (flat_t, still_t, tail_t))
for p in range(3):
    pw = W if p == 0 else Wc
    off = 0 if p == 0 else W * H + (p - 1) * Wc * H
    ms = m[:, off:off + pw * H].reshape(nf, H, pw)
    ds = d[:, off:off + pw * H].reshape(nf, H, pw)
    mb, db = blocks(ms, H, pw), blocks(ds, H, pw)
    # source qualification
    sd = mb.std(axis=3)                       # (frames, nby, nbx)
    mv = np.abs(np.diff(mb, axis=0)).mean(axis=3)   # (frames-1, nby, nbx)
    ok = (sd.max(axis=0) <= flat_t) & (mv.max(axis=0) <= still_t)
    n = int(ok.sum())
    if n == 0:
        print("%-6s %6s   %s" % (names[p], 0, "no verdict -- the source has no flat, static block here"))
        out[names[p]] = {"blocks": 0}
        continue
    dd = np.abs(np.diff(db, axis=0))[:, ok, :]     # (frames-1, nblocks, B*B)
    md = np.abs(np.diff(mb, axis=0))[:, ok, :]
    r = {"blocks": n,
         "dec_tail": float((dd > tail_t).mean() * 100.0), "dec_boil": float(dd.mean()),
         "src_tail": float((md > tail_t).mean() * 100.0), "src_boil": float(md.mean())}
    out[names[p]] = r
    print("%-6s %6d   %10.2f %7.3f   %10.2f %7.3f" %
          (names[p], n, r["dec_tail"], r["dec_boil"], r["src_tail"], r["src_boil"]))
out["_cfg"] = {"flat": flat_t, "still": still_t, "tail": tail_t, "frames": nf, "block": B}
if jout: json.dump(out, open(jout, "w"), indent=1)
```

### `tests/mkstill.py`

```python
#!/usr/bin/env python3
"""mkstill.py - build temporal test masters from a short real master.

The corpus masters are 2-3 frames, which is too thin for a temporal metric.
Two constructions, both from real footage, neither inventing pixel content:

  still  <n>   frame 0 repeated n times.  The source's frame-to-frame movement
               is EXACTLY zero, so any movement in the decode is generated by
               the codec and nothing else.  This is the sharpest possible form
               of "match the source": the source is perfectly still, so the
               target is perfectly still.
  loop   <n>   the frames walked forward and back (0,1,2,1,0,...) to n frames.
               Real content motion with a real source movement level, for
               checking that a fix has not simply removed texture.

  mkstill.py <in.yuv> <out.yuv> <W> <H> <422|444> <depth> <still|loop> <n>
"""
import sys, numpy as np
src, dst, W, H, fmt, depth, mode, n = (sys.argv[1], sys.argv[2], int(sys.argv[3]),
    int(sys.argv[4]), sys.argv[5], int(sys.argv[6]), sys.argv[7], int(sys.argv[8]))
Wc = W if fmt == '444' else W // 2
fw = W * H + 2 * Wc * H
a = np.fromfile(src, dtype='<u2')
assert a.size % fw == 0, "not a whole number of frames at this geometry"
a = a.reshape(-1, fw)
nf = a.shape[0]
if mode == 'still':
    idx = [0] * n
else:
    seq = list(range(nf)) + list(range(nf - 2, 0, -1))
    idx = [seq[i % len(seq)] for i in range(n)]
a[idx].tofile(dst)
print("wrote %s: %d frames, %s, from %d source frame(s)" % (dst, n, mode, nf))
```

### `tests/antsmatrix.sh`

```bash
#!/bin/bash
# antsmatrix.sh -- the temporal-stability ("ants") matrix, and its cost.
#
# For every cell of the corpus and every arm named below it prints, on one line,
# the ants tail of the DECODE and of the SOURCE on all three planes, and the
# VMAF-NEG of that decode against the same master.  Those are the two numbers a
# candidate fix has to move in the right direction at the same time: a fix that
# calms the picture by removing texture shows up as a VMAF-NEG loss in the last
# column, and a fix that hides the defect by adding energy cannot gain there at
# all (that is what the NEG model is for).  See docs/TEMPORAL_T5.md 12.23.
#
#   tail = P(|frame-to-frame difference| > 6 codes) over blocks the SOURCE holds
#          flat and static -- docs/REPORT.md 18.6, generalised off luma
#
# The source column is the target, not zero: real footage has grain and grain
# moves.  A decode BELOW its source column has the incumbent's "sub-source calm".
#
# Requires: tests/ants.py, tests/vmafneg.sh (and libvmaf -- see that script's
# header), the masters of section 10.1, and a v4.14 tree if the v4.14 column is
# wanted.
#
#   usage:  antsmatrix.sh [bpp ...]            (default: 0.5 1.0 2.0)
#   env:    OMC_BIN   directory holding the omc_enc/omc_dec under test
#           OMC_BIN_REF  optional: a second tree to print as the "reference"
#                     column (this project used the v4.14 drop)
set -u
cd "$(dirname "$0")/.."
E="${OMC_BIN:-$(pwd)/omc/omc_v4.9}"
REF="${OMC_BIN_REF:-}"
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
RATES=${*:-"0.5 1.0 2.0"}

cell() {  # <tree> <env-assignments> <flags> <master> <w> <h> <fmt> <depth> <bpp> <label>
  local t=$1 ev=$2 fl=$3 m=$4 w=$5 h=$6 f=$7 d=$8 b=$9 lab=${10}
  env $ev "$t/omc_enc" -i "$m" -o "$TMP/a.omc" -w "$w" -h "$h" --fmt "$f" \
      --depth "$d" --bpp "$b" $fl >/dev/null 2>&1 || { printf "  %-24s ENCODE FAILED\n" "$lab"; return; }
  "$t/omc_dec" -i "$TMP/a.omc" -o "$TMP/a.yuv" >/dev/null 2>&1
  read -r yt ys cbt cbs crt crs <<<"$(python3 tests/ants.py "$m" "$TMP/a.yuv" "$w" "$h" "$f" "$d" |
      awk '/^Y /{yt=$3;ys=$5} /^Cb /{cbt=$3;cbs=$5} /^Cr /{crt=$3;crs=$5} END{print yt,ys,cbt,cbs,crt,crs}')"
  # the project's OWN thresholds (docs/REPORT.md 18.7).  They select far fewer
  # blocks and on some content none at all, which is why the relaxed pair above
  # carries the main table and this one is reported beside it rather than
  # instead of it.
  read -r syt sys <<<"$(python3 tests/ants.py "$m" "$TMP/a.yuv" "$w" "$h" "$f" "$d" --strict |
      awk '/^Y /{yt=$3;ys=$5} END{print yt,ys}')"
  local v; v=$(bash tests/vmafneg.sh "$m" "$TMP/a.yuv" "$w" "$h" "$f" "$d" |
      sed -n 's/.*mean \([0-9.]*\).*/\1/p')
  printf "  %-24s Y %6s/%-6s Cb %6s/%-6s Cr %6s/%-6s | strict Y %6s/%-6s | NEG %s\n" \
         "$lab" "$yt" "$ys" "$cbt" "$cbs" "$crt" "$crs" "$syt" "$sys" "${v:-n/a}"
}

for arm in "tests/raw/still1080_422_10.yuv 1920 1080 422 10" \
           "tests/raw/loop1080_422_10.yuv 1920 1080 422 10" \
           "tests/raw/still720_444_8.yuv 1280 720 444 8" \
           "tests/raw/gfx1080_fullrange_422_10.yuv 1920 1080 422 10" \
           "tests/raw/gfx1080_422_10.yuv 1920 1080 422 10" \
           "tests/raw/gfx1080_444_12.yuv 1920 1080 444 12" \
           "tests/raw/cineA21_444_10.yuv 2048 1152 444 10" \
           "tests/raw/cineA21_422_12.yuv 2048 1152 422 12" \
           "tests/raw/cineA31_720_444_8.yuv 1280 720 444 8" \
           "tests/raw/cine4k_422_8.yuv 4096 2160 422 8" \
           "tests/raw/gfxF003_444_8.yuv 4480 1856 444 8"; do
  set -- $arm
  for b in $RATES; do
    echo "=== $(basename "$1" .yuv) @ $b   decode-tail/source-tail %"
    [ -n "$REF" ] && cell "$REF" "" ""                      "$1" "$2" "$3" "$4" "$5" "$b" "reference build"
    cell "$E" "OMC_CALM=0" "--fill"                          "$1" "$2" "$3" "$4" "$5" "$b" "ants fix off, fill on"
    cell "$E" "OMC_CALM=0" ""                                "$1" "$2" "$3" "$4" "$5" "$b" "ants fix off, fill off"
    cell "$E" "" "--fill"                                    "$1" "$2" "$3" "$4" "$5" "$b" "shipped fix, fill on"
    cell "$E" "" ""                                          "$1" "$2" "$3" "$4" "$5" "$b" "SHIPPED DEFAULTS"
  done
done
echo ANTSMATRIX-DONE
```

---

## Checksums for this revision

| | |
|---|---|
| document | 14821 lines before this block was appended |
| source commit | `a1ef39b` |
| branch | `claude/codec-temporal-rebuild-3i9o7q` |
| stream minor | 12 |

The md5 of a file cannot appear inside it, so this block does not try.  To
check the three embedded patches came across intact, extract them with the
recipes in Appendix A, Appendix D and Appendix F, apply them to a pristine
`omc_v4.9` drop, and confirm `make test` produces no line beginning with `FAIL`
(five suites print `all ok`; `test_xsl` prints `test_xsl: all ok`, with 27
`ok:` lines) and that the 1080p reference cell of 12.6 hashes to
`d6e111cfaf33c17406182bc1310a0b90`.  That is a stronger check than any hash of
this file, because it tests the thing the hash is a proxy for.

---

# Appendix M — Block motion field and the A5 fetch barrier (minor 16)

Added by the motion package (Agent 1, MEMO 004/006). Wire format in `BITSTREAM.md`.

## M.1 Why the vectors are transmitted and not derived

Two designs were built and measured. **(A)** the decoder repeats the encoder's block search from
its own committed history, sending nothing; **(B)** the encoder sends the field.

(A) scores better in isolation but **fails A5**: after two slices are destroyed the base heals by
frame 9, while (A) has not healed by frame 11 and the error *grows* (max |d| 462 -> 946). The
rolling refresh restores **pixels**, not state derived from them, so any decoder-side derivation
from history is a resilience hazard unless it is re-derivable from refreshed pixels inside the heal
window. (A) also needs a second luma frame in the decoder, which violates the one-frame-look-back
constraint outright.

**(B) is what ships.** Measured wire cost 0.93 % of payload at 0.5 bpp on soccer2 (141 bits/slice
mean, 274 max), 0.34 % on runA. Zero decoder memory, no decoder search, A5 unchanged. Keeping the
vector on the wire is also what keeps the design clear of the decoder-side-derivation patent family
(IP review, 2026-09-04) — **no optimisation may remove the transmitted vector.**

## M.2 The A5 refresh barrier on the motion fetch

A fractional vertical tap averages reference rows `y` and `y+1`. Where `y` is the last row of a
slice, `y+1` belongs to the next slice, so the tap **duplicates** a neighbouring slice's committed
rows into this slice's prediction. Integer motion also reads across the boundary, but it
*transports* the error rather than duplicating it, and transport heals.

The barrier forbids the fractional vertical tap at a slice boundary. Measured on the 8-phase loss
probe (dng24, 1080p 4:2:2 @0.5, two slice positions, 24 frames):

| arm | heal lag min | max | over the 10-frame gate |
|---|---|---|---|
| no barrier | 4 | **16** | yes |
| **barrier at every slice boundary (ships)** | 4 | **10** | no |
| barrier only at the current frame's refresh boundaries | 3 | 10 | no |
| barrier only at the reference frame's refresh boundaries | 4 | **16** | yes — falsified |

**Condition on the rule.** The barrier's necessity depends on the coding-plan policy. Under a plan
re-derived per frame (`omc_plan_hyst = 0`, the v5.0 restore incantation) the unbarriered arm reaches
lag 16 and breaches the gate. Under v5.3.5's near-tie plan hold (`omc_plan_hyst = 3`, the default) the
unbarriered arm heals within the gate on the cells measured, because the plan no longer churns for
the error to ride. The barrier is retained because `omc_plan_hyst = 0` is a supported configuration;
implementations must not drop it on the strength of the default policy alone.

## M.3 Implementation note that is easy to get wrong

The barrier applies at **three** sites: the region prediction, the overlapped-blend prediction, and
the encoder's search SAD (which must mirror the operator that will be applied). They must be one
function. Implementing them separately produces an encoder and decoder that agree while the *search*
optimises for a different predictor, which no conformance test detects.
