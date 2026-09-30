# CHANGES — OMC-1 v5.3.5 (baseline release, 2026-09-06; stream minor 16)

v5.3.5 is the new baseline: **everything accomplished since v5.3 that passed its gates, landed at its intended default**, so that every later change is measured against one stacked base (owner decision 2026-09-06). It was built in `.work/v535` from the Task G integration tree (`v54tree_g`, minor 16) plus the batch in §B. Its stacked measurement is Agent 5's ladder on the v5.3.5 binaries (see `LEDGER_v5_3_5.md` §G.5 / the sandbox ledger H.13).

## A. Landed in the integration round before v5.3.5 (all gated; NORMATIVE marked)

| # | change | marker / files | normative | gate | ledger |
|---|---|---|---|---|---|
| 1 | Agent 5's 14 doc/code fixes: true bounds (40-per-entry emit, 48 repair passes, 4,096 lock candidates), `a2_strict` default on, encoder checks declared rational conversion, one slice-height rule, lossless ceiling and default rate per format, 0.3 bpp as a mechanical limit, two floors stated | `[A5-M*]` in `src/config.c`, `tools/omc_enc.c`, `tools/omc_uc_tool.c`; `HARDWARE.md`, `HW_TIMING_METHOD.md`, `BITSTREAM.md`, `CONTROL_PLANE.md`, `REPORT.md` | no | 26/26 byte-identical | S5.83 |
| 2 | `omc_dec --lose` walks true slice extents (`used_bits`, 24 bits at bit 86) instead of a fixed stride that damaged the wrong slices | `[G-LOSEWALK]` `tools/omc_dec.c` | no (tool) | decode identical to the reference injector; old probe differed | S5.83, S5.88 |
| 3 | Concealment upward-only: downward searches and spatial interpolation deleted; fully-intra-frame loss freezes | `[G-CONCEAL-UP]` `src/codec.c` | no (concealment is not normative) | identical to the shipped rule on an isolated loss; 0 ms deferral | S5.83 |
| 4 | Two declarations (`sh_held`, `sd_*`) moved above the forward `goto encode_attempts` sites (C11 6.2.4p6) | `[G-C11]` `src/codec.c` | no | byte-identical | S5.83 |
| 5 | Six C8 violators pinned: `OMC_Q5INTRA`(1) `OMC_XSL_LOOPFREE`(1) `OMC_TPART`(0) `OMC_XSL_CASC`(0) `OMC_XSL_SPREAD`(0) in the freeze list; `OMC_DBG_ZBAND` inline decoder read removed and announced | `[G-FREEZE6]` `src/codec.c` | no (pins shipped values) | 8-lever freeze gate, negative control bites | S5.83, S5.89 |
| 6 | OMC-TF deleted: `src/tfilt.c`, `tests/test_tf.c`, `tools/omc_tf_tool.c`, `include/omc_tf.h`, Makefile targets, `OMC_TF` validator, `omc_tf_mode`. Header `tf_mode` bits must be 0 | `[G-TFDEL]` | no (field already had to be 0) | build clean, `test_unit` | S5.84 |
| 7 | Agent 1 motion package: per-block motion field (bit 7 of the `n_steps` byte) + half-pel + A5 fetch barrier; five levers frozen | `[A1-*]` `src/codec.c`, `src/tans.c` (`omc_tans_mv[6]`), `src/internal.h`; `BITSTREAM.md`, `TEMPORAL_T5.md` App. M | **YES** | == Agent 1 ship tree on 3 cells; A4 15/15; 16/16 chains | S5.84, S5.85 |
| 8 | `OMC_MINOR_T5` 15 → 16 (one bump for the round); a minor-15 decoder refuses minor-16 streams (`bad stream header`) | `include/omc1.h` | **YES** | verified refusal | S5.85 |
| 9 | `[A2-LOCKCAP]`: lock-candidate walk bounded by progress (`OMC_LOCK_MAXTRIES` 16, counted once a lock exists) | `src/codec.c`, `src/internal.h` | no | 26/26 identical; extrema 9/9 encode; chains | S5.88 |
| 10 | `[A2-Q5CTX]`: Q5F-skipped intra values made context-neutral at both ends so a loss cannot desync the entropy decoder on byte-perfect slices | `src/codec.c` (`band_scan` gains `inter`) | **YES** (on 16) | 0 extra failures on 10/10 patterns (shipped 14–58); chains; 720p @0.5 Cb −0.032 / Cr −0.035 dB recorded | S5.88 |
| 11 | `--no-fill` honoured (`fill_grain_explicit`); it had been silently inert | `[G-NOFILL]` `include/omc1.h`, `tools/omc_enc.c`, `src/codec.c` | no | `--no-fill` == `OMC_FILL=0`, ≠ default | S5.89 |
| 12 | `OMC_DBG_ZBAND` announced when set | `[G-FREEZE6]` | no | — | S5.89 |

**Not changed, by measurement:** 720p slice height stays 8 (16 rows removes the grille but the
raster latency model gives 1.139 ms with a declared 720p→1080p conversion, over the 1 ms bar;
S5.89). `derive.py`'s depth truncation is kept (S5.86).

**Gates on the whole tree (Agent 4, MEMO 013):** `test_unit` all ok; chains 16/16 (CDR + baseband,
8 generations, zero bytes moved); recovery identical by both injectors; freeze with biting negative
control; inert at `--refresh 1` except the minor byte; pristine decoder refuses. Re-gate after items
9–12 in progress.


## B. The v5.3.5 batch (landed 2026-09-06 evening)
| # | change | source | default | gate |
|---|---|---|---|---|
| B1 | **Block-layer half-pel motion — UNCONDITIONAL** (`omc_blkhp = 1`, no lever: it sets the wire unit of the block delta) — NORMATIVE, minor 16 | Agent 1 Msg 8, `Agents/Agent1/diffs/blkhp_vs_v54tree_g.diff` | on | byte-identity vs Agent 1's reference build (fill on): stream + decode IDENTICAL on 3 cells; 8-gen CDR chains PASS (0 bytes moved gen 2..8, two cells); recorded regression floorballgameL f16–f23 (allocator; plan-idempotence work) |
| B2 | Region half-pel stays in the search and its lever `OMC_MVHP` stays frozen at 1 (unconditional in effect) | Agent 1 Msg 8 §d | on | freeze list |
| B3 | Luma-only motion-compensated concealment on intra-frame loss `[A2-INTRACONCEAL-Y]` | Agent 2 Msg 14, `Agents/Agent2/diffs/intraconceal_codec.c.diff` | on (loss path only) | byte-identical on clean streams |
| B4 | **Grain fill OFF by default** (library default `fill_grain = 0`; `--fill` / `OMC_FILL=1` turns it on) — owner 2026-09-06, IP review item 0b | coordinator | off | negative control: default stream ≠ fill-on stream |
| B5 | Memoised lattice candidate search `latt_inval_box()` (byte-identical) | Agent 5 B2, `MERGE_src_latt_probe.inc.lattmemo.diff` | — | byte-identity (fill on) vs reference |
| B6 | Fill/quantiser idempotence unit test (552 combinations) | Agent 3 A5, `test_unit_fillquant.diff` | test | `test_unit` all ok |
| B7 | Slice-aligned packetiser/depacketiser `omc_pack`/`omc_depack`; ST 2110-20 / SDI pixel path `omc_pixpack`/`omc_pixunpack`; DDR service model `src/ddr_model.c` + `omc_ddr_sweep` (standalone; the in-codec DDR hooks are NOT landed — see §C) | Agent 4 A3/A4/A6 | tools | build; Agent 4's round-trip gates (`Agents/Agent4/notes/h_pkt_roundtrip.sh`, `h_pix_roundtrip.sh`) |
| B8 | Docs: `HARDWARE.md` §2a (tANS 136 tables, 4.46/6.86 Mbit) and §3a (per-band coefficient widths; 18 bits free in UltraRAM); `DDR_WINDOW_CACHE.md`; `DDR_TASKD_IP_NOTE.md`; `harness/prep_master.py` 4:4:4 16-bit path | Agent 4 A7/A8/A9 | docs | — |
| B9 | Harness instruments: `lat_lose.py` (reference loss injector), `lat_model.py` (39/39 cells), `lat_gates5.sh`, `lat_m3_ladder.sh` (per-row binary guard), render scripts | Agent 5 D1–D5 | harness | — |
| B10 | Every reference in code, docs and file names renamed from the working title to v5.3.5; `OMC_PRODUCT_VERSION "5.3.5"` in `include/omc1.h`; `CHANGES_v5_4_G.md` → this file; `LEDGER_v5_4.md` → `LEDGER_v5_3_5.md` | coordinator | — | `grep -r 'v5\.4'` = 0 |

## C. Accepted since v5.3 and NOT in v5.3.5 (queued, with the reason)
| item | reason | where it goes |
|---|---|---|
| Refresh boost 50 → 100 (`OMC_RBOOST`) | measured better on one frozen cell (LEDGER B5.2) but the owner's condition — a full-gamut cost measurement showing the other seven slices are not starved — has not been run | measurement lane, then a one-constant change |
| Lazy band-cost table `bc_bits()` (Agent 5 B1), `refresh_r == 1` allocation guard (Agent 4 A1), row-outer prediction gather (Agent 4 A2), in-codec DDR hooks (Agent 4 A6) | their diffs are against minor 15 and reject at sites the motion package rewrote; all are byte-inert (memory/efficiency), so no v5.3.5 measurement changes without them; rebasing is a coding task for the owning agent | WORK_QUEUE F2 |
| Band-offer predicate shared with `lock_verify` and the lattice admission window (Agent 3 A2/A3) | Agent 3's own A0 precondition: all three of his accepted features carry the dead stand-down lever's terms and must have `omc_fill_stood_down()`, `a3_standdown`, `a3_sd_ctx` (and `a3_floor`, `a3_target`, `a3_brow2`) stripped and re-gated before promotion — a coding task for Agent 3; and they are active only with the fill ON, which v5.3.5 ships OFF | WORK_QUEUE Q5 (repair reform) — Agent 3's next item after the seam |
| Level-1 4:4:4 chroma fill halving (Agent 3 A1) | superseded: the fill is off by default and leaves the format in v5.4 | closed |
| Inter dead zone 10/16 (Agent 2 W10) | ruled "does not merge" (MEMO 020: luma down on 11/15 cells) | falsified register |
| 8-bit depth-relative constants | not built; owner's route decision (a) taken 2026-09-06; a builder assignment | WORK_QUEUE, first v5.4 item |

## D. Known defects carried into v5.3.5 (recorded, not hidden)
- `test_xsl` **G-T5-CUT4** (hard plates at the exact rails) **PASSES on v5.3.5 defaults (0/0) because the fill is OFF; with `--fill` it fails** — "plates alone" 9 samples, localised by Agent 1 (D3) to the PER-REGION motion search `[S5-MVREG]` (four vectors in one slice; the block field and half-pel are not the cause); "cut against footage" 10 samples — the in-gamut repair's impulse-table estimator versus inputs it does not model (the `[S5-DC]` parity rounding; Agent 1 measured that `OMC_MVREG=0` clears this half too on his tree). One mechanism, two triggers: the repair's per-band impulse table assumes a single prediction and symmetric rounding. Queued builder fix (WORK_QUEUE L1-0). The fill-on path is not a shipping configuration of v5.3.5.
- The in-gamut repair is skipped on CDR re-encodes (`!e->cdr_input`, Agent 4 B4a): on highwayviewL @1.0 generation 2 re-encodes with 31 out-of-range samples, exits 2 with an announced refusal, and the chain settles only at generation 5. Announced, not silent; queued (WORK_QUEUE L1-1).
- Two arms refuse to encode at 0.5 bpp on out-of-range samples (officewalkL 4:2:2 and 4:4:4, spotrobotL 4:4:4; Agent 5 F1): the illegal-source policy (commit-and-flag) is decided and not yet built; the 4:4:4 cases point at the `omc_off_c444` chroma step doubling (Agent 5 F3; WORK_QUEUE C6).
- **Fill OFF reopens the slice-seam replication defect** (Agent 3 C2): with the fill on, rows 13–14 of each 16-row slice replicate at 0.6–0.7× the source's rate; with the fill off they replicate at **15.7× (luma) and 22.9× (Cb)** the source's rate — the fill was masking `dwt.c` §55's one-neighbour boundary. The fix in flight is the two-sided boundary predictor (Agent 3, MEMO 028); until it lands, v5.3.5 carries the seam replication that v5.3 carried under the fill. Also from Agent 3 C1: without the fill the codec invents no texture at all (0.00 % on every plane, twelve arms), and fill-off beats fill-on on source correlation in 93 % of band/plane cases.
- A signed edge fringe on the right of strong vertical edges, dated to `[S5-DC]` (Agent 5 F4: −0.67 at minor 15, −1.69 now); design item for v5.4 (value-dependent rounding instead of spatial parity).
- Block half-pel's allocator-driven regression on floorballgameL f16–f23 (−0.252 NEG); test case of the plan-idempotence work (Agent 2).
- R=2R not met (Agent 5's ladder); the v5.3.5 ladder is the baseline number.
