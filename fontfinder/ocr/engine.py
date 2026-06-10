"""OCR da imagem com segmentação palavra a palavra.

Engine principal: RapidOCR (PP-OCR via ONNX, 100% offline, alfabeto latino com
acentos pt-BR). Fallback: Tesseract (por+eng) se instalado. O OCR aqui é só
sugestão — o usuário sempre pode corrigir o texto antes do matching.

O RapidOCR detecta LINHAS de texto; a divisão em palavras é feita aqui, por
projeção vertical (vales de espaço entre palavras) com fallback proporcional.
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


_rapidocr = None


def _get_rapidocr():
    global _rapidocr
    if _rapidocr is None:
        from rapidocr_onnxruntime import RapidOCR
        _rapidocr = RapidOCR()
    return _rapidocr


def _split_line_into_words(img: np.ndarray, x: int, y: int, w: int, h: int,
                           tokens: list[str], score: float) -> list[WordBox]:
    """Divide a caixa de uma linha em caixas de palavra."""
    if len(tokens) == 1:
        return [WordBox(x, y, w, h, tokens[0], score)]

    crop = img[y:y + h, x:x + w]
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if crop.ndim == 3 else crop
    try:
        binary = binarize(gray)
    except cv2.error:
        binary = None

    gaps: list[tuple[int, int]] = []
    if binary is not None:
        ink_per_col = (binary < 128).sum(axis=0)
        in_gap = False
        start = 0
        for col, ink in enumerate(ink_per_col):
            if ink == 0 and not in_gap:
                in_gap, start = True, col
            elif ink > 0 and in_gap:
                in_gap = False
                gaps.append((start, col))
        # Espaço entre palavras ≈ vão largo (≥ 25% da altura da linha).
        min_gap = max(3, int(h * 0.25))
        gaps = [(a, b) for a, b in gaps
                if (b - a) >= min_gap and a > 0 and b < w]
        gaps.sort(key=lambda g: g[1] - g[0], reverse=True)
        gaps = sorted(gaps[:len(tokens) - 1])

    if len(gaps) == len(tokens) - 1:
        cuts = [0] + [(a + b) // 2 for a, b in gaps] + [w]
    else:
        # Fallback: divide proporcionalmente ao nº de caracteres por token.
        lens = [len(t) for t in tokens]
        total = sum(lens) + len(tokens) - 1
        cuts = [0]
        acc = 0
        for ln in lens[:-1]:
            acc += ln + 1
            cuts.append(int(w * acc / total))
        cuts.append(w)

    boxes = []
    for i, token in enumerate(tokens):
        wx0, wx1 = cuts[i], cuts[i + 1]
        boxes.append(WordBox(x + wx0, y, max(1, wx1 - wx0), h, token, score))
    return boxes


def _detect_rapidocr(img: np.ndarray) -> list[WordBox]:
    result, _ = _get_rapidocr()(img)
    words: list[WordBox] = []
    for box, text, score in (result or []):
        text = text.strip()
        if not text:
            continue
        pts = np.array(box, dtype=np.float32)
        x, y = int(pts[:, 0].min()), int(pts[:, 1].min())
        w = int(pts[:, 0].max() - x)
        h = int(pts[:, 1].max() - y)
        if w < 4 or h < 4:
            continue
        words.extend(_split_line_into_words(img, x, y, w, h,
                                            text.split(), float(score)))
    return words


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
