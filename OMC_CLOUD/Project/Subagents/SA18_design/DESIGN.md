# SA18 design — working document (written incrementally)

Status 2026-09-29 evening. PAPER = argument only; PROXY = entropy screen; REAL = real code lengths from static tables
trained on clips disjoint from the test cells, exact CBR, full frames, compared with today's real decodes.

---------------------------------------------------------------------------------------------------------------
## §A. Candidate architectures (owner request: 2–3 genuinely different structures, then a reasoned choice)

### A.0 The root that separates the candidates (measured before choosing)
Every current goal except efficiency is decided by ONE structural choice: **is an output sample ever an input to an
average that something else reads?**
- If yes (any lowpass with an update/averaging step, including 5/3, S-transform pairs, lapped transforms), exactness
  forces the legaliser to preserve that average (gen 2 re-reads it from the picture), so an overshooting sample's
  excess is pushed onto its partner(s), in a direction the decoder cannot know. "Never away" then fails wherever the
  mean's error has the wrong sign. Measured kill test (D2, oracle = best of 18 single ±1 re-choices of the coarse
  coefficients covering each case, whole-plane check): fixable cases cut24 0.1 % (682), ext10 0.0 % (1 876),
  dng720 @0.5 32.7 % (150 sampled), cf_gfx 56 % (34). No predetermined re-choice rule can reach 100 %.
- If no (every output sample is written once, from values that are already final, plus its own leaf, and is read by
  others only as that final value), a plain per-sample clip is (i) legal, (ii) never away by construction (the clip
  only moves an overshooting value to the rail, which lies between it and the in-range source), (iii) exact
  (gen 2 reads leaf = sample − prediction(final values); the smallest index reproducing the clipped sample is
  canonical), (iv) free (no symbol). This is the predict-only ("interpolating") family.
- Proof sketch of the dichotomy: a gen-2 encoder sees only the picture; any quantity that the synthesis READS must be
  recoverable from the picture; an average of an overshooting sample and a partner is recoverable after legalisation
  only if the legaliser preserves it; preserving it moves the partner by the overshoot; the partner's error sign
  depends on the source, which the decoder does not have. So per-sample never-away + exactness ⇒ no averaged sample is
  ever legalised ⇒ predict-only structure.

### A.1 Architecture AVG — continuous averaging pair pyramid, leaf-interval legality (the SA15–17 family, re-derived)
- Structure: pair mean/difference pyramid over the whole frame, slices = rate/packet units only; each pair written
  last from a final mean + a clamped leaf.
- Goals: seams/smudges met (disjoint pair support); legal by construction at zero cost; exact (canonical reading);
  loss < 4 frames (on-demand heal) — all measured by SA15–17. **Never away: fails, provably (A.0).** Chroma row
  signature: 2 nested dyadic vertical levels make rows 0/3 vs 1/2 of every 4-row group differ whenever level-2
  vertical details are zeroed (D1: zero-detail synthesis 3.4–4.5 %, 10–12 % with horizontal detail also zeroed);
  predictor tuning cannot remove it (best of 108 dyadic 2/4-tap sets 24 → 16 %), one vertical chroma level removes it
  but costs −2.4 NEG (dng720 @0.5) / −1.4 (volley @0.5) at real code lengths (D1a).
- Constraints: latency 2S+10 lines, 8K memory fits (SA16/17 paper), one pass, royalty-free (Haar/S-transform, 2/6).
- Verdict: cannot meet goal 2 as worded (per sample). Kept only as the efficiency REFERENCE for the other candidates.

### A.2 Architecture IPL — interpolating pyramid with per-sample leaves on a row-uniform lattice (new)
- Structure: every level splits the current sample set into "kept" samples and "predicted" samples; a predicted
  sample = clip(P(final kept neighbours) + leaf). No update step: kept samples are real output pixels, written at
  their coarsest level and never changed. Separable 4-point interpolation P (Deslauriers–Dubuc, 1989: (−1,9,9,−1)/16),
  shift-add only. Row-uniformity by construction: the vertical kept/predicted pattern is SKEWED per column group so
  that every picture row contains every lattice class at the same density (no row class exists at all); slices are
  rate/packet units only (continuous across slice edges, with ahead rows like AVG).
- Goals: legal + never away + exact + zero cost by construction (A.0). Seams: none by construction (no slice-closed
  unit; rows statistically identical). Still areas / temporal / loss: per-sample leaves take a value-domain
  prediction exactly like AVG's leaves; on-demand heal unchanged.
- Risks (decisive tests BEFORE anything else): (1) coding gain — predict-only lowpasses are aliased point samples;
  SA17's PROXY screen said +12…60 % bits (never measured at real code lengths; SA17's other proxy overstated a
  transform price by 2–6 points); (2) at low rate the kept samples keep texture while interpolated ones are smooth →
  a visible dot/diagonal lattice ("screen door") is possible; must be judged on renders, per plane.
- Constraints: same line buffers as AVG (4-tap vertical support = 2 rows each side per level), shift-add, one pass;
  IP: interpolating wavelets / lifting (Deslauriers–Dubuc 1989, Sweldens 1996), expired/open.

### A.3 Architecture DOL — decoupled output layer (partner's proposal; Laplacian pyramid, Burt–Adelson 1983)
- Structure: coarse pyramid used only as an internal predictor; output = clip(up(coarse) + per-sample residual).
- Kill test (gen 2 must re-read the same coarse indices from the output): 1-level LP, down = 2×2 mean, up =
  replicate (left inverse), coarse step 1–8, residual step 8–32: coarse re-read mismatch 11–40 % (dng720), 5–36 %
  (hwy). Reason (analytic): down(P1) = c + down(residual error), i.e. the re-read sees the UNQUANTISED coarse value
  plus noise, which falls into another cell with probability ≈ |noise|/step. **Falsified.**


### A.5 Wide search for goal 2 "never away" (owner ruling 2026-09-29: A.0 is not an answer; widen with SA18P)
Every family below was checked against the records and argued or measured. "Case 3" = an overshooting sample whose
SOURCE is not at a rail (near-rail texture); D6 measured it is 100 % of AVG's away moves on natural content
(dng720 @0.5/1/2: 388/36/2 away samples; cf_gfx 71/7/2), ~50 % on cut24, < 5 % on ext10.

| # | family (where legality acts / what is sent / structure / how gen 2 reads) | verdict | evidence |
|---|---|---|---|
| L1 | per-sample clip after synthesis, predict-only structure (IPL, A.2) | never-away + exact + free by construction; **efficiency dead** | REAL intra (tables trained identically for both arms): dng720 @0.5 IPL NEG 65.45 (64.50) PSNR 29.99/33.67/34.66 vs AVG 80.55 (79.57) 32.06/35.70/36.72 = −15 NEG, −2.1 dB every plane; INTER proxy (MC residual from real decoded references): volley/hwy ≈ −2.7 dB luma at matched rate — temporal prediction does not remove the predict-only penalty |
| L2 | leaf clamp, mean-preserving (AVG, A.1) | exact, free; not never-away | D2, SA17 §3.2 |
| L3 | rank-order lowpass (coarse = min/max of a pair) | never-away at the rail on the extreme side, exact; erosion/dilation bias = colour cast (G6), no anti-aliasing | paper |
| L4 | encoder-side closed loop "no overshoot in own streams" | decoder clamp never fires; the partner harm is only relocated into the encoder's constrained choice (b = 2m − a) | paper |
| L5 | injective dequantisation (SA14 IDQ) | moves samples away | SA14 v2 (107 k away) |
| L6 | rail symbols in the entropy stage (SA14 RAIL±) | +10.9 % bits on a graded frame | SA14 |
| L7 | fold at the rail (hi + o → hi − o) | never farther than the pre-legal value, but a rail source gets dips (white plate → grey speckle) | paper |
| L8 | overshoot-conditional correction symbol | breaks gen 2 (the corrected sample enters gen 2's averages) + bits | paper |
| L9 | lattice-preserving legaliser (sum changes by 2k·s so the mean stays on its lattice) | the mean is synthesised: changing it = changing an ancestor index (sibling/whole block moves, unsigned); also rewrites a mean after neighbours read it | partner, paper |
| DOL | decoupled output layer (Laplacian pyramid) | gen-2 coarse re-read mismatch 5–40 % | A.3 |
| RC | rail-conditional structure switch keyed on final coarse values | m ↔ switch fixed point (iteration) | paper |
| F2 | switch keyed on causally final data (the decoded reference) | not by construction on cuts / moving rails; parse/structure depends on history (loss, join; S5.29 class) | partner, paper |
| F3 | rail-excluded structure: R = samples exactly at a rail are known values outside all averages; non-R samples clamped to [lo+1, hi−1] so gen 2 reads R from P1 without a cycle | by construction for plates and clipped highlights; does NOT touch case 3 (all of natural content's away moves) | D6 |
| e_m | inward rounding of ancestor means near rails (encoder or decoder side) | a detail moves its two children in opposite directions; the inward margin needed at the top grows with depth (LL forced inward = darkening = harm); conflicts where both rails share a support | partner, paper; D2 oracle 0–56 % |

Where the chain ends for case 3: an overshooting sample and its partner share a synthesised mean whose inherited error the
decoder cannot sign; any exact legaliser must preserve what gen 2 re-reads (that mean); so a by-construction guarantee
needs the sample's LAST write to be private (no averaging), which is L1. The open question is therefore L1's price.

### A.4 Choice
IPL failed its decisive test (A.5 row L1): −15 NEG intra at real code lengths, ≈ −2.7 dB on inter residuals. The
legality core is therefore the averaging pair pyramid with leaf-interval legality (AVG), re-derived here from A.0/A.5
and D2/D6, not inherited. For natural content (case 3) no exact, free and efficient structure among the ~15 families
above satisfies "never away" per sample; this is reported plainly as the design's failure on that clause (§ Risks),
with its measured size. The remaining sections design the efficiency, still-area and row-phase layers on that core.
(Original pre-set rule: Rule fixed in advance: IPL is chosen if at real code lengths (tables
trained for it, disjoint clips) it costs ≤ 0.1 NEG on intra and shows no lattice artifact on the renders; otherwise
the dichotomy of A.0 is reported to the owner as a measured conflict between "never away (per sample)" and
"efficiency ≥ today", with AVG's away-move sizes (count, max, share of plane MSE vs a clip).)

---------------------------------------------------------------------------------------------------------------
## §B. The design ("CFV-1": continuous pair pyramid + coarse-first vectors + hold-once still areas)

Status: B.1–B.4 are chosen and justified by the measurements cited; numbers for the full design are in §5.

### B.1 Transform and legality (chosen in §A from ~15 families; re-derived, not inherited)
- Per plane, a continuous pair pyramid: 2 "quad" levels (vertical pair, then horizontal pairs of the vertical means
  and differences) and 3 horizontal pair levels, over the whole picture. Pair step: S-transform mean with
  position-parity rounding + difference; every difference is predicted from neighbouring FINAL means (2/6 slope) and
  coded as a leaf. Slices are rate/packet units only; the transform never closes at a slice edge.
- Why this and not the alternatives: IPL (predict-only, per-sample leaves) costs −15 NEG intra / −2.7 dB inter
  (A.5 L1); DOL fails gen 2 (A.3); continuous 5/3 leaves a 5–15 % chroma row class (SA17 E1); slice-closed
  transforms make slice-edge rows (SA12–14). Transform price of the pair vs 5/3 at real code lengths ≈ 0 (SA17 EV-B).
- Legality: each leaf is clamped into the exact set that keeps its pair's two outputs legal, computed from FINAL
  values only (acyclic because every leaf is read by nothing but its own pair). Any bitstream decodes to a legal
  picture; no symbol is spent; a legal source passes unchanged.
- Known failure (OPEN goal item): "never away" per sample (A.5, D6): the clamp preserves the pair mean (what gen 2
  re-reads), so the partner of an overshooting sample moves by the overshoot; on natural content every such case is
  near-rail texture ("case 3"). Measured sizes in §3.

### B.2 Temporal prediction: coarse-first vectors (new element)
- Value-domain coefficient prediction from one reference D(t−1): leaf value = leaf of T(P) + q·2^e, P = OBMC
  (bilinear block-centre weights, 64×8 luma blocks) of D(t−1).
- Two vector fields per frame, both TRANSMITTED (the decoder never derives vectors: S5.29 loss hazard, and the
  ledger's IP note on decoder-side derivation):
  1. History field V_h: block match of D(t−1) against D(t−2) (±16×±4, row-regularised, zero preferred within
     2 codes/pixel) — predicts the coarse bands LL, H5, H4, H3.
  2. Coarse-first field V_2: once a slice's coarse bands are decoded, its level-2 LL, LL2(t) (quarter resolution),
     is known exactly to every encoder, re-encoder and decoder. Per 64×8 block, among the 25 candidates
     {V_h + d : d ∈ [−2, 2]²} (fixed order, zero first), take the one whose block-shifted reference has the level-2
     LL closest to LL2(t) (SAD per block; each candidate scored as a uniform field, so no block coupling). V_2
     predicts the level-2 and level-1 bands. Sent as a difference to V_h; its bits are capped per slice by a fixed
     allowance (2.5 % of the slice budget, raster order, excess blocks fall back to V_h — deterministic).
- Why: the fast-motion deficit is STALENESS of history vectors (D8: MC prediction PSNR luma hwy 34.46 hist /
  34.55 clean-source history / 35.52 source-searched; floor 34.02 / 34.25 / 35.26; forward projection 0).
  Source-searched vectors cannot be re-derived by gen 2 (D9: predictions differ on 11.5 % of hwy blocks). The
  current frame's own decoded coarse band removes the staleness exactly: prediction PSNR luma with V_2 (quarter-res
  scoring) hwy 35.51, floor 34.91 (D14); the half-res variant (LL1 stage, level-1 only) 35.74 / 35.23 (D13c).
- Coding order inside a slice: coarse bands → LL2 → V_2 → level-2 and level-1 bands.

### B.3 Quantisation and texture reconstruction
- Lattice: leaf value = base + recon(q)·, recon(q) = q·2^e for the coarse bands; for the level-1/2 bands of inter
  frames recon(q) = q·2^e + sign(q)·2^(e−2) (nonzero indices reconstruct ¼ step outward: a canonical texture
  reconstruction offset, normative, same at both ends). Encoder dead zone ρ = 0.35. Plan ladder: 30 (plane, band)
  exponents, one band coarser per plan step, order from the synthesis gains + 0.25-octave tilt per level toward the
  fine bands (tilt measured on a training clip: 0.25 → 93.95, 0.5 → 93.62, 0.75 → 93.50 NEG, city @0.5).
- Canonical index = smallest |q| whose (clamped) reconstruction reproduces the final leaf; the offset keeps this
  one-to-one (tested: chain exact with the offset on).
- Evidence (E8, @0.5, hold1): dng720 89.35 → 89.59, volley 91.72 → 91.86 NEG.

### B.4 Entropy coding
- Per leaf: magnitude class (static tANS, L = 1024) + raw mantissa bits + sign. Context = classes of left and above
  neighbours inside the slice (indices only: independent of the decoder's clamps, so gen 2 computes the same bits;
  packets parse independently). Tables keyed by (luma/chroma, band group, intra/inter, step bucket) = 82 tables ×
  4 contexts, trained on 5 clips disjoint from all test cells UNDER THE FINAL CONFIGURATION (T2).
- Considered and dropped: a per-(band, slice) bank of 8 skew variants of every table. It removes 5–26 % of class
  bits (D11) but is worth only +0.07/+0.11 NEG in the full codec (E10) and cannot be built at 8K (48 Mbit stored,
  or ~240 table builds per 31 µs slice period).

### B.5 Still areas: hold once, then update only on change (owner rulings in force)
- Rule (encoder only; a re-encoder reads the result like any value): a coefficient of a zero-vector block that has
  been coded once since it went still (or since an intra/heal) is held — its index is 0, so its value = the
  prediction = its previous value — until the SOURCE changes by more than ¾ of the step it was coded at. No
  scheduled, age-based or pulsing refinement exists. State per (64×8 block, band): one exponent + the still flag.
- Measured: frozen input 0 changed samples on Y, Cb, Cr from frame 2 on (§3.4); mixed clip in §3.4.
- Built, measured and rejected (owner rules): refinement events at fixed frames / still ages (C2: +1.2 volley /
  +2.4 dng720 NEG, but each event changes ≈ 70 % of still samples by ≈ 6 codes: refresh-pulse class); error-driven
  hold with an absolute threshold (C3: 33–62 % of still samples change every frame, mean 6.5 → 3.4 codes, no stop in
  10 frames: ants class; NEG 89.11 < hold1 on dng720); current-plan octave re-coding (= SA17 hold2, 18–71 %/frame).
- Consequence (open goal-4 item): on static-camera content the still areas keep the quality of the frame in which
  they went still. Root chain: still content is first coded under a budget shared with motion (or at a cut) → exact
  CBR per frame (rev. 4, no cross-frame credit) and one reference frame (C2) give a still region at most one frame's
  bits per visible change → today's codec reaches its higher static quality by changing still samples every frame
  (its 60–77 % "ants"), which the owner forbids. Levers that raise what the one update buys (B.3 offset, tilt) are in.

### B.6 Rate control: exact CBR, one decision per slice + one predetermined re-choice
- Per slice, the code lengths of all 16 exponents of every band are computed in parallel from open-loop symbols; the
  plan k = the finest ladder plan whose total fits B + credit − header − V_2 allowance − 16-bit reserve.
- After the slice's coarse bands are decoded and V_2 is known: ONE predetermined re-choice of the fine bands' own
  plan index k_f on the same ladder (the finest that fits the remaining budget with V_2's real costs; the coarse
  exponents stay at k). Costed from the same parallel table; no trial coding, no iteration.
- Emission = the canonical reading of the encoder's own picture: coarse plan = coarsest consistent on the coarse bands,
  k_f = coarsest consistent on the fine bands, smallest indices. Unspent bits carry as credit within the frame.

### B.7 Slices, packets, loss recovery
- Slice = S rows (4 at 720p, 8 above), one packet, one (k, k_f). The transform is continuous; packet k carries the
  coarse leaves of the blocks below that slice k's pairs read (a packing order).
- Primary (two-way links, owner ruling S5.37): per-slice loss flags; on-demand heal: rows [kS − m, (k+1)S + m],
  m = 16 + 8(RT + 1), coded intra in frame t + RT + 1 inside the fixed budget. Vectors are transmitted, so the
  decoder's prediction state after the heal equals the encoder's (§3.5).
- One-way links: a column wave of cycle 2 with the clean-region rule (SA17's mechanism, re-measured here §3.5); the
  coarse-first field is derived from decoded data of the current frame, which is clean wherever the slice is clean.

### B.8 Formats and conversion
- The transform, legality intervals [lo, hi] and canonical reading are depth- and range-agnostic (lo/hi from the
  format: full or limited range, 8/10/12-bit); 4:2:2 chroma uses half-width planes with vectors halved (2-tap
  half-sample average); 4:4:4 uses full planes; 4:2:0 would halve chroma rows (one vertical chroma level fewer).
  Resolution conversion (720p50 3:1) is outside the codec core, as today.

---------------------------------------------------------------------------------------------------------------
## §4. Work, latency, memory (PAPER unless marked; the model is frame-level)

### 4.1 Work per sample (fixed, every branch fixed, shift/add/compare only, no multipliers)
- Decoder: synthesis incl. leaf clamps ≈ 25; OBMC prediction twice (V_h for the coarse bands, V_2 for levels 1–2)
  ≈ 2 × 16; forward analysis of the two predictions ≈ 12 + 10; entropy ≈ 4 → ≈ 83 ops/sample ≈ 3× a JPEG XS
  decoder's per-sample work. Closed formula per slice of S rows × W: W·S·(25 + 32 + 22 + 4) for luma, the same per
  chroma sample.
- Encoder: SA17's ≈ 330 (source + prediction analysis, 16 exponent costs in parallel, canonical reading ≈ 48,
  history vector derivation ≈ 150 on a 1:4 decimated match) + V_2 scoring: 25 candidates, each a 4×4 box mean of
  the block-shifted reference (separable running sums ≈ 2 adds per candidate per full-res sample) + quarter-res SAD
  → ≈ 55 + the second prediction/analysis ≈ 28 → ≈ 415 ops/sample. One plan decision + one predetermined fine-plan
  re-choice + one fixed emission pass per slice; no search over codings, no iteration.

### 4.2 Latency (lines, excluding conversion; constant by construction)
- Capture S + transform look-ahead 8 (two blocks of ahead data) + one slice period (exact-CBR prefix bound) +
  ≈ 2 pipeline = 2S + 10 → 18 lines at 720p (S = 4), 26 at 1080p–8K (S = 8). JPEG XS ≈ 32.
- Coarse-first order adds no capture wait (LL2 of slice k comes from rows already captured); it adds a compute
  stage inside the slice: coarse synthesis → LL2 → V_2 → fine bands. It must be pipelined per 64-column block
  (block j's fine bands start when block j's LL2 and V_2 exist), otherwise it costs up to S/2 line times; at
  720p50 with the 3:1 conversion (0.99 ms today) even 2 lines (53 µs) would break 1 ms. RISK: this pipelining is
  argued, not built.

### 4.3 Memory against today's documented setup (.work/v537/docs/DDR_WINDOW_CACHE.md §7.3)
- Decoder, 8K (4320p60) 4:2:2 10-bit: reference ring ≈ 44 rows × 15 360 samples × 10 bit = 6.8 Mbit (the window
  grows by the V_2 reach ±2 rows); coefficient buffers ≈ 7.9 + 3.9 (second prediction's fine-band analysis) =
  11.8 Mbit; output lines 1.2; tANS tables 328 distributions × 1024 × 19 bit ≈ 6.4 Mbit → ≈ 26.2 Mbit, against
  today's 29.23 Mbit (narrowed store) on the ZU7EV-class part (27 URAM + 11 BRAM).
- 8K 4:4:4 12-bit: ≈ 39 Mbit — over the ZU7EV like today's (47.2). Same status as today; not solved here.
- DDR: reference read + write at depth bits, 20 bit/sample (today 26); both vector fields read from the same on-chip
  window (no extra DDR read). Encoder-only state: still flag + one exponent per (64×8 block, band) ≈ 0.16 bit/sample
  plus V_h/V_2 fields (a few kbit per slice row).

---------------------------------------------------------------------------------------------------------------
## §6. IP provenance
| element | source | status |
|---|---|---|
| S-transform pair mean/difference, 2/6 slope prediction | Haar / S-transform (1970s–80s); TS/CREW 2/6 (mid-1990s) | expired |
| lifting framework, position-parity rounding | Sweldens 1996; own work | open / own |
| leaf-interval legality, canonical reading, nested dyadic ladder | own work (after SA15) | own |
| texture reconstruction offset (¼ step outward on fine bands) | generic reconstruction-point choice (textbook quantiser theory, Lloyd-Max 1960s) | expired / generic |
| OBMC bilinear block-centre weights | H.263 Annex F era (1996) | expired |
| history block matching; coarse-first candidate selection on the current frame's decoded coarse band | textbook block matching; own work (selection rule; vectors TRANSMITTED, no decoder-side derivation) | own |
| Exp-Golomb vector differences | 1978 | expired |
| static tANS | Duda (tANS only; no rANS) | open |
| on-demand heal over a return path; cycle-2 column wave | owner ruling S5.37; GDR (H.263/MPEG-2 era) | own / expired |

---------------------------------------------------------------------------------------------------------------
## §7. Prior failures checked
| failure | where | here |
|---|---|---|
| slice-closed transforms: edge step / anchor row / first-row excess | SA12–14 | transform continuous, slices are rate/packet units only (§3.3 row phases) |
| continuous 5/3: even/odd row class | SA17 E1 | pair vertical |
| 2-level vertical pair: 4-row chroma signature | SA16 F3, SA17 F3 | root found (D1: nested dyadic interpolator when LH2/HH2 are zero); 1 chroma level −1.4…−2.4 NEG, predictor tuning 24→16 %, staggered pairing makes columns special (D10): NOT solved; measured in §3.3 |
| lattice lock (texture loss, ants, 1 000-frame refresh) | SA15 | value-domain prediction |
| history vectors stale on fast motion | SA17 F1 | coarse-first vectors from the current frame's decoded LL2 (B.2), exact by construction |
| source-searched vectors (gen 2 cannot re-derive) | S5.152, D9 | not used |
| decoder-derived vectors (loss hazard, IP) | S5.29, ledger | vectors transmitted |
| per-band intra/inter mode | S5.135 | oracle +0.01…+0.17 (D4): not used |
| entropy-estimate efficiency claims | SA15 F1a | every figure real code lengths |
| tables trained without the operating state | SA17 bench (found here, D4b) | retrained under the final configuration (T2) |
| table pooling over step sizes | SA17 ENT1 | tables keyed by step bucket |
| exact hold not gen-2 consistent | SA16 F2 | hold = encoder choice of zero indices; read back canonically (chain §3.2) |
| hold freezes still content coarse (SA17 F1a) | SA17 | measured as the main remaining gap; every catch-up form tried violates the flicker/pulse rulings (B.5) |
| never away | SA15 F5, SA17 F2 | NOT solved; ~15 families costed (A.5); sizes §3.1 |
| predict-only legality structures | SA15 #1, SA17 E1d | IPL measured at real code lengths: −15 NEG intra (A.5) |
| Laplacian / overcomplete output layer | new | gen-2 re-read mismatch 5–40 % (A.3) |
| rail symbols / IDQ / REXT iteration | SA13, SA14 | not used |
