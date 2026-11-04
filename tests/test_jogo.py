"""
Acompanhar jogos (#4): o Ollama sem "pensar", o reconhecimento do jogo, o pedido de jogo, o print repetido
que não é mandado e o freio da fala, com o controlador dentro do app de verdade (Qt offscreen, modelo falso).
"""

import base64
import os
import sys
import time
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402
from PySide6.QtCore import QBuffer, QIODevice  # noqa: E402
from PySide6.QtGui import QColor, QImage  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from pestinha import config  # noqa: E402
from pestinha.app import PestinhaApp  # noqa: E402
from pestinha.ia import mente, provedores  # noqa: E402
from pestinha.mind import visao as visao_mod  # noqa: E402
from pestinha.paths import Paths  # noqa: E402
from pestinha.sense import senses  # noqa: E402
from pestinha.settings_store import SettingsStore  # noqa: E402

OLHADA = '{"resumo": "jogando Minecraft", "comentario": "Achou diamante!", "novidade": 0.9}'


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    return app


def print_de(cor, qapp):
    """Um 'print' de uma cor só, em JPEG base64 (como o capturar_tela devolve)."""
    imagem = QImage(320, 180, QImage.Format_RGB32)
    imagem.fill(QColor(cor))
    buffer = QBuffer()
    buffer.open(QIODevice.WriteOnly)
    imagem.save(buffer, "JPG", 70)
    return base64.b64encode(bytes(buffer.data())).decode("ascii")


# ---------------- provedores: Ollama sem pensar ----------------

class _Chamadas:
    def __init__(self):
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))])


def test_ollama_responde_sem_pensar():
    cliente = provedores.criar_cliente("ollama", "gemma4:e4b", "192.168.3.250")
    chamadas = _Chamadas()
    cliente.cliente = SimpleNamespace(chat=SimpleNamespace(completions=chamadas))
    cliente.responder("s", [{"role": "user", "content": "x"}])
    assert chamadas.kwargs["extra_body"] == {"reasoning_effort": "none"}


def test_api_paga_nao_recebe_o_ajuste_do_ollama(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "teste")
    cliente = provedores.criar_cliente("deepseek")
    chamadas = _Chamadas()
    cliente.cliente = SimpleNamespace(chat=SimpleNamespace(completions=chamadas))
    cliente.responder("s", [{"role": "user", "content": "x"}])
    assert chamadas.kwargs["extra_body"] is None


# ---------------- sentidos e mente ----------------

@pytest.mark.parametrize("app, titulo, esperado", [
    ("javaw.exe", "Minecraft 1.21.4 - Singleplayer", True),
    ("javaw", "Minecraft* 1.21", True),
    ("javaw.exe", "IntelliJ IDEA", False),
    ("chrome.exe", "Minecraft Wiki", False),            # ler sobre o jogo não é jogar
    ("javaw.exe", None, False),
])
def test_minecraft_java_pelo_titulo(app, titulo, esperado):
    assert senses.jogo_pelo_titulo(app, titulo) is esperado


def test_jogos_da_lista_sao_gaming():
    for app in ("Minecraft.Windows.exe", "RobloxPlayerBeta.exe", "cs2.exe"):
        assert senses.detect_activity(app, 0.0, 300.0) == "GAMING"


@pytest.mark.parametrize("caminho, esperado", [
    # qualquer jogo instalado numa biblioteca conta, sem estar na lista
    (r"C:\Program Files (x86)\Steam\steamapps\common\PBZ\steam\PBZ.exe", True),         # Phantom Blade Zero
    (r"D:\SteamLibrary\steamapps\common\ELDEN RING\Game\eldenring.exe", True),
    (r"C:\Program Files\Epic Games\Fortnite\FortniteGame\Binaries\Win64\FortniteClient-Win64-Shipping.exe", True),
    (r"C:\XboxGames\Forza Horizon 5\Content\ForzaHorizon5.exe", True),
    (r"E:\Jogos\Wukong\b1\Binaries\Win64\b1-Win64-Shipping.exe", True),                 # Unreal, fora da biblioteca
    ("/home/eu/.local/share/Steam/steamapps/common/Terraria/Terraria.bin.x86_64", True),
    # não são jogos
    (r"C:\Program Files (x86)\Steam\steamapps\common\wallpaper_engine\wallpaper64.exe", False),
    (r"C:\Program Files (x86)\Epic Games\Launcher\Portal\Binaries\Win64\EpicGamesLauncher.exe", False),
    (r"C:\Program Files (x86)\Steam\steam.exe", False),
    (r"C:\Program Files\Mozilla Firefox\firefox.exe", False),
    ("", False),
])
def test_jogo_pela_pasta_onde_esta_instalado(caminho, esperado):
    assert senses.jogo_pelo_caminho(caminho) is esperado
    nome = caminho.replace("\\", "/").rsplit("/", 1)[-1]
    assert (senses.detect_activity(nome, 0.0, 300.0, caminho) == "GAMING") is esperado


def test_pedido_de_jogo_so_com_o_modo_jogo():
    com = mente.pedido_observacao("javaw", "Minecraft", "GAMING", "curioso", jogo=True)
    sem = mente.pedido_observacao("javaw", "Minecraft", "GAMING", "curioso")
    assert "acompanhando a partida" in com and "comemore" in com
    assert "acompanhando a partida" not in sem


def test_miniatura_compara_prints(qapp):
    verde, verde2, preto = (visao_mod.miniatura(print_de(c, qapp)) for c in ("#22aa22", "#22aa22", "#000000"))
    assert len(verde) == visao_mod.TAMANHO_MINI[0] * visao_mod.TAMANHO_MINI[1]
    assert visao_mod.diferenca(verde, verde2) < visao_mod.QUASE_IGUAL
    assert visao_mod.diferenca(verde, preto) > 0.3
    assert visao_mod.miniatura("PRINT") is None and visao_mod.diferenca(None, verde) == 1.0


# ---------------- controlador, dentro do app ----------------

class ClienteFalso:
    ve_imagem = True

    def __init__(self, resposta):
        self.resposta = resposta
        self.chamadas = []

    def responder(self, sistema, mensagens, imagem=None):
        self.chamadas.append((mensagens, imagem))
        return self.resposta


@pytest.fixture
def pet(qapp, tmp_path, monkeypatch):
    paths = Paths(root=tmp_path)
    store = SettingsStore(paths)
    store.update(dict(config.DEFAULT_PERMISSIONS, ia=True, ver_tela=True, jogos=True, ia_provedor="ollama"))
    app = PestinhaApp(store, paths)
    olhos = ClienteFalso(OLHADA)
    tela = {"print": print_de("#22aa22", qapp)}
    monkeypatch.setattr(app.visao, "cliente", lambda: olhos)
    monkeypatch.setattr(visao_mod, "capturar_tela", lambda *_a, **_k: tela["print"])
    monkeypatch.setattr(visao_mod.senses, "get_active_app", lambda: "javaw.exe")
    monkeypatch.setattr(visao_mod.senses, "get_active_title", lambda: "Minecraft 1.21.4 - Singleplayer")
    app.pet.show()
    yield app, olhos, tela
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


def olhar(qapp, app, olhos, agora):
    """Uma olhada no instante `agora`; espera a resposta (se ela saiu)."""
    antes = len(olhos.chamadas)
    app.visao.olhar(agora)
    if len(olhos.chamadas) > antes or app.visao.olhando:
        assert esperar(qapp, lambda: not app.visao.olhando)
    return len(olhos.chamadas) > antes


def test_em_jogo_olha_bem_mais_seguido(qapp, pet):
    app, _olhos, _tela = pet
    prof = app.prof
    assert app.visao.em_jogo()
    assert app.visao.intervalo() == prof["visao_jogo"] < prof["visao_intervalo"]
    app.apply_perms({"ia_provedor": "claude"})
    assert app.visao.intervalo() == prof["visao_jogo_nuvem"]          # API paga: mais devagar
    app.apply_perms({"jogos": False})
    assert not app.visao.em_jogo() and app.visao.intervalo() == prof["visao_intervalo"]


def test_o_modelo_recebe_o_pedido_de_jogo(qapp, pet):
    app, olhos, _tela = pet
    assert olhar(qapp, app, olhos, time.monotonic())
    assert "acompanhando a partida" in olhos.chamadas[0][0][0]["content"]


def test_tela_parada_nao_gasta_olhada(qapp, pet):
    app, olhos, tela = pet
    agora = time.monotonic()
    assert olhar(qapp, app, olhos, agora)
    assert not olhar(qapp, app, olhos, agora + 8)                      # mesma tela: não manda
    tela["print"] = print_de("#000000", qapp)
    assert olhar(qapp, app, olhos, agora + 16)                         # mudou: manda
    assert olhar(qapp, app, olhos, agora + 16 + app.prof["visao_intervalo"] + 1)   # parada há muito: manda


def test_fora_do_jogo_manda_sempre(qapp, pet):
    app, olhos, _tela = pet
    app.apply_perms({"jogos": False})
    agora = time.monotonic()
    assert olhar(qapp, app, olhos, agora) and olhar(qapp, app, olhos, agora + 200)


def test_em_jogo_fala_bem_menos_do_que_ve(qapp, pet):
    app, olhos, tela = pet
    falas = []
    app.visao.fala.connect(falas.append)
    agora = time.monotonic()
    olhar(qapp, app, olhos, agora)
    tela["print"] = print_de("#000000", qapp)
    olhos.resposta = '{"resumo": "jogando", "comentario": "Que pulo!"}'
    olhar(qapp, app, olhos, agora + 8)                                 # olhou, mas ainda é cedo para falar
    assert len(olhos.chamadas) == 2 and falas == ["Achou diamante!"]
    app.visao.olhar_agora()                                            # pedido seu: sempre responde
    assert esperar(qapp, lambda: len(falas) == 2)


def test_troca_para_o_jogo_olha_logo(qapp, pet):
    app, _olhos, _tela = pet
    agora = time.monotonic()
    app.visao.ultima_olhada = agora
    app.visao.proxima = agora + 1000
    app.visao.app_mudou(agora)
    assert app.visao.proxima <= agora + max(visao_mod.ESPERA_TROCA, app.prof["visao_jogo"])


def test_configuracoes_e_padrao(qapp, tmp_path):
    from pestinha.ui.ui import SettingsDialog
    assert config.DEFAULT_PERMISSIONS["jogos"] is False
    dialogo = SettingsDialog(dict(config.DEFAULT_PERMISSIONS), Paths(root=tmp_path), first_run=False)
    assert not dialogo.boxes["jogos"].isEnabled()
    dialogo.boxes["ia"].setChecked(True)
    dialogo.boxes["ver_tela"].setChecked(True)
    assert dialogo.boxes["jogos"].isEnabled()
    dialogo.close()
