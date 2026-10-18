"""Lossless binary FBX (7.x) reader/writer. Nodes keep typed properties so files round-trip."""
import struct, zlib

ARR = {'f': 'f', 'd': 'd', 'l': 'q', 'i': 'i', 'b': 'b'}


class Node:
    __slots__ = ('name', 'props', 'kids')

    def __init__(self, name, props=None, kids=None):
        self.name, self.props, self.kids = name, props or [], kids or []

    def get(self, name):
        for k in self.kids:
            if k.name == name:
                return k

    def all(self, name):
        return [k for k in self.kids if k.name == name]

    def __repr__(self):
        return 'Node(%s,%r)' % (self.name, [p[1] if p[0] not in ARR else '[..]' for p in self.props][:3])


def _props(b, o, n):
    out = []
    for _ in range(n):
        t = chr(b[o]); o += 1
        if t == 'Y': v = struct.unpack_from('<h', b, o)[0]; o += 2
        elif t == 'C': v = b[o]; o += 1
        elif t == 'I': v = struct.unpack_from('<i', b, o)[0]; o += 4
        elif t == 'F': v = struct.unpack_from('<f', b, o)[0]; o += 4
        elif t == 'D': v = struct.unpack_from('<d', b, o)[0]; o += 8
        elif t == 'L': v = struct.unpack_from('<q', b, o)[0]; o += 8
        elif t in ARR:
            ln, enc, clen = struct.unpack_from('<III', b, o); o += 12
            raw = b[o:o + clen]; o += clen
            if enc == 1: raw = zlib.decompress(raw)
            v = list(struct.unpack('<%d%s' % (ln, ARR[t]), raw[:ln * struct.calcsize(ARR[t])]))
        elif t in 'SR':
            ln = struct.unpack_from('<I', b, o)[0]; o += 4
            v = bytes(b[o:o + ln]); o += ln
        else:
            raise ValueError(t)
        out.append([t, v])
    return out, o


def _node(b, o, v64):
    if v64: end, n, plen = struct.unpack_from('<QQQ', b, o); o += 24
    else: end, n, plen = struct.unpack_from('<III', b, o); o += 12
    nl = b[o]; o += 1
    if end == 0: return None, o
    name = b[o:o + nl].decode(); o += nl
    props, o = _props(b, o, n)
    kids = []
    sent = 25 if v64 else 13
    while o < end:
        if end - o == sent and b[o:end] == b'\0' * sent: o = end; break
        k, o = _node(b, o, v64)
        if k is None: break
        kids.append(k)
    return Node(name, props, kids), end


def read(path):
    b = open(path, 'rb').read()
    ver = struct.unpack_from('<I', b, 23)[0]
    v64 = ver >= 7500
    o, top = 27, []
    while True:
        n, o2 = _node(b, o, v64)
        if n is None: break
        top.append(n); o = o2
    footer = b[o:]  # null record + footer bytes, copied verbatim
    return {'ver': ver, 'head': b[:27], 'top': top, 'footer': footer, 'endnull': b[o - (25 if v64 else 13):o]}


def _wprops(props):
    out = bytearray()
    for t, v in props:
        out += t.encode()
        if t == 'Y': out += struct.pack('<h', v)
        elif t == 'C': out += bytes([v])
        elif t == 'I': out += struct.pack('<i', v)
        elif t == 'F': out += struct.pack('<f', v)
        elif t == 'D': out += struct.pack('<d', v)
        elif t == 'L': out += struct.pack('<q', v)
        elif t in ARR:
            raw = struct.pack('<%d%s' % (len(v), ARR[t]), *v)
            comp = zlib.compress(raw)
            out += struct.pack('<III', len(v), 1, len(comp)) + comp
        elif t in 'SR':
            out += struct.pack('<I', len(v)) + v
    return bytes(out)


def _wnode(n, off, v64):
    hl = 25 if v64 else 13
    pb = _wprops(n.props)
    nb = n.name.encode()
    body_off = off + hl + len(nb) + len(pb)
    kids = bytearray()
    if n.kids:
        for k in n.kids:
            kids += _wnode(k, body_off + len(kids), v64)
        kids += b'\0' * hl
    elif not n.props:
        kids += b'\0' * hl  # empty nodes still carry a null record
    end = body_off + len(kids)
    if v64: h = struct.pack('<QQQ', end, len(n.props), len(pb))
    else: h = struct.pack('<III', end, len(n.props), len(pb))
    return h + bytes([len(nb)]) + nb + pb + bytes(kids)


def write(doc, path):
    v64 = doc['ver'] >= 7500
    out = bytearray(doc['head'])
    for n in doc['top']:
        out += _wnode(n, len(out), v64)
    f = doc['footer']
    vi = f.find(struct.pack('<I', doc['ver']), 29)
    out += f[:29]
    z = (4 - len(out)) % 16
    if z < 4: z += 16
    out += b'\0' * z + f[vi:]
    open(path, 'wb').write(bytes(out))
