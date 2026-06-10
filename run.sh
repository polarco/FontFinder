#!/usr/bin/env bash
# Inicia o FontFinder usando o venv do projeto.
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
    echo "Ambiente não encontrado. Crie com:"
    echo "  uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -r requirements.txt"
    exit 1
fi
exec .venv/bin/python -m fontfinder.main "$@"
