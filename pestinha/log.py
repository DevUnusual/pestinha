"""
LOG - um lugar só para mensagens do app: terminal e arquivo em memory/logs/.

O arquivo é aparado quando passa de 1 MB (fica com a metade mais recente).
Se o arquivo não puder ser escrito, a mensagem vai só para o terminal.

As últimas linhas também ficam na memória (`recentes`): é assim que o pet lê o próprio registro no chat e
consegue contar o que aconteceu ("a música cortou em 1:32 e eu recomecei"). Linhas de depuração do modo
teste (homeostase, aprendizado...) e os episódios de travessura ficam de fora: são ruído para ele.
"""

import collections
import datetime
import os
import re
import sys
import traceback
from pathlib import Path

MAX_BYTES = 1_000_000
MAX_RECENTES = 200
_file = None
_recentes = collections.deque(maxlen=MAX_RECENTES)      # (quando, texto)
_RUIDO = re.compile(r"^\[(?:homeostase|condicionamento|aprendizado|cutucada|assets|pânico|uso)\]|^\[memória\] \w+\|")


def setup(path):
    """Escolhe o arquivo do log (criado sob demanda)."""
    global _file
    _file = Path(path)


def desligar_arquivo():
    """Para de gravar em arquivo (usado ao apagar os dados: nada pode recriar a pasta)."""
    global _file
    _file = None


def _trim():
    """Corta o início do log quando ele passa do limite, para não crescer sem fim."""
    try:
        if _file.exists() and _file.stat().st_size > MAX_BYTES:
            lines = _file.read_text(encoding="utf-8", errors="replace").splitlines()
            _file.write_text("\n".join(lines[len(lines) // 2:]) + "\n", encoding="utf-8")
    except OSError:
        pass


def log(*parts):
    """Escreve uma mensagem no terminal e no arquivo do log (uma linha por chamada)."""
    text = " ".join(str(p) for p in parts)
    _recentes.append((datetime.datetime.now(), text))
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode("ascii", "replace").decode("ascii"))
    _gravar(text)


def _gravar(text):
    """Acrescenta a mensagem ao arquivo do log, se houver um."""
    if _file is None:
        return
    try:
        _file.parent.mkdir(parents=True, exist_ok=True)
        stamp = datetime.datetime.now().isoformat(timespec="seconds")
        with open(_file, "a", encoding="utf-8") as f:
            f.write(f"{stamp} {text}{os.linesep}")
        _trim()
    except OSError:
        pass


def recentes(minutos=30, maximo=10, agora=None):
    """
    As últimas linhas do log (no máximo `maximo`, dos últimos `minutos`), sem o ruído de depuração, como
    texto para o pet ler: '01:21 música: cortou ... em 1:32'. Sem colchetes (o bloco que leva isso já usa).
    """
    agora = agora or datetime.datetime.now()
    desde = agora - datetime.timedelta(minutes=minutos)
    linhas = []
    for quando, texto in _recentes:
        if quando < desde or _RUIDO.match(texto):
            continue
        texto = re.sub(r"^\[([^\]]+)\]\s*", r"\1: ", texto).replace("[", "(").replace("]", ")")
        linhas.append(f"{quando:%H:%M} {texto}")
    return linhas[-maximo:]
def capturar_erros():
    """Grava no log os erros não tratados: o executável não tem terminal onde eles apareceriam."""
    anterior = sys.excepthook
    if getattr(anterior, "_do_pestinha", False):
        return

    def gancho(tipo, valor, rastro):
        """Registra o erro e deixa o tratamento anterior seguir normalmente."""
        _gravar("[erro] " + "".join(traceback.format_exception(tipo, valor, rastro)).rstrip())
        anterior(tipo, valor, rastro)

    gancho._do_pestinha = True
    sys.excepthook = gancho
