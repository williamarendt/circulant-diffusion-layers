from pathlib import Path
from itertools import combinations
from math import gcd
import argparse, hashlib, json, platform, subprocess, sys, time, os
BASE=Path(__file__).resolve().parent
sys.path.insert(0,str(BASE/'src'))
from binary_helpers import canonical, rows_for, exact_branch, verify
HERE=BASE
EXECUTABLE=None

def full_rank(rows,n):
    a=list(rows)
    for j in range(n):
        k=next((k for k in range(j,n) if (a[k]>>j)&1),None)
        if k is None:return False
        a[k],a[j]=a[j],a[k]
        for k in range(j+1,n):
            if (a[k]>>j)&1:a[k]^=a[j]
    return True

def enumerate_case(n,w,b):
    t=time.perf_counter()
    normalized=[(0,)+tail for tail in combinations(range(1,n),w-1)]
    reps=sorted({canonical(d,n) for d in normalized})
    legal=[]
    for d in reps:
        rows=rows_for(d,n)
        if n<=16:
            branch=exact_branch(rows,n)
            if branch!=b:continue
            assert full_rank(rows,n)
        else:
            assert w==3 and b==4
            if not full_rank(rows,n):continue
            branch=4 # invertible binary circulant of weight three: proved in paper
        g=n
        for j in d:g=gcd(g,j)
        legal.append(dict(n=n,weight=w,branch=branch,support=d,connected=g==1,rows=rows))
    info=dict(n=n,weight=w,branch_required=b,normalized_supports=len(normalized),
        affine_classes=len(reps),legal_classes=len(legal),connected_legal_classes=sum(c['connected'] for c in legal),
        enumeration_seconds=time.perf_counter()-t,
        property_check='exhaustive nonzero inputs + independent Gaussian rank' if n<=16 else 'Gaussian rank + proved weight-three branch-four theorem')
    return legal,info

def main():
    global HERE, EXECUTABLE
    ap=argparse.ArgumentParser()
    ap.add_argument('--cases',required=True,help='n:weight:branch comma separated')
    ap.add_argument('--seeds',type=int,required=True)
    ap.add_argument('--timeout',type=float,default=60)
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--executable',type=Path,default=BASE/'src'/('bp_small.exe' if os.name=='nt' else 'bp_small'))
    args=ap.parse_args()
    HERE=args.out.resolve();HERE.mkdir(parents=True,exist_ok=False)
    EXECUTABLE=args.executable.resolve()
    cases=[tuple(map(int,s.split(':'))) for s in args.cases.split(',')]
    metadata=dict(platform=platform.platform(),python=platform.python_version(),
        compiler=subprocess.check_output(['g++','--version'],text=True).splitlines()[0],
        source_sha256=hashlib.sha256((BASE/'src/bp_small.cpp').read_bytes()).hexdigest(),
        executable_sha256=hashlib.sha256((EXECUTABLE).read_bytes()).hexdigest(),
        seeds=list(range(args.seeds)),timeout_seconds=args.timeout,cases=cases,
        depth_caps='post-filtered unrestricted outputs, NOT constrained optimization',
        baseline='one deterministic BP construction per representative',
        random_protocol='one complete construction per seed for each RNBP/A1/A2',
        labeling='one canonical affine representative per class; heuristic may depend on labeling')
    (HERE/'circuits').mkdir(exist_ok=True)
    protocol_name='protocol_'+'_'.join(f'n{n}w{w}' for n,w,b in cases)+f'_s{args.seeds}.json'
    (HERE/protocol_name).write_text(json.dumps(metadata,indent=2))
    for n,w,b in cases:
        case=HERE/f'n{n}_w{w}';case.mkdir(exist_ok=True)
        (case/'protocol.json').write_text(json.dumps(metadata,indent=2))
        cp=case/'candidates.json'
        if cp.exists():
            saved=json.loads(cp.read_text());cs=saved['candidates'];info=saved['counts']
        else:
            cs,info=enumerate_case(n,w,b)
            cp.write_text(json.dumps(dict(counts=info,candidates=cs),indent=2))
        print('ENUM '+json.dumps(info),flush=True)
        rp=case/'trials.jsonl'
        rr=[json.loads(s) for s in rp.read_text().splitlines()] if rp.exists() else []
        done={(tuple(r['support']),r['algorithm'],r['seed']) for r in rr}
        newcount=0;tcase=time.perf_counter()
        for idx,c in enumerate(cs):
            rows=c['rows'];d=c['support']
            matrix=f'{n} {n}\n'+'\n'.join(' '.join(str((row>>j)&1) for j in range(n)) for row in rows)+'\n'
            for option,name in enumerate(['BP','RNBP','A1','A2']):
                for seed in range(1 if option==0 else args.seeds):
                    if (tuple(d),name,seed) in done:continue
                    stem=f'n{n}_w{w}_'+'-'.join(map(str,d))+f'_{name}_s{seed}'
                    r={k:v for k,v in c.items() if k!='rows'}
                    r.update(algorithm=name,seed=seed)
                    t=time.perf_counter()
                    try:
                        p=subprocess.run([str(EXECUTABLE),str(option),str(seed)],input=matrix,text=True,capture_output=True,timeout=args.timeout)
                        r['elapsed_seconds']=time.perf_counter()-t
                        if p.returncode:raise RuntimeError(f'exit={p.returncode} stdout={p.stdout} stderr={p.stderr}')
                        r.update(verify(p.stdout,rows,n),status='complete',circuit=f'circuits/{stem}.txt')
                        (HERE/r['circuit']).write_text(p.stdout)
                    except subprocess.TimeoutExpired:
                        r.update(status='timeout',elapsed_seconds=time.perf_counter()-t)
                    except Exception as exc:
                        r.update(status='error',error=str(exc),elapsed_seconds=time.perf_counter()-t)
                        with rp.open('a') as f:f.write(json.dumps(r)+'\n')
                        raise
                    with rp.open('a') as f:f.write(json.dumps(r)+'\n')
                    rr.append(r);newcount+=1
            good=[r for r in rr if tuple(r['support'])==tuple(d) and r['status']=='complete']
            print(f'CLASS n={n} w={w} {idx+1}/{len(cs)} support={d} best='+str(min((r['gates'],r['depth']) for r in good)) if good else f'CLASS n={n} no complete',flush=True)
        session=dict(new_trials=newcount,search_wall_seconds=time.perf_counter()-tcase)
        with (case/'sessions.jsonl').open('a') as f:f.write(json.dumps(session)+'\n')
        summarize(case,rr,args.seeds)
        print('DONE '+json.dumps(dict(n=n,weight=w,trials=len(rr),**session)),flush=True)

def summarize(case,rr,seeds):
    out=[]
    for conn in [False,True]:
        results=[r for r in rr if r['status']=='complete' and (not conn or r['connected'])]
        if not results:continue
        bydepth={}
        for cap in [2,3,4]:
            pool=[r for r in results if r['depth']<=cap]
            bydepth[str(cap)]=min(pool,key=lambda r:(r['gates'],r['depth'])) if pool else None
        milestones={}
        for count in [10,30,100]:
            if count>seeds:continue
            pool=[r for r in results if r['algorithm']=='BP' or r['seed']<count]
            milestones[str(count)]=min(pool,key=lambda r:(r['gates'],r['depth']))
        out.append(dict(connected_required=conn,best=min(results,key=lambda r:(r['gates'],r['depth'])),
            best_by_postfiltered_depth_cap=bydepth,best_by_seed_count=milestones,
            algorithms={a:dict(completed=sum(r['algorithm']==a for r in results),
                best=min((r for r in results if r['algorithm']==a),key=lambda r:(r['gates'],r['depth']),default=None),
                subprocess_seconds=sum(r['elapsed_seconds'] for r in results if r['algorithm']==a)) for a in ['BP','RNBP','A1','A2']}))
    (case/'summary.json').write_text(json.dumps(dict(trials=len(rr),timeouts=sum(r['status']=='timeout' for r in rr),
        errors=sum(r['status']=='error' for r in rr),results=out),indent=2))

if __name__=='__main__':main()
