"""
VISÃO - o pet olha a sua tela e conversa com você por um modelo de IA (opcional, desligado por padrão).

Dois caminhos, os dois em thread para o pet não travar enquanto o modelo pensa:
    olhar      de tempos em tempos (e logo depois de você trocar de programa) tira um print, lê o título
               da janela e pergunta ao modelo o que você está fazendo. A resposta vira sinais para a rede
               (VISAO_*) e, às vezes, um comentário no balão.
    conversar  você escreve pelo chat; ele responde no chat e no balão, e a conversa vira o canal CONVERSA.

Política (as permissões ficam em config.py):
    - nada sai do computador sem "Usar IA"; print e título só com "Ver minha tela";
    - não olha com o pet escondido, em tela cheia, dormindo, pausado, no pânico ou com você longe;
    - o print fica só na memória: nunca é gravado, nem o que o modelo disse sobre ele (nem no log);
    - pânico, pausa ou desligar a IA descartam a resposta que ainda estava a caminho.
"""

import base64
import threading
import time

from PySide6.QtCore import QBuffer, QIODevice, QObject, QPoint, Qt, Signal
from PySide6.QtGui import QGuiApplication

from ..ia import provedores
from ..ia.mente import Conversa, ler_observacao, limpar_fala, pedido_observacao, prompt_sistema
from ..log import log
from ..sense import senses

LARGURA_PRINT = 1280        # px: o print é reduzido antes de ir (mais barato e rápido)
QUALIDADE_JPEG = 70
ESPERA_APOS_ERRO = 300.0    # s sem olhar depois de uma falha (sem chave, sem rede...)
ESPERA_TROCA = 3.0          # s depois de trocar de programa, para a janela nova terminar de desenhar
REPETE_AVISO = 600.0        # s antes de repetir o mesmo aviso na bandeja


def capturar_tela(retangulo_ativo=None, dpr=1.0):
    """Print do monitor onde está a janela ativa, reduzido e em JPEG base64. None se não deu."""
    tela = None
    if retangulo_ativo:
        meio = QPoint(int((retangulo_ativo[0] + retangulo_ativo[2]) / 2 / dpr),
                      int((retangulo_ativo[1] + retangulo_ativo[3]) / 2 / dpr))
        tela = QGuiApplication.screenAt(meio)
    tela = tela or QGuiApplication.primaryScreen()
    if tela is None:
        return None
    imagem = tela.grabWindow(0).toImage()
    if imagem.isNull() or imagem.width() == 0:
        return None
    if imagem.width() > LARGURA_PRINT:
        imagem = imagem.scaledToWidth(LARGURA_PRINT, Qt.SmoothTransformation)
    buffer = QBuffer()
    buffer.open(QIODevice.WriteOnly)
    if not imagem.save(buffer, "JPG", QUALIDADE_JPEG):
        return None
    return base64.b64encode(bytes(buffer.data())).decode("ascii")


class VisaoController(QObject):
    """Quando olhar, o que perguntar e o que fazer com a resposta. Usa os atributos do PestinhaApp."""

    fala = Signal(str)              # algo para o balão
    resposta = Signal(str)          # resposta do chat
    erro_conversa = Signal(str)     # o chat falhou (mostrado no próprio chat)
    aviso = Signal(str)             # problema de configuração (mostrado na bandeja)
    _pronto = Signal(str, object, int)      # da thread para a thread do Qt: (tipo, resultado, geração)

    def __init__(self, app, nome, persona, debugging):
        """`app` é o PestinhaApp (permissões, sentidos, homeostase); `persona` vem de pets/<pet>.json."""
        super().__init__()
        self.app = app
        self.nome = nome
        self.sistema = prompt_sistema(nome, persona)
        self.debugging = debugging
        self.conversa = Conversa()
        self.ultimo_resumo = ""
        self.ultima_olhada = float("-inf")
        self.proxima = 0.0                  # primeira olhada assim que tudo estiver ligado
        self.olhando = False                # uma olhada a caminho
        self.respondendo = False            # uma resposta do chat a caminho
        self.geracao = 0                    # muda no pânico/pausa: respostas antigas são descartadas
        self._pedido_seu = False            # a olhada a caminho foi pedida por você (pelo menu)
        self._pergunta = ""                 # a mensagem do chat que está sendo respondida
        self._cliente = None
        self._cliente_de = None
        self._avisos = {}
        self._pronto.connect(self._ao_pronto)

    # ---------------- estado ----------------

    @property
    def perms(self):
        """As permissões atuais (o mesmo dicionário do app)."""
        return self.app.perms

    def ligada(self):
        """IA ligada e o pet ativo."""
        return self.perms["ia"] and self.perms["ativo"]

    def vendo(self):
        """Pode olhar a tela agora (permissão)."""
        return self.ligada() and self.perms["ver_tela"]

    def descricao(self):
        """Uma linha para o chat: quem responde e se ele está vendo a tela."""
        provedor = self.perms["ia_provedor"]
        modelo = provedores.modelo_de(provedor, self.perms["ia_modelo"])
        olhos = "vendo sua tela" if self.vendo() else "sem ver sua tela"
        return f"{provedores.info(provedor)['nome']} · {modelo} · {olhos}"

    def cancelar(self):
        """Pânico, pausa ou IA desligada: esquece o que estava a caminho."""
        self.geracao += 1
        self.olhando = self.respondendo = False

    def cliente(self):
        """O cliente do provedor escolhido (recriado se você trocar de provedor ou modelo)."""
        chave = (self.perms["ia_provedor"], self.perms["ia_modelo"])
        if self._cliente is None or self._cliente_de != chave:
            self._cliente = provedores.criar_cliente(*chave)
            self._cliente_de = chave
        return self._cliente

    # ---------------- olhar ----------------

    def app_mudou(self, now):
        """Você trocou de programa: ele dá uma olhada logo (respeitando o intervalo mínimo)."""
        if self.vendo():
            cedo = max(now + ESPERA_TROCA, self.ultima_olhada + self.app.prof["visao_apos_troca"])
            self.proxima = min(self.proxima, cedo)

    def pode_olhar(self):
        """Condições do momento: visível, acordado, você por perto, sem pausa nem pânico."""
        app = self.app
        return (self.vendo() and not app._congelado() and app.pet.isVisible()
                and not app.asleep and app.activity != "AWAY")

    def tick(self, now):
        """Chamado pelo ciclo de pensamento: olha a tela quando dá a hora."""
        if self.olhando or now < self.proxima or not self.pode_olhar():
            return
        self.olhar(now)

    def olhar(self, now):
        """Tira o print, lê o programa e o título e pergunta ao modelo (em outra thread)."""
        self.ultima_olhada = now
        self.proxima = now + self.app.prof["visao_intervalo"]
        try:
            cliente = self.cliente()
        except provedores.ErroIA as erro:
            self._falhou(str(erro), now)
            return
        imagem = self._print() if cliente.ve_imagem else None
        pergunta = pedido_observacao(senses.get_active_app(), senses.get_active_title(), self.app.activity,
                                     self.app.pet_state.emotion, self.ultimo_resumo)
        self.olhando = True
        self._em_thread("observacao", cliente, [{"role": "user", "content": pergunta}], imagem)

    def olhar_agora(self):
        """Menu: 'O que você está vendo?' (pula o intervalo; o comentário sempre aparece)."""
        if self.olhando or not self.vendo() or self.app._congelado():
            return
        self._pedido_seu = True
        self.olhar(time.monotonic())

    def _print(self):
        """Print da tela agora, na thread do Qt (a captura não pode ser feita fora dela)."""
        dpr = QGuiApplication.primaryScreen().devicePixelRatio()
        try:
            return capturar_tela(senses.foreground_rect(dpr), dpr)
        except Exception as erro:                      # tela bloqueada, sem permissão de captura...
            log(f"[visão] sem print: {erro}")
            return None

    # ---------------- conversar ----------------

    def perguntar(self, texto):
        """Você escreveu no chat: ele responde (vendo a tela, se puder)."""
        if self.respondendo or not self.ligada() or not self.perms["conversa"] or self.app._congelado():
            return False
        try:
            cliente = self.cliente()
        except provedores.ErroIA as erro:
            self.erro_conversa.emit(str(erro))
            return False
        imagem = self._print() if self.vendo() and cliente.ve_imagem else None
        mensagens = self.conversa.mensagens(texto, self.ultimo_resumo if self.vendo() else "")
        self.respondendo = True
        self._pergunta = texto
        self._em_thread("conversa", cliente, mensagens, imagem)
        return True

    # ---------------- thread ----------------

    def _em_thread(self, tipo, cliente, mensagens, imagem):
        """Chama o modelo fora da thread do Qt; o resultado volta pelo sinal _pronto."""
        geracao = self.geracao

        def trabalho():
            """Roda numa thread: devolve o texto ou a falha, nunca levanta."""
            try:
                resultado = cliente.responder(self.sistema, mensagens, imagem)
            except provedores.ErroIA as erro:
                resultado = erro
            except Exception as erro:                  # bug ou SDK inesperada: vira aviso, não derruba
                resultado = provedores.ErroIA(f"falha inesperada: {type(erro).__name__}: {erro}")
            self._pronto.emit(tipo, resultado, geracao)

        threading.Thread(target=trabalho, name=f"pestinha-{tipo}", daemon=True).start()

    def _ao_pronto(self, tipo, resultado, geracao):
        """Resposta do modelo, já na thread do Qt."""
        if geracao != self.geracao:
            return                                      # pânico/pausa no meio do caminho: descarta
        now = time.monotonic()
        if tipo == "observacao":
            self.olhando = False
            pedido, self._pedido_seu = self._pedido_seu, False
            if isinstance(resultado, Exception):
                self._falhou(str(resultado), now)
            elif self.vendo() and not self.app._congelado():
                self._entender(ler_observacao(resultado), pedido)
        else:
            self.respondendo = False
            if isinstance(resultado, Exception):
                self.erro_conversa.emit(str(resultado))
            elif not self.app._congelado():
                self._respondido(limpar_fala(resultado) or "...")

    def _entender(self, obs, pedido=False):
        """O que ele viu vira sinal para a rede e, às vezes, um comentário."""
        app = self.app
        if obs.resumo:
            self.ultimo_resumo = obs.resumo
        app.senses.saw(obs.sinais)
        novidade = obs.sinais.get("VISAO_NOVO", 0.0)
        if novidade > 0.3:
            app.drives.stimulate("novelty", novidade)  # coisa nova na tela também tira o tédio
        if self.debugging():
            log("[visão] sinais " + " ".join(f"{k[6:].lower()}={v:.2f}" for k, v in obs.sinais.items()))
        comentario = obs.comentario or (obs.resumo if pedido else "")
        if comentario and (pedido or self.perms["comentarios"]):
            self.fala.emit(comentario)

    def _respondido(self, texto):
        """Resposta do chat: mostra, guarda na conversa e conta como atenção sua."""
        app = self.app
        self.conversa.registrar(self._pergunta, texto)
        app.senses.kick("CONVERSA", 0.8)
        app.drives.touched("poke")                     # conversar é atenção: a carência diminui
        app.memory.on_interaction()
        app.timeline.note_interaction()
        if app.asleep:
            app.sleep.wake(startled=False)
        self.resposta.emit(texto)
        self.fala.emit(texto)

    def _falhou(self, motivo, now):
        """Falha da olhada: espera um tempo e avisa na bandeja (sem repetir o mesmo aviso toda hora)."""
        self.proxima = now + max(ESPERA_APOS_ERRO, self.app.prof["visao_intervalo"])
        log(f"[visão] {motivo}")
        if now - self._avisos.get(motivo, float("-inf")) >= REPETE_AVISO:
            self._avisos[motivo] = now
            self.aviso.emit(motivo)
