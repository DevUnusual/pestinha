"""
TOCANDO - o cartãozinho "tocando agora" ao lado do pet, com 👍 👎 ⏭ ⏸ 📌 ✕ e a barra de volume.

Só desenho e botões: quem toca e aprende é mind/musica_ctl.py. Cada botão vira `comando` com o mesmo
nome dos comandos do chat ('gostei', 'nao_gostei', 'pular', 'pausar'/'continuar', 'parar'). Recebe
clique mas não rouba o foco do programa que você está usando. Fica do lado direito do pet; perto da
borda da tela, passa para o esquerdo.

Para não ter que caçar o pet andando: arraste o cartão (fora dos botões) ou clique no 📌 e ele fica
parado onde está, até você clicar no 📌 de novo. Solto, a posição fica em memory/panels.json.

O tempo da música aparece de dois jeitos:
    borda     acende a partir do meio de cima e dá a volta no cartão (sentido horário); fecha a volta no
              fim da música. Uma pontinha brilha onde a música está; pausada, ela pulsa; carregando, um
              pedaço de borda fica dando voltas.
    número    '1:23 / 3:45' ao lado do rótulo.
No canto, um disquinho de vinil gira a 33⅓ rpm (desacelera devagar quando você pausa, como um toca-discos).
Se a música tem capa, ela vira o selo do disco; o 🖼 tira ou põe a capa (fica lembrado em panels.json).
"""

import math
import time

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (QColor, QConicalGradient, QFont, QImage, QPainter, QPainterPath, QPen,
                           QRadialGradient)
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QPushButton, QSlider, QVBoxLayout, QWidget)

from ..body.animacoes import aproximar
from ..body.pet import overlay_flags, set_no_activate
from ..store import write_json
from .arrastavel import load_positions, posicao_acessivel

CHAVE = "tocando"           # em memory/panels.json: [x, y] quando solto; ausente quando segue o pet
CHAVE_CAPA = "tocando_capa" # em memory/panels.json: false quando você tirou a capa do disco
ARRASTE_MIN = 4             # px antes de um clique virar arraste

LARGURA = 230               # px do cartão
DISTANCIA = 70              # px do centro do pet até a borda do cartão
RAIO = 10.0                 # px dos cantos do cartão
DISCO = 50                  # px do disquinho
GIRO = 200.0                # graus/s: 33⅓ rpm
PARAR_DISCO = 0.9           # s para o disco parar quando pausa (o motor desliga, o prato vai parando)
LIGAR_DISCO = 0.35          # s para pegar velocidade quando volta a tocar
VOLTA_CARREGANDO = 1.4      # s de uma volta do pedacinho de borda enquanto carrega

FUNDO = QColor(12, 31, 19, 235)
BORDA = QColor("#2c5236")
PROGRESSO = QColor("#63e56f")
PONTA = QColor("#dfffe6")
ESTILO = """
QFrame#cartao { background: transparent; border: none; }
QLabel { color: #dfffe6; font-size: 11px; }
QLabel#rotulo { color: #63e56f; font-size: 10px; font-weight: bold; }
QLabel#tempo { color: #9fd9ad; font-size: 10px; }
QPushButton { background: #17201a; color: #dfffe6; border: 1px solid #2c5236; border-radius: 6px;
              padding: 2px 0; font-size: 13px; min-width: 30px; }
QPushButton:hover { border-color: #63e56f; }
QPushButton:checked { background: #2c8a40; border-color: #63e56f; }
QPushButton#nao:checked { background: #b3261e; border-color: #ff9a8a; }
QPushButton#capa { min-width: 24px; font-size: 11px; }
QSlider::groove:horizontal { height: 4px; background: #2c5236; border-radius: 2px; }
QSlider::sub-page:horizontal { background: #63e56f; border-radius: 2px; }
QSlider::handle:horizontal { background: #dfffe6; width: 12px; margin: -5px 0; border-radius: 6px; }
"""


def tempo(segundos):
    """83 -> '1:23'."""
    segundos = max(0, int(segundos))
    return f"{segundos // 60}:{segundos % 60:02d}"


def contorno(caixa, raio=RAIO):
    """O contorno do cartão começando no meio de cima e dando a volta no sentido horário."""
    p = QPainterPath()
    meio, d = caixa.center().x(), 2 * raio
    p.moveTo(meio, caixa.top())
    p.lineTo(caixa.right() - raio, caixa.top())
    p.arcTo(QRectF(caixa.right() - d, caixa.top(), d, d), 90, -90)
    p.lineTo(caixa.right(), caixa.bottom() - raio)
    p.arcTo(QRectF(caixa.right() - d, caixa.bottom() - d, d, d), 0, -90)
    p.lineTo(caixa.left() + raio, caixa.bottom())
    p.arcTo(QRectF(caixa.left(), caixa.bottom() - d, d, d), -90, -90)
    p.lineTo(caixa.left(), caixa.top() + raio)
    p.arcTo(QRectF(caixa.left(), caixa.top(), d, d), 180, -90)
    p.lineTo(meio, caixa.top())
    return p


def trecho(caminho, de, ate, passos=160):
    """Os pontos do caminho entre as frações `de` e `ate` do comprimento (0..1; dá a volta se ate > 1)."""
    if ate <= de:
        return []
    n = max(2, int(passos * (ate - de)) + 1)
    pontos = []
    for i in range(n):
        f = de + (ate - de) * i / (n - 1)
        pontos.append(caminho.pointAtPercent(f - 1.0 if f > 1.0 else f))   # o contorno é fechado: emenda
    return pontos


class Tocando(QWidget):
    """O cartão: atualizar(controle) e, a cada quadro, seguir(x, y, limites)."""

    comando = Signal(str)
    volume = Signal(float)          # a barra de volume mudou (0 a 1)

    def __init__(self, arquivo=None):
        """Monta o cartão escondido; `arquivo` é o panels.json (lembra se ele está solto, e onde)."""
        super().__init__(None, overlay_flags())
        self.arquivo = arquivo
        self.solto = None               # (x, y) onde você deixou; None: segue o pet
        self._pego = None               # (onde o mouse apertou, posição do cartão nessa hora)
        self._arrastando = False
        self._ctl = None                # o controle de música (para ler o tempo a cada quadro)
        self.fracao = 0.0               # quanto da música já tocou (0..1)
        self.angulo = 0.0               # do disco, em graus
        self.giro = 0.0                 # velocidade atual do disco (graus/s)
        self._ultimo = None             # hora do último quadro
        self._capa_de = None            # os bytes de onde veio a capa decodificada
        self.capa = None                # QImage da capa da música da vez (ou None)
        self.setCursor(Qt.OpenHandCursor)
        self.setToolTip("arraste para deixar o player parado num cantinho")
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setStyleSheet(ESTILO)
        self.setFixedWidth(LARGURA)
        cartao = QFrame(self)
        cartao.setObjectName("cartao")
        fora = QVBoxLayout(self)
        fora.setContentsMargins(0, 0, 0, 0)
        fora.addWidget(cartao)
        layout = QVBoxLayout(cartao)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        topo = QHBoxLayout()                    # textos à esquerda, o disquinho à direita
        topo.setSpacing(8)
        textos = QVBoxLayout()
        textos.setSpacing(2)
        linha_rotulo = QHBoxLayout()
        self.rotulo = QLabel("♪ TOCANDO")
        self.rotulo.setObjectName("rotulo")
        linha_rotulo.addWidget(self.rotulo)
        linha_rotulo.addStretch(1)
        self.tempo = QLabel("")
        self.tempo.setObjectName("tempo")
        linha_rotulo.addWidget(self.tempo)
        textos.addLayout(linha_rotulo)
        self.titulo = QLabel("")
        self.titulo.setWordWrap(True)
        textos.addWidget(self.titulo)
        textos.addStretch(1)
        topo.addLayout(textos, 1)
        self.lugar_disco = QWidget()            # só reserva o lugar: o disco é pintado pelo cartão
        self.lugar_disco.setFixedSize(DISCO, DISCO)
        self.lugar_disco.setAttribute(Qt.WA_TransparentForMouseEvents)
        topo.addWidget(self.lugar_disco, 0, Qt.AlignTop)
        layout.addLayout(topo)

        botoes = QHBoxLayout()
        botoes.setSpacing(4)
        self.botoes = {}
        for nome, texto, dica in (("gostei", "👍", "gostei: mais músicas assim"),
                                  ("nao_gostei", "👎", "não gostei: pula e não toca mais"),
                                  ("pular", "⏭", "próxima"),
                                  ("pausa", "⏸", "pausar"),
                                  ("fixar", "📌", ""),
                                  ("parar", "✕", "parar a música")):
            botao = QPushButton(texto)
            botao.setToolTip(dica)
            botao.setFocusPolicy(Qt.NoFocus)
            botao.setCursor(Qt.PointingHandCursor)
            if nome in ("gostei", "nao_gostei", "fixar"):
                botao.setCheckable(True)
                botao.setObjectName("nao" if nome == "nao_gostei" else "sim")
            botao.clicked.connect(lambda _marcado=False, n=nome: self._clicou(n))
            botoes.addWidget(botao)
            self.botoes[nome] = botao
        layout.addLayout(botoes)
        linha_volume = QHBoxLayout()
        linha_volume.setSpacing(6)
        self.icone_volume = QLabel("🔉")
        linha_volume.addWidget(self.icone_volume)
        self.volume_barra = QSlider(Qt.Horizontal)
        self.volume_barra.setRange(0, 100)
        self.volume_barra.setFocusPolicy(Qt.NoFocus)
        self.volume_barra.setCursor(Qt.PointingHandCursor)
        self.volume_barra.setToolTip("volume da música")
        self.volume_barra.valueChanged.connect(self._barra_mudou)
        linha_volume.addWidget(self.volume_barra, 1)
        self.volume_texto = QLabel("50%")
        self.volume_texto.setFixedWidth(34)
        linha_volume.addWidget(self.volume_texto)
        capa = QPushButton("🖼")
        capa.setObjectName("capa")
        capa.setCheckable(True)
        capa.setFocusPolicy(Qt.NoFocus)
        capa.setCursor(Qt.PointingHandCursor)
        capa.clicked.connect(lambda marcado: self.mostrar_capa(marcado))
        linha_volume.addWidget(capa)
        self.botoes["capa"] = capa
        layout.addLayout(linha_volume)
        self._pausada = False
        self.adjustSize()
        salvos = load_positions(arquivo) if arquivo is not None else {}
        if salvos.get(CHAVE) is not None:
            self.solto = posicao_acessivel(salvos[CHAVE], (20, 20), (self.width(), self.height()))
        self.com_capa = salvos.get(CHAVE_CAPA) is not False
        self._marcar_fixo()
        self._marcar_capa()

    def showEvent(self, event):
        """Ao aparecer, não rouba o foco."""
        super().showEvent(event)
        set_no_activate(self)

    # ---------------- solto ou seguindo o pet ----------------

    def soltar(self, x, y):
        """Fica parado em (x, y) até você grudar de novo (e lembra disso na próxima vez)."""
        self.solto = (int(x), int(y))
        self.move(*self.solto)
        self._gravar()
        self._marcar_fixo()

    def grudar(self):
        """Volta a seguir o pet."""
        self.solto = None
        self._gravar()
        self._marcar_fixo()

    def mostrar_capa(self, sim):
        """Põe (ou tira) a capa da música no disquinho, e lembra disso na próxima vez."""
        self.com_capa = bool(sim)
        self._gravar()
        self._marcar_capa()
        self.update()

    def _marcar_fixo(self):
        """O 📌 aceso quando ele está solto."""
        botao = self.botoes["fixar"]
        botao.setChecked(self.solto is not None)
        botao.setToolTip("grudar de volta no pet" if self.solto else "deixar o player parado aqui")

    def _marcar_capa(self):
        """O 🖼 aceso quando a capa aparece no disco."""
        botao = self.botoes["capa"]
        botao.setChecked(self.com_capa)
        botao.setToolTip("tirar a capa do disco" if self.com_capa else "mostrar a capa da música no disco")

    def _gravar(self):
        """Lembra (ou esquece) a posição solta e a escolha da capa em panels.json."""
        if self.arquivo is None:
            return
        dados = load_positions(self.arquivo)
        if self.solto is None:
            dados.pop(CHAVE, None)
        else:
            dados[CHAVE] = list(self.solto)
        if self.com_capa:
            dados.pop(CHAVE_CAPA, None)
        else:
            dados[CHAVE_CAPA] = False
        try:
            write_json(self.arquivo, dados)
        except OSError:
            pass                                # sem gravar, vale só nesta sessão

    def mousePressEvent(self, event):
        """Apertou fora dos botões: pode ser o começo de um arraste."""
        if event.button() == Qt.LeftButton:
            self._pego = (event.globalPosition().toPoint(), self.pos())
            self._arrastando = False

    def mouseMoveEvent(self, event):
        """Arrastando: o cartão vai junto (e, ao soltar, fica lá)."""
        if self._pego is None:
            return
        inicio, origem = self._pego
        delta = event.globalPosition().toPoint() - inicio
        if not self._arrastando and delta.manhattanLength() < ARRASTE_MIN:
            return
        self._arrastando = True
        self.setCursor(Qt.ClosedHandCursor)
        self.move(origem + delta)

    def mouseReleaseEvent(self, event):
        """Soltou depois de arrastar: o player fica onde você deixou."""
        if event.button() != Qt.LeftButton or self._pego is None:
            return
        if self._arrastando:
            self.soltar(self.x(), self.y())
        self._pego, self._arrastando = None, False
        self.setCursor(Qt.OpenHandCursor)

    # ---------------- botões ----------------

    def _clicou(self, nome):
        """Um botão: vira o comando com o nome do chat (o ⏸ alterna entre pausar e continuar)."""
        if nome == "fixar":
            if self.solto is None:
                self.soltar(self.x(), self.y())
            else:
                self.grudar()
            return
        if nome == "pausa":
            nome = "continuar" if self._pausada else "pausar"
        self.comando.emit(nome)

    def atualizar(self, ctl):
        """Mostra o que o controle de música está fazendo (música, pausa, opinião já dada, capa)."""
        self._ctl = ctl
        self._pausada = ctl.pausada
        if ctl.atual is None:
            self.rotulo.setText("♪ PROCURANDO" + (f" {ctl.estilo.upper()}" if ctl.estilo else ""))
            self.titulo.setText("escolhendo a próxima...")
        else:
            self.rotulo.setText("♪ PAUSADA" if ctl.pausada else
                                "♪ CARREGANDO" if ctl.carregando else "♪ TOCANDO")
            self.titulo.setText(ctl.atual.nome())
        self.botoes["gostei"].setChecked(ctl.opiniao == "gostei")
        self.botoes["nao_gostei"].setChecked(ctl.opiniao == "nao_gostei")
        for nome in ("gostei", "nao_gostei"):
            self.botoes[nome].setEnabled(ctl.atual is not None)
        self.botoes["pausa"].setText("▶" if ctl.pausada else "⏸")
        self.botoes["pausa"].setToolTip("continuar" if ctl.pausada else "pausar")
        self.volume_barra.blockSignals(True)            # mostrar o volume não é mudar o volume
        self.volume_barra.setValue(round(ctl.volume * 100))
        self.volume_barra.blockSignals(False)
        self._mostrar_volume(ctl.volume)
        dados = getattr(ctl, "capa", None)
        if dados is not self._capa_de:                  # decodifica uma vez por música
            self._capa_de = dados
            imagem = QImage.fromData(dados) if dados else QImage()
            self.capa = None if imagem.isNull() else imagem
        self._passo_do_tempo(time.monotonic())
        self.adjustSize()

    def _barra_mudou(self, valor):
        """Você mexeu na barra: o número acompanha e o volume muda na hora."""
        self._mostrar_volume(valor / 100)
        self.volume.emit(valor / 100)

    def _mostrar_volume(self, volume):
        """O número e o alto-falante do lado da barra (🔇 mudo, 🔈 baixo, 🔉 médio, 🔊 alto)."""
        self.volume_texto.setText(f"{round(volume * 100)}%")
        self.icone_volume.setText("🔇" if volume == 0 else "🔈" if volume < 0.34 else "🔉" if volume < 0.67 else "🔊")

    def seguir(self, x, y, limites, pode_aparecer=True):
        """Põe o cartão ao lado do pet (centro em x, y); some se não puder aparecer."""
        if not pode_aparecer:
            if self.isVisible():
                self.hide()
            return
        self._passo_do_tempo(time.monotonic())
        self.update()                                   # a borda anda e o disco gira
        if self.solto is not None or self._arrastando:
            if self.solto is not None and not self._arrastando and self.pos() != QPoint(*self.solto):
                self.move(*self.solto)
            if not self.isVisible():
                self.show()
            return
        esquerda, topo, direita, _baixo = limites
        px = x + DISTANCIA
        if px + self.width() > direita:
            px = x - DISTANCIA - self.width()
        py = max(topo, int(y - self.height() / 2))
        self.move(int(max(esquerda, px)), int(py))
        if not self.isVisible():
            self.show()

    # ---------------- tempo e disco ----------------

    def tocando_agora(self):
        """A música está andando (nem pausada nem carregando)."""
        ctl = self._ctl
        return ctl is not None and ctl.atual is not None and not ctl.pausada and not ctl.carregando

    def _passo_do_tempo(self, agora):
        """Lê o tempo da música, atualiza o número e gira o disco (que acelera e freia suave)."""
        dt = 0.0 if self._ultimo is None else min(0.1, max(0.0, agora - self._ultimo))
        self._ultimo = agora
        ctl = self._ctl
        posicao, duracao = ctl.progresso() if ctl is not None and hasattr(ctl, "progresso") else (0.0, 0.0)
        self.fracao = min(1.0, posicao / duracao) if duracao > 0 else 0.0
        texto = f"{tempo(posicao)} / {tempo(duracao)}" if duracao > 0 and ctl.atual is not None else ""
        if self.tempo.text() != texto:
            self.tempo.setText(texto)
        alvo = GIRO if self.tocando_agora() else 0.0
        self.giro = aproximar(self.giro, alvo, dt, LIGAR_DISCO if alvo > self.giro else PARAR_DISCO)
        if self.giro < 1.0 and alvo == 0.0:
            self.giro = 0.0
        self.angulo = (self.angulo + self.giro * dt) % 360.0

    def paintEvent(self, _event):
        """Fundo, a borda que marca o tempo e o disquinho (os textos e botões vêm por cima)."""
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        caixa = QRectF(self.rect()).adjusted(1.5, 1.5, -1.5, -1.5)
        p.setPen(Qt.NoPen)
        p.setBrush(FUNDO)
        p.drawRoundedRect(caixa, RAIO, RAIO)
        self._pintar_disco(p)
        self._pintar_borda(p, caixa)
        p.end()

    def _pintar_borda(self, p, caixa):
        """A borda apagada e, por cima, o pedaço já tocado (do meio de cima, no sentido horário)."""
        caminho = contorno(caixa)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(BORDA, 1.5))
        p.drawPath(caminho)
        agora = time.monotonic()
        ctl = self._ctl
        if ctl is None or ctl.atual is None or ctl.carregando:
            inicio = (agora / VOLTA_CARREGANDO) % 1.0               # carregando: um pedaço dando voltas
            pontos = trecho(caminho, inicio, inicio + 0.14, 60)
            self._linha(p, pontos, 0.9)
            return
        if self.fracao <= 0.0:
            return
        pontos = trecho(caminho, 0.0, self.fracao)
        self._linha(p, pontos, 1.0)
        ponta = caminho.pointAtPercent(min(self.fracao, 1.0))
        pulso = 0.55 + 0.45 * math.sin(agora * math.tau * 0.9) if ctl.pausada else 1.0
        brilho = QRadialGradient(ponta, 7)
        cor = QColor(PROGRESSO)
        cor.setAlphaF(0.55 * pulso)
        brilho.setColorAt(0.0, cor)
        cor.setAlphaF(0.0)
        brilho.setColorAt(1.0, cor)
        p.setPen(Qt.NoPen)
        p.setBrush(brilho)
        p.drawEllipse(ponta, 7, 7)
        cabeca = QColor(PONTA)
        cabeca.setAlphaF(pulso)
        p.setBrush(cabeca)
        p.drawEllipse(ponta, 2.2, 2.2)

    @staticmethod
    def _linha(p, pontos, alfa):
        """Uma linha grossa e brilhante passando pelos pontos."""
        if len(pontos) < 2:
            return
        cor = QColor(PROGRESSO)
        cor.setAlphaF(alfa)
        p.setPen(QPen(cor, 2.6, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(Qt.NoBrush)
        p.drawPolyline(pontos)

    def _pintar_disco(self, p):
        """O vinil no canto: sulcos, reflexo parado (é o selo girando que mostra o giro) e o selo."""
        lugar = self.lugar_disco
        topo_esq = lugar.mapTo(self, QPoint(0, 0))
        centro = QPointF(topo_esq.x() + DISCO / 2, topo_esq.y() + DISCO / 2)
        r = DISCO / 2
        p.save()
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 90))                            # sombrinha
        p.drawEllipse(centro + QPointF(1.5, 2.0), r, r)
        vinil = QRadialGradient(centro, r)
        vinil.setColorAt(0.0, QColor("#202522"))
        vinil.setColorAt(1.0, QColor("#0b0d0c"))
        p.setBrush(vinil)
        p.drawEllipse(centro, r, r)
        p.setBrush(Qt.NoBrush)
        for i, raio in enumerate((r * 0.92, r * 0.84, r * 0.76, r * 0.68, r * 0.6)):
            p.setPen(QPen(QColor(255, 255, 255, 18 if i % 2 else 28), 0.8))
            p.drawEllipse(centro, raio, raio)
        reflexo = QConicalGradient(centro, 45)                       # o reflexo da luz não gira
        for parada, alfa in ((0.0, 0), (0.08, 38), (0.16, 0), (0.5, 0), (0.58, 30), (0.66, 0), (1.0, 0)):
            reflexo.setColorAt(parada, QColor(255, 255, 255, alfa))
        p.setPen(Qt.NoPen)
        p.setBrush(reflexo)
        p.drawEllipse(centro, r * 0.97, r * 0.97)
        selo = r * 0.5
        p.translate(centro)
        p.rotate(self.angulo)
        if self.capa is not None and self.com_capa:
            recorte = QPainterPath()
            recorte.addEllipse(QPointF(0, 0), selo, selo)
            p.setClipPath(recorte)
            lado = min(self.capa.width(), self.capa.height())
            origem = QRectF((self.capa.width() - lado) / 2, (self.capa.height() - lado) / 2, lado, lado)
            p.drawImage(QRectF(-selo, -selo, 2 * selo, 2 * selo), self.capa, origem)
            p.setClipping(False)
        else:
            p.setBrush(PROGRESSO.darker(150))
            p.drawEllipse(QPointF(0, 0), selo, selo)
            p.setPen(QPen(PROGRESSO, 1.2))
            p.setBrush(Qt.NoBrush)
            p.drawArc(QRectF(-selo * 0.7, -selo * 0.7, selo * 1.4, selo * 1.4), 30 * 16, 120 * 16)
            p.setPen(PONTA)
            p.setFont(QFont("Segoe UI Symbol", 7))
            p.drawText(QRectF(-selo, -selo, 2 * selo, 2 * selo), Qt.AlignCenter, "♪")
        p.setPen(QPen(QColor(0, 0, 0, 120), 1.0))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(QPointF(0, 0), selo, selo)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#0b0d0c"))
        p.drawEllipse(QPointF(0, 0), 1.8, 1.8)                     # o furo do meio
        p.restore()
