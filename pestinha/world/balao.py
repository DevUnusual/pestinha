"""
BALÃO - o balãozinho de fala em cima do pet (comentários da IA e respostas do chat).

Só desenho: quem decide o que ele fala fica em mind/visao.py. Segue o pet a cada quadro,
some sozinho depois de um tempo proporcional ao texto, e some se você clicar nele. Não rouba
o foco do programa que você está usando.

Aparece com um pop saindo da pontinha (passa um pouco do tamanho e assenta) e o texto vai sendo
digitado no mesmo ritmo em que os olhos dele "falam" (body/animacoes.py). As letras que ainda não
apareceram já ocupam o lugar delas: nenhuma palavra pula de linha no meio da digitação.
"""

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (QColor, QFont, QPainter, QPainterPath, QPen, QTextCharFormat, QTextLayout,
                           QTextOption)
from PySide6.QtWidgets import QWidget

from ..body.animacoes import FALA_MAX, SEGUNDOS_POR_LETRA, ease_out_back, ease_out_cubic
from ..body.pet import overlay_flags, set_no_activate

LARGURA_MAX = 260           # px do texto antes de quebrar a linha
MARGEM = 12                 # px entre o texto e a borda do balão
PONTA = 14                  # px da pontinha que aponta para o pet
FOLGA = 10                  # px em volta do balão: o pop passa um pouco do tamanho e não pode ser cortado
SEGUNDOS_BASE = 4.0         # todo balão fica pelo menos isso...
SEGUNDOS_POR_LETRA = 0.06   # ...mais um tanto por letra (tempo de leitura)
SEGUNDOS_MAX = 14.0
DURACAO_POP = 0.28          # s do balão crescendo a partir da pontinha
DURACAO_SAIDA = 0.16        # s do balão sumindo (sair é mais rápido que entrar)
COR_TEXTO = QColor("#13261a")


def duracao(texto):
    """Quanto tempo o balão fica na tela para dar tempo de ler."""
    return min(SEGUNDOS_MAX, SEGUNDOS_BASE + SEGUNDOS_POR_LETRA * len(texto))


class Balao(QWidget):
    """Balão de fala: mostrar(texto) e, a cada quadro, seguir(x, y_topo, agora)."""

    def __init__(self):
        """Janela transparente sem moldura; começa escondida."""
        super().__init__(None, overlay_flags())
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("clique para fechar")
        self.fonte = QFont("Segoe UI", 10)
        self.texto = ""
        self.ate = 0.0
        self.desde = 0.0
        self._agora = 0.0
        self._caixa = QRectF()
        self._layout = None

    def showEvent(self, event):
        """Ao aparecer, não rouba o foco."""
        super().showEvent(event)
        set_no_activate(self)

    def mostrar(self, texto, agora):
        """Mostra (ou troca) a fala; ela some sozinha depois de duracao(texto)."""
        self.texto = texto
        self.desde = self._agora = agora
        self.ate = agora + duracao(texto)
        self._layout, largura_texto, altura_texto = _diagramar(texto, self.fonte)
        largura = math.ceil(largura_texto) + 2 * MARGEM
        altura = math.ceil(altura_texto) + 2 * MARGEM
        self._caixa = QRectF(FOLGA, FOLGA, largura, altura)
        self.setFixedSize(largura + 2 * FOLGA, altura + PONTA + 2 * FOLGA)
        self.update()

    def esconder(self):
        """Some com o balão agora."""
        self.ate = 0.0
        self.hide()

    def letras(self, agora):
        """Quantas letras já foram digitadas (o mesmo ritmo dos olhos falando)."""
        digitar = min(FALA_MAX, SEGUNDOS_POR_LETRA * len(self.texto))
        if digitar <= 0.0 or agora - self.desde >= digitar:
            return len(self.texto)
        return max(0, min(len(self.texto), math.ceil(len(self.texto) * (agora - self.desde) / digitar)))

    def escala(self, agora):
        """(tamanho, opacidade) do balão agora: cresce com pop na entrada e encolhe um pouco na saída."""
        entrada = (agora - self.desde) / DURACAO_POP
        saida = (self.ate - agora) / DURACAO_SAIDA
        if saida < 1.0:
            return 0.85 + 0.15 * max(0.0, saida), max(0.0, saida)
        return 0.6 + 0.4 * ease_out_back(entrada), ease_out_cubic(entrada * 1.6)

    def seguir(self, x, y_topo, agora, pode_aparecer=True):
        """Põe o balão acima do pet, com a ponta no centro dele; esconde quando o tempo acaba."""
        if not self.texto or agora >= self.ate or not pode_aparecer:
            if self.isVisible():
                self.hide()
            return
        self.move(int(x - self.width() / 2), int(y_topo - self.height() + FOLGA))      # a ponta fica onde ficava
        self._agora = agora
        if not self.isVisible():
            self.show()
        if (agora - self.desde < max(DURACAO_POP, SEGUNDOS_POR_LETRA * len(self.texto), 0.0) + 0.1
                or self.ate - agora < DURACAO_SAIDA + 0.05):
            self.update()                       # só redesenha enquanto anima (pop, digitação, saída)

    def mousePressEvent(self, event):
        """Clique: fecha o balão."""
        if event.button() == Qt.LeftButton:
            self.esconder()

    def paintEvent(self, _event):
        """Desenha o balão branco com a pontinha embaixo e o texto."""
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        caixa = self._caixa
        meio = caixa.center().x()
        tamanho, opacidade = self.escala(self._agora)
        p.setOpacity(opacidade)
        p.translate(meio, caixa.bottom() + PONTA)          # cresce a partir da pontinha, que aponta para ele
        p.scale(tamanho, tamanho)
        p.translate(-meio, -(caixa.bottom() + PONTA))
        forma = QPainterPath()
        forma.addRoundedRect(caixa, 10, 10)
        ponta = QPainterPath()
        ponta.moveTo(meio - 9, caixa.bottom() - 1)
        ponta.lineTo(meio, caixa.bottom() + PONTA)
        ponta.lineTo(meio + 9, caixa.bottom() - 1)
        ponta.closeSubpath()
        forma = forma.united(ponta)
        p.setPen(QPen(QColor("#2c5236"), 1.5))
        p.setBrush(QColor("#f7fff9"))
        p.drawPath(forma)
        if self._layout is not None:
            p.setPen(COR_TEXTO)
            escondido = QTextLayout.FormatRange()
            escondido.start = self.letras(self._agora)
            escondido.length = len(self.texto) - escondido.start
            escondido.format = QTextCharFormat()
            escondido.format.setForeground(QColor(0, 0, 0, 0))
            self._layout.draw(p, QPointF(caixa.left() + MARGEM, caixa.top() + MARGEM),
                              [escondido] if escondido.length > 0 else [])
        p.end()


def _diagramar(texto, fonte):
    """Quebra o texto em linhas de até LARGURA_MAX; devolve (layout, largura, altura)."""
    layout = QTextLayout(texto, fonte)
    opcao = QTextOption()
    opcao.setWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
    layout.setTextOption(opcao)
    layout.beginLayout()
    largura = altura = 0.0
    while True:
        linha = layout.createLine()
        if not linha.isValid():
            break
        linha.setLineWidth(LARGURA_MAX)
        linha.setPosition(QPointF(0, altura))
        altura += linha.height()
        largura = max(largura, linha.naturalTextWidth())
    layout.endLayout()
    return layout, largura, altura
