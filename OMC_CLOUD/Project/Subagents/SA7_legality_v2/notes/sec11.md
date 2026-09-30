# §11. Loop iteration 6 — the ASSIGNMENT RULE (L-I23), step 1 — arm R measured, arm J not built

## §11.1 Arm R — the local re-ranking greedy at within-bin granularity, emitting escapes

Built in `ptree3` (`[SA7-R]`, `diffs/sa7_r.diff`). Candidates are restricted to atoms whose support
covers a **still-violating** sample (the shipped `bad`/`mark` rule), the displacement ladder is the
within-bin sized ladder of L-I19, the base index is **frozen** so the whole correction rides in the
escape list, every accepted move is verified by the exact inverse, `ESC_MAX = 512` with **no
fallback** (an overflow abandons the slice and is counted).

| discriminator | result |
|---|---|
| unarmed ≡ base | stream byte-identical to the frozen base, dng 720p 12 frames (`cmp` rc 0) |
| a forced escape differs | armed stream differs; `esc_bits > 0` |
| **rt = 0 with escapes live** | `omc_dec` output = `--recon − 2048` byte for byte on every armed run |
| legality | `gamut: 0 committed samples outside legal range`, every run |
| exact CBR | exact at every rate |
| `ESC_MAX` | **`over = 0` everywhere**; largest list **156** (spotrobotL), **133** (dng 720p) of 512 |

**Closure, by granularity `k`** (4 frames unless stated):

| cell | k = 2 | k = 3 | k = 4 | k = 5 | k = 7 |
|---|---|---|---|---|---|
| dng 720p @0.5 | — | — | **131/131 = 100 %** | — | 49/136 = 36 % |
| dng 720p @0.5, **12 frames, k = 4** | | | **326/326 = 100 %** | | |
| spotrobotL @0.5 | **140/158 = 89 %** | 139/156 = 89 % | 129/159 = 81 % | 85/159 = 53 % | — |

**dng 720p closes completely.** spotrobotL saturates at **89 %**, and two controls say why it is not
a tuning question:

* **not the move cap** — raising `LATT_MAXMV` from 1,024 to 4,096 changes nothing (140/158 either
  way; the worst slice uses 220 moves at k = 2);
* **not the wash guard** — `OMC_GM_LATT_LVL = 0` (guard off) changes nothing (140/158 either way).

What stops it is the greedy itself: on the residual slices **no single within-bin move of any
covering atom has a positive predicted gain**, so the search exhausts its candidate set. That is
precisely the contention case arm J exists to solve — a combination of displacements helps where no
single one does.

## §11.2 The footprint — measured on the cell where closure is 100 %, and it is NOT zero

This is the measurement the owner's amendment asked for, and dng 720p @0.5 answers it cleanly
because **every violating slice is closed by the pass there**, so nothing can be blamed on
fall-through:

| dng 720p @0.5, 12 frames | dark blocks f0 (>20 / >40) | dark, rest of run, mean (>20 / >40) | worst >40 | mean PSNR Y |
|---|---|---|---|---|
| frozen base | 90 / **3** | 4.2 / **0.2** | 13 | 34.788 |
| **arm R (100 % closed)** | 131 / **4** | 12.5 / **3.7** | **40** | ≈ 34.0 |

**The engine's own footprint is not zero.** With the shipped repair's shrink removed from every
violating slice, the black-smudge class still rises (>40 rest-mean 0.2 → 3.7) and luma falls ~0.8 dB.
6,015 escapes over 326 slice-instances is ~18 per slice, each displacing its atom by up to half a
step across a 27–45-sample support; that is a real picture change, and it is what the numbers show.
So the answer to the owner's question is: **the correction footprint is a first-order effect, not a
rounding artifact**, and a correction engine that closes everything still does not, by itself, make
the level maps better than the base.

Renders: `renders/dng720_f8_q_{base,within-bin}_{lvl,absdiff}_{Y,Cb,Cr}.png` and the L-I22 pair,
frame 8, steady state, every plane, grid-marked.

## §11.3 Arm J — not built, and what the arm-R controls now tell us about it

I did not build the per-cluster joint solve. Two honest reasons: the session had already run
through five full build-and-measure iterations, and arm R's controls (§11.1) had to come first
because they are what makes arm J's case — without them "the greedy stalls" could still have been
the move cap or the guard. They are not.

What arm R establishes for the design of arm J:

* the clusters are small — the residual slices carry a **handful** of samples each (spotrobotL:
  18 slices of 158, ~12.5 % of violating samples across the run at L-I22's finer measurement), and
  every one of them has covering atoms (`nocover = 0` throughout this session);
* the solve is therefore a few samples × a few atoms, which is the regime where an integer
  normal-equation form in fixed point, or a bounded coordinate sweep over the exact local kernel,
  is affordable — but **the cost question the coordinator posed is exactly the open one**, and I
  have not measured it;
* `ESC_MAX = 512` is comfortable (max 156 used) and the bank draw is well inside the 2× cap, so
  arm J inherits both PASSes unchanged.

## §11.4 Against the bar

| criterion | measured | verdict |
|---|---|---|
| closure 100 % on **both** cells with a fixed phase count | dng 720p **100 %**; spotrobotL **89 %** | **MISS** |
| `escover = 0` | 0 on both cells, max 156 of 512 | **PASS** |
| bank within cap | worst draw well inside the 2× allowance | **PASS** |
| **the pass's own footprint zero** | dark > 40 rest-mean **0.2 → 3.7**; luma ≈ **−0.8 dB** on the 100 %-closure cell | **MISS** |
| cycles inside the period | not costed for arm J; arm R's probe uses a full-plane inverse per accepted move (50,283 inverses over 326 slices ≈ 154 each) — the production form's local inverse is §9.5's arithmetic, but the **move count** (up to 220 per slice) is now the cost driver, not the inverse | **not established** |
| rt = 0 with escapes live / oob / exact CBR / inertness | all hold | **PASS** |

**Verdict: NO-GO.** Arm R clears closure on one cell of two and fails the footprint bar on the cell
where it clears. Arm J is unbuilt and is now the only untested branch.

## §11.5 The position, stated plainly

Six iterations have narrowed this to two facts that sit against each other:

1. **The mechanism is sound and complete enough to ship, mechanically**: escapes live in the
   bitstream, both ends reproduce them (`rt = 0`), the bank pays, `ESC_MAX` is never approached,
   legality reaches 0 out-of-range, and on dng 720p the pass closes **every** violating slice
   without the shipped repair touching a violation.
2. **Correcting a picture costs picture.** On the cell where the correction does everything, the
   black-smudge class still doubles and luma still falls 0.8 dB. The shipped repair's shrink was
   one way of paying that cost; a within-bin escape is a gentler way; neither is free.

So the question the next iteration should answer is not "can the correction be made complete"
(nearly, and arm J is the remaining lever) but **"can a correction of this size be made invisible"**
— and the measured answer so far is that ~18 escapes per slice, each half a step over a 27–45-sample
support, is not. That may mean the correction has to be spread over more, smaller moves (more
escapes, finer `k`, more bits — the bank has room), or it may mean the residual belongs somewhere
other than the detail coefficients. I have not measured either.

## §11.6 Provenance and hygiene

New elements this iteration: none beyond arm R's candidate restriction (own work; it is the shipped
`bad`/`mark` rule applied to a within-bin ladder) and the escape syntax already provenance-stated in
§10.7. `.work/v537` untouched (0 files changed this session). `tree/` unmodified. Probes in
`ptree`, `ptree2`, `ptree3`; SA1's trees copied, never edited. Every exit code checked; processes
identified by `/proc/<pid>/cwd`; no `pkill`. All `.yuv` deleted. md5s in `out/manifest.md5`.
