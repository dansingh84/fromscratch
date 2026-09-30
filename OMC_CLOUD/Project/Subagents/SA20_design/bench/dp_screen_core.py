import numpy as np
def motion(src, ref, B=16, R=8, Z=0.0):
    # Z > 0: encoder prefers the zero vector unless the best one beats it by more than Z codes per sample (mean |d|)
    Hh, Ww = src.shape; V = np.zeros((Hh // B + 1, Ww // B + 1, 2), int); P = np.zeros_like(ref)
    pad = np.pad(ref, R, mode='edge')
    for by in range(0, Hh, B):
        for bx in range(0, Ww, B):
            blk = src[by:by + B, bx:bx + B]; best = None
            for dy in range(-R, R + 1, 2):
                for dx in range(-R, R + 1, 2):
                    c = pad[by + R + dy:by + R + dy + blk.shape[0], bx + R + dx:bx + R + dx + blk.shape[1]]
                    sad = np.abs(blk - c).sum()
                    if best is None or sad < best[0]: best = (sad, dy, dx)
            _, dy0, dx0 = best
            for dy in (dy0 - 1, dy0, dy0 + 1):
                for dx in (dx0 - 1, dx0, dx0 + 1):
                    if abs(dy) > R or abs(dx) > R: continue
                    c = pad[by + R + dy:by + R + dy + blk.shape[0], bx + R + dx:bx + R + dx + blk.shape[1]]
                    sad = np.abs(blk - c).sum()
                    if sad < best[0]: best = (sad, dy, dx)
            if Z > 0:
                s0 = np.abs(blk - pad[by + R:by + R + blk.shape[0], bx + R:bx + R + blk.shape[1]]).sum()
                if s0 <= best[0] + Z * blk.size: best = (s0, 0, 0)
            V[by // B, bx // B] = best[1:]
    return V
def apply(ref, V, B, sx):
    Hh, Ww = ref.shape; R = 8; pad = np.pad(ref, R, mode='edge'); P = np.zeros_like(ref); Bx = B // sx
    for i in range(V.shape[0]):
        for j in range(V.shape[1]):
            by, bx = i * B, j * Bx
            if by >= Hh or bx >= Ww: continue
            dy, dx = V[i, j]; dx = int(np.round(dx / sx))
            h = min(B, Hh - by); w = min(Bx, Ww - bx)
            P[by:by + h, bx:bx + w] = pad[by + R + dy:by + R + dy + h, bx + R + dx:bx + R + dx + w]
    return P

