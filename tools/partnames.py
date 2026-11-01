"""Part names shown when you point at a part (and in its context menu) come from the part
blueprint's `PartName`, an FName property - so a .locres cannot reach them, just like the
tablet app labels. For every part package we append the Chinese name to its name map and
repoint only the PartName values; every other use of the same English name (component
variables, part paths, symptoms, ...) keeps pointing at the original entry. The modified
copies ship inside the patch pak; the game's own files are never touched."""
import struct
from uasset import Summary, append_names

# PartName values that have no PartData text to borrow a translation from
EXTRA = {'Workbench Bolt': '工作台螺栓', 'Workbench Box': '工作台包装箱', 'Workbench Box Top': '工作台包装箱盖',
         'Workbench Bracket': '工作台支架', 'Workbench Cross Brace': '工作台横撑', 'Workbench Foot': '工作台脚垫',
         'Workbench Leg': '工作台桌腿', 'Workbench Packaging Foam': '工作台包装泡沫', 'Workbench Top': '工作台台面'}


def _sites(x, ix, prop):
    tag = struct.pack('<iiiiiiB', ix[prop], 0, ix['NameProperty'], 0, 8, 0, 0)
    out = []; i = x.find(tag)
    while i >= 0:
        out.append(i + len(tag)); i = x.find(tag, i + 1)
    return out


def build_part_names(pak, zh, files=None):
    """Return ({path: bytes}, n_packages, n_values, untranslated_names).
    `files` holds already-modified packages (e.g. TextRender fixes) to build on."""
    files = files or {}
    out = {}; n_vals = 0; missing = set()
    for f in pak.files:
        if not f.endswith('.uasset'):
            continue
        stem = f[:-7]
        a = files.get(f) or pak.read(f)
        if b'PartName' not in a:
            continue
        s = Summary(a)
        N = [n for n, _ in s.names]; ix = {n: i for i, n in enumerate(N)}
        if 'PartName' not in ix or 'NameProperty' not in ix or stem + '.uexp' not in pak.files:
            continue
        x = bytearray(files.get(stem + '.uexp') or pak.read(stem + '.uexp'))
        sites = []
        for pos in _sites(x, ix, 'PartName'):
            vi, num = struct.unpack_from('<ii', x, pos)
            if 0 <= vi < len(N) and N[vi] != 'None':
                tr = zh.get(N[vi]) or EXTRA.get(N[vi])
                if tr and tr != N[vi]:
                    sites.append((pos, N[vi], tr))
                elif not tr:
                    missing.add(N[vi])
        if not sites:
            continue
        new = list(dict.fromkeys(tr for _, _, tr in sites if tr not in ix))
        a2, newix = append_names(a, new) if new else (a, {})
        for pos, _, tr in sites:
            struct.pack_into('<i', x, pos, newix.get(tr, ix.get(tr)))
        s2 = Summary(a2)
        assert [n for n, _ in s2.names[:s.NameCount]] == N
        assert s2.exports[0][2] == s2.TotalHeaderSize
        assert sum(e[1] for e in s2.exports) == len(x) - 4, f
        out[f] = a2; out[stem + '.uexp'] = bytes(x); n_vals += len(sites)
    return out, len(out) // 2, n_vals, sorted(missing)
