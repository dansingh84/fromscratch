"""Deterministic latency model for OMC-1 (A2) - generates the docs/LATENCY.md table.

Model (algorithmic buffering; strictly causal, deterministic):
  T_total = T_capture + T_transmit + T_overdraft
    T_capture   = slice_h lines of source capture   = slice_h / (fps * lines)
    T_transmit  = one slice at the provisioned link = frame_time / nslices
    T_overdraft = banking prefix bound              = OD_CAP * frame_time / nslices
  (Pipelined transform/entropy hardware adds line-level, not slice-level, delay:
   a few source lines; it is inside T_capture's next-slice overlap and bounded
   by 2 lines - included below as T_pipe for honesty.)

Encoder never emits slice k later than uniform schedule; decoder can begin
reconstruction of slice k the moment its (<= 1.5 B) bytes have arrived, and the
banking prefix invariant (spent(k) <= (k+1)B + B/2) guarantees arrival by
uniform time + 0.5 slice periods. Every slice is intra and self-contained, so
the bound is exact and constant frame-to-frame (genlock-safe): latency never
depends on content.
"""

FORMATS = [
    # name, width, height, fps, slice_h
    ("720p50", 1280, 720, 50.0, 8),
    ("720p59.94", 1280, 720, 59.94, 8),
    ("720p60", 1280, 720, 60.0, 8),
    ("1080p50", 1920, 1080, 50.0, 8),
    ("1080p59.94", 1920, 1080, 59.94, 8),
    ("1080p60", 1920, 1080, 60.0, 8),
    ("2160p50", 3840, 2160, 50.0, 16),
    ("2160p60", 3840, 2160, 60.0, 16),
    ("2160p100", 3840, 2160, 100.0, 16),
    ("2160p120", 3840, 2160, 120.0, 16),
    ("4320p60 (8K)", 7680, 4320, 60.0, 16),
]

OD_CAP = 0.5  # banking overdraft, fraction of one slice period
PIPE_LINES = 2  # transform/entropy pipeline depth in source lines


def rows():
    out = []
    for name, w, h, fps, sh in FORMATS:
        frame_ms = 1000.0 / fps
        line_ms = frame_ms / h
        nslices = h // sh
        t_cap = sh * line_ms
        t_tx = frame_ms / nslices
        t_od = OD_CAP * t_tx
        t_pipe = PIPE_LINES * line_ms
        total = t_cap + t_tx + t_od + t_pipe
        out.append((name, w, h, fps, sh, nslices, t_cap, t_tx, t_od, t_pipe, total))
    return out


def markdown():
    lines = [
        "| Format | Slice h | Slices | Capture | Transmit | Overdraft | Pipeline | **Total** |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for (name, w, h, fps, sh, ns, tc, tt, to, tp, tot) in rows():
        lines.append(
            f"| {name} | {sh} | {ns} | {tc:.3f} ms | {tt:.3f} ms | {to:.3f} ms |"
            f" {tp:.3f} ms | **{tot:.3f} ms** |")
    return "\n".join(lines)


if __name__ == "__main__":
    print(markdown())
    bad = [r for r in rows() if r[-1] >= 1.0]
    print("\nAll formats < 1 ms:", "YES" if not bad else f"NO: {bad}")
