"""
Visão e conversa pela IA: o texto do modelo, os clientes (com SDK falsa, sem rede) e o controlador
dentro do app de verdade (Qt offscreen, pasta temporária). Nenhum teste chama uma API real.
"""

import os
import sys
import time
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from pestinha import config  # noqa: E402
from pestinha.app import PestinhaApp  # noqa: E402
from pestinha.core.nervous_system import SENSORY_SPEC  # noqa: E402
from pestinha.ia import mente, provedores  # noqa: E402
from pestinha.mind import visao as visao_mod  # noqa: E402
from pestinha.paths import Paths  # noqa: E402
from pestinha.settings_store import SettingsStore  # noqa: E402

RESPOSTA_OK = ('Claro! ```json\n{"resumo": "programando em Python", "comentario": "Esse bug de novo?", '
               '"graca": 0.1, "erro": 0.9, "foco": 2, "novidade": "muito"}\n```')


# ---------------- mente: o texto do modelo ----------------

def test_observacao_tolera_texto_em_volta_e_valores_ruins():
    obs = mente.ler_observacao(RESPOSTA_OK)
    assert obs.resumo == "programando em Python"
    assert obs.comentario == "Esse bug de novo?"
    assert obs.sinais == {"VISAO_GRACA": 0.1, "VISAO_ERRO": 0.9, "VISAO_FOCO": 1.0, "VISAO_NOVO": 0.0}


@pytest.mark.parametrize("texto", ["", "não sei", "{quebrado", '["lista"]', None])
def test_observacao_sem_json_nao_inventa_fala(texto):
    obs = mente.ler_observacao(texto)
    assert obs.comentario == "" and obs.sinais == {}


def test_sinal_booleano_nao_vira_numero():
    assert mente.ler_observacao('{"erro": true}').sinais["VISAO_ERRO"] == 0.0


def test_todo_sinal_da_ia_e_um_canal_da_rede():
    assert set(mente.SINAIS.values()) | {"CONVERSA"} <= set(SENSORY_SPEC)


def test_fala_vira_uma_linha_curta():
    fala = mente.limpar_fala('  "oi\n\n' + "a" * 500 + '"  ')
    assert "\n" not in fala and len(fala) == mente.MAX_COMENTARIO and fala.endswith("…")


def test_conversa_guarda_pouco_e_sem_o_contexto_da_tela():
    conversa = mente.Conversa()
    msgs = conversa.mensagens("oi", contexto="lendo e-mail")
    assert "lendo e-mail" in msgs[-1]["content"]
    for i in range(20):
        conversa.registrar(f"pergunta {i}", f"resposta {i}")
    assert len(conversa.turnos) == mente.MAX_TURNOS
    assert all("lendo e-mail" not in t["content"] for t in conversa.turnos)
    assert conversa.turnos[0]["role"] == "user"


def test_persona_entra_no_prompt():
    assert "pirata" in mente.prompt_sistema("Bryan", "Você é um pirata.")
    assert mente.PERSONA_PADRAO in mente.prompt_sistema("Bryan")


# ---------------- provedores (SDK falsa) ----------------

def test_sem_chave_explica_qual_variavel(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(provedores.ErroIA, match="Salvar chave"):
        provedores.criar_cliente("openai")


def test_provedor_desconhecido_vira_o_padrao_e_modelo_vazio_o_do_provedor():
    assert provedores.info("xyz") is provedores.PROVEDORES[provedores.PROVEDOR_PADRAO]
    assert provedores.modelo_de("ollama", "  ") == provedores.PROVEDORES["ollama"]["modelo"]
    assert provedores.modelo_de("ollama", "gemma3") == "gemma3"


def test_ollama_nao_precisa_de_chave(monkeypatch):
    cliente = provedores.criar_cliente("ollama")
    assert cliente.local and cliente.ve_imagem


class _Chamadas:
    """Guarda os argumentos da chamada e devolve a resposta pronta."""

    def __init__(self, resposta):
        self.resposta = resposta
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        return self.resposta


def test_claude_manda_o_print_e_le_o_texto(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "teste")
    cliente = provedores.criar_cliente("claude")
    resposta = SimpleNamespace(stop_reason="end_turn",
                               content=[SimpleNamespace(type="text", text=" oi ")])
    chamadas = _Chamadas(resposta)
    cliente.cliente = SimpleNamespace(beta=SimpleNamespace(messages=chamadas))
    assert cliente.responder("sistema", [{"role": "user", "content": "o que é isso?"}], imagem="AAAA") == "oi"
    ultima = chamadas.kwargs["messages"][-1]["content"]
    assert ultima[0]["source"]["data"] == "AAAA" and ultima[1]["text"] == "o que é isso?"
    assert chamadas.kwargs["model"] == provedores.PROVEDORES["claude"]["modelo"]
    assert chamadas.kwargs["system"] == "sistema"


def test_claude_recusa_vira_erro_explicado(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "teste")
    cliente = provedores.criar_cliente("claude")
    cliente.cliente = SimpleNamespace(beta=SimpleNamespace(
        messages=_Chamadas(SimpleNamespace(stop_reason="refusal", content=[]))))
    with pytest.raises(provedores.ErroIA, match="não responder"):
        cliente.responder("s", [{"role": "user", "content": "x"}])


def test_deepseek_nao_recebe_imagem(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "teste")
    cliente = provedores.criar_cliente("deepseek")
    resposta = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="beleza"))])
    chamadas = _Chamadas(resposta)
    cliente.cliente = SimpleNamespace(chat=SimpleNamespace(completions=chamadas))
    assert cliente.responder("s", [{"role": "user", "content": "x"}], imagem="AAAA") == "beleza"
    assert chamadas.kwargs["messages"][0] == {"role": "system", "content": "s"}
    assert chamadas.kwargs["messages"][-1]["content"] == "x"           # sem o print


# ---------------- controlador, dentro do app ----------------

@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    return app


class ClienteFalso:
    """Responde na hora (na thread do controlador) e conta as chamadas."""

    ve_imagem = True

    def __init__(self, resposta=RESPOSTA_OK, erro=None):
        self.resposta, self.erro = resposta, erro
        self.chamadas = []

    def responder(self, sistema, mensagens, imagem=None):
        self.chamadas.append((sistema, mensagens, imagem))
        if self.erro:
            raise self.erro
        return self.resposta


@pytest.fixture
def pet(qapp, tmp_path, monkeypatch):
    paths = Paths(root=tmp_path)
    store = SettingsStore(paths)
    store.update(dict(config.DEFAULT_PERMISSIONS, ia=True, ver_tela=True, modo_teste=True))
    app = PestinhaApp(store, paths)
    falso = ClienteFalso()
    monkeypatch.setattr(app.visao, "cliente", lambda: falso)
    monkeypatch.setattr(visao_mod, "capturar_tela", lambda *_a, **_k: "PRINT")
    monkeypatch.setattr(visao_mod.senses, "get_active_title", lambda: "main.py - pestinha")
    app.activity = "PROGRAMMING"
    app.pet.show()
    yield app, falso
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


def test_olhada_vira_sinal_na_rede_e_comentario_no_balao(qapp, pet):
    app, falso = pet
    app.visao.tick(time.monotonic())
    assert esperar(qapp, lambda: not app.visao.olhando)
    _sistema, mensagens, imagem = falso.chamadas[0]
    assert imagem == "PRINT" and "main.py - pestinha" in mensagens[0]["content"]
    assert app.senses.pulse["VISAO_ERRO"] == pytest.approx(0.9)
    assert app.balao.texto == "Esse bug de novo?"
    assert app.visao.ultimo_resumo == "programando em Python"


def test_sem_comentarios_ele_so_sente(qapp, pet):
    app, _falso = pet
    app.apply_perms({"comentarios": False})
    app.visao.tick(time.monotonic())
    assert esperar(qapp, lambda: not app.visao.olhando)
    assert app.senses.pulse["VISAO_ERRO"] > 0.5 and app.balao.texto == ""


def test_intervalo_entre_olhadas(qapp, pet):
    app, falso = pet
    agora = time.monotonic()
    app.visao.tick(agora)
    assert esperar(qapp, lambda: not app.visao.olhando)
    app.visao.tick(agora + 1.0)
    assert len(falso.chamadas) == 1
    app.visao.tick(agora + app.prof["visao_intervalo"] + 0.1)
    assert esperar(qapp, lambda: len(falso.chamadas) == 2)


@pytest.mark.parametrize("mudanca", [{"ia": False}, {"ver_tela": False}])
def test_sem_permissao_nada_sai_do_computador(qapp, pet, mudanca):
    app, falso = pet
    app.apply_perms(mudanca)
    app.visao.tick(time.monotonic() + 1e6)
    app.visao.olhar_agora()
    qapp.processEvents()
    assert falso.chamadas == []


def test_nao_olha_com_voce_longe_dormindo_ou_escondido(qapp, pet):
    app, falso = pet
    app.activity = "AWAY"
    app.visao.tick(time.monotonic() + 1e6)
    app.activity = "PROGRAMMING"
    app.sleep.asleep = True
    app.visao.tick(time.monotonic() + 1e6)
    app.sleep.asleep = False
    app.toggle_hidden()
    app.visao.tick(time.monotonic() + 1e6)
    assert falso.chamadas == []


def test_panico_descarta_a_resposta_a_caminho(qapp, pet):
    app, falso = pet
    geracao = app.visao.geracao
    app.panic()
    app.visao._ao_pronto("observacao", RESPOSTA_OK, geracao)     # chegou depois do pânico
    assert app.senses.pulse["VISAO_ERRO"] == 0.0 and app.balao.texto == ""


def test_falha_avisa_uma_vez_e_espera(qapp, pet):
    app, falso = pet
    falso.erro = provedores.ErroIA("falta a chave")
    avisos = []
    app.visao.aviso.connect(avisos.append)
    agora = time.monotonic()
    app.visao.tick(agora)
    assert esperar(qapp, lambda: not app.visao.olhando and avisos)
    assert app.visao.proxima >= agora + visao_mod.ESPERA_APOS_ERRO
    app.visao.olhar(agora + 1)
    assert esperar(qapp, lambda: not app.visao.olhando)
    assert avisos == ["falta a chave"]


def test_conversa_responde_e_conta_como_atencao(qapp, pet):
    app, falso = pet
    falso.resposta = "Oi! Tô vendo seu código."
    respostas = []
    app.visao.resposta.connect(respostas.append)
    app.visao.ultimo_resumo = "programando"
    contato = app.drives.contact
    assert app.visao.perguntar("o que acha?")
    assert esperar(qapp, lambda: respostas)
    assert respostas == ["Oi! Tô vendo seu código."]
    assert app.balao.texto == respostas[0]
    assert app.senses.pulse["CONVERSA"] > 0.5 and app.drives.contact <= contato
    _s, mensagens, imagem = falso.chamadas[-1]
    assert imagem == "PRINT" and "programando" in mensagens[-1]["content"]
    assert app.visao.conversa.turnos[-2]["content"] == "o que acha?"


def test_conversa_sem_ver_a_tela_nao_manda_print(qapp, pet):
    app, falso = pet
    app.apply_perms({"ver_tela": False})
    assert app.visao.perguntar("oi")
    assert esperar(qapp, lambda: not app.visao.respondendo)
    assert falso.chamadas[-1][2] is None


def test_conversa_desligada_nao_pergunta(qapp, pet):
    app, falso = pet
    app.apply_perms({"conversa": False})
    assert not app.visao.perguntar("oi") and falso.chamadas == []


def test_balao_some_com_o_pet(qapp, pet):
    app, _falso = pet
    app.balao.mostrar("oi", time.monotonic())
    app.balao.seguir(300, 300, time.monotonic())
    assert app.balao.isVisible()
    app.toggle_hidden()
    assert not app.balao.isVisible()


def test_tela_de_configuracoes_trava_o_que_depende_da_ia(qapp, tmp_path):
    from pestinha.ui.ui import SettingsDialog
    perms = dict(config.DEFAULT_PERMISSIONS)
    dialogo = SettingsDialog(perms, Paths(root=tmp_path), first_run=False)
    assert not dialogo.boxes["ver_tela"].isEnabled() and not dialogo.provedor_combo.isEnabled()
    dialogo.boxes["ia"].setChecked(True)
    assert dialogo.boxes["ver_tela"].isEnabled() and not dialogo.boxes["comentarios"].isEnabled()
    dialogo.provedor_combo.setCurrentIndex(dialogo.provedor_combo.findData("ollama"))
    assert dialogo.perms["ia_provedor"] == "ollama" and "ollama pull" in dialogo.provedor_dica.text()
    dialogo.close()


def test_permissoes_de_ia_comecam_desligadas():
    assert config.DEFAULT_PERMISSIONS["ia"] is False and config.DEFAULT_PERMISSIONS["ver_tela"] is False


def test_personas_carregam(tmp_path):
    paths = Paths()
    for pet_id in ("bryan", "jorge"):
        assert config.load_pet(paths, pet_id)["persona"]
    assert "NUNCA vende" in config.load_pet(paths, "jorge")["persona"]
