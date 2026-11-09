"""
POLÍTICA DE FALA - quem decide se o pet comenta o que viu é o app, não o modelo.

Sem Qt. O modelo sempre devolve uma fala candidata em cada olhada (ia/mente.py); ela só aparece no balão se
houver motivo, e o motivo vem da rede: os sinais da olhada entram nela (VISAO_*) e, um instante depois,
o tom dos motores mostra como ele reagiu (CHEER: alegria; WATCH: atenção). Em ordem:

    você pediu (menu ou chat)                    sempre fala
    sem fala candidata                           quieto
    em jogo                                      fala, respeitado o intervalo do perfil (fala_jogo): o
                                                 comentário da jogada é o que ele está ali para fazer, e o
                                                 próprio modelo fica quieto quando nada mudou
    intervalo mínimo desde a última espontânea   quieto (em jogo, o intervalo do perfil, mais curto)
    teto por hora                                quieto
    erro na tela acima do limiar                 fala (é quando ele mais ajuda)
    foco alto                                    quieto (você está concentrado: só um erro interrompe)
    graça acima do limiar e CHEER acima do dele  fala
    novidade acima do limiar e WATCH acima       fala
    o resto                                      quieto

Os números ficam em ajustes.py (FALA_*). A avaliação da IA (ferramentas/avaliar_ia.py) mede o resultado:
numa tela neutra ele fala no máximo 2 de 10 vezes; numa com erro, pelo menos 8 de 10.
"""

from collections import deque
from dataclasses import dataclass

from .. import ajustes

HORA = 3600.0


@dataclass
class Decisao:
    """Se a fala aparece e por quê (o motivo vai para o log no modo teste)."""
    falar: bool
    motivo: str


class PoliticaFala:
    """Guarda quando ele falou por conta própria e decide a próxima vez."""

    def __init__(self):
        """Sem fala nenhuma ainda."""
        self.falas = deque()                # instantes das falas espontâneas da última hora

    def decidir(self, agora, comentario, sinais, tom, pedido=False, intervalo=None, jogo=False):
        """
        Decide se `comentario` aparece. `sinais`: VISAO_* (0 a 1) da olhada; `tom`: o tom dos motores
        (MotorTone.r) já depois de a rede receber esses sinais; `intervalo`: o mínimo entre falas espontâneas
        (s; None usa FALA_INTERVALO_MIN). Não registra nada: quem fala chama `falou`.
        """
        if not comentario:
            return Decisao(False, "sem fala candidata")
        if pedido:
            return Decisao(True, "você pediu")
        while self.falas and agora - self.falas[0] > HORA:
            self.falas.popleft()
        minimo = ajustes.FALA_INTERVALO_MIN if intervalo is None else intervalo
        if self.falas and agora - self.falas[-1] < minimo:
            return Decisao(False, "falou há pouco")
        if jogo:
            return Decisao(True, "comentando a jogada")
        if len(self.falas) >= ajustes.FALA_MAX_POR_HORA:
            return Decisao(False, "já falou bastante nesta hora")
        erro = sinais.get("VISAO_ERRO", 0.0)
        if erro >= ajustes.FALA_LIMIAR_ERRO:
            return Decisao(True, f"erro na tela ({erro:.2f})")
        if sinais.get("VISAO_FOCO", 0.0) >= ajustes.FALA_LIMIAR_FOCO:
            return Decisao(False, "você está concentrado")
        graca, cheer = sinais.get("VISAO_GRACA", 0.0), tom.get("CHEER", 0.0)
        if graca >= ajustes.FALA_LIMIAR_GRACA and cheer >= ajustes.FALA_LIMIAR_CHEER:
            return Decisao(True, f"achou graça ({graca:.2f}, CHEER {cheer:.2f})")
        novo, watch = sinais.get("VISAO_NOVO", 0.0), tom.get("WATCH", 0.0)
        if novo >= ajustes.FALA_LIMIAR_NOVIDADE and watch >= ajustes.FALA_LIMIAR_WATCH:
            return Decisao(True, f"coisa nova ({novo:.2f}, WATCH {watch:.2f})")
        return Decisao(False, "nada que valha comentar")

    def falou(self, agora):
        """Uma fala espontânea apareceu: conta para o intervalo e o teto."""
        self.falas.append(agora)
