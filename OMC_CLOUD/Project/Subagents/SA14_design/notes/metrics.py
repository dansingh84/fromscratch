"""Per-frame VMAF-NEG (vmaf_v0.6.1neg, luma by construction) and per-plane PSNR for frames a..b-1."""
import subprocess, json, numpy as np, os, tempfile
def frames(path, W, H, fmt, a, b):
    cw = W // 2 if fmt in ('422', '420') else W; ch = H // 2 if fmt == '420' else H
    fw = W * H + 2 * cw * ch
    d = np.fromfile(path, dtype='<u2', count=fw * b)[fw * a:]
    return d.reshape(b - a, fw), (W * H, cw * ch)
def neg_per_frame(ref, dec, W, H, fmt, a, b, scr):
    pix = {'422': 'yuv422p10le', '444': 'yuv444p10le', '420': 'yuv420p10le'}[fmt]
    r, _ = frames(ref, W, H, fmt, a, b); d, _ = frames(dec, W, H, fmt, a, b)
    rp = os.path.join(scr, 'm_r.yuv'); dp = os.path.join(scr, 'm_d.yuv')
    r.astype('<u2').tofile(rp); d.astype('<u2').tofile(dp); n = b - a
    cmd = ['ffmpeg', '-v', 'error', '-f', 'rawvideo', '-pix_fmt', pix, '-s', f'{W}x{H}', '-i', dp, '-f', 'rawvideo', '-pix_fmt', pix,
           '-s', f'{W}x{H}', '-i', rp, '-frames:v', str(n), '-lavfi',
           f'[0:v]trim=end_frame={n}[d];[1:v]trim=end_frame={n}[r];[d][r]libvmaf=model=path=/home/user/fromscratch/OMC_CLOUD/vmaf_model/vmaf_v0.6.1neg.json:n_threads=4:log_fmt=json:log_path=/dev/stdout',
           '-f', 'null', '-']
    out = subprocess.run(cmd, capture_output=True, text=True).stdout
    j = json.loads(out); os.remove(rp); os.remove(dp)
    return [f['metrics']['vmaf'] for f in j['frames']]
def psnr_per_frame(ref, dec, W, H, fmt, a, b, maxv=1023):
    r, (ny, nc) = frames(ref, W, H, fmt, a, b); d, _ = frames(dec, W, H, fmt, a, b)
    out = []
    for i in range(b - a):
        rr = r[i].astype(float); dd = d[i].astype(float); sl = [(0, ny), (ny, ny + nc), (ny + nc, ny + 2 * nc)]
        out.append([99.0 if np.mean((rr[x:y] - dd[x:y]) ** 2) == 0 else 10 * np.log10(maxv ** 2 / np.mean((rr[x:y] - dd[x:y]) ** 2)) for x, y in sl])
    return np.array(out)
def summary(ref, dec, W, H, fmt, scr, a=2, b=12):
    n = neg_per_frame(ref, dec, W, H, fmt, a, b, scr); p = psnr_per_frame(ref, dec, W, H, fmt, a, b)
    return {'neg_mean': float(np.mean(n)), 'neg_worst': float(np.min(n)), 'psnr_mean': p.mean(0).tolist(), 'psnr_worst': p.min(0).tolist()}
