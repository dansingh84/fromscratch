# Contribution Video Codec — Mandated Constraints & Artifact Definitions

**Revision 6 (2026-07-27), mandate-holder amendment — the measuring stick is the eye, and the
bar is looking better, not scoring better.** The rev. 5 rate relation stands unchanged — the codec
is always tested at R against JPEG XS at 2R, at every useful R — but **"equal quality" is redefined:
PSNR and VMAF are no longer the measure of the match. The mandate is: OMC at half the bitrate must
LOOK the same as — and ideally better than — JPEG XS, to human eyes,** on full-resolution,
full-frame output at real viewing conditions, in motion (Section E's human-review rules).
Consequences, in force from this revision:

- **The decisive test is blind human viewing: OMC @ R against JPEG XS @ 2R.** Same-or-better to
  the eye passes; visibly worse fails. No number overrides the eye in either direction.
- **PSNR and VMAF are demoted to engineering diagnostics.** They may guide development and appear
  in reports, but no PSNR or VMAF comparison is ever again a pass/fail criterion for the quality
  match, and a PSNR deficit against XS @ 2R is not a failure if the eye cannot see it.
- **This is not a parity mandate.** Matching JPEG XS at equal bitrate — on any measure or to any
  eye — remains meaningless to the goal. The comparison is only ever against XS at double the rate.
- **Everything else is untouched:** the exact-CBR half pipe (rev. 4), the ramp rules (rev. 3),
  every Section G artifact prohibition (the permitted degradation is still only smooth softening —
  and it must now survive the eye test against XS @ 2R), latency, generations, loss resilience,
  formats, IP, and hardware constraints all bind exactly as written. Freeing the codec from PSNR
  does not free it from a single artifact rule.

**Revision 5 (2026-07-27), mandate-holder amendment — the half-rate mandate stated exactly.**
"≤ 0.50 × JPEG XS at the same quality" means the codec's whole rate-versus-quality curve sits
**one full octave to the left of JPEG XS's**, at every useful rate:

> **OMC @ 1.0 bpp must equal JPEG XS @ 2.0 bpp.
> OMC @ 2.0 bpp must equal JPEG XS @ 4.0 bpp.
> OMC @ R must equal JPEG XS @ 2R — at every useful R, not only at these anchors.**

"Equal" means the same visual quality — every measure at once (A1) and the human eye decisive
(Section E). What does **not** meet this mandate: matching or slightly beating JPEG XS **at the
same bitrate**. That is parity — a rate ratio of 1.0×, however many fractions of a dB ahead —
and parity at equal bits is not half-rate at equal quality. The amended clause is marked
*(rev. 5)* in A1.

**Revision 4 (2026-07-26), mandate-holder amendment.** The worst frame decides the
contribution pipe: the codec's provisioned pipe MUST always be at most 50% of JPEG XS's —
see the pipe rule added to A1. This binds on every frame of every stream, with no
exceptions; the ramp of rev. 3 relaxes only the *quality* judgement of frames 0–1, never
the pipe.

**Revision 3 (2026-07-26), mandate-holder amendment.** Temporal (inter-frame) prediction is
now sanctioned and expected: the codec should use prediction as much as possible to keep the
bitrate low. Quality accounting changes accordingly: **frames 0 and 1 of a stream (and the two
frames after a scene cut) are a permitted quality ramp** — they may run below the steady-state
quality target provided the ramp is visually unobtrusive (no flash, no visible pop-in, nothing a
normal viewer notices in real-time playback). **Frame 2 onward is steady state and must meet the
full quality bar.** The bitrate pipe is never relaxed: every frame, including ramp frames, fits
the provisioned CBR pipe exactly. Amended clauses are marked *(rev. 3)* in A1, A3, A4, A5, C2,
E and F below.

**What this is:** the complete set of non-negotiable requirements the codec must satisfy, plus a
detailed description of the visual artifacts that must never appear in its output. The constraints hold
*together, simultaneously* — a design that meets one by breaking another does not satisfy the
specification. This document defines the requirement, not the state of any implementation.

The codec's purpose: **fully replace JPEG XS in broadcast television contribution, on all content
types, with no exceptions.**

---

## 0. What this codec is for — broadcast TV contribution

This is a **broadcast television contribution codec**. Understanding that use case is essential, because
every requirement below follows directly from it.

In professional television, "**contribution**" is the link that carries **live video from the point of
capture back to the broadcaster** — from a stadium, a news truck, a concert venue, or a remote studio,
over a network link, to the production facility or network operations centre — *before* the content is
processed, mixed, graphics-added, and finally distributed to viewers. It is distinct from
**distribution** (also called emission), which is the last hop out to the home viewer's TV. Contribution
is the professional, upstream, behind-the-scenes transport; distribution is the consumer-facing delivery.

**This codec is a direct JPEG XS replacement for the whole contribution chain — every point where JPEG
XS is used, not a single hop.** In a typical live production that means at least two distinct legs, and
the same codec must serve both:

- **Camera → switcher.** The individual live camera feeds carried from the venue into the production
  switcher (the vision mixer), typically on-site — e.g. inside an outside-broadcast (OB) truck. Many
  independent camera feeds, each of which must arrive clean and near-instant for the director to cut
  between them on-air.
- **Switcher → broadcast center.** The produced/mixed program feed carried from the switcher back to
  the broadcast center (network operations / studio) over the contribution network link.

It is **one single codec for the entire path — not two.** The same encoder, the same decoder, and the
same bitstream format are deployed identically at every leg. There is no camera-to-switcher variant and
a separate switcher-to-broadcast-center variant; there are no per-leg profiles or special modes. One
design drops into every point where a JPEG XS encoder/decoder pair sits in the contribution path and
replaces it, unchanged.

A direct consequence of one codec at multiple legs is that **a single picture is encoded and decoded
several times before it is ever distributed** — see the generation-robustness requirement (A4), which
this multi-point deployment makes unavoidable.

Contribution has a specific and demanding profile that dictates this codec's requirements:

- **It is live and interactive.** Contribution feeds are used in real-time production — live remote
  interviews, multi-site coordination, camera feeds cut on-air as they arrive. Delay is intolerable.
  **This is why latency must be sub-1 millisecond at every supported resolution — not "low," but
  effectively imperceptible.**
- **It is a mezzanine, not a final delivery.** A contribution feed is not the last compression the
  picture will see — it will be decoded, produced on, and then **re-encoded again** for distribution.
  Any artifact introduced here is baked in and amplified by everything downstream. **This is why the
  quality bar is visually-lossless / near-perfect, why visible compression artifacts (Section G) are
  disqualifying, and why quality must survive multiple re-encode generations.**
- **It runs on constrained, real professional networks** (bounded-bandwidth links between sites that
  drop packets and jitter). **This drives both the bitrate goal — beating JPEG XS by 2× on the worst
  frame — and the error-resilience requirement (A5).**
- **It must run in dedicated broadcast hardware** (encoders and decoders in racks, cameras, and
  gateways — typically FPGA). **This is why both ends must be FPGA-native** (shifts/adds/lookups, no
  per-pixel multipliers, no adaptive arithmetic coding).
- **The incumbent is JPEG XS**, the low-latency mezzanine codec this product exists to displace. It is
  patent-encumbered; this codec must reach the same use case with clean, royalty-free IP.

Every requirement below is a direct consequence of this use case.

---

## A. The performance mandate

### A1. Bitrate — at most half of JPEG XS, at every useful quality level, on steady-state frames, into a fixed pipe *(rev. 3)*

- **The bar:** to reach any given picture quality, the codec must use **at most half the bits JPEG XS
  needs to reach that same quality** — ≤ **0.50 × JPEG XS**.
- ***(rev. 5)* Stated as the equality it is: OMC @ R = JPEG XS @ 2R, at every useful R.**
  OMC at 1.0 bpp must deliver the visual quality JPEG XS delivers at 2.0 bpp; OMC at 2.0 bpp must
  deliver what JPEG XS delivers at 4.0 bpp; and so on at **any** rate a broadcaster would run —
  the anchors above are examples, not the definition. Equivalently: the codec's rate–quality curve
  must sit **one full octave to the left** of JPEG XS's, everywhere in the useful range. The test
  is always OMC @ R against JPEG XS @ **2R** — never against JPEG XS @ R. Matching or beating
  JPEG XS **at equal bitrate** is parity (1.0×) and **does not meet this bar**, regardless of the
  margin; a codec that needs about the same bits as JPEG XS for the same quality fails the mandate
  even if it is ahead at every equal-rate anchor. ***(rev. 6)*** "Same visual quality" is judged
  **by blind human viewing alone** (full-frame, full-resolution, in motion): OMC @ R must look the
  same as or better than JPEG XS @ 2R. PSNR and VMAF are diagnostics only and never the pass/fail
  measure — in either direction.
- ***(rev. 4)* The worst frame decides the contribution pipe — the codec MUST always be 50% of
  JPEG XS.** The link is provisioned at **at most 0.50 × JPEG XS's provisioned CBR rate**, and
  **every frame — including the worst frame, ramp frames, cut frames, and motion bursts — must fit
  that pipe exactly.** There is no frame, no content, and no condition under which the codec may
  exceed half of JPEG XS's provisioned rate. (The rev. 3 ramp relaxes only how frames 0–1 are
  *quality-judged*; it never relaxes the pipe.)
- ***(rev. 3)* Steady-state accounting.** Temporal prediction is sanctioned and encouraged. The
  quality bar is judged on **steady-state frames — frame 2 of the stream onward** (and, after a
  scene cut, from the second frame after the cut onward), on the **worst steady-state frame** of a
  window, never on averages. Frames 0 and 1 (and the two frames after a cut) are the **ramp**: they
  are excluded from the quality-match comparison but are **never excluded from the pipe** — every
  frame, ramp included, must fit the provisioned CBR rate exactly.
- ***(rev. 3)* The ramp must be invisible in use.** The two ramp frames are steps toward full
  quality: quality must increase monotonically, with no flash, no visible pop-in or "snap" at
  frame 2, and nothing a normal viewer notices at real-time playback. Ramp visibility is judged
  by human review (Section E) like any artifact; a noticeable ramp fails.
- **This is the whole rate-versus-quality curve, not one operating point.** The 2× advantage must hold at
  **every useful quality level** — every quality a real broadcast customer would actually run at, from
  visually-lossless down to the lowest quality still worth shipping — **not merely at one threshold where
  a single metric happens to cross.** The test is: pick *any* useful quality; compare the bits JPEG XS
  needs to reach it against the bits this codec needs to reach the *same* quality; the codec's number
  must be at most half — at that level **and at every other useful level.** A codec that is half the rate
  at one chosen quality point but only *matches* JPEG XS (parity, not half) at other useful levels **does
  not meet this bar.** One favorable crossing point is not the requirement; the whole curve is.
- **"Same quality" must hold on every measure at once — it can never be won on one metric by giving up
  another.** Maintained quality means maintained VMAF **and** maintained brightness accuracy (luma PSNR)
  **and** maintained color accuracy (per-plane chroma) **and** the human full-frame verdict (Section E),
  *all together*. Reaching a target VMAF at half the bits while letting color accuracy fall below the
  incumbent's is **not** meeting this bar — it is trading one quality axis away to buy another and
  reporting only the flattering one. No single metric establishes "same quality"; **VMAF least of all,
  because it is largely brightness-driven and barely weighs color**, so a design can raise its VMAF by
  starving color and look better on that one number while the picture is not actually better. Where any
  metric and the human eye disagree, **the eye decides (Section E) — including for color.**
- **Accounting is PIPE:** the codec's frame bits ÷ JPEG XS's *provisioned rate at service quality* (XS
  is provisioned CBR and never dips, so its provisioned rate is the fixed reference).
- **Worst frame decides — never averages.** The bar is a worst-frame requirement; average bitrate is
  never the measure.
- **Both matched chroma configurations:** the 0.50 bar must hold with **both codecs at 4:2:2** *and*
  **both codecs at 4:4:4**. A mixed configuration does not count.
- **Fits a fixed provisioned pipe.** Contribution links are fixed-bandwidth. The codec must operate in a
  **constant-bitrate / capped-VBR mode that holds the provisioned link rate exactly**, with a **bounded
  buffer that never overflows or underflows** — the stream must fit the pipe on *every* frame, not just
  on average.
- **The commercial aspiration (not just the floor):** the point of the codec is *better* picture at
  half the bits, not merely equal — quality-parity-or-better versus the incumbent at ≤ 0.50× its rate.
- **Quality is won within the budget, never bought with bits.** Solving a quality or artifact problem
  may not raise the bitrate; the ceiling is unconditional.

### A2. Latency — sub-1 millisecond, deterministic, at every resolution

- **The bar:** **sub-1 ms** total codec latency (encode + decode algorithmic buffering: capture wait +
  paced unit transmission + decode start) at **every supported resolution and frame rate — from the
  720p floor upward, no exceptions** (see B4). The incumbent's latency figures are context, never the
  definition of the bar.
- **Deterministic, not just low.** Latency must be **constant and predictable** frame-to-frame.
  Broadcast is genlocked — feeds must hold sync; variable latency breaks lip-sync and multi-camera
  timing. A codec whose latency wanders does not meet the bar even if its average is under 1 ms.
- **Strictly causal by construction** (see C2) — the latency bar is only achievable causally.

### A3. Quality — VMAF ≥ 97 where the rate envelope allows

- **The bar:** VMAF ≥ 97 where the bitrate envelope allows it.
- **Content-relative where it can't:** on content hard enough that incumbent-class quality collapses,
  the requirement is *decisively better than the incumbent at the same bits* — never chasing 97 at
  ruinous bitrate.
- **Cut frames *(rev. 3)*:** a scene cut restarts the two-frame ramp of A1: the cut frame and the
  following frame may relax toward the 0.50 budget, with full steady-state quality restored by the
  second frame after the cut. The relaxation must satisfy the same invisibility requirement as the
  stream-start ramp. A quality-protection mode remains available for QC-sensitive workflows.
- **No visible compression artifacts.** None of the artifacts described in Section G may be present in
  delivered output. They must be prevented at the codec core, not hidden after the fact.
- **The one permitted degradation.** Under bitrate pressure the **only** acceptable form of quality loss
  is a **graceful, smooth softening** — a mild, defocus-like blur — **of regions that are already out of
  focus in the source.** Nothing else is acceptable: not the 32×32 grid, not blocks, not pixelation, not
  flattening/blotches, not hard edges, not discoloration (Section G). The softening must always be
  **smooth, never stepped** — softness is not banding and must never become banding. **Color banding is
  never permitted**, at any bitrate, in any region; the permitted softness does not extend to it.

### A4. Generation robustness — quality must survive multiple encode/decode generations

- **The bar:** because the same codec sits at multiple points in the contribution path (§0), a single
  picture is **encoded and decoded several times end-to-end** before it is ever distributed — each
  encode→decode pass is a "generation" (camera→switcher is one; switcher→broadcast center is another;
  real workflows add more). The codec must **retain exact quality across these multiple generations,
  with no accumulating loss** — the picture after the last generation must be effectively identical to
  the picture after the first, not degraded a little further at each hop.
- **Why this is disqualifying if missed:** "generation loss" — quality quietly eroding every time the
  signal is re-encoded — is a classic failure mode of codecs not built for contribution, and it is
  fatal here. A contribution/mezzanine codec exists to hand downstream a **pristine picture no matter
  how many times it has been through the pipe.** A codec that looks perfect on a single pass but
  softens or accumulates artifacts over several generations does not meet the specification, even if
  each pass would pass A3.
- **Distinct from `rt = 0` (C4).** `rt = 0` guarantees the decoder reproduces the encoder's own
  reconstruction *within one pass*; generation robustness is about what happens when that decoded output
  is **re-encoded again** by the next codec in the chain — it must not degrade with each re-coding.
- ***(rev. 3)* With temporal prediction:** the requirement applies to steady-state output. Each
  generation may use its own two-frame ramp, but from frame 2 onward the picture handed downstream
  must show no accumulating loss across generations, exactly as before.

### A5. Error resilience — graceful survival of a lossy network

- **The bar:** contribution runs over real IP networks that drop packets, reorder, and jitter. The
  codec must remain usable under loss, not just on a clean link. Specifically:
  - **Contain errors spatially:** a lost or corrupted packet damages only a **small, bounded region of
    one frame** — never the whole frame, and never propagating uncontrolled across the frame or forward
    into later frames.
  - **Recover fast:** resynchronize to clean decoding within a **bounded, small number of frames** after
    any error, via defined recovery points. ***(rev. 3)*** With temporal prediction this bound is
    load-bearing: prediction may propagate a loss forward, so the codec must carry defined refresh
    mechanisms (e.g. rolling intra refresh) that guarantee complete recovery within the stated bound,
    and the bound must be documented and measured.
  - **Degrade gracefully:** under loss the picture should soften or show a localized, bounded artifact
    rather than break up, freeze, or go to garbage.
- **Why it is fundamental:** this is as core to contribution as latency. A codec that is pristine on a
  clean link but shatters on a lossy one does not meet the use case.

---

## B. Signal formats & operating range (what the codec must handle)

### B1. Bit depth — professional depth, not consumer

- **10-bit minimum** — the broadcast professional standard; 8-bit is not sufficient for contribution.
- **12-bit** must be supported for high-end / wide-dynamic-range workflows.

### B2. Chroma sampling — broadcast-native, ingested as YCbCr

- **Native 4:2:2** — the broadcast contribution workhorse — ingested **directly as YCbCr**, with **no
  lossy detour through RGB**.
- **4:4:4** also supported (for content that needs it, e.g. graphics/keying).
- 4:2:0 is a distribution format and is not a contribution requirement.

### B3. Color space & dynamic range — SDR and HDR, wide gamut

- **Transparent to the broadcast color signal:** SDR (**BT.709**) and HDR — **BT.2020** wide color
  gamut with **PQ and HLG** transfer.
- The codec must carry the color space and HDR's expanded value range **without introducing color error
  or banding**, and without assuming SD (BT.601) primaries/matrix on HD/UHD content.

### B4. Resolution & frame rate — 720p and up, every one sub-1 ms

- **Resolution:** the supported range **starts at 720p** and **scales upward** — 1080p (HD), 2160p
  (UHD/4K), and higher. 720p is the **floor**, a full first-class format, not a special reduced-latency
  tier.
- **Frame rate:** standard broadcast rates (50, 59.94, 60) and upward as formats scale (including
  high-frame-rate operation).
- **Sub-1 ms at every one:** the A2 latency bar applies at **every** supported resolution and frame rate
  from the 720p floor up — no format is exempt.

---

## C. Permanent engineering constraints

### C1. Royalty-free / clean IP — always

- Open-standard, royalty-free, expired-vintage, or own-work techniques **only**. Royalty-free is an
  *ingredient* property (clean IP inside); the codec itself is a commercial product to sell/license.
- **Forbidden:** MPEG-LA pool codecs; HEVC/AVC internals; JPEG XS internals; **CABAC**; **rANS anywhere
  in the codebase, even experimental or disabled** (patent risk — entropy coding builds on tANS only,
  and any rANS re-entry requires prior IP-counsel clearance); any per-unit fee.
- **Allowed:** ISO/IEC 15444-15 / HTJ2K (royalty-free by committee design, with its upstream BSD-2
  notice carried).
- IP status is verified before any technique is used; vintage is noted in commits.

### C2. Strictly causal *(rev. 3)*

- **Look-back only** — never future frames or lines beyond the declared causal window.
- ***(rev. 3)* Single-frame temporal reference permitted.** The decoder may retain **exactly one
  previous reconstructed frame** as the temporal prediction reference. **No frame libraries, no
  long-term or multi-picture recall** — one frame of look-back, nothing more. Per-frame statistics
  learning remains permitted.

### C3. Comfortably FPGA-native — both encoder and decoder

- **Shifts, adds, and table lookups only.** **No multipliers in per-pixel paths. No adaptive arithmetic
  coding.**
- **Both ends real-time in hardware.** The requirement is not decoder-only — the encoder also runs live
  in professional hardware (cameras, OB-truck gear), so encode complexity must likewise be bounded and
  hardware-implementable in real time.
- **"Comfortably" is literal:** the hardware op/DDR budget must be met **with margin**, not at the edge.
  A design needing a per-pixel multiplier or an arithmetic coder is the wrong design.

### C4. Verify-before-commit — `rt = 0`, all planes

- The decoder's reconstruction must be **byte-exact equal to the encoder's** (`rt = 0`), on **all
  planes**. Nothing counts as correct until this holds.
- Correctness, quality, hardware-op, and causality checks are all satisfied, and every claim is stated
  with its measurement.

### C5. Color, always

- **Never measure, gate, or compare luma-only against a color original.** Round-trip checks cover all
  planes; quality verification reports per-plane figures (Y, Cb, Cr) plus a channel-spread collapse
  tripwire; every incumbent comparison states chroma quality at the match point. This is absolute.

### C6. Measure first

- **Measured evidence gates decisions, not estimates.** If a measured cost contradicts an estimate, the
  design is stopped and reconsidered rather than pushed through.

### C7. Fully self-reliant — video in, bitstream out, nothing else

- The codec is a **standalone black box, exactly like any other professional codec.** The encoder's
  only input is the video signal; its only output is the compressed bitstream. The decoder's only input
  is that bitstream; its only output is the reconstructed video. Nothing else crosses the boundary.
- **No access to, and no dependency on, anything outside the codec.** Not the production/show controls,
  not the switcher's state or "take" signals, not camera/lens metadata, not the production system it
  sits inside, not any external side channel. Everything the codec needs — scene-cut detection, motion,
  rate control, every decision — must be derived from the **video and the bitstream alone.**

### C8. Standardized, documented, versioned bitstream

- The bitstream must be a **stable, fully-documented, versioned format** so multiple vendors interoperate
  — an encoder from one supplier feeding a decoder from another, exactly as JPEG XS (an ISO standard)
  allows. **No undocumented or vendor-locked bitstream.**

---

## D. Scope boundary — video essence only

The codec is responsible for the **video essence only.** The following are the **transport layer's**
responsibility — carried alongside the coded video, not inside it — and are explicitly **out of scope**
for the codec itself:

- Embedded audio, timecode, closed captions/subtitles, SCTE/ad markers, and other ancillary (VANC) data.
- Content encryption / protection in transit.
- The IP transport itself: packetization, professional-media IP carriage, and any forward-error-
  correction or retransmission the network layer applies.

The codec must be **compatible with and transparent to** that transport (video feed in, compliant
bitstream out), but it does **not** carry or interpret those non-video streams. A5's error resilience is
the codec's own intrinsic robustness; any transport-layer FEC is additive on top of it, not a
substitute for it.

---

## E. Evaluation & acceptance

- **Bitrate and quality are judged on the worst steady-state frame, never on averages** (A1
  *(rev. 3)*: frames 0–1 and the two frames after a cut are the permitted ramp; everything from
  frame 2 onward is judged at full bar). Ramp invisibility is itself an acceptance item: reviewed
  as real-time playback by a human, a noticeable ramp or a visible snap at frame 2 is a failure.
- **The bitrate advantage is evaluated across the whole rate-versus-quality curve, not at a single
  point** (A1, rev. 5). The comparison is always **OMC @ R against JPEG XS @ 2R** — swept across the
  useful range, never OMC against XS at equal rate. Demonstrating ≤ 0.50× at one convenient quality
  threshold is not sufficient: the sweep must confirm the codec needs at most half of JPEG XS's
  bits to match it **at every useful quality level.** And "match" must be confirmed on **all** quality
  measures together plus the human eye — never a single metric (e.g. VMAF alone) at the expense of
  another (e.g. color accuracy). A half-rate result at one threshold that collapses to parity elsewhere,
  or that is bought by trading brightness score against color, fails the requirement even though the one
  headline number looks right.
- **Every picture-quality test is evaluated on the FULL FRAME, never on a zoomed-in or cropped region.**
  A crop or zoom shows only what it contains, so a region-scoped test cannot reveal:
  - a **side effect** a change introduced *elsewhere* in the frame (a fix can improve the area it was
    aimed at while making another part worse, or move a defect from the tested region into an untested
    one), or
  - that the **defect is not actually fixed** — that the same problem still persists outside the cropped
    area even though it looks resolved inside it.

  A crop may be used to *point at* a location of interest, but it is never sufficient on its own to
  conclude a change worked. The whole frame must be assessed.
- **No numerical quality metric can be trusted to tell whether a picture is truly high quality.**
  MSE, PSNR (including per-plane Y-PSNR), VMAF, SSIM, VIF, and every automated detector or tripwire are
  **guides only** — a picture can score well on all of them and still be visibly wrong, and in practice
  it does. These metrics measure a mathematical proxy, not perceived quality; they routinely miss
  exactly the localized, structured artifacts (Section G) that a human sees immediately. Where this
  document uses a metric as a bar (e.g. VMAF ≥ 97 in A3), clearing that bar is a **floor to meet, never
  proof the picture is good.** A metric win is never, on its own, evidence of quality.
- **This applies equally to testing for the *absence* of artifacts.** An automated detector, tripwire,
  or numerical check reporting "no artifact" is **not proof the artifact is gone.** A detector can miss
  it, or a change can move the artifact to a region the detector is not weighting — a passing number can
  hide that the problem was never fixed, only relocated. Artifact-freedom (Section G) is confirmed only
  by direct human review of the full frame, never by a passing detector or metric.
- **The only decisive verdict on picture quality is direct human visual review of the full-resolution,
  full-frame output.** No computed number overrides it. (Full-*resolution* and full-*frame* are separate
  requirements: full-resolution means not downscaled — downscaling hides the pixel-scale grid in G1;
  full-frame means not cropped — cropping hides the rest of the picture.) No mockup or simulated output
  may stand in for real codec output.

---

## F. One-line summary

One codec for the whole contribution path, using temporal prediction to beat JPEG XS's bitrate by
2× — **OMC @ R = JPEG XS @ 2R, the whole curve one octave left** — at **every useful quality
level** on **every steady-state frame** (frame 2 onward; frames 0–1 a
visually-unnoticeable ramp), quality judged on every measure *and* the human eye together,
never one metric bought at another's expense, in constant sub-1 ms latency at every resolution from 720p up, resilient on a
lossy network, on FPGA-friendly hardware at both ends with clean royalty-free IP, self-contained (video
in, bitstream out, nothing else), carrying professional 10-/12-bit SDR-and-HDR 4:2:2 broadcast video,
holding exact quality across multiple encode/decode generations, proven byte-exact on every color
plane — all at once, no trade-offs.

---

## G. The artifacts that must not appear (what they look like)

These are the visual defects that must never be present in output. This section describes **what each
one looks like** and **how to spot it**. Several overlap or share a cause, but they present differently
to the eye and are named separately so they are not conflated.

### G1. The 32×32 grid (also called "tiles")

**What it is.** The codec internally divides every frame into a fixed grid of 32×32-pixel squares. When
compression goes wrong, that grid becomes visible in the *output* even though it does not exist in the
*source* — a regular lattice of squares tiled across the entire frame.

**What it looks like.** Adjacent squares are treated differently from one another: one square keeps its
fine detail/texture while the square right next to it is smoothed flat. The result is a patchwork /
checkerboard where you can make out the square boundaries — some cells "busy," their neighbors "empty."
The seams run in **both directions** — vertical lines between columns of squares *and* horizontal lines
between rows — so it reads as a full two-dimensional grid laid over the whole image, not streaks in a
single direction. It is worst on detailed or grainy content (animal fur, foliage, skin texture, grass),
where the keep-detail-versus-flatten outcome differs sharply between one square and the next.

**How to spot it (identification method).** The grid can be subtle at normal brightness and normal
viewing. To reveal it:
- **(a)** increase the image brightness, **and**
- **(b)** overlay a 32×32 grid across the entire image, then look at how the chroma (color) and luma
  (brightness) happen to correspond with that grid — the artifact shows itself where the content's
  transitions line up with the grid boundaries.

*Note:* this brightness-plus-grid-overlay method only helps you **see the 32×32 grid**. It does not help
identify any of the other artifacts below.

### G2. Blockiness / banding (also called "blocks")

**What it looks like.** A smooth, continuous gradient in the source — most visibly a clear sky, a
stadium field, a gently shaded wall — renders as a series of flat, stepped bands instead of a smooth
transition. Rather than tone changing gradually, you see discrete "steps" or "terraces," like the
contour lines on a topographic map, with a visible edge (a color/brightness cliff) between each band.

**Color banding specifically is forbidden.** Banding occurs in both brightness and **color** — "color
banding," where a smooth color gradient breaks into flat bands of slightly different hue or saturation
(a subtly striped sky, a stepped skin-tone gradient), is a specific and common form of this defect and
is equally unacceptable. It must never be introduced, and the "permitted softness" allowance (A3) does
**not** extend to it — softening a region is smooth; banding it is not.

**How it differs from the grid.** This is smooth areas becoming *stepped*, not detailed areas becoming
*patchy*. It is worst on sky and other large, smooth gradients — exactly the places where there was no
real detail to begin with, only a slow, even change of tone.

### G3. Pixelation

**What it looks like.** Isolated, single-pixel (or tiny-cluster) deviations scattered across an area —
stray dots of wrong brightness or, more often, wrong color that clearly do not belong, like sparse
speckle or "thrown" pixels. It is disorganized and random-looking, and tends to concentrate in the
color (chroma) rather than in structure.

**How it differs from the grid.** The grid is organized and regular; pixelation is scattered and
irregular — individual wrong pixels, not a repeating lattice.

### G4. Flattening / blotches

**What it looks like.** A region where the real texture or detail the source actually contained is
simply gone, replaced by a smooth, empty patch. In brightness, this is fur / fabric / grass detail
dissolving into a featureless smear. In color it is worse: the patch comes out as a flat, often
visibly-wrong single color — a discolored blotch — for example a dark area losing its true color and
going gray or shifting to the wrong hue. It is the same underlying event as the "texture-kill" that
produces the grid, described as the *patch itself* rather than as the grid pattern. ("Flattening" and
"blotches" name the same defect — real detail replaced by a flat patch, sometimes a wrong-colored one.)

### G5. Hard edges

**What it looks like.** A sharp, abrupt boundary between two differently-colored or differently-valued
groups of pixels, at a place where the source has a smooth or gradual transition. Where the real image
eases from one tone into another, the output snaps between them with a visible hard line, as if two
flat regions were pasted together.

### G6. Discoloration

**What it looks like.** Color coming out wrong — a region's real color replaced by a different, wrong
color; or collapsing toward gray / neutral (a loss of saturation); or a color *cast*, where the average
color of an area is shifted off from the source. It tends to concentrate in the darker parts of the
image. This is the color (chroma) face of the flattening/blotch problem in G4.

---

*All six are unacceptable in delivered output regardless of bitrate. The requirement is that the codec
cannot produce them at its core, not that they are cleaned up afterward.*
