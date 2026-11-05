"""
O cartão de música mostra o tempo: a borda acende do meio de cima e dá a volta (sentido horário) até o fim
da música, o número '1:23 / 3:45' acompanha e um disquinho gira no canto, com a capa da música como selo
(que dá para tirar pelo 🖼).
"""
import sys
import time
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402
from PySide6.QtCore import QBuffer, QIODevice, QRectF  # noqa: E402
from PySide6.QtGui import QColor, QImage  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from pestinha.ia import musica  # noqa: E402
from pestinha.ia.musica import Faixa  # noqa: E402
from pestinha.world import tocando as mod  # noqa: E402
from pestinha.world.tocando import Tocando, contorno, tempo, trecho  # noqa: E402

QApplication.instance() or QApplication([])

FAIXA = Faixa("v1", "Chuva", ("Kupla",), 200, capa="https://lh3.googleusercontent.com/x=w240-h240")


def png(cor="#f6a400"):
    img = QImage(30, 30, QImage.Format_ARGB32)
    img.fill(QColor(cor))
    buf = QBuffer()
    buf.open(QIODevice.WriteOnly)
    img.save(buf, "PNG")
    return bytes(buf.data())


class Ctl(SimpleNamespace):
    """Um controle de música de mentira: diz o tempo que quisermos."""

    def progresso(self):
        return self.pos, self.dur


def ctl(**campos):
    base = dict(atual=FAIXA, carregando=False, pausada=False, estilo="lo-fi", opiniao=None, volume=0.5,
                capa=None, pos=50.0, dur=200.0)
    base.update(campos)
    return Ctl(**base)


# ---------------- borda ----------------

def test_contorno_comeca_no_meio_de_cima_e_vai_no_sentido_horario():
    caixa = QRectF(0, 0, 200, 100)
    c = contorno(caixa)
    inicio = c.pointAtPercent(0.0)
    assert abs(inicio.x() - 100) < 0.5 and abs(inicio.y()) < 0.5
    quarto = c.pointAtPercent(0.25)
    assert quarto.x() > 190                                              # foi para a direita primeiro
    meio = c.pointAtPercent(0.5)
    assert meio.y() > 95                                                 # metade: embaixo
    fim = c.pointAtPercent(1.0)
    assert abs(fim.x() - 100) < 0.5 and abs(fim.y()) < 0.5               # fecha a volta no mesmo ponto


def test_trecho_vai_do_inicio_ate_a_fracao_e_emenda_na_volta():
    c = contorno(QRectF(0, 0, 200, 100))
    assert trecho(c, 0.3, 0.3) == []
    pontos = trecho(c, 0.0, 0.5)
    assert pontos[0] == c.pointAtPercent(0.0) and pontos[-1] == c.pointAtPercent(0.5)
    volta = trecho(c, 0.95, 1.05)                                        # pedaço que cruza o começo
    assert abs(volta[-1].x() - c.pointAtPercent(0.05).x()) < 0.5


def test_tempo_formatado():
    assert tempo(83) == "1:23" and tempo(0) == "0:00" and tempo(-3) == "0:00"


# ---------------- cartão ----------------

def test_fracao_e_numero_acompanham_a_musica():
    t = Tocando()
    t.atualizar(ctl(pos=50.0, dur=200.0))
    assert t.fracao == pytest.approx(0.25) and t.tempo.text() == "0:50 / 3:20"
    t._ctl.pos = 200.0
    t._passo_do_tempo(time.monotonic())
    assert t.fracao == 1.0                                               # fechou a volta
    t.atualizar(ctl(atual=None, dur=0.0, pos=0.0))
    assert t.fracao == 0.0 and t.tempo.text() == ""


def test_disco_gira_tocando_e_freia_suave_na_pausa():
    t = Tocando()
    c = ctl()
    t.atualizar(c)
    for i in range(60):
        t._passo_do_tempo(100.0 + i * 0.016)
    assert t.giro > mod.GIRO * 0.95                                      # pegou velocidade
    c.pausada = True
    t._passo_do_tempo(100.0 + 60 * 0.016)
    t._passo_do_tempo(100.0 + 61 * 0.016)
    assert 0.0 < t.giro < mod.GIRO                                       # freando, ainda não parou
    for i in range(120):
        t._passo_do_tempo(101.0 + i * 0.016)
    assert t.giro == 0.0
    angulo = t.angulo
    t._passo_do_tempo(103.5)
    assert t.angulo == angulo                                            # parado não gira


def test_capa_vira_selo_e_da_para_tirar(tmp_path):
    arquivo = tmp_path / "panels.json"
    t = Tocando(arquivo)
    assert t.com_capa and t.botoes["capa"].isChecked()
    t.atualizar(ctl(capa=png()))
    assert t.capa is not None and t.capa.width() == 30
    com = QImage(t.size(), QImage.Format_ARGB32)
    com.fill(0)
    t.render(com)
    t.botoes["capa"].click()                                             # 🖼: tira a capa
    assert not t.com_capa and not t.botoes["capa"].isChecked()
    sem = QImage(t.size(), QImage.Format_ARGB32)
    sem.fill(0)
    t.render(sem)
    assert com != sem
    assert Tocando(arquivo).com_capa is False                            # lembra na próxima vez
    t.botoes["capa"].click()
    assert Tocando(arquivo).com_capa is True


def test_capa_quebrada_fica_sem_selo():
    t = Tocando()
    t.atualizar(ctl(capa=b"nao e imagem"))
    assert t.capa is None


# ---------------- ia/musica e o controle ----------------

def test_faixa_traz_a_maior_capa_e_pede_maior():
    f = musica.faixa_de({"videoId": "x", "title": "T", "length": "2:18", "thumbnails": [
        {"url": "https://lh3.googleusercontent.com/a=w60-h60-l90-rj", "width": 60},
        {"url": "https://lh3.googleusercontent.com/a=w120-h120-l90-rj", "width": 120}]})
    assert f.capa == f"https://lh3.googleusercontent.com/a=w{musica.CAPA_PX}-h{musica.CAPA_PX}-l90-rj"
    r = musica.faixa_de({"videoId": "y", "title": "R", "length": "2:00",
                         "thumbnail": [{"url": "https://i.ytimg.com/vi/y/sddefault.jpg", "width": 640}]})
    assert r.capa == "https://i.ytimg.com/vi/y/sddefault.jpg"
    assert Faixa("x", "T", (), 138) == Faixa("x", "T", (), 138, capa="outra")   # capa não muda a música
    assert musica.link_da_capa(Faixa("z", "Z")) == "https://i.ytimg.com/vi/z/hqdefault.jpg"


@pytest.fixture
def ctl_real(tmp_path):
    from pestinha.mind.musica_ctl import MusicaController
    app = SimpleNamespace(paths=SimpleNamespace(memory=tmp_path), pet_state=SimpleNamespace(emotion="feliz"))
    return MusicaController(app, None, tmp_path)


def test_capa_chega_e_falha_de_capa_nao_pula_a_musica(ctl_real):
    c = ctl_real
    c.estilo, c.atual, c.geracao = "", FAIXA, 3
    pulou = []
    c._proxima = lambda: pulou.append(1)
    c._ao_pronto("capa", musica.ErroMusica("sem capa"), 3)
    assert c.capa is None and pulou == [] and c.falhas == 0
    c._ao_pronto("capa", b"PNG", 3)
    assert c.capa == b"PNG"
    c._ao_pronto("capa", b"VELHA", 2)                                    # de outra música: descarta
    assert c.capa == b"PNG"


def test_progresso_sem_player_usa_a_duracao_da_faixa(ctl_real):
    c = ctl_real
    assert c.progresso() == (0.0, 0.0)
    c.atual = FAIXA
    assert c.progresso() == (0.0, 200.0)
