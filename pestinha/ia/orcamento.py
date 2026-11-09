"""
ORÇAMENTO - quanto cabe em cada chamada ao modelo, e quanto ele pode responder.

Sem Qt. Cada tarefa tem um limite de saída (LIMITES). A entrada cabe na janela do modelo menos esse
limite (no Ollama a resposta divide a janela com o pedido) e uma margem:

    disponivel(cliente, tarefa, sistema, imagem)   tokens que sobram para as mensagens
    encaixar(partes, disponivel)                   encurta as partes cortáveis, da menos importante para a mais
    encurtar(texto, tokens, manter="inicio")       corta um texto para caber em `tokens`

O prompt de sistema nunca é cortado: ele é a persona e as regras do pet. Quem monta o pedido escolhe o que
pode encolher (o registro, as lembranças, o artigo do jogo, as notas antigas de um vídeo) e em que ordem.
Antes, um pedido grande demais era cortado pelo próprio Ollama, pelo começo, e perdia as instruções.

A contagem é uma estimativa (CARACTERES_POR_TOKEN, medido no gemma4 em português, mais POR_MENSAGEM),
de propósito um pouco acima do real: errar para menos deixaria a resposta sem espaço na janela. Quando o
Ollama devolve bem menos tokens de entrada que a estimativa, ele cortou o pedido: `cortou` diz isso, e o
cliente avisa.
"""

import math

CARACTERES_POR_TOKEN = 3.5      # gemma4 em português: 4,0 em texto corrido, 3,5 na conversa longa do app
POR_MENSAGEM = 4                # tokens do papel e das marcas de cada mensagem no modelo de chat
PROSA = 4.0                     # caracteres por token de prosa corrida (artigo da Wikipédia: inglês ~4,8, português
                                # ~4,0): com 3,5 o artigo do estudo encolhia sem precisar e perdia o fim do enredo
MARGEM = 256                    # tokens de folga (a estimativa erra um pouco)
CORTE_SUSPEITO = 0.6            # entrada abaixo disso da estimativa: o servidor cortou o pedido (um corte de
                                # verdade dá ~0,4; texto em inglês, sem corte, ~0,73)
JANELA_OLLAMA = 8192            # OLLAMA_CONTEXT_LENGTH padrão recomendado (README); lida do servidor quando dá
JANELA_NUVEM = 32000            # Claude, OpenAI, DeepSeek e Hermes têm mais; o teto aqui é de custo
TOKENS_IMAGEM = 1200            # o print de 1280 px (Claude ~1.196; o gemma4 gasta ~400)
CORTE = "\n[…]\n"               # marca onde um texto foi encurtado

# tokens de saída por tarefa: uma resposta que passa disso volta cortada e vira erro (provedores.py)
LIMITES = {
    "olhada": 400,      # o JSON da olhada (medido: ~120 tokens)
    "trecho": 400,      # em qual trecho da história a pessoa está
    "chat": 800,        # uma resposta de conversa
    "dica": 800,        # a dica de uma pesquisa
    "diario": 800,      # o resumo de um dia de conversa (mind/diario.py)
    "notas": 1500,      # os tópicos de um pedaço de vídeo
    "estudo": 4096,     # o estudo de um jogo (medido: até ~1.550 tokens)
    "resumo": 4096,     # o resumo de um vídeo
}


def limite(tarefa):
    """Tokens de saída da tarefa (uma tarefa desconhecida vale como chat)."""
    return LIMITES.get(tarefa, LIMITES["chat"])


def tokens(texto, razao=CARACTERES_POR_TOKEN):
    """Estimativa de tokens de um texto (`razao`: caracteres por token; PROSA para um artigo)."""
    return math.ceil(len(texto or "") / razao)


def tokens_mensagens(sistema, mensagens):
    """Estimativa dos tokens de texto de um pedido (a imagem fica de fora)."""
    total = tokens(sistema) + (POR_MENSAGEM if sistema else 0)
    for m in mensagens:
        total += POR_MENSAGEM
        conteudo = m.get("content", "")
        if isinstance(conteudo, str):
            total += tokens(conteudo)
        else:
            total += sum(tokens(parte.get("text", "")) for parte in conteudo if isinstance(parte, dict))
    return total


def janela(cliente):
    """A janela de contexto do cliente (um cliente sem esse dado vale como nuvem)."""
    return getattr(cliente, "janela", None) or JANELA_NUVEM


def disponivel(cliente, tarefa, sistema, imagem=False):
    """Tokens que sobram para as mensagens: janela - saída da tarefa - margem - sistema - imagem."""
    resto = janela(cliente) - limite(tarefa) - MARGEM - tokens(sistema)
    if imagem:
        resto -= getattr(cliente, "tokens_imagem", TOKENS_IMAGEM)
    return max(0, resto)


def encurtar(texto, maximo, manter="inicio", razao=CARACTERES_POR_TOKEN):
    """`texto` com no máximo `maximo` tokens (estimados com `razao`). `manter`: "inicio" corta o fim, "fim"
    corta o começo. Zero tokens: vazio."""
    texto = texto or ""
    if tokens(texto, razao) <= maximo:
        return texto
    if maximo <= tokens(CORTE):
        return ""
    caracteres = int((maximo - tokens(CORTE)) * razao)
    return texto[:caracteres] + CORTE if manter == "inicio" else CORTE + texto[len(texto) - caracteres:]


def encaixar(partes, disponivel_):
    """
    Faz as partes caberem em `disponivel_` tokens. `partes` é uma lista de (texto, ordem, manter): ordem None
    nunca é cortada; das cortáveis, a de ordem maior encolhe primeiro (até sumir, se preciso), depois a
    seguinte. Devolve os textos, na mesma ordem das partes.
    """
    textos = [p[0] or "" for p in partes]
    excesso = sum(tokens(t) for t in textos) - disponivel_
    cortaveis = sorted((i for i, p in enumerate(partes) if p[1] is not None), key=lambda i: -partes[i][1])
    for i in cortaveis:
        if excesso <= 0:
            break
        antes = tokens(textos[i])
        textos[i] = encurtar(textos[i], max(0, antes - excesso), partes[i][2] if len(partes[i]) > 2 else "inicio")
        excesso -= antes - tokens(textos[i])
    return textos


def cortou(prompt_tokens, sistema, mensagens):
    """O servidor devolveu bem menos tokens de entrada que a estimativa: ele cortou o pedido."""
    estimado = tokens_mensagens(sistema, mensagens)
    return bool(prompt_tokens) and prompt_tokens < CORTE_SUSPEITO * estimado
