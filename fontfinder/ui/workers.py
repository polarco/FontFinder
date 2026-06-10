"""Threads de trabalho para não travar a UI (OCR e matching)."""
from __future__ import annotations

import numpy as np
from PySide6.QtCore import QThread, Signal

from fontfinder.fonts.discovery import FontInfo, discover_fonts
from fontfinder.matching.pipeline import MatchError, match_word
from fontfinder.ocr.engine import detect_words


class OcrWorker(QThread):
    finished_ok = Signal(list)   # list[WordBox]
    failed = Signal(str)

    def __init__(self, img: np.ndarray, parent=None):
        super().__init__(parent)
        self._img = img

    def run(self):
        try:
            self.finished_ok.emit(detect_words(self._img))
        except Exception as exc:  # noqa: BLE001 — qualquer falha vira aviso na UI
            self.failed.emit(str(exc))


class FontScanWorker(QThread):
    finished_ok = Signal(list)   # list[FontInfo]
    failed = Signal(str)

    def run(self):
        try:
            self.finished_ok.emit(discover_fonts())
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))


class MatchWorker(QThread):
    progressed = Signal(int, int, str)
    finished_ok = Signal(list)   # list[MatchResult]
    failed = Signal(str)

    def __init__(self, crop: np.ndarray, word: str, fonts: list[FontInfo],
                 parent=None):
        super().__init__(parent)
        self._crop = crop
        self._word = word
        self._fonts = fonts
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        try:
            results = match_word(
                self._crop, self._word, self._fonts,
                progress=lambda d, t, s: self.progressed.emit(d, t, s),
                is_cancelled=lambda: self._cancelled,
            )
            if not self._cancelled:
                self.finished_ok.emit(results)
        except MatchError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(f"Erro inesperado durante a comparação: {exc}")
