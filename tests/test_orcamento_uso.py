"""
Chamadas confiáveis: o limite de saída de cada tarefa, a resposta cortada que vira erro, o registro de uso
sem conteúdo (ia/uso.py), o orçamento de contexto que nunca corta o prompt de sistema (ia/orcamento.py) e o
aviso quando o Ollama corta o pedido. Clientes e SDKs falsos: nenhum teste fala com a rede.
"""

import io
import json
import os
import sys
import time
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from pestinha import config  # noqa: E402
from pestinha import log as log_module  # noqa: E402
from pestinha.ia import mente, orcamento, pesquisa, provedores, uso  # noqa: E402
from pestinha.paths import Paths  # noqa: E402
from pestinha.settings_store import SettingsStore  # noqa: E402


@pytest.fixture
def usos(monkeypatch):
    """Captura o que os clientes registram (sem gravar arquivo)."""
    registrados = []
    monkeypatch.setattr(uso, "registrar", registrados.append)
    return registrados


# ---------------- orçamento ----------------

def test_limites_por_tarefa():
    assert [orcamento.limite(t) for t in ("olhada", "chat", "notas", "estudo", "resumo")] == [400, 800, 1500, 4096, 4096]
    assert orcamento.limite("tarefa nova") == 800                  # desconhecida vale como chat


def test_encurtar_pelo_fim_ou_pelo_comeco():
    texto = "começo " + "x" * 4000 + " fim"
    inicio, fim = orcamento.encurtar(texto, 100), orcamento.encurtar(texto, 100, manter="fim")
    assert orcamento.tokens(inicio) <= 100 and inicio.startswith("começo") and orcamento.CORTE.strip() in inicio
    assert orcamento.tokens(fim) <= 100 and fim.endswith(" fim") and not fim.startswith("começo")
    assert orcamento.encurtar("curto", 100) == "curto" and orcamento.encurtar(texto, 0) == ""
    prosa = orcamento.encurtar(texto, 1100, razao=orcamento.PROSA)          # o artigo do estudo: prosa corrida
    assert prosa == texto and orcamento.encurtar(texto, 1100) != texto       # com 3,5 ele encolheria à toa


def test_encaixar_corta_da_ordem_maior_para_a_menor_e_nunca_a_fixa():
    cem = int(100 * orcamento.CARACTERES_POR_TOKEN)        # 100 tokens
    fixa, a, b = "F" * cem, "A" * cem, "B" * cem
    textos = orcamento.encaixar([(fixa, None), (a, 1), (b, 2)], 220)
    assert textos[0] == fixa and textos[1] == a             # ordem None nunca é cortada; a 1 nem precisou
    assert 0 < orcamento.tokens(textos[2]) < 100            # a ordem 2 encolheu só o necessário
    assert sum(orcamento.tokens(t) for t in textos) <= 220
    textos = orcamento.encaixar([(fixa, None), (a, 1), (b, 2)], 150)
    assert textos[0] == fixa and textos[2] == "" and 0 < orcamento.tokens(textos[1]) < 100   # a 2 some antes
    assert orcamento.encaixar([(fixa, None), (a, 1)], 1000) == [fixa, a]     # cabendo, nada muda


def test_disponivel_desconta_saida_margem_sistema_e_imagem():
    cliente = SimpleNamespace(janela=8192, tokens_imagem=450)
    sistema = "s" * 4000
    sem = orcamento.disponivel(cliente, "chat", sistema)
    assert sem == 8192 - 800 - orcamento.MARGEM - orcamento.tokens(sistema)
    assert orcamento.disponivel(cliente, "chat", sistema, imagem=True) == sem - 450
    assert orcamento.disponivel(object(), "chat", "") == orcamento.JANELA_NUVEM - 800 - orcamento.MARGEM


def test_cortou_compara_com_a_estimativa():
    mensagens = [{"role": "user", "content": "x" * 36000}]  # ~9000 tokens
    assert orcamento.cortou(4099, "", mensagens)                             # corte de verdade: ~0,4
    ingles = [{"role": "user", "content": "x" * 13464}]                         # artigo em inglês, sem corte
    assert not orcamento.cortou(2790, "", ingles)                               # ~0,73 da estimativa
    assert not orcamento.cortou(orcamento.tokens_mensagens("", mensagens), "", mensagens) and not orcamento.cortou(0, "", mensagens)


def test_conversa_encolhe_o_contexto_e_depois_as_trocas_antigas_mas_nunca_a_fala():
    conversa = mente.Conversa()
    for i in range(4):
        conversa.registrar(f"pergunta {i} " + "p" * 400, f"resposta {i} " + "r" * 400)
    args = ("Qual é o código?", "programando", "contente", "L" * 2000, ["registro " + "g" * 2000],
            "V" * 2000, "J" * 2000)
    inteiro = conversa.mensagens(*args)
    assert len(inteiro) == 9
    apertado = conversa.mensagens(*args, disponivel=1100)
    ultima = apertado[-1]["content"]
    assert ultima.endswith("Qual é o código?") and len(apertado) == 9          # trocas ficam; contexto encolhe
    assert "registro" not in ultima and "[Seu estado agora: contente]" in ultima   # o registro sai antes do estado
    assert orcamento.tokens_mensagens("", apertado) <= 1100
    minimo = conversa.mensagens(*args, disponivel=150)
    assert minimo[-1]["content"].endswith("Qual é o código?") and len(minimo) < 9   # trocas antigas saíram
    assert all(m["role"] == "user" for m in minimo[::2])                          # sempre aos pares


# ---------------- clientes: limite, corte e uso ----------------

class _Mensagens:
    def __init__(self, resposta):
        self.resposta, self.kwargs = resposta, None

    def create(self, **kwargs):
        self.kwargs = kwargs
        return self.resposta


def claude(monkeypatch, resposta):
    sdk = SimpleNamespace(AuthenticationError=KeyError, NotFoundError=KeyError, RateLimitError=KeyError,
                          APIStatusError=KeyError, APIConnectionError=KeyError,
                          Anthropic=lambda **_k: SimpleNamespace(beta=SimpleNamespace(messages=_Mensagens(resposta))))
    monkeypatch.setitem(sys.modules, "anthropic", sdk)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-teste")
    return provedores.criar_cliente("claude", "claude-haiku-5-5")


def test_claude_usa_o_limite_da_tarefa_e_registra_o_uso(monkeypatch, usos):
    resposta = SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text="Oi!")],
                               usage=SimpleNamespace(input_tokens=1234, output_tokens=56))
    cliente = claude(monkeypatch, resposta)
    assert cliente.responder("sistema", [{"role": "user", "content": "oi"}], tarefa="olhada") == "Oi!"
    assert cliente.cliente.beta.messages.kwargs["max_tokens"] == 400
    cliente.responder("sistema", [{"role": "user", "content": "estuda"}], tarefa="estudo")
    assert cliente.cliente.beta.messages.kwargs["max_tokens"] == 4096
    assert (usos[0].tarefa, usos[0].provedor, usos[0].entrada, usos[0].saida, usos[0].motivo) == \
        ("olhada", "claude", 1234, 56, "end_turn")


def test_claude_cortado_vira_erro(monkeypatch, usos):
    resposta = SimpleNamespace(stop_reason="max_tokens", content=[SimpleNamespace(type="text", text='{"nome": "Ho')],
                               usage=SimpleNamespace(input_tokens=2000, output_tokens=4096))
    cliente = claude(monkeypatch, resposta)
    with pytest.raises(provedores.ErroIA, match="cortada.*4096.*estudo"):
        cliente.responder("sistema", [{"role": "user", "content": "estuda"}], tarefa="estudo")
    assert usos[0].motivo == "max_tokens"                           # o corte também é registrado


def openai_falso(monkeypatch, resposta):
    sdk = SimpleNamespace(AuthenticationError=KeyError, NotFoundError=KeyError, RateLimitError=KeyError,
                          APIStatusError=KeyError, APIConnectionError=KeyError,
                          OpenAI=lambda **_k: SimpleNamespace(chat=SimpleNamespace(completions=_Mensagens(resposta))))
    monkeypatch.setitem(sys.modules, "openai", sdk)


def resposta_openai(texto="Oi!", motivo="stop", entrada=100, saida=10):
    return SimpleNamespace(choices=[SimpleNamespace(finish_reason=motivo, message=SimpleNamespace(content=texto))],
                           usage=SimpleNamespace(prompt_tokens=entrada, completion_tokens=saida))


def test_cada_provedor_recebe_o_limite_no_seu_formato(monkeypatch, usos):
    openai_falso(monkeypatch, resposta_openai())
    monkeypatch.setenv("OPENAI_API_KEY", "sk-teste")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-teste")
    monkeypatch.setattr(provedores.ClienteOpenAI, "ler_janela", lambda self: self.janela)
    gpt = provedores.criar_cliente("openai", "")
    gpt.responder("s", [{"role": "user", "content": "oi"}], tarefa="chat")
    kwargs = gpt.cliente.chat.completions.kwargs
    assert kwargs["max_completion_tokens"] == 800 + provedores.RACIOCINIO_OPENAI and kwargs["reasoning_effort"] == "minimal"
    assert "max_tokens" not in kwargs
    for provedor in ("deepseek", "ollama"):
        cliente = provedores.criar_cliente(provedor, "", "localhost")
        cliente.responder("s", [{"role": "user", "content": "oi"}], tarefa="notas")
        kwargs = cliente.cliente.chat.completions.kwargs
        assert kwargs["max_tokens"] == 1500 and "max_completion_tokens" not in kwargs
    assert [u.provedor for u in usos] == ["openai", "deepseek", "ollama"]


def test_finish_length_vira_erro(monkeypatch, usos):
    openai_falso(monkeypatch, resposta_openai('{"resumo": "jog', motivo="length"))
    monkeypatch.setattr(provedores.ClienteOpenAI, "ler_janela", lambda self: self.janela)
    cliente = provedores.criar_cliente("ollama", "gemma4:e4b", "localhost")
    with pytest.raises(provedores.ErroIA, match="cortada.*400.*olhada"):
        cliente.responder("s", [{"role": "user", "content": "olha"}], tarefa="olhada")
    assert usos[0].motivo == "length"


def test_ollama_que_cortou_o_pedido_vai_para_o_log(monkeypatch, usos):
    openai_falso(monkeypatch, resposta_openai("Não sei.", entrada=4099))
    monkeypatch.setattr(provedores.ClienteOpenAI, "ler_janela", lambda self: self.janela)
    linhas = []
    monkeypatch.setattr(provedores, "log", linhas.append)
    cliente = provedores.criar_cliente("ollama", "gemma4:e4b", "localhost")
    cliente.responder("sistema", [{"role": "user", "content": "x" * 36000}])
    assert usos[0].corte_entrada and any("cortou o pedido" in linha and "OLLAMA_CONTEXT_LENGTH" in linha
                                         for linha in linhas)
    usos.clear()
    cliente.responder("sistema", [{"role": "user", "content": "oi"}])
    assert not usos[0].corte_entrada


def test_janela_do_ollama_lida_do_servidor(monkeypatch):
    openai_falso(monkeypatch, resposta_openai())
    cliente = provedores.criar_cliente("ollama", "gemma4:e4b", "192.168.3.250")
    assert cliente.janela == orcamento.JANELA_OLLAMA
    lidos = []

    def urlopen(url, timeout=0):
        lidos.append(url)
        corpo = {"models": [{"name": "outro:7b", "context_length": 2048},
                            {"name": "gemma4:e4b", "context_length": 16384}]}
        return io.BytesIO(json.dumps(corpo).encode())

    monkeypatch.setattr(provedores.urllib.request, "urlopen", urlopen)
    assert cliente.ler_janela() == 16384 and lidos == ["http://192.168.3.250:11434/api/ps"]
    assert cliente.ler_janela() == 16384 and len(lidos) == 1           # não pergunta de novo tão cedo
    nuvem = provedores.ClienteOpenAI("k", "m")
    assert nuvem.janela == orcamento.JANELA_NUVEM and nuvem.ler_janela() == orcamento.JANELA_NUVEM


def test_hermes_le_o_fim_do_stream_e_acusa_corte(monkeypatch, usos):
    linhas = [b'data: {"choices": [{"delta": {"content": "Achei "}}]}', b"",
              b'data: {"choices": [{"delta": {"content": "isso"}, "finish_reason": "length"}], '
              b'"usage": {"prompt_tokens": 900, "completion_tokens": 300}}', b"", b"data: [DONE]", b""]
    fim = {}
    assert pesquisa.ler_stream(linhas, fim=fim) == "Achei isso"
    assert fim == {"entrada": 900, "saida": 300, "motivo": "length"}

    class Resposta(io.BytesIO):
        def __enter__(self):
            return iter(linhas)

        def __exit__(self, *_a):
            return False

    monkeypatch.setattr(pesquisa.urllib.request, "urlopen", lambda *_a, **_k: Resposta())
    hermes = pesquisa.ClienteHermes("http://localhost:8642", "chave")
    with pytest.raises(provedores.ErroIA, match="cortada"):
        hermes.conversar("s", [{"role": "user", "content": "pesquisa"}])
    assert (usos[0].provedor, usos[0].entrada, usos[0].saida) == ("hermes", 900, 300)


# ---------------- registro de uso ----------------

def test_uso_grava_so_numeros_e_apara_o_arquivo(tmp_path, monkeypatch):
    arquivo = tmp_path / "logs" / "uso_ia.jsonl"
    monkeypatch.setattr(uso, "MAX_LINHAS", 5)
    monkeypatch.setattr(uso, "APARAR_A_CADA", 3)
    monkeypatch.setattr(uso, "_desde_aparar", 0)
    uso.configurar(arquivo)
    try:
        for i in range(9):
            uso.registrar(uso.Uso("olhada", "ollama", "gemma4:e4b", 1800 + i, 120, 700, "stop"))
    finally:
        uso.configurar(None)
    chamadas = uso.ler(arquivo)
    assert 5 <= len(chamadas) <= 7 and chamadas[-1]["entrada"] == 1808
    assert set(chamadas[0]) == {"tarefa", "provedor", "modelo", "entrada", "saida", "ms", "motivo", "corte_entrada",
                                "cache_lido", "cache_gravado", "quando"}
    uso.registrar(uso.Uso("chat", "claude", "x"))                    # sem arquivo: só o log
    assert len(uso.ler(arquivo)) == len(chamadas)


def test_linha_de_uso_nao_vai_para_o_registro_que_o_pet_le():
    uso.registrar(uso.Uso("olhada", "ollama", "gemma4:e4b", 10, 5, 300, "stop"))
    log_module.log("[música] tocando lo-fi")
    recentes = log_module.recentes()
    assert any("música" in r for r in recentes) and not any(r[6:].startswith("uso:") for r in recentes)


# ---------------- no app de verdade ----------------

@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    return app


class ClienteQueAnota:
    """Cliente falso que guarda a tarefa de cada chamada."""
    ve_imagem = False
    janela = 4000

    def __init__(self):
        self.tarefas, self.pedidos = [], []

    def responder(self, sistema, mensagens, imagem=None, tarefa="chat"):
        self.tarefas.append(tarefa)
        self.pedidos.append((sistema, mensagens))
        if tarefa == "olhada":
            return json.dumps({"resumo": "programando", "comentario": "", "graca": 0, "erro": 0, "foco": 0.5,
                               "novidade": 0})
        return "Oi!"


def esperar(qapp, condicao, segundos=3.0):
    fim = time.monotonic() + segundos
    while time.monotonic() < fim:
        qapp.processEvents()
        if condicao():
            return True
        time.sleep(0.01)
    return False


def test_o_app_passa_a_tarefa_e_o_sistema_vai_inteiro(qapp, tmp_path, monkeypatch):
    from pestinha.app import PestinhaApp
    from pestinha.mind import visao as visao_mod
    paths = Paths(root=tmp_path)
    store = SettingsStore(paths)
    store.update(dict(config.DEFAULT_PERMISSIONS, ia=True, ver_tela=True, conversa=True))
    app = PestinhaApp(store, paths)
    try:
        assert uso._arquivo == paths.uso_ia                          # o app grava o uso na pasta de dados
        cliente = ClienteQueAnota()
        monkeypatch.setattr(app.visao, "cliente", lambda: cliente)
        monkeypatch.setattr(visao_mod, "capturar_tela", lambda *_a, **_k: None)
        monkeypatch.setattr(app.visao, "lembrado", lambda: "ontem no notebook: " + "programando " * 2000)
        app.visao.olhar(time.monotonic())
        assert esperar(qapp, lambda: not app.visao.olhando)
        assert app.visao.perguntar("oi, tudo bem?")
        assert esperar(qapp, lambda: not app.visao.respondendo)
        assert cliente.tarefas == ["olhada", "chat"]
        for sistema, mensagens in cliente.pedidos:
            assert sistema == app.visao.sistema                      # o prompt de sistema nunca é cortado
            assert orcamento.tokens_mensagens(sistema, mensagens) <= cliente.janela
    finally:
        app.visao.cancelar()
        app.tray.icon.hide()


def test_resumo_de_video_encaixa_tirando_as_notas_mais_antigas(qapp, tmp_path):
    from pestinha.app import PestinhaApp
    from pestinha.ia import video as video_mod
    paths = Paths(root=tmp_path)
    app = PestinhaApp(SettingsStore(paths), paths)
    try:
        video = app.video
        video.titulo, video._duracao = "Aula", 1800
        video.transcricao.notas = [f"- nota {i} " + "n" * 400 for i in range(30)]
        video.transcricao.texto = lambda: "transcrição do fim " + "t" * 8000
        video.transcricao.texto_telas = lambda: "slide " + "s" * 8000
        cliente = SimpleNamespace(janela=8192)
        notas, texto, telas = video.encaixar_resumo(cliente)
        assert notas[0].startswith("- nota 0 ") and notas[-1].startswith("- nota 29") and len(notas) < 30
        assert texto.endswith("t" * 50)                              # da transcrição do resto fica o fim
        assert telas == ""                                           # o que viu na tela sai primeiro
        disponivel = orcamento.disponivel(cliente, "resumo", app.visao.sistema)
        resto = disponivel - orcamento.tokens(video_mod.pedido_resumo("Aula", [], "", 1800, "", ""))
        assert orcamento.tokens("\n".join(notas)) + orcamento.tokens(texto) <= resto
        video.transcricao.notas = ["- nota única"]
        video.transcricao.texto = lambda: "fala curta"
        video.transcricao.texto_telas = lambda: "um slide"
        assert video.encaixar_resumo(cliente) == (["- nota única"], "fala curta", "um slide")   # cabendo, nada muda
    finally:
        app.tray.icon.hide()


def test_apagar_tudo_desliga_o_registro_de_uso(qapp, tmp_path, monkeypatch):
    from pestinha.app import PestinhaApp
    paths = Paths(root=tmp_path)
    app = PestinhaApp(SettingsStore(paths), paths)
    monkeypatch.setattr(app, "quit", lambda: None)
    app.wipe_all_data()
    assert uso._arquivo is None
    uso.registrar(uso.Uso("chat", "ollama", "m"))
    assert not paths.memory.exists()                                 # nada recria a pasta apagada
    app.tray.icon.hide()
