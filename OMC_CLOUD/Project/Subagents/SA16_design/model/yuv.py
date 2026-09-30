import numpy as np
ARMS = '/home/user/fromscratch/OMC_CLOUD/Project/.work/arms/'
CELLS = {'dng720': (ARMS + 'dng_1280x720_422_10.yuv', 1280, 720),
         'dng1080': (ARMS + 'dng_1920x1080_422_10.yuv', 1920, 1080),
         'spot': (ARMS + 'long/spotrobotL_1920x1080_422_10.yuv', 1920, 1080),
         'floor': (ARMS + 'long/floorballgameL_1920x1080_422_10.yuv', 1920, 1080),
         'hwy': (ARMS + 'long/highwaydriveL_1920x1080_422_10.yuv', 1920, 1080),
         'volley': (ARMS + 'long/volleyballgameL_1920x1080_422_10.yuv', 1920, 1080),
         'gfx': (ARMS + 'cf_gfx_448x256_422_10.yuv', 448, 256)}
TRAIN = [ARMS + 'bosphorus_1920x1080_422_10.yuv', ARMS + 'cityalley_1920x1080_422_10.yuv',
         ARMS + 'readysetgo_1920x1080_422_10.yuv', ARMS + 'long/trafficlightsL_1920x1080_422_10.yuv',
         ARMS + 'long/winterdriveL_1920x1080_422_10.yuv']
TODAY = {'dng720': '/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA7_legality_v2/out/DM/dng720_b%s_a0.d.yuv',
         'dng1080': '/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA7_legality_v2/out/DM/dng1080_b%s_a0.d.yuv',
         'spot': '/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA7_legality_v2/out/DM/spot_b%s_a0.d.yuv',
         'gfx': '/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA7_legality_v2/out/DM/gfx_b%s_a0.d.yuv',
         'floor': '/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA15_design/out/today/floor_b%s.d.yuv',
         'hwy': '/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA15_design/out/today/hwy_b%s.d.yuv',
         'volley': '/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA15_design/out/today/volley_b%s.d.yuv'}

def shapes(W, H, fmt):
    cw = W // 2 if fmt in (422, 420) else W; ch = H // 2 if fmt == 420 else H
    return [(H, W), (ch, cw), (ch, cw)]

def read_frame(path, W, H, f, fmt=422, depth=10):
    sh = shapes(W, H, fmt); n = sum(a * b for a, b in sh)
    dt = '<u2'
    a = np.fromfile(path, dtype=dt, count=n, offset=2 * n * f).astype(np.int64)
    if a.size < n: raise SystemExit('short read %s frame %d' % (path, f))
    out = []; o = 0
    for (h, w) in sh: out.append(a[o:o + h * w].reshape(h, w)); o += h * w
    return out

def write_frames(path, frames, depth=10):
    with open(path, 'wb') as fh:
        for fr in frames:
            for p in fr: fh.write(np.ascontiguousarray(p).astype('<u2').tobytes())

def nframes(path, W, H, fmt=422):
    import os
    return os.path.getsize(path) // (2 * sum(a * b for a, b in shapes(W, H, fmt)))
