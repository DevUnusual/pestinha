"""
Assistir vídeos (ouvir, anotar, resumir e guardar) e desenhar na tela: o texto do modelo, o conhecimento
em disco, a janela do desenho e os controladores dentro do app de verdade (Qt offscreen, pasta temporária,
som e modelo falsos). Nenhum teste ouve o som de verdade nem chama uma API.
"""

import math
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
import pytest  # noqa: E402
from PySide6.QtGui import QImage  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from pestinha import config  # noqa: E402
from pestinha.app import PestinhaApp  # noqa: E402
from pestinha.ia import desenho, mente, video  # noqa: E402
from pestinha.mind import video_ctl  # noqa: E402
from pestinha.mind import visao as visao_mod  # noqa: E402
from pestinha.mind.conhecimento import Conhecimento  # noqa: E402
from pestinha.paths import Paths  # noqa: E402
from pestinha.settings_store import SettingsStore  # noqa: E402
from pestinha.world.rabisco import Rabisco, prefixo  # noqa: E402


# ---------------- desenho: o pedido do modelo ----------------

def test_linha_desenhar_vira_formas_em_fracoes_da_tela():
    texto = ('Olha o botão aqui!\nDESENHAR: [{"forma": "circulo", "caixa": [100, 200, 300, 400], "texto": "aqui"},'
             ' {"forma": "seta", "de": [900, 900], "para": [500, 500]}, {"forma": "icone", "em": [10, 20], '
             '"icone": "estrela"}]')
    limpo, formas = desenho.separar_desenho(texto)
    assert limpo == "Olha o botão aqui!"
    assert [f.tipo for f in formas] == ["circulo", "seta", "icone"]
    assert formas[0].pontos == ((0.1, 0.2), (0.3, 0.4)) and formas[0].texto == "aqui"
    assert formas[1].pontos == ((0.9, 0.9), (0.5, 0.5))
    assert formas[2].icone == "★"


def test_desenho_aceita_fracoes_sinonimos_e_corrige_a_caixa():
    formas = desenho.ler_formas([{"tipo": "retângulo", "box": [0.8, 0.9, 0.2, 0.1]},
                                 {"forma": "circle", "caixa": [500, 500, 500, 500]}])
    assert formas[0].tipo == "quadrado" and formas[0].pontos == ((0.2, 0.1), (0.8, 0.9))
    (x1, y1), (x2, y2) = formas[1].pontos
    assert x2 - x1 >= desenho.MIN_LADO - 1e-9 and y2 - y1 >= desenho.MIN_LADO - 1e-9   # ponto vira círculo


@pytest.mark.parametrize("dados", [None, "x", 3, [], [{"forma": "estrela"}], [{"forma": "circulo"}],
                                   [{"forma": "seta", "de": [1, 1], "para": [1, 1]}],
                                   [{"forma": "circulo", "caixa": ["a", 1, 2, 3]}],
                                   [{"forma": "icone", "em": [float("nan"), 3]}]])
def test_desenho_ruim_e_pulado(dados):
    assert desenho.ler_formas(dados) == []


def test_no_maximo_tres_formas_e_coordenada_fora_e_cortada():
    formas = desenho.ler_formas([{"forma": "icone", "em": [5000, -20]}] * 6)
    assert len(formas) == desenho.MAX_FORMAS and formas[0].pontos == ((1.0, 0.0),)


def test_linha_desenhar_quebrada_sai_da_fala_sem_formas():
    limpo, formas = desenho.separar_desenho("Tá aqui.\n**DESENHAR:** [{quebrado\nTchau")
    assert formas == [] and "DESENHAR" not in limpo and "Tá aqui." in limpo and "Tchau" in limpo


def test_sem_linha_desenhar_nada_muda():
    assert desenho.separar_desenho("só conversa") == ("só conversa", [])


def test_olhada_traz_desenho_e_video():
    obs = mente.ler_observacao('{"resumo": "vendo aula", "comentario": "olha o erro", "video": true, '
                               '"desenhar": [{"forma": "quadrado", "caixa": [0, 0, 500, 500]}]}')
    assert obs.video is True and obs.desenhar[0].tipo == "quadrado"
    assert mente.ler_observacao('{"video": "sim"}').video is False


def test_pedido_da_olhada_so_pede_desenho_e_video_quando_pode():
    sem = mente.pedido_observacao("chrome", "", "BROWSING", "feliz")
    com = mente.pedido_observacao("chrome", "", "BROWSING", "feliz", desenhar=True, video=True)
    assert '"desenhar"' not in sem and '"video"' not in sem
    assert '"desenhar": []' in com and '"video": false' in com


# ---------------- vídeo: o texto ----------------

@pytest.mark.parametrize("texto, esperado", [
    ("assiste esse vídeo comigo", "comecar"),
    ("Vamos assistir junto?", "comecar"),
    ("presta atenção nessa aula", "comecar"),
    ("escuta esse podcast", "comecar"),
    ("resume o vídeo", "parar"),
    ("me faz um resumo do vídeo", "parar"),
    ("pode parar de assistir", "parar"),
    ("acabou o vídeo", "parar"),
    ("não assiste esse vídeo comigo", None),
    ("que vídeo legal", None),
    ("toca um lo-fi", None),
    ("", None),
])
def test_pedido_de_video(texto, esperado):
    assert video.pedido_de_video(texto) == esperado


@pytest.mark.parametrize("texto, esperado", [
    ("sim", "sim"), ("Pode sim!", "sim"), ("bora", "sim"), ("é sim", "sim"), ("assiste comigo", "sim"),
    ("não, valeu", "nao"), ("agora não", "nao"), ("nem precisa", "nao"),
    ("que horas são?", None), ("", None),
])
def test_resposta_a_oferta(texto, esperado):
    assert video.resposta_a_oferta(texto) == esperado


def test_transcricao_guarda_o_que_viu_na_tela():
    t = video.Transcricao()
    assert t.ver(5, "slide de título") and not t.ver(9, "slide de título")
    assert t.ver(65, "código em Python")
    assert t.texto_telas() == "[0:05] slide de título\n[1:05] código em Python"
    assert t.vazia()                                                   # ver não é ouvir alguém falando


def test_tem_som():
    silencio = np.zeros(16000, dtype="<i2").tobytes()
    tom = (np.sin(np.arange(16000) / 5.0) * 8000).astype("<i2").tobytes()
    assert not video.tem_som(silencio) and video.tem_som(tom) and not video.tem_som(b"")


def test_transcricao_pula_alucinacao_e_repeticao_e_condensa_o_velho():
    t = video.Transcricao()
    assert not t.adicionar(0, "Legendas pela comunidade Amara.org")
    assert t.adicionar(0, "  primeira   fala ") and not t.adicionar(20, "primeira fala")
    assert t.texto() == "[0:00] primeira fala"
    assert t.pedaco_para_notas() is None
    for i in range(1, 40):
        t.adicionar(i * 20, f"trecho {i} " + "x" * 400)
    pedaco = t.pedaco_para_notas()
    assert pedaco and "[0:00] primeira fala" in pedaco and t.trechos and t.trechos[0][0] > 0
    t.anotar("- ponto um")
    assert t.notas == ["- ponto um"] and not t.vazia()
    for _ in range(40):
        t.anotar("n" * 400)
    assert sum(len(n) for n in t.notas) <= video.MAX_NOTAS


def test_resumo_tolera_texto_em_volta_e_campos_ruins():
    a = video.ler_resumo('Pronto!\n{"titulo": "Como fazer pão", "resumo": "Sova e descanso.", '
                         '"pontos": ["farinha", 3, "", "fermento"], "comentario": "Fiquei com fome"}')
    assert (a.titulo, a.resumo, a.pontos, a.comentario) == ("Como fazer pão", "Sova e descanso.",
                                                           ["farinha", "fermento"], "Fiquei com fome")
    assert video.ler_resumo("sem json").vazio() and video.ler_resumo('{"resumo": 5}').vazio()


def test_tempo():
    assert video.tempo(125) == "2:05" and video.tempo(3725) == "1:02:05"


# ---------------- conhecimento em disco ----------------

def test_conhecimento_guarda_le_e_acha_o_assunto(tmp_path):
    caminho = tmp_path / "pet" / "conhecimento.jsonl"
    c = Conhecimento(caminho, "pc")
    assert c.contexto("oi") == ""
    assert not c.guardar(video.Aprendizado())                         # vazio não grava
    assert c.guardar(video.Aprendizado("Receita de pão caseiro", "Sova, descanso e forno quente.",
                                       ["farinha forte", "fermento natural"]), 600, agora=1000)
    assert c.guardar(video.Aprendizado("Python assíncrono", "asyncio e await."), agora=2000)
    caminho.write_text(caminho.read_text(encoding="utf-8") + "lixo\n{\"resumo\": 3}\n", encoding="utf-8")
    assert [i["titulo"] for i in c.todos()] == ["Receita de pão caseiro", "Python assíncrono"]
    contexto = c.contexto("como era aquela receita de pão?", agora=3000)
    assert "«Python assíncrono»" in contexto and "Sova, descanso" in contexto and "farinha forte" in contexto
    assert "Sova" not in c.contexto("bom dia, tudo bem?", agora=3000)


def test_conhecimento_vai_para_a_memoria_compartilhada(tmp_path):
    from pestinha import memoria_remota
    paths = Paths(root=tmp_path)
    perms = dict(config.DEFAULT_PERMISSIONS, memoria_compartilhada=True, memoria_url="127.0.0.1")
    sinc = memoria_remota.criar(perms, paths, "bryan", paths.pet("bryan"))
    assert sinc.arquivos["conhecimento.jsonl"] == paths.pet("bryan").conhecimento


# ---------------- a janela do desenho ----------------

@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    return app


def test_prefixo_do_traco():
    assert prefixo([1, 2, 3, 4, 5], 0) == [] and prefixo([1, 2, 3, 4, 5], 1.0) == [1, 2, 3, 4, 5]
    assert len(prefixo(list(range(11)), 0.5)) == 6


def test_rabisco_desenha_some_e_apaga(qapp):
    r = Rabisco()
    formas = desenho.ler_formas([{"forma": "circulo", "caixa": [100, 100, 300, 300], "texto": "isso"},
                                 {"forma": "quadrado", "caixa": [400, 400, 600, 500]},
                                 {"forma": "seta", "de": [900, 900], "para": [700, 600], "texto": "aqui"}])
    assert not r.desenhar([], (0, 0, 800, 600), 0.0) and not r.desenhar(formas, (0, 0, 0, 0), 0.0)
    assert r.desenhar(formas, (10, 20, 800, 600), 100.0)
    assert r.geometry().x() == 10 and r.width() == 800
    for agora in (100.2, 101.0, 102.5, 104.0):                     # pinta cada fase sem quebrar
        r.seguir(agora)
        imagem = QImage(r.size(), QImage.Format_ARGB32)
        imagem.fill(0)
        r.render(imagem)
    assert r.isVisible() and r.visivel(104.0)
    assert r.apagar(104.0) and not r.visivel(104.0 + 0.3)
    r.seguir(104.5)
    assert not r.isVisible() and r.formas == []
    r.desenhar(desenho.ler_formas([{"forma": "icone", "em": [500, 500], "icone": "?"}]), (0, 0, 400, 300), 0.0)
    r.seguir(1.0, pode_aparecer=False)
    assert not r.isVisible()
    r.esconder()


# ---------------- no app de verdade ----------------

class ClienteFalso:
    """Modelo falso: responde na hora e guarda as mensagens."""
    ve_imagem = True

    def __init__(self, resposta):
        self.resposta = resposta
        self.chamadas = []

    def responder(self, sistema, mensagens, imagem=None, tarefa="chat"):
        self.chamadas.append((mensagens, imagem))
        return self.resposta(mensagens) if callable(self.resposta) else self.resposta


class GravadorFalso:
    """O loopback: um tom (alguém falando) e, depois de `tom` leituras, silêncio."""

    def __init__(self, tom=3):
        self.lidas = 0
        self.tom = tom

    def __enter__(self):
        return self

    def __exit__(self, *_a):
        return False

    def record(self, numframes):
        self.lidas += 1
        time.sleep(0.002)
        if self.lidas <= self.tom:
            return (np.sin(np.arange(numframes, dtype=np.float32) / 5.0) * 0.3).reshape(-1, 1)
        return np.zeros((numframes, 1), dtype=np.float32)


class FonteFalsa:
    def __init__(self, gravador):
        self.gravador = gravador

    def recorder(self, samplerate, channels):
        return self.gravador


class VozFalsa:
    def __init__(self):
        self.vezes = 0

    def transcrever(self, wav, dica=""):
        self.vezes += 1
        return f"o professor explica a parte {self.vezes}"


def esperar(qapp, condicao, segundos=3.0):
    fim = time.monotonic() + segundos
    while time.monotonic() < fim:
        qapp.processEvents()
        if condicao():
            return True
        time.sleep(0.01)
    return False


RESUMO = ('{"titulo": "Aula de física", "resumo": "Explica a lei de Newton com exemplos.", '
          '"pontos": ["força = massa x aceleração"], "comentario": "Agora eu sei física!"}')


@pytest.fixture
def pet(qapp, tmp_path, monkeypatch):
    paths = Paths(root=tmp_path)
    store = SettingsStore(paths)
    store.update(dict(config.DEFAULT_PERMISSIONS, ia=True, ver_tela=True, videos=True, modo_teste=True))
    app = PestinhaApp(store, paths)
    falso = ClienteFalso(RESUMO)
    monkeypatch.setattr(app.visao, "cliente", lambda: falso)
    monkeypatch.setattr(visao_mod, "capturar_tela", lambda *_a, **_k: "PRINT")
    monkeypatch.setattr(visao_mod, "onde_fica", lambda *_a, **_k: (0, 0, 1000, 800))
    monkeypatch.setattr(visao_mod.senses, "get_active_title", lambda: "Aula de física - YouTube - Google Chrome")
    monkeypatch.setattr(video_ctl.senses, "get_active_title", lambda: "Aula de física - YouTube - Google Chrome")
    monkeypatch.setattr(video_ctl, "LEITURA", 0.05)
    monkeypatch.setattr(video_ctl, "TRECHO", 0.1)
    monkeypatch.setattr(video_ctl, "MIN_RESTO", 0.05)
    voz = VozFalsa()
    monkeypatch.setattr(app.video, "cliente_voz", lambda: voz)
    gravador = GravadorFalso()
    monkeypatch.setattr(video_ctl, "_som_do_computador", lambda: FonteFalsa(gravador))
    app.activity = "BROWSING"
    app.pet.show()
    yield app, falso, voz
    app.video.cancelar()
    app.visao.cancelar()
    app.rabisco.esconder()
    app.balao.esconder()
    app.tray.icon.hide()


def test_assiste_quieto_resume_e_guarda(qapp, pet):
    app, falso, voz = pet
    falas = []
    resumos = []
    app.video.fala.connect(falas.append)
    app.video.resumo.connect(resumos.append)
    assert "quietinho" in app._video_pelo_chat("assiste esse vídeo comigo")
    assert app.video.ativo and app.video.titulo == "Aula de física"
    app._atualizar_mente(time.monotonic())
    assert "ouvindo" in app.pet_state.mente
    # o serviço de voz conta a chamada antes de o trecho chegar à thread do Qt: espera o texto também
    assert esperar(qapp, lambda: voz.vezes >= 2 and app.video.pendentes == 0
                   and "professor explica" in app.video.transcricao.texto())
    app.visao._entender(mente.ler_observacao('{"resumo": "vendo aula", "comentario": "que aula chata"}'))
    assert app.balao.texto != "que aula chata"                       # assistindo: não comenta
    assert app._video_pelo_chat("resume o vídeo").startswith("Beleza")
    assert not app.video.ativo
    assert esperar(qapp, lambda: (app.video.tick(time.monotonic()), resumos)[1])
    assert "Agora eu sei física!" in falas and "força = massa x aceleração" in resumos[0]
    assert app.conhecimento.todos()[0]["titulo"] == "Aula de física"
    assert app.video.transcricao.vazia()                             # o que ouviu não fica
    pedido = falso.chamadas[-1][0][0]["content"]
    assert "professor explica" in pedido and "Aula de física" in pedido
    # e depois ele conversa sobre o que aprendeu
    mensagens = app.visao.conversa.mensagens("lembra da aula de física?", conhecimento=app.visao.conhecido(
        "lembra da aula de física?"))
    assert "lei de Newton" in mensagens[-1]["content"]


def test_silencio_encerra_sozinho(qapp, pet):
    app, _falso, _voz = pet
    falas = []
    app.video.fala.connect(falas.append)
    app.video.comecar()
    app.video.cancelar()                                              # sem nada ouvido ainda
    app.video.comecar()
    app.video.ultimo_som = time.monotonic() - app.prof["video_silencio"] - 1
    app.video._gravando = True
    app.video.transcricao = video.Transcricao()
    app.video.tick(time.monotonic())
    assert not app.video.ativo and not app.video._gravando
    assert falas and "Não ouvi ninguém" in falas[-1]                  # silêncio sem fala: nada a resumir


def test_olhada_que_ve_video_confere_o_som_e_pergunta_antes(qapp, pet):
    app, _falso, _voz = pet
    falas = []
    app.video.fala.connect(falas.append)
    app.chamado.ouvindo = app.chamado.pronto = True               # o chamado esperando o nome
    app.visao._entender(mente.ler_observacao('{"resumo": "vendo aula", "video": true}'))
    assert esperar(qapp, lambda: app.video.oferecendo())
    assert not app.video.ativo and "Quer que eu assista" in falas[-1]
    assert app.chamado.escutando                                      # a orelha já ouve o "sim"
    assert app._video_pelo_chat("que horas são?") is None             # não era resposta: vai para a IA
    assert "quietinho" in app._video_pelo_chat("pode sim")
    assert app.video.ativo and not app.video.oferecendo()
    app.video.parar()
    app.video.cancelar()
    app.visao._entender(mente.ler_observacao('{"resumo": "vendo aula", "video": true}'))
    assert not app.video.conferindo and not app.video.oferecendo()     # acabou de parar: não pergunta logo
    app.chamado.ouvindo = app.chamado.pronto = app.chamado.escutando = False


def test_parece_video_mas_sem_som_nao_pergunta(qapp, pet, monkeypatch):
    app, _falso, _voz = pet
    falas = []
    app.video.fala.connect(falas.append)
    monkeypatch.setattr(video_ctl, "_som_do_computador", lambda: FonteFalsa(GravadorFalso(tom=0)))
    app.visao._entender(mente.ler_observacao('{"resumo": "vendo aula", "video": true}'))
    assert esperar(qapp, lambda: not app.video.conferindo)
    assert not app.video.oferecendo() and falas == [] and app.video.sem_auto_ate > time.monotonic()


def test_nao_quero_que_assista_fica_quieto_um_tempo(qapp, pet):
    app, _falso, _voz = pet
    app.video.viu_video(time.monotonic())
    assert esperar(qapp, lambda: app.video.oferecendo())
    assert app._video_pelo_chat("não, valeu").startswith("Beleza")
    assert not app.video.ativo
    assert app.video.sem_auto_ate > time.monotonic() + video_ctl.ESPERA_RECUSA - 5


def test_oferta_sem_resposta_expira(qapp, pet):
    app, _falso, _voz = pet
    app.video.viu_video(time.monotonic())
    assert esperar(qapp, lambda: app.video.oferecendo())
    app.video.oferta_ate = time.monotonic() - 1
    app.video.tick(time.monotonic())
    assert not app.video.oferecendo() and app._video_pelo_chat("sim") is None


def test_assistindo_olha_a_tela_rapido_e_anota_para_o_resumo(qapp, pet):
    app, falso, _voz = pet
    app.video.comecar()
    assert app.visao.intervalo() == app.prof["visao_jogo_nuvem" if app.perms["ia_provedor"] != "ollama"
                                             else "visao_jogo"]
    app.visao.olhar(time.monotonic())
    assert esperar(qapp, lambda: not app.visao.olhando)
    assert "assistindo esse vídeo junto" in falso.chamadas[-1][0][0]["content"]
    app.visao._entender(mente.ler_observacao('{"resumo": "slide com a fórmula F = m.a", "comentario": "uau"}'))
    assert app.video.transcricao.telas[-1][1] == "slide com a fórmula F = m.a"
    assert app.balao.texto != "uau"
    app.video.transcricao.adicionar(0, "a força é massa vezes aceleração")
    app.video.parar()
    assert esperar(qapp, lambda: (app.video.tick(time.monotonic()), not app.video.resumindo
                                  and not app.video.finalizando)[1])
    pedido = falso.chamadas[-1][0][0]["content"]
    assert "slide com a fórmula F = m.a" in pedido and "O que você viu na tela" in pedido


def test_pergunta_falada_pede_para_oferecer_mais(qapp, pet):
    app, falso, _voz = pet
    app.apply_perms({"conversa": True})
    falso.resposta = "fica no menu Arquivo. quer saber mais alguma coisa?"
    assert app.visao.perguntar("como eu exporto o arquivo?", por_voz=True)
    assert esperar(qapp, lambda: not app.visao.respondendo)
    assert "quer saber mais alguma coisa" in falso.chamadas[-1][0][-1]["content"]
    assert app.visao.perguntar("e como salvo?")
    assert esperar(qapp, lambda: not app.visao.respondendo)
    assert "Ela falou isso em voz alta" not in falso.chamadas[-1][0][-1]["content"]


def test_sem_permissao_nao_ouve(qapp, pet):
    app, _falso, _voz = pet
    app.apply_perms({"videos": False})
    assert app._video_pelo_chat("assiste esse vídeo comigo") is None
    assert "desligado" in app.video.comecar() and not app.video.ativo


def test_panico_joga_fora_o_que_ouviu(qapp, pet):
    app, _falso, voz = pet
    app.video.comecar()
    assert esperar(qapp, lambda: voz.vezes >= 1 and not app.video.transcricao.vazia())
    app.panic()
    assert not app.video.ocupado() and app.video.transcricao.vazia()


def test_som_que_falha_avisa_e_para(qapp, pet, monkeypatch):
    app, _falso, _voz = pet

    def sem_som():
        raise video_ctl.ErroIA("sem loopback")
    monkeypatch.setattr(video_ctl, "_som_do_computador", sem_som)
    avisos = []
    app.video.aviso.connect(avisos.append)
    app.video.comecar()
    assert esperar(qapp, lambda: not app.video.ativo) and avisos == ["sem loopback"]


def test_chat_com_desenho_rabisca_no_monitor_do_print(qapp, pet):
    app, falso, _voz = pet
    falso.resposta = ('O salvar fica aqui em cima!\nDESENHAR: [{"forma": "circulo", "caixa": [0, 0, 100, 100], '
                      '"texto": "salvar"}]')
    desenhos = []
    app.visao.desenho.connect(lambda formas, onde: desenhos.append((formas, onde)))
    assert app.visao.perguntar("onde fica o botão de salvar?")
    assert esperar(qapp, lambda: not app.visao.respondendo)
    mensagens, imagem = falso.chamadas[-1]
    assert imagem == "PRINT" and "DESENHAR:" in mensagens[-1]["content"]
    assert desenhos and desenhos[0][1] == (0, 0, 1000, 800) and desenhos[0][0][0].texto == "salvar"
    assert app.rabisco.visivel(time.monotonic())
    assert "DESENHAR" not in app.visao.conversa.turnos[-1]["content"]
    app.fechar_projecao()                                             # mexeu nele: o desenho some
    assert not app.rabisco.visivel(time.monotonic() + 0.5)


def test_sem_permissao_de_desenhar_nao_pede_nem_desenha(qapp, pet):
    app, falso, _voz = pet
    app.apply_perms({"desenhar": False})
    falso.resposta = 'Tá aqui.\nDESENHAR: [{"forma": "icone", "em": [5, 5]}]'
    assert app.visao.perguntar("onde fica?")
    assert esperar(qapp, lambda: not app.visao.respondendo)
    assert "DESENHAR:" not in falso.chamadas[-1][0][-1]["content"]
    assert not app.rabisco.visivel(time.monotonic())
    assert app.visao.conversa.turnos[-1]["content"] == "Tá aqui."


def test_comentario_da_olhada_vem_com_desenho(qapp, pet):
    app, falso, _voz = pet
    app.apply_perms({"videos": False})
    falso.resposta = ('{"resumo": "vendo código", "comentario": "olha esse erro!", "erro": 0.9, '
                      '"desenhar": [{"forma": "seta", "de": [100, 100], "para": [500, 400]}]}')
    app.visao.olhar(time.monotonic())
    assert esperar(qapp, lambda: not app.visao.olhando and app.rabisco.visivel(time.monotonic()))
    assert app.rabisco.formas[0][0].tipo == "seta"
    assert math.isclose(app.rabisco.width(), 1000)
