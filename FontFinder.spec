# Spec do PyInstaller para gerar o FontFinder.exe (Windows, onefile, sem console).
# Build: pyinstaller FontFinder.spec
from PyInstaller.utils.hooks import collect_all

# RapidOCR carrega modelos .onnx e configs .yaml de dentro do pacote — o CI
# pré-baixa os modelos (latino PP-OCRv5) antes do build para serem embutidos.
rapidocr_datas, rapidocr_binaries, rapidocr_hidden = collect_all("rapidocr")

a = Analysis(
    ["fontfinder/main.py"],
    pathex=["."],
    binaries=rapidocr_binaries,
    datas=rapidocr_datas,
    hiddenimports=rapidocr_hidden,
    excludes=["tkinter", "pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="FontFinder",
    console=False,
    upx=False,
)
