"""
MULTIMÍDIA - o QtMultimedia é opcional.

Ele vem no PySide6-Addons, que não faz parte do PySide6-Essentials. O microfone da voz e do chamado
(QAudioSource) e o player da música (QMediaPlayer) dependem dele. Sem o módulo, o pet abre normalmente, e
voz, chamado pelo nome e música ficam desligados, com um aviso. Ninguém importa o QtMultimedia no
carregamento: quem precisa dele chama `modulo()` na hora de usar.
"""

import importlib

from .log import log

NOME = "PySide6.QtMultimedia"
AVISO = ("falta o PySide6-Addons (pip install PySide6-Addons): voz, chamado pelo nome e música ficam "
         "desligados")

_disponivel = None      # None: ainda não conferiu


def disponivel():
    """True se o QtMultimedia pode ser importado (confere uma vez e guarda)."""
    global _disponivel
    if _disponivel is None:
        try:
            importlib.import_module(NOME)
            _disponivel = True
        except ImportError:
            _disponivel = False
            log(f"[multimídia] {AVISO}")
    return _disponivel


def modulo():
    """O módulo PySide6.QtMultimedia (só chame depois de conferir `disponivel()`)."""
    return importlib.import_module(NOME)


def esquecer():
    """Esquece a conferência (os testes simulam a falta do módulo)."""
    global _disponivel
    _disponivel = None
