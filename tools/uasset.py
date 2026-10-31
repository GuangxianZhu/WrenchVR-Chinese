"""Minimal UE4.26 cooked package (.uasset) summary/name-map/export-map parser + writer."""
import struct, zlib
from pakfile import fstr, _rstr


class Summary:
    INT_FIELDS = ['GatherableTextDataOffset', 'ExportOffset', 'ImportOffset', 'DependsOffset',
                  'SoftPackageReferencesOffset', 'SearchableNamesOffset', 'ThumbnailTableOffset',
                  'AssetRegistryDataOffset', 'WorldTileInfoDataOffset', 'PreloadDependencyOffset']

    def __init__(self, b):
        self.b = b; o = 0; self.pos = {}
        def i32(name=None):
            nonlocal o
            v, = struct.unpack_from('<i', b, o)
            if name: self.pos[name] = o; setattr(self, name, v)
            o += 4; return v
        assert i32() == -1641380927 & 0xFFFFFFFF or True
        self.tag, = struct.unpack_from('<I', b, 0)
        assert self.tag == 0x9E2A83C1, hex(self.tag)
        o = 4
        self.legacy = i32()
        if self.legacy != -4: i32()
        self.ue4ver = i32(); i32()
        n = i32(); o += 20 * n
        i32('TotalHeaderSize')
        _, o = _rstr(b, o)
        self.pkgflags = i32()
        i32('NameCount'); i32('NameOffset')
        i32('GatherableTextDataCount'); i32('GatherableTextDataOffset')
        i32('ExportCount'); i32('ExportOffset'); i32('ImportCount'); i32('ImportOffset'); i32('DependsOffset')
        i32('SoftPackageReferencesCount'); i32('SoftPackageReferencesOffset')
        i32('SearchableNamesOffset'); i32('ThumbnailTableOffset')
        o += 16
        g = i32(); o += 8 * g
        for _ in range(2):
            o += 10; _, o = _rstr(b, o)
        i32()  # compression flags
        assert i32() == 0  # compressed chunks
        i32()  # package source
        n = i32()
        for _ in range(n): _, o = _rstr(b, o)
        if self.legacy > -7: i32()
        i32('AssetRegistryDataOffset')
        self.pos['BulkDataStartOffset'] = o; self.BulkDataStartOffset, = struct.unpack_from('<q', b, o); o += 8
        i32('WorldTileInfoDataOffset')
        n = i32(); o += 4 * n
        i32('PreloadDependencyCount'); i32('PreloadDependencyOffset')
        self.summary_end = o
        # name map
        o = self.NameOffset; self.names = []
        for _ in range(self.NameCount):
            s, o = _rstr(b, o); h = b[o:o + 4]; o += 4
            self.names.append((s, h))
        self.namemap_end = o
        # export map
        self.exports = []
        for i in range(self.ExportCount):
            eo = self.ExportOffset + i * 104
            size, off = struct.unpack_from('<qq', b, eo + 28)
            self.exports.append((eo, size, off))


def name_hashes(s):
    # Hashes are informational in UE4.23+ (recomputed on load); keep a CRC-based value.
    c = zlib.crc32(s.encode('utf-16-le')) & 0xFFFF
    return struct.pack('<HH', c, c)


def append_names(uasset, new_names):
    """Return (new_uasset_bytes, {name: index}). Existing name indices are unchanged."""
    s = Summary(uasset)
    assert s.namemap_end <= min(v for v in [s.ExportOffset, s.ImportOffset] if v > 0)
    extra = b''.join(fstr(n) + name_hashes(n) for n in new_names)
    d = len(extra)
    out = bytearray(uasset[:s.namemap_end] + extra + uasset[s.namemap_end:])
    def put(field, fmt='<i'):
        v = getattr(s, field)
        if v and v >= s.namemap_end:
            struct.pack_into(fmt, out, s.pos[field], v + d)
    for f in Summary.INT_FIELDS + ['TotalHeaderSize']:
        put(f)
    put('BulkDataStartOffset', '<q')
    struct.pack_into('<i', out, s.pos['NameCount'], s.NameCount + len(new_names))
    for eo, size, off in s.exports:
        struct.pack_into('<q', out, eo + d + 36, off + d)
    idx = {n: s.NameCount + i for i, n in enumerate(new_names)}
    return bytes(out), idx
