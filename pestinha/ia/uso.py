"""
USO - o registro de cada chamada ao modelo, sem conteúdo: tarefa, provedor, modelo, tokens, tempo e
motivo de parada.

Sem Qt. Os clientes (provedores.py, pesquisa.py) chamam `registrar` depois de cada resposta. Cada chamada
vira uma linha "[uso] ..." no log e uma linha em memory/logs/uso_ia.jsonl (o app escolhe o arquivo com
`configurar`; sem arquivo, só o log). Nunca entra o print, o pedido nem a resposta: só os números, para
ver custo, latência e cortes. O arquivo guarda as últimas MAX_LINHAS chamadas.
"""

import datetime
import json
import threading
from dataclasses import asdict, dataclass

from .. import store
from ..log import log

MAX_LINHAS = 5000
APARAR_A_CADA = 200         # chamadas entre uma conferência do tamanho do arquivo e outra

_arquivo = None
_trava = threading.Lock()
_desde_aparar = 0


@dataclass
class Uso:
    """Uma chamada ao modelo, só os números."""
    tarefa: str
    provedor: str
    modelo: str
    entrada: int = 0            # tokens do pedido (o que o servidor contou)
    saida: int = 0              # tokens da resposta
    ms: int = 0
    motivo: str = ""            # por que parou: end_turn/stop, max_tokens/length (cortada), refusal...
    corte_entrada: bool = False     # o servidor cortou o pedido (Ollama com janela pequena)


def configurar(arquivo):
    """Onde gravar o uso (memory/logs/uso_ia.jsonl); None: só no log (ao apagar os dados, por exemplo)."""
    global _arquivo
    _arquivo = arquivo


def registrar(uso):
    """Uma linha no log e outra no arquivo (se houver). Nunca levanta: uso é registro, não pode derrubar."""
    global _desde_aparar
    avisos = (" CORTADA" if uso.motivo in ("max_tokens", "length") else "") + (
        " ENTRADA CORTADA" if uso.corte_entrada else "")
    log(f"[uso] {uso.tarefa} {uso.provedor}:{uso.modelo} {uso.entrada}+{uso.saida} tokens {uso.ms} ms "
        f"{uso.motivo or '?'}{avisos}")
    arquivo = _arquivo
    if arquivo is None:
        return
    linha = json.dumps(dict(asdict(uso), quando=datetime.datetime.now().isoformat(timespec="seconds")),
                       ensure_ascii=False)
    try:
        with _trava:
            store.append_line(arquivo, linha)
            _desde_aparar += 1
            if _desde_aparar >= APARAR_A_CADA:
                _desde_aparar = 0
                linhas = store.read_lines(arquivo)
                if len(linhas) > MAX_LINHAS:
                    store.write_lines(arquivo, linhas[-MAX_LINHAS:])
    except OSError as erro:
        log(f"[uso] não gravei o uso: {erro}")


def ler(arquivo):
    """As chamadas gravadas (dicionários), da mais antiga para a mais nova; linha estragada é pulada."""
    chamadas = []
    for linha in store.read_lines(arquivo):
        try:
            dados = json.loads(linha)
        except ValueError:
            continue
        if isinstance(dados, dict):
            chamadas.append(dados)
    return chamadas
