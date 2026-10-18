"""Offline software preview (numpy sample-splat rasterizer with z-buffer). It is a geometry check only: it does not
reproduce URP lighting, shadows, post-processing or the UI, and it is NOT a Unity screenshot."""
from __future__ import annotations

import math

import numpy as np
from PIL import Image

# Approximate base colours of the URP materials (mirrors NeramSetup.MaterialSpec; preview only)
PREVIEW_COLORS = {}


def unity_camera(pivot, yaw, pitch, dist):
    y, p = math.radians(yaw), math.radians(pitch)
    fwd = np.array([math.sin(y) * math.cos(p), -math.sin(p), math.cos(y) * math.cos(p)])
    right = np.array([math.cos(y), 0.0, -math.sin(y)])
    up = np.array([math.sin(y) * math.sin(p), math.cos(p), math.cos(y) * math.sin(p)])
    eye = np.asarray(pivot, float) - fwd * dist
    return eye, fwd, right, up


def render(items, cam, size=(1600, 900), fov=40.0, bg=(14, 17, 22), samples_per_px=7.0, lights=None, shift=(0.0, 0.0)):
    """items: list of (Mesh, rgb(0..1), emission rgb or None, alpha). cam: (eye, fwd, right, up)."""
    W, H = size
    eye, fwd, right, up = cam
    f = (H / 2) / math.tan(math.radians(fov) / 2)
    depth = np.full(W * H, np.inf, np.float32)
    color = np.zeros((W * H, 3), np.float32)
    color[:] = np.array(bg) / 255.0
    if lights is None:
        lights = [(np.array([0.35, 0.85, -0.4]), 0.75, np.array([1.0, 0.97, 0.92])), (np.array([-0.5, 0.6, 0.3]), 0.35, np.array([0.8, 0.88, 1.0]))]
    rng = np.random.default_rng(1)
    all_idx, all_d, all_c = [], [], []
    for item in items:
        m, rgb, emis, alpha = item[:4]
        texarr = item[4] if len(item) > 4 else None
        if m is None or len(m.F) == 0:
            continue
        rel = m.V - eye
        z = rel @ fwd
        x = rel @ right
        yv = rel @ up
        valid = z > 0.02
        sx = W / 2 + f * x / np.where(valid, z, 1) + shift[0] * W / 2
        sy = H / 2 - f * yv / np.where(valid, z, 1) - shift[1] * H / 2
        Fv = m.F[valid[m.F].all(axis=1)]
        if len(Fv) == 0:
            continue
        a, b, c = Fv[:, 0], Fv[:, 1], Fv[:, 2]
        # back-face culling (Unity culls back faces): face normal vs view vector
        fn = np.cross(m.V[b] - m.V[a], m.V[c] - m.V[a])
        view = m.V[a] - eye
        front = np.einsum("ij,ij->i", fn, view) < 0
        Fv = Fv[front]
        a, b, c = Fv[:, 0], Fv[:, 1], Fv[:, 2]
        area = 0.5 * np.abs((sx[b] - sx[a]) * (sy[c] - sy[a]) - (sx[c] - sx[a]) * (sy[b] - sy[a]))
        onscreen = (np.maximum.reduce([sx[a], sx[b], sx[c]]) >= 0) & (np.minimum.reduce([sx[a], sx[b], sx[c]]) < W) & \
                   (np.maximum.reduce([sy[a], sy[b], sy[c]]) >= 0) & (np.minimum.reduce([sy[a], sy[b], sy[c]]) < H)
        Fv, area = Fv[onscreen], area[onscreen]
        if len(Fv) == 0:
            continue
        n = np.minimum(np.ceil(area * samples_per_px).astype(int) + 3, 400000)
        tri = np.repeat(np.arange(len(Fv)), n)
        r1 = np.sqrt(rng.random(len(tri)))
        r2 = rng.random(len(tri))
        w0, w1, w2 = 1 - r1, r1 * (1 - r2), r1 * r2
        A, B, C = Fv[tri, 0], Fv[tri, 1], Fv[tri, 2]
        px = w0 * sx[A] + w1 * sx[B] + w2 * sx[C]
        py = w0 * sy[A] + w1 * sy[B] + w2 * sy[C]
        pz = w0 * z[A] + w1 * z[B] + w2 * z[C]
        N = w0[:, None] * m.N[A] + w1[:, None] * m.N[B] + w2[:, None] * m.N[C]
        N /= np.linalg.norm(N, axis=1, keepdims=True) + 1e-12
        P = w0[:, None] * m.V[A] + w1[:, None] * m.V[B] + w2[:, None] * m.V[C]
        V = eye - P
        V /= np.linalg.norm(V, axis=1, keepdims=True) + 1e-12
        base = rgb(P) if callable(rgb) else np.array(rgb, float)
        if texarr is not None and m.UV is not None:
            UVs = w0[:, None] * m.UV[A] + w1[:, None] * m.UV[B] + w2[:, None] * m.UV[C]
            th, tw = texarr.shape[:2]
            tu = np.clip((UVs[:, 0] % 1.0) * (tw - 1), 0, tw - 1).astype(int)
            tv = np.clip((1 - (UVs[:, 1] % 1.0)) * (th - 1), 0, th - 1).astype(int)
            base = texarr[tv, tu, :3] / 255.0
        shade = np.full((len(N), 3), 0.30) * np.array([0.85, 0.9, 1.0])
        spec = np.zeros(len(N))
        for (L, k, lc) in lights:
            L = L / np.linalg.norm(L)
            nd = np.clip(N @ L, 0, 1)
            shade += k * nd[:, None] * lc
            Hh = (L + V)
            Hh /= np.linalg.norm(Hh, axis=1, keepdims=True)
            spec += 0.18 * k * np.clip(np.einsum("ij,ij->i", N, Hh), 0, 1) ** 40
        col = base * shade + spec[:, None]
        if emis is not None:
            col = col + np.array(emis)
        ix = px.astype(int)
        iy = py.astype(int)
        ok = (ix >= 0) & (ix < W) & (iy >= 0) & (iy < H)
        all_idx.append((iy[ok] * W + ix[ok]))
        all_d.append(pz[ok].astype(np.float32))
        all_c.append(col[ok].astype(np.float32))
    if all_idx:
        idx = np.concatenate(all_idx)
        d = np.concatenate(all_d)
        c = np.concatenate(all_c)
        order = np.lexsort((d, idx))
        idx, d, c = idx[order], d[order], c[order]
        first = np.ones(len(idx), bool)
        first[1:] = idx[1:] != idx[:-1]
        color[idx[first]] = c[first]
        depth[idx[first]] = d[first]
    img = np.clip(color, 0, 1) ** (1 / 1.15)
    img = (img.reshape(H, W, 3) * 255).astype(np.uint8)
    return Image.fromarray(img), depth.reshape(H, W)


def fill_holes(img: Image.Image, depth):
    """Fill isolated background pixels inside surfaces (sample-splat artefacts) with a 3x3 median of neighbours."""
    a = np.asarray(img).astype(np.int16)
    holes = ~np.isfinite(depth)
    pad = np.pad(a, ((1, 1), (1, 1), (0, 0)), mode="edge")
    padh = np.pad(holes, 1, mode="edge")
    neigh_ok = np.zeros(holes.shape, int)
    acc = np.zeros(a.shape, np.int32)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            ok = ~padh[1 + dy:1 + dy + holes.shape[0], 1 + dx:1 + dx + holes.shape[1]]
            neigh_ok += ok
            acc += pad[1 + dy:1 + dy + a.shape[0], 1 + dx:1 + dx + a.shape[1]] * ok[..., None]
    fillable = holes & (neigh_ok >= 6)
    out = a.copy()
    out[fillable] = (acc[fillable] / neigh_ok[fillable][:, None]).astype(np.int16)
    return Image.fromarray(out.astype(np.uint8))
