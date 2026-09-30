# BRIEF — group SA19 (three agents: SA19 designer, SA19P and SA19Q ideation), 2026-09-29

## 1. Read first, yourselves, in full
1. `/home/user/fromscratch/OMC_CLOUD/Project/PROJECT_CONSTRAINTS.md` (rev. 6).
2. `/home/user/fromscratch/OMC_CLOUD/Project/Subagents/DESIGNER_READING_PACK_FULL.md`. This is every owner ruling, method, test and result of all earlier designers (SA12–SA18, a verified document); its front guide maps sections to topics.

Where this brief adds to or changes the pack, this brief wins.

## 2. Your task: design the codec FROM SCRATCH, for the CURRENT goals and the BIG PICTURE at the same time
**FROM SCRATCH (owner, binding):** do NOT duplicate, extend or repair any earlier designer's design (CPV-1, CQP-1, CPP-LL, …). Repairing a previous design is patching and loses innovation (S5.384; SA18 was stopped partly for this). Owner clarification: you MAY be inspired by earlier designers and pick and choose individual elements from any of them (each must earn its place; note its origin in DESIGN.md); you may NOT take an existing design as the base to continue from. Earlier models may be used ONLY as measuring instruments. Start with 2–3 genuinely different architectures of your own.

The owner wants one design created with both in mind, because the big-picture levers change what the current goals cost.

His example: a damage-free compressed frame buffer lets multi-frame prediction fit, which saves bits that can go into quality.

### 2a. Current goals (all required; see pack §1)
1. **No seam or smudge.** No special row, and no blotches beyond today's (owner's artifactmap/smudgegroups, per plane).
2. **Legal by construction:** zero bits, zero quality cost, and NEVER moving a sample away from the source.
3. **Byte-exact** through CBR and baseband hops, for unlimited generations, with only the image crossing. That includes mid-stream join and loss recovery.
4. **Efficiency at least today's,** VMAF-NEG first including the worst frame, at REAL code lengths. The current best (SA17/SA18) fails this on static-camera content and on fast motion at 0.5 bpp.
5. **Still areas show ZERO change.** No flicker, and no scheduled or pulsing refinement: update only when something changed.
6. **Loss recovery under 4 frames:** on-demand with a return path; a 2–3 frame cycle on one-way links (cycle 2 measured OK, cycle 3 gives 4 frames, which fails); no long-wave machinery.
7. **Latency never noticeably longer than JPEG XS,** and under 1 ms including conversion. 720p50 with 3:1 conversion is accepted at about 0.99 ms.
8. **8K fits today's memory,** on-chip and DDR.

### 2b. Big-picture challenges (design for these too)
1. Spend FEWER bits to paint the same picture, so the saved bits buy quality.
2. FREE quality-improvement mechanisms, with the same net effect.
3. Motion quality: no big quality drop on motion. Fast motion is where OMC must beat JPEG XS.
4. Temporal efficiency, especially on high motion, to save bits.
5. Refresh without spreading damage, on both return-path and one-way links, under 4 frames.
6. Eliminating artifacts: row patterns, text blotches, texture loss, flicker.
7. Latency parity with JPEG XS in every format, including resolution conversion.
8. A COMPRESSED FRAME BUFFER that damages nothing (see §3).
9. Remaining formats later: 16-bit, 4:0:0, 4:4:4:4.
10. Join and exactness through every hop type.

## 3. New owner rulings since the pack's snapshot (binding)
- **C2 (ledger S5.393).** The single-reference limit was about SIZE only. Multi-frame PREDICTION is PERMITTED if the reference frames are compressed so they fit, and nothing else is damaged: recovery under 4 frames with no damage hiding in older references, join, exactness, latency parity, 8K memory, quality.
  - A frame LIBRARY or long-term store remains FORBIDDEN ("no moving frame is exactly identical").
  - A compressed frame buffer must be lossless, or proven exact, if it feeds prediction. It must never degrade prediction on motion.
- **Still areas (S5.390):**
  - update only when something changed (source, or remaining decoded-vs-source error);
  - no timed events;
  - no visible pulse, and no sharp-next-to-soft grid during catch-up (the HVBC-class step).
- **Unworkable design:** "If we design something that doesn't work, then the design is the problem." Never relax a requirement, and never write "structural" or "FAILS" as an end state. Two ideas are never the whole option space.
- **Progress:** a group is shut down when it has clearly stalled (no progress on the open goals). Deliver measured results early and often.

## 4. The three roles
- **SA19 (designer)** runs the show: it decides, builds the numpy models, runs every test, and writes `Subagents/SA19_design/DESIGN.md` and `RESUME.md`.
- **SA19P and SA19Q (ideation)** think problems through with SA19 and with each other. They bring root-level ideas, check them against the pack, challenge assumptions and flag patching. They may disagree. They do NO building or testing and stay LOW on tokens.
- **Group conversation:** every message goes to BOTH other agents (SendMessage), plus one line in the shared log `Subagents/SA19_design/GROUP_LOG.md`. Read the latest log entries before replying.

## 5. Method (pack §2 applies in full)
- Real code lengths, with tables trained on footage disjoint from the test cells AND on the exact configuration being measured. SA17 and SA18 were both misled by a train/measure mismatch.
- Every figure NEG first, then PSNR Y/Cb/Cr, including the worst frame.
- Reproduce a known result on any reused bench before trusting it (e.g. SA17's dng720 @0.5 88.97).
- Detached job queues, at most 6 parallel; keep RESUME.md current after every item.
- Correctness first. SA18's last open breaks:
  - ext10 @1.0/@2.0: one gen-2 frame with different bits;
  - gfx @0.25: 50 prefix overs.
- You may read earlier sandboxes as evidence. Change nothing outside `Subagents/SA19_design/`. `.work/v537` is read-only.

## 6. Deliverable
DESIGN.md, written incrementally, meeting pack §2's deliverable list, plus a section on how the design serves each big-picture item in §2b.

Final message: a short summary, every figure NEG first then per plane, and the weakest point.
