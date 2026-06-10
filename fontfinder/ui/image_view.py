"""Visualizador da imagem com caixas de palavra clicáveis e seleção manual.

 - Clique numa caixa de palavra (detectada pelo OCR) para escolhê-la.
 - Arraste com o mouse para desenhar uma seleção manual (quando o OCR errou
   a segmentação ou não detectou nada).
"""
from __future__ import annotations

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QImage, QPen, QPixmap
from PySide6.QtWidgets import QGraphicsScene, QGraphicsView

from fontfinder.ocr.engine import WordBox


def ndarray_to_qimage(img: np.ndarray) -> QImage:
    if img.ndim == 2:
        h, w = img.shape
        return QImage(np.ascontiguousarray(img).data, w, h, w,
                      QImage.Format_Grayscale8).copy()
    h, w, _ = img.shape
    rgb = np.ascontiguousarray(img[:, :, ::-1])  # BGR -> RGB
    return QImage(rgb.data, w, h, 3 * w, QImage.Format_RGB888).copy()


class ImageView(QGraphicsView):
    # rect (x, y, w, h) em coords da imagem + texto sugerido pelo OCR ("" se manual)
    selectionChanged = Signal(tuple, str)

    DRAG_THRESHOLD = 6  # px de tela para diferenciar clique de arraste

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setRenderHints(self.renderHints())
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setDragMode(QGraphicsView.NoDrag)
        self.setMouseTracking(True)

        self._pixmap_item = None
        self._words: list[WordBox] = []
        self._box_items = []
        self._selected_rect: tuple[int, int, int, int] | None = None
        self._highlight_item = None
        self._press_pos: QPointF | None = None
        self._rubber_item = None

        self._pen_box = QPen(QColor("#4f7cff"), 0)
        self._pen_box.setCosmetic(True)
        self._pen_box.setWidth(1)
        self._pen_sel = QPen(QColor("#2ecc71"), 0)
        self._pen_sel.setCosmetic(True)
        self._pen_sel.setWidth(2)
        self._fill_box = QColor(79, 124, 255, 36)
        self._fill_sel = QColor(46, 204, 113, 40)

    # ------------------------------------------------------------ public --
    def set_image(self, img: np.ndarray):
        self._scene.clear()
        self._box_items.clear()
        self._highlight_item = None
        self._rubber_item = None
        self._selected_rect = None
        self._words = []
        pix = QPixmap.fromImage(ndarray_to_qimage(img))
        self._pixmap_item = self._scene.addPixmap(pix)
        self._scene.setSceneRect(QRectF(pix.rect()))
        self.fitInView(self._scene.sceneRect(), Qt.KeepAspectRatio)

    def set_words(self, words: list[WordBox]):
        for item in self._box_items:
            self._scene.removeItem(item)
        self._box_items.clear()
        self._words = words
        for wb in words:
            item = self._scene.addRect(QRectF(*wb.rect), self._pen_box,
                                       self._fill_box)
            item.setToolTip(wb.text)
            self._box_items.append(item)

    def select_rect(self, rect: tuple[int, int, int, int], text: str = ""):
        self._selected_rect = rect
        if self._highlight_item is not None:
            self._scene.removeItem(self._highlight_item)
        self._highlight_item = self._scene.addRect(QRectF(*rect),
                                                   self._pen_sel,
                                                   self._fill_sel)
        self.selectionChanged.emit(rect, text)

    def selected_rect(self) -> tuple[int, int, int, int] | None:
        return self._selected_rect

    def has_image(self) -> bool:
        return self._pixmap_item is not None

    # ------------------------------------------------------------ events --
    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._pixmap_item is not None:
            self.fitInView(self._scene.sceneRect(), Qt.KeepAspectRatio)

    def wheelEvent(self, event):
        if self._pixmap_item is None:
            return
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.scale(factor, factor)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self._pixmap_item is not None:
            self._press_pos = event.position()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if (self._press_pos is not None
                and (event.position() - self._press_pos).manhattanLength()
                > self.DRAG_THRESHOLD):
            start = self.mapToScene(self._press_pos.toPoint())
            end = self.mapToScene(event.position().toPoint())
            rect = QRectF(start, end).normalized()
            if self._rubber_item is None:
                self._rubber_item = self._scene.addRect(rect, self._pen_sel,
                                                        self._fill_sel)
            else:
                self._rubber_item.setRect(rect)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._press_pos is not None:
            press = self._press_pos
            self._press_pos = None
            if self._rubber_item is not None:
                rect = self._rubber_item.rect()
                self._scene.removeItem(self._rubber_item)
                self._rubber_item = None
                clamped = rect.intersected(self._scene.sceneRect())
                if clamped.width() >= 8 and clamped.height() >= 8:
                    self.select_rect((int(clamped.x()), int(clamped.y()),
                                      int(clamped.width()),
                                      int(clamped.height())), "")
            else:
                scene_pos = self.mapToScene(press.toPoint())
                self._click_word(scene_pos)
        super().mouseReleaseEvent(event)

    def _click_word(self, pos: QPointF):
        for wb in self._words:
            x, y, w, h = wb.rect
            if x <= pos.x() <= x + w and y <= pos.y() <= y + h:
                self.select_rect(wb.rect, wb.text)
                return
