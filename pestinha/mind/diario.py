"""
DIÁRIO - o resumo de cada dia de conversa, para ele lembrar de você nos outros dias (opcional: "Lembrar das
conversas", desligado por padrão).

Quando ele vai dormir, ou na virada do dia, as falas do dia no histórico do chat (mind/historico.py) vão para
o modelo do chat, que escreve um resumo curto do que vocês conversaram: projetos, gostos, decisões, o que
ficou para depois. O resumo passa pelo filtro do que o modelo devolve (ia/validacao.py) e é gravado em
memory/pets/<pet>/diario.jsonl, uma linha por dia. Só neste computador: não vai para a memória compartilhada.

    Diario(caminho)             ler(), tem(data), gravar(data, resumo)
    DiarioController(app)       tick(agora): resume o dia quando ele dorme ou quando o dia vira

Sem "Guardar o histórico do chat", não há o que resumir. Pânico e pausa descartam o resumo a caminho.
"""

import datetime
import json
import threading
import time

from PySide6.QtCore import QObject, Signal

from .. import store
from ..ia import provedores
from ..ia.mente import pedido_diario
from ..ia.validacao import para_gravar
from ..log import log

CONFERE_A_CADA = 60.0       # s entre uma conferência e outra (a virada do dia, o sono)
MIN_FALAS = 2               # um dia com menos que isso não vira diário
MAX_FALAS = 80              # as últimas falas do dia que vão para o resumo
MAX_RESUMO = 900            # caracteres do resumo gravado
MAX_DIAS = 365              # dias guardados no diário


def data_de(segundos):
    """'2026-11-09' do instante `segundos` (relógio de parede, fuso deste computador)."""
    return datetime.date.fromtimestamp(segundos).isoformat()


class Diario:
    """O arquivo do diário: uma linha {"data", "resumo", "falas"} por dia."""

    def __init__(self, caminho):
        """`caminho` é memory/pets/<pet>/diario.jsonl."""
        self.caminho = caminho

    def ler(self):
        """Os dias guardados, do mais antigo para o mais novo."""
        dias = []
        for linha in store.read_lines(self.caminho):
            try:
                item = json.loads(linha)
            except ValueError:
                continue
            if isinstance(item, dict) and isinstance(item.get("data"), str) and isinstance(item.get("resumo"), str):
                dias.append(item)
        return dias

    def apagar(self):
        """Apaga o diário inteiro (o botão Esquecer do chat)."""
        try:
            self.caminho.unlink(missing_ok=True)
        except OSError as erro:
            log(f"[diário] não apagou: {erro}")

    def tem(self, data):
        """Esse dia já foi resumido."""
        return any(d["data"] == data for d in self.ler())

    def gravar(self, data, resumo, falas=0):
        """Guarda o resumo do dia (troca o que houver do mesmo dia). Devolve True se gravou."""
        resumo = para_gravar(resumo, "o diário")[:MAX_RESUMO]
        if not resumo:
            return False
        dias = [d for d in self.ler() if d["data"] != data] + [{"data": data, "resumo": resumo, "falas": int(falas)}]
        dias.sort(key=lambda d: d["data"])
        try:
            store.write_lines(self.caminho, [json.dumps(d, ensure_ascii=False) for d in dias[-MAX_DIAS:]])
        except OSError as erro:
            log(f"[diário] não gravou: {erro}")
            return False
        log(f"[diário] guardei o resumo de {data}")
        return True


def falas_do_dia(entradas, data):
    """As falas do histórico (não as de erro) desse dia, em ordem."""
    return [e for e in entradas if not e.get("erro") and data_de(e.get("t", 0)) == data][-MAX_FALAS:]


class DiarioController(QObject):
    """Quando resumir o dia e quem resume (o modelo do chat, numa thread). Usa os atributos do PestinhaApp."""

    _pronto = Signal(str, object, int, int)     # (data, resumo ou erro, quantas falas, geração)

    def __init__(self, app, diario, relogio=time.time):
        """`diario` é o Diario do pet; `relogio` é o relógio de parede (os testes trocam)."""
        super().__init__()
        self.app = app
        self.diario = diario
        self.relogio = relogio
        self.resumindo = False
        self.geracao = 0
        self._conferido = float("-inf")
        self._dia = data_de(relogio())
        self._dormindo = False
        self._pronto.connect(self._ao_pronto)

    def ligado(self):
        """IA, conversa, histórico do chat e "Lembrar das conversas" ligados."""
        p = self.app.perms
        return bool(p["ia"] and p["conversa"] and p["historico_chat"] and p["memoria_local"])

    def cancelar(self):
        """Pânico ou pausa: o resumo a caminho é descartado."""
        self.geracao += 1
        self.resumindo = False

    def tick(self, agora):
        """No ciclo de pensamento: na virada do dia, resume o dia que passou; ao dormir, resume o de hoje."""
        if agora - self._conferido < CONFERE_A_CADA:
            return
        self._conferido = agora
        hoje = data_de(self.relogio())
        dormiu = bool(getattr(self.app, "asleep", False)) and not self._dormindo
        self._dormindo = bool(getattr(self.app, "asleep", False))
        if not self.ligado() or self.app._congelado() or self.resumindo:
            self._dia = hoje
            return
        if hoje != self._dia:
            ontem, self._dia = self._dia, hoje
            self.resumir(ontem)
        elif dormiu:
            self.resumir(hoje)

    def resumir(self, data):
        """Resume as falas de `data` (numa thread). Devolve False se não há o que resumir ou não dá agora."""
        if self.resumindo or not self.ligado():
            return False
        falas = falas_do_dia(self.app.historico.ultimas(10 ** 6), data)
        if len(falas) < MIN_FALAS:
            return False
        try:
            cliente = self.app.visao.cliente()
        except provedores.ErroIA as erro:
            log(f"[diário] {erro}")
            return False
        self.resumindo = True
        geracao = self.geracao
        pedido = pedido_diario(data, falas, self.app.nome)
        sistema = self.app.visao.sistema

        def trabalho():
            """Roda numa thread: devolve o resumo ou a falha, nunca levanta."""
            try:
                resultado = cliente.responder(sistema, [{"role": "user", "content": pedido}], None, tarefa="diario")
            except provedores.ErroIA as erro:
                resultado = erro
            except Exception as erro:                  # bug inesperado: vira log, não derruba
                resultado = provedores.ErroIA(f"falha inesperada: {type(erro).__name__}: {erro}")
            self._pronto.emit(data, resultado, len(falas), geracao)

        threading.Thread(target=trabalho, name="pestinha-diario", daemon=True).start()
        return True

    def _ao_pronto(self, data, resultado, falas, geracao):
        """O resumo do dia, já na thread do Qt."""
        if geracao != self.geracao:
            return                                      # pânico ou pausa no meio do caminho
        self.resumindo = False
        if isinstance(resultado, Exception):
            log(f"[diário] não resumi {data}: {resultado}")
        elif self.ligado():
            self.diario.gravar(data, resultado, falas)
