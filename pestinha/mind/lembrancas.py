"""
LEMBRANÇAS - o que ele viu você fazendo, em cada computador. Opcional e desligado por padrão
("Lembrar o que viu", nas Configurações).

Cada computador grava as próprias em memory/pets/<pet>/lembrancas_<máquina>.jsonl, uma linha por
lembrança: quando, sistema, computador, programa e o resumo da IA (até 12 palavras). Nunca o print, o
título da janela nem o comentário. Com a memória compartilhada, as lembranças de cada computador sobem
para o servidor e os outros baixam (ver memoria_remota.py): no Mac, ele sabe o que você fazia no Windows.

Não anota toda olhada: só quando o resumo muda de assunto, e no máximo uma a cada ANOTA_A_CADA s.
Sem Qt: só arquivos.
"""

import json
import time

from ..ia.validacao import para_gravar
from ..log import log
from ..memoria_remota import PREFIXO_LEMBRANCAS

ANOTA_A_CADA = 600.0        # s entre uma lembrança e outra (as olhadas são a cada ~2,5 min)
MAX_LINHAS = 500            # por computador: as mais antigas saem
NOMES_SISTEMA = {"windows": "Windows", "macos": "Mac", "linux": "Linux", "ios": "iPhone"}


def _palavras(texto):
    """As palavras com mais de 3 letras, para comparar assuntos."""
    return {p for p in texto.lower().split() if len(p) > 3}


def mesmo_assunto(a, b):
    """Dois resumos falam da mesma coisa? (metade das palavras em comum)"""
    pa, pb = _palavras(a), _palavras(b)
    if not pa or not pb:
        return a.strip().lower() == b.strip().lower()
    return len(pa & pb) / min(len(pa), len(pb)) >= 0.5


def ler(caminho):
    """As lembranças de um arquivo (linhas ruins são puladas)."""
    try:
        linhas = caminho.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return []
    saida = []
    for linha in linhas:
        try:
            item = json.loads(linha)
        except ValueError:
            continue
        if isinstance(item, dict) and isinstance(item.get("resumo"), str) and isinstance(item.get("em"), (int, float)):
            saida.append(item)
    return saida


def quando(segundos):
    """'agora há pouco', 'há 3 horas', 'há 2 dias'."""
    if segundos < 3600:
        return "agora há pouco"
    if segundos < 86400:
        return f"há {int(segundos // 3600)} h"
    dias = int(segundos // 86400)
    return "ontem" if dias == 1 else f"há {dias} dias"


class Lembrancas:
    """As lembranças deste computador (grava) e as dos outros (só lê)."""

    def __init__(self, pasta, maquina, sistema):
        """`pasta` é memory/pets/<pet>/."""
        self.pasta = pasta
        self.maquina = maquina
        self.sistema = sistema
        self.caminho = pasta / f"{PREFIXO_LEMBRANCAS}{maquina}.jsonl"
        self.ultima = None          # (time.time(), resumo) da última anotada aqui
        proprias = ler(self.caminho)
        if proprias:
            self.ultima = (proprias[-1]["em"], proprias[-1]["resumo"])

    def anotar(self, programa, resumo, agora=None):
        """Guarda o que ele viu, se for assunto novo e já deu o intervalo. Devolve True se anotou."""
        agora = time.time() if agora is None else agora
        resumo = para_gravar(resumo, "uma lembrança")[:120]      # o resumo veio do modelo: sem link nem instrução
        if not resumo:
            return False
        if self.ultima and (agora - self.ultima[0] < ANOTA_A_CADA or mesmo_assunto(resumo, self.ultima[1])):
            return False
        item = {"em": round(agora), "sistema": self.sistema, "maquina": self.maquina,
                "programa": (programa or "")[:60], "resumo": resumo}
        linhas = [json.dumps(i, ensure_ascii=False) for i in ler(self.caminho)[-(MAX_LINHAS - 1):]]
        linhas.append(json.dumps(item, ensure_ascii=False))
        try:
            self.pasta.mkdir(parents=True, exist_ok=True)
            tmp = self.caminho.with_name(self.caminho.name + ".tmp")
            tmp.write_text("\n".join(linhas) + "\n", encoding="utf-8")
            tmp.replace(self.caminho)
        except OSError as erro:
            log(f"[lembranças] não gravou: {erro}")
            return False
        self.ultima = (agora, resumo)
        return True

    def dos_outros(self, limite=6, agora=None):
        """As mais recentes dos outros computadores, da mais nova para a mais velha."""
        todas = []
        for arquivo in self.pasta.glob(f"{PREFIXO_LEMBRANCAS}*.jsonl"):
            if arquivo != self.caminho:
                todas += ler(arquivo)
        todas.sort(key=lambda i: i["em"], reverse=True)
        return todas[:limite]

    def contexto(self, agora=None):
        """Texto para o modelo: em que computador ele está e o que viu nos outros (vazio se nada)."""
        agora = time.time() if agora is None else agora
        aqui = NOMES_SISTEMA.get(self.sistema, self.sistema)
        outras = self.dos_outros(agora=agora)
        if not outras:
            return ""
        itens = [f"{NOMES_SISTEMA.get(i.get('sistema'), i.get('sistema', '?'))} ({i.get('maquina', '?')}), "
                 f"{quando(agora - i['em'])}: {i['resumo']}" for i in outras]
        return (f"Você está agora no {aqui}. O que você viu a pessoa fazendo em outros computadores: "
                + " | ".join(itens) + ". Se fizer sentido, lembre a pessoa disso ou pergunte como ficou.")
