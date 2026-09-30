#!/bin/bash
# build_bundle.sh — packs DESIGN.md + everything needed to reproduce it into SA20_bundle.zip (in SA20_design/).
cd "$(dirname "$0")/.."; R=/home/user/fromscratch
cp out/q_*.sh queues/ 2>/dev/null
( cd $R && git log --reverse --format='%h %ad %s' --date=format:'%H:%M' -- OMC_CLOUD/Project/Subagents/SA20_design ) > history/commits.txt
( cd $R && git log --reverse -p --format='=== commit %h %ad %s' --date=format:'%H:%M' -- OMC_CLOUD/Project/Subagents/SA20_design/bench \
    OMC_CLOUD/Project/Subagents/SA20_design/tools OMC_CLOUD/Project/Subagents/SA20_design/out/*.sh OMC_CLOUD/footage_in/conv.sh OMC_CLOUD/scratch/today/*.sh ) > history/bench_history.patch
rm -f SA20_bundle.zip
python3 - <<'PY'
import zipfile, os
z = zipfile.ZipFile('SA20_bundle.zip', 'w', zipfile.ZIP_DEFLATED)
for f in ['DESIGN.md', 'REPRODUCE.md']: z.write(f, 'SA20_design/' + f)
for d in ['bench', 'tools', 'queues', 'history']:
    for root, _, files in os.walk(d):
        if '__pycache__' in root: continue
        for f in files: z.write(os.path.join(root, f), 'SA20_design/' + os.path.join(root, f))
for f in sorted(os.listdir('t1')):   # T1/T2 sources only; the .so and table caches are rebuilt (REPRODUCE.md)
    if f.endswith(('.c', '.py')): z.write(os.path.join('t1', f), 'SA20_design/t1/' + f)
z.close(); print('SA20_bundle.zip', os.path.getsize('SA20_bundle.zip'), 'bytes', len(zipfile.ZipFile('SA20_bundle.zip').namelist()), 'files')
PY
