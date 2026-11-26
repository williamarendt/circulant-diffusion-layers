from math import gcd
import re

def canonical(d, n):
    return min(tuple(sorted((u*(j-a)) % n for j in d))
               for u in range(1,n) if gcd(u,n)==1 for a in d)

def rows_for(d, n):
    return [sum(1 << ((j+i)%n) for j in d) for i in range(n)]

def exact_branch(rows, n):
    # Exhaust all inputs; independent of the manuscript's small-support shortcut.
    cols = [sum(((row>>j)&1)<<i for i,row in enumerate(rows)) for j in range(n)]
    best = 2*n
    out = 0
    prev = 0
    for k in range(1,1<<n):
        x = k^(k>>1)
        out ^= cols[(x^prev).bit_length()-1]
        prev = x
        if out == 0:
            return None  # singular
        best = min(best, x.bit_count()+out.bit_count())
    return best

def verify(text, rows, n):
    lines=text.strip().splitlines()
    if not lines or not lines[0].startswith('GATES '): raise ValueError(text)
    expected=int(lines[0].split()[1])
    values={f'x{i}':1<<i for i in range(n)}
    depths={f'x{i}':0 for i in range(n)}
    ops=[]
    for line in lines[1:]:
        m=re.fullmatch(r'(\w+) = (\w+) \+ (\w+)',line.strip())
        if not m: raise ValueError(line)
        dst,a,b=m.groups()
        if dst in values: raise ValueError('reassigned signal')
        values[dst]=values[a]^values[b]
        depths[dst]=1+max(depths[a],depths[b])
        ops.append((dst,a,b))
    assert len(ops)==expected
    assert all(values[f'y{i}']==row for i,row in enumerate(rows))
    # Remove dead gates for both gate count and actual output depth reporting.
    needed={f'y{i}' for i in range(n)}
    live=[]
    for dst,a,b in reversed(ops):
        if dst in needed:
            needed.update((a,b)); live.append((dst,a,b))
    return {'gates':len(live),'raw_gates':expected,'depth':max(depths[f'y{i}'] for i in range(n)),
            'dead_gates':expected-len(live),'verified':True}
