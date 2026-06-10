"""Pré-processamento do recorte da imagem e dos renders para comparação."""
from __future__ import annotations

import cv2
import numpy as np

from fontfinder.core.config import NORM_HEIGHT


def binarize(gray: np.ndarray) -> np.ndarray:
    """Binariza com Otsu + adaptativa e garante texto preto em fundo branco."""
    gray = cv2.fastNlMeansDenoising(gray, h=10)
    _, otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    block = max(15, (min(gray.shape) // 4) | 1)
    adapt = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                  cv2.THRESH_BINARY, block, 10)
    # Usa Otsu por padrão; se ele apagar quase tudo (fundo complexo), usa a adaptativa.
    binary = otsu
    ink_ratio = float(np.mean(binary < 128))
    if ink_ratio < 0.01 or ink_ratio > 0.9:
        binary = adapt
    # Auto-inverte: texto deve ser minoria de pixels (tinta preta).
    if np.mean(binary < 128) > 0.5:
        binary = 255 - binary
    return binary


def deskew(binary: np.ndarray) -> np.ndarray:
    """Corrige inclinação leve usando o retângulo mínimo da tinta."""
    ink = np.column_stack(np.where(binary < 128))
    if len(ink) < 20:
        return binary
    angle = cv2.minAreaRect(ink[:, ::-1].astype(np.float32))[-1]
    if angle > 45:
        angle -= 90
    if abs(angle) < 0.5 or abs(angle) > 20:  # ignora ruído e rotações absurdas
        return binary
    h, w = binary.shape
    m = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    return cv2.warpAffine(binary, m, (w, h), flags=cv2.INTER_LINEAR,
                          borderMode=cv2.BORDER_CONSTANT, borderValue=255)


def tight_crop(binary: np.ndarray) -> np.ndarray | None:
    ink = binary < 128
    if not ink.any():
        return None
    rows = np.any(ink, axis=1)
    cols = np.any(ink, axis=0)
    r0, r1 = np.argmax(rows), len(rows) - np.argmax(rows[::-1])
    c0, c1 = np.argmax(cols), len(cols) - np.argmax(cols[::-1])
    return binary[r0:r1, c0:c1]


def remove_specks(binary: np.ndarray) -> np.ndarray:
    """Remove componentes minúsculos (ruído) preservando acentos e pingos."""
    inv = (binary < 128).astype(np.uint8)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(inv, connectivity=8)
    if n <= 2:
        return binary
    areas = stats[1:, cv2.CC_STAT_AREA]
    threshold = max(2, int(areas.max() * 0.002))
    out = binary.copy()
    for i in range(1, n):
        if stats[i, cv2.CC_STAT_AREA] < threshold:
            out[labels == i] = 255
    return out


def normalize_height(binary: np.ndarray, height: int = NORM_HEIGHT) -> np.ndarray:
    h, w = binary.shape
    scale = height / h
    new_w = max(4, int(round(w * scale)))
    interp = cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC
    resized = cv2.resize(binary, (new_w, height), interpolation=interp)
    _, rebin = cv2.threshold(resized, 127, 255, cv2.THRESH_BINARY)
    return rebin


def estimate_stroke_width(binary: np.ndarray) -> float:
    """Largura média de traço via transformada de distância."""
    ink = (binary < 128).astype(np.uint8)
    if not ink.any():
        return 1.0
    dist = cv2.distanceTransform(ink, cv2.DIST_L2, 3)
    strokes = dist[dist > 0]
    if len(strokes) == 0:
        return 1.0
    return float(2.0 * np.median(strokes))


def match_stroke_width(binary: np.ndarray, target_width: float,
                       max_steps: int = 3) -> np.ndarray:
    """Engrossa/afina o traço para aproximar a espessura do alvo, tolerando
    diferenças de peso (bold vs regular) entre imagem e fonte."""
    current = estimate_stroke_width(binary)
    out = binary
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    steps = 0
    while steps < max_steps:
        diff = target_width - estimate_stroke_width(out)
        if abs(diff) < 1.0:
            break
        if diff > 0:  # alvo é mais grosso → dilata a tinta (erode no branco)
            out = cv2.erode(out, kernel)
        else:
            out = cv2.dilate(out, kernel)
        if not (out < 128).any():  # afinou demais, desfaz
            return binary
        steps += 1
    return out


def prepare_crop(bgr_or_gray: np.ndarray) -> np.ndarray | None:
    """Pipeline completo para o recorte vindo da imagem do usuário.
    Devolve binário normalizado (texto preto, altura NORM_HEIGHT) ou None."""
    if bgr_or_gray.ndim == 3:
        gray = cv2.cvtColor(bgr_or_gray, cv2.COLOR_BGR2GRAY)
    else:
        gray = bgr_or_gray
    if gray.size == 0 or min(gray.shape) < 8:
        return None
    # Aumenta recortes muito pequenos antes de binarizar.
    if gray.shape[0] < 48:
        scale = 48 / gray.shape[0]
        gray = cv2.resize(gray, None, fx=scale, fy=scale,
                          interpolation=cv2.INTER_CUBIC)
    binary = binarize(gray)
    binary = remove_specks(binary)
    binary = deskew(binary)
    binary = tight_crop(binary)
    if binary is None:
        return None
    return normalize_height(binary)


def prepare_render(render_gray: np.ndarray) -> np.ndarray | None:
    """Pipeline para o render da fonte candidata (já é limpo: só binariza e
    normaliza)."""
    _, binary = cv2.threshold(render_gray, 127, 255, cv2.THRESH_BINARY)
    binary = tight_crop(binary)
    if binary is None:
        return None
    return normalize_height(binary)
