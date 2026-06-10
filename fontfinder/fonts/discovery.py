"""Descoberta das fontes instaladas no sistema (Linux, Windows, macOS)."""
from __future__ import annotations

import json
import platform
import subprocess
from dataclasses import dataclass, asdict
from pathlib import Path

from fontTools.ttLib import TTFont, TTLibError

from fontfinder.core.config import CACHE_DIR

VALID_SUFFIXES = {".ttf", ".otf", ".ttc", ".otc"}


@dataclass(frozen=True)
class FontInfo:
    path: str
    index: int  # índice dentro de .ttc/.otc; 0 para fontes simples
    family: str
    style: str
    mtime: float

    @property
    def display_name(self) -> str:
        if self.style and self.style.lower() not in ("regular", "book", "normal"):
            return f"{self.family} {self.style}"
        return self.family

    @property
    def key(self) -> str:
        return f"{self.path}::{self.index}"


def _discover_fontconfig() -> list[FontInfo]:
    out = subprocess.run(
        ["fc-list", "--format", "%{file}\t%{family[0]}\t%{style[0]}\t%{index}\n"],
        capture_output=True, text=True, check=True,
    ).stdout
    fonts = []
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) != 4:
            continue
        path, family, style, index = parts
        p = Path(path)
        if p.suffix.lower() not in VALID_SUFFIXES or not p.exists():
            continue
        fonts.append(FontInfo(
            path=str(p), index=int(index or 0),
            family=family or p.stem, style=style or "",
            mtime=p.stat().st_mtime,
        ))
    return fonts


def _font_dirs() -> list[Path]:
    system = platform.system()
    home = Path.home()
    if system == "Windows":
        import os
        return [
            Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts",
            home / "AppData/Local/Microsoft/Windows/Fonts",
        ]
    if system == "Darwin":
        return [Path("/System/Library/Fonts"), Path("/Library/Fonts"),
                home / "Library/Fonts"]
    return [Path("/usr/share/fonts"), Path("/usr/local/share/fonts"),
            home / ".fonts", home / ".local/share/fonts"]


def _read_names(path: Path) -> list[tuple[int, str, str]]:
    """Lê (index, family, style) de um arquivo de fonte via fontTools."""
    results = []
    try:
        n_fonts = 1
        if path.suffix.lower() in (".ttc", ".otc"):
            from fontTools.ttLib import TTCollection
            n_fonts = len(TTCollection(str(path), lazy=True).fonts)
        for i in range(n_fonts):
            tt = TTFont(str(path), fontNumber=i if n_fonts > 1 else -1, lazy=True)
            name = tt["name"]
            family = (name.getDebugName(16) or name.getDebugName(1)
                      or path.stem)
            style = name.getDebugName(17) or name.getDebugName(2) or ""
            results.append((i, family, style))
            tt.close()
    except (TTLibError, Exception):
        pass
    return results


def _discover_scan() -> list[FontInfo]:
    fonts = []
    for root in _font_dirs():
        if not root.exists():
            continue
        for p in root.rglob("*"):
            if p.suffix.lower() not in VALID_SUFFIXES or not p.is_file():
                continue
            for index, family, style in _read_names(p):
                fonts.append(FontInfo(
                    path=str(p), index=index, family=family,
                    style=style, mtime=p.stat().st_mtime,
                ))
    return fonts


def discover_fonts(use_cache: bool = True) -> list[FontInfo]:
    """Lista todas as fontes instaladas, com cache em disco."""
    cache_file = CACHE_DIR / "fonts.json"
    if use_cache and cache_file.exists():
        try:
            data = json.loads(cache_file.read_text())
            fonts = [FontInfo(**d) for d in data]
            # Cache válido se os arquivos ainda existem com o mesmo mtime
            # (amostra os 20 primeiros para não custar caro).
            sample = fonts[:20]
            if all(Path(f.path).exists()
                   and Path(f.path).stat().st_mtime == f.mtime for f in sample):
                return fonts
        except (json.JSONDecodeError, TypeError, OSError):
            pass

    try:
        fonts = _discover_fontconfig()
    except (FileNotFoundError, subprocess.CalledProcessError):
        fonts = _discover_scan()

    # Remove duplicatas (mesmo arquivo+índice listado mais de uma vez).
    seen: set[str] = set()
    unique = []
    for f in sorted(fonts, key=lambda f: (f.family.lower(), f.style.lower())):
        if f.key not in seen:
            seen.add(f.key)
            unique.append(f)

    cache_file.write_text(json.dumps([asdict(f) for f in unique]))
    return unique


def supports_text(font: FontInfo, text: str) -> bool:
    """True se a fonte tem glifos para todos os caracteres do texto."""
    try:
        tt = TTFont(font.path, fontNumber=font.index if font.path.lower()
                    .endswith((".ttc", ".otc")) else -1, lazy=True)
        cmap = tt.getBestCmap()
        tt.close()
    except Exception:
        return False
    if not cmap:
        return False
    return all(ord(ch) in cmap for ch in text if not ch.isspace())
