# §15. F0 — the grain fill out of the normative reconstruction

*Owner decision 2026-09-06, executed 2026-09-14. Independently landable: its own diff against the
frozen base (`diffs/f0_fill_removal.diff`), its own gate, its own package. **No dependency on the
transform rebuild or on F2c.** Sandbox tree `f0tree2/`; `.work/v537` untouched.*

## §15.1 The premise, verified before anything was deleted

The instruction's premise is that the fill is already off, so nothing measurable may change. I did
not assume it — I measured it on the **frozen base**:

| cell | @0.5 | @1.0 | @2.0 |
|---|---|---|---|
| dng 720p | default ≡ `--no-fill` | ≡ | ≡ |
| cf_gfx | ≡ | ≡ | ≡ |
| spotrobotL | ≡ | — | — |

and the signalled fields are zero everywhere: `fill_mask = 0x000000` and `fill_gain = 0,0,0` on
**every slice** of dng 720p, cf_gfx and spotrobotL. **So the fill is inert at the shipped defaults,
deletion must be byte-identical, and byte-identity is therefore a real gate rather than a hope.**

## §15.2 What was removed

`diffs/f0_fill_removal.diff` — **599 lines removed, 37 added, net −562**, all in `src/codec.c`.

**The normative reconstruction path** (the whole point of F0):

| removed | what it was |
|---|---|
| `fill_value_p`, `fill_value_h`, `fill_value` | the function that painted a value into a coefficient the encoder had coded as zero — the only place the fill entered the decoder's output |
| `fill_gate`, `fill_gate_g`, `fill_gate_g_raw` | the activity ("ants") tier gate that decided which zero positions were eligible |
| `fp_t`, `fp_hint`, `fp_build`, `fp_build_arr` | the fill predictor context (local coded structure used to choose the fill sign) |
| `fg_memo_t`, `FG_MEMO_INIT` | the per-band fill-gate memo |
| the 4 paint call sites | `verify_candidate`'s lock check, the encoder's DC-feedback sweep, the encoder's committed-reconstruction sweep, **and the decoder's reconstruction loop** |
| `verify_candidate`'s fill-bit derivation block | the encoder's re-derivation of the fill bit during the generation-lock check |
| the locals that existed only to feed them | `ll`, `llw`, `llh`, `lllim`, `fcol`, `w`, `vvis` at 14 sites |

**The syntax** (BITSTREAM §3.1):

* the **18 grain-fill bits** are now written as zero and are **RESERVED, must be zero**;
* the **6 per-plane fill-gain bits** likewise;
* **the decoder refuses any stream that signals either** — `if (fill_mask) return -1;` and the same
  for each gain — so a stream that would ask for the fill is rejected, not silently ignored. That is
  the validator behaviour the instruction asks for.

**Kept deliberately, because it serves another purpose** (the instruction's rule):

| kept | why |
|---|---|
| `OMC_FILL_BANDS_FROM` (= 4) | it is the **deadzone's** band range (`omc_quant1b_dz` is armed for `b >= OMC_FILL_BANDS_FROM`) and the level-1/2 band boundary used throughout the quantiser. Only its *name* is a fill name |
| `OMC_FILL_MIN_SHIFT` | still referenced by the `can_fill` guard that remains inert; a follow-up rename is cosmetic |
| `e->elig[][]` (the OMC_GR noise-class maps) | the grain-**replace** classifier, a different mechanism |
| the per-slice fill-decision block (~410 lines) | **see §15.4 — attempted, reverted, and why** |

## §15.3 The gate

| check | result |
|---|---|
| build | `make all`, **0 warnings, 0 errors** |
| **streams byte-identical to the frozen base** | dng 720p, cf_gfx, spotrobotL, dng 1080p, dng 4:4:4 12-bit, dng 4:2:2 8-bit × 0.5 / 1.0 / 2.0 bpp, 12 frames — **identical on every point** |
| **decodes byte-identical** | same points — **identical on every point** |
| exit codes | every encode and decode rc 0 |
| **full suite** | **FAILS — see §15.6. 7 of the legality gates fail; the pristine base control passes them all** |
| chain | not run: the suite verdict makes it moot |

## §15.6 The suite — what is established and what is still running

**On the OVER-REACHING tree (`f0tree`, §15.4, the one that already failed byte-identity)** the suite
reported **7 FAIL against 46 ok**, and every failure was a legality gate:

| gate | what it asserts |
|---|---|
| **G-T5-GAMUT2a** | with `--gamut-strict` the committed picture stays inside the legal range — *reported: 44,923 out of range with the repair off, **100** with it on (the gate wants 0)* |
| **G-T5-GAMUT2c** | the pathological rail arm is CLOSED, not merely 99 % closed |
| **G-T5-GAMUT2b** | and its baseband chain is byte-exact |
| **G-T5-GAMUT5d** | the alignment veto still reaches zero out-of-range inside the pass budget |
| **G-T5-CUT4** | hard black/white plates at the exact rails close completely — *reported: 84 out of range alone, 108 cut against ordinary footage* |
| **G-T5-CUT24** | the 24-frame cut probe commits no out-of-range sample at any refresh period — *reported: oob 866–2,713, unfixed 17–35* |
| **G-T5-CAP2** | at the real cap nothing is stopped and no out-of-range sample is committed |

**Those 7 failures cannot be attributed to the delivered scope**, and I nearly reported them as if
they could. Two of my background runs wrote `make test` output to the same path — one from `f0tree`
(broken) and one from `f0tree2` (delivered) — so `out/F0/suite.txt` is ambiguous. That is the third
harness collision of this session and it is entirely mine: too many overlapping background jobs
sharing filenames.

**The clean run**, `f0tree2` alone with nothing else on the machine, writing to
`out/F0/suite_f0tree2.txt`: **0 FAIL, 46 ok** at the point this report was written, still inside
`test_xsl` where the GAMUT and CUT gates live. The pristine control `basectl` is at the same point
with **0 FAIL, 46 ok**. **The suite verdict for the delivered scope is therefore PENDING**, and F0
is not signed off until it lands.

**What the `f0tree` failures do tell us, and it is worth keeping**: they were all legality gates
(GAMUT2a/2b/2c/5d, CUT4, CUT24, CAP2), reporting 100 out-of-range samples where the gate wants 0 and
oob 866–2,713 on the 24-frame cut probe. Whatever the over-reaching cut removed, it was load-bearing
for the repair on rail-graded synthetic content. That is a lead for the follow-up bisect, not a
verdict on the fill.

## §15.4 What I tried, broke, and reverted — recorded because it is the useful part

I also cut the **per-slice fill-decision block** (~410 lines: the activity tier gate, the fill-bit
threshold and its chroma variant, the amplitude ladder and its hysteresis, the temporal mask
dead-band, the intra/plane restrictions, the DC-feedback freeze) together with the dead bookkeeping
it fed (`gm_nofill`, `lock_fmask`, `lock_gain`, `dc3_frozen`).

**It broke byte-identity**: dng 720p @1.0 and cf_gfx @0.5 produced different streams, and
spotrobotL @0.5 made the encoder exit 2 (a refusal). Re-running the inertness check on the frozen
base at the same points showed the fill **is** inert there, so the cause was my cut, not the fill:
**that block has a side effect outside the fill that I did not isolate.** I reverted to the scope
above, which gates clean, and I am not guessing at the culprit in the report.

**Consequence for the package:** F0 as delivered removes the fill from the **normative
reconstruction, the syntax and the decoder** — which is what F0 is for — and leaves an inert
encoder-side decision block whose output is forced to zero two lines before it is used. That block
is dead weight, not a mechanism; removing it is a follow-up that needs its own bisect, and it
cannot affect any decoder.

## §15.5 Provenance

Nothing removed was ever anything but own work (the grain fill and its gate were developed in this
project, v4.0 through v5.2 sect.65/80). It is **removed, not replaced**: no substitute mechanism is
introduced, and the reconstruction of a zero-coded coefficient is now exactly `dequant(0) = 0` plus
the prediction, as it was before v4.0.
