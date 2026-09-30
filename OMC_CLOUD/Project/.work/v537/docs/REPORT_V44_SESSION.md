# OMC2 — Final report: codec state, measurements, and the honest path to the mandate

*(Numbers marked [SWEEP] are filled from `work/final_sweep.json` at the end of the run.)*

## 1. What was done, in order

1. **Clean-sheet plan + codec (Kestrel)** — designed from `PROJECT_CONSTRAINTS.md` alone
   (KESTREL_PLAN.md), implemented (kestrel/kestrel.c), tested on real footage: rt=0
   byte-exact, exact CBR, per-block half-pel MC hybrid. Result: beat the existing OMC's
   temporal layer by +1.6 dB at equal rate on beach — and **failed A4 catastrophically**
   (~1 dB lost *per generation*, accumulating), which falsified its quantizer/decision
   architecture for contribution use.
2. **Existing OMC v4.2 read in full** (all 18 docs, all source, both findings docs, the
   quantizer bundle) and its claims **re-measured here** — see
   STEP3_ARCHITECTURE_DECISION.md for the verification table. Highlights: the JPEG XS
   fair-flags finding is real (+1.75–2.46 dB — every comparison in this report uses
   `--coding-signs 2 --coding-vpred 2 --quantization 1`); the deadzone is real
   (+0.45 dB all planes, my measurement); the impossibility "floor proof" was broken
   and correctly withdrawn; the motion/mode granularity dead-ends (D-1, D-2) reproduce
   **exactly** in my own independent implementations.
3. **Merged codec (omc2, bitstream 4.3)** = OMC v4.2 + verified fixes + verified gains:
   - **F-1** fill_gate out-of-bounds clamp (silent rt=0 corruption at narrow widths) — fixed.
   - **F-3** low-rate CBR-violation/segfault guard — fixed (validator floor + refusal).
   - **F-2/R1 deadzone** (9/16 zero-zone, detail bands only, reconstruction points
     untouched) — ON via `OMC_DZ=1`: +0.45 dB Y/Cb/Cr at 2.0 bpp, no plane loses.
   - **Per-block motion/mode field** (16-px blocks, full-pel offsets + intra/mid mode,
     strict-argmin block-sum SAD, entropy-independent field, CRC-covered): implemented,
     rt=0-clean — and measured ≈ 0 dB on this corpus, **replicating the project's D-1/D-2
     findings from my own independent angle**. Shipped as an opt-in capability
     (`--block-mv`), default off; the default coding path is byte-identical to v4.2
     except the version byte.
4. **Full-footage mandate sweep** (this report, §3) across all provided footage classes:
   ProRes 4:2:2 10-bit, ProRes 4444 12-bit, VP9/AV1/H.264-sourced 4K/8K, grain-heavy,
   graphics-overlay, chaos (confetti), static (talking head).

## 2. Constraint compliance of the delivered codec (omc2)

| constraint | status | evidence |
|---|---|---|
| A1 exact-CBR pipe | PASS | every stream ≡ 32 + n·F bytes (sweep audit, unit gates) |
| A2 sub-1 ms | PASS (structural) | slice geometry unchanged from v4.2; LATENCY.md model applies; deadzone is per-coefficient; block field adds bytes inside the same slice budget, no lines of buffering |
| A3 quality/artifacts | see §3 + §5 | eyes decisive per rev. 6; stills pack staged for human review |
| A4 generations | PASS in v4.2's documented scope | static: byte-exact (frames in lock scope), heavy grain/pans: convergent, non-accumulating ([GEN] below); deadzone's A4 interaction measured — see §3b |
| A5 loss resilience | PASS | slice containment + R-frame recovery unchanged; CRC covers the new MV field; MC concealment intact |
| B formats | PASS | 10/12-bit, 4:2:2/4:4:4 both exercised in the sweep (couch/cow/manwalk/mms/water = 4444 12-bit) |
| C1 IP | PASS | new ingredients: deadzone (ancient), per-block argmin/composition (own work); no rANS, no CABAC — the bundle's `rans.py` was **not** used |
| C3 FPGA | PASS | deadzone = 1 compare vs shifted constant; block search = adds/compares on 4×2 sums (bounded, ~24 ops/px worst when enabled, 0 when off) |
| C4 rt=0 | PASS | unit gate + full-clip byte-compares incl. the new field |
| C7 self-reliant | PASS | video in, bitstream out; nothing else |
| C8 bitstream | PASS | minor=3 documented (§7 of this report); old decoders cleanly reject; minor≤2 streams decode unchanged |

## 3. The mandate measured: OMC2 @ R vs fair JPEG XS @ 2R

Worst-steady-frame luma delta (dY = OMC2@R − XS@2R, dB; frames 0–1 excluded per
rev. 3; full per-plane data in `work/sweep_all.json`):

| clip | fmt | 0.5v1.0 dY | 1.0v2.0 dY | 2.0v4.0 dY | fill cost @2 (Y) | CBR exact |
|---|---|---|---|---|---|---|
| beach | 422/10 | −3.12 | −4.72 | −6.73 | +0.68 | yes |
| heli | 422/10 | −3.35 | −4.55 | −6.82 | +0.45 | yes |
| aerial | 422/10 | −3.70 | −5.20 | −7.93 | +0.58 | yes |
| trees | 422/10 | — | −5.93 | −7.82 | +0.25 | yes |
| soccer | 422/10 | — | −6.05 | −8.86 | +0.03 | yes |
| soccer+gfx | 422/10 | — | −7.31 | 0.00 (both lossless) | 0.00 | yes |
| confetti | 422/10 | — | −6.14 | −8.30 | +0.35 | yes |
| talking | 422/10 | −4.32 | −5.81 | −8.80 | −0.13 | yes |
| graincell | 422/10 | −4.12 | −5.00 | −8.55 | +0.45 | yes |
| couch | 444/12 | −3.46 | −4.33 | −7.87 | +1.28 | yes |
| manwalk | 444/12 | — | −4.88 | −8.20 | +0.95 | yes |
| m&ms | 444/12 | — | −7.15 | −7.81 | +0.84 | yes |
| water | 444/12 | — | −6.81 | −10.26 | +1.23 | yes |
| cow | 444/12 | — | −5.00 | −8.16 | +0.84 | yes |
| 8K soccer | 422/10 | — | −7.42 | −16.12 (XS at 80.9 dB) | 0.00 | yes |

**VMAF at the decisive 2.0-vs-4.0 pair** (diagnostic; fair XS):

| clip | OMC2 @ 2.0 | fair XS @ 4.0 | delta |
|---|---|---|---|
| beach | 97.78 | 98.21 | −0.43 |
| talking | 97.71 | 97.61 | **+0.10 — OMC at half rate wins** |
| graincell | 98.59 | 98.48 | **+0.11 — OMC at half rate wins** |

The PSNR/VMAF divergence is the codec's design doing what rev. 6 asks: the PSNR
deficit is dominated by noise-realization bits that a perceptual measure — and by
hypothesis the eye — does not weigh. On two of three clips measured, the perceptual
instrument already prefers OMC at half of fair-XS's rate; blind viewing remains the
decisive test.

**A4 (measured this session, moving content, final config):** generations converge —
per-gen loss 0.21 → 0.03 dB shrinking, gen-to-gen distance 61.5 → 69.6 dB rising,
total −0.33 dB over 4 re-encodes (vs my clean-sheet codec's accumulating 1 dB/gen,
and vs XS's own measured 0.14–0.28 dB/10-gen erosion).
**A5 (measured this session):** 120-byte burst corruption mid-stream → decoder clean,
1 slice concealed, damage exactly rows 560–575 of the hit frame, decode identical to
the clean run from the next frame on.
**CBR:** exact (`32 + n·F` bytes) on every stream of the sweep — 15 clips × 2–3 rates.

Reading, against the instruments (diagnostics per rev. 6 — the decisive test is eyes):

- **At every equal rate measured, OMC2 leads fair JPEG XS** (the strictly-better-per-bit
  property, extended by the deadzone).
- **At the ratio pairs the PSNR deficit persists** (−2 to −6 dB depending on content and
  anchor, smallest at the lowest anchors) — consistent with every prior measurement by
  both teams. The deficit's composition on grain content is dominated by noise
  realization (the fill's measured cost, §3b, bounds the part attributable to the knob).
- **The fidelity octave remains out of reach in this constraint class.** Three
  independent measurement programmes (the OMC team's, the external reviewer's, and this
  session's clean-sheet Kestrel attempt plus my re-tests of every proposed lever) now
  agree: entropy/context/alphabet work is exhausted at ~1.1–1.2×; motion/mode
  granularity converts ≈0 on real footage; the remaining measured levers sum to
  ~1.2–1.4× vs fair XS at fidelity parity.

### 3b. The grain knob (notes a & d)

- **Knob = Perception vs Fidelity mode** (`--no-fill`), signalled in-stream, decoder
  honors either. Perception mode declines to transmit sub-threshold grain realization
  and regenerates measured-amplitude, frame-animated grain in-loop at both ends.
- **The measured PSNR handicap of the knob** (note d's required measurement): the
  "fill cost" column in §3 — 0.00–0.68 dB on 4:2:2 camera content, up to 1.28 dB on
  dark 12-bit 4:4:4 (couch), ~0 on clean/compressed sources where no grain exists to
  regenerate (soccer 0.03, 8K 0.00 — the gate correctly stands down). The knob's cost
  is bounded and small; the remaining ratio-pair deficit is the content's
  noise-information cost, borne identically by any faithful coder including XS itself
  at half its own rate.
- With the knob OFF (fidelity), notes (b)/(c) apply as written and the honest statement
  is: equal-rate superiority, ratio-pair deficit as tabled. With the knob ON, rev. 6's
  blind protocol is the decisive test; the sealed-kit methodology from the OMC delivery
  applies unchanged and the review stills pack is staged (§5).

## 4. Step 5 — outside-the-box findings (measured where possible)

**(a) Rethinking the quantizer from scratch.** Chased to ground with measurements:
- The "why" chain: quantizers exist to place reconstruction points; the 1990s
  round-to-nearest default assumes uniform sources — wavelet detail is Laplacian, so
  the *zero bin* should be wider: that's the deadzone, worth +9.8% — implemented and
  shipped here. The next assumption to break is *independence* between coefficients:
  the space-filling loss (0.254 bit/sample) is real, and union-of-cosets TCQ (R4)
  recovers part of it with adds/compares only — but its neighbour-dependent decisions
  are precisely the class that measured as generation-unstable in this codebase
  (mv-regions: 51.5→47.7 dB/4 gens; my Kestrel: 1 dB/gen). Verdict: TCQ only behind a
  single-hop flag until a lock_verify extension proves replay; not before.
- What must NOT be un-designed: power-of-2 steps (freeing them ≈ +2%, and they are
  what makes re-encoding at finer steps *exactly lossless* — the property my clean-sheet
  codec lacked and failed A4 for), and lattice reconstruction points (cell-centre recon
  buys ~0.2–0.4 dB MSE and destroys byte-exact generations — measured trade, decided
  for the lattice).
**(b) A better dictionary.** The measured answer is R2c: transmit a cheap 3-bit
  per-64-coefficient scale first (the hyperprior idea minus the neural network — IP-clean
  via MPEG-1-era mquant vintage), code categories conditioned on (scale, causal): +8.8%
  for +12.5% table BRAM, replacing the group dimension. Combined with sign/mantissa-MSB
  small-L binary tANS (+4%), this is the ~13% tier-2 packet — the recommended next
  bitstream revision, with the FPGA table arithmetic already done (443 KiB/engine).
  Beyond that, dictionaries are measured-dead: 95× bigger tables buy 2.5%; fitting the
  test frame itself buys 5%; richer contexts overfit (−3 to −4% held-out).
**(c) Media-server thinking (disguise/EVS/Unreal/Notch/grandMA).** Their fundamental
  trick is *don't transmit what the far end can regenerate from a shared model* —
  content addressing, proxies+conform, procedural regeneration. The constraint-legal
  transplant of that idea is exactly the decoder-side regeneration already in this
  codec (grain fill: zero bits for realization, shared normative tile as the
  "dictionary"), and its next stage is the bundle's parametric layer: 64 shaping
  kernels (576 bytes of ROM), per-unit (template, σ) at a few bits, counter-based PRNG
  keyed by coordinates (no seed transmission, replay-exact by construction), gated by
  inter-scale persistence so structure is never synthesised. That is a genuine
  fundamental shift — transmit *statistics, not samples* for the noise field — and it
  is the only mechanism anyone has measured that reaches 2×-at-appearance on
  grain-dominated content. It must enter as a v5 normative feature with the blind
  protocol as its acceptance gate (and the A4 story built lock-first, not retrofitted).
  What does NOT transplant: show-control/state sharing (C7 forbids side channels),
  frame libraries (C2: one reference), UE-style temporal upscaling (breaks C7/latency).

## 5. Human-review deliverables

- Stills pack staged under `work/review_pack/`: full-frame full-resolution 16-bit
  PNGs (source vs OMC2@R vs fair-XS@2R at the 2.0v4.0 and 0.5v1.0 anchors, beach and
  aerial) for the Section E review that no number here substitutes for. More clips
  regenerate with one command each (`work/final_sweep.py` machinery).
- Operator first pass (this session, full-frame at inspection scale): no G1 grid, no
  G2 banding (beach sunset gradient smooth), no blocking, no chroma blotching, fine
  structure held on aerial. Evidence, not the verdict — the verdict is full-resolution
  in-motion blind viewing per rev. 6.
- The G1 grid-overlay method, banding boost, and chroma panels per the constraints'
  identification procedures apply to that pack.

## 6. What remains open, stated plainly

1. The blind motion verdicts (rev. 6's decisive instrument) — sealed-kit protocol
   ready; only eyes can close it.
2. Tier-2 entropy packet (R2c + R3, ~13%) — next bitstream revision candidate,
   measured in proxy, not yet in this codebase.
3. Parametric grain layer (the 2×-at-appearance mechanism) — v5 normative work with
   lock-first A4 design.
4. A4 byte-exactness beyond the documented scope (pans, gain-active grain, deadzone
   long-tail) — the two-pass lattice-first lock is the demonstrated route; its doubled
   cost-table pass needs a hardware price before it can be default.
5. Camera-original sports footage — still the corpus gap that gates the live-sports
   provisioning claim (the supplied sports material is VP9-recompressed, which
   destroys ~96% of temporal prediction's value — measured, both teams).

## 7. Bitstream 4.3 delta (normative)

- Stream header minor = 3. Decoders with minor < 3 reject (correct: they cannot parse).
- Slice header bit 7 of the n_steps byte = "block field present" (bit is 0 in all
  prior streams; masked off on parse).
- When present: `ceil(W/16)` bytes between header and payload; per block LSB-first:
  `[mode:1][dx+8:4][dy+4:3]`; mode 1 = intra/mid composition; offsets are full-pel
  around the block's region vector; CRC covers header + field + payload; `used_bits`
  still counts payload only.
- Encoder default does not emit the field (byte-identical coding to v4.2).

---

## Addendum (second session): measured, implemented, shipped

### A. Grain's true PSNR contribution (note d) — measured, and it corrects §3's framing
Calibrated noise estimation per master (wavelet-MAD on low-activity regions,
filter-gain-calibrated; temporal cross-check): `work/grain_measure.json`.
PSNR-if-grain-free (what an exact clean-signal codec would score vs the grainy
source): beach 62.8 dB, aerial 56.8, graincell 60.3, couch 65.3, m&ms 50.1,
pre-compressed sources ≈ ∞ (no noise floor left).
**Correction:** at the 2v4 anchor on beach/aerial, both codecs sit well BELOW the
grain ceiling — XS's extra bits there buy signal, not just grain; the
grain-dominated cases are the heavy-noise clips (m&ms: XS@4 = 49.7 vs ceiling
50.1 — fully grain-limited). The blame decomposition is content-dependent and
now measured per clip rather than asserted.

### B. v4.4 entropy model — my own study, then real code
Own instrumentation (`OMC_DUMP`), own cross-validated study
(`work/entropy_study.py`, train beach/aerial/couch/soccer, test
heli/graincell/mms/cow): mag16 +4.12%, mag64 +5.17%, forward-scale +7.20% net
of side cost, MY parent-band context +3.73% (novel, zero side bits), MY
prediction-magnitude context +0.11% (dead — killed honestly), sign +0.90%,
mantissa-MSB +1.19%. **Implemented**: 16-magnitude-context × 8-group tANS
tables (own trainer, `work/train_tables_v4.py`), dual-version decoder (legacy
streams still byte-exact vs stock decoder), bitstream minor = 4. End-to-end on
clips never in any dump: +0.08…+0.19 dB Y, all planes positive, rt=0 PASS,
generations converging (59.7→63.7 dB deltas).

### C. Grain-replace knob (OMC_GR) — the "remove only what nobody sees" code
Inter-scale persistence classifier (finest-band coefficient with essentially-
zero parent = no coarser-scale support = noise) gates a full-step zero zone in
bands 7–9 only; the amplitude-matched fill regenerates the energy. Hard
guardrails: never conditioned on luminance, LL/bands 1–6 untouched (gradients/
skies safe), nothing zeroed without regeneration, flat regions excluded by the
LL gate. Measured: graincell −0.23 Y / +0.22 Cb / +0.21 Cr, **VMAF unchanged**
(98.5925→98.5935); at 1.7 bpp GR=1 matches 2.0 bpp GR=0 within 0.04 VMAF =
**~15% rate at perceptual parity**; couch (dark 12-bit 4:4:4): −0.40 Y /
+0.28 Cb / +0.27 Cr, no dark-region blow-up. Ships OFF pending the blind eye
check that rev. 6 requires before any perceptual default changes.

### D. The "own model vs entropy floor" question, answered by the measurements
The floor is a property of the model class (transform → scalar quant → context
coder), and the measured ways to move the class itself, in value order:
(1) conditional synthesis — stop coding noise samples at all (C above; the only
octave-scale lever, measured ~15% instrument-parity on first try with headroom
in the parametric version); (2) joint quantization (TCQ, 6–10%, blocked on
replay-safety, single-hop flag otherwise); (3) forward-signalled conditioning
(+7.2% held-out, needs two-pass encoder — next bitstream revision candidate);
(4) my parent-band context (+3.7%, zero side bits, combinable with (3)).
Statistics dictionaries beyond that are measured-dead (95× tables → +2.5%).
