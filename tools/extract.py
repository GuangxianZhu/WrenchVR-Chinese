"""Extract all localizable FText (namespace, key, source) from the game's pak."""
import re, struct, json, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pakfile import PakReader

KEY = re.compile(rb'\x21\x00\x00\x00([0-9A-F]{32})\x00')
# Blueprint bytecode: EX_TextConst(0x29) + LocalizedText(0x01) + 3 string consts (source, key, namespace)
KISMET = re.compile(rb'\x29\x01(?=[\x1f\x34])')
# FText with a human-readable key (e.g. DataTable rows: ns "IntroGameObjectDescriptions",
# key "Part_CAS_Description"): int8 history=0 | FString ns | FString key | FString source
NAMED = re.compile(rb'\x00([\x02-\x80])\x00\x00\x00([A-Za-z_][A-Za-z0-9_]*)\x00([\x02-\x80])\x00\x00\x00([A-Za-z0-9_][A-Za-z0-9_ .\-/]*)\x00')


def _kstr(b, p):
    """Read a Kismet EX_StringConst (0x1f, ANSI) or EX_UnicodeStringConst (0x34, UTF-16)."""
    if p >= len(b):
        return None, p
    if b[p] == 0x1f:
        e = b.find(b'\0', p + 1)
        if e < 0 or e - p > 20000:
            return None, p
        return b[p + 1:e].decode('latin1'), e + 1
    if b[p] == 0x34:
        q = p + 1
        while q + 1 < len(b) and b[q:q + 2] != b'\0\0':
            q += 2
        return b[p + 1:q].decode('utf-16-le', 'replace'), q + 2
    return None, p


def _fstr(b, p):
    n, = struct.unpack_from('<i', b, p)
    if 0 < n < 20000:
        raw = b[p + 4:p + 4 + n]
        return (raw[:-1].decode('latin1') if raw[-1:] == b'\0' else None)
    if -20000 < n < 0:
        raw = b[p + 4:p + 4 - 2 * n]
        return (raw[:-2].decode('utf-16-le', 'replace') if raw[-2:] == b'\0\0' else None)
    return '' if n == 0 else None


def _namespace(b, k):
    if k >= 5 and b[k - 4:k] == b'\0\0\0\0' and b[k - 5] == 0:
        return ''
    for n in range(1, 300):
        s = k - 4 - n
        if s < 1:
            break
        if struct.unpack_from('<i', b, s)[0] == n and b[k - 1] == 0 and b[s - 1] == 0:
            return b[s + 4:k - 1].decode('latin1')
    return None


def extract(pak_path):
    pak = PakReader(pak_path)
    found = {}; conflicts = 0
    for path in sorted(pak.files):
        if not (path.startswith('WrenchGame/Content') and path.endswith('.uexp')):
            continue
        try:
            b = pak.read(path)
        except NotImplementedError:
            continue
        for m in KEY.finditer(b):
            ns = _namespace(b, m.start())
            if ns is None:
                continue
            src = _fstr(b, m.end())
            if not src or not src.strip():
                continue
            k = (ns, m.group(1).decode())
            if k in found and found[k]['src'] != src:
                conflicts += 1
                continue
            found.setdefault(k, {'ns': ns, 'key': k[1], 'src': src, 'asset': path})
        for m in NAMED.finditer(b):
            ns, key = m.group(2).decode(), m.group(4).decode()
            if len(ns) + 1 != m.group(1)[0] or len(key) + 1 != m.group(3)[0]:
                continue
            if re.fullmatch(r'[0-9A-F]{32}', ns) or re.fullmatch(r'[0-9A-F]{32}', key):
                continue  # GUID-keyed texts are handled by KEY above
            src = _fstr(b, m.end())
            if not src or not re.search(r'[A-Za-z]{2,}', src):
                continue
            k = (ns, key)
            if k in found and found[k]['src'] != src:
                conflicts += 1
                continue
            found.setdefault(k, {'ns': ns, 'key': key, 'src': src, 'asset': path})
        for m in KISMET.finditer(b):
            src, q = _kstr(b, m.end())
            key, q = _kstr(b, q) if src is not None else (None, q)
            ns, q = _kstr(b, q) if key is not None else (None, q)
            if ns is None or not src or not src.strip() or not key or len(key) > 128:
                continue
            k = (ns, key)
            if k in found and found[k]['src'] != src:
                conflicts += 1
                continue
            found.setdefault(k, {'ns': ns, 'key': key, 'src': src, 'asset': path})
    return list(found.values()), conflicts


if __name__ == '__main__':
    pak_path, out = sys.argv[1], sys.argv[2]
    ents, conflicts = extract(pak_path)
    json.dump(ents, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    print('entries', len(ents), 'key conflicts', conflicts, 'unique sources', len({e['src'] for e in ents}))
