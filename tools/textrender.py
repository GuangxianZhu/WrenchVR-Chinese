"""3D text (TextRenderComponent) draws with the engine's offline distance-field font, which has
no CJK glyphs - Chinese would show as boxes. But the same FText (same key) is often shared with
a UI widget, e.g. a tutorial station's title is both a floating 3D sign and the title on its
board. A locres entry can't tell the two apart, so we give the 3D copy its own key instead:
the last character of its key is changed (same length, no other byte moves), the locres has no
entry for that key, and the 3D sign keeps its English source text while the UI shows Chinese.
The edited packages are shipped inside the patch pak; the game's own files are not touched."""
import re
from uasset import Summary, export_spans

KEY = re.compile(rb'\x21\x00\x00\x00([0-9A-F]{32})\x00')


def textrender_overrides(pak):
    out = {}; n_total = 0
    for p in sorted(pak.files):
        if not (p.startswith('WrenchGame/Content') and p.endswith('.uexp')):
            continue
        base = p[:-5]
        head = base + '.umap' if base + '.umap' in pak.files else base + '.uasset'
        if head not in pak.files:
            continue
        a = pak.read(head)
        try:
            s = Summary(a)
        except Exception:
            continue
        if not any(n == 'TextRenderComponent' for n, _ in s.names):
            continue
        spans = [(st, en) for st, en, c in export_spans(a, s) if 'TextRender' in c]
        if not spans:
            continue
        b = bytearray(pak.read(p)); n = 0
        for m in KEY.finditer(b):
            if any(st <= m.start() < en for st, en in spans):
                last = m.end(1) - 1
                b[last] = ord('0') if b[last] != ord('0') else ord('1')
                n += 1
        if n:
            out[p] = bytes(b); out[head] = a; n_total += n
    return out, n_total
