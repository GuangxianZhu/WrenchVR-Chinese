"""Maintenance tool: list display-like UTF-16 strings in the game exe that are not yet in
data/zh_exe.json (e.g. after a game update). Writes data/untranslated_exe.json.

The game module's literals sit in one cluster of .rdata; we locate it from strings that are
already translated, then keep sentence-like strings that are NOT used as identifiers
anywhere in the game's assets (FName tables) or config files - patching an identifier
could break input bindings or lookups.

python extract_exe.py            (uses the original exe backup if the exe is patched)
"""
import json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build import find_game, ROOT, PAK_REL, BASE_PAK
from pakfile import PakReader
from uasset import Summary
from exepatch import EXE_REL, BACKUP, rdata_range

PAT = re.compile(rb'(?:[\x20-\x7e]\x00|\x0a\x00|\x0d\x00|\x09\x00){2,}\x00\x00')
CODE = re.compile(r'::|\(\)|\.cpp|\bUsage:|[A-Za-z0-9_]=|=%|%f|\b[a-z]+\.[a-z]+\.[A-Za-z]|[A-Za-z]/[A-Za-z]|\\\\|/Game/|/Script/')


def identifiers(pak):
    ids = set()
    for p in pak.files:
        if p.endswith(('.uasset', '.umap')):
            try:
                ids.update(n for n, _ in Summary(pak.read(p)).names)
            except Exception:
                pass
        elif p.endswith('.ini'):
            t = pak.read(p).decode('utf-8', 'replace')
            ids.update(re.findall(r'"([^"]+)"', t)); ids.update(re.findall(r'=([^=\r\n,()"]+)', t))
    return {x.strip() for x in ids}


def main():
    game = find_game(sys.argv[1] if len(sys.argv) > 1 else None)
    exe = os.path.join(game, EXE_REL)
    if os.path.exists(exe + BACKUP):
        exe = exe + BACKUP
    b = open(exe, 'rb').read()
    known = json.load(open(os.path.join(ROOT, 'data', 'zh_exe.json'), encoding='utf-8'))
    offs = [b.find(b'\0\0' + k.encode('utf-16-le') + b'\0\0') for k in list(known)[:400] if ' ' in k]
    offs = sorted(o for o in offs if o > 0)
    lo, hi = offs[len(offs) // 50] - 200_000, offs[-len(offs) // 50 - 1] + 200_000
    rlo, rhi = rdata_range(b); lo, hi = max(lo, rlo), min(hi, rhi)
    ids = identifiers(PakReader(os.path.join(game, PAK_REL, BASE_PAK)))
    out = []
    for m in PAT.finditer(b, lo, hi):
        if m.start() % 2 or b[m.start() - 2:m.start()] != b'\0\0':
            continue
        s = m.group()[:-2].decode('utf-16-le')
        if s in known or s in ids or ' ' not in s.strip() or not re.search(r'[A-Za-z]{2,}', s) or CODE.search(s):
            continue
        out.append(s)
    out = list(dict.fromkeys(out))
    json.dump(out, open(os.path.join(ROOT, 'data', 'untranslated_exe.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=0)
    print('exe 中未翻译的候选文本: %d 条 -> data/untranslated_exe.json' % len(out))


if __name__ == '__main__':
    main()
