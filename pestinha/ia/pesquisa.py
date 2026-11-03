"""
PESQUISA - o pet pesquisa na internet pelo Hermes (um agente com ferramentas), no formato da OpenAI.

Sem Qt: só HTTP. As chamadas bloqueiam: quem chama roda numa thread (ver mind/visao.py).
    endereco_hermes(texto)     '192.168.0.10' -> 'http://192.168.0.10:8642'
    testar_hermes(endereco)    o Hermes responde? a chave vale?
    criar_cliente(endereco)    cliente pronto para `responder` (o mesmo ClienteOpenAI dos provedores)

Quem olha a tela continua sendo o provedor de visão. O Hermes recebe só o termo da pesquisa e o resumo
do que a pessoa está fazendo (nunca o print nem o título da janela), pesquisa e devolve uma dica.
No Hermes, deixe a plataforma api_server só com a ferramenta de pesquisa: o texto da tela pode tentar
dar ordens a ele (ver README do projeto).

A chave é a API_SERVER_KEY do Hermes, guardada aqui como HERMES_API_KEY no .env (ver chaves.py).
"""

import json
import os
import urllib.error
import urllib.request

from .provedores import ClienteOpenAI, ErroIA, endereco_de

PORTA_HERMES = 8642
HERMES_PADRAO = "http://localhost:8642"     # este computador; outro PC da rede vai em "Endereço do Hermes"
CHAVE = "HERMES_API_KEY"
MODELO = "hermes-agent"     # o nome que o api_server do Hermes anuncia em /v1/models
TEMPO_LIMITE = 120.0        # s: um agente pesquisando demora mais que uma resposta direta


def endereco_hermes(texto):
    """'192.168.3.250' -> 'http://192.168.3.250:8642'. Vazio vira este computador; inválido vira None."""
    return endereco_de(texto, PORTA_HERMES, HERMES_PADRAO)


def _chave():
    """A chave do .env (já no ambiente do processo), ou vazio."""
    return os.environ.get(CHAVE, "").strip()


def testar_hermes(endereco, tempo=3.0):
    """(deu_certo, mensagem): o Hermes responde nesse endereço? A chave foi aceita?"""
    base = endereco_hermes(endereco)
    if base is None:
        return False, "endereço inválido (exemplo: 192.168.0.10 ou http://192.168.0.10:8642)"
    try:
        with urllib.request.urlopen(f"{base}/health", timeout=tempo) as resposta:
            dados = json.loads(resposta.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError):
        return False, (f"o Hermes não respondeu em {base} (o gateway está rodando com API_SERVER_KEY? "
                       "aceita conexões da rede?)")
    if not isinstance(dados, dict) or dados.get("platform") != "hermes-agent":
        return False, f"{base} respondeu, mas não parece o Hermes"
    chave = _chave()
    if not chave:
        return False, f"Hermes {dados.get('version', '?')} respondeu, mas falta a chave (a API_SERVER_KEY dele)"
    pedido = urllib.request.Request(f"{base}/v1/models", headers={"Authorization": f"Bearer {chave}"})
    try:
        with urllib.request.urlopen(pedido, timeout=tempo):
            pass
    except urllib.error.HTTPError as erro:
        if erro.code in (401, 403):
            return False, "o Hermes recusou a chave (confira a API_SERVER_KEY dele)"
        return False, f"o Hermes respondeu com erro {erro.code}"
    except (urllib.error.URLError, OSError):
        return False, f"o Hermes parou de responder em {base}"
    return True, f"Hermes {dados.get('version', '?')} respondeu em {base} e aceitou a chave."


def criar_cliente(endereco):
    """Cliente do Hermes. Levanta ErroIA se faltar a chave ou o endereço for ruim."""
    base = endereco_hermes(endereco)
    if base is None:
        raise ErroIA(f"endereço do Hermes inválido: {endereco!r}")
    chave = _chave()
    if not chave:
        raise ErroIA("falta a chave do Hermes: cole a API_SERVER_KEY dele em Configurações e clique em Salvar")
    return ClienteOpenAI(chave, MODELO, f"{base}/v1", ve_imagem=False, tempo=TEMPO_LIMITE)
