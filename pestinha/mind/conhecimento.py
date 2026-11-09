"""
CONHECIMENTO - o que ele aprendeu assistindo vídeos com você, guardado para conversar sobre isso depois.

Cada vídeo resumido (mind/video_ctl.py) vira uma linha em memory/pets/<pet>/conhecimento.jsonl: quando,
quanto tempo vocês assistiram, o título, o resumo e os pontos para lembrar. Nunca o áudio nem a
transcrição. Com a memória compartilhada, o arquivo vai junto para os outros computadores
(memoria_remota.py).

No chat, `contexto(texto)` entra na mensagem: os títulos mais recentes e, se a sua pergunta parecer ser
sobre um deles, o resumo e os pontos daquele. Sem Qt: só arquivos.
"""

import json
import time

from ..ia.validacao import para_gravar
from ..log import log
from .lembrancas import _palavras, quando

MAX_LINHAS = 300            # vídeos guardados: os mais antigos saem
RECENTES = 4                # títulos que sempre vão para o chat
PARECIDO = 0.34             # fração das palavras do título/resumo que precisa aparecer na sua pergunta


def ler(caminho):
    """Os itens do arquivo (linhas ruins são puladas)."""
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
        if (isinstance(item, dict) and isinstance(item.get("resumo"), str) and item["resumo"].strip()
                and isinstance(item.get("em"), (int, float))):
            item["titulo"] = item.get("titulo") if isinstance(item.get("titulo"), str) else ""
            pontos = item.get("pontos")
            item["pontos"] = [p for p in pontos if isinstance(p, str)] if isinstance(pontos, list) else []
            saida.append(item)
    return saida


class Conhecimento:
    """O arquivo de conhecimento de um pet."""

    def __init__(self, caminho, maquina=""):
        """`caminho` é memory/pets/<pet>/conhecimento.jsonl."""
        self.caminho = caminho
        self.maquina = maquina

    def todos(self):
        """Do mais velho para o mais novo."""
        return ler(self.caminho)

    def guardar(self, aprendizado, duracao=0.0, agora=None):
        """Grava um vídeo resumido. Devolve True se gravou."""
        if aprendizado.vazio():
            return False
        # o resumo veio do modelo, a partir do que foi dito no vídeo: sem link nem instrução antes de gravar
        resumo = para_gravar(aprendizado.resumo, "o resumo de um vídeo")
        if not resumo:
            return False
        pontos = [p for p in (para_gravar(p, "um ponto de um vídeo") for p in aprendizado.pontos) if p]
        agora = time.time() if agora is None else agora
        item = {"em": round(agora), "fonte": "video", "duracao": round(max(0.0, duracao)),
                "maquina": self.maquina, "titulo": para_gravar(aprendizado.titulo, "o título de um vídeo") or "um vídeo",
                "resumo": resumo, "pontos": pontos}
        linhas = [json.dumps(i, ensure_ascii=False) for i in self.todos()[-(MAX_LINHAS - 1):]]
        linhas.append(json.dumps(item, ensure_ascii=False))
        try:
            self.caminho.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.caminho.with_name(self.caminho.name + ".tmp")
            tmp.write_text("\n".join(linhas) + "\n", encoding="utf-8")
            tmp.replace(self.caminho)
        except OSError as erro:
            log(f"[conhecimento] não gravou: {erro}")
            return False
        log(f"[conhecimento] guardei: {item['titulo']}")
        return True

    def sobre(self, texto, itens=None):
        """O item de que a sua mensagem parece falar (palavras do título ou do resumo), ou None."""
        pergunta = _palavras(texto or "")
        if not pergunta:
            return None
        melhor, nota = None, 0.0
        for item in reversed(self.todos() if itens is None else itens):
            titulo = _palavras(item["titulo"])
            alvo = titulo | _palavras(" ".join(item["pontos"]))
            if not alvo:
                continue
            comum = len(pergunta & alvo)
            parecido = max(comum / max(1, min(len(pergunta), len(alvo))),
                           len(pergunta & titulo) / max(1, len(titulo)) if titulo else 0.0)
            if comum and parecido > nota:
                melhor, nota = item, parecido
        return melhor if nota >= PARECIDO else None

    def contexto(self, texto="", agora=None):
        """Texto para o modelo: os vídeos recentes e, se for o assunto da mensagem, o que ele aprendeu daquele."""
        agora = time.time() if agora is None else agora
        itens = self.todos()
        if not itens:
            return ""
        recentes = itens[-RECENTES:][::-1]
        partes = ["Vídeos que você assistiu com a pessoa: "
                  + " | ".join(f"«{i['titulo']}» ({quando(agora - i['em'])})" for i in recentes) + "."]
        alvo = self.sobre(texto, itens)
        if alvo is not None:
            pontos = "; ".join(alvo["pontos"])
            partes.append(f"Do vídeo «{alvo['titulo']}» você aprendeu: {alvo['resumo']}"
                          + (f" Pontos: {pontos}." if pontos else ""))
        return " ".join(partes)
