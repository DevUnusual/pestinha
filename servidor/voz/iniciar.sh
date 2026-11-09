#!/bin/sh
# Sobe o pestinha-voz com as bibliotecas da CUDA que vieram pelo pip (sem instalar nada no sistema).
cd "$(dirname "$0")"
SP=$(.venv/bin/python -c "import site; print(site.getsitepackages()[0])")
export LD_LIBRARY_PATH="$SP/nvidia/cublas/lib:$SP/nvidia/cudnn/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
exec .venv/bin/uvicorn pestinha_voz:app --host 0.0.0.0 --port "${PESTINHA_VOZ_PORTA:-11500}" --workers 1
