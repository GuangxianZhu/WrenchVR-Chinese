"""Build the Wrench Simplified-Chinese patch.

python build.py              # extract text, build pak into ../dist
python build.py --install    # ...and copy it into the game's Paks folder
python build.py --uninstall  # remove the patch from the game
"""
import argparse, json, os, re, shutil, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from pakfile import write_pak, PakReader
from locres import write_locres, read_locres_legacy
from extract import extract
from appnames import build_app_names
from partnames import build_part_names
from dffont import build_cjk_font
from textrender import textrender_overrides
from exepatch import install_exe, uninstall_exe, clean_exe_bytes, EXE_REL
from exeloctext import extract_loctext
from idents import identifiers

ROOT = os.path.dirname(HERE)
PAK_REL = os.path.join('WindowsNoEditor', 'WrenchGame', 'Content', 'Paks')
BASE_PAK = 'WrenchGame-WindowsNoEditor.pak'
PATCH_NAME = 'zzz_WrenchZhCN_P.pak'
# The game ships English-only ICU data, so it can't switch to zh-Hans.
# Putting the Chinese table under "en" overrides the English text directly;
# other folders are a fallback in case the current culture resolves differently.
CULTURES = ['en', 'ja', 'zh', 'zh-Hans', 'zh-CN']
EXE_LOC_SOURCES = set()


def steam_libraries():
    libs = []
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Valve\Steam') as k:
            steam = winreg.QueryValueEx(k, 'SteamPath')[0]
        libs.append(steam)
        vdf = os.path.join(steam, 'steamapps', 'libraryfolders.vdf')
        for m in re.finditer(r'"path"\s+"([^"]+)"', open(vdf, encoding='utf-8', errors='ignore').read()):
            libs.append(m.group(1).replace('\\\\', '\\'))
    except Exception:
        pass
    return libs


def find_game(explicit=None):
    cands = []
    if explicit:
        cands.append(explicit)
    cfg = os.path.join(ROOT, 'game_path.txt')
    if os.path.exists(cfg):
        cands.append(open(cfg, encoding='utf-8').read().strip())
    cands.append(os.path.dirname(ROOT))  # patch folder placed inside the game folder
    cands += [os.path.join(l, 'steamapps', 'common', 'Wrench') for l in steam_libraries()]
    cands.append(r'D:\SteamLibrary\steamapps\common\Wrench')
    for c in cands:
        if c and os.path.isfile(os.path.join(c, PAK_REL, BASE_PAK)):
            return c
    sys.exit('找不到 Wrench 安装目录。请把游戏路径写进 game_path.txt（例如 D:\\SteamLibrary\\steamapps\\common\\Wrench）')


def build(game):
    base = os.path.join(game, PAK_REL, BASE_PAK)
    print('读取游戏文本:', base)
    entries, conflicts = extract(base)
    json.dump(entries, open(os.path.join(ROOT, 'data', 'source_entries.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=0)
    zh = json.load(open(os.path.join(ROOT, 'data', 'zh_CN.json'), encoding='utf-8'))
    # the same English word can need different Chinese in different places ("Empty" as a
    # state vs. as a button): zh_context.json maps "AssetName|English" to a specific translation
    ctx_path = os.path.join(ROOT, 'data', 'zh_context.json')
    ctx = json.load(open(ctx_path, encoding='utf-8')) if os.path.exists(ctx_path) else {}

    def tr_of(e):
        stem = os.path.splitext(os.path.basename(e['asset']))[0]
        return ctx.get(stem + '|' + e['src']) or zh.get(e['src'])
    rows = [(e['ns'], e['key'], e['src'], t) for e in entries for t in [tr_of(e)] if t]
    # C++ LOCTEXT texts recovered from the exe: translated through the same locres
    exe_loc = []
    if os.path.exists(os.path.join(game, EXE_REL)):
        exe_loc = extract_loctext(clean_exe_bytes(game))
        json.dump(exe_loc, open(os.path.join(ROOT, 'data', 'exe_loctext.json'), 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=0)
    zx = json.load(open(os.path.join(ROOT, 'data', 'zh_exe.json'), encoding='utf-8'))
    zk = json.load(open(os.path.join(ROOT, 'data', 'zh_inputkeys.json'), encoding='utf-8'))
    have = {(r[0], r[1]) for r in rows}; n_exe = 0; untranslated_exe = set()
    for e in exe_loc:
        if e['ns'] == 'InputKeys':
            tr = zk.get(e['key'])
        elif e['ns'] == 'WrenchGame':
            tr = zx.get(e['src']) or zh.get(e['src'])
            if not tr and re.search(r'[A-Za-z]{2,}', e['src']):
                untranslated_exe.add(e['src'])
        else:
            tr = zx.get(e['src'])     # engine namespaces: only texts we deliberately translated
        if tr and tr != e['src'] and (e['ns'], e['key']) not in have:
            rows.append((e['ns'], e['key'], e['src'], tr)); have.add((e['ns'], e['key'])); n_exe += 1
    print('exe 内 LOCTEXT 文本 %d 条，已通过翻译表汉化 %d 条，未翻译 %d 条' % (len(exe_loc), n_exe, len(untranslated_exe)))
    global EXE_LOC_SOURCES
    EXE_LOC_SOURCES = {e['src'] for e in exe_loc}
    srcs = {e['src'] for e in entries}
    missing = sorted(s for s in srcs if s not in zh and re.search(r'[A-Za-z]{2,}', s))
    print('文本条目 %d，已翻译 %d，未翻译(含新文本) %d' % (len(entries), len(rows), len(missing)))
    json.dump(missing, open(os.path.join(ROOT, 'data', 'untranslated.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=0)
    loc = write_locres(rows)
    assert len(read_locres_legacy(loc)) == len(rows)
    files = {'WrenchGame/Content/Localization/Game/%s/Game.locres' % c: loc for c in CULTURES}
    tro, n_tr = textrender_overrides(PakReader(base))
    files.update(tro)
    print('3D 文字（TextRender，字体无中文）保持英文: %d 处' % n_tr)
    try:
        extra, n = build_app_names(PakReader(base))
        files.update(extra)
        print('平板应用名称已汉化 %d 个' % n)
    except Exception as ex:  # layout changed after a game update: skip this part only
        print('跳过平板应用名称汉化（游戏资源结构已变化）:', ex)
    try:
        pn, n_pkg, n_val, miss = build_part_names(PakReader(base), zh, files)
        files.update(pn)
        print('零件名称（准星指向零件时显示）已汉化 %d 个' % n_pkg)
        if miss:
            print('  以下零件名还没有译文:', ', '.join(miss))
    except Exception as ex:
        print('跳过零件名称汉化（游戏资源结构已变化）:', ex)
    try:
        # VR part labels etc. are 3D text, whose baked font only has Latin glyphs
        fo, n_g, cps = build_cjk_font(PakReader(base))
        files.update(fo)
        print('3D 文字字体已补中文字形 %d 个' % n_g)
        used = set()
        for tbl in (zh, zx, zk):
            for v in tbl.values():
                used.update(c for c in v if ord(c) > 255)
        lack = sorted(c for c in used if ord(c) not in cps)
        if lack:
            print('  这些字在 3D 文字里会显示成方框（运行 tools/make_cjk_glyphs.py 补）:', ''.join(lack))
    except Exception as ex:
        print('跳过 3D 文字字体（游戏资源结构已变化）:', ex)
    os.makedirs(os.path.join(ROOT, 'dist'), exist_ok=True)
    out = os.path.join(ROOT, 'dist', PATCH_NAME)
    write_pak(out, files)
    chk = PakReader(out)
    assert sorted(chk.files) == sorted(files) and all(chk.read(k) == v for k, v in files.items())
    print('补丁已生成:', out, '(%d KB)' % (os.path.getsize(out) // 1024))
    return out


def main():
    for st in (sys.stdout, sys.stderr):
        try:
            st.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass
    ap = argparse.ArgumentParser()
    ap.add_argument('--game')
    ap.add_argument('--install', action='store_true')
    ap.add_argument('--uninstall', action='store_true')
    ap.add_argument('--no-exe', action='store_true', help='不改 exe（只装 pak 补丁）')
    a = ap.parse_args()
    game = find_game(a.game)
    target = os.path.join(game, PAK_REL, PATCH_NAME)
    if a.uninstall:
        if os.path.exists(target):
            try:
                os.remove(target)
            except PermissionError:
                raise RuntimeError('补丁文件被占用：请先完全退出 Wrench 再运行。')
            print('已卸载汉化补丁。')
        else:
            print('未安装汉化补丁，无需卸载。')
        uninstall_exe(game)
        return
    out = build(game)
    if a.install:
        try:
            shutil.copyfile(out, target)
        except PermissionError:
            raise RuntimeError('补丁文件被占用：请先完全退出 Wrench 再运行。')
        print('已安装到:', target)
        exe_table = os.path.join(ROOT, 'data', 'zh_exe.json')
        if not a.no_exe and os.path.exists(exe_table):
            # LOCTEXT texts are handled by the locres; only patch plain (non-LOCTEXT) literals,
            # and never a literal that the game also uses as an identifier
            skip = identifiers(PakReader(os.path.join(game, PAK_REL, BASE_PAK))) | EXE_LOC_SOURCES
            install_exe(game, json.load(open(exe_table, encoding='utf-8')), skip)


if __name__ == '__main__':
    try:
        main()
    except RuntimeError as ex:
        print('错误:', ex)
        sys.exit(1)
