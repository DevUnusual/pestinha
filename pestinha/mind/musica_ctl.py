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
você pediu outra coisa (ou parou) no meio do caminho. Quem toca é o QMediaPlayer, criado na primeira música,
a partir do áudio baixado em `pasta` (só a música da vez fica lá). Se mesmo assim cortar no meio, ele
tenta uma vez de onde parou. O que acontece (música, opinião, corte) vai para o log: é por ele que o pet
conta o que houve quando você pergunta.
"""

import random
import threading
from pathlib import Path

from PySide6.QtCore import QObject, QUrl, Signal

from ..ia import musica
from ..log import log

FILA_MINIMA = 5         # menos músicas livres que isso: puxa mais pelo rádio
MAX_FALHAS = 3          # músicas seguidas que não tocaram: para e avisa
MAX_RETOMADAS = 1       # cortou no meio: recomeça de onde parou esta quantidade de vezes, depois pula
EVENTO_NO_LOG = {"gostei": "você gostou de", "nao_gostei": "você não gostou de", "pulou": "você pulou"}
CURIOSIDADE = {"curioso": 0.8, "feliz": 0.6, "contente": 0.5, "observando": 0.4, "triste": 0.15, "bravo": 0.2}


class MusicaController(QObject):
    """A playlist dele: pedir(estilo), comando('pular'...), e o estado para o cartão (atual, tocando())."""

    mudou = Signal()                    # música, pausa ou opinião mudou: o cartão redesenha
    aviso = Signal(str)                 # algo deu errado (vai para a bandeja)
    _pronto = Signal(str, object, int)  # (tipo, resultado, geração) de uma thread

    def __init__(self, app, arquivo=None, pasta=None):
        """`arquivo` é o musica.json do pet (o gosto aprendido; None guarda só na memória); `pasta`, onde
        fica o áudio da música da vez (o padrão é memory/cache/musica)."""
        super().__init__()
        self.app = app
        self.gosto = musica.Gosto(arquivo).carregar()
        self.pasta = Path(pasta) if pasta else Path(app.paths.memory) / "cache" / "musica"
        self._retomar_em = None         # ms: depois de um corte, recomeça daqui
        self._retomadas = 0             # quantas vezes já recomeçou a música da vez
        self.estilo = None              # None: sem música; '' : sem estilo (ele escolhe)
        self.fila = []                  # músicas candidatas (Faixa), na ordem em que chegaram
        self.tocadas = []               # ids que já tocaram nesta sessão
        self.atual = None
        self.capa = None                # bytes da capa da música da vez (None: ainda não chegou ou não tem)
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
        """
        Começa uma playlist de `estilo`. Sem estilo ('') ele escolhe: às vezes puxa o rádio de uma música que
        você curtiu, às vezes um estilo do humor dele (curioso, arrisca mais). Devolve o estilo que ficou
        ('' quando foi pelo rádio de uma curtida).
        """
        self._parar_player()
        self.geracao += 1
        self.lista += 1
        self._enchendo = False
        semente = None
        if not estilo:
            if self.gosto.curtidas and random.random() > self.curiosidade():
                semente = random.choice(self.gosto.curtidas[-20:])
            else:
                estilo = musica.estilo_dele(getattr(self.app.pet_state, "emotion", ""))
        self.estilo = estilo
        self.fila, self.atual, self.opiniao, self.pausada, self.falhas = [], None, None, False, 0
        self.carregando = True
        log(f"[música] playlist de {estilo}" if estilo else "[música] playlist puxada de uma que você curtiu")
        if semente:
            self._rodar("fila", lambda: musica.radio(semente) or musica.buscar(musica.estilo_dele("")))
        else:
            self._rodar("fila", lambda: musica.buscar(estilo))
        self.mudou.emit()
        return estilo

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

    @property
    def volume(self):
        """0 a 1: o volume da música (o mesmo da próxima vez que abrir)."""
        return self.gosto.volume

    def mudar_volume(self, volume):
        """Muda o volume na hora e lembra dele. Devolve o que ele responde."""
        self.gosto.volume = max(0.0, min(1.0, float(volume)))
        if self._saida is not None:
            self._saida.setVolume(self.gosto.volume)
        try:
            self.gosto.salvar()
        except OSError as erro:
            log(f"[música] não deu para gravar o volume: {erro}")
        self.mudou.emit()
        return "Mudo." if self.gosto.volume == 0 else f"Volume em {round(self.gosto.volume * 100)}%."

    def parar(self):
        """✕: para tudo e esquece a fila (o gosto aprendido fica)."""
        self.geracao += 1
        self.lista += 1
        self._parar_player()
        self.estilo, self.fila, self.atual, self.opiniao = None, [], None, None
        self.carregando = self.pausada = self._enchendo = False
        if self.pasta.is_dir():
            musica.limpar_pasta(self.pasta)             # o áudio baixado não fica para trás
        self.mudou.emit()
        return "Parei a música."

    # ---------------- fila ----------------

    def _notar(self, evento):
        """Opinião sobre a atual: muda a nota dos artistas e grava o gosto."""
        self.gosto.notar(self.atual, evento)
        if evento in ("gostei", "nao_gostei"):
            self.opiniao = evento
        if evento != "ouviu":
            log(f"[música] {EVENTO_NO_LOG[evento]}: {self.atual.nome()}")
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
        self.capa = None
        if faixa is None:
            self.carregando = True
            self._encher(forcar=True)           # acabou a fila: o rádio traz mais e aí ela continua
            self.mudou.emit()
            return
        self.tocadas.append(faixa.video_id)
        self.carregando = True
        self._retomar_em, self._retomadas = None, 0
        self._rodar("audio", lambda: musica.baixar_audio(faixa.video_id, self.pasta))
        self._rodar("capa", lambda: musica.baixar_capa(faixa))
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
        if tipo == "capa":                      # capa é enfeite: sem ela, o disquinho fica liso
            if not isinstance(resultado, Exception):
                self.capa = resultado
                self.mudou.emit()
            return
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
            musica.limpar_pasta(self.pasta, manter=[resultado])
            log(f"[música] tocando {self.atual.nome()}")
            self._tocar(resultado)
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

    def _tocar(self, caminho):
        """Toca o áudio baixado no QMediaPlayer (criado na primeira vez)."""
        if self._player is None:
            from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
            self._player = QMediaPlayer(self)
            self._saida = QAudioOutput(self)
            self._saida.setVolume(self.volume)
            self._player.setAudioOutput(self._saida)
            self._player.mediaStatusChanged.connect(self._ao_status)
            self._player.errorOccurred.connect(lambda _erro, texto: self._ao_erro(texto))
        self._player.setSource(QUrl.fromLocalFile(str(caminho)))
        self._player.play()

    def progresso(self):
        """(segundos tocados, duração em segundos) da música da vez; (0, 0) sem música."""
        if self.atual is None:
            return 0.0, 0.0
        posicao = duracao = 0.0
        if self._player is not None and not self.carregando:
            posicao = max(0.0, self._player.position() / 1000)
            duracao = max(0.0, self._player.duration() / 1000)
        return posicao, duracao or float(self.atual.duracao)

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
        elif status in (QMediaPlayer.LoadedMedia, QMediaPlayer.BufferedMedia):
            self.falhas = 0
            if self._retomar_em is not None:        # recomeçando depois de um corte: volta para onde estava
                self._player.setPosition(self._retomar_em)
                self._retomar_em = None

    def _ao_erro(self, texto):
        """O player falhou: no meio da música, recomeça de onde parou (uma vez); senão, vai para a próxima."""
        if self.atual is None or self.carregando:
            return
        ms = self._player.position() if self._player is not None else 0
        onde = f"em {musica.tempo(ms / 1000)}" + (f" de {musica.tempo(self.atual.duracao)}" if self.atual.duracao else "")
        if ms > 0 and self._retomadas < MAX_RETOMADAS:
            self._retomadas += 1
            log(f"[música] cortou {self.atual.nome()} {onde} ({texto}); recomeçando de onde parou")
            self._retomar_em = ms
            fonte = self._player.source()
            self._player.setSource(QUrl())
            self._player.setSource(fonte)
            self._player.play()
            return
        log(f"[música] não consegui tocar {self.atual.nome()} {onde} ({texto}); pulando para a próxima")
        self._falhou()
