"""
Chamar pelo nome ("Bob!"): as grafias que o modelo ouve, a leitura do resultado do Vosk, o recorte do
pedido, a escuta depois do nome, o download do modelo (de um zip local) e o controlador dentro do app de
verdade (Qt offscreen, detector e serviço de voz falsos). Nenhum teste abre o microfone de verdade.
"""

import io
import json
import os
import queue
import sys
import threading
import time
import zipfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
import pytest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from pestinha import config  # noqa: E402
from pestinha.app import PestinhaApp  # noqa: E402
from pestinha.ia import chamado  # noqa: E402
from pestinha.ia.provedores import ErroIA  # noqa: E402
from pestinha.paths import Paths  # noqa: E402
from pestinha.settings_store import SettingsStore  # noqa: E402

TAXA = 16000


def fala(segundos, alto=True):
    """PCM 16 bits: um tom (alguém falando) ou silêncio."""
    n = int(segundos * TAXA)
    if not alto:
        return np.zeros(n, dtype="<i2").tobytes()
    return (np.sin(np.arange(n) / 4.0) * 6000).astype("<i2").tobytes()


# ---------------- texto e áudio ----------------

def test_grafias_do_nome():
    assert chamado.grafias("Bob") == ["bob", "bobi", "bóbi", "bobe", "bóbe"]
    assert chamado.grafias("Jorge") == ["jorge"]
    assert chamado.grafias("") == [] and chamado.grafias("dois nomes") == ["dois nomes"]


def resultado(*palavras):
    return json.dumps({"result": [{"word": w, "conf": c, "start": s, "end": e} for w, c, s, e in palavras]})


def test_resultado_com_o_nome_e_o_pedido_junto():
    d = chamado.ler_resultado(resultado(("bóbi", 0.9, 1.0, 1.4), ("[unk]", 0.5, 1.6, 2.5)), ["bóbi"])
    assert (d.inicio, d.fim, d.fim_frase) == (1.0, 1.4, 2.5) and d.com_pedido()
    sozinho = chamado.ler_resultado(resultado(("bóbi", 0.9, 1.0, 1.4)), ["bóbi"])
    assert not sozinho.com_pedido()


@pytest.mark.parametrize("texto", [resultado(("bola", 0.99, 0, 1)), resultado(("bóbi", 0.3, 0, 1)), "",
                                   "{quebrado", '{"result": "x"}', '["lista"]', '{"text": "bob"}'])
def test_resultado_sem_o_nome(texto):
    assert chamado.ler_resultado(texto, ["bóbi"]) is None


class ReconhecedorFalso:
    """No lugar do KaldiRecognizer: devolve um resultado quando já recebeu `quando` s de áudio."""

    def __init__(self, resultados):
        self.resultados = list(resultados)      # [(segundos, json)]
        self.recebido = 0.0
        self._pronto = None

    def AcceptWaveform(self, pcm):
        self.recebido += len(pcm) / 2 / TAXA
        if self.resultados and self.recebido >= self.resultados[0][0]:
            self._pronto = self.resultados.pop(0)[1]
            return True
        return False

    def Result(self):
        return self._pronto


def test_detector_recorta_o_pedido_e_guarda_so_o_fim():
    rec = ReconhecedorFalso([(3.0, resultado(("bob", 0.95, 1.0, 1.4), ("[unk]", 0.6, 1.5, 2.6)))])
    d = chamado.Detector(None, "bob", TAXA, reconhecedor=rec)
    achou = None
    for _ in range(30):
        achou = d.alimentar(fala(0.1)) or achou
    assert achou and achou.com_pedido()
    assert len(d.recortar(achou.inicio - chamado.ANTES, achou.fim_frase)) == int((2.6 - 0.75) * TAXA) * 2
    for _ in range(int(chamado.GUARDA * 10) + 20):           # muito tempo depois: o começo saiu da guarda
        d.alimentar(fala(0.1, alto=False))
    assert d.recortar(0, 2.6) == b""


def test_detector_sem_grafia_conhecida_avisa():
    class Modelo:
        def vosk_model_find_word(self, palavra):
            return -1
    with pytest.raises(ErroIA, match="não conhece"):
        chamado.Detector(Modelo(), "xpto", TAXA)


def test_escuta_termina_no_silencio_ou_desiste():
    e = chamado.Escuta(TAXA, comeco=fala(0.3))
    assert e.alimentar(fala(0.5)) is None
    fins = [e.alimentar(fala(0.1, alto=False)) for _ in range(12)]
    assert "fim" in fins and len(e.audio()) > len(fala(0.8))
    calado = chamado.Escuta(TAXA)
    passos = [calado.alimentar(fala(0.5, alto=False)) for _ in range(12)]
    assert passos[-1] == "desistiu" or "desistiu" in passos


def test_escuta_corta_pedido_longo():
    e = chamado.Escuta(TAXA)
    assert "fim" in [e.alimentar(fala(1.0)) for _ in range(int(chamado.MAX_PEDIDO) + 1)]


# ---------------- modelo ----------------

def _zip(arquivos):
    dados = io.BytesIO()
    with zipfile.ZipFile(dados, "w") as z:
        for nome, conteudo in arquivos.items():
            z.writestr(nome, conteudo)
    return dados.getvalue()


def test_baixa_o_modelo_uma_vez(tmp_path):
    origem = tmp_path / "modelo.zip"
    origem.write_bytes(_zip({f"{chamado.MODELO}/final.mdl": "m", f"{chamado.MODELO}/HCLr.fst": "h"}))
    pasta = tmp_path / "modelos"
    assert not chamado.modelo_baixado(pasta)
    chamado.baixar_modelo(pasta, url=origem.as_uri())
    assert chamado.modelo_baixado(pasta) and sorted(p.name for p in pasta.iterdir()) == [chamado.MODELO]
    origem.unlink()                                          # já baixado: nem tenta de novo
    assert chamado.baixar_modelo(pasta, url=origem.as_uri()) == chamado.pasta_do_modelo(pasta)


@pytest.mark.parametrize("arquivos", [{"../fora.txt": "x"}, {"outra/final.mdl": "x"}])
def test_modelo_estranho_e_recusado(tmp_path, arquivos):
    origem = tmp_path / "modelo.zip"
    origem.write_bytes(_zip(arquivos))
    with pytest.raises(ErroIA):
        chamado.baixar_modelo(tmp_path / "modelos", url=origem.as_uri())
    assert not (tmp_path / "fora.txt").exists() and not chamado.modelo_baixado(tmp_path / "modelos")


def test_sem_internet_avisa(tmp_path):
    with pytest.raises(ErroIA, match="baixar"):
        chamado.baixar_modelo(tmp_path, url=(tmp_path / "nao_existe.zip").as_uri())


# ---------------- no app de verdade ----------------

@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    return app


def esperar(qapp, condicao, segundos=3.0):
    fim = time.monotonic() + segundos
    while time.monotonic() < fim:
        qapp.processEvents()
        if condicao():
            return True
        time.sleep(0.01)
    return False


class VozFalsa:
    def __init__(self):
        self.wavs = []

    def transcrever(self, wav, dica=""):
        self.wavs.append(wav)
        return "que horas são"


@pytest.fixture
def pet(qapp, tmp_path, monkeypatch):
    from pestinha.sense import senses
    monkeypatch.setattr(senses, "is_fullscreen", lambda: False)
    paths = Paths(root=tmp_path)
    store = SettingsStore(paths)
    store.update(dict(config.DEFAULT_PERMISSIONS, ia=True, conversa=True, voz=True, modo_teste=True))
    app = PestinhaApp(store, paths)
    abriu = []
    monkeypatch.setattr(app.chamado, "comecar", lambda: (abriu.append(1), setattr(app.chamado, "ouvindo", True)))
    app.apply_perms({"chamar": True})                         # sem abrir o microfone de verdade
    app.chamado.abriu = abriu
    voz = VozFalsa()
    monkeypatch.setattr(app.voz, "cliente", lambda: voz)
    ouvidos = []
    monkeypatch.setattr(app, "_ouvi", ouvidos.append)
    app.voz.ouvido.disconnect()
    app.voz.ouvido.connect(ouvidos.append)
    app.pet.show()
    yield app, voz, ouvidos
    app.chamado.parar()
    app.voz.cancelar()
    app.balao.esconder()
    app.tray.icon.hide()


def rodar_laco(app, rec, pedacos):
    """O laço da thread do chamado com um detector falso, até a fila esvaziar."""
    c = app.chamado
    c.geracao += 1
    geracao = c.geracao
    fila = queue.Queue()
    for p in pedacos:
        fila.put(p)
    detector = chamado.Detector(None, "bob", TAXA, reconhecedor=rec)
    t = threading.Thread(target=c._ouvir, args=(detector, fila, geracao, TAXA, c._evento.emit), daemon=True)
    t.start()
    return fila, t


def test_bob_com_pedido_vai_para_a_voz_e_vira_mensagem(qapp, pet):
    app, voz, ouvidos = pet
    rec = ReconhecedorFalso([(2.0, resultado(("bob", 0.95, 0.5, 0.9), ("[unk]", 0.7, 1.0, 1.8)))])
    rodar_laco(app, rec, [fala(0.1)] * 25)
    assert esperar(qapp, lambda: ouvidos == ["que horas são"])
    assert voz.wavs and voz.wavs[0][:4] == b"RIFF"
    app.chamado.geracao += 1


def test_so_o_nome_levanta_a_orelha_e_espera_o_pedido(qapp, pet):
    app, voz, ouvidos = pet
    chamou = []

    def ao_chamar():
        app._atualizar_mente(time.monotonic())
        chamou.append("ouvindo" in app.pet_state.mente)
    app.chamado.chamou.connect(ao_chamar)
    rec = ReconhecedorFalso([(1.0, resultado(("bob", 0.95, 0.4, 0.8)))])
    pedacos = [fala(0.1)] * 10 + [fala(0.1)] * 8 + [fala(0.1, alto=False)] * 14
    rodar_laco(app, rec, pedacos)
    assert esperar(qapp, lambda: chamou) and chamou == [True]        # a orelha vai para a frente
    assert esperar(qapp, lambda: ouvidos == ["que horas são"])
    assert not app.chamado.escutando
    app.chamado.geracao += 1


def test_assistindo_video_nao_atende(qapp, pet):
    app, voz, ouvidos = pet
    app.chamado._surdo = True
    rec = ReconhecedorFalso([(1.0, resultado(("bob", 0.95, 0.4, 0.8), ("[unk]", 0.7, 0.9, 1.6)))])
    _fila, t = rodar_laco(app, rec, [fala(0.1)] * 15)
    time.sleep(0.3)
    qapp.processEvents()
    assert ouvidos == [] and voz.wavs == []
    app.chamado.geracao += 1
    t.join(1.0)


def test_surdo_quando_o_video_ou_a_voz_estao_ocupados(qapp, pet):
    app, _voz, _ouvidos = pet
    app.chamado.atualizar()
    assert not app.chamado._surdo
    app.voz.transcrevendo = True
    app.chamado.atualizar()
    assert app.chamado._surdo
    app.voz.transcrevendo = False
    app.video.ativo = True
    app.chamado.atualizar()
    assert app.chamado._surdo
    app.video.ativo = False


def test_so_abre_o_microfone_com_a_permissao(qapp, pet):
    app, _voz, _ouvidos = pet
    abriu = app.chamado.abriu
    assert abriu == [1] and app.chamado.palavra_de_chamado() == app.nome.lower()
    app.apply_perms({"chamar": False})
    assert not app.chamado.ouvindo                               # desligou: fecha
    app.apply_perms({"chamar": True})
    assert abriu == [1, 1]
    app.toggle_pause()
    assert not app.chamado.ouvindo                               # pausado: fecha
    app.toggle_pause()
    assert app.chamado.ouvindo
    app.apply_perms({"chamado_palavra": "pestinha"})
    assert app.chamado.palavra_de_chamado() == "pestinha" and len(abriu) == 4
    app.panic()
    assert not app.chamado.ouvindo


def test_erro_do_modelo_avisa_e_fecha(qapp, pet):
    app, _voz, _ouvidos = pet
    avisos = []
    app.chamado.aviso.connect(avisos.append)
    app.chamado.ouvindo = True
    app.chamado._evento.emit("erro", "o modelo de voz não abriu", app.chamado.geracao)
    assert esperar(qapp, lambda: avisos) and not app.chamado.ouvindo


def test_o_pet_agora_se_chama_bob():
    definicao = json.loads((ROOT / "pets" / "bryan.json").read_text(encoding="utf-8"))
    assert definicao["nome"] == "Bob" and definicao["persona"].startswith("Você é o Bob")
