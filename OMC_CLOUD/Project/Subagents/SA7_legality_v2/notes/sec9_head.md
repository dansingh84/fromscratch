# §9. Loop iteration 4 — the TWO-PHASE WHOLE-STEP PASS and a BANK-FUNDED RESIDUE (L-I21), step 1

**The idea (coordinator).** Make the in-lattice correction pass as complete as it is cheap, and pay
for whatever it cannot close **across slices, from the causal bank**, not from the slice's own
bands.

## §9.1 What I built, and why it can be emitted with no syntax at all

Probe `[SA7-2PH]`, `ptree3/src/latt_probe.inc` (`diffs/sa7_2ph.diff`), armed by `OMC_SA7P=1`,
byte-inert unset. It replaces the shipped greedy coordinate descent at the same call site with the
DESIGN §2 Stage-E pass:

* **phase 1** — one sweep over the violating samples. For each, the covering **level-1 and level-2**
  coefficients are found by index arithmetic from `GM_BASIS`, the one with the largest exact
  synthesis response `g` at that sample is taken (`latt_bas`, the impulse response of this codec's
  own inverse, Q12), and the number of **whole** quantiser steps that would move the sample inside
  is recorded: `n = round(need·2^12 / (2^s · g))`, with `|n| ≥ 1` when the rounding gives zero
  (there is no smaller move available to a whole-step pass). Demands accumulate on the shared atom
  by largest magnitude with sign agreement; sign conflicts are counted.
* **phase 2** — apply the accumulated demands, reconstruct exactly, re-census. The wash guard
  (`latt_blockshift` form 4) is a **hard limit**: a guard failure halves every demand once and
  re-reconstructs. Positions where the grain fill would fire (`q == 0` in a fill band) are excluded.
* at most **K = 2** phase pairs (`OMC_SA7P_K`).

**It needs no new syntax.** Every move is a whole quantiser step at the **signalled** plan, so the
result is an ordinary lattice point: when the pass closes a slice the probe writes the corrected
coefficients into `e->coef`/`e->dcoef` and the slice is **emitted**. That is why every number below
is a real encode of a real stream rather than an offline estimate, and why exact CBR can be checked
directly.

| discriminator | result |
|---|---|
| build | `make all`, **0 warnings** |
| **a pass with no violations ≡ base** | `OMC_SA7P` unset: stream byte-identical to the frozen base on dng 720p, 12 frames (`cmp` rc 0) |
| **a forced move differs** | armed: the stream differs, and `SA7P` lines show moves applied |
| **exact CBR** | armed stream is byte-for-byte the same **size** as the base at every rate: e.g. spotrobotL @0.5 1,566,752 B = `32 + 1920×68×12` |
| legality | `gamut: 0 committed samples outside legal range` on every armed run (the shipped repair still cleans up what the pass leaves) |
| determinism | the assignment is a fixed sweep order with deterministic tie-breaks; 3 repeats byte-identical |
| exit codes | every run checked; `notes/p3_bat.sh` runs `set -u` and aborts non-zero |
