"""
MÚSICA - você pede um estilo no chat ("toca um lo-fi") e ele monta a fila no YouTube Music, aprendendo
com o seu 👍 e 👎 (e com o que você deixa tocar até o fim ou pula).

Sem Qt: só texto, um arquivo JSON e HTTP. As buscas bloqueiam: quem chama roda numa thread (ver
mind/musica_ctl.py).
    pedido_de_musica(texto)    'toca um lo-fi pra mim' -> 'lo-fi'; 'toca música' -> ''; conversa -> None
    comando_de_musica(texto)   'pula' -> 'pular', 'gostei' -> 'gostei'... (só frases curtas; senão None)
    Gosto                      nota por artista e músicas curtidas/banidas, em pets/<pet>/musica.json
    escolher(faixas, gosto, tocadas, curiosidade)   a próxima: o gosto pesa, a curiosidade arrisca
    buscar(estilo)             músicas do estilo (busca no YouTube Music)
    radio(video_id)            músicas parecidas com uma (o "rádio" do YouTube Music)
    link_de_audio(video_id)    o link do áudio (m4a) pelo yt-dlp, para o QMediaPlayer tocar

Para o YouTube vai só o estilo que você pediu e os ids das músicas: nunca a conversa, a tela ou o
gosto guardado. ytmusicapi e yt-dlp são opcionais: sem eles, ErroMusica explica o que instalar.
"""

import json
import math
import random
import re
import unicodedata
from dataclasses import dataclass

DURACAO_MIN = 60                # s: menos que isso é vinheta
DURACAO_MAX = 600               # s: mais que isso é compilação de horas ("3 hours of lofi")
NOTA_MAX = 3.0
EVENTOS = {                     # quanto cada coisa mexe na nota do artista
    "gostei": 1.0,
    "nao_gostei": -1.0,
    "pulou": -0.4,              # pulou sem dar 👎
    "ouviu": 0.25,              # deixou tocar até o fim, sem fazer nada
}
MAX_LISTA = 300                 # ids guardados em curtidas e banidas
INSTALAR = "para tocar música, instale: pip install yt-dlp ytmusicapi"


class ErroMusica(Exception):
    """Falha que vira aviso: biblioteca faltando, YouTube fora do ar, nada encontrado."""


@dataclass(frozen=True)
class Faixa:
    """Uma música: o id do YouTube, o título, os artistas e a duração (s, 0 se não sabe)."""
    video_id: str
    titulo: str
    artistas: tuple = ()
    duracao: int = 0

    @property
    def artista(self):
        """O artista principal ('' se não veio)."""
        return self.artistas[0] if self.artistas else ""

    def nome(self):
        """'Título · Artista' para o cartão e o chat."""
        return f"{self.titulo} · {', '.join(self.artistas)}" if self.artistas else self.titulo


# ---------------- entender o que você disse ----------------

def _normal(texto):
    """Minúsculas, sem acento e sem pontuação nas pontas."""
    texto = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
    return " ".join(texto.lower().split()).strip(" .!?,;:~")


# O pedido vem no começo da frase, depois de no máximo quatro palavras ("Bryan, você pode tocar...",
# "por favor, toca..."): a voz transcreve a frase inteira, com vírgula e ponto de interrogação.
_INICIO = r"^(?P<antes>(?:[\w-]+\s+){0,4}?)"
_TOCA = re.compile(_INICIO + r"(?:toca|toque|tocar|tocasse|reproduz|reproduza|reproduzir|play|"
                   r"quero ouvir|quero escutar|bora ouvir|vamos ouvir)\b\s*(?P<resto>.*)")
_BOTA = re.compile(_INICIO + r"(?:bota|botar|coloca|colocar|coloque|poe|por|ponha)\s+"
                   r"(?P<resto>.*\b(?:musica|musicas|playlist|som|sons)\b.*)")
# "quem toca essa música?" e "que música é essa?" são perguntas sobre música, não pedidos ("que tal" é pedido)
_PERGUNTA = re.compile(r"^(?:quem|qual|quais|que(?! tal)|o que|onde|quando|por que|porque)\b")
_NEGA = re.compile(r"\b(?:nao|nunca|para de|pare de)\b")
_ABERTURA = re.compile(r"^(?:(?:um|uma|uns|umas|o|a|os|as|algo|alguma|algumas|alguns|ai|la|me)\s+)*"
                       r"(?:(?:musica|musicas|playlist|som|sons|cancao|cancoes)\b\s*)?"
                       r"(?:(?:de|do|da|dos|das|no estilo|estilo|tipo)\s+)?")
_RABO = re.compile(r"(?:^|\s+)(?:pra mim|para mim|pra gente|por favor|pfv|pf|ai|agora|ae|ali|aqui|"
                   r"pra tocar|para tocar|pra ouvir|para ouvir|pra eu ouvir|pra escutar)$")
_VAZIO = {"", "algo", "alguma coisa", "qualquer", "qualquer coisa", "musica", "uma musica", "isso", "som"}


def _sem_rabo(texto):
    """Tira 'pra mim', 'por favor', 'aí'... do fim, quantos houver."""
    while True:
        limpo = _RABO.sub("", texto).strip()
        if limpo == texto:
            return texto
        texto = limpo


def pedido_de_musica(texto):
    """O estilo pedido ('toca um lo-fi' -> 'lo-fi'), '' se pediu música sem estilo, None se não pediu."""
    normal = _normal(re.sub(r"[,!?;:]", " ", texto or ""))
    if _PERGUNTA.match(normal):
        return None
    achado = _TOCA.match(normal) or _BOTA.match(normal)
    if not achado or _NEGA.search(achado.group("antes")):
        return None                             # "não toca isso" não é pedido
    if achado.group("antes") and not achado.group("resto"):
        return None                             # "o celular toca" também não
    estilo = _sem_rabo(_ABERTURA.sub("", _sem_rabo(achado.group("resto").strip())))
    return "" if estilo in _VAZIO else estilo[:60]


_COMANDOS = (
    ("nao_gostei", r"(?:nao gostei|nao curti|ruim|que ruim|chata|odiei|essa nao)"),
    ("gostei", r"(?:gostei|curti|amei|boa|que boa|essa e boa|essa e das boas|massa|top)"),
    ("pular", r"(?:pula|pular|proxima|passa|troca|outra)"),
    ("pausar", r"(?:pausa|pause|pausar)"),
    ("continuar", r"(?:continua|continuar|despausa|volta a tocar|solta o som)"),
    ("parar", r"(?:para|pare|parar|chega|desliga)"),
)
_COMANDO = [(nome, re.compile(rf"(?:\w+\s+){{0,2}}?{padrao}"
                              r"(?:\s+(?:essa|isso|a musica|essa musica|o som|a playlist))?(?:\s+por favor)?"))
            for nome, padrao in _COMANDOS]


def comando_de_musica(texto):
    """'pula' -> 'pular', 'não gostei' -> 'nao_gostei'... Só frases curtas inteiras: o resto é conversa."""
    normal = _normal(re.sub(r"[,!?;:]", " ", texto or ""))
    if len(normal) > 40:
        return None
    for nome, padrao in _COMANDO:
        if padrao.fullmatch(normal):
            return nome
    return "gostei" if "👍" in texto else "nao_gostei" if "👎" in texto else None


# ---------------- gosto ----------------

class Gosto:
    """O que ele aprendeu do seu gosto: nota por artista, músicas curtidas e banidas (👎)."""

    def __init__(self, arquivo=None):
        """Começa vazio; `arquivo` é o musica.json do pet (None: só na memória)."""
        self.arquivo = arquivo
        self.artistas = {}
        self.curtidas = []
        self.banidas = []

    def carregar(self):
        """Lê o arquivo (se existir e estiver bom); um arquivo estragado vira gosto vazio."""
        try:
            dados = json.loads(self.arquivo.read_text(encoding="utf-8"))
        except (AttributeError, OSError, ValueError):
            return self
        if isinstance(dados, dict):
            self.artistas = {str(k): max(-NOTA_MAX, min(NOTA_MAX, float(v)))
                             for k, v in (dados.get("artistas") or {}).items() if isinstance(v, (int, float))}
            self.curtidas = [str(i) for i in dados.get("curtidas") or []][-MAX_LISTA:]
            self.banidas = [str(i) for i in dados.get("banidas") or []][-MAX_LISTA:]
        return self

    def salvar(self):
        """Grava o arquivo (sem arquivo, não faz nada)."""
        if self.arquivo is None:
            return
        self.arquivo.parent.mkdir(parents=True, exist_ok=True)
        dados = {"artistas": self.artistas, "curtidas": self.curtidas, "banidas": self.banidas}
        self.arquivo.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")

    def nota(self, faixa):
        """Nota da música (-3 a 3): a média dos artistas dela, e um bônus se você já curtiu."""
        notas = [self.artistas.get(a, 0.0) for a in faixa.artistas] or [0.0]
        return sum(notas) / len(notas) + (1.0 if faixa.video_id in self.curtidas else 0.0)

    def conhece(self, faixa):
        """Se ele já tem opinião sobre algum artista da música."""
        return any(a in self.artistas for a in faixa.artistas)

    def notar(self, faixa, evento):
        """Um 👍, 👎, pulo ou música ouvida até o fim mexe na nota dos artistas dela."""
        delta = EVENTOS[evento]
        for artista in faixa.artistas:
            self.artistas[artista] = max(-NOTA_MAX, min(NOTA_MAX, self.artistas.get(artista, 0.0) + delta))
        if evento == "gostei" and faixa.video_id not in self.curtidas:
            self.curtidas = (self.curtidas + [faixa.video_id])[-MAX_LISTA:]
        elif evento == "nao_gostei":
            self.curtidas = [i for i in self.curtidas if i != faixa.video_id]
            if faixa.video_id not in self.banidas:
                self.banidas = (self.banidas + [faixa.video_id])[-MAX_LISTA:]


def escolher(faixas, gosto, tocadas=(), curiosidade=0.4, sorteio=random):
    """
    A próxima música: nada banido nem repetido nesta sessão. O gosto pesa (artista bem visto sobe,
    mal visto quase some) e a `curiosidade` (0 a 1, do humor dele) dá chance a artistas que ele não conhece.
    """
    tocadas = set(tocadas)
    livres = [f for f in faixas if f.video_id not in tocadas and f.video_id not in gosto.banidas]
    if not livres:
        return None
    pesos = [math.exp(0.9 * gosto.nota(f)) * (1.0 + 1.5 * curiosidade * (not gosto.conhece(f))) for f in livres]
    return sorteio.choices(livres, weights=pesos, k=1)[0]


def semente(faixas, gosto, tocadas):
    """De qual música puxar o próximo rádio: a mais bem vista do que já tocou (ou None)."""
    ouvidas = [f for f in faixas if f.video_id in set(tocadas) and f.video_id not in gosto.banidas]
    return max(ouvidas, key=gosto.nota, default=None)


# ---------------- YouTube Music ----------------

def _segundos(texto):
    """'3:25' -> 205; '1:02:03' -> 3723; vazio ou ruim -> 0."""
    try:
        total = 0
        for parte in str(texto or "").split(":"):
            total = total * 60 + int(parte)
        return total
    except ValueError:
        return 0


def faixa_de(item):
    """Um resultado do ytmusicapi vira Faixa (None se faltar o id ou a duração não servir)."""
    if not isinstance(item, dict) or not item.get("videoId"):
        return None
    duracao = item.get("duration_seconds") or _segundos(item.get("length") or item.get("duration"))
    if duracao and not DURACAO_MIN <= duracao <= DURACAO_MAX:
        return None
    artistas = tuple(a["name"] for a in item.get("artists") or [] if isinstance(a, dict) and a.get("name"))
    return Faixa(item["videoId"], str(item.get("title") or "?"), artistas, int(duracao or 0))


def _ytmusic():
    """Cliente do YouTube Music (sem login: só busca e rádio)."""
    try:
        from ytmusicapi import YTMusic
    except ImportError as erro:
        raise ErroMusica(INSTALAR) from erro
    return YTMusic()                            # em pt a busca filtrada volta vazia: o padrão (en) acha tudo


def buscar(estilo, cliente=None):
    """Músicas do estilo; sem estilo, um pop brasileiro. Levanta ErroMusica se nada der certo."""
    try:
        resultados = (cliente or _ytmusic()).search(estilo or "pop brasil", filter="songs", limit=25)
    except ErroMusica:
        raise
    except Exception as erro:                   # rede, YouTube mudou o formato...
        raise ErroMusica(f"o YouTube Music não respondeu ({type(erro).__name__})") from erro
    faixas = [f for f in map(faixa_de, resultados) if f]
    if not faixas:
        raise ErroMusica(f"não achei músicas de {estilo!r}")
    return faixas


def radio(video_id, cliente=None):
    """Músicas parecidas com `video_id` (o rádio do YouTube Music); lista vazia se não deu."""
    try:
        dados = (cliente or _ytmusic()).get_watch_playlist(videoId=video_id, radio=True, limit=30)
    except ErroMusica:
        raise
    except Exception:
        return []
    return [f for f in map(faixa_de, dados.get("tracks") or []) if f and f.video_id != video_id]


def link_de_audio(video_id):
    """O link direto do áudio (m4a de preferência: o Qt toca sem problema). Expira em algumas horas."""
    try:
        import yt_dlp
    except ImportError as erro:
        raise ErroMusica(INSTALAR) from erro
    opcoes = {"format": "bestaudio[ext=m4a]/bestaudio", "quiet": True, "no_warnings": True,
              "noplaylist": True, "skip_download": True}
    try:
        with yt_dlp.YoutubeDL(opcoes) as ydl:
            info = ydl.extract_info(f"https://music.youtube.com/watch?v={video_id}", download=False)
    except Exception as erro:
        raise ErroMusica(f"não consegui o áudio dessa música ({type(erro).__name__})") from erro
    if not info or not info.get("url"):
        raise ErroMusica("o YouTube não devolveu o áudio dessa música")
    return info["url"]
