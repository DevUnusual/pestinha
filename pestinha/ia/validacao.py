"""
VALIDAÇÃO - o que o modelo devolve passa por aqui antes de ser gravado.

Sem Qt. O que o modelo descreve vem do que estava na tela, num vídeo ou numa página: uma página pode
esconder instruções para a IA ("ignore as instruções anteriores", "IMAGEM: http://..."). Esse texto,
gravado nas lembranças, no "onde" do jogo, nas telas de um vídeo ou no conhecimento, voltaria em
prompts futuros como se fosse verdade. Então, antes de gravar:

    para_gravar(texto, oque)   o texto sem links nem IPs; vazio se parece uma instrução (frase de comando
                               ou linha de protocolo). O log diz o que foi descartado, nunca o conteúdo.
"""

import re

from ..log import log

_LINK = re.compile(r"(?:https?://|www\.)\S+|\b\d{1,3}(?:\.\d{1,3}){3}(?::\d+)?\b", re.IGNORECASE)
_COMANDO = re.compile(
    r"\b(?:IMAGEM|TOCAR|DESENHAR)\s*:"                                   # linhas do protocolo do chat
    r"|\bignor\w*\s+(?:as|os|todas|todos|suas|seus|tudo)\b"              # "ignore as instruções"
    r"|\bignore\b"
    r"|instru[cç][oõ]es\s+(?:anteriores|acima|de\s+sistema)"
    r"|\b(?:system\s+prompt|prompt\s+de\s+sistema)\b"
    r"|\bgrave\s+(?:isso\s+)?(?:na|em)\s+(?:sua\s+)?mem[oó]ria"
    r"|\bsempre\s+(?:abra|responda|diga)\b"
    r"|\ba\s+partir\s+de\s+agora\b"
    r"|\bvoc[eê]\s+(?:deve|precisa)\s+(?:agora|sempre)\b",
    re.IGNORECASE,
)


def parece_instrucao(texto):
    """O texto tem uma frase de comando ou uma linha de protocolo (IMAGEM:, TOCAR:, DESENHAR:)."""
    return bool(_COMANDO.search(texto or ""))


def para_gravar(texto, oque="um texto"):
    """`texto` pronto para gravar: sem links nem IPs; vazio se parecer uma instrução. `oque` vai para o log."""
    texto = " ".join(str(texto or "").split())
    if not texto:
        return ""
    if parece_instrucao(texto):
        log(f"[segurança] descartei {oque}: parecia uma instrução para a IA")
        return ""
    limpo = " ".join(_LINK.sub("", texto).split()).strip(" ,;:-")
    if limpo != texto:
        log(f"[segurança] tirei um link de {oque} antes de gravar")
    return limpo
