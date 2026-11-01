"""Collect strings the game uses as identifiers (FNames in package name maps, values in
config files). Text that is also an identifier must not be rewritten in the exe:
the same literal may be used for lookups (input action names, IDs), not just display."""
import re
from uasset import Summary


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
            ids.update(re.findall(r'"([^"]+)"', t))
            ids.update(re.findall(r'=([^=\r\n,()"]+)', t))
    return {x.strip() for x in ids}
