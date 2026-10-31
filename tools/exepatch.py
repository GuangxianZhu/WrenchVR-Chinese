"""Translate UTF-16 string literals hardcoded in the game exe, in place.

Why in place: C++ code refers to each literal by its address, so a translation must sit
at the same address. Chinese is shorter than English, so it fits; the rest is zero-padded
(the string simply ends earlier). Only complete, null-delimited literals inside the .rdata
section are replaced, and only strings listed in data/zh_exe.json.

Safety: the original exe is backed up next to it (*.zh_backup) and a small state file
remembers the hashes, so re-installing always patches from the clean original, and
uninstalling restores it. After a game update the new exe is detected as a fresh original.
"""
import hashlib, json, os, shutil, struct

EXE_REL = os.path.join('WindowsNoEditor', 'WrenchGame', 'Binaries', 'Win64', 'WrenchGame-Win64-Shipping.exe')
BACKUP = '.zh_backup'
STATE = '.zh_state.json'


def _sha1(b):
    return hashlib.sha1(b).hexdigest()


def _units(s):
    return len(s.encode('utf-16-le')) // 2


def rdata_range(b):
    pe, = struct.unpack_from('<I', b, 0x3C)
    assert b[pe:pe + 4] == b'PE\0\0', 'not a PE file'
    nsec, = struct.unpack_from('<H', b, pe + 6)
    opt, = struct.unpack_from('<H', b, pe + 20)
    sec = pe + 24 + opt
    for i in range(nsec):
        name = b[sec + 40 * i:sec + 40 * i + 8].rstrip(b'\0')
        size, ptr = struct.unpack_from('<II', b, sec + 40 * i + 16)
        if name == b'.rdata':
            return ptr, ptr + size
    raise RuntimeError('.rdata not found')


def patch_bytes(orig, table):
    b = bytearray(orig)
    lo, hi = rdata_range(orig)
    n_str = n_occ = 0
    for en, zh in table.items():
        if not zh or zh == en or _units(zh) > _units(en):
            continue
        pat = b'\0\0' + en.encode('utf-16-le') + b'\0\0'
        rep = b'\0\0' + zh.encode('utf-16-le') + b'\0\0' * (_units(en) - _units(zh)) + b'\0\0'
        assert len(rep) == len(pat)
        i = orig.find(pat, lo, hi); hit = False
        while i >= 0:
            if (i + 2) % 2 == 0:
                b[i:i + len(pat)] = rep; n_occ += 1; hit = True
            i = orig.find(pat, i + 2, hi)
        n_str += hit
    return bytes(b), n_str, n_occ


def install_exe(game, table, log=print):
    exe = os.path.join(game, EXE_REL); bak = exe + BACKUP; st = exe + STATE
    cur = open(exe, 'rb').read(); h = _sha1(cur)
    state = json.load(open(st, encoding='utf-8')) if os.path.exists(st) else None
    if state and h == state.get('patched'):
        if not os.path.exists(bak):
            raise RuntimeError('找不到 exe 备份。请在 Steam 里“验证游戏文件完整性”后再运行。')
        orig = open(bak, 'rb').read()
        if _sha1(orig) != state.get('orig'):
            raise RuntimeError('exe 备份已损坏。请在 Steam 里“验证游戏文件完整性”后再运行。')
    else:
        orig = cur                      # first install, or the game updated / was verified
        shutil.copyfile(exe, bak)
    new, n_str, n_occ = patch_bytes(orig, table)
    assert len(new) == len(orig)
    try:
        with open(exe, 'wb') as f:
            f.write(new)
    except PermissionError:
        raise RuntimeError('exe 被占用：请先完全退出 Wrench 再运行。')
    json.dump({'orig': _sha1(orig), 'patched': _sha1(new)}, open(st, 'w', encoding='utf-8'))
    log('exe 内置文本已汉化 %d 条（%d 处）。原版备份: %s' % (n_str, n_occ, os.path.basename(bak)))


def uninstall_exe(game, log=print):
    exe = os.path.join(game, EXE_REL); bak = exe + BACKUP; st = exe + STATE
    if not os.path.exists(st):
        log('exe 未被修改，无需还原。'); return
    state = json.load(open(st, encoding='utf-8'))
    cur = open(exe, 'rb').read()
    if _sha1(cur) == state.get('patched') and os.path.exists(bak):
        orig = open(bak, 'rb').read()
        if _sha1(orig) != state.get('orig'):
            raise RuntimeError('exe 备份已损坏，请在 Steam 里“验证游戏文件完整性”。')
        try:
            with open(exe, 'wb') as f:
                f.write(orig)
        except PermissionError:
            raise RuntimeError('exe 被占用：请先完全退出 Wrench 再运行。')
        log('已还原原版 exe。')
    else:
        log('exe 已不是汉化版（可能游戏更新过），保持不动。')
    for p in (bak, st):
        try:
            os.remove(p)
        except OSError:
            pass
