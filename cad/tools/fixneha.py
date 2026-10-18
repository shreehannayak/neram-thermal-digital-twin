"""Sai's Unity-prep of Neharika's Fusion FBX exports (plan section V/W). Geometry shape is not changed except
controller decimation; every change is listed in the report the script prints."""
import copy, json, sys
import numpy as np
import fbxio, qem

SRC = sys.argv[2] if len(sys.argv) > 2 else 'cad/exports/source_fusion_2026-10-18/'
OUT = sys.argv[1]
CM_TO_M = 0.01


def nm(n): return n.props[1][1].split(b'\0')[0].decode()
def setname(n, s, cls): n.props[1][1] = s.encode() + b'\x00\x01' + cls


def rot(v):  # Z-up design -> Y-up: (x, y, z) -> (x, z, -y)
    return np.stack([v[:, 0], v[:, 2], -v[:, 1]], 1)


def p70(n):
    return n.get('Properties70')


def set_p(node, key, vals):
    for p in p70(node).kids:
        if p.props[0][1] == key.encode():
            p.props[4:] = [['D', float(x)] for x in vals]; return
    tpl = {'Lcl Scaling': [b'Lcl Scaling', b'', b'A']}
    p70(node).kids.append(fbxio.Node('P', [['S', key.encode()]] + [['S', s] for s in tpl[key]] + [['D', float(x)] for x in vals]))


def material_role(obj):
    o = obj
    if o.startswith('BC_'):
        if o in ('BC_Enclosure', 'BC_Front_Panel', 'BC_Rail_Clamp'): return 'MAT_Enclosure'
        if o.startswith('BC_LED_'): return 'MAT_Indicator'
        if o == 'BC_Display': return 'MAT_Display'
        if o.startswith('BC_Button_'): return 'MAT_' + o[3:]           # MAT_Button_Start / _Stop / _Reset
        if o.startswith('BC_Port_') or o in ('BC_Mains_Inlet', 'BC_Power_Switch'): return 'MAT_Connector'
        if o.endswith('_Placeholder'): return 'MAT_Placeholder'
    if o.startswith('Watch_'):
        return {'Watch_Case': 'MAT_Enclosure', 'Watch_Clasp': 'MAT_Enclosure', 'Watch_Display': 'MAT_Display',
                'Watch_Strap': 'MAT_Strap'}[o]
    part = o.split('_', 1)[1]
    for key, mat in (('Liner', 'MAT_Liner'), ('Heater', 'MAT_Heater'), ('Insulation', 'MAT_Insulation'),
                     ('Shell', 'MAT_Shell'), ('Strap', 'MAT_Strap'), ('Hook', 'MAT_Strap'), ('Sensor', 'MAT_Sensor')):
        if part.startswith(key): return mat
    raise KeyError(o)


def mesh_tris(g):
    idx = g.get('PolygonVertexIndex').props[0][1]
    F, cur = [], []
    for i in idx:
        if i < 0: cur.append(-i - 1); F += [[cur[0], cur[k], cur[k + 1]] for k in range(1, len(cur) - 1)]; cur = []
        else: cur.append(i)
    return F


def smooth_normals(V, F, crease_deg=30):
    V = np.asarray(V); F = np.asarray(F)
    fn = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    fn /= np.maximum(np.linalg.norm(fn, axis=1, keepdims=True), 1e-20)
    vfaces = [[] for _ in V]
    for i, f in enumerate(F):
        for v in f: vfaces[v].append(i)
    c = np.cos(np.radians(crease_deg)); out = []
    for i, f in enumerate(F):
        for v in f:
            acc = sum((fn[j] for j in vfaces[v] if fn[j].dot(fn[i]) >= c), np.zeros(3))
            out.append(acc / max(np.linalg.norm(acc), 1e-20))
    return np.array(out)


def process(src_file, groups, report):
    """groups: list of (out_file, root_name, object_prefix_or_None, pivot_fn, tri_targets)"""
    for out_file, root_name, prefix, pivot, targets in groups:
        d = fbxio.read(SRC + src_file)
        top = {n.name: n for n in d['top']}
        objs, cons = top['Objects'], top['Connections']
        byid = {o.props[0][1]: o for o in objs.kids}
        links = [[c.props[0][1], c.props[1][1], c.props[2][1]] for c in cons.kids]
        oo = [l for l in links if l[0] == b'OO']
        rep = {'file': out_file, 'source': src_file, 'changes': []}
        # --- globals: metres
        for p in p70(top['GlobalSettings']).kids:
            if p.props[0][1] in (b'UnitScaleFactor', b'OriginalUnitScaleFactor'): p.props[4] = ['D', 100.0]
        rep['changes'].append('units: file now in metres (UnitScaleFactor 100); vertex data converted cm->m; per-part x10 transform scale removed')
        # --- pick objects
        models = [o for o in objs.kids if o.name == 'Model']
        root = [m for m in models if m.props[2][1] == b'Null'][0]
        keep_models = [m for m in models if m is not root and (prefix is None or nm(m).strip().startswith(prefix))]
        mesh_of = {}
        for c, child, parent in oo:
            if child in byid and byid[child].name == 'Geometry' and parent in byid: mesh_of[parent] = child
        # --- geometry: rename, rotate, convert, pivot, decimate
        allv = {}
        for m in keep_models:
            g = byid[mesh_of[m.props[0][1]]]
            allv[nm(m).strip()] = np.array(g.get('Vertices').props[0][1]).reshape(-1, 3)
        piv = pivot(allv)
        tris_total = 0
        for m in keep_models:
            old = nm(m); new = old.strip()
            if old != new: rep['changes'].append('renamed %r -> %r (trailing space)' % (old, new))
            setname(m, new, b'Model'); set_p(m, 'Lcl Scaling', (1, 1, 1))
            g = byid[mesh_of[m.props[0][1]]]; setname(g, new, b'Geometry')
            V = (rot(allv[new] - piv)) * CM_TO_M
            F = mesh_tris(g)
            tgt = targets.get(new)
            if tgt and len(F) > tgt:
                n0 = len(F); V, F = qem.decimate(V, F, tgt)
                rep['changes'].append('%s decimated %d -> %d triangles (runtime copy; plan V.5)' % (new, n0, len(F)))
                g.kids = [k for k in g.kids if k.name not in ('LayerElementUV',)]
                lay = g.get('Layer'); lay.kids = [k for k in lay.kids if not (k.name == 'LayerElement' and k.get('Type').props[0][1] == b'LayerElementUV')]
                nrm = smooth_normals(V, F)
            else:
                nrm = None
            g.get('Vertices').props[0][1] = [float(x) for x in np.asarray(V).ravel()]
            pvi = []
            for f in F: pvi += [int(f[0]), int(f[1]), -int(f[2]) - 1]
            g.get('PolygonVertexIndex').props[0][1] = pvi
            g.kids = [k for k in g.kids if k.name != 'Edges']
            for le in g.all('LayerElementNormal') + g.all('LayerElementBinormal') + g.all('LayerElementTangent'):
                for k in le.kids:
                    if k.name in ('Normals', 'Binormals', 'Tangents'):
                        if nrm is not None and k.name == 'Normals':
                            k.props[0][1] = [float(x) for x in nrm.ravel()]
                        elif nrm is None:
                            a = np.array(k.props[0][1]).reshape(-1, 3); k.props[0][1] = [float(x) for x in rot(a).ravel()]
                    if k.name in ('NormalsW',) and nrm is not None: k.props[0][1] = [1.0] * len(F) * 3
            for le in g.all('LayerElementMaterial'):
                le.get('MappingInformationType').props[0][1] = b'AllSame'
                le.get('Materials').props[0][1] = [0]
            tris_total += len(F)
        rep['triangles'] = tris_total
        rep['changes'].append('axes: Z-up design rotated to Y-up (+Y away from skin for modules); pivot = %s' % pivot.__doc__)
        # --- materials: one per function
        next_id = [max(byid) + 1]
        def nid(): next_id[0] += 1; return next_id[0]
        src_mats = {o.props[0][1]: o for o in objs.kids if o.name == 'Material'}
        func = {}
        new_links = []
        for m in keep_models:
            mid = m.props[0][1]; role = material_role(nm(m))
            mine = [ch for c, ch, par in oo if par == mid and ch in src_mats]
            if role not in func:
                mat = copy.deepcopy(src_mats[mine[0]]); mat.props[0][1] = nid(); setname(mat, role, b'Material')
                col = (1.0, 0.0, 1.0) if role == 'MAT_Placeholder' else None
                srcname = nm(src_mats[mine[0]])
                dif = [p.props[4:7] for p in p70(src_mats[mine[0]]).kids if p.props[0][1] == b'DiffuseColor'][0]
                if col is None and sum(x[1] for x in dif) < 0.01:   # Fusion texture-only appearance exports black
                    for word, c in (('Light Brown', (0.76, 0.62, 0.46)), ('Grey', (0.55, 0.55, 0.57)), ('Black', (0.10, 0.10, 0.11))):
                        if word in srcname: col = c; rep['changes'].append('%s: "%s" exported with no flat colour -> flat %s from its appearance name' % (role, srcname, c)); break
                if col:
                    for p in p70(mat).kids:
                        if p.props[0][1] in (b'DiffuseColor', b'Diffuse'): p.props[4:] = [['D', c] for c in col]
                func[role] = mat
                if role == 'MAT_Placeholder': rep['changes'].append('MAT_Placeholder = magenta (plan placeholder convention)')
                elif not col: rep['changes'].append('%s <- colour of "%s"' % (role, srcname))
            new_links.append([b'OO', func[role].props[0][1], mid])
        # --- new root
        newroot = copy.deepcopy(root); newroot.props[0][1] = nid(); setname(newroot, root_name, b'Model')
        attr_ids = [ch for c, ch, par in oo if par == root.props[0][1] and byid.get(ch) is not None and byid[ch].name == 'NodeAttribute']
        attr = copy.deepcopy(byid[attr_ids[0]]); attr.props[0][1] = nid(); setname(attr, root_name, b'NodeAttribute')
        rep['changes'].append('root %r -> %r%s' % (nm(root), root_name, '' if prefix is None else ' (only %s* parts; pair split into one file per module, plan V.1)' % prefix))
        # --- rebuild objects + connections
        keep_ids = {m.props[0][1] for m in keep_models} | {mesh_of[m.props[0][1]] for m in keep_models}
        objs.kids = [o for o in objs.kids if o.props[0][1] in keep_ids] + [attr, newroot] + list(func.values())
        conn = [[b'OO', newroot.props[0][1], 0], [b'OO', attr.props[0][1], newroot.props[0][1]]]
        conn += [[b'OO', m.props[0][1], newroot.props[0][1]] for m in keep_models]
        conn += [[b'OO', mesh_of[m.props[0][1]], m.props[0][1]] for m in keep_models]
        conn += new_links
        cons.kids = [fbxio.Node('C', [['S', a], ['L', b], ['L', c]]) for a, b, c in conn]
        # --- definitions counts
        counts = {}
        for o in objs.kids: counts[o.name] = counts.get(o.name, 0) + 1
        tot = 1
        for ot in top['Definitions'].all('ObjectType'):
            k = ot.props[0][1].decode()
            if k in counts: ot.get('Count').props[0][1] = counts[k]
            tot += ot.get('Count').props[0][1] if k != 'GlobalSettings' else 0
        top['Definitions'].get('Count').props[0][1] = sum(ot.get('Count').props[0][1] for ot in top['Definitions'].all('ObjectType'))
        fbxio.write(d, OUT + '/' + out_file)
        rep['materials'] = sorted(func)
        report.append(rep)


def liner_pivot(prefix):
    def f(allv):
        v = allv[prefix + '_Liner']
        c = (v.min(0) + v.max(0)) / 2; c[2] = v[:, 2].min(); return c
    f.__doc__ = 'centroid of the %s_Liner skin-contact face' % prefix
    return f


def clamp_pivot(allv):
    """centre of BC_Rail_Clamp"""
    v = allv['BC_Rail_Clamp']; return (v.min(0) + v.max(0)) / 2


def watch_pivot(allv):
    """centre of the watch case underside (skin side)"""
    v = allv['Watch_Case']; c = (v.min(0) + v.max(0)) / 2; c[2] = v[:, 2].min(); return c


report = []
process('NERAM_CH1_Hand_Module.fbx', [
    ('NERAM_Left_Hand_Module.fbx', 'Left_Hand_Module', 'CH1_', liner_pivot('CH1'), {}),
    ('NERAM_Right_Hand_Module.fbx', 'Right_Hand_Module', 'CH2_', liner_pivot('CH2'), {})], report)
process('NERAM_CH3_Foot_Module.fbx', [
    ('NERAM_Left_Foot_Module.fbx', 'Left_Foot_Module', 'CH3_', liner_pivot('CH3'), {}),
    ('NERAM_Right_Foot_Module.fbx', 'Right_Foot_Module', 'CH4_', liner_pivot('CH4'), {})], report)
process('NERAM_Bedside_Controller.fbx', [
    ('NERAM_Bedside_Controller.fbx', 'Bedside_Controller', None, clamp_pivot, {'BC_Enclosure': 5200, 'BC_Front_Panel': 3200})], report)
process('NERAM_Watch_Concept.fbx', [
    ('NERAM_Watch_Concept.fbx', 'Watch_Concept', None, watch_pivot, {})], report)
json.dump(report, open(OUT + '/report.json', 'w'), indent=1)
for r in report: print(r['file'], r['triangles'], r['materials'])
