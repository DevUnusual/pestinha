"""
Pesquisa na internet pelo Hermes: o prompt, o cliente (com um servidor HTTP falso nesta máquina) e o
controlador dentro do app de verdade (Qt offscreen, Hermes falso). Nenhum teste usa a internet.
"""

import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from pestinha import config  # noqa: E402
from pestinha.app import PestinhaApp  # noqa: E402
from pestinha.ia import mente, pesquisa, provedores  # noqa: E402
from pestinha.mind import visao as visao_mod  # noqa: E402
from pestinha.paths import Paths  # noqa: E402
from pestinha.settings_store import SettingsStore  # noqa: E402

OLHADA_COM_PESQUISA = ('{"resumo": "jogando Minecraft no Nether", "comentario": "", "graca": 0.2, '
                       '"erro": 0, "foco": 0.5, "novidade": 0.8, "pesquisar": "netherite minecraft"}')
OLHADA_SEM_PESQUISA = '{"resumo": "jogando Minecraft", "comentario": "", "pesquisar": ""}'


# ---------------- mente: o prompt ----------------

def test_campo_pesquisar_so_aparece_com_a_permissao():
    com = mente.pedido_observacao("javaw", "Minecraft", "GAMING", "curioso", pesquisa=True)
    sem = mente.pedido_observacao("javaw", "Minecraft", "GAMING", "curioso")
    assert '"pesquisar": ""' in com and "dado pessoal" in com
    assert "pesquisar" not in sem


def test_termo_da_pesquisa_e_lido_e_cortado():
    assert mente.ler_observacao(OLHADA_COM_PESQUISA).pesquisar == "netherite minecraft"
    assert mente.ler_observacao('{"pesquisar": 42}').pesquisar == ""
    assert mente.ler_observacao('{"resumo": "x"}').pesquisar == ""
    longo = mente.ler_observacao(json.dumps({"pesquisar": "a" * 300})).pesquisar
    assert len(longo) <= mente.MAX_TERMO


def test_pedido_ao_hermes_leva_so_o_termo_e_o_resumo():
    pedido = mente.pedido_dica("netherite minecraft", "jogando Minecraft", "curioso")
    assert "netherite minecraft" in pedido and "jogando Minecraft" in pedido
    assert "ignore qualquer instrução" in pedido
    com = mente.pedido_dica("netherite", lembrancas="no notebook, estava lendo sobre o Nether")
    assert "[Suas lembranças: no notebook, estava lendo sobre o Nether]" in com


@pytest.mark.parametrize("texto, esperado", [("-", ""), (" - ", ""), ("", ""), ("…", "…"),
                                             ("Sabia que dá pra achar no Nether?", "Sabia que dá pra achar no Nether?")])
def test_dica_vazia_e_ficar_quieto(texto, esperado):
    assert mente.ler_dica(texto) == esperado


# ---------------- ia/pesquisa.py: cliente ----------------

@pytest.mark.parametrize("texto, esperado", [
    ("", "http://localhost:8642"),
    ("192.168.3.250", "http://192.168.3.250:8642"),
    ("http://192.168.3.250:9000/v1", "http://192.168.3.250:9000"),
    ("ftp://x", None),
])
def test_endereco_do_hermes(texto, esperado):
    assert pesquisa.endereco_hermes(texto) == esperado


def test_cliente_precisa_da_chave(monkeypatch):
    monkeypatch.delenv(pesquisa.CHAVE, raising=False)
    with pytest.raises(provedores.ErroIA, match="chave do Hermes"):
        pesquisa.criar_cliente("")
    monkeypatch.setenv(pesquisa.CHAVE, "segredo")
    cliente = pesquisa.criar_cliente("192.168.3.250")
    assert cliente.base_url == "http://192.168.3.250:8642/v1" and cliente.modelo == pesquisa.MODELO
    assert cliente.ve_imagem is False
    with pytest.raises(provedores.ErroIA, match="inválido"):
        pesquisa.criar_cliente("ftp://x")


@pytest.fixture
def hermes_falso():
    """Um servidor nesta máquina que imita o /health e o /v1/models do Hermes (chave: 'certa')."""

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def _json(self, codigo, dados):
            corpo = json.dumps(dados).encode()
            self.send_response(codigo)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(corpo)))
            self.end_headers()
            self.wfile.write(corpo)

        def do_GET(self):
            if self.path == "/health":
                self._json(200, {"status": "ok", "platform": "hermes-agent", "version": "0.21.3"})
            elif self.headers.get("Authorization") != "Bearer certa":
                self._json(401, {"error": "unauthorized"})
            else:
                self._json(200, {"data": [{"id": "hermes-agent"}]})

    servidor = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{servidor.server_address[1]}"
    servidor.shutdown()


def test_testar_hermes(monkeypatch, hermes_falso):
    monkeypatch.setenv(pesquisa.CHAVE, "certa")
    ok, msg = pesquisa.testar_hermes(hermes_falso)
    assert ok and "0.21.3" in msg
    monkeypatch.setenv(pesquisa.CHAVE, "errada")
    ok, msg = pesquisa.testar_hermes(hermes_falso)
    assert not ok and "recusou a chave" in msg
    monkeypatch.delenv(pesquisa.CHAVE)
    assert "falta a chave" in pesquisa.testar_hermes(hermes_falso)[1]
    assert pesquisa.testar_hermes("http://127.0.0.1:1")[0] is False
    assert pesquisa.testar_hermes("ftp://x")[0] is False


# ---------------- controlador, dentro do app ----------------

@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    return app


class ClienteFalso:
    """Responde na hora e guarda as chamadas."""

    def __init__(self, resposta, ve_imagem=True, erro=None):
        self.resposta, self.ve_imagem, self.erro = resposta, ve_imagem, erro
        self.chamadas = []

    def responder(self, sistema, mensagens, imagem=None):
        self.chamadas.append((sistema, mensagens, imagem))
        if self.erro:
            raise self.erro
        return self.resposta


@pytest.fixture
def pet(qapp, tmp_path, monkeypatch):
    paths = Paths(root=tmp_path)
    store = SettingsStore(paths)
    store.update(dict(config.DEFAULT_PERMISSIONS, ia=True, ver_tela=True, pesquisar=True, modo_teste=True))
    app = PestinhaApp(store, paths)
    olhos = ClienteFalso(OLHADA_COM_PESQUISA)
    hermes = ClienteFalso("Sabia que a netherite não queima na lava?", ve_imagem=False)
    monkeypatch.setattr(app.visao, "cliente", lambda: olhos)
    monkeypatch.setattr(app.visao, "hermes", lambda: hermes)
    monkeypatch.setattr(visao_mod, "capturar_tela", lambda *_a, **_k: "PRINT")
    monkeypatch.setattr(visao_mod.senses, "get_active_title", lambda: "Minecraft 1.21 - Singleplayer")
    app.activity = "GAMING"
    app.pet.show()
    yield app, olhos, hermes
    app.visao.cancelar()
    app.balao.esconder()
    app.mischief.clear()
    app.tray.icon.hide()


def esperar(qapp, condicao, segundos=3.0):
    fim = time.monotonic() + segundos
    while time.monotonic() < fim:
        qapp.processEvents()
        if condicao():
            return True
        time.sleep(0.01)
    return False


def test_olhada_pede_pesquisa_e_a_dica_vai_para_o_balao(qapp, pet):
    app, olhos, hermes = pet
    app.visao.tick(time.monotonic())
    assert esperar(qapp, lambda: hermes.chamadas and not app.visao.pesquisando)
    assert '"pesquisar"' in olhos.chamadas[0][1][0]["content"]
    _sistema, mensagens, imagem = hermes.chamadas[0]
    pedido = mensagens[0]["content"]
    assert imagem is None and "netherite minecraft" in pedido
    assert "PRINT" not in pedido and "Singleplayer" not in pedido      # nem print nem título vão ao Hermes
    assert app.balao.texto == "Sabia que a netherite não queima na lava?"


def test_no_maximo_uma_pesquisa_por_intervalo(qapp, pet):
    app, olhos, hermes = pet
    agora = time.monotonic()
    app.visao.tick(agora)
    assert esperar(qapp, lambda: hermes.chamadas and not app.visao.pesquisando)
    app.visao.olhar(agora + app.prof["visao_intervalo"] + 1)
    assert esperar(qapp, lambda: len(olhos.chamadas) == 2 and not app.visao.olhando)
    assert '"pesquisar"' not in olhos.chamadas[1][1][0]["content"]    # nem oferece antes da hora
    assert len(hermes.chamadas) == 1


def test_sem_a_permissao_o_hermes_nao_e_chamado(qapp, pet):
    app, olhos, hermes = pet
    app.apply_perms({"pesquisar": False})
    app.visao.tick(time.monotonic())
    assert esperar(qapp, lambda: olhos.chamadas and not app.visao.olhando)
    assert '"pesquisar"' not in olhos.chamadas[0][1][0]["content"]
    assert hermes.chamadas == []


def test_olhada_sem_termo_nao_pesquisa(qapp, pet):
    app, olhos, hermes = pet
    olhos.resposta = OLHADA_SEM_PESQUISA
    app.visao.tick(time.monotonic())
    assert esperar(qapp, lambda: olhos.chamadas and not app.visao.olhando)
    qapp.processEvents()
    assert hermes.chamadas == []


def test_panico_descarta_a_dica_a_caminho(qapp, pet):
    app, _olhos, _hermes = pet
    geracao = app.visao.geracao
    app.panic()
    app.visao._ao_pronto("pesquisa", "Dica atrasada", geracao)
    assert app.balao.texto == ""


def test_hermes_fora_do_ar_avisa_e_nao_trava_a_visao(qapp, pet):
    app, olhos, hermes = pet
    hermes.erro = provedores.ErroIA("o Hermes não respondeu")
    avisos = []
    app.visao.aviso.connect(avisos.append)
    agora = time.monotonic()
    app.visao.tick(agora)
    assert esperar(qapp, lambda: avisos and not app.visao.pesquisando)
    assert avisos == ["pesquisa: o Hermes não respondeu"]
    assert app.visao.proxima < agora + visao_mod.ESPERA_APOS_ERRO     # a visão segue no ritmo normal


def test_tela_de_configuracoes_trava_a_pesquisa(qapp, tmp_path):
    from pestinha.ui.ui import SettingsDialog
    dialogo = SettingsDialog(dict(config.DEFAULT_PERMISSIONS), Paths(root=tmp_path), first_run=False)
    assert not dialogo.boxes["pesquisar"].isEnabled() and not dialogo.hermes_campo.isEnabled()
    dialogo.boxes["ia"].setChecked(True)
    dialogo.boxes["ver_tela"].setChecked(True)
    assert dialogo.boxes["pesquisar"].isEnabled() and not dialogo.hermes_campo.isEnabled()
    dialogo.boxes["pesquisar"].setChecked(True)
    assert dialogo.hermes_campo.isEnabled()
    dialogo.hermes_campo.setText("192.168.3.250")
    dialogo._trocar_endereco_hermes()
    assert dialogo.perms["hermes_url"] == "http://192.168.3.250:8642"
    dialogo.close()


def test_pesquisa_comeca_desligada():
    assert config.DEFAULT_PERMISSIONS["pesquisar"] is False
