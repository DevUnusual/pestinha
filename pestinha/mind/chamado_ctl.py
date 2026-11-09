"""
CHAMADO - você chama ele pelo nome ("Bob!") e ele te ouve, como a Alexa (opcional, desligado por padrão:
"Chamar pelo nome").

Com a permissão ligada, o microfone fica aberto e o áudio vai, aos pedaços, para uma thread que roda o
Vosk neste computador (ia/chamado.py), procurando só a palavra de chamado. Dois jeitos de falar:
    junto     "Bob, que horas são?": a frase inteira (desde o nome) vai para o serviço de voz
    em dois   "Bob." ... a orelha levanta e ele espera o pedido; você fala e, quando para, o pedido vai
              (se você não falar nada em alguns segundos, ele desiste)
O texto volta pelo VozController, como se você tivesse usado o atalho de falar: vai para a IA e a resposta
vem no balão (e no chat, se estiver aberto).

Continuar a conversa: depois de responder uma pergunta que você fez chamando o nome (ou de perguntar se
assiste um vídeo com você), a orelha levanta de novo e ele te ouve por ESPERA_CONTINUA s sem precisar do
nome, para você emendar outra pergunta ou responder ("sim"). Calado esse tempo, ele volta a esperar o nome.

O chamado é um serviço à parte (microfone e thread próprios) e fica ligado o tempo todo, inclusive com ele
assistindo um vídeo: o vídeo é ouvido pelo som do computador (loopback), não pelo microfone. Com vídeo ou
música tocando, o nome pode vir da caixa de som, então só vale com confiança alta (CONFIANCA_EXIGENTE).
Ele só não atende enquanto você segura o atalho de falar, ou ele ainda está transcrevendo ou respondendo o
pedido anterior.

Política (as permissões ficam em config.py):
    - só com "Usar IA", "Conversar por texto", "Falar com ele" e "Chamar pelo nome", sem pausa nem pânico;
    - antes do nome nada sai do computador e nada é gravado: o áudio passa pela memória e é descartado
      (só os últimos segundos ficam, para recortar o pedido que veio junto);
    - depois do nome, só o pedido vai para o serviço de voz (e não é gravado, como no atalho);
    - pânico, pausa ou desligar a permissão fecham o microfone na hora;
    - o modelo (31 MB) é baixado uma vez, para memory/modelos/.
"""

import queue
import threading
import time

from PySide6.QtCore import QObject, Signal

from .. import multimidia
from ..ia import chamado, voz
from ..ia.provedores import ErroIA
from ..log import log
from .voz_ctl import nome_do_formato

REPETE_AVISO = 600.0
ESPERA_FILA = 0.3           # s: a thread confere se ainda deve ouvir pelo menos a esse intervalo
ESPERA_RESPOSTA = 120.0     # s: uma resposta que chega depois disso já não emenda a conversa falada


class ChamadoController(QObject):
    """Microfone aberto esperando o nome. Usa os atributos do PestinhaApp (permissões, voz, vídeo)."""

    chamou = Signal()                   # ouviu o nome sozinho: a orelha levanta, esperando o pedido
    aviso = Signal(str)
    _evento = Signal(str, object, int)  # da thread para a thread do Qt: (tipo, dado, geração)

    def __init__(self, app, pasta_modelos):
        """`pasta_modelos` é memory/modelos/."""
        super().__init__()
        self.app = app
        self.pasta_modelos = pasta_modelos
        self.geracao = 0
        self.ouvindo = False            # microfone aberto, esperando o nome
        self.escutando = False          # ouviu o nome: esperando o pedido
        self.pronto = False             # o modelo carregou
        self.palavra = ""
        self._fonte = None
        self._dispositivo = None
        self._formato = None
        self._nome_formato = None       # 'int16'... do formato do microfone aberto
        self._fila = queue.Queue()
        self._surdo = False             # lido pela thread: agora não atende
        self._exigente = False          # lido pela thread: vídeo ou música tocando, só o nome bem claro
        self._continuar = None          # (geração, espera): a thread abre uma escuta sem precisar do nome
        self.pediu_em = 0.0             # quando mandou o último pedido falado (para continuar depois da resposta)
        self._avisos = {}
        self._evento.connect(self._ao_evento)

    # ---------------- estado ----------------

    @property
    def perms(self):
        return self.app.perms

    def permitido(self):
        """As permissões deixam: IA, conversa, voz e "Chamar pelo nome", com o pet ativo (e o QtMultimedia
        instalado, multimidia.py)."""
        p = self.perms
        return bool(p["ia"] and p["conversa"] and p["voz"] and p["chamar"] and p["ativo"]
                    and multimidia.disponivel())

    def palavra_de_chamado(self):
        """A palavra configurada, ou o nome do pet."""
        return (self.perms["chamado_palavra"] or self.app.nome).strip().lower()

    def sincronizar(self):
        """Abre ou fecha o microfone conforme as permissões e a pausa (chamado quando algo muda)."""
        deve = self.permitido() and not self.app._congelado()
        if deve and (not self.ouvindo or self.palavra != self.palavra_de_chamado()):
            self.parar()
            self.comecar()
        elif not deve and self.ouvindo:
            self.parar()

    def atualizar(self):
        """No ciclo de pensamento: quando ele não deve atender (atalho de falar, respondendo) e quando o som
        do computador pode ter o nome (vídeo ou música: só vale bem claro)."""
        app = self.app
        self._surdo = bool(app.voz.gravando or app.voz.transcrevendo or app.visao.respondendo)
        video = getattr(app, "video", None)
        musica = getattr(app, "musica", None)
        self._exigente = bool((video is not None and video.ativo)
                              or (musica is not None and musica.ativa() and musica.tocando()))

    def respondeu(self, _texto=""):
        """Chegou a resposta do chat: se a pergunta veio chamando pelo nome, continua ouvindo."""
        if self.pediu_em and time.monotonic() - self.pediu_em < ESPERA_RESPOSTA:
            self.continuar_ouvindo()
        self.pediu_em = 0.0

    def continuar_ouvindo(self, espera=chamado.ESPERA_CONTINUA):
        """Depois de uma resposta: a orelha levanta e ele ouve sem precisar do nome. False se não está ouvindo."""
        if not (self.ouvindo and self.pronto) or self.escutando:
            return False
        self._continuar = (self.geracao, espera)
        self.escutando = True
        log("[chamado] continuo ouvindo, sem precisar do nome")
        return True

    # ---------------- microfone ----------------

    def comecar(self):
        """Abre o microfone e liga a thread do Vosk. Devolve False se não houver microfone."""
        if not multimidia.disponivel():
            self._avisar(multimidia.AVISO)
            return False
        qm = multimidia.modulo()
        QAudioFormat = qm.QAudioFormat
        dispositivo = qm.QMediaDevices.defaultAudioInput()
        if dispositivo.isNull():
            self._avisar("não achei um microfone para ouvir o nome")
            return False
        formato = QAudioFormat()
        formato.setSampleRate(16000)
        formato.setChannelCount(1)
        formato.setSampleFormat(QAudioFormat.Int16)
        if not dispositivo.isFormatSupported(formato):
            formato = dispositivo.preferredFormat()
        if nome_do_formato(formato) is None:
            self._avisar("o microfone usa um formato de áudio que eu não sei ler")
            return False
        self.geracao += 1
        self.palavra = self.palavra_de_chamado()
        self._fila = queue.Queue()
        self._formato = formato
        self._nome_formato = nome_do_formato(formato)
        self._fonte = qm.QAudioSource(dispositivo, formato)
        self._dispositivo = self._fonte.start()
        if self._dispositivo is None:
            self._fonte = None
            self._avisar("o microfone não abriu")
            return False
        self._dispositivo.readyRead.connect(self._ler)
        self.ouvindo = True
        self.escutando = self.pronto = False
        threading.Thread(target=self._trabalhar, args=(self.geracao, self._fila, formato.sampleRate(), self.palavra),
                         name="pestinha-chamado", daemon=True).start()
        log(f'[chamado] microfone aberto, esperando "{self.palavra}"')
        return True

    def parar(self):
        """Fecha o microfone e para a thread (o que estava na fila é jogado fora)."""
        self.geracao += 1
        if self._fonte is not None:
            try:
                self._dispositivo.readyRead.disconnect(self._ler)
            except (RuntimeError, TypeError):
                pass
            self._fonte.stop()
        estava = self.ouvindo
        self._fonte = self._dispositivo = None
        self.ouvindo = self.escutando = self.pronto = False
        self._continuar = None
        self._fila = queue.Queue()
        if estava:
            log("[chamado] microfone fechado")

    def _ler(self):
        """O microfone tem áudio: vai para a fila da thread (em 16 bits mono)."""
        if self._dispositivo is None:
            return
        dados = bytes(self._dispositivo.readAll())
        if dados:
            formato = self._formato
            self._fila.put(voz.para_mono16(dados, self._nome_formato, formato.channelCount()))

    # ---------------- thread ----------------

    def _trabalhar(self, geracao, fila, taxa, palavra):
        """Roda numa thread: baixa e carrega o modelo, e procura o nome no áudio que chega."""
        emitir = self._evento.emit
        try:
            if not chamado.modelo_baixado(self.pasta_modelos):
                emitir("baixando", None, geracao)
                chamado.baixar_modelo(self.pasta_modelos)
            if geracao != self.geracao:
                return
            detector = chamado.Detector(chamado.carregar_modelo(self.pasta_modelos), palavra, taxa)
        except ErroIA as erro:
            emitir("erro", str(erro), geracao)
            return
        except Exception as erro:
            emitir("erro", f"falha inesperada no chamado: {type(erro).__name__}: {erro}", geracao)
            return
        emitir("pronto", detector.alvos, geracao)
        self._ouvir(detector, fila, geracao, taxa, emitir)

    def _ouvir(self, detector, fila, geracao, taxa, emitir):
        """O laço da thread (separado para os testes poderem dar um detector falso)."""
        escuta = None
        while geracao == self.geracao:
            try:
                pcm = fila.get(timeout=ESPERA_FILA)
            except queue.Empty:
                continue
            achou = detector.alimentar(pcm)          # sempre alimenta: os tempos do Vosk não se perdem
            continuar, self._continuar = self._continuar, None
            if continuar is not None and continuar[0] == geracao and escuta is None:
                escuta = chamado.Escuta(taxa, espera=continuar[1])     # emendando: sem precisar do nome
            if escuta is not None:
                fim = escuta.alimentar(pcm)
                if fim == "fim":
                    emitir("pedido", voz.wav_de_pcm(escuta.audio(), taxa), geracao)
                    escuta = None
                elif fim == "desistiu":
                    emitir("desistiu", None, geracao)
                    escuta = None
                continue
            if achou is None or self._surdo:
                continue
            if self._exigente and achou.confianca < chamado.CONFIANCA_EXIGENTE:
                log(f"[chamado] nome pouco claro com som tocando (confiança {achou.confianca:.2f}): ignorei")
                continue
            log(f"[chamado] ouvi o nome (confiança {achou.confianca:.2f})")
            if achou.com_pedido():                    # "Bob, que horas são?": o pedido veio junto
                pedido = detector.recortar(achou.inicio - chamado.ANTES, achou.fim_frase + 0.3)
                emitir("pedido", voz.wav_de_pcm(pedido, taxa), geracao)
            else:                                     # só "Bob": espera o pedido
                agora = detector.amostras / taxa
                escuta = chamado.Escuta(taxa, detector.recortar(achou.inicio - chamado.ANTES, agora))
                emitir("chamou", None, geracao)

    def _ao_evento(self, tipo, dado, geracao):
        """O que a thread avisa, já na thread do Qt."""
        if geracao != self.geracao:
            return
        if tipo == "baixando":
            self._avisar("baixando o modelo de voz para ouvir o seu chamado (31 MB, só desta vez)...")
        elif tipo == "pronto":
            self.pronto = True
            log(f"[chamado] pronto: reconheço {', '.join(dado)}")
        elif tipo == "erro":
            self._avisar(dado)
            self.parar()
        elif tipo == "chamou":
            self.escutando = True
            self.chamou.emit()
        elif tipo == "desistiu":
            self.escutando = False
        elif tipo == "pedido":
            self.escutando = False
            if self.permitido() and not self.app._congelado() and self.app.voz.transcrever(dado):
                self.pediu_em = time.monotonic()

    def _avisar(self, motivo):
        """Loga e avisa na bandeja, sem repetir o mesmo aviso toda hora."""
        log(f"[chamado] {motivo}")
        now = time.monotonic()
        if now - self._avisos.get(motivo, float("-inf")) >= REPETE_AVISO:
            self._avisos[motivo] = now
            self.aviso.emit(motivo)
