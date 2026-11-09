"""
ROTEADOR DO CHAT - para onde vai cada mensagem e o que vai junto, decidido aqui, sem modelo.

Sem Qt. Antes, com "Conectar ao Hermes", toda mensagem ia para o Hermes (um agente que pesquisa e lembra,
mais lento e caro) e toda mensagem levava o registro recente do pet. Agora:

    pede_hermes(texto)        pesquisa ("pesquisa", "procura", "notícia", "quem é"...), imagem ("me mostra")
                              ou memória do Hermes ("lembra", "anota", "da última vez"): vai para o Hermes.
                              O resto ("oi, Bob", "o que acha disso?") vai direto para o provedor escolhido.
    sobre_o_programa(texto)   a pergunta é sobre o próprio pet ("por que a música parou?", "o que você fez?",
                              "deu erro?"): só então o registro recente (o log dele) vai junto.

São regras simples e explícitas, como as de música e vídeo (ia/musica.py, ia/video.py): uma mensagem que
ninguém reconhece segue o caminho mais barato e rápido.
"""

import re
import unicodedata


def _normal(texto):
    """Minúsculas, sem acento e sem pontuação: 'Você pesquisa?' -> 'voce pesquisa'."""
    texto = unicodedata.normalize("NFKD", texto or "")
    texto = "".join(c for c in texto if not unicodedata.combining(c)).lower()
    return " ".join(re.sub(r"[^\w\s-]", " ", texto).split())


_HERMES = re.compile(
    r"\b(?:pesquis\w*|procur\w*|busc\w*|googl\w*|internet|web|site|noticia\w*|novidade\w*|"
    r"quem (?:e|foi|sao)|o que (?:e|sao|significa)|qual (?:e|foi) o|quando (?:e|foi|sai|saiu|lanca\w*)|"
    r"onde fica|quanto custa|preco|cotacao|previsao|clima|tempo (?:hoje|amanha|agora)|"
    r"mostr\w*|quero ver|foto|imagem|"
    r"lembr\w*|esquec\w*|anot\w*|memoriz\w*|guard\w* (?:isso|que)|ultima vez|semana passada|"
    r"voce sabe (?:que|o que) eu|o que eu (?:te )?(?:disse|falei|contei))\b"
)
_PROGRAMA = re.compile(
    r"\b(?:por ?que (?:a musica|o video|voce|vc|o pet|ele|parou|travou|cortou|sumiu)|"
    r"o que (?:aconteceu|houve|deu)|(?:a musica|o video|o som|o microfone|a voz) (?:parou|cortou|travou|sumiu)|"
    r"(?:parou|cortou|travou|sumiu|falhou|deu erro)|erro|problema|log|registro|"
    r"o que voce (?:fez|fazia|estava fazendo|tocou|ouviu|viu)|voce (?:tocou|ouviu|parou|travou)|"
    r"configura\w*|permiss\w*|pestinha|nao (?:funciona|funcionou|toca|ouve|responde))\b"
)


def pede_hermes(texto):
    """A mensagem pede pesquisa, imagem ou a memória do Hermes."""
    return bool(_HERMES.search(_normal(texto)))


def sobre_o_programa(texto):
    """A pergunta é sobre o próprio pet (o que ele fez, o que parou, um erro): leva o registro recente junto."""
    return bool(_PROGRAMA.search(_normal(texto)))
