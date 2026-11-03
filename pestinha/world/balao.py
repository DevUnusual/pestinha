"""
BALÃO - o balãozinho de fala em cima do pet (comentários da IA e respostas do chat).

Só desenho: quem decide o que ele fala fica em mind/visao.py. Segue o pet a cada quadro,
some sozinho depois de um tempo proporcional ao texto, e some se você clicar nele. Não rouba
o foco do programa que você está usando.
"""

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

from ..body.pet import overlay_flags, set_no_activate

LARGURA_MAX = 260           # px do texto antes de quebrar a linha
MARGEM = 12                 # px entre o texto e a borda do balão
PONTA = 14                  # px da pontinha que aponta para o pet
SEGUNDOS_BASE = 4.0         # todo balão fica pelo menos isso...
SEGUNDOS_POR_LETRA = 0.06   # ...mais um tanto por letra (tempo de leitura)
SEGUNDOS_MAX = 14.0


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
        self._caixa = QRectF()

    def showEvent(self, event):
        """Ao aparecer, não rouba o foco."""
        super().showEvent(event)
        set_no_activate(self)

    def mostrar(self, texto, agora):
        """Mostra (ou troca) a fala; ela some sozinha depois de duracao(texto)."""
        self.texto = texto
        self.ate = agora + duracao(texto)
        metricas = QFontMetrics(self.fonte)
        caixa = metricas.boundingRect(0, 0, LARGURA_MAX, 1000, Qt.TextWordWrap, texto)
        largura = caixa.width() + 2 * MARGEM
        altura = caixa.height() + 2 * MARGEM
        self._caixa = QRectF(1, 1, largura, altura)
        self.setFixedSize(largura + 3, altura + PONTA + 3)
        self.update()

    def esconder(self):
        """Some com o balão agora."""
        self.ate = 0.0
        self.hide()

    def seguir(self, x, y_topo, agora, pode_aparecer=True):
        """Põe o balão acima do pet, com a ponta no centro dele; esconde quando o tempo acaba."""
        if not self.texto or agora >= self.ate or not pode_aparecer:
            if self.isVisible():
                self.hide()
            return
        self.move(int(x - self.width() / 2), int(y_topo - self.height()))
        if not self.isVisible():
            self.show()

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
        p.setPen(QColor("#13261a"))
        p.setFont(self.fonte)
        p.drawText(caixa.adjusted(MARGEM, MARGEM, -MARGEM, -MARGEM), Qt.TextWordWrap | Qt.AlignLeft, self.texto)
        p.end()
