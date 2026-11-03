"""
PROVEDORES - quem responde pelo pet: Claude, OpenAI, DeepSeek ou um modelo local no Ollama.

Sem Qt: cada cliente recebe o prompt de sistema, as mensagens e (opcional) um print em JPEG
base64, e devolve só o texto da resposta. As chamadas bloqueiam: quem chama roda numa thread
(ver mind/visao.py).

As chaves vêm das variáveis de ambiente (ANTHROPIC_API_KEY, OPENAI_API_KEY, DEEPSEEK_API_KEY), que o
app preenche com o .env salvo pela tela de Configurações (ver chaves.py); nunca de memory/. O Ollama
roda no seu computador e não precisa de chave.
"""

import json
import os
import re
import urllib.error
import urllib.request

from .chaves import parece_chave

TEMPO_LIMITE = 60.0         # s por chamada; o pet desiste e tenta de novo mais tarde
OLLAMA_PADRAO = "http://localhost:11434"     # este computador; outro PC da rede vai em "Endereço do Ollama"
PORTA_OLLAMA = 11434
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
        "ve_imagem": True,      # com um modelo de visão (gemma4, qwen2.5vl, minicpm-v, llava)
        "recomendado": "gemma4:e4b",    # testado: ~5 s por olhada numa placa de 8 GB, bom em português
    },
}
PROVEDOR_PADRAO = "claude"


class ErroIA(Exception):
    """Falha que dá para explicar para a pessoa (sem chave, sem conexão, recusa)."""


def info(provedor):
    """Dados do provedor; um nome desconhecido vira o padrão."""
    return PROVEDORES.get(provedor, PROVEDORES[PROVEDOR_PADRAO])


def modelo_de(provedor, modelo):
    """O modelo escolhido, ou o padrão do provedor se o campo estiver vazio (ou tiver uma chave por engano)."""
    modelo = (modelo or "").strip()
    return info(provedor)["modelo"] if not modelo or parece_chave(modelo) else modelo


def endereco_de(texto, porta_padrao, padrao):
    """'192.168.3.250' -> 'http://192.168.3.250:<porta_padrao>'. Vazio vira `padrao`; inválido vira None."""
    texto = (texto or "").strip().rstrip("/")
    if not texto:
        return padrao
    if "://" not in texto:
        texto = "http://" + texto
    achado = re.fullmatch(r"(https?)://([A-Za-z0-9.-]+|\[[0-9A-Fa-f:]+\])(?::(\d{1,5}))?(?:/v1)?", texto)
    if not achado or (achado.group(3) and not 0 < int(achado.group(3)) < 65536):
        return None
    esquema, host, porta = achado.groups()
    return f"{esquema}://{host}:{porta or porta_padrao}"


def endereco_ollama(texto):
    """'192.168.3.250' -> 'http://192.168.3.250:11434'. Vazio vira este computador; inválido vira None."""
    return endereco_de(texto, PORTA_OLLAMA, OLLAMA_PADRAO)


def testar_ollama(endereco, modelo, tempo=3.0):
    """(deu_certo, mensagem): o Ollama responde nesse endereço? O modelo está instalado lá?"""
    base = endereco_ollama(endereco)
    if base is None:
        return False, "endereço inválido (exemplo: 192.168.0.10 ou http://192.168.0.10:11434)"
    try:
        with urllib.request.urlopen(f"{base}/api/version", timeout=tempo) as resposta:
            versao = json.loads(resposta.read().decode("utf-8")).get("version", "?")
        with urllib.request.urlopen(f"{base}/api/tags", timeout=tempo) as resposta:
            nomes = {m.get("name", "") for m in json.loads(resposta.read().decode("utf-8")).get("models", [])}
    except (urllib.error.URLError, OSError, ValueError, AttributeError):
        return False, f"o Ollama não respondeu em {base} (ligado? aceita conexões da rede?)"
    modelo = modelo_de("ollama", modelo)
    instalado = modelo in nomes or f"{modelo}:latest" in nomes
    if not instalado:
        return False, f"Ollama {versao} respondeu, mas falta o modelo: rode ollama pull {modelo} nele"
    return True, f"Ollama {versao} respondeu em {base}, com {modelo} instalado."


def criar_cliente(provedor, modelo="", endereco=""):
    """Cliente pronto para `responder`. Levanta ErroIA se faltar a chave, o pacote ou o endereço for ruim."""
    dados = info(provedor)
    chave = None
    if dados["chave"]:
        chave = os.environ.get(dados["chave"], "").strip()
        if not chave:
            raise ErroIA(f"falta a chave de {dados['nome']}: cole em Configurações, Visão e conversa (IA), "
                         "e clique em Salvar chave")
    if provedor == "claude":
        return ClienteClaude(chave, modelo_de(provedor, modelo))
    if provedor == "ollama":
        base = endereco_ollama(endereco)
        if base is None:
            raise ErroIA(f"endereço do Ollama inválido: {endereco!r}")
        return ClienteOpenAI("ollama", modelo_de(provedor, modelo), f"{base}/v1", dados["ve_imagem"], ollama=True)
    return ClienteOpenAI(chave, modelo_de(provedor, modelo), dados.get("base_url"), dados["ve_imagem"])


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

    def __init__(self, chave, modelo, base_url=None, ve_imagem=True, ollama=False):
        """Cria o cliente; `base_url` aponta para o DeepSeek ou para o Ollama (deste ou de outro computador)."""
        try:
            import openai
        except ImportError as erro:
            raise ErroIA("pacote 'openai' não instalado (pip install -r requirements.txt)") from erro
        self._sdk = openai
        self.modelo = modelo
        self.ve_imagem = ve_imagem
        self.ollama = ollama
        self.base_url = base_url
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
            dica = f" (rode: ollama pull {self.modelo})" if self.ollama else ""
            raise ErroIA(f"modelo '{self.modelo}' não encontrado{dica}") from erro
        except sdk.RateLimitError as erro:
            raise ErroIA("limite de uso da API atingido; tento de novo mais tarde") from erro
        except sdk.APIStatusError as erro:
            raise ErroIA(f"a API respondeu com erro {erro.status_code}") from erro
        except sdk.APIConnectionError as erro:
            if self.ollama:
                endereco = (self.base_url or "").removesuffix("/v1")
                raise ErroIA(f"o Ollama não respondeu em {endereco} (está ligado? aceita conexões da rede?)") from erro
            raise ErroIA("sem conexão com a API") from erro
        if not resposta.choices:
            return ""
        return (resposta.choices[0].message.content or "").strip()
