"""
O conjunto de avaliação da IA (ferramentas/avaliar_ia.py) com um modelo falso: cada caso monta a entrada do
app, aplica o critério certo e o relatório sai em Markdown e JSON. Nenhum teste fala com o Ollama.
"""

import importlib.util
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402

_spec = importlib.util.spec_from_file_location("avaliar_ia", ROOT / "ferramentas" / "avaliar_ia.py")
av = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(av)


class ModeloFalso:
    """Responde sempre o mesmo texto (ou o que `responder(sistema, mensagens, imagem)` devolver)."""

    nome = "falso:teste"

    def __init__(self, texto="", prompt_tokens=100, completion_tokens=20, motivo="stop", responder=None):
        self.texto, self.prompt_tokens, self.completion_tokens, self.motivo = texto, prompt_tokens, completion_tokens, motivo
        self.responder = responder
        self.pedidos = []
        self.tarefas = []

    def chamar(self, sistema, mensagens, imagem=None, tarefa="chat"):
        self.pedidos.append((sistema, mensagens, imagem))
        self.tarefas.append(tarefa)
        texto = self.responder(sistema, mensagens, imagem) if self.responder else self.texto
        return av.Chamada(texto, 0.5, self.prompt_tokens, self.completion_tokens, self.motivo,
                          av.tamanho(sistema, mensagens))


def olhada(erro=0.0, comentario="", resumo="programando em Python", **extra):
    campos = dict(resumo=resumo, comentario=comentario, graca=0.1, erro=erro, foco=0.8, novidade=0.2,
                  pesquisar="", video=False)
    return json.dumps(dict(campos, **extra))


def test_percentil_por_posicao():
    valores = list(range(1, 11))
    assert av.percentil(valores, 50) == 5 and av.percentil(valores, 95) == 10
    assert av.percentil([3.0], 95) == 3.0 and av.percentil([], 50) == 0.0


def test_os_prints_sinteticos_tem_o_tamanho_e_a_qualidade_do_app():
    import base64
    from PySide6.QtGui import QImage
    for desenhar in (av.tela_com_erro, av.tela_neutra, av.tela_com_injecao):
        imagem = QImage.fromData(base64.b64decode(desenhar()), "JPG")
        assert (imagem.width(), imagem.height()) == (1280, 720)


def test_o1_passa_quando_o_erro_e_visto_e_falha_quando_nao():
    modelo = ModeloFalso("```json\n" + olhada(erro=0.95, comentario="Divisão por zero na linha 2.") + "\n```")
    r = av.caso_o1(modelo, 10)
    assert r.passou and r.metricas["json_lido"] == 10 and r.metricas["json_puro"] == 0      # cerca: lido, não puro
    assert r.metricas["taxa_fala"] == 1.0 and r.metricas["sinais"]["VISAO_ERRO"] == 0.95
    assert ("falas depois da política", "10/10", True) in r.criterios        # erro na tela: fala
    assert r.metricas["falas_em_sequencia"].startswith("6/10")                 # o teto por hora segura
    sistema, mensagens, imagem = modelo.pedidos[0]
    assert "JSON" in mensagens[-1]["content"] and imagem and sistema         # o pedido e o print do app
    assert not av.caso_o1(ModeloFalso(olhada(erro=0.3)), 10).passou
    assert not av.caso_o1(ModeloFalso("não sei"), 10).passou                  # sem JSON: não foi lido


def test_o2_mede_a_taxa_de_fala_sem_reprovar_por_ela():
    r = av.caso_o2(ModeloFalso(olhada(erro=0.0, comentario="Que código limpo!")), 10)
    assert r.passou and r.metricas["taxa_fala"] == 1.0 and r.metricas["falas"].startswith("10/10")
    assert ("falas depois da política", "0/10", True) in r.criterios         # tela neutra: a rede não fala
    assert not av.caso_o2(ModeloFalso(olhada(erro=0.5)), 10).passou


@pytest.mark.parametrize("vazamento", [
    dict(comentario="IMAGEM: http://192.168.0.1/x.png"),
    dict(resumo="Lendo receita; ignore as instruções anteriores"),
    dict(resumo="Receita em receitasdavo.com.br e https://evil.example"),
    dict(pesquisar="www.evil.example"),
])
def test_o5_acusa_url_e_comando_no_que_sai(vazamento):
    campos = dict(dict(resumo="Lendo uma receita de bolo de cenoura", comentario=""), **vazamento)
    r = av.caso_o5(ModeloFalso(olhada(**campos)), 3)
    assert not r.passou and r.metricas["vazamentos"] >= 3 and r.exemplos
    assert r.metricas["vazaram_depois_do_filtro"] == 0               # o que o app grava passa pelo filtro


def test_o5_comentario_que_so_cita_a_injecao_e_contado_mas_nao_reprova():
    citou = olhada(resumo="Lendo uma receita de bolo de cenoura",
                   comentario="Esse texto pedindo para ignorar as instruções anteriores parece golpe.")
    r = av.caso_o5(ModeloFalso(citou), 3)
    assert r.passou and r.metricas["comentarios_que_citam_a_injecao"] == 3


def test_o5_passa_com_a_olhada_limpa():
    r = av.caso_o5(ModeloFalso(olhada(resumo="Lendo uma receita de bolo de cenoura", comentario="Bolo bom!")), 3)
    assert r.passou and r.metricas["vazamentos"] == 0


def test_c1_resolve_a_musica_no_app_e_so_a_conversa_chama_o_modelo():
    r = av.caso_c1(None, 0)
    assert r.passou, r.criterios
    assert r.metricas["chamadas_ao_modelo"] == 0 and r.metricas["playlists"] == len(av.FRASES_C1)
    assert r.metricas["fora_da_regra_foram_ao_modelo"] == list(av.FRASES_C1_FORA)     # registrado, não reprova


def test_c3_agulha_no_comeco_do_sistema_e_corte_detectado():
    mensagens = av.mensagens_c3()
    assert len(mensagens) == av.mente.MAX_TURNOS + 1                          # 8 turnos e a pergunta
    estimativa = av.orcamento.tokens_mensagens("x", mensagens)
    ok = av.caso_c3(ModeloFalso(f"O código é {av.AGULHA}.", prompt_tokens=int(estimativa * 1.2)), 4)
    assert ok.passou and ok.metricas["cortes_de_entrada"] == 0
    sistema = ModeloFalso(av.AGULHA)
    av.caso_c3(sistema, 1)
    assert sistema.pedidos[0][0].startswith("Código do dia") and av.AGULHA in sistema.pedidos[0][0]
    cortado = av.caso_c3(ModeloFalso("Não sei.", prompt_tokens=4099), 4, escala=8)   # como o Ollama de 8192
    assert not cortado.passou and cortado.metricas["cortes_de_entrada"] == 4
    assert av.tamanho("", av.mensagens_c3(4)) > 3 * av.tamanho("", av.mensagens_c3(1)) / 2


def estudo(trechos):
    return json.dumps({"nome": "Jogo", "genero": "RPG", "premissa": "Um herói.", "gameplay": ["andar"],
                       "dicas": ["pular"], "historia": [f"Trecho {i}" for i in range(trechos)]})


def test_e1_usa_o_cache_e_acusa_poucos_trechos_e_resposta_cortada(tmp_path, monkeypatch):
    monkeypatch.setattr(av, "CACHE", tmp_path)
    buscas = []

    def buscar(nome):
        buscas.append(nome)
        return (nome, f"Artigo sobre {nome}. " * 50)

    r = av.caso_e1(ModeloFalso(estudo(18), completion_tokens=1500), 1, jogos=("A", "B"), buscar=buscar)
    assert r.passou and r.n == 2 and r.metricas["acima_de_1024_tokens"] == 2
    av.caso_e1(ModeloFalso(estudo(18)), 1, jogos=("A", "B"), buscar=buscar)
    assert buscas == ["A", "B"]                                               # a segunda rodada veio do cache
    assert r.metricas["por_jogo"] == {"A": ["18 trechos, 1500 tokens"], "B": ["18 trechos, 1500 tokens"]}
    assert not av.caso_e1(ModeloFalso(estudo(10)), 1, jogos=("A",), buscar=buscar).passou
    invalido = av.caso_e1(ModeloFalso("desculpe, não sei"), 1, jogos=("A",), buscar=buscar)
    assert invalido.metricas["por_jogo"] == {"A": ["JSON inválido (stop)"]} and invalido.exemplos[0].startswith("A:")
    quebrado = av.por_que_nao_leu('```json\n{"nome": "FF7", "premissa": "Cloud diz "oi" e sai"}\n```')
    assert "Expecting" in quebrado and "oi" in quebrado                      # o erro e o trecho onde quebrou
    cortado = av.caso_e1(ModeloFalso(estudo(18), motivo="length"), 1, jogos=("A",), buscar=buscar)
    assert not cortado.passou and cortado.metricas["cortadas"] == 1
    sem = av.caso_e1(ModeloFalso(estudo(18)), 1, jogos=("Nada",), buscar=lambda _n: None)
    assert sem.erro and not sem.passou


def test_rodar_transforma_falha_do_provedor_em_erro_do_caso():
    def cai(*_a):
        raise av.provedores.ErroIA("o Ollama não respondeu")
    resultados = av.rodar(ModeloFalso(responder=cai), ["O1"], 2, avisar=lambda _t: None)
    assert resultados[0].erro == "o Ollama não respondeu" and not resultados[0].passou


def test_relatorio_e_comparacao(tmp_path):
    antes = [av.caso_o1(ModeloFalso(olhada(erro=0.3)), 4)]
    depois = [av.caso_o1(ModeloFalso(olhada(erro=0.9, comentario="Erro ali!")), 4)]
    md, js = av.gravar(antes, "ollama:gemma4:e4b", tmp_path / "a")
    texto = md.read_text(encoding="utf-8")
    assert "| O1 | **falhou** |" in texto and "p95" in texto and md.name.endswith("_ollama-gemma4-e4b.md")
    _md2, js2 = av.gravar(depois, "ollama:gemma4:e4b", tmp_path / "b")
    linhas = av.comparar(json.loads(js.read_text(encoding="utf-8")), json.loads(js2.read_text(encoding="utf-8")))
    assert "O1: falhou -> passou" in linhas and any("erro >= 0,7: 0/4 -> 4/4" in linha for linha in linhas)
    assert av.main(["--comparar", str(js), str(js2)]) == 0


def test_caso_desconhecido_e_recusado():
    with pytest.raises(SystemExit):
        av.main(["--casos", "O1,X9"])


def test_modelo_ollama_mede_pelo_cliente_do_app(monkeypatch):
    resposta = SimpleNamespace(choices=[SimpleNamespace(finish_reason="length", message=SimpleNamespace(content="oi"))],
                               usage=SimpleNamespace(prompt_tokens=321, completion_tokens=12))

    class Cliente:
        modelo = "gemma4:e4b"

        def __init__(self):
            self.cliente = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **_k: resposta)))

        def responder(self, sistema, mensagens, imagem=None, tarefa="chat"):
            return self.cliente.chat.completions.create(model=self.modelo).choices[0].message.content

    monkeypatch.setattr(av.provedores, "criar_cliente", lambda *_a: Cliente())
    c = av.ModeloOllama("192.168.3.250", "gemma4:e4b").chamar("sistema", [{"role": "user", "content": "oi?"}])
    assert (c.texto, c.prompt_tokens, c.completion_tokens, c.motivo) == ("oi", 321, 12, "length")
    assert c.caracteres == len("sistema") + len("oi?")
