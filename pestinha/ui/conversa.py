"""
CONVERSA - a janelinha de chat com o pet (botão direito nele, Conversar).

É a única janela do pet que recebe o foco: você abriu para digitar. Mostra a conversa desta
sessão (nada é gravado em disco) e manda cada mensagem pelo sinal `enviar`. Quem pergunta
ao modelo é mind/visao.py.
"""

import html

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QPushButton, QTextBrowser, QVBoxLayout, QWidget

from .. import config

ESTILO = """
QWidget#conversa { background: #0c1f13; }
QLabel { color: #6f9c7b; font-size: 11px; }
QTextBrowser { background: #10251a; color: #dfffe6; border: 1px solid #24402c; border-radius: 6px;
               font-size: 13px; padding: 4px; }
QLineEdit { background: #17201a; color: #dfffe6; border: 1px solid #2c5236; border-radius: 6px;
            padding: 6px; font-size: 13px; }
QLineEdit:focus { border-color: #63e56f; }
QPushButton { background: #2c8a40; color: #dfffe6; border: 1px solid #63e56f; border-radius: 6px;
              padding: 6px 14px; font-weight: bold; }
QPushButton:disabled { background: #17201a; border-color: #2c5236; color: #4d6655; }
"""


class ConversaJanela(QWidget):
    """Chat por texto: histórico, campo de digitação e o botão Enviar."""

    enviar = Signal(str)
    esquecer = Signal()

    def __init__(self, nome):
        """Monta a janela; `nome` é o do personagem (quem responde)."""
        super().__init__(None, Qt.Tool | Qt.WindowStaysOnTopHint)
        self.nome = nome
        self.setObjectName("conversa")
        self.setAttribute(Qt.WA_StyledBackground)
        self.setStyleSheet(ESTILO)
        self.setWindowTitle(f"Conversar com {nome} · {config.APP_NOME}")
        self.resize(380, 440)

        layout = QVBoxLayout(self)
        self.historico = QTextBrowser()
        self.historico.setOpenLinks(False)
        layout.addWidget(self.historico, 1)
        self.estado = QLabel("")
        layout.addWidget(self.estado)
        linha = QHBoxLayout()
        self.campo = QLineEdit()
        self.campo.setPlaceholderText(f"Escreva para o {nome}...")
        self.campo.setMaxLength(1000)
        self.campo.returnPressed.connect(self._enviar)
        linha.addWidget(self.campo, 1)
        self.botao = QPushButton("Enviar")
        self.botao.clicked.connect(self._enviar)
        linha.addWidget(self.botao)
        layout.addLayout(linha)
        rodape = QHBoxLayout()
        self.aviso = QLabel("")
        self.aviso.setWordWrap(True)
        rodape.addWidget(self.aviso, 1)
        limpar = QPushButton("Esquecer")
        limpar.setToolTip("Apaga esta conversa (ela só existe enquanto o app está aberto)")
        limpar.clicked.connect(self._esquecer)
        rodape.addWidget(limpar)
        layout.addLayout(rodape)

    def set_aviso(self, texto):
        """Linha de baixo: qual modelo responde e se ele está vendo a tela."""
        self.aviso.setText(texto)

    def adicionar(self, quem, texto, erro=False):
        """Acrescenta uma fala ao histórico."""
        cor = "#ff9a8a" if erro else ("#63e56f" if quem == self.nome else "#9fd0ff")
        self.historico.append(f'<p><b style="color:{cor}">{html.escape(quem)}:</b> {html.escape(texto)}</p>')
        self.historico.verticalScrollBar().setValue(self.historico.verticalScrollBar().maximum())

    def set_ocupado(self, ocupado):
        """Enquanto ele pensa, não dá para mandar outra mensagem."""
        self.campo.setEnabled(not ocupado)
        self.botao.setEnabled(not ocupado)
        self.estado.setText(f"{self.nome} está pensando..." if ocupado else "")
        if not ocupado:
            self.campo.setFocus()

    def abrir(self):
        """Mostra a janela na frente, com o cursor no campo."""
        self.show()
        self.raise_()
        self.activateWindow()
        self.campo.setFocus()

    def _enviar(self):
        """Manda o que está no campo (texto vazio não vai)."""
        texto = self.campo.text().strip()
        if not texto or not self.campo.isEnabled():
            return
        self.campo.clear()
        self.adicionar("Você", texto)
        self.enviar.emit(texto)

    def _esquecer(self):
        """Limpa a tela e pede ao pet para esquecer a conversa."""
        self.historico.clear()
        self.esquecer.emit()
