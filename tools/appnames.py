"""Tablet app labels are FName properties (DisplayName) in WrenchOSAppConfigs, which a
.locres cannot reach. We append Chinese names to that package's name map and repoint only
the DisplayName values (NameId etc. keep their original names), then ship the modified
copy inside the patch pak. The original game files are never touched."""
import struct
from uasset import Summary, append_names

ASSET = 'WrenchGame/Content/Blueprints/UI/WrenchOS/WrenchOSAppConfigs'
FALLBACK = {'Garage': '车库', 'Classifieds': '二手车广告', 'Job Board': '任务板', 'Manual': '维修手册',
            'Logbook': '日志本', 'Race Monitor': '比赛监控', 'Lift': '举升机', 'Inspector': '检查',
            'Catalog': '商品目录', 'Inventory': '库存', 'Scanner Wars': '扫描仪大战', 'Tutorial': '教程',
            'Settings': '设置', 'Roadmap': '路线图', "What's New": '更新内容', 'Credits': '制作人员'}


def build_app_names(pak):
    a = pak.read(ASSET + '.uasset'); x = bytearray(pak.read(ASSET + '.uexp'))
    s = Summary(a)
    N = [n for n, _ in s.names]; ix = {n: i for i, n in enumerate(N)}
    dn = [n for n in N if n.startswith('DisplayName_')]
    if len(dn) != 1 or 'NameProperty' not in ix:
        raise RuntimeError('WrenchOSAppConfigs layout changed')
    tag = struct.pack('<iiiiiiB', ix[dn[0]], 0, ix['NameProperty'], 0, 8, 0, 0)
    sites = []; i = x.find(tag)
    while i >= 0:
        v, num = struct.unpack_from('<ii', x, i + len(tag))
        sites.append((i + len(tag), N[v])); i = x.find(tag, i + 1)
    wanted = [n for _, n in sites if n in FALLBACK]
    new_names = list(dict.fromkeys(FALLBACK[n] for n in wanted))
    a2, newix = append_names(a, new_names)
    changed = 0
    for pos, name in sites:
        if name in FALLBACK:
            struct.pack_into('<i', x, pos, newix[FALLBACK[name]]); changed += 1
    # sanity: re-parse and check export map still matches the uexp
    s2 = Summary(a2)
    assert s2.NameCount == s.NameCount + len(new_names)
    assert s2.exports[0][2] == s2.TotalHeaderSize
    assert sum(e[1] for e in s2.exports) == len(x) - 4
    assert [n for n, _ in s2.names[:s.NameCount]] == N
    return {ASSET + '.uasset': a2, ASSET + '.uexp': bytes(x)}, changed
