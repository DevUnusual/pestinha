"""
Música pelo chat: "toca um lo-fi" monta a fila no YouTube Music, 👍/👎/pulo/ouvir até o fim ensinam o
gosto e a fila se renova pelo rádio. Sem rede nem som: o YouTube e o player são simulados.
"""
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from pestinha import config  # noqa: E402
from pestinha.app import PestinhaApp  # noqa: E402
from pestinha.ia import musica  # noqa: E402
from pestinha.ia.musica import Faixa, Gosto  # noqa: E402
from pestinha.paths import Paths  # noqa: E402
from pestinha.settings_store import SettingsStore  # noqa: E402

QApplication.instance() or QApplication([])


# ---------------- o que você disse ----------------

@pytest.mark.parametrize("texto, estilo", [
    ("toca um lo-fi pra mim", "lo-fi"),
    ("Pestinha, toca um rock anos 80", "rock anos 80"),
    ("quero ouvir música de samba", "samba"),
    ("coloca uma playlist de jazz por favor", "jazz"),
    ("bota um som de forró aí", "forro"),
    ("toca algo animado", "animado"),
    ("toca música", ""),
    # pela voz: frase inteira, com nome, vírgula e ponto de interrogação
    ("pode tocar um rock?", "rock"),
    ("Bryan, você pode tocar um lo-fi?", "lo-fi"),
    ("Você poderia tocar uma música pra mim?", ""),
    ("Ei Bryan, por favor, toca um forró aí.", "forro"),
    ("Que tal tocar um samba?", "samba"),
    ("bota uma musica ai", ""),
    ("coloca uma música de rock pra tocar", "rock"),
    ("reproduz um jazz", "jazz"),
    # do jeito que se fala em casa: sem estilo, ele escolhe
    ("Coloca uma musiquinha aí pra nós ouvir.", ""),
    ("bota um som aí pra gente curtir", ""),
    ("solta um sonzinho", ""),
    ("manda uma música boa aí", ""),
    ("toca o que você quiser", ""),
    ("coloca uma música que você ache legal", ""),
    ("toca uma música pra relaxar", "musica pra relaxar"),
    ("toca um rock pra nós", "rock"),
    ("coloca o som mais alto", None),
    ("quem toca essa música?", None),
    ("que música toca no jogo", None),
    ("o celular toca", None),
    ("não toca isso de novo", None),
    ("você consegue me ouvir?", None),
    ("bota o notebook ali", None),
    ("oi, tudo bem?", None),
])
def test_pedido_de_musica(texto, estilo):
    assert musica.pedido_de_musica(texto) == estilo


@pytest.mark.parametrize("texto, comando", [
    ("pula", "pular"), ("Próxima!", "pular"), ("pestinha, pula essa", "pular"),
    ("Ei Bryan, pula essa música.", "pular"), ("Bryan, não gostei.", "nao_gostei"),
    ("gostei", "gostei"), ("👍", "gostei"), ("não gostei", "nao_gostei"), ("essa não", "nao_gostei"),
    ("pausa", "pausar"), ("continua", "continuar"), ("para a música", "parar"), ("chega", "parar"),
    ("para de olhar minha tela", None), ("gostei muito do que você falou ontem", None), ("oi", None),
])
def test_comando_de_musica(texto, comando):
    assert musica.comando_de_musica(texto) == comando


# ---------------- gosto e escolha ----------------

A = Faixa("a1", "Chuva", ("Kupla",), 140)
B = Faixa("b1", "Noite", ("Zyra",), 150)
C = Faixa("c1", "Café", ("Desconhecido",), 160)


def test_gosto_aprende_e_grava(tmp_path):
    gosto = Gosto(tmp_path / "musica.json")
    gosto.notar(A, "gostei")
    gosto.notar(A, "ouviu")
    gosto.notar(B, "nao_gostei")
    gosto.notar(C, "pulou")
    gosto.salvar()
    lido = Gosto(tmp_path / "musica.json").carregar()
    assert lido.artistas == {"Kupla": 1.25, "Zyra": -1.0, "Desconhecido": -0.4}
    assert lido.curtidas == ["a1"] and lido.banidas == ["b1"]
    assert lido.nota(A) == 2.25                                   # artista bem visto + curtida


def test_gosto_estragado_vira_vazio(tmp_path):
    (tmp_path / "musica.json").write_text("{nada", encoding="utf-8")
    assert Gosto(tmp_path / "musica.json").carregar().artistas == {}


def test_escolher_respeita_banidas_tocadas_e_o_gosto():
    gosto = Gosto()
    gosto.notar(B, "nao_gostei")
    assert musica.escolher([B], gosto) is None                   # banida nunca volta
    assert musica.escolher([A, C], gosto, tocadas=["a1"]) == C    # nada repete na sessão
    gosto.notar(A, "gostei")
    gosto.notar(A, "gostei")
    sorteio = random.Random(1)
    escolhas = [musica.escolher([A, C], gosto, curiosidade=0.0, sorteio=sorteio) for _ in range(200)]
    assert escolhas.count(A) > 170                                # quem você curte toca muito mais
    curiosas = [musica.escolher([A, C], gosto, curiosidade=1.0, sorteio=sorteio) for _ in range(200)]
    assert curiosas.count(C) > escolhas.count(C)                  # curioso, ele arrisca o desconhecido


def test_faixa_de_filtra_compilacoes_e_vinhetas():
    assert musica.faixa_de({"videoId": "x", "title": "3 Hours of Lofi", "duration_seconds": 11017}) is None
    assert musica.faixa_de({"videoId": "x", "title": "Vinheta", "length": "0:20"}) is None
    f = musica.faixa_de({"videoId": "x", "title": "Silver Lining", "length": "2:18",
                         "artists": [{"name": "Kupla"}, {"name": "J'san"}]})
    assert f == Faixa("x", "Silver Lining", ("Kupla", "J'san"), 138)
    assert f.nome() == "Silver Lining · Kupla, J'san"


def test_sem_bibliotecas_explica_o_que_instalar(monkeypatch):
    import builtins
    importar = builtins.__import__
    monkeypatch.setattr(builtins, "__import__", lambda nome, *a, **k: (_ for _ in ()).throw(ImportError(nome))
                        if nome in ("ytmusicapi", "yt_dlp") else importar(nome, *a, **k))
    with pytest.raises(musica.ErroMusica, match="pip install"):
        musica.buscar("lofi")
    with pytest.raises(musica.ErroMusica, match="pip install"):
        musica.baixar_audio("x", ".")


# ---------------- dentro do app ----------------

@pytest.fixture
def app(tmp_path, monkeypatch):
    qapp = QApplication.instance() or QApplication([])
    qapp.setQuitOnLastWindowClosed(False)
    paths = Paths(root=tmp_path)
    store = SettingsStore(paths)
    store.update(dict(config.DEFAULT_PERMISSIONS, ia=True, conversa=True, modo_teste=True))
    a = PestinhaApp(store, paths)
    tocou = []
    monkeypatch.setattr(a.musica, "_tocar", lambda caminho: tocou.append(Path(caminho).stem))
    monkeypatch.setattr(a.musica, "_parar_player", lambda: None)
    monkeypatch.setattr(musica, "buscar", lambda estilo: [A, B, C])
    monkeypatch.setattr(musica, "radio", lambda video_id: [Faixa(f"r{video_id}{i}", f"Rádio {i}", ("Novo",), 150)
                                                         for i in range(6)])
    monkeypatch.setattr(musica, "baixar_audio", lambda video_id, pasta: Path(pasta) / f"{video_id}.m4a")
    a.tocou = tocou
    a.pet.show()
    yield a
    a.musica.parar()
    a.tocando.close()
    a.mischief.clear()
    a.tray.icon.hide()


def esperar(condicao, segundos=3.0):
    qapp = QApplication.instance()
    fim = time.monotonic() + segundos
    while time.monotonic() < fim:
        qapp.processEvents()
        if condicao():
            return True
        time.sleep(0.01)
    return False


def test_toca_pelo_chat_e_aprende_com_os_botoes(app, monkeypatch):
    from PySide6.QtMultimedia import QMediaPlayer
    assert app._musica_pelo_chat("toca um lo-fi") == "Bora de lo-fi! Procurando..."
    assert esperar(lambda: app.tocou)
    primeira = app.musica.atual
    assert app.tocou == [primeira.video_id] and app.musica.tocando()
    app.tocando.atualizar(app.musica)
    assert primeira.titulo in app.tocando.titulo.text()

    app._comando_do_cartao("gostei")                              # 👍 no cartão
    assert primeira.video_id in app.musica.gosto.curtidas and app.tocando.botoes["gostei"].isChecked()
    assert (app.paths.memory / "pets").exists()                   # o gosto foi gravado

    app.musica._ao_status(QMediaPlayer.EndOfMedia)                # acabou sozinha: a próxima começa
    assert esperar(lambda: len(app.tocou) == 2)
    segunda = app.musica.atual
    assert segunda != primeira and app.musica.opiniao is None

    assert app._musica_pelo_chat("não gostei") == "Anotado, essa não toca mais."
    assert segunda.video_id in app.musica.gosto.banidas
    assert esperar(lambda: len(app.tocou) == 3)

    assert app._musica_pelo_chat("pula") == "Próxima!"
    assert esperar(lambda: len(app.tocou) == 4)
    assert len(set(app.tocou)) == 4                               # nada repete
    assert any(f.artista == "Novo" for f in app.musica.fila)      # com pouca música, o rádio trouxe mais
    assert app._musica_pelo_chat("para a música") == "Parei a música."
    assert not app.musica.ativa()
    assert app._musica_pelo_chat("pula") is None                  # sem música, é conversa normal


def test_quando_a_fila_acaba_o_radio_continua(app, monkeypatch):
    monkeypatch.setattr(musica, "buscar", lambda estilo: [A])
    app._musica_pelo_chat("toca um lo-fi")
    assert esperar(lambda: app.tocou)
    for n in range(2, 5):                                          # a busca só deu uma: o resto vem do rádio
        app._musica_pelo_chat("pula")
        assert esperar(lambda: len(app.tocou) == n)
    assert app.musica.atual.artista == "Novo" and app.musica.ativa()


def test_player_solto_fica_parado_e_lembra_onde(tmp_path):
    from PySide6.QtCore import QPoint, QPointF, Qt
    from PySide6.QtGui import QMouseEvent
    from pestinha.world.tocando import Tocando
    arquivo = tmp_path / "panels.json"
    t = Tocando(arquivo)
    limites = (0, 0, 1920, 1080)
    t.seguir(100, 300, limites)
    assert t.pos() == QPoint(100 + 70, 300 - t.height() // 2)            # grudado: ao lado do pet

    def mouse(tipo, x, y):
        botoes = Qt.NoButton if tipo == QMouseEvent.MouseButtonRelease else Qt.LeftButton
        return QMouseEvent(tipo, QPointF(5, 5), QPointF(x, y), Qt.LeftButton, botoes, Qt.NoModifier)

    t.mousePressEvent(mouse(QMouseEvent.MouseButtonPress, 200, 300))
    t.mouseMoveEvent(mouse(QMouseEvent.MouseMove, 250, 200))               # arrastou 50 → e 100 ↑
    t.mouseReleaseEvent(mouse(QMouseEvent.MouseButtonRelease, 250, 200))
    assert t.solto == (220, 200 - t.height() // 2) and t.botoes["fixar"].isChecked()
    t.seguir(600, 700, limites)                                            # o pet andou: o player não
    assert t.pos() == QPoint(*t.solto)

    assert Tocando(arquivo).solto == t.solto                               # lembra na próxima vez
    t.botoes["fixar"].click()                                              # 📌 de novo: gruda no pet
    t.seguir(600, 700, limites)
    assert t.solto is None and t.pos().x() == 670 and Tocando(arquivo).solto is None
    t.close()


def test_limpar_pasta_deixa_so_a_musica_da_vez(tmp_path):
    for nome in ("velha.m4a", "outra.webm", "atual.m4a"):
        (tmp_path / nome).write_bytes(b"x")
    musica.limpar_pasta(tmp_path, manter=[tmp_path / "atual.m4a"])
    assert [p.name for p in tmp_path.iterdir()] == ["atual.m4a"]
    assert musica.tempo(92) == "1:32" and musica.tempo(0) == "0:00"


class PlayerFalso:
    """O bastante do QMediaPlayer para simular um corte no meio da música."""

    def __init__(self, ms):
        self.ms, self.fontes, self.foi_para = ms, [], None

    def position(self):
        return self.ms

    def source(self):
        return self.fontes[-1] if self.fontes else None

    def setSource(self, fonte):
        self.fontes.append(fonte)

    def play(self):
        pass

    def setPosition(self, ms):
        self.foi_para = ms


def test_cortou_no_meio_recomeca_de_onde_parou_e_conta_no_log(app):
    from PySide6.QtCore import QUrl
    from PySide6.QtMultimedia import QMediaPlayer
    from pestinha import log as log_mod
    app._musica_pelo_chat("toca charlie brown")
    assert esperar(lambda: app.tocou)
    atual = app.musica.atual
    player = PlayerFalso(92_000)
    player.fontes.append(QUrl.fromLocalFile(f"C:/x/{atual.video_id}.m4a"))
    app.musica._player = player

    app.musica._ao_erro("Demuxing failed")                         # primeiro corte: recomeça
    assert app.musica.atual == atual and player.source() == QUrl.fromLocalFile(f"C:/x/{atual.video_id}.m4a")
    app.musica._ao_status(QMediaPlayer.LoadedMedia)
    assert player.foi_para == 92_000                               # de 1:32, não do começo
    registro = " ".join(log_mod.recentes())
    assert f"cortou {atual.nome()} em 1:32" in registro and "recomeçando" in registro

    app.musica._ao_erro("Demuxing failed")                         # cortou de novo: desiste dessa
    assert esperar(lambda: len(app.tocou) == 2)
    assert app.musica.atual != atual and "pulando para a próxima" in " ".join(log_mod.recentes())
    app.musica._player = None


def test_sem_estilo_ele_escolhe_pelo_humor(app):
    app.pet_state.emotion = "bravo"
    resposta = app._musica_pelo_chat("Coloca uma musiquinha aí pra nós ouvir")
    assert app.musica.estilo in musica.ESTILOS_DELE["bravo"]
    assert resposta == f"Deixa comigo! Tô no clima de {app.musica.estilo}."
    assert esperar(lambda: app.tocou)


def test_a_ia_da_o_play_quando_so_ela_entendeu(app, monkeypatch):
    from pestinha.ia import mente

    class IA:
        ve_imagem = False

        def responder(self, sistema, mensagens, imagem=None):
            assert "TOCAR:" in sistema                              # ela sabe que pode tocar
            return "Fechou, vou de samba raiz!\nTOCAR: samba raiz"

    monkeypatch.setattr(app.visao, "cliente", lambda: IA())
    falas = []
    app.visao.resposta.connect(falas.append)
    assert app._musica_pelo_chat("Bryan, dá aquela animada no ambiente") is None   # o Pestinha não entendeu...
    assert app.visao.perguntar("Bryan, dá aquela animada no ambiente")
    assert esperar(lambda: app.musica.ativa())                                      # ...a IA sim
    assert app.musica.estilo == "samba raiz" and falas == ["Fechou, vou de samba raiz!"]
    assert mente.separar_tocar("Escolhi pra você!\nTOCAR: -") == ("Escolhi pra você!", "")
    assert mente.separar_tocar("Oi!") == ("Oi!", None)


def test_panico_para_a_musica(app):
    app._musica_pelo_chat("toca um rock")
    assert esperar(lambda: app.tocou)
    app.panic()
    assert not app.musica.ativa()


def test_pedir_outra_descarta_o_que_estava_a_caminho(app, monkeypatch):
    import threading
    solta = threading.Event()
    monkeypatch.setattr(musica, "baixar_audio", lambda video_id, pasta: solta.wait(2) and Path(pasta) / video_id)
    app._musica_pelo_chat("toca um lo-fi")
    assert esperar(lambda: app.musica.atual is not None)
    app.musica.parar()
    solta.set()
    esperar(lambda: False, 0.3)
    assert app.tocou == [] and not app.musica.ativa()
