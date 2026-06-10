"""Ponto de entrada do FontFinder."""
import multiprocessing
import sys


def main():
    # Obrigatório em executáveis congelados (PyInstaller): sem isto, cada
    # worker do matching reabriria a janela do app em vez de processar fontes.
    multiprocessing.freeze_support()
    from PySide6.QtWidgets import QApplication

    from fontfinder.ui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("FontFinder")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
