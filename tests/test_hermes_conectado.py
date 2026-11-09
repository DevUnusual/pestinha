"""
Pet e Hermes conectados: o chat passa pelo Hermes (persona do pet, pesquisa, memória por sessão), a IA vilã
aparece só enquanto ele usa uma ferramenta, o link de imagem da resposta vira holograma e, se o Hermes cair,
o provedor escolhido responde no lugar sem a conversa quebrar.
"""
import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402
from PySide6.QtCore import QBuffer, QIODevice  # noqa: E402
from PySide6.QtGui import QColor, QImage  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from pestinha import config  # noqa: E402
from pestinha.app import PestinhaApp  # noqa: E402
from pestinha.ia import imagem, mente, pesquisa, provedores  # noqa: E402
from pestinha.paths import Paths  # noqa: E402
from pestinha.settings_store import SettingsStore  # noqa: E402

QApplication.instance() or QApplication([])

LINK = "https://upload.wikimedia.org/wikipedia/commons/9/90/Hapus_Mango.jpg"


def png():
    img = QImage(40, 30, QImage.Format_ARGB32)
    img.fill(QColor("#f6a400"))
    buf = QBuffer()
    buf.open(QIODevice.WriteOnly)
    img.save(buf, "PNG")
    return bytes(buf.data())


def sse(resposta, ferramentas=("web_search",)):
    """O stream que o Hermes manda: ferramentas rodando e terminando, depois o texto em pedaços."""
    frames = [b'data: {"choices":[{"delta":{"role":"assistant"}}]}\n\n']
    for i, nome in enumerate(ferramentas):
        for status in ("running", "completed"):
            dados = json.dumps({"tool": nome, "toolCallId": f"c{i}", "status": status}).encode()
            frames.append(b"event: hermes.tool.progress\ndata: " + dados + b"\n\n")
    for pedaco in (resposta[: len(resposta) // 2], resposta[len(resposta) // 2:]):
        frames.append(b"data: " + json.dumps({"choices": [{"delta": {"content": pedaco}}]}).encode() + b"\n\n")
    frames.append(b"data: [DONE]\n\n")
    return b"".join(frames)


# ---------------- sem rede ----------------

def test_ler_stream_junta_texto_e_avisa_ferramentas():
    eventos = []
    texto = pesquisa.ler_stream(sse("Manga é fruta!").split(b"\n"), lambda f, r: eventos.append((f, r)))
    assert texto == "Manga é fruta!" and eventos == [("web_search", True), ("web_search", False)]


def test_stream_cortado_nao_deixa_ferramenta_rodando():
    corte = b'event: hermes.tool.progress\ndata: {"tool":"web_search","toolCallId":"a","status":"running"}\n\n'
    eventos = []
    pesquisa.ler_stream(corte.split(b"\n"), lambda f, r: eventos.append(r))
    assert eventos == [True, False]


def test_separar_imagem():
    assert mente.separar_imagem(f"É uma fruta!\nIMAGEM: {LINK}") == ("É uma fruta!", LINK)
    assert mente.separar_imagem(f"Olha\nimagem: <{LINK}>") == ("Olha", LINK)
    assert mente.separar_imagem("Sem imagem aqui.") == ("Sem imagem aqui.", None)
    assert mente.separar_imagem("IMAGEM: ftp://x/y.jpg")[1] is None


def test_sistema_hermes_tem_a_persona_e_as_ferramentas():
    s = mente.sistema_hermes("Você é o Bryan.")
    assert s.startswith("Você é o Bryan.") and "memória" in s and "IMAGEM:" in s


def test_miniatura_do_wikimedia_e_titulo():
    assert imagem.miniatura_wikimedia(LINK) == (
        "https://upload.wikimedia.org/wikipedia/commons/thumb/9/90/Hapus_Mango.jpg/500px-Hapus_Mango.jpg")
    assert imagem.miniatura_wikimedia("https://upload.wikimedia.org/wikipedia/commons/thumb/9/90/X.jpg/480px-X.jpg") == (
        "https://upload.wikimedia.org/wikipedia/commons/thumb/9/90/X.jpg/500px-X.jpg")         # tamanho padrão
    assert imagem.miniatura_wikimedia("https://upload.wikimedia.org/wikipedia/commons/thumb/9/90/X.jpg/500px-X.jpg") is None
    assert imagem.miniatura_wikimedia("https://example.com/a.jpg") is None
    assert imagem.titulo_do_link(LINK) == "Hapus Mango"


def test_baixar_tenta_a_miniatura_e_cai_no_original(monkeypatch):
    pedidos = []

    def get(url, tempo):
        pedidos.append(url)
        if "/thumb/" in url:
            raise OSError("sem miniatura")
        return b"JPG", "image/jpeg"

    monkeypatch.setattr(imagem, "_get", get)
    assert imagem.baixar(LINK) == b"JPG" and "/thumb/" in pedidos[0] and pedidos[1] == LINK


# ---------------- Hermes falso ----------------

@pytest.fixture
def hermes_falso():
    """Um Hermes nesta máquina: guarda os pedidos e responde em SSE (ou com erro, se `falhar`)."""
    estado = {"pedidos": [], "resposta": f"Manga é a fruta da mangueira!\nIMAGEM: {LINK}", "falhar": False}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_POST(self):
            corpo = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            estado["pedidos"].append((dict(self.headers), corpo))
            if estado["falhar"]:
                self.send_response(502)
                self.end_headers()
                return
            dados = sse(estado["resposta"])
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Content-Length", str(len(dados)))
            self.end_headers()
            self.wfile.write(dados)

    servidor = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    estado["url"] = f"http://127.0.0.1:{servidor.server_address[1]}"
    yield estado
    servidor.shutdown()


def test_cliente_hermes_manda_sessao_e_stream(monkeypatch, hermes_falso):
    monkeypatch.setenv(pesquisa.CHAVE, "segredo")
    cliente = pesquisa.criar_cliente(hermes_falso["url"], "pestinha-bryan")
    eventos = []
    texto = cliente.conversar("sistema", [{"role": "user", "content": "oi"}], lambda f, r: eventos.append(r))
    cabecalhos, corpo = hermes_falso["pedidos"][0]
    assert cabecalhos["X-Hermes-Session-Key"] == "pestinha-bryan"
    assert cabecalhos["Authorization"] == "Bearer segredo"
    assert corpo["stream"] is True and corpo["messages"][0] == {"role": "system", "content": "sistema"}
    assert texto.startswith("Manga") and eventos == [True, False]
    hermes_falso["falhar"] = True
    with pytest.raises(provedores.ErroIA, match="502"):
        cliente.conversar("s", [{"role": "user", "content": "oi"}])


class ProvedorFalso:
    ve_imagem = False

    def __init__(self):
        self.chamadas = []

    def responder(self, sistema, mensagens, imagem=None, tarefa="chat"):
        self.chamadas.append(mensagens)
        return "Respondi eu mesmo."


@pytest.fixture
def app(tmp_path, monkeypatch, hermes_falso):
    monkeypatch.setenv(pesquisa.CHAVE, "segredo")
    paths = Paths(root=tmp_path)
    store = SettingsStore(paths)
    store.update(dict(config.DEFAULT_PERMISSIONS, ia=True, conversa=True, pesquisar=True, modo_teste=True,
                      hermes_url=hermes_falso["url"]))
    a = PestinhaApp(store, paths)
    provedor = ProvedorFalso()
    monkeypatch.setattr(a.visao, "cliente", lambda: provedor)
    monkeypatch.setattr("pestinha.mind.visao.baixar_imagem", lambda url: png())
    a.pet.show()
    yield a, provedor
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


def test_chat_passa_pelo_hermes_e_projeta_o_link(app, hermes_falso):
    a, provedor = app
    assert a.visao.com_hermes() and "Hermes" in a.visao.descricao()
    assert a.visao.perguntar("pesquisa o que é manga")
    assert esperar(lambda: a.holograma.visivel(time.monotonic()))
    cabecalhos, corpo = hermes_falso["pedidos"][0]
    assert cabecalhos["X-Hermes-Session-Key"] == a.visao.sessao.lower() == "pestinha-bryan"
    assert "IMAGEM:" in corpo["messages"][0]["content"]                 # sistema com as instruções
    assert a.balao.texto == "Manga é a fruta da mangueira!"             # a linha do link não aparece
    assert a.holograma.titulo == "Manga" and provedor.chamadas == []
    assert a.visao.conversa.turnos[-1] == {"role": "assistant", "content": "Manga é a fruta da mangueira!"}


def test_vila_so_enquanto_o_hermes_usa_ferramenta(app):
    a, _ = app
    a.visao.respondendo = True
    a._atualizar_mente(0.0)
    assert a.pet_state.mente == {"pensando"}                            # pensando: detetive
    a.visao._ao_usar_ferramenta(True, a.visao.geracao)
    a._atualizar_mente(0.0)
    assert a.pet_state.mente == {"pesquisando"}                         # pesquisando: IA vilã
    a.visao._ao_usar_ferramenta(False, a.visao.geracao)
    a._atualizar_mente(0.0)
    assert a.pet_state.mente == {"pensando"}
    a.visao._ao_usar_ferramenta(True, a.visao.geracao - 1)             # de antes do pânico: ignora
    assert a.visao.ferramentas == 0


def test_hermes_caiu_o_provedor_responde_no_lugar(app, hermes_falso):
    a, provedor = app
    hermes_falso["falhar"] = True
    avisos = []
    a.visao.aviso.connect(avisos.append)
    assert a.visao.perguntar("oi, tudo bem?")
    assert esperar(lambda: a.balao.texto == "Respondi eu mesmo.")
    assert len(provedor.chamadas) == 1 and any("Hermes" in x for x in avisos)
    assert not a.visao.respondendo and a.visao.ferramentas == 0


def test_link_quebrado_cai_na_wikipedia(app, hermes_falso, monkeypatch):
    a, _ = app

    def quebrado(url):
        raise ValueError("não é imagem")

    monkeypatch.setattr("pestinha.mind.visao.baixar_imagem", quebrado)
    monkeypatch.setattr("pestinha.mind.visao.buscar_imagem_na_web", lambda termo: ("Manga (fruta)", png()))
    a.visao.perguntar("me mostra uma foto de manga")
    assert esperar(lambda: a.holograma.visivel(time.monotonic()))
    assert a.holograma.titulo == "Manga (fruta)"


def test_sem_hermes_conectado_o_chat_usa_o_provedor(app, hermes_falso):
    a, provedor = app
    a.perms["pesquisar"] = False
    assert not a.visao.com_hermes()
    a.visao.perguntar("oi")
    assert esperar(lambda: a.balao.texto == "Respondi eu mesmo.")
    assert hermes_falso["pedidos"] == []
