# LEDGER — OMC-1 v5.3.5 (the development ledger of the v5.4 effort, released as the v5.3.5 baseline on 2026-09-06)

**Brief:** `Prompts/Prompt_08302026.txt`. **Baseline:** `Codec/Current/omc_v5.3_20260830-1.zip`
(stream major 5, minor 13), built and gated from a fresh unzip on this machine: `make` clean,
`make test` **97 `ok:` assertions, 6/6 suites, rc 0**.

**Where this ledger lives:** the working copy is `.work/ledger54/LEDGER_v5_4_DRAFT.md`; it is published unchanged to `Codec/Current/LEDGER_v5_4.md` by `.work/ledger54/publish.sh` after every update (owner continuity rule 21). The structural / engine-replacement track is recorded in a SEPARATE document, `Codec/Current/LEDGER_SANDBOX.md`, and lives in `.work/sandbox/`; this ledger only names it and never merges it (ruling 20/21).

**Governing documents, read in full this session:** `PROJECT_CONSTRAINTS.md` (rev 6),
`LEDGER_v5_3.md` (all 56,598 lines), `A1_MEANS_2026-08-30.md`.

**Owner rules recorded this session (2026-08-31), binding on everything below:**
1. *For task C (A1), also read `A1_MEANS_2026-08-30.md`* — done, summarised in §C.
2. *"Don't focus on a crop of the frame only... Review full frames. Same applies to subsequent
   frames... And you might be fixing one type of footage but breaking other kinds. You have to
   look at context — not just one specific detail."* Every measurement below is full-frame, is
   taken over all 12 frames of the arm (never one frame), and every candidate is measured on
   every clip of the corpus before any verdict.
3. *"Whenever you get an idea for how to fix a problem, review the ledger and the codec's
   documentation (both OMC and HVBC) so that you don't waste time and tokens on something that
   has already been falsified."* Every candidate section below opens with its record check.

## 0. Reproduction

Everything below reproduces from this document + the v5.3 zip + `Footage/`. Working root is
`Project/.work/`; the v5.3 tree is `.work/v53/omc_v5.3`.

### 0.1 The corpus, byte-verified against the shipped provenance chain

| step | command | verification |
|---|---|---|
| dng master | `unzip DNG/260806_171716_VIDEO_14mm.zip frame0000{00..11}.dng; prep_master.py dng <dir> 12 masters/dng_3840x2160_444_12.yuv` | frame prints 3840x2160 x12 |
| yuv masters | `7z x <clip>_3840x2160_*_420_10bit_YUV_RAW.7z; prep_master.py yuv420 <in> 3840 2160 10 12 masters/<clip>_3840x2160_444_12.yuv` | bosphorus / cityalley / readysetgo |
| arms | `derive.py masters/<clip>_3840x2160_444_12.yuv 3840 2160 <W> <H> <fmt> <depth> 12 arms/<name>.yuv` | |
| cf_gfx | 448×256 crop of `arms/dng_1920x1080_422_10.yuv` at (row 400, col 800), luma-aligned chroma | **6-frame prefix SHA-256 = `359c9599…` — byte-identical to `delivery/conformance/expected/cf_source.sha256`** |
| frozen_* | frame 0 of each 1080p arm repeated ×12 (crawl instrument: source tail 0 by construction) | |
| baseline sanity | v5.3 `dng@0.5`, 6 frames → **NEG 88.971** | = ledger v5.3 §55.8d exactly |

### 0.2 Instruments

All from the v5.3 zip's `harness/` (shipped, unmodified): `negscore.sh` (format-correct VMAF-NEG,
equal lengths), `blotch.py` (G7, `--sh` from the stream header byte 12), `flatplane.py` (G4 per
plane), `pitch.py` (seam periodicity per plane vs source null), `tests/ants.py` (crawl, frozen
masters). Environment: gcc 16.2.1, ffmpeg 8.1.2, libvmaf `vmaf_v0.6.1neg` (luma-only by
construction), scratch on /home, one encode chain at a time.


---

# B1. FLATNESS AT MID AND HIGH RATES — the fill divisor's rate rung (v5.4)

## B1.0 The finding that opened it

The brief requires the full-gamut test: *"run a full gamut test to see if [the artifacts]
manifest themselves at higher bitrates as well, which is equally (if not more) important."*
They do. The 12-frame full-gamut baseline (§A.2) shows the flatness class — declared
"essentially MET" at 0.5 bpp by the v5.3 ledger — broadly UNMET at 1.0–4.0 bpp:

| cell (v5.3 defaults) | flat f3 Y/Cb/Cr % |
|---|---|
| `cityalley@1.0` | **9.18 / 31.91 / 20.88** |
| `bosphorus@1.0` | 6.33 / 11.31 / 5.50 |
| `cityalley@2.0` | 5.43 / 8.96 / 8.71 |
| `bosphorus@2.0` | 2.60 / 16.88 / 15.97 |
| `readysetgo@2.0` | 2.13 / 1.09 / 0.91 |
| `bosphorus@4.0` | 0.00 / 6.70 / 3.84 |
| `readysetgo@4.0` | 0.00 / 4.32 / 1.22 |
| `dng_720p@2.0 / @4.0` | 5.67 / 0 / 0 · 4.91 / 0 / 0.06 |

At 0.5 bpp the same arms are at or near 0.00 on every plane. **The artifact class was tuned
at one rate and manifests one to three octaves above it.**

## B1.1 The mechanism, isolated by A/B before any code

`OMC_FDBG` first ruled OUT the shift-eligibility window (cityalley@1.0 fills at s=5,6 with
zero refusals — the fill is active). The amplitude probes then isolated it (cityalley@1.0,
12 frames unless noted, frame-2 flat):

| arm | NEG | flat Y/Cb/Cr % |
|---|---|---|
| v5.3 defaults | 96.094 | 10.22 / 31.70 / 17.44 |
| fill OFF | 96.103 | 31.31 / 46.24 / 53.74 |
| `FILLDIV=1` (luma one octave louder) | 95.891 | **0.44** / 36.57 / 18.30 |
| `FILLDIV_C=0` (chroma one octave louder) | 96.086 | 10.26 / **0.00 / 0.00** |
| **both** | 95.877 | **0.44 / 0.00 / 0.00** |
| `FILLDIV=0` (luma two octaves) | 95.773 | 10.70 / … | 

**The mechanism:** the grain the quantiser kills has a CONTENT amplitude; the fill paints at
a fixed fraction of the RATE-dependent quantiser step (`1 << (s−2−div)`). One rate octave up,
the step halves, the fill halves with it, and the painted grain falls below the flatness
threshold while the real grain is still below the deadzone. The v5.3 divisors (luma 2,
chroma 1) are correct at 0.5 bpp and one octave too quiet per octave above it. (Also
measured: the non-monotone `FILLDIV=0` row is the §67.6 fill→repair feedback returning at
full amplitude — which is what shapes the guard in B1.3.)

## B1.2 The record check (owner rule 3)

* Rate-keyed fill divisor: **nowhere in the OMC record** (grep over the full ledger; §67
  explored global constants only). The *pattern* — a normative rung derived from
  `bits_per_slice` — is `xsl_lim_for()`'s, shipped since minor 9.
* `OMC_DIVEFF` (divisor keyed on the SHIFT) is falsified (§67.11, `G-T5-CALM2a/b`): `s` is
  not generation-invariant. **The rung is keyed on the stream config**, which is constant
  for the stream's life and identical at every generation — the invariance §75.5 rule 1
  demands.
* `OMC_FILLMIN1` (amplitude 1) falsified (§67.11) — the rung never produces amplitude
  ambiguity: it changes `div`, and amplitude stays `1<<(s−2−div_eff)` ≥ 2.
* HVBC: deletion-ledger row 27 rejects a DECODER-side gradient fill for flattening real
  structure; the OMC fill is the transmitted-mask grain fill (different mechanism, already
  shipped); no HVBC row keys fill on rate.
* The gain classifier's fixed point (§62) holds per stream: with the rung constant, every
  amplitude still re-measures into its own class at generation 2.

## B1.3 The design — reached by falsification, in five measured steps

The first shape tried (divisor rung on BOTH planes, luma floored at 1) passed all 97 gates
— and the full-frame instruments then falsified half of it. Every step below is a
12-frame, full-frame measurement; each dead shape is kept default-off in the tree as
evidence (the §67 precedent).

**(a) Chroma divisor 0 at 1.0 bpp washes LUMA.** `FILLDIV_C=0` alone on `bosphorus@1.0`:
blotch n>20 118 (worst −44.7), with the luma rung too: n>20 191, NEG −2.59 — a
chroma-only amplitude change producing luma level errors. Eliminated one by one: repair
(0 slices fire; `--no-gamut-strict` arm byte-identical), gain classifier (`FILLGAIN_MAX=0`
no change), chroma dead-band, MV derivation (luma-only by construction), the §alloc
allocator (`OMC_ALLOC=0` arm still washes: n>20 86), redraw-vs-carry (`FILLINTRA=1` still
washes: n>20 121).

**(b) Chroma ELIGIBILITY relax washes worse.** The offer precheck refuses chroma bands
with `base_s < 3 + div + 1`; dropping the `+1` for chroma (`OMC_FILLELIG_C=1`,
encoder-only, amplitude untouched) closes chroma flatness at 2.0 bpp on static content —
and destroys `bosphorus@2.0`: blotch worst −141, n>40 107, NEG −2.7.

**(c) "Paint at the refresh, carry between" fails on exactly the content that needs it.**
`OMC_FILLELIG_C=2` (relax INTRA bands only — grain painted once per refresh cycle, then
carried inside the deadzone by inter prediction, the §68 crawl logic in reverse): on
poorly-predicted content the chroma bands re-choose intra EVERY frame, so "intra only"
degenerates to "every frame" — `bosphorus@2.0` n>40 107 worst −141 NEG −2.6, `@1.0`
n>40 43 NEG −2.1. Both lever values kept default-off as falsification evidence.

**(d) The chroma OFFER THRESHOLD is free — at 0 exactly, and only with a new guard.**
The mid-rate chroma flatness at 1.0 bpp is not amplitude-limited at all: the failing
bands' mean eligible magnitude sits in (0, 1/16) of a step, below the §61 offer line of
3/16. `OMC_FILLTHR_C=1` fixes nothing; `=0` fixes it completely at unchanged NEG and zero
blotch (`bosphorus@1.0` Cb 11.31→0.00 at NEG 96.654 vs 96.660; `cityalley@1.0` Cb
31.91→0.00 at NEG +0.10). But bare threshold 0 re-broke A4 — G-T5-XSL2/3a/3b, PAD2,
GAMUT2b, CUT3 all failed, the §67.11 `FILLTHR=0` falsification reproduced chroma-only:
a band with EXACTLY zero eligible energy (plates, graphics) gets offered fill. The v5.4
form adds `sum > 0` to the offer (live rule and lock_verify mirror, same edit): truly
empty bands stay unoffered, every (0, 3/16) band is admitted, and the full gate suite
passes.

**(e) The washes of (a)/(b) were CLIP DAMAGE, and the §80 reach guard closes them.** The
wash region is the bosphorus sun glint (src max 942 = against the bright rail; local
errors to −402/+283 codes): double-amplitude grain on a rail-pinned sparkle block clips
one-sided and the block mean walks off. No repair fires (0 slices, 0 oob) — this is
direct fill damage through the clamp, not the §78.10 repair path. `OMC_FILLREACH`
(sect.80) refuses fill where the block's estimated peak excursion reaches within 64
codes of a rail — shipped ON at slice_h 8, OFF at 16 ("harmful at sh16": measured at
0.5 bpp, rung 0, where the divisor is 2 and there is nothing to guard; it does not
carry). With the guard forced ON at rung 2 any slice height, the same amplitudes that
washed at (a)/(b) measure blotch-CLEAN (n>20 0) at unchanged NEG.

### The adopted co-set (all keys generation-invariant: plane, stream-config rung)

    rung = 2 if bits_per_slice ≥ 0.75·T,  1 if ≥ 0.375·T,  else 0
           (T = width · slice_h · (444 ? 3 : 2) coded samples per slice)

    luma   divisor: d0 − 1 at rung ≥ 1, only while d0 > 1   [minor-14 normative]
    chroma divisor: 0 at rung 2                              [minor-14 normative]
    chroma offer threshold: 0 at rung ≥ 1, with sum > 0      [encoder-only, in the mask]
    reach guard: forced (64) at rung 2, any slice height     [minor-14 normative]

Every divisor consumer moves together through `omc_filldiv_pr()` — amplitude, gain fold,
lattice admission (`LAT_DV`), band-offer test (the §62 lesson applied in advance); the
threshold through `omc_fillthr_pr()`, mirrored in `lock_verify` in the same edit.

**Stream coherence of the A/B lever.** `OMC_FILLRUNG=0` restores v5.3 SEMANTICS, so the
encoder stamps those streams **minor 13**: they decode byte-for-byte on a v5.3 decoder,
and this build's strict single-minor decoder refuses them LOUDLY instead of silently
applying rung amplitudes the encoder never used (verified both ways). Every minor-14
stream therefore has rung semantics; the decoder derives the rung unconditionally from
the header and never reads the environment (§11.5b/c). `G-T5-RESTORE` passes: the v5.0
incantation runs `FILLDIV=0`, which the `d0 > 1` guard leaves untouched.

## B1.4 Measured results (v5.4 defaults vs v5.3 defaults, 12-frame full-frame)

| cell | flat f3 Y/Cb/Cr (v5.3 → v5.4) | blotch tail | NEG |
|---|---|---|---|
| `bosphorus@1.0` | 6.33/11.31/5.50 → **0.30/0.00/0.00** | n>20 0 | 96.660 → 96.588 |
| `cityalley@1.0` | 9.18/31.91/20.88 → **0.00/0.00/0.00** | n>20 0 | 96.094 → 96.143 |
| `bosphorus@2.0` | 2.66/16.88/15.97 → **1.61/0.00/0.00** | n>20 0 | 98.095 → 98.053 |
| `cityalley@2.0` | 5.43/8.96/8.71 → **2.80/0.00/0.00** | n>20 0 | 96.956 → 96.946 |
| `readysetgo@2.0` | 2.15/1.09/0.91 → **0.48/0.00/0.00** | n>20 0 | 98.831 → 98.791 |
| `dng@2.0` | — → 0.21/0.00/0.00 | n>20 0 | 96.145 |

f11 (owner rule: subsequent frames) tracks f3 within noise on every cell. The remaining
luma residue at 2.0 bpp (1.6–2.8%) is dominated by the reach-REFUSED rail blocks — the
blocks where painting was the measured damage; the residual chroma at 4.0 bpp
(`bosphorus` 6.7/3.8) sits below `OMC_FILL_MIN_SHIFT` (texture loss < 2 codes at 10-bit
— no fill is representable there, and the eye question goes to the owner).

All 97 gates pass; G-T5-RESTORE reproduces v5.0 byte-for-byte outside the version field.
Full-gamut battery, A4 chain battery (baseband + CDR, 5 generations, incl. ≥0.75 b/cs
cells where the rung is live), and the frozen-master crawl battery: §B1.5.

## B1.5 Validation (full gamut, 48 cells x 12 frames, per-plane, f2/f3/f11)

Full table: `battery_v54_vs_v53.txt` (this zip). The headline facts:

**1. Byte-identity at rung 0 confirmed ACROSS THE GAMUT.** Every 0.5 bpp cell
(all twelve) reports dNEG exactly +0.000 with identical blotch tails and
flatness to three decimals — the v5.4 encoder at rung 0 is v5.3's
reconstruction, cell for cell, as designed.

**2. The flatness class closes at 1.0–4.0 bpp.** Cb/Cr flatness is 0.00 on
EVERY cell at 1.0 bpp and above (including `bosphorus@4.0` 6.70→0.00 — a
bonus of the rung-2 chroma divisor: div 0 lowers the eligibility floor to
s=3, so the 4.0 bpp bands previously below `OMC_FILL_MIN_SHIFT`+div fill at
amplitude 2). Luma closes to ≤0.5 % on all but four cells and improves on
those (bosphorus@2.0 1.61, cityalley@2.0 2.80, cf_gfx 3.83 unchanged —
graphics has no grain to paint — and dng_444_8@1.0, see item 3). No cell's
NEG moves by more than −0.13 except the two in item 4; many improve.

**3. OPEN: the 4:4:4 rung boundary.** `dng_444_8@1.0` keeps Y 8.42 % flat,
untouched — at 4:4:4 a display bpp of 1.0 is 0.333 bits/coded-sample, one
notch BELOW the 0.375 rung-1 threshold, while the same display rate at 4:2:2
(0.5 b/cs) is rung 1 and closes to 0.04. The measured class boundary is
therefore ≤ 1/3 b/cs and the rung-1 threshold should drop to 5/16 (0.3125):
anchors 0.25 b/cs = clean at rung 0 (every 0.5 bpp 4:2:2 cell), 0.333 b/cs =
class present. To be changed and re-validated after the A4/crawl batteries
complete (no rebuild while a battery is live — the mixed-build lesson).

**4. OPEN: two mild rung-1 regressions, both on the sh-8 short rung.**
`cf_gfx@1.0` NEG −0.254 with n>20 21→26 (n>40 3→3, flatness unchanged — the
chroma offer threshold paints grain into anti-aliased graphics chroma that
needed none), and `dng_720p@1.0` NEG −0.178 for a flatness return of only
3.18→3.07 (its real gain arrives at 2.0: 5.67→0.98 at −0.055). Both cells
sit at slice_h 8. To investigate with the §51.15 map after the batteries;
candidate shapes: keep the chroma threshold rung off graphics-energy bands
(needs a non-content-keyed discriminator — record check first), or accept
and document (cf_gfx is the 448x256 proxy; the §55.7-L precedent is that a
cf_gfx-only NEG loss did NOT reproduce on the real 1080p graphics arm).

**5. A4 chain battery and frozen-master crawl battery: running** (baseband +
CDR, 5 generations, 10 cells including every rung-live rate; crawl 12 cells
x 3 rates vs the v5.3 baseline) — results below when complete.

## B1.6 The rung-1 boundary — CLOSED at 0.3125 b/cs

Item 3 of §B1.5 resolved: threshold 0.375 → 0.3125 (5/16, splitting the
measured anchors: 0.25 b/cs clean at rung 0, 0.333 not). Target cell
dng_444_8@1.0: Y flatness **8.42 → 0.09 %** at +0.10 NEG, tails clean.
Full train: 48-cell battery NEG mean −0.005 with ONE flagged cell
(dng_444_10@1.0: n>40 0→4, worst −114, NEG −0.14 — the rung-1 luma divisor
biting without the reach guard, the same clip mechanism §B1.3(e) closed at
rung 2); frozen crawl 0 of 12 worse than v5.3; **A4 20/20**; 97 gates +
restore green. The flagged cell's fix — reach guard at rung ≥ 1 — is the
next serialized change (§B1.7).

## B1.7 The 444_10@1.0 tail: reach-at-rung-1 FALSIFIED; tail documented open

Extending the reach guard to rung ≥ 1 was built and falsified within minutes:
the guard's fill refusals reopen the flatness class at rung 1 (444_8@1.0
0.09 → 2.37 %, cityalley 0.83 → 1.19) and the target tail WORSENED (n>40
4 → 32, worst −224) — so the 4-block tail is NOT the fill-clip mechanism, and
§80's sh16 finding holds one rung down. Reverted byte-exact to the validated
boundary build. The 4-block, worst −114 tail on dng_444_10@1.0 stands as the
boundary change's one documented cost, with a §51.15 map diagnosis queued in
the smudge workstream (it is a G7 item by definition).


---

# B2. CRAWL — the plan sawtooth was the carrier, and the stabilizer already existed

## B2.0 The gate that caught B1

The frozen-master crawl battery (source tail 0 by construction) run against the adopted
B1 co-set showed B1 buying flatness at crawl's expense at every rung-live rate — exactly
the owner's standing warning. frozen ants tail (Y):

| cell | v5.3 | v5.4-B1 |
|---|---|---|
| readysetgo@1.0 | 6.78 | 11.71 |
| dng@2.0 | 18.49 | 23.29 |
| cityalley@1.0 | 2.64 | 4.97 |
| (all 0.5 cells) | identical | identical (rung 0 byte-identity) |

B1 was therefore NOT acceptable as-is. Per the root-cause directive the fix had to make
the fill (and everything else) STABLE across frames — "it's not the presence of fill
that causes crawl, it's that the fill is in different places from one frame to another."

## B2.1 The decomposition (frozen dng@1.0, one lever at a time)

| arm | ants tail Y | verdict |
|---|---|---|
| v5.4-B1 defaults | 27.06 | reference |
| `OMC_FILL=0` | 16.92 | fill carries ~10 pts — but 17 REMAIN with no fill at all |
| `OMC_ALLOC=0` | 27.28 | allocator exonerated |
| `--refresh 12` | 23.46 | refresh scales it weakly |
| `OMC_RBOOST=0` | 27.06 | refresh boost exonerated (byte-identical) |
| `OMC_PLAN_HYST=2` + fill 0 | **7.87** | plan sawtooth = ~9 pts of the 17 |
| `OMC_PLAN_HYST=1` + fill 0 | **7.87** | level 1 achieves the FULL pin on static content |
| `OMC_PLAN_HYST=1`, fill on | **14.75** | better than v5.3's 23.60 WITH the louder B1 fill |

Localization (per frame-pair, per row-band, fill-off): non-refreshed slices hold a ~15 %
churn floor that never converges (a frozen source should converge to zero); refresh-wave
slices flicker at ~50 %; slice-boundary rows barely differ from interior (XSL loop is
NOT the carrier). Derived MVs are all zero on frozen content (MV loop exonerated).

Stream-level proof: parsing consecutive plans out of the emitted stream shows **99.5 %
of non-refresh slices change their (Q, prof, n_steps) EVERY FRAME** on a bit-static
source (558 of 561 slice-pairs; profile stable — the flips are Q/n_steps). The plan
search re-runs from scratch each frame and the near-tie winner wanders with residual
noise; every flip re-quantises the same content differently, the committed picture
oscillates, and the fill field rides along (a plan flip reshuffles the zero-coded set —
the "different places" of the owner's diagnosis).

## B2.2 The root cause was a wiring gap, not a missing mechanism

`OMC_PLAN_HYST=1` (v4.7: reuse the previous frame's committed plan verbatim on an inter
slice while it still fits this frame's budget, fall through to fresh rate control
otherwise) is the exact stabilizer for this — and its default sat INSIDE
`if (cfg->grain_replace)`: **plan hysteresis was OFF in every normal encode** since
v4.7. The T5 comment beside it already blesses level 1's generation story ("the fill
decision stays measurement-derived, which IS a generation fixed point") and forbids
level 2 (froze signalled state; broke grain-replace locks; −1.00 NEG, §51.18.3).

## B2.3 The stabilizer — five shapes measured, one survivor

The naive fix (make level 1 the default) was built, gated, fully validated — and
falsified by the 48-cell battery: **mean NEG −0.55, cf_gfx@0.5 −7.13 with blotch n>20
605→1066, every 0.5 bpp cell down 0.5–2.4.** Mechanism: reuse-whenever-it-FITS throws
the budget's slack away as padding on moving content (the old plan "fits" but stops
refining where fresh planning would spend). One incidental positive kept for the smudge
chapter: it zeroed dng720p@1.0's deep tail (n>40 27→0).

Shape 2, near-tie hold (same prof, same Q, |Δn_steps| ≤ 3, after fresh planning):
NEG restored, crawl win almost gone (frozen dng@1.0 Y 23.25). Stream decomposition of
the remaining flips: Q itself moves on 152/558 pairs, steps jump >3 on 204, **0
within-band flips** — the hold works but the cycle jumps past any band.

Shape 3, small-slack cap (hold only when budget−est(old) ≤ budget/16): never engages —
a static slice's residual costs far LESS than the budget, which is exactly when the
refine loop re-rolls noise-level tails. Crawl win fully lost (27.06).

Shape 4, step ratchet (monotone n_steps at fixed Q): never engages. The debug print
found why, and it is the load-bearing fact of this chapter: **the wander is
REPRESENTATION DEGENERACY** — consecutive frames of a frozen slice plan (Q6, ns13) then
(Q5, ns1): adjacent (Q, n_steps) triples encode nearly the same effective shift set, so
no condition phrased in plan coordinates can gate the cycle.

Shape 5 — THE STATIC-SLICE HOLD (adopted). The discriminator that separates cleanly is
the residual's own cost under the old plan, est(old)/budget, measured per slice:

| content (f≥2) | p25 | median | p75 |
|---|---|---|---|
| frozen dng@1.0 (static slices) | 27 % | 35 % | 206* |
| cf_gfx@0.5 (moving graphics) | 77 % | 85 % | 93 % |
| bosphorus@0.5 (moving water) | 85 % | 92 % | 98 % |

(*the >100 % population is slices that no longer fit — they replan regardless.) A
factor-of-two gap with nothing in between. Rule: **hold the previous committed plan iff
the profile matches and est(old) ≤ budget × OMC_PLAN_STATIC/100.** A held slice's
residuals are so cheap that fresh refinement would re-roll reconstruction noise (the
limit cycle); a slice with real content in its residual sails past the line and replans
at full fresh quality — which is why this cannot reproduce level 1's NEG cost (its
victims all sit far above the line).

Threshold: 50 measured −0.10 NEG and +65 blotch blocks on dng@0.5 (real grain residual
sits at 35–50 %); **35 (the static cluster's median) is byte-neutral on dng@0.5 and
within noise everywhere else probed, and keeps the crawl win** (frozen dng@0.5
25.08→14.53, @1.0 27.06→15.88 Y). Default `OMC_PLAN_HYST=3`, `OMC_PLAN_STATIC=35`;
level 1 remains grain-replace-only; level 2 remains diagnostic. Encoder-only (plans are
signalled). The v5.0 restore incantation carries `OMC_PLAN_HYST=0` (authoritative copy
in `tests/restore_check.sh`, mirrored in docs/OMC_V5_1.md §7.2; G-T5-RESTORE enforces).

## B2.3b Three bugs between the design and a correct build — each caught by A4

The first full validation of the static-slice hold FAILED four A4 chains
(pixels-gen2: dng@1.0, dng720p@1.0, baseband and CDR). The gate suite had
passed — A4's real-content chains caught what the synthetic cells cannot.
Root-causing found three distinct defects, each traced to the exact first
held slice:

**(1) The hold omitted `Q`.** It grafted the old plan's `(n_steps, partial)`
onto the FRESH frame's Q — a Frankenstein plan no fresh search emits
(observed: held "(Q7, ns0, partial1)" built from a Q6 plan's parts).

**(2) Held partials are not lock-discoverable.** The candidate scan pushes
ONE k per (prof, Q, ns) — the lattice's LOWER bound (the "one candidate per
feasible k" fan its own comment describes is not present in the code) — so a
held partial whose refined chunk leaves no finer-lattice evidence cannot be
re-derived by the next generation. A FRESH partial refines a chunk chosen for
its content, which is why v5.3 locked them. The hold now refuses plans with
`partial != 0` (a lock-completeness condition, commented as such at the site).

**(3) The level-2 fill freeze leaked into level 3.** `pinned &&
omc_plan_hyst >= 2` (written when 2 was the maximum) froze the fill mask and
gains on held slices — exactly the signalled-state-not-derivable-from-pixels
mechanism the T5 note forbids, re-learned: the frozen mask made the emitted
slice unreproducible, the actual size missed the estimate, and the overflow
backoff then mutated held plans into ones no fresh search emits. Scoped to
`== 2`; a level-3 hold derives fill by the measurement rule like any fresh
slice.

Also hardened while inside: the hysteresis STORE canonicalizes its triple
(minimal-n_steps representative of the effective shift matrix) so degenerate
lock representations at generation 2 — the lock verifies reconstructions,
not header fields — cannot fork the held lineage between generations.

After the three fixes: dng@1.0 and dng720p@1.0 are gen2-pixel-exact AND
gen3-stream-exact; the corrected build keeps the crawl win (frozen dng@0.5
25.08→14.94, @1.0 27.06→16.22 Y) at exactly-baseline NEG on dng@0.5 /
bosphorus@0.5 and −0.002 on cf_gfx@0.5. All 97 gates + restore pass.

## B2.4 Validation — CLOSED (crawl_v54_hold2.log, battery_v54_hold2.log, a4_v54_hold2.log)

* **A4: all 20 chains PASS** (10 cells × baseband + CDR, 5 generations) — the three
  §B2.3b defects are fixed and the exactness contract holds with the hold active.
* **48-cell battery, hold vs the B1 build: free.** NEG mean +0.001 (worst cell −0.002,
  best +0.021); zero cells flagged on blotch or flatness. The only regressed-vs-v5.3
  cells remain B1's two open items (cf_gfx@1.0, dng720p@1.0), unchanged by the hold.
* **Frozen crawl battery vs v5.3:** frozen dng 25.08→14.94 (0.5), 23.60→16.22 (1.0),
  18.49→17.26 (2.0) Y with chroma similar; readysetgo@0.5 14.95→12.73; cityalley@0.5
  7.48→6.22; bosphorus@0.5 3.13→2.40. Remaining WORSE rows are the chroma-at-2.0
  fill-redraw family (worst: readysetgo Cb 2.29→6.35) plus sub-unit ticks at 1.0 —
  the next serialized crawl item, not the hold.
* 97 gates + G-T5-RESTORE green throughout.

## B2.5 What remains of crawl after the sawtooth (measured, queued one at a time)

With the plan stable and fill off, frozen dng@1.0 still shows: refresh-wave slices at
~41 % pair-tail (the intra and inter stationary points differ; each refresh yanks the
picture between the two fixtures — root-cause candidates start from why Q5's intra skip
`q == quant(pcoef)` fails to hold the carried picture through a refresh), and fill
still contributes ~7 pts on heavy-grain content (redraw at refresh). Both are the next
serialized items if the batteries confirm them at scale.

## B2.5 The pulsation instrument, and where the remaining pulse actually lives

Owner constraint (2026-08-31): a crawl fix must not become PULSATION — periodic
pixel-group changes the eye locks onto. And: **compare against SOURCE, not the
decode's own frame pairs.** Built as `pulse.py` (ships in harness/): per 16x16
block, per frame, the error field vs source as a time series; blocks classify as
FIXED (settles), CRAWL (error pattern decorrelates per frame), or PULSING (rare
large re-draw steps; dominant period reported). 120-frame frozen arms.

| frozen dng@1.0, 120f | fixed | crawl | pulsing |
|---|---|---|---|
| v5.3 | Y 17% / Cb 14% / Cr 29% | 28% / 2% / 3% | **54% / 83% / 67%, period 8** |
| v5.4 (B1+B2) | **75% / 91% / 91%** | 3% / 0% / 0% | 20% / 8% / 7%, period 8 |

So the sawtooth fix did NOT trade crawl for pulsation — v5.3 was already pulsing
at the refresh period, worse than today by 2.7–10x, with heavy crawl on top.

**The remaining period-8 pulse is the REFRESH QUALITY RAMP, and it is rate
physics, not a planning defect.** Proven by escalation: (a) grid constancy at
the refresh (reuse the previous refresh's plan when the whole cycle was
static-held; includes the post-refresh exemption that breaks the
snap-disqualifies-the-cycle deadlock) was built, engaged on 79% of refresh
events — and moved nothing: even refresh-HELD slices change 62% of their pixels
by >6 codes at the refresh. (b) Direct measurement: the inter lineage
ACCUMULATES quality over the R−1 refinement frames; a standalone intra frame at
the same slice budget cannot re-encode that accumulated picture (Q5's intra
skip is structurally unreachable on refresh slices — the A5 resync contract
forbids pcoef there). The refresh resets quality to single-frame level every
cycle: a sawtooth in quality, i.e. the pulse. The grid-hold machinery was
REVERTED (no measured benefit; FPGA-minimal rule) — this section is its
falsification record.

**Disposition:** the ramp is the named Task C item ("ramp invisibility"), where
the recorded levers live: §48 refresh boost (built, default off, "50 measured:
refresh parity" under its co-set), Candidate W need-keyed refresh scheduling
(§39.5), and the R=R2 temporal goals. B-crawl's remaining in-scope item is the
chroma fill-redraw at rung-2 rates (§B2.6).

## B2.6 The chroma fill repaint — and the boost that was never on

The remaining crawl regression vs v5.3 (frozen readysetgo@2.0: ants Cb 2.29→6.35)
classified under the amplitude-tiered pulse instrument as REFRESH-PERIOD REPAINT:
visible-redraw (>6 codes) pulsing blocks Cb 488 (v5.3) → 1596 (v5.4-B1), Cr 688 → 1685,
period 8. With the fill silenced the floor is 340/334 — the pulse is ~80 %% painted
grain, redrawn each cycle because the refresh's fresh plan moves the band shift s and
the fill amplitude (1<<(s−2−div)) moves with it, at B1's full-step chroma loudness.

Escalation, one shape at a time:
* Grid constancy at the refresh (reuse the previous refresh's plan when the cycle sat
  in static hold, with the post-refresh snap-exemption): engaged, changed NOTHING
  (Cb 1614/Cr 1771) — the LL band still snaps (the quality ramp) and the fill's
  LL-keyed gates flip regardless of the plan triple. Machinery kept (it is the
  bookkeeping the boost interacts with and costs nothing measurable).
* §48 refresh boost — **found to be DEAD CODE since it shipped**: its guard tested
  `c->cfg.refresh_r`, which is 0 whenever `--refresh` is not given (the R=8 default is
  applied via `?:` fallbacks at the USE sites, not stored). Every §48 measurement was
  necessarily taken with an explicit `--refresh`. Guard fixed to resolve R the same way
  every other site does (sect.B2d); default `OMC_RBOOST` 0 → **50**; the v5.0 restore
  incantation gains `OMC_RBOOST=0` (same edit, both copies).

**Measured with the boost live (frozen rsg@2.0, 32f, visible-redraw blocks):**

| | v5.3 | v5.4-B1 | v5.4+boost |
|---|---|---|---|
| Cb crawl / pulsing | 381 / 488 | 123 / 1596 | **1 / 169** |
| Cr crawl / pulsing | 284 / 688 | 245 / 1685 | **1 / 132** |
| Y crawl / pulsing | 1908 / 1634 | 1805 / 2491 | **345 / 2693*** |
| Y no-visible-redraw | 4498 | 3587 | **5002** |

(*the residual Y "pulsing" is burst-shaped, median gap 1 frame — the classifier's
boundary; total visible Y flicker 4296 → 3038.) Chroma lands BELOW the fill-silenced
floor and 3–5x better than v5.3: the boost closes the refresh-vs-converged LL gap at
its source, so the gates stop flipping and the paint reproduces.

Spot guards: cf_gfx@0.5 NEG **+1.09** with blotch n>20 605→514, n>40 126→104 (the §48
original finding — budget-starved refreshed slices land flat on graphics — was a live
defect in every shipped default-R encode); bosphorus@0.5 +0.004; dng@1.0 −0.02;
dng@0.5 +0.11 NEG with a deep-tail tick to watch (n>40 3→6, worst −71→−125).

## B2.7 Validation of the boost — CLOSED, and B2 with it

* **A4: 20/20 chains PASS** (baseband + CDR, 5 generations). 97 gates + restore green.
* **Frozen crawl battery: ZERO cells worse than v5.3** — the crawl-class regression
  list against baseline is EMPTY for the first time; most cells are far better
  (dng 25.08→14.9 at 0.5 etc., §B2.4), and the pulse instrument shows the
  chroma repaint 3–5x better than v5.3 on the stress cell (§B2.6).
* **48-cell battery: NEG mean +0.075 vs pre-boost** (+0.057 vs v5.3), max +1.09
  (cf_gfx@0.5 — the worst smudge cell, whose refreshed slices §48 correctly
  diagnosed as budget-starved). No cell loses more than 0.11.
* **Documented cost, deliberately NOT tuned away**: at 0.5 bpp the shave deepens
  some dng deep tails (720p n>40 105→159; 1080p 3→6; 4K n>20 67→83) while NEG
  on those same cells IMPROVES (+0.11..+0.34). A 25/35/50 boost sweep showed the
  tail counts NON-MONOTONE in the boost (1080p n>40: 3/10/63/6) — single-cell
  deep-tail counts at 0.5 bpp are plan-cascade noise, and tuning a global knob
  against them is noise-chasing. Those tails ARE the G7 smudge class, which is
  the next workstream with a mechanistic procedure (§51.15 attribution → root
  cause); the boost keeps its §48-measured value of 50 and the tail state
  becomes the smudge baseline.

**B2 CLOSES** with two adopted mechanisms and one revived one: the static-slice
hold (§B2.3, sawtooth), the level-3 canonicalized hysteresis it rides on, and
the §48 refresh boost brought back from the dead (§B2.6). Crawl ≤ v5.3
everywhere, mostly far better; pulsation strictly reduced at every point
measured; A4 intact; FPGA surface: no new frame stores, no new passes (the
boost is arithmetic on existing budget targets).


---

# B3. SMUDGES (G7) — mechanism found, parity targets set

## B3.0 Baseline under the B1+B2 build, and what the boost already fixed

The B2 refresh boost moved the class before B3 began: cf_gfx@0.5 n>20 605→514,
n>40 126→104, NEG +1.09 (§48's own diagnosis — budget-starved refresh slices —
was live in every shipped default-R encode); dng720p@1.0 closed outright
(n>20 35→4, n>40 28→0, the plan-hold's incidental win §B2.3). Remaining, by
severity (12f, full-frame): dng720p@0.5 620/159 worst −117; cf_gfx@0.5 514/104
worst +212; dng444_12@0.5 122/15; dng@0.5 32/6; the 8-bit cells ~58–119/1–6.

## B3.1 The mechanism (§51.15 procedure, cf_gfx@0.5)

FIND/SEE: one region dominates frame 0 — rows 32–43, cols 427–447, mean
err +163 on a ~294-code source. The error patch is confined EXACTLY to slice
4's rows (32–39; neighbours clean), ramps vertically within the slice, and
spans ~140 columns at +80–260. ATTRIBUTE: slice 4 plans at **Q=10** (ns 12–21),
repair converges (bad 20→6, deep 83→15) — and the +163 error is IN-GAMUT, so
the repair cannot see it by design. The source has a 900-vs-280 vertical
stripe at col ~424: its coarse-band coefficients, quantised at Q=10 steps,
leave half-step rounding errors of ±100–300 codes that splatter across the
32-column basis support into the flat dark area. **The wash is a handful of
catastrophic coefficient roundings at a forced-coarse rung — not diffuse
noise, and not repair damage.**

Edge test (512-wide re-crop, same content interior): the error drops +163→+33
— the frame edge AMPLIFIES the mechanism ~5x but does not cause it (the new
edge is clean; a new worst appears elsewhere: geometry decides WHERE the
roundings land, content decides IF).

## B3.2 Parity targets (the goal-b criterion: OMC@R vs XS@2R, best-flags SVT q1rc2sh32)

| cell | OMC@R today (n>20/n>40, worst) | XS@2R (n>20/n>40, worst) |
|---|---|---|
| cf_gfx@0.5 | 514/104, +212 | 152/3, +45 |
| dng720p@0.5 | 620/159, −117 | 1/0, −21 |
| dng@0.5 | 32/6, −125 | 0/0, +13 |
| dng444_12@0.5 | 122/15 | 0/0, +12 |

At EQUAL rate OMC beats XS on cf_gfx (26/3 vs 152/3 at 1.0 bpp) — the class is
a half-rate-budget problem, concentrated in the deep tail.

## B3.3 Candidates from the record (no re-treads)

* **HALF-RUNG** (§38.4, queued with a docs-first prerequisite): ×1.5 quantiser
  rungs fill the octave gap that forces Q=10 when Q=9 misses the budget —
  the direct hit on "forced one rung too coarse". Normative, rides minor 14.
* **PLAN-SD** (§38.5, kill-test specified): distortion-scored plan choice in
  the first-fit neighbourhood; encoder-only; average-metric, unlikely to reach
  the deep tail alone.
* Targeted spend (repair-aware-planning family, §45.10 wave-3): the tail is
  FEW blocks — per-chunk extra refinement where truncation damage lands on
  smooth support would close it surgically; needs new syntax if beyond the
  existing partial-chunk shape.

## B3.4 PLAN-SD: built, falsified as specced, rebuilt weighted, adopted — and map-verified honestly

Per the §38.5 spec (coefficient-domain |error|): built and **falsified by its own
kill-test** — cf_gfx@0.5 went 514/104 → 699/129 at NEG −3.2. Cause measured with
tests/basis.c: the synthesis norms span **242×** (||g_LL||² = 104.8 vs band-9
0.52); an unweighted score trades coarse-band precision (what draws washes) for
fine-band counts. Rebuilt with ||g_b||₂ weights (Q8 table in-code, from the
codec's own impulse-response tool) and a 2 % switch margin (near-ties flip on
the scorer's mode/deadzone approximation — measured: a 720p block deepened
−117→−274 and bosphorus paid −0.09 NEG without it; both gone with it).

**Adopted default-on (encoder-only), with the repair boundary made structural:**
SD never coexists with the in-gamut repair — on FIRST repair activation the
fit-driven plan is restored and the ladder re-runs (one-shot). Without this,
G-T5-GAMUT2c failed (the pathological rail arm kept one excursion). All 97
gates + restore pass; the incantations gain OMC_PLANSD=0.

Measured (12f, full-frame): cf_gfx@0.5 NEG **+1.68**, tails 514/104 → 441/81,
p99.9 99→75; dng720p@0.5 NEG **+0.82**, n>40 159 → 82; dng@0.5 +0.13;
bosphorus **+0.07**; cityalley@1.0 neutral.

**The §51.15 maps keep the verdict honest (owner rule: the maps, not the
counts):** frame 0's worst wash — the +208 stripe patch, 53/10 level-map blocks
— is IDENTICAL with SD on and off. Those slices activate the repair, so SD
stands aside there by design. PLAN-SD improves the body of the distribution and
buys real NEG; **the class-defining wash still stands** and waits on the
finer-rung work (HALF-RUNG, docs-first) or targeted spend. Validation train
running: battery/crawl/a4 _sd logs.

## B3.5 DESIGN — TARGETED PARTIAL (the wash-shaped spend), pre-build record

HALF-RUNG docs-first verdict: read §12.22.3 in full. Two findings. (1) The
lattice coupling is more benign than feared — multiplying a step by 3 (the
×1.5 rung is 3<<(k−1)) PRESERVES trailing zeros, so the tz-signature machinery
would survive — but the surgery is still wide (quant/dequant ÷3 paths, plan
field width, BMIN/derive_shifts tables, tANS statistics), and (2) it CANNOT
reach parity anyway: the ×1.5 rung scales the +208 wash to ~+156 against a +45
target, because the wash is a FEW coefficients in one region, not a global
granularity problem. HALF-RUNG stays queued as a NEG item, not the wash fix.

**The wash-shaped design instead — TARGETED PARTIAL.** The plan syntax already
carries per-chunk refinement: `partial = k` refines k chunks of the next
refinement step's band — but the chunks are taken in SCAN ORDER, which is
content-blind. Change the chunk-selection rule: **the k refined chunks are the
k with the largest LL gradient under their support** (ties broken by chunk
index). Deterministic and decoder-computable: the LL band decodes FIRST within
the slice, before any detail band, so both ends derive the same choice from
the same bits — no new syntax, no new fields, the (Q, ns, k) plan space and
the lock's candidate enumeration are IDENTICAL. The refinement lands exactly
where washes are drawn: the §B3.1 mechanism is coarse-band rounding splatter
next to high-contrast features, and 'high-contrast feature' IS 'max |∇LL|'
(the cf_gfx stripe, the 720p worst blocks). Normative (minor 14 rider —
decoder must apply the same rule); generation-safe by construction
(lock_verify simulates the decode and derives the same chunks; committed
pixels → same LL → same choice at every generation).

Risks to check in build order: (a) the §12.22.3-noted 720p A4 asymmetry
history around partials — the offer/eligibility interplay must see the SAME
chunk set on both ends (single shared helper, the §62 lesson); (b) the
existing fan-k lock inference ("the lattice only lower-bounds k") is
UNCHANGED — k is still a count; (c) the fill interaction: partial boundaries
remain excluded from fill bands (existing rule keeps holding); (d) measure
first on cf_gfx@0.5 + dng720p@0.5 with maps, not counts.

### B3.5b The design's own kill-test, and the revision it forced (pre-build)

Parse of the wash cell's stream: **partial = 0 on 384 of 384 slices** — the
draft above would have touched nothing. Root: partial is only created in the
refine loop's overflow path AND only when the next step's band is below
OMC_FILL_BANDS_FROM — and the refine order is mostly fill bands. The
mechanism is vestigial at exactly the operating points that wash.

Revision (TARGETED PARTIAL, full form):
1. **Selection rule** as drafted: the k refined chunks of the partial step are
   the k with the largest reconstructed-LL gradient under their support
   (decoded-LL, NOT source — both ends must derive from the same bits);
   deterministic tiebreak by chunk index.
2. **Fill-band partials become legal**: the recorded prohibition ("the
   boundary position is not recoverable from committed values, so the
   generation lock could never re-derive such a plan") is DISSOLVED by rule 1
   — the partition now IS recoverable, from the committed LL. Per-chunk fill
   amplitude uses that chunk's actual shift, derived identically at both ends.
3. **The planner engages partial whenever step granularity leaves room**: the
   refine loop stops when the next whole step misses the budget; the
   remainder currently drains into frame-close padding (est/160 + 64 margin
   plus up to a whole step's delta — potentially several percent of the
   slice, ~6 chunks' worth at the wash cell). Spend it as targeted chunks of
   the next step instead. Padding becomes wash repair, at zero rate cost.
4. Lever OMC_TPART (default 1; 0 = v5.3 scan-order-and-overflow-only
   semantics, joins the restore incantation; forced 0 when OMC_FILLRUNG=0 so
   minor-13-stamped streams stay v5.3-exact).
Normative (minor-14 rider). Build checks: the fan-k lock inference sees the
same selection through the shared helper; lock_verify simulates decode and
re-derives it; the §62 rule (one helper, all sites) applies to the selector.

### B3.4b The full battery falsifies PLAN-SD as a default — lever retained

The 48-cell battery + frozen crawl battery on the SD-default build: **the
closed chroma classes reopen** — flatness bosphorus@1.0 0→11.7 % / cityalley@1.0
0→8.3 % (SD's plan choices cross fill-band eligibility lines), frozen chroma
crawl worse than v5.3 on 10 of 12 cells (dng@0.5 Cb 28.8→43.2 — per-frame plan
wander re-introduced exactly where B2 closed it), 4K@0.5 tails 83/5→105/25,
and −0.13..−0.36 NEG across the 2.0/4.0 dng cells. The smudge-cell wins
(cf_gfx +1.21, 422_12@0.5 +0.43, tails down ~10 %) do not buy that. Default →
OFF; lever + weighted scorer + repair-exclusion retained in-tree with this
record. A chroma-stability-aware rebuild (score gated on fill-eligibility
invariance, or SD restricted to intra/first frames) is the recorded revival
path.

**Process lesson, recorded as a rule**: the spot-guard set for a plan-machinery
change MUST include a chroma-flatness cell and a frozen-chroma-crawl cell from
the start — the narrow NEG/blotch spot set passed while both closed classes
were reopening; only the full battery caught it.

### B3.5c TARGETED PARTIAL: built, tested, falsified AS ENGAGED — infrastructure retained

Built in full (selector on reconstructed LL shared by encoder/decoder/
lock_verify/lock_trial_bits; rank-prefix inference keeping pixels-gen2 and
stream-gen3 exact for evidence-free chunks; fill-band partials legalised by
committed-derivable partition; OMC_TPART lever with the FILLRUNG=0 minor-13
coupling). Probes (lever on): cf_gfx@0.5 NEG −0.54 with worst +212→+242;
dng720p@0.5 NEG −0.32, tails 620/159→580/136; bosphorus@1.0 guard clean.
Two causes: (1) THE FIXED REFINE ORDER DICTATES THE PARTIAL'S BAND — by the
marginal step it points at a fine band irrelevant to the wash, so ranking
chunks WITHIN it cannot reach the coarse-band roundings that draw the wash;
(2) the engagement's slack estimate over-spends and trips overflow backoffs
(the worst-block deepening). Default stays OFF; the selector machinery is
retained as the foundation for the syntax-bearing form: the wash needs the
partial (or an equivalent) to CHOOSE ITS BAND, which the (Q, ns, k) triple
cannot express — an explicit per-band delta field (XS-style priority
signalling, a few bits per slice) is the recorded next design, to be drafted
and built as its own change.

## B3.6 DESIGN DRAFT — PBAND: the band-choosing refinement field (pre-build)

What B3.5c proved is that the wash needs refinement bits DELIVERED TO A CHOSEN
BAND, which (Q, ns, k) cannot express: ns walks a fixed order. Minimal syntax
that can: a per-slice PBAND field — **4 bits: 1 flag + 3 bits naming one
(plane-class, band) target** from a fixed 8-entry table of the coarse bands
(the wash lives in b1–b3 per §B3.1; fine bands never draw block-mean washes) —
plus the existing k (partial count) re-aimed at that band with the B3.5
rank-selector choosing chunks. Cost: 4 bits/slice ≈ 0.013 % of a 0.5 bpp
slice. Decoder: derive_shifts applies (s−1) to the k rank-chunks of the NAMED
band instead of order[ns]. Lock: the field is header-parsed like Q/ns/k; the
candidate space grows 8x ONLY when the flag is set — bounded.

Encoder policy (what earns the field): after the fit, compute per coarse band
the WEIGHTED truncation damage (the B3.4 ||g||₂ weights × sum |quant error|,
restricted to chunks whose LL gradient ranks top-N — damage ON SMOOTH SUPPORT
is what the eye sees per §51.15); if the best (band, k) buys more weighted
damage reduction per bit than the order[ns] step the slack would otherwise
buy, set the flag. This is PLAN-SD's scorer reused WHERE IT IS SAFE: a
band-local, repair-excluded, chroma-eligibility-invariant comparison (the
B3.4b falsification came from whole-plan swaps moving fill eligibility; a
single-band s−1 on k chunks cannot cross a fill-band eligibility line when
the target table is restricted to b1–b3, which are never fill-capable).

Header bit budget: the slice header has spare space (HDRC §39.6 measured 296
bits with ~138 compressible — 4 bits fit without layout change, or ride the
region-0 mv reserved-bit scheme §39.5c). To verify before build: exact spare
bits at the current header layout.

Falsification-aware: not DIVEFF (no s-keyed amplitude); not BANDTILT (no
table change); not TPART-as-engaged (band is chosen, not dictated); the §62
mirror rule applies to the damage scorer only via the emitted field (decoder
reads the field, derives nothing content-side except the B3.5 rank selector
already validated for determinism).

## B3.7 PBAND: built through two versions, and the wash's true root found by its failure

Built per §B3.6 (field packed into partial16's spare bits as
[flag:1][band:3][depth:2][k:10] — the header is otherwise exactly full at
384 bits; zero layout change), with the depth extension after v1 measured
that ONE rung is useless (the wash's coefficients are ZEROED at s — |c| far
below the half-step — and stay zero at s−1). Engagement policy: argmax
pixel-weighted damage reduction over the 7-entry coarse-band table, depth
1..4, spending the step-granularity slack. Verified live on the wire
(55/64 slices flagged; the wash slice takes t=0 = Y b1).

**Measured: the wash does not move** (+212 unchanged, patch pixels shift ≤ 4
codes) although PBAND changes 67k pixels frame-wide at +0.35..+0.57 NEG. The
band-zeroing diagnostic decode (OMC_DBG_ZBAND, analysis-only) then decomposed
the patch: LL carries ~+330, b1 carries ~−350 — **the patch error is b1 coded
~350 SHORT against LL**. Refining b1's quantisation cannot restore what is
not in the coefficients: GAMUT_STAT confirms the slice repairs every frame,
and finer b1 does not shrink the excursion either (bad 371→413, deep 96→95).
**The cf_gfx wash is the in-gamut REPAIR's contrast price, exactly as §51.15's
original attribution said** — the ringing excursion at the stripe is
content+transform-intrinsic at this budget, the repair must shave b1 to keep
the rails legal, and the shave IS the wash.

Disposition: PBAND default OFF (lever kept; its NEG gain is real and a future
cycle may adopt it for what it does buy; its lock-enumeration stage was
deliberately not built once the wash target was refuted). The wash class on
repair-bound cells now reduces to ONE architectural question:

**THE CLAMP QUESTION (owner decision, docs-first).** XS-class codecs clamp at
the rails and lose nothing but the clip itself; OMC forbids clamping and
repairs coefficients instead because a clamped pixel breaks the lattice
re-encode exactness (A4). The measured price on this cell is the entire
remaining wash (+212 worst, ~150-code patch means). Whether a NORMATIVE CLAMP
with a clamp-aware exactness story (e.g., lock candidates verified against
the clamped reconstruction) can preserve A4 is an engine-level design the
owner reserved for themselves with a thorough OMC+HVBC+constraints
consultation (§12.22's why-not-clamp record first). Everything short of it —
five shapes measured this session — leaves the wash standing.

### B3.7b The clamp question, MEASURED at generation 1 (zero codec changes)

Sandbox step 0 per the owner's requirement: encode with the repair's own
off-switch (--no-gamut-strict, the GAMUT1 non-vacuity arm — a conformant
configuration whose out-of-range committed values both ends carry
identically), decode, clamp the output to [0,1023] in post. That output is
pixel-identical to a clamp-architecture generation 1.

| cell @0.5 | repair (shipped) | clamp (simulated) | XS@2R |
|---|---|---|---|
| cf_gfx | 514/104, worst +212, NEG 78.48 | 302/**19**, worst −94, NEG **82.28** | 152/3, +45 |
| dng720p | 620/159, NEG 88.01 | 187/**8**, worst +50, NEG **88.71** | 1/0 |

The repair-bound wash class collapses (+3.80 / +0.70 NEG; deep tails 5–20x
down; the +212 patch GONE — its coefficients are never cut). Remaining before
reality: (1) the owner's §12.22/HVBC/constraints consultation ruling;
(2) the clamptree sandbox with a clamp-aware exactness story, proven on the
full suite + hardened chains (8+ generations, CDR conversion, rail-walkers,
poison audits) before promotion. Until then the shipped tree is unchanged.


---

# B4. SEAM EDGE — the "seam" that isn't: the 2-row chroma stripe

## B4.0 Baseline map (48-cell battery pitch columns, current build)

Two families, unmoved by B1–B3: cityalley CHROMA at ×44–57 over the source
null at EVERY rate (Y only ×4); dng720p at ×20–30 everywhere (co-located with
its smudge cluster on the sh8 rung). Falsified shapes on record, not re-tried:
K (relocates, chroma worse 18/20), SPREAD (A4 8/12), CASC (relocates into G7).
Candidate L already ships ON since v5.3 — these are post-L residuals.

## B4.1 The rowphase measurement redefines the class (cityalley@1.0)

Detail retention by row phase inside the 16-row slice: Y is FLAT (±1.5 %, mild
±3.5 boundary bumps) — but Cb alternates **every other row across ALL phases**:
odd phases +11..+22 % OVER-retained, even phases −20 % under (spread 44.9 % of
mean; Cr 30.5 %). The "slice-pitch" ×50 is the harmonic signature of a 2-ROW
CHROMA STRIPE, not a boundary artifact. **The class definition changes: this
is not a join defect — the picture is striped everywhere.**

## B4.2 Cause: the fill paints it (measured chain)

* Fill OFF ⇒ the alternation VANISHES (spread 44.9 → 12.4 %) — and chroma
  retention collapses to 0.57 (the flatness the fill exists to fix).
* Stream fill-mask parse: the chroma paint is ~pure FINEST-HH — b9 on 97/91 %
  of Cb/Cr slices; b7 (finest LH, the vertical-detail complement) on 9 %.
  A HH-only grain splits its energy between the two rows of each pair by the
  V-synthesis high-pass polyphase ratio — every pair alike ⇒ a 2-row stripe.
  Y paints a broader band mix (b9 59 %) ⇒ Y's profile stays flat.
* Why HH-only: per-frame mask parse shows b6/7/8 offered on frame 1 then
  COLLAPSING to ~1 slice by frame 5 while b9 holds 67–68/68. The offer's
  inter-band `pc != 0` rule excludes positions already painted (their grain
  CARRIES — correct) so those bands' offers self-extinguish; b9 keeps
  re-offering every frame (count stays 3840 — the intra path skips the pc
  exclusion). Not the dead-band, not the coarse veto, not gr_fillveto
  (lever-isolated: coverage identical with each off).

## B4.3 Fix directions (next cycle, one at a time)

(a) BAND-BALANCED PAINT: the row stripe is an energy-ratio artifact; painting
LH+HL alongside HH balances the two V-polyphases (Y demonstrates this — its
mixed masks read flat). The lever point is the offer population asymmetry.
(b) Polyphase-aware amplitude is NOT possible per coefficient (each HH
coefficient feeds both rows at a fixed tap ratio — intrinsic).
(c) Whatever the shape, guards: rowphase spread joins the mandatory guard set
for any fill change, alongside chroma flat + frozen crawl.

## B4.4 Phase 1 CLOSED: the rung-gated chroma eligibility relax

Mechanism completed by attribution: refinement drives chroma b6..b8 to
base_s 4, under the div-linked eligibility floor (3+div+1 = 5 at div 1), so
only the unrefined finest-HH keeps painting — mask coverage b7 = 1..2 of 68
slices. Relaxed (rung ≥ 1 only; rung 2 is a no-op at div 0, rung 0 keeps the
v5.3 byte-identity — verified), coverage returns (b7 58/68) and the stripe
spread drops 44.9 → 30.2 % of mean. The 2026-08-31 FILLELIG falsification
was the rung-2/div-0/pre-reach regime and does not apply at rung-1/div-1
(guards clean). Full train: 48-cell battery NEG mean +0.000, ZERO flags;
frozen crawl 0/12 worse; A4 20/20; 97 gates + restore green.

Residual (30 %): the balancing bands paint at HALF the finest-HH amplitude
(their shift is one lower). The follow-up — a paired-amplitude rule keying
the finest-trio chroma fill amplitude on the trio's coarsest shift — is
DESIGNED but touches the lattice-admission windows (the highest-risk zone,
three A4 bugs this session); deferred behind the full-gamut battery
extension, which gates every closure claim. dng720p's ×20-30 pitch family
remains open (co-located with its smudge cluster; likely repair-bound —
the clamp question's territory).


---

# APPENDIX S — every instrument and script this ledger cites, inlined (self-containment rule)

## `pulse.py`

```
#!/usr/bin/env python3
"""pulse.py — the PULSATION vs CRAWL vs FIXED classifier, source-referenced.

Owner requirement (2026-08-31): a crawl fix must not turn per-frame shimmer into
periodic pixel-group changes every second or two (pulsation).  Frame-pair diffs of
the decode cannot see this — the reference is ALWAYS THE SOURCE (the sect.51.15
rule): per 16x16 block, per frame, the block's error field vs source is tracked as
a time series, and each block is classified:

  fixed     : error settles and stays (low churn, no steps)
  crawl     : error pattern decorrelates frame after frame (high churn rate)
  pulsation : error holds still for stretches, then JUMPS and holds again
              (rare large envelope steps); dominant step period reported

Churn of a block at t = 1 - corr(err_t, err_t-1) over the block's pixels (0 = the
error field froze, 1 = fully redrawn), counted when the block has meaningful error
(rms > 1 code).  A step = frame where churn > 0.5 (the field visibly re-drew).
Blocks stepping on >=25% of frames = crawl; blocks with 1..(nf/8) steps = pulsing;
blocks with 0 steps = fixed.  Period = median gap between steps of pulsing blocks.

  pulse.py SRC.yuv DEC.yuv W H NF [--fmt 422] [--depth 10] [--blk 16]
"""
import sys, numpy as np
sys.path.insert(0,'v53/omc_v5.3/harness'); import yuvio
a=sys.argv[1:]
src,dec,W,H,NF=a[0],a[1],int(a[2]),int(a[3]),int(a[4])
fmt,depth,blk='422',10,16
i=5
while i<len(a):
    if a[i]=='--fmt': fmt=a[i+1]; i+=2
    elif a[i]=='--depth': depth=int(a[i+1]); i+=2
    elif a[i]=='--blk': blk=int(a[i+1]); i+=2
    else: i+=1
sc=1<<(depth-10)
for pi,pname in ((0,'Y'),(1,'Cb'),(2,'Cr')):
    errs=[]
    for f in range(NF):
        ps=yuvio.planes(src,W,H,f,fmt,depth)[pi].astype(np.float64)
        pd=yuvio.planes(dec,W,H,f,fmt,depth)[pi].astype(np.float64)
        errs.append((pd-ps)/sc)
    h,w=errs[0].shape; nh,nw=h//blk,w//blk
    E=np.array([e[:nh*blk,:nw*blk].reshape(nh,blk,nw,blk).transpose(0,2,1,3).reshape(nh,nw,-1) for e in errs])
    rms=np.sqrt((E**2).mean(-1))                      # (NF,nh,nw)
    Ec=E-E.mean(-1,keepdims=True)
    num=(Ec[1:]*Ec[:-1]).sum(-1)
    den=np.sqrt((Ec[1:]**2).sum(-1)*(Ec[:-1]**2).sum(-1))+1e-9
    churn=1-num/den                                    # (NF-1,nh,nw)
    active=(rms[1:]>1.0)&(rms[:-1]>1.0)
    step=(churn>0.5)&active
    nstep=step.sum(0); nact=active.sum(0)
    fixedb=crawlb=pulseb=0; periods=[]
    for y in range(nh):
        for x in range(nw):
            if nact[y,x] < NF//4: continue            # block never meaningfully wrong
            ns=nstep[y,x]
            if ns==0: fixedb+=1
            elif ns>=0.25*nact[y,x]: crawlb+=1
            else:
                pulseb+=1
                ts=np.nonzero(step[:,y,x])[0]
                if len(ts)>1: periods.extend(np.diff(ts).tolist())
                elif len(ts)==1: periods.append(NF)   # single jump in the run
    per=(f" period~{int(np.median(periods))}f" if periods else "")
    tot=max(fixedb+crawlb+pulseb,1)
    print(f"PULSE {pname}: active-blocks {fixedb+crawlb+pulseb}  fixed {fixedb} ({100*fixedb//tot}%)  crawl {crawlb} ({100*crawlb//tot}%)  pulsing {pulseb} ({100*pulseb//tot}%){per}")
    # severity tier: only blocks whose LARGEST frame-to-frame redraw amplitude
    # (rms of err_t - err_t-1 at a step) exceeds 6 codes -- the visibility line
    # the ants instrument uses.  Sub-visible flicker must not dominate the counts.
    dE=np.sqrt(((E[1:]-E[:-1])**2).mean(-1))          # (NF-1,nh,nw) redraw rms
    f6=c6=p6=0; periods6=[]
    for y in range(nh):
        for x in range(nw):
            if nact[y,x] < NF//4: continue
            vis=(step[:,y,x])&(dE[:,y,x]>6.0)
            nv=vis.sum()
            if nv==0: f6+=1
            elif nv>=0.25*nact[y,x]: c6+=1
            else:
                p6+=1
                ts=np.nonzero(vis)[0]
                if len(ts)>1: periods6.extend(np.diff(ts).tolist())
    per6=(f" period~{int(np.median(periods6))}f" if periods6 else "")
    print(f"PULSE>6c {pname}: no-visible-redraw {f6}  crawl {c6}  pulsing {p6}{per6}")

```

## `ants_local.py`

```
#!/usr/bin/env python3
"""Localize crawl: for each frame pair, tail P(|d|>6) per 16-row band (slice_h 16),
split into boundary rows (0,1,14,15 of each slice) vs interior rows. Y plane."""
import sys, numpy as np
sys.path.insert(0,'v53/omc_v5.3/harness'); import yuvio
dec,W,H,NF=sys.argv[1],int(sys.argv[2]),int(sys.argv[3]),int(sys.argv[4])
ys=[yuvio.planes(dec,W,H,f,'422',10)[0].astype(np.int32) for f in range(NF)]
SH=16; ns=H//SH
print("pair | overall | boundary-rows | interior-rows | refresh-slices(tail) | others(tail)")
for f in range(NF-1):
    d=np.abs(ys[f+1]-ys[f])
    t=lambda a: 100.0*(a>6).mean() if a.size else 0.0
    bmask=np.zeros(H,bool)
    for s in range(ns): bmask[[s*SH,s*SH+1,s*SH+14,s*SH+15]]=True
    rs={ (f%8), ((f+1)%8) }   # slices refreshed in either frame of the pair
    smask=np.zeros(H,bool)
    for s in range(ns):
        if s%8 in rs: smask[s*SH:(s+1)*SH]=True
    print(f"f{f}->f{f+1} | {t(d):5.2f} | {t(d[bmask]):5.2f} | {t(d[~bmask]):5.2f} | {t(d[smask]):5.2f} | {t(d[~smask]):5.2f}")

```

## `cmp_batt.py`

```
#!/usr/bin/env python3
"""Compare v5.4 battery vs v5.3 baseline cell-by-cell: NEG delta, blotch tails, flatness, pitch."""
import re, sys
def parse(path):
    out={}
    for ln in open(path):
        if not ln.startswith('CELL '): continue
        tag=ln.split()[1]
        neg=re.search(r'NEG=([0-9.]+)',ln); bl=re.search(r'BLOTCH\(10b-scale\) (\S+) at f\S+ r\d+ c\d+\s+p99\.9 (\S+)\s+n>20 (\d+)\s+n>40 (\d+)',ln)
        fl={}
        for k in ('FLATF2','FLATF3','FLATF11'):
            m=re.search(k+r'\[\s*Y\s+([0-9.]+)%.*?Cb\s+([0-9.]+)%.*?Cr\s+([0-9.]+)%',ln)
            if m: fl[k]=[float(x) for x in m.groups()]
        pt=re.search(r'PITCH dec-vs-src Y/Cb/Cr ([0-9.]+)/([0-9.]+)/([0-9.]+)\s+\|\s+SOURCE null ([0-9.]+)/([0-9.]+)/([0-9.]+)',ln)
        oob=re.search(r'oob=(\S+)',ln)
        out[tag]=dict(neg=float(neg.group(1)) if neg else None,
                      bl=[float(bl.group(1)),float(bl.group(2)),int(bl.group(3)),int(bl.group(4))] if bl else None,
                      fl=fl, pt=[float(x) for x in pt.groups()] if pt else None, oob=oob.group(1) if oob else '?')
    return out
a=parse('logs/battery_v53_baseline.log'); b=parse('logs/battery_v54_coset.log')
worse=[]; print(f"{'cell':44s} {'dNEG':>7s} {'n20 v53>v54':>12s} {'n40':>8s} {'flatf3 Y/Cb/Cr v53 -> v54':>34s}")
for t in sorted(a):
    if t not in b: print(t,"MISSING in v54"); continue
    x,y=a[t],b[t]
    dn=(y['neg']-x['neg']) if x['neg'] and y['neg'] else float('nan')
    f3a=x['fl'].get('FLATF3',[float('nan')]*3); f3b=y['fl'].get('FLATF3',[float('nan')]*3)
    n20=f"{x['bl'][2]}>{y['bl'][2]}"; n40=f"{x['bl'][3]}>{y['bl'][3]}"
    flag=''
    if y['bl'][2]>x['bl'][2]+5 or y['bl'][3]>x['bl'][3]: flag+=' BLOTCH-WORSE'
    if dn==dn and dn<-0.15: flag+=' NEG-DOWN'
    if any(bb>aa+0.5 for aa,bb in zip(f3a,f3b)): flag+=' FLAT-WORSE'
    if y['oob'] not in ('0','?'): flag+=' OOB'
    if flag: worse.append(t)
    print(f"{t:44s} {dn:+7.3f} {n20:>12s} {n40:>8s}  {f3a[0]:.2f}/{f3a[1]:.2f}/{f3a[2]:.2f} -> {f3b[0]:.2f}/{f3b[1]:.2f}/{f3b[2]:.2f}{flag}")
print("\nREGRESSED CELLS:", len(worse)); [print(" ",t) for t in worse]

```

## `h_battery54.sh`

```
#!/bin/bash
# v5.4 B1 co-set: same battery on v54tree compiled defaults (rung + chroma thr).
# ONE encode at a time (machine rule). Full frames, per-plane, 12-frame arms.
cd /home/user/fromscratch/OMC_CLOUD/Project/.work
export TMPDIR=$PWD/scratch/tmp
V=v54tree; H=v53/omc_v5.3/harness
run_cell(){ # clip W H fmt depth bpp sh nf
  c=$1; W=$2; Hh=$3; fmt=$4; dep=$5; b=$6; sh=$7; nf=$8
  A=arms/${c}_${W}x${Hh}_${fmt}_${dep}.yuv
  [ -f $A ] || { echo "SKIP $A"; return; }
  tag=${c}_${W}x${Hh}_${fmt}_${dep}_bpp${b}
  shflag=""; [ "$sh" != "-" ] && shflag="--slice-h $sh"
  nice -n 19 $V/omc_enc -i $A -o out/$tag.omc -w $W -h $Hh --fmt $fmt --depth $dep --bpp $b -n $nf $shflag > out/$tag.enc.log 2>&1 || { echo "ENCFAIL $tag"; return; }
  nice -n 19 $V/omc_dec -i out/$tag.omc -o out/$tag.yuv > out/$tag.dec.log 2>&1
  neg=$(bash $H/negscore.sh $A out/$tag.yuv $W $Hh $fmt $dep $nf 2>/dev/null | tail -1)
  esh=$(python3 -c "
import sys
h=open('out/$tag.omc','rb').read(32); print(h[12])")
  bl=$(nice -n 19 python3 $H/blotch.py $A out/$tag.yuv $W $Hh $nf --sh $esh --fmt $fmt --depth $dep 2>/dev/null | tail -1)
  f2=$(nice -n 19 python3 $H/flatplane.py $A out/$tag.yuv $W $Hh 2 --fmt $fmt --depth $dep 2>/dev/null | tail -1)
  f3=$(nice -n 19 python3 $H/flatplane.py $A out/$tag.yuv $W $Hh 3 --fmt $fmt --depth $dep 2>/dev/null | tail -1)
  f11=$(nice -n 19 python3 $H/flatplane.py $A out/$tag.yuv $W $Hh 11 --fmt $fmt --depth $dep 2>/dev/null | tail -1)
  pt=$(nice -n 19 python3 $H/pitch.py $A out/$tag.yuv $W $Hh $nf --fmt $fmt --depth $dep --sh $esh 2>/dev/null | tail -1)
  gm=$(grep -oE "gamut: [0-9]+" out/$tag.enc.log | awk '{print $2}')
  echo "CELL $tag sh=$esh oob=${gm:-?} NEG=$neg BLOTCH[$bl] FLATF2[$f2] FLATF3[$f3] FLATF11[$f11] PITCH[$pt]"
  rm -f out/$tag.yuv
}
NF=12
for b in 0.5 1.0 2.0 4.0; do
  for c in dng cityalley bosphorus readysetgo; do run_cell $c 1920 1080 422 10 $b - $NF; done
  run_cell dng 1280 720 422 10 $b - $NF
  run_cell dng 3840 2160 422 10 $b - $NF
  [ "$b" = 0.5 -o "$b" = 1.0 ] && run_cell dng 7680 4320 422 10 $b - $NF
  [ "$b" = 0.5 -o "$b" = 1.0 ] && run_cell cityalley 7680 4320 422 10 $b - $NF
  run_cell cf_gfx 448 256 422 10 $b - $NF
  for fd in "422 8" "422 12" "444 8" "444 10" "444 12"; do set -- $fd; run_cell dng 1920 1080 $1 $2 $b - $NF; done
done
echo BATTERY-DONE

```

## `h_crawl54.sh`

```
#!/bin/bash
# Crawl battery on FROZEN masters (source tail 0 by construction), v5.4 defaults, rates 0.5/1.0/2.0.
cd /home/user/fromscratch/OMC_CLOUD/Project/.work
export TMPDIR=$PWD/scratch/tmp
V=v54tree
for b in 0.5 1.0 2.0; do
 for c in dng cityalley bosphorus readysetgo; do
  A=arms/frozen_${c}_1920x1080_422_10.yuv
  tag=frozen_${c}_bpp${b}
  nice -n 19 $V/omc_enc -i $A -o out/$tag.omc -w 1920 -h 1080 --fmt 422 --depth 10 --bpp $b -n 12 > out/$tag.enc.log 2>&1
  nice -n 19 $V/omc_dec -i out/$tag.omc -o out/$tag.yuv > /dev/null 2>&1
  echo "CRAWL $tag $(nice -n 19 python3 $V/tests/ants.py $A out/$tag.yuv 1920 1080 422 10 2>/dev/null | tail -3 | tr '\n' ' ')"
  rm -f out/$tag.yuv
 done
done
echo CRAWL-DONE

```

## `h_a4.sh`

```
#!/bin/bash
# A4 chains for the v5.4 tree (rung active at >=0.75bpp cells).
# a4chain ARM W H FMT DEPTH BPP NF GENS MODE
cd /home/user/fromscratch/OMC_CLOUD/Project/.work
E=v54tree/omc_enc; D=v54tree/omc_dec
export TMPDIR=$PWD/scratch/tmp
a4(){ A=$1; WD=$2; HT=$3; FMT=$4; DP=$5; BPP=$6; NF=$7; G=$8; M=$9
  free=$(df --output=avail -B1M $PWD | tail -1)
  need=$(( WD*HT*4*NF*(G+1)/1000000 + 512 ))
  [ "$free" -lt "$need" ] && { echo "HARNESS ERROR: disk $free MB < $need MB"; return 99; }
  tmp=$(mktemp -d $PWD/scratch/tmp/a4.XXXXXX)
  cur=$A; SH=$([ $HT -le 720 ] && echo 8 || echo 16); CHh=$(( (HT+SH-1)/SH*SH ))
  ok=PASS; why=""
  for g in $(seq 1 $G); do
    if [ "$M" = cdr ] && [ $g -gt 1 ]; then
      $E -i $cur -o $tmp/s$g.omc -w $WD -h $CHh --fmt $FMT --depth $DP --bpp $BPP -n $NF --display-w $WD --display-h $HT --cdr-in >/dev/null 2>&1
    else
      $E -i $cur -o $tmp/s$g.omc -w $WD -h $HT --fmt $FMT --depth $DP --bpp $BPP -n $NF >/dev/null 2>&1
    fi
    [ -s $tmp/s$g.omc ] || { ok=FAIL; why="enc-gen$g"; break; }
    if [ "$M" = cdr ]; then $D -i $tmp/s$g.omc --cdr -o $tmp/d$g.yuv >/dev/null 2>&1
    else $D -i $tmp/s$g.omc -o $tmp/d$g.yuv >/dev/null 2>&1; fi
    [ -s $tmp/d$g.yuv ] || { ok=FAIL; why="dec-gen$g"; break; }
    if [ $g -ge 2 ]; then
      cmp -s $tmp/d$g.yuv $tmp/d$((g-1)).yuv || { ok=FAIL; why="pixels-gen$g"; break; }
      [ $g -ge 3 ] && { cmp -s $tmp/s$g.omc $tmp/s$((g-1)).omc || { ok=FAIL; why="stream-gen$g"; break; }; }
    fi
    cur=$tmp/d$g.yuv
  done
  echo "A4 $(basename $A .yuv)@$BPP/$FMT-$DP $M gens=$G : $ok $why"
  rm -rf $tmp
}
# gamut incl the rates the rung changes (1.0/2.0), both modes
for M in baseband cdr; do
  a4 arms/dng_1920x1080_422_10.yuv 1920 1080 422 10 1.0 12 5 $M
  a4 arms/cityalley_1920x1080_422_10.yuv 1920 1080 422 10 1.0 12 5 $M
  a4 arms/bosphorus_1920x1080_422_10.yuv 1920 1080 422 10 2.0 12 5 $M
  a4 arms/dng_1920x1080_422_10.yuv 1920 1080 422 10 0.5 12 5 $M
  a4 arms/dng_1280x720_422_10.yuv 1280 720 422 10 1.0 12 5 $M
  a4 arms/dng_1920x1080_444_10.yuv 1920 1080 444 10 1.0 12 5 $M
  a4 arms/dng_1920x1080_422_8.yuv 1920 1080 422 8 2.0 12 5 $M
  a4 arms/dng_1920x1080_444_12.yuv 1920 1080 444 12 1.0 12 5 $M
  a4 arms/cf_gfx_448x256_422_10.yuv 448 256 422 10 1.0 12 5 $M
  a4 arms/readysetgo_1920x1080_422_10.yuv 1920 1080 422 10 4.0 12 5 $M
done
echo A4-DONE

```

## `h_a4_final.sh`

```
#!/bin/bash
# A4 chains for the v5.4 tree (rung active at >=0.75bpp cells).
# a4chain ARM W H FMT DEPTH BPP NF GENS MODE
cd /home/user/fromscratch/OMC_CLOUD/Project/.work
E=v54tree/omc_enc; D=v54tree/omc_dec
export TMPDIR=$PWD/scratch/tmp
a4(){ A=$1; WD=$2; HT=$3; FMT=$4; DP=$5; BPP=$6; NF=$7; G=$8; M=$9
  free=$(df --output=avail -B1M $PWD | tail -1)
  need=$(( WD*HT*4*NF*(G+1)/1000000 + 512 ))
  [ "$free" -lt "$need" ] && { echo "HARNESS ERROR: disk $free MB < $need MB"; return 99; }
  tmp=$(mktemp -d $PWD/scratch/tmp/a4.XXXXXX)
  cur=$A; SH=$([ $HT -le 720 ] && echo 8 || echo 16); CHh=$(( (HT+SH-1)/SH*SH ))
  ok=PASS; why=""
  for g in $(seq 1 $G); do
    if [ "$M" = cdr ] && [ $g -gt 1 ]; then
      $E -i $cur -o $tmp/s$g.omc -w $WD -h $CHh --fmt $FMT --depth $DP --bpp $BPP -n $NF --display-w $WD --display-h $HT --cdr-in >/dev/null 2>&1
    else
      $E -i $cur -o $tmp/s$g.omc -w $WD -h $HT --fmt $FMT --depth $DP --bpp $BPP -n $NF >/dev/null 2>&1
    fi
    [ -s $tmp/s$g.omc ] || { ok=FAIL; why="enc-gen$g"; break; }
    if [ "$M" = cdr ]; then $D -i $tmp/s$g.omc --cdr -o $tmp/d$g.yuv >/dev/null 2>&1
    else $D -i $tmp/s$g.omc -o $tmp/d$g.yuv >/dev/null 2>&1; fi
    [ -s $tmp/d$g.yuv ] || { ok=FAIL; why="dec-gen$g"; break; }
    if [ $g -ge 2 ]; then
      cmp -s $tmp/d$g.yuv $tmp/d$((g-1)).yuv || { ok=FAIL; why="pixels-gen$g"; break; }
      [ $g -ge 3 ] && { cmp -s $tmp/s$g.omc $tmp/s$((g-1)).omc || { ok=FAIL; why="stream-gen$g"; break; }; }
    fi
    cur=$tmp/d$g.yuv
  done
  echo "A4 $(basename $A .yuv)@$BPP/$FMT-$DP $M gens=$G : $ok $why"
  rm -rf $tmp
}
# gamut incl the rates the rung changes (1.0/2.0), both modes
for M in baseband cdr; do
  a4 arms/dng_1920x1080_422_10.yuv 1920 1080 422 10 1.0 12 12 $M
  a4 arms/cityalley_1920x1080_422_10.yuv 1920 1080 422 10 1.0 12 12 $M
  a4 arms/bosphorus_1920x1080_422_10.yuv 1920 1080 422 10 2.0 12 12 $M
  a4 arms/dng_1920x1080_422_10.yuv 1920 1080 422 10 0.5 12 12 $M
  a4 arms/dng_1280x720_422_10.yuv 1280 720 422 10 1.0 12 12 $M
  a4 arms/dng_1920x1080_444_10.yuv 1920 1080 444 10 1.0 12 12 $M
  a4 arms/dng_1920x1080_422_8.yuv 1920 1080 422 8 2.0 12 12 $M
  a4 arms/dng_1920x1080_444_12.yuv 1920 1080 444 12 1.0 12 12 $M
  a4 arms/cf_gfx_448x256_422_10.yuv 448 256 422 10 1.0 12 12 $M
  a4 arms/readysetgo_1920x1080_422_10.yuv 1920 1080 422 10 4.0 12 12 $M
done
echo A4-DONE

```

## `h_pulse_rsg.sh`

```
#!/bin/bash
cd /home/user/fromscratch/OMC_CLOUD/Project/.work
A=arms/frozen120_readysetgo_1920x1080_422_10.yuv
nice -n 19 v54tree/omc_enc -i $A -o out/rg.omc -w 1920 -h 1080 --fmt 422 --depth 10 --bpp 2.0 -n 120 >/dev/null 2>&1 || { echo ENC-FAIL; exit 1; }
nice -n 19 v54tree/omc_dec -i out/rg.omc -o out/rg.yuv >/dev/null 2>&1 || { echo DEC-FAIL; exit 1; }
nice -n 19 python3 pulse.py $A out/rg.yuv 1920 1080 120
echo RSG-PULSE-DONE

```


---

# OPEN ITEMS REGISTER (v5.4 close)

| item | state | route |
|---|---|---|
| THE CLAMP QUESTION (§B3.7) | measured at gen-1 (+3.8 NEG cf_gfx, deep tails 5–20x down); OWNER ruling gates the clamptree sandbox (12+ gen chains standard) | owner + §12.22/HVBC docs-first |
| Chroma paired-amplitude (§B4.4) | designed; lattice-admission surgery flagged high-risk; residual = 2-row paint parity ×1.36 | last B code change, own cycle |
| dng720p pitch ×20–30 | co-located with its repair-bound smudge cluster | clamp bucket |
| dng_444_10@1.0 4-block tail (§B1.7) | diagnosed repair-cut collateral (s58 near-rail) | clamp bucket |
| 16-bit / 4:0:0 / 4:4:4:4 | NOT IMPLEMENTED in the codec; owner ruled: named backlog, outside B closure | feature backlog |
| Refresh quality ramp (§B2.5) | rate physics; levers recorded (§48 boost now live, W scheduling) | Task C "ramp invisibility" |
| Refresh-on-demand + verified concealment + block patches | design seeds recorded with owner constraints (no new stores/DDR; R unlock; cut-ramp masking) | Task C |
| PLAN-SD / TPART / PBAND / FILLELIG modes / grid-hold | built, measured, default-off with full falsification records | levers, revival paths noted |

# OWNER RULINGS LOG (this session)

1. Finish B completely (build→test→adversarial→codec+ledger) before C or anything else.
2. One change at a time; no rebuilds during batteries.
3. Root cause over repair; symptom machinery is a last resort.
4. Engine replacement permitted IF it truly solves and breaks nothing — docs/ledger/constraints consultation first.
5. Crawl must not become pulsation; source-referenced instruments (pulse.py built).
6. The 2.0bpp wall-clock 5x must be shown not to translate to FPGA latency (Task E item; static high-rate content = the verify-walk stress case).
7. Sub-1ms must hold to mathematical losslessness (Task E rate axis to lossless).
8. Never just design — always build, test, adversarially test, then land in codec and ledger.
9. Full gamut per the prompt's definition before "done"; owner ruled gamut = implemented formats, exhaustively; final closure chains WAY beyond 4 generations (12+ standard adopted; interim 5-gen OK).
10. Smudge work must use the §51.15 map harness and compare OMC against source.


---

# B5. THE ZERO BAR — closing residuals the "no worse" framing had parked

Owner (2026-09-01): *"not becoming worse was not the ask. the ask was for the
artifacts to be gone."* Every class is henceforth graded against zero; the
rung-0 byte-identity-to-v5.3 choice is outranked where it holds a residual.

## B5.1 The chroma rung (crung) — 4:4:4@0.5 chroma flatness to 0.00

New per-context `fill_crung` (>= fill_rung; 1 from 0.125 b/cs): the CHROMA
offer threshold engages one notch below the luma rung. Measured: 444_10@0.5
Cb 3.75 → **0.00** at NEG 87.39 → **89.04 (+1.65)**; cityalley@0.5 chroma
cleans with NEG +0.5..+1.3. First build extended the ELIGIBILITY relax down
too and **G-T5-CALM2a/2b failed** — the calm kill moves s across the 4/5
admission line between generations (the recorded DIVEFF shape); the relax
keeps its luma-rung key, the threshold (calm-safe: sum > 0) extends alone,
and all 97 gates pass. Normative minor-14 rider (decoder derives crung from
config). Tail watch: 444_10@0.5 n>40 9→11 worst −103 — train to judge.

## B5.2 The refresh boost knee (queued change)

RBOOST sweep on frozen dng@1.0: 50 → 16.2/14.2/15.2, 75 → 12.4/11.7/12.0,
100 → **12.1/10.0/10.5** — the ramp narrows monotonically; the self-limiting
pool cap bounds the shave. Default-raise cycle (with full-gamut cost
measurement) queued after the B5.1 train.


---

# ZERO-BAR SCORECARD (closure run, v5.4 tip, 2026-09-01)

## FLATNESS (target 0.00% every plane) — nonzero cells:
  bosphorus_1920x1080_422_10_bpp0.5: Y/Cb/Cr 2.93/0.0/0.0%
  bosphorus_1920x1080_422_10_bpp1.0: Y/Cb/Cr 0.13/0.0/0.0%
  bosphorus_1920x1080_422_10_bpp2.0: Y/Cb/Cr 1.3/0.0/0.0%
  cf_gfx_448x256_422_10_bpp0.5: Y/Cb/Cr 4.28/0.0/0.0%
  cf_gfx_448x256_422_10_bpp1.0: Y/Cb/Cr 4.05/0.0/0.0%
  cf_gfx_448x256_422_10_bpp2.0: Y/Cb/Cr 3.15/0.0/0.0%
  cityalley_1920x1080_422_10_bpp0.5: Y/Cb/Cr 0.8/0.03/0.64%
  cityalley_1920x1080_422_10_bpp1.0: Y/Cb/Cr 0.36/0.0/0.0%
  cityalley_1920x1080_422_10_bpp2.0: Y/Cb/Cr 3.42/0.0/0.0%
  dng_1280x720_422_10_bpp0.5: Y/Cb/Cr 3.24/0.0/0.0%
  dng_1280x720_422_10_bpp1.0: Y/Cb/Cr 2.9/0.0/0.0%
  dng_1280x720_422_10_bpp2.0: Y/Cb/Cr 0.89/0.0/0.0%
  dng_1280x720_422_10_bpp4.0: Y/Cb/Cr 0.89/0.0/0.0%
  dng_1920x1080_422_10_bpp0.5: Y/Cb/Cr 0.07/0.0/0.0%
  dng_1920x1080_422_10_bpp2.0: Y/Cb/Cr 0.22/0.0/0.0%
  dng_1920x1080_422_10_bpp4.0: Y/Cb/Cr 0.06/0.0/0.0%
  dng_1920x1080_422_12_bpp0.5: Y/Cb/Cr 0.06/0.0/0.0%
  dng_1920x1080_422_12_bpp2.0: Y/Cb/Cr 0.26/0.0/0.0%
  dng_1920x1080_422_12_bpp4.0: Y/Cb/Cr 0.06/0.0/0.0%
  dng_1920x1080_422_8_bpp0.5: Y/Cb/Cr 5.01/0.0/0.0%
  dng_1920x1080_422_8_bpp1.0: Y/Cb/Cr 0.07/0.0/0.0%
  dng_1920x1080_422_8_bpp2.0: Y/Cb/Cr 0.55/0.0/0.0%
  dng_1920x1080_422_8_bpp4.0: Y/Cb/Cr 0.12/0.0/0.0%
  dng_1920x1080_444_10_bpp0.5: Y/Cb/Cr 0.06/3.75/0.0%
  dng_1920x1080_444_10_bpp4.0: Y/Cb/Cr 0.06/0.0/0.0%
  dng_1920x1080_444_12_bpp0.5: Y/Cb/Cr 0.06/4.45/0.0%
  dng_1920x1080_444_12_bpp4.0: Y/Cb/Cr 0.06/0.0/0.0%
  dng_1920x1080_444_8_bpp0.5: Y/Cb/Cr 3.91/0.1/0.0%
  dng_1920x1080_444_8_bpp1.0: Y/Cb/Cr 0.09/0.0/0.0%
  dng_1920x1080_444_8_bpp2.0: Y/Cb/Cr 0.41/0.0/0.0%
  dng_1920x1080_444_8_bpp4.0: Y/Cb/Cr 0.29/0.0/0.0%
  dng_3840x2160_422_10_bpp2.0: Y/Cb/Cr 0.17/0.0/0.03%
  readysetgo_1920x1080_422_10_bpp0.5: Y/Cb/Cr 0.0/0.0/0.6%
  readysetgo_1920x1080_422_10_bpp2.0: Y/Cb/Cr 0.31/0.0/0.0%
  (34 of 50 cells nonzero; 0.5bpp rung-0 dominates — B5 chroma-rung in train)

## SMUDGES (target n>20 = 0) — nonzero cells:
  cf_gfx_448x256_422_10_bpp0.5: n>20 514 n>40 104
  cf_gfx_448x256_422_10_bpp1.0: n>20 26 n>40 2
  dng_1280x720_422_10_bpp0.5: n>20 620 n>40 159
  dng_1280x720_422_10_bpp1.0: n>20 5 n>40 0
  dng_1920x1080_422_10_bpp0.5: n>20 32 n>40 6
  dng_1920x1080_422_12_bpp0.5: n>20 24 n>40 4
  dng_1920x1080_422_8_bpp0.5: n>20 58 n>40 1
  dng_1920x1080_444_10_bpp0.5: n>20 43 n>40 9
  dng_1920x1080_444_10_bpp1.0: n>20 10 n>40 4
  dng_1920x1080_444_12_bpp0.5: n>20 122 n>40 15
  dng_1920x1080_444_12_bpp1.0: n>20 1 n>40 0
  dng_1920x1080_444_8_bpp0.5: n>20 83 n>40 7
  dng_3840x2160_422_10_bpp0.5: n>20 83 n>40 5
  dng_7680x4320_422_10_bpp0.5: n>20 13 n>40 0
  readysetgo_1920x1080_422_10_bpp0.5: n>20 25 n>40 0
  (15 of 50; dominated by repair-bound cells — clamp train running)

## CRAWL (frozen source; target tail 0.00) — all cells:
  frozen_bosphorus_bpp0.5: Y/Cb/Cr 1.48/2.54/2.53%
  frozen_bosphorus_bpp1.0: Y/Cb/Cr 0.85/1.16/1.06%
  frozen_bosphorus_bpp2.0: Y/Cb/Cr 0.32/0.59/0.74%
  frozen_cityalley_bpp0.5: Y/Cb/Cr 3.92/2.77/3.02%
  frozen_cityalley_bpp1.0: Y/Cb/Cr 1.61/0.60/0.84%
  frozen_cityalley_bpp2.0: Y/Cb/Cr 1.00/0.34/0.52%
  frozen_dng_bpp0.5: Y/Cb/Cr 12.85/18.92/18.19%
  frozen_dng_bpp1.0: Y/Cb/Cr 12.04/11.37/11.91%
  frozen_dng_bpp2.0: Y/Cb/Cr 10.41/9.44/10.47%
  frozen_readysetgo_bpp0.5: Y/Cb/Cr 6.65/6.76/9.71%
  frozen_readysetgo_bpp1.0: Y/Cb/Cr 3.96/3.79/5.92%
  frozen_readysetgo_bpp2.0: Y/Cb/Cr 1.85/2.59/4.41%

## SEAM/pitch (target = source-null ratio ~1x) — worst:
  dng_7680x4320_422_10_bpp0.5: x76.5/25.9/33.6
  cityalley_1920x1080_422_10_bpp1.0: x4.3/61.1/6.4
  dng_7680x4320_422_10_bpp1.0: x57.2/30.5/36.9
  cityalley_1920x1080_422_10_bpp2.0: x4.4/48.8/5.0
  cityalley_1920x1080_422_10_bpp0.5: x4.2/43.6/4.6
  cityalley_1920x1080_422_10_bpp4.0: x3.8/35.6/3.2

# CLAMP PROJECT CLOSE-OUT + REPAIR ROOT-CAUSE CYCLE (2026-09-01, post-compaction)
# (re-consolidated at end of day from B3_smudge.md / B5_zero.md -- those
#  files are authoritative for this day; this merge is verbatim)

## B3.7f CLAMP ships CDR-scoped — the 100% proof (2026-09-01, VERIFIED binary)

Owner ruling: solver path (C1 recovery) skipped; ship = CDR+clamp AND
baseband+repair, both 100% exact.  Clip-aware lock experiment PARKED in
clamptree behind OMC_CLAMPMODE=0 (byte-identical off; gated !cdr_input).
Its post-mortem, for the record: the pixel-domain verify was vacuous in v1
(centered-vs-biased domain constant); made honest, it proves quantizing
clip-contaminated coefficients essentially never reproduces the display
(35,582 rejections/frame, cf_gfx@0.5), and true clamp baseband chains do
NOT converge (gen8 still ~100k px moving).  Clipping destroys exactly the
information generation 2 needs; only C1-recovery could close it.

**CDR+clamp 12-generation chains: 10/10 PASS** across the implemented gamut
(422/444, 8/10/12-bit, 720p..1080p, 0.5..4.0 bpp, graphics incl.), every
generation encoded --no-gamut-strict, byte-exact committed pictures gen2+
and byte-identical streams gen3+.  Script h_a4_clampcdr.sh, log
logs/a4_cdrclamp12.log.  Wire checks: modes distinct on the wire; repair
default untouched (gamut_strict=12 restored in clamptree enc tool);
diagnostic "baseband-safe: NO" fires exactly when clamp is chosen.

## sect.51.20 Baseband repair vs clamp: the measured floor (2026-09-01)

Full-gamut gen-1 NEG gap, repair(default) vs clamp(--no-gamut-strict),
identical binary (logs/gapsweep.log):

  camera (dng/cityalley/readysetgo, 0.5-2.0bpp): gap 0.00-0.02 except
  dng@0.5 = 0.24;  444/12 = 0.06;  422/8 = 0.00.
  graphics cf_gfx: 3.79 @0.5bpp -> 0.46 @1.0 -> 0.03 @2.0.

Baseband+repair is ALREADY at clamp parity on camera content; the gap is
confined to rate-starved graphics and collapses as steps get finer -- the
cost is set by LATTICE-STEP GRANULARITY vs few-code excursions, not by the
repair's shape.  Four redesigns built and measured on cf_gfx@0.5, ALL worse
than shipped 78.484: bulk bidirectional steering (25.4; runaway without
boundary-sign fallback), one-band-per-pass steering ladder (67.8),
veto-population rescue by magnitude increase (76.8; increases re-violate
the same rail), near-free boundary flips (69.5; the flip is free for the
COEFFICIENT but its full-step pixel move still overshoots).  Attribution
knobs: keepfill +-0.000, llhold -0.18, esc2 7/8 +0.54 but FAILS
G-T5-GAMUT2c/CUT4 (harsh 3/4 is load-bearing; staged/noprog variants also
fail -- the pathology progresses slowly, evading stall detection).
Conclusion: the shipped repair is near the achievable floor for committed-
in-gamut baseband; the residual graphics-at-0.5bpp gap is structural and
belongs to CDR pipelines.  All experiment code stays in clamptree behind
default-off envs (OMC_GM_STEER/FREEFLIP/ESC3FROM, OMC_GM_MODE=20), each
verified byte-identical when off; NONE are promoted to v54tree.

## sect.51.21 STAGED DILATION — landed in clamptree (2026-09-01)

Root cause found by term-by-term attribution (owner directive: investigate,
don't label): the repair's reach dilation ("for filter reach", 1 band cell)
is the largest single damage term on dense-rail graphics — cf_gfx@0.5 NEG
78.484 -> 80.117 with it off, but G-T5-GAMUT2c NEEDS it.  Fix: stage it —
passes < OMC_GM_DILFROM repair the exact support only; the dilated reach
joins for pixels that persist, and a fallback-restarted slice gets full
reach from its first pass.  DEFAULT 2.  Evidence (verified binary, wire-
checked off-path byte-identity): 97/97 gates; full-gamut cost table — every
cell >= shipped (cf_gfx@0.5 +1.76, @1.0 +0.17, dng@0.5 +0.15, camera cells
+0.00x), oob=0 everywhere; 6x12-gen baseband chains PASS incl cf_gfx@0.5/1.0;
seam instruments: PITCH unchanged within noise, rowphase boundary/interior
ratio 1.096 -> 1.086.  DILFROM=6 and the fallback-bypass-only variant FAIL
G-T5-GAMUT2c (on record; do not re-try).  Graphics gap remaining vs clamp:
~2.0 NEG @0.5 (was 3.79) — investigation continues (sect.51.15 maps, depth
census, committed-stream diff).

## sect.51.22/23 The residual graphics gap: cause mapped, cheap levers exhausted

Instrumented findings (cf_gfx@0.5, verified binary, logs under scratch+notes):
excursions are DEEP (median band 9-128 codes, max 301 -- hard-edge ringing,
not shallow noise); the repair encode differs from the clamp encode in 42%%
of committed samples, but 99%% of its EXTRA display error lies >24 px from
any rail; 146/384 slices emit different plans, and the first plan divergence
precedes the first differing slice's own repair -- the repair's smaller
re-emissions leak freed bits into the frame pool and every later slice
re-fits.  Levers built and FALSIFIED on top of the landed 51.21 default:
plan pinning on re-encodes (51.22, exact no-op: Q5GREEDY off, planreset
already pins re-entry); budget containment (51.23, charging pre-repair cost:
-0.47 NEG -- downstream slices spend the freed bits WELL); intra softening
(INTRAFROM 8: -0.05; NOINTRA: +0.18 but oob=2, breaks the guarantee).  Both
new envs remain default-off, off-path byte-identity wire-verified.
Residual vs clamp: 2.03 NEG @0.5 (was 3.79), 0.29 @1.0, 0.02 @2.0.
Conclusion this cycle: the remainder is the aggregate cost of projecting
DEEP rail overshoots onto the lattice plus its temporal ripples; no
shape/plan/rate lever recovers it.  Next instruments if reopened: per-slice
damage-vs-repair-depth regression; temporal ripple isolation (frame-1-only
census); repair rate-efficiency (bits per cleared code).

## sect.51.24 CORRECTION to 51.22/23's "structural wall" claim + DEFERRAL

Owner directed a documentation check before accepting a bitrate wall, and the
record contradicts the strong form of my claim.  GAMUT_STRICT_COST.md
(2026-08-18, reading TEMPORAL_T5_v4.md's own cost table): dense graphics
masters repaired CHEAPLY even then (gfxF003_444_8@0.5: 220,236 samples
repaired at -0.51 NEG; gfx1080_444_12@0.5: +0.11, an IMPROVEMENT), while the
pathological cost sat on camera cells (city1080@0.5: 104 samples at -9.83)
-- and that camera pathology has since been engineered away (today's gap
0.00-0.02).  cf_gfx@0.5's own history: repair-on NEG 67.5 -> 74.4 (ESCMODE,
sect.51.18.4) -> 78.5 (v5.4 tip) -> 80.25 (sect.51.21) against clamp 82.28.
The gap has FALLEN at every cycle that root-caused a term; "structural wall"
was overstated -- what is true is that each remaining term costs more to
find, and the lattice-granularity floor argument bounds the MINIMAL move at
this rate, not the achievable end state.

[SUPERSEDED same day by the owner's later explicit grant -- see ruling 14
in the rulings log and sect.51.25; kept for the sequence of events.]
OWNER RULING (2026-09-01, corrected record): the ruling was CONDITIONAL --
table the graphics-gap work only IF the documentation check confirmed a true
bitrate wall.  The check REFUTED the wall (this section).  The condition
fails, so NOTHING IS DEFERRED: the graphics-gap work remains active Task B
work and the investigation continues now.  (First recording of this ruling
mis-stated it as an unconditional deferral -- corrected same day, called
out by the owner.)

## sect.51.25 Knob-space exhaustion at cf_gfx@0.5 (on top of 51.21) + HVBC input

Env matrix on the staged-dilation default (falsified levers, on record):
ESCMODE 4/6 (more fine-first passes before the LL-inclusive rule): 76.7 --
WORSE by 3.5, the historical preference INVERTS once dilation is staged;
LLHOLD 4/6/8/12: 80.18..80.44 -- noise-band around the 80.25 default, not a
landable lever.  Every remaining single-knob move at this cell is <= +-0.2
or negative.  The remaining ~2.0 vs clamp requires either structural rate
work (per-slice allocation is fixed by CBR today -- reallocating toward
rail slices is bitstream/rate-control work in Task C's domain) or the
bitrate headroom C itself buys.  The item stays ACTIVE (owner: wall not
proven); its next levers are C-domain levers.

HVBC documentation survey -- WITH THE OWNER'S CAVEAT (2026-09-01): HVBC was
SHELVED for unresolved artifacts: abundant completely-flat "waxy" detail in
16-line-high rows.  Every HVBC quality claim below coexisted with that
defect, so none of its numbers are validated wins; they are leads.  The
"wavelets code flats nearly free" finding is plausibly the ROOT of the wax
(free == sub-threshold texture erased -- the very failure OMC's grain fill
exists to repair), and 16-line rows match its stripe architecture.  Any
tool imported from HVBC (palette included) must pass OMC's flatness
instruments before it is trusted.  Survey findings: (1) HVBC's out-of-range philosophy converged on exactly the
clamp architecture -- signed unclipped planes in-loop, ONE clip at final
display conversion; they paid for in-loop clipping twice (phantom bug hunt
+ a user-visible signed-chroma wipe).  Corroborates B3.7f's CDR+clamp
design.  (2) Palette/indexed coding: validated 7-18%% byte win on
flat-colour content, never built (their roadmap #46) -- a royalty-free
candidate for OMC graphics AFTER C, if the gap survives C's rate gains.
(3) Wavelets code flats nearly free; the graphics weakness is EDGE ringing
-- matching our deep-excursion census exactly.  (4) No evidence anywhere
that starved-rate graphics was "fine": HVBC's operating floor is ~0.2 bpp
with different accounting.

## sect.51.26 Staged dilation at FULL battery scale (b5 -> dil isolation) —
## verdict MIXED; landing needs a tail-tuning cycle

With the honest comparison tool (51.25 note: cmp_batt previously ignored its
arguments; every prior "battery comparison" this day was phantom):
WINS: NEG up broadly -- cf_gfx@0.5 +1.311 (tails ALSO better: n20 534->458,
n40 96->64), cf_gfx@1.0 +0.170 (2->0), dng@0.5 +0.132 (25->16), 4K@0.5
+0.240 (83->33), 444_12@0.5 +0.127 with n40 35->6, 444_10@1.0 +0.050
(tails 10->0, 4->0).
REGRESSIONS (smudge-tail class, zero-bar violations): 720p@0.5 n40 103->196
(near-doubled), 720p@1.0 n40 0->17 (new), 422_8@0.5 n40 1->22, 444_8@0.5
n40 6->15 + flat Y 3.93->5.11, 422_12@0.5 4->7, 4K@1.0 small.  Pattern:
720p (sh8 rung) and 8-bit cells at 0.5 -- the exact-support-only early
passes leave DEEPER local residual clusters where the dilated reach used to
spread the correction.  My 13-cell pre-landing train logged NEG+oob only
and MISSED the tail regressions -- pre-landing trains must carry the blotch
column henceforth.
DISPOSITION: DILFROM=2 stays landed pending the tuning cycle (chains/gates/
crawl unaffected -- exactness intact); IMMEDIATELY after the running train
completes, a tuning cycle (DILFROM=1, per-plane or depth-gated staging)
targets the six tail cells; if no setting keeps the wins and clears the
tails, the default reverts to 0 and 51.21 re-enters as opt-in.
Combined closure->dil at B5's target cells nets well: 444_10@0.5 flat
3.75->0.00 with n40 9->4; 444_12@0.5 flat 4.45->0.00 with n40 15->6.

## sect.51.27 INSTRUMENT AUDIT after the cmp_batt incident (owner-directed)

Owner: with one instrument proven broken, nothing proceeds on trust.  Audit
of every instrument in use, method = two different inputs must yield two
different outputs, same input twice must yield the same output:
  negscore.sh   ARG-HONORING + DETERMINISTIC (80.247 / 82.278 / 80.247)
  blotch.py     ARG-HONORING
  pitch.py      ARG-HONORING
  flatplane.py  ARG-HONORING (first probe coincided -- repair and clamp
                decodes genuinely share 4.73% flatness; sharper probe:
                source-vs-source 0.00%, posterized source 12.16%)
  pulse.py / ants_local.py: no hardcoded paths found
  cmp_batt.py   WAS BROKEN (ignored argv); fixed + guarded (51.25/B5.3)
Reproducibility spot-check: the ESCMODE=4 falsification re-encodes to a
BYTE-IDENTICAL stream and the identical NEG (76.729).

TAINT MAP -- what rested on the broken tool vs what stands:
  TAINTED (all corrected same day): the B5-train stale-binary VOID (reversed,
  B5.3); the phantom B5 "regressions" (replaced by the honest b5->closure
  comparison); every "battery rows byte-identical" claim.
  CLEAN (direct audited instruments, unaffected by cmp_batt): the entire
  cf_gfx@0.5 lever campaign incl. all falsifications (negscore direct);
  the repair-vs-clamp gap sweep; the excursion/ring/per-frame censuses
  (raw sample math); the CDR 10/10 chain proofs and all byte-exactness
  results (cmp on wire bytes); 97/97 gates; restore checks; wire checks.
  PROCESS GAP (mine, not the tool's): the 51.21 pre-landing train logged
  NEG+oob without the blotch column and missed the tail regressions; the
  blotch column is now mandatory in pre-landing trains.
Standing rule added: a new comparison/instrument script is not trusted
until it passes the two-inputs/two-outputs + determinism audit ON THE WIRE.

## sect.51.28 Depth-gated staging: FALSIFIED (sandbox A/B, on record)

The per-slice depth gate (stage only when pass-0 max excursion depth >=
maxv>>5) FAILS the A/B: it surrenders part of the graphics win (cf_gfx@0.5
80.25 -> 78.98, tails 426/64 -> 486/96), worsens dng@0.5 (492/123 ->
582/170), leaves 720p@1.0's regression untouched (its p90-deep slices still
stage), helps 8-bit, and wrecks 12-bit (29/7 -> 88/57).  The simple depth
story does not survive per-slice granularity.  Gate stays in the sandbox
default -1 but the LANDING PLAN drops it.  Revised plan, one change at a
time: (1) scope crung to 4:4:4 (its own record says 4:2:2@0.5 chroma was
already clean at rung 0; measured at 720p@0.5 the scoped state flips
staging from harmful to the cell's best-ever numbers 436/78); full battery;
(2) adjudicate the DILFROM default on that clean state's remaining tail
set.  Zero-bar rule stands: if the remaining regressions do not clear, the
staging default reverts while the graphics win is pursued by other means.


## B5.3 CORRECTION OF THE CORRECTION: the B5.1 train was VALID; the
## comparison tool was broken (2026-09-01)

The earlier B5.3 entry declared the train void on a stale binary.  That was
WRONG.  Root cause of the wrong verdict: `cmp_batt.py` HARDCODED its two log
paths and silently ignored command-line arguments, so every "comparison" run
that day diffed the same two unrelated old logs (v5.3-baseline vs v5.4-coset)
regardless of what was asked -- producing phantom "byte-identical" rows and
phantom "regressions" that seeded the stale-binary story.  The tool now
requires its two arguments (and refuses to run without them); the train logs
are UN-quarantined (battery/crawl/a4_v54_b5.log).

THE REAL B5.1 BATTERY VERDICT (closure -> B5 train, honest tool; only
0.5bpp cells move, exactly the crung-eligible set):
  TARGET MET: 444_10@0.5 Cb flatness 3.75 -> 0.00; 444_12@0.5 Cb 4.45 -> 0.00.
  COSTS at the same cells: NEG -0.169 / -0.161; blotch tails up
  (444_10 n20 43->54, n40 9->11; 444_12 n40 15->35) -- the tail watch B5.1
  itself flagged ("n>40 9->11 -- train to judge") is real and adverse.
  Elsewhere: 720p@0.5 +0.085 NEG with tails BETTER (620->493 / 159->103);
  cf_gfx@0.5 +0.097 NEG but n20 514->534 and flat Y 4.28->5.41 (worse);
  8K/4K@0.5 small NEG dips (-0.031/-0.034).
  a4 17/17 PASS, crawl clean (those phases of the train stand as-is).
OPEN (zero-bar): B5.1 closes the chroma-flatness class at its target cells
but WORSENS the smudge-tail class there (n40 15->35).  Adjudication of
keep/tune deferred to the 51.21 train comparison (b5 -> dil isolates the
dilation change; closure -> dil shows the combined tip), then a B5 tail
follow-up cycle if the tails stand.

## B5.4 crung BREAKS CDR+clamp generation exactness (found 2026-09-01 evening)

The v54tree-binary CDR-clamp proof (10 arms, 12 generations, clamp mode at
every generation) failed ONE arm: dng_1920x1080_422_10@0.5, pixels-gen2
(logs/a4_cdrclamp54.log; the other 9 PASS).  Attributed by 2-generation
repro (scratch/tmp/cdrfail method, recorded in RESUME_STATE): 12 frames
REQUIRED (4-frame chain exact -- the R=8 refresh cycle is implicated);
default = gen2 DIFF, OMC_FILLTHR_C=3 = gen2 EXACT.  DILFROM is irrelevant
in clamp mode (repair off).  VERDICT: B5.1's rung-0 crung extension breaks
the chroma-fill generation fixed point under CDR+clamp with refresh
cycling.  Baseband (repair-on) chains are NOT affected (20/20 PASS incl.
this cell in both modes, logs/a4_v54_dil12.log).  NEXT CYCLE (first task):
root-cause the fill fixed point (suspect: a rung-0/refresh-phase path the
B1 sum>0 guard does not cover), then the 444-scoping (sect.51.26 plan),
and the CDR proof set gains a 444@0.5 arm -- crung's own target cell is
absent from the 10-arm set; if it also fails, scoping is insufficient and
B5 must not ship anywhere until the fixed point is repaired.


## B5.5 ROOT CAUSE + FIX of the CDR-clamp exactness break: lock tie-break by
## ACTUAL size (sect.B5.5, env OMC_LOCK_TIEACT, default 1)

Owner directed a history check first: docs/TEMPORAL_T5.md 5.5.4/5.5.6 record
this exact class twice ("estimate-based selection was off by +-bytes ...
starved slice 35"; group-id jitter "+4 / +70 bytes ... starved a later
slice") -- so this is a NEW jitter source of a KNOWN class, not new theory.
Diagnosis chain (all on the encoder's own dumps, wire-verified): gen-2
pixels first differ at frame 8 = the R=8 refresh group (slices 48-55),
which fails to lock; gen-1 coded s48 with payload EXACTLY = its hard budget
(22968 bits); gen-2's hard budget there is 8 bits smaller because gen-2 had
spent 1 byte more earlier (the causal-bank prefix bound depends on spent
bits); the extra byte comes from LOCKED slices that emit gen-1's identical
plan +3 bits (f2 s16, f6 s33/s42, f7 s33, f8 s18): in each, ONE chroma band
is coded INTER at gen 2 where gen 1 coded it INTRA+fill.  Mechanism: the
prediction already carries the (frame-static) grain fill, so the inter
residual is all-zero and BOTH modes reproduce the pixels; lock_verify broke
the tie by the bc[] ESTIMATE, which does not price the Q5 skip-flag symbol
an inter band carries (+3 bits).  crung's role: it raised the number of
filled chroma bands at 0.5 bpp (thr 0), making such ties common; the hole
itself is mode-independent and latent in baseband too (only a budget-edge
slice exposes it).
FIX: lock_verify reports free-choice bands (+ the alternate mode's fill
bit); the candidate walk flips each such band and keeps whichever variant
is ACTUALLY smaller (lock_trial_bits), greedily and deterministically.
Flips are gain-neutral (5.7 fixed-point classes) and both variants are
already pixel-verified.  Restores the induction (section 8 step 4): the
per-band min-actual is <= gen 1's own assignment.  Applied at both lock
sites.  Restore incantation += OMC_LOCK_TIEACT=0.
EVIDENCE (verified binary): gen-1 stream byte-identical (fix acts only on
locked ties); the failing 12-frame CDR-clamp chain: gen2 EXACT, gen3 stream
== gen2; OMC_LOCK_TIEACT=0 reproduces the old gen-2 bytes exactly.  Gates,
restore, full battery(+blotch)/crawl/20-chain A4 and the CDR proof set
(now 12 arms incl. 444_10@0.5 and 444_12@0.5, crung's target cells) are
running as this is written -- verdict follows.


## sect.51.29 Fresh-eyes review (owner-directed, documentation-first) — outcomes

Full text: notes_disk/REVIEW_2026-09-01_fresh_eyes_DRAFT.md.  Ledger-
affecting outcomes:
1. The sect.51.26/51.28 plan "scope crung to 4:4:4" is WITHDRAWN: its
   premise (4:2:2@0.5 chroma clean at rung 0) is contradicted by
   ZERO_SCORECARD (cityalley@0.5 Cr 0.64 %, readysetgo@0.5 Cr 0.60 %) and by
   B5.1's own 4:2:2 win.  The tail-matrix "crung-off" control
   (OMC_FILLTHR_C=3) is not a clean control (thr 2 measured worse, v5.3
   S.1-OPEN-B).  Replacement: clean lever OMC_FILLCRUNG=0, then sect.51.15
   attribution of the crung x dilation interaction at 720p@0.5 (luma AND
   chroma), then fix the interaction.
2. B5.5 tie-break: not exact under the Q5 per-plane coupling; exact
   per-plane variant (B5.5b) prepared, applies after the train.
3. New permanent gate proposed: G-T5-SPEND (gen-2 locked slice bytes <=
   gen-1, per slice; ~1 in 100 slices sit exactly at the hard budget).
4. Repair reach: the +-1-cell dilation contradicts the measured GM_BASIS
   support boxes; the exact-basis SOLVER was falsified (v5.3 45.10, replan
   churn), the eligibility-box variant was not -- one bounded arm in the
   next repair cycle, no promise.
5. HALF-RUNG (v5.3 38.4, designed, docs-first) is the mechanism-level
   attack on the GFX@0.5 granularity floor; schedule inside Task C.
6. Record-consistency notes: rung-0 byte-identity to v5.3 no longer holds
   at the tip (do not cite it); sect.51.24 is superseded by the owner's
   later deferral grant (ruling 14); RBOOST's own A4 evidence is 5-gen --
   the running 12-gen train covers it de facto; B5.5's lock-only change
   needs no live-rule mirror (the live path never faces the tie).
7. Instruments still missing that the record asked for: cost per repaired
   slice; blotch contiguity column; chroma-wash measurement (readers are
   luma-only).


## sect.51.30 Smudge instruments extended to ALL THREE PLANES + a CONTIGUITY column (2026-09-01)

**Why, from the record.** LEDGER_v5_3 §78.2 records that `blotch.py`, `levelmap.py` and
`artifactmap.py` all read `[:W*H]` — the Y plane only — so **chroma level error had never been
measured anywhere in the project**, although §50.1 item 4 (city "colour-block updating") is a
chroma observation and the prompt rule is *never measure only luma or only chroma*. §80.4b
records the second gap: the ship set "improved" the aggregate while **relocating** the wash
into a bar, and `blotch.py` "cannot distinguish five scattered blocks from one long bar" — the
contiguity column was named as the missing one, to be added to the SHIPPED tool, not a fourth
instrument. Both gaps are closed here, in the shipped tools, before any further smudge work.
The owner-verified method (§50.7/§51.15) is unchanged: map first, regions off the map, no
shape prior; only the plane it is applied to becomes selectable.

**What changed (all in `v54tree/harness/`, shipped in v5.4):**
- `blotch.py`: one line per plane (Y, Cb, Cr), each on its OWN LL support ((slice_h/4) rows ×
  32 plane columns, because the band layout is per plane width), with worst / p99.9 / n>20 /
  n>40 and **`cont>20`** = largest 4-connected component of blocks past 20 codes in any one
  frame, with its frame and top-left corner. The **legacy luma line is printed LAST and is
  byte-identical to v5.3 up to `n>40 N`**, so every battery that does
  `tail -1 | grep -oE "n>20 [0-9]+\s+n>40 [0-9]+"` is unchanged. `--fmt 400` accepted.
- `levelmap.py`: `--plane Y|Cb|Cr|all` (`all` writes `_Y/_Cb/_Cr` files; chroma at its own
  raster, 960 wide at 4:2:2). Default Y byte-identical to v5.3.
- `artifactmap.py`: `--plane Y|Cb|Cr`; tag gains `_Cb`/`_Cr`; the "src" column is then mean
  source chroma. Default Y byte-identical to v5.3 at 10-bit. One behaviour change at OTHER
  depths, deliberate: the error is now put on the common 10-bit scale before the ±40 map (the
  v5.3 tool assumed 10-bit, so at 8-bit its map saturated at 160 codes on the 10-bit scale —
  the depth-scale trap §51.12 rule 4 warns about, in the instrument this time).
- `h_battery54.sh`: `H=v54tree/harness`; the full blotch output is kept per cell
  (`out/<tag>.blotch.txt`) and the chroma lines are appended to the CELL line as `BLOTCHC[...]`.

**Instrument audit (§51.27 discipline: two inputs → two outputs; determinism; old-equivalence),
`arms/dng_1920x1080_422_10.yuv`, 6 frames, decodes `out/base_dng05.yuv` / `out/ia1_dng05.yuv`:**
```
OLD blotch (v54tree_bak = v5.3 tool), base:
BLOTCH(10b-scale) -71.0 at f0 r976 c960  p99.9 14.1  n>20 20  n>40 3
NEW blotch, base (run 1 == run 2, cmp IDENTICAL):
BLOTCH Y  worst   -71.0 at f0 r976 c960  p99.9  14.1  n>20 20  n>40 3  cont>20 4 (f0 r976 c960)
BLOTCH Cb worst   +17.9 at f0 r412 c256  p99.9  12.2  n>20 0  n>40 0  cont>20 0 (f0 r0 c0)
BLOTCH Cr worst   +19.5 at f0 r972 c928  p99.9  11.0  n>20 0  n>40 0  cont>20 0 (f0 r0 c0)
BLOTCH(10b-scale) -71.0 at f0 r976 c960  p99.9 14.1  n>20 20  n>40 3  cont>20 4
NEW blotch, ia1 (DIFFERENT from base, as it must be):
BLOTCH Y  worst  -119.5 at f4 r988 c864  p99.9  14.2  n>20 26  n>40 7  cont>20 6 (f4 r984 c832)
BLOTCH Cb worst   +18.8 at f4 r988 c928  p99.9  12.1  n>20 0  n>40 0  cont>20 0 (f0 r0 c0)
BLOTCH Cr worst   +19.5 at f0 r972 c928  p99.9  11.0  n>20 0  n>40 0  cont>20 0 (f0 r0 c0)
legacy prefix of the new last line == old tool output: EXACT (diff empty)
444 self-compare (arms/dng_1920x1080_444_10.yuv vs itself, --fmt 444): all planes 0.0 / 0 / 0
artifactmap NEW vs OLD, luma f3, base: regions.txt IDENTICAL, ERRORMAP.png IDENTICAL, run1==run2
artifactmap --plane Cb: base 50 bright/14 dark regions; ia1 48/8 (different, as it must be)
levelmap NEW vs OLD, luma f0: PNG IDENTICAL; --plane all writes Y (1920x1080), Cb, Cr (960x1080)
```
**First chroma reading ever taken on the smudge class, on the corpus's pathological cell:** on
`dng` @0.5 the chroma planes carry NO level blocks past 20 codes (worst +17.9 Cb / +19.5 Cr)
while luma carries 20 (worst −71.0). That is consistent with §51.14's definition of the wash as
a luma defect — but it is now a measurement, not an assumption, and the chroma columns are in
every battery from here on so a chroma smudge can never again go unmeasured. `cont>20` reads
4 blocks (one 128-px bar) on the base build and 6 on the alternate — the relocation-vs-
concentration question §80.4b could not answer is now a column.

### The extended tools, in full

#### `harness/blotch.py`
```python
#!/usr/bin/env python3
"""blotch.py SRC.yuv DEC.yuv W H NFRAMES [--sh 16] [--fmt 422|444|400] [--depth 10]

sect.51's LEVEL instrument.  artifactmap.py (sect.50.7) is owner-verified for
FINDING the artifact; this quantifies its one defining property so two arms can
be RANKED.  The defect is a LEVEL error over a coherent block, and the block is
the LL band's support: (slice_h/4) picture rows by 32 plane columns.  So:

    BLOTCH = max over all frames and all blocks of |mean signed error|

reported alongside the 99.9th percentile and the counts of blocks past 20 and
past 40 codes, because one number can be beaten by luck and three cannot.
Unlike VMAF-NEG this rises when the damage is CONCENTRATED, which is exactly
the failure mode a mean-square metric rewards.

v5.4 EXTENSIONS (sect.B3 of LEDGER_v5_4; both were recorded as instrument gaps
in LEDGER_v5_3 sect.78.2 and sect.80.4b and are closed here, in the SHIPPED
tool rather than in a fourth instrument):

  1. ALL THREE PLANES.  The v5.3 tool read `[:W*H]` -- the Y plane only -- so
     chroma level error had never been measured anywhere in the project, even
     though the owner's item 4 (city "colour-block updating") is a chroma
     observation and C5 forbids luma-only measurement.  Each plane is now
     scored on its OWN LL support (the band layout is per plane width, so a
     chroma block is (slice_h/4) rows x 32 CHROMA columns).

  2. CONTIGUITY.  A max, a percentile and two counts cannot tell five scattered
     blocks from one long bar, and the eye reads the bar (sect.80.4b: the ship
     set "improved" the aggregate while relocating the wash into a bar the
     aggregate could not see).  `cont>20` is the largest 4-connected component
     of blocks past 20 codes, in blocks, over any single frame, with its frame
     and top-left corner, so a relocation shows up as a number.

  Output: one line per plane, then the LEGACY luma line LAST -- byte-for-byte
  the v5.3 format up to `n>40 N`, so every battery that does
  `tail -1 | grep -oE "n>20 [0-9]+\\s+n>40 [0-9]+"` keeps working unchanged.
  Do NOT rank on the luma line alone: read all three.
"""
import sys, numpy as np

def largest_component(mask):
    """Largest 4-connected component of a boolean block grid.
    Returns (size, (row, col)) of its top-left-most cell; (0, None) if empty."""
    H, W = mask.shape
    seen = np.zeros_like(mask, dtype=bool)
    best, bloc = 0, None
    ys, xs = np.nonzero(mask)
    for y0, x0 in zip(ys, xs):
        if seen[y0, x0]:
            continue
        stack = [(y0, x0)]; seen[y0, x0] = True; n = 0
        top = (y0, x0)
        while stack:
            y, x = stack.pop(); n += 1
            if (y, x) < top: top = (y, x)
            for ny, nx in ((y-1, x), (y+1, x), (y, x-1), (y, x+1)):
                if 0 <= ny < H and 0 <= nx < W and mask[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True; stack.append((ny, nx))
        if n > best:
            best, bloc = n, top
    return best, bloc

def main(a):
    src, dec, W, H, N = a[1], a[2], int(a[3]), int(a[4]), int(a[5])
    fmt = a[a.index('--fmt')+1] if '--fmt' in a else '422'
    depth = int(a[a.index('--depth')+1]) if '--depth' in a else 10
    sc = 1024.0 / (1 << depth)      # report on a common 10-bit code scale
    sh = int(a[a.index('--sh')+1]) if '--sh' in a else 16
    bh, bw = sh // 4, 32
    if fmt == '400':
        CW = 0; names = ('Y',)
    else:
        CW = W // 2 if fmt == '422' else W; names = ('Y', 'Cb', 'Cr')
    per = W*H + 2*CW*H
    dims = {'Y': (H, W), 'Cb': (H, CW), 'Cr': (H, CW)}
    offs = {'Y': 0, 'Cb': W*H, 'Cr': W*H + CW*H}

    st = {n: dict(worst=0.0, loc=None, vals=[], cont=0, cloc=None) for n in names}
    for f in range(N):
        S = np.fromfile(src, dtype='<u2', count=per, offset=f*per*2).astype(np.float64)
        D = np.fromfile(dec, dtype='<u2', count=per, offset=f*per*2).astype(np.float64)
        if S.size < per or D.size < per:
            raise SystemExit("blotch.py: short read at frame %d (src %d, dec %d of %d)"
                             % (f, S.size, D.size, per))
        for n in names:
            hh, ww = dims[n]
            if hh < bh or ww < bw:
                continue
            s = S[offs[n]:offs[n]+hh*ww].reshape(hh, ww)
            d = D[offs[n]:offs[n]+hh*ww].reshape(hh, ww)
            e = (d - s) * sc
            nh, nw = hh // bh, ww // bw
            blk = e[:nh*bh, :nw*bw].reshape(nh, bh, nw, bw).mean(axis=(1, 3))
            r = st[n]
            r['vals'].append(blk.ravel())
            i = int(np.argmax(np.abs(blk)))
            v = blk.ravel()[i]
            if abs(v) > abs(r['worst']):
                r['worst'] = v; r['loc'] = (f, (i // nw) * bh, (i % nw) * bw)
            csz, cl = largest_component(np.abs(blk) > 20)
            if csz > r['cont']:
                r['cont'] = csz; r['cloc'] = (f, cl[0] * bh, cl[1] * bw)

    lines = []
    legacy = None
    for n in names:
        r = st[n]
        if not r['vals']:
            lines.append("BLOTCH %-2s n/a (plane narrower than one LL block)" % n)
            continue
        v = np.abs(np.concatenate(r['vals']))
        loc = r['loc'] or (0, 0, 0)
        cl = r['cloc'] or (0, 0, 0)
        n20, n40 = int((v > 20).sum()), int((v > 40).sum())
        lines.append("BLOTCH %-2s worst %+7.1f at f%d r%d c%d  p99.9 %5.1f  n>20 %d  n>40 %d  cont>20 %d (f%d r%d c%d)"
                     % (n, r['worst'], loc[0], loc[1], loc[2], np.percentile(v, 99.9),
                        n20, n40, r['cont'], cl[0], cl[1], cl[2]))
        if n == 'Y':
            legacy = ("BLOTCH(10b-scale) %+.1f at f%d r%d c%d  p99.9 %.1f  n>20 %d  n>40 %d  cont>20 %d"
                      % (r['worst'], loc[0], loc[1], loc[2], np.percentile(v, 99.9),
                         n20, n40, r['cont']))
    for l in lines: print(l)
    if legacy: print(legacy)   # LAST: legacy luma line, battery-compatible

if __name__ == '__main__': main(sys.argv)
```
#### `harness/levelmap.py`
```python
#!/usr/bin/env python3
"""levelmap.py SRC.yuv DEC.yuv W H FRAME OUT.png [--sh 16] [--fmt 422|444|400] [--sat 20]
                                                  [--depth 10] [--plane Y|Cb|Cr|all]

The COHERENCE view of sect.50.7's error map.  artifactmap.py renders the
per-pixel signed error, which at 0.5 bpp is dense everywhere on detailed
content -- ordinary quantisation noise saturates it just as a real blotch does,
so the eye cannot separate "this level is wrong" from "this area is noisy".
This renders the MEAN signed error over each LL support block
((slice_h/4) rows x 32 plane columns), which is zero for noise and non-zero
only when a LEVEL is wrong.  Red = too bright, blue = too dark, saturating at
+-SAT codes on the 10-bit scale.  A clean picture is BLACK here.

v5.4 (sect.B3): `--plane` selects the plane.  The v5.3 tool read the Y plane
only (LEDGER_v5_3 sect.78.2: chroma level error had never been rendered).
`--plane all` writes three files, OUT with `_Y`, `_Cb`, `_Cr` inserted before
the extension.  A 4:2:2 chroma map is half the luma width; it is written at its
own raster, NOT stretched, so a block is still one LL support.  Default Y, so
every existing call is unchanged.
"""
import sys, os, numpy as np
from PIL import Image
a=sys.argv
src,dec,W,H,f,out = a[1],a[2],int(a[3]),int(a[4]),int(a[5]),a[6]
fmt = a[a.index('--fmt')+1] if '--fmt' in a else '422'
sh  = int(a[a.index('--sh')+1]) if '--sh' in a else 16
SAT = float(a[a.index('--sat')+1]) if '--sat' in a else 20.0
depth = int(a[a.index('--depth')+1]) if '--depth' in a else 10
plane = a[a.index('--plane')+1] if '--plane' in a else 'Y'
CW = 0 if fmt == '400' else (W//2 if fmt=='422' else W)
per = W*H + 2*CW*H
dims = {'Y': (H, W), 'Cb': (H, CW), 'Cr': (H, CW)}
offs = {'Y': 0, 'Cb': W*H, 'Cr': W*H + CW*H}
S=np.fromfile(src,dtype='<u2',count=per,offset=f*per*2).astype(np.float64)
D=np.fromfile(dec,dtype='<u2',count=per,offset=f*per*2).astype(np.float64)
if S.size < per or D.size < per:
    raise SystemExit("levelmap.py: short read at frame %d" % f)
planes = ('Y','Cb','Cr') if plane == 'all' else (plane,)
if fmt == '400': planes = tuple(p for p in planes if p == 'Y')
bh,bw=sh//4,32
for pn in planes:
    hh, ww = dims[pn]
    s = S[offs[pn]:offs[pn]+hh*ww].reshape(hh, ww)
    d = D[offs[pn]:offs[pn]+hh*ww].reshape(hh, ww)
    e=(d-s)*(1024.0/(1<<depth))
    nh,nw=hh//bh,ww//bw
    blk=e[:nh*bh,:nw*bw].reshape(nh,bh,nw,bw).mean(axis=(1,3))
    big=np.repeat(np.repeat(blk,bh,0),bw,1)
    img=np.zeros((nh*bh,nw*bw,3),np.uint8)
    img[...,0]=(np.clip( big/SAT,0,1)*255).astype(np.uint8)
    img[...,2]=(np.clip(-big/SAT,0,1)*255).astype(np.uint8)
    if plane == 'all':
        root, ext = os.path.splitext(out); o = "%s_%s%s" % (root, pn, ext or '.png')
    else:
        o = out
    Image.fromarray(img).save(o)
    print("%s [%s]: worst block %+.1f, blocks |mean|>20: %d, >40: %d"
          % (o, pn, blk.ravel()[int(np.argmax(np.abs(blk)))], int((np.abs(blk)>20).sum()), int((np.abs(blk)>40).sum())))
```
#### `harness/artifactmap.py` — diff against v5.3
```diff
--- v54tree_bak/harness/artifactmap.py	2026-09-01 18:21:00.813598064 -0400
+++ v54tree/harness/artifactmap.py	2026-09-01 23:25:15.350040214 -0400
@@ -10,7 +10,16 @@
 prior: that is exactly what made the earlier ones wrong.
 
 Usage:
-  artifactmap.py SRC.yuv DEC.yuv W H FRAME OUTDIR [--depth 10] [--fmt 422]
+  artifactmap.py SRC.yuv DEC.yuv W H FRAME OUTDIR [--depth 10] [--fmt 422|444|400]
+                 [--slice-h 16] [--plane Y|Cb|Cr]
+
+v5.4 (sect.B3): `--plane` runs the identical map-and-region method on a chroma
+plane, at that plane's own raster (half width at 4:2:2).  The v5.3 tool read
+the Y plane only (LEDGER_v5_3 sect.78.2), and C5 forbids luma-only measurement.
+The rule -- map first, regions read off the map, no shape prior -- is unchanged;
+only the plane it is applied to is selectable.  Default Y, so every existing
+call and every owner-verified luma result is unchanged.  The output tag carries
+the plane name for Cb/Cr, and the "src" column is then the mean source CHROMA.
 
 Writes, into OUTDIR:
   <tag>_ERRORMAP.png        signed error, RED = decoded brighter than source,
@@ -31,10 +40,21 @@
 NH, NW = 5, 25    # neighbourhood: 5 rows x 25 cols (wide, because streaks are)
 MINAREA = 150     # smallest region reported; NOT a shape filter
 
-def luma(path, W, H, frame, fmt='422'):
-    per = W*H*2 if fmt == '422' else W*H*3
+def plane(path, W, H, frame, fmt='422', which='Y'):
+    """One plane of one frame, at the plane's own raster."""
+    CW = 0 if fmt == '400' else (W // 2 if fmt == '422' else W)
+    per = W*H + 2*CW*H
     a = np.fromfile(path, dtype='<u2', count=per, offset=frame*per*2)
-    return a[:W*H].reshape(H, W).astype(float)
+    if a.size < per:
+        raise SystemExit("artifactmap.py: short read at frame %d" % frame)
+    if which == 'Y':  return a[:W*H].reshape(H, W).astype(float)
+    if CW == 0:       raise SystemExit("artifactmap.py: no chroma plane in 4:0:0")
+    if which == 'Cb': return a[W*H:W*H+CW*H].reshape(H, CW).astype(float)
+    if which == 'Cr': return a[W*H+CW*H:W*H+2*CW*H].reshape(H, CW).astype(float)
+    raise SystemExit("artifactmap.py: --plane must be Y, Cb or Cr")
+
+def luma(path, W, H, frame, fmt='422'):
+    return plane(path, W, H, frame, fmt, 'Y')
 
 def boxfilt(a, kh, kw):
     c = np.cumsum(np.cumsum(np.pad(a.astype(float), ((kh,0),(kw,0))), 0), 1)
@@ -60,10 +80,13 @@
     src_p, dec_p, W, H, frame, outdir = argv[1], argv[2], int(argv[3]), int(argv[4]), int(argv[5]), argv[6]
     fmt = argv[argv.index('--fmt')+1] if '--fmt' in argv else '422'
     sh  = int(argv[argv.index('--slice-h')+1]) if '--slice-h' in argv else 16
+    which = argv[argv.index('--plane')+1] if '--plane' in argv else 'Y'
+    depth = int(argv[argv.index('--depth')+1]) if '--depth' in argv else 10
     os.makedirs(outdir, exist_ok=True)
-    tag = os.path.splitext(os.path.basename(dec_p))[0] + f'_f{frame}'
-    src = luma(src_p, W, H, frame, fmt); dec = luma(dec_p, W, H, frame, fmt)
-    d = dec - src
+    tag = os.path.splitext(os.path.basename(dec_p))[0] + f'_f{frame}' + ('' if which == 'Y' else f'_{which}')
+    src = plane(src_p, W, H, frame, fmt, which); dec = plane(dec_p, W, H, frame, fmt, which)
+    H, W = src.shape                      # the plane's own raster
+    d = (dec - src) * (1024.0 / (1 << depth))   # common 10-bit code scale (v5.3 assumed 10-bit)
 
     # 1. the map.  This is the instrument the owner verified; everything else
     #    is derived FROM it, never from a fresh threshold on d.
@@ -80,7 +103,7 @@
     mb = boxfilt(strong_b, NH, NW) > DENS
 
     em = Image.fromarray(img).convert('RGB')
-    dc = np.clip(dec/4, 0, 255).astype(np.uint8)
+    dc = np.clip(dec / float(1 << (depth - 8)), 0, 255).astype(np.uint8)
     dcim = Image.fromarray(np.dstack([dc]*3)).convert('RGB')
     d1, d2 = ImageDraw.Draw(em), ImageDraw.Draw(dcim)
     rows = []
```

## OWNER RULINGS LOG (additions, 2026-09-01)
11. Clamp solver path (C1 recovery) SKIPPED by owner; ship = CDR+clamp AND
    baseband+repair, both 100% generation-exact in 100% of circumstances.
12. Slice-level repairs must never create a seam with the previous/next
    slice; every repair change reruns the pitch/rowphase seam instruments.
13. CDR is NOT an acceptable answer for graphics over baseband; mixed feeds
    must work over baseband.
14. Conditional deferral of the GFX@0.5 gap: condition (a true bitrate
    wall) was REFUTED by the documentation check; the first recording of
    this ruling wrongly deferred anyway and was called out by the owner and
    corrected.  Later the owner GRANTED deferral until after Task C on
    no-known-lever grounds (sect.51.24/25); revisit after C is MANDATORY.
15. Owner context: HVBC was SHELVED for unresolved waxy 16-row flatness --
    all HVBC evidence carries that caveat (51.25).
16. After the cmp_batt incident: nothing proceeds on trust; every
    instrument passes the two-inputs/two-outputs + determinism audit
    (51.27); pre-landing trains must log the blotch column.
17. Standing rules given in chat (2026-09-01, late): (a) judge fixes on
    FULL frames, on the FOLLOWING frames, and on OTHER footage -- never on a
    crop, one frame or one clip; (b) a previous agent's result is not
    evidence until replicated here; (c) before acting on any fix idea,
    consult the ledger, the OMC docs and the HVBC docs so nothing already
    falsified is retried; (d) replacing an entire engine is acceptable if it
    truly solves the problem without creating new ones, after consulting
    OMC docs, HVBC docs, the ledger and the constraints thoroughly;
    (e) design without build-and-test does not count.
18. The never-measured formats (16-bit, 4:0:0, 4:4:4:4) are DEFERRED until
    after the last prompt task (G); they remain in the full-gamut
    definition and must be revisited then.
19. Prompt rules restated for the record: no profiles or switches -- one
    default must work on all footage at once; never measure only luma or
    only chroma; crawl is measured over multiple frames; never change
    settings mid-measurement; never measure latency in C; normative
    changes need reporting only.
20. Structural (engine-replacement) work is built in a SANDBOX tree, never
    in the current codec tree; the current codec stays the reference the
    sandbox must beat on the same instruments (owner, 2026-09-01 late).
21. Continuity: the current ledger is kept up to date CONTINUOUSLY -- every
    finding, metric, method and the code behind it, self-contained and
    reproducible -- because the structural track's deep read may exhaust
    the weekly quota mid-way and must be resumable by a later session.
    The sandbox never crosses paths with baseline v5.3 in the ledger OR the
    folder structure: it lives in `.work/sandbox/` with its own source,
    binaries, outputs and logs, and its record is the SEPARATE document
    `Codec/Current/LEDGER_SANDBOX.md`; this ledger only names it.
22. Baseline track decision (owner + assistant, 2026-09-01 late): the
    exactness fix in flight (B5.5) lands; the instrument/gate work lands;
    the remaining B knob-tuning items (repair reach adjudication, chroma-
    fill x reach attribution, fill-loudness flatness, fill-carry crawl,
    refresh-boost knee, amplitude pairing) are PAUSED, kept documented as
    the fallback queue, because each tunes an engine the structural track
    may replace.

## OPEN ITEMS REGISTER (state at end of 2026-09-01)
- B5.4 crung-vs-CDR-clamp exactness break: ROOT-CAUSED and FIXED (B5.5,
  OMC_LOCK_TIEACT); full train + 12-arm CDR proof running for the verdict.
  444@0.5 arms added to the proof set.
- sect.51.26 staged-dilation tail regressions on ~6 camera cells: fix plan
  = crung scoping first, then adjudicate DILFROM default on the clean
  state.  Depth gate FALSIFIED (51.28).
- GFX@0.5 vs clamp residual ~2.0 NEG: deferred to after C by owner grant;
  MANDATORY revisit; palette (HVBC lead, flatness-gated) is a candidate.
- RBOOST knee (default 50 -> ~100; measured 12.1/10.0/10.5); own cycle.
- Amplitude-pairing (lattice-risky): LAST v54tree change before C.
- Backlog formats: 16-bit / 4:0:0 / 4:4:4:4 (named backlog per owner).
- v5.4 zip + adversarial review: ONLY after ALL prompt tasks A-G complete.

# INLINED SCRIPTS (2026-09-01 additions)

## `h_a4_clampcdr.sh`
```bash
#!/bin/bash
# sect.B3.7f: CLAMP ships CDR-scoped.  12-generation CDR chains, clamp mode
# (--no-gamut-strict) at EVERY generation, across the implemented gamut.
cd /home/user/fromscratch/OMC_CLOUD/Project/.work
E=clamptree/omc_enc; D=clamptree/omc_dec
export TMPDIR=$PWD/scratch/tmp
a4(){ A=$1; WD=$2; HT=$3; FMT=$4; DP=$5; BPP=$6; NF=$7; G=$8
  free=$(df --output=avail -B1M $PWD | tail -1)
  need=$(( WD*HT*4*NF*(G+1)/1000000 + 512 ))
  [ "$free" -lt "$need" ] && { echo "HARNESS ERROR: disk $free MB < $need MB"; return 99; }
  tmp=$(mktemp -d $PWD/scratch/tmp/a4.XXXXXX)
  cur=$A; SH=$([ $HT -le 720 ] && echo 8 || echo 16); CHh=$(( (HT+SH-1)/SH*SH ))
  ok=PASS; why=""
  for g in $(seq 1 $G); do
    if [ $g -gt 1 ]; then
      $E -i $cur -o $tmp/s$g.omc -w $WD -h $CHh --fmt $FMT --depth $DP --bpp $BPP -n $NF --display-w $WD --display-h $HT --cdr-in --no-gamut-strict >/dev/null 2>&1
    else
      $E -i $cur -o $tmp/s$g.omc -w $WD -h $HT --fmt $FMT --depth $DP --bpp $BPP -n $NF --no-gamut-strict >/dev/null 2>&1
    fi
    [ -s $tmp/s$g.omc ] || { ok=FAIL; why="enc-gen$g"; break; }
    $D -i $tmp/s$g.omc --cdr -o $tmp/d$g.yuv >/dev/null 2>&1
    [ -s $tmp/d$g.yuv ] || { ok=FAIL; why="dec-gen$g"; break; }
    if [ $g -ge 2 ]; then
      cmp -s $tmp/d$g.yuv $tmp/d$((g-1)).yuv || { ok=FAIL; why="pixels-gen$g"; break; }
      [ $g -ge 3 ] && { cmp -s $tmp/s$g.omc $tmp/s$((g-1)).omc || { ok=FAIL; why="stream-gen$g"; break; }; }
    fi
    cur=$tmp/d$g.yuv
  done
  echo "A4-CDR-CLAMP $(basename $A .yuv)@$BPP/$FMT-$DP gens=$G : $ok $why"
  rm -rf $tmp
}
a4 arms/dng_1920x1080_422_10.yuv 1920 1080 422 10 1.0 12 12
a4 arms/cityalley_1920x1080_422_10.yuv 1920 1080 422 10 1.0 12 12
a4 arms/bosphorus_1920x1080_422_10.yuv 1920 1080 422 10 2.0 12 12
a4 arms/dng_1920x1080_422_10.yuv 1920 1080 422 10 0.5 12 12
a4 arms/dng_1280x720_422_10.yuv 1280 720 422 10 1.0 12 12
a4 arms/dng_1920x1080_444_10.yuv 1920 1080 444 10 1.0 12 12
a4 arms/dng_1920x1080_422_8.yuv 1920 1080 422 8 2.0 12 12
a4 arms/dng_1920x1080_444_12.yuv 1920 1080 444 12 1.0 12 12
a4 arms/cf_gfx_448x256_422_10.yuv 448 256 422 10 0.5 12 12
a4 arms/readysetgo_1920x1080_422_10.yuv 1920 1080 422 10 4.0 12 12
echo CDR-CLAMP-DONE
```

## `h_gapsweep.sh`
```bash
#!/bin/bash
# sect.51.20: size the repair-vs-clamp NEG gap per cell (gen-1 quality).
cd /home/user/fromscratch/OMC_CLOUD/Project/.work
H=v53/omc_v5.3/harness; T=scratch/tmp/gap; mkdir -p $T
cell(){ c=$1; W=$2; Hh=$3; fmt=$4; dep=$5; b=$6
  A=arms/${c}_${W}x${Hh}_${fmt}_${dep}.yuv; [ -f $A ] || { echo "SKIP $A"; return; }
  tag=${c}_${fmt}${dep}_bpp${b}
  for m in on off; do
    fl=""; [ $m = off ] && fl="--no-gamut-strict"
    nice -n 19 clamptree/omc_enc -i $A -o $T/$tag.$m.omc -w $W -h $Hh --fmt $fmt --depth $dep --bpp $b -n 12 $fl >$T/$tag.$m.log 2>&1
    nice -n 19 clamptree/omc_dec -i $T/$tag.$m.omc -o $T/$tag.$m.yuv >/dev/null 2>&1
  done
  non=$(bash $H/negscore.sh $A $T/$tag.on.yuv $W $Hh $fmt $dep 12 2>/dev/null | tail -1)
  nof=$(bash $H/negscore.sh $A $T/$tag.off.yuv $W $Hh $fmt $dep 12 2>/dev/null | tail -1)
  oob=$(grep -oE "gamut: [0-9]+" $T/$tag.off.log | awk '{print $2}')
  rep=$(grep -oE "[0-9]+ slices repaired" $T/$tag.on.log | awk '{print $1}')
  echo "GAP $tag repair=$non clamp=$nof oob=${oob:-0} repaired=${rep:-0}"
  rm -f $T/$tag.on.yuv $T/$tag.off.yuv
}
for b in 0.5 1.0 2.0; do
  cell dng 1920 1080 422 10 $b
  cell cityalley 1920 1080 422 10 $b
  cell readysetgo 1920 1080 422 10 $b
  cell cf_gfx 448 256 422 10 $b
done
cell dng 1920 1080 444 12 1.0
cell dng 1920 1080 422 8 2.0
echo GAPSWEEP-DONE
```

## `h_dilfrom_train.sh`
```bash
#!/bin/bash
# sect.51.21 staged-dilation candidate (OMC_GM_DILFROM=2): full cost + chains.
cd /home/user/fromscratch/OMC_CLOUD/Project/.work
H=v53/omc_v5.3/harness; T=scratch/tmp/dft; mkdir -p $T
export OMC_GM_DILFROM=2
cell(){ c=$1; W=$2; Hh=$3; fmt=$4; dep=$5; b=$6
  A=arms/${c}_${W}x${Hh}_${fmt}_${dep}.yuv; [ -f $A ] || return
  tag=${c}_${fmt}${dep}_bpp${b}
  nice -n 19 clamptree/omc_enc -i $A -o $T/$tag.omc -w $W -h $Hh --fmt $fmt --depth $dep --bpp $b -n 12 >$T/$tag.log 2>&1
  nice -n 19 clamptree/omc_dec -i $T/$tag.omc -o $T/$tag.yuv >/dev/null 2>&1
  neg=$(bash $H/negscore.sh $A $T/$tag.yuv $W $Hh $fmt $dep 12 2>/dev/null | tail -1)
  oob=$(grep -oE "gamut: [0-9]+" $T/$tag.log | awk '{print $2}')
  echo "DF2 $tag NEG=$neg oob=${oob:-0}"; rm -f $T/$tag.yuv
}
for b in 0.5 1.0 2.0; do
  cell dng 1920 1080 422 10 $b; cell cityalley 1920 1080 422 10 $b
  cell readysetgo 1920 1080 422 10 $b; cell cf_gfx 448 256 422 10 $b
done
cell dng 1920 1080 444 12 1.0; cell dng 1920 1080 422 8 2.0; cell dng 1280 720 422 10 1.0
# 12-gen baseband chains, default repair + DILFROM=2
a4(){ A=$1; WD=$2; HT=$3; FMT=$4; DP=$5; BPP=$6
  tmp=$(mktemp -d $T/a4.XXXXXX); cur=$A; ok=PASS; why=""
  for g in $(seq 1 12); do
    clamptree/omc_enc -i $cur -o $tmp/s$g.omc -w $WD -h $HT --fmt $FMT --depth $DP --bpp $BPP -n 8 >/dev/null 2>&1
    clamptree/omc_dec -i $tmp/s$g.omc -o $tmp/d$g.yuv >/dev/null 2>&1
    [ -s $tmp/d$g.yuv ] || { ok=FAIL; why=dec$g; break; }
    if [ $g -ge 2 ]; then cmp -s $tmp/d$g.yuv $tmp/d$((g-1)).yuv || { ok=FAIL; why=pix$g; break; }
      [ $g -ge 3 ] && { cmp -s $tmp/s$g.omc $tmp/s$((g-1)).omc || { ok=FAIL; why=str$g; break; }; }; fi
    cur=$tmp/d$g.yuv
  done
  echo "DF2-A4 $(basename $A .yuv)@$BPP gens=12 : $ok $why"; rm -rf $tmp
}
a4 arms/cf_gfx_448x256_422_10.yuv 448 256 422 10 0.5
a4 arms/cf_gfx_448x256_422_10.yuv 448 256 422 10 1.0
a4 arms/dng_1920x1080_422_10.yuv 1920 1080 422 10 0.5
a4 arms/dng_1920x1080_422_10.yuv 1920 1080 422 10 1.0
a4 arms/dng_1920x1080_444_12.yuv 1920 1080 444 12 1.0
a4 arms/readysetgo_1920x1080_422_10.yuv 1920 1080 422 10 4.0
echo DILFROM-TRAIN-DONE
```

## `h_tailmatrix.sh`
```bash
#!/bin/bash
# Tail-regression tuning matrix: crung-scoping x DILFROM on the six cells.
cd /home/user/fromscratch/OMC_CLOUD/Project/.work
H=v53/omc_v5.3/harness; T=scratch/tmp/tails
m(){ arm=$1; W=$2; Hh=$3; fmt=$4; dep=$5; bpp=$6; sh=$7; label=$8; shift 8
  A=arms/${arm}_${W}x${Hh}_${fmt}_${dep}.yuv; n=${arm}_${fmt}${dep}_${bpp}_${label}
  nice -n 15 env "$@" v54tree/omc_enc -i $A -o $T/$n.omc -w $W -h $Hh --fmt $fmt --depth $dep --bpp $bpp -n 12 >/dev/null 2>&1
  v54tree/omc_dec -i $T/$n.omc -o $T/$n.yuv >/dev/null 2>&1
  neg=$(bash $H/negscore.sh $A $T/$n.yuv $W $Hh $fmt $dep 12 2>/dev/null | tail -1)
  bl=$(python3 $H/blotch.py $A $T/$n.yuv $W $Hh 12 --sh $sh --fmt $fmt --depth $dep 2>/dev/null | tail -1 | grep -oE "n>20 [0-9]+\s+n>40 [0-9]+")
  echo "MX $n NEG=$neg $bl"; rm -f $T/$n.yuv $T/$n.omc; }
# 422 cells: crung-off simulation (FILLTHR_C=3) x dil 1/2 ; also dil1 with crung on
for c in "dng 1280 720 422 10 0.5 8" "dng 1280 720 422 10 1.0 8" "dng 1920 1080 422 8 0.5 16" "dng 1920 1080 422 12 0.5 16"; do
  set -- $c
  m $1 $2 $3 $4 $5 $6 $7 nf_d1 OMC_FILLTHR_C=3 OMC_GM_DILFROM=1
  m $1 $2 $3 $4 $5 $6 $7 nf_d2 OMC_FILLTHR_C=3 OMC_GM_DILFROM=2
  m $1 $2 $3 $4 $5 $6 $7 cr_d1 OMC_GM_DILFROM=1
done
# 444_8 cell (crung is its target class): dil 0/1/2 with crung on
for d in 0 1 2; do m dng 1920 1080 444 8 0.5 16 cr_d$d OMC_GM_DILFROM=$d; done
# 4K@1.0 small regression: dil 1 vs 2
m dng 3840 2160 422 10 1.0 16 cr_d1 OMC_GM_DILFROM=1
m dng 3840 2160 422 10 1.0 16 cr_d2 OMC_GM_DILFROM=2
echo TAILMATRIX-DONE
```

## sect.B5.5 — train verdict (2026-09-02 00:18) and a correction about the CDR proof

**Verdict on the B5.5 tie-break fix (v54tree, `OMC_LOCK_TIEACT=1`):**
- Battery `logs/battery_v54_tie.log`: 52 of 52 cells, VMAF-NEG identical to the previous
  battery (`battery_v54_dil.log`) on every cell to the last digit, oob = 0 everywhere, blotch
  columns unchanged — as expected for a change that only acts on locked ties at generation ≥ 2.
- Crawl `logs/crawl_v54_tie.log`: complete (frozen masters, 12 cells).
- A4 chains `logs/a4_v54_tie12.log`: 20 PASS, 0 FAIL (12 generations).
- **Correction:** the "12-arm CDR proof" `logs/a4_cdrclamp54_tie.log` (12 PASS, 0 FAIL) was run by
  `h_a4_clampcdr.sh`, which encodes with the **clamptree** binaries (built 2026-09-01 16:47,
  and `clamptree/src/codec.c` contains no `OMC_LOCK_TIEACT`). It therefore proves the clamp
  sandbox's CDR exactness, not the B5.5 fix. The B5.5 fix's own CDR evidence is the repro
  chain recorded above (gen 2 EXACT, gen 3 == gen 2 on the failing chain) plus the 20 A4
  chains. A v54tree copy of the proof script now exists (`h_a4_cdr54.sh`, prints
  `A4-CDR-V54`) and runs inside the B5.5b train below, so the 12-arm proof on the shipping
  tree will exist before anything is published as final.

## sect.B5.5b — the exact per-plane tie-break: landing train launched 2026-09-02 00:19

Patch `notes_disk/pending_patch_B5_5b_plane_regime.py` (per plane, also evaluate the
"all tie bands → intra" variant so the Q5 plane regime is covered; greedy then refines within
the chosen regime). Train driver `h_b55b_train.sh`: snapshot `v54tree_pre55b/` → patch →
make → `make test` + `tests/run_script_gates.sh` (incl. G-T5-SPEND) + `tests/restore_check.sh`
(`logs/b55b_gates.log`) → generation-1 wire check on three cells against the pre-patch
binary (`logs/b55b_wire.log`, must read IDENTICAL) → `h_battery54.sh` (`battery_v54_55b.log`)
→ `h_crawl54.sh` → `h_a4_final.sh` (20 chains) → `h_a4_cdr54.sh` (12-arm CDR proof on v54tree).
Marker `out/B55B.done`. Verdict follows.

## sect.B5.5b — verdict so far (2026-09-02 05:00)

- Patch applied cleanly; build ok. Gates: `make test` failed ONLY on `tests/refcheck.sh`
  (source cites sect.51.21, which the in-tree v5.3 ledger does not contain — a citation from the
  earlier DILFROM landing, not from this patch); fixed by appending the published v5.4 ledger
  to `v54tree/LEDGER_v5_ADVERSARIAL.md` as a "V5.4 ADDENDUM" (refcheck: all 52 cited sections
  resolve). Script gates rc 0 incl. G-T5-SPEND on three cells; restore check rc 0.
- Wire check: generation-1 streams byte-identical to the pre-patch tree on dng 1080p 4:2:2,
  cf_gfx and dng 1080p 4:4:4 @0.5 (`logs/b55b_wire.log`) — the fix acts only on locked ties.
- Battery `logs/battery_v54_55b.log`: 52 of 52 cells, NEG, blotch, flatness and pitch identical
  to the B5.5 battery on every cell (the only textual difference is the sect.51.30 `cont>20`
  and chroma-blotch columns, which the B5.5 battery predates); oob = 0 everywhere.
- Crawl `logs/crawl_v54_55b.log`: all 12 lines identical to B5.5's.
- A4 chains `logs/a4_v54_55b.log`: 20 PASS, 0 FAIL (12 generations).
- 12-arm CDR proof ON v54tree (`h_a4_cdr54.sh`, `logs/a4_cdr54_55b.log`): running, 1 of 12
  PASS so far; verdict appended when complete. `make test` re-run after the refcheck fix:
  see next entry.

## sect.B5.5b — gate suite re-run after the citation fix (2026-09-02 06:44)

`make test` in v54tree: 97 ok, rc 0 (`logs/b55b_gates_rerun.log`). The only earlier failure was
the citation check; every codec gate passed on both runs. The v54tree 12-arm CDR proof stands at
9 of 12 PASS, 0 FAIL at this writing.

## sect.B5.5b — FINAL VERDICT: LANDED (2026-09-02 06:52)

The 12-generation CDR proof on the shipping tree (`h_a4_cdr54.sh`, 10 arms: dng 1080p 4:2:2
@0.5/1.0, cityalley @1.0, bosphorus @2.0, dng 720p @1.0, 4:4:4 10-bit @1.0, 4:2:2 8-bit @2.0,
4:4:4 12-bit @1.0, cf_gfx @0.5, readysetgo @4.0; `logs/a4_cdr54_55b.log`): **10 PASS, 0 FAIL**.
With the battery (52/52 identical), crawl (12/12 identical), A4 chains (20/20), gates (97 ok
after the citation fix) and the generation-1 wire check (byte-identical), the exact per-plane
tie-break is landed. The tree is the v5.4 tip: B5.5 + B5.5b. Snapshot `v54tree_bak` (pre-B5.5)
deleted; `v54tree_pre55b` kept as the current fallback until the next landing.
Note for the record: the clamptree proof script carries 12 arms, the v54tree copy 10 (the two
clamp-only arms are not part of the shipping tree's contract).

## sect.LATT — the constructive legality step promoted from the sandbox: battery, gates, wire (2026-09-02 12:42)

Source: `Codec/Current/LEDGER_SANDBOX.md` S2 (design, evidence, falsifications) and
`.work/sandbox/promotion/` (the patch: `latt_probe.inc`, four hooks, Makefile dependency, tool
report, `label_legacy.py`, `LEGACY_REPAIR_INVENTORY.md`, restore incantation += `OMC_GM_LATT=0`).
Default ON (no opt-in). The legacy repair stays as the labelled fallback (117 `[LEGACY-REPAIR]`
sites) with its removal condition in the inventory.

- Wire (`logs/latt54_wire.log`): with `OMC_GM_LATT=0` the encoder is byte-identical to the
  pre-patch tree on all three cells; with the step on it differs (expected).
- Gates (`logs/latt54_gates.log`): `make test` rc 0, script gates rc 0 (incl. G-T5-SPEND),
  restore rc 0.
- Battery `logs/battery_v54_latt.log` vs `battery_v54_55b.log` (52 cells × 12 frames, identical
  bytes, comparison `logs/latt54_battery_cmp.md`): NEG after − before mean **+0.004** (median 0;
  5 cells better, 3 worse; max +0.179 on 720p @0.5, min −0.073 on cf_gfx @0.5 — the graphics
  gain the sandbox saw over v5.3 is already in v5.4 through the refresh boost, so the step is
  score-neutral there); by rate +0.027 @0.5, −0.007 @1.0, −0.003 @2.0, −0.001 @4.0.
  **Luma blocks past 40 codes, summed over the 52 cells: 346 → 88; past 20: 1493 → 883.** oob = 0
  on every cell both arms. Chroma, flatness and pitch columns in the comparison file; crawl,
  A4 chains and the 10-arm CDR proof are running and are appended with the final verdict.

## sect.LATT — FINAL VERDICT (train finished 2026-09-02 ~21:05, `.work/out/LATT54.done` (cwd of the train is `.work`; logs `.work/logs/latt54_*.log`); recorded at the 98 %-quota halt 21:50)

`LATT54-DONE wire: WIRE dng_1920x1080_422_10@0.5 step-off IDENTICAL to pre-patch; step-on differs (expected); WIRE cf_gfx_448x256_422_10@0.5 step-off IDENTICAL; step-on differs (expected); WIRE dng_1920x1080_444_10@0.5 step-off IDENTICAL; step-on differs (expected); gates: make test rc=0 script gates rc=0 restore rc=0 battery=52 chains=20/0F cdr=10/0F`

The step stays promoted, default ON.  **Verdict wording (owner-corrected, sandbox S3.12–S3.13, S3.28): "legality by construction + deep washes only" — it is NOT a smudge fix.**  The owner's marked 720p frame still shows the grille's white patches (lost detail = whole-frame bit shortage at 8-row slices, sandbox S3.34) and the black patches (the in-gamut repair's shrink, ruled metric-only 2026-09-02 16:50); the chroma speckle is the sect.67.12 chroma fill (sandbox S3.17; gate candidate post-Task-C).

Everything after this point of the structural track is in **`Codec/Current/LEDGER_SANDBOX_v2.md`** (hand-off section H first): Task C (refresh on demand + state hash, minor 14) and the zero-mean lifting rounding (colour-cast fix, minor 15, normative) are gated and packaged in `.work/sandbox/promotion/` and NOT yet promoted into this tree; the train for them is `.work/h_taskc_promote_train.sh`.

---

# G. TASK G INTEGRATION — the v5.4 → v5.4-G round (2026-09-05/06). Summary; the working record is `LEDGER_SANDBOX_v2.md` S5.40–S5.91 and hand-off H.12

**Tree:** `.work/v54tree_g`, built from `.work/v54tree_int` (minor 15), **stream minor 16**. Changelog with markers, gates and ledger cites: `v54tree_g/docs/CHANGES_v5_4_G.md`. Promotion to the agents' base waits on the re-gate (Agent 4, MEMO 014).

## G.1 Landed (12 items, all gated; NORMATIVE marked)
1. Agent 5's 14 doc/code fixes — true bounds (40 emits/entry, 48 repair passes, 4,096 lock candidates; the documents said 32 / 16 / 48), `a2_strict` on by default, declared rational conversion checked, one slice-height rule, lossless ceiling and per-format default rate (three of six formats could not reach lossless), 0.3 bpp as a mechanical limit, two floors stated. S5.83.
2. `omc_dec --lose` walks true slice extents; the fixed-stride probe had damaged the wrong slices (every earlier recovery gate used it; re-run: gates stand). S5.83, S5.88.
3. Concealment upward-only; downward searches and spatial interpolation deleted; loss-path deferral 16–20 ms → 0. Intra-frame loss freezes (design item open). S5.83.
4. C11 goto/declaration fix. S5.83.
5. Six C8 freeze violators pinned; `OMC_DBG_ZBAND` inline read removed and announced. S5.83, S5.89.
6. OMC-TF deleted (legal review action 3). S5.84.
7. **NORMATIVE** Agent 1 block-motion field + half-pel + A5 fetch barrier (BITSTREAM.md, TEMPORAL_T5.md App. M). S5.84–S5.85.
8. **NORMATIVE** `OMC_MINOR_T5` 15 → 16; minor-15 decoders refuse. S5.85.
9. `[A2-LOCKCAP]` lock walk bounded by progress: 2,656 → 17 verifications per slice on an all-black frame, byte-identical elsewhere; the expert's nine extrema all encode. S5.88, S5.90.
10. **NORMATIVE** `[A2-Q5CTX]` loss-neutral entropy contexts: 0 extra decode failures on 10/10 loss patterns (shipped 14–58). S5.88.
11. `--no-fill` honoured (was silently inert). S5.89.
12. `OMC_DBG_ZBAND` announced. S5.89.

## G.2 Falsified this round (do not re-try; full text at the cite)
Normative committed-range clamp (6/6 pixels-gen2; B3.7f; `reconstruct_slice()` comment; the repair is load-bearing) — S5.80. Fill/quantiser crossing (0 in 71.9 M; clamp at `codec.c:4552`, 12.5 % margin, expert: fragile) — S5.80. Option-(3) legality test (E_max vacuous at 0.5 bpp; 77×) — S5.80. LL-shift-0 mechanism; every cross-arm frozen-plan result; w = 10 inter deadzone; ±8 px MVYCAP; "one floor"; line-based scan as a pure reorder (closed-loop rate control) — S5.80, S5.84. 720p "bit shortage" (S3.34) — flatness does not respond to rate — S5.90. 16-row slices at 720p as recommended — 1.139 ms with declared conversion — S5.89.

## G.3 Standing findings that shape the next round
- Every flatness number before 2026-09-05 was read on the intra ramp (f2); steady state (encode from f0, measure ≥ f7, state both) is mandatory. S5.80.
- **The shipping codec fails the owner's flatness bar at 0.5 bpp on 4 of 6 owned cells at f7** (re-derivation in `flatplane.py` assigned). S5.80.
- Arms: 1080p from 4K = Lanczos via `derive.py`, never crop; one agent's entire self-derived 1080p corpus was crops; long 24-frame masters exist at `.work/arms/long/`. S5.80, S5.86.
- Codec expert (response 5): a decoder-only fill cannot correlate with lost detail; put the effort into allocation (retain the correlation-bearing coefficients); protect the boundary row with its own rung; the fill margin is fragile — derive a local bound. S5.81.
- 8-bit late convergence (fixed point at gen 7, one clip, cause unidentified, moved by fill amplitude/reach). S5.80.
- 720p grille = two artifacts: flatness is the slice-h-8 fill-reach rule (reach 0 fixes it); the SMUDGE (owner's instrument) is the 8-row geometry and grows f7 → f11. S5.90–S5.91.
- Loss footprint k−1 … k+1 (the slice above is affected); recovery gates stand under correct injection. S5.82.
- Gen-1 static bound `W_fwd + 1,920·W_emit + 48·W_repair` (N_lock = 0 at gen 1); gen 2 has N_lock unbounded → 1 with a carried plan. S5.81–S5.82.
- VMAF-NEG failed three ways; diagnostic only. S5.80.

## G.4 Open (assigned)
A1: motion package priced against R = 2R (MEMO 016). A2: 720p (smudge growth, reach, header pricing), `altrows` lattice-repair bound, intra-frame MC concealment (MEMO 018/019). A3: flatness bar in the owner's tool, then the allocation route Steps A–D (MEMO 023). A4 (measurement): re-gate → promote (MEMO 014). A5 (measurement): R = 2R ladder on the long arms (MEMO 016). Coordinator: Task A (read v5.3 ledger + docs in full) and Task F (papers) NOT started.

## G.5 Round continuation, 2026-09-06 afternoon–evening (sandbox ledger S5.93–S5.117)
**Promotion:** v54tree_g (minor 16) promoted 09-06 after Agent 4's re-gate (S5.93). **R = 2R measured for the first time on trustworthy arms** (Lanczos, 24 f, steady state, XS at best flags; Agent 5's ladder `Agents/Agent5/out/m3/ladder_all.log`, enc 5f9d31658a1e): met only on highwayview 4:2:2 in one window; every other cell fails at 0.5-vs-1.0 AND 1.0-vs-2.0 (S5.98, S5.110); equal-rate OMC beats XS everywhere; two 4:4:4 cells refuse to encode at 0.5 on out-of-range samples (policy changed: commit-and-flag). **Higher expert (memo 007, six documents + eight follow-ups, S5.104/S5.106):** temporal engine at ≈25 % of a ≈67 % ceiling (one mode per band per slice is the binding limit); mandate priced in rate (5 of 7 cells reachable); flatness partly rate (16:1 gear) and partly built-in (fill amplitude tied to the step, band-level on/off, absolute thresholds); seam = one-neighbour reconstruction (two-sided predictor, no bits); exactness = plan not locked (Rules A/B/C, keep banking); 8K fits the ZU7EV (chroma reach ±4 + 10-bit ring → 79 %). **IP review revision (S5.108):** the fill must leave the format; PQ deleted; per-block energy class held; luminance offset encoder-only; parent context cleared (re-cite); per-block intra/inter flag cleared. **Owner rulings:** see sandbox H.13. **Defect found by the round's own gate once rebuilt (S5.112–S5.117):** `test_xsl` G-T5-CUT4 fails — "plates alone" = the motion package (Agent 1 fixing), "cut" = the repair's impulse-table estimator vs the `[S5-DC]` parity rounding (merge of 09-04; builder queued). Promotion of `_next` blocked until both pass. **Landing audit (S5.113–S5.115):** eight measured wins not live (`UNIMPLEMENTED_SUCCESSES.md`), incl. three older than this round (W10 inter dead zone, refresh boost 100, Task D docs) and the 8-bit depth-relative rules awaiting the owner's route decision. **Delivered this round, not yet landed:** block-layer half-pel (`Agents/Agent1/diffs/blkhp_vs_v54tree_g.diff`, +0.557 dB luma soccer2, one allocator-driven regression). Reproduce: every number above cites its log under `Agents/*/out/`, `.work/logs/fable_2026-09-06/` or the sandbox ledger entry named.


## G.6 — v5.3.6 (2026-09-08): the findings merge (stream minor 16, unchanged)

Built in `.work/v536` from the v5.3.5 tree on the owner's instruction to merge the five agents' findings and the outside adversarial review into one reality and apply it. The complete, traceable record is `.work/v536/docs/CHANGES_v5_3_6.md`; the working-ledger entry is LEDGER_SANDBOX_v2 S5.126–S5.127. Headline: repair budget 13 + G-T5-CUT24 (the shipped default no longer breaches at cuts), the level-2 two-sided boundary predictor qualified with the fill off and then held back by G-T5-CUT24 (legality; repair granularity is the blocker), CDR-input repair keyed on verified status, `OMC_VEXT_LVL` pinned, PQ removed, CLI segfault fixed, 0 warnings, vectors restored + restore gate re-based, CRC-valid fuzz gate, Agent 4 all3 and Agent 5 lattice memo landed. Not applied, with reasons: CHANGES §C. Carried defects: CHANGES §D.
