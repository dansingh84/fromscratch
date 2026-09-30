# v5.3.5 — adversarial check (owner's four questions), 2026-09-06

## (c) Every default is what it is supposed to be — verified at RUN TIME on the built binaries, not by reading
| item | intended | check | result |
|---|---|---|---|
| grain fill | OFF unless `--fill`/`OMC_FILL=1` | default stream == `OMC_FILL=0` stream == `--no-fill` stream (highwaydriveL 4:2:2 @0.5, 3 f) | IDENTICAL — OFF |
| block-layer half-pel | ON, unconditional (wire unit) | default stream == `OMC_BLKHP=1` == `OMC_BLKHP=0` (env inert) | IDENTICAL — UNCONDITIONAL |
| region half-pel | ON, lever frozen at 1 | freeze list `{ "OMC_MVHP", &omc_mvhp, 1 }` | present |
| per-region motion search | ON (default 1) | `omc_mvreg` default 1 | present |
| refresh boost | 50 % (100 % deferred to its cost measurement) | `omc_rboost` default 50 | 50 |
| A2 latency bar | strict for rasters ≥ 720p | `cfg.a2_strict = (a2_want && omc_uc_format_supported(...))` | present |
| luma-only intra concealment | on (loss path only) | `[A2-INTRACONCEAL-Y]` markers 2; clean decode byte-identical to the reference build | present, inert on clean streams |
| coefficient saturation, Q5 context neutrality, lock-walk cap, upward-only concealment, OMC-TF deleted | as in the integration round | markers in source; `test_unit` all ok | present |
| stream minor | 16 | `OMC_MINOR_T5 16` | 16 |
| product version | 5.3.5 | `OMC_PRODUCT_VERSION "5.3.5"` | present |

## (d) Every reference names the codec v5.3.5
- `grep -rI 'v5\.4\b\|v5_4\|V5\.4'` over the package: **0 hits** outside CHANGES §C/§D, where "v5.4" names the NEXT version's queue (future work, not this codec).
- File names: `CHANGES_v5_4_G.md` → `CHANGES_v5_3_5.md`; `LEDGER_v5_4.md` → `LEDGER_v5_3_5.md` (package and project); `CHANGELOG_v5.4.md` → `CHANGELOG_v5.3.5.md`; no `*v5_4*` / `*v54*` file names remain (`find` = 0).
- `tests/refcheck.sh`: all 52 cited sections resolve (7 pre-existing unresolved section numbers are unchanged from v5.3 and listed by the tool).
- Historical version docs (`OMC_V5.md`, `OMC_V5_1.md`, `OMC_V5_2.md`) describe earlier versions by their own names; they never named the current codec.

## (b) Everything works as intended — gates on the built tree
| gate | result |
|---|---|
| `make all` (encoder, decoder, five test suites, seven tools) | clean (warnings: 5 unused-parameter/variable, pre-existing) |
| `test_unit` (incl. the new fill/quantiser idempotence test), `test_cap`, `test_cc`, `test_uc` | all ok |
| `test_xsl` (cross-slice suite incl. G-T5-CUT4 hard plates) | ALL PASS at v5.3.5 defaults (fill off); fails with `--fill` — recorded in CHANGES §D |
| byte-identity control vs Agent 1's reference build (fill on, block half-pel on) | stream IDENTICAL on 3 cells; decode IDENTICAL |
| negative control (fill on ≠ fill off) | differs on 3 cells |
| 8-generation CDR chains, v5.3.5 defaults, 6 frames, highwaydriveL 4:2:2 10-bit @0.5 and 4:4:4 12-bit @0.5 (`omc_dec --cdr` → `omc_enc --cdr-in`, Agent 5's recipe) | **PASS, zero bytes moved at every generation 2..8 on both cells** (`logs/v535_gates/chains2.out`). A first run with a wrong harness (plain-pixel re-encode of coded-domain data) is recorded as void in the sandbox ledger S5.119 addendum. **Limitation (Agent 4 Msg 25 §0, received after this gate ran): a 6-frame chain can invert at the arm's full 24 frames on a hard arm (officewalkL); full-length chains on all 27 long arms are part of the stacked measurement when work resumes.** |
| Agent 5's ladder on the v5.3.5 binaries (the stacked measurement) | NOT YET RUN — Agent 5 holds his M3 write-up; the owner has paused new assignments post-v5.3.5; the ladder is the first measurement when work resumes. Until then the v5.3.5 quality baseline is Agent 5's minor-16 ladder plus the block half-pel deltas of Agent 1 Msg 8. |

## (a) Exhaustiveness — every "implement" item in the six ledgers, with its v5.3.5 status
(filled from the sandbox ledger H.2/H.12/S5.110–S5.119, LEDGER_v5_3_5 §B/§G, UNIMPLEMENTED_SUCCESSES.md, and all five agent success ledgers in their revised form, each re-read in full on 2026-09-06 evening)
| ledger | item | v5.3.5 status |
|---|---|---|
| sandbox H.2 | step-1 legality lattice; Task C refresh-on-demand + hash; per-region vectors; lifting rounding fix; 4:4:4 chroma rung | LIVE (source-verified) |
| sandbox H.2.6 | 8-bit depth-relative rules | NOT built — owner chose route (a) 2026-09-06; first v5.4 item |
| sandbox H.2.7 | level-1 chroma fill halving | superseded (fill off / leaves the format) |
| LEDGER B5.2 | refresh boost 100 | deferred to its cost measurement (CHANGES §C) |
| Agent 1 A1, A4, A5, A6 | motion package, barrier, probe strip, n_steps guard | LIVE |
| Agent 1 A2 | block-layer half-pel | LANDED, unconditional (B1) |
| Agent 1 A3 | region half-pel kept, lever frozen | LANDED (B2) |
| Agent 1 B1–B10 | instruments | in `Agents/Agent1/notes` (not codec code; referenced) |
| Agent 1 D3 | MVREG rail defect | recorded (CHANGES §D), fill-on only |
| Agent 2 A1–A3, D0 | LOCKCAP, Q5CTX, no-fill fix, lose walk | LIVE |
| Agent 2 B1 | intra concealment luma-only | LANDED (B3) |
| Agent 2 C1–C3 | trailer, latency-model correction, compact header | parked/design (WORK_QUEUE T1) |
| Agent 2 W10 | inter dead zone | rejected (MEMO 020) — not landed, correctly |
| Agent 3 A1 | chroma fill halving | superseded |
| Agent 3 A2, A3 | mirror fix, lattice admission | NOT landed — Agent 3's own A0 precondition (strip the dead stand-down terms first, re-gate); fill-on only; CHANGES §C |
| Agent 3 C2 | fill off reopens seam replication 15.7×/22.9× | recorded (CHANGES §D) — fix in flight (two-sided predictor) |
| Agent 3 C4 | seam dominant term is the level-1 highpass | recorded (S5.118); contradicts the expert; his row-class model holds on luma, fails on chroma |
| Agent 3 A4 | frozen-plan instrument | instrumentation only, must not ship — not landed, correctly |
| Agent 3 A5 | fill/quantiser unit test | LANDED (B6) |
| Agent 4 A1, A2 | R1 allocation guard, row-outer gather | NOT landed (diffs reject; byte-inert; CHANGES §C) |
| Agent 4 A3, A4 | packetiser/depacketiser, pixel path | LANDED (B7) |
| Agent 4 A6 | DDR model + spec | LANDED standalone (B7); in-codec hooks not landed (§C) |
| Agent 4 A7, A8, A9 | HARDWARE §2a/§3a, prep_master | LANDED (B8) |
| Agent 5 A1–A4, C1, E | lossless fixes, A2 strict, rational check, slice rule, upward concealment, nine doc fixes | LIVE (the 14 diffs) |
| Agent 5 B1 | lazy cost table | NOT landed (rejects; byte-inert; §C) |
| Agent 5 B2 | lattice memo | LANDED (B5) |
| Agent 5 D1–D5 | harness instruments | LANDED (B9) |
| Agent 5 F1–F4 | diagnosed defects | recorded (CHANGES §D / WORK_QUEUE) |
