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
| C1 | chroma allocation curve (cm) + chroma-from-luma, real code | fails at 1.0-1.5 all clips (frontier ~0.1 NEG short); CfL no effect -> KILLED |
| R1 | conditional-mean leaf reconstruction (level x |q| x activity LUT) | +0.00..+0.06 dB luma -> KILLED |

## 2e. Rate points (owner, binding): 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0 bpp. 0.25 is not used (0.25/0.3 figures are
extra information only and carry no weight in a verdict). All screens and today's baseline report these points.
Rule (owner, repeated): no test point below 0.5 bpp is generated or reported; 0.25/0.3 figures earlier in this file
are superseded and carry no weight. Real-code runs keep only points with 0.5 <= bpp < 4.6.

## 3. STATUS SNAPSHOT (for the owner; details in DESIGN.md G1-G56)
Engine: form (i) "private last write": predict-only interpolating pyramid (DD4, 2 x 2-D + 3 horizontal levels, kept
coarse grid), every sample written once as clip(P + pred + leaf). Never-away holds by construction (0 oob everywhere).
What stands (measured, real static-table code lengths):
- S16 entropy model: 16 static tables shared by every step/level/plane (the context is the local |q| scale class
  from decoded neighbours + step-normalised activity from final coarser samples). Fits today's table budget (60
  tables, 1.1 Mbit) with room to spare. The left neighbour closes a per-symbol loop at 8K (S16u without it costs
  +18-32 %); a distance-2 variant is pending.
- Intra dead zone rho 0.42 (nested fit): removes the A006 smudge groups; texture at source energy (texstat).
- Intra vs today, all 6 clips (G18, G49): NEG ahead on 4 clips and near parity on A006. The G41 rule still FAILS
  cells: gfx F003 NEG @1.0/1.5; A006 NEG @2.5; chroma PSNR on A006/F003 at low-mid rates.
- 3-frame exact CBR vs today (G32): worst inter frame NEG from parity to +0.93, inter chroma -0.3..-2.1 dB.
- Still areas: churn roots found and fixed:
  - DPCM-start bug and the residual DPCM chain in inter;
  - motion search picking nonzero vectors on frozen input;
  - per-block last-write step reset by partial writes;
  - rounding slack;
  - a per-sample noise floor that interpolation amplifies -> block-level zero leaves;
  - frame-to-frame gate misses -> accumulated-since-last-write test + 3-frame hysteresis + 2-fail release.
  Frozen and noisy-frozen input now: ramp frames, ONE whole-frame catch-up, then 0.00 % changes.
OPEN (failing now):
- noisy slow pans smear (hold on low-contrast motion inside noise; NEG decays ~6 over 10 frames);
- pans: intermittent blocks 3-40 % (bound 1 %);
- gfx: region plan misallocates (still region held at frame-1 quality while moving goes very fine; whole-set catch-up
  never fits); needs per-connected-region catch-ups (b);
- exact CBR proof needs a bounded fallback plan (owner call, DESIGN G35);
- chroma-step function (nested) pending; 10-generation chains, per-slice CBR and the owner's visual tools on inter
  frames not yet run.
OWNER QUESTIONS: (1) confirm the rail-free definition of never-away (DESIGN V); (2) is a proven, never-fired
worst-case CBR plan acceptable (G35)?; (3) region-keyed steps (still vs moving) have block-shaped boundaries:
acceptable if the boundary tests pass (G39)?

## 4. Owner guidance, 2026-09-30 (working guidance for this round, NOT a rule; do not cite as one)
Never-away: proceed with the current reading (output = clip of the legality-blind value per sample, pixels needing no
fix untouched), provided the result is artifact-free. Next: rail clips (cut24, ext10) through the design with the
owner's smudgegroups/artifactmap per plane + renders; watch for the near-rail level shift.
From the record (DESIGN G35/G39 superseded): per-region parameters must be continuous fields both ends derive (owner:
"zero visible steps"), so block-keyed region steps (_rg per-region step, _rr) are dropped; a visible fallback plan
is a disqualifying artifact (S5.344), so dense rail content stays an open problem, stated as such.

## 5. OWNER RULINGS 2026-09-30 (rules)
- Lines, grids and seams are disqualifying in absolute terms; today's codec is no baseline for them.
- No patches: when an idea or feature fails, redesign from scratch further upstream.
- Latency: no noticeable increase over JPEG XS (~32 lines excl. conversion, < 1 ms incl.).
- Byte-exact across UNLIMITED generations (pictures and bits), proven by construction; a rate change may cost once, then the chain is a fixed point (no drift).
- Never-away: "Go with what the engineer would accept": legal output, no bit or quality cost from legality, no
  visible effect of any legality move on the hardest cases (renders), worst-case move size reported (DESIGN H21).
- Sub-agents generate their own ideas, vet mine and each other's.
