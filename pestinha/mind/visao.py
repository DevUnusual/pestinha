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
               se a tela quase não mudou e fala no máximo a cada `fala_jogo`. Comenta a jogabilidade, não o
               visual. Com "Estudar os jogos", a olhada diz qual é o jogo e onde você está, e ele lê sobre o
               jogo e acompanha o seu progresso na história, sem spoiler (mind/jogo_ctl.py).
    desenhar   com "Desenhar na tela", a olhada (campo "desenhar") ou a resposta do chat (linha "DESENHAR:")
               pode trazer formas sobre o print; elas são desenhadas no monitor que foi fotografado
               (ia/desenho.py, world/rabisco.py).
    vídeo      com "Assistir vídeos comigo", a olhada diz se você está vendo um vídeo (campo "video") e ele
               pergunta se assiste junto (mind/video_ctl.py); enquanto assiste, olha a tela no ritmo do
               jogo, não comenta e anota o que aparece (slides, código, cenas) para o resumo.

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

from PySide6.QtCore import QBuffer, QIODevice, QObject, QPoint, Qt, QTimer, Signal
from PySide6.QtGui import QGuiApplication, QImage

from ..ia import orcamento, pesquisa, provedores, roteador
from .. import ajustes
from .politica import PoliticaFala
from ..ia.desenho import INSTRUCOES_CHAT as INSTRUCOES_DESENHO, separar_desenho
from ..ia.imagem import baixar as baixar_imagem, buscar as buscar_imagem_na_web, pedido_de_imagem as imagem_pedida
from ..ia.imagem import titulo_do_link
from ..ia.mente import (INSTRUCOES_VOZ, Conversa, ler_dica, ler_observacao, limpar_fala, limpar_resposta,
                        pedido_dica, pedido_observacao, prompt_sistema, separar_imagem, separar_tocar,
                        sistema_hermes)
from ..log import log, recentes as log_recente
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


# tipo da chamada (o sinal _pronto) -> tarefa do orçamento (limite de saída, ia/orcamento.py)
TAREFAS = {"observacao": "olhada", "conversa": "chat", "pesquisa": "dica"}


def tela_da_janela(retangulo_ativo=None, dpr=1.0):
    """O QScreen do monitor onde está a janela ativa (o principal, se não souber). None se não houver."""
    tela = None
    if retangulo_ativo:
        meio = QPoint(int((retangulo_ativo[0] + retangulo_ativo[2]) / 2 / dpr),
                      int((retangulo_ativo[1] + retangulo_ativo[3]) / 2 / dpr))
        tela = QGuiApplication.screenAt(meio)
    return tela or QGuiApplication.primaryScreen()


def onde_fica(retangulo_ativo=None, dpr=1.0):
    """(x, y, largura, altura) lógicos do monitor que o print fotografa, para desenhar em cima. None se não houver."""
    tela = tela_da_janela(retangulo_ativo, dpr)
    if tela is None:
        return None
    g = tela.geometry()
    return (g.x(), g.y(), g.width(), g.height())


def capturar_tela(retangulo_ativo=None, dpr=1.0):
    """Print do monitor onde está a janela ativa, reduzido e em JPEG base64. None se não deu."""
    tela = tela_da_janela(retangulo_ativo, dpr)
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
    tocar = Signal(str)             # a IA decidiu tocar música (linha "TOCAR:"): o estilo, '' se ela não escolheu
    desenho = Signal(object, object)    # (formas, monitor fotografado): a IA quer destacar algo na tela
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
        self.ultima_fala = float("-inf")    # último comentário espontâneo
        self.politica = PoliticaFala()      # se o comentário da olhada aparece (mind/politica.py)
        self._mini = None                   # miniatura do último print enviado
        self.geracao = 0                    # muda no pânico/pausa: respostas antigas são descartadas
        self._pedido_seu = False            # a olhada a caminho foi pedida por você (pelo menu)
        self._pergunta = ""                 # a mensagem do chat que está sendo respondida
        self._tela_print = None             # (x, y, largura, altura) do monitor do último print
        self._onde_olhada = None            # o monitor do print da olhada a caminho
        self._onde_conversa = None          # o monitor do print da conversa a caminho
        self._cliente = None
        self._cliente_de = None
        self._olhada = None                # o cliente de quem olha a tela (cliente_olhada)
        self._olhada_de = None
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

    def pode_desenhar(self):
        """"Desenhar na tela" ligado (só vale vendo a tela: ele desenha sobre o que viu no print)."""
        return self.vendo() and self.perms["desenhar"]

    def assistindo_video(self):
        """Ele está assistindo um vídeo com você (fica quieto)."""
        video = getattr(self.app, "video", None)
        return video is not None and video.ocupado()

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
        """Segundos até a próxima olhada: curto em jogo ou assistindo vídeo (mais com o Ollama, que não cobra),
        longo fora."""
        prof = self.app.prof
        if self.em_jogo() or self.assistindo_video():
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
        jogo = getattr(self.app, "jogo", None)
        if jogo is not None:
            jogo.cancelar()

    def chave_nova(self):
        """Você salvou uma chave: recria o cliente e olha de novo logo (sem esperar o tempo de erro)."""
        self._cliente = self._hermes = self._olhada = None
        self._avisos.clear()
        self.proxima = min(self.proxima, time.monotonic() + ESPERA_TROCA)

    def cliente(self):
        """O cliente do provedor escolhido (recriado se você trocar de provedor ou modelo)."""
        chave = (self.perms["ia_provedor"], self.perms["ia_modelo"], self.perms["ia_ollama_url"])
        if self._cliente is None or self._cliente_de != chave:
            self._cliente = provedores.criar_cliente(*chave)
            self._cliente_de = chave
        return self._cliente

    def cliente_olhada(self):
        """O cliente de quem olha a tela (provedores.modelo_da_olhada): em geral, o Ollama ou o Claude Haiku. O
        chat, o estudo e o resumo continuam no `cliente()`. Se o da olhada não der (no automático, sem a chave do
        Claude, por exemplo), a olhada vai pelo do chat."""
        escolha = provedores.modelo_da_olhada(self.perms)
        if escolha == (self.perms["ia_provedor"], self.perms["ia_modelo"], self.perms["ia_ollama_url"]):
            return self.cliente()                       # o mesmo do chat: um cliente só
        de = (self.perms.get("olhada_provedor", "auto"),) + escolha    # o automático pode cair no do chat
        if self._olhada is None or self._olhada_de != de:
            self._olhada_de = de
            try:
                self._olhada = provedores.criar_cliente(*escolha)
            except provedores.ErroIA as erro:
                if self.perms.get("olhada_provedor", "auto") != "auto":
                    self._olhada = None
                    raise
                log(f"[visão] a olhada vai pelo modelo do chat ({erro})")
                self._olhada = self.cliente()
        return self._olhada

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

    def conhecido(self, texto=""):
        """O que ele aprendeu assistindo vídeos com você (mind/conhecimento.py), para o chat."""
        conhecimento = getattr(self.app, "conhecimento", None)
        return conhecimento.contexto(texto) if conhecimento is not None else ""

    def sobre_jogo(self):
        """O que ele sabe do jogo de agora, até onde você chegou (mind/jogo_ctl.py). '' se nada."""
        jogo = getattr(self.app, "jogo", None)
        return jogo.contexto_olhada() if jogo is not None else ""

    def jogos(self, texto=""):
        """O que ele sabe dos seus jogos, para o chat (a história adiante só se você pediu spoiler)."""
        jogo = getattr(self.app, "jogo", None)
        return jogo.contexto_chat(texto) if jogo is not None else ""

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
        assistindo = self.assistindo_video()
        jogo = self.em_jogo() and not assistindo
        rapido = jogo or assistindo                    # olhando a cada poucos segundos
        self.ultima_olhada = now
        self.proxima = now + self.intervalo()
        try:
            cliente = self.cliente_olhada()
        except provedores.ErroIA as erro:
            self._falhou(str(erro), now)
            return
        imagem = self._print() if cliente.ve_imagem else None
        self._onde_olhada = self._tela_print if imagem else None
        if imagem:
            mini = miniatura(imagem)
            if (rapido and not self._pedido_seu and diferenca(mini, self._mini) < QUASE_IGUAL
                    and now - self.ultimo_envio < self.app.prof["visao_intervalo"]):
                return                                 # a tela quase não mudou: não gasta uma olhada
            self._mini = mini
        self.ultimo_envio = now

        def montar(lembrancas, sobre_jogo):
            return pedido_observacao(programa, titulo, self.app.activity, self.app.pet_state.emotion,
                                     self.ultimo_resumo, estado, self.ja_disse, lembrancas,
                                     self.pode_pesquisar(now) and not assistindo, jogo,
                                     desenhar=bool(imagem) and self.pode_desenhar() and not assistindo,
                                     video=self.perms["videos"] and not assistindo, assistindo=assistindo,
                                     sobre_jogo=sobre_jogo)

        programa, titulo, estado = senses.get_active_app(), senses.get_active_title(), self.estado()
        # o que sobra da janela vai para o que ele sabe do jogo e as lembranças (encolhem nessa ordem inversa)
        resto = orcamento.disponivel(cliente, "olhada", self.sistema, bool(imagem)) - orcamento.tokens(montar("", ""))
        lembrancas, sobre = orcamento.encaixar([(self.lembrado(), 2), (self.sobre_jogo() if jogo else "", 1)], resto)
        pergunta = montar(lembrancas, sobre)
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
            retangulo = senses.foreground_rect(dpr)
            imagem = capturar_tela(retangulo, dpr)
            self._tela_print = onde_fica(retangulo, dpr) if imagem else None
            return imagem
        except Exception as erro:                      # tela bloqueada, sem permissão de captura...
            log(f"[visão] sem print: {erro}")
            self._tela_print = None
            return None

    # ---------------- conversar ----------------

    def perguntar(self, texto, por_voz=False):
        """Você escreveu no chat: ele responde (pelo Hermes, se estiver conectado; vendo a tela, se puder).
        `por_voz`: você chamou pelo nome; numa dúvida, ele termina perguntando se quer saber mais."""
        if self.respondendo or not self.ligada() or not self.perms["conversa"] or self.app._congelado():
            return False
        hermes = cliente = None
        # o Hermes (pesquisa e memória, mais lento) só recebe o que pede isso; o resto vai direto ao provedor
        local = bool(self.perms.get("memoria_local"))
        if self.com_hermes() and roteador.pede_hermes(texto, memoria_local=local):
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
        self._onde_conversa = self._tela_print if imagem else None
        quem = cliente if cliente is not None else hermes
        extra = (orcamento.tokens(INSTRUCOES_DESENHO) if imagem else 0) + (orcamento.tokens(INSTRUCOES_VOZ) if por_voz else 0)
        # com a memória local, lembranças e vídeos só vão quando a pergunta pede memória, e só os trechos que
        # têm a ver (mind/memoria_local.py); o chat leva só as conversas de hoje
        self.conversa.so_hoje = local
        trechos = self.app.memoria_local.buscar(texto) if local and roteador.pede_memoria(texto) else []
        mensagens = self.conversa.mensagens(texto, self.ultimo_resumo if self.vendo() else "", self.estado(),
                                            "" if local else self.lembrado(),
                                            log_recente() if roteador.sobre_o_programa(texto) else (),
                                            "" if local else self.conhecido(texto),
                                            self.jogos(texto),
                                            memoria=trechos,
                                            disponivel=orcamento.disponivel(quem, "chat", self.sistema, bool(imagem))
                                            - extra)
        if imagem and self.pode_desenhar():
            mensagens[-1] = dict(mensagens[-1], content=mensagens[-1]["content"] + "\n" + INSTRUCOES_DESENHO)
        if por_voz:
            mensagens[-1] = dict(mensagens[-1], content=mensagens[-1]["content"] + "\n" + INSTRUCOES_VOZ)
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
            return cliente.responder(self.sistema, mensagens, imagem, tarefa="chat")
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

        tarefa = TAREFAS.get(tipo, "chat")

        def trabalho():
            """Roda numa thread: devolve o texto ou a falha, nunca levanta."""
            try:
                resultado = cliente.responder(self.sistema, mensagens, imagem, tarefa=tarefa)
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
                resultado, formas = separar_desenho(resultado)
                resultado, estilo = separar_tocar(resultado)
                self._respondido(limpar_resposta(resultado) or "Bora!")
                if estilo is not None:
                    self.tocar.emit(estilo)             # a IA entendeu que você pediu música
                if formas and self._onde_conversa and self.pode_desenhar():
                    self.desenho.emit(formas, self._onde_conversa)

    def _entender(self, obs, pedido=False):
        """O que ele viu vira sinal para a rede e, às vezes, um comentário."""
        app = self.app
        if obs.resumo:
            self.ultimo_resumo = obs.resumo
            if self.perms["lembrar"]:
                app.lembrancas.anotar(senses.get_active_app(), obs.resumo)
        app.senses.saw(obs.sinais)
        if obs.resumo and self.assistindo_video():
            app.video.viu_tela(obs.resumo)             # o que aparece no vídeo vai para o resumo dele
        if self.em_jogo() and not self.assistindo_video() and getattr(app, "jogo", None) is not None:
            app.jogo.viu(obs.jogo, obs.onde, time.monotonic())     # qual jogo e onde você está nele
        novidade = obs.sinais.get("VISAO_NOVO", 0.0)
        if novidade > 0.3:
            app.drives.stimulate("novelty", novidade)  # coisa nova na tela também tira o tédio
        if self.debugging():
            log("[visão] sinais " + " ".join(f"{k[6:].lower()}={v:.2f}" for k, v in obs.sinais.items()))
        now = time.monotonic()
        if obs.video and self.perms["videos"] and getattr(app, "video", None) is not None:
            app.video.viu_video(now)                   # um vídeo com fala: ele começa a assistir junto
        quieto = self.assistindo_video() and not pedido     # assistindo: só presta atenção
        if obs.pesquisar and self.pode_pesquisar(now) and not quieto:
            self.pesquisar(obs.pesquisar, now)
        comentario = "" if quieto else (obs.comentario or (obs.resumo if pedido else ""))
        if not comentario or not (pedido or self.perms["comentarios"]):
            return
        onde = self._onde_olhada
        if pedido:
            self._falar(comentario, obs, onde, pedido=True)
            return
        # a rede decide: os sinais acabaram de entrar nela; um instante depois, o tom dos motores mostra a reação
        geracao = self.geracao
        QTimer.singleShot(int(ajustes.FALA_ESPERA_REDE * 1000),
                          lambda: self._decidir_fala(comentario, obs, onde, geracao))

    def _decidir_fala(self, comentario, obs, onde, geracao):
        """Depois de a rede reagir ao que ele viu: a política diz se o comentário aparece."""
        app = self.app
        if geracao != self.geracao or app._congelado() or not self.perms["comentarios"]:
            return                                      # pânico, pausa ou cancelado no meio da espera
        now = time.monotonic()
        tom = dict(getattr(getattr(app.pet_state, "tone", None), "r", {}) or {})
        jogo = self.em_jogo()
        intervalo = app.prof["fala_jogo"] if jogo else None     # em jogo ele olha muito mais
        decisao = self.politica.decidir(now, comentario, obs.sinais, tom, intervalo=intervalo, jogo=jogo)
        if self.debugging():
            log(f"[visão] fala {'sim' if decisao.falar else 'não'}: {decisao.motivo}")
        if decisao.falar:
            self.politica.falou(now)
            self.ultima_fala = now
            self._falar(comentario, obs, onde)

    def _falar(self, comentario, obs, onde, pedido=False):
        """O comentário vai para o balão (e o desenho vem junto)."""
        self.ja_disse = (self.ja_disse + [comentario])[-JA_DISSE:]
        self.fala.emit(comentario)
        if obs.desenhar and onde and self.pode_desenhar():
            self.desenho.emit(obs.desenhar, onde)       # o desenho vem junto do comentário

    def _respondido(self, texto):
        """Resposta do chat: a inteira vai para o chat (e o histórico), a curta para o balão; guarda na conversa
        e conta como atenção sua."""
        app = self.app
        self.conversa.registrar(self._pergunta, texto)
        app.senses.kick("CONVERSA", 0.8)
        app.drives.touched("poke")                     # conversar é atenção: a carência diminui
        app.memory.on_interaction()
        app.timeline.note_interaction()
        if app.asleep:
            app.sleep.wake(startled=False)
        self.resposta.emit(texto)
        self.fala.emit(limpar_fala(texto))

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
