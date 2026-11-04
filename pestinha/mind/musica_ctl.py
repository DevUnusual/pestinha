"""
MÚSICA (controle) - toca a música que você pediu no chat e vai escolhendo as próximas.

Você pede um estilo ("toca um lo-fi"): ele busca no YouTube Music e começa. Quando a fila acaba, puxa o
"rádio" da música mais bem vista até ali, então a playlist vai mudando com o seu gosto e o humor dele
(curioso ou feliz, arrisca artistas que não conhece). O que conta como opinião (ia/musica.py, Gosto):
    👍 / "gostei"           o artista sobe e a música entra nas curtidas
    👎 / "não gostei"       o artista desce, a música nunca mais toca e pula na hora
    ⏭ / "pula"              o artista desce um pouco
    deixar tocar até o fim  o artista sobe um pouco (você não precisa fazer nada)

As buscas rodam em threads; o resultado volta pelo sinal _pronto, já na thread do Qt, e é descartado se
você pediu outra coisa (ou parou) no meio do caminho. Quem toca é o QMediaPlayer, criado na primeira música.
"""

import threading

from PySide6.QtCore import QObject, QUrl, Signal

from ..ia import musica
from ..log import log

VOLUME = 0.5
FILA_MINIMA = 5         # menos músicas livres que isso: puxa mais pelo rádio
MAX_FALHAS = 3          # músicas seguidas que não tocaram: para e avisa
CURIOSIDADE = {"curioso": 0.8, "feliz": 0.6, "contente": 0.5, "observando": 0.4, "triste": 0.15, "bravo": 0.2}


class MusicaController(QObject):
    """A playlist dele: pedir(estilo), comando('pular'...), e o estado para o cartão (atual, tocando())."""

    mudou = Signal()                    # música, pausa ou opinião mudou: o cartão redesenha
    aviso = Signal(str)                 # algo deu errado (vai para a bandeja)
    _pronto = Signal(str, object, int)  # (tipo, resultado, geração) de uma thread

    def __init__(self, app, arquivo=None):
        """`arquivo` é o musica.json do pet (o gosto aprendido); None guarda só na memória."""
        super().__init__()
        self.app = app
        self.gosto = musica.Gosto(arquivo).carregar()
        self.estilo = None              # None: sem música; '' : sem estilo (ele escolhe)
        self.fila = []                  # músicas candidatas (Faixa), na ordem em que chegaram
        self.tocadas = []               # ids que já tocaram nesta sessão
        self.atual = None
        self.opiniao = None             # "gostei" / "nao_gostei" já dado para a atual
        self.carregando = False         # buscando a fila ou o áudio da próxima
        self.pausada = False
        self.geracao = 0                # muda a cada música: descarta áudio buscado para a anterior
        self.lista = 0                  # muda a cada playlist: descarta o rádio buscado para a anterior
        self.falhas = 0
        self._enchendo = False          # buscando mais músicas pelo rádio
        self._player = None
        self._saida = None
        self._pronto.connect(self._ao_pronto)

    # ---------------- estado ----------------

    def ativa(self):
        """Tem uma playlist rodando (tocando, pausada ou buscando)."""
        return self.estilo is not None

    def tocando(self):
        """Tem música saindo agora."""
        return self.ativa() and self.atual is not None and not self.pausada and not self.carregando

    def curiosidade(self):
        """0 a 1: quanto ele arrisca artistas novos, conforme a emoção da rede agora."""
        return CURIOSIDADE.get(getattr(self.app.pet_state, "emotion", ""), 0.4)

    # ---------------- o que você pede ----------------

    def pedir(self, estilo):
        """Começa uma playlist de `estilo` ('' deixa ele escolher pelo seu gosto)."""
        self._parar_player()
        self.geracao += 1
        self.lista += 1
        self._enchendo = False
        self.estilo = estilo
        self.fila, self.atual, self.opiniao, self.pausada, self.falhas = [], None, None, False, 0
        self.carregando = True
        semente = self.gosto.curtidas[-1] if not estilo and self.gosto.curtidas else None
        if semente:
            self._rodar("fila", lambda: musica.radio(semente) or musica.buscar(""))
        else:
            self._rodar("fila", lambda: musica.buscar(estilo))
        self.mudou.emit()

    def comando(self, nome):
        """Um comando do chat, da voz ou do cartão ('gostei', 'pular'...). Devolve o que ele responde."""
        if not self.ativa():
            return None
        acao = {"gostei": self.gostei, "nao_gostei": self.nao_gostei, "pular": self.pular,
                "pausar": self.pausar, "continuar": self.continuar, "parar": self.parar}[nome]
        return acao()

    def gostei(self):
        """👍: o artista sobe e a música vira curtida (continua tocando)."""
        if self.atual is None or self.opiniao == "gostei":
            return None
        self._notar("gostei")
        return "Também curti! Vou lembrar."

    def nao_gostei(self):
        """👎: o artista desce, a música é banida e já pula."""
        if self.atual is None:
            return None
        self._notar("nao_gostei")
        self._proxima()
        return "Anotado, essa não toca mais."

    def pular(self):
        """⏭: vai para a próxima (sem opinião dada, conta como um pulo)."""
        if self.atual is not None and self.opiniao is None:
            self._notar("pulou")
        self._proxima()
        return "Próxima!"

    def pausar(self):
        """⏸: pausa (a fila fica)."""
        if self._player is not None and self.atual is not None and not self.pausada:
            self._player.pause()
            self.pausada = True
            self.mudou.emit()
        return "Pausei."

    def continuar(self):
        """▶: volta a tocar de onde parou."""
        if self._player is not None and self.pausada:
            self._player.play()
            self.pausada = False
            self.mudou.emit()
        return "Voltando!"

    def parar(self):
        """✕: para tudo e esquece a fila (o gosto aprendido fica)."""
        self.geracao += 1
        self.lista += 1
        self._parar_player()
        self.estilo, self.fila, self.atual, self.opiniao = None, [], None, None
        self.carregando = self.pausada = self._enchendo = False
        self.mudou.emit()
        return "Parei a música."

    # ---------------- fila ----------------

    def _notar(self, evento):
        """Opinião sobre a atual: muda a nota dos artistas e grava o gosto."""
        self.gosto.notar(self.atual, evento)
        if evento in ("gostei", "nao_gostei"):
            self.opiniao = evento
        try:
            self.gosto.salvar()
        except OSError as erro:
            log(f"[música] não deu para gravar o gosto: {erro}")
        self.mudou.emit()

    def _proxima(self):
        """Escolhe a próxima da fila e busca o áudio dela (em outra thread)."""
        self._parar_player()
        self.geracao += 1
        faixa = musica.escolher(self.fila, self.gosto, self.tocadas, self.curiosidade())
        self.atual, self.opiniao, self.pausada = faixa, None, False
        if faixa is None:
            self.carregando = True
            self._encher(forcar=True)           # acabou a fila: o rádio traz mais e aí ela continua
            self.mudou.emit()
            return
        self.tocadas.append(faixa.video_id)
        self.carregando = True
        self._rodar("audio", lambda: musica.link_de_audio(faixa.video_id))
        self._encher()
        self.mudou.emit()

    def _encher(self, forcar=False):
        """Poucas músicas livres: puxa o rádio da mais bem vista até agora (é assim que a playlist varia)."""
        livres = [f for f in self.fila if f.video_id not in self.tocadas and f.video_id not in self.gosto.banidas]
        if self._enchendo or (len(livres) >= FILA_MINIMA and not forcar):
            return
        semente = musica.semente(self.fila, self.gosto, self.tocadas) or self.atual
        if semente is None:
            if forcar:
                self._desistir("acabaram as músicas dessa playlist")
            return
        self._enchendo = True
        self._rodar("mais", lambda: musica.radio(semente.video_id), self.lista)     # vale até outra playlist

    # ---------------- threads ----------------

    def _rodar(self, tipo, trabalho, marca=None):
        """Roda `trabalho` numa thread; o resultado (ou a falha) volta pelo sinal _pronto com `marca`
        (a geração atual, se não vier: qualquer pulo descarta o resultado)."""
        geracao = self.geracao if marca is None else marca

        def rodar():
            """Na thread: nunca levanta."""
            try:
                resultado = trabalho()
            except Exception as erro:           # ErroMusica ou qualquer coisa inesperada
                resultado = erro if isinstance(erro, musica.ErroMusica) else musica.ErroMusica(
                    f"falha inesperada: {type(erro).__name__}: {erro}")
            self._pronto.emit(tipo, resultado, geracao)

        threading.Thread(target=rodar, name=f"pestinha-musica-{tipo}", daemon=True).start()

    def _ao_pronto(self, tipo, resultado, geracao):
        """Resultado de uma thread, já na thread do Qt."""
        if tipo == "mais":
            if geracao != self.lista or not self.ativa():
                return                          # era de uma playlist que você já trocou ou parou
            self._enchendo = False
            if not isinstance(resultado, Exception):
                self._juntar(resultado)
            if self.atual is None:              # a fila tinha acabado: retoma com o que chegou
                if isinstance(resultado, Exception) or not resultado:
                    self._desistir("acabaram as músicas dessa playlist")
                else:
                    self._proxima()
            return
        if geracao != self.geracao or not self.ativa():
            return                              # você pulou, parou ou pediu outra no meio do caminho
        if isinstance(resultado, Exception):
            log(f"[música] {resultado}")
            if tipo == "fila":
                self._desistir(str(resultado))
            else:
                self._falhou()
            return
        if tipo == "fila":
            self._juntar(resultado)
            self._proxima()
        elif tipo == "audio":
            self.carregando = False
            self._tocar_url(resultado)
            self.mudou.emit()

    def _juntar(self, faixas):
        """Acrescenta à fila as músicas que ainda não estão nela."""
        ids = {f.video_id for f in self.fila}
        self.fila += [f for f in faixas if f.video_id not in ids and not ids.add(f.video_id)]

    def _falhou(self):
        """Uma música não tocou: tenta a próxima; muitas seguidas, desiste."""
        self.falhas += 1
        if self.falhas >= MAX_FALHAS:
            self._desistir("o YouTube não está deixando tocar agora")
        else:
            self._proxima()

    def _desistir(self, motivo):
        """Para a playlist e conta o porquê."""
        self.parar()
        self.aviso.emit(f"música: {motivo}")

    # ---------------- player ----------------

    def _tocar_url(self, url):
        """Toca o link do áudio no QMediaPlayer (criado na primeira vez)."""
        if self._player is None:
            from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
            self._player = QMediaPlayer(self)
            self._saida = QAudioOutput(self)
            self._saida.setVolume(VOLUME)
            self._player.setAudioOutput(self._saida)
            self._player.mediaStatusChanged.connect(self._ao_status)
            self._player.errorOccurred.connect(lambda _erro, texto: self._ao_erro(texto))
        self._player.setSource(QUrl(url))
        self._player.play()

    def _parar_player(self):
        """Para o som (sem mexer na fila)."""
        if self._player is not None:
            self._player.stop()
            self._player.setSource(QUrl())

    def _ao_status(self, status):
        """A música acabou sozinha: você deixou tocar até o fim, e isso conta como gostar um pouco."""
        from PySide6.QtMultimedia import QMediaPlayer
        if status == QMediaPlayer.EndOfMedia and self.atual is not None:
            self.falhas = 0
            if self.opiniao is None:
                self._notar("ouviu")
            self._proxima()
        elif status == QMediaPlayer.BufferedMedia:
            self.falhas = 0

    def _ao_erro(self, texto):
        """O player não conseguiu tocar (link expirado, formato...): vai para a próxima."""
        if self.atual is not None and not self.carregando:
            log(f"[música] o player falhou: {texto}")
            self._falhou()
