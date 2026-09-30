# §14. L-I26 step 0 — the cross-slice `d[−1]` term into the level-1 vertical UPDATE (d1m = 0 arm)

**Why this came first.** The IP reviewer's correction is right and I verified it in the code: two
different things are called XSL. The *interior boundary edit* is dormant (`omc_xsl_loopfree` defaults
to 1, so it runs as the display blend). The **cross-slice `d[−1]` term into the level-1 vertical
update is LIVE**: `xsl_prep` fills `xsl_buf` and sets `xsl_live` unconditionally apart from
refresh-barrier returns, and three sites pass it into the transform. The predict-only transform
deletes the update and therefore deletes this term, so its cost had to be measured before anything
else.

**The three sites** (frozen base `.work/v537`, sandbox copy `ptree5`):

| site | `src/codec.c` | what it is |
|---|---|---|
| 1 | ~4111 | the **prediction's** forward transform, `omc_slice_fwd_p(pbuf, …)` |
| 2 | ~5185 | `reconstruct_slice`'s inverse, `omc_slice_inv_p(sbuf[p], …)` — used by **both ends** |
| 3 | ~6028 | the **encoder's source** forward transform |

The probe `[SA7-D1M0]` routes all three through one helper `d1m_of()` which returns 0 when
`OMC_D1M0=1`. Because site 2 is shared, the probe applies at both ends automatically.

**Discriminators.** Unset: stream byte-identical to the frozen base (dng 720p, 12 frames, `cmp`
rc 0). Armed: the stream differs. Exact CBR holds on every arm (byte counts identical between arms
at every cell and rate). Build: 0 warnings.

## §14.1 What moves — per-plane PSNR, 12 frames, equal CBR

| cell | bpp | term ON (shipped) Y/Cb/Cr | **term = 0** Y/Cb/Cr | **Δ Y/Cb/Cr** | **worst-frame ΔY** |
|---|---|---|---|---|---|
| dng 720p | 0.5 | 34.788 / 35.998 / 37.033 | 34.622 / 35.977 / 37.017 | **−0.166** / −0.020 / −0.016 | **−0.290** |
| dng 720p | 1.0 | 37.980 / 37.017 / 37.898 | 37.960 / 37.003 / 37.896 | −0.020 / −0.013 / −0.002 | −0.070 |
| dng 1080p | 0.5 | 35.101 / 34.629 / 35.712 | 35.075 / 34.620 / 35.706 | −0.026 / −0.009 / −0.007 | −0.130 |
| dng 1080p | 1.0 | 36.852 / 35.973 / 36.698 | 36.850 / 35.973 / 36.696 | −0.002 / +0.000 / −0.002 | −0.020 |
| **spotrobotL** | 0.5 | 39.491 / 42.636 / 46.103 | 39.034 / 42.643 / 46.102 | **−0.457** / +0.008 / −0.001 | **−2.890** |
| **spotrobotL** | 1.0 | 43.028 / 44.696 / 48.057 | 43.084 / 44.688 / 48.060 | +0.056 / −0.008 / +0.003 | **−3.690** |
| cf_gfx | 0.5 | 29.657 / 33.347 / 33.343 | 29.537 / 33.318 / 33.323 | **−0.120** / −0.028 / −0.020 | −0.430 |
| cf_gfx | 1.0 | 33.959 / 34.602 / 34.676 | 33.939 / 34.598 / 34.682 | −0.020 / −0.005 / +0.007 | −0.220 |

**The term is not free.** Removing it costs **−0.17 dB** luma mean on dng 720p @0.5, **−0.46 dB** on
spotrobotL @0.5, and **−0.12 dB** on cf_gfx @0.5 — all above the 0.1 dB bar. The **worst frame** is
where it really shows: **−2.89 dB** on spotrobotL @0.5 and **−3.69 dB** at 1.0, on a cell whose mean
barely moves. A mean that is flat while the worst frame falls 3.7 dB is exactly the shape the
mandate's "worst frame decides" rule exists to catch.

## §14.2 The seam — row bias at rows 13–15 (Y), term ON → term 0

| cell | bpp | inner | r13 | r14 | **r15** |
|---|---|---|---|---|---|
| dng 720p | 0.5 | +0.003 → +0.032 | +0.197 → +0.127 | −0.153 → −0.206 | **−0.344 → −0.452** |
| dng 720p | 1.0 | −0.055 → −0.014 | +0.075 → +0.031 | −0.047 → −0.070 | −0.183 → −0.175 |
| dng 1080p | 0.5 | −0.007 → +0.042 | −0.061 → −0.064 | −0.023 → −0.033 | −0.287 → −0.222 |
| spotrobotL | 1.0 | **−0.038 → −0.183** | **−0.280 → −0.422** | **−0.233 → −0.380** | +0.038 → −0.075 |
| cf_gfx | 0.5 | −0.091 → −0.037 | −0.002 → **−0.532** | −0.515 → −0.449 | **−1.686 → −1.452** |

Mixed and small in absolute terms (all under 0.5 codes except cf_gfx's row 15), but **it moves**:
the last-row bias grows on dng 720p @0.5, the interior and rows 13–14 grow on spotrobotL @1.0, and
cf_gfx's row 13 goes from −0.002 to −0.532. The phase statistic at the slice grid moves too
(dng 720p Y cp/mid 1.0046 → 1.0066). **The term is doing seam work, not only rate work.**

Energy-meter flat share (a number, not a verdict): moves by −2.7 to +3.7 points, no consistent
direction.

**Renders** (unmarked **and** `_grid`, every plane, frame 8, slice grid marked):
`renders/DM_dng720_f8_{d1m_on,d1m_off}_{lvl,absdiff}_{Y,Cb,Cr}.png`. The level-map block-mean range
widens **−24.1 … +22.0 → −27.5 … +26.6** and the worst sample error **301 → 356**.

## §14.3 Verdict, and what it does to the predict-only budget

**Something moves, so by the coordinator's own rule the cost enters the predict-only budget:**
up to **−0.46 dB mean / −3.7 dB worst frame**, plus a measurable seam movement. The term cannot
simply be deleted with the update.

**And under predict-only there is no analogue of it**, which is the structural point. The shipped
term supplies `d[−1]` — the *highpass* of the previous slice's last pair — to the **update** at
`i = 0` (`dl = (i>0) ? H[i−1] : (use_dm1 ? dm1 : H[0])`, `src/dwt.c:173`). With no update there is
no `d[−1]` and nothing to feed. The top of the slice needs no cross-slice predict either: under
predict-only row 0 is an **even** (a lowpass sample on every grid) and row 1's predict reads rows 0
and 2, both inside the slice. So the shipped mechanism has no predict-step form at the same place.

### The predict-step form I would design instead, and what it costs

The information the term carries is *vertical continuity across the seam*, and under predict-only
the place that information is missing is the **lowpass**: row 0 of slice *k* is coded as an LL
sample with no vertical predictor at all, while every other LL row is predicted horizontally
(the shipped LL DPCM). The causal, exact, both-ends form is therefore:

> **Cross-slice LL predictor.** For the first LL row of slice *k* (source row 0), predict each LL
> sample from the **committed** LL-grid sample directly above it in slice *k−1* (source row
> `k·sh − 4`, the last LL row of the previous slice), and code the difference. Both ends hold that
> sample exactly (it is committed before slice *k* is decoded); the predictor is one subtract; it is
> causal, adds no latency and no state beyond one row already resident.

* it replaces a vertical predictor the shipped tree gets from the *update*, with one the
  predict-only tree gets from the *lowpass*, at the same boundary;
* it is exactly the shape of the existing LL DPCM (BITSTREAM §4.3, "horizontal first-order
  differences, predictor reset to 0 at the start of each band row") extended to the first row's
  vertical neighbour, so it costs one normative sentence and no new syntax;
* **cost:** one subtract per LL sample of one row per slice — `W/32` samples, i.e. 60 at 1080p:
  arithmetically free;
* **what it cannot recover:** the shipped term also feeds the *interior* rows' update through
  `H[i−1]` propagation, which is why spotrobotL's worst frame moves by 3.7 dB. A first-row LL
  predictor addresses the seam, not the interior. **I would not claim it recovers the full
  −0.46 dB, and the oracle must measure it rather than assume.**

**Recommendation before the transform probe proceeds:** carry **−0.17 to −0.46 dB mean and up to
−3.7 dB on a worst frame** as a standing debit against predict-only, and treat the cross-slice LL
predictor as a required part of the design rather than an optimisation — with its own arm in the
compression gate, because on this measurement predict-only starts the 0.1 dB bar already behind.
