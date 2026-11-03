"""
PESTINHA MEMÓRIA - a memória e a personalidade dos pets num computador da rede, para todos os seus
computadores (Windows, Mac e, no futuro, iPhone) falarem com o mesmo bichinho.

Só a biblioteca padrão do Python (3.10+): nada para instalar. Guarda cada arquivo do pet como está
(o JSON da rede, da homeostase, do protesto... e o pets/<pet>.json), com um número de versão:

    GET  /health                       está vivo?
    GET  /v1/pets                      quais pets existem aqui
    GET  /v1/pets/<pet>                os documentos do pet (versão, quando, de qual computador) e quem
                                       está com ele aberto agora
    GET  /v1/pets/<pet>/<doc>          um documento: {"meta": {...}, "conteudo": "<texto>"}
    PUT  /v1/pets/<pet>/<doc>          grava: {"base": <versão que você tinha>, "conteudo", "saved_at",
                                       "maquina"}. Se alguém gravou depois da sua base: 409 com a versão atual
    POST /v1/pets/<pet>/ativo          "estou com ele aberto" ({"maquina"}); devolve quem estava antes

Sem senha por padrão, como o serviço de voz: deixe a porta aberta só para a rede de casa. Com a variável
PESTINHA_MEMORIA_TOKEN definida, todo pedido (menos /health) precisa de "Authorization: Bearer <token>".
"""

import hashlib
import hmac
import json
import os
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PORTA = int(os.environ.get("PESTINHA_MEMORIA_PORTA", "11600"))
DADOS = Path(os.environ.get("PESTINHA_MEMORIA_DADOS", str(Path.home() / "pestinha-memoria" / "dados")))
TOKEN = os.environ.get("PESTINHA_MEMORIA_TOKEN", "")
MAX_BYTES = 8 * 1024 * 1024         # por documento (o episodes.jsonl é o maior)
ATIVO_VALE = 120.0                  # s: sem notícia por mais que isso, o computador não está mais com ele aberto

ID_DE_PET = re.compile(r"^[a-z0-9][a-z0-9_-]{0,39}$")
NOME_DE_DOC = re.compile(r"^[a-z0-9][a-z0-9_]{0,39}\.jsonl?$")
ROTA = re.compile(r"^/v1/pets(?:/([^/]+)(?:/([^/]+))?)?$")

_trava = threading.Lock()           # um usuário, poucos pedidos: uma trava só, simples e sem corrida


def _hash(texto):
    """Impressão digital do conteúdo (para os dois lados saberem se mudou)."""
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def _gravar(caminho, texto):
    """Grava de forma atômica: arquivo temporário e troca."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    tmp = caminho.with_name(caminho.name + ".tmp")
    tmp.write_text(texto, encoding="utf-8")
    os.replace(tmp, caminho)


def _ler_json(caminho, padrao):
    """JSON do disco, ou `padrao` se não existir ou estiver estragado."""
    try:
        return json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return padrao


def conteudo_valido(doc, texto):
    """Só aceita JSON (ou uma linha de JSON por linha, no .jsonl): é o que o Pestinha grava."""
    try:
        if doc.endswith(".jsonl"):
            for linha in texto.splitlines():
                if linha.strip():
                    json.loads(linha)
        else:
            json.loads(texto)
    except ValueError:
        return False
    return True


class Memoria:
    """Os documentos de cada pet numa pasta: <dados>/<pet>/<doc> e, ao lado, <doc>.meta."""

    def __init__(self, pasta):
        """`pasta` é onde tudo fica (criada no primeiro documento)."""
        self.pasta = Path(pasta)

    def _meta(self, pet, doc):
        """Versão, horário, computador e hash de um documento (versão 0 = não existe)."""
        return _ler_json(self.pasta / pet / f"{doc}.meta", {"versao": 0})

    def pets(self):
        """Os pets guardados aqui."""
        if not self.pasta.exists():
            return []
        return sorted(p.name for p in self.pasta.iterdir() if p.is_dir() and ID_DE_PET.match(p.name))

    def indice(self, pet):
        """Os documentos do pet e quem está com ele aberto."""
        base = self.pasta / pet
        docs = {}
        if base.exists():
            for meta in base.glob("*.meta"):
                doc = meta.name[:-5]
                if NOME_DE_DOC.match(doc):
                    docs[doc] = self._meta(pet, doc)
        ativo = _ler_json(base / "ativo.estado", None)
        if not isinstance(ativo, dict) or time.time() - ativo.get("em", 0) > ATIVO_VALE:
            ativo = None
        return {"docs": docs, "ativo": ativo}

    def ler(self, pet, doc):
        """Um documento, ou None se não existe."""
        meta = self._meta(pet, doc)
        if not meta.get("versao"):
            return None
        try:
            texto = (self.pasta / pet / doc).read_text(encoding="utf-8")
        except OSError:
            return None
        return {"meta": meta, "conteudo": texto}

    def gravar(self, pet, doc, base, texto, saved_at, maquina, sistema="?"):
        """(True, meta nova) ou (False, meta atual) se alguém gravou depois da `base` de quem pediu."""
        with _trava:
            atual = self._meta(pet, doc)
            if base != atual.get("versao", 0):
                return False, atual
            meta = {"versao": atual.get("versao", 0) + 1, "saved_at": saved_at, "maquina": maquina, "sistema": sistema,
                    "hash": _hash(texto), "recebido_em": time.time()}
            _gravar(self.pasta / pet / doc, texto)
            _gravar(self.pasta / pet / f"{doc}.meta", json.dumps(meta))
            return True, meta

    def anunciar(self, pet, maquina, sistema="?"):
        """`maquina` está com o pet aberto agora. Devolve quem estava antes (se ainda valia)."""
        with _trava:
            antes = self.indice(pet)["ativo"]
            _gravar(self.pasta / pet / "ativo.estado", json.dumps({"maquina": maquina, "sistema": sistema,
                                                                  "em": time.time()}))
            return antes


def criar_handler(memoria, token=""):
    """O tratador de pedidos HTTP, ligado a uma Memoria (e a um token, se houver)."""

    class Handler(BaseHTTPRequestHandler):
        """Um pedido: confere rota, token e nomes, e responde em JSON."""
        server_version = "pestinha-memoria/1"

        def log_message(self, formato, *args):
            """Uma linha por pedido, sem conteúdo."""
            print(f"[memória] {self.address_string()} {formato % args}", flush=True)

        def _responder(self, codigo, dados):
            corpo = json.dumps(dados, ensure_ascii=False).encode("utf-8")
            self.send_response(codigo)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(corpo)))
            self.end_headers()
            self.wfile.write(corpo)

        def _autorizado(self):
            if not token:
                return True
            recebido = self.headers.get("Authorization", "")
            return hmac.compare_digest(recebido.encode(), f"Bearer {token}".encode())

        def _rota(self):
            """(pet, doc) da URL já conferidos, ou None (e já respondeu o erro)."""
            if not self._autorizado():
                self._responder(401, {"erro": "token errado ou faltando"})
                return None
            achado = ROTA.match(self.path.split("?", 1)[0])
            if not achado:
                self._responder(404, {"erro": "rota desconhecida"})
                return None
            pet, doc = achado.groups()
            if pet is not None and not ID_DE_PET.match(pet):
                self._responder(400, {"erro": "id de pet inválido"})
                return None
            if doc is not None and doc != "ativo" and not NOME_DE_DOC.match(doc):
                self._responder(400, {"erro": "nome de documento inválido"})
                return None
            return pet, doc

        def _corpo(self):
            """O JSON do corpo do pedido, ou None (e já respondeu o erro)."""
            try:
                tamanho = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                tamanho = -1
            if not 0 < tamanho <= MAX_BYTES + 4096:
                self._responder(413 if tamanho > 0 else 400, {"erro": "corpo vazio ou grande demais"})
                return None
            try:
                dados = json.loads(self.rfile.read(tamanho).decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                self._responder(400, {"erro": "corpo não é JSON"})
                return None
            if not isinstance(dados, dict):
                self._responder(400, {"erro": "corpo não é um objeto JSON"})
                return None
            return dados

        def do_GET(self):
            if self.path == "/health":
                self._responder(200, {"ok": True, "servico": "pestinha-memoria", "versao": 1})
                return
            rota = self._rota()
            if rota is None:
                return
            pet, doc = rota
            if pet is None:
                self._responder(200, {"pets": memoria.pets()})
            elif doc is None:
                self._responder(200, memoria.indice(pet))
            else:
                achado = memoria.ler(pet, doc)
                self._responder(200 if achado else 404, achado or {"erro": "documento não existe"})

        def do_PUT(self):
            rota = self._rota()
            if rota is None:
                return
            pet, doc = rota
            if pet is None or doc is None or doc == "ativo":
                self._responder(405, {"erro": "PUT só em /v1/pets/<pet>/<doc>"})
                return
            dados = self._corpo()
            if dados is None:
                return
            texto, base = dados.get("conteudo"), dados.get("base")
            if not isinstance(texto, str) or type(base) is not int or len(texto.encode("utf-8")) > MAX_BYTES:
                self._responder(400, {"erro": "precisa de 'conteudo' (texto) e 'base' (número)"})
                return
            if not conteudo_valido(doc, texto):
                self._responder(400, {"erro": "conteúdo não é JSON válido"})
                return
            saved_at = dados.get("saved_at")
            saved_at = float(saved_at) if isinstance(saved_at, (int, float)) else time.time()
            maquina = str(dados.get("maquina") or "?")[:60]
            sistema = str(dados.get("sistema") or "?")[:20]
            ok, meta = memoria.gravar(pet, doc, base, texto, saved_at, maquina, sistema)
            self._responder(200 if ok else 409, {"meta": meta})

        def do_POST(self):
            rota = self._rota()
            if rota is None:
                return
            pet, doc = rota
            if pet is None or doc != "ativo":
                self._responder(405, {"erro": "POST só em /v1/pets/<pet>/ativo"})
                return
            dados = self._corpo()
            if dados is None:
                return
            antes = memoria.anunciar(pet, str(dados.get("maquina") or "?")[:60], str(dados.get("sistema") or "?")[:20])
            self._responder(200, {"antes": antes})

    return Handler


def servir(porta=PORTA, pasta=DADOS, token=TOKEN, host="0.0.0.0"):
    """Cria o servidor (sem começar a atender): `servidor.serve_forever()` para atender."""
    return ThreadingHTTPServer((host, porta), criar_handler(Memoria(pasta), token))


if __name__ == "__main__":
    servidor = servir()
    print(f"[memória] em http://0.0.0.0:{PORTA}, dados em {DADOS}"
          + (" (com token)" if TOKEN else " (sem token: só na rede de casa)"), flush=True)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass
