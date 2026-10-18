"""Helpers for gen_cad_fit.py (Sai, 2026-10-18, v2): anatomical hands from the glove outline, fabric drape of the
pads, and straps rebuilt as bands that follow the limb. All coordinates are the CAD root's Unity-local frame
(x lateral, y away from the skin, z along the pad: fingers / toes at +z) unless stated."""
import numpy as np
from scipy import ndimage
from skimage.morphology import medial_axis
from skimage import measure


def skeleton_blobs(mask, gx, gz, res, step=0.0022, rmin=0.0035):
    """Medial axis of a 2D mask -> blob centres (x, z) and radii r (metres), thinned to ~step spacing."""
    sk, dist = medial_axis(mask, return_distance=True)
    ii, jj = np.nonzero(sk)
    r = dist[ii, jj] * res
    x, z = gx[ii], gz[jj]
    keep = r >= rmin
    x, z, r = x[keep], z[keep], r[keep]
    key = np.round(np.stack([x, z], 1) / step).astype(int)
    order = np.argsort(-r)                                    # keep the biggest blob per cell
    _, first = np.unique(key[order], axis=0, return_index=True)
    sel = order[first]
    return x[sel], z[sel], r[sel]


def blobs_sdf(L, bx, bz, br, ry_of_r, yc_of_r, k=0.0035, chunk=12000):
    """Smooth union of ellipsoids (rx = r, ry = ry_of_r(r), rz = r) at (bx, yc, bz); L (..., 3) local points."""
    shp = L.shape[:-1]; P = L.reshape(-1, 3); out = np.empty(len(P))
    ry = ry_of_r(br); yc = yc_of_r(br)
    for a in range(0, len(P), chunk):
        q = P[a:a + chunk]
        dx = (q[:, None, 0] - bx[None]) / br[None]; dy = (q[:, None, 1] - yc[None]) / ry[None]; dz = (q[:, None, 2] - bz[None]) / br[None]
        d = (np.sqrt(dx * dx + dy * dy + dz * dz) - 1.0) * np.minimum(br, ry)[None]
        m = d.min(1)
        out[a:a + chunk] = m - k * np.log(np.exp(-(d - m[:, None]) / k).sum(1))
    return out.reshape(shp)


def blobs_top(xg, zg, bx, bz, br, ry_of_r, yc_of_r):
    """Exact top surface y(x, z) of the (hard) union of the ellipsoids; NaN where no blob covers."""
    X, Z = np.meshgrid(xg, zg, indexing="ij")
    top = np.full(X.shape, -np.inf)
    ry = ry_of_r(br); yc = yc_of_r(br)
    for x0, z0, r, h, c in zip(bx, bz, br, ry, yc):
        q = 1 - ((X - x0) ** 2 + (Z - z0) ** 2) / (r * r)
        ok = q > 0
        top[ok] = np.maximum(top[ok], c + h * np.sqrt(q[ok]))
    top[~np.isfinite(top)] = np.nan
    return top


def fill_smooth(H, sigma_px):
    """Fill NaNs with the nearest valid value, then Gaussian-smooth."""
    bad = np.isnan(H)
    if bad.any():
        idx = ndimage.distance_transform_edt(bad, return_distances=False, return_indices=True)
        H = H[tuple(idx)]
    return ndimage.gaussian_filter(H, sigma_px)


def sample_grid(H, x0, z0, step, x, z):
    i = np.clip((np.asarray(x) - x0) / step, 0, H.shape[0] - 1.001)
    j = np.clip((np.asarray(z) - z0) / step, 0, H.shape[1] - 1.001)
    return ndimage.map_coordinates(H, [np.ravel(i), np.ravel(j)], order=1, mode="nearest").reshape(np.shape(x))


def section_loop(inside_fn, z0, z1, xlim, ylim, gap=0.0006, res=0.0004, n=120, zs=7, smooth=2.5):
    """Closed CCW loop (n,2) in (x, y) around the union of cross-sections over z in [z0, z1], offset by gap."""
    xs = np.arange(xlim[0], xlim[1], res); ys = np.arange(ylim[0], ylim[1], res)
    X, Y = np.meshgrid(xs, ys, indexing="ij")
    m = np.zeros(X.shape, bool)
    for z in np.linspace(z0, z1, zs):
        m |= inside_fn(X, Y, np.full_like(X, z))
    m = ndimage.binary_closing(m, iterations=3)
    lab, nl = ndimage.label(m)
    if nl > 1:
        sizes = ndimage.sum(m, lab, range(1, nl + 1)); m = lab == (1 + int(np.argmax(sizes)))
    D = ndimage.distance_transform_edt(~m) * res - ndimage.distance_transform_edt(m) * res
    D = ndimage.gaussian_filter(D, smooth)
    c = max(measure.find_contours(D, gap), key=len)
    pts = np.stack([xlim[0] + c[:, 0] * res, ylim[0] + c[:, 1] * res], 1)
    if np.linalg.norm(pts[0] - pts[-1]) < 1e-9: pts = pts[:-1]
    seg = np.r_[0, np.cumsum(np.linalg.norm(np.diff(np.vstack([pts, pts[:1]]), axis=0), axis=1))]
    t = np.linspace(0, seg[-1], n, endpoint=False)
    pts = np.stack([np.interp(t, seg, np.r_[pts[:, 0], pts[0, 0]]), np.interp(t, seg, np.r_[pts[:, 1], pts[0, 1]])], 1)
    area = 0.5 * np.sum(pts[:, 0] * np.roll(pts[:, 1], -1) - np.roll(pts[:, 0], -1) * pts[:, 1])
    if area < 0: pts = pts[::-1]
    return pts


def loop_normals(pts, closed=True):
    if closed:
        tang = np.roll(pts, -1, 0) - np.roll(pts, 1, 0)
    else:
        tang = np.gradient(pts, axis=0)
    tang /= np.linalg.norm(tang, axis=1, keepdims=True)
    return np.stack([tang[:, 1], -tang[:, 0]], 1)


def sweep(pts, nrm, z0, z1, thick, closed=True):
    """Solid band of thickness `thick` outward from the polyline pts (n,2) over z in [z0, z1]."""
    n = len(pts); inner, outer = pts, pts + nrm * thick
    V, N, F = [], [], []

    def ring(p2, z, nn3):
        base = len(V)
        for (x, y), nv in zip(p2, nn3): V.append((x, y, z)); N.append(nv)
        return base
    n2 = np.c_[nrm[:, 0], nrm[:, 1], np.zeros(n)]
    oA = ring(outer, z0, n2); oB = ring(outer, z1, n2); iA = ring(inner, z0, -n2); iB = ring(inner, z1, -n2)
    eA_o = ring(outer, z0, np.tile([0, 0, -1.0], (n, 1))); eA_i = ring(inner, z0, np.tile([0, 0, -1.0], (n, 1)))
    eB_o = ring(outer, z1, np.tile([0, 0, 1.0], (n, 1))); eB_i = ring(inner, z1, np.tile([0, 0, 1.0], (n, 1)))
    m = n if closed else n - 1

    def strip(a, b):
        for i in range(m):
            j = (i + 1) % n
            F.append((a + i, a + j, b + j)); F.append((a + i, b + j, b + i))
    strip(oA, oB); strip(iB, iA); strip(eA_i, eA_o); strip(eB_o, eB_i)
    if not closed:                                            # end caps
        for k in (0, n - 1):
            q = [oA + k, oB + k, iB + k, iA + k]
            F.append((q[0], q[1], q[2])); F.append((q[0], q[2], q[3]))
            for v in q: N[v] = N[v]
    V = np.array(V); N = np.array(N); F = np.array(F)
    fn = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    cen = V.mean(0)
    ref = N[F].sum(1)
    if not closed:
        caps = np.zeros(len(F), bool); caps[-4:] = True
        ref[caps] = (V[F[caps]].mean(1) - cen)
    flip = np.einsum("ij,ij->i", fn, ref) < 0
    F[flip] = F[flip][:, ::-1]
    return V, N, F


def band(inside_fn, z0, z1, xlim, ylim, thick=0.0015, **kw):
    """Strap band hugging the limb section. Returns V, N, F (root-local) and the loop (for the hook patch)."""
    pts = section_loop(inside_fn, z0, z1, xlim, ylim, **kw)
    nrm = loop_normals(pts)
    V, N, F = sweep(pts, nrm, z0, z1, thick)
    return V, N, F, (pts, nrm)


def hook_patch(loop, z0, z1, length, band_thick=0.0015, thick=0.0012, where="bottom"):
    """Hook-and-loop closure patch lying on the band's outer surface, centred at the band's lowest point."""
    pts, nrm = loop
    n = len(pts)
    c = int(np.argmin(pts[:, 1])) if where == "bottom" else int(np.argmax(pts[:, 1]))
    seg = np.linalg.norm(np.roll(pts, -1, 0) - pts, axis=1)
    idx = [c]; acc = 0.0; k = c
    while acc < length / 2: k = (k + 1) % n; acc += seg[k]; idx.append(k)
    acc = 0.0; k = c
    while acc < length / 2: k = (k - 1) % n; acc += seg[k]; idx.insert(0, k)
    sub = pts[idx] + nrm[idx] * (band_thick + 0.0001)
    return sweep(sub, nrm[idx], z0 + 0.001, z1 - 0.001, thick, closed=False)


def skin_top(sdf_local, xg, zg, sdf2, y_lo, y_hi, dy=0.0003, margin=0.003):
    """Highest y where sdf_local(x, y, z) < 0 for each (x, z) column of the pad footprint (NaN where none)."""
    X, Z = np.meshgrid(xg, zg, indexing="ij")
    use = sdf2(X, Z) < margin
    ys = np.arange(y_hi, y_lo, -dy)
    xs, zs = X[use], Z[use]
    found = np.full(len(xs), np.nan)
    for y in ys:                                              # scan downwards; first hit = top surface
        todo = np.isnan(found)
        if not todo.any(): break
        L = np.stack([xs[todo], np.full(todo.sum(), y), zs[todo]], -1)
        hit = sdf_local(L) < 0
        idx = np.nonzero(todo)[0][hit]
        found[idx] = y
    out = np.full(X.shape, np.nan); out[use] = found
    return out


def subdivide(V, F, maxlen=0.004, iters=8, need=None):
    """Conforming edge-split subdivision until no edge is longer than maxlen (winding preserved)."""
    V = [tuple(v) for v in np.asarray(V, float)]; F = [tuple(f) for f in np.asarray(F, int)]
    for _ in range(iters):
        P = np.array(V)
        mids = {}

        def mid(a, b):
            k = (a, b) if a < b else (b, a)
            if k not in mids:
                mids[k] = len(V); V.append(tuple((P[a] + P[b]) / 2))
            return mids[k]
        def long_(a, b):
            L = np.linalg.norm(P[a] - P[b])
            if L <= maxlen: return False
            return need is None or L > 0.02 or need(P[a], P[b])
        newF, changed = [], False
        for a, b, c in F:
            s = (long_(a, b), long_(b, c), long_(c, a))
            n = sum(s)
            if n == 0: newF.append((a, b, c)); continue
            changed = True
            if n == 3:
                ab, bc, ca = mid(a, b), mid(b, c), mid(c, a)
                newF += [(a, ab, ca), (ab, b, bc), (ca, bc, c), (ab, bc, ca)]
            elif n == 1:
                if s[0]: m = mid(a, b); newF += [(a, m, c), (m, b, c)]
                elif s[1]: m = mid(b, c); newF += [(a, b, m), (a, m, c)]
                else: m = mid(c, a); newF += [(a, b, m), (m, b, c)]
            else:
                # rotate so the unsplit edge is (c, a): splits on (a, b) and (b, c)
                if not s[2]: x, y, z = a, b, c
                elif not s[0]: x, y, z = b, c, a
                else: x, y, z = c, a, b
                m1, m2 = mid(x, y), mid(y, z)
                newF += [(m1, y, m2), (x, m1, m2), (x, m2, z)]
        F = newF
        if not changed: break
    return np.array(V), np.array(F)


def corner_normals(V, F, crease_deg=40.0):
    """Unwelded mesh (3 vertices per triangle) with angle-weighted smooth normals split at creases."""
    V = np.asarray(V, float); F = np.asarray(F, int)
    e1 = V[F[:, 1]] - V[F[:, 0]]; e2 = V[F[:, 2]] - V[F[:, 0]]
    fn = np.cross(e1, e2); fa = np.linalg.norm(fn, axis=1); fn = fn / np.maximum(fa, 1e-20)[:, None]
    vf = [[] for _ in range(len(V))]
    for i, f in enumerate(F):
        for v in f: vf[v].append(i)
    c = np.cos(np.radians(crease_deg))
    outV, outN = V[F].reshape(-1, 3), np.zeros((len(F) * 3, 3))
    for i, f in enumerate(F):
        for k, v in enumerate(f):
            adj = [j for j in vf[v] if fn[j] @ fn[i] >= c]
            n = (fn[adj] * fa[adj, None]).sum(0)
            outN[3 * i + k] = n / max(np.linalg.norm(n), 1e-20)
    return outV, outN, np.arange(len(F) * 3).reshape(-1, 3)
