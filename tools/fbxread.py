"""Read mesh parts of a binary FBX into metres (FBX axes): {name: (V (n,3), F (m,3))}. Uses cad/tools/fbxio.py."""
import numpy as np
import fbxio


def load(path):
    d = fbxio.read(str(path))
    top = {n.name: n for n in d['top']}
    objs = top['Objects']; byid = {o.props[0][1]: o for o in objs.kids}
    us = [p.props[4][1] for p in top['GlobalSettings'].get('Properties70').kids if p.props[0][1] == b'UnitScaleFactor'][0] / 100.0
    oo = [(c.props[1][1], c.props[2][1]) for c in top['Connections'].kids]
    out = {}
    for m in [o for o in objs.kids if o.name == 'Model' and o.props[2][1] == b'Mesh']:
        mid = m.props[0][1]
        g = [byid[c] for c, p in oo if p == mid and c in byid and byid[c].name == 'Geometry'][0]
        sc = 1.0
        for pp in m.get('Properties70').kids:
            if pp.props[0][1] == b'Lcl Scaling': sc = pp.props[4][1]
        V = np.array(g.get('Vertices').props[0][1]).reshape(-1, 3) * sc * us
        F, cur = [], []
        for i in g.get('PolygonVertexIndex').props[0][1]:
            if i < 0:
                cur.append(-i - 1); F += [[cur[0], cur[k], cur[k + 1]] for k in range(1, len(cur) - 1)]; cur = []
            else:
                cur.append(i)
        out[m.props[1][1].split(b'\0')[0].decode()] = (V, np.array(F))
    return out
