# Reproducing SA20 (DESIGN.md)

Everything needed to regenerate every number in DESIGN.md is in this bundle, the owner's project zip and the owner's
footage. Nothing else is used.

## 1. Environment
- Linux, Python 3 with numpy and pillow (`pip install numpy pillow`). No other Python packages.
- ffmpeg with libvmaf (a static build, e.g. the BtbN "linux64-gpl" build; the distro ffmpeg lacks libvmaf).
- The owner's project zip unpacked so that `/home/user/fromscratch/OMC_CLOUD/` holds CLOUD_README.md, cloud_setup.sh,
  Project/ and vmaf_model/ (the scripts use this absolute root; to move it, change the path constants at the top of
  each script). Run `cloud_setup.sh` (it unpacks today's v537 binaries to Project/.work/v537).
- This bundle unpacked as `OMC_CLOUD/Project/Subagents/SA20_design/` (bench/, tools/, queues/, history/).
- Owner's footage PNGs in `OMC_CLOUD/footage_in/` named `<clip>_frameNNN.png` (clips: cine_4k_A006, cine_A005C021,
  cine_A005C031, gfx444_B001C001, gfx444_F003C012, prores_sample; 2-3 frames each).

## 2. Clips
    cd OMC_CLOUD/footage_in
    for c in cine_4k_A006 cine_A005C021 cine_A005C031 gfx444_B001C001 gfx444_F003C012 prores_sample; do
      bash ../Project/Subagents/SA20_design/tools/conv.sh $c 1280 720 422; done
    for c in cine_A005C031 gfx444_B001C001 prores_sample; do bash ../Project/Subagents/SA20_design/tools/conv.sh $c 1920 1080 422; done
    python3 ../Project/Subagents/SA20_design/tools/make_synth.py      # frozen, noisy frozen, pans (bit-exact, seed 7)
Output: `Project/.work/arms/<clip>_<W>x<H>_<fmt>_10.yuv`. The rail extremes cut24/ext_10 ship in the pack
(Project/Subagents/SA7_legality_v2/arms/).

## 3. Today's baseline (v537, read-only binaries)
    RATES="0.5 1.0 1.5 2.0 2.5 3.0 4.0" bash tools/run_today.sh                  # test clips, 720p + 1080p
    CLIPS="cine_4k_A006 cine_A005C021 gfx444_F003C012" GEOMS=1280x720 RATES="0.5 1.0 1.5 2.0 2.5 3.0 4.0" bash tools/run_today2.sh
    CLIPS="cine_frozen10 cine_nfrozen2 cine_npan0.5s2 cine_pan0.25 cine_pan1.0" GEOMS=1280x720 RATES="0.5 2.0" bash tools/run_today2.sh
    bash tools/today_eval.sh                                                       # -> out/today_eval.txt
    python3 bench/today_perframe.py cine_4k_A006 cine_A005C021 gfx444_F003C012     # training clips, per frame
    python3 tools/today_boil.py                                                    # boil / ants of today
Decodes land in `OMC_CLOUD/scratch/today/`.

## 4. The bench (bench/)
- `n4_core.py`: the form-(i) engine `po()` (predict-only pyramid, per-sample clip; options: step map QM, hysteresis
  HT, activity output ACT, luma-guided chroma LG, reconstruction offsets RO/RS). Environment switches: RHO (leaf
  dead-zone offset, default 0.35), RHOK (kept-sample offset), RCL=1 (range-clamped interpolation).
- `d1_screen.py`: reader, dead-zone quantiser, 5/3 reference. `dp_screen_core.py`: block motion search and MC.
- Intra, real code lengths: `rcl_fi.py` (per-step tables), `rcl_ctx.py` (activity contexts), `rcl_tab.py` (table
  pooling), `rcl_sc.py` (step-invariant S16 family), `rcl_s16.py CLIP CM [S16|S16i|S16u|S16l2]` (S16, leave-one-out
  tables for training clips; env EST=1 estimate/upper bound, INSAMPLE=1, F, RHO, RHOK, RCL).
  Scored with `intra_vs_today.py LOG...` (rate-matched vs today's frame 0).
- Inter / CBR: `rcl_cbr.py CLIP ARM` (exact per-frame CBR; ARM = "_"-joined tokens, see DESIGN.md glossary; env
  NF = frames, RATES, LOO=1). `rcl_cbr.py train ARM` builds the arm's tables first.
- Diagnostics: `diag_bands.py`, `diag_feat.py`, `intra_eval.py` (smudge/texstat/features/bands per arm),
  `rail_test.py`, `downstream.py`, `diag_inter.py`; tools/diag_gfx.py, diag_noise.py, diag_res.py.
- The owner's visual tools are used unmodified from Project/Subagents/shared_tools/.

## 5. Which command produced which entry
The exact command lines of every batch are in queues/q_*.sh (one script per batch; run from SA20_design/).
| DESIGN entries | command |
|---|---|
| G1-G2, G4 | rcl_intra.py / rcl_fi.py CLIP cm<x>[_cl] ; intra_vs_today.py (queues/q_chroma.sh) |
| G7 | rcl_fi.py CLIP cm1_lg1 etc. (q_lg.sh) |
| G10 | rcl_ctx.py (q_ctx.sh) |
| G11, G24-G29, G32, G50-G68 | rcl_cbr.py (q_cbr*.sh, q_still.sh, q_rg*.sh, q_acc*.sh, q_win.sh, q_ctl.sh, q_grain.sh, q_split.sh, q_chab.sh, q_gn.sh) |
| G13 | rcl_tab.py cine_A005C031 |
| G18, G21 | rcl_sc.py CLIP [CM] (env ONLY=S16,S16i) |
| G30 | rcl_s16.py CLIP 1 S16u / S16l2 (q_s16u.sh, q_l2.sh) |
| G31 | EST=1 rcl_s16.py (q_est.sh) |
| G40-G49, G69, G73 | rcl_s16.py with RHO/RHOK/F/RCL (q_fit.sh, q_rho.sh, q_cm42.sh, q_rk42.sh, q_rcl.sh) ; intra_eval.py |
| G42-G44, G47-G48 | diag_bands.py, diag_feat.py, intra_eval.py |
| G36, G28, G37 | tools/diag_gfx.py, tools/diag_res.py, tools/diag_noise.py |
| G67, G72 | rail_test.py, downstream.py |

## 6. Code state per entry
The bench changed during the session (bugs found and fixed are recorded in DESIGN.md, e.g. G15, G37, G53). Each
DESIGN entry was committed together with the code that produced it: history/commits.txt lists every commit in order
(time, message), and history/bench_history.patch holds every change to the bench, queue and tool scripts in the same
order. To reproduce an early entry, rebuild the bench as of the matching commit from that patch history. The current
bench/ reproduces the latest entries.

## 7. Notes
- Table pickles (out/*/tables_*.pkl) are rebuilt automatically when missing (training is the slow step).
- All code lengths are ideal static-table code lengths (-log2 p, add-1 smoothing); no headers are counted except where
  an entry says so.
- Runs are deterministic (no random input except make_synth's seed 7).
