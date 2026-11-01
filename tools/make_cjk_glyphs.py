"""Maintenance tool (needs Pillow, numpy, scipy): render the Chinese characters used by the
translations as distance-field glyphs, for the 3D text font (see dffont.py).

    python tools/make_cjk_glyphs.py <DroidSansFallback.ttf>

The TTF is the engine's own fallback font (Engine/Content/EngineFonts/Faces/
DroidSansFallback.ufont inside the game pak; Apache License 2.0). Output:
data/cjk_glyphs.bin (zlib). Re-run after adding translations with new characters;
the build prints any character that has no glyph yet.

Glyph layout matches the 2x-upscaled Roboto distance-field font: cell height 52 texels,
baseline 41.2 texels from the top, distance-field slope 3.2 levels per texel, edge at 128."""
import json, os, struct, sys, zlib
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.ndimage import distance_transform_edt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
CELL_H = 52          # texels (Roboto DF cell is 26 at 1x; the build upscales it 2x)
BASELINE = 41.2      # texels from the cell top (Roboto ascent 0.928 em of a 1.172 em line)
EM = 42              # CJK em size in texels
ADV = 44             # advance (em + 2 texels spacing)
MARGIN = 4           # extra distance-field texels stored around the cell
SLOPE = 3.2          # value levels per texel (same as the 2x-upscaled Roboto page)
BOLD = 0.5           # texels: thicken strokes a little to match Roboto's heavy weight
SS = 8               # supersampling for the outline


def charset():
    from partnames import EXTRA
    from appnames import FALLBACK
    s = set()
    for f in ('zh_CN.json', 'zh_exe.json', 'zh_inputkeys.json', 'zh_context.json'):
        p = os.path.join(ROOT, 'data', f)
        if os.path.exists(p):
            for v in json.load(open(p, encoding='utf-8')).values():
                s.update(c for c in v if 255 < ord(c) < 0x10000)
    for v in list(EXTRA.values()) + list(FALLBACK.values()):
        s.update(c for c in v if 255 < ord(c) < 0x10000)
    return sorted(s)


def glyph(font, ch):
    w, h = ADV + 2 * MARGIN, CELL_H + 2 * MARGIN
    img = Image.new('L', (w * SS, h * SS), 0)
    ImageDraw.Draw(img).text(((MARGIN + 1) * SS, (MARGIN + BASELINE) * SS), ch, fill=255, font=font, anchor='ls')
    inside = np.asarray(img) >= 128
    if not inside.any():
        return None
    d_out = distance_transform_edt(~inside)          # hi-res px to the glyph, for outside pixels
    d_in = distance_transform_edt(inside)            # hi-res px to the background, for inside pixels
    sd = (np.where(inside, d_in - 0.5, -(d_out - 0.5))) / SS   # signed distance in texels
    # sample at texel centres
    sd = sd[SS // 2::SS, SS // 2::SS][:h, :w]
    v = np.clip(np.round(128 + (sd + BOLD) * SLOPE), 0, 255).astype(np.uint8)
    return w, h, v.tobytes()


def main():
    ttf = sys.argv[1]
    font = ImageFont.truetype(ttf, EM * SS)
    chars = charset()
    out = bytearray(b'WZG1' + struct.pack('<HHHHI', CELL_H, ADV, MARGIN, 0, len(chars)))
    missing = []
    for i, ch in enumerate(chars):
        g = glyph(font, ch)
        if g is None:
            missing.append(ch); g = (ADV + 2 * MARGIN, CELL_H + 2 * MARGIN, bytes((ADV + 2 * MARGIN) * (CELL_H + 2 * MARGIN)))
        w, h, px = g
        out += struct.pack('<IHH', ord(ch), w, h) + px
        if i % 200 == 0:
            print(i, '/', len(chars))
    dst = os.path.join(ROOT, 'data', 'cjk_glyphs.bin')
    open(dst, 'wb').write(zlib.compress(bytes(out), 9))
    print('glyphs', len(chars), 'empty', ''.join(missing), '->', dst, os.path.getsize(dst) // 1024, 'KB')


if __name__ == '__main__':
    main()
