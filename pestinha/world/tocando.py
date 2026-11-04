"""
TOCANDO - o cartãozinho "tocando agora" ao lado do pet, com 👍 👎 ⏭ ⏸ ✕.

Só desenho e botões: quem toca e aprende é mind/musica_ctl.py. Cada botão vira `comando` com o mesmo
nome dos comandos do chat ('gostei', 'nao_gostei', 'pular', 'pausar'/'continuar', 'parar'). Recebe
clique mas não rouba o foco do programa que você está usando. Fica do lado direito do pet; perto da
borda da tela, passa para o esquerdo.

Para não ter que caçar o pet andando: arraste o cartão (fora dos botões) ou clique no 📌 e ele fica
parado onde está, até você clicar no 📌 de novo. Solto, a posição fica em memory/panels.json.
"""

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ..body.pet import overlay_flags, set_no_activate
from ..store import write_json
from .arrastavel import load_positions, posicao_acessivel

CHAVE = "tocando"           # em memory/panels.json: [x, y] quando solto; ausente quando segue o pet
ARRASTE_MIN = 4             # px antes de um clique virar arraste

LARGURA = 230               # px do cartão
DISTANCIA = 70              # px do centro do pet até a borda do cartão
ESTILO = """
QFrame#cartao { background: rgba(12, 31, 19, 235); border: 1px solid #2c5236; border-radius: 10px; }
QLabel { color: #dfffe6; font-size: 11px; }
QLabel#rotulo { color: #63e56f; font-size: 10px; font-weight: bold; }
QPushButton { background: #17201a; color: #dfffe6; border: 1px solid #2c5236; border-radius: 6px;
              padding: 2px 0; font-size: 13px; min-width: 30px; }
QPushButton:hover { border-color: #63e56f; }
QPushButton:checked { background: #2c8a40; border-color: #63e56f; }
QPushButton#nao:checked { background: #b3261e; border-color: #ff9a8a; }
"""


class Tocando(QWidget):
    """O cartão: atualizar(controle) e, a cada quadro, seguir(x, y, limites)."""

    comando = Signal(str)

    def __init__(self, arquivo=None):
        """Monta o cartão escondido; `arquivo` é o panels.json (lembra se ele está solto, e onde)."""
        super().__init__(None, overlay_flags())
        self.arquivo = arquivo
        self.solto = None               # (x, y) onde você deixou; None: segue o pet
        self._pego = None               # (onde o mouse apertou, posição do cartão nessa hora)
        self._arrastando = False
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
        self.rotulo = QLabel("♪ TOCANDO")
        self.rotulo.setObjectName("rotulo")
        layout.addWidget(self.rotulo)
        self.titulo = QLabel("")
        self.titulo.setWordWrap(True)
        layout.addWidget(self.titulo)
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
        self._pausada = False
        self.adjustSize()
        salvo = load_positions(arquivo).get(CHAVE) if arquivo is not None else None
        if salvo is not None:
            self.solto = posicao_acessivel(salvo, (20, 20), (self.width(), self.height()))
        self._marcar_fixo()

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

    def _marcar_fixo(self):
        """O 📌 aceso quando ele está solto."""
        botao = self.botoes["fixar"]
        botao.setChecked(self.solto is not None)
        botao.setToolTip("grudar de volta no pet" if self.solto else "deixar o player parado aqui")

    def _gravar(self):
        """Lembra (ou esquece) a posição solta em panels.json."""
        if self.arquivo is None:
            return
        dados = load_positions(self.arquivo)
        if self.solto is None:
            dados.pop(CHAVE, None)
        else:
            dados[CHAVE] = list(self.solto)
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
        """Mostra o que o controle de música está fazendo (música, pausa, opinião já dada)."""
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
        self.adjustSize()

    def seguir(self, x, y, limites, pode_aparecer=True):
        """Põe o cartão ao lado do pet (centro em x, y); some se não puder aparecer."""
        if not pode_aparecer:
            if self.isVisible():
                self.hide()
            return
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
