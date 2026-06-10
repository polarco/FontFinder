# Changelog

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/);
versionamento [SemVer](https://semver.org/lang/pt-BR/).

## [0.3.0] — 2026-06-10

### Melhorado
- **OCR muito mais preciso para português:** modelo de reconhecimento trocado
  para PP-OCRv5 LATINO (dicionário com acentuação completa) — antes o modelo
  ch/en perdia acentos ("coracao"); agora lê "coração" com 99,9% de confiança.
- Caixas por palavra vêm direto do modelo (`return_word_box`), substituindo a
  segmentação heurística por projeção.
- OCR multi-passada para imagens difíceis: original + ampliada com CLAHE +
  binarizada, com fusão dos resultados por sobreposição.
- Matching: alinhamento horizontal por correlação antes da comparação e nova
  métrica de chamfer (tolerante a deformações — melhor em fontes decorativas).
- Score recalibrado para escala perceptual: match exato ≈ 95%, candidato
  razoável ≈ 75%, fonte errada < 20% (antes um match exato mostrava ~55%).
- Re-ranking fino agora considera 100 candidatas (antes 60).
- Benchmark interno: 8/9 fontes difíceis (serif, script, mono, condensed) no
  top 3 sob degradação de foto; acentos preservados no OCR.

### Adicionado
- Testes de OCR (acentuação pt-BR, caixas plausíveis, imagem ruidosa).

## [0.2.0] — 2026-06-10

### Adicionado
- Distribuição para Windows: `FontFinder.spec` (PyInstaller, onefile, sem
  console) e workflow do GitHub Actions que compila o `FontFinder.exe` num
  runner Windows, roda os testes e anexa o executável às releases (tags `v*`).
- `multiprocessing.freeze_support()` no entry point (obrigatório no
  executável congelado para o pool de workers do matching).

## [0.1.0] — 2026-06-10

### Adicionado
- Interface desktop PySide6 com tema escuro/claro, drag-and-drop, colar do
  clipboard (Ctrl+V) e abertura por diálogo.
- OCR offline em português (RapidOCR/PP-OCR; fallback Tesseract se instalado)
  com segmentação palavra por palavra e caixas clicáveis sobre a imagem.
- Seleção manual por arraste quando o OCR erra a segmentação; campo de texto
  editável para corrigir a palavra reconhecida.
- Descoberta de fontes instaladas via fontconfig (Linux) com fallback de
  varredura de diretórios (Windows/macOS), com cache.
- Pipeline de matching em duas etapas: filtro coarse (projeções, densidade,
  momentos de Hu) + re-ranking fino (SSIM multi-escala, HOG, IoU) com
  normalização de espessura de traço e deskew/binarização robustos.
- Paralelização por processos e cache de renders/features em
  `~/.cache/fontfinder/`.
- Ranking top 20 com previews lado a lado e diálogo de comparação ampliada.
- Testes do pipeline usando fontes instaladas como ground truth (render limpo
  no top 3; render degradado tipo foto no top 5).
