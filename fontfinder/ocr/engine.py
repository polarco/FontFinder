"""OCR da imagem com segmentação palavra a palavra.

Engine principal: RapidOCR com modelo de reconhecimento PP-OCRv5 LATINO —
dicionário com acentuação completa (ã, ç, é, õ…), essencial para pt-BR.
As caixas por palavra vêm do próprio modelo (return_word_box).

Robustez para fontes difíceis: a imagem passa por múltiplas passadas de OCR
(original, ampliada com equalização de contraste, binarizada) e os resultados
são fundidos por sobreposição, ficando o de maior confiança.

Fallback: Tesseract (por+eng) se instalado. O OCR é sempre só sugestão — o
usuário pode corrigir o texto antes do matching.
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from fontfinder.matching.preprocess import binarize


@dataclass
class WordBox:
    x: int
    y: int
    w: int
    h: int
    text: str
    score: float

    @property
    def rect(self) -> tuple[int, int, int, int]:
        return self.x, self.y, self.w, self.h


_engine = None


def _get_engine():
    global _engine
    if _engine is None:
        from rapidocr import RapidOCR
        from rapidocr.utils.typings import LangRec, ModelType, OCRVersion
        _engine = RapidOCR(params={
            "Rec.lang_type": LangRec.LATIN,
            "Rec.ocr_version": OCRVersion.PPOCRV5,
            "Rec.model_type": ModelType.MOBILE,
        })
    return _engine


def _run_pass(img: np.ndarray, scale: float = 1.0) -> list[WordBox]:
    """Roda uma passada de OCR e devolve caixas por palavra na escala
    original."""
    result = _get_engine()(img, return_word_box=True)
    words: list[WordBox] = []
    if result is None or not getattr(result, "word_results", None):
        return words
    for line in result.word_results:
        for entry in line:
            try:
                text, score, pts = entry
            except (ValueError, TypeError):
                continue
            text = (text or "").strip()
            if not text or pts is None:
                continue
            arr = np.array(pts, dtype=np.float32) / scale
            x, y = int(arr[:, 0].min()), int(arr[:, 1].min())
            w = int(arr[:, 0].max() - x)
            h = int(arr[:, 1].max() - y)
            if w < 3 or h < 3:
                continue
            words.append(WordBox(x, y, w, h, text, float(score or 0.0)))
    return words


def _iou(a: WordBox, b: WordBox) -> float:
    x0 = max(a.x, b.x)
    y0 = max(a.y, b.y)
    x1 = min(a.x + a.w, b.x + b.w)
    y1 = min(a.y + a.h, b.y + b.h)
    inter = max(0, x1 - x0) * max(0, y1 - y0)
    union = a.w * a.h + b.w * b.h - inter
    return inter / union if union else 0.0


def _merge(all_words: list[list[WordBox]]) -> list[WordBox]:
    """Funde passadas: caixas sobrepostas viram uma só, vence a de maior
    confiança."""
    merged: list[WordBox] = []
    for words in all_words:
        for wb in words:
            dup = next((m for m in merged if _iou(m, wb) > 0.5), None)
            if dup is None:
                merged.append(wb)
            elif wb.score > dup.score:
                merged[merged.index(dup)] = wb
    merged.sort(key=lambda w: (w.y // 20, w.x))
    return merged


def _enhanced(img: np.ndarray) -> tuple[np.ndarray, float]:
    """Versão 2x ampliada com contraste equalizado (CLAHE)."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    scale = 2.0 if max(img.shape[:2]) < 1400 else 1.0
    if scale != 1.0:
        gray = cv2.resize(gray, None, fx=scale, fy=scale,
                          interpolation=cv2.INTER_CUBIC)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    out = clahe.apply(gray)
    return cv2.cvtColor(out, cv2.COLOR_GRAY2BGR), scale


def _binarized(img: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    binary = binarize(gray)
    return cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)


def _detect_rapidocr(img: np.ndarray) -> list[WordBox]:
    passes = [_run_pass(img)]
    # Passadas extras só ajudam quando a primeira veio fraca — evita custo
    # desnecessário em imagens limpas.
    weak = (not passes[0]
            or min((w.score for w in passes[0]), default=0.0) < 0.92)
    if weak:
        enhanced, scale = _enhanced(img)
        passes.append(_run_pass(enhanced, scale))
        try:
            passes.append(_run_pass(_binarized(img)))
        except cv2.error:
            pass
    return _merge(passes)


def _detect_tesseract(img: np.ndarray) -> list[WordBox]:
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        cv2.imwrite(f.name, img)
        tmp = f.name
    try:
        out = subprocess.run(
            ["tesseract", tmp, "stdout", "-l", "por+eng", "tsv"],
            capture_output=True, text=True, check=True,
        ).stdout
    finally:
        Path(tmp).unlink(missing_ok=True)
    words = []
    for line in out.splitlines()[1:]:
        cols = line.split("\t")
        if len(cols) < 12 or cols[0] != "5":  # level 5 = palavra
            continue
        text = cols[11].strip()
        conf = float(cols[10])
        if not text or conf < 0:
            continue
        words.append(WordBox(int(cols[6]), int(cols[7]), int(cols[8]),
                             int(cols[9]), text, conf / 100.0))
    return words


def detect_words(img: np.ndarray) -> list[WordBox]:
    """Detecta palavras na imagem (BGR). Lista vazia se nada for encontrado."""
    try:
        words = _detect_rapidocr(img)
        if words:
            return words
    except Exception:
        pass
    if shutil.which("tesseract"):
        try:
            return _detect_tesseract(img)
        except Exception:
            pass
    return []
