"""
PROVEDORES - quem responde pelo pet: Claude, OpenAI, DeepSeek ou um modelo local no Ollama.

Sem Qt: cada cliente recebe o prompt de sistema, as mensagens e (opcional) um print em JPEG
base64, e devolve só o texto da resposta. As chamadas bloqueiam: quem chama roda numa thread
(ver mind/visao.py).

As chaves vêm das variáveis de ambiente (ANTHROPIC_API_KEY, OPENAI_API_KEY, DEEPSEEK_API_KEY),
nunca de arquivo do projeto nem de memory/. O Ollama roda no seu computador e não precisa de chave.
"""

import os

TEMPO_LIMITE = 60.0         # s por chamada; o pet desiste e tenta de novo mais tarde
MAX_TOKENS = 1024           # as respostas pedidas são curtas (um JSON ou duas frases)

PROVEDORES = {
    "claude": {
        "nome": "Claude (Anthropic)",
        "modelo": "claude-opus-5-5",
        "chave": "ANTHROPIC_API_KEY",
        "ve_imagem": True,
    },
    "openai": {
        "nome": "OpenAI",
        "modelo": "gpt-5-mini",
        "chave": "OPENAI_API_KEY",
        "ve_imagem": True,
    },
    "deepseek": {
        "nome": "DeepSeek (só texto)",
        "modelo": "deepseek-chat",
        "chave": "DEEPSEEK_API_KEY",
        "base_url": "https://api.deepseek.com",
        "ve_imagem": False,     # a API do DeepSeek não aceita imagem: ele vê só o nome e o título
    },
    "ollama": {
        "nome": "Ollama (local, sem internet)",
        "modelo": "qwen2.5vl:7b",
        "chave": None,
        "base_url": "http://localhost:11434/v1",
        "ve_imagem": True,      # com um modelo de visão (qwen2.5vl, gemma3, minicpm-v, llava)
    },
}
PROVEDOR_PADRAO = "claude"


class ErroIA(Exception):
    """Falha que dá para explicar para a pessoa (sem chave, sem conexão, recusa)."""


def info(provedor):
    """Dados do provedor; um nome desconhecido vira o padrão."""
    return PROVEDORES.get(provedor, PROVEDORES[PROVEDOR_PADRAO])


def modelo_de(provedor, modelo):
    """O modelo escolhido, ou o padrão do provedor se o campo estiver vazio."""
    return (modelo or "").strip() or info(provedor)["modelo"]


def criar_cliente(provedor, modelo=""):
    """Cliente pronto para `responder`. Levanta ErroIA se faltar a chave ou o pacote."""
    dados = info(provedor)
    chave = None
    if dados["chave"]:
        chave = os.environ.get(dados["chave"], "").strip()
        if not chave:
            raise ErroIA(f"falta a chave: defina a variável de ambiente {dados['chave']} e reabra o Pestinha")
    if provedor == "claude":
        return ClienteClaude(chave, modelo_de(provedor, modelo))
    return ClienteOpenAI(chave or "ollama", modelo_de(provedor, modelo), dados.get("base_url"),
                         dados["ve_imagem"])


class ClienteClaude:
    """Claude pela SDK oficial da Anthropic."""

    ve_imagem = True

    def __init__(self, chave, modelo):
        """Cria o cliente com a chave e o modelo."""
        try:
            import anthropic
        except ImportError as erro:
            raise ErroIA("pacote 'anthropic' não instalado (pip install -r requirements.txt)") from erro
        self._sdk = anthropic
        self.modelo = modelo
        self.cliente = anthropic.Anthropic(api_key=chave, timeout=TEMPO_LIMITE, max_retries=1)

    def responder(self, sistema, mensagens, imagem=None):
        """Manda a conversa (o print vai junto da última mensagem) e devolve o texto."""
        msgs = [dict(m) for m in mensagens]
        if imagem:
            msgs[-1]["content"] = [
                {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": imagem}},
                {"type": "text", "text": msgs[-1]["content"]},
            ]
        sdk = self._sdk
        try:
            resposta = self.cliente.beta.messages.create(
                model=self.modelo,
                max_tokens=MAX_TOKENS,
                system=sistema,
                messages=msgs,
                output_config={"effort": "low"},         # frases curtas: não precisa pensar muito
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",                      # recusa por engano: outro modelo responde
            )
        except sdk.AuthenticationError as erro:
            raise ErroIA("a chave ANTHROPIC_API_KEY foi recusada") from erro
        except sdk.NotFoundError as erro:
            raise ErroIA(f"modelo '{self.modelo}' não encontrado") from erro
        except sdk.RateLimitError as erro:
            raise ErroIA("limite de uso da API atingido; tento de novo mais tarde") from erro
        except sdk.APIStatusError as erro:
            raise ErroIA(f"a API respondeu com erro {erro.status_code}") from erro
        except sdk.APIConnectionError as erro:
            raise ErroIA("sem conexão com a API da Anthropic") from erro
        if resposta.stop_reason == "refusal":
            raise ErroIA("o modelo preferiu não responder a isso")
        return "".join(b.text for b in resposta.content if b.type == "text").strip()


class ClienteOpenAI:
    """OpenAI, DeepSeek e Ollama: todos falam o formato de chat da OpenAI."""

    def __init__(self, chave, modelo, base_url=None, ve_imagem=True):
        """Cria o cliente; `base_url` aponta para o DeepSeek ou para o Ollama local."""
        try:
            import openai
        except ImportError as erro:
            raise ErroIA("pacote 'openai' não instalado (pip install -r requirements.txt)") from erro
        self._sdk = openai
        self.modelo = modelo
        self.ve_imagem = ve_imagem
        self.local = base_url is not None and "localhost" in base_url
        self.cliente = openai.OpenAI(api_key=chave, base_url=base_url, timeout=TEMPO_LIMITE, max_retries=1)

    def responder(self, sistema, mensagens, imagem=None):
        """Manda a conversa (o print vai junto da última mensagem, se o modelo vê imagem) e devolve o texto."""
        msgs = [{"role": "system", "content": sistema}] + [dict(m) for m in mensagens]
        if imagem and self.ve_imagem:
            msgs[-1]["content"] = [
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{imagem}"}},
                {"type": "text", "text": msgs[-1]["content"]},
            ]
        sdk = self._sdk
        try:
            resposta = self.cliente.chat.completions.create(model=self.modelo, messages=msgs)
        except sdk.AuthenticationError as erro:
            raise ErroIA("a chave da API foi recusada") from erro
        except sdk.NotFoundError as erro:
            dica = f" (rode: ollama pull {self.modelo})" if self.local else ""
            raise ErroIA(f"modelo '{self.modelo}' não encontrado{dica}") from erro
        except sdk.RateLimitError as erro:
            raise ErroIA("limite de uso da API atingido; tento de novo mais tarde") from erro
        except sdk.APIStatusError as erro:
            raise ErroIA(f"a API respondeu com erro {erro.status_code}") from erro
        except sdk.APIConnectionError as erro:
            if self.local:
                raise ErroIA("o Ollama não está rodando (abra o Ollama ou rode: ollama serve)") from erro
            raise ErroIA("sem conexão com a API") from erro
        if not resposta.choices:
            return ""
        return (resposta.choices[0].message.content or "").strip()
