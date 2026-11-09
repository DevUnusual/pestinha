"""
Política de fala (mind/politica.py): o modelo sempre propõe uma fala, e quem decide se ela aparece é o
app, pelo tom da rede, pelos sinais da olhada, pelo intervalo e pelo teto por hora. Também a espera pela
reação da rede dentro do app de verdade, que pânico e pausa cancelam.
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

from pestinha import ajustes, config  # noqa: E402
from pestinha.ia import mente  # noqa: E402
from pestinha.mind.politica import PoliticaFala  # noqa: E402
from pestinha.paths import Paths  # noqa: E402
from pestinha.settings_store import SettingsStore  # noqa: E402

NEUTRA = {"VISAO_ERRO": 0.0, "VISAO_FOCO": 0.82, "VISAO_NOVO": 0.07, "VISAO_GRACA": 0.0}
ERRO = {"VISAO_ERRO": 1.0, "VISAO_FOCO": 0.8, "VISAO_NOVO": 0.2}


def test_erro_fala_e_tela_neutra_fica_quieta():
    p = PoliticaFala()
    assert p.decidir(0, "Divisão por zero ali.", ERRO, {"WATCH": 0.5}).falar
    neutra = p.decidir(0, "Usar pathlib deixaria mais limpo.", NEUTRA, {"WATCH": 0.6})
    assert not neutra.falar and "concentrado" in neutra.motivo


def test_graca_e_novidade_precisam_da_rede_concordar():
    p = PoliticaFala()
    graca = {"VISAO_GRACA": 0.9, "VISAO_FOCO": 0.2}
    assert p.decidir(0, "Hahaha!", graca, {"CHEER": 0.8}).falar
    assert not p.decidir(0, "Hahaha!", graca, {"CHEER": 0.05}).falar          # a rede não achou graça
    novo = {"VISAO_NOVO": 0.8, "VISAO_FOCO": 0.3}
    assert p.decidir(0, "Que projeto é esse?", novo, {"WATCH": 0.2}).falar
    assert not p.decidir(0, "Que projeto é esse?", novo, {"WATCH": 0.0}).falar


def test_sem_candidata_nao_fala_e_pedido_sempre_fala():
    p = PoliticaFala()
    assert not p.decidir(0, "", ERRO, {}).falar
    assert p.decidir(0, "Você está programando.", NEUTRA, {}, pedido=True).falar


def test_intervalo_minimo_e_teto_por_hora():
    p = PoliticaFala()
    t = 0.0
    assert p.decidir(t, "a", ERRO, {}).falar
    p.falou(t)
    assert not p.decidir(t + ajustes.FALA_INTERVALO_MIN - 1, "b", ERRO, {}).falar
    for _ in range(ajustes.FALA_MAX_POR_HORA - 1):
        t += ajustes.FALA_INTERVALO_MIN + 1
        assert p.decidir(t, "c", ERRO, {}).falar
        p.falou(t)
    t += ajustes.FALA_INTERVALO_MIN + 1
    teto = p.decidir(t, "d", ERRO, {})
    assert not teto.falar and "bastante" in teto.motivo
    assert p.decidir(t + 3600, "e", ERRO, {}).falar                            # uma hora depois, volta


def test_em_jogo_vale_o_intervalo_do_perfil():
    p = PoliticaFala()
    assert p.decidir(0, "Que pulo!", NEUTRA, {}, intervalo=12.0, jogo=True).falar
    p.falou(0)
    assert not p.decidir(5, "De novo!", NEUTRA, {}, intervalo=12.0, jogo=True).falar
    assert p.decidir(13, "De novo!", NEUTRA, {}, intervalo=12.0, jogo=True).falar


def test_o_pedido_da_olhada_pede_sempre_uma_fala():
    pedido = mente.pedido_observacao("code", "x.py", "PROGRAMMING", "curioso")
    assert "Escreva sempre o comentario" in pedido and "fique quieto (comentario vazio) na" not in pedido


# ---------------- no app de verdade ----------------

@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    return app


def esperar(qapp, condicao, segundos=2.0):
    fim = time.monotonic() + segundos
    while time.monotonic() < fim:
        qapp.processEvents()
        if condicao():
            return True
        time.sleep(0.01)
    return False


@pytest.fixture
def pet(qapp, tmp_path, monkeypatch):
    from pestinha.app import PestinhaApp
    paths = Paths(root=tmp_path)
    store = SettingsStore(paths)
    store.update(dict(config.DEFAULT_PERMISSIONS, ia=True, ver_tela=True, modo_teste=True))
    app = PestinhaApp(store, paths)
    monkeypatch.setattr(ajustes, "FALA_ESPERA_REDE", 0.2)
    falas = []
    app.visao.fala.connect(falas.append)
    yield app, falas
    app.visao.cancelar()
    app.tray.icon.hide()


def obs(comentario, **sinais):
    return mente.Observacao(resumo="programando", comentario=comentario, sinais=sinais)


def test_a_fala_espera_a_rede_e_depois_a_politica_decide(qapp, pet):
    app, falas = pet
    app.visao._entender(obs("Divisão por zero ali.", VISAO_ERRO=1.0, VISAO_FOCO=0.8))
    assert falas == []                                                           # ainda esperando a rede
    assert esperar(qapp, lambda: falas == ["Divisão por zero ali."])
    app.visao.politica.falas.clear()
    app.visao._entender(obs("Usar pathlib aqui.", **NEUTRA))
    assert not esperar(qapp, lambda: len(falas) > 1, segundos=0.6)               # tela neutra: quieto


@pytest.mark.parametrize("parar", ["pausa", "panico"])
def test_pausa_e_panico_cancelam_a_fala_que_esperava(qapp, pet, parar):
    app, falas = pet
    app.visao._entender(obs("Divisão por zero ali.", VISAO_ERRO=1.0))
    app.toggle_pause() if parar == "pausa" else app.panic()
    assert not esperar(qapp, lambda: falas, segundos=0.6)
