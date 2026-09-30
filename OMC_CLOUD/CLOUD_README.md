# OMC-1 cloud packet: START HERE

This packet is EVERYTHING a codec designer agent needs to continue the OMC-1 design work without access to the owner's machine. The owner supplies the footage separately (§3).

## 1. What this project is, and what to read
OMC-1 is a broadcast contribution video codec meant to replace JPEG XS. The work is at the DESIGN stage: numpy models on real footage, judged against today's OMC codec.

Read, in full and in this order:
1. `Project/PROJECT_CONSTRAINTS.md`: the governing requirements.
2. `Project/Subagents/DESIGNER_READING_PACK_FULL.md`: every owner ruling, method, test, result and falsified idea of all designers so far (SA12–SA19), verified complete. Its front guide maps sections to topics.
3. `Project/Codec/Current/HANDOFF_2026-09-28.md`: START HERE block, then §10.2 = PRIORITY ONE (owner, 2026-09-29): finish the NEW engine until all four goals hold (legality incl. never-away; exactness over >= 10 generations incl. CBR and baseband hops; no seams/smudges/streaks; efficiency >= today). No new codec version ships with ANY efficiency deficit. Legality first. NEWEST (ledger S5.404, handoff §10.2 last bullet): the SA19 group found every never-away route in the pair-pyramid (averaging) family closed (measured: R-FIX, R-CLIP; algebra: 5 routes); predict-only costs -15 NEG intra / -2.7 dB inter. NOT yet independently verified: your first job is to adversarially verify that verdict (SA19_design/DESIGN.md §L, GROUP_LOG.md). If it holds, the averaging pyramid is the root design choice to replace: find an engine where never-away holds by construction at zero efficiency cost.
4. `Project/Subagents/SA19_design/BRIEF_SA19.md`: the current assignment. `LAUNCH_INSTRUCTIONS.md` (next to this README) holds the exact launch prompts and follow-up instructions given to the designer and the two thinkers. It covers the current goals AND the big-picture challenges together, plus the newest owner rulings. Where it differs from the pack, the brief wins.
5. The latest work, to continue from as EVIDENCE, never as a base to extend:
   - `Project/Subagents/SA19_design/RESUME.md`, `DESIGN.md` and `GROUP_LOG.md`;
   - `Project/Subagents/SA19_design/bench/`, the model code.

Owner rules that trip new agents most often. All are in the pack §1, and listed here too:
- **Metrics:** VMAF-NEG first, then PSNR Y/Cb/Cr. Chroma is never optional.
- **Rates:** always REAL code lengths, with tables trained on footage disjoint from the test cells AND on the exact configuration being measured.
- **Design from scratch.** You may pick and choose elements from earlier designs, but never continue an existing design as your base.
- **No patches.** A design-created artifact disqualifies the choice behind it. "If we design something that doesn't work, then the design is the problem." Never relax a requirement.
- **No retries or searches.** One decision per slice.
- **Legality** may never harm the image or cost bits.
- **Still areas:** zero change, and no timed or pulsing refinement.
- **Loss recovery:** under 4 frames on both link types.
- **Latency:** at parity with JPEG XS, and under 1 ms including conversion.
- **8K** must fit today's memory.
- **Multi-frame prediction** is allowed only with compressed references that damage nothing (C2 ruling). No frame library.
- **Never modify `Project/.work/v537`.** It is today's codec, a read-only reference.

## 2. Setup (once)
```
unzip all OMC_CLOUD_part*.zip into ONE folder (they share the OMC_CLOUD/ root)
cd OMC_CLOUD && bash cloud_setup.sh     # fixes paths, VMAF model path, builds today's omc_enc/omc_dec
# put the footage in place (§3), then:
bash regen_today.sh                     # rebuilds today's real decodes (the comparison baseline) from bundled bitstreams
```
Requirements: Linux, python3 with numpy, gcc and make, and ffmpeg built with libvmaf. The VMAF-NEG model is bundled in `vmaf_model/`. Scripts use absolute paths; `cloud_setup.sh` rewrites the original `/home/dan/Documents/Apps/Codec/Project` to this folder's `Project/`.

## 3. Footage (supplied by the owner)
Raw 10-bit 4:2:2 planar little-endian .yuv, full frames (never crop; other sizes are made by Lanczos resampling).

Put the files at these exact paths:
- **Test cells:**
  - `Project/.work/arms/dng_1280x720_422_10.yuv`
  - `Project/.work/arms/dng_1920x1080_422_10.yuv`
  - `Project/.work/arms/cf_gfx_448x256_422_10.yuv`
  - `Project/.work/arms/long/spotrobotL_1920x1080_422_10.yuv`
  - `Project/.work/arms/long/floorballgameL_1920x1080_422_10.yuv`
  - `Project/.work/arms/long/highwaydriveL_1920x1080_422_10.yuv`
  - `Project/.work/arms/long/volleyballgameL_1920x1080_422_10.yuv`
- **Table-training clips** (disjoint from the test cells):
  - `Project/.work/arms/cityalley_1920x1080_422_10.yuv`
  - `Project/.work/arms/bosphorus_1920x1080_422_10.yuv`
  - `Project/.work/arms/readysetgo_1920x1080_422_10.yuv`
  - `Project/.work/arms/long/trafficlightsL_1920x1080_422_10.yuv`
  - `Project/.work/arms/long/winterdriveL_1920x1080_422_10.yuv`
- **Format checks** (optional, but needed for the full sweep): `dng_1920x1080_{422_8,422_12,444_10,444_12,444_8}.yuv`, `dng_3840x2160_422_10.yuv`, `dng_7680x4320_422_10.yuv`, `*L_1920x1080_444_12.yuv`, `*L_3840x2160_444_12.yuv`.
- **Bundled already** (no action): the synthetic rail extremes `Project/Subagents/SA7_legality_v2/arms/cut24.yuv` and `ext_{8,10,12}_{422,444}_l{0,1}.yuv`.
- **Also supply** (older scripts use it): `Project/Subagents/SA7_legality_v2/arms/dngL_1920x1080_422_10.yuv`.
- **Excluded content** (do not use): soccer, soccer2, officewalk.
- **Not bundled, not needed:** old-codec gate harnesses referenced by a few legacy scripts (`.work/sandbox/harness`, `.work/v536`, `Agents/Agent3`); they belong to the abandoned patched-legality work.

Generated test content is made by scripts in the designer sandboxes: the rail extremes cut24/ext10 (SA13/SA15), still and "frozen" clips, the mixed still/moving clip (SA18), and floor720 (a Lanczos 720p of floorballgameL).

## 4. Instruments
- `Project/Subagents/shared_tools/`: the owner's tools, used UNMODIFIED:
  - `negscore.sh REF DIST W H FMT DEPTH NFRAMES` (VMAF-NEG);
  - `smudgegroups.py` and `artifactmap.py` (run the latter with `--plane Y`, `--plane Cb` and `--plane Cr`);
  - `flatplane.py`, `rowphase.py`, `texstat.py`, `planepsnr.py`, and the render tools.
- **Today's real decodes** (after `regen_today.sh`): `Project/Subagents/SA7_legality_v2/out/DM/*_a0.d.yuv` (dng720, dng1080, spot, gfx) and `Project/Subagents/SA15_design/out/today/*.d.yuv` (floor, hwy, volley).
- **Designer models** (numpy):
  - `SA15_design/notes`, `SA16_design/model`, `SA17_design/model`, `SA18_design/bench`, `SA19_design/bench`;
  - trained tables `*.pkl` alongside them.
  - Reproduce a known result before trusting any bench, e.g. SA17's dng720 @0.5 VMAF-NEG 88.97 (worst 88.10).
- **Records:** `Project/Codec/Current/LEDGER_SANDBOX_v2.md` (grep it; the pack already contains all of it that matters) and `Project/Communication/202600927/` (the expert answers).

## 5. Working rules for the cloud session
- Keep a `RESUME.md` in your working folder, updated after every finished item.
- Run long batches detached with nohup, at most 6 in parallel (each 1080p job uses about 2.6 GB of RAM).
- Delete large .yuv files after scoring.
- Write your results and design so they can be brought back and merged into the project records: one folder per group, with RESUME.md, DESIGN.md and a log.
