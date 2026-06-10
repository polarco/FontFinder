"""Renderização de uma palavra em uma fonte instalada."""
from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from fontfinder.fonts.discovery import FontInfo

RENDER_SIZE = 128  # tamanho do corpo usado no render de matching


def render_word(font: FontInfo, text: str, size: int = RENDER_SIZE) -> np.ndarray | None:
    """Renderiza `text` na fonte e devolve grayscale uint8 (texto preto, fundo
    branco), recortado justo. None se a fonte não puder ser usada."""
    try:
        pil_font = ImageFont.truetype(font.path, size=size, index=font.index)
    except Exception:
        return None
    try:
        bbox = pil_font.getbbox(text)
    except Exception:
        return None
    if bbox is None or bbox[2] <= bbox[0] or bbox[3] <= bbox[1]:
        return None

    pad = size // 4
    w = bbox[2] - bbox[0] + 2 * pad
    h = bbox[3] - bbox[1] + 2 * pad
    if w <= 0 or h <= 0 or w > 8000:
        return None
    img = Image.new("L", (w, h), 255)
    draw = ImageDraw.Draw(img)
    draw.text((pad - bbox[0], pad - bbox[1]), text, font=pil_font, fill=0)
    arr = np.asarray(img)

    ink = arr < 128
    if not ink.any():
        return None
    rows = np.any(ink, axis=1)
    cols = np.any(ink, axis=0)
    r0, r1 = np.argmax(rows), len(rows) - np.argmax(rows[::-1])
    c0, c1 = np.argmax(cols), len(cols) - np.argmax(cols[::-1])
    return arr[r0:r1, c0:c1]
