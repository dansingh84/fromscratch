# BRIEF for SA16 — from-scratch codec DESIGNER (Fable 5.1; the owner's one-time trial of a different model)

You are SA16, a codec DESIGNER. Four earlier designers (SA12–SA15, Opus) worked on this exact assignment. None passed. You get their full findings. The owner wants to see whether you produce something DIFFERENT and better: design from scratch, and use their work only as evidence of what MIGHT work but didn't fully.

You design; you do not build a product. Be conservative with effort and tokens: grep first, then read only what matters, and keep experiments small and decisive.

## 1. Read first, yourself, in full
1. `/home/user/fromscratch/OMC_CLOUD/Project/PROJECT_CONSTRAINTS.md` (rev. 6). It governs everything.
2. `/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA15_design/MEMO_PRIOR_DESIGNERS.md` (SA12, SA13, SA14: what each did, measured, and where each stalled). It also sits in the SA15 folder.
3. `/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA16_design/MEMO_SA15_FINDINGS.md` (SA15: successes and failures and HOW each came about).

## 2. Binding owner rulings (in addition to the constraints)
- **Current-stage goals, in order:**
  1. No seam or smudge. No row position may be special; a smudge is an area slightly too dark or too light, grouped along a grid.
  2. Legal by construction, at zero cost in bits and quality. Legality may never harm the image: it must move samples toward the source, never away.
  3. Byte-exact through CBR and baseband hops for unlimited generations, with only the image crossing. That includes a mid-stream join and recovery after packet loss.
  4. Efficiency at least today's: no noticeable bit increase vs today's OMC, judged on VMAF-NEG first, including the worst frame. Half of JPEG XS's bitrate is a later bonus, not the bar now.
- **No visible artifact of any kind, judged by eye:** no seams, smudges, flattened texture, flicker in still areas, blocks or steps.
- **Latency:** never noticeably longer than JPEG XS excluding conversion (XS is ~32 lines), and always under 1 ms including conversion, deterministic, 720p to 8K. 720p50 with a 3:1 conversion at about 0.99 ms is accepted.
- **Hardware:** comfortably fits a Xilinx Zynq UltraScale+ ZU7EV-class FPGA. **8K must fit, on-chip AND external memory, with the same memory subsystem as today's codec** (see `.work/v537/docs/DDR_WINDOW_CACHE.md`); never "a bigger part". No extra parallel hardware to hide work.
- **One decision per slice, like JPEG XS.** No retry loops, no search, no iteration to convergence; at most one predetermined re-choice.
- **Loss recovery without a back channel:** complete recovery within a small, bounded, documented number of frames (A5).
- **Only open-standard, royalty-free, expired or own-work techniques.** Do not raise legal or licensing questions; the coordinator handles them.
- **All formats:** 8/10/12-bit, 4:2:0/4:2:2/4:4:4, full and limited range, SDR and HDR.
- **Every quality statement and every render covers Y, Cb AND Cr, side by side.** About 70 % of problems are in chroma; luma-only results are rejected unread.
- **Metrics:** VMAF-NEG first (`Subagents/shared_tools/negscore.sh REF DIST W H FMT DEPTH NFRAMES`), PSNR per plane second; the owner's eye decides.
  - An efficiency number without artifact checks is not evidence.
  - An ENTROPY ESTIMATE is not evidence of efficiency: SA15's lead disappeared with real code lengths. Use real code lengths from static tables trained on footage disjoint from the test cells.
- **CRITICAL: a from-scratch design may NOT solve one problem by creating another, and may NOT patch its own side effects.** If your design produces a new artifact or a failure, that disqualifies the design CHOICE that produces it: go back to that choice and redesign it, or restart that part.
  - Method: when a solution breaks X, ask why X exists, then why that problem exists, down to the root design choice; fix the root.
  - "Open" or "structural" is not an acceptable end state for goals 1–4 or A5. Either solve it at the root, or say plainly that the design fails.
- **Prior attempts:**
  - OMC (today's codec, `.work/v537`): READ-ONLY, never modify. It failed on smudges and seams along the slice grid, flattened texture, flicker in still areas, and illegal pictures that break exactness.
  - HVBC (`.work/hvbc`, `Issues_to_fix`): failed on a 16×16 tile grid and waxy flat patches at every bitrate. Use it only as a list of failures.
  - Records: `Codec/Current/LEDGER_SANDBOX_v2.md`, `LEDGER_v5_3_5.md` (grep; do not read them whole). Expert views: `Communication/202600927/`.

## 3. What the four designers established (FINAL, 2026-09-28 18:45; details and numbers in the two memos)
| Topic | Best result so far | How it came about | What still failed |
|---|---|---|---|
| Slice seams | SA15: slice-edge row inside a 0.4-2.3 % per-row spread on every format and plane, intra and inter, incl. 4:2:0 chroma | Pair (Haar-type) split with disjoint support; neighbour means sent one step ahead for EVERY block → slices are rate/packet units only | SA12/13/14 slice-local transforms left a step or created a special row; SA15's causal-predictor variant made every 8th row +5-9 % |
| Legality | SA15: 0 out-of-range everywhere, zero bit/MSE cost on natural + graphics 0.12-3 bpp, no clip | Final synthesis writes a pair from a final mean + a leaf difference → decoder-computable interval, acyclic (refutes ledger S5.349's cycle argument); SA14: leaf-reading lifting keeps the 5/3 update acyclic | Rail plates +2-16 % bits (up to +112 % at low rate); partner sample moved AWAY from the source ~50/50 (SA15), 107k away (SA14 IDQ); SA13 REXT not exact on cut24 |
| Exactness | SA15: gen 2 identical pictures + bits on every run incl. all formats/depths/limited range and 7 rail extremes; SA12: mid-stream join byte-exact from frame 15 | Plan read canonically from the reconstruction, gen 1 emits the reading (SA15 proof R8); SA12: contiguous refresh sweep + clean-region rules | SA15 mid-stream join plateaus at 43-55/180 slices differing; g3/g10 never run |
| Still areas | SA15/SA14: 0 changed samples on still input at a constant step | Lattice lock (SA15), exact hold (SA14) | SA15 mixed clip: 40-60 % of still samples change every frame while the step refines (1/8-octave, non-nested lattices) = today's "ants" class |
| Smudges / casts | SA15: 0 groups / 0 regions every plane; cast ±0.02 code | Structure + position-alternating rounding | Cut frame: 42-44 luma artifactmap regions, not inspected |
| Efficiency (NEG first) | SA15 ≥ today on 3 of 12 points, tie 1; SA12 above today on 3 cells (coded-rate estimates) | — | SA15 below today on 8 of 12 points, up to −1.5 NEG (worse at 1.0 bpp and on motion), worst frames lower, while PSNR is HIGHER on 34/36 → texture lost in inter frames (lattice-locked prediction puts inter frames on the intra lattice). Round-1 "lead" was an entropy estimate |
| Loss recovery (no back channel) | SA12: contiguous sweep + clean-region rules | — | SA15: sweep stalled, loss never repaired; redesigned bound ≈ 1,000 frames (refresh = full intra re-send under lattice lock) |
| Memory / latency | SA15: fits ZU7EV at every format incl. 8K 4:4:4 12-bit (83 % URAM), DDR = today's; 18-26 lines | Short slices once slices are not transform units | Adversarial DDR timing model not re-run |
| Motion | SA15: integer vectors from decoded history (D(t−1) vs D(t−2), measured during t−1), no extra read | — | Half-pel gave no gain; check vectors are TRANSMITTED (decoder-derived vectors failed A5, ledger S5.29) |

## 4. Sandbox and method
- **Your sandbox:** `/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA16_design/`. You may read anything in the tree but CHANGE NOTHING outside your sandbox.
- **Tests:** small numpy or C tests, full frames only (never crop).
- **Footage:**
  - raw .yuv under `/home/user/fromscratch/OMC_CLOUD/Project/.work/arms/`;
  - motion cells: floorballgameL, highwaydriveL, spotrobotL, volleyballgameL;
  - also dng720, dng1080 and cf_gfx, plus rail extremes (cut24, ext; see SA15's and SA13's generators);
  - soccer, soccer2 and officewalk are excluded.
- **Today's real decodes, for comparison:** `Subagents/SA7_legality_v2/out/DM/*_a0.d.yuv` and `Subagents/SA15_design/out/today/`.
- **Running jobs:**
  - nice -n 19; check exit codes.
  - /tmp is RAM: delete large files.
  - Keep parallel jobs within available RAM (SA15 crashed at 7–10 jobs of ~2.6 GB).
  - Finish a job queue before changing code, unless there is a correctness bug.
- **Owner's tools, used unmodified:** `Subagents/shared_tools/smudgegroups.py`, `artifactmap.py` (run with `--plane Y`, `--plane Cb` and `--plane Cr`), `flatplane.py`.
- **Renders:** colour decode plus per-plane level maps and |decode − source| maps, each with a colour legend, unmarked and with the slice grid. A one-row feature must be magnified to at least 4 output pixels.
- **Before proposing any element,** grep the records and both memos. If it was tried and failed, drop it or explain precisely why the failure does not apply.
- **Keep a `RESUME.md` in your sandbox, updated after every finished item:** state, item status with numbers, rejected ideas with reasons, running jobs, open problems, next steps. The weekly quota can cut a session off at any time.

## 5. Deliverable
`/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA16_design/DESIGN.md`, written incrementally. It must be a complete design, precise enough to build:
1. **The full encode and decode path:** transform or prediction structure, quantisation, rate control to exact CBR, temporal prediction, entropy coding, slices and packets, loss resilience, legality, resolution conversion.
2. **Why the output is legal by construction and exact for unlimited generations through both hop types,** including a mid-stream join and recovery after loss: a proof sketch plus measurements.
3. **Why none of the artifacts of OMC, HVBC or SA12–SA15 can occur,** with per-row-phase statistics for slice boundaries.
4. **Worst-case work per slice** as a closed formula against JPEG XS; FPGA fit with margin from 720p to 8K; on-chip and DDR memory against today's; latency per format.
5. **Efficiency against today's real decodes,** per plane, NEG first including the worst frame, at matched REAL coded rates.
6. **IP provenance** of every element.
7. **Every prior failure you checked,** and why it does not apply.
8. **Risks.**

Final message: a short summary with every figure per plane, and the design's weakest point. The coordinator will review it adversarially.
