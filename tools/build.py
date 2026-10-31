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
from exepatch import install_exe, uninstall_exe

ROOT = os.path.dirname(HERE)
PAK_REL = os.path.join('WindowsNoEditor', 'WrenchGame', 'Content', 'Paks')
BASE_PAK = 'WrenchGame-WindowsNoEditor.pak'
PATCH_NAME = 'zzz_WrenchZhCN_P.pak'
# The game ships English-only ICU data, so it can't switch to zh-Hans.
# Putting the Chinese table under "en" overrides the English text directly;
# other folders are a fallback in case the current culture resolves differently.
CULTURES = ['en', 'ja', 'zh', 'zh-Hans', 'zh-CN']


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
    rows = [(e['ns'], e['key'], e['src'], zh[e['src']]) for e in entries if zh.get(e['src'])]
    srcs = {e['src'] for e in entries}
    missing = sorted(s for s in srcs if s not in zh and re.search(r'[A-Za-z]{2,}', s))
    print('文本条目 %d，已翻译 %d，未翻译(含新文本) %d' % (len(entries), len(rows), len(missing)))
    json.dump(missing, open(os.path.join(ROOT, 'data', 'untranslated.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=0)
    loc = write_locres(rows)
    assert len(read_locres_legacy(loc)) == len(rows)
    files = {'WrenchGame/Content/Localization/Game/%s/Game.locres' % c: loc for c in CULTURES}
    try:
        extra, n = build_app_names(PakReader(base))
        files.update(extra)
        print('平板应用名称已汉化 %d 个' % n)
    except Exception as ex:  # layout changed after a game update: skip this part only
        print('跳过平板应用名称汉化（游戏资源结构已变化）:', ex)
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
            os.remove(target); print('已卸载汉化补丁。')
        else:
            print('未安装汉化补丁，无需卸载。')
        uninstall_exe(game)
        return
    out = build(game)
    if a.install:
        shutil.copyfile(out, target)
        print('已安装到:', target)
        exe_table = os.path.join(ROOT, 'data', 'zh_exe.json')
        if not a.no_exe and os.path.exists(exe_table):
            install_exe(game, json.load(open(exe_table, encoding='utf-8')))


if __name__ == '__main__':
    try:
        main()
    except RuntimeError as ex:
        print('错误:', ex)
        sys.exit(1)
