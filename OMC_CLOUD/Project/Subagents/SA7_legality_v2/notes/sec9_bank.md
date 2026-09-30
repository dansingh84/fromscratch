## §9.3 (b) The shipped bank and cap, stated exactly from the code

`src/codec.c:5986–6001`, per slice, before the rate ladder:

```c
int64_t B = (int64_t)c->cfg.bits_per_slice;          /* the slice's nominal share */
int64_t F = B * c->nslices;                          /* the frame's total          */
int64_t min_slice = (OMC_SLICE_HDR_BYTES + 32) * 8;  /* 608 bits: header + 32 B     */
int64_t avail_prefix = (int64_t)slice_idx * B + B - e->spent_bits;
int64_t reserve      = (int64_t)(c->nslices - 1 - slice_idx) * min_slice;
int64_t avail_frame  = F - e->spent_bits - reserve;
int64_t budget_wire  = min(avail_prefix, avail_frame);
if (budget_wire < min_slice) budget_wire = min_slice;
int64_t wire_cap = (int64_t)c->slice_bytes * 2 * 8;  /* NORMATIVE 2x cap            */
if (budget_wire > wire_cap) budget_wire = wire_cap;
int64_t budget = budget_wire - OMC_SLICE_HDR_BYTES * 8;   /* payload bits           */
```

| parameter | value | meaning |
|---|---|---|
| **what a slice may borrow** | `avail_prefix = (slice_idx+1)·B − spent_bits` | everything the causal prefix has not yet spent — the bank is the unspent surplus of slices 0…k−1 of the **same frame** |
| **the hard cap** | `wire_cap = 2 × slice_bytes` on the wire, **normative** (the decoder's read window and the encoder's payload scratch are sized to it, BITSTREAM §5) | a slice may draw **at most one further slice_bytes**, i.e. **+100 %**, however much is banked |
| **the floor every later slice keeps** | `min_slice = 608 bits` each | the reserve; a residue slice can never starve a neighbour below the header + 32 bytes |
| **the CBR window** | the **frame**: every stream is exactly `32 + nslices × slice_bytes × nframes` | the bank never crosses a frame boundary (`if (slice_idx == 0) e->spent_bits = 0;`, `src/codec.c:5902`) |
| **overdraft** | none (`/* no banking overdraft */`, `src/codec.c:5987`) | a slice cannot spend what the prefix has not banked |

So the question (b) asks is exactly answerable: **can the residue slices' escape bits fit inside
`min(banked surplus, slice_bytes·8)` without pushing any later slice below `min_slice`?** The
second term is the one that binds in the worst case, and it is generous: **at 1080p @0.5 bpp a
slice may draw up to 15,360 further payload bits.**
