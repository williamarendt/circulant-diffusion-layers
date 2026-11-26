"""Verify the saved table witnesses without starting a search."""
import argparse
import csv
import json
from pathlib import Path
import sys
BASE = Path(__file__).resolve().parent
sys.path.insert(0,str(BASE/'src'))
from verify_circuit import verify
from algebra_snapshot import components, security


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--properties',action='store_true',help='Also recheck matrix invertibility/branch number')
    args=ap.parse_args()
    entries=json.loads((BASE/'witnesses/manifest.json').read_text())
    checked={}
    saved=0
    import zipfile
    for stage in ('small','large'):
        with zipfile.ZipFile(BASE/'results'/stage/'task_records.zip') as archive:
            for name in archive.namelist():
                if name.endswith('.json'):
                    record=json.loads(archive.read(name))
                    if isinstance(record,dict) and 'matrix' in record and 'gates' in record:
                        verify(record)
                        saved+=1
    for e in entries:
        c=json.loads((BASE/e['file']).read_text())
        result=verify(c)
        assert (result['gates'],result['depth']) == (e['gates'],e['depth'])
        assert len(c['matrix']) == e['n']
        assert c['prime'] == e['prime']
        connected=components(c['matrix'][0]) == 1
        assert connected == e['connected']
        if args.properties:
            key=(tuple(c['matrix'][0]),e['prime'])
            if key not in checked:
                checked[key]=security(list(key[0]),e['prime'],e['weight']+1)
            assert checked[key]['passed']
    published=list(csv.DictReader((BASE/'results/table.csv').open()))
    lookup={(e['n'],e['prime']):e for e in entries if e['scope']=='all'}
    for row in published:
        if row['upper'] == '---':
            continue
        e=lookup[int(row['n']),int(row['prime'])]
        assert (int(row['upper']),int(row['depth'])) == (e['gates'],e['depth'])
    print(json.dumps({'witnesses_verified':len(entries),'saved_circuits_verified':saved,'table_cells_verified':len(lookup),
                      'matrix_property_checks':len(checked),'searches_started':False}))


if __name__=='__main__':
    main()
