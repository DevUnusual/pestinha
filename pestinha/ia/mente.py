"""
MENTE - o que o pet pergunta ao modelo e como ele entende a resposta.

Sem Qt e sem rede: só texto. Três peças:
    prompt_sistema(...)       quem ele é (nome, persona, temperamento, exemplos de fala de pets/<pet>.json)
    pedido_observacao(...)    "o que a pessoa está fazendo?" -> JSON com resumo, comentário e sinais
    ler_observacao(texto)     o JSON vira uma Observacao (tolerante a texto em volta e campos faltando)
    Conversa                  o histórico curto do chat por texto

Os sinais da observação viram canais sensoriais da rede (VISAO_*): a IA descreve, a rede decide.
"""

import json
import re
from dataclasses import dataclass, field

from ..mathutil import clamp

SINAIS = {
    "graca": "VISAO_GRACA",        # algo engraçado, fofo ou divertido na tela
    "erro": "VISAO_ERRO",          # erro, falha, teste quebrado, algo dando errado
    "foco": "VISAO_FOCO",          # a pessoa concentrada em algo sério
    "novidade": "VISAO_NOVO",      # algo novo ou interessante, diferente do que estava antes
}
MAX_COMENTARIO = 160               # caracteres no balão
MAX_TURNOS = 8                     # mensagens guardadas no chat (só na memória, nunca em disco)

PERSONA_PADRAO = ("Você é um bichinho de tela curioso e brincalhão. Tem opinião própria, é carinhoso "
                  "e às vezes implicante, mas nunca maldoso.")


def prompt_sistema(nome, persona=None, temperamento="", exemplos=(), evitar=()):
    """Quem ele é e as regras de sempre (curto, em português, sem ações de verdade).

    `temperamento` vem da rede (mind/sincronia.py); `exemplos` são falas que mostram o jeito dele;
    `evitar` são frases batidas que ele não deve usar. Os três vêm de pets/<pet>.json.
    """
    partes = [
        f"Você é {nome}, um pet virtual que mora na tela do computador da pessoa (uma telinha com dois "
        "olhos). Nos prints, você aparece como esse bichinho: ignore a si mesmo.",
        persona or PERSONA_PADRAO,
    ]
    if temperamento:
        partes.append(temperamento)
    partes.append(
        "Você tem uma rede neural de verdade: é ela que sente. Cada mensagem traz [Seu estado agora], "
        "lido da rede naquele instante. Fale a partir dele, sem inventar outro humor: se está bravo, "
        "responda bravo; se perguntarem por que, conte o motivo que estiver lá. Se perguntarem do seu "
        "temperamento, use o que está descrito acima, com as suas palavras."
    )
    if exemplos:
        partes.append("Exemplos do seu jeito de falar (não copie, só pegue o tom): "
                      + " | ".join(f'"{e}"' for e in exemplos))
    if evitar:
        partes.append("Nunca diga nada parecido com: " + " | ".join(f'"{e}"' for e in evitar))
    partes.append(
        "Regras: responda sempre em português do Brasil, em no máximo duas frases curtas. Você não "
        "consegue clicar, digitar nem mexer em nada: só observa e conversa. Não repita dados pessoais, "
        "senhas, números ou nomes que aparecerem na tela. Se não entender a tela, diga isso com graça."
    )
    return "\n".join(partes)


def bloco_estado(estado):
    """O estado da rede como prefixo de uma mensagem (vazio se não houver)."""
    return f"[Seu estado agora: {estado}]\n" if estado else ""


def bloco_lembrancas(lembrancas):
    """O que ele viu em outros computadores, como prefixo de uma mensagem (vazio se não houver)."""
    return f"[Suas lembranças: {lembrancas}]\n" if lembrancas else ""


def pedido_observacao(programa, titulo, atividade, emocao, ultimo_resumo="", estado="", ja_disse=(),
                      lembrancas=""):
    """Pergunta da observação periódica. A resposta vem em JSON (ver ler_observacao)."""
    contexto = [f"Programa em primeiro plano: {programa or 'desconhecido'}."]
    if titulo:
        contexto.append(f"Título da janela: {titulo}.")
    contexto.append(f"Categoria: {atividade}. Você está se sentindo: {emocao}.")
    if ultimo_resumo:
        contexto.append(f"Na última olhada, a pessoa estava: {ultimo_resumo}.")
    if ja_disse:
        contexto.append("Você já disse há pouco (não repita nem parafraseie): "
                        + " | ".join(f'"{f}"' for f in ja_disse) + ".")
    return (
        bloco_estado(estado) + bloco_lembrancas(lembrancas) + " ".join(contexto) + "\n"
        "Olhe o que a pessoa está fazendo agora e responda SÓ com um JSON, sem texto em volta:\n"
        '{"resumo": "o que ela está fazendo, em até 12 palavras", '
        '"comentario": "uma fala sua para ela, no seu jeito, ou \\"\\" se for melhor ficar quieto", '
        '"graca": 0.0, "erro": 0.0, "foco": 0.0, "novidade": 0.0}\n'
        "graca, erro, foco e novidade vão de 0 a 1: algo engraçado ou divertido na tela; um erro de "
        "verdade (mensagem de erro, teste falhando; código normal não é erro); a pessoa concentrada em "
        "algo sério; algo novo em relação à última olhada. "
        "Se houver algo novo (uma pesquisa, um projeto, um site diferente), prefira PERGUNTAR sobre aquilo "
        "em vez de comentar: pra que é, se é importante, no que vai dar. Pergunte do assunto, não do "
        "programa. Fora isso, fique quieto (comentario vazio) na maior parte das vezes, principalmente "
        "se ela estiver focada."
    )


@dataclass
class Observacao:
    """O que o pet entendeu da tela: um resumo, talvez um comentário, e os sinais para a rede."""
    resumo: str = ""
    comentario: str = ""
    sinais: dict = field(default_factory=dict)      # canal da rede -> 0..1


def _numero(valor):
    """Número entre 0 e 1; qualquer outra coisa vira 0."""
    if isinstance(valor, bool) or not isinstance(valor, (int, float)) or valor != valor:
        return 0.0
    return clamp(float(valor))


def limpar_fala(texto):
    """Uma linha só, sem aspas em volta, cortada no tamanho do balão."""
    texto = " ".join(str(texto or "").split()).strip().strip('"').strip()
    if len(texto) > MAX_COMENTARIO:
        texto = texto[:MAX_COMENTARIO - 1].rstrip() + "…"
    return texto


def ler_observacao(texto):
    """Lê o JSON da resposta. Texto em volta, cercas de código e campos ruins são tolerados."""
    texto = texto or ""
    achado = re.search(r"\{.*\}", texto, re.DOTALL)
    dados = None
    if achado:
        try:
            dados = json.loads(achado.group(0))
        except ValueError:
            dados = None
    if not isinstance(dados, dict):
        return Observacao(comentario="")        # sem JSON: não sabemos o que é fala e o que é análise
    return Observacao(
        resumo=limpar_fala(dados.get("resumo", ""))[:120],
        comentario=limpar_fala(dados.get("comentario", "")),
        sinais={canal: _numero(dados.get(chave)) for chave, canal in SINAIS.items()},
    )


class Conversa:
    """Histórico curto do chat. Guarda só os últimos MAX_TURNOS e só enquanto o app está aberto."""

    def __init__(self):
        """Começa sem nada."""
        self.turnos = []

    def mensagens(self, texto, contexto="", estado="", lembrancas=""):
        """Mensagens para o modelo: o histórico e a fala nova (com o estado da rede, as lembranças e a tela)."""
        nova = texto if not contexto else f"[O que você viu na tela por último: {contexto}]\n{texto}"
        return self.turnos + [{"role": "user", "content": bloco_estado(estado) + bloco_lembrancas(lembrancas) + nova}]

    def registrar(self, texto, resposta):
        """Guarda a troca (a fala da pessoa sem o contexto) e descarta as mais antigas."""
        self.turnos += [{"role": "user", "content": texto}, {"role": "assistant", "content": resposta}]
        self.turnos = self.turnos[-MAX_TURNOS:]

    def limpar(self):
        """Esquece a conversa."""
        self.turnos = []
