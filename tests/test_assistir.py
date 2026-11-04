"""
Assistindo você jogar: com "Acompanhar jogos" e um jogo na tela, ele vai para o monitor ao lado (o mais à
direita que não é o do jogo), fica parado olhando para a partida e comenta, sem passear nem aprontar.
"""
import sys
import time
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from pestinha import config  # noqa: E402
from pestinha.body.behavior import Behavior  # noqa: E402
from pestinha.body.pet_state import PetState  # noqa: E402
from pestinha.core.physics import Body  # noqa: E402
from pestinha.mind import assistir  # noqa: E402
from pestinha.mind.assistir import AssistirController, escolher_lugar, monitor_de  # noqa: E402

QApplication.instance() or QApplication([])

ESQUERDA = (0, 0, 1920, 1040)           # monitor do jogo
DIREITA = (1920, 0, 3840, 1040)         # monitor ao lado
TERCEIRO = (-1920, 0, 0, 1040)
JOGO = (960, 520)                       # meio da janela do jogo


def corpo(x=500, y=990):
    b = Body(x, y, 60, 45)
    b.grounded = True
    return b


# ---------------- onde ele assiste ----------------

def test_vai_para_o_monitor_da_direita_perto_do_jogo():
    assert escolher_lugar([ESQUERDA, DIREITA], 0) == (1920 + assistir.DISTANCIA_BORDA, 1)


def test_jogo_na_direita_assiste_da_esquerda_perto_do_jogo():
    assert escolher_lugar([ESQUERDA, DIREITA], 1) == (1920 - assistir.DISTANCIA_BORDA, 0)


def test_com_tres_monitores_prefere_o_mais_a_direita():
    assert escolher_lugar([TERCEIRO, ESQUERDA, DIREITA], 1)[1] == 2
    assert escolher_lugar([TERCEIRO, ESQUERDA, DIREITA], 2)[1] == 1      # jogo na direita: o mais à direita que sobra


def test_um_monitor_so_fica_no_canto():
    assert escolher_lugar([ESQUERDA], 0) == (1920 - assistir.CANTO, 0)
    assert escolher_lugar([], 0) is None
    assert monitor_de([ESQUERDA, DIREITA], 2000, 500) == 1 and monitor_de([ESQUERDA], -5, 5) is None


# ---------------- controlador ----------------

def test_sem_jogo_nao_assiste():
    c, st = AssistirController(), PetState()
    c.atualizar(0.0, False, [ESQUERDA, DIREITA], JOGO, corpo())
    c.agir(0.0, corpo(), st)
    assert not c.ativo and st.assistindo is None and not c.libera_tela_cheia()


def test_jogando_diz_para_onde_ir_e_para_onde_olhar():
    c, st, b = AssistirController(), PetState(), corpo()
    c.atualizar(0.0, True, [ESQUERDA, DIREITA], JOGO, b)
    c.agir(0.0, b, st)
    assert c.ativo and c.libera_tela_cheia()
    assert st.assistindo == (1920 + assistir.DISTANCIA_BORDA, JOGO)


def test_travado_aparece_direto_no_lugar():
    c, st, b = AssistirController(), PetState(), corpo()
    c.atualizar(0.0, True, [ESQUERDA, DIREITA], JOGO, b)
    c.agir(0.0, b, st)
    c.agir(assistir.TRAVADO + 0.1, b, st)                               # não andou nada em 3 s
    assert b.x == 1920 + assistir.DISTANCIA_BORDA and b.y == DIREITA[1] + assistir.QUEDA
    assert not b.grounded and b.vx == 0.0


def test_andando_nao_e_travado():
    c, st, b = AssistirController(), PetState(), corpo()
    c.atualizar(0.0, True, [ESQUERDA, DIREITA], JOGO, b)
    for i in range(60):
        b.x += 40                                                        # andando para a direita
        c.agir(i * 0.1, b, st)
    assert b.y == 990                                                    # chegou andando, sem aparecer


def test_tela_cheia_aparece_na_hora_no_outro_monitor():
    c, b = AssistirController(), corpo()
    c.atualizar(0.0, True, [ESQUERDA, DIREITA], JOGO, b, tela_cheia=True)
    assert monitor_de([ESQUERDA, DIREITA], b.x, b.y) == 1


def test_arrastado_fica_onde_voce_soltou_e_depois_volta():
    c, st, b = AssistirController(), PetState(), corpo(x=3000)
    c.atualizar(0.0, True, [ESQUERDA, DIREITA], JOGO, b)
    c.arrastado(1.0)
    c.agir(2.0, b, st)
    assert st.assistindo[0] == 3000                                      # fica onde você soltou
    c.agir(1.0 + assistir.ESPERA_APOS_ARRASTE + 0.1, b, st)
    assert st.assistindo[0] == 1920 + assistir.DISTANCIA_BORDA


def test_segurando_ele_nao_teleporta():
    c, st, b = AssistirController(), PetState(), corpo()
    b.held = True
    c.atualizar(0.0, True, [ESQUERDA, DIREITA], JOGO, b, tela_cheia=True)
    c.agir(10.0, b, st)
    assert b.x == 500


# ---------------- comportamento ----------------

def comportamento(b, st):
    beh = Behavior(b, st, SimpleNamespace(things=[]))
    return beh


def test_anda_ate_o_lugar_para_e_olha_o_jogo():
    b, st = corpo(x=1500), PetState()
    beh = comportamento(b, st)
    st.assistindo = (2070, JOGO)
    beh.mission = ("cross", 100, 99.0)
    beh.tick(0.016, 0.0, (0, 0), ESQUERDA, config.PROFILES["normal"])
    assert b.vx > 0 and beh.mission is None                             # vai para a direita, larga a missão
    assert st.gaze[0] < 0                                               # olhando para o jogo, à esquerda
    b.x = 2065
    beh.tick(0.016, 0.1, (0, 0), DIREITA, {})
    assert b.vx == 0.0


def test_dormindo_nao_vai_assistir():
    b, st = corpo(x=1500), PetState()
    beh = comportamento(b, st)
    beh.emotion = "dormindo"
    st.assistindo = (2070, JOGO)
    beh.tick(0.016, 0.0, (0, 0), ESQUERDA, {"roam_interval": (3, 5)})
    assert b.vx == 0.0


# ---------------- dentro do app ----------------

@pytest.fixture
def app(tmp_path, monkeypatch):
    from pestinha.app import PestinhaApp
    from pestinha.paths import Paths
    from pestinha.settings_store import SettingsStore
    qapp = QApplication.instance()
    qapp.setQuitOnLastWindowClosed(False)
    paths = Paths(root=tmp_path)
    store = SettingsStore(paths)
    store.update(dict(config.DEFAULT_PERMISSIONS, ia=True, ver_tela=True, jogos=True, travessuras=True,
                      modo_teste=True))
    a = PestinhaApp(store, paths)
    monkeypatch.setattr(a, "screen_bounds", lambda: [ESQUERDA, DIREITA])
    monkeypatch.setattr(a.visao, "em_jogo", lambda: True)
    monkeypatch.setattr("pestinha.app.senses.foreground_rect", lambda *_: (0, 0, 1920, 1080))
    monkeypatch.setattr("pestinha.app.QGuiApplication.primaryScreen",
                        lambda: SimpleNamespace(devicePixelRatio=lambda: 1.0))
    a.pet.show()
    yield a
    a.visao.cancelar()
    a.balao.esconder()
    a.holograma.esconder()
    a.mischief.clear()
    a.tray.icon.hide()


def test_jogando_o_app_liga_o_modo_e_nao_apronta(app):
    app._atualizar_mente(time.monotonic())
    assert "jogo" in app.pet_state.mente and app.assistir.ativo
    assert app.assistir.lugar == (1920 + assistir.DISTANCIA_BORDA, 1)
    chamou = []
    app.mischief_ctl.maybe_act = lambda *a, **k: chamou.append(1)
    app.maybe_mischief(time.monotonic(), 0.016, ESQUERDA, (0, 0), {})
    assert chamou == []                                                 # assistindo não apronta


def test_tela_cheia_do_jogo_nao_esconde_quem_assiste_do_lado(app):
    app.tela_cheia_bruta = True
    app._atualizar_mente(time.monotonic())
    assert not app.fullscreen and app.pet.isVisible()
    assert monitor_de([ESQUERDA, DIREITA], app.pet.body.x, app.pet.body.y) == 1
    app.visao.em_jogo = lambda: False                                   # parou de jogar: tela cheia volta a esconder
    app._atualizar_mente(time.monotonic())
    assert app.fullscreen and not app.pet.isVisible()
