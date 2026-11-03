"""
UI - tela inicial de permissões, ícone na bandeja e atalho de pânico.
"""

from .. import plataforma

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QAction, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSystemTrayIcon,
    QWidget,
    QVBoxLayout,
)

from .. import config, memoria_remota
from ..ia import chaves, pesquisa, provedores, voz
from ..sense import timeline
from ..core.emotion import EYE_SHAPES
from ..body.pet import draw_face

STYLE = """
QDialog { background: #0c1f13; }
QScrollArea { background: #0c1f13; border: none; }
QWidget#conteudo, QWidget#qt_scrollarea_viewport { background: #0c1f13; }
QLabel { color: #b9f5c8; }
QLabel#title { color: #63e56f; font: bold 20px 'Consolas'; }
QLabel#hint { color: #6f9c7b; font-size: 11px; }
QGroupBox { color: #63e56f; font: bold 12px; border: 1px solid #24402c;
            border-radius: 8px; margin-top: 14px; padding: 10px 8px 6px 8px; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
QCheckBox { color: #dfffe6; font-size: 13px; spacing: 8px; }
QCheckBox:disabled { color: #4d6655; }
QComboBox, QLineEdit { background: #17201a; color: #dfffe6; border: 1px solid #2c5236; padding: 3px 6px; }
QComboBox:disabled, QLineEdit:disabled { color: #4d6655; }
QPushButton { background: #17201a; color: #dfffe6; border: 1px solid #2c5236;
              border-radius: 6px; padding: 7px 18px; font-size: 13px; }
QPushButton#start { background: #2c8a40; border-color: #63e56f; font-weight: bold; }
QLabel#ok { color: #63e56f; font-size: 12px; font-weight: bold; }
QLabel#erro { color: #ff9a8a; font-size: 12px; font-weight: bold; }
QPushButton:hover { border-color: #63e56f; }
"""


def face_icon(emotion="observando"):
    """Ícone da bandeja e das janelas: o rosto do pet desenhado numa imagem pequena."""
    pix = QPixmap(128, 128)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    p.translate(64, 64)
    p.scale(0.95, 0.95)
    draw_face(p, EYE_SHAPES[emotion])
    p.end()
    return QIcon(pix)


class SettingsDialog(QDialog):
    """
    Tela inicial (e de configurações, pela bandeja). Cada mudança é gravada
    na hora e avisada por `changed`, então vale na sessão em andamento.
    """

    changed = Signal(dict)
    chave_salva = Signal(str)          # nome da variável (ANTHROPIC_API_KEY...) que acabou de ser salva no .env
    wipe_all = Signal()
    history_wiped = Signal()

    def __init__(self, perms, paths, first_run=True):
        """Tela de permissões e configurações. Trabalha numa cópia das permissões: cada mudança é avisada ao app na hora."""
        super().__init__()
        self.perms = dict(perms)           # cópia: só o app grava, pela transição certa
        self.paths = paths
        self.setWindowTitle(config.APP_NOME)
        self.setWindowIcon(face_icon())
        self.setStyleSheet(STYLE)
        self.setMinimumWidth(460)
        # cabe na tela: o conteúdo rola dentro da janela, e o botão de começar fica sempre visível
        screen = QApplication.primaryScreen().availableGeometry()
        self.resize(500, min(760, int(screen.height() * 0.85)))
        outer = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(scroll.Shape.NoFrame)
        content = QWidget()
        content.setObjectName("conteudo")
        scroll.setWidget(content)
        outer.addWidget(scroll, 1)
        self._outer = outer
        self.boxes = {}

        root = QVBoxLayout(content)
        root.setSpacing(8)
        title = QLabel(config.APP_NOME.upper())
        title.setObjectName("title")
        root.addWidget(title)
        if first_run:
            welcome = QLabel(
                f"Bem-vindo! O {config.APP_NOME} vê só o nome dos programas, o tempo sem usar o teclado e "
                "as janelas para pousar. Só enxerga a sua tela se você ligar \"Ver minha tela\" na parte "
                "de IA. Detalhes em PRIVACIDADE.md.\n"
                "Escolha abaixo o que ele pode fazer e clique em Começar. Tudo pode ser mudado depois.")
            welcome.setObjectName("hint")
            welcome.setWordWrap(True)
            root.addWidget(welcome)
        hint = QLabel("Escolha o que o pet pode fazer nesta sessão. Fica salvo para a próxima.")
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        root.addWidget(hint)

        top = QGroupBox(config.APP_NOME)
        top_layout = QVBoxLayout(top)
        self.active_box = QCheckBox(f"{config.APP_NOME} ligado")
        self.active_box.setChecked(perms["ativo"])
        self.active_box.toggled.connect(lambda on: self._set("ativo", on))
        top_layout.addWidget(self.active_box)
        if not perms["ativo"]:
            warn = QLabel(f"O pânico desligou o {config.APP_NOME} na última vez. Marque acima para religar.")
            warn.setObjectName("hint")
            warn.setWordWrap(True)
            top_layout.addWidget(warn)

        pet_row = QHBoxLayout()
        pet_row.addWidget(QLabel("Personagem:"))
        self.pet_combo = QComboBox()
        for pet_id in config.list_pets(self.paths):            # só pets/<id>.json; memória antiga não conta
            self.pet_combo.addItem(config.load_pet(self.paths, pet_id)["nome"], pet_id)
        atual = config.escolher_pet(self.paths, perms["pet"])
        self.pet_combo.setCurrentIndex(max(0, self.pet_combo.findData(atual)))
        self.pet_combo.currentIndexChanged.connect(self._trocar_pet)
        pet_row.addWidget(self.pet_combo, 1)
        top_layout.addLayout(pet_row)
        self.pet_aviso = QLabel("Vale na próxima vez que abrir. Cada personagem tem a própria memória.")
        self.pet_aviso.setObjectName("hint")
        self.pet_aviso.setWordWrap(True)
        self.pet_aviso.setVisible(not first_run)
        top_layout.addWidget(self.pet_aviso)
        root.addWidget(top)

        for group_title, items in config.PERMISSION_GROUPS:
            group = QGroupBox(group_title)
            layout = QVBoxLayout(group)
            for key, label, description in items:
                box = QCheckBox(label)
                box.setChecked(bool(perms[key]))
                box.setToolTip(description)
                box.toggled.connect(lambda on, k=key: self._set(k, on))
                self.boxes[key] = box
                layout.addWidget(box)
                desc = QLabel(description)
                desc.setObjectName("hint")
                desc.setWordWrap(True)
                desc.setContentsMargins(26, 0, 0, 4)
                layout.addWidget(desc)
            if group_title == "Travessuras":
                self.resumo = self._asset_summary()
                layout.addWidget(self.resumo)
            if group_title == "Rotina":
                row = QHBoxLayout()
                self.history_label = QLabel()
                self.history_label.setObjectName("hint")
                row.addWidget(self.history_label, 1)
                wipe = QPushButton("Apagar histórico")
                wipe.clicked.connect(self._wipe_history)
                row.addWidget(wipe)
                layout.addLayout(row)
                everything = QPushButton(f"Apagar todos os dados do {config.APP_NOME}")
                everything.clicked.connect(self._wipe_everything)
                layout.addWidget(everything)
                self._update_history_label()
            if group_title == "Visão e conversa (IA)":
                self._montar_provedor(layout)
                self._montar_voz(layout)
                self._montar_pesquisa(layout)
            if group_title == "Memória em outro computador":
                self._montar_memoria(layout)
            root.addWidget(group)

        panic = QLabel(f"Pânico (desliga tudo e fica desligado): {config.PANIC_HOTKEY_TEXT}")
        panic.setObjectName("hint")
        root.addWidget(panic)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        if first_run:
            leave = QPushButton("Sair")
            leave.clicked.connect(self.reject)
            buttons.addWidget(leave)
            go = QPushButton("Começar")
            go.setObjectName("start")
            go.clicked.connect(self.accept)
        else:
            go = QPushButton("Fechar")
            go.setObjectName("start")
            go.clicked.connect(self.accept)
        buttons.addWidget(go)
        self._outer.addLayout(buttons)

        self._sync_enabled()

    def _montar_provedor(self, layout):
        """Escolha do provedor e do modelo, e onde fica a chave (variável de ambiente, nunca em arquivo)."""
        linha = QHBoxLayout()
        linha.addWidget(QLabel("Provedor:"))
        self.provedor_combo = QComboBox()
        for chave, dados in provedores.PROVEDORES.items():
            self.provedor_combo.addItem(dados["nome"], chave)
        self.provedor_combo.setCurrentIndex(max(0, self.provedor_combo.findData(self.perms["ia_provedor"])))
        self.provedor_combo.currentIndexChanged.connect(self._trocar_provedor)
        linha.addWidget(self.provedor_combo, 1)
        layout.addLayout(linha)
        linha = QHBoxLayout()
        linha.addWidget(QLabel("Modelo:"))
        self.modelo_campo = QLineEdit(self.perms["ia_modelo"])
        self.modelo_campo.setMaxLength(100)
        self.modelo_campo.editingFinished.connect(self._trocar_modelo)
        linha.addWidget(self.modelo_campo, 1)
        layout.addLayout(linha)
        self.ollama_linha = QWidget()
        linha = QHBoxLayout(self.ollama_linha)
        linha.setContentsMargins(0, 0, 0, 0)
        linha.addWidget(QLabel("Endereço:"))
        self.ollama_campo = QLineEdit(self.perms["ia_ollama_url"])
        self.ollama_campo.setPlaceholderText(f"{provedores.OLLAMA_PADRAO} (este computador)")
        self.ollama_campo.setMaxLength(200)
        self.ollama_campo.editingFinished.connect(self._trocar_endereco)
        linha.addWidget(self.ollama_campo, 1)
        self.ollama_botao = QPushButton("Testar conexão")
        self.ollama_botao.clicked.connect(self._testar_ollama)
        linha.addWidget(self.ollama_botao)
        layout.addWidget(self.ollama_linha)
        self.chave_linha = QWidget()
        linha = QHBoxLayout(self.chave_linha)
        linha.setContentsMargins(0, 0, 0, 0)
        linha.addWidget(QLabel("Chave:"))
        self.chave_campo = QLineEdit()
        self.chave_campo.setEchoMode(QLineEdit.Password)     # não aparece na tela
        self.chave_campo.setMaxLength(400)
        self.chave_campo.returnPressed.connect(self._salvar_chave)
        linha.addWidget(self.chave_campo, 1)
        self.chave_botao = QPushButton("Salvar chave")
        self.chave_botao.clicked.connect(self._salvar_chave)
        linha.addWidget(self.chave_botao)
        layout.addWidget(self.chave_linha)
        self.chave_estado = QLabel()
        self.chave_estado.setWordWrap(True)
        layout.addWidget(self.chave_estado)
        self.provedor_dica = QLabel()
        self.provedor_dica.setObjectName("hint")
        self.provedor_dica.setWordWrap(True)
        layout.addWidget(self.provedor_dica)
        self._atualizar_provedor()

    def _montar_voz(self, layout):
        """Onde fica o serviço de voz (servidor/voz/), que transforma a sua fala em texto."""
        linha = QHBoxLayout()
        linha.addWidget(QLabel("Servidor da voz:"))
        self.voz_campo = QLineEdit(self.perms["voz_url"])
        self.voz_campo.setPlaceholderText(f"vazio = este computador ({voz.VOZ_URL_PADRAO})")
        self.voz_campo.setMaxLength(200)
        self.voz_campo.editingFinished.connect(self._trocar_endereco_voz)
        linha.addWidget(self.voz_campo, 1)
        self.voz_botao = QPushButton("Testar voz")
        self.voz_botao.clicked.connect(self._testar_voz)
        linha.addWidget(self.voz_botao)
        layout.addLayout(linha)
        self.voz_dica = QLabel("O computador que transforma a sua fala em texto (o serviço da pasta "
                               "servidor/voz/, precisa de placa de vídeo). Se ele roda em outro computador "
                               "da casa, digite o IP dele, por exemplo 192.168.0.10. O áudio vai só para lá.")
        self.voz_dica.setObjectName("hint")
        self.voz_dica.setWordWrap(True)
        layout.addWidget(self.voz_dica)
        self.voz_estado = QLabel()
        self.voz_estado.setWordWrap(True)
        self.voz_estado.setVisible(False)
        layout.addWidget(self.voz_estado)

    def _montar_pesquisa(self, layout):
        """Onde fica o Hermes, que pesquisa na internet para ele, e a chave da API dele."""
        linha = QHBoxLayout()
        linha.addWidget(QLabel("Endereço do Hermes:"))
        self.hermes_campo = QLineEdit(self.perms["hermes_url"])
        self.hermes_campo.setPlaceholderText(f"vazio = este computador ({pesquisa.HERMES_PADRAO})")
        self.hermes_campo.setMaxLength(200)
        self.hermes_campo.editingFinished.connect(self._trocar_endereco_hermes)
        linha.addWidget(self.hermes_campo, 1)
        self.hermes_botao = QPushButton("Testar Hermes")
        self.hermes_botao.clicked.connect(self._testar_hermes)
        linha.addWidget(self.hermes_botao)
        layout.addLayout(linha)
        linha = QHBoxLayout()
        linha.addWidget(QLabel("Chave do Hermes:"))
        self.hermes_chave = QLineEdit()
        self.hermes_chave.setEchoMode(QLineEdit.Password)
        self.hermes_chave.setMaxLength(400)
        final = chaves.final_da_chave(pesquisa.CHAVE)
        self.hermes_chave.setPlaceholderText(f"salva (termina em …{final})" if final
                                             else "cole aqui a API_SERVER_KEY do Hermes")
        self.hermes_chave.returnPressed.connect(self._salvar_chave_hermes)
        linha.addWidget(self.hermes_chave, 1)
        self.hermes_salvar = QPushButton("Salvar chave")
        self.hermes_salvar.clicked.connect(self._salvar_chave_hermes)
        linha.addWidget(self.hermes_salvar)
        layout.addLayout(linha)
        dica = QLabel("O Hermes é um agente com ferramentas que roda num computador seu (hermes gateway, com "
                      "API_SERVER_KEY no .env dele). Deixe a plataforma api_server dele só com a ferramenta "
                      "de pesquisa: o que aparece na tela pode tentar dar ordens a ele.")
        dica.setObjectName("hint")
        dica.setWordWrap(True)
        layout.addWidget(dica)
        self.hermes_estado = QLabel()
        self.hermes_estado.setWordWrap(True)
        self.hermes_estado.setVisible(False)
        layout.addWidget(self.hermes_estado)

    def _trocar_endereco_hermes(self):
        """Grava o endereço do Hermes já completo (http:// e a porta); um endereço ruim é recusado."""
        base = pesquisa.endereco_hermes(self.hermes_campo.text().strip())
        if base is None:
            self._mostrar_estado_hermes("Endereço inválido. Exemplos: 192.168.0.10 ou http://192.168.0.10:8642",
                                        erro=True)
            self.hermes_campo.setText(self.perms["hermes_url"])
            return
        valor = "" if base == pesquisa.HERMES_PADRAO else base
        self.hermes_campo.setText(valor)
        if valor != self.perms["hermes_url"]:
            self._set("hermes_url", valor)
            self._mostrar_estado_hermes("")

    def _salvar_chave_hermes(self):
        """Grava a chave do Hermes no .env e apaga do campo."""
        valor = self.hermes_chave.text().strip()
        self.hermes_chave.clear()
        if not valor:
            self._mostrar_estado_hermes("Cole a chave no campo antes de salvar.", erro=True)
            return
        try:
            chaves.salvar_chave(self.paths.env, pesquisa.CHAVE, valor)
        except (ValueError, OSError) as erro:
            self._mostrar_estado_hermes(f"Não salvou: {erro}", erro=True)
            return
        self.hermes_chave.setPlaceholderText(f"salva (termina em …{valor[-4:]})")
        self._mostrar_estado_hermes(f"✔ Chave salva (termina em …{valor[-4:]}). Já está valendo.")
        self.chave_salva.emit(pesquisa.CHAVE)

    def _testar_hermes(self):
        """Pergunta ao Hermes se ele responde e aceita a chave (espera uns segundos no máximo)."""
        self._trocar_endereco_hermes()
        self.hermes_botao.setEnabled(False)
        self.hermes_botao.setText("Testando...")
        QApplication.processEvents()
        try:
            ok, mensagem = pesquisa.testar_hermes(self.perms["hermes_url"])
        finally:
            self.hermes_botao.setText("Testar Hermes")
            self._sync_enabled()
        self._mostrar_estado_hermes(("✔ " if ok else "") + mensagem, erro=not ok)

    def _mostrar_estado_hermes(self, texto, erro=False):
        """Linha de aviso do Hermes: verde quando deu certo, vermelha quando não."""
        self.hermes_estado.setObjectName("erro" if erro else "ok")
        self.hermes_estado.setStyleSheet("")
        self.hermes_estado.setText(texto)
        self.hermes_estado.setVisible(bool(texto))

    def _montar_memoria(self, layout):
        """Onde fica o serviço de memória (servidor/memoria/), que guarda o pet para todos os computadores."""
        linha = QHBoxLayout()
        linha.addWidget(QLabel("Servidor da memória:"))
        self.memoria_campo = QLineEdit(self.perms["memoria_url"])
        self.memoria_campo.setPlaceholderText("ex.: 192.168.0.10")
        self.memoria_campo.setMaxLength(200)
        self.memoria_campo.editingFinished.connect(self._trocar_endereco_memoria)
        linha.addWidget(self.memoria_campo, 1)
        self.memoria_botao = QPushButton("Testar memória")
        self.memoria_botao.clicked.connect(self._testar_memoria)
        linha.addWidget(self.memoria_botao)
        layout.addLayout(linha)
        dica = QLabel(f"Este computador aparece lá como \"{memoria_remota.maquina_atual()}\" "
                      f"({memoria_remota.sistema_atual()}). Sem internet ou com o servidor desligado, ele "
                      "usa a memória daqui e sincroniza quando der.")
        dica.setObjectName("hint")
        dica.setWordWrap(True)
        layout.addWidget(dica)
        self.memoria_estado = QLabel()
        self.memoria_estado.setWordWrap(True)
        self.memoria_estado.setVisible(False)
        layout.addWidget(self.memoria_estado)

    def _trocar_endereco_memoria(self):
        """Grava o endereço do serviço de memória já completo (http:// e a porta); um endereço ruim é recusado."""
        texto = self.memoria_campo.text().strip()
        base = memoria_remota.endereco_memoria(texto) if texto else ""
        if base is None:
            self._mostrar_estado_memoria("Endereço inválido. Exemplos: 192.168.0.10 ou http://192.168.0.10:11600",
                                         erro=True)
            self.memoria_campo.setText(self.perms["memoria_url"])
            return
        self.memoria_campo.setText(base)
        if base != self.perms["memoria_url"]:
            self._set("memoria_url", base)
            self._mostrar_estado_memoria("Vale na próxima vez que abrir.")

    def _testar_memoria(self):
        """Pergunta ao serviço de memória se ele responde (espera uns segundos no máximo)."""
        self._trocar_endereco_memoria()
        self.memoria_botao.setEnabled(False)
        self.memoria_botao.setText("Testando...")
        QApplication.processEvents()
        try:
            ok, mensagem = memoria_remota.testar_memoria(self.perms["memoria_url"])
        finally:
            self.memoria_botao.setText("Testar memória")
            self._sync_enabled()
        self._mostrar_estado_memoria(("✔ " if ok else "") + mensagem, erro=not ok)

    def _mostrar_estado_memoria(self, texto, erro=False):
        """Linha de aviso do serviço de memória: verde quando deu certo, vermelha quando não."""
        self.memoria_estado.setObjectName("erro" if erro else "ok")
        self.memoria_estado.setStyleSheet("")
        self.memoria_estado.setText(texto)
        self.memoria_estado.setVisible(bool(texto))

    def _trocar_endereco_voz(self):
        """Grava o endereço do serviço de voz já completo (http:// e a porta); um endereço ruim é recusado."""
        base = voz.endereco_voz(self.voz_campo.text().strip())
        if base is None:
            self._mostrar_estado_voz("Endereço inválido. Exemplos: 192.168.0.10 ou http://192.168.0.10:11500",
                                     erro=True)
            self.voz_campo.setText(self.perms["voz_url"])
            return
        valor = "" if base == voz.VOZ_URL_PADRAO else base
        self.voz_campo.setText(valor)
        if valor != self.perms["voz_url"]:
            self._set("voz_url", valor)
            self._mostrar_estado_voz("")

    def _testar_voz(self):
        """Pergunta ao serviço de voz se ele responde (espera uns segundos no máximo)."""
        self._trocar_endereco_voz()
        self.voz_botao.setEnabled(False)
        self.voz_botao.setText("Testando...")
        QApplication.processEvents()
        try:
            ok, mensagem = voz.testar_voz(self.perms["voz_url"])
        finally:
            self.voz_botao.setText("Testar voz")
            self._sync_enabled()
        self._mostrar_estado_voz(("✔ " if ok else "") + mensagem, erro=not ok)

    def _mostrar_estado_voz(self, texto, erro=False):
        """Linha de aviso do serviço de voz: verde quando deu certo, vermelha quando não."""
        self.voz_estado.setObjectName("erro" if erro else "ok")
        self.voz_estado.setStyleSheet("")
        self.voz_estado.setText(texto)
        self.voz_estado.setVisible(bool(texto))

    def _trocar_provedor(self, _indice):
        """Outro provedor: o modelo volta para o padrão dele."""
        self._set("ia_provedor", self.provedor_combo.currentData())
        self.modelo_campo.setText("")
        self._set("ia_modelo", "")
        self.chave_campo.clear()
        self._atualizar_provedor()

    def _trocar_modelo(self):
        """Grava o modelo. Uma chave colada aqui por engano é recusada e apagada da tela."""
        texto = self.modelo_campo.text().strip()
        if chaves.parece_chave(texto):
            self.modelo_campo.clear()
            self._set("ia_modelo", "")
            self._mostrar_estado_chave("Isso parece uma chave, não um modelo. Cole a chave no campo Chave "
                                       "e clique em Salvar chave.", erro=True)
            return
        self._set("ia_modelo", texto)

    def _trocar_endereco(self):
        """Grava o endereço do Ollama já completo (http:// e a porta); um endereço ruim é recusado."""
        texto = self.ollama_campo.text().strip()
        base = provedores.endereco_ollama(texto)
        if base is None:
            self._mostrar_estado_chave("Endereço inválido. Exemplos: 192.168.0.10 ou http://192.168.0.10:11434",
                                       erro=True)
            self.ollama_campo.setText(self.perms["ia_ollama_url"])
            return
        valor = "" if base == provedores.OLLAMA_PADRAO else base
        self.ollama_campo.setText(valor)
        if valor != self.perms["ia_ollama_url"]:
            self._set("ia_ollama_url", valor)
            self._mostrar_estado_chave("")

    def _testar_ollama(self):
        """Pergunta ao Ollama se ele responde e se tem o modelo escolhido (espera no máximo uns segundos)."""
        self._trocar_endereco()
        self.ollama_botao.setEnabled(False)
        self.ollama_botao.setText("Testando...")
        QApplication.processEvents()
        try:
            ok, mensagem = provedores.testar_ollama(self.perms["ia_ollama_url"], self.perms["ia_modelo"])
        finally:
            self.ollama_botao.setText("Testar conexão")
            self.ollama_botao.setEnabled(self.perms["ia"])
        self._mostrar_estado_chave(("\u2714 " if ok else "") + mensagem, erro=not ok)

    def _salvar_chave(self):
        """Grava a chave no .env, apaga do campo e avisa que deu certo (ou por que não deu)."""
        dados = provedores.info(self.perms["ia_provedor"])
        valor = self.chave_campo.text().strip()
        self.chave_campo.clear()                        # some da tela, dando certo ou não
        if not dados["chave"]:
            return
        if not valor:
            self._mostrar_estado_chave("Cole a chave no campo antes de salvar.", erro=True)
            return
        try:
            chaves.salvar_chave(self.paths.env, dados["chave"], valor)
        except (ValueError, OSError) as erro:
            self._mostrar_estado_chave(f"Não salvou: {erro}", erro=True)
            return
        self._mostrar_estado_chave(f"✔ Chave salva (termina em …{valor[-4:]}). Já está valendo.")
        self.chave_salva.emit(dados["chave"])

    def _mostrar_estado_chave(self, texto, erro=False):
        """Linha de aviso embaixo da chave: verde quando deu certo, vermelha quando não."""
        self.chave_estado.setObjectName("erro" if erro else "ok")
        self.chave_estado.setStyleSheet("")             # reaplica o estilo do novo objectName
        self.chave_estado.setText(texto)
        self.chave_estado.setVisible(bool(texto))

    def _atualizar_provedor(self):
        """Modelo padrão no campo vazio e a dica de onde fica a chave."""
        dados = provedores.info(self.perms["ia_provedor"])
        self.modelo_campo.setPlaceholderText(f"padrão: {dados['modelo']}")
        self.chave_linha.setVisible(bool(dados["chave"]))
        self.ollama_linha.setVisible(self.perms["ia_provedor"] == "ollama")
        if dados["chave"]:
            final = chaves.final_da_chave(dados["chave"])
            self.chave_campo.setPlaceholderText(f"cole aqui a chave ({dados['chave']})")
            if final:
                self._mostrar_estado_chave(f"✔ Chave configurada (termina em …{final}).")
            else:
                self._mostrar_estado_chave("Nenhuma chave configurada para este provedor.", erro=True)
            dica = ("A chave é gravada no arquivo .env da pasta do Pestinha (fora do git e da pasta memory/) "
                    "e não aparece mais na tela depois de salva. Cada olhada e cada mensagem custam um "
                    "pouco na conta do provedor.")
        else:
            dica = ("Roda num computador seu (este ou outro da rede), sem internet e sem custo. Recomendado: "
                    f"{dados['recomendado']} (ollama pull {dados['recomendado']}), que cabe numa placa de vídeo "
                    "de 8 GB. Para usar outro PC, ponha o endereço dele acima; lá, o Ollama precisa aceitar "
                    "conexões da rede (OLLAMA_HOST=0.0.0.0).")
            self._mostrar_estado_chave("")
        if not dados["ve_imagem"]:
            dica += " Este provedor não vê imagem: ele conhece só o nome do programa e o título da janela."
        self.provedor_dica.setText(dica)

    def _asset_summary(self):
        """Linha de resumo do conteúdo do pet escolhido (memes, fotos, recadinhos)."""
        label = QLabel()
        label.setWordWrap(True)
        label.setObjectName("hint")
        self.resumo = label
        self._atualizar_resumo()
        return label

    def _atualizar_resumo(self):
        """Recalcula o resumo do conteúdo quando o personagem muda."""
        if not hasattr(self, "resumo"):
            return
        pet = config.escolher_pet(self.paths, self.perms["pet"])
        conteudo = self.paths.conteudo(pet)
        memes = sum(len(config.list_images(conteudo.memes / e)) for e in config.EMOTIONS)
        trabalho = len(config.list_images(conteudo.memes_trabalho))
        photos = len(config.list_images(conteudo.fotos))
        notes = config.Notes(conteudo.notes)
        notes._reload()
        tristes = config.Notes(conteudo.notes_sad)
        tristes._reload()
        nome = config.load_pet(self.paths, pet)["nome"]
        self.resumo.setText(f"Conteúdo de {nome}: {memes} memes de emoção, {trabalho} de trabalho, {photos} fotos, "
                            f"{len(notes.lines)} recadinhos e {len(tristes.lines)} bilhetes tristes.")

    def _update_history_label(self):
        """Mostra quantos minutos de rotina estão gravados."""
        minutes = timeline.count_rows(self.paths.timeline)
        self.history_label.setText(f"Histórico: {minutes} minutos ({minutes / 60:.1f} h) gravados.")

    def _wipe_history(self):
        """Apaga a rotina (timeline.csv) depois de pedir confirmação."""
        answer = QMessageBox.question(
            self, "Apagar histórico",
            "Apagar todo o histórico da sua rotina (memory/timeline.csv)? Não dá para desfazer.",
        )
        if answer == QMessageBox.Yes:
            try:
                self.paths.timeline.unlink(missing_ok=True)
            except OSError as error:
                QMessageBox.warning(self, "Apagar histórico", f"Não deu para apagar: {error}")
            self.history_wiped.emit()             # o app descarta também o minuto que ainda está em RAM
            self._update_history_label()

    def _wipe_everything(self):
        """Apaga todos os dados do app depois de pedir confirmação; o app fecha em seguida."""
        answer = QMessageBox.question(
            self, "Apagar todos os dados",
            f"Apagar tudo que o {config.APP_NOME} guardou (pasta memory/: a memória de todos os "
            f"personagens, histórico, painéis, permissões)? O {config.APP_NOME} vai fechar. Não dá para desfazer.",
        )
        if answer == QMessageBox.Yes:
            self.wipe_all.emit()

    def _trocar_pet(self, _indice):
        """Só grava a escolha: o pet que está na tela continua até reabrir (a memória dele é outra)."""
        self._set("pet", self.pet_combo.currentData())
        self._atualizar_resumo()

    def _set(self, key, value):
        """Grava uma permissão e avisa o app só dessa mudança."""
        self.perms[key] = value
        self._sync_enabled()
        self.changed.emit({key: value})          # só o campo mudado: o resto é do app

    def _sync_enabled(self):
        """Liga ou desliga os itens que dependem de 'Travessuras' (memes, fotos, bilhetes)."""
        master = self.perms["travessuras"]
        for key in ("memes", "fotos", "bilhetes"):
            self.boxes[key].setEnabled(master)
        self.boxes["mostrar_emocao"].setEnabled(self.perms["modo_teste"])
        ia = self.perms["ia"]
        for key in ("ver_tela", "conversa"):
            self.boxes[key].setEnabled(ia)
        self.boxes["comentarios"].setEnabled(ia and self.perms["ver_tela"])
        self.boxes["jogos"].setEnabled(ia and self.perms["ver_tela"])
        self.boxes["voz"].setEnabled(ia and self.perms["conversa"])
        self.boxes["lembrar"].setEnabled(ia and self.perms["ver_tela"])
        self.boxes["pesquisar"].setEnabled(ia and self.perms["ver_tela"])
        if hasattr(self, "hermes_campo"):
            com_pesquisa = ia and self.perms["ver_tela"] and self.perms["pesquisar"]
            for campo in (self.hermes_campo, self.hermes_botao, self.hermes_chave, self.hermes_salvar):
                campo.setEnabled(com_pesquisa)
        if hasattr(self, "memoria_campo"):
            for campo in (self.memoria_campo, self.memoria_botao):
                campo.setEnabled(self.perms["memoria_compartilhada"])
        if hasattr(self, "voz_campo"):
            com_voz = ia and self.perms["conversa"] and self.perms["voz"]
            for campo in (self.voz_campo, self.voz_botao):
                campo.setEnabled(com_voz)
        if hasattr(self, "provedor_combo"):
            for campo in (self.provedor_combo, self.modelo_campo, self.chave_campo, self.chave_botao,
                          self.ollama_campo, self.ollama_botao):
                campo.setEnabled(ia)

    def set_active(self, on):
        """Atualiza a caixa 'ligado' sem disparar a gravação (usado pelo pânico)."""
        self.active_box.blockSignals(True)
        self.active_box.setChecked(on)
        self.active_box.blockSignals(False)


class Tray(QObject):
    """Ícone da bandeja do sistema, com o menu de controle do pet."""
    open_settings = Signal()
    open_monitor = Signal()
    open_panel = Signal()
    toggle_floating = Signal()
    toggle_pause = Signal()
    toggle_hidden = Signal()
    clear_things = Signal()
    panic = Signal()
    quit = Signal()

    def __init__(self, nome):
        """Cria o ícone e o menu; cada item emite um sinal que o app ouve."""
        super().__init__()
        self.titulo = f"{config.APP_NOME} · {nome}"
        self.icon = QSystemTrayIcon(face_icon())
        self.icon.setToolTip(self.titulo)
        menu = QMenu()
        self.actions = {}
        for key, text, signal in [
            ("settings", "Configurações...", self.open_settings),
            ("monitor", "Monitor neural", self.open_monitor),
            ("panel", "Painel de protesto", self.open_panel),
            ("floating", "Esconder painéis de teste", self.toggle_floating),
            ("pause", "Pausar", self.toggle_pause),
            ("hide", "Esconder", self.toggle_hidden),
            ("clear", "Limpar travessuras", self.clear_things),
            ("panic", f"Pânico ({config.PANIC_HOTKEY_TEXT})", self.panic),
            ("quit", "Sair", self.quit),
        ]:
            action = QAction(text, menu)
            action.triggered.connect(signal.emit)
            menu.addAction(action)
            self.actions[key] = action
            if key in ("hide", "panic"):
                menu.addSeparator()
        self.menu = menu
        self.icon.setContextMenu(menu)
        self.icon.activated.connect(
            lambda reason: self.open_settings.emit() if reason == QSystemTrayIcon.DoubleClick else None
        )
        self.icon.show()

    def set_state(self, paused, hidden, test_mode):
        """Atualiza os textos do menu e a dica do ícone conforme o estado (pausado, escondido, modo de teste)."""
        self.actions["pause"].setText("Continuar" if paused else "Pausar")
        self.actions["hide"].setText("Mostrar" if hidden else "Esconder")
        self.icon.setToolTip(self.titulo + ("  [MODO TESTE]" if test_mode else ""))


# ============================================================
# ATALHO GLOBAL DE PÂNICO (Ctrl + Alt + Shift + B)
# ============================================================


class PanicHotkey(QObject):
    """Registra o atalho pela plataforma (Windows, macOS ou Linux); avisa o Qt por sinal."""

    pressed = Signal()

    def __init__(self):
        """Registra o atalho de pânico pela plataforma; `ok` diz se o sistema aceitou o atalho."""
        super().__init__()
        self.ok = plataforma.iniciar_atalho(self.pressed.emit)
