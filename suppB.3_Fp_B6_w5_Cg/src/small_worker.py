from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
import hashlib, json, os, random, shutil, sys, time, traceback
from itertools import combinations, product
from pathlib import Path
from signed_paar import optimize, circulant
from verify_circuit import verify
from algebra_snapshot import canonical, security, components, BudgetExpired
HERE = Path(__file__).resolve().parent

def utc():
    return datetime.now(timezone.utc).isoformat()

def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name+f'.{os.getpid()}.tmp')
    temporary.write_text(json.dumps(value, indent=2)+'\n', encoding='utf-8')
    for attempt in range(30):
        try:
            temporary.replace(path)
            return
        except PermissionError:
            time.sleep(.05)
    raise PermissionError(f'Cannot replace {path}')

def run_task(job):
    folder = HERE/'tasks'/job['id']
    state = json.loads((folder/'state.json').read_text())
    if state['status'] in ('complete','infeasible'):
        return state
    if state['status'] != 'pending':
        raise RuntimeError(f"Refuse automatic restart of {job['id']} in {state['status']}")
    started = time.perf_counter()
    deadline = started+job['budget_seconds']
    folder.joinpath('circuits').mkdir(exist_ok=True)
    state.update(status='running', started_utc=utc(), worker_pid=os.getpid(),
        elapsed_seconds=0, trials_by_arm={}, best_heuristic=None, best_heuristic_depth3=None,
        best_connected_heuristic=None, best_integer_heuristic=None)
    write(folder/'state.json', state)
    n, p, w = job['n'], job['prime'], job['weight']
    lower = 2*n-n//job['branch']
    last_write = started
    rng = random.Random(job['order_seed'])
    legal = []
    terminal = 'fixed task budget exhausted'

    def checkpoint(force=False):
        nonlocal last_write
        now = time.perf_counter()
        if force or now-last_write >= 3:
            state.update(elapsed_seconds=now-started, heartbeat_utc=utc())
            write(folder/'state.json', state)
            last_write = now

    def attempt(candidate, arithmetic, cap, seed, log):
        if time.perf_counter() >= deadline:
            raise TimeoutError()
        t = time.perf_counter()
        circuit = optimize(circulant(candidate['generator']), arithmetic, seed, cap, deadline=deadline)
        result = verify(circuit)
        assert result['gates'] >= lower, (job, result)
        state['completed'] += 1
        arm = f'p{arithmetic}_depth{cap or "any"}'
        state['trials_by_arm'][arm] = state['trials_by_arm'].get(arm,0)+1
        record = dict(candidate_id=candidate['id'], generator=candidate['generator'],
            arithmetic_prime=arithmetic, max_depth=cap, seed=seed, gates=result['gates'],
            depth=result['depth'], elapsed_seconds=time.perf_counter()-t,
            task_seconds=time.perf_counter()-started, integer_identity=result['integer_identity'], verified=True)
        log.write(json.dumps(record)+'\n')
        log.flush()
        eligible = ['best_heuristic']
        if result['depth'] <= 3:
            eligible.append('best_heuristic_depth3')
        if candidate['connected']:
            eligible.append('best_connected_heuristic')
        if result['integer_identity']:
            eligible.append('best_integer_heuristic')
        improved = [key for key in eligible if state.get(key) is None or
                    (result['gates'],result['depth']) < (state[key]['gates'],state[key]['depth'])]
        if improved:
            name = f'circuits/trial_{state["completed"]:07}.json'
            write(folder/name, circuit)
            entry = dict(gates=result['gates'],depth=result['depth'],circuit=name,
                         generator=candidate['generator'],connected=candidate['connected'],
                         arithmetic_prime=arithmetic,max_depth=cap,seed=seed,
                         integer_identity=result['integer_identity'],found_at_task_seconds=time.perf_counter()-started)
            for key in improved:
                state[key] = entry
            prior = state['best_upper']
            if (entry['gates'],entry['depth']) < (prior['gates'],prior['depth']):
                state['best_upper'] = dict(entry,origin='heuristic')
                state['last_gate_improvement_seconds'] = time.perf_counter()-started
        checkpoint()
        if result['gates'] == lower:
            raise StopIteration('A verified upper bound meets the proved general lower bound')

    try:
        # Canonical signed support classes are independent of the odd prime.
        keys = set()
        for tail in combinations(range(1,n),w-1):
            for signs in product((1,-1), repeat=w-1):
                if time.perf_counter() >= deadline:
                    raise TimeoutError()
                row = [0]*n
                row[0] = 1
                for j, sign in zip(tail, signs):
                    row[j] = sign
                keys.add(canonical(row,3))
            checkpoint()
        universe = sorted(keys)
        rng.shuffle(universe)
        baseline_key = canonical(state['baseline_generator'],3)
        universe.remove(baseline_key)
        universe.insert(0,baseline_key)
        state.update(class_universe_complete=True,total_affine_classes=len(universe))
        with (folder/'candidates.jsonl').open('w',encoding='utf-8') as candidates_log, \
             (folder/'trials.jsonl').open('w',encoding='utf-8') as trial_log:
            for index, key in enumerate(universe):
                # security() uses time.monotonic(); translate the remaining
                # perf_counter budget explicitly rather than assuming clocks equal.
                remaining = deadline-time.perf_counter()
                if remaining <= 0:
                    raise TimeoutError()
                row = [0]*n
                for j, sign in key:
                    row[j] = sign
                properties = security(row,p,w+1,time.monotonic()+remaining)
                state['classes_checked'] += 1
                candidate = dict(id=index,generator=row,connected=components(row)==1,
                                 properties=properties)
                candidates_log.write(json.dumps(candidate)+'\n')
                if properties['passed']:
                    legal.append(candidate)
                    state['legal_classes_tested'] = len(legal)
                    attempt(candidate,p,None,0,trial_log)
                checkpoint()
            state['property_checks_complete'] = True
            state['legal_classes_total'] = len(legal)
            if not legal:
                raise RuntimeError('Known feasible task unexpectedly has no legal representative')
            # First pass already covered (field, no cap, seed0).
            for arithmetic, cap in ((0,None),(p,3),(0,3)):
                order = legal[:]
                rng.shuffle(order)
                for candidate in order:
                    attempt(candidate,arithmetic,cap,0,trial_log)
            seed = 1
            while True:
                state['current_seed_round'] = seed
                for arithmetic,cap in ((p,None),(0,None),(p,3),(0,3)):
                    order = legal[:]
                    rng.shuffle(order)
                    for candidate in order:
                        attempt(candidate,arithmetic,cap,seed,trial_log)
                seed += 1
    except StopIteration as exc:
        terminal = str(exc)
        state['exact_via_matching_bound'] = True
    except (TimeoutError,BudgetExpired):
        pass
    except BaseException:
        state.update(status='error', error=traceback.format_exc())
    finally:
        if state['status'] != 'error':
            state['status'] = 'complete'
        state.update(ended_utc=utc(),elapsed_seconds=time.perf_counter()-started,stopped_reason=terminal,
                     beat_rectangle=state['best_upper']['gates'] < job['rectangle_minimum'])
        write(folder/'state.json',state)
    print(json.dumps({k:state.get(k) for k in ('id','status','completed','legal_classes_tested',
                                             'classes_checked','total_affine_classes','best_upper')}),flush=True)
    return state
