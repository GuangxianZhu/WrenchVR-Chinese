"""UE4 pak (v10/v11) reader + minimal uncompressed v11 writer. Pure stdlib."""
import struct, hashlib, os

MAGIC = 0x5A6F12E1
M64 = (1 << 64) - 1


def _rstr(b, o):
    n, = struct.unpack_from('<i', b, o); o += 4
    if n == 0:
        return '', o
    if n < 0:
        return b[o:o - 2 * n].decode('utf-16-le')[:-1], o - 2 * n
    return b[o:o + n].decode('utf-8', 'replace')[:-1], o + n


def fstr(s):
    """Serialize an FString (ANSI when possible, else UTF-16)."""
    if s == '':
        return struct.pack('<i', 0)
    try:
        raw = s.encode('ascii') + b'\0'
        return struct.pack('<i', len(raw)) + raw
    except UnicodeEncodeError:
        raw = s.encode('utf-16-le') + b'\0\0'
        return struct.pack('<i', -(len(raw) // 2)) + raw


class PakReader:
    def __init__(self, path):
        self.f = open(path, 'rb')
        size = os.path.getsize(path)
        self.f.seek(size - 221)
        foot = self.f.read(221)
        magic, ver, ioff, isz = struct.unpack_from('<IiqQ', foot, 17)
        if magic != MAGIC or ver < 10:
            raise ValueError('unsupported pak (magic/version %x/%d)' % (magic, ver))
        self.version = ver
        self.f.seek(ioff)
        idx = self.f.read(isz)
        o = 0
        self.mount, o = _rstr(idx, o)
        self.count, self.seed = struct.unpack_from('<iQ', idx, o); o += 12
        hp, = struct.unpack_from('<I', idx, o); o += 4
        if hp:
            o += 36
        hf, = struct.unpack_from('<I', idx, o); o += 4
        if not hf:
            raise ValueError('pak has no full directory index')
        fo, fs = struct.unpack_from('<qq', idx, o); o += 36
        es, = struct.unpack_from('<i', idx, o); o += 4
        self.enc = idx[o:o + es]
        self.f.seek(fo)
        d = self.f.read(fs)
        self.files = {}
        o = 0
        nd, = struct.unpack_from('<i', d, o); o += 4
        for _ in range(nd):
            dn, o = _rstr(d, o)
            nf, = struct.unpack_from('<i', d, o); o += 4
            for _ in range(nf):
                fn, o = _rstr(d, o)
                loc, = struct.unpack_from('<i', d, o); o += 4
                self.files[(dn + fn).lstrip('/')] = loc

    def entry(self, path):
        loc = self.files[path]
        if loc < 0:
            raise NotImplementedError('non-encoded entry')
        e = self.enc
        v, = struct.unpack_from('<I', e, loc); p = loc + 4
        if (v & 0x3f) == 0x3f:
            p += 4
        if v >> 31:
            off, = struct.unpack_from('<I', e, p); p += 4
        else:
            off, = struct.unpack_from('<q', e, p); p += 8
        if (v >> 30) & 1:
            us, = struct.unpack_from('<I', e, p); p += 4
        else:
            us, = struct.unpack_from('<q', e, p); p += 8
        return off, us, (v >> 23) & 0x3f, (v >> 22) & 1

    def read(self, path):
        off, us, cm, enc = self.entry(path)
        if cm or enc:
            raise NotImplementedError('compressed/encrypted entry: ' + path)
        self.f.seek(off + 53)  # serialized FPakEntry header of an uncompressed entry
        return self.f.read(us)


def fnv64_path(path, seed):
    h = (0xcbf29ce484222325 + seed) & M64
    for c in path.lower().encode('utf-16-le'):
        h ^= c
        h = (h * 0x100000001b3) & M64
    return h


def write_pak(out_path, files, mount='../../../', seed=0x5A5A1234):
    """files: {relative/path: bytes}. Writes an uncompressed, unencrypted v11 pak."""
    data = bytearray(); enc = bytearray(); locs = {}
    for rel in sorted(files):
        b = files[rel]
        off = len(data)
        hdr = struct.pack('<qqqI', 0, len(b), len(b), 0) + hashlib.sha1(b).digest() + struct.pack('<BI', 0, 0)
        data += hdr + b
        locs[rel] = len(enc)
        enc += struct.pack('<III', 0xE0000000, off, len(b))
    dirs = {'/': []}
    for rel in sorted(files):
        parts = rel.split('/')
        for i in range(1, len(parts)):
            dirs.setdefault('/'.join(parts[:i]) + '/', [])
        d = '/'.join(parts[:-1]) + '/' if len(parts) > 1 else '/'
        dirs[d].append((parts[-1], locs[rel]))
    fdi = struct.pack('<i', len(dirs))
    for d, fl in dirs.items():
        fdi += fstr(d) + struct.pack('<i', len(fl))
        for fn, loc in fl:
            fdi += fstr(fn) + struct.pack('<i', loc)
    phi = struct.pack('<i', len(files))
    for rel in sorted(files):
        phi += struct.pack('<Qi', fnv64_path(rel, seed), locs[rel])
    phi += fdi  # pruned directory index (keep everything)
    index_offset = len(data)

    def primary(phi_off, fdi_off):
        return (fstr(mount) + struct.pack('<iQ', len(files), seed)
                + struct.pack('<IqQ', 1, phi_off, len(phi)) + hashlib.sha1(phi).digest()
                + struct.pack('<IqQ', 1, fdi_off, len(fdi)) + hashlib.sha1(fdi).digest()
                + struct.pack('<i', len(enc)) + bytes(enc) + struct.pack('<i', 0))
    psize = len(primary(0, 0))
    phi_off = index_offset + psize
    fdi_off = phi_off + len(phi)
    prim = primary(phi_off, fdi_off)
    footer = (b'\0' * 16 + b'\0' + struct.pack('<IiqQ', MAGIC, 11, index_offset, len(prim))
              + hashlib.sha1(prim).digest() + b'\0' * 160)
    with open(out_path, 'wb') as f:
        f.write(bytes(data) + prim + phi + fdi + footer)
