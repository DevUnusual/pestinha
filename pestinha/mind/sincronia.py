"""
SINCRONIA - a rede neural e o modelo de IA falando a mesma língua.

A rede é quem sente; o modelo é quem fala. Os dois ficam em sincronia nos dois sentidos:
    rede -> IA    a cada pedido (olhada ou chat), o estado atual da rede vira um bloco de texto:
                  emoção, o que os motores querem, necessidades, protesto e o porquê, castigo e o
                  que ele já enjoou. O temperamento (pets/<pet>.json) entra uma vez, no prompt do sistema.
    IA -> rede    o que o modelo viu na tela volta como canais VISAO_* (ver ia/mente.py) e a conversa
                  como o canal CONVERSA (ver mind/visao.py).

Sem Qt: só lê atributos do app, para dar para testar com um app de mentira.
"""

from ..config import EMOTION_NAMES
from ..core.protesto import STAGE_NAMES
from ..core.rotulos import nome_canal

# o que cada motor "quer", na voz dele (só entram os que estão bem ativos)
VONTADES = {
    "WANDER": "vontade de passear",
    "WATCH": "de olho no cursor",
    "CHEER": "animado, com vontade de pular",
    "STARTLE": "assustado",
    "DROWSE": "com sono",
    "ANGRY": "irritado",
    "SAD": "pra baixo",
    "SETTLE": "sossegado",
}
TRISTEZA = {1: "com saudade de atenção", 2: "chorando de solidão", 3: "se sentindo abandonado"}
VONTADE_MINIMA = 0.45           # tom do motor (0..1) a partir do qual ele "sente" aquilo
ENJOADO = 0.5                   # eficácia da sinapse abaixo disso: ele já enjoou daquele estímulo


def _nivel(valor, baixo, alto):
    """Uma palavra para um valor de 0 a 1."""
    return baixo if valor < 0.3 else alto if valor > 0.7 else "médio"


def descrever_temperamento(temperamento):
    """
    O temperamento do pets/<pet>.json em frases. Ganho de interneurônio ("CURIOUS": 1.3) é um traço;
    ganho de ligação ("DISMISS->FRUSTRATION": 1.3) é uma reação. Só o que foge do normal entra.
    """
    tracos, reacoes = [], []
    for chave, ganho in sorted((temperamento or {}).items()):
        if 0.8 <= ganho <= 1.2:
            continue
        forte = ganho > 1.2
        if "->" in chave:
            pre, pos = chave.split("->", 1)
            reacoes.append(f"{nome_canal(pre)} -> {nome_canal(pos)} ({'forte' if forte else 'fraco'})")
        else:
            tracos.append(f"{nome_canal(chave)} {'alta' if forte else 'baixa'}")
    partes = []
    if tracos:
        partes.append("Seu temperamento (da sua rede neural): " + ", ".join(tracos) + ".")
    if reacoes:
        partes.append("O que mexe com você mais ou menos que o normal: " + "; ".join(reacoes) + ".")
    return " ".join(partes)


def estado_agora(app):
    """O estado da rede e do corpo agora, em poucas linhas, para o modelo falar a partir dele."""
    linhas = []
    emocao = EMOTION_NAMES.get(app.pet_state.emotion, app.pet_state.emotion).lower()
    emo = app.emotion
    linhas.append(f"emoção: {emocao} (valência {emo.valence:+.1f}, ativação {emo.arousal:+.1f})")

    tom = app.behavior.tone.r
    vontades = [VONTADES[m] for m, r in sorted(tom.items(), key=lambda item: -item[1])
                if r >= VONTADE_MINIMA and m in VONTADES]
    if vontades:
        linhas.append("seu corpo agora: " + ", ".join(vontades[:3]))

    d = app.drives
    linhas.append(f"energia {_nivel(d.energy, 'baixa', 'alta')}, "
                  f"estímulo {_nivel(d.stimulation, 'entediado', 'agitado')}, "
                  f"carência de contato {_nivel(d.contact, 'baixa', 'alta')}")

    pr = app.protest
    if pr.stage:
        motivos = pr.motivos_recentes()
        porque = f" porque {' e '.join(motivos[-2:])}" if motivos else " de tanto acumular irritação"
        linhas.append(f"protesto: {STAGE_NAMES[pr.stage]}{porque}")
    if app.sad.stage:
        linhas.append(f"tristeza: {TRISTEZA[app.sad.stage]}")
    castigo = app.castigo
    if castigo.dentro:
        linhas.append("você está preso no cantinho do castigo")
    elif castigo.rancor > 0.3:
        linhas.append("ainda com rancor do cantinho do castigo")

    eficacia = app.brain.efficacy()
    enjoos = [nome_canal(c) for c, e in eficacia.items() if e < ENJOADO]
    if enjoos:
        linhas.append("já enjoou de: " + ", ".join(enjoos[:4]))
    if app.asleep:
        linhas.append("você estava dormindo")
    return "; ".join(linhas)
