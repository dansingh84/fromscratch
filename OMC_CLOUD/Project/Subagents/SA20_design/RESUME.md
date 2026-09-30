# SA20 RESUME (cloud session, started 2026-09-30 02:13 UTC)

## 0. Group
SA20 = designer (main session). SA20P, SA20Q = ideation (Opus 5.5), roles per LAUNCH_INSTRUCTIONS §2-§4 (SA19* -> SA20*).
Log: GROUP_LOG.md. Priority (CLOUD_README §1.3, HANDOFF §10.2): first adversarially verify S5.404 never-away verdict,
then an engine where never-away holds by construction at zero efficiency cost; all four goals; legality first.

## 1. Environment (cloud)
- 4 CPUs, 15 GB RAM -> at most 4 parallel 720p jobs, 2-3 at 1080p (README says 2.6 GB per 1080p job).
- numpy 2.4 (pip). ffmpeg with libvmaf = static BtbN build /usr/local/bin/ffmpeg (Ubuntu ffmpeg has no libvmaf).
- cloud_setup.sh done (paths rewritten, omc_enc/omc_dec built).

## 2. Footage (owner, 2026-09-30; NOT the clips named in CLOUD_README §3)
Source: PNG frames (RGB; owner: lossy-compressed originals), converted by footage_in/conv.sh:
BT.709 matrix, limited range, Lanczos (full frame, no crop), raw planar 10-bit LE, into Project/.work/arms/.
| clip | native | frames | mean|dY| f->f (720p) | still frac | role |
|---|---|---|---|---|---|
| cine_4k_A006 | 4096x2160 8-bit | 2 | 60.6 (near cut) | 0.017 | TRAIN |
| cine_A005C021 | 2048x1152 16-bit | 2 | 8.8 | 0.089 | TRAIN |
| gfx444_F003C012 | 4480x1856 8-bit | 3 | 13.1/14.0 | 0.09 | TRAIN |
| cine_A005C031 | 2048x1152 16-bit | 3 | 8.1/8.1 | 0.096 | TEST |
| gfx444_B001C001 | 1920x1080 16-bit | 3 | 1.5/1.6 | 0.22 | TEST (also 4:4:4 1080p) |
| prores_sample | 2048x1152 16-bit | 3 | 3.9/3.9 | 0.13 | TEST |
Sizes made: 1920x1080 and 1280x720 4:2:2 10-bit for all; gfx444_B001C001 1920x1080 4:4:4 10-bit.
Limits: 3 frames -> steady state = frame 2 only (worst frame = that frame); no long motion cells; old bundled
today-decodes (dng/spot/floor/...) cannot be scored (their sources are absent) -> today's baseline is re-made
with v537 on the new clips (scratch/today/).
Rails: synthetic rail extremes bundled (cut24, ext_*) are used unchanged.

## 3. Items
| id | item | result |
|---|---|---|
| E0 | pipeline check: v537 prores_sample 720p @0.5, 3 frames | NEG 92.238 (all 3 frames); 172,832 bytes = 0.500 bpp |

## 2b. Owner note (2026-09-30): 3 frames are too few for the codec to build up to its steady quality
Absolute figures on these clips sit below what the codec reaches on long clips. Use them only as RELATIVE
comparisons (candidate vs today on the same 3 frames, same rate); never quote them as steady-state quality.

## 2c. Owner directive (2026-09-30, binding)
Build FROM SCRATCH. Earlier agents failed; their work shows which choice caused which effect, and is NEVER a frame
of thinking to adopt or adapt. Rethink, don't adapt; an element earns its place only from first principles, with
the risk named that it leads down the same failed path. Always meet PROJECT_CONSTRAINTS and never repeat a
falsified idea (pack §13/§14, SA19 §L, DESIGN §E). 3-frame clips never reach the temporal build-up: read absolute
scores accordingly.
Status: S5.404 verified (DESIGN §V); D1 and D-P screened dead (DESIGN §E). Next: first-principles engine round
(3 directions each from SA20P/SA20Q + own, DESIGN §F).

| E1 | D1 slack-read Laplacian, intra proxy | -1..-11 dB vs 5/3 at 0.5 every arm -> KILLED |
| E2 | D-P predict-only on e = x - P, 3-frame proxy | frame-2 NEG -0.3..-4.0 @0.25/0.5 -> KILLED (pre-agreed rule) |

## 2d. Benchmark = today's codec on OUR clips (owner, 2026-09-30)
The documentation's figures do not apply to these clips. Every comparison uses v537 (read-only binaries) run on the
same 3-frame segments: out/today_eval.txt (720p + 1080p, 0.3/0.5/1.0 bpp, frame-2 NEG + PSNR Y/Cb/Cr; per-frame
NEG kept). Intra comparisons use today's frame 0 (exact CBR: 5,120 bits/slice x 90 slices = 0.5 bpp per frame).
Watchdog: 5 session crons (efcae82a, 4105dbfc, 4112b1a7, 1fd074af, 4f045645) = one check every 25 min
(one short gap at midnight); each pings SA20P/SA20Q and checks my own jobs; they expire after 7 days / with the session.
| N1 | causal 2-D intra (B=8) + block-local private pyramid, proxy | -3.2..-12.6 dB vs 5/3 at every rate -> KILLED |

## 2e. Rate points (owner, binding): 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0 bpp. 0.25 is not used (0.25/0.3 figures are
extra information only and carry no weight in a verdict). All screens and today's baseline report these points.
