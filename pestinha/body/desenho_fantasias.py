"""
DESENHO DAS FANTASIAS - o que ele veste conforme o que a mente está fazendo (o tempo vem de animacoes.py).

    pensando     detetive: chapéu de caçador xadrez cai na cabeça, a capa abre atrás e o cachimbo solta fumaça
    pesquisando  IA vilã: a casca vira metal, os olhos ficam vermelhos com brilho e a grade da boca pulsa
    jogo         cinema: óculos 3D de papelão descem nos olhos e um balde de pipoca sobe do canto
    ouvindo      uma orelha aparece do lado e gira para a frente; as ondinhas saem dela
    projetando   olhos de holograma, com linhas passando e a luz subindo para a projeção

Só desenho, com centro do corpo na origem. `desenhar(p, mente, agora, a, frente)` é chamado duas vezes:
atrás do corpo (capa, orelha) e na frente (o resto). As cores da IA vilã e do holograma entram pela
Aparencia (`aparencia_da_mente`), assim os olhos continuam sendo desenhados por desenho_rosto.py.
"""

import math
from dataclasses import replace

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainterPath, QPen, QRadialGradient

from .animacoes import ease_out_back, ease_out_cubic

BODY_W, BODY_H = 120, 90            # o mesmo do desenho_rosto (não importa de lá para não dar ciclo)

TWEED = QColor("#a9824f")
TWEED_ESCURO = QColor("#6e5232")
CACHIMBO = QColor("#4a2e1c")
FUMACA = QColor("#d9dde3")

METAL = QColor("#b9bec8")
METAL_CASCA = QColor("#1b1d23")
METAL_TELA = QColor("#0c0d11")
VERMELHO = QColor("#ff2b2b")
VERMELHO_BRILHO = QColor("#ffd3d3")

PAPELAO = QColor("#f4f1e8")
LENTE_VERMELHA = QColor(255, 48, 64, 120)
LENTE_CIANO = QColor(32, 216, 255, 120)
BALDE = QColor("#d7263d")
PIPOCA = QColor("#fff3cf")
PIPOCA_SOMBRA = QColor("#e9c77b")

HOLO = QColor("#6ff6ff")
HOLO_BRILHO = QColor("#e8ffff")


def _misturar(a, b, k):
    """Cor entre `a` (k=0) e `b` (k=1)."""
    k = max(0.0, min(1.0, k))
    return QColor.fromRgbF(a.redF() + (b.redF() - a.redF()) * k, a.greenF() + (b.greenF() - a.greenF()) * k,
                           a.blueF() + (b.blueF() - a.blueF()) * k, a.alphaF() + (b.alphaF() - a.alphaF()) * k)


def _misturar_matiz(a, b, k):
    """Cor entre `a` e `b` pelo matiz (verde -> amarelo -> vermelho), sem passar pelo marrom do meio."""
    k = max(0.0, min(1.0, k))
    ha, sa, va, _ = a.getHsvF()
    hb, sb, vb, _ = b.getHsvF()
    ha, hb = max(ha, 0.0), max(hb, 0.0)                 # cinza tem matiz -1
    if abs(hb - ha) > 0.5:                              # o caminho mais curto na roda de cores
        hb += 1.0 if hb < ha else -1.0
    return QColor.fromHsvF((ha + (hb - ha) * k) % 1.0, sa + (sb - sa) * k, va + (vb - va) * k)


def _alfa(cor, alfa):
    c = QColor(cor)
    c.setAlphaF(max(0.0, min(1.0, alfa * cor.alphaF())))
    return c


def aparencia_da_mente(a, mente):
    """A aparência do pet com as cores da IA vilã e do holograma misturadas pelo nível de cada um."""
    if mente is None:
        return a
    vila, holo, jogo = mente.nivel("pesquisando"), mente.nivel("projetando"), mente.nivel("jogo")
    if not (vila or holo or jogo > 0.5):
        return a
    olho = _misturar(_misturar_matiz(a.olho, VERMELHO, vila), HOLO, holo)
    brilho = _misturar(_misturar(a.brilho, VERMELHO_BRILHO, vila), HOLO_BRILHO, holo)
    acessorios = tuple(x for x in a.acessorios if not (jogo > 0.5 and x[0] == "oculos"))   # os 3D no lugar
    return replace(a, moldura=_misturar(a.moldura, METAL, vila), casca=_misturar(a.casca, METAL_CASCA, vila),
                   tela=_misturar(a.tela, METAL_TELA, vila), olho=olho, brilho=brilho, acessorios=acessorios)


def desenhar(p, mente, agora, a, frente):
    """As fantasias da vez: `frente=False` antes do corpo (capa, orelha), `frente=True` depois."""
    if mente is None:
        return
    pensa, vila, jogo = mente.nivel("pensando"), mente.nivel("pesquisando"), mente.nivel("jogo")
    ouve, holo = mente.nivel("ouvindo"), mente.nivel("projetando")
    if not frente:
        if pensa:
            _capa(p, pensa)
        if ouve:
            _orelha(p, ouve, mente.orelha(), agora, a)
        return
    if vila:
        _vila(p, vila, agora)
    if holo:
        _holograma(p, holo, agora)
    if jogo:
        _oculos_3d(p, jogo)
        _pipoca(p, jogo, mente.pipoca(agora), agora)
    if pensa:
        _chapeu(p, pensa)
        _cachimbo(p, pensa, mente.fumaca(agora))
    if ouve:
        _ondas_da_orelha(p, ouve, mente.orelha(), mente.ondas(agora), a.olho)


# ---------------- detetive ----------------

def _xadrez(p, area, cor, passo=7.0):
    """Linhas do tecido xadrez dentro do clip atual."""
    p.setPen(QPen(cor, 1.2))
    x = area.left()
    while x < area.right():
        p.drawLine(QPointF(x, area.top()), QPointF(x, area.bottom()))
        x += passo
    y = area.top()
    while y < area.bottom():
        p.drawLine(QPointF(area.left(), y), QPointF(area.right(), y))
        y += passo


def _capa(p, nivel):
    """A capa curta atrás do corpo: abre dos ombros para os lados, como quem joga a capa para trás."""
    abre = ease_out_back(nivel, 1.4)
    p.save()
    p.setOpacity(min(1.0, nivel * 2.5))
    top = -BODY_H / 2 + 6
    for lado in (-1, 1):
        ombro = lado * (BODY_W / 2 - 8)
        ponta = lado * (BODY_W / 2 + 18 * abre)
        capa = QPainterPath()
        capa.moveTo(ombro, top)
        capa.cubicTo(ombro + lado * 14 * abre, top + 6, ponta, top + 26, ponta - lado * 2, BODY_H / 2 - 4)
        capa.lineTo(lado * (BODY_W / 2 - 14), BODY_H / 2 - 8)
        capa.closeSubpath()
        p.setPen(QPen(TWEED_ESCURO.darker(130), 1.5))
        p.setBrush(TWEED_ESCURO)
        p.drawPath(capa)
        p.save()
        p.setClipPath(capa)
        _xadrez(p, capa.boundingRect(), _alfa(TWEED.darker(115), 0.6), 8.0)
        p.restore()
    p.restore()


def _chapeu(p, nivel):
    """Chapéu de caçador xadrez: cai de cima, quica e assenta um pouco torto."""
    cai = ease_out_back(nivel, 2.0)
    p.save()
    p.setOpacity(min(1.0, nivel * 3.0))
    base = -BODY_H / 2 + 3
    p.translate(0, -70 * (1.0 - cai))
    p.rotate(-7 * cai)
    copa = QPainterPath()
    copa.moveTo(-46, base)
    copa.cubicTo(-46, base - 30, -20, base - 40, 0, base - 40)
    copa.cubicTo(20, base - 40, 46, base - 30, 46, base)
    copa.closeSubpath()
    p.setPen(QPen(TWEED_ESCURO, 2))
    p.setBrush(TWEED)
    p.drawPath(copa)
    p.save()
    p.setClipPath(copa)
    _xadrez(p, copa.boundingRect(), _alfa(TWEED_ESCURO, 0.55))
    p.setPen(QPen(_alfa(TWEED_ESCURO, 0.8), 1.5))
    p.drawLine(QPointF(0, base - 40), QPointF(0, base))              # costura do meio
    p.restore()
    # aba da frente, e as abas das orelhas amarradas em cima com um lacinho
    p.setPen(QPen(TWEED_ESCURO.darker(120), 1.5))
    p.setBrush(TWEED_ESCURO)
    p.drawRoundedRect(QRectF(-38, base - 4, 76, 9), 4.5, 4.5)
    p.setBrush(TWEED.darker(110))
    for lado in (-1, 1):
        p.drawEllipse(QRectF(lado * 9 - 7, base - 46, 14, 8))
    p.setBrush(TWEED_ESCURO)
    p.drawEllipse(QPointF(0, base - 42), 3, 3)
    p.restore()


def _cachimbo(p, nivel, fumaca):
    """Cachimbo no canto da 'boca', entrando de lado; a fumaça sai do fornilho em baforadas."""
    entra = ease_out_cubic(nivel)
    p.save()
    p.setOpacity(min(1.0, nivel * 2.5))
    p.translate(26 * (1.0 - entra), 0)
    p.setPen(QPen(CACHIMBO, 4, Qt.SolidLine, Qt.RoundCap))
    haste = QPainterPath()
    haste.moveTo(6, 28)
    haste.cubicTo(18, 31, 26, 32, 34, 28)
    p.setBrush(Qt.NoBrush)
    p.drawPath(haste)
    fornilho = QPainterPath()
    fornilho.moveTo(32, 16)
    fornilho.lineTo(46, 16)
    fornilho.cubicTo(46, 28, 42, 32, 39, 32)
    fornilho.cubicTo(35, 32, 32, 28, 32, 16)
    p.setPen(QPen(CACHIMBO.darker(130), 1.2))
    p.setBrush(CACHIMBO)
    p.drawPath(fornilho)
    p.setPen(QPen(QColor("#ff9b42"), 2, Qt.SolidLine, Qt.RoundCap))   # brasa
    p.drawLine(QPointF(35, 16.5), QPointF(43, 16.5))
    p.setPen(Qt.NoPen)
    for subida, alfa in fumaca:
        x = 40 + 14 * subida + 4 * math.sin(subida * math.tau * 1.2)
        y = 12 - 52 * subida
        p.setBrush(_alfa(FUMACA, 0.75 * alfa * nivel))
        r = 3 + 7 * subida
        p.drawEllipse(QPointF(x, y), r, r * 0.8)
    p.restore()


# ---------------- IA vilã ----------------

def _vila(p, nivel, agora):
    """Brilho vermelho nos olhos, placas do rosto, grade da boca pulsando e a varredura vermelha."""
    p.save()
    for lado in (-1, 1):                               # o brilho dos olhos vaza para a tela
        brilho = QRadialGradient(QPointF(lado * 24, 0), 30)
        brilho.setColorAt(0.0, _alfa(VERMELHO, 0.35 * nivel))
        brilho.setColorAt(1.0, _alfa(VERMELHO, 0.0))
        p.setPen(Qt.NoPen)
        p.setBrush(brilho)
        p.drawEllipse(QPointF(lado * 24, 0), 30, 30)
    p.setPen(QPen(_alfa(METAL, 0.8 * nivel), 1.4))
    for lado in (-1, 1):                               # placas do rosto
        p.drawLine(QPointF(lado * 44, -30), QPointF(lado * 40, 30))
        p.drawLine(QPointF(lado * 40, 30), QPointF(lado * 14, 33))
    pulso = 0.55 + 0.45 * math.sin(agora * math.tau * 3.0)
    for i in range(7):                                 # grade da boca, acendendo em onda
        x = -15 + i * 5
        onda = 0.5 + 0.5 * math.sin(agora * math.tau * 2.0 - i * 0.7)
        p.setPen(QPen(_alfa(VERMELHO, nivel * (0.35 + 0.65 * onda * pulso)), 2.2, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(x, 24), QPointF(x, 30))
    y = -30 + 60 * ((agora / 0.8) % 1.0)               # varredura rápida, de cima para baixo
    p.setPen(QPen(_alfa(VERMELHO, 0.45 * nivel), 1.0))
    p.drawLine(QPointF(-48, y), QPointF(48, y))
    p.restore()


# ---------------- cinema ----------------

def _oculos_3d(p, nivel):
    """Óculos 3D de papelão: descem de cima e encaixam nos olhos, lente vermelha e ciano."""
    desce = ease_out_back(nivel, 1.8)
    p.save()
    p.setOpacity(min(1.0, nivel * 2.5))
    p.translate(0, -55 * (1.0 - desce))
    armacao = QPainterPath()
    armacao.addRoundedRect(QRectF(-54, -22, 108, 42), 8, 8)
    lentes = []
    for lado in (-1, 1):
        lente = QPainterPath()
        lente.addRoundedRect(QRectF(lado * 24 - 19, -16, 38, 30), 7, 7)
        lentes.append((lado, lente))
        armacao = armacao.subtracted(lente)
    for lado, lente in lentes:
        p.setPen(Qt.NoPen)
        p.setBrush(LENTE_VERMELHA if lado < 0 else LENTE_CIANO)
        p.drawPath(lente)
    p.setPen(QPen(QColor("#2b2b2b"), 1.5))
    p.setBrush(PAPELAO)
    p.drawPath(armacao)
    p.setPen(QPen(PAPELAO.darker(115), 3, Qt.SolidLine, Qt.RoundCap))
    for lado in (-1, 1):                               # hastes saindo para os lados
        p.drawLine(QPointF(lado * 54, -14), QPointF(lado * 64, -12))
    p.setPen(QPen(QColor("#2b2b2b"), 1))
    p.setBrush(Qt.NoBrush)
    p.drawLine(QPointF(-6, -2), QPointF(6, -2))
    p.restore()


def _pipoquinha(p, x, y, r, giro=0.0):
    """Uma pipoca: três bolinhas fofas com um miolo dourado."""
    p.save()
    p.translate(x, y)
    p.rotate(giro)
    p.setPen(QPen(PIPOCA_SOMBRA, 0.8))
    p.setBrush(PIPOCA)
    for dx, dy in ((-0.5, 0.2), (0.5, 0.2), (0.0, -0.45)):
        p.drawEllipse(QPointF(dx * r, dy * r), r * 0.62, r * 0.62)
    p.setPen(Qt.NoPen)
    p.setBrush(PIPOCA_SOMBRA)
    p.drawEllipse(QPointF(0, r * 0.35), r * 0.25, r * 0.2)
    p.restore()


def _pipoca(p, nivel, voo, agora):
    """O balde listrado sobe do canto; de tempos em tempos uma pipoca pula dele para dentro da tela."""
    sobe = ease_out_back(nivel, 1.6)
    p.save()
    p.setOpacity(min(1.0, nivel * 2.5))
    p.translate(0, 40 * (1.0 - sobe))
    balde = QPainterPath()
    balde.moveTo(-58, 14)
    balde.lineTo(-30, 14)
    balde.lineTo(-34, 44)
    balde.lineTo(-54, 44)
    balde.closeSubpath()
    p.setPen(Qt.NoPen)
    for i, x in enumerate((-58, -48, -38)):            # listras vermelhas e brancas
        p.setBrush(BALDE if i % 2 == 0 else QColor("#ffffff"))
        p.save()
        p.setClipPath(balde)
        p.drawRect(QRectF(x, 14, 10, 31))
        p.restore()
    p.setPen(QPen(BALDE.darker(140), 1.2))
    p.setBrush(Qt.NoBrush)
    p.drawPath(balde)
    for i, (dx, dy) in enumerate(((-54, 12), (-47, 9), (-40, 11), (-34, 12), (-50, 6), (-42, 5))):
        _pipoquinha(p, dx, dy + math.sin(agora * 2 + i) * 0.4, 4.5, i * 40)
    if voo is not None:                                # do balde até a "boca", num arco, girando
        x = -44 + 44 * voo
        y = 4 + 16 * voo - 46 * voo * (1.0 - voo)
        _pipoquinha(p, x, y, 4.0 * (1.0 - 0.3 * voo), voo * 360)
    p.restore()


# ---------------- orelha ----------------

ORELHA = QPointF(BODY_W / 2 + 6, -6)


def _orelha(p, nivel, virada, agora, a):
    """A orelha do lado direito, atrás do corpo: começa de lado (fininha) e gira para a frente."""
    largura = max(0.08, virada)
    tremida = 4 * math.sin(agora * math.tau * 0.7) * nivel     # uma mexidinha de quem presta atenção
    p.save()
    p.setOpacity(min(1.0, nivel * 3.0))
    p.translate(ORELHA)
    p.rotate(tremida)
    p.scale(largura, 1.0)
    p.setPen(QPen(a.moldura.darker(110), 3))
    p.setBrush(a.casca)
    p.drawEllipse(QRectF(-4, -19, 24, 36))                       # concha
    p.setPen(Qt.NoPen)
    p.setBrush(a.tela.lighter(160))
    p.drawEllipse(QRectF(2, -12, 13, 23))                        # dentro da orelha
    p.setPen(QPen(a.moldura, 2.2, Qt.SolidLine, Qt.RoundCap))
    p.setBrush(Qt.NoBrush)
    p.drawArc(QRectF(4, -8, 10, 14), 60 * 16, 220 * 16)          # a dobrinha
    p.restore()


def _ondas_da_orelha(p, nivel, virada, ondas, cor):
    """As ondinhas de ouvir chegando na orelha (só depois que ela virou para a frente)."""
    if virada < 0.6:
        return
    p.save()
    p.setBrush(Qt.NoBrush)
    centro = QPointF(ORELHA.x() + 8, ORELHA.y())
    for raio, alfa in ondas:
        r = 17.0 - 9.0 * raio                                     # vêm de fora para dentro: é o som chegando
        p.setPen(QPen(_alfa(cor, alfa * nivel * min(1.0, (virada - 0.6) / 0.4)), 2.0, Qt.SolidLine, Qt.RoundCap))
        p.drawArc(QRectF(centro.x() - r, centro.y() - r, 2 * r, 2 * r), -40 * 16, 80 * 16)
    p.restore()


# ---------------- holograma ----------------

def _holograma(p, nivel, agora):
    """Linhas de holograma passando nos olhos e a luz subindo dos olhos para a projeção."""
    p.save()
    tremula = 0.85 + 0.15 * math.sin(agora * 37.0) * math.sin(agora * 11.0)
    for lado in (-1, 1):
        luz = QLinearGradient(0, -2, 0, -110)
        luz.setColorAt(0.0, _alfa(HOLO, 0.45 * nivel * tremula))
        luz.setColorAt(1.0, _alfa(HOLO, 0.0))
        cone = QPainterPath()                          # de cada olho, abrindo até a projeção lá em cima
        cone.moveTo(lado * 16, -8)                     # lado de dentro, embaixo
        cone.lineTo(lado * 32, -8)
        cone.lineTo(lado * 48, -110)
        cone.lineTo(lado * 12, -110)
        cone.closeSubpath()
        p.setPen(Qt.NoPen)
        p.setBrush(luz)
        p.drawPath(cone)
    tela = QPainterPath()
    tela.addRoundedRect(QRectF(-BODY_W / 2 + 11, -BODY_H / 2 + 11, BODY_W - 22, BODY_H - 22), 12, 12)
    p.setClipPath(tela)
    p.setPen(QPen(_alfa(HOLO_BRILHO, 0.35 * nivel), 1.0))
    desloca = (agora * 18.0) % 4.0
    y = -BODY_H / 2 + 11 + desloca
    while y < BODY_H / 2 - 11:
        p.drawLine(QPointF(-BODY_W / 2 + 11, y), QPointF(BODY_W / 2 - 11, y))
        y += 4.0
    p.restore()
