"""Repeat selected recorded tasks into a NEW output directory."""
import argparse
from concurrent.futures import ProcessPoolExecutor
import importlib
import json
from pathlib import Path
import shutil
import sys

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE / 'src'))


def execute(payload):
    stage, output, job = payload
    worker = importlib.import_module(stage + '_worker')
    worker.HERE = Path(output)
    return worker.run_task(job) if stage == 'small' else worker.task(job)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--stage', choices=['small', 'large'], required=True)
    ap.add_argument('--orders', help='Comma-separated orders; default: all recorded tasks')
    ap.add_argument('--primes', help='Comma-separated primes; default: all recorded tasks')
    ap.add_argument('--seconds', type=float, help='Override 300s/600s for a short reproduction check')
    ap.add_argument('--workers', type=int, default=1)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    if args.workers < 1 or (args.seconds is not None and args.seconds <= 0):
        ap.error('workers and time budget must be positive')
    orders = set(map(int, args.orders.split(','))) if args.orders else None
    primes = set(map(int, args.primes.split(','))) if args.primes else None
    recorded = BASE / 'results' / args.stage
    from records import ensure_tasks
    ensure_tasks(recorded)
    jobs = [j for j in json.loads((recorded/'jobs.json').read_text())
            if j['rectangle_minimum'] and (orders is None or j['n'] in orders)
            and (primes is None or j['prime'] in primes)]
    if not jobs:
        ap.error('No feasible recorded task matches the selection')
    output = args.out.resolve()
    output.mkdir(parents=True, exist_ok=False)
    for job in jobs:
        if args.seconds is not None:
            job['budget_seconds'] = args.seconds
        folder = output/'tasks'/job['id']
        folder.mkdir(parents=True)
        original = recorded/'tasks'/job['id']
        previous = json.loads((original/'state.json').read_text())
        for p in original.glob('*_circuit.json'):
            shutil.copy2(p, folder/p.name)
        state = dict(job, status='pending', reason=None, completed=0,
                     legal_classes_tested=0, classes_checked=0,
                     candidates_checked=0, legal_candidates=0,
                     class_universe_complete=False, property_checks_complete=False)
        if args.stage == 'small':
            baseline = json.loads((folder/'baseline_circuit.json').read_text())
            from algebra_snapshot import components
            state.update(baseline_generator=baseline['matrix'][0],
                         baseline_source='recorded baseline_circuit.json',
                         best_upper=dict(gates=baseline['gate_count'],depth=baseline['depth'],
                                         circuit='baseline_circuit.json',origin='rectangle',
                                         connected=components(baseline['matrix'][0]) == 1))
        else:
            state.update(best_upper=previous['initial_upper'],
                         initial_upper=previous['initial_upper'],initial_rows=previous['initial_rows'])
            pool = output/'pools'/f'w{job["weight"]}_n{job["n"]}.json'
            pool.parent.mkdir(exist_ok=True)
            shutil.copy2(recorded/'pools'/pool.name,pool)
        (folder/'state.json').write_text(json.dumps(state,indent=2)+'\n')
    (output/'jobs.json').write_text(json.dumps(jobs,indent=2)+'\n')
    payloads = [(args.stage,str(output),job) for job in jobs]
    if args.workers == 1:
        results = [execute(p) for p in payloads]
    else:
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            results = list(pool.map(execute,payloads))
    (output/'results.json').write_text(json.dumps(results,indent=2)+'\n')
    errors = [s['id'] for s in results if s['status'] != 'complete']
    if errors:
        raise RuntimeError('Failed tasks: '+str(errors))
    print(json.dumps({'completed_tasks':len(results),'output':str(output)}))


if __name__ == '__main__':
    main()
