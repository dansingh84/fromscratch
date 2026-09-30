## §9.10 Adversarial check on L-I21

1. **"Your phase-1 rule is naive — a better assignment would close more."** Partly, and the
   measurement bounds how much. `nocover = 0` says the reach is there; `left1 > bad0` on the 0.5 bpp
   motion cells says the *first* sweep already loses ground. A cleverer assignment can reduce the
   overshoot it causes but cannot create a move smaller than one quantiser step, and the deficit is
   5–18×. The shipped greedy is the empirical upper bound on what whole steps can do — 92–99 % —
   and it pays 512 moves and 741 full-plane inverses per slice for it. So the honest statement is:
   whole steps can be complete **or** cheap, and this iteration measured the cheap end.
2. **"`|n| ≥ 1` when the rounding gives zero is your choice."** It is, and it is forced: with
   `round(need/step) = 0` the alternatives are to leave the sample illegal or to move a full step.
   Both are measured — the forced move is what produces `left1 > bad0`, and not forcing it would
   simply move those samples from "overshot" to "still out". I did not run the no-force arm; it
   would lower the quality cost and raise the residue, and neither direction reaches the bar.
3. **"The escape bits are estimated, not coded."** Yes — positions as sorted Elias-gamma deltas
   plus `k = 2` value bits, the same estimator as §7.3. It would have to be wrong by **2.8×** on
   cf_gfx @0.5 (the worst cell) before the bank cap bound, and by 5× on the others. The bank
   conclusion is robust to the estimator; the residue-count conclusion does not depend on it at all.
4. **"K = 2 might not be the right cap."** Measured both: `left1` and `left2` are in the table, and
   at 0.5 bpp on the motion cells **K = 1 is better than K = 2** (spotrobotL 8,082 vs 8,696). The
   completeness figure is 25–45 % at 0.5 bpp either way.
5. **"Is the pass really emitting what you rendered?"** Yes: the armed arm writes whole-step lattice
   points into `e->coef`/`e->dcoef`, the stream is exact-CBR at the same byte count as the base, and
   `recon − 2048` is byte-identical to the decoder output (verified over 3.69 M samples). This is
   the first arm in the whole session that could be measured as a real stream with **no syntax
   change at all**, and that is a property of whole steps, not of my probe.
6. **"The lock was not chained."** Correct. The whole-step half needs no lock work — it emits
   ordinary lattice points at the signalled plan, which is the shipped situation — and the escape
   half is designed in §9.4 but not built, so there is nothing new to chain. The base control chain
   from §8.6 (locks at g2/g3 through g8) is the relevant control and it is unchanged by this arm.
7. **"Flatness was not measured."** Not asked for in L-I21's list; the eye evidence is the level
   maps of §9.6, and they are worse on spotrobotL — enough to fail on its own.
8. **Sandbox / hygiene.** `.work/v537` untouched. `tree/` unmodified. Probes in `ptree3/` (this
   iteration), `ptree/`, `ptree2/`. Every exit code checked; `notes/p3_bat.sh` runs `set -u` and
   aborts non-zero. Processes identified by `/proc/<pid>/cwd`; no `pkill`/`killall`. All `.yuv`
   deleted after measurement.

**Adversarial check done on the exact files I deliver.** `ptree3/src/latt_probe.inc`,
`diffs/sa7_2ph.diff`; md5s appended to `out/manifest.md5`.

## §9.11 Open questions for the coordinator, one sentence each

1. The numbers point at one experiment nobody has run — **the two-phase pass using within-bin
   granularity from its first move, bank-funded, on the slices that need correction at all** — do
   you want that as L-I22, with the bar being the same completeness bar this iteration missed?
2. If so, should the escape's step `k` be fixed (k = 2 was best in L-I19) or chosen per slice from
   the census, given the bank has 3–10× more headroom than the worst measured draw?
3. `ESC_MAX` is the one new normative constant the lock trial needs to bound its work — the worst
   measured residue slice wants **311** escaped coefficients; do you want that sized from the p99
   (161) with the rest falling back to the shipped repair, or from the max?
4. Whole steps at 1.0 bpp already close 81–92 % of slices with quality within 0.1 dB on every plane
   — is a rate-dependent design (whole steps above ~0.75 bpp, within-bin below) acceptable, or must
   one mechanism serve every rate?
