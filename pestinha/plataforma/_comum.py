"""Partes que os três sistemas compartilham: rodar comandos do sistema e o atalho global via pynput."""

import subprocess

from ..log import log


def rodar(comando, tempo=1.0):
    """Saída do comando (texto) ou None se ele não existe, falhou ou demorou demais."""
    try:
        resultado = subprocess.run(comando, capture_output=True, text=True, timeout=tempo, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    return resultado.stdout if resultado.returncode == 0 else None


def atalho_pynput(callback, tecla="b", nome="pânico"):
    """Ctrl + Alt + Shift + `tecla` em qualquer lugar do sistema. Precisa de pynput instalado."""
    try:
        from pynput import keyboard
    except Exception:
        log(f"[{nome}] pynput não está instalado: o atalho global fica desligado")
        return False
    try:
        listener = keyboard.GlobalHotKeys({f"<ctrl>+<alt>+<shift>+{tecla}": callback})
        listener.daemon = True
        listener.start()
    except Exception as error:
        log(f"[{nome}] não deu para registrar o atalho: {error}")
        return False
    return True
