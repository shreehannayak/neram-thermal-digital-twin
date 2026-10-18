"""Minimal binary-FBX inspector: units, axes, models, meshes (tris, bbox), materials, parent links. Read-only."""
import struct, zlib, sys, json

def read_props(b, o, n):
    props = []
    for _ in range(n):
        t = chr(b[o]); o += 1
        if t == 'Y': v = struct.unpack_from('<h', b, o)[0]; o += 2
        elif t == 'C': v = bool(b[o]); o += 1
        elif t == 'I': v = struct.unpack_from('<i', b, o)[0]; o += 4
        elif t == 'F': v = struct.unpack_from('<f', b, o)[0]; o += 4
        elif t == 'D': v = struct.unpack_from('<d', b, o)[0]; o += 8
        elif t == 'L': v = struct.unpack_from('<q', b, o)[0]; o += 8
        elif t in 'fdlib':
            ln, enc, clen = struct.unpack_from('<III', b, o); o += 12
            raw = b[o:o + clen]; o += clen
            if enc == 1: raw = zlib.decompress(raw)
            fmt = {'f': 'f', 'd': 'd', 'l': 'q', 'i': 'i', 'b': 'b'}[t]
            v = list(struct.unpack('<%d%s' % (ln, fmt), raw[:ln * struct.calcsize(fmt)]))
        elif t in 'SR':
            ln = struct.unpack_from('<I', b, o)[0]; o += 4
            v = b[o:o + ln]; o += ln
            if t == 'S': v = v.decode('utf-8', 'replace')
        else: raise ValueError('prop type ' + t)
        props.append(v)
    return props, o

def read_node(b, o, v64):
    if v64:
        end, n, plen = struct.unpack_from('<QQQ', b, o); o += 24
    else:
        end, n, plen = struct.unpack_from('<III', b, o); o += 12
    nl = b[o]; o += 1
    if end == 0: return None, o
    name = b[o:o + nl].decode(); o += nl
    props, o = read_props(b, o, n)
    kids = []
    sentinel = 25 if v64 else 13
    while o < end:
        if end - o == sentinel and b[o:end] == b'\0' * sentinel: o = end; break
        k, o = read_node(b, o, v64)
        if k is None: break
        kids.append(k)
    return {'name': name, 'props': props, 'kids': kids}, end

def parse(path):
    b = open(path, 'rb').read()
    ver = struct.unpack_from('<I', b, 23)[0]; v64 = ver >= 7500
    o = 27; top = []
    while o < len(b) - 200:
        n, o2 = read_node(b, o, v64)
        if n is None: break
        top.append(n); o = o2
    return ver, top

def find(nodes, name): return [n for n in nodes if n['name'] == name]
def nm(s): return s.split('\x00\x01')[0] if isinstance(s, str) else s

def inspect(path):
    ver, top = parse(path)
    out = {'file': path.split('/')[-1], 'fbx_version': ver}
    hdr = find(top, 'FBXHeaderExtension')
    if hdr:
        for k in hdr[0]['kids']:
            if k['name'] == 'Creator': out['creator'] = k['props'][0]
    for c in find(top, 'Creator'): out['creator'] = c['props'][0]
    gs = find(top, 'GlobalSettings')
    if gs:
        for p70 in gs[0]['kids']:
            if p70['name'] == 'Properties70':
                for p in p70['kids']:
                    key = p['props'][0]
                    if key in ('UpAxis', 'UpAxisSign', 'FrontAxis', 'FrontAxisSign', 'CoordAxis', 'CoordAxisSign', 'UnitScaleFactor', 'OriginalUnitScaleFactor'):
                        out[key] = p['props'][-1]
    objs = find(top, 'Objects')[0]['kids']
    ids = {}
    models, geoms, mats = [], [], []
    for ob in objs:
        oid = ob['props'][0]; name = nm(ob['props'][1]); kind = ob['props'][2] if len(ob['props']) > 2 else ''
        ids[oid] = (ob['name'], name)
        if ob['name'] == 'Model':
            m = {'name': name, 'type': kind}
            for k in ob['kids']:
                if k['name'] == 'Properties70':
                    for p in k['kids']:
                        if p['props'][0] in ('Lcl Translation', 'Lcl Rotation', 'Lcl Scaling'):
                            m[p['props'][0]] = [round(x, 4) for x in p['props'][-3:]]
            models.append(m)
        elif ob['name'] == 'Geometry':
            g = {'name': name, 'id': oid}
            for k in ob['kids']:
                if k['name'] == 'Vertices':
                    v = k['props'][0]; g['verts'] = len(v) // 3
                    xs, ys, zs = v[0::3], v[1::3], v[2::3]
                    g['bbox'] = [round(max(xs) - min(xs), 4), round(max(ys) - min(ys), 4), round(max(zs) - min(zs), 4)]
                if k['name'] == 'PolygonVertexIndex':
                    idx = k['props'][0]; polys = 0; tris = 0; cnt = 0
                    for i in idx:
                        cnt += 1
                        if i < 0: polys += 1; tris += cnt - 2; cnt = 0
                    g['polys'] = polys; g['tris'] = tris
            geoms.append(g)
        elif ob['name'] == 'Material':
            mats.append(name)
    parents = {}
    con = find(top, 'Connections')
    if con:
        for c in con[0]['kids']:
            if c['props'][0] == 'OO':
                parents.setdefault(c['props'][2], []).append(c['props'][1])
    # model hierarchy (model -> model only)
    tree = {}
    for parent, chs in parents.items():
        if parent in ids and ids[parent][0] == 'Model':
            tree[ids[parent][1]] = [ids[c][1] for c in chs if c in ids and ids[c][0] == 'Model']
    roots = [m['name'] for m in models if not any(m['name'] in v for v in tree.values())]
    out.update({'models': models, 'geoms': geoms, 'materials': mats, 'tree': {k: v for k, v in tree.items() if v}, 'roots': roots,
                'total_tris': sum(g.get('tris', 0) for g in geoms)})
    return out

if __name__ == '__main__':
    for p in sys.argv[1:]:
        print(json.dumps(inspect(p), default=str)[:6000]); print()
