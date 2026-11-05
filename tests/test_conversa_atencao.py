"""
Falar ou escrever com o pet conta como atenção (como um carinho): a carência cai, a tristeza alivia e a
rede recebe recompensa, na hora em que você fala, mesmo que a IA não responda. App de verdade, Qt offscreen.
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
from pestinha.app import PestinhaApp  # noqa: E402
from pestinha.paths import Paths  # noqa: E402
from pestinha.settings_store import SettingsStore  # noqa: E402


@pytest.fixture
def qapp():
    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    return app


@pytest.fixture
def pet(qapp, tmp_path, monkeypatch):
    paths = Paths(root=tmp_path)
    store = SettingsStore(paths)
    store.update(dict(config.DEFAULT_PERMISSIONS, modo_teste=True))     # IA desligada: ninguém responde
    app = PestinhaApp(store, paths)
    app.drives.contact = 0.9            # carente
    app.sad.grievance = 1.0             # triste
    yield app
    app.balao.esconder()
    if app.conversa_janela:
        app.conversa_janela.close()
    app.tray.icon.hide()


@pytest.mark.parametrize("como", ["voz", "texto"])
def test_falar_com_ele_e_atencao_mesmo_sem_resposta(pet, como):
    app = pet
    if como == "voz":
        app._ouvi("oi, tudo bem?")
    else:
        app.menu_conversar()
        app._enviar_conversa("oi, tudo bem?")
    assert app.drives.contact < 0.6
    assert app.sad.grievance < 1.0
    assert app.senses.pulse["CONVERSA"] > 0.5
    assert app.recompensa_conversa_ate > time.monotonic()


def test_recompensa_vai_para_a_rede(pet, monkeypatch):
    app = pet
    recompensas = []
    original = app.brain.learn
    monkeypatch.setattr(app.brain, "learn", lambda r, dt, rate: recompensas.append(r) or original(r, dt, rate))
    app._ouvi("oi")
    app.think()
    assert recompensas and recompensas[-1] > 0


def test_pausado_nao_conta(pet):
    app = pet
    app.paused = True
    app._ouvi("oi")
    assert app.drives.contact == 0.9 and app.sad.grievance == 1.0
