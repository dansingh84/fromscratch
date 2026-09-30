#!/usr/bin/env python3
"""[A5-LATCHECK] Adversarial check of harness/lat_model.py: every cell must
equal what the CODEC's own omc_config_latency() returns, as reported by
tree/latprobe.  A model that agrees with the codec on three cells and drifts on
the rest is exactly the failure mode this file exists to catch."""
import re, subprocess, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lat_model as M

probe = subprocess.run([os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                     '..', 'tree', 'latprobe')],
                       capture_output=True, text=True).stdout
bad = 0; n = 0
for line in probe.splitlines():
    m = re.match(r'LAT r=(\d) (\S+)\s+(\d+)\s+(\d+)\s+([\d.]+) sh=\s*(\d+) '
                 r'nsl=\s*(\d+).*total=\s*([\d.]+)', line)
    if not m: continue
    r, name, w, ch, fps, sh, nsl, tot = (int(m.group(1)), m.group(2), int(m.group(3)),
                                         int(m.group(4)), float(m.group(5)),
                                         int(m.group(6)), int(m.group(7)),
                                         float(m.group(8)))
    fmt = [f for f in M.FORMATS if f[0] == name]
    if not fmt: continue
    _, fw, fh, num, den = fmt[0]
    t = M.terms(fw, fh, num, den, uc_ratio=r)
    n += 1
    ok = (abs(t['total'] - tot) < 5e-4 and t['sh'] == sh and t['nsl'] == nsl
          and t['ch'] == ch)
    if not ok:
        bad += 1
        print("MISMATCH %s r=%d: probe sh=%d nsl=%d ch=%d total=%.4f | "
              "model sh=%d nsl=%d ch=%d total=%.4f"
              % (name, r, sh, nsl, ch, tot, t['sh'], t['nsl'], t['ch'], t['total']))
print("LATCHECK %d cells compared, %d mismatches -> %s"
      % (n, bad, "PASS" if bad == 0 else "FAIL"))
sys.exit(1 if bad else 0)
