"""Testes do pipeline de matching usando fontes instaladas como ground truth:
renderiza uma palavra numa fonte conhecida e verifica que o pipeline a coloca
no topo do ranking."""
import cv2
import numpy as np
import pytest

from fontfinder.fonts.discovery import discover_fonts, supports_text
from fontfinder.fonts.render import render_word
from fontfinder.matching.features import coarse_features, fine_similarity, to_canvas
from fontfinder.matching.pipeline import MatchError, match_word
from fontfinder.matching.preprocess import prepare_crop, prepare_render

WORD = "Ação"  # com acento e cedilha — testa suporte pt-BR

FONTS = discover_fonts()


def _pick_test_font():
    preferred = ("dejavu sans", "liberation sans", "ubuntu", "noto sans",
                 "arial", "helvetica")
    for name in preferred:
        for f in FONTS:
            if (f.family.lower() == name
                    and f.style.lower() in ("regular", "book", "normal", "")
                    and supports_text(f, WORD)):
                return f
    for f in FONTS:
        if supports_text(f, WORD) and render_word(f, WORD) is not None:
            return f
    pytest.skip("nenhuma fonte instalada renderiza a palavra de teste")


@pytest.fixture(scope="module")
def test_font():
    if not FONTS:
        pytest.skip("nenhuma fonte instalada")
    return _pick_test_font()


def _photo_like(gray: np.ndarray) -> np.ndarray:
    """Simula uma foto: ruído, contraste reduzido e leve borrão."""
    img = gray.astype(np.float32)
    img = img * 0.7 + 40                       # contraste menor
    rng = np.random.default_rng(42)
    img += rng.normal(0, 8, img.shape)         # ruído
    img = np.clip(img, 0, 255).astype(np.uint8)
    return cv2.GaussianBlur(img, (3, 3), 0)


def test_prepare_crop_extracts_text(test_font):
    gray = render_word(test_font, WORD)
    binary = prepare_crop(_photo_like(gray))
    assert binary is not None
    ink = float(np.mean(binary < 128))
    assert 0.02 < ink < 0.8


def test_self_similarity_is_high(test_font):
    gray = render_word(test_font, WORD)
    a = to_canvas(prepare_render(gray))
    score = fine_similarity(a, a)
    assert score > 0.99


def test_coarse_features_shape_stable(test_font):
    gray = render_word(test_font, WORD)
    feats = coarse_features(prepare_render(gray))
    feats2 = coarse_features(prepare_render(gray))
    assert feats.shape == feats2.shape
    assert np.allclose(feats, feats2)


def test_exact_render_ranks_top3(test_font):
    """Render limpo da própria fonte deve voltar no top 3."""
    gray = render_word(test_font, WORD)
    results = match_word(gray, WORD, FONTS)
    assert results, "pipeline não devolveu resultados"
    top = [r.font.family.lower() for r in results[:3]]
    assert test_font.family.lower() in top, (
        f"{test_font.family} fora do top 3: {top}")


def test_noisy_render_ranks_top5(test_font):
    """Mesmo com ruído de foto, a fonte original deve ficar no top 5."""
    gray = render_word(test_font, WORD)
    results = match_word(_photo_like(gray), WORD, FONTS)
    assert results
    top = [r.font.family.lower() for r in results[:5]]
    assert test_font.family.lower() in top, (
        f"{test_font.family} fora do top 5: {top}")


def test_empty_word_raises():
    with pytest.raises(MatchError):
        match_word(np.full((50, 200), 255, np.uint8), "   ", FONTS)


def test_blank_crop_raises():
    with pytest.raises(MatchError):
        match_word(np.full((50, 200), 255, np.uint8), "teste", FONTS)
