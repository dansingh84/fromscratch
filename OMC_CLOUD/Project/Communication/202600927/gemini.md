## 1. Canonical Decisions and Rate Control

The core requirement of a baseband hop is that only the image crosses, with no metadata or side channels. Because of this, the second encoder must deterministically arrive at the exact same plan (profile, Q-step per band, and refinement steps) using only the decoded, spatially clipped baseband pixels. 

- The current architecture fundamentally violates this by having the first encoder choose its plan based on the original source. 

- This forces the subsequent encoder to run a costly "lock" search to guess the first encoder's state. 

- To make decisions canonical without incurring a bit or quality cost, the rate-control algorithm must be mathematically idempotent. 

- The first encoder must execute a bounded analysis-by-synthesis loop: it selects a plan, performs the inverse transform and spatial clip, and feeds that clipped baseband reconstruction back into its own rate-control logic. 

- If the rate control selects a different plan for the reconstructed pixels, the first encoder must adjust its transmitted plan to match the stable state, guaranteeing the next generation will natively calculate the exact same parameters.

## 2. Achieving Legality Without Destroying Information

Applying a spatial clip after an inverse wavelet transform is mathematically destructive because the transform spreads the non-linear clipping operation across multiple coefficients. This pushes coefficients off the dead-zone scalar quantizer lattice. 

- Attempts to fix this in the coefficient domain via index capping severely degraded quality (costing 0.8–21 dB) because correcting one sample breaks its neighbors. 

- Legality must instead be enforced directly within the transform stage.

- Because the architecture relies on an exactly invertible integer lifting wavelet (5/3 and 9/7-like), non-linear bounding can be integrated directly into the lifting steps. 

- By applying clipping to the intermediate spatial representations during the update and predict steps of the lifting scheme, the transform becomes non-linear but remains perfectly invertible.

- This mathematically guarantees that the final synthesis will never exceed the legal range (e.g., 10-bit 4 … 1019), eliminating the need for a post-transform clip and completely preserving the generation 2+ exactness lock. 

## 3. Worst-Case Work per Slice

To maintain a deterministic latency of strictly under 1 ms and fit comfortably on a Zynq UltraScale+ FPGA without parallel hardware, all iterative searches must be eliminated. 

- The current lock requires about 50 entropy-pass equivalents. 

- Recovery attempts on rail edges required up to 190,000 slice-inverse equivalents. 

- By enforcing legality within the lifting steps and ensuring the first encoder canonicalizes the plan via an analysis-by-synthesis check, the architecture becomes strictly feed-forward at generation 2.

- The worst-case work for any subsequent encoder becomes exactly one pass: it receives the legal baseband pixels, performs the forward transform, natively calculates the canonical plan, and applies static tANS encoding. This perfectly aligns with the standard set by JPEG XS. 

## 4. Architectural Flaws and Missteps

The design went astray in two specific areas: the order of decisions regarding legality, and the fragility of the rate-control structure.

- **Order of Decisions:** The primary failure was relying on a decoder-side spatial clip to enforce legal picture ranges. By allowing the inverse transform to overshoot and relying on a destructive post-clip, the design mathematically guaranteed that the second encoder would receive perturbed data, destroying the exactness of the coefficient lattice. 

- **Rate-Control Fragility:** The use of a causal bank that allows unspent bits to flow to later slices (capped at 2× a slice's budget) creates a cascading dependency. When combined with a 9/16 dead-zone quantizer—which is inherently sensitive to small perturbations—a single clipped pixel in one slice alters the bit budget for subsequent slices in the next generation. This coupling makes canonical plan reproduction mathematically impossible without the unbounded searches the team has already measured and ruled out. 

