## §9.2b (a) Why the residue resists — measured, and it is a single cause

Three counters in the probe answer this directly, and they agree on every cell:

* **`nocover = 0` on every cell at every rate.** Every violating sample has at least one covering
  level-1 or level-2 coefficient with a non-zero synthesis response. **The residue is never a
  reach problem.**
* **`left1 > bad0` on the 0.5 bpp motion cells** — spotrobotL 7,625 violating samples before the
  pass and **8,082 after phase 1**; volleyballgameL 6,171 → 5,586 but 5,740 after the second pair.
  The pass **creates more violations than it removes** at the low rate. That is neighbour push-out,
  and nothing else can produce it: every move is inward for the sample that asked for it.
* **`deep2 ≫ deep0`** — spotrobotL's worst excursion goes **102 → 356 codes**, volleyballgameL's
  **119 → 390**. The pass does not merely fail to close; it deepens what it leaves.

The cause is the one this session measured three times: **a whole quantiser step of a level-1
coefficient is 32–512 codes at 0.5 bpp while the typical excursion is 7–27** (L-I19 §1). When
`round(need / step)` is zero the pass has no smaller move — it must either leave the sample out or
move a full step, and a full step overshoots the sample inward while carrying its 3–5 neighbours
the same distance the other way. **No arrangement of whole-step moves can be complete**, because
completeness is not a search property here, it is a granularity property. Organising the search
better (which is all the two-phase pass does relative to the shipped greedy) changes the cost, not
the reach: the shipped greedy reaches 92–99 % only by spending up to 512 moves and 741 full-plane
inverses undoing its own overshoot, which is exactly the cost the two-phase pass exists to remove.

The second phase is worth stating separately because it is a design answer, not a tuning one: at
0.5 bpp **`K = 2` is worse than `K = 1`** on the motion cells (spotrobotL 8,082 → 8,696), while at
1.0 bpp it helps (3,015 → 2,268). A second whole-step pass chases its own overshoot. If a
whole-step pass were to ship, `K = 1` would be the right cap at low rate — but the completeness
figure is 25–45 % either way.
