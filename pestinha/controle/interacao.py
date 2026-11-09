"""
INTERAÇÃO - o que você faz com o pet: cutucar, arrastar, arremessar, dispensar travessuras,
os comandos do menu do botão direito e o notebook.

Cada interação vira sinal para a rede (sentidos), homeostase, condicionamento e memória.
Pausado ou desligado, as interações não mexem no estado (ver SessaoMixin._congelado).
Mixin de PestinhaApp: usa os atributos criados em PestinhaApp.__init__.
"""

from ..log import log
import time
from PySide6.QtWidgets import QMenu
from .. import multimidia
from ..body.pet import cursor_pos
from ..ia.musica import comando_de_musica, pedido_de_musica, volume_pedido
from ..ia.video import pedido_de_video
from ..ui.conversa import ConversaJanela
from ..ajustes import (
    ALIVIO_CONVERSA,
    DURACAO_RECOMPENSA_CONVERSA,
    INSATISFACAO_NOTEBOOK,
    COOLDOWN_CUTUCADA as POKE_COOLDOWN,
    ESPERA_MEDIDA_CUTUCADA as POKE_PROBE,
    HZ_RESPOSTA_CHEIA as POKE_FULL_HZ,
    RESPOSTA_MINIMA as POKE_MIN_RESPONSE,
)


class InteracaoMixin:
    """Ações do usuário sobre o pet: cutucar, arrastar, arremessar, dispensar travessuras e o menu do botão direito. Vira atributo de PestinhaApp."""
    def on_poke(self):
        """Você cutucou o pet: ele reage e a rede recebe o toque (ignorado na pausa)."""
        self.fechar_projecao()
        if self._congelado():
            return
        now = time.monotonic()
        if now - self.last_poke < POKE_COOLDOWN:
            return
        self.sad.grievance = max(0.0, self.sad.grievance - 0.25)     # cutucar alegra um pouco
        self.last_poke = now
        self.conditioning.outcome(now)
        self.senses.poke()
        self.timeline.note_interaction()
        self.drives.stimulate("poke")
        self.drives.touched("poke")
        self.memory.on_interaction()
        if self.asleep:
            self.sleep.wake(startled=True)
        # a reação NÃO é fixa: mede-se o que a rede fez com a cutucada (ver poke_reflex)
        self.poke_probe = (now + POKE_PROBE, self.brain.motor_activity()["CHEER"])

    def poke_reflex(self, delta_hz):
        """
        Tamanho da reação = aumento real de CHEER causado pela cutucada.
        Com cutucadas repetidas a sinapse de POKE habitua e a resposta encolhe:
        pulo grande, pulo menor, só os olhos, quase nada. Volta depois de minutos.
        """
        self.poke_probe = None
        response = max(0.0, min(1.0, delta_hz / POKE_FULL_HZ))
        if self.protest.stage == 3:
            response *= 0.2                         # em greve: mal responde
        self.last_poke_response = response
        body = self.pet.body
        if response >= POKE_MIN_RESPONSE and body.grounded:
            body.jump(0.0, -(150.0 + 650.0 * response))
        else:
            self.pet_state.blink_until = time.monotonic() + 0.13       # só pisca e olha
            cx, cy = cursor_pos()
            self.behavior.look_at(cx, cy, time.monotonic())
        if self.debugging():
            eff = self.brain.efficacy()["POKE"]
            log(f"[cutucada] resposta da rede {response:.2f} "
                  f"(+{delta_hz:.1f} Hz em CHEER, eficácia POKE {eff:.2f})")

    def on_drag_started(self):
        """Você pegou o pet: ele sente o arraste e a insatisfação baixa um pouco (você está interagindo)."""
        self.fechar_projecao()
        if self._congelado():
            return
        self.sad.grievance = max(0.0, self.sad.grievance - 0.1)
        self.conditioning.outcome(time.monotonic())
        self.senses.set_dragging(True)
        self.timeline.note_interaction()
        self.drives.stimulate("drag")
        self.drives.touched("drag")
        self.memory.on_interaction()
        if self.asleep:
            self.sleep.wake(startled=True)

    def on_thrown(self, speed):
        """Você arremessou o pet: a velocidade vira intensidade do arremesso; ele não aprende com isso na pausa."""
        if self._congelado():
            return
        self.conditioning.outcome(time.monotonic())
        self.senses.thrown(min(1.0, speed / 2000.0))
        self.timeline.note_interaction()
        self.drives.stimulate("throw")
        self.drives.touched("throw")
        self.in_flight = True

    def on_dismissed(self, thing, elapsed):
        """Você dispensou uma travessura: ela some, e o tempo até você fechar vira aprendizado (fechar rápido é pior)."""
        if self._congelado():
            return                                   # o objeto some, mas não vira aprendizado na pausa
        self.mischief_ctl.on_dismissed(thing, elapsed, self.prof, time.monotonic())

    def arrancar_notebook(self, now):
        """Arrancaram o notebook dele: ele levanta e fica bravo ou triste, conforme o pet."""
        self.mesa.levantar_arrancado(now)
        self.senses.dismissed()                    # a dispensa entra na rede como frustração
        alvo = self.sad_ctl if self.reacao_notebook == "triste" else self.protest_ctl
        alvo.provoke(INSATISFACAO_NOTEBOOK, "arrancaram o meu notebook")
        if self.debugging():
            log(f"[notebook] arrancado: reação {self.reacao_notebook}")

    def show_pet_menu(self, pos):
        """Mostra o menu do botão direito no pet; cada item fica desativado se não fizer sentido agora."""
        menu = QMenu()
        perms = self.perms

        def item(text, fn, enabled=True):
            """Cria um item do menu; `enabled=False` deixa o item visível mas sem ação."""
            act = menu.addAction(text)
            act.setEnabled(enabled)
            act.triggered.connect(fn)

        item("Cutucar", self.menu_poke, perms["cutucar"])
        item("Dar carinho", self.menu_caress, perms["carinho"])
        menu.addSeparator()
        item("Jogar a bolinha perto dele", self.menu_place_ball, perms["bolinha"])
        item("Guardar a bolinha", self.menu_store_ball, perms["bolinha"] and not self.ball_stored)
        menu.addSeparator()
        item("Pedir para dormir", self.menu_sleep, not self.asleep)
        item("Pedir para trabalhar", self.menu_pedir_trabalho)
        item("Mostrar o notebook" if self.mesa.escondido else "Esconder o notebook",
             self.menu_alternar_notebook)
        item("Fazer uma travessura agora", self.menu_mischief, perms["travessuras"])
        menu.addSeparator()
        item("Conversar...", self.menu_conversar, perms["ia"] and perms["conversa"])
        item("O que você está vendo?", self.visao.olhar_agora,
             perms["ia"] and perms["ver_tela"] and not self.visao.olhando)
        if self.video.ativo:
            item("Parar e resumir o vídeo", lambda: self._mostrar_fala(self.video.parar(por_voce=True)))
        else:
            item("Assistir o vídeo comigo", self.menu_assistir_video,
                 perms["ia"] and perms["videos"] and not self.video.ocupado())
        if self.musica.ativa():
            item("Pular a música", lambda: self._comando_do_cartao("pular"))
            item("Parar a música", lambda: self._comando_do_cartao("parar"))
        menu.addSeparator()
        item("Cantinho do castigo", lambda: self.castigo.toggle(self.bounds()))
        item("Painel de protesto", lambda: self.floats.toggle("greve"))
        item("Monitor neural", lambda: self.floats.toggle("neural"))
        item("Configurações...", self.open_settings)
        menu.addSeparator()
        item("Esconder (volta pela bandeja)", self.toggle_hidden)
        item("Fechar", self.menu_close)
        menu.exec(pos)

    def menu_poke(self):
        """Menu: 'Cutucar' (ignora o intervalo mínimo entre cutucadas)."""
        self.last_poke = 0.0
        self.on_poke()

    def menu_caress(self):
        """Menu: 'Fazer carinho' (conta como carinho na rede, se não estiver pausado)."""
        self.fechar_projecao()
        if self._congelado():
            return
        self.pet_state.mark_caress()
        self.drives.touched("caress")
        self.memory.on_interaction()
        self.timeline.note_interaction()

    def menu_place_ball(self):
        """Menu: 'Pôr a bolinha' (coloca a bolinha perto do pet, no chão)."""
        self.ball_stored = False
        self.ball.body.x = self.pet.body.x + 130
        self.ball.body.y = self.bounds()[3] - 40
        self.ball.body.vx = self.ball.body.vy = 0.0
        self.update_visibility()

    def menu_store_ball(self):
        """Menu: 'Guardar a bolinha' (some com a bolinha até você pedir de novo)."""
        self.ball_stored = True
        self.update_visibility()

    def menu_sleep(self):
        """Menu: 'Dormir' (baixa a energia: ele cochila em vez de ficar acordado)."""
        if self._congelado():
            return
        self.drives.energy = min(self.drives.energy, 0.1)

    def menu_mischief(self):
        """Menu: 'Aprontar' (pede uma travessura agora)."""
        self.mischief_ctl.pedir(time.monotonic())

    def menu_alternar_notebook(self):
        """Menu: mostra ou esconde o notebook; sem o notebook, ele não pode sentar nele."""
        self.mesa.alternar_notebook()
        self.pet_state.at_desk = self.mesa.sentado
        if not self.mesa.sentado:
            self.pet_state.desk_top = None

    def menu_assistir_video(self):
        """Menu: 'Assistir o vídeo comigo' (ele ouve o som do computador e resume no fim)."""
        self._mostrar_fala(self.video.comecar())

    def _video_pelo_chat(self, texto):
        """
        'assiste esse vídeo comigo' começa; 'resume o vídeo' ou 'pode parar de assistir' termina e resume.
        Devolve o que ele responde, ou None se a mensagem não era sobre vídeo (ou a permissão está desligada).
        """
        if self._congelado() or not (self.perms["ia"] and self.perms["videos"]):
            return None
        resposta = self.video.responder_oferta(texto)      # "quer que eu assista com você?" -> "sim"
        if resposta is not None:
            return resposta
        pedido = pedido_de_video(texto)
        if pedido == "comecar":
            return self.video.comecar()
        if pedido == "parar":
            return self.video.parar(por_voce=True) or "Beleza!"
        return None

    def menu_conversar(self):
        """Menu: 'Conversar' (abre o chat por texto; a resposta aparece no chat e no balão)."""
        if self.conversa_janela is None:
            janela = ConversaJanela(self.nome)
            janela.enviar.connect(self._enviar_conversa)
            janela.esquecer.connect(self._esquecer_conversa)
            janela.microfone.connect(self.voz.alternar_microfone)
            self.voz.estado.connect(self.atualizar_microfone)
            if self.perms["historico_chat"]:
                janela.carregar(self.historico.ultimas())       # o que vocês conversaram antes
            self.conversa_janela = janela
        self.conversa_janela.set_aviso(self.visao.descricao())
        self.atualizar_microfone()
        self.conversa_janela.abrir()

    def on_double_click(self):
        """Dois cliques rápidos no pet: abre o chat, se a conversa estiver ligada em Configurações."""
        if self.perms["ia"] and self.perms["conversa"]:
            self.menu_conversar()

    def _no_chat(self, voce, texto, erro=False, voz=False):
        """Uma fala no chat (se a janela existe, mesmo escondida) e no histórico (se estiver ligado).
        `voce`: True para o que você disse, False para ele."""
        if self.conversa_janela is not None:
            self.conversa_janela.adicionar("Você" if voce else self.nome, texto, erro=erro, voz=voz)
        self._guardar_no_historico(voce, texto, erro, voz)

    def _guardar_no_historico(self, voce, texto, erro=False, voz=False):
        """Só o histórico (a janela já mostrou do jeito dela, como a imagem)."""
        if self.perms["historico_chat"] and not self.wiping:
            self.historico.adicionar("voce" if voce else "pet", texto, erro=erro, voz=voz)

    def _esquecer_conversa(self):
        """O botão Esquecer do chat: a IA esquece a conversa, e o histórico e o diário (que sai dele) são apagados."""
        self.visao.conversa.limpar()
        self.historico.apagar()
        self.diario.cancelar()
        self.diario.diario.apagar()
        self.memoria_local.apagar()

    def falaram_comigo(self):
        """
        Você escreveu ou falou com ele: isso é atenção, como um carinho. Vale na hora em que você fala
        (não só quando a IA responde, nem só quando é conversa: 'toca um lo-fi' também conta).
        A carência cai, o tédio diminui, a tristeza alivia e a rede recebe recompensa por uns segundos.
        """
        if self._congelado():
            return
        now = time.monotonic()
        self.sad.grievance = max(0.0, self.sad.grievance - ALIVIO_CONVERSA)
        self.drives.touched("conversa")
        self.drives.stimulate("conversa")
        self.senses.kick("CONVERSA", 0.8)
        self.timeline.note_interaction()
        self.memory.on_interaction()
        self.recompensa_conversa_ate = now + DURACAO_RECOMPENSA_CONVERSA
        if self.asleep:
            self.sleep.wake(startled=False)

    def _enviar_conversa(self, texto):
        """Você mandou uma mensagem: ele começa a pensar (ou explica por que não dá agora)."""
        self.falaram_comigo()
        self.chamado.pediu_em = 0.0                         # escreveu: a resposta não abre o microfone
        janela = self.conversa_janela
        janela.set_aviso(self.visao.descricao())
        self._no_chat(True, texto)
        resposta = self._video_pelo_chat(texto) or self._musica_pelo_chat(texto)
        if resposta:
            self._no_chat(False, resposta)
            self._mostrar_fala(resposta)
            return
        if self.visao.perguntar(texto):
            janela.set_ocupado(True)
        elif not self.visao.respondendo:
            motivo = ("a conversa está desligada em Configurações" if not (self.perms["ia"] and self.perms["conversa"])
                      else f"o {self.nome} está pausado ou desligado agora")
            self._no_chat(False, motivo, erro=True)

    def _ouvi(self, texto):
        """Você falou pelo atalho: vai para ele como se tivesse escrito no chat (a resposta vem no balão)."""
        self.falaram_comigo()
        janela = self.conversa_janela
        self._no_chat(True, texto, voz=True)
        resposta = self._video_pelo_chat(texto) or self._musica_pelo_chat(texto)
        if resposta:
            self.chamado.pediu_em = 0.0                     # um comando: feito, não precisa emendar
            self._no_chat(False, resposta)
            self._mostrar_fala(resposta)
            return
        if self.visao.perguntar(texto, por_voz=bool(self.chamado.pediu_em)):
            if janela is not None:
                janela.set_ocupado(True)
        elif not self.visao.respondendo:
            self._no_chat(False, f"o {self.nome} está pausado ou desligado agora", erro=True)

    def _musica_pelo_chat(self, texto):
        """
        'toca um lo-fi' começa uma playlist; com música tocando, 'pula', 'gostei', 'para'... viram comando.
        Devolve o que ele responde, ou None se a mensagem não era sobre música (aí vai para a IA).
        """
        if self._congelado() or not (self.perms["ia"] and self.perms["conversa"]):
            return None
        comando = comando_de_musica(texto) if self.musica.ativa() else None
        if comando:
            resposta = self.musica.comando(comando)
            self.tocando.atualizar(self.musica)
            return resposta
        volume = volume_pedido(texto, self.musica.volume) if self.musica.ativa() else None
        if volume is not None:
            return self.musica.mudar_volume(volume)          # "aumenta o volume", "volume 30", "mais baixo"
        estilo = pedido_de_musica(texto)
        if estilo is None:
            return None
        return self.tocar_musica(estilo)

    def tocar_musica(self, estilo):
        """Começa a playlist (pedida por você, ou escolhida pela IA na conversa) e diz o que vai tocar."""
        if not multimidia.disponivel():
            return "Não consigo tocar música aqui: falta o PySide6-Addons (pip install PySide6-Addons)."
        escolhido = self.musica.pedir(estilo)
        self.tocando.atualizar(self.musica)
        if estilo:
            return f"Bora de {estilo}! Procurando..."
        if escolhido:
            return f"Deixa comigo! Tô no clima de {escolhido}."
        return "Deixa comigo, vou puxar umas parecidas com as que você curtiu!"

    def _comando_do_cartao(self, comando):
        """Um botão do cartão 'tocando agora' (👍 👎 ⏭ ⏸ ✕)."""
        resposta = self.musica.comando(comando)
        self.tocando.atualizar(self.musica)
        if resposta and comando in ("gostei", "nao_gostei"):
            self._mostrar_fala(resposta)

    def atualizar_microfone(self):
        """O botão de microfone do chat segue a permissão de voz e o que a voz está fazendo."""
        if self.conversa_janela is not None:
            v = self.voz
            self.conversa_janela.set_microfone(v.ligada(), v.gravando == "chat", v.transcrevendo)

    def _ditado(self, texto):
        """Você falou pelo botão de microfone do chat: o texto cai no campo, para conferir e mandar."""
        if self.conversa_janela is not None:
            self.conversa_janela.ditar(texto)

    def _fim_conversa(self, texto, erro=False):
        """Resposta (ou falha) do chat, inteira: no chat (se a janela existe) e no histórico."""
        if self.conversa_janela is not None:
            self.conversa_janela.set_ocupado(False)
        self._no_chat(False, texto, erro=erro)

    def menu_pedir_trabalho(self):
        """Menu: 'Pedir para trabalhar' (ele pode aceitar, ou recusar com frustração)."""
        self.mesa.pedir(time.monotonic())
