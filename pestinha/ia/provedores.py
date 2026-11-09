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
import threading
import time
import urllib.error
import urllib.request

from . import orcamento, uso
from ..log import log
from .chaves import parece_chave

TEMPO_LIMITE = 60.0         # s por chamada; o pet desiste e tenta de novo mais tarde
OLLAMA_PADRAO = "http://localhost:11434"     # este computador; outro PC da rede vai em "Endereço do Ollama"
PORTA_OLLAMA = 11434
MAX_TOKENS = orcamento.LIMITES["chat"]      # a saída de cada tarefa fica em orcamento.LIMITES
RACIOCINIO_OPENAI = 1024    # tokens a mais na OpenAI: o gpt-5 conta o raciocínio dentro do limite de saída
JANELA_LIDA_A_CADA = 600.0  # s entre leituras da janela do Ollama (/api/ps)

PROVEDORES = {
    "claude": {
        "nome": "Claude (Anthropic)",
        "modelo": "claude-sonnet-5-5",      # o chat; a olhada, mais frequente, usa o Haiku (modelo_da_olhada)
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
MODELO_OLHADA_CLAUDE = "claude-haiku-5-5"   # a olhada a cada 2,5 min: ~40x mais barata que o Opus
SEM_FALLBACK = ("haiku",)                   # modelos sem fallback de recusa no servidor (o parâmetro dá 400)
OLHADA_PROVEDORES = {
    "auto": "Automático (Ollama, se configurado; no Claude, o Haiku; senão, o do chat)",
    "ollama": "Ollama",
    "claude": "Claude",
    "mesmo": "O mesmo do chat",
}


def ollama_configurado(perms):
    """Você configurou um Ollama: é o provedor do chat ou tem um endereço salvo."""
    return perms.get("ia_provedor") == "ollama" or bool((perms.get("ia_ollama_url") or "").strip())


def modelo_da_olhada(perms):
    """(provedor, modelo, endereço) da olhada. O chat, o estudo e o resumo continuam com o provedor e o modelo
    escolhidos; a olhada, a chamada mais frequente, tem o seu (perms "olhada_provedor" e "olhada_modelo")."""
    escolha = perms.get("olhada_provedor", "auto")
    modelo = (perms.get("olhada_modelo") or "").strip()
    endereco = perms.get("ia_ollama_url", "")
    if escolha == "mesmo" or escolha not in OLHADA_PROVEDORES:
        return perms.get("ia_provedor", PROVEDOR_PADRAO), perms.get("ia_modelo", ""), endereco
    if escolha == "auto":
        # o print só vai para um provedor que você escolheu: o Ollama que você configurou, ou o do chat (no
        # Claude, o modelo mais barato dele)
        if ollama_configurado(perms):
            escolha = "ollama"
        elif perms.get("ia_provedor", PROVEDOR_PADRAO) == "claude":
            escolha = "claude"
        else:
            return perms.get("ia_provedor", PROVEDOR_PADRAO), perms.get("ia_modelo", ""), endereco
    if escolha == "ollama":
        do_chat = perms.get("ia_modelo", "") if perms.get("ia_provedor") == "ollama" else ""
        return "ollama", modelo or do_chat or PROVEDORES["ollama"]["recomendado"], endereco
    return "claude", modelo or MODELO_OLHADA_CLAUDE, endereco


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


def modelos_ollama(endereco, tempo=3.0):
    """Os modelos instalados no Ollama desse endereço (nomes, em ordem alfabética). Levanta ErroIA se não respondeu."""
    base = endereco_ollama(endereco)
    if base is None:
        raise ErroIA("endereço inválido (exemplo: 192.168.0.10 ou http://192.168.0.10:11434)")
    try:
        with urllib.request.urlopen(f"{base}/api/tags", timeout=tempo) as resposta:
            dados = json.loads(resposta.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError) as erro:
        raise ErroIA(f"o Ollama não respondeu em {base} (ligado? aceita conexões da rede?)") from erro
    modelos = dados.get("models") if isinstance(dados, dict) else None
    return sorted({m["name"] for m in modelos or [] if isinstance(m, dict) and isinstance(m.get("name"), str)})


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
        return ClienteOpenAI("ollama", modelo_de(provedor, modelo), f"{base}/v1", dados["ve_imagem"], ollama=True,
                             provedor="ollama")
    return ClienteOpenAI(chave, modelo_de(provedor, modelo), dados.get("base_url"), dados["ve_imagem"],
                         provedor=provedor if provedor in PROVEDORES else "openai")


def cortada(tarefa):
    """O erro de uma resposta que passou do limite de saída da tarefa (orcamento.LIMITES)."""
    return ErroIA(f"a resposta veio cortada (passou de {orcamento.limite(tarefa)} tokens na tarefa {tarefa})")


def _ms(desde):
    """Milissegundos desde `desde` (time.perf_counter)."""
    return int((time.perf_counter() - desde) * 1000)


class ClienteClaude:
    """Claude pela SDK oficial da Anthropic."""

    ve_imagem = True
    janela = orcamento.JANELA_NUVEM

    def __init__(self, chave, modelo):
        """Cria o cliente com a chave e o modelo."""
        try:
            import anthropic
        except ImportError as erro:
            raise ErroIA("pacote 'anthropic' não instalado (pip install -r requirements.txt)") from erro
        self._sdk = anthropic
        self.modelo = modelo
        self.cliente = anthropic.Anthropic(api_key=chave, timeout=TEMPO_LIMITE, max_retries=1)

    def responder(self, sistema, mensagens, imagem=None, tarefa="chat"):
        """Manda a conversa (o print vai junto da última mensagem) e devolve o texto. `tarefa` escolhe o
        limite de saída (orcamento.LIMITES); uma resposta que passa dele vira ErroIA."""
        msgs = [dict(m) for m in mensagens]
        if imagem:
            msgs[-1]["content"] = [
                {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": imagem}},
                {"type": "text", "text": msgs[-1]["content"]},
            ]
        sdk = self._sdk
        inicio = time.perf_counter()
        extra = {}
        if not any(nome in self.modelo for nome in SEM_FALLBACK):
            extra = {"betas": ["server-side-fallback-2026-07-01"],
                     "fallbacks": "default"}             # recusa por engano: outro modelo responde
        try:
            resposta = self.cliente.beta.messages.create(
                model=self.modelo,
                max_tokens=orcamento.limite(tarefa),
                # o prompt de sistema (a persona) é o mesmo em toda chamada: fica no cache (~10% do preço)
                system=[{"type": "text", "text": sistema, "cache_control": {"type": "ephemeral"}}],
                messages=msgs,
                output_config={"effort": "low"},         # frases curtas: não precisa pensar muito
                **extra,
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
        gasto = getattr(resposta, "usage", None)
        uso.registrar(uso.Uso(tarefa, "claude", self.modelo, getattr(gasto, "input_tokens", 0) or 0,
                              getattr(gasto, "output_tokens", 0) or 0, _ms(inicio),
                              getattr(resposta, "stop_reason", "") or "",
                              cache_lido=getattr(gasto, "cache_read_input_tokens", 0) or 0,
                              cache_gravado=getattr(gasto, "cache_creation_input_tokens", 0) or 0))
        if resposta.stop_reason == "refusal":
            raise ErroIA("o modelo preferiu não responder a isso")
        if resposta.stop_reason in ("max_tokens", "model_context_window_exceeded"):
            raise cortada(tarefa)
        return "".join(b.text for b in resposta.content if b.type == "text").strip()


class ClienteOpenAI:
    """OpenAI, DeepSeek e Ollama: todos falam o formato de chat da OpenAI."""

    def __init__(self, chave, modelo, base_url=None, ve_imagem=True, ollama=False, tempo=TEMPO_LIMITE,
                 provedor="openai"):
        """Cria o cliente; `base_url` aponta para o DeepSeek ou o Ollama (deste ou de outro computador)."""
        try:
            import openai
        except ImportError as erro:
            raise ErroIA("pacote 'openai' não instalado (pip install -r requirements.txt)") from erro
        self._sdk = openai
        self.modelo = modelo
        self.ve_imagem = ve_imagem
        self.ollama = ollama
        self.base_url = base_url
        self.provedor = "ollama" if ollama else provedor
        self.janela = orcamento.JANELA_OLLAMA if ollama else orcamento.JANELA_NUVEM
        self.tokens_imagem = 450 if ollama else orcamento.TOKENS_IMAGEM      # gemma4: ~400 por print
        self._janela_lida = None                # quando leu a janela do Ollama pela última vez
        self.cliente = openai.OpenAI(api_key=chave, base_url=base_url, timeout=tempo, max_retries=1)

    def _parametros(self, tarefa):
        """O limite de saída (e o raciocínio) no formato de cada provedor."""
        maximo = orcamento.limite(tarefa)
        if self.provedor == "openai":       # gpt-5: o raciocínio conta no limite; pouco raciocínio basta aqui
            return {"max_completion_tokens": maximo + RACIOCINIO_OPENAI, "reasoning_effort": "minimal"}
        return {"max_tokens": maximo}

    def ler_janela(self):
        """Ollama: a janela de contexto do modelo carregado (/api/ps), no máximo a cada JANELA_LIDA_A_CADA s.
        Roda fora da thread do Qt; se falhar ou o modelo não estiver carregado, fica a que estava."""
        agora = time.monotonic()
        if not self.ollama or (self._janela_lida is not None and agora - self._janela_lida < JANELA_LIDA_A_CADA):
            return self.janela
        self._janela_lida = agora
        base = (self.base_url or "").removesuffix("/v1")
        try:
            with urllib.request.urlopen(f"{base}/api/ps", timeout=3.0) as resposta:
                dados = json.loads(resposta.read().decode("utf-8"))
        except (urllib.error.URLError, OSError, ValueError):
            return self.janela
        modelos = dados.get("models") if isinstance(dados, dict) else None
        for item in modelos if isinstance(modelos, list) else []:
            if not isinstance(item, dict):
                continue
            nome, tamanho = item.get("name") or item.get("model"), item.get("context_length")
            if nome in (self.modelo, f"{self.modelo}:latest") and isinstance(tamanho, int) and tamanho > 0:
                if tamanho != self.janela:
                    log(f"[ia] janela do Ollama para {self.modelo}: {tamanho} tokens")
                self.janela = tamanho
        return self.janela

    def responder(self, sistema, mensagens, imagem=None, tarefa="chat"):
        """Manda a conversa (o print vai junto da última mensagem, se o modelo vê imagem) e devolve o texto.
        `tarefa` escolhe o limite de saída (orcamento.LIMITES); uma resposta que passa dele vira ErroIA. No
        Ollama, um pedido que o servidor cortou (janela pequena) vai para o log."""
        msgs = [{"role": "system", "content": sistema}] + [dict(m) for m in mensagens]
        if imagem and self.ve_imagem:
            msgs[-1]["content"] = [
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{imagem}"}},
                {"type": "text", "text": msgs[-1]["content"]},
            ]
        sdk = self._sdk
        inicio = time.perf_counter()
        try:
            # Ollama: sem "pensar" antes de responder (gemma4: de ~6 s para <1 s por olhada, ver #4)
            extra = {"reasoning_effort": "none"} if self.ollama else None
            resposta = self.cliente.chat.completions.create(model=self.modelo, messages=msgs, extra_body=extra,
                                                            **self._parametros(tarefa))
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
        gasto = getattr(resposta, "usage", None)
        entrada = getattr(gasto, "prompt_tokens", 0) or 0
        motivo = (getattr(resposta.choices[0], "finish_reason", "") or "") if resposta.choices else ""
        corte = bool(self.ollama and orcamento.cortou(entrada, sistema, mensagens))
        uso.registrar(uso.Uso(tarefa, self.provedor, self.modelo, entrada,
                              getattr(gasto, "completion_tokens", 0) or 0, _ms(inicio), motivo, corte))
        if corte:
            log(f"[ia] o Ollama cortou o pedido ({entrada} tokens, ~{orcamento.tokens_mensagens(sistema, mensagens)} "
                f"esperados; janela de {self.janela}): aumente OLLAMA_CONTEXT_LENGTH no servidor (README)")
        if self.ollama:
            threading.Thread(target=self.ler_janela, name="pestinha-janela", daemon=True).start()
        if motivo == "length":
            raise cortada(tarefa)
        if not resposta.choices:
            return ""
        return (resposta.choices[0].message.content or "").strip()
