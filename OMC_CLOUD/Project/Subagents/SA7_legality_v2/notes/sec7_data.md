## §7.2 The probe, and the discriminators

`ptree/` = a copy of `otree/` with one env-gated addition, `[SA7-ESC]`, in
`src/latt_probe.inc` (`diffs/sa7_esc.diff`). Under `OMC_SA7_K=k` it runs a **measurement solve**
on each violating slice *before* the shipped constructive step, on the same pass-0 state, with:

* candidate moves at granularity `2^(s−k)` instead of one whole quantiser step;
* every coefficient's cumulative displacement held inside **its own bin**, with the window derived
  from `(q, s, deadzone)` per §7.1(1)-(2) (`sa7_window()`), and the base index `q` never changed;
* positions where the grain fill would fire (`q == 0` in a fill band) refused;
* a **sized ladder** of candidate displacements (1, 2, 4, … grains in each direction, clamped to
  the bin and to `k` bits) rather than one grain at a time — this is the two-phase
  "accumulate the demand" rule of DESIGN §2 Stage E expressed as a candidate set;
* the existing wash guard (`latt_blockshift` form 4) on;
* every accepted move verified by the real inverse, as the shipped step does.

It then **writes nothing** and returns, so the shipped path runs unchanged.

| discriminator | result |
|---|---|
| D0 build | `make all`, **0 warnings**, 7 test binaries present |
| D1 inert, probe unset | stream byte-identical to the frozen base on dng 720p and spotrobotL, 12 frames (`cmp` rc 0) |
| D2 inert, probe **armed** | `OMC_SA7_K=4` stream byte-identical to the frozen base on both cells (`cmp` rc 0) — the probe measures the true base trajectory and cannot perturb it |
| D3 non-vacuous | 401 / 334 SA7 lines emitted, escapes > 0, closures > 0 |
| D4 the probe found a real bug in itself first | the first version reported `esc=0` with `moves>0`: the accept path had been patched into `latt_probe_run` instead of `latt_plane_solve` (the same source line occurs in both). Caught because "moves happened but nothing was escaped" is impossible. Fixed, re-verified |
| exit codes | every run checked; all rc 0 |

## §7.3 (a)(b)(c) The sweep — five cells, 12 frames, 0.5 bpp, k = 1…4

`left` = violating samples still outside the legal window after escapes only, i.e. **the residue
that needs the base index to change**. `%resid` is the GO/NO-GO quantity for (a).

| cell | k | slices | closed | bad0 | left | **%resid** | escapes/slice p50/p90/p99/max | moves/slice p50/p90/p99/max | **worst-slice escape bits, % of budget** | mean % | pmax (codes) | slices where the wash guard fired |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **spotrobotL** | 1 | 401 | 261 | 7722 | 901 | 11.67 | 15/73/165/191 | 15/74/165/193 | 14.1 | 2.45 | 178 | 212 |
| | 2 | 401 | 360 | 7722 | 163 | **2.11** | 14/70/194/250 | 18/90/249/341 | **19.4** | 2.72 | 106 | 143 |
| | 3 | 401 | 360 | 7722 | 163 | **2.11** | 12/62/175/230 | 20/119/342/451 | 19.6 | 2.62 | 106 | 81 |
| | 4 | 401 | 340 | 7722 | 410 | 5.31 | 12/65/186/242 | 25/157/411/590 | 22.0 | 2.77 | 104 | 42 |
| **volleyballgameL** | 1 | 313 | 180 | 6357 | 581 | 9.14 | 31/107/223/267 | 31/107/231/283 | 18.9 | 3.82 | 248 | 161 |
| | 2 | 313 | 292 | 6357 | 48 | 0.76 | 27/91/247/311 | 32/117/314/444 | 23.5 | 3.68 | 119 | 83 |
| | 3 | 313 | 289 | 6357 | 41 | **0.64** | 22/77/210/261 | 39/146/372/508 | 21.9 | 3.31 | 119 | 45 |
| | 4 | 313 | 262 | 6357 | 175 | 2.75 | 22/73/217/263 | 54/217/478/660 | 23.8 | 3.45 | 120 | 32 |
| **cf_gfx** | 1 | 249 | 215 | 934 | 54 | 5.78 | 7/21/40/56 | 7/22/42/58 | 31.3 | 6.26 | 507 | 216 |
| | 2 | 249 | 249 | 934 | 0 | **0.00** | 8/23/38/58 | 10/29/49/79 | **35.4** | 7.89 | 275 | 193 |
| | 3 | 249 | 249 | 934 | 0 | **0.00** | 7/19/36/53 | 15/44/85/136 | 35.7 | 7.24 | 233 | 181 |
| | 4 | 249 | 249 | 934 | 0 | **0.00** | 6/18/33/40 | 21/63/136/149 | 30.1 | 7.31 | 236 | 171 |
| **dng 1080p** | 1 | 270 | 267 | 1320 | 3 | 0.23 | 6/27/48/79 | 6/27/48/79 | **6.5** | 1.02 | 169 | 146 |
| | 2 | 270 | 270 | 1320 | 0 | **0.00** | 7/38/64/109 | 9/43/78/135 | 9.3 | 1.40 | 169 | 116 |
| | 3 | 270 | 270 | 1320 | 0 | **0.00** | 6/35/52/91 | 12/63/104/164 | **8.5** | 1.34 | 163 | 96 |
| | 4 | 270 | 270 | 1320 | 0 | **0.00** | 6/32/56/87 | 14/69/137/179 | 8.8 | 1.36 | 163 | 46 |
| **dng 720p** | 1 | 334 | 302 | 2461 | 55 | 2.23 | 9/48/76/105 | 9/49/83/111 | 21.8 | 4.25 | 304 | 274 |
| | 2 | 334 | 334 | 2461 | 0 | **0.00** | 10/72/112/135 | 13/90/139/175 | 29.7 | 6.25 | 166 | 232 |
| | 3 | 334 | 334 | 2461 | 0 | **0.00** | 8/56/91/123 | 17/112/206/253 | 29.7 | 5.59 | 163 | 209 |
| | 4 | 334 | 334 | 2461 | 0 | **0.00** | 7/56/91/123 | 21/115/275/329 | 29.6 | 5.55 | 164 | 192 |

Bit cost is `Σ over escapes of (log2(N_coef/n_esc) + 2 + k)` — sorted positions with Elias-gamma
deltas — against the slice's own bit budget (5,120 bits at 720p @0.5, 15,360 at 1080p, 1,792 on
cf_gfx). A flat 16-bit position index instead gives 8.7–58.3 % worst-slice, so the position coding
is not what decides it.

**k = 2 or 3 is the optimum on every cell; k = 4 is worse.** That is not a property of the escape,
it is my solver: with a finer grain the sized ladder offers more candidates whose first step the
lifting rounding swallows, and the shipped accept/undo rule then forbids that position for good.
So **`%resid` is an upper bound on what a within-bin mechanism cannot reach, not a proven floor** —
a better solver would clear more. It is reported as measured, with that caveat attached.

## §7.4 Against the bar

> **GO** = at some k ≤ 4: residue needing beyond-bin moves ≤ **0.1 %** of violating samples on
> **every** cell, worst-slice escape bits ≤ **10 %** of the budget, moves within the bar
> (max ≤ 32, p99 ≤ 8), no plane worse by 0.1 dB, and the lock argument holds in the code.

| criterion | best achieved | bar | verdict |
|---|---|---|---|
| residue, **every** cell | cf_gfx / dng1080 / dng720 **0.00 %**; volleyballgameL **0.64 %**; **spotrobotL 2.11 %** | ≤ 0.1 % | **MISS** (21× on spotrobotL, 6× on volleyballgameL) |
| worst-slice escape bits | dng1080 **6.5 %** (k=1) / 8.5 % (k=3); every other cell **19–36 %** | ≤ 10 % | **MISS on 4 of 5 cells** |
| escapes per slice (the (c) count) | p99 33–247, max 40–311 | max ≤ 32, p99 ≤ 8 | **MISS** (3–10×) |
| per-plane dB at equal CBR net of escape bits | **not measurable without the syntax** — the probe emits nothing, so there is no decodable stream to score. What *is* measured is the perturbation the escape puts into the committed picture: **pmax 104–507 codes**, and the wash guard fires on **42–274 slices per cell** | ≤ 0.1 dB | **NOT MET / not established** |
| the lock in the code | holds **only** with the `verify_candidate` extension of §7.1 and the three bin corrections | holds as specified | **MISS as specified; fixable** |

**Verdict: NO-GO.** Four of five criteria missed; the fifth not establishable at this step. Nothing
is built. The 1.0 bpp arm was not run: the loop forbids extending a step-1 measurement that has
already missed its bar.

**What the numbers nonetheless establish, and it is the useful part.** A within-bin escape at
k = 2–3 clears **97.9 %** of violating samples on the worst cell and **100 %** on three of five,
with the base index untouched — so the mechanism is real and the lock question is answerable. What
it cannot do is (i) reach the last 0.6–2.1 % on the two hard motion cells, because those
corrections want to leave the bin, and (ii) pay for itself: its cost is **per escaped coefficient
and spikes exactly on the hard slices** (2.4–7.9 % of the budget on average, 19–36 % on the worst
slice), which is the wrong cost shape for a fixed-CBR codec.

## §7.5 (d) The picture perturbation, and the eye

The within-bin move changes one coefficient's reconstruction by at most **`s/2`** — half a
quantiser step, by construction, which at the measured level-1 shifts of 5–9 is 16–256 code units
and at the coarse shifts more. Per sample the perturbations add over overlapping supports, and
that is what the probe measured directly (`perturb`, `pmax`): **max |committed − base| of 104–507
codes** per slice. So "within the bin" bounds the *coefficient*, not the *picture*, and the escape
is not intrinsically gentle. The wash guard (block-mean shift beyond what the fix required) fired
on **42–274 slices per cell** — between 10 % and 82 % of the slices the engine touched — which is
the smudge class asking to be let in.

Renders, frame 8, steady state, **with the control-point grid marked** (owner ruling: no harness
verdict on steps is trusted). `notes/gridmap.py` draws, per plane, the level map (block mean of
decode − source, blocks `sh/4 × 32`, ±20 codes) and the `|decode − source|` map (0–40 codes), each
with green lines at every 64 luma columns (the proposed control-point pitch) and at every slice
boundary:

* `renders/spot_f8_grid_{lvl,absdiff}_{Y,Cb,Cr}.png`
* `renders/dng720_f8_grid_{lvl,absdiff}_{Y,Cb,Cr}.png`
* plus the earlier pair `renders/{spot,dng720}_f8_r{0,1}_{Y,Cb,Cr}.png` from §3.6.

**What I see in them.** In `spot_f8_grid_absdiff_Y.png` the error is entirely **content-following**
— it traces the railings, stair treads, panel edges and the floor texture — and shows **no
alignment whatever with the 64-column grid or the 16-row slice grid**. The only structure that
tracks the codec rather than the picture is the faint horizontal banding at slice pitch in the
floor, already known. Same on the 720p cell. So the baseline the field would be added to has no
grid-phase artifact to be confused with, and a step at control-point phase would be immediately
visible against it. Per plane statistics are printed by the tool (`|e|` mean 6.05 / p99 28 /
max 190 on spotrobotL Y; 11.65 / 64 / 301 on dng 720p Y).

**Escape clustering vs the grid (owner ruling 2).** The escape column histogram (32 buckets across
the plane, §7.z) shows strong **content** clustering — max/min ratio 202–1181, with 5–7 buckets
carrying exactly zero — and **no periodicity at any grid pitch**: the dng cells give a single smooth
hump (buckets 0–7 exactly zero, peak at bucket 16), spotrobotL and volleyballgameL give several
broad humps. Nothing repeats at 64 columns, at 32 columns, or at any sub-multiple. So the escape
does not cluster into a precision boundary; it clusters onto edges.
