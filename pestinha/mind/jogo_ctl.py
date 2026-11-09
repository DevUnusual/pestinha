"""
JOGO_CTL - com "Estudar os jogos", ele descobre o que você está jogando, lê sobre o jogo e acompanha até
onde você chegou na história, para comentar a jogatina sem dar spoiler.

    nome      a olhada em jogo devolve o nome do jogo (campo "jogo"); sem ele, vale o título da janela. Só
              depois de ver o mesmo nome duas vezes seguidas ele acredita (uma olhada confusa não vira estudo).
    estudar   uma vez por jogo, numa thread: o artigo da Wikipédia (vai só o nome do jogo) e o provedor de IA
              condensa em premissa, gameplay, dicas e a história em trechos (ia/jogo_info.py). Sem artigo,
              com "Conectar ao Hermes", o Hermes pesquisa no lugar. Fica em mind/jogos.py.
    onde      a olhada devolve onde você está (campo "onde": capítulo, área, missão); quando muda, uma
              chamada curta descobre em qual trecho da história isso fica, e o progresso só sobe.
    contexto  a olhada e o chat recebem o que ele sabe do jogo até o seu trecho; a história adiante só vai
              para o chat se você pedir spoiler (jogo_info.pediu_spoiler).
"""

import threading
import time

from PySide6.QtCore import QObject, Signal

from ..ia import orcamento, provedores
from ..ia.jogo_info import (SISTEMA_ESTUDO, SISTEMA_TRECHO, buscar_wikipedia, chave, ler_estudo, ler_trecho,
                            nome_pelo_titulo, pedido_estudo, pedido_trecho, pediu_spoiler)
from ..log import log
from ..sense import senses
from .jogos import Jogos

CONFIRMA = 2                # olhadas seguidas com o mesmo nome até ele acreditar que é esse o jogo
REESTUDA = 3600.0           # s antes de tentar de novo um jogo cujo estudo falhou (sem rede, sem chave...)
LOCALIZA_A_CADA = 45.0      # s mínimos entre uma localização na história e outra


class JogoController(QObject):
    """O jogo de agora, o estudo dele e o progresso. Usa os atributos do PestinhaApp (perms, visao)."""

    fala = Signal(str)                      # "li sobre o jogo" para o balão
    _pronto = Signal(str, object, object, int)      # (tipo, chave, resultado, geração) da thread

    def __init__(self, app, caminho):
        """`caminho` é memory/pets/<pet>/jogos.json."""
        super().__init__()
        self.app = app
        self.memoria = Jogos(caminho)
        self.atual = None                   # a chave do jogo de agora (confirmado)
        self._nome_atual = ""
        self._candidato = None
        self._vezes = 0
        self.estudando = False
        self.localizando = False
        self._falhas = {}                   # chave -> quando o estudo falhou
        self._ultima_localizacao = float("-inf")
        self._localizado = {}               # chave -> o último "onde" já localizado
        self.geracao = 0
        self._pronto.connect(self._ao_pronto)

    # ---------------- estado ----------------

    def ligado(self):
        """"Estudar os jogos" ligado e você jogando."""
        return bool(self.app.perms.get("estudar_jogos")) and self.app.visao.em_jogo()

    def cancelar(self):
        """Pânico, pausa ou IA desligada: esquece o que estava a caminho."""
        self.geracao += 1
        self.estudando = self.localizando = False

    def contexto_olhada(self):
        """O que ele sabe do jogo de agora, para a olhada (sem passar de onde você está). '' se nada."""
        if not self.ligado() or not self.atual:
            return ""
        return self.memoria.contexto_olhada(self.atual)

    def contexto_chat(self, texto):
        """O que ele sabe dos seus jogos, para o chat; a história inteira só se você pediu spoiler."""
        if not self.app.perms.get("estudar_jogos"):
            return ""
        atual = self.atual if self.app.visao.em_jogo() else None
        return self.memoria.contexto_chat(texto, atual, pediu_spoiler(texto))

    # ---------------- o que a olhada viu ----------------

    def viu(self, nome, onde, now):
        """Uma olhada em jogo: `nome` do jogo (do modelo; vazio usa o título) e `onde` você está."""
        if not self.ligado():
            return
        nome = (nome or "").strip() or nome_pelo_titulo(senses.get_active_title())
        k = chave(nome)
        if not k:
            return
        if k == self._candidato:
            self._vezes += 1
        else:
            self._candidato, self._vezes = k, 1
        if self._vezes < CONFIRMA and self.memoria.get(k) is None:
            return
        if k != self.atual:
            self.atual, self._nome_atual = k, nome
            log(f"[jogos] jogando {nome}")
        if onde:
            self.memoria.anotar_onde(k, nome, onde)
        if not self.memoria.estudado(k):
            if not self.estudando and now - self._falhas.get(k, float("-inf")) >= REESTUDA:
                self.estudar(k, nome)
        elif onde:
            self._talvez_localizar(k, onde, now)

    # ---------------- estudar ----------------

    def estudar(self, k, nome):
        """Lê sobre o jogo numa thread: Wikipédia + provedor de IA (ou o Hermes, se não achar artigo)."""
        visao = self.app.visao
        try:
            cliente = visao.cliente()
        except provedores.ErroIA as erro:
            self._falhas[k] = time.monotonic()
            log(f"[jogos] sem IA para estudar {nome}: {erro}")
            return
        hermes = None
        if visao.com_hermes():
            try:
                hermes = visao.hermes()
            except provedores.ErroIA:
                hermes = None
        self.estudando = True
        geracao = self.geracao

        def trabalho():
            """Roda numa thread: devolve (estudo ou None, fonte) ou a falha, nunca levanta."""
            try:
                artigo = buscar_wikipedia(nome)
                if artigo:
                    titulo, texto = artigo
                    quem, fonte = cliente, f"Wikipédia: {titulo}"
                else:
                    texto, quem, fonte = "", hermes or cliente, "Hermes" if hermes else "o que a IA sabia"
                # o artigo encolhe (pelo fim) até caber: o pedido e as instruções nunca são cortados
                resto = orcamento.disponivel(quem, "estudo", SISTEMA_ESTUDO) - orcamento.tokens(pedido_estudo(nome, "x"))
                texto = orcamento.encurtar(texto, resto, razao=orcamento.PROSA) if texto else ""
                resposta = quem.responder(SISTEMA_ESTUDO, [{"role": "user", "content": pedido_estudo(nome, texto)}],
                                          tarefa="estudo")
                resultado = (ler_estudo(resposta), fonte)
            except provedores.ErroIA as erro:
                resultado = erro
            except Exception as erro:                  # bug ou rede estranha: vira log, não derruba
                resultado = provedores.ErroIA(f"falha inesperada: {type(erro).__name__}: {erro}")
            self._pronto.emit("estudo", k, resultado, geracao)

        threading.Thread(target=trabalho, name="pestinha-jogo", daemon=True).start()

    # ---------------- localizar na história ----------------

    def _talvez_localizar(self, k, onde, now):
        """Se o lugar mudou, descobre em qual trecho da história ele fica (no máximo a cada LOCALIZA_A_CADA)."""
        item = self.memoria.get(k)
        if (item is None or not item["historia"] or self.localizando
                or now - self._ultima_localizacao < LOCALIZA_A_CADA
                or self._localizado.get(k, "").lower() == onde.lower()):
            return
        try:
            cliente = self.app.visao.cliente()
        except provedores.ErroIA:
            return
        self._ultima_localizacao = now
        self._localizado[k] = onde
        self.localizando = True
        geracao = self.geracao
        pedido = pedido_trecho(item["nome"], item["historia"], onde, item["trecho"])
        total = len(item["historia"])

        def trabalho():
            """Roda numa thread: devolve o número do trecho (ou None), nunca levanta."""
            try:
                resultado = ler_trecho(cliente.responder(SISTEMA_TRECHO, [{"role": "user", "content": pedido}],
                                                         tarefa="trecho"), total)
            except Exception as erro:
                log(f"[jogos] não localizei: {type(erro).__name__}: {erro}")
                resultado = None
            self._pronto.emit("trecho", k, resultado, geracao)

        threading.Thread(target=trabalho, name="pestinha-jogo-trecho", daemon=True).start()

    # ---------------- respostas ----------------

    def _ao_pronto(self, tipo, k, resultado, geracao):
        """Resposta da thread, já na thread do Qt."""
        if geracao != self.geracao:
            return
        if tipo == "trecho":
            self.localizando = False
            if resultado:
                self.memoria.avancar(k, resultado)
            return
        self.estudando = False
        if isinstance(resultado, Exception):
            self._falhas[k] = time.monotonic()
            log(f"[jogos] não estudei o jogo: {resultado}")
            return
        estudo, fonte = resultado
        if estudo is None:                             # não achou nada: tenta de novo daqui a um tempo
            self._falhas[k] = time.monotonic()
            log("[jogos] não achei nada sobre o jogo")
            return
        self.memoria.guardar_estudo(k, estudo, fonte)
        if self.ligado() and k == self.atual and self.app.perms.get("comentarios", True):
            self.fala.emit(f"Li sobre {estudo['nome']}! Pode jogar tranquilo que eu não dou spoiler.")
