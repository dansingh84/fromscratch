## §7.7 Adversarial check on L-I19

1. **"Your `%resid` is your solver's failure, not the mechanism's."** Accepted, and stated in §7.3:
   k = 2/3 beats k = 4, which a correct solver could never do, so the residue is an **upper bound**.
   The direction of the error favours the escape, and the bar is still missed by 6–21× on two
   cells, so the verdict does not turn on it. What would change the verdict is a solver that takes
   spotrobotL from 2.11 % to ≤ 0.1 % — a 21× improvement from a greedy that is already sized-ladder
   rather than single-grain. I do not believe it, but I have not proved it impossible.
2. **"The probe could have perturbed what it measured."** It cannot: the armed run's stream is
   byte-identical to the frozen base on both cells (D2). That is a stronger control than the r-sweep
   of §3 had, and it was built after noticing that an emitting probe would drift.
3. **"`esc=0` with `moves>0` in the first version."** A real bug, caught by its own impossibility,
   not by a gate: the accept path had been patched into `latt_probe_run` instead of
   `latt_plane_solve` because the same source line occurs in both functions. Every number in §7.3
   is from the fixed binary (`ptree/omc_enc` md5 `f199a18f56889f02bef134b32514a430`).
4. **"The bit cost is an estimate, not a coded size."** True — there is no escape syntax, so the
   bits are computed as `Σ (log2(N_coef/n_esc) + 2 + k)`. I report the flat-16-bit-position
   alternative beside it (8.7–58.3 % worst slice); both miss the 10 % bar on four of five cells, so
   the coding scheme is not what decides it. An entropy-coded position list would have to beat the
   sorted-delta estimate by 2–3.5× to change the verdict.
5. **"Is the residue real, or an artifact of the wash guard?"** The guard was on in every arm (it is
   a quality requirement, not a tuning knob). Turning it off would lower the residue and raise the
   smudge risk; I did not run that arm, and that is a gap. It is the one measurement that could move
   `%resid` materially without a better solver.
6. **"(d) is not answered."** Correct and stated: no syntax, no decodable stream, no PSNR. What I
   report instead is the measured perturbation (pmax 104–507 codes; guard firing on 42–274 slices
   per cell), which is evidence *against* the escape being gentle, not evidence for it.
7. **The lock.** I did not take the argument on trust; I read `omc_quant1b_dz`, `omc_dequant1`,
   `verify_candidate`, the deadzone constants, the fill path and the `elig` kill, and the answer is
   that it fails at `verify_candidate` and needs three bin corrections besides. Both are stated with
   file and line so a fresh reviewer can check them in minutes.
8. **Scope.** 1.0 bpp was not run — the loop forbids extending a measurement that missed its step-1
   bar. 8/12-bit, 4:4:4, limited range and the cut probe were not run for the same reason.
9. **Sandbox.** `find .work/v537 -newermt '2026-09-13 19:00' -type f` → **0 files**. SA1's trees were
   copied, never edited. `tree/` is still an unmodified rsync. No `pkill`/`killall` at any point;
   background jobs were my own and were waited on by condition, not by pattern-matching processes.

**Adversarial check done on the exact files I deliver.** `ptree/src/latt_probe.inc` md5
`c2ce8397672aead90cd8117d2cd1fcef`, `ptree/omc_enc` `f199a18f56889f02bef134b32514a430`, diff
`diffs/sa7_esc.diff` (242 lines). Frozen base `out/basebin/omc_enc`
`6b5b67aa8a45eb7cf13157d2fc23427a`. All `.yuv` deleted.

## §7.8 Open questions for the coordinator, one sentence each

1. The escape's residue is 0.00 % on three cells and 0.64–2.11 % on the two hard motion cells, and
   those residues are exactly the coefficients whose demand is pinned at the bin edge (8–25 % of
   escapes) — do you want the field to carry the whole job, or the field plus a much smaller escape
   for the last fraction, given they compose cleanly (§7.z)?
2. Should I run the guard-off arm (§7.7.5) before closing the escape, since it is the one cheap
   measurement that could move `%resid` without a better solver?
3. The field's control-point choice is a new encoder decision with no precedent in this codec — do
   you want its oracle to derive the control points from an edge/rail detector, or from the
   measured escape demand itself (which I can already dump per slice and which is, by construction,
   the ideal field)?
4. `verify_candidate` would need extending for the escape but **not** for the field (§7.z) — is
   that enough on its own to make the field the primary and drop the escape from the build?
