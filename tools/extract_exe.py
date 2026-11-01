"""Maintenance tool: list display-like UTF-16 strings in the game exe that are not yet in
data/zh_exe.json (e.g. after a game update). Writes data/untranslated_exe.json.

The game module's literals sit in one cluster of .rdata; we locate it from strings that are
already translated, then keep sentence-like strings that are NOT used as identifiers
anywhere in the game's assets (FName tables) or config files - patching an identifier
could break input bindings or lookups.

python extract_exe.py            (uses the original exe backup if the exe is patched)
"""
import hashlib, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build import find_game, ROOT, PAK_REL, BASE_PAK
from pakfile import PakReader
from exepatch import EXE_REL, BACKUP, STATE, rdata_range, boundary_ok
from idents import identifiers

PAT = re.compile(rb'(?:[\x20-\x7e]\x00|\x0a\x00|\x0d\x00|\x09\x00){2,}\x00\x00')
ENGINE = re.compile(r'Oculus|OVRPlugin|Swapchain|WebM|Analyzer|SteamVR|OpenXR')
CODE = re.compile(r'::|\(\)|\.cpp|\bUsage:|[A-Za-z0-9_]=|=%|%f|\b[a-z]+\.[a-z]+\.[A-Za-z]|[A-Za-z]/[A-Za-z]|\\\\|/Game/|/Script/')




def main():
    game = find_game(sys.argv[1] if len(sys.argv) > 1 else None)
    exe = os.path.join(game, EXE_REL)
    b = open(exe, 'rb').read()
    st = exe + STATE
    if os.path.exists(st) and os.path.exists(exe + BACKUP):
        # the exe is our patched copy -> analyse the clean original instead
        if hashlib.sha1(b).hexdigest() == json.load(open(st, encoding='utf-8')).get('patched'):
            b = open(exe + BACKUP, 'rb').read()
    known = json.load(open(os.path.join(ROOT, 'data', 'zh_exe.json'), encoding='utf-8'))
    offs = [b.find(b'\0\0' + k.encode('utf-16-le') + b'\0\0') for k in list(known)[:400] if ' ' in k]
    offs = sorted(o for o in offs if o > 0)
    # the game module's literals form one cluster; stay inside the span of strings we already
    # know (engine/plugin literals sit right next to it and must not be touched)
    lo, hi = offs[len(offs) // 100], offs[-len(offs) // 100 - 1] + 50_000
    rlo, rhi = rdata_range(b); lo, hi = max(lo, rlo), min(hi, rhi)
    ids = identifiers(PakReader(os.path.join(game, PAK_REL, BASE_PAK)))
    out = []
    for m in PAT.finditer(b, lo, hi):
        # a literal right after an 8-bit string makes the match start a char or two early
        start = next((p for p in range(m.start(), m.start() + 4) if boundary_ok(b, p)), None)
        if start is None or start >= m.end() - 4:
            continue
        s = b[start:m.end() - 2].decode('utf-16-le')
        if s in known or s in ids or ' ' not in s.strip() or not re.search(r'[A-Za-z]{2,}', s) or CODE.search(s) \
                or ENGINE.search(s):
            continue
        out.append(s)
    out = list(dict.fromkeys(out))
    json.dump(out, open(os.path.join(ROOT, 'data', 'untranslated_exe.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=0)
    print('exe 中未翻译的候选文本: %d 条 -> data/untranslated_exe.json' % len(out))


if __name__ == '__main__':
    main()
