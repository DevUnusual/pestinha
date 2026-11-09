"""
IMAGEM - quando você pede no chat para ele pesquisar algo, ele acha uma imagem na Wikipédia para projetar.

Sem Qt: só texto e HTTP. As chamadas bloqueiam: quem chama roda numa thread (ver mind/visao.py).
    pedido_de_imagem(texto)   'pesquisa o que é manga' -> 'manga'; conversa comum -> None
    escolher(paginas, termo)  qual resultado da busca tem a imagem certa (devolve o link dela)
    baixar(url)               baixa o link de uma imagem (só https, só image/*, até MAX_BYTES); do
                              Wikimedia, pede a miniatura de TAMANHO px em vez do arquivo original
    link_permitido(url)       o link pode ser baixado? (https, porta 443, sem localhost nem IP da rede)
    titulo_do_link(url)       'https://.../Hapus_Mango.jpg' -> 'Hapus Mango'
    buscar(termo)             acha o link na Wikipédia e baixa: (título, bytes da imagem) ou None

O link pode vir do Hermes (linha "IMAGEM:" na resposta, ver mind/visao.py) ou da busca na Wikipédia,
para onde vai só o termo, nunca a conversa, o print ou o título da janela.

O link vem de um modelo que lê páginas da web, então não é confiável: um site pode fazer o modelo
devolver o endereço de um aparelho da sua rede (o roteador, a impressora, o servidor da casa). Por isso
ele pode ser de qualquer site, mas só por https na porta padrão, nunca de localhost nem de um IP privado,
e o nome é resolvido antes de baixar: um nome que aponta para dentro da rede também é recusado. Cada
redirecionamento passa pela mesma conferência (no máximo MAX_REDIRECIONAMENTOS).
"""

import ipaddress
import json
import re
import socket
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

API = "https://{lingua}.wikipedia.org/w/api.php"
LINGUAS = ("pt", "en")
TAMANHO = 500                   # px da miniatura (o Wikimedia só aceita os tamanhos padrão: 330, 500, 960...)
MAX_BYTES = 8_000_000
TEMPO_LIMITE = 10.0
AGENTE = "Pestinha/0.7 (pet de tela; imagem do que pediram no chat)"
MAX_REDIRECIONAMENTOS = 3
_NOMES_LOCAIS = (".local", ".localhost", ".internal", ".lan", ".home", ".arpa")


def _ip_publico(texto):
    """True se `texto` é um IP público (nem privado, nem loopback, nem link-local, reservado ou multicast)."""
    try:
        return ipaddress.ip_address(texto).is_global
    except ValueError:
        return False


def link_permitido(url):
    """O link pode ser baixado: https, porta 443, um nome ou IP público. Não resolve o nome (ver _resolve_publico)."""
    try:
        partes = urllib.parse.urlsplit(url or "")
        porta = partes.port
    except ValueError:
        return False
    host = (partes.hostname or "").lower().rstrip(".")
    if partes.scheme != "https" or not host or porta not in (None, 443) or partes.username or partes.password:
        return False
    if host == "localhost" or host.endswith(_NOMES_LOCAIS) or "." not in host.strip("[]"):
        return False
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return True                                  # um nome: resolvido em _resolve_publico, antes de baixar
    return _ip_publico(host)


def _resolve_publico(host):
    """Todos os IPs do nome são públicos (um nome que aponta para a rede de casa é recusado)."""
    try:
        enderecos = {info[4][0] for info in socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)}
    except (socket.gaierror, UnicodeError, OSError):
        return False
    return bool(enderecos) and all(_ip_publico(e.split("%")[0]) for e in enderecos)


def conferir(url):
    """Levanta ValueError se o link não pode ser baixado (o nome é resolvido aqui)."""
    if not link_permitido(url):
        raise ValueError(f"link de imagem recusado: {url!r} (só https de um site público)")
    if not _resolve_publico(urllib.parse.urlsplit(url).hostname):
        raise ValueError(f"link de imagem recusado: {urllib.parse.urlsplit(url).hostname} aponta para a rede local")


class _Redirecionamento(urllib.request.HTTPRedirectHandler):
    """Segue um redirecionamento só para um link que também pode ser baixado, e no máximo MAX_REDIRECIONAMENTOS."""

    max_redirections = MAX_REDIRECIONAMENTOS

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        conferir(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_abrir = urllib.request.build_opener(_Redirecionamento()).open

# "pesquisa (pra mim) (sobre|o que é|quem é) X", "me mostra (uma foto de) X", "procura X"...
_PEDIDO = re.compile(
    r"\b(?:pesquis\w*|procur\w*|busc\w*|mostr\w*|quero ver)\s+"
    r"(?:(?:pra|para) mim\s+)?(?:(?:na|em) (?:internet|web|wikip[ée]dia)\s+)?"
    r"(?:(?:uma |a )?(?:imagem|foto|figura)s? (?:de|da|do|das|dos)\s+)?"
    r"(?:sobre\s+|o que (?:é|e|são|sao)\s+|quem (?:é|e|foi)\s+|como (?:é|e)\s+)?"
    r"(?:(?:um|uma|o|a|os|as)\s+)?"
    r"(?P<termo>[^?.!,;\n]{2,60})",
    re.IGNORECASE,
)
_RABO = re.compile(r"\s+(?:(?:na|em) (?:internet|web|wikip[ée]dia)|pra mim|para mim|por favor|pfv|pf)$",
                   re.IGNORECASE)


def pedido_de_imagem(texto):
    """O termo de um pedido explícito de pesquisa ('pesquisa o que é manga' -> 'manga'), ou None."""
    achado = _PEDIDO.search(texto or "")
    if not achado:
        return None
    termo = achado.group("termo").strip()
    while True:
        limpo = _RABO.sub("", termo).strip()
        if limpo == termo:
            break
        termo = limpo
    if termo.lower() in ("isso", "isto", "aquilo", "ai", "aí", "aqui", "algo", "alguma coisa"):
        return None
    return termo or None


def _normal(texto):
    """Minúsculas e espaços simples, mantendo os acentos ('manga' e 'mangá' são coisas diferentes)."""
    return " ".join(unicodedata.normalize("NFC", texto).lower().split())


def escolher(paginas, termo):
    """
    (título, url da imagem) do melhor resultado com imagem, ou None. Prefere o título igual ao termo,
    depois 'Termo (sentido)', depois a ordem da busca. Páginas de desambiguação não têm imagem e saem.
    """
    alvo = _normal(termo)
    com_imagem = [p for p in sorted(paginas, key=lambda p: p.get("index", 0))
                  if (p.get("thumbnail") or {}).get("source")]

    def nota(pagina):
        titulo = _normal(pagina.get("title", ""))
        if titulo == alvo:
            return 0
        if titulo.startswith(alvo + " ("):
            return 1
        return 2

    if not com_imagem:
        return None
    melhor = min(com_imagem, key=nota)          # min é estável: no empate, vale a ordem da busca
    return melhor["title"], melhor["thumbnail"]["source"]


def _get(url, tempo):
    """Bytes de `url` (no máximo MAX_BYTES), com o User-Agent que a Wikimedia pede. O link e cada
    redirecionamento são conferidos (conferir): nada vai para a rede local."""
    conferir(url)
    pedido = urllib.request.Request(url, headers={"User-Agent": AGENTE})
    with _abrir(pedido, timeout=tempo) as resposta:
        dados = resposta.read(MAX_BYTES + 1)
        tipo = resposta.headers.get("Content-Type", "")
    if len(dados) > MAX_BYTES:
        raise ValueError("imagem grande demais")
    return dados, tipo


_WIKIMEDIA = re.compile(
    r"^(https://upload\.wikimedia\.org/wikipedia/[^/]+)/(?!thumb/)([0-9a-f]/[0-9a-f]{2})/([^/?#]+)$")


_MINIATURA = re.compile(r"^(https://upload\.wikimedia\.org/wikipedia/.+/thumb/.+/)\d+px-([^/]+)$")


def miniatura_wikimedia(url):
    """
    O link da miniatura de TAMANHO px de um arquivo do Wikimedia (o original pode ter vários MB), ou None.
    Uma miniatura de outro tamanho vira a de TAMANHO (tamanho fora do padrão o Wikimedia recusa).
    """
    outra = _MINIATURA.match(url or "")
    if outra:
        novo = f"{outra.group(1)}{TAMANHO}px-{outra.group(2)}"
        return novo if novo != url else None
    achado = _WIKIMEDIA.match(url or "")
    if not achado:
        return None
    base, pasta, nome = achado.groups()
    final = nome + (".png" if nome.lower().endswith(".svg") else "")
    return f"{base}/thumb/{pasta}/{nome}/{TAMANHO}px-{final}"


def titulo_do_link(url):
    """Um título a partir do nome do arquivo: 'https://.../Hapus_Mango.jpg' -> 'Hapus Mango'."""
    nome = urllib.parse.unquote(urllib.parse.urlsplit(url or "").path.rsplit("/", 1)[-1])
    nome = re.sub(r"^\d+px-", "", nome.rsplit(".", 1)[0])
    return re.sub(r"[_\-]+", " ", nome).strip() or "imagem"


def baixar(url, tempo=TEMPO_LIMITE):
    """Bytes da imagem em `url`. Levanta ValueError se o link for recusado (link_permitido), não for imagem
    ou for grande demais."""
    if not link_permitido(url):
        raise ValueError(f"link de imagem recusado: {url!r} (só https de um site público)")
    miniatura = miniatura_wikimedia(url)
    if miniatura:
        try:
            dados, tipo = _get(miniatura, tempo)
            if tipo.startswith("image/"):
                return dados
        except (urllib.error.URLError, OSError, ValueError):
            pass                                        # sem miniatura: baixa o original
    dados, tipo = _get(url, tempo)
    if not tipo.startswith("image/"):
        raise ValueError(f"o link não é uma imagem ({tipo or 'sem tipo'})")
    return dados


def buscar(termo, tempo=TEMPO_LIMITE):
    """(título, bytes da imagem) da Wikipédia para `termo`, em português e depois em inglês. None se não achou."""
    for lingua in LINGUAS:
        consulta = urllib.parse.urlencode({
            "action": "query", "generator": "search", "gsrsearch": termo, "gsrlimit": 5,
            "prop": "pageimages", "piprop": "thumbnail", "pithumbsize": TAMANHO,
            "format": "json", "formatversion": 2,
        })
        try:
            dados, _ = _get(f"{API.format(lingua=lingua)}?{consulta}", tempo)
            paginas = json.loads(dados.decode("utf-8")).get("query", {}).get("pages", [])
        except (urllib.error.URLError, OSError, ValueError):
            continue
        escolhido = escolher(paginas, termo)
        if escolhido is None:
            continue
        titulo, url = escolhido
        try:
            return titulo, baixar(url, tempo)
        except (urllib.error.URLError, OSError, ValueError):
            continue
    return None
