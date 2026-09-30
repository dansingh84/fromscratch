import sys, subprocess, os, shlex
# run a list of jobs (tag, args, tables) with at most P in parallel; each job writes out/r2/log/<tag>.txt
jobs=[l.split('|') for l in open(sys.argv[1]).read().strip().splitlines()]
P=int(sys.argv[2]); procs=[]
for tag,args,tab in jobs:
    while len([p for p in procs if p.poll() is None])>=P:
        import time; time.sleep(20)
    log=open(f'../out/r2/log/{tag.strip()}.txt','w')
    env=dict(os.environ,TABLES=tab.strip())
    a=shlex.split(args.strip()); script='run2.py'
    if a[0].endswith('.py'): script=a[0]; a=a[1:]
    for kv in [x for x in a if x.startswith('ENV:')]: k,v=kv[4:].split('=',1); env[k]=v
    a=[x for x in a if not x.startswith('ENV:')]
    procs.append(subprocess.Popen(['nice','-n','19','python3',script]+a,stdout=log,stderr=subprocess.STDOUT,env=env))
for p in procs: p.wait()
