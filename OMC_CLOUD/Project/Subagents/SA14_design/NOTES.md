# SA14 design notes (kept current)

## Path I am pursuing (2026-09-27)

Working name: **NEST** — escape-lifted, lattice-nested wavelet codec.

Neither of the two families already in use by other designers (Haar/S-transform pair pyramid with
predicted details; pixel-owned predict-only quincunx). I keep a **symmetric update step** (the
anti-aliasing that the records say is worth ~3 dB, S5.212/S5.353) and still get a decoder that is
legal by construction and acyclic. The idea that makes this possible:

1. **The update reads transmitted leaf values, never clamped values.** In synthesis,
   even = L − U(u), where u is the dequantised leaf (R(q), plus the band prediction in inter
   mode). u is known from the bitstream before any sample is computed, so the interval
   that makes each odd sample legal depends only on final values. No cycle, so no need for
   predict-only. (The records' cycle argument, S5.349/memo 011 §2.3, assumed the update
   reads the clamped value.)
2. **Every detail band is a leaf.** A separable 2-D transform makes the horizontal detail
   an intermediate value, which breaks (1). I use a non-separable one-level 2-D lifting:
   the three detail classes (eo, oe, oo) are predicted straight from final samples and coded
   as they are, and one update builds the low band. Applied recursively, then horizontal-only
   1-D levels at coarse scales.
3. **Legality by rail escapes, not clamps.** A detail sample whose output sits on its window
   boundary (on a rail at level 1) is coded as an ESCAPE symbol: output = boundary, update
   contribution = the band prediction (0 in intra). Windows for intermediate low-band samples
   are [lo+U, hi+U], computed top-down from the leaves before synthesis, so even samples
   are legal as well. A safety clamp keeps even non-conformant (lossy) streams legal.
4. **Exactness by reading, with nested lattices.** Reconstruction points sit on qΔ
   (power-of-two Δ, no offset; the dead zone still biases decisions toward zero). A decoded
   picture's non-escape leaves sit exactly on the transmitted lattice. The next encoder
   (a) recomputes the leaves exactly (the analysis is the exact inverse of the synthesis;
   escapes are recognised because they sit on the boundary), (b) reads, per band, the coarsest
   Δ and the cheapest consistent mode whose lattice contains them (OR plus count-trailing-zeros,
   one pass). This description decodes to the same picture, costs no more bits, and is a
   function of the picture alone. So E(D(s)) is canonical, and D(E(D(s))) = D(s) for every
   decoded picture. Generation 1 emits E(y1) of its own reconstruction; stream-identical
   from generation 2. Escapes do not depend on Δ, which is what made nested lattices fail before
   (S5.70: provenance is not needed, a canonical representative is enough).
5. **The encoder's only extra job** is the escape closure: a normal site that lands on or past its
   boundary must become an escape. This is monotone (sites only become escapes). A bounded
   one-pass version uses pessimistic neighbour margins. It is the design's main risk (worst-case
   bound on rails), to be measured.

Still open: the slice structure without seams (continuous vertical transform vs. vertical-causal),
temporal prediction and motion vectors taken canonically from decoded frames (t−1, t−2, rows
above), rolling refresh without a still-area pop, and entropy coding whose exact cost comes from
a lookup table.

## Experiments (small, numpy; scripts in notes/)
- E1: intra efficiency of the non-separable escape-lifting (NEST) analysis vs separable 5/3,
  per plane, entropy estimate, full frames.
- E2: legality and generation-2 exactness of the NEST decoder, closure and reading, on real
  frames plus rail content.

## Status (end of round 1, 2026-09-27): DESIGN.md delivered
- Point 2 above, as first written (a non-separable one-level lifting with a single update), LOST
  4–28 % BD-rate. It is replaced by an EXACT rewriting of the separable 5/3 in which all four bands
  are leaves (HL = dB + inner update from the HH leaves; LH likewise). Measured ±0.5 % versus the
  separable 5/3 on every plane (out/e1s.txt).
- Rail rule (final): a detail sample on its window bound is a RAIL symbol whose update value is
  the rail value (0 intra, band prediction inter). The encoder closure:
  - a lattice sample reaching its bound moves one index step inward;
  - index 0 on the bound becomes a RAIL.
  Measured ≤ 6 rounds. Exact and legal in 21 of 21 runs. Cost against the clip is 0 on
  dng/floor/gfx and −0.04…−0.16 VMAF-NEG on spot at low rate. On rails it is 55–63 % FEWER bits
  and +4…7 dB, which needs the rail sign in the entropy context.
- Slices: shifted causal slices. The first row is predicted from the slice above's final rows;
  the last row is a low row whose update from below is zero. No mirror, no blend, no lookahead.
  Row-phase profile ≈ the continuous transform's; −3…4 % bits versus mirrored slices
  (out/seam_test*.txt).
- Rejected: modular (wrap-around) lifting (black and white are neighbours on the circle, so
  graphics edges would need to be exact); rails carrying exact values (fixed-point oscillation);
  one-shot pessimistic closure; coarsest-first rounds.
- Weakest point: no proven small worst-case round bound for the encoder closure.

## Log
- 2026-09-27: constraints read in full; expert memos (start_here, vibe, gemini) read; ledger
  grepped (predict-only S5.212/S5.228, one-sided update S5.349, nested lattices S5.70, vertical
  causal S5.353–S5.358, SA12/SA13 paths S5.355/S5.359).

## Round 2 (2026-09-27, after the coordinator's review): DESIGN_v2.md
- Closure replaced by INJECTIVE DEQUANTISATION (IDQ). Beyond-window indices map one to one onto
  the window's off-lattice values; any index set is legal and exact, and the encoder is one pass.
  Exactness now comes from exact index recovery with canonical parameters (causal plan, modes read
  as the cheapest exact reading, vectors from decoded frames).
  Code: notes/nv3.py, notes/temporal3.py.
- Measured:
  - intra = clip within ±0.01 dB;
  - still input: 0 changed samples from frame 1;
  - generation 2 identical on moving dng720 and spot;
  - versus today (tilted plan): parity at 0.5 and 1.0 bpp by VMAF-NEG, every plane.
- Open:
  - slices + IDQ + temporal not yet run in one model;
  - first-row excess (+3…7 %) costs about 4 % bits to remove;
  - rates are estimated;
  - IDQ admissibility table.
