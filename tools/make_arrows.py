#!/usr/bin/env python3
"""Draw the direction arrows (8 directions) as FRM files into mod/art/intrface/.
OBJA<n>.FRM 13 px (panel), OBJM<n>.FRM 17 px (screen-edge markers); n = 0 N, 1 NE ... 7 NW."""
import math
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_data import palette_index  # noqa: E402
import objdata as od  # noqa: E402

OUT = os.path.join(od.ROOT, "mod", "art", "intrface")


def inside(x, y, ang, r):
    """Arrow pointing along ang (0 = up, clockwise), radius r, in screen coords (y down)."""
    dx, dy = math.sin(ang), -math.cos(ang)
    along = x * dx + y * dy
    perp = -x * dy + y * dx
    head0 = -r * 0.1
    if head0 <= along <= r and abs(perp) <= (r - along) * 0.75:
        return True
    return -r <= along <= head0 + 0.5 and abs(perp) <= r * 0.2


def frm(w, h, pix):
    hdr = struct.pack(">IHHH", 4, 1, 0, 1) + struct.pack(">6h", *[0] * 6) * 2
    hdr += struct.pack(">6I", *[0] * 6) + struct.pack(">I", 12 + w * h)
    return hdr + struct.pack(">HHIhh", w, h, w * h, 0, 0) + bytes(pix)


def arrow(size, n, fill, edge):
    r = size / 2.0 - 1.6
    c = (size - 1) / 2.0
    ang = n * math.pi / 4
    grid = [[0] * size for _ in range(size)]
    for j in range(size):
        for i in range(size):
            hits = sum(inside(i - c + (a + .5) / 4 - .5, j - c + (b + .5) / 4 - .5, ang, r)
                       for a in range(4) for b in range(4))
            grid[j][i] = 1 if hits >= 7 else 0
    pix = []
    for j in range(size):
        for i in range(size):
            if grid[j][i]:
                pix.append(fill)
            elif any(0 <= j + b < size and 0 <= i + a < size and grid[j + b][i + a]
                     for a in (-1, 0, 1) for b in (-1, 0, 1)):
                pix.append(edge)
            else:
                pix.append(0)
    return pix


def main():
    os.makedirs(OUT, exist_ok=True)
    fill = palette_index((80, 255, 80))
    edge = palette_index((8, 20, 8))
    for n in range(8):
        for name, size in (("OBJA", 13), ("OBJM", 17)):
            with open(os.path.join(OUT, "%s%d.FRM" % (name, n)), "wb") as f:
                f.write(frm(size, size, arrow(size, n, fill, edge)))
    print("arrows written to", OUT, "fill", fill, "edge", edge)
    # preview for checking
    for n in (0, 1, 2):
        p = arrow(13, n, 1, 2)
        print("\n".join("".join(" #."[p[j * 13 + i]] for i in range(13)) for j in range(13)))


if __name__ == "__main__":
    main()
