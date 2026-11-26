"""Small signed Paar-style greedy circuit optimizer over Z or an odd F_p.

Each counted gate is +/-u +/-v; copying and negation are free. Candidate
signals are pair sums/differences of existing signals. Exact matching to
subsets of residual output expressions allows nested reuse and cancellation.
This is a heuristic upper-bound search, not BP and not an exact C_g solver.
"""
import argparse
from collections import defaultdict
import heapq
from itertools import combinations
import json
from math import isqrt
from pathlib import Path
import random
import time

from verify_circuit import verify


def canonical(vector, p):
    vector = tuple(v % p for v in vector) if p else tuple(vector)
    first = next((v for v in vector if v), None)
    if first is None:
        return None, 1
    sign = -1 if (first > p//2 if p else first < 0) else 1
    return (tuple(sign*v % p for v in vector) if p else tuple(sign*v for v in vector)), sign


def normalize(terms, p):
    coefficients = defaultdict(int)
    for node, sign in terms:
        coefficients[node] += sign
    result = []
    for node, coefficient in sorted(coefficients.items()):
        if p:
            coefficient %= p
            if coefficient > p//2:
                coefficient -= p
        result.extend([(node, 1 if coefficient > 0 else -1)] * abs(coefficient))
    return tuple(result)


def completion_depth(terms, depths, extra=None):
    heap = [depths[node] if node < len(depths) else extra for node, _ in terms]
    heapq.heapify(heap)
    while len(heap) > 1:
        first = heapq.heappop(heap)
        second = heapq.heappop(heap)
        heapq.heappush(heap, max(first, second)+1)
    return heap[0] if heap else 0


def optimize(matrix, prime=0, seed=0, max_depth=None, subset_limit=6, deadline=None):
    def check_time():
        if deadline is not None and time.perf_counter() >= deadline:
            raise TimeoutError('Construction reached the task deadline')

    check_time()
    if prime and (prime < 3 or any(prime % d == 0 for d in range(2, isqrt(prime)+1))):
        raise ValueError('prime must be zero (integers) or an odd prime')
    if not matrix or not matrix[0] or any(len(row) != len(matrix[0]) for row in matrix):
        raise ValueError('Need a nonempty rectangular integer matrix')
    if subset_limit < 2:
        raise ValueError('subset_limit must be at least two')
    p, n = prime, len(matrix[0])
    rng = random.Random(seed)
    vectors = [tuple(int(i == j) for j in range(n)) for i in range(n)]
    depths, gates = [0]*n, []
    known = {vector: i for i, vector in enumerate(vectors)}
    expressions = [normalize([(i, 1 if c > 0 else -1)
                              for i, c in enumerate(row) for _ in range(abs(c))], p)
                   for row in matrix]
    if max_depth is not None and any(completion_depth(e, depths) > max_depth for e in expressions):
        raise ValueError('The direct addition trees do not fit max_depth')
    # vector -> (depth, left, right, left_sign, right_sign), best available pair.
    pairs = {}

    def extend_pairs(right):
        for left in range(right+1):
            check_time()
            for rs in ((1,) if left == right else (1, -1)):
                raw = tuple(a+rs*b for a, b in zip(vectors[left], vectors[right]))
                vector, orientation = canonical(raw, p)
                if vector is None:
                    continue
                candidate = (max(depths[left], depths[right])+1, left, right,
                             orientation, orientation*rs)
                if vector not in pairs or candidate < pairs[vector]:
                    pairs[vector] = candidate

    for node in range(n):
        extend_pairs(node)

    def create(vector, pair, recompute_shallower=False):
        if vector in known and not (recompute_shallower and
                                    depths[known[vector]] > pair[0]):
            return known[vector]
        depth, left, right, ls, rs = pair
        node = len(vectors)
        vectors.append(vector)
        depths.append(depth)
        gates.append(dict(left=left, right=right, left_sign=ls, right_sign=rs))
        known[vector] = node
        extend_pairs(node)
        return node

    while any(len(e) > 1 for e in expressions):
        check_time()
        patterns = defaultdict(lambda: defaultdict(list))
        removed_zero = False
        for row, expression in enumerate(expressions):
            check_time()
            for size in range(min(subset_limit, len(expression)), 1, -1):
                for indices in combinations(range(len(expression)), size):
                    raw = tuple(sum(expression[i][1]*vectors[expression[i][0]][j]
                                    for i in indices) for j in range(n))
                    vector, orientation = canonical(raw, p)
                    if vector is None:
                        expressions[row] = normalize([term for i, term in enumerate(expression)
                                                      if i not in indices], p)
                        removed_zero = True
                        break
                    patterns[vector][row].append((indices, orientation))
                if removed_zero:
                    break
            if removed_zero:
                break
        if removed_zero:
            continue
        best_gain, choices = -1, []
        for vector, matches in patterns.items():
            check_time()
            pair = pairs.get(vector)
            existing = known.get(vector)
            if existing is None and pair is None:
                continue
            node = existing if existing is not None else len(vectors)
            depth = depths[existing] if existing is not None else pair[0]
            if max_depth is not None and depth > max_depth:
                continue
            updates, saved = {}, 0
            for row, subsets in matches.items():
                winner = None
                for indices, orientation in subsets:
                    replacement = normalize([term for i, term in enumerate(expressions[row])
                                             if i not in indices] + [(node, orientation)], p)
                    final_depth = completion_depth(replacement, depths, depth)
                    if max_depth is not None and final_depth > max_depth:
                        continue
                    rank = (len(replacement), final_depth, replacement)
                    if winner is None or rank < winner:
                        winner = rank
                if winner is not None:
                    saved += len(expressions[row])-winner[0]
                    updates[row] = winner[2]
            gain = saved - int(existing is None)
            if not updates or gain < 0:
                continue
            if gain > best_gain:
                best_gain, choices = gain, []
            if gain == best_gain:
                choices.append((vector, pair, updates))
        if not choices:
            break
        # Zero immediate gain is permitted: an ordinary output-tree gate may
        # enable subsequent reuse. Residual term count still strictly decreases.
        vector, pair, updates = rng.choice(choices)
        create(vector, pair)
        for row, expression in updates.items():
            expressions[row] = expression

    outputs = []
    for expression in expressions:
        heap = [(depths[node], i, node, sign) for i, (node, sign) in enumerate(expression)]
        heapq.heapify(heap)
        counter = len(heap)
        while len(heap) > 1:
            _, _, left, ls = heapq.heappop(heap)
            _, _, right, rs = heapq.heappop(heap)
            raw = tuple(ls*a+rs*b for a, b in zip(vectors[left], vectors[right]))
            vector, orientation = canonical(raw, p)
            if vector is None:
                continue
            node = create(vector, (max(depths[left], depths[right])+1,
                                   left, right, orientation*ls, orientation*rs),
                          recompute_shallower=max_depth is not None)
            heapq.heappush(heap, (depths[node], counter, node, orientation))
            counter += 1
        outputs.append(dict(signal=heap[0][2], sign=heap[0][3]) if heap else dict(signal=None, sign=1))
    needed = {o['signal'] for o in outputs if o['signal'] is not None}
    for i in range(len(gates)-1, -1, -1):
        if n+i in needed:
            needed.update((gates[i]['left'], gates[i]['right']))
    relabel = {i: i for i in range(n)}
    live = []
    for i, gate in enumerate(gates):
        if n+i not in needed:
            continue
        relabel[n+i] = n+len(live)
        live.append(dict(gate, left=relabel[gate['left']], right=relabel[gate['right']]))
    result = dict(format='signed-add-circuit-v1', algorithm='signed Paar-style subset matching',
                  prime=p, seed=seed, max_depth=max_depth, subset_limit=subset_limit,
                  matrix=matrix, gates=live,
                  outputs=[dict(signal=relabel[o['signal']] if o['signal'] is not None else None,
                                sign=o['sign']) for o in outputs],
                  gate_count=len(live),
                  depth=max((depths[o['signal']] for o in outputs if o['signal'] is not None), default=0))
    result['verification'] = verify(result)
    return result


def circulant(row):
    n = len(row)
    return [[row[(j-i) % n] for j in range(n)] for i in range(n)]


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--row', required=True, help='Signed first row, comma separated')
    parser.add_argument('--prime', type=int, default=0, help='0: integers; otherwise an odd prime')
    parser.add_argument('--seeds', type=int, default=20)
    parser.add_argument('--max-depth', type=int)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.seeds < 1:
        parser.error('seeds must be positive')
    matrix = circulant([int(x) for x in args.row.split(',')])
    args.out.mkdir(parents=True, exist_ok=True)
    best = None
    with (args.out / 'trials.jsonl').open('w', encoding='utf-8') as log:
        for seed in range(args.seeds):
            start = time.perf_counter()
            circuit = optimize(matrix, args.prime, seed, args.max_depth)
            record = dict(seed=seed, gates=circuit['gate_count'], depth=circuit['depth'],
                          seconds=time.perf_counter()-start, verification=circuit['verification'])
            log.write(json.dumps(record)+'\n')
            if best is None or (circuit['gate_count'], circuit['depth']) < (best['gate_count'], best['depth']):
                best = circuit
                (args.out / 'best_circuit.json').write_text(json.dumps(best, indent=2)+'\n')
                print(json.dumps(record), flush=True)
