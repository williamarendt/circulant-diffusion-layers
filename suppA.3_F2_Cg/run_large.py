from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import argparse, json, os, subprocess, sys, threading, time, traceback
BASE=Path(__file__).resolve().parent
sys.path.insert(0,str(BASE/'src'))
from binary_helpers import rows_for, verify
HERE=BASE
EXECUTABLE=None
LOCK=threading.RLock()
ACTIVE={}

def utc():return datetime.now(timezone.utc).isoformat()

def atomic(path,data):
    temp=path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(data,indent=2),encoding='utf-8')
    temp.replace(path)

def task_state(job):
    path=HERE/'tasks'/job['id']/'state.json'
    if path.exists():return json.loads(path.read_text())
    return dict(status='pending',consumed_seconds=0,completed=0,next_seed=0,best=None,**job)

def run_task(job):
    directory=HERE/'tasks'/job['id'];directory.mkdir(parents=True,exist_ok=True)
    (directory/'circuits').mkdir(exist_ok=True)
    state=task_state(job)
    if state['status']=='complete':return
    previous=state.get('consumed_seconds',0)
    seed=state.get('next_seed',0)
    started=time.perf_counter()
    text=f"{job['n']} {job['n']}\n"+'\n'.join(' '.join(str((r>>j)&1) for j in range(job['n'])) for r in rows_for(job['support'],job['n']))+'\n'
    rows=rows_for(job['support'],job['n'])
    with LOCK:
        ACTIVE[job['id']]=dict(started=started,previous_seconds=previous,seed=seed,child_pid=None)
        state.update(status='running',started_utc=state.get('started_utc',utc()),last_session_utc=utc())
        atomic(directory/'state.json',state)
    try:
        while True:
            remaining=job['budget_seconds']-previous-(time.perf_counter()-started)
            if remaining<=0:break
            with LOCK:ACTIVE[job['id']].update(seed=seed,child_pid=None)
            trial_started=time.perf_counter();record=dict(seed=seed,started_utc=utc(),allowed_seconds=remaining)
            proc=subprocess.Popen([str(EXECUTABLE),str(job['option']),str(seed)],
                stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            with LOCK:ACTIVE[job['id']]['child_pid']=proc.pid
            try:
                output,error=proc.communicate(input=text,timeout=remaining)
                record['elapsed_seconds']=time.perf_counter()-trial_started
                if proc.returncode:raise RuntimeError(f'exit={proc.returncode}; {error}; {output}')
                result=verify(output,rows,job['n'])
                record.update(result,status='complete')
                # Preserve every completed trial; a best-so-far circuit is also
                # copied to a stable path for inspection during the run.
                name=f'circuits/seed_{seed:08}.txt'
                (directory/name).write_text(output)
                record['circuit']=name
                consumed=previous+time.perf_counter()-started
                current=(result['gates'],result['depth'])
                with LOCK:
                    state=task_state(job)
                    best=state.get('best')
                    gate_improved=best is None or result['gates']<best['gates']
                    if best is None or current<(best['gates'],best['depth']):
                        state['best']=dict(gates=result['gates'],depth=result['depth'],seed=seed,circuit=name,
                            found_at_task_seconds=consumed,verified=True)
                        (directory/'best_circuit.txt').write_text(output)
                        with (directory/'improvements.jsonl').open('a') as f:f.write(json.dumps(state['best'])+'\n')
                    if gate_improved:state['last_gate_improvement_seconds']=consumed
                    state.update(completed=state.get('completed',0)+1,next_seed=seed+1,consumed_seconds=min(consumed,job['budget_seconds']))
                    atomic(directory/'state.json',state)
            except subprocess.TimeoutExpired:
                proc.kill();output,error=proc.communicate()
                record.update(status='budget_exhausted_during_construction',elapsed_seconds=time.perf_counter()-trial_started)
            with LOCK:
                with (directory/'trials.jsonl').open('a') as f:f.write(json.dumps(record)+'\n')
            if record['status']!='complete':break
            seed+=1
        with LOCK:
            state=task_state(job)
            state.update(status='complete',ended_utc=utc(),consumed_seconds=job['budget_seconds'],
                actual_task_seconds=previous+time.perf_counter()-started,active_seed=None,child_pid=None,
                stopped_reason='fixed cumulative wall budget exhausted',
                stability_rule='no gate-count improvement in final half of task budget; descriptive only')
            last=state.get('last_gate_improvement_seconds')
            state['no_gate_improvement_in_final_half']=last is not None and last<=job['budget_seconds']/2
            state['stability_requires_caution']=state.get('completed',0)<20
            atomic(directory/'state.json',state)
            print(f"DONE {job['id']} completed={state.get('completed',0)} best={state.get('best')}",flush=True)
    except BaseException:
        with LOCK:
            state=task_state(job)
            state.update(status='error',error=traceback.format_exc(),consumed_seconds=min(job['budget_seconds'],previous+time.perf_counter()-started))
            atomic(directory/'state.json',state)
        raise
    finally:
        with LOCK:ACTIVE.pop(job['id'],None)

def main():
    global HERE, EXECUTABLE
    ap=argparse.ArgumentParser(description='Repeat the fixed 32/64 sample into a new output directory')
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--orders',default='32,64')
    ap.add_argument('--workers',type=int,default=8)
    ap.add_argument('--seconds',type=float,help='Optional per-task budget override for a short check')
    ap.add_argument('--limit-tasks',type=int,help='Optional first-task subset for a short check')
    ap.add_argument('--executable',type=Path,default=BASE/'src'/('bp_large.exe' if os.name=='nt' else 'bp_large'))
    args=ap.parse_args()
    if args.workers<1 or (args.seconds is not None and args.seconds<=0):ap.error('Invalid worker/budget count')
    HERE=args.out.resolve();EXECUTABLE=args.executable.resolve()
    jobs=json.loads((BASE/'results/large_jobs.json').read_text())
    orders=set(map(int,args.orders.split(',')));jobs=[j for j in jobs if j['n'] in orders]
    if args.limit_tasks is not None:jobs=jobs[:args.limit_tasks]
    if not jobs:ap.error('No tasks selected')
    if args.seconds is not None:
        jobs=[dict(j,budget_seconds=args.seconds) for j in jobs]
    HERE.mkdir(parents=True,exist_ok=False)
    atomic(HERE/'jobs.json',jobs)
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        list(pool.map(run_task,jobs))
    states=[task_state(j) for j in jobs]
    atomic(HERE/'results.json',states)
    if any(s['status']!='complete' for s in states):raise RuntimeError('Incomplete task')
    print(json.dumps({'tasks':len(states),'output':str(HERE)}))

if __name__=='__main__':main()
