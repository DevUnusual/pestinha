"""
HISTÓRICO DO CHAT - o que você pediu (escrito ou falado) e o que ele respondeu, inteiro, para rever no chat
("Guardar o histórico do chat", ligado por padrão).

O balão corta a fala (ia/mente.MAX_COMENTARIO); aqui fica a resposta completa. Cada fala é uma linha de
memory/pets/<pet>/historico_chat.jsonl:
    {"t": 1730900000.0, "quem": "voce" | "pet", "texto": "...", "erro": false, "voz": false}

Política:
    - só neste computador: não vai para a memória compartilhada (não está em PetPaths.todos()) nem para a IA
      (o que a IA lembra da conversa é outra coisa, curta e só na memória: ia/mente.Conversa);
    - "Esquecer", no chat, apaga o arquivo; "Apagar todos os dados" apaga junto com memory/;
    - guarda no máximo MAX_LINHAS falas: as mais velhas saem.
"""

import json
import time

from ..log import log

MAX_LINHAS = 3000           # falas guardadas no arquivo (as mais velhas saem)
MAX_TEXTO = 8000            # caracteres por fala
MOSTRAR = 300               # falas que o chat mostra ao abrir


class HistoricoChat:
    """O arquivo do histórico: acrescenta, lê as últimas e apaga. Falha de disco só vai para o log."""

    def __init__(self, caminho):
        """`caminho` é memory/pets/<pet>/historico_chat.jsonl."""
        self.caminho = caminho
        self._linhas = None         # quantas linhas o arquivo tem (lido na primeira vez que precisa)

    def adicionar(self, quem, texto, erro=False, voz=False, quando=None):
        """Uma fala. `quem` é "voce" ou "pet". Devolve a entrada gravada (ou None se não deu)."""
        texto = str(texto or "").strip()[:MAX_TEXTO]
        if quem not in ("voce", "pet") or not texto:
            return None
        entrada = {"t": time.time() if quando is None else float(quando), "quem": quem, "texto": texto,
                   "erro": bool(erro), "voz": bool(voz)}
        try:
            self.caminho.parent.mkdir(parents=True, exist_ok=True)
            with open(self.caminho, "a", encoding="utf-8") as arquivo:
                arquivo.write(json.dumps(entrada, ensure_ascii=False) + "\n")
        except OSError as falha:
            log(f"[histórico] não consegui gravar: {falha}")
            return None
        if self._linhas is None:
            self._linhas = len(self._ler())
        else:
            self._linhas += 1
        if self._linhas > MAX_LINHAS:
            self._encurtar()
        return entrada

    def ultimas(self, quantas=MOSTRAR):
        """As últimas falas, da mais velha para a mais nova (linhas estragadas ficam de fora)."""
        return self._ler()[-quantas:] if quantas > 0 else []

    def apagar(self):
        """Apaga o histórico inteiro."""
        try:
            self.caminho.unlink()
        except FileNotFoundError:
            pass
        except OSError as falha:
            log(f"[histórico] não consegui apagar: {falha}")
            return False
        self._linhas = 0
        log("[histórico] conversa apagada")
        return True

    def _ler(self):
        try:
            with open(self.caminho, encoding="utf-8") as arquivo:
                linhas = arquivo.readlines()
        except FileNotFoundError:
            return []
        except OSError as falha:
            log(f"[histórico] não consegui ler: {falha}")
            return []
        entradas = []
        for linha in linhas:
            try:
                e = json.loads(linha)
            except ValueError:
                continue
            if (isinstance(e, dict) and e.get("quem") in ("voce", "pet") and isinstance(e.get("texto"), str)
                    and isinstance(e.get("t"), (int, float))):
                entradas.append({"t": float(e["t"]), "quem": e["quem"], "texto": e["texto"][:MAX_TEXTO],
                                 "erro": bool(e.get("erro")), "voz": bool(e.get("voz"))})
        return entradas

    def _encurtar(self):
        """Passou de MAX_LINHAS: fica só com as 80% mais novas (reescreve o arquivo inteiro)."""
        manter = self._ler()[-int(MAX_LINHAS * 0.8):]
        temporario = self.caminho.with_suffix(".tmp")
        try:
            with open(temporario, "w", encoding="utf-8") as arquivo:
                arquivo.writelines(json.dumps(e, ensure_ascii=False) + "\n" for e in manter)
            temporario.replace(self.caminho)
        except OSError as falha:
            log(f"[histórico] não consegui encurtar: {falha}")
            return
        self._linhas = len(manter)
