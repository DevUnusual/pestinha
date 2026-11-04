"""
ASSISTIR - quando você está jogando, ele vai para o monitor ao lado e fica assistindo e comentando.

Com "Acompanhar jogos" e um jogo na tela (o mesmo critério da visão: mind/visao.py, em_jogo), ele escolhe
um lugar fora do jogo e fica parado lá, virado para a partida:
    vários monitores   no monitor mais à direita que não é o do jogo, perto da borda virada para o jogo
    um monitor só      no canto de baixo à direita, para atrapalhar o mínimo
Vai andando até lá; se não der para chegar andando (monitores desalinhados, ele em cima de uma janela) ou
o jogo estiver em tela cheia, aparece direto no lugar. Enquanto assiste: sem passeio, sem bolinha, sem
travessura e sem sentar no notebook. Os comentários continuam vindo da visão, no balão, em cima dele.

Se você arrastar ele para outro lugar, ele respeita: fica onde você soltou e só volta para o lugar dele
depois de ESPERA_APOS_ARRASTE. Castigo, sono e pânico continuam passando na frente (body/behavior.py).

Tela cheia num monitor não esconde o pet que está assistindo de outro (controle/sessao.py, ver
`libera_tela_cheia`).
"""

import math

DISTANCIA_BORDA = 150.0         # px da borda do monitor virada para o jogo
CANTO = 110.0                   # px do canto, com um monitor só
CHEGOU = 14.0                   # px: perto o bastante para parar
TRAVADO = 3.0                   # s andando sem chegar mais perto: aparece direto no lugar
PROGRESSO = 20.0                # px que contam como "chegou mais perto"
ESPERA_APOS_ARRASTE = 20.0      # s parado onde você soltou antes de voltar para o lugar dele
QUEDA = 60.0                    # px abaixo do topo do monitor onde ele aparece (e cai até o chão)


def monitor_de(areas, x, y):
    """Índice da área (monitor) que contém o ponto, ou None."""
    for i, (left, top, right, bottom) in enumerate(areas):
        if left <= x < right and top <= y < bottom:
            return i
    return None


def escolher_lugar(areas, jogo):
    """
    (x, índice do monitor) de onde ele assiste, ou None se não há monitor. `jogo` é o índice do monitor do
    jogo (None: não sabe, trata como o primeiro).
    """
    if not areas:
        return None
    jogo = 0 if jogo is None or not 0 <= jogo < len(areas) else jogo
    outros = [i for i in range(len(areas)) if i != jogo]
    if not outros:
        return areas[jogo][2] - CANTO, jogo
    escolhido = max(outros, key=lambda i: (areas[i][0], areas[i][2]))     # o mais à direita
    left, _top, right, _bottom = areas[escolhido]
    centro_jogo = (areas[jogo][0] + areas[jogo][2]) / 2
    if (left + right) / 2 >= centro_jogo:
        return left + DISTANCIA_BORDA, escolhido        # à direita do jogo: perto da borda da esquerda
    return right - DISTANCIA_BORDA, escolhido           # à esquerda do jogo: perto da borda da direita


class AssistirController:
    """Onde ele assiste e se já chegou. `atualizar` no ciclo de pensamento, `agir` a cada quadro."""

    def __init__(self):
        """Sem jogo: não está assistindo."""
        self.ativo = False
        self.lugar = None               # (x, índice do monitor)
        self.ponto_jogo = None          # (x, y) do meio do monitor do jogo: para onde ele olha
        self.outro_monitor = False      # o lugar é num monitor diferente do jogo
        self.solto_em = float("-inf")   # quando você soltou ele (depois de arrastar)
        self._areas = []
        self._melhor = math.inf         # menor distância até o lugar desde o último progresso
        self._progresso_em = 0.0

    def atualizar(self, now, jogando, areas, centro_jogo, body, tela_cheia=False):
        """
        A cada 100 ms: liga ou desliga o modo e recalcula o lugar. `centro_jogo` é o meio da janela do jogo
        (coordenadas lógicas) ou None. Com o jogo em tela cheia, ele já aparece no lugar (mesmo escondido).
        """
        if not jogando or not areas:
            self.ativo = False
            self.lugar = self.ponto_jogo = None
            self.outro_monitor = False
            return
        jogo = monitor_de(areas, *centro_jogo) if centro_jogo else None
        lugar = escolher_lugar(areas, jogo)
        jogo = 0 if jogo is None else jogo
        comecou = not self.ativo or lugar != self.lugar
        self.ativo = True
        self._areas = list(areas)
        self.lugar = lugar
        a = areas[jogo]
        self.ponto_jogo = ((a[0] + a[2]) / 2, (a[1] + a[3]) / 2)
        self.outro_monitor = lugar is not None and lugar[1] != jogo
        if comecou:
            self._melhor, self._progresso_em = math.inf, now
        if tela_cheia and self.outro_monitor and not body.held and monitor_de(areas, body.x, body.y) != lugar[1]:
            self.aparecer_no_lugar(body)

    def libera_tela_cheia(self):
        """Tela cheia não esconde o pet: ele está assistindo de outro monitor."""
        return self.ativo and self.outro_monitor

    def arrastado(self, now):
        """Você soltou ele depois de arrastar: fica onde está por ESPERA_APOS_ARRASTE."""
        self.solto_em = now

    def alvo(self, now, body):
        """(x, ponto para onde olhar) que o comportamento deve seguir agora, ou None (não está assistindo)."""
        if not self.ativo or self.lugar is None:
            return None
        if body.held or now - self.solto_em < ESPERA_APOS_ARRASTE:
            self._progresso_em = now                     # parado onde você soltou, assistindo de lá
            self._melhor = math.inf
            return body.x, self.ponto_jogo
        return self.lugar[0], self.ponto_jogo

    def agir(self, now, body, state):
        """A cada quadro: diz ao corpo para onde ir; se ele não consegue chegar andando, aparece lá."""
        alvo = self.alvo(now, body)
        state.assistindo = alvo
        if alvo is None or body.held:
            return
        x = alvo[0]
        distancia = abs(body.x - x)
        if distancia <= CHEGOU and monitor_de(self._areas, body.x, body.y) == self.lugar[1]:
            self._melhor, self._progresso_em = distancia, now
            return
        if distancia < self._melhor - PROGRESSO:          # andando (inclusive de um monitor para o outro)
            self._melhor, self._progresso_em = distancia, now
        elif now - self._progresso_em > TRAVADO:
            self.aparecer_no_lugar(body)
            self._progresso_em = now

    def aparecer_no_lugar(self, body):
        """Põe ele direto no lugar (um pouco acima do chão daquele monitor; a física faz ele cair)."""
        if self.lugar is None:
            return
        x, i = self.lugar
        body.x = x
        body.y = self._areas[i][1] + QUEDA
        body.vx = body.vy = 0.0
        body.omega = 0.0
        body.grounded = False
        body.platform = None
