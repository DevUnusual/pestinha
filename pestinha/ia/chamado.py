"""
CHAMADO - a palavra de chamado ("Bob!"), como na Alexa: um reconhecedor pequeno (Vosk) roda neste
computador e só procura o nome do pet. Nada sai do computador até ele ouvir o nome.

Sem Qt: só áudio em bytes, o Vosk e HTTP (para baixar o modelo uma vez). Quem abre o microfone e manda
o pedido para o serviço de voz é mind/chamado_ctl.py.
    modelo_baixado / baixar_modelo   o modelo pequeno de português (~31 MB), em memory/modelos/, uma vez só
    grafias(palavra)                 'bob' -> 'bob', 'bóbi', 'bobi'...: as que o modelo conhece viram alvo
    Detector                         recebe o áudio aos pedaços e diz quando ouviu o nome (Deteccao)
    Escuta                           depois do nome: guarda a sua fala até você parar (pelo volume)

Por que uma gramática com iscas: com só [nome, desconhecido], o Vosk força tudo o que soa parecido
("bola", "bom", "bottle") a virar o nome. Com palavras parecidas na lista, elas absorvem esses sons e o
nome só sai quando é ele mesmo.
"""

import json
import shutil
import unicodedata
import urllib.request
import zipfile
from collections import deque
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .provedores import ErroIA

MODELO = "vosk-model-small-pt-0.3"
MODELO_URL = f"https://alphacephei.com/vosk/models/{MODELO}.zip"
CONFIANCA = 0.7             # 0..1: abaixo disso não é o nome (só ruído parecido)
DEPOIS_DO_NOME = 0.45       # s de fala depois do nome, na mesma frase: o pedido já veio junto
ANTES = 0.25                # s antes do nome que vão junto no pedido (o começo da palavra)
GUARDA = 30.0               # s de áudio guardados para recortar o pedido que veio junto
LIMIAR_FALA = 0.012         # RMS (0..1): acima disso é fala
SILENCIO_FIM = 1.1          # s de silêncio depois de falar: terminou o pedido
ESPERA_FALA = 5.0           # s esperando você começar a falar depois do nome
MAX_PEDIDO = 15.0           # s no máximo de pedido

# Palavras comuns que soam parecido com nomes curtos: absorvem os falsos chamados
ISCAS = ("bobo", "boba", "bom", "boa", "bola", "bolo", "bota", "bote", "pode", "bebê", "brian", "bryan",
         "jorge", "gorro", "porco", "povo", "pobre", "olha", "oi", "ok", "você", "isso", "esse", "aqui",
         "então", "sim", "não", "agora", "vou", "vai", "bora", "lobo", "rabo", "toda", "dois", "doce",
         "bíblia", "boby", "beto", "bento", "bebo", "bem", "bate", "pare", "para", "sobe", "sabe",
         "nove", "noite", "dia", "obrigado", "tchau")


def _sem_acento(texto):
    texto = unicodedata.normalize("NFD", texto)
    return "".join(c for c in texto if unicodedata.category(c) != "Mn")


def grafias(palavra):
    """
    Jeitos de escrever o nome como o modelo em português ouviria: o próprio nome, sem acento e, se termina
    em consoante, com o 'i'/'e' que a gente fala no fim ('bob' -> 'bóbi'). Só as que o modelo conhece valem.
    """
    base = " ".join((palavra or "").lower().split())
    if not base or " " in base:
        return [base] if base else []
    saida = [base, _sem_acento(base)]
    if base[-1] not in "aeiouáéíóúâêôãõ":
        for fim in ("i", "e"):
            saida.append(base + fim)
            for i, letra in enumerate(base):                 # a sílaba forte com acento: 'bóbi', 'jórgi'
                if letra in "aeiou":
                    acento = {"a": "á", "e": "é", "i": "í", "o": "ó", "u": "ú"}[letra]
                    saida.append(base[:i] + acento + base[i + 1:] + fim)
                    break
    unicas = []
    for g in saida:
        if g and g not in unicas:
            unicas.append(g)
    return unicas


# ---------------- modelo ----------------

def pasta_do_modelo(pasta_modelos):
    """memory/modelos/vosk-model-small-pt-0.3."""
    return Path(pasta_modelos) / MODELO


def modelo_baixado(pasta_modelos):
    """O modelo já está em memory/modelos/ (pasta completa)."""
    pasta = pasta_do_modelo(pasta_modelos)
    return (pasta / "final.mdl").exists() and (pasta / "HCLr.fst").exists()


def baixar_modelo(pasta_modelos, url=MODELO_URL, tempo=60.0):
    """Baixa e descompacta o modelo (uma vez). Bloqueia: rode numa thread. Levanta ErroIA se não der."""
    pasta_modelos = Path(pasta_modelos)
    if modelo_baixado(pasta_modelos):
        return pasta_do_modelo(pasta_modelos)
    pasta_modelos.mkdir(parents=True, exist_ok=True)
    zip_tmp = pasta_modelos / f"{MODELO}.zip.tmp"
    destino_tmp = pasta_modelos / f"{MODELO}.tmp"
    try:
        with urllib.request.urlopen(url, timeout=tempo) as resposta, open(zip_tmp, "wb") as saida:
            shutil.copyfileobj(resposta, saida)
        shutil.rmtree(destino_tmp, ignore_errors=True)
        with zipfile.ZipFile(zip_tmp) as z:
            for nome in z.namelist():                    # nada fora da pasta do modelo
                alvo = (destino_tmp / nome).resolve()
                if not str(alvo).startswith(str(destino_tmp.resolve())):
                    raise ErroIA("o arquivo do modelo de voz veio estranho (caminho fora da pasta)")
            z.extractall(destino_tmp)
        interna = destino_tmp / MODELO
        if not (interna / "final.mdl").exists():
            raise ErroIA("o arquivo do modelo de voz veio incompleto")
        final = pasta_do_modelo(pasta_modelos)
        shutil.rmtree(final, ignore_errors=True)
        interna.replace(final)
        return final
    except ErroIA:
        raise
    except (OSError, zipfile.BadZipFile, ValueError) as erro:
        raise ErroIA(f"não consegui baixar o modelo de voz ({type(erro).__name__}: {erro})") from erro
    finally:
        zip_tmp.unlink(missing_ok=True)
        shutil.rmtree(destino_tmp, ignore_errors=True)


def carregar_modelo(pasta_modelos):
    """O modelo do Vosk (precisa estar baixado). Levanta ErroIA se o Vosk não estiver instalado ou falhar."""
    try:
        import vosk
    except Exception as erro:
        raise ErroIA("para chamar pelo nome, instale o pacote vosk (pip install vosk)") from erro
    vosk.SetLogLevel(-1)
    try:
        return vosk.Model(str(pasta_do_modelo(pasta_modelos)))
    except Exception as erro:
        raise ErroIA(f"o modelo de voz não abriu ({erro})") from erro


def conhece(modelo, palavra):
    """O modelo tem essa palavra no vocabulário?"""
    try:
        return modelo.vosk_model_find_word(palavra) >= 0
    except Exception:
        return False


# ---------------- detectar ----------------

@dataclass(frozen=True)
class Deteccao:
    """Ouviu o nome. Tempos em segundos desde o começo da escuta."""
    inicio: float           # começo da palavra
    fim: float              # fim da palavra
    fim_frase: float        # fim da última palavra da frase (o pedido que veio junto termina aqui)
    confianca: float

    def com_pedido(self):
        """O pedido veio na mesma frase ('Bob, que horas são?')."""
        return self.fim_frase - self.fim >= DEPOIS_DO_NOME


def ler_resultado(texto, alvos, confianca=CONFIANCA):
    """O JSON de um resultado final do Vosk -> Deteccao (a primeira vez que o nome aparece) ou None."""
    try:
        dados = json.loads(texto or "{}")
    except ValueError:
        return None
    palavras = [p for p in dados.get("result", []) if isinstance(p, dict)] if isinstance(dados, dict) else []
    for p in palavras:
        if p.get("word") in alvos and float(p.get("conf", 0.0)) >= confianca:
            fim_frase = max(float(q.get("end", 0.0)) for q in palavras)
            return Deteccao(float(p.get("start", 0.0)), float(p.get("end", 0.0)), fim_frase, float(p["conf"]))
    return None


class Detector:
    """Recebe o áudio (PCM 16 bits mono) e diz quando ouviu o nome; guarda os últimos GUARDA s para recortar."""

    def __init__(self, modelo, palavra, taxa, confianca=CONFIANCA, reconhecedor=None):
        """`modelo` é o do Vosk; `reconhecedor` é para os testes (no lugar do KaldiRecognizer)."""
        self.taxa = int(taxa)
        self.confianca = confianca
        self.alvos = [g for g in grafias(palavra) if reconhecedor is not None or conhece(modelo, g)]
        if not self.alvos:
            raise ErroIA(f'o modelo de voz não conhece "{palavra}": escolha outra palavra de chamado')
        if reconhecedor is None:
            import vosk
            iscas = [i for i in ISCAS if i not in self.alvos and conhece(modelo, i)]
            gramatica = json.dumps(self.alvos + iscas + ["[unk]"], ensure_ascii=False)
            reconhecedor = vosk.KaldiRecognizer(modelo, self.taxa, gramatica)
            reconhecedor.SetWords(True)
        self.reconhecedor = reconhecedor
        self.amostras = 0                                 # quantas amostras já entraram
        self._guarda = deque()
        self._guardadas = 0

    def alimentar(self, pcm):
        """Um pedaço de áudio. Devolve a Deteccao quando uma frase com o nome termina, senão None."""
        if not pcm:
            return None
        self._guarda.append((self.amostras, pcm))
        self.amostras += len(pcm) // 2
        self._guardadas += len(pcm) // 2
        while self._guardadas - len(self._guarda[0][1]) // 2 > GUARDA * self.taxa:
            self._guardadas -= len(self._guarda.popleft()[1]) // 2
        if self.reconhecedor.AcceptWaveform(pcm):
            return ler_resultado(self.reconhecedor.Result(), self.alvos, self.confianca)
        return None

    def recortar(self, inicio, fim):
        """O áudio guardado entre `inicio` e `fim` s (o que sobrou na guarda)."""
        a, b = int(inicio * self.taxa), int(fim * self.taxa)
        partes = []
        for comeco, pcm in self._guarda:
            n = len(pcm) // 2
            de, ate = max(a, comeco), min(b, comeco + n)
            if de < ate:
                partes.append(pcm[(de - comeco) * 2:(ate - comeco) * 2])
        return b"".join(partes)

    def recomecar(self):
        """Esquece a frase em andamento (depois de um pedido, para o nome não ser ouvido de novo)."""
        try:
            self.reconhecedor.Reset()
        except AttributeError:
            pass


def volume(pcm):
    """RMS de 0 a 1 de um pedaço PCM 16 bits."""
    if len(pcm) < 2:
        return 0.0
    a = np.frombuffer(pcm[:len(pcm) - len(pcm) % 2], dtype="<i2").astype(np.float32) / 32768.0
    return float(np.sqrt(np.mean(a * a)))


class Escuta:
    """Depois do nome sozinho: junta a sua fala até você parar (SILENCIO_FIM) ou desistir (ESPERA_FALA)."""

    def __init__(self, taxa, comeco=b""):
        """`comeco`: o nome, que vai junto (o Whisper entende melhor a frase inteira)."""
        self.taxa = int(taxa)
        self.partes = [comeco] if comeco else []
        self.duracao = 0.0
        self.falou = False
        self.silencio = 0.0

    def alimentar(self, pcm):
        """Um pedaço. Devolve 'fim' (terminou de falar), 'desistiu' (não falou nada) ou None (continua)."""
        segundos = len(pcm) / 2 / self.taxa
        self.partes.append(pcm)
        self.duracao += segundos
        if volume(pcm) >= LIMIAR_FALA:
            self.falou, self.silencio = True, 0.0
        else:
            self.silencio += segundos
        if self.falou and (self.silencio >= SILENCIO_FIM or self.duracao >= MAX_PEDIDO):
            return "fim"
        if not self.falou and self.duracao >= ESPERA_FALA:
            return "desistiu"
        return None

    def audio(self):
        return b"".join(self.partes)
