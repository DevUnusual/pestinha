"""
TOCANDO - o cartãozinho "tocando agora" ao lado do pet, com 👍 👎 ⏭ ⏸ ✕.

Só desenho e botões: quem toca e aprende é mind/musica_ctl.py. Cada botão vira `comando` com o mesmo
nome dos comandos do chat ('gostei', 'nao_gostei', 'pular', 'pausar'/'continuar', 'parar'). Recebe
clique mas não rouba o foco do programa que você está usando. Fica do lado direito do pet; perto da
borda da tela, passa para o esquerdo.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ..body.pet import overlay_flags, set_no_activate

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

    def __init__(self):
        """Monta o cartão escondido."""
        super().__init__(None, overlay_flags())
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
                                  ("parar", "✕", "parar a música")):
            botao = QPushButton(texto)
            botao.setToolTip(dica)
            botao.setFocusPolicy(Qt.NoFocus)
            botao.setCursor(Qt.PointingHandCursor)
            if nome in ("gostei", "nao_gostei"):
                botao.setCheckable(True)
                botao.setObjectName("nao" if nome == "nao_gostei" else "sim")
            botao.clicked.connect(lambda _marcado=False, n=nome: self._clicou(n))
            botoes.addWidget(botao)
            self.botoes[nome] = botao
        layout.addLayout(botoes)
        self._pausada = False

    def showEvent(self, event):
        """Ao aparecer, não rouba o foco."""
        super().showEvent(event)
        set_no_activate(self)

    def _clicou(self, nome):
        """Um botão: vira o comando com o nome do chat (o ⏸ alterna entre pausar e continuar)."""
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
        esquerda, topo, direita, _baixo = limites
        px = x + DISTANCIA
        if px + self.width() > direita:
            px = x - DISTANCIA - self.width()
        py = max(topo, int(y - self.height() / 2))
        self.move(int(max(esquerda, px)), int(py))
        if not self.isVisible():
            self.show()
