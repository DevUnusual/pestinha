"""
MEMÓRIA REMOTA - o mesmo pet em vários computadores, pelo serviço de memória (servidor/memoria/).

Opcional e desligado por padrão ("Memória em outro computador", nas Configurações). Os arquivos
continuam no disco como sempre (o pet funciona sem rede); este módulo só os sincroniza:
    ao abrir     baixa o que outro computador gravou depois da última sincronia e avisa o servidor
                 que este computador está com o pet aberto
    ao salvar    (no máximo a cada ENVIA_A_CADA s, numa thread) manda o que mudou aqui
    ao fechar    manda o que falta

O que vai: a rede, a memória e a homeostase do pet (memory/pets/<pet>/) e a definição dele
(pets/<pet>.json, com a personalidade). O que é de cada computador (permissões, painéis, rotina) fica.
Cada computador tem também as próprias lembranças (lembrancas_<máquina>.jsonl, ver mind/lembrancas.py):
só ele grava a dele; as dos outros só são baixadas, para o pet saber o que viu em cada sistema.

Conflito (os dois mudaram desde a última sincronia): ao abrir, vale o mais recente; com o pet aberto, vale
o deste computador, porque é o estado que está vivo aqui. O log diz quando isso acontece.
Sem Qt: só arquivos e HTTP. As chamadas bloqueiam, com tempo curto.
"""

import hashlib
import json
import os
import re
import socket
import sys
import time
import urllib.error
import urllib.request

from .ia.provedores import endereco_de
from .log import log
from .store import read_json, write_json

PORTA_MEMORIA = 11600
TEMPO_LIMITE = 4.0          # s por pedido
ENVIA_A_CADA = 60.0         # s mínimos entre um envio e outro (o app salva a cada 30 s)
PREFIXO_LEMBRANCAS = "lembrancas_"


class ErroMemoria(Exception):
    """O serviço de memória não respondeu ou recusou o pedido (a mensagem diz o que fazer)."""


def endereco_memoria(texto):
    """'192.168.3.250' -> 'http://192.168.3.250:11600'. Vazio ou inválido vira None (sem servidor)."""
    return endereco_de(texto, PORTA_MEMORIA, None) if (texto or "").strip() else None


def sistema_atual():
    """windows, macos ou linux: de onde vem cada lembrança."""
    return {"win32": "windows", "darwin": "macos"}.get(sys.platform, "linux")


def maquina_atual():
    """Nome deste computador em forma de id (vira nome de arquivo): minúsculas, números e '_'."""
    nome = re.sub(r"[^a-z0-9]+", "_", socket.gethostname().lower()).strip("_")[:28]          # lembrancas_<máquina>.jsonl cabe no limite do servidor
    return nome or "pc"


def _hash(texto):
    """Mesma impressão digital do servidor."""
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def _ler_texto(caminho):
    """O arquivo como texto, ou None se não existe (ou não deu para ler)."""
    try:
        return caminho.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def _gravar_texto(caminho, texto):
    """Grava de forma atômica (o pet pode estar lendo)."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    tmp = caminho.with_name(caminho.name + ".tmp")
    tmp.write_text(texto, encoding="utf-8")
    os.replace(tmp, caminho)


class Sincronia:
    """Sincroniza os arquivos de um pet com o serviço de memória."""

    def __init__(self, base_url, pet_id, arquivos, pasta, maquina=None, sistema=None, token=None):
        """`arquivos`: {nome do documento: caminho}; `pasta`: onde ficam as lembranças e o .sync.json."""
        self.base_url = base_url
        self.pet_id = pet_id
        self.maquina = maquina or maquina_atual()
        self.sistema = sistema or sistema_atual()
        self.pasta = pasta
        self.proprias = f"{PREFIXO_LEMBRANCAS}{self.maquina}.jsonl"
        self.arquivos = dict(arquivos, **{self.proprias: pasta / self.proprias})
        self.manifesto_path = pasta / ".sync.json"
        self.token = os.environ.get("PESTINHA_MEMORIA_TOKEN", "") if token is None else token
        self.ultimo_envio = float("-inf")
        self.enviando = False

    # ---------------- HTTP ----------------

    def _pedir(self, metodo, rota, corpo=None):
        """(código, JSON) do serviço. Falha de rede vira ErroMemoria; 409 volta como código."""
        dados = None if corpo is None else json.dumps(corpo, ensure_ascii=False).encode("utf-8")
        pedido = urllib.request.Request(f"{self.base_url}{rota}", data=dados, method=metodo)
        pedido.add_header("Content-Type", "application/json")
        if self.token:
            pedido.add_header("Authorization", f"Bearer {self.token}")
        try:
            with urllib.request.urlopen(pedido, timeout=TEMPO_LIMITE) as resposta:
                return resposta.status, json.loads(resposta.read().decode("utf-8"))
        except urllib.error.HTTPError as erro:
            try:
                corpo_erro = json.loads(erro.read().decode("utf-8"))
            except ValueError:
                corpo_erro = {}
            if erro.code in (404, 409):
                return erro.code, corpo_erro
            if erro.code == 401:
                raise ErroMemoria("o serviço de memória pediu um token (PESTINHA_MEMORIA_TOKEN)") from erro
            raise ErroMemoria(f"o serviço de memória recusou ({erro.code}): {corpo_erro.get('erro', '')}") from erro
        except (urllib.error.URLError, OSError, ValueError) as erro:
            raise ErroMemoria(f"o serviço de memória não respondeu em {self.base_url}") from erro

    def _rota(self, doc=""):
        return f"/v1/pets/{self.pet_id}" + (f"/{doc}" if doc else "")

    # ---------------- manifesto ----------------

    def _manifesto(self):
        """{doc: {"versao", "hash"}} da última sincronia de cada documento."""
        dados = read_json(self.manifesto_path, default={})
        return dados if isinstance(dados, dict) else {}

    def _guardar_manifesto(self, manifesto):
        try:
            write_json(self.manifesto_path, manifesto)
        except OSError as erro:
            log(f"[memória] não salvou o .sync.json: {erro}")

    # ---------------- ao abrir ----------------

    def baixar(self):
        """Traz o que mudou no servidor. Devolve quem está com o pet aberto em outro computador (ou None)."""
        _codigo, indice = self._pedir("GET", self._rota())
        docs = indice.get("docs", {}) if isinstance(indice, dict) else {}
        manifesto = self._manifesto()
        for doc, meta in sorted(docs.items()):
            caminho = self._caminho(doc)
            if caminho is None or not isinstance(meta, dict):
                continue
            marca = manifesto.get(doc, {"versao": 0, "hash": None})
            local = _ler_texto(caminho)
            if local is not None and _hash(local) == meta.get("hash"):
                manifesto[doc] = {"versao": meta["versao"], "hash": meta["hash"]}     # já iguais
                continue
            if meta.get("versao", 0) <= marca.get("versao", 0):
                continue                                   # nada novo lá; o que mudou aqui vai no envio
            mudou_aqui = local is not None and _hash(local) != marca.get("hash")
            if mudou_aqui and caminho.stat().st_mtime > meta.get("saved_at", 0):
                # os dois mudaram e o daqui é mais novo: fica o daqui, que sobe no próximo envio
                log(f"[memória] {doc}: mudou aqui e em {meta.get('maquina')}; fica o daqui (mais novo)")
                manifesto[doc] = {"versao": meta["versao"], "hash": marca.get("hash")}
                continue
            _codigo, achado = self._pedir("GET", self._rota(doc))
            texto = achado.get("conteudo") if isinstance(achado, dict) else None
            if not isinstance(texto, str):
                continue
            _gravar_texto(caminho, texto)
            manifesto[doc] = {"versao": achado["meta"]["versao"], "hash": _hash(texto)}
            log(f"[memória] {doc}: veio de {meta.get('maquina')} (versão {meta['versao']})")
        self._guardar_manifesto(manifesto)
        _codigo, resposta = self._pedir("POST", self._rota("ativo"),
                                        {"maquina": self.maquina, "sistema": self.sistema})
        antes = resposta.get("antes") if isinstance(resposta, dict) else None
        if isinstance(antes, dict) and antes.get("maquina") != self.maquina:
            return antes.get("maquina")
        return None

    def _caminho(self, doc):
        """Onde fica um documento aqui. Lembranças de outro computador vão para a pasta do pet."""
        if doc in self.arquivos:
            return self.arquivos[doc]
        if doc.startswith(PREFIXO_LEMBRANCAS) and doc.endswith(".jsonl") and "/" not in doc and "\\" not in doc:
            return self.pasta / doc
        return None                                        # documento que este Pestinha não conhece

    # ---------------- ao salvar ----------------

    def hora_de_enviar(self, now):
        """Já passou o intervalo mínimo e não tem envio a caminho."""
        return not self.enviando and now - self.ultimo_envio >= ENVIA_A_CADA

    def enviar(self):
        """Manda o que mudou aqui desde a última sincronia. Devolve quantos documentos subiram."""
        self.enviando = True
        self.ultimo_envio = time.monotonic()
        try:
            manifesto = self._manifesto()
            subiu = 0
            for doc, caminho in sorted(self.arquivos.items()):
                texto = _ler_texto(caminho)
                if texto is None:
                    continue
                marca = manifesto.get(doc, {"versao": 0, "hash": None})
                if _hash(texto) == marca.get("hash"):
                    continue
                meta = self._subir(doc, texto, marca.get("versao", 0), caminho.stat().st_mtime)
                if meta:
                    manifesto[doc] = {"versao": meta["versao"], "hash": _hash(texto)}
                    subiu += 1
            self._guardar_manifesto(manifesto)
            self._pedir("POST", self._rota("ativo"), {"maquina": self.maquina, "sistema": self.sistema})
            return subiu
        finally:
            self.enviando = False

    def _subir(self, doc, texto, base, saved_at):
        """PUT de um documento. Se outro computador gravou no meio, vale o daqui (o pet vivo é este)."""
        corpo = {"base": base, "conteudo": texto, "saved_at": saved_at, "maquina": self.maquina,
                 "sistema": self.sistema}
        codigo, resposta = self._pedir("PUT", self._rota(doc), corpo)
        if codigo == 409:
            atual = resposta.get("meta", {})
            log(f"[memória] {doc}: {atual.get('maquina')} também gravou; fica a versão daqui")
            corpo["base"] = atual.get("versao", 0)
            codigo, resposta = self._pedir("PUT", self._rota(doc), corpo)
        if codigo != 200:
            log(f"[memória] {doc}: não subiu ({codigo})")
            return None
        return resposta.get("meta")


def testar_memoria(endereco, tempo=3.0):
    """(deu_certo, mensagem): o serviço de memória responde nesse endereço?"""
    base = endereco_memoria(endereco)
    if base is None:
        return False, "endereço inválido (exemplo: 192.168.0.10 ou http://192.168.0.10:11600)"
    try:
        with urllib.request.urlopen(f"{base}/health", timeout=tempo) as resposta:
            dados = json.loads(resposta.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError):
        return False, f"o serviço de memória não respondeu em {base} (ligado? aceita conexões da rede?)"
    if not isinstance(dados, dict) or dados.get("servico") != "pestinha-memoria":
        return False, f"{base} respondeu, mas não parece o serviço de memória do Pestinha"
    return True, f"serviço de memória ok em {base} (este computador: {maquina_atual()}, {sistema_atual()})"


def criar(perms, paths, pet_id, pet_paths):
    """A Sincronia deste pet, ou None se a memória compartilhada está desligada ou sem endereço."""
    if not perms.get("memoria_compartilhada"):
        return None
    base = endereco_memoria(perms.get("memoria_url", ""))
    if base is None:
        return None
    arquivos = {p.name: p for p in pet_paths.todos()}
    arquivos["definicao.json"] = paths.definicao(pet_id)          # a personalidade vai junto
    arquivos["conhecimento.jsonl"] = pet_paths.conhecimento       # e o que ele aprendeu nos vídeos
    return Sincronia(base, pet_id, arquivos, pet_paths.base)
