"""
QtMultimedia opcional (pestinha/multimidia.py): com só o PySide6-Essentials o pet abre, e voz, chamado pelo
nome e música ficam desligados, com aviso. A falta do módulo é simulada com sys.modules[...] = None.
"""

import os
import subprocess
import sys
import textwrap
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from pestinha import config, multimidia  # noqa: E402
from pestinha.paths import Paths  # noqa: E402
from pestinha.settings_store import SettingsStore  # noqa: E402


@pytest.fixture
def sem_multimidia(monkeypatch):
    """Faz de conta que o PySide6-Addons não está instalado."""
    monkeypatch.setitem(sys.modules, multimidia.NOME, None)
    multimidia.esquecer()
    yield
    multimidia.esquecer()


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    return app


def test_sem_o_modulo_nao_esta_disponivel_e_avisa_no_log(sem_multimidia, monkeypatch):
    linhas = []
    monkeypatch.setattr(multimidia, "log", linhas.append)
    assert multimidia.disponivel() is False
    assert multimidia.disponivel() is False                 # conferiu uma vez só
    assert len(linhas) == 1 and "PySide6-Addons" in linhas[0]


def test_com_o_modulo_esta_disponivel():
    pytest.importorskip(multimidia.NOME)
    multimidia.esquecer()
    assert multimidia.disponivel() is True


def test_nenhum_modulo_importa_o_qtmultimedia_ao_carregar():
    """Num Python novo, sem o módulo, o app inteiro importa (antes, voz_ctl e chamado_ctl quebravam)."""
    codigo = textwrap.dedent(f"""
        import sys
        sys.path.insert(0, {str(ROOT)!r})
        sys.modules["PySide6.QtMultimedia"] = None
        import pestinha.app, pestinha.ui.ui, pestinha.mind.voz_ctl, pestinha.mind.chamado_ctl
        import pestinha.mind.musica_ctl
        print("ok")
    """)
    saida = subprocess.run([sys.executable, "-c", codigo], capture_output=True, text=True, timeout=120,
                           env=dict(os.environ, QT_QPA_PLATFORM="offscreen"))
    assert saida.returncode == 0, saida.stderr
    assert saida.stdout.strip() == "ok"


def test_o_app_abre_sem_o_modulo_com_voz_chamado_e_musica_desligados(qapp, tmp_path, sem_multimidia):
    from pestinha.app import PestinhaApp
    paths = Paths(root=tmp_path)
    store = SettingsStore(paths)
    store.update(dict(config.DEFAULT_PERMISSIONS, ia=True, conversa=True, voz=True, chamar=True))
    app = PestinhaApp(store, paths)
    try:
        assert not app.voz.ligada()
        assert not app.voz.ouvir("chat")                        # o botão do microfone não abre nada
        assert not app.chamado.permitido()
        app.chamado.sincronizar()
        assert not app.chamado.ouvindo
        resposta = app.tocar_musica("lo-fi")
        assert "PySide6-Addons" in resposta and not app.musica.ativa()
        app.open_settings()
        for chave in ("voz", "chamar"):
            caixa = app.settings.boxes[chave]
            assert not caixa.isEnabled() and "PySide6-Addons" in caixa.toolTip()
        app.settings._sync_enabled()                            # o aviso não se repete na dica
        assert app.settings.boxes["voz"].toolTip().count("Desligado:") == 1
    finally:
        if app.settings:
            app.settings.close()
        app.tray.icon.hide()


def test_o_chamado_sem_o_modulo_nao_abre_o_microfone(qapp, tmp_path, sem_multimidia):
    from pestinha.app import PestinhaApp
    paths = Paths(root=tmp_path)
    app = PestinhaApp(SettingsStore(paths), paths)
    try:
        assert app.chamado.comecar() is False and not app.chamado.ouvindo
    finally:
        app.tray.icon.hide()
