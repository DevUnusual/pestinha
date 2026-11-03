"""
VOZ - a sua fala vira texto pelo serviço de voz (servidor/voz/), no formato da API de áudio da OpenAI.

Sem Qt: só bytes de áudio e HTTP. As chamadas bloqueiam: quem chama roda numa thread (ver
mind/voz_ctl.py). Ele não fala: a resposta continua em texto, no chat e no balão.
    ClienteVoz.transcrever(wav)   fala -> texto      (POST /v1/audio/transcriptions)
    testar_voz(endereco)          o serviço responde?
    wav_de_pcm                    PCM 16 bits -> WAV
    para_mono16                   o que o microfone entregou -> PCM 16 bits mono

Nada é gravado em disco: o áudio vai pela memória.
"""

import io
import json
import urllib.error
import urllib.request
import uuid
import wave

import numpy as np

from .provedores import ErroIA, endereco_de

PORTA_VOZ = 11500
VOZ_URL_PADRAO = "http://localhost:11500"     # este computador; o servidor da rede vai em "Servidor da voz"
TEMPO_LIMITE = 30.0         # s por chamada


def endereco_voz(texto):
    """'192.168.3.250' -> 'http://192.168.3.250:11500'. Vazio vira este computador; inválido vira None."""
    return endereco_de(texto, PORTA_VOZ, VOZ_URL_PADRAO)


def wav_de_pcm(pcm, taxa, canais=1):
    """PCM 16 bits -> arquivo WAV (em bytes)."""
    saida = io.BytesIO()
    with wave.open(saida, "wb") as w:
        w.setnchannels(canais)
        w.setsampwidth(2)
        w.setframerate(int(taxa))
        w.writeframes(pcm)
    return saida.getvalue()


def para_mono16(dados, formato, canais):
    """Amostras do microfone ('int16', 'int32', 'float' ou 'uint8', intercaladas) -> PCM 16 bits mono."""
    tipos = {"int16": "<i2", "int32": "<i4", "float": "<f4", "uint8": "u1"}
    if formato not in tipos:
        raise ValueError(f"formato de áudio desconhecido: {formato}")
    largura = np.dtype(tipos[formato]).itemsize * max(1, canais)
    a = np.frombuffer(dados[:len(dados) - len(dados) % largura], dtype=tipos[formato]).astype(np.float32)
    if formato == "int16":
        a /= 32768.0
    elif formato == "int32":
        a /= 2147483648.0
    elif formato == "uint8":
        a = (a - 128.0) / 128.0
    if canais > 1:
        a = a.reshape(-1, canais).mean(axis=1)
    return (np.clip(a, -1.0, 1.0) * 32767).astype("<i2").tobytes()


def duracao(pcm, taxa, canais=1):
    """Segundos de áudio em PCM 16 bits."""
    return len(pcm) / (2 * canais * taxa) if taxa else 0.0


def testar_voz(endereco, tempo=3.0):
    """(deu_certo, mensagem): o serviço de voz responde nesse endereço?"""
    base = endereco_voz(endereco)
    if base is None:
        return False, "endereço inválido (exemplo: 192.168.0.10 ou http://192.168.0.10:11500)"
    try:
        with urllib.request.urlopen(f"{base}/health", timeout=tempo) as resposta:
            dados = json.loads(resposta.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError):
        return False, f"o serviço de voz não respondeu em {base} (ligado? aceita conexões da rede?)"
    if not isinstance(dados, dict) or not dados.get("whisper"):
        return False, f"{base} respondeu, mas não parece o serviço de voz do Pestinha"
    return True, f"Serviço de voz respondeu em {base} (Whisper {dados['whisper']})."


class ClienteVoz:
    """Fala com o serviço de voz pelo formato da OpenAI (/v1/audio/transcriptions)."""

    def __init__(self, endereco):
        """`endereco` como a pessoa escreveu (vazio: este computador)."""
        base = endereco_voz(endereco)
        if base is None:
            raise ErroIA(f"endereço do serviço de voz inválido: {endereco!r}")
        self.base = base

    def transcrever(self, wav, dica=""):
        """WAV da sua fala -> texto. `dica` ajuda o modelo com nomes (o nome do pet)."""
        fronteira = uuid.uuid4().hex
        partes = []
        for nome, valor in (("model", "whisper-1"), ("language", "pt"), ("prompt", dica)):
            partes.append(f'--{fronteira}\r\nContent-Disposition: form-data; name="{nome}"\r\n\r\n{valor}\r\n')
        cabeca = (f'--{fronteira}\r\nContent-Disposition: form-data; name="file"; filename="fala.wav"\r\n'
                  "Content-Type: audio/wav\r\n\r\n")
        corpo = ("".join(partes) + cabeca).encode("utf-8") + wav + f"\r\n--{fronteira}--\r\n".encode("ascii")
        pedido = urllib.request.Request(f"{self.base}/v1/audio/transcriptions", data=corpo,
                                        headers={"Content-Type": f"multipart/form-data; boundary={fronteira}"})
        try:
            with urllib.request.urlopen(pedido, timeout=TEMPO_LIMITE) as resposta:
                texto = json.loads(resposta.read().decode("utf-8")).get("text", "")
        except urllib.error.HTTPError as erro:
            raise ErroIA(f"o serviço de voz respondeu com erro {erro.code}") from erro
        except (urllib.error.URLError, OSError) as erro:
            raise ErroIA(f"o serviço de voz não respondeu em {self.base} (está ligado?)") from erro
        except (ValueError, AttributeError) as erro:
            raise ErroIA("o serviço de voz mandou uma resposta estranha") from erro
        return " ".join(str(texto or "").split())
