"""Temas escuro/claro em QSS."""

_BASE = """
* {{ font-family: "Inter", "Segoe UI", "Ubuntu", sans-serif; font-size: 13px; }}
QMainWindow, QDialog {{ background: {bg}; }}
QWidget {{ color: {fg}; }}
QLabel#title {{ font-size: 17px; font-weight: 600; }}
QLabel#subtitle {{ color: {muted}; }}
QLabel#hint {{ color: {muted}; font-size: 12px; }}

QPushButton {{
    background: {surface}; border: 1px solid {border};
    border-radius: 8px; padding: 7px 16px;
}}
QPushButton:hover {{ background: {hover}; }}
QPushButton:disabled {{ color: {muted}; background: {bg}; }}
QPushButton#primary {{
    background: {accent}; color: white; border: none; font-weight: 600;
}}
QPushButton#primary:hover {{ background: {accent_hover}; }}
QPushButton#primary:disabled {{ background: {border}; color: {muted}; }}
QPushButton#flat {{ border: none; background: transparent; padding: 6px 10px; }}
QPushButton#flat:hover {{ background: {hover}; border-radius: 8px; }}

QLineEdit {{
    background: {surface}; border: 1px solid {border}; border-radius: 8px;
    padding: 8px 12px; font-size: 15px; selection-background-color: {accent};
}}
QLineEdit:focus {{ border-color: {accent}; }}

QProgressBar {{
    background: {surface}; border: none; border-radius: 6px;
    height: 12px; text-align: center; font-size: 10px; color: {fg};
}}
QProgressBar::chunk {{ background: {accent}; border-radius: 6px; }}

QListWidget {{
    background: transparent; border: none; outline: none;
}}
QListWidget::item {{
    background: {surface}; border: 1px solid {border};
    border-radius: 10px; margin: 4px 6px;
}}
QListWidget::item:selected {{ border: 1px solid {accent}; background: {hover}; }}
QListWidget::item:hover {{ background: {hover}; }}

QGraphicsView {{
    background: {surface}; border: 1px dashed {border}; border-radius: 12px;
}}
QFrame#card {{
    background: {surface}; border: 1px solid {border}; border-radius: 12px;
}}
QScrollBar:vertical {{
    background: transparent; width: 10px; margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: {border}; border-radius: 5px; min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{ background: {muted}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QToolTip {{ background: {surface}; color: {fg}; border: 1px solid {border}; }}
QStatusBar {{ color: {muted}; }}
"""

DARK = _BASE.format(
    bg="#101216", surface="#1a1d23", hover="#23262e", border="#2e323b",
    fg="#e8eaed", muted="#8b919c", accent="#4f7cff", accent_hover="#6890ff",
)

LIGHT = _BASE.format(
    bg="#f4f5f7", surface="#ffffff", hover="#eef0f4", border="#d9dce3",
    fg="#1c1e22", muted="#6b7280", accent="#3b66e0", accent_hover="#2d54c8",
)
