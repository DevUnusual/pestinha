"""
Configuração comum dos testes (pasta tests/).

- Qt sem janela: os testes rodam em qualquer máquina, sem abrir nada na tela.
- Isolamento: apps e janelas criados num teste não continuam rodando nos seguintes.
- Sem rede: a tela de Configurações pergunta ao Ollama quais modelos ele tem; nos testes, ele "não tem
  nenhum" (o teste que precisa de uma lista troca isso).
- QtMultimedia: os testes valem com ou sem o PySide6-Addons (a falta dele é testada em test_multimidia.py).
"""
import gc
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(autouse=True)
def _ollama_sem_rede(monkeypatch):
    from pestinha.ia import provedores
    monkeypatch.setattr(provedores, "modelos_ollama", lambda endereco, tempo=3.0: [])


@pytest.fixture(autouse=True)
def _multimidia_presente(monkeypatch):
    # Os testes de voz, chamado e música usam microfone e player falsos: valem com ou sem o PySide6-Addons.
    # A falta do módulo é testada à parte (tests/test_multimidia.py).
    from pestinha import multimidia
    monkeypatch.setattr(multimidia, "_disponivel", True)


@pytest.fixture(autouse=True)
def _uso_sem_arquivo(monkeypatch):
    # O app grava o uso da IA na pasta de dados (ia/uso.py); cada teste começa sem arquivo escolhido, para
    # um teste não escrever na pasta temporária de outro.
    from pestinha.ia import uso
    monkeypatch.setattr(uso, "_arquivo", None)


@pytest.fixture(autouse=True)
def _encerrar_apps_e_janelas():
    from PySide6.QtWidgets import QApplication
    qt = QApplication.instance()
    antes = set(qt.topLevelWidgets()) if qt else set()
    yield
    from PySide6.QtCore import QTimer
    from pestinha.app import PestinhaApp
    for obj in gc.get_objects():
        if isinstance(obj, PestinhaApp):
            for timer in obj.findChildren(QTimer):
                timer.stop()
    qt = QApplication.instance()
    if qt:
        for widget in set(qt.topLevelWidgets()) - antes:
            for timer in widget.findChildren(QTimer):
                timer.stop()
            widget.close()
