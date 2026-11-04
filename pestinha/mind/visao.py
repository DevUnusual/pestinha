"""
VISÃO - o pet olha a sua tela e conversa com você por um modelo de IA (opcional, desligado por padrão).

Dois caminhos, os dois em thread para o pet não travar enquanto o modelo pensa:
    olhar      de tempos em tempos (e logo depois de você trocar de programa) tira um print, lê o título
               da janela e pergunta ao modelo o que você está fazendo. A resposta vira sinais para a rede
               (VISAO_*) e, às vezes, um comentário no balão.
    conversar  você escreve pelo chat; ele responde no chat e no balão, e a conversa vira o canal CONVERSA.
    pesquisar  se a olhada pedir (campo "pesquisar"), o Hermes pesquisa na internet e a dica vai para o balão.
    Hermes     com "Conectar ao Hermes", o chat passa por ele: a mesma persona, mas com pesquisa na internet,
               leitura de páginas e a memória dele sobre você (a sessão "pestinha-<pet>" é a mesma em todos
               os computadores). Enquanto ele usa uma ferramenta, o pet vira a IA vilã. Se o Hermes cair, o
               provedor escolhido responde no lugar, sem você perceber (só um aviso na bandeja).
    imagem     se você pedir para ver algo ("pesquisa o que é manga"), o Hermes devolve o link de uma imagem
               (linha "IMAGEM:"); sem link ou sem Hermes, o link vem da Wikipédia. Uma thread baixa e o pet
               projeta como holograma (ia/imagem.py, world/holograma.py).
    jogo       com "Acompanhar jogos", em jogo ele olha a cada poucos segundos (visao_jogo), pula o print
               se a tela quase não mudou e fala no máximo a cada `fala_jogo`.

Nos dois, o estado da rede vai junto (mind/sincronia.py): quem sente é a rede, o modelo só dá voz.

Política (as permissões ficam em config.py):
    - nada sai do computador sem "Usar IA"; print e título só com "Ver minha tela";
    - não olha com o pet escondido, em tela cheia, dormindo, pausado, no pânico ou com você longe;
    - o print fica só na memória: nunca é gravado, nem o que o modelo disse sobre ele (nem no log);
    - para o Hermes vão só o termo e o resumo, nunca o print nem o título, e no máximo uma pesquisa por
      `pesquisa_intervalo`;
    - com "Conectar ao Hermes", o chat (com o resumo da tela, o estado da rede e as lembranças) vai para o
      Hermes; para a Wikipédia, só o termo que você pediu;
    - pânico, pausa ou desligar a IA descartam a resposta que ainda estava a caminho.
"""

import base64
import threading
import time

from PySide6.QtCore import QBuffer, QIODevice, QObject, QPoint, Qt, Signal
from PySide6.QtGui import QGuiApplication, QImage

from ..ia import pesquisa, provedores
from ..ia.imagem import baixar as baixar_imagem, buscar as buscar_imagem_na_web, pedido_de_imagem as imagem_pedida
from ..ia.imagem import titulo_do_link
from ..ia.mente import (Conversa, ler_dica, ler_observacao, limpar_fala, pedido_dica, pedido_observacao,
                        prompt_sistema, separar_imagem, sistema_hermes)
from ..log import log
from .sincronia import descrever_temperamento, estado_agora
from ..sense import senses

LARGURA_PRINT = 1280        # px: o print é reduzido antes de ir (mais barato e rápido)
QUALIDADE_JPEG = 70
ESPERA_APOS_ERRO = 300.0    # s sem olhar depois de uma falha (sem chave, sem rede...)
JA_DISSE = 5                # últimos comentários que ele não deve repetir
ESPERA_TROCA = 3.0          # s depois de trocar de programa, para a janela nova terminar de desenhar
REPETE_AVISO = 600.0        # s antes de repetir o mesmo aviso na bandeja
TAMANHO_MINI = (32, 18)     # px da miniatura cinza que compara um print com o anterior
QUASE_IGUAL = 0.025         # diferença média (0..1) abaixo disso: a tela não mudou o bastante


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


def miniatura(imagem_b64):
    """Miniatura cinza do print (bytes, um por pixel), para comparar com o anterior. None se não deu."""
    try:
        imagem = QImage.fromData(base64.b64decode(imagem_b64, validate=True), "JPG")
    except (ValueError, TypeError):
        return None
    if imagem.isNull():
        return None
    mini = imagem.scaled(*TAMANHO_MINI, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
    mini = mini.convertToFormat(QImage.Format_Grayscale8)
    largura, altura = TAMANHO_MINI
    linha = mini.bytesPerLine()
    dados = bytes(mini.constBits())
    return b"".join(dados[y * linha:y * linha + largura] for y in range(altura))


def diferenca(a, b):
    """Quanto duas miniaturas diferem, de 0 (iguais) a 1. Sem uma delas, 1."""
    if not a or not b or len(a) != len(b):
        return 1.0
    return sum(abs(x - y) for x, y in zip(a, b)) / (255.0 * len(a))


class VisaoController(QObject):
    """Quando olhar, o que perguntar e o que fazer com a resposta. Usa os atributos do PestinhaApp."""

    fala = Signal(str)              # algo para o balão
    resposta = Signal(str)          # resposta do chat
    erro_conversa = Signal(str)     # o chat falhou (mostrado no próprio chat)
    aviso = Signal(str)             # problema de configuração (mostrado na bandeja)
    imagem = Signal(str, bytes)     # (título, bytes) da imagem que você pediu, para projetar
    _pronto = Signal(str, object, int)      # da thread para a thread do Qt: (tipo, resultado, geração)
    _ferramenta = Signal(bool, int)         # o Hermes começou (True) ou terminou de usar uma ferramenta

    def __init__(self, app, nome, pet_def, debugging):
        """`app` é o PestinhaApp (permissões, sentidos, homeostase); `pet_def` é o pets/<pet>.json carregado."""
        super().__init__()
        self.app = app
        self.nome = nome
        self.sistema = prompt_sistema(nome, pet_def.get("persona"),
                                      descrever_temperamento(pet_def.get("temperamento")),
                                      pet_def.get("exemplos", ()), pet_def.get("evitar", ()))
        self.sessao = f"pestinha-{pet_def.get('id') or nome}".lower()   # a memória do Hermes sobre você
        self.ja_disse = []                  # comentários recentes (para ele não se repetir)
        self.debugging = debugging
        self.conversa = Conversa()
        self.ultimo_resumo = ""
        self.ultima_olhada = float("-inf")
        self.proxima = 0.0                  # primeira olhada assim que tudo estiver ligado
        self.olhando = False                # uma olhada a caminho
        self.respondendo = False            # uma resposta do chat a caminho
        self.pesquisando = False            # uma pesquisa do Hermes a caminho
        self.buscando_imagem = False        # uma imagem pedida no chat a caminho
        self.ferramentas = 0                # ferramentas do Hermes rodando agora (o pet vira a IA vilã)
        self.ultima_pesquisa = float("-inf")
        self.ultimo_envio = float("-inf")   # quando um print foi de fato para o modelo
        self.ultima_fala = float("-inf")    # último comentário espontâneo (freio em jogo)
        self._mini = None                   # miniatura do último print enviado
        self.geracao = 0                    # muda no pânico/pausa: respostas antigas são descartadas
        self._pedido_seu = False            # a olhada a caminho foi pedida por você (pelo menu)
        self._pergunta = ""                 # a mensagem do chat que está sendo respondida
        self._cliente = None
        self._cliente_de = None
        self._hermes = None
        self._hermes_de = None
        self._avisos = {}
        self._pronto.connect(self._ao_pronto)
        self._ferramenta.connect(self._ao_usar_ferramenta)

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

    def pode_pesquisar(self, now):
        """Permissão ligada, nada a caminho e já passou o intervalo desde a última pesquisa."""
        return (self.vendo() and self.perms["pesquisar"] and not self.pesquisando
                and now - self.ultima_pesquisa >= self.app.prof["pesquisa_intervalo"])

    def com_hermes(self):
        """O chat passa pelo Hermes: IA, conversa e "Conectar ao Hermes" ligados."""
        return self.ligada() and self.perms["conversa"] and self.perms["pesquisar"]

    def em_jogo(self):
        """"Acompanhar jogos" ligado e você jogando (pela lista de jogos ou pelo título, no Minecraft Java)."""
        if not (self.vendo() and self.perms["jogos"]):
            return False
        return (self.app.activity == "GAMING"
                or senses.jogo_pelo_titulo(senses.get_active_app(), senses.get_active_title()))

    def intervalo(self):
        """Segundos até a próxima olhada: curto em jogo (mais com o Ollama, que não cobra), longo fora."""
        prof = self.app.prof
        if self.em_jogo():
            return prof["visao_jogo" if self.perms["ia_provedor"] == "ollama" else "visao_jogo_nuvem"]
        return prof["visao_intervalo"]

    def descricao(self):
        """Uma linha para o chat: quem responde e se ele está vendo a tela."""
        provedor = self.perms["ia_provedor"]
        modelo = provedores.modelo_de(provedor, self.perms["ia_modelo"])
        olhos = "vendo sua tela" if self.vendo() else "sem ver sua tela"
        nome = provedores.info(provedor)["nome"]
        if provedor == "ollama":
            nome = f"Ollama em {provedores.endereco_ollama(self.perms['ia_ollama_url']) or '?'}"
        if self.com_hermes():
            return f"Hermes (pesquisa e memória) + {nome} · {modelo} · {olhos}"
        return f"{nome} · {modelo} · {olhos}"

    def cancelar(self):
        """Pânico, pausa ou IA desligada: esquece o que estava a caminho."""
        self.geracao += 1
        self.olhando = self.respondendo = self.pesquisando = self.buscando_imagem = False
        self.ferramentas = 0

    def chave_nova(self):
        """Você salvou uma chave: recria o cliente e olha de novo logo (sem esperar o tempo de erro)."""
        self._cliente = self._hermes = None
        self._avisos.clear()
        self.proxima = min(self.proxima, time.monotonic() + ESPERA_TROCA)

    def cliente(self):
        """O cliente do provedor escolhido (recriado se você trocar de provedor ou modelo)."""
        chave = (self.perms["ia_provedor"], self.perms["ia_modelo"], self.perms["ia_ollama_url"])
        if self._cliente is None or self._cliente_de != chave:
            self._cliente = provedores.criar_cliente(*chave)
            self._cliente_de = chave
        return self._cliente

    def hermes(self):
        """O cliente do Hermes (recriado se você trocar o endereço)."""
        if self._hermes is None or self._hermes_de != self.perms["hermes_url"]:
            self._hermes = pesquisa.criar_cliente(self.perms["hermes_url"], self.sessao)
            self._hermes_de = self.perms["hermes_url"]
        return self._hermes

    def estado(self):
        """O estado da rede agora, em texto (sincronia rede -> IA). Vazio se algo ainda não existe."""
        try:
            return estado_agora(self.app)
        except AttributeError:                         # app ainda montando (ou de teste)
            return ""

    def lembrado(self):
        """O que ele viu nos outros computadores (só com "Lembrar o que viu")."""
        return self.app.lembrancas.contexto() if self.perms["lembrar"] else ""

    # ---------------- olhar ----------------

    def app_mudou(self, now):
        """Você trocou de programa: ele dá uma olhada logo (respeitando o intervalo mínimo)."""
        if self.vendo():
            minimo = min(self.app.prof["visao_apos_troca"], self.intervalo())
            cedo = max(now + ESPERA_TROCA, self.ultima_olhada + minimo)
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
        jogo = self.em_jogo()
        self.ultima_olhada = now
        self.proxima = now + self.intervalo()
        try:
            cliente = self.cliente()
        except provedores.ErroIA as erro:
            self._falhou(str(erro), now)
            return
        imagem = self._print() if cliente.ve_imagem else None
        if imagem:
            mini = miniatura(imagem)
            if (jogo and not self._pedido_seu and diferenca(mini, self._mini) < QUASE_IGUAL
                    and now - self.ultimo_envio < self.app.prof["visao_intervalo"]):
                return                                 # a tela quase não mudou: não gasta uma olhada
            self._mini = mini
        self.ultimo_envio = now
        pergunta = pedido_observacao(senses.get_active_app(), senses.get_active_title(), self.app.activity,
                                     self.app.pet_state.emotion, self.ultimo_resumo,
                                     self.estado(), self.ja_disse, self.lembrado(), self.pode_pesquisar(now),
                                     jogo)
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
        """Você escreveu no chat: ele responde (pelo Hermes, se estiver conectado; vendo a tela, se puder)."""
        if self.respondendo or not self.ligada() or not self.perms["conversa"] or self.app._congelado():
            return False
        hermes = cliente = None
        if self.com_hermes():
            try:
                hermes = self.hermes()
            except provedores.ErroIA as erro:          # sem chave ou endereço ruim: segue sem ele
                self._avisar(f"[hermes] {erro}", str(erro), time.monotonic())
        try:
            cliente = self.cliente()
        except provedores.ErroIA as erro:
            if hermes is None:
                self.erro_conversa.emit(str(erro))
                return False
        imagem = self._print() if cliente is not None and self.vendo() and cliente.ve_imagem else None
        mensagens = self.conversa.mensagens(texto, self.ultimo_resumo if self.vendo() else "", self.estado(),
                                            self.lembrado())
        self.respondendo = True
        self._pergunta = texto
        termo = imagem_pedida(texto) if self.perms["pesquisar"] else None
        if hermes is not None:
            self._conversar_pelo_hermes(hermes, cliente, mensagens, imagem, termo)
        else:
            self._em_thread("conversa", cliente, mensagens, imagem)
            if termo and not self.buscando_imagem:
                self.buscar_imagem(termo)
        return True

    def _conversar_pelo_hermes(self, hermes, reserva, mensagens, imagem, termo):
        """
        O Hermes responde (pesquisando e lembrando de você); se ele cair, o provedor `reserva` responde no
        lugar. Depois, se veio um link de imagem (ou você pediu uma), a mesma thread baixa para projetar.
        """
        geracao = self.geracao
        sistema = sistema_hermes(self.sistema)

        def trabalho():
            """Roda numa thread: resposta, depois a imagem; nunca levanta."""
            link = None
            try:
                texto = hermes.conversar(sistema, mensagens,
                                         lambda _ferramenta, rodando: self._ferramenta.emit(rodando, geracao))
                resultado, link = separar_imagem(texto)
            except Exception as erro:                  # Hermes fora do ar, chave errada, bug...
                motivo = str(erro) if isinstance(erro, provedores.ErroIA) else f"{type(erro).__name__}: {erro}"
                self._pronto.emit("hermes_caiu", motivo, geracao)
                resultado = self._responder_com(reserva, mensagens, imagem)
            self._pronto.emit("conversa", resultado, geracao)
            if link or termo:
                self._pronto.emit("imagem_vindo", None, geracao)
                self._pronto.emit("imagem", self._achar_imagem(link, termo), geracao)

        threading.Thread(target=trabalho, name="pestinha-hermes", daemon=True).start()

    def _responder_com(self, cliente, mensagens, imagem):
        """O provedor escolhido responde (no lugar do Hermes); a falha vira o resultado."""
        if cliente is None:
            return provedores.ErroIA("o Hermes não respondeu e não há outro provedor configurado")
        try:
            return cliente.responder(self.sistema, mensagens, imagem)
        except provedores.ErroIA as erro:
            return erro
        except Exception as erro:
            return provedores.ErroIA(f"falha inesperada: {type(erro).__name__}: {erro}")

    @staticmethod
    def _achar_imagem(link, termo):
        """(título, bytes): primeiro o link que o Hermes deu, depois a Wikipédia pelo termo. None se nada deu."""
        if link:
            try:
                return (termo or titulo_do_link(link)).strip().capitalize(), baixar_imagem(link)
            except Exception as erro:                  # link quebrado ou que não é imagem: tenta a Wikipédia
                log(f"[imagem] o link do Hermes não deu: {erro}")
        if termo:
            try:
                return buscar_imagem_na_web(termo)
            except Exception as erro:
                return provedores.ErroIA(f"falha inesperada na imagem: {type(erro).__name__}: {erro}")
        return None

    def buscar_imagem(self, termo):
        """Acha o link de uma imagem de `termo` e baixa (em outra thread); vai só o termo."""
        geracao = self.geracao
        self.buscando_imagem = True

        def trabalho():
            """Roda numa thread: devolve (título, bytes), None ou a falha, nunca levanta."""
            self._pronto.emit("imagem", self._achar_imagem(None, termo), geracao)

        threading.Thread(target=trabalho, name="pestinha-imagem", daemon=True).start()

    def _ao_usar_ferramenta(self, rodando, geracao):
        """O Hermes começou ou terminou de usar uma ferramenta (pesquisa, página, memória)."""
        if geracao == self.geracao:
            self.ferramentas = max(0, self.ferramentas + (1 if rodando else -1))

    # ---------------- pesquisar ----------------

    def pesquisar(self, termo, now):
        """O Hermes pesquisa `termo` na internet (em outra thread). Leva só o termo e o resumo."""
        self.ultima_pesquisa = now
        try:
            cliente = self.hermes()
        except provedores.ErroIA as erro:
            self._avisar(f"[pesquisa] {erro}", str(erro), now)
            return
        self.pesquisando = True
        pedido = pedido_dica(termo, self.ultimo_resumo, self.estado(), self.lembrado())
        self._em_thread("pesquisa", cliente, [{"role": "user", "content": pedido}], None)

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
        elif tipo == "hermes_caiu":
            self._avisar(f"[hermes] {resultado}", f"Hermes: {resultado}", now)
        elif tipo == "imagem_vindo":
            self.buscando_imagem = True
        elif tipo == "imagem":
            self.buscando_imagem = False
            if isinstance(resultado, Exception):
                self._avisar(f"[imagem] {resultado}", f"imagem: {resultado}", now)
            elif resultado is None:
                log("[imagem] não achei uma imagem")
            elif self.ligada() and self.perms["pesquisar"] and not self.app._congelado():
                self.imagem.emit(*resultado)
        elif tipo == "pesquisa":
            self.pesquisando = False
            if isinstance(resultado, Exception):
                self._avisar(f"[pesquisa] {resultado}", f"pesquisa: {resultado}", now)
            elif self.vendo() and self.perms["pesquisar"] and not self.app._congelado():
                dica = ler_dica(resultado)
                if dica:
                    self.ja_disse = (self.ja_disse + [dica])[-JA_DISSE:]
                    self.fala.emit(dica)
        else:
            self.respondendo = False
            self.ferramentas = 0
            if isinstance(resultado, Exception):
                self.erro_conversa.emit(str(resultado))
            elif not self.app._congelado():
                self._respondido(limpar_fala(resultado) or "...")

    def _entender(self, obs, pedido=False):
        """O que ele viu vira sinal para a rede e, às vezes, um comentário."""
        app = self.app
        if obs.resumo:
            self.ultimo_resumo = obs.resumo
            if self.perms["lembrar"]:
                app.lembrancas.anotar(senses.get_active_app(), obs.resumo)
        app.senses.saw(obs.sinais)
        novidade = obs.sinais.get("VISAO_NOVO", 0.0)
        if novidade > 0.3:
            app.drives.stimulate("novelty", novidade)  # coisa nova na tela também tira o tédio
        if self.debugging():
            log("[visão] sinais " + " ".join(f"{k[6:].lower()}={v:.2f}" for k, v in obs.sinais.items()))
        now = time.monotonic()
        if obs.pesquisar and self.pode_pesquisar(now):
            self.pesquisar(obs.pesquisar, now)
        comentario = obs.comentario or (obs.resumo if pedido else "")
        if not pedido and self.em_jogo() and now - self.ultima_fala < app.prof["fala_jogo"]:
            comentario = ""                            # em jogo ele olha muito: fala bem menos do que vê
        if comentario and (pedido or self.perms["comentarios"]):
            self.ja_disse = (self.ja_disse + [comentario])[-JA_DISSE:]
            if not pedido:
                self.ultima_fala = now
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
        self._avisar(f"[visão] {motivo}", motivo, now)

    def _avisar(self, linha, motivo, now):
        """Loga e avisa na bandeja, sem repetir o mesmo aviso toda hora."""
        log(linha)
        if now - self._avisos.get(motivo, float("-inf")) >= REPETE_AVISO:
            self._avisos[motivo] = now
            self.aviso.emit(motivo)
