"""
Animações da mente: o corpo mostra o que a IA e a voz estão fazendo (olhando, pensando, pesquisando,
ouvindo, jogo) e dá o pop quando o balão aparece. Tudo entra e sai suave, e nada muda quando a mente
está parada (o visual de sempre continua idêntico).
"""
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PySide6.QtGui import QImage, QPainter  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from pestinha.body import animacoes  # noqa: E402
from pestinha.body.animacoes import (  # noqa: E402
    ATIVIDADES, Animacoes, ease_out_back, ease_out_cubic, ida_e_volta, mola,
)
from pestinha.body.desenho_rosto import PADRAO, draw_face, draw_mente  # noqa: E402
from pestinha.body.pet import CX, CY, WIN  # noqa: E402
from pestinha.core.emotion import EYE_SHAPES  # noqa: E402


def rodar(anim, ativas, de, ate, passo=0.016):
    t = de
    while t < ate:
        t += passo
        anim.passo(t, ativas)
    return t


def pintar(mente=None, agora=0.0, ouvindo=False):
    QApplication.instance() or QApplication([])
    img = QImage(WIN, WIN, QImage.Format_ARGB32)
    img.fill(0)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    p.translate(CX, CY)
    if mente is not None:
        draw_mente(p, mente, agora, PADRAO, frente=False)
    draw_face(p, dict(EYE_SHAPES["observando"]), (0.0, 0.0), 1.0, "observando", aparencia=PADRAO,
              ouvindo=ouvindo, mente=mente, agora=agora)
    if mente is not None:
        draw_mente(p, mente, agora, PADRAO, frente=True)
    p.end()
    return img


def test_curvas_comecam_e_terminam_no_lugar():
    for curva in (ease_out_cubic, ease_out_back):
        assert abs(curva(0.0)) < 1e-9 and abs(curva(1.0) - 1.0) < 1e-9
    assert max(ease_out_back(i / 100) for i in range(101)) > 1.0       # o pop passa do alvo
    assert ida_e_volta(0.0, 2.0) == 0.0 and abs(ida_e_volta(1.0, 2.0) - 1.0) < 1e-9
    assert mola(0.0) == 0.0 and abs(mola(5.0)) < 1e-6                   # começa parada e assenta


def test_atividade_entra_suave_e_sai_mais_rapido():
    a = Animacoes()
    a.passo(0.0, set())
    rodar(a, {"olhando"}, 0.0, 0.05)
    assert 0.0 < a.nivel("olhando") < 0.9                                # não aparece de estalo
    t = rodar(a, {"olhando"}, 0.05, 0.5)
    assert a.nivel("olhando") > 0.99
    rodar(a, set(), t, t + animacoes.SAIDA + 0.05)
    assert a.nivel("olhando") < 0.05

    b = Animacoes()
    b.passo(0.0, set())
    rodar(b, {"pensando"}, 0.0, 0.1)
    subiu = b.nivel("pensando")
    c = Animacoes()
    c.niveis["pensando"] = 1.0
    c.passo(0.0, {"pensando"})
    rodar(c, set(), 0.0, 0.1)
    assert 1.0 - c.nivel("pensando") > subiu                             # sair é mais rápido que entrar


def test_mente_parada_nao_muda_nada():
    a = Animacoes()
    pose = a.pose(123.0)
    assert (pose.escala_x, pose.escala_y, pose.inclinacao, pose.olho_x, pose.olho_y) == (1, 1, 0, 1, 1)
    assert pose.olhar is None
    assert pintar(a, 123.0) == pintar(None)


def test_parar_some_com_tudo():
    a = Animacoes()
    a.niveis = dict.fromkeys(ATIVIDADES, 1.0)
    a.falar(0.0, "oi")
    a.parar()
    assert all(v == 0.0 for v in a.niveis.values()) and a.falando(0.01) == 0.0


def test_pop_achata_depois_estica_e_assenta():
    a = Animacoes()
    a.falar(10.0, "Esse bug de novo?")
    ys = [a.pose(10.0 + i * 0.01).escala_y for i in range(80)]
    assert min(ys[:8]) < 1.0                                             # antecipa: achata
    assert max(ys[8:30]) > 1.0                                           # depois estica
    assert abs(a.pose(10.0 + animacoes.DURACAO_POP + 0.01).escala_y - 1.0) < 1e-9


def test_olhos_falam_enquanto_o_balao_digita():
    a = Animacoes()
    texto = "Olha só que coisa"
    a.falar(0.0, texto)
    assert a.letras_visiveis(0.0, texto) == 0
    assert 0 < a.letras_visiveis(a.fala_ate / 2, texto) < len(texto)
    assert a.letras_visiveis(a.fala_ate, texto) == len(texto)
    assert any(a.pose(t / 100).olho_y < 0.95 for t in range(5, 50))
    assert a.falando(a.fala_ate + 0.01) == 0.0
    a.falar(0.0, "x" * 1000)
    assert a.fala_ate <= animacoes.FALA_MAX                              # texto enorme não fala para sempre


def test_quem_manda_no_olhar():
    a = Animacoes()
    a.niveis.update(pensando=1.0)
    olhar, peso = a.olhar(0.0)
    assert peso == 1.0 and olhar[1] < 0                                  # detetive: olha para cima, pensando
    a.niveis.update(olhando=1.0)
    xs = [a.olhar(t / 10)[0][0] for t in range(20)]
    assert min(xs) < -0.5 and max(xs) > 0.5                              # lendo: varre de um lado ao outro
    a.niveis.update(pesquisando=1.0)
    xs = [a.olhar(t / 20)[0][0] for t in range(20)]
    assert min(xs) < -0.5 and max(xs) > 0.5                              # IA vilã: calcula rápido
    a.niveis.update(projetando=1.0)
    assert a.olhar(0.0)[0] == (0.0, -1.0)                                # olha para a projeção


def test_ia_vila_fica_brava_e_vermelha():
    from pestinha.body.desenho_fantasias import VERMELHO, aparencia_da_mente
    a = Animacoes()
    a.niveis["pesquisando"] = 1.0
    pose = a.pose(0.0)
    assert pose.forma == "bravo" and pose.peso_forma == 1.0
    vila = aparencia_da_mente(PADRAO, a)
    assert vila.olho.name() == VERMELHO.name() and vila.moldura != PADRAO.moldura
    a.niveis["pesquisando"] = 0.5                                        # no meio do caminho: laranja, não marrom
    meio = aparencia_da_mente(PADRAO, a).olho
    assert meio.hsvSaturationF() > 0.6 and meio.valueF() > 0.7


def test_oculos_3d_tiram_os_oculos_do_pet():
    from pestinha.body.desenho_fantasias import aparencia_da_mente
    from pestinha.body.desenho_rosto import aparencia_de
    jorge = aparencia_de({"acessorios": {"oculos": "#222222", "gravata": "#b3261e"}})
    a = Animacoes()
    assert aparencia_da_mente(jorge, a) is jorge                         # sem mente: o pet de sempre
    a.niveis["jogo"] = 1.0
    assert [n for n, _ in aparencia_da_mente(jorge, a).acessorios] == ["gravata"]


def test_pipoca_voa_e_ele_mastiga():
    a = Animacoes()
    assert a.pipoca(0.1) is not None and a.pipoca(animacoes.VOO_PIPOCA + 0.2) is None
    assert a.mastigando(animacoes.VOO_PIPOCA + animacoes.MASTIGA / 4) > 0.5
    a.niveis["jogo"] = 1.0
    assert a.pose(animacoes.VOO_PIPOCA + animacoes.MASTIGA / 4).olho_y < a.pose(animacoes.VOO_PIPOCA + 1.2).olho_y


def test_orelha_vira_para_a_frente():
    a = Animacoes()
    assert a.orelha() == 0.0
    a.niveis["ouvindo"] = 0.5
    meio = a.orelha()
    a.niveis["ouvindo"] = 1.0
    assert 0.0 < meio and abs(a.orelha() - 1.0) < 1e-9
    assert max(animacoes.ease_out_back(i / 50, 2.2) for i in range(51)) > 1.0      # passa um pouco e volta


def test_fumaca_do_cachimbo_sobe():
    a = Animacoes()
    for subida, alfa in a.fumaca(0.7):
        assert 0.0 <= subida <= 1.0 and 0.0 <= alfa <= 1.0
    assert len({round(s, 3) for s, _ in a.fumaca(0.7)}) == animacoes.BAFORADAS


def test_ouvindo_inclina_e_as_ondas_pulsam():
    a = Animacoes()
    a.niveis["ouvindo"] = 1.0
    assert a.pose(0.0).inclinacao == animacoes.INCLINACAO_OUVINDO
    assert pintar(a, 0.1) != pintar(a, 0.3)                              # as ondinhas andam


def test_cada_atividade_aparece_no_desenho():
    vazio = pintar(None)
    for nome in ATIVIDADES:
        a = Animacoes()
        a.niveis[nome] = 1.0
        assert pintar(a, 0.3) != vazio, nome


def test_app_conta_ao_rosto_o_que_a_mente_faz():
    from pestinha.app import PestinhaApp
    st = SimpleNamespace(mente=frozenset(), anim=Animacoes())
    visao = SimpleNamespace(olhando=True, respondendo=False, pesquisando=False, buscando_imagem=True,
                            em_jogo=lambda: False)
    holograma = SimpleNamespace(visivel=lambda agora: True)
    app = SimpleNamespace(visao=visao, voz=SimpleNamespace(transcrevendo=True), pet_state=st, holograma=holograma)
    PestinhaApp._atualizar_mente(app, 5.0)
    assert st.mente == {"olhando", "pesquisando", "projetando"}             # a vilã toma o lugar do detetive
    visao.olhando = False
    PestinhaApp._atualizar_mente(app, 6.0)
    assert st.anim.entendi_desde == 6.0 and "olhando" not in st.mente    # a olhada voltou: entendi
