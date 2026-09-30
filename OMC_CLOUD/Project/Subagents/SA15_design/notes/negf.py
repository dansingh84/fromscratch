# per-frame VMAF-NEG, same model/convention as shared_tools/vmafneg.sh (pooled mean printed for cross-check)
import subprocess, json, sys, tempfile, os
def negframes(ref,dist,W,H,N,pixfmt='yuv422p10le'):
    fd,log=tempfile.mkstemp(suffix='.json'); os.close(fd)
    cmd=['ffmpeg','-v','error','-f','rawvideo','-pix_fmt',pixfmt,'-s',f'{W}x{H}','-i',dist,'-f','rawvideo','-pix_fmt',pixfmt,
         '-s',f'{W}x{H}','-i',ref,'-frames:v',str(N),'-lavfi',
         f'[0:v]trim=end_frame={N}[d];[1:v]trim=end_frame={N}[r];[d][r]libvmaf=model=path=/home/user/fromscratch/OMC_CLOUD/vmaf_model/vmaf_v0.6.1neg.json:n_threads=4:log_fmt=json:log_path={log}',
         '-f','null','-']
    r=subprocess.run(cmd,capture_output=True,text=True)
    if r.returncode!=0: raise SystemExit('vmaf failed '+r.stderr[-500:])
    j=json.load(open(log)); os.remove(log)
    return [f['metrics']['vmaf'] for f in j['frames']], j['pooled_metrics']['vmaf']['mean']
if __name__=='__main__':
    fr,m=negframes(*sys.argv[1:3],int(sys.argv[3]),int(sys.argv[4]),int(sys.argv[5]),*(sys.argv[6:7]))
    print('mean %.3f min %.3f'%(m,min(fr)),' '.join('%.2f'%x for x in fr))
