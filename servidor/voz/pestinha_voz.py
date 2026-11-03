"""
PESTINHA-VOZ - serviço pequeno que transforma a sua fala em texto para o Pestinha, no formato da API de
áudio da OpenAI.

    POST /v1/audio/transcriptions   fala -> texto (faster-whisper large-v3-turbo na placa de vídeo)
    GET  /health                    está vivo? (e se o Whisper está carregado)

Feito para dividir a máquina com outras coisas (um servidor de jogo, o Ollama):
    - um pedido por vez (uma trava), com poucos threads de CPU;
    - o Whisper só entra na placa no primeiro pedido e sai depois de OCIOSO_WHISPER s sem uso;
    - nada é gravado em disco: o áudio que chega fica só na memória.

Rodar: PESTINHA_VOZ_MODELOS=~/pestinha-voz/modelos uvicorn pestinha_voz:app --host 0.0.0.0 --port 11500
"""

import gc
import io
import os
import threading
import time
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse, Response

MODELOS = Path(os.environ.get("PESTINHA_VOZ_MODELOS", "~/pestinha-voz/modelos")).expanduser()
OCIOSO_WHISPER = float(os.environ.get("PESTINHA_VOZ_OCIOSO", "600"))   # s até tirar o Whisper da placa
TIPO_WHISPER = os.environ.get("PESTINHA_VOZ_WHISPER_TIPO", "int8_float16")
MAX_AUDIO = 10 * 1024 * 1024        # bytes de áudio por pedido (~5 min de WAV 16 kHz)

app = FastAPI(title="pestinha-voz")
_trava = threading.Lock()
_whisper = {"modelo": None, "usado": 0.0}


def _whisper_modelo():
    """O Whisper, carregado na placa no primeiro uso."""
    if _whisper["modelo"] is None:
        from faster_whisper import WhisperModel
        _whisper["modelo"] = WhisperModel(str(MODELOS / "whisper-large-v3-turbo"), device="cuda",
                                          compute_type=TIPO_WHISPER, cpu_threads=2)
    _whisper["usado"] = time.monotonic()
    return _whisper["modelo"]


def _vigia_whisper():
    """Tira o Whisper da placa depois de um tempo sem uso (a VRAM volta para o Ollama)."""
    while True:
        time.sleep(30)
        with _trava:
            if _whisper["modelo"] is not None and time.monotonic() - _whisper["usado"] > OCIOSO_WHISPER:
                _whisper["modelo"] = None
                gc.collect()


threading.Thread(target=_vigia_whisper, daemon=True).start()


@app.get("/health")
def saude():
    """Vivo, e se o Whisper está na placa agora."""
    return {"ok": True, "whisper": "large-v3-turbo", "whisper_carregado": _whisper["modelo"] is not None}


@app.post("/v1/audio/transcriptions")
def transcrever(file: UploadFile = File(...), model: str = Form("whisper-1"), language: str = Form("pt"),
                prompt: str = Form(""), response_format: str = Form("json")):
    """Fala -> texto (como a OpenAI: devolve {"text": ...}, ou texto puro com response_format=text)."""
    dados = file.file.read(MAX_AUDIO + 1)
    if not dados:
        raise HTTPException(400, "áudio vazio")
    if len(dados) > MAX_AUDIO:
        raise HTTPException(413, "áudio grande demais")
    with _trava:
        try:
            segmentos, _info = _whisper_modelo().transcribe(
                io.BytesIO(dados), language=(language or "pt")[:5], beam_size=1, vad_filter=True,
                vad_parameters={"speech_pad_ms": 500},      # não corta o começo da primeira palavra
                initial_prompt=prompt[:200] or None, condition_on_previous_text=False)
            texto = " ".join(s.text.strip() for s in segmentos).strip()
        except Exception as erro:          # áudio corrompido ou formato que o decodificador não lê
            raise HTTPException(400, f"não deu para ler o áudio: {type(erro).__name__}") from erro
    if response_format == "text":
        return Response(texto, media_type="text/plain; charset=utf-8")
    return JSONResponse({"text": texto})
