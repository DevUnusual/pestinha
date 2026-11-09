"""
DESENHO - como a IA pede para desenhar por cima da sua tela (círculo, quadrado, seta ou ícone) e como o
pedido vira formas.

Sem Qt e sem rede: só texto. O modelo vê o print e responde em coordenadas de 0 a 1000 sobre ele (x da
esquerda para a direita, y de cima para baixo); aqui elas viram frações de 0 a 1 da tela, e quem desenha
(world/rabisco.py) multiplica pelo tamanho do monitor que foi fotografado.
    INSTRUCOES_CHAT / INSTRUCOES_OLHADA   o que o modelo precisa saber para desenhar
    separar_desenho(texto)                 a resposta sem a linha "DESENHAR: [...]", e as formas (ou [])
    ler_formas(dados)                      a lista do JSON vira Formas (tolerante a campos ruins)
"""

import json
import re
from dataclasses import dataclass

TIPOS = ("circulo", "quadrado", "seta", "icone")
ICONES = {"!": "!", "?": "?", "★": "★", "♥": "♥", "👀": "👀", "✓": "✓", "✗": "✗",
          "exclamacao": "!", "atencao": "!", "interrogacao": "?", "pergunta": "?", "estrela": "★",
          "coracao": "♥", "olho": "👀", "olhos": "👀", "certo": "✓", "ok": "✓", "errado": "✗", "x": "✗"}
SINONIMOS = {"circulo": "circulo", "círculo": "circulo", "circle": "circulo", "elipse": "circulo",
             "quadrado": "quadrado", "retangulo": "quadrado", "retângulo": "quadrado", "caixa": "quadrado",
             "square": "quadrado", "rect": "quadrado", "box": "quadrado",
             "seta": "seta", "flecha": "seta", "arrow": "seta",
             "icone": "icone", "ícone": "icone", "icon": "icone", "marcador": "icone"}
MAX_FORMAS = 3
MAX_TEXTO = 24              # caracteres da legenda de cada forma
MIN_LADO = 0.02             # fração da tela: uma caixa menor que isso cresce (o círculo não vira um ponto)

FORMAS_TEXTO = (
    "As coordenadas são de 0 a 1000 sobre o print: x da esquerda para a direita, y de cima para baixo. "
    'Formas: {"forma": "circulo"} ou {"forma": "quadrado"} com "caixa": [x1, y1, x2, y2] em volta da coisa; '
    '{"forma": "seta", "de": [x, y], "para": [x, y]} (a ponta fica no "para"); '
    '{"forma": "icone", "em": [x, y], "icone": "!"} (ícones: ! ? ★ ♥ 👀 ✓ ✗). '
    f'Cada forma pode ter "texto" (até 3 palavras). No máximo {MAX_FORMAS} formas, só sobre o que está no print.'
)
INSTRUCOES_CHAT = (
    "[Você pode desenhar por cima da tela dela para mostrar ou destacar algo que está no print (um botão, "
    "um erro, uma parte de uma imagem): use quando ela pedir para mostrar onde algo está, ou quando apontar "
    "ajudar de verdade. Para desenhar, termine a resposta com uma linha só com: DESENHAR: [formas em JSON]. "
    + FORMAS_TEXTO + " Se não precisar, não use essa linha.]"
)
INSTRUCOES_OLHADA = (
    ' Você pode destacar na tela algo de que falou no comentário, em "desenhar": uma lista de formas, quase '
    "sempre vazia (só quando apontar ajuda: um erro, um botão, algo que te chamou a atenção). " + FORMAS_TEXTO
)

_LINHA = re.compile(r"^[ \t*_`]*DESENHAR[ \t*_`]*:[ \t]*", re.IGNORECASE | re.MULTILINE)


@dataclass(frozen=True)
class Forma:
    """Uma forma em frações da tela (0..1). `pontos`: caixa (2 cantos), seta (de, para) ou ícone (1 ponto)."""
    tipo: str
    pontos: tuple
    texto: str = ""
    icone: str = ""


def _num(valor):
    """Número finito, ou None."""
    if isinstance(valor, bool) or not isinstance(valor, (int, float)) or valor != valor:
        return None
    if valor in (float("inf"), float("-inf")):
        return None
    return float(valor)


def _ponto(valor, escala):
    """[x, y] (ou {"x", "y"}) na escala do modelo -> (x, y) em 0..1; None se não der."""
    if isinstance(valor, dict):
        valor = [valor.get("x"), valor.get("y")]
    if not isinstance(valor, (list, tuple)) or len(valor) < 2:
        return None
    x, y = _num(valor[0]), _num(valor[1])
    if x is None or y is None:
        return None
    return (min(1.0, max(0.0, x / escala)), min(1.0, max(0.0, y / escala)))


def _escala(itens):
    """1000 (o combinado) ou 1, se todos os números da forma vieram como frações."""
    numeros = []

    def juntar(v):
        if isinstance(v, (list, tuple)):
            for i in v:
                juntar(i)
        elif isinstance(v, dict):
            for i in v.values():
                juntar(i)
        elif _num(v) is not None:
            numeros.append(_num(v))
    for item in itens:
        if isinstance(item, dict):
            for chave in ("caixa", "box", "de", "para", "em", "ponto", "x", "y", "x1", "y1", "x2", "y2"):
                juntar(item.get(chave))
    return 1.0 if numeros and max(numeros) <= 1.0 else 1000.0


def _caixa(item, escala):
    """Os dois cantos da caixa, em ordem e com um tamanho mínimo; None se não der."""
    bruto = item.get("caixa", item.get("box"))
    if bruto is None and all(k in item for k in ("x1", "y1", "x2", "y2")):
        bruto = [item["x1"], item["y1"], item["x2"], item["y2"]]
    if not isinstance(bruto, (list, tuple)) or len(bruto) < 4:
        return None
    a, b = _ponto(bruto[:2], escala), _ponto(bruto[2:4], escala)
    if a is None or b is None:
        return None
    (x1, x2), (y1, y2) = sorted((a[0], b[0])), sorted((a[1], b[1]))
    if x2 - x1 < MIN_LADO:
        meio = (x1 + x2) / 2
        x1, x2 = max(0.0, meio - MIN_LADO / 2), min(1.0, meio + MIN_LADO / 2)
    if y2 - y1 < MIN_LADO:
        meio = (y1 + y2) / 2
        y1, y2 = max(0.0, meio - MIN_LADO / 2), min(1.0, meio + MIN_LADO / 2)
    return (x1, y1), (x2, y2)


def _texto(valor):
    """Legenda curta, numa linha."""
    if not isinstance(valor, str):
        return ""
    texto = " ".join(valor.split())
    return texto if len(texto) <= MAX_TEXTO else texto[:MAX_TEXTO - 1].rstrip() + "…"


def ler_formas(dados):
    """A lista (ou uma forma só) do JSON vira até MAX_FORMAS Formas; o que não der para entender é pulado."""
    if isinstance(dados, dict):
        dados = dados.get("formas", [dados]) if "forma" not in dados and "tipo" not in dados else [dados]
    if not isinstance(dados, list):
        return []
    formas = []
    for item in (i for i in dados if isinstance(i, dict)):
        escala = _escala([item])                    # cada forma na sua escala: 0..1000, ou frações
        tipo = SINONIMOS.get(str(item.get("forma", item.get("tipo", ""))).strip().lower())
        texto = _texto(item.get("texto", item.get("legenda")))
        forma = None
        if tipo in ("circulo", "quadrado"):
            caixa = _caixa(item, escala)
            if caixa:
                forma = Forma(tipo, caixa, texto)
        elif tipo == "seta":
            de, para = _ponto(item.get("de"), escala), _ponto(item.get("para"), escala)
            if de and para and de != para:
                forma = Forma("seta", (de, para), texto)
        elif tipo == "icone":
            em = _ponto(item.get("em", item.get("ponto")), escala)
            if em is None and "x" in item:
                em = _ponto([item.get("x"), item.get("y")], escala)
            if em:
                icone = ICONES.get(str(item.get("icone", "!")).strip().lower(), "!")
                forma = Forma("icone", (em,), texto, icone)
        if forma:
            formas.append(forma)
        if len(formas) >= MAX_FORMAS:
            break
    return formas


def separar_desenho(texto):
    """('resposta sem a linha DESENHAR', [Formas]) ou (texto, []) se ele não quis desenhar."""
    texto = texto or ""
    achado = _LINHA.search(texto)
    if not achado:
        return texto, []
    resto = texto[achado.end():]
    inicio = min((i for i in (resto.find("["), resto.find("{")) if i >= 0), default=-1)
    formas, fim = [], achado.end()
    if inicio >= 0:
        try:
            dados, tamanho = json.JSONDecoder().raw_decode(resto[inicio:])
            formas = ler_formas(dados)
            fim = achado.end() + inicio + tamanho
        except ValueError:
            fim = achado.end() + (resto.find("\n") if "\n" in resto else len(resto))
    else:
        fim = achado.end() + (resto.find("\n") if "\n" in resto else len(resto))
    limpo = (texto[:achado.start()] + texto[fim:]).strip()
    return limpo, formas
