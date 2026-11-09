# `pestinha/mind/`

> Gerado por `ferramentas/gerar_readmes.py` a partir das docstrings. Não edite à mão: rode o script.

Controladores de decisão: ligam o que a rede decide à cena (sono, mesa, protesto, travessuras, festa, revolução, cantinho do castigo, visão e conversa pela IA).

**Pode importar de:** core, ia, sense, body, world (e dos módulos compartilhados). A regra é verificada por `tests/test_arquitetura.py`.

| Arquivo | O que faz |
|---|---|
| `assistir.py` | Quando você está jogando, ele vai para o monitor ao lado e fica assistindo e comentando. |
| `castigo_ctl.py` | Uma plaquinha de cartoon que você arrasta para onde quiser. |
| `chamado_ctl.py` | Você chama ele pelo nome ("Bob!") e ele te ouve, como a Alexa (opcional, desligado por padrão: "Chamar pelo nome"). |
| `conhecimento.py` | O que ele aprendeu assistindo vídeos com você, guardado para conversar sobre isso depois. |
| `festa.py` | O fogo de artifício do pet feliz: a alegria da rede enche a euforia. |
| `historico.py` | O que você pediu (escrito ou falado) e o que ele respondeu, inteiro, para rever no chat ("Guardar o histórico do chat", ligado por padrão). |
| `jogo_ctl.py` | Com "Estudar os jogos", ele descobre o que você está jogando, lê sobre o jogo e acompanha até onde você chegou na história, para comentar a jogatina sem dar spoiler. |
| `jogos.py` | O que ele sabe de cada jogo que você joga e até onde você chegou (com "Estudar os jogos"). |
| `lembrancas.py` | O que ele viu você fazendo, em cada computador. |
| `mesa.py` | O computadorzinho do pet: sentar e levantar do notebook. |
| `mischief_ctl.py` | Quando e como ele apronta, e o que a dispensa causa. |
| `musica_ctl.py` | MÚSICA (controle) - toca a música que você pediu no chat e vai escolhendo as próximas. |
| `protest_ctl.py` | Liga o protesto (core/protesto.py) à cena: cartaz, estágio, repressão. |
| `revolucao.py` | As bolinhas de papel que o pet atira no cursor quando está em revolução. |
| `sincronia.py` | A rede neural e o modelo de IA falando a mesma língua. |
| `sleep.py` | Quando ele dorme, quando acorda, e o que acontece ao adormecer. |
| `video_ctl.py` | Ele assiste com você: ouve o som do computador, fica quieto prestando atenção e, no fim, resume e guarda o que aprendeu (opcional, desligado por padrão: "Assistir vídeos comigo"). |
| `visao.py` | O pet olha a sua tela e conversa com você por um modelo de IA (opcional, desligado por padrão). |
| `voz_ctl.py` | Você fala, e a sua fala vira texto para o pet (opcional, desligado por padrão). |
