# v5.3.6 — adversarial check: was everything that should have been applied actually applied?

Compiled 2026-09-08 by the coordinator after building v5.3.6. Part 1 walks **every finding in the six input ledgers** (`project_docs/findings_ledgers/`) that implies a change to code, tests, tools, harness or documentation and states where it landed or why it did not. Part 2 is the mechanical check that the change note's claims are true of the tree. Part 3 is the review of the package itself (build from the zip, gates from the zip, documentation vs code). Findings that are measurements, withdrawals, process rules or questions to the owner/expert are listed only where they change what ships.

Legend: **APPLIED** (where) · **NOT APPLIED** (why; where it waits) · **N/A** (no change implied) · **DOC** (recorded in a document, no code).

## Part 1 — ledger by ledger

### Agent 1 (AGENT1_FINDINGS.md)
| finding | implies | disposition |
|---|---|---|
| A1/A2/A13/A40 per-region search inert, `out_sad` never written | fix the search + margin | **NOT APPLIED** — Agent 1's own recommendation (A23, A35, A46): the fix fails G-T5-GAMUT2c and is quality-negative on graphics; the two halves must move together; margin choice with the expert (question 004). **Defect marked in the code** (`[S5-MVREG]` at `derive_mv_cols`), listed in CHANGES §C/§D, queued (L1-0; `queued_diffs/`). |
| A3/A38/A43 CUT4 two sub-counts; shipped refresh default breaches at cuts on every tree | close the breach; a gate that can see it | **APPLIED** — repair budget 13 (CHANGES §A1) + G-T5-CUT24 (§A2). Verified: 0 at every period incl. 8 and NONE. |
| A9/A30 GAMUT2c regression is a repair-budget effect; `GM_PASS` and `OMC_GAMUT_DEFPASS` must move together | both constants | **APPLIED** — both at 13 (§A1). |
| A24/A28, A3-C17/C39 stale test binaries print `all ok` | never trust a test binary older than its sources | **DOC + PROCESS** — `make test` rebuilds (Makefile dependencies); `codec/bin/README_BIN.md` and README say never run a test binary directly; the package's binaries are built from the packaged sources (md5 recorded). No source guard added. |
| A42 no `test_xsl` section can certify the shipped refresh period | a long-enough section | **APPLIED** — G-T5-CUT24 (24 frames, period 8). |
| A19 harness traps (`-n 24` on 12-frame arms silently 12; `pgrep -f`; `OMC_GAMUT_STRICT` inert in `test_xsl`) | harness discipline | **N/A** for the tree (Agent 1's harness); the inert-lever fact is stated in TEMPORAL_T5's addendum via the two-constant rule. |
| A20/A29 A5 healing degrades with genuine region vectors (content-dependent) | — | **N/A** (the fix is not landed). |
| A47/A48 rebase-check script; texstat window `F0=4 NF=8` | agent tooling | **N/A** (Agent 1's notes; noted for the measurement lane). |
| F (question 004; `GM_PASS` needs an owner) | forwarding | **DOC** — WORK_QUEUE; the budget question is answered (13) for the pristine trees; granularity stays with the expert. |

### Agent 2 (AGENT2_FINDINGS.md)
| finding | implies | disposition |
|---|---|---|
| B11–B13 the grain fill is the 8-bit lock blocker; couplings are not | fill off / out | **APPLIED earlier** (fill OFF, v5.3.5) — F0 (out of the format) is a builder assignment, queued. 8-bit lock at defaults holds gen 2/3 (his B11 FILL-OFF arm). |
| B15 Rule B contra-indicated; Rules A/C cancelled | do not build | **N/A** — not built. |
| B16 A0 breaks the flatness bar; **720p's worst slice improves +3.15 dB with fixed budgets** | a lead for the 720p grille | **DOC** — WORK_QUEUE v5.3.6 addendum row n7. |
| B18–B20, B25–B26 gamut breach at cuts, shipped default, three trees; gate too short | close + gate ≥ 2 waves | **APPLIED** — §A1/§A2 (his probe `patch_cutprobe6.py` is the gate, verbatim). |
| B28/B29 rebase-check, vacuous-check traps | process | **N/A**; the rule "build the discriminator first" was applied to the fuzzer here (its self-check caught the fixed-slice assumption). |
| B31 `rsync --exclude 'test_*'` trap | process | **N/A**. |

### Agent 3 (AGENT3_FINDINGS.md)
| finding | implies | disposition |
|---|---|---|
| C1/C3/C8/C41 Way 1: sound mechanism, three-row anomaly with the fill off, "the seam repair goes in beside the fill result" | ship the predictor with the fill off | **BUILT, QUALIFIED, NOT SHIPPED** — landed as minor 17, quality-verified (six cells), then G-T5-CUT24 leaked with it on (4 samples at budget 13, 1 at 14; attribution runs with it off: 0). Reverted to a pinned candidate; minor stays 16. CHANGES §C, `src/dwt.c` §55. The repair granularity is the blocker (queue, expert). |
| C4 `slice_vis_rows()` returns `c->sh` silently for `vv % 4 != 0` | a probe trap | **DOC** — CONTROL_PLANE note (no source edit after the battery started; the guard itself is correct). |
| C6 the per-row rung fails lock progressively | — | superseded: the outside review's rung passes lock (credit at the admission site) and fails on gates — CHANGES §C; the falsified register's reason is corrected in WORK_QUEUE. |
| C9 `[G-LOSEWALK]` | in v5.3.5 | **already in** (verified `tools/omc_dec.c`). |
| C19–C25 budget one pass short; window 13–14; both constants; holds on both pristine bases | 13 | **APPLIED** — §A1. |
| C22 granularity question ("is the budget allocated at the right unit?") | expert | **DOC** — WORK_QUEUE; the `rowbad[]` observation (per-row information exists and is discarded) recorded at the repair site. |
| C27 the incumbent breaches the flatness bar on dng422 at every rate; luma flatness worst at the HIGHEST rate (unexplained) | flatness lane | **DOC** — CHANGES §D; WORK_QUEUE row n8. |
| C31–C37 mirror fix / lattice admission / A3 undemonstrated; A1's depth gate load-bearing | fill-on path | **NOT APPLIED** — fill OFF by default and leaving the format; Agent 3's own audit: the fix changes nothing on five cells; landing a no-op into a path scheduled for deletion is churn (CHANGES §C). |
| C38 gates run with the lever ON must be re-verified after later edits | process | applied to this build: the battery runs on the final binaries. |
| C12/C30 process-kill anchoring (`/proc/<pid>/cwd`) | process | **N/A**. |

### Agent 4 (AGENT4_FINDINGS.md)
| finding | implies | disposition |
|---|---|---|
| D6/D11/D12 the CDR-input exemption is a contract defect; key off the output contract; re-assert per generation | fix | **APPLIED** — §A3 (`[L1-1]`): repair runs on a CDR re-encode whenever the native reconstruction is out of gamut; in-gamut → unchanged fixed point. |
| D13/D14 gates are ~8× short of the 10,000-opportunity criterion; gen-3 minimum; state-horizon length | longer chains | **PARTLY** — chains are 8 generations (gen 3+ checked) on 6–12 frames; the 10,000-opportunity bar (~50 frames at 1080p) is NOT met by this battery and is stated as a limit in CHANGES §D/§E. Short gates are trusted downward only (D15). |
| D16–D18 officewalk-class refusal is predictor state, not content; INTERABS does not fix it | terminal rung (expert) | **DOC** — CHANGES §D; queue. `OMC_GM_INTERABS` stays 2 (his own reading: one arm is not enough). |
| D19–D23 three accepted items in no tree; land `all3` as one batch | land | **APPLIED** — §A7 (`ALL3_vs_v535.diff` + `MVGUARD_vs_v535.diff`; byte-identical). |
| D22 `ddr_model.c` not in `SRC`; `mvread` one-frame accounting; `store_bits()` 16 not 13; x32 optimism | build + doc | **APPLIED** (`SRC`) + **DOC** (`DDR_WINDOW_CACHE.md` addendum) + `[D-MV1]` fixes the wasted frame-1 search. |
| D25 packetiser / pixel tools re-gated on v5.3.5 streams | — | **already in**; not re-gated on minor-17 streams here (tools are stream-agnostic containers; noted §E). |
| D28 questions | — | answered in §A7/§C (batch: yes; instrument in the tree: yes, behind `OMC_DDR`; accounting: documented and fixed; INTERABS default: unchanged). |
| D30–D33 studio-range caveat withdrawn; clipped-decode trap | instruments | **N/A** for the tree; the battery's chains compare streams AND unclipped CDR pictures. |

### Agent 5 (AGENT5_FINDINGS.md)
| finding | implies | disposition |
|---|---|---|
| E17 the M3 classifier (`lat_m3_table.py:61`) could never return MET | fix the harness | **N/A for the codec tree** — that script is Agent 5's (`agent_notes/Agent5/harness/`), not in `codec/harness/`; the copy in this package still carries the defect he found; his fix, queue row n10. |
| E22 (3a) remove the unconditional CDR repair bypass | fix | **APPLIED** — §A3. |
| E22 (3b) contribution profile with chroma fill disabled | profile | **NOT APPLIED** — moot at the fill-off default; superseded by F0. |
| E23 the edge halo is NEW since `[S5-DC]` (−0.67 → −1.69) | design item | **DOC** — CHANGES §D (value-dependent rounding, v5.4 design). |
| E26 `lat_gates5.sh` never checked the encoder exit status (its chain section) | fix the shipped harness | **APPLIED** — `codec/harness/lat_gates5.sh` chain(): encode/decode exit status checked (an rc=2 encode writes a playable stream), and the STREAM compared from gen 3 on (E27). The identity section already checked status. Harness only, no binary change. |
| E27 compare streams, not decodes only | harness rule | **APPLIED** — the battery's chains report bytes moved AND stream equality per generation. |
| E20 flatness bar breached on 90/100 rows | flatness lane | **DOC** — CHANGES §D. |
| E29–E31 crop-arm provenance | corpus | **N/A** for the tree (Agent 1's folder); the battery uses `.work/arms` masters and `arms/long`. |
| E6 concealment upward-only diverges from f7 on fbgame | — | **N/A** (decoder behaviour on loss; recorded). |

### External review (EXTERNAL_REVIEW_V535_FINDINGS.md)
| finding | implies | disposition |
|---|---|---|
| A1 `test_xsl` 4-frame blind spot | — | **APPLIED** (CUT24). |
| A2 restore vector missing; skip-with-rc-0 | restore | **APPLIED** differently — 16 vectors restored; the gate re-based on a v5.3.6 golden vector (§B); a missing vector FAILS loudly (their rc-0 skip not adopted). |
| A3 28 warnings; `derive_mv_cols` casts; `rowbad[]` | cleanup | **APPLIED** with the `[S5-MVREG]` marker kept (their casts alone would have hidden the defect). |
| A4 stale minor-14 headers; BITSTREAM §3.1 | docs | **APPLIED**. |
| B4/B5 harness race and traps | process | applied to this battery (binaries frozen; `-s` and rc checked). |
| C1/C2 fuzzers | adopt | **APPLIED** — `harness/crcfuzz.py` + `tests/fuzz_check.sh` (hardened fallback here; no sanitizer runtime on this machine — stated). |
| D1 blotch clean; D2 renders exist on their branch | eye | **NOT DONE here** — no renders in the package (images excluded by rule); the owner's eye on v5.3.6 is queue row n4. Blotch not re-run on v5.3.6 (§E states it). |
| E1–E10 the seam fix, level/sign/strength, C8 gap, controls, residual | land + pin | **C8 gap APPLIED** (§A4, `OMC_VEXT_LVL` pinned); the predictor itself qualified (E6 gap closed by the six-cell A/B; E8 rounding stated) and **NOT SHIPPED** on legality (G-T5-CUT24); controls (E9) in the battery; residual (E10) in §D. |
| F1–F8 the rung; temporal excess; in-process freeze inheritance | do not land; doc | **NOT APPLIED** (rung) — CHANGES §C; F5 temporal excess in §D; **F8/I2 freeze inheritance documented** in CONTROL_PLANE (no source comment after the battery started). |
| G1 CLI segfault | fix | **APPLIED** (§A9). |
| H1 RBOOST cost; H2 RECOFF | — | **NOT APPLIED** — RBOOST: benefit and cost never on one clip (§C); RECOFF stays off (their exactness claim contradicted by our 8-generation chains, recorded). |
| H4 "every other default equals its freeze value" | method limit | **DOC** — F2 item 2d (release-gate lever sweep) stays queued. |
| I1 PQ still in the tree | remove | **APPLIED** (§A10). |
| I3 A5 loss on real footage | — | **N/A** (`[G-LOSEWALK]` verified present). |
| L6 tools worth adopting | — | fuzzer adopted; the per-row-phase temporal instrument NOT adopted (their script is on their branch, not delivered) — queue. |

### Landing register and unimplemented list (cross-check)
Items 3 (`OMC_MVHP`), 12–13 and 16-hooks (Agent 4), 18-memo (Agent 5): **landed**. Item 4 (RBOOST), 8 (8-bit), 9–10 (Agent 3 fill-on), 18-lazycost, Agent 1 region search, F0: **open with reasons**. Nothing in the register is marked landed without a row in CHANGES §A.

## Part 2 — mechanical checks on the tree
- Every marker CHANGES §A names exists in the tree (`[A2-CUTPROBE6]`, `[L1-1]`, `OMC_VEXT_LVL` pin, `[V536-FUZZ1]`, `[D-R1]`, `[D-LBORDER]`, `[D-DDR]`, `[D-MV1]`, `[A5-LATTMEMO]`, `NEXTARG` ×10 files, `[S5-MVREG] KNOWN DEFECT`, `G-T5-CUT24`, `c536_policy_restore_rail`, `OMC_GAMUT_DEFPASS 13`, `GM_PASS 13`, `OMC_MINOR_T5 16`, `OMC_PRODUCT_VERSION "5.3.6"`, `omc_vext = 0`, BITSTREAM §4.2a.1 as candidate).
- Every symbol CHANGES §A claims removed is absent (`OMC_CC_T_PQ`, `eotf_pq`, `sad_blk`, `uc_get_i32`, `rowbad[`, `getenv("OMC_MVHP")`): 0 hits.
- `gcc -Wall -Wextra -fsyntax-only` on every source, tool and test: 0 warnings.
- Stale-string sweep: no live document says minor 14 or 16 as current; no `argv[++i]` outside the macro definition and its comment; no `12 passes` as current; PQ appears only as "removed/refused/not carried".
- The lattice-memo landing was first reported as "lazy cost table + lattice memo"; the check found the lazy-cost diff had not applied (its base was wrong) — corrected in CHANGES §A8/§C and the ledger (S5.126). The gated byte-identity (12/12) holds for what actually landed.

## Part 3 — the package (zip review result, 2026-09-08)

Method: `OMC-1_v5.3.6.zip` unpacked into a clean directory; `codec/` built from source with the stock toolchain; the rebuilt encoder/decoder compared against the shipped `codec/bin/` on real streams; `make test` run from the zip; documentation swept for stale strings; inventory and hygiene checked. Script: `scratchpad/zipreview.sh` (its output is the basis of every line below).

| check | result |
|---|---|
| inventory | 1,902 files, 54 MB unpacked, 23.8 MB zipped; 0 parent-directory entries; 0 files over 30 MiB; 0 footage/images; no objects or `.git` |
| streams inside | 19 `.omc`: the 16 restored conformance vectors, the v5.3.6 golden restore vector, and the two fuzz-crash evidence streams under `logs/v536_gates/` — nothing else |
| shipped binaries | 15 tools/tests in `codec/bin/`; `omc_enc`/`omc_dec` md5 match `codec/BINARIES_20260908.md5` |
| build from source | `make all` rc 0, **0 warnings, 0 errors** |
| rebuilt vs shipped | streams AND decodes byte-identical on dng 4:2:2/10 @0.5, dng 4:4:4/12 @1.0, cf_gfx @0.5 |
| `make test` from the zip | rc 0, **93 `ok`, 0 `FAIL`** (five suites incl. G-T5-CUT24, G-T5-RESTORE on the golden vector, refcheck; levercheck skipped loudly as designed) |
| CLI trailing option | `omc_enc … --depth` → rc 1 with a usage error (was a segfault in v5.3.5) |
| documentation sweep | version 5.3.6 present in README, CHANGELOG, CHANGES, `omc1.h`; the one `minor 14` hit is the annotated historical v5.3.5 note; PQ appears only as refused/removed; no live `argv[++i]`; no dead references (`sad_blk`, `uc_get_i32`, `OMC_CC_T_PQ`) |
| completeness of the documents | CHANGES §A–§E filled (§E rendered from the battery log); this check's Parts 1–3; `README_PACKAGE.md`; 6 findings ledgers; the 3 external-review texts; 22 gate logs incl. the reverted first battery and the attribution runs |

What the review did NOT do: run the full 24-frame gate on 4K (the suites run at their fixed geometry); re-run the M3 ladder (the stacked measurement is the next task after the owner's go-ahead); apply the owner's eye (no renders in the package). Verdict: the package builds, tests and runs as its documents say; nothing in the documents describes a state the tree does not have.
