"""
CONFIG - caminhos, permissões da sessão, perfis de tempo e pets.

Tudo o que o usuário escolhe na tela inicial mora em memory/permissions.json (ver paths.py)
e é gravado a CADA mudança (se o programa cair, a escolha não se perde).
"""

import random

from .ia.chaves import parece_chave
from .paths import pet_id_valido
from .store import read_json, read_lines, write_json

EMOTIONS = ["feliz", "contente", "observando", "curioso", "bravo", "triste", "assustado", "dramatico"]

EMOTION_NAMES = {
    "feliz": "FELIZ",
    "contente": "CONTENTE",
    "observando": "OBSERVANDO",
    "curioso": "CURIOSO",
    "bravo": "BRAVO",
    "triste": "TRISTE",
    "assustado": "ASSUSTADO",
    "dramatico": "DRAMÁTICO",
    "dormindo": "DORMINDO",
}

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}

PANIC_HOTKEY_TEXT = "Ctrl + Alt + Shift + B"
PTT_HOTKEY_TEXT = "Ctrl + Alt + Shift + V"     # segurar para falar com ele (macOS/Linux: aperta e aperta de novo)

# ============================================================
# PERMISSÕES
# ============================================================

DEFAULT_PERMISSIONS = {
    "ativo": True,             # False depois do pânico, até religar na tela inicial
    "pet": "bryan",
    "travessuras": False,      # interruptor mestre de memes/fotos/bilhetes
    "memes": True,
    "fotos": False,
    "bilhetes": True,
    "cutucar": True,
    "carinho": True,           # esfregar o mouse nele = carinho, e ele aprende com isso
    "arrastar": True,
    "pousar_janelas": True,
    "tela_cheia": False,       # experimental: aparecer em jogo/vídeo/apresentação
    "rotina": True,            # grava a timeline por minuto (só categorias) para o LSTM
    "modo_teste": False,       # desligado por padrão: o modo teste é só para desenvolvimento
    "mostrar_emocao": False,   # só vale com modo_teste ligado
    "bolinha": True,           # a bolinha para ele brincar
    "fogos": True,             # fogo de artifício quando ele fica feliz de verdade (rede)
    "ia": False,               # interruptor mestre da IA: sem ele, nada sai do computador
    "ver_tela": False,         # print da tela + título da janela vão para o modelo de IA
    "comentarios": True,       # ele comenta em balão o que vê (só com ver_tela)
    "jogos": False,            # em jogo, ele olha bem mais seguido para acompanhar a partida (só com ver_tela)
    "estudar_jogos": False,    # lê sobre o jogo (Wikipédia, só o nome) e segue seu progresso sem spoiler (só com jogos)
    "desenhar": True,          # ele pode desenhar por cima da tela para mostrar algo (só com ver_tela)
    "videos": False,           # ouve o som do computador num vídeo, fica quieto e depois resume (precisa de ia)
    "conversa": True,          # chat por texto pelo menu do pet
    "historico_chat": True,    # guarda o que você pediu e as respostas inteiras, para rever no chat (só aqui)
    "pesquisar": False,        # "Conectar ao Hermes": o chat passa por ele (pesquisa, memória) e ele pesquisa o que vê na tela
    "hermes_url": "",          # onde está a API do Hermes; vazio: este computador, porta 8642
    "ia_provedor": "claude",   # claude, openai, deepseek ou ollama (ver ia/provedores.py)
    "ia_modelo": "",           # vazio: o modelo padrão do provedor
    "ia_modelos": {},          # o último modelo de cada provedor: trocar e voltar não perde o que estava
    "ia_ollama_url": "",       # vazio: o Ollama deste computador; ou outro PC da rede (ex.: 192.168.0.10)
    "voz": False,              # sua fala vira texto (só com a tecla ou o botão do microfone); precisa de ia e conversa
    "voz_url": "",             # serviço de voz (servidor/voz/); vazio: este computador, porta 11500
    "chamar": False,           # microfone aberto esperando o nome dele (detecção local, Vosk); precisa de voz
    "chamado_palavra": "",     # a palavra de chamado; vazio: o nome do pet
    "lembrar": False,          # grava o resumo do que a IA viu (nunca o print nem o título), por computador
    "memoria_compartilhada": False,   # sincroniza o pet com o serviço de memória (servidor/memoria/)
    "memoria_url": "",         # onde está o serviço de memória (ex.: 192.168.0.10); vazio: desligado
}

# (chave, rótulo, descrição) na ordem da tela inicial
PERMISSION_GROUPS = [
    ("Travessuras", [
        ("travessuras", "Travessuras", "Interruptor geral: sem ele, nada de memes, fotos ou bilhetes."),
        ("memes", "Trazer memes", "Imagens de pets/<pet>/memes/<emoção>/."),
        ("fotos", "Trazer fotos", "Imagens de assets/comum/fotos/."),
        ("bilhetes", "Deixar bilhetes", "Post-its com frases de pets/<pet>/recadinhos.txt."),
    ]),
    ("Interação", [
        ("cutucar", "Cutucar", "Clicar nele é uma cutucada, e ele reage."),
        ("carinho", "Carinho e aprendizado",
         "Passar o mouse para lá e para cá em cima dele é carinho. Ele aprende a gostar "
         "do que estava acontecendo quando ganhou carinho (e a desgostar de ser dispensado)."),
        ("arrastar", "Arrastar e arremessar", "Segurar, girar com a rodinha e jogar longe."),
        ("pousar_janelas", "Pousar em janelas", "Solto no ar, ele pode cair em cima da barra de título."),
    ]),
    ("Contexto", [
        ("tela_cheia", "Aparecer em tela cheia (experimental)",
         "Por padrão ele some em jogos, vídeos e apresentações."),
    ]),
    ("Rotina", [
        ("rotina", "Aprender minha rotina",
         "Grava 1 linha por minuto em memory/timeline.csv: hora, categoria de atividade, "
         "trocas de programa, ocioso. Nunca títulos, sites ou conteúdo."),
    ]),
    ("Brincadeira", [
        ("fogos", "Fogos de artifício", "Quando ele fica muito feliz, a alegria da rede pode soltar um fogo."),
        ("bolinha", "Bolinha", "Uma bolinha para ele brincar. Se você levar para longe, ele reage (pode ficar triste, bravo ou ir atrás)."),
    ]),
    ("Visão e conversa (IA)", [
        ("ia", "Usar IA",
         "Interruptor geral. Liga a conversa e a visão por um modelo de IA (Claude, OpenAI, DeepSeek ou "
         "Ollama local). Com Claude, OpenAI ou DeepSeek, o que ele vê e o que você escreve vai para a API."),
        ("ver_tela", "Ver minha tela",
         "De tempos em tempos ele tira um print da tela e lê o título da janela ativa, e manda para o modelo "
         "descrever o que você está fazendo. O print não é gravado em disco."),
        ("comentarios", "Comentar o que vê", "Às vezes ele comenta num balãozinho o que você está fazendo."),
        ("jogos", "Acompanhar jogos",
         "Quando você está jogando, ele olha a tela bem mais seguido (com o Ollama, a cada poucos segundos; "
         "com uma API paga, mais devagar, por causa do custo) para perceber itens, conquistas e jogadas e "
         "comentar. Se a tela quase não mudou, ele não manda o print. Enquanto você joga, ele vai para o "
         "monitor da direita (com um monitor só, para o canto de baixo) e fica parado lá assistindo e "
         "comentando, sem passear nem aprontar; a tela cheia do jogo não esconde ele no outro monitor. Com um "
         "monitor só, para ele aparecer por cima do jogo, ligue também \"Aparecer em tela cheia\" e jogue em "
         "janela sem borda."),
        ("estudar_jogos", "Estudar os jogos (sem spoiler)",
         "Quando ele percebe qual jogo você está jogando (pela tela ou pelo título da janela), procura o jogo "
         "na Wikipédia (vai só o nome do jogo) e o modelo de IA resume a premissa, as mecânicas, dicas e a "
         "história inteira em trechos; sem artigo, com o Hermes conectado, ele pesquisa. Fica guardado em "
         "memory/pets/<pet>/jogos.json, junto com onde ele te viu no jogo (capítulo, área, missão). A cada "
         "lugar novo, ele descobre em que parte da história você está: a história só vai para o modelo até "
         "ali, então ele não dá spoiler. No chat, peça \"pode dar spoiler\" ou \"como termina?\" para ele "
         "contar o resto. Só com \"Acompanhar jogos\"."),
        ("desenhar", "Desenhar na tela",
         "Quando quer te mostrar algo que está na tela (um erro, um botão, algo que chamou a atenção dele), ele "
         "rabisca um círculo, um quadrado, uma seta ou um ícone por cima, por alguns segundos. Peça no chat: "
         "\"me mostra onde fica o botão de salvar\". O desenho não recebe clique e some sozinho (ou quando "
         "você mexe nele). Só com \"Ver minha tela\"."),
        ("videos", "Assistir vídeos comigo",
         "Peça \"assiste esse vídeo comigo\" (ou pelo menu; com \"Ver minha tela\", ele percebe sozinho quando "
         "você está vendo uma aula, tutorial ou podcast): ele ouve o som do computador, fica quietinho "
         "prestando atenção e, quando o vídeo acaba (ou você pede \"resume o vídeo\"), resume e guarda o que "
         "aprendeu em memory/pets/<pet>/conhecimento.jsonl, para conversar sobre isso depois. O áudio vai para "
         "o serviço de voz (o mesmo de \"Falar com ele\") e o texto ouvido vai para o modelo de IA; nenhum dos "
         "dois é gravado, só o resumo."),
        ("pesquisar", "Conectar ao Hermes (pesquisa e memória)",
         "O chat e a voz passam pelo Hermes: ele responde como o pet, pesquisa na internet quando precisa e "
         "vai aprendendo sobre você (a memória dele é a mesma em todos os seus computadores). Se o Hermes "
         "cair, o provedor de IA responde no lugar. Quando algo na tela chama a atenção (um jogo, um item, "
         "um erro), ele também pesquisa sozinho e te dá uma dica no balão. Peça \"pesquisa o que é manga\" e "
         "ele projeta uma imagem como holograma. Vai para o Hermes a conversa, o resumo do que você está "
         "fazendo e o estado do pet; nunca o print nem o título da janela."),
        ("conversa", "Conversar por texto", "Botão direito nele, Conversar: você escreve e ele responde."),
        ("historico_chat", "Guardar o histórico do chat",
         "O que você pediu (escrito ou falado) e as respostas inteiras, sem o corte do balão, ficam em "
         "memory/pets/<pet>/historico_chat.jsonl e aparecem quando você abre o chat. Só neste computador: "
         "não vai para a IA nem para a memória compartilhada. O botão Esquecer, no chat, apaga."),
        ("voz", "Falar com ele (voz para texto)",
         f"Segure {PTT_HOTKEY_TEXT} e fale, ou use o botão de microfone do chat: a sua fala vira texto e ele "
         "responde por escrito. Ele só ouve enquanto você aperta. O áudio vai para o serviço de voz do "
         "endereço abaixo (o seu servidor) e não é gravado."),
        ("chamar", "Chamar pelo nome (como a Alexa)",
         "O microfone fica aberto e um reconhecedor pequeno, rodando só neste computador, espera a palavra de "
         "chamado (o nome dele, ou a que você escrever abaixo). Diga \"Bob, que horas são?\" ou só \"Bob\" e, "
         "quando a orelha dele levantar, faça o pedido. Até ouvir o nome, nada sai do computador e nada é "
         "gravado; depois, só o seu pedido vai para o serviço de voz. Na primeira vez baixa o modelo de "
         "português do Vosk (31 MB, alphacephei.com) para memory/modelos/."),
        ("lembrar", "Lembrar o que viu",
         "Grava o resumo curto do que a IA viu (até 12 palavras) e o nome do programa, com a hora e o "
         "computador, em memory/pets/<pet>/lembrancas_<computador>.jsonl. Nunca o print, o título da "
         "janela nem o que ele comentou. Com a memória compartilhada, ele lembra num computador do que viu "
         "no outro (e pode te perguntar como ficou)."),
    ]),
    ("Memória em outro computador", [
        ("memoria_compartilhada", "Compartilhar a memória dele",
         "O mesmo pet em todos os seus computadores: a rede, a memória, o humor e a personalidade (pets/<pet>.json) "
         "ficam também no serviço de memória (servidor/memoria/) de um computador da sua casa. Vale na "
         "próxima vez que abrir. Permissões, painéis e rotina continuam de cada computador."),
    ]),
    ("Teste", [
        ("modo_teste", "Modo teste", "Tempos curtos: travessuras e emoções acontecem em segundos."),
        ("mostrar_emocao", "Mostrar nome da emoção", "Texto pequeno embaixo dele (só no modo teste)."),
    ]),
]


def permissoes_validas(novo):
    """Mantém só as chaves conhecidas e com o mesmo tipo do padrão; o modelo nunca guarda uma chave de API."""
    validas = {k: v for k, v in novo.items()
               if k in DEFAULT_PERMISSIONS and type(v) is type(DEFAULT_PERMISSIONS[k])}
    if parece_chave(validas.get("ia_modelo")):
        validas["ia_modelo"] = ""                  # chave colada no lugar do modelo: não grava
    if "ia_modelos" in validas:
        validas["ia_modelos"] = {p: m.strip()[:100] for p, m in validas["ia_modelos"].items()
                                 if isinstance(p, str) and isinstance(m, str) and not parece_chave(m)}
    return validas


def load_permissions(paths):
    """Lê as permissões salvas e completa as que faltam com o padrão (um arquivo antigo continua valendo)."""
    perms = dict(DEFAULT_PERMISSIONS)
    saved = read_json(paths.permissions, default=None)
    if isinstance(saved, dict):
        perms.update(permissoes_validas(saved))
    return perms


def save_permissions(paths, perms):
    """Grava as permissões em memory/permissions.json."""
    write_json(paths.permissions, perms, indent=1)


# ============================================================
# PERFIS DE TEMPO (segundos)
# ============================================================

PROFILES = {
    "teste": {
        "mischief_interval": (20.0, 45.0),
        "max_objects": 3,
        "emotion_tau": 1.5,          # quão rápido a emoção segue o cérebro
        "emotion_dwell": 0.6,        # tempo mínimo numa emoção
        "roam_interval": (2.0, 5.0),
        "drama_window": 15.0,
        "drama_count": 3,
        "away_after": 10.0,
        "righting_after": 3.0,       # tempo tombado antes de tentar levantar
        "learn_rate": 0.004,         # ~5 s de carinho já mudam uma associação
        "cond_rate": 0.12,           # condicionamento: ~10 repetições já criam a antecipação
        # homeostase (s): quanto dura cada reserva
        "energy_span": 300.0,        # acordado e parado, de cheio a vazio
        "sleep_recover": 60.0,       # dormindo, de vazio a cheio
        "stim_decay": 40.0,          # estimulação some sem nada acontecer
        "contact_span": 120.0,       # de satisfeito a carente sem interação
        # memória episódica
        "episode_ok": 45.0,          # objeto que fica isso na tela = aceito
        "episode_window": 15.0,      # janela para ver se a ação teve efeito
        "dismiss_patience": 30.0,    # fechar depois disso já não é tão ruim
        "explore": 0.25,             # chance de testar uma ação qualquer
        # protesto: raiva sustentada vira insatisfação
        "grievance_up": 45.0,        # raiva média de 0,4 chega à revolução em ~3,5 min
        "grievance_down": 420.0,     # ignorado, a insatisfação some em ~7 min
        "stage_up": [0.12, 0.4, 0.68, 1.0],  # reclamação, manifestação, greve, revolução
        "stage_dwell": 20.0,         # s mínimos em cada estágio antes de subir (teste)
        "sad_up": 30.0,              # tristeza: ~30 s de tristeza leva ao abandono (sozinho: ~5 min)
        "sad_down": 300.0,
        "sad_stage_up": [0.2, 0.5, 0.8, 1.0],
        "stage_hyst": 0.06,          # cartaz só some quando cai este tanto abaixo do limiar
        # visão (IA): quanto tempo entre uma olhada e outra
        "visao_intervalo": 25.0,     # s entre olhadas
        "visao_apos_troca": 8.0,     # s depois de você trocar de programa (se já deu o mínimo)
        "pesquisa_intervalo": 60.0,  # s mínimos entre uma pesquisa na internet e outra
        "visao_jogo": 4.0,           # s entre olhadas em jogo, com o Ollama ("Acompanhar jogos")
        "visao_jogo_nuvem": 20.0,    # s entre olhadas em jogo, com uma API paga
        "fala_jogo": 12.0,           # s mínimos entre um comentário e outro em jogo
        "video_silencio": 40.0,      # s sem som nenhum: o vídeo acabou (ou foi pausado) e ele resume
    },
    "normal": {
        "mischief_interval": (300.0, 900.0),
        "max_objects": 3,
        "emotion_tau": 5.0,
        "emotion_dwell": 1.5,
        "roam_interval": (6.0, 15.0),
        "drama_window": 15.0,
        "drama_count": 3,
        "away_after": 60.0,
        "righting_after": 8.0,
        "learn_rate": 0.001,
        "cond_rate": 0.03,
        "energy_span": 3 * 3600.0,
        "sleep_recover": 20 * 60.0,
        "stim_decay": 240.0,
        "contact_span": 40 * 60.0,
        "episode_ok": 300.0,
        "episode_window": 30.0,
        "dismiss_patience": 60.0,
        "explore": 0.1,
        "grievance_up": 1800.0,      # ~1 h de provocação até a revolução
        "grievance_down": 3600.0,
        "stage_up": [0.25, 0.5, 0.75, 1.0],
        "stage_dwell": 120.0,        # s mínimos em cada estágio antes de subir (normal)
        "sad_up": 2400.0,            # tristeza: ~40 min sozinho ou triste leva ao abandono
        "sad_down": 5400.0,
        "sad_stage_up": [0.25, 0.5, 0.75, 1.0],
        "stage_hyst": 0.12,
        "visao_intervalo": 150.0,    # ~2,5 min entre olhadas: o custo da API fica baixo
        "visao_apos_troca": 45.0,
        "pesquisa_intervalo": 120.0,     # no máximo uma pesquisa espontânea a cada 2 min
        "visao_jogo": 8.0,           # Ollama: ~0,7 s por olhada no gemma4:e4b, sobra placa para o jogo
        "visao_jogo_nuvem": 60.0,    # API paga: ~1 olhada por minuto em jogo
        "fala_jogo": 45.0,           # olhar rápido não é falar sem parar
        "video_silencio": 240.0,     # 4 min sem som: pausa curta não encerra o vídeo
    },
}


def check_assets(conteudo):
    """Lista o que falta no conteúdo do pet (pets/<pet>/ ou assets/comum/), para avisar em vez de quebrar."""
    warnings = []
    pasta = _relativo(conteudo.proprio)
    if not conteudo.memes.exists():
        warnings.append(f"sem pasta memes/ em {pasta} nem em assets/comum/: sem memes")
    elif not any(list_images(conteudo.memes / e) for e in EMOTIONS):
        warnings.append(f"a pasta {_relativo(conteudo.memes)} está vazia: sem memes")
    if not conteudo.notes.exists():
        warnings.append(f"sem recadinhos.txt em {pasta}: sem post-its")
    if not conteudo.signs.exists():
        warnings.append(f"sem cartazes.txt em {pasta}: usando frases neutras")
    return warnings


def _relativo(caminho):
    """Caminho curto para mensagens: só as duas últimas partes da pasta, com a barra no fim."""
    return "/".join(caminho.parts[-2:]) + "/"


def profile(perms):
    """Tempos do pet para o modo escolhido: 'teste' é acelerado, 'normal' é o real."""
    return PROFILES["teste" if perms.get("modo_teste") else "normal"]


# ============================================================
# PETS
# ============================================================

APP_NOME = "Pestinha"             # o programa; cada personagem tem o próprio nome (pets/<pet>.json)
PET_PADRAO = "bryan"

DEFAULT_PET = {
    "nome": None,                       # sem nome no .json: o id com inicial maiúscula
    "seed": 7,
    "brincadeira": {"bola": 1.0, "arremesso": 0.6, "postit": 0.5},   # pesos: 0 desliga
    "temperamento": {},
    "reacao_notebook": "bravo",         # o que sente se arrancarem o notebook: "bravo" ou "triste"
    "persona": None,                    # como ele fala com a IA (texto livre); sem isso, a persona padrão
    "exemplos": [],                     # falas que mostram o jeito dele (a IA pega o tom, não copia)
    "evitar": [],                       # frases batidas que ele nunca deve dizer
}


def list_pets(paths):
    """Os personagens são os pets/<id>.json com id válido. Pasta de memória não cria personagem."""
    if not paths.pets.exists():
        return [PET_PADRAO]
    names = sorted(p.stem for p in paths.pets.glob("*.json") if pet_id_valido(p.stem))
    return names or [PET_PADRAO]


def escolher_pet(paths, pedido):
    """O pet salvo, se ainda existir; senão o padrão (ou o primeiro que houver)."""
    pets = list_pets(paths)
    if pedido in pets:
        return pedido
    return PET_PADRAO if PET_PADRAO in pets else pets[0]


def _numero_ok(valor, minimo=0.0):
    """Diz se o valor é um número finito e não negativo (ou maior que `minimo`)."""
    return (type(valor) in (int, float) and valor == valor and valor not in (float("inf"),)
            and valor >= minimo)


def _pet_valido(saved):
    """Só os campos do tipo certo entram; o resto fica com o padrão."""
    out = {}
    if isinstance(saved.get("nome"), str) and saved["nome"].strip():
        out["nome"] = saved["nome"]
    if type(saved.get("seed")) is int and saved["seed"] >= 0:
        out["seed"] = saved["seed"]
    brinc = saved.get("brincadeira")
    if isinstance(brinc, dict) and all(isinstance(k, str) and _numero_ok(v) for k, v in brinc.items()):
        out["brincadeira"] = dict(brinc)
    temp = saved.get("temperamento")
    if isinstance(temp, dict) and all(isinstance(k, str) and _numero_ok(v) for k, v in temp.items()):
        out["temperamento"] = dict(temp)
    if saved.get("reacao_notebook") in ("bravo", "triste"):
        out["reacao_notebook"] = saved["reacao_notebook"]
    if isinstance(saved.get("persona"), str) and saved["persona"].strip():
        out["persona"] = saved["persona"].strip()[:2000]
    for campo in ("exemplos", "evitar"):
        lista = saved.get(campo)
        if isinstance(lista, list):
            out[campo] = [t.strip()[:200] for t in lista if isinstance(t, str) and t.strip()][:12]
    if isinstance(saved.get("aparencia"), dict):
        out["aparencia"] = dict(saved["aparencia"])    # cores e acessórios: validados em body/desenho_rosto.py
    return out


def load_pet(paths, name):
    """Carrega o personagem: pets/<pet>.json sobre o padrão, com o nome e o id."""
    pet = dict(DEFAULT_PET)
    saved = read_json(paths.definicao(name), default=None)
    if isinstance(saved, dict):
        pet.update(_pet_valido(saved))
    pet["id"] = name
    if not pet["nome"]:
        pet["nome"] = name.capitalize()
    return pet


# ============================================================
# ASSETS
# ============================================================


def list_images(folder):
    """Imagens (png, jpg, gif, webp, bmp) de uma pasta; pasta inexistente vira lista vazia."""
    if not folder.exists():
        return []
    return [p for p in folder.iterdir() if p.suffix.lower() in IMAGE_EXT]


def meme_for(memes_dir, emotion):
    """Meme da pasta da emoção; se vazia, de qualquer emoção da mesma pasta (do mesmo pet); se nada, None."""
    own = list_images(memes_dir / emotion)
    if own:
        return random.choice(own)
    every = [img for e in EMOTIONS for img in list_images(memes_dir / e)]
    return random.choice(every) if every else None


def random_photo(fotos_dir):
    """Uma foto ao acaso da pasta de fotos, ou None se não houver."""
    photos = list_images(fotos_dir)
    return random.choice(photos) if photos else None


class Notes:
    """Frases de recadinhos.txt (uma por linha, # é comentário). Relê se o arquivo mudar."""

    def __init__(self, path):
        """Post-its de um arquivo de texto (uma frase por linha), relidos quando o arquivo muda."""
        self.path = path
        self.mtime = None
        self.lines = []
        self.last = None

    def _reload(self):
        """Relê o arquivo só se a data de modificação mudou (assim dá para editar com o pet aberto)."""
        try:
            mtime = self.path.stat().st_mtime
        except OSError:
            self.lines = []
            return
        if mtime == self.mtime:
            return
        self.mtime = mtime
        self.lines = [
            line.strip() for line in read_lines(self.path)
            if line.strip() and not line.lstrip().startswith("#")
        ]

    def has_lines(self):
        """Diz se há algum post-it disponível."""
        self._reload()
        return bool(self.lines)

    def pick(self):
        """Um post-it ao acaso, sem repetir o último quando há outros."""
        self._reload()
        if not self.lines:
            return None
        options = [l for l in self.lines if l != self.last] or self.lines
        self.last = random.choice(options)
        return self.last
