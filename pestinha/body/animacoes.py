"""
ANIMAÇÕES - como o corpo mostra o que a mente (IA, voz) está fazendo: só tempo e curvas, sem Qt.

Cada atividade tem um nível de 0 a 1 que entra e sai suave (nada aparece ou some de estalo):
    olhando      uma olhada na tela a caminho: a linha de leitura varre a tela e os olhos leem junto
    pensando     o chat ou a sua fala esperando resposta: vira detetive (chapéu de caçador, capa e
                 cachimbo soltando fumaça) e olha para cima
    pesquisando  pesquisa na internet a caminho: vira uma IA vilã (casca metálica, olhos vermelhos
                 bravos, grade da boca acesa) e os olhos varrem rápido, calculando
    ouvindo      segurando a tecla de falar: uma orelha gira para a frente e as ondinhas saem dela
    jogo         acompanhando um jogo: óculos 3D de cinema e um balde de pipoca (de vez em quando uma
                 pipoca pula para dentro da tela e ele mastiga)
    projetando   mostrando uma imagem que você pediu: olhos de holograma, olhando para a projeção

E dois eventos com hora marcada:
    falar(...)   o balão apareceu: um "pop" (achata, estica e assenta) e os olhos "falam" enquanto o texto
                 é digitado no balão
    olhou(...)   a olhada voltou: os olhos piscam devagar, como quem entendeu

Personalidade única para tudo (brincalhão): entra com desaceleração, sai mais rápido do que entra, e os
laços contínuos são senoidais para não dar tranco. Quem desenha é desenho_rosto.py; aqui só se calcula.
"""

import math
from dataclasses import dataclass

ATIVIDADES = ("olhando", "pensando", "pesquisando", "ouvindo", "jogo", "projetando")

ENTRADA = 0.22                  # s para uma atividade aparecer (≈ 95%)
SAIDA = 0.15                    # s para sumir: a saída é mais rápida que a entrada
ENTRADA_FANTASIA = 0.45         # s das fantasias (chapéu caindo, óculos descendo): coisa maior, mais tempo
FANTASIAS = ("pensando", "pesquisando", "jogo")

PERIODO_LEITURA = 1.6           # s de uma varrida de ida e volta da linha de leitura
PERIODO_FUMACA = 2.2            # s de uma baforada subir e sumir
BAFORADAS = 3
PERIODO_CALCULO = 0.9           # s de uma varrida dos olhos da IA vilã
PERIODO_PIPOCA = 2.6            # s entre uma pipoca e outra
VOO_PIPOCA = 0.55               # s da pipoca do balde até a tela
MASTIGA = 0.5                   # s mastigando depois de cada pipoca
INCLINACAO_OUVINDO = 7.0        # graus

SEGUNDOS_POR_LETRA = 0.035      # o balão digita a ~28 letras por segundo
FALA_MAX = 4.0                  # s no máximo de olhinhos "falando"
SILABAS_POR_SEGUNDO = 4.6
DURACAO_POP = 0.7               # s do achata-estica-assenta quando o balão aparece
DURACAO_ENTENDI = 0.45          # s da piscada lenta quando a olhada volta


def ease_out_cubic(t):
    """Desacelera no fim: entradas."""
    t = min(1.0, max(0.0, t))
    return 1.0 - (1.0 - t) ** 3


def ease_out_back(t, s=1.70158):
    """Passa um pouco do alvo e volta: o 'pop' brincalhão."""
    t = min(1.0, max(0.0, t)) - 1.0
    return 1.0 + (s + 1.0) * t ** 3 + s * t ** 2


def ease_in_out_sine(t):
    """Suave nas duas pontas: laços que não podem dar tranco."""
    t = min(1.0, max(0.0, t))
    return 0.5 - 0.5 * math.cos(math.pi * t)


def ida_e_volta(agora, periodo):
    """0 → 1 → 0 em `periodo` segundos, com as pontas suaves (para varrer de um lado ao outro)."""
    fase = (agora / periodo) % 1.0
    return ease_in_out_sine(fase * 2.0 if fase < 0.5 else 2.0 - fase * 2.0)


def aproximar(atual, alvo, dt, tempo):
    """Chega perto de `alvo` exponencialmente: em `tempo` segundos já percorreu ~95% do caminho."""
    if dt <= 0.0:
        return atual
    k = 1.0 - math.exp(-3.0 * dt / max(tempo, 1e-3))
    return atual + (alvo - atual) * k


def mola(t, amplitude=0.09, frequencia=3.2, amortecimento=4.2, ataque=0.06):
    """
    Uma mola amortecida que começa em zero: sobe até `amplitude` em `ataque` s (a antecipação) e oscila
    perdendo força. Positivo = achatado, negativo = esticado.
    """
    if t < 0.0:
        return 0.0
    envelope = min(1.0, t / ataque) if ataque > 0 else 1.0
    return amplitude * envelope * math.exp(-amortecimento * t) * math.cos(math.tau * frequencia * t)


@dataclass
class Pose:
    """Quanto o corpo e os olhos se deformam neste quadro (1.0 e 0.0 = sem mudança)."""
    escala_x: float = 1.0
    escala_y: float = 1.0
    inclinacao: float = 0.0     # graus a mais na rotação do corpo
    olho_x: float = 1.0         # escala da largura dos olhos
    olho_y: float = 1.0         # escala da altura dos olhos
    olhar: tuple = None         # (gx, gy) que manda no olhar agora, ou None
    peso_olhar: float = 0.0     # 0 = olhar natural, 1 = só o `olhar` daqui
    forma: str = None           # uma forma de olho (core/emotion.EYE_SHAPES) que manda agora, ou None
    peso_forma: float = 0.0


class Animacoes:
    """Os níveis das atividades e os eventos (fala, olhada); `passo` a cada quadro, `pose` para desenhar."""

    def __init__(self):
        """Tudo parado: nenhuma atividade, nenhum evento."""
        self.niveis = dict.fromkeys(ATIVIDADES, 0.0)
        self.fala_desde = float("-inf")
        self.fala_ate = float("-inf")
        self.entendi_desde = float("-inf")
        self._ultimo = None

    def passo(self, agora, ativas):
        """Um quadro: cada atividade em `ativas` sobe para 1, as outras descem para 0."""
        dt = 0.0 if self._ultimo is None else min(0.1, max(0.0, agora - self._ultimo))
        self._ultimo = agora
        for nome in ATIVIDADES:
            alvo = 1.0 if nome in ativas else 0.0
            tempo = (ENTRADA_FANTASIA if nome in FANTASIAS else ENTRADA) if alvo > self.niveis[nome] else SAIDA
            nivel = aproximar(self.niveis[nome], alvo, dt, tempo)
            self.niveis[nome] = 0.0 if nivel < 0.01 and alvo == 0.0 else nivel

    def nivel(self, nome):
        """O nível (0..1) de uma atividade agora."""
        return self.niveis.get(nome, 0.0)

    def parar(self):
        """Pânico ou pausa: tudo some na hora (não é animação de saída, é sumir)."""
        self.niveis = dict.fromkeys(ATIVIDADES, 0.0)
        self.fala_desde = self.fala_ate = self.entendi_desde = float("-inf")

    def falar(self, agora, texto):
        """O balão apareceu com `texto`: começa o pop e os olhinhos falam enquanto ele é digitado."""
        self.fala_desde = agora
        self.fala_ate = agora + min(FALA_MAX, SEGUNDOS_POR_LETRA * len(texto))

    def olhou(self, agora):
        """A olhada voltou: piscada lenta de quem entendeu."""
        self.entendi_desde = agora

    def letras_visiveis(self, agora, texto):
        """Quantas letras do balão já foram digitadas."""
        if agora >= self.fala_ate or self.fala_ate <= self.fala_desde:
            return len(texto)
        k = (agora - self.fala_desde) / (self.fala_ate - self.fala_desde)
        return max(0, min(len(texto), int(math.ceil(len(texto) * k))))

    def falando(self, agora):
        """De 0 a 1: quanto os olhinhos ainda estão 'falando' (some suave no fim)."""
        if not self.fala_desde <= agora < self.fala_ate:
            return 0.0
        return min(1.0, (agora - self.fala_desde) / 0.08, (self.fala_ate - agora) / 0.2)

    def entendendo(self, agora):
        """De 0 a 1 a 0: a piscada lenta depois da olhada (0 fora dela)."""
        t = (agora - self.entendi_desde) / DURACAO_ENTENDI
        if not 0.0 <= t < 1.0:
            return 0.0
        return math.sin(math.pi * t)

    # ---------------- o que desenhar ----------------

    def pose(self, agora):
        """A deformação do corpo e dos olhos neste quadro, somando atividades e eventos."""
        pose = Pose()

        # pop do balão: achata (antecipa), estica e assenta; volume mais ou menos constante
        achata = mola(agora - self.fala_desde) if agora - self.fala_desde < DURACAO_POP else 0.0
        pose.escala_y -= achata
        pose.escala_x += achata * 0.7

        # olhos "falando": abrem e fecham um pouco, num ritmo de sílabas que não é regular demais
        fala = self.falando(agora)
        if fala:
            t = agora - self.fala_desde
            silaba = abs(math.sin(math.pi * SILABAS_POR_SEGUNDO * t + 0.6 * math.sin(math.tau * 1.3 * t)))
            pose.olho_y *= 1.0 - 0.16 * fala * silaba
            pose.olho_x *= 1.0 + 0.04 * fala * silaba

        # entendi: os olhos fecham pela metade e abrem devagar
        pose.olho_y *= 1.0 - 0.55 * self.entendendo(agora)

        # jogo: vidrado, olhos um pouco maiores; mastiga cada pipoca que chega
        jogo = self.nivel("jogo")
        pose.olho_x *= 1.0 + 0.06 * jogo
        pose.olho_y *= 1.0 + 0.10 * jogo - 0.22 * jogo * self.mastigando(agora)

        # IA vilã: os olhos viram os de bravo, um pouco mais finos
        vila = self.nivel("pesquisando")
        if vila:
            pose.forma, pose.peso_forma = "bravo", vila
            pose.olho_y *= 1.0 - 0.18 * vila

        # ouvindo: inclina a cabeça para o lado das ondinhas
        pose.inclinacao += INCLINACAO_OUVINDO * ease_out_cubic(self.nivel("ouvindo"))

        # quem manda no olhar: projeção > IA vilã > leitura > pensando
        olhar = self.olhar(agora)
        if olhar is not None:
            pose.olhar, pose.peso_olhar = olhar
        return pose

    def olhar(self, agora):
        """((gx, gy), peso) de quem manda no olhar agora, ou None."""
        projeta = self.nivel("projetando")
        if projeta:
            return (0.0, -1.0), projeta
        vila = self.nivel("pesquisando")
        if vila:
            return (ida_e_volta(agora, PERIODO_CALCULO) * 1.6 - 0.8, 0.0), vila
        leitura = self.nivel("olhando")
        if leitura:
            return (ida_e_volta(agora, PERIODO_LEITURA) * 1.8 - 0.9, 0.35 * self.linha_leitura(agora) - 0.2), leitura
        pensa = self.nivel("pensando")
        if pensa:
            return (0.75, -0.9), pensa
        return None

    def linha_leitura(self, agora):
        """Altura da linha de leitura, de 0 (topo da tela) a 1 (base); desce lenta e sobe rápida."""
        fase = (agora / (PERIODO_LEITURA * 2.0)) % 1.0
        if fase < 0.8:
            return ease_in_out_sine(fase / 0.8)
        return 1.0 - ease_out_cubic((fase - 0.8) / 0.2)

    def fumaca(self, agora):
        """Cada baforada do cachimbo: (subida 0..1, opacidade 0..1). Sobem, crescem e somem."""
        resultado = []
        for i in range(BAFORADAS):
            fase = (agora / PERIODO_FUMACA + i / BAFORADAS) % 1.0
            resultado.append((ease_out_cubic(fase), math.sin(math.pi * fase) * (1.0 - fase) ** 0.5))
        return resultado

    def pipoca(self, agora):
        """Onde está a pipoca da vez, de 0 (no balde) a 1 (entrou na tela), ou None entre uma e outra."""
        fase = agora % PERIODO_PIPOCA
        return fase / VOO_PIPOCA if fase < VOO_PIPOCA else None

    def mastigando(self, agora):
        """De 0 a 1: os olhos apertam no ritmo da mastigada logo depois que a pipoca entra."""
        t = agora % PERIODO_PIPOCA - VOO_PIPOCA
        if not 0.0 <= t < MASTIGA:
            return 0.0
        return abs(math.sin(math.tau * t / MASTIGA)) * (1.0 - t / MASTIGA)       # duas mastigadas

    def orelha(self):
        """Quanto a orelha já virou para a frente: 0 (de lado, fininha) a 1 (de frente), passando um pouco."""
        return ease_out_back(self.nivel("ouvindo"), 2.2)

    def ondas(self, agora, quantas=3, periodo=1.2):
        """Raio (0..1) e opacidade (0..1) de cada ondinha que sai de quem ouve (radar)."""
        resultado = []
        for i in range(quantas):
            fase = (agora / periodo + i / quantas) % 1.0
            resultado.append((ease_out_cubic(fase), (1.0 - fase) ** 1.5))
        return resultado
