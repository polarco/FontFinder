# ContextoGeral.md

## Visão — nome, descrição, problema, público
- **Nome:** FontFinder
- **Descrição:** Programa desktop que identifica, a partir de uma imagem, qual fonte instalada localmente no computador do usuário é mais parecida com o texto da imagem.
- **Problema:** Identificar fontes a partir de imagens hoje depende de serviços online (WhatTheFont etc.) que não comparam com as fontes que o usuário realmente tem instaladas.
- **Público:** Designers e usuários que precisam reproduzir uma fonte vista em uma imagem usando as fontes locais.

## Objetivo atual
Testar o MVP v0.1.0 com imagens reais e refinar a precisão do matching.

## Estado — status, versão
- Status: MVP funcional, testes passando (7/7 + e2e)
- Versão: 0.1.0

## Stack — front, back, db, infra, integrações
- Python 3.12 (venv via `uv`, em `.venv/`)
- UI: PySide6 (QSS, tema escuro/claro)
- OCR: RapidOCR (PP-OCR/ONNX, offline, latino) com fallback Tesseract
- Visão: OpenCV (headless) + scikit-image (SSIM, HOG) + Pillow/fontTools (render)
- Sem banco de dados; cache de renders/features em `~/.cache/fontfinder/`
- 100% local/offline

## Features — ✅ feitas / 🚧 em progresso / 📋 planejadas
- ✅ Upload/drag-and-drop/Ctrl+V de imagem
- ✅ OCR em português com segmentação palavra a palavra (caixas clicáveis)
- ✅ Seleção de 1 palavra + edição manual do texto + seleção manual por arraste
- ✅ Varredura das fontes instaladas (fontconfig/scan, com cache)
- ✅ Ranking top 20 com preview lado a lado + comparação ampliada
- ✅ Matching robusto em 2 etapas (coarse + fine, normalização de traço, deskew)
- 📋 Validação com fotos reais (fontes decorativas, fundos ruidosos)

## Decisões — decisão / motivo / impacto / quem decidiu
- Comparação usa apenas 1 palavra (escolhida/editada pelo usuário) / simplifica e melhora precisão do matching / pipeline gira em torno de render-e-comparar uma palavra / Filipe
- Tudo roda localmente, sem serviços externos / privacidade e requisito explícito / restringe stack a ferramentas offline / Filipe

## Estrutura de pastas
```
fontfinder/
├── core/config.py        constantes e cache dir
├── ocr/engine.py         RapidOCR + split de linhas em palavras (fallback Tesseract)
├── fonts/discovery.py    fc-list / scan de diretórios + checagem de glifos
├── fonts/render.py       render da palavra via Pillow
├── matching/preprocess.py  binarização, deskew, normalização, traço
├── matching/features.py    coarse (projeções/Hu) + fine (SSIM/HOG/IoU)
├── matching/pipeline.py    orquestração, multiprocessing (spawn), cache npz
├── ui/                   main_window, image_view, results, theme, workers
└── main.py               entry point (python -m fontfinder.main)
tests/test_matching.py    ground truth com fontes instaladas
run.sh                    launcher
```

## Fluxos principais
1. Usuário envia imagem → OCR segmenta palavras → usuário escolhe 1 palavra (e pode corrigir o texto) → app renderiza essa palavra em todas as fontes instaladas → compara visualmente com o recorte da imagem → exibe ranking de similaridade.

## Dívidas técnicas
- Score conservador (~55% para match exato) — considerar recalibração da escala exibida.
- Split de linha em palavras pode gerar caixas duplicadas/sobrepostas em casos raros (visto com "é" no e2e).
- Descoberta de fontes em Windows/macOS implementada mas não testada (só Linux/fontconfig validado).

## Pontos de atenção
- Fontes decorativas/manuscritas degradam OCR — por isso a edição manual da palavra é essencial (o matching usa o texto digitado, nunca o OCR cru).
- Multiprocessing usa contexto `spawn` (seguro com QThread e Windows); scripts que chamam `match_word` precisam do guard `if __name__ == "__main__"`.
- Suporte a acentuação pt-BR validado (palavra de teste: "Ação"/"coração"); fontes sem os glifos são puladas via cmap.
- `opencv-python-headless` (não o normal) para não conflitar com Qt do PySide6.

## Convenções — versionamento, branches, commits, organização
- SemVer + CHANGELOG.md obrigatórios a partir da primeira entrega de código.

## Histórico
- 2026-06-10 — Sessão inicial: escopo definido, prompt de criação gerado (Claude).
- 2026-06-10 — MVP v0.1.0 implementado e testado (7 testes + e2e + smoke da GUI; fonte original no top 1 do ranking no e2e) (Claude).

## Próximos passos
- Filipe testar a UI com imagens reais (`./run.sh`).
- Calibrar pesos do score fino com casos reais difíceis.

## Backlog
- Comparação multi-palavra / frase inteira
- Detecção de peso/estilo (bold, italic) além da família
- Exportar relatório de matching

## Divisão de trabalho — Codex: / Claude:
- Claude: escopo + prompt inicial. Demais divisões a definir.
