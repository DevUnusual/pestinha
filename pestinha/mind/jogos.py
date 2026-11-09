"""
JOGOS - o que ele sabe de cada jogo que você joga e até onde você chegou (com "Estudar os jogos").

Um arquivo só, memory/pets/<pet>/jogos.json, com um item por jogo (pela chave do nome, ia/jogo_info.chave):
    nome, gênero, premissa (sem spoiler), gameplay, dicas  -> o estudo, feito uma vez (mind/jogo_ctl.py)
    historia                                                -> a história inteira, em trechos na ordem
    trecho                                                  -> até que trecho você já chegou (só sobe)
    onde                                                    -> os últimos lugares em que ele te viu
                                                               (capítulo, área, missão), com a hora

O que vai para o modelo nunca passa do `trecho`: a história adiante fica guardada, mas só sai se você
pedir spoiler no chat. Com a memória compartilhada, o arquivo vai junto (o progresso é o mesmo em todos os
computadores). Nunca o print nem o título da janela. Sem Qt: só arquivos.
"""

import json
import time

from ..ia.jogo_info import chave as chave_do_nome
from ..log import log
from .lembrancas import quando

MAX_JOGOS = 60              # jogos guardados: os vistos há mais tempo saem
MAX_ONDE = 6                # lugares lembrados por jogo
MAX_DICAS_OLHADA = 4        # dicas e mecânicas que vão em cada olhada (o pedido fica curto)
REGRAVA_VISTO = 300.0       # s: no mesmo lugar, só regrava "quando foi visto" de tempos em tempos


def _limpo(item):
    """Um item do arquivo com os campos certos (o que estiver ruim vira vazio)."""
    if not isinstance(item, dict) or not isinstance(item.get("nome"), str):
        return None
    saida = {"nome": item["nome"]}
    for campo in ("genero", "premissa", "fonte"):
        saida[campo] = item.get(campo) if isinstance(item.get(campo), str) else ""
    for campo in ("gameplay", "dicas", "historia"):
        lista = item.get(campo)
        saida[campo] = [t for t in lista if isinstance(t, str)] if isinstance(lista, list) else []
    trecho = item.get("trecho")
    saida["trecho"] = (max(0, min(int(trecho), len(saida["historia"])))
                       if isinstance(trecho, (int, float)) and not isinstance(trecho, bool) else 0)
    onde = item.get("onde")
    saida["onde"] = [o for o in onde if isinstance(o, dict) and isinstance(o.get("texto"), str)
                     and isinstance(o.get("em"), (int, float))][-MAX_ONDE:] if isinstance(onde, list) else []
    for campo in ("estudado_em", "visto_em"):
        valor = item.get(campo)
        saida[campo] = valor if isinstance(valor, (int, float)) and not isinstance(valor, bool) else 0
    saida["estudado"] = item.get("estudado") is True
    return saida


class Jogos:
    """O arquivo de jogos de um pet."""

    def __init__(self, caminho):
        """`caminho` é memory/pets/<pet>/jogos.json."""
        self.caminho = caminho

    # ---------------- arquivo ----------------

    def todos(self):
        """{chave: item}; arquivo ruim ou ausente vira {}."""
        try:
            dados = json.loads(self.caminho.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, ValueError):
            return {}
        if not isinstance(dados, dict):
            return {}
        saida = {}
        for chave, item in dados.items():
            limpo = _limpo(item)
            if isinstance(chave, str) and limpo is not None:
                saida[chave] = limpo
        return saida

    def _gravar(self, jogos):
        """Grava (os vistos há mais tempo saem). Devolve True se gravou."""
        if len(jogos) > MAX_JOGOS:
            fica = sorted(jogos, key=lambda k: jogos[k]["visto_em"])[-MAX_JOGOS:]
            jogos = {k: jogos[k] for k in fica}
        try:
            self.caminho.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.caminho.with_name(self.caminho.name + ".tmp")
            tmp.write_text(json.dumps(jogos, ensure_ascii=False, indent=1), encoding="utf-8")
            tmp.replace(self.caminho)
        except OSError as erro:
            log(f"[jogos] não gravou: {erro}")
            return False
        return True

    def get(self, chave):
        """O item do jogo, ou None."""
        return self.todos().get(chave)

    def estudado(self, chave):
        """Ele já leu sobre esse jogo (mesmo que não tenha achado nada)."""
        item = self.get(chave)
        return item is not None and item["estudado"]

    # ---------------- escrever ----------------

    def guardar_estudo(self, chave, estudo, fonte="", agora=None):
        """Grava o que ele aprendeu do jogo (mantém o progresso que já havia). `estudo` vem de ler_estudo;
        None marca que ele procurou e não achou (para não procurar de novo toda hora)."""
        agora = time.time() if agora is None else agora
        jogos = self.todos()
        antes = jogos.get(chave) or _limpo({"nome": (estudo or {}).get("nome") or chave})
        item = dict(antes, estudado=True, estudado_em=round(agora), visto_em=round(agora), fonte=fonte)
        if estudo:
            item.update({k: estudo[k] for k in ("nome", "genero", "premissa", "gameplay", "dicas", "historia")})
            item["trecho"] = min(item["trecho"], len(item["historia"]))
        jogos[chave] = item
        ok = self._gravar(jogos)
        if ok and estudo:
            log(f"[jogos] estudei {item['nome']} ({len(item['historia'])} trechos de história)")
        return ok

    def anotar_onde(self, chave, nome, onde, agora=None):
        """Ele te viu em `onde` (capítulo, área, missão). Só grava se mudou. Devolve True se é novidade."""
        onde = " ".join((onde or "").split())[:120]
        if not onde:
            return False
        agora = time.time() if agora is None else agora
        jogos = self.todos()
        item = jogos.get(chave) or _limpo({"nome": nome})
        novo = not item["onde"] or item["onde"][-1]["texto"].lower() != onde.lower()
        if not novo and agora - item["visto_em"] < REGRAVA_VISTO:
            return False                                # o mesmo lugar: não regrava a cada olhada
        item["visto_em"] = round(agora)
        if novo:
            item["onde"] = (item["onde"] + [{"em": round(agora), "texto": onde}])[-MAX_ONDE:]
        jogos[chave] = item
        self._gravar(jogos)
        return novo

    def avancar(self, chave, trecho):
        """Você chegou ao `trecho` da história (só sobe: rever um lugar antigo não desfaz o progresso)."""
        jogos = self.todos()
        item = jogos.get(chave)
        if item is None or not (0 < trecho <= len(item["historia"])) or trecho <= item["trecho"]:
            return False
        item["trecho"] = trecho
        jogos[chave] = item
        if self._gravar(jogos):
            log(f"[jogos] {item['nome']}: chegou ao trecho {trecho} de {len(item['historia'])}")
            return True
        return False

    # ---------------- ler para o modelo ----------------

    @staticmethod
    def _historia(item, spoiler=False):
        """A história até onde você chegou (ou inteira, com spoiler), em texto."""
        historia = item["historia"]
        if not historia:
            return ""
        if spoiler:
            return ("A história inteira (ela PEDIU spoiler, pode contar): "
                    + " | ".join(f"{i}. {t}" for i, t in enumerate(historia, 1)) + ".")
        if not item["trecho"]:
            return ("Você sabe a história, mas ainda não sabe até onde ela chegou: não conte nada além da "
                    "premissa.")
        feito = historia[:item["trecho"]]
        return (f"A história até onde ela chegou (trecho {item['trecho']} de {len(historia)}; o que vem depois "
                "você não conta sem ela pedir): " + " | ".join(feito) + ".")

    def contexto_olhada(self, chave, agora=None):
        """Para a olhada em jogo: o que ele sabe do jogo, sem passar de onde você está. '' se nada."""
        item = self.get(chave)
        if item is None:
            return ""
        agora = time.time() if agora is None else agora
        partes = [f"Jogo: {item['nome']}" + (f" ({item['genero']})" if item["genero"] else "") + "."]
        if item["premissa"]:
            partes.append(f"Premissa: {item['premissa']}")
        if item["gameplay"]:
            partes.append("Mecânicas: " + "; ".join(item["gameplay"][:MAX_DICAS_OLHADA]) + ".")
        if item["dicas"]:
            partes.append("Dicas que você conhece: " + "; ".join(item["dicas"][:MAX_DICAS_OLHADA]) + ".")
        historia = self._historia(item)
        if historia:
            partes.append(historia)
        if item["onde"]:
            ultimo = item["onde"][-1]
            partes.append(f"Da última vez ela estava em: {ultimo['texto']} ({quando(agora - ultimo['em'])}).")
        return " ".join(partes)

    def sobre(self, texto, jogos=None):
        """A chave do jogo de que a sua mensagem fala (o nome aparece nela), ou None."""
        alvo = f" {chave_do_nome(texto)} "
        jogos = self.todos() if jogos is None else jogos
        for chave in sorted(jogos, key=len, reverse=True):          # 'dark souls 3' antes de 'dark souls'
            if chave and f" {chave} " in alvo:
                return chave
        return None

    def contexto_chat(self, texto, atual=None, spoiler=False, agora=None):
        """Para o chat: o jogo de agora (ou o que você citou), até onde você chegou; tudo, se pediu spoiler."""
        agora = time.time() if agora is None else agora
        jogos = self.todos()
        if not jogos:
            return ""
        chave = self.sobre(texto, jogos) or (atual if atual in jogos else None)
        partes = []
        recentes = sorted(jogos.values(), key=lambda i: i["visto_em"], reverse=True)[:4]
        partes.append("Jogos que você viu ela jogar: "
                      + " | ".join(f"«{i['nome']}» ({quando(agora - i['visto_em'])})" for i in recentes) + ".")
        if chave:
            item = jogos[chave]
            partes.append(f"Sobre {item['nome']}" + (f" ({item['genero']})" if item["genero"] else "") + ":")
            if item["premissa"]:
                partes.append(f"Premissa: {item['premissa']}")
            if item["gameplay"]:
                partes.append("Mecânicas: " + "; ".join(item["gameplay"]) + ".")
            if item["dicas"]:
                partes.append("Dicas: " + "; ".join(item["dicas"]) + ".")
            historia = self._historia(item, spoiler)
            if historia:
                partes.append(historia)
            if item["onde"]:
                partes.append("Onde você a viu: " + " | ".join(
                    f"{o['texto']} ({quando(agora - o['em'])})" for o in item["onde"][-3:]) + ".")
            if not spoiler:
                partes.append("Sem spoiler: não conte o que acontece depois de onde ela está, nem reviravoltas, "
                              "a não ser que ela peça.")
        return " ".join(partes)
