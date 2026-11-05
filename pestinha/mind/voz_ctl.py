"""
VOZ - você fala, e a sua fala vira texto para o pet (opcional, desligado por padrão). Ele responde em
texto, como no chat: não fala.

Dois jeitos de falar:
    atalho     segure Ctrl+Alt+Shift+V: ele ouve (ondinhas no rosto) só enquanto a tecla está apertada,
               e o texto vai direto para ele, como uma mensagem do chat. No macOS e no Linux o sistema
               não avisa quando a tecla é solta: aperta para começar e aperta de novo para parar.
    microfone  o botão de microfone do chat: clica para gravar, clica de novo para parar; o texto cai no
               campo do chat para você conferir e mandar.
A fala vai para o serviço de voz (servidor/voz/), que devolve o texto (faster-whisper).

Política (as permissões ficam em config.py):
    - nunca ouve sem você apertar, e para sozinho depois de MAX_GRAVACAO s (a exceção é "Chamar pelo nome",
      opcional: mind/chamado_ctl.py espera o nome neste computador e manda o pedido por `transcrever`);
    - só com "Usar IA", "Conversar por texto" e "Falar com ele" ligados, sem pausa nem pânico;
    - o áudio fica só na memória: nunca é gravado, nem o que você disse (nem no log);
    - pânico, pausa ou desligar a voz fecham o microfone na hora e descartam o que estava a caminho.
"""

import threading
import time

from PySide6.QtCore import QBuffer, QIODevice, QObject, QTimer, Signal
from PySide6.QtMultimedia import QAudioFormat, QAudioSource, QMediaDevices, QtAudio

from .. import plataforma
from ..ia import voz
from ..ia.provedores import ErroIA
from ..log import log

TAXA = 16000                # Hz pedidos ao microfone (é o que o Whisper usa)
MAX_GRAVACAO = 30.0         # s: depois disso ele para de ouvir sozinho
MIN_GRAVACAO = 0.35         # s: menos que isso foi um toque sem querer
PASSO_MS = 50               # ms entre leituras da tecla
REPETE_AVISO = 600.0        # s antes de repetir o mesmo aviso na bandeja

_FORMATOS = {QAudioFormat.Int16: "int16", QAudioFormat.Int32: "int32", QAudioFormat.Float: "float",
             QAudioFormat.UInt8: "uint8"}


class Microfone:
    """Grava do microfone padrão para a memória (QAudioSource num QBuffer)."""

    def __init__(self):
        """Nada aberto até `abrir`."""
        self._fonte = None
        self._buffer = None
        self._formato = None

    def abrir(self):
        """Começa a gravar. Devolve False se não houver microfone ou ele não abrir."""
        dispositivo = QMediaDevices.defaultAudioInput()
        if dispositivo.isNull():
            return False
        formato = QAudioFormat()
        formato.setSampleRate(TAXA)
        formato.setChannelCount(1)
        formato.setSampleFormat(QAudioFormat.Int16)
        if not dispositivo.isFormatSupported(formato):
            formato = dispositivo.preferredFormat()     # convertido para 16 bits mono no fim (ia/voz.py)
        self._formato = formato
        self._buffer = QBuffer()
        self._buffer.open(QIODevice.WriteOnly)
        self._fonte = QAudioSource(dispositivo, formato)
        self._fonte.start(self._buffer)
        return self._fonte.error() == QtAudio.Error.NoError

    def fechar(self):
        """Para de gravar e devolve (pcm 16 bits mono, taxa); (b"", 0) se não havia nada."""
        if self._fonte is None:
            return b"", 0
        self._fonte.stop()
        dados = bytes(self._buffer.data())
        formato = self._formato
        self._fonte = self._buffer = self._formato = None
        nome = _FORMATOS.get(formato.sampleFormat())
        if not dados or nome is None:
            return b"", 0
        return voz.para_mono16(dados, nome, formato.channelCount()), formato.sampleRate()


class VozController(QObject):
    """Quando ouvir e para onde vai o texto da sua fala. Usa os atributos do PestinhaApp."""

    ouvido = Signal(str)            # falou pelo atalho: o texto vai direto para ele (o app manda ao chat)
    ditado = Signal(str)            # falou pelo botão do chat: o texto vai para o campo do chat
    estado = Signal()               # começou ou parou de ouvir, ou de transcrever (o botão do chat muda)
    aviso = Signal(str)             # problema (mostrado na bandeja)
    _pronto = Signal(str, object, int)      # da thread para a thread do Qt: (origem, resultado, geração)
    _apertou_sinal = Signal()               # o atalho chega de outra thread (Windows, pynput)

    def __init__(self, app, nome):
        """`app` é o PestinhaApp (permissões, rosto); `nome` ajuda o Whisper a escrever o nome dele."""
        super().__init__()
        self.app = app
        self.nome = nome
        self.microfone = Microfone()
        self.gravando = None                # None, "atalho" ou "chat": de onde veio o pedido para ouvir
        self.ouvindo_desde = 0.0
        self.transcrevendo = False
        self.geracao = 0
        self.atalho_ok = None               # None: ainda não registrou (só registra quando a voz é ligada)
        self._cliente = None
        self._cliente_de = None
        self._avisos = {}
        self._relogio = QTimer(self)
        self._relogio.setInterval(PASSO_MS)
        self._relogio.timeout.connect(self._passo)
        self._pronto.connect(self._ao_pronto)
        self._apertou_sinal.connect(self.apertou)

    # ---------------- estado ----------------

    @property
    def perms(self):
        """As permissões atuais (o mesmo dicionário do app)."""
        return self.app.perms

    def ligada(self):
        """Voz permitida agora: IA, conversa e voz ligadas, e o pet ativo."""
        p = self.perms
        return p["ia"] and p["conversa"] and p["voz"] and p["ativo"]

    def registrar_atalho(self):
        """Registra Ctrl+Alt+Shift+V na primeira vez que a voz é ligada (antes disso a tecla fica livre)."""
        if self.atalho_ok is None and self.ligada():
            self.atalho_ok = plataforma.iniciar_atalho_falar(self._apertou_sinal.emit)
            if not self.atalho_ok:
                self._avisar("o atalho de falar já está em uso por outro programa")
        return self.atalho_ok

    def cliente(self):
        """O cliente do serviço de voz (recriado se você trocar o endereço)."""
        if self._cliente is None or self._cliente_de != self.perms["voz_url"]:
            self._cliente = voz.ClienteVoz(self.perms["voz_url"])
            self._cliente_de = self.perms["voz_url"]
        return self._cliente

    def cancelar(self):
        """Pânico, pausa ou voz desligada: fecha o microfone e esquece o que estava a caminho."""
        self.geracao += 1
        estava = self.gravando or self.transcrevendo
        if self.gravando:
            self.microfone.fechar()                     # o que foi gravado é jogado fora
        self.gravando = None
        self.transcrevendo = False
        self._relogio.stop()
        self.app.pet_state.ouvindo = False
        if estava:
            self.estado.emit()

    # ---------------- ouvir ----------------

    def apertou(self):
        """O atalho foi apertado: começa a ouvir (ou, sem saber quando soltou, para)."""
        if self.gravando:
            self.parar_de_ouvir()
        else:
            self.ouvir("atalho")

    def alternar_microfone(self):
        """O botão de microfone do chat: grava, ou para e transcreve."""
        if self.gravando:
            self.parar_de_ouvir()
        elif not self.ouvir("chat"):
            self.estado.emit()                          # não abriu: o botão volta ao normal

    def ouvir(self, origem):
        """Abre o microfone, se pode. `origem` diz para onde vai o texto ('atalho' ou 'chat')."""
        if not self.ligada() or self.app._congelado() or self.transcrevendo or self.gravando:
            return False
        if not self.microfone.abrir():
            self.microfone.fechar()
            self._avisar("não achei um microfone")
            return False
        self.gravando = origem
        self.ouvindo_desde = time.monotonic()
        self.app.pet_state.ouvindo = True
        self._relogio.start()
        self.estado.emit()
        return True

    def parar_de_ouvir(self):
        """Fecha o microfone e manda a fala para virar texto (um toque curto demais é ignorado)."""
        if not self.gravando:
            return
        origem, self.gravando = self.gravando, None
        self._relogio.stop()
        self.app.pet_state.ouvindo = False
        pcm, taxa = self.microfone.fechar()
        cliente = None
        if taxa and voz.duracao(pcm, taxa) >= MIN_GRAVACAO:
            try:
                cliente = self.cliente()
            except ErroIA as erro:
                self._avisar(str(erro))
        if cliente is not None:
            self.transcrevendo = True
            self._em_thread(origem, cliente, voz.wav_de_pcm(pcm, taxa))
        self.estado.emit()

    def transcrever(self, wav):
        """Um pedido que já chegou gravado (o chamado pelo nome, mind/chamado_ctl.py): vai como o atalho."""
        if not self.ligada() or self.app._congelado() or self.transcrevendo or self.gravando:
            return False
        try:
            cliente = self.cliente()
        except ErroIA as erro:
            self._avisar(str(erro))
            return False
        self.transcrevendo = True
        self._em_thread("atalho", cliente, wav)
        self.estado.emit()
        return True

    def _passo(self):
        """A cada PASSO_MS enquanto ouve: soltou a tecla? passou do tempo?"""
        if not self.gravando:
            self._relogio.stop()
            return
        soltou = self.gravando == "atalho" and plataforma.tecla_falar_segurada() is False
        if soltou or time.monotonic() - self.ouvindo_desde > MAX_GRAVACAO:
            self.parar_de_ouvir()

    # ---------------- thread ----------------

    def _em_thread(self, origem, cliente, wav):
        """Manda a fala para o serviço fora da thread do Qt; o texto volta pelo sinal _pronto."""
        geracao = self.geracao

        def rodar():
            """Roda numa thread: devolve o texto ou a falha, nunca levanta."""
            try:
                resultado = cliente.transcrever(wav, dica=self.nome)
            except ErroIA as erro:
                resultado = erro
            except Exception as erro:                  # bug inesperado: vira aviso, não derruba
                resultado = ErroIA(f"falha inesperada na voz: {type(erro).__name__}: {erro}")
            self._pronto.emit(origem, resultado, geracao)

        threading.Thread(target=rodar, name="pestinha-voz", daemon=True).start()

    def _ao_pronto(self, origem, resultado, geracao):
        """O texto da sua fala, já na thread do Qt."""
        if geracao != self.geracao:
            return                                      # pânico/pausa no meio do caminho: descarta
        self.transcrevendo = False
        self.estado.emit()
        if isinstance(resultado, Exception):
            self._avisar(str(resultado))
        elif not resultado:
            self._avisar("não ouvi nada (o microfone está ligado e sem mudo?)")
        elif self.ligada() and not self.app._congelado():
            (self.ouvido if origem == "atalho" else self.ditado).emit(resultado)

    def _avisar(self, motivo):
        """Avisa na bandeja (sem repetir o mesmo aviso toda hora)."""
        log(f"[voz] {motivo}")
        now = time.monotonic()
        if now - self._avisos.get(motivo, float("-inf")) >= REPETE_AVISO:
            self._avisos[motivo] = now
            self.aviso.emit(motivo)
