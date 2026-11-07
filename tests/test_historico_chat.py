"""
Histórico do chat: o que você pediu (escrito ou falado) e as respostas inteiras ficam em
memory/pets/<pet>/historico_chat.jsonl e voltam quando você abre o chat. O balão continua curto.
O arquivo (pasta temporária) e o app de verdade (Qt offscreen, modelo falso).
"""

import json
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
from pestinha.app import PestinhaApp  # noqa: E402
from pestinha.ia import mente  # noqa: E402
from pestinha.mind import historico as historico_mod  # noqa: E402
from pestinha.mind.historico import HistoricoChat  # noqa: E402
from pestinha.paths import Paths  # noqa: E402
from pestinha.settings_store import SettingsStore  # noqa: E402

LONGA = ("Para exportar:\n1. Abra o menu Arquivo e escolha Exportar.\n2. Escolha o formato.\n\n"
         + "Depois é só salvar onde quiser. " * 12)


# ---------------- o arquivo ----------------

def test_guarda_le_e_apaga(tmp_path):
    h = HistoricoChat(tmp_path / "pet" / "historico_chat.jsonl")
    assert h.ultimas() == []
    h.adicionar("voce", "como exporto?", voz=True, quando=100.0)
    h.adicionar("pet", LONGA)
    assert not h.adicionar("ninguem", "x") and not h.adicionar("pet", "   ")
    falas = h.ultimas()
    assert [f["quem"] for f in falas] == ["voce", "pet"]
    assert falas[0] == {"t": 100.0, "quem": "voce", "texto": "como exporto?", "erro": False, "voz": True}
    assert falas[1]["texto"] == LONGA.strip()                         # inteira, com as quebras de linha
    assert h.apagar() and h.ultimas() == [] and not h.caminho.exists()


def test_linha_estragada_fica_de_fora(tmp_path):
    caminho = tmp_path / "historico_chat.jsonl"
    caminho.write_text('{"t": 1, "quem": "voce", "texto": "oi"}\nlixo\n{"quem": "pet"}\n'
                       '{"t": 2, "quem": "pet", "texto": "olá", "erro": true}\n', encoding="utf-8")
    falas = HistoricoChat(caminho).ultimas()
    assert [(f["texto"], f["erro"]) for f in falas] == [("oi", False), ("olá", True)]


def test_as_mais_velhas_saem(tmp_path, monkeypatch):
    monkeypatch.setattr(historico_mod, "MAX_LINHAS", 10)
    h = HistoricoChat(tmp_path / "historico_chat.jsonl")
    for i in range(15):
        h.adicionar("voce", f"fala {i}")
    falas = h.ultimas()
    assert len(falas) <= 10 and falas[-1]["texto"] == "fala 14" and falas[0]["texto"] != "fala 0"


def test_resposta_inteira_para_o_chat_e_curta_para_o_balao():
    eco = "[Seu estado agora: feliz]\n" + LONGA
    inteira = mente.limpar_resposta(eco)
    assert inteira.startswith("Para exportar:\n1. Abra") and len(inteira) > mente.MAX_COMENTARIO
    assert "Seu estado" not in inteira and "\n\n\n" not in inteira
    assert len(mente.limpar_fala(inteira)) <= mente.MAX_COMENTARIO


def test_historico_nao_vai_para_a_memoria_compartilhada(tmp_path):
    pet = Paths(root=tmp_path).pet("bryan")
    assert pet.historico_chat.name == "historico_chat.jsonl"
    assert pet.historico_chat not in pet.todos()


# ---------------- no app de verdade ----------------

class ClienteFalso:
    ve_imagem = False

    def __init__(self, resposta):
        self.resposta = resposta

    def responder(self, sistema, mensagens, imagem=None):
        return self.resposta


@pytest.fixture
def qapp():
    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    return app


def criar_app(tmp_path, monkeypatch, **perms):
    paths = Paths(root=tmp_path)
    store = SettingsStore(paths)
    store.update(dict(config.DEFAULT_PERMISSIONS, ia=True, modo_teste=True, **perms))
    app = PestinhaApp(store, paths)
    monkeypatch.setattr(app.visao, "cliente", lambda: ClienteFalso(LONGA))
    return app


def fechar(app):
    app.visao.cancelar()
    app.balao.esconder()
    if app.conversa_janela:
        app.conversa_janela.close()
    app.tray.icon.hide()


def esperar(qapp, condicao, segundos=3.0):
    fim = time.monotonic() + segundos
    while time.monotonic() < fim:
        qapp.processEvents()
        if condicao():
            return True
        time.sleep(0.01)
    return False


def test_chat_guarda_a_resposta_inteira_e_volta_ao_abrir(qapp, tmp_path, monkeypatch):
    app = criar_app(tmp_path, monkeypatch)
    try:
        app.menu_conversar()
        app._enviar_conversa("como eu exporto?")
        assert esperar(qapp, lambda: not app.visao.respondendo)
        assert len(app.balao.texto) <= mente.MAX_COMENTARIO           # o balão continua curto
        tela = app.conversa_janela.historico.toPlainText()
        assert "como eu exporto?" in tela and "2. Escolha o formato." in tela
        assert tela.count("Depois é só salvar") == 12                 # inteira, não cortada
        falas = app.historico.ultimas()
        assert [f["quem"] for f in falas] == ["voce", "pet"] and falas[1]["texto"] == LONGA.strip()
    finally:
        fechar(app)
    outro = criar_app(tmp_path, monkeypatch)                          # abriu o app de novo
    try:
        outro.menu_conversar()
        tela = outro.conversa_janela.historico.toPlainText()
        assert "como eu exporto?" in tela and "2. Escolha o formato." in tela
    finally:
        fechar(outro)


def test_fala_pela_voz_entra_no_historico_mesmo_sem_o_chat_aberto(qapp, tmp_path, monkeypatch):
    app = criar_app(tmp_path, monkeypatch)
    try:
        assert app.conversa_janela is None
        app._ouvi("como eu exporto?")
        assert esperar(qapp, lambda: not app.visao.respondendo)
        falas = app.historico.ultimas()
        assert falas[0]["voz"] and falas[0]["texto"] == "como eu exporto?"
        assert falas[1]["texto"] == LONGA.strip()
        app.menu_conversar()
        assert "🎤" in app.conversa_janela.historico.toPlainText()
    finally:
        fechar(app)


def test_comando_e_resumo_do_video_tambem_ficam(qapp, tmp_path, monkeypatch):
    app = criar_app(tmp_path, monkeypatch)
    try:
        app._resumo_do_video("📺 Aula de física\nExplica a lei de Newton.")
        assert app.historico.ultimas()[-1]["texto"].startswith("📺 Aula de física\nExplica")
    finally:
        fechar(app)


def test_desligado_nao_guarda(qapp, tmp_path, monkeypatch):
    app = criar_app(tmp_path, monkeypatch, historico_chat=False)
    try:
        app.menu_conversar()
        app._enviar_conversa("oi")
        assert esperar(qapp, lambda: not app.visao.respondendo)
        assert "Depois é só salvar" in app.conversa_janela.historico.toPlainText()   # o chat mostra
        assert not app.pet_paths.historico_chat.exists()                            # mas não guarda
    finally:
        fechar(app)


def test_esquecer_apaga_o_historico(qapp, tmp_path, monkeypatch):
    app = criar_app(tmp_path, monkeypatch)
    try:
        app._ouvi("oi")
        assert esperar(qapp, lambda: not app.visao.respondendo)
        assert app.historico.ultimas() and app.visao.conversa.turnos
        app._esquecer_conversa()
        assert app.historico.ultimas() == [] and app.visao.conversa.turnos == []
        linhas = [json.loads(x) for x in app.pet_paths.historico_chat.read_text(encoding="utf-8").splitlines()] \
            if app.pet_paths.historico_chat.exists() else []
        assert linhas == []
    finally:
        fechar(app)
