"""
Voz: o áudio e o cliente do serviço de transcrição (com um servidor HTTP falso nesta máquina) e o
controlador dentro do app de verdade (Qt offscreen, microfone falso). Nenhum teste usa o microfone.
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

import numpy as np  # noqa: E402
import pytest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from pestinha import config  # noqa: E402
from pestinha.app import PestinhaApp  # noqa: E402
from pestinha.ia import voz  # noqa: E402
from pestinha.ia.provedores import ErroIA  # noqa: E402
from pestinha.mind import visao as visao_mod  # noqa: E402
from pestinha.mind import voz_ctl  # noqa: E402
from pestinha.paths import Paths  # noqa: E402
from pestinha.settings_store import SettingsStore  # noqa: E402


def tom(segundos=1.0, taxa=16000, volume=0.5):
    """PCM 16 bits mono de um tom de 220 Hz."""
    t = np.arange(int(segundos * taxa)) / taxa
    return (np.sin(2 * np.pi * 220 * t) * volume * 32767).astype("<i2").tobytes()


# ---------------- ia/voz.py: áudio ----------------

@pytest.mark.parametrize("texto, esperado", [
    ("", "http://localhost:11500"),
    ("192.168.3.250", "http://192.168.3.250:11500"),
    ("http://192.168.3.250:9000/", "http://192.168.3.250:9000"),
    ("ftp://x", None),
])
def test_endereco_da_voz(texto, esperado):
    assert voz.endereco_voz(texto) == esperado


def test_wav_de_pcm():
    wav = voz.wav_de_pcm(tom(0.5), 16000)
    assert wav[:4] == b"RIFF" and wav[8:12] == b"WAVE" and len(wav) == 44 + 16000


def test_microfone_em_float_estereo_vira_16_bits_mono():
    estereo = np.repeat(np.array([0.5, -0.5, 0.25], dtype="<f4"), 2).tobytes()
    mono = np.frombuffer(voz.para_mono16(estereo, "float", 2), dtype="<i2")
    assert list(mono) == [16383, -16383, 8191]
    assert voz.para_mono16(b"\x80\x80", "uint8", 1) == b"\x00\x00\x00\x00"     # 128 é o silêncio no uint8
    assert voz.duracao(tom(0.5), 16000) == pytest.approx(0.5)


# ---------------- ia/voz.py: o cliente, contra um servidor falso ----------------

class ServicoFalso(BaseHTTPRequestHandler):
    """Imita o pestinha-voz: /health e a transcrição."""

    pedidos = []

    def log_message(self, *_a):
        pass

    def _responder(self, codigo, corpo):
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def do_GET(self):
        if self.path == "/health":
            self._responder(200, json.dumps({"ok": True, "whisper": "large-v3-turbo"}).encode())
        else:
            self._responder(404, b"{}")

    def do_POST(self):
        corpo = self.rfile.read(int(self.headers["Content-Length"]))
        ServicoFalso.pedidos.append((self.path, self.headers["Content-Type"], corpo))
        if self.path == "/v1/audio/transcriptions":
            self._responder(200, json.dumps({"text": "  oi   Pestinha "}).encode())
        else:
            self._responder(500, b"")


@pytest.fixture
def servico():
    ServicoFalso.pedidos = []
    servidor = ThreadingHTTPServer(("127.0.0.1", 0), ServicoFalso)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    yield f"127.0.0.1:{servidor.server_address[1]}"
    servidor.shutdown()


def test_cliente_transcreve(servico):
    cliente = voz.ClienteVoz(servico)
    assert cliente.transcrever(voz.wav_de_pcm(tom(0.5), 16000), dica="Bryan") == "oi Pestinha"
    caminho, tipo, corpo = ServicoFalso.pedidos[0]
    assert caminho == "/v1/audio/transcriptions" and tipo.startswith("multipart/form-data")
    assert b'name="language"\r\n\r\npt' in corpo and b"Bryan" in corpo and b"RIFF" in corpo


def test_servico_fora_do_ar_vira_erro_explicado():
    with pytest.raises(ErroIA, match="não respondeu"):
        voz.ClienteVoz("127.0.0.1:9").transcrever(b"RIFF")
    with pytest.raises(ErroIA, match="inválido"):
        voz.ClienteVoz("ftp://x")


def test_testar_voz(servico):
    ok, mensagem = voz.testar_voz(servico)
    assert ok and "large-v3-turbo" in mensagem
    assert voz.testar_voz("127.0.0.1:9")[0] is False
    assert voz.testar_voz("ftp://x")[0] is False


# ---------------- controlador, dentro do app ----------------

@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    return app


class MicrofoneFalso:
    def __init__(self):
        self.aberto = False
        self.segundos = 1.0
        self.funciona = True

    def abrir(self):
        self.aberto = self.funciona
        return self.funciona

    def fechar(self):
        estava, self.aberto = self.aberto, False
        return (tom(self.segundos), 16000) if estava else (b"", 0)


class ClienteVozFalso:
    def __init__(self):
        self.ouvidos = []
        self.erro = None
        self.texto = "oi, tudo bem?"

    def transcrever(self, wav, dica=""):
        self.ouvidos.append((wav, dica))
        if self.erro:
            raise self.erro
        return self.texto


class ChatFalso:
    ve_imagem = True

    def __init__(self):
        self.chamadas = []

    def responder(self, sistema, mensagens, imagem=None):
        self.chamadas.append(mensagens)
        return "Tudo ótimo!"


@pytest.fixture
def pet(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(voz_ctl.plataforma, "iniciar_atalho_falar", lambda _cb: True)
    monkeypatch.setattr(voz_ctl.plataforma, "tecla_falar_segurada", lambda: True)
    paths = Paths(root=tmp_path)
    store = SettingsStore(paths)
    store.update(dict(config.DEFAULT_PERMISSIONS, ia=True, voz=True, modo_teste=True))
    app = PestinhaApp(store, paths)
    cliente, chat = ClienteVozFalso(), ChatFalso()
    app.voz.microfone = MicrofoneFalso()
    monkeypatch.setattr(app.voz, "cliente", lambda: cliente)
    monkeypatch.setattr(app.visao, "cliente", lambda: chat)
    monkeypatch.setattr(visao_mod, "capturar_tela", lambda *_a, **_k: None)
    app.pet.show()
    yield app, cliente, chat
    app.voz.cancelar()
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


def test_voz_comeca_desligada():
    assert config.DEFAULT_PERMISSIONS["voz"] is False


def test_segurar_o_atalho_falar_e_soltar_manda_o_texto_para_ele(qapp, pet, monkeypatch):
    app, cliente, chat = pet
    app.voz.apertou()
    assert app.voz.gravando == "atalho" and app.pet_state.ouvindo and app.voz.microfone.aberto
    monkeypatch.setattr(voz_ctl.plataforma, "tecla_falar_segurada", lambda: False)     # soltou
    assert esperar(qapp, lambda: app.balao.texto == "Tudo ótimo!")
    assert not app.voz.microfone.aberto and not app.pet_state.ouvindo
    assert cliente.ouvidos[0][1] == app.nome and cliente.ouvidos[0][0][:4] == b"RIFF"
    assert chat.chamadas[-1][-1]["content"].endswith("]\noi, tudo bem?")      # depois do estado da rede
    assert app.visao.conversa.turnos[-1]["content"] == "Tudo ótimo!"


def test_botao_do_microfone_poe_o_texto_no_campo_do_chat(qapp, pet):
    app, cliente, chat = pet
    app.menu_conversar()
    janela = app.conversa_janela
    assert not janela.mic.isHidden() and janela.mic.isEnabled()
    janela.campo.setText("olha:")
    janela.mic.click()
    assert app.voz.gravando == "chat" and janela.mic.isChecked() and "Ouvindo" in janela.estado.text()
    app.voz._passo()                                   # no chat, soltar a tecla não para: é o botão
    assert app.voz.gravando == "chat"
    janela.mic.click()
    assert esperar(qapp, lambda: janela.campo.text() == "olha: oi, tudo bem?")
    assert not janela.mic.isChecked() and janela.mic.isEnabled() and janela.estado.text() == ""
    assert chat.chamadas == []                          # não manda sozinho: você confere antes


def test_botao_do_microfone_some_sem_a_voz(qapp, pet):
    app, _cliente, _chat = pet
    app.menu_conversar()
    app.apply_perms({"voz": False})
    assert app.conversa_janela.mic.isHidden()
    app.apply_perms({"voz": True})
    assert not app.conversa_janela.mic.isHidden()


def test_sem_microfone_o_botao_volta_e_avisa(qapp, pet):
    app, _cliente, _chat = pet
    app.menu_conversar()
    avisos = []
    app.voz.aviso.connect(avisos.append)
    app.voz.microfone.funciona = False
    app.conversa_janela.mic.click()
    assert not app.voz.gravando and not app.conversa_janela.mic.isChecked()
    assert avisos == ["não achei um microfone"]


def test_toque_curto_e_ignorado(qapp, pet):
    app, cliente, _chat = pet
    app.voz.microfone.segundos = 0.1
    app.voz.ouvir("atalho")
    app.voz.parar_de_ouvir()
    qapp.processEvents()
    assert cliente.ouvidos == [] and not app.voz.transcrevendo


def test_sem_saber_quando_soltou_aperta_de_novo_para_parar(qapp, pet, monkeypatch):
    app, cliente, _chat = pet
    monkeypatch.setattr(voz_ctl.plataforma, "tecla_falar_segurada", lambda: None)     # macOS, Linux
    app.voz.apertou()
    app.voz._passo()
    assert app.voz.gravando
    app.voz.apertou()
    assert not app.voz.gravando and esperar(qapp, lambda: cliente.ouvidos)


def test_para_de_ouvir_sozinho_depois_do_maximo(qapp, pet):
    app, _cliente, _chat = pet
    app.voz.ouvir("chat")
    app.voz.ouvindo_desde -= voz_ctl.MAX_GRAVACAO + 1
    app.voz._passo()
    assert not app.voz.gravando and not app.voz.microfone.aberto


@pytest.mark.parametrize("mudanca", [{"voz": False}, {"ia": False}, {"conversa": False}])
def test_sem_permissao_nao_ouve(qapp, pet, mudanca):
    app, _cliente, _chat = pet
    app.apply_perms(mudanca)
    app.voz.apertou()
    app.voz.alternar_microfone()
    assert not app.voz.gravando and not app.voz.microfone.aberto


def test_desligar_a_voz_no_meio_fecha_o_microfone(qapp, pet):
    app, _cliente, _chat = pet
    app.voz.ouvir("atalho")
    app.apply_perms({"voz": False})
    assert not app.voz.gravando and not app.voz.microfone.aberto and not app.pet_state.ouvindo


def test_panico_fecha_o_microfone_e_descarta_o_texto_a_caminho(qapp, pet):
    app, cliente, chat = pet
    app.voz.ouvir("atalho")
    app.panic()
    assert not app.voz.microfone.aberto and not app.pet_state.ouvindo
    app.store.update({"ativo": True})
    geracao = app.voz.geracao
    app.voz.ouvir("atalho")
    app.panic()
    app.voz._ao_pronto("atalho", "oi", geracao)        # chegou depois do pânico
    qapp.processEvents()
    assert chat.chamadas == []


def test_pausa_fecha_o_microfone(qapp, pet):
    app, _cliente, _chat = pet
    app.voz.ouvir("atalho")
    app.toggle_pause()
    assert not app.voz.microfone.aberto
    app.voz.apertou()
    assert not app.voz.gravando
    app.toggle_pause()


def test_servico_fora_do_ar_ou_silencio_avisa_uma_vez(qapp, pet):
    app, cliente, _chat = pet
    avisos = []
    app.voz.aviso.connect(avisos.append)
    cliente.erro = ErroIA("o serviço de voz não respondeu")
    for _ in range(2):
        app.voz.ouvir("atalho")
        app.voz.parar_de_ouvir()
        assert esperar(qapp, lambda: not app.voz.transcrevendo)
    cliente.erro, cliente.texto = None, ""
    app.voz.ouvir("atalho")
    app.voz.parar_de_ouvir()
    assert esperar(qapp, lambda: len(avisos) == 2)
    assert avisos[0] == "o serviço de voz não respondeu" and avisos[1].startswith("não ouvi nada")


def test_voz_recria_o_cliente_ao_trocar_o_endereco(qapp, pet):
    app, _cliente, _chat = pet
    del app.voz.cliente
    app.apply_perms({"voz_url": "http://192.168.3.250:11500"})
    assert app.voz.cliente().base == "http://192.168.3.250:11500"
    app.apply_perms({"voz_url": ""})
    assert app.voz.cliente().base == "http://localhost:11500"


def test_atalho_so_e_registrado_com_a_voz_ligada(qapp, tmp_path, monkeypatch):
    registros = []
    monkeypatch.setattr(voz_ctl.plataforma, "iniciar_atalho_falar", lambda cb: registros.append(cb) or True)
    paths = Paths(root=tmp_path)
    store = SettingsStore(paths)
    store.update(dict(config.DEFAULT_PERMISSIONS, ia=True))
    app = PestinhaApp(store, paths)
    try:
        assert registros == [] and app.voz.atalho_ok is None
        app.apply_perms({"voz": True})
        app.apply_perms({"voz_url": "192.168.3.250"})
        assert len(registros) == 1 and app.voz.atalho_ok
    finally:
        app.tray.icon.hide()


def test_tela_de_configuracoes_da_voz(qapp, tmp_path, monkeypatch):
    from pestinha.ui.ui import SettingsDialog
    dialogo = SettingsDialog(dict(config.DEFAULT_PERMISSIONS), Paths(root=tmp_path), first_run=False)
    try:
        assert not dialogo.boxes["voz"].isEnabled() and not dialogo.voz_campo.isEnabled()
        dialogo.boxes["ia"].setChecked(True)
        assert dialogo.boxes["voz"].isEnabled() and not dialogo.voz_campo.isEnabled()
        dialogo.boxes["voz"].setChecked(True)
        assert dialogo.voz_campo.isEnabled() and dialogo.voz_botao.isEnabled()
        dialogo.voz_campo.setText("192.168.3.250")
        dialogo.voz_campo.editingFinished.emit()
        assert dialogo.perms["voz_url"] == "http://192.168.3.250:11500"
        dialogo.voz_campo.setText("ftp://nada")
        dialogo.voz_campo.editingFinished.emit()
        assert dialogo.perms["voz_url"] == "http://192.168.3.250:11500"
        assert dialogo.voz_estado.objectName() == "erro"
        monkeypatch.setattr(voz, "testar_voz", lambda _e: (True, "ok"))
        dialogo.voz_botao.click()
        assert dialogo.voz_estado.objectName() == "ok"
        dialogo.boxes["conversa"].setChecked(False)
        assert not dialogo.boxes["voz"].isEnabled() and not dialogo.voz_campo.isEnabled()
    finally:
        dialogo.close()
