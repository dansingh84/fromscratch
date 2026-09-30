## §8.6 (e) The lock — the control passes, the field arm does not, and the reason is a build finding

**The chain.** `notes/chain8.sh`: generation *g* encodes the **display decode** of generation
*g−1* (the legal baseband hop), same rate, same flags, 4 frames, dng 720p. PASS = 0 bytes moved
from generation 2 and the stream identical from generation 3.

| | g2 | g3 | g4 | g5 | stream | verdict |
|---|---|---|---|---|---|---|
| **base control** (`OMC_SA7F` unset, frozen behaviour) | **0** | **0** | **0** | **0** (through g8) | DIFF at g2, **SAME from g3 onward** | **PASS** — reproduces S5.176's control exactly, so the harness is right |
| **arm 4** (content-independent field, both ends, nothing signalled) | **1,917,258** | 1,522,685 | 1,360,187 | 1,210,427 | DIFF throughout | **FAIL** |

Decay ratios 0.79, 0.89, 0.89 — drifting, not settling, the same signature S5.176 measured on the
rail exception layer. The run was stopped at generation 5 after the field arm's encode time grew
generation on generation (the repair works harder as the picture degrades); generations 6–8 would
have added nothing to a verdict already decided at generation 2. Log: `out/C/chains.txt`.

**A discriminator on the most likely cause: it is not the grain fill.** Repeating both arms with
`--no-fill` (2 frames, so compare per frame):

| | base, moved at g2 | arm 4, moved at g2 | arm 4, g3 |
|---|---|---|---|
| fill on (4 frames) | **0** | 1,917,258 → **479k/frame** | 1,522,685 |
| **fill off** (2 frames) | **0** | 816,456 → **408k/frame** | 513,455 |

Turning the fill off removes about **15 %** of the damage and the base still locks exactly. So the
`can_fill`-versus-`coeff_shift` inconsistency is real but minor; the bulk of the failure is
elsewhere in the plan machinery that reads `sp.shift[p][b]` directly — the targeted-partial rank
and the per-band cost model are the two remaining candidates, and I did not isolate further.

Arm 4 was built precisely so the field could not be blamed on signalling: it is a fixed function of
`(slice index, control point)` computed identically in `omc_enc` and `omc_dec`, and **`rt = 0`
holds with it live** (the decoder's output equals `--recon − 2048` byte for byte, and the encoder
prints `baseband-safe: yes`). So the committed picture *is* the decode of the emitted symbols, and
it *is* a lattice point of the field-modified plan. The lattice property holds. The **lock** does
not.

**Why, and this is a build finding rather than a property of the mechanism.** My probe applies the
field in exactly one place — `coeff_shift()` — and `verify_candidate` does call `coeff_shift()`
(`src/codec.c:5387`), so the lock trial does see the field. But the codec makes several *decisions*
from the band-level `sp.shift[p][b]` directly, and those are now inconsistent with the
per-coefficient shift actually used:

* **fill eligibility**: `int base_s = sp.shift[p][b]; int can_fill = b >= OMC_FILL_BANDS_FROM &&
  base_s >= OMC_FILL_MIN_SHIFT && …` (`src/codec.c:5380`, and the same pattern in the emission
  path) — the *eligibility* is decided on the unfielded shift while the fill *value* is computed at
  `coeff_shift()`'s fielded shift;
* **the targeted-partial rank**: `omc_tpart_rank` is fed `omc_quant1b(c_, ls_, 0)` with
  `ls_ = sp.shift[tp_][0]`, the unfielded LL shift, while the LL was quantised at the fielded one;
* **the band cost model** `bandcost[m][p][b].bits[sft]` is indexed by a single band shift, which no
  longer describes a band whose coefficients sit at several shifts.

Any of these makes the plan the encoder re-derives at generation 2 differ from the one it emitted
at generation 1, and the picture then moves. **The conclusion is not "a field breaks the lock" —
it is "a field cannot be bolted onto `coeff_shift()` alone".** Every place that reasons about *the
band's shift* has to become field-aware, which is a real and sizeable build, and it is the honest
cost of this mechanism that the sizing in §7.9 did not include.

**What remains true of the lock, analytically** (§8.5): the committed picture is a lattice point of
a signalled plan; `verify_candidate` needs **no** escape-style extension; and generation 2 can
*derive* a reproducing field constructively from the trailing-zero count of the received
coefficients, in one traversal, with no search. Those three things are what would make the field
lock-safe, and none of them is contradicted by the arm-4 result. I did not build them, so I do not
claim them measured.

**A process note, because it nearly produced a false number.** Two copies of the chain script ran
concurrently for a while, writing to the same output paths, after a wait-loop of the form
`until ! pgrep -f chain8.sh` matched **its own shell** and never exited — the trap already recorded
in COMMON_RULES (`pgrep -f` matches the process running it). The affected outputs were deleted and
both chains re-run alone, identified by `/proc/<pid>/cwd` inside my own tree; no raced number is in
this report.
