# Static-analysis / MISRA-class audit (2026-07-28)

> **STATUS in v5.0: partially superseded.** v5 fixed five undefined left-shifts of negative values in the normative transform and colour stage, and a leak in `tests/test_cap.c`; all six suites are now clean under AddressSanitizer and UndefinedBehaviorSanitizer. See `docs/OMC_V5.md` 5.1.


> **Currency note (2026-08-03, v4.7 rev8, bitstream minor 7).** This audit
> covers the 2026-07-28 v4.2-era tree (~2.9k LOC). The v4.4-v4.7 additions
> (deadzone, entropy v2, block-MV, grain-hold v3, static fill, plan
> hysteresis, perceptual allocation) are NOT covered, and the line numbers
> cited below no longer align with the current sources. A re-run of this
> pass on the v4.7 tree is an open item. Findings below are historical and
> preserved as-is. For the current feature set see REPORT.md 18.x,
> ENHANCEMENTS_LEDGER E-9/E-10/E-11, and BITSTREAM.md 9.3-9.5.

Tooling run: `clang-tidy 18` with bugprone-*, clang-analyzer-*, misc-* (the
overlap with MISRA C:2012 advisory/required rules on pointer arithmetic,
conversions, and resource handling). Full MISRA certification with a
dedicated tool (e.g. a licensed checker + rule-by-rule sign-off) remains a
partner-gated item; this pass covers the free-tool subset and records a
deviation register for the rest.

## Fixed
- **omc_dec.c: obuf leak on exit** (clang-analyzer-unix.Malloc). The v4.2
  output-stage buffer was not freed. Fixed (free added); decoder output
  verified bit-identical and deterministic after the change.
- Earlier in this program: the two -pedantic nits and the slice_h=8
  out-of-bounds read (ASan) - already fixed and gated.

## Deviation register (reviewed, not defects)

| site | check | rationale |
|---|---|---|
| dwt.c multiple | implicit-widening-of-multiplication (int*int used as pointer offset) | all indices are bounded by frame dimensions (<= 8192 x 4352); int (>= 32-bit here) cannot overflow. The load-bearing large strides already use explicit (size_t) casts. Cosmetic under MISRA 10.x; no correctness impact. Will be cast explicitly in the architectural-model rewrite. |
| codec.c:339,740 | signed-char-misuse (int8_t MV -> int) | MV components are intentionally signed (-64..63 / -32..31); the sign IS the value. No misuse; the byte is never treated as a character. |
| codec.c:117,146 | dead store (`o` post-increment on last field) | idiomatic serialize-cursor; the final `o +=` documents layout completion. Harmless; kept for symmetry/maintainability. |
| codec.c:473,476; dwt.c:149 | analyzer "garbage value" | false positives from path explosion: llbuf/Lc/col are fully written by the immediately preceding loop before any read. Verified by inspection and by ASan-clean runs across the whole test corpus. |
| codec.c:1512 | narrowing uint32->int | value is a slice index bounded by nslices (<< INT_MAX); defined for all reachable inputs. |

## Standing guarantees relevant to a MISRA program
- No dynamic allocation in the per-slice/per-frame path (all buffers
  allocated once at create; verified).
- No recursion anywhere (checked).
- Encoder/decoder instances share no mutable state (reentrancy fix + TSan).
- Bounded loops throughout; the one backoff loop has a hard 40-iteration
  cap (measured worst case 32; docs/HARDWARE.md section 7).
- Strict ISO C11, -pedantic -Wall -Wextra clean.

## Next step for full certification
A licensed MISRA checker run + formal deviation sign-off, done proactively
or when a hardware partner's process requires it (~days at ~2.9k LOC). The
register above is the starting draft.

---

# v5.1 (2026-08-25)

Built and gated with **gcc 16.1.1** at `-O2 -g -std=c11 -Wall -Wextra`. No new
warning is introduced by the v5.1 changes; the pre-existing
`-Wmisleading-indentation` notes at `src/codec.c` (the two `if (d1 > lim) d1 =
lim; if (d1 < -lim) d1 = -lim;` lines) and the `rowbad set but not used` note are
v5.0's and are unchanged.

`make test` — 96 assertions across six suites, **rc = 0**.

Note for anyone repeating the v5.0 build notes: **a system C compiler is
sufficient.** The v5.0-era record describes a private zig/musl toolchain because
the machine of the day had no system compiler; that is not a property of this
tree.
