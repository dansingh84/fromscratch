# OMC remaining work — status and blocking dependencies (2026-08-02, v4.7)

> **STATUS in v5.0: historical.** Items in it that v5 completed are recorded in `CHANGELOG_v5.md`; this document has not been re-planned.


**v4.7 delta:** grain-hold v3 shipped inside --grain-replace (E-9: third
amplitude vote, per-slice-band grain-carpet vote, parent threshold 8 at
10-bit, LL-gradient gate removed, soft-threshold coding; encoder-only) plus
new --fill-static flag (stream byte 27 bit 2, bitstream minor 7):
frame-independent grain-fill sign-tile offsets (static grain texture).
Viewer-box ant-tail 18.0% (watched v4.4) -> 7.98%, below fair JPEG XS@2bpp
(7.73%); @1.0bpp 18.6% -> 10.7%. Grain sigma retained 100% on
cow/graincell; beach fine grain 67% + static fill; no flattening
(flat-block rate 0.08% = baseline); exact CBR; minor<=6 streams decode
byte-identically vs pristine v4.6. The ants/blind-viewing beach defect is
**closed pending viewer sign-off** on the _antfix sealed pairs. FPGA cost:
zero new per-pixel multipliers; latency table unchanged. Details:
REPORT §18.7, ENHANCEMENTS_LEDGER E-9/E-10, BITSTREAM §9.5.

**v4.4 delta:** F-1/F-3 defect fixes shipped; deadzone default-on (+0.45 dB);
entropy model v2 shipped (minor 4, +0.08-0.21 dB, held-out validated);
two-vote grain-replace classifier shipped opt-in (4-17% at equal VMAF,
honeypot-safe); per-block MV capability shipped opt-in (measured ~0). Test campaigns (REPORT §17) closed the
forward-signalled-scale and TCQ levers (both falsified against the real v4.4
baseline) and confirmed the coarse-grain-correlation hypothesis with per-clip
measurements: the one surviving pre-RTL coding lever is the correlated-sign
fill (v5 normative candidate, blind-gated). B1/B2 gating below unchanged: blind verdicts remain the gate.


Codebase state: bitstream minor 7, all gates green, feature-complete for the
Contribution (primary) and Studio profiles. Every remaining item below is
listed with exactly what it is pending on.

## A. Pending on the customer / mandate holder

| # | item | pending on | why it matters |
|---|---|---|---|
| A1 | Real footage: captured continuous motion with camera grain; optionally 4:4:4 graphics chains, HDR, high-fps | footage delivery | the ONE question our corpus cannot answer (grain behavior under real motion); gates the final perceptual round and therefore the freeze |
| A2 | Blind-kit verdicts (CLIP/CLIP10, CLIP16, CLIP04/08 - three rate-ratio rungs, sealed keys) | human viewers | decides the 0.5x claim and the 0.4x hypothesis; the acceptance standard is eyes by mandate |
| A3 | Claim-framing ratification (eye-led ~50% vs instrument-led 25-40%; letter Addendum 2) | mandate-holder decision | determines product positioning and default mode before silicon |
| A4 | FPGA SKU sizing (streams per device, max fps per SKU) | product decision | must be explicit so the media-server requirement never silently sizes the contribution part |

## B. Chained: footage -> perceptual round -> freeze -> ecosystem finals

| # | item | pending on |
|---|---|---|
| B1 | Final perceptual round (incl. re-evaluating the parked CSF/eye allocation ladder on real footage with blind eyes) | A1 |
| B2 | **Bitstream freeze** (the gate to RTL) | B1 |
| B3 | Final RTP payload spec (from TRANSPORT_NOTE.md) | B2 |
| B4 | NMOS / BCP-style control profile | B2 |
| B5 | MXF / ISOBMFF container mappings | B2 + a file-workflow customer |
| B6 | Profiles/levels finalization (PROFILES.md draft -> normative) | B2 |

## C. Engineering, unblocked - status after round C (2026-07-28)

| # | item | status |
|---|---|---|
| C1 | Architectural/streaming model | **DONE, both sides** (hw_decoder_model.py + hw_encoder_model.py: memory map + ports + bandwidth + pipeline; decoder byte-exact vs reference, encoder accounting byte-checked vs instrumented reference). RTL correctness proven separately by the conformance vectors. |
| C2 | Encoder worst-case timing bound | **DONE** - measured (max 3 attempts at delivery rate, 9 at 0.4 bpp, 32 adversarial; cap 40); budget in HARDWARE.md 7 |
| C3 | HFR validation + throughput | **DONE** - fps metadata to 120/119.88 verified; fine-step pan gap fixed (+2.2 dB at 3 px/f); software throughput baselined (FPGA-territory, as designed) |
| C4 | Burst-loss traces | **DONE** - harness/loss_harness.py (Gilbert-Elliott + directed); all patterns recover within R at R=2 and R=8, no crashes/range violations |
| C5 | MISRA-class pass | **partial DONE** - clang-tidy subset run, one real leak fixed, deviation register written (STATIC_ANALYSIS.md); licensed-tool certification still partner-gated |
| C6 | Software encoder speed | measured (attempt cascades bounded); optimization opportunistic |

Remaining unblocked engineering: none of substance before RTL - the
architectural handoff (both models), conformance packaging, timing budget,
loss harness, and static-analysis register are all in place. The next
concrete step is RTL itself, which is gated by the bitstream freeze (B2),
which is gated by footage (A1).

## D. Parked, with reopening conditions on record

| # | item | reopens when | record |
|---|---|---|---|
| D1 | Byte-exact generation lock for pans / gain-active grain (today: convergent, bounded, invisible) | someone needs bit-exactness beyond statics | diagnosis in REPORT 11n/12c |
| D2 | Motion-adaptive allocation (moving slices donate budget) | a dedicated artifact round (motion-stop pump test) | REPORT 12d |
| D3 | Deterministic --mv-regions (multi-hop safe fine motion) | same lock machinery as D1 | DESIGN.md 1b |
| D4 | 4:2:0 | a concrete pro-AV/IPMX socket | FEATURE_MATRIX.md |
| D5 | Interlace (design complete, on the shelf) | concrete customer demand | INTERLACE_CONVENTION.md |
| D6 | 14/16-bit, Bayer/RAW, sub-line profiles | a business case in those markets | FEATURE_MATRIX.md |
| D7 | Team A truly-independent decoder (upgrades spec proof from self-checked to independent) | Team A engagement | LETTER_TEAM_A.md |

## E. FPGA phase proper (all pending B2 + C1)

RTL decoder (small; spec + conformance vectors + two reference
implementations + streaming decoder model exist) -> RTL encoder (the real
project: control plane, search, lock; streaming encoder model + memory map
+ timing budget in hand) -> device bring-up -> conformance sign-off
(make_conformance.py vector set is the acceptance instrument).

## The critical path, in one line

Footage (A1) -> perceptual round (B1) -> freeze (B2) -> RTL (E), with C1/C2
proceeding in parallel today so the FPGA handoff is ready the day B2 lands.


## Current resume point (2026-08-04)

The authoritative open-items list is docs/HANDOFF_2026-08-04.md.
Highest value next: finish the independent spec-only decoder under the
no-peeking rule (C8), then the F-4 minor-8 checklist (bias-aware
concealment first), then the mms equal-rate deficit investigation.

---

# v5.1 (2026-08-25) — status and what is next

## Closed in v5.1

- **The lighter/darker blotches** (the owner's eye findings of 2026-08-25,
  items 1 and 3): cause identified in the in-gamut repair, fixed, validated
  across the format matrix. `docs/OMC_V5_1.md`.
- **The conformance folder could not bring up a v5 decoder** (it carried only
  pre-v5 vectors). A v5 class is added.
- **Machine-specific paths in the delivered tree** — `harness/common.py`
  defaulted to a scratch directory on the machine it was written on, and 18
  scripts under `research/scripts/` hard-coded an absolute work tree. All now
  read the environment with a tree-relative default. Historical *logs* under
  `research/results/` and `docs/SESSION_LEDGER_2026-08-12.md` keep their paths:
  they are records of runs, not instructions.

## Open, in the order the measurements rank them

1. **The slice-seam class** (the owner's item 2: visible seam blends at every
   slice border on most clips). NOT addressed by v5.1 and explicitly out of its
   scope. The §51 level map shows the residual: a persistent slight positive
   block bias that survives even with the repair disabled, so it is a different
   mechanism from the blotches. Causes already eliminated by the project record:
   the display blend (contributes exactly 0), the gamut repair (bright slices
   barely repaired), the in-loop boundary edit (suppressing it changes nothing).
   Treat the transform-boundary hypothesis as unproven.
2. **Temporal distortion levelling** (proposed Q9). The distortion-propagation
   recursion of Turaga et al. 2005 §4, applied to OMC's one-reference,
   rolling-refresh structure, so the allocator can spend to keep decoded
   distortion flat *over time* rather than within a frame. Addresses F-12 (the
   repair makes the picture wobble frame to frame) and the owner's item 4
   ("more colour-block updating than JPEG XS"). Encoder-only; IP-clean (an MSE
   recursion, not a coding tool).
3. **Q5 — chunk-granular inter/intra**, the mechanism the goal-(b) programme
   rests on. Its C1 re-derivation chain is now available and written down:
   Mounts 1969 → on-sensor conditional replenishment (mid-1990s) → conditional
   replenishment in the WAVELET domain per precinct with gain-per-byte ordering
   (Devaux et al. 2007, on JPEG 2000) → OMC's own SKIPCHUNK carrier. Nothing in
   that chain passes through JPEG XS.
4. The rest of the goal-(b) programme, unchanged: see the project ledger.
