## §8.8b (g) Steps at control-point phase — the number, and the renders

**The number** (`notes/phase.py`): mean `|decode − source|` in the columns at control-point phase
(`x ≡ 0 mod 64` luma, `mod 32` chroma) against mid-span phase (`x ≡ 32`, resp. `16`), frame 8.
A ratio above 1 means the error is larger where the control points sit.

| cell | arm | Y cp/mid | Cb cp/mid | Cr cp/mid |
|---|---|---|---|---|
| spotrobotL | base | 1.032 | 0.995 | 0.946 |
| | B legality | **1.049** | 0.980 | 0.930 |
| | C texture | **1.052** | 0.976 | 0.925 |
| dng 720p | base | 1.005 | 0.973 | 0.973 |
| | B legality | 1.017 | 0.964 | 0.978 |
| | C texture | **1.031** | 0.959 | 0.963 |

The base already sits at 1.03 / 1.01 on luma — the 64-column phase is not special in the shipped
codec — and the field adds **+0.017 to +0.026** to that ratio on luma while *lowering* it on
chroma. So there is a small, measurable luma excess at control-point phase, of the order of 2 % of
the local error, and no chroma excess at all. **This is a number, not a verdict.** By the owner's
ruling the eye decides, and the renders carry the grid for exactly that:

* `renders/spot_f8_field_a{0,2,3}_lvl_{Y,Cb,Cr}.png` and `..._absdiff_{Y,Cb,Cr}.png`
* `renders/dng720_f8_field_a{0,2,3}_lvl_{Y,Cb,Cr}.png` and `..._absdiff_{Y,Cb,Cr}.png`
* baseline pair `renders/{spot,dng720}_f8_grid_*` (frozen base, same marking)

green 1-pixel lines at every 64 luma columns (32 chroma) and at every slice boundary.

**What I see.** In `spot_f8_field_a2_lvl_Y.png` the new saturated bands run horizontally and cross
several grid cells; their ends do not sit on grid lines. In the `absdiff` maps the error still
traces the picture's own edges (railings, treads, panel edges) exactly as it does in the base. **I
cannot see a step at control-point phase in any plane of either cell** — but the field's *other*
damage (the new smudge bands, §8.4) is plainly visible, and that is what would fail the eye here,
not a boundary step. The continuity construction appears to do its job; the field's problem is not
where it changes, it is that it changes anything.
