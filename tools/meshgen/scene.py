"""Scene collector and binary bundle writer (read by Assets/Editor/NeramSceneBuilder.cs).

Bundle layout (little endian):
  char[4] "NRMB", int32 version (=1)
  int32 nodeCount; per node: str name, str parent ("" = scene root), float3 position, float4 rotation (x,y,z,w),
                    str region, str flags
  int32 meshCount; per mesh: str name, str parent node, str material, float3 pivot (world),
                    int32 vertexCount, int32 indexCount, float3[v] positions (relative to pivot, world axes),
                    float3[v] normals, float2[v] uv, uint32[i] indices
  str = int32 byte length + UTF-8 bytes.
Mesh GameObjects are placed at the pivot with WORLD rotation identity, so vertex data never needs re-orientation.
"""
from __future__ import annotations

import hashlib
import struct
from pathlib import Path

import numpy as np

from geom import Mesh, box_uv


def quat_from_matrix(Rm):
    Rm = np.asarray(Rm, float)
    t = np.trace(Rm)
    if t > 0:
        s = np.sqrt(t + 1.0) * 2
        w = 0.25 * s
        x = (Rm[2, 1] - Rm[1, 2]) / s
        y = (Rm[0, 2] - Rm[2, 0]) / s
        z = (Rm[1, 0] - Rm[0, 1]) / s
    elif Rm[0, 0] > Rm[1, 1] and Rm[0, 0] > Rm[2, 2]:
        s = np.sqrt(1.0 + Rm[0, 0] - Rm[1, 1] - Rm[2, 2]) * 2
        w = (Rm[2, 1] - Rm[1, 2]) / s
        x = 0.25 * s
        y = (Rm[0, 1] + Rm[1, 0]) / s
        z = (Rm[0, 2] + Rm[2, 0]) / s
    elif Rm[1, 1] > Rm[2, 2]:
        s = np.sqrt(1.0 + Rm[1, 1] - Rm[0, 0] - Rm[2, 2]) * 2
        w = (Rm[0, 2] - Rm[2, 0]) / s
        x = (Rm[0, 1] + Rm[1, 0]) / s
        y = 0.25 * s
        z = (Rm[1, 2] + Rm[2, 1]) / s
    else:
        s = np.sqrt(1.0 + Rm[2, 2] - Rm[0, 0] - Rm[1, 1]) * 2
        w = (Rm[1, 0] - Rm[0, 1]) / s
        x = (Rm[0, 2] + Rm[2, 0]) / s
        y = (Rm[1, 2] + Rm[2, 1]) / s
        z = 0.25 * s
    q = np.array([x, y, z, w])
    return q / np.linalg.norm(q)


class SceneOut:
    def __init__(self):
        self.nodes = []
        self.meshes = []
        self._names = set()

    def node(self, name, parent="", pos=(0, 0, 0), R=None, region="", flags=""):
        assert name not in self._names, "duplicate node " + name
        self._names.add(name)
        q = quat_from_matrix(R) if R is not None else np.array([0, 0, 0, 1.0])
        self.nodes.append(dict(name=name, parent=parent, pos=np.asarray(pos, float), q=q, region=region, flags=flags))
        return name

    def add(self, parent, name, mesh: Mesh, material, pivot=None):
        if mesh is None or len(mesh.F) == 0:
            return
        base, k = name, 1
        while name in self._names:
            k += 1
            name = f"{base}_{k}"
        self._names.add(name)
        if pivot is None:
            lo, hi = mesh.V.min(0), mesh.V.max(0)
            pivot = (lo + hi) / 2
        self.meshes.append(dict(name=name, parent=parent, material=material, pivot=np.asarray(pivot, float), mesh=mesh))
        return name

    def materials(self):
        return sorted({m["material"] for m in self.meshes})

    def stats(self):
        tris = sum(len(m["mesh"].F) for m in self.meshes)
        verts = sum(len(m["mesh"].V) for m in self.meshes)
        return dict(nodes=len(self.nodes), meshes=len(self.meshes), triangles=int(tris), vertices=int(verts))

    def write(self, path: Path):
        def s(b, text):
            data = text.encode("utf-8")
            b.append(struct.pack("<i", len(data)))
            b.append(data)
        out = [b"NRMB", struct.pack("<i", 1), struct.pack("<i", len(self.nodes))]
        for n in self.nodes:
            s(out, n["name"])
            s(out, n["parent"])
            out.append(struct.pack("<3f", *n["pos"]))
            out.append(struct.pack("<4f", *n["q"]))
            s(out, n["region"])
            s(out, n["flags"])
        out.append(struct.pack("<i", len(self.meshes)))
        for m in self.meshes:
            me: Mesh = m["mesh"]
            uv = me.UV if me.UV is not None else box_uv(me.V, me.N)
            V = (me.V - m["pivot"]).astype("<f4")
            N = me.N.astype("<f4")
            F = me.F.astype("<u4").ravel()
            s(out, m["name"])
            s(out, m["parent"])
            s(out, m["material"])
            out.append(struct.pack("<3f", *m["pivot"]))
            out.append(struct.pack("<ii", len(V), len(F)))
            out.append(V.tobytes())
            out.append(N.tobytes())
            out.append(uv.astype("<f4").tobytes())
            out.append(F.tobytes())
        data = b"".join(out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return hashlib.sha256(data).hexdigest(), len(data)


def read_bundle(path: Path):
    """Independent reader (used by the verification script to check the file round-trips)."""
    data = path.read_bytes()
    o = 0

    def i32():
        nonlocal o
        v = struct.unpack_from("<i", data, o)[0]
        o += 4
        return v

    def st():
        nonlocal o
        n = i32()
        v = data[o:o + n].decode("utf-8")
        o += n
        return v

    def f(n):
        nonlocal o
        v = struct.unpack_from(f"<{n}f", data, o)
        o += 4 * n
        return v

    assert data[:4] == b"NRMB"
    o = 4
    ver = i32()
    nodes = []
    for _ in range(i32()):
        nodes.append(dict(name=st(), parent=st(), pos=f(3), q=f(4), region=st(), flags=st()))
    meshes = []
    for _ in range(i32()):
        name, parent, mat = st(), st(), st()
        piv = f(3)
        nv, ni = i32(), i32()
        V = np.frombuffer(data, "<f4", nv * 3, o).reshape(-1, 3); o += nv * 12
        N = np.frombuffer(data, "<f4", nv * 3, o).reshape(-1, 3); o += nv * 12
        UV = np.frombuffer(data, "<f4", nv * 2, o).reshape(-1, 2); o += nv * 8
        I = np.frombuffer(data, "<u4", ni, o); o += ni * 4
        meshes.append(dict(name=name, parent=parent, material=mat, pivot=piv, V=V, N=N, UV=UV, I=I))
    assert o == len(data), "trailing bytes"
    return ver, nodes, meshes
