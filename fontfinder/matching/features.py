"""Extração de features e métricas de similaridade.

Duas etapas:
 - coarse: features baratas (proporção, densidade, perfis de projeção) para
   descartar rapidamente a maioria das fontes;
 - fine: SSIM multi-escala + HOG sobre um canvas comum, para o re-ranking.
"""
from __future__ import annotations

import cv2
import numpy as np
from skimage.feature import hog
from skimage.metrics import structural_similarity

from fontfinder.core.config import FINE_CANVAS

PROJ_BINS_H = 64   # perfil horizontal (colunas)
PROJ_BINS_V = 32   # perfil vertical (linhas)


# ---------------------------------------------------------------- coarse ----

def coarse_features(binary: np.ndarray) -> np.ndarray:
    """Vetor barato de features de uma palavra binarizada (texto preto)."""
    ink = (binary < 128).astype(np.float32)
    h, w = ink.shape
    aspect = w / h
    density = float(ink.mean())

    proj_h = ink.mean(axis=0)  # por coluna
    proj_v = ink.mean(axis=1)  # por linha
    proj_h = cv2.resize(proj_h.reshape(1, -1), (PROJ_BINS_H, 1)).ravel()
    proj_v = cv2.resize(proj_v.reshape(1, -1), (PROJ_BINS_V, 1)).ravel()
    for p in (proj_h, proj_v):
        m = p.max()
        if m > 0:
            p /= m

    moments = cv2.moments(ink)
    hu = cv2.HuMoments(moments).ravel()
    hu = np.sign(hu) * np.log10(np.abs(hu) + 1e-12)  # comprime a escala

    return np.concatenate([[aspect, density], proj_h, proj_v, hu]).astype(np.float32)


def coarse_distance(fa: np.ndarray, fb: np.ndarray) -> float:
    """Distância ponderada entre dois vetores de coarse_features."""
    aspect_d = abs(fa[0] - fb[0]) / max(fa[0], fb[0], 1e-6)
    density_d = abs(fa[1] - fb[1])
    i = 2
    ph_d = float(np.mean(np.abs(fa[i:i + PROJ_BINS_H] - fb[i:i + PROJ_BINS_H])))
    i += PROJ_BINS_H
    pv_d = float(np.mean(np.abs(fa[i:i + PROJ_BINS_V] - fb[i:i + PROJ_BINS_V])))
    i += PROJ_BINS_V
    hu_d = float(np.mean(np.abs(fa[i:] - fb[i:]))) / 10.0
    return 2.0 * aspect_d + 1.5 * density_d + 2.0 * ph_d + 1.5 * pv_d + hu_d


# ------------------------------------------------------------------ fine ----

def to_canvas(binary: np.ndarray, canvas: tuple[int, int] = FINE_CANVAS) -> np.ndarray:
    """Centraliza a palavra num canvas fixo preservando proporção."""
    cw, ch = canvas
    h, w = binary.shape
    scale = min((cw - 8) / w, (ch - 8) / h)
    nw, nh = max(2, int(w * scale)), max(2, int(h * scale))
    interp = cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC
    resized = cv2.resize(binary, (nw, nh), interpolation=interp)
    out = np.full((ch, cw), 255, dtype=np.uint8)
    y0 = (ch - nh) // 2
    x0 = (cw - nw) // 2
    out[y0:y0 + nh, x0:x0 + nw] = resized
    return out


def _align_horizontal(canvas_a: np.ndarray, canvas_b: np.ndarray,
                      max_shift: int = 24) -> np.ndarray:
    """Desloca `canvas_b` horizontalmente para casar com `canvas_a`
    (correlação dos perfis de tinta por coluna)."""
    prof_a = (canvas_a < 128).sum(axis=0).astype(np.float32)
    prof_b = (canvas_b < 128).sum(axis=0).astype(np.float32)
    best_shift, best_err = 0, np.inf
    for shift in range(-max_shift, max_shift + 1):
        rolled = np.roll(prof_b, shift)
        err = float(np.mean(np.abs(prof_a - rolled)))
        if err < best_err:
            best_err, best_shift = err, shift
    if best_shift == 0:
        return canvas_b
    out = np.roll(canvas_b, best_shift, axis=1)
    if best_shift > 0:
        out[:, :best_shift] = 255
    else:
        out[:, best_shift:] = 255
    return out


def _chamfer_similarity(canvas_a: np.ndarray, canvas_b: np.ndarray) -> float:
    """Similaridade por distância de chamfer simétrica: quão perto cada pixel
    de tinta de um está da tinta do outro. Tolerante a deformações pequenas —
    bom para fontes decorativas/irregulares."""
    ink_a = canvas_a < 128
    ink_b = canvas_b < 128
    if not ink_a.any() or not ink_b.any():
        return 0.0
    # distância de cada pixel até a tinta mais próxima
    dist_to_a = cv2.distanceTransform((~ink_a).astype(np.uint8), cv2.DIST_L2, 3)
    dist_to_b = cv2.distanceTransform((~ink_b).astype(np.uint8), cv2.DIST_L2, 3)
    d_ab = float(dist_to_b[ink_a].mean())
    d_ba = float(dist_to_a[ink_b].mean())
    # escala: ~4px de desvio médio ainda é "parecido" num canvas de 96px de altura
    return float(np.exp(-(d_ab + d_ba) / 8.0))


def fine_similarity(canvas_a: np.ndarray, canvas_b: np.ndarray) -> float:
    """Similaridade 0..1 entre dois canvases (mesma forma)."""
    canvas_b = _align_horizontal(canvas_a, canvas_b)
    # Borrão leve dá tolerância a pequenos desalinhamentos.
    a = cv2.GaussianBlur(canvas_a, (5, 5), 0).astype(np.float32)
    b = cv2.GaussianBlur(canvas_b, (5, 5), 0).astype(np.float32)

    ssim_full = structural_similarity(a, b, data_range=255.0)
    a2 = cv2.resize(a, None, fx=0.5, fy=0.5)
    b2 = cv2.resize(b, None, fx=0.5, fy=0.5)
    ssim_half = structural_similarity(a2, b2, data_range=255.0)
    ssim = 0.5 * (ssim_full + ssim_half)

    hog_a = hog(canvas_a, orientations=9, pixels_per_cell=(16, 16),
                cells_per_block=(2, 2), feature_vector=True)
    hog_b = hog(canvas_b, orientations=9, pixels_per_cell=(16, 16),
                cells_per_block=(2, 2), feature_vector=True)
    denom = np.linalg.norm(hog_a) * np.linalg.norm(hog_b)
    hog_cos = float(np.dot(hog_a, hog_b) / denom) if denom > 0 else 0.0

    # Sobreposição direta de tinta (IoU) ancora o score em forma real.
    ink_a = canvas_a < 128
    ink_b = canvas_b < 128
    union = np.logical_or(ink_a, ink_b).sum()
    iou = float(np.logical_and(ink_a, ink_b).sum() / union) if union else 0.0

    chamfer = _chamfer_similarity(canvas_a, canvas_b)

    score = (0.30 * max(0.0, ssim) + 0.25 * max(0.0, hog_cos)
             + 0.20 * iou + 0.25 * chamfer)
    return float(np.clip(score, 0.0, 1.0))
