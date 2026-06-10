"""Lista de resultados com preview lado a lado e comparação ampliada."""
from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QListWidget,
                               QListWidgetItem, QVBoxLayout, QWidget)

from fontfinder.matching.pipeline import MatchResult
from fontfinder.ui.image_view import ndarray_to_qimage


def _pixmap(arr: np.ndarray, max_w: int, max_h: int) -> QPixmap:
    pix = QPixmap.fromImage(ndarray_to_qimage(arr))
    return pix.scaled(max_w, max_h, Qt.KeepAspectRatio,
                      Qt.SmoothTransformation)


class _ResultRow(QWidget):
    def __init__(self, rank: int, result: MatchResult, crop: np.ndarray):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(12)

        score_label = QLabel(f"{result.score:.0f}%")
        score_label.setFixedWidth(48)
        score_label.setAlignment(Qt.AlignCenter)
        # A métrica é conservadora: um match exato fica na faixa de ~55%.
        color = ("#2ecc71" if result.score >= 52
                 else "#f1c40f" if result.score >= 44 else "#8b919c")
        score_label.setStyleSheet(
            f"font-size: 15px; font-weight: 700; color: {color};")

        previews = QVBoxLayout()
        previews.setSpacing(4)
        img_orig = QLabel()
        img_orig.setPixmap(_pixmap(crop, 220, 32))
        img_render = QLabel()
        img_render.setPixmap(_pixmap(result.render, 220, 32))
        previews.addWidget(img_orig)
        previews.addWidget(img_render)

        info = QVBoxLayout()
        info.setSpacing(2)
        name = QLabel(f"{rank}. {result.font.display_name}")
        name.setStyleSheet("font-weight: 600; font-size: 14px;")
        path = QLabel(result.font.path)
        path.setObjectName("hint")
        path.setStyleSheet("color: #8b919c; font-size: 11px;")
        info.addWidget(name)
        info.addLayout(previews)
        info.addWidget(path)

        layout.addWidget(score_label)
        layout.addLayout(info, 1)


class ComparisonDialog(QDialog):
    """Comparação ampliada: recorte original sobre o render da fonte."""

    def __init__(self, result: MatchResult, crop: np.ndarray, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Comparação — {result.font.display_name}")
        self.setMinimumWidth(640)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(8)

        for caption, arr in (("Imagem original", crop),
                             (f"{result.font.display_name} — "
                              f"{result.score:.0f}% de similaridade",
                              result.render)):
            label = QLabel(caption)
            label.setObjectName("subtitle")
            img = QLabel()
            img.setPixmap(_pixmap(arr, 580, 140))
            img.setAlignment(Qt.AlignCenter)
            layout.addWidget(label)
            layout.addWidget(img)

        path = QLabel(result.font.path)
        path.setObjectName("hint")
        path.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(path)


class ResultsList(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setVerticalScrollMode(QListWidget.ScrollPerPixel)
        self._results: list[MatchResult] = []
        self._crop: np.ndarray | None = None
        self.itemActivated.connect(self._open_comparison)
        self.itemClicked.connect(self._open_comparison)

    def show_results(self, results: list[MatchResult], crop: np.ndarray):
        self.clear()
        self._results = results
        self._crop = crop
        for i, result in enumerate(results, 1):
            row = _ResultRow(i, result, crop)
            item = QListWidgetItem(self)
            item.setSizeHint(QSize(0, row.sizeHint().height() + 8))
            item.setData(Qt.UserRole, i - 1)
            self.addItem(item)
            self.setItemWidget(item, row)

    def _open_comparison(self, item: QListWidgetItem):
        idx = item.data(Qt.UserRole)
        if idx is None or self._crop is None:
            return
        ComparisonDialog(self._results[idx], self._crop, self).exec()
