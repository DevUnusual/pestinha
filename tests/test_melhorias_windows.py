"""Melhorias para o Windows: tela cheia, vários monitores, pasta de dados, uma cópia só, início automático e fechamento seguro."""
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import main as main_mod  # noqa: E402
from pestinha import config, log as log_module, store  # noqa: E402
from pestinha.app import PestinhaApp  # noqa: E402
from pestinha.paths import Paths, pasta_de_dados  # noqa: E402
from pestinha.sense import senses  # noqa: E402
from pestinha.settings_store import SettingsStore  # noqa: E402

windows = None
if sys.platform == "win32":
    from pestinha.plataforma import windows  # noqa: E402

so_windows = pytest.mark.skipif(sys.platform != "win32", reason="Requer backend Windows")


@pytest.fixture
def pet(tmp_path):
    QApplication.instance() or QApplication([])
    paths = Paths(root=tmp_path)
    settings = SettingsStore(paths)
    settings.update(dict(config.DEFAULT_PERMISSIONS))
    app = PestinhaApp(settings, paths)
    yield app
    app.tray.icon.hide()


# ----- tela cheia -----

@so_windows
@pytest.mark.parametrize("janela, zoom, estilo, esperado", [
    ((-8, -8, 1928, 1088), 1, "moldura", False),     # maximizada em monitor sem barra de tarefas
    ((0, 0, 1920, 1080), 0, "sem", True),            # tela cheia de verdade
    ((0, 0, 1920, 1080), 1, "sem", True),            # tela cheia vinda de uma janela maximizada
    ((100, 100, 900, 700), 0, "moldura", False),     # janela comum
])
def test_tela_cheia_nao_confunde_janela_maximizada(monkeypatch, janela, zoom, estilo, esperado):
    win32con = windows.win32con
    valor = win32con.WS_CAPTION | win32con.WS_THICKFRAME if estilo == "moldura" else win32con.WS_POPUP
    monkeypatch.setattr(windows.win32gui, "GetForegroundWindow", lambda: 1)
    monkeypatch.setattr(windows.win32gui, "GetClassName", lambda h: "Chrome_WidgetWin_1")
    monkeypatch.setattr(windows.win32gui, "GetWindowLong", lambda h, i: valor)
    monkeypatch.setattr(windows.win32gui, "GetWindowRect", lambda h: janela)
    monkeypatch.setattr(windows.win32api, "MonitorFromWindow", lambda h, f: 1)
    monkeypatch.setattr(windows.win32api, "GetMonitorInfo", lambda m: {"Monitor": (0, 0, 1920, 1080)})
    monkeypatch.setattr(windows.ctypes, "windll", SimpleNamespace(user32=SimpleNamespace(IsZoomed=lambda h: zoom)))
    assert windows.tela_cheia() is esperado


# ----- vários monitores -----

TELAS = [(0, 0, 1280, 720, 1.5), (1920, 0, 1920, 1080, 1.0), (-1920, 100, 960, 540, 2.0)]


def test_cada_ponto_fisico_cai_na_tela_certa_com_escala_propria():
    assert senses.tela_nativa(1919, 500, TELAS) is TELAS[0]        # 1280 lógicos * 1,5
    assert senses.tela_nativa(1920, 500, TELAS) is TELAS[1]
    assert senses.tela_nativa(-1000, 500, TELAS) is TELAS[2]
    assert senses.tela_nativa(9000, 0, TELAS) is None
    assert senses.nativo_para_logico(300, 150, TELAS[0]) == (200, 100)
    assert senses.nativo_para_logico(2020, 50, TELAS[1]) == (2020, 50)
    assert senses.nativo_para_logico(-1720, 300, TELAS[2]) == (-1820, 200)


def test_pousa_em_janela_de_qualquer_monitor(pet, monkeypatch):
    monkeypatch.setattr(pet, "_telas", lambda: TELAS)
    monkeypatch.setattr(senses, "list_windows", lambda excluir, escala=1.0: [
        (1, (300, 150, 900, 600), False),        # principal, com escala 1,5
        (2, (2020, 200, 2820, 800), False),      # à direita, sem escala
        (3, (-1800, 400, -1000, 900), False),    # à esquerda, com escala 2
        (4, (2100, 20, 2800, 500), False),       # colada no topo: não dá para pousar
        (5, (5000, 300, 5800, 900), False),      # fora de todos os monitores
    ])
    monkeypatch.setattr(pet.pet, "isVisible", lambda: True)
    pet.scan_windows()
    assert pet.platforms == [(1, 210, 590, 100), (2, 2030, 2810, 200), (3, -1850, -1470, 250)]


# ----- pasta de dados -----

def test_executavel_grava_em_localappdata_sem_memoria_ao_lado(tmp_path):
    local = {"LOCALAPPDATA": str(tmp_path / "local")}
    assert pasta_de_dados(tmp_path, True, "win32", local) == tmp_path / "local" / "Pestinha"
    (tmp_path / "memory").mkdir()                                   # quem já usa o .exe não perde a memória
    assert pasta_de_dados(tmp_path, True, "win32", local) == tmp_path / "memory"


def test_codigo_fonte_e_outros_sistemas_continuam_em_memory(tmp_path):
    local = {"LOCALAPPDATA": str(tmp_path / "local")}
    assert pasta_de_dados(tmp_path, False, "win32", local) == tmp_path / "memory"
    assert pasta_de_dados(tmp_path, True, "linux", local) == tmp_path / "memory"
    assert Paths(root=tmp_path).memory == tmp_path / "memory"


def test_pasta_sem_permissao_e_detectada(tmp_path):
    assert store.pasta_gravavel(tmp_path / "nova") is True
    arquivo = tmp_path / "arquivo"
    arquivo.write_text("x", encoding="utf-8")
    assert store.pasta_gravavel(arquivo / "dentro") is False


# ----- abertura -----

def _args(direto=False, configurar=False):
    return SimpleNamespace(direto=direto, configurar=configurar)


def test_tela_de_permissoes_so_aparece_quando_precisa():
    pronto = dict(config.DEFAULT_PERMISSIONS, configurado=True)
    assert main_mod.deve_mostrar_tela(_args(), pronto, False) is False
    assert main_mod.deve_mostrar_tela(_args(configurar=True), pronto, False) is True
    assert main_mod.deve_mostrar_tela(_args(), dict(pronto, configurado=False), False) is True    # saiu sem Começar
    assert main_mod.deve_mostrar_tela(_args(), dict(pronto, ativo=False), False) is True          # para religar
    assert main_mod.deve_mostrar_tela(_args(direto=True), dict(pronto, ativo=False), False) is False
    assert main_mod.deve_mostrar_tela(_args(direto=True), pronto, True) is True                   # sem consentimento


def test_rotina_vem_desligada():
    assert config.DEFAULT_PERMISSIONS["rotina"] is False


def test_segunda_copia_nao_abre(tmp_path):
    QApplication.instance() or QApplication([])
    paths = Paths(root=tmp_path)
    primeira = main_mod.travar_instancia(paths)
    assert primeira is not None
    assert main_mod.travar_instancia(paths) is None
    assert main_mod.travar_instancia(Paths(root=tmp_path / "outra")) is not None
    primeira.unlock()
    assert main_mod.travar_instancia(paths) is not None


# ----- início automático -----

@so_windows
def test_inicio_com_windows_liga_e_desliga(monkeypatch):
    registro = {}

    class Chave:
        def __enter__(self):
            return self

        def __exit__(self, *erro):
            return False

    def consultar(_chave, nome):
        if nome not in registro:
            raise FileNotFoundError(nome)
        return registro[nome], 1

    def apagar(_chave, nome):
        if nome not in registro:
            raise FileNotFoundError(nome)
        del registro[nome]

    monkeypatch.setattr(windows, "winreg", SimpleNamespace(
        HKEY_CURRENT_USER=0, REG_SZ=1, OpenKey=lambda *a: Chave(), CreateKey=lambda *a: Chave(),
        QueryValueEx=consultar, DeleteValue=apagar,
        SetValueEx=lambda _c, nome, _r, _t, valor: registro.__setitem__(nome, valor),
    ))
    assert windows.inicia_com_sistema() is False
    assert windows.definir_inicio_com_sistema(True) is True
    assert windows.inicia_com_sistema() is True
    assert registro[windows.VALOR_INICIO].endswith("--direto")
    registro[windows.VALOR_INICIO] = '"C:\\pasta antiga\\Pestinha.exe" --direto'
    assert windows.inicia_com_sistema() is False                    # o programa mudou de lugar
    assert windows.definir_inicio_com_sistema(False) is True
    assert windows.definir_inicio_com_sistema(False) is True        # já desligado não é erro


# ----- programas -----

def test_programas_extras_somam_aos_conhecidos(tmp_path):
    paths = Paths(root=tmp_path)
    paths.comum.mkdir(parents=True)
    paths.programas.write_text(
        '{"GAMING": ["MeuJogo.EXE", 7], "INVENTADA": ["x"], "MUSIC": "nao-e-lista"}', encoding="utf-8")
    try:
        senses.definir_programas(config.load_programas(paths))
        assert senses.detect_activity("meujogo.exe", 0.0, 60.0) == "GAMING"
        assert senses.detect_activity("x.exe", 0.0, 60.0) == "IDLE"
        assert senses.detect_activity("cursor.exe", 0.0, 60.0) == "PROGRAMMING"
    finally:
        senses.definir_programas({})


def test_arquivo_de_programas_que_acompanha_o_projeto_e_valido():
    assert config.load_programas(Paths(root=ROOT)) == {k: [] for k in senses.ACTIVITY_APPS}


# ----- fechar, apagar e retomar -----

def test_erro_ao_salvar_nao_impede_as_outras_partes_nem_de_fechar(pet, monkeypatch):
    fechou, salvou = [], []

    def falha():
        raise ValueError("NaN")

    monkeypatch.setattr(QApplication, "quit", lambda *a: fechou.append(True))
    monkeypatch.setattr(pet.memory, "save", falha)
    monkeypatch.setattr(pet.conditioning, "save", lambda: salvou.append(True))
    pet.quit()
    assert salvou and fechou


def test_falha_ao_apagar_avisa_mesmo_sem_terminal(pet, monkeypatch):
    avisos = []
    monkeypatch.setattr(pet, "quit", lambda: None)
    monkeypatch.setattr(store, "apagar_pasta", lambda pasta: ["memory/preso.json"])
    monkeypatch.setattr(QMessageBox, "warning", lambda *a: avisos.append(a[-1]))
    pet.paths.memory.mkdir(parents=True, exist_ok=True)
    pet.wipe_all_data()
    assert len(avisos) == 1 and "memory/preso.json" in avisos[0]


def test_tempo_desligado_pelo_panico_nao_vence_os_prazos(pet, monkeypatch):
    deslocado = []
    monkeypatch.setattr(pet.memory, "deslocar", deslocado.append)
    pet.panic()
    assert deslocado == []
    pet.apply_perms(dict(pet.perms, ativo=True))
    assert len(deslocado) == 1 and deslocado[0] >= 0
    pet.apply_perms(dict(pet.perms, fogos=False))
    assert len(deslocado) == 1


def test_pausa_durante_o_panico_so_retoma_quando_os_dois_acabam(pet, monkeypatch):
    deslocado = []
    monkeypatch.setattr(pet.memory, "deslocar", deslocado.append)
    pet.panic()
    pet.toggle_pause()
    pet.apply_perms(dict(pet.perms, ativo=True))
    assert deslocado == []
    pet.toggle_pause()
    assert len(deslocado) == 1


def test_erro_nao_tratado_vai_para_o_log(tmp_path, monkeypatch):
    registro = tmp_path / "erros.log"
    monkeypatch.setattr(sys, "excepthook", lambda *a: None)
    log_module.setup(registro)
    try:
        log_module.capturar_erros()
        log_module.capturar_erros()                     # não empilha
        try:
            raise RuntimeError("falha de teste")
        except RuntimeError:
            sys.excepthook(*sys.exc_info())
        assert registro.read_text(encoding="utf-8").count("RuntimeError: falha de teste") == 1
    finally:
        log_module.desligar_arquivo()
