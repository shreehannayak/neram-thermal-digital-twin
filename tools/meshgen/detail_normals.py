"""Tileable tangent-space detail normal maps (512 px): fabric weave, non-woven (mask/cap), fine skin. Generated, not
photographic; used at low strength for surface detail only."""
from pathlib import Path

import numpy as np
from PIL import Image

N = 512


def height_to_normal(h, strength):
    gx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) * 0.5 * strength
    gy = (np.roll(h, -1, 0) - np.roll(h, 1, 0)) * 0.5 * strength
    n = np.stack([-gx, -gy, np.ones_like(h)], -1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    return Image.fromarray(((n * 0.5 + 0.5) * 255).astype(np.uint8), "RGB")


def tile_noise(rng, cells, octaves=4):
    out = np.zeros((N, N))
    amp = 1.0
    for o in range(octaves):
        c = cells * 2 ** o
        g = rng.standard_normal((c, c))
        img = Image.fromarray(((g - g.min()) / (np.ptp(g) + 1e-9) * 255).astype(np.uint8)).resize((N, N), Image.BICUBIC)
        # wrap-safe: blend with a rolled copy so the seam is continuous
        a = np.asarray(img, float) / 255.0
        a = 0.5 * (a + np.roll(np.roll(a, N // 2, 0), N // 2, 1))
        out += amp * a
        amp *= 0.5
    return (out - out.min()) / (np.ptp(out) + 1e-9)


def main(outdir):
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(7)
    y, x = np.mgrid[0:N, 0:N] / N * 2 * np.pi
    k = 32
    warp = np.sin(x * k) * np.cos(y * k)          # plain weave: alternating over/under
    weft = np.abs(np.sin(y * k * 2)) ** 0.6
    warpz = np.abs(np.sin(x * k * 2)) ** 0.6
    h = np.where(warp > 0, warpz, weft) + 0.25 * tile_noise(rng, 16, 3)
    height_to_normal(h, 6.0).save(out / "weave_normal.png")
    h = tile_noise(rng, 24, 4) + 0.35 * tile_noise(rng, 96, 2)
    height_to_normal(h, 10.0).save(out / "nonwoven_normal.png")
    h = tile_noise(rng, 40, 3) * 0.6 + 0.4 * (tile_noise(rng, 160, 2) > 0.62)
    height_to_normal(h, 5.0).save(out / "skin_normal.png")


if __name__ == "__main__":
    main("unity_editor/Assets/NERAM_Generated/Textures")
