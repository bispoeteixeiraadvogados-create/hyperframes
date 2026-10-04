"""Texturas procedurais deterministicas: grao de filme (PNG) e curvas de nivel (SVG).

Uso:  python scripts/textures.py
"""

import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from PIL import Image, ImageFilter  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "assets", "textures")


def grain():
    r = np.random.default_rng(1234)
    g = r.normal(128, 42, (512, 512)).clip(0, 255).astype(np.uint8)
    im = Image.fromarray(g, "L").filter(ImageFilter.GaussianBlur(0.55))
    im.save(os.path.join(OUT, "grain.png"), optimize=True)


def value_noise(n, cells, seed):
    r = np.random.default_rng(seed)
    grid = r.random((cells + 3, cells + 3))
    xs = np.linspace(0, cells, n, endpoint=False)
    i = xs.astype(int)
    f = xs - i
    f = f * f * (3 - 2 * f)
    a = grid[np.ix_(i, i)]
    b = grid[np.ix_(i + 1, i)]
    c = grid[np.ix_(i, i + 1)]
    d = grid[np.ix_(i + 1, i + 1)]
    fx = f[:, None]
    fy = f[None, :]
    return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy


def contours():
    n = 700
    z = (value_noise(n, 3, 11) * 0.55 + value_noise(n, 6, 12) * 0.3 + value_noise(n, 13, 13) * 0.15)
    size = 1400.0
    fig = plt.figure()
    cs = plt.contour(np.linspace(0, size, n), np.linspace(0, size, n), z, levels=18)
    paths = []
    for level_segs in cs.allsegs:
        for seg in level_segs:
            if len(seg) < 12:
                continue
            seg = seg[::3]
            d = "M" + " L".join(f"{x:.0f} {y:.0f}" for x, y in seg)
            paths.append(d)
    plt.close(fig)
    body = "\n".join(f'  <path d="{d}"/>' for d in paths)
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1400 1400" width="1400" height="1400">\n'
        '<g fill="none" stroke="#8FA876" stroke-width="1.6" stroke-linejoin="round">\n'
        f"{body}\n</g>\n</svg>\n"
    )
    with open(os.path.join(OUT, "contours.svg"), "w") as f:
        f.write(svg)
    print("contour paths:", len(paths), "bytes:", len(svg))


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    grain()
    contours()
