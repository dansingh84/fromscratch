# §10. Loop iteration 5 — the WITHIN-BIN TWO-PHASE PASS, escapes in the bitstream (L-I22), step 1

## §10.1 What was built — the escape is now a real bitstream element, and it round-trips

`ptree3`, `[SA7-ESCSYN]` (`src/sa7_esc.inc`, hooks in `src/codec.c`) and `[SA7-Q]`
(`src/latt_probe.inc`). This is the first iteration in which the escape **exists in the stream**:

* **Syntax.** The 14 header bits documented "reserved, must be zero (minor 14)" carry `esc_bits`,
  the bit length of an escape list that **prefixes the payload**. `used_bits` covers both, so the
  CRC, the wire cap and the bank bounds cover the escapes with no further change. List =
  `n_esc` (10 b), `k` (3 b), then per escape, in ascending flat-index order, a 5-bit-exponent +
  mantissa position delta and a `k`-bit two's-complement value. The payload's backward tANS reader
  never reaches the prefix (it consumes from the tail), so the two coexist without interleaving.
* **Semantics.** The escape displaces the **dequantised** coefficient by `val << (s−k)` on the
  **magnitude**, inside bin `q` per the §7.1 window (half-open, deadzone-lifted for `|q| = 1`,
  `q = 0`-in-a-fill-band excluded). The base index never changes, so the committed picture is still
  a lattice point of the signalled plan plus a signalled in-bin offset.
* **The pass.** Phase 1's demand is now a **coefficient-domain displacement**, and phase 2 splits it
  into whole steps (changing `q`) plus a within-bin escape for the remainder — so the granularity
  is chosen by need per coefficient, one mechanism at every rate, exactly as ruled.
* **`ESC_MAX = 512`** as ruled, with no fallback: an overflow is counted and reported.

| discriminator | result |
|---|---|
| build | `make all`, **0 warnings** |
| no escapes ≡ base | `OMC_SA7P` unset: stream byte-identical to the frozen base, dng 720p 12 frames (`cmp` rc 0) |
| a forced escape differs | armed: stream differs, `esc_bits` non-zero, `SA7P` lines show escapes |
| **rt = 0 with escapes live** | `omc_dec` output equals `--recon − 2048` **byte for byte**; `baseband-safe: yes` — verified on every armed run |
| exact CBR | armed streams exact at every rate |
| legality | `gamut: 0 committed samples outside legal range` on every run |
| `ESC_MAX` | **`escover = 0`** on both cells; largest list **274** escapes (spotrobotL), 63 (dng 720p) — the 512 cap is never approached |

**A real bug found and fixed on the way, and it is worth recording.** The first working version
pinned closure at **20 % for every K from 2 to 16** — more phases bought nothing. The cause: phase
1's demand is computed against the *current* picture and is therefore **incremental**, while phase
2 applied it as an *absolute* displacement from the lattice, discarding the previous phase's
escape. Fixed by carrying `cur − (dequant(q)+pred)` into the split. After the fix closure rises
with K, which is how the fixed point below can be trusted as a property of the rule rather than of
a defect.

## §10.2 (a) Completeness — it saturates, and well short of the bar

dng 720p @0.5, 4 frames, sweeping the phase cap:

| K | slices | closed | residual violating samples | escapes | max/slice |
|---|---|---|---|---|---|
| 2 | 137 | 48 (35 %) | 311 of 1,105 | 1,300 | 62 |
| 4 | 138 | 62 (45 %) | 192 of 1,209 | 1,608 | 63 |
| 8 | 136 | 62 (46 %) | 169 of 1,172 | 1,557 | 63 |
| 16 | 135 | 63 (47 %) | 150 of 1,166 | 1,570 | 63 |
| **32** | 135 | **63 (47 %)** | **150 of 1,166** | 1,570 | 63 |

**K = 16 and K = 32 are identical: the pass has a fixed point at 47 % of slices and 13 % of
violating samples.** Confirmed on a motion cell (spotrobotL @0.5, 4 frames, K = 8): **68 of 160
slices closed (42 %), 435 of 3,468 violating samples left (12.5 %)**, 274 escapes on the worst
slice, `escover = 0`. Deepest excursion: dng 720p 156 → **87** (the correction does reduce depth
where it works); spotrobotL 121 → 196 (the residue is deeper than what it started from).

**Against the bar (zero residue on every cell at every rate with ≤ 2 passes): MISS**, by 47 %
versus 100 % at ≤ 2 passes and by 12.5–13 % of samples at any K.

**Why it saturates.** `nocover = 0` throughout — every violating sample has a covering atom, and
now a fine enough move to use. What remains is **contention**: a sample's best atom is also the
best atom of a neighbour with the opposite demand. I added an **exclusive claim** (an atom serves
one sample per phase, the loser deferring to the next phase, still O(Ka·V)) and it moved closure
by one slice in 137. The limit is not granularity, not reach, and not phase count: it is that a
**direct, one-atom-per-sample assignment** cannot resolve a coupled system where each atom's
support carries several samples with conflicting demands. The shipped greedy resolves exactly that
— by re-ranking every candidate after every move, at 512 moves and 741 full-plane inverses per
slice (§1). **The gap between 47 % and 98 % is the search, and the search is what costs 1,274
traversals.**

## §10.3 (b) Bank — still a PASS, and now measured on emitted streams

Largest escape list: **274** coefficients (spotrobotL) → at `k = 7` and ~13-bit position deltas,
**≈ 5,500 bits**, i.e. **36 % of a 1080p @0.5 slice budget** against the normative **100 %**
allowance (`wire_cap = 2 × slice_bytes`), with the 608-bit floor never approached. `escover = 0`:
**no slice exceeded `ESC_MAX = 512`**, so the ruling's "a slice over the cap is a design failure"
never fired. The bank conclusion of §9.3 stands and is now confirmed against real streams.

## §10.4 (c) The owner's artifact bar — MISSED, and in the wrong direction

dng 720p @0.5, 12 frames, `darkblocks.py` (the owner's black-smudge class, 8×8 luma blocks darker
than source by > 20 and > 40 codes) and the level map of frame 8:

| | dark blocks f0 (>20 / >40) | dark, rest of run, mean (>20 / >40) | worst frame >40 | level-map block-mean range (Y, f8) | worst sample error |
|---|---|---|---|---|---|
| **frozen base** | 90 / **3** | 4.2 / **0.2** | 13 | **−24.1 … +22.0** | 301 |
| **within-bin pass** | 108 / **17** | 8.8 / **4.2** | **48** | −25.8 … +27.6 | 290 |

The bar was that these must be **absent** where the base had them. They are **worse**: the > 40
class rises 3 → 17 at frame 0 and 0.2 → 4.2 across the run, the block-mean range widens, and only
the worst single sample improves. The cause is structural and follows directly from §10.2: **55 %
of slices still fall through to the shipped repair**, whose shrink is what draws the smudges
(S3.23/S3.29), and the corrected slices add a footprint of their own on top. An engine that closes
under half its slices cannot remove an artifact that the fallback manufactures.

Renders for the eye: `renders/dng720_f8_q_{base,within-bin}_{lvl,absdiff}_{Y,Cb,Cr}.png`, frame 8,
steady state, every plane, control-point and slice grid marked.

## §10.5 Against the bar, and the verdict

| criterion | measured | verdict |
|---|---|---|
| zero residue, every cell, every rate, ≤ 2 passes | 47 % of slices closed at K = 32; 12.5–13 % of violating samples left | **MISS** |
| every slice inside `ESC_MAX` and the bank cap | `escover = 0`, max 274 of 512; ≤ 36 % of a 100 % allowance | **PASS** |
| level maps / dark blocks better than base | dark > 40: 3 → 17 (f0), 0.2 → 4.2 (run); range −24.1…+22.0 → −25.8…+27.6 | **MISS** |
| the lock | not chained: with 55 % of slices unclosed there is no arm worth chaining; **rt = 0 with escapes live is verified**, which is the lattice half | **not established** |
| oob / exact CBR / inertness | 0 out-of-range, exact CBR, byte-identical unarmed | hold |

**Verdict: NO-GO.** The syntax, the round trip and the bank all work; the **assignment rule** does
not. Per the loop I stopped here rather than running the remaining cells, rates, chains and NEG on
a mechanism that closes under half its slices.

## §10.6 What is now established, and the one question left

Three things are settled by construction and no longer need re-testing: **the escape can live in
the bitstream** (14 reserved header bits + a payload prefix, CRC and bank bounds unchanged);
**both ends reproduce it** (`rt = 0`, `baseband-safe: yes`); and **the bank can pay for it**
(`escover = 0`, ≤ 36 % of a 100 % allowance). The granularity question is closed too: with `k = 7`
the pass owns a move as small as one code and still saturates.

What is left is a single, sharply-posed question: **what assignment rule resolves the contention?**
The two ends of the range are now both measured on the same cells — a direct one-atom-per-sample
assignment reaches **47 %** at O(Ka·V) per phase, and a full greedy with re-ranking reaches
**92–99 %** at 1,274 traversals. Everything this engine needs sits between them, and nothing else
in the design is now in doubt.

## §10.7 Provenance

Unchanged from §7.10 and §9.7 for every carried-over element. New in this iteration: the escape
**syntax** (own work: a length field in bits already reserved, a flat ascending position list with
length-prefixed binary deltas, a `k`-bit value; no embedded ordering, no truncation semantics, no
layer) and the **exclusive-claim** rule in phase 1 (own work; it is a "taken" flag). Nothing is
lifted from a named standard. Left out, as before: any embedded/truncatable ordering of the escape
list, any per-block or per-region step syntax, any quantisation-weight table.

## §10.8 Adversarial check

1. **"The fixed point is your bug, not the rule."** One bug was found and fixed (incremental vs
   absolute demand, §10.1) and it moved the fixed point from 20 % to 47 % and made K matter. The
   remaining saturation is flat from K = 16 to K = 32 on one cell and reproduces on a second, and
   `nocover = 0` rules out reach. I cannot prove no third bug exists; I can say the two obvious
   ones are gone and the result reproduces across cells and phase counts.
2. **"`k = 7` may not be optimal."** k was raised from 3 to 7 after k = 3 was measured to round
   real demands to zero at `s = 7`. k = 7 gives a one-code move at `s = 7`. Finer is not available
   in a 3-bit field and would not help: the residue is contention, not granularity.
3. **"You did not run the full battery."** Correct, and deliberate: the primary criterion is missed
   by 2× on two cells with the phase count saturated. The loop forbids extending a step-1
   measurement that missed its bar.
4. **"rt = 0 could be trivially true if the escapes were empty."** They are not: `esc_bits > 0`,
   1,300–4,773 escapes per run, and the unarmed stream is byte-identical to the base while the
   armed one is not.
5. **Sandbox.** `.work/v537` untouched (0 files). `tree/` unmodified. Probes in `ptree`, `ptree2`,
   `ptree3`. Exit codes checked; processes identified by `/proc/<pid>/cwd`; no `pkill`.

## §10.9 Open questions

1. The only open question is the assignment rule (§10.6) — do you want an iteration on it, bounded
   by the same fixed-work budget, or is 1,274 traversals now worth re-costing against a cheaper
   verification rather than a cheaper search?
2. A middle form exists and is cheap to try: re-rank **only the atoms whose support contains a
   still-violating sample**, which is O(V·Ka) per move rather than O(all coefficients) — the
   shipped greedy's cost is the full re-scan, not the re-ranking idea itself.
