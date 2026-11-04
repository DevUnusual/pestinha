"""
HOLOGRAMA - a imagem que você pediu no chat, projetada pelos olhos do pet como um holograma.

Só desenho: quem busca a imagem é mind/visao.py (ia/imagem.py). A janela fica logo acima do pet e
continua a luz que sai dos olhos dele (body/desenho_fantasias.py): o feixe sobe e abre, a imagem
desdobra de uma linha com um pouco de falha de sinal e flutua com linhas de varredura passando até
você mexer no pet (fechar): aí fecha numa linha e o feixe recolhe. Não recebe clique (o clique passa
para o que está embaixo) e não rouba o foco.
"""

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

from ..body.animacoes import ease_out_back, ease_out_cubic
from ..body.pet import overlay_flags, set_no_activate

LARGURA_MAX = 200           # px da imagem
ALTURA_MAX = 150
TITULO = 18                 # px da faixa do título em cima da imagem
FEIXE = 46                  # px do feixe entre o pet e a imagem
MARGEM = 12                 # px em volta (brilho e flutuação não são cortados)
SUBIR_FEIXE = 0.25          # s do feixe subindo
ABRIR = 0.45                # s da imagem desdobrando (começa quando o feixe chega)
FALHA = 0.7                 # s com falha de sinal no começo
FECHAR = 0.3                # s fechando no fim
HOLO = QColor("#6ff6ff")


def _alfa(cor, alfa):
    c = QColor(cor)
    c.setAlphaF(max(0.0, min(1.0, alfa)))
    return c


class Holograma(QWidget):
    """A projeção: mostrar(imagem, titulo, agora) e, a cada quadro, seguir(x, y_base, agora)."""

    def __init__(self):
        """Janela transparente que não recebe clique; começa escondida."""
        super().__init__(None, overlay_flags() | Qt.WindowTransparentForInput)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.imagem = None
        self.titulo = ""
        self.desde = 0.0
        self.ate = 0.0
        self._agora = 0.0
        self._tam = (0, 0)

    def showEvent(self, event):
        """Ao aparecer, não rouba o foco."""
        super().showEvent(event)
        set_no_activate(self)

    def mostrar(self, imagem, titulo, agora):
        """Projeta `imagem` (QImage) com `titulo` em cima; fica no ar até alguém chamar fechar()."""
        if imagem is None or imagem.isNull():
            return False
        self.imagem = imagem.scaled(LARGURA_MAX, ALTURA_MAX, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.titulo = titulo
        self.desde = self._agora = agora
        self.ate = math.inf
        largura = max(self.imagem.width(), 120)
        self._tam = (largura, self.imagem.height())
        self.setFixedSize(largura + 2 * MARGEM, TITULO + self.imagem.height() + FEIXE + 2 * MARGEM)
        self.update()
        return True

    def fechar(self, agora):
        """Você mexeu no pet: a projeção fecha numa linha e o feixe recolhe (em FECHAR segundos)."""
        if not self.visivel(agora) or self.ate <= agora + FECHAR:
            return False
        self.ate = agora + FECHAR
        return True

    def esconder(self):
        """Some com a projeção agora."""
        self.ate = 0.0
        self.imagem = None
        self.hide()

    def visivel(self, agora):
        """Se há uma projeção no ar agora."""
        return self.imagem is not None and agora < self.ate

    def topo(self):
        """y (na tela) do topo da projeção, para o balão ficar acima dela."""
        return self.y() + MARGEM

    def seguir(self, x, y_base, agora, pode_aparecer=True):
        """Põe a projeção acima do pet, com a base do feixe em (x, y_base); esconde quando o tempo acaba."""
        if not self.visivel(agora) or not pode_aparecer:
            if self.isVisible():
                self.hide()
            if self.imagem is not None and agora >= self.ate:
                self.imagem = None
            return
        self._agora = agora
        self.move(int(x - self.width() / 2), int(y_base - self.height() + MARGEM))
        if not self.isVisible():
            self.show()
        self.update()                       # flutua e varre o tempo todo

    # ---------------- desenho ----------------

    def fases(self, agora):
        """(feixe, abertura, falha) de 0 a 1 neste instante: quanto o feixe subiu, a imagem abriu e falha."""
        t = agora - self.desde
        fim = (self.ate - agora) / FECHAR
        feixe = ease_out_cubic(t / SUBIR_FEIXE)
        abre = ease_out_back((t - SUBIR_FEIXE * 0.6) / ABRIR, 1.2) if t > SUBIR_FEIXE * 0.6 else 0.0
        if fim < 1.0:                                   # fechando: a imagem vira linha e o feixe recolhe
            abre = min(abre, max(0.0, fim) ** 2)
            feixe = min(feixe, max(0.0, fim * 1.5))
        falha = max(0.0, 1.0 - t / FALHA) if t > 0 else 1.0
        return feixe, abre, falha

    def paintEvent(self, _event):
        """Feixe, imagem com varredura e moldura de holograma, e o título."""
        if self.imagem is None:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        agora = self._agora
        feixe, abre, falha = self.fases(agora)
        largura, altura = self._tam
        meio = self.width() / 2
        base = self.height() - MARGEM                   # onde o feixe encosta no pet
        flutua = 3.0 * math.sin(agora * 1.7)
        caixa = QRectF(meio - largura / 2, MARGEM + TITULO + flutua, largura, altura)
        tremula = 0.9 + 0.1 * math.sin(agora * 41.0) * math.sin(agora * 13.0)

        # feixe: sai estreito do pet e abre até a base da imagem
        topo_feixe = base - (base - caixa.bottom()) * feixe
        cone = QPainterPath()
        cone.moveTo(meio - 36, base)
        cone.lineTo(meio + 36, base)
        cone.lineTo(meio + largura / 2 * (0.4 + 0.6 * feixe), topo_feixe)
        cone.lineTo(meio - largura / 2 * (0.4 + 0.6 * feixe), topo_feixe)
        cone.closeSubpath()
        luz = QLinearGradient(0, base, 0, caixa.bottom())
        luz.setColorAt(0.0, _alfa(HOLO, 0.40 * feixe * tremula))
        luz.setColorAt(1.0, _alfa(HOLO, 0.10 * feixe))
        p.setPen(Qt.NoPen)
        p.setBrush(luz)
        p.drawPath(cone)

        if abre > 0.0:
            p.save()
            p.translate(meio, caixa.center().y())
            p.scale(1.0, max(0.02, abre))               # desdobra a partir de uma linha no meio
            p.translate(-meio, -caixa.center().y())
            p.setOpacity(min(1.0, abre * 1.5) * tremula)
            self._imagem(p, caixa, agora, falha)
            self._moldura(p, caixa, agora)
            p.restore()
            if abre > 0.8 and self.titulo:
                p.setOpacity(min(1.0, (abre - 0.8) / 0.2) * tremula)
                p.setPen(HOLO)
                p.setFont(QFont("Consolas", 9, QFont.Bold))
                p.drawText(QRectF(0, caixa.top() - TITULO, self.width(), TITULO - 2), Qt.AlignCenter,
                           self.titulo.upper())
        p.end()

    def _imagem(self, p, caixa, agora, falha):
        """A imagem com um toque azul de holograma; no começo, faixas deslocadas (falha de sinal)."""
        img = self.imagem
        faixas = 9 if falha > 0 else 1
        altura = caixa.height() / faixas
        for i in range(faixas):
            desvio = falha * 14.0 * math.sin(i * 2.7 + agora * 31.0) if falha > 0 else 0.0
            origem = QRectF(0, img.height() * i / faixas, img.width(), img.height() / faixas)
            destino = QRectF(caixa.left() + desvio, caixa.top() + altura * i, caixa.width(), altura)
            p.drawImage(destino, img, origem)
        p.save()
        p.setCompositionMode(QPainter.CompositionMode_Screen)
        p.fillRect(caixa, _alfa(HOLO, 0.22))
        p.restore()
        p.setPen(QPen(_alfa(QColor("#ffffff"), 0.10), 1.0))   # varredura descendo
        y = caixa.top() + (agora * 20.0) % 3.0
        while y < caixa.bottom():
            p.drawLine(QPointF(caixa.left(), y), QPointF(caixa.right(), y))
            y += 3.0
        faixa = caixa.top() + caixa.height() * ((agora / 2.2) % 1.0)
        brilho = QLinearGradient(0, faixa - 14, 0, faixa)
        brilho.setColorAt(0.0, _alfa(HOLO, 0.0))
        brilho.setColorAt(1.0, _alfa(HOLO, 0.28))
        p.fillRect(QRectF(caixa.left(), faixa - 14, caixa.width(), 14), brilho)

    def _moldura(self, p, caixa, agora):
        """Borda brilhante e cantoneiras de mira, como num painel de ficção científica."""
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(_alfa(HOLO, 0.55), 1.2))
        p.drawRect(caixa)
        canto = 12
        p.setPen(QPen(HOLO, 2.4, Qt.SolidLine, Qt.SquareCap))
        for (x, y, dx, dy) in ((caixa.left(), caixa.top(), 1, 1), (caixa.right(), caixa.top(), -1, 1),
                               (caixa.left(), caixa.bottom(), 1, -1), (caixa.right(), caixa.bottom(), -1, -1)):
            p.drawLine(QPointF(x, y), QPointF(x + dx * canto, y))
            p.drawLine(QPointF(x, y), QPointF(x, y + dy * canto))


def imagem_de_bytes(dados):
    """QImage dos bytes baixados (jpg, png, webp...), ou None se não deu para ler."""
    img = QImage.fromData(dados)
    return None if img.isNull() else img
