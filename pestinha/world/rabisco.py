"""
RABISCO - ele desenha por cima da sua tela para te mostrar algo: um círculo, um quadrado, uma seta ou um
ícone, como quem rabisca com caneta marca-texto.

Só desenho: quem decide o que desenhar é a IA (ia/desenho.py, pedido por mind/visao.py). A janela cobre o
monitor que foi fotografado, é transparente, não recebe clique (o clique passa para o que está embaixo) e
não rouba o foco. Cada forma é traçada à mão em TRACO s, uma depois da outra; a legenda aparece quando o
traço termina; tudo fica DURACAO s e some esmaecendo. Mexer nele (cutucar, pegar, carinho) apaga antes.
"""

import math
import random

from PySide6.QtCore import QPointF, QRect, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

from ..body.animacoes import ease_out_back, ease_out_cubic
from ..body.pet import overlay_flags, set_no_activate

TRACO = 0.55                # s para traçar cada forma
ENTRE = 0.25                # s entre o começo de uma forma e o da próxima (depois do traço anterior)
DURACAO = 9.0               # s que o desenho fica na tela
SUMIR = 0.6                 # s esmaecendo no fim
APAGAR = 0.25               # s esmaecendo quando você mexe nele
FOLGA = 0.14                # o círculo e o quadrado ficam um pouco maiores que a caixa pedida
ESPESSURA = 4.5
COR = QColor("#ff3d71")
CONTORNO = QColor(255, 255, 255, 170)
AMOSTRAS = 72               # pontos por forma (o traço é uma linha quebrada bem fina)


def pontos_circulo(caixa, semente):
    """Elipse à mão em volta da caixa: dá um pouco mais de uma volta e treme de leve."""
    rng = random.Random(semente)
    (x1, y1), (x2, y2) = caixa
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
    rx, ry = (x2 - x1) / 2 * (1 + FOLGA) + 6, (y2 - y1) / 2 * (1 + FOLGA) + 6
    comeco, fase = rng.uniform(-2.6, -2.0), rng.uniform(0, math.tau)
    voltas = 1.12
    saida = []
    for i in range(AMOSTRAS + 1):
        t = i / AMOSTRAS
        a = comeco + t * voltas * math.tau
        treme = 1 + 0.035 * math.sin(3 * a + fase) + 0.05 * t      # o fim passa um pouco por fora
        saida.append(QPointF(cx + rx * treme * math.cos(a), cy + ry * treme * math.sin(a)))
    return saida


def pontos_quadrado(caixa, semente):
    """Retângulo à mão: quatro lados levemente tortos, e o último passa do canto."""
    rng = random.Random(semente)
    (x1, y1), (x2, y2) = caixa
    fx, fy = (x2 - x1) * FOLGA / 2 + 6, (y2 - y1) * FOLGA / 2 + 6
    cantos = [(x1 - fx, y1 - fy), (x2 + fx, y1 - fy), (x2 + fx, y2 + fy), (x1 - fx, y2 + fy), (x1 - fx, y1 - fy)]
    cantos = [(x + rng.uniform(-3, 3), y + rng.uniform(-3, 3)) for x, y in cantos]
    cantos[-1] = (cantos[-1][0] + 10, cantos[-1][1] - 4)               # passa do canto, como na caneta
    saida = []
    por_lado = AMOSTRAS // 4
    for (ax, ay), (bx, by) in zip(cantos, cantos[1:]):
        for i in range(por_lado):
            t = i / por_lado
            saida.append(QPointF(ax + (bx - ax) * t, ay + (by - ay) * t))
    saida.append(QPointF(*cantos[-1]))
    return saida


def pontos_seta(de, para):
    """Corpo da seta: uma curva suave de `de` até `para`."""
    (ax, ay), (bx, by) = de, para
    dx, dy = bx - ax, by - ay
    comprimento = math.hypot(dx, dy) or 1.0
    nx, ny = -dy / comprimento, dx / comprimento
    curva = min(40.0, comprimento * 0.12)
    cx, cy = (ax + bx) / 2 + nx * curva, (ay + by) / 2 + ny * curva
    saida = []
    for i in range(AMOSTRAS + 1):
        t = i / AMOSTRAS
        u = 1 - t
        saida.append(QPointF(u * u * ax + 2 * u * t * cx + t * t * bx, u * u * ay + 2 * u * t * cy + t * t * by))
    return saida


def prefixo(pontos, fracao):
    """Os primeiros `fracao` (0..1) dos pontos: o traço até onde a caneta já chegou."""
    if fracao <= 0 or len(pontos) < 2:
        return []
    n = max(2, int(math.ceil(fracao * (len(pontos) - 1))) + 1)
    return pontos[:min(n, len(pontos))]


class Rabisco(QWidget):
    """O desenho: desenhar(formas, geometria, agora) e, a cada quadro, seguir(agora, pode_aparecer)."""

    def __init__(self):
        """Janela transparente que não recebe clique; começa escondida."""
        super().__init__(None, overlay_flags() | Qt.WindowTransparentForInput)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.formas = []            # (Forma, pontos na janela, quando começa a traçar)
        self.desde = 0.0
        self.ate = 0.0
        self._agora = 0.0

    def showEvent(self, event):
        """Ao aparecer, não rouba o foco."""
        super().showEvent(event)
        set_no_activate(self)

    def desenhar(self, formas, geometria, agora):
        """Desenha `formas` (ia/desenho.Forma, em frações) sobre o monitor `geometria` (x, y, largura, altura)."""
        x, y, largura, altura = geometria
        if not formas or largura <= 0 or altura <= 0:
            return False
        self.setGeometry(QRect(int(x), int(y), int(largura), int(altura)))
        self.formas = []
        comeco = agora
        for i, forma in enumerate(formas):
            pts = [(px * largura, py * altura) for px, py in forma.pontos]
            semente = hash((forma.tipo, forma.pontos)) & 0xFFFF
            if forma.tipo == "circulo":
                linha = pontos_circulo(pts, semente)
            elif forma.tipo == "quadrado":
                linha = pontos_quadrado(pts, semente)
            elif forma.tipo == "seta":
                linha = pontos_seta(*pts)
            else:
                linha = [QPointF(*pts[0])]
            self.formas.append((forma, linha, comeco))
            comeco += TRACO + ENTRE
        self.desde = self._agora = agora
        self.ate = comeco + DURACAO
        self.update()
        return True

    def visivel(self, agora):
        """Se há um desenho na tela agora."""
        return bool(self.formas) and agora < self.ate

    def apagar(self, agora):
        """Você mexeu nele: o desenho some rápido."""
        if self.visivel(agora) and self.ate > agora + APAGAR:
            self.ate = agora + APAGAR
            return True
        return False

    def esconder(self):
        """Some agora."""
        self.formas = []
        self.ate = 0.0
        self.hide()

    def seguir(self, agora, pode_aparecer=True):
        """A cada quadro: anima, ou esconde quando o tempo acaba (ou ele não pode aparecer)."""
        if not self.visivel(agora) or not pode_aparecer:
            if self.isVisible():
                self.hide()
            if agora >= self.ate:
                self.formas = []
            return
        self._agora = agora
        if not self.isVisible():
            self.show()
        self.update()

    # ---------------- desenho ----------------

    def opacidade(self, agora):
        """1 enquanto está na tela; vai a 0 nos últimos SUMIR s."""
        falta = self.ate - agora
        return max(0.0, min(1.0, falta / SUMIR))

    def paintEvent(self, _event):
        """Cada forma até onde a caneta chegou, com contorno branco para aparecer em qualquer fundo."""
        if not self.formas:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        agora = self._agora
        p.setOpacity(self.opacidade(agora))
        for forma, linha, comeco in self.formas:
            t = (agora - comeco) / TRACO
            if t <= 0:
                continue
            if forma.tipo == "icone":
                ancora = self._icone(p, forma, linha[0], t, agora)
            else:
                trecho = prefixo(linha, ease_out_cubic(min(1.0, t)))
                self._traco(p, trecho)
                if forma.tipo == "seta" and t >= 0.85:
                    self._ponta(p, linha, min(1.0, (t - 0.85) / 0.3))
                ancora = self._ancora(forma, linha)
            if forma.texto and t >= 1.0:
                self._legenda(p, forma.texto, ancora, min(1.0, (t - 1.0) * 3.0))
        p.end()

    def _traco(self, p, pontos):
        """A linha da caneta: primeiro o contorno largo e claro, depois a cor."""
        if len(pontos) < 2:
            return
        caminho = QPainterPath(pontos[0])
        for ponto in pontos[1:]:
            caminho.lineTo(ponto)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(CONTORNO, ESPESSURA + 4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawPath(caminho)
        p.setPen(QPen(COR, ESPESSURA, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawPath(caminho)

    def _ponta(self, p, linha, abre):
        """A ponta da seta, abrindo no fim do traço."""
        fim, antes = linha[-1], linha[-6]
        angulo = math.atan2(fim.y() - antes.y(), fim.x() - antes.x())
        tamanho = 18 * ease_out_back(abre, 2.0)
        for lado in (-1, 1):
            a = angulo + math.pi + lado * 0.5
            self._traco(p, [fim, QPointF(fim.x() + tamanho * math.cos(a), fim.y() + tamanho * math.sin(a))])

    def _icone(self, p, forma, centro, t, agora):
        """Um selo redondo com o ícone, que aparece com um pulo e fica pulsando de leve."""
        escala = ease_out_back(min(1.0, t), 2.2) * (1 + 0.06 * math.sin((agora - self.desde) * 5.0))
        raio = 22 * escala
        if raio <= 1:
            return centro
        p.setPen(QPen(CONTORNO, 4))
        p.setBrush(COR)
        p.drawEllipse(centro, raio, raio)
        p.setPen(QColor("#ffffff"))
        p.setFont(QFont("Segoe UI Emoji", max(1, int(18 * escala)), QFont.Bold))
        p.drawText(QRectF(centro.x() - raio, centro.y() - raio, 2 * raio, 2 * raio), Qt.AlignCenter, forma.icone)
        return QPointF(centro.x(), centro.y() - 26)

    @staticmethod
    def _ancora(forma, linha):
        """Onde fica a legenda: em cima da caixa, ou no começo da seta."""
        if forma.tipo == "seta":
            return linha[0]
        topo = min(linha, key=lambda q: q.y())
        meio = sum(q.x() for q in linha) / len(linha)
        return QPointF(meio, topo.y() - 8)

    def _legenda(self, p, texto, ancora, alfa):
        """O texto numa etiqueta arredondada, sem sair da tela."""
        fonte = QFont("Segoe UI", 12, QFont.Bold)
        medida = QFontMetricsF(fonte)
        largura, altura = medida.horizontalAdvance(texto) + 18, medida.height() + 8
        x = min(max(4.0, ancora.x() - largura / 2), self.width() - largura - 4)
        y = min(max(4.0, ancora.y() - altura), self.height() - altura - 4)
        caixa = QRectF(x, y, largura, altura)
        p.save()
        p.setOpacity(p.opacity() * alfa)
        p.setPen(QPen(CONTORNO, 2))
        p.setBrush(COR)
        p.drawRoundedRect(caixa, altura / 2, altura / 2)
        p.setPen(QColor("#ffffff"))
        p.setFont(fonte)
        p.drawText(caixa, Qt.AlignCenter, texto)
        p.restore()
