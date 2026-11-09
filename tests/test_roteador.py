"""
Roteador do chat (ia/roteador.py): o Hermes só recebe o que pede pesquisa, imagem ou memória, e o registro
recente do pet só vai junto quando a pergunta é sobre o próprio programa. No app de verdade: "oi, Bob"
responde pelo provedor sem passar pelo Hermes, e "pesquisa X" passa por ele.
"""

import os
import sys
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from pestinha import config  # noqa: E402
from pestinha.ia import roteador  # noqa: E402
from pestinha.paths import Paths  # noqa: E402
from pestinha.settings_store import SettingsStore  # noqa: E402


@pytest.mark.parametrize("texto, hermes", [
    ("oi, Bob", False),
    ("o que você acha desse código?", False),
    ("como você está hoje?", False),
    ("me explica o que essa função faz", False),
    ("pesquisa o que é manga", True),
    ("Procura na internet as notícias de hoje", True),
    ("quem é Santos Dumont?", True),
    ("me mostra uma foto de capivara", True),
    ("como vai ficar o tempo amanhã?", True),
    ("Lembra do que eu te contei sobre o projeto?", True),
    ("anota que eu prefiro Python", True),
])
def test_pede_hermes(texto, hermes):
    assert roteador.pede_hermes(texto) is hermes


@pytest.mark.parametrize("texto, programa", [
    ("oi, Bob", False),
    ("pesquisa o que é manga", False),
    ("por que a música parou?", True),
    ("O que aconteceu com o vídeo?", True),
    ("deu erro aí?", True),
    ("o que você tocou agora há pouco?", True),
    ("o microfone não funciona", True),
])
def test_sobre_o_programa(texto, programa):
    assert roteador.sobre_o_programa(texto) is programa


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    return app


def esperar(qapp, condicao, segundos=3.0):
    fim = time.monotonic() + segundos
    while time.monotonic() < fim:
        qapp.processEvents()
        if condicao():
            return True
        time.sleep(0.01)
    return False


class Cliente:
    ve_imagem = False

    def __init__(self):
        self.pedidos = []

    def responder(self, sistema, mensagens, imagem=None, tarefa="chat"):
        self.pedidos.append(mensagens[-1]["content"])
        return "Pelo provedor."


class Hermes(Cliente):
    def conversar(self, sistema, mensagens, ao_usar=None, tarefa="chat"):
        self.pedidos.append(mensagens[-1]["content"])
        return "Pelo Hermes."


@pytest.fixture
def pet(qapp, tmp_path, monkeypatch):
    from pestinha.app import PestinhaApp
    from pestinha.log import log
    paths = Paths(root=tmp_path)
    store = SettingsStore(paths)
    store.update(dict(config.DEFAULT_PERMISSIONS, ia=True, conversa=True, ver_tela=True, pesquisar=True))
    app = PestinhaApp(store, paths)
    provedor, hermes = Cliente(), Hermes()
    monkeypatch.setattr(app.visao, "cliente", lambda: provedor)
    monkeypatch.setattr(app.visao, "hermes", lambda: hermes)
    monkeypatch.setattr("pestinha.mind.visao.buscar_imagem_na_web", lambda termo: None)
    log("[música] cortou em 1:32 e eu recomecei")
    yield app, provedor, hermes
    app.visao.cancelar()
    app.tray.icon.hide()


def test_oi_vai_direto_e_pesquisa_vai_pelo_hermes(qapp, pet):
    app, provedor, hermes = pet
    assert app.visao.com_hermes()
    inicio = time.monotonic()
    assert app.visao.perguntar("oi, Bob")
    assert esperar(qapp, lambda: not app.visao.respondendo)
    assert time.monotonic() - inicio < 2.0 and len(provedor.pedidos) == 1 and hermes.pedidos == []
    assert "registro recente" not in provedor.pedidos[0]                  # conversa comum: sem o log dele
    assert app.visao.perguntar("pesquisa o que é manga")
    assert esperar(qapp, lambda: not app.visao.respondendo)
    assert len(hermes.pedidos) == 1 and len(provedor.pedidos) == 1


def test_o_log_vai_junto_so_quando_a_pergunta_e_sobre_ele(qapp, pet):
    app, provedor, _hermes = pet
    assert app.visao.perguntar("por que a música parou?")
    assert esperar(qapp, lambda: not app.visao.respondendo)
    assert "registro recente" in provedor.pedidos[-1] and "cortou em 1:32" in provedor.pedidos[-1]
