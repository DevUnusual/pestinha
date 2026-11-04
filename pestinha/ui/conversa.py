"""
CONVERSA - a janelinha de chat com o pet (botão direito nele, Conversar).

É a única janela do pet que recebe o foco: você abriu para digitar. Mostra a conversa desta
sessão (nada é gravado em disco) e manda cada mensagem pelo sinal `enviar`. Quem pergunta
ao modelo é mind/visao.py. Com a voz ligada, o botão de microfone grava e a fala vira texto no campo
(quem ouve é mind/voz_ctl.py).
"""

import html

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QTextDocument
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QPushButton, QTextBrowser, QVBoxLayout, QWidget

from .. import config

LARGURA_IMAGEM = 300            # px: maior lado da imagem projetada, quando ela também aparece no chat

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
QPushButton#microfone { background: #17201a; padding: 6px 10px; }
QPushButton#microfone:checked { background: #b3261e; border-color: #ff9a8a; }
"""


class ConversaJanela(QWidget):
    """Chat por texto: histórico, campo de digitação e o botão Enviar."""

    enviar = Signal(str)
    esquecer = Signal()
    microfone = Signal()            # o botão de microfone: começa ou para de gravar

    def __init__(self, nome):
        """Monta a janela; `nome` é o do personagem (quem responde)."""
        super().__init__(None, Qt.Tool | Qt.WindowStaysOnTopHint)
        self.nome = nome
        self._imagens = 0               # quantas imagens já entraram no histórico (cada uma com seu nome)
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
        self.mic = QPushButton("🎤")
        self.mic.setObjectName("microfone")
        self.mic.setCheckable(True)
        self.mic.setToolTip("Clique e fale; clique de novo para parar. A sua fala vira texto aqui no campo.")
        self.mic.clicked.connect(lambda _marcado: self.microfone.emit())
        self.mic.setVisible(False)
        linha.addWidget(self.mic)
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

    def adicionar_imagem(self, quem, titulo, imagem):
        """Acrescenta ao histórico a imagem que ele projetou (QImage), com o título embaixo."""
        self._imagens += 1
        nome = QUrl(f"imagem-{self._imagens}.png")
        reduzida = imagem.scaled(LARGURA_IMAGEM, LARGURA_IMAGEM, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.historico.document().addResource(QTextDocument.ImageResource, nome, reduzida)
        self.historico.append(f'<p><b style="color:#63e56f">{html.escape(quem)}:</b><br>'
                              f'<img src="{nome.toString()}"><br><i>{html.escape(titulo)}</i></p>')
        self.historico.verticalScrollBar().setValue(self.historico.verticalScrollBar().maximum())

    def set_microfone(self, ligado, gravando=False, transcrevendo=False):
        """O botão de microfone: só aparece com a voz ligada; vermelho enquanto grava."""
        self.mic.setVisible(ligado)
        self.mic.setChecked(gravando)
        self.mic.setEnabled(ligado and not transcrevendo)
        if gravando:
            self.estado.setText("Ouvindo... clique no microfone para parar.")
        elif transcrevendo:
            self.estado.setText("Transformando a sua fala em texto...")
        elif self.estado.text().startswith(("Ouvindo", "Transformando")):
            self.estado.setText("")

    def ditar(self, texto):
        """O texto da sua fala entra no campo (depois do que já estava escrito), para conferir e mandar."""
        atual = self.campo.text().rstrip()
        self.campo.setText(f"{atual} {texto}".strip()[:self.campo.maxLength()])
        self.campo.setFocus()
        self.campo.end(False)

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
