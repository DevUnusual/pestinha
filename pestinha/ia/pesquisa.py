"""
PESQUISA - o pet pesquisa na internet pelo Hermes (um agente com ferramentas), no formato da OpenAI.

Sem Qt: só HTTP. As chamadas bloqueiam: quem chama roda numa thread (ver mind/visao.py).
    endereco_hermes(texto)     '192.168.0.10' -> 'http://192.168.0.10:8642'
    testar_hermes(endereco)    o Hermes responde? a chave vale?
    criar_cliente(endereco, sessao)   ClienteHermes: `responder` (como os outros clientes) e `conversar`
                                      (em streaming, avisando quando ele começa e termina de usar uma
                                      ferramenta: é aí que o pet vira IA vilã)

Quem olha a tela continua sendo o provedor de visão; quem conversa e pesquisa, com "Conectar ao Hermes",
é o Hermes. Toda chamada leva a mesma chave de sessão (X-Hermes-Session-Key, "pestinha-<pet>"): o Hermes
guarda na memória dele o que aprende sobre você e todos os computadores falam com o mesmo "ele".
Nunca vai o print nem o título da janela, só o resumo do que você está fazendo.
No Hermes, deixe a plataforma api_server com [web, memory, session_search] (sem terminal nem arquivos):
pesquisa, lê páginas e lembra de você, mas nada que apareça numa página consegue mexer no servidor.

A chave é a API_SERVER_KEY do Hermes, guardada aqui como HERMES_API_KEY no .env (ver chaves.py).
"""

import json
import os
import urllib.error
import urllib.request

from .provedores import ErroIA, endereco_de

PORTA_HERMES = 8642
HERMES_PADRAO = "http://localhost:8642"     # este computador; outro PC da rede vai em "Endereço do Hermes"
CHAVE = "HERMES_API_KEY"
MODELO = "hermes-agent"     # o nome que o api_server do Hermes anuncia em /v1/models
TEMPO_LIMITE = 120.0        # s: um agente pesquisando demora mais que uma resposta direta
EVENTO_FERRAMENTA = "hermes.tool.progress"


class ClienteHermes:
    """Chat Completions do Hermes por HTTP puro, em streaming, com a chave de sessão da memória dele."""

    ve_imagem = False

    def __init__(self, base, chave, sessao="", tempo=TEMPO_LIMITE):
        """`base` sem /v1 ('http://192.168.3.250:8642'); `sessao` vira o X-Hermes-Session-Key."""
        self.base_url = f"{base}/v1"
        self.modelo = MODELO
        self.chave = chave
        self.sessao = sessao
        self.tempo = tempo

    def responder(self, sistema, mensagens, imagem=None):
        """Igual aos outros clientes (sem imagem: o Hermes não vê o print)."""
        return self.conversar(sistema, mensagens)

    def conversar(self, sistema, mensagens, ao_usar=None):
        """
        Manda a conversa e devolve o texto. `ao_usar(ferramenta, rodando)` é chamado (na thread de quem
        chamou) quando o Hermes começa (True) e termina (False) de usar uma ferramenta.
        """
        corpo = json.dumps({"model": self.modelo, "stream": True,
                            "messages": [{"role": "system", "content": sistema}] + list(mensagens)}).encode()
        cabecalhos = {"Authorization": f"Bearer {self.chave}", "Content-Type": "application/json",
                      "Accept": "text/event-stream"}
        if self.sessao:
            cabecalhos["X-Hermes-Session-Key"] = self.sessao
        pedido = urllib.request.Request(f"{self.base_url}/chat/completions", data=corpo, headers=cabecalhos)
        try:
            with urllib.request.urlopen(pedido, timeout=self.tempo) as resposta:
                return ler_stream(resposta, ao_usar)
        except urllib.error.HTTPError as erro:
            if erro.code in (401, 403):
                raise ErroIA("o Hermes recusou a chave (confira a API_SERVER_KEY dele)") from erro
            raise ErroIA(f"o Hermes respondeu com erro {erro.code}") from erro
        except (urllib.error.URLError, OSError) as erro:
            raise ErroIA(f"o Hermes não respondeu em {self.base_url.removesuffix('/v1')}") from erro


def ler_stream(linhas, ao_usar=None):
    """Lê o SSE do Hermes (bytes por linha): junta o texto e avisa as ferramentas. Devolve o texto."""
    texto, evento, dados = [], "", []
    rodando = set()

    def despachar():
        bruto = "\n".join(dados)
        if not bruto or bruto == "[DONE]":
            return
        try:
            carga = json.loads(bruto)
        except ValueError:
            return
        if evento == EVENTO_FERRAMENTA:
            if ao_usar is None or not isinstance(carga, dict):
                return
            ident, ferramenta = carga.get("toolCallId"), carga.get("tool", "")
            if carga.get("status") == "running":
                rodando.add(ident)
                ao_usar(ferramenta, True)
            elif ident in rodando:
                rodando.discard(ident)
                ao_usar(ferramenta, False)
            return
        for escolha in (carga.get("choices") or []) if isinstance(carga, dict) else []:
            pedaco = (escolha.get("delta") or {}).get("content")
            if isinstance(pedaco, str):
                texto.append(pedaco)

    for linha in linhas:
        if isinstance(linha, bytes):
            linha = linha.decode("utf-8", "replace")
        linha = linha.rstrip("\r\n")
        if not linha:
            despachar()
            evento, dados = "", []
        elif linha.startswith("event:"):
            evento = linha[6:].strip()
        elif linha.startswith("data:"):
            dados.append(linha[5:].lstrip())
    despachar()
    if ao_usar is not None:
        for _ in rodando:                       # caiu no meio: nenhuma ferramenta fica "rodando" para sempre
            ao_usar("", False)
    return "".join(texto).strip()


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


def criar_cliente(endereco, sessao=""):
    """Cliente do Hermes. Levanta ErroIA se faltar a chave ou o endereço for ruim."""
    base = endereco_hermes(endereco)
    if base is None:
        raise ErroIA(f"endereço do Hermes inválido: {endereco!r}")
    chave = _chave()
    if not chave:
        raise ErroIA("falta a chave do Hermes: cole a API_SERVER_KEY dele em Configurações e clique em Salvar")
    return ClienteHermes(base, chave, sessao)
