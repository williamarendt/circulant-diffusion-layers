"""Audit all recorded binary SLPs and published table witnesses."""
import csv
import json
from pathlib import Path
import sys
import zipfile
BASE=Path(__file__).resolve().parent
sys.path.insert(0,str(BASE/'src'))
from binary_helpers import rows_for, verify


def main():
    total=0
    with zipfile.ZipFile(BASE/'results/small_records.zip') as z:
        for name in z.namelist():
            if name.endswith('/trials.jsonl'):
                for line in z.read(name).decode().splitlines():
                    r=json.loads(line)
                    if r['status']!='complete':continue
                    v=verify(z.read(r['circuit']).decode(),rows_for(r['support'],r['n']),r['n'])
                    assert (v['gates'],v['depth'])==(r['gates'],r['depth'])
                    total+=1
    jobs={j['id']:j for j in json.loads((BASE/'results/large_jobs.json').read_text())}
    with zipfile.ZipFile(BASE/'results/large_records.zip') as z:
        for name in z.namelist():
            if name.endswith('/trials.jsonl') and name.startswith('tasks/'):
                job=jobs[name.split('/')[1]]
                for line in z.read(name).decode().splitlines():
                    r=json.loads(line)
                    if r['status']!='complete':continue
                    slp=name.rsplit('/',1)[0]+'/'+r['circuit']
                    v=verify(z.read(slp).decode(),rows_for(job['support'],job['n']),job['n'])
                    assert (v['gates'],v['depth'])==(r['gates'],r['depth'])
                    total+=1
    witnesses=json.loads((BASE/'witnesses/manifest.json').read_text())
    for w in witnesses:
        v=verify((BASE/w['file']).read_text(),rows_for(w['support'],w['n']),w['n'])
        assert (v['gates'],v['depth'])==(w['gates'],w['depth'])
    assert total==35217+6829
    # Recompute each plotted cumulative minimum from the recorded trials.
    expected={}
    with zipfile.ZipFile(BASE/'results/small_records.zip') as z:
        for n in (13,14,15,16):
            trials=[json.loads(s) for s in z.read(f'n{n}_w5/trials.jsonl').decode().splitlines()]
            for algorithm in ('RNBP','A1','A2'):
                for k in range(1,101):
                    expected[n,algorithm,k]=min(r['gates'] for r in trials if r['algorithm']==algorithm and r['seed']<k)
    with (BASE/'figures/seed_progress_small_orders_20261125.csv').open() as f:
        for r in csv.DictReader(f):
            assert expected[int(r['n']),r['algorithm'],int(r['seeds_per_matrix'])]==int(r['best_xor_gates'])
    print(json.dumps({'recorded_circuits_verified':total,'selected_witnesses_verified':len(witnesses),
                      'figure_points_verified':len(expected),'searches_started':False}))


if __name__=='__main__':main()
