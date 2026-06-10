# FontFinder

Programa desktop que identifica qual fonte **instalada no seu computador** é
mais parecida com o texto de uma imagem. Tudo roda 100% local — nenhuma imagem
sai da sua máquina.

## Como funciona

1. Abra uma imagem (botão, arrastar-e-soltar ou Ctrl+V).
2. O OCR (português, com acentos) detecta e segmenta o texto **palavra por
   palavra**, desenhando caixas clicáveis sobre a imagem.
3. Clique na palavra que quer usar na comparação — ou **arraste** sobre a
   imagem para selecionar manualmente, caso o OCR tenha errado a segmentação.
4. Confira o texto reconhecido no campo "Palavra" e **corrija se necessário**
   (o matching usa o texto digitado, não o OCR).
5. Clique em **Comparar fontes**: o app renderiza a palavra em todas as fontes
   instaladas e mostra o ranking das mais parecidas, com preview lado a lado.
6. Clique num resultado para ver a comparação ampliada.

## Instalação

Requer Python 3.10+ (recomendado 3.12).

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Ou, com [uv](https://docs.astral.sh/uv/):

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r requirements.txt
```

### Windows (executável pronto)

Baixe o `FontFinder.exe` na página de
[Releases](../../releases) do repositório — não precisa instalar Python nem
dependências. O `.exe` é gerado automaticamente pelo GitHub Actions
(workflow `build-windows.yml`) a cada tag `v*`.

> Na primeira execução o Windows SmartScreen pode avisar que o app não é
> assinado — clique em "Mais informações" → "Executar assim mesmo".

## Uso

```bash
./run.sh
# ou
.venv/bin/python -m fontfinder.main
```

## Testes

```bash
.venv/bin/python -m pytest tests/
```

Os testes usam as fontes instaladas como ground truth: renderizam uma palavra
("Ação") numa fonte conhecida, simulam degradação de foto (ruído, contraste
baixo, borrão) e verificam que o pipeline devolve a fonte original no topo do
ranking.

## Arquitetura

```
fontfinder/
├── core/       configurações e cache
├── ocr/        detecção de palavras (RapidOCR offline; fallback Tesseract)
├── fonts/      descoberta (fontconfig/scan) e renderização das fontes
├── matching/   pré-processamento, features e pipeline de comparação
└── ui/         interface PySide6 (tema escuro/claro)
```

O matching é feito em duas etapas:

- **Coarse:** features baratas (proporção, densidade de tinta, perfis de
  projeção, momentos de Hu) descartam a maioria das fontes rapidamente.
- **Fine:** as ~60 melhores passam por re-ranking com SSIM multi-escala +
  HOG + IoU de tinta, com normalização de espessura de traço (tolera
  diferenças de peso bold/regular).

Renders e features ficam em cache em `~/.cache/fontfinder/`, então
comparações repetidas da mesma palavra são quase instantâneas.

## Limitações conhecidas

- O score é conservador: um match exato fica na faixa de ~55%, não 100%.
  O que importa é a **ordem** do ranking.
- Fontes que não têm os glifos da palavra (ex.: símbolos, ícones) são puladas
  automaticamente.
- O OCR pode errar acentos em fontes decorativas — por isso o campo de texto
  é editável.
