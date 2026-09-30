# CLP-1 — revision 5 (response to the review of DESIGN_v4)

**SA12, 2026-09-27.** This revision builds on revisions 1–4; what is not changed stands.

- **Owner's decision applied:** the cross-slice vertical transform (revision 4, option b) is out.
- **Scope of the numbers:** everything is the sequence model (`notes/seq.py`), not a codec build. Rates are **coded**: model entropy × the static-tANS overhead model `notes/cost2.py`.
- **Final configuration:**
  - overlapped-block MC;
  - MC context below the slice;
  - encoder error continuation;
  - clean-region refresh rules (contiguous sweep);
  - gen-1 self-read (§3).
- **Metric used throughout:** "excess" = mean |error step| at the slice boundary minus that at the internal half-slice row, relative to the other rows. **0 = the internal-boundary floor.**

---

## 1. Error continuation on INTRA slices (measured, frame 8 coded intra)

Continuation reads only the slice above in the same frame, which the decoder already has. It is therefore loss-safe (A5) and exactness-safe, as on inter slices (`out/v5/intraA.txt`, `intraB.txt`).

- Fade = the number of rows the previous slice's low-frequency error is carried into.
- Weight = the starting fraction of that error.
- Intra NEG is one intra frame. The entropy rate is the same across variants to within 0.3 %.

| cell (slice height) | continuation (fade, weight) | **intra NEG** | PSNR Y/Cb/Cr | intra boundary excess Y/Cb/Cr |
|---|---|---|---|---|
| spot 1080p (16) | off | **91.90** | 41.23/42.76/46.21 | +0.16/+0.18/+0.32 |
| | 4, ½ | 91.75 | 41.23/42.76/46.19 | +0.14/+0.15/+0.28 |
| | 8, ½ | 91.62 | 41.22/42.74/46.16 | +0.14/+0.14/+0.25 |
| | 4, 1 | 91.53 | 41.21/42.73/46.15 | +0.13/+0.13/+0.24 |
| | 8, 1 | 91.21 | 41.17/42.65/46.03 | **+0.12/+0.12/+0.21** |
| | 16, 1 | 90.81 | 41.09/42.50/45.83 | +0.12/+0.11/+0.19 |
| spot 1080p (8) | off | 91.92 | 41.20/42.76/46.18 | +0.15/+0.14/+0.28 |
| | 8, 1 | 90.60 | 41.06/42.53/45.83 | +0.12/+0.10/+0.19 |
| dng720 (8) | off | 91.46 | 38.25/36.93/37.95 | +0.07/+0.07/+0.07 |
| | 4, ½ | 91.12 | 38.24/36.92/37.94 | +0.06/+0.06/+0.06 |
| | 8, ½ | 90.94 | 38.23/36.90/37.93 | +0.06/+0.06/+0.05 |
| | 4, 1 | 90.72 | 38.22/36.89/37.91 | +0.05/+0.05/+0.05 |
| | 8, 1 | 90.15 | 38.17/36.82/37.84 | +0.05/+0.05/+0.04 |
| cf_gfx (8) | off | 92.83 | 36.94/36.05/36.42 | +0.07/+0.10/+0.12 |
| | 8, 1 | 91.70 | 36.89/35.94/36.30 | +0.06/+0.08/+0.10 |

**Reading.**
- On intra slices continuation removes a quarter to a third of the step.
- It costs intra VMAF-NEG: −0.15 to −1.3 depending on strength.
- It never reaches the floor.
- On inter slices the same element costs little and reaches +0.03…0.08 (§2, revision 3).
- **Default:** fade 4, weight 1 on intra slices (spot −0.37 NEG, dng720 −0.74 NEG, on intra frames only; in steady state only the refresh group, 1/8 of the frame, is intra); fade 8, weight 1 on inter slices.

## 2. Option (a): 8-row slices at 1080p (measured, spot, 12 frames, final configuration)

| slice height | coded bpp | **VMAF-NEG f2–11** | PSNR Y/Cb/Cr | inter excess Y/Cb/Cr | intra excess (§1, off / 8,1) | latency (lines, 1080p) |
|---|---|---|---|---|---|---|
| 16 | 0.413 | 92.17 | 40.03/42.14/45.48 | +0.04/+0.03/+0.08 | +0.16/+0.18/+0.32 → +0.12/+0.12/+0.21 | 34 (0.50 ms at 60p) |
| 16 | 0.538 | 94.47 | 41.30/42.88/46.33 | +0.04/+0.03/+0.06 | | |
| **16 @ 0.5** (interpolated) | 0.500 | **≈ 93.83** | ≈ 40.95/42.68/46.09 | | | |
| 8 | 0.428 | 91.41 | 39.87/42.02/45.30 | +0.07/+0.04/+0.08 | +0.15/+0.14/+0.28 → +0.12/+0.10/+0.19 | **18 (0.27 ms)** |
| 8 | 0.555 | 93.94 | 41.16/42.78/46.16 | +0.05/+0.03/+0.07 | | |
| **8 @ 0.5** (interpolated) | 0.500 | **≈ 92.93 (−0.9)** | | | | |

**Reading.** At 1080p, 8-row slices cost about 0.9 NEG (≈ +4 % bits at equal Qf) and do **not** reduce the boundary step. The step is set by content, not by slice height: dng720 at 8 rows shows +0.07 because its content is smoother. The latency gain (34 → 18 lines) is real but not needed, since 16 rows already sits at XS parity. **Option (a) is not taken.**

Today real at 0.5 bpp on spot: NEG 93.76, PSNR 39.54/42.80/46.31. With the clean-region rules and the self-read now in, CLP at 0.5 is ≈ 93.83 NEG: parity on NEG, +1.4 dB luma, −0.12/−0.22 dB chroma. The earlier +0.3 NEG was measured without the clean-region rules; they cost ≈ 0.2 NEG.

## 3. Gen-1 self-read and T8 byte comparison (measured)

**The rule** (`SEQ_SELFREAD`). After coding a slice inter, gen 1 checks whether intra coding of the slice's own reconstruction reproduces it exactly. If it does, gen 1 emits the intra description.

- This is the same rule the joining encoder applies to its input, so both encoders choose the same description.
- The joiner learns the sweep phase from the group whose slices are **all** intra, preferring the one that follows the previous phase. A lone static slice read as intra therefore cannot mislead it.
- In the model the check is a trial intra pass. In hardware it is the one-pass divisibility read (revision 2 §1, item 5).

**T8, re-run** (spot 1080p, 24 frames, per-slice md5 of every index array + the intra/inter flag, all planes, `notes/joincmp.py`):

| join at | slices identical per frame (picture / symbols of 68) | byte-identical from |
|---|---|---|
| 3 | f8 9/10, f10 27/27, f12 45/45, f14 63/63, **f15–f23 68/68** | **frame 15 to the end** |
| 7 | f8 12/13, f10 27/30, f12 45/46, f14 63/63, **f15–f23 68/68** | **frame 15 to the end** |

The frame-16 equivalent-description case of revision 4 is gone. **Pictures and coded streams are byte-identical from the first frame of full convergence to the end of the sequence.** The lock bound is one refresh cycle after the next cycle start (≤ 16 frames).

## 4. The intra step that remains, and renders for the owner's eye

**Plainly:** after revision 5 the boundary step over the internal floor is:

| slices | cell (slice height) | step, Y/Cb/Cr |
|---|---|---|
| intra (default continuation) | spot 1080p (16) | **+0.13/+0.13/+0.24** |
| intra | dng720 (8) | **+0.05** |
| intra | cf_gfx (8) | **+0.06/+0.08/+0.10** |
| inter | spot | +0.04/+0.03/+0.06…0.08 |
| inter | dng720 | ≈ +0.04/+0.03/+0.02 |

- Rates: spot around 0.5 bpp; dng720 and cf_gfx at the intra-frame rates of §1.
- **For comparison, today's codec (real decodes):** spot 0.5 inter +0.15/+0.14/+0.30; dng720 +0.05/+0.04/+0.05.
- In steady state the intra rows are one refresh group per frame (1/8 of the frame, moving top to bottom), plus frames 0–1 and cut frames.

**Measured on the refresh group in steady state** (dng720, 8-row slices, final configuration, `out/v5`). Excess at the two boundaries of the refresh group only (a small sample, 2 boundaries), against all boundaries of the frame:

| frame | refresh group | its 2 boundaries, Y/Cb/Cr | all boundaries, Y/Cb/Cr |
|---|---|---|---|
| 9 | group 1 (rows 96–191) | −0.06/−0.05/+0.03 | +0.04/+0.03/+0.02 |
| 10 | group 2 (rows 192–287) | +0.01/+0.08/+0.10 | +0.04/+0.03/+0.03 |
| 11 | group 3 (rows 288–383) | +0.05/+0.05/+0.10 | +0.04/+0.03/+0.01 |

**Renders for the eye:** `out/eye_refresh/` (60 PNGs).
- The owner's marked 720p cell (dng720), final configuration with the refresh sweep, against today's real 0.5-bpp decode.
- **Frame 11: the refresh group sits mid-frame, rows 288–383.** Frame 8: the refresh group is at the top.
- Per decode and frame: colour decode, level maps per plane (8×8 block mean of decode − source, red/blue at ±10 codes), and |decode − source| ×8 per plane. Each is plain and `_grid` (8-row slice lines, 32/16-column lines).
- Dark areas: mean signed chroma error −0.02…+0.03 Cb, +0.01/−0.07 Cr (today +0.22/−0.15). No cast.

## 5. Status against the owner's list

| Goal | Status (model) |
|---|---|
| 1. No seams or smudges | **Smudges:** 0 % grille classes (today 13–14 %). **Inter seams:** +0.03…0.08, against today's +0.14…0.30. **Intra seams:** spot +0.13/+0.13/+0.24, dng720 +0.05, cf_gfx +0.06…0.10. Intra NEG cost is −0.37 (spot) / −0.74 (dng720) on intra frames. **Not zero.** Renders for the eye are in `out/eye_refresh/`. |
| 2. Legal by construction | Holds; 0 out-of-range in every run |
| 3. Byte-exact generations | Gen-2 identity in every configuration tested. **Mid-stream join with motion: pictures and streams byte-identical from frame 15 to the end (joins at 3 and 7).** |
| 4. No more bits than today | At 0.5 bpp coded: NEG dng720 +1.1, spot ≈ +0.1, highwaydriveL +0.2. Luma +1.0…+2.1 dB. Chroma −0.2…+0.5 dB. |

## 6. Weakest point

**The intra-slice step.** It is +0.13/+0.13/+0.24 on spot at 16 rows, over the internal floor, per plane. That is lower than today's inter +0.15/+0.14/+0.30, but it is on every intra slice: ramp and cut frames, and the moving refresh group. None of the latency-free legal remedies tested removes it:

| Remedy | Result |
|---|---|
| Below-context | Last-row magnitude only |
| Anchor bracketing | Worse |
| 8-row slices | No gain, −0.9 NEG |
| Error continuation | −25…35 % step, at an intra NEG cost |

Whether the remaining step is visible is for the owner's eye on `out/eye_refresh/`. Second: spot chroma PSNR at 0.5 bpp is −0.1/−0.2 dB against today, with the clean-region rules on.

## 7. Files (new in revision 5)

- `notes/seq.py`, with `SEQ_SELFREAD`, `SEQ_CW` and the robust phase rule.
- `notes/intrastep.py`: single-frame and refresh-group step.
- `out/v5/`: intraA/B, B_sh8/16, C_g1/j3/j7, D_d720.
- `out/eye_refresh/`: renders.
