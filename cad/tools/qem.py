"""Garland-Heckbert quadric edge-collapse decimation (triangles), boundary-preserving, flip-checked."""
import heapq
import numpy as np


def decimate(V, F, target, boundary_w=1e3):
    V = [np.array(v, float) for v in V]
    F = [list(f) for f in F]
    alive = [True] * len(F)
    vf = [set() for _ in V]
    for i, f in enumerate(F):
        for v in f: vf[v].add(i)
    Q = [np.zeros((4, 4)) for _ in V]

    def plane(f):
        a, b, c = V[f[0]], V[f[1]], V[f[2]]
        n = np.cross(b - a, c - a); s = np.linalg.norm(n)
        if s < 1e-20: return None, 0
        n = n / s
        return np.append(n, -n.dot(a)), s / 2

    for f in F:
        p, area = plane(f)
        if p is None: continue
        K = np.outer(p, p) * area
        for v in f: Q[v] += K
    # boundary edges: add a perpendicular constraint plane
    ecount = {}
    for i, f in enumerate(F):
        for j in range(3):
            e = tuple(sorted((f[j], f[(j + 1) % 3])))
            ecount.setdefault(e, []).append(i)
    for e, fs in ecount.items():
        if len(fs) == 1:
            f = F[fs[0]]; p, _ = plane(f)
            if p is None: continue
            a, b = V[e[0]], V[e[1]]
            d = b - a; n = np.cross(d, p[:3]); s = np.linalg.norm(n)
            if s < 1e-20: continue
            n /= s; q = np.append(n, -n.dot(a))
            K = np.outer(q, q) * boundary_w * np.dot(d, d)
            Q[e[0]] += K; Q[e[1]] += K

    ver = [0] * len(V)

    def cost(a, b):
        Qs = Q[a] + Q[b]
        A = Qs.copy(); A[3] = [0, 0, 0, 1]
        cands = []
        try:
            if abs(np.linalg.det(A)) > 1e-12:
                cands.append(np.linalg.solve(A, [0, 0, 0, 1])[:3])
        except np.linalg.LinAlgError:
            pass
        cands += [V[a], V[b], (V[a] + V[b]) / 2]
        best = None
        for x in cands:
            h = np.append(x, 1); c = h @ Qs @ h
            if best is None or c < best[0]: best = (c, x)
        return best

    heap = []
    def push(a, b):
        c, x = cost(a, b)
        heapq.heappush(heap, (c, a, b, ver[a], ver[b], tuple(x)))
    for e in ecount: push(*e)

    nf = sum(alive)
    while nf > target and heap:
        c, a, b, va, vb, x = heapq.heappop(heap)
        if ver[a] != va or ver[b] != vb or not vf[a] or not vf[b]: continue
        shared = vf[a] & vf[b]
        if not shared: continue
        x = np.array(x)
        # link condition (keeps manifoldness)
        na = {v for f in vf[a] for v in F[f]} - {a}
        nb = {v for f in vf[b] for v in F[f]} - {b}
        opp = {v for f in shared for v in F[f]} - {a, b}
        if (na & nb) != opp: continue
        ok = True
        for f in (vf[a] | vf[b]) - shared:
            tri = F[f]
            old = [V[v] for v in tri]
            new = [x if v in (a, b) else V[v] for v in tri]
            n0 = np.cross(old[1] - old[0], old[2] - old[0]); n1 = np.cross(new[1] - new[0], new[2] - new[0])
            l0, l1 = np.linalg.norm(n0), np.linalg.norm(n1)
            if l1 < 1e-14 or (l0 > 0 and n0.dot(n1) / (l0 * l1) < 0.3): ok = False; break
        if not ok: continue
        V[a] = x; Q[a] = Q[a] + Q[b]
        for f in shared:
            alive[f] = False; nf -= 1
            for v in F[f]: vf[v].discard(f)
        for f in list(vf[b]):
            F[f] = [a if v == b else v for v in F[f]]; vf[a].add(f)
        vf[b] = set(); ver[a] += 1; ver[b] += 1
        for v in {v for f in vf[a] for v in F[f]} - {a}: push(min(a, v), max(a, v)) if a != v else None
    # compact
    used = sorted({v for i, f in enumerate(F) if alive[i] for v in f})
    remap = {v: i for i, v in enumerate(used)}
    V2 = np.array([V[v] for v in used])
    F2 = [[remap[v] for v in f] for i, f in enumerate(F) if alive[i]]
    return V2, F2
