"""
Chaves de API no .env: gravar pela tela de Configurações, carregar ao abrir, nunca aceitar uma chave
no campo de modelo. Tudo numa pasta temporária; o ambiente do processo é restaurado a cada teste.
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from pestinha import config  # noqa: E402
from pestinha.ia import chaves, provedores  # noqa: E402
from pestinha.paths import Paths  # noqa: E402
from pestinha.settings_store import SettingsStore  # noqa: E402

CHAVE = "sk-ant-api03-" + "x" * 80 + "AbCd"


@pytest.fixture(autouse=True)
def ambiente_limpo(monkeypatch):
    for nome in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "DEEPSEEK_API_KEY"):
        monkeypatch.delenv(nome, raising=False)


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


# ---------------- arquivo .env ----------------

def test_salva_carrega_e_vale_na_hora(tmp_path):
    env = tmp_path / ".env"
    chaves.salvar_chave(env, "ANTHROPIC_API_KEY", CHAVE)
    assert os.environ["ANTHROPIC_API_KEY"] == CHAVE                 # sem reabrir
    del os.environ["ANTHROPIC_API_KEY"]
    assert chaves.carregar_env(env) == ["ANTHROPIC_API_KEY"]        # e na próxima abertura
    assert os.environ["ANTHROPIC_API_KEY"] == CHAVE


def test_trocar_a_chave_mantem_o_resto_do_arquivo(tmp_path):
    env = tmp_path / ".env"
    env.write_text("# meu comentário\nOUTRA=1\nANTHROPIC_API_KEY=velha\nANTHROPIC_API_KEY=repetida\n",
                   encoding="utf-8")
    chaves.salvar_chave(env, "ANTHROPIC_API_KEY", CHAVE)
    linhas = env.read_text(encoding="utf-8").splitlines()
    assert linhas == ["# meu comentário", "OUTRA=1", f"ANTHROPIC_API_KEY={CHAVE}"]


@pytest.mark.parametrize("valor", ["", "  ", "com espaço", 'aspas"', "a\nb", "x=y"])
def test_chave_invalida_nao_grava(tmp_path, valor):
    with pytest.raises(ValueError):
        chaves.salvar_chave(tmp_path / ".env", "ANTHROPIC_API_KEY", valor)
    assert not (tmp_path / ".env").exists()


def test_le_aspas_export_e_ignora_lixo(tmp_path):
    env = tmp_path / ".env"
    env.write_text('export OPENAI_API_KEY="abc"\nlixo sem igual\n#X=1\nminusculo=2\n', encoding="utf-8")
    assert chaves.ler_env(env) == {"OPENAI_API_KEY": "abc"}


def test_env_fica_fora_do_git_e_da_memory():
    assert Paths().env.parent == ROOT and Paths().env.parent != Paths().memory
    assert ".env" in (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()


# ---------------- modelo nunca guarda chave ----------------

@pytest.mark.parametrize("texto, chave", [
    (CHAVE, True), ("sk-proj-abc", True), ("claude-haiku-5-5", False), ("qwen2.5vl:7b", False), ("", False),
])
def test_parece_chave(texto, chave):
    assert chaves.parece_chave(texto) is chave


def test_chave_no_campo_modelo_nao_e_gravada_nem_usada(tmp_path):
    paths = Paths(root=tmp_path)
    store = SettingsStore(paths)
    store.update({"ia_modelo": CHAVE})
    assert store["ia_modelo"] == "" and CHAVE not in paths.permissions.read_text(encoding="utf-8")
    assert provedores.modelo_de("claude", CHAVE) == provedores.PROVEDORES["claude"]["modelo"]


def test_arquivo_antigo_com_chave_no_modelo_e_limpo_ao_abrir(tmp_path):
    paths = Paths(root=tmp_path)
    paths.memory.mkdir()
    paths.permissions.write_text(f'{{"ia_modelo": "{CHAVE}"}}', encoding="utf-8")
    assert config.load_permissions(paths)["ia_modelo"] == ""


# ---------------- tela de Configurações ----------------

@pytest.fixture
def dialogo(qapp, tmp_path):
    from pestinha.ui.ui import SettingsDialog
    perms = dict(config.DEFAULT_PERMISSIONS, ia=True)
    d = SettingsDialog(perms, Paths(root=tmp_path), first_run=False)
    yield d
    d.close()


def test_botao_salva_no_env_some_do_campo_e_avisa_em_verde(dialogo, tmp_path):
    salvas = []
    dialogo.chave_salva.connect(salvas.append)
    assert dialogo.chave_estado.objectName() == "erro"              # começa sem chave
    dialogo.chave_campo.setText(CHAVE)
    dialogo.chave_botao.click()
    assert dialogo.chave_campo.text() == ""
    assert dialogo.chave_estado.objectName() == "ok" and "AbCd" in dialogo.chave_estado.text()
    assert CHAVE not in dialogo.chave_estado.text()
    assert f"ANTHROPIC_API_KEY={CHAVE}" in (tmp_path / ".env").read_text(encoding="utf-8")
    assert salvas == ["ANTHROPIC_API_KEY"]
    assert dialogo.chave_campo.echoMode() == dialogo.chave_campo.EchoMode.Password


def test_chave_ruim_avisa_em_vermelho_e_nao_grava(dialogo, tmp_path):
    dialogo.chave_campo.setText("com espaço")
    dialogo.chave_botao.click()
    assert dialogo.chave_campo.text() == "" and dialogo.chave_estado.objectName() == "erro"
    assert not (tmp_path / ".env").exists()


def test_chave_colada_no_modelo_e_recusada(dialogo):
    mudancas = []
    dialogo.changed.connect(mudancas.append)
    dialogo.modelo_campo.setEditText(CHAVE)
    dialogo.modelo_campo.lineEdit().editingFinished.emit()
    assert dialogo.modelo_campo.currentText() == "" and dialogo.perms["ia_modelo"] == ""
    assert mudancas == [{"ia_modelo": ""}] and dialogo.chave_estado.objectName() == "erro"


def test_ollama_nao_mostra_campo_de_chave(dialogo):
    dialogo.provedor_combo.setCurrentIndex(dialogo.provedor_combo.findData("ollama"))
    assert dialogo.chave_linha.isHidden()
    dialogo.provedor_combo.setCurrentIndex(dialogo.provedor_combo.findData("openai"))
    assert not dialogo.chave_linha.isHidden() and "OPENAI_API_KEY" in dialogo.chave_campo.placeholderText()


def test_chave_salva_destrava_a_visao(qapp, tmp_path, monkeypatch):
    from pestinha.app import PestinhaApp
    paths = Paths(root=tmp_path)
    store = SettingsStore(paths)
    store.update(dict(config.DEFAULT_PERMISSIONS, ia=True, ver_tela=True))
    app = PestinhaApp(store, paths)
    try:
        app.visao.proxima = 1e12                     # esperando depois de uma falha de chave
        app.visao._cliente = object()
        app.open_settings()
        app.settings.chave_campo.setText(CHAVE)
        app.settings.chave_botao.click()
        assert app.visao._cliente is None and app.visao.proxima < 1e12
    finally:
        app.settings.close()
        app.tray.icon.hide()
