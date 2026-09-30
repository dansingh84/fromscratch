# Reply to Memo 010 — from the codec expert

**To:** Fable, OMC-1 coordinator
**Re:** how to build picture→numbers→legal picture so that every generation repeats, from first principles

I will answer your four questions, but everything follows from one idea, so I state it first.

---

## 0. The one idea

A codec that is stable over unlimited generations is a codec whose **decode output is a fixed point of the encode–decode map**:

> If `y = D(E(x))`, then we require `E(y) = E(x)` and `D(E(y)) = y`.

Every mechanism you have built — the lock, the repair engine, index capping, δ-recovery — is an attempt to *restore* this property after it was broken upstream. The right way is to build it so it is never broken:

1. **The encoder's reconstruction must be the decoder's output, bit for bit, including the legality step.** Whatever the decoder does last, the encoder does last too, and the encoder uses *that* picture — not a pre-clip reconstruction — as its reference for prediction, its input for rate-control statistics, and its test for plan re-decision. This is "closing the loop" in the strict sense: there is exactly one reconstruction pipeline, and encoder and decoder both run it.
2. **Every decision must be a computable function of the decoded picture alone.** Not "recoverable" by search — computable, deterministically, by the same procedure the next encoder will run.

If (1) and (2) hold, then at generation 2 the encoder sees a picture that is *already* a fixed point, and by induction it re-emits the identical stream forever. There is nothing to lock, nothing to repair, nothing to recover.

Your history in one sentence: you built a codec whose encoder decisions depend on pre-quantisation source data, discovered that generation 2 could not reproduce them, and then spent enormous fixed work trying to *rediscover* the decisions from the decoded picture. The decisions should instead be *made* from the decoded picture's data in the first place — then there is nothing to rediscover.

---

## 1. Which decisions must be canonical, and how to structure rate control

### 1.1 The canonical set

Everything the encoder decides, it must decide from data that generation 2 also possesses. Generation 2 possesses: the decoded picture `y`, the previous decoded frame (identical by induction), the frame counter, and the bit budget schedule. So the rule is:

- **Canonical (recomputed, never signalled as free choice):** quantisation plan (per band, per slice), prediction mode flags, rate-control state, legality handling, motion vectors (yours already are — keep this), intra-refresh schedule (frame-counter derived — keep), slice-boundary handling, entropy tables (already static — keep).
- **Free inputs (identical at every generation by construction):** the configuration, the CBR budget, the frame index.

One caution that I suspect is behind some of your failures: **canonical is not the same as "deterministic."** Your plan choice today is deterministic, but it is a function of the *source*, which generation 2 never sees. A function of unseen data is useless no matter how deterministic it is. The test for every decision is: *run this decision procedure twice, once at generation 1 on the reconstruction, once at generation 2 on `y` — the inputs must be equal objects.* That is the design discipline.

### 1.2 Rate control: feed-forward, decided on quantised data, one pass

Your current structure — "rate control tries plans until the slice fits its budget" — has two faults: unbounded work, and a decision input (source coefficients) that generation 2 lacks. Restructure as follows.

**Per-slice budget, feed-forward.** The slice's budget is computed from (a) the nominal per-slice budget derived from the config alone, plus (b) the causal bank: the *actual* bits spent by earlier slices of the same frame, with your 2× cap. Note the induction: at generation 2 the earlier slices of the same frame have already been encoded **byte-identically** (that is the whole point), so their actual bit counts are identical, so the bank state is identical, so the budget is identical. The bank becomes canonical for free. The same holds for the first frames: their budgets come from the config, so exactness on frame 0 is automatic. Add a deterministic, canonical stuffing rule to fill the slice to its exact budget (tANS flush plus a fixed filler pattern); it costs nothing and is reproducible.

**Plan choice by cost model, not by entropy passes.** Your entropy coder is *static* tANS. That means the exact bit cost of every symbol is known a priori and can be put in a lookup table: `bits[index, band]`. This is the property JPEG XS exploits — its rate allocation is a computation, not a search over encodes. Use it:

- Quantise once at the finest candidate step per band. Because your steps are powers of two and your dead zone is a fixed fraction (9/16) of the step, **the quantiser lattices nest**: the indices at every coarser candidate step are obtained from the fine indices by shifts and a constant add — no re-quantisation, no second pass.
- Sum the LUT costs of the candidate plans in the same pass that produces the indices. The plan is then a fixed deterministic threshold rule over these sums against the slice budget: cheapest candidate plan whose estimated cost fits, with a fixed tie-break.

**Worst case:** one transform pass + one quantise/estimate pass (fusable into one streaming pass) + one entropy-encode pass. The "try plans until it fits" loop disappears. This is the JPEG XS shape: *the decision is a table-lookup computation, made once per slice.*

**Where the plan choice's canonicality comes from — the critical subtlety.** At generation 1 you could compute the plan from the source; at generation 2 it must be computable from `y`. These can disagree near decision boundaries, because `y`'s coefficients lie *inside* cells, not at lattice points. So the rule must be: **the encoder computes the plan from its own reconstruction (the projected picture described below), not from the source.** Concretely, per slice (Section 2, stage E): quantise provisionally, reconstruct and legalise, then *recompute the plan from the reconstruction's coefficients* and check it equals the provisional plan. On all ordinary content it matches on the first try, at the cost of one comparison. When it does not match, there is a bounded ladder (Section 3.3). This is the one place where you pay a small, constant, worst-case-bounded amount of extra work to make canonicality *true by construction* rather than hoped-for — and it is exactly the work your 50-pass lock was trying to buy at 50× the price.

### 1.3 Prediction modes

The mode decision (intra vs inter, per band) must likewise be made by comparing costs computed from quantised, reconstruction-side data. At generation 2 the coefficients are cell-identical, so the costs are identical, so the mode bits are identical. Motion vectors you already derive from decoded frames — keep that exactly as it is; it is the one part of your design that is canonical in the strong sense.

---

## 2. The pipeline, stage by stage

### Stage A — Prediction
Motion-compensated prediction from the previous **projected** (legal, decoder-identical) decoded frame. MVs derived from decoded frames by a fixed rule, as today.

### Stage B — Transform and single quantisation
Forward lifting wavelet as today (5/3 reversible + your integer 9/7-like finest levels — this is fine, and integer lifting's exact invertibility is one of your genuine assets; do not abandon it). Quantise at the finest candidate step per band; derive all coarser candidate indices by shifts.

### Stage C — Plan, by computation
LUT cost sums over the nested indices; deterministic threshold rule against the feed-forward budget (Section 1.2).

### Stage D — Reconstruction *is* the decoder: legality by in-cell projection
Both encoder and decoder run, identically:

```
repeat K times (K fixed, e.g. K = 4; early-exit if a round changes nothing):
    clip samples to the legal range
    forward-transform the slice
    snap each coefficient back inside its transmitted quantisation cell
    inverse-transform
final clip (needed only if the last round changed nothing but samples were still out of range — see ladder)
```

Why this is the right mechanism:

- The set of coefficient vectors whose transmitted cells are respected is a **box** (product of cells). The set whose inverse transform is legal is the preimage of a box under a linear map — **convex**. Alternating projection between two convex sets converges to a point in their intersection whenever the intersection is non-empty. Your own measurement confirms this: with K = 4, *every* coefficient stayed inside its true cell. So the algorithm you already built in attempt 8 is the correct core. What is wrong is not the projection — it is what you demand of its output (next section).
- It costs **zero bits** (no signalling), and its quality equals the plain clip (your measurement).
- It runs on adds, shifts and compares per sample, K bounded — FPGA-trivial.
- Because the encoder uses this projected picture as its reconstruction, reference, and statistics source, **the information is never lost in the first place**, and there is nothing for the next encoder to recover.

### Stage E — Canonical re-decision and verification
From the projected reconstruction's coefficients, recompute the plan (and mode costs) exactly as generation 2 will. If they equal the provisional ones (the overwhelmingly common case), entropy-encode and you are done, with a *proof* — not a hope — that generation 2 reproduces the stream. If not, escalate (Section 3.3). This replaces your 50-pass lock with, in steady state, one comparison.

### Stage F — Entropy and stuffing
Static tANS, per band, exactly as today; deterministic flush and stuffing to the exact budget.

### What this does to the boundary blend
Delete it. It is a second mechanism patching the symptom of the first. The cross-slice lifting term should be a function of *previously decoded rows of the picture itself*, exactly invertible from the decoded image alone — then the boundary is handled once, in the transform, and it is canonical by construction (generation 2 recomputes the same lifting from the same decoded rows). A display-side blend that "the next encoder undoes exactly" is a hidden metadata channel across your baseband hop; it violates your own image-only rule in spirit and it is exactly the kind of fragile coupling that breaks generation-exactness in the field. If the 5/3 cross-slice term as implemented cannot be made seamless, the fallback is to make each slice's transform self-contained (start lifting state from a fixed initialisation at the slice top) and accept the one-row cost at the boundary — but a one-row, exactly-invertible cross-slice term is straightforward in lifting and is the better fix.

---

## 3. Legality on black/white rails — question 2 in full

Three layers, in order of application.

### 3.1 The dead zone does most of the work
Your 9/16 dead zone with power-of-two steps already zeroes ringing below the threshold. Your own numbers show sparse overshoot is 100–1,100 samples per frame, small, at edges, mostly from the two finest levels. Coarser or equal-step dead-zone treatment of the finest bands suppresses nearly all of the sparse case. Keep it — it is deterministic and costs nothing.

### 3.2 The projection handles the coupled case when a solution exists
On dense rail edges the violations are thousands to tens of thousands and strongly coupled — exactly the case where per-sample fixes (your index capping) are hopeless, because "a fix at one sample breaks its neighbour through the update step." The projection is the correct tool *because* it is coupled: it solves the whole slice at once, as a convex feasibility problem, and your K = 4 measurement says it succeeds on the graphics and 720p frames with zero residual samples.

### 3.3 Guaranteed termination: the escalation ladder
The projection is only guaranteed when the intersection (cell box ∩ legal preimage) is non-empty. When it is empty, no coefficient vector inside the transmitted cells decodes to a legal picture — **no mechanism can fix that at that step size**; the only honest options are to change the cells or to emit an illegal picture. So change the cells, deterministically:

- If after K rounds samples remain out of range, escalate the whole slice (or, better, only the bands contributing the excursion — the two finest levels, per your measurements) by **one power of two**, and re-run projection. Repeat up to a fixed ladder depth (a handful of rungs; you have few levels of step sizes anyway).
- Escalation enlarges every cell in the box, which monotonically enlarges the intersection, and the ladder is finite, so termination is unconditional. Worst case work is a constant, computable in advance, content-independent.
- The ladder is *not* signalled and need not be known at generation 2. Generation 2 sees a legal picture whose coefficients sit in the (coarse) cells of the plan that was actually transmitted; it recomputes the plan by the same threshold rule from the same reconstruction and reproduces the same coarse plan. The ladder is invisible across the hop by construction.

**Why this does not violate your "no bits, no quality" requirement:** the ladder triggers only where a legal decode at the finer step is *impossible* — content sitting exactly on black or white plates with dense edges. There, your own measurements (and everyone else's experience with rail content) show the excursion is ringing around flat plates; a coarser dead zone on the finest bands quantises that ringing to **zero**. The picture becomes *exactly the flat plate the source was*. That is not a visible artifact; it is the permitted outcome par excellence — regions already soft stay soft, and a rail stays a rail. On natural content the ladder never triggers and the bit cost is zero. On pathological content, the "cost" is bits spent where the alternative was an illegal picture, which your section 1 does not permit at any price. Also note the ladder replaces your repair engine's *unbounded* pass count with a bounded one — it is strictly better on the very content the repair engine was built for.

### 3.4 Two further hardening measures, both canonical

- **Fixed-point idempotence check:** at generation ≥ 2, the input picture is already legal and in-cell, so round 1 of the projection is the identity and the early-exit fires. This is the fixed-point property verified in silicon, every frame, for free. It also means the projection's cost at generation 2 is one round, not K.
- **On the residual "0.3–2.7 % of coefficients off their lattice points":** this is not a defect of the projection. It is a defect of your **lock**. See next section — this single change is the cheapest fix in your entire history.

### Why your attempt 8 "failed" when it had actually succeeded
Your K = 4 projection achieved: legality, zero bits, unchanged quality, and — by your own direct check — **every coefficient inside its transmitted cell**. Then you rejected it because 0.3–2.7 % of coefficients were "in-cell but not at the reconstruction point" and your lattice-point lock rejected them. But byte-identical re-encoding does not require lattice points. It requires exactly one thing:

> quantise(forward(y)) must return the transmitted indices.

A coefficient anywhere inside the correct cell quantises back to the same index. That is the definition of a cell. **Cell membership is sufficient; lattice-point membership is a strictly stronger, unnecessary demand.** Replace the lock's lattice test with an in-cell test (a sign check and a shift per coefficient — one cheap pass), and attempt 8 plus the plan-recomputation structure above solves generation 2 on natural content outright. Your measurements had already proved the theorem; your verification criterion was the only thing standing between you and it.

---

## 4. Worst-case work per slice — question 3

Steady state (all natural content, and every generation ≥ 2):

| Pass | Work |
|---|---|
| 1 | Forward transform + quantise at finest candidate steps + accumulate LUT costs (fused, streaming) |
| 2 | Plan threshold rule (a comparison on the accumulated sums — not a pass) |
| 3 | Inverse transform + projection, with early-exit (typically 1–2 rounds; gen ≥ 2: exactly 1, an identity) |
| 4 | Entropy encode |

That is the JPEG XS shape: **one decision per slice, one pass to decide it.** The projection rounds are constant-time, add/shift/compare work that the decoder runs anyway; K is fixed, early-exit is deterministic (a round that changes nothing ends the loop — idempotence, not a guess).

Worst case (pathological rail content, generation 1 only): add the escalation ladder — each rung costs one re-quantise-by-shift + one projection (2K passes) — with ladder depth a design constant (your number of power-of-two steps; call it 4–6). Total worst case is a small constant multiple of the steady-state work, known in advance, identical for every slice: no data-dependent unbounded loop anywhere. Set against your shipped lock at ~50 entropy passes **per slice, always**, this is cheaper even in its worst case, and it does the one thing the lock cannot: it makes generation 2 *exactly* reproduce generation 1 instead of approximately rediscovering it.

Hardware check against your constraints: all of it is adds, shifts, compares, table lookups; the cost LUTs are exactly your static tANS code lengths (known at design time); no multipliers; no adaptive arithmetic; the K-round projection is a fixed small unroll of existing transform hardware. Latency per slice is a constant number of pipeline passes over 16 rows; at 8K with your per-line throughput budget it stays comfortably inside a JPEG XS-comparable slice latency, and it is *constant by construction*, which your requirement actually demands and a retry-until-it-fits loop can never give you.

---

## 5. Where you went astray — question 4, plainly

1. **The clip was a decoder-only afterthought.** From day one, legality was handled at the *end of the decoder*, outside the encoder's reconstruction loop. That single ordering decision — reconstruction *then* clip — is the origin of every downstream disaster: the reference frames were wrong, the plan statistics were wrong, and the next encoder had lost information it needed. Legality must be *inside* the loop, and the encoder must live with the legal picture, not the ideal one. This is the architectural mistake; everything else is a consequence.

2. **The plan was chosen from the source, and then you built a machine to rediscover it.** The lock is 50 passes spent recovering a decision you could have made from data the next encoder also has. Invert the design: decide from the reconstruction. The lock should not exist; its job should be a one-comparison check inside the encoder, or nothing at all.

3. **The lock demands lattice points when cells suffice.** Your own K = 4 measurement proves in-cell holds; your verification then rejects a correct answer for not being a *more* correct answer. This is the single cheapest fix in the history: change one test, and attempt 8 works on natural content today.

4. **Rate control by trial encodes.** "Tries plans until the slice fits" is unbounded work and a non-canonical decision. With static entropy coding, plan selection should be arithmetic on LUT costs, one pass, JPEG XS-style. Power-of-two steps make every candidate cost available from one quantisation via shifts — you had the property and didn't use it.

5. **The boundary blend is a patch on a patch.** A cross-slice lifting term that is a function of decoded rows is exactly invertible and needs no display-side smoothing and no "undo" convention. Handling the boundary once, in the transform, removes both a potential visible seam and a fragile hidden contract across the hop.

6. **Attempts 1–3 (repair engine, index capping, δ-recovery) all search for information after destroying it.** The repair engine has unbounded passes; capping fights the transform's own update step (of course a per-sample fix breaks its neighbour — the transform is coupled, so the fix must be coupled); δ-recovery is a per-site search over a global coupling, which is why it explodes to 190,000 slice-inverses on rails and finds *several* valid δ — the problem was never well-posed. Close the loop and there is nothing lost, hence nothing to find.

7. **The embedded bit-plane variant (attempt 7) was abandoned for the wrong reasons.** Its 1–17 % bit cost came from static contexts and a fixed coding order — treatable — and its legality stall is the same cell-projection question you already solved in attempt 8. I do not recommend it over the design above (the plan-based path is cheaper and you have all its machinery), but the conclusion "no route meets all requirements" does not follow from that experiment. If you ever want a plan-free fallback, that is the direction; give it adaptive-to-static context modelling done *canonically* (state derived from decoded data only) and the same projection legality step.

---

## 6. What I would build, in one paragraph

Keep your transform, your static tANS, your MV derivation, your intra-refresh schedule, your integer lifting and slice size. Delete the display-side blend (make the cross-slice term a function of decoded rows, exactly invertible). Delete the lock, the repair engine, capping, and δ-recovery. Restructure rate control to a feed-forward budget (nominal + bank from actual prior-slice bits, capped) with plan selection by a one-pass LUT cost computation over nested power-of-two quantiser lattices, decided — and this is the essence — *from the reconstruction, not the source*. Make legality an in-cell projection (your attempt-8 mechanism, K fixed, early-exit) that the encoder runs as part of its own reconstruction, so references, statistics and plan re-decisions all live on the legal projected picture. Verify canonicality per slice with a re-decision comparison, and guarantee termination on rail content with a bounded escalation ladder that is invisible across hops. Replace the lattice lock with an in-cell test. The worst case per slice is a fixed small constant of slice passes; the steady state is one decision per slice, like JPEG XS; the bit cost of exactness and legality is zero on all content where they are achievable at all — and where they are not achievable (dense rails), no codec at any bit cost can achieve them, and the ladder spends its bits buying the one thing you refuse to trade: a legal picture that repeats forever.

## 7. What to verify first (in order)

1. Change the lock's lattice test to an in-cell test and re-run your attempt-8 corpus. I expect generation-2 byte-exactness on natural content immediately — this is hours of work, not weeks.
2. Wire the encoder's reference frames and plan statistics to the projected reconstruction; re-measure quality (should be identical to plain clip, per your own data) and generation stability.
3. Implement the LUT cost plan selection and measure the fit accuracy of the estimate against actual entropy output on your corpus; tune the deterministic threshold rule.
4. Implement the ladder and run the dense synthetic rail corpus; verify termination depth, generation-2 byte-exactness through the escalated plans, and — with the owner's eye — that escalated rail slices show flat rails, not artifacts.
5. Stress the canonicality at the boundaries: scene cuts, first frames, forced-intra slices, bank-saturated frames — the cases where generation 1 has no prior identical history to lean on. The feed-forward budget structure is designed to make these exact by construction; verify it is.

One request in return: when you measure, measure generation-3 and generation-10, not just generation-2. Generation-2 exactness plus the fixed-point property gives all generations, but the property deserves to be seen in the raw byte counts, at both hop types, before anyone believes it.

— the codec expert