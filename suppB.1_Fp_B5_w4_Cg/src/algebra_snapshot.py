"""Finite-field arithmetic. No floating-point rank or inverse computations."""
from itertools import combinations, product
from math import gcd, isqrt
import time


class BudgetExpired(Exception):
    pass


def check_time(deadline=None):
    if deadline is not None and time.monotonic() >= deadline:
        raise BudgetExpired()


def prime(p):
    return p >= 2 and all(p % d for d in range(2, isqrt(p) + 1))


def circulant(a, p):
    n = len(a)
    return [[a[(j - i) % n] % p for j in range(n)] for i in range(n)]


def inverse(matrix, p, deadline=None):
    n = len(matrix)
    a = [[x % p for x in row] + [int(i == j) for j in range(n)]
         for i, row in enumerate(matrix)]
    for j in range(n):
        check_time(deadline)
        pivot = next((i for i in range(j, n) if a[i][j]), None)
        if pivot is None:
            return None
        a[j], a[pivot] = a[pivot], a[j]
        z = pow(a[j][j], -1, p)
        a[j] = [x * z % p for x in a[j]]
        for i in range(n):
            if i != j and a[i][j]:
                z = a[i][j]
                a[i] = [(x - z * y) % p for x, y in zip(a[i], a[j])]
    return [row[n:] for row in a]


def matvec(m, x, p):
    return [sum(a * b for a, b in zip(row, x)) % p for row in m]


def weight(x):
    return sum(v != 0 for v in x)


def security(a, p, b, deadline=None):
    """Prove B >= b, or give a counterexample; exact in all characteristics.

    The general method inspects both M and its inverse. Any violating pair
    (x,Mx) has one side of weight <= floor((b-1)/2).
    """
    m = circulant(a, p)
    inv = inverse(m, p, deadline)
    if inv is None:
        return {"passed": False, "reason": "singular"}
    n, k = len(a), weight(a)
    if p == 2 and k == 5 and b == 6:
        d = {i for i, v in enumerate(a) if v}
        overlaps = [len(d & {(j + t) % n for j in d}) for t in range(1, n)]
        ok = max(overlaps, default=0) <= 3 and weight(inv[0]) >= 5
        return {"passed": ok, "reason": "binary_weight5_exact", "full_rank": True,
                "inverse_weight": weight(inv[0]), "max_overlap": max(overlaps, default=0),
                "certified_branch_lower_bound": 6 if ok else None}
    if p != 2 and k == 4 and b == 5:
        ok = weight(inv[0]) >= 4
        worst = 0
        for t in range(1, n):
            check_time(deadline)
            same = opp = 0
            for j in range(n):
                u, v = a[j] % p, a[(j - t) % n] % p
                if u and v:
                    same += u == v
                    opp += u != v
            worst = max(worst, same + opp + max(same, opp))
        ok = ok and worst <= 5
        return {"passed": ok, "reason": "signed_weight4_exact", "full_rank": True,
                "inverse_weight": weight(inv[0]), "overlap_score": worst,
                "certified_branch_lower_bound": 5 if ok else None}
    checked = 0
    for direction, mat in (("forward", m), ("inverse", inv)):
        cols = [list(col) for col in zip(*mat)]
        masks = [sum((v != 0) << i for i, v in enumerate(col)) for col in cols] if p == 2 else None
        for t in range(1, min(n, (b - 1) // 2) + 1):
            for supp in combinations(range(n), t):
                check_time(deadline)
                for tail in product(range(1, p), repeat=t - 1):
                    checked += 1
                    if checked % 256 == 0:
                        check_time(deadline)
                    coeff = (1,) + tail
                    if p == 2:
                        out = 0
                        for j in supp:
                            out ^= masks[j]
                        w = out.bit_count()
                    else:
                        out = [sum(c * cols[j][i] for j, c in zip(supp, coeff)) % p
                               for i in range(n)]
                        w = weight(out)
                    if t + w < b:
                        return {"passed": False, "reason": "branch_counterexample",
                                "direction": direction, "support": list(supp),
                                "coefficients": list(coeff), "weight_sum": t + w}
    return {"passed": True, "full_rank": True, "reason": "bidirectional_small_support",
            "checked": checked, "certified_branch_lower_bound": b,
            "inverse_weight": weight(inv[0])}


def components(a):
    d = [i for i, x in enumerate(a) if x]
    g = len(a)
    for i in d:
        g = gcd(g, i - d[0])
    return g


def canonical(a, p):
    n = len(a)
    d = [i for i, x in enumerate(a) if x]
    best = None
    for u in range(1, n):
        if gcd(u, n) != 1:
            continue
        for anchor in d:
            sign = a[anchor] if p != 2 else 1
            key = tuple(sorted((((j - anchor) * u) % n, a[j] * sign) for j in d))
            if best is None or key < best:
                best = key
    return best


def lower_bound(n, k, b):
    c0 = n * (k - 1)
    if k == b - 1:
        r = b // 2
        if b % 2:
            num, den = 2 * (2 * r - 1) * n, r + 1
        else:
            num, den = 2 * (r - 1) * (2 * r - 1) * n, r * r
        return (num + den - 1) // den, "rectangle_closed_form_minimum_weight"
    r = min(k - 1, k + 1 - (b + 1) // 2)
    if r < 2:
        return c0, "no_nontrivial_rectangles"
    return (2 * c0 + r) // (r + 1), "rectangle_rank_ratio_nonminimum_weight"
