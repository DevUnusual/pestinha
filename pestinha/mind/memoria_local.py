"""
MEMÓRIA LOCAL - busca no que ele já sabe de você, para o chat levar só o que importa (opcional: "Lembrar das
conversas", desligado por padrão).

Sem Qt. Um índice SQLite FTS5 em memory/pets/<pet>/memoria.sqlite, montado a partir dos arquivos que já
existem (o índice é só uma cópia para buscar; apagar o arquivo não perde nada):

    diario.jsonl            o resumo de cada dia de conversa (mind/diario.py)
    conhecimento.jsonl      o que ele aprendeu assistindo vídeos com você
    lembrancas_*.jsonl      o que ele viu você fazendo, em cada computador
    jogos.json              os seus jogos: nome, gênero, premissa, mecânicas, dicas e onde você está. A história
                            NUNCA entra no índice: ela só vai para o modelo até onde você chegou (mind/jogos.py),
                            e o índice não pode ser um atalho para spoiler.

A busca é normalizada dos dois lados: sem acento, sem pontuação, sem maiúscula ("o que aprendemos sobre
python?" acha "Aula de Python,"). O índice se refaz sozinho quando um desses arquivos muda.
"""

import json
import re
import sqlite3
import threading
import time
from pathlib import Path

from ..log import log
from .conhecimento import ler as ler_conhecimento
from .lembrancas import ler as ler_lembrancas, quando

MAX_TRECHOS = 5
MAX_TRECHO = 400            # caracteres de cada trecho que vai para o chat
PALAVRAS_VAZIAS = {
    "a", "o", "as", "os", "um", "uma", "de", "da", "do", "das", "dos", "e", "em", "no", "na", "nos", "nas", "que",
    "se", "por", "pra", "para", "com", "sem", "eu", "voce", "vc", "me", "te", "mim", "ele", "ela", "isso", "esse",
    "essa", "aquele", "aquela", "foi", "era", "ser", "tem", "ter", "sobre", "qual", "quais", "como", "quando",
    "onde", "lembra", "lembrar", "lembro", "sabe", "sei", "gente", "nos", "aprendemos", "aprendi", "falamos",
    "conversamos", "ja", "mais", "muito", "bem", "ai", "la", "aqui", "agora", "hoje", "ontem",
}


def normalizar(texto):
    """Minúsculas, sem acento e sem pontuação (o mesmo do roteador do chat)."""
    from ..ia.roteador import _normal
    return _normal(texto)


def termos(texto):
    """As palavras que valem para buscar: normalizadas, sem as vazias e com pelo menos 3 letras."""
    return [p for p in dict.fromkeys(normalizar(texto).split()) if len(p) >= 3 and p not in PALAVRAS_VAZIAS
            and not p.isdigit()]


def _jsonl(caminho):
    """As linhas JSON (dicionários) de um arquivo; linha estragada fica de fora."""
    itens = []
    try:
        linhas = Path(caminho).read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return itens
    for linha in linhas:
        try:
            item = json.loads(linha)
        except ValueError:
            continue
        if isinstance(item, dict):
            itens.append(item)
    return itens


def trechos_das_fontes(pasta, jogos=None):
    """[(fonte, quando, texto)] de tudo o que ele sabe, a partir dos arquivos da pasta do pet."""
    pasta = Path(pasta)
    trechos = []
    for item in _jsonl(pasta / "diario.jsonl"):
        if isinstance(item.get("resumo"), str):
            trechos.append(("conversa", item.get("data", ""), item["resumo"]))
    for item in ler_conhecimento(pasta / "conhecimento.jsonl"):
        pontos = "; ".join(p for p in item.get("pontos", []) if isinstance(p, str))
        trechos.append(("vídeo", item.get("em", 0), f"{item.get('titulo', '')}: {item.get('resumo', '')} {pontos}"))
    for arquivo in sorted(pasta.glob("lembrancas_*.jsonl")):
        for item in ler_lembrancas(arquivo):
            trechos.append(("visto", item.get("em", 0),
                            f"{item.get('resumo', '')} ({item.get('programa', '')}, {item.get('maquina', '')})"))
    for item in (jogos.todos().values() if jogos is not None else []):
        partes = [item.get("nome", ""), item.get("genero", ""), item.get("premissa", "")]
        partes += list(item.get("gameplay", [])) + list(item.get("dicas", []))
        partes += [f"esteve em {o['texto']}" for o in item.get("onde", [])[-3:]]
        trechos.append(("jogo", item.get("visto_em", 0), ". ".join(p for p in partes if p)))       # sem a história
    return [(f, q, " ".join(str(t).split())) for f, q, t in trechos if str(t).strip()]


class MemoriaLocal:
    """O índice de busca de um pet (memoria.sqlite), refeito quando as fontes mudam."""

    def __init__(self, pasta, jogos=None):
        """`pasta` é memory/pets/<pet>/; `jogos` é o mind/jogos.Jogos do pet (para o índice ler sem a história)."""
        self.pasta = Path(pasta)
        self.caminho = self.pasta / "memoria.sqlite"
        self.jogos = jogos
        self._assinatura = None
        self._trava = threading.Lock()

    def _fontes(self):
        return [self.pasta / "diario.jsonl", self.pasta / "conhecimento.jsonl", self.pasta / "jogos.json",
                *sorted(self.pasta.glob("lembrancas_*.jsonl"))]

    def assinatura(self):
        """O tamanho e a data de cada fonte: mudou, o índice é refeito."""
        marcas = []
        for fonte in self._fontes():
            try:
                estado = fonte.stat()
                marcas.append((fonte.name, estado.st_size, int(estado.st_mtime_ns)))
            except OSError:
                pass
        return tuple(marcas)

    def _conectar(self):
        self.pasta.mkdir(parents=True, exist_ok=True)
        conexao = sqlite3.connect(self.caminho)
        conexao.execute("CREATE VIRTUAL TABLE IF NOT EXISTS trechos USING fts5("
                        "texto_normal, fonte UNINDEXED, quando UNINDEXED, texto UNINDEXED, "
                        "tokenize='unicode61 remove_diacritics 2')")
        return conexao

    def reindexar(self, forcar=False):
        """Refaz o índice se alguma fonte mudou. Devolve quantos trechos ele tem (ou None se não mexeu)."""
        assinatura = self.assinatura()
        if not forcar and assinatura == self._assinatura and self.caminho.exists():
            return None
        trechos = trechos_das_fontes(self.pasta, self.jogos)
        with self._trava:
            try:
                with self._conectar() as conexao:
                    conexao.execute("DELETE FROM trechos")
                    conexao.executemany("INSERT INTO trechos (texto_normal, fonte, quando, texto) VALUES (?, ?, ?, ?)",
                                        [(normalizar(t), f, str(q), t) for f, q, t in trechos])
                conexao.close()
            except sqlite3.Error as erro:
                log(f"[memória local] não montei o índice: {erro}")
                return None
        self._assinatura = assinatura
        return len(trechos)

    def apagar(self):
        """Apaga o índice (ele é só uma cópia para buscar: refaz sozinho a partir do que sobrou)."""
        with self._trava:
            try:
                self.caminho.unlink(missing_ok=True)
            except OSError as erro:
                log(f"[memória local] não apagou o índice: {erro}")
        self._assinatura = None

    def buscar(self, texto, n=MAX_TRECHOS):
        """Os `n` trechos mais parecidos com `texto` (normalizado), já prontos para o chat. Vazio se nada bate."""
        palavras = termos(texto)
        if not palavras:
            return []
        self.reindexar()
        consulta = " OR ".join(f'"{re.sub(r"[^a-z0-9]", "", p)}"*' for p in palavras if re.sub(r"[^a-z0-9]", "", p))
        if not consulta:
            return []
        with self._trava:
            try:
                conexao = self._conectar()
                linhas = conexao.execute("SELECT fonte, quando, texto FROM trechos WHERE trechos MATCH ? "
                                         "ORDER BY bm25(trechos) LIMIT ?", (consulta, int(n))).fetchall()
                conexao.close()
            except sqlite3.Error as erro:
                log(f"[memória local] a busca falhou: {erro}")
                return []
        return [self._formatar(f, q, t) for f, q, t in linhas]

    @staticmethod
    def _formatar(fonte, quando_, texto):
        """'(vídeo, há 2 dias) Aula de Python: ...' com no máximo MAX_TRECHO caracteres. O diário traz a data."""
        try:
            segundos = float(quando_)
        except (TypeError, ValueError):
            segundos = None
        if segundos:
            rotulo = f"{fonte}, {quando(time.time() - segundos)}"
        elif quando_ and quando_ != "0":
            rotulo = f"{fonte}, {quando_}"                 # a data do diário: '2026-11-08'
        else:
            rotulo = fonte
        texto = texto if len(texto) <= MAX_TRECHO else texto[:MAX_TRECHO - 1].rstrip() + "…"
        return f"({rotulo}) {texto}"
