"""Independent exact checker for signed binary addition/subtraction circuits."""
import argparse
import json
from math import isqrt
from pathlib import Path


def verify(circuit):
    matrix = circuit['matrix']
    n = len(matrix[0])
    assert matrix and all(len(row) == n for row in matrix)
    vectors = [tuple(int(i == j) for j in range(n)) for i in range(n)]
    depths = [0] * n
    for gate in circuit['gates']:
        left, right = gate['left'], gate['right']
        ls, rs = gate['left_sign'], gate['right_sign']
        assert ls in (-1, 1) and rs in (-1, 1)
        assert 0 <= left < len(vectors) and 0 <= right < len(vectors)
        vectors.append(tuple(ls*a + rs*b for a, b in zip(vectors[left], vectors[right])))
        depths.append(1 + max(depths[left], depths[right]))
    actual = []
    output_depths = []
    needed = set()
    for output in circuit['outputs']:
        node, sign = output['signal'], output['sign']
        assert sign in (-1, 1)
        if node is None:
            actual.append((0,) * n)
            output_depths.append(0)
        else:
            assert 0 <= node < len(vectors)
            actual.append(tuple(sign*v for v in vectors[node]))
            output_depths.append(depths[node])
            needed.add(node)
    assert len(actual) == len(matrix)
    integer_identity = actual == [tuple(row) for row in matrix]
    prime = circuit['prime']
    assert prime == 0 or (prime >= 3 and all(prime % d for d in range(2, isqrt(prime)+1)))
    moduli = (3, 5, 7) if prime == 0 else (prime,)
    if prime == 0:
        assert integer_identity, 'Integer coefficient identity failed'
    for p in moduli:
        assert all(tuple(v % p for v in a) == tuple(v % p for v in b)
                   for a, b in zip(actual, matrix)), f'Identity failed modulo {p}'
    live = 0
    for i in range(len(circuit['gates']) - 1, -1, -1):
        if n+i in needed:
            live += 1
            gate = circuit['gates'][i]
            needed.update((gate['left'], gate['right']))
    assert live == len(circuit['gates']) == circuit['gate_count']
    assert max(output_depths, default=0) == circuit['depth']
    cap = circuit.get('max_depth')
    assert cap is None or circuit['depth'] <= cap
    return dict(verified=True, gates=live, depth=circuit['depth'],
                integer_identity=integer_identity, verified_moduli=list(moduli))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('circuit', type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(json.loads(args.circuit.read_text(encoding='utf-8')))))
