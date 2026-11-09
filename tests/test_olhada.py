"""
Modelo da olhada separado: a olhada (a chamada mais frequente) vai pelo Ollama, se houver, ou pelo Claude
Haiku; o chat, o estudo e o resumo continuam com o provedor e o modelo escolhidos. Também o padrão do
Claude (Sonnet, não mais o Opus), o cache do prompt de sistema e o Haiku sem o parâmetro de fallback.
"""

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
from pestinha.ia import provedores, uso  # noqa: E402
from pestinha.mind import visao as visao_mod  # noqa: E402
from pestinha.paths import Paths  # noqa: E402
from pestinha.settings_store import SettingsStore  # noqa: E402

REAL = visao_mod.VisaoController.cliente_olhada         # o conftest troca pela do chat em todos os testes


@pytest.mark.parametrize("perms, esperado", [
    ({}, ("claude", "claude-haiku-5-5")),                                           # nada configurado
    ({"ia_ollama_url": "http://192.168.3.250:11434"}, ("ollama", "gemma4:e4b")),    # Ollama na rede de casa
    ({"ia_provedor": "ollama", "ia_modelo": "qwen2.5vl:7b"}, ("ollama", "qwen2.5vl:7b")),
    ({"ia_ollama_url": "x", "olhada_modelo": "gemma4:e2b"}, ("ollama", "gemma4:e2b")),
    ({"olhada_provedor": "claude", "ia_ollama_url": "x"}, ("claude", "claude-haiku-5-5")),
    ({"olhada_provedor": "claude", "olhada_modelo": "claude-sonnet-5-5"}, ("claude", "claude-sonnet-5-5")),
    ({"olhada_provedor": "mesmo", "ia_provedor": "openai", "ia_modelo": "gpt-5-mini"}, ("openai", "gpt-5-mini")),
    ({"olhada_provedor": "ollama"}, ("ollama", "gemma4:e4b")),
    ({"ia_provedor": "openai", "ia_modelo": "gpt-5-mini"}, ("openai", "gpt-5-mini")),   # o print não vai para
    ({"ia_provedor": "deepseek"}, ("deepseek", "")),                                     # quem você não escolheu
])
def test_quem_olha_a_tela(perms, esperado):
    provedor, modelo, _endereco = provedores.modelo_da_olhada(dict(config.DEFAULT_PERMISSIONS, **perms))
    assert (provedor, modelo) == esperado


def test_o_padrao_do_claude_nao_e_mais_o_opus():
    assert provedores.PROVEDORES["claude"]["modelo"] == "claude-sonnet-5-5"
    assert config.DEFAULT_PERMISSIONS["olhada_provedor"] == "auto"


def test_permissao_da_olhada_validada():
    validas = config.permissoes_validas({"olhada_provedor": "qualquer", "olhada_modelo": "sk-ant-api03-" + "x" * 40})
    assert "olhada_provedor" not in validas and validas["olhada_modelo"] == ""


class _Mensagens:
    def __init__(self, resposta):
        self.resposta, self.kwargs = resposta, None

    def create(self, **kwargs):
        self.kwargs = kwargs
        return self.resposta


def claude(monkeypatch, modelo):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-teste")
    cliente = provedores.criar_cliente("claude", modelo)
    resposta = SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text="oi")],
                               usage=SimpleNamespace(input_tokens=50, output_tokens=5, cache_read_input_tokens=980,
                                                     cache_creation_input_tokens=0))
    cliente.cliente = SimpleNamespace(beta=SimpleNamespace(messages=_Mensagens(resposta)))
    return cliente


def test_haiku_vai_sem_fallback_e_o_sistema_vai_para_o_cache(monkeypatch):
    registrados = []
    monkeypatch.setattr(uso, "registrar", registrados.append)
    haiku = claude(monkeypatch, "claude-haiku-5-5")
    haiku.responder("persona do Bob", [{"role": "user", "content": "olha"}], tarefa="olhada")
    kwargs = haiku.cliente.beta.messages.kwargs
    assert "fallbacks" not in kwargs and "betas" not in kwargs               # o Haiku 5.5 não tem fallback
    assert kwargs["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert registrados[0].cache_lido == 980                                    # o uso mostra o cache
    sonnet = claude(monkeypatch, "claude-sonnet-5-5")
    sonnet.responder("persona", [{"role": "user", "content": "oi"}])
    assert sonnet.cliente.beta.messages.kwargs["fallbacks"] == "default"


# ---------------- no app de verdade ----------------

@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    return app


class Falso:
    ve_imagem = False

    def __init__(self, nome):
        self.nome, self.tarefas = nome, []

    def responder(self, sistema, mensagens, imagem=None, tarefa="chat"):
        self.tarefas.append(tarefa)
        return '{"resumo": "programando", "comentario": ""}' if tarefa == "olhada" else "Oi!"


def esperar(qapp, condicao, segundos=3.0):
    fim = time.monotonic() + segundos
    while time.monotonic() < fim:
        qapp.processEvents()
        if condicao():
            return True
        time.sleep(0.01)
    return False


def test_a_olhada_vai_pelo_ollama_e_o_chat_pelo_escolhido(qapp, tmp_path, monkeypatch):
    from pestinha.app import PestinhaApp
    monkeypatch.setattr(visao_mod.VisaoController, "cliente_olhada", REAL)
    criados = {}

    def criar(provedor, modelo="", endereco=""):
        criados[provedor] = Falso(provedor)
        criados[provedor].modelo = modelo
        return criados[provedor]

    monkeypatch.setattr(provedores, "criar_cliente", criar)
    monkeypatch.setattr(visao_mod, "capturar_tela", lambda *_a, **_k: None)
    paths = Paths(root=tmp_path)
    store = SettingsStore(paths)
    store.update(dict(config.DEFAULT_PERMISSIONS, ia=True, ver_tela=True, conversa=True, ia_provedor="claude",
                      ia_ollama_url="http://192.168.3.250:11434"))
    app = PestinhaApp(store, paths)
    try:
        app.visao.olhar(time.monotonic())
        assert esperar(qapp, lambda: not app.visao.olhando)
        assert app.visao.perguntar("oi")
        assert esperar(qapp, lambda: not app.visao.respondendo)
        assert criados["ollama"].tarefas == ["olhada"] and criados["ollama"].modelo == "gemma4:e4b"
        assert criados["claude"].tarefas == ["chat"]                            # o chat segue no escolhido
        app.apply_perms({"olhada_provedor": "mesmo"})
        assert app.visao.cliente_olhada() is app.visao.cliente()               # trocou: recriado na hora
    finally:
        app.visao.cancelar()
        app.tray.icon.hide()


def test_no_automatico_sem_chave_a_olhada_vai_pelo_do_chat(qapp, tmp_path, monkeypatch):
    from pestinha.app import PestinhaApp
    monkeypatch.setattr(visao_mod.VisaoController, "cliente_olhada", REAL)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    paths = Paths(root=tmp_path)
    store = SettingsStore(paths)
    store.update(dict(config.DEFAULT_PERMISSIONS, ia=True, ver_tela=True, ia_provedor="ollama"))
    app = PestinhaApp(store, paths)
    try:
        do_chat = Falso("chat")
        monkeypatch.setattr(app.visao, "cliente", lambda: do_chat)
        app.apply_perms({"olhada_provedor": "auto", "ia_provedor": "deepseek", "ia_ollama_url": ""})
        assert app.visao.cliente_olhada() is do_chat                           # sem Ollama nem chave do Claude
        app.apply_perms({"olhada_provedor": "claude"})
        with pytest.raises(provedores.ErroIA, match="falta a chave"):
            app.visao.cliente_olhada()                                         # escolhido à mão: o erro aparece
    finally:
        app.tray.icon.hide()


def test_nada_alarga_as_configuracoes_e_corta_os_botoes(qapp, tmp_path):
    """Uma opção comprida numa caixa de escolha, um rótulo longo ou um caminho de pasta não podem alargar a página
    e empurrar os botões da direita ("Testar...", "Salvar...") para fora da janela."""
    from PySide6.QtWidgets import QComboBox, QLabel
    from pestinha.ui.ui import QUEBRA, Escolha, SettingsDialog
    paths = Paths(root=tmp_path / ("pasta_com_um_nome_bem_comprido_sem_espacos" * 3))
    perms = dict(config.DEFAULT_PERMISSIONS, ia=True, conversa=True, ver_tela=True, memoria_compartilhada=True)
    tela = SettingsDialog(perms, paths, first_run=False)
    try:
        caixas = tela.findChildren(Escolha)
        assert caixas and all(c.sizeAdjustPolicy() == QComboBox.AdjustToMinimumContentsLengthWithIcon for c in caixas)
        olhada = tela.olhada_combo
        assert olhada.minimumSizeHint().width() < olhada.fontMetrics().horizontalAdvance("O mesmo do chat" * 3)
        longos = [r for r in tela.findChildren(QLabel) if len(r.text()) > 45]
        assert longos and all(r.wordWrap() for r in longos), [r.text() for r in longos if not r.wordWrap()]
        pasta = next(r for r in longos if r.text().startswith("Pasta de dados"))
        assert QUEBRA in pasta.text()                                   # o caminho tem onde quebrar
    finally:
        tela.close()
