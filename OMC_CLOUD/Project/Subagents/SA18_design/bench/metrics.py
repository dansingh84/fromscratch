# SA17 metrics: VMAF-NEG (same ffmpeg/libvmaf model as shared_tools/vmafneg.sh) with per-frame values,
# PSNR per plane. Steady-state frames only (2..N-1) unless told otherwise.
import numpy as np, subprocess, json, os, tempfile, yuv

SCR = os.environ.get('SA17_TMP', '/tmp/claude-1000/-home-dan-Documents-Apps-Codec/349df860-b2b7-4717-bcf8-5bdc1c07368a/scratchpad')

def neg_frames(ref_frames, dist_frames, W, H):
    os.makedirs(SCR, exist_ok=True)
    fr = tempfile.NamedTemporaryFile(dir=SCR, suffix='.yuv', delete=False).name
    fd = tempfile.NamedTemporaryFile(dir=SCR, suffix='.yuv', delete=False).name
    try:
        yuv.write_frames(fr, ref_frames); yuv.write_frames(fd, dist_frames)
        N = len(ref_frames)
        cmd = ['ffmpeg', '-v', 'error', '-f', 'rawvideo', '-pix_fmt', 'yuv422p10le', '-s', '%dx%d' % (W, H), '-i', fd,
               '-f', 'rawvideo', '-pix_fmt', 'yuv422p10le', '-s', '%dx%d' % (W, H), '-i', fr, '-frames:v', str(N),
               '-lavfi', '[0:v]trim=end_frame=%d[d];[1:v]trim=end_frame=%d[r];[d][r]libvmaf=model=path=/home/user/fromscratch/OMC_CLOUD/vmaf_model/vmaf_v0.6.1neg.json:n_threads=4:log_fmt=json:log_path=/dev/stdout' % (N, N),
               '-f', 'null', '-']
        o = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
        j = json.loads(o)
        v = np.array([f['metrics']['vmaf'] for f in j['frames']])
        return v
    finally:
        os.unlink(fr); os.unlink(fd)

def summary(src, dec, W, H, first=2):
    s = src[first:]; d = dec[first:]
    v = neg_frames(s, d, W, H)
    ps = [np.mean([yuv.psnr(a[i], b[i]) for a, b in zip(s, d)]) for i in range(3)]
    return dict(neg=float(v.mean()), negmin=float(v.min()), psnr=ps, negf=v)
