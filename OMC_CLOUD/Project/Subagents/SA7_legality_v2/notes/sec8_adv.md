## §8.9 Adversarial check on L-I20

1. **"Your detector is bad, not the mechanism."** The strongest answer available is **arm A**: the
   *ideal* field, derived from the slice's own committed violations after a first reconstruction —
   it knows exactly where the illegality is, which no shippable detector can. Arm A is the **worst**
   arm on every cell. A mechanism whose oracle arm is worse than doing nothing is not failing for
   want of a detector.
2. **"You picked `g` to make it fail."** `g` was swept (§8.2) and the trend is monotone: more field,
   worse legality, on both detector arms. `g = 2` is the lightest setting that moves more than one
   control point in 32. `g = 1` — one point up and one down out of 32 — is the only setting that
   ever improved anything, by 5 % on one cell, which is not a mechanism.
3. **"Mean-zero was your choice."** It was, and it is forced: a field with mean **+0.92** was my
   first version and the ladder took it straight back through `Q` (spotrobotL 738 passes vs a base
   of 377), which is S5.188 reproduced. A field that is *not* mean-zero is the whole-band rung that
   L-I18/S5.188 already falsified. So the two options are "clawed back" and "redistributed", and
   both are measured here.
4. **"The syntax charge is punitive on small pictures."** It is 4.52 % on cf_gfx and 3.87 % at 720p
   against 1.88 % at 1080p, and I report it per cell rather than quoting the 1080p figure. But the
   cf_gfx field is identically zero (§8.2), so cf_gfx's numbers are purely the rate charge and are
   labelled as such, not counted as evidence against the field.
5. **"`--recon` is not the decode."** Verified this session over 3.69 M samples: `recon − 2048` is
   byte-identical to `omc_dec`'s output, single constant. Every picture number is from `--recon`,
   and the arm-4 round trip re-verifies it with the field live.
6. **"The chain does not test the real mechanism."** Correct, and stated in §8.5: arm 4 isolates
   the lattice property from field recovery, because field recovery is a build I did not make. The
   chain result is reported for exactly what it is.
7. **"@1.0 bpp was not run."** Per the loop: a step-1 measurement that misses its bar is not
   extended. Nor were 8/12-bit, 4:4:4, limited range, the cut probe or `make test` — all of those
   are step-3 work on a build that is not authorised.
8. **Sandbox.** `.work/v537` untouched (`find … -newermt` → 0 files). `tree/` still an unmodified
   rsync. `ptree/` and `ptree2/` are mine; `otree/` is a copy of SA1's tree3, never edited. No
   `pkill`/`killall`; background jobs were my own and waited on by condition.
9. **Every exit code checked**; `notes/field_bat.sh` and `notes/chain8.sh` run `set -u` and abort
   non-zero on any failure, so no arm could silently become a number.

**Adversarial check done on the exact files I deliver.** `ptree/src/sa7_field.inc`, the three hooks
in `ptree/src/codec.c`, diff `diffs/sa7_field.diff`; md5s in `out/manifest.md5`.

## §8.10 Open questions for the coordinator, one sentence each

1. Arm A — the field that *knows* where the violations are — is the worst arm on every cell, which
   says the spatial redistribution of a fixed precision budget cannot buy legality at all: do you
   want that treated as closing the rate-allocation family for **legality**, leaving the field to be
   judged only as a flatness/texture mechanism (blocker 4)?
2. The 64-column pitch degenerates on narrow pictures (`ncp = 9` on cf_gfx → an identically zero
   field): should a re-run use a pitch that guarantees `ncp ≥ 24` on every supported width?
3. Every mechanism that redistributes or refines *within the slice's existing bit budget* has now
   failed on legality (plan rung, escape, field, and arm A's oracle) while the only thing that ever
   worked is the in-lattice correction pass — is the next question therefore not "where do the bits
   go" but "how cheap can the correction pass be made", where I already measure 1,274 → < 3
   traversals?
4. The field's *cycle* cost is negligible and its lock is recoverable constructively (§8.5, §8.7) —
   if it is to be pursued for flatness rather than legality, do you want the same probe re-pointed
   at a texture bar with the energy meter and the eye, rather than at violations?
