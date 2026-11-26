from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
import hashlib, json, os, random, shutil, sys, time, traceback
from itertools import combinations, product
from pathlib import Path
from signed_paar import optimize, circulant
from verify_circuit import verify
from algebra_snapshot import canonical, security, components, BudgetExpired
HERE = Path(__file__).resolve().parent

def utc():return datetime.now(timezone.utc).isoformat()

def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.name+f'.{os.getpid()}.tmp')
    temp.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
    for _ in range(30):
        try:temp.replace(path);return
        except PermissionError:time.sleep(.05)
    raise PermissionError(str(path))

def task(job):
    folder=HERE/'tasks'/job['id'];state=json.loads((folder/'state.json').read_text())
    if state['status']=='complete':return state
    if state['status']!='pending':raise RuntimeError('Refuse duplicate task start')
    start=time.perf_counter();deadline=start+job['budget_seconds'];last=start
    n,p,w=job['n'],job['prime'],job['weight'];rng=random.Random(job['sampling_seed'])
    state.update(status='running',started_utc=utc(),worker_pid=os.getpid(),best_heuristic=None,
                 best_connected_heuristic=None,best_depth3_heuristic=None,trials_by_arm={})
    write(folder/'state.json',state)
    pool=json.loads((HERE/'pools'/f'w{w}_n{n}.json').read_text());rng.shuffle(pool)
    initial=list(state['initial_rows']);saved_index=0;proposal_index=0;seen=set();legal=[]
    lower=2*n-n//job['branch']
    def checkpoint(force=False):
        nonlocal last
        now=time.perf_counter()
        if force or now-last>3:
            state.update(elapsed_seconds=now-start,heartbeat_utc=utc())
            write(folder/'state.json',state);last=now
    def attempt(candidate,arithmetic,cap,seed,log):
        before=time.perf_counter()
        c=optimize(circulant(candidate['generator']),arithmetic,seed,cap,deadline=deadline)
        verified=verify(c);assert verified['gates']>=lower
        state['completed']+=1
        arm=f'p{arithmetic}_depth{cap or "any"}'
        state['trials_by_arm'][arm]=state['trials_by_arm'].get(arm,0)+1
        log.write(json.dumps(dict(candidate_id=candidate['id'],arithmetic_prime=arithmetic,max_depth=cap,
            seed=seed,gates=c['gate_count'],depth=c['depth'],integer_identity=verified['integer_identity'],
            elapsed_seconds=time.perf_counter()-before,task_seconds=time.perf_counter()-start,verified=True))+'\n');log.flush()
        rank=(c['gate_count'],c['depth']);candidate['best_rank']=min(tuple(candidate.get('best_rank',rank)),rank)
        keys=['best_heuristic']
        if candidate['connected']:keys.append('best_connected_heuristic')
        if c['depth']<=3:keys.append('best_depth3_heuristic')
        improved=[k for k in keys if state[k] is None or rank<(state[k]['gates'],state[k]['depth'])]
        if improved or rank<(state['best_upper']['gates'],state['best_upper']['depth']):
            name=f'circuits/trial_{state["completed"]:06}.json';write(folder/name,c)
            entry=dict(gates=c['gate_count'],depth=c['depth'],circuit=name,generator=candidate['generator'],
                connected=candidate['connected'],origin='heuristic',arithmetic_prime=arithmetic,max_depth=cap,
                seed=seed,integer_identity=verified['integer_identity'],found_at_task_seconds=time.perf_counter()-start)
            for key in improved:state[key]=entry
            if rank<(state['best_upper']['gates'],state['best_upper']['depth']):state['best_upper']=entry
        checkpoint()
    try:
        with (folder/'candidates.jsonl').open('w') as candidate_log,(folder/'trials.jsonl').open('w') as trial_log:
            while time.perf_counter()<deadline:
                if initial:row=initial.pop(0);origin='incumbent'
                elif proposal_index%2==0 and saved_index<len(pool):
                    row=pool[saved_index];saved_index+=1;origin='saved matrix record'
                else:
                    row=[0]*n;row[0]=1
                    for j in rng.sample(range(1,n),w-1):row[j]=rng.choice((-1,1))
                    origin='fresh normalized signed support'
                proposal_index+=1
                key=canonical(row,3)
                if key in seen:continue
                seen.add(key)
                row=[0]*n
                for j,sign in key:row[j]=sign
                properties=security(row,p,w+1,time.monotonic()+max(0,deadline-time.perf_counter()))
                state['candidates_checked']+=1
                candidate=dict(id=state['candidates_checked']-1,generator=row,origin=origin,
                    connected=components(row)==1,properties=properties,next_seed=0)
                candidate_log.write(json.dumps(candidate)+'\n');candidate_log.flush();checkpoint()
                if not properties['passed']:continue
                legal.append(candidate);state['legal_candidates']=len(legal)
                for arithmetic,cap in ((p,None),(0,None),(p,3),(0,3)):
                    attempt(candidate,arithmetic,cap,0,trial_log)
                candidate['next_seed']=1
                if len(legal)%4==0:
                    frontier=sorted(legal,key=lambda c:c['best_rank'])[:4]
                    revisited=rng.choice(frontier);seed=revisited['next_seed'];revisited['next_seed']+=1
                    for arithmetic,cap in ((p,None),(0,None),(p,3),(0,3)):
                        attempt(revisited,arithmetic,cap,seed,trial_log)
    except (TimeoutError,BudgetExpired):pass
    except BaseException:state.update(status='error',error=traceback.format_exc())
    finally:
        if state['status']!='error':state['status']='complete'
        state.update(ended_utc=utc(),elapsed_seconds=time.perf_counter()-start,
            beat_rectangle=state['best_upper']['gates']<job['rectangle_minimum'],
            beat_initial=state['best_upper']['gates']<state['initial_upper']['gates'],matrix_coverage='sampled')
        write(folder/'state.json',state)
    print(json.dumps({k:state.get(k) for k in ('id','status','completed','legal_candidates','best_upper')}),flush=True)
    return state
