"""
Estudar os jogos: o nome pelo título, o artigo da Wikipédia, o estudo condensado, a memória do jogo com o
progresso que só sobe, a história que nunca passa de onde a pessoa chegou (sem spoiler) e o comentário sobre
a jogabilidade, com o controlador dentro do app de verdade (Qt offscreen, modelo e Wikipédia falsos).
"""

import json
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
from pestinha.ia import jogo_info, mente  # noqa: E402
from pestinha.mind import jogo_ctl, visao as visao_mod  # noqa: E402
from pestinha.mind.jogos import Jogos  # noqa: E402
from pestinha.paths import Paths  # noqa: E402
from pestinha.settings_store import SettingsStore  # noqa: E402

ESTUDO = {"nome": "Hollow Knight", "genero": "metroidvania", "premissa": "Um cavaleiro desce ao reino caído.",
          "gameplay": ["Golpes de ferrão e foco para curar com a alma."],
          "dicas": ["Pare num banco para salvar e trocar amuletos."],
          "historia": ["Encruzilhadas Esquecidas: o cavaleiro chega a Dirtmouth e desce.",
                       "Caminho Verde: encontra Hornet pela primeira vez.",
                       "Cidade das Lágrimas: o Cavaleiro Oco é o receptáculo que falhou."]}


# ---------------- texto (sem Qt) ----------------

@pytest.mark.parametrize("titulo, esperado", [
    ("Minecraft 1.21.4 - Singleplayer", "Minecraft"),
    ("ELDEN RING™", "ELDEN RING"),
    ("Hollow Knight", "Hollow Knight"),
    ("Launcher", ""),
    ("", ""),
    ("v1.2.3", ""),
])
def test_nome_pelo_titulo(titulo, esperado):
    assert jogo_info.nome_pelo_titulo(titulo) == esperado


def test_chave_junta_o_mesmo_jogo():
    assert jogo_info.chave("ELDEN RING™") == jogo_info.chave("Elden Ring") == "elden ring"
    assert jogo_info.chave("Pokémon: Edição Ouro") == "pokemon edicao ouro"


def test_artigo_so_com_jogabilidade_e_enredo():
    artigo = ("Hollow Knight is a 2017 video game.\n\n== Gameplay ==\nYou fight.\n\n=== Charms ===\nCharms."
              "\n\n== Plot ==\nThe Knight descends.\n\n== Development ==\nTeam Cherry.\n\n== Reception ==\nGood.")
    texto = jogo_info.secoes_boas(artigo)
    assert "2017 video game" in texto and "You fight" in texto and "Charms." in texto and "descends" in texto
    assert "Team Cherry" not in texto and "Good." not in texto


def test_escolhe_o_artigo_do_jogo():
    resultados = [{"title": "Hollow (filme)", "snippet": "um filme"},
                  {"title": "Hollow Knight", "snippet": "é um <b>jogo eletrônico</b> de ação"},
                  {"title": "Hollow Knight: Silksong", "snippet": "video game"}]
    assert jogo_info.escolher_artigo(resultados, "Hollow Knight") == "Hollow Knight"
    assert jogo_info.escolher_artigo([{"title": "Batata", "snippet": "tubérculo"}], "Hollow Knight") is None
    filme_primeiro = [{"title": "Elden Ring (film)", "snippet": "film based on the 2022 video game"},
                      {"title": "Elden Ring", "snippet": "action role-playing game"},
                      {"title": "Halo (2003 video game)", "snippet": "shooter"}]
    assert jogo_info.escolher_artigo(filme_primeiro, "ELDEN RING") == "Elden Ring"
    assert jogo_info.escolher_artigo(filme_primeiro[2:], "Halo") == "Halo (2003 video game)"


def test_le_o_estudo_e_o_trecho():
    estudo = jogo_info.ler_estudo("```json\n" + json.dumps(ESTUDO) + "\n```")
    assert estudo["nome"] == "Hollow Knight" and len(estudo["historia"]) == 3
    assert jogo_info.ler_estudo('{"nome": ""}') is None and jogo_info.ler_estudo("sei lá") is None
    assert jogo_info.ler_trecho('{"trecho": 2}', 3) == 2
    assert jogo_info.ler_trecho('{"trecho": 0}', 3) is None and jogo_info.ler_trecho('{"trecho": 9}', 3) is None
    assert "Cidade das Lágrimas" in jogo_info.pedido_trecho("HK", ESTUDO["historia"], "Caminho Verde")


@pytest.mark.parametrize("texto, esperado", [
    ("como termina o jogo?", True),
    ("pode dar spoiler", True),
    ("o que acontece depois desse chefe?", True),
    ("me conta a história inteira", True),
    ("sem spoiler, qual a melhor build?", False),
    ("não quero spoiler", False),
    ("como passo desse chefe?", False),
])
def test_pediu_spoiler(texto, esperado):
    assert jogo_info.pediu_spoiler(texto) is esperado


def test_olhada_em_jogo_fala_de_gameplay_sem_spoiler():
    pedido = mente.pedido_observacao("hollow_knight", "Hollow Knight", "GAMING", "curioso", jogo=True,
                                     sobre_jogo="Jogo: Hollow Knight.")
    assert "JOGABILIDADE" in pedido and "Nunca comente o visual, a atmosfera" in pedido
    assert "Sem spoiler" in pedido and '"jogo": "", "onde": ""' in pedido
    assert pedido.startswith("[O que você sabe deste jogo: Jogo: Hollow Knight.]")
    fora = mente.pedido_observacao("code", "x", "PROGRAMMING", "curioso", sobre_jogo="Jogo: Hollow Knight.")
    assert "JOGABILIDADE" not in fora and "Hollow Knight" not in fora and '"onde"' not in fora
    obs = mente.ler_observacao('{"resumo": "jogando", "jogo": "Hollow Knight", "onde": "Caminho Verde"}')
    assert (obs.jogo, obs.onde) == ("Hollow Knight", "Caminho Verde")
    assert mente.limpar_fala("[O que você sabe deste jogo: x] Boa esquiva!") == "Boa esquiva!"


# ---------------- memória do jogo ----------------

def test_historia_so_ate_onde_chegou(tmp_path):
    jogos = Jogos(tmp_path / "jogos.json")
    assert jogos.guardar_estudo("hollow knight", ESTUDO, "teste")
    olhada = jogos.contexto_olhada("hollow knight")
    assert "Golpes de ferrão" in olhada and "Encruzilhadas" not in olhada        # sem progresso: só a premissa
    assert jogos.avancar("hollow knight", 2)
    olhada = jogos.contexto_olhada("hollow knight")
    assert "Hornet" in olhada and "receptáculo" not in olhada and "trecho 2 de 3" in olhada
    assert not jogos.avancar("hollow knight", 1) and jogos.get("hollow knight")["trecho"] == 2   # só sobe
    chat = jogos.contexto_chat("qual a melhor build no hollow knight?")
    assert "Hornet" in chat and "receptáculo" not in chat and "Sem spoiler" in chat
    spoiler = jogos.contexto_chat("como termina hollow knight?", spoiler=True)
    assert "receptáculo" in spoiler and "PEDIU spoiler" in spoiler


def test_onde_so_grava_lugar_novo(tmp_path):
    jogos = Jogos(tmp_path / "jogos.json")
    agora = time.time()
    assert jogos.anotar_onde("hk", "HK", "Caminho Verde", agora)
    assert not jogos.anotar_onde("hk", "HK", "caminho verde", agora + 5)
    assert jogos.anotar_onde("hk", "HK", "Cidade das Lágrimas", agora + 10)
    assert [o["texto"] for o in jogos.get("hk")["onde"]] == ["Caminho Verde", "Cidade das Lágrimas"]
    assert "Cidade das Lágrimas" in jogos.contexto_olhada("hk", agora + 20)
    (tmp_path / "jogos.json").write_text("{quebrado", encoding="utf-8")
    assert jogos.todos() == {} and jogos.contexto_olhada("hk") == ""


# ---------------- controlador, dentro do app ----------------

@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    return app


class ModeloFalso:
    """Responde a olhada, o estudo e a localização, conforme o pedido."""
    ve_imagem = True

    def __init__(self):
        self.olhada = {"resumo": "jogando Hollow Knight", "comentario": "", "jogo": "Hollow Knight", "onde": ""}
        self.trecho = 2
        self.pedidos = []

    def responder(self, sistema, mensagens, imagem=None):
        texto = mensagens[-1]["content"]
        self.pedidos.append((sistema, texto))
        if sistema == jogo_info.SISTEMA_ESTUDO:
            return json.dumps(ESTUDO)
        if sistema == jogo_info.SISTEMA_TRECHO:
            return json.dumps({"trecho": self.trecho})
        return json.dumps(self.olhada)


@pytest.fixture
def pet(qapp, tmp_path, monkeypatch):
    paths = Paths(root=tmp_path)
    store = SettingsStore(paths)
    store.update(dict(config.DEFAULT_PERMISSIONS, ia=True, ver_tela=True, jogos=True, estudar_jogos=True,
                      ia_provedor="ollama"))
    app = PestinhaApp(store, paths)
    modelo = ModeloFalso()
    wiki = []
    monkeypatch.setattr(app.visao, "cliente", lambda: modelo)
    monkeypatch.setattr(visao_mod, "capturar_tela", lambda *_a, **_k: None)
    monkeypatch.setattr(visao_mod.senses, "get_active_app", lambda: "hollow_knight.exe")
    monkeypatch.setattr(visao_mod.senses, "get_active_title", lambda: "Hollow Knight")
    monkeypatch.setattr(visao_mod.senses, "jogo_pelo_titulo", lambda *_a: True)
    monkeypatch.setattr(jogo_ctl, "buscar_wikipedia",
                        lambda nome: wiki.append(nome) or ("Hollow Knight", "Hollow Knight is a video game."))
    app.pet.show()
    yield app, modelo, wiki
    app.visao.cancelar()
    app.balao.esconder()
    app.mischief.clear()
    app.tray.icon.hide()


def esperar(qapp, condicao, segundos=3.0):
    fim = time.monotonic() + segundos
    while time.monotonic() < fim:
        qapp.processEvents()
        if condicao():
            return True
        time.sleep(0.01)
    return False


def olhar(qapp, app, agora):
    app.visao.olhar(agora)
    assert esperar(qapp, lambda: not app.visao.olhando)


def test_reconhece_estuda_e_acompanha_sem_spoiler(qapp, pet):
    app, modelo, wiki = pet
    falas = []
    app.jogo.fala.connect(falas.append)
    agora = time.monotonic()
    olhar(qapp, app, agora)
    assert wiki == [] and not app.jogo.estudando                       # uma olhada só ainda não confirma
    olhar(qapp, app, agora + 10)
    assert esperar(qapp, lambda: app.jogo.memoria.estudado("hollow knight"))
    assert wiki == ["Hollow Knight"] and any("não dou spoiler" in f for f in falas)
    estudo_pedido = [t for s, t in modelo.pedidos if s == jogo_info.SISTEMA_ESTUDO][0]
    assert "Hollow Knight is a video game." in estudo_pedido

    modelo.olhada = dict(modelo.olhada, onde="Caminho Verde, lutando com Hornet")
    olhar(qapp, app, agora + 20)
    assert esperar(qapp, lambda: app.jogo.memoria.get("hollow knight")["trecho"] == 2)

    olhar(qapp, app, agora + 30)
    ultima = [t for s, t in modelo.pedidos if s not in (jogo_info.SISTEMA_ESTUDO, jogo_info.SISTEMA_TRECHO)][-1]
    assert "Hornet" in ultima and "receptáculo" not in ultima          # a história só até onde ela chegou
    assert "Caminho Verde" in ultima


def test_desligado_nao_estuda(qapp, pet):
    app, _modelo, wiki = pet
    app.apply_perms({"estudar_jogos": False})
    agora = time.monotonic()
    olhar(qapp, app, agora)
    olhar(qapp, app, agora + 10)
    assert wiki == [] and app.jogo.memoria.todos() == {} and app.jogo.contexto_chat("hollow knight") == ""


def test_chat_so_conta_o_resto_se_pedir(qapp, pet):
    app, _modelo, _wiki = pet
    app.jogo.memoria.guardar_estudo("hollow knight", ESTUDO)
    app.jogo.memoria.avancar("hollow knight", 1)
    normal = app.visao.jogos("qual amuleto uso no hollow knight?")
    assert "Encruzilhadas" in normal and "Hornet" not in normal
    spoiler = app.visao.jogos("pode dar spoiler: como termina hollow knight?")
    assert "receptáculo" in spoiler


def test_configuracao_depende_de_acompanhar_jogos(qapp, tmp_path):
    from pestinha.ui.ui import SettingsDialog
    assert config.DEFAULT_PERMISSIONS["estudar_jogos"] is False
    dialogo = SettingsDialog(dict(config.DEFAULT_PERMISSIONS, ia=True, ver_tela=True), Paths(root=tmp_path),
                             first_run=False)
    assert not dialogo.boxes["estudar_jogos"].isEnabled()
    dialogo.boxes["jogos"].setChecked(True)
    assert dialogo.boxes["estudar_jogos"].isEnabled()
    dialogo.close()
