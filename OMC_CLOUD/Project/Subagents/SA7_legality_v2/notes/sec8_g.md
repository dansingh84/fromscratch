## §8.2 Discriminators, and the strength sweep that set `g`

| discriminator | result |
|---|---|
| **all offsets 0 ≡ frozen base, byte for byte** | `OMC_SA7F` unset: stream byte-identical to `out/basebin/omc_enc` on dng 720p and spotrobotL, 12 frames (`cmp` rc 0). The build is 0 warnings, 7 test binaries |
| **a forced field differs** | arms A/B/C each give a different stream from the base and from each other |
| **determinism** | the assignment is an insertion sort with ties broken by index and a fixed histogram; 3 repeats of arm B on dng 720p byte-identical |
| **exact CBR** | every armed stream is exactly `32 + nslices × slice_bytes × nframes` at its own (reduced) rate: 1,537,376 B at 1080p, 221,432 B at 720p, 81,824 B on cf_gfx — identical across A, B and C |
| **legality preserved** | `gamut: 0 committed samples outside legal range` on **every** arm of **every** cell |
| **round trip with the field live** | arm 4 (content-independent field, both ends): `omc_dec` output equals `--recon − 2048` byte for byte, and the encoder prints `baseband-safe: yes`. **rt = 0 holds with a field-modified plan** |
| `--recon` provenance | verified this session: `recon − 2048` is byte-identical to `omc_dec`'s output over 3.69 M samples, single constant difference, so every picture measurement below is taken from `--recon` |

**The strength sweep.** The assignment has one free parameter, `g`, and picking it by hand would be
a tuned result. Swept on spotrobotL @0.5, 4 frames, repair passes against a base of **377**:

| g | offsets at ncp = 32 | arm B passes | arm C passes |
|---|---|---|---|
| 1 | 1 point ±1, 30 at 0 | **357** (−5 %) | 418 (+11 %) |
| 2 | 5 at −1, 3 at +1, 1 at +2 | 421 (+12 %) | 419 (+11 %) |
| 4 | 11 at −1, 6 at +1, 3 at +2, 1 at +3 | 571 (+51 %) | 543 (+44 %) |
| 8 | degenerate (see below) | 377 (= base) | 377 (= base) |

The trend is monotone and it is the wrong way: **the more field, the worse legality.** `g = 2` was
carried into the battery as the lightest setting that actually moves more than one control point.

**A geometry defect found by the sweep, and it matters for the design.** At `g = 8` the counts
overflow `ncp` and the assignment falls back to all-zero — and the same degeneracy happens at
`g = 2` whenever `ncp` is small. **On cf_gfx (448 wide, `ncp = 9`) the field is identically zero on
every control point of every slice** (`sa7field … offsets −1/0/+1/+2/+3 = 0 10368 0 0 0`), so the
cf_gfx rows below measure nothing but the 4.52 % rate the syntax took away. **One control point per
64 luma columns does not survive narrow pictures**: a 448-wide picture gets 9 control points and a
mean-zero histogram with a +3 class needs at least ~20. Either the pitch must scale with the
picture (e.g. `ncp ≥ 24` always, i.e. 18 columns on cf_gfx) or the histogram must change on narrow
pictures. This is a real design constraint the sizing in §7.9 did not catch, because §7.9 sized the
field from 1080p demand maps.
