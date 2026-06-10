"""Testes do OCR: acentuação pt-BR e segmentação por palavra."""
import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageFont

from fontfinder.fonts.discovery import discover_fonts, supports_text
from fontfinder.ocr.engine import detect_words

PHRASE = "Meu coração é tropical"


def _phrase_image(noise: bool = False) -> np.ndarray:
    fonts = discover_fonts()
    # Fontes de texto conhecidas — pegar "qualquer fonte com os glifos"
    # arrisca cair numa fonte de dingbats/símbolos.
    preferred = ("dejavu sans", "liberation sans", "ubuntu", "noto sans",
                 "arial", "calibri", "segoe ui", "helvetica")
    target = next((f for name in preferred for f in fonts
                   if f.family.lower() == name
                   and f.style.lower() in ("regular", "book", "normal", "")
                   and supports_text(f, PHRASE)), None)
    if target is None:
        pytest.skip("nenhuma fonte de texto conhecida instalada")
    pil_font = ImageFont.truetype(target.path, size=72, index=target.index)
    img = Image.new("RGB", (1100, 160), (245, 243, 238))
    ImageDraw.Draw(img).text((30, 35), PHRASE, font=pil_font, fill=(30, 30, 35))
    bgr = np.asarray(img)[:, :, ::-1].copy()
    if noise:
        rng = np.random.default_rng(7)
        noisy = bgr.astype(np.float32) + rng.normal(0, 12, bgr.shape)
        bgr = np.clip(noisy, 0, 255).astype(np.uint8)
    return bgr


def test_detects_words_with_accents():
    words = detect_words(_phrase_image())
    texts = [w.text.lower() for w in words]
    assert "coração" in texts, f"acentos perdidos: {texts}"


def test_word_boxes_are_plausible():
    img = _phrase_image()
    words = detect_words(img)
    assert 3 <= len(words) <= 8
    for wb in words:
        assert 0 <= wb.x < img.shape[1]
        assert 0 <= wb.y < img.shape[0]
        assert wb.w > 0 and wb.h > 0


def test_noisy_image_still_detected():
    words = detect_words(_phrase_image(noise=True))
    assert words, "OCR não detectou nada em imagem com ruído"
    joined = " ".join(w.text.lower() for w in words)
    assert "tropical" in joined
