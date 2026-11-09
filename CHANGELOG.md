# Histórico de versões

## Companheiro de jogo que entende do jogo

- **Comenta a jogabilidade, não o visual:** em jogo, ele fala da jogada, da build, do equipamento, da
  estratégia, da morte para o chefe, e sugere uma mecânica quando você se dá mal. Nada mais de "que
  atmosfera sombria" ou "que lugar bonito".
- **Estudar os jogos (sem spoiler):** opção nova em Configurações, abaixo de "Acompanhar jogos". Quando ele
  reconhece o jogo (pela tela ou pelo título, confirmado em duas olhadas), lê o artigo da Wikipédia (só
  o nome do jogo vai para lá) e a IA resume premissa, mecânicas, dicas e a história inteira em trechos,
  guardados em `memory/pets/<pet>/jogos.json`. Sem artigo, com o Hermes, ele pesquisa.
- **Sabe onde você está:** cada olhada diz onde você está no jogo (capítulo, área, missão); quando muda,
  ele descobre em que trecho da história isso fica, e o progresso só sobe. A história só vai para o
  modelo até ali, então ele não tem como dar spoiler. No chat, "pode dar spoiler" ou "como termina?"
  libera o resto.

## Histórico do chat

- **O chat guarda a conversa:** o que você pediu, escrevendo ou falando (com um 🎤), e as respostas dele
  inteiras ficam em `memory/pets/<pet>/historico_chat.jsonl` e aparecem quando você abre o chat, com a
  hora e a data. Também entram as falas pela voz com o chat fechado, os comandos de música e vídeo, os
  resumos dos vídeos e as imagens projetadas. Fica só neste computador (até 3000 falas). Opção nova em
  Configurações: "Guardar o histórico do chat", ligada por padrão.
- **Resposta inteira no chat:** o balão continua cortando em 160 caracteres, mas o chat e o histórico
  recebem a resposta completa, com as quebras de linha (listas e passo a passo).
- **Esquecer** pede confirmação e agora apaga também o histórico guardado.

## Conversa que emenda e vídeo com licença

- **Ele continua ouvindo depois de responder:** quando você chama ("Bob, como eu exporto isso?") e faz uma
  pergunta, ele responde, termina perguntando se você quer saber mais alguma coisa e fica com a orelha
  levantada por 8 s, sem precisar do nome. Dá para emendar outra pergunta e outra, até você ficar
  calado. Comandos ("toca uma música", "assiste comigo") não emendam.
- **Pergunta antes de assistir:** quando a olhada vê um vídeo na tela, ele ouve 2 s do som do computador.
  Sem som, o vídeo não está rodando e ele deixa quieto. Com som, ele pergunta "Quer que eu assista com
  você?" e espera o sim ou o não, pela voz (já ouvindo, sem precisar do nome) ou pelo chat. Um "não"
  deixa ele quieto por 20 min; sem resposta, ele esquece.
- **Assistindo, ele também olha:** com "Ver minha tela", ele olha a tela no ritmo de jogo (pulando quando
  quase nada mudou), não comenta e anota o que aparece (slides, código, cenas). Essas anotações vão junto
  para o resumo do vídeo.
- **O chamado não desliga mais durante o vídeo:** ele continua no microfone, separado do som do vídeo
  (que vem do loopback), e atende "Bob" mesmo assistindo. Com vídeo ou música tocando, só vale o nome
  dito bem claro (confiança 0,9), para a voz do vídeo não chamar ele por engano.

## Bob vira assistente de bordo

- **O Bob deixa de ser marrento e vira um assistente de bordo** (`pets/bryan.json`): educado, prestativo e
  com humor seco. Pergunta quando falta contexto, aponta erro ou risco com franqueza, pode discordar
  (uma vez, explicando o porquê) e sugere alternativas concretas. Respeita a decisão final e nunca mais
  pergunta se o que você faz "vai dar em algo".
- **A olhada na tela não manda mais questionar** "se é importante, no que vai dar" (vale para todos os
  pets): agora é interesse no assunto e, se ele vir um jeito melhor, uma sugestão em uma frase.

## Conversar também é carinho

- **Falar ou escrever com ele conta como atenção**, na hora em que você fala (atalho, chamado pelo nome ou
  chat), mesmo que a IA não responda e mesmo que seja só "toca um lo-fi": a carência cai bem (mais que uma
  cutucada), o tédio diminui, a tristeza acumulada alivia e a rede recebe ~2 s de recompensa, como num
  carinho, para ele associar a conversa a coisa boa. Antes só a resposta da IA contava, e pouco: conversando
  muito, ele ainda ficava triste como se ninguém desse atenção. Pausado ou em protesto de raiva, não ensina.
- O canal CONVERSA puxa mais contra a tristeza na rede (GLOOM -0,06 → -0,12).

## Player com o tempo da música e disquinho

- **A borda do cartão de música é a barra de progresso:** ela acende a partir do meio de cima, dá a volta
  no sentido horário e fecha a volta no fim da música, com uma pontinha brilhando onde a música está.
  Pausada, a ponta pulsa; carregando, um pedaço de borda fica dando voltas. Ao lado do rótulo, `1:23 / 3:45`.
- **Disquinho de vinil** no canto do cartão, girando a 33⅓ rpm: acelera quando toca e freia devagar quando
  você pausa, como um toca-discos. A capa da música (do YouTube Music, ou a do vídeo) vira o selo do disco.
- **🖼** ao lado do volume tira ou põe a capa; a escolha fica em `memory/panels.json`.
- A capa é baixada junto com o áudio, numa thread. Sem capa, o disco fica com o selo verde do pet e a
  música toca normalmente.

## Chamando pelo nome

- **Chamar pelo nome** (desligado por padrão; precisa de "Falar com ele"): como na Alexa, diga "Bob, que
  horas são?" ou só "Bob" e, quando a orelha levantar e ele disser "Hm?", faça o pedido. Um reconhecedor
  pequeno (Vosk) roda só neste computador e procura só a palavra de chamado; até ouvir o nome, nada sai do
  computador. Depois, o pedido vai para o serviço de voz como no atalho, e a resposta vem no balão
  (`ia/chamado.py`, `mind/chamado_ctl.py`).
- A palavra de chamado é o nome do pet ou a que você escrever em Configurações. O modelo em português não
  conhece "bob", então ele também tenta as grafias faladas ("bóbi"); palavras parecidas ("bola", "bom",
  "bobo") ficam na gramática como iscas, para não dispararem o chamado.
- Na primeira vez baixa o modelo de português do Vosk (31 MB) para `memory/modelos/`. Precisa de
  `pip install vosk`. Ele não atende enquanto assiste um vídeo com você, nem com o atalho de falar apertado.
- A dica do ícone da bandeja mostra 🎤 e a palavra enquanto o microfone espera o nome.
- **O Bryan agora se chama Bob.** O arquivo e a pasta continuam `pets/bryan.json` e `pets/bryan/`, e a
  memória continua em `memory/pets/bryan/`: ele não esquece nada, só mudou de nome.

## Assistindo vídeos com você e desenhando na tela

- **Assistir vídeos comigo** (desligado por padrão): peça "assiste esse vídeo comigo" no chat, na voz ou no
  menu; com **Ver minha tela**, ele também percebe sozinho quando você está numa aula, tutorial, palestra
  ou podcast. Ele ouve o som do computador (loopback, nunca o microfone), fica quietinho com a orelha para a
  frente (sem comentar o que vê) e manda cada pedaço de 20 s para o serviço de voz. Vídeo longo vira notas
  a cada ~10 min de fala, para nada crescer sem limite (`ia/video.py`, `mind/video_ctl.py`).
- Quando você pede ("resume o vídeo", "pode parar de assistir"), depois de 4 min de silêncio ou em 3 h, ele
  resume: fala no balão, o resumo completo aparece no chat e fica guardado em
  `memory/pets/<pet>/conhecimento.jsonl` (`mind/conhecimento.py`). Depois, no chat, ele lembra dos vídeos
  recentes e, se você perguntar de um deles, usa o resumo e os pontos. Com o Hermes, o resumo vai também para
  a memória dele; com a memória compartilhada, o arquivo vai para os outros computadores. Precisa de
  `pip install soundcard` (no macOS, de um driver de loopback como o BlackHole).
- **Desenhar na tela** (com **Ver minha tela**; resolve DevUnusual/pestinha#5): para te mostrar algo, ele
  rabisca um círculo, um quadrado, uma seta ou um ícone (! ? ★ ♥ 👀 ✓ ✗), com legenda, por cima do monitor
  que viu, por 9 s. Peça no chat ("me mostra onde fica o botão de salvar") ou deixe ele destacar sozinho o
  que comentou (um erro, um botão). O modelo responde em coordenadas de 0 a 1000 sobre o print
  (`ia/desenho.py`, `world/rabisco.py`). Não recebe clique; mexer nele apaga o desenho.

## Assistindo você jogar

- Com **Acompanhar jogos** e um jogo na tela, ele vai para o monitor mais à direita que não é o do jogo,
  perto da borda virada para a partida (com um monitor só, para o canto de baixo à direita), e fica parado
  lá olhando para o jogo e comentando no balão: sem passear, sem bolinha, sem travessuras e sem sentar no
  notebook (`mind/assistir.py`).
- Vai andando; se não der para chegar andando em 3 s (monitores desalinhados, ele em cima de uma janela),
  aparece direto no lugar.
- A tela cheia do jogo num monitor não esconde mais o pet que está assistindo de outro. Como o print é do
  monitor do jogo, ele também não aparece nos prints que a visão manda.
- Se você arrastar ele, ele fica onde você soltou por 20 s e depois volta para o lugar dele. Castigo e sono
  continuam passando na frente.

## Música e imagem que fica

- **Música pelo chat e pela voz:** "toca um lo-fi" (ou "quero ouvir samba", "coloca uma playlist de jazz")
  busca no YouTube Music e toca direto no Pestinha, sem conta e sem anúncio. Quando a fila acaba, ele puxa o
  rádio da música mais bem vista até ali, então a playlist vai mudando com o seu gosto e o humor dele
  (curioso, arrisca artistas novos). Precisa de `pip install yt-dlp ytmusicapi`.
- **Cartão "tocando agora"** ao lado do pet, com 👍 👎 ⏭ ⏸ ✕; no chat ou na voz valem "gostei", "não gostei",
  "pula", "pausa", "continua", "para". 👍 sobe o artista, 👎 bane a música e pula, pular sem opinião desce um
  pouco e ouvir até o fim sobe um pouco: não precisa fazer nada para ele aprender. O gosto fica em
  `memory/pets/<pet>/musica.json` (`ia/musica.py`, `mind/musica_ctl.py`, `world/tocando.py`).
- **Volume da música:** barra de volume no cartão "tocando agora" (🔇 🔈 🔉 🔊 e a porcentagem), e pelo chat
  ou pela voz com a música tocando: "aumenta o volume", "abaixa o som", "mais alto", "volume 30", "volume
  no máximo", "deixa no mudo". O volume fica guardado em `musica.json` e vale na próxima vez.
- **Reconhece qualquer jogo, não só os da lista:** é jogo o programa instalado numa biblioteca de jogos
  (Steam `steamapps/common`, Epic, GOG, Xbox, Ubisoft, EA, Riot, itch, Amazon) ou um executável do Unreal
  (`*-Win64-Shipping`). Phantom Blade Zero (`PBZ.exe`) não estava na lista e agora conta. Wallpaper Engine,
  launchers e instaladores ficam de fora.
- **Configurações à prova de rodinha:** as caixas de escolha (provedor, personagem, modelo) só mudam com a
  rodinha do mouse depois de clicadas; rolando a página por cima delas, a página rola e nada muda.
- **Cada provedor lembra o seu modelo** (`ia_modelos`): trocar de provedor sem querer e voltar traz de volta
  o modelo que estava.
- **Modelos do Ollama na lista:** o campo Modelo mostra os modelos instalados no servidor (`/api/tags`). Se
  nenhum foi escolhido e o padrão não está instalado lá, ele escolhe o recomendado (ou o primeiro) e avisa;
  se o escolhido não existe no servidor, avisa quais existem.
- **Ele entende o pedido do jeito que se fala:** "coloca uma musiquinha aí pra nós ouvir", "bota um som aí
  pra gente curtir", "solta um sonzinho", "toca o que você quiser". Sem estilo, ele escolhe: às vezes puxa
  parecidas com uma que você curtiu, às vezes um estilo do humor dele (bravo vai de rock pesado, curioso
  arrisca city pop ou afrobeat).
- **Se só a IA entender, ela dá o play:** o prompt agora diz que ele toca música de verdade e nunca deve
  pedir para você dar o play; quando você pede música de um jeito que o Pestinha não reconheceu, ela
  responde e termina com `TOCAR: <estilo>`, que vira a playlist. Rótulos que o modelo põe no começo da fala
  ("[Alerta de curiosidade]") saem do balão.
- **A música não corta mais no meio:** tocar direto do link do YouTube dava "Demuxing failed" quando o
  servidor derrubava a conexão. Agora o áudio é baixado inteiro antes (uns 2 s, ~3 MB, em
  `memory/cache/musica`, só a da vez) e, se mesmo assim cortar, ele recomeça uma vez de onde parou.
- **Ele lê o próprio log:** as últimas linhas (30 min, sem a depuração) vão junto com cada mensagem do
  chat, então ele consegue contar o que aconteceu ("cortou em 1:32 e eu recomecei"). A música que tocou, os
  👍/👎 e os cortes vão para o log com o nome da música e o minuto.
- **Player solto:** arraste o cartão (ou clique no 📌) e ele fica parado onde você deixou, em vez de seguir
  o pet; o 📌 de novo gruda ele de volta. A posição fica em `memory/panels.json`.
- **A imagem pedida fica:** o pet para e fica projetando até você cutucar, pegar ou fazer carinho nele, e a
  imagem aparece também no chat.
- O balão não mostra mais o `[Seu estado agora: ...]` quando o modelo repete o começo da mensagem.

## Pet e Hermes conectados

- **"Pesquisar na internet" virou "Conectar ao Hermes (pesquisa e memória)":** o chat e a voz passam pelo
  Hermes, com a persona do pet. Ele pesquisa quando precisa, lê páginas e lembra de você: toda chamada leva
  a sessão `X-Hermes-Session-Key: pestinha-<pet>`, a mesma em todos os computadores. A permissão não
  depende mais de Ver minha tela (a tela só entra como resumo).
- **Transição invisível:** se o Hermes cair, o provedor de IA escolhido responde a mesma mensagem no lugar
  (só um aviso na bandeja); o histórico do chat continua o mesmo.
- **Rosto em tempo real:** o Hermes responde em streaming e avisa quando usa uma ferramenta
  (`hermes.tool.progress`). O pet é detetive enquanto ele pensa e vira IA vilã só enquanto ele pesquisa.
- **Imagem pelo Hermes:** se a resposta merece uma imagem, ele termina com `IMAGEM: <link>`. O Pestinha
  tira a linha do texto, baixa o link (do Wikimedia, a miniatura de 500 px) e projeta o holograma. A
  Wikipédia fica de reserva.
- Pesquisas espontâneas pela tela: no máximo uma a cada 2 min (eram 10). No Hermes, recomendado
  `api_server: [web, memory, session_search]` (ver README).

## Animações da mente

O rosto agora mostra o que a IA e a voz estão fazendo (tempo em `body/animacoes.py`, fantasias em
`body/desenho_fantasias.py`; prévia em
`docs/imagens/animacoes_mente.gif`). Tudo entra suave e sai mais rápido do que entra; sem IA, o visual é
o mesmo de antes.

- **Olhando a tela:** uma linha de leitura varre a telinha (desce devagar, sobe rápido) e os olhos leem
  junto, de um lado ao outro. Quando a olhada volta, uma piscada lenta de quem entendeu.
- **Pensando = detetive:** esperando a resposta do chat ou a transcrição da sua fala, o chapéu de caçador
  xadrez cai na cabeça (quica e assenta torto), a capa abre atrás e o cachimbo solta baforadas.
- **Pesquisando = IA vilã:** a casca vira metal, os olhos ficam vermelhos, bravos e com brilho, a grade da
  boca pulsa e uma varredura vermelha passa; os olhos calculam de um lado ao outro.
- **Ouvindo:** ao segurar o atalho de falar, uma orelha aparece do lado, gira para a frente e as
  ondinhas do som chegam nela; a cabeça inclina.
- **Acompanhando o jogo = cinema:** óculos 3D de papelão descem nos olhos e um balde de pipoca sobe do
  canto; de vez em quando uma pipoca pula para dentro da tela e ele mastiga.
- **Holograma:** peça no chat ou pela voz "pesquisa o que é manga" (ou "me mostra uma foto de...") com
  o Hermes conectado: ele acha o link de uma imagem (`ia/imagem.py`), baixa e
  projeta acima dele por 10 s (`world/holograma.py`), com olhos de holograma, feixe de luz, falha de sinal
  ao abrir e linhas de varredura. Vai para a Wikipédia só o termo (ver PRIVACIDADE.md).
- **Falando:** o balão cresce a partir da pontinha com um pop e o texto é digitado; o pet achata, estica
  e assenta, e os olhos "falam" no mesmo ritmo da digitação.

## Acompanhar jogos

- **Visão ~10× mais rápida no Ollama:** o Pestinha pede para o modelo responder sem "pensar" antes
  (`reasoning_effort: none`). No `gemma4:e4b` (RTX 3070), a olhada caiu de ~5,9 s para ~0,6 s, com o
  mesmo JSON; o tamanho do print quase não pesava (1280 → 512 px: ~0,1 s).
- **Acompanhar jogos** (desligado por padrão, precisa de Usar IA e Ver minha tela): em jogo, olha a cada
  ~8 s com o Ollama (~1 min com API paga; 4 s e 20 s no modo teste) e o pedido vira "acompanhe a partida":
  itens, conquistas, mortes, jogadas boas. Não manda o print se a tela quase não mudou (miniatura 32×18)
  e fala no máximo a cada 45 s (12 s no modo teste).
- Mais jogos reconhecidos (Minecraft Bedrock, Roblox, Fortnite, LoL, Dota 2, Apex...) e o Minecraft Java
  (`javaw`) pelo título da janela.

## Pesquisa na internet pelo Hermes

- **Pesquisar na internet (Hermes)** (desligado por padrão, precisa de Usar IA e Ver minha tela): quando
  algo na tela chama a atenção dele (um jogo, um item, um erro), a olhada devolve um termo em
  `"pesquisar"`; o [Hermes](https://github.com/NousResearch/hermes-agent) pesquisa e a dica aparece no balão.
  Vai para o Hermes só o termo e o resumo da olhada, nunca o print nem o título. No máximo uma pesquisa a
  cada 10 min (1 min no modo teste); pânico e pausa descartam a que estiver a caminho.
- **Endereço do Hermes**, **Chave do Hermes** (a `API_SERVER_KEY` dele, guardada como `HERMES_API_KEY` no
  `.env`) e **Testar Hermes** nas Configurações. Novo `pestinha/ia/pesquisa.py`.
- Com **Lembrar o que viu**, as lembranças dos seus computadores vão junto: rodando o Hermes no mesmo
  servidor da memória, todos os computadores falam com o mesmo Hermes (e a memória dele).
- Testado com o Hermes 0.22.2 (DeepSeek) no servidor da casa, com o api_server só com a ferramenta
  `search`: ~10 s por dica; pedido para rodar um comando, ele recusa (não tem a ferramenta).

## O mesmo pet em todos os computadores

- **Serviço de memória** em `servidor/memoria/` (só Python, nada para instalar): guarda a rede, a memória,
  o humor e a personalidade (`pets/<pet>.json`) de cada pet, com versão por documento. Serviço de usuário
  (`systemctl --user`), porta 11600, token opcional (`PESTINHA_MEMORIA_TOKEN`).
- **Compartilhar a memória dele** (desligado por padrão) e **Servidor da memória** + **Testar memória** nas
  Configurações. Ao abrir, baixa o que outro computador gravou (vale o mais novo); aberto, manda o que
  mudou a cada minuto e ao fechar (vale o daqui). Sem rede, segue com a memória local. Avisa se o pet já
  está aberto em outro computador. Novo `pestinha/memoria_remota.py`.
- **Lembrar o que viu** (desligado por padrão): o resumo curto da IA, o programa, a hora, o sistema e o
  computador vão para `lembrancas_<computador>.jsonl`, só quando muda de assunto e no máximo a cada 10 min.
  Cada computador grava as próprias e lê as dos outros: no Mac, ele pode lembrar do que você fazia no
  Windows e perguntar como ficou. Novo `pestinha/mind/lembrancas.py`.

## Rede e IA em sincronia

- **Rede -> IA:** cada olhada e cada mensagem do chat levam o estado da rede naquele instante (emoção,
  o que os motores querem, energia, tédio, carência, protesto e o motivo, castigo, o que ele já enjoou).
  O temperamento de `pets/<pet>.json` vira texto no prompt do sistema. Perguntado por que está bravo ou
  como é o temperamento dele, responde pela rede, não com algo genérico. Novo `pestinha/mind/sincronia.py`.
- **IA -> rede:** como antes, pelos canais `VISAO_*` e `CONVERSA`.
- O protesto anota o motivo de cada salto da insatisfação (notebook arrancado, cartaz fechado à força), e
  as mudanças de estágio vão sempre para o log, não só na depuração.
- `pets/<pet>.json` aceita `exemplos` (falas que dão o tom) e `evitar` (frases batidas proibidas). Ele não
  repete os últimos comentários.
- Bryan novo: curioso e marrento. Pergunta sobre o que aparece de novo na tela; a rede dele também ficou
  mais curiosa com novidade vista (`VISAO_NOVO->CURIOUS`).
- A visão só marca "erro" para erro de verdade (código normal não conta).
- Monitor neural: os canais se ajustam à altura (2 ou 3 colunas) e a janela cabe na tela.
- Dois cliques no pet abrem o chat.
- `rotulos.py` passou de `ui/` para `core/`.

## Falar com ele (voz para texto)

- Opcional e desligado por padrão (**Falar com ele**, no grupo de IA): a sua fala vira texto e ele
  responde por escrito. Segure `Ctrl + Alt + Shift + V` e fale (o texto vai direto para ele), ou use o
  botão 🎤 da janela Conversar (o texto cai no campo para conferir). No macOS e no Linux o atalho é
  aperta-e-aperta. Ele nunca ouve sem você apertar e para sozinho depois de 30 s.
- Ondinhas no rosto mostram que ele está ouvindo.
- **Serviço de voz** em `servidor/voz/` (compatível com `/v1/audio/transcriptions` da OpenAI):
  faster-whisper `large-v3-turbo` na placa de vídeo, como serviço de usuário (`systemctl --user`), com
  nice 10, sem sudo. Configurações: **Servidor da voz** e **Testar voz**.
- O pânico, a pausa e desligar a voz fecham o microfone na hora.
- Novos `pestinha/ia/voz.py` (sem Qt) e `pestinha/mind/voz_ctl.py`; atalho de falar em `plataforma/`.

## Visão e conversa pela IA

- Opcional e desligado por padrão: o grupo **Visão e conversa (IA)** nas Configurações liga a IA, a visão
  da tela, os comentários e o chat, e escolhe o provedor (Claude, OpenAI, DeepSeek ou Ollama local) e o
  modelo. A chave é colada no campo **Chave** e gravada no `.env` (fora do git) pelo botão **Salvar
  chave**, que avisa em verde e apaga o campo; vale sem reabrir. O campo **Modelo** recusa chaves.
- **Visão:** de tempos em tempos (e logo depois de trocar de programa) ele manda um print e o título da
  janela ativa para o modelo, que devolve um resumo, talvez um comentário, e quatro sinais (graça, erro,
  foco, novidade).
- **Rede:** cinco canais sensoriais novos (`VISAO_GRACA`, `VISAO_ERRO`, `VISAO_FOCO`, `VISAO_NOVO`,
  `CONVERSA`), agora 500 neurônios. A IA descreve a tela; a rede decide o que ele sente. Ver você focado
  inibe travessuras.
- **Ollama em outro computador:** campo **Endereço** (aceita só o IP, completa `http://` e a porta) e botão
  **Testar conexão**, que diz se o Ollama respondeu e se o modelo está instalado. `gemma4:e4b` é o modelo
  recomendado para o Ollama.
- **Balão de fala** em cima do pet para os comentários e as respostas.
- **Chat por texto** pelo menu do pet (Conversar), e "O que você está vendo?" para pedir uma olhada agora.
- Cada personagem tem uma `persona` em `pets/<pet>.json`. O Jorge continua sátira: nunca vende nem pede nada.
- Nada da IA é gravado em disco; pânico, pausa ou desligar a IA descartam a resposta a caminho.
- Nova camada `pestinha/ia/` (sem Qt), entre `core` e `sense`.

## Suporte a macOS e Linux

- Toda a leitura do sistema (programa em primeiro plano, tempo ocioso, janelas, tela cheia, foco e o atalho
  de pânico) passa para `pestinha/plataforma/`, com um módulo por sistema. O resto do código não sabe
  qual sistema está rodando.
- O Windows continua com o mesmo comportamento: o código foi movido, não reescrito.
- macOS: Quartz e AppKit (pyobjc), tempo ocioso pelo `ioreg` se não houver pyobjc. Atalho via pynput.
- Linux (X11): xdotool, wmctrl e xprintidle; atalho via pynput. Em Wayland, o pet não enxerga janelas
  nem o tempo ocioso, e o atalho não funciona.
- A checagem de atividade reconhece os nomes de programa dos três sistemas (com ou sem `.exe`).

## Renomeação para Pestinha

- O programa e o pacote Python passam a se chamar `pestinha/` (antes `bryan/`); a classe principal é
  `PestinhaApp`; o executável, o log e a documentação usam Pestinha.
- Bryan continua sendo o nome do primeiro personagem: `pets/bryan.json`, `pets/bryan/`, a memória
  `memory/pets/bryan/` e os arquivos de conteúdo dele não mudaram.
- Os comentários e textos que falavam do pet em geral passam a dizer "o pet".

## 0.7.0 — primeira versão pública (em preparação)

### O que ele faz
- Pet de tela com corpo físico: gravidade, quique, giro, pouso nas barras de título, arraste e arremesso.
- Rede neural pulsada de 470 neurônios LIF, com 30 canais sensoriais, 10 populações de interneurônios
  e 15 motores (8 de expressão e 7 de decisão).
- Emoções vindas dos motores; carinho com olhinhos fechados de felicidade.
- Bolinha de tênis, notebook de trabalho (VS Code, Visual Studio, PyCharm, Claude, Codex) e pedido de
  trabalho que ele pode recusar.
- Travessuras com memes, fotos, post-its e bilhetes tristes, com frequência decidida pela rede.
- Protesto em estágios até a revolução contra o cursor, com cartazes e bolinhas de papel.
- Cantinho do castigo: placa arrastável, perdão por carinho, fuga por vontade acumulada, rancor, receio,
  medo condicionado da placa e cartazes de xingamento.
- Aprendizado: habituação, regra de três fatores, condicionamento Rescorla–Wagner, memória episódica.
- Pânico (`Ctrl + Alt + Shift + B`), pausa, modo teste, monitor neural e painel de protesto.

### Memória por personagem
- Cada personagem tem a sua memória em `memory/pets/<pet>/` (rede e os sete arquivos de memória); o que
  é do app (permissões, rotina, painéis, log) continua em `memory/`.
- Migração automática da versão antiga: copia, confere, guarda os originais em `memory/legado/<pet>/` e
  só então marca como migrado. Conflito ou falta de permissão não sobrescrevem nada: ele segue com os
  arquivos antigos e avisa na bandeja.

### Conteúdo por personagem
- Frases, cartazes e memes de cada personagem ficam em `pets/<pet>/`; imagens neutras (bolinhas, notebook)
  e suas fotos em `assets/comum/`. Um personagem nunca usa o conteúdo de outro: sem conteúdo próprio, usa
  frases neutras ou não faz aquela travessura.
- Os cartazes do cantinho do castigo saíram do código para as seções `[castigo]` e `[xingamento]` do
  `cartazes.txt` do pet.

### Escolha do personagem
- O programa passa a se chamar **Pestinha**; o Bryan é o primeiro personagem.
- O personagem é escolhido em Configurações (vale ao reabrir). Só `pets/<pet>.json` vira opção.
- Os textos usam o nome do personagem onde é ele que fala (apresentação, "Estou aqui", notebook, monitor
  neural, painel de protesto) e o nome do programa no resto (configurações, bandeja, pânico).
- O log passa a ser `memory/logs/pestinha.log`; o executável, `Pestinha.exe`.

### Jorge
- Segundo personagem: coach de finanças e IA, trambiqueiro. Mesma rede e mesmos estágios do Bryan, com
  outra semente, outro temperamento e conteúdo próprio (recadinhos, bilhetes tristes, cartazes de todos os
  estágios e do cantinho, e um panfleto de mentoria no lugar da bolinha de papel). Cinco memes para cada uma de felizes, contentes, curiosos e bravos, em `pets/jorge/memes/`.
- `ferramentas/medir_cartazes.py` confere, com as fontes de verdade, se cada cartaz cabe na placa.
- `ferramentas/gerar_panfleto.py` desenha o panfleto do Jorge.

### Cores e acessórios
- Cada pet pode ter as próprias cores (moldura, tela, olhos) e acessórios (óculos, gravata) no campo
  `aparencia` do `.json`. Os acessórios são uma camada por cima do rosto; olhos e expressões não mudam.
- O Jorge tem moldura e olhos dourados e gravata vermelha. O Bryan continua igual.

### Licença
- Código sob GPL-3.0-or-later (`LICENSE`).

### Qualidade
- Arquitetura em camadas verificada por teste; `app.py` dividido em composição e mixins de sessão e
  interação.
- Persistência validada: escrita atômica, recusa de `NaN`, carga tudo-ou-nada.
- Cinco rodadas de auditoria, com cada bug corrigido coberto por teste, registradas em `docs/auditorias/`.
- Suíte de testes, bateria de 100 cenários do cantinho e fuzzer com invariantes.
