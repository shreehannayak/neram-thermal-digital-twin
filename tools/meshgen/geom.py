"""Geometry library for the NERAM procedural scene (offline generator, numpy only + skimage marching cubes).

Coordinates are UNITY coordinates (metres, Y up, +Z toward the patient's head, patient's LEFT = +X). Triangles are
emitted so that the numeric cross product (b - a) x (c - a) points OUTWARD; this is exactly what Unity's own
primitives use (e.g. Quad: verts (-.5,-.5,0),(.5,-.5,0),(-.5,.5,0),(.5,.5,0), tris 0,3,1 -> normal (0,0,-1)), so no
handedness flip is applied anywhere and left/right cannot be mirrored (unlike the OBJ importer, which negates X).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

try:
    from skimage.measure import marching_cubes
except Exception:  # pragma: no cover
    marching_cubes = None


# ----------------------------------------------------------------------------------------------- mesh container
@dataclass
class Mesh:
    V: np.ndarray  # (n,3) float
    N: np.ndarray  # (n,3) float, unit
    F: np.ndarray  # (m,3) int
    UV: np.ndarray | None = None  # (n,2)

    def copy(self) -> "Mesh":
        return Mesh(self.V.copy(), self.N.copy(), self.F.copy(), None if self.UV is None else self.UV.copy())

    @property
    def tris(self) -> int:
        return int(len(self.F))

    def transformed(self, R: np.ndarray | None = None, t=(0, 0, 0), s=None) -> "Mesh":
        V = self.V.copy()
        N = self.N.copy()
        if s is not None:
            s = np.asarray(s, float) * np.ones(3)
            V = V * s
            N = N / s
            N /= np.linalg.norm(N, axis=1, keepdims=True) + 1e-12
            if np.prod(s) < 0:
                F = self.F[:, ::-1].copy()
            else:
                F = self.F.copy()
        else:
            F = self.F.copy()
        if R is not None:
            V = V @ R.T
            N = N @ R.T
        V = V + np.asarray(t, float)
        return Mesh(V, N, F, None if self.UV is None else self.UV.copy())


def merge(meshes) -> Mesh:
    meshes = [m for m in meshes if m is not None and len(m.F)]
    if not meshes:
        return Mesh(np.zeros((0, 3)), np.zeros((0, 3)), np.zeros((0, 3), int), np.zeros((0, 2)))
    Vs, Ns, Fs, UVs = [], [], [], []
    off = 0
    for m in meshes:
        Vs.append(m.V)
        Ns.append(m.N)
        Fs.append(m.F + off)
        UVs.append(m.UV if m.UV is not None else box_uv(m.V, m.N))
        off += len(m.V)
    return Mesh(np.vstack(Vs), np.vstack(Ns), np.vstack(Fs), np.vstack(UVs))


def box_uv(V, N, scale=1.0):
    """Tri-planar style UVs (dominant normal axis), metres * scale. Only used for subtle fabric/floor detail maps."""
    a = np.argmax(np.abs(N), axis=1)
    uv = np.where(a[:, None] == 0, V[:, [2, 1]], np.where(a[:, None] == 1, V[:, [0, 2]], V[:, [0, 1]]))
    return uv * scale


def face_normals(V, F):
    n = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    return n


def orient_outward(m: Mesh) -> Mesh:
    """Flip triangles whose geometric normal disagrees with the (outward) vertex normals."""
    fn = face_normals(m.V, m.F)
    vn = m.N[m.F].sum(axis=1)
    flip = np.einsum("ij,ij->i", fn, vn) < 0
    F = m.F.copy()
    F[flip] = F[flip][:, ::-1]
    return Mesh(m.V, m.N, F, m.UV)


def double_sided(m: Mesh, offset=0.0) -> Mesh:
    back = Mesh(m.V - m.N * offset, -m.N, m.F[:, ::-1].copy(), None if m.UV is None else m.UV.copy())
    return merge([m, back])


def submesh_by_faces(m: Mesh, mask: np.ndarray) -> Mesh:
    F = m.F[mask]
    if len(F) == 0:
        return None
    used = np.unique(F)
    remap = -np.ones(len(m.V), int)
    remap[used] = np.arange(len(used))
    return Mesh(m.V[used], m.N[used], remap[F], None if m.UV is None else m.UV[used])


def rot_x(deg):
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def rot_y(deg):
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def rot_z(deg):
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def frame_from(z_axis, y_hint=(0, 1, 0)):
    """Rotation whose columns are (x, y, z) with z = given axis and y as close as possible to y_hint."""
    z = np.asarray(z_axis, float)
    z = z / np.linalg.norm(z)
    y = np.asarray(y_hint, float)
    y = y - z * np.dot(y, z)
    if np.linalg.norm(y) < 1e-6:
        y = np.array([1.0, 0, 0]) - z * z[0]
    y /= np.linalg.norm(y)
    x = np.cross(y, z)
    return np.stack([x, y, z], axis=1)


# ----------------------------------------------------------------------------------------------- parametric primitives
def rounded_box(size, radius, center=(0, 0, 0), R=None, k=5) -> Mesh:
    """Box with rounded edges (smooth normals). size = full extents. k = arc segments per rounded edge."""
    h = np.asarray(size, float) / 2.0
    r = float(min(radius, *(h * 0.999)))
    core = h - r
    arc = np.sin(np.linspace(0, math.pi / 2, k + 1))

    def coords(axis):
        neg = -(core[axis] + r * arc[::-1])
        pos = core[axis] + r * arc
        return np.concatenate([neg, pos])

    cx, cy, cz = coords(0), coords(1), coords(2)
    Vs, Fs = [], []
    off = 0
    for axis in range(3):
        for sign in (-1, 1):
            o = [a for a in range(3) if a != axis]
            A, B = (cx, cy, cz)[o[0]], (cx, cy, cz)[o[1]]
            ga, gb = np.meshgrid(A, B, indexing="ij")
            P = np.zeros(ga.shape + (3,))
            P[..., axis] = sign * h[axis]
            P[..., o[0]] = ga
            P[..., o[1]] = gb
            P = P.reshape(-1, 3)
            inner = np.clip(P, -core, core)
            d = P - inner
            n = d / (np.linalg.norm(d, axis=1, keepdims=True) + 1e-12)
            V = inner + n * r
            na, nb = len(A), len(B)
            idx = np.arange(na * nb).reshape(na, nb)
            a0 = idx[:-1, :-1].ravel()
            a1 = idx[1:, :-1].ravel()
            b0 = idx[:-1, 1:].ravel()
            b1 = idx[1:, 1:].ravel()
            F = np.vstack([np.stack([a0, a1, b1], 1), np.stack([a0, b1, b0], 1)])
            Vs.append(V)
            Fs.append(F + off)
            off += len(V)
    V = np.vstack(Vs)
    F = np.vstack(Fs)
    # weld duplicate edge vertices
    V, F = weld(V, F)
    inner = np.clip(V, -core, core)
    d = V - inner
    N = d / (np.linalg.norm(d, axis=1, keepdims=True) + 1e-12)
    m = orient_outward(Mesh(V, N, F))
    if R is not None:
        m = m.transformed(R=R)
    return m.transformed(t=center)


def weld(V, F, tol=1e-7):
    key = np.round(V / tol).astype(np.int64)
    _, first, inv = np.unique(key, axis=0, return_index=True, return_inverse=True)
    inv = inv.ravel()
    F2 = inv[F]
    ok = (F2[:, 0] != F2[:, 1]) & (F2[:, 1] != F2[:, 2]) & (F2[:, 0] != F2[:, 2])
    return V[first], F2[ok]


def box(size, center=(0, 0, 0), R=None) -> Mesh:
    """Sharp box with flat normals (24 vertices)."""
    h = np.asarray(size, float) / 2
    Vs, Ns, Fs, UVs = [], [], [], []
    for axis in range(3):
        for sign in (-1, 1):
            o = [a for a in range(3) if a != axis]
            quad = []
            for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                p = np.zeros(3)
                p[axis] = sign * h[axis]
                p[o[0]] = a * h[o[0]]
                p[o[1]] = b * h[o[1]]
                quad.append(p)
            n = np.zeros(3)
            n[axis] = sign
            base = len(Vs) * 0 + sum(len(v) for v in Vs)
            Vs.append(np.array(quad))
            Ns.append(np.tile(n, (4, 1)))
            UVs.append(np.array([[0, 0], [1, 0], [1, 1], [0, 1]], float))
            Fs.append(np.array([[0, 1, 2], [0, 2, 3]]) + base)
    m = orient_outward(Mesh(np.vstack(Vs), np.vstack(Ns), np.vstack(Fs), np.vstack(UVs)))
    if R is not None:
        m = m.transformed(R=R)
    return m.transformed(t=center)


def lathe(profile, segments=32, center=(0, 0, 0), R=None, creases=(), cap=True, uv_v=None) -> Mesh:
    """Surface of revolution about local +Y. profile = [(radius, y), ...] from bottom to top.
    Indices in `creases` get split normals (sharp edge). Radius 0 at the ends closes the shape."""
    prof = [tuple(map(float, p)) for p in profile]
    pts = []
    for i, p in enumerate(prof):
        pts.append((p, i in creases))
    rows = []  # list of (r, y, nr, ny)
    n = len(prof)
    for i, (p, crease) in enumerate(pts):
        r, y = p
        def seg_n(a, b):
            dr, dy = b[0] - a[0], b[1] - a[1]
            l = math.hypot(dr, dy) or 1.0
            return (dy / l, -dr / l)
        nprev = seg_n(prof[i - 1], p) if i > 0 else None
        nnext = seg_n(p, prof[i + 1]) if i < n - 1 else None
        if crease and nprev is not None and nnext is not None:
            rows.append((r, y) + nprev)
            rows.append((r, y) + nnext)
        else:
            cands = [v for v in (nprev, nnext) if v is not None]
            nr = sum(v[0] for v in cands)
            ny = sum(v[1] for v in cands)
            l = math.hypot(nr, ny) or 1.0
            rows.append((r, y, nr / l, ny / l))
    th = np.linspace(0, 2 * math.pi, segments + 1)
    c, s = np.cos(th), np.sin(th)
    V, N, UV = [], [], []
    for j, (r, y, nr, ny) in enumerate(rows):
        for k in range(segments + 1):
            V.append((r * c[k], y, r * s[k]))
            N.append((nr * c[k], ny, nr * s[k]))
            UV.append((k / segments, j / max(1, len(rows) - 1)))
    V = np.array(V)
    N = np.array(N)
    F = []
    w = segments + 1
    for j in range(len(rows) - 1):
        if abs(rows[j][0] - rows[j + 1][0]) < 1e-12 and abs(rows[j][1] - rows[j + 1][1]) < 1e-12:
            continue  # crease duplicate row
        for k in range(segments):
            a = j * w + k
            b = a + 1
            c2 = a + w
            d = c2 + 1
            F.append((a, c2, d))
            F.append((a, d, b))
    F = np.array(F)
    m = Mesh(V, N, F, np.array(UV))
    # drop degenerate (r=0) triangles
    fn = face_normals(m.V, m.F)
    keep = np.linalg.norm(fn, axis=1) > 1e-14
    m = Mesh(m.V, m.N, m.F[keep], m.UV)
    m = orient_outward(m)
    parts = [m]
    if cap:
        for end in (0, len(prof) - 1):
            r, y = prof[end]
            if r > 1e-9:
                disc = disc_mesh(r, segments, up=(end != 0)).transformed(t=(0, y, 0))
                parts.append(disc)
    m = merge(parts)
    if R is not None:
        m = m.transformed(R=R)
    return m.transformed(t=center)


def disc_mesh(r, segments=32, up=True) -> Mesh:
    th = np.linspace(0, 2 * math.pi, segments, endpoint=False)
    V = np.vstack([[0, 0, 0], np.stack([r * np.cos(th), np.zeros_like(th), r * np.sin(th)], 1)])
    N = np.tile([0, 1.0 if up else -1.0, 0], (len(V), 1))
    F = np.array([(0, 1 + k, 1 + (k + 1) % segments) for k in range(segments)])
    UV = np.vstack([[0.5, 0.5], np.stack([0.5 + 0.5 * np.cos(th), 0.5 + 0.5 * np.sin(th)], 1)])
    return orient_outward(Mesh(V, N, F, UV))


def cylinder(r, h, center=(0, 0, 0), R=None, segments=24, bevel=0.0) -> Mesh:
    if bevel > 0:
        prof = [(0, -h / 2), (r - bevel, -h / 2), (r, -h / 2 + bevel), (r, h / 2 - bevel), (r - bevel, h / 2), (0, h / 2)]
        return lathe(prof, segments, center, R, creases=(1, 4), cap=False)
    prof = [(0, -h / 2), (r, -h / 2), (r, h / 2), (0, h / 2)]
    return lathe(prof, segments, center, R, creases=(1, 2), cap=False)


def tube(points, radius, segments=12, closed_ends=True, radii=None) -> Mesh:
    """Circular tube swept along a polyline (parallel-transport frames)."""
    P = np.asarray(points, float)
    if radii is None:
        radii = np.full(len(P), radius, float)
    radii = np.asarray(radii, float)
    T = np.gradient(P, axis=0)
    T /= np.linalg.norm(T, axis=1, keepdims=True) + 1e-12
    ref = np.array([0, 1.0, 0]) if abs(T[0][1]) < 0.9 else np.array([1.0, 0, 0])
    Nn = np.cross(T[0], ref)
    Nn /= np.linalg.norm(Nn)
    frames = []
    for i in range(len(P)):
        if i > 0:
            Nn = Nn - T[i] * np.dot(Nn, T[i])
            Nn /= np.linalg.norm(Nn) + 1e-12
        B = np.cross(T[i], Nn)
        frames.append((Nn.copy(), B))
    th = np.linspace(0, 2 * math.pi, segments + 1)
    V, N, UV = [], [], []
    acc = 0.0
    for i, (n_, b_) in enumerate(frames):
        if i > 0:
            acc += np.linalg.norm(P[i] - P[i - 1])
        for k in range(segments + 1):
            d = n_ * math.cos(th[k]) + b_ * math.sin(th[k])
            V.append(P[i] + d * radii[i])
            N.append(d)
            UV.append((k / segments, acc))
    V = np.array(V)
    N = np.array(N)
    w = segments + 1
    F = []
    for i in range(len(P) - 1):
        for k in range(segments):
            a = i * w + k
            F.append((a, a + w, a + w + 1))
            F.append((a, a + w + 1, a + 1))
    m = orient_outward(Mesh(V, N, np.array(F), np.array(UV)))
    parts = [m]
    if closed_ends:
        for i, sgn in ((0, -1), (len(P) - 1, 1)):
            d = disc_mesh(radii[i], segments, up=True)
            Rd = rotation_between((0, 1, 0), T[i] * sgn)  # disc normal +Y -> outward tangent
            parts.append(d.transformed(R=Rd, t=P[i]))
    return merge(parts)


def rotation_between(a, b):
    a = np.asarray(a, float)
    b = np.asarray(b, float)
    a /= np.linalg.norm(a)
    b /= np.linalg.norm(b)
    v = np.cross(a, b)
    c = np.dot(a, b)
    if c < -0.999999:
        axis = np.array([1.0, 0, 0]) if abs(a[0]) < 0.9 else np.array([0, 0, 1.0])
        v = np.cross(a, axis)
        v /= np.linalg.norm(v)
        return 2 * np.outer(v, v) - np.eye(3)
    vx = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + vx + vx @ vx / (1 + c)


def torus(R0, r, center=(0, 0, 0), Rm=None, seg_major=48, seg_minor=12, arc=2 * math.pi) -> Mesh:
    u = np.linspace(0, arc, seg_major + 1)
    v = np.linspace(0, 2 * math.pi, seg_minor + 1)
    uu, vv = np.meshgrid(u, v, indexing="ij")
    cx, cz = np.cos(uu), np.sin(uu)
    V = np.stack([(R0 + r * np.cos(vv)) * cx, r * np.sin(vv), (R0 + r * np.cos(vv)) * cz], -1).reshape(-1, 3)
    N = np.stack([np.cos(vv) * cx, np.sin(vv), np.cos(vv) * cz], -1).reshape(-1, 3)
    w = seg_minor + 1
    F = []
    for i in range(seg_major):
        for j in range(seg_minor):
            a = i * w + j
            F.append((a, a + 1, a + w + 1))
            F.append((a, a + w + 1, a + w))
    m = orient_outward(Mesh(V, N, np.array(F)))
    if Rm is not None:
        m = m.transformed(R=Rm)
    return m.transformed(t=center)


def quad(w, h, center=(0, 0, 0), normal=(0, 0, -1), up=(0, 1, 0), uv_flip_u=False) -> Mesh:
    """Textured quad; the texture reads correctly when viewed from the side the normal points to."""
    n = np.asarray(normal, float)
    n /= np.linalg.norm(n)
    u_ = np.asarray(up, float)
    u_ = u_ - n * np.dot(u_, n)
    u_ /= np.linalg.norm(u_)
    # right as seen by a viewer looking along -n (Unity left-handed): right = cross(up, viewdir) with viewdir = -n
    # Unity camera: right = Cross(up, forward) evaluated numerically (Camera default: Cross(+Y, +Z) = +X).
    # The viewer of this quad looks along -n, so its screen-right is cross(up, -n).
    right = np.cross(u_, -n)
    c = np.asarray(center, float)
    V = np.array([c - right * w / 2 - u_ * h / 2, c + right * w / 2 - u_ * h / 2, c + right * w / 2 + u_ * h / 2, c - right * w / 2 + u_ * h / 2])
    UV = np.array([[0, 0], [1, 0], [1, 1], [0, 1]], float)
    if uv_flip_u:
        UV[:, 0] = 1 - UV[:, 0]
    N = np.tile(n, (4, 1))
    m = orient_outward(Mesh(V, N, np.array([[0, 1, 2], [0, 2, 3]]), UV))
    return m


def sphere(r, center=(0, 0, 0), segments=24, rings=16, scale=(1, 1, 1)) -> Mesh:
    prof = [(r * math.sin(a), -r * math.cos(a)) for a in np.linspace(0, math.pi, rings + 1)]
    m = lathe(prof, segments, cap=False)
    if scale != (1, 1, 1):
        m = m.transformed(s=scale)
    return m.transformed(t=center)


# ----------------------------------------------------------------------------------------------- SDF toolkit
def sd_capsule(P, a, b, ra, rb=None):
    a = np.asarray(a, float)
    b = np.asarray(b, float)
    rb = ra if rb is None else rb
    ba = b - a
    pa = P - a
    h = np.clip((pa @ ba) / (ba @ ba), 0, 1)
    d = np.linalg.norm(pa - h[..., None] * ba, axis=-1)
    return d - (ra + (rb - ra) * h)


def sd_ellipsoid(P, c, r, R=None):
    Q = P - np.asarray(c, float)
    if R is not None:
        Q = Q @ R  # world -> local (R columns are local axes)
    r = np.asarray(r, float)
    k0 = np.linalg.norm(Q / r, axis=-1)
    k1 = np.linalg.norm(Q / (r * r), axis=-1)
    return k0 * (k0 - 1.0) / (k1 + 1e-12)


def sd_round_box(P, c, size, radius, R=None):
    Q = P - np.asarray(c, float)
    if R is not None:
        Q = Q @ R
    h = np.asarray(size, float) / 2 - radius
    q = np.abs(Q) - h
    return np.linalg.norm(np.maximum(q, 0), axis=-1) + np.minimum(np.max(q, axis=-1), 0) - radius


def sd_plane(P, n, d):
    return P @ np.asarray(n, float) - d


def smin(a, b, k):
    if k <= 0:
        return np.minimum(a, b)
    h = np.maximum(k - np.abs(a - b), 0) / k
    return np.minimum(a, b) - h * h * k * 0.25


def smax(a, b, k):
    return -smin(-a, -b, k)


def sdf_mesh(fn, lo, hi, voxel, pad=2) -> Mesh:
    """Marching cubes on fn(P) over the box [lo, hi]; normals from the SDF gradient (smooth, seam-free)."""
    lo = np.asarray(lo, float) - pad * voxel
    hi = np.asarray(hi, float) + pad * voxel
    shape = np.ceil((hi - lo) / voxel).astype(int) + 1
    axes = [lo[i] + np.arange(shape[i]) * voxel for i in range(3)]
    G = np.stack(np.meshgrid(*axes, indexing="ij"), -1)
    D = np.empty(tuple(shape), np.float32)
    # evaluate in slabs to bound memory
    step = max(1, int(2_000_000 // (shape[1] * shape[2])))
    for i in range(0, shape[0], step):
        D[i:i + step] = fn(G[i:i + step].reshape(-1, 3)).reshape(G[i:i + step].shape[:3])
    del G
    if D.min() >= 0 or D.max() <= 0:
        raise ValueError("SDF has no surface in the sampled box")
    verts, faces, _, _ = marching_cubes(D, level=0.0, spacing=(voxel, voxel, voxel))
    V = verts + lo
    e = voxel * 0.5
    gx = fn(V + [e, 0, 0]) - fn(V - [e, 0, 0])
    gy = fn(V + [0, e, 0]) - fn(V - [0, e, 0])
    gz = fn(V + [0, 0, e]) - fn(V - [0, 0, e])
    N = np.stack([gx, gy, gz], 1)
    N /= np.linalg.norm(N, axis=1, keepdims=True) + 1e-12
    return orient_outward(Mesh(V, N, faces.astype(np.int64)))


def relax(m: Mesh, fn, iterations=2):
    """Project vertices back onto the zero level set (one Newton step each) for a cleaner surface."""
    V = m.V.copy()
    for _ in range(iterations):
        d = fn(V)
        e = 1e-4
        g = np.stack([(fn(V + [e, 0, 0]) - fn(V - [e, 0, 0])), (fn(V + [0, e, 0]) - fn(V - [0, e, 0])), (fn(V + [0, 0, e]) - fn(V - [0, 0, e]))], 1) / (2 * e)
        gn = np.linalg.norm(g, axis=1, keepdims=True) + 1e-12
        V = V - (d[:, None] * g / gn**2)
    return Mesh(V, m.N, m.F, m.UV)


def decimate_grid(m: Mesh, cell):
    """Very small vertex-clustering decimation (used only for far-away props)."""
    key = np.floor(m.V / cell).astype(np.int64)
    _, inv, counts = np.unique(key, axis=0, return_inverse=True, return_counts=True)
    inv = inv.ravel()
    k = counts.size
    V = np.zeros((k, 3))
    N = np.zeros((k, 3))
    np.add.at(V, inv, m.V)
    np.add.at(N, inv, m.N)
    V /= counts[:, None]
    N /= np.linalg.norm(N, axis=1, keepdims=True) + 1e-12
    F = inv[m.F]
    ok = (F[:, 0] != F[:, 1]) & (F[:, 1] != F[:, 2]) & (F[:, 0] != F[:, 2])
    return orient_outward(Mesh(V, N, F[ok]))
