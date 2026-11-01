"""Give the engine's 3D-text font Chinese glyphs.

3D text (TextRenderComponent) - e.g. the part name floating next to your hand in VR - can
only use an *offline* font: a pre-baked texture page plus a table of glyph rectangles. The
default one, /Engine/EngineFonts/RobotoDistanceField, holds just 256 Latin glyphs (512x256,
G8 distance field), so Chinese turns into boxes. UI widgets use a runtime font with a CJK
fallback, which is why menus are fine.

We rebuild that font package: a 4096x2048 page with the original 256 glyphs upscaled 2x
(distance fields scale cleanly) plus the Chinese glyphs from data/cjk_glyphs.bin
(rendered from the engine's own DroidSansFallback, see make_cjk_glyphs.py). The glyph
table grows accordingly and the font switches to IsRemapped + CharRemap (UTF-16 -> glyph
index). Every glyph is 52 texels tall, so the text keeps its size on screen.
Pure Python; the modified package only goes into the patch pak."""
import os, struct, zlib
from uasset import Summary, append_names

ASSET = 'Engine/Content/EngineFonts/RobotoDistanceField'
GLYPHS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'cjk_glyphs.bin')
PAGE_W, PAGE_H = 4096, 2048
SCALE = 2
CELL_H = 26 * SCALE
M = 4                      # distance-field margin kept around each glyph rectangle
CHAR_SIZE = 21             # FFontCharacter: StartU, StartV, USize, VSize (int32), TextureIndex (u8), VerticalOffset (int32)


def _load_glyphs():
    b = zlib.decompress(open(GLYPHS, 'rb').read())
    assert b[:4] == b'WZG1'
    cell_h, adv, margin, _, n = struct.unpack_from('<HHHHI', b, 4)
    assert cell_h == CELL_H and margin == M
    o = 16; out = []
    for _ in range(n):
        cp, w, h = struct.unpack_from('<IHH', b, o); o += 8
        out.append((cp, w, h, b[o:o + w * h])); o += w * h
    return adv, out


def _tags(x, o, N):
    """Walk tagged properties; return [(name, start, end)] and the offset after 'None'."""
    out = []
    while True:
        ni, = struct.unpack_from('<i', x, o)
        if N[ni] == 'None':
            return out, o + 8
        ti, _, size, _ = struct.unpack_from('<iiii', x, o + 8)
        p = o + 24; t = N[ti]
        if t == 'StructProperty':
            p += 8 + 16
        elif t in ('ArrayProperty', 'ByteProperty', 'EnumProperty', 'SetProperty'):
            p += 8
        elif t == 'BoolProperty':
            p += 1
        p += 1
        out.append((N[ni], o, p, p + size))   # name, tag start, value start, value end
        o = p + size


def build_cjk_font(pak):
    """Return ({path: bytes}, glyph_count, set_of_codepoints)."""
    a = pak.read(ASSET + '.uasset'); x = pak.read(ASSET + '.uexp')
    s = Summary(a); N = [n for n, _ in s.names]
    assert len(s.exports) == 2
    (_, fsize, foff), (_, tsize, toff) = s.exports[0], s.exports[1]
    font = x[:fsize]; tex = x[fsize:fsize + tsize]
    assert foff == s.TotalHeaderSize and toff == foff + fsize and len(x) == fsize + tsize + 4

    # --- original font export
    tags, end = _tags(font, 0, N)
    tg = {n: (ts, vs, ve) for n, ts, vs, ve in tags}
    assert 'IsRemapped' not in tg and font[end:] == b'\0' * 8   # HasGuid=0, CharRemap empty
    ts, vs, ve = tg['Characters']
    count, = struct.unpack_from('<i', font, vs)
    inner = font[vs + 4:vs + 4 + 49]
    assert struct.unpack_from('<i', inner, 16)[0] == count * CHAR_SIZE
    chars = [struct.unpack_from('<iiiiBi', font, vs + 53 + i * CHAR_SIZE) for i in range(count)]
    assert vs + 53 + count * CHAR_SIZE == ve

    # --- original page (G8)
    ttags, tend = _tags(tex, 0, N)
    q = tend + 4 + 2 + 2 + 4                       # HasGuid, 2x strip flags, bCooked
    pf, = struct.unpack_from('<i', tex, q); assert N[pf] == 'PF_G8'
    q_skip = q + 8
    q_size = q + 16
    ow, oh, _ = struct.unpack_from('<iii', tex, q_size)
    sl, = struct.unpack_from('<i', tex, q_size + 12); q_mip = q_size + 16 + sl
    _, nmips, cooked, flags, cnt, sod = struct.unpack_from('<iiiiii', tex, q_mip)
    assert nmips == 1 and cnt == ow * oh == sod
    q_data = q_mip + 24 + 8
    page = tex[q_data:q_data + cnt]
    q_after = q_data + cnt                          # mip SizeX, SizeY, SizeZ, bIsVirtual, 'None'

    # --- new page
    adv, glyphs = _load_glyphs()
    P = bytearray(PAGE_W * PAGE_H)
    cur = [0, 0]

    def place(w, h):
        if cur[0] + w > PAGE_W:
            cur[0] = 0; cur[1] += h
        assert cur[1] + h <= PAGE_H, 'font page full'
        pos = tuple(cur); cur[0] += w
        return pos

    def sample(fx, fy):                             # bilinear sample of the old page
        fx = min(max(fx, 0), ow - 1.001); fy = min(max(fy, 0), oh - 1.001)
        x0, y0 = int(fx), int(fy); dx, dy = fx - x0, fy - y0
        i = y0 * ow + x0
        a0 = page[i] + (page[i + 1] - page[i]) * dx
        a1 = page[i + ow] + (page[i + ow + 1] - page[i + ow]) * dx
        return int(a0 + (a1 - a0) * dy + 0.5)

    new_chars = []
    th = CELL_H + 2 * M
    for su, sv, us, vs_, ti, vo in chars:
        w = us * SCALE + 2 * M
        px, py = place(w, th)
        for yy in range(th):
            fy = sv + (yy - M + 0.5) / SCALE - 0.5
            row = (py + yy) * PAGE_W + px
            for xx in range(w):
                P[row + xx] = sample(su + (xx - M + 0.5) / SCALE - 0.5, fy)
        new_chars.append((px + M, py + M, us * SCALE, vs_ * SCALE, ti, vo * SCALE))
    remap = {i: i for i in range(len(chars))}
    for cp, w, h, px_ in glyphs:
        px, py = place(w, h)
        for yy in range(h):
            P[(py + yy) * PAGE_W + px:(py + yy) * PAGE_W + px + w] = px_[yy * w:(yy + 1) * w]
        remap[cp] = len(new_chars)
        new_chars.append((px + M, py + M, adv, CELL_H, 0, 0))

    # --- new font export
    a2, newix = append_names(a, ['IsRemapped'])
    N2 = N + ['IsRemapped']; ix = {n: i for i, n in enumerate(N2)}
    inner = bytearray(inner); struct.pack_into('<i', inner, 16, len(new_chars) * CHAR_SIZE)
    arr = struct.pack('<i', len(new_chars)) + bytes(inner) + b''.join(struct.pack('<iiiiBi', *c) for c in new_chars)
    chars_tag = bytearray(font[ts:vs]); struct.pack_into('<i', chars_tag, 16, len(arr))
    f2 = bytearray(font[:ts] + bytes(chars_tag) + arr + font[ve:end - 8])
    f2 += struct.pack('<iiiiiiB', ix['IsRemapped'], 0, ix['IntProperty'], 0, 4, 0, 0) + struct.pack('<i', 1)
    f2 += font[end - 8:end]                        # 'None'
    f2 += struct.pack('<ii', 0, len(remap)) + b''.join(struct.pack('<HH', k, v) for k, v in sorted(remap.items()))

    # --- new texture export
    t2 = bytearray(tex[:q_data]) + P + bytearray(tex[q_after:])
    ts_, vs2, ve2 = next((t, v, e) for n, t, v, e in ttags if n == 'ImportedSize')
    struct.pack_into('<ii', t2, vs2, PAGE_W, PAGE_H)
    struct.pack_into('<ii', t2, q_size, PAGE_W, PAGE_H)
    struct.pack_into('<ii', t2, q_mip + 16, PAGE_W * PAGE_H, PAGE_W * PAGE_H)
    struct.pack_into('<ii', t2, q_data + len(P), PAGE_W, PAGE_H)

    s2 = Summary(a2); hdr = s2.TotalHeaderSize
    tex_abs = hdr + len(f2)
    struct.pack_into('<q', t2, q_mip + 24, tex_abs + q_data)                  # inline mip data position
    struct.pack_into('<q', t2, q_skip, tex_abs + len(t2) - 8)                 # end of this pixel format
    uexp = bytes(f2) + bytes(t2) + x[-4:]

    # --- export map / summary
    a2 = bytearray(a2)
    e0, e1 = s2.exports[0][0], s2.exports[1][0]
    struct.pack_into('<qq', a2, e0 + 28, len(f2), hdr)
    struct.pack_into('<qq', a2, e1 + 28, len(t2), hdr + len(f2))
    struct.pack_into('<q', a2, s2.pos['BulkDataStartOffset'], hdr + len(f2) + len(t2))
    chk = Summary(bytes(a2))
    assert sum(e[1] for e in chk.exports) == len(uexp) - 4
    return {ASSET + '.uasset': bytes(a2), ASSET + '.uexp': uexp}, len(glyphs), set(remap)
