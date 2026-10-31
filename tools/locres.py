"""Write/read UE4 .locres files (legacy format: no hashes needed for keys)."""
import struct, zlib
from pakfile import fstr, _rstr


def source_hash(s):
    # FTextLocalizationResource::HashString == FCrc::StrCrc32 (each char as 4 bytes)
    return zlib.crc32(s.encode('utf-32-le')) & 0xFFFFFFFF


def write_locres(entries):
    """entries: iterable of (namespace, key, source, translation) -> bytes."""
    tree = {}
    for ns, key, src, tr in entries:
        tree.setdefault(ns, []).append((key, source_hash(src), tr))
    out = bytearray(struct.pack('<I', len(tree)))
    for ns, keys in tree.items():
        out += fstr(ns) + struct.pack('<I', len(keys))
        for key, h, tr in keys:
            out += fstr(key) + struct.pack('<I', h) + fstr(tr)
    return bytes(out)


def read_locres_legacy(b):
    o = 0; res = {}
    n, = struct.unpack_from('<I', b, o); o += 4
    for _ in range(n):
        ns, o = _rstr(b, o)
        k, = struct.unpack_from('<I', b, o); o += 4
        for _ in range(k):
            key, o = _rstr(b, o)
            h, = struct.unpack_from('<I', b, o); o += 4
            tr, o = _rstr(b, o)
            res[(ns, key)] = (h, tr)
    assert o == len(b)
    return res
