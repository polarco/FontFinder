"""Janela principal do FontFinder."""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from PySide6.QtCore import Qt, QSettings
from PySide6.QtGui import QAction, QImage, QKeySequence
from PySide6.QtWidgets import (QApplication, QFileDialog, QFrame, QHBoxLayout,
                               QLabel, QLineEdit, QMainWindow, QMessageBox,
                               QProgressBar, QPushButton, QSplitter,
                               QVBoxLayout, QWidget)

from fontfinder import __version__
from fontfinder.ui.image_view import ImageView
from fontfinder.ui.results import ResultsList
from fontfinder.ui.theme import DARK, LIGHT
from fontfinder.ui.workers import FontScanWorker, MatchWorker, OcrWorker

IMAGE_FILTER = "Imagens (*.png *.jpg *.jpeg *.bmp *.webp *.tif *.tiff)"


def qimage_to_bgr(qimg: QImage) -> np.ndarray:
    qimg = qimg.convertToFormat(QImage.Format_RGB888)
    w, h = qimg.width(), qimg.height()
    buf = np.frombuffer(qimg.constBits(), dtype=np.uint8)
    arr = buf.reshape(h, qimg.bytesPerLine())[:, : w * 3].reshape(h, w, 3)
    return arr[:, :, ::-1].copy()  # RGB -> BGR


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"FontFinder {__version__}")
        self.resize(1180, 720)
        self.setAcceptDrops(True)

        self._settings = QSettings("fontfinder", "fontfinder")
        self._image: np.ndarray | None = None
        self._crop: np.ndarray | None = None
        self._fonts = []
        self._match_worker: MatchWorker | None = None
        self._ocr_worker: OcrWorker | None = None

        self._build_ui()
        self._apply_theme(self._settings.value("theme", "dark"))
        self._scan_fonts()

    # ---------------------------------------------------------------- ui --
    def _build_ui(self):
        # Painel esquerdo: imagem + palavra + ação
        left = QWidget()
        left_lay = QVBoxLayout(left)
        left_lay.setContentsMargins(16, 16, 8, 16)
        left_lay.setSpacing(10)

        header = QHBoxLayout()
        title = QLabel("FontFinder")
        title.setObjectName("title")
        header.addWidget(title)
        header.addStretch()
        self.theme_btn = QPushButton("☀")
        self.theme_btn.setObjectName("flat")
        self.theme_btn.setToolTip("Alternar tema claro/escuro")
        self.theme_btn.clicked.connect(self._toggle_theme)
        open_btn = QPushButton("Abrir imagem…")
        open_btn.clicked.connect(self._open_dialog)
        header.addWidget(open_btn)
        header.addWidget(self.theme_btn)
        left_lay.addLayout(header)

        self.image_view = ImageView()
        self.image_view.selectionChanged.connect(self._on_selection)
        left_lay.addWidget(self.image_view, 1)

        self.empty_hint = QLabel(
            "Arraste uma imagem aqui, cole com Ctrl+V ou clique em "
            "“Abrir imagem…”.\nDepois clique numa palavra detectada — ou "
            "arraste para selecionar manualmente.")
        self.empty_hint.setObjectName("hint")
        self.empty_hint.setAlignment(Qt.AlignCenter)
        left_lay.addWidget(self.empty_hint)

        word_card = QFrame()
        word_card.setObjectName("card")
        word_lay = QHBoxLayout(word_card)
        word_lay.setContentsMargins(12, 10, 12, 10)
        word_label = QLabel("Palavra:")
        self.word_edit = QLineEdit()
        self.word_edit.setPlaceholderText(
            "Texto da palavra selecionada (edite se o OCR errou)")
        self.word_edit.returnPressed.connect(self._start_match)
        self.compare_btn = QPushButton("Comparar fontes")
        self.compare_btn.setObjectName("primary")
        self.compare_btn.clicked.connect(self._start_match)
        self.compare_btn.setEnabled(False)
        word_lay.addWidget(word_label)
        word_lay.addWidget(self.word_edit, 1)
        word_lay.addWidget(self.compare_btn)
        left_lay.addWidget(word_card)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        left_lay.addWidget(self.progress)

        # Painel direito: resultados
        right = QWidget()
        right_lay = QVBoxLayout(right)
        right_lay.setContentsMargins(8, 16, 16, 16)
        right_lay.setSpacing(10)
        results_title = QLabel("Fontes mais parecidas")
        results_title.setObjectName("title")
        self.results_hint = QLabel(
            "Os resultados aparecem aqui depois da comparação.\n"
            "Clique num resultado para ver a comparação ampliada.")
        self.results_hint.setObjectName("hint")
        self.results_hint.setAlignment(Qt.AlignCenter)
        self.results_list = ResultsList()
        right_lay.addWidget(results_title)
        right_lay.addWidget(self.results_hint, 1)
        right_lay.addWidget(self.results_list, 4)
        self.results_list.setVisible(False)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setSizes([640, 540])
        self.setCentralWidget(splitter)

        self.statusBar().showMessage("Procurando fontes instaladas…")

        paste = QAction(self)
        paste.setShortcut(QKeySequence.Paste)
        paste.triggered.connect(self._paste_image)
        self.addAction(paste)

    # ------------------------------------------------------------- theme --
    def _apply_theme(self, name: str):
        self._theme = name
        QApplication.instance().setStyleSheet(DARK if name == "dark" else LIGHT)
        self.theme_btn.setText("☀" if name == "dark" else "🌙")
        self._settings.setValue("theme", name)

    def _toggle_theme(self):
        self._apply_theme("light" if self._theme == "dark" else "dark")

    # ------------------------------------------------------------- fonts --
    def _scan_fonts(self):
        self._scan_worker = FontScanWorker(self)
        self._scan_worker.finished_ok.connect(self._on_fonts)
        self._scan_worker.failed.connect(
            lambda msg: self._error("Falha ao listar fontes do sistema", msg))
        self._scan_worker.start()

    def _on_fonts(self, fonts):
        self._fonts = fonts
        self.statusBar().showMessage(
            f"{len(fonts)} fontes instaladas encontradas.")
        if not fonts:
            self._error("Nenhuma fonte encontrada",
                        "Não foi possível encontrar fontes instaladas no sistema.")

    # ------------------------------------------------------------- image --
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() or event.mimeData().hasImage():
            event.acceptProposedAction()

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            self._load_path(event.mimeData().urls()[0].toLocalFile())
        elif event.mimeData().hasImage():
            self._load_qimage(QImage(event.mimeData().imageData()))

    def _paste_image(self):
        clipboard = QApplication.clipboard()
        img = clipboard.image()
        if not img.isNull():
            self._load_qimage(img)
        elif clipboard.mimeData().hasUrls():
            self._load_path(clipboard.mimeData().urls()[0].toLocalFile())

    def _open_dialog(self):
        path, _ = QFileDialog.getOpenFileName(self, "Abrir imagem", str(Path.home()),
                                              IMAGE_FILTER)
        if path:
            self._load_path(path)

    def _load_path(self, path: str):
        img = cv2.imread(path, cv2.IMREAD_COLOR)
        if img is None:
            self._error("Imagem inválida",
                        f"Não foi possível abrir “{Path(path).name}”.")
            return
        self._set_image(img)

    def _load_qimage(self, qimg: QImage):
        if qimg.isNull():
            return
        self._set_image(qimage_to_bgr(qimg))

    def _set_image(self, img: np.ndarray):
        # Limita imagens gigantes para o OCR não demorar.
        max_side = 2200
        scale = max_side / max(img.shape[:2])
        if scale < 1:
            img = cv2.resize(img, None, fx=scale, fy=scale,
                             interpolation=cv2.INTER_AREA)
        self._image = img
        self._crop = None
        self.word_edit.clear()
        self.compare_btn.setEnabled(False)
        self.results_list.setVisible(False)
        self.results_hint.setVisible(True)
        self.image_view.set_image(img)
        self.empty_hint.setText("Detectando palavras…")
        self._run_ocr()

    # --------------------------------------------------------------- ocr --
    def _run_ocr(self):
        self._ocr_worker = OcrWorker(self._image, self)
        self._ocr_worker.finished_ok.connect(self._on_words)
        self._ocr_worker.failed.connect(lambda msg: self._on_words([]))
        self._ocr_worker.start()
        self.statusBar().showMessage("Rodando OCR…")

    def _on_words(self, words):
        self.image_view.set_words(words)
        if words:
            self.empty_hint.setText(
                f"{len(words)} palavra(s) detectada(s). Clique numa caixa para "
                "escolher — ou arraste para selecionar manualmente.")
            self.statusBar().showMessage(f"{len(words)} palavras detectadas.")
            # Pré-seleciona a maior palavra (mais útil para matching).
            best = max(words, key=lambda wb: wb.w * wb.h)
            self.image_view.select_rect(best.rect, best.text)
        else:
            self.empty_hint.setText(
                "Nenhum texto detectado pelo OCR. Arraste sobre a imagem para "
                "selecionar a palavra manualmente e digite o texto dela.")
            self.statusBar().showMessage("OCR não encontrou texto — use a "
                                         "seleção manual.")

    def _on_selection(self, rect, text):
        x, y, w, h = rect
        pad = max(2, h // 10)
        img = self._image
        y0, y1 = max(0, y - pad), min(img.shape[0], y + h + pad)
        x0, x1 = max(0, x - pad), min(img.shape[1], x + w + pad)
        self._crop = img[y0:y1, x0:x1].copy()
        if text:
            self.word_edit.setText(text)
        self.compare_btn.setEnabled(True)
        self.word_edit.setFocus()
        self.word_edit.selectAll()

    # ------------------------------------------------------------- match --
    def _start_match(self):
        if self._match_worker is not None and self._match_worker.isRunning():
            return
        if self._crop is None:
            self._error("Nenhuma palavra selecionada",
                        "Clique numa palavra detectada ou arraste sobre a "
                        "imagem para selecionar uma.")
            return
        word = self.word_edit.text().strip()
        if not word:
            self._error("Palavra vazia",
                        "Digite o texto da palavra selecionada antes de "
                        "comparar.")
            return
        if not self._fonts:
            self._error("Sem fontes", "Nenhuma fonte instalada para comparar.")
            return

        self.compare_btn.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setValue(0)

        self._match_worker = MatchWorker(self._crop, word, self._fonts, self)
        self._match_worker.progressed.connect(self._on_progress)
        self._match_worker.finished_ok.connect(self._on_results)
        self._match_worker.failed.connect(self._on_match_failed)
        self._match_worker.start()

    def _on_progress(self, done, total, stage):
        self.progress.setMaximum(total)
        self.progress.setValue(done)
        self.statusBar().showMessage(f"{stage}… {done}/{total}")

    def _on_results(self, results):
        self.progress.setVisible(False)
        self.compare_btn.setEnabled(True)
        if not results:
            self.statusBar().showMessage("Nenhum resultado.")
            return
        self.results_hint.setVisible(False)
        self.results_list.setVisible(True)
        self.results_list.show_results(results, self._crop)
        best = results[0]
        self.statusBar().showMessage(
            f"Melhor correspondência: {best.font.display_name} "
            f"({best.score:.0f}%).")

    def _on_match_failed(self, msg):
        self.progress.setVisible(False)
        self.compare_btn.setEnabled(True)
        self._error("Não foi possível comparar", msg)

    # ------------------------------------------------------------- utils --
    def _error(self, title: str, msg: str):
        QMessageBox.warning(self, title, msg)
        self.statusBar().showMessage(title)

    def closeEvent(self, event):
        if self._match_worker is not None and self._match_worker.isRunning():
            self._match_worker.cancel()
            self._match_worker.wait(3000)
        super().closeEvent(event)
