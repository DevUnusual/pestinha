"""
Imagem pedida no chat: "pesquisa o que é manga" acha o link de uma imagem na Wikipédia, baixa e o pet
projeta como holograma. Sem rede: a Wikipédia e o download são simulados.
"""
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402
from PySide6.QtCore import QBuffer, QIODevice, QUrl  # noqa: E402
from PySide6.QtGui import QColor, QImage, QTextDocument  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from pestinha import config  # noqa: E402
from pestinha.app import PestinhaApp  # noqa: E402
from pestinha.ia import imagem  # noqa: E402
from pestinha.paths import Paths  # noqa: E402
from pestinha.settings_store import SettingsStore  # noqa: E402
from pestinha.world import holograma as holo_mod  # noqa: E402
from pestinha.world.holograma import Holograma, imagem_de_bytes  # noqa: E402

QApplication.instance() or QApplication([])


def png(cor="#f6a400", tamanho=(64, 48)):
    QApplication.instance() or QApplication([])
    img = QImage(*tamanho, QImage.Format_ARGB32)
    img.fill(QColor(cor))
    buf = QBuffer()
    buf.open(QIODevice.WriteOnly)
    img.save(buf, "PNG")
    return bytes(buf.data())


# ---------------- ia/imagem.py ----------------

@pytest.mark.parametrize("texto, termo", [
    ("pesquisa o que é manga", "manga"),
    ("Pestinha, pesquise sobre a Torre Eiffel pra mim", "Torre Eiffel"),
    ("me mostra uma foto de um gato", "gato"),
    ("procura na internet quem foi Santos Dumont?", "Santos Dumont"),
    ("busca capivara por favor", "capivara"),
    ("oi, tudo bem?", None),
    ("mostra isso", None),
    ("o que você acha do meu código?", None),
])
def test_pedido_de_imagem(texto, termo):
    assert imagem.pedido_de_imagem(texto) == termo


def test_escolhe_a_fruta_e_nao_a_desambiguacao_nem_o_manga():
    paginas = [
        {"index": 1, "title": "Manga"},                                          # desambiguação: sem imagem
        {"index": 2, "title": "Mangá", "thumbnail": {"source": "https://x/manga_hq.jpg"}},
        {"index": 3, "title": "Manga (fruta)", "thumbnail": {"source": "https://x/mangas.jpg"}},
    ]
    assert imagem.escolher(paginas, "manga") == ("Manga (fruta)", "https://x/mangas.jpg")
    assert imagem.escolher(paginas, "mangá") == ("Mangá", "https://x/manga_hq.jpg")
    assert imagem.escolher([{"index": 1, "title": "Gato", "thumbnail": {"source": "u"}}], "felino") == ("Gato", "u")
    assert imagem.escolher([{"index": 1, "title": "Manga"}], "manga") is None


def test_baixar_so_aceita_link_de_imagem(monkeypatch):
    with pytest.raises(ValueError):
        imagem.baixar("file:///etc/passwd")
    monkeypatch.setattr(imagem, "_get", lambda url, tempo: (b"<html>", "text/html"))
    with pytest.raises(ValueError, match="não é uma imagem"):
        imagem.baixar("https://exemplo.com/pagina")
    monkeypatch.setattr(imagem, "_get", lambda url, tempo: (b"PNG", "image/png"))
    assert imagem.baixar("https://exemplo.com/a.png") == b"PNG"


def test_buscar_acha_o_link_e_baixa(monkeypatch):
    import json
    pedidos = []

    def get(url, tempo):
        pedidos.append(url)
        if "api.php" in url:
            return json.dumps({"query": {"pages": [
                {"index": 1, "title": "Manga (fruta)", "thumbnail": {"source": "https://upload.example.org/manga.jpg"}}]}}).encode(), \
                "application/json"
        return b"JPEG", "image/jpeg"

    monkeypatch.setattr(imagem, "_get", get)
    assert imagem.buscar("manga") == ("Manga (fruta)", b"JPEG")
    assert "gsrsearch=manga" in pedidos[0] and pedidos[1] == "https://upload.example.org/manga.jpg"


# ---------------- world/holograma.py ----------------

def test_holograma_abre_flutua_e_fecha():
    h = Holograma()
    assert not h.mostrar(None, "x", 0.0) and not h.mostrar(QImage(), "x", 0.0)
    img = imagem_de_bytes(png(tamanho=(800, 400)))
    assert h.mostrar(img, "Manga (fruta)", 100.0)
    assert h.imagem.width() <= holo_mod.LARGURA_MAX and h.imagem.height() <= holo_mod.ALTURA_MAX
    feixe, abre, falha = h.fases(100.0)
    assert feixe == 0.0 and abre == 0.0 and falha == 1.0                # começa do nada
    feixe, abre, falha = h.fases(102.0)
    assert feixe == 1.0 and abs(abre - 1.0) < 1e-9 and falha == 0.0     # aberto e estável
    assert h.visivel(100.0 + 3600.0)                                     # fica no ar até você mexer nele
    assert h.fechar(200.0) and not h.fechar(200.1)                       # fechar duas vezes não estica o fim
    _, abre, _ = h.fases(200.0 + holo_mod.FECHAR - 0.02)
    assert abre < 0.1                                                    # fechando numa linha
    assert h.visivel(200.0) and not h.visivel(200.0 + holo_mod.FECHAR + 0.01)


def test_holograma_desenha_a_imagem():
    h = Holograma()
    h.mostrar(imagem_de_bytes(png("#ff8800")), "Manga", 0.0)
    h._agora = 2.0
    tela = QImage(h.size(), QImage.Format_ARGB32)
    tela.fill(0)
    h.render(tela)
    meio = QColor(tela.pixel(tela.width() // 2, holo_mod.MARGEM + holo_mod.TITULO + 20))
    assert meio.red() > 180 and meio.alpha() > 0                         # a manga laranja aparece (com tom de holograma)


def test_holograma_nao_pega_clique():
    from PySide6.QtCore import Qt
    h = Holograma()
    assert h.windowFlags() & Qt.WindowTransparentForInput


# ---------------- dentro do app ----------------

class ClienteFalso:
    ve_imagem = False

    def __init__(self):
        self.chamadas = []

    def responder(self, sistema, mensagens, imagem=None, tarefa="chat"):
        self.chamadas.append(mensagens)
        return "Manga é uma fruta tropical, docinha!"


@pytest.fixture
def app(tmp_path, monkeypatch):
    qapp = QApplication.instance() or QApplication([])
    qapp.setQuitOnLastWindowClosed(False)
    paths = Paths(root=tmp_path)
    store = SettingsStore(paths)
    store.update(dict(config.DEFAULT_PERMISSIONS, ia=True, conversa=True, pesquisar=True, modo_teste=True))
    a = PestinhaApp(store, paths)
    cliente = ClienteFalso()
    monkeypatch.setattr(a.visao, "cliente", lambda: cliente)
    a.pet.show()
    yield a
    a.visao.cancelar()
    a.balao.esconder()
    a.holograma.esconder()
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


def test_pedir_no_chat_projeta_a_imagem(app, monkeypatch):
    termos = []
    monkeypatch.setattr("pestinha.mind.visao.buscar_imagem_na_web",
                        lambda termo: termos.append(termo) or ("Manga (fruta)", png()))
    assert app.visao.perguntar("pesquisa o que é manga")
    assert esperar(lambda: app.holograma.visivel(time.monotonic()))
    assert termos == ["manga"] and app.holograma.titulo == "Manga (fruta)"
    assert "projetando" in app.pet_state.mente
    app._atualizar_mente(time.monotonic())
    assert "projetando" in app.pet_state.mente and not app.visao.buscando_imagem
    app.panic()
    assert not app.holograma.visivel(time.monotonic())


def test_projetando_fica_parado_ate_voce_mexer_e_a_imagem_vai_pro_chat(app, monkeypatch):
    monkeypatch.setattr("pestinha.mind.visao.buscar_imagem_na_web", lambda termo: ("Manga (fruta)", png()))
    app.menu_conversar()
    assert app.visao.perguntar("pesquisa o que é manga")
    assert esperar(lambda: app.holograma.visivel(time.monotonic()))
    historico = app.conversa_janela.historico
    assert 'src="imagem-1.png"' in historico.toHtml()
    assert not historico.document().resource(QTextDocument.ImageResource, QUrl("imagem-1.png")).isNull()

    body, agora = app.pet.body, time.monotonic()
    body.grounded, body.vx = True, 300.0
    app.behavior.target_x = body.x + 500
    app.behavior.tick(0.016, agora, (0, 0), app.bounds(), app.prof)
    assert body.vx == 0.0 and app.behavior.target_x is None              # paradinho, sem passear

    app.on_poke()                                                        # você mexeu nele: a imagem fecha
    assert not app.holograma.visivel(time.monotonic() + holo_mod.FECHAR + 0.01)
    app.conversa_janela.close()


def test_sem_permissao_de_pesquisar_nao_busca(app, monkeypatch):
    app.perms["pesquisar"] = False
    chamou = []
    monkeypatch.setattr("pestinha.mind.visao.buscar_imagem_na_web", lambda termo: chamou.append(termo))
    assert app.visao.perguntar("pesquisa o que é manga")
    esperar(lambda: not app.visao.respondendo, 1.0)
    assert chamou == [] and not app.visao.buscando_imagem


def test_conversa_comum_nao_busca_imagem(app, monkeypatch):
    chamou = []
    monkeypatch.setattr("pestinha.mind.visao.buscar_imagem_na_web", lambda termo: chamou.append(termo))
    assert app.visao.perguntar("oi, tudo bem?")
    esperar(lambda: not app.visao.respondendo, 1.0)
    assert chamou == []


def test_panico_descarta_a_imagem_a_caminho(app, monkeypatch):
    import threading
    solta = threading.Event()
    monkeypatch.setattr("pestinha.mind.visao.buscar_imagem_na_web",
                        lambda termo: solta.wait(2) and ("Manga", png()))
    app.visao.perguntar("me mostra uma foto de manga")
    assert app.visao.buscando_imagem
    app.panic()
    solta.set()
    time.sleep(0.1)
    esperar(lambda: False, 0.3)
    assert not app.holograma.visivel(time.monotonic())
