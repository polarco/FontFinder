"""Pipeline de matching: imagem da palavra vs. fontes instaladas.

Etapas:
 1. prepara o recorte do usuário (binariza, deskew, normaliza);
 2. renderiza a palavra em cada fonte (paralelo + cache em disco) e extrai
    features baratas;
 3. filtro coarse mantém as COARSE_KEEP melhores;
 4. re-ranking fino (SSIM + HOG + IoU) com normalização de espessura de traço.
"""
from __future__ import annotations

import hashlib
import multiprocessing
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Callable

import cv2
import numpy as np

from fontfinder.core.config import (CACHE_DIR, COARSE_KEEP, PIPELINE_VERSION,
                                    TOP_RESULTS)
from fontfinder.fonts.discovery import FontInfo, supports_text
from fontfinder.fonts.render import RENDER_SIZE, render_word
from fontfinder.matching.features import (coarse_distance, coarse_features,
                                          fine_similarity, to_canvas)
from fontfinder.matching.preprocess import (estimate_stroke_width,
                                            match_stroke_width, prepare_crop,
                                            prepare_render)

RENDER_CACHE_DIR = CACHE_DIR / "renders"
RENDER_CACHE_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class MatchResult:
    font: FontInfo
    score: float                 # 0..100
    render: np.ndarray = field(repr=False)  # binário normalizado da fonte


class MatchError(Exception):
    """Erro amigável do pipeline (mostrado na UI)."""


def _cache_path(font: FontInfo, word: str) -> str:
    raw = f"{font.key}|{font.mtime}|{word}|{PIPELINE_VERSION}|{RENDER_SIZE}"
    digest = hashlib.sha1(raw.encode()).hexdigest()
    return str(RENDER_CACHE_DIR / f"{digest}.npz")


def _compute_font_entry(font: FontInfo, word: str):
    """Worker (roda em subprocesso): render + features de uma fonte, com cache.

    Devolve (font_key, coarse_features | None, binary | None).
    """
    path = _cache_path(font, word)
    if os.path.exists(path):
        try:
            data = np.load(path, allow_pickle=False)
            if data["ok"]:
                return font.key, data["coarse"], data["binary"]
            return font.key, None, None
        except Exception:
            pass  # cache corrompido — recalcula

    binary = None
    feats = None
    if supports_text(font, word):
        gray = render_word(font, word)
        if gray is not None:
            binary = prepare_render(gray)
            if binary is not None:
                feats = coarse_features(binary)

    try:
        if feats is not None:
            np.savez_compressed(path, ok=np.array(True),
                                coarse=feats, binary=binary)
        else:
            np.savez_compressed(path, ok=np.array(False),
                                coarse=np.zeros(1, np.float32),
                                binary=np.zeros((1, 1), np.uint8))
    except OSError:
        pass
    return font.key, feats, binary


def match_word(
    crop: np.ndarray,
    word: str,
    fonts: list[FontInfo],
    progress: Callable[[int, int, str], None] | None = None,
    is_cancelled: Callable[[], bool] | None = None,
) -> list[MatchResult]:
    """Compara o recorte (BGR ou grayscale) contra todas as fontes.

    `progress(done, total, etapa)` é chamado durante a varredura.
    """
    word = word.strip()
    if not word:
        raise MatchError("Digite a palavra que aparece no recorte.")
    if not fonts:
        raise MatchError("Nenhuma fonte instalada foi encontrada no sistema.")

    target = prepare_crop(crop)
    if target is None:
        raise MatchError("Não foi possível extrair texto legível do recorte. "
                         "Tente ajustar a seleção.")
    target_feats = coarse_features(target)
    target_stroke = estimate_stroke_width(target)
    target_canvas = to_canvas(target)

    notify = progress or (lambda *a: None)
    cancelled = is_cancelled or (lambda: False)
    by_key = {f.key: f for f in fonts}
    entries: dict[str, tuple[np.ndarray, np.ndarray]] = {}

    total = len(fonts)
    done = 0
    workers = max(1, (os.cpu_count() or 2) - 1)
    # spawn: fork em processo multi-thread (a UI roda isto numa QThread)
    # pode travar, e spawn é o que existe no Windows.
    ctx = multiprocessing.get_context("spawn")
    with ProcessPoolExecutor(max_workers=workers, mp_context=ctx) as pool:
        futures = [pool.submit(_compute_font_entry, f, word) for f in fonts]
        for fut in as_completed(futures):
            if cancelled():
                pool.shutdown(cancel_futures=True)
                return []
            key, feats, binary = fut.result()
            if feats is not None and binary is not None:
                entries[key] = (feats, binary)
            done += 1
            notify(done, total, "Renderizando fontes")

    if not entries:
        raise MatchError(f"Nenhuma fonte instalada consegue renderizar "
                         f"“{word}”. Verifique o texto digitado.")

    # ------------------------------------------------------------- coarse --
    ranked = sorted(
        ((coarse_distance(target_feats, feats), key)
         for key, (feats, _) in entries.items()),
        key=lambda t: t[0],
    )
    survivors = [key for _, key in ranked[:COARSE_KEEP]]

    # --------------------------------------------------------------- fine --
    results: list[MatchResult] = []
    for i, key in enumerate(survivors, 1):
        if cancelled():
            return []
        _, binary = entries[key]
        adjusted = match_stroke_width(binary, target_stroke)
        score = fine_similarity(target_canvas, to_canvas(adjusted))
        results.append(MatchResult(font=by_key[key], score=round(score * 100, 1),
                                   render=binary))
        notify(i, len(survivors), "Comparando candidatas")

    results.sort(key=lambda r: r.score, reverse=True)

    # Dedup por nome exibido (mesma família/estilo em arquivos diferentes).
    seen: set[str] = set()
    unique = []
    for r in results:
        name = r.font.display_name
        if name not in seen:
            seen.add(name)
            unique.append(r)
    return unique[:TOP_RESULTS]
