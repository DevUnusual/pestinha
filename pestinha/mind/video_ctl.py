"""
VÍDEO - ele assiste com você: ouve o som do computador, fica quieto prestando atenção e, no fim, resume
e guarda o que aprendeu (opcional, desligado por padrão: "Assistir vídeos comigo").

Como começa:
    você pede     no chat ou na voz ("assiste esse vídeo comigo") ou no menu ("Assistir o vídeo comigo")
    ele oferece   com "Ver minha tela" ligado, quando a olhada da IA diz que você está vendo um vídeo com
                  fala (aula, tutorial, palestra, podcast), ele primeiro ouve CONFERE_SOM s do som do
                  computador: sem som, o vídeo não está rodando e ele deixa quieto. Com som, pergunta no
                  balão se é para assistir com você; você responde "sim" ou "não" pela voz (a orelha já
                  levanta, sem precisar do nome) ou pelo chat. Sem resposta em ESPERA_OFERTA s, ele esquece.
Enquanto assiste: a orelha fica para a frente (ouvindo), os comentários da visão param e a música dele
pausa (senão ele ouviria a si mesmo). Com "Ver minha tela", ele olha a tela no ritmo de jogo e anota o
que aparece (slides, código, cenas), que vai junto para o resumo. O som do computador (loopback: o que sai na caixa ou no fone, nunca
o microfone) é gravado em pedaços de TRECHO s; cada pedaço com som vai para o serviço de voz
(servidor/voz/, o mesmo de "Falar com ele") e volta como texto. Vídeo longo: a cada ~10 min de fala, o
modelo de IA anota os pontos daquele pedaço (ia/video.py), para nada crescer sem limite.
Como termina: você pede ("resume o vídeo", "pode parar de assistir", ou o menu), passa `video_silencio` s
sem som nenhum (o vídeo acabou ou você pausou) ou MAX_DURACAO. Aí o modelo resume, ele fala no balão,
o resumo aparece no chat e vai para o conhecimento (mind/conhecimento.py); com o Hermes conectado, vai
também para a memória dele.

Política (as permissões ficam em config.py):
    - só com "Usar IA" e "Assistir vídeos comigo", sem pausa nem pânico;
    - o áudio e a transcrição ficam só na memória: nunca são gravados (nem no log); só o resumo é guardado;
    - para o serviço de voz vai o áudio; para o modelo de IA, só o texto transcrito e o título da janela
      (este só com "Ver minha tela");
    - pânico, pausa ou desligar a permissão param na hora e jogam fora o que foi ouvido.
"""

import threading
import time
import warnings

from PySide6.QtCore import QObject, Signal

from ..ia import video, voz
from ..ia.provedores import ErroIA
from ..log import log
from ..sense import senses
from .sincronia import estado_agora

TAXA = 16000                # Hz (o Whisper usa 16 kHz mono)
LEITURA = 1.0               # s por leitura do loopback
TRECHO = 20.0               # s de áudio por pedaço mandado para o serviço de voz
MIN_RESTO = 3.0             # s: o pedaço final menor que isso fica de fora
MAX_DURACAO = 3 * 3600.0    # s: depois disso ele resume sozinho
ESPERA_TRANSCRICAO = 45.0   # s esperando os últimos pedaços voltarem antes de resumir sem eles
ESPERA_AUTO = 180.0         # s depois de um resumo (ou de você mandar parar) sem começar sozinho de novo
REPETE_AVISO = 600.0
CONFERE_SOM = 2.0           # s ouvindo o som do computador antes de perguntar se assiste (vídeo rodando?)
ESPERA_OFERTA = 40.0        # s esperando você responder se ele assiste junto
ESPERA_SEM_SOM = 60.0       # s sem perguntar de novo quando parecia vídeo, mas não tinha som
ESPERA_RECUSA = 20 * 60.0   # s sem oferecer de novo depois de você dizer que não


def _som_do_computador():
    """O 'microfone' que grava o que sai na caixa/fone (loopback). Levanta ErroIA se não der."""
    try:
        import soundcard
    except Exception as erro:              # não instalado, ou sem servidor de som (Linux)
        raise ErroIA("para ouvir o vídeo, instale o pacote soundcard (pip install soundcard)") from erro
    try:
        saida = soundcard.default_speaker()
        return soundcard.get_microphone(id=str(saida.name), include_loopback=True)
    except Exception as erro:              # macOS não tem loopback sem um driver como o BlackHole
        raise ErroIA(f"não consegui ouvir o som do computador ({type(erro).__name__}: {erro})") from erro


class VideoController(QObject):
    """Assistir um vídeo junto: ouvir, anotar e resumir. Usa os atributos do PestinhaApp."""

    fala = Signal(str)              # algo para o balão
    resumo = Signal(str)            # o resumo completo (para o chat)
    aviso = Signal(str)             # problema (bandeja)
    perguntou = Signal()            # perguntou se assiste junto: o app deixa a orelha ouvindo a resposta
    _pronto = Signal(str, object, int)      # da thread para a thread do Qt: (tipo, resultado, geração)

    def __init__(self, app, nome):
        """`app` é o PestinhaApp (permissões, visão, conhecimento); `nome` ajuda o Whisper com o nome dele."""
        super().__init__()
        self.app = app
        self.nome = nome
        self.geracao = 0
        self.ativo = False              # ouvindo um vídeo agora
        self.finalizando = False        # parou de ouvir; esperando os últimos pedaços para resumir
        self.resumindo = False          # o resumo a caminho
        self.condensando = False        # notas de um pedaço a caminho
        self.desde = 0.0
        self.ultimo_som = 0.0
        self.titulo = ""
        self.transcricao = video.Transcricao()
        self.pendentes = 0              # pedaços no serviço de voz
        self.sem_auto_ate = 0.0
        self.conferindo = False         # ouvindo um pouco do som do computador antes de oferecer
        self.oferta_ate = 0.0           # perguntou se assiste junto: a resposta vale até aqui
        self._finalizar_ate = 0.0
        self._duracao = 0.0
        self._gravando = False
        self._cliente_voz = None
        self._cliente_voz_de = None
        self._avisos = {}
        self._pronto.connect(self._ao_pronto)

    # ---------------- estado ----------------

    @property
    def perms(self):
        return self.app.perms

    def ligado(self):
        """Permitido agora: IA e "Assistir vídeos comigo" ligados, e o pet ativo."""
        p = self.perms
        return p["ia"] and p["videos"] and p["ativo"]

    def ocupado(self):
        """Assistindo ou ainda resumindo o último."""
        return self.ativo or self.finalizando or self.resumindo

    def oferecendo(self):
        """Perguntou se assiste junto e ainda espera a resposta."""
        return time.monotonic() < self.oferta_ate

    def cliente_voz(self):
        """O cliente do serviço de voz (recriado se você trocar o endereço)."""
        if self._cliente_voz is None or self._cliente_voz_de != self.perms["voz_url"]:
            self._cliente_voz = voz.ClienteVoz(self.perms["voz_url"])
            self._cliente_voz_de = self.perms["voz_url"]
        return self._cliente_voz

    # ---------------- começar ----------------

    def comecar(self, sozinho=False):
        """Começa a ouvir. Devolve o que ele diz (ou o motivo de não dar)."""
        if not self.ligado():
            return "assistir vídeos está desligado em Configurações"
        if self.app._congelado():
            return f"o {self.nome} está pausado ou desligado agora"
        if self.ocupado():
            return "Já tô assistindo, quietinho!" if self.ativo else "Calma, ainda tô resumindo o outro!"
        try:
            cliente = self.cliente_voz()
        except ErroIA as erro:
            return str(erro)
        self.geracao += 1
        self.ativo, self.finalizando = True, False
        self.conferindo, self.oferta_ate = False, 0.0
        self.desde = self.ultimo_som = time.monotonic()
        self.transcricao = video.Transcricao()
        self.titulo = self._titulo_da_janela()
        self.pendentes = 0
        if self.app.musica.ativa() and self.app.musica.tocando():
            self.app.musica.pausar()                    # senão ele ouve a própria música
        self._gravando = True
        threading.Thread(target=self._gravar, args=(self.geracao, cliente), name="pestinha-video",
                         daemon=True).start()
        log("[vídeo] comecei a assistir" + (" (sozinho)" if sozinho else ""))
        if sozinho:
            return "Fechou! Vou assistir quietinho com você e depois te conto o que aprendi."
        return "Bora! Vou ficar quietinho prestando atenção. Quando acabar, eu resumo."

    def viu_video(self, now):
        """A olhada da IA disse que você está vendo um vídeo: confere se tem som e, se tiver, pergunta se
        assiste junto (se pode, e se não acabou de parar, de perguntar ou de ouvir um não)."""
        if (self.ocupado() or self.conferindo or self.oferecendo() or now < self.sem_auto_ate
                or not self.ligado() or self.app._congelado()):
            return
        self.conferindo = True
        threading.Thread(target=self._conferir_som, args=(self.geracao,), name="pestinha-video-confere",
                         daemon=True).start()

    def _conferir_som(self, geracao):
        """Roda numa thread: ouve CONFERE_SOM s do som do computador e diz se tem alguma coisa tocando."""
        try:
            import pythoncom
            pythoncom.CoInitialize()
        except Exception:
            pass
        try:
            fonte = _som_do_computador()
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                with fonte.recorder(samplerate=TAXA, channels=1) as gravador:
                    dados = gravador.record(numframes=int(TAXA * CONFERE_SOM))
            pcm = voz.para_mono16(dados.astype("<f4").tobytes(), "float", 1)
            self._pronto.emit("conferido", video.tem_som(pcm), geracao)
        except ErroIA as erro:
            self._pronto.emit("conferido", erro, geracao)
        except Exception as erro:
            self._pronto.emit("conferido", ErroIA(f"o som do computador falhou: {type(erro).__name__}: {erro}"),
                              geracao)

    def _conferido(self, resultado, now):
        """Voltou a conferência do som: com som, pergunta se assiste junto."""
        self.conferindo = False
        if isinstance(resultado, Exception):
            self._avisar(str(resultado))
            self.sem_auto_ate = now + ESPERA_AUTO
            return
        if not resultado:
            log("[vídeo] parecia vídeo, mas o computador está em silêncio: não pergunto")
            self.sem_auto_ate = now + ESPERA_SEM_SOM
            return
        if self.ocupado() or not self.ligado() or self.app._congelado():
            return
        self.oferta_ate = now + ESPERA_OFERTA
        log("[vídeo] tem vídeo tocando: perguntei se assisto junto")
        self.fala.emit("Isso aí é um vídeo? Quer que eu assista com você?")
        self.perguntou.emit()

    def responder_oferta(self, texto):
        """Sua resposta a "quer que eu assista com você?". Devolve o que ele diz, ou None se não era resposta."""
        if not self.oferecendo():
            return None
        resposta = video.resposta_a_oferta(texto)
        if resposta == "sim":
            self.oferta_ate = 0.0
            return self.comecar(sozinho=True)
        if resposta == "nao":
            self.oferta_ate = 0.0
            self.sem_auto_ate = time.monotonic() + ESPERA_RECUSA
            log("[vídeo] você não quis que eu assistisse")
            return "Beleza, fico na minha."
        return None

    def viu_tela(self, texto):
        """Uma olhada enquanto assiste: o que aparece no vídeo vai para o resumo."""
        if self.ativo:
            self.transcricao.ver(time.monotonic() - self.desde, texto)

    def _titulo_da_janela(self):
        """O título da janela (o nome do vídeo, no navegador), só com "Ver minha tela"."""
        if not (self.perms["ver_tela"] and self.perms["ia"]):
            return ""
        titulo = senses.get_active_title() or ""
        for rabo in (" - YouTube", " - Google Chrome", " - Mozilla Firefox", " - Microsoft Edge", " - Brave",
                     " - Opera"):
            titulo = titulo.replace(rabo, "")
        return titulo.strip()[:video.MAX_TITULO]

    # ---------------- ouvir (thread) ----------------

    def _gravar(self, geracao, cliente):
        """Roda numa thread: lê o loopback e manda cada pedaço com som para virar texto."""
        try:
            import pythoncom                            # Windows: o COM precisa ser iniciado nesta thread
            pythoncom.CoInitialize()
        except Exception:
            pass
        try:
            fonte = _som_do_computador()
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")         # "data discontinuity" do WASAPI não é problema
                with fonte.recorder(samplerate=TAXA, channels=1) as gravador:
                    self._ler(gravador, geracao, cliente)
        except ErroIA as erro:
            self._pronto.emit("erro_som", erro, geracao)
        except Exception as erro:
            self._pronto.emit("erro_som", ErroIA(f"o som do computador falhou: {type(erro).__name__}: {erro}"),
                              geracao)

    def _ler(self, gravador, geracao, cliente):
        """Junta leituras de LEITURA s até TRECHO s; ao parar, manda o resto (se tiver pelo menos MIN_RESTO s)."""
        pedaco, inicio = [], 0.0
        numero = 0
        while self._gravando and geracao == self.geracao:
            dados = gravador.record(numframes=int(TAXA * LEITURA))
            pedaco.append(voz.para_mono16(dados.astype("<f4").tobytes(), "float", 1))
            if len(pedaco) * LEITURA >= TRECHO:
                self._mandar(b"".join(pedaco), inicio, geracao, cliente)
                numero += 1
                inicio = numero * TRECHO
                pedaco = []
        if pedaco and len(pedaco) * LEITURA >= MIN_RESTO and geracao == self.geracao:
            self._mandar(b"".join(pedaco), inicio, geracao, cliente)
        self._pronto.emit("parou_de_ouvir", None, geracao)

    def _mandar(self, pcm, inicio, geracao, cliente):
        """Um pedaço: silêncio só avisa que não tinha som; com som vai para o serviço de voz (outra thread)."""
        if not video.tem_som(pcm):
            self._pronto.emit("silencio", None, geracao)
            return
        self._pronto.emit("som", None, geracao)
        wav = voz.wav_de_pcm(pcm, TAXA)

        def transcrever():
            try:
                texto = cliente.transcrever(wav, dica=self.titulo)
            except ErroIA as erro:
                texto = erro
            except Exception as erro:
                texto = ErroIA(f"falha inesperada na voz: {type(erro).__name__}: {erro}")
            self._pronto.emit("trecho", (inicio, texto), geracao)

        threading.Thread(target=transcrever, name="pestinha-video-voz", daemon=True).start()

    # ---------------- ciclo ----------------

    def tick(self, now):
        """No ciclo de pensamento: fim por silêncio ou duração, notas de vídeo longo, e o resumo final."""
        if self.oferta_ate and now >= self.oferta_ate:
            self.oferta_ate = 0.0                       # você não respondeu: ele esquece e não pergunta logo
            self.sem_auto_ate = now + ESPERA_AUTO
        if self.ativo:
            if now - self.ultimo_som > self.app.prof["video_silencio"]:
                log("[vídeo] silêncio: o vídeo acabou ou foi pausado")
                self.parar()
            elif now - self.desde > MAX_DURACAO:
                self.parar()
        if not self.condensando and not self.resumindo:
            pedaco = self.transcricao.pedaco_para_notas()
            if pedaco:
                self._condensar(pedaco)
        if self.finalizando and not self.condensando and (self.pendentes <= 0 or now > self._finalizar_ate):
            self._resumir(now)

    def parar(self, por_voce=False):
        """Para de ouvir e resume quando os últimos pedaços voltarem. Devolve o que ele diz."""
        if not self.ativo:
            if self.finalizando or self.resumindo:
                return "Tô terminando o resumo, só um instante!"
            return "Não tô assistindo nada agora. Quer que eu assista com você? É só pedir."
        self.ativo = False
        self._gravando = False
        self.finalizando = True
        self._finalizar_ate = time.monotonic() + ESPERA_TRANSCRICAO
        self.sem_auto_ate = time.monotonic() + ESPERA_AUTO
        log(f"[vídeo] parei de assistir ({video.tempo(time.monotonic() - self.desde)})")
        return "Beleza! Deixa eu juntar o que eu ouvi..." if por_voce else ""

    def cancelar(self):
        """Pânico, pausa ou permissão desligada: para na hora e esquece o que ouviu."""
        estava = self.ocupado()
        self.geracao += 1
        self._gravando = False
        self.ativo = self.finalizando = self.resumindo = self.condensando = False
        self.conferindo, self.oferta_ate = False, 0.0
        self.pendentes = 0
        self.transcricao = video.Transcricao()
        if estava:
            log("[vídeo] cancelado: o que ouvi foi descartado")

    # ---------------- modelo ----------------

    def _condensar(self, pedaco):
        """Vídeo longo: o modelo anota os pontos de um pedaço (em outra thread)."""
        try:
            cliente = self.app.visao.cliente()
        except ErroIA as erro:
            self._avisar(str(erro))
            self.transcricao.devolver(pedaco)
            return
        self.condensando = True
        self._modelo("notas", cliente, video.pedido_notas(self.titulo, pedaco), pedaco)

    def _resumir(self, now):
        """O resumo final (em outra thread). Sem nada ouvido, ele só diz isso."""
        self.finalizando = False
        if self.transcricao.vazia():
            self.fala.emit("Não ouvi ninguém falando nesse vídeo, então não tenho o que resumir.")
            return
        try:
            cliente = self.app.visao.cliente()
        except ErroIA as erro:
            self._avisar(str(erro))
            return
        try:
            estado = estado_agora(self.app)
        except AttributeError:
            estado = ""
        self.resumindo = True
        self._duracao = now - self.desde
        pedido = video.pedido_resumo(self.titulo, self.transcricao.notas, self.transcricao.texto(),
                                     self._duracao, estado, self.transcricao.texto_telas())
        self._modelo("resumo", cliente, pedido, None)

    def _modelo(self, tipo, cliente, pedido, extra):
        """Chama o modelo fora da thread do Qt; o resultado volta por _pronto."""
        geracao = self.geracao
        sistema = self.app.visao.sistema

        def trabalho():
            try:
                resultado = cliente.responder(sistema, [{"role": "user", "content": pedido}], None)
            except ErroIA as erro:
                resultado = erro
            except Exception as erro:
                resultado = ErroIA(f"falha inesperada: {type(erro).__name__}: {erro}")
            self._pronto.emit(tipo, (resultado, extra), geracao)

        threading.Thread(target=trabalho, name=f"pestinha-video-{tipo}", daemon=True).start()

    def _memorizar_no_hermes(self, aprendizado):
        """Com o Hermes conectado, o que ele aprendeu vai também para a memória dele (em outra thread)."""
        visao = self.app.visao
        if not visao.com_hermes():
            return
        try:
            hermes = visao.hermes()
        except ErroIA:
            return
        sistema = visao.sistema

        def trabalho():
            try:
                hermes.conversar(sistema, [{"role": "user", "content": video.pedido_memorizar(aprendizado)}],
                                 lambda *_: None)
            except Exception as erro:
                log(f"[vídeo] o Hermes não guardou: {type(erro).__name__}")

        threading.Thread(target=trabalho, name="pestinha-video-hermes", daemon=True).start()

    # ---------------- respostas ----------------

    def _ao_pronto(self, tipo, resultado, geracao):
        """Tudo o que volta das threads, já na thread do Qt."""
        if geracao != self.geracao:
            return                                      # cancelado no meio do caminho: descarta
        now = time.monotonic()
        if tipo == "som":
            self.ultimo_som = now
            self.pendentes += 1
        elif tipo == "silencio":
            pass
        elif tipo == "conferido":
            self._conferido(resultado, now)
        elif tipo == "trecho":
            self.pendentes = max(0, self.pendentes - 1)
            inicio, texto = resultado
            if isinstance(texto, Exception):
                self._avisar(str(texto))
            else:
                self.transcricao.adicionar(inicio, texto)
        elif tipo == "erro_som":
            self._avisar(str(resultado))
            self.cancelar()
            self.fala.emit("Não consegui ouvir o som do computador. Dá uma olhada no aviso da bandeja.")
        elif tipo == "parou_de_ouvir":
            pass
        elif tipo == "notas":
            self.condensando = False
            texto, pedaco = resultado
            if isinstance(texto, Exception):
                self._avisar(str(texto))
                self.transcricao.devolver(pedaco)
            else:
                self.transcricao.anotar(texto)
        elif tipo == "resumo":
            self.resumindo = False
            texto, _ = resultado
            if isinstance(texto, Exception):
                self._avisar(str(texto))
                self.fala.emit("Assisti tudo, mas não consegui resumir agora (veja o aviso da bandeja).")
                return
            self._aprendeu(video.ler_resumo(texto))

    def _aprendeu(self, aprendizado):
        """O resumo chegou: guarda, fala no balão e manda o texto completo para o chat."""
        self.transcricao = video.Transcricao()          # o que ouviu não fica: só o resumo
        if aprendizado.vazio():
            self.fala.emit(aprendizado.comentario or "Era mais música do que conversa, não tenho o que resumir.")
            return
        if not aprendizado.titulo:
            aprendizado.titulo = self.titulo or "um vídeo"
        self.app.conhecimento.guardar(aprendizado, self._duracao)
        self._memorizar_no_hermes(aprendizado)
        self.fala.emit(aprendizado.comentario or f"Aprendi sobre {aprendizado.titulo}! Tá guardado.")
        pontos = "".join(f"\n• {p}" for p in aprendizado.pontos)
        self.resumo.emit(f"📺 {aprendizado.titulo}\n{aprendizado.resumo}{pontos}")

    def _avisar(self, motivo):
        """Loga e avisa na bandeja, sem repetir o mesmo aviso toda hora."""
        log(f"[vídeo] {motivo}")
        now = time.monotonic()
        if now - self._avisos.get(motivo, float("-inf")) >= REPETE_AVISO:
            self._avisos[motivo] = now
            self.aviso.emit(motivo)
