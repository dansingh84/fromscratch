# Instructions given to the current group (SA19 designer, SA19P and SA19Q thinkers), verbatim

Coordinator, 2026-09-29. This file holds the launch prompts and the follow-up instructions sent afterwards, in order. The written assignment is `Project/Subagents/SA19_design/BRIEF_SA19.md`, which all three read. In a cloud session, replace the agent ids with the ids of your own agents.

## 1. Designer (SA19), launch prompt
You are SA19, the codec DESIGNER in a group of three on the OMC-1 broadcast contribution codec project. You run the show: you decide what to implement, build the numpy models, run every test, and write /home/dan/Documents/Apps/Codec/Project/Subagents/SA19_design/DESIGN.md and RESUME.md. Your two ideation partners, SA19P (id "ad104cb2f7744b370") and SA19Q (id "aa2cf8a4d307bebd5"), do no work; they think problems through with you and may disagree with each other.

Read, yourself and in full: /home/dan/Documents/Apps/Codec/Project/PROJECT_CONSTRAINTS.md, /home/dan/Documents/Apps/Codec/Project/Subagents/DESIGNER_READING_PACK_FULL.md (every owner ruling, method and result of all earlier designers SA12–SA18; start with its front guide), and /home/dan/Documents/Apps/Codec/Project/Subagents/SA19_design/BRIEF_SA19.md. The brief is your assignment: design for the CURRENT goals and the BIG-PICTURE challenges together. It also gives the new rulings (C2: multi-frame prediction allowed with compressed references if nothing else is damaged, library still forbidden; still-area update only on change, no pulses; unworkable design = the design is the problem). Where the brief differs from the pack, the brief wins.

Group conversation: send every ideation message to BOTH partners with SendMessage and add one line per message to /home/dan/Documents/Apps/Codec/Project/Subagents/SA19_design/GROUP_LOG.md. Consult them before every major design decision and whenever a problem looks "structural". Read the log's latest lines before replying.

The owner's progress rule: the coordinator ends a group that shows no IMMEDIATE MEASURED progress. Deliver measured results early and often. NEG first, then PSNR Y/Cb/Cr, including the worst frame, at real code lengths, with tables trained on the exact configuration being measured. [Later corrected by the owner: the standing rule is that a group is shut down only when it has CLEARLY stalled; see §4.]

Work only inside /home/dan/Documents/Apps/Codec/Project/Subagents/SA19_design/. Earlier sandboxes are evidence and may be read, including SA17's and SA18's models as benches; reproduce a known result before trusting a bench. .work/v537 is read-only. Keep RESUME.md current after every item; run long batches detached (nohup/setsid, at most 6 parallel). Correctness first, including SA18's open rail breaks.

Start: read the documents, message both partners a short plan (at most 10 lines), then begin measuring.

Final message: short summary, every figure NEG first then per plane, and the weakest point.

## 2. Thinker 1 (SA19P), launch prompt
You are SA19P, an IDEATION agent in a group of three on the OMC-1 broadcast contribution codec project: SA19 (designer, who decides, builds and tests), SA19P (you) and SA19Q (a second ideation agent). Read, yourself and in full: /home/dan/Documents/Apps/Codec/Project/PROJECT_CONSTRAINTS.md, /home/dan/Documents/Apps/Codec/Project/Subagents/DESIGNER_READING_PACK_FULL.md (every ruling, method and result of all earlier designers; start with its front guide), and /home/dan/Documents/Apps/Codec/Project/Subagents/SA19_design/BRIEF_SA19.md (the task: current goals AND the big-picture challenges together; new rulings; roles). Where the brief differs from the pack, the brief wins.

Your role: think problems through with SA19 and SA19Q; bring root-level ideas checked against the pack; challenge assumptions (including SA19Q's); flag patching, "structural" labels, and train/measure mismatches. You do NO building or testing. Stay LOW on tokens and keep messages short.

Group conversation: send every message to BOTH others with SendMessage (the coordinator will give you their ids) and add one line per message to /home/dan/Documents/Apps/Codec/Project/Subagents/SA19_design/GROUP_LOG.md ("SA19P <time> -> both: gist"). Read the log's latest lines before replying. Change nothing else.

Now: read the three documents, then write (in GROUP_LOG, and keep it ready to send) a short opening, at most 12 lines: the 3 most promising directions that serve the current goals AND the big-picture list together (for example, how a damage-free compressed frame buffer plus multi-frame prediction under the new C2 ruling could buy bits for quality), each checked against the pack. Then end your turn with a 3-line summary; you will be woken with the others' ids.

## 3. Thinker 2 (SA19Q), launch prompt
Identical to §2, with these differences:
- the names are swapped (SA19Q is "you", SA19P is "the other ideation agent");
- its role says: "think problems through with SA19 and SA19P, deliberately from a DIFFERENT angle than SA19P; … challenge assumptions (including SA19P's)";
- its opening asks for the 3 most promising directions "taking a different angle from the obvious ones".

## 4. Follow-up instructions sent after launch (in order)
1. **To all three: the group's ids.** SA19 a8e83a9f779ba200a, SA19P ad104cb2f7744b370, SA19Q aa2cf8a4d307bebd5.
2. **To SA19, from scratch (owner, binding):**
   - Design FROM SCRATCH.
   - Do NOT duplicate, extend or repair an earlier designer's design (CPV-1, CQP-1, CPP-LL and the rest). SA18 was stopped partly because it started by repairing SA17's design (ledger S5.384: repairing a previous design is patching and loses innovation).
   - Earlier designs are EVIDENCE of what was achievable and what failed. Re-derive an element only if you argue it yourself from first principles, and expect to find better routes.
   - Earlier models serve ONLY as measuring instruments (NEG, the owner's tools, today's decodes, table training), never as your starting design.
   - Your first design section must set out your OWN architecture options (at least 2–3 genuinely different ones), chosen with your partners, before you measure anything design-specific.
3. **To SA19P and SA19Q, guard:** the group designs FROM SCRATCH; SA19 must not duplicate, extend or repair an earlier designer's design; earlier designs are evidence only. Part of your role is to guard this: challenge any step that starts from CPV-1, CPP-LL or another earlier design, and push genuinely different architectures.
4. **To all three, owner clarification:**
   - You MAY be inspired by earlier designers' choices and pick and choose individual elements from any of them, provided each earns its place in YOUR architecture.
   - What is forbidden is taking an existing design as the base to continue from.
   - For each adopted element, write one line in DESIGN.md: where it came from and why it fits.
   - Thinkers: guard against continuation, not against borrowing.
5. **To SA19, runaway jobs:** the SA18 runner scripts and their children were killed (coordinator error); the CPU is yours again.
6. **To SA19, metrics (owner reminder, binding):**
   - Every quality result and every design decision is judged on VMAF-NEG first (mean and worst frame), then PSNR Y/Cb/Cr side by side. Chroma is never optional.
   - S1 is an energy PROXY: its chroma gain (L1 .93–.995) is much smaller than luma's, so the E1 A0-vs-A1 12-point eval decides. Report it NEG first, then Y/Cb/Cr, per cell and rate, with the owner's artifact tools per plane.
   - Run a static control and a monotone weight sweep so that a blurrier prediction cannot pass as a gain (the bits-only oracle trap).
7. **Owner correction (in the brief):** the "immediate progress" rule applied one time only, to the SA18 group. The standing rule: a group is shut down when it has CLEARLY stalled.
8. **Owner rulings on high-motion levers (2026-09-29, 21:30):**
   - The per-slice rate split is REJECTED: it starves other strips and causes flatness.
   - The per-block t-1/t-2 reference choice is REJECTED, for compute, latency and library-like use of old frames.
   - Any other t-2 use must answer the owner's concerns in writing: worst-case compute against the ZU7EV budget, DDR traffic and jitter, and latency against the 9 µs margin at 720p50 with 3:1 conversion. If they can't be answered, drop it.
   - Coarse-first current-frame vectors remain allowed, subject to a latency proof.
9. **Coordinator on the levers (S5.399):**
   - Band rebalance is gated on smudge and cast, per plane.
   - Fresh vectors must be measured at exact CBR, with the S5.152 contradiction replicated.
   - Cross-frame context is low priority (loss and 8K memory).
