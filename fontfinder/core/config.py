"""Configurações globais e caminhos de cache."""
from pathlib import Path

APP_NAME = "FontFinder"

CACHE_DIR = Path.home() / ".cache" / "fontfinder"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Versão dos parâmetros de render/features — mudar invalida o cache.
PIPELINE_VERSION = 2

# Altura normalizada dos recortes/renders usados no matching.
NORM_HEIGHT = 64
# Canvas do re-ranking fino (largura x altura).
FINE_CANVAS = (320, 96)
# Quantas fontes sobrevivem ao filtro barato para o re-ranking fino.
COARSE_KEEP = 100
# Quantos resultados aparecem na UI.
TOP_RESULTS = 20
